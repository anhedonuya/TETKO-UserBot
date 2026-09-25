TETKO UserBot Installation
==========================

Requirements
------------

- Python 3.10+
- pip, git
- Termux (Android), Debian/Ubuntu (Linux) or VPS

Termux (Android)
----------------

Install Termux from F-Droid, not from Play Store.

    pkg update && pkg upgrade -y
    pkg install python git clang libffi openssl rust binutils -y
    pip install --upgrade pip wheel

Linux (Debian / Ubuntu)
-----------------------

    sudo apt update
    sudo apt install python3 python3-pip git build-essential libffi-dev libssl-dev -y
    pip3 install --upgrade pip wheel

Clone and dependencies
----------------------

    git clone https://github.com/anhedonuya/TETKO-UserBot.git
    cd TETKO-UserBot
    pip install -r requirements.txt

config.json
-----------

    cp config.example.json config.json
    nano config.json

Fields:

  api_id                 — my.telegram.org → API Development
  api_hash               — same page
  phone                  — account phone (+7...)
  inline_bot_token       — token from @BotFather
  inline_bot_username    — bot username without @
  language               — ru / en / uk (default ru)

Inline bot
----------

Inline menus require a separate bot. Steps:

1. @BotFather → /newbot → name and username (…_bot)
2. Copy the token (123456:ABC-DEF…)
3. /setinline → choose bot → placeholder
4. Paste token and username into config.json

Running
-------

    python main.py

First run:

- Telethon will ask for the confirmation code
- Enter the code from Telegram
- Bot detects admin_id and saves it to config.json

Expected startup:

    🤖 Inline-бот подключён: @your_bot
    MCUB inline запущен, bot_client=…
    ✅ Ядро TETKO полностью инициализировано и готово!

Console:

    [console] Commands: restart | stop | help

Updating
--------

    cd TETKO-UserBot
    git pull
    pip install -r requirements.txt

Then Ctrl+C → python main.py.

Troubleshooting
---------------

**Bot token expired**
Bot token revoked. @BotFather → /mybots → API Token → Revoke.
Update inline_bot_token, remove sessions/inline_bot.session*.

**Buttons don't work for others**
Inline bot allows only owner and trusted users. Manage with:
.trustaccess, .inlineforall, .inlinesec.

**Commands not visible in .tek**
Check __compat__ = "0.0.9.0" and class inherits Module.
See main.log for details.
