"""Реальный MCUB ModuleBase поверх tetko.

Собирает декораторы из `@loader.command/watcher/loop/callback/...` через
`__init_subclass__`, а в `__init__` регистрирует всё через `kernel.register.*`.
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Optional

log = logging.getLogger("TETKO.mcub_compat.module_base")

from .module_config import ModuleConfig


class _ModuleLogger:
    def __init__(self, name):
        self._logger = logging.getLogger(f"MCUB.module.{name}")
    def debug(self, msg, *a, **kw): self._logger.debug(msg, *a, **kw)
    def info(self, msg, *a, **kw): self._logger.info(msg, *a, **kw)
    def warning(self, msg, *a, **kw): self._logger.warning(msg, *a, **kw)
    def error(self, msg, *a, **kw): self._logger.error(msg, *a, **kw)
    def exception(self, msg, *a, **kw): self._logger.exception(msg, *a, **kw)


class _DictStrings:
    def __init__(self, data): self._data = data or {}
    def __call__(self, key, **kw):
        v = self._data.get(key, f"[{key}]")
        if kw and isinstance(v, str):
            try: return v.format(**kw)
            except Exception: return v
        return v
    def __getitem__(self, key): return self._data[key]
    def get(self, key, default=None): return self._data.get(key, default)
    def has(self, key): return key in self._data
    def keys(self): return set(self._data.keys())


class _EmptyStrings:
    def __call__(self, key, **kw): return f"[{key}]"
    def __getitem__(self, key): return f"[{key}]"
    def get(self, key, default=None): return default or f"[{key}]"
    def has(self, key): return False
    def keys(self): return set()


class _EmptyConfig:
    def get(self, key, default=None): return default
    def set(self, key, value): return None
    def all(self): return {}
    def __getitem__(self, key): raise KeyError(key)
    def __setitem__(self, key, value): pass
    def __contains__(self, key): return False


class _ArgsShim:
    def __init__(self, raw):
        self._raw = raw or ""
        self.args = self._raw.split() if self._raw else []
        self.kwargs = {}
        self.flags = set()
    def get(self, index, default=None):
        try: return self.args[index]
        except IndexError: return default
    def get_flag(self, flag): return flag in self.flags
    def get_kwarg(self, key, default=None): return self.kwargs.get(key, default)
    def has(self, key): return key in self.kwargs
    def join_args(self, start=0, end=None):
        return " ".join(str(a) for a in self.args[start:end])
    def __len__(self): return len(self.args)
    def __getitem__(self, i): return self.args[i]
    def __iter__(self): return iter(self.args)


class _ButtonFactoryStub:
    """Фабрика кнопок в стиле MCUB (Button.copy, Button.inline, ...)."""

    def __init__(self, module=None):
        self._module = module

    def _make_callback_data(self, callback):
        """Создаёт токен для callback-кнопки и регистрирует handler."""
        import secrets, time
        token = secrets.token_hex(8)
        if self._module is not None:
            kernel = getattr(self._module, "kernel", None)
            if kernel is not None:
                register = getattr(self._module, "_register", None)
                if register is not None:
                    cb_map = getattr(kernel, "inline_callback_map", None)
                    if cb_map is None:
                        kernel.inline_callback_map = {}
                        cb_map = kernel.inline_callback_map
                    cb_map[token] = {
                        "handler": callback,
                        "module": self._module,
                        "expires_at": time.time() + 900,
                    }
        return token.encode() if isinstance(token, str) else token

    def inline(self, text, callback, style=None, **kw):
        """Inline callback-кнопка (TETKO-формат: dict)."""
        kernel = getattr(self._module, "kernel", None) if self._module else None
        inline = getattr(kernel, "inline", None) if kernel else None
        if inline is not None and hasattr(inline, "make_button"):
            async def _wrapped(ev, *a, **k):
                return await callback(ev)
            token = inline.register_handler(_wrapped, [], 600)
            return {"label": str(text or "·"), "token": token, "style": style or "primary"}
        from telethon.tl.types import KeyboardButtonCallback
        data = self._make_callback_data(callback)
        return KeyboardButtonCallback(text=str(text), data=data)

    def url(self, text, url, **kw):
        from telethon.tl.custom import Button
        return Button.url(str(text), str(url))

    def text(self, text, **kw):
        """Простая текстовая кнопка (в inline не работает, но вернём как есть)."""
        from telethon.tl.types import KeyboardButton
        return KeyboardButton(text=str(text))

    def switch(self, text, query="", **kw):
        from telethon.tl.types import KeyboardButtonSwitchInline
        return KeyboardButtonSwitchInline(text=str(text), query=str(query))

    def input(self, text, placeholder="", **kw):
        from telethon.tl.types import KeyboardButtonRequestPhone
        # input не поддерживается в inline, вернём обычную кнопку
        from telethon.tl.types import KeyboardButton
        return KeyboardButton(text=str(text))

    def close(self, text="Закрыть", **kw):
        """Кнопка 'закрыть' — отправит callback с data='close'."""
        from telethon.tl.types import KeyboardButtonCallback
        return KeyboardButtonCallback(text=str(text), data=b"close")

    def copy(self, text, copy_text, **kw):
        """Кнопка 'скопировать текст'."""
        from telethon.tl.types import KeyboardButtonCopy
        return KeyboardButtonCopy(text=str(text), copy_text=str(copy_text))


class MCUBModuleBase:
    """Базовый класс MCUB-модуля."""

    name = "Unnamed"
    version = "0.0.0"
    author = "unknown"
    description = {}
    dependencies = []
    banner_url = None
    strings = {}
    config = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        registry = {
            "commands": [],
            "watchers": [],
            "callbacks": [],
            "loops": [],
            "bot_commands": [],
            "inlines": [],
            "events": [],
        }
        for attr_name, attr in cls.__dict__.items():
            if not callable(attr):
                continue
            for pattern, kw in getattr(attr, "_mcub_commands", []):
                registry["commands"].append((pattern, kw, attr_name))
            for kw in getattr(attr, "_mcub_watchers", []):
                registry["watchers"].append((kw, attr_name))
            for kw in getattr(attr, "_mcub_callbacks", []):
                registry["callbacks"].append((kw, attr_name))
            for kw in getattr(attr, "_mcub_loops", []):
                registry["loops"].append((kw, attr_name))
            for pattern, kw in getattr(attr, "_mcub_bot_commands", []):
                registry["bot_commands"].append((pattern, kw, attr_name))
            for pattern, kw in getattr(attr, "_mcub_inline", []):
                registry["inlines"].append((pattern, kw, attr_name))
            for ev_type, ev_args, ev_kw in getattr(attr, "_mcub_events", []):
                registry["events"].append((ev_type, ev_args, ev_kw, attr_name))

        cls._mcub_registry = registry

    @staticmethod
    def _normalize_kwargs(kwargs: dict) -> dict:
        """MCUB → Telethon: конвертируем Bot API kwargs."""
        if "disable_web_page_preview" in kwargs:
            dwp = kwargs.pop("disable_web_page_preview")
            if "link_preview" not in kwargs:
                kwargs["link_preview"] = not dwp  # True → превью off
        if "disable_notification" in kwargs:
            dn = kwargs.pop("disable_notification")
            if "silent" not in kwargs:
                kwargs["silent"] = dn
        if "parse_mode" in kwargs and kwargs["parse_mode"] is None:
            kwargs.pop("parse_mode")
        return kwargs

    def __init__(self, kernel=None, client=None, register=None):
        self.kernel = kernel
        self.client = client
        self._register = register or getattr(kernel, "register", None)
        self.log = _ModuleLogger(getattr(self, "name", type(self).__name__))
        self._loaded = False
        self.cache = getattr(kernel, "cache", None)
        self.db = _ModuleDB(self)  # объект с .get/.set/.delete/.query
        self.translator = _EmptyTranslator()  # i18n

        self._config_obj = None
        cls_cfg = getattr(type(self), "config", None)
        if isinstance(cls_cfg, ModuleConfig):
            self._config_obj = cls_cfg
            try:
                self._config_obj.bind_owner(self)
            except Exception:
                pass

        try:
            self._auto_register()
        except Exception as e:
            log.warning(f"[{getattr(self, 'name', '?')}] auto-register: {e}")

        if self._config_obj is not None:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._load_config_async())
            except Exception:
                pass

    async def _load_config_async(self):
        """Загружает ModuleConfig из БД (fire-and-forget)."""
        try:
            await self._config_obj.load_from_db(self)
        except Exception as e:
            log.warning(f"load_config({self.name}): {e}")

    def _auto_register(self):
        registry = getattr(type(self), "_mcub_registry", None)
        if not registry:
            return
        kr = getattr(self.kernel, "register", None)
        if kr is None:
            return

        for pattern, kw, attr_name in registry.get("commands", []):
            bound = getattr(self, attr_name)
            kr.command(pattern, **kw)(bound)

        for kw, attr_name in registry.get("watchers", []):
            bound = getattr(self, attr_name)
            kr.watcher(**kw)(bound)

        for kw, attr_name in registry.get("callbacks", []):
            bound = getattr(self, attr_name)
            try:
                kr.callback(**kw)(bound)
            except Exception:
                pass

        for kw, attr_name in registry.get("loops", []):
            bound = getattr(self, attr_name)
            kr.loop(**kw)(bound)

        for pattern, kw, attr_name in registry.get("bot_commands", []):
            bound = getattr(self, attr_name)
            try:
                kr.bot_command(pattern, **kw)(bound)
            except Exception:
                pass

        for pattern, kw, attr_name in registry.get("inlines", []):
            bound = getattr(self, attr_name)
            try:
                kr.event("inlinequery", pattern=pattern, **kw)(bound)
            except Exception:
                pass

        for ev_type, ev_args, ev_kw, attr_name in registry.get("events", []):
            bound = getattr(self, attr_name)
            try:
                kr.event(ev_type, *ev_args, **ev_kw)(bound)
            except Exception:
                pass

    def _get_strings(self):
        data = getattr(type(self), "strings", None) or {}
        if not data:
            return _EmptyStrings()
        if "name" in data:
            return _DictStrings(data)
        lang = "ru"
        try: lang = self.get_lang() or "ru"
        except Exception: pass
        active = data.get(lang) or data.get("en") or next(iter(data.values()), {})
        return _DictStrings(active)

    def _get_config(self):
        cfg = object.__getattribute__(self, "_config_obj") if "_config_obj" in object.__getattribute__(self, "__dict__") else None
        if cfg is not None:
            return cfg
        return _EmptyConfig()

    async def save_config(self):
        """Сохраняет ModuleConfig в БД."""
        cfg = self._config_obj
        if cfg is None:
            return
        try:
            await cfg.save_to_db(self)
        except Exception as e:
            log.warning(f"save_config({self.name}): {e}")

    def get_prefix(self):
        k = self.kernel
        return getattr(k, "custom_prefix", ".") if k else "."

    def get_lang(self):
        k = self.kernel
        cfg = getattr(k, "config", None) if k else None
        if isinstance(cfg, dict): return cfg.get("language", "ru") or "ru"
        return "ru"

    def args_raw(self, event):
        text = getattr(event, "raw_text", "") or ""
        prefix = self.get_prefix()
        if text.startswith(prefix):
            parts = text[len(prefix):].split(maxsplit=1)
            return parts[1] if len(parts) > 1 else ""
        return ""

    def args(self, event): return _ArgsShim(self.args_raw(event))
    def args_html(self, event): return self.args_raw(event)

    async def edit(self, event, text, **kwargs):
        as_html = kwargs.pop("as_html", False)
        reply_markup = kwargs.pop("reply_markup", None)
        if reply_markup is not None:
            kwargs["buttons"] = reply_markup
        if as_html and "parse_mode" not in kwargs:
            kwargs["parse_mode"] = "html"
        kwargs = self._normalize_kwargs(kwargs)
        return await event.edit(text, **kwargs)

    async def answer(self, event, text, **kwargs):
        as_html = kwargs.pop("as_html", False)
        if as_html and "parse_mode" not in kwargs:
            kwargs["parse_mode"] = "html"
        kwargs = self._normalize_kwargs(kwargs)
        return await event.reply(text, **kwargs)

    async def reply(self, event, text, **kwargs):
        return await self.answer(event, text, **kwargs)

    async def invoke(self, command, args=None, chat_id=None, reply_to=None):
        if self.kernel is not None and hasattr(self.kernel, "register"):
            return await self.kernel.register.invoke(command, args, chat_id, reply_to)
        return None

    async def inline(self, chat_id, title, fields=None, buttons=None, auto_send=True,
                     ttl=200, reply_to=None, **kwargs):
        log.warning("inline() пока не реализован (этап 4)")
        return (False, None)

    def lookup_module(self, module_name, *, all_loaded=False):
        k = self.kernel
        if k is not None and hasattr(k, "lookup_module"):
            return k.lookup_module(module_name, all_loaded=all_loaded)
        return None

    def require_module(self, module_name, *, all_loaded=False):
        mod = self.lookup_module(module_name, all_loaded=all_loaded)
        if mod is None:
            raise LookupError(f"Required module '{module_name}' is not loaded")
        return mod

    def lookup(self, module_name, *, all_loaded=False):
        """Алиас для MCUB: self.lookup("name")."""
        return self.lookup_module(module_name, all_loaded=all_loaded)

    def require(self, module_name, *, all_loaded=False):
        """Алиас для MCUB: self.require("name")."""
        return self.require_module(module_name, all_loaded=all_loaded)

    @property
    def bot(self):
        """Telegram-бот (BotClient) для отправки inline."""
        k = self.kernel
        if k is not None:
            return getattr(k, "bot_client", None)
        return None

    async def db_get(self, key, default=None):
        """Короткая обёртка: self.db_get("key")."""
        return await self.db.get(key, default)

    async def db_set(self, key, value):
        """Короткая обёртка: self.db_set("key", value)."""
        return await self.db.set(key, value)

    async def db_del(self, key):
        """Короткая обёртка: self.db_del("key")."""
        return await self.db.delete(key)

    async def import_lib(self, url, *, name=None):
        import sys, types, urllib.request
        if name is None:
            name = url.split("/")[-1]
            if name.endswith(".py"): name = name[:-3]
        with urllib.request.urlopen(url) as resp:
            code = resp.read().decode("utf-8")
        module = types.ModuleType(name)
        sys.modules[name] = module
        exec(code, module.__dict__)
        return module

    @property
    def Button(self):
        if not hasattr(self, "_btn_factory") or self._btn_factory is None:
            self._btn_factory = _ButtonFactoryStub(self)
        return self._btn_factory

    async def on_load(self):
        self._loaded = True
        reg = getattr(self.kernel, "register", None)
        if reg is not None:
            try:
                from .register_shim import run_autostart_loops
                run_autostart_loops(reg)
            except Exception as e:
                log.warning(f"autostart loops: {e}")
            if getattr(reg, "_on_load_fn", None):
                try:
                    result = reg._on_load_fn(self.kernel)
                    if inspect.isawaitable(result): await result
                except Exception as e:
                    log.warning(f"on_load hook: {e}")

    async def on_unload(self):
        reg = getattr(self.kernel, "register", None)
        if reg is not None:
            try:
                from .register_shim import stop_all_loops
                stop_all_loops(reg)
            except Exception: pass
            if getattr(reg, "_uninstall_fn", None):
                try:
                    result = reg._uninstall_fn(self.kernel)
                    if inspect.isawaitable(result): await result
                except Exception as e:
                    log.warning(f"uninstall hook: {e}")
        self._loaded = False

    @property
    def subinline(self):
        """MCUB-совместимый subinline: фасад над ботом/юзерботом.

        Примеры:
            await self.subinline.rich_form(event, "<blockquote>Привет</blockquote>")
            await self.subinline.form(chat_id, "Заголовок", buttons=[[btn]])
            await self.subinline.send(chat_id, "текст")
        """
        if not hasattr(self, "_subinline") or self._subinline is None:
            self._subinline = _SubInline(self)
        return self._subinline


    def __getattribute__(self, name):
        if name == "config":
            try: return object.__getattribute__(self, "_get_config")()
            except AttributeError: pass
        if name == "strings":
            try: return object.__getattribute__(self, "_get_strings")()
            except AttributeError: pass
        return object.__getattribute__(self, name)



def command(pattern, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_commands", []))
        meta.append((pattern, kwargs))
        fn._mcub_commands = meta
        return fn
    return deco


def watcher(*args, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_watchers", []))
        meta.append(kwargs)
        fn._mcub_watchers = meta
        return fn
    if args and callable(args[0]) and not kwargs:
        return deco(args[0])
    return deco


def callback(*args, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_callbacks", []))
        meta.append(kwargs)
        fn._mcub_callbacks = meta
        return fn
    if args and callable(args[0]) and not kwargs:
        return deco(args[0])
    return deco


def loop(*args, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_loops", []))
        meta.append(kwargs)
        fn._mcub_loops = meta
        return fn
    if args and callable(args[0]) and not kwargs:
        return deco(args[0])
    return deco


def bot_command(pattern, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_bot_commands", []))
        meta.append((pattern, kwargs))
        fn._mcub_bot_commands = meta
        return fn
    return deco


def event(event_type, *args, bot_client=False, **kwargs):
    """MCUB-декоратор @event — регистрирует обработчик события."""
    def deco(fn):
        meta = list(getattr(fn, "_mcub_events", []))
        meta.append((event_type, args, kwargs))
        fn._mcub_events = meta
        return fn
    return deco


def inline(pattern, **kwargs):
    def deco(fn):
        meta = list(getattr(fn, "_mcub_inline", []))
        meta.append((pattern, kwargs))
        fn._mcub_inline = meta
        return fn
    return deco


__all__ = ["MCUBModuleBase", "command", "watcher", "callback", "loop", "bot_command", "inline", "event"]




class _ModuleDB:
    """MCUB-совместимая обёртка над kernel.db_* для модуля."""

    def __init__(self, module):
        self._module = module
        self._ns = getattr(module, "name", "unnamed")

    async def get(self, key, default=None):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return default
        try:
            return await k.db_get(self._ns, key, default)
        except Exception:
            return default

    async def set(self, key, value):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return None
        try:
            return await k.db_set(self._ns, key, value)
        except Exception:
            return None

    async def delete(self, key):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return None
        try:
            return await k.db_delete(self._ns, key)
        except Exception:
            return None

    async def query(self, sql, params=None):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return None
        try:
            return await k.db_query(sql, params)
        except Exception:
            return None

    async def db_get(self, namespace, key, default=None):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return default
        try:
            return await k.db_get(namespace, key, default)
        except Exception:
            return default

    async def db_set(self, namespace, key, value):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return None
        try:
            return await k.db_set(namespace, key, value)
        except Exception:
            return None

    async def db_delete(self, namespace, key):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return None
        try:
            return await k.db_delete(namespace, key)
        except Exception:
            return None

    async def db_del(self, namespace, key):
        return await self.db_delete(namespace, key)

    async def db_query(self, sql, params=None):
        return await self.query(sql, params)


class _EmptyTranslator:
    """Заглушка i18n: возвращает ключ как есть."""

    def get(self, key, default=None, **kwargs):
        return default if default is not None else key

    def __call__(self, key, **kwargs):
        return key

    def __getitem__(self, key):
        return key

    def has(self, key):
        return False

    def keys(self):
        return set()


class _SubInline:
    """Рабочий subinline.

    Порядок отправки:
      1. bot_client.send_rich_message (Telethon-MCUB) — если есть
      2. bot_client.send_message
      3. client.send_message (юзербот)
    """

    def __init__(self, module):
        self._module = module

    def _kk(self):
        k = getattr(self._module, "kernel", None)
        return getattr(k, "_k", k)

    @property
    def bot(self):
        return getattr(self._kk(), "bot_client", None)

    @property
    def client(self):
        return getattr(self._kk(), "client", None)

    def _find_rich_client(self):
        """Найти TelegramClient для отправки.

        Для core/tetko/bot.py BotClient: TelegramClient лежит в bot.client.
        Возвращает (tg_client, is_rich) или None.
        """
        import logging
        log = logging.getLogger("TETKO.mcub_compat.subinline")

        bot = self.bot
        if bot is not None:
            # core/tetko/bot.py — BotClient.client = TelegramClient
            tg = getattr(bot, "client", None)
            if tg is not None and hasattr(tg, "send_rich_message"):
                log.warning(f"rich_form: TelegramClient в bot.client ({type(tg).__name__}) — rich")
                return (tg, True)
            if tg is not None and hasattr(tg, "send_message"):
                log.warning(f"rich_form: клиент в bot.client ({type(tg).__name__}) — без rich")
                return (tg, False)
            # _client
            tg = getattr(bot, "_client", None)
            if tg is not None and hasattr(tg, "send_message"):
                log.warning(f"rich_form: клиент в bot._client ({type(tg).__name__})")
                return (tg, hasattr(tg, "send_rich_message"))

        c = self.client
        if c is not None and hasattr(c, "send_message"):
            log.warning(f"rich_form: клиент в kernel.client ({type(c).__name__})")
            return (c, hasattr(c, "send_rich_message"))

        log.warning("rich_form: TelegramClient не найден")
        return None


    async def _send_text(self, chat_id, text, **kwargs):
        import logging
        log = logging.getLogger("TETKO.mcub_compat.subinline")
        reply_to = kwargs.get("reply_to")
        buttons = kwargs.get("buttons")
        parse_mode = kwargs.get("parse_mode", "html")

        found = self._find_rich_client()
        if found is None:
            return None
        tg, _ = found
        try:
            return await tg.send_message(
                chat_id, text, parse_mode=parse_mode,
                buttons=buttons, reply_to=reply_to,
            )
        except TypeError:
            return await tg.send_message(
                chat_id, text, parse_mode=parse_mode, reply_to=reply_to
            )
        except Exception as e:
            log.warning(f"_send_text: {type(e).__name__}: {e}")
            return None


    async def rich_form(self, event, text, **kwargs):
        """Отправка rich-сообщения через inline-бота (плашка via @bot)."""
        import logging
        import time as _time
        log = logging.getLogger("TETKO.mcub_compat.subinline")

        kk = self._kk()
        chat_id = getattr(event, "chat_id", None)
        if chat_id is None:
            return None
        text = str(text or "")
        reply_to = kwargs.get("reply_to")

        # Основной путь: inline-запрос через бота
        bot = getattr(kk, "bot_client", None)
        if bot is not None and hasattr(bot, "send_inline_menu"):
            try:
                key = f"rich_{int(_time.time() * 1000)}"
                buttons = kwargs.get("buttons") or []
                # Регистрируем меню: key → (text, buttons)
                if hasattr(bot, "register_menu"):
                    bot.register_menu(key, text, buttons)
                # Шлём query=rich:<key> — key, а не текст!
                await bot.send_inline_menu(
                    chat_id=chat_id,
                    key=key,
                    text=text,
                    buttons=buttons,
                    query=f"rich:{key}",
                )
                log.debug(f"rich_form: inline через бота OK (key={key})")
                return None
            except Exception as e:
                log.warning(f"rich_form inline: {type(e).__name__}: {e}")

        # Fallback: send_rich_message юзерботом
        found = self._find_rich_client()
        if found is not None:
            tg, is_rich = found
            if is_rich:
                try:
                    result = tg.send_rich_message(chat_id, html=text)
                    if hasattr(result, "__await__"):
                        result = await result
                    log.warning("rich_form: fallback send_rich_message юзерботом")
                    return result
                except Exception as e:
                    log.warning(f"rich_form fallback send_rich_message: {e}")

        # Fallback: обычное сообщение с html
        c = self.client
        if c is not None:
            try:
                return await c.send_message(chat_id, text, parse_mode="html", reply_to=reply_to)
            except Exception as e:
                log.warning(f"rich_form fallback send_message: {e}")

        return None

    async def form(self, chat_id, text, buttons=None, **kwargs):
        """Форма с кнопками (обычное сообщение)."""
        return await self._send_text(
            chat_id, str(text or ""),
            buttons=buttons,
            reply_to=kwargs.get("reply_to"),
        )

    async def send(self, chat_id, text, **kwargs):
        """Обычное сообщение."""
        return await self._send_text(
            chat_id, str(text or ""),
            buttons=kwargs.get("buttons"),
            reply_to=kwargs.get("reply_to"),
        )

    async def answer(self, event, text="", **kwargs):
        """Ответ в callback."""
        try:
            return await event.answer(text, alert=kwargs.get("alert", False))
        except Exception:
            return None
