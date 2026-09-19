"""Заглушка. При загрузке mcub-модуля compat подменяет sys.modules."""
from __future__ import annotations


class ModuleBase:
    name = "Unnamed"
    version = "0.0.0"
    author = "unknown"
    description = {}
    dependencies = []
    banner_url = None
    strings = {}
    config = None

    def __init__(self, *args, **kwargs):
        pass

    async def on_load(self): pass
    async def on_unload(self): pass


def _stub_decorator(*args, **kwargs):
    def deco(fn):
        return fn
    if args and callable(args[0]) and not kwargs:
        return args[0]
    return deco


command = _stub_decorator
callback = _stub_decorator
watcher = _stub_decorator
loop = _stub_decorator
bot_command = _stub_decorator
inline = _stub_decorator
