"""TETKO — модульная система TETKO UserBot."""

# Версия API TETKO-COMPAT (стиль модулей)
__compat__ = "0.0.9.0"
__compat_style__ = "TETKO-COMPAT"
from core.tetko.module import Module
from core.tetko.decorators import command, watcher, callback, loop
from core.tetko.config import ModuleConfig
from core.tetko.registry import Registry, Command
from core.tetko.loader import ModuleLoader
from core.tetko.dispatcher import EventDispatcher
from core.tetko.kernel import Kernel
from core.tetko.exceptions import (
    TetkoError,
    ModuleError,
    ModuleLoadError,
    ModuleValidationError,
    ModuleRegistrationError,
    ModuleNotFoundError,
    CommandError,
    CommandNotFoundError,
    CommandRegistrationError,
    ConfigError,
)

__all__ = [
    "Module",
    "command",
    "watcher",
    "callback",
    "loop",
    "ModuleConfig",
    "Registry",
    "Command",
    "ModuleLoader",
    "EventDispatcher",
    "Kernel",
    "TetkoError",
    "ModuleError",
    "ModuleLoadError",
    "ModuleValidationError",
    "ModuleRegistrationError",
    "ModuleNotFoundError",
    "CommandError",
    "CommandNotFoundError",
    "CommandRegistrationError",
    "ConfigError",
]
