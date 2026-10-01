"""PicToStories — делит фото на сетку 3×N и загружает в сторис."""
# req: pillow
from __future__ import annotations

import asyncio
import io
import logging

from telethon import functions, types
from PIL import Image

from core.tetko import Module, command

log = logging.getLogger("TETKO.module.pictostories")


class PicToStories(Module):
    name = "PicToStories"
    __compat__ = "0.0.9.0"
    version = "1.0.0"
    author = "@anhedonuya"
    description = "Делит фото на сетку 3×N и загружает в сторис"

    config = {
        "period": 48,
        "blacklist": [],
        "cooldown": 0,
    }

    # ── эмодзи ──
    def _emoji(self) -> dict:
        premium = bool(getattr(self.kernel.context, "user_premium", False))
        if premium:
            return {
                "warn": '<tg-emoji emoji-id="5879813604068298387">❗️</tg-emoji>',
                "work": '<tg-emoji emoji-id="5841359499146825803">🕔</tg-emoji>',
                "done": '<tg-emoji emoji-id="5776375003280838798">✅</tg-emoji>',
                "err": '<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji>',
            }
        return {
            "warn": "❗️",
            "work": "🕔",
            "done": "✅",
            "err": "❌",
        }

    @command(
        name="pts",
        aliases=["pictostories"],
        description="<reply фото> [альбом] — сетка 3×N в сторис",
        only_for="owner",
    )
    async def pts_cmd(self, event, args):
        e = self._emoji()
        album_name = " ".join(args).strip() if args else ""

        # reply
        reply = await event.get_reply_message()
        if not reply or not reply.media:
            await event.edit(f"{e['warn']} <b>Реплай на фото!</b>", parse_mode="html")
            return

        # скачиваем
        try:
            image_bytes = await reply.download_media(file=bytes)
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
        except Exception as ex:
            log.exception("pts: download/convert failed")
            await event.edit(
                f"{e['err']} <b>Ошибка:</b> <code>{self._esc(str(ex))}</code>",
                parse_mode="html",
            )
            return

        await event.edit(f"{e['work']} <b>Обрабатываю...</b>", parse_mode="html")

        # подбираем сетку
        w, h = img.size
        curr_ratio = w / h
        cell_ratio = 1.25
        variants = [(3 / (rows * cell_ratio), rows) for rows in (1, 2, 3, 4, 5)]
        best_ratio, rows = min(variants, key=lambda x: abs(curr_ratio - x[0]))

        new_h = int(w / best_ratio)
        img = img.resize((w, new_h), Image.LANCZOS)
        w, h = img.size

        parts = []
        pw, ph = w // 3, h // rows
        for r in range(rows):
            for c in range(3):
                x, y = c * pw, r * ph
                parts.append(img.crop((x, y, x + pw, y + ph)))
        parts.reverse()

        total = len(parts)

        # privacy
        privacy = [types.InputPrivacyValueAllowAll()]
        blacklist = self.cfg.get("blacklist", []) or []
        if blacklist:
            entities = []
            for uid in blacklist:
                try:
                    entities.append(await self.client.get_input_entity(uid))
                except Exception:
                    continue
            if entities:
                privacy.append(types.InputPrivacyValueDisallowUsers(users=entities))

        period = int(self.cfg.get("period", 48))
        cooldown = int(self.cfg.get("cooldown", 0))

        story_ids = []
        for i, p in enumerate(parts, 1):
            try:
                await event.edit(
                    f"{e['work']} <b>[{i}/{total}]</b> Загружаю сторис...",
                    parse_mode="html",
                )
            except Exception:
                pass

            out = io.BytesIO()
            p.save(out, "JPEG", quality=95)
            out.seek(0)

            try:
                uploaded = await self.client.upload_file(out, file_name="s.jpg")
                res = await self.client(functions.stories.SendStoryRequest(
                    peer=types.InputPeerSelf(),
                    media=types.InputMediaUploadedPhoto(uploaded),
                    privacy_rules=privacy,
                    period=period * 3600,
                ))
            except Exception as ex:
                msg = str(ex)
                if "STORIES_TOO_MUCH" in msg:
                    await event.edit(
                        f"{e['warn']} <b>Слишком много историй. Подожди {period}ч.</b>",
                        parse_mode="html",
                    )
                else:
                    log.exception("pts: send story failed")
                    await event.edit(
                        f"{e['err']} <b>Ошибка:</b> <code>{self._esc(msg)}</code>",
                        parse_mode="html",
                    )
                return

            sid = next(
                (
                    getattr(u, "story_id", None) or getattr(u, "id", None)
                    for u in res.updates
                    if hasattr(u, "story_id") or hasattr(u, "id")
                ),
                None,
            )
            if sid:
                story_ids.append(sid)

            if cooldown > 0 and i < total:
                await asyncio.sleep(cooldown)

        if not story_ids:
            return

        # альбом
        if album_name:
            try:
                all_albums = await self.client(functions.stories.GetAlbumsRequest(
                    peer=types.InputPeerSelf(), hash=0,
                ))
                target = next(
                    (a for a in all_albums.albums if getattr(a, "title", "") == album_name),
                    None,
                )
                if target:
                    await self.client(functions.stories.UpdateAlbumRequest(
                        peer=types.InputPeerSelf(),
                        album_id=target.album_id,
                        add_stories=story_ids,
                    ))
                else:
                    await self.client(functions.stories.CreateAlbumRequest(
                        peer=types.InputPeerSelf(),
                        stories=story_ids,
                        title=album_name,
                    ))
            except Exception as ex:
                log.warning(f"pts: album failed: {ex}")

        # прикрепить к профилю
        try:
            await self.client(functions.stories.TogglePinnedRequest(
                peer=types.InputPeerSelf(), id=story_ids, pinned=True,
            ))
        except Exception as ex:
            log.warning(f"pts: pin failed: {ex}")

        await event.edit(
            f"{e['done']} <b>Готово! Проверяй профиль.</b>",
            parse_mode="html",
        )

    @staticmethod
    def _esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
