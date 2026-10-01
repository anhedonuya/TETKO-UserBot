import json
from pathlib import Path

class ProfileManager:
    def __init__(self, base_dir='data/dontdothat_cfg_profiles'):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list(self):
        builtin = ['prod', 'dev', 'minimal', 'test']
        custom = [p.stem for p in self.base_dir.glob('*.json')]
        return {'builtin': builtin, 'custom': custom}

    def get_builtin(self, name):
        if name == 'prod':
            return {'ui': {'log_searches': False}, 'search': {'priority_first': True}}
        if name == 'dev':
            return {'ui': {'log_searches': True}, 'plugins': {'auto_disable_on_error': False}}
        if name == 'minimal':
            return {'search': {'max_parallel': 3, 'priority_first': False}}
        if name == 'test':
            return {'plugins': {'enabled': False}}
        return None

    def save(self, name, data):
        p = self.base_dir / ('%s.json' % name)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def load(self, name):
        builtin = self.get_builtin(name)
        if builtin:
            return builtin
        p = self.base_dir / ('%s.json' % name)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            return None

    def delete(self, name):
        p = self.base_dir / ('%s.json' % name)
        if p.exists():
            p.unlink()
            return True
        return False
