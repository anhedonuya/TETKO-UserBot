class Cleaner:
    def __init__(self, store):
        self.store = store

    def run(self, days=30):
        n = 0
        try:
            n = self.store.cleanup_inactive(days)
        except Exception:
            pass
        return n

    def vacuum(self):
        try:
            with self.store._lock:
                c = self.store._connect()
                c.execute("VACUUM")
                c.commit()
        except Exception:
            pass
