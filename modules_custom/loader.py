"""Loader — dynamic module loader."""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from core.tetko import Module, command, shell, shell

try:
    import aiohttp
    _HAS_AIOHTTP = True
except Exception:
    aiohttp = None
    _HAS_AIOHTTP = False


MODULES_DIR = "modules_custom"


def _esc(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bq(msg):
    return "<blockquote><b>" + msg + "</b></blockquote>"


def _bq_i(msg):
    return "<blockquote>" + msg + "</blockquote>"


def _shell(cmd, running=True):
    return shell.wrap([], cmd=cmd, running=running, trailing=True)


def _shell_out(cmd, out):
    return "<pre>$ " + _esc(cmd) + "\n" + _esc(out) + "</pre>"


class Loader(Module):
    name = "Loader"
    __compat__ = "0.0.9.0"
    version = "1.5.0"
    author = "@anhedonuya & @flexownerAL"
    description = {
        "ru": "Динамическая загрузка модулей",
        "en": "Dynamic module loader",
    }
    config = {"auto_install_reqs": True}

    async def _install_requirements(self, code, event):
        m = re.search(r"#\s*(?:req|requirements|pip):\s*(.+)", code, re.IGNORECASE)
        if not m:
            return
        pkgs = m.group(1).strip().split()
        if not pkgs:
            return
        cmd = "pip install " + " ".join(pkgs)
        await event.edit(
            _shell(cmd),
            parse_mode="html",
        )
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", *pkgs,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    def _extract_meta(self, code):
        meta = {}

        def grab(pat):
            m = re.search(pat, code, re.MULTILINE)
            return m.group(1).strip() if m else None

        meta["name"] = grab(r'^\s*name\s*=\s*["\']([^"\']+)["\']')
        meta["version"] = grab(r'^\s*version\s*=\s*["\']([^"\']+)["\']')
        meta["author"] = grab(r'^\s*author\s*=\s*["\']([^"\']+)["\']')
        desc = grab(r'^\s*description\s*=\s*["\']([^"\']+)["\']')
        if desc:
            meta["description"] = desc
        else:
            ru = grab(r'^\s*description\s*=\s*\{[^}]*["\']ru["\']\s*:\s*["\']([^"\']+)["\']')
            en = grab(r'^\s*description\s*=\s*\{[^}]*["\']en["\']\s*:\s*["\']([^"\']+)["\']')
            meta["description"] = ru or en or "-"
        return meta

    @command("load", aliases=["dlmod"], description="Load module from file or url")
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
                (getattr(a, "file_name", None) for a in doc.attributes if hasattr(a, "file_name")),
                None,
            )
            if file_name and file_name.endswith(".py"):
                await event.edit(
                    _shell("tg download " + file_name),
                    parse_mode="html",
                )
                tmp_dir = os.path.join(MODULES_DIR, ".tmp")
                os.makedirs(tmp_dir, exist_ok=True)
                tmp_path = await self.client.download_media(reply, file=tmp_dir)
                with open(tmp_path, "r", encoding="utf-8") as f:
                    code_content = f.read()
                mod_name = os.path.splitext(file_name)[0]
                file_path = os.path.join(MODULES_DIR, mod_name + ".py")
                if os.path.abspath(tmp_path) != os.path.abspath(file_path):
                    os.replace(tmp_path, file_path)
            else:
                await event.edit(
                    _bq("File must be .py"),
                    parse_mode="html",
                )
                return

        elif url_arg and url_arg.strip().startswith("http"):
            url = url_arg.strip()
            if "github.com" in url and "raw.githubusercontent.com" not in url:
                url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

            if not _HAS_AIOHTTP:
                await event.edit(
                    _bq("aiohttp not installed"),
                    parse_mode="html",
                )
                return

            await event.edit(
                _shell("wget " + url[:80]),
                parse_mode="html",
            )
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            await event.edit(
                                _bq("HTTP status " + str(resp.status)),
                                parse_mode="html",
                            )
                            return
                        code_content = await resp.text()
                        mod_name = url.split("/")[-1].replace(".py", "").split("?")[0]
                        file_path = os.path.join(MODULES_DIR, mod_name + ".py")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(code_content)
            except Exception as e:
                await event.edit(
                    _bq("Fetch failed") + "\n"
                    + _shell_out("wget " + url[:80], str(e)),
                    parse_mode="html",
                )
                return
        else:
            await event.edit(
                _bq("Reply to .py or pass url"),
                parse_mode="html",
            )
            return

        if code_content and self.cfg.get("auto_install_reqs"):
            await self._install_requirements(code_content, event)

        if not (loader and hasattr(loader, "load_module_from_file")):
            await event.edit(
                _bq("Saved " + MODULES_DIR + "/" + mod_name + ".py (restart required)"),
                parse_mode="html",
            )
            return

        try:
            await loader.load_module_from_file(Path(file_path))

            meta = self._extract_meta(code_content or "")
            shown_name = meta.get("name") or mod_name
            shown_desc = meta.get("description") or "-"
            shown_author = meta.get("author") or "-"
            shown_version = meta.get("version") or "-"
            prefix = getattr(self.kernel, "prefix", ".") or "."

            cmds = []
            for cmd in self.kernel.registry._commands.values():
                try:
                    if getattr(cmd.module, "name", "") == shown_name:
                        cmds.append(prefix + cmd.name)
                except Exception:
                    pass
            cmds_text = " ".join(sorted(set(cmds))) or "-"

            await event.edit(
                _bq("Successfully installed <code>" + _esc(shown_name) + "</code> <code>v" + _esc(shown_version) + "</code>") + "\n"
                + _bq_i("author: <code>" + _esc(shown_author) + "</code>") + "\n"
                + _bq_i("info: " + _esc(shown_desc)) + "\n"
                + _bq_i("cmds: <code>" + _esc(cmds_text) + "</code>"),
                parse_mode="html",
            )

        except Exception as e:
            self.log.exception("load: init failed " + str(mod_name))
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            await event.edit(
                _bq("Install failed") + "\n"
                + _shell_out("python " + mod_name + ".py", str(e)),
                parse_mode="html",
            )

    @command("unload", description="Unload and remove module")
    async def cmd_unload(self, event, args):
        loader = getattr(self.client, "loader", None)
        if not args:
            await event.edit(
                _bq("Usage: .unload &lt;name&gt;"),
                parse_mode="html",
            )
            return
        name = args[0].strip().replace(".py", "")

        await event.edit(
            _shell("rm " + name + ".py"),
            parse_mode="html",
        )

        if loader and hasattr(loader, "unload_module"):
            await loader.unload_module(name)
        path = os.path.join(MODULES_DIR, name + ".py")
        if os.path.exists(path):
            os.remove(path)

        await event.edit(
            _bq("Successfully removed <code>" + _esc(name) + "</code>"),
            parse_mode="html",
        )

    @command("unlm", aliases=["getmod", "sendmod"], description="Send module file", only_for="owner")
    async def cmd_unlm(self, event, args):
        if not args:
            if not os.path.isdir(MODULES_DIR):
                await event.edit(_bq("Empty"), parse_mode="html")
                return
            installed = sorted(
                f[:-3] for f in os.listdir(MODULES_DIR)
                if f.endswith(".py") and not f.startswith("_")
            )
            if not installed:
                await event.edit(_bq("Empty"), parse_mode="html")
                return
            body = _bq("Modules: <code>" + str(len(installed)) + "</code>")
            for n in installed:
                body += "\n" + _bq_i("<code>" + _esc(n) + "</code>")
            await event.edit(body, parse_mode="html")
            return

        name = args[0].strip().replace(".py", "")
        path = os.path.join(MODULES_DIR, name + ".py")
        if not os.path.exists(path):
            await event.edit(
                _bq("<code>" + _esc(name) + "</code> not found"),
                parse_mode="html",
            )
            return

        try:
            size = os.path.getsize(path)
            await self.client.send_file(
                event.chat_id,
                file=path,
                caption=_bq("File <code>" + _esc(name) + ".py</code> · <code>" + str(size) + " bytes</code>"),
                parse_mode="html",
                reply_to=getattr(event, "reply_to_msg_id", None),
            )
            try:
                await event.delete()
            except Exception:
                pass
        except Exception as e:
            self.log.exception("unlm: send failed " + str(name))
            await event.edit(
                _bq("Send failed") + "\n"
                + _shell_out("tg send " + name, str(e)),
                parse_mode="html",
            )

    @command("um", description="Remove user module", only_for="owner")
    async def cmd_um(self, event, args):
        import os as _os

        def _list_user():
            if not _os.path.isdir(MODULES_DIR):
                return []
            return sorted(
                f[:-3] for f in _os.listdir(MODULES_DIR)
                if f.endswith(".py") and not f.startswith("_")
            )

        if not args:
            installed = _list_user()
            if not installed:
                await event.edit(_bq("Empty"), parse_mode="html")
                return
            body = _bq("Modules: <code>" + str(len(installed)) + "</code>")
            for n in installed:
                body += "\n" + _bq_i("<code>" + _esc(n) + "</code>")
            await event.edit(body, parse_mode="html")
            return

        name = args[0].strip()
        if name.endswith(".py"):
            name = name[:-3]

        path = _os.path.join(MODULES_DIR, name + ".py")
        if not _os.path.exists(path):
            sys_mod = _os.path.join("modules", name + ".py")
            if _os.path.exists(sys_mod):
                await event.edit(
                    _bq("<code>" + _esc(name) + "</code> is system module"),
                    parse_mode="html",
                )
                return
            await event.edit(
                _bq("<code>" + _esc(name) + "</code> not found"),
                parse_mode="html",
            )
            return

        await event.edit(
            _shell("rm " + name + ".py"),
            parse_mode="html",
        )

        loader = getattr(self.client, "loader", None)
        if loader is not None:
            try:
                await loader.unload_module(name)
            except Exception as e:
                self.log.warning("um: unload " + name + " failed: " + str(e))
        try:
            _os.remove(path)
        except Exception as e:
            await event.edit(
                _bq("Remove failed") + "\n"
                + _shell_out("rm " + name + ".py", str(e)),
                parse_mode="html",
            )
            return

        await event.edit(
            _bq("Successfully removed <code>" + _esc(name) + "</code>"),
            parse_mode="html",
        )

    @command("restart", description="Restart TETKO process", only_for="owner")
    async def cmd_restart(self, event):
        from core.tetko import db_set
        db_set("updates", "pending_reload", {
            "chat_id": event.chat_id,
            "message_id": event.message.id,
        })
        await event.edit(
            _shell("systemctl restart tetko"),
            parse_mode="html",
        )
        await asyncio.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
