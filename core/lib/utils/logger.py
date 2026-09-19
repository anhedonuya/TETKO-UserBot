class ErrorFormatter:
    @staticmethod
    def format_full_traceback(tb): return tb

def mask_sensitive_data(v): return v

class KernelLogger:
    def __init__(self, *a, **kw): pass

def setup_logging(*a, **kw): return None
def setup_telegram_logging(*a, **kw): return None
