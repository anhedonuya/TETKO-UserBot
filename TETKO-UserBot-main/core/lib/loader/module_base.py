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


def event(event_type, *args, bot_client=False, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_events", []))
        meta.append({"event_type": event_type, "args": args,
                     "bot_client": bot_client, "kwargs": kwargs})
        fn._mcub_events = meta
        return fn
    return deco


def inline_temp(func=None, *, ttl=300, allow_user=None, allow_ttl=100,
                article=None, data=None):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_inline_temp", []))
        meta.append({"ttl": ttl, "allow_user": allow_user, "allow_ttl": allow_ttl,
                     "article": article, "data": data})
        fn._mcub_inline_temp = meta
        return fn
    if func is not None:
        return deco(func)
    return deco


def method(func=None):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_methods", []))
        meta.append(True)
        fn._mcub_methods = meta
        return fn
    if func is not None:
        return deco(func)
    return deco


def on_install(func=None):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_on_install", []))
        meta.append(True)
        fn._mcub_on_install = meta
        return fn
    if func is not None:
        return deco(func)
    return deco


def on_uninstall(func=None):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_uninstall", []))
        meta.append(True)
        fn._mcub_uninstall = meta
        return fn
    if func is not None:
        return deco(func)
    return deco


def owner_only(func=None, *, only_admin=False):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_owner", []))
        meta.append({"only_admin": only_admin})
        fn._mcub_owner = meta
        return fn
    if func is not None:
        return deco(func)
    return deco


def permissions(func=None, *, log_level="error", **perms):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_permissions", []))
        meta.append({"log_level": log_level, **perms})
        fn._mcub_permissions = meta
        return fn
    if func is not None:
        return deco(func)
    return deco


def error_handler(func=None, *, log_level="error", reraise=False, message=None):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_error_handler", []))
        meta.append({"log_level": log_level, "reraise": reraise, "message": message})
        fn._mcub_error_handler = meta
        return fn
    if func is not None:
        return deco(func)
    return deco
