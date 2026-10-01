# module by worriedBr4 | fixed
from __future__ import annotations

import asyncio
import os
import re
import hashlib
import shutil
import subprocess
import time
import unicodedata
import json
from typing import Optional, List, Dict, Any, Tuple

import yt_dlp
import urllib3

from core.lib.loader.module_base import ModuleBase, command
from core.lib.loader.module_config import ModuleConfig, ConfigValue, Integer, String, Choice

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


STRINGS = {
    "ru": {
        "searching": "<blockquote><b>Searching..</b></blockquote>",
        "found_downloading": (
            "<blockquote><b>Found, downloading</b></blockquote>\n"
            "<blockquote><b>Name</b> — <i>{name}</i>\n"
            "<b>Author</b> — <i>{author}</i></blockquote>\n"
            "<i>via MusicNowAL</i>"
        ),
        "sending": "<blockquote><b>Sending..</b> | {size} <i>MB</i></blockquote>",
        "caption": (
            "<blockquote><b>Author</b> — <code>{author}</code></blockquote>\n"
            "<blockquote><b>Name</b> — <code>{name}</code></blockquote>\n"
            "{link_line}"
            "—————\n"
            "<i>via MusicNowAL</i>"
        ),
        "mstat": (
            "<blockquote><i>MusicNowAL v{version}</i></blockquote>\n"
            "<blockquote><b>yt-dlp</b> — {ytdlp_version} | {ytdlp_status}</blockquote>\n"
            "<blockquote><b>ffmpeg</b> — {ffmpeg_version} | {ffmpeg_status}</blockquote>\n"
            "<blockquote><b>Tracks downloaded</b> — {tracks_downloaded}</blockquote>\n"
            "<blockquote><b>Cache size</b> — {cache_size}</blockquote>\n"
            "<blockquote><b>Show link</b> — {link_status}</blockquote>\n"
            "<blockquote><i>user: {username}</i></blockquote>"
        ),
        "not_found": "<blockquote><b>Track not found.</b></blockquote>",
        "error": "<blockquote><b>Error:</b> {error}</blockquote>",
        "usage": (
            "<blockquote><b>Usage:</b>\n"
            "<code>{prefix}music query</code> — YouTube search\n"
            "<code>{prefix}music https://youtu.be/xxx</code> — Download by link</blockquote>"
        ),
        "cache_cleared": "<blockquote><b>Cache cleared.</b> Freed: {size}</blockquote>",
        "link_enabled": "<blockquote>Link to original <b>enabled</b></blockquote>",
        "link_disabled": "<blockquote>Link to original <b>disabled</b></blockquote>",
        "link_status": "<blockquote>Link to original: <b>{status}</b></blockquote>",
        "invalid_url": "<blockquote><b>Invalid URL.</b></blockquote>",
    },
    "en": {
        "searching": "<blockquote><b>Searching..</b></blockquote>",
        "found_downloading": (
            "<blockquote><b>Found, downloading</b></blockquote>\n"
            "<blockquote><b>Name</b> — <i>{name}</i>\n"
            "<b>Author</b> — <i>{author}</i></blockquote>\n"
            "<i>via MusicNowAL</i>"
        ),
        "sending": "<blockquote><b>Sending..</b> | {size} <i>MB</i></blockquote>",
        "caption": (
            "<blockquote><b>Author</b> — <code>{author}</code></blockquote>\n"
            "<blockquote><b>Name</b> — <code>{name}</code></blockquote>\n"
            "{link_line}"
            "—————\n"
            "<i>via MusicNowAL</i>"
        ),
        "mstat": (
            "<blockquote><i>MusicNowAL v{version}</i></blockquote>\n"
            "<blockquote><b>yt-dlp</b> — {ytdlp_version} | {ytdlp_status}</blockquote>\n"
            "<blockquote><b>ffmpeg</b> — {ffmpeg_version} | {ffmpeg_status}</blockquote>\n"
            "<blockquote><b>Tracks downloaded</b> — {tracks_downloaded}</blockquote>\n"
            "<blockquote><b>Cache size</b> — {cache_size}</blockquote>\n"
            "<blockquote><b>Show link</b> — {link_status}</blockquote>\n"
            "<blockquote><i>user: {username}</i></blockquote>"
        ),
        "not_found": "<blockquote><b>Track not found.</b></blockquote>",
        "error": "<blockquote><b>Error:</b> {error}</blockquote>",
        "usage": (
            "<blockquote><b>Usage:</b>\n"
            "<code>{prefix}music query</code> — YouTube search\n"
            "<code>{prefix}music https://youtu.be/xxx</code> — Download by link</blockquote>"
        ),
        "cache_cleared": "<blockquote><b>Cache cleared.</b> Freed: {size}</blockquote>",
        "link_enabled": "<blockquote>Link to original <b>enabled</b></blockquote>",
        "link_disabled": "<blockquote>Link to original <b>disabled</b></blockquote>",
        "link_status": "<blockquote>Link to original: <b>{status}</b></blockquote>",
        "invalid_url": "<blockquote><b>Invalid URL.</b></blockquote>",
    },
}

