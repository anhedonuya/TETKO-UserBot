import os
import sys
import re
import asyncio
import aiohttp
from core.tetko import Module, command

class Loader(Module):
    name = "Loader"
    version = "1.0.0"
    author = "@anhedonuya & @flexownerAL"
    description = {
        "ru": "Динамическая загрузка, обновление и выгрузка модулей TETKO-COMPAT",
        "en": "Dynamic loader for TETKO-COMPAT modules",
    }
    config = {
        "auto_install_reqs": True,
    }

    async def _install_requirements(self, code: str, event):
        """Проверяет и автоматически устанавливает pip-зависимости модуля."""
        req_match = re.search(r"#\s*(?:req|requirements|pip):\s*(.+)", code, re.IGNORECASE)
        if req_match:
            packages = req_match.group(1).strip().split()
            if packages:
                await event.edit(f"📦 **Установка зависимостей:** `{', '.join(packages)}`...")
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", *packages,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

    @command("load", aliases=["dlmod"], doc="Загрузить модуль по файлу, коду или ссылке")
    async def cmd_load(self, event):
        loader = getattr(self.client, "loader", None)
        reply = await event.get_reply_message()
        args = event.pattern_match.group(1) if hasattr(event, "pattern_match") else None

        mod_name = None
        code_content = None

        # 1. Из файла .py
        if reply and reply.media and hasattr(reply.media, "document"):
            doc = reply.media.document
            file_name = next((attr.file_name for attr in doc.attributes if hasattr(attr, "file_name")), None)
            if file_name and file_name.endswith(".py"):
                await event.edit("📥 Скачивание файла модуля...")
                file_path = await self.client.download_media(reply, file="modules/")
                mod_name = os.path.basename(file_path)[:-3]
                with open(file_path, "r", encoding="utf-8") as f:
                    code_content = f.read()
            else:
                await event.edit("❌ Файл должен иметь расширение `.py`.")
                return

        # 2. Из ссылки URL
        elif args and args.strip().startswith("http"):
            url = args.strip()
            if "github.com" in url and "raw.githubusercontent.com" not in url:
                url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

            await event.edit("🌐 Скачивание модуля по URL...")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        code_content = await resp.text()
                        mod_name = url.split("/")[-1].replace(".py", "").split("?")[0]
                        file_path = os.path.join("modules", f"{mod_name}.py")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(code_content)
                    else:
                        await event.edit(f"❌ Ошибка скачивания: HTTP status `{resp.status}`.")
                        return
        else:
            await event.edit("❌ Ответьте на `.py` файл или укажите прямую ссылку (`.load <url>`).")
            return

        if code_content and self.cfg.get("auto_install_reqs"):
            await self._install_requirements(code_content, event)

        await event.edit(f"⚙️ Подключение модуля `{mod_name}`...")
        if loader and hasattr(loader, "load_module"):
            success = await loader.load_module(mod_name)
            if success:
                await event.edit(f"✅ Модуль `{mod_name}` успешно загружен в TETKO!")
            else:
                await event.edit(f"❌ Ошибка при инициализации модуля `{mod_name}`.")
        else:
            await event.edit(f"✅ Файл `modules/{mod_name}.py` сохранен. Перезапустите бота, если лоадер не активен.")

    @command("unload", doc="Выгрузить и удалить модуль")
    async def cmd_unload(self, event):
        loader = getattr(self.client, "loader", None)
        args = event.pattern_match.group(1) if hasattr(event, "pattern_match") else None

        if not args:
            await event.edit("❌ Укажите имя модуля (`.unload <имя_файла>`).")
            return

        mod_name = args.strip().replace(".py", "")

        if loader and hasattr(loader, "unload_module"):
            await loader.unload_module(mod_name)

        file_path = os.path.join("modules", f"{mod_name}.py")
        if os.path.exists(file_path):
            os.remove(file_path)

        await event.edit(f"🗑 Модуль `{mod_name}` выгружен и удален.")

    @command("restart", doc="Перезапустить процесс TETKO")
    async def cmd_restart(self, event):
        await event.edit("🔄 **Перезапуск TETKO UserBot...**")
        os.execv(sys.executable, [sys.executable] + sys.argv)
