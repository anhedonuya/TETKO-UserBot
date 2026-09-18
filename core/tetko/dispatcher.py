"""Dispatcher — обработчик входящих событий Telegram для TETKO."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from core.tetko.registry import Registry

log = logging.getLogger("TETKO.tetko.dispatcher")


class EventDispatcher:
    """Диспетчер команд, ватчеров и колбэков."""

    def __init__(self, registry: Registry, prefix: str = "."):
        self.registry = registry
        self.prefix = prefix

    async def handle_message(self, client: Any, event: Any) -> None:
        """Обработка входящих сообщений Telegram."""
        text = getattr(event, "raw_text", "") or ""

        # 1. Парсинг и вызов команды
        if text.startswith(self.prefix):
            parts = text[len(self.prefix):].split(maxsplit=1)
            if parts:
                cmd_name = parts[0].lower()
                cmd_args = parts[1].split() if len(parts) > 1 else []

                command = self.registry.find_command(cmd_name)
                if command:
                    try:
                        if hasattr(command.module, "client"):
                            command.module.client = client

                        match_str = text[len(self.prefix) + len(cmd_name):].strip()
                        event.pattern_match = re.search(r"(.*)", match_str)

                        await command.call(client, event, cmd_args)
                        return
                    except Exception as e:
                        log.error(f"Ошибка выполнения команды .{cmd_name}: {e}")
                        await event.edit(f"❌ Ошибка в команде `.{cmd_name}`:\n`{e}`")
                        return

        # 2. Вызов ватчеров (watchers)
        for module, watcher_func in self.registry.list_watchers():
            try:
                await watcher_func(event)
            except Exception as e:
                log.error(f"Ошибка ватчера в модуле {module.name}: {e}")
