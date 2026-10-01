import asyncio
import logging
import secrets
import time

from telethon.tl.types import InputMediaWebPage

from core.tetko import Module, command, shell

log = logging.getLogger("TETKO.module.ping")

PING_BANNER = "https://raw.githubusercontent.com/anhedonuya/TETKO-UserBot/main/ping_banner.png"

TG_DCS = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
}

PROMPT = shell.PROMPT


def _esc(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _term(lines):
    from core.tetko import shell as _sh
    return _sh.wrap(lines, cmd=None, running=False, trailing=False)


def _ms(v):
    if v is None or v < 0:
        return "timeout"
    return "%.2f ms" % v


class PingModule(Module):
    name = "Ping"
    __compat__ = "0.0.9.0"
    description = "Latency probe"
    author = "@anhedonuya"
    version = "3.2.0"

    async def _get_dc_id(self):
        try:
            dc_id = getattr(self.client.session, "dc_id", None)
            if dc_id:
                return int(dc_id)
        except Exception:
            pass
        try:
            me = await self.client.get_me()
            v = getattr(me, "dc_id", None)
            if v:
                return int(v)
        except Exception:
            pass
        try:
            from telethon.tl.functions.help import GetConfigRequest
            cfg = await self.client(GetConfigRequest())
            return getattr(cfg, "this_dc", None)
        except Exception:
            pass
        return None

    async def _tcp_probe(self, host, port, timeout=4.0):
        t0 = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            dt = (time.perf_counter() - t0) * 1000
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return dt
        except Exception:
            return None

    async def _icmp_probe(self, host="1.1.1.1"):
        t0 = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "2", host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=6)
            if proc.returncode == 0:
                return (time.perf_counter() - t0) * 1000
        except Exception:
            pass
        return None

    async def _tcp_ping_external(self, host="1.1.1.1", port=443):
        t0 = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=4.0
            )
            dt = (time.perf_counter() - t0) * 1000
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return dt
        except Exception:
            return None

    async def _dns_probe(self, host="telegram.org"):
        t0 = time.perf_counter()
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: __import__("socket").gethostbyname(host)
                ),
                timeout=5,
            )
            return (time.perf_counter() - t0) * 1000
        except Exception:
            return None

    async def _mtproto_probe(self):
        try:
            from telethon.tl.functions import PingRequest
            pid = int.from_bytes(secrets.token_bytes(8), "big", signed=True)
            t = time.perf_counter()
            await self.client(PingRequest(ping_id=pid))
            return (time.perf_counter() - t) * 1000
        except Exception as e:
            log.debug("mtproto: " + str(e))
            return None

    @command(name="ping", description="Ping tetko subsystems")
    async def ping_cmd(self, event):
        await event.edit(_term([
            PROMPT + " ping --tetko",
            "",
            "  resolving...",
        ]), parse_mode="html")

        t0 = time.perf_counter()
        await event.edit(_term([
            PROMPT + " ping --tetko",
            "",
            "  probing...",
        ]), parse_mode="html")
        edit_ms = (time.perf_counter() - t0) * 1000

        mt_ms = await self._mtproto_probe()
        dc_id = await self._get_dc_id()
        dc_ip = TG_DCS.get(dc_id) if dc_id else None

        tcp_ms = None
        if dc_ip:
            tcp_ms = await self._tcp_probe(dc_ip, 443)

        icmp_ms = await self._icmp_probe()
        if icmp_ms is None:
            icmp_ms = await self._tcp_ping_external("1.1.1.1", 443)

        dns_ms = await self._dns_probe()

        ok = sum(1 for v in (edit_ms, mt_ms, tcp_ms, icmp_ms, dns_ms) if v is not None)
        total = 5
        loss = int((total - ok) / total * 100)

        header_ip = dc_ip or "?"

        lines = [
            PROMPT + " ping --tetko",
            "",
            "PING tetko.mtproto (DC" + str(dc_id or "?") + " " + header_ip + ") 56(84) bytes of data.",
            "",
            "  edit       " + _ms(edit_ms),
            "  mtproto    " + _ms(mt_ms),
            "  tcp/443    " + _ms(tcp_ms),
            "  icmp       " + _ms(icmp_ms),
            "  dns        " + _ms(dns_ms),
            "  dc         " + (str(dc_id) if dc_id is not None else "unknown"),
            "",
            "--- tetko.mtproto ping statistics ---",
            str(total) + " probes transmitted, " + str(ok) + " received, " + str(loss) + "% packet loss",
            "",
            PROMPT + " ",
        ]
        text = _term(lines)

        try:
            from telethon.tl.functions.messages import EditMessageRequest
            parsed, entities = await self.client._parse_message_text(text, "html")
            await self.client(EditMessageRequest(
                peer=await event.get_input_chat(),
                id=event.id,
                message=parsed,
                entities=entities,
                media=InputMediaWebPage(PING_BANNER, force_large_media=True, optional=True),
                invert_media=True,
            ))
        except Exception as e:
            log.warning("ping: banner failed: " + str(e))
            await event.edit(text, parse_mode="html")

    @command(name="latency", aliases=["lat"], description="Quick latency")
    async def latency_cmd(self, event):
        await event.edit(_term([
            PROMPT + " latency",
            "",
            "  measuring...",
        ]), parse_mode="html")

        t0 = time.perf_counter()
        await event.edit(_term([
            PROMPT + " latency",
            "",
            "  probing...",
        ]), parse_mode="html")
        edit_ms = (time.perf_counter() - t0) * 1000

        mt_ms = await self._mtproto_probe()
        dc_id = await self._get_dc_id()
        dc_ip = TG_DCS.get(dc_id) if dc_id else None

        tcp_ms = None
        if dc_ip:
            tcp_ms = await self._tcp_probe(dc_ip, 443)

        vals = [v for v in (edit_ms, mt_ms, tcp_ms) if v is not None]
        avg = sum(vals) / len(vals) if vals else None
        jitter = max(vals) - min(vals) if len(vals) > 1 else 0.0

        lines = [
            PROMPT + " latency",
            "",
            "  edit       " + _ms(edit_ms),
            "  mtproto    " + _ms(mt_ms),
            "  tcp/443    " + _ms(tcp_ms),
            "  dc         " + (str(dc_id) if dc_id is not None else "unknown"),
            "",
            "  avg        " + _ms(avg),
            "  jitter     " + _ms(jitter),
            "",
            PROMPT + " ",
        ]
        text = _term(lines)

        # C БАННЕРОМ
        try:
            from telethon.tl.functions.messages import EditMessageRequest
            parsed, entities = await self.client._parse_message_text(text, "html")
            await self.client(EditMessageRequest(
                peer=await event.get_input_chat(),
                id=event.id,
                message=parsed,
                entities=entities,
                media=InputMediaWebPage(PING_BANNER, force_large_media=True, optional=True),
                invert_media=True,
            ))
        except Exception as e:
            log.warning("latency: banner failed: " + str(e))
            await event.edit(text, parse_mode="html")

    @command(name="info", description="TETKO system info")
    async def info_cmd(self, event):
        try:
            from core.tetko import __compat__ as _compat
        except Exception:
            _compat = "?"
        try:
            import sys as _sys
            py = _sys.version.split()[0]
        except Exception:
            py = "?"
        try:
            import platform as _plat
            os_name = _plat.system() + " " + _plat.release()
        except Exception:
            os_name = "?"

        lines = [
            PROMPT + " info",
            "",
            "  style      tetko-compat " + str(_compat),
            "  python     " + py,
            "  os         " + os_name,
            "  engine     Telethon",
            "  authors    @anhedonuya, @flexownerAL",
            "",
            PROMPT + " ",
        ]
        await event.edit(_term(lines), parse_mode="html")
