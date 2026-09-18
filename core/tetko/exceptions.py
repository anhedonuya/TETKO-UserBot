"""Исключения TETKO."""


class TetkoError(Exception):
    pass


class ModuleError(TetkoError):
    pass


class ModuleLoadError(ModuleError):
    pass


class ModuleValidationError(ModuleError):
    pass


class ModuleRegistrationError(ModuleError):
    pass


class ModuleNotFoundError(ModuleError):
    pass


class CommandError(TetkoError):
    pass


class CommandNotFoundError(CommandError):
    pass


class CommandRegistrationError(CommandError):
    pass


class ConfigError(TetkoError):
    pass
