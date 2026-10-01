def make(ident, derive_int, derive):
    return [
        ("PHPSESSID", derive(ident, "php_sid", 26), None, "/", "Lax"),
        ("csrftoken", derive(ident, "csrf", 64), 86400 * 30, "/", "Lax"),
        ("XSRF-TOKEN", derive(ident, "xsrf", 40), None, "/", "Lax"),
        ("laravel_session", derive(ident, "laravel", 40), None, "/", "Lax"),
        ("connect.sid", "s%%3A%s.%s" % (derive(ident, "sess", 32), derive(ident, "sig", 20)), None, "/", "Lax"),
    ]
