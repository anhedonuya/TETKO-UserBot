"""MCUB Register API backed by the native TETKO runtime.

This module deliberately mirrors the public surface of MCUB's Register while
keeping ownership/lifecycle inside TETKO.  No second Telegram dispatcher is
created for ordinary userbot events.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import re
import secrets
import time
import uuid
from typing import Any, Callable

log = logging.getLogger("TETKO.mcub_compat.register")


def _await(v):
    return v if inspect.isawaitable(v) else _Immediate(v)


class _Immediate:
    def __init__(self, value): self.value = value
    def __await__(self):
        async def _x(): return self.value
        return _x().__await__()


class InfiniteLoop:
    def __init__(self, func, interval=60, autostart=True, wait_before=False):
        self.func = func
        self.interval = max(0.1, float(interval))
        self.autostart = bool(autostart)
        self._wait_before = bool(wait_before)
        self._task = None
        self.status = False
        self.last_run = None
        self.last_error = None
        self.fail_count = 0
        self._kernel = None

    @property
    def is_running(self):
        return bool(self._task and not self._task.done() and self.status)

    def start(self):
        if self.is_running:
            return
        self._task = asyncio.ensure_future(self._run())

    def stop(self):
        self.status = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    def restart(self):
        self.stop(); self.start()

    async def _run(self):
        self.status = True
        try:
            while self.status:
                if self._wait_before:
                    await asyncio.sleep(self.interval)
                if not self.status: break
                try:
                    self.last_run = time.time()
                    result = self.func(self._kernel) if self._kernel is not None else self.func()
                    if inspect.isawaitable(result): await result
                    self.last_error = None; self.fail_count = 0
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    self.last_error = exc; self.fail_count += 1
                    log.exception("InfiniteLoop error: %s", exc)
                if not self._wait_before:
                    await asyncio.sleep(self.interval)
        finally:
            self.status = False


def _watcher_passes_filters(event, tags):
    if not tags: return True
    msg = getattr(event, "message", event)
    out = bool(getattr(msg, "out", False))
    if tags.get("out") and not out: return False
    if tags.get("incoming") and out: return False
    chat = getattr(event, "chat", None)
    is_pm = bool(chat) and not any(getattr(chat, x, False) for x in ("megagroup", "gigagroup", "broadcast"))
    is_group = bool(chat) and (getattr(chat, "megagroup", False) or getattr(chat, "gigagroup", False))
    is_channel = bool(chat) and getattr(chat, "broadcast", False)
    pairs = (
        ("only_pm", is_pm), ("no_pm", not is_pm),
        ("only_groups", is_group), ("no_groups", not is_group),
        ("only_channels", is_channel), ("no_channels", not is_channel),
    )
    for key, ok in pairs:
        if tags.get(key) and not ok: return False
    media = getattr(msg, "media", None)
    doc = bool(media and getattr(media, "document", None))
    photo = bool(media and getattr(media, "photo", None))
    video = bool(media and getattr(media, "video", None))
    checks = (("only_media", bool(media)), ("no_media", not media),
              ("only_photos", photo), ("no_photos", not photo),
              ("only_videos", video), ("no_videos", not video),
              ("only_docs", doc), ("no_docs", not doc))
    for key, ok in checks:
        if tags.get(key) and not ok: return False
    text = getattr(msg, "raw_text", None) or getattr(msg, "text", "") or ""
    try:
        if "regex" in tags and not re.search(tags["regex"], text): return False
    except re.error:
        return False
    if "startswith" in tags and not text.startswith(tags["startswith"]): return False
    if "endswith" in tags and not text.endswith(tags["endswith"]): return False
    if "contains" in tags and tags["contains"] not in text: return False
    if "from_id" in tags and getattr(event, "sender_id", None) != tags["from_id"]: return False
    if "chat_id" in tags and getattr(event, "chat_id", None) != tags["chat_id"]: return False
    return True


def _event_builder(event_type, args, kwargs):
    """Accept both MCUB strings and already-created Telethon EventBuilder objects."""
    from telethon import events
    if event_type is not None and not isinstance(event_type, str):
        # Telethon builders are already callable only as constructors in some versions;
        # never call an instance/class blindly.  Return an existing builder unchanged.
        if hasattr(event_type, "resolve") or hasattr(event_type, "filter") or event_type.__class__.__module__.startswith("telethon"):
            return event_type
        if isinstance(event_type, type):
            try: return event_type(*args, **kwargs)
            except TypeError: return event_type()
    key = str(event_type or "newmessage").lower()
    _join_req = getattr(events, "JoinRequest", None)
    mapping = {
        "newmessage": events.NewMessage, "message": events.NewMessage,
        "messageedited": events.MessageEdited, "edited": events.MessageEdited,
        "messagedeleted": events.MessageDeleted, "deleted": events.MessageDeleted,
        "messageread": events.MessageRead, "read": events.MessageRead,
        "userupdate": events.UserUpdate, "user": events.UserUpdate,
        "chataction": events.ChatAction, "action": events.ChatAction,
        "joinrequest": _join_req, "request": _join_req,
        "album": events.Album, "inlinequery": events.InlineQuery, "inline": events.InlineQuery,
        "callbackquery": events.CallbackQuery, "callback": events.CallbackQuery,
        "raw": events.Raw, "custom": events.Raw,
    }
    mapping = {k: v for k, v in mapping.items() if v is not None}
    cls = mapping.get(key)
    if cls is None: raise ValueError(f"Unknown MCUB event type: {event_type!r}")
    return cls(*args, **kwargs)


def _patch_event_mcub(event):
    """Добавляет MCUB-совместимые атрибуты к Telethon-событию.

    MCUB-модули используют event.html_text, event.text (как у Message),
    но Telethon даёт raw_text / message. Патчим на лету.
    """
    if event is None:
        return event

    # raw_text — базовый текст
    raw = getattr(event, "raw_text", None)
    if raw is None:
        raw = getattr(event, "message", "") or getattr(event, "text", "") or ""

    # text — plain
    if not hasattr(event, "text") or getattr(event, "text", None) is None:
        try:
            event.text = raw
        except Exception:
            pass

    # html_text — HTML-escape (MCUB-стиль)
    if not hasattr(event, "html_text") or getattr(event, "html_text", None) is None:
        try:
            import html as _html
            event.html_text = _html.escape(raw, quote=False)
        except Exception:
            try:
                event.html_text = raw
            except Exception:
                pass

    # markdown_text — raw (пока без конвертации)
    if not hasattr(event, "markdown_text") or getattr(event, "markdown_text", None) is None:
        try:
            event.markdown_text = raw
        except Exception:
            pass

    return event


class RegisterShim:
    MAX_LOOPS_PER_MODULE = 20

    def __init__(self, tetko_kernel, module_instance):
        self.kernel = tetko_kernel
        self.module = module_instance
        self._tetko_registry = tetko_kernel.registry
        self._commands = {}
        self._bot_commands = {}
        self._watchers = []
        self._events = []
        self._loops = []
        self._methods = {}
        self._aliases = {}
        self._inline_temp_map = {}
        self._callbacks = []
        self._inline_handlers = []
        self._on_load_fn = None
        self._on_install_fn = None
        self._uninstall_fn = None

    @property
    def module_name(self): return getattr(self.module, "name", type(self.module).__name__)

    def _register_event_handler(self, handler, event_obj, bot_client=False):
        client = getattr(self.kernel, "bot_client", None) if bot_client else getattr(self.kernel, "client", None)
        if client is None: raise RuntimeError("Telegram client unavailable")
        target = client
        if not hasattr(target, "add_event_handler") and hasattr(target, "client"):
            target = target.client
        if not hasattr(target, "add_event_handler"):
            raise RuntimeError(f"client {type(target).__name__} has no add_event_handler")
        target.add_event_handler(handler, event_obj)
        self._events.append((handler, event_obj, target))

    def command(self, pattern, **kwargs):
        def decorator(fn):
            name = str(pattern).lstrip("./!#^")
            name = name[:-1] if name.endswith("$") else name
            aliases = kwargs.get("alias", kwargs.get("aliases", [])) or []
            if isinstance(aliases, str): aliases = [aliases]
            docs = kwargs.get("doc")
            if isinstance(docs, dict): docs = docs.get("ru") or docs.get("en") or ""
            docs = docs or kwargs.get("doc_ru") or kwargs.get("doc_en") or ""
            async def wrapper(event, *args): return await self._invoke_handler(fn, event, args)
            try:
                from core.tetko.registry import Command
                self._tetko_registry.register_command(Command(name=name, func=wrapper, module=self.module, aliases=list(aliases), doc=docs, only_for=kwargs.get("only_for"), **{k:v for k,v in kwargs.items() if k not in {"alias","aliases","doc","doc_ru","doc_en","only_for"}}))
                self._commands[name] = wrapper
                for a in aliases: self._aliases[str(a).lower()] = name
            except Exception as e:
                # Duplicate command on the same module is harmless during reload.
                existing = self._tetko_registry.find_command(name)
                if existing is None or existing.module is not self.module:
                    log.warning("[%s] command '%s': %s", self.module_name, name, e)
            return fn
        return decorator

    def bot_command(self, pattern, **kwargs):
        def decorator(fn): self._bot_commands[str(pattern).lstrip("/")] = (pattern, fn); return fn
        return decorator

    def watcher(self, func=None, bot_client=False, **tags):
        def decorator(fn):
            async def wrapper(event):
                if not _watcher_passes_filters(event, tags): return None
                return await self._invoke_handler(fn, event)
            wrapper.__name__ = f"mcub_watcher:{self.module_name}:{getattr(fn,'__name__','?')}"
            self._tetko_registry.register_watcher(self.module, wrapper)
            self._watchers.append({"module": self.module_name, "method": getattr(fn,"__name__","?"), "enabled": True, "tags": dict(tags), "bot_client": bot_client, "wrapper": wrapper})
            return fn
        return decorator(func) if func is not None and callable(func) else decorator

    def event(self, event_type, *args, bot_client=False, **kwargs):
        def decorator(fn):
            try:
                event_obj = _event_builder(event_type, args, kwargs)
                async def wrapper(event): return await self._invoke_handler(fn, event)
                wrapper.__name__ = f"mcub_event:{self.module_name}:{getattr(fn,'__name__','?')}"
                self._register_event_handler(wrapper, event_obj, bot_client=bot_client)
            except Exception as e:
                log.error("[%s] event registration: %s", self.module_name, e)
            return fn
        return decorator

    def callback(self, func=None, *, ttl=900):
        def decorator(fn):
            token = uuid.uuid4().hex[:32]
            entry = {"handler": self._make_callback_handler(fn), "args": [], "kwargs": {}, "module_name": self.module_name, "expires_at": time.time()+ttl if ttl else None}
            self._ensure_cb_map()[token] = entry
            self._callbacks.append((token, fn, entry))
            return fn
        return decorator(func) if func is not None and callable(func) else decorator

    def _ensure_cb_map(self):
        if not hasattr(self.kernel, "inline_callback_map"): self.kernel.inline_callback_map = {}
        if not hasattr(self.kernel, "_inline_cb_lock"):
            import threading; self.kernel._inline_cb_lock = threading.Lock()
        return self.kernel.inline_callback_map

    def _make_callback_handler(self, fn):
        async def handler(event, *args, **kwargs):
            return await self._invoke_handler(fn, event, args)
        return handler

    def loop(self, interval=60, autostart=True, wait_before=False, **kwargs):
        def decorator(fn):
            obj = InfiniteLoop(lambda *a, **kw: self._invoke_handler(fn, None), interval, autostart, wait_before)
            obj._kernel = self.kernel
            self._loops.append(obj)
            return obj
        return decorator

    def method(self, func=None):
        def decorator(fn): self._methods[fn.__name__] = fn; return fn
        return decorator(func) if func is not None and callable(func) else decorator

    def on_load(self, func=None):
        def decorator(fn): self._on_load_fn = fn; return fn
        return decorator(func) if func is not None and callable(func) else decorator

    def on_install(self, func=None):
        def decorator(fn): self._on_install_fn = fn; return fn
        return decorator(func) if func is not None and callable(func) else decorator

    def uninstall(self, func=None):
        def decorator(fn): self._uninstall_fn = fn; return fn
        return decorator(func) if func is not None and callable(func) else decorator

    def owner(self, func=None, only_admin=False):
        def decorator(fn):
            async def wrapper(event):
                admin = getattr(getattr(self.kernel,"context",None),"admin_id",None)
                sender = getattr(event,"sender_id",None)
                if admin is None or sender is None or int(admin) != int(sender): return None
                return await self._invoke_handler(fn,event)
            return wrapper
        return decorator(func) if func is not None and callable(func) else decorator

    def permissions(self, *args, **kwargs):
        return lambda fn: fn
    permission = permissions

    def inline(self, pattern, **kwargs):
        def decorator(fn):
            try:
                if hasattr(self.kernel, "register_inline_handler"):
                    async def wrapper(event): return await self._invoke_handler(fn,event)
                    self.kernel.register_inline_handler(pattern, wrapper)
                    self._inline_handlers.append((pattern, wrapper))
            except Exception as e: log.warning("[%s] inline '%s': %s", self.module_name, pattern, e)
            return fn
        return decorator

    def inline_temp(self, func=None, *, ttl=300, **kwargs):
        def decorator(fn):
            token = uuid.uuid4().hex[:8]
            self._inline_temp_map[token] = {"handler": fn, "expires_at": time.time()+ttl}
            return token
        return decorator(func) if func is not None and callable(func) else decorator

    async def invoke(self, command, args=None, chat_id=None, reply_to=None, **kwargs):
        prefix = getattr(getattr(self.kernel,"context",None),"prefix",None) or getattr(self.kernel,"prefix",".") or "."
        chat_id = chat_id or getattr(getattr(self.kernel,"context",None),"admin_id",None)
        if chat_id is None: return None
        text = f"{prefix}{command}" + (f" {args}" if args else "")
        return await self.kernel.client.send_message(chat_id, text, reply_to=reply_to)

    def get_commands(self): return dict(self._commands)
    def command_list(self): return list(self._commands.keys())
    def get_command(self, name): return self._commands.get(name)
    def alias_list(self): return list(self._aliases.keys())
    def get_command(self, command): return {"handler": self._commands.get(command), "owner": self.module_name if command in self._commands else None, "docs": {}}
    def get_bot_commands(self): return dict(self._bot_commands)
    def get_watchers(self): return list(self._watchers)
    def get_events(self): return list(self._events)
    def get_loops(self): return list(self._loops)
    def get_all_aliases(self): return dict(self._aliases)
    def get_command_alias(self, command):
        for a,c in self._aliases.items():
            if c == command: return a
        return None
    def get_use_bot(self): return {"available": getattr(self.kernel,"bot_client",None) is not None, "connected": bool(getattr(self.kernel,"bot_client",None)), "username": None}
    def disable_watcher(self, module_name, watcher_name):
        for w in self._watchers:
            if w["module"] == module_name and w["method"] == watcher_name: w["enabled"] = False; return True
        return False
    def enable_watcher(self, module_name, watcher_name):
        for w in self._watchers:
            if w["module"] == module_name and w["method"] == watcher_name: w["enabled"] = True; return True
        return False
    def unregister_command(self, cmd):
        self._commands.pop(cmd, None); return True
    def unregister_bot_command(self, cmd):
        self._bot_commands.pop(cmd, None); return True

    async def _invoke_handler(self, fn, event, args=None):

        event = _patch_event_mcub(event)

        try:
            sig = inspect.signature(fn)
            params = [p for p in sig.parameters.values() if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
            n = len(params)
        except Exception: n = 1
        try:
            # Bound MCUB method: self is already bound.
            if inspect.ismethod(fn) or getattr(fn, "__self__", None) is not None:
                if event is None:
                    return await _maybe(fn())
                if n <= 1: return await _maybe(fn(event))
                return await _maybe(fn(event, args or []))
            if event is None:
                return await _maybe(fn(self.module)) if n else await _maybe(fn())
            if n <= 1: return await _maybe(fn(event))
            if n == 2: return await _maybe(fn(self.module,event))
            return await _maybe(fn(self.module,event,args or []))
        except Exception as e:
            log.exception("[%s] handler: %s", self.module_name, e)
            return None


async def _maybe(v):
    if inspect.isawaitable(v): return await v
    return v


def run_autostart_loops(register_shim):
    for loop_obj in register_shim.get_loops():
        if loop_obj.autostart:
            try: loop_obj.start()
            except Exception as e: log.warning("[%s] loop start: %s", register_shim.module_name, e)


def stop_all_loops(register_shim):
    for loop_obj in register_shim.get_loops():
        try: loop_obj.stop()
        except Exception: pass


def unregister_all_events(register_shim):
    for handler, event_obj, client in list(register_shim.get_events()):
        try: client.remove_event_handler(handler, event_obj)
        except Exception: pass
    register_shim._events.clear()


def unregister_all_callbacks(register_shim):
    cb_map = getattr(register_shim.kernel, "inline_callback_map", {})
    for token, _, _ in list(register_shim._callbacks): cb_map.pop(token, None)
    register_shim._callbacks.clear()

__all__ = ["RegisterShim", "InfiniteLoop", "run_autostart_loops", "stop_all_loops", "unregister_all_events", "unregister_all_callbacks"]
