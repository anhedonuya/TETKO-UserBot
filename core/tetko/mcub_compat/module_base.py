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
    def inline(self, *a, **kw): raise NotImplementedError("Button.inline — этап 4")
    def url(self, text, url, **kw):
        from telethon.tl.custom import Button
        return Button.url(text, url)
    def text(self, *a, **kw): raise NotImplementedError("Button.text — этап 4")
    def switch(self, *a, **kw): raise NotImplementedError("Button.switch — этап 4")
    def input(self, *a, **kw): raise NotImplementedError("Button.input — этап 4")
    def close(self, *a, **kw): raise NotImplementedError("Button.close — этап 4")
    def copy(self, *a, **kw): raise NotImplementedError("Button.copy — этап 4")


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

        # Собираем всё, что помечено декораторами из loader.*
        registry = {
            "commands": [],
            "watchers": [],
            "callbacks": [],
            "loops": [],
            "bot_commands": [],
            "inlines": [],
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

        cls._mcub_registry = registry

    def __init__(self, kernel=None, client=None, register=None):
        self.kernel = kernel
        self.client = client
        self._register = register or getattr(kernel, "register", None)
        self.log = _ModuleLogger(getattr(self, "name", type(self).__name__))
        self._loaded = False
        self.cache = getattr(kernel, "cache", None)
        self.db = kernel

        # Реальный ModuleConfig из class.config (MCUB-стиль)
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

    def _get_strings(self):
        data = getattr(self, "strings", None) or {}
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
        cfg = getattr(self, "_config_obj", None)
        if cfg is not None:
            return cfg
        return _EmptyConfig()

    async def save_config(self): return None

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
        return await event.edit(text, **kwargs)

    async def answer(self, event, text, **kwargs):
        as_html = kwargs.pop("as_html", False)
        if as_html and "parse_mode" not in kwargs:
            kwargs["parse_mode"] = "html"
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
    def Button(self): return _ButtonFactoryStub()

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
        """MCUB-совместимый subinline: rich_form / form / send / button.

        Реализация через tetko kernel.inline и bot_client (если есть).
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


__all__ = ["MCUBModuleBase"]


class _SubInline:
    """Реальный subinline: делегирует в tetko kernel.inline / bot_client."""

    def __init__(self, module):
        self._module = module

    @property
    def bot(self):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return None
        return getattr(k, "bot_client", None) or getattr(k, "_k", None) and getattr(getattr(k, "_k"), "bot_client", None)

    async def rich_form(self, event, text, **kwargs):
        """Fallback: rich-API нет — шлём обычным сообщением с HTML."""
        k = getattr(self._module, "kernel", None)
        chat_id = getattr(event, "chat_id", None)
        if k is None or chat_id is None:
            return None
        try:
            kk = getattr(k, "_k", k)  # развернуть KernelProxy при необходимости
            inline = getattr(kk, "inline", None)
            text = str(text or "").strip()
            if inline is not None and hasattr(inline, "form"):
                return await inline.form(
                    chat_id=chat_id,
                    text=text,
                    buttons=[],
                    reply_to=kwargs.get("reply_to"),
                    parse_mode="html",
                )
            client = getattr(kk, "client", None)
            if client is not None:
                return await client.send_message(
                    chat_id, text, parse_mode="html",
                    reply_to=kwargs.get("reply_to"),
                )
        except Exception as e:
            import logging
            logging.getLogger("TETKO.mcub_compat.subinline").warning(f"rich_form: {e}")
        return None

    async def form(self, chat_id, text, buttons=None, **kwargs):
        k = getattr(self._module, "kernel", None)
        if k is None:
            return None
        kk = getattr(k, "_k", k)
        inline = getattr(kk, "inline", None)
        if inline is not None and hasattr(inline, "form"):
            try:
                return await inline.form(
                    chat_id=chat_id, text=str(text or ""),
                    buttons=buttons or [],
                    reply_to=kwargs.get("reply_to"),
                    parse_mode="html",
                )
            except Exception as e:
                import logging
                logging.getLogger("TETKO.mcub_compat.subinline").warning(f"form: {e}")
        client = getattr(kk, "client", None)
        if client is not None:
            return await client.send_message(chat_id, str(text or ""), parse_mode="html")
        return None

    def __getattr__(self, name):
        import logging
        logging.getLogger("TETKO.mcub_compat.subinline").debug(f"subinline.{name} — не реализовано")
        async def _stub(*a, **kw):
            return None
        return _stub
