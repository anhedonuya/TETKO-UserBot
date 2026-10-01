import html
import time
from urllib.parse import urlparse


def norm(text):
    s = (text or "").strip().lower()
    if not s:
        return ""
    if "://" in s:
        try:
            s = urlparse(s).netloc
        except Exception:
            pass
    s = s.split("/")[0].split("?")[0].split("#")[0]
    if s.startswith("www."):
        s = s[4:]
    return s


async def run(plugin, ctx, tail):
    p = plugin.prefix
    d = norm(tail)
    if not d:
        return "<blockquote>usage: <code>" + p + "dothat nf inspect &lt;domain&gt;</code></blockquote>"
    if plugin.store is None:
        return "<blockquote>store not ready</blockquote>"
    ident = plugin.store.get_identity(d)
    cookies = plugin.store.list_cookies(d, "")
    summary = plugin.store.domain_summary(d)
    lines = ["<blockquote><b>inspect: " + html.escape(d) + "</b>"]
    if ident:
        lines.append("<b>identity:</b>")
        lines.append("  visits: <code>" + str(ident.get("visit_count", 0)) + "</code>")
        c = ident.get("created_at") or 0
        if c:
            lines.append("  age: <code>" + str(int((time.time() - c) / 3600)) + "h</code>")
        ua = ident.get("ua_locked") or "-"
        lines.append("  ua: <code>" + html.escape(ua[:60]) + "</code>")
        lines.append("  lang: <code>" + html.escape(str(ident.get("lang_locked") or "-")) + "</code>")
        lines.append("  tz: <code>" + html.escape(str(ident.get("tz_locked") or "-")) + "</code>")
        lines.append("  tls: <code>" + html.escape(str(ident.get("tls_profile") or "-")) + "</code>")
    if cookies:
        by_kind = {}
        for c in cookies:
            by_kind.setdefault(c.get("kind") or "?", []).append(c)
        lines.append("<b>cookies (" + str(len(cookies)) + "):</b>")
        order = ["premium", "sacred", "harvest", "tracker", "seed"]
        for kind in order + [k for k in by_kind if k not in order]:
            g = by_kind.get(kind) or []
            if not g:
                continue
            lines.append("  <b>" + html.escape(kind) + ":</b>")
            for c in g[:12]:
                v = str(c.get("value", ""))
                if len(v) > 32:
                    v = v[:32] + "..."
                lines.append("    <code>" + html.escape(c.get("name", "?")) + "</code>=<code>" + html.escape(v) + "</code>")
            if len(g) > 12:
                lines.append("    +" + str(len(g) - 12) + " more")
    cd = summary.get("cooldowns") or {}
    if cd:
        lines.append("<b>cooldowns:</b>")
        for k, u in cd.items():
            lines.append("  " + html.escape(str(k)) + " " + str(max(0, int(u - time.time()))) + "s")
    lines.append("</blockquote>")
    return "\n".join(lines)


async def cookies(plugin, ctx, tail):
    d = norm(tail)
    if not d:
        return "<blockquote>usage: <code>" + plugin.prefix + "dothat nf cookies &lt;domain&gt;</code></blockquote>"
    cks = plugin.store.list_cookies(d, "")
    if not cks:
        return "<blockquote>no cookies for <code>" + html.escape(d) + "</code></blockquote>"
    lines = ["<blockquote><b>cookies: " + html.escape(d) + " (" + str(len(cks)) + ")</b>"]
    for c in cks:
        v = str(c.get("value", ""))[:40]
        lines.append("<code>" + html.escape(c.get("name", "?")) + "</code>=<code>" + html.escape(v) + "</code> [" + html.escape(c.get("kind") or "?") + "]")
    lines.append("</blockquote>")
    return "\n".join(lines)
