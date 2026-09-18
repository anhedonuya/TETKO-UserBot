"""Loader — загрузчик TETKO-модулей."""
from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

from core.tetko.module import Module
from core.tetko.registry import Registry, Command
from core.tetko.exceptions import (
    ModuleLoadError,
    ModuleValidationError,
)

log = logging.getLogger("TETKO.tetko.loader")


class Loader:
    """Загрузчик модулей TETKO."""

    def __init__(self, registry: Registry, kernel: Optional[Any] = None,
                 modules_dir: str = "modules",
                 custom_dir: str = "modules_custom"):
        self.registry = registry
        self.kernel = kernel
        self.modules_dir = Path(modules_dir)
        self.custom_dir = Path(custom_dir)
        self._loaded_files: dict[str, Path] = {}  # module_name → file_path

    # ═══════════════════════════════════════
    #   ЗАГРУЗКА
    # ═══════════════════════════════════════
    def load_all(self) -> int:
        """Загрузить все модули из modules/ и modules_custom/."""
        count = 0
        for directory in (self.modules_dir, self.custom_dir):
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                if self._load_file(path):
                    count += 1
        log.info(f"[loader] Загружено модулей: {count}")
        return count

    def load_file(self, path: str | Path) -> bool:
        """Загрузить один модуль."""
        p = Path(path)
        if not p.exists():
            p = self.modules_dir / p
        if not p.exists():
            raise ModuleLoadError(f"Файл не найден: {path}")
        return self._load_file(p)

    # ═══════════════════════════════════════
    #   ВНУТРЕННЕЕ
    # ═══════════════════════════════════════
    def _load_file(self, path: Path) -> bool:
        """Импортировать файл, найти классы Module, зарегистрировать."""
        module_name = f"tetko_mod_{path.stem}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ModuleLoadError(f"Не могу создать spec для {path}")

            mod = importlib.util.module_from_spec(spec)

            # Инжектим тетко-API в модуль (для удобства)
            mod.__dict__["tetko_module"] = Module
            from core.tetko.decorators import command, watcher, callback, loop
            mod.__dict__["command"] = command
            mod.__dict__["watcher"] = watcher
            mod.__dict__["callback"] = callback
            mod.__dict__["loop"] = loop

            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
        except Exception as e:
            log.error(f"[!] Ошибка импорта {path.name}:\n{traceback.format_exc()}")
            return False

        # Ищем классы-наследники Module
        found_any = False
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj is Module:
                continue
            if not issubclass(obj, Module):
                continue

            try:
                instance = obj(self.kernel)
                self._register_instance(instance)
                found_any = True
            except Exception as e:
                log.error(f"[!] Ошибка создания {obj.__name__}: {e}")
                log.error(traceback.format_exc())

        if not found_any:
            log.warning(f"[?] В {path.name} не найден класс-наследник Module")

        return found_any

    def _register_instance(self, module: Module) -> None:
        """Зарегистрировать модуль и его команды в Registry."""
        # Валидация
        if not module.name or module.name == "Unnamed":
            raise ModuleValidationError(
                f"Модуль {module.__class__.__name__} без имени"
            )

        # Регистрация модуля
        self.registry.register_module(module)

        # Собираем команды / watchers / callbacks / loops
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            # Команды
            meta = getattr(attr, "__tetko_command__", None)
            if meta:
                cmd = Command(
                    name=meta["name"],
                    func=attr,
                    module=module,
                    aliases=meta["aliases"],
                    doc=meta["doc"],
                    **meta.get("kwargs", {}),
                )
                try:
                    self.registry.register_command(cmd)
                except Exception as e:
                    log.error(f"[!] Не могу зарегистрировать .{cmd.name}: {e}")

            # Watchers
            if getattr(attr, "__tetko_watcher__", None):
                self.registry.register_watcher(module, attr)

            # Callbacks
            if getattr(attr, "__tetko_callback__", None):
                self.registry.register_callback(module, attr)

            # Loops
            loop_meta = getattr(attr, "__tetko_loop__", None)
            if loop_meta:
                self.registry.register_loop(
                    module, attr, loop_meta.get("interval", 60)
                )

    # ═══════════════════════════════════════
    #   ВЫГРУЗКА
    # ═══════════════════════════════════════
    async def unload(self, module_name: str) -> bool:
        """Выгрузить модуль (снять с регистрации + on_unload)."""
        module = self.registry.get_module(module_name)
        if module is None:
            log.warning(f"[loader] Модуль {module_name} не найден")
            return False

        try:
            await module.on_unload()
        except Exception as e:
            log.error(f"[!] on_unload упал в {module_name}: {e}")

        self.registry.unregister_module(module_name)
        return True

    async def reload(self, module_name: str) -> bool:
        """Перезагрузить модуль (нужно имя файла, не класса)."""
        module = self.registry.get_module(module_name)
        if module is None:
            log.warning(f"[loader] Модуль {module_name} не найден")
            return False

        # Ищем файл по имени класса
        filename = f"{module_name.lower()}.py"
        for d in (self.modules_dir, self.custom_dir):
            path = d / filename
            if path.exists():
                await self.unload(module_name)
                return self._load_file(path)

        log.warning(f"[loader] Файл для {module_name} не найден")
        return False
