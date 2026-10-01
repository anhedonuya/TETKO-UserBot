"""Terminal-style shell block helper."""
from __future__ import annotations

PROMPT = "usernamefromtelegram@tetko:~%"


def set_username(username):
    global PROMPT
    username = str(username or "user").strip().lstrip("@")
    username = "".join(c for c in username if c.isalnum() or c == "_")
    PROMPT = (username or "user") + "@tetko:~%"


def esc(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(lines, cmd=None, running=False, trailing=True, lang="shell"):
    out = []
    if cmd is not None:
        out.append(PROMPT + " " + str(cmd))
        out.append("")
    for ln in lines:
        s = str(ln)
        if s.startswith("$ "):
            s = s[2:]
        out.append(s)
    if running:
        out.append("  running...")
    if trailing:
        out.append("")
        out.append(PROMPT + " ")
    body = esc("\n".join(out))
    return '<pre><code class="language-%s">%s</code></pre>' % (lang, body)
