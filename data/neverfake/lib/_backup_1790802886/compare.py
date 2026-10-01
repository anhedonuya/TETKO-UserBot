import html
from .inspect import norm


async def run(plugin, ctx, tail):
    parts = (tail or "").split()
    if len(parts) < 2:
        return "<blockquote>usage: <code>" + plugin.prefix + "dothat nf compare &lt;d1&gt; &lt;d2&gt;</code></blockquote>"
    d1 = norm(parts[0])
    d2 = norm(parts[1])
    i1 = plugin.store.get_identity(d1)
    i2 = plugin.store.get_identity(d2)
    c1 = plugin.store.list_cookies(d1, "")
    c2 = plugin.store.list_cookies(d2, "")
    lines = ["<blockquote><b>compare</b>"]
    lines.append("<b>" + html.escape(d1) + "</b>: visits=" + str((i1 or {}).get("visit_count", 0)) + " cookies=" + str(len(c1)))
    lines.append("<b>" + html.escape(d2) + "</b>: visits=" + str((i2 or {}).get("visit_count", 0)) + " cookies=" + str(len(c2)))
    lines.append("</blockquote>")
    return "\n".join(lines)
