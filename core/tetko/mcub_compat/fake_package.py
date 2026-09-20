"""Фейковые пакеты MCUB: подмена sys.modules на время импорта mcub-модуля.

Этап 1: минимальный набор заглушек, чтобы импорты mcub-модуля не падали
с ImportError. Реальная логика появляется в следующих этапах — сейчас
это безопасные no-op / алиасы на tetko-эквиваленты.
"""
from __future__ import annotations

import contextlib
import sys
import types
from typing import Any, Iterator


# ────────────────────────────────────────────────────────────────────
#  Базовые заглушки (будут заменены на реальные в этапах 2-7)
# ────────────────────────────────────────────────────────────────────

class _Unavailable:
    """Объект-заглушка: обращение к нему кидает понятную ошибку."""

    def __init__(self, name: str):
        self._name = name

    def _fail(self, *a, **kw):
        raise NotImplementedError(
            f"[mcub_compat этап 1] '{self._name}' ещё не реализован. "
            "Дождись следующих этапов."
        )

    def __call__(self, *a, **kw):
        return self._fail()

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _Unavailable(f"{self._name}.{item}")


def _make_module(name: str, attrs: dict[str, Any] | None = None) -> types.ModuleType:
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    return mod


# ────────────────────────────────────────────────────────────────────
#  Минимальный ModuleBase (реальный класс — нужен для isinstance)
# ────────────────────────────────────────────────────────────────────

from .module_base import MCUBModuleBase as _MCUB_ModuleBase
from .module_base import (
    command as _mcub_command,
    callback as _mcub_callback,
    watcher as _mcub_watcher,
    loop as _mcub_loop,
    bot_command as _mcub_bot_command,
    inline as _mcub_inline,
)

def _noop_decorator(*args, **kwargs):
    """Декоратор-заглушка: возвращает функцию без изменений."""
    def deco(fn):
        return fn
    if args and callable(args[0]) and not kwargs:
        return args[0]
    return deco


# ────────────────────────────────────────────────────────────────────
#  Регистрация фейков в sys.modules
# ────────────────────────────────────────────────────────────────────

def _mcub_event(event_type, *args, bot_client=False, **kwargs):
    """MCUB-декоратор @event — регистрирует обработчик события."""
    def deco(fn):
        meta = list(getattr(fn, "_mcub_events", []))
        meta.append((event_type, args, kwargs))
        fn._mcub_events = meta
        return fn
    return deco


