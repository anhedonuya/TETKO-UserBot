import os

def env_key(section, key):
    return 'DDT_%s_%s' % (section.upper(), key.upper())

def env_value(section, key):
    ek = env_key(section, key)
    if ek in os.environ:
        return os.environ[ek]
    return None

def env_all(defaults):
    out = {}
    for section, keys in defaults.items():
        if not isinstance(keys, dict):
            continue
        for k in keys:
            v = env_value(section, k)
            if v is not None:
                out['%s.%s' % (section, k)] = v
    return out
