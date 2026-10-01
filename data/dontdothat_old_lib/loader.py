import importlib.util
import sys
import uuid
from pathlib import Path

def detect_manifest_legacy(mod):
    plain = getattr(mod, "PLUGIN", None)
    if isinstance(plain, dict):
        return plain
    flat = {}
    for k in ("name", "version", "author", "description", "access", "tags", "hooks", "min_core"):
        if hasattr(mod, k):
            flat[k] = getattr(mod, k)
    if flat.get("name"):
        return flat
    return None

def import_path(path):
    path = Path(path)
    name = "ddt_legacy_%s_%s" % (path.stem, uuid.uuid4().hex[:8])
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("spec failed: %s" % path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def load_from_path(path):
    mod = import_path(path)
    manifest = detect_manifest_legacy(mod)
    if manifest is None:
        return None, None, "manifest not found"
    name = (manifest.get("name") or Path(path).stem).lower().replace(" ", "_")
    return name, mod, manifest
