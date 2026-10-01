"""BotClient - inline bot for TETKO."""
from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time
from typing import Any, Optional

from telethon import TelegramClient, events
from telethon.tl.functions.messages import (
    GetInlineBotResultsRequest,
    SendInlineBotResultRequest,
)
from telethon.tl.types import (
    KeyboardButtonSwitchInline,
    UpdateBotInlineSend,
    InputBotInlineResult,
    InputBotInlineMessageText,
    InputBotInlineMessageRichMessage,
    InputRichMessageHTML,
    InputReplyToMessage,
    MessageEntityCustomEmoji,
    ReplyInlineMarkup,
    KeyboardButtonRow,
    KeyboardButtonCallback,
)

log = logging.getLogger("TETKO.tetko.bot")


def _make_btn_style_bot(style_name, emoji_id=None):
    bg_primary = False
    bg_success = False
    bg_danger = False
    if style_name == "primary":
        bg_primary = True
    elif style_name == "success":
        bg_success = True
    elif style_name == "danger":
        bg_danger = True
    if emoji_id is None and not (bg_primary or bg_success or bg_danger):
        return None
    from telethon.tl.types import KeyboardButtonStyle
    kwargs = {}
    if emoji_id is not None:
        kwargs["icon"] = emoji_id
    if bg_primary:
        kwargs["bg_primary"] = True
    if bg_success:
        kwargs["bg_success"] = True
    if bg_danger:
        kwargs["bg_danger"] = True
    try:
        return KeyboardButtonStyle(**kwargs)
    except Exception:
        return None


import re as _re

_TG_EMOJI_RE = _re.compile(r'<tg-emoji emoji-id="(\d+)">(.*?)</tg-emoji>')


def _split_label(label):
    if not isinstance(label, str):
        return str(label), None
    m = _TG_EMOJI_RE.search(label)
    if not m:
        return label, None
    emoji_id = int(m.group(1))
    plain = _TG_EMOJI_RE.sub(lambda x: x.group(2), label)
    return plain, emoji_id


