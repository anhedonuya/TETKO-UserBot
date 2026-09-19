"""Register — MCUB-совместимый реестр поверх tetko-Registry."""
from __future__ import annotations

import asyncio
import inspect
import logging
import re
import time
from collections.abc import Callable
from typing import Any, Optional

from core.tetko.registry import Command as TetkoCommand


log = logging.getLogger("TETKO.mcub_compat.register")


class InfiniteLoop:
    def __init__(self, func, interval, autostart=True, wait_before=False):
        self.func = func
        self.interval = max(1, int(interval))
        self.autostart = autostart
        self._wait_before = wait_before
        self._task = None
        self.status = False
        self.last_run = None
        self.last_error = None
        self.fail_count = 0

    @property
    def is_running(self):
        return bool(self._task and not self._task.done() and self.status)

    def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.ensure_future(self._run())

    def stop(self):
        self.status = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    def restart(self):
        self.stop()
        self.start()

    async def _run(self):
        self.status = True
        try:
            while self.status:
                if self._wait_before:
                    await asyncio.sleep(self.interval)
                if not self.status:
                    break
                try:
                    self.last_run = time.time()
                    result = self.func()
                    if inspect.isawaitable(result):
                        await result
                    self.last_error = None
                    self.fail_count = 0
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.last_error = e
                    self.fail_count += 1
                    log.error(f"InfiniteLoop: {e}")
                if not self._wait_before:
                    await asyncio.sleep(self.interval)
        finally:
            self.status = False


def _watcher_passes_filters(event, tags):
    if not tags:
        return True
    msg = getattr(event, "message", event)
    if tags.get("out") and not getattr(msg, "out", False):
        return False
    if tags.get("incoming") and getattr(msg, "out", False):
        return False
    chat = getattr(event, "chat", None)
    is_pm = bool(chat) and not getattr(chat, "megagroup", False) and not getattr(chat, "broadcast", False)
    is_group = getattr(chat, "megagroup", False) or getattr(chat, "gigagroup", False)
    is_channel = getattr(chat, "broadcast", False)
    for tag, check in (
        ("only_pm", is_pm), ("no_pm", not is_pm),
        ("only_groups", is_group), ("no_groups", not is_group),
        ("only_channels", is_channel), ("no_channels", not is_channel),
    ):
        if tags.get(tag) and not check:
            return False
    media = getattr(msg, "media", None)
    photo = media and hasattr(media, "photo")
    video = media and hasattr(media, "video")
    doc = media and hasattr(media, "document")
    for tag, check in (
        ("only_media", bool(media)), ("no_media", not media),
        ("only_photos", bool(photo)), ("no_photos", not photo),
        ("only_videos", bool(video)), ("no_videos", not video),
        ("only_docs", bool(doc)), ("no_docs", not doc),
    ):
        if tags.get(tag) and not check:
            return False
    fwd = getattr(msg, "fwd_from", None)
    reply = getattr(msg, "reply_to", None)
    for tag, check in (
        ("only_forwards", bool(fwd)), ("no_forwards", not fwd),
        ("only_reply", bool(reply)), ("no_reply", not reply),
    ):
        if tags.get(tag) and not check:
            return False
    text = getattr(msg, "text", "") or ""
    if "regex" in tags:
        try:
            if not re.search(tags["regex"], text):
                return False
        except re.error:
            return False
    if "startswith" in tags and not text.startswith(tags["startswith"]):
        return False
    if "endswith" in tags and not text.endswith(tags["endswith"]):
        return False
    if "contains" in tags and tags["contains"] not in text:
        return False
    if "from_id" in tags and getattr(event, "sender_id", None) != tags["from_id"]:
        return False
    if "chat_id" in tags and getattr(event, "chat_id", None) != tags["chat_id"]:
        return False
    return True


async def _await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _extract_args(event):
    try:
        text = (getattr(event, "raw_text", "") or "").strip()
        prefix = getattr(event, "_prefix", ".") or "."
        if text.startswith(prefix):
            parts = text[len(prefix):].split(maxsplit=1)
            if len(parts) > 1:
                return parts[1].split()
    except Exception:
        pass
    return []


