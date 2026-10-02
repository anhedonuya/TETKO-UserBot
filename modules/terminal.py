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
    version = "0.6.0"
    author = "@anhedonuya"
    description = "Выполнение shell-команд (только владелец)"

    config = {
        "timeout": 30,
        "max_output": 3500,
        "live_update": True,
        "live_interval": 3,
        "show_exit_code": True,
        "show_elapsed": True,
    }

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
                    "usage    : " + str(self._p()) + "t <command>",
                    "example  : " + str(self._p()) + "t fastfetch",
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

        await self._run_live(event, cmd)

    def _p(self):
        try:
            return self.kernel.prefix
        except Exception:
            return "."

    async def _run_live(self, event, cmd):
        timeout = float(self.cfg.get("timeout", 30))
        max_out = int(self.cfg.get("max_output", 3500))
        live = bool(self.cfg.get("live_update", True))
        interval = float(self.cfg.get("live_interval", 3))
        show_exit = bool(self.cfg.get("show_exit_code", True))
        show_elapsed = bool(self.cfg.get("show_elapsed", True))

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
        except Exception as e:
            log.exception("terminal: spawn failed")
            await event.edit(
                shell.wrap(["error    : " + str(e)], cmd=cmd, trailing=True),
                parse_mode="html",
            )
            return

        buf = bytearray()
        last_edit = started
        timed_out = False

        async def _reader():
            nonlocal buf
            try:
                while True:
                    chunk = await proc.stdout.read(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)
            except Exception:
                pass

        reader_task = asyncio.create_task(_reader())

        try:
            while True:
                done, _ = await asyncio.wait({reader_task}, timeout=interval)
                now = time.perf_counter()

                if reader_task in done and proc.returncode is not None:
                    break

                if live and (now - last_edit) >= interval:
                    await self._flush(event, cmd, buf, now - started, False, max_out, show_elapsed)
                    last_edit = now

                if (now - started) >= timeout:
                    timed_out = True
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    await proc.wait()
                    break

            try:
                await asyncio.wait_for(reader_task, timeout=2)
            except Exception:
                reader_task.cancel()

            if not timed_out:
                try:
                    await proc.wait()
                except Exception:
                    pass

            elapsed = time.perf_counter() - started
            exit_code = proc.returncode

            if timed_out:
                await event.edit(
                    shell.wrap([
                        "timeout  : " + str(int(timeout)) + "s",
                        "elapsed  : " + ("%.2f" % elapsed) + "s",
                    ], cmd=cmd, trailing=True),
                    parse_mode="html",
                )
                return

            output = buf.decode(errors="replace").rstrip()

            if exit_code not in (0, None):
                if not output:
                    output = "exit code " + str(exit_code)
                if len(output) > max_out:
                    output = output[:max_out]
                await event.edit(
                    shell.wrap([
                        "exit     : " + str(exit_code),
                        "error    : " + _clean_error(output),
                        "elapsed  : " + ("%.2f" % elapsed) + "s",
                    ], cmd=cmd, trailing=True),
                    parse_mode="html",
                )
                return

            if not output:
                output = "(no output)"

            truncated = False
            if len(output) > max_out:
                output = output[:max_out]
                truncated = True

            body = _esc(output)
            if truncated:
                body += "\n... truncated to " + str(max_out) + " chars"

            tail = []
            if show_elapsed:
                tail.append("elapsed  : " + ("%.2f" % elapsed) + "s")
            if show_exit and exit_code is not None:
                tail.append("exit     : " + str(exit_code))

            await event.edit(
                shell.wrap([body, ""] + tail, cmd=cmd, trailing=True),
                parse_mode="html",
            )

        except Exception as e:
            log.exception("terminal: live run failed")
            try:
                await event.edit(
                    shell.wrap(["error    : " + str(e)], cmd=cmd, trailing=True),
                    parse_mode="html",
                )
            except Exception:
                pass

    async def _flush(self, event, cmd, buf, elapsed, running, max_out, show_elapsed):
        text = buf.decode(errors="replace")
        if len(text) > max_out:
            text = text[-max_out:]
        tail = []
        if show_elapsed:
            tail.append("elapsed  : " + ("%.2f" % elapsed) + "s")
        if running:
            tail.append("(running...)")
        try:
            await event.edit(
                shell.wrap([text or "(running...)", ""] + tail, cmd=cmd, trailing=True),
                parse_mode="html",
            )
        except Exception:
            pass
