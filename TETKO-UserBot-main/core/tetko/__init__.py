"""TETKO — модульная система TETKO UserBot."""

# Версия API tetko-compat (стиль модулей)
__compat__ = "0.0.9.0"
__compat_style__ = "tetko-compat"
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

from core.tetko.db import db_get, db_set, db_del, db_list, db_clear

from core.tetko.context import Context

from core.tetko.inline import Inline

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
    "db_get",
    "db_set",
    "db_del",
    "db_list",
    "db_clear",
    "Context",
    "Inline",
]
