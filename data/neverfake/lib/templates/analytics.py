import time


def make(ident, derive_int, derive):
    cid = str(derive_int(ident, "ga_cid", 10))[:10]
    now = int(time.time())
    first = now - 86400 * 30
    out = []
    out.append(("_ga", "GA1.2.%s.%d" % (cid, first), 86400 * 730, "/", None))
    out.append(("_gid", "GA1.2.%s.%d" % (cid, now), 86400, "/", None))
    out.append(("_gat", "1", 60, "/", None))
    out.append(("_ga_%s" % derive(ident, "ga_prop", 8).upper(), "GS1.1.%d.%d.1.1.0.0.0" % (now, now), 86400 * 730, "/", None))
    return out
