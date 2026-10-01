def make(ident, derive_int, derive):
    return [
        ("JSESSIONID", derive(ident, "java_sid", 32).upper(), None, "/", "Lax"),
        ("ASPSESSIONID%s" % derive(ident, "asp_id", 8).upper(), derive(ident, "asp_val", 24).upper(), None, "/", "Lax"),
        ("ASP.NET_SessionId", derive(ident, "net_sid", 24), None, "/", "Lax"),
        (".AspNetCore.Session", derive(ident, "core_sess", 40), None, "/", "Lax"),
        (".AspNetCore.Antiforgery.%s" % derive(ident, "af", 10), derive(ident, "af_val", 40), None, "/", "Lax"),
        ("CFID", str(derive_int(ident, "cfid", 8))[:8], 86400 * 365, "/", "Lax"),
        ("CFTOKEN", str(derive_int(ident, "cftoken", 8))[:8], 86400 * 365, "/", "Lax"),
    ]
