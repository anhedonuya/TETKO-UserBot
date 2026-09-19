"""Tek — модули, скрытие, инфо о системе."""
import time
import logging
import sys

from core.tetko import Module, command, db_get, db_set

START_TIME = time.time()
log = logging.getLogger("TETKO.module.tek")

# Премиум-эмодзи
EMOJI_SYS = '<tg-emoji emoji-id="6012473147998084083">🙏</tg-emoji>'
EMOJI_USER = '<tg-emoji emoji-id="5208774197278447727">❤️</tg-emoji>'
EMOJI_Q = '<tg-emoji emoji-id="6010208325843557447">❔</tg-emoji>'
EMOJI_TRASH = '<tg-emoji emoji-id="5348118479847333898">🗑</tg-emoji>'
EMOJI_HEART1 = '<tg-emoji emoji-id="5282797322969852134">❤️</tg-emoji>'
EMOJI_HEART2 = '<tg-emoji emoji-id="5208814909273445904">❤️</tg-emoji>'

# Fallback (без премиума)
FB_SYS = '🔧'
FB_USER = '👤'
FB_Q = '❔'
FB_TRASH = '🗑'

PAGE_SIZE = 10  # модулей на страницу
CMD_LIMIT = 3   # команд показывать


def _lang(kernel) -> str:
    """Определить язык."""
    try:
        lang = kernel.config.get("language", "ru")
        return "en" if lang == "en" else "ru"
    except Exception:
        return "ru"


def _texts(lang: str) -> dict:
    """Строки для ru/en."""
    if lang == "en":
        return {
            "help_title": "Which modules do you need help with?",
            "btn_sys": "system modules",
            "btn_user": "user modules",
            "close": "close tek",
            "back": "back",
            "title": "TETKO",
            "modules_line": "modules: sys m: {sys} | user m: {user}",
            "no_cmds": "(no commands)",
        }
    return {
        "help_title": "С какими модулями тебе нужна помощь?",
        "btn_sys": "систем модули",
        "btn_user": "юзер модули",
        "close": "закрыть список",
        "back": "назад",
        "title": "TETKO",
        "modules_line": "modules: sys m: {sys} | user m: {user}",
        "no_cmds": "(нет команд)",
    }


def _premium(kernel) -> bool:
    """Премиум у владельца?"""
    try:
        return bool(getattr(kernel.context, "user_premium", False))
    except Exception:
        return False


def _parse_folder(name: str) -> str:
    """Определить папку модуля: 'modules' или 'modules_custom'."""
    # пробуем по __file__ модуля
    try:
        mod_obj = None
        # найдём модуль по имени в registry
        for m in getattr(_parse_folder, "_registry", {}).values() if hasattr(_parse_folder, "_registry") else []:
            pass
    except Exception:
        pass
    return ""


