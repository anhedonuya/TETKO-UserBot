def validate_value(value, default):
    if default is None:
        return True, None
    if isinstance(default, bool):
        return isinstance(value, bool), 'expected bool'
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool), 'expected int'
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool), 'expected number'
    if isinstance(default, str):
        return isinstance(value, str), 'expected str'
    if isinstance(default, list):
        return isinstance(value, list), 'expected list'
    if isinstance(default, dict):
        return isinstance(value, dict), 'expected dict'
    return True, None

def validate_cfg(flat, defaults):
    errors = []
    for section, vals in defaults.items():
        if not isinstance(vals, dict):
            continue
        for k, default in vals.items():
            key = '%s.%s' % (section, k)
            if key not in flat:
                continue
            ok, err = validate_value(flat[key], default)
            if not ok:
                errors.append('%s: %s' % (key, err))
    return errors
