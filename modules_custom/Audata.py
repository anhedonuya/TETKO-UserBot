"""Audata - direct music metadata editor."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
from pathlib import Path

from core.tetko import Module, command, shell

log = logging.getLogger("TETKO.module.Audata")

FIELDS = ("title", "artist", "album", "year", "genre", "track", "cover")
AUDIO_RE = re.compile(r"\.(mp3|m4a|flac|ogg|opus|wav)$", re.I)


def _esc(t):
    if t is None:
        return "-"
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _norm_year(y):
    if not y:
        return None
    y = str(y).strip()
    if len(y) >= 4 and y[:4].isdigit():
        return y[:4]
    return y


class Audata(Module):
    name = "Audata"
    __compat__ = "0.0.9.0"
    version = "3.0.0"
    author = "@flexOwnerAL"
    description = "Music metadata editor"

    config = {"max_file_size_mb": 100}

    async def on_load(self):
        self.log.info("Audata loaded")

    async def on_unload(self):
        self.log.info("Audata unloaded")

    def _prefix(self):
        try:
            return getattr(self.kernel, "prefix", ".") or "."
        except Exception:
            return "."

    @command(name="audata", aliases=["meta", "tag"], description="Edit music metadata")
    async def cmd_audata(self, event, args):
        p = self._prefix()

        if not args:
            await event.edit(shell.wrap([
                "usage    : " + p + "audata <field> <value>",
                "fields   : title artist album year genre track",
                "cover    : attach photo + " + p + "audata cover",
                "note     : reply to the audio file",
            ], cmd="audata", trailing=True), parse_mode="html")
            return

        field = str(args[0]).lower().strip()
        value = " ".join(args[1:]).strip()

        if field not in FIELDS:
            await event.edit(shell.wrap([
                "error    : unknown field: " + field,
                "fields   : title artist album year genre track cover",
            ], cmd="audata", trailing=True), parse_mode="html")
            return

        reply = await event.get_reply_message()
        if not reply or not reply.media or not hasattr(reply.media, "document"):
            await event.edit(shell.wrap([
                "error    : reply to an audio file",
                "usage    : " + p + "audata <field> <value>",
            ], cmd="audata", trailing=True), parse_mode="html")
            return

        doc = reply.media.document
        attrs = getattr(doc, "attributes", []) or []
        is_audio = False
        fname = None
        for a in attrs:
            n = type(a).__name__
            if n == "DocumentAttributeAudio":
                is_audio = True
            if n == "DocumentAttributeFilename":
                fname = getattr(a, "file_name", None)

        if not is_audio and not (fname and AUDIO_RE.search(fname)):
            await event.edit(shell.wrap([
                "error    : reply is not an audio file",
            ], cmd="audata", trailing=True), parse_mode="html")
            return

        size = getattr(doc, "size", 0) or 0
        max_bytes = int(self.cfg.get("max_file_size_mb", 100)) * 1024 * 1024
        if size > max_bytes:
            await event.edit(shell.wrap([
                "error    : file too large",
                "size     : %.1f MB" % (size / (1024 * 1024)),
                "limit    : %.1f MB" % (max_bytes / (1024 * 1024)),
            ], cmd="audata", trailing=True), parse_mode="html")
            return

        if field != "cover" and not value:
            await event.edit(shell.wrap([
                "error    : empty value",
                "usage    : " + p + "audata " + field + " <value>",
            ], cmd="audata", trailing=True), parse_mode="html")
            return

        cover_msg = None
        if field == "cover":
            try:
                if getattr(event, "media", None) is not None:
                    if getattr(event.media, "photo", None) is not None:
                        cover_msg = event.message
            except Exception:
                cover_msg = None
            if cover_msg is None:
                rid = getattr(event, "reply_to_msg_id", None)
                if rid:
                    try:
                        m = await event.client.get_messages(event.chat_id, ids=rid)
                        if m and getattr(m, "photo", None):
                            cover_msg = m
                    except Exception:
                        cover_msg = None
            if cover_msg is None:
                await event.edit(shell.wrap([
                    "error    : no photo found",
                    "hint     : send photo with caption " + p + "audata cover",
                ], cmd="audata", trailing=True), parse_mode="html")
                return

        await event.edit(shell.wrap([
            "info     : processing",
            "field    : " + field,
            "value    : " + (_esc(value) if value else "cover"),
            "",
            "downloading...",
        ], cmd="audata", running=True, trailing=False), parse_mode="html")

        tmp_dir = tempfile.mkdtemp(prefix="audata_")
        try:
            fpath = Path(tmp_dir) / (fname or "audio.mp3")
            path = await event.client.download_media(reply, file=str(fpath))
            if not path:
                raise RuntimeError("download failed")

            cover_path = None
            if cover_msg is not None:
                cover_path = str(Path(tmp_dir) / "cover.jpg")
                await event.client.download_media(cover_msg, file=cover_path)

            if cover_path is None:
                try:
                    from mutagen import File as _MF
                    _f = _MF(path)
                    _pics = getattr(_f, "pictures", None) or []
                    if _pics:
                        _c = str(Path(tmp_dir) / "cover_extract.jpg")
                        with open(_c, "wb") as _w:
                            _w.write(_pics[0].data)
                        cover_path = _c
                except Exception:
                    cover_path = None

            out_name = Path(path).stem + "_tagged" + Path(path).suffix
            out_path = str(Path(tmp_dir) / out_name)

            fields = {}
            if field == "cover":
                pass
            elif field == "year":
                y = _norm_year(value)
                if y:
                    fields["date"] = y
            else:
                fields[field] = value

            args_ff = ["ffmpeg", "-y", "-i", path]
            if cover_path:
                args_ff += ["-i", cover_path]
                args_ff += [
                    "-map", "0:a", "-map", "1:0",
                    "-c:a", "copy", "-c:v", "mjpeg",
                    "-disposition:v", "attached_pic",
                    "-metadata:s:v", "title=Album cover",
                    "-metadata:s:v", "comment=Cover (front)",
                ]
            else:
                args_ff += ["-map", "0", "-c", "copy"]
            for k, v in fields.items():
                args_ff += ["-metadata", "%s=%s" % (k, v)]
            args_ff += [out_path]

            proc = await asyncio.create_subprocess_exec(
                *args_ff,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(err.decode(errors="replace")[-300:])

            send_kwargs = {
                "caption": shell.wrap([
                    "saved",
                    "field    : " + field,
                    "value    : " + (_esc(value) if value else "cover"),
                ], cmd="audata", trailing=False),
                "parse_mode": "html",
                "reply_to": reply.id,
                "supports_streaming": True,
                "force_document": False,
            }
            if cover_path:
                send_kwargs["thumb"] = cover_path

            await event.client.send_file(
                event.chat_id,
                out_path,
                **send_kwargs,
            )
            try:
                await event.delete()
            except Exception:
                pass

        except Exception as e:
            log.exception("audata")
            await event.edit(shell.wrap([
                "error    : " + _esc(e),
            ], cmd="audata", trailing=True), parse_mode="html")
        finally:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
