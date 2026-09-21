"""MCUB-совместимый core_inline.

Реализует:
    InlineManager       — права (allow/deny/is_allowed) через tetko db
    make_cb_button      — Button.inline + токен в реестре kernel
    build_*             — словарные билдеры inline-результатов
    InlineHandlers      — минимальная заглушка (диспетчер живёт в tetko)
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from typing import Any

log = logging.getLogger("TETKO.mcub_compat.inline_shim")


# ────────────────────────────────────────────────────────────────────
#  InlineManager — права (порт из core_inline/lib/manager.py)
# ────────────────────────────────────────────────────────────────────

class InlineManager:
    """Менеджер прав inline. Работает с async db_get/db_set tetko."""

    MODULE = "inline_permissions"

    def __init__(self, kernel):
        self.kernel = kernel

    def _admin_id(self):
        k = self.kernel
        ctx = getattr(k, "context", None)
        if ctx is not None:
            return getattr(ctx, "admin_id", None)
        return getattr(k, "ADMIN_ID", None)

    async def is_admin(self, user_id: int) -> bool:
        admin_id = self._admin_id()
        if admin_id is None:
            return False
        try:
            return int(admin_id) > 0 and int(user_id) == int(admin_id)
        except (ValueError, TypeError):
            return False

    async def is_allowed(self, user_id: int, command: str | None = None) -> bool:
        if await self.is_admin(user_id):
            return True

        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if all_users:
                allowed = json.loads(all_users) if isinstance(all_users, str) else all_users
                denied = allowed.get("denied", {})
                if command and isinstance(denied, dict):
                    if user_id in denied.get(command, []):
                        return False
                if user_id in allowed.get("global", []):
                    return True
                if command and user_id in allowed.get(command, []):
                    return True
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            data = await self.kernel.db_get("trusted", "users")
            if data:
                trusted = json.loads(data) if isinstance(data, str) else json.loads(str(data))
                if user_id in trusted:
                    return True
        except Exception:
            pass

        return False

    async def allow_user(self, user_id: int, command: str | None = None) -> bool:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            allowed = json.loads(all_users) if all_users else {"global": []}
            target = "global" if command is None else command
            if target not in allowed:
                allowed[target] = []

            denied = allowed.get("denied", {})
            if command is not None and isinstance(denied, dict):
                denied_users = denied.get(command, [])
                if user_id in denied_users:
                    denied_users.remove(user_id)
                if denied_users:
                    denied[command] = denied_users
                else:
                    denied.pop(command, None)
                if denied:
                    allowed["denied"] = denied
                else:
                    allowed.pop("denied", None)

            if user_id not in allowed[target]:
                allowed[target].append(user_id)
            await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
            return True
        except Exception as e:
            log.error(f"InlineManager allow_user: {e}")
            return False

    async def deny_user(self, user_id: int, command: str | None = None) -> bool:
        try:
            if await self.is_admin(user_id):
                return False

            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if not all_users:
                return False

            allowed = json.loads(all_users) if isinstance(all_users, str) else all_users
            target = "global" if command is None else command

            if command is not None:
                denied = allowed.get("denied", {})
                if not isinstance(denied, dict):
                    denied = {}
                denied_users = denied.setdefault(command, [])
                if user_id not in denied_users:
                    denied_users.append(user_id)
                allowed["denied"] = denied

            if target in allowed and user_id in allowed[target]:
                allowed[target].remove(user_id)
            await self.kernel.db_set(self.MODULE, "allowed_users", json.dumps(allowed))
            return True
        except Exception as e:
            log.error(f"InlineManager deny_user: {e}")
            return False

    async def get_allowed_users(self, command: str | None = None) -> list:
        try:
            all_users = await self.kernel.db_get(self.MODULE, "allowed_users")
            if not all_users:
                return []
            allowed = json.loads(all_users) if isinstance(all_users, str) else all_users
            target = "global" if command is None else command
            return allowed.get(target, [])
        except Exception:
            return []

    async def clear_all(self) -> bool:
        try:
            await self.kernel.db_delete(self.MODULE, "allowed_users")
            return True
        except Exception as e:
            log.error(f"InlineManager clear_all: {e}")
            return False


# ────────────────────────────────────────────────────────────────────
#  make_cb_button + работа с kernel.inline_callback_map
# ────────────────────────────────────────────────────────────────────

def _unwrap_kernel(kernel):
    """Return the real TETKO kernel behind KernelProxy."""
    return getattr(kernel, "_k", kernel)


def _ensure_cb_map(kernel):
    if not hasattr(kernel, "_inline_cb_lock"):
        try:
            kernel._inline_cb_lock = threading.Lock()
        except Exception:
            pass
    if not hasattr(kernel, "inline_callback_map"):
        try:
            kernel.inline_callback_map = {}
        except Exception:
            pass
    return getattr(kernel, "_inline_cb_lock", None), getattr(kernel, "inline_callback_map", None)


def make_cb_button(kernel, text, callback, *, args=None, kwargs=None,
                   ttl=900, token=None, icon=None, style=None):
    from telethon import Button
    if not callable(callback):
        raise TypeError("callback must be callable")

    kernel = _unwrap_kernel(kernel)
    lock, cb_map = _ensure_cb_map(kernel)
    if lock is None or cb_map is None:
        return Button.inline(text, uuid.uuid4().hex.encode())

    with lock:
        now = time.time()
        for k in [k for k, v in list(cb_map.items())
                  if v.get("expires_at") and v["expires_at"] < now]:
            cb_map.pop(k, None)

        tok = token or uuid.uuid4().hex
        cb_map[tok] = {
            "handler": callback,
            "args": list(args or []),
            "kwargs": dict(kwargs or {}),
            "expires_at": now + ttl if ttl else None,
        }

    try:
        return Button.inline(text, tok.encode(), icon=icon, style=style)
    except TypeError:
        return Button.inline(text, tok.encode())


# ────────────────────────────────────────────────────────────────────
#  Билдеры словарных inline-результатов (копия core_inline/api/core.py)
# ────────────────────────────────────────────────────────────────────

def build_inline_result_text(title, text, description=None, parse_mode="HTML", result_id=None):
    r = {"type": "article", "id": result_id or str(uuid.uuid4()), "title": title,
         "input_message_content": {"message_text": text or "", "parse_mode": parse_mode}}
    if description is not None:
        r["description"] = description
    elif text:
        r["description"] = text[:200]
    return r


def build_inline_result_photo(photo_url, text, title, description=None, parse_mode="HTML",
                              thumb_url=None, result_id=None):
    r = {"type": "photo", "id": result_id or str(uuid.uuid4()), "photo_url": photo_url,
         "thumbnail_url": thumb_url or photo_url, "title": title, "caption": text,
         "parse_mode": parse_mode}
    if description is not None:
        r["description"] = description
    return r


def build_inline_result_video(video_url, text, title, mime_type="video/mp4",
                              thumb_url=None, description=None, parse_mode="HTML", result_id=None):
    r = {"type": "video", "id": result_id or str(uuid.uuid4()), "video_url": video_url,
         "mime_type": mime_type, "thumbnail_url": thumb_url or video_url, "title": title,
         "caption": text, "parse_mode": parse_mode}
    if description is not None:
        r["description"] = description
    return r


def build_inline_result_document(document_url, text, title, mime_type="application/octet-stream",
                                 thumb_url=None, description=None, parse_mode="HTML", result_id=None):
    r = {"type": "document", "id": result_id or str(uuid.uuid4()), "document_url": document_url,
         "mime_type": mime_type, "thumbnail_url": thumb_url or "https://kappa.lol/KSKoOu",
         "title": title, "caption": text, "parse_mode": parse_mode}
    if description is not None:
        r["description"] = description
    return r


def build_inline_result_gif(gif_url, text, title, thumb_url=None, description=None,
                            parse_mode="HTML", result_id=None):
    r = {"type": "mpeg4_gif", "id": result_id or str(uuid.uuid4()), "mpeg4_url": gif_url,
         "thumbnail_url": thumb_url or gif_url, "title": title, "caption": text,
         "parse_mode": parse_mode}
    if description is not None:
        r["description"] = description
    return r


def build_inline_result_audio(audio_url, text, title, performer=None, duration=None,
                              description=None, parse_mode="HTML", result_id=None):
    r = {"type": "audio", "id": result_id or str(uuid.uuid4()), "audio_url": audio_url,
         "title": title, "caption": text, "parse_mode": parse_mode}
    if performer is not None:
        r["performer"] = performer
    if duration is not None:
        r["audio_duration"] = duration
    if description is not None:
        r["description"] = description
    return r


def build_inline_result_voice(voice_url, text, title, duration=None, description=None,
                              parse_mode="HTML", result_id=None):
    r = {"type": "voice", "id": result_id or str(uuid.uuid4()), "voice_url": voice_url,
         "title": title, "caption": text, "parse_mode": parse_mode}
    if duration is not None:
        r["voice_duration"] = duration
    if description is not None:
        r["description"] = description
    return r


def build_inline_result_sticker(sticker_url, text=None, title=None, description=None, result_id=None):
    r = {"type": "sticker", "id": result_id or str(uuid.uuid4()), "sticker_url": sticker_url}
    if text is not None:
        r["caption"] = text
    if title is not None:
        r["title"] = title
    if description is not None:
        r["description"] = description
    return r


def build_inline_result_media(media_url, media_type, text, title, description=None,
                              parse_mode="HTML", result_id=None):
    mt = media_type.lower()
    fn = {
        "photo": build_inline_result_photo, "video": build_inline_result_video,
        "document": build_inline_result_document, "gif": build_inline_result_gif,
        "audio": build_inline_result_audio, "voice": build_inline_result_voice,
        "sticker": build_inline_result_sticker,
    }.get(mt, build_inline_result_photo)
    try:
        return fn(media_url, text, title, description=description,
                  parse_mode=parse_mode, result_id=result_id)
    except TypeError:
        return fn(media_url, text, title, result_id=result_id)


def build_input_message_content(text, parse_mode=None, entities=None, disable_web_page_preview=False):
    c = {"message_text": text}
    if parse_mode:
        c["parse_mode"] = parse_mode
    if entities:
        c["entities"] = entities
    if disable_web_page_preview:
        c["disable_web_page_preview"] = True
    return c


def build_button_callback(text, data, emoji=None):
    b = {"text": text, "callback_data": data}
    if emoji:
        b["emoji"] = emoji
    return b


def build_button_url(text, url, emoji=None):
    b = {"text": text, "url": url}
    if emoji:
        b["emoji"] = emoji
    return b


def build_button_switch(text, query, hint="", emoji=None, same_peer=False):
    b = {"text": text}
    if same_peer or hint:
        b["switch_inline_query_current_chat"] = hint or query
    else:
        b["switch_inline_query"] = query
    if emoji:
        b["emoji"] = emoji
    return b


def build_button_phone(text, emoji=None):
    b = {"text": text, "request_contact": True}
    if emoji:
        b["emoji"] = emoji
    return b


def build_button_location(text, emoji=None):
    b = {"text": text, "request_location": True}
    if emoji:
        b["emoji"] = emoji
    return b


def build_button_game(text, emoji=None):
    b = {"text": text, "callback_game": {}}
    if emoji:
        b["emoji"] = emoji
    return b


def build_inline_button(btn):
    """Телеграм Button → dict для Bot API."""
    from telethon.tl.types import (
        KeyboardButtonCallback, KeyboardButtonGame, KeyboardButtonRequestGeoLocation,
        KeyboardButtonRequestPhone, KeyboardButtonSwitchInline, KeyboardButtonUrl,
    )
    if isinstance(btn, KeyboardButtonCallback):
        data = btn.data
        return {"text": btn.text, "callback_data": data.decode() if isinstance(data, bytes) else str(data)}
    if isinstance(btn, KeyboardButtonUrl):
        return {"text": btn.text, "url": btn.url}
    if isinstance(btn, KeyboardButtonSwitchInline):
        key = "switch_inline_query_current_chat" if getattr(btn, "same_peer", False) else "switch_inline_query"
        return {"text": btn.text, key: btn.query or ""}
    if isinstance(btn, KeyboardButtonRequestPhone):
        return {"text": btn.text, "request_contact": True}
    if isinstance(btn, KeyboardButtonRequestGeoLocation):
        return {"text": btn.text, "request_location": True}
    if isinstance(btn, KeyboardButtonGame):
        return {"text": btn.text, "callback_game": {}}
    return {"text": str(btn)}


def build_inline_keyboard(rows, resize=None, one_time=None):
    kb = []
    for row in rows:
        if not isinstance(row, list):
            row = [row]
        kb_row = [build_inline_button(b) for b in row if b]
        if kb_row:
            kb.append(kb_row)
    r = {"inline_keyboard": kb}
    if resize is not None:
        r["resize_keyboard"] = resize
    if one_time is not None:
        r["one_time_keyboard"] = one_time
    return r


def add_inline_keyboard_to_result(result, buttons, parse_mode=None):
    result["reply_markup"] = build_inline_keyboard(buttons)
    if parse_mode:
        if "input_message_content" not in result:
            result["input_message_content"] = {}
        result["input_message_content"]["parse_mode"] = parse_mode
    return result


# ────────────────────────────────────────────────────────────────────
#  InlineHandlers — заглушка (диспетчер inline живёт в tetko)
# ────────────────────────────────────────────────────────────────────

class InlineHandlers:
    """Compatibility facade for MCUB's core_inline.handlers.InlineHandlers.

    TETKO keeps actual inline rendering in ``kernel.inline``.  This class adds
    the MCUB form cache and the handful of helper methods used by modules.
    """

    def __init__(self, kernel, bot_client=None):
        self.kernel = _unwrap_kernel(kernel)
        self.bot_client = bot_client or getattr(self.kernel, "bot_client", None)
        self._forms = {}
        self._counter = 0

    def create_inline_form(self, text="", buttons=None, ttl=3600, media=None,
                           media_type="photo", rich_text=None, rich_parse_mode="html",
                           **kwargs):
        self._counter += 1
        form_id = f"form_{uuid.uuid4().hex[:16]}"
        self._forms[form_id] = {
            "text": rich_text if rich_text is not None else text,
            "buttons": buttons or [],
            "media": media,
            "media_type": media_type,
            "expires_at": time.time() + ttl if ttl else None,
            "rich": rich_text is not None,
            "parse_mode": rich_parse_mode,
        }
        return form_id

    def get_inline_form(self, form_id):
        item = self._forms.get(form_id)
        if not item:
            return None
        exp = item.get("expires_at")
        if exp and exp < time.time():
            self._forms.pop(form_id, None)
            return None
        return item

    async def send_inline_menu(self, chat_id, key, text=None, buttons=None,
                               rich=False, reply_to=None, **kwargs):
        form = self.get_inline_form(key)
        if form:
            text = text if text is not None else form["text"]
            buttons = buttons if buttons is not None else form["buttons"]
        inline = getattr(self.kernel, "inline", None)
        if inline is not None:
            try:
                return await inline.form(chat_id, text or "", buttons or [],
                                         reply_to=reply_to)
            except Exception:
                pass
        client = getattr(self.kernel, "client", None)
        if client is not None:
            return await client.send_message(chat_id, text or "", buttons=buttons)
        return None

    async def register_handlers(self):
        # Callback dispatch is installed by callback_dispatch.py; this method is
        # intentionally idempotent and only cleans expired form sessions.
        for key in list(self._forms):
            self.get_inline_form(key)
        return True

    async def unregister_handlers(self):
        self._forms.clear()
        return True


__all__ = [
    "InlineManager",
    "make_cb_button",
    "build_inline_result_text", "build_inline_result_photo", "build_inline_result_video",
    "build_inline_result_document", "build_inline_result_gif", "build_inline_result_audio",
    "build_inline_result_voice", "build_inline_result_sticker", "build_inline_result_media",
    "build_input_message_content", "build_button_callback", "build_button_url",
    "build_button_switch", "build_button_phone", "build_button_location", "build_button_game",
    "build_inline_button", "build_inline_keyboard", "add_inline_keyboard_to_result",
    "InlineHandlers",
]
