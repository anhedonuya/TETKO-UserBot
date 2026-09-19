"""Загрузчик MCUB-модулей поверх TETKO."""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from .detector import is_mcub_module
from .kernel_proxy import KernelProxy
from .module_base import MCUBModuleBase
from .register_shim import RegisterShim, run_autostart_loops, stop_all_loops


log = logging.getLogger("TETKO.mcub_compat.loader")


def _install_fakes() -> None:
    import types

    # Создаём всю цепочку пакетов, если их нет в sys.modules
    for pkg in (
        "core.lib",
        "core.lib.loader",
        "core.lib.types",
        "core.lib.base",
        "core.lib.utils",
        "core.lib.time",
        "core_inline",
        "core_inline.api",
        "core_inline.lib",
    ):
        if pkg not in sys.modules:
            mod = types.ModuleType(pkg)
            mod.__path__ = []
            sys.modules[pkg] = mod

    mb = sys.modules.get("core.lib.loader.module_base")
    if mb is None:
        mb = types.ModuleType("core.lib.loader.module_base")
        sys.modules["core.lib.loader.module_base"] = mb
    mb.ModuleBase = MCUBModuleBase
    mb.command = _stub_decorator
    mb.callback = _stub_decorator
    mb.watcher = _stub_decorator
    mb.loop = _stub_decorator
    mb.bot_command = _stub_decorator
    mb.inline = _stub_decorator

    kp = sys.modules.get("core.lib.loader.kernel_proxy")
    if kp is None:
        kp = types.ModuleType("core.lib.loader.kernel_proxy")
        sys.modules["core.lib.loader.kernel_proxy"] = kp
    kp.wrap_event_for_module = lambda e, *a, **kw: e

    # core.lib.types
    t = sys.modules.get("core.lib.types")
    if t is not None:
        t.Event = object
        t.InlineMessage = object
        t.Message = object
        t.Kernel = object
        t.Client = object
        t.Register = object

    # core.lib.types.event и другие подпакеты — как отдельные модули
    for sub in ("event", "client", "kernel", "message", "register"):
        full = f"core.lib.types.{sub}"
        if full not in sys.modules:
            m = types.ModuleType(full)
            sys.modules[full] = m
        m = sys.modules[full]
        if sub == "event":
            m.Event = object
        elif sub == "client":
            m.Client = object
        elif sub == "kernel":
            m.Kernel = object
        elif sub == "message":
            m.Message = object
        elif sub == "register":
            m.Register = object

    # core_inline.api.inline — make_cb_button заглушка
    if "core_inline.api.inline" not in sys.modules:
        m = types.ModuleType("core_inline.api.inline")
        sys.modules["core_inline.api.inline"] = m
    sys.modules["core_inline.api.inline"].make_cb_button = _stub_decorator

    # core_inline.lib.manager — InlineManager заглушка
    if "core_inline.lib.manager" not in sys.modules:
        m = types.ModuleType("core_inline.lib.manager")
        sys.modules["core_inline.lib.manager"] = m
    if not hasattr(sys.modules["core_inline.lib.manager"], "InlineManager"):
        sys.modules["core_inline.lib.manager"].InlineManager = type("InlineManager", (), {})

def _stub_decorator(*args, **kwargs):
    def deco(fn):
        return fn
    if args and callable(args[0]) and not kwargs:
        return args[0]
    return deco


def _find_module_class(py_module: Any) -> Any:
    for attr_name in dir(py_module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(py_module, attr_name)
        if not isinstance(attr, type):
            continue
        if attr is MCUBModuleBase:
            continue
        try:
            if issubclass(attr, MCUBModuleBase):
                return attr
        except TypeError:
            continue
    return None


async def load_mcub_module(tetko_kernel, file_path, module_name=None):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MCUB-модуль не найден: {path}")

    mod_name = module_name or path.stem
    spec_name = f"mcub_compat_modules.{mod_name}"

    code = path.read_text(encoding="utf-8")
    if not is_mcub_module(code):
        raise ValueError(f"Файл {path.name} не похож на MCUB-модуль")

    _install_fakes()
    try:
        spec = importlib.util.spec_from_file_location(spec_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Не удалось создать spec для {path}")
        py_module = importlib.util.module_from_spec(spec)
        sys.modules[spec_name] = py_module
        spec.loader.exec_module(py_module)
    except Exception as e:
        log.exception(f"[mcub_compat] ошибка исполнения {path.name}")
        raise ImportError(f"Ошибка импорта MCUB-модуля {mod_name}: {e}") from e

    module_class = _find_module_class(py_module)
    if module_class is None:
        raise ImportError(f"В файле {path.name} не найден класс-наследник ModuleBase")

    try:
        instance = module_class(
            kernel=tetko_kernel,
            client=getattr(tetko_kernel, "client", None),
            register=None,
        )
    except TypeError:
        instance = module_class(tetko_kernel)

    proxy = KernelProxy(tetko_kernel, instance)
    instance.kernel = proxy
    instance._register = proxy.register

    registry = tetko_kernel.registry
    registry.register_module(instance)

    try:
        run_autostart_loops(proxy.register)
    except Exception as e:
        log.warning(f"[mcub_compat] autostart: {e}")

    try:
        on_load = getattr(instance, "on_load", None)
        if callable(on_load):
            result = on_load()
            if hasattr(result, "__await__"):
                await result
    except Exception as e:
        log.error(f"[mcub_compat] on_load {mod_name}: {e}")

    log.info(
        f"[mcub_compat] загружен {mod_name}: "
        f"команд={len(proxy.register.get_commands())}, "
        f"watcher={len(proxy.register.get_watchers())}, "
        f"loop={len(proxy.register.get_loops())}"
    )
    return instance


async def unload_mcub_module(tetko_kernel, module_name):
    registry = tetko_kernel.registry
    mod = registry.get_module(module_name)
    if mod is None:
        return False

    proxy = getattr(mod, "kernel", None)
    if proxy is not None and hasattr(proxy, "register"):
        try:
            stop_all_loops(proxy.register)
        except Exception:
            pass

    try:
        on_unload = getattr(mod, "on_unload", None)
        if callable(on_unload):
            result = on_unload()
            if hasattr(result, "__await__"):
                await result
    except Exception as e:
        log.error(f"[mcub_compat] on_unload {module_name}: {e}")

    registry.unregister_module(module_name)
    sys.modules.pop(f"mcub_compat_modules.{module_name}", None)
    log.info(f"[mcub_compat] выгружен {module_name}")
    return True


__all__ = ["load_mcub_module", "unload_mcub_module"]
