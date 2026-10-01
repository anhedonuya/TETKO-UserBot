import html
import time


async def domains(plugin, ctx, tail):
    if plugin.store is None:
        return "<blockquote>store not ready</blockquote>"
    c = plugin.store._connect()
    with plugin.store._lock:
        rows = c.execute("SELECT i.domain, i.visit_count, (SELECT COUNT(*) FROM cookies c WHERE c.domain = i.domain) FROM identities i ORDER BY i.last_seen DESC LIMIT 50").fetchall()
    if not rows:
        return "<blockquote>no domains yet</blockquote>"
    lines = ["<blockquote><b>domains (" + str(len(rows)) + ")</b>"]
    for d, vc, cc in rows:
        lines.append("<code>" + html.escape(str(d)) + "</code> visits=" + str(vc) + " cookies=" + str(cc))
    lines.append("</blockquote>")
    return "\n".join(lines)


async def run(plugin, ctx, tail):
    if plugin.store is None:
        return "<blockquote>store not ready</blockquote>"
    s = plugin.store.global_stats()
    c = plugin.store._connect()
    with plugin.store._lock:
        recent = c.execute("SELECT kind, COUNT(*) FROM events WHERE ts > ? GROUP BY kind", (time.time() - 86400,)).fetchall()
    lines = ["<blockquote><b>NeverFake dashboard</b>"]
    lines.append("identities: <code>" + str(s["identities"]) + "</code>")
    lines.append("cookies: <code>" + str(s["cookies"]) + "</code>")
    for k, v in (s.get("kinds") or {}).items():
        lines.append("  " + html.escape(str(k)) + ": " + str(v))
    lines.append("<b>events 24h:</b>")
    for k, v in (recent or []):
        lines.append("  " + html.escape(str(k)) + ": " + str(v))
    lines.append("</blockquote>")
    return "\n".join(lines)
