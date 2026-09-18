"""DLM — Dynamic Loader of Modules.

Системный модуль: тянет модули строго из официального каталога
flexOwnerAL/repo-TETKO-modules.
Автообновление: проверяет новые версии, скачивает и перезагружает.
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Optional

from core.tetko import Module, command, loop

log = logging.getLogger("TETKO.module.dlm")

# ─── Источник модулей (СТРОГО этот репозиторий) ───
CATALOG_REPO = "flexOwnerAL/repo-TETKO-modules"
CATALOG_BRANCH = "main"
CATALOG_API = f"https://api.github.com/repos/{CATALOG_REPO}/contents/"
CATALOG_RAW = f"https://raw.githubusercontent.com/{CATALOG_REPO}/{CATALOG_BRANCH}"

MODULES_DIR = Path("modules")
CACHE_TTL = 300  # 5 минут — кэш каталога

# Версия модуля (по дефолту). Переопредели в модуле.
VERSION_RE = re.compile(r'^\s*version\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def _parse_version(v: str) -> tuple:
    """'1.0.2' → (1, 0, 2)."""
    parts = []
    for p in str(v).split("."):
        p = p.split("-")[0]
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _compare_versions(v1: str, v2: str) -> int:
    """-1 если v1 < v2, 0 если равны, 1 если v1 > v2."""
    t1 = _parse_version(v1)
    t2 = _parse_version(v2)
    if t1 < t2:
        return -1
    if t1 > t2:
        return 1
    return 0


class DLMModule(Module):
    name = "DLM"
    __compat__ = "0.0.9.0"
    version = "1.0.0"
    author = "@anhedonuya"
    description = "Dynamic Loader of Modules — установка и автообновление модулей"

    config = {
        "auto_update": True,        # автообновлять существующие модули
        "auto_install_new": False,  # автоустанавливать новые модули
        "update_interval": 3600,    # период проверки (сек)
        "notify_updates": True,     # уведомлять владельца в ЛС
    }

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self._catalog_cache: Optional[list[dict]] = None
        self._cache_time: float = 0

    # ── Загрузка / выгрузка ──
    async def on_load(self):
        self.log.info("DLM loaded")

    async def on_unload(self):
        self.log.info("DLM unloaded")

    # ── КАТАЛОГ ──
    async def _fetch_catalog(self, force: bool = False) -> list[dict]:
        """Получить список модулей из GitHub API (с кэшем)."""
        now = time.time()
        if not force and self._catalog_cache is not None and (now - self._cache_time) < CACHE_TTL:
            return self._catalog_cache

        items: list[dict] = []
        try:
            import aiohttp
            headers = {"Accept": "application/vnd.github+json"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(CATALOG_API, timeout=15) as resp:
                    if resp.status != 200:
                        log.error(f"DLM: GitHub API вернул {resp.status}")
                        return self._catalog_cache or []
                    data = await resp.json()

            for entry in data:
                if entry.get("type") != "file":
                    continue
                name = entry.get("name", "")
                if not name.endswith(".py") or name.startswith("_"):
                    continue
                items.append({
                    "file": name,
                    "name": name[:-3],
                    "size": entry.get("size", 0),
                    "url": entry.get("download_url") or f"{CATALOG_RAW}/{name}",
                })
        except Exception as e:
            log.exception(f"DLM: ошибка получения каталога: {e}")
            return self._catalog_cache or []

        self._catalog_cache = items
        self._cache_time = now
        return items

    # ── ВЕРСИИ ──
    async def _get_remote_version(self, file: str) -> Optional[str]:
        """Скачать raw-файл и вытащить version."""
        url = f"{CATALOG_RAW}/{file}"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return None
                    content = await resp.text()
            m = VERSION_RE.search(content)
            if m:
                return m.group(1)
        except Exception as e:
            log.debug(f"DLM: не удалось получить версию {file}: {e}")
        return None

    def _get_local_version(self, file: str) -> Optional[str]:
        """Вытащить version из локального modules/<file>."""
        path = MODULES_DIR / file
        if not path.exists():
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return None
        m = VERSION_RE.search(content)
        return m.group(1) if m else None

    # ── ПРОВЕРКА ОБНОВЛЕНИЙ ──
    async def _check_updates(self) -> dict:
        """Вернуть dict: {file: {"local": v, "remote": v, "status": 'new'/'update'/'same'}}."""
        catalog = await self._fetch_catalog()
        result: dict[str, dict] = {}

        for item in catalog:
            file = item["file"]
            local = self._get_local_version(file)
            remote = await self._get_remote_version(file)

            if local is None and remote is not None:
                status = "new"
            elif local is not None and remote is None:
                status = "same"  # не смогли получить удалённую — считаем как есть
            elif local is None and remote is None:
                status = "same"
            else:
                cmp = _compare_versions(remote, local)
                if cmp > 0:
                    status = "update"
                else:
                    status = "same"

            result[file] = {"local": local, "remote": remote, "status": status}

        return result

    # ── УВЕДОМЛЕНИЕ ──
    async def _notify_admin(self, text: str):
        """Отправить ЛС владельцу (и в лог)."""
        if not self.cfg.get("notify_updates", True):
            return
        admin_id = None
        if self.kernel and self.kernel.context:
            admin_id = self.kernel.context.admin_id
        if admin_id is None:
            self.log.info(f"[DLM notify] {text}")
            return
        try:
            await self.client.send_message(admin_id, text, parse_mode="html")
        except Exception as e:
            self.log.warning(f"DLM: не удалось отправить уведомление: {e}")

    # ── ОБНОВЛЕНИЕ ──
    async def _update_module(self, file: str) -> bool:
        """Скачать новую версию модуля и перезагрузить его."""
        url = f"{CATALOG_RAW}/{file}"
        target = MODULES_DIR / file
        backup = MODULES_DIR / f"{file}.bak"

        # 1. Скачать
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        log.error(f"DLM: HTTP {resp.status} для {url}")
                        return False
                    content = await resp.text()
        except Exception as e:
            log.exception(f"DLM: ошибка скачивания {file}: {e}")
            return False

        # 2. Валидация
        if "class " not in content or "Module" not in content:
            log.error(f"DLM: {file} не похож на TETKO-модуль")
            return False

        # 3. Бэкап
        try:
            if target.exists():
                backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as e:
            log.warning(f"DLM: не удалось сделать .bak для {file}: {e}")

        # 4. Записать
        try:
            target.write_text(content, encoding="utf-8")
        except Exception as e:
            log.exception(f"DLM: не удалось записать {file}: {e}")
            return False

        # 5. Перезагрузить (если loader поддерживает)
        try:
            file_stem = file[:-3]  # "randomedits"
            loader = getattr(self.client, "loader", None)
            if loader is not None:
                # ищем реальное имя модуля в реестре (например, "RandomEdits")
                real_name = None
                for reg_name in list(self.kernel.registry.list_modules().keys()):
                    if reg_name.lower() == file_stem.lower() or reg_name.lower().replace(" ", "") == file_stem.lower():
                        real_name = reg_name
                        break

                if real_name:
                    try:
                        await loader.unload_module(real_name)
                        self.log.info(f"DLM: выгружен модуль {real_name}")
                    except Exception as e:
                        self.log.warning(f"DLM: unload {real_name} failed: {e}")
                else:
                    self.log.warning(f"DLM: модуль {file_stem} не найден в реестре — пропускаем unload")

                await loader.load_module_from_file(target)
                self.log.info(f"DLM: модуль {file_stem} перезагружен")
                return True
        except Exception as e:
            log.exception(f"DLM: ошибка перезагрузки {file}: {e}")
            # откат из .bak
            if backup.exists():
                try:
                    target.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
                    self.log.warning(f"DLM: откат {file} из .bak")
                except Exception:
                    pass
            return False

        return True

    # ── ФОНОВАЯ ЗАДАЧА ──
    @loop(interval=3600)
    async def auto_update_loop(self):
        """Периодическая проверка каталога и автообновление модулей."""
        if not self.cfg.get("auto_update", True):
            return

        # если интервал в конфиге отличается — пропускаем
        target_interval = int(self.cfg.get("update_interval", 3600))
        if target_interval != 3600:
            # упрощённо: не поддерживаем разный интервал без перезапуска loop
            pass

        try:
            updates = await self._check_updates()
        except Exception as e:
            log.exception(f"DLM: ошибка проверки обновлений: {e}")
            return

        updated_files: list[str] = []
        new_files: list[str] = []

        for file, info in updates.items():
            status = info["status"]
            if status == "update":
                if self.cfg.get("auto_update", True):
                    ok = await self._update_module(file)
                    if ok:
                        updated_files.append(file)
            elif status == "new":
                new_files.append(file)
                if self.cfg.get("auto_install_new", False):
                    ok = await self._update_module(file)
                    if ok:
                        updated_files.append(file)

        # уведомления
        if updated_files:
            await self._notify_admin(
                "🔄 <b>DLM: обновлены модули</b>\n\n"
                + "\n".join(f"• <code>{f}</code>" for f in updated_files)
            )
        if new_files:
            await self._notify_admin(
                "🆕 <b>DLM: новые модули в каталоге</b>\n\n"
                + "\n".join(f"• <code>{f}</code>" for f in new_files)
                + "\n\n<i>Установи через <code>.dlm</code></i>"
            )

    # ── ГЛАВНОЕ МЕНЮ ──
    @command(name="dlm", aliases=["mods", "dlmods"], description="Менеджер модулей", only_for="owner")
    async def dlm_cmd(self, event, args):
        await self._show_main(event, is_cb=False)

    async def _send_menu_via_bot(self, cb_event, text: str, buttons: list) -> None:
        """Отправить новое меню в чат (после callback)."""
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return

        # chat_id = 0 у inline-callback → не валидный
        peer = getattr(cb_event, "chat_id", None)

        # если 0/None — берём input_chat, потом sender_id
        if not peer:
            try:
                peer = await cb_event.get_input_chat()
            except Exception as e:
                peer = None

        if not peer:
            peer = getattr(cb_event, "sender_id", None)

        if not peer:
            return

        # Ищем (chat_id, message_id) в кэше по token кнопки
        data = getattr(cb_event, "data", b"")
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        imid = bot.get_inline_message_id(data)

        try:
            if imid:
                # редактируем inline-сообщение
                await bot.edit_inline_menu(
                    inline_message_id=imid,
                    text=text,
                    buttons=buttons,
                )
            else:
                # отправляем новое
                await bot.send_inline_menu(
                    chat_id=peer,
                    key=f"dlm_menu_{int(time.time())}",
                    text=text,
                    buttons=buttons,
                )
        except Exception as e:
            self.log.warning(f"_send_menu_via_bot failed: {e}")

    async def _show_main(self, event_or_cb, is_cb: bool = False, force_refresh: bool = False):
        kernel = self.kernel
        catalog = await self._fetch_catalog(force=force_refresh)

        installed = [x for x in catalog if (MODULES_DIR / x["file"]).exists()]

        if not catalog:
            text = (
                "📦 <b>DLM — Dynamic Loader of Modules</b>\n\n"
                "⚠️ Каталог модулей пуст или недоступен.\n"
                f"<i>Источник: {CATALOG_REPO}</i>"
            )

            async def on_refresh_empty(cb_event):
                await cb_event.answer("Обновляю...")
                await self._show_main(cb_event, is_cb=True, force_refresh=True)

            buttons = [[kernel.inline.make_button("🔄 Обновить", on_refresh_empty, ttl=600)]]
        else:
            text = (
                "📦 <b>DLM — Dynamic Loader of Modules</b>\n\n"
                f"В каталоге: <code>{len(catalog)}</code>\n"
                f"Установлено: <code>{len(installed)}</code>\n\n"
                f"<i>Источник: {CATALOG_REPO}</i>"
            )
            buttons = []
            for item in catalog:
                mark = "✅ " if (MODULES_DIR / item["file"]).exists() else "📥 "
                label = f"{mark}{item['name']}"

                async def on_click(cb_event, file=item["file"]):
                    await self._show_module(cb_event, file)

                buttons.append([kernel.inline.make_button(label, on_click, ttl=600)])

            async def on_refresh(cb_event):
                await cb_event.answer("Обновляю...")
                await self._show_main(cb_event, is_cb=True, force_refresh=True)

            buttons.append([kernel.inline.make_button("🔄 Обновить", on_refresh, ttl=600)])


        try:
            if is_cb:
                # inline-сообщения нельзя edit'ать — отправляем новое
                await self._send_menu_via_bot(event_or_cb, text, buttons)
            else:
                chat_id = event_or_cb.chat_id
                try:
                    await event_or_cb.delete()
                except Exception:
                    pass

                # Отправляем inline-меню через бота (работает в любом чате)
                bot = getattr(kernel, "bot_client", None)
                if bot is not None:
                    try:
                        menu_key = f"dlm_main_{int(time.time())}"
                        await bot.send_inline_menu(
                            chat_id=chat_id,
                            key=menu_key,
                            text=text,
                            buttons=buttons,
                        )
                        return
                    except Exception as e:
                        log.warning(f"DLM: send_inline_menu failed: {e}, fallback")
                # fallback — обычная отправка (без кнопок)
                await kernel.inline.form(chat_id, text, buttons)
        except Exception:
            log.exception("DLM: ошибка в form/edit")

    # ── МЕНЮ МОДУЛЯ ──
    async def _show_module(self, cb_event, file: str):
        catalog = self._catalog_cache or []
        item = next((x for x in catalog if x["file"] == file), None)
        if item is None:
            await cb_event.answer("Модуль не найден")
            return

        installed = (MODULES_DIR / file).exists()
        local_v = self._get_local_version(file)
        remote_v = await self._get_remote_version(file)

        status = "✅ Установлен" if installed else "📥 Не установлен"
        size_kb = round(item.get("size", 0) / 1024, 1)
        versions_line = ""
        if local_v and remote_v:
            versions_line = f"\n<b>Локально:</b> <code>{local_v}</code>\n<b>Удалённо:</b> <code>{remote_v}</code>"
        elif remote_v:
            versions_line = f"\n<b>Удалённо:</b> <code>{remote_v}</code>"

        text = (
            f"📦 <b>{item['name']}</b>\n\n"
            f"<b>Файл:</b> <code>{file}</code>\n"
            f"<b>Размер:</b> <code>{size_kb} KB</code>\n"
            f"<b>Статус:</b> {status}{versions_line}"
        )

        async def on_download(cb_event, f=file, nm=item["name"]):
            await cb_event.answer(f"Скачиваю {nm}...")
            ok = await self._update_module(f)
            if ok:
                await cb_event.answer(f"✅ {nm} установлен/обновлён")
                await self._show_module(cb_event, f)
            else:
                await cb_event.answer(f"❌ Не удалось скачать {nm}", alert=True)

        async def on_back(cb_event):
            await self._show_main(cb_event, is_cb=True)

        buttons = []
        if not installed:
            buttons.append([self.kernel.inline.make_button("📥 Скачать", on_download, ttl=600)])
        else:
            buttons.append([self.kernel.inline.make_button("🔄 Обновить", on_download, ttl=600)])
        buttons.append([self.kernel.inline.make_button("← Назад", on_back, ttl=600)])

        await self._send_menu_via_bot(cb_event, text, buttons)

    # ── РУЧНАЯ ПРОВЕРКА ──
    @command(name="dlm_check", aliases=["checkmods"], description="Проверить обновления модулей", only_for="owner")
    async def dlm_check_cmd(self, event, args):
        await event.edit("🔍 Проверяю каталог...")

        try:
            updates = await self._check_updates()
        except Exception as e:
            await event.edit(f"❌ Ошибка: <code>{e}</code>", parse_mode="html")
            return

        upd = [(f, i) for f, i in updates.items() if i["status"] == "update"]
        new = [(f, i) for f, i in updates.items() if i["status"] == "new"]

        if not upd and not new:
            await event.edit("✅ Всё актуально, новых модулей нет.")
            return

        lines = ["🔍 <b>Результат проверки</b>\n"]
        if upd:
            lines.append("<b>Обновления:</b>")
            for f, i in upd:
                lines.append(f"• <code>{f}</code>: {i['local']} → {i['remote']}")
        if new:
            lines.append("\n<b>Новые:</b>")
            for f, i in new:
                lines.append(f"• <code>{f}</code> (v{i['remote']})")

        await event.edit("\n".join(lines), parse_mode="html")
