"""LogHandler — пересылка важных логов в Telegram-чат через бота."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

log = logging.getLogger("TETKO.tetko.log_handler")


class TelegramLogHandler(logging.Handler):
    LEVELS = (logging.ERROR, logging.WARNING, logging.CRITICAL)
    SKIP_LOGGERS = (
        "TETKO.tetko.log_handler",
        "telethon",
        "asyncio",
        "aiohttp",
    )
    FLOOD_WINDOW = 5.0

    def __init__(self, kernel):
        super().__init__(level=logging.WARNING)
        self.kernel = kernel
        self._loop = None
        self._last = defaultdict(float)

    def set_loop(self, loop):
        self._loop = loop

    def emit(self, record):
        if record.levelno not in self.LEVELS:
            return
        if any(record.name.startswith(s) for s in self.SKIP_LOGGERS):
            return

        chat_id = getattr(self.kernel, "log_chat_id", None)
        bot = getattr(self.kernel, "bot_client", None)
        if not chat_id or bot is None:
            return

        key = record.name + ":" + str(record.levelno)
        now = time.time()
        if now - self._last[key] < self.FLOOD_WINDOW:
            return
        self._last[key] = now

        try:
            text = self._format(record)
        except Exception:
            return

        try:
            loop = self._loop or asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._send(bot, chat_id, text), loop,
                )
        except Exception as e:
            log.debug("log_handler dispatch failed: " + str(e))

    async def _send(self, bot, chat_id, text):
        try:
            await bot.client.send_message(chat_id, text, parse_mode="html")
        except Exception as e:
            log.debug("log_handler send failed: " + str(e))

    def _format(self, record):
        lvl = record.levelname
        name = record.name
        msg = record.getMessage()
        exc = ""
        if record.exc_info:
            import traceback
            tb = "".join(traceback.format_exception(*record.exc_info))
            exc = "\n<pre>" + _esc(tb[-1500:]) + "</pre>"
        icons = {"ERROR": "❌", "WARNING": "⚠️", "CRITICAL": "🔥"}
        icon = icons.get(lvl, "•")
        header = f"{icon} <b>{lvl}</b> <code>{_esc(name)}</code>"
        body = "<blockquote>" + _esc(msg[:1000]) + "</blockquote>"
        return header + "\n" + body + exc


def _esc(t):
    if t is None:
        return ""
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
