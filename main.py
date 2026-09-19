"""TETKO UserBot — точка входа на новом ядре core.tetko."""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from telethon import TelegramClient

from core.tetko import Kernel
from core.tetko.bot import BotClient
from core.tetko.banner import render_banner


# Приглушаем Telethon (много служебных сообщений)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("TETKO")

CONFIG_PATH = Path("config.json")


def load_config() -> dict:
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


async def console_reader() -> None:
    """Читает команды из консоли Termux (только после авторизации)."""
    loop = asyncio.get_event_loop()
    print()
    print("\033[1;92m[console] Команды: restart | stop | help\033[0m")
    print()
    sys.stdout.flush()

    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            cmd = line.strip().lower()
            if not cmd:
                continue

            if cmd == "restart":
                print("\033[1;93m[console] 🔄 Перезапуск TETKO...\033[0m")
                sys.stdout.flush()
                await asyncio.sleep(0.5)
                os.execv(sys.executable, [sys.executable] + sys.argv)
                return
            elif cmd == "stop":
                print("\033[1;91m[console] 🛑 Остановка TETKO...\033[0m")
                sys.stdout.flush()
                os._exit(0)
            elif cmd == "help":
                print("\033[1;92m[console] Команды: restart | stop | help\033[0m")
                sys.stdout.flush()
            else:
                print(f"\033[1;91m[console] Неизвестная команда: {cmd!r}. Введи help\033[0m")
                sys.stdout.flush()

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"\033[1;91m[console] Ошибка: {e}\033[0m")
            sys.stdout.flush()


async def main():
    cfg = load_config()

    api_id = int(cfg["api_id"])
    api_hash = cfg["api_hash"]
    phone = cfg.get("phone") or None
    prefix = cfg.get("command_prefix", ".")
    session_name = "tetko"

    log.info("🔥 Инициализация TETKO UserBot...")
    log.info(f"   • api_id: {api_id}")
    log.info(f"   • phone:  {phone or '(из сессии)'}")
    log.info(f"   • prefix: {prefix!r}")

    client = TelegramClient(session_name, api_id, api_hash)

    log.info("📡 Подключение к Telegram...")
    await client.start(phone=phone)

    # Автоопределение admin_id, если его нет в конфиге
    if not cfg.get("admin_id"):
        me = await client.get_me()
        cfg["admin_id"] = me.id
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            log.info(f"👑 admin_id определён автоматически: {me.id} (@{me.username}) и записан в config.json")
        except Exception as e:
            log.error(f"❌ Не удалось записать admin_id в config.json: {e}")

    kernel = Kernel(client=client, prefix=prefix, config=cfg)

    await kernel.start()

    # ── Запуск inline-бота (если есть токен) ──
    bot_client = None
    bot_token = cfg.get("inline_bot_token")
    if bot_token:
        try:
            bot_client = BotClient(
                api_id=api_id,
                api_hash=api_hash,
                bot_token=bot_token,
                kernel=kernel,
            )
            await bot_client.start()
            kernel.bot_client = bot_client
            log.info(f"🤖 Inline-бот подключён: @{bot_client.username}")
        except Exception as e:
            log.error(f"❌ Не удалось запустить inline-бота: {e}")
            bot_client = None

    os.system("clear")

    print(render_banner(version="0.0.9.7", codename="native"))
    print()
    print("  \033[1;92m[>]\033[0m Kernel:  loaded successfully")
    modules = list(kernel.registry.list_modules().keys()) or ["none"]
    print(f"  \033[1;92m[>]\033[0m Modules: {len(modules)} ({', '.join(modules)})")
    print("  \033[1;92m[>]\033[0m Compat:  tetko-compat 0.0.9.0")
    print(f"  \033[1;92m[>]\033[0m Owner:   {kernel.context.admin_id}")
    print()
    print("\033[1;92mTETKO loaded\033[0m")
    sys.stdout.flush()

    console_task = asyncio.create_task(console_reader())

    try:
        await client.run_until_disconnected()
    finally:
        if console_task is not None:
            console_task.cancel()
            try:
                await console_task
            except asyncio.CancelledError:
                pass
        await kernel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Юзербот остановлен пользователем.")
