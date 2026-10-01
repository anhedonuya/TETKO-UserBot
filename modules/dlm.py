"""DLM — Dynamic Loader of Modules (shell-style)."""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from core.tetko import Module, command, loop, shell

log = logging.getLogger("TETKO.module.dlm")

CATALOG_REPO = "anhedonuya/TETKO-dlm"
CATALOG_BRANCH = "main"
CATALOG_API = f"https://api.github.com/repos/{CATALOG_REPO}/contents/"
CATALOG_RAW = f"https://raw.githubusercontent.com/{CATALOG_REPO}/{CATALOG_BRANCH}"

MODULES_DIR = Path("modules")
CUSTOM_DIR = Path("modules_custom")
CACHE_TTL = 300
PAGE_SIZE = 5

VERSION_RE = re.compile(r'^\s*version\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def _esc(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bq(msg):
    return "<blockquote><b>" + msg + "</b></blockquote>"


def _shell(lines, running=False, cmd=None):
    return shell.wrap(lines, cmd=cmd, running=running, trailing=True)


def _parse_version(v):
    parts = []
    for p in str(v).split("."):
        p = p.split("-")[0]
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _compare_versions(v1, v2):
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
    version = "1.2.0"
    author = "@anhedonuya"
    description = "Dynamic Loader of Modules"

    config = {
        "auto_update": True,
        "auto_install_new": False,
        "update_interval": 3600,
        "notify_updates": True,
    }

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self._catalog_cache = None
        self._cache_time = 0.0

    async def on_load(self):
        self.log.info("DLM loaded")

    async def on_unload(self):
        self.log.debug("DLM unloaded")

    async def _fetch_catalog(self, force=False):
        now = time.time()
        if not force and self._catalog_cache is not None and (now - self._cache_time) < CACHE_TTL:
            return self._catalog_cache

        items = []
        try:
            import aiohttp
            headers = {"Accept": "application/vnd.github+json"}
            async with aiohttp.ClientSession(headers=headers) as session:
                catalog_url = f"{CATALOG_RAW}/catalog.json"
                async with session.get(catalog_url, timeout=15) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json(content_type=None)
                            if isinstance(data, dict) and "modules" in data:
                                for m in data["modules"]:
                                    if not isinstance(m, dict):
                                        continue
                                    f = m.get("file") or ""
                                    if not f.endswith(".py"):
                                        continue
                                    items.append({
                                        "file": f,
                                        "name": m.get("name") or f[:-3],
                                        "description": m.get("description") or "-",
                                        "size": 0,
                                        "url": m.get("url") or f"{CATALOG_RAW}/{f}",
                                    })
                        except Exception as e:
                            log.warning("DLM: catalog.json parse: " + str(e))

                if not items:
                    async with session.get(CATALOG_API, timeout=15) as resp:
                        if resp.status != 200:
                            log.error("DLM: GitHub API returned " + str(resp.status))
                            return self._catalog_cache or []
                        data = await resp.json(content_type=None)
                    for entry in data:
                        if entry.get("type") != "file":
                            continue
                        name = entry.get("name", "")
                        if not name.endswith(".py") or name.startswith("_"):
                            continue
                        items.append({
                            "file": name,
                            "name": name[:-3],
                            "description": "-",
                            "size": entry.get("size", 0),
                            "url": entry.get("download_url") or f"{CATALOG_RAW}/{name}",
                        })
        except Exception as e:
            log.exception("DLM: catalog fetch failed: " + str(e))
            return self._catalog_cache or []

        self._catalog_cache = items
        self._cache_time = now
        return items

    async def _get_remote_version(self, file):
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
            log.debug("DLM: version fetch " + file + ": " + str(e))
        return None

    def _get_local_version(self, file):
        for base in (CUSTOM_DIR, MODULES_DIR):
            path = base / file
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    m = VERSION_RE.search(content)
                    return m.group(1) if m else None
                except Exception:
                    pass
        return None

    async def _check_updates(self):
        catalog = await self._fetch_catalog()
        result = {}
        for item in catalog:
            file = item["file"]
            local = self._get_local_version(file)
            remote = await self._get_remote_version(file)
            if local is None and remote is not None:
                status = "new"
            elif local is not None and remote is None:
                status = "same"
            elif local is None and remote is None:
                status = "same"
            else:
                cmp = _compare_versions(remote, local)
                status = "update" if cmp > 0 else "same"
            result[file] = {"local": local, "remote": remote, "status": status}
        return result

    async def _notify_admin(self, text):
        if not self.cfg.get("notify_updates", True):
            return
        admin_id = None
        if self.kernel and self.kernel.context:
            admin_id = self.kernel.context.admin_id
        if admin_id is None:
            self.log.info("[DLM notify] " + str(text))
            return
        try:
            await self.client.send_message(admin_id, text, parse_mode="html")
        except Exception as e:
            self.log.warning("DLM: notify failed: " + str(e))

    async def _update_module(self, file):
        url = f"{CATALOG_RAW}/{file}"
        if (CUSTOM_DIR / file).exists() or not (MODULES_DIR / file).exists():
            target = CUSTOM_DIR / file
        else:
            log.warning("DLM: " + file + " — system module, skipped")
            return False
        backup = target.parent / (file + ".bak")

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        log.error("DLM: HTTP " + str(resp.status) + " for " + url)
                        return False
                    content = await resp.text()
        except Exception as e:
            log.exception("DLM: download failed " + file + ": " + str(e))
            return False

        if "class " not in content or "Module" not in content:
            log.error("DLM: " + file + " — not a TETKO module")
            return False

        try:
            if target.exists():
                backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as e:
            log.warning("DLM: backup failed " + file + ": " + str(e))

        try:
            target.write_text(content, encoding="utf-8")
        except Exception as e:
            log.exception("DLM: write failed " + file + ": " + str(e))
            return False

        try:
            file_stem = file[:-3]
            loader = getattr(self.client, "loader", None)
            if loader is not None:
                real_name = None
                for reg_name in list(self.kernel.registry.list_modules().keys()):
                    if reg_name.lower() == file_stem.lower() or reg_name.lower().replace(" ", "") == file_stem.lower():
                        real_name = reg_name
                        break
                if real_name:
                    try:
                        await loader.unload_module(real_name)
                        self.log.info("DLM: unloaded " + real_name)
                    except Exception as e:
                        self.log.debug("DLM: unload failed " + real_name + ": " + str(e))
                await loader.load_module_from_file(target)
                self.log.debug("DLM: reloaded " + file_stem)
                return True
        except Exception as e:
            log.exception("DLM: reload failed " + file + ": " + str(e))
            if backup.exists():
                try:
                    target.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
                    self.log.warning("DLM: rollback " + file + " from .bak")
                except Exception:
                    pass
            return False
        return True

    @loop(interval=3600)
    async def auto_update_loop(self):
        if not self.cfg.get("auto_update", True):
            return
        try:
            updates = await self._check_updates()
        except Exception as e:
            log.exception("DLM: update check failed: " + str(e))
            return

        updated_files = []
        new_files = []

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

        catalog = await self._fetch_catalog()
        _names = {it["file"]: it.get("name", it["file"][:-3]) for it in catalog}

        if updated_files:
            lines = ["dlm updated:"]
            for f in updated_files:
                lines.append("  " + _names.get(f, f))
            await self._notify_admin(
                _bq("dlm: updated modules") + "\n"
                + _shell(lines)
            )
        if new_files:
            lines = ["dlm new modules:"]
            for f in new_files:
                lines.append("  " + _names.get(f, f))
            lines.append("install with .dlm")
            await self._notify_admin(
                _bq("dlm: new modules in catalog") + "\n"
                + _shell(lines)
            )

    @command(name="dlm", aliases=["mods", "dlmods"], description="Module manager", only_for="owner")
    async def dlm_cmd(self, event, args):
        await self._show_main(event, is_cb=False)

    async def _send_menu_via_bot(self, cb_event, text, buttons):
        bot = getattr(self.kernel, "bot_client", None)
        if bot is None:
            return
        topic_id = None
        try:
            rt = getattr(cb_event, "reply_to", None)
            if rt is not None:
                topic_id = (getattr(rt, "reply_to_top_id", None) or getattr(rt, "reply_to_msg_id", None))
        except Exception:
            pass
        peer = getattr(cb_event, "chat_id", None)
        if not peer:
            try:
                peer = await cb_event.get_input_chat()
            except Exception:
                peer = None
        if not peer:
            peer = getattr(cb_event, "sender_id", None)
        if not peer:
            return
        data = getattr(cb_event, "data", b"")
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        imid = bot.get_inline_message_id(data)
        try:
            if imid:
                await bot.edit_inline_menu(inline_message_id=imid, text=text, buttons=buttons)
                if not hasattr(bot, "_inlines"):
                    bot._inlines = {}
                for row in buttons:
                    for btn in row:
                        bot._inlines[btn["token"]] = imid
            else:
                await bot.send_inline_menu(
                    chat_id=peer,
                    key=f"dlm_menu_{int(time.time())}",
                    text=text,
                    buttons=buttons,
                    topic_id=topic_id,
                )
        except Exception as e:
            self.log.warning("_send_menu_via_bot failed: " + str(e))

    async def _show_main(self, event_or_cb, is_cb=False, force_refresh=False, page=0):
        kernel = self.kernel
        catalog = await self._fetch_catalog(force=force_refresh)

        def _mod_path(f):
            for base in (CUSTOM_DIR, MODULES_DIR):
                if (base / f).exists():
                    return base
            return None

        installed = [x for x in catalog if _mod_path(x["file"])]

        if not catalog:
            text = (
                _bq("DLM — Dynamic Loader of Modules") + "\n"
                + _shell(["catalog: empty or unavailable"])
            )

            async def on_refresh_empty(cb_event):
                await cb_event.answer("refreshing...")
                await self._show_main(cb_event, is_cb=True, force_refresh=True, page=0)

            buttons = [[kernel.inline.make_button("refresh", on_refresh_empty, ttl=600)]]
        else:
            total = len(catalog)
            total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            page = max(0, min(page, total_pages - 1))
            start_i = page * PAGE_SIZE
            page_items = catalog[start_i:start_i + PAGE_SIZE]

            text = (
                _bq("DLM — Dynamic Loader of Modules") + "\n"
                + _shell([
                    "installed: %d/%d" % (len(installed), total),
                    "page: %d/%d" % (page + 1, total_pages),
                ])
            )
            buttons = []

            for item in page_items:
                p = _mod_path(item["file"])
                if p is None:
                    mark = "[+]"
                elif p == MODULES_DIR:
                    mark = "[~]"
                else:
                    mark = "[*]"
                label = mark + " " + item["name"]

                async def on_click(cb_event, file=item["file"]):
                    await self._show_module(cb_event, file)

                buttons.append([kernel.inline.make_button(label, on_click, ttl=600)])

            nav = []
            if page > 0:
                async def on_prev(cb, p=page - 1):
                    await self._show_main(cb, is_cb=True, page=p)
                nav.append(kernel.inline.make_button("<", on_prev, ttl=600))

            async def on_noop(cb):
                await cb.answer()
            nav.append(kernel.inline.make_button(".", on_noop, ttl=600))

            for i in range(total_pages):
                if i == page:
                    continue
                if len(nav) > 6:
                    break
                async def on_page(cb, p=i):
                    await self._show_main(cb, is_cb=True, page=p)
                nav.append(kernel.inline.make_button(str(i + 1), on_page, ttl=600))

            if page < total_pages - 1:
                async def on_next(cb, p=page + 1):
                    await self._show_main(cb, is_cb=True, page=p)
                nav.append(kernel.inline.make_button(">", on_next, ttl=600))

            buttons.append(nav)

            async def on_refresh(cb):
                await cb.answer("refreshing...")
                await self._show_main(cb, is_cb=True, force_refresh=True, page=page)

            buttons.append([kernel.inline.make_button("refresh", on_refresh, ttl=600)])

        topic_id = None
        try:
            rt = getattr(event_or_cb, "reply_to", None)
            if rt is not None:
                topic_id = (getattr(rt, "reply_to_top_id", None) or getattr(rt, "reply_to_msg_id", None))
        except Exception:
            pass

        if is_cb:
            await self._send_menu_via_bot(event_or_cb, text, buttons)
        else:
            chat_id = event_or_cb.chat_id
            try:
                await event_or_cb.delete()
            except Exception:
                pass
            bot = getattr(kernel, "bot_client", None)
            if bot is not None:
                try:
                    menu_key = f"dlm_main_{int(time.time())}"
                    await bot.send_inline_menu(
                        chat_id=chat_id, key=menu_key, text=text,
                        buttons=buttons, topic_id=topic_id,
                    )
                    return
                except Exception as e:
                    log.warning("DLM: send_inline_menu failed: " + str(e))
            await kernel.inline.form(chat_id, text, buttons)

    async def _show_module(self, cb_event, file):
        catalog = self._catalog_cache or []
        item = next((x for x in catalog if x["file"] == file), None)
        if item is None:
            await cb_event.answer("module not found")
            return

        mod_path = None
        for base in (CUSTOM_DIR, MODULES_DIR):
            if (base / file).exists():
                mod_path = base / file
                break
        installed = mod_path is not None
        local_v = self._get_local_version(file)
        remote_v = await self._get_remote_version(file)

        text = (
            _bq(item["name"]) + "\n"
            + _shell([
                "status : " + ("installed" if installed else "not installed"),
                "local  : " + (local_v or "-"),
                "remote : " + (remote_v or "-"),
            ]) + "\n"
            + _shell(["info   : " + (item.get("description") or "-")])
        )

        async def on_download(cb_event, f=file, nm=item["name"]):
            await cb_event.answer("downloading " + nm + "...")
            ok = await self._update_module(f)
            if ok:
                await cb_event.answer(nm + " installed/updated")
                await self._show_module(cb_event, f)
            else:
                await cb_event.answer("failed: " + nm, alert=True)

        async def on_back(cb_event):
            await self._show_main(cb_event, is_cb=True)

        buttons = []
        if not installed:
            buttons.append([self.kernel.inline.make_button("install", on_download, ttl=600)])
        else:
            buttons.append([self.kernel.inline.make_button("update", on_download, ttl=600)])
        buttons.append([self.kernel.inline.make_button("< back", on_back, ttl=600)])

        await self._send_menu_via_bot(cb_event, text, buttons)

    @command(name="dlm_check", aliases=["checkmods"], description="Check module updates", only_for="owner")
    async def dlm_check_cmd(self, event, args):
        await event.edit(_shell(["dlm check catalog"], running=True), parse_mode="html")

        try:
            updates = await self._check_updates()
        except Exception as e:
            await event.edit(
                _bq("dlm check") + "\n" + _shell(["error: " + str(e)]),
                parse_mode="html",
            )
            return

        upd = [(f, i) for f, i in updates.items() if i["status"] == "update"]
        new = [(f, i) for f, i in updates.items() if i["status"] == "new"]

        if not upd and not new:
            await event.edit(
                _bq("dlm check") + "\n" + _shell(["no new modules"]),
                parse_mode="html",
            )
            return

        lines = []
        if upd:
            lines.append("updates:")
            for f, i in upd:
                lines.append("  " + f + ": " + str(i['local']) + " -> " + str(i['remote']))
        if new:
            lines.append("new:")
            for f, i in new:
                lines.append("  " + f + " (v" + str(i['remote']) + ")")

        await event.edit(
            _bq("dlm check") + "\n" + _shell(lines),
            parse_mode="html",
        )
