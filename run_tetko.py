# SPDX-License-Identifier: MIT
# Copyright (c) 2026 flexownerAL, @anhedonuya
# ---- meta data ----- run_tetko -------------------------
# authors: @flexownerAL, @anhedonuya
# description: TETKO entry point (StandardKernel, userbot)
# ---- meta data end -------------------------------------
"""Точка входа TETKO с консольным управлением."""
import asyncio
import os
import sys

from core.version import __version__ as TETKO_VERSION
from core.kernel.standard import StandardKernel


async def console_reader():
    """Читает команды из консоли Termux.

    ВАЖНО: запускается ТОЛЬКО после kernel.start(),
    чтобы не перехватывать stdin у Telethon (SMS-код, 2FA).

    Команды:
      restart — перезапустить бота
      stop    — остановить бота
      help    — показать команды
    """
    loop = asyncio.get_event_loop()

    # Приветствие
    sys.stdout.write("\n")
    sys.stdout.write("\033[1;92m[console] Команды: restart | stop | help\033[0m\n")
    sys.stdout.write("\n")
    sys.stdout.flush()

    while True:
        try:
            # Асинхронно читаем строку из stdin
            line = await loop.run_in_executor(None, sys.stdin.readline)

            if not line:  # EOF
                break

            cmd = line.strip().lower()

            if not cmd:
                continue

            if cmd == "restart":
                sys.stdout.write("\033[1;93m[console] 🔄 Перезапуск TETKO...\033[0m\n")
                sys.stdout.flush()
                await asyncio.sleep(0.5)
                os.execv(sys.executable, [sys.executable] + sys.argv)
                return

            elif cmd == "stop":
                sys.stdout.write("\033[1;91m[console] 🛑 Остановка TETKO...\033[0m\n")
                sys.stdout.flush()
                os._exit(0)
                return

            elif cmd == "help":
                sys.stdout.write("\033[1;92m[console] Команды: restart | stop | help\033[0m\n")
                sys.stdout.flush()

            else:
                sys.stdout.write(f"\033[1;91m[console] Неизвестная команда: {cmd!r}. Введи help\033[0m\n")
                sys.stdout.flush()

        except asyncio.CancelledError:
            break
        except Exception as e:
            sys.stdout.write(f"\033[1;91m[console] Ошибка: {e}\033[0m\n")
            sys.stdout.flush()


async def main():
    # Баннер печатается в _set_boot_status
    kernel = StandardKernel()

    console_task = None

    try:
        # 1. Сначала старт (Telethon читает SMS-код, 2FA)
        if hasattr(kernel, 'start') and hasattr(kernel, 'telegram'):
            await kernel.start()
            print(f"TETKO connected to Telegram (v{TETKO_VERSION})")
            print('Loaded modules:', ', '.join(getattr(kernel.loader, 'loaded', {}) or ['none']))
        else:
            # Полный путь через миксин
            await kernel.run()
            return

        # 2. ТОЛЬКО ПОСЛЕ авторизации — console_reader
        console_task = asyncio.create_task(console_reader())

        # 3. Основной цикл (ждём до разрыва)
        await kernel.telegram.run_until_disconnected()

    except KeyboardInterrupt:
        print("\n[!] Stopped by user")

    finally:
        if console_task is not None:
            console_task.cancel()
            try:
                await console_task
            except asyncio.CancelledError:
                pass


if __name__ == '__main__':
    asyncio.run(main())
