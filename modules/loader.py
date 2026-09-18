import os
import sys
import re
import asyncio
import aiohttp
from core.tetko import Module, command


class Loader(Module):
    name = "Loader"
    __compat__ = "0.0.9.0"
    version = "1.1.0"
    author = "@anhedonuya & @flexownerAL"
    description = {
        "ru": "Динамическая загрузка, обновление и выгрузка модулей tetko-compat",
        "en": "Dynamic loader for tetko-compat modules",
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
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

    @command("load", aliases=["dlmod"], doc="Загрузить модуль по файлу, коду или ссылке")
    async def cmd_load(self, event, args):
        loader = getattr(self.client, "loader", None)
        reply = await event.get_reply_message()
        url_arg = args[0] if args else None

        mod_name = None
        code_content = None

        # 1. Из файла .py (ответом на сообщение)
        if reply and reply.media and hasattr(reply.media, "document"):
            doc = reply.media.document
            file_name = next(
                (attr.file_name for attr in doc.attributes if hasattr(attr, "file_name")),
                None,
            )
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
        elif url_arg and url_arg.strip().startswith("http"):
            url = url_arg.strip()
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
            await event.edit(
                "❌ Ответьте на `.py` файл или укажите прямую ссылку.\n"
                "Использование: `.load <url>` или reply + `.load`"
            )
            return

        if code_content and self.cfg.get("auto_install_reqs"):
            await self._install_requirements(code_content, event)

        await event.edit(f"⚙️ Подключение модуля `{mod_name}`...")
        if loader and hasattr(loader, "load_module_from_file"):
            try:
                from pathlib import Path
                await loader.load_module_from_file(Path("modules") / f"{mod_name}.py")
                await event.edit(f"✅ Модуль `{mod_name}` успешно загружен в TETKO!")
            except Exception as e:
                await event.edit(f"❌ Ошибка при инициализации модуля `{mod_name}`:\n`{e}`")
        else:
            await event.edit(
                f"✅ Файл `modules/{mod_name}.py` сохранён. Перезапустите бота."
            )

    @command("unload", doc="Выгрузить и удалить модуль")
    async def cmd_unload(self, event, args):
        loader = getattr(self.client, "loader", None)

        if not args:
            await event.edit("❌ Укажите имя модуля.\nИспользование: `.unload <имя>`")
            return

        mod_name = args[0].strip().replace(".py", "")

        if loader and hasattr(loader, "unload_module"):
            await loader.unload_module(mod_name)

        file_path = os.path.join("modules", f"{mod_name}.py")
        if os.path.exists(file_path):
            os.remove(file_path)

        await event.edit(f"🗑 Модуль `{mod_name}` выгружен и удалён.")

    @command(
        "unlm",
        aliases=["getmod", "sendmod"],
        doc="Отправить файл модуля в чат",
        only_for="owner",
    )
    async def cmd_unlm(self, event, args):
        """Выгрузить файл модуля из modules/ прямо в чат.

        Использование:
          .unlm <имя>    — отправить modules/<имя>.py
          .unlm          — список доступных модулей
        """
        modules_dir = "modules"

        if not args:
            installed = sorted([
                f[:-3] for f in os.listdir(modules_dir)
                if f.endswith(".py") and not f.startswith("_")
            ]) if os.path.isdir(modules_dir) else []
            if not installed:
                await event.edit("📂 Нет установленных модулей")
                return
            text = (
                "📂 <b>Установленные модули</b>\n\n"
                + "\n".join(f"• <code>{name}</code>" for name in installed)
                + "\n\n<i>Использование:</i> <code>.unlm &lt;имя&gt;</code>"
            )
            await event.edit(text, parse_mode="html")
            return

        name = args[0].strip()
        if name.endswith(".py"):
            name = name[:-3]

        path = os.path.join(modules_dir, f"{name}.py")
        if not os.path.exists(path):
            await event.edit(
                f"❌ Модуль <code>{name}</code> не найден",
                parse_mode="html",
            )
            return

        try:
            size = os.path.getsize(path)
            await self.client.send_file(
                event.chat_id,
                file=path,
                caption=f"📄 <b>{name}.py</b>\n<i>Размер: {size} байт</i>",
                parse_mode="html",
                reply_to=getattr(event, "reply_to_msg_id", None),
            )
            try:
                await event.delete()
            except Exception:
                pass
        except Exception as e:
            self.log.exception(f"unlm: ошибка отправки {name}: {e}")
            await event.edit(
                f"❌ Ошибка отправки: <code>{e}</code>",
                parse_mode="html",
            )

    @command("restart", doc="Перезапустить процесс TETKO")
    async def cmd_restart(self, event):
        await event.edit("🔄 **Перезапуск TETKO UserBot...**")
        os.execv(sys.executable, [sys.executable] + sys.argv)
