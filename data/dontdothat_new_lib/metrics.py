class Metrics:
    def __init__(self):
        self._data = {}

    def inc(self, plugin, hook, key="calls", amount=1):
        p = self._data.setdefault(plugin, {}).setdefault(hook, {})
        p[key] = p.get(key, 0) + amount

    def add_time(self, plugin, hook, seconds):
        p = self._data.setdefault(plugin, {}).setdefault(hook, {})
        p["total_time"] = p.get("total_time", 0.0) + seconds

    def get(self, plugin=None):
        if plugin:
            return self._data.get(plugin, {})
        return dict(self._data)

    def clear(self):
        self._data.clear()
