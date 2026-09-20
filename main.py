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


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit("Настройка отменена.")
    return value or default


def _ask_secret(prompt: str, default: str = "") -> str:
    """Read a secret without echoing it when getpass is available."""
    try:
        import getpass
        value = getpass.getpass(f"{prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit("Настройка отменена.")
    return value or default


def _save_config(cfg: dict) -> None:
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, CONFIG_PATH)


def _needs_first_run(cfg: dict | None) -> bool:
    if not cfg:
        return True
    # Values shipped in config.example.json are placeholders and must never
    # be treated as a completed setup.
    placeholders = {
        "api_id": {"12345678", "0", ""},
        "api_hash": {"", "0123456789abcdef0123456789abcdef"},
        "phone": {"", "+10000000000"},
    }
    for key, bad_values in placeholders.items():
        value = str(cfg.get(key, ""))
        if value in bad_values:
            return True
    try:
        return int(cfg.get("api_id")) <= 0 or not str(cfg.get("api_hash", "")).strip()
    except (TypeError, ValueError):
        return True


def first_run_setup(existing: dict | None = None) -> dict:
    """Interactive first-run wizard for a clean Termux installation."""
    cfg = dict(existing or {})
    print("\n" + "=" * 60)
    print("  TETKO UserBot — первоначальная настройка")
    print("=" * 60)
    print("Нужны API ID/API HASH с my.telegram.org.")
    print("Токен inline-бота можно пропустить и добавить позже.")
    print()

    while True:
        raw_id = _ask("API ID", str(cfg.get("api_id", "")))
        try:
            api_id = int(raw_id)
            if api_id <= 0:
                raise ValueError
            break
        except ValueError:
            print("❌ API ID должен быть положительным числом.")

    while True:
        api_hash = _ask_secret("API HASH", str(cfg.get("api_hash", "")))
        if len(api_hash) >= 20:
            break
        print("❌ API HASH выглядит слишком коротким. Проверь значение с my.telegram.org.")

    phone = _ask("Номер Telegram", str(cfg.get("phone", "")))
    if phone and not phone.startswith("+"):
        phone = "+" + phone

    prefix = _ask("Префикс команд", str(cfg.get("command_prefix", ".")) or ".")
    if not prefix:
        prefix = "."

    print("\n--- Inline-бот ---")
    print("Создай бота через @BotFather и вставь токен ниже.")
    print("Enter — пропустить настройку inline-бота.")
    bot_token = _ask_secret("Токен бота", str(cfg.get("inline_bot_token") or ""))
    bot_username = _ask("Username бота без @", str(cfg.get("inline_bot_username") or "")) if bot_token else ""
    if bot_username.startswith("@"):
        bot_username = bot_username[1:]

    print("\n--- Дополнительно ---")
    language = _ask("Язык", str(cfg.get("language", "ru")) or "ru")

    cfg.update({
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone,
        "command_prefix": prefix,
        "inline_bot_token": bot_token or None,
        "inline_bot_username": bot_username or None,
        "language": language or "ru",
        "db_version": int(cfg.get("db_version", 2) or 2),
    })
    _save_config(cfg)
    print(f"\n✅ Настройка сохранена в {CONFIG_PATH}.")
    print("🔐 Код входа Telegram и пароль 2FA будут запрошены самим Telethon при авторизации.\n")
    return cfg


def load_config() -> dict:
    cfg = None
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                cfg = None
        except Exception as e:
            log.warning(f"⚠️ Ошибка чтения {CONFIG_PATH}: {e}. Запускаю первоначальную настройку.")

    if _needs_first_run(cfg):
        return first_run_setup(cfg)

    # Power Save is intentionally not a TETKO setting anymore.
    cfg.pop("power_save_mode", None)
    required = ["api_id", "api_hash"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        return first_run_setup(cfg)
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

    # ── Inline-бот (TETKO BotClient) ──
    # Создаём ДО kernel.start(), чтобы MCUB inline (setup_mcub_inline)
    # не перезаписал kernel.bot_client на сырой TelegramClient.
    bot_token = cfg.get("inline_bot_token")
    bot_client = getattr(kernel, "bot_client", None)
    if bot_token and not isinstance(bot_client, BotClient):
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

    await kernel.start()



    os.system("clear")

    print(render_banner(version="0.0.9.13", codename="native"))
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
