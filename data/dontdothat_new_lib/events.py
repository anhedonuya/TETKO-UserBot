import time

class EventBus:
    def __init__(self, log_size=500):
        self._log = []
        self._log_size = log_size

    def emit(self, event_type, data=None):
        rec = {"ts": time.time(), "type": event_type, "data": data or {}}
        self._log.append(rec)
        if len(self._log) > self._log_size:
            self._log = self._log[-self._log_size:]
        return rec

    def history(self, limit=50, event_type=None):
        out = self._log
        if event_type:
            out = [r for r in out if r["type"] == event_type]
        return out[-limit:]
