"""Deterministic per-domain persona."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time


class Identity:
    def __init__(self, store):
        self.store = store

    def get_or_create(self, domain):
        ident = self.store.get_identity(domain)
        if ident is not None:
            return ident
        seed = secrets.token_hex(32)
        ident = {
            "domain": domain,
            "device_seed": seed,
            "created_at": time.time(),
            "visit_count": 0,
            "ua_locked": None,
            "lang_locked": None,
            "tz_locked": None,
            "tls_locked": None,
        }
        self.store.upsert_identity(domain, ident)
        return ident

    def derive(self, ident, purpose, length):
        msg = ("%s:%s" % (purpose, ident["domain"])).encode()
        mac = hmac.new(ident["device_seed"].encode(), msg, hashlib.sha256).hexdigest()
        return mac[:length]

    def derive_int(self, ident, purpose, length):
        h = self.derive(ident, purpose, length * 2)
        return int(h, 16)

    def bump_visit(self, domain):
        self.store.bump_visit(domain)

    def lock_ua(self, domain, ua):
        ident = self.get_or_create(domain)
        ident["ua_locked"] = ua
        self.store.upsert_identity(domain, ident)

    def lock_lang(self, domain, lang):
        ident = self.get_or_create(domain)
        ident["lang_locked"] = lang
        self.store.upsert_identity(domain, ident)

    def lock_tls(self, domain, profile):
        ident = self.get_or_create(domain)
        ident["tls_locked"] = profile
        self.store.upsert_identity(domain, ident)
