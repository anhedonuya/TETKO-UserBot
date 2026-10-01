"""Progressive seeding + header composition."""
from __future__ import annotations

import time


_PROGRESSIVE = [
    (0, ["consent"]),
    (1, ["consent", "analytics"]),
    (2, ["consent", "analytics", "yandex"]),
    (4, ["consent", "analytics", "yandex", "cms"]),
    (6, ["consent", "analytics", "yandex", "cms", "ads"]),
]


class Seeder:
    def __init__(self, store, identity, templates):
        self.store = store
        self.identity = identity
        self.templates = templates

    def _plan(self, visit_count):
        plan = []
        for threshold, groups in _PROGRESSIVE:
            if visit_count >= threshold:
                plan = groups
        return plan

    def seed_for(self, domain, proxy_key, enabled_groups):
        ident = self.identity.get_or_create(domain)
        visit_count = ident.get("visit_count", 0)
        groups = self._plan(visit_count)
        result = []
        for g in groups:
            if g not in enabled_groups:
                continue
            fn = getattr(self.templates, g, None)
            if fn is None:
                continue
            try:
                entries = fn(ident)
            except Exception:
                continue
            for name, value, ttl, path, same_site in entries:
                expires = time.time() + ttl if ttl else None
                result.append({
                    "name": name, "value": value, "path": path,
                    "expires_at": expires, "secure": False,
                    "http_only": False, "same_site": same_site,
                    "kind": "seed", "source": "template:%s" % g,
                })
        return ident, result

    def compose_header(self, entries):
        pairs = []
        for e in entries:
            name = e.get("name")
            value = e.get("value")
            if not name or value is None:
                continue
            pairs.append("%s=%s" % (name, value))
        return "; ".join(pairs)

    def commit_seeds(self, domain, proxy_key, entries):
        for e in entries:
            self.store.put_cookie(domain, proxy_key, e)
            self.store.log_seed(domain, e.get("source") or "?", "seeded")
