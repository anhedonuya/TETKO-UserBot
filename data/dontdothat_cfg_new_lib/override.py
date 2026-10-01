import time

class OverrideManager:
    def __init__(self):
        self._data = {}

    def set(self, key, value, ttl=3600):
        self._data[key] = {'value': value, 'expires_at': time.time() + ttl}

    def get(self, key):
        e = self._data.get(key)
        if not e:
            return None
        if e['expires_at'] < time.time():
            self._data.pop(key, None)
            return None
        return e['value']

    def active(self):
        now = time.time()
        expired = [k for k, v in self._data.items() if v['expires_at'] < now]
        for k in expired:
            self._data.pop(k, None)
        return dict(self._data)

    def clear(self):
        self._data.clear()
