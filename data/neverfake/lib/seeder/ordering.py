KIND_ORDER = {"premium": 0, "sacred": 1, "harvest": 2, "tracker": 3, "seed": 4}


def order_cookies(cookies):
    def key(c):
        return (
            KIND_ORDER.get(c.get("kind") or "seed", 9),
            len(c.get("path") or "/"),
            c.get("name") or "",
        )
    return sorted(cookies, key=key)
