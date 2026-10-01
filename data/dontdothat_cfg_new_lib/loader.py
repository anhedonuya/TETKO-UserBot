import json
from pathlib import Path

class ConfigLoader:
    def __init__(self, module_name, base_dir='data/tetko_config'):
        self.module_name = module_name
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / ('%s.json' % module_name)

    def load(self):
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def save(self, data):
        try:
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return True
        except Exception:
            return False

    def save_atomic(self, data):
        import tempfile, os
        try:
            fd, tmp = tempfile.mkstemp(prefix='cfg_', suffix='.json', dir=str(self.base_dir))
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            return True
        except Exception:
            return self.save(data)
