import asyncio
import logging
import os
import sys
from telethon import TelegramClient

from core.tetko import Kernel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TETKO")

# Данные авторизации Telegram API
# Переменные окружения или параметры по умолчанию
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = "tetko_session"


async def main():
    log.info("🔥 Инициализация TETKO UserBot...")

    if not API_ID or not API_HASH:
        log.warning("⚠️ API_ID или API_HASH не заданы в окружении.")
        log.info("Убедитесь, что сессионный файл создан или переданы API ключи.")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    # Инициализация ядра TETKO
    kernel = Kernel(client=client, prefix=".")
    
    log.info("📡 Подключение к Telegram...")
    await client.start()

    # Запуск ядра и загрузка модулей
    await kernel.start()

    me = await client.get_me()
    log.info(f"✅ Успешный вход как {me.first_name} (@{me.username or me.id})")
    log.info("🚀 TETKO UserBot работает. Для остановки нажмите Ctrl+C")

    try:
        await client.run_until_disconnected()
    finally:
        await kernel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("👋 Юзербот остановлен пользователем.")
