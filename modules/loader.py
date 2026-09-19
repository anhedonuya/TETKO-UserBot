import os
import sys
import re
import asyncio
import aiohttp
from core.tetko import Module, command


MODULES_DIR = "modules_custom"


class Loader(Module):
    name = "Loader"
    __compat__ = "0.0.9.0"
    version = "1.2.0"
    author = "@anhedonuya & @flexownerAL"
    description = {
        "ru": "Динамическая загрузка, обновление и выгрузка модулей tetko-compat",
        "en": "Dynamic loader for tetko-compat modules",
    }
    config = {
        "auto_install_reqs": True,
    }

    async def _install_requirements(self, code: str, event):
        req_match = re.search(r"#\s*(?:req|requirements|pip):\s*(.+)", code, re.IGNORECASE)
        if req_match:
            packages = req_match.group(1).strip().split()
            if packages:
                await event.edit(f"📦 Установка зависимостей: <code>{', '.join(packages)}</code>", parse_mode="html")
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", *packages,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()

    def _extract_meta(self, code: str) -> dict:
        meta = {}

        def grab(pattern):
            m = re.search(pattern, code, re.MULTILINE)
            return m.group(1).strip() if m else None

        meta["name"] = grab(r'^\s*name\s*=\s*["\']([^"\']+)["\']')
        meta["version"] = grab(r'^\s*version\s*=\s*["\']([^"\']+)["\']')
        meta["author"] = grab(r'^\s*author\s*=\s*["\']([^"\']+)["\']')
        meta["compat"] = grab(r'^\s*__compat__\s*=\s*["\']([^"\']+)["\']')

        desc_str = grab(r'^\s*description\s*=\s*["\']([^"\']+)["\']')
        if desc_str:
            meta["description"] = desc_str
        else:
            desc_ru = grab(r'^\s*description\s*=\s*\{[^}]*["\']ru["\']\s*:\s*["\']([^"\']+)["\']')
            desc_en = grab(r'^\s*description\s*=\s*\{[^}]*["\']en["\']\s*:\s*["\']([^"\']+)["\']')
            meta["description"] = desc_ru or desc_en or "—"

        return meta

    def _esc(self, text) -> str:
        if text is None:
            return "—"
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @command("load", aliases=["dlmod"], doc="Загрузить модуль по файлу или ссылке")
    async def cmd_load(self, event, args):
        loader = getattr(self.client, "loader", None)
        reply = await event.get_reply_message()
        url_arg = args[0] if args else None

        os.makedirs(MODULES_DIR, exist_ok=True)

        mod_name = None
        code_content = None
        file_path = None

        if reply and reply.media and hasattr(reply.media, "document"):
            doc = reply.media.document
            file_name = next(
                (attr.file_name for attr in doc.attributes if hasattr(attr, "file_name")),
                None,
            )
            if file_name and file_name.endswith(".py"):
                await event.edit("📥 Скачивание файла модуля...")
                file_path = await self.client.download_media(reply, file=f"{MODULES_DIR}/")
                mod_name = os.path.basename(file_path)[:-3]
                with open(file_path, "r", encoding="utf-8") as f:
                    code_content = f.read()
            else:
                await event.edit("❌ Файл должен иметь расширение <code>.py</code>.", parse_mode="html")
                return

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
                        file_path = os.path.join(MODULES_DIR, f"{mod_name}.py")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(code_content)
                    else:
                        await event.edit(f"❌ Ошибка скачивания: HTTP <code>{resp.status}</code>", parse_mode="html")
                        return
        else:
            await event.edit(
                "❌ Ответьте на <code>.py</code> файл или укажите прямую ссылку.\n"
                "Использование: <code>.load &lt;url&gt;</code> или reply + <code>.load</code>",
                parse_mode="html",
            )
            return

        if code_content and self.cfg.get("auto_install_reqs"):
            await self._install_requirements(code_content, event)

        await event.edit(f"⚙️ Подключение модуля <code>{self._esc(mod_name)}</code>...", parse_mode="html")

        if loader and hasattr(loader, "load_module_from_file"):
            try:
                from pathlib import Path
                await loader.load_module_from_file(Path(file_path))

                meta = self._extract_meta(code_content or "")
                shown_name = meta.get("name") or mod_name
                shown_desc = meta.get("description") or "—"
                shown_compat = meta.get("compat") or "—"
                shown_author = meta.get("author") or "—"

                text = (
                    f"<blockquote><b>Модуль <i>{self._esc(shown_name)}</i> загружен!!</b></blockquote>\n\n"
                    f"<blockquote><i>Описание</i>: {self._esc(shown_desc)}\n"
                    f"Компат: <code>{self._esc(shown_compat)}</code></blockquote>\n\n"
                    f"<blockquote>Автор: {self._esc(shown_author)}</blockquote>"
                )
                await event.edit(text, parse_mode="html")
            except Exception as e:
                self.log.exception(f"load: ошибка инициализации {mod_name}")
                await event.edit(
                    f"❌ Ошибка при инициализации модуля <code>{self._esc(mod_name)}</code>:\n<code>{self._esc(e)}</code>",
                    parse_mode="html",
                )
        else:
            await event.edit(
                f"✅ Файл <code>{MODULES_DIR}/{self._esc(mod_name)}.py</code> сохранён. Перезапустите бота.",
                parse_mode="html",
            )

    @command("unload", doc="Выгрузить и удалить модуль")
    async def cmd_unload(self, event, args):
        loader = getattr(self.client, "loader", None)

        if not args:
            await event.edit("❌ Укажите имя модуля.\nИспользование: <code>.unload &lt;имя&gt;</code>", parse_mode="html")
            return

        mod_name = args[0].strip().replace(".py", "")

        if loader and hasattr(loader, "unload_module"):
            await loader.unload_module(mod_name)

        file_path = os.path.join(MODULES_DIR, f"{mod_name}.py")
        if os.path.exists(file_path):
            os.remove(file_path)

        await event.edit(f"🗑 Модуль <code>{self._esc(mod_name)}</code> выгружен и удалён.", parse_mode="html")

    @command("unlm", aliases=["getmod", "sendmod"], doc="Отправить файл модуля в чат", only_for="owner")
    async def cmd_unlm(self, event, args):
        if not args:
            installed = sorted([
                f[:-3] for f in os.listdir(MODULES_DIR)
                if f.endswith(".py") and not f.startswith("_")
            ]) if os.path.isdir(MODULES_DIR) else []
            if not installed:
                await event.edit("📂 Нет установленных модулей")
                return
            text = (
                "📂 <b>Установленные модули</b>\n\n"
                + "\n".join(f"• <code>{self._esc(name)}</code>" for name in installed)
                + "\n\n<i>Использование:</i> <code>.unlm &lt;имя&gt;</code>"
            )
            await event.edit(text, parse_mode="html")
            return

        name = args[0].strip().replace(".py", "")
        path = os.path.join(MODULES_DIR, f"{name}.py")
        if not os.path.exists(path):
            await event.edit(f"❌ Модуль <code>{self._esc(name)}</code> не найден", parse_mode="html")
            return

        try:
            size = os.path.getsize(path)
            await self.client.send_file(
                event.chat_id,
                file=path,
                caption=f"📄 <b>{self._esc(name)}.py</b>\n<i>Размер: {size} байт</i>",
                parse_mode="html",
                reply_to=getattr(event, "reply_to_msg_id", None),
            )
            try:
                await event.delete()
            except Exception:
                pass
        except Exception as e:
            self.log.exception(f"unlm: ошибка отправки {name}")
            await event.edit(f"❌ Ошибка отправки: <code>{self._esc(e)}</code>", parse_mode="html")

    @command("um", doc="Удалить пользовательский модуль", only_for="owner")
    async def cmd_um(self, event, args):
        """Удалить модуль из локальной папки modules_custom/ + выгрузить."""
        import os as _os

        def _list_user_modules() -> list:
            if not _os.path.isdir("modules_custom"):
                return []
            return sorted(
                f[:-3] for f in _os.listdir("modules_custom")
                if f.endswith(".py") and not f.startswith("_")
            )

        def _find_user_module(name: str):
            candidate = _os.path.join("modules_custom", f"{name}.py")
            return candidate if _os.path.exists(candidate) else None

        if not args:
            installed = _list_user_modules()
            if not installed:
                await event.edit(
                    "📂 <b>Нет пользовательских модулей</b>",
                    parse_mode="html",
                )
                return
            text = (
                "📂 <b>Пользовательские модули</b>\n\n"
                + "\n".join(f"• <code>{name}</code>" for name in installed)
                + "\n\n<i>Использование:</i> <code>.um &lt;имя&gt;</code>"
            )
            await event.edit(text, parse_mode="html")
            return

        name = args[0].strip()
        if name.endswith(".py"):
            name = name[:-3]

        path = _find_user_module(name)
        if not path:
            if _os.path.exists(_os.path.join("modules", f"{name}.py")):
                await event.edit(
                    f"❌ <code>{name}</code> — системный модуль, нельзя удалить",
                    parse_mode="html",
                )
                return
            await event.edit(
                f"❌ Модуль <code>{name}</code> не найден",
                parse_mode="html",
            )
            return

        loader = getattr(self.client, "loader", None)
        if loader is not None:
            try:
                await loader.unload_module(name)
            except Exception as e:
                self.log.warning(f"um: unload {name} failed: {e}")

        try:
            _os.remove(path)
        except Exception as e:
            await event.edit(
                f"❌ Ошибка удаления: <code>{e}</code>",
                parse_mode="html",
            )
            return

        await event.edit(
            f"🗑 Модуль <code>{name}</code> удалён",
            parse_mode="html",
        )

    @command("restart", doc="Перезапустить процесс TETKO", only_for="owner")
    async def cmd_restart(self, event):
        from core.tetko import db_set
        db_set("updates", "pending_reload", {
            "chat_id": event.chat_id,
            "message_id": event.message.id,
        })
        await event.edit(
            "<blockquote><b>🔄 Перезапуск TETKO UserBot...</b></blockquote>",
            parse_mode="html",
        )
        await asyncio.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)

