import html
from .inspect import norm


async def forget(plugin, ctx, tail):
    d = norm(tail)
    if not d:
        return "<blockquote>usage: <code>" + plugin.prefix + "dothat nf forget &lt;domain&gt;</code></blockquote>"
    plugin.store.clear_domain(d)
    return "<blockquote>forgotten: <code>" + html.escape(d) + "</code></blockquote>"


async def freeze_all(plugin, ctx, tail):
    plugin._frozen = True
    return "<blockquote>NeverFake frozen</blockquote>"


async def unfreeze(plugin, ctx, tail):
    plugin._frozen = False
    return "<blockquote>NeverFake unfrozen</blockquote>"


async def panic(plugin, ctx, tail):
    c = plugin.store._connect()
    with plugin.store._lock:
        c.execute("DELETE FROM cookies")
        c.execute("DELETE FROM identities")
        c.execute("DELETE FROM cooldowns")
        c.execute("DELETE FROM seed_stats")
        c.execute("DELETE FROM harvest_log")
        c.commit()
    plugin._frozen = True
    return "<blockquote>panic done: wiped + frozen</blockquote>"
