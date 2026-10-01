import time


def make(ident, derive_int, derive):
    ms = str(int(time.time() * 1000))[:13]
    rnd = str(derive_int(ident, "ym_r", 7))[:7]
    ym = ms + rnd
    yx = (ms + str(derive_int(ident, "yx", 6)))[:20]
    return [
        ("_ym_uid", ym, 86400 * 365, "/", None),
        ("_ym_d", str(int(time.time())), 86400 * 365, "/", None),
        ("_ym_isad", "1", 86400, "/", None),
        ("_ym_visorc", "w", 1800, "/", None),
        ("yandexuid", yx, 86400 * 365, "/", None),
        ("ymex", "%d.%d.0.0" % (time.gmtime().tm_year, time.gmtime().tm_mon), 86400 * 365, "/", None),
    ]