def _build_fake_modules() -> dict[str, types.ModuleType]:
    fake: dict[str, types.ModuleType] = {}

    # ── core.lib.loader.module_base ──
    module_base = _make_module("core.lib.loader.module_base", {
        "ModuleBase": _MCUB_ModuleBase,
        "command": _mcub_command,
        "callback": _mcub_callback,
        "watcher": _mcub_watcher,
        "loop": _mcub_loop,
        "bot_command": _mcub_bot_command,
        "inline": _mcub_inline,
        "event": _mcub_event,
    })
    fake["core.lib.loader.module_base"] = module_base

    # ── core.lib.loader.kernel_proxy ──
    def _wrap_event_for_module(event, *a, **kw):
        return event

    class _EventProxy:
        def __init__(self, event, *a, **kw):
            self._event = event
        def __getattr__(self, item):
            return getattr(self._event, item)

    kernel_proxy = _make_module("core.lib.loader.kernel_proxy", {
        "wrap_event_for_module": _wrap_event_for_module,
        "EventProxy": _EventProxy,
        "ModuleKernelProxy": _Unavailable("ModuleKernelProxy"),
        "ModuleRegisterProxy": _Unavailable("ModuleRegisterProxy"),
        "ClientProxy": _Unavailable("ClientProxy"),
        "DatabaseProxy": _Unavailable("DatabaseProxy"),
        "ConfigProxy": _Unavailable("ConfigProxy"),
        "CallInsecure": type("CallInsecure", (Exception,), {}),
        "get_module_kernel": lambda k, *a, **kw: k,
        "get_module_client": lambda k, *a, **kw: getattr(k, "client", None),
        "get_module_db": lambda k, *a, **kw: getattr(k, "db_manager", None),
        "get_module_register": lambda k, *a, **kw: getattr(k, "register", None),
        "get_module_config": lambda k, *a, **kw: getattr(k, "config", {}),
    })
    fake["core.lib.loader.kernel_proxy"] = kernel_proxy

    # ── core.lib.loader.repository ──
    def _validate_remote_url(url):
        return True, ""

    fake["core.lib.loader.repository"] = _make_module(
        "core.lib.loader.repository",
        {"validate_remote_url": _validate_remote_url},
    )

    # ── core.lib.types (и подпакеты) ──
    types_mod = _make_module("core.lib.types", {
        "Event": _Unavailable("Event"),
        "InlineMessage": _Unavailable("InlineMessage"),
        "Message": _Unavailable("Message"),
        "Kernel": _Unavailable("Kernel"),
        "Client": _Unavailable("Client"),
        "Register": _Unavailable("Register"),
    })
    fake["core.lib.types"] = types_mod
    fake["core.lib.types.event"] = _make_module("core.lib.types.event", {"Event": _Unavailable("Event")})
    fake["core.lib.types.client"] = _make_module("core.lib.types.client", {"Client": _Unavailable("Client")})
    fake["core.lib.types.kernel"] = _make_module("core.lib.types.kernel", {"Kernel": _Unavailable("Kernel")})
    fake["core.lib.types.message"] = _make_module("core.lib.types.message", {"Message": _Unavailable("Message")})
    fake["core.lib.types.register"] = _make_module("core.lib.types.register", {"Register": _Unavailable("Register")})

    # ── core.lib.utils.* ──
    fake["core.lib.utils"] = _make_module("core.lib.utils", {"purge_caches": lambda *a, **kw: {}})
    fake["core.lib.utils.colors"] = _make_module("core.lib.utils.colors", {
        "Colors": type("Colors", (), {
            "RESET": "", "BOLD": "", "BRIGHT_GREEN": "", "BRIGHT_RED": "",
            "YELLOW": "", "CYAN": "", "MUTED": "", "BRIGHT_WHITE": "",
            "paint": staticmethod(lambda t, *a: t),
            "gradient_multicolor": staticmethod(lambda t, *a, **kw: t),
        }),
    })
    fake["core.lib.utils.exceptions"] = _make_module("core.lib.utils.exceptions", {
        "CommandConflictError": type("CommandConflictError", (Exception,), {}),
        "CallInsecure": type("CallInsecure", (Exception,), {}),
        "McubTelethonError": type("McubTelethonError", (Exception,), {}),
    })
    fake["core.lib.utils.logger"] = _make_module("core.lib.utils.logger", {
        "KernelLogger": _Unavailable("KernelLogger"),
        "setup_logging": lambda *a, **kw: None,
        "setup_telegram_logging": lambda *a, **kw: None,
        "ErrorFormatter": type("ErrorFormatter", (), {
            "format_full_traceback": staticmethod(lambda tb: tb),
        }),
        "mask_sensitive_data": lambda v: v,
    })
    fake["core.lib.utils.case_insensitive"] = _make_module(
        "core.lib.utils.case_insensitive", {"CaseInsensitiveDict": dict})
    fake["core.lib.utils.event_helpers"] = _make_module("core.lib.utils.event_helpers", {
        "make_simple_event": lambda *a, **kw: None,
        "run_and_capture": _Unavailable("run_and_capture"),
    })

    # ── core.lib.base.* ──
    fake["core.lib.base"] = _make_module("core.lib.base", {})
    fake["core.lib.base.client"] = _make_module("core.lib.base.client", {"ClientManager": _Unavailable("ClientManager")})
    fake["core.lib.base.config"] = _make_module("core.lib.base.config", {"ConfigManager": _Unavailable("ConfigManager")})
    fake["core.lib.base.database"] = _make_module("core.lib.base.database", {"DatabaseManager": _Unavailable("DatabaseManager")})
    fake["core.lib.base.permissions"] = _make_module("core.lib.base.permissions", {
        "CallbackPermissionManager": _Unavailable("CallbackPermissionManager"),
        "check_trust": _Unavailable("check_trust"),
    })

    # ── core.lib.time.* ──
    fake["core.lib.time"] = _make_module("core.lib.time", {})
    fake["core.lib.time.cache"] = _make_module("core.lib.time.cache", {"TTLCache": _Unavailable("TTLCache")})
    fake["core.lib.time.scheduler"] = _make_module("core.lib.time.scheduler", {"TaskScheduler": _Unavailable("TaskScheduler")})


    # ── core_inline.* ──
    fake["core_inline"] = _make_module("core_inline", {})
    fake["core_inline.bot"] = _make_module("core_inline.bot", {"InlineBot": _Unavailable("InlineBot")})
    fake["core_inline.handlers"] = _make_module("core_inline.handlers", {"InlineHandlers": _Unavailable("InlineHandlers")})

    # ── utils.* (заглушки; реальный пакет поставим в этапе 5) ──
    fake["utils.arg_parser"] = _make_module("utils.arg_parser", {
        "ArgumentParser": _Unavailable("ArgumentParser"),
        "ArgumentValidator": _Unavailable("ArgumentValidator"),
        "extract_command": _Unavailable("extract_command"),
        "parse_arguments": _Unavailable("parse_arguments"),
        "parse_kwargs": _Unavailable("parse_kwargs"),
        "split_args": _Unavailable("split_args"),
        "PipelineParser": _Unavailable("PipelineParser"),
        "PipelineSegment": _Unavailable("PipelineSegment"),
    })
    fake["utils.helpers"] = _make_module("utils.helpers", {})
    fake["utils.custom_placeholders"] = _make_module("utils.custom_placeholders", {})
    fake["utils.emoji_parser"] = _make_module("utils.emoji_parser", {"emoji_parser": _Unavailable("emoji_parser")})
    fake["utils.html_parser"] = _make_module("utils.html_parser", {
        "parse_html": _Unavailable("parse_html"),
        "telegram_to_html": _Unavailable("telegram_to_html"),
    })
    fake["utils.message_helpers"] = _make_module("utils.message_helpers", {})
    fake["utils.raw_html"] = _make_module("utils.raw_html", {})
    fake["utils.restart"] = _make_module("utils.restart", {
        "restart_kernel": _Unavailable("restart_kernel"),
        "read_restart_context": _Unavailable("read_restart_context"),
        "RestartContext": _Unavailable("RestartContext"),
        "write_restart_file": _Unavailable("write_restart_file"),
    })
    fake["utils.platform"] = _make_module("utils.platform", {
        "PlatformDetector": _Unavailable("PlatformDetector"),
        "get_platform": lambda: "unknown",
    })

    return fake


