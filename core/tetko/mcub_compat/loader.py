"""Загрузчик MCUB-модулей поверх TETKO."""
from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from .detector import is_mcub_module
from .kernel_proxy import KernelProxy
from .register_shim import RegisterShim, run_autostart_loops, stop_all_loops, unregister_all_events, unregister_all_callbacks


log = logging.getLogger("TETKO.mcub_compat.loader")


def _install_fakes() -> None:
    """Install only compatibility aliases; keep the real MCUB API intact."""
    import importlib
    # The full MCUB core/lib is shipped with TETKO.  Do not replace ModuleBase,
    # decorators or ModuleConfig with reduced shims: that was the source of
    # several subtle incompatibilities in older builds.
    for name in (
        "core.lib.loader.module_base",
        "core.lib.loader.decorators",
        "core.lib.loader.base",
        "core.lib.loader.module_config",
        "core.lib.loader.kernel_proxy",
        "core.lib.loader.register",
    ):
        try:
            importlib.import_module(name)
        except Exception as exc:
            log.debug("[mcub_compat] optional import %s: %s", name, exc)

    # TETKO still owns the runtime.  MCUB's event wrapper must not attempt to
    # replace it, so wrap_event_for_module is deliberately a no-op here.
    try:
        kp = sys.modules.get("core.lib.loader.kernel_proxy")
        if kp is not None:
            kp.wrap_event_for_module = lambda event, *a, **kw: event
    except Exception:
        pass

    # Keep MCUB's core_inline package available.  TETKO's implementation is
    # already shipped from the MCUB fork and is loaded normally.

def _stub_decorator(*args, **kwargs):
    def deco(fn):
        return fn
    if args and callable(args[0]) and not kwargs:
        return args[0]
    return deco


def _find_module_class(py_module: Any) -> Any:
    try:
        from core.lib.loader.module_base import ModuleBase
    except Exception:
        ModuleBase = None
    for attr_name in dir(py_module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(py_module, attr_name)
        if not isinstance(attr, type):
            continue
        if ModuleBase is not None and attr is ModuleBase:
            continue
        try:
            if ModuleBase is not None and issubclass(attr, ModuleBase):
                return attr
        except TypeError:
            pass
    return None


async def load_mcub_module(
    tetko_kernel: Any,
    file_path: str | Path,
    module_name: str | None = None,
) -> Any:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MCUB-модуль не найден: {path}")

    mod_name = module_name or path.stem
    spec_name = f"mcub_compat_modules.{mod_name}"

    code = path.read_text(encoding="utf-8")
    if not is_mcub_module(code):
        raise ValueError(
            f"Файл {path.name} не похож на MCUB-модуль — используй обычный загрузчик"
        )

    # однократная инициализация подсистем mcub_compat
    if not getattr(tetko_kernel, "_mcub_subsystems_installed", False):
        try:
            from .config_ui import install as _install_cfg_ui
            _install_cfg_ui(tetko_kernel)
        except Exception as e:
            log.warning(f"[mcub_compat] config_ui: {e}")
        try:
            from .callback_dispatch import install_callback_handler
            _bot = getattr(tetko_kernel, "bot_client", None)
            if _bot is not None:
                install_callback_handler(tetko_kernel, _bot)
        except Exception as e:
            log.warning(f"[mcub_compat] callback_dispatch: {e}")
        tetko_kernel._mcub_subsystems_installed = True

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

    # Создаём proxy ДО инстанса, чтобы __init__ модуля видел kernel.register
    proxy = KernelProxy(tetko_kernel, None)

    class _PlaceholderModule:
        name = "Pending"
    proxy.register.module = _PlaceholderModule()

    old_loading = getattr(tetko_kernel, "current_loading_module", None)
    old_loading_type = getattr(tetko_kernel, "current_loading_module_type", None)
    tetko_kernel.current_loading_module = getattr(module_class, "name", None) or mod_name
    tetko_kernel.current_loading_module_type = "mcub"
    try:
        try:
            instance = module_class(
                kernel=proxy,
                client=getattr(tetko_kernel, "client", None),
                register=proxy.register,
            )
        except TypeError:
            instance = module_class(proxy)
    finally:
        # Keep MCUB's loading context available for the tiny registration window,
        # then restore TETKO's previous state.
        tetko_kernel.current_loading_module = old_loading
        tetko_kernel.current_loading_module_type = old_loading_type

    # Дописываем module_instance в proxy (нужен register_shim)
    object.__setattr__(proxy, "_module", instance)
    proxy.register.module = instance

    instance.kernel = proxy
    instance._register = proxy.register

    # ── Регистрация команд/watcher'ов из @command-декораторов ──
    try:
        _reg = getattr(type(instance), "_mcub_registry", None) or {}
        _shim = proxy.register
        for pattern, kw, attr_name in _reg.get("commands", []):
            method = getattr(instance, attr_name, None)
            if method is not None:
                _shim.command(pattern, **kw)(method)
        for kw, attr_name in _reg.get("watchers", []):
            method = getattr(instance, attr_name, None)
            if method is not None:
                _shim.watcher(method, **kw)
        for kw, attr_name in _reg.get("callbacks", []):
            method = getattr(instance, attr_name, None)
            if method is not None:
                _shim.callback(method, **kw)
        for kw, attr_name in _reg.get("loops", []):
            method = getattr(instance, attr_name, None)
            if method is not None:
                _shim.loop(**kw)(method)
        for pattern, kw, attr_name in _reg.get("bot_commands", []):
            method = getattr(instance, attr_name, None)
            if method is not None:
                _shim.bot_command(pattern, **kw)(method)
        for pattern, kw, attr_name in _reg.get("inlines", []):
            method = getattr(instance, attr_name, None)
            if method is not None and hasattr(_shim, "inline"):
                _shim.inline(pattern, **kw)(method)
    except Exception as e:
        log.warning(f"[mcub_compat] _mcub_registry register: {e}")


    registry = tetko_kernel.registry
    # MCUB's canonical module identity is the class name, not the filename.
    canonical_name = getattr(instance, "name", None) or mod_name
    existing = registry.get_module(canonical_name)
    if existing is not None and existing is not instance:
        existing_path = getattr(existing, "_mcub_source_path", None)
        # Reloading the same module should replace the old instance cleanly.
        try:
            await unload_mcub_module(tetko_kernel, canonical_name)
        except Exception as e:
            log.warning("[mcub_compat] unload-existing %s: %s", canonical_name, e)
    try:
        registry.register_module(instance)
    except Exception as exc:
        # A second copy with the same class name can be the result of a user
        # loading "Foo (1).py".  Reuse the existing instance rather than
        # falling back into TETKO's native Module validation path.
        existing = registry.get_module(canonical_name)
        if existing is not None:
            return existing
        raise
    instance._mcub_source_path = str(path)

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


async def unload_mcub_module(tetko_kernel: Any, module_name: str) -> bool:
    registry = tetko_kernel.registry
    mod = registry.get_module(module_name)
    if mod is None:
        return False

    proxy = getattr(mod, "kernel", None)
    if proxy is not None and hasattr(proxy, "register"):
        try: stop_all_loops(proxy.register)
        except Exception: pass
        try: unregister_all_events(proxy.register)
        except Exception: pass
        try: unregister_all_callbacks(proxy.register)
        except Exception: pass

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
