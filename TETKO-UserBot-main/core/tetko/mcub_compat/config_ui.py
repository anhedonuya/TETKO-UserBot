"""Small, functional MCUB configuration UI bridge.

TETKO does not require a separate config UI service.  This module exposes the
schema and persistence hooks expected by MCUB code and leaves presentation to
the caller.
"""
from __future__ import annotations
import logging
log=logging.getLogger("TETKO.mcub_compat.config_ui")

def install(kernel):
    if getattr(kernel, "_mcub_config_ui_installed", False):
        return True

    def get_config_schema(module_name):
        mod = kernel.registry.get_module(module_name)
        cfg = getattr(mod, "config", None) if mod else None
        if cfg is None:
            cfg = getattr(mod, "cfg", None) if mod else None
        if cfg is None:
            return []
        return getattr(cfg, "schema", []) or []

    async def set_config_value(module_name, key, value):
        mod = kernel.registry.get_module(module_name)
        cfg = getattr(mod, "config", None) if mod else None
        if cfg is None:
            cfg = getattr(mod, "cfg", None) if mod else None
        if cfg is None:
            return False
        try:
            cfg[key] = value
            if hasattr(mod, "save_config"):
                await mod.save_config()
            return True
        except Exception as exc:
            log.warning("set config %s.%s: %s", module_name, key, exc)
            return False

    kernel.mcub_config_schema = get_config_schema
    kernel.mcub_set_config_value = set_config_value
    kernel._mcub_config_ui_installed = True
    return True

__all__=["install"]
