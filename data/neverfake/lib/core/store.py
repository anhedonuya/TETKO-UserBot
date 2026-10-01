import sqlite3
import threading
import time
from pathlib import Path

SCHEMA_V1 = [
    "CREATE TABLE IF NOT EXISTS identities (domain TEXT PRIMARY KEY, device_seed TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL, visit_count INTEGER DEFAULT 0, ua_locked TEXT, lang_locked TEXT, tz_locked TEXT, tls_locked TEXT, tls_profile TEXT, hints_json TEXT)",
    "CREATE TABLE IF NOT EXISTS cookies (domain TEXT NOT NULL, proxy_key TEXT NOT NULL DEFAULT '', name TEXT NOT NULL, value TEXT NOT NULL, path TEXT DEFAULT '/', cookie_domain TEXT DEFAULT '', expires_at REAL, secure INTEGER DEFAULT 0, http_only INTEGER DEFAULT 0, same_site TEXT, kind TEXT NOT NULL, source TEXT, created_at REAL NOT NULL, last_sent_at REAL, send_count INTEGER DEFAULT 0, PRIMARY KEY (domain, proxy_key, name, path))",
    "CREATE TABLE IF NOT EXISTS seed_stats (domain TEXT NOT NULL, template TEXT NOT NULL, seeded_at REAL NOT NULL, outcome TEXT, latency_ms REAL)",
    "CREATE TABLE IF NOT EXISTS cooldowns (domain TEXT NOT NULL, strategy TEXT NOT NULL, until_ts REAL NOT NULL, reason TEXT, PRIMARY KEY (domain, strategy))",
    "CREATE TABLE IF NOT EXISTS harvest_log (ts REAL NOT NULL, domain TEXT NOT NULL, proxy_key TEXT DEFAULT '', name TEXT NOT NULL, kind TEXT NOT NULL, source TEXT, status INTEGER)",
    "CREATE TABLE IF NOT EXISTS events (ts REAL NOT NULL, kind TEXT NOT NULL, domain TEXT, data TEXT)",
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)",
]

