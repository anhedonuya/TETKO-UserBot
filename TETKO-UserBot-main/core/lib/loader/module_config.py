"""Заглушка ModuleConfig для mcub (реальная — в compat)."""
from __future__ import annotations


class ValidationError(Exception):
    pass


class Validator:
    def __init__(self, default=None): self.default = default
    def validate(self, value): return value


class Boolean(Validator): pass
class Integer(Validator): pass
class Float(Validator): pass
class String(Validator): pass
class Choice(Validator):
    def __init__(self, choices=None, default=None):
        super().__init__(default)
        self.choices = choices or []
class List(Validator): pass
class DictType(Validator): pass
class Secret(Validator): pass
class Placeholders(String): pass
class RegExp(String): pass
class Link(String): pass
class TelegramID(Integer): pass
class EntityLike(Validator): pass
class Emoji(String): pass
class MultiChoice(Validator):
    def __init__(self, choices=None, default=None):
        super().__init__(default)
        self.choices = choices or []
class Union(Validator): pass
class Hidden(Validator): pass
class NoneType(Validator): pass
class ConfigValue:
    def __init__(self, *a, **kw): pass
class ModuleConfig:
    def __init__(self, *a, **kw): pass
class Group:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Row:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Divider:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Url:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Callback:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Status:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Notice:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Answer:
    """UI-stub: принимает любые аргументы."""
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Buttons: pass