DB_NS = "MusicNowAL"
DB_KEY_SHOW_LINK = "show_link"


class MusicNowAL(ModuleBase):
    name = "MusicNowAL"
    version = "1.9.2"
    author = "@flexOwnerAL"
    description = {
        "ru": "Download music from YouTube",
        "en": "Download music from YouTube",
    }

    config = ModuleConfig(
        ConfigValue(
            "quality",
            "192",
            description="Audio quality (128, 192, 320, best)",
            validator=Choice(choices=["128", "192", "320", "best"]),
        ),
        ConfigValue(
            "max_duration",
            3600,
            description="Maximum track duration in seconds",
            validator=Integer(min=60, max=7200),
        ),
        ConfigValue(
            "music_dir",
            "music_cache",
            description="Directory for music cache",
            validator=String(),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._downloading: Dict[str, bool] = {}

    # ── DB flags (persist across restarts) ──

    async def _get_show_link(self) -> bool:
        val = await self.db.db_get(DB_NS, DB_KEY_SHOW_LINK)
        if val is None:
            return True
        if isinstance(val, str):
            return val.lower() in ("1", "true", "yes", "on")
        return bool(val)

    async def _set_show_link(self, value: bool) -> None:
        await self.db.db_set(DB_NS, DB_KEY_SHOW_LINK, bool(value))

    # ── Lifecycle ──

    async def on_load(self) -> None:
        await super().on_load()
        os.makedirs(self.config["music_dir"], exist_ok=True)
        show_link = await self._get_show_link()
        self.log.info(
            f"MusicNowAL loaded quality={self.config['quality']} show_link={show_link}"
        )

    async def on_unload(self) -> None:
        self.log.info("MusicNowAL unloaded")
        await super().on_unload()

    # ── Helpers ──

    def _get_strings(self) -> Dict[str, str]:
        lang = self.get_lang()
        return STRINGS.get(lang, STRINGS["en"])

    def _prefix(self) -> str:
        for obj in (self, getattr(self, "kernel", None), getattr(self, "client", None)):
            for key in ("prefix", "command_prefix", "cmd_prefix"):
                try:
                    value = getattr(obj, key, None)
                    if value:
                        return str(value)
                except Exception:
                    pass
            try:
                config = getattr(obj, "config", None)
                if isinstance(config, dict):
                    for key in ("prefix", "command_prefix", "cmd_prefix"):
                        if config.get(key):
                            return str(config[key])
            except Exception:
                pass
        return "?"

    def _s(self, key: str, **kwargs) -> str:
        strings = self._get_strings()
        template = strings.get(key, key)
        merged = {"prefix": self._prefix(), **kwargs}
        return template.format(**merged)

    def _clean_filename(self, s: str, max_len: int = 100) -> str:
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = re.sub(r'[<>:"/\\|?*]', "", s)
        s = re.sub(r"[^\x20-\x7E]", "", s).strip()
        if len(s) > max_len:
            name, ext = os.path.splitext(s)
            s = name[:max_len - len(ext)] + ext
        return s or "track"

    def _is_url(self, text: str) -> bool:
        url_pattern = re.compile(
            r"^https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|m\.youtube\.com/watch\?v=|music\.youtube\.com/)[^\s]+",
            re.IGNORECASE,
        )
        return bool(url_pattern.match(text.strip()))

    def _get_cache_size(self) -> str:
        music_dir = self.config["music_dir"]
        total_size = 0
        for dirpath, _, filenames in os.walk(music_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        if total_size < 1024:
            return f"{total_size} B"
        elif total_size < 1024 * 1024:
            return f"{total_size / 1024:.1f} KB"
        elif total_size < 1024 * 1024 * 1024:
            return f"{total_size / (1024 * 1024):.1f} MB"
        else:
            return f"{total_size / (1024 * 1024 * 1024):.2f} GB"

    def _clear_cache(self) -> Tuple[int, str]:
        music_dir = self.config["music_dir"]
        total_size = 0
        for dirpath, _, filenames in os.walk(music_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
        return total_size, self._get_cache_size()

    def _get_ytdlp_version(self) -> str:
        try:
            return yt_dlp.version.__version__
        except Exception:
            return "unknown"

    def _check_ffmpeg(self) -> Tuple[str, str]:
        try:
            r = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                first_line = r.stdout.split("\n")[0]
                match = re.search(r"ffmpeg version (\S+)", first_line)
                if match:
                    return match.group(1), "OK"
                return "found", "OK"
            return "unknown", "FAIL"
        except FileNotFoundError:
            return "not installed", "FAIL"
        except Exception:
            return "error", "FAIL"

    def _base_ydl_opts(self) -> Dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["webpage", "configs"],
                }
            },
        }

    def _search_ytdlp(self, query: str, limit: int = 1) -> List[Dict[str, Any]]:
        opts = {
            **self._base_ydl_opts(),
            "default_search": "ytsearch",
            "extract_flat": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                if not info or "entries" not in info:
                    return []
                return [
                    {
                        "title": e.get("title", "-"),
                        "url": f"https://youtube.com/watch?v={e['id']}",
                        "duration": e.get("duration") or 0,
                        "channel": e.get("uploader") or e.get("channel") or "-",
                        "id": e.get("id", ""),
                        "thumbnail": e.get("thumbnail", ""),
                    }
                    for e in info["entries"]
                    if e and e.get("id")
                ]
        except Exception:
            return []

    def _get_info(self, url: str) -> Optional[Dict[str, Any]]:
        opts = self._base_ydl_opts()
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                return {
                    "title": info.get("title", "Unknown"),
                    "artist": info.get("uploader") or info.get("artist") or "Unknown",
                    "duration": info.get("duration") or 0,
                    "source": info.get("extractor_key", "YouTube"),
                    "id": info.get("id", ""),
                    "thumbnail": info.get("thumbnail", ""),
                    "webpage_url": info.get("webpage_url", url),
                }
        except Exception:
            return None

    def _download_yt(self, url: str, info: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        music_dir = self.config["music_dir"]
        quality = self.config["quality"]

        download_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:8]
        temp_filename = f"temp_{download_id}.%(ext)s"
        temp_path_template = os.path.join(music_dir, temp_filename)

        cache_key = hashlib.md5(f"{url}{quality}".encode()).hexdigest()[:12]
        cache_path = os.path.join(music_dir, f"cache_{cache_key}.mp3")

        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            return cache_path, None

        opts = {
            **self._base_ydl_opts(),
            "format": "bestaudio/best",
            "outtmpl": temp_path_template,
            "writethumbnail": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": quality if quality != "best" else "0",
                },
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                },
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": False,
                },
                {"key": "FFmpegMetadata", "add_metadata": True},
            ],
            "postprocessor_args": {
                "EmbedThumbnail": ["-id3v2_version", "3"],
            },
        }

        title = info.get("title", "") or ""
        artist = info.get("artist", "") or ""

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            expected_mp3 = temp_path_template.replace(".%(ext)s", ".mp3")
            if os.path.exists(expected_mp3) and os.path.getsize(expected_mp3) > 0:
                temp_path = expected_mp3
            else:
                candidates = [
                    f
                    for f in os.listdir(music_dir)
                    if f.endswith(".mp3")
                    and os.path.getctime(os.path.join(music_dir, f)) > time.time() - 30
                ]
                if not candidates:
                    return None, "file not created"
                candidates.sort(
                    key=lambda f: os.path.getctime(os.path.join(music_dir, f)),
                    reverse=True,
                )
                temp_path = os.path.join(music_dir, candidates[0])

            final_name = self._clean_filename(f"{artist} - {title}.mp3")
            final_path = os.path.join(music_dir, final_name)

            counter = 1
            while os.path.exists(final_path):
                final_name = self._clean_filename(f"{artist} - {title}_{counter}.mp3")
                final_path = os.path.join(music_dir, final_name)
                counter += 1

            shutil.move(temp_path, final_path)

            for f in os.listdir(music_dir):
                if f.startswith(f"temp_{download_id}") and not f.endswith(".mp3"):
                    try:
                        os.remove(os.path.join(music_dir, f))
                    except OSError:
                        pass

            try:
                shutil.copy2(final_path, cache_path)
            except OSError:
                pass

            return final_path, None

        except Exception as e:
            err = str(e)
            if "403" in err or "Forbidden" in err:
                return None, "403 Forbidden (try update yt-dlp or different client)"
            return None, err[:300]

    async def _get_stats(self) -> Dict[str, Any]:
        data = await self.db.db_get(self.name, "stats")
        if not data:
            return {"tracks_downloaded": 0}
        try:
            return json.loads(data) if isinstance(data, str) else (data or {})
        except Exception:
            return {"tracks_downloaded": 0}

    async def _save_stats(self, stats: Dict[str, Any]) -> None:
        await self.db.db_set(self.name, "stats", json.dumps(stats))

    async def _process_and_send(
        self,
        event,
        track_url: str,
        info: Dict[str, Any],
    ) -> None:
        stats = await self._get_stats()
        show_link = await self._get_show_link()
        max_duration = int(self.config["max_duration"])

        if info["duration"] > max_duration:
            await event.edit(
                self._s("error", error="Track too long (max 1 hour)"),
                parse_mode="html",
            )
            return

        track_name = info["title"]
        track_author = info["artist"]
        track_link = info.get("webpage_url", track_url)

        await event.edit(
            self._s(
                "found_downloading",
                name=track_name,
                author=track_author,
            ),
            parse_mode="html",
        )

        if track_url in self._downloading:
            await event.edit(
                self._s("error", error="Already downloading"),
                parse_mode="html",
            )
            return

        self._downloading[track_url] = True
        try:
            path, error = await asyncio.to_thread(self._download_yt, track_url, info)
        finally:
            self._downloading.pop(track_url, None)

        if error or not path or not os.path.exists(path):
            await event.edit(
                self._s("error", error=error or "File not found"),
                parse_mode="html",
            )
            return

        file_size_mb = os.path.getsize(path) / (1024 * 1024)

        await event.edit(
            self._s("sending", size=f"{file_size_mb:.1f}"),
            parse_mode="html",
        )

        link_line = (
            f"<blockquote><b>Original</b> — "
            f"<a href='{track_link}'>YouTube</a></blockquote>\n"
            if show_link
            else ""
        )

        caption = self._s(
            "caption",
            author=track_author,
            name=track_name,
            link_line=link_line,
        )

        thumb = None
        base = os.path.splitext(path)[0]
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            cand = base + ext
            if os.path.exists(cand):
                thumb = cand
                break

        try:
            await self.client.send_file(
                event.chat_id,
                path,
                caption=caption,
                parse_mode="html",
                thumb=thumb,
                attributes=[],
                reply_to=getattr(event.message, "reply_to", None),
            )
            await event.delete()
        except Exception as e:
            await event.edit(self._s("error", error=str(e)[:200]), parse_mode="html")
            return
        finally:
            if thumb and os.path.exists(thumb):
                try:
                    os.remove(thumb)
                except OSError:
                    pass

        stats["tracks_downloaded"] = stats.get("tracks_downloaded", 0) + 1
        await self._save_stats(stats)

    # ── Commands ──

    @command(
        "music",
        doc_ru="Download music: music query / music link",
        doc_en="Download music: music query / music link",
    )
    async def cmd_music(self, event) -> None:
        text = event.text or ""
        args = text.split(maxsplit=1)

        if len(args) < 2:
            await event.edit(self._s("usage"), parse_mode="html")
            return

        query = args[1].strip()
        if not query:
            await event.edit(self._s("usage"), parse_mode="html")
            return

        await event.edit(self._s("searching"), parse_mode="html")

        try:
            if self._is_url(query):
                track_url = query
                info = await asyncio.to_thread(self._get_info, track_url)
                if not info:
                    await event.edit(self._s("invalid_url"), parse_mode="html")
                    return
                await self._process_and_send(event, track_url, info)
                return

            results = await asyncio.to_thread(self._search_ytdlp, query, limit=1)
            if not results:
                await event.edit(self._s("not_found"), parse_mode="html")
                return

            track_url = results[0]["url"]
            info = await asyncio.to_thread(self._get_info, track_url)
            if not info:
                await event.edit(self._s("not_found"), parse_mode="html")
                return

            await self._process_and_send(event, track_url, info)

        except Exception as e:
            error_msg = str(e)[:200]
            await event.edit(self._s("error", error=error_msg), parse_mode="html")

    @command(
        "mlink",
        doc_ru="Toggle link in music caption",
        doc_en="Toggle link in music caption",
    )
    async def cmd_mlink(self, event) -> None:
        current = await self._get_show_link()
        new_value = not current
        await self._set_show_link(new_value)

        if new_value:
            await event.edit(self._s("link_enabled"), parse_mode="html")
        else:
            await event.edit(self._s("link_disabled"), parse_mode="html")

    @command(
        "mlinkstatus",
        doc_ru="Show link status in caption",
        doc_en="Show link status in caption",
    )
    async def cmd_mlinkstatus(self, event) -> None:
        current = await self._get_show_link()
        status = "enabled" if current else "disabled"
        await event.edit(self._s("link_status", status=status), parse_mode="html")

    @command("mstat", doc_ru="MusicNowAL stats", doc_en="MusicNowAL stats")
    async def cmd_mstat(self, event) -> None:
        ytdlp_version = self._get_ytdlp_version()
        ytdlp_status = "OK"
        ffmpeg_version, ffmpeg_status = self._check_ffmpeg()
        stats = await self._get_stats()
        cache_size = self._get_cache_size()
        show_link = await self._get_show_link()

        try:
            me = await self.client.get_me()
            username = f"@{me.username}" if me.username else me.first_name or "unknown"
        except Exception:
            username = "unknown"

        link_status = "enabled" if show_link else "disabled"

        await event.edit(
            self._s(
                "mstat",
                version=self.version,
                ytdlp_version=ytdlp_version,
                ytdlp_status=ytdlp_status,
                ffmpeg_version=ffmpeg_version,
                ffmpeg_status=ffmpeg_status,
                tracks_downloaded=stats.get("tracks_downloaded", 0),
                cache_size=cache_size,
                link_status=link_status,
                username=username,
            ),
            parse_mode="html",
        )

    @command("mclear", doc_ru="Clear music cache", doc_en="Clear music cache")
    async def cmd_mclear(self, event) -> None:
        _, size_str = await asyncio.to_thread(self._clear_cache)
        await event.edit(
            self._s("cache_cleared", size=size_str),
            parse_mode="html",
        )

    @command(
        "mquality",
        doc_ru="Set audio quality: mquality 128|192|320|best",
        doc_en="Set audio quality: mquality 128|192|320|best",
    )
    async def cmd_mquality(self, event) -> None:
        args = (event.text or "").split(maxsplit=1)

        if len(args) < 2:
            await event.edit(
                f"<blockquote>Current quality: "
                f"<code>{self.config['quality']}</code>\n"
                f"Usage: <code>{self._prefix()}mquality 128|192|320|best</code></blockquote>",
                parse_mode="html",
            )
            return

        new_quality = args[1].strip().lower()
        valid_qualities = ["128", "192", "320", "best"]

        if new_quality not in valid_qualities:
            await event.edit(
                f"<blockquote>Invalid quality. "
                f"Available: {', '.join(valid_qualities)}</blockquote>",
                parse_mode="html",
            )
            return

        self.config["quality"] = new_quality
        await self.kernel.save_module_config(self.name, self.config.to_dict())
        await event.edit(
            f"<blockquote>Quality set to: "
            f"<code>{new_quality}</code></blockquote>",
            parse_mode="html",
        )


# module by worriedBr4 dont steal plz