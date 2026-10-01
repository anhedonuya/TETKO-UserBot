from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
from urllib.parse import quote, quote_plus


@dataclass
class Manifest:
    name: str = "TGAdresses"
    version: str = "3.0.0"
    author: str = "@flexOwnerAL"
    description: str = "telegram deeplinks catalog"
    api: str = "1.5.0"
    min_core: str = ">=0.0.0"
    access: List[str] = field(default_factory=lambda: ["module"])
    tags: List[str] = field(default_factory=lambda: ["util", "tg"])
    categories: List[str] = field(default_factory=lambda: ["util"])
    events: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=lambda: ["on_command"])
    priority: Dict[str, int] = field(default_factory=lambda: {"on_command": 100})
    cfg_defaults: Dict[str, Any] = field(default_factory=lambda: {"enabled": True})
    cfg_schema: Dict[str, Any] = field(default_factory=lambda: {"enabled": {"type": "bool"}})


MANIFEST = Manifest()


def _enc(s):
    return quote(str(s), safe="")


def _enc2(s):
    return quote(quote(str(s), safe=""), safe="")


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_PAGES: Dict[int, tuple] = {
    1: ("user", [
        ("resolve",   "tgadr resolve <@u> [text]",       "dothat tgadr resolve durov hi",          "tg://resolve?domain=durov&amp;text=hi"),
        ("share",     "tgadr share <url> [text]",        "dothat tgadr share https://t.me hi",     "https://t.me/share/url?url=https%3A%2F%2Ft.me&amp;text=hi"),
        ("user",      "tgadr user <id>",                 "dothat tgadr user 123456789",            "tg://user?id=123456789"),
        ("contact",   "tgadr contact <token>",           "dothat tgadr contact ABC123",            "tg://contact?token=ABC123"),
        ("phone",     "tgadr phone <+79...>",            "dothat tgadr phone +79991234567",        "tg://resolve?phone=79991234567"),
        ("profile",   "tgadr profile <@u>",              "dothat tgadr profile durov",             "tg://resolve?domain=durov&amp;profile"),
        ("direct",    "tgadr direct <@u>",               "dothat tgadr direct news",               "tg://resolve?domain=news&amp;direct"),
        ("mention",   "tgadr mention <@u>",              "dothat tgadr mention durov",             "https://t.me/durov"),
        ("msg",       "tgadr msg <chat_id> [msg_id]",    "dothat tgadr msg 123 456",               "tg://openmessage?chat_id=123&amp;message_id=456"),
        ("voicecall", "tgadr voicecall <@u>",            "dothat tgadr voicecall durov",           "tg://resolve?domain=durov&amp;start"),
    ]),
    2: ("messages", [
        ("post",      "tgadr post <channel> <post>",     "dothat tgadr post 123 456",              "tg://privatepost?channel=123&amp;post=456"),
        ("single",    "tgadr single <channel> <post>",   "dothat tgadr single 123 456",            "tg://privatepost?channel=123&amp;post=456&amp;single"),
        ("thread",    "tgadr thread <ch> <post> <thr>",  "dothat tgadr thread 123 456 789",        "tg://privatepost?channel=123&amp;post=456&amp;thread=789"),
        ("comment",   "tgadr comment <ch> <post> <c>",   "dothat tgadr comment 123 456 789",       "tg://privatepost?channel=123&amp;post=456&amp;comment=789"),
        ("timestamp", "tgadr timestamp <ch> <post> <t>", "dothat tgadr timestamp 123 456 10:23",   "tg://privatepost?channel=123&amp;post=456&amp;t=10:23"),
        ("task",      "tgadr task <ch> <post> <task>",   "dothat tgadr task 123 456 1",            "tg://privatepost?channel=123&amp;post=456&amp;task=1"),
        ("public",    "tgadr public <@u> <post>",        "dothat tgadr public durov 123",          "tg://resolve?domain=durov&amp;post=123"),
        ("pubsingle", "tgadr pubsingle <@u> <post>",     "dothat tgadr pubsingle durov 123",       "tg://resolve?domain=durov&amp;post=123&amp;single"),
        ("msgurl",    "tgadr msgurl <url> [text]",       "dothat tgadr msgurl https://t.me hi",    "tg://msg_url?url=https%3A%2F%2Ft.me&amp;text=hi"),
        ("tme",       "tgadr tme <@u> <post>",           "dothat tgadr tme durov 123",             "https://t.me/durov/123"),
    ]),
    3: ("chats", [
        ("join",      "tgadr join <hash>",               "dothat tgadr join abc123",               "tg://join?invite=abc123"),
        ("invite",    "tgadr invite <hash>",             "dothat tgadr invite abc123",             "https://t.me/+abc123"),
        ("addlist",   "tgadr addlist <slug>",            "dothat tgadr addlist abc",               "tg://addlist?slug=abc"),
        ("boost",     "tgadr boost <@ch>",               "dothat tgadr boost durov",               "tg://boost?domain=durov"),
        ("boostch",   "tgadr boostch <channel_id>",      "dothat tgadr boostch 1234567890",        "tg://boost?channel=1234567890"),
        ("call",      "tgadr call <slug>",               "dothat tgadr call abc",                  "tg://call?slug=abc"),
        ("conference","tgadr conference <slug>",         "dothat tgadr conference abc",            "https://t.me/call/abc"),
        ("videochat", "tgadr videochat <@u>",            "dothat tgadr videochat durov",           "tg://resolve?domain=durov&amp;videochat"),
        ("livestream","tgadr livestream <@u>",           "dothat tgadr livestream durov",          "tg://resolve?domain=durov&amp;livestream"),
        ("voicechat", "tgadr voicechat <@u>",            "dothat tgadr voicechat durov",           "tg://resolve?domain=durov&amp;voicechat"),
    ]),
    4: ("proxy", [
        ("proxy",     "tgadr proxy <host> <port> <secret>", "dothat tgadr proxy 1.2.3.4 443 abc",  "tg://proxy?server=1.2.3.4&amp;port=443&amp;secret=abc"),
        ("socks",     "tgadr socks <host> <port> [u] [p]",  "dothat tgadr socks 1.2.3.4 1080",     "tg://socks?server=1.2.3.4&amp;port=1080"),
        ("proxytme",  "tgadr proxytme <host> <port> <sec>", "dothat tgadr proxytme 1.2.3.4 443 abc","https://t.me/proxy?server=1.2.3.4&amp;port=443&amp;secret=abc"),
        ("sockstme",  "tgadr sockstme <host> <port>",       "dothat tgadr sockstme 1.2.3.4 1080",  "https://t.me/socks?server=1.2.3.4&amp;port=1080"),
        ("setlang",   "tgadr setlang <lang>",               "dothat tgadr setlang ru",             "tg://setlanguage?lang=ru"),
        ("setlangtme","tgadr setlangtme <lang>",            "dothat tgadr setlangtme ru",          "https://t.me/setlanguage/ru"),
        ("confirmph", "tgadr confirmph <phone> <hash>",     "dothat tgadr confirmph +7999 abc",    "tg://confirmphone?phone=7999&amp;hash=abc"),
        ("oauth",     "tgadr oauth <token>",                "dothat tgadr oauth TOKEN123",         "tg://oauth?token=TOKEN123"),
        ("login",     "tgadr login <code>",                 "dothat tgadr login 12345",            "tg://login?code=12345"),
        ("passport",  "tgadr passport <bot_id> <scope>",    "dothat tgadr passport 123 telegram_passport", "tg://passport?bot_id=123&amp;scope=telegram_passport"),
    ]),
    5: ("stickers", [
        ("sticker",   "tgadr sticker <set>",             "dothat tgadr sticker PackName",          "tg://addstickers?set=PackName"),
        ("emoji",     "tgadr emoji <set>",               "dothat tgadr emoji PackName",            "tg://addemoji?set=PackName"),
        ("stkr_tme",  "tgadr stkr_tme <set>",            "dothat tgadr stkr_tme PackName",         "https://t.me/addstickers/PackName"),
        ("emoji_tme", "tgadr emoji_tme <set>",           "dothat tgadr emoji_tme PackName",        "https://t.me/addemoji/PackName"),
        ("theme",     "tgadr theme <slug>",              "dothat tgadr theme night",               "tg://addtheme?slug=night"),
        ("theme_tme", "tgadr theme_tme <slug>",          "dothat tgadr theme_tme night",           "https://t.me/addtheme/night"),
        ("style",     "tgadr style <slug>",              "dothat tgadr style calm",                "tg://addstyle?slug=calm"),
        ("style_tme", "tgadr style_tme <slug>",          "dothat tgadr style_tme calm",            "https://t.me/addstyle/calm"),
        ("bg",        "tgadr bg <slug> [mode]",          "dothat tgadr bg pattern blur",           "tg://bg?slug=pattern&amp;mode=blur"),
        ("bg_tme",    "tgadr bg_tme <slug>",             "dothat tgadr bg_tme pattern",            "https://t.me/bg/pattern"),
    ]),
    6: ("wallpapers", [
        ("bgsolid",   "tgadr bgsolid <hex>",             "dothat tgadr bgsolid ff0000",            "tg://bg?color=ff0000"),
        ("bggrad",    "tgadr bggrad <top> <bot> [rot]",  "dothat tgadr bggrad ff0000 0000ff 45",   "tg://bg?gradient=ff0000-0000ff&amp;rotation=45"),
        ("bgfree",    "tgadr bgfree <h1> <h2> <h3>",     "dothat tgadr bgfree ff0000 00ff00 0000ff","tg://bg?gradient=ff0000~00ff00~0000ff"),
        ("bgsolid_t", "tgadr bgsolid_t <hex>",           "dothat tgadr bgsolid_t ff0000",          "https://t.me/bg/ff0000"),
        ("bggrad_t",  "tgadr bggrad_t <top> <bot>",      "dothat tgadr bggrad_t ff0000 0000ff",    "https://t.me/bg/ff0000-0000ff"),
        ("bgfree_t",  "tgadr bgfree_t <h1>~<h2>~<h3>",   "dothat tgadr bgfree_t ff0000~00ff00~0000ff","https://t.me/bg/ff0000~00ff00~0000ff"),
        ("hashtag",   "tgadr hashtag <tag>",             "dothat tgadr hashtag news",              "tg://search_hashtag?hashtag=news"),
        ("botcmd",    "tgadr botcmd <bot> <cmd>",        "dothat tgadr botcmd durov start",        "tg://bot_command?command=start&amp;bot=durov"),
        ("unsafe",    "tgadr unsafe <url>",              "dothat tgadr unsafe https://x.com",      "tg://unsafe_url?url=https%3A%2F%2Fx.com"),
        ("tme_link",  "tgadr tme_link <@u>",             "dothat tgadr tme_link durov",            "https://t.me/durov"),
    ]),
    7: ("bots", [
        ("start",     "tgadr start <bot> [param]",       "dothat tgadr start durov hi",            "tg://resolve?domain=durov&amp;start=hi"),
        ("startgrp",  "tgadr startgrp <bot> [param]",    "dothat tgadr startgrp bot hi",           "tg://resolve?domain=bot&amp;startgroup=hi"),
        ("startch",   "tgadr startch <bot> <perms>",     "dothat tgadr startch bot post_messages", "tg://resolve?domain=bot&amp;startchannel&amp;admin=post_messages"),
        ("startadmin","tgadr startadmin <bot> <perms>",  "dothat tgadr startadmin bot invite_users","tg://resolve?domain=bot&amp;startgroup&amp;admin=invite_users"),
        ("game",      "tgadr game <bot> <short>",        "dothat tgadr game bot tetris",           "tg://resolve?domain=bot&amp;game=tetris"),
        ("startapp",  "tgadr startapp <bot> <param>",    "dothat tgadr startapp bot abc",          "tg://resolve?domain=bot&amp;startapp=abc"),
        ("attach",    "tgadr attach <bot> <payload>",    "dothat tgadr attach bot xyz",            "tg://resolve?domain=bot&amp;startattach=xyz"),
        ("mainapp",   "tgadr mainapp <bot> <mode>",      "dothat tgadr mainapp bot compact",       "tg://resolve?domain=bot&amp;startapp=&amp;mode=compact"),
        ("tme_start", "tgadr tme_start <bot> <p>",       "dothat tgadr tme_start bot hi",          "https://t.me/bot?start=hi"),
        ("tme_app",   "tgadr tme_app <bot>",             "dothat tgadr tme_app bot",               "https://t.me/bot"),
    ]),
    8: ("stories", [
        ("story",     "tgadr story <@u> <id>",           "dothat tgadr story durov 42",            "tg://resolve?domain=durov&amp;story=42"),
        ("storylive", "tgadr storylive <@u>",            "dothat tgadr storylive durov",           "tg://resolve?domain=durov&amp;story=live"),
        ("album",     "tgadr album <@u> <album_id>",     "dothat tgadr album durov 7",             "tg://resolve?domain=durov&amp;album=7"),
        ("tme_story", "tgadr tme_story <@u> <id>",       "dothat tgadr tme_story durov 42",        "https://t.me/durov/s/42"),
        ("tme_live",  "tgadr tme_live <@u>",             "dothat tgadr tme_live durov",            "https://t.me/durov/s/live"),
        ("giftcode",  "tgadr giftcode <slug>",           "dothat tgadr giftcode abc",              "tg://giftcode?slug=abc"),
        ("nft",       "tgadr nft <slug>",                "dothat tgadr nft abc",                   "tg://nft?slug=abc"),
        ("auction",   "tgadr auction <slug>",            "dothat tgadr auction abc",               "tg://auction?slug=abc"),
        ("gshare",    "tgadr gshare <hash>",             "dothat tgadr gshare abc",                "tg://gshare?hash=abc"),
        ("sharegame", "tgadr sharegame <hash>",          "dothat tgadr sharegame abc",             "tg://share_game_score?hash=abc"),
    ]),
    9: ("settings", [
        ("settings",  "tgadr settings",                  "dothat tgadr settings",                  "tg://settings"),
        ("set_appear","tgadr set_appear",                "dothat tgadr set_appear",                "tg://settings/appearance"),
        ("set_themes","tgadr set_themes",                "dothat tgadr set_themes",                "tg://settings/appearance/themes"),
        ("set_wall",  "tgadr set_wall",                  "dothat tgadr set_wall",                  "tg://settings/appearance/wallpapers"),
        ("set_night", "tgadr set_night",                 "dothat tgadr set_night",                 "tg://settings/appearance/night-mode"),
        ("set_font",  "tgadr set_font",                  "dothat tgadr set_font",                  "tg://settings/appearance/text-size"),
        ("set_data",  "tgadr set_data",                  "dothat tgadr set_data",                  "tg://settings/data"),
        ("set_priv",  "tgadr set_priv",                  "dothat tgadr set_priv",                  "tg://settings/privacy"),
        ("set_lang",  "tgadr set_lang",                  "dothat tgadr set_lang",                  "tg://settings/language"),
        ("set_dev",   "tgadr set_dev",                   "dothat tgadr set_dev",                   "tg://settings/devices"),
    ]),
    10: ("stars", [
        ("stars",     "tgadr stars <balance>",           "dothat tgadr stars 100",                 "tg://stars_topup?balance=100"),
        ("stars_text","tgadr stars_text <text>",         "dothat tgadr stars_text hello",          "tg://stars_topup?balance=hello"),
        ("stars_set", "tgadr stars_set",                 "dothat tgadr stars_set",                 "tg://settings/stars"),
        ("wallet",    "tgadr wallet",                    "dothat tgadr wallet",                    "tg://wallet"),
        ("premium",   "tgadr premium",                   "dothat tgadr premium",                   "tg://premium_offer"),
        ("tme_stars", "tgadr tme_stars",                 "dothat tgadr tme_stars",                 "https://t.me/stars"),
        ("tme_prem",  "tgadr tme_prem",                  "dothat tgadr tme_prem",                  "https://t.me/premium"),
        ("channels",  "tgadr channels",                  "dothat tgadr channels",                  "tg://channels"),
        ("folder",    "tgadr folder <id>",               "dothat tgadr folder 0",                  "tg://dialog_filters?id=0"),
        ("invoice",   "tgadr invoice <slug>",            "dothat tgadr invoice abc",               "tg://invoice?slug=abc"),
    ]),
    11: ("misc", [
        ("debug",     "tgadr debug",                     "dothat tgadr debug",                     "tg://debug"),
        ("devices",   "tgadr devices",                   "dothat tgadr devices",                   "tg://devices"),
        ("autologin", "tgadr autologin",                 "dothat tgadr autologin",                 "tg://autologin"),
        ("bind",      "tgadr bind",                      "dothat tgadr bind",                      "tg://bind"),
        ("browser",   "tgadr browser",                   "dothat tgadr browser",                   "tg://browser"),
        ("newchat",   "tgadr newchat",                   "dothat tgadr newchat",                   "tg://newchat"),
        ("newgroup",  "tgadr newgroup",                  "dothat tgadr newgroup",                  "tg://newgroup"),
        ("saved",     "tgadr saved",                     "dothat tgadr saved",                     "tg://saved"),
        ("contacts",  "tgadr contacts",                  "dothat tgadr contacts",                  "tg://contacts"),
        ("calls",     "tgadr calls",                     "dothat tgadr calls",                     "tg://calls"),
    ]),
    12: ("share", [
        ("share_url", "tgadr share_url <url> <text>",    "dothat tgadr share_url https://t.me hi", "https://t.me/share/url?url=https%3A%2F%2Ft.me&amp;text=hi"),
        ("share_msg", "tgadr share_msg <url> <text>",    "dothat tgadr share_msg https://t.me hi", "https://t.me/msg/url?url=https%3A%2F%2Ft.me&amp;text=hi"),
        ("share_raw", "tgadr share_raw <url> <text>",    "dothat tgadr share_raw https://t.me hi", "https://t.me/share?url=https%3A%2F%2Ft.me&amp;text=hi"),
        ("share_dbl", "tgadr share_dbl <url> <text>",    "dothat tgadr share_dbl https://t.me hi", "https://t.me/share/url?url=https%253A%252F%252Ft.me&amp;text=hi"),
        ("business",  "tgadr business <slug>",           "dothat tgadr business abc",              "tg://message?slug=abc"),
        ("business_t","tgadr business_t <slug>",         "dothat tgadr business_t abc",            "https://t.me/m/abc"),
        ("need_upd",  "tgadr need_upd",                  "dothat tgadr need_upd",                  "tg://need_update_for_some_feature"),
        ("unsupp",    "tgadr unsupp",                    "dothat tgadr unsupp",                    "tg://some_unsupported_feature"),
        ("private",   "tgadr private <ch> <post>",       "dothat tgadr private 123 456",           "https://t.me/c/123/456"),
        ("premium_b", "tgadr premium_b",                 "dothat tgadr premium_b",                 "https://t.me/premium"),
    ]),
}


