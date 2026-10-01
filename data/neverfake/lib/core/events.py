import time


class EventBus:
    def __init__(self, store, log_size=500):
        self.store = store
        self._log = []
        self._log_size = log_size

    def emit(self, kind, domain=None, data=None):
        rec = {"ts": time.time(), "kind": kind, "domain": domain, "data": data or {}}
        self._log.append(rec)
        if len(self._log) > self._log_size:
            self._log = self._log[-self._log_size:]
        if self.store is not None:
            try:
                self.store.log_event(kind, domain, data)
            except Exception:
                pass
        return rec

    def history(self, limit=50, kind=None):
        out = self._log
        if kind:
            out = [r for r in out if r["kind"] == kind]
        return out[-limit:]

    def clear(self):
        self._log = []
