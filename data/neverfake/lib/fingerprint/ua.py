import re


def ua_to_profile(ua):
    if not ua:
        return None
    m = re.search(r"Chrome/(\d+)", ua)
    if m:
        return "chrome%s" % m.group(1)
    if "Firefox/" in ua:
        return "firefox"
    if "Safari/" in ua and "iPhone" in ua:
        return "safari17_2_ios"
    if "Safari/" in ua:
        return "safari17_0"
    return None


def is_chrome(ua):
    return "chrome" in (ua or "").lower()


def is_firefox(ua):
    return "firefox" in (ua or "").lower()


def is_safari(ua):
    u = (ua or "").lower()
    return "safari" in u and "chrome" not in u


def is_mobile(ua):
    return "mobile" in (ua or "").lower()
