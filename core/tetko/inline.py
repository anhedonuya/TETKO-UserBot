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

    def register_handler(
        self,
        func: Callable,
        args: list | None = None,
        ttl: float = 600,
    ) -> str:
        """Зарегистрировать обработчик, вернуть token."""
        token = secrets.token_urlsafe(16)
        self._handlers[token] = {
            "func": func,
            "args": list(args or []),
            "ttl": ttl,
            "created": time.time(),
        }
        return token

    def get_handler(self, token: str) -> Optional[dict]:
        """Получить хендлер по token (с проверкой TTL)."""
        h = self._handlers.get(token)
        if not h:
            return None
        if time.time() - h["created"] > h["ttl"]:
            del self._handlers[token]
            return None
        return h

    def cleanup(self) -> int:
        """Удалить истёкшие хендлеры. Вернуть количество."""
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
        """Создать inline-кнопку (dict с label + token)."""
        token = self.register_handler(func, args=args, ttl=ttl)
        return {"label": label, "token": token, "style": style}

    def _build_rows(self, buttons: list[list[dict]]):
        """Собрать telethon-кнопки из наших dict-ов."""
        from telethon.tl.custom import Button
        rows = []
        for row in buttons:
            buttons_row = []
            for btn in row:
                buttons_row.append(Button.inline(btn["label"], data=btn["token"]))
            rows.append(buttons_row)
        return rows

    async def form(
        self,
        chat_id: int,
        text: str,
        buttons: list[list[dict]],
        reply_to: int | None = None,
    ):
        """Отправить сообщение с inline-кнопками."""
        rows = self._build_rows(buttons)
        return await self.kernel.client.send_message(
            chat_id,
            text,
            buttons=rows,
            parse_mode="html",
            reply_to=reply_to,
        )

    async def edit(
        self,
        event: Any,
        text: str,
        buttons: list[list[dict]] | None = None,
    ):
        """Отредактировать сообщение (опционально с новыми кнопками)."""
        if buttons is None:
            return await event.edit(text, parse_mode="html")
        rows = self._build_rows(buttons)
        return await event.edit(text, buttons=rows, parse_mode="html")

    async def answer(self, event: Any, text: str = "", alert: bool = False):
        """Ответить на callback (всплывающее уведомление)."""
        try:
            await event.answer(text, alert=alert)
        except Exception:
            pass
