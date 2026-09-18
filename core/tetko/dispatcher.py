"""Dispatcher — обработчик входящих событий Telegram для TETKO."""
from __future__ import annotations

import logging
from typing import Any

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

        # 1. Команды (начинаются с префикса)
        if text.startswith(self.prefix):
            body = text[len(self.prefix):]
            parts = body.split(maxsplit=1)
            if parts:
                cmd_name = parts[0].lower()
                cmd_args = parts[1].split() if len(parts) > 1 else []

                command = self.registry.find_command(cmd_name)
                if command:
                    try:
                        # Прокидываем client в модуль (некоторые модули его ждут)
                        if hasattr(command.module, "client"):
                            try:
                                command.module.client = client
                            except Exception:
                                pass

                        await command.call(client, event, cmd_args)
                    except Exception as e:
                        log.exception(f"Ошибка выполнения команды .{cmd_name}")
                        try:
                            await event.edit(
                                f"❌ Ошибка в команде `.{cmd_name}`:\n`{e}`"
                            )
                        except Exception:
                            pass
                    return

        # 2. Watchers (реакция на все сообщения)
        for module, watcher_func in self.registry.list_watchers():
            try:
                await watcher_func(event)
            except Exception as e:
                log.exception(f"Ошибка ватчера в модуле {module.name}: {e}")

    async def handle_callback(self, client: Any, event: Any) -> None:
        """Обработка inline-кнопок (callback query)."""
        data = getattr(event, "data", b"") or b""
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")

        for module, callback_func in self.registry.list_callbacks():
            try:
                await callback_func(event)
            except Exception as e:
                log.exception(f"Ошибка callback в модуле {module.name}: {e}")
