import time

class HealthMonitor:
    def __init__(self):
        self._status = {}

    def update(self, name, status, message=""):
        self._status[name] = {"status": status, "message": message, "checked_at": time.time()}

    def get(self, name):
        return self._status.get(name)

    def all(self):
        return dict(self._status)

    def failed(self):
        return [n for n, v in self._status.items() if v.get("status") == "failed"]
