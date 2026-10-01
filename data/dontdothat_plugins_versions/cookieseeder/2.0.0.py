from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import base64
import hashlib
import json
import os
import random
import re
import sqlite3
import string
import threading
import time
from collections import OrderedDict
from pathlib import Path


DB_PATH = Path("data/dontdothat_cookies.db")
SHARED_PATH = Path("data/dontdothat_cookies_shared.json")
LOCK_PATH = Path("data/dontdothat_cookies.lock")


@dataclass
class Manifest:
    name: str = "CookieSeeder"
    version: str = "2.0.0"
    author: str = "@flexOwnerAL"
    description: str = "advanced cookie jar: profiles, geo, TCF, harvest, learning"
    api: str = "1.5.0"
    min_core: str = ">=0.0.0"
    access: List[str] = field(default_factory=lambda: ["module"])
    tags: List[str] = field(default_factory=lambda: ["bypass", "cookies", "net"])
    categories: List[str] = field(default_factory=lambda: ["net"])
    events: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=lambda: ["before_fetch", "after_fetch", "on_blocked", "on_command"])
    priority: Dict[str, int] = field(default_factory=lambda: {
        "before_fetch": 150, "after_fetch": 150, "on_blocked": 150, "on_command": 90,
    })
    cfg_defaults: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "inject_on_before": True,
        "harvest_on_after": True,
        "harvest_on_blocked": True,
        "max_cookies_per_domain": 60,
        "cookie_ttl": 21600,
        "seed_ga": True,
        "seed_fbp": True,
        "seed_ym": True,
        "seed_session": True,
        "seed_consent": True,
        "seed_analytics": True,
        "seed_cf": True,
        "seed_tcf": True,
        "seed_ads": True,
        "seed_cms": True,
        "premium_detection": True,
        "domain_learning": True,
        "cf_block_threshold": 5,
        "cf_disable_ttl": 86400,
        "subdomain_scope": True,
        "decay_detection": True,
        "refusal_threshold": 10,
        "refusal_drop_after": 3,
        "hot_cache_size": 100,
        "batch_size": 20,
        "lr_max_cookies": 20000,
        "shared_jar": False,
        "pii_scrub_export": True,
        "default_browser_profile": "chrome_win_ru",
        "auto_geo_profile": True,
        "temporal_consistency": True,
    })
    cfg_schema: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": {"type": "bool"},
        "inject_on_before": {"type": "bool"},
        "harvest_on_after": {"type": "bool"},
        "harvest_on_blocked": {"type": "bool"},
        "max_cookies_per_domain": {"type": "int", "min": 5, "max": 500},
        "cookie_ttl": {"type": "int", "min": 60, "max": 604800},
        "seed_ga": {"type": "bool"},
        "seed_fbp": {"type": "bool"},
        "seed_ym": {"type": "bool"},
        "seed_session": {"type": "bool"},
        "seed_consent": {"type": "bool"},
        "seed_analytics": {"type": "bool"},
        "seed_cf": {"type": "bool"},
        "seed_tcf": {"type": "bool"},
        "seed_ads": {"type": "bool"},
        "seed_cms": {"type": "bool"},
        "premium_detection": {"type": "bool"},
        "domain_learning": {"type": "bool"},
        "cf_block_threshold": {"type": "int", "min": 1, "max": 100},
        "cf_disable_ttl": {"type": "int", "min": 60, "max": 604800},
        "subdomain_scope": {"type": "bool"},
        "decay_detection": {"type": "bool"},
        "refusal_threshold": {"type": "int", "min": 1, "max": 100},
        "refusal_drop_after": {"type": "int", "min": 1, "max": 20},
        "hot_cache_size": {"type": "int", "min": 10, "max": 1000},
        "batch_size": {"type": "int", "min": 1, "max": 200},
        "lr_max_cookies": {"type": "int", "min": 100, "max": 1000000},
        "shared_jar": {"type": "bool"},
        "pii_scrub_export": {"type": "bool"},
        "default_browser_profile": {"type": "str"},
        "auto_geo_profile": {"type": "bool"},
        "temporal_consistency": {"type": "bool"},
    })


MANIFEST = Manifest()


BROWSER_PROFILES = {
    "chrome_win_ru": {
        "ua_marker": "chrome_win",
        "pools": ["ga", "ym", "session", "consent", "analytics", "ads_google", "cf", "tcf", "cms_wordpress"],
    },
    "chrome_mac_en": {
        "ua_marker": "chrome_mac",
        "pools": ["ga", "session", "consent", "analytics", "ads_google", "ads_fb", "cf", "tcf"],
    },
    "safari_ios_ru": {
        "ua_marker": "safari_ios",
        "pools": ["ym", "session", "consent", "analytics", "cf", "tcf"],
    },
    "firefox_linux_en": {
        "ua_marker": "firefox_linux",
        "pools": ["ga", "session", "consent", "analytics", "cf"],
    },
    "edge_win_en": {
        "ua_marker": "edge_win",
        "pools": ["ga", "fbp", "session", "consent", "analytics", "ads_google", "ads_fb", "cf"],
    },
}

GEO_PROFILES = {
    "ru": ["ym", "consent", "analytics", "ads_yandex"],
    "en": ["ga", "ads_google", "ads_fb", "consent", "analytics"],
    "cn": ["analytics"],
    "de": ["tcf", "consent", "ga"],
    "fr": ["tcf", "consent", "ga"],
}


