import json

def export_cfg(flat, fmt='json'):
    if fmt == 'json':
        return json.dumps(flat, ensure_ascii=False, indent=2).encode('utf-8')
    if fmt == 'env':
        lines = []
        for k, v in flat.items():
            lines.append('%s=%s' % ('DDT_' + k.replace('.', '_').upper(), json.dumps(v)))
        return '\n'.join(lines).encode('utf-8')
    if fmt == 'toml':
        lines = []
        for k, v in flat.items():
            lines.append('"%s" = %s' % (k, json.dumps(v)))
        return '\n'.join(lines).encode('utf-8')
    return json.dumps(flat, ensure_ascii=False).encode('utf-8')

def import_cfg(data, merge=True, current=None):
    try:
        parsed = json.loads(data.decode('utf-8'))
    except Exception as e:
        return {}, str(e)
    if not isinstance(parsed, dict):
        return {}, 'not a dict'
    if merge and current:
        out = dict(current)
        for k, v in parsed.items():
            if out.get(k) is None:
                out[k] = v
        return out, None
    return parsed, None
