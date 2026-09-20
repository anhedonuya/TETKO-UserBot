"""Trusted — доверенные пользователи TETKO.

"""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone

from core.tetko import Module, command, watcher, loop
from core_inline.lib.manager import InlineManager


ACCESS_CATEGORIES = {
    "modules": {
        "label": "Модули",
        "desc": "выгрузка, очистка и управление установленными модулями",
        "commands": [],
        "is_module_cmds": True,
    },
    "loader": {
        "label": "Загрузчик модулей",
        "desc": "установка внешних модулей из файлов, ссылок и пресетов",
        "commands": ["iload", "dlm", "um", "reload", "addrepo", "delrepo"],
    },
    "config": {
        "label": "Конфиг",
        "desc": "настройки юзербота и базовые параметры",
        "commands": [
            "cfg", "config", "fcfg", "fconfig", "setprefix",
            "addalias", "delalias", "setlang", "cleardb", "clearmodules",
            "clearcache", "api_protection", "piped", "api_reset",
            "api_suspend", "unla", "iloadalias", "logs",
        ],
    },
    "backup": {
        "label": "Бэкапы",
        "desc": "резервные копии базы и модулей",
        "commands": ["backup", "restore", "restore_with"],
    },
    "terminal": {
        "label": "Терминал",
        "desc": "системные shell-команды на сервере",
        "commands": ["t", "tkill", "write"],
    },
    "eval": {
        "label": "Код / Eval",
        "desc": "eval и выполнение кода",
        "commands": ["py", "js", "rb", "go", "rs"],
    },
    "security": {
        "label": "Безопасность",
        "desc": "owner, security, targeted rules и доступы",
        "commands": [
            "trust", "untrust", "trustlist", "trustcmd",
            "inlinesec", "inlineforall", "sgroup", "watcher",
            "timedtrusted", "nonickuser", "nonickusers",
            "trustaccess", "teaser",
        ],
    },
    "system": {
        "label": "Система",
        "desc": "update, restart и системное обслуживание",
        "commands": ["restart", "update", "stop", "rollback"],
    },
    "inline": {
        "label": "Inline",
        "desc": "использовать инлайн-команды и бота",
        "commands": [],
    },
    "callback": {
        "label": "Callback",
        "desc": "нажимать на callback-кнопки",
        "commands": [],
    },
    "aliases": {
        "label": "Алиасы",
        "desc": "использовать алиасы и сокращения команд",
        "commands": [],
    },
}

# Flat map: command → category
_CMD_TO_CAT: dict = {}
for _cat_key, _cat_info in ACCESS_CATEGORIES.items():
    for _cmd in _cat_info.get("commands", []):
        _CMD_TO_CAT[_cmd] = _cat_key

_CATEGORY_ROWS = [
    ("modules", "loader"),
    ("config", "backup"),
    ("terminal", "eval"),
    ("security", "system"),
    ("inline", "callback"),
    ("aliases",),
]

PRESETS = {
    "user": {
        "label": "👤 Пользователь",
        "access": {k: (k == "modules") for k in ACCESS_CATEGORIES},
    },
    "programmer": {
        "label": "💻 Программист",
        "access": {k: (k in ("modules", "eval", "terminal")) for k in ACCESS_CATEGORIES},
    },
    "moderator": {
        "label": "🛡 Модератор",
        "access": {k: (k in ("modules", "loader", "config")) for k in ACCESS_CATEGORIES},
    },
}


class _ModuleDB:
    def __init__(self, module):
        self._module = module
        self._ns = getattr(module, "name", "unnamed")

    async def get(self, key, default=None):
        from core.tetko import db as _db
        return _db.db_get(self._ns, key, default)

    async def set(self, key, value):
        from core.tetko import db as _db
        _db.db_set(self._ns, key, value)

    async def db_get(self, namespace, key, default=None):
        from core.tetko import db as _db
        return _db.db_get(namespace, key, default)

    async def db_set(self, namespace, key, value):
        from core.tetko import db as _db
        _db.db_set(namespace, key, value)

    async def db_delete(self, namespace, key):
        from core.tetko import db as _db
        _db.db_set(namespace, key, None)

    async def delete(self, key):
        from core.tetko import db as _db
        _db.db_set(self._ns, key, None)


