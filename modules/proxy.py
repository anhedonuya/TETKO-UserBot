"""Proxy — управление прокси-соединением TETKO."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from core.tetko import Module, command, shell

CONFIG_PATH = Path("config.json")
PROMPT = shell.PROMPT


def _esc(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _term(lines):
    from core.tetko import shell as _sh
    return _sh.wrap(lines, cmd=None, running=False, trailing=False)


def _read_cfg():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_cfg(cfg):
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _detect_mtproto_type(secret):
    if not secret:
        return "mtproto_dd"
    s = secret.strip()
    if s.startswith("ee"):
        return "mtproto_ee"
    if s.startswith("dd"):
        return "mtproto_dd"
    if all(c in "0123456789abcdefABCDEF" for c in s) and len(s) in (32, 34):
        return "mtproto_dd"
    return "mtproto_ee"


class Proxy(Module):
    name = "proxy"
    __compat__ = "0.9.1"
    version = "1.0.0"
    author = "@anhedonuya"
    description = {
        "ru": "Управление прокси TETKO",
        "en": "TETKO proxy control",
    }

    @command(name="proxy", description="Прокси: статус, настройка, тест")
    async def cmd_proxy(self, event, args):
        if not args:
            await self._status(event)
            return

        sub = args[0].lower()

        if sub in ("on",):
            cfg = _read_cfg()
            p = cfg.get("proxy") or {}
            if not p.get("host"):
                await event.edit(_term([
                    PROMPT + " proxy on",
                    "",
                    "  error      no proxy configured",
                    "",
                    PROMPT + " ",
                ]), parse_mode="html")
                return
            p["enabled"] = True
            cfg["proxy"] = p
            _write_cfg(cfg)
            await event.edit(_term([
                PROMPT + " proxy on",
                "",
                "  status     enabled",
                "  note       restart required (.restart)",
                "",
                PROMPT + " ",
            ]), parse_mode="html")
            return

        if sub in ("off",):
            cfg = _read_cfg()
            p = cfg.get("proxy") or {}
            p["enabled"] = False
            cfg["proxy"] = p
            _write_cfg(cfg)
            await event.edit(_term([
                PROMPT + " proxy off",
                "",
                "  status     disabled",
                "  note       restart required (.restart)",
                "",
                PROMPT + " ",
            ]), parse_mode="html")
            return

        if sub in ("delete", "del", "rm"):
            cfg = _read_cfg()
            cfg.pop("proxy", None)
            _write_cfg(cfg)
            await event.edit(_term([
                PROMPT + " proxy delete",
                "",
                "  status     removed from config.json",
                "",
                PROMPT + " ",
            ]), parse_mode="html")
            return

        if sub == "test":
            await self._test(event)
            return

        if sub == "set":
            await self._set_cmd(event, args[1:])
            return

        await self._usage(event)

    async def _usage(self, event):
        await event.edit(_term([
            PROMPT + " proxy --help",
            "",
            "  usage      .proxy                              status",
            "             .proxy set socks5 host port [u] [p]",
            "             .proxy set http   host port [u] [p]",
            "             .proxy set mtproto host port secret",
            "             .proxy set mtproto_dd host port secret",
            "             .proxy set mtproto_ee host port secret",
            "             .proxy on | off",
            "             .proxy test",
            "             .proxy delete",
            "",
            PROMPT + " ",
        ]), parse_mode="html")

    async def _status(self, event):
        cfg = _read_cfg()
        p = cfg.get("proxy") or {}
        rows = [
            PROMPT + " proxy --status",
            "",
        ]
        if not p.get("host"):
            rows += [
                "  state      not configured",
                "",
                "  hint       .proxy set socks5 <host> <port>",
                "",
                PROMPT + " ",
            ]
        else:
            rows += [
                "  type       " + str(p.get("type", "?")),
                "  host       " + str(p.get("host", "?")),
                "  port       " + str(p.get("port", "?")),
                "  enabled    " + ("yes" if p.get("enabled") else "no"),
            ]
            if p.get("user"):
                rows.append("  user       " + str(p.get("user")))
            if p.get("secret"):
                sec = str(p.get("secret"))
                rows.append("  secret     " + (sec[:8] + "..." if len(sec) > 8 else sec))
            rows += [
                "",
                "  note       change requires restart (.restart)",
                "",
                PROMPT + " ",
            ]
        await event.edit(_term(rows), parse_mode="html")

    async def _set_cmd(self, event, args):
        if len(args) < 3:
            await self._usage(event)
            return

        ptype = args[0].lower()
        host = args[1]
        try:
            port = int(args[2])
        except (ValueError, TypeError):
            await self._usage(event)
            return

        entry = {"enabled": True, "type": ptype, "host": host, "port": port}

        if ptype in ("socks5", "socks4", "http"):
            if len(args) >= 4:
                entry["user"] = args[3]
            if len(args) >= 5:
                entry["password"] = args[4]
        elif ptype == "mtproto":
            if len(args) < 4:
                await self._usage(event)
                return
            secret = args[3]
            entry["type"] = _detect_mtproto_type(secret)
            entry["secret"] = secret
        elif ptype in ("mtproto_dd", "mtproto_ee"):
            if len(args) < 4:
                await self._usage(event)
                return
            entry["secret"] = args[3]
        else:
            await self._usage(event)
            return

        cfg = _read_cfg()
        cfg["proxy"] = entry
        _write_cfg(cfg)

        rows = [
            PROMPT + " proxy set",
            "",
            "  type       " + str(entry.get("type")),
            "  host       " + str(host),
            "  port       " + str(port),
            "  status     saved",
            "",
            "  note       restart required (.restart)",
            "",
            PROMPT + " ",
        ]
        await event.edit(_term(rows), parse_mode="html")

    async def _test(self, event):
        cfg = _read_cfg()
        p = cfg.get("proxy") or {}
        if not p.get("host"):
            await event.edit(_term([
                PROMPT + " proxy test",
                "",
                "  error      no proxy configured",
                "",
                PROMPT + " ",
            ]), parse_mode="html")
            return

        host = p["host"]
        port = int(p["port"])
        ptype = (p.get("type") or "").lower()

        await event.edit(_term([
            PROMPT + " proxy test",
            "",
            "  connecting " + str(host) + ":" + str(port),
            "",
            PROMPT + " ",
        ]), parse_mode="html")

        t0 = time.perf_counter()
        ok = False
        err_msg = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=8.0,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            ok = True
        except Exception as e:
            err_msg = str(e)

        ms = round((time.perf_counter() - t0) * 1000, 2)

        if ok:
            rows = [
                PROMPT + " proxy test",
                "",
                "  target     " + str(host) + ":" + str(port),
                "  type       " + str(ptype),
                "  result     ok",
                "  latency    " + str(ms) + " ms",
                "",
                "--- proxy probe statistics ---",
                "1 probe transmitted, 1 received, 0% packet loss",
                "",
                PROMPT + " ",
            ]
        else:
            rows = [
                PROMPT + " proxy test",
                "",
                "  target     " + str(host) + ":" + str(port),
                "  type       " + str(ptype),
                "  result     failed",
                "  error      " + _esc(err_msg or "unknown"),
                "",
                "--- proxy probe statistics ---",
                "1 probe transmitted, 0 received, 100% packet loss",
                "",
                PROMPT + " ",
            ]

        await event.edit(_term(rows), parse_mode="html")
