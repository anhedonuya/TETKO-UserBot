"""Загрузчик MCUB-модулей поверх TETKO.

Этап 1: модуль загружается, находит класс-наследник ModuleBase,
регистрирует @command/@watcher/@loop через tetko-декораторы.

Не поддерживает (пока):
    - полноценный kernel.register.* (этап 2)
    - utils.* (этап 5)
    - @callback, Button, inline_form (этап 4)
    - ModuleConfig UI (этап 3)
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from .detector import is_mcub_module
from .fake_package import fakes_active


log = logging.getLogger("TETKO.mcub_compat.loader")


def _register_decorated_attrs(module_instance: Any, tetko_registry: Any) -> list[str]:
    """Пробегает по атрибутам инстанса и регистрирует декорированные функции.

    В этапе 1 используется минимальный набор: command/watcher/loop/callback.
    Полная эмуляция kernel.register.* — в этапе 2.
    """
    from core.tetko.registry import Command as TetkoCommand

    registered: list[str] = []

    for attr_name in dir(module_instance):
        if attr_name.startswith("__"):
            continue
        try:
            attr = getattr(module_instance, attr_name)
        except Exception:
            continue
        if not callable(attr):
            continue

        # tetko-декораторы вешают метаданные так:
        cmd_meta = getattr(attr, "__tetko_command__", None)
        if cmd_meta:
            try:
                cmd = TetkoCommand(
                    name=cmd_meta["name"],
                    func=attr,
                    module=module_instance,
                    aliases=cmd_meta.get("aliases") or [],
                    doc=cmd_meta.get("doc", ""),
                    only_for=cmd_meta.get("only_for"),
                    **cmd_meta.get("kwargs", {}),
                )
                tetko_registry.register_command(cmd)
                registered.append(f"command:{cmd_meta['name']}")
            except Exception as e:
                log.warning(f"[mcub_compat] не удалось зарегистрировать {attr_name}: {e}")
            continue

        if hasattr(attr, "__tetko_watcher__"):
            try:
                tetko_registry.register_watcher(module_instance, attr)
                registered.append(f"watcher:{attr_name}")
            except Exception as e:
                log.warning(f"[mcub_compat] watcher {attr_name}: {e}")
            continue

        if hasattr(attr, "__tetko_callback__"):
            try:
                tetko_registry.register_callback(module_instance, attr)
                registered.append(f"callback:{attr_name}")
            except Exception as e:
                log.warning(f"[mcub_compat] callback {attr_name}: {e}")
            continue

        loop_meta = getattr(attr, "__tetko_loop__", None)
        if loop_meta:
            try:
                tetko_registry.register_loop(
                    module_instance, attr, float(loop_meta.get("interval", 60))
                )
                registered.append(f"loop:{attr_name}")
            except Exception as e:
                log.warning(f"[mcub_compat] loop {attr_name}: {e}")
            continue

    return registered


def _find_module_class(py_module: Any) -> Any:
    """Ищет класс-наследник _MCUB_ModuleBase в загруженном модуле."""
    from .fake_package import _MCUB_ModuleBase

    for attr_name in dir(py_module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(py_module, attr_name)
        if not isinstance(attr, type):
            continue
        if attr is _MCUB_ModuleBase:
            continue
        try:
            if issubclass(attr, _MCUB_ModuleBase):
                return attr
        except TypeError:
            continue
    return None


async def load_mcub_module(
    tetko_kernel: Any,
    file_path: str | Path,
    module_name: str | None = None,
) -> Any:
    """Загружает MCUB-модуль из файла. Возвращает инстанс модуля.

    Подменяет sys.modules на MCUB-фейки на время импорта.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MCUB-модуль не найден: {path}")

    mod_name = module_name or path.stem
    spec_name = f"mcub_compat_modules.{mod_name}"

    # Читаем код, проверяем что это действительно mcub-модуль
    code = path.read_text(encoding="utf-8")
    if not is_mcub_module(code):
        raise ValueError(
            f"Файл {path.name} не похож на MCUB-модуль — используй обычный загрузчик"
        )

    # 1. Компилируем и исполняем с активными фейками
    with fakes_active():
        try:
            spec = importlib.util.spec_from_file_location(spec_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Не удалось создать spec для {path}")
            py_module = importlib.util.module_from_spec(spec)
            sys.modules[spec_name] = py_module
            spec.loader.exec_module(py_module)
        except Exception as e:
            log.exception(f"[mcub_compat] ошибка исполнения {path.name}")
            raise ImportError(f"Ошибка импорта MCUB-модуля {mod_name}: {e}") from e

    # 2. Ищем класс
    module_class = _find_module_class(py_module)
    if module_class is None:
        raise ImportError(
            f"В файле {path.name} не найден класс-наследник ModuleBase"
        )

    # 3. Инстанцируем и регистрируем в tetko
    try:
        instance = module_class(
            kernel=tetko_kernel,
            client=getattr(tetko_kernel, "client", None),
            register=getattr(tetko_kernel, "register", None),
        )
    except TypeError:
        # Некоторые ModuleBase-классы принимают только kernel
        instance = module_class(tetko_kernel)

    registry = tetko_kernel.registry
    registry.register_module(instance)

    registered = _register_decorated_attrs(instance, registry)
    log.info(
        f"[mcub_compat] загружен {mod_name}: {len(registered)} обработчиков "
        f"({', '.join(registered[:5])}{'...' if len(registered) > 5 else ''})"
    )

    # 4. Хук on_load
    try:
        on_load = getattr(instance, "on_load", None)
        if callable(on_load):
            result = on_load()
            if hasattr(result, "__await__"):
                await result
    except Exception as e:
        log.error(f"[mcub_compat] on_load {mod_name} упал: {e}")

    return instance


async def unload_mcub_module(tetko_kernel: Any, module_name: str) -> bool:
    """Снимает модуль с регистрации и чистит sys.modules."""
    registry = tetko_kernel.registry
    mod = registry.get_module(module_name)
    if mod is None:
        return False

    try:
        on_unload = getattr(mod, "on_unload", None)
        if callable(on_unload):
            result = on_unload()
            if hasattr(result, "__await__"):
                await result
    except Exception as e:
        log.error(f"[mcub_compat] on_unload {module_name}: {e}")

    registry.unregister_module(module_name)

    full_name = f"mcub_compat_modules.{module_name}"
    sys.modules.pop(full_name, None)

    log.info(f"[mcub_compat] выгружен {module_name}")
    return True


__all__ = ["load_mcub_module", "unload_mcub_module"]
