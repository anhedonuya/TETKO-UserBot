import time


class Learning:
    def __init__(self, store):
        self.store = store
        self._throttle = {}
        self._streaks = {}
        self._drift_window = 3600
        self._drift_threshold = 3

    def cooldown_active(self, domain, strategy="fetch"):
        return self.store.cooldown_active(domain, strategy)

    def note_outcome(self, domain, strategy, outcome, default_hours=24):
        if outcome in ("cf", "captcha", "blocked"):
            self.store.set_cooldown(domain, strategy, default_hours * 3600, outcome)
            return True
        return False

    def note_success(self, domain, strategy="fetch"):
        self.store.clear_cooldown(domain, strategy)
        self.mark_success(domain)

    def throttle_ok(self, domain, min_interval_sec):
        if min_interval_sec <= 0:
            return True
        now = time.time()
        last = self._throttle.get(domain, 0.0)
        if now - last < min_interval_sec:
            return False
        self._throttle[domain] = now
        return True

    def mark_visit(self, domain):
        self._throttle[domain] = time.time()

    def mark_success(self, domain):
        self._streaks[domain] = {"ok": 1, "fail": 0, "first_fail_ts": None}

    def mark_fail(self, domain):
        now = time.time()
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
        return bool(s and s.get("fail", 0) >= self._drift_threshold)

    def clear_drift(self, domain):
        self._streaks.pop(domain, None)
