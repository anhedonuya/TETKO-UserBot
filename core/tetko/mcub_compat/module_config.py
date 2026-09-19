"""MCUB-совместимый ModuleConfig поверх tetko ModuleConfig.

Реализует MCUB-стиль:
    ConfigValue("key", default, validator=Integer())
    ModuleConfig(ConfigValue(...), ConfigValue(...), Group(...), Row())
    config.get("key") / config["key"] = value / config.to_dict() / from_dict()

Хранение — в data/tetko_config/<module_name>.json (как у tetko).
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Optional

log = logging.getLogger("TETKO.mcub_compat.module_config")


# ────────────────────────────────────────────────────────────────────
#  Валидаторы
# ────────────────────────────────────────────────────────────────────

class ValidationError(Exception):
    pass


class Validator:
    internal_id = "Validator"

    def __init__(self, default: Any = None):
        self.default = default

    def validate(self, value: Any) -> Any:
        return value

    def to_python(self, value: Any) -> Any:
        return self.validate(value)

    def to_storage(self, value: Any) -> Any:
        return value


class Boolean(Validator):
    internal_id = "Boolean"
    def validate(self, value):
        if isinstance(value, bool): return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes", "on"): return True
            if v in ("false", "0", "no", "off"): return False
        if isinstance(value, (int, float)): return bool(value)
        raise ValidationError(f"Expected boolean, got {type(value).__name__}")


class Integer(Validator):
    internal_id = "Integer"
    def __init__(self, default=None, min=None, max=None):
        super().__init__(default)
        self.min = min
        self.max = max
    def validate(self, value):
        if value is None: return None
        if isinstance(value, bool): raise ValidationError("Expected integer, got bool")
        try: v = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Expected integer, got {type(value).__name__}") from None
        if self.min is not None and v < self.min:
            raise ValidationError(f"Value must be >= {self.min}")
        if self.max is not None and v > self.max:
            raise ValidationError(f"Value must be <= {self.max}")
        return v


class Float(Validator):
    internal_id = "Float"
    def __init__(self, default=None, min=None, max=None):
        super().__init__(default)
        self.min = min
        self.max = max
    def validate(self, value):
        if value is None: return None
        if isinstance(value, bool): raise ValidationError("Expected float, got bool")
        try: v = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Expected float, got {type(value).__name__}") from None
        if self.min is not None and v < self.min:
            raise ValidationError(f"Value must be >= {self.min}")
        if self.max is not None and v > self.max:
            raise ValidationError(f"Value must be <= {self.max}")
        return v


class String(Validator):
    internal_id = "String"
    def __init__(self, default="", min_len=None, max_len=None, **kwargs):
        super().__init__(default)
        self.min_len = min_len
        self.max_len = max_len
    def validate(self, value):
        if value is None: return None
        v = str(value)
        if self.min_len is not None and len(v) < self.min_len:
            raise ValidationError(f"String length must be >= {self.min_len}")
        if self.max_len is not None and len(v) > self.max_len:
            raise ValidationError(f"String length must be <= {self.max_len}")
        return v


class Choice(Validator):
    internal_id = "Choice"
    def __init__(self, choices, default=None):
        super().__init__(default if default is not None else (choices[0] if choices else None))
        self.choices = list(choices or [])
    def validate(self, value):
        if value not in self.choices:
            raise ValidationError(f"Value must be one of: {', '.join(map(str, self.choices))}")
        return value


class List(Validator):
    internal_id = "List"
    def __init__(self, default=None, item_type=None):
        super().__init__(default if default is not None else [])
        self.item_type = item_type
    def validate(self, value):
        if not isinstance(value, list):
            raise ValidationError("Expected list")
        if self.item_type is not None:
            for item in value:
                if isinstance(self.item_type, type) and not isinstance(item, self.item_type):
                    raise ValidationError(f"List items must be {self.item_type.__name__}")
        return list(value)


class DictType(Validator):
    internal_id = "DictType"
    def __init__(self, default=None, key_type=None, value_type=None):
        super().__init__(default if default is not None else {})
        self.key_type = key_type
        self.value_type = value_type
    def validate(self, value):
        if not isinstance(value, dict):
            raise ValidationError("Expected dict")
        return dict(value)


class Secret(Validator):
    internal_id = "Secret"
    def __init__(self, default=None):
        super().__init__(default)
        self.secret = True
    def validate(self, value): return value


class Placeholders(String):
    internal_id = "Placeholders"
    def __init__(self, default="", *, placeholder_scope="any", **kwargs):
        super().__init__(default, **kwargs)
        self.supports_placeholders = True
        self.placeholder_scope = placeholder_scope


class RegExp(String):
    internal_id = "RegExp"
    def __init__(self, pattern, default="", **kwargs):
        super().__init__(default, **kwargs)
        self.pattern = pattern
    def validate(self, value):
        import re
        v = super().validate(value)
        if v is None: return None
        if not re.fullmatch(self.pattern, v):
            raise ValidationError(f"String must match: {self.pattern}")
        return v


class Link(String):
    internal_id = "Link"
    def validate(self, value):
        v = super().validate(value)
        if v is None: return None
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValidationError("Must be http:// or https:// URL")
        return v


class TelegramID(Integer):
    internal_id = "TelegramID"


class EntityLike(Validator):
    internal_id = "EntityLike"
    def validate(self, value): return value


class Emoji(String):
    internal_id = "Emoji"


class MultiChoice(Validator):
    internal_id = "MultiChoice"
    def __init__(self, choices, default=None):
        super().__init__(default if default is not None else [])
        self.choices = list(choices or [])
    def validate(self, value):
        if not isinstance(value, (list, tuple, set)):
            raise ValidationError("Expected list")
        for v in value:
            if v not in self.choices:
                raise ValidationError(f"Invalid choice: {v}")
        return list(value)


class Union(Validator):
    internal_id = "Union"
    def __init__(self, *validators, default=None):
        self.validators = validators
        super().__init__(default if default is not None else (validators[0].default if validators else None))
    def validate(self, value):
        errs = []
        for v in self.validators:
            try: return v.validate(value)
            except ValidationError as e: errs.append(str(e))
        raise ValidationError("; ".join(errs))


class Hidden(Validator):
    internal_id = "Hidden"
    def __init__(self, validator=None, default=None):
        self.validator = validator or String(default or "")
        super().__init__(self.validator.default if default is None else default)
        self.secret = True
    def validate(self, value): return self.validator.validate(value)


class NoneType(Validator):
    internal_id = "NoneType"
    def validate(self, value):
        if value is None: return None
        if isinstance(value, str) and value.strip().lower() in ("", "none", "null"):
            return None
        raise ValidationError("Expected None")


# ────────────────────────────────────────────────────────────────────
#  UI-элементы (простые маркеры, для этапа 3 — храним, но UI базовый)
# ────────────────────────────────────────────────────────────────────

class _UIItem:
    ui_only = True
    ui_type = "ui"
    def __init__(self, *, key=None, **kwargs):
        self.key = str(key).strip() if key else None
        self._kwargs = kwargs


class Row(_UIItem):
    ui_type = "row"


class Divider(_UIItem):
    ui_type = "divider"


class Group(_UIItem):
    ui_type = "group"
    def __init__(self, title, items, description="", *, button_text=None, key=None, **kw):
        super().__init__(key=key, **kw)
        self.title = title
        self.items = list(items or [])
        self.description = description
        self.button_text = button_text or title


class Answer(_UIItem):
    """UI-only: всплывающий ответ при нажатии."""
    ui_type = "answer"

    def __init__(self, button_text, text="", *, alert=True, key=None, **_kw):
        super().__init__(key=key, **_kw)
        self._button_text = button_text
        self._text = text
        self.alert = alert

    def get_button_text(self, owner=None):
        return str(self._button_text or "Info")

    @property
    def button_text(self):
        return self.get_button_text()

    def get_text(self, owner=None):
        return str(self._text or "")

    @property
    def text(self):
        return self.get_text()


class Status(_UIItem):
    """UI-only: read-only статус."""
    ui_type = "status"

    def __init__(self, title, value="", *, key=None, **_kw):
        super().__init__(key=key, **_kw)
        self._title = title
        self._value = value

    def get_button_text(self, owner=None):
        return str(self._title or "Status")

    @property
    def button_text(self):
        return self.get_button_text()

    def get_value(self, owner=None):
        return self._value


class Notice(_UIItem):
    """UI-only: popup с текстом."""
    ui_type = "notice"

    def __init__(self, text, *, alert=True, key=None, **_kw):
        super().__init__(key=key, **_kw)
        self._text = text
        self.alert = alert

    def get_text(self, owner=None):
        return str(self._text or "")

    @property
    def text(self):
        return self.get_text()


class Callback(_UIItem):
    """UI-only: одна callback-кнопка."""
    ui_type = "callback"

    def __init__(self, button_text, on_click=None, *, key=None, **_kw):
        super().__init__(key=key, **_kw)
        self._button_text = button_text
        self.on_click = on_click

    def get_button_text(self, owner=None):
        return str(self._button_text or "Action")

    @property
    def button_text(self):
        return self.get_button_text()

    async def trigger_on_click(self, owner, event):
        if self.on_click is None:
            return None
        import inspect
        result = self.on_click(owner, event)
        if inspect.isawaitable(result):
            await result


class Url(_UIItem):
    """UI-only: URL-кнопка."""
    ui_type = "url"

    def __init__(self, button_text, url, *, key=None, **_kw):
        super().__init__(key=key, **_kw)
        self._button_text = button_text
        self._url = url

    def get_button_text(self, owner=None):
        return str(self._button_text or "Link")

    @property
    def button_text(self):
        return self.get_button_text()

    def get_url(self, owner=None):
        return str(self._url or "")

    @property
    def url(self):
        return self.get_url()


class Divider(_UIItem):
    """UI-only: разделитель."""
    ui_type = "divider"

    def __init__(self, text="────────", *, key=None, **_kw):
        super().__init__(key=key, **_kw)
        self._text = text

    def get_button_text(self, owner=None):
        return str(self._text or "────────")

    @property
    def button_text(self):
        return self.get_button_text()


class Buttons(_UIItem):
    ui_type = "buttons"
    def __init__(self, title, buttons=None, description="", *, button_text=None, key=None, **kw):
        super().__init__(key=key, **kw)
        self.title = title
        self.buttons = buttons or []
        self.description = description
        self.button_text = button_text or title


# ────────────────────────────────────────────────────────────────────
#  ConfigValue + ModuleConfig
# ────────────────────────────────────────────────────────────────────

class ConfigValue:
    """Значение конфига в стиле MCUB."""

    def __init__(self, key: str, default: Any, description=None,
                 validator: Optional[Validator] = None, hidden: bool = False,
                 on_change=None, show_if=True):
        # совместимость: ConfigValue("key", default, Validator())
        if isinstance(description, Validator) and validator is None:
            validator = description
            description = None

        self.key = key
        self._default = default
        self._description = description
        self.validator = validator or Validator(default)
        self.hidden = hidden
        self.on_change = on_change
        self._value = _UNSET

    @property
    def default(self):
        return self._default() if callable(self._default) else self._default

    @property
    def description(self):
        if callable(self._description):
            try: return str(self._description())
            except Exception: return ""
        return str(self._description or "")

    def set_value(self, value):
        self._value = self.validator.validate(value)

    def get_value(self):
        if self._value is _UNSET:
            return self.default
        return self._value

    def to_storage(self):
        return self.validator.to_storage(self.get_value())

    def from_storage(self, stored):
        self._value = self.validator.to_python(stored)


_UNSET = object()


class ModuleConfig:
    """MCUB-совместимый ModuleConfig."""

    def __init__(self, *items, on_change=None, version=None, migrate=None,
                 custom_handler=None):
        self._values: dict[str, ConfigValue] = {}
        self._ui_items: dict[str, Any] = {}
        self._group_items: dict[str, list[str]] = {}
        self._items_order: list[str] = []
        self._owner = None
        self.on_change = on_change
        self.version = version
        self.migrate = migrate
        self.custom_handler = custom_handler

        for index, item in enumerate(items):
            self._register_item(item, index)

    def _register_item(self, item, index):
        if isinstance(item, ConfigValue):
            self._values[item.key] = item
            self._items_order.append(item.key)
            return
        if getattr(item, "ui_only", False):
            ui_type = getattr(item, "ui_type", "ui")
            raw_key = item.key or f"{ui_type}_{index}"
            key = raw_key
            self._ui_items[key] = item
            self._items_order.append(key)
            if ui_type == "group":
                group_order = []
                self._group_items[key] = group_order
                for ci, child in enumerate(getattr(item, "items", []) or []):
                    if isinstance(child, ConfigValue):
                        self._values[child.key] = child
                        group_order.append(child.key)
            return
        raise TypeError(f"ModuleConfig: неподдерживаемый элемент {type(item).__name__}")

    def bind_owner(self, owner):
        self._owner = owner
        return self

    # ── словарный интерфейс ──

    def __getitem__(self, key):
        if key not in self._values:
            raise KeyError(f"Unknown config key: {key}")
        return self._values[key].get_value()

    def __setitem__(self, key, value):
        if key not in self._values:
            raise KeyError(f"Unknown config key: {key}")
        cv = self._values[key]
        old = cv.get_value()
        cv.set_value(value)
        new = cv.get_value()
        if cv.on_change:
            try:
                r = cv.on_change(old, new)
                if inspect.isawaitable(r):
                    import asyncio
                    asyncio.ensure_future(r)
            except Exception as e:
                log.warning(f"on_change({key}): {e}")

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def set(self, key, value):
        self[key] = value

    def keys(self):
        return list(self._values.keys())

    def values(self):
        return [cv.get_value() for cv in self._values.values()]

    def items(self):
        return [(k, cv.get_value()) for k, cv in self._values.items()]

    def all(self) -> dict:
        return dict(self.items())

    def update(self, mapping):
        for k, v in mapping.items():
            try: self[k] = v
            except KeyError: pass

    def __contains__(self, key):
        return key in self._values

    def to_dict(self):
        data = {k: cv.to_storage() for k, cv in self._values.items()}
        data["__mcub_config__"] = True
        if self.version is not None:
            data["__mcub_config_version__"] = self.version
        return data

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        for k, cv in self._values.items():
            if k in data:
                try: cv.from_storage(data[k])
                except Exception as e:
                    log.warning(f"from_dict({k}): {e}")

    def ui_items(self):
        return [(k, self._values[k].get_value() if k in self._values else self._ui_items[k])
                for k in self._items_order
                if k in self._values or k in self._ui_items]

    @property
    def schema(self):
        out = []
        for k, cv in self._values.items():
            out.append({
                "key": k,
                "type": getattr(cv.validator, "internal_id", "Validator").lower(),
                "default": cv.default,
                "description": cv.description,
                "hidden": cv.hidden or getattr(cv.validator, "secret", False),
                "choices": getattr(cv.validator, "choices", None),
            })
        return out


__all__ = [
    "ValidationError",
    "Validator", "Boolean", "Integer", "Float", "String", "Choice", "List",
    "DictType", "Secret", "Placeholders", "RegExp", "Link", "TelegramID",
    "EntityLike", "Emoji", "MultiChoice", "Union", "Hidden", "NoneType",
    "ConfigValue", "ModuleConfig",
    "Row", "Divider", "Group", "Buttons",
]
