import time
import sys
from core.tetko import Module, command

START_TIME = time.time()

class TekModule(Module):
    name = "Tek"
    description = "Информационный модуль и управление отображением"
    author = "@anhedonuya & @flexownerAL"
    version = "1.0.0"

    @command(name="tek", description="Показать список загруженных модулей")
    async def tek_cmd(self, event):
        loader = getattr(self.client, "loader", None)
        if not loader:
            await event.edit("❌ **Ошибка:** Загрузчик модулей не доступен.")
            return

        hidden = self.db.get("system", "hidden_modules", []) if self.db else []
        modules = loader.loaded_modules

        visible_mods = [m for name, m in modules.items() if name not in hidden]

        text = "🔻 **TETKO KOMPAT — Список модулей**\n\n"
        text += f"📦 Всего загружено: **{len(modules)}** | Скрыто: **{len(hidden)}**\n\n"

        for mod in visible_mods:
            text += f"▪️ **{mod.name}** (`v{mod.version}`) — {mod.description}\n"

        text += "\n💡 *Используйте `.tekhide <имя_файла>` для скрытия модуля*"
        await event.edit(text)

    @command(name="tekhide", description="Скрыть модуль из списка .tek")
    async def tekhide_cmd(self, event):
        args = event.pattern_match.group(1)
        if not args:
            await event.edit("❌ Укажите имя файла модуля (без `.py`).")
            return

        mod_name = args.strip().replace(".py", "")
        hidden = self.db.get("system", "hidden_modules", []) if self.db else []

        if mod_name not in hidden:
            hidden.append(mod_name)
            if self.db:
                self.db.set("system", "hidden_modules", hidden)
            await event.edit(f"🙈 Модуль `{mod_name}` скрыт из списка `.tek`.")
        else:
            await event.edit(f"ℹ️ Модуль `{mod_name}` уже скрыт.")

    @command(name="tekunhide", description="Вернуть скрытый модуль в список .tek")
    async def tekunhide_cmd(self, event):
        args = event.pattern_match.group(1)
        if not args:
            await event.edit("❌ Укажите имя файла модуля.")
            return

        mod_name = args.strip().replace(".py", "")
        hidden = self.db.get("system", "hidden_modules", []) if self.db else []

        if mod_name in hidden:
            hidden.remove(mod_name)
            if self.db:
                self.db.set("system", "hidden_modules", hidden)
            await event.edit(f"👁 Модуль `{mod_name}` снова отображается в `.tek`.")
        else:
            await event.edit(f"ℹ️ Модуль `{mod_name}` не находится в списке скрытых.")

    @command(name="tekcfg", description="Информация о состоянии системы TETKO")
    async def tekcfg_cmd(self, event):
        uptime = round(time.time() - START_TIME)
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)

        loader = getattr(self.client, "loader", None)
        total_mods = len(loader.loaded_modules) if loader else 0

        text = (
            "🔻 **TETKO System Config**\n\n"
            f"⏱ **Время работы:** `{hours}ч {minutes}м {seconds}с`\n"
            f"📦 **Активные модули:** `{total_mods}`\n"
            f"🐍 **Версия Python:** `{sys.version.split()[0]}`\n"
            f"⚡ **Стандарт:** `TETKO KOMPAT v1.0`\n"
            f"👥 **Создатели:** @anhedonuya, @flexownerAL"
        )
        await event.edit(text)
