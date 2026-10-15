TETKO Modules Guide (tetko-compat 0.9.1)
========================================

Kernel: 0.0.10.0. Module style: tetko-compat 0.9.1.

1. Module structure
-------------------

Single .py file in modules/ (system) or modules_custom/ (user). Contains
a class inheriting Module with decorated methods.

    from core.tetko import Module, command


    class Hello(Module):
        name = "Hello"
        __compat__ = "0.9.1"
        version = "1.0.0"
        author = "@username"
        description = {"ru": "Greeter", "en": "Greeter"}

        @command(name="hello", description="Say hi")
        async def hello_cmd(self, event, args):
            await event.edit("👋 Hi!")

Loader finds the class automatically.

2. Class attributes
-------------------

    name          unique module name
    __compat__    API version, use "0.9.1"
    version       module version
    author        author
    description   string or {"ru": "...", "en": "...", "uk": "..."}
    config        default JSON config (dict)

3. Decorators
-------------

@command(name=..., aliases=[...], description=..., doc=..., only_for=None)

    @command(name="ping", aliases=["p"], description="Ping", only_for="owner")
    async def ping_cmd(self, event, args):
        ...

Signatures:
    async def cmd(self, event)
    async def cmd(self, event, args)

only_for="owner" — owner only. None — everyone.

@watcher() — every message:

    @watcher()
    async def on_message(self, event):
        if "spam" in (event.raw_text or ""):
            await event.delete()

@callback() — inline buttons:

    @callback()
    async def on_button(self, event):
        data = event.data.decode() if isinstance(event.data, bytes) else event.data
        if data == "btn1":
            await event.answer("Clicked")

@loop(interval=seconds, autostart=True) — periodic task:

    @loop(interval=3600, autostart=True)
    async def every_hour(self):
        self.log.info("hour passed")

4. Lifecycle hooks
------------------

    async def on_load(self):
        self.log.info("loaded")

    async def on_unload(self):
        self.log.info("unloaded")

5. Inside a module
------------------

    self.kernel     kernel
    self.client     TelegramClient
    self.cfg        ModuleConfig
    self.log        logger
    self.strings    localized strings (see §9)
    self._t(key, **kwargs)   get string with substitution

Via self.kernel:

    self.kernel.config        config.json (dict)
    self.kernel.context       admin_id, prefix, language
    self.kernel.registry      module/command registry
    self.kernel.loader        loader
    self.kernel.dispatcher    dispatcher
    self.kernel.inline        inline API (see §8)
    self.kernel.inline_manager  inline permissions
    self.kernel.bot_client    inline bot
    self.kernel.version_manager  kernel version check
    self.kernel.log_chat_id   log chat

6. Module config
----------------

    class MyMod(Module):
        name = "MyMod"
        config = {
            "enabled": True,
            "threshold": 5,
            "greeting": "hi",
        }

        async def on_load(self):
            enabled = self.cfg.get("enabled", True)
            self.cfg.set("threshold", 10)
            self.cfg.delete("greeting")
            data = self.cfg.all()

File: data/tetko_config/<Name>.json

API:
    cfg.get(key, default=None)
    cfg.set(key, value)
    cfg.delete(key)
    cfg.all()
    cfg[key], cfg[key] = value, key in cfg

Runtime editing — .cfg command (Tek module).

7. Database
-----------

    from core.tetko import db_get, db_set, db_del, db_list

    db_set("mymodule", "users", [123, 456])
    users = db_get("mymodule", "users", default=[])
    db_del("mymodule", "users")
    data = db_list("mymodule")

File: data/tetko_db/<namespace>.json

8. Inline menus
---------------

    async def _show(self, event):
        buttons = [[
            self.kernel.inline.make_button("Button", self._on_click, ttl=600),
        ]]
        await self.kernel.inline.edit(event, "Text", buttons)

    async def _on_click(self, event):
        await self.kernel.inline.edit(event, "Clicked", [])

