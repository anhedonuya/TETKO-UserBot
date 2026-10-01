def compose(entries):
    pairs = []
    for e in entries:
        n = e.get("name")
        v = e.get("value")
        if not n or v is None:
            continue
        pairs.append("%s=%s" % (n, v))
    return "; ".join(pairs)
