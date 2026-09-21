"""Простое JSON-хранилище для модулей tetko-compat.

Данные раскладываются по namespace (отдельный JSON-файл на каждый).
Путь по умолчанию: data/tetko_db/{namespace}.json
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("TETKO.tetko.db")

DEFAULT_DB_DIR = Path("data/tetko_db")


class Storage:
    """JSON-хранилище: namespace → {key: value}."""

    def __init__(self, base_dir: str | Path = DEFAULT_DB_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, Any]] = {}

    def _path(self, namespace: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in namespace)
        return self.base_dir / f"{safe}.json"

    def _load(self, namespace: str) -> dict[str, Any]:
        if namespace in self._cache:
            return self._cache[namespace]
        path = self._path(namespace)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except Exception as e:
                log.error(f"[{namespace}] ошибка чтения {path}: {e}")
                data = {}
        else:
            data = {}
        self._cache[namespace] = data
        return data

    def _save(self, namespace: str) -> None:
        path = self._path(namespace)
        data = self._cache.get(namespace, {})
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"[{namespace}] ошибка сохранения {path}: {e}")

    # ─── Публичный API ───
    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        return self._load(namespace).get(key, default)

    def set(self, namespace: str, key: str, value: Any) -> None:
        self._load(namespace)[key] = value
        self._save(namespace)

    def delete(self, namespace: str, key: str) -> bool:
        data = self._load(namespace)
        if key in data:
            del data[key]
            self._save(namespace)
            return True
        return False

    def list(self, namespace: str) -> dict[str, Any]:
        return dict(self._load(namespace))

    def clear(self, namespace: str) -> None:
        self._cache[namespace] = {}
        self._save(namespace)


# Глобальный экземпляр для использования из модулей
_storage = Storage()


def db_get(namespace: str, key: str, default: Any = None) -> Any:
    return _storage.get(namespace, key, default)


def db_set(namespace: str, key: str, value: Any) -> None:
    _storage.set(namespace, key, value)


def db_del(namespace: str, key: str) -> bool:
    return _storage.delete(namespace, key)


def db_list(namespace: str) -> dict[str, Any]:
    return _storage.list(namespace)


def db_clear(namespace: str) -> None:
    _storage.clear(namespace)
