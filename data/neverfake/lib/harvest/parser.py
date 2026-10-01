import time


def parse_set_cookie(header_value):
    if not header_value:
        return None
    parts = [p.strip() for p in header_value.split(";")]
    if not parts or "=" not in parts[0]:
        return None
    name, _, value = parts[0].partition("=")
    name = name.strip()
    value = value.strip()
    if not name:
        return None
    out = {"name": name, "value": value, "path": "/", "cookie_domain": "", "expires_at": None, "secure": False, "http_only": False, "same_site": None}
    for a in parts[1:]:
        low = a.lower()
        if low.startswith("path="):
            out["path"] = a.split("=", 1)[1].strip()
        elif low.startswith("domain="):
            out["cookie_domain"] = a.split("=", 1)[1].strip().lstrip(".")
        elif low.startswith("max-age="):
            try:
                out["expires_at"] = time.time() + int(a.split("=", 1)[1])
            except Exception:
                pass
        elif low == "secure":
            out["secure"] = True
        elif low == "httponly":
            out["http_only"] = True
        elif low.startswith("samesite="):
            out["same_site"] = a.split("=", 1)[1].strip()
    return out
