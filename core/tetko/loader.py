"""Loader — загрузчик модулей TETKO."""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from core.tetko.exceptions import (
    ModuleLoadError,
    ModuleNotFoundError,
    ModuleValidationError,
)
from core.tetko.module import Module
from core.tetko.registry import Command, Registry

log = logging.getLogger("TETKO.tetko.loader")


class ModuleLoader:
    """Загрузчик модулей TETKO-COMPAT."""

    def __init__(self, registry: Registry, kernel: Optional[Any] = None):
        self.registry = registry
        self.kernel = kernel
        self.modules_dir = Path("modules")
        self.modules_dir.mkdir(parents=True, exist_ok=True)

    async def load_module_from_file(self, file_path: str | Path) -> Module:
        """Загрузить модуль из .py файла."""
        path = Path(file_path)
        if not path.exists():
            raise ModuleNotFoundError(f"Файл {path} не найден")

        mod_name = path.stem
        module_spec_name = f"tetko_user_modules.{mod_name}"

        try:
            spec = importlib.util.spec_from_file_location(module_spec_name, path)
            if spec is None or spec.loader is None:
                raise ModuleLoadError(f"Не удалось создать spec для {path}")

            py_module = importlib.util.module_from_spec(spec)
            sys.modules[module_spec_name] = py_module
            spec.loader.exec_module(py_module)
        except Exception as e:
            log.error(f"Ошибка выполнения файла {path}: {e}")
            raise ModuleLoadError(f"Ошибка синтаксиса/выполнения {mod_name}: {e}") from e

        module_class = None
        for attr_name in dir(py_module):
            attr = getattr(py_module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Module)
                and attr is not Module
            ):
                module_class = attr
                break

        if not module_class:
            raise ModuleValidationError(
                f"В файле {path.name} не найден класс, унаследованный от Module"
            )

        mod_instance = module_class(kernel=self.kernel)
        self.registry.register_module(mod_instance)

        for attr_name in dir(mod_instance):
            attr = getattr(mod_instance, attr_name)

            cmd_meta = getattr(attr, "__tetko_command__", None)
            if cmd_meta:
                cmd = Command(
                    name=cmd_meta["name"],
                    func=attr,
                    module=mod_instance,
                    aliases=cmd_meta["aliases"],
                    doc=cmd_meta["doc"],
                    **cmd_meta["kwargs"],
                )
                self.registry.register_command(cmd)

            if hasattr(attr, "__tetko_watcher__"):
                self.registry.register_watcher(mod_instance, attr)

            if hasattr(attr, "__tetko_callback__"):
                self.registry.register_callback(mod_instance, attr)

            loop_meta = getattr(attr, "__tetko_loop__", None)
            if loop_meta:
                self.registry.register_loop(
                    mod_instance, attr, loop_meta["interval"]
                )

        try:
            await mod_instance.on_load()
        except Exception as e:
            log.error(f"Ошибка в on_load модуля {mod_instance.name}: {e}")

        log.info(f"✅ Модуль {mod_instance.name} успешно загружен")
        return mod_instance

    async def unload_module(self, name: str) -> bool:
        """Выгрузить модуль по имени."""
        mod = self.registry.get_module(name)
        if not mod:
            return False

        try:
            await mod.on_unload()
        except Exception as e:
            log.error(f"Ошибка в on_unload модуля {name}: {e}")

        self.registry.unregister_module(name)

        full_name = f"tetko_user_modules.{name}"
        sys.modules.pop(full_name, None)

        log.info(f"🗑 Модуль {name} выгружен")
        return True

    async def load_all(self) -> int:
        """Загрузить все .py модули из папки modules/."""
        count = 0
        for p in self.modules_dir.glob("*.py"):
            if p.name.startswith("_"):
                continue
            try:
                await self.load_module_from_file(p)
                count += 1
            except Exception as e:
                log.error(f"Ошибка загрузки {p.name}: {e}")
        return count
