"""TTLCache — MCUB-совместимый кэш."""
import time


class TTLCache:
    def __init__(self, max_size=500, ttl=600):
        self._d = {}
        self._max = max_size
        self._ttl = ttl

    def set(self, key, value, ttl=None):
        if len(self._d) >= self._max:
            self._d.clear()
        self._d[key] = (value, time.time() + (ttl or self._ttl))

    def get(self, key, default=None):
        e = self._d.get(key)
        if not e:
            return default
        v, exp = e
        if time.time() > exp:
            self._d.pop(key, None)
            return default
        return v

    def pop(self, key, default=None):
        e = self._d.pop(key, None)
        return e[0] if e else default

    def delete(self, key):
        self._d.pop(key, None)

    def clear(self):
        self._d.clear()


_DictCache = TTLCache
