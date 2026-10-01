class Api:
    def __init__(self, plugin):
        self.plugin = plugin

    def get_cookies(self, domain, proxy_key=""):
        s = self.plugin.store
        return s.list_cookies(domain, proxy_key) if s else []

    def get_identity(self, domain):
        s = self.plugin.store
        return s.get_identity(domain) if s else None

    def put_cookie(self, domain, cookie, proxy_key=""):
        s = self.plugin.store
        if not s:
            return False
        try:
            s.put_cookie(domain, proxy_key, cookie)
            return True
        except Exception:
            return False

    def compose_header(self, domain, proxy_key=""):
        ck = self.get_cookies(domain, proxy_key)
        return "; ".join("%s=%s" % (c["name"], c["value"]) for c in ck)

    def forget(self, domain):
        s = self.plugin.store
        if not s:
            return False
        s.clear_domain(domain)
        return True

    def stats(self):
        s = self.plugin.store
        return s.global_stats() if s else {}

    def summary(self, domain):
        s = self.plugin.store
        return s.domain_summary(domain) if s else {}

    def pick_ua(self, domain):
        i = self.plugin.identity
        if not i:
            return None
        ident = i.get_or_create(domain)
        return ident.get("ua_locked")

    def harvest_html(self, domain, html, status=200, proxy_key=""):
        h = self.plugin.harvester
        if not h or not html:
            return []
        try:
            found = h.from_html(domain, proxy_key, html, status)
            if found and self.plugin.policy:
                self.plugin.policy.apply_harvest(domain, proxy_key, found, status)
            return found
        except Exception:
            return []

    def harvest_headers(self, domain, headers, status=200, proxy_key=""):
        h = self.plugin.harvester
        if not h or not headers:
            return []
        try:
            return h.from_response_headers(domain, proxy_key, headers, status)
        except Exception:
            return []

    def cooldown_active(self, domain, strategy="fetch"):
        l = self.plugin.learning
        return l.cooldown_active(domain, strategy) if l else False

    def should_drift(self, domain):
        l = self.plugin.learning
        return l.should_drift(domain) if l else False
