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
        ident = {"domain": domain, "device_seed": seed, "created_at": time.time(), "visit_count": 0}
        self.store.upsert_identity(domain, ident)
        return ident

    def derive(self, ident, purpose, length):
        msg = ("%s:%s" % (purpose, ident["domain"])).encode()
        mac = hmac.new(ident["device_seed"].encode(), msg, hashlib.sha256).hexdigest()
        return mac[:length]

    def derive_int(self, ident, purpose, length):
        return int(self.derive(ident, purpose, length * 2), 16)

    def bump_visit(self, domain):
        self.store.bump_visit(domain)

    def lock_ua(self, domain, ua):
        i = self.get_or_create(domain)
        i["ua_locked"] = ua
        self.store.upsert_identity(domain, i)

    def lock_lang(self, domain, lang):
        i = self.get_or_create(domain)
        i["lang_locked"] = lang
        self.store.upsert_identity(domain, i)

    def lock_tz(self, domain, tz):
        i = self.get_or_create(domain)
        i["tz_locked"] = tz
        self.store.upsert_identity(domain, i)

    def lock_tls(self, domain, profile):
        i = self.get_or_create(domain)
        i["tls_profile"] = profile
        self.store.upsert_identity(domain, i)

    def lock_hints(self, domain, hints_json):
        i = self.get_or_create(domain)
        i["hints_json"] = hints_json
        self.store.upsert_identity(domain, i)

    def reset(self, domain):
        self.store.clear_domain(domain)
