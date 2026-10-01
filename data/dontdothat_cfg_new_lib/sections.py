def flatten(cfg):
    out = {}
    for section, values in cfg.items():
        if isinstance(values, dict):
            for k, v in values.items():
                out['%s.%s' % (section, k)] = v
        else:
            out[section] = values
    return out

def unflatten(flat):
    out = {}
    for key, value in flat.items():
        if '.' in key:
            section, k = key.split('.', 1)
            out.setdefault(section, {})[k] = value
        else:
            out.setdefault('advanced', {})[key] = value
    return out

def section_of(key, defaults):
    if '.' in key:
        return key.split('.', 1)[0]
    for section, values in defaults.items():
        if isinstance(values, dict) and key in values:
            return section
    return 'advanced'

def get_path(cfg, key):
    if '.' in key:
        section, k = key.split('.', 1)
        data = cfg.get(section) or {}
        if isinstance(data, dict):
            return data.get(k)
        return None
    return cfg.get(key)

def set_path(cfg, key, value):
    if '.' in key:
        section, k = key.split('.', 1)
        data = cfg.get(section) or {}
        if not isinstance(data, dict):
            data = {}
        data[k] = value
        cfg[section] = data
    else:
        cfg[key] = value
    return cfg
