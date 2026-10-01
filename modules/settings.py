"""Settings — TETKO userbot settings."""
from __future__ import annotations

import json
from pathlib import Path

from core.tetko import Module, command

CONFIG_PATH = Path("config.json")


def _bq(msg):
    return "<blockquote><b>" + msg + "</b></blockquote>"


def _bq_i(msg):
    return "<blockquote>" + msg + "</blockquote>"


class Settings(Module):
    name = "settings"
    version = "1.1.0"
    author = "@anhedonuya"
    __compat__ = "0.0.9.0"
    description = "TETKO userbot settings"

    @command(name="setlang", aliases=["lang"], description="Change bot language")
    async def setlang_cmd(self, event, args):
        from core.langpacks import get_available_locales, clear_langpacks_cache

        available = get_available_locales()
        current = self.kernel.config.get("language", "ru") or "ru"
        pretty = ", ".join("<code>" + str(x) + "</code>" for x in available)

        if not args:
            await event.edit(
                _bq("Current language: " + str(current)) + "\n"
                + _bq_i("Available: " + pretty),
                parse_mode="html",
            )
            return

        new_lang = args[0].strip().lower()
        if new_lang not in available:
            await event.edit(
                _bq("Unknown language: " + str(new_lang)) + "\n"
                + _bq_i("Available: " + pretty),
                parse_mode="html",
            )
            return

        self.kernel.config["language"] = new_lang
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg["language"] = new_lang
            CONFIG_PATH.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            self.log.warning("setlang save: " + str(e))

        clear_langpacks_cache()

        await event.edit(
            _bq("Language changed to " + str(new_lang)),
            parse_mode="html",
        )
