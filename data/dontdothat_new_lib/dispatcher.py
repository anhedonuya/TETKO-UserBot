import asyncio
import time

from .return_ import Return
from .errors import PluginError, TimeoutHookError

class Dispatcher:
    def __init__(self, registry, make_ctx, log_error=None):
        self.registry = registry
        self.make_ctx = make_ctx
        self.log_error = log_error or (lambda *a, **k: None)

    async def dispatch(self, hook_name, ctx_base):
        result = None
        for priority, name, info in self.registry.find_by_hook(hook_name):
            module_obj = info.get("module")
            method = getattr(module_obj, hook_name, None) if module_obj else None
            if method is None or not callable(method):
                continue
            manifest = info.get("manifest") or {}
            timeout = manifest.get("timeout", 10)
            metrics = info.setdefault("_metrics", {}).setdefault(hook_name, {"calls": 0, "errors": 0, "total_time": 0.0})
            metrics["calls"] += 1
            started = time.time()
            try:
                ctx = self.make_ctx(name, hook_name, ctx_base)
                r = method(ctx)
                if asyncio.iscoroutine(r):
                    if timeout and timeout > 0:
                        r = await asyncio.wait_for(r, timeout=timeout)
                    else:
                        r = await r
                metrics["total_time"] += time.time() - started
                if r is None:
                    continue
                if isinstance(r, Return):
                    if r.kind == Return.CONTINUE:
                        continue
                    if r.kind == Return.SKIP:
                        return result
                    if r.kind == Return.BLOCK:
                        return False
                    if r.kind in (Return.MODIFY, Return.REPLACE):
                        return r.value
                    if r.kind == Return.CHAIN:
                        result = r.value
                        continue
                    if r.kind == Return.ERROR:
                        raise PluginError(r.reason or "plugin error")
                if r is False:
                    return False
                return r
            except asyncio.TimeoutError:
                metrics["errors"] += 1
                self.log_error(name, hook_name, "timeout")
                continue
            except Exception as e:
                metrics["errors"] += 1
                self.log_error(name, hook_name, str(e))
                continue
        return result

    async def dispatch_plugin(self, name, hook_name, ctx_base):
        info = self.registry.get(name)
        if not info or info.get("enabled") is False:
            return None
        module_obj = info.get("module")
        method = getattr(module_obj, hook_name, None) if module_obj else None
        if method is None or not callable(method):
            return None
        try:
            ctx = self.make_ctx(name, hook_name, ctx_base)
            r = method(ctx)
            if asyncio.iscoroutine(r):
                r = await r
            return r
        except Exception as e:
            self.log_error(name, hook_name, str(e))
            return None

    async def dispatch_event(self, event_type, ctx_base):
        for name, info in self.registry.find_by_event(event_type):
            module_obj = info.get("module")
            method = getattr(module_obj, "on_event", None) if module_obj else None
            if method is None or not callable(method):
                continue
            try:
                ctx = self.make_ctx(name, "on_event", ctx_base)
                r = method(ctx)
                if asyncio.iscoroutine(r):
                    asyncio.create_task(r)
            except Exception as e:
                self.log_error(name, "on_event", str(e))
