class LegacyDispatcher:
    def __init__(self, registry):
        self.registry = registry

    def dispatch(self, module, hook_name, ctx):
        result = None
        for name, info in self.registry.find_by_hook(hook_name):
            mod_obj = info.get("module")
            method = getattr(mod_obj, hook_name, None) if mod_obj else None
            if method is None or not callable(method):
                continue
            try:
                r = method(ctx)
                if r is not None:
                    return r
            except Exception:
                continue
        return result
