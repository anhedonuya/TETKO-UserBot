"""Terminal — выполнение shell-команд из Telegram (только для владельца)."""
from __future__ import annotations

import asyncio
import logging
import re

from core.tetko import Module, command

log = logging.getLogger("TETKO.module.terminal")

# Максимум символов в ответе
MAX_OUTPUT = 3500

# Таймаут выполнения команды (секунды)
CMD_TIMEOUT = 30

# ─── Блэклист опасных паттернов ───
# Это защита от СЛУЧАЙНОГО разрушения, не от целенаправленной атаки.
BLACKLIST = [
    # Разрушительные
    r"rm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*f?\s+/\s*$",
    r"rm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*f?\s+/\*",
    r"rm\s+(-[a-zA-Z]*\s+)*-r[f]?\s+~",
    r"rm\s+(-[a-zA-Z]*\s+)*-r[f]?\s+/sdcard",
    r"\bmkfs\b",
    r"\bdd\s+.*of=/dev/",
    r"\bdd\s+.*if=/dev/(zero|random|urandom)",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r">\s*/dev/(sd|block|mmcblk)",

    # Завершение системы
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\binit\s+0\b",

    # Убийство критичных процессов
    r"\bkill\s+-9\s+1\b",
    r"\bkillall\s+python\b",
    r"\bpkill\s+.*python\b",

    # Эскалация
    r"^\s*su(\s|$)",
    r"^\s*sudo(\s|$)",
]

_BLACKLIST_RE = [re.compile(p, re.IGNORECASE) for p in BLACKLIST]


def _is_blocked(cmd: str) -> str | None:
    """Вернуть причину блокировки или None."""
    for pattern in _BLACKLIST_RE:
        if pattern.search(cmd):
            return pattern.pattern
    return None


def _esc(text: str) -> str:
    """Экранирование HTML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _clean_error(text: str) -> str:
    """Убрать шум из stderr (пути /path/sh: N:)."""
    import re as _re
    cleaned = []
    for line in text.split("\n"):
        # убрать префикс "/path/to/sh: N:"
        line = _re.sub(r"^/[^:]*sh:\s*\d+:\s*", "", line)
        line = _re.sub(r"^/data/[^:]+:\s*\d+:\s*", "", line)
        if line.strip():
            cleaned.append(line.strip())
    return "\n".join(cleaned) if cleaned else text.strip()


class TerminalModule(Module):
    name = "Terminal"
    __compat__ = "0.0.9.0"
    version = "0.3.0"
    author = "@anhedonuya"
    description = "Выполнение shell-команд (только владелец)"

    @command(
        name="t",
        aliases=["term", "sh"],
        description="Выполнить shell-команду",
        only_for="owner",
    )
    async def cmd_terminal(self, event, args):
        """Выполнить shell-команду, отправить вывод в чат."""
        if not args:
            await event.edit(
                "🖥 <b>Terminal</b>\n"
                "Использование: <code>.t &lt;команда&gt;</code>\n"
                "Пример: <code>.t ls -la</code>",
                parse_mode="html",
            )
            return

        cmd = " ".join(args)

        # ── Проверка блэклиста ──
        reason = _is_blocked(cmd)
        if reason:
            await event.edit(
                f"🚫 <b>Команда заблокирована</b>\n"
                f"<code>{_esc(cmd)}</code>\n\n"
                f"<i>Совпал запрещённый паттерн:</i>\n"
                f"<code>{_esc(reason)}</code>",
                parse_mode="html",
            )
            log.warning(f"Terminal: blocked command: {cmd!r} (pattern: {reason})")
            return

        # ── executing ──
        await event.edit(
            f"<blockquote><b>executing:</b>\n"
            f"<code>{_esc(cmd)}</code></blockquote>",
            parse_mode="html",
        )

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
                await event.edit(
                    f"<b>❌ Error:</b>\n"
                    f"<blockquote><code>timeout ({CMD_TIMEOUT}s)</code></blockquote>",
                    parse_mode="html",
                )
                return

            output = stdout.decode(errors="replace").rstrip()
            exit_code = proc.returncode

            # ── Успех ──
            if exit_code == 0:
                if not output:
                    output = "(no output)"

                truncated = False
                if len(output) > MAX_OUTPUT:
                    output = output[:MAX_OUTPUT]
                    truncated = True

                text = (
                    f"<b>✅ Successfully:</b>\n"
                    f"<blockquote><pre>{_esc(output)}</pre></blockquote>"
                )
                if truncated:
                    text += f"\n<i>(truncated to {MAX_OUTPUT} chars)</i>"

                await event.edit(text, parse_mode="html")
                return

            # ── Ошибка (exit_code != 0) ──
            err = output or f"exit code {exit_code}"
            if len(err) > MAX_OUTPUT:
                err = err[:MAX_OUTPUT]

            err_clean = _clean_error(err)
            await event.edit(
                f"<b>❌ Error:</b>\n"
                f"<blockquote><code>{_esc(err_clean)}</code></blockquote>",
                parse_mode="html",
            )

        except Exception as e:
            log.exception("terminal command failed")
            await event.edit(
                f"<b>❌ Error:</b>\n"
                f"<blockquote><code>{_esc(str(e))}</code></blockquote>",
                parse_mode="html",
            )
