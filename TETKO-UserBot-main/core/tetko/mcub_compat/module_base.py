"""MCUB ModuleBase compatibility implementation for TETKO.

The class intentionally mirrors the public MCUB ModuleBase surface while
routing registration, storage, events and inline callbacks through TETKO.
"""
from __future__ import annotations

import inspect
import logging
import time
import uuid
from typing import Any

from .module_config import ModuleConfig

log = logging.getLogger("TETKO.mcub_compat.module_base")


class _ModuleLogger:
    def __init__(self, name: str):
        self._logger = logging.getLogger(f"MCUB.module.{name}")
    def debug(self, msg, *a, **kw): self._logger.debug(msg, *a, **kw)
    def info(self, msg, *a, **kw): self._logger.info(msg, *a, **kw)
    def warning(self, msg, *a, **kw): self._logger.warning(msg, *a, **kw)
    def error(self, msg, *a, **kw): self._logger.error(msg, *a, **kw)
    def exception(self, msg, *a, **kw): self._logger.exception(msg, *a, **kw)


class _DictStrings:
    def __init__(self, data):
        self._data = data or {}
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


class _EmptyStrings(_DictStrings):
    def __init__(self): super().__init__({})
    def __call__(self, key, **kw): return f"[{key}]"
    def __getitem__(self, key): return f"[{key}]"
    def get(self, key, default=None): return default if default is not None else f"[{key}]"


class _ArgsShim:
    def __init__(self, raw: str):
        self.raw = raw or ""
        self.args = self.raw.split() if self.raw else []
        self.kwargs = {}
        self.flags = set()
        for item in list(self.args):
            if item.startswith("--"):
                self.flags.add(item[2:])
    def get(self, index, default=None):
        try: return self.args[index]
        except (IndexError, TypeError): return default
    def get_flag(self, flag): return flag in self.flags
    def get_kwarg(self, key, default=None): return self.kwargs.get(key, default)
    def has(self, key): return key in self.kwargs
    def join_args(self, start=0, end=None): return " ".join(map(str, self.args[start:end]))
    def __len__(self): return len(self.args)
    def __getitem__(self, i): return self.args[i]
    def __iter__(self): return iter(self.args)
    def __bool__(self): return bool(self.args)


class _ButtonFactory:
    """MCUB Button API backed by Telethon and the compat callback store."""

    def __init__(self, module):
        self._module = module

    def inline(self, text, callback=None, *, data=None, args=None, kwargs=None,
               ttl=900, icon=None, style=None):
        from telethon import Button
        if callable(callback):
            from .inline_shim import make_cb_button
            return make_cb_button(
                self._module.kernel, text, callback,
                args=args, kwargs=kwargs, ttl=ttl, icon=icon, style=style
            )
        if data is None:
            data = b""
        if isinstance(data, str):
            data = data.encode()
        try:
            return Button.inline(text, data=data, icon=icon, style=style)
        except TypeError:
            return Button.inline(text, data=data)

    def url(self, text, url, **kwargs):
        from telethon import Button
        return Button.url(text, url)

    def text(self, text, **kwargs):
        from telethon import Button
        return Button.text(text)

    def switch(self, text, query="", same_peer=False, **kwargs):
        from telethon import Button
        return Button.switch_inline(text, query, same_peer=same_peer)

    def input(self, text, placeholder="", **kwargs):
        from telethon import Button
        try:
            return Button.input(text, placeholder=placeholder)
        except TypeError:
            return Button.input(text)

    def close(self, text="Close", **kwargs):
        from telethon import Button
        return Button.clear(text)

    def copy(self, text, query, **kwargs):
        from telethon import Button
        # Telegram/Telethon does not expose a universal copy button. Use callback
        # data where possible; this keeps old MCUB modules functional.
        cb = kwargs.get("callback")
        if callable(cb):
            return self.inline(text, cb, ttl=kwargs.get("ttl", 900))
        return Button.inline(text, data=str(query).encode()[:64])


