from __future__ import annotations
import sys

E = chr(27)
RESET = E + "[0m"
BOLD  = E + "[1m"
DIM   = E + "[2m"
GREEN = E + "[92m"
CYAN  = E + "[96m"
YELLOW= E + "[93m"
RED   = E + "[91m"
GRAY  = E + "[90m"

if not sys.stdout.isatty():
    RESET = BOLD = DIM = GREEN = CYAN = YELLOW = RED = GRAY = ""


def header(version):
    print(BOLD + "TETKO " + str(version) + RESET)


def collect(msg):
    print(CYAN + msg + RESET)


def item(msg, status="ok"):
    if status == "ok":
        print("  " + msg)
    elif status == "warn":
        print("  " + YELLOW + msg + RESET)
    elif status == "err":
        print("  " + RED + msg + RESET)
    else:
        print("  " + msg)


def sub(msg):
    print("    " + GRAY + msg + RESET)


def done(msg):
    print(GREEN + msg + RESET)


def warn(msg):
    print(YELLOW + msg + RESET)


def err(msg):
    print(RED + msg + RESET)
