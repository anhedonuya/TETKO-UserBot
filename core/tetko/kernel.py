"""Kernel — главное ядро юзербота TETKO."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from telethon import TelegramClient, events

from core.tetko.context import Context
from core.tetko.dispatcher import EventDispatcher
from core.tetko.inline import Inline
from core.tetko.loader import ModuleLoader
from core.tetko.registry import Registry

log = logging.getLogger("TETKO.tetko.kernel")


class Kernel:
    """Ядро TETKO (tetko-compat API 0.0.9.0)."""

    def __init__(
        self,
        client: TelegramClient,
        prefix: str = ".",
        config: dict | None = None,
    ):
        self.client = client
        self.prefix = prefix
        self.config = dict(config or {})

        # Контекст ядра: admin_id, prefix, language, config, handle_error
        self.context = Context(
            admin_id=self.config.get("admin_id") or self.config.get("owner_id"),
            prefix=prefix,
            language=self.config.get("language", "ru"),
            config=self.config,
        )

        self.registry = Registry()
        self.loader = ModuleLoader(registry=self.registry, kernel=self)
        self.dispatcher = EventDispatcher(
            registry=self.registry,
            prefix=self.prefix,
            context=self.context,
        )
        self.inline = Inline(kernel=self)
        self._loop_tasks: list[asyncio.Task] = []

        # Связываем важные объекты с клиентом Telethon для быстрого доступа из модулей
        self.client.kernel = self
        self.client.loader = self.loader
        self.client.registry = self.registry
        self.client.context = self.context

    async def start(self) -> None:
        """Запуск ядра, загрузка модулей и старт событий."""
        log.info("🚀 Запуск ядра TETKO...")

        # проверяем premium у владельца
        try:
            me = await self.client.get_me()
            self.context.user_premium = False  # TEMP TEST
            log.info(f"👑 Premium: {self.context.user_premium}")
        except Exception as e:
            log.warning(f"Не удалось проверить premium: {e}")

        # 1. Загружаем модули из папки modules/
        count = await self.loader.load_all()
        log.info(f"📦 Успешно загружено модулей: {count}")

        # 2. Регистрируем обработчик входящих исходящих сообщений Telethon
        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            await self.dispatcher.handle_message(self.client, event)

        @self.client.on(events.CallbackQuery())
        async def callback_handler(event):
            await self.dispatcher.handle_callback(self.client, event)

        # 3. Запускаем фоновые задачи модулей (@loop)
        self._start_loops()

        log.info("✅ Ядро TETKO полностью инициализировано и готово!")

    def _start_loops(self) -> None:
        """Запуск фоновых периодических функций модулей."""
        for module, func, interval in self.registry.list_loops():
            async def loop_runner(m=module, f=func, i=interval):
                while True:
                    try:
                        await f()
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        log.error(f"Ошибка в фоновом цикле модуля {m.name}: {e}")
                    await asyncio.sleep(i)

            task = asyncio.create_task(loop_runner())
            self._loop_tasks.append(task)

    async def stop(self) -> None:
        """Остановка ядра и корректная выгрузка модулей."""
        log.info("🛑 Остановка ядра TETKO...")

        # Отменяем фоновые задачи и ждём их завершения
        for task in self._loop_tasks:
            task.cancel()
        if self._loop_tasks:
            await asyncio.gather(*self._loop_tasks, return_exceptions=True)
        self._loop_tasks.clear()

        # Выгружаем модули
        for mod_name in list(self.registry.list_modules().keys()):
            await self.loader.unload_module(mod_name)

        log.info("👋 Ядро TETKO остановлено.")
