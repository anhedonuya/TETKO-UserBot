PUBLIC_SUFFIXES = ("co.uk", "com.br", "co.jp", "org.uk", "ac.uk", "com.au", "co.nz")


def shared_domain(host):
    if not host:
        return ""
    h = host.lower().lstrip(".")
    if h.startswith("www."):
        h = h[4:]
    parts = h.split(".")
    if len(parts) < 2:
        return h
    for sfx in PUBLIC_SUFFIXES:
        if h.endswith("." + sfx) and len(parts) >= 3:
            return ".".join(parts[-3:])
    return ".".join(parts[-2:])
