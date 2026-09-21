"""Заглушка wrap_event_for_module."""
def wrap_event_for_module(event, *a, **kw):
    return event

class EventProxy:
    def __init__(self, event, *a, **kw): self._event = event
    def __getattr__(self, item): return getattr(self._event, item)