_PAGE_LIST = [
    ("1",  "user",      "resolve, share, user, contact, phone, profile"),
    ("2",  "messages",  "post, single, thread, comment, timestamp, task"),
    ("3",  "chats",     "join, invite, addlist, boost, call, videochat"),
    ("4",  "proxy",     "proxy, socks, setlang, confirmphone, oauth, login"),
    ("5",  "stickers",  "sticker, emoji, theme, style, bg"),
    ("6",  "wallpapers","bgsolid, bggrad, bgfree, hashtag, botcmd, unsafe"),
    ("7",  "bots",      "start, startgrp, startch, game, startapp, attach"),
    ("8",  "stories",   "story, storylive, album, giftcode, nft, auction"),
    ("9",  "settings",  "settings, appearance, themes, privacy, devices"),
    ("10", "stars",     "stars, wallet, premium, channels, folder, invoice"),
    ("11", "misc",      "debug, devices, autologin, bind, browser"),
    ("12", "share",     "share_url, share_msg, business, private"),
]


def _page_root(prefix):
    lines = ["<b>TGAdresses</b> <code>//</code> <code>v3.0.0</code>", "",
             "<b>pages</b> <code>//</code> <code>" + prefix + "dothat tgadr 1..12</code>"]
    for num, name, cmds in _PAGE_LIST:
        lines.append("<blockquote><b>" + num + ".</b> <b>" + name + "</b>\n"
                     "<code>" + prefix + "dothat tgadr " + num + "</code> — " + cmds + "</blockquote>")
    lines.append("")
    lines.append("<blockquote><b>--encode</b> — <code>dothat tgadr &lt;cmd&gt; ... --encode</code> url-encode итоговой ссылки</blockquote>")
    return "\n".join(lines)


