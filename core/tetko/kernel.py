"""Kernel — главное ядро юзербота TETKO."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from telethon import TelegramClient, events

from core.tetko.context import Context
from core.tetko.dispatcher import EventDispatcher
# MCUB-compat: используем полноценный InlineHandlers и InlineBot
try:
    from core_inline.handlers import InlineHandlers
except Exception as _e:
    InlineHandlers = None
try:
    from core_inline.bot import InlineBot
except Exception as _e:
    InlineBot = None
# Fallback на старый tetko Inline
from core.tetko.inline import Inline as _TetkoInline
from core.tetko.loader import ModuleLoader
from core.tetko.registry import Registry

log = logging.getLogger("TETKO.tetko.kernel")



    async def setup_mcub_inline(self):
        """Подключить MCUB InlineBot + InlineHandlers к ядру."""
        if InlineBot is None or InlineHandlers is None:
            import logging
            logging.getLogger("TETKO.tetko.kernel").warning(
                "MCUB core_inline недоступен, остаёмся на старом Inline"
            )
            return

        import logging
        log = logging.getLogger("TETKO.tetko.kernel")

        token = (self.config or {}).get("inline_bot_token")
        if not token:
            log.warning("inline_bot_token не задан — MCUB inline не стартует")
            return

        try:
            bot_manager = InlineBot(self)
            await bot_manager.setup()
            self._mcub_inline_bot = bot_manager

            bot_client = getattr(bot_manager, "bot_client", None)
            if bot_client is None:
                log.warning("InlineBot не создал bot_client")
                return

            handlers = InlineHandlers(self, bot_client)
            self._mcub_inline_handlers = handlers

            self.bot_client = bot_client
            self.inline_bot = bot_manager

            await handlers.register_handlers()
            log.info("MCUB inline запущен, bot_client=%s", type(bot_client).__name__)
        except Exception as e:
            log.exception(f"Не удалось запустить MCUB inline: {e}")


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
        # Старый inline для обратной совместимости
        self.inline = _TetkoInline(kernel=self)
        # MCUB InlineHandlers подключается после старта bot_client
        self._mcub_inline_handlers = None
        self._mcub_inline_bot = None
        # Ссылка на inline_callback_map (для make_cb_button и InlineHandlers)
        if not hasattr(self, "inline_callback_map"):
            self.inline_callback_map = {}
        if not hasattr(self, "_inline_cb_lock"):
            import threading as _th
            self._inline_cb_lock = _th.Lock()
        self._loop_tasks: list[asyncio.Task] = []

        # лог-чат
        self.log_chat_id = self.config.get("log_chat_id") or None

        # Связываем важные объекты с клиентом Telethon для быстрого доступа из модулей
        self.client.kernel = self
        self.client.loader = self.loader
        self.client.registry = self.registry
        self.client.context = self.context

    async def start(self) -> None:
        """Запуск ядра, загрузка модулей и старт событий."""
        log.info("🚀 Запуск ядра TETKO...")
        # MCUB inline (bot + InlineHandlers)
        await self.setup_mcub_inline()

        # проверяем premium у владельца
        try:
            me = await self.client.get_me()
            self.context.user_premium = bool(getattr(me, "premium", False))
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

    async def log_to_chat(self, text: str):
        """Отправить сообщение в log_chat_id (если задан)."""
        if not self.log_chat_id:
            return
        try:
            await self.client.send_message(
                self.log_chat_id,
                text,
                parse_mode="html",
            )
        except Exception as e:
            log.warning(f"log_to_chat failed: {e}")
