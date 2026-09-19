"""MCUB compatibility layer for TETKO.

Позволяет загружать модули MCUB-стиля (ModuleBase, core.lib.*, utils.*,
core_inline.*, core.langpacks) поверх TETKO-ядра.

Публичный API:
    is_mcub_module(code) -> bool
    load_mcub_module(kernel, path, module_name) -> Module
    unload_mcub_module(kernel, module_name) -> bool
"""
from __future__ import annotations

__compat__ = "0.0.9.0"
__mcub_compat_version__ = "0.1.0"

from .detector import is_mcub_module
from .loader import load_mcub_module, unload_mcub_module

__all__ = [
    "is_mcub_module",
    "load_mcub_module",
    "unload_mcub_module",
]