class Tek(Module):
    name = "Tek"
    __compat__ = "0.0.9.0"
    version = "2.0.0"
    author = "@anhedonuya & @flexownerAL"
    description = {
        "ru": "Модули, команды, скрытие, инфо",
        "en": "Modules, commands, hiding, info",
    }

    # ── БАЗА ──
    def _get_hidden(self) -> list:
        data = db_get("tek", "hidden", [])
        return list(data) if isinstance(data, list) else []

    def _set_hidden(self, hidden: list):
        db_set("tek", "hidden", list(hidden))

    def _is_system(self, mod) -> bool:
        """Системный модуль? (из modules/)"""
        mod_file = getattr(mod, "__module__", "") or ""
        # если модуль импортирован из modules.tetko_user_modules — попробуем файл
        try:
            import sys as _sys
            from pathlib import Path as _Path
            real_mod = _sys.modules.get(mod_file)
            if real_mod and hasattr(real_mod, "__file__"):
                path = _Path(real_mod.__file__).as_posix()  # универсальный /
                # системный = в modules/, не в modules_custom/
                parts = path.split("/")
                if "modules_custom" in parts:
                    return False
                if "modules" in parts:
                    return True
        except Exception:
            pass
        return False

    def _modules_split(self) -> tuple[list, list]:
        """Вернуть (системные, пользовательские) — без скрытых."""
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
        """Команды модуля."""
        registry = self.kernel.registry
        result = []
        for cmd in registry._commands.values():
            if cmd.module is mod:
                result.append(cmd)
        result.sort(key=lambda c: c.name)
        return result

    def _module_line(self, mod, lang: str) -> str:
        """Строка модуля с командами."""
        cmds = self._cmds_for_module(mod)
        if not cmds:
            t = _texts(lang)
            return f"▫️ <b>{mod.name}</b>: <i>{t['no_cmds']}</i>"

        parts = []
        for i, cmd in enumerate(cmds):
            if i >= CMD_LIMIT:
                parts.append(f"(+{len(cmds) - CMD_LIMIT})")
                break
            s = f"<code>.{cmd.name}</code>"
            if cmd.aliases:
                aliases = ", ".join(f".{a}" for a in cmd.aliases)
                s += f" [<i>{aliases}</i>]"
            parts.append(s)
        return f"▫️ <b>{mod.name}</b>: " + ", ".join(parts)

    # ── ГЛАВНОЕ МЕНЮ ──
    @command(name="tek", description="Модули и команды")
    async def cmd_tek(self, event, args):
        await self._show_help(event)

    async def _show_help(self, event_or_cb, is_cb: bool = False):
        """Главное меню: с какими модулями нужна помощь?"""
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return

        lang = _lang(self.kernel)
        t = _texts(lang)
        premium = _premium(self.kernel)

        # В КНОПКАХ премиум-эмодзи не работают — только обычные
        sys_emoji = FB_SYS
        user_emoji = FB_USER
        q_emoji = EMOJI_Q if premium else FB_Q

        text = f"{t['help_title']} {q_emoji}{q_emoji}"

        # кнопки: система / юзер
        async def on_sys(cb):
            await self._show_list(cb, "system", 0)

        async def on_user(cb):
            await self._show_list(cb, "user", 0)

        buttons = [[
            self.kernel.inline.make_button(f"{sys_emoji} {t['btn_sys']}", on_sys, ttl=600),
            self.kernel.inline.make_button(f"{user_emoji} {t['btn_user']}", on_user, ttl=600),
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

    # ── СПИСОК МОДУЛЕЙ ──
    async def _show_list(self, cb_event, kind: str, page: int):
        """Показать список модулей (kind = 'system' | 'user')."""
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return

        lang = _lang(self.kernel)
        t = _texts(lang)
        premium = _premium(self.kernel)

        sys_mods, user_mods = self._modules_split()
        mods = sys_mods if kind == "system" else user_mods

        total_pages = max(1, (len(mods) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))

        start = page * PAGE_SIZE
        page_mods = mods[start:start + PAGE_SIZE]

        # заголовок
        h1 = EMOJI_HEART1 if premium else "❤️"
        h2 = EMOJI_HEART2 if premium else "❤️"
        text = (
            f"{h1} <b>{t['title']}</b>\n"
            f"{h2} <b>{t['modules_line'].format(sys=len(sys_mods), user=len(user_mods))}</b>\n\n"
            "<blockquote expandable>"
        )
        for mod in page_mods:
            text += self._module_line(mod, lang) + "\n"
        text += "</blockquote>"

        # кнопки пагинации
        rows = []
        nav = []
        if page > 0:
            async def on_prev(cb, k=kind, p=page - 1):
                await self._show_list(cb, k, p)
            nav.append(self.kernel.inline.make_button("<", on_prev, ttl=600))

        # текущая точка
        async def on_noop(cb):
            await cb.answer()
        nav.append(self.kernel.inline.make_button("•", on_noop, ttl=600))

        # страницы (все)
        for i in range(total_pages):
            if i == page:
                continue
            if len(nav) > 6:  # ограничим количество
                break
            async def on_page(cb, k=kind, p=i):
                await self._show_list(cb, k, p)
            nav.append(self.kernel.inline.make_button(str(i + 1), on_page, ttl=600))

        if page < total_pages - 1:
            async def on_next(cb, k=kind, p=page + 1):
                await self._show_list(cb, k, p)
            nav.append(self.kernel.inline.make_button(">", on_next, ttl=600))

        rows.append(nav)

        # назад + закрыть
        async def on_back(cb):
            await self._show_help(cb, is_cb=True)

        async def on_close(cb):
            """Закрыть: отредактировать в "Меню закрыто" и убрать кнопки."""
            try:
                await cb.answer()
            except Exception:
                pass
            # получить imid
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
                    message="🗑 Меню закрыто",
                    reply_markup=None,
                ))
            except Exception as e:
                log.warning(f"[TEK] close edit failed: {e}")

        trash = FB_TRASH
        rows.append([
            self.kernel.inline.make_button(f"← {t['back']}", on_back, ttl=600),
            self.kernel.inline.make_button(f"{trash} {t['close']}", on_close, ttl=600),
        ])

        await self.kernel.inline.edit(cb_event, text, rows)

    # ── СКРЫТИЕ ──
    @command(name="tekhide", description="Скрыть/показать модуль")
    async def cmd_tekhide(self, event, args):
        await self._show_hide(event)

    async def _show_hide(self, event_or_cb, is_cb: bool = False, page: int = 0):
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return

        lang = _lang(self.kernel)
        t = _texts(lang)
        premium = _premium(self.kernel)
        hidden = self._get_hidden()

        registry = self.kernel.registry
        all_mods = sorted(registry._modules.keys())

        total_pages = max(1, (len(all_mods) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start = page * PAGE_SIZE
        page_mods = all_mods[start:start + PAGE_SIZE]

        text = f"<b>Скрытие модулей</b> (стр. {page + 1}/{total_pages})\n\n"
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
                await cb.answer("Обновлено")
                await self._show_hide(cb, is_cb=True, page=p)

            rows.append([self.kernel.inline.make_button(label, on_toggle, ttl=600)])

        # пагинация
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

        # назад + закрыть
        async def on_back(cb):
            await self._show_help(cb, is_cb=True)

        async def on_close(cb):
            """Закрыть: отредактировать в "Меню закрыто" и убрать кнопки."""
            try:
                await cb.answer()
            except Exception:
                pass
            # получить imid
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
                    message="🗑 <i>Меню закрыто</i>",
                    reply_markup=None,
                ))
            except Exception as e:
                log.warning(f"[TEK] close edit failed: {e}")

        trash = FB_TRASH
        rows.append([
            self.kernel.inline.make_button(f"← {t['back']}", on_back, ttl=600),
            self.kernel.inline.make_button(f"{trash} {t['close']}", on_close, ttl=600),
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

    # ── ИНФО О СИСТЕМЕ ──
    @command(name="tekcfg", description="Состояние системы")
    async def cmd_tekcfg(self, event, args):
        uptime = round(time.time() - START_TIME)
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)

        registry = self.kernel.registry
        total_mods = len(registry._modules)
        total_cmds = len(registry._commands)
        premium = _premium(self.kernel)

        text = (
            "<b>❤️ TETKO — System</b>\n\n"
            f"⏱ <b>Uptime:</b> <code>{hours}ч {minutes}м {seconds}с</code>\n"
            f"📦 <b>Модулей:</b> <code>{total_mods}</code>\n"
            f"⌨️ <b>Команд:</b> <code>{total_cmds}</code>\n"
            f"🐍 <b>Python:</b> <code>{sys.version.split()[0]}</code>\n"
            "⚡ <b>Стиль:</b> <code>tetko-compat 0.0.9.0</code>\n"
            f"👑 <b>Premium:</b> <code>{premium}</code>\n"
            "👥 <b>Авторы:</b> @anhedonuya, @flexownerAL"
        )
        await event.edit(text, parse_mode="html")
