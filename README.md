# TETKO UserBot

Версия **0.0.9.5**. Юзербот для Telegram на базе Telethon-Tetko.

Ядро: **TETKO 0.0.9.0**

## Авторы

- @flexownerAL
- @anhedonuya

## Запуск

    python main.py

## Формат модуля tetko-compat

    from core.tetko import Module, command

    class MyModule(Module):
        name = "MyModule"
        version = "1.0.0"

        @command(name="hello")
        async def hello_cmd(self, event):
            await event.edit("Привет!")
