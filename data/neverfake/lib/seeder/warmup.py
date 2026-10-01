import time


class WarmupQueue:
    def __init__(self):
        self._pending = {}

    def should_warmup(self, domain, visit_count, target_url):
        if visit_count > 0:
            return False
        path = target_url.split("//", 1)[-1].split("/", 1)
        p = "/" + (path[1] if len(path) > 1 else "")
        if p in ("/", ""):
            return False
        if domain not in self._pending:
            self._pending[domain] = {"queued_at": time.time(), "target": target_url}
            return True
        return False

    def pop_warmup_url(self, domain):
        return "https://%s/" % domain