API:
    kernel.inline.make_button(label, callback, ttl=600, style="primary")
    kernel.inline.form(chat_id, text, buttons)
    kernel.inline.edit(event_or_cb, text, buttons)

Button styles: primary, success, danger.

Switch-inline button (opens inline in input field):

    {"label": "✏️ edit", "kind": "switch_current", "query": "key "}

9. Localization
---------------

Module strings come from core/langpacks/<locale>.yaml under a section
named after the module in lowercase.

    # core/langpacks/en.yaml
    mymodule:
      greet: "Hello, {name}!"

    # modules/mymodule.py
    class MyMod(Module):
        name = "mymodule"

        @command(name="hi")
        async def hi_cmd(self, event, args):
            await event.edit(self._t("greet", name="world"))

Locales: ru, en, uk. Change language with .setlang.

10. Permissions (trusted)
-------------------------

only_for="owner" — owner only.
only_for=None — everyone.

Trusted check:

    from modules.trusted import Trusted
    users = await trusted._get_trusted_list()

Categories: modules, loader, config, eval, terminal.
Manage: .trustaccess, .sgroup, .trustcmd.

11. Inline permissions
----------------------

Kernel.inline_manager (namespace inline_perm in DB):

    allowed_users   [user_id, ...]
    denied_users    [user_id, ...]
    allowed_cmds    {cmd: [user_id, ...]}
    denied_cmds     {cmd: [user_id, ...]}
    everyone_mode   "all" | "groups" | "pm" | None

Owner (admin_id) always has access.

12. Logs
--------

All log.error / log.warning go to the log chat automatically (if
log_chat_id is set). Configure — .logchat command.

    self.log.info("regular")
    self.log.warning("warning → log chat")
    self.log.error("error → log chat")

13. Pip style
-------------

For a unified terminal design use core.tetko.shell:

    from core.tetko import shell

    text = shell.wrap([
        "cmd --flag",
        "",
        "  param      value",
        "  status     ok",
    ], cmd="mycommand", trailing=True)
    await event.edit(text, parse_mode="html")

Result:

    user@tetko:~$ mycommand --flag

      param      value
      status     ok

    user@tetko:~$

Used by ping, tek, cfg.

14. Full example
----------------

    """MyModule — tetko-compat 0.9.1 example."""
    from __future__ import annotations

    from core.tetko import Module, command, loop, db_get, db_set


    class MyModule(Module):
        name = "MyModule"
        __compat__ = "0.9.1"
        version = "1.0.0"
        author = "@anhedonuya"
        description = {"ru": "Demo", "en": "Demo"}

        config = {"greeting": "Hello!"}

        async def on_load(self):
            self.log.info("MyModule loaded")
            if db_get(self.name, "counter") is None:
                db_set(self.name, "counter", 0)

        async def on_unload(self):
            self.log.info("MyModule unloaded")

        @command(name="hello", aliases=["hi"], description="Say hi")
        async def hello_cmd(self, event, args):
            greeting = self.cfg.get("greeting", "Hello!")
            name = " ".join(args) if args else "world"
            await event.edit(f"{greeting}, {name}!")

        @command(name="counter", description="Counter")
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

15. Do NOT
----------

- Do not write register(kernel) — old style.
- Do not use kernel.register.command(...) — old API.
- Do not use kernel.ADMIN_ID — use self.kernel.context.admin_id.
- Do not use kernel.db_get — use db_get(namespace, key).
- Do not import from core.lib.* — only MCUB compatibility.
- Do not use core_inline.* directly.

16. Minimal template
--------------------

    """Name — short description."""
    from __future__ import annotations

    from core.tetko import Module, command


    class Name(Module):
        name = "Name"
        __compat__ = "0.9.1"
        version = "1.0.0"
        author = "@username"
        description = {"ru": "Description", "en": "Description"}

        @command(name="cmd", description="What it does")
        async def cmd_cmd(self, event, args):
            await event.edit("Result")

17. MCUB compatibility
----------------------

Kernel supports MCUB modules via core.tetko.mcub_compat. They load
alongside tetko-compat, but new modules should use tetko-compat.
