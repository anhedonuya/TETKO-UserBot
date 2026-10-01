class Return:
    CONTINUE = "continue"
    MODIFY = "modify"
    BLOCK = "block"
    REPLACE = "replace"
    ERROR = "error"
    SKIP = "skip"
    CHAIN = "chain"

    def __init__(self, kind, value=None, reason=None):
        self.kind = kind
        self.value = value
        self.reason = reason

    @classmethod
    def cont(cls):
        return cls(cls.CONTINUE)

    @classmethod
    def modify(cls, value):
        return cls(cls.MODIFY, value=value)

    @classmethod
    def block(cls, reason=""):
        return cls(cls.BLOCK, reason=reason)

    @classmethod
    def replace(cls, value):
        return cls(cls.REPLACE, value=value)

    @classmethod
    def error(cls, reason=""):
        return cls(cls.ERROR, reason=reason)

    @classmethod
    def skip(cls):
        return cls(cls.SKIP)

    @classmethod
    def chain(cls, value=None):
        return cls(cls.CHAIN, value=value)

    def __repr__(self):
        return "Return(kind=%r, value=%r)" % (self.kind, self.value)
