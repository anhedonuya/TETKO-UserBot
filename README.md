# TETKO UserBot

Версия **0.0.9.19**. Юзербот для Telegram на базе Telethon.

**Ядро:** TETKO · **Стиль модулей:** tetko-compat 0.0.9.0

## Авторы

- [@flexownerAL](https://github.com/flexOwnerAL)
- [@anhedonuya](https://github.com/anhedonuya)

## Требования

- **Python 3.10+**
- **pip**, **git**
- **Termux** (Android) / **Linux** (Debian, Ubuntu) / **VPS**

## Установка

### 1. Termux (Android)

    pkg update && pkg upgrade -y
    pkg install python git clang libffi openssl rust binutils -y
    pip install --upgrade pip wheel

### 2. Linux (Debian / Ubuntu)

    sudo apt update
    sudo apt install python3 python3-pip git build-essential libffi-dev libssl-dev -y
    pip3 install --upgrade pip wheel

### 3. Клонирование

    git clone https://github.com/anhedonuya/TETKO-UserBot.git
    cd TETKO-UserBot
    pip install -r requirements.txt

### 4. Настройка config.json

    cp config.example.json config.json
    nano config.json

Заполни:

- **api_id** — https://my.telegram.org (API Development)
- **api_hash** — там же
- **phone** — номер аккаунта (в формате +7...)
- **inline_bot_token** — токен от @BotFather
- **inline_bot_username** — username бота без @

### 5. Инлайн-бот

Для инлайн-меню нужен свой бот:

1. **@BotFather** → `/newbot`
2. Получить токен (`123456:ABC-DEF...`)
3. `/setinline` → выбрать бота → placeholder
4. Вставить токен и username в `config.json`

## Запуск

    python main.py

**Первый запуск:**
- Telethon запросит код (SMS / Telegram)
- Бот определит `admin_id` и запишет в `config.json`

После старта — баннер и консоль:

    [console] Команды: restart | stop | help

## Команды

- `.ping` — проверить работу
- `.tek` — модули и команды (инлайн-меню)

## Обновление

    cd TETKO-UserBot
    git pull
    pip install -r requirements.txt

Затем `Ctrl+C` → `python main.py`.

## Документация

- [Написание модулей (RU)](docs/ru/modules.md)
- [Writing modules (EN)](docs/en/modules.md)

## Лицензия

MIT. См. [LICENSE](LICENSE).
