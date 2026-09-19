"""Диспетчер callback-ов для mcub-модулей.

Подключается к tetko bot_client, ловит CallbackQuery, ищет токен
в kernel.inline_callback_map и вызывает сохранённый handler.
"""
from __future__ import annotations

import asyncio
import html
import inspect
import logging
import time
from typing import Any

from telethon import events

log = logging.getLogger("TETKO.mcub_compat.callback")


def _ensure_map(kernel):
    if not hasattr(kernel, "inline_callback_map"):
        try:
            kernel.inline_callback_map = {}
        except Exception:
            pass
    if not hasattr(kernel, "_inline_cb_lock"):
        import threading
        try:
            kernel._inline_cb_lock = threading.Lock()
        except Exception:
            pass


def _lookup_token(kernel, token: str) -> dict | None:
    _ensure_map(kernel)
    lock = getattr(kernel, "_inline_cb_lock", None)
    cb_map = getattr(kernel, "inline_callback_map", None)
    if cb_map is None:
        return None

    if lock is None:
        entry = cb_map.get(token)
    else:
        with lock:
            entry = cb_map.get(token)
            # чистка просроченных
            now = time.time()
            for k in [k for k, v in list(cb_map.items())
                      if v.get("expires_at") and v["expires_at"] < now]:
                cb_map.pop(k, None)

    if entry is None:
        return None
    exp = entry.get("expires_at")
    if exp and exp < time.time():
        return None
    return entry


async def _call_handler(entry: dict, event: Any) -> None:
    """Вызывает handler с учётом сигнатуры."""
    handler = entry.get("handler")
    if not callable(handler):
        return

    args = list(entry.get("args", []))
    kwargs = dict(entry.get("kwargs", {}))
    if "data" not in kwargs and entry.get("data") is not None:
        kwargs["data"] = entry["data"]

    try:
        # пробуем разные варианты
        sig = inspect.signature(handler)
        params = [p for p in sig.parameters.values()
                  if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
        n = len(params)
    except (TypeError, ValueError):
        n = 1

    try:
        if n == 0:
            result = handler()
        elif n == 1:
            result = handler(event)
        else:
            result = handler(event, *args, **kwargs)
        if inspect.isawaitable(result):
            await result
    except Exception as e:
        log.exception(f"callback handler: {e}")
        try:
            await event.answer(f"error: {e}", alert=True)
        except Exception:
            pass


def install_callback_handler(kernel, bot_client) -> None:
    """Подключить обработчик к bot_client один раз."""
    if bot_client is None:
        log.debug("[callback] bot_client отсутствует — пропускаем")
        return
    if getattr(bot_client, "_mcub_cb_handler_installed", False):
        return
    try:
        bot_client._mcub_cb_handler_installed = True
    except Exception:
        pass

    @bot_client.on(events.CallbackQuery())
    async def _mcub_cb_handler(event):
        try:
            data = event.data
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            if not data:
                return

            entry = _lookup_token(kernel, data)
            if entry is None:
                # не наш токен — пусть обрабатывают другие
                return

            # сначала гасим спиннер, потом зовём handler
            try:
                await event.answer()
            except Exception:
                pass

            await _call_handler(entry, event)
        except Exception as e:
            log.exception(f"callback dispatcher: {e}")

    log.info("[mcub_compat] callback handler установлен на bot_client")


__all__ = ["install_callback_handler"]
