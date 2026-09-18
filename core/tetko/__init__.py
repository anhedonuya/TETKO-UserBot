"""TETKO — модульная система TETKO UserBot."""
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
