import time
from core.tetko import Module, command

class PingModule(Module):
    name = "Ping"
    __compat__ = "0.0.9.0"
    description = "Проверка задержки и состояния TETKO Юзербота"
    author = "@anhedonuya"
    version = "1.0.0"

    @command(name="ping", description="Измерить пинг бота")
    async def ping_cmd(self, event):
        start = time.perf_counter()
        msg = await event.edit("🔻 **TETKO Pinging...**")
        end = time.perf_counter()
        ms = round((end - start) * 1000, 2)
        await msg.edit(f"🔻 **TETKO KOMPAT**\n⚡ **Пинг:** `{ms} ms`")

    @command(name="info", description="Информация о системе TETKO")
    async def info_cmd(self, event):
        text = (
            "🔻 **TETKO UserBot**\n"
            "▫️ **Формат модулей:** TETKO KOMPAT v1.0\n"
            "▫️ **Авторы:** @anhedonuya, @flexownerAL\n"
            "▫️ **Движок:** Telethon (Pure)"
        )
        await event.edit(text)
