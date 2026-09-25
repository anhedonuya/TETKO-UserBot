TETKO Kernel
============

Overview
--------

The kernel is built from the `core/tetko/` package. Components:

    core/tetko/
      kernel.py        — Kernel: main object, lifecycle
      module.py        — Module base class
      decorators.py    — @command, @watcher, @callback, @loop
      registry.py      — Registry: modules and commands
      loader.py        — ModuleLoader: load/unload modules
      dispatcher.py    — EventDispatcher: event routing
      config.py        — ModuleConfig: per-module JSON config
      context.py       — Context: admin_id, prefix, language
      db.py            — db_get / db_set / db_del / db_list
      inline.py        — Inline: inline menus (make_button, form, edit)
      exceptions.py    — TetkoError and subclasses
      mcub_compat/     — MCUB module compatibility

Kernel
------

Main object. Created in main.py, started via `await kernel.start()`.

Attributes:

    kernel.client          — Telethon TelegramClient (userbot)
    kernel.bot_client      — inline bot TelegramClient
    kernel.config          — raw config.json (dict)
    kernel.context         — Context
    kernel.registry        — Registry
    kernel.loader          — ModuleLoader
    kernel.dispatcher      — EventDispatcher
    kernel.inline          — Inline
    kernel.cache           — cache (set/get with ttl)
    kernel.VERSION         — kernel version
    kernel.UPDATE_REPO     — update repository
    kernel.loaded_modules  — loaded modules
    kernel.system_modules  — system modules

Lifecycle:

    kernel = Kernel(client, config)
    await kernel.start()
    # ... running ...
    await kernel.stop()

start() does:

1. Loads modules from `modules/` and `modules_custom/`
2. Registers Telethon handlers (NewMessage, CallbackQuery)
3. Starts @loop tasks
4. Boots inline bot (if inline_bot_token is set)

Module
------

Base module class. Details — see [modules.md](modules.md).

    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.0.9.0"

        async def on_load(self): ...
        async def on_unload(self): ...

Registration goes through `__init_subclass__` — decorators attach
metadata to functions that Registry picks up.

Registry
--------

Stores modules and commands.

    kernel.registry.list_modules()
    kernel.registry.list_commands()
    kernel.registry.get_command("ping")
    kernel.registry.list_callbacks()
    kernel.registry.list_loops()

ModuleLoader
------------

Loads and unloads modules from `modules/` and `modules_custom/`.

    await kernel.loader.load_module_from_file(path)
    await kernel.loader.load_module_from_url(url)
    await kernel.loader.unload_module(name)

Each module is checked against `__compat__` (see `core/version.py`).

EventDispatcher
---------------

Routes incoming Telethon events.

    kernel.dispatcher.handle_message(client, event)   # NewMessage
    kernel.dispatcher.handle_callback(client, event)  # CallbackQuery

Checks permissions (only_for="owner"), calls @command / @watcher.
For callbacks — first inline handlers (`kernel.inline`), then
`@callback` modules.

Inline
------

Inline menus (buttons) via a separate bot.

    buttons = [[kernel.inline.make_button("Label", callback, ttl=600)]]
    await kernel.inline.form(chat_id, "Text", buttons)
    await kernel.inline.edit(event_or_cb, "New text", buttons)

Access is restricted to owner and trusted (namespace `inline_perm` in DB,
see [modules.md §11](modules.md)).

Context
-------

    kernel.context.admin_id      # owner
    kernel.context.prefix        # command prefix, "." by default
    kernel.context.language      # current language (ru/en/uk)
    kernel.context.handle_error  # error helper

Config
------

ModuleConfig — per-module JSON file at `data/tetko_config/<Name>.json`.

    self.cfg.get(key, default)
    self.cfg.set(key, value)
    self.cfg.delete(key)
    self.cfg.all()

DB
--

Simple JSON DB at `data/tetko_db/<namespace>.json`.

    from core.tetko import db_get, db_set, db_del, db_list

    db_set("mymodule", "users", [123, 456])
    users = db_get("mymodule", "users", default=[])

Exceptions
----------

All inherit from TetkoError: ModuleError, ModuleLoadError,
ModuleValidationError, ModuleRegistrationError, ModuleNotFoundError,
CommandError, CommandNotFoundError, CommandRegistrationError, ConfigError.

Compatibility (mcub_compat)
---------------------------

The `core/tetko/mcub_compat/` package provides compatibility with the
old MCUB module style: `kernel.register`, `ModuleBase`, `@command` with
`doc=`, inline API, callback dispatch. New modules should use tetko-compat.
