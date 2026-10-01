import os
import time
from pathlib import Path

class PluginLogger:
    def __init__(self, name, base_dir="data/dontdothat_plugins_logs", level="INFO"):
        self.name = name
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / (name + ".log")
        self.level = level
        self._levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

    def _should(self, level):
        return self._levels.get(level, 20) >= self._levels.get(self.level, 20)

    def _write(self, level, msg):
        if not self._should(level):
            return
        line = "[%s] [%s] %s
" % (time.strftime("%Y-%m-%d %H:%M:%S"), level, str(msg))
        try:
            if self.path.exists() and self.path.stat().st_size > 1024 * 1024:
                try:
                    if self.path.with_suffix(".log.2").exists():
                        self.path.with_suffix(".log.2").unlink()
                    if self.path.with_suffix(".log.1").exists():
                        self.path.with_suffix(".log.1").rename(self.path.with_suffix(".log.2"))
                    self.path.rename(self.path.with_suffix(".log.1"))
                except Exception:
                    pass
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def debug(self, msg):
        self._write("DEBUG", msg)

    def info(self, msg):
        self._write("INFO", msg)

    def warning(self, msg):
        self._write("WARNING", msg)

    def error(self, msg):
        self._write("ERROR", msg)

    def read(self, limit=100):
        if not self.path.exists():
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return lines[-limit:]
        except Exception:
            return []
