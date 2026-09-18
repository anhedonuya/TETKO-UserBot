"""Kernel — главное ядро юзербота TETKO."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from telethon import TelegramClient, events

from core.tetko.dispatcher import EventDispatcher
from core.tetko.loader import ModuleLoader
from core.tetko.registry import Registry

log = logging.getLogger("TETKO.tetko.kernel")


class Kernel:
    """Ядро TETKO-COMPAT 0.0.9.0."""

    def __init__(
        self,
        client: TelegramClient,
        prefix: str = ".",
    ):
        self.client = client
        self.prefix = prefix
        self.registry = Registry()
        self.loader = ModuleLoader(registry=self.registry, kernel=self)
        self.dispatcher = EventDispatcher(registry=self.registry, prefix=self.prefix)
        self._loop_tasks: list[asyncio.Task] = []

        # Связываем важные объекты с клиентом Telethon для быстрого доступа из модулей
        self.client.kernel = self
        self.client.loader = self.loader
        self.client.registry = self.registry

    async def start(self) -> None:
        """Запуск ядра, загрузка модулей и старт событий."""
        log.info("🚀 Запуск ядра TETKO-COMPAT...")

        # 1. Загружаем модули из папки modules/
        count = await self.loader.load_all()
        log.info(f"📦 Успешно загружено модулей: {count}")

        # 2. Регистрируем обработчик входящих исходящих сообщений Telethon
        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            await self.dispatcher.handle_message(self.client, event)

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
