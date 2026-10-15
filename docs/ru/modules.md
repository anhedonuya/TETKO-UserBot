Гайд по модулям TETKO (tetko-compat 0.9.1)
==========================================

Версия ядра: 0.0.10.0. Стиль модулей: tetko-compat 0.9.1.

1. Как выглядит модуль
----------------------

Модуль — один .py файл в modules/ (системный) или modules_custom/
(пользовательский). Внутри — класс, унаследованный от Module, с методами
и декораторами.

    from core.tetko import Module, command


    class Hello(Module):
        name = "Hello"
        __compat__ = "0.9.1"
        version = "1.0.0"
        author = "@username"
        description = {"ru": "Приветствие", "en": "Greeter"}

        @command(name="hello", description="Поприветствовать")
        async def hello_cmd(self, event, args):
            await event.edit("👋 Привет!")

Загрузчик найдёт класс автоматически.

2. Атрибуты класса
------------------

    name          имя модуля (уникальное)
    __compat__    версия API, пиши "0.9.1"
    version       версия модуля
    author        автор
    description   строка или {"ru": "...", "en": "...", "uk": "..."}
    config        дефолтный JSON-конфиг (dict)

3. Декораторы
-------------

@command(name=..., aliases=[...], description=..., doc=..., only_for=None)

    @command(name="ping", aliases=["p"], description="Пинг", only_for="owner")
    async def ping_cmd(self, event, args):
        ...

Сигнатуры:
    async def cmd(self, event)
    async def cmd(self, event, args)

only_for="owner" — только владелец. None — всем.

@watcher() — все входящие сообщения:

    @watcher()
    async def on_message(self, event):
        if "spam" in (event.raw_text or ""):
            await event.delete()

@callback() — inline-кнопки:

    @callback()
    async def on_button(self, event):
        data = event.data.decode() if isinstance(event.data, bytes) else event.data
        if data == "btn1":
            await event.answer("Нажато")

@loop(interval=секунды, autostart=True) — периодическая задача:

    @loop(interval=3600, autostart=True)
    async def every_hour(self):
        self.log.info("час прошёл")

4. Хуки жизненного цикла
------------------------

    async def on_load(self):
        self.log.info("загружен")

    async def on_unload(self):
        self.log.info("выгружен")

5. Что доступно внутри модуля
-----------------------------

    self.kernel     ядро
    self.client     TelegramClient
    self.cfg        ModuleConfig
    self.log        логгер
    self.strings    локализованные строки (см. §9)
    self._t(key, **kwargs)   получить строку с подстановкой

Через self.kernel:

    self.kernel.config        config.json (dict)
    self.kernel.context       admin_id, prefix, language
    self.kernel.registry      реестр модулей и команд
    self.kernel.loader        загрузчик
    self.kernel.dispatcher    диспетчер
    self.kernel.inline        inline API (см. §8)
    self.kernel.inline_manager  права на inline
    self.kernel.bot_client    inline-бот
    self.kernel.version_manager  проверка версии ядра
    self.kernel.log_chat_id   лог-чат

6. Конфиг модуля
----------------

    class MyMod(Module):
        name = "MyMod"
        config = {
            "enabled": True,
            "threshold": 5,
            "greeting": "привет",
        }

        async def on_load(self):
            enabled = self.cfg.get("enabled", True)
            self.cfg.set("threshold", 10)
            self.cfg.delete("greeting")
            data = self.cfg.all()

Файл: data/tetko_config/<Name>.json

API:
    cfg.get(key, default=None)
    cfg.set(key, value)
    cfg.delete(key)
    cfg.all()
    cfg[key], cfg[key] = value, key in cfg

Редактирование в рантайме — команда .cfg (в модуле Tek).

7. База данных
--------------

    from core.tetko import db_get, db_set, db_del, db_list

    db_set("mymodule", "users", [123, 456])
    users = db_get("mymodule", "users", default=[])
    db_del("mymodule", "users")
    data = db_list("mymodule")

Файл: data/tetko_db/<namespace>.json

