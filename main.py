from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from telethon import TelegramClient

from core.tetko import Kernel, ui

try:
    from core.version import __version__ as TETKO_VERSION
except Exception:
    TETKO_VERSION = "0.0.9.19"


logging.getLogger("telethon").setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
_fh = logging.FileHandler("main.log", encoding="utf-8", mode="a")
_fh.setLevel(logging.INFO)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    datefmt="%H:%M:%S",
))
logging.getLogger().addHandler(_fh)
log = logging.getLogger("TETKO")


CONFIG_PATH = Path("config.json")

E = "\033["
C_RESET = E + "0m"
C_BOLD  = E + "1m"
C_DIM   = E + "2m"
C_ITAL  = E + "3m"
C_UNDER = E + "4m"
C_RED   = E + "91m"
C_GREEN = E + "92m"
C_YELLOW= E + "93m"
C_BLUE  = E + "94m"
C_MAG   = E + "95m"
C_CYAN  = E + "96m"
C_GRAY  = E + "90m"

if not sys.stdout.isatty():
    C_RESET = C_BOLD = C_DIM = C_ITAL = C_UNDER = ""
    C_RED = C_GREEN = C_YELLOW = C_BLUE = C_MAG = C_CYAN = C_GRAY = ""


def _arrow(msg, color=C_CYAN, bold=True):
    b = C_BOLD if bold else ""
    print(f"{color}{b}=>{C_RESET} {msg}")


def _hint(msg):
    print(f"   {C_GRAY}{C_ITAL}{msg}{C_RESET}")


def _err(msg):
    print(f"   {C_RED}{C_BOLD}err{C_RESET} {C_DIM}{msg}{C_RESET}")


def _ok(msg):
    print(f"{C_GREEN}{C_BOLD}=>{C_RESET} {msg}")


def _rule(n=16):
    print(f"{C_GRAY}{'=' * n}{C_RESET}")


def _save_config(cfg):
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, CONFIG_PATH)


def _needs_first_run(cfg):
    if not cfg:
        return True
    bad = {
        "api_id": {"12345678", "0", ""},
        "api_hash": {"", "0123456789abcdef0123456789abcdef"},
        "phone": {"", "+10000000000"},
    }
    for k, bads in bad.items():
        if str(cfg.get(k, "")) in bads:
            return True
    try:
        return int(cfg.get("api_id")) <= 0 or not str(cfg.get("api_hash", "")).strip()
    except (TypeError, ValueError):
        return True


