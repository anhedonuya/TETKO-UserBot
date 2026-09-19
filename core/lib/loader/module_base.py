"""MCUB-совместимый module_base. Декораторы вешают метаданные на функции."""
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


def command(pattern, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_commands", []))
        meta.append((pattern, kwargs))
        fn._mcub_commands = meta
        return fn
    return deco


def watcher(*args, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_watchers", []))
        meta.append(kwargs)
        fn._mcub_watchers = meta
        return fn
    if args and callable(args[0]) and not kwargs:
        return deco(args[0])
    return deco


def callback(*args, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_callbacks", []))
        meta.append(kwargs)
        fn._mcub_callbacks = meta
        return fn
    if args and callable(args[0]) and not kwargs:
        return deco(args[0])
    return deco


def loop(*args, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_loops", []))
        meta.append(kwargs)
        fn._mcub_loops = meta
        return fn
    if args and callable(args[0]) and not kwargs:
        return deco(args[0])
    return deco


def bot_command(pattern, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_bot_commands", []))
        meta.append((pattern, kwargs))
        fn._mcub_bot_commands = meta
        return fn
    return deco


def inline(pattern, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_inline", []))
        meta.append((pattern, kwargs))
        fn._mcub_inline = meta
        return fn
    return deco
