import time

class V2Registry:
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
            if info.get("enabled") is False or info.get("frozen"):
                continue
            manifest = info.get("manifest") or {}
            hooks = manifest.get("hooks") or []
            if hook_name in hooks:
                priority = (manifest.get("priority") or {}).get(hook_name, 50)
                out.append((priority, name, info))
        out.sort(key=lambda x: (-x[0], x[1]))
        return out

    def find_by_event(self, event_type):
        out = []
        for name, info in self._plugins.items():
            if info.get("enabled") is False:
                continue
            manifest = info.get("manifest") or {}
            events = manifest.get("events") or []
            if event_type in events:
                out.append((name, info))
        return out

    def resolve_dependencies(self):
        loaded = set(self._plugins.keys())
        errors = []
        for name, info in self._plugins.items():
            manifest = info.get("manifest") or {}
            requires = manifest.get("requires") or []
            conflicts = manifest.get("conflicts") or []
            for r in requires:
                base = r.split(">")[0].split("<")[0].split("=")[0].strip()
                if base and base not in loaded:
                    errors.append("plugin %s requires %s (not loaded)" % (name, base))
            for c in conflicts:
                if c in loaded:
                    errors.append("plugin %s conflicts with %s" % (name, c))
        return errors
