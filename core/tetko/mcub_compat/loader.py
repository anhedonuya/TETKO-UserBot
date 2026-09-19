"""Загрузчик MCUB-модулей поверх TETKO."""
from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from .detector import is_mcub_module
from .kernel_proxy import KernelProxy
from .module_base import MCUBModuleBase
from .register_shim import RegisterShim, run_autostart_loops, stop_all_loops


log = logging.getLogger("TETKO.mcub_compat.loader")


def _install_fakes() -> None:
    """Подменить ModuleBase в core.lib.loader.module_base на MCUBModuleBase.

    Декораторы (command/watcher/loop/...) остаются РЕАЛЬНЫМИ — они уже
    вешают `_mcub_*` атрибуты на функции в core/lib/loader/module_base.py.
    """
    # 1. Убеждаемся, что реальный модуль core.lib.loader.module_base загружен
    if "core.lib.loader.module_base" not in sys.modules:
        importlib.import_module("core.lib.loader.module_base")

    mb = sys.modules["core.lib.loader.module_base"]
    mb.ModuleBase = MCUBModuleBase

    # 2. kernel_proxy — wrap_event_for_module no-op
    if "core.lib.loader.kernel_proxy" not in sys.modules:
        importlib.import_module("core.lib.loader.kernel_proxy")
    kp = sys.modules["core.lib.loader.kernel_proxy"]
    kp.wrap_event_for_module = lambda e, *a, **kw: e

    
    # 4. core_inline.* — подменяем на inline_shim
    try:
        from . import inline_shim as _ishim
        import types as _t2
        for _mod_name in (
            "core_inline",
            "core_inline.lib",
            "core_inline.lib.manager",
            "core_inline.api",
            "core_inline.api.inline",
            "core_inline.api.core",
            "core_inline.handlers",
            "core_inline.bot",
        ):
            if _mod_name not in sys.modules:
                sys.modules[_mod_name] = _t2.ModuleType(_mod_name)
            _m = sys.modules[_mod_name]
            # Пихаем весь shim во все подмодули, чтобы любые импорты находились
            for _n in dir(_ishim):
                if _n.startswith("_"):
                    continue
                setattr(_m, _n, getattr(_ishim, _n))
    except Exception as _e:
        log.warning(f"[mcub_compat] core_inline fake: {_e}")

# 3. module_config — подменяем на mcub_compat.module_config
    import importlib as _il
    if "core.lib.loader.module_config" not in sys.modules:
        try:
            _il.import_module("core.lib.loader.module_config")
        except Exception:
            pass
    try:
        from . import module_config as _mcm
        if "core.lib.loader.module_config" in sys.modules:
            _target = sys.modules["core.lib.loader.module_config"]
        else:
            import types as _types
            _target = _types.ModuleType("core.lib.loader.module_config")
            sys.modules["core.lib.loader.module_config"] = _target
        for _name in (
            "ValidationError", "Validator",
            "Boolean", "Integer", "Float", "String", "Choice", "List",
            "DictType", "Secret", "Placeholders", "RegExp", "Link", "TelegramID",
            "EntityLike", "Emoji", "MultiChoice", "Union", "Hidden", "NoneType",
            "ConfigValue", "ModuleConfig",
            "Row", "Divider", "Group", "Buttons",
        ):
            if hasattr(_mcm, _name):
                setattr(_target, _name, getattr(_mcm, _name))
    except Exception as _e:
        log.warning(f"[mcub_compat] module_config fake: {_e}")



def _stub_decorator(*args, **kwargs):
    def deco(fn):
        return fn
    if args and callable(args[0]) and not kwargs:
        return args[0]
    return deco


