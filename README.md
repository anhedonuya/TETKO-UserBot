# TETKO UserBot

Версия **0.0.9.8**. Юзербот для Telegram на базе Telethon.

**Ядро:** TETKO · **Стиль модулей:** tetko-compat 0.0.9.0

## Авторы

- [@flexownerAL](https://github.com/flexOwnerAL)
- [@anhedonuya](https://github.com/anhedonuya)

## Требования

- **Python 3.10+**
- **pip**
- **git**
- **Termux** (Android) / **Linux** (Debian, Ubuntu) / **VPS**

## Установка

### 1. Termux (Android)

Открой **Termux** (из F-Droid, не из Play Store) и выполни:

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
- **inline_bot_token** — токен от @BotFather (см. ниже)
- **inline_bot_username** — username бота без @

### 5. Создание инлайн-бота

Для инлайн-меню нужен **свой** бот:

1. Открой **@BotFather** в Telegram.
2. `/newbot` → следуй инструкциям.
3. Получи **токен** (вида `123456:ABC-DEF...`).
4. `/setinline` → выбери бота → напиши placeholder.
5. Вставь **токен** и **username** в `config.json`.

## Запуск

    python main.py

**Первый запуск:**
- Telethon запросит код (SMS / Telegram).
- Введи код.
- Бот определит `admin_id` и запишет в `config.json`.

После запуска появится баннер и консоль:

    [console] Команды: restart | stop | help

## Использование

### Консоль Termux

- `restart` — перезапуск
- `stop` — остановка
- `help` — справка

### Команды в Telegram

- `.ping` — проверить работу
- `.dlm` — менеджер модулей (инлайн-меню)
- `.unlm <имя>` — скачать модуль в чат
- `.load <url>` — установить модуль по ссылке
- `.unload <имя>` — удалить модуль
- `.t <команда>` — shell-команда (только владелец)

## Модули

**Системные** — в `modules/` (обновляются с ядром).

**Пользовательские** — в `modules_custom/` (локальные, не публикуются).

### Установка модулей

**Через DLM:**

    .dlm

Меню с каталогом из [flexOwnerAL/repo-TETKO-modules](https://github.com/flexOwnerAL/repo-TETKO-modules).

**Вручную:**

    .load https://raw.githubusercontent.com/.../module.py

**Написание своих:**

См. [docs/ru/modules.md](docs/ru/modules.md).

## Обновление

    cd TETKO-UserBot
    git pull
    pip install -r requirements.txt

Затем `Ctrl+C` → `python main.py`.

## Документация

- [Русская](docs/ru/README.md)
- [English](docs/en/README.md)
- [Написание модулей (RU)](docs/ru/modules.md)
- [Writing modules (EN)](docs/en/modules.md)

## Лицензия

MIT. См. [LICENSE](LICENSE).
