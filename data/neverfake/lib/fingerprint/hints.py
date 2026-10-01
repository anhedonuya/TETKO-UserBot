import json
import re


def client_hints(ua, platform=None):
    u = (ua or "").lower()
    if "chrome" not in u and "edge" not in u:
        return {}
    m = re.search(r"Chrome/(\d+)", ua or "")
    ver = m.group(1) if m else "131"
    if "android" in u:
        plat = "Android"
    elif "iphone" in u or "ipad" in u:
        plat = "iOS"
    elif "mac" in u:
        plat = "macOS"
    elif "linux" in u:
        plat = "Linux"
    else:
        plat = platform or "Windows"
    mobile = "?1" if ("mobile" in u or "android" in u or "iphone" in u) else "?0"
    return {"sec-ch-ua": '"Chromium";v="%s", "Not_A Brand";v="24"' % ver, "sec-ch-ua-mobile": mobile, "sec-ch-ua-platform": '"%s"' % plat}


def hints_json(hints):
    try:
        return json.dumps(hints)
    except Exception:
        return "{}"
