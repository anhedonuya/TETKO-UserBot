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


    def _cfg_dir(self):
        from pathlib import Path
        return Path("data/tetko_config")

    def _cfg_list(self):
        d = self._cfg_dir()
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.json"))

    def _cfg_read(self, module: str):
        import json
        from pathlib import Path
        p = self._cfg_dir() / f"{module}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _cfg_write(self, module: str, data: dict):
        import json
        from pathlib import Path
        d = self._cfg_dir()
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{module}.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    @command(name="cfg", aliases=["mcfg", "moduleconfig"], description="Конфиги модулей")
    async def cmd_cfg(self, event, args):
        self.log.info(f"[cfg] вызвана, args={args!r}")
        if not args:
            await self._cfg_show_list(event)
            return

        sub = args[0].lower()

        if sub in ("system", "sys", "системные"):
            await self._cfg_show_list(event, kind="system", page=0)
            return
        if sub in ("user", "custom", "пользовательские"):
            await self._cfg_show_list(event, kind="user", page=0)
            return

        if sub == "set":
            if len(args) < 4:
                await event.edit(self._t("cfg_set_usage"), parse_mode="html")
                return
            mod, key = args[1], args[2]
            value = " ".join(args[3:])
            data = self._cfg_read(mod)
            if data is None:
                await event.edit(self._t("cfg_not_found", module=self._esc(mod)), parse_mode="html")
                return
            parsed = self._parse_cfg_value(value)
            data[key] = parsed
            self._cfg_write(mod, data)
            await event.edit(self._t("cfg_set_done", key=self._esc(key), value=self._esc(str(parsed))), parse_mode="html")
            return

        if sub == "del":
            if len(args) < 3:
                await event.edit(self._t("cfg_del_usage"), parse_mode="html")
                return
            mod, key = args[1], args[2]
            data = self._cfg_read(mod)
            if data is None:
                await event.edit(self._t("cfg_not_found", module=self._esc(mod)), parse_mode="html")
                return
            if key not in data:
                await event.edit(self._t("cfg_key_not_found", key=self._esc(key)), parse_mode="html")
                return
            data.pop(key, None)
            self._cfg_write(mod, data)
            await event.edit(self._t("cfg_del_done", key=self._esc(key)), parse_mode="html")
            return

        await self._cfg_show_module(event, args[0])

    @staticmethod
    def _parse_cfg_value(s: str):
        low = s.lower()
        if low in ("true", "yes", "on"):
            return True
        if low in ("false", "no", "off"):
            return False
        if low == "null" or low == "none":
            return None
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            try:
                import json
                return json.loads(s)
            except Exception:
                pass
        return s

    def _cfg_kind(self, name: str) -> str:
        reg = getattr(self.kernel, "registry", None)
        if reg is not None:
            for mod_name, mod in reg._modules.items():
                if mod_name.lower() == name.lower():
                    return "system" if self._is_system(mod) else "user"
        from pathlib import Path as _P
        for p_name, kind in (("modules", "system"), ("modules_custom", "user")):
            d = _P(p_name)
            if d.exists():
                for f in d.glob("*.py"):
                    if f.stem.lower() == name.lower():
                        return kind
        return "system"

    async def _cfg_show_menu(self, event_or_cb, is_cb: bool = False):
        text = self._t("cfg_choose_section")
        rows = []

        async def on_sys(cb):
            await self._cfg_show_list(cb, is_cb=True, kind="system", page=0)

        async def on_user(cb):
            await self._cfg_show_list(cb, is_cb=True, kind="user", page=0)

        async def on_close(cb):
            await self._close_cfg(cb)

        rows.append([
            self.kernel.inline.make_button(self._t("cfg_btn_sys"), on_sys, ttl=600),
            self.kernel.inline.make_button(self._t("cfg_btn_user"), on_user, ttl=600),
        ])
        rows.append([
            self.kernel.inline.make_button(self._t("cfg_close"), on_close, ttl=600),
        ])

        await self._reply_cfg(event_or_cb, is_cb, text, rows)

    async def _cfg_show_list(self, event_or_cb, is_cb: bool = False, kind: str = "system", page: int = 0):
        all_mods = self._cfg_list()
        filtered = [
            m for m in all_mods
            if self._cfg_kind(m) == kind and self._cfg_read(m)
        ]

        per_page = 6
        total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))
        page_mods = filtered[page * per_page:(page + 1) * per_page]

        title_key = "cfg_modules_title_sys" if kind == "system" else "cfg_modules_title_user"
        text = self._t(title_key) + "\n\n"
        if not page_mods:
            text += self._t("cfg_no_modules")
        else:
            text += "<blockquote expandable>"
            for m in page_mods:
                text += f"• <code>{self._esc(m)}</code>\n"
            text += "</blockquote>"

        rows = []

        chunk = []
        for m in page_mods:
            async def on_mod(cb, name=m):
                await self._cfg_show_module(cb, name, is_cb=True)
            chunk.append(self.kernel.inline.make_button(m, on_mod, ttl=600))
            if len(chunk) == 3:
                rows.append(chunk)
                chunk = []
        if chunk:
            rows.append(chunk)

        nav = []
        if page > 0:
            async def on_prev(cb, k=kind, pg=page - 1):
                await self._cfg_show_list(cb, is_cb=True, kind=k, page=pg)
            nav.append(self.kernel.inline.make_button("<", on_prev, ttl=600))

        if total_pages > 1:
            async def on_noop(cb):
                try:
                    await cb.answer()
                except Exception:
                    pass
            nav.append(self.kernel.inline.make_button(
                self._t("cfg_page", page=page + 1, total=total_pages),
                on_noop, ttl=600,
            ))

        if page < total_pages - 1:
            async def on_next(cb, k=kind, pg=page + 1):
                await self._cfg_show_list(cb, is_cb=True, kind=k, page=pg)
            nav.append(self.kernel.inline.make_button(">", on_next, ttl=600))

        if nav:
            rows.append(nav)

        async def on_back(cb):
            await self._cfg_show_menu(cb, is_cb=True)

        async def on_close(cb):
            await self._close_cfg(cb)

        rows.append([
            self.kernel.inline.make_button(self._t("cfg_back"), on_back, ttl=600),
            self.kernel.inline.make_button(self._t("cfg_close"), on_close, ttl=600),
        ])

        await self._reply_cfg(event_or_cb, is_cb, text, rows)

    async def _cfg_show_module(self, event_or_cb, module: str, is_cb: bool = False):
        data = self._cfg_read(module)
        if data is None:
            await event_or_cb.edit(self._t("cfg_not_found", module=self._esc(module)), parse_mode="html")
            return

        if not data:
            lines = self._t("cfg_no_keys")
        else:
            lines = "\n".join(
                self._t("cfg_key_line", key=self._esc(k), value=self._esc(repr(v)))
                for k, v in data.items()
            )

        text = self._t("cfg_module_title", name=self._esc(module)) + "\n\n<blockquote expandable>" + lines + "</blockquote>\n" + self._t("cfg_hint")

        rows = []
        chunk = []
        for k, v in list(data.items())[:20]:
            async def on_edit(cb, m=module, key=k):
                await self._cfg_edit_key(cb, m, key)
            chunk.append(self.kernel.inline.make_button(f"✏️ {k}", on_edit, ttl=600))
            if len(chunk) == 3:
                rows.append(chunk)
                chunk = []
        if chunk:
            rows.append(chunk)

        async def on_back(cb):
            await self._cfg_show_list(cb, is_cb=True)

        async def on_close(cb):
            await self._close_cfg(cb)

        rows.append([
            self.kernel.inline.make_button(self._t("cfg_back"), on_back, ttl=600),
            self.kernel.inline.make_button(self._t("cfg_close"), on_close, ttl=600),
        ])

        await self._reply_cfg(event_or_cb, is_cb, text, rows)

    def _defaults_for(self, module: str, key: str):
        try:
            from pathlib import Path as _P
            import importlib.util
            mod_path = _P("modules") / f"{module}.py"
            if not mod_path.exists():
                mod_path = _P("modules_custom") / f"{module}.py"
            if not mod_path.exists():
                return None
            spec = importlib.util.spec_from_file_location(f"_cfg_def_{module}", mod_path)
            if spec is None or spec.loader is None:
                return None
            m = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(m)
            except Exception:
                return None
            for name in dir(m):
                cls = getattr(m, name)
                if isinstance(cls, type) and isinstance(getattr(cls, "config", None), dict):
                    return cls.config.get(key, None)
        except Exception:
            return None
        return None

    async def _cfg_edit_key(self, cb, module: str, key: str):
        data = self._cfg_read(module)
        if data is None or key not in data:
            await cb.answer(self._t("cfg_key_not_found", key=key))
            return

        value = data[key]
        try:
            await cb.answer()
        except Exception:
            pass

        header = self._t("cfg_edit_title", module=self._esc(module), key=self._esc(key))
        cur = self._t("cfg_key_line", key=self._esc(key), value=self._esc(repr(value)))
        hint = self._t("cfg_inline_hint")
        text = f"{header}\n\n<blockquote>{cur}</blockquote>\n{hint}"

        import secrets as _sec
        token = _sec.token_hex(3)
        if not hasattr(self.kernel, "_cfg_pending"):
            self.kernel._cfg_pending = {}
        self.kernel._cfg_pending[token] = {
            "module": module,
            "key": key,
            "ts": time.time(),
        }

        rows = [
            [{
                "label": self._t("cfg_btn_edit"),
                "kind": "switch_current",
                "query": f"cfg_{token} ",
            }],
        ]

        async def on_reset(c, m=module, k=key, v=value):
            d = self._cfg_read(m) or {}
            default = self._defaults_for(m, k)
            if default is not None:
                d[k] = default
            else:
                if isinstance(v, str):
                    d[k] = ""
                elif isinstance(v, list):
                    d[k] = []
                elif isinstance(v, dict):
                    d[k] = {}
                elif isinstance(v, bool):
                    d[k] = False
                elif isinstance(v, int):
                    d[k] = 0
                elif isinstance(v, float):
                    d[k] = 0.0
            self._cfg_write(m, d)
            await self._cfg_edit_key(c, m, k)

        async def on_back(c, m=module):
            await self._cfg_show_module(c, m, is_cb=True)

        async def on_close(c):
            await self._close_cfg(c)

        rows.append([
            self.kernel.inline.make_button(self._t("cfg_btn_reset"), on_reset, ttl=600),
        ])
        rows.append([
            self.kernel.inline.make_button(self._t("cfg_back"), on_back, ttl=600),
            self.kernel.inline.make_button(self._t("cfg_close"), on_close, ttl=600),
        ])

        await self.kernel.inline.edit(cb, text, rows)

    async def _cfg_set_key(self, cb, module: str, key: str, value):
        data = self._cfg_read(module) or {}
        data[key] = value
        self._cfg_write(module, data)
        await self._cfg_edit_key(cb, module, key)

    async def _cfg_bump(self, cb, module: str, key: str, delta):
        data = self._cfg_read(module) or {}
        if key not in data:
            return
        cur = data[key]
        try:
            if isinstance(cur, bool):
                new = not cur
            elif isinstance(cur, int):
                new = int(cur) + int(delta)
            elif isinstance(cur, float):
                new = round(float(cur) + float(delta), 4)
            else:
                return
        except Exception:
            return
        data[key] = new
        self._cfg_write(module, data)
        await self._cfg_edit_key(cb, module, key)

    async def _close_cfg(self, cb):
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
            log.warning(f"[TEK] close cfg failed: {e}")

    async def _reply_cfg(self, event_or_cb, is_cb: bool, text: str, rows: list):
        if is_cb:
            await self.kernel.inline.edit(event_or_cb, text, rows)
            return
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            await event_or_cb.edit(text, parse_mode="html")
            return
        chat_id = event_or_cb.chat_id
        try:
            await event_or_cb.delete()
        except Exception:
            pass
        await bot.send_inline_menu(
            chat_id=chat_id,
            key=f"cfgmenu_{int(time.time())}",
            text=text,
            buttons=rows,
        )
