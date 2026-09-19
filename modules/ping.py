import logging
import time

from telethon.tl.types import InputMediaWebPage

from core.tetko import Module, command

log = logging.getLogger("TETKO.module.ping")

PING_BANNER = "https://raw.githubusercontent.com/anhedonuya/TETKO-UserBot/main/ping_banner.png"


class PingModule(Module):
    name = "Ping"
    __compat__ = "0.0.9.0"
    description = "Проверка задержки и состояния TETKO Юзербота"
    author = "@anhedonuya"
    version = "1.2.1"

    @command(name="ping", description="Измерить пинг бота")
    async def ping_cmd(self, event):
        start = time.perf_counter()
        await event.edit(
            '<tg-emoji emoji-id="5345988476716226868">🤔</tg-emoji>',
            parse_mode="html",
        )
        end = time.perf_counter()
        ms = round((end - start) * 1000, 2)

        has_premium = bool(getattr(self.kernel.context, "user_premium", False))

        if has_premium:
            text = (
                'пивет!! твоя '
                '<tg-emoji emoji-id="5285530631567095762">🙏</tg-emoji>'
                '<tg-emoji emoji-id="5285030066013648645">📧</tg-emoji>'
                '<tg-emoji emoji-id="5285504668489785087">🅾️</tg-emoji>'
                ' РАБОТАИТ!!!\n'
                f'по пингу все харашо {ms} '
                '<tg-emoji emoji-id="5345778951031658558">😭</tg-emoji>'
            )
        else:
            text = (
                'пивет!! твоя TETKO РАБОТАИТ!!!\n'
                f'по пингу все харашо {ms}'
            )

        try:
            from telethon.tl.functions.messages import EditMessageRequest

            # парсим HTML в entities
            parsed, entities = await self.client._parse_message_text(text, "html")

            await self.client(EditMessageRequest(
                peer=await event.get_input_chat(),
                id=event.id,
                message=parsed,
                entities=entities,
                media=InputMediaWebPage(PING_BANNER, force_large_media=True, optional=True),
                invert_media=True,
            ))
        except Exception as e:
            log.warning(f"ping: banner failed: {e}")
            await event.edit(text, parse_mode="html")

    @command(name="info", description="Информация о системе TETKO")
    async def info_cmd(self, event):
        text = (
            "🔻 <b>TETKO UserBot</b>\n"
            "▫️ <b>Стиль модулей:</b> tetko-compat 0.0.9.0\n"
            "▫️ <b>Авторы:</b> @anhedonuya, @flexownerAL\n"
            "▫️ <b>Движок:</b> Telethon (Pure)"
        )
        await event.edit(text, parse_mode="html")
