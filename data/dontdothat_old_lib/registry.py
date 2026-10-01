class LegacyRegistry:
    def __init__(self):
        self._plugins = {}

    def register(self, name, info):
        self._plugins[name] = info
        return info

    def unregister(self, name):
        return self._plugins.pop(name, None)

    def get(self, name):
        return self._plugins.get(name)

    def list(self):
        return list(self._plugins.values())

    def names(self):
        return list(self._plugins.keys())

    def find_by_hook(self, hook_name):
        out = []
        for name, info in self._plugins.items():
            if info.get("enabled") is False:
                continue
            hooks = (info.get("manifest") or {}).get("hooks") or []
            if hook_name in hooks:
                out.append((name, info))
        out.sort(key=lambda x: x[0])
        return out
