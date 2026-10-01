"""Set-Cookie parser + JS-cookie extraction."""
from __future__ import annotations

import re


_JS_COOKIE_RX = re.compile(
    r"document\.cookie\s*=\s*['\"]([^=]+)=([^;'\"]+)(?:;\s*([^'\"]*))?['\"]",
    re.IGNORECASE,
)


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
    out = {
        "name": name, "value": value, "path": "/",
        "expires_at": None, "secure": False,
        "http_only": False, "same_site": None,
    }
    for attr in parts[1:]:
        low = attr.lower()
        if low.startswith("path="):
            out["path"] = attr.split("=", 1)[1].strip()
        elif low.startswith("max-age="):
            try:
                out["expires_at"] = __import__("time").time() + int(attr.split("=", 1)[1])
            except Exception:
                pass
        elif low.startswith("expires="):
            pass
        elif low == "secure":
            out["secure"] = True
        elif low == "httponly":
            out["http_only"] = True
        elif low.startswith("samesite="):
            out["same_site"] = attr.split("=", 1)[1].strip()
    return out


def harvest_js(html_text):
    if not html_text or "document.cookie" not in html_text:
        return []
    out = []
    for m in _JS_COOKIE_RX.finditer(html_text):
        name = m.group(1).strip()
        value = m.group(2).strip()
        if not name or len(name) > 64:
            continue
        out.append({
            "name": name, "value": value, "path": "/",
            "expires_at": None, "secure": False,
            "http_only": False, "same_site": None,
        })
    return out


class Harvester:
    def __init__(self, store):
        self.store = store

    def from_response_headers(self, domain, proxy_key, headers, status):
        found = []
        for k, v in (headers or {}).items():
            if k.lower() != "set-cookie":
                continue
            if isinstance(v, (list, tuple)):
                for item in v:
                    c = parse_set_cookie(item)
                    if c:
                        found.append(c)
            else:
                c = parse_set_cookie(v)
                if c:
                    found.append(c)
        for c in found:
            c["kind"] = "harvest"
            c["source"] = "set-cookie:%d" % (status or 0)
            self.store.put_cookie(domain, proxy_key, c)
            self.store.log_harvest(domain, proxy_key, c["name"], "harvest", c["source"], status)
        return found

    def from_html(self, domain, proxy_key, html_text, status):
        found = harvest_js(html_text)
        for c in found:
            c["kind"] = "harvest"
            c["source"] = "js:%d" % (status or 0)
            self.store.put_cookie(domain, proxy_key, c)
            self.store.log_harvest(domain, proxy_key, c["name"], "harvest", c["source"], status)
        return found
