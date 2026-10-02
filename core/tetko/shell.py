from __future__ import annotations

FALLBACK_USER = "user"
FALLBACK_HOST = "tetko"
_KERNEL = None


def set_kernel(kernel):
    global _KERNEL
    _KERNEL = kernel


def _find_kernel():
    """Найти живой kernel в sys.modules, если _KERNEL потерялся."""
    global _KERNEL
    if _KERNEL is not None:
        return _KERNEL
    import sys as _sys
    for m in list(_sys.modules.values()):
        if m is None:
            continue
        k = getattr(m, "kernel", None)
        if k is not None and hasattr(k, "context") and hasattr(k, "config"):
            _KERNEL = k
            return k
    return None


def _get_prompt():
    user = FALLBACK_USER
    host = FALLBACK_HOST
    symbol = "%"

    k = _find_kernel()
    if k is not None:
        cfg = getattr(k, "config", None) or {}

        symbol = str(cfg.get("shell_prompt", "%") or "%")
        host = str(cfg.get("shell_host", "tetko") or "tetko")

        # username
        try:
            ctx = getattr(k, "context", None)
            if ctx is not None:
                u = getattr(ctx, "user_username", None)
                if u:
                    user = str(u)
        except Exception:
            pass

        # fallback: me
        if user == FALLBACK_USER:
            try:
                me = getattr(k, "_me", None)
                if me is not None:
                    u = getattr(me, "username", None) or getattr(me, "first_name", None)
                    if u:
                        user = str(u)
            except Exception:
                pass

        # 1. override по username (shell_host_overrides)
        try:
            overrides = cfg.get("shell_host_overrides") or {}
            if user in overrides:
                host = str(overrides[user])
        except Exception:
            pass

        # 2. если user == админ → host = shell_host_owner (по умолчанию "god")
        if host == "tetko":
            try:
                ctx = getattr(k, "context", None)
                admin_id = getattr(ctx, "admin_id", None) if ctx else None
                me = getattr(k, "_me", None)
                if admin_id is not None and me is not None:
                    if int(getattr(me, "id", 0)) == int(admin_id):
                        owner_host = str(cfg.get("shell_host_owner", "god") or "god")
                        if owner_host:
                            host = owner_host
            except Exception:
                pass

    return user + "@" + host + ":~" + symbol


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


class _PromptProxy:
    """Proxy: str(PROMPT) читает _KERNEL динамически."""
    def __str__(self):
        return _get_prompt()
    def __format__(self, spec):
        return format(_get_prompt(), spec)
    def __add__(self, other):
        return _get_prompt() + str(other)
    def __radd__(self, other):
        return str(other) + _get_prompt()
    def __repr__(self):
        return _get_prompt()


PROMPT = _PromptProxy()


def set_username(username=None):
    """DEPRECATED."""
    return None
