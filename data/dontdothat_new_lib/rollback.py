import shutil
import time
from pathlib import Path

class RollbackManager:
    def __init__(self, base_dir="data/dontdothat_plugins_versions", max_versions=3):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_versions = max_versions

    def store_version(self, name, version, path):
        folder = self.base_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / ("%s.py" % version)
        try:
            shutil.copyfile(path, target)
        except Exception:
            return False
        versions = sorted(folder.glob("*.py"), key=lambda p: p.stat().st_mtime)
        while len(versions) > self.max_versions:
            old = versions.pop(0)
            try:
                old.unlink()
            except Exception:
                pass
        return True

    def list_versions(self, name):
        folder = self.base_dir / name
        if not folder.exists():
            return []
        return sorted([p.stem for p in folder.glob("*.py")])

    def get_version(self, name, version):
        p = self.base_dir / name / ("%s.py" % version)
        if p.exists():
            return p
        return None
