Ядро TETKO
==========

Обзор
-----

Ядро собирается из пакета `core/tetko/`. Компоненты:

    core/tetko/
      kernel.py        — Kernel: главный объект, жизненный цикл
      module.py        — базовый класс Module
      decorators.py    — @command, @watcher, @callback, @loop
      registry.py      — Registry: реестр модулей и команд
      loader.py        — ModuleLoader: загрузка/выгрузка модулей
      dispatcher.py    — EventDispatcher: маршрутизация событий
      config.py        — ModuleConfig: JSON-конфиг модуля
      context.py       — Context: admin_id, prefix, language
      db.py            — db_get / db_set / db_del / db_list
      inline.py        — Inline: инлайн-меню (make_button, form, edit)
      exceptions.py    — TetkoError и наследники
      mcub_compat/     — совместимость с MCUB-модулями

Kernel
------

Главный объект. Создаётся в main.py, стартует через `await kernel.start()`.

Атрибуты:

    kernel.client          — Telethon TelegramClient (юзербот)
    kernel.bot_client      — TelegramClient инлайн-бота
    kernel.config          — сырой config.json (dict)
    kernel.context         — Context
    kernel.registry        — Registry
    kernel.loader          — ModuleLoader
    kernel.dispatcher      — EventDispatcher
    kernel.inline          — Inline
    kernel.cache           — кэш (set/get с ttl)
    kernel.VERSION         — версия ядра
    kernel.UPDATE_REPO     — репозиторий обновлений
    kernel.loaded_modules  — загруженные модули
    kernel.system_modules  — системные модули

Жизненный цикл:

    kernel = Kernel(client, config)
    await kernel.start()
    # ... работа ...
    await kernel.stop()

start() делает:

1. Загружает модули из `modules/` и `modules_custom/`
2. Регистрирует обработчики Telethon (NewMessage, CallbackQuery)
3. Запускает @loop-задачи модулей
4. Поднимает инлайн-бота (если задан inline_bot_token)

Module
------

Базовый класс модуля. Подробности — в [modules.md](modules.md).

    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.0.9.0"

        async def on_load(self): ...
        async def on_unload(self): ...

Регистрация команд идёт через `__init_subclass__` — при наследовании от
Module декораторы собираются в метаданные, которые читает Registry.

Registry
--------

Хранит модули и команды.

    kernel.registry.list_modules()           # все модули
    kernel.registry.list_commands()          # все команды
    kernel.registry.get_command("ping")      # найти по имени/алиасу
    kernel.registry.list_callbacks()         # @callback-хендлеры
    kernel.registry.list_loops()             # @loop-задачи

ModuleLoader
------------

Загрузка и выгрузка модулей из `modules/` и `modules_custom/`.

    await kernel.loader.load_module_from_file(path)
    await kernel.loader.load_module_from_url(url)
    await kernel.loader.unload_module(name)

Каждый модуль проходит проверку `__compat__` (см. `core/version.py`).

EventDispatcher
---------------

Маршрутизация входящих событий от Telethon.

    kernel.dispatcher.handle_message(client, event)   # NewMessage
    kernel.dispatcher.handle_callback(client, event)  # CallbackQuery

Проверяет права (only_for="owner"), вызывает @command / @watcher.
Для callback — сначала inline-хендлеры (`kernel.inline`), затем
`@callback`-модули.

Inline
------

Инлайн-меню (кнопки) через отдельного бота.

    buttons = [[kernel.inline.make_button("Метка", callback, ttl=600)]]
    await kernel.inline.form(chat_id, "Текст", buttons)
    await kernel.inline.edit(event_or_cb, "Новый текст", buttons)

Доступ ограничен владельцем и trusted (namespace `inline_perm` в БД,
см. [modules.md §11](modules.md)).

Context
-------

    kernel.context.admin_id      # владелец
    kernel.context.prefix        # префикс команд, по умолчанию "."
    kernel.context.language      # текущий язык (ru/en/uk)
    kernel.context.handle_error  # хелпер для ошибок

Config
------

ModuleConfig — JSON-файл модуля в `data/tetko_config/<Name>.json`.

    self.cfg.get(key, default)
    self.cfg.set(key, value)
    self.cfg.delete(key)
    self.cfg.all()

DB
--

Простая JSON-БД в `data/tetko_db/<namespace>.json`.

    from core.tetko import db_get, db_set, db_del, db_list

    db_set("mymodule", "users", [123, 456])
    users = db_get("mymodule", "users", default=[])

Исключения
----------

Все наследуют TetkoError: ModuleError, ModuleLoadError,
ModuleValidationError, ModuleRegistrationError, ModuleNotFoundError,
CommandError, CommandNotFoundError, CommandRegistrationError, ConfigError.

Совместимость (mcub_compat)
---------------------------

Пакет `core/tetko/mcub_compat/` даёт совместимость со старым стилем
MCUB-модулей: `kernel.register`, `ModuleBase`, `@command` с `doc=`,
inline API, callback dispatch. Новые модули лучше писать в tetko-compat.
