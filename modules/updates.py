"""Updates — авто-обновление ядра TETKO из git."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from core.tetko import Module, command, db_get, db_set, db_del

log = logging.getLogger("TETKO.module.updates")

REPO_ROOT = Path(__file__).resolve().parent.parent


class UpdatesModule(Module):
    name = "Updates"
    __compat__ = "0.0.9.0"
    version = "1.1.0"
    author = "@anhedonuya"
    description = "Авто-обновление и перезапуск TETKO"

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
                chat_id,
                message_id,
                "<blockquote><b>✅ Ваша тетенька успешно перезагрузилась!!</b></blockquote>",
                parse_mode="html",
            )
            log.info(f"updates: pending reload message edited ({chat_id}/{message_id})")
        except Exception as e:
            log.warning(f"updates: pending reload edit failed: {e}")
        db_del("updates", "pending_reload")

    def _emoji(self) -> dict:
        premium = bool(getattr(self.kernel.context, "user_premium", False))
        if premium:
            return {
                "think": '<tg-emoji emoji-id="5346022209389372742">🤔</tg-emoji>',
                "hourglass": '<tg-emoji emoji-id="5332688668102525212">⌛</tg-emoji>',
                "tetko": (
                    '<tg-emoji emoji-id="5285530631567095762">🙏</tg-emoji>'
                    '<tg-emoji emoji-id="5285030066013648645">📧</tg-emoji>'
                    '<tg-emoji emoji-id="5285504668489785087">🅾️</tg-emoji>'
                ),
                "ok": '<tg-emoji emoji-id="5339256974473199519">👍</tg-emoji>',
                "err": '<tg-emoji emoji-id="5258196742435787040">👾</tg-emoji>',
            }
        return {
            "think": "🤔",
            "hourglass": "⌛",
            "tetko": "TETKO",
            "ok": "👍",
            "err": "👾",
        }

    def _branch(self) -> str:
        try:
            return self.kernel.config.get("branch", "main")
        except Exception:
            return "main"

    def _restart(self):
        try:
            os.execv(sys.executable, [sys.executable, str(REPO_ROOT / "main.py")])
        except Exception as e:
            log.exception(f"restart failed: {e}")

    @staticmethod
    def _esc(text: str) -> str:
        return (
            str(text).replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @command(
        name="update",
        aliases=["upd"],
        description="Обновить TETKO из git",
        only_for="owner",
    )
    async def cmd_update(self, event, args):
        e = self._emoji()
        branch = self._branch()

        await event.edit(
            f"<blockquote>{e['think']} <b>Щаща погоди я обновы сматрю!!</b> {e['hourglass']}</blockquote>",
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
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=60,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                await event.edit(
                    f"<blockquote>{e['err']} <b>Ошибка:</b> <code>git pull timeout (60s)</code></blockquote>",
                    parse_mode="html",
                )
                return

            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")
            rc = proc.returncode

        except Exception as ex:
            log.exception("update: git pull failed")
            await event.edit(
                f"<blockquote>{e['err']} <b>Ошибка:</b> <code>{self._esc(str(ex))}</code></blockquote>",
                parse_mode="html",
            )
            return

        if rc != 0:
            err_text = (stderr or stdout).strip()[:300]
            await event.edit(
                f"<blockquote>{e['err']} <b>git pull failed:</b>\n"
                f"<code>{self._esc(err_text)}</code></blockquote>",
                parse_mode="html",
            )
            return

        combined = (stdout + stderr).lower()
        if "already up to date" in combined or "already up-to-date" in combined:
            await event.edit(
                f"<blockquote>{e['ok']} <b>Зачем???? У тя последняя версия TETKO!!!</b></blockquote>",
                parse_mode="html",
            )
            return

        # сохраняем сообщение, чтобы после рестарта отредактировать
        db_set("updates", "pending_reload", {
            "chat_id": event.chat_id,
            "message_id": event.message.id,
        })

        await event.edit(
            f"<blockquote>{e['ok']} <b>Обновление успешно!</b>\n"
            f"{e['tetko']} <b>Перезапуск...</b></blockquote>",
            parse_mode="html",
        )

        await asyncio.sleep(2)
        self._restart()
