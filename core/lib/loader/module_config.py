"""Реэкспорт ModuleConfig/ConfigValue из mcub_compat.

MCUB-модули делают `from core.lib.loader.module_config import ConfigValue, ...`
и ожидают РАБОЧИЕ классы, а не заглушки.
"""
from core.tetko.mcub_compat.module_config import (
    # Core
    ConfigValue,
    ModuleConfig,
    ValidationError,
    # Validators
    Validator,
    Boolean,
    Integer,
    Float,
    String,
    Choice,
    List,
    DictType,
    Secret,
    Placeholders,
    RegExp,
    Link,
    TelegramID,
    EntityLike,
    Emoji,
    MultiChoice,
    Union,
    Hidden,
    NoneType,
    # UI
    Group,
    Row,
    Divider,
    Url,
    Callback,
    Status,
    Notice,
    Answer,
    Buttons,
)

__all__ = [
    "ConfigValue", "ModuleConfig", "ValidationError",
    "Validator", "Boolean", "Integer", "Float", "String", "Choice",
    "List", "DictType", "Secret", "Placeholders", "RegExp", "Link",
    "TelegramID", "EntityLike", "Emoji", "MultiChoice", "Union",
    "Hidden", "NoneType",
    "Group", "Row", "Divider", "Url", "Callback", "Status",
    "Notice", "Answer", "Buttons",
]