8. Inline-меню
--------------

    async def _show(self, event):
        buttons = [[
            self.kernel.inline.make_button("Кнопка", self._on_click, ttl=600),
        ]]
        await self.kernel.inline.edit(event, "Текст", buttons)

    async def _on_click(self, event):
        await self.kernel.inline.edit(event, "Нажато", [])

API:
    kernel.inline.make_button(label, callback, ttl=600, style="primary")
    kernel.inline.form(chat_id, text, buttons)
    kernel.inline.edit(event_or_cb, text, buttons)

Стили кнопок: primary, success, danger.

Кнопка-переключатель inline-запроса в поле ввода:

    {"label": "✏️ изменить", "kind": "switch_current", "query": "ключ "}

9. Локализация
--------------

Строки модуля берутся из core/langpacks/<locale>.yaml по секции с именем
модуля в нижнем регистре.

    # core/langpacks/ru.yaml
    mymodule:
      greet: "Привет, {name}!"

    # modules/mymodule.py
    class MyMod(Module):
        name = "mymodule"

        @command(name="hi")
        async def hi_cmd(self, event, args):
            await event.edit(self._t("greet", name="мир"))

Доступные локали: ru, en, uk. Смена языка — .setlang.

10. Права (trusted)
-------------------

only_for="owner" — только владелец.
only_for=None — всем.

Проверка trusted в коде:

    from modules.trusted import Trusted
    users = await trusted._get_trusted_list()

Категории: modules, loader, config, eval, terminal.
Управление: .trustaccess, .sgroup, .trustcmd.

11. Inline-права
----------------

Кто может пользоваться inline-ботом — kernel.inline_manager (namespace
inline_perm в БД).

    allowed_users   [user_id, ...]
    denied_users    [user_id, ...]
    allowed_cmds    {cmd: [user_id, ...]}
    denied_cmds     {cmd: [user_id, ...]}
    everyone_mode   "all" | "groups" | "pm" | None

Владелец (admin_id) всегда имеет доступ.

12. Логи
--------

Все log.error / log.warning автоматически уходят в лог-чат (если задан
log_chat_id). Настроить лог-чат — команда .logchat.

    self.log.info("обычное сообщение")
    self.log.warning("предупреждение → в лог-чат")
    self.log.error("ошибка → в лог-чат")

13. Pip-стиль вывода
--------------------

Для единого терминального дизайна используй core.tetko.shell:

    from core.tetko import shell

    text = shell.wrap([
        "команда --флаг",
        "",
        "  параметр   значение",
        "  статус     ok",
    ], cmd="mycommand", trailing=True)
    await event.edit(text, parse_mode="html")

Результат — блок вида:

    user@tetko:~$ mycommand --флаг

      параметр   значение
      статус     ok

    user@tetko:~$

Для сложных команд (ping, tek, cfg) применяется этот стиль.

14. Полный пример
-----------------

    """MyModule — пример tetko-compat 0.9.1."""
    from __future__ import annotations

    from core.tetko import Module, command, loop, db_get, db_set


    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.9.1"
        version = "1.0.0"
        author = "@anhedonuya"
        description = {"ru": "Демо", "en": "Demo"}

        config = {"greeting": "Привет!"}

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

        @command(name="counter", description="Счётчик")
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

15. Чего не делать
------------------

- Не писать register(kernel) — старый стиль.
- Не использовать kernel.register.command(...) — старый API.
- Не использовать kernel.ADMIN_ID — есть self.kernel.context.admin_id.
- Не использовать kernel.db_get — есть db_get(namespace, key).
- Не импортировать из core.lib.* — только для MCUB-совместимости.
- Не использовать core_inline.* напрямую.

16. Минимальная заготовка
-------------------------

    """Название — краткое описание."""
    from __future__ import annotations

    from core.tetko import Module, command


    class Название(Module):
        name = "Название"
        __compat__ = "0.9.1"
        version = "1.0.0"
        author = "@username"
        description = {"ru": "Описание", "en": "Description"}

        @command(name="команда", description="Что делает")
        async def команда_cmd(self, event, args):
            await event.edit("Результат")

17. Совместимость с MCUB
------------------------

Ядро поддерживает MCUB-модули через core.tetko.mcub_compat. Они
загружаются наравне с tetko-compat, но писать новые лучше в tetko-compat.
