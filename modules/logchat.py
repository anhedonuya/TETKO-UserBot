"""LogChat — управление лог-чатом (куда бот шлёт ошибки/обновления)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core.tetko import Module, command, shell

log = logging.getLogger("TETKO.module.logchat")
CONFIG_PATH = Path("config.json")
PROMPT = shell.PROMPT


def _esc(t):
    if t is None:
        return "-"
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _shell(lines, cmd=None):
    return shell.wrap(lines, cmd=cmd, running=False, trailing=True)


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


class LogChat(Module):
    name = "logchat"
    __compat__ = "0.9.1"
    version = "1.0.0"
    author = "@anhedonuya"
    description = {
        "ru": "Лог-чат для ошибок и обновлений",
        "en": "Log chat for errors and updates",
    }

    @command(name="logchat", description="Лог-чат: показ, установка, тест")
    async def cmd_logchat(self, event, args):
        cfg = _read_cfg()

        if not args:
            chat_id = cfg.get("log_chat_id")
            if not chat_id:
                await event.edit(_shell([
                    "logchat",
                    "",
                    "  status     not set",
                    "  hint       .logchat set <chat_id>",
                ]), parse_mode="html")
                return
            title = await self._chat_title(chat_id)
            await event.edit(_shell([
                "logchat",
                "",
                "  chat_id    " + str(chat_id),
                "  title      " + title,
                "  status     active",
            ]), parse_mode="html")
            return

        sub = args[0].lower()

        if sub == "set":
            if len(args) < 2:
                await event.edit(_shell([
                    "logchat set",
                    "",
                    "  error      chat_id required",
                    "  hint       .logchat set -1001234567890",
                ]), parse_mode="html")
                return
            try:
                chat_id = int(args[1])
            except (ValueError, TypeError):
                await event.edit(_shell([
                    "logchat set",
                    "",
                    "  error      chat_id must be integer",
                ]), parse_mode="html")
                return
            cfg["log_chat_id"] = chat_id
            _write_cfg(cfg)
            self.kernel.log_chat_id = chat_id
            self.kernel.config["log_chat_id"] = chat_id
            await event.edit(_shell([
                "logchat set",
                "",
                "  chat_id    " + str(chat_id),
                "  status     saved",
                "",
            ]), parse_mode="html")
            return

        if sub in ("off", "delete", "del"):
            cfg.pop("log_chat_id", None)
            _write_cfg(cfg)
            self.kernel.log_chat_id = None
            self.kernel.config.pop("log_chat_id", None)
            await event.edit(_shell([
                "logchat off",
                "",
                "  status     removed",
            ]), parse_mode="html")
            return

        await event.edit(_shell([
            "logchat --help",
            "",
            "  usage      .logchat               status",
            "             .logchat set <chat_id>",
            "             .logchat off",
        ]), parse_mode="html")

    async def _chat_title(self, chat_id):
        try:
            bot = getattr(self.kernel, "bot_client", None)
            if bot is None:
                return "-"
            chat = await bot.client.get_entity(chat_id)
            return getattr(chat, "title", None) or getattr(chat, "username", None) or "-"
        except Exception:
            return "-"