def _find_module_class(py_module: Any) -> Any:
    for attr_name in dir(py_module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(py_module, attr_name)
        if not isinstance(attr, type):
            continue
        if attr is MCUBModuleBase:
            continue
        try:
            if issubclass(attr, MCUBModuleBase):
                return attr
        except TypeError:
            continue
    return None


async def load_mcub_module(
    tetko_kernel: Any,
    file_path: str | Path,
    module_name: str | None = None,
) -> Any:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MCUB-модуль не найден: {path}")

    mod_name = module_name or path.stem
    spec_name = f"mcub_compat_modules.{mod_name}"

    code = path.read_text(encoding="utf-8")
    if not is_mcub_module(code):
        raise ValueError(
            f"Файл {path.name} не похож на MCUB-модуль — используй обычный загрузчик"
        )

    # однократная инициализация подсистем mcub_compat
    if not getattr(tetko_kernel, "_mcub_subsystems_installed", False):
        try:
            from .config_ui import install as _install_cfg_ui
            _install_cfg_ui(tetko_kernel)
        except Exception as e:
            log.warning(f"[mcub_compat] config_ui: {e}")
        try:
            from .callback_dispatch import install_callback_handler
            _bot = getattr(tetko_kernel, "bot_client", None)
            if _bot is not None:
                install_callback_handler(tetko_kernel, _bot)
        except Exception as e:
            log.warning(f"[mcub_compat] callback_dispatch: {e}")
        tetko_kernel._mcub_subsystems_installed = True

    _install_fakes()
    try:
        spec = importlib.util.spec_from_file_location(spec_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Не удалось создать spec для {path}")
        py_module = importlib.util.module_from_spec(spec)
        sys.modules[spec_name] = py_module
        spec.loader.exec_module(py_module)
    except Exception as e:
        log.exception(f"[mcub_compat] ошибка исполнения {path.name}")
        try:
            path.unlink()
            log.warning(f"[mcub_compat] удалён сбойный модуль: {path}")
        except Exception as _rm_err:
            log.warning(f"[mcub_compat] не удалось удалить {path}: {_rm_err}")
        raise ImportError(f"Ошибка импорта MCUB-модуля {mod_name}: {e}") from e

    module_class = _find_module_class(py_module)
    if module_class is None:
        raise ImportError(f"В файле {path.name} не найден класс-наследник ModuleBase")

    # Создаём proxy ДО инстанса, чтобы __init__ модуля видел kernel.register
    proxy = KernelProxy(tetko_kernel, None)

    class _PlaceholderModule:
        name = "Pending"
    proxy.register.module = _PlaceholderModule()

    try:
        instance = module_class(
            kernel=proxy,
            client=getattr(tetko_kernel, "client", None),
            register=proxy.register,
        )
    except TypeError:
        instance = module_class(proxy)

    # Дописываем module_instance в proxy (нужен register_shim)
    object.__setattr__(proxy, "_module", instance)
    proxy.register.module = instance

    instance.kernel = proxy
    instance._register = proxy.register

    registry = tetko_kernel.registry

    # Если модуль уже загружен — сначала выгружаем
    existing = registry.get_module(mod_name)
    if existing is not None:
        try:
            await unload_mcub_module(tetko_kernel, mod_name)
        except Exception as e:
            log.warning(f"[mcub_compat] unload-existing {mod_name}: {e}")

    registry.register_module(instance)

    try:
        run_autostart_loops(proxy.register)
    except Exception as e:
        log.warning(f"[mcub_compat] autostart: {e}")

    try:
        on_load = getattr(instance, "on_load", None)
        if callable(on_load):
            result = on_load()
            if hasattr(result, "__await__"):
                await result
    except Exception as e:
        log.error(f"[mcub_compat] on_load {mod_name}: {e}")

    log.info(
        f"[mcub_compat] загружен {mod_name}: "
        f"команд={len(proxy.register.get_commands())}, "
        f"watcher={len(proxy.register.get_watchers())}, "
        f"loop={len(proxy.register.get_loops())}"
    )
    return instance


async def unload_mcub_module(tetko_kernel: Any, module_name: str) -> bool:
    registry = tetko_kernel.registry
    mod = registry.get_module(module_name)
    if mod is None:
        return False

    proxy = getattr(mod, "kernel", None)
    if proxy is not None and hasattr(proxy, "register"):
        try:
            stop_all_loops(proxy.register)
        except Exception:
            pass

    try:
        on_unload = getattr(mod, "on_unload", None)
        if callable(on_unload):
            result = on_unload()
            if hasattr(result, "__await__"):
                await result
    except Exception as e:
        log.error(f"[mcub_compat] on_unload {module_name}: {e}")

    registry.unregister_module(module_name)
    sys.modules.pop(f"mcub_compat_modules.{module_name}", None)
    log.info(f"[mcub_compat] выгружен {module_name}")
    return True


__all__ = ["load_mcub_module", "unload_mcub_module"]
