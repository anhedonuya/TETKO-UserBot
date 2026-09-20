"""Реэкспорт ModuleConfig/ConfigValue из mcub_compat.

MCUB-модули делают `from core.lib.loader.module_config import ConfigValue, ...`
и ожидают РАБОЧИЕ классы, а не заглушки.
"""
from core.tetko.mcub_compat.module_config import (
    ConfigValue,
    ModuleConfig,
    Group,
    Row,
    Divider,
    Boolean,
    Integer,
    String,
    Validator,
    Emoji,
    MultiChoice,
    Union,
    Hidden,
    NoneType,
)

__all__ = [
    "ConfigValue", "ModuleConfig", "Group", "Row", "Divider",
    "Boolean", "Integer", "String", "Validator", "Emoji",
    "MultiChoice", "Union", "Hidden", "NoneType",
]
