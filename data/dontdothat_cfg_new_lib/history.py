import time

class History:
    def __init__(self, per_key_limit=100):
        self._data = {}
        self._limit = per_key_limit

    def push(self, key, old, new, actor='?'):
        h = self._data.setdefault(key, [])
        h.append({'ts': time.time(), 'old': old, 'new': new, 'actor': str(actor)})
        if len(h) > self._limit:
            self._data[key] = h[-self._limit:]

    def get(self, key, limit=20):
        return self._data.get(key, [])[-limit:]

    def all(self):
        return dict(self._data)

    def clear(self):
        self._data.clear()
