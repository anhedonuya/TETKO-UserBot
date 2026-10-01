"""Updates — pull TETKO from git and restart."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from core.tetko import Module, command, db_get, db_set, db_del, shell

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
