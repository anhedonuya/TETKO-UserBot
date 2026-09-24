"""Settings — настройки TETKO (язык, префикс и т.д.)."""
from __future__ import annotations

import json
from pathlib import Path

from core.tetko import Module, command, db_get, db_set

CONFIG_PATH = Path("config.json")


class Settings(Module):
    name = "Settings"
    version = "1.0.0"
    author = "@anhedonuya"
    __compat__ = "0.0.9.0"
    description = "Настройки TETKO UserBot"

    strings = {
        "ru": {
            "current": "🌐 <b>Текущий язык:</b> <code>{lang}</code>",
            "available": "📚 <b>Доступные языки:</b> {list}",
            "changed": "✅ Язык изменён на <code>{lang}</code>",
            "unknown": "❌ Язык <code>{lang}</code> не найден",
            "usage": "Использование: <code>.setlang &lt;код&gt;</code>",
        },
        "en": {
            "current": "🌐 <b>Current language:</b> <code>{lang}</code>",
            "available": "📚 <b>Available:</b> {list}",
            "changed": "✅ Language changed to <code>{lang}</code>",
            "unknown": "❌ Language <code>{lang}</code> not found",
            "usage": "Usage: <code>.setlang &lt;code&gt;</code>",
        },
    }

    def _t(self, key, **kwargs):
        lang = self.kernel.config.get("language", "ru") or "ru"
        s = self.strings.get(lang, self.strings["ru"])
        return s.get(key, key).format(**kwargs) if kwargs else s.get(key, key)

    @command(name="setlang", aliases=["lang"], description="Сменить язык бота")
    async def setlang_cmd(self, event, args):
        from core.langpacks import get_available_locales, clear_langpacks_cache

        available = get_available_locales()
        current = self.kernel.config.get("language", "ru") or "ru"

        if not args:
            await event.edit(
                self._t("current", lang=current)
                + "\n"
                + self._t("available", list=", ".join(f"<code>{x}</code>" for x in available)),
                parse_mode="html",
            )
            return

        new_lang = args[0].strip().lower()
        if new_lang not in available:
            await event.edit(
                self._t("unknown", lang=new_lang)
                + "\n"
                + self._t("available", list=", ".join(f"<code>{x}</code>" for x in available)),
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

        await event.edit(self._t("changed", lang=new_lang), parse_mode="html")
