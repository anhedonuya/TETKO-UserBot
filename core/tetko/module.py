"""Module — базовый класс TETKO-модуля."""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.tetko.config import ModuleConfig


class Module:
    """Базовый класс модуля TETKO."""

    name: str = "Unnamed"
    version: str = "0.0.0"
    author: str = "unknown"
    description: dict[str, str] = {}
    config: dict[str, Any] = {}

    def __init__(self, kernel: Optional[Any] = None):
        self.kernel = kernel
        self._config = ModuleConfig(self.name, self.config)
        self._logger = logging.getLogger(f"TETKO.module.{self.name}")
        self._loaded = False

    @property
    def cfg(self) -> ModuleConfig:
        return self._config

    @property
    def log(self) -> logging.Logger:
        return self._logger

    @property
    def client(self):
        if self.kernel and hasattr(self.kernel, "client"):
            return self.kernel.client
        return None

    def _get_lang(self) -> str:
        try:
            cfg = getattr(self.kernel, "config", None) or {}
            return cfg.get("language") or "ru"
        except Exception:
            return "ru"

    @property
    def strings(self) -> dict:
        try:
            from core.langpacks import get_module_strings
            return get_module_strings(self.name.lower(), self._get_lang()) or {}
        except Exception:
            return {}

    def _t(self, key: str, **kwargs) -> str:
        data = self.strings
        value = data.get(key, key)
        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return value
        return value

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    def get_description(self, lang: str = "ru") -> str:
        if isinstance(self.description, dict):
            return (
                self.description.get(lang)
                or self.description.get("en")
                or self.description.get("ru")
                or ""
            )
        return str(self.description)

    def __repr__(self) -> str:
        return f"<Module {self.name} v{self.version} by {self.author}>"
