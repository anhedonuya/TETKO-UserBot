"""NeverFake commands."""
from __future__ import annotations

import html as _html
import json as _json
import time as _time
from pathlib import Path as _P


class Commands:
    def __init__(self, plugin):
        self.plugin = plugin

    def help_text(self):
        p = self.plugin.prefix
        return (
            "<blockquote><b>NeverFake</b>"
            "\n<code>" + p + "dothat nf status</code>"
            "\n<code>" + p + "dothat nf stats</code>"
            "\n<code>" + p + "dothat nf inspect &lt;domain&gt;</code>"
            "\n<code>" + p + "dothat nf cookies &lt;domain&gt;</code>"
            "\n<code>" + p + "dothat nf dump &lt;domain&gt;</code>"
            "\n<code>" + p + "dothat nf export &lt;domain&gt;</code>"
            "\n<code>" + p + "dothat nf forget &lt;domain&gt;</code>"
            "\n<code>" + p + "dothat nf cooldowns</code>"
            "\n<code>" + p + "dothat nf freeze-all</code>"
            "\n<code>" + p + "dothat nf unfreeze</code>"
            "\n<code>" + p + "dothat nf panic</code>"
            "</blockquote>"
        )

    async def dispatch(self, ctx, sub, tail):
        if sub in ("status", ""):
            return await self._status(ctx)
        if sub == "help":
            return self.help_text()
        if sub == "stats":
            return await self._stats(ctx)
        if sub == "inspect":
            return await self._inspect(ctx, tail)
        if sub == "cookies":
            return await self._cookies(ctx, tail)
        if sub == "dump":
            return await self._dump(ctx, tail)
        if sub == "export":
            return await self._export(ctx, tail)
        if sub == "forget":
            return await self._forget(ctx, tail)
        if sub == "cooldowns":
            return await self._cooldowns(ctx)
        if sub == "freeze-all":
            return await self._freeze_all(ctx)
        if sub == "unfreeze":
            return await self._unfreeze(ctx)
        if sub == "panic":
            return await self._panic(ctx)
        return self.help_text()

    async def _status(self, ctx):
        if self.plugin.store is None:
            return "<blockquote><b>NeverFake not ready</b></blockquote>"
        p = self.plugin.prefix
        return (
            "<blockquote><b>NeverFake v" + str(self.plugin.version) + "</b>"
            "\nready=<code>" + str(self.plugin._ready) + "</code>"
            "\nfrozen=<code>" + str(self.plugin._frozen) + "</code>"
            "\npatched=<code>" + str(self.plugin._patched_http) + "</code>"
            "\ndb=<code>" + _html.escape(str(self.plugin.db_path)) + "</code>"
            "\nhelp: <code>" + p + "dothat nf help</code>"
            "</blockquote>"
        )

    async def _stats(self, ctx):
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        try:
            s = self.plugin.store.global_stats()
        except Exception as e:
            return "<blockquote><b>error:</b> <code>" + _html.escape(str(e)) + "</code></blockquote>"
        lines = ["<blockquote><b>NeverFake stats</b>"]
        lines.append("identities: <code>" + str(s["identities"]) + "</code>")
        lines.append("cookies: <code>" + str(s["cookies"]) + "</code>")
        for k, v in (s.get("kinds") or {}).items():
            lines.append("  " + _html.escape(str(k)) + ": <code>" + str(v) + "</code>")
        lines.append("active cooldowns: <code>" + str(s["cooldowns"]) + "</code>")
        if s.get("top"):
            lines.append("<b>top domains:</b>")
            for d, cc in s["top"]:
                lines.append("  <code>" + _html.escape(str(d)) + "</code>: " + str(cc))
        lines.append("</blockquote>")
        return "\n".join(lines)

    async def _inspect(self, ctx, tail):
        p = self.plugin.prefix
        domain = (tail or "").strip().lower()
        if not domain:
            return "<blockquote><b>usage:</b> <code>" + p + "dothat nf inspect &lt;domain&gt;</code></blockquote>"
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        try:
            ident = self.plugin.store.get_identity(domain)
            cookies = self.plugin.store.list_cookies(domain, "")
            summary = self.plugin.store.domain_summary(domain)
        except Exception as e:
            return "<blockquote><b>error:</b> <code>" + _html.escape(str(e)) + "</code></blockquote>"
        lines = ["<blockquote><b>inspect: " + _html.escape(domain) + "</b>"]
        if ident:
            lines.append("<b>identity:</b>")
            lines.append("  visits: <code>" + str(ident.get("visit_count", 0)) + "</code>")
            created = ident.get("created_at") or 0
            if created:
                age_h = int((_time.time() - created) / 3600)
                lines.append("  age: <code>" + str(age_h) + "h</code>")
            ua = ident.get("ua_locked") or "-"
            if len(ua) > 60:
                ua = ua[:60] + "..."
            lines.append("  ua: <code>" + _html.escape(ua) + "</code>")
            lines.append("  lang: <code>" + _html.escape(str(ident.get("lang_locked") or "-")) + "</code>")
        else:
            lines.append("<i>no identity yet</i>")
        if cookies:
            lines.append("<b>cookies (" + str(len(cookies)) + "):</b>")
            by_kind = {}
            for c in cookies:
                k = c.get("kind") or "?"
                by_kind.setdefault(k, []).append(c)
            order = ["premium", "sacred", "harvest", "tracker", "seed"]
            for kind in order + [k for k in by_kind.keys() if k not in order]:
                group = by_kind.get(kind) or []
                if not group:
                    continue
                lines.append("  <b>" + _html.escape(kind) + ":</b>")
                for c in group[:10]:
                    nm = c.get("name", "?")
                    val = str(c.get("value", ""))
                    if len(val) > 32:
                        val = val[:32] + "..."
                    src = c.get("source") or "?"
                    lines.append("    <code>" + _html.escape(nm) + "</code> = <code>" + _html.escape(val) + "</code> <i>(" + _html.escape(src) + ")</i>")
                if len(group) > 10:
                    lines.append("    <i>... +" + str(len(group) - 10) + " more</i>")
        else:
            lines.append("<i>no cookies yet</i>")
        cd = summary.get("cooldowns") or {}
        if cd:
            lines.append("<b>cooldowns:</b>")
            now = _time.time()
            for name, until in cd.items():
                rem = int(until - now)
                lines.append("  " + _html.escape(str(name)) + " — <code>" + str(max(0, rem)) + "s</code>")
        lines.append("</blockquote>")
        return "\n".join(lines)

    async def _cookies(self, ctx, tail):
        p = self.plugin.prefix
        domain = (tail or "").strip().lower()
        if not domain:
            return "<blockquote><b>usage:</b> <code>" + p + "dothat nf cookies &lt;domain&gt;</code></blockquote>"
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        cookies = self.plugin.store.list_cookies(domain, "")
        if not cookies:
            return "<blockquote><i>no cookies for</i> <code>" + _html.escape(domain) + "</code></blockquote>"
        lines = ["<blockquote><b>cookies: " + _html.escape(domain) + " (" + str(len(cookies)) + ")</b>"]
        for c in cookies:
            lines.append(
                "<code>" + _html.escape(c.get("name", "?")) + "</code>"
                + " = <code>" + _html.escape(str(c.get("value", ""))[:60]) + "</code>"
                + " <i>[" + _html.escape(c.get("kind") or "?") + "]</i>"
            )
        lines.append("</blockquote>")
        return "\n".join(lines)

    async def _dump(self, ctx, tail):
        p = self.plugin.prefix
        domain = (tail or "").strip().lower()
        if not domain:
            return "<blockquote><b>usage:</b> <code>" + p + "dothat nf dump &lt;domain&gt;</code></blockquote>"
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        try:
            ident = self.plugin.store.get_identity(domain)
            cookies = self.plugin.store.list_cookies(domain, "")
            payload = {"domain": domain, "identity": ident, "cookies": cookies}
            txt = _json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception as e:
            return "<blockquote><b>error:</b> <code>" + _html.escape(str(e)) + "</code></blockquote>"
        if len(txt) > 3500:
            txt = txt[:3500] + "...(truncated)"
        return "<blockquote><b>dump " + _html.escape(domain) + "</b></blockquote>\n<pre>" + _html.escape(txt) + "</pre>"

    async def _export(self, ctx, tail):
        p = self.plugin.prefix
        domain = (tail or "").strip().lower()
        if not domain:
            return "<blockquote><b>usage:</b> <code>" + p + "dothat nf export &lt;domain&gt;</code></blockquote>"
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        out_dir = _P("data/neverfake/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in domain)
        path = out_dir / (safe + ".json")
        try:
            ident = self.plugin.store.get_identity(domain)
            cookies = self.plugin.store.list_cookies(domain, "")
            payload = {"domain": domain, "identity": ident, "cookies": cookies, "exported_at": _time.time()}
            path.write_text(_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            return "<blockquote><b>error:</b> <code>" + _html.escape(str(e)) + "</code></blockquote>"
        return "<blockquote><b>exported:</b> <code>" + _html.escape(str(path)) + "</code></blockquote>"

    async def _forget(self, ctx, tail):
        p = self.plugin.prefix
        domain = (tail or "").strip().lower()
        if not domain:
            return "<blockquote><b>usage:</b> <code>" + p + "dothat nf forget &lt;domain&gt;</code></blockquote>"
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        self.plugin.store.clear_domain(domain)
        return "<blockquote><b>forgotten:</b> <code>" + _html.escape(domain) + "</code></blockquote>"

    async def _cooldowns(self, ctx):
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        try:
            c = self.plugin.store._connect()
            with self.plugin.store._lock:
                rows = c.execute("SELECT domain, strategy, until_ts, reason FROM cooldowns WHERE until_ts > ? ORDER BY until_ts ASC", (_time.time(),)).fetchall()
        except Exception as e:
            return "<blockquote><b>error:</b> <code>" + _html.escape(str(e)) + "</code></blockquote>"
        if not rows:
            return "<blockquote><i>no active cooldowns</i></blockquote>"
        now = _time.time()
        lines = ["<blockquote><b>cooldowns (" + str(len(rows)) + ")</b>"]
        for dom, strat, until, reason in rows:
            rem = int(until - now)
            lines.append("<code>" + _html.escape(str(dom)) + "</code> · " + _html.escape(str(strat)) + " · " + str(rem) + "s · " + _html.escape(str(reason or "")))
        lines.append("</blockquote>")
        return "\n".join(lines)

    async def _freeze_all(self, ctx):
        self.plugin._frozen = True
        return "<blockquote><b>NeverFake frozen</b></blockquote>"

    async def _unfreeze(self, ctx):
        self.plugin._frozen = False
        return "<blockquote><b>NeverFake unfrozen</b></blockquote>"

    async def _panic(self, ctx):
        if self.plugin.store is None:
            return "<blockquote><b>store not ready</b></blockquote>"
        try:
            c = self.plugin.store._connect()
            with self.plugin.store._lock:
                c.execute("DELETE FROM cookies")
                c.execute("DELETE FROM identities")
                c.execute("DELETE FROM cooldowns")
                c.execute("DELETE FROM seed_stats")
                c.execute("DELETE FROM harvest_log")
                c.commit()
        except Exception as e:
            return "<blockquote><b>panic failed:</b> <code>" + _html.escape(str(e)) + "</code></blockquote>"
        self.plugin._frozen = True
        return "<blockquote><b>panic done:</b> wiped + frozen</blockquote>"