def _rnd(n, kind="alnum"):
    if kind == "hex":
        return "".join(random.choices("0123456789abcdef", k=n))
    if kind == "upper":
        return "".join(random.choices("0123456789ABCDEF", k=n))
    if kind == "digit":
        return "".join(random.choices("0123456789", k=n))
    if kind == "uuid":
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
            "x", lambda _: random.choice("0123456789abcdef")
        ).replace("y", random.choice("89ab"))
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def _tcf_v2_consent():
    """Генерирует упрощённый TCF v2 consent string (base64url)"""
    ts = int(time.time() // 100) % 10**10
    payload = "%010d" % ts
    payload += "01"
    payload += "0" * 8
    payload += "".join(random.choices("0123456789", k=40))
    raw = bytes.fromhex(payload[: len(payload) // 2 * 2]) if len(payload) % 2 == 0 else payload.encode()
    try:
        return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    except Exception:
        return _rnd(80, "alnum")


COOKIE_POOLS = {
    "ga": [
        ("_ga", lambda: "GA1.2.%d.%d" % (random.randint(100000000, 999999999), int(time.time()))),
        ("_gid", lambda: "GA1.2.%d.%d" % (random.randint(100000000, 999999999), int(time.time()))),
        ("_gat", lambda: "1"),
        ("_gcl_au", lambda: "1.1.%d.%d" % (random.randint(100000000, 999999999), int(time.time()))),
    ],
    "fbp": [
        ("_fbp", lambda: "fb.1.%d.%d" % (int(time.time() * 1000), random.randint(100000000, 999999999))),
        ("_fbc", lambda: "fb.1.%d.IwAR%d" % (int(time.time() * 1000), random.randint(10**14, 10**15))),
        ("fr", lambda: _rnd(30, "alnum")),
    ],
    "ym": [
        ("_ym_uid", lambda: str(int(time.time() * 1000000))),
        ("_ym_d", lambda: str(int(time.time()))),
        ("_ym_isad", lambda: str(random.choice([1, 2]))),
        ("_ym_visorc", lambda: "w"),
        ("ymex", lambda: "%d.%d" % (int(time.time() * 1000), random.randint(100000, 999999))),
        ("yandexuid", lambda: str(random.randint(10**17, 10**18))),
        ("yuidss", lambda: str(random.randint(10**17, 10**18))),
    ],
    "session": [
        ("PHPSESSID", lambda: _rnd(26, "hex")),
        ("JSESSIONID", lambda: _rnd(32, "upper")),
        ("sessionid", lambda: _rnd(32, "hex")),
        ("session", lambda: _rnd(24, "alnum")),
        ("sid", lambda: _rnd(20, "hex")),
        ("csrftoken", lambda: _rnd(32, "alnum")),
        ("connect.sid", lambda: "s:" + _rnd(32, "hex")),
        ("laravel_session", lambda: _rnd(40, "alnum")),
        ("XSRF-TOKEN", lambda: _rnd(40, "alnum")),
    ],
    "consent": [
        ("cookieconsent_status", lambda: "dismiss"),
        ("cookie_consent", lambda: "1"),
        ("gdpr", lambda: "true"),
        ("eu_cn", lambda: "1"),
        ("cookie_notice_accepted", lambda: "true"),
        ("cky-action", lambda: "accept"),
        ("OptanonConsent", lambda: "isGpcEnabled=0&datestamp=%s&version=202401.1.0" % time.strftime("%Y-%m-%d", time.gmtime())),
        ("CookieConsent", lambda: "{stamp:'%s',necessary:true,preferences:true,statistics:true,marketing:true}" % str(int(time.time()))),
        ("borlabs-cookie", lambda: "1"),
        ("klaro", lambda: _rnd(20, "alnum")),
    ],
    "analytics": [
        ("_clck", lambda: _rnd(10, "alnum") + "|2|" + str(int(time.time() * 1000))),
        ("_clsk", lambda: _rnd(10, "alnum") + "|" + str(int(time.time() * 1000)) + "|1|1|" + _rnd(1, "digit") + "|" + _rnd(4, "alnum")),
        ("amplitude_id", lambda: _rnd(32, "hex")),
        ("ajs_anonymous_id", lambda: _rnd(36, "uuid")),
        ("hubspotutk", lambda: _rnd(32, "hex")),
        ("_vwo_uuid", lambda: _rnd(32, "alnum")),
        ("_vis_opt_s", lambda: "1-" + str(random.randint(100, 999))),
        ("mp_" + _rnd(6, "hex") + "_mixpanel", lambda: _rnd(32, "hex")),
    ],
    "ads_google": [
        ("_gcl_aw", lambda: "GCL.%d.%s" % (int(time.time() * 1000), _rnd(20, "alnum"))),
        ("_gcl_dc", lambda: "GCL.%d.%s" % (int(time.time() * 1000), _rnd(20, "alnum"))),
        ("IDE", lambda: _rnd(30, "alnum")),
        ("test_cookie", lambda: "CheckForPermission"),
    ],
    "ads_yandex": [
        ("_ym_metrika_enabled", lambda: "true"),
        ("i", lambda: _rnd(30, "hex")),
    ],
    "ads_fb": [
        ("datr", lambda: _rnd(24, "alnum")),
        ("sb", lambda: _rnd(24, "alnum")),
        ("dpr", lambda: str(random.choice([1, 2, 3]))),
    ],
    "ads_tiktok": [
        ("_ttp", lambda: _rnd(40, "alnum")),
        ("ttclid", lambda: "E.C.P." + _rnd(30, "alnum")),
    ],
    "ads_vk": [
        ("remixlang", lambda: "0"),
        ("remixstid", lambda: str(random.randint(10**9, 10**10))),
    ],
    "cf": [
        ("cf_clearance", lambda: _rnd(43, "alnum")),
        ("__cf_bm", lambda: _rnd(32, "alnum") + "." + str(int(time.time()) + 3600)),
        ("__cfduid", lambda: "d" + _rnd(20, "hex")),
        ("__cfruid", lambda: _rnd(32, "hex") + "-" + str(int(time.time()))),
    ],
    "akamai": [
        ("_abck", lambda: _rnd(200, "alnum") + "~-1~-1~-1"),
        ("ak_bmsc", lambda: _rnd(60, "alnum")),
        ("bm_sz", lambda: _rnd(20, "alnum") + "~" + str(int(time.time()))),
    ],
    "imperva": [
        ("incap_ses_" + _rnd(6, "digit"), lambda: _rnd(40, "alnum")),
        ("visid_incap_" + _rnd(6, "digit"), lambda: _rnd(40, "alnum")),
    ],
    "tcf": [
        ("euconsent-v2", lambda: _tcf_v2_consent()),
        ("__tcfapi", lambda: "1"),
    ],
    "cms_wordpress": [
        ("wordpress_test_cookie", lambda: "WP%20Cookie%20check"),
        ("wp-settings-" + str(random.randint(1, 5)), lambda: "1"),
    ],
    "cms_bitrix": [
        ("BITRIX_SM_SALE_UID", lambda: str(random.randint(10**6, 10**9))),
        ("BITRIX_SM_GUEST_ID", lambda: str(random.randint(10**6, 10**9))),
    ],
    "cms_drupal": [
        ("Drupal.visitor.name", lambda: "visitor_" + _rnd(8, "alnum")),
    ],
    "user_id": [
        ("user_id", lambda: str(random.randint(10**6, 10**9))),
        ("uid", lambda: str(random.randint(10**6, 10**9))),
        ("_u", lambda: str(random.randint(10**6, 10**9))),
    ],
}

PREMIUM_NAME_RX = re.compile(
    r"(?i)^(?:session|sid|auth|token|access|refresh|login|user|account|"
    r"jwt|bearer|apikey|api_key|remember|autologin|user_id|uid|"
    r"sessionid|session_id|PHPSESSID|JSESSIONID|connect\.sid|"
    r"laravel_session|XSRF-TOKEN|csrftoken)$"
)

PII_RX = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}"),
]


_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_LOG_BUFFER: List[Dict[str, Any]] = []
_LOG_LOCK = threading.Lock()
_PENDING: Dict[Tuple[str, str], Dict[str, Any]] = {}
_PENDING_LOCK = threading.Lock()


def _log_event(kind, domain, name="", extra=""):
    with _LOG_LOCK:
        _LOG_BUFFER.append({
            "ts": time.time(), "kind": kind, "domain": domain,
            "name": name, "extra": extra[:120],
        })
        if len(_LOG_BUFFER) > 200:
            del _LOG_BUFFER[: len(_LOG_BUFFER) - 200]


def _domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _domain_suffix(domain):
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    return ".".join(parts[-2:])


def _geo_for_domain(domain):
    if domain.endswith((".ru", ".рф", ".su", ".by", ".kz")):
        return "ru"
    if domain.endswith(".cn"):
        return "cn"
    if domain.endswith(".de"):
        return "de"
    if domain.endswith(".fr"):
        return "fr"
    return "en"


def _db():
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
            CREATE TABLE IF NOT EXISTS cookies (
                domain TEXT, name TEXT, value TEXT, path TEXT,
                created REAL, expires REAL, source TEXT,
                premium INTEGER DEFAULT 0, confirmed INTEGER DEFAULT 0,
                secure INTEGER DEFAULT 0, http_only INTEGER DEFAULT 0,
                same_site TEXT DEFAULT '',
                seen_count INTEGER DEFAULT 0,
                PRIMARY KEY (domain, name)
            );
            CREATE TABLE IF NOT EXISTS seeds (domain TEXT PRIMARY KEY, seeded REAL);
            CREATE TABLE IF NOT EXISTS learning (
                domain TEXT PRIMARY KEY,
                cf_blocks INTEGER DEFAULT 0,
                cf_disabled_until REAL DEFAULT 0,
                total_blocks INTEGER DEFAULT 0,
                total_ok INTEGER DEFAULT 0,
                last_seen REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS change_log (
                ts REAL, domain TEXT, name TEXT, old_value TEXT, new_value TEXT, source TEXT
            );
            CREATE TABLE IF NOT EXISTS locks (domain TEXT PRIMARY KEY, note TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS whitelist (domain TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS blacklist (domain TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS domain_ttl (domain TEXT PRIMARY KEY, ttl INTEGER);
        """)
        c.commit()
        return c
    except Exception:
        return None


def _cache_get(domain):
    with _CACHE_LOCK:
        v = _CACHE.get(domain)
        if v is not None:
            _CACHE.move_to_end(domain)
        return v


def _cache_set(domain, items, limit=100):
    with _CACHE_LOCK:
        _CACHE[domain] = items
        _CACHE.move_to_end(domain)
        while len(_CACHE) > limit:
            _CACHE.popitem(last=False)


def _cache_invalidate(domain):
    with _CACHE_LOCK:
        _CACHE.pop(domain, None)


def _is_locked(domain):
    c = _db()
    if c is None:
        return False
    try:
        return c.execute("SELECT 1 FROM locks WHERE domain=?", (domain,)).fetchone() is not None
    except Exception:
        return False


def _in_whitelist(domain):
    c = _db()
    if c is None:
        return False
    try:
        return c.execute("SELECT 1 FROM whitelist WHERE domain=?", (domain,)).fetchone() is not None
    except Exception:
        return False


def _in_blacklist(domain):
    c = _db()
    if c is None:
        return False
    try:
        return c.execute("SELECT 1 FROM blacklist WHERE domain=?", (domain,)).fetchone() is not None
    except Exception:
        return False


def _domain_ttl(domain, default):
    c = _db()
    if c is None:
        return default
    try:
        row = c.execute("SELECT ttl FROM domain_ttl WHERE domain=?", (domain,)).fetchone()
        if row:
            return int(row[0])
    except Exception:
        pass
    suffix = _domain_suffix(domain)
    try:
        row = c.execute("SELECT ttl FROM domain_ttl WHERE domain=?", (suffix,)).fetchone()
        if row:
            return int(row[0])
    except Exception:
        pass
    return default


def _get_all(domain, cfg=None):
    cached = _cache_get(domain)
    if cached is not None:
        return cached
    c = _db()
    if c is None:
        return []
    now = time.time()
    try:
        rows = c.execute(
            "SELECT name, value, path, expires, source, premium, secure, http_only, same_site, confirmed, seen_count "
            "FROM cookies WHERE domain=? AND expires>?",
            (domain, now),
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "name": r[0], "value": r[1], "path": r[2] or "/",
                "expires": r[3], "source": r[4] or "seed",
                "premium": bool(r[5]), "secure": bool(r[6]),
                "http_only": bool(r[7]), "same_site": r[8] or "",
                "confirmed": bool(r[9]), "seen_count": r[10] or 0,
            })
        _cache_set(domain, out, limit=int((cfg or {}).get("hot_cache_size", 100) or 100))
        return out
    except Exception:
        return []


def _log_change(domain, name, old_value, new_value, source):
    c = _db()
    if c is None:
        return
    try:
        c.execute(
            "INSERT INTO change_log (ts, domain, name, old_value, new_value, source) VALUES (?,?,?,?,?,?)",
            (time.time(), domain, name, old_value or "", new_value or "", source),
        )
    except Exception:
        pass


def _flush_pending():
    c = _db()
    if c is None:
        return
    with _PENDING_LOCK:
        items = list(_PENDING.items())
        _PENDING.clear()
    if not items:
        return
    try:
        for (domain, name), data in items:
            old = c.execute("SELECT value FROM cookies WHERE domain=? AND name=?", (domain, name)).fetchone()
            old_value = old[0] if old else ""
            if data.get("delete"):
                c.execute("DELETE FROM cookies WHERE domain=? AND name=?", (domain, name))
                _log_change(domain, name, old_value, "", "decay")
                continue
            row = c.execute("SELECT premium FROM cookies WHERE domain=? AND name=?", (domain, name)).fetchone()
            if row and row[0] and data.get("source") in ("seed", "js"):
                continue
            c.execute(
                "INSERT OR REPLACE INTO cookies "
                "(domain, name, value, path, created, expires, source, premium, secure, http_only, same_site, confirmed, seen_count) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    domain, name, data["value"], data.get("path", "/"),
                    time.time(), data.get("expires", time.time() + 21600),
                    data.get("source", "seed"), int(data.get("premium", 0)),
                    int(data.get("secure", 0)), int(data.get("http_only", 0)),
                    data.get("same_site", ""), int(data.get("confirmed", 0)),
                    int(data.get("seen_count", 0)),
                ),
            )
            if old_value != data["value"]:
                _log_change(domain, name, old_value, data["value"], data.get("source", "?"))
        c.commit()
        for (domain, _) in items:
            _cache_invalidate(domain)
    except Exception:
        pass


def _set_one(domain, name, value, path="/", ttl=21600, source="seed",
             premium=0, secure=0, http_only=0, same_site="", confirmed=0, seen_count=0):
    with _PENDING_LOCK:
        _PENDING[(domain, name)] = {
            "value": value, "path": path,
            "expires": time.time() + ttl, "source": source,
            "premium": premium, "secure": secure, "http_only": http_only,
            "same_site": same_site, "confirmed": confirmed, "seen_count": seen_count,
        }
        if len(_PENDING) >= 20:
            _flush_pending()


def _delete_one(domain, name):
    with _PENDING_LOCK:
        _PENDING[(domain, name)] = {"delete": True}
        if len(_PENDING) >= 20:
            _flush_pending()


def _set_many(domain, items, ttl=21600, source="seed"):
    for it in items:
        _set_one(
            domain, it["name"], it["value"], it.get("path", "/"), ttl, source,
            premium=it.get("premium", 0), secure=it.get("secure", 0),
            http_only=it.get("http_only", 0), same_site=it.get("same_site", ""),
        )


def _is_seeded(domain, ttl=86400):
    c = _db()
    if c is None:
        return False
    try:
        row = c.execute("SELECT seeded FROM seeds WHERE domain=?", (domain,)).fetchone()
        if not row:
            return False
        return time.time() - row[0] < ttl
    except Exception:
        return False


def _mark_seeded(domain):
    c = _db()
    if c is None:
        return
    try:
        c.execute("INSERT OR REPLACE INTO seeds (domain, seeded) VALUES (?,?)", (domain, time.time()))
        c.commit()
    except Exception:
        pass


def _learning_get(domain):
    c = _db()
    if c is None:
        return {"cf_blocks": 0, "cf_disabled_until": 0, "total_blocks": 0, "total_ok": 0}
    try:
        row = c.execute(
            "SELECT cf_blocks, cf_disabled_until, total_blocks, total_ok FROM learning WHERE domain=?",
            (domain,),
        ).fetchone()
        if not row:
            return {"cf_blocks": 0, "cf_disabled_until": 0, "total_blocks": 0, "total_ok": 0}
        return {"cf_blocks": row[0] or 0, "cf_disabled_until": row[1] or 0,
                "total_blocks": row[2] or 0, "total_ok": row[3] or 0}
    except Exception:
        return {"cf_blocks": 0, "cf_disabled_until": 0, "total_blocks": 0, "total_ok": 0}


def _learning_set(domain, **kw):
    c = _db()
    if c is None:
        return
    try:
        cur = _learning_get(domain)
        cur.update(kw)
        c.execute(
            "INSERT OR REPLACE INTO learning (domain, cf_blocks, cf_disabled_until, total_blocks, total_ok, last_seen) "
            "VALUES (?,?,?,?,?,?)",
            (domain, cur["cf_blocks"], cur["cf_disabled_until"], cur["total_blocks"], cur["total_ok"], time.time()),
        )
        c.commit()
    except Exception:
        pass


def _is_cf_disabled(domain):
    return _learning_get(domain)["cf_disabled_until"] > time.time()


def _pick_pools(cfg, domain):
    if cfg.get("auto_geo_profile", True):
        geo = _geo_for_domain(domain)
        base = list(GEO_PROFILES.get(geo, GEO_PROFILES["en"]))
    else:
        base = []
    profile_name = cfg.get("default_browser_profile", "chrome_win_ru")
    prof = BROWSER_PROFILES.get(profile_name)
    pools = list(base)
    if prof:
        pools.extend(prof["pools"])
    if cfg.get("seed_ga", True) and "ga" not in pools:
        pools.append("ga")
    if cfg.get("seed_fbp", True) and "fbp" not in pools:
        pools.append("fbp")
    if cfg.get("seed_ym", True) and "ym" not in pools:
        pools.append("ym")
    if cfg.get("seed_session", True) and "session" not in pools:
        pools.append("session")
    if cfg.get("seed_consent", True) and "consent" not in pools:
        pools.append("consent")
    if cfg.get("seed_analytics", True) and "analytics" not in pools:
        pools.append("analytics")
    if cfg.get("seed_ads", True):
        pools.extend(["ads_google", "ads_fb", "ads_tiktok"])
    if cfg.get("seed_cms", True):
        pools.extend(["cms_wordpress", "cms_bitrix"])
    if cfg.get("seed_tcf", True):
        pools.append("tcf")
    if cfg.get("seed_cf", True) and not _is_cf_disabled(domain):
        pools.append("cf")
    pools.append("akamai")
    pools.append("imperva")
    pools.append("user_id")
    return list(dict.fromkeys(pools))


def _gen_cookies(cfg, domain):
    pool_names = _pick_pools(cfg, domain)
    out = []
    for pn in pool_names:
        pool = COOKIE_POOLS.get(pn)
        if not pool:
            continue
        for name, fn in pool:
            try:
                value = fn()
            except Exception:
                continue
            premium = 1 if (cfg.get("premium_detection", True) and PREMIUM_NAME_RX.match(name)) else 0
            out.append({
                "name": name, "value": value, "path": "/",
                "premium": premium, "source": "seed",
            })
    return out


def _seed_domain(domain, cfg):
    if not domain or _is_seeded(domain):
        return
    ttl = _domain_ttl(domain, int(cfg.get("cookie_ttl", 21600) or 21600))
    pool = _gen_cookies(cfg, domain)
    random.shuffle(pool)
    limit = int(cfg.get("max_cookies_per_domain", 60) or 60)
    pool = pool[:limit]
    _set_many(domain, pool, ttl=ttl, source="seed")
    _mark_seeded(domain)
    _log_event("seed", domain, extra="%d cookies" % len(pool))


def _cookie_header(domain):
    items = _get_all(domain)
    if not items:
        return None
    return "; ".join("%s=%s" % (c["name"], c["value"]) for c in items)


def _parse_setcookie_line(line, default_ttl):
    parts = line.split(";")
    if not parts:
        return None
    first = parts[0].strip()
    if "=" not in first:
        return None
    name, value = first.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not name or len(name) > 120 or len(value) > 4000:
        return None
    path = "/"
    ttl = default_ttl
    secure = 0
    http_only = 0
    same_site = ""
    is_delete = False
    for attr in parts[1:]:
        a = attr.strip()
        al = a.lower()
        if al.startswith("path="):
            path = a[5:].strip() or "/"
        elif al.startswith("max-age="):
            try:
                v = int(a[8:].strip())
                if v <= 0:
                    is_delete = True
                else:
                    ttl = max(60, v)
            except Exception:
                pass
        elif al.startswith("expires="):
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(a[8:].strip())
                diff = int(dt.timestamp() - time.time())
                if diff <= 0:
                    is_delete = True
                else:
                    ttl = max(60, diff)
            except Exception:
                pass
        elif al == "secure":
            secure = 1
        elif al == "httponly":
            http_only = 1
        elif al.startswith("samesite="):
            same_site = a[9:].strip().lower()
    return {
        "name": name, "value": value, "path": path, "ttl": ttl,
        "secure": secure, "http_only": http_only, "same_site": same_site,
        "delete": is_delete,
    }


def _harvest_setcookie(domain, headers, ttl, status, cfg):
    raw = None
    for k in ("set-cookie", "Set-Cookie", "SET-COOKIE"):
        if k in headers:
            raw = headers[k]
            break
    if not raw:
        return 0, 0, 0
    if isinstance(raw, str):
        raw = [raw]
    count = 0
    premium_count = 0
    delete_count = 0
    detect_premium = bool(cfg.get("premium_detection", True))
    decay = bool(cfg.get("decay_detection", True))
    for line in raw:
        parsed = _parse_setcookie_line(line, ttl)
        if not parsed:
            continue
        name = parsed["name"]
        if parsed["delete"] and decay:
            _delete_one(domain, name)
            delete_count += 1
            _log_event("decay", domain, name)
            continue
        value = parsed["value"]
        is_premium = 0
        if detect_premium and status == 200 and PREMIUM_NAME_RX.match(name) and len(value) >= 8:
            is_premium = 1
            premium_count += 1
        _set_one(
            domain, name, value, parsed["path"], parsed["ttl"],
            "harvest", premium=is_premium, secure=parsed["secure"],
            http_only=parsed["http_only"], same_site=parsed["same_site"],
            confirmed=1,
        )
        count += 1
    return count, premium_count, delete_count


def _harvest_from_js(domain, html_text, ttl):
    count = 0
    patterns = [
        re.compile(r"document\.cookie\s*=\s*['\"]([^='\"]+)=([^;'\"]+)", re.I),
        re.compile(r"setCookie\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", re.I),
        re.compile(r"Cookies\.set\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", re.I),
    ]
    seen = set()
    for rx in patterns:
        for m in rx.finditer(html_text):
            name = m.group(1).strip()
            value = m.group(2).strip()
            if not name or name in seen or len(name) > 120 or len(value) > 2000:
                continue
            seen.add(name)
            _set_one(domain, name, value, "/", ttl, "js", confirmed=0)
            count += 1
    return count


def _stats():
    c = _db()
    if c is None:
        return {"total": 0, "domains": 0, "premium": 0, "seeds": 0, "learning": 0, "locks": 0}
    try:
        return {
            "total": c.execute("SELECT COUNT(*) FROM cookies").fetchone()[0],
            "domains": c.execute("SELECT COUNT(DISTINCT domain) FROM cookies").fetchone()[0],
            "premium": c.execute("SELECT COUNT(*) FROM cookies WHERE premium=1").fetchone()[0],
            "seeds": c.execute("SELECT COUNT(*) FROM seeds").fetchone()[0],
            "learning": c.execute("SELECT COUNT(*) FROM learning").fetchone()[0],
            "locks": c.execute("SELECT COUNT(*) FROM locks").fetchone()[0],
        }
    except Exception:
        return {"total": 0, "domains": 0, "premium": 0, "seeds": 0, "learning": 0, "locks": 0}


def _pool_stats():
    c = _db()
    if c is None:
        return {}
    try:
        rows = c.execute("SELECT source, COUNT(*) FROM cookies GROUP BY source").fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _lr_evict(max_cookies):
    c = _db()
    if c is None:
        return 0
    try:
        total = c.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
        if total <= max_cookies:
            return 0
        excess = total - max_cookies
        c.execute(
            "DELETE FROM cookies WHERE (domain, name) IN "
            "(SELECT domain, name FROM cookies WHERE premium=0 ORDER BY created ASC LIMIT ?)",
            (excess,),
        )
        c.commit()
        return excess
    except Exception:
        return 0


def _scrub_pii(data):
    s = json.dumps(data, ensure_ascii=False)
    for rx in PII_RX:
        s = rx.sub("[REDACTED]", s)
    return s


def _encrypt(data: bytes, key: str) -> bytes:
    kb = hashlib.sha256(key.encode("utf-8")).digest()
    out = bytearray()
    for i, b in enumerate(data):
        out.append(b ^ kb[i % len(kb)])
    return base64.b64encode(bytes(out))


def _decrypt(data: bytes, key: str) -> bytes:
    try:
        raw = base64.b64decode(data)
    except Exception:
        return b""
    kb = hashlib.sha256(key.encode("utf-8")).digest()
    out = bytearray()
    for i, b in enumerate(raw):
        out.append(b ^ kb[i % len(kb)])
    return bytes(out)


def _export_netscape(items_by_domain):
    lines = ["# Netscape HTTP Cookie File", "# generated by CookieSeeder", ""]
    for domain, items in items_by_domain.items():
        for c in items:
            secure = "TRUE" if c.get("secure") else "FALSE"
            exp = int(c["expires"]) if c.get("expires") else 0
            lines.append("\t".join([
                domain, "TRUE", c.get("path", "/"), secure,
                str(exp), c["name"], c["value"],
            ]))
    return "\n".join(lines).encode("utf-8")


def _export_editthiscookie(items_by_domain):
    out = []
    for domain, items in items_by_domain.items():
        for c in items:
            out.append({
                "domain": domain, "name": c["name"], "value": c["value"],
                "path": c.get("path", "/"), "secure": bool(c.get("secure")),
                "httpOnly": bool(c.get("http_only")),
                "expirationDate": c.get("expires"),
                "sameSite": c.get("same_site", "unspecified"),
            })
    return json.dumps(out, ensure_ascii=False, indent=2).encode("utf-8")


def _curl_string(domain, items):
    cookie_str = "; ".join("%s=%s" % (c["name"], c["value"]) for c in items)
    return "curl -H 'Cookie: %s' 'https://%s/'" % (cookie_str.replace("'", "'\\''"), domain)


def _ascii_bar(value, max_value, width=40):
    if max_value <= 0:
        return ""
    filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


async def _send(event, text):
    if event is None:
        return
    if getattr(event, "out", False):
        try:
            await event.edit(text, parse_mode="html")
            return
        except Exception:
            pass
    try:
        await event.respond(text, parse_mode="html")
    except Exception:
        try:
            await event.reply(text, parse_mode="html")
        except Exception:
            pass


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def before_fetch(ctx):
    if not ctx.cfg.get("enabled", True):
        return None
    if not ctx.cfg.get("inject_on_before", True):
        return None
    url = ctx.get("url") or ""
    d = _domain(url)
    if not d:
        return None
    if _is_locked(d):
        return None
    if _in_blacklist(d):
        return None
    if _in_whitelist(d):
        pass
    _seed_domain(d, ctx.cfg.all())
    header = _cookie_header(d)
    if not header:
        return None
    headers = dict(ctx.get("headers") or {})
    if "Cookie" in headers and headers["Cookie"]:
        existing = headers["Cookie"]
        names_existing = set(x.split("=", 1)[0].strip() for x in existing.split(";") if "=" in x)
        extra = [c for c in _get_all(d) if c["name"] not in names_existing]
        if extra:
            headers["Cookie"] = existing + "; " + "; ".join("%s=%s" % (c["name"], c["value"]) for c in extra)
    else:
        headers["Cookie"] = header
    ctx["headers"] = headers
    return None


async def after_fetch(ctx):
    if not ctx.cfg.get("enabled", True):
        return None
    if not ctx.cfg.get("harvest_on_after", True):
        return None
    url = ctx.get("url") or ""
    d = _domain(url)
    if not d:
        return None
    if _is_locked(d):
        return None
    cfg = ctx.cfg.all()
    ttl = _domain_ttl(d, int(cfg.get("cookie_ttl", 21600) or 21600))
    headers = ctx.get("headers") or {}
    status = int(ctx.get("status") or 200)
    n1, nprem, ndel = _harvest_setcookie(d, headers, ttl, status, cfg)
    html = ctx.get("html") or ""
    n2 = _harvest_from_js(d, html[:200000], ttl) if html else 0
    if n1 or nprem or ndel or n2:
        _log_event("harvest", d, extra="h=%d p=%d d=%d j=%d" % (n1, nprem, ndel, n2))
    if cfg.get("domain_learning", True):
        info = _learning_get(d)
        _learning_set(d, total_ok=info["total_ok"] + 1)
    _lr_evict(int(cfg.get("lr_max_cookies", 20000) or 20000))
    return None


async def on_blocked(ctx):
    if not ctx.cfg.get("enabled", True):
        return None
    if not ctx.cfg.get("harvest_on_blocked", True):
        return None
    url = ctx.get("url") or ""
    d = _domain(url)
    if not d or _is_locked(d):
        return None
    cfg = ctx.cfg.all()
    html = ctx.get("html") or ""
    ttl = _domain_ttl(d, int(cfg.get("cookie_ttl", 21600) or 21600))

    if html:
        m = re.search(r"cf_clearance=([^;\"'\s]+)", html, re.I)
        if m:
            _set_one(d, "cf_clearance", m.group(1), "/", ttl, "cf-clearance", premium=1, confirmed=1)
            _log_event("cf_clearance", d)
        _harvest_from_js(d, html[:200000], ttl)

    if cfg.get("domain_learning", True):
        reason = (ctx.get("reason") or "").lower()
        info = _learning_get(d)
        kw = {"total_blocks": info["total_blocks"] + 1}
        if reason == "cloudflare":
            new_cf = info["cf_blocks"] + 1
            kw["cf_blocks"] = new_cf
            threshold = int(cfg.get("cf_block_threshold", 5) or 5)
            if new_cf >= threshold:
                kw["cf_disabled_until"] = time.time() + int(cfg.get("cf_disable_ttl", 86400) or 86400)
                kw["cf_blocks"] = 0
                _log_event("cf_disabled", d)
        _learning_set(d, **kw)
    return None


HELP_TEXT = (
    "<b>CookieSeeder</b> <code>//</code> <code>v2.0.0</code>\n"
    "\n"
    "<blockquote><b>list</b> — <code>%sdothat ck list [domain]</code>\n"
    "<b>clear</b> — <code>%sdothat ck clear &lt;domain&gt;</code>\n"
    "<b>seed</b> — <code>%sdothat ck seed &lt;domain&gt;</code>\n"
    "<b>why</b> — <code>%sdothat ck why &lt;domain&gt; &lt;name&gt;</code>\n"
    "<b>tail</b> — <code>%sdothat ck tail</code>\n"
    "<b>stats</b> — <code>%sdothat ck stats</code>\n"
    "<b>pools</b> — <code>%sdothat ck pools</code>\n"
    "<b>top</b> — <code>%sdothat ck top [n]</code>\n"
    "<b>graph</b> — <code>%sdothat ck graph [n]</code>\n"
    "<b>learning</b> — <code>%sdothat ck learning [domain]</code>\n"
    "<b>reset</b> — <code>%sdothat ck reset &lt;domain&gt;</code>\n"
    "<b>lock</b> — <code>%sdothat ck lock &lt;domain&gt; [note]</code>\n"
    "<b>unlock</b> — <code>%sdothat ck unlock &lt;domain&gt;</code>\n"
    "<b>locks</b> — <code>%sdothat ck locks</code>\n"
    "<b>wl</b> — <code>%sdothat ck wl add|remove|list &lt;domain&gt;</code>\n"
    "<b>bl</b> — <code>%sdothat ck bl add|remove|list &lt;domain&gt;</code>\n"
    "<b>ttl</b> — <code>%sdothat ck ttl set|get|del &lt;domain&gt; [sec]</code>\n"
    "<b>export</b> — <code>%sdothat ck export [json|netscape|etc|encrypted]</code>\n"
    "<b>import</b> — <code>%sdothat ck import</code> (reply to json)\n"
    "<b>curl</b> — <code>%sdothat ck curl &lt;domain&gt;</code></blockquote>"
)


def _help(prefix):
    return HELP_TEXT % tuple([prefix] * 21)


async def on_command(ctx):
    action = (ctx.get("action") or "").lower()
    if action != "ck":
        return None
    if not ctx.cfg.get("enabled", True):
        return None
    role = (ctx.get("role") or "").lower()
    if role not in ("owner", "superadmin", "admin"):
        return None
    event = ctx.get("event")
    prefix = ctx.get("prefix") or "."
    args = (ctx.get("args") or "").strip()
    if args.lower().startswith("ck"):
        args = args[2:].strip()
    parts = args.split(maxsplit=2)
    sub = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    tail = parts[2] if len(parts) > 2 else ""

    if not sub or sub == "help":
        await _send(event, _help(prefix))
        return True

    mapping = {
        "list": _cmd_list, "clear": _cmd_clear, "del": _cmd_clear, "seed": _cmd_seed,
        "why": _cmd_why, "tail": _cmd_tail, "stats": _cmd_stats, "pools": _cmd_pools,
        "top": _cmd_top, "graph": _cmd_graph, "learning": _cmd_learning, "reset": _cmd_reset,
        "lock": _cmd_lock, "unlock": _cmd_unlock, "locks": _cmd_locks,
        "wl": _cmd_wl, "bl": _cmd_bl, "ttl": _cmd_ttl,
        "export": _cmd_export, "import": _cmd_import, "curl": _cmd_curl,
    }
    handler = mapping.get(sub)
    if handler is None:
        await _send(event, "<b>err</b> — <code>unknown: %s</code>\n\n%s" % (_esc(sub), _help(prefix)))
        return True
    try:
        await handler(event, rest, tail, prefix)
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))
    return True


async def _cmd_list(event, rest, tail, prefix):
    if not rest:
        s = _stats()
        await _send(event,
            "<b>ck</b>\n<blockquote>"
            "<b>total</b> — <code>%d</code>\n<b>domains</b> — <code>%d</code>\n"
            "<b>premium</b> — <code>%d</code>\n<b>seeds</b> — <code>%d</code>\n"
            "<b>learning</b> — <code>%d</code>\n<b>locks</b> — <code>%d</code>"
            "</blockquote>" % (s["total"], s["domains"], s["premium"], s["seeds"], s["learning"], s["locks"]))
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    items = _get_all(d)
    if not items:
        await _send(event, "<b>ck</b> — <code>empty: %s</code>" % _esc(d))
        return
    lines = ["<b>ck</b> <code>//</code> <code>%s</code> <code>//</code> <code>%d</code>" % (_esc(d), len(items))]
    for c in items:
        mark = "⭐" if c["premium"] else ("✓" if c["confirmed"] else "·")
        flags = []
        if c["secure"]: flags.append("S")
        if c["http_only"]: flags.append("H")
        if c["same_site"]: flags.append("SS=%s" % c["same_site"])
        fl = " ".join(flags)
        ttl = int((c["expires"] - time.time()) / 60)
        lines.append("<blockquote>%s <b>%s</b> <code>%s</code>\n<i>%s · ttl %dm %s</i></blockquote>"
                     % (mark, _esc(c["name"]), _esc(c["value"][:60]), _esc(c["source"]), ttl, fl))
    await _send(event, "\n".join(lines))


async def _cmd_clear(event, rest, tail, prefix):
    if not rest:
        await _send(event, "<b>err</b> — <code>clear &lt;domain&gt;</code>")
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    c = _db()
    if c is None:
        return
    try:
        n = c.execute("DELETE FROM cookies WHERE domain=?", (d,)).rowcount
        c.execute("DELETE FROM seeds WHERE domain=?", (d,))
        c.commit()
        _cache_invalidate(d)
        await _send(event, "<b>ck clear</b> <code>//</code> <code>%s</code> — <code>%d</code>" % (_esc(d), n))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_seed(event, rest, tail, prefix):
    if not rest:
        await _send(event, "<b>err</b> — <code>seed &lt;domain&gt;</code>")
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    c = _db()
    if c is not None:
        try:
            c.execute("DELETE FROM seeds WHERE domain=?", (d,))
            c.commit()
        except Exception:
            pass
    from types import SimpleNamespace
    class _CfgWrap:
        def __init__(self, data): self._d = data
        def get(self, k, default=None): return self._d.get(k, default)
        def all(self): return dict(self._d)
    default_cfg = _CfgWrap({
        "seed_ga": True, "seed_fbp": True, "seed_ym": True,
        "seed_session": True, "seed_consent": True, "seed_analytics": True,
        "seed_cf": True, "seed_tcf": True, "seed_ads": True, "seed_cms": True,
        "cookie_ttl": 21600, "max_cookies_per_domain": 60,
        "auto_geo_profile": True, "default_browser_profile": "chrome_win_ru",
        "premium_detection": True,
    })
    _seed_domain(d, default_cfg)
    _flush_pending()
    items = _get_all(d)
    await _send(event, "<b>ck seed</b> <code>//</code> <code>%s</code> — <code>%d</code>" % (_esc(d), len(items)))


async def _cmd_why(event, rest, tail, prefix):
    if not rest or not tail:
        await _send(event, "<b>err</b> — <code>why &lt;domain&gt; &lt;name&gt;</code>")
        return
    d = rest.strip().lower()
    name = tail.strip()
    if "://" in d:
        d = _domain(d)
    c = _db()
    if c is None:
        return
    try:
        row = c.execute(
            "SELECT value, source, premium, length(value), created, expires, confirmed, seen_count "
            "FROM cookies WHERE domain=? AND name=?", (d, name)
        ).fetchone()
        if not row:
            await _send(event, "<b>err</b> — <code>not found</code>")
            return
        value, source, premium, vlen, created, expires, confirmed, seen = row
        regex_hit = bool(PREMIUM_NAME_RX.match(name))
        lines = [
            "<b>ck why</b> <code>//</code> <code>%s</code> <code>//</code> <code>%s</code>" % (_esc(d), _esc(name)),
            "<blockquote><b>value</b> — <code>%s</code>" % _esc(str(value)[:80]),
            "<b>source</b> — <code>%s</code>" % _esc(source),
            "<b>premium</b> — <code>%s</code>" % ("yes" if premium else "no"),
            "<b>regex_match</b> — <code>%s</code>" % ("yes" if regex_hit else "no"),
            "<b>length</b> — <code>%d</code>" % vlen,
            "<b>confirmed</b> — <code>%s</code>" % ("yes" if confirmed else "no"),
            "<b>seen_count</b> — <code>%d</code>" % (seen or 0),
            "<b>created</b> — <code>%s</code>" % time.strftime("%Y-%m-%d %H:%M", time.localtime(created)),
            "<b>ttl</b> — <code>%dm</code>" % int((expires - time.time()) / 60),
            "</blockquote>",
        ]
        await _send(event, "\n".join(lines))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_tail(event, rest, tail, prefix):
    with _LOG_LOCK:
        recent = list(_LOG_BUFFER[-30:])
    if not recent:
        await _send(event, "<b>ck tail</b> — <code>empty</code>")
        return
    lines = ["<b>ck tail</b> <code>//</code> <code>%d</code>" % len(recent)]
    for r in recent:
        ts = time.strftime("%H:%M:%S", time.localtime(r["ts"]))
        lines.append("<blockquote><code>%s</code> <b>%s</b> <code>%s</code> <i>%s</i></blockquote>"
                     % (ts, _esc(r["kind"]), _esc(r["domain"][:40]), _esc(r.get("extra", ""))))
    await _send(event, "\n".join(lines))


async def _cmd_stats(event, rest, tail, prefix):
    s = _stats()
    p = _pool_stats()
    pools_lines = "\n".join("  <b>%s</b> — <code>%d</code>" % (_esc(k), v) for k, v in sorted(p.items()))
    await _send(event,
        "<b>ck stats</b>\n<blockquote>"
        "<b>total</b> — <code>%d</code>\n<b>domains</b> — <code>%d</code>\n"
        "<b>premium</b> — <code>%d</code>\n<b>seeds</b> — <code>%d</code>\n"
        "<b>learning</b> — <code>%d</code>\n<b>locks</b> — <code>%d</code>\n\n"
        "<b>by source</b>\n%s</blockquote>"
        % (s["total"], s["domains"], s["premium"], s["seeds"], s["learning"], s["locks"], pools_lines))


async def _cmd_pools(event, rest, tail, prefix):
    lines = ["<b>ck pools</b>"]
    for name in sorted(COOKIE_POOLS.keys()):
        lines.append("<blockquote><b>%s</b> — <code>%d</code> cookies</blockquote>"
                     % (_esc(name), len(COOKIE_POOLS[name])))
    lines.append("<blockquote><b>browser profiles</b>\n%s</blockquote>"
                 % "\n".join("  <code>%s</code>" % _esc(k) for k in BROWSER_PROFILES))
    lines.append("<blockquote><b>geo profiles</b>\n%s</blockquote>"
                 % "\n".join("  <code>%s</code> → %s" % (_esc(k), ", ".join(v)) for k, v in GEO_PROFILES.items()))
    await _send(event, "\n".join(lines))


async def _cmd_top(event, rest, tail, prefix):
    n = 10
    if rest.strip().isdigit():
        n = max(1, min(50, int(rest.strip())))
    c = _db()
    if c is None:
        return
    try:
        rows = c.execute("SELECT domain, COUNT(*) FROM cookies GROUP BY domain ORDER BY COUNT(*) DESC LIMIT ?", (n,)).fetchall()
        if not rows:
            await _send(event, "<b>ck top</b> — <code>empty</code>")
            return
        maxv = rows[0][1] if rows else 1
        lines = ["<b>ck top</b> <code>//</code> <code>%d</code>" % n]
        for i, (d, cnt) in enumerate(rows, 1):
            bar = _ascii_bar(cnt, maxv, 20)
            lines.append("<blockquote><b>%d.</b> <code>%s</code> — <code>%d</code> %s</blockquote>"
                         % (i, _esc(d), cnt, bar))
        await _send(event, "\n".join(lines))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_graph(event, rest, tail, prefix):
    n = 15
    if rest.strip().isdigit():
        n = max(1, min(50, int(rest.strip())))
    c = _db()
    if c is None:
        return
    try:
        rows = c.execute(
            "SELECT substr(source, 1, 20), COUNT(*) FROM cookies GROUP BY source ORDER BY COUNT(*) DESC LIMIT ?",
            (n,),
        ).fetchall()
        if not rows:
            await _send(event, "<b>ck graph</b> — <code>empty</code>")
            return
        maxv = rows[0][1]
        lines = ["<b>ck graph</b> <code>//</code> <code>by source</code>"]
        for src, cnt in rows:
            bar = _ascii_bar(cnt, maxv, 30)
            lines.append("<blockquote><code>%-20s</code> %s <code>%d</code></blockquote>"
                         % (_esc(src), bar, cnt))
        await _send(event, "\n".join(lines))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_learning(event, rest, tail, prefix):
    c = _db()
    if c is None:
        return
    if not rest:
        try:
            rows = c.execute("SELECT domain, cf_blocks, cf_disabled_until, total_blocks, total_ok FROM learning ORDER BY total_blocks DESC LIMIT 20").fetchall()
            if not rows:
                await _send(event, "<b>ck learning</b> — <code>empty</code>")
                return
            now = time.time()
            lines = ["<b>ck learning</b> <code>//</code> <code>top 20</code>"]
            for d, cfb, cfd, tb, tok in rows:
                cf_mark = ""
                if cfd and cfd > now:
                    cf_mark = " [cf_off %dm]" % int((cfd - now) / 60)
                lines.append("<blockquote><b>%s</b>%s\n<i>blocks=%d cf=%d ok=%d</i></blockquote>"
                             % (_esc(d), cf_mark, tb or 0, cfb or 0, tok or 0))
            await _send(event, "\n".join(lines))
        except Exception as e:
            await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    info = _learning_get(d)
    now = time.time()
    cf_line = "—"
    if info["cf_disabled_until"] > now:
        cf_line = "disabled %dm" % int((info["cf_disabled_until"] - now) / 60)
    elif info["cf_disabled_until"] > 0:
        cf_line = "expired"
    await _send(event,
        "<b>ck learning</b> <code>//</code> <code>%s</code>\n<blockquote>"
        "<b>blocks</b> — <code>%d</code>\n<b>cf_blocks</b> — <code>%d</code>\n"
        "<b>cf_state</b> — <code>%s</code>\n<b>ok</b> — <code>%d</code></blockquote>"
        % (_esc(d), info["total_blocks"], info["cf_blocks"], cf_line, info["total_ok"]))


async def _cmd_reset(event, rest, tail, prefix):
    if not rest:
        await _send(event, "<b>err</b> — <code>reset &lt;domain&gt;</code>")
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    c = _db()
    if c is None:
        return
    try:
        c.execute("DELETE FROM learning WHERE domain=?", (d,))
        c.commit()
        await _send(event, "<b>ck reset</b> <code>//</code> <code>%s</code>" % _esc(d))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_lock(event, rest, tail, prefix):
    if not rest:
        await _send(event, "<b>err</b> — <code>lock &lt;domain&gt; [note]</code>")
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    c = _db()
    if c is None:
        return
    try:
        c.execute("INSERT OR REPLACE INTO locks (domain, note, created) VALUES (?,?,?)", (d, tail, time.time()))
        c.commit()
        await _send(event, "<b>ck lock</b> <code>//</code> <code>%s</code> %s" % (_esc(d), _esc(tail)))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_unlock(event, rest, tail, prefix):
    if not rest:
        await _send(event, "<b>err</b> — <code>unlock &lt;domain&gt;</code>")
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    c = _db()
    if c is None:
        return
    try:
        c.execute("DELETE FROM locks WHERE domain=?", (d,))
        c.commit()
        await _send(event, "<b>ck unlock</b> <code>//</code> <code>%s</code>" % _esc(d))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_locks(event, rest, tail, prefix):
    c = _db()
    if c is None:
        return
    try:
        rows = c.execute("SELECT domain, note, created FROM locks ORDER BY created DESC").fetchall()
        if not rows:
            await _send(event, "<b>ck locks</b> — <code>empty</code>")
            return
        lines = ["<b>ck locks</b> <code>//</code> <code>%d</code>" % len(rows)]
        for d, note, ts in rows:
            lines.append("<blockquote><code>%s</code> — <i>%s</i></blockquote>"
                         % (_esc(d), _esc(note or "-")))
        await _send(event, "\n".join(lines))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_wl(event, rest, tail, prefix):
    await _list_cmd(event, "whitelist", rest, tail, "wl")


async def _cmd_bl(event, rest, tail, prefix):
    await _list_cmd(event, "blacklist", rest, tail, "bl")


async def _list_cmd(event, table, rest, tail, name):
    c = _db()
    if c is None:
        return
    parts = rest.split(maxsplit=1)
    sub = parts[0].lower() if parts else ""
    d = parts[1].strip().lower() if len(parts) > 1 else ""
    if "://" in d:
        d = _domain(d)
    try:
        if sub == "add" and d:
            c.execute("INSERT OR REPLACE INTO %s (domain) VALUES (?)" % table, (d,))
            c.commit()
            await _send(event, "<b>ck %s add</b> <code>//</code> <code>%s</code>" % (name, _esc(d)))
            return
        if sub in ("remove", "del") and d:
            c.execute("DELETE FROM %s WHERE domain=?" % table, (d,))
            c.commit()
            await _send(event, "<b>ck %s remove</b> <code>//</code> <code>%s</code>" % (name, _esc(d)))
            return
        if sub in ("list", "") or not sub:
            rows = c.execute("SELECT domain FROM %s ORDER BY domain" % table).fetchall()
            if not rows:
                await _send(event, "<b>ck %s</b> — <code>empty</code>" % name)
                return
            lines = ["<b>ck %s</b> <code>//</code> <code>%d</code>" % (name, len(rows))]
            for (dom,) in rows:
                lines.append("<blockquote><code>%s</code></blockquote>" % _esc(dom))
            await _send(event, "\n".join(lines))
            return
        await _send(event, "<b>err</b> — <code>%s add|remove|list [domain]</code>" % name)
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_ttl(event, rest, tail, prefix):
    c = _db()
    if c is None:
        return
    parts = rest.split()
    sub = parts[0].lower() if parts else ""
    d = parts[1].strip().lower() if len(parts) > 1 else ""
    if "://" in d:
        d = _domain(d)
    try:
        if sub == "set" and d and len(parts) > 2:
            try:
                ttl = int(parts[2])
            except ValueError:
                await _send(event, "<b>err</b> — <code>ttl must be int</code>")
                return
            c.execute("INSERT OR REPLACE INTO domain_ttl (domain, ttl) VALUES (?,?)", (d, ttl))
            c.commit()
            await _send(event, "<b>ck ttl set</b> <code>//</code> <code>%s</code> <code>%d</code>" % (_esc(d), ttl))
            return
        if sub == "get" and d:
            row = c.execute("SELECT ttl FROM domain_ttl WHERE domain=?", (d,)).fetchone()
            if row:
                await _send(event, "<b>ck ttl</b> <code>//</code> <code>%s</code> <code>%d</code>" % (_esc(d), row[0]))
            else:
                await _send(event, "<b>ck ttl</b> — <code>no override for %s</code>" % _esc(d))
            return
        if sub in ("del", "remove") and d:
            c.execute("DELETE FROM domain_ttl WHERE domain=?", (d,))
            c.commit()
            await _send(event, "<b>ck ttl del</b> <code>//</code> <code>%s</code>" % _esc(d))
            return
        if sub == "list":
            rows = c.execute("SELECT domain, ttl FROM domain_ttl ORDER BY domain").fetchall()
            if not rows:
                await _send(event, "<b>ck ttl</b> — <code>empty</code>")
                return
            lines = ["<b>ck ttl</b> <code>//</code> <code>%d</code>" % len(rows)]
            for dom, t in rows:
                lines.append("<blockquote><code>%s</code> — <code>%d</code></blockquote>" % (_esc(dom), t))
            await _send(event, "\n".join(lines))
            return
        await _send(event, "<b>err</b> — <code>ttl set|get|del|list [domain] [sec]</code>")
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_export(event, rest, tail, prefix):
    fmt = rest.strip().lower() or "json"
    c = _db()
    if c is None:
        return
    try:
        rows = c.execute("SELECT domain, name, value, path, expires, source, premium, secure, http_only, same_site FROM cookies").fetchall()
        data = {}
        for d, name, value, path, expires, source, premium, secure, http_only, same_site in rows:
            data.setdefault(d, []).append({
                "name": name, "value": value, "path": path or "/",
                "expires": expires, "source": source or "seed",
                "premium": bool(premium), "secure": bool(secure),
                "http_only": bool(http_only), "same_site": same_site or "",
            })
        cfg_scrub = True
        if fmt == "netscape":
            payload = _export_netscape(data)
            fname = "cookies_netscape.txt"
        elif fmt in ("etc", "editthiscookie"):
            payload = _export_editthiscookie(data)
            fname = "cookies_editthiscookie.json"
        elif fmt == "encrypted":
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            payload = _encrypt(raw, "cookieseeder-default")
            fname = "cookies_encrypted.b64"
        else:
            if cfg_scrub:
                raw_text = _scrub_pii(data)
                payload = raw_text.encode("utf-8")
            else:
                payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            fname = "cookies_%d.json" % int(time.time())
        if event is None:
            return
        try:
            await event.client.send_file(event.chat_id, payload, file_name=fname,
                                          caption="<b>ck export</b> <code>//</code> <code>%s</code>"
                                                  % _esc(fmt), parse_mode="html")
        except Exception as e:
            await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))


async def _cmd_import(event, rest, tail, prefix):
    if event is None:
        return
    reply = None
    try:
        reply = await event.get_reply_message()
    except Exception:
        reply = None
    if reply is None:
        await _send(event, "<b>err</b> — <code>reply to json</code>")
        return
    try:
        raw = await reply.download_media(bytes)
    except Exception as e:
        await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))
        return
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except Exception as e:
            await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))
            return
    else:
        try:
            data = json.loads(_decrypt(raw, "cookieseeder-default").decode("utf-8"))
        except Exception as e:
            await _send(event, "<b>err</b> — <code>%s</code>" % _esc(str(e)))
            return
    count = 0
    if isinstance(data, dict):
        for d, items in data.items():
            if not isinstance(items, list):
                continue
            for c in items:
                if not isinstance(c, dict) or "name" not in c or "value" not in c:
                    continue
                _set_one(
                    d, c["name"], c["value"], c.get("path", "/"),
                    int(c.get("expires", 0) - time.time()) if c.get("expires") else 21600,
                    c.get("source", "import"), premium=int(bool(c.get("premium"))),
                    secure=int(bool(c.get("secure"))), http_only=int(bool(c.get("http_only"))),
                    same_site=c.get("same_site", ""), confirmed=1,
                )
                count += 1
    _flush_pending()
    await _send(event, "<b>ck import</b> <code>//</code> <code>%d</code>" % count)


async def _cmd_curl(event, rest, tail, prefix):
    if not rest:
        await _send(event, "<b>err</b> — <code>curl &lt;domain&gt;</code>")
        return
    d = rest.strip().lower()
    if "://" in d:
        d = _domain(d)
    items = _get_all(d)
    if not items:
        await _send(event, "<b>err</b> — <code>empty: %s</code>" % _esc(d))
        return
    s = _curl_string(d, items)
    await _send(event, "<b>ck curl</b>\n" + s)


def stats(ctx=None):
    return _stats()


def health(ctx=None):
    s = _stats()
    return {"status": "ok", "message": "cookies=%d domains=%d premium=%d locks=%d"
            % (s["total"], s["domains"], s["premium"], s["locks"])}