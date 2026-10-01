ALLOWED_ACCESS = {"module", "kernel", "cfg", "fs", "db", "net"}

class Sandbox:
    def __init__(self, allowed_access):
        self.allowed = set(allowed_access or [])

    def check(self, access):
        return access in self.allowed

    def deny_reason(self, access):
        return "access %r not granted (allowed: %s)" % (access, sorted(self.allowed))
