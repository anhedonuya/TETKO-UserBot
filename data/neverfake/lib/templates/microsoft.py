import time


def make(ident, derive_int, derive):
    return [
        ("_uetvid", "%s_%s" % (derive(ident, "uet_1", 26), derive(ident, "uet_2", 26)), 86400 * 390, "/", "Lax"),
        ("_uetsid", "%s_%s" % (derive(ident, "uets_1", 26), derive(ident, "uets_2", 26)), 86400 * 1, "/", "Lax"),
        ("MUID", derive(ident, "muid", 32).upper(), 86400 * 390, "/", "None"),
        ("SRM_B", derive(ident, "srm", 32).upper(), 86400 * 390, "/", "None"),
        ("ANONCHK", "0", 600, "/", "None"),
        ("SM", "0", None, "/", "None"),
        ("_clck", "1%7C%s%7C2%7C0%7C0" % derive(ident, "clck", 8), 86400 * 365, "/", "Lax"),
    ]
