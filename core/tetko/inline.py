"""Inline — inline-клавиатуры и callback-маршрутизация для TETKO."""
from __future__ import annotations

import logging
import secrets
import time
from typing import Any, Callable, Optional

from telethon.tl.types import (
    KeyboardButtonCallback,
    KeyboardButtonSwitchInline,
    KeyboardButtonStyle,
)

log = logging.getLogger("TETKO.tetko.inline")


def _make_btn_style(style_name, emoji_id=None):
    bg_primary = False
    bg_success = False
    bg_danger = False
    if style_name == "primary":
        bg_primary = True
    elif style_name == "success":
        bg_success = True
    elif style_name == "danger":
        bg_danger = True
    if emoji_id is None and not (bg_primary or bg_success or bg_danger):
        return None
    from telethon.tl.types import KeyboardButtonStyle
    kwargs = {}
    if emoji_id is not None:
        kwargs["icon"] = emoji_id
    if bg_primary:
        kwargs["bg_primary"] = True
    if bg_success:
        kwargs["bg_success"] = True
    if bg_danger:
        kwargs["bg_danger"] = True
    try:
        return KeyboardButtonStyle(**kwargs)
    except Exception:
        return None




import re as _re

_TG_EMOJI_RE = _re.compile(r'<tg-emoji emoji-id="(\d+)">(.*?)</tg-emoji>')


def _split_label(label: str) -> tuple[str, int | None]:
    if not isinstance(label, str):
        return str(label), None
    m = _TG_EMOJI_RE.search(label)
    if not m:
        return label, None
    emoji_id = int(m.group(1))
    plain = _TG_EMOJI_RE.sub(lambda x: x.group(2), label)
    return plain, emoji_id

