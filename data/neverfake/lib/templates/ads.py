import time


def make(ident, derive_int, derive):
    now_ms = int(time.time() * 1000)
    r10 = str(derive_int(ident, "fbp", 10))[:10]
    return [
        ("_fbp", "fb.1.%d.%s" % (now_ms, r10), 86400 * 90, "/", None),
        ("_gcl_au", "1.1.%s.%d" % (r10, int(time.time())), 86400 * 90, "/", None),
        ("IDE", str(derive_int(ident, "ide", 20))[:20], 86400 * 390, "/", "None"),
        ("DSID", str(derive_int(ident, "dsid", 15))[:15], 86400 * 14, "/", "None"),
        ("test_cookie", "CheckForPermission", 900, "/", "None"),
    ]
