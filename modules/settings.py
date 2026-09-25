"""Settings — настройки TETKO (язык, префикс и т.д.)."""
from __future__ import annotations

import json
from pathlib import Path

from core.tetko import Module, command

CONFIG_PATH = Path("config.json")


class Settings(Module):
    name = "settings"
    version = "1.0.0"
    author = "@anhedonuya"
    __compat__ = "0.9.1"
    description = "Настройки TETKO UserBot"

    @command(name="setlang", aliases=["lang"], description="Сменить язык бота")
    async def setlang_cmd(self, event, args):
        from core.langpacks import get_available_locales, clear_langpacks_cache

        available = get_available_locales()
        current = self.kernel.config.get("language", "ru") or "ru"
        pretty = ", ".join(f"<code>{x}</code>" for x in available)

        if not args:
            await event.edit(
                self._t("setlang_current", lang=current)
                + "\n"
                + self._t("setlang_available", list=pretty),
                parse_mode="html",
            )
            return

        new_lang = args[0].strip().lower()
        if new_lang not in available:
            await event.edit(
                self._t("setlang_unknown", lang=new_lang)
                + "\n"
                + self._t("setlang_available", list=pretty),
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
            self.log.warning(f"setlang save: {e}")

        clear_langpacks_cache()

        await event.edit(
            self._t("setlang_changed", lang=new_lang),
            parse_mode="html",
        )
