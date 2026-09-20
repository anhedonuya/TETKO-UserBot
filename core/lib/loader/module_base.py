"""MCUB-совместимый module_base.

ModuleBase = настоящий MCUBModuleBase (с __init_subclass__,
который собирает _mcub_registry из @command-декораторов).
Декораторы command/watcher/callback/loop/bot_command/inline
оставлены здесь для совместимости импортов MCUB-модулей.
"""
from __future__ import annotations

# Реэкспорт настоящего класса
from core.tetko.mcub_compat.module_base import MCUBModuleBase as ModuleBase


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


def event(event_type, *args, bot_client=False, **kwargs):
    """MCUB-декоратор @event — регистрирует обработчик события."""
    def deco(fn):
        meta = list(getattr(fn, "_mcub_events", []))
        meta.append((event_type, args, kwargs))
        fn._mcub_events = meta
        return fn
    return deco


def inline(pattern, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_inline", []))
        meta.append((pattern, kwargs))
        fn._mcub_inline = meta
        return fn
    return deco


__all__ = ["ModuleBase", "command", "watcher", "callback", "loop", "bot_command", "inline", "event"]
