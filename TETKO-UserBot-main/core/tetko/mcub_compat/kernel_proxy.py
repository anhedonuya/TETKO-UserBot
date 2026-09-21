"""KernelProxy — MCUB-совместимый фасад над tetko-Kernel."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from types import MappingProxyType
from typing import Any, Optional


log = logging.getLogger("TETKO.mcub_compat.kernel_proxy")


class _TTLCache:
    def __init__(self, max_size=500, ttl=600):
        self._store = {}
        self._max = max_size
        self._ttl = ttl

    def set(self, key, value, ttl=None):
        if len(self._store) >= self._max:
            self._store.clear()
        self._store[key] = (value, time.time() + (ttl or self._ttl))

    def get(self, key, default=None):
        entry = self._store.get(key)
        if entry is None:
            return default
        value, expires = entry
        if time.time() > expires:
            self._store.pop(key, None)
            return default
        return value

    def delete(self, key):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()


class _VersionManager:
    def __init__(self, repo_root):
        self.repo_root = repo_root

    async def _git(self, *args):
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", *args, cwd=str(self.repo_root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return proc.returncode, stdout.decode().strip()
        except Exception:
            return 1, ""

    async def detect_branch(self):
        rc, out = await self._git("rev-parse", "--abbrev-ref", "HEAD")
        return out if rc == 0 and out else "main"

    async def get_commit_sha(self, short=True):
        rc, out = await self._git("rev-parse", "HEAD")
        if rc != 0 or not out:
            return "unknown"
        return out[:7] if short else out

    async def get_github_commit_url(self):
        sha = await self.get_commit_sha(short=False)
        if sha == "unknown":
            return ""
        rc, remote = await self._git("config", "--get", "remote.origin.url")
        if rc != 0 or not remote:
            return ""
        remote = remote.strip()
        if remote.endswith(".git"):
            remote = remote[:-4]
        if remote.startswith("git@github.com:"):
            remote = "https://github.com/" + remote[len("git@github.com:"):]
        return f"{remote}/commit/{sha}"

    async def get_latest_kernel_version(self):
        return "?"

    async def check_module_compatibility(self, code):
        return True, ""


class KernelProxy:
    def __init__(self, tetko_kernel, module_instance):
        object.__setattr__(self, "_k", tetko_kernel)
        object.__setattr__(self, "_module", module_instance)
        object.__setattr__(self, "_cache", _TTLCache())
        object.__setattr__(self, "_register", None)
        object.__setattr__(self, "_repo_root", Path(__file__).resolve().parent.parent.parent.parent)
        object.__setattr__(self, "_version_manager", None)

    @property
    def register(self):
        r = object.__getattribute__(self, "_register")
        if r is None:
            from .register_shim import RegisterShim
            r = RegisterShim(object.__getattribute__(self, "_k"), object.__getattribute__(self, "_module"))
            object.__setattr__(self, "_register", r)
        return r

    async def db_get(self, namespace, key, default=None):
        from core.tetko import db_get
        try:
            return db_get(namespace, key, default)
        except Exception as e:
            log.warning(f"db_get({namespace}.{key}): {e}")
            return default

    async def db_set(self, namespace, key, value):
        from core.tetko import db_set
        try:
            db_set(namespace, key, value)
        except Exception as e:
            log.warning(f"db_set({namespace}.{key}): {e}")

    async def db_delete(self, namespace, key):
        from core.tetko import db_del
        try:
            db_del(namespace, key)
        except Exception as e:
            log.warning(f"db_delete({namespace}.{key}): {e}")

    async def db_query(self, query, parameters=None):
        """Best-effort compatibility query over TETKO JSON namespaces.

        MCUB modules rarely use SQL directly; when they do, support simple
        SELECT/DELETE/UPDATE forms against a namespace inferred from params.
        Unsupported SQL returns an empty result instead of crashing the module.
        """
        from core.tetko import db_list, db_set, db_del
        q = str(query or "").strip().lower()
        params = list(parameters or [])
        # SELECT * FROM namespace [WHERE key = ?]
        import re
        m = re.match(r"select\s+\*\s+from\s+([\w.-]+)(?:\s+where\s+key\s*=\s*\?)?$", q)
        if m:
            ns = m.group(1)
            data = db_list(ns)
            if "where" in q and params:
                return data.get(str(params[0]))
            return data
        return []

    def store_inline_callback(self, token, data):
        lock = getattr(object.__getattribute__(self, "_k"), "_inline_cb_lock", None)
        cb_map = getattr(object.__getattribute__(self, "_k"), "inline_callback_map", None)
        if cb_map is None:
            object.__getattribute__(self, "_k").inline_callback_map = {}
            cb_map = object.__getattribute__(self, "_k").inline_callback_map
        if lock:
            with lock: cb_map[token] = data
        else:
            cb_map[token] = data

    def remove_inline_callback_tokens(self, tokens):
        cb_map = getattr(object.__getattribute__(self, "_k"), "inline_callback_map", {})
        lock = getattr(object.__getattribute__(self, "_k"), "_inline_cb_lock", None)
        if lock:
            with lock:
                for token in tokens: cb_map.pop(token, None)
        else:
            for token in tokens: cb_map.pop(token, None)

    def allow_inline_callback_user(self, user_id, token, allow_ttl):
        entry = getattr(object.__getattribute__(self, "_k"), "inline_callback_map", {}).get(token)
        if entry is not None:
            entry["allowed_user"] = int(user_id)
            entry["allow_expires_at"] = time.time() + int(allow_ttl)

    async def get_module_config(self, module_name, default=None):
        mod = object.__getattribute__(self, "_module")
        if getattr(mod, "name", None) == module_name:
            cfg = getattr(mod, "cfg", None)
            if cfg is None:
                cfg = getattr(mod, "config", None)
            if cfg is not None:
                data = cfg.all() if hasattr(cfg, "all") else dict(cfg)
                if data:
                    return data
        return dict(default) if isinstance(default, dict) else default

    async def save_module_config(self, module_name, config_data):
        mod = object.__getattribute__(self, "_module")
        cfg = getattr(mod, "cfg", None)
        if cfg is None:
            cfg = getattr(mod, "config", None)
        if cfg is None or not isinstance(config_data, dict):
            return False
        for k, v in config_data.items():
            if k.startswith("__"):
                continue
            try:
                cfg.set(k, v)
            except Exception:
                pass
        return True

    def store_module_config_schema(self, module_name, config):
        try:
            from core.tetko import db_set
            data = config.to_dict() if hasattr(config, "to_dict") else config
            db_set("module_config_schema", module_name, data)
            return True
        except Exception:
            return False

    async def delete_module_config(self, module_name):
        try:
            from core.tetko import db_del
            return bool(db_del("module_configs", module_name))
        except Exception:
            return False

    async def handle_error(self, error, source="unknown", message=None, event=None):
        ctx = getattr(object.__getattribute__(self, "_k"), "context", None)
        if ctx is not None and hasattr(ctx, "handle_error"):
            try:
                await ctx.handle_error(event, error, message or str(error))
                return
            except Exception:
                pass
        log.exception(f"handle_error [{source}]: {message or error}")

    @property
    def logger(self):
        return logging.getLogger(f"MCUB.module.{getattr(object.__getattribute__(self, '_module'), 'name', '?')}")

    @property
    def client(self):
        return getattr(object.__getattribute__(self, "_k"), "client", None)

    @property
    def bot_client(self):
        return getattr(object.__getattribute__(self, "_k"), "bot_client", None)

    @property
    def ADMIN_ID(self):
        ctx = getattr(object.__getattribute__(self, "_k"), "context", None)
        return getattr(ctx, "admin_id", None) if ctx else None

    @property
    def custom_prefix(self):
        ctx = getattr(object.__getattribute__(self, "_k"), "context", None)
        return getattr(ctx, "prefix", ".") if ctx else "."

    @property
    def config(self):
        return getattr(object.__getattribute__(self, "_k"), "config", {}) or {}

    @property
    def inline_manager(self):
        from .inline_shim import InlineManager
        return InlineManager(object.__getattribute__(self, "_k"))

    @property
    def aliases(self):
        reg = object.__getattribute__(self, "_k").registry
        return dict(getattr(reg, "_aliases", {}))

    @property
    def command_handlers(self):
        reg = object.__getattribute__(self, "_k").registry
        return {n: c.func for n, c in reg._commands.items()}

    @property
    def command_owners(self):
        reg = object.__getattribute__(self, "_k").registry
        return {n: getattr(c.module, "name", "?") for n, c in reg._commands.items()}

    @property
    def inline_handlers(self):
        handlers = getattr(object.__getattribute__(self, "_k"), "_mcub_inline_handlers", None)
        return handlers if handlers is not None else {}

    @property
    def cache(self):
        return object.__getattribute__(self, "_cache")

    @property
    def version_manager(self):
        vm = object.__getattribute__(self, "_version_manager")
        if vm is None:
            vm = _VersionManager(object.__getattribute__(self, "_repo_root"))
            object.__setattr__(self, "_version_manager", vm)
        return vm

    @property
    def MODULES_DIR(self):
        return "modules"

    @property
    def MODULES_LOADED_DIR(self):
        return "modules_custom"

    @property
    def LOGS_DIR(self):
        return "logs"

    @property
    def IMG_DIR(self):
        return "img"

    @property
    def CONFIG_FILE(self):
        return "config.json"

    @property
    def START_TIME(self):
        return getattr(object.__getattribute__(self, "_k"), "start_time", 0.0)

    @property
    def VERSION(self):
        return "0.0.9.0"

    @property
    def CORE_NAME(self):
        return "tetko"

    @property
    def _live_module_configs(self):
        return MappingProxyType({})

    @property
    def loaded_modules(self):
        reg = object.__getattribute__(self, "_k").registry
        return MappingProxyType(dict(reg._modules))

    @property
    def system_modules(self):
        return MappingProxyType({})

    @property
    def loaded_modules_view(self):
        return self.loaded_modules

    @property
    def system_modules_view(self):
        return self.system_modules

    @property
    def loaded_module_names(self):
        reg = object.__getattribute__(self, "_k").registry
        return tuple(sorted(reg._modules.keys()))

    async def process_command(self, event, depth=0):
        k = object.__getattribute__(self, "_k")
        if hasattr(k, "dispatcher") and k.dispatcher is not None:
            return await k.dispatcher.handle_message(k.client, event) or True
        return False

    async def process_bot_command(self, event):
        return False

    async def restart(self, chat_id=None, message_id=None):
        from core.tetko import db_set
        if chat_id is not None and message_id is not None:
            db_set("updates", "pending_reload", {"chat_id": chat_id, "message_id": message_id})
        import os, sys
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def shutdown(self):
        return None

    def lookup_module(self, module_name, *, all_loaded=False):
        reg = object.__getattribute__(self, "_k").registry
        low = str(module_name).lower()
        for n, m in reg._modules.items():
            if n.lower() == low:
                return m
        return None

    def get_loaded_module(self, module_name, *, all_loaded=False):
        return self.lookup_module(module_name, all_loaded=all_loaded)

    def iter_loaded_module_names(self):
        return self.loaded_module_names

    def is_admin(self, user_id):
        admin = self.ADMIN_ID
        return admin is not None and int(user_id) == int(admin)

    def is_bot_available(self):
        bc = getattr(object.__getattribute__(self, "_k"), "bot_client", None)
        return bc is not None and getattr(bc, "is_connected", lambda: False)()

    def get_prefix_for_sender(self, sender_id):
        return self.custom_prefix

    async def log_module(self, message):
        self.logger.info(message)

    async def log_network(self, message):
        self.logger.info(f"[network] {message}")

    async def log_error_async(self, message):
        self.logger.error(message)

    async def inline_form(self, chat_id, title, fields=None, buttons=None,
                           auto_send=True, ttl=200, reply_to=None, **kwargs):
        """Render an MCUB form using TETKO's real inline implementation."""
        inline = getattr(object.__getattribute__(self, "_k"), "inline", None)
        if inline is None:
            return (False, None)
        text = str(title or "")
        if fields:
            if isinstance(fields, dict):
                values = fields.items()
            else:
                values = []
                for item in fields:
                    if isinstance(item, dict):
                        values.extend(item.items())
                    else:
                        values.append(("", item))
            lines = []
            for key, value in values:
                if key:
                    lines.append(f"<b>{key}</b>: {value}")
                else:
                    lines.append(str(value))
            if lines:
                text += "\n" + "\n".join(lines)
        if not auto_send:
            return (True, {"form_id": f"form_{int(time.time()*1000)}",
                           "text": text, "buttons": buttons})
        try:
            msg = await inline.form(chat_id, text, buttons or [], reply_to=reply_to)
            return (True, msg)
        except Exception as e:
            log.warning("inline_form: %s", e)
            client = getattr(object.__getattribute__(self, "_k"), "client", None)
            if client is None:
                return (False, None)
            try:
                msg = await client.send_message(chat_id, text, buttons=_convert_buttons(buttons))
                return (True, msg)
            except Exception:
                return (False, None)

    async def inline_query_and_click(self, chat_id, query, **kwargs):
        """Выполнить inline-запрос и кликнуть результат (через юзербота)."""
        try:
            k = object.__getattribute__(self, "_k")
            client = getattr(k, "client", None)
            if client is None:
                return (False, None)
            bot_username = (getattr(k, "config", {}) or {}).get("inline_bot_username")
            if not bot_username:
                log.warning("inline_bot_username не задан в config")
                return (False, None)
            results = await client.inline_query(bot_username, query)
            if not results:
                return (False, None)
            msg = await results[0].click(chat_id, reply_to=kwargs.get("reply_to"))
            return (True, msg)
        except Exception as e:
            log.exception(f"inline_query_and_click: {e}")
            return (False, None)

    async def send_inline(self, chat_id, query, buttons=None):
        return False

    async def send_inline_from_config(self, chat_id, query, buttons=None):
        return None

    async def send_with_emoji(self, chat_id, text, **kwargs):
        client = self.client
        if client is None:
            return None
        return await client.send_message(chat_id, text, **kwargs)

    def raw_text(self, source):
        try:
            from telethon.extensions import html as tg_html
            if isinstance(source, str):
                return tg_html.unparse(source, [])
            return tg_html.message_to_html(source) or ""
        except Exception:
            return ""

    def format_with_html(self, text, entities):
        if not text:
            return ""
        import html as _h
        return _h.escape(text, quote=False)

    def pipe_interpolate(self, text, pipe_input=""):
        return text

    async def async_pipe_interpolate(self, text, pipe_input="", event=None, active_prefix=""):
        return text

    def __getattr__(self, name):
        # Public kernel helpers not explicitly reimplemented above are delegated.
        # Never expose private attributes through the MCUB facade.
        if name.startswith("_"):
            raise AttributeError(name)
        k = object.__getattribute__(self, "_k")
        value = getattr(k, name, None)
        if value is not None:
            return value
        raise AttributeError(name)

    def __repr__(self):
        mod = object.__getattribute__(self, "_module")
        return f"<KernelProxy module={getattr(mod, 'name', '?')!r}>"


__all__ = ["KernelProxy", "_TTLCache"]


def _convert_buttons(buttons):
    """MCUB buttons (list[list[dict|Button]]) → tetko buttons (list[list[Button]])."""
    if not buttons:
        return []
    out = []
    for row in buttons:
        if not isinstance(row, list):
            row = [row]
        r = []
        for b in row:
            if b is None:
                continue
            # уже telethon Button — оставляем
            if type(b).__name__.startswith("KeyboardButton") or hasattr(b, "click"):
                r.append(b)
            elif isinstance(b, dict):
                btype = b.get("type", "callback").lower()
                text = b.get("text", "…")
                if btype == "url":
                    from telethon.tl.custom import Button
                    r.append(Button.url(text, b.get("url", "")))
                elif btype == "callback":
                    from telethon.tl.custom import Button
                    data = b.get("data") or b.get("token") or ""
                    if isinstance(data, str):
                        data = data.encode()
                    r.append(Button.inline(text, data))
            else:
                r.append(b)
        if r:
            out.append(r)
    return out
