import json
import time
import logging
import traceback

from core.tetko import Module, command, watcher, loop, db_get, db_set, shell, InlineManager

log = logging.getLogger("TETKO.module.Trusted")

ACCESS_CATEGORIES = {
    "modules":  {"label": "Модули",       "desc": "просмотр, выгрузка, управление модулями"},
    "loader":   {"label": "Загрузчик",    "desc": "установка внешних модулей из файлов и ссылок"},
    "config":   {"label": "Конфиг",       "desc": "настройки юзербота и модулей"},
    "backup":   {"label": "Бэкапы",       "desc": "резервные копии и восстановление"},
    "terminal": {"label": "Терминал",     "desc": "shell-команды на сервере"},
    "eval":     {"label": "Eval",         "desc": "выполнение произвольного кода"},
    "security": {"label": "Безопасность", "desc": "управление доступами и trust"},
    "system":   {"label": "Система",      "desc": "обновление, рестарт, обслуживание"},
    "inline":   {"label": "Inline",       "desc": "использование инлайн-бота"},
    "callback": {"label": "Callback",     "desc": "нажатие на inline-кнопки"},
    "aliases":  {"label": "Алиасы",       "desc": "использование алиасов и сокращений"},
}

BUILTIN_CMD_MAP = {
    "modules":  ["dlm", "dlm_check", "um", "unload", "unlm", "tekhide"],
    "loader":   ["load", "reload"],
    "config":   ["cfg", "fconfig", "ftekcfg", "tekcfg", "setprefix", "setlang", "addalias", "delalias"],
    "backup":   ["backup", "restore"],
    "terminal": ["t", "term", "sh"],
    "eval":     ["py", "eval"],
    "security": ["trust", "untrust", "trustlist", "trustaccess", "trustcmd", "sgroup",
                 "inlinesec", "inlineforall", "watcher", "watchers", "timedtrusted",
                 "nonickuser", "nonickusers", "ownerprefix"],
    "system":   ["update", "restart", "stop"],
}

CMD_TO_CAT = {}
for _cat, _cmds in BUILTIN_CMD_MAP.items():
    for _c in _cmds:
        CMD_TO_CAT[_c] = _cat

CATEGORY_ROWS = [
    ("aliases", "eval"),
    ("system", "modules"),
    ("inline", "backup"),
    ("callback", "terminal"),
    ("loader", "config"),
    ("security",),
]

PRESETS = {
    "user":       {"label": "👤 User",       "access": {"modules": True, "inline": True, "callback": True, "aliases": True}},
    "programmer": {"label": "💻 Programmer", "access": {"modules": True, "eval": True, "terminal": True, "loader": True, "inline": True, "callback": True, "aliases": True}},
    "moderator":  {"label": "🛡 Moderator",  "access": {"modules": True, "loader": True, "config": True, "security": True, "inline": True, "callback": True, "aliases": True}},
    "admin":      {"label": "👑 Admin",      "access": {k: True for k in ACCESS_CATEGORIES}},
}

T = "trusted"


