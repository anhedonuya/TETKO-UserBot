"""Декораторы TETKO-модулей."""
from __future__ import annotations

from typing import Any, Callable, Optional


def command(
    name: Optional[str] = None,
    *,
    aliases: Optional[list[str]] = None,
    doc: Any = "",
    description: Any = None,
    **kwargs: Any,
) -> Callable:
    """@command — регистрация команды.

    Параметры:
        name: имя команды (без префикса). Если не задано — берётся из имени функции.
        aliases: список альтернативных имён.
        doc / description: описание команды (синонимы).
        **kwargs: дополнительные параметры (передаются в Command).
    """
    def decorator(func: Callable) -> Callable:
        cmd_name = name or func.__name__.replace("cmd_", "")
        # description — приоритетнее, но если не задан, берём doc
        final_doc = description if description is not None else doc
        func.__tetko_command__ = {
            "name": cmd_name,
            "aliases": list(aliases or []),
            "doc": final_doc,
            "kwargs": kwargs,
        }
        return func
    return decorator


def watcher(*args: Any, **kwargs: Any) -> Callable:
    """@watcher — реакция на все сообщения."""
    def decorator(func: Callable) -> Callable:
        func.__tetko_watcher__ = {"kwargs": kwargs}
        return func
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def callback(*args: Any, **kwargs: Any) -> Callable:
    """@callback — реакция на inline-кнопки."""
    def decorator(func: Callable) -> Callable:
        func.__tetko_callback__ = {"kwargs": kwargs}
        return func
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def loop(*args: Any, **kwargs: Any) -> Callable:
    """@loop — периодическая задача."""
    def decorator(func: Callable) -> Callable:
        func.__tetko_loop__ = {
            "interval": kwargs.get("interval", 60),
            "kwargs": kwargs,
        }
        return func
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator
