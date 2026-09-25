Установка TETKO UserBot
=======================

Требования
----------

- Python 3.10 или новее
- pip, git
- Termux (Android), Debian/Ubuntu (Linux) или VPS

Termux (Android)
----------------

Ставь Termux из F-Droid, не из Play Store.

    pkg update && pkg upgrade -y
    pkg install python git clang libffi openssl rust binutils -y
    pip install --upgrade pip wheel

Linux (Debian / Ubuntu)
-----------------------

    sudo apt update
    sudo apt install python3 python3-pip git build-essential libffi-dev libssl-dev -y
    pip3 install --upgrade pip wheel

Клонирование и зависимости
--------------------------

    git clone https://github.com/anhedonuya/TETKO-UserBot.git
    cd TETKO-UserBot
    pip install -r requirements.txt

config.json
-----------

    cp config.example.json config.json
    nano config.json

Поля:

  api_id                 — my.telegram.org → API Development
  api_hash               — там же
  phone                  — номер аккаунта в формате +7...
  inline_bot_token       — токен от @BotFather
  inline_bot_username    — username бота без @
  language               — ru / en / uk (по умолчанию ru)

Инлайн-бот
----------

Инлайн-меню работают через отдельного бота. Порядок:

1. @BotFather → /newbot → имя и username (…_bot)
2. Скопировать токен (123456:ABC-DEF…)
3. /setinline → выбрать бота → placeholder
4. Вставить токен и username в config.json

Запуск
------

    python main.py

Первый запуск:

- Telethon запросит код подтверждения
- Введи код из Telegram
- Бот определит admin_id и сохранит в config.json

Ожидаемый старт:

    🤖 Inline-бот подключён: @your_bot
    MCUB inline запущен, bot_client=…
    ✅ Ядро TETKO полностью инициализировано и готово!

Консоль:

    [console] Команды: restart | stop | help

Обновление
----------

    cd TETKO-UserBot
    git pull
    pip install -r requirements.txt

Затем Ctrl+C → python main.py.

Частые проблемы
---------------

**Bot token expired**
Токен бота отозван. @BotFather → /mybots → API Token → Revoke.
Обнови inline_bot_token в config.json, удали sessions/inline_bot.session*.

**Кнопки не работают у других**
Инлайн-бот пропускает только владельца и trusted. Управление:
.trustaccess, .inlineforall, .inlinesec.

**Команды не видны в .tek**
Проверь __compat__ = "0.0.9.0" и что класс наследует Module.
Логи смотри в main.log.
