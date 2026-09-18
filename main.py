"""TETKO UserBot — точка входа на новом ядре core.tetko."""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from telethon import TelegramClient

from core.tetko import Kernel


# ─────────── Логирование ───────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TETKO")


# ─────────── Конфиг ───────────
CONFIG_PATH = Path("config.json")


def load_config() -> dict:
    """Читает config.json. Если файла нет — падаем с понятной ошибкой."""
    if not CONFIG_PATH.exists():
        log.error(f"❌ Файл {CONFIG_PATH} не найден. Создай его из config.example.json")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        log.error(f"❌ Ошибка чтения {CONFIG_PATH}: {e}")
        sys.exit(1)

    required = ["api_id", "api_hash"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        log.error(f"❌ В config.json отсутствуют обязательные поля: {missing}")
        sys.exit(1)
    return cfg


async def main():
    cfg = load_config()

    api_id = int(cfg["api_id"])
    api_hash = cfg["api_hash"]
    phone = cfg.get("phone") or None
    prefix = cfg.get("command_prefix", ".")
    session_name = "tetko"  # совпадает с существующим tetko.session

    log.info("🔥 Инициализация TETKO UserBot...")
    log.info(f"   • api_id: {api_id}")
    log.info(f"   • phone:  {phone or '(из сессии)'}")
    log.info(f"   • prefix: {prefix!r}")

    client = TelegramClient(session_name, api_id, api_hash)

    # Ядро TETKO-COMPAT
    kernel = Kernel(client=client, prefix=prefix)

    log.info("📡 Подключение к Telegram...")
    await client.start(phone=phone)

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
