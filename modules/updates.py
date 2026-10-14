"""Updates — pull TETKO from git and restart."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from core.tetko import Module, command, loop, db_get, db_set, db_del, shell

log = logging.getLogger("TETKO.module.updates")

REPO_ROOT = Path(__file__).resolve().parent.parent


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


class UpdatesModule(Module):
    config = {
        "branch": "main",
        "auto_pull": False,
        "auto_restart": True,
        "auto_check": True,
        "check_interval": 3600,
        "notify_chat": True,
    }

    name = "Updates"
    __compat__ = "0.0.9.0"
    version = "1.4.0"
    author = "@anhedonuya"
    description = "Auto-update and restart of TETKO"

    async def on_load(self):
        pending = db_get("updates", "pending_reload")
        if not pending:
            return
        chat_id = pending.get("chat_id")
        message_id = pending.get("message_id")
        if chat_id is None or message_id is None:
            db_del("updates", "pending_reload")
            return
        try:
            await self.client.edit_message(
                chat_id, message_id,
                _bq("Successfully reloaded TETKO"),
                parse_mode="html",
            )
        except Exception as e:
            log.warning("updates: pending edit failed: " + str(e))
        db_del("updates", "pending_reload")

    def _branch(self):
        try:
            return self.kernel.config.get("branch", "main")
        except Exception:
            return "main"

    def _restart(self):
        try:
            os.execv(sys.executable, [sys.executable, str(REPO_ROOT / "main.py")])
        except Exception as e:
            log.exception("restart failed: " + str(e))

    async def _notify_chat(self, text, buttons=None):
        """Отправить в log_chat_id через бота (или в чат owner'а)."""
        if not self.cfg.get("notify_chat", True):
            return None
        chat_id = None
        try:
            chat_id = getattr(self.kernel, "log_chat_id", None)
            if not chat_id and self.kernel.context is not None:
                chat_id = self.kernel.context.admin_id
        except Exception:
            chat_id = None
        if not chat_id:
            return None
        bot = getattr(self.kernel, "bot_client", None)
        try:
            if bot is not None:
                return await bot.client.send_message(chat_id, text, parse_mode="html")
            return await self.client.send_message(chat_id, text, parse_mode="html")
        except Exception as e:
            log.warning("updates notify failed: " + str(e))
        return None

    async def _check_remote_version(self):
        """Вернуть (current, latest) или (None, None) если не удалось."""
        try:
            vm = getattr(self.kernel, "version_manager", None)
            if vm is None:
                return None, None
            current = getattr(self.kernel, "VERSION", "0.0.0")
            latest = await vm.get_latest_kernel_version()
            return current, latest
        except Exception as e:
            log.debug("check remote version failed: " + str(e))
            return None, None

    @command(name="update_check", aliases=["updchk"], description="Check for new core version")
    async def cmd_update_check(self, event, args):
        await event.edit(_shell("git fetch --dry-run"), parse_mode="html")
        current, latest = await self._check_remote_version()
        if current is None or latest is None:
            await event.edit(
                _bq("update check") + "\n" + _shell("update check failed"),
                parse_mode="html",
            )
            return
        try:
            from core.version import VersionManager
            cmp = VersionManager.compare_versions(latest, current)
        except Exception:
            cmp = 0
        status = "up to date" if cmp <= 0 else "update available"
        await event.edit(
            _bq("update check") + "\n" + _shell([
                "current    " + str(current),
                "latest     " + str(latest),
                "status     " + status,
            ]),
            parse_mode="html",
        )

    @loop(interval=3600)
    async def auto_check_loop(self):
        if not self.cfg.get("auto_check", True):
            return
        current, latest = await self._check_remote_version()
        if current is None or latest is None:
            return
        try:
            from core.version import VersionManager
            cmp = VersionManager.compare_versions(latest, current)
        except Exception:
            return
        if cmp <= 0:
            return
        seen = db_get("updates", "notified_version")
        if seen == latest:
            return

        text = _bq("⬆️ TETKO — доступно обновление") + "\n" + _shell([
            "current    " + str(current),
            "latest     " + str(latest),
            "branch     " + str(self._branch()),
        ])
        msg = await self._notify_chat(text)
        if msg is not None:
            try:
                db_set("updates", "notified_version", latest)
            except Exception:
                pass

    @command(name="update", aliases=["upd"], description="Pull TETKO from git", only_for="owner")
    async def cmd_update(self, event, args):
        branch = self._branch()
        cmd = "git pull origin " + branch

        await event.edit(
            _shell(cmd),
            parse_mode="html",
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "pull", "origin", branch,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(REPO_ROOT),
            )
            try:
                out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                await event.edit(
                    _bq("git pull timeout after 60s") + "\n"
                    + _shell(cmd, running=False),
                    parse_mode="html",
                )
                return
            stdout = out_b.decode(errors="replace")
            stderr = err_b.decode(errors="replace")
            rc = proc.returncode
        except Exception as ex:
            log.exception("update: git pull failed")
            await event.edit(
                _bq("git pull failed") + "\n"
                + _shell_out(cmd, str(ex)),
                parse_mode="html",
            )
            return

        if rc != 0:
            err_text = (stderr or stdout).strip()[:300]
            await event.edit(
                _bq("git pull exit code " + str(rc)) + "\n"
                + _shell_out(cmd, err_text),
                parse_mode="html",
            )
            return

        combined = (stdout + stderr).lower()
        if "already up to date" in combined or "already up-to-date" in combined:
            await event.edit(
                _bq("Already up to date") + "\n"
                + _shell_out(cmd, "Already up to date."),
                parse_mode="html",
            )
            return

        db_set("updates", "pending_reload", {
            "chat_id": event.chat_id,
            "message_id": event.message.id,
        })

        await event.edit(
            _bq("Successfully pulled TETKO") + "\n"
            + _shell("systemctl restart tetko"),
            parse_mode="html",
        )

        await asyncio.sleep(2)
        self._restart()
