import logging
from core.tetko import Module, command, watcher, db_get, db_set

log = logging.getLogger("TETKO.module.aliases")

NS = "aliases"
KEY = "map"


class Aliases(Module):
    name = "Aliases"
    __compat__ = "0.0.9.0"
    version = "1.0.0"
    author = "@flexownerAL"
    description = {
        "ru": "Глобальные алиасы для команд",
        "en": "Global command aliases",
    }

    def _get_map(self) -> dict:
        data = db_get(NS, KEY, {})
        return dict(data) if isinstance(data, dict) else {}

    def _set_map(self, m: dict):
        db_set(NS, KEY, m)

    def _esc(self, t) -> str:
        if t is None:
            return "—"
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @command("addalias", aliases=["aalias"], description="Add alias to a command")
    async def cmd_addalias(self, event, args):
        if len(args) < 2:
            await event.edit(
                "<blockquote>Usage: <code>.addalias &lt;command&gt; &lt;alias&gt;</code>\n"
                "Example: <code>.addalias ping p</code></blockquote>",
                parse_mode="html",
            )
            return

        target = args[0].strip().lstrip(".").lower()
        alias = args[1].strip().lstrip(".").lower()

        if target == alias:
            await event.edit("<blockquote>Alias equals command</blockquote>", parse_mode="html")
            return

        registry = self.kernel.registry
        if registry.find_command(alias):
            await event.edit(
                f"<blockquote><code>.{self._esc(alias)}</code> is already taken</blockquote>",
                parse_mode="html",
            )
            return

        if not registry.find_command(target):
            await event.edit(
                f"<blockquote>Command <code>.{self._esc(target)}</code> not found</blockquote>",
                parse_mode="html",
            )
            return

        m = self._get_map()
        m[alias] = target
        self._set_map(m)

        await event.edit(
            f"<blockquote><code>.{self._esc(alias)}</code> → <code>.{self._esc(target)}</code></blockquote>",
            parse_mode="html",
        )

    @command("delalias", aliases=["dalias"], description="Delete alias")
    async def cmd_delalias(self, event, args):
        if not args:
            await event.edit(
                "<blockquote>Usage: <code>.delalias &lt;alias&gt;</code></blockquote>",
                parse_mode="html",
            )
            return

        alias = args[0].strip().lstrip(".").lower()
        m = self._get_map()

        if alias not in m:
            await event.edit(
                f"<blockquote>Alias <code>.{self._esc(alias)}</code> not found</blockquote>",
                parse_mode="html",
            )
            return

        target = m.pop(alias)
        self._set_map(m)

        await event.edit(
            f"<blockquote><code>.{self._esc(alias)}</code> (→ <code>.{self._esc(target)}</code>) removed</blockquote>",
            parse_mode="html",
        )

    @command("aliases", aliases=["alist"], description="List aliases")
    async def cmd_aliases(self, event, args):
        m = self._get_map()
        if not m:
            await event.edit("<blockquote>No aliases</blockquote>", parse_mode="html")
            return

        lines = [
            f"<code>.{self._esc(a)}</code> → <code>.{self._esc(c)}</code>"
            for a, c in sorted(m.items())
        ]
        body = "\n".join(lines)
        await event.edit(
            f"<blockquote><b>Aliases ({len(m)})</b>\n{body}</blockquote>",
            parse_mode="html",
        )

    @watcher()
    async def watch(self, event):
        text = (event.raw_text or "").strip()
        prefix = self.kernel.context.prefix

        if not text.startswith(prefix):
            return

        body = text[len(prefix):].lstrip()
        if not body:
            return

        parts = body.split(maxsplit=1)
        word = parts[0].lower()

        m = self._get_map()
        target = m.get(word)
        if not target:
            return

        rest = parts[1] if len(parts) > 1 else ""
        new_text = f"{prefix}{target}" + (f" {rest}" if rest else "")

        cmd = self.kernel.registry.find_command(target)
        if not cmd:
            return

        if cmd.only_for == "owner":
            sender_id = getattr(event, "sender_id", None)
            if not self.kernel.context.is_owner(sender_id):
                try:
                    await event.edit("This command is for the owner only.")
                except Exception:
                    pass
                return

        try:
            event.raw_text = new_text
            if hasattr(event, "message") and event.message is not None:
                try:
                    event.message.message = new_text
                except Exception:
                    pass
            args = rest.split() if rest else []
            await cmd.call(self.client, event, args)
        except Exception as e:
            log.exception(f"alias {word} -> {target} failed: {e}")
