"""Tek — модули, инфо о системе."""
import time
import logging
import sys

from core.tetko import Module, command, db_get, db_set

START_TIME = time.time()
log = logging.getLogger("TETKO.module.tek")

EMOJI_SYS = '<tg-emoji emoji-id="6012473147998084083">🙏</tg-emoji>'
EMOJI_USER = '<tg-emoji emoji-id="5208774197278447727">❤️</tg-emoji>'
EMOJI_Q = '<tg-emoji emoji-id="6010208325843557447">❔</tg-emoji>'
EMOJI_TRASH = '<tg-emoji emoji-id="5348118479847333898">🗑</tg-emoji>'
EMOJI_HEART1 = '<tg-emoji emoji-id="5282797322969852134">❤️</tg-emoji>'
EMOJI_HEART2 = '<tg-emoji emoji-id="5208814909273445904">❤️</tg-emoji>'

FB_SYS = '🔧'
FB_USER = '👤'
FB_Q = '❔'
FB_TRASH = '🗑'

PAGE_SIZE = 10
CMD_LIMIT = 3


def _premium(kernel) -> bool:
    try:
        return bool(getattr(kernel.context, "user_premium", False))
    except Exception:
        return False


class Tek(Module):
    name = "Tek"
    __compat__ = "0.9.1"
    version = "2.1.0"
    author = "@anhedonuya & @flexownerAL"
    description = {
        "ru": "Модули, команды, скрытие, инфо",
        "en": "Modules, commands, hiding, info",
    }

    def _get_hidden(self) -> list:
        data = db_get("tek", "hidden", [])
        return list(data) if isinstance(data, list) else []

    def _set_hidden(self, hidden: list):
        db_set("tek", "hidden", list(hidden))

    def _is_system(self, mod) -> bool:
        mod_file = getattr(mod, "__module__", "") or ""
        try:
            import sys as _sys
            from pathlib import Path as _Path
            real_mod = _sys.modules.get(mod_file)
            if real_mod and hasattr(real_mod, "__file__"):
                path = _Path(real_mod.__file__).as_posix()
                parts = path.split("/")
                if "modules_custom" in parts:
                    return False
                if "modules" in parts:
                    return True
        except Exception:
            pass
        return False

    def _modules_split(self):
        registry = self.kernel.registry
        hidden = self._get_hidden()
        sys_mods, user_mods = [], []
        for name, mod in registry._modules.items():
            if name in hidden:
                continue
            if self._is_system(mod):
                sys_mods.append(mod)
            else:
                user_mods.append(mod)
        return sys_mods, user_mods

    def _cmds_for_module(self, mod) -> list:
        registry = self.kernel.registry
        _mod_name = getattr(mod, "name", None) or type(mod).__name__

        result = []
        for cmd in registry._commands.values():
            cmd_mod = getattr(cmd, "module", None)
            if cmd_mod is mod:
                result.append(cmd)
                continue
            _cmd_mod_name = getattr(cmd_mod, "name", None) or (
                type(cmd_mod).__name__ if cmd_mod is not None else None
            )
            if _cmd_mod_name == _mod_name:
                result.append(cmd)

        result.sort(key=lambda c: c.name)
        return result

    def _module_line(self, mod, lang: str) -> str:
        cmds = self._cmds_for_module(mod)
        if not cmds:
            return f"▫️ <b>{mod.name}</b>: <i>{self._t('no_cmds')}</i>"

        _prefix = getattr(self.kernel, "prefix", ".") or "."
        parts = []
        for i, cmd in enumerate(cmds):
            if i >= CMD_LIMIT:
                parts.append(f"(+{len(cmds) - CMD_LIMIT})")
                break
            s = f"<code>{_prefix}{self._esc(cmd.name)}</code>"
            if cmd.aliases:
                aliases = ", ".join(f"{_prefix}{self._esc(a)}" for a in cmd.aliases)
                s += f" [<i>{aliases}</i>]"
            parts.append(s)
        return f"▫️ <b>{mod.name}</b>: " + ", ".join(parts)

    def _find_module(self, name: str):
        registry = self.kernel.registry
        if name in registry._modules:
            return registry._modules[name]
        low = name.lower()
        for n, m in registry._modules.items():
            if n.lower() == low:
                return m
        return None

    def _esc(self, t) -> str:
        if t is None:
            return "—"
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @command(name="tek", description="Модули и команды")
    async def cmd_tek(self, event, args):
        if args:
            await self._show_module_info(event, args[0])
            return
        await self._show_help(event)

    async def _show_module_info(self, event, name: str):
        mod = self._find_module(name)
        if mod is None:
            await event.edit(
                "<blockquote>" + self._t("module_not_found", name=self._esc(name)) + "</blockquote>",
                parse_mode="html",
            )
            return

        lang_code = self._get_lang()
        if hasattr(mod, "get_description"):
            try:
                desc = mod.get_description(lang_code)
            except Exception:
                desc = "—"
        else:
            _d = getattr(mod, "description", "—")
            if isinstance(_d, dict):
                desc = _d.get(lang_code) or _d.get("ru") or _d.get("en") or next(iter(_d.values()), "—")
            else:
                desc = _d or "—"
        if not isinstance(desc, str):
            desc = str(desc)
        ver = getattr(mod, "version", "—")
        author = getattr(mod, "author", "—")
        compat = getattr(mod, "__compat__", None)
        if not compat:
            try:
                mro = type(mod).__mro__
                _is_mcub = any("MCUBModuleBase" in c.__name__ for c in mro)
            except Exception:
                _is_mcub = False
            compat = "mcub-compat" if _is_mcub else "—"
        is_sys = self._is_system(mod)
        kind = self._t("kind_system") if is_sys else self._t("kind_user")

        cmds = self._cmds_for_module(mod)
        if cmds:
            cmd_lines = []
            for c in cmds:
                _prefix = getattr(self.kernel, "prefix", ".") or "."
                line = f"🪬 <code>{_prefix}{self._esc(c.name)}</code>"
                if c.aliases:
                    aliases = ", ".join(f"{_prefix}{self._esc(a)}" for a in c.aliases)
                    line += f" [<i>{aliases}</i>]"
                if c.only_for:
                    line += f" <i>({self._esc(c.only_for)})</i>"
                if c.doc:
                    doc = c.doc if isinstance(c.doc, str) else (
                        c.doc.get(lang_code) or c.doc.get("ru") or c.doc.get("en") or ""
                    )
                    if doc:
                        line += f" — {self._esc(doc)}"
                cmd_lines.append(line)
            cmds_block = "\n".join(cmd_lines)
        else:
            cmds_block = "<i>" + self._t("no_cmds") + "</i>"

        header = self._t("module_header", name=self._esc(mod.name), version=self._esc(ver), kind=kind)
        desc_line = self._t("module_desc", desc=self._esc(desc))
        cmds_header = self._t("module_cmds", count=len(cmds))
        author_line = self._t("module_author", author=self._esc(author))
        compat_line = self._t("module_compat", compat=self._esc(compat))

        text = (
            f"<blockquote><b>{header}</b></blockquote>\n"
            f"<blockquote>{desc_line}</blockquote>\n"
            f"<blockquote><b>{cmds_header}</b>\n{cmds_block}</blockquote>\n"
            f"<blockquote>{author_line}\n{compat_line}</blockquote>"
        )
        await event.edit(text, parse_mode="html")

    async def _show_help(self, event_or_cb, is_cb: bool = False):
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return

        premium = _premium(self.kernel)

        sys_emoji = FB_SYS
        user_emoji = FB_USER
        q_emoji = EMOJI_Q if premium else FB_Q

        text = f"{self._t('help_title')} {q_emoji}{q_emoji}"

        async def on_sys(cb):
            await self._show_list(cb, "system", 0)

        async def on_user(cb):
            await self._show_list(cb, "user", 0)

        buttons = [[
            self.kernel.inline.make_button(f"{sys_emoji} {self._t('btn_sys')}", on_sys, ttl=600),
            self.kernel.inline.make_button(f"{user_emoji} {self._t('btn_user')}", on_user, ttl=600),
        ]]

        if is_cb:
            await self.kernel.inline.edit(event_or_cb, text, buttons)
        else:
            chat_id = event_or_cb.chat_id
            try:
                await event_or_cb.delete()
            except Exception:
                pass
            await bot.send_inline_menu(
                chat_id=chat_id,
                key=f"tek_help_{int(time.time())}",
                text=text,
                buttons=buttons,
            )

    async def _show_list(self, cb_event, kind: str, page: int):
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return

        premium = _premium(self.kernel)

        sys_mods, user_mods = self._modules_split()
        mods = sys_mods if kind == "system" else user_mods

        total_pages = max(1, (len(mods) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))

        start = page * PAGE_SIZE
        page_mods = mods[start:start + PAGE_SIZE]

        h1 = EMOJI_HEART1 if premium else "❤️"
        h2 = EMOJI_HEART2 if premium else "❤️"
        modules_line = self._t("modules_line", sys=len(sys_mods), user=len(user_mods))
        text = (
            f"{h1} <b>{self._t('title')}</b>\n"
            f"{h2} <b>{modules_line}</b>\n\n"
            "<blockquote expandable>"
        )
        for mod in page_mods:
            text += self._module_line(mod, None) + "\n"
        text += "</blockquote>"

        rows = []
        nav = []
        if page > 0:
            async def on_prev(cb, k=kind, p=page - 1):
                await self._show_list(cb, k, p)
            nav.append(self.kernel.inline.make_button("<", on_prev, ttl=600))

        async def on_noop(cb):
            await cb.answer()
        nav.append(self.kernel.inline.make_button("•", on_noop, ttl=600))

        for i in range(total_pages):
            if i == page:
                continue
            if len(nav) > 6:
                break
            async def on_page(cb, k=kind, p=i):
                await self._show_list(cb, k, p)
            nav.append(self.kernel.inline.make_button(str(i + 1), on_page, ttl=600))

        if page < total_pages - 1:
            async def on_next(cb, k=kind, p=page + 1):
                await self._show_list(cb, k, p)
            nav.append(self.kernel.inline.make_button(">", on_next, ttl=600))

        rows.append(nav)

        async def on_back(cb):
            await self._show_help(cb, is_cb=True)

        async def on_close(cb):
            try:
                await cb.answer()
            except Exception:
                pass
            bot = getattr(self.kernel, "bot_client", None)
            if bot is None:
                return
            data = getattr(cb, "data", b"")
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            imid = getattr(cb, "inline_message_id", None) or bot.get_inline_message_id(data)
            if not imid:
                return
            try:
                from telethon.tl.functions.messages import EditInlineBotMessageRequest
                await bot.client(EditInlineBotMessageRequest(
                    id=imid,
                    message=self._t("menu_closed"),
                    reply_markup=None,
                ))
            except Exception as e:
                log.warning(f"[TEK] close edit failed: {e}")

        trash = FB_TRASH
        rows.append([
            self.kernel.inline.make_button(f"← {self._t('back')}", on_back, ttl=600),
            self.kernel.inline.make_button(f"{trash} {self._t('close')}", on_close, ttl=600),
        ])

        await self.kernel.inline.edit(cb_event, text, rows)

    @command(name="tekhide", description="Скрыть/показать модуль")
    async def cmd_tekhide(self, event, args):
        await self._show_hide(event)

    async def _show_hide(self, event_or_cb, is_cb: bool = False, page: int = 0):
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return

        premium = _premium(self.kernel)
        hidden = self._get_hidden()

        registry = self.kernel.registry
        all_mods = sorted(registry._modules.keys())

        total_pages = max(1, (len(all_mods) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start = page * PAGE_SIZE
        page_mods = all_mods[start:start + PAGE_SIZE]

        page_line = self._t("page", page=page + 1, total=total_pages)
        text = f"<b>{self._t('hide_title')}</b> ({page_line})\n\n"
        text += "<blockquote expandable>"
        for name in page_mods:
            mark = "🔒" if name in hidden else "▫️"
            text += f"{mark} <code>{name}</code>\n"
        text += "</blockquote>"

        rows = []
        for name in page_mods:
            is_hidden = name in hidden
            label = f"✅ {name}" if is_hidden else f"▫️ {name}"

            async def on_toggle(cb, n=name, cur=is_hidden, p=page):
                h = self._get_hidden()
                if cur:
                    if n in h:
                        h.remove(n)
                else:
                    if n not in h:
                        h.append(n)
                self._set_hidden(h)
                await cb.answer(self._t("updated"))
                await self._show_hide(cb, is_cb=True, page=p)

            rows.append([self.kernel.inline.make_button(label, on_toggle, ttl=600)])

        nav = []
        if page > 0:
            async def on_prev(cb, p=page - 1):
                await self._show_hide(cb, is_cb=True, page=p)
            nav.append(self.kernel.inline.make_button("<", on_prev, ttl=600))
        if page < total_pages - 1:
            async def on_next(cb, p=page + 1):
                await self._show_hide(cb, is_cb=True, page=p)
            nav.append(self.kernel.inline.make_button(">", on_next, ttl=600))
        if nav:
            rows.append(nav)

        async def on_back(cb):
            await self._show_help(cb, is_cb=True)

        async def on_close(cb):
            try:
                await cb.answer()
            except Exception:
                pass
            bot = getattr(self.kernel, "bot_client", None)
            if bot is None:
                return
            data = getattr(cb, "data", b"")
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            imid = getattr(cb, "inline_message_id", None) or bot.get_inline_message_id(data)
            if not imid:
                return
            try:
                from telethon.tl.functions.messages import EditInlineBotMessageRequest
                close_html = self._t("menu_closed")
                try:
                    parsed, entities = await bot.client._parse_message_text(close_html, "html")
                except Exception:
                    parsed, entities = close_html, None
                await bot.client(EditInlineBotMessageRequest(
                    id=imid,
                    message=parsed,
                    entities=entities,
                    reply_markup=None,
                ))
            except Exception as e:
                log.warning(f"[TEK] close edit failed: {e}")

        trash = FB_TRASH
        rows.append([
            self.kernel.inline.make_button(f"← {self._t('back')}", on_back, ttl=600),
            self.kernel.inline.make_button(f"{trash} {self._t('close')}", on_close, ttl=600),
        ])

        if is_cb:
            await self.kernel.inline.edit(event_or_cb, text, rows)
        else:
            chat_id = event_or_cb.chat_id
            try:
                await event_or_cb.delete()
            except Exception:
                pass
            await bot.send_inline_menu(
                chat_id=chat_id,
                key=f"tek_hide_{int(time.time())}",
                text=text,
                buttons=rows,
            )

    @command(
        name="setprefix",
        aliases=["prefix"],
        description="Сменить префикс команд",
        only_for="owner",
    )
    async def cmd_setprefix(self, event, args):
        if not args:
            cur = self.kernel.prefix
            await event.edit(
                self._t("prefix_current", prefix=self._esc(cur))
                + "\n"
                + self._t("prefix_usage"),
                parse_mode="html",
            )
            return

        new_prefix = args[0].strip()

        if not new_prefix:
            await event.edit(self._t("prefix_empty"), parse_mode="html")
            return
        if len(new_prefix) > 3:
            await event.edit(self._t("prefix_too_long"), parse_mode="html")
            return
        if new_prefix.isspace():
            await event.edit(self._t("prefix_space"), parse_mode="html")
            return

        old_prefix = self.kernel.prefix

        self.kernel.prefix = new_prefix
        if hasattr(self.kernel, "context") and self.kernel.context is not None:
            self.kernel.context.prefix = new_prefix
        if hasattr(self.kernel, "dispatcher") and self.kernel.dispatcher is not None:
            self.kernel.dispatcher.prefix = new_prefix
        kk = getattr(self.kernel, "_k", None)
        if kk is not None and hasattr(kk, "_custom_prefix"):
            kk._custom_prefix = new_prefix

        try:
            import json
            from pathlib import Path as _Path
            cfg_path = _Path("config.json")
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                cfg["command_prefix"] = new_prefix
                cfg_path.write_text(
                    json.dumps(cfg, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except Exception as e:
            log.warning(f"setprefix: save failed: {e}")

        await event.edit(
            self._t("prefix_changed", old=self._esc(old_prefix), new=self._esc(new_prefix)),
            parse_mode="html",
        )

    @command(name="tekcfg", description="Состояние системы")
    async def cmd_tekcfg(self, event, args):
        uptime = round(time.time() - START_TIME)
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)

        registry = self.kernel.registry
        total_mods = len(registry._modules)
        total_cmds = len(registry._commands)
        premium = _premium(self.kernel)

        from core.tetko import __compat__ as _compat
        uptime_str = self._t("uptime_fmt", h=hours, m=minutes, s=seconds)

        text = (
            f"<b>{self._t('cfg_title')}</b>\n\n"
            + self._t("cfg_uptime", time=uptime_str) + "\n"
            + self._t("cfg_modules", count=total_mods) + "\n"
            + self._t("cfg_commands", count=total_cmds) + "\n"
            + self._t("cfg_python", version=sys.version.split()[0]) + "\n"
            + self._t("cfg_style", compat=_compat) + "\n"
            + self._t("cfg_premium", premium=premium) + "\n"
            + self._t("cfg_authors")
        )
        await event.edit(text, parse_mode="html")
