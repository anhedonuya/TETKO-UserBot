import html
import json
import time
from pathlib import Path
from .inspect import norm


async def run(plugin, ctx, tail):
    d = norm(tail)
    if not d:
        return "<blockquote>usage: <code>" + plugin.prefix + "dothat nf export &lt;domain&gt;</code></blockquote>"
    out_dir = Path("data/neverfake/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in d)
    path = out_dir / (safe + ".json")
    payload = {"domain": d, "identity": plugin.store.get_identity(d), "cookies": plugin.store.list_cookies(d, ""), "exported_at": time.time()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return "<blockquote>exported: <code>" + html.escape(str(path)) + "</code></blockquote>"