def _page(n, prefix):
    pdata = _PAGES.get(n)
    if pdata is None:
        return None
    name, items = pdata
    total = len(_PAGES)
    lines = ["<b>TGAdresses</b> <code>//</code> <code>" + name + "</code> <code>//</code> <code>" + str(n) + "/" + str(total) + "</code>", ""]
    for label, usage, example, result in items:
        lines.append("<blockquote><b>" + label + "</b>\n"
                     "<code>" + prefix + "dothat " + usage + "</code>\n"
                     "→ " + result + "</blockquote>")
    lines.append("")
    lines.append("<b>nav</b> <code>//</code> <code>" + prefix + "dothat tgadr</code>")
    return "\n".join(lines)


def _encode_wrap(s):
    return _enc(s)


def _encode_wrap2(s):
    return _enc2(s)


async def _resolve_event(event, text):
    if getattr(event, "out", False):
        try:
            await event.edit(text, parse_mode="html")
            return
        except Exception:
            pass
    try:
        await event.respond(text, parse_mode="html")
    except Exception:
        try:
            await event.reply(text, parse_mode="html")
        except Exception:
            pass


class Plugin:
    manifest = MANIFEST

    async def on_load(self, ctx):
        try:
            ctx.logger.info("TGAdresses v3.0.0 loaded")
        except Exception:
            pass

    async def on_command(self, ctx):
        action = (ctx.get("action") or "").lower()
        if action != "tgadr":
            return None
        if not ctx.cfg.get("enabled", True):
            return None
        event = ctx.get("event")
        prefix = ctx.get("prefix") or "."
        args = (ctx.get("args") or "").strip()
        if args.lower().startswith("tgadr"):
            args = args[5:].strip()

        encode = 0
        if args.endswith("--encodex2"):
            encode = 2
            args = args[:-len("--encodex2")].strip()
        elif args.endswith("--encode"):
            encode = 1
            args = args[:-len("--encode")].strip()

        if not args:
            await _resolve_event(event, _page_root(prefix))
            return True

        first = args.split(maxsplit=1)[0]
        if first.isdigit():
            n = int(first)
            if 1 <= n <= 12:
                await _resolve_event(event, _page(n, prefix))
                return True
            await _resolve_event(event, "<b>err</b> — <code>no such page: " + str(n) + "</code>")
            return True

        if first in ("all", "list"):
            await _resolve_event(event, _page_root(prefix))
            return True

        rest = args[len(first):].strip()
        handler = getattr(self, "_c_" + first, None)
        if handler is None:
            await _resolve_event(event, "<b>err</b> — <code>unknown cmd: " + _esc(first) + "</code>\n\n" + _page_root(prefix))
            return True
        try:
            await handler(event, rest, encode)
        except Exception as e:
            await _resolve_event(event, "<b>err</b> — <code>" + _esc(str(e)) + "</code>")
        return True

    async def _c_resolve(self, event, rest, encode):
        p = rest.split(maxsplit=1)
        if not p:
            await _resolve_event(event, "<b>err</b> — <code>resolve &lt;@u&gt; [text]</code>")
            return
        domain, text = p[0].lstrip("@"), (p[1] if len(p) > 1 else "")
        url = "tg://resolve?domain=" + _enc(domain)
        if text:
            url += "&text=" + _enc(text)
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>resolve</b>\n" + url)

    async def _c_share(self, event, rest, encode):
        p = rest.split(maxsplit=1)
        if not p:
            await _resolve_event(event, "<b>err</b> — <code>share &lt;url&gt; [text]</code>")
            return
        url, text = p[0], (p[1] if len(p) > 1 else "")
        out = "https://t.me/share/url?url=" + _enc(url)
        if text:
            out += "&text=" + _enc(text)
        if encode == 1:
            out = _encode_wrap(out)
        elif encode == 2:
            out = _encode_wrap2(out)
        await _resolve_event(event, "<b>share</b>\n" + out)

    async def _c_user(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>user &lt;id&gt;</code>")
            return
        url = "tg://user?id=" + rest.strip()
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>user</b>\n" + url)

    async def _c_contact(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>contact &lt;token&gt;</code>")
            return
        url = "tg://contact?token=" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>contact</b>\n" + url)

    async def _c_phone(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>phone &lt;+79...&gt;</code>")
            return
        num = rest.strip().replace("+", "").replace(" ", "")
        url = "tg://resolve?phone=" + num
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>phone</b>\n" + url)

    async def _c_msg(self, event, rest, encode):
        p = rest.split()
        if not p:
            await _resolve_event(event, "<b>err</b> — <code>msg &lt;chat_id&gt; [msg_id]</code>")
            return
        url = "tg://openmessage?chat_id=" + p[0]
        if len(p) > 1:
            url += "&message_id=" + p[1]
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>msg</b>\n" + url)

    async def _c_post(self, event, rest, encode):
        p = rest.split()
        if len(p) < 2:
            await _resolve_event(event, "<b>err</b> — <code>post &lt;channel&gt; &lt;post&gt;</code>")
            return
        url = "tg://privatepost?channel=%s&amp;post=%s" % (p[0], p[1])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>post</b>\n" + url)

    async def _c_join(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>join &lt;hash&gt;</code>")
            return
        url = "tg://join?invite=" + _enc(rest.strip().lstrip("+"))
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>join</b>\n" + url)

    async def _c_invite(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>invite &lt;hash&gt;</code>")
            return
        url = "https://t.me/+" + rest.strip().lstrip("+")
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>invite</b>\n" + url)

    async def _c_proxy(self, event, rest, encode):
        p = rest.split()
        if len(p) < 3:
            await _resolve_event(event, "<b>err</b> — <code>proxy host port secret</code>")
            return
        url = "tg://proxy?server=%s&amp;port=%s&amp;secret=%s" % (_enc(p[0]), _enc(p[1]), _enc(p[2]))
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>proxy</b>\n" + url)

    async def _c_socks(self, event, rest, encode):
        p = rest.split()
        if len(p) < 2:
            await _resolve_event(event, "<b>err</b> — <code>socks host port [user] [pass]</code>")
            return
        url = "tg://socks?server=%s&amp;port=%s" % (_enc(p[0]), _enc(p[1]))
        if len(p) > 2:
            url += "&amp;user=" + _enc(p[2])
        if len(p) > 3:
            url += "&amp;pass=" + _enc(p[3])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>socks</b>\n" + url)

    async def _c_setlang(self, event, rest, encode):
        lang = (rest or "ru").strip()
        url = "tg://setlanguage?lang=" + _enc(lang)
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>setlang</b>\n" + url)

    async def _c_sticker(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>sticker &lt;set&gt;</code>")
            return
        url = "tg://addstickers?set=" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>sticker</b>\n" + url)

    async def _c_stars(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>stars &lt;balance&gt;</code>")
            return
        if rest.strip().isdigit():
            url = "tg://stars_topup?balance=" + rest.strip()
        else:
            url = "tg://stars_topup?balance=" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>stars</b>\n" + url)

    async def _c_call(self, event, rest, encode):
        p = rest.split()
        if not p:
            await _resolve_event(event, "<b>err</b> — <code>call &lt;slug&gt;</code>")
            return
        url = "tg://call?slug=" + _enc(p[0])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>call</b>\n" + url)

    async def _c_theme(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>theme &lt;slug&gt;</code>")
            return
        url = "tg://addtheme?slug=" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>theme</b>\n" + url)

    async def _c_bg(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>bg &lt;slug&gt; [mode]</code>")
            return
        p = rest.split()
        url = "tg://bg?slug=" + _enc(p[0])
        if len(p) > 1:
            url += "&amp;mode=" + _enc(p[1])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>bg</b>\n" + url)

    async def _c_start(self, event, rest, encode):
        p = rest.split(maxsplit=1)
        if not p:
            await _resolve_event(event, "<b>err</b> — <code>start &lt;bot&gt; [param]</code>")
            return
        url = "tg://resolve?domain=" + _enc(p[0].lstrip("@"))
        if len(p) > 1:
            url += "&amp;start=" + _enc(p[1])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>start</b>\n" + url)

    async def _c_story(self, event, rest, encode):
        p = rest.split()
        if len(p) < 2:
            await _resolve_event(event, "<b>err</b> — <code>story &lt;@u&gt; &lt;id&gt;</code>")
            return
        url = "tg://resolve?domain=%s&amp;story=%s" % (_enc(p[0].lstrip("@")), p[1])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>story</b>\n" + url)

    async def _c_boost(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>boost &lt;@ch&gt;</code>")
            return
        url = "tg://boost?domain=" + _enc(rest.strip().lstrip("@"))
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>boost</b>\n" + url)

    async def _c_folder(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>folder &lt;id&gt;</code>")
            return
        url = "tg://dialog_filters?id=" + rest.strip()
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>folder</b>\n" + url)

    async def _c_settings(self, event, rest, encode):
        url = "tg://settings"
        if rest.strip():
            url += "/" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>settings</b>\n" + url)

    async def _c_premium(self, event, rest, encode):
        url = "tg://premium_offer"
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>premium</b>\n" + url)

    async def _c_wallet(self, event, rest, encode):
        url = "tg://wallet"
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>wallet</b>\n" + url)

    async def _c_botcmd(self, event, rest, encode):
        p = rest.split(maxsplit=1)
        if len(p) < 2:
            await _resolve_event(event, "<b>err</b> — <code>botcmd &lt;bot&gt; &lt;cmd&gt;</code>")
            return
        url = "tg://bot_command?command=%s&amp;bot=%s" % (_enc(p[1]), _enc(p[0].lstrip("@")))
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>botcmd</b>\n" + url)

    async def _c_hashtag(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>hashtag &lt;tag&gt;</code>")
            return
        url = "tg://search_hashtag?hashtag=" + _enc(rest.strip().lstrip("#"))
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>hashtag</b>\n" + url)

    async def _c_oauth(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>oauth &lt;token&gt;</code>")
            return
        url = "tg://oauth?token=" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>oauth</b>\n" + url)

    async def _c_login(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>login &lt;code&gt;</code>")
            return
        url = "tg://login?code=" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>login</b>\n" + url)

    async def _c_private(self, event, rest, encode):
        p = rest.split()
        if len(p) < 2:
            await _resolve_event(event, "<b>err</b> — <code>private &lt;ch&gt; &lt;post&gt;</code>")
            return
        url = "https://t.me/c/%s/%s" % (p[0], p[1])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>private</b>\n" + url)

    async def _c_share_url(self, event, rest, encode):
        p = rest.split(maxsplit=1)
        if not p:
            await _resolve_event(event, "<b>err</b> — <code>share_url &lt;url&gt; [text]</code>")
            return
        url = "https://t.me/share/url?url=" + _enc(p[0])
        if len(p) > 1:
            url += "&amp;text=" + _enc(p[1])
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>share_url</b>\n" + url)

    async def _c_business(self, event, rest, encode):
        if not rest:
            await _resolve_event(event, "<b>err</b> — <code>business &lt;slug&gt;</code>")
            return
        url = "tg://message?slug=" + _enc(rest.strip())
        if encode == 1:
            url = _encode_wrap(url)
        elif encode == 2:
            url = _encode_wrap2(url)
        await _resolve_event(event, "<b>business</b>\n" + url)