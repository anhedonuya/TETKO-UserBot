import time

class PluginCache:
    def __init__(self, ttl=300, max_size=1000):
        self.ttl = ttl
        self.max_size = max_size
        self._data = {}

    def get(self, key):
        e = self._data.get(key)
        if not e:
            return None
        if time.time() - e["ts"] > e["ttl"]:
            del self._data[key]
            return None
        return e["value"]

    def set(self, key, value, ttl=None):
        self._data[key] = {"value": value, "ts": time.time(), "ttl": ttl or self.ttl}
        if len(self._data) > self.max_size:
            items = sorted(self._data.items(), key=lambda kv: kv[1]["ts"])
            for k, _ in items[: len(items) // 2]:
                self._data.pop(k, None)

    def delete(self, key):
        self._data.pop(key, None)

    def clear(self):
        self._data.clear()
