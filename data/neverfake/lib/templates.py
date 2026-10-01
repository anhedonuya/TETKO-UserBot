"""Cookie factory templates."""
from __future__ import annotations

import time


class Templates:
    def __init__(self, identity):
        self.identity = identity

    def _ga(self, ident):
        cid = str(self.identity.derive_int(ident, "ga_cid", 10))[:10]
        first = int(time.time()) - 86400 * 30
        return "GA1.2.%s.%d" % (cid, first)

    def _gid(self, ident):
        cid = str(self.identity.derive_int(ident, "gid_cid", 10))[:10]
        return "GA1.2.%s.%d" % (cid, int(time.time()))

    def _ym_uid(self, ident):
        ms = str(int(time.time() * 1000))[:13]
        rnd = str(self.identity.derive_int(ident, "ym_r", 7))[:7]
        return ms + rnd

    def _ym_d(self, ident):
        return str(int(time.time()))

    def _ym_isad(self, ident):
        return "1"

    def _yandexuid(self, ident):
        ms = str(int(time.time() * 1000))
        rnd = str(self.identity.derive_int(ident, "yx", 6))
        return (ms + rnd)[:20]

    def _fbp(self, ident):
        r = str(self.identity.derive_int(ident, "fbp", 10))[:10]
        return "fb.1.%d.%s" % (int(time.time() * 1000), r)

    def _gcl_au(self, ident):
        r = str(self.identity.derive_int(ident, "gcl", 10))[:10]
        return "1.1.%s.%d" % (r, int(time.time()))

    def _cookieconsent(self, ident):
        return "dismiss"

    def _optanon(self, ident):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        return "isGpcEnabled=0&datestamp=%s&version=202311.1.0&browserGpcFlag=0" % stamp

    def _php_sessid(self, ident):
        return self.identity.derive(ident, "php_sid", 26)

    def _csrf(self, ident):
        return self.identity.derive(ident, "csrf", 64)

    def _xsrf(self, ident):
        return self.identity.derive(ident, "xsrf", 40)

    def _laravel(self, ident):
        return self.identity.derive(ident, "laravel", 40)

    def _wp_settings(self, ident):
        return "libraryContent=browse&editor=html"

    def _wp_time(self, ident):
        return str(int(time.time()))

    def analytics(self, ident):
        return [
            ("_ga", self._ga(ident), 86400 * 730, "/", None),
            ("_gid", self._gid(ident), 86400, "/", None),
        ]

    def yandex(self, ident):
        return [
            ("_ym_uid", self._ym_uid(ident), 86400 * 365, "/", None),
            ("_ym_d", self._ym_d(ident), 86400 * 365, "/", None),
            ("_ym_isad", self._ym_isad(ident), 86400, "/", None),
            ("yandexuid", self._yandexuid(ident), 86400 * 365, "/", None),
        ]

    def ads(self, ident):
        return [
            ("_fbp", self._fbp(ident), 86400 * 90, "/", None),
            ("_gcl_au", self._gcl_au(ident), 86400 * 90, "/", None),
        ]

    def consent(self, ident):
        return [
            ("cookieconsent_status", self._cookieconsent(ident), 86400 * 365, "/", None),
            ("OptanonConsent", self._optanon(ident), 86400 * 365, "/", None),
        ]

    def session(self, ident):
        return [
            ("PHPSESSID", self._php_sessid(ident), None, "/", None),
            ("csrftoken", self._csrf(ident), 86400 * 30, "/", None),
            ("XSRF-TOKEN", self._xsrf(ident), None, "/", None),
            ("laravel_session", self._laravel(ident), None, "/", None),
        ]

    def cms(self, ident):
        return [
            ("wp-settings-1", self._wp_settings(ident), 86400 * 365, "/", None),
            ("wp-settings-time-1", self._wp_time(ident), 86400 * 365, "/", None),
        ]
