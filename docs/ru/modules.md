TETKO-COMPAT 0.0.9.0 — гайд по написанию модулей
================================================

Это стиль модулей для TETKO UserBot. Если хочешь переписать старый модуль
или написать новый — читай и делай по образцу.


1. Как выглядит модуль
----------------------

Модуль — один .py файл в папке modules/. Внутри — класс, наследующий Module,
и методы с декораторами.

    from core.tetko import Module, command


    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.0.9.0"
        version = "1.0.0"
        author = "@username"
        description = "Что делает модуль"

        @command(name="hello", description="Поприветствовать")
        async def hello_cmd(self, event, args):
            await event.edit("👋 Привет!")

Файл положить в modules/, назвать как угодно (hello.py, mymodule.py).
Загрузчик сам найдёт класс и зарегистрирует.


2. Атрибуты класса
------------------

  name          — обязательно, имя модуля (уникальное)
  __compat__    — обязательно, версия API. Пиши "0.0.9.0"
  version       — необязательно, версия модуля ("1.0.0")
  author        — необязательно, автор
  description   — необязательно, строка или {"ru": "...", "en": "..."}
  config        — необязательно, дефолтный JSON-конфиг


3. Декораторы
-------------

3.1. @command(...) — команда

    @command(
        name="ping",                   # без префикса. ".ping" вызовет
        aliases=["p"],                 # алиасы
        description="Измерить пинг",   # для .help
        only_for="owner",              # "owner" — только владелец, None — всем
    )
    async def ping_cmd(self, event, args):
        ...

Сигнатуры:

    async def cmd(self, event):          # без аргументов
    async def cmd(self, event, args):    # args — список строк после команды

Пример с аргументами:

    @command(name="echo")
    async def echo_cmd(self, event, args):
        # ".echo hello world"  →  args = ["hello", "world"]
        await event.edit(" ".join(args) or "(пусто)")


3.2. @watcher() — на все сообщения

    @watcher()
    async def on_message(self, event):
        if "spam" in (event.raw_text or ""):
            await event.delete()


3.3. @callback() — на inline-кнопки

    @callback()
    async def on_button(self, event):
        data = event.data.decode() if isinstance(event.data, bytes) else event.data
        if data == "my_button":
            await event.answer("Нажато!")

ВНИМАНИЕ: @callback пока регистрируется, но не подключён к событиям
Telethon. Будет позже.


3.4. @loop(interval=секунды) — периодическая задача

    @loop(interval=60)
    async def background_task(self):
        self.log.info("Тик!")

Стартует автоматически при запуске, останавливается при остановке.


4. Хуки жизненного цикла
------------------------

    class MyModule(Module):
        async def on_load(self):
            self.log.info("Модуль загружен!")

        async def on_unload(self):
            self.log.info("Модуль выгружается...")


5. Что доступно внутри модуля
-----------------------------

    self.kernel          # объект Kernel
    self.client          # TelegramClient
    self.cfg             # ModuleConfig (JSON-конфиг модуля)
    self.log             # logging.Logger

Через self.kernel:

    self.kernel.context          # admin_id, prefix, language, handle_error
    self.kernel.registry         # реестр модулей и команд
    self.kernel.loader           # загрузчик
    self.kernel.dispatcher       # диспетчер
    self.kernel.config           # сырой config.json (dict)


6. Конфиг модуля (сохраняется в JSON автоматически)
---------------------------------------------------

    class MyModule(Module):
        name = "MyModule"
        config = {
            "enabled": True,
            "threshold": 5,
        }

        async def on_load(self):
            enabled = self.cfg.get("enabled", True)     # читать
            self.cfg.set("threshold", 10)               # писать
            self.cfg.delete("message")                  # удалить
            data = self.cfg.all()                       # всё

Файл: data/tetko_config/MyModule.json

API:
    cfg.get(key, default=None)
    cfg.set(key, value)
    cfg.delete(key)
    cfg.all()
    cfg[key], cfg[key] = value, key in cfg


