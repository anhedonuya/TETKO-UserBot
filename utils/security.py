"""MCUB-совместимый utils.security (минимальная заглушка)."""
from __future__ import annotations


def get_db_path(*a, **kw):
    return "userbot.db"


def get_config_path(*a, **kw):
    return "config.json"


def get_session_path(*a, **kw):
    return "user_session.session"


def session_exists(*a, **kw):
    return False


def safe_extract_archive(*a, **kw):
    raise NotImplementedError("safe_extract_archive")


def safe_extract_zip(*a, **kw):
    raise NotImplementedError("safe_extract_zip")


def safe_extract_tar(*a, **kw):
    raise NotImplementedError("safe_extract_tar")


def get_sessions_dir(*a, **kw):
    return "sessions"


def get_logs_dir(*a, **kw):
    return "logs"


def get_data_dir(*a, **kw):
    return "data"
