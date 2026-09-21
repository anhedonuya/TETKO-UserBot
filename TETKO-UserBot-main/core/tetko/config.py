"""ModuleConfig — JSON-конфиг модуля."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("TETKO.tetko.config")


class ModuleConfig:
    """Конфиг одного модуля (JSON)."""

    def __init__(self, module_name: str, defaults: dict[str, Any] | None = None,
                 base_dir: str | Path = "data/tetko_config"):
        self.module_name = module_name
        self.defaults = dict(defaults or {})
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / f"{module_name}.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                log.error(f"[{self.module_name}] Ошибка чтения: {e}")
                self._data = dict(self.defaults)
        else:
            self._data = dict(self.defaults)
            self._save()

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log.error(f"[{self.module_name}] Ошибка сохранения: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            return self._data[key]
        if key in self.defaults:
            return self.defaults[key]
        return default

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            self._save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"<ModuleConfig {self.module_name} keys={list(self._data.keys())}>"
