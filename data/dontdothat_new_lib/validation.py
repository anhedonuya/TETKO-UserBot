from .core import DDTManifest
from .utils import is_valid_name, check_version_range

ALLOWED_ACCESS = {"module", "kernel", "cfg", "fs", "db", "net"}
ALLOWED_CHANNELS = {"stable", "beta", "dev"}
ALLOWED_STABILITY = {"stable", "experimental", "deprecated"}

def validate_manifest(d, current_api="1.5.0", current_core="0.0.0"):
    errors = []
    if not isinstance(d, dict):
        return ["manifest must be dict"]
    name = d.get("name") or ""
    if not is_valid_name(name):
        errors.append("invalid name")
    version = str(d.get("version") or "")
    if not version or version.count(".") < 1:
        errors.append("invalid version")
    api = str(d.get("api") or "1.5.0")
    if api != current_api:
        errors.append("api mismatch: %s != %s" % (api, current_api))
    mc = str(d.get("min_core") or "")
    if mc and not check_version_range(current_core, mc):
        errors.append("min_core not satisfied: %s" % mc)
    access = d.get("access") or []
    if not isinstance(access, list):
        errors.append("access must be list")
    else:
        for a in access:
            if a not in ALLOWED_ACCESS:
                errors.append("unknown access: %s" % a)
    priority = d.get("priority") or {}
    if not isinstance(priority, dict):
        errors.append("priority must be dict")
    else:
        for k, v in priority.items():
            if not isinstance(v, int):
                errors.append("priority[%s] must be int" % k)
    for k in ("requires", "optional", "conflicts", "tags", "categories"):
        v = d.get(k) or []
        if not isinstance(v, list):
            errors.append("%s must be list" % k)
    cfg = d.get("cfg_defaults") or {}
    if not isinstance(cfg, dict):
        errors.append("cfg_defaults must be dict")
    events = d.get("events") or []
    if not isinstance(events, list):
        errors.append("events must be list")
    ch = d.get("channel") or "stable"
    if ch not in ALLOWED_CHANNELS:
        errors.append("unknown channel: %s" % ch)
    st = d.get("stability") or "stable"
    if st not in ALLOWED_STABILITY:
        errors.append("unknown stability: %s" % st)
    return errors

def validate_plugin(module_obj, manifest_dict, current_core="0.0.0"):
    errors = validate_manifest(manifest_dict, current_core=current_core)
    if errors:
        return errors
    if not hasattr(module_obj, "Plugin") and not hasattr(module_obj, "PLUGIN"):
        errors.append("no Plugin class or PLUGIN dict")
    hooks = manifest_dict.get("hooks") or []
    plugin_cls = getattr(module_obj, "Plugin", None)
    if plugin_cls is not None:
        for h in hooks:
            if not hasattr(plugin_cls, h):
                errors.append("hook missing in class: %s" % h)
    return errors