def first_run_setup(existing=None):
    cfg = dict(existing or {})
    print()
    _arrow("hello tetko user, i see u are new here", color=C_MAG)
    print()

    while True:
        try:
            raw = input(f"{C_BOLD}so basically give me ur api id{C_RESET}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            _err("setup cancelled")
            raise SystemExit(1)
        try:
            api_id = int(raw)
            if api_id <= 0:
                raise ValueError
            cfg["api_id"] = api_id
            break
        except ValueError:
            _err("positive integer required")

    while True:
        try:
            api_hash = input(f"{C_BOLD}next will be api hash{C_RESET}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            _err("setup cancelled")
            raise SystemExit(1)
        if len(api_hash) >= 20:
            cfg["api_hash"] = api_hash
            break
        _err("api_hash looks too short - check my.telegram.org")

    try:
        phone = input(f"{C_BOLD}and the last one phone num{C_RESET}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        _err("setup cancelled")
        raise SystemExit(1)
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    cfg["phone"] = phone

    cfg.setdefault("command_prefix", ".")
    cfg.setdefault("language", "en")
    cfg.setdefault("db_version", 2)

    _save_config(cfg)

    print()
    _ok(f"config saved -> {C_UNDER}{CONFIG_PATH}{C_RESET}")
    _hint("login code and 2FA will be requested by Telethon on first connect")
    print()
    return cfg


def load_config():
    cfg = None
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                cfg = None
        except Exception as e:
            log.warning(f"config read error: {e}")

    if _needs_first_run(cfg):
        return first_run_setup(cfg), True

    cfg.pop("power_save_mode", None)
    missing = [k for k in ("api_id", "api_hash") if not cfg.get(k)]
    if missing:
        return first_run_setup(cfg), True
    return cfg, False


def loading_banner(first_run=False):
    line = ""
    try:
        from core.langpacks import get_kernel_strings
        locale = "ru"
        if CONFIG_PATH.exists():
            try:
                import json as _json
                _c = _json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                locale = _c.get("language", "ru") or "ru"
            except Exception:
                locale = "ru"
        k = get_kernel_strings(locale)
        if first_run:
            line = k.get("loading_first", "tetko loading in first time.., bugs? t.me/tetkosupport")
        else:
            line = k.get("loading_normal", "loading ur tetko // t.me/tetkosupport")
    except Exception:
        line = "loading ur tetko // t.me/tetkosupport"

    print()
    print(f"{C_BOLD}=>{C_RESET} {C_ITAL}{line}{C_RESET}")
    print()
    _rule(16)
    print(f"{C_GREEN}{C_BOLD}=> Kernel loaded <={C_RESET}")
    _rule(16)
    print()


async def console_reader():
    loop = asyncio.get_event_loop()
    print(f"{C_GRAY}[console] commands: {C_RESET}"
          f"{C_BOLD}restart{C_RESET} {C_GRAY}|{C_RESET} "
          f"{C_BOLD}stop{C_RESET} {C_GRAY}|{C_RESET} "
          f"{C_BOLD}help{C_RESET}")
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
                print(f"{C_YELLOW}=>{C_RESET} restarting tetko...")
                sys.stdout.flush()
                await asyncio.sleep(0.5)
                os.execv(sys.executable, [sys.executable] + sys.argv)
                return
            elif cmd == "stop":
                print(f"{C_RED}=>{C_RESET} stopping tetko...")
                sys.stdout.flush()
                os._exit(0)
            elif cmd == "help":
                print(f"{C_GRAY}[console] commands: {C_RESET}"
                      f"{C_BOLD}restart{C_RESET} {C_GRAY}|{C_RESET} "
                      f"{C_BOLD}stop{C_RESET} {C_GRAY}|{C_RESET} "
                      f"{C_BOLD}help{C_RESET}")
                sys.stdout.flush()
            else:
                print(f"{C_RED}=>{C_RESET} unknown: {cmd!r} (try help)")
                sys.stdout.flush()

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"{C_RED}=>{C_RESET} console error: {e}")
            sys.stdout.flush()


async def main():
    cfg, first_run = load_config()

    api_id = int(cfg["api_id"])
    api_hash = cfg["api_hash"]
    phone = cfg.get("phone") or None
    prefix = cfg.get("command_prefix", ".")
    session_name = "tetko"

    print()
    _arrow("connecting to telegram", color=C_CYAN)
    sys.stdout.flush()

    client = TelegramClient(
        session_name, api_id, api_hash,
        device_model="TETKO",
        system_version="TETKO",
        app_version=TETKO_VERSION,
    )

    await client.start(phone=phone)

    me = await client.get_me()

    if not cfg.get("admin_id"):
        cfg["admin_id"] = me.id
        try:
            _save_config(cfg)
            log.info(f"admin_id set to {me.id}")
        except Exception as e:
            log.error(f"admin_id save failed: {e}")

    kernel = Kernel(client=client, prefix=prefix, config=cfg)

    bot_token = cfg.get("inline_bot_token")
    if bot_token:
        try:
            from core.tetko.bot import BotClient
            existing = getattr(kernel, "bot_client", None)
            if not isinstance(existing, BotClient):
                bc = BotClient(
                    api_id=api_id,
                    api_hash=api_hash,
                    bot_token=bot_token,
                    kernel=kernel,
                )
                await bc.start()
                kernel.bot_client = bc
                log.info(f"inline bot connected: @{bc.username}")
        except Exception as e:
            log.error(f"inline bot start failed: {e}")

    await kernel.start()

    loading_banner(first_run=first_run)

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
        print(f"\n{C_GRAY}=>{C_RESET} tetko stopped")
