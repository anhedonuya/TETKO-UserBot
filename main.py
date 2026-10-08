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

_console = logging.StreamHandler()
_console.setLevel(logging.ERROR)
_console.setFormatter(logging.Formatter(
    "%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    datefmt="%H:%M:%S",
))

_fh = logging.FileHandler("tetko.log", encoding="utf-8", mode="w")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)-7s] %(name)s:%(lineno)d — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logging.getLogger().addHandler(_console)
logging.getLogger().addHandler(_fh)
logging.getLogger().setLevel(logging.DEBUG)

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

    try:
        ans = input(f"{C_BOLD}настроить прокси сейчас? (y/N){C_RESET}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "n"
    if ans in ("y", "yes", "д", "да"):
        setup_proxy_interactive(cfg)

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


def apply_proxy(cfg):
    proxy = cfg.get("proxy") or {}
    if not proxy.get("enabled"):
        return {}
    ptype = (proxy.get("type") or "").lower()
    host = proxy.get("host")
    port = proxy.get("port")
    if not host or not port:
        return {}

    try:
        port = int(port)
    except (TypeError, ValueError):
        return {}

    if ptype in ("socks5", "socks4", "http"):
        from python_socks import ProxyType
        tmap = {"socks5": ProxyType.SOCKS5, "socks4": ProxyType.SOCKS4, "http": ProxyType.HTTP}
        pkw = {
            "proxy_type": tmap[ptype],
            "addr": host,
            "port": port,
            "rdns": bool(proxy.get("rdns", True)),
        }
        if proxy.get("user"):
            pkw["username"] = proxy["user"]
        if proxy.get("password"):
            pkw["password"] = proxy["password"]
        return {"proxy": pkw}

    if ptype in ("mtproto", "mtproto_dd"):
        from telethon.network.connection.tcpmtproxy import ConnectionTcpMTProxyRandomizedIntermediate
        secret = proxy.get("secret") or ""
        return {
            "connection": ConnectionTcpMTProxyRandomizedIntermediate,
            "proxy": (host, port, secret),
        }

    if ptype == "mtproto_ee":
        from TelethonFakeTLS import ConnectionTcpMTProxyFakeTLS
        secret = proxy.get("secret") or ""
        return {
            "connection": ConnectionTcpMTProxyFakeTLS,
            "proxy": (host, port, secret),
        }

    return {}


def _detect_mtproto_type(secret):
    if not secret:
        return "mtproto_dd"
    s = secret.strip()
    if s.startswith("dd") or s.startswith("ee"):
        return "mtproto_ee" if s.startswith("ee") else "mtproto_dd"
    if all(c in "0123456789abcdefABCDEF" for c in s) and len(s) in (32, 34):
        return "mtproto_dd"
    return "mtproto_ee"


def setup_proxy_interactive(cfg):
    print()
    _arrow("proxy setup", color=C_CYAN)
    _hint("socks5 / http / mtproto / skip")
    print()
    try:
        raw = input(f"{C_BOLD}proxy type [skip]{C_RESET}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if not raw or raw in ("skip", "n", "no", "none"):
        cfg.pop("proxy", None)
        return

    ptype = raw
    if ptype == "socks":
        ptype = "socks5"

    try:
        host = input(f"{C_BOLD}host{C_RESET}: ").strip()
        port_raw = input(f"{C_BOLD}port{C_RESET}: ").strip()
        port = int(port_raw)
    except (EOFError, KeyboardInterrupt, ValueError):
        _err("cancelled")
        return

    entry = {"enabled": True, "type": ptype, "host": host, "port": port}

    if ptype in ("socks5", "socks4", "http"):
        u = input(f"{C_BOLD}user (optional){C_RESET}: ").strip()
        pw = input(f"{C_BOLD}password (optional){C_RESET}: ").strip()
        if u:
            entry["user"] = u
        if pw:
            entry["password"] = pw
    elif ptype in ("mtproto", "mtproto_dd", "mtproto_ee"):
        sec = input(f"{C_BOLD}secret{C_RESET}: ").strip()
        if not sec:
            _err("secret required")
            return
        entry["type"] = _detect_mtproto_type(sec) if ptype == "mtproto" else ptype
        entry["secret"] = sec
    else:
        _err(f"unknown type: {ptype}")
        return

    cfg["proxy"] = entry
    _ok(f"proxy saved: {entry.get('type')} {host}:{port}")


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
    return line



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

    _proxy_kwargs = apply_proxy(cfg)
    if _proxy_kwargs:
        _pinfo = cfg.get("proxy") or {}
        _arrow(f"proxy: {_pinfo.get('type')} {_pinfo.get('host')}:{_pinfo.get('port')}", color=C_CYAN)
    client = TelegramClient(
        session_name, api_id, api_hash,
        device_model="TETKO",
        system_version="TETKO",
        app_version=TETKO_VERSION,
        **_proxy_kwargs,
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

    _line = loading_banner(first_run=first_run)

    try:
        print(f"{C_GRAY}=>{C_RESET} clear terminal? (Y/n): ", end="")
        sys.stdout.flush()
        _ans = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if _ans.strip().lower() in ("", "y", "yes", "д", "да"):
            os.system("clear")
            print()
            print(f"{C_BOLD}=>{C_RESET} {C_ITAL}{_line}{C_RESET}")
            print()
            _rule(16)
            print(f"{C_GREEN}{C_BOLD}=> Kernel loaded <={C_RESET}")
            _rule(16)
            print()
    except Exception:
        pass

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


