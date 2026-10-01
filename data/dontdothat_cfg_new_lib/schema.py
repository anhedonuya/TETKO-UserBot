def validate_schema(key, value, schema):
    rule = schema.get(key)
    if not rule:
        return True, None
    t = rule.get('type')
    if t == 'int' and (not isinstance(value, int) or isinstance(value, bool)):
        return False, 'expected int'
    if t == 'float' and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return False, 'expected float'
    if t == 'str' and not isinstance(value, str):
        return False, 'expected str'
    if t == 'bool' and not isinstance(value, bool):
        return False, 'expected bool'
    if t == 'choice' and value not in (rule.get('choices') or []):
        return False, 'not in choices'
    mn = rule.get('min')
    if mn is not None and isinstance(value, (int, float)) and value < mn:
        return False, 'below min %s' % mn
    mx = rule.get('max')
    if mx is not None and isinstance(value, (int, float)) and value > mx:
        return False, 'above max %s' % mx
    return True, None
