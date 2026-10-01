import html
import time
from urllib.parse import urlparse

from .core.store import Store
from .core.identity import Identity
from .core.policy import Policy
from .core.learning import Learning
from .core.events import EventBus
from .core.cleanup import Cleaner
from .harvest.headers import Harvester
from .seeder.progressive import plan
from .seeder.composer import compose
from .seeder.ordering import order_cookies
from .seeder.commit import commit_seeds
from .seeder.warmup import WarmupQueue
from .templates import GROUPS
from .fingerprint.referer import pick_referer
from .fingerprint.timezone import tz_for_region
from .integrations.liteflare import liteflare_solve, liteflare_headers
from .integrations.ddt_patch import install_patch
from .commands import dispatcher


DB_PATH = "data/neverfake/neverfake.db"


def _domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _region(host, module=None):
    if module is not None:
        try:
            return module._region_for_url("https://" + host + "/")
        except Exception:
            pass
    if host.endswith((".ru", ".su", ".by", ".kz")):
        return "ru"
    if host.endswith(".cn"):
        return "cn"
    return "en"


class Main:
    def __init__(self):
        self.store = Store(DB_PATH)
        self.identity = Identity(self.store)
        self.policy = Policy(self.store)
        self.learning = Learning(self.store)
        self.events = EventBus(self.store)
        self.cleaner = Cleaner(self.store)
        self.harvester = Harvester(self.store)
        self.warmup = WarmupQueue()
        self.version = "2.0.0"
        self.lib_path = ""
        self.prefix = "."
        self._ready = True
        self._frozen = False
        self._patched = False
        self._last_headers = {}
        self._module = None

    def _groups(self, cfg):
        out = []
        for name, _ in GROUPS:
            key = "seed_" + name
            if cfg.get(key, True):
                out.append(name)
        if not cfg.get("seed_session", False) and "session" in out:
            out.remove("session")
        if not cfg.get("seed_session_advanced", False) and "session_advanced" in out:
            out.remove("session_advanced")
        return out

    def _seed_for(self, domain, visit_count, enabled):
        ident = self.identity.get_or_create(domain)
        groups = plan(visit_count, enabled)
        out = []
        for gname in groups:
            for name, fn in GROUPS:
                if name != gname:
                    continue
                try:
                    entries = fn(ident, self.identity.derive_int, self.identity.derive)
                except Exception:
                    entries = []
                for name2, value, ttl, path, ss in entries:
                    exp = time.time() + ttl if ttl else None
                    out.append({"name": name2, "value": value, "path": path, "expires_at": exp, "secure": False, "http_only": False, "same_site": ss, "kind": "seed", "source": "template:%s" % gname})
        return ident, out

    async def before_fetch(self, ctx):
        if not self._ready or self._frozen:
            return None
        if not ctx.cfg.get("enabled", True):
            return None
        url = ctx.get("url") or ""
        if not url:
            return None
        domain = _domain(url)
        if not domain:
            return None
        try:
            self.prefix = ctx.kernel.context.prefix or "."
        except Exception:
            self.prefix = "."
        if self.learning.should_drift(domain):
            self.events.emit("nf.drift", domain, {})
            self.store.clear_domain(domain)
            self.learning.clear_drift(domain)
        if self.learning.cooldown_active(domain, "fetch"):
            return None
        thr = float(ctx.cfg.get("throttle_per_domain_sec", 1.5) or 1.5)
        if not self.learning.throttle_ok(domain, thr):
            return None
        enabled = self._groups(ctx.cfg)
        try:
            ident, seeds = self._seed_for(domain, (self.store.get_identity(domain) or {}).get("visit_count", 0), enabled)
        except Exception:
            return None
        nf_signed = bool(ctx.cfg.get("never_fake_signed", True))
        filtered = [s for s in seeds if not (nf_signed and self.policy.is_signed(s["name"])) and self.policy.can_seed(s["name"])]
        existing = self.store.list_cookies(domain, "")
        merged = {c["name"]: c for c in existing}
        for s in filtered:
            if s["name"] not in merged:
                merged[s["name"]] = s
        entries = order_cookies(list(merged.values()))
        cap = int(ctx.cfg.get("max_cookies_per_request", 20) or 20)
        if len(entries) > cap:
            entries = entries[:cap]
        try:
            commit_seeds(self.store, domain, "", filtered)
            self.identity.bump_visit(domain)
            self.learning.mark_visit(domain)
        except Exception:
            pass
        header = compose(entries)
        if not header:
            return None
        module = ctx.module
        if module is not None:
            if not hasattr(module, "_cookie_jar") or module._cookie_jar is None:
                module._cookie_jar = {}
            ident_now = self.store.get_identity(domain) or {}
            ua = ident_now.get("ua_locked")
            if not ua:
                try:
                    ua = module._pick_ua(url) or ""
                except Exception:
                    ua = ""
                if ua:
                    self.identity.lock_ua(domain, ua)
            lang = ident_now.get("lang_locked")
            if not lang:
                reg = _region(domain, module)
                lang = {"ru": "ru-RU,ru;q=0.9,en;q=0.8", "cn": "zh-CN,zh;q=0.9,en;q=0.8"}.get(reg, "en-US,en;q=0.9")
                self.identity.lock_lang(domain, lang)
            tz = ident_now.get("tz_locked")
            if not tz:
                reg = _region(domain, module)
                self.identity.lock_tz(domain, tz_for_region(reg))
            module._cookie_jar[domain] = {"cookie": header, "ua": ua or "", "proxy": "", "expires": time.time() + 3600}
        return None

    async def after_fetch(self, ctx):
        if not self._ready or self._frozen:
            return None
        url = ctx.get("url") or ""
        html_text = ctx.get("html") or ""
        status = ctx.get("status") or 200
        domain = _domain(url)
        if not domain:
            return None
        if html_text and ctx.cfg.get("harvest_js_cookies", True):
            try:
                got = self.harvester.from_html(domain, "", html_text, status)
                if got:
                    self.policy.apply_harvest(domain, "", got, status)
            except Exception:
                pass
        if status in (401, 403, 429, 503):
            self.learning.mark_fail(domain)
        if status in (200, 201, 204):
            self.learning.note_success(domain, "fetch")
            self.events.emit("nf.success", domain, {"status": status})
        return None

    async def on_blocked(self, ctx):
        if not self._ready:
            return None
        url = ctx.get("url") or ""
        reason = str(ctx.get("reason") or "blocked").lower()
        domain = _domain(url)
        if not domain:
            return None
        hours = int(ctx.cfg.get("cooldown_hours_default", 24) or 24)
        self.learning.mark_fail(domain)
        self.learning.note_outcome(domain, "fetch", reason, default_hours=hours)
        self.events.emit("nf.blocked", domain, {"reason": reason})
        try:
            self.store.clear_domain(domain)
        except Exception:
            pass
        if ctx.cfg.get("rotate_ua_on_block", True):
            self.identity.lock_ua(domain, "")
            self.identity.lock_lang(domain, "")
        if not ctx.cfg.get("call_liteflare_on_block", True):
            return None
        page = await liteflare_solve(ctx, url, reason)
        if not (isinstance(page, str) and len(page) > 500):
            return None
        headers, status = await liteflare_headers(ctx, url)
        if headers:
            try:
                got = self.harvester.from_response_headers(domain, "", headers, status or 200)
                for c in (got or []):
                    nm = (c.get("name") or "").lower()
                    if nm in ("cf_clearance", "__cf_bm", "datadome", "_abck"):
                        c["kind"] = "premium"
                        self.store.put_cookie(domain, "", c)
                        self.events.emit("nf.premium", domain, {"name": nm})
            except Exception:
                pass
        try:
            got2 = self.harvester.from_html(domain, "", page, status or 200)
            if got2:
                self.policy.apply_harvest(domain, "", got2, status or 200)
        except Exception:
            pass
        self.events.emit("nf.liteflare_bypass", domain, {"bytes": len(page)})
        return page

    async def on_js_required(self, ctx):
        return None

    async def on_error(self, ctx):
        url = ctx.get("url") or ""
        err = str(ctx.get("error") or "").lower()
        domain = _domain(url)
        if not domain:
            return None
        if "timeout" in err or "timed out" in err:
            self.store.set_cooldown(domain, "fetch", 0, "reset")
        if "refused" in err or "connection" in err:
            self.identity.lock_ua(domain, "")
        return None

    async def on_result(self, ctx):
        return None

    async def on_command(self, ctx):
        if not self._ready:
            return None
        action = (ctx.get("action") or "").lower()
        if action != "nf":
            return None
        parts = ctx.get("parts") or []
        sub = parts[1].lower() if len(parts) > 1 else "status"
        tail = parts[2] if len(parts) > 2 else ""
        try:
            self.prefix = ctx.kernel.context.prefix or "."
        except Exception:
            pass
        event = ctx.get("event")
        if event is None:
            return None
        try:
            text = await dispatcher.dispatch(self, ctx, sub, tail)
        except Exception as e:
            text = "<blockquote>nf error: <code>" + html.escape(str(e)) + "</code></blockquote>"
        try:
            await event.edit(text, parse_mode="html")
        except Exception:
            try:
                await event.respond(text, parse_mode="html")
            except Exception:
                pass
        return True

    def install_ddt_patch(self, ctx):
        def on_response(url, text, status, headers):
            domain = _domain(url)
            if not domain:
                return
            if headers:
                try:
                    got = self.harvester.from_response_headers(domain, "", headers, status)
                    for c in (got or []):
                        nm = (c.get("name") or "").lower()
                        if nm in ("cf_clearance", "__cf_bm", "datadome", "_abck"):
                            c["kind"] = "premium"
                            self.store.put_cookie(domain, "", c)
                except Exception:
                    pass
            if text:
                try:
                    got2 = self.harvester.from_html(domain, "", text, status)
                    if got2 and self.policy:
                        self.policy.apply_harvest(domain, "", got2, status)
                except Exception:
                    pass
        self._patched = install_patch(ctx.module, on_response)

    def health(self, ctx):
        return {"status": "ok" if self._ready else "loading", "message": "v%s ready=%s frozen=%s" % (self.version, self._ready, self._frozen)}


def build():
    return Main()
