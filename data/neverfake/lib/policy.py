"""Cookie classification: sacred / premium / tracker / seed."""
from __future__ import annotations

import re


_NEVER_FAKE = (
    "cf_clearance", "__cf_bm", "__cfduid",
    "cf_chl_1", "cf_chl_2", "cf_chl_prog", "cf_chl_opt",
    "datadome", "_abck", "ak_bmsc",
)
_NEVER_FAKE_RX = (
    re.compile(r"^_px", re.IGNORECASE),
    re.compile(r"^px_", re.IGNORECASE),
    re.compile(r"^incap_ses_", re.IGNORECASE),
    re.compile(r"^visid_incap_", re.IGNORECASE),
    re.compile(r"^TSPD_", re.IGNORECASE),
    re.compile(r"jwt$", re.IGNORECASE),
)

_SACRED = (
    "session", "phpsessid", "csrftoken", "xsrf-token",
    "laravel_session", "connect.sid", "auth",
)
_SACRED_RX = (
    re.compile(r"^_secure", re.IGNORECASE),
    re.compile(r"user_?id$", re.IGNORECASE),
)

_TRACKER = (
    "_ga", "_gid", "_gat", "_fbp", "_gcl_au", "_ym_uid", "_ym_d",
    "yandexuid", "_hjid", "_clck", "_clsk",
)
_TRACKER_RX = (
    re.compile(r"^_ga_", re.IGNORECASE),
    re.compile(r"^_ym_", re.IGNORECASE),
)


def is_signed(name):
    low = (name or "").lower()
    if low in _NEVER_FAKE:
        return True
    for rx in _NEVER_FAKE_RX:
        if rx.search(name):
            return True
    return False


def is_sacred(name):
    low = (name or "").lower()
    if low in _SACRED:
        return True
    for rx in _SACRED_RX:
        if rx.search(name):
            return True
    return False


def is_tracker(name):
    low = (name or "").lower()
    if low in _TRACKER:
        return True
    for rx in _TRACKER_RX:
        if rx.search(name):
            return True
    return False


class Policy:
    def __init__(self, store):
        self.store = store

    def is_signed(self, name):
        return is_signed(name)

    def is_sacred(self, name):
        return is_sacred(name)

    def is_tracker(self, name):
        return is_tracker(name)

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

    def is_honeypot(self, name):
        low = (name or '').lower()
        return low.startswith(('_hp', '_trap', '_check_', 'honeypot', 'verify_'))

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
            kind = self.classify(c, status)
            c["kind"] = kind
            self.store.put_cookie(domain, proxy_key, c)
