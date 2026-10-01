"""Cooldown + throttle + drift detection."""
from __future__ import annotations

import time as _time


class Learning:
    def __init__(self, store):
        self.store = store
        self._throttle = {}
        self._streaks = {}
        self._drift_window = 3600
        self._drift_threshold = 3

    def cooldown_active(self, domain, strategy):
        return self.store.cooldown_active(domain, strategy)

    def note_outcome(self, domain, strategy, outcome, default_hours=24):
        if outcome in ("cf", "captcha", "blocked"):
            self.store.set_cooldown(domain, strategy, default_hours * 3600, outcome)
            return True
        return False

    def note_success(self, domain, strategy):
        try:
            c = self.store._connect()
            with self.store._lock:
                c.execute("DELETE FROM cooldowns WHERE domain=? AND strategy=?", (domain, strategy))
                c.commit()
        except Exception:
            pass
        self.mark_success(domain)

    def throttle_ok(self, domain, min_interval_sec):
        if min_interval_sec <= 0:
            return True
        now = _time.time()
        last = self._throttle.get(domain, 0.0)
        if now - last < min_interval_sec:
            return False
        self._throttle[domain] = now
        return True

    def mark_visit(self, domain):
        self._throttle[domain] = _time.time()

    def mark_success(self, domain):
        s = self._streaks.get(domain)
        if s is None:
            s = {"ok": 0, "fail": 0, "first_fail_ts": None}
        s["ok"] += 1
        s["fail"] = 0
        s["first_fail_ts"] = None
        self._streaks[domain] = s

    def mark_fail(self, domain):
        now = _time.time()
        s = self._streaks.get(domain)
        if s is None:
            s = {"ok": 0, "fail": 0, "first_fail_ts": now}
        elif s.get("first_fail_ts") and now - s["first_fail_ts"] > self._drift_window:
            s = {"ok": 0, "fail": 0, "first_fail_ts": now}
        s["fail"] += 1
        self._streaks[domain] = s
        return s["fail"]

    def should_drift(self, domain):
        s = self._streaks.get(domain)
        if not s:
            return False
        return s.get("fail", 0) >= self._drift_threshold

    def clear_drift(self, domain):
        self._streaks.pop(domain, None)

    def clear(self, domain, strategy):
        self.store.set_cooldown(domain, strategy, 0, "cleared")
