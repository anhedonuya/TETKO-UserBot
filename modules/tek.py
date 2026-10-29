# SPDX-License-Identifier: MIT
# TETKO-UserBot
# Authors: @anhedonuya, @flexOwnerAL
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from html import escape
from typing import Any
from urllib.parse import urlparse

from telethon.errors import BadRequestError
from telethon.tl.types import (
    DocumentAttributeImageSize,
    InputMediaWebPage,
    InputWebDocument,
)

from core.tetko import Module, command, shell

CUSTOM_EMOJI = {
    "crystal": '<tg-emoji emoji-id="5332762073388578651">🎮</tg-emoji>',
    "dna": '<tg-emoji emoji-id="5332762073388578651">❔</tg-emoji>',
    "alembic": '<tg-emoji emoji-id="5411243692960810848">🤔</tg-emoji>',
    "snowflake": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "blocked": '<tg-emoji emoji-id="5332439413970469607">🚫</tg-emoji>',
    "confused": '<tg-emoji emoji-id="5408830797513784663">❓</tg-emoji>',
    "map": '<tg-emoji emoji-id="5332373172689860602">🚫</tg-emoji>',
    "tot": '<tg-emoji emoji-id="5404696015318054899">▪️</tg-emoji>',
    "eye_off": '<tg-emoji emoji-id="5228686859663585439">👁</tg-emoji>',
    "bot": '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>',
}

CUSTOM_EMOJI.update({
    "📁": '<tg-emoji emoji-id="5433653135799228968">📁</tg-emoji>',
    "📝": '<tg-emoji emoji-id="5334882760735598374">📝</tg-emoji>',
    "📚": '<tg-emoji emoji-id="5373098009640836781">📚</tg-emoji>',
    "📖": '<tg-emoji emoji-id="5226512880362332956">📖</tg-emoji>',
    "💼": '<tg-emoji emoji-id="5359785904535774578">💼</tg-emoji>',
    "☑️": '<tg-emoji emoji-id="5454096630372379732">☑️</tg-emoji>',
    "➕": '<tg-emoji emoji-id="5226945370684140473">➕</tg-emoji>',
    "➖": '<tg-emoji emoji-id="5229113891081956317">➖</tg-emoji>',
    "✏️": '<tg-emoji emoji-id="5334673106202010226">✏️</tg-emoji>',
    "❄️": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "🗂": '<tg-emoji emoji-id="5431736674147114227">🗂</tg-emoji>',
    "📋": '<tg-emoji emoji-id="5431736674147114227">📋</tg-emoji>',
    "⚙️": '<tg-emoji emoji-id="5332654441508119011">⚙️</tg-emoji>',
    "🔢": '<tg-emoji emoji-id="5465154440287757794">🔢</tg-emoji>',
    "🔙": '<tg-emoji emoji-id="5332600281970517875">🔙</tg-emoji>',
    "✅": '<tg-emoji emoji-id="5118861066981344121">✅</tg-emoji>',
    "❌": '<tg-emoji emoji-id="5370843963559254781">❌</tg-emoji>',
    "🔄": '<tg-emoji emoji-id="5332600281970517875">🔄</tg-emoji>',
    "🧩": '<tg-emoji emoji-id="5359785904535774578">🧩</tg-emoji>',
    "🔧": '<tg-emoji emoji-id="5332654441508119011">🔧</tg-emoji>',
    "🗳": '<tg-emoji emoji-id="5359741159566484212">🗳</tg-emoji>',
    "📎": '<tg-emoji emoji-id="5377844313575150051">📎</tg-emoji>',
    "💬": '<tg-emoji emoji-id="5465300082628763143">💬</tg-emoji>',
    "🗯": '<tg-emoji emoji-id="5465132703458270101">🗯</tg-emoji>',
    "📰": '<tg-emoji emoji-id="5433982607035474385">📰</tg-emoji>',
    "🔍": '<tg-emoji emoji-id="5429283852684124412">🔍</tg-emoji>',
    "🧊": '<tg-emoji emoji-id="5404728536810398694">🧊</tg-emoji>',
})

ZERO_WIDTH_CHAR = "\u2060"

TYPE_EMOJIS = {
    "str": "📝",
    "int": "🔢",
    "float": "🔢",
    "bool": "☑️",
    "list": "📚",
    "dict": "🗂",
    "NoneType": "🗳",
    "hidden": "🔒",
}
LONG_VALUE_BLOCKQUOTE_LIMIT = 300


def _truncate_key(key, max_length=15):
    if len(key) > max_length:
        return key[: max_length - 3] + "..."
    return key


def _format_key_value(key, value, reveal=False):
    value_type = type(value).__name__
    type_emoji = TYPE_EMOJIS.get(value_type, "📎")
    if isinstance(value, (dict, list)):
        try:
            formatted = json.dumps(value, ensure_ascii=False, indent=2)
        except Exception:
            formatted = str(value)
        display = "<pre>%s</pre>" % escape(formatted)
        if len(formatted) > LONG_VALUE_BLOCKQUOTE_LIMIT:
            display = "<blockquote expandable>%s</blockquote>" % display
    elif value is None:
        display = "<code>null</code>"
        type_emoji = TYPE_EMOJIS.get("NoneType", "🗳")
    elif isinstance(value, bool):
        display = "✔️ <code>true</code>" if value else "✖️ <code>false</code>"
    elif isinstance(value, str):
        escaped = escape(value)
        display = "<code>%s</code>" % escaped
        if len(value) > LONG_VALUE_BLOCKQUOTE_LIMIT:
            display = "<blockquote expandable>%s</blockquote>" % display
    else:
        raw = str(value)
        display = "<code>%s</code>" % escape(raw)
        if len(raw) > LONG_VALUE_BLOCKQUOTE_LIMIT:
            display = "<blockquote expandable>%s</blockquote>" % display
    return type_emoji, value_type, display


def esc(t):
    if t is None:
        return "-"
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _normalize_http_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    url = value.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def _is_webpage_url_invalid_error(error: BaseException) -> bool:
    if not isinstance(error, BadRequestError):
        return False
    message = getattr(error, "message", "") or str(error)
    return "WEBPAGE_URL_INVALID" in str(message)


def _make_thumb(url: str) -> InputWebDocument:
    return InputWebDocument(
        url=url,
        size=0,
        mime_type="image/jpeg",
        attributes=[DocumentAttributeImageSize(w=0, h=0)],
    )



def _tl_buttons(rows, kernel):
    from telethon import Button
    out = []
    for row in rows:
        tl_row = []
        for b in row:
            if not isinstance(b, dict) or "token" not in b:
                continue
            token = b["token"]
            if isinstance(token, str):
                token = token.encode("utf-8")
            if len(token) > 64:
                token = token[:64]
            tl_row.append(Button.inline(b.get("label", "?"), data=token))
        if tl_row:
            out.append(tl_row)
    return out or None


CUSTOM_EMOJI.clear()