class Trusted(Module):
    name = "Trusted"
    __compat__ = "0.0.9.0"
    version = "2.0.0"
    author = "@flexownerAL"
    description = "Управление доверенными пользователями и доступами"

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self._inline_manager = None

    def _im(self):
        if self._inline_manager is None:
            self._inline_manager = InlineManager(self.kernel)
        return self._inline_manager

    def _is_owner(self, uid):
        try:
            return int(uid) == int(self.kernel.context.admin_id)
        except Exception:
            return False

    def _esc(self, t):
        if t is None:
            return "—"
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    async def _get_list(self, key):
        raw = db_get(T, key, None)
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
            return v if isinstance(v, list) else []
        except Exception:
            return []

    async def _set_list(self, key, value):
        db_set(T, key, json.dumps(value))

    async def _get_dict(self, key):
        raw = db_get(T, key, None)
        if raw is None:
            return {}
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}

    async def _set_dict(self, key, value):
        db_set(T, key, json.dumps(value))

    async def _get_users(self):
        return await self._get_list("users")

    async def _set_users(self, v):
        await self._set_list("users", v)

    async def _get_nonick(self):
        return await self._get_list("nonick")

    async def _set_nonick(self, v):
        await self._set_list("nonick", v)

    async def _get_timed(self):
        return await self._get_dict("timed")

    async def _set_timed(self, v):
        await self._set_dict("timed", v)

    async def _get_sgroups(self):
        return await self._get_dict("sgroups")

    async def _set_sgroups(self, v):
        await self._set_dict("sgroups", v)

    async def _get_access(self, uid):
        raw = db_get(T, "access_%d" % uid, None)
        defaults = {k: False for k in ACCESS_CATEGORIES}
        defaults["aliases"] = True
        if raw is None:
            return defaults
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(v, dict):
                return defaults
            return {k: bool(v.get(k, defaults.get(k, False))) for k in ACCESS_CATEGORIES}
        except Exception:
            return defaults

    async def _set_access(self, uid, access):
        db_set(T, "access_%d" % uid, json.dumps(access))

    async def _get_cmd_access(self, uid):
        return await self._get_dict("cmd_access_%d" % uid)

    async def _set_cmd_access(self, uid, v):
        await self._set_dict("cmd_access_%d" % uid, v)

    async def _display(self, uid):
        try:
            u = await self.client.get_entity(uid)
            if getattr(u, "username", None):
                return "@" + u.username
            return getattr(u, "first_name", None) or str(uid)
        except Exception:
            return str(uid)

    async def _resolve_target(self, event, args):
        if event.is_reply:
            r = await event.get_reply_message()
            if r:
                return r.sender_id
        if args:
            a = args[0].lstrip("@")
            if a.lstrip("-").isdigit():
                return int(a)
            try:
                e = await self.client.get_entity(a)
                return e.id
            except Exception:
                return None
        return None

    def _category_of(self, cmd_name):
        c = (cmd_name or "").lower()
        if c in CMD_TO_CAT:
            return CMD_TO_CAT[c]
        try:
            cmd = self.kernel.registry.find_command(c)
            if cmd:
                mod_name = getattr(cmd.module, "name", "").lower()
                if mod_name in ("dlm", "loader", "updates"):
                    return "modules"
                if mod_name == "terminal":
                    return "terminal"
                if mod_name in ("tapi", "updates"):
                    return "system"
                if mod_name == "tek":
                    return "config"
        except Exception:
            pass
        return None

    def _all_commands(self):
        try:
            return sorted(self.kernel.registry._commands.keys())
        except Exception:
            return []

    async def _is_sgroup_member(self, uid):
        groups = await self._get_sgroups()
        for g in groups.values():
            if uid in g.get("users", []):
                return True
        return False

    async def _sgroup_access_for(self, uid):
        groups = await self._get_sgroups()
        out = {}
        for name, g in groups.items():
            if uid in g.get("users", []):
                out[name] = g.get("access", {})
        return out

    async def _user_has_access(self, uid, category, cmd=None):
        if self._is_owner(uid):
            return True
        access = await self._get_access(uid)
        if cmd:
            ca = await self._get_cmd_access(uid)
            if cmd in ca and ca[cmd]:
                return True
        if access.get(category, False):
            return True
        groups = await self._sgroup_access_for(uid)
        for gacc in groups.values():
            if gacc.get(category, False):
                return True
        return False

    async def _notify(self, text):
        try:
            chat = getattr(self.kernel, "log_chat_id", None) or self.kernel.context.admin_id
            if chat is None:
                return
            await self.client.send_message(chat, text, parse_mode="html")
        except Exception as e:
            log.warning("notify failed: %s", e)

    config = {
        "default_preset": "user",
        "notify_on_add": True,
        "notify_on_remove": True,
        "notify_on_expire": True,
        "expire_check_interval": 60,
        "permission_refresh_interval": 30,
        "auto_allow_inline_on_trust": True,
        "auto_allow_callback_on_trust": True,
        "auto_allow_aliases_on_trust": True,
        "max_trusted": 0,
        "max_sgroups": 0,
        "watcher_enabled": True,
    }

    config_schema = {
        "default_preset": {"type": "str", "description": "Пресет по умолчанию при trust",
                            "options": ["user", "programmer", "moderator", "admin"]},
        "notify_on_add": {"type": "bool", "description": "Уведомлять в log-chat о добавлении"},
        "notify_on_remove": {"type": "bool", "description": "Уведомлять об удалении"},
        "notify_on_expire": {"type": "bool", "description": "Уведомлять об истечении временного trust"},
        "expire_check_interval": {"type": "int", "description": "Интервал проверки истёкших (сек)"},
        "permission_refresh_interval": {"type": "int", "description": "Интервал обновления прав inline (сек)"},
        "auto_allow_inline_on_trust": {"type": "bool", "description": "Автоматически разрешать inline"},
        "auto_allow_callback_on_trust": {"type": "bool", "description": "Автоматически разрешать callback"},
        "auto_allow_aliases_on_trust": {"type": "bool", "description": "Автоматически разрешать aliases"},
        "max_trusted": {"type": "int", "description": "Максимум trust (0 = без лимита)"},
        "max_sgroups": {"type": "int", "description": "Максимум sgroup (0 = без лимита)"},
        "watcher_enabled": {"type": "bool", "description": "Перехватывать команды от trust"},
    }

    @command(name="trust", aliases=["addtrust", "addowner"], description="Добавить в доверенные", only_for="owner")
    async def cmd_trust(self, event, args):
        uid = await self._resolve_target(event, args)
        if uid is None:
            await event.edit(self._t("usage_trust"), parse_mode="html")
            return
        users = await self._get_users()
        if uid in users:
            await event.edit(self._t("already_trusted"), parse_mode="html")
            return
        max_t = int(self.cfg.get("max_trusted", 0))
        if max_t and len(users) >= max_t:
            await event.edit(self._t("max_reached"), parse_mode="html")
            return

        users.append(uid)
        await self._set_users(users)

        preset_key = self.cfg.get("default_preset", "user")
        preset = PRESETS.get(preset_key, PRESETS["user"])
        access = {k: False for k in ACCESS_CATEGORIES}
        access.update(preset["access"])
        if self.cfg.get("auto_allow_inline_on_trust", True):
            access["inline"] = True
        if self.cfg.get("auto_allow_callback_on_trust", True):
            access["callback"] = True
        if self.cfg.get("auto_allow_aliases_on_trust", True):
            access["aliases"] = True
        await self._set_access(uid, access)

        if access.get("inline"):
            try:
                await self._im().allow_user(uid)
            except Exception:
                pass

        if self.cfg.get("notify_on_add", True):
            try:
                await self._notify("➕ %s → trusted (preset: %s)" % (await self._display(uid), preset_key))
            except Exception:
                pass

        await event.edit(
            shell.wrap([
                "trust added",
                "  user   : " + str(uid),
                "  preset : " + preset_key,
            ], cmd="trust", trailing=True),
            parse_mode="html",
        )

    @command(name="untrust", aliases=["deltrust", "delowner"], description="Убрать из доверенных", only_for="owner")
    async def cmd_untrust(self, event, args):
        uid = await self._resolve_target(event, args)
        if uid is None:
            await event.edit(self._t("usage_untrust"), parse_mode="html")
            return
        users = await self._get_users()
        if uid not in users:
            await event.edit(self._t("not_trusted"), parse_mode="html")
            return
        users.remove(uid)
        await self._set_users(users)

        nn = await self._get_nonick()
        if uid in nn:
            nn.remove(uid)
            await self._set_nonick(nn)

        timed = await self._get_timed()
        timed.pop(str(uid), None)
        await self._set_timed(timed)

        try:
            await self._im().deny_user(uid)
        except Exception:
            pass

        if self.cfg.get("notify_on_remove", True):
            try:
                await self._notify("➖ %s → untrusted" % (await self._display(uid)))
            except Exception:
                pass

        await event.edit("🚫 untrusted: <code>%d</code>" % uid, parse_mode="html")

    @command(name="trustlist", aliases=["listtrust"], description="Список доверенных")
    async def cmd_trustlist(self, event, args):
        users = await self._get_users()
        if not users:
            await event.edit(self._t("list_empty"), parse_mode="html")
            return
        nn = await self._get_nonick()
        lines = [self._t("list_title"), ""]
        for u in users:
            name = await self._display(u)
            nn_mark = " 🔑" if u in nn else ""
            lines.append("• %s <code>(%d)</code>%s" % (self._esc(name), u, nn_mark))
        await event.edit("\n".join(lines), parse_mode="html")

    @command(name="nonickuser", description="Toggle NoNick для пользователя", only_for="owner")
    async def cmd_nonickuser(self, event, args):
        uid = await self._resolve_target(event, args)
        if uid is None:
            await event.edit(self._t("usage_nonick"), parse_mode="html")
            return
        users = await self._get_users()
        if uid not in users:
            await event.edit(self._t("not_trusted"), parse_mode="html")
            return
        nn = await self._get_nonick()
        name = await self._display(uid)
        if uid in nn:
            nn.remove(uid)
            await self._set_nonick(nn)
            await event.edit(self._t("nonick_off", name=self._esc(name)), parse_mode="html")
        else:
            nn.append(uid)
            await self._set_nonick(nn)
            await event.edit(self._t("nonick_on", name=self._esc(name)), parse_mode="html")

    @command(name="nonickusers", description="Список NoNick")
    async def cmd_nonickusers(self, event, args):
        nn = await self._get_nonick()
        if not nn:
            await event.edit(self._t("nonick_empty"), parse_mode="html")
            return
        lines = [self._t("nonick_title"), ""]
        for u in nn:
            lines.append("• %s <code>(%d)</code>" % (self._esc(await self._display(u)), u))
        await event.edit("\n".join(lines), parse_mode="html")

    @command(name="timedtrusted", description="Временные доверенные")
    async def cmd_timedtrusted(self, event, args):
        timed = await self._get_timed()
        if not timed:
            await event.edit(self._t("timed_empty"), parse_mode="html")
            return
        now = time.time()
        lines = [self._t("timed_title"), ""]
        for uid_str, exp in timed.items():
            left = int(float(exp) - now)
            if left <= 0:
                continue
            name = await self._display(int(uid_str))
            mins = left // 60
            lines.append("• %s — %d мин" % (self._esc(name), mins))
        await event.edit("\n".join(lines), parse_mode="html")

    async def _get_custom_access(self, uid):
        raw = db_get(T, "custom_access_%d" % uid, None)
        if raw is None:
            return {}
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}

    async def _set_custom_access(self, uid, value):
        db_set(T, "custom_access_%d" % uid, json.dumps(value))

    def _custom_modules(self):
        result = {}
        try:
            from pathlib import Path as _P
            custom_dir = _P("modules_custom")
            if not custom_dir.exists():
                return result
            reg = self.kernel.registry
            by_mod = {}
            for name, cmd in reg._commands.items():
                mod = getattr(cmd, "module", None)
                if mod is None:
                    continue
                mod_name = getattr(mod, "name", None)
                if not mod_name:
                    continue
                by_mod.setdefault(mod_name, []).append(name)

            for mod_name, cmds in by_mod.items():
                if self._is_custom_module(mod_name):
                    result[mod_name] = sorted(cmds)
        except Exception as e:
            log.warning("_custom_modules: %s", e)
        return result

    def _is_custom_module(self, mod_name):
        try:
            reg = self.kernel.registry
            mod = None
            for n, mm in reg._modules.items():
                if n.lower() == mod_name.lower() or getattr(mm, "name", "").lower() == mod_name.lower():
                    mod = mm
                    break
            if mod is None:
                return False
            mod_file = getattr(mod.__class__, "__module__", "") or ""
            import sys as _sys
            from pathlib import Path as _P
            real = _sys.modules.get(mod_file)
            if real and getattr(real, "__file__", None):
                path = _P(real.__file__).as_posix()
                parts = path.split("/")
                return "modules_custom" in parts
        except Exception:
            pass
        return False

    async def _user_has_custom_access(self, uid, mod_name):
        if self._is_owner(uid):
            return True
        ca = await self._get_custom_access(uid)
        return bool(ca.get(mod_name, False))

    def _access_text(self, name, access, group_access=None):
        total = len(ACCESS_CATEGORIES)
        allowed = 0
        via_group = 0
        denied = 0

        body = []
        for cat, info in ACCESS_CATEGORIES.items():
            own = access.get(cat, False)
            grp = False
            if group_access:
                for gacc in group_access.values():
                    if gacc.get(cat, False):
                        grp = True
                        break

            if own:
                icon = "🟢"
                allowed += 1
            elif grp:
                icon = "🔵"
                via_group += 1
            else:
                icon = "🔴"
                denied += 1

            body.append("%s <b>%s</b> — <i>%s</i>" % (icon, self._esc(info["label"]), self._esc(info["desc"])))

        title = self._t("access_title", user=self._esc(name))
        stats = "🟢 %d  🔵 %d  🔴 %d" % (allowed, via_group, denied)

        return (
            title + "\n"
            + "<blockquote>" + stats + "</blockquote>\n"
            + "<blockquote expandable>" + "\n".join(body) + "</blockquote>\n"
            + self._t("access_footer")
        )

    def _access_buttons(self, uid, access, group_access=None):
        rows = []
        for row_cats in CATEGORY_ROWS:
            row = []
            for cat in row_cats:
                info = ACCESS_CATEGORIES[cat]
                own = access.get(cat, False)
                via_group = False
                if group_access:
                    for gacc in group_access.values():
                        if gacc.get(cat, False):
                            via_group = True
                            break
                if own:
                    style = "success"
                elif via_group:
                    style = "primary"
                else:
                    style = "danger"

                async def on_toggle(cb, u=uid, c=cat):
                    sender = cb.sender_id
                    if not (self._is_owner(sender) or await self._is_sgroup_member(sender)):
                        await cb.answer("no access", alert=False)
                        return
                    cur = await self._get_access(u)
                    cur[c] = not cur.get(c, False)
                    await self._set_access(u, cur)
                    if c == "inline":
                        im = self._im()
                        if cur[c]:
                            await im.allow_user(u)
                        else:
                            await im.deny_user(u)
                    await self._render_access(cb, u)

                row.append(self.kernel.inline.make_button(
                    info["label"],
                    on_toggle, ttl=900, style=style))
            rows.append(row)

        async def on_allow_all(cb, u=uid):
            if not self._is_owner(cb.sender_id):
                return
            full = {k: True for k in ACCESS_CATEGORIES}
            await self._set_access(u, full)
            await self._im().allow_user(u)
            await self._render_access(cb, u)

        async def on_deny_all(cb, u=uid):
            if not self._is_owner(cb.sender_id):
                return
            none = {k: False for k in ACCESS_CATEGORIES}
            await self._set_access(u, none)
            await self._im().deny_user(u)
            await self._render_access(cb, u)

        async def on_percmd(cb, u=uid):
            await self._show_percmd(cb, u)

        async def on_back(cb, u=uid):
            await self._show_user(cb, u)

        async def on_close(cb):
            await self._close_menu(cb)

        rows.append([
            self.kernel.inline.make_button(self._t("btn_allow_all"), on_allow_all, ttl=900, style="success"),
            self.kernel.inline.make_button(self._t("btn_deny_all"), on_deny_all, ttl=900, style="danger"),
        ])
        async def on_custom(cb, u=uid):
            await self._show_custom_menu(cb, u)

        rows.append([
            self.kernel.inline.make_button(self._t("btn_percmd"), on_percmd, ttl=900),
            self.kernel.inline.make_button(self._t("btn_custom"), on_custom, ttl=900),
        ])
        rows.append([
            self.kernel.inline.make_button(self._t("btn_back"), on_back, ttl=900),
            self.kernel.inline.make_button(self._t("btn_close"), on_close, ttl=900),
        ])
        return rows

    async def _render_access(self, cb, uid):
        access = await self._get_access(uid)
        g_access = await self._sgroup_access_for(uid)
        name = await self._display(uid)
        text = self._access_text(name, access, g_access)
        buttons = self._access_buttons(uid, access, g_access)
        await self.kernel.inline.edit(cb, text, buttons)

    async def _show_user(self, cb, uid):
        users = await self._get_users()
        if uid not in users:
            try:
                await cb.answer(self._t("not_trusted"), alert=True)
            except Exception:
                pass
            return
        await self._render_access(cb, uid)

    async def _show_percmd(self, cb, uid, page=0):
        all_cmds = self._all_commands()
        per_page = 10
        total_pages = max(1, (len(all_cmds) + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))
        slice_ = all_cmds[page * per_page:(page + 1) * per_page]
        ca = await self._get_cmd_access(uid)
        access = await self._get_access(uid)
        name = await self._display(uid)

        lines = [self._t("percmd_title", user=name), ""]
        for c in slice_:
            allowed = ca.get(c, None)
            if allowed is None:
                cat = self._category_of(c)
                allowed = access.get(cat, False) if cat else False
            icon = "✅" if allowed else "🚫"
            lines.append("%s <code>%s</code>" % (icon, self._esc(c)))
        lines.append("")
        lines.append("<i>%d/%d</i>" % (page + 1, total_pages))
        text = "\n".join(lines)

        rows = []
        for c in slice_:
            allowed = ca.get(c, None)
            if allowed is None:
                cat = self._category_of(c)
                allowed = access.get(cat, False) if cat else False
            async def on_toggle(cb2, u=uid, cc=c, a=allowed, p=page):
                if not (self._is_owner(cb2.sender_id) or await self._is_sgroup_member(cb2.sender_id)):
                    return
                d = await self._get_cmd_access(u)
                d[cc] = not a
                await self._set_cmd_access(u, d)
                await self._show_percmd(cb2, u, p)
            icon = "✅" if allowed else "🚫"
            rows.append([self.kernel.inline.make_button(
                "%s %s" % (icon, c), on_toggle, ttl=900,
                style=("primary" if allowed else None))])

        nav = []
        if page > 0:
            async def on_prev(cb2, u=uid, p=page - 1):
                await self._show_percmd(cb2, u, p)
            nav.append(self.kernel.inline.make_button("<", on_prev, ttl=900))
        if page < total_pages - 1:
            async def on_next(cb2, u=uid, p=page + 1):
                await self._show_percmd(cb2, u, p)
            nav.append(self.kernel.inline.make_button(">", on_next, ttl=900))
        if nav:
            rows.append(nav)

        async def on_back(cb2, u=uid):
            await self._show_user(cb2, u)
        rows.append([
            self.kernel.inline.make_button(self._t("btn_back"), on_back, ttl=900),
        ])
        await self.kernel.inline.edit(cb, text, rows)

    async def _show_custom_menu(self, cb, uid, page=0):
        modules = self._custom_modules()
        if not modules:
            try:
                await cb.answer(self._t("custom_empty"), alert=True)
            except Exception:
                pass
            return

        names = sorted(modules.keys())
        per_page = 8
        total_pages = max(1, (len(names) + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))
        slice_ = names[page * per_page:(page + 1) * per_page]

        ca = await self._get_custom_access(uid)
        name = await self._display(uid)

        allowed = sum(1 for m in names if ca.get(m, False))
        denied = len(names) - allowed

        title = self._t("custom_title", user=self._esc(name))
        stats = "🟢 %d  🔴 %d" % (allowed, denied)

        body = []
        for mod in slice_:
            on = ca.get(mod, False)
            icon = "🟢" if on else "🔴"
            cnt = len(modules.get(mod, []))
            body.append("%s <b>%s</b> <i>(%d)</i>" % (icon, self._esc(mod), cnt))

        page_info = ""
        if total_pages > 1:
            page_info = " <i>[%d/%d]</i>" % (page + 1, total_pages)

        text = (
            title + page_info + "\n"
            + "<blockquote>" + stats + "</blockquote>\n"
            + "<blockquote expandable>" + "\n".join(body) + "</blockquote>\n"
            + self._t("custom_footer")
        )

        rows = []
        chunk = []
        for mod in slice_:
            on = ca.get(mod, False)
            label = mod
            if len(label) > 24:
                label = label[:24]

            async def on_toggle_mod(cb2, u=uid, m=mod, p=page):
                cur = await self._get_custom_access(u)
                cur[m] = not cur.get(m, False)
                await self._set_custom_access(u, cur)
                await self._show_custom_menu(cb2, u, p)

            chunk.append(self.kernel.inline.make_button(
                label, on_toggle_mod, ttl=900,
                style=("success" if on else "danger")))
            if len(chunk) == 2:
                rows.append(chunk)
                chunk = []
        if chunk:
            rows.append(chunk)

        nav = []
        if page > 0:
            async def on_prev(cb2, u=uid, p=page - 1):
                await self._show_custom_menu(cb2, u, p)
            nav.append(self.kernel.inline.make_button("<", on_prev, ttl=900))
        if page < total_pages - 1:
            async def on_next(cb2, u=uid, p=page + 1):
                await self._show_custom_menu(cb2, u, p)
            nav.append(self.kernel.inline.make_button(">", on_next, ttl=900))
        if nav:
            rows.append(nav)

        async def on_back(cb2, u=uid):
            await self._show_user(cb2, u)

        async def on_close(cb2):
            await self._close_menu(cb2)

        rows.append([
            self.kernel.inline.make_button(self._t("btn_back"), on_back, ttl=900),
            self.kernel.inline.make_button(self._t("btn_close"), on_close, ttl=900),
        ])

        await self.kernel.inline.edit(cb, text, rows)

    async def _close_menu(self, cb):
        try:
            await cb.answer()
        except Exception:
            pass
        try:
            await cb.delete()
            return
        except Exception:
            pass
        try:
            await cb.edit(self._t("menu_closed"), parse_mode="html", buttons=None)
        except Exception:
            pass

    @command(name="trustaccess", description="Управление доступами пользователя", only_for="owner")
    async def cmd_trustaccess(self, event, args):
        uid = await self._resolve_target(event, args)
        if uid is None:
            await event.edit(self._t("usage_trustaccess"), parse_mode="html")
            return
        users = await self._get_users()
        if uid not in users:
            await event.edit(self._t("not_trusted"), parse_mode="html")
            return
        bot = getattr(self.kernel, "bot_client", None)
        access = await self._get_access(uid)
        g_access = await self._sgroup_access_for(uid)
        name = await self._display(uid)
        text = self._access_text(name, access, g_access)
        buttons = self._access_buttons(uid, access, g_access)
        if bot is None:
            await event.edit(text, parse_mode="html")
            return
        try:
            await event.delete()
        except Exception:
            pass
        await bot.send_inline_menu(
            chat_id=event.chat_id,
            key="trustaccess_%d_%d" % (uid, int(time.time())),
            text=text,
            buttons=buttons,
        )

    @command(name="sgroup", description="Группы доступа", only_for="owner")
    async def cmd_sgroup(self, event, args):
        if not args:
            await event.edit(self._t("sgroup_usage"), parse_mode="html")
            return
        sub = args[0].lower()
        groups = await self._get_sgroups()

        if sub == "list":
            if not groups:
                await event.edit(self._t("sgroup_list_empty"), parse_mode="html")
                return
            lines = [self._t("sgroup_list_title"), ""]
            for name, g in groups.items():
                lines.append("• <b>%s</b> — %d users, %d access" % (
                    self._esc(name), len(g.get("users", [])),
                    sum(1 for v in g.get("access", {}).values() if v)))
            await event.edit("\n".join(lines), parse_mode="html")
            return

        if sub == "create":
            if len(args) < 2:
                await event.edit(self._t("sgroup_usage"), parse_mode="html")
                return
            name = args[1]
            if name in groups:
                await event.edit(self._t("sgroup_exists", name=self._esc(name)), parse_mode="html")
                return
            max_s = int(self.cfg.get("max_sgroups", 0))
            if max_s and len(groups) >= max_s:
                await event.edit(self._t("max_reached"), parse_mode="html")
                return
            groups[name] = {"users": [], "access": {k: False for k in ACCESS_CATEGORIES}}
            await self._set_sgroups(groups)
            await event.edit(self._t("sgroup_created", name=self._esc(name)), parse_mode="html")
            return

        if sub == "delete":
            if len(args) < 2:
                await event.edit(self._t("sgroup_usage"), parse_mode="html")
                return
            name = args[1]
            if name not in groups:
                await event.edit(self._t("sgroup_not_found", name=self._esc(name)), parse_mode="html")
                return
            del groups[name]
            await self._set_sgroups(groups)
            await event.edit(self._t("sgroup_deleted", name=self._esc(name)), parse_mode="html")
            return

        if sub in ("add", "remove"):
            if len(args) < 3:
                await event.edit(self._t("sgroup_usage"), parse_mode="html")
                return
            name = args[1]
            tgt = args[2].lstrip("@")
            if tgt.lstrip("-").isdigit():
                uid = int(tgt)
            else:
                try:
                    e = await self.client.get_entity(tgt)
                    uid = e.id
                except Exception:
                    await event.edit(self._t("sgroup_usage"), parse_mode="html")
                    return
            if name not in groups:
                await event.edit(self._t("sgroup_not_found", name=self._esc(name)), parse_mode="html")
                return
            users_in_group = groups[name].setdefault("users", [])
            if sub == "add":
                if uid in users_in_group:
                    await event.edit(self._t("sgroup_user_in_group"), parse_mode="html")
                    return
                users_in_group.append(uid)
                await self._set_sgroups(groups)
                await event.edit(self._t("sgroup_user_added",
                    user=self._esc(await self._display(uid)), group=self._esc(name)),
                    parse_mode="html")
            else:
                if uid not in users_in_group:
                    await event.edit(self._t("sgroup_user_not_in_group"), parse_mode="html")
                    return
                users_in_group.remove(uid)
                await self._set_sgroups(groups)
                await event.edit(self._t("sgroup_user_removed",
                    user=self._esc(await self._display(uid)), group=self._esc(name)),
                    parse_mode="html")
            return

        if sub == "info":
            if len(args) < 2 or args[1] not in groups:
                await event.edit(self._t("sgroup_usage"), parse_mode="html")
                return
            name = args[1]
            g = groups[name]
            lines = [self._t("sgroup_info_title", name=self._esc(name)), ""]
            if g.get("users"):
                lines.append("<b>Users:</b>")
                for u in g["users"]:
                    lines.append("• %s <code>(%d)</code>" % (self._esc(await self._display(u)), u))
            else:
                lines.append("<i>(нет пользователей)</i>")
            await event.edit("\n".join(lines), parse_mode="html")
            return

        await event.edit(self._t("sgroup_usage"), parse_mode="html")

    @command(name="ownerprefix", description="Показать префикс владельца")
    async def cmd_ownerprefix(self, event, args):
        try:
            prefix = self.kernel.get_prefix_for_sender(self.kernel.context.admin_id)
        except Exception:
            prefix = getattr(self.kernel, "prefix", ".")
        await event.edit("👑 owner prefix: <code>%s</code>" % self._esc(prefix), parse_mode="html")

    @command(name="watchers", description="Список watcher'ов")
    async def cmd_watchers(self, event, args):
        reg = getattr(self.kernel, "registry", None)
        ws = []
        try:
            if reg is not None:
                ws = reg.list_watchers() or []
        except Exception:
            ws = []
        if not ws:
            await event.edit(self._t("watchers_empty"), parse_mode="html")
            return
        lines = [self._t("watchers_title"), ""]
        for i, item in enumerate(ws, 1):
            try:
                mod, func = item
                mod_name = getattr(mod, "name", "?")
                fn_name = getattr(func, "__name__", "?")
                lines.append("<code>%d.</code> <b>%s.%s</b>" % (i, self._esc(mod_name), self._esc(fn_name)))
            except Exception:
                lines.append("<code>%d.</code> ?" % i)
        await event.edit("\n".join(lines), parse_mode="html")

    @command(name="watcher", description="Вкл/выкл watcher", only_for="owner")
    async def cmd_watcher(self, event, args):
        if len(args) < 2:
            await event.edit(self._t("usage_watcher"), parse_mode="html")
            return
        await event.edit(
            "ℹ️ Watcher'ы управляются через ядро, отдельного toggle пока нет.\n"
            "Смотри список: <code>?watchers</code>",
            parse_mode="html",
        )

    @watcher()
    async def trusted_watcher(self, event):
        if not self.cfg.get("watcher_enabled", True):
            return

        msg = getattr(event, "message", event)
        if getattr(msg, "out", False):
            return

        sender_id = getattr(event, "sender_id", None)
        if sender_id is None:
            return
        if self._is_owner(sender_id):
            return

        users = await self._get_users()
        if sender_id not in users:
            return

        text = getattr(msg, "raw_text", "") or ""
        prefix = getattr(self.kernel, "prefix", ".")

        if not text.startswith(prefix):
            return

        body = text[len(prefix):].strip()
        if not body:
            return

        parts = body.split()
        cmd_name = parts[0].lower()
        rest = parts[1:]

        access = await self._get_access(sender_id)
        if access.get("aliases", True):
            try:
                if cmd_name in self.kernel.registry._aliases:
                    cmd_name = self.kernel.registry._aliases[cmd_name]
            except Exception:
                pass

        cmd = self.kernel.registry.find_command(cmd_name)
        if cmd is None:
            return

        cmd_module = getattr(cmd, "module", None)
        cmd_mod_name = getattr(cmd_module, "name", None) if cmd_module else None

        if cmd_mod_name and self._is_custom_module(cmd_mod_name):
            if not await self._user_has_custom_access(sender_id, cmd_mod_name):
                try:
                    await event.reply(self._t("no_access_cmd"))
                except Exception:
                    pass
                event._tetko_handled = True
                return
        else:
            cat = self._category_of(cmd_name)
            if cat is None:
                return

            if not await self._user_has_access(sender_id, cat, cmd=cmd_name):
                try:
                    await event.reply(self._t("no_access_cmd"))
                except Exception:
                    pass
                event._tetko_handled = True
                return

        event._tetko_handled = True

        new_text = prefix + cmd_name
        if rest:
            new_text += " " + " ".join(rest)

        try:
            sent = await self.client.send_message(event.chat_id, new_text)
        except Exception as e:
            log.warning("trusted_watcher send failed: %s", e)
            return

        class _FakeEvent:
            def __init__(self, client, sent_msg, admin_id, raw_text):
                self._client = client
                self._sent_msg = sent_msg
                self.sender_id = admin_id
                self.chat_id = sent_msg.chat_id
                self.raw_text = raw_text
                self.text = raw_text
                self.message = sent_msg
                self.out = True
                self.is_reply = False
                self.id = getattr(sent_msg, "id", None)

            async def edit(self, text, **kw):
                return await self._sent_msg.edit(text, **kw)

            async def reply(self, text, **kw):
                return await self._sent_msg.reply(text, **kw)

            async def respond(self, text, **kw):
                return await self._sent_msg.respond(text, **kw)

            async def delete(self, **kw):
                return await self._sent_msg.delete(**kw)

            async def get_reply_message(self):
                return None

            def get_input_chat(self):
                try:
                    return self._sent_msg.get_input_chat()
                except Exception:
                    return None

            async def answer(self, text="", **kw):
                return None

        fake = _FakeEvent(self.client, sent, self.kernel.context.admin_id, new_text)
        try:
            try:
                await cmd.func(fake, rest)
            except TypeError:
                await cmd.func(fake)
        except Exception as e:
            full = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            log.error("trusted cmd %s failed: %s\n%s", cmd_name, e, full)

    @loop(interval=60)
    async def check_expired(self):
        try:
            timed = await self._get_timed()
        except Exception:
            return
        if not timed:
            return
        now = time.time()
        try:
            users = await self._get_users()
        except Exception:
            return
        changed = False
        for uid_str, exp in list(timed.items()):
            try:
                if now < float(exp):
                    continue
            except Exception:
                continue
            try:
                uid = int(uid_str)
            except Exception:
                continue
            if uid in users:
                users.remove(uid)
                changed = True
            try:
                nn = await self._get_nonick()
                if uid in nn:
                    nn.remove(uid)
                    await self._set_nonick(nn)
            except Exception:
                pass
            try:
                await self._im().deny_user(uid)
            except Exception:
                pass
            del timed[uid_str]
            changed = True
            if self.cfg.get("notify_on_expire", True):
                try:
                    await self._notify("⏰ trust истёк: %s" % (await self._display(uid)))
                except Exception:
                    pass
        if changed:
            try:
                await self._set_users(users)
                await self._set_timed(timed)
            except Exception:
                pass

    @loop(interval=30)
    async def refresh_inline_perms(self):
        try:
            users = await self._get_users()
        except Exception:
            return
        im = self._im()
        for uid in users:
            try:
                access = await self._get_access(uid)
                if access.get("inline", False):
                    await im.allow_user(uid)
            except Exception:
                pass
