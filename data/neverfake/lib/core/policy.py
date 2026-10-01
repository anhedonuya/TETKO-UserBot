import re
import time

NEVER_FAKE = ("cf_clearance", "__cf_bm", "__cfduid", "cf_chl_1", "cf_chl_2", "cf_chl_prog", "cf_chl_opt", "datadome", "_abck", "ak_bmsc")
NEVER_FAKE_RX = (re.compile(r"^_px", re.I), re.compile(r"^px_", re.I), re.compile(r"^incap_ses_", re.I), re.compile(r"^visid_incap_", re.I), re.compile(r"^TSPD_", re.I), re.compile(r"jwt$", re.I))

SACRED = ("session", "phpsessid", "csrftoken", "xsrf-token", "laravel_session", "connect.sid", "auth")
SACRED_RX = (re.compile(r"^_secure", re.I), re.compile(r"user_?id$", re.I))

TRACKER = ("_ga", "_gid", "_gat", "_fbp", "_gcl_au", "_ym_uid", "_ym_d", "yandexuid", "_hjid", "_clck", "_clsk")
TRACKER_RX = (re.compile(r"^_ga_", re.I), re.compile(r"^_ym_", re.I))

HONEYPOT_PREFIXES = ("_hp", "_trap", "_check_", "honeypot", "verify_")


def is_signed(name):
    low = (name or "").lower()
    if low in NEVER_FAKE:
        return True
    return any(rx.search(name) for rx in NEVER_FAKE_RX)


def is_sacred(name):
    low = (name or "").lower()
    if low in SACRED:
        return True
    return any(rx.search(name) for rx in SACRED_RX)


def is_tracker(name):
    low = (name or "").lower()
    if low in TRACKER:
        return True
    return any(rx.search(name) for rx in TRACKER_RX)


class Policy:
    def __init__(self, store):
        self.store = store
        self._honeypot = {}

    def is_signed(self, name):
        return is_signed(name)

    def is_sacred(self, name):
        return is_sacred(name)

    def is_tracker(self, name):
        return is_tracker(name)

    def is_honeypot(self, name):
        low = (name or "").lower()
        if low.startswith(HONEYPOT_PREFIXES):
            return True
        return self._honeypot.get(name, {}).get("hit", 0) >= 3

    def mark_honeypot_hit(self, name):
        e = self._honeypot.setdefault(name, {"hit": 0, "first": time.time()})
        e["hit"] += 1

    def classify(self, cookie, status=200):
        name = cookie.get("name") or ""
        if is_signed(name):
            return "sacred"
        if is_sacred(name) and status in (200, 201, 204, 302):
            return "premium"
        if is_tracker(name):
            return "tracker"
        if is_sacred(name):
            return "sacred"
        return "harvest"

    def can_seed(self, name):
        if self.is_honeypot(name):
            return False
        if is_signed(name):
            return False
        if is_sacred(name):
            return False
        return True

    def apply_harvest(self, domain, proxy_key, cookies, status):
        for c in cookies:
            c["kind"] = self.classify(c, status)
            self.store.put_cookie(domain, proxy_key, c)
