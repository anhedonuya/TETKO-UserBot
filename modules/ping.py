import time
from core.tetko import Module, command


class PingModule(Module):
    name = "Ping"
    __compat__ = "0.0.9.0"
    description = "Проверка задержки и состояния TETKO Юзербота"
    author = "@anhedonuya"
    version = "1.2.0"

    @command(name="ping", description="Измерить пинг бота")
    async def ping_cmd(self, event):
        start = time.perf_counter()
        await event.edit(
            '<tg-emoji emoji-id="5345988476716226868">🤔</tg-emoji>',
            parse_mode="html",
        )
        end = time.perf_counter()
        ms = round((end - start) * 1000, 2)

        # премиум-флаг установлен ядром при старте
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
