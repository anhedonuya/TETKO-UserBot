from __future__ import annotations

import time

from core.tetko import Module, command, shell


class PingModule(Module):
    name = "ping"
    version = "1.3.0"
    author = "@anhedonuya"
    __compat__ = "0.0.9.0"
    description = "Latency check"

    @command(name="ping")
    async def ping_cmd(self, event):
        start = time.perf_counter()
        await event.edit(shell.wrap(["pong..."], cmd="ping", running=True, trailing=False), parse_mode="html")
        end = time.perf_counter()
        ms = round((end - start) * 1000, 2)
        text = self._t("pong", ms=str(ms) + "ms")
        await event.edit(shell.wrap([text], cmd="ping", trailing=True), parse_mode="html")

    @command(name="info")
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
            "style    : tetko-compat " + str(_compat),
            "python   : " + py,
            "os       : " + os_name,
            "engine   : Telethon",
            "authors  : @anhedonuya, @flexownerAL",
        ]
        await event.edit(shell.wrap(lines, cmd="info", trailing=True), parse_mode="html")
