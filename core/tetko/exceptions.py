"""Исключения TETKO."""


class TetkoError(Exception):
    """Базовая ошибка TETKO."""
    pass


class ModuleError(TetkoError):
    """Ошибка модуля."""
    pass


class ModuleLoadError(ModuleError):
    """Ошибка загрузки модуля."""
    pass


class ModuleValidationError(ModuleError):
    """Модуль не прошёл валидацию."""
    pass


class ModuleRegistrationError(ModuleError):
    """Ошибка регистрации модуля."""
    pass


class ModuleNotFoundError(ModuleError):
    """Модуль не найден."""
    pass


class CommandError(TetkoError):
    """Ошибка команды."""
    pass


class CommandNotFoundError(CommandError):
    """Команда не найдена."""
    pass


class CommandRegistrationError(CommandError):
    """Ошибка регистрации команды."""
    pass


class ConfigError(TetkoError):
    """Ошибка конфига."""
    pass