class RegisterShim:
    MAX_LOOPS_PER_MODULE = 20

    def __init__(self, tetko_kernel, module_instance):
        self.kernel = tetko_kernel
        self.module = module_instance
        self.module_name = getattr(module_instance, "name", type(module_instance).__name__)
        self._tetko_registry = tetko_kernel.registry
        self._commands = {}
        self._bot_commands = {}
        self._watchers = []
        self._events = []
        self._loops = []
        self._methods = {}
        self._aliases = {}
        self._inline_temp_map = {}
        self._on_load_fn = None
        self._on_install_fn = None
        self._uninstall_fn = None

    def command(self, pattern, **kwargs):
        def decorator(fn):
            name = str(pattern).lstrip("./!#^")
            if name.endswith("$"):
                name = name[:-1]
            aliases = kwargs.get("alias") or kwargs.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            doc = kwargs.get("doc_ru") or kwargs.get("doc_en") or kwargs.get("doc") or ""
            if isinstance(doc, dict):
                doc = doc.get("ru") or doc.get("en") or ""

            async def _wrapper(event, *args, **kw):
                return await self._invoke_handler(fn, event)

            _wrapper.__name__ = getattr(fn, "__name__", name)

            try:
                cmd = TetkoCommand(
                    name=name, func=_wrapper, module=self.module,
                    aliases=list(aliases), doc=doc, only_for=None,
                )
                self._tetko_registry.register_command(cmd)
                self._commands[name] = _wrapper
                for a in aliases:
                    self._aliases[a] = name
            except Exception as e:
                log.warning(f"[{self.module_name}] command '{name}': {e}")
            return fn
        return decorator

    def bot_command(self, pattern, **kwargs):
        def decorator(fn):
            name = str(pattern).lstrip("/")
            self._bot_commands[name] = (pattern, fn)
            return fn
        return decorator

    def watcher(self, func=None, bot_client=False, **tags):
        def decorator(fn):
            async def _wrapper(event):
                if not _watcher_passes_filters(event, tags):
                    return
                return await self._invoke_handler(fn, event)
            _wrapper.__name__ = f"mcub_watcher:{self.module_name}:{getattr(fn, '__name__', '?')}"
            try:
                self._tetko_registry.register_watcher(self.module, _wrapper)
                self._watchers.append({
                    "module": self.module_name,
                    "method": getattr(fn, "__name__", "?"),
                    "enabled": True, "tags": dict(tags),
                    "bot_client": bot_client, "wrapper": _wrapper,
                })
            except Exception as e:
                log.warning(f"[{self.module_name}] watcher: {e}")
            return fn
        if func is not None and callable(func):
            return decorator(func)
        return decorator

    def loop(self, interval=60, autostart=True, wait_before=False, **kwargs):
        def decorator(fn):
            if len(self._loops) >= self.MAX_LOOPS_PER_MODULE:
                log.warning(f"[{self.module_name}] max loops, skip {fn.__name__}")
                return InfiniteLoop(lambda: None, interval, autostart=False)
            async def _runner():
                return await self._invoke_handler(fn, None)
            loop_obj = InfiniteLoop(_runner, interval, autostart, wait_before)
            self._loops.append(loop_obj)
            return loop_obj
        return decorator

    def on_load(self, func=None):
        def decorator(fn):
            self._on_load_fn = fn
            return fn
        if func is not None and callable(func):
            return decorator(func)
        return decorator

    def on_install(self, func=None):
        def decorator(fn):
            self._on_install_fn = fn
            return fn
        if func is not None and callable(func):
            return decorator(func)
        return decorator

    def uninstall(self, func=None):
        def decorator(fn):
            self._uninstall_fn = fn
            return fn
        if func is not None and callable(func):
            return decorator(func)
        return decorator

    def method(self, func=None):
        def decorator(fn):
            self._methods[fn.__name__] = fn
            return fn
        if func is not None and callable(func):
            return decorator(func)
        return decorator

    def owner(self, func=None, only_admin=False):
        def decorator(fn):
            async def _wrapper(event):
                admin_id = getattr(self.kernel.context, "admin_id", None)
                sender_id = getattr(event, "sender_id", None)
                if admin_id is None or sender_id is None:
                    return
                if int(sender_id) != int(admin_id):
                    return
                return await self._invoke_handler(fn, event)
            _wrapper.__name__ = f"owner:{getattr(fn, '__name__', '?')}"
            return _wrapper
        if func is not None and callable(func):
            return decorator(func)
        return decorator

    def event(self, event_type, *args, bot_client=False, **kwargs):
        def decorator(fn):
            client = getattr(self.kernel, "bot_client" if bot_client else "client", None)
            if client is None:
                log.warning(f"[{self.module_name}] event '{event_type}': нет клиента")
                return fn
            try:
                from telethon import events as tg_events
                event_map = {
                    "newmessage": tg_events.NewMessage, "message": tg_events.NewMessage,
                    "messageedited": tg_events.MessageEdited, "edited": tg_events.MessageEdited,
                    "callbackquery": tg_events.CallbackQuery, "callback": tg_events.CallbackQuery,
                    "inlinequery": tg_events.InlineQuery, "inline": tg_events.InlineQuery,
                    "chataction": tg_events.ChatAction, "action": tg_events.ChatAction,
                    "raw": tg_events.Raw,
                }
                ev_cls = event_map.get(event_type.lower())
                if ev_cls is None:
                    log.warning(f"[{self.module_name}] неизвестный event '{event_type}'")
                    return fn
                ev_obj = ev_cls(*args, **kwargs)
                async def _wrapper(ev):
                    return await self._invoke_handler(fn, ev)
                _wrapper.__name__ = f"mcub_event:{self.module_name}:{getattr(fn, '__name__', '?')}"
                client.add_event_handler(_wrapper, ev_obj)
                self._events.append((_wrapper, ev_obj, client))
            except Exception as e:
                log.warning(f"[{self.module_name}] event '{event_type}': {e}")
            return fn
        return decorator

    def inline_temp(self, func, ttl=300, **kwargs):
        import uuid
        temp_id = uuid.uuid4().hex[:8]
        self._inline_temp_map[temp_id] = {"handler": func, "expires_at": time.time() + ttl}
        return temp_id

    async def invoke(self, command, args=None, chat_id=None, reply_to=None, **kwargs):
        prefix = getattr(self.kernel.context, "prefix", ".") or "."
        text = f"{prefix}{command}"
        if args:
            text = f"{text} {args}"
        if chat_id is None:
            chat_id = getattr(self.kernel.context, "admin_id", None)
        if chat_id is None:
            return None
        client = getattr(self.kernel, "client", None)
        if client is None:
            return None
        return await client.send_message(chat_id, text, reply_to=reply_to)

    def get_commands(self):
        return dict(self._commands)

    def get_command(self, command):
        return {"handler": self._commands.get(command),
                "owner": self.module_name if command in self._commands else None,
                "docs": {}}

    def get_bot_commands(self):
        return dict(self._bot_commands)

    def get_watchers(self):
        return list(self._watchers)

    def get_events(self):
        return list(self._events)

    def get_loops(self):
        return list(self._loops)

    def get_all_aliases(self):
        return dict(self._aliases)

    def get_command_alias(self, command):
        for a, c in self._aliases.items():
            if c == command:
                return a
        return None

    def get_use_bot(self):
        bot = getattr(self.kernel, "bot_client", None)
        return {"available": bot is not None, "connected": bool(bot), "username": None}

    def disable_watcher(self, module_name, watcher_name):
        for w in self._watchers:
            if w["module"] == module_name and w["method"] == watcher_name:
                w["enabled"] = False
                return True
        return False

    def enable_watcher(self, module_name, watcher_name):
        for w in self._watchers:
            if w["module"] == module_name and w["method"] == watcher_name:
                w["enabled"] = True
                return True
        return False

    def unregister_command(self, cmd):
        if cmd in self._commands:
            del self._commands[cmd]
            return True
        return False

    def unregister_bot_command(self, cmd):
        if cmd in self._bot_commands:
            del self._bot_commands[cmd]
            return True
        return False

    async def _invoke_handler(self, fn, event):
        if event is None:
            try:
                sig = inspect.signature(fn)
                if len(sig.parameters) == 0:
                    return await _await(fn())
                return await _await(fn(self.kernel))
            except Exception as e:
                log.error(f"[{self.module_name}] loop call: {e}")
                return None
        try:
            sig = inspect.signature(fn)
            params = [p for p in sig.parameters.values()
                      if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
            n = len(params)
        except (TypeError, ValueError):
            n = 2
        bound = getattr(fn, "__self__", None)
        if bound is not None:
            try:
                if n <= 1:
                    return await _await(fn(event))
                args_list = _extract_args(event)
                return await _await(fn(event, args_list))
            except Exception as e:
                log.error(f"[{self.module_name}] handler: {e}")
                return None
        try:
            if n <= 1:
                return await _await(fn(event))
            if n == 2:
                return await _await(fn(self.module, event))
            args_list = _extract_args(event)
            return await _await(fn(self.module, event, args_list))
        except Exception as e:
            log.error(f"[{self.module_name}] handler: {e}")
            return None


def run_autostart_loops(register_shim):
    for loop_obj in register_shim.get_loops():
        if loop_obj.autostart:
            try:
                loop_obj.start()
            except Exception as e:
                log.warning(f"[{register_shim.module_name}] autostart: {e}")


def stop_all_loops(register_shim):
    for loop_obj in register_shim.get_loops():
        try:
            loop_obj.stop()
        except Exception:
            pass


__all__ = ["RegisterShim", "InfiniteLoop", "run_autostart_loops", "stop_all_loops"]
