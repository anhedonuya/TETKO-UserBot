class MiddlewareChain:
    def __init__(self):
        self._chain = []

    def add(self, name, before=None, after=None):
        self._chain.append({"name": name, "before": before, "after": after})

    def remove(self, name):
        self._chain = [m for m in self._chain if m["name"] != name]

    def list(self):
        return list(self._chain)
