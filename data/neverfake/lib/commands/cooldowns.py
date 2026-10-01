import html
import time


async def run(plugin, ctx, tail):
    if plugin.store is None:
        return "<blockquote>store not ready</blockquote>"
    c = plugin.store._connect()
    with plugin.store._lock:
        rows = c.execute("SELECT domain, strategy, until_ts, reason FROM cooldowns WHERE until_ts > ? ORDER BY until_ts ASC", (time.time(),)).fetchall()
    if not rows:
        return "<blockquote>no active cooldowns</blockquote>"
    now = time.time()
    lines = ["<blockquote><b>cooldowns (" + str(len(rows)) + ")</b>"]
    for d, s, u, r in rows:
        lines.append("<code>" + html.escape(str(d)) + "</code> " + html.escape(str(s)) + " " + str(int(u - now)) + "s " + html.escape(str(r or "")))
    lines.append("</blockquote>")
    return "\n".join(lines)
