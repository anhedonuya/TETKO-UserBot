import base64


def make(ident, derive_int, derive):
    raw = ("CP%s" % derive(ident, "tcf", 80)).encode()
    b64 = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return [
        ("euconsent-v2", b64[:200], 86400 * 390, "/", "None"),
        ("didomi_token", "eyJ1c2VyX2lkIjoi%sIiwidmVuZG9ycyI6e319" % derive(ident, "didomi", 12), 86400 * 390, "/", "None"),
    ]
