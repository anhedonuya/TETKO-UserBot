from __future__ import annotations

FALLBACK_USER = "user"
FALLBACK_HOST = "tetko"


def _get_prompt():
    user = FALLBACK_USER
    host = FALLBACK_HOST
    try:
        from core.tetko import shell as _sh
        k = getattr(_sh, "_KERNEL", None)
        if k is not None:
            try:
                ctx = getattr(k, "context", None)
                if ctx is not None:
                    u = getattr(ctx, "user_username", None)
                    if u:
                        user = str(u)
            except Exception:
                pass
            if user == FALLBACK_USER:
                try:
                    me = getattr(k, "_me", None)
                    if me is not None:
                        u = getattr(me, "username", None) or getattr(me, "first_name", None)
                        if u:
                            user = str(u)
                except Exception:
                    pass
    except Exception:
        pass
    return user + "@" + host + ":~%"


def get_prompt():
    return _get_prompt()


def esc(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(lines, cmd=None, running=False, trailing=True, lang="shell"):
    prompt = _get_prompt()
    out = []
    if cmd is not None:
        out.append(prompt + " " + str(cmd))
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
        out.append(prompt + " ")
    body = esc("\n".join(out))
    return '<pre><code class="language-%s">%s</code></pre>' % (lang, body)
