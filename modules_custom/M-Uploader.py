"""M-Uploader — загрузка файлов на файлообменники (TETKO-COMPAT 0.0.9.0)."""
from __future__ import annotations

import html
import io

import aiohttp

from core.tetko import Module, command


class MUploaderModule(Module):
    name = "M-Uploader"
    __compat__ = "0.0.9.0"
    version = "1.1.0"
    author = "@flexOwnertrue"
    description = {
        "ru": "Загрузка файлов на файлообменники",
        "en": "Upload files to file hosts",
    }

    config = {
        "timeout": 120,
    }

    # ---------- helpers ----------

    @staticmethod
    def _safe_text(value) -> str:
        return html.escape(str(value), quote=False)

    @staticmethod
    def _safe_url(value) -> str:
        return html.escape(str(value), quote=True)

    def _t(self, key: str) -> str:
        lang = getattr(self.kernel.context, "language", "ru") or "ru"
        table = self.STRINGS.get(lang) or self.STRINGS["ru"]
        return table.get(key, self.STRINGS["ru"].get(key, ""))

    def _timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(total=int(self.cfg.get("timeout", 120)))

    async def _get_file(self, event) -> io.BytesIO | None:
        reply = await event.get_reply_message()
        if not reply:
            await event.edit(self._t("reply_to_file"))
            return None

        if reply.media:
            file_bytes = await event.client.download_media(reply.media, bytes)
            if not file_bytes:
                await event.edit(self._t("no_file"))
                return None

            file = io.BytesIO(file_bytes)
            file.name = f"file_{reply.id}"

            if reply.document:
                for attr in reply.document.attributes:
                    if getattr(attr, "file_name", None):
                        file.name = attr.file_name
                        break
            elif getattr(reply, "photo", None):
                file.name = f"file_{reply.id}.jpg"
            else:
                mime = getattr(reply.document, "mime_type", None) if reply.document else None
                if mime == "image/png":
                    file.name = f"file_{reply.id}.png"
                elif mime == "image/jpeg":
                    file.name = f"file_{reply.id}.jpg"
        else:
            text = reply.raw_text or ""
            if not text.strip():
                await event.edit(self._t("reply_to_file"))
                return None
            file = io.BytesIO(text.encode("utf-8"))
            file.name = "text.txt"

        file.seek(0)
        return file

    async def _post_text(self, url: str, *, field_name: str, file: io.BytesIO, data=None):
        form = aiohttp.FormData()
        form.add_field(field_name, file, filename=getattr(file, "name", "file"))
        if data:
            for key, value in data.items():
                form.add_field(key, str(value))

        async with aiohttp.ClientSession(timeout=self._timeout()) as session:
            async with session.post(url, data=form) as response:
                text = await response.text()
                return response.status, text

    async def _post_json(self, url: str, *, field_name: str, file: io.BytesIO, data=None):
        form = aiohttp.FormData()
        form.add_field(field_name, file, filename=getattr(file, "name", "file"))
        if data:
            for key, value in data.items():
                form.add_field(key, str(value))

        async with aiohttp.ClientSession(timeout=self._timeout()) as session:
            async with session.post(url, data=form) as response:
                payload = await response.json(content_type=None)
                return response.status, payload

    async def _handle_upload(self, event, upload_func, *args, **kwargs):
        await event.edit(self._t("uploading"))
        file = await self._get_file(event)
        if not file:
            return

        try:
            result = await upload_func(*args, file=file, **kwargs)

            if isinstance(result, tuple) and len(result) == 2:
                status, data = result
                if 200 <= status < 300:
                    if isinstance(data, dict):
                        url = data.get("data", {}).get("url") or data.get("url") or data.get("id")
                        if isinstance(url, str):
                            await event.edit(self._t("uploaded").format(url=self._safe_url(url)))
                            return
                    elif isinstance(data, str):
                        url = data.strip()
                        await event.edit(self._t("uploaded").format(url=self._safe_url(url)))
                        return

            await event.edit(self._t("error").format(error=self._safe_text(status if status else "unknown")))

        except Exception as e:
            await self.kernel.context.handle_error(e, message=f"{self.name} upload failed", event=event)
            await event.edit(self._t("error").format(error=self._safe_text(e)))

    async def _handle_json_upload(self, event, url: str, field_name: str = "file", data=None):
        await event.edit(self._t("uploading"))
        file = await self._get_file(event)
        if not file:
            return

        try:
            status, payload = await self._post_json(url, field_name=field_name, file=file, data=data)

            if 200 <= status < 300 and isinstance(payload, dict):
                result_url = None
                if "data" in payload and isinstance(payload["data"], dict):
                    result_url = payload["data"].get("url")
                elif "url" in payload:
                    result_url = payload["url"]
                elif "id" in payload:
                    result_url = f"https://kappa.lol/{payload['id']}"

                if result_url:
                    await event.edit(self._t("uploaded").format(url=self._safe_url(result_url)))
                    return

            await event.edit(self._t("error").format(error=self._safe_text(status if status else "unknown")))

        except Exception as e:
            await self.kernel.context.handle_error(e, message=f"{self.name} upload failed", event=event)
            await event.edit(self._t("error").format(error=self._safe_text(e)))

    # ---------- commands ----------

    @command(name="catbox", description="Загрузить файл на catbox.moe")
    async def cmd_catbox(self, event):
        await self._handle_upload(
            event,
            self._post_text,
            "https://catbox.moe/user/api.php",
            field_name="fileToUpload",
            data={"reqtype": "fileupload"},
        )

    @command(name="envs", description="Загрузить файл на envs.sh")
    async def cmd_envs(self, event):
        await self._handle_upload(
            event,
            self._post_text,
            "https://envs.sh",
            field_name="file",
        )

    @command(name="kappa", description="Загрузить файл на kappa.lol")
    async def cmd_kappa(self, event):
        await self._handle_json_upload(
            event,
            "https://kappa.lol/api/upload",
            field_name="file",
        )

    @command(name="0x0", description="Загрузить файл на 0x0.st")
    async def cmd_0x0(self, event):
        await self._handle_upload(
            event,
            self._post_text,
            "https://0x0.st",
            field_name="file",
            data={"secret": "1"},
        )

    @command(name="x0", description="Загрузить файл на x0.at")
    async def cmd_x0(self, event):
        await self._handle_upload(
            event,
            self._post_text,
            "https://x0.at",
            field_name="file",
        )

    @command(name="tmpfiles", description="Загрузить файл на tmpfiles.org")
    async def cmd_tmpfiles(self, event):
        await self._handle_json_upload(
            event,
            "https://tmpfiles.org/api/v1/upload",
            field_name="file",
        )

    @command(name="pomf", description="Загрузить файл на pomf.lain.la")
    async def cmd_pomf(self, event):
        await self._handle_json_upload(
            event,
            "https://pomf.lain.la/upload.php",
            field_name="files[]",
        )

    @command(name="bash", description="Загрузить файл на bashupload.com")
    async def cmd_bash(self, event):
        await event.edit(self._t("uploading"))
        file = await self._get_file(event)
        if not file:
            return

        try:
            async with aiohttp.ClientSession(timeout=self._timeout()) as session:
                async with session.put("https://bashupload.com", data=file.read()) as response:
                    text = await response.text()
                    if response.ok:
                        urls = [line for line in text.splitlines() if "wget" in line]
                        if urls:
                            url = urls[0].split()[-1]
                            await event.edit(self._t("uploaded").format(url=self._safe_url(url)))
                        else:
                            await event.edit(self._t("error").format(error="Не удалось найти URL"))
                    else:
                        await event.edit(self._t("error").format(error=self._safe_text(response.status)))

        except Exception as e:
            await self.kernel.context.handle_error(e, message=f"{self.name} bash upload failed", event=event)
            await event.edit(self._t("error").format(error=self._safe_text(e)))

    @command(name="upload", description="Показать список сервисов для загрузки")
    async def cmd_upload(self, event):
        await event.edit(self._t("help"))

    async def on_load(self):
        self.log.info(f"{self.name} v{self.version} loaded")

    # ---------- strings ----------

    STRINGS = {
        "ru": {
            "uploading": '<blockquote><b>Загружаю…</b></blockquote>',
            "reply_to_file": '<blockquote><b>Ответьте на файл!</b></blockquote>',
            "no_file": '<blockquote><b>Не удалось скачать файл</b></blockquote>',
            "uploaded": '<blockquote><b>Файл загружен.</b>\n<b>URL:</b> <code><a href="{url}">{url}</a></code></blockquote>',
            "error": '<blockquote><b>Ошибка при загрузке:</b> <code>{error}</code></blockquote>',
            "help": (
                'Сервисы для загрузки:\n\n'
                '<code>.catbox</code> — catbox.moe\n'
                '<code>.envs</code> — envs.sh\n'
                '<code>.kappa</code> — kappa.lol\n'
                '<code>.0x0</code> — 0x0.st\n'
                '<code>.x0</code> — x0.at\n'
                '<code>.tmpfiles</code> — tmpfiles.org\n'
                '<code>.pomf</code> — pomf.lain.la\n'
                '<code>.bash</code> — bashupload.com\n\n'
                '<i>Желательно использовать x0, так как работает только он.</i>'
            ),
        },
        "en": {
            "uploading": '<blockquote><b>Uploading…</b></blockquote>',
            "reply_to_file": '<blockquote><b>Reply to a file!</b></blockquote>',
            "no_file": '<blockquote><b>Failed to download file</b></blockquote>',
            "uploaded": '<blockquote><b>File uploaded.</b>\n<b>URL:</b> <code><a href="{url}">{url}</a></code></blockquote>',
            "error": '<blockquote><b>Upload error:</b> <code>{error}</code></blockquote>',
            "help": (
                'Upload services:\n\n'
                '<code>.catbox</code> — catbox.moe\n'
                '<code>.envs</code> — envs.sh\n'
                '<code>.kappa</code> — kappa.lol\n'
                '<code>.0x0</code> — 0x0.st\n'
                '<code>.x0</code> — x0.at\n'
                '<code>.tmpfiles</code> — tmpfiles.org\n'
                '<code>.pomf</code> — pomf.lain.la\n'
                '<code>.bash</code> — bashupload.com\n\n'
                '<i>It is recommended to use x0, as only it works.</i>'
            ),
        },
    }