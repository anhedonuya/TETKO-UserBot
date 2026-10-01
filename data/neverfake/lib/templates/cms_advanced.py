def make(ident, derive_int, derive):
    return [
        ("joomla_user_state", "logged_in", None, "/", "Lax"),
        ("tildauid", str(derive_int(ident, "tilda_uid", 12))[:12], 86400 * 365, "/", "Lax"),
        ("tildasid", str(derive_int(ident, "tilda_sid", 12))[:12], None, "/", "Lax"),
        ("tilda_secret", derive(ident, "tilda_sec", 32), 86400 * 365, "/", "Lax"),
        ("wp-wpml_current_language", "ru", 86400, "/", "Lax"),
    ]
