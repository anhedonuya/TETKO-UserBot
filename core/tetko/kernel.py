"""Kernel — главное ядро юзербота TETKO."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from telethon import TelegramClient, events

from core.tetko import ui
from core.tetko.context import Context
from core.tetko.dispatcher import EventDispatcher
try:
    from core_inline.handlers import InlineHandlers
except Exception as _e:
    InlineHandlers = None
try:
    from core_inline.bot import InlineBot
except Exception as _e:
    InlineBot = None
from core.tetko.inline import Inline as _TetkoInline
from core.tetko.loader import ModuleLoader
from core.tetko.registry import Registry

log = logging.getLogger("TETKO.tetko.kernel")





class _DummyCallbackPermissions:
    def allow(self, uid, command="", duration_seconds=60):
        pass

    def prohibit(self, uid):
        pass

    def is_allowed(self, uid, command="", duration_seconds=60):
        return False

class Kernel:
    """Ядро TETKO (tetko-compat API 0.0.9.0)."""

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

            if getattr(self, "bot_client", None) is None:
                self.bot_client = bot_client
            else:
                log.info("setup_mcub_inline: сохраняем существующий bot_client=%s",
                         type(self.bot_client).__name__)
            self.inline_bot = bot_manager

            await handlers.register_handlers()
            log.info("MCUB inline запущен, bot_client=%s", type(bot_client).__name__)
        except Exception as e:
            log.exception(f"Не удалось запустить MCUB inline: {e}")


    def __init__(
        self,
        client: TelegramClient,
        prefix: str = ".",
        config: dict | None = None,
    ):
        self.client = client
        self.config = dict(config or {})
        self.prefix = (
            self.config.get("command_prefix")
            or prefix
            or "."
        )
        self.log_chat_id = self.config.get("log_chat_id") or None
        self.bot_command_handlers = {}
        self.premium_user = False
        self.user_premium = False
        self.command_handlers = {}
        self.inline_handlers = {}
        self.callback_permissions = _DummyCallbackPermissions()

        self.logger = log
        self.CONFIG_FILE = "config.json"
        self.API_ID = int(self.config.get("api_id") or 0)
        self.API_HASH = str(self.config.get("api_hash") or "")
        self.current_loading_module = None
        self.current_loading_module_type = None
        self.callback_handlers = {}
        self.inline_handlers_owners = {}
        self.command_owners = {}
        self.bot_command_owners = {}
        self._module_commands_index = {}
        self._live_module_configs = {}
        self.start_time = time.time()

        self.context = Context(
            admin_id=self.config.get("admin_id") or self.config.get("owner_id"),
            prefix=self.prefix,
            language=self.config.get("language", "ru"),
            config=self.config,
        )
        self._ensure_global_config()

        self.registry = Registry()
        self.loader = ModuleLoader(registry=self.registry, kernel=self)
        self.dispatcher = EventDispatcher(
            registry=self.registry,
            prefix=self.prefix,
            context=self.context,
        )
        self.inline = _TetkoInline(kernel=self)
        from core.tetko.inline_manager import InlineManager as _InlineManager
        self.inline_manager = _InlineManager(self)
        self._mcub_inline_handlers = None
        self._mcub_inline_bot = None
        if not hasattr(self, "inline_callback_map"):
            self.inline_callback_map = {}
        if not hasattr(self, "_inline_cb_lock"):
            import threading as _th
            self._inline_cb_lock = _th.Lock()
        self._loop_tasks: list[asyncio.Task] = []
        self.client.kernel = self
        self.client.loader = self.loader
        self.client.registry = self.registry
        self.client.context = self.context

    def _register_shell_everywhere(self):
        """Зарегистрировать self во всех копиях core.tetko.shell в sys.modules."""
        import sys as _sys
        _seen = set()
        _candidates = []

        # 1. Прямой импорт
        try:
            from core.tetko import shell as _sh_main
            _candidates.append(_sh_main)
        except Exception:
            pass

        # 2. Все модули в sys.modules с именем core.tetko.shell или shell
        for _m in list(_sys.modules.values()):
            if _m is None:
                continue
            _n = getattr(_m, "__name__", "")
            if _n in ("core.tetko.shell", "core.tetko.shell"):
                _candidates.append(_m)

        for _sh in _candidates:
            if id(_sh) in _seen:
                continue
            _seen.add(id(_sh))
            try:
                if hasattr(_sh, "_KERNEL"):
                    _sh._KERNEL = self
                if hasattr(_sh, "set_kernel"):
                    _sh.set_kernel(self)
            except Exception:
                pass

        return len(_seen)


    def get_prefix_for_sender(self, uid):
        return self.prefix

    async def start(self) -> None:
        """Запуск ядра, загрузка модулей и старт событий."""
        t0 = time.time()
        ui.collect("Preparing kernel")
        try:
            me = await self.client.get_me()

            try:

                _u = getattr(me, 'username', None) or getattr(me, 'first_name', None) or str(getattr(me, 'id', 'user'))

                self.context.user_username = str(_u)

            except Exception:

                pass
            self._register_shell_everywhere()
            self.context.user_premium = bool(getattr(me, "premium", False))
            ui.item("owner: " + str(getattr(me, "id", "?")))
            ui.item("premium: " + str(self.context.user_premium).lower())
        except Exception as e:
            ui.item("get_me failed: " + str(e), "warn")

        await self.loader.load_all()

        ui.collect("Installing")
        ui.item(
            str(self.registry.modules_count) + " modules, "
            + str(self.registry.commands_count) + " commands, "
            + str(len(self.registry.list_watchers())) + " watchers, "
            + str(len(self.registry.list_loops())) + " loops"
        )

        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            await self.dispatcher.handle_message(self.client, event)

        @self.client.on(events.NewMessage(incoming=True))
        async def message_handler_incoming(event):
            await self.dispatcher.handle_message(self.client, event)

        @self.client.on(events.CallbackQuery())
        async def callback_handler(event):
            await self.dispatcher.handle_callback(self.client, event)

        @self.client.on(events.NewMessage(outgoing=True))
        async def _cfg_deliver_watcher(event):
            """Удаляет эфемерные сообщения после inline-cfg-edit."""
            txt = (getattr(event, "raw_text", "") or "").strip()
            if not txt.startswith("✅ Изменения доставлены в инлайн"):
                return
            import asyncio as _aio
            async def _later():
                await _aio.sleep(1.5)
                try:
                    await event.delete()
                except Exception:
                    pass
            _aio.create_task(_later())

        self._start_loops()

        ui.done("Successfully loaded in " + ("%.2f" % (time.time() - t0)) + "s.")

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

        for task in self._loop_tasks:
            task.cancel()
        if self._loop_tasks:
            await asyncio.gather(*self._loop_tasks, return_exceptions=True)
        self._loop_tasks.clear()

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

    GLOBAL_CONFIG_DEFAULTS = {
        "shell_prompt": "%",
        "shell_host": "tetko",
        "message_delete_delay": 0,
        "command_cooldown": 0,
        "verbose_errors": False,
        "log_chat_id": None,
    }

    def _ensure_global_config(self):
        import json
        from pathlib import Path
        d = Path("data/tetko_config")
        d.mkdir(parents=True, exist_ok=True)
        p = d / "__global__.json"
        if not p.exists():
            p.write_text(
                json.dumps(self.GLOBAL_CONFIG_DEFAULTS, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            changed = False
            for k, v in self.GLOBAL_CONFIG_DEFAULTS.items():
                if k not in data:
                    data[k] = v
                    changed = True
            if changed:
                p.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
        except Exception:
            pass
