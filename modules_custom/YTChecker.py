import asyncio
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from core.tetko import Module, command


class YTChecker(Module):
    name = "YTChecker"
    __compat__ = "0.0.9.0"
    version = "2.3"
    author = "@flexOwnerAL"
    description = "checks new videos on YouTube channels"

    def __init__(self, kernel):
        super().__init__(kernel)

        if not hasattr(kernel, "_ytchecker_data"):
            kernel._ytchecker_data = {
                "channels": {},
                "chat_id": None,
                "enabled": True,
                "preview": False,
                "max_age": 24
            }

        self.data = kernel._ytchecker_data

        self.data.setdefault("channels", {})
        self.data.setdefault("chat_id", None)
        self.data.setdefault("enabled", True)
        self.data.setdefault("preview", False)
        self.data.setdefault("max_age", 24)

        self.task = None
        self._start_loop()

    def _start_loop(self):
        try:
            loop = asyncio.get_running_loop()
            self.task = loop.create_task(self._loop())
        except Exception:
            self.task = None

    async def _request(self, url):
        def fetch():
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=10
            ) as response:
                return response.read()

        return await asyncio.to_thread(fetch)

    async def _get_channel_page(self, value):
        value = value.strip()

        if value.startswith("@"):
            return "https://www.youtube.com/" + value

        if value.startswith("http://") or value.startswith("https://"):
            return value

        if re.fullmatch(
            r"UC[a-zA-Z0-9_-]{20,}",
            value
        ):
            return (
                "https://www.youtube.com/channel/"
                + value
            )

        return "https://www.youtube.com/@" + value

    async def _get_channel_id(self, value):
        value = value.strip()

        if re.fullmatch(
            r"UC[a-zA-Z0-9_-]{20,}",
            value
        ):
            return value

        match = re.search(
            r"youtube\.com/channel/(UC[a-zA-Z0-9_-]+)",
            value
        )

        if match:
            return match.group(1)

        url = await self._get_channel_page(value)

        try:
            data = await self._request(url)
            text = data.decode(
                "utf-8",
                errors="ignore"
            )
        except Exception:
            return None

        patterns = (
            r'"channelId":"(UC[a-zA-Z0-9_-]+)"',
            r'"externalId":"(UC[a-zA-Z0-9_-]+)"',
            r'"browseId":"(UC[a-zA-Z0-9_-]+)"',
            r'<meta itemprop="channelId" content="(UC[a-zA-Z0-9_-]+)">'
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                text
            )

            if match:
                return match.group(1)

        return None

    async def _get_channel_info(self, channel_id):
        url = (
            "https://www.youtube.com/feeds/videos.xml"
            "?channel_id="
            + channel_id
        )

        try:
            data = await self._request(url)
            root = ET.fromstring(data)
        except Exception:
            return None, []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015"
        }

        display_name = ""

        author = root.find(
            "atom:author",
            ns
        )

        if author is not None:
            name = author.find(
                "atom:name",
                ns
            )

            if name is not None and name.text:
                display_name = name.text.strip()

        if not display_name:
            feed_title = root.find(
                "atom:title",
                ns
            )

            if feed_title is not None and feed_title.text:
                display_name = feed_title.text.strip()

        videos = []

        for entry in root.findall(
            "atom:entry",
            ns
        ):
            video_id = entry.findtext(
                "yt:videoId",
                "",
                ns
            )

            title = entry.findtext(
                "atom:title",
                "",
                ns
            )

            published = entry.findtext(
                "atom:published",
                "",
                ns
            )

            if not video_id:
                continue

            videos.append({
                "id": video_id,
                "title": title or "untitled",
                "published": published or "",
                "url": (
                    "https://youtu.be/"
                    + video_id
                )
            })

        videos.sort(
            key=lambda item: item["published"]
        )

        return display_name, videos

    def _age_hours(self, published):
        try:
            date = datetime.fromisoformat(
                published.replace(
                    "Z",
                    "+00:00"
                )
            )

            now = datetime.now(
                timezone.utc
            )

            return (
                now - date
            ).total_seconds() / 3600

        except Exception:
            return None

    def _is_allowed_age(self, video):
        max_age = self.data.get(
            "max_age",
            24
        )

        if max_age <= 0:
            return True

        age = self._age_hours(
            video.get(
                "published",
                ""
            )
        )

        if age is None:
            return False

        return age <= max_age

    async def _check_channel(self, channel_id):
        display_name, videos = (
            await self._get_channel_info(
                channel_id
            )
        )

        if not videos:
            return []

        info = self.data[
            "channels"
        ].get(channel_id)

        if not info:
            self.data[
                "channels"
            ][channel_id] = {
                "author": display_name or "Unknown",
                "last": videos[-1]["id"]
            }

            return []

        if display_name:
            info["author"] = display_name

        last = info.get("last")

        if not last:
            info["last"] = videos[-1]["id"]
            return []

        new_videos = []
        found_last = False

        for video in videos:
            if video["id"] == last:
                found_last = True
                continue

            if found_last and self._is_allowed_age(video):
                new_videos.append(video)

        if not found_last:
            for video in videos:
                if self._is_allowed_age(video):
                    new_videos.append(video)

        info["last"] = videos[-1]["id"]

        return new_videos

    async def _send_video(
        self,
        chat_id,
        video,
        author
    ):
        title = html.escape(
            video["title"]
        )

        url = html.escape(
            video["url"],
            quote=True
        )

        channel_name = html.escape(
            author or "Unknown"
        )

        text = (
            "<blockquote>"
            "<b>new video!!</b>\n\n"
            f"<i>From {channel_name}</i>\n\n"
            f"<a href=\"{url}\">{title}</a>"
            "</blockquote>"
        )

        try:
            await self.client.send_message(
                chat_id,
                text,
                parse_mode="html",
                link_preview=self.data.get(
                    "preview",
                    False
                )
            )
        except Exception:
            try:
                await self.client.send_message(
                    chat_id,
                    text,
                    parse_mode="html"
                )
            except Exception:
                pass

    async def _check_all(self):
        if not self.data.get(
            "enabled",
            True
        ):
            return 0

        channels = self.data.get(
            "channels",
            {}
        )

        if not channels:
            return 0

        chat_id = self.data.get(
            "chat_id"
        )

        if not chat_id:
            return 0

        found = 0

        for channel_id in list(channels):
            try:
                videos = await self._check_channel(
                    channel_id
                )

                author = channels[
                    channel_id
                ].get(
                    "author",
                    "Unknown"
                )

                for video in videos:
                    await self._send_video(
                        chat_id,
                        video,
                        author
                    )

                    found += 1

            except Exception:
                continue

        return found

    async def _loop(self):
        while True:
            try:
                await asyncio.sleep(15)

                if not self.data.get("channels"):
                    continue

                if not self.data.get(
                    "enabled",
                    True
                ):
                    continue

                await self._check_all()

            except asyncio.CancelledError:
                return

            except Exception:
                await asyncio.sleep(5)

    @command("ytc")
    async def ytc(self, event, args):
        args = list(
            args or []
        )

        sub = (
            args[0].lower()
            if args
            else ""
        )

        if not sub:
            channels = self.data.get(
                "channels",
                {}
            )

            if not channels:
                await event.edit(
                    "<blockquote>"
                    "<b>ytchecker!!</b>\n\n"
                    "<i>empty</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            count = len(channels)

            first = next(
                iter(
                    channels.values()
                )
            )

            author = (
                first.get(
                    "author"
                )
                or "Unknown"
            )

            age = self.data.get(
                "max_age",
                24
            )

            age_text = (
                "disabled"
                if age <= 0
                else f"{age:g} hour(s)"
            )

            preview = (
                "enabled"
                if self.data.get(
                    "preview",
                    False
                )
                else "disabled"
            )

            await event.edit(
                "<blockquote>"
                "<b>ytchecker!!</b>\n\n"
                f"<i>2.3 From "
                f"{html.escape(author)}</i>\n\n"
                f"{count} channel(s) watching..\n"
                f"max age: {age_text}\n"
                f"link preview: {preview}\n"
                "check interval: 15 seconds"
                "</blockquote>",
                parse_mode="html"
            )

            return

        if sub == "add":
            if len(args) < 2:
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>give me a channel..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            source = args[1]

            await event.edit(
                "<blockquote>"
                "<b>doing that..</b>"
                "</blockquote>",
                parse_mode="html"
            )

            channel_id = (
                await self._get_channel_id(
                    source
                )
            )

            if not channel_id:
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>can't find this channel..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            display_name, videos = (
                await self._get_channel_info(
                    channel_id
                )
            )

            if not videos:
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>no information..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            if channel_id in self.data[
                "channels"
            ]:
                await event.edit(
                    "<blockquote>"
                    "<b>already founded!!</b>\n"
                    "<i>this channel is already watching..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            author = (
                display_name
                or "Unknown"
            )

            self.data[
                "channels"
            ][channel_id] = {
                "author": author,
                "last": videos[-1]["id"]
            }

            self.data[
                "chat_id"
            ] = event.chat_id

            await event.edit(
                "<blockquote>"
                "<b>some founded!!</b>\n\n"
                f"<b>{html.escape(author)}</b>\n"
                "<i>i'll watch this channel now..</i>"
                "</blockquote>",
                parse_mode="html"
            )

            return

        if sub in (
            "del",
            "remove",
            "rm"
        ):
            if len(args) < 2:
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>give me a channel..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            await event.edit(
                "<blockquote>"
                "<b>doing that..</b>"
                "</blockquote>",
                parse_mode="html"
            )

            channel_id = (
                await self._get_channel_id(
                    args[1]
                )
            )

            if (
                not channel_id
                or channel_id not in self.data[
                    "channels"
                ]
            ):
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>channel not found..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            author = self.data[
                "channels"
            ][channel_id].get(
                "author",
                "Unknown"
            )

            del self.data[
                "channels"
            ][channel_id]

            if not self.data[
                "channels"
            ]:
                self.data[
                    "chat_id"
                ] = None

            await event.edit(
                "<blockquote>"
                "<b>done!!</b>\n"
                f"<i>stopped watching "
                f"{html.escape(author)}..</i>"
                "</blockquote>",
                parse_mode="html"
            )

            return

        if sub == "check":
            if not self.data.get(
                "channels"
            ):
                await event.edit(
                    "<blockquote>"
                    "<b>ytchecker!!</b>\n\n"
                    "<i>empty</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            await event.edit(
                "<blockquote>"
                "<b>doing that..</b>"
                "</blockquote>",
                parse_mode="html"
            )

            found = await self._check_all()

            if found:
                await event.edit(
                    "<blockquote>"
                    "<b>some founded!!</b>\n"
                    f"<i>{found} new video(s)..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
            else:
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>nothing new..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )

            return

        if sub == "age":
            if len(args) < 2:
                age = self.data.get(
                    "max_age",
                    24
                )

                text = (
                    "disabled"
                    if age <= 0
                    else f"{age:g} hour(s)"
                )

                await event.edit(
                    "<blockquote>"
                    "<b>video age limit</b>\n"
                    f"<i>{text}</i>"
                    "</blockquote>",
                    parse_mode="html"
                )

                return

            try:
                age = float(
                    args[1]
                )

                if age < 0:
                    raise ValueError

            except ValueError:
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>use a valid number..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            self.data[
                "max_age"
            ] = age

            text = (
                "disabled"
                if age <= 0
                else f"{age:g} hour(s)"
            )

            await event.edit(
                "<blockquote>"
                "<b>done!!</b>\n"
                f"<i>max video age: {text}</i>"
                "</blockquote>",
                parse_mode="html"
            )

            return

        if sub == "preview":
            if len(args) < 2:
                state = (
                    "enabled"
                    if self.data.get(
                        "preview",
                        False
                    )
                    else "disabled"
                )

                await event.edit(
                    "<blockquote>"
                    "<b>link preview</b>\n"
                    f"<i>{state}</i>"
                    "</blockquote>",
                    parse_mode="html"
                )

                return

            state = args[1].lower()

            if state == "on":
                self.data[
                    "preview"
                ] = True

            elif state == "off":
                self.data[
                    "preview"
                ] = False

            else:
                await event.edit(
                    "<blockquote>"
                    "<b>oh, fuck..</b>\n"
                    "<i>use on or off..</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            state_text = (
                "enabled"
                if self.data[
                    "preview"
                ]
                else "disabled"
            )

            await event.edit(
                "<blockquote>"
                "<b>done!!</b>\n"
                f"<i>link preview "
                f"{state_text}..</i>"
                "</blockquote>",
                parse_mode="html"
            )

            return

        if sub == "on":
            self.data[
                "enabled"
            ] = True

            await event.edit(
                "<blockquote>"
                "<b>ytchecker is watching again..</b>"
                "</blockquote>",
                parse_mode="html"
            )

            return

        if sub == "off":
            self.data[
                "enabled"
            ] = False

            await event.edit(
                "<blockquote>"
                "<b>ytchecker stopped..</b>"
                "</blockquote>",
                parse_mode="html"
            )

            return

        if sub == "chat":
            if not self.data.get("channels"):
                await event.edit(
                    "<blockquote>"
                    "<b>ytchecker!!</b>\n\n"
                    "<i>empty</i>"
                    "</blockquote>",
                    parse_mode="html"
                )
                return

            self.data[
                "chat_id"
            ] = event.chat_id

            await event.edit(
                "<blockquote>"
                "<b>this chat is mine now..</b>"
                "</blockquote>",
                parse_mode="html"
            )

            return