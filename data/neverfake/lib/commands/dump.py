import html
import json
from .inspect import norm


async def run(plugin, ctx, tail):
    d = norm(tail)
    if not d:
        return "<blockquote>usage: <code>" + plugin.prefix + "dothat nf dump &lt;domain&gt;</code></blockquote>"
    ident = plugin.store.get_identity(d)
    cookies = plugin.store.list_cookies(d, "")
    payload = {"domain": d, "identity": ident, "cookies": cookies}
    txt = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(txt) > 3500:
        txt = txt[:3500] + "...(truncated)"
    return "<blockquote><b>dump " + html.escape(d) + "</b></blockquote>\n<pre>" + html.escape(txt) + "</pre>"
