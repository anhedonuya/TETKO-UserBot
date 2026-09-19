class TTLCache:
    def __init__(self, max_size=500, ttl=600):
        self._d = {}
    def set(self, k, v, ttl=None): self._d[k] = v
    def get(self, k, default=None): return self._d.get(k, default)
    def delete(self, k): self._d.pop(k, None)
    def clear(self): self._d.clear()
