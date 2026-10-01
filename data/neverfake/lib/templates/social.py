def make(ident, derive_int, derive):
    return [
        ("_pin_unauth", "dWIu%s" % derive(ident, "pin", 12), 86400 * 365, "/", "Lax"),
        ("_ttp", "%s_%s" % (derive(ident, "ttp1", 20), derive(ident, "ttp2", 6)), 86400 * 390, "/", "Lax"),
        ("ttwid", derive(ident, "ttw", 40), 86400 * 365, "/", "Lax"),
        ("ttclid", derive(ident, "ttclid", 26), 86400 * 30, "/", "Lax"),
        ("remixlang", "0", 86400 * 365, "/", "Lax"),
        ("remixstid", str(derive_int(ident, "remix", 10))[:10], 86400 * 365, "/", "Lax"),
        ("Mrcuid", "V%s" % str(derive_int(ident, "mrcu", 12))[:12], 86400 * 365, "/", "Lax"),
        ("VID", derive(ident, "vid", 20), 86400 * 365, "/", "Lax"),
    ]