7. База данных
--------------

    from core.tetko import db_get, db_set, db_del, db_list

    db_set("mymodule", "users", [123, 456])          # сохранить
    users = db_get("mymodule", "users", default=[])  # прочитать
    db_del("mymodule", "users")                      # удалить
    data = db_list("mymodule")                       # всё

Файл: data/tetko_db/<namespace>.json
Namespace — обычно имя модуля.


8. Права
--------

    @command(name="eval", only_for="owner")
    async def eval_cmd(self, event, args):
        ...

  only_for="owner" — только владелец бота.
  only_for=None    — всем.

Если не владелец — ответ: "🚫 Эта команда только для владельца."


9. Полный пример
----------------

    """MyModule — пример модуля TETKO-COMPAT."""
    from __future__ import annotations

    from core.tetko import Module, command, loop, db_get, db_set


    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.0.9.0"
        version = "1.0.0"
        author = "@anhedonuya"
        description = "Демо-модуль"

        config = {
            "greeting": "Привет!",
        }

        async def on_load(self):
            self.log.info("MyModule загружен")
            if db_get(self.name, "counter") is None:
                db_set(self.name, "counter", 0)

        async def on_unload(self):
            self.log.info("MyModule выгружается")

        @command(name="hello", aliases=["hi"], description="Поздороваться")
        async def hello_cmd(self, event, args):
            greeting = self.cfg.get("greeting", "Привет!")
            name = " ".join(args) if args else "мир"
            await event.edit(f"{greeting}, {name}!")

        @command(name="counter", description="Счётчик запусков")
        async def counter_cmd(self, event):
            count = db_get(self.name, "counter", 0) + 1
            db_set(self.name, "counter", count)
            await event.edit(f"Счётчик: {count}")

        @command(name="ownerping", only_for="owner")
        async def owner_cmd(self, event):
            await event.edit("👑 Владелец на связи")

        @loop(interval=30)
        async def tick(self):
            self.log.debug("tick")


10. Чего НЕ делать
------------------

  - Не писать register(kernel) — это старый стиль.
  - Не использовать kernel.register.command(...) — старый API.
  - Не импортировать из core.lib.*, core.kernel.*, core.native.* —
    их больше нет.
  - Не использовать core_inline.*, utils.strings.Strings, core.langpacks —
    не подключены.
  - Не использовать kernel.db_get — есть db_get(namespace, key).
  - Не использовать kernel.inline.form(...) — inline-меню пока нет.
  - Не использовать kernel.ADMIN_ID — есть self.kernel.context.admin_id.


11. Если чего-то не хватает
---------------------------

Если модулю нужна функциональность, которой нет в API (inline-меню,
локализация, группы, ACL-категории) — скажи разработчику ядра.
Не тащи из старого кода.


12. Что готово в ядре сейчас
----------------------------

Работает:
  - @command, @watcher, @callback, @loop
  - Module, ModuleConfig
  - Registry, ModuleLoader, EventDispatcher, Kernel
  - db_get / db_set / db_del / db_list
  - Context (admin_id, prefix, language, handle_error)
  - only_for="owner"
  - проверка __compat__
  - баннер, console_reader

В работе:
  - @callback не подключён к events.CallbackQuery
  - нет локализации
  - нет inline-меню
  - нет modules_custom/
  - нет hot-reload
  - нет прав кроме only_for="owner"


13. Минимальная заготовка — копируй и пиши
------------------------------------------

    """НазваниеМодуля — краткое описание."""
    from __future__ import annotations

    from core.tetko import Module, command


    class НазваниеМодуля(Module):
        name = "НазваниеМодуля"
        __compat__ = "0.0.9.0"
        version = "1.0.0"
        author = "@username"
        description = "Описание модуля"

        @command(name="команда", description="Что делает")
        async def команда_cmd(self, event, args):
            await event.edit("Результат")
