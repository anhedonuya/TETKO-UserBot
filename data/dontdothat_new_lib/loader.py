import importlib.util
import sys
import uuid
from pathlib import Path

from .core import DDTManifest, DDTPlugin
from .validation import validate_manifest, validate_plugin
from .utils import sha256_bytes

def _module_name(prefix):
    return "ddt_plugin_%s_%s" % (prefix, uuid.uuid4().hex[:8])

def import_path(path):
    path = Path(path)
    stem = path.stem
    name = _module_name(stem)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("spec failed for %s" % path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def detect_manifest(mod):
    for attr in ("MANIFEST", "MANIFEST_CLASS"):
        obj = getattr(mod, attr, None)
        if obj is None:
            continue
        try:
            from dataclasses import is_dataclass, asdict
            if is_dataclass(obj) and not isinstance(obj, type):
                return asdict(obj)
            if is_dataclass(obj) and isinstance(obj, type):
                return asdict(obj())
        except Exception:
            pass
        if isinstance(obj, dict):
            return dict(obj)
        if hasattr(obj, "__dict__") and hasattr(obj, "name"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    plugin_cls = getattr(mod, "Plugin", None)
    if plugin_cls is not None and hasattr(plugin_cls, "manifest"):
        m = plugin_cls.manifest
        try:
            from dataclasses import is_dataclass, asdict
            if is_dataclass(m) and not isinstance(m, type):
                return asdict(m)
            if is_dataclass(m) and isinstance(m, type):
                return asdict(m())
        except Exception:
            pass
        if isinstance(m, dict):
            return dict(m)
    plain = getattr(mod, "PLUGIN", None)
    if isinstance(plain, dict):
        return dict(plain)
    flat = {}
    for k in ("name", "version", "author", "description", "access", "tags", "hooks", "min_core", "api", "priority", "events", "cfg_defaults"):
        if hasattr(mod, k):
            flat[k] = getattr(mod, k)
    if flat.get("name"):
        return flat
    for attr in dir(mod):
        if attr.startswith("_"):
            continue
        obj = getattr(mod, attr)
        if isinstance(obj, type) and hasattr(obj, "name") and hasattr(obj, "version"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_") and not callable(v)}
    return None

def load_plugin(path, current_core="0.0.0"):
    mod = import_path(path)
    manifest = detect_manifest(mod)
    if manifest is None:
        return None, None, "manifest not found"
    errs = validate_plugin(mod, manifest, current_core=current_core)
    if errs:
        return None, None, "validation: " + "; ".join(errs)
    name = (manifest.get("name") or Path(path).stem).lower().replace(" ", "_")
    if "Plugin" in dir(mod):
        cls = getattr(mod, "Plugin")
        try:
            instance = cls()
        except Exception as e:
            return None, None, "instantiate: %s" % e
        return name, instance, manifest
    return name, mod, manifest
