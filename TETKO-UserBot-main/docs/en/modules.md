Module Writing Guide for the TETKO kernel (tetko-compat 0.0.9.0)
===========================================

This is the module style for TETKO UserBot. If you want to rewrite an old
module or write a new one — read this and follow the pattern.


1. What a module looks like
---------------------------

A module is a single .py file in the modules/ folder. It contains a class
that inherits from Module, with methods decorated with @command, @watcher,
@callback, @loop.

    from core.tetko import Module, command


    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.0.9.0"
        version = "1.0.0"
        author = "@username"
        description = "What the module does"

        @command(name="hello", description="Say hi")
        async def hello_cmd(self, event, args):
            await event.edit("👋 Hello!")

Put the file in modules/, name it anything (hello.py, mymodule.py).
The loader will find the class and register it automatically.


2. Class attributes
-------------------

  name          — required, module name (unique)
  __compat__    — required, API version. Write "0.0.9.0"
  version       — optional, module version ("1.0.0")
  author        — optional, author
  description   — optional, string or {"ru": "...", "en": "..."}
  config        — optional, default JSON config


3. Decorators
-------------

3.1. @command(...) — command

    @command(
        name="ping",                   # without prefix. ".ping" triggers it
        aliases=["p"],                 # aliases
        description="Measure ping",    # for .help
        only_for="owner",              # "owner" — owner only, None — everyone
    )
    async def ping_cmd(self, event, args):
        ...

Signatures:

    async def cmd(self, event):          # no args
    async def cmd(self, event, args):    # args — list of strings after command

Example with arguments:

    @command(name="echo")
    async def echo_cmd(self, event, args):
        # ".echo hello world"  →  args = ["hello", "world"]
        await event.edit(" ".join(args) or "(empty)")


3.2. @watcher() — all messages

    @watcher()
    async def on_message(self, event):
        if "spam" in (event.raw_text or ""):
            await event.delete()


3.3. @callback() — inline buttons

    @callback()
    async def on_button(self, event):
        data = event.data.decode() if isinstance(event.data, bytes) else event.data
        if data == "my_button":
            await event.answer("Pressed!")

NOTE: @callback is registered but not yet hooked into Telethon's
CallbackQuery events. Coming soon.


3.4. @loop(interval=seconds) — periodic task

    @loop(interval=60)
    async def background_task(self):
        self.log.info("Tick!")

Starts automatically on launch, stops on shutdown.


4. Lifecycle hooks
------------------

    class MyModule(Module):
        async def on_load(self):
            self.log.info("Module loaded!")

        async def on_unload(self):
            self.log.info("Module unloading...")


5. What's available inside a module
-----------------------------------

    self.kernel          # Kernel object
    self.client          # TelegramClient
    self.cfg             # ModuleConfig (JSON config for the module)
    self.log             # logging.Logger

Via self.kernel:

    self.kernel.context          # admin_id, prefix, language, handle_error
    self.kernel.registry         # module & command registry
    self.kernel.loader           # module loader
    self.kernel.dispatcher       # event dispatcher
    self.kernel.config           # raw config.json (dict)


6. Module config (saved to JSON automatically)
----------------------------------------------

    class MyModule(Module):
        name = "MyModule"
        config = {
            "enabled": True,
            "threshold": 5,
        }

        async def on_load(self):
            enabled = self.cfg.get("enabled", True)     # read
            self.cfg.set("threshold", 10)               # write
            self.cfg.delete("message")                  # delete
            data = self.cfg.all()                       # all

File: data/tetko_config/MyModule.json

API:
    cfg.get(key, default=None)
    cfg.set(key, value)
    cfg.delete(key)
    cfg.all()
    cfg[key], cfg[key] = value, key in cfg


7. Database
-----------

    from core.tetko import db_get, db_set, db_del, db_list

    db_set("mymodule", "users", [123, 456])          # save
    users = db_get("mymodule", "users", default=[])  # read
    db_del("mymodule", "users")                      # delete
    data = db_list("mymodule")                       # all

File: data/tetko_db/<namespace>.json
Namespace — usually the module name.


8. Permissions
--------------

    @command(name="eval", only_for="owner")
    async def eval_cmd(self, event, args):
        ...

  only_for="owner" — owner only.
  only_for=None    — everyone.

If not owner — reply: "🚫 This command is for the owner only."


9. Full example
---------------

    """MyModule — tetko-compat example module."""
    from __future__ import annotations

    from core.tetko import Module, command, loop, db_get, db_set


    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.0.9.0"
        version = "1.0.0"
        author = "@anhedonuya"
        description = "Demo module"

        config = {
            "greeting": "Hello!",
        }

        async def on_load(self):
            self.log.info("MyModule loaded")
            if db_get(self.name, "counter") is None:
                db_set(self.name, "counter", 0)

        async def on_unload(self):
            self.log.info("MyModule unloading")

        @command(name="hello", aliases=["hi"], description="Say hi")
        async def hello_cmd(self, event, args):
            greeting = self.cfg.get("greeting", "Hello!")
            name = " ".join(args) if args else "world"
            await event.edit(f"{greeting}, {name}!")

        @command(name="counter", description="Launch counter")
        async def counter_cmd(self, event):
            count = db_get(self.name, "counter", 0) + 1
            db_set(self.name, "counter", count)
            await event.edit(f"Counter: {count}")

        @command(name="ownerping", only_for="owner")
        async def owner_cmd(self, event):
            await event.edit("👑 Owner online")

        @loop(interval=30)
        async def tick(self):
            self.log.debug("tick")


10. What NOT to do
------------------

  - Don't write register(kernel) — that's the old style.
  - Don't use kernel.register.command(...) — old API.
  - Don't import from core.lib.*, core.kernel.*, core.native.* —
    they no longer exist.
  - Don't use core_inline.*, utils.strings.Strings, core.langpacks —
    not wired into the new kernel.
  - Don't use kernel.db_get — use db_get(namespace, key).
  - Don't use kernel.inline.form(...) — inline menus not yet available.
  - Don't use kernel.ADMIN_ID — use self.kernel.context.admin_id.


11. If something is missing
---------------------------

If a module needs functionality that's not in the API yet (inline menus,
localization, groups, ACL categories) — tell the kernel developer.
Don't copy from the old code.


12. Kernel status right now
---------------------------

Working:
  - @command, @watcher, @callback, @loop
  - Module, ModuleConfig
  - Registry, ModuleLoader, EventDispatcher, Kernel
  - db_get / db_set / db_del / db_list
  - Context (admin_id, prefix, language, handle_error)
  - only_for="owner"
  - __compat__ check
  - banner, console_reader

In progress:
  - @callback not hooked into events.CallbackQuery
  - no localization
  - no inline menus
  - no modules_custom/
  - no hot-reload
  - no permissions beyond only_for="owner"


13. Minimal template — copy and start
-------------------------------------

    """ModuleName — short description."""
    from __future__ import annotations

    from core.tetko import Module, command


    class ModuleName(Module):
        name = "ModuleName"
        __compat__ = "0.0.9.0"
        version = "1.0.0"
        author = "@username"
        description = "Module description"

        @command(name="command", description="What it does")
        async def command_cmd(self, event, args):
            await event.edit("Result")