class MCUBModuleBase:
    name = "Unnamed"
    version = "1.0.0"
    author = "unknown"
    description = {}
    dependencies = []
    banner_url = None
    strings = {}
    config = None

    def __getattribute__(self, name):
        if name == "config":
            try:
                return object.__getattribute__(self, "_get_config")()
            except AttributeError:
                pass
        if name == "strings":
            try:
                return object.__getattribute__(self, "_get_strings")()
            except AttributeError:
                pass
        return object.__getattribute__(self, name)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        registries = (
            "_mcub_registry_commands", "_mcub_registry_watchers",
            "_mcub_registry_callbacks", "_mcub_registry_loops",
            "_mcub_registry_events", "_mcub_registry_methods",
            "_mcub_registry_install", "_mcub_registry_uninstall",
            "_mcub_registry_bot_commands", "_mcub_registry_inline",
            "_mcub_registry_inline_temp", "_mcub_registry_owner",
            "_mcub_registry_permissions", "_mcub_registry_errors",
        )
        for r in registries:
            setattr(cls, r, [])
        for name, attr in cls.__dict__.items():
            if not callable(attr):
                continue
            for pattern, meta in getattr(attr, "_mcub_commands", []):
                cls._mcub_registry_commands.append((pattern, attr, meta))
            for info in getattr(attr, "_mcub_watchers", []):
                cls._mcub_registry_watchers.append((attr, info))
            for info in getattr(attr, "_mcub_callbacks", []):
                cls._mcub_registry_callbacks.append((attr, info.get("ttl", 900)))
            for info in getattr(attr, "_mcub_loops", []):
                cls._mcub_registry_loops.append((attr, info))
            for info in getattr(attr, "_mcub_events", []):
                cls._mcub_registry_events.append((attr, info))
            for info in getattr(attr, "_mcub_methods", []):
                cls._mcub_registry_methods.append(attr)
            for info in getattr(attr, "_mcub_on_install", []):
                cls._mcub_registry_install.append(attr)
            for info in getattr(attr, "_mcub_uninstall", []):
                cls._mcub_registry_uninstall.append(attr)
            for pattern, meta in getattr(attr, "_mcub_bot_commands", []):
                cls._mcub_registry_bot_commands.append((pattern, attr, meta))
            for pattern in getattr(attr, "_mcub_inline", []):
                cls._mcub_registry_inline.append((pattern, attr))
            for info in getattr(attr, "_mcub_inline_temp", []):
                cls._mcub_registry_inline_temp.append((attr, info))
            for info in getattr(attr, "_mcub_owner", []):
                cls._mcub_registry_owner.append((attr, info))
            for info in getattr(attr, "_mcub_permissions", []):
                cls._mcub_registry_permissions.append((attr, info))
            for info in getattr(attr, "_mcub_error_handler", []):
                cls._mcub_registry_errors.append((attr, info))

    def __init__(self, kernel=None, client=None, register=None):
        self.kernel = kernel
        self.client = client or getattr(kernel, "client", None)
        self._register = register or getattr(kernel, "register", None)
        self.log = _ModuleLogger(getattr(self, "name", type(self).__name__))
        self._loaded = False
        self.cache = getattr(kernel, "cache", None)
        self.db = kernel
        self._loops = []
        self._callback_tokens = []
        self._inline_temp_ids = {}

        cfg = None
        for cls in type(self).__mro__:
            if "config" in cls.__dict__ and not isinstance(cls.__dict__["config"], property):
                cfg = cls.__dict__["config"]
                break
        self._config_obj = cfg if isinstance(cfg, ModuleConfig) else None
        if self._config_obj is not None:
            try:
                self._config_obj.bind_owner(self)
                from core.tetko import db_get
                saved = db_get("module_configs", self.name, None)
                if isinstance(saved, dict):
                    if hasattr(self._config_obj, "from_dict"):
                        self._config_obj.from_dict(saved)
                    else:
                        self._config_obj.update(saved)
            except Exception as e:
                log.debug("[%s] config restore skipped: %s", self.name, e)

        self._auto_register()

    def _auto_register(self):
        kr = self._register or getattr(self.kernel, "register", None)
        if kr is None:
            return

        owners = {fn.__name__: info for fn, info in type(self)._mcub_registry_owner}
        permissions = {}
        for fn, info in type(self)._mcub_registry_permissions:
            permissions.setdefault(fn.__name__, {}).update(info)
        errors = {fn.__name__: info for fn, info in type(self)._mcub_registry_errors}

        for pattern, fn, meta in type(self)._mcub_registry_commands:
            bound = getattr(self, fn.__name__)
            kw = dict(meta or {})
            alias = kw.pop("alias", None)
            doc = kw.pop("doc", None)
            if doc is None:
                docs = {k[4:]: v for k, v in kw.items() if k.startswith("doc_")}
                doc = docs or None
            for k in list(kw):
                if k.startswith("doc_"):
                    kw.pop(k)
            if alias is not None: kw["alias"] = alias
            if doc is not None: kw["doc"] = doc
            wrapped = self._wrap_handler(bound, fn.__name__, permissions.get(fn.__name__), errors.get(fn.__name__))
            if fn.__name__ in owners:
                wrapped = self._owner_wrap(wrapped, owners[fn.__name__].get("only_admin", False))
            kr.command(pattern, **kw)(wrapped)

        for fn, info in type(self)._mcub_registry_watchers:
            bound = getattr(self, fn.__name__)
            info = dict(info)
            tags = dict(info.pop("tags", {}))
            kr.watcher(bound, bot_client=info.get("bot_client", False), **tags)

        for fn, ttl in type(self)._mcub_registry_callbacks:
            bound = getattr(self, fn.__name__)
            if hasattr(kr, "callback"):
                kr.callback(ttl=ttl)(bound)

        for fn, info in type(self)._mcub_registry_loops:
            bound = getattr(self, fn.__name__)
            loop = kr.loop(**dict(info))(bound)
            self._loops.append(loop)
            setattr(self, fn.__name__, loop)

        for fn, info in type(self)._mcub_registry_events:
            bound = getattr(self, fn.__name__)
            info = dict(info)
            event_type = info.pop("event_type")
            args = info.pop("args", ())
            bot_client = info.pop("bot_client", False)
            kr.event(event_type, *args, bot_client=bot_client, **info)(bound)

        for fn in type(self)._mcub_registry_methods:
            self._run_method(getattr(self, fn.__name__))

        for fn in type(self)._mcub_registry_install:
            self._install_fn = getattr(self, fn.__name__)
        for fn in type(self)._mcub_registry_uninstall:
            self._uninstall_fn = getattr(self, fn.__name__)

        for pattern, fn, meta in type(self)._mcub_registry_bot_commands:
            bound = getattr(self, fn.__name__)
            kr.bot_command(pattern, **dict(meta or {}))(bound)

        for pattern, fn in type(self)._mcub_registry_inline:
            bound = getattr(self, fn.__name__)
            # Inline handlers are Telethon InlineQuery handlers in the MCUB API.
            kr.event("inlinequery", pattern=pattern, bot_client=True)(bound)

        for fn, info in type(self)._mcub_registry_inline_temp:
            bound = getattr(self, fn.__name__)
            try:
                token = kr.inline_temp(
                    bound,
                    ttl=info.get("ttl", 300),
                    article=info.get("article"),
                    data=info.get("data"),
                    allow_user=info.get("allow_user"),
                    allow_ttl=info.get("allow_ttl", 100),
                )
                self._inline_temp_ids[f"{self.name}:{fn.__name__}"] = token
            except Exception as e:
                log.warning("[%s] inline_temp %s: %s", self.name, fn.__name__, e)

    def _run_method(self, fn):
        try:
            result = fn()
            if inspect.isawaitable(result):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    asyncio.run(result)
        except Exception as e:
            log.error("[%s] method %s failed: %s", self.name, getattr(fn, "__name__", "?"), e)

    def _wrap_handler(self, fn, name, permissions=None, error_handler=None):
        async def wrapped(event, *args, **kwargs):
            if permissions:
                tags = {k:v for k,v in permissions.items() if k != "log_level"}
                if not self._passes_permission_tags(event, tags):
                    return
            try:
                result = fn(event, *args, **kwargs)
                return await result if inspect.isawaitable(result) else result
            except Exception as e:
                if error_handler and error_handler.get("message"):
                    msg = str(error_handler["message"]).format(exc=str(e), func=name, module=self.name)
                    getattr(self.log, error_handler.get("log_level","error"), self.log.error)(msg)
                else:
                    self.log.exception(f"handler {name}: {e}")
                if error_handler and error_handler.get("reraise"):
                    raise
        wrapped.__name__ = f"mcub:{self.name}:{name}"
        return wrapped

    def _owner_wrap(self, fn, only_admin=False):
        async def wrapped(event, *args, **kwargs):
            sender = getattr(event, "sender_id", None)
            admin = getattr(self.kernel, "ADMIN_ID", None)
            if admin is None or sender is None or int(sender) != int(admin):
                return
            return await fn(event, *args, **kwargs)
        return wrapped

    def _passes_permission_tags(self, event, tags):
        from .register_shim import _watcher_passes_filters
        try: return _watcher_passes_filters(event, tags)
        except Exception: return False

    def _get_strings(self):
        data = None
        for cls in type(self).__mro__:
            if "strings" in cls.__dict__:
                data = cls.__dict__["strings"]
                break
        if not data:
            return _EmptyStrings()
        try:
            from .strings_compat import Strings
            return Strings(self.kernel, data)
        except Exception:
            if "name" in data:
                try:
                    from core.langpacks import get_module_strings
                    locale = self.get_lang()
                    return _DictStrings(get_module_strings(self.name, locale) or data)
                except Exception:
                    pass
            if all(isinstance(v, dict) for v in data.values()):
                active = data.get(self.get_lang()) or data.get("en") or next(iter(data.values()), {})
            else:
                active = data
            return _DictStrings(active)

    def _get_config(self):
        return self._config_obj if self._config_obj is not None else _EmptyConfig()

    async def save_config(self):
        cfg = self._config_obj
        if cfg is None: return False
        try:
            from core.tetko.db import db_set
            db_set("module_configs", self.name, cfg.to_dict() if hasattr(cfg, "to_dict") else cfg.all())
            return True
        except Exception as e:
            self.log.error(f"save_config: {e}")
            return False

    def get_prefix(self):
        return getattr(self.kernel, "custom_prefix", ".") or "."

    def get_lang(self):
        cfg = getattr(self.kernel, "config", {}) or {}
        return cfg.get("language", "ru") if isinstance(cfg, dict) else "ru"

    def args_raw(self, event):
        text = getattr(event, "raw_text", "") or getattr(event, "text", "") or ""
        prefix = self.get_prefix()
        if text.startswith(prefix):
            body = text[len(prefix):]
            return body.split(maxsplit=1)[1] if len(body.split(maxsplit=1)) > 1 else ""
        return ""

    def args(self, event):
        return _ArgsShim(self.args_raw(event))

    def args_html(self, event):
        return self.args_raw(event)

    async def edit(self, event, text, **kwargs):
        as_html = kwargs.pop("as_html", False)
        reply_markup = kwargs.pop("reply_markup", None)
        if reply_markup is not None: kwargs["buttons"] = reply_markup
        if as_html and "parse_mode" not in kwargs: kwargs["parse_mode"] = "html"
        return await event.edit(text, **kwargs)

    async def answer(self, event, text="", **kwargs):
        as_html = kwargs.pop("as_html", False)
        if as_html and "parse_mode" not in kwargs: kwargs["parse_mode"] = "html"
        if hasattr(event, "answer") and callable(event.answer):
            return await event.answer(text, **kwargs)
        if hasattr(event, "reply") and callable(event.reply):
            return await event.reply(text, **kwargs)
        return None

    async def reply(self, event, text, **kwargs):
        as_html = kwargs.pop("as_html", False)
        if as_html and "parse_mode" not in kwargs: kwargs["parse_mode"] = "html"
        if hasattr(event, "reply") and callable(event.reply):
            return await event.reply(text, **kwargs)
        return await self.answer(event, text, **kwargs)

    async def invoke(self, command, args=None, chat_id=None, reply_to=None):
        return await self._register.invoke(command, args, chat_id, reply_to)

    async def inline(self, chat_id, title, fields=None, buttons=None, auto_send=True, ttl=200, reply_to=None, **kwargs):
        return await self.kernel.inline_form(
            chat_id, title, fields=fields, buttons=buttons, auto_send=auto_send,
            ttl=ttl, reply_to=reply_to, **kwargs
        )

    def lookup_module(self, module_name, *, all_loaded=False):
        return self.kernel.lookup_module(module_name, all_loaded=all_loaded)

    def require_module(self, module_name, *, all_loaded=False):
        mod = self.lookup_module(module_name, all_loaded=all_loaded)
        if mod is None: raise LookupError(f"Required module '{module_name}' is not loaded")
        return mod

    async def import_lib(self, url, *, name=None):
        import aiohttp
        if name is None: name = url.rsplit("/", 1)[-1].removesuffix(".py")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as response:
                response.raise_for_status()
                code = await response.text()
        import sys, types
        module = types.ModuleType(name)
        sys.modules[name] = module
        exec(compile(code, name, "exec"), module.__dict__)
        return module

    @property
    def Button(self): return _ButtonFactory(self)

    def callback_button(self, text, callback, *, args=None, kwargs=None, ttl=900, **kw):
        return self.Button.inline(text, callback, args=args, kwargs=kwargs, ttl=ttl, **kw)

    async def on_load(self):
        self._loaded = True
        # MCUB has a regular method named on_load in most modules; decorators are
        # registered above only when @on_load was used, so both styles work.
        if getattr(self, "_install_fn", None):
            pass
        # Start loops after all registrations.
        from .register_shim import run_autostart_loops
        run_autostart_loops(self._register)
        return None

    async def on_install(self):
        fn = getattr(self, "_install_fn", None)
        if fn:
            result = fn()
            if inspect.isawaitable(result): await result

    async def on_unload(self):
        if hasattr(self._register, "cleanup"):
            self._register.cleanup()
        else:
            from .register_shim import stop_all_loops
            stop_all_loops(self._register)
        self._cleanup_callback_tokens()
        fn = getattr(self, "_uninstall_fn", None)
        if fn:
            result = fn()
            if inspect.isawaitable(result): await result
        self._loaded = False

    def _cleanup_callback_tokens(self):
        k = self.kernel
        tokens = getattr(self, "_callback_tokens", [])
        if not tokens: return
        remover = getattr(k, "remove_inline_callback_tokens", None)
        if callable(remover):
            remover(tokens)
        else:
            lock = getattr(k, "_inline_cb_lock", None)
            cb_map = getattr(k, "inline_callback_map", None)
            if lock and cb_map:
                with lock:
                    for t in tokens: cb_map.pop(t, None)
        self._callback_tokens = []

    @property
    def subinline(self):
        if not hasattr(self, "_subinline"):
            self._subinline = _SubInline(self)
        return self._subinline

    def _empty(self): return None


class _EmptyConfig:
    def get(self, key, default=None): return default
    def set(self, key, value): return None
    def all(self): return {}
    def to_dict(self): return {}
    def __getitem__(self, key): raise KeyError(key)
    def __setitem__(self, key, value): pass
    def __contains__(self, key): return False


class _SubInline:
    def __init__(self, module): self._module = module
    @property
    def bot(self): return getattr(self._module.kernel, "bot_client", None)
    @property
    def client(self): return getattr(self._module.kernel, "client", None)
    async def send(self, chat_id, text, **kwargs):
        c = self.bot or self.client
        if c is None: return None
        sender = getattr(c, "send_message", None)
        if callable(sender):
            return await sender(chat_id, text, **kwargs)
        return None
    async def form(self, chat_id, text, buttons=None, **kwargs):
        return await self.send(chat_id, text, buttons=buttons, **kwargs)
    async def rich_form(self, event, text, **kwargs):
        return await self._module.inline(getattr(event, "chat_id", None), text, **kwargs)
    async def answer(self, event, text="", **kwargs):
        try: return await event.answer(text, alert=kwargs.get("alert", False))
        except Exception: return None


__all__ = ["MCUBModuleBase"]