class Trusted(Module):
    """Доверенные пользователи могут выполнять команды владельца."""

    name = "trusted"
    version = "1.4.0-beta-tetko"
    author = "@flexownerAL, @anhedonuya"
    __compat__ = "0.0.9.0"
    description = "Доверенные пользователи могут выполнять команды владельца"

    _STRINGS = {
        "ru": {
            "not_owner": "🚫 <b>Только для владельца.</b>",
            "usage": "Использование: <code>.trust &lt;reply/id/username&gt;</code>",
            "trust_already": "✅ Пользователь уже в списке доверенных.",
            "trust_added": "✅ Пользователь добавлен в доверенные.",
            "trust_added_timed": "✅ Пользователь добавлен в доверенные на {time}.",
            "trust_removed": "🗑 Пользователь удалён из доверенных.",
            "trust_not_in_list": "❌ Пользователь не в списке доверенных.",
            "trust_expired": "⏰ Время доверия истекло у {user}.",
            "trustlist_empty": "📭 Список доверенных пуст.",
            "trustlist_title": "👥 <b>Доверенные пользователи:</b>",
            "trust_time_title": "⏱ <b>На какой срок добавить?</b>",
            "trust_time_desc": "Выбери кнопкой ниже.",
            "btn_1h": "1 час",
            "btn_24h": "24 часа",
            "btn_7d": "7 дней",
            "btn_permanent": "Навсегда",
            "btn_cancel": "Отмена",
            "nonick_step_title": "🔑 <b>Добавить в NoNick для {name}?</b>",
            "nonick_step_desc": "NoNick позволяет использовать короткие команды без @{alias}.",
            "nonick_step_desc_no_alias": "NoNick позволяет использовать короткие команды.",
            "btn_nonick_yes": "✅ Да",
            "btn_nonick_no": "❌ Нет",
            "nonick_usage": "Использование: <code>.nonickuser &lt;reply/id&gt;</code>",
            "nonick_toggled_on": "🔑 NoNick включён для {name}.",
            "nonick_toggled_off": "🔓 NoNick выключен для {name}.",
            "nonick_list_empty": "📭 Список NoNick пуст.",
            "nonick_list_title": "🔑 <b>NoNick:</b>",
            "timed_trusted_empty": "📭 Нет временных доверенных.",
            "timed_trusted_title": "⏱ <b>Временные доверенные:</b>",
            "trust_expiring": " — осталось {time}",
            "ownerprefix_usage": "Использование: <code>.ownerprefix [reply/id/username]</code>",
            "ownerprefix_one": "👤 <b>{user}</b> (<code>{user_id}</code>)\nПрефикс: <code>{prefix}</code> ({source})",
            "ownerprefix_list_title": "👑 <b>Префиксы owner'ов:</b>",
            "ownerprefix_list_item": "• {user} (<code>{user_id}</code>) — <code>{prefix}</code> ({source})",
            "ownerprefix_source_personal": "личный",
            "ownerprefix_source_fallback": "по умолчанию",
            "trustaccess_title": "🔐 <b>Доступы для {user}:</b>",
            "trustaccess_footer": "<i>Нажми на категорию, чтобы переключить.</i>",
            "trustaccess_usage": "Использование: <code>.trustaccess &lt;reply/id&gt;</code>",
            "access_allowed": "разрешено",
            "access_allowed_group": "разрешено через группу",
            "access_denied": "запрещено",
            "btn_allow_all": "✅ Разрешить всё",
            "btn_deny_all": "🚫 Запретить всё",
            "btn_close": "🗑 Закрыть",
            "btn_cmds": "📋 Команды",
            "btn_inline_cmds": "🔮 Inline-команды",
            "percmd_title": "📋 <b>Команды для {user}:</b>",
            "percmd_back": "← Назад",
            "trustcmd_usage": "Использование: <code>.trustcmd &lt;reply/id&gt; &lt;+/-/list&gt; [команда]</code>",
            "trustcmd_added": "✅ {cmd} разрешён для {user}.",
            "trustcmd_removed": "🚫 {cmd} запрещён для {user}.",
            "trustcmd_not_found": "❌ Команда {cmd} не найдена.",
            "trustcmd_list_empty": "📭 Персональные доступы пусты.",
            "trustcmd_list_title": "📋 <b>Команды для {user}:</b>",
            "inlinecmd_title": "🔮 <b>Inline-команды для {user}:</b>",
            "inlinecmd_empty": "📭 Нет inline-команд.",
            "inlinesec_usage": "Использование: <code>.inlinesec &lt;reply/id&gt; [команда]</code>",
            "inlinesec_not_found": "❌ Inline-команда {cmd} не найдена.",
            "inlinesec_allowed": "✅ Inline-команда {cmd} разрешена для {user}.",
            "inlinesec_denied": "🚫 Inline-команда {cmd} запрещена для {user}.",
            "sgroup_usage": "Использование: <code>.sgroup create/delete/add/remove/access/list/info &lt;имя&gt;</code>",
            "sgroup_already_exists": "❌ Группа {name} уже существует.",
            "sgroup_created": "✅ Группа {name} создана.",
            "sgroup_deleted": "🗑 Группа {name} удалена.",
            "sgroup_not_found": "❌ Группа {name} не найдена.",
            "sgroup_user_in_group": "⚠️ Пользователь уже в группе.",
            "sgroup_user_not_in_group": "⚠️ Пользователя нет в группе.",
            "sgroup_user_added": "✅ {user} добавлен в {group}.",
            "sgroup_user_removed": "🗑 {user} удалён из {group}.",
            "sgroup_list_empty": "📭 Нет групп доступа.",
            "sgroup_list_title": "👥 <b>Группы доступа:</b>",
            "sgroup_menu_title": "👥 <b>Группа {name}</b>",
            "sgroup_info_users_empty": "пусто",
            "sgroup_info_access_empty": "нет доступов",
            "sgroup_btn_add_user": "➕ Добавить",
            "sgroup_btn_remove_user": "➖ Удалить",
            "sgroup_btn_delete": "🗑 Удалить группу",
            "sgroup_btn_access": "🔐 Доступы",
            "sgroup_confirm_delete": "🗑 Удалить группу {name}?",
            "btn_confirm_delete": "✅ Удалить",
            "watchers_title": "👁 <b>Watcher'ы:</b>",
            "watchers_empty": "📭 Нет watcher'ов.",
            "watchers_debug_title": "👁 <b>Watcher debug:</b>",
            "watchers_debug_empty": "📭 Ничего не найдено.",
            "watcher_usage": "Использование: <code>.watcher &lt;module&gt; &lt;method&gt;</code>",
            "watcher_not_found": "❌ Watcher {module}.{watcher} не найден.",
            "watcher_enabled": "✅ Watcher {module}.{watcher} включён.",
            "watcher_disabled": "🚫 Watcher {module}.{watcher} выключен.",
            "error": "❌ <b>Ошибка:</b> {error}\n<code>{full_error}</code>",
            "groups": "группы",
            "pm": "ЛС",
            "all": "всюду",
            "aliases": "алиасы",
        },
    }

    @property
    def strings(self):
        """Активный словарь переводов (по языку из config)."""
        data = getattr(type(self), "_STRINGS", {}) or {}
        lang = "ru"
        try:
            lang = (self.kernel.config or {}).get("language", "ru") or "ru"
        except Exception:
            pass
        return data.get(lang) or data.get("ru") or data.get("en") or {}

    def _mk_btn(self, label, fn, *args, ttl=600, style="primary"):
        async def wrapped(cb):
            return await fn(cb, *args)
        token = self.kernel.inline.register_handler(wrapped, ttl=ttl)
        return {"label": label, "token": token, "style": style}

    @property
    def db(self):
        if not hasattr(self, "_db_proxy"):
            self._db_proxy = _ModuleDB(self)
        return self._db_proxy

    async def _get_trusted_list(self) -> list:
        data = await self.db.db_get(self.name, "users")
        if not data:
            return []
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return []

    async def _save_trusted_list(self, users: list):
        await self.db.db_set(self.name, "users", json.dumps(users))

    async def _get_nonick_list(self) -> list:
        data = await self.db.db_get(self.name, "nonick")
        if not data:
            return []
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return []

    async def _save_nonick_list(self, users: list):
        await self.db.db_set(self.name, "nonick", json.dumps(users))

    async def _get_expired_trusted(self) -> dict:
        data = await self.db.db_get(self.name, "expired")
        if not data:
            return {}
        try:
            return json.loads(data) if isinstance(data, str) else json.loads(str(data))
        except Exception:
            return {}

    async def _save_expired_trusted(self, expired: dict):
        await self.db.db_set(self.name, "expired", json.dumps(expired))

    async def _get_sgroups(self) -> dict:
        data = await self.db.db_get(self.name, "sgroups")
        if not data:
            return {}
        try:
            parsed = json.loads(data) if isinstance(data, str) else json.loads(str(data))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    async def _save_sgroups(self, groups: dict):
        await self.db.db_set(self.name, "sgroups", json.dumps(groups))

    async def _is_sgroup_member(self, user_id: int) -> bool:
        groups = await self._get_sgroups()
        for gdata in groups.values():
            if user_id in gdata.get("users", []):
                return True
        return False

    async def _get_access(self, user_id: int) -> dict:
        data = await self.db.db_get(self.name + "_access", str(user_id))
        _defaults = dict.fromkeys(ACCESS_CATEGORIES, False)
        _defaults["aliases"] = True
        if not data:
            return _defaults
        try:
            stored = json.loads(data) if isinstance(data, str) else json.loads(str(data))
            if not isinstance(stored, dict):
                return _defaults
            return {cat: stored.get(cat, cat == "aliases") for cat in ACCESS_CATEGORIES}
        except Exception:
            return _defaults

    async def _save_access(self, user_id: int, access: dict):
        await self.db.db_set(self.name + "_access", str(user_id), json.dumps(access))

    async def _get_cmd_access(self, user_id: int) -> dict:
        data = await self.db.db_get(self.name + "_cmd_access", str(user_id))
        if not data:
            return {}
        try:
            parsed = json.loads(data) if isinstance(data, str) else json.loads(str(data))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    async def _save_cmd_access(self, user_id: int, cmd_access: dict):
        await self.db.db_set(self.name + "_cmd_access", str(user_id), json.dumps(cmd_access))

    def _get_all_commands(self) -> list:
        reg = getattr(self.kernel, "registry", None)
        if reg is None:
            return []
        try:
            return list(reg._commands.keys())
        except Exception:
            return []

    async def _get_user_display(self, user_id: int) -> str:
        try:
            user = await self.client.get_entity(user_id)
            if getattr(user, "username", None):
                return f"@{user.username}"
            return getattr(user, "first_name", None) or str(user_id)
        except Exception:
            return str(user_id)

    async def _get_user_id(self, event) -> int | None:
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply:
                return reply.sender_id
        args = event.raw_text.split(maxsplit=1)
        if len(args) > 1:
            target = args[1].strip().split()[0]
            if target.lstrip("-").isdigit():
                return int(target)
            username = target.lstrip("@")
            try:
                entity = await self.client.get_entity(username)
                return entity.id
            except Exception:
                pass
        return None

    def _get_command_category(self, cmd: str) -> str:
        result = _CMD_TO_CAT.get(cmd)
        if result:
            return result
        reg = getattr(self.kernel, "registry", None)
        if reg is not None:
            try:
                if cmd in reg._commands:
                    return "modules"
            except Exception:
                pass
        return "unknown"

    def _get_cmd_default_access(self, cmd: str, access: dict) -> bool:
        category = self._get_command_category(cmd)
        return access.get(category, False)

    async def _get_owner_username(self):
        try:
            me = await self.client.get_me()
            return me.username
        except Exception:
            return None

    @command(name="trust", aliases=["addowner"], description="Добавить в доверенные")
    async def cmd_trust(self, event, args):
        if event.sender_id != self.kernel.context.admin_id:
            await event.edit(self.strings["not_owner"], parse_mode="html")
            return

        user_id = await self._get_user_id(event)
        if not user_id:
            await event.edit(self.strings["usage"], parse_mode="html")
            return

        trusted = await self._get_trusted_list()
        if user_id in trusted:
            await event.edit(self.strings["trust_already"], parse_mode="html")
            return

        trusted.append(user_id)
        await self._save_trusted_list(trusted)

        # Дефолтные доступы
        default_access = {
            cat: (cat in ("modules", "inline", "callback"))
            for cat in ACCESS_CATEGORIES
        }
        await self._save_access(user_id, default_access)

        await event.edit(self.strings["trust_added"], parse_mode="html")

    @command(name="untrust", aliases=["delowner"], description="Удалить из доверенных")
    async def cmd_untrust(self, event, args):
        if event.sender_id != self.kernel.context.admin_id:
            await event.edit(self.strings["not_owner"], parse_mode="html")
            return

        user_id = await self._get_user_id(event)
        if not user_id:
            await event.edit(self.strings["usage"], parse_mode="html")
            return

        trusted = await self._get_trusted_list()
        if user_id not in trusted:
            await event.edit(self.strings["trust_not_in_list"], parse_mode="html")
            return

        trusted.remove(user_id)
        await self._save_trusted_list(trusted)

        nonick_list = await self._get_nonick_list()
        if user_id in nonick_list:
            nonick_list.remove(user_id)
            await self._save_nonick_list(nonick_list)

        await event.edit(self.strings["trust_removed"], parse_mode="html")

    @command(name="trustlist", aliases=["listowner"], description="Список доверенных")
    async def cmd_trustlist(self, event, args):
        trusted = await self._get_trusted_list()
        if not trusted:
            await event.edit(self.strings["trustlist_empty"], parse_mode="html")
            return

        nonick_list = await self._get_nonick_list()
        lines = [self.strings["trustlist_title"]]
        for uid in trusted:
            name = await self._get_user_display(uid)
            nn = " 🔑" if uid in nonick_list else ""
            lines.append(f"• {name} (<code>{uid}</code>){nn}")

        await event.edit("\n".join(lines), parse_mode="html")

    @command(name="nonickuser", description="Toggle NoNick для trusted")
    async def cmd_nonickuser(self, event, args):
        if event.sender_id != self.kernel.context.admin_id:
            await event.edit(self.strings["not_owner"], parse_mode="html")
            return

        user_id = await self._get_user_id(event)
        if not user_id:
            await event.edit(self.strings["nonick_usage"], parse_mode="html")
            return

        trusted = await self._get_trusted_list()
        if user_id not in trusted:
            await event.edit(self.strings["trust_not_in_list"], parse_mode="html")
            return

        nonick_list = await self._get_nonick_list()
        name = await self._get_user_display(user_id)

        if user_id in nonick_list:
            nonick_list.remove(user_id)
            await self._save_nonick_list(nonick_list)
            await event.edit(self.strings["nonick_toggled_off"].format(name=name), parse_mode="html")
        else:
            nonick_list.append(user_id)
            await self._save_nonick_list(nonick_list)
            await event.edit(self.strings["nonick_toggled_on"].format(name=name), parse_mode="html")

    @command(name="nonickusers", description="Список NoNick")
    async def cmd_nonickusers(self, event, args):
        nonick_list = await self._get_nonick_list()
        if not nonick_list:
            await event.edit(self.strings["nonick_list_empty"], parse_mode="html")
            return
        lines = [self.strings["nonick_list_title"]]
        for uid in nonick_list:
            name = await self._get_user_display(uid)
            lines.append(f"• {name} (<code>{uid}</code>)")
        await event.edit("\n".join(lines), parse_mode="html")

    @command(name="ownerprefix", description="Показать префикс owner'а")
    async def cmd_ownerprefix(self, event, args):
        parts = event.raw_text.split(maxsplit=1)
        has_target = event.is_reply or len(parts) > 1

        target_id = await self._get_user_id(event) if has_target else None
        owner_prefixes = getattr(self.kernel, "owner_prefixes", {}) or {}

        if has_target and target_id is None:
            await event.edit(self.strings["ownerprefix_usage"], parse_mode="html")
            return

        if target_id is not None:
            display_name = await self._get_user_display(target_id)
            try:
                active_prefix = self.kernel.get_prefix_for_sender(target_id)
            except Exception:
                active_prefix = getattr(self.kernel, "prefix", ".")
            personal = owner_prefixes.get(str(target_id))
            source = self.strings["ownerprefix_source_personal"] if personal is not None else self.strings["ownerprefix_source_fallback"]
            await event.edit(
                self.strings["ownerprefix_one"].format(
                    user=display_name, user_id=target_id,
                    prefix=active_prefix, source=source,
                ),
                parse_mode="html",
            )
            return

        trusted = await self._get_trusted_list()
        admin_id = self.kernel.context.admin_id
        owner_ids = [admin_id] + [uid for uid in trusted if uid != admin_id]

        lines = [self.strings["ownerprefix_list_title"]]
        for uid in owner_ids:
            display_name = await self._get_user_display(uid)
            try:
                active_prefix = self.kernel.get_prefix_for_sender(uid)
            except Exception:
                active_prefix = getattr(self.kernel, "prefix", ".")
            personal = owner_prefixes.get(str(uid))
            source = self.strings["ownerprefix_source_personal"] if personal is not None else self.strings["ownerprefix_source_fallback"]
            lines.append(self.strings["ownerprefix_list_item"].format(
                user=display_name, user_id=uid, prefix=active_prefix, source=source,
            ))
        await event.edit("\n".join(lines), parse_mode="html")

    @command(name="timedtrusted", description="Временные доверенные")
    async def cmd_timedtrusted(self, event, args):
        expired = await self._get_expired_trusted()
        if not expired:
            await event.edit(self.strings["timed_trusted_empty"], parse_mode="html")
            return

        current = int(time.time())
        lines = [self.strings["timed_trusted_title"]]
        for uid_str, expiry in expired.items():
            uid = int(uid_str)
            name = await self._get_user_display(uid)
            remaining = expiry - current
            if remaining > 0:
                if remaining >= 86400:
                    t = f"{remaining // 86400}д"
                elif remaining >= 3600:
                    t = f"{remaining // 3600}ч"
                else:
                    t = f"{remaining // 60}м"
                lines.append(f"• {name} (<code>{uid}</code>){self.strings['trust_expiring'].format(time=t)}")
        await event.edit("\n".join(lines), parse_mode="html")

    def _im(self):
        im = getattr(self, "_inline_manager", None)
        if im is None:
            im = InlineManager(self.kernel)
            self._inline_manager = im
        return im

    def _get_all_inline_commands(self) -> list:
        reg = getattr(self.kernel, "registry", None)
        if reg is None:
            return []
        handlers = getattr(reg, "inline_handlers", None)
        if isinstance(handlers, dict):
            return list(handlers.keys())
        return []

    def _access_text(self, user_display: str, access: dict, group_access: dict | None = None) -> str:
        lines = [self.strings["trustaccess_title"].format(user=user_display)]
        body = []
        for cat_key, cat_info in ACCESS_CATEGORIES.items():
            allowed = access.get(cat_key, False)
            group_allowed = False
            if group_access:
                for gdata in group_access.values():
                    if gdata.get("access", {}).get(cat_key, False):
                        group_allowed = True
                        break
            if allowed and not group_allowed:
                state = self.strings["access_allowed"]
            elif group_allowed and not allowed:
                state = self.strings["access_allowed_group"]
            elif allowed and group_allowed:
                state = self.strings["access_allowed"]
            else:
                state = self.strings["access_denied"]
            icon = "✅" if (allowed or group_allowed) else "🚫"
            body.append(f"{icon} {cat_info['label']} - <em>{state}</em>\n└ {cat_info['desc']}")
        lines.append("<blockquote expandable>" + "\n".join(body) + "</blockquote>")
        lines.append(self.strings["trustaccess_footer"])
        return "\n".join(lines)

    def _access_buttons(self, user_id: int, access: dict, group_access: dict | None = None,
                        input_chat=None) -> list:
        kernel = self.kernel
        TTL = 600

        async def on_toggle(cb_event, uid, cat_key):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            cur = await self._get_access(uid)
            cur[cat_key] = not cur.get(cat_key, False)
            await self._save_access(uid, cur)
            if cat_key == "inline":
                im = self._im()
                if cur[cat_key]:
                    await im.allow_user(uid)
                else:
                    await im.deny_user(uid)
            name = await self._get_user_display(uid)
            groups = await self._get_sgroups()
            g_access = {g: d for g, d in groups.items() if uid in d.get("users", [])}
            try:
                await cb_event.edit(
                    self._access_text(name, cur, g_access),
                    buttons=self._access_buttons(uid, cur, g_access, input_chat),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_preset(cb_event, uid, preset_key):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            preset = PRESETS[preset_key]
            await self._save_access(uid, dict(preset["access"]))
            im = self._im()
            if preset["access"].get("inline", False):
                await im.allow_user(uid)
            else:
                await im.deny_user(uid)
            name = await self._get_user_display(uid)
            groups = await self._get_sgroups()
            g_access = {g: d for g, d in groups.items() if uid in d.get("users", [])}
            try:
                await cb_event.edit(
                    self._access_text(name, preset["access"], g_access),
                    buttons=self._access_buttons(uid, preset["access"], g_access, input_chat),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_allow_all(cb_event, uid):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            full = dict.fromkeys(ACCESS_CATEGORIES, True)
            await self._save_access(uid, full)
            im = self._im()
            await im.allow_user(uid)
            name = await self._get_user_display(uid)
            try:
                await cb_event.edit(
                    self._access_text(name, full),
                    buttons=self._access_buttons(uid, full, input_chat=input_chat),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_deny_all(cb_event, uid):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            none_ = dict.fromkeys(ACCESS_CATEGORIES, False)
            await self._save_access(uid, none_)
            im = self._im()
            await im.deny_user(uid)
            name = await self._get_user_display(uid)
            try:
                await cb_event.edit(
                    self._access_text(name, none_),
                    buttons=self._access_buttons(uid, none_, input_chat=input_chat),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_close(cb_event, uid):
            try:
                await cb_event.delete()
            except Exception:
                pass

        async def on_cmds(cb_event, uid):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            access = await self._get_access(uid)
            cmd_access = await self._get_cmd_access(uid)
            name = await self._get_user_display(uid)
            text, rows = self._percmd_menu(uid, access, cmd_access, name)
            try:
                await self.kernel.inline.edit(cb_event, text, rows)
            except Exception:
                pass

        async def on_inline_cmds(cb_event, uid):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            name = await self._get_user_display(uid)
            text, rows = await self._inline_cmd_menu(uid, name)
            try:
                await self.kernel.inline.edit(cb_event, text, rows)
            except Exception:
                pass

        rows = []
        for row_cats in _CATEGORY_ROWS:
            row = []
            for cat_key in row_cats:
                cat_info = ACCESS_CATEGORIES[cat_key]
                allowed = access.get(cat_key, False)
                group_allowed = False
                if group_access:
                    for gdata in group_access.values():
                        if gdata.get("access", {}).get(cat_key, False):
                            group_allowed = True
                            break
                is_allowed = allowed or group_allowed
                icon = "✅" if is_allowed else "🚫"
                row.append(self._mk_btn(f"{icon} {cat_info['label']}", on_toggle, user_id, cat_key, ttl=TTL, style="success" if is_allowed else "danger",))
            rows.append(row)

        preset_row = []
        for pk, pi in PRESETS.items():
            preset_row.append(self._mk_btn(pi["label"], on_preset, user_id, pk, ttl=TTL, style="primary",))
        rows.append(preset_row)

        rows.append([
            self._mk_btn(self.strings["btn_cmds"], on_cmds, user_id, ttl=TTL, style="primary"),
            self._mk_btn(self.strings["btn_inline_cmds"], on_inline_cmds, user_id, ttl=TTL, style="primary"),
        ])
        rows.append([
            self._mk_btn(self.strings["btn_allow_all"], on_allow_all, user_id, ttl=TTL, style="success"),
            self._mk_btn(self.strings["btn_deny_all"], on_deny_all, user_id, ttl=TTL, style="danger"),
        ])
        rows.append([
            self._mk_btn(self.strings["btn_close"], on_close, user_id, ttl=TTL, style="primary"),
        ])
        return [[b for b in r if b is not None] for r in rows if r]

    def _percmd_menu(self, user_id: int, access: dict, cmd_access: dict, name: str, page: int = 0):
        ITEMS_PER_PAGE = 10
        kernel = self.kernel
        TTL = 600

        async def on_toggle_cmd(cb_event, uid, cmd, current_allowed, current_page):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            ca = await self._get_cmd_access(uid)
            ca[cmd] = not current_allowed
            await self._save_cmd_access(uid, ca)
            acc = await self._get_access(uid)
            nm = await self._get_user_display(uid)
            text, rows = self._percmd_menu(uid, acc, ca, nm, current_page)
            try:
                await self.kernel.inline.edit(cb_event, text, rows)
            except Exception:
                pass

        async def on_back(cb_event, uid):
            acc = await self._get_access(uid)
            nm = await self._get_user_display(uid)
            groups = await self._get_sgroups()
            g_access = {g: d for g, d in groups.items() if uid in d.get("users", [])}
            try:
                await cb_event.edit(
                    self._access_text(nm, acc, g_access),
                    buttons=self._access_buttons(uid, acc, g_access),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_prev(cb_event, uid, current_page):
            if current_page > 0:
                acc = await self._get_access(uid)
                ca = await self._get_cmd_access(uid)
                nm = await self._get_user_display(uid)
                text, rows = self._percmd_menu(uid, acc, ca, nm, current_page - 1)
                try:
                    await self.kernel.inline.edit(cb_event, text, rows)
                except Exception:
                    pass

        async def on_next(cb_event, uid, current_page):
            all_cmds = self._get_all_commands()
            total = (len(all_cmds) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            if current_page < total - 1:
                acc = await self._get_access(uid)
                ca = await self._get_cmd_access(uid)
                nm = await self._get_user_display(uid)
                text, rows = self._percmd_menu(uid, acc, ca, nm, current_page + 1)
                try:
                    await self.kernel.inline.edit(cb_event, text, rows)
                except Exception:
                    pass

        all_cmds = self._get_all_commands()
        total_pages = (len(all_cmds) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, len(all_cmds))
        page_cmds = all_cmds[start:end]

        lines = [self.strings["percmd_title"].format(user=name), "<blockquote>"]
        for cmd in page_cmds:
            if cmd in cmd_access:
                allowed = cmd_access[cmd]
            else:
                allowed = self._get_cmd_default_access(cmd, access)
            icon = "✅" if allowed else "🚫"
            state = self.strings["access_allowed"] if allowed else self.strings["access_denied"]
            lines.append(f"{icon} <code>{cmd}</code> - <em>{state}</em>")
        if total_pages > 1:
            lines.append(f"<em>{page + 1}/{total_pages}</em>")
        lines.append("</blockquote>")
        text = "\n".join(lines)

        rows = []
        for cmd in page_cmds:
            if cmd in cmd_access:
                allowed = cmd_access[cmd]
            else:
                allowed = self._get_cmd_default_access(cmd, access)
            icon = "✅" if allowed else "🚫"
            rows.append([self._mk_btn(f"{icon} {cmd}", on_toggle_cmd, user_id, cmd, allowed, page, ttl=TTL, style="success" if allowed else "danger")])

        nav = []
        if page > 0:
            nav.append(self._mk_btn("<", on_prev, user_id, page, ttl=TTL, style="primary"))
        if page < total_pages - 1:
            nav.append(self._mk_btn(">", on_next, user_id, page, ttl=TTL, style="primary"))
        if nav:
            rows.append(nav)
        rows.append([self._mk_btn(self.strings["percmd_back"], on_back, user_id, ttl=TTL, style="primary")])
        return text, rows

    async def _inline_cmd_menu(self, user_id: int, name: str, page: int = 0):
        ITEMS_PER_PAGE = 10
        kernel = self.kernel
        TTL = 600
        im = self._im()

        async def on_toggle(cb_event, uid, cmd, current_allowed, current_page):
            sender = cb_event.sender_id
            admin_id = self.kernel.context.admin_id
            is_admin = sender == admin_id
            is_sgroup = await self._is_sgroup_member(sender) if not is_admin else True
            if not is_admin and not is_sgroup:
                await cb_event.answer()
                return
            if current_allowed:
                await im.deny_user(uid, command=cmd)
            else:
                await im.allow_user(uid, command=cmd)
            nm = await self._get_user_display(uid)
            text, rows = await self._inline_cmd_menu(uid, nm, current_page)
            try:
                await self.kernel.inline.edit(cb_event, text, rows)
            except Exception:
                pass

        async def on_back(cb_event, uid):
            acc = await self._get_access(uid)
            nm = await self._get_user_display(uid)
            groups = await self._get_sgroups()
            g_access = {g: d for g, d in groups.items() if uid in d.get("users", [])}
            try:
                await cb_event.edit(
                    self._access_text(nm, acc, g_access),
                    buttons=self._access_buttons(uid, acc, g_access),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_prev(cb_event, uid, current_page):
            if current_page > 0:
                nm = await self._get_user_display(uid)
                text, rows = await self._inline_cmd_menu(uid, nm, current_page - 1)
                try:
                    await self.kernel.inline.edit(cb_event, text, rows)
                except Exception:
                    pass

        async def on_next(cb_event, uid, current_page):
            all_cmds = self._get_all_inline_commands()
            total = (len(all_cmds) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            if current_page < total - 1:
                nm = await self._get_user_display(uid)
                text, rows = await self._inline_cmd_menu(uid, nm, current_page + 1)
                try:
                    await self.kernel.inline.edit(cb_event, text, rows)
                except Exception:
                    pass

        all_cmds = self._get_all_inline_commands()
        total_pages = (len(all_cmds) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, len(all_cmds))
        page_cmds = all_cmds[start:end]

        lines = [self.strings["inlinecmd_title"].format(user=name), "<blockquote>"]
        if not page_cmds:
            lines.append(self.strings["inlinecmd_empty"])
        for cmd in page_cmds:
            allowed = await im.is_allowed(user_id, command=cmd)
            icon = "✅" if allowed else "🚫"
            state = self.strings["access_allowed"] if allowed else self.strings["access_denied"]
            lines.append(f"{icon} <code>{cmd}</code> - <em>{state}</em>")
        if total_pages > 1:
            lines.append(f"<em>{page + 1}/{total_pages}</em>")
        lines.append("</blockquote>")
        text = "\n".join(lines)

        rows = []
        for cmd in page_cmds:
            allowed = await im.is_allowed(user_id, command=cmd)
            icon = "✅" if allowed else "🚫"
            rows.append([self._mk_btn(f"{icon} {cmd}", on_toggle, user_id, cmd, allowed, page, ttl=TTL, style="success" if allowed else "danger")])
        nav = []
        if page > 0:
            nav.append(self._mk_btn("<", on_prev, user_id, page, ttl=TTL, style="primary"))
        if page < total_pages - 1:
            nav.append(self._mk_btn(">", on_next, user_id, page, ttl=TTL, style="primary"))
        if nav:
            rows.append(nav)
        rows.append([self._mk_btn(self.strings["percmd_back"], on_back, user_id, ttl=TTL, style="primary")])
        return text, rows

    @command(name="trustaccess", description="Управление доступами trusted")
    async def cmd_trustaccess(self, event, args):
        user_id = await self._get_user_id(event)
        if not user_id:
            await event.edit(self.strings["trustaccess_usage"], parse_mode="html")
            return
        trusted = await self._get_trusted_list()
        if user_id not in trusted:
            await event.edit(self.strings["trust_not_in_list"], parse_mode="html")
            return
        access = await self._get_access(user_id)
        name = await self._get_user_display(user_id)
        groups = await self._get_sgroups()
        g_access = {g: d for g, d in groups.items() if user_id in d.get("users", [])}
        _btns = self._access_buttons(user_id, access, g_access)
        _text = self._access_text(name, access, g_access)
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            await event.edit(_text, parse_mode="html")
            return
        try:
            await event.delete()
        except Exception:
            pass
        await bot.send_inline_menu(
            chat_id=event.chat_id,
            key=f"trustaccess_{user_id}_{int(time.time())}",
            text=_text,
            buttons=_btns,
        )

    @command(name="trustcmd", description="Персональные доступы к командам")
    async def cmd_trustcmd(self, event, args):
        parts = event.raw_text.split(maxsplit=2)
        if len(parts) < 2:
            await event.edit(self.strings["trustcmd_usage"], parse_mode="html")
            return
        user_id = await self._get_user_id(event)
        if not user_id:
            await event.edit(self.strings["trustcmd_usage"], parse_mode="html")
            return
        trusted = await self._get_trusted_list()
        if user_id not in trusted:
            await event.edit(self.strings["trust_not_in_list"], parse_mode="html")
            return
        all_cmds = self._get_all_commands()
        action = parts[1].lower() if len(parts) > 1 else ""
        if action == "list":
            ca = await self._get_cmd_access(user_id)
            name = await self._get_user_display(user_id)
            if not ca:
                await event.edit(self.strings["trustcmd_list_empty"], parse_mode="html")
                return
            lines = [self.strings["trustcmd_list_title"].format(user=name), "<blockquote>"]
            for cmd, allowed in ca.items():
                icon = "✅" if allowed else "🚫"
                state = self.strings["access_allowed"] if allowed else self.strings["access_denied"]
                lines.append(f"{icon} <code>{cmd}</code> - <em>{state}</em>")
            lines.append("</blockquote>")
            await event.edit("\n".join(lines), parse_mode="html")
            return
        if len(parts) < 3:
            await event.edit(self.strings["trustcmd_usage"], parse_mode="html")
            return
        raw = parts[2]
        cmd_name = raw.lstrip("+_-").lower()
        if cmd_name not in all_cmds:
            await event.edit(self.strings["trustcmd_not_found"].format(cmd=cmd_name), parse_mode="html")
            return
        ca = await self._get_cmd_access(user_id)
        name = await self._get_user_display(user_id)
        if raw.startswith("+"):
            ca[cmd_name] = True
            key = "trustcmd_added"
        elif raw.startswith("-"):
            ca[cmd_name] = False
            key = "trustcmd_removed"
        else:
            await event.edit(self.strings["trustcmd_usage"], parse_mode="html")
            return
        await self._save_cmd_access(user_id, ca)
        await event.edit(self.strings[key].format(cmd=cmd_name, user=name), parse_mode="html")

    @command(name="inlinesec", description="Доступы к inline-командам")
    async def cmd_inlinesec(self, event, args):
        user_id = await self._get_user_id(event)
        if not user_id:
            await event.edit(self.strings["inlinesec_usage"], parse_mode="html")
            return
        trusted = await self._get_trusted_list()
        if user_id not in trusted:
            await event.edit(self.strings["trust_not_in_list"], parse_mode="html")
            return
        im = self._im()
        parts = event.raw_text.split(maxsplit=2)
        inline_cmds = self._get_all_inline_commands()
        if len(parts) < 3:
            name = await self._get_user_display(user_id)
            lines = [self.strings["inlinecmd_title"].format(user=name), "<blockquote>"]
            if not inline_cmds:
                lines.append(f"<em>{self.strings['inlinecmd_empty']}</em>")
            for cmd in inline_cmds:
                allowed = await im.is_allowed(user_id, command=cmd)
                icon = "✅" if allowed else "🚫"
                lines.append(f"{icon} <code>{cmd}</code>")
            lines.append("</blockquote>")
            await event.edit("\n".join(lines), parse_mode="html")
            return
        cmd = parts[2].strip().lower()
        if cmd not in inline_cmds:
            await event.edit(self.strings["inlinesec_not_found"].format(cmd=cmd), parse_mode="html")
            return
        name = await self._get_user_display(user_id)
        currently = await im.is_allowed(user_id, command=cmd)
        if currently:
            await im.deny_user(user_id, command=cmd)
            await event.edit(self.strings["inlinesec_denied"].format(cmd=cmd, user=name), parse_mode="html")
        else:
            await im.allow_user(user_id, command=cmd)
            await event.edit(self.strings["inlinesec_allowed"].format(cmd=cmd, user=name), parse_mode="html")

    @command(name="inlineforall", aliases=["inlineall", "allinline"], description="Inline для всех")
    async def cmd_inlineforall(self, event, args):
        if event.sender_id != self.kernel.context.admin_id:
            await event.edit(self.strings["not_owner"], parse_mode="html")
            return
        im = self._im()
        parts = event.raw_text.split(maxsplit=1)
        if len(parts) < 2:
            mode = await im.get_everyone_mode()
            status = f"✅ <code>{mode}</code>" if mode else "🚫 <code>запрещено</code>"
            await event.edit(
                f"🌐 <b>Inline для всех:</b> {status}\n"
                f"Использование: <code>.inlineforall on/off</code>",
                parse_mode="html",
            )
            return
        action = parts[1].strip().lower()
        if action in ("on", "all", "yes"):
            await im.allow_everyone("all")
            await event.edit("✅ Inline разрешён для всех.", parse_mode="html")
        elif action in ("off", "no"):
            await im.deny_everyone()
            await event.edit("🚫 Inline запрещён для всех.", parse_mode="html")
        else:
            await event.edit("Использование: <code>.inlineforall on/off</code>", parse_mode="html")

    @command(name="sgroup", description="Группы доступа")
    async def cmd_sgroup(self, event, args):
        parts = event.raw_text.split(maxsplit=2)
        if len(parts) < 2:
            await event.edit(self.strings["sgroup_usage"], parse_mode="html")
            return
        action = parts[1].lower()
        groups = await self._get_sgroups()

        if action == "create":
            if len(parts) < 3:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            name = parts[2].strip()
            if name in groups:
                await event.edit(self.strings["sgroup_already_exists"].format(name=name), parse_mode="html")
                return
            groups[name] = {"users": [], "access": dict.fromkeys(ACCESS_CATEGORIES, False)}
            await self._save_sgroups(groups)
            await event.edit(self.strings["sgroup_created"].format(name=name), parse_mode="html")
            return

        if action == "delete":
            if len(parts) < 3:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            name = parts[2].strip()
            if name not in groups:
                await event.edit(self.strings["sgroup_not_found"].format(name=name), parse_mode="html")
                return
            del groups[name]
            await self._save_sgroups(groups)
            await event.edit(self.strings["sgroup_deleted"].format(name=name), parse_mode="html")
            return

        if action == "add":
            if len(parts) < 3:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            sub = parts[2].split(maxsplit=1)
            if len(sub) < 2:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            name = sub[0].strip()
            user_part = sub[1].strip()
            if user_part.lstrip("-").isdigit():
                user_id = int(user_part)
            else:
                try:
                    entity = await self.client.get_entity(user_part.lstrip("@"))
                    user_id = entity.id
                except Exception:
                    await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                    return
            if name not in groups:
                await event.edit(self.strings["sgroup_not_found"].format(name=name), parse_mode="html")
                return
            if user_id in groups[name]["users"]:
                await event.edit(self.strings["sgroup_user_in_group"], parse_mode="html")
                return
            groups[name]["users"].append(user_id)
            await self._save_sgroups(groups)
            user_name = await self._get_user_display(user_id)
            await event.edit(self.strings["sgroup_user_added"].format(user=user_name, group=name), parse_mode="html")
            return

        if action == "remove":
            if len(parts) < 3:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            sub = parts[2].split(maxsplit=1)
            if len(sub) < 2:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            name = sub[0].strip()
            user_part = sub[1].strip()
            if user_part.lstrip("-").isdigit():
                user_id = int(user_part)
            else:
                try:
                    entity = await self.client.get_entity(user_part.lstrip("@"))
                    user_id = entity.id
                except Exception:
                    await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                    return
            if name not in groups:
                await event.edit(self.strings["sgroup_not_found"].format(name=name), parse_mode="html")
                return
            if user_id not in groups[name]["users"]:
                await event.edit(self.strings["sgroup_user_not_in_group"], parse_mode="html")
                return
            groups[name]["users"].remove(user_id)
            await self._save_sgroups(groups)
            user_name = await self._get_user_display(user_id)
            await event.edit(self.strings["sgroup_user_removed"].format(user=user_name, group=name), parse_mode="html")
            return

        if action == "list":
            if not groups:
                await event.edit(self.strings["sgroup_list_empty"], parse_mode="html")
                return
            lines = [self.strings["sgroup_list_title"]]
            for gname, gdata in groups.items():
                uc = len(gdata.get("users", []))
                ac = sum(1 for v in gdata.get("access", {}).values() if v)
                lines.append(f"• <b>{gname}</b> - {uc} users, {ac} access")
            await event.edit("\n".join(lines), parse_mode="html")
            return

        if action == "access":
            if len(parts) < 3:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            name = parts[2].strip()
            if name not in groups:
                await event.edit(self.strings["sgroup_not_found"].format(name=name), parse_mode="html")
                return
            await self._show_sgroup_access(event, name)
            return

        if action == "info":
            if len(parts) < 3:
                await event.edit(self.strings["sgroup_usage"], parse_mode="html")
                return
            name = parts[2].strip()
            if name not in groups:
                await event.edit(self.strings["sgroup_not_found"].format(name=name), parse_mode="html")
                return
            await self._show_sgroup_info(event, name)
            return

        await event.edit(self.strings["sgroup_usage"], parse_mode="html")

    def _sgroup_access_text(self, group_name: str, access: dict) -> str:
        lines = [f"🔐 <b>Доступы для группы {group_name}:</b>"]
        body = []
        for cat_key, cat_info in ACCESS_CATEGORIES.items():
            allowed = access.get(cat_key, False)
            icon = "✅" if allowed else "🚫"
            state = self.strings["access_allowed"] if allowed else self.strings["access_denied"]
            body.append(f"{icon} {cat_info['label']} - <em>{state}</em>\n└ {cat_info['desc']}")
        lines.append("<blockquote expandable>" + "\n".join(body) + "</blockquote>")
        lines.append(self.strings["trustaccess_footer"])
        return "\n".join(lines)

    def _sgroup_access_buttons(self, group_name: str, access: dict) -> list:
        kernel = self.kernel
        TTL = 600

        async def on_toggle(cb_event, gname, cat_key, current):
            groups = await self._get_sgroups()
            if gname in groups:
                groups[gname]["access"][cat_key] = not current
                await self._save_sgroups(groups)
            acc = groups[gname]["access"]
            try:
                await cb_event.edit(
                    self._sgroup_access_text(gname, acc),
                    buttons=self._sgroup_access_buttons(gname, acc),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_allow_all(cb_event, gname):
            groups = await self._get_sgroups()
            if gname in groups:
                groups[gname]["access"] = dict.fromkeys(ACCESS_CATEGORIES, True)
                await self._save_sgroups(groups)
            acc = groups[gname]["access"]
            try:
                await cb_event.edit(
                    self._sgroup_access_text(gname, acc),
                    buttons=self._sgroup_access_buttons(gname, acc),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_deny_all(cb_event, gname):
            groups = await self._get_sgroups()
            if gname in groups:
                groups[gname]["access"] = dict.fromkeys(ACCESS_CATEGORIES, False)
                await self._save_sgroups(groups)
            acc = groups[gname]["access"]
            try:
                await cb_event.edit(
                    self._sgroup_access_text(gname, acc),
                    buttons=self._sgroup_access_buttons(gname, acc),
                    parse_mode="html",
                )
            except Exception:
                pass

        async def on_back(cb_event, gname):
            await self._show_sgroup_info(cb_event, gname)

        rows = []
        for row_cats in _CATEGORY_ROWS:
            row = []
            for cat_key in row_cats:
                cat_info = ACCESS_CATEGORIES[cat_key]
                allowed = access.get(cat_key, False)
                icon = "✅" if allowed else "🚫"
                row.append(self._mk_btn(f"{icon} {cat_info['label']}", on_toggle, group_name, cat_key, allowed, ttl=TTL, style="success" if allowed else "danger"))
            rows.append(row)
        rows.append([
            self._mk_btn(self.strings["btn_allow_all"], on_allow_all, group_name, ttl=TTL, style="success"),
            self._mk_btn(self.strings["btn_deny_all"], on_deny_all, group_name, ttl=TTL, style="danger"),
        ])
        rows.append([self._mk_btn(self.strings["percmd_back"], on_back, group_name, ttl=TTL, style="primary")])
        return [[b for b in r if b is not None] for r in rows if r]

    async def _show_sgroup_info(self, event, name: str):
        groups = await self._get_sgroups()
        if name not in groups:
            await event.edit(self.strings["sgroup_not_found"].format(name=name), parse_mode="html")
            return
        group = groups[name]
        lines = [self.strings["sgroup_menu_title"].format(name=name)]
        if group["users"]:
            lines.append("\n<b>Users:</b>")
            for uid in group["users"]:
                u_name = await self._get_user_display(uid)
                lines.append(f"• {u_name} (<code>{uid}</code>)")
        else:
            lines.append("\n<b>Users:</b> - " + self.strings["sgroup_info_users_empty"])
        access = group.get("access", {})
        access_on = [cat for cat, v in access.items() if v]
        if access_on:
            lines.append(f"\n<b>Access:</b> {', '.join(access_on)}")
        else:
            lines.append("\n<b>Access:</b> " + self.strings["sgroup_info_access_empty"])
        text = "\n".join(lines)
        kernel = self.kernel
        TTL = 600

        async def on_access(cb_event, gname):
            await self._show_sgroup_access(cb_event, gname)

        async def on_delete_group(cb_event, gname):
            async def on_confirm(cb_inner, g):
                groups2 = await self._get_sgroups()
                if g in groups2:
                    del groups2[g]
                    await self._save_sgroups(groups2)
                try:
                    await cb_inner.edit(self.strings["sgroup_deleted"].format(name=g), parse_mode="html")
                except Exception:
                    pass

            async def on_cancel(cb_inner, g):
                await self._show_sgroup_info(cb_inner, g)

            buttons = [[
                self._mk_btn(self.strings["btn_confirm_delete"], on_confirm, gname, ttl=TTL, style="danger"),
                self._mk_btn(self.strings["btn_cancel"], on_cancel, gname, ttl=TTL, style="primary"),
            ]]
            try:
                await self.kernel.inline.edit(cb_event, self.strings["sgroup_confirm_delete"].format(name=gname), buttons)
            except Exception:
                pass

        rows = [[
            self._mk_btn(self.strings["sgroup_btn_access"], on_access, name, ttl=TTL, style="primary"),
            self._mk_btn(self.strings["sgroup_btn_delete"], on_delete_group, name, ttl=TTL, style="danger"),
        ]]
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            try:
                await event.edit(text, parse_mode="html")
            except Exception:
                pass
            return
        try:
            await event.delete()
        except Exception:
            pass
        await bot.send_inline_menu(
            chat_id=event.chat_id,
            key=f"sgroup_info_{name}_{int(time.time())}",
            text=text,
            buttons=rows,
        )

    async def _show_sgroup_access(self, event, name: str):
        groups = await self._get_sgroups()
        if name not in groups:
            await event.edit(self.strings["sgroup_not_found"].format(name=name), parse_mode="html")
            return
        access = groups[name]["access"]
        try:
            await event.edit(
                self._sgroup_access_text(name, access),
                buttons=self._sgroup_access_buttons(name, access),
                parse_mode="html",
            )
        except Exception:
            pass

    @command(name="watcher", description="Вкл/выкл watcher")
    async def cmd_watcher(self, event, args):
        if event.sender_id != self.kernel.context.admin_id:
            await event.edit(self.strings["not_owner"], parse_mode="html")
            return
        parts = event.raw_text.split(maxsplit=2)
        if len(parts) < 3:
            await event.edit(self.strings["watcher_usage"], parse_mode="html")
            return
        module_name = parts[1]
        watcher_name = parts[2]
        reg = getattr(self.kernel, "register", None)
        if reg is None:
            return
        get_watchers = getattr(reg, "get_watchers", None)
        if get_watchers is None:
            return
        watchers = get_watchers()
        info = next((w for w in watchers if w["module"] == module_name and w["method"] == watcher_name), None)
        if info is None:
            await event.edit(self.strings["watcher_not_found"].format(module=module_name, watcher=watcher_name), parse_mode="html")
            return
        if info["enabled"]:
            ok = reg.disable_watcher(module_name, watcher_name)
            key = "watcher_disabled"
        else:
            ok = reg.enable_watcher(module_name, watcher_name)
            key = "watcher_enabled"
        if not ok:
            await event.edit(self.strings["watcher_not_found"].format(module=module_name, watcher=watcher_name), parse_mode="html")
            return
        await event.edit(self.strings[key].format(module=module_name, watcher=watcher_name), parse_mode="html")

    @command(name="watchers", description="Список watcher'ов")
    async def cmd_watchers(self, event, args):
        try:
            reg = getattr(self.kernel, "register", None)
            watchers = reg.get_watchers() if reg else []
            if not watchers:
                await event.edit(self.strings["watchers_empty"], parse_mode="html")
                return
            lines = [self.strings["watchers_title"] + "<blockquote expandable>"]
            for i, w in enumerate(watchers, 1):
                ev_obj = w.get("event")
                direction = ""
                if getattr(ev_obj, "incoming", False):
                    direction = " [in]"
                elif getattr(ev_obj, "out", False):
                    direction = " [out]"
                status = "on" if w["enabled"] else "off"
                lines.append(f"<code>{i}.</code> <b>{w['module']}.{w['method']}</b>{direction} - <i>{status}</i>")
            lines.append("</blockquote>")
            await event.edit("\n".join(lines), parse_mode="html")
        except Exception as e:
            await event.edit(self.strings["error"].format(error=e, full_error=""), parse_mode="html")

    @command(name="watchersdebug", description="Отладка watcher'ов")
    async def cmd_watchersdebug(self, event, args):
        try:
            parts = event.raw_text.split(maxsplit=1)
            filter_text = parts[1].lower() if len(parts) > 1 else ""
            reg = getattr(self.kernel, "register", None)
            watchers = reg.get_watchers() if reg else []
            lines = [self.strings["watchers_debug_title"] + "<blockquote expandable>"]
            matched = 0
            for w in watchers:
                full = f"{w['module']}.{w['method']}"
                if filter_text and filter_text not in full.lower():
                    continue
                direction = []
                if w["tags"].get("incoming"):
                    direction.append("incoming")
                if w["tags"].get("out"):
                    direction.append("out")
                if not direction:
                    direction.append("any")
                lines.append(f"<b>{full}</b> - <code>enabled={w['enabled']}</code> <code>dir={','.join(direction)}</code>")
                matched += 1
            if not matched:
                await event.edit(self.strings["watchers_debug_empty"], parse_mode="html")
                return
            lines.append("</blockquote>")
            await event.edit("\n".join(lines), parse_mode="html")
        except Exception as e:
            await event.edit(self.strings["error"].format(error=e, full_error=""), parse_mode="html")

    @watcher()
    async def trusted_watcher(self, event):
        msg = getattr(event, "message", event)
        if getattr(msg, "out", False):
            return
        text = getattr(msg, "raw_text", "") or ""
        sender_id = getattr(event, "sender_id", None)
        try:
            incoming_prefix = self.kernel.get_prefix_for_sender(sender_id)
            owner_prefix = self.kernel.get_prefix_for_sender(self.kernel.context.admin_id)
        except Exception:
            incoming_prefix = getattr(self.kernel, "prefix", ".")
            owner_prefix = incoming_prefix
        trusted = await self._get_trusted_list()
        is_owner = (sender_id == self.kernel.context.admin_id)
        if sender_id not in trusted and not is_owner:
            return
        if not text.startswith(incoming_prefix):
            return
        cmd_body = text[len(incoming_prefix):]
        parts = cmd_body.split()
        if not parts:
            return
        cmd_token = parts[0]
        rest = parts[1:]

        owner_uname = await self._get_owner_username()
        owner_alias = f"@{owner_uname}" if owner_uname else None

        has_alias = False
        actual_cmd = cmd_token

        if owner_alias and cmd_token.lower().endswith(owner_alias.lower()):
            stripped = cmd_token[:-len(owner_alias)]
            if stripped:
                actual_cmd = stripped
                has_alias = True

        nonick_list = await self._get_nonick_list()
        sender_has_nonick = sender_id in nonick_list

        if not has_alias and not sender_has_nonick:
            if sender_id != self.kernel.context.admin_id:
                return

        access = await self._get_access(sender_id)
        resolved_cmd = actual_cmd
        if access.get("aliases", True):
            reg = getattr(self.kernel, "registry", None)
            if reg is not None:
                try:
                    if resolved_cmd in reg._aliases:
                        resolved_cmd = reg._aliases[resolved_cmd]
                except Exception:
                    pass

        category = self._get_command_category(resolved_cmd)
        if category == "unknown":
            return

        cmd_access = await self._get_cmd_access(sender_id)
        user_has_access = False
        if resolved_cmd in cmd_access:
            if not cmd_access[resolved_cmd]:
                groups = await self._get_sgroups()
                for gdata in groups.values():
                    if sender_id in gdata.get("users", []):
                        if gdata.get("access", {}).get(category, False):
                            user_has_access = True
                            break
                if not user_has_access:
                    return
            else:
                user_has_access = True
        elif not access.get(category, False):
            groups = await self._get_sgroups()
            for gdata in groups.values():
                if sender_id in gdata.get("users", []):
                    if gdata.get("access", {}).get(category, False):
                        user_has_access = True
                        break
            if not user_has_access:
                return

        reg = getattr(self.kernel, "registry", None)
        if reg is None:
            return
        try:
            cmd = reg.find_command(resolved_cmd)
            if cmd is None:
                return
            cmd_args = " ".join(rest) if rest else []
            await cmd.func(event, cmd_args)
        except Exception as e:
            full = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            try:
                await event.edit(self.strings["error"].format(error=e, full_error=full))
            except Exception:
                pass

    @loop(interval=30, autostart=True)
    async def update_callback_permissions(self):
        trusted = await self._get_trusted_list()
        im = self._im()
        for uid in trusted:
            access = await self._get_access(uid)
            if access.get("inline", False) or access.get("callback", False):
                await im.allow_user(uid)
            else:
                await im.deny_user(uid)

    @loop(interval=60, autostart=True)
    async def check_expired_trusted(self):
        expired = await self._get_expired_trusted()
        if not expired:
            return
        current = int(time.time())
        trusted = await self._get_trusted_list()
        changed = False
        for uid_str, expiry in list(expired.items()):
            if current >= expiry:
                uid = int(uid_str)
                if uid in trusted:
                    trusted.remove(uid)
                    changed = True
                nonick_list = await self._get_nonick_list()
                if uid in nonick_list:
                    nonick_list.remove(uid)
                    await self._save_nonick_list(nonick_list)
                im = self._im()
                await im.deny_user(uid)
                del expired[uid_str]
                changed = True
                try:
                    name = await self._get_user_display(uid)
                except Exception:
                    name = str(uid)
                try:
                    await self.kernel.client.send_message(
                        getattr(self.kernel, "log_chat_id", None) or self.kernel.context.admin_id,
                        self.strings["trust_expired"].format(user=name),
                        parse_mode="html",
                    )
                except Exception:
                    pass
        if changed:
            await self._save_trusted_list(trusted)
            await self._save_expired_trusted(expired)

    async def on_load(self):
        trusted = await self._get_trusted_list()
        im = self._im()
        for uid in trusted:
            access = await self._get_access(uid)
            if access.get("inline", False):
                await im.allow_user(uid)
