import asyncio


async def liteflare_solve(ctx, url, reason="blocked"):
    try:
        r = ctx.call_plugin("liteflare", "solve", url, reason)
        if asyncio.iscoroutine(r):
            r = await r
        return r
    except Exception:
        return None


async def liteflare_headers(ctx, url):
    try:
        r = ctx.call_plugin("liteflare", "get_last_headers", url)
        if asyncio.iscoroutine(r):
            r = await r
        if isinstance(r, tuple) and len(r) >= 2:
            return r[0], r[1]
    except Exception:
        pass
    return {}, 200
