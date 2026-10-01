import time


def make(ident, derive_int, derive):
    return [
        ("tmr_lvid", derive(ident, "tmr", 32), 86400 * 90, "/", "Lax"),
        ("tmr_lvidTS", str(int(time.time() * 1000)), 86400 * 90, "/", "Lax"),
        ("_ym_metrika_enabled", "1", 3600, "/", "Lax"),
        ("adrdel", "1", 86400 * 365, "/", "Lax"),
        ("adrcnt", "1", 86400 * 365, "/", "Lax"),
        ("__rr", "1", 86400 * 30, "/", "Lax"),
        ("abt_data", derive(ident, "abt", 20), 86400 * 30, "/", "Lax"),
        ("mrcu", str(derive_int(ident, "mrcu2", 8))[:8], 86400 * 365, "/", "Lax"),
    ]
