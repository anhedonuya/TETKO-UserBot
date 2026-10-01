import asyncio

class PipelineManager:
    def __init__(self, registry):
        self.registry = registry
        self._pipelines = {}

    def define(self, name, plugins, hook=None):
        self._pipelines[name] = {"plugins": list(plugins), "hook": hook}

    def list(self):
        return dict(self._pipelines)

    def get(self, name):
        return self._pipelines.get(name)

    def remove(self, name):
        self._pipelines.pop(name, None)

    async def run(self, name, ctx, dispatcher):
        p = self._pipelines.get(name)
        if not p:
            return ctx
        result = ctx
        for plugin_name in p["plugins"]:
            info = self.registry.get(plugin_name)
            if not info:
                continue
            module_obj = info.get("module")
            hook = p.get("hook") or "on_pipeline"
            method = getattr(module_obj, hook, None) if module_obj else None
            if method is None:
                continue
            try:
                ctx_obj = dispatcher.make_ctx(plugin_name, hook, result)
                r = method(ctx_obj)
                if asyncio.iscoroutine(r):
                    r = await r
                if isinstance(r, dict):
                    result = r
            except Exception:
                continue
        return result
