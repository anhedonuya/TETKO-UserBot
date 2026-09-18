import os
import sys
import re
import asyncio
import importlib
import aiohttp
from core.tetko import Module, command

class LoaderModule(Module):
    name = "Loader"
    description = "Динамическая загрузка, обновление и выгрузка модулей TETKO"
    author = "@anhedonuya & @flexownerAL"
    version = "1.1.0"

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

    @command(name="load", description="Загрузить модуль (в ответе на .py / код или по ссылке)")
    async def load_cmd(self, event):
        loader = getattr(self.client, "loader", None)
        if not loader:
            await event.edit("❌ **Ошибка:** Core Loader не привязан к клиенту.")
            return

        reply = await event.get_reply_message()
        args = event.pattern_match.group(1)

        mod_name = None
        code_content = None

        # 1. Загрузка из файла в ответе
        if reply and reply.media and hasattr(reply.media, 'document'):
            doc = reply.media.document
            file_name = next((attr.file_name for attr in doc.attributes if hasattr(attr, 'file_name')), None)
            
            if file_name and file_name.endswith('.py'):
                await event.edit("📥 **Скачивание файла модуля...**")
                file_path = await self.client.download_media(reply, file="modules/")
                mod_name = os.path.basename(file_path)[:-3]
                with open(file_path, "r", encoding="utf-8") as f:
                    code_content = f.read()
            else:
                await event.edit("❌ Файл должен иметь расширение `.py`.")
                return

        # 2. Загрузка из текста в ответе (если прислали сырой код)
        elif reply and reply.text and not args:
            code_content = reply.text
            # Пробуем вытащить имя из названия класса или комментария
            name_match = re.search(r"class\s+([A-Za-z0-9_]+)\s*\(\s*Module\s*\)", code_content)
            mod_name = name_match.group(1).lower() if name_match else f"mod_{int(event.id)}"
            file_path = os.path.join("modules", f"{mod_name}.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code_content)

        # 3. Загрузка по ссылке (URL)
        elif args and args.strip().startswith("http"):
            url = args.strip()
            # Конвертируем обычно ссылку GitHub в RAW
            if "github.com" in url and "raw.githubusercontent.com" not in url:
                url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

            await event.edit("🌐 **Загрузка модуля по URL...**")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        code_content = await resp.text()
                        mod_name = url.split("/")[-1].replace(".py", "").split("?")[0]
                        file_path = os.path.join("modules", f"{mod_name}.py")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(code_content)
                    else:
                        await event.edit(f"❌ **Ошибка скачивания:** HTTP Status `{resp.status}`.")
                        return
        else:
            await event.edit("❌ **Инструкция:** Ответьте на `.py` файл, текст с кодом или укажите ссылку:\n`.load https://raw.github...`")
            return

        # Проверка и установка внешних библиотек
        if code_content:
            await self._install_requirements(code_content, event)

        # Подключение через ядро
        await event.edit(f"⚙️ **Инициализация модуля `{mod_name}`...**")
        success = await loader.load_module(mod_name)

        if success:
            mod_inst = loader.loaded_modules.get(mod_name)
            title = mod_inst.name if mod_inst else mod_name
            ver = f"v{mod_inst.version}" if mod_inst else ""
            await event.edit(f"✅ **Модуль `{title}` {ver} успешно загружен!**\n📁 Файл: `modules/{mod_name}.py`")
        else:
            await event.edit(f"❌ **Ошибка при загрузке модуля `{mod_name}`.** Проверьте синтаксис файла.")

    @command(name="reload", description="Перезагрузить загруженный модуль")
    async def reload_cmd(self, event):
        loader = getattr(self.client, "loader", None)
        args = event.pattern_match.group(1)

        if not args or not loader:
            await event.edit("❌ Укажите имя модуля для перезагрузки (`.reload <имя_файла>`).")
            return

        mod_name = args.strip().replace(".py", "")
        if mod_name not in loader.loaded_modules:
            await event.edit(f"❌ Модуль `{mod_name}` не найден среди активных.")
            return

        await event.edit(f"🔄 Перезагрузка модуля `{mod_name}`...")
        await loader.unload_module(mod_name)
        success = await loader.load_module(mod_name)

        if success:
            await event.edit(f"✅ Модуль `{mod_name}` успешно перезагружен!")
        else:
            await event.edit(f"❌ Ошибка при перезагрузке модуля `{mod_name}`.")

    @command(name="unload", description="Выгрузить и удалить модуль")
    async def unload_cmd(self, event):
        loader = getattr(self.client, "loader", None)
        args = event.pattern_match.group(1)

        if not args or not loader:
            await event.edit("❌ Укажите имя модуля (`.unload <имя_файла>`).")
            return

        mod_name = args.strip().replace(".py", "")
        if mod_name not in loader.loaded_modules:
            await event.edit(f"❌ Модуль `{mod_name}` не активен.")
            return

        await loader.unload_module(mod_name)
        file_path = os.path.join("modules", f"{mod_name}.py")
        if os.path.exists(file_path):
            os.remove(file_path)

        await event.edit(f"🗑 **Модуль `{mod_name}` выгружен и удален.**")

    @command(name="restart", description="Перезапустить процесс TETKO")
    async def restart_cmd(self, event):
        await event.edit("🔄 **Перезапуск TETKO UserBot...**")
        os.execv(sys.executable, [sys.executable] + sys.argv)
