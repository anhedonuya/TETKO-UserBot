from .core import DDTManifest, DDTPlugin

class ShimmedPlugin(DDTPlugin):
    pass

def shim_from_plugin_dict(module_obj, manifest_dict):
    hooks = manifest_dict.get("hooks") or []
    cls_attrs = {}
    for h in hooks:
        fn = getattr(module_obj, h, None)
        if callable(fn):
            cls_attrs[h] = staticmethod(fn)
    cls = type("Shim_" + str(manifest_dict.get("name", "plugin")), (ShimmedPlugin,), cls_attrs)
    manifest = DDTManifest(
        name=manifest_dict.get("name", ""),
        version=manifest_dict.get("version", "1.0.0"),
        author=manifest_dict.get("author", ""),
        description=manifest_dict.get("description", ""),
        api="1.0.0",
        access=manifest_dict.get("access", []) or [],
        tags=manifest_dict.get("tags", []) or [],
    )
    instance = cls(manifest=manifest)
    instance.__dict__["_original_module"] = module_obj
    return instance
