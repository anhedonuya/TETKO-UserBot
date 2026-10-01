PATCH_FLAG = "_nf_patched"


def install_patch(module, on_response):
    if module is None:
        return False
    original = getattr(module, "_http_request", None)
    if original is None:
        return False
    if getattr(original, PATCH_FLAG, False):
        return True

    async def patched(url, headers=None, timeout=None):
        r = await original(url, headers=headers, timeout=timeout)
        try:
            if isinstance(r, tuple) and len(r) >= 2:
                text = r[0]
                status = r[1]
                headers_dict = r[2] if len(r) >= 3 and isinstance(r[2], dict) else None
                try:
                    on_response(url, text, status, headers_dict)
                except Exception:
                    pass
        except Exception:
            pass
        return r

    setattr(patched, PATCH_FLAG, True)
    setattr(patched, "_nf_original", original)
    try:
        module._http_request = patched
        return True
    except Exception:
        return False


def uninstall_patch(module):
    if module is None:
        return False
    original = getattr(module, "_http_request", None)
    if original is None:
        return False
    inner = getattr(original, "_nf_original", None)
    if inner is None:
        return False
    try:
        module._http_request = inner
        return True
    except Exception:
        return False
