def register_hooks_legacy(module, name, mod_obj, manifest):
    hooks = manifest.get("hooks") or []
    registered = []
    for h in hooks:
        fn = getattr(mod_obj, h, None)
        if callable(fn):
            registered.append(h)
    return registered

def run_hook_legacy(module, hook_name, ctx):
    result = None
    for name, info in list(module._plugins.items()):
        if not info.get("legacy"):
            continue
        if info.get("enabled") is False:
            continue
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
