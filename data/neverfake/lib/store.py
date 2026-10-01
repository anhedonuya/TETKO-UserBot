"""SQLite store: identities, cookies, seed_stats, cooldowns, harvest_log."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS identities (domain TEXT PRIMARY KEY, device_seed TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL, visit_count INTEGER DEFAULT 0, ua_locked TEXT, lang_locked TEXT, tz_locked TEXT, tls_locked TEXT)",
    "CREATE TABLE IF NOT EXISTS cookies (domain TEXT NOT NULL, proxy_key TEXT NOT NULL DEFAULT '', name TEXT NOT NULL, value TEXT NOT NULL, path TEXT DEFAULT '/', expires_at REAL, secure INTEGER DEFAULT 0, http_only INTEGER DEFAULT 0, same_site TEXT, kind TEXT NOT NULL, source TEXT, created_at REAL NOT NULL, last_sent_at REAL, send_count INTEGER DEFAULT 0, PRIMARY KEY (domain, proxy_key, name, path))",
    "CREATE TABLE IF NOT EXISTS seed_stats (domain TEXT NOT NULL, template TEXT NOT NULL, seeded_at REAL NOT NULL, outcome TEXT, latency_ms REAL)",
    "CREATE TABLE IF NOT EXISTS cooldowns (domain TEXT NOT NULL, strategy TEXT NOT NULL, until_ts REAL NOT NULL, reason TEXT, PRIMARY KEY (domain, strategy))",
    "CREATE TABLE IF NOT EXISTS harvest_log (ts REAL NOT NULL, domain TEXT NOT NULL, proxy_key TEXT DEFAULT '', name TEXT NOT NULL, kind TEXT NOT NULL, source TEXT, status INTEGER)",
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
        for stmt in _SCHEMA:
            c.execute(stmt)
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

    def get_identity(self, domain):
        with self._lock:
            c = self._connect()
            row = c.execute(
                "SELECT domain, device_seed, created_at, last_seen, visit_count, ua_locked, lang_locked, tz_locked, tls_locked FROM identities WHERE domain=?",
                (domain,),
            ).fetchone()
            if row is None:
                return None
            return {
                "domain": row[0], "device_seed": row[1],
                "created_at": row[2], "last_seen": row[3],
                "visit_count": row[4] or 0,
                "ua_locked": row[5], "lang_locked": row[6],
                "tz_locked": row[7], "tls_locked": row[8],
            }

    def upsert_identity(self, domain, data):
        with self._lock:
            c = self._connect()
            c.execute(
                "INSERT OR REPLACE INTO identities (domain, device_seed, created_at, last_seen, visit_count, ua_locked, lang_locked, tz_locked, tls_locked) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    domain, data["device_seed"],
                    data.get("created_at", time.time()), time.time(),
                    int(data.get("visit_count", 0)),
                    data.get("ua_locked"), data.get("lang_locked"),
                    data.get("tz_locked"), data.get("tls_locked"),
                ),
            )
            c.commit()

    def bump_visit(self, domain):
        with self._lock:
            c = self._connect()
            c.execute("UPDATE identities SET visit_count = visit_count + 1, last_seen = ? WHERE domain = ?", (time.time(), domain))
            c.commit()

    def list_cookies(self, domain, proxy_key=""):
        with self._lock:
            c = self._connect()
            rows = c.execute(
                "SELECT name, value, path, expires_at, secure, http_only, same_site, kind, source, send_count, created_at FROM cookies WHERE domain=? AND proxy_key=? ORDER BY kind, name",
                (domain, proxy_key),
            ).fetchall()
            return [
                {
                    "name": r[0], "value": r[1], "path": r[2],
                    "expires_at": r[3], "secure": bool(r[4]),
                    "http_only": bool(r[5]), "same_site": r[6],
                    "kind": r[7], "source": r[8],
                    "send_count": r[9] or 0, "created_at": r[10],
                }
                for r in rows
            ]

    def put_cookie(self, domain, proxy_key, data):
        with self._lock:
            c = self._connect()
            c.execute(
                "INSERT OR REPLACE INTO cookies (domain, proxy_key, name, value, path, expires_at, secure, http_only, same_site, kind, source, created_at, last_sent_at, send_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    domain, proxy_key, data["name"], data["value"],
                    data.get("path", "/"), data.get("expires_at"),
                    1 if data.get("secure") else 0,
                    1 if data.get("http_only") else 0,
                    data.get("same_site"),
                    data.get("kind", "seed"),
                    data.get("source"),
                    time.time(), data.get("last_sent_at"),
                    int(data.get("send_count", 0)),
                ),
            )
            c.commit()

    def delete_cookie(self, domain, proxy_key, name, path="/"):
        with self._lock:
            c = self._connect()
            c.execute("DELETE FROM cookies WHERE domain=? AND proxy_key=? AND name=? AND path=?", (domain, proxy_key, name, path))
            c.commit()

    def clear_domain(self, domain):
        with self._lock:
            c = self._connect()
            c.execute("DELETE FROM cookies WHERE domain=?", (domain,))
            c.execute("DELETE FROM identities WHERE domain=?", (domain,))
            c.execute("DELETE FROM seed_stats WHERE domain=?", (domain,))
            c.execute("DELETE FROM cooldowns WHERE domain=?", (domain,))
            c.commit()

    def log_seed(self, domain, template, outcome, latency_ms=None):
        with self._lock:
            c = self._connect()
            c.execute("INSERT INTO seed_stats (domain, template, seeded_at, outcome, latency_ms) VALUES (?,?,?,?,?)", (domain, template, time.time(), outcome, latency_ms))
            c.commit()

    def log_harvest(self, domain, proxy_key, name, kind, source, status):
        with self._lock:
            c = self._connect()
            c.execute("INSERT INTO harvest_log (ts, domain, proxy_key, name, kind, source, status) VALUES (?,?,?,?,?,?,?)", (time.time(), domain, proxy_key, name, kind, source, status))
            c.commit()

    def cooldown_active(self, domain, strategy):
        with self._lock:
            c = self._connect()
            row = c.execute("SELECT until_ts FROM cooldowns WHERE domain=? AND strategy=?", (domain, strategy)).fetchone()
            if row is None:
                return False
            if row[0] < time.time():
                c.execute("DELETE FROM cooldowns WHERE domain=? AND strategy=?", (domain, strategy))
                c.commit()
                return False
            return True

    def set_cooldown(self, domain, strategy, seconds, reason=""):
        with self._lock:
            c = self._connect()
            c.execute("INSERT OR REPLACE INTO cooldowns (domain, strategy, until_ts, reason) VALUES (?,?,?,?)", (domain, strategy, time.time() + seconds, reason))
            c.commit()

    def domain_summary(self, domain):
        with self._lock:
            c = self._connect()
            total = c.execute("SELECT COUNT(*) FROM cookies WHERE domain=?", (domain,)).fetchone()[0]
            kinds = dict(c.execute("SELECT kind, COUNT(*) FROM cookies WHERE domain=? GROUP BY kind", (domain,)).fetchall())
            cd = dict(c.execute("SELECT strategy, until_ts FROM cooldowns WHERE domain=?", (domain,)).fetchall())
            return {"total": total, "kinds": kinds, "cooldowns": cd}

    def global_stats(self):
        with self._lock:
            c = self._connect()
            idents = c.execute("SELECT COUNT(*) FROM identities").fetchone()[0]
            cookies = c.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
            kinds = dict(c.execute("SELECT kind, COUNT(*) FROM cookies GROUP BY kind").fetchall())
            cd = c.execute("SELECT COUNT(*) FROM cooldowns WHERE until_ts > ?", (time.time(),)).fetchone()[0]
            top = c.execute("SELECT domain, COUNT(*) c FROM cookies GROUP BY domain ORDER BY c DESC LIMIT 10").fetchall()
            return {"identities": idents, "cookies": cookies, "kinds": kinds, "cooldowns": cd, "top": top}
