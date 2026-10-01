import copy
from .defaults import CFG_DEFAULTS, CFG_SCHEMA, CFG_SECTIONS
from .sections import flatten, unflatten, section_of, get_path, set_path
from .validator import validate_cfg
from .schema import validate_schema
from .history import History
from .override import OverrideManager
from .profiles import ProfileManager
from .export import export_cfg, import_cfg
from .loader import ConfigLoader
from .env import env_all

class ConfigManager:
    def __init__(self, module_name='DontDoThatADM', base_dir='data/tetko_config'):
        self.module_name = module_name
        self.defaults = CFG_DEFAULTS
        self.schema = CFG_SCHEMA
        self.sections = CFG_SECTIONS
        self.loader = ConfigLoader(module_name, base_dir)
        self.history = History()
        self.overrides = OverrideManager()
        self.profiles = ProfileManager()
        self._data = {}
        self._load()

    def _load(self):
        disk = self.loader.load()
        data = {}
        for s, v in self.defaults.items():
            data[s] = copy.deepcopy(v) if isinstance(v, dict) else v
        for s, v in disk.items():
            if isinstance(v, dict) and isinstance(data.get(s), dict):
                data[s].update(v)
            else:
                data[s] = v
        env = env_all(self.defaults)
        for k, v in env.items():
            if v in ('true', 'True', '1'):
                v = True
            elif v in ('false', 'False', '0'):
                v = False
            else:
                try:
                    v = int(v)
                except Exception:
                    try:
                        v = float(v)
                    except Exception:
                        pass
            set_path(data, k, v)
        self._data = data

    def _save(self):
        self.loader.save_atomic(self._data)

    def all(self):
        return copy.deepcopy(self._data)

    def section(self, name):
        v = self._data.get(name)
        if isinstance(v, dict):
            return dict(v)
        return {}

    def get(self, key, default=None):
        v = get_path(self._data, key)
        if v is None and default is not None:
            return default
        return v

    def set(self, key, value, actor='?'):
        rule = self.schema.get(key)
        if rule:
            ok, err = validate_schema(key, value, self.schema)
            if not ok:
                raise ValueError('%s: %s' % (key, err))
        old = get_path(self._data, key)
        set_path(self._data, key, value)
        self.history.push(key, old, value, actor)
        self._save()
        return True

    def reset(self, key, actor='reset'):
        section = section_of(key, self.defaults)
        short = key.split('.', 1)[-1] if '.' in key else key
        if short not in self.defaults.get(section, {}):
            return False
        default = copy.deepcopy(self.defaults[section][short])
        old = get_path(self._data, key)
        set_path(self._data, key, default)
        self.history.push(key, old, default, actor)
        self._save()
        return True

    def validate(self):
        flat = flatten(self._data)
        return validate_cfg(flat, self.defaults)

    def flat(self):
        return flatten(self._data)

    def schema_for(self, key):
        section = section_of(key, self.defaults)
        short = key.split('.', 1)[-1] if '.' in key else key
        defaults = self.defaults.get(section, {})
        base = {'type': 'unknown', 'default': None, 'section': section}
        if short in defaults:
            base['type'] = type(defaults[short]).__name__
            base['default'] = defaults[short]
        rule = self.schema.get(key)
        if rule:
            base.update(rule)
        return base

    def use_profile(self, name):
        p = self.profiles.load(name)
        if not p:
            return False
        for s, v in p.items():
            if isinstance(v, dict):
                cur = self._data.get(s) or {}
                if not isinstance(cur, dict):
                    cur = {}
                cur.update(v)
                self._data[s] = cur
            else:
                self._data[s] = v
        self._save()
        return True

    def export(self, fmt='json'):
        return export_cfg(self.flat(), fmt)

    def import_(self, data, merge=True):
        cur = self.flat()
        new, err = import_cfg(data, merge=merge, current=cur)
        if err:
            return 0, err
        cnt = 0
        for k, v in new.items():
            set_path(self._data, k, v)
            cnt += 1
        self._save()
        return cnt, None
