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


async def _is_allowed(kernel, event) -> bool:
    sender = getattr(event, "sender_id", None)
    if sender is None:
        sender = getattr(getattr(event, "from_user", None), "id", None)
    try:
        sender = int(sender) if sender is not None else None
    except (ValueError, TypeError):
        sender = None
    if sender is None:
        return False

    cfg = getattr(kernel, "config", None) or {}
    owner = cfg.get("admin_id") or cfg.get("owner_id")
    if owner is not None:
        try:
            if int(owner) == sender:
                return True
        except (ValueError, TypeError):
            pass

    try:
        from core.tetko import db as _db
        raw = _db.db_get("inline_perm", "allowed_users")
        if raw:
            import json as _json
            users = _json.loads(raw) if isinstance(raw, str) else raw
            if sender in (users or []):
                return True
        denied_raw = _db.db_get("inline_perm", "denied_users")
        if denied_raw:
            import json as _json
            denied = _json.loads(denied_raw) if isinstance(denied_raw, str) else denied_raw
            if sender in (denied or []):
                return False
        mode = _db.db_get("inline_perm", "everyone_mode")
        if mode:
            return True
    except Exception:
        pass

    return False


async def _call_handler(entry: dict, event: Any, kernel: Any = None) -> None:
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
    if not hasattr(bot_client, "on"):
        log.debug("[callback] bot_client без .on — пропускаем (обработает TETKO bot.py)")
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
                return

            if not await _is_allowed(kernel, event):
                try:
                    await event.answer("🚫 Нет доступа", alert=True)
                except Exception:
                    pass
                return

            try:
                await event.answer()
            except Exception:
                pass

            await _call_handler(entry, event, kernel)
        except Exception as e:
            log.exception(f"callback dispatcher: {e}")

    log.info("[mcub_compat] callback handler установлен на bot_client")


__all__ = ["install_callback_handler"]
