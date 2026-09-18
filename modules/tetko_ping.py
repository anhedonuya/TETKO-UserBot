"""Тестовый TETKO-модуль: ping."""
from core.tetko import Module, command


class Ping(Module):
    """Простая команда ping."""

    name = "Ping"
    version = "1.0.0"
    author = "@anhedonuya"
    description = {
        "ru": "Проверка связи",
        "en": "Ping check",
    }

    @command("ping", aliases=["p"], doc="Проверка")
    async def cmd_ping(self, event):
        await event.edit("🏓 Pong! TETKO работает.")
