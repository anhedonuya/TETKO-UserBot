class PluginConfig:
    def __init__(self, module, plugin_name, defaults=None, schema=None):
        self._module = module
        self._name = plugin_name
        self._defaults = dict(defaults or {})
        self._schema = dict(schema or {})

    def _store(self):
        plugins = self._module.cfg.get("plugins", {}) or {}
        store = plugins.get("per_plugin", {}) or {}
        return plugins, store

    def get(self, key, default=None):
        _, store = self._store()
        per = store.get(self._name, {}) or {}
        if key in per:
            return per[key]
        if key in self._defaults:
            return self._defaults[key]
        return default

    def set(self, key, value):
        schema = self._schema.get(key)
        if schema:
            t = schema.get("type")
            if t == "int" and not isinstance(value, int):
                raise ValueError("expected int for %s" % key)
            if t == "float" and not isinstance(value, (int, float)):
                raise ValueError("expected float for %s" % key)
            if t == "str" and not isinstance(value, str):
                raise ValueError("expected str for %s" % key)
            if t == "bool" and not isinstance(value, bool):
                raise ValueError("expected bool for %s" % key)
            mn = schema.get("min")
            if mn is not None and value < mn:
                raise ValueError("%s < min %s" % (key, mn))
            mx = schema.get("max")
            if mx is not None and value > mx:
                raise ValueError("%s > max %s" % (key, mx))
            ch = schema.get("choices")
            if ch and value not in ch:
                raise ValueError("%s not in choices" % key)
        plugins, store = self._store()
        per = store.get(self._name, {}) or {}
        per[key] = value
        store[self._name] = per
        plugins["per_plugin"] = store
        self._module.cfg.set("plugins", plugins)

    def all(self):
        _, store = self._store()
        per = dict(store.get(self._name, {}) or {})
        for k, v in self._defaults.items():
            per.setdefault(k, v)
        return per

    def reset(self):
        plugins, store = self._store()
        store.pop(self._name, None)
        plugins["per_plugin"] = store
        self._module.cfg.set("plugins", plugins)
