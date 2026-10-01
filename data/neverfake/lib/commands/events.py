import html
import time


async def run(plugin, ctx, tail):
    if plugin.store is None:
        return "<blockquote>store not ready</blockquote>"
    c = plugin.store._connect()
    with plugin.store._lock:
        rows = c.execute("SELECT ts, kind, domain, data FROM events ORDER BY ts DESC LIMIT 30").fetchall()
    if not rows:
        return "<blockquote>no events</blockquote>"
    lines = ["<blockquote><b>events</b>"]
    for ts, kind, dom, data in rows:
        t = time.strftime("%H:%M:%S", time.localtime(ts))
        lines.append("<code>" + t + "</code> " + html.escape(str(kind)) + " " + html.escape(str(dom or "")))
    lines.append("</blockquote>")
    return "\n".join(lines)
