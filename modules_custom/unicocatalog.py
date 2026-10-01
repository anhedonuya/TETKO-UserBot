"""UnicoCatalog — send random media from @unico_1213213213."""
from __future__ import annotations

import asyncio
import logging
import random
from typing import List, Optional

from telethon.tl.types import (
    InputMessagesFilterGif,
    InputMessagesFilterPhotoVideo,
    InputMessagesFilterVideo,
    Message,
)

from core.tetko import Module, command, db_get, db_set

log = logging.getLogger("TETKO.module.UnicoCatalog")


def _bq(msg):
    return "<blockquote><b>" + msg + "</b></blockquote>"


def _bq_i(msg):
    return "<blockquote>" + msg + "</blockquote>"


class UnicoCatalog(Module):
    name = "UnicoCatalog"
    version = "1.5.0"
    author = "@Hairpin00 && porting to tetko style by @anhedonuya"
    __compat__ = "0.0.9.0"
    description = "Random media from @unico_1213213213"

    config = {
        "CACHE_LIMIT": 300,
        "FETCH_GIF": True,
        "FETCH_VIDEO": True,
        "FETCH_PHOTO_VIDEO": True,
        "BACKGROUND_UPDATE_HOURS": 4,
        "SILENT": True,
    }

    strings = {
        "searching": '<blockquote><tg-emoji emoji-id="5420560293069626753">🔍</tg-emoji> searching unico..</blockquote>',
        "no_media": _bq("No media found in channel. Try again later."),
        "send_error": _bq("Failed to send media. Try again."),
        "cache_updated": _bq("Cache updated."),
        "cache_error": _bq("Cache update failed."),
        "fetch_error": _bq("Fetch failed."),
        "invalid_limit": _bq("Limit must be between 20 and 500."),
        "cache_empty": _bq("Cache empty. Updating.."),
    }

    UNICO_CHANNEL = "unico_1213213213"
    DB_OWNER = "UnicoCatalog"
    DB_KEY = "cache_ids"

    def __init__(self, kernel=None):
        super().__init__(kernel)
        self._bg_task: Optional[asyncio.Task] = None
        self._cache_lock = asyncio.Lock()

    async def on_load(self):
        if self._bg_task and not self._bg_task.done():
            self._bg_task.cancel()
        self._bg_task = asyncio.create_task(self._cache_updater_loop())

    async def on_unload(self):
        if self._bg_task and not self._bg_task.done():
            self._bg_task.cancel()
        try:
            if self._bg_task is not None:
                await self._bg_task
        except (asyncio.CancelledError, Exception):
            pass

    def _get_cache_ids(self) -> List[int]:
        data = db_get(self.DB_OWNER, self.DB_KEY, default=[])
        if not isinstance(data, list):
            return []
        out: List[int] = []
        for x in data:
            try:
                out.append(int(x))
            except Exception:
                continue
        return out

    def _set_cache_ids(self, ids: List[int]) -> None:
        limit = int(self.cfg.get("CACHE_LIMIT", 300))
        ids = ids[: max(0, limit)]
        db_set(self.DB_OWNER, self.DB_KEY, ids)

    async def _fetch_media_ids(self, limit: int) -> List[int]:
        filters = []
        if self.cfg.get("FETCH_GIF", True):
            filters.append(InputMessagesFilterGif)
        if self.cfg.get("FETCH_VIDEO", True):
            filters.append(InputMessagesFilterVideo)
        if self.cfg.get("FETCH_PHOTO_VIDEO", True):
            filters.append(InputMessagesFilterPhotoVideo)
        if not filters:
            filters = [None]

        ids: List[int] = []
        seen = set()

        for flt in filters:
            try:
                async for m in self.client.iter_messages(
                    self.UNICO_CHANNEL,
                    limit=limit,
                    filter=flt,
                ):
                    if not getattr(m, "media", None):
                        continue
                    mid = int(m.id)
                    if mid in seen:
                        continue
                    seen.add(mid)
                    ids.append(mid)
            except Exception as e:
                self.log.warning("unico fetch error: " + str(e))
        return ids

    async def _update_cache(self, *, force: bool = False) -> int:
        async with self._cache_lock:
            current = self._get_cache_ids()
            if current and not force:
                return len(current)

            limit = int(self.cfg.get("CACHE_LIMIT", 300))
            ids = await self._fetch_media_ids(limit=min(limit, 500))
            if not ids:
                self._set_cache_ids([])
                return 0

            self._set_cache_ids(ids)
            return len(ids)

    async def _cache_updater_loop(self):
        while True:
            try:
                count = await self._update_cache(force=True)
                if count:
                    self.log.info("unico cache updated: " + str(count) + " medias")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.log.warning("unico cache error: " + str(e))
            await asyncio.sleep(
                int(self.cfg.get("BACKGROUND_UPDATE_HOURS", 4)) * 3600
            )

    async def _get_message_by_id(self, msg_id: int) -> Optional[Message]:
        try:
            msg = await self.client.get_messages(self.UNICO_CHANNEL, ids=msg_id)
        except Exception:
            return None
        if not msg or not getattr(msg, "media", None):
            return None
        return msg

    @command(name="unico", description="Random media from @unico_1213213213")
    async def unico_cmd(self, event, args):
        msg = await event.edit(self.strings["searching"], parse_mode="html")

        refresh_limit: Optional[int] = None
        if args:
            try:
                refresh_limit = int(args[0])
            except Exception:
                refresh_limit = None

        if refresh_limit is not None and not (20 <= refresh_limit <= 500):
            await msg.edit(self.strings["invalid_limit"], parse_mode="html")
            return

        if refresh_limit is not None:
            async with self._cache_lock:
                ids = await self._fetch_media_ids(limit=refresh_limit)
                self._set_cache_ids(ids)

        ids = self._get_cache_ids()
        if not ids:
            await msg.edit(self.strings["cache_empty"], parse_mode="html")
            await self._update_cache(force=True)
            ids = self._get_cache_ids()

        if not ids:
            await msg.edit(self.strings["no_media"], parse_mode="html")
            return

        chosen_id = random.choice(ids)
        source = await self._get_message_by_id(chosen_id)
        if not source:
            await self._update_cache(force=True)
            ids = self._get_cache_ids()
            if not ids:
                await msg.edit(self.strings["no_media"], parse_mode="html")
                return
            chosen_id = random.choice(ids)
            source = await self._get_message_by_id(chosen_id)

        if not source:
            await msg.edit(self.strings["send_error"], parse_mode="html")
            return

        try:
            await msg.delete()
        except Exception:
            pass

        try:
            await self.client.send_file(
                event.chat_id,
                source.media,
                caption=source.text or "",
                silent=bool(self.cfg.get("SILENT", True)),
                supports_streaming=True,
            )
        except Exception:
            await event.reply(self.strings["send_error"], parse_mode="html")
