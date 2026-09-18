import time
import sys
from core.tetko import Module, command

START_TIME = time.time()

class Tek(Module):
    name = "Tek"
    __compat__ = "0.0.9.0"
    version = "1.0.0"
    author = "@anhedonuya & @flexownerAL"
    description = {
        "ru": "Информационный модуль и управление отображением",
        "en": "Information module and display control",
    }
    config = {
        "show_hidden_count": True,
    }

    @command("tek", aliases=["modules", "mods"], doc="Показать список загруженных модулей")
    async def cmd_tek(self, event):
        loader = getattr(self.client, "loader", None)
        registry = getattr(self.kernel, "registry", None) if hasattr(self, "kernel") and self.kernel else None

        hidden = self.cfg.get("hidden_modules", [])
        
        # Получаем модули из реестра или лоадера
        loaded_mods = registry._modules if registry else getattr(loader, "loaded_modules", {})

        visible_mods = [m for name, m in loaded_mods.items() if name not in hidden]

        text = "🔻 **TETKO KOMPAT — Список модулей**\n\n"
        if self.cfg.get("show_hidden_count"):
            text += f"📦 Всего загружено: **{len(loaded_mods)}** | Скрыто: **{len(hidden)}**\n\n"

        for mod in visible_mods:
            mod_name = getattr(mod, "name", "Unnamed")
            mod_ver = getattr(mod, "version", "0.0.0")
            mod_desc = mod.get_description("ru") if hasattr(mod, "get_description") else getattr(mod, "description", "")
            text += f"▪️ **{mod_name}** (`v{mod_ver}`) — {mod_desc}\n"

        text += "\n💡 *Используйте `.tekhide <имя_модуля>` для скрытия модуля*"
        await event.edit(text)

    @command("tekhide", doc="Скрыть модуль из списка .tek")
    async def cmd_tekhide(self, event):
        args = event.pattern_match.group(1) if hasattr(event, "pattern_match") else None
        if not args:
            await event.edit("❌ Укажите имя модуля.")
            return

        mod_name = args.strip().replace(".py", "")
        hidden = self.cfg.get("hidden_modules", [])

        if mod_name not in hidden:
            hidden.append(mod_name)
            self.cfg.set("hidden_modules", hidden)
            await event.edit(f"🙈 Модуль `{mod_name}` скрыт из списка `.tek`.")
        else:
            await event.edit(f"ℹ️ Модуль `{mod_name}` уже скрыт.")

    @command("tekunhide", doc="Вернуть скрытый модуль в список .tek")
    async def cmd_tekunhide(self, event):
        args = event.pattern_match.group(1) if hasattr(event, "pattern_match") else None
        if not args:
            await event.edit("❌ Укажите имя модуля.")
            return

        mod_name = args.strip().replace(".py", "")
        hidden = self.cfg.get("hidden_modules", [])

        if mod_name in hidden:
            hidden.remove(mod_name)
            self.cfg.set("hidden_modules", hidden)
            await event.edit(f"👁 Модуль `{mod_name}` снова отображается в `.tek`.")
        else:
            await event.edit(f"ℹ️ Модуль `{mod_name}` не находится в скрытых.")

    @command("tekcfg", doc="Информация о состоянии системы TETKO")
    async def cmd_tekcfg(self, event):
        uptime = round(time.time() - START_TIME)
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)

        registry = getattr(self.kernel, "registry", None) if hasattr(self, "kernel") and self.kernel else None
        total_mods = registry.modules_count if registry else 0

        text = (
            "🔻 **TETKO System Config**\n\n"
            f"⏱ **Время работы:** `{hours}ч {minutes}м {seconds}с`\n"
            f"📦 **Активные модули:** `{total_mods}`\n"
            f"🐍 **Версия Python:** `{sys.version.split()[0]}`\n"
            f"⚡ **Стандарт:** `TETKO-COMPAT 0.0.9.0`\n"
            f"👥 **Создатели:** @anhedonuya, @flexownerAL"
        )
        await event.edit(text)
