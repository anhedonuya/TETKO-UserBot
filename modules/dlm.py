"""DLM — Dynamic Loader of Modules (инлайн-менеджер модулей)."""
from __future__ import annotations

import logging
from pathlib import Path

from core.tetko import Module, command

log = logging.getLogger("TETKO.module.dlm")

REPO_RAW = "https://raw.githubusercontent.com/anhedonuya/TETKO-UserBot/main/modules"
MODULES_DIR = Path("modules")

CATALOG = [
    {"file": "ping.py", "name": "Ping", "desc": "Измерить пинг бота", "author": "@anhedonuya"},
    {"file": "tek.py", "name": "Tek", "desc": "Управление TETKO", "author": "@anhedonuya"},
    {"file": "loader.py", "name": "Loader", "desc": "Загрузчик модулей", "author": "@anhedonuya"},
    {"file": "terminal.py", "name": "Terminal", "desc": "Shell-команды из Telegram", "author": "@anhedonuya"},
]


class DLMModule(Module):
    name = "DLM"
    __compat__ = "0.0.9.0"
    version = "0.1.0"
    author = "@anhedonuya"
    description = "Dynamic Loader of Modules — инлайн-менеджер модулей"

    @command(name="dlm", aliases=["mods", "dlmods"], description="Менеджер модулей")
    async def dlm_cmd(self, event, args):
        await self._show_main(event, is_cb=False)

    async def _show_main(self, event_or_cb, is_cb: bool = False):
        kernel = self.kernel
        installed = [x for x in CATALOG if (MODULES_DIR / x["file"]).exists()]

        text = (
            "📦 <b>DLM — Dynamic Loader of Modules</b>\n\n"
            f"Всего в каталоге: <code>{len(CATALOG)}</code>\n"
            f"Установлено: <code>{len(installed)}</code>\n\n"
            "<i>Выбери модуль:</i>"
        )

        buttons = []
        for item in CATALOG:
            mark = "✅ " if (MODULES_DIR / item["file"]).exists() else "📥 "
            label = f"{mark}{item['name']}"

            async def on_click(cb_event, file=item["file"]):
                await self._show_module(cb_event, file)

            buttons.append([kernel.inline.make_button(label, on_click, ttl=600)])

        async def on_refresh(cb_event):
            await cb_event.answer("Обновлено")
            await self._show_main(cb_event, is_cb=True)

        buttons.append([kernel.inline.make_button("🔄 Обновить", on_refresh, ttl=600)])

        if is_cb:
            await kernel.inline.edit(event_or_cb, text, buttons)
        else:
            chat_id = event_or_cb.chat_id
            try:
                await event_or_cb.delete()
            except Exception:
                pass
            await kernel.inline.form(chat_id, text, buttons)

    async def _show_module(self, cb_event, file: str):
        item = next((x for x in CATALOG if x["file"] == file), None)
        if item is None:
            await cb_event.answer("Модуль не найден")
            return

        installed = (MODULES_DIR / file).exists()
        status = "✅ Установлен" if installed else "📥 Не установлен"

        text = (
            f"📦 <b>{item['name']}</b>\n\n"
            f"<b>Файл:</b> <code>{item['file']}</code>\n"
            f"<b>Автор:</b> {item['author']}\n"
            f"<b>Описание:</b> {item['desc']}\n"
            f"<b>Статус:</b> {status}"
        )

        async def on_download(cb_event, f=file, nm=item["name"]):
            await cb_event.answer(f"Скачиваю {nm}...")
            ok = await self._download_module(f)
            if ok:
                await cb_event.answer(f"✅ {nm} установлен. Перезапусти бота.")
            else:
                await cb_event.answer(f"❌ Не удалось скачать {nm}", alert=True)

        async def on_back(cb_event):
            await self._show_main(cb_event, is_cb=True)

        buttons = []
        if not installed:
            buttons.append([self.kernel.inline.make_button("📥 Скачать", on_download, ttl=600)])
        buttons.append([self.kernel.inline.make_button("← Назад", on_back, ttl=600)])

        await self.kernel.inline.edit(cb_event, text, buttons)

    async def _download_module(self, file: str) -> bool:
        url = f"{REPO_RAW}/{file}"
        target = MODULES_DIR / file
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        log.error(f"DLM: HTTP {resp.status} для {url}")
                        return False
                    content = await resp.text()

            if "class " not in content or "Module" not in content:
                log.error(f"DLM: {file} не похож на TETKO-модуль")
                return False

            target.write_text(content, encoding="utf-8")
            log.info(f"DLM: скачан {file} → {target}")
            return True
        except Exception as e:
            log.exception(f"DLM: ошибка скачивания {file}: {e}")
            return False