class Inline:
    """Менеджер inline-кнопок и временных callback-хендлеров."""

    def __init__(self, kernel: Any = None):
        self.kernel = kernel
        self._handlers: dict[str, dict] = {}

    def register_handler(
        self,
        func: Callable,
        args: list | None = None,
        ttl: float = 600,
    ) -> str:
        token = secrets.token_urlsafe(16)
        self._handlers[token] = {
            "func": func,
            "args": list(args or []),
            "ttl": ttl,
            "created": time.time(),
        }
        return token

    def get_handler(self, token: str) -> Optional[dict]:
        h = self._handlers.get(token)
        if not h:
            return None
        if time.time() - h["created"] > h["ttl"]:
            del self._handlers[token]
            return None
        return h

    def is_owner(self, user_id) -> bool:
        """Проверка владельца."""
        if self.kernel is None or not hasattr(self.kernel, "context"):
            return False
        return self.kernel.context.is_owner(user_id)

    def cleanup(self) -> int:
        now = time.time()
        expired = [
            t for t, h in self._handlers.items()
            if now - h["created"] > h["ttl"]
        ]
        for t in expired:
            del self._handlers[t]
        return len(expired)

    def make_button(
        self,
        label: str,
        func: Callable,
        args: list | None = None,
        ttl: float = 600,
        style: str = "primary",
    ) -> dict:
        token = self.register_handler(func, args=args, ttl=ttl)
        return {"label": label, "token": token, "style": style}

    def _build_markup(self, buttons: list[list[dict]]):
        """Собрать ReplyInlineMarkup через ButtonMethods.build_reply_markup."""
        from telethon.client.buttons import ButtonMethods

        rows = []
        for row in buttons:
            btn_row = []
            for btn in row:
                kind = btn.get("kind", "callback") if isinstance(btn, dict) else "callback"
                label, emoji_id = _split_label(btn["label"])
                style = _make_btn_style(btn.get("style") if isinstance(btn, dict) else None, emoji_id)
                if kind == "switch_current":
                    kw = {"same_peer": True}
                    if style is not None:
                        kw["style"] = style
                    btn_row.append(KeyboardButtonSwitchInline(text=label, query=btn.get("query", ""), **kw))
                    continue
                if kind == "switch":
                    kw = {"same_peer": False}
                    if style is not None:
                        kw["style"] = style
                    btn_row.append(KeyboardButtonSwitchInline(text=label, query=btn.get("query", ""), **kw))
                    continue
                data = btn["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                if style is not None:
                    btn_row.append(KeyboardButtonCallback(text=label, data=data, style=style))
                else:
                    btn_row.append(KeyboardButtonCallback(text=label, data=data))
            rows.append(btn_row)

        client = self.kernel.client
        try:
            return client.build_reply_markup(rows)
        except Exception as e:
            log.warning(f"_build_markup: client.build_reply_markup failed: {e}")

        from telethon.tl.types import (
            ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonCallback,
            KeyboardButtonSwitchInline,
        )
        kb_rows = []
        for row in buttons:
            kb_row = []
            for btn in row:
                kind = btn.get("kind", "callback") if isinstance(btn, dict) else "callback"
                label, emoji_id = _split_label(btn["label"])
                style = _make_btn_style(btn.get("style") if isinstance(btn, dict) else None, emoji_id)
                if kind == "switch_current":
                    kw = {"same_peer": True}
                    if style is not None:
                        kw["style"] = style
                    kb_row.append(KeyboardButtonSwitchInline(
                        text=label,
                        query=btn.get("query", ""),
                        **kw,
                    ))
                    continue
                if kind == "switch":
                    kw = {"same_peer": False}
                    if style is not None:
                        kw["style"] = style
                    kb_row.append(KeyboardButtonSwitchInline(
                        text=label,
                        query=btn.get("query", ""),
                        **kw,
                    ))
                    continue
                data = btn["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                if style is not None:
                    kb_row.append(KeyboardButtonCallback(text=label, data=data, style=style))
                else:
                    kb_row.append(KeyboardButtonCallback(text=label, data=data))
            kb_rows.append(KeyboardButtonRow(buttons=kb_row))
        return ReplyInlineMarkup(rows=kb_rows)

    async def form(
        self,
        chat_id: int,
        text: str,
        buttons: list[list[dict]],
        reply_to: int | None = None,
        parse_mode: str | None = "html",
    ):
        """Отправить сообщение с inline-кнопками через низкоуровневый запрос."""
        from telethon.tl.functions.messages import SendMessageRequest
        from telethon.tl.types import InputReplyToMessage

        markup = self._build_markup(buttons)
        peer = await self.kernel.client.get_input_entity(chat_id)

        message_text = text
        entities = None
        if parse_mode == "html":
            try:
                parsed, entities = await self.kernel.client._parse_message_text(text, "html")
                message_text = parsed
            except Exception as e:
                log.debug(f"form: parse_message_text failed: {e}")

        kwargs = {
            "peer": peer,
            "message": message_text,
            "reply_markup": markup,
        }
        if entities:
            kwargs["entities"] = entities
        if reply_to is not None:
            kwargs["reply_to"] = InputReplyToMessage(reply_to)

        result = await self.kernel.client(SendMessageRequest(**kwargs))
        return result

    async def edit(
        self,
        event: Any,
        text: str,
        buttons: list[list[dict]] | None = None,
    ):
        """Отредактировать сообщение (inline или обычное)."""
        if buttons is None:
            try:
                return await event.edit(text, parse_mode="html")
            except Exception:
                return None

        rows = []
        for row in buttons:
            btn_row = []
            for b in row:
                kind = b.get("kind", "callback") if isinstance(b, dict) else "callback"
                label, emoji_id = _split_label(b["label"])
                style = _make_btn_style(b.get("style") if isinstance(b, dict) else None, emoji_id)
                if kind == "switch_current":
                    kw = {"same_peer": True}
                    if style is not None:
                        kw["style"] = style
                    btn_row.append(KeyboardButtonSwitchInline(text=label, query=b.get("query", ""), **kw))
                    continue
                if kind == "switch":
                    kw = {"same_peer": False}
                    if style is not None:
                        kw["style"] = style
                    btn_row.append(KeyboardButtonSwitchInline(text=label, query=b.get("query", ""), **kw))
                    continue
                data = b["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                if style is not None:
                    btn_row.append(KeyboardButtonCallback(text=label, data=data, style=style))
                else:
                    btn_row.append(KeyboardButtonCallback(text=label, data=data))
            rows.append(btn_row)

        bot = getattr(self.kernel, "bot_client", None)
        imid = getattr(event, "inline_message_id", None)
        if not imid:
            data = getattr(event, "data", b"")
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            if bot is not None and hasattr(bot, "get_inline_message_id"):
                imid = bot.get_inline_message_id(data)

        if imid and bot is not None:
            try:
                await bot.edit_inline_menu(
                    inline_message_id=imid,
                    text=text,
                    buttons=buttons,
                )
                if not hasattr(bot, "_inlines"):
                    bot._inlines = {}
                for row in buttons:
                    for b in row:
                        if isinstance(b, dict) and "token" in b:
                            bot._inlines[b["token"]] = imid
                return
            except Exception as e:
                _es = str(e).lower()
                if "not modified" not in _es:
                    log.warning(f"inline.edit via bot failed: {e}")

        try:
            return await event.edit(text, buttons=rows, parse_mode="html")
        except Exception as e:
            _es = str(e).lower()
            if "not modified" in _es or "message is not modified" in _es:
                return None
            log.warning(f"inline.edit fallback failed: {e}")
            try:
                return await event.edit(text, parse_mode="html")
            except Exception as e2:
                _e2 = str(e2).lower()
                if "not modified" in _e2:
                    return None
                return None

    async def answer(self, event: Any, text: str = "", alert: bool = False):
        try:
            await event.answer(text, alert=alert)
        except Exception:
            pass
