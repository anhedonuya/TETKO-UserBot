import os
import sys
import aiohttp
from core.tetko import Module, command

class LoaderModule(Module):
    name = "Loader"
    description = "Управление динамической загрузкой и жизнью юзербота"
    author = "@anhedonuya & @flexownerAL"
    version = "1.0.0"

    @command(name="load", description="Загрузить модуль из файла или по URL")
    async def load_cmd(self, event):
        loader = getattr(self.client, "loader", None)
        if not loader:
            await event.edit("❌ **Ошибка:** Загрузчик недоступен.")
            return

        reply = await event.get_reply_message()
        args = event.pattern_match.group(1)

        mod_name = None

        if reply and reply.media:
            await event.edit("📥 Скачивание файла модуля...")
            file_path = await self.client.download_media(reply, file="modules/")
            if file_path and file_path.endswith(".py"):
                mod_name = os.path.basename(file_path)[:-3]
            else:
                await event.edit("❌ Файл должен иметь расширение `.py`.")
                return

        elif args and args.startswith("http"):
            url = args.strip()
            if "raw.githubusercontent.com" not in url and "github.com" in url:
                url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

            await event.edit("🌐 Загрузка модуля по URL...")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        code = await resp.text()
                        mod_name = url.split("/")[-1].replace(".py", "")
                        file_path = os.path.join("modules", f"{mod_name}.py")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(code)
                    else:
                        await event.edit(f"❌ Ошибка скачивания: HTTP status {resp.status}")
                        return
        else:
            await event.edit("❌ Ответьте на `.py` файл или укажите прямую ссылку.")
            return

        await event.edit(f"⚙️ Подключение модуля `{mod_name}`...")
        success = await loader.load_module(mod_name)
        if success:
            mod = loader.loaded_modules.get(mod_name)
            display_name = mod.name if mod else mod_name
            await event.edit(f"✅ Модуль **{display_name}** (`{mod_name}.py`) успешно загружен!")
        else:
            await event.edit(f"❌ Ошибка при инициализации модуля `{mod_name}`.")

    @command(name="unload", description="Выгрузить и удалить модуль")
    async def unload_cmd(self, event):
        loader = getattr(self.client, "loader", None)
        args = event.pattern_match.group(1)

        if not args or not loader:
            await event.edit("❌ Укажите имя модуля для выгрузки.")
            return

        mod_name = args.strip().replace(".py", "")
        if mod_name not in loader.loaded_modules:
            await event.edit(f"❌ Модуль `{mod_name}` не найден среди активных.")
            return

        await loader.unload_module(mod_name)
        file_path = os.path.join("modules", f"{mod_name}.py")
        if os.path.exists(file_path):
            os.remove(file_path)

        await event.edit(f"🗑 Модуль `{mod_name}` выгружен и удален из директории.")

    @command(name="restart", description="Перезапустить процесс юзербота")
    async def restart_cmd(self, event):
        await event.edit("🔄 **Перезапуск TETKO UserBot...**")
        os.execv(sys.executable, [sys.executable] + sys.argv)
