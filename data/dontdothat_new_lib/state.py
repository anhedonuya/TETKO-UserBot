import json
import threading
import time
from pathlib import Path

class StateStore:
    def __init__(self, base_dir="data/dontdothat_plugins_state"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache = {}

    def _path(self, name):
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        return self.base_dir / (safe + ".json")

    def get(self, name):
        with self._lock:
            if name in self._cache:
                return self._cache[name]
            p = self._path(name)
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if not isinstance(data, dict):
                        data = {}
                except Exception:
                    data = {}
            else:
                data = {}
            self._cache[name] = data
            return data

    def save(self, name):
        with self._lock:
            data = self._cache.get(name)
            if data is None:
                return
            try:
                self._path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

    def save_all(self):
        for name in list(self._cache.keys()):
            self.save(name)

    def clear(self, name):
        with self._lock:
            self._cache[name] = {}
            try:
                self._path(name).unlink()
            except Exception:
                pass
