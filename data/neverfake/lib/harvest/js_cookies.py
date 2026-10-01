import re

JS_RX = re.compile(r"document\.cookie\s*=\s*['\"]([^=]+)=([^;'\"]+)(?:;\s*([^'\"]*))?['\"]", re.I)


def extract_js_cookies(html):
    if not html or "document.cookie" not in html:
        return []
    out = []
    for m in JS_RX.finditer(html):
        name = m.group(1).strip()
        value = m.group(2).strip()
        if not name or len(name) > 64:
            continue
        out.append({"name": name, "value": value, "path": "/", "cookie_domain": "", "expires_at": None, "secure": False, "http_only": False, "same_site": None})
    return out