class Store:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._lock = threading.Lock()

    def _connect(self):
        if self._conn is not None:
            return self._conn
        c = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            c.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        for s in SCHEMA_V1:
            try:
                c.execute(s)
            except Exception:
                pass
        c.commit()
        self._conn = c
        return c

    def close(self):
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def _rows(self, sql, params=()):
        with self._lock:
            c = self._connect()
            return c.execute(sql, params).fetchall()

    def _exec(self, sql, params=()):
        with self._lock:
            c = self._connect()
            c.execute(sql, params)
            c.commit()

    def get_identity(self, domain):
        r = self._rows("SELECT domain, device_seed, created_at, last_seen, visit_count, ua_locked, lang_locked, tz_locked, tls_locked, tls_profile, hints_json FROM identities WHERE domain=?", (domain,))
        if not r:
            return None
        x = r[0]
        return {"domain": x[0], "device_seed": x[1], "created_at": x[2], "last_seen": x[3], "visit_count": x[4] or 0, "ua_locked": x[5], "lang_locked": x[6], "tz_locked": x[7], "tls_locked": x[8], "tls_profile": x[9], "hints_json": x[10]}

    def upsert_identity(self, domain, data):
        self._exec("INSERT OR REPLACE INTO identities (domain, device_seed, created_at, last_seen, visit_count, ua_locked, lang_locked, tz_locked, tls_locked, tls_profile, hints_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (domain, data["device_seed"], data.get("created_at", time.time()), time.time(), int(data.get("visit_count", 0)), data.get("ua_locked"), data.get("lang_locked"), data.get("tz_locked"), data.get("tls_locked"), data.get("tls_profile"), data.get("hints_json")))

    def bump_visit(self, domain):
        self._exec("UPDATE identities SET visit_count = visit_count + 1, last_seen = ? WHERE domain = ?", (time.time(), domain))

    def list_cookies(self, domain, proxy_key=""):
        r = self._rows("SELECT name, value, path, cookie_domain, expires_at, secure, http_only, same_site, kind, source, send_count, created_at FROM cookies WHERE domain=? AND proxy_key=? ORDER BY kind, name", (domain, proxy_key))
        return [{"name": x[0], "value": x[1], "path": x[2], "cookie_domain": x[3], "expires_at": x[4], "secure": bool(x[5]), "http_only": bool(x[6]), "same_site": x[7], "kind": x[8], "source": x[9], "send_count": x[10] or 0, "created_at": x[11]} for x in r]

    def put_cookie(self, domain, proxy_key, data):
        self._exec("INSERT OR REPLACE INTO cookies (domain, proxy_key, name, value, path, cookie_domain, expires_at, secure, http_only, same_site, kind, source, created_at, last_sent_at, send_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (domain, proxy_key, data["name"], data["value"], data.get("path", "/"), data.get("cookie_domain", ""), data.get("expires_at"), 1 if data.get("secure") else 0, 1 if data.get("http_only") else 0, data.get("same_site"), data.get("kind", "seed"), data.get("source"), time.time(), data.get("last_sent_at"), int(data.get("send_count", 0))))

    def delete_cookie(self, domain, proxy_key, name, path="/"):
        self._exec("DELETE FROM cookies WHERE domain=? AND proxy_key=? AND name=? AND path=?", (domain, proxy_key, name, path))

    def clear_domain(self, domain):
        self._exec("DELETE FROM cookies WHERE domain=?", (domain,))
        self._exec("DELETE FROM identities WHERE domain=?", (domain,))
        self._exec("DELETE FROM cooldowns WHERE domain=?", (domain,))

    def log_seed(self, domain, template, outcome, latency_ms=None):
        self._exec("INSERT INTO seed_stats (domain, template, seeded_at, outcome, latency_ms) VALUES (?,?,?,?,?)", (domain, template, time.time(), outcome, latency_ms))

    def log_harvest(self, domain, proxy_key, name, kind, source, status):
        self._exec("INSERT INTO harvest_log (ts, domain, proxy_key, name, kind, source, status) VALUES (?,?,?,?,?,?,?)", (time.time(), domain, proxy_key, name, kind, source, status))

    def log_event(self, kind, domain, data):
        try:
            self._exec("INSERT INTO events (ts, kind, domain, data) VALUES (?,?,?,?)", (time.time(), kind, domain, str(data)[:500]))
        except Exception:
            pass

    def cooldown_active(self, domain, strategy):
        r = self._rows("SELECT until_ts FROM cooldowns WHERE domain=? AND strategy=?", (domain, strategy))
        if not r:
            return False
        if r[0][0] < time.time():
            self._exec("DELETE FROM cooldowns WHERE domain=? AND strategy=?", (domain, strategy))
            return False
        return True

    def set_cooldown(self, domain, strategy, seconds, reason=""):
        self._exec("INSERT OR REPLACE INTO cooldowns (domain, strategy, until_ts, reason) VALUES (?,?,?,?)", (domain, strategy, time.time() + seconds, reason))

    def clear_cooldown(self, domain, strategy="fetch"):
        self._exec("DELETE FROM cooldowns WHERE domain=? AND strategy=?", (domain, strategy))

    def domain_summary(self, domain):
        total = self._rows("SELECT COUNT(*) FROM cookies WHERE domain=?", (domain,))
        kinds = dict(self._rows("SELECT kind, COUNT(*) FROM cookies WHERE domain=? GROUP BY kind", (domain,)))
        cd = dict(self._rows("SELECT strategy, until_ts FROM cooldowns WHERE domain=?", (domain,)))
        return {"total": total[0][0] if total else 0, "kinds": kinds, "cooldowns": cd}

    def global_stats(self):
        idents = self._rows("SELECT COUNT(*) FROM identities")
        cks = self._rows("SELECT COUNT(*) FROM cookies")
        kinds = dict(self._rows("SELECT kind, COUNT(*) FROM cookies GROUP BY kind"))
        cd = self._rows("SELECT COUNT(*) FROM cooldowns WHERE until_ts > ?", (time.time(),))
        top = self._rows("SELECT domain, COUNT(*) c FROM cookies GROUP BY domain ORDER BY c DESC LIMIT 15")
        return {"identities": idents[0][0] if idents else 0, "cookies": cks[0][0] if cks else 0, "kinds": kinds, "cooldowns": cd[0][0] if cd else 0, "top": top}

    def get_meta(self, key, default=None):
        r = self._rows("SELECT value FROM meta WHERE key=?", (key,))
        return r[0][0] if r else default

    def set_meta(self, key, value):
        self._exec("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, str(value)))

    def cleanup_inactive(self, days=30):
        cutoff = time.time() - days * 86400
        r = self._rows("SELECT domain FROM identities WHERE last_seen < ?", (cutoff,))
        n = 0
        for x in r:
            self._exec("DELETE FROM cookies WHERE domain=?", (x[0],))
            self._exec("DELETE FROM identities WHERE domain=?", (x[0],))
            self._exec("DELETE FROM cooldowns WHERE domain=?", (x[0],))
            n += 1
        return n
