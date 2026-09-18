"""TETKO — модульная система TETKO UserBot."""
from core.tetko.module import Module
from core.tetko.decorators import command, watcher, callback, loop
from core.tetko.config import ModuleConfig
from core.tetko.exceptions import (
    TetkoError,
    ModuleError,
    ModuleLoadError,
    ModuleValidationError,
    ModuleNotFoundError,
    CommandError,
    CommandNotFoundError,
    ConfigError,
)

__all__ = [
    "Module",
    "command",
    "watcher",
    "callback",
    "loop",
    "ModuleConfig",
    "TetkoError",
    "ModuleError",
    "ModuleLoadError",
    "ModuleValidationError",
    "ModuleNotFoundError",
    "CommandError",
    "CommandNotFoundError",
    "ConfigError",
]
