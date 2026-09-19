class CommandConflictError(Exception):
    def __init__(self, *a, **kw): super().__init__(*a)

class CallInsecure(Exception): pass
class McubTelethonError(Exception): pass