class BotClient:
    def __init__(self, api_id, api_hash, bot_token, kernel=None):
        self.kernel = kernel
        self.username = None
        self.client = TelegramClient("tetko_inline_bot", api_id, api_hash)
        self._bot_token = bot_token
        self._menus = {}
        self._inline_sends = {}

    async def start(self):
        await self.client.start(bot_token=self._bot_token)
        me = await self.client.get_me()
        self.username = me.username
        log.info(f"Inline bot started: @{self.username}")

        @self.client.on(events.InlineQuery())
        async def on_inline(event):
            await self._handle_inline(event)

        @self.client.on(events.CallbackQuery())
        async def on_callback(event):
            await self._handle_callback(event)

        @self.client.on(events.NewMessage(pattern=r"^/(start|menu|help)"))
        async def on_start(event):
            await self._handle_start(event)

        @self.client.on(events.Raw(UpdateBotInlineSend))
        async def on_inline_send(update):
            qid = update.id
            imid = update.msg_id
            self._inline_sends[qid] = imid

    async def stop(self):
        await self.client.disconnect()

    def register_menu(self, key, text, buttons, ttl=600):
        now = time.time()
        self._menus = {
            k: v for k, v in self._menus.items()
            if not isinstance(v, dict) or now - v.get("created", 0) < v.get("ttl", 600)
        }
        self._menus[key] = {
            "text": text,
            "buttons": buttons,
            "created": now,
            "ttl": ttl,
        }

    async def edit_inline_menu(self, inline_message_id, text, buttons):
        from telethon.tl.functions.messages import EditInlineBotMessageRequest
        from telethon.tl.types import (
            ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonCallback,
            KeyboardButtonSwitchInline,
        )

        msg_text = text
        entities = None
        try:
            parsed, entities = await self.kernel.client._parse_message_text(text, "html")
            msg_text = parsed
        except Exception as e:
            log.debug(f"edit_inline_menu parse failed: {e}")

        rows = []
        for row in buttons:
            kb_row = []
            for b in row:
                kind = b.get("kind", "callback") if isinstance(b, dict) else "callback"
                label, emoji_id = _split_label(b["label"])
                style = _make_btn_style_bot(b.get("style") if isinstance(b, dict) else None, emoji_id)
                if kind == "switch_current":
                    kw = {"same_peer": True}
                    if style is not None:
                        kw["style"] = style
                    kb_row.append(KeyboardButtonSwitchInline(text=label, query=b.get("query", ""), **kw))
                    continue
                if kind == "switch":
                    kw = {"same_peer": False}
                    if style is not None:
                        kw["style"] = style
                    kb_row.append(KeyboardButtonSwitchInline(text=label, query=b.get("query", ""), **kw))
                    continue
                data = b["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                if style is not None:
                    kb_row.append(KeyboardButtonCallback(text=label, data=data, style=style))
                else:
                    kb_row.append(KeyboardButtonCallback(text=label, data=data))
            rows.append(KeyboardButtonRow(buttons=kb_row))
        markup = ReplyInlineMarkup(rows=rows) if rows else None

        kwargs = {"id": inline_message_id, "message": msg_text}
        if markup:
            kwargs["reply_markup"] = markup
        if entities:
            kwargs["entities"] = entities

        return await self.client(EditInlineBotMessageRequest(**kwargs))

    def get_inline_message_id(self, token):
        if not hasattr(self, "_inlines"):
            return None
        return self._inlines.get(token)

    def get_message_id(self, token):
        return self._menus.get(f"msgid_{token}")

    async def send_inline_menu(self, chat_id, key, text, buttons, query=None, topic_id=None):
        self.register_menu(key, text, buttons)

        query_str = query or key
        kernel = self.kernel
        userbot = kernel.client

        _t = type(chat_id).__name__
        if _t.startswith('InputPeer'):
            peer = chat_id
        else:
            try:
                peer = await userbot.get_input_entity(chat_id)
            except Exception as e:
                log.warning(f"send_inline_menu get_input_entity failed: {e}")
                peer = chat_id

        results = await userbot(GetInlineBotResultsRequest(
            bot=f"@{self.username}",
            peer=peer,
            query=query_str,
            offset="",
        ))

        if not results or not results.results:
            log.error(f"send_inline_menu no results for {query_str}")
            return None

        from telethon.tl.custom.inlineresult import InlineResult
        inline_results = [InlineResult(userbot, r, results.query_id) for r in results.results]

        if topic_id:
            reply_to_obj = InputReplyToMessage(reply_to_msg_id=topic_id, top_msg_id=topic_id)
            message = await userbot(SendInlineBotResultRequest(
                peer=peer,
                query_id=results.query_id,
                id=results.results[0].id,
                reply_to=reply_to_obj,
            ))
        else:
            message = await inline_results[0].click(chat_id)

        imid = None
        for _ in range(25):
            await asyncio.sleep(0.2)
            imid = self._inline_sends.get(query_str)
            if imid:
                break

        if imid:
            if not hasattr(self, "_inlines"):
                self._inlines = {}
            for row in buttons:
                for btn in row:
                    if not isinstance(btn, dict) or "token" not in btn:
                        continue
                    token = btn["token"]
                    self._inlines[token] = imid

        return message

    async def _handle_inline(self, event):
        query = (event.text or "").strip()

        if query.startswith("cfg_"):
            try:
                await self._handle_cfg_inline(event, query)
            except Exception as e:
                log.exception(f"cfg inline: {e}")
            return

        if query.startswith("audata_"):
            try:
                await self._handle_audata_inline(event, query)
            except Exception as e:
                log.exception(f"audata inline: {e}")
            return

        if query.startswith("rich:"):
            key = query[len("rich:"):]
            menu = self._menus.get(key)
            if menu is None:
                html_text = key
                menu = {"text": html_text, "buttons": []}
            html_text = menu.get("text", "")

            try:
                rich = InputRichMessageHTML(html=html_text)
            except Exception as e:
                log.warning(f"_handle_inline rich HTML failed: {e}")
                rich = None

            if rich is not None:
                try:
                    reply_markup = None
                    buttons = menu.get("buttons") or []
                    if buttons:
                        kb_rows = []
                        for row in buttons:
                            kb_row = []
                            for b in row:
                                if not isinstance(b, dict):
                                    kb_row.append(b)
                                    continue
                                kind = b.get("kind", "callback")
                                text_btn = b.get("text", ".")
                                style = _make_btn_style_bot(b.get("style"), None)
                                if kind == "switch_current":
                                    kw = {"same_peer": True}
                                    if style is not None:
                                        kw["style"] = style
                                    kb_row.append(KeyboardButtonSwitchInline(text=text_btn, query=b.get("query", ""), **kw))
                                    continue
                                if kind == "switch":
                                    kw = {"same_peer": False}
                                    if style is not None:
                                        kw["style"] = style
                                    kb_row.append(KeyboardButtonSwitchInline(text=text_btn, query=b.get("query", ""), **kw))
                                    continue
                                data = b.get("token", b.get("data", ""))
                                if isinstance(data, str):
                                    data = data.encode("utf-8")
                                if style is not None:
                                    kb_row.append(KeyboardButtonCallback(text=text_btn, data=data, style=style))
                                else:
                                    kb_row.append(KeyboardButtonCallback(text=text_btn, data=data))
                            if kb_row:
                                kb_rows.append(KeyboardButtonRow(buttons=kb_row))
                        if kb_rows:
                            reply_markup = ReplyInlineMarkup(rows=kb_rows)

                    result = InputBotInlineResult(
                        id=f"rich_{secrets.token_hex(4)}",
                        type="article",
                        title="Rich",
                        description=html_text[:80],
                        send_message=InputBotInlineMessageRichMessage(
                            rich_message=rich,
                            reply_markup=reply_markup,
                        ),
                    )
                    await event.answer([result], cache_time=0, gallery=False)
                    return
                except Exception as e:
                    log.warning(f"_handle_inline rich result failed: {e}")

        if query.startswith("table:"):
            body = query[len("table:"):].strip()
            lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
            if not lines:
                return
            rows = [ln.split("|") for ln in lines]
            header = rows[0]
            data = rows[1:]
            html_parts = ["<table>"]
            html_parts.append("<tr>" + "".join(f"<th>{h.strip()}</th>" for h in header) + "</tr>")
            for row in data:
                html_parts.append("<tr>" + "".join(f"<td>{c.strip()}</td>" for c in row) + "</tr>")
            html_parts.append("</table>")
            html_text = "".join(html_parts)

            try:
                rich = InputRichMessageHTML(html=html_text)
            except Exception as e:
                log.warning(f"_handle_inline table HTML failed: {e}")
                rich = None

            if rich is not None:
                try:
                    result = InputBotInlineResult(
                        id=f"table_{secrets.token_hex(4)}",
                        type="article",
                        title="Table",
                        description=body[:80],
                        send_message=InputBotInlineMessageRichMessage(rich_message=rich),
                    )
                    await event.answer([result], cache_time=0, gallery=False)
                    return
                except Exception as e:
                    log.warning(f"_handle_inline table result failed: {e}")

        menu = self._menus.get(query)

        now = time.time()
        self._menus = {
            k: v for k, v in self._menus.items()
            if now - v["created"] < v["ttl"]
        }

        if menu is None:
            results = [InputBotInlineResult(
                id=f"empty_{secrets.token_hex(4)}",
                type="article",
                title="TETKO",
                description=f"menu '{query}' not found",
                send_message=InputBotInlineMessageText(message="menu not found or expired"),
            )]
            await event.answer(results, cache_time=0, gallery=False)
            return

        rows = []
        for row in menu["buttons"]:
            kb_row = []
            for b in row:
                kind = b.get("kind", "callback") if isinstance(b, dict) else "callback"
                label, emoji_id = _split_label(b["label"])
                style = _make_btn_style_bot(b.get("style") if isinstance(b, dict) else None, emoji_id)
                if kind == "switch_current":
                    kw = {"same_peer": True}
                    if style is not None:
                        kw["style"] = style
                    kb_row.append(KeyboardButtonSwitchInline(text=label, query=b.get("query", ""), **kw))
                    continue
                if kind == "switch":
                    kw = {"same_peer": False}
                    if style is not None:
                        kw["style"] = style
                    kb_row.append(KeyboardButtonSwitchInline(text=label, query=b.get("query", ""), **kw))
                    continue
                data = b["token"]
                if isinstance(data, str):
                    data = data.encode("utf-8")
                if len(data) > 64:
                    data = data[:64]
                if style is not None:
                    kb_row.append(KeyboardButtonCallback(text=label, data=data, style=style))
                else:
                    kb_row.append(KeyboardButtonCallback(text=label, data=data))
            rows.append(KeyboardButtonRow(buttons=kb_row))

        markup = ReplyInlineMarkup(rows=rows) if rows else None

        result_id = query
        msg_text = menu["text"]
        entities = None
        try:
            parsed, entities = await self.client._parse_message_text(msg_text, "html")
            msg_text = parsed
        except Exception as e:
            log.debug(f"_handle_inline parse failed: {e}")

        kwargs = {"message": msg_text, "reply_markup": markup}
        if entities:
            kwargs["entities"] = entities

        results = [InputBotInlineResult(
            id=result_id,
            type="article",
            title="TETKO Menu",
            description=re.sub(r"<[^>]+>", "", menu["text"])[:100],
            send_message=InputBotInlineMessageText(**kwargs),
        )]

        await event.answer(results, cache_time=0, gallery=False)

    async def _handle_audata_inline(self, event, query):
        plugin = None
        try:
            reg = getattr(self.kernel, "registry", None)
            if reg is not None:
                for _n, _m in reg._modules.items():
                    if getattr(_m, "name", "") == "Audata":
                        plugin = _m
                        break
        except Exception:
            plugin = None

        if plugin is None:
            await event.answer([], cache_time=0, gallery=False)
            return

        rest = query[len("audata_"):]
        if " " not in rest:
            await event.answer([
                InputBotInlineResult(
                    id="audata_hint_" + secrets.token_hex(4),
                    type="article",
                    title="audata",
                    description="type new value after the space",
                    send_message=InputBotInlineMessageText(message="type new value after the space"),
                )
            ], cache_time=0, gallery=False)
            return

        head, value = rest.split(" ", 1)
        value = value.strip()
        if not value:
            await event.answer([], cache_time=0, gallery=False)
            return

        if "_" not in head:
            await event.answer([], cache_time=0, gallery=False)
            return

        token, field = head.rsplit("_", 1)
        token = token.strip()
        field = field.strip().lower()

        if field not in ("title", "artist", "album", "year", "genre", "track"):
            await event.answer([
                InputBotInlineResult(
                    id="audata_badfield_" + secrets.token_hex(4),
                    type="article",
                    title="audata",
                    description="unknown field: " + field,
                    send_message=InputBotInlineMessageText(message="unknown field: " + field),
                )
            ], cache_time=0, gallery=False)
            return

        sessions = getattr(plugin, "_sessions", None) or {}
        session = sessions.get(token)
        if session is None:
            await event.answer([
                InputBotInlineResult(
                    id="audata_exp_" + secrets.token_hex(4),
                    type="article",
                    title="audata",
                    description="session expired",
                    send_message=InputBotInlineMessageText(message="session expired - reopen audata"),
                )
            ], cache_time=0, gallery=False)
            return

        session.fields[field] = value

        try:
            imid = getattr(session, "inline_message_id", None)
            if imid:
                await self.edit_inline_menu(
                    inline_message_id=imid,
                    text=plugin._render(session),
                    buttons=plugin._buttons(session),
                )
                if not hasattr(self, "_inlines"):
                    self._inlines = {}
                for row in plugin._buttons(session):
                    for b in row:
                        tok = b.get("token") if isinstance(b, dict) else None
                        if tok:
                            self._inlines[tok] = imid
        except Exception as e:
            es = str(e).lower()
            if "not modified" not in es:
                log.warning("audata refresh failed: " + str(e))

        from core.tetko import shell as _sh
        try:
            prefix = getattr(self.kernel, "prefix", ".") or "."
        except Exception:
            prefix = "."

        text = _sh.wrap([
            "saved",
            "field    : " + field,
            "value    : " + value,
            "",
            "hint     : " + prefix + "audata to reopen",
        ], cmd="audata " + field, trailing=True)

        try:
            parsed_text, entities = await self.client._parse_message_text(text, "html")
        except Exception:
            parsed_text, entities = text, None

        kw = {"message": parsed_text}
        if entities:
            kw["entities"] = entities

        await event.answer([
            InputBotInlineResult(
                id="audata_ok_" + secrets.token_hex(4),
                type="article",
                title="saved: " + field,
                description=value[:100],
                send_message=InputBotInlineMessageText(**kw),
            )
        ], cache_time=0, gallery=False)

    async def _handle_cfg_inline(self, event, query):
        import json as _json
        from pathlib import Path as _P

        parts = query.split(maxsplit=1)
        if len(parts) < 2:
            await event.answer([
                InputBotInlineResult(
                    id=f"cfgerr_{secrets.token_hex(4)}",
                    type="article",
                    title="cfg",
                    description="format: cfg_<token> <value>",
                    send_message=InputBotInlineMessageText(message="format: cfg_<token> <value>"),
                )
            ], cache_time=0, gallery=False)
            return

        head = parts[0]
        raw_value = parts[1].strip()
        token = head[len("cfg_"):]

        pending = getattr(self.kernel, "_cfg_pending", {}) or {}
        now = time.time()
        for _t in [t for t, v in list(pending.items()) if now - v.get("ts", 0) > 900]:
            pending.pop(_t, None)
        info = pending.get(token)
        if info is None:
            await event.answer([
                InputBotInlineResult(
                    id=f"cfgexp_{secrets.token_hex(4)}",
                    type="article",
                    title="cfg",
                    description="token expired",
                    send_message=InputBotInlineMessageText(message="token expired - open cfg again"),
                )
            ], cache_time=0, gallery=False)
            return

        module = info.get("module")
        key = info.get("key")
        parsed = self._parse_cfg_value(raw_value)

        cfg_path = _P("data/tetko_config") / f"{module}.json"
        data = {}
        if cfg_path.exists():
            try:
                data = _json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[key] = parsed
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(_json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

        result_text = f"<b>{module}</b> -> <code>{key}</code> = <code>{parsed!r}</code>"
        try:
            parsed_text, entities = await self.client._parse_message_text(result_text, "html")
        except Exception:
            parsed_text, entities = result_text, None

        kwargs = {"message": parsed_text}
        if entities:
            kwargs["entities"] = entities

        await event.answer([
            InputBotInlineResult(
                id=f"cfgok_{secrets.token_hex(4)}",
                type="article",
                title="saved",
                description=f"{module}.{key} = {parsed!r}",
                send_message=InputBotInlineMessageText(**kwargs),
            )
        ], cache_time=0, gallery=False)

    @staticmethod
    def _parse_cfg_value(s):
        low = s.lower()
        if low in ("true", "yes", "on"):
            return True
        if low in ("false", "no", "off"):
            return False
        if low in ("null", "none"):
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
                import json as _j
                return _j.loads(s)
            except Exception:
                pass
        return s

    async def _handle_callback(self, event):
        data = event.data
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")

        log.debug(f"Bot callback: data={data!r}")

        sender = getattr(event, "sender_id", None)
        if sender is None:
            sender = getattr(getattr(event, "from_user", None), "id", None)
        try:
            sender = int(sender) if sender is not None else None
        except (ValueError, TypeError):
            sender = None

        cfg = getattr(self.kernel, "config", None) or {}
        owner = cfg.get("admin_id") or cfg.get("owner_id")
        allowed = False
        if owner is not None and sender is not None:
            try:
                if int(owner) == sender:
                    allowed = True
            except (ValueError, TypeError):
                pass
        if not allowed and sender is not None:
            im = getattr(self.kernel, "inline_manager", None)
            if im is not None:
                try:
                    allowed = await im.is_allowed(sender, context=event)
                except Exception:
                    allowed = False

        if not allowed:
            log.warning(f"Bot callback denied sender={sender} owner={owner}")
            try:
                await event.answer("no access", alert=True)
            except Exception:
                pass
            return

        if self.kernel is not None and hasattr(self.kernel, "inline"):
            h = self.kernel.inline.get_handler(data)
            if h is not None:
                try:
                    await h["func"](event, *h["args"])
                except Exception as e:
                    log.exception(f"inline handler error: {e}")
                return

        sender_id = getattr(event, "sender_id", None)
        admin_id = None
        if self.kernel is not None and hasattr(self.kernel, "context"):
            admin_id = self.kernel.context.admin_id

        if admin_id is None or sender_id != admin_id:
            log.warning(f"Bot callback denied sender={sender_id} owner={admin_id}")
            try:
                await event.answer("no access", alert=True)
            except Exception:
                pass
            return

        try:
            await event.answer()
        except Exception:
            pass

    async def _handle_start(self, event):
        if self.kernel is not None and hasattr(self.kernel, "inline"):
            handler = getattr(self.kernel.inline, "_start_handler", None)
            if handler is not None:
                try:
                    await handler(event)
                    return
                except Exception as e:
                    log.exception(f"_handle_start error: {e}")

        await event.reply(
            "TETKO inline bot.\n"
            "Use .dlm via userbot to get menu in any chat."
        )
