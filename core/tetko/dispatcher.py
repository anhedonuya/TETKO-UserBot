"""Dispatcher — вызов TETKO-команд."""
from __future__ import annotations

import logging
import traceback
from typing import Any

from telethon import events

from core.tetko.registry import Registry

log = logging.getLogger("TETKO.tetko.dispatcher")


class Dispatcher:
    """Диспетчер событий TETKO: парсит сообщения и вызывает команды."""

    def __init__(self, client, registry: Registry, prefix: str = "."):
        self.client = client
        self.registry = registry
        self.prefix = prefix
        self._started = False

    async def start(self) -> None:
        """Зарегистрировать обработчик событий."""
        if self._started:
            log.warning("[dispatcher] уже запущен")
            return

        @self.client.on(events.NewMessage(outgoing=True))
        async def _handler(event):
            try:
                await self.handle(event)
            except Exception as e:
                log.error(f"[dispatcher] ошибка в handle: {e}")
                log.error(traceback.format_exc())

        self._started = True
        log.info(f"[dispatcher] обработчик запущен (prefix={self.prefix!r})")

    async def stop(self) -> None:
        """Заглушка."""
        self._started = False

    async def handle(self, event) -> None:
        """Обработать входящее сообщение."""
        text = event.raw_text or ""
        prefix = self.prefix

        if not text.startswith(prefix):
            return

        body = text[len(prefix):].strip()
        if not body:
            return

        parts = body.split()
        cmd_name = parts[0].lower()
        args = parts[1:]

        cmd = self.registry.find_command(cmd_name)
        if cmd is None:
            return

        log.debug(f"[dispatcher] .{cmd_name} → {cmd.module.name}")

        try:
            await cmd.call(self.client, event, args)
        except Exception as e:
            log.error(f"[!] Ошибка в .{cmd_name}: {e}")
            log.error(traceback.format_exc())
            try:
                await event.edit(f"❌ Ошибка: {e}")
            except Exception:
                pass