class Tek(Module):

    def _cfg_format_value(self, key, value):
        value_type = type(value).__name__
        type_emoji = {
            "str": "📝", "int": "🔢", "float": "🔢", "bool": "☑️",
            "list": "📚", "dict": "🗂", "NoneType": "🗳", "hidden": "🔒",
        }.get(value_type, "📎")
        if isinstance(value, (dict, list)):
            try:
                formatted_value = json.dumps(value, ensure_ascii=False, indent=2)
            except Exception:
                formatted_value = str(value)
            display_value = "<pre>%s</pre>" % esc(formatted_value)
            if len(formatted_value) > 300:
                display_value = "<blockquote expandable>%s</blockquote>" % display_value
        elif value is None:
            display_value = "<code>null</code>"
        elif isinstance(value, bool):
            display_value = "✔️ <code>true</code>" if value else "✖️ <code>false</code>"
        elif isinstance(value, str):
            escaped_value = esc(value)
            display_value = "<code>%s</code>" % escaped_value
            if len(value) > 300:
                display_value = "<blockquote expandable>%s</blockquote>" % display_value
        else:
            raw_value = str(value)
            display_value = "<code>%s</code>" % esc(raw_value)
            if len(raw_value) > 300:
                display_value = "<blockquote expandable>%s</blockquote>" % display_value
        return type_emoji, value_type, display_value

    def _cfg_truncate_key(self, key, max_length=15):
        if len(key) > max_length:
            return key[: max_length - 3] + "..."
        return key

    def _cfg_truncate_module(self, name, max_length=12):
        if len(name) > max_length:
            return name[: max_length - 3] + "..."
        return name
    name = "Tek"
    __compat__ = "0.0.9.0"
    version = "2.2.0"
    author = "@anhedonuya & @flexOwnerAL"
    description = {
        "ru": "Модули, команды, скрытие, инфо",
        "en": "Modules, commands, hiding, info",
    }

    config = {
        "banner_url": "",
        "invert_media": True,
        "quote_media": True,
        "modules_per_page": 10,
        "emoji_system": "▫️",
        "emoji_user": "▪️",
        "emoji_no_cmd": "❔",
        "emoji_error": "🚫",
        "emoji_tot": "▪️",
    }

    config_sections = {
        "View": ["banner_url", "invert_media", "quote_media", "modules_per_page"],
        "Emoji": ["emoji_system", "emoji_user", "emoji_no_cmd", "emoji_error", "emoji_tot"],
    }

    config_schema = {
        "banner_url": {"type": "str", "description": "Banner URL"},
        "invert_media": {"type": "bool", "description": "Invert media"},
        "quote_media": {"type": "bool", "description": "Send media in quotes"},
        "modules_per_page": {"type": "int", "description": "Modules per page"},
        "emoji_system": {"type": "str", "description": "System module emoji"},
        "emoji_user": {"type": "str", "description": "User module emoji"},
        "emoji_no_cmd": {"type": "str", "description": "No commands emoji"},
        "emoji_error": {"type": "str", "description": "Error emoji"},
        "emoji_tot": {"type": "str", "description": "List bullet emoji"},
    }

    def _repair_config(self) -> None:
        try:
            cur = self.cfg.get("modules_per_page", 10)
            cur = int(cur)
            cur = max(1, min(50, cur))
            self.cfg.set("modules_per_page", cur)
        except Exception:
            try:
                self.cfg.set("modules_per_page", 10)
            except Exception:
                pass

    async def on_load(self) -> None:
        self._repair_config()


    _CAT_EMOJI = {
        "model": "🧠", "behavior": "🎭", "tools": "🛠", "tool": "🛠",
        "session": "💬", "style": "🎨", "view": "👁", "emoji": "😀",
        "hidden": "🙈", "other": "📦", "plugins": "🔌", "android": "📱",
        "gateway": "🌐", "files": "📂", "interface": "🖼", "core": "⚙",
        "context": "🧩", "prompt": "📝", "general": "⚙", "chat": "💬",
        "network": "🌐", "logging": "📋", "memory": "🧠", "security": "🔒",
    }

    def _cat_emoji(self, name):
        key = (name or "").strip().lower()
        return self._CAT_EMOJI.get(key, "📂")

    def _val_emoji(self, v, has_options=False):
        if has_options:
            return "🎯"
        if isinstance(v, bool):
            return "🟢" if v else "🔴"
        if isinstance(v, int):
            return "🔢"
        if isinstance(v, float):
            return "🔣"
        if isinstance(v, list):
            return "📋"
        if isinstance(v, dict):
            return "🗂"
        if isinstance(v, str):
            return "✏️"
        if v is None:
            return "∅"
        return "⚙"

    def _tl(self, rows):
        if not rows:
            return None
        try:
            from telethon.tl.types import (
                KeyboardButtonCallback, KeyboardButtonStyle, KeyboardButtonRow,
                ReplyInlineMarkup,
            )
            _STYLES = {
                "primary": KeyboardButtonStyle(bg_primary=True),
                "success": KeyboardButtonStyle(bg_success=True),
                "danger": KeyboardButtonStyle(bg_danger=True),
            }
            out = []
            for row in rows:
                tl_row = []
                for b in row:
                    if not isinstance(b, dict) or "token" not in b:
                        continue
                    tok = b["token"]
                    if isinstance(tok, str):
                        tok = tok.encode("utf-8")
                    if len(tok) > 64:
                        tok = tok[:64]
                    label = b.get("label", "?")
                    style_name = b.get("style", "")
                    style = _STYLES.get(style_name)
                    if style is not None:
                        tl_row.append(KeyboardButtonCallback(text=label, data=tok, style=style))
                    else:
                        tl_row.append(KeyboardButtonCallback(text=label, data=tok))
                if tl_row:
                    out.append(KeyboardButtonRow(buttons=tl_row))
            if not out:
                return None
            return ReplyInlineMarkup(rows=out)
        except Exception:
            return None

    def _get_bot_command_description(self, docs, lang: str) -> str:
        if isinstance(docs, str):
            return docs.strip()
        if not isinstance(docs, dict) or not docs:
            return ""
        for locale in (lang, "ru", "en"):
            v = docs.get(locale)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in docs.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _get_bot_commands(self, module_name: str):
        try:
            owners = getattr(self.kernel, "bot_command_owners", {}) or {}
            docs_by = getattr(self.kernel, "bot_command_docs", {}) or {}
            if not isinstance(owners, dict):
                return []
            lang = self._get_lang()
            wanted = module_name.lower()
            out = []
            for cmd, owner in owners.items():
                owner_name = getattr(owner, "name", owner)
                if str(owner_name).lower() != wanted:
                    continue
                cname = str(cmd).strip().lstrip("/")
                if not cname:
                    continue
                desc = self._get_bot_command_description(docs_by.get(cmd, {}), lang)
                out.append((cname, desc))
            return out
        except Exception:
            return []

    def _get_module_commands(self, module_name: str):
        try:
            reg = self.kernel.registry
            mod = None
            for n, m in reg._modules.items():
                if n.lower() == module_name.lower():
                    mod = m
                    break
            if mod is None:
                return {}, {}, {}
            cmds = {}
            aliases = {}
            descs = {}
            for cmd in reg._commands.values():
                if getattr(cmd, "module", None) is mod:
                    cmds[cmd.name] = True
                    if cmd.aliases:
                        aliases[cmd.name] = list(cmd.aliases)
                    if cmd.doc:
                        descs[cmd.name] = str(cmd.doc)
            return cmds, aliases, descs
        except Exception:
            return {}, {}, {}

    async def _load_module_metadata(self, name: str, mod) -> dict:
        fallback = {
            "version": getattr(mod, "version", "?.?.?"),
            "author": getattr(mod, "author", "?"),
            "description": "-",
            "description_i18n": {},
            "banner_url": None,
        }
        try:
            version = getattr(mod, "version", None)
            if isinstance(version, str) and version.strip():
                fallback["version"] = version.strip()
            author = getattr(mod, "author", None)
            if isinstance(author, str) and author.strip():
                fallback["author"] = author.strip()
            desc = getattr(mod, "description", None)
            if isinstance(desc, dict):
                fallback["description_i18n"] = desc
                lang = self._get_lang()
                fallback["description"] = desc.get(lang) or desc.get("ru") or desc.get("en") or next(iter(desc.values()), "-")
            elif isinstance(desc, str) and desc.strip():
                fallback["description"] = desc.strip()
            for attr in ("banner_url", "banner", "image", "photo"):
                b = getattr(mod, attr, None)
                if isinstance(b, str) and b.strip():
                    fallback["banner_url"] = b.strip()
                    break
        except Exception:
            pass
        return fallback

    def _get_lang(self) -> str:
        try:
            cfg = getattr(self.kernel, "config", None) or {}
            return cfg.get("language", "ru") or "ru"
        except Exception:
            return "ru"

    async def _build_module_detail(self, mod) -> tuple:
        name = getattr(mod, "name", "?")
        is_sys = self._is_system(mod)
        meta = await self._load_module_metadata(name, mod)
        cmds, aliases, descs = self._get_module_commands(name)

        lang = self._get_lang()
        i18n = meta.get("description_i18n") or {}
        desc_text = i18n.get(lang) or i18n.get("ru") or i18n.get("en") or meta.get("description") or "-"

        header_emoji = CUSTOM_EMOJI.get("dna")
        author_emoji = CUSTOM_EMOJI.get("alembic")
        tot = CUSTOM_EMOJI.get("tot")
        confused = CUSTOM_EMOJI.get("confused")
        no_cmd = CUSTOM_EMOJI.get("snowflake")

        version = meta.get("version", "?")
        author = meta.get("author", "?")
        kind = "core" if is_sys else "user"

        parts = []
        parts.append('<p>%s <b>%s</b> <i>(v%s)</i></p>' % (header_emoji, esc(name), esc(str(version))))
        if desc_text and desc_text != "-":
            parts.append('<blockquote expandable>%s <i>%s</i></blockquote>' % (author_emoji, esc(desc_text)))
        parts.append('<blockquote>%s <i>kind: %s</i></blockquote>' % (tot, esc(kind)))

        if cmds:
            lines = []
            _prefix = getattr(self.kernel, "prefix", ".") or "."
            for cname in cmds:
                cdesc = descs.get(cname) or "%s no description" % confused
                line = "%s <code>%s%s</code> - <b>%s</b>" % (tot, esc(_prefix), esc(cname), esc(str(cdesc)))
                if cname in aliases:
                    al = aliases[cname]
                    if isinstance(al, str):
                        al = [al]
                    if al:
                        line += " | aliases: " + ", ".join("<code>%s%s</code>" % (esc(_prefix), esc(a)) for a in al)
                lines.append(line)
            parts.append('<blockquote expandable>%s</blockquote>' % chr(10).join(lines))
        else:
            parts.append('<blockquote>%s <i>no commands</i></blockquote>' % no_cmd)

        bot_cmds = self._get_bot_commands(name)
        if bot_cmds:
            bot_emoji = CUSTOM_EMOJI.get("bot")
            lines = []
            for cname, cdesc in bot_cmds:
                line = "%s <code>/%s</code>" % (bot_emoji, esc(cname))
                if cdesc:
                    line += " - <b>%s</b>" % esc(cdesc)
                lines.append(line)
            parts.append('<blockquote expandable>%s</blockquote>' % chr(10).join(lines))

        parts.append('<blockquote>%s <b>author:</b> <i>%s</i></blockquote>' % (author_emoji, esc(str(author))))

        text = chr(10).join(parts)
        banner = _normalize_http_url(meta.get("banner_url") or "")
        return text, banner

    def _add_banner_preview(self, text: str, banner_url: str) -> str:
        if not banner_url:
            return text
        return '<a href="%s">%s</a>%s' % (escape(banner_url, quote=True), ZERO_WIDTH_CHAR, text)

    async def _edit_with_banner(self, event_or_cb, text: str, banner_url: str):
        banner_url = _normalize_http_url(banner_url)
        if not banner_url:
            try:
                return await event_or_cb.edit(text, parse_mode="html")
            except Exception as e:
                self.log.warning("edit failed: %s", e)
                return None
        try:
            return await event_or_cb.edit(
                self._add_banner_preview(text, banner_url),
                parse_mode="html",
                file=InputMediaWebPage(banner_url, optional=True),
                invert_media=bool(self.cfg.get("invert_media", True)),
            )
        except BadRequestError as e:
            if _is_webpage_url_invalid_error(e):
                try:
                    return await event_or_cb.edit(text, parse_mode="html")
                except Exception as _e:
                    self.log.warning("edit no banner failed: %s", _e)
                    return None
            self.log.warning("edit banner failed: %s", e)
            return None
        except TypeError:
            try:
                return await event_or_cb.edit(text, parse_mode="html")
            except Exception as _e:
                self.log.warning("edit fallback failed: %s", _e)
                return None
        except Exception as e:
            self.log.warning("edit banner unexpected: %s", e)
            return None

    def _get_paginated_data(self, page: int, mods_sys, mods_user, page_cb=None, close_cb=None, ttl: int = 900):
        sys_mods = sorted(mods_sys, key=lambda m: getattr(m, "name", ""))
        usr_mods = sorted(mods_user, key=lambda m: getattr(m, "name", ""))
        try:
            per_page = int(self.cfg.get("modules_per_page", 10))
        except Exception:
            per_page = 10
        per_page = max(1, min(50, per_page))

        usr_chunks = [usr_mods[i: i + per_page] for i in range(0, len(usr_mods), per_page)] or [[]]
        total_pages = max(1, len(usr_chunks))
        page = max(0, min(page, total_pages - 1))

        emoji_sys = self.cfg.get("emoji_system") or "▫️"
        emoji_usr = self.cfg.get("emoji_user") or "▪️"
        emoji_no = self.cfg.get("emoji_no_cmd") or "❔"

        def line_for(mod) -> str:
            name = getattr(mod, "name", "?")
            icon = getattr(mod, "icon", None) or "◼"
            is_sys = self._is_system(mod)
            emoji = emoji_sys if is_sys else emoji_usr
            cmds, _, _ = self._get_module_commands(name)
            _prefix = getattr(self.kernel, "prefix", ".") or "."
            if cmds:
                names = list(cmds.keys())[:3]
                cmd_text = ", ".join("<code>%s%s</code>" % (esc(_prefix), esc(c)) for c in names)
                if len(cmds) > 3:
                    cmd_text += " (+%d)" % (len(cmds) - 3)
                return "%s %s <code>%s</code>: %s" % (emoji, icon, esc(name), cmd_text)
            return "%s %s <code>%s</code>: <i>%s</i>" % (emoji_no, icon, esc(name), "no commands")

        if page == 0:
            parts = ["<p>modules: sys <code>%d</code> | user <code>%d</code></p>" % (len(sys_mods), len(usr_mods))]
            if sys_mods:
                parts.append("<blockquote expandable>%s</blockquote>" % chr(10).join(line_for(m) for m in sys_mods))
            if usr_chunks[0]:
                parts.append("<blockquote expandable>%s</blockquote>" % chr(10).join(line_for(m) for m in usr_chunks[0]))
        else:
            parts = ["<p><b>page %d / %d</b></p>" % (page + 1, total_pages)]
            parts.append("<blockquote expandable>%s</blockquote>" % chr(10).join(line_for(m) for m in usr_chunks[page]))

        buttons = []
        page_row = []
        if page_cb is not None:
            page_row.append(self.kernel.inline.make_button("<", page_cb, args=[max(0, page - 1)], ttl=ttl))
            if total_pages <= 7:
                for i in range(total_pages):
                    label = "•" if i == page else str(i + 1)
                    page_row.append(self.kernel.inline.make_button(label, page_cb, args=[i], ttl=ttl))
            else:
                page_row.append(self.kernel.inline.make_button(str(page + 1), page_cb, args=[page], ttl=ttl))
            page_row.append(self.kernel.inline.make_button(">", page_cb, args=[min(total_pages - 1, page + 1)], ttl=ttl))
            buttons.append(page_row)
        if close_cb is not None:
            buttons.append([self.kernel.inline.make_button("❌ close", close_cb, ttl=ttl)])

        return chr(10).join(parts), buttons

    async def _tek_page_cb(self, cb_event, page: int):
        try:
            await cb_event.answer()
        except Exception:
            pass
        sys_mods, usr_mods = self._modules_split()
        text, buttons = self._get_paginated_data(page, sys_mods, usr_mods, page_cb=self._tek_page_cb, close_cb=self._tek_close_cb)
        banner = _normalize_http_url(self.cfg.get("banner_url") or "")
        try:
            if banner:
                await cb_event.edit(
                    self._add_banner_preview(text, banner),
                    buttons=self._tl(buttons),
                    parse_mode="html",
                    file=InputMediaWebPage(banner, optional=True),
                    invert_media=bool(self.cfg.get("invert_media", True)),
                )
            else:
                await cb_event.edit(text, buttons=self._tl(buttons), parse_mode="html")
        except Exception as e:
            self.log.warning("page cb edit failed: %s", e)

    async def _tek_close_cb(self, cb_event):
        try:
            await cb_event.answer()
        except Exception:
            pass
        try:
            await cb_event.delete()
        except Exception as e:
            self.log.warning("close cb failed: %s", e)

    def _is_system(self, mod) -> bool:
        name = getattr(mod, "name", "") or ""
        if not name:
            return True
        try:
            from pathlib import Path
            if (Path("modules_custom") / (name + ".py")).exists():
                return False
        except Exception:
            pass
        return True

    def _modules_split(self):
        sys_mods = []
        usr_mods = []
        hidden = set(self._get_hidden())
        try:
            reg = self.kernel.registry
            all_mods = getattr(reg, "_modules", {}) or {}
            for name, mod in all_mods.items():
                if name in hidden:
                    continue
                try:
                    is_sys = self._is_system(mod)
                except Exception:
                    is_sys = False
                if is_sys:
                    sys_mods.append(mod)
                else:
                    usr_mods.append(mod)
        except Exception as e:
            self.log.warning("modules_split failed: %s", e)
        return sys_mods, usr_mods

    def _modules_split_all(self):
        sys_mods, usr_mods = self._modules_split()
        return {"core": sys_mods, "user": usr_mods, "all": sys_mods + usr_mods}

    def _cmds_for_module(self, mod):
        try:
            reg = self.kernel.registry
            return [c for c in reg._commands.values() if getattr(c, "module", None) is mod]
        except Exception:
            return []

    @command(name="tek", description="Modules and commands list")
    async def cmd_tek(self, event, args):
        if args:
            await self._show_module(event, args[0])
            return
        await self._show_help(event)

    async def _show_help(self, event):
        sys_mods, usr_mods = self._modules_split()
        text, _ = self._get_paginated_data(0, sys_mods, usr_mods)
        banner = _normalize_http_url(self.cfg.get("banner_url") or "")
        if banner:
            try:
                await event.edit(
                    self._add_banner_preview(text, banner),
                    parse_mode="html",
                    file=InputMediaWebPage(banner, optional=True),
                    invert_media=bool(self.cfg.get("invert_media", True)),
                )
                return
            except Exception as e:
                self.log.warning("show_help banner failed: %s", e)
        try:
            await event.edit(text, parse_mode="html")
        except Exception as e:
            self.log.warning("show_help failed: %s", e)

    async def _show_module(self, event, query: str):
        mod = self._find_module(query)
        if mod is None:
            err = self.cfg.get("emoji_error") or "🚫"
            try:
                await event.edit("%s <b>module not found:</b> <code>%s</code>" % (err, esc(query)), parse_mode="html")
            except Exception:
                pass
            return
        text, banner = await self._build_module_detail(mod)
        if banner:
            try:
                await event.edit(
                    self._add_banner_preview(text, banner),
                    parse_mode="html",
                    file=InputMediaWebPage(banner, optional=True),
                    invert_media=bool(self.cfg.get("invert_media", True)),
                )
                return
            except Exception as e:
                self.log.warning("show_module banner failed: %s", e)
        try:
            await event.edit(text, parse_mode="html")
        except Exception as e:
            self.log.warning("show_module failed: %s", e)

    def _find_module(self, name: str):
        try:
            reg = self.kernel.registry
            for n, m in reg._modules.items():
                if n.lower() == name.lower():
                    return m
            return None
        except Exception:
            return None

    def _get_hidden(self) -> list:
        try:
            raw = self.cfg.get("hidden_modules") or []
            if isinstance(raw, str):
                return json.loads(raw)
            if isinstance(raw, list):
                return list(raw)
        except Exception:
            pass
        return []

    def _save_hidden(self, hidden: list) -> None:
        try:
            self.cfg.set("hidden_modules", hidden)
        except Exception:
            pass

    @command(name="tekhide", description="Hide module from tek list")
    async def cmd_tekhide(self, event, args):
        if not args:
            try:
                await event.edit("<b>tekhide</b>\n<blockquote>usage: <code>?tekhide &lt;module&gt;</code></blockquote>", parse_mode="html")
            except Exception:
                pass
            return
        target = args[0].strip()
        mod = self._find_module(target)
        if mod is None:
            err = self.cfg.get("emoji_error") or "🚫"
            try:
                await event.edit("%s <b>module not found:</b> <code>%s</code>" % (err, esc(target)), parse_mode="html")
            except Exception:
                pass
            return
        name = getattr(mod, "name", target)
        hidden = self._get_hidden()
        if name in hidden:
            try:
                await event.edit("<b>tekhide</b>\n<blockquote>already hidden: <code>%s</code></blockquote>" % esc(name), parse_mode="html")
            except Exception:
                pass
            return
        hidden.append(name)
        self._save_hidden(hidden)
        try:
            await event.edit("<b>tekhide</b>\n<blockquote>hidden: <code>%s</code></blockquote>" % esc(name), parse_mode="html")
        except Exception:
            pass

    @command(name="tekunhide", description="Unhide module from tek list")
    async def cmd_tekunhide(self, event, args):
        if not args:
            try:
                await event.edit("<b>tekunhide</b>\n<blockquote>usage: <code>?tekunhide &lt;module&gt;</code></blockquote>", parse_mode="html")
            except Exception:
                pass
            return
        target = args[0].strip()
        hidden = self._get_hidden()
        match = None
        for n in hidden:
            if n.lower() == target.lower():
                match = n
                break
        if match is None:
            try:
                await event.edit("<b>tekunhide</b>\n<blockquote>not hidden: <code>%s</code></blockquote>" % esc(target), parse_mode="html")
            except Exception:
                pass
            return
        hidden.remove(match)
        self._save_hidden(hidden)
        try:
            await event.edit("<b>tekunhide</b>\n<blockquote>unhidden: <code>%s</code></blockquote>" % esc(match), parse_mode="html")
        except Exception:
            pass

    @command(name="tekhide_list", aliases=["tekhidden"], description="List hidden modules")
    async def cmd_tekhide_list(self, event, args):
        hidden = self._get_hidden()
        if not hidden:
            try:
                await event.edit("<b>tekhide</b>\n<blockquote>no hidden modules</blockquote>", parse_mode="html")
            except Exception:
                pass
            return
        lines = ["<b>hidden modules (%d)</b>" % len(hidden), "<blockquote expandable>"]
        for n in hidden:
            lines.append("<code>%s</code>" % esc(n))
        lines.append("</blockquote>")
        try:
            await event.edit(chr(10).join(lines), parse_mode="html")
        except Exception:
            pass

    def _cfg_data(self, module_name: str) -> dict:
        try:
            from pathlib import Path
            p = Path("data/tetko_config") / (module_name + ".json")
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
        return {}

    def _cfg_save(self, module_name: str, data: dict) -> None:
        try:
            from pathlib import Path
            p = Path("data/tetko_config") / (module_name + ".json")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            reg = self.kernel.registry
            for name, mod in reg._modules.items():
                if name == module_name:
                    mc = getattr(mod, "_config", None)
                    if mc is not None and hasattr(mc, "_load"):
                        mc._load()
                    break
        except Exception:
            pass

    def _cfg_schema(self, module_name: str) -> dict:
        try:
            reg = self.kernel.registry
            for name, mod in reg._modules.items():
                if name == module_name:
                    sc = getattr(mod, "config_schema", None)
                    if isinstance(sc, dict):
                        return sc
                    break
        except Exception:
            pass
        return {}

    def _cfg_sections(self, module_name: str) -> dict:
        try:
            reg = self.kernel.registry
            for name, mod in reg._modules.items():
                if name == module_name:
                    sc = getattr(mod, "config_sections", None)
                    if isinstance(sc, dict):
                        return sc
                    break
        except Exception:
            pass
        return {}

    def _cfg_default(self, module_name: str, key: str):
        try:
            reg = self.kernel.registry
            for name, mod in reg._modules.items():
                if name == module_name:
                    defaults = getattr(mod, "config", None)
                    if isinstance(defaults, dict) and key in defaults:
                        return defaults[key]
                    break
        except Exception:
            pass
        return None

    def _cfg_get(self, module_name: str):
        cfg = self._cfg_data(module_name)
        if not cfg:
            return None, None
        sections = self._cfg_sections(module_name)
        if sections:
            used = set()
            cats = []
            for sec, keys in sections.items():
                present = [k for k in keys if k in cfg and k not in used]
                if present:
                    cats.append((sec, present))
                    used.update(present)
            rest = [k for k in cfg.keys() if k not in used]
            if rest:
                cats.append(("Other", rest))
            return cfg, cats
        buckets = {"Flags": [], "Values": [], "Collections": [], "Other": []}
        for k, v in cfg.items():
            if isinstance(v, bool):
                buckets["Flags"].append(k)
            elif isinstance(v, (list, dict)):
                buckets["Collections"].append(k)
            elif isinstance(v, (str, int, float)):
                buckets["Values"].append(k)
            else:
                buckets["Other"].append(k)
        cats = [(sec, keys) for sec, keys in buckets.items() if keys]
        return cfg, cats

    def _cfg_val(self, v, limit=80):
        if isinstance(v, bool):
            return "on" if v else "off"
        if v is None:
            return "null"
        if isinstance(v, (list, dict)):
            try:
                js = json.dumps(v, ensure_ascii=False)
            except Exception:
                js = str(v)
            return js[:limit] + ("..." if len(js) > limit else "")
        s = str(v)
        return s[:limit] + ("..." if len(s) > limit else "")

    def _cfg_parse(self, raw):
        low = str(raw).strip().lower()
        if low in ("true", "yes", "on", "1"):
            return True
        if low in ("false", "no", "off", "0"):
            return False
        if low in ("null", "none"):
            return None
        try:
            return int(raw)
        except Exception:
            pass
        try:
            return float(raw)
        except Exception:
            pass
        if str(raw).startswith("[") or str(raw).startswith("{"):
            try:
                return json.loads(raw)
            except Exception:
                pass
        return raw

    async def _cfg_menu(self, event_or_cb, is_cb: bool = False):
        sys_mods_all, usr_mods_all = self._modules_split()
        sys_mods = [m for m in sys_mods_all if self._cfg_data(getattr(m, "name", ""))]
        usr_mods = [m for m in usr_mods_all if self._cfg_data(getattr(m, "name", ""))]
        text = (
            "<p>%s <b>Config Menu</b></p>"
            "<blockquote>sys <code>%d</code> · user <code>%d</code></blockquote>"
        ) % (CUSTOM_EMOJI.get("📋", "📋"), len(sys_mods), len(usr_mods))

        async def on_sys(c):
            await self._cfg_list(c, "core", 0)
        async def on_usr(c):
            await self._cfg_list(c, "user", 0)
        async def on_all(c):
            await self._cfg_list(c, "all", 0)
        async def on_close(c):
            await self._tek_close_cb(c)

        buttons = [
            [
                self.kernel.inline.make_button("%s system (%d)" % (CUSTOM_EMOJI.get("📦", "📦"), len(sys_mods)), on_sys, ttl=900, style="primary"),
                self.kernel.inline.make_button("%s user (%d)" % (CUSTOM_EMOJI.get("🔧", "🔧"), len(usr_mods)), on_usr, ttl=900, style="success"),
            ],
            [
                self.kernel.inline.make_button("%s all" % CUSTOM_EMOJI.get("🧩", "🧩"), on_all, ttl=900, style="primary"),
            ],
            [self.kernel.inline.make_button("Close", on_close, ttl=900, style="danger")],
        ]

        if is_cb:
            try:
                await event_or_cb.edit(text, buttons=self._tl(buttons), parse_mode="html")
            except Exception as e:
                self.log.warning("cfg menu edit: %s", e)
            return

        bot = getattr(self.kernel, "bot_client", None)
        if bot is not None:
            try:
                await bot.send_inline_menu(event_or_cb.chat_id, "tek_cfg_" + str(int(time.time())), text, buttons)
                try:
                    await event_or_cb.delete()
                except Exception:
                    pass
                return
            except Exception as e:
                self.log.warning("cfg menu send: %s", e)
        try:
            await event_or_cb.edit(text, parse_mode="html")
        except Exception:
            pass

    async def _cfg_list(self, cb, kind: str = "all", page: int = 0):
        sys_mods, usr_mods = self._modules_split()
        if kind == "core":
            mods = sys_mods
        elif kind == "user":
            mods = usr_mods
        else:
            mods = sys_mods + usr_mods
        mods = [m for m in mods if self._cfg_data(getattr(m, "name", ""))]
        mods = sorted(mods, key=lambda m: getattr(m, "name", ""))
        per_page = 12
        total = max(1, (len(mods) + per_page - 1) // per_page)
        page = max(0, min(page, total - 1))
        chunk = mods[page * per_page:(page + 1) * per_page]
        lines = ["<p>%s <b>Modules Config</b> · <i>%d/%d</i></p>" % (CUSTOM_EMOJI.get("🧩", "🧩"), page + 1, total)]
        lines.append("<blockquote>filter: <code>%s</code></blockquote>" % kind)
        text = chr(10).join(lines)
        buttons = []
        filter_row = []
        emoji_map = {"all": "🧩", "core": "📦", "user": "🔧"}
        for f_val in ("all", "core", "user"):
            label = "%s %s" % (emoji_map.get(f_val, "▪️"), f_val)
            if f_val == kind:
                label = "✅ " + label
            async def on_filter(c, f=f_val):
                await self._cfg_list(c, f, 0)
            filter_row.append(self.kernel.inline.make_button(label, on_filter, ttl=900, style="primary"))
        buttons.append(filter_row)
        row = []
        for m in chunk:
            name = getattr(m, "name", "?")
            async def on_pick(c, n=name):
                await self._cfg_cats(c, n)
            style = "success" if kind == "user" else "primary"
            row.append(self.kernel.inline.make_button(name[:12], on_pick, ttl=900, style=style))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        nav = []
        if page > 0:
            async def on_prev(c, k=kind, p=page - 1):
                await self._cfg_list(c, k, p)
            nav.append(self.kernel.inline.make_button("🔙", on_prev, ttl=900, style="primary"))
        if total > 1:
            async def on_noop(c):
                try:
                    await c.answer()
                except Exception:
                    pass
            nav.append(self.kernel.inline.make_button("📰 %d/%d" % (page + 1, total), on_noop, ttl=900))
        if page < total - 1:
            async def on_next(c, k=kind, p=page + 1):
                await self._cfg_list(c, k, p)
            nav.append(self.kernel.inline.make_button("➡️", on_next, ttl=900, style="primary"))
        if nav:
            buttons.append(nav)
        async def on_back(c):
            await self._cfg_menu(c, is_cb=True)
        async def on_close(c):
            await self._tek_close_cb(c)
        buttons.append([
            self.kernel.inline.make_button("← back", on_back, ttl=900),
            self.kernel.inline.make_button("❌ Close", on_close, ttl=900, style="danger"),
        ])
        try:
            await cb.edit(text, buttons=self._tl(buttons), parse_mode="html")
        except Exception as e:
            self.log.warning("cfg list edit: %s", e)

    async def _cfg_cats(self, cb, module_name: str):
        cfg, cats = self._cfg_get(module_name)
        if cfg is None:
            try:
                await cb.edit(
                    "<blockquote>❌ <code>%s</code> · config not found</blockquote>" % esc(module_name),
                    buttons=self._tl([[self.kernel.inline.make_button("↩️ back", self._cfg_menu, args=[], ttl=900)]]),
                    parse_mode="html",
                )
            except Exception:
                pass
            return

        if not cats:
            await self._cfg_flat(cb, module_name, cfg)
            return

        lines = [
            "<p>⚙️ <b>%s</b> · <i>%d keys · %d categories</i></p>" % (
                esc(module_name), len(cfg), len(cats)
            ),
            "<blockquote>pick a category</blockquote>",
        ]
        text = chr(10).join(lines)

        buttons = []
        row = []
        for sec, keys in cats:
            em = self._cat_emoji(sec)
            async def on_sec(c, s=sec, m=module_name):
                await self._cfg_sec(c, m, s, 0)
            label = "%s %s (%d)" % (em, sec, len(keys))
            row.append(self.kernel.inline.make_button(label[:28], on_sec, ttl=900, style="primary"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        async def on_back(c):
            await self._cfg_menu(c, is_cb=True)
        async def on_close(c):
            await self._tek_close_cb(c)
        buttons.append([
            self.kernel.inline.make_button("↩️ back", on_back, ttl=900),
            self.kernel.inline.make_button("❌ close", on_close, ttl=900, style="danger"),
        ])

        try:
            await cb.edit(text, buttons=self._tl(buttons), parse_mode="html")
        except Exception as e:
            self.log.warning("cfg cats edit: %s", e)

    async def _cfg_flat(self, cb, module_name: str, cfg: dict, page: int = 0):
        keys = list(cfg.keys())
        per_page = 16
        total = max(1, (len(keys) + per_page - 1) // per_page)
        page = max(0, min(page, total - 1))
        chunk = keys[page * per_page:(page + 1) * per_page]
        lines = ["<p>%s <b>%s</b> · <i>%d keys · %d/%d</i></p>" % (
            CUSTOM_EMOJI.get("🧩", "🧩"), esc(module_name), len(keys), page + 1, total)]
        lines.append("<blockquote>pick a key</blockquote>")
        text = chr(10).join(lines)
        buttons = []
        row = []
        for k in chunk:
            v = cfg.get(k)
            icon = {"str": "📝", "int": "🔢", "float": "🔢", "bool": "☑️",
                    "list": "📚", "dict": "🗂", "NoneType": "🗳"}.get(type(v).__name__, "📎")
            async def on_key(c, m=module_name, key=k):
                await self._cfg_key(c, m, key)
            style = "primary"
            row.append(self.kernel.inline.make_button("%s %s" % (icon, self._cfg_truncate_key(k)[:22]), on_key, ttl=900, style=style))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        nav = []
        if page > 0:
            async def on_prev(c, m=module_name, p=page - 1):
                await self._cfg_flat(c, m, cfg, p)
            nav.append(self.kernel.inline.make_button(CUSTOM_EMOJI.get("🔙", "🔙"), on_prev, ttl=900, style="primary"))
        if total > 1:
            async def on_noop(c):
                try:
                    await c.answer()
                except Exception:
                    pass
            nav.append(self.kernel.inline.make_button("📰 %d/%d" % (page + 1, total), on_noop, ttl=900))
        if page < total - 1:
            async def on_next(c, m=module_name, p=page + 1):
                await self._cfg_flat(c, m, cfg, p)
            nav.append(self.kernel.inline.make_button("➡️", on_next, ttl=900, style="primary"))
        if nav:
            buttons.append(nav)
        async def on_back(c):
            await self._cfg_menu(c, is_cb=True)
        async def on_close(c):
            await self._tek_close_cb(c)
        buttons.append([
            self.kernel.inline.make_button("← back", on_back, ttl=900),
            self.kernel.inline.make_button("Close", on_close, ttl=900, style="danger"),
        ])
        try:
            await cb.edit(text, buttons=self._tl(buttons), parse_mode="html")
        except Exception as e:
            self.log.warning("cfg flat edit: %s", e)

    async def _cfg_sec(self, cb, module_name: str, section: str, page: int = 0):
        cfg, cats = self._cfg_get(module_name)
        if cfg is None:
            return
        keys = []
        for sec, ks in cats:
            if sec == section:
                keys = ks
                break
        per_page = 16
        total = max(1, (len(keys) + per_page - 1) // per_page)
        page = max(0, min(page, total - 1))
        chunk = keys[page * per_page:(page + 1) * per_page]
        cat_em = self._cat_emoji(section)
        lines = ["<p>%s <b>%s</b> › <b>%s</b> · <i>%d/%d</i></p>" % (
            cat_em, esc(module_name), esc(section), page + 1, total)]
        lines.append("<blockquote>pick a key</blockquote>")
        text = chr(10).join(lines)
        buttons = []
        row = []
        for k in chunk:
            v = cfg.get(k)
            icon = {"str": "📝", "int": "🔢", "float": "🔢", "bool": "☑️",
                    "list": "📚", "dict": "🗂", "NoneType": "🗳"}.get(type(v).__name__, "📎")
            async def on_key(c, m=module_name, key=k):
                await self._cfg_key(c, m, key)
            style = "primary"
            row.append(self.kernel.inline.make_button("%s %s" % (icon, self._cfg_truncate_key(k)[:22]), on_key, ttl=900, style=style))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        nav = []
        if page > 0:
            async def on_prev(c, m=module_name, s=section, p=page - 1):
                await self._cfg_sec(c, m, s, p)
            nav.append(self.kernel.inline.make_button(CUSTOM_EMOJI.get("🔙", "🔙"), on_prev, ttl=900, style="primary"))
        if total > 1:
            async def on_noop(c):
                try:
                    await c.answer()
                except Exception:
                    pass
            nav.append(self.kernel.inline.make_button("📰 %d/%d" % (page + 1, total), on_noop, ttl=900))
        if page < total - 1:
            async def on_next(c, m=module_name, s=section, p=page + 1):
                await self._cfg_sec(c, m, s, p)
            nav.append(self.kernel.inline.make_button("➡️", on_next, ttl=900, style="primary"))
        if nav:
            buttons.append(nav)
        async def on_back(c, m=module_name):
            await self._cfg_cats(c, m)
        async def on_close(c):
            await self._tek_close_cb(c)
        buttons.append([
            self.kernel.inline.make_button("← back", on_back, ttl=900),
            self.kernel.inline.make_button("Close", on_close, ttl=900, style="danger"),
        ])
        try:
            await cb.edit(text, buttons=self._tl(buttons), parse_mode="html")
        except Exception as e:
            self.log.warning("cfg sec edit: %s", e)

    async def _cfg_key(self, cb, module_name: str, key: str):
        cfg = self._cfg_data(module_name)
        if key not in cfg:
            try:
                await cb.answer("not found")
            except Exception:
                pass
            return
        v = cfg.get(key)
        schema = self._cfg_schema(module_name)
        sc = schema.get(key) or {}
        desc = sc.get("description") or ""
        opts = sc.get("options") or []
        type_emoji, value_type, display_value = self._cfg_format_value(key, v)
        lines = ["<p>%s <b>%s</b> › <code>%s</code></p>" % (type_emoji, esc(module_name), esc(key))]
        if isinstance(v, bool):
            lines.append("<blockquote>📐 bool</blockquote>")
        else:
            lines.append("<blockquote>📐 <code>%s</code></blockquote>" % esc(value_type))
        if desc:
            lines.append("<blockquote>📖 <i>%s</i></blockquote>" % esc(desc))
        if not isinstance(v, bool):
            lines.append("<blockquote>💾 value %s</blockquote>" % display_value)
        if opts:
            lines.append("<blockquote>🎯 options: %s</blockquote>" % ", ".join("<code>%s</code>" % esc(str(o)) for o in opts))
        text = chr(10).join(lines)

        buttons = []
        row = []
        if isinstance(v, bool):
            async def on_toggle(c, m=module_name, k=key, cur=v):
                d = self._cfg_data(m)
                d[k] = not bool(cur)
                self._cfg_save(m, d)
                try:
                    await c.answer("→ " + ("on" if d[k] else "off"))
                except Exception:
                    pass
                await self._cfg_key(c, m, k)
            label = "🟢 ON" if v else "🔴 OFF"
            style = "primary"
            row.append(self.kernel.inline.make_button(label + " · toggle", on_toggle, ttl=900, style=style))
        elif isinstance(v, (int, float)):
            step = 1 if isinstance(v, int) else 0.5
            async def on_bump(c, m=module_name, k=key, delta=0):
                d = self._cfg_data(m)
                cur = d.get(k, 0)
                try:
                    nv = cur + delta
                    nv = int(nv) if isinstance(cur, int) else round(float(nv), 4)
                except Exception:
                    return
                d[k] = nv
                self._cfg_save(m, d)
                try:
                    await c.answer("→ " + str(nv))
                except Exception:
                    pass
                await self._cfg_key(c, m, k)
            row.append(self.kernel.inline.make_button("➖ %s" % step, on_bump, args=[-step], ttl=900, style="danger"))
            row.append(self.kernel.inline.make_button("➕ %s" % step, on_bump, args=[step], ttl=900, style="success"))
        elif isinstance(v, str) and opts:
            for o in opts:
                ov = str(o)
                async def on_pick(c, m=module_name, k=key, val=ov):
                    d = self._cfg_data(m)
                    d[k] = val
                    self._cfg_save(m, d)
                    try:
                        await c.answer("→ " + val)
                    except Exception:
                        pass
                    await self._cfg_key(c, m, k)
                style = "success" if ov == v else "primary"
                mark = "✅ " if ov == v else "🎯 "
                row.append(self.kernel.inline.make_button((mark + ov)[:24], on_pick, ttl=900, style=style))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
        if row:
            buttons.append(row)

        async def on_edit(c, m=module_name, k=key):
            await c.answer()
            try:
                _tl_btns = self._tl([[
                    self.kernel.inline.make_button("← back", self._cfg_key_cb_back, args=[m, k], ttl=900),
                    self.kernel.inline.make_button("Close", self._tek_close_cb, ttl=900, style="danger"),
                ]])
                await c.edit(
                    "<blockquote>✏️ <b>edit</b> <code>%s.%s</code></blockquote>"
                    "<blockquote>📨 send: <code>?cfg set %s %s &lt;value&gt;</code></blockquote>" % (
                        esc(m), esc(k), esc(m), esc(k)),
                    buttons=_tl_btns,
                    parse_mode="html",
                )
            except Exception:
                pass
        buttons.append([self.kernel.inline.make_button("✏️ edit", on_edit, ttl=900, style="primary")])

        async def on_delete(c, m=module_name, k=key):
            d = self._cfg_data(m)
            if k in d:
                d.pop(k, None)
                self._cfg_save(m, d)
            try:
                await c.answer("deleted")
            except Exception:
                pass
            await self._cfg_cats(c, m)
        buttons.append([self.kernel.inline.make_button("🗑 delete", on_delete, ttl=900, style="danger")])

        if isinstance(v, (list, dict)):
            vt = "list" if isinstance(v, list) else "dict"
            async def on_add(c, m=module_name, k=key):
                await c.answer("?cfg set %s %s <json>" % (m, k), alert=True)
            async def on_del(c, m=module_name, k=key):
                await c.answer("?cfg set %s %s <json>" % (m, k), alert=True)
            async def on_set(c, m=module_name, k=key):
                await c.answer("?cfg set %s %s <json>" % (m, k), alert=True)
            buttons.append([
                self.kernel.inline.make_button("➕ add", on_add, ttl=900, style="success"),
                self.kernel.inline.make_button("➖ del", on_del, ttl=900, style="danger"),
                self.kernel.inline.make_button("🎯 set", on_set, ttl=900, style="primary"),
            ])

        default_v = self._cfg_default(module_name, key)
        if default_v is not None and default_v != v:
            async def on_reset(c, m=module_name, k=key, dv=default_v):
                d = self._cfg_data(m)
                d[k] = dv
                self._cfg_save(m, d)
                try:
                    await c.answer("reset")
                except Exception:
                    pass
                await self._cfg_key(c, m, k)
            buttons.append([self.kernel.inline.make_button("🔄 reset to default", on_reset, ttl=900)])

        async def on_back(c, m=module_name, k=key):
            _, cats = self._cfg_get(m)
            sec = "Other"
            for sc_name, ks in (cats or []):
                if k in ks:
                    sec = sc_name
                    break
            await self._cfg_sec(c, m, sec, 0)
        async def on_close(c):
            await self._tek_close_cb(c)
        buttons.append([
            self.kernel.inline.make_button("← back", on_back, ttl=900),
            self.kernel.inline.make_button("Close", on_close, ttl=900, style="danger"),
        ])

        try:
            await cb.edit(text, buttons=self._tl(buttons), parse_mode="html")
        except Exception as e:
            self.log.warning("cfg key edit: %s", e)

    async def _cfg_key_cb_back(self, cb, module_name: str, key: str):
        try:
            await cb.answer()
        except Exception:
            pass
        await self._cfg_key(cb, module_name, key)

    @command(name="cfg", aliases=["mcfg"], description="Module config")
    async def cmd_cfg(self, event, args):
        if not args:
            await self._cfg_menu(event)
            return
        sub = args[0].lower()
        if sub in ("core", "core"):
            await self._cfg_cmd_list(event, "core")
            return
        if sub in ("user", "custom"):
            await self._cfg_cmd_list(event, "user")
            return
        if sub == "set":
            await self._cfg_cmd_set(event, args)
            return
        if sub == "reset":
            await self._cfg_cmd_reset(event, args)
            return
        if sub in ("find", "search"):
            await self._cfg_cmd_find(event, args)
            return
        await self._cfg_menu(event)

    async def _cfg_cmd_list(self, event, kind: str):
        sys_mods, usr_mods = self._modules_split()
        mods = sys_mods if kind == "core" else usr_mods
        mods = sorted(mods, key=lambda m: getattr(m, "name", ""))
        lines = ["<blockquote><b>cfg › %s</b> <code>(%d)</code></blockquote>" % (kind, len(mods))]
        for m in mods:
            icon = getattr(m, "icon", None) or "◼"
            lines.append("<blockquote>%s <code>%s</code></blockquote>" % (esc(icon), esc(getattr(m, "name", "?"))))
        try:
            await event.edit(chr(10).join(lines), parse_mode="html")
        except Exception:
            pass

    async def _cfg_cmd_set(self, event, args):
        parts = " ".join(args[1:]).strip()
        tokens = parts.split(None, 2)
        if len(tokens) < 3:
            try:
                await event.edit("<blockquote>usage: <code>?cfg set &lt;module&gt; &lt;key&gt; &lt;value&gt;</code></blockquote>", parse_mode="html")
            except Exception:
                pass
            return
        m, k, raw = tokens
        cfg = self._cfg_data(m)
        if not cfg or k not in cfg:
            try:
                await event.edit("<blockquote>key not found: <code>%s.%s</code></blockquote>" % (esc(m), esc(k)), parse_mode="html")
            except Exception:
                pass
            return
        value = self._cfg_parse(raw)
        cfg[k] = value
        self._cfg_save(m, cfg)
        try:
            await event.edit("<blockquote>✓ <code>%s.%s</code> = <code>%s</code></blockquote>" % (esc(m), esc(k), esc(self._cfg_val(value, 200))), parse_mode="html")
        except Exception:
            pass

    async def _cfg_cmd_reset(self, event, args):
        if len(args) < 3:
            try:
                await event.edit("<blockquote>usage: <code>?cfg reset &lt;module&gt; &lt;key&gt;</code></blockquote>", parse_mode="html")
            except Exception:
                pass
            return
        m, k = args[1], args[2]
        dv = self._cfg_default(m, k)
        if dv is None:
            try:
                await event.edit("<blockquote>no default for <code>%s.%s</code></blockquote>" % (esc(m), esc(k)), parse_mode="html")
            except Exception:
                pass
            return
        cfg = self._cfg_data(m)
        if not cfg:
            return
        cfg[k] = dv
        self._cfg_save(m, cfg)
        try:
            await event.edit("<blockquote>↺ reset <code>%s.%s</code></blockquote>" % (esc(m), esc(k)), parse_mode="html")
        except Exception:
            pass

    async def _cfg_cmd_find(self, event, args):
        if len(args) < 2:
            try:
                await event.edit("<blockquote>usage: <code>?cfg find &lt;query&gt;</code></blockquote>", parse_mode="html")
            except Exception:
                pass
            return
        q = " ".join(args[1:]).strip().lower()
        hits = []
        try:
            from pathlib import Path
            d = Path("data/tetko_config")
            for f in d.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8")) or {}
                except Exception:
                    continue
                for k in data:
                    if q in k.lower():
                        hits.append((f.stem, k, data[k]))
                        if len(hits) >= 30:
                            break
                if len(hits) >= 30:
                    break
        except Exception:
            pass
        if not hits:
            try:
                await event.edit("<blockquote>nothing for <code>%s</code></blockquote>" % esc(q), parse_mode="html")
            except Exception:
                pass
            return
        lines = ["<blockquote><b>cfg find:</b> <code>%s</code></blockquote>" % esc(q)]
        for m, k, v in hits:
            lines.append("<blockquote><code>%s.%s</code> = %s</blockquote>" % (esc(m), esc(k), esc(self._cfg_val(v, 60))))
        try:
            await event.edit(chr(10).join(lines), parse_mode="html")
        except Exception:
            pass
