import time


def make(ident, derive_int, derive):
    return [
        ("wp-settings-1", "libraryContent=browse&editor=html", 86400 * 365, "/", "Lax"),
        ("wp-settings-time-1", str(int(time.time())), 86400 * 365, "/", "Lax"),
        ("BITRIX_SM_SALE_UID", str(derive_int(ident, "bitrix_uid", 10))[:10], 86400 * 365, "/", "Lax"),
        ("BITRIX_SM_GUEST_ID", str(derive_int(ident, "bitrix_gid", 8))[:8], 86400 * 365, "/", "Lax"),
        ("Drupal.visitor.name", "guest_%s" % derive(ident, "drupal", 8), 86400 * 365, "/", "Lax"),
    ]
