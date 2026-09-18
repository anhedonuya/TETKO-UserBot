"""Inline — inline-клавиатуры и callback-маршрутизация для TETKO."""
from __future__ import annotations

import logging
import secrets
import time
from typing import Any, Callable, Optional

log = logging.getLogger("TETKO.tetko.inline")


class Inline:
    """Менеджер inline-кнопок и временных callback-хендлеров."""

    def __init__(self, kernel: Any = None):
        self.kernel = kernel
        self._handlers: dict[str, dict] = {}

    # ── Регистрация временного callback-хендлера ──
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

    # ── Построение ReplyInlineMarkup БЕЗ build_reply_markup ──
    def _build_markup(self, buttons: list[list[dict]]):
        """Собрать ReplyInlineMarkup через ButtonMethods.build_reply_markup."""
        from telethon.tl.custom import Button
        from telethon.client.buttons import ButtonMethods

        # конвертируем наши dict-ы в Button.inline
        rows = []
        for row in buttons:
            btn_row = []
            for btn in row:
                data = btn["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                btn_row.append(Button.inline(btn["label"], data=data))
            rows.append(btn_row)

        # build_reply_markup — метод клиента (self = client)
        client = self.kernel.client
        try:
            return client.build_reply_markup(rows)
        except Exception as e:
            log.warning(f"_build_markup: client.build_reply_markup failed: {e}")

        # fallback — вручную
        from telethon.tl.types import (
            ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonCallback,
        )
        kb_rows = []
        for row in buttons:
            kb_row = []
            for btn in row:
                data = btn["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                kb_row.append(KeyboardButtonCallback(text=btn["label"], data=data))
            kb_rows.append(KeyboardButtonRow(buttons=kb_row))
        return ReplyInlineMarkup(rows=kb_rows)

    # ── Отправка сообщения с кнопками (через SendMessageRequest) ──
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

        # парсим HTML в entities + получаем текст без тегов
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

    # ── Редактирование сообщения с кнопками ──
    async def edit(
        self,
        event: Any,
        text: str,
        buttons: list[list[dict]] | None = None,
    ):
        """Отредактировать сообщение (опционально с новыми кнопками)."""
        if buttons is None:
            return await event.edit(text, parse_mode="html")

        from telethon.tl.functions.messages import EditMessageRequest

        markup = self._build_markup(buttons)

        # парсим HTML
        message_text = text
        entities = None
        try:
            parsed, entities = await self.kernel.client._parse_message_text(text, "html")
            message_text = parsed
        except Exception:
            pass

        try:
            peer = await event.get_input_chat()
            kwargs = {
                "peer": peer,
                "id": event.message_id,
                "message": message_text,
                "reply_markup": markup,
            }
            if entities:
                kwargs["entities"] = entities
            await self.kernel.client(EditMessageRequest(**kwargs))
        except Exception as e:
            log.warning(f"edit через raw request не сработал, fallback: {e}")
            try:
                await event.edit(text, parse_mode="html")
            except Exception:
                pass

    async def answer(self, event: Any, text: str = "", alert: bool = False):
        try:
            await event.answer(text, alert=alert)
        except Exception:
            pass
