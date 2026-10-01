"""Terminal — shell-команды из Telegram (только владелец)."""
from __future__ import annotations

import asyncio
import logging
import re
import time

from core.tetko import Module, command, shell, shell

log = logging.getLogger("TETKO.module.terminal")

MAX_OUTPUT = 3500
CMD_TIMEOUT = 30

BLACKLIST = [
    r"rm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*f?\s+/\s*$",
    r"rm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*f?\s+/\*",
    r"rm\s+(-[a-zA-Z]*\s+)*-r[f]?\s+~",
    r"rm\s+(-[a-zA-Z]*\s+)*-r[f]?\s+/sdcard",
    r"\bmkfs\b",
    r"\bdd\s+.*of=/dev/",
    r"\bdd\s+.*if=/dev/(zero|random|urandom)",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r">\s*/dev/(sd|block|mmcblk)",
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\binit\s+0\b",
    r"\bkill\s+-9\s+1\b",
    r"\bkillall\s+python\b",
    r"\bpkill\s+.*python\b",
    r"^\s*su(\s|$)",
    r"^\s*sudo(\s|$)",
]

_BLACKLIST_RE = [re.compile(p, re.IGNORECASE) for p in BLACKLIST]


def _is_blocked(cmd):
    for pattern in _BLACKLIST_RE:
        if pattern.search(cmd):
            return pattern.pattern
    return None


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _clean_error(text):
    cleaned = []
    for line in text.split("\n"):
        line = re.sub(r"^/[^:]*sh:\s*\d+:\s*", "", line)
        line = re.sub(r"^/data/[^:]+:\s*\d+:\s*", "", line)
        if line.strip():
            cleaned.append(line.strip())
    return "\n".join(cleaned) if cleaned else text.strip()


class TerminalModule(Module):
    name = "Terminal"
    __compat__ = "0.0.9.0"
    version = "0.5.0"
    author = "@anhedonuya"
    description = "Выполнение shell-команд (только владелец)"

    @command(
        name="t",
        aliases=["term", "sh"],
        description="Выполнить shell-команду",
        only_for="owner",
    )
    async def cmd_terminal(self, event, args):
        if not args:
            await event.edit(
                shell.wrap([
                    "usage    : .t <command>",
                    "example  : .t fastfetch",
                ], cmd="t", trailing=True),
                parse_mode="html",
            )
            return

        cmd = " ".join(args)

        reason = _is_blocked(cmd)
        if reason:
            await event.edit(
                shell.wrap([
                    "blocked  : true",
                    "matched  : " + reason,
                ], cmd=cmd, trailing=True),
                parse_mode="html",
            )
            log.warning("Terminal: blocked: %r (pattern: %s)" % (cmd, reason))
            return

        await event.edit(
            shell.wrap([], cmd=cmd, running=True, trailing=False),
            parse_mode="html",
        )

        started = time.perf_counter()

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=CMD_TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = time.perf_counter() - started
                await event.edit(
                    shell.wrap([
                        "timeout  : " + str(CMD_TIMEOUT) + "s",
                        "elapsed  : " + ("%.2f" % elapsed) + "s",
                    ], cmd=cmd, trailing=True),
                    parse_mode="html",
                )
                return

            elapsed = time.perf_counter() - started
            output = stdout.decode(errors="replace").rstrip()
            exit_code = proc.returncode

            if exit_code != 0:
                err = output or ("exit code " + str(exit_code))
                if len(err) > MAX_OUTPUT:
                    err = err[:MAX_OUTPUT]
                err_clean = _clean_error(err)
                await event.edit(
                    shell.wrap([
                        "exit     : " + str(exit_code),
                        "error    : " + err_clean,
                        "elapsed  : " + ("%.2f" % elapsed) + "s",
                    ], cmd=cmd, trailing=True),
                    parse_mode="html",
                )
                return

            if not output:
                output = "(no output)"

            truncated = False
            if len(output) > MAX_OUTPUT:
                output = output[:MAX_OUTPUT]
                truncated = True

            body = _esc(output)
            if truncated:
                body += "\n... truncated to " + str(MAX_OUTPUT) + " chars"

            await event.edit(
                shell.wrap([
                    body,
                    "",
                    "elapsed  : " + ("%.2f" % elapsed) + "s",
                ], cmd=cmd, trailing=True),
                parse_mode="html",
            )

        except Exception as e:
            elapsed = time.perf_counter() - started
            log.exception("terminal command failed")
            await event.edit(
                shell.wrap([
                    "error    : " + str(e),
                    "elapsed  : " + ("%.2f" % elapsed) + "s",
                ], cmd=cmd, trailing=True),
                parse_mode="html",
            )
