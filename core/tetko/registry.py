"""Registry — реестр модулей и команд TETKO."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from core.tetko.exceptions import (
    ModuleRegistrationError,
    CommandRegistrationError,
)

log = logging.getLogger("TETKO.tetko.registry")


class Command:
    """Обёртка над командой модуля."""

    def __init__(
        self,
        name: str,
        func: Callable,
        module: Any,
        aliases: list[str] | None = None,
        doc: Any = "",
        **kwargs: Any,
    ):
        self.name = name
        self.func = func
        self.module = module
        self.aliases: list[str] = list(aliases or [])
        self.doc = doc
        self.kwargs = kwargs

    async def call(self, client, event, args: list[str]):
        """Вызвать команду, подбирая аргументы по её сигнатуре."""
        import inspect
        sig = inspect.signature(self.func)
        params = list(sig.parameters.values())

        # bound method — self уже связан, params содержит только реальные аргументы
        # Ожидаемые варианты:
        #   (event)          → func(event)
        #   (event, args)    → func(event, args)
        #   (event, text)    → func(event, args)   # args как список
        if len(params) == 0:
            return await self.func()
        if len(params) == 1:
            return await self.func(event)
        # >= 2 — передаём event + args
        return await self.func(event, args)

    def __repr__(self) -> str:
        return f"<Command .{self.name} ({self.module.name})>"


class Registry:
    """Реестр модулей и команд TETKO."""

    def __init__(self):
        self._modules: dict[str, Any] = {}            # name → Module
        self._commands: dict[str, Command] = {}       # name → Command
        self._aliases: dict[str, str] = {}            # alias → command_name
        self._watchers: list[tuple[Any, Callable]] = []
        self._callbacks: list[tuple[Any, Callable]] = []
        self._loops: list[tuple[Any, Callable, float]] = []

    # ═══════════════════════════════════════
    #   МОДУЛИ
    # ═══════════════════════════════════════
    def register_module(self, module: Any) -> None:
        """Зарегистрировать модуль."""
        if module.name in self._modules:
            raise ModuleRegistrationError(
                f"Модуль {module.name!r} уже зарегистрирован"
            )
        self._modules[module.name] = module
        log.debug(f"[+] Модуль: {module}")

    def unregister_module(self, name: str) -> Optional[Any]:
        """Снять модуль с регистрации + все его команды."""
        module = self._modules.pop(name, None)
        if module is None:
            return None

        # Снимаем команды
        to_remove = [
            cmd_name for cmd_name, cmd in self._commands.items()
            if cmd.module is module
        ]
        for cmd_name in to_remove:
            del self._commands[cmd_name]

        # Снимаем алиасы
        self._aliases = {
            alias: target for alias, target in self._aliases.items()
            if target in self._commands
        }

        # Снимаем watchers/callbacks/loops
        self._watchers = [(m, w) for m, w in self._watchers if m is not module]
        self._callbacks = [(m, c) for m, c in self._callbacks if m is not module]
        self._loops = [(m, l, i) for m, l, i in self._loops if m is not module]

        log.debug(f"[-] Модуль: {module}")
        return module

    def get_module(self, name: str) -> Optional[Any]:
        return self._modules.get(name)

    def list_modules(self) -> dict[str, str]:
        """{имя: версия}"""
        return {m.name: m.version for m in self._modules.values()}

    # ═══════════════════════════════════════
    #   КОМАНДЫ
    # ═══════════════════════════════════════
    def register_command(self, cmd: Command) -> None:
        """Зарегистрировать команду."""
        key = cmd.name.lower()
        if key in self._commands:
            existing = self._commands[key]
            raise CommandRegistrationError(
                f"Команда .{key} уже зарегистрирована "
                f"модулем {existing.module.name!r}"
            )
        self._commands[key] = cmd

        # Алиасы
        for alias in cmd.aliases:
            a = alias.lower()
            if a in self._aliases and self._aliases[a] != key:
                log.warning(f"Алиас .{a} перезаписан")
            self._aliases[a] = key

        log.debug(f"[+] Команда: {cmd}")

    def find_command(self, name: str) -> Optional[Command]:
        """Найти команду по имени или алиасу."""
        key = name.lower()
        if key in self._commands:
            return self._commands[key]
        if key in self._aliases:
            return self._commands.get(self._aliases[key])
        return None

    def list_commands(self) -> dict[str, str]:
        """{команда: имя_модуля}"""
        return {
            name: cmd.module.name
            for name, cmd in self._commands.items()
        }

    # ═══════════════════════════════════════
    #   WATCHERS / CALLBACKS / LOOPS
    # ═══════════════════════════════════════
    def register_watcher(self, module: Any, func: Callable) -> None:
        self._watchers.append((module, func))
        log.debug(f"[+] Watcher: {func.__name__} ({module.name})")

    def register_callback(self, module: Any, func: Callable) -> None:
        self._callbacks.append((module, func))
        log.debug(f"[+] Callback: {func.__name__} ({module.name})")

    def register_loop(self, module: Any, func: Callable, interval: float) -> None:
        self._loops.append((module, func, interval))
        log.debug(f"[+] Loop: {func.__name__} ({module.name}, {interval}s)")

    def list_watchers(self) -> list:
        return list(self._watchers)

    def list_callbacks(self) -> list:
        return list(self._callbacks)

    def list_loops(self) -> list:
        return list(self._loops)

    # ═══════════════════════════════════════
    #   ОБЩЕЕ
    # ═══════════════════════════════════════
    def clear(self) -> None:
        self._modules.clear()
        self._commands.clear()
        self._aliases.clear()
        self._watchers.clear()
        self._callbacks.clear()
        self._loops.clear()

    @property
    def modules_count(self) -> int:
        return len(self._modules)

    @property
    def commands_count(self) -> int:
        return len(self._commands)

    def __repr__(self) -> str:
        return (
            f"<Registry modules={self.modules_count} "
            f"commands={self.commands_count}>"
        )
