"""Updates — авто-обновление ядра TETKO из git."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from core.tetko import Module, command

log = logging.getLogger("TETKO.module.updates")

# корень проекта (../ от modules/)
REPO_ROOT = Path(__file__).resolve().parent.parent


class UpdatesModule(Module):
    name = "Updates"
    __compat__ = "0.0.9.0"
    version = "1.0.0"
    author = "@anhedonuya"
    description = "Авто-обновление и перезапуск TETKO"

    # ── emoji ──
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

    # ── helpers ──
    def _branch(self) -> str:
        try:
            return self.kernel.config.get("branch", "main")
        except Exception:
            return "main"

    def _restart(self):
        """Полный перезапуск процесса (main.py)."""
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

    # ── .update ──
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
            f"{e['think']} <b>Щаща погоди я обновы сматрю!!</b> {e['hourglass']}",
            parse_mode="html",
        )

        # git pull
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
                    f"{e['err']} <b>Ошибка:</b> <code>git pull timeout (60s)</code>",
                    parse_mode="html",
                )
                self.log_to_chat(f"⬆️ update: git pull timeout")
                return

            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")
            rc = proc.returncode

        except Exception as ex:
            log.exception("update: git pull failed")
            await event.edit(
                f"{e['err']} <b>Ошибка:</b> <code>{self._esc(str(ex))}</code>",
                parse_mode="html",
            )
            await self.kernel.log_to_chat(f"👾 update failed: {ex}")
            return

        if rc != 0:
            err_text = (stderr or stdout).strip()[:300]
            await event.edit(
                f"{e['err']} <b>git pull failed:</b>\n<code>{self._esc(err_text)}</code>",
                parse_mode="html",
            )
            await self.kernel.log_to_chat(
                f"👾 update: git pull failed:\n<code>{self._esc(err_text)}</code>"
            )
            return

        # проверка на "Already up to date"
        combined = (stdout + stderr).lower()
        if "already up to date" in combined or "already up-to-date" in combined:
            await event.edit(
                f"{e['ok']} <b>Зачем???? У тя последняя версия TETKO!!!</b>",
                parse_mode="html",
            )
            await self.kernel.log_to_chat(
                f"👍 update: уже актуально ({branch})"
            )
            return

        # успех
        await event.edit(
            f"{e['ok']} <b>Обновление успешно!</b>\n"
            f"{e['tetko']} <b>Перезапуск...</b>",
            parse_mode="html",
        )
        await self.kernel.log_to_chat(
            f"👍 update: успешно ({branch})\n"
            f"<pre>{self._esc(stdout[:500])}</pre>"
        )

        await asyncio.sleep(2)
        self._restart()

    # .restart — удалён, используйте .restart из loader.py
