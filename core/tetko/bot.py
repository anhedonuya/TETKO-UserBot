"""BotClient — inline-бот TETKO для отправки кнопок в любой чат.

Работает РЯДОМ с юзерботом в одном процессе. Юзербот запрашивает
inline-результат у бота (send_inline_menu) и отправляет его в нужный чат.
Telegram разрешает отправлять inline-результаты в ЛЮБОЙ чат — даже
без присутствия бота.
"""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from typing import Any, Optional

from telethon import TelegramClient, events
from telethon.tl.functions.messages import (
    GetInlineBotResultsRequest,
    SendInlineBotResultRequest,
)
from telethon.tl.types import (
    UpdateBotInlineSend,
    InputBotInlineResult,
    InputBotInlineMessageText,
    ReplyInlineMarkup,
    KeyboardButtonRow,
    KeyboardButtonCallback,
)

log = logging.getLogger("TETKO.tetko.bot")


class BotClient:
    """Inline-бот: регистрация меню + отправка через inline в любой чат."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        bot_token: str,
        kernel: Any = None,
    ):
        self.kernel = kernel
        self.username: Optional[str] = None
        self.client = TelegramClient("tetko_inline_bot", api_id, api_hash)
        self._bot_token = bot_token

        # Хранилище готовых меню: key → {text, buttons, created, ttl}
        self._menus: dict[str, dict] = {}
        self._inline_sends: dict[str, str] = {}

    # ─── Старт / стоп ───
    async def start(self) -> None:
        await self.client.start(bot_token=self._bot_token)
        me = await self.client.get_me()
        self.username = me.username
        log.info(f"🤖 Inline-бот запущен: @{self.username}")

        # inline-запросы (например, @tetkodevbot <key>)
        @self.client.on(events.InlineQuery())
        async def on_inline(event):
            await self._handle_inline(event)

        # callback от кнопок
        @self.client.on(events.CallbackQuery())
        async def on_callback(event):
            await self._handle_callback(event)

        # /start, /menu, /help
        @self.client.on(events.NewMessage(pattern=r"^/(start|menu|help)"))
        async def on_start(event):
            await self._handle_start(event)

        # UpdateBotInlineSend — приходит inline_message_id
        from telethon import events as _events
        @self.client.on(_events.Raw(UpdateBotInlineSend))
        async def on_inline_send(update):
            qid = update.id
            imid = update.msg_id
            self._inline_sends[qid] = imid

    async def stop(self) -> None:
        await self.client.disconnect()

    # ─── Регистрация меню ───
    def register_menu(
        self,
        key: str,
        text: str,
        buttons: list[list[dict]],
        ttl: float = 600,
    ) -> None:
        """Зарегистрировать готовое меню под ключом key."""
        now = time.time()
        # чистим только меню (dict-и с "created")
        self._menus = {
            k: v for k, v in self._menus.items()
            if not isinstance(v, dict) or now - v.get("created", 0) < v.get("ttl", 600)
        }
        self._menus[key] = {
            "text": text,
            "buttons": buttons,
            "created": now,
            "ttl": ttl,
        }

    # ─── Отправка inline-меню в чат ───
    async def edit_inline_menu(
        self,
        inline_message_id: str,
        text: str,
        buttons: list[list[dict]],
    ):
        """Отредактировать существующее inline-сообщение."""
        from telethon.tl.functions.messages import EditInlineBotMessageRequest
        from telethon.tl.types import (
            ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonCallback,
        )

        # парсим HTML в entities
        msg_text = text
        entities = None
        try:
            parsed, entities = await self.kernel.client._parse_message_text(text, "html")
            msg_text = parsed
        except Exception as e:
            log.debug(f"edit_inline_menu: parse failed: {e}")

        # markup
        rows = []
        for row in buttons:
            kb_row = []
            for b in row:
                data = b["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                kb_row.append(KeyboardButtonCallback(text=b["label"], data=data))
            rows.append(KeyboardButtonRow(buttons=kb_row))
        markup = ReplyInlineMarkup(rows=rows) if rows else None


        kwargs = {
            "id": inline_message_id,
            "message": msg_text,
        }
        if markup:
            kwargs["reply_markup"] = markup
        if entities:
            kwargs["entities"] = entities

        # ВАЖНО: редактировать inline-сообщение может ТОЛЬКО бот, не юзербот!
        return await self.client(EditInlineBotMessageRequest(**kwargs))

    def get_inline_message_id(self, token: str):
        """Получить inline_message_id по token кнопки."""
        if not hasattr(self, "_inlines"):
            return None
        return self._inlines.get(token)

    def get_message_id(self, token: str):
        """Получить (chat_id, message_id) по token кнопки."""
        return self._menus.get(f"msgid_{token}")

    async def edit_bot_message(self, chat_id, message_id, text: str, buttons: list):
        """Отредактировать сообщение, отправленное ботом."""
        from telethon.tl.custom import Button

        rows = []
        for row in buttons:
            btn_row = []
            for b in row:
                data = b["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                btn_row.append(Button.inline(b["label"], data=data))
            rows.append(btn_row)

        return await self.client.edit_message(
            chat_id,
            message_id,
            text=text,
            buttons=rows,
            parse_mode="html",
        )

    async def send_inline_menu(
        self,
        chat_id: any,
        key: str,
        text: str,
        buttons: list[list[dict]],
        query: str | None = None,
    ):
        """Отправить меню в чат через inline-бота.

        Шаги:
          1. Регистрируем меню под ключом
          2. Запрашиваем inline-результат у бота
          3. Отправляем результат в чат
        """
        # 1. Регистрация
        self.register_menu(key, text, buttons)

        # 2. Запрос к боту
        query_str = query or key
        kernel = self.kernel
        userbot = kernel.client

        # если это уже InputPeer — используем как есть
        _t = type(chat_id).__name__
        if _t.startswith('InputPeer'):
            peer = chat_id
        else:
            try:
                peer = await userbot.get_input_entity(chat_id)
            except Exception as e:
                log.warning(f"send_inline_menu: get_input_entity failed: {e}")
                peer = chat_id

        results = await userbot(GetInlineBotResultsRequest(
            bot=f"@{self.username}",
            peer=peer,
            query=query_str,
            offset="",
        ))

        if not results or not results.results:
            log.error(f"send_inline_menu: нет результатов от бота для {query_str}")
            return None

        # 3. Отправка
        # Оборачиваем в InlineResult — у него есть .click()
        from telethon.tl.custom.inlineresult import InlineResult
        inline_results = [
            InlineResult(userbot, r, results.query_id)
            for r in results.results
        ]
        message = await inline_results[0].click(chat_id)

        # ждём inline_message_id из UpdateBotInlineSend
        imid = None
        for _ in range(25):
            await asyncio.sleep(0.2)
            imid = self._inline_sends.get(query_str)
            if imid:
                break


        # сохраняем inline_message_id для каждого token
        if imid:
            if not hasattr(self, "_inlines"):
                self._inlines: dict = {}
            for row in buttons:
                for btn in row:
                    token = btn["token"]
                    self._inlines[token] = imid

            # если в тексте есть <tg-emoji> — пересылаем через edit
            # (InputBotInlineMessageText игнорирует custom_emoji)
            if "<tg-emoji" in text:
                try:
                    result = await self.edit_inline_menu(imid, text, buttons)
                except Exception as e:
                    import traceback
        return message

    # ─── Обработчики ───
    async def _handle_inline(self, event) -> None:
        """Обработка inline-запросов от юзербота."""
        query = (event.text or "").strip()

        # ── ТЕСТ премиум emoji ──
        if query == "test_emoji":
            from telethon.tl.types import MessageEntityCustomEmoji
            text = "❤️ TETKO ❤️"
            entities = [
                MessageEntityCustomEmoji(offset=0, length=2, document_id=5282797322969852134),
                MessageEntityCustomEmoji(offset=8, length=2, document_id=5208814909273445904),
            ]
            results = [InputBotInlineResult(
                id="test",
                type="article",
                title="Test emoji",
                description="Test",
                send_message=InputBotInlineMessageText(
                    message=text,
                    entities=entities,
                ),
            )]
            await event.answer(results, cache_time=0, gallery=False)
            return
        # ── /ТЕСТ ──

        # ищем меню по ключу
        menu = self._menus.get(query)

        # чистим просроченные
        now = time.time()
        self._menus = {
            k: v for k, v in self._menus.items()
            if now - v["created"] < v["ttl"]
        }

        if menu is None:
            # дефолтный ответ
            results = [InputBotInlineResult(
                id=f"empty_{secrets.token_hex(4)}",
                type="article",
                title="TETKO",
                description=f"Меню '{query}' не найдено",
                send_message=InputBotInlineMessageText(
                    message="🫥 Меню не найдено или устарело"
                ),
            )]
            await event.answer(results, cache_time=0, gallery=False)
            return

        # строим кнопки
        rows = []
        for row in menu["buttons"]:
            kb_row = []
            for b in row:
                data = b["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                kb_row.append(KeyboardButtonCallback(text=b["label"], data=data))
            rows.append(KeyboardButtonRow(buttons=kb_row))

        markup = ReplyInlineMarkup(rows=rows) if rows else None

        # ID результата — это же key меню, чтобы юзербот знал, что выбирать
        result_id = query

        # парсим HTML в entities
        msg_text = menu["text"]
        entities = None
        try:
            parsed, entities = await self.client._parse_message_text(msg_text, "html")
            msg_text = parsed
        except Exception as e:
            log.debug(f"_handle_inline: parse failed: {e}")

        kwargs = {
            "message": msg_text,
            "reply_markup": markup,
        }

        if entities:
            kwargs["entities"] = entities

        results = [InputBotInlineResult(
            id=result_id,
            type="article",
            title="TETKO Menu",
            description=re.sub(r"<[^>]+>", "", menu["text"])[:100],
            send_message=InputBotInlineMessageText(**kwargs),
        )]

        await event.answer(results, cache_time=0, gallery=False)

    async def _handle_callback(self, event) -> None:
        """Callback от кнопок (только владелец)."""
        # ── ЗАЩИТА: только владелец ──
        sender_id = getattr(event, "sender_id", None)
        admin_id = None
        if self.kernel is not None and hasattr(self.kernel, "context"):
            admin_id = self.kernel.context.admin_id

        if admin_id is None or sender_id != admin_id:
            log.warning(f"🤖 Bot callback: отказано sender={sender_id} (owner={admin_id})")
            try:
                await event.answer("🚫 Нет доступа", alert=True)
            except Exception:
                pass
            return

        data = event.data
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")

        log.info(f"🤖 Bot callback: data={data!r}")

        if self.kernel is not None and hasattr(self.kernel, "inline"):
            h = self.kernel.inline.get_handler(data)
            if h is not None:
                try:
                    await h["func"](event, *h["args"])
                except Exception as e:
                    log.exception(f"inline handler error: {e}")
                return

        try:
            await event.answer()
        except Exception:
            pass

    async def _handle_start(self, event) -> None:
        """Обработчик /start бота."""
        if self.kernel is not None and hasattr(self.kernel, "inline"):
            handler = getattr(self.kernel.inline, "_start_handler", None)
            if handler is not None:
                try:
                    await handler(event)
                    return
                except Exception as e:
                    log.exception(f"_handle_start error: {e}")

        await event.reply(
            "👋 Я inline-бот TETKO.\n"
            "Используй .dlm через юзербот, чтобы получить меню в любом чате."
        )
