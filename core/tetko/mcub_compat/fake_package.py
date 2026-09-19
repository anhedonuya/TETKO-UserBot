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

class _MCUB_ModuleBase:
    """Заглушка базового класса. Реальная реализация — в этапе 3."""

    name: str = "Unnamed"
    version: str = "0.0.0"
    author: str = "unknown"
    description: dict = {}
    dependencies: list = []
    banner_url: str | None = None
    strings: dict = {}
    config: Any = None

    def __init__(self, kernel=None, client=None, register=None):
        self.kernel = kernel
        self.client = client
        self._register = register

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass


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

def _build_fake_modules() -> dict[str, types.ModuleType]:
    fake: dict[str, types.ModuleType] = {}

    # ── core.lib.loader.module_base ──
    module_base = _make_module("core.lib.loader.module_base", {
        "ModuleBase": _MCUB_ModuleBase,
        "command": _noop_decorator,
        "callback": _noop_decorator,
        "watcher": _noop_decorator,
        "loop": _noop_decorator,
        "bot_command": _noop_decorator,
        "inline": _noop_decorator,
    })
    fake["core.lib.loader.module_base"] = module_base

    # ── core.lib.loader.module_config ──
    module_config = _make_module("core.lib.loader.module_config", {
        "ModuleConfig": _Unavailable("ModuleConfig"),
        "ConfigValue": _Unavailable("ConfigValue"),
        "ValidationError": type("ValidationError", (Exception,), {}),
        # валидаторы
        "Boolean": _Unavailable("Boolean"),
        "Integer": _Unavailable("Integer"),
        "Float": _Unavailable("Float"),
        "String": _Unavailable("String"),
        "Choice": _Unavailable("Choice"),
        "List": _Unavailable("List"),
        "DictType": _Unavailable("DictType"),
        "Secret": _Unavailable("Secret"),
        "Placeholders": _Unavailable("Placeholders"),
        "RegExp": _Unavailable("RegExp"),
        "Link": _Unavailable("Link"),
        "TelegramID": _Unavailable("TelegramID"),
        "EntityLike": _Unavailable("EntityLike"),
        "Emoji": _Unavailable("Emoji"),
        "MultiChoice": _Unavailable("MultiChoice"),
        "Union": _Unavailable("Union"),
        "Hidden": _Unavailable("Hidden"),
        "NoneType": _Unavailable("NoneType"),
        # UI-элементы
        "Group": _Unavailable("Group"),
        "Row": _Unavailable("Row"),
        "Divider": _Unavailable("Divider"),
        "Url": _Unavailable("Url"),
        "Callback": _Unavailable("Callback"),
        "Status": _Unavailable("Status"),
        "Notice": _Unavailable("Notice"),
        "Answer": _Unavailable("Answer"),
        "Buttons": _Unavailable("Buttons"),
    })
    fake["core.lib.loader.module_config"] = module_config

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

    # ── core.langpacks ──
    _LP_CACHE: dict = {
        "en": {"kernel": {"welcome": "Welcome"}, "core_inline": {"welcome": "Welcome"}},
        "ru": {"kernel": {"welcome": "Добро пожаловать"}, "core_inline": {"welcome": "Добро пожаловать"}},
    }
    fake["core.langpacks"] = _make_module("core.langpacks", {
        "get_langpacks": lambda: _LP_CACHE,
        "get_module_strings": lambda module_name, locale: _LP_CACHE.get(locale, {}).get(module_name, {}),
        "get_available_locales": lambda: ["en", "ru"],
        "clear_langpacks_cache": lambda: None,
    })

    # ── core_inline.* ──
    fake["core_inline"] = _make_module("core_inline", {})
    fake["core_inline.api"] = _make_module("core_inline.api", {})
    fake["core_inline.api.inline"] = _make_module("core_inline.api.inline", {
        "make_cb_button": _Unavailable("make_cb_button"),
    })
    fake["core_inline.lib"] = _make_module("core_inline.lib", {})
    fake["core_inline.lib.manager"] = _make_module("core_inline.lib.manager", {
        "InlineManager": _Unavailable("InlineManager"),
    })
    fake["core_inline.bot"] = _make_module("core_inline.bot", {"InlineBot": _Unavailable("InlineBot")})
    fake["core_inline.handlers"] = _make_module("core_inline.handlers", {"InlineHandlers": _Unavailable("InlineHandlers")})

    # ── utils.* (заглушки; реальный пакет поставим в этапе 5) ──
    fake["utils"] = _make_module("utils", {
        "answer": _Unavailable("utils.answer"),
        "answer_file": _Unavailable("utils.answer_file"),
        "config_placeholders": _Unavailable("utils.config_placeholders"),
        "format_placeholders": _Unavailable("utils.format_placeholders"),
        "get_placeholders": _Unavailable("utils.get_placeholders"),
        "list_placeholder_keys": _Unavailable("utils.list_placeholder_keys"),
        "placeholders": _noop_decorator,
        "register_decorated_placeholders": _Unavailable("utils.register_decorated_placeholders"),
        "register_placeholder": _Unavailable("utils.register_placeholder"),
        "resolve_placeholders": _Unavailable("utils.resolve_placeholders"),
        "unregister_placeholder": _Unavailable("utils.unregister_placeholder"),
        "unregister_scope": _Unavailable("utils.unregister_scope"),
        "get_args": _Unavailable("utils.get_args"),
        "get_args_raw": _Unavailable("utils.get_args_raw"),
        "get_args_html": _Unavailable("utils.get_args_html"),
        "get_prefix": lambda *a, **kw: ".",
        "get_lang": lambda *a, **kw: "ru",
        "make_button": _Unavailable("utils.make_button"),
        "make_buttons": _Unavailable("utils.make_buttons"),
        "restart_kernel": _Unavailable("utils.restart_kernel"),
    })
    fake["utils.strings"] = _make_module("utils.strings", {
        "Strings": _Unavailable("utils.strings.Strings"),
        "get_available_locales": lambda: ["en", "ru"],
        "reload_packs": lambda: None,
    })
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
    fake["utils.security"] = _make_module("utils.security", {
        "get_db_path": lambda *a, **kw: "userbot.db",
        "get_config_path": lambda *a, **kw: "config.json",
        "get_session_path": lambda *a, **kw: "user_session.session",
        "session_exists": lambda *a, **kw: False,
        "safe_extract_archive": _Unavailable("safe_extract_archive"),
        "safe_extract_zip": _Unavailable("safe_extract_zip"),
        "safe_extract_tar": _Unavailable("safe_extract_tar"),
    })
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


def install_fakes() -> None:
    """Заменяет sys.modules на MCUB-фейки. Сохраняет оригиналы для restore."""
    global _FAKE_MODULES
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
