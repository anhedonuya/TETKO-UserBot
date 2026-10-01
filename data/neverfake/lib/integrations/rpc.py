import asyncio


def call_plugin(ctx, name, method, *args, **kwargs):
    try:
        return ctx.call_plugin(name, method, *args, **kwargs)
    except Exception:
        return None


async def call_plugin_async(ctx, name, method, *args, **kwargs):
    r = call_plugin(ctx, name, method, *args, **kwargs)
    if asyncio.iscoroutine(r):
        return await r
    return r
