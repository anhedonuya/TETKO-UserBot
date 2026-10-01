"""Monkey-patch helper for DDT _http_request."""
from __future__ import annotations


def install_hook(module, on_headers):
    if module is None:
        return False
    original = getattr(module, "_http_request", None)
    if original is None:
        return False
    if getattr(original, "_neverfake_patched", False):
        return True

    async def patched(url, headers=None, timeout=None):
        result = await original(url, headers=headers, timeout=timeout)
        try:
            if isinstance(result, tuple) and len(result) >= 2:
                text, status = result[0], result[1]
                try:
                    on_headers(url, text, status, None)
                except Exception:
                    pass
        except Exception:
            pass
        return result

    patched._neverfake_patched = True
    patched._neverfake_original = original
    try:
        module._http_request = patched
    except Exception:
        return False
    return True


def uninstall_hook(module):
    if module is None:
        return False
    original = getattr(module, "_http_request", None)
    if original is None:
        return False
    inner = getattr(original, "_neverfake_original", None)
    if inner is None:
        return False
    try:
        module._http_request = inner
        return True
    except Exception:
        return False
