"""MCUB-совместимый класс Strings.

Использование:
    data = {"name": "mod", "en": {...}, "ru": {...}}
    strings = Strings(kernel, data)
    s = strings._active    # активный язык
    s["key"]               # перевод
    s["key"].format(x=1)   # с подстановкой
    strings("key")         # вызов
"""
from __future__ import annotations


class _StringDict(dict):
    """Обёртка над dict, чтобы можно было вызывать s["key"]("full_error", ...)."""

    def __init__(self, data: dict, fallback=None):
        super().__init__(data or {})
        self._fallback = fallback

    def __call__(self, key, **kwargs):
        return self.get(key, f"[{key}]")

    def __getitem__(self, key):
        val = self.get(key)
        if val is None:
            return _MissingString(key)
        if isinstance(val, str):
            return _CallableString(val)
        return val


class _CallableString(str):
    """str с поддержкой вызова: s["key"]("full_error", ...)"""

    def __call__(self, *args, **kwargs):
        return self


class _MissingString(str):
    def __new__(cls, key):
        return super().__new__(cls, f"[{key}]")

    def __call__(self, *args, **kwargs):
        return str(self)


class Strings:
    """MCUB-совместимый Strings.

    data: {"name": "...", "en": {...}, "ru": {...}, "uk": {...}}
    """

    def __init__(self, kernel=None, data: dict | None = None, *args, **kwargs):
        self.kernel = kernel
        self.data = data or {}

        lang = "ru"
        try:
            if kernel is not None:
                cfg = getattr(kernel, "config", None) or {}
                if isinstance(cfg, dict):
                    lang = cfg.get("language", "ru") or "ru"
        except Exception:
            pass
        self.language = lang

        active = self._pick_active(lang)
        self._active = _StringDict(active)

        # Для удобства: атрибуты через strings.KEY
        for k, v in active.items():
            if not hasattr(self, k):
                try:
                    setattr(self, k, v)
                except Exception:
                    pass

    def _pick_active(self, lang: str) -> dict:
        data = self.data or {}
        # 1. Точный язык
        if lang in data and isinstance(data[lang], dict):
            return dict(data[lang])
        # 2. Русский
        if "ru" in data and isinstance(data["ru"], dict):
            return dict(data["ru"])
        # 3. Английский
        if "en" in data and isinstance(data["en"], dict):
            return dict(data["en"])
        # 4. Первый попавшийся dict (кроме name)
        for k, v in data.items():
            if k != "name" and isinstance(v, dict):
                return dict(v)
        # 5. Если сам data — плоский словарь
        return {k: v for k, v in data.items() if k != "name"}

    def __call__(self, key, **kwargs):
        return self._active.get(key, f"[{key}]")

    def __getitem__(self, key):
        return self._active[key]

    def get(self, key, default=None):
        return self._active.get(key, default)

    def has(self, key):
        return key in self._active

    def keys(self):
        return set(self._active.keys())

    def switch_lang(self, lang: str):
        self.language = lang
        self._active = _StringDict(self._pick_active(lang))
        return self