# ────────────────────────────────────────────────────────────────────
#  Публичный API
# ────────────────────────────────────────────────────────────────────

_FAKE_MODULES: dict[str, types.ModuleType] | None = None
_SAVED_ORIGINALS: dict[str, Any] = {}


def _patch_telethon_message():
    """Monkey-patch Telethon Message: добавляет MCUB-совместимые атрибуты.

    MCUB-модули используют message.html_text, message.text, message.markdown_text.
    Telethon даёт .raw_text / .message / .text (уже есть).
    Добавляем .html_text и .markdown_text.
    """
    try:
        from telethon.tl.custom.message import Message
    except Exception:
        return

    # Если уже пропатчен
    if getattr(Message, "_mcub_patched", False):
        return

    def _get_html_text(self):
        """MCUB html_text — HTML-разметка сообщения (entities → HTML).

        Используем telethon.extensions.html.unparse (entities → html).
        Fallback — raw без escape.
        """
        raw = getattr(self, "raw_text", None) or getattr(self, "message", "") or ""
        entities = getattr(self, "entities", None) or []
        if entities:
            try:
                from telethon.extensions import html as _html_ext
                return _html_ext.unparse(raw, entities)
            except Exception:
                pass
        return raw

    def _get_markdown_text(self):
        return getattr(self, "raw_text", None) or getattr(self, "message", "") or ""

    try:
        if not hasattr(Message, "html_text"):
            Message.html_text = property(_get_html_text)
        if not hasattr(Message, "markdown_text"):
            Message.markdown_text = property(_get_markdown_text)
        Message._mcub_patched = True
    except Exception:
        pass


def install_fakes() -> None:
    """Заменяет sys.modules на MCUB-фейки. Сохраняет оригиналы для restore."""
    global _FAKE_MODULES
    _patch_telethon_message()
    if _FAKE_MODULES is None:
        _FAKE_MODULES = _build_fake_modules()

    for name, mod in _FAKE_MODULES.items():
        # Запоминаем что было — только в первый раз
        if name not in _SAVED_ORIGINALS:
            _SAVED_ORIGINALS[name] = sys.modules.get(name)
        sys.modules[name] = mod


def restore_fakes() -> None:
    """Восстанавливает оригинальные sys.modules записи."""
    for name, original in _SAVED_ORIGINALS.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original
    _SAVED_ORIGINALS.clear()


@contextlib.contextmanager
def fakes_active() -> Iterator[None]:
    """Контекст: sys.modules содержит MCUB-фейки внутри блока."""
    install_fakes()
    try:
        yield
    finally:
        restore_fakes()


__all__ = ["install_fakes", "restore_fakes", "fakes_active"]
