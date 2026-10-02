import asyncio
import json
import time
import logging
from collections import defaultdict, deque, Counter

from core.tetko import Module, command, db_get, db_set, db_del, shell

log = logging.getLogger("TETKO.module.TAPI")

MODES = {
    "safe":       {"per_minute": 5,  "delay": 3.0, "burst": 3,  "max_retries": 5, "peerflood_suspend_seconds": 3600},
    "normal":     {"per_minute": 20, "delay": 1.0, "burst": 8,  "max_retries": 3, "peerflood_suspend_seconds": 1800},
    "aggressive": {"per_minute": 60, "delay": 0.0, "burst": 30, "max_retries": 1, "peerflood_suspend_seconds": 600},
    "paranoid":   {"per_minute": 2,  "delay": 10.0, "burst": 1, "max_retries": 10, "peerflood_suspend_seconds": 7200},
}

WRAPPED_METHODS = [
    "send_message",
    "send_file",
    "edit_message",
    "delete_messages",
    "forward_messages",
    "send_read_acknowledge",
    "send_reaction",
    "pin_message",
]

PERSIST_INTERVAL = 30
NOTIFY_FLUSH_INTERVAL = 10


class TAPI(Module):
    name = "TAPI"
    __compat__ = "0.0.9.0"
    version = "1.1.0"
    author = "@flexownerAL"
    description = "Защита юзербота от лимитов Telegram: throttle, retry, suspend"

    config = {
        "enabled": True,
        "mode": "normal",
        "per_minute": 20,
        "delay": 1.0,
        "burst": 8,
        "jitter": 0.0,
        "floodwait_retry": True,
        "max_retries": 3,
        "floodwait_multiplier": 1.0,
        "floodwait_max_sleep": 300,
        "auto_suspend_on_peerflood": True,
        "peerflood_suspend_seconds": 1800,
        "auto_resume_after_suspend": True,
        "log_floodwaits": True,
        "notify_owner_on_flood": True,
        "notify_owner_on_suspend": True,
        "notify_batch_seconds": 15,
        "notify_min_severity": 1,
        "quiet_hours_enabled": False,
        "quiet_hours_from": 23,
        "quiet_hours_to": 8,
        "adaptive_mode": False,
        "adaptive_decay": 0.7,
        "adaptive_min_per_minute": 3,
        "adaptive_recover": True,
        "adaptive_recover_step": 1,
        "adaptive_recover_interval": 600,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_action": "safe",
        "circuit_breaker_window": 300,
        "proactive_throttle": False,
        "proactive_throttle_factor": 2.0,
        "proactive_throttle_window": 120,
        "warmup_mode": False,
        "warmup_duration": 300,
        "warmup_start_per_minute": 3,
        "per_method_limits": {},
        "per_chat_limits": {},
        "whitelist_methods": [],
        "blacklist_methods": [],
        "whitelist_chats": [],
        "blacklist_chats": [],
        "max_tracked_chats": 100,
        "keep_events": 200,
        "daily_reset": False,
        "daily_reset_hour": 4,
        "stats_persist_interval": 30,
    }

    config_schema = {
        "enabled": {"type": "bool", "description": "Включить защиту"},
        "mode": {"type": "str", "description": "Профиль по умолчанию",
                 "options": ["safe", "normal", "aggressive", "paranoid"]},
        "per_minute": {"type": "int", "description": "Максимум запросов в минуту"},
        "delay": {"type": "float", "description": "Пауза между запросами (сек)"},
        "burst": {"type": "int", "description": "Burst перед throttle"},
        "jitter": {"type": "float", "description": "Случайный разброс к delay (0.0-2.0)"},
        "floodwait_retry": {"type": "bool", "description": "Авто-повтор при FloodWait"},
        "max_retries": {"type": "int", "description": "Максимум повторных попыток"},
        "floodwait_multiplier": {"type": "float", "description": "Множитель паузы FloodWait (>1 = осторожнее)"},
        "floodwait_max_sleep": {"type": "int", "description": "Максимум секунд ожидания FloodWait"},
        "auto_suspend_on_peerflood": {"type": "bool", "description": "Авто-стоп при PeerFlood"},
        "peerflood_suspend_seconds": {"type": "int", "description": "Пауза при PeerFlood"},
        "auto_resume_after_suspend": {"type": "bool", "description": "Авто-возобновление после suspend"},
        "log_floodwaits": {"type": "bool", "description": "Логировать FloodWait"},
        "notify_owner_on_flood": {"type": "bool", "description": "Уведомлять владельца при FloodWait"},
        "notify_owner_on_suspend": {"type": "bool", "description": "Уведомлять владельца при suspend"},
        "notify_batch_seconds": {"type": "int", "description": "Группировка уведомлений (сек)"},
        "notify_min_severity": {"type": "int", "description": "Мин. длительность FloodWait для уведомления (сек)"},
        "quiet_hours_enabled": {"type": "bool", "description": "Тихие часы (не уведомлять)"},
        "quiet_hours_from": {"type": "int", "description": "Час начала тишины (0-23)"},
        "quiet_hours_to": {"type": "int", "description": "Час конца тишины (0-23)"},
        "adaptive_mode": {"type": "bool", "description": "Снижать скорость при частых FloodWait"},
        "adaptive_decay": {"type": "float", "description": "Коэффициент снижения (0.5-0.9)"},
        "adaptive_min_per_minute": {"type": "int", "description": "Нижний порог per_minute"},
        "adaptive_recover": {"type": "bool", "description": "Авто-восстановление скорости"},
        "adaptive_recover_step": {"type": "int", "description": "Шаг восстановления (+N к per_minute)"},
        "adaptive_recover_interval": {"type": "int", "description": "Интервал восстановления (сек)"},
        "circuit_breaker_threshold": {"type": "int", "description": "FloodWait подряд → action"},
        "circuit_breaker_action": {"type": "str", "description": "Что делать при срабатывании",
                                    "options": ["safe", "paranoid", "suspend", "nothing"]},
        "circuit_breaker_window": {"type": "int", "description": "Окно подсчёта (сек)"},
        "proactive_throttle": {"type": "bool", "description": "Превентивное замедление после свежих FloodWait"},
        "proactive_throttle_factor": {"type": "float", "description": "Во сколько раз медленнее"},
        "proactive_throttle_window": {"type": "int", "description": "Окно превентивного замедления (сек)"},
        "warmup_mode": {"type": "bool", "description": "Плавный разгон после старта"},
        "warmup_duration": {"type": "int", "description": "Длительность warmup (сек)"},
        "warmup_start_per_minute": {"type": "int", "description": "С какой скорости начать"},
        "per_method_limits": {"type": "dict", "description": "Лимиты по методам: {\"send_message\": 10}"},
        "per_chat_limits": {"type": "dict", "description": "Лимиты по чатам: {\"1234567\": 5}"},
        "whitelist_methods": {"type": "list", "description": "Только эти методы перехватывать"},
        "blacklist_methods": {"type": "list", "description": "Эти методы НЕ перехватывать"},
        "whitelist_chats": {"type": "list", "description": "Чаты без ограничений"},
        "blacklist_chats": {"type": "list", "description": "Чаты с блокировкой"},
        "max_tracked_chats": {"type": "int", "description": "Сколько чатов держать в статистике"},
        "keep_events": {"type": "int", "description": "Сколько событий хранить в памяти"},
        "daily_reset": {"type": "bool", "description": "Сбрасывать статистику раз в сутки"},
        "daily_reset_hour": {"type": "int", "description": "Час сброса (0-23)"},
        "stats_persist_interval": {"type": "int", "description": "Как часто сохранять состояние (сек)"},
    }

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self._orig = {}
        self._patched = False
        self._suspended_until = 0.0
        self._recent = defaultdict(lambda: deque(maxlen=500))
        self._recent_all = deque(maxlen=500)
        self._flood_events = deque(maxlen=500)
        self._method_floods = Counter()
        self._chat_floods = Counter()
        self._lock = asyncio.Lock()
        self._stats = {
            "total_calls": 0,
            "floodwaits": 0,
            "peerfloods": 0,
            "spamblocks": 0,
            "suspends": 0,
            "retries": 0,
            "blocked": 0,
            "circuit_breaks": 0,
        }
        self._started_at = time.time()
        self._last_persist = 0.0
        self._notify_buffer = []
        self._notify_task = None
        self._persist_task = None

    async def on_load(self):
        self.log.info("TAPI loaded, mode=%s", self.cfg.get("mode", "normal"))
        self._load_state()
        self._apply_mode_if_needed()
        self._install_wrappers()
        self._persist_task = asyncio.create_task(self._persist_loop())

    async def on_unload(self):
        self._remove_wrappers()
        for t in (self._persist_task, self._notify_task):
            if t:
                t.cancel()
        self._save_state()

    def _load_state(self):
        try:
            raw = db_get("tapi", "state", None)
            if raw:
                data = json.loads(raw) if isinstance(raw, str) else raw
                self._suspended_until = float(data.get("suspended_until", 0))
                for k in self._stats:
                    self._stats[k] = int(data.get("stats", {}).get(k, self._stats[k]))
        except Exception as e:
            self.log.warning("load_state: %s", e)

    def _save_state(self):
        try:
            db_set("tapi", "state", json.dumps({
                "suspended_until": self._suspended_until,
                "stats": self._stats,
                "saved_at": time.time(),
            }))
        except Exception as e:
            self.log.warning("save_state: %s", e)

    async def _persist_loop(self):
        while True:
            try:
                await asyncio.sleep(PERSIST_INTERVAL)
                self._save_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.warning("persist loop: %s", e)

    def _apply_mode_if_needed(self):
        mode = self.cfg.get("mode", "normal")
        if mode not in MODES:
            return
        m = MODES[mode]
        cur_pm = self.cfg.get("per_minute", 20)
        if cur_pm not in (v["per_minute"] for v in MODES.values()):
            return
        for k, v in m.items():
            self.cfg.set(k, v)

    def _install_wrappers(self):
        if self._patched:
            return
        client = getattr(self.kernel, "client", None)
        if client is None:
            self.log.warning("no client")
            return
        for name in WRAPPED_METHODS:
            orig = getattr(client, name, None)
            if orig is None or not callable(orig):
                continue
            if hasattr(orig, "__wrapped__"):
                continue
            self._orig[name] = orig
            setattr(client, name, self._make_wrapper(name, orig))
        self._patched = True
        self.log.info("wrappers: %s", list(self._orig.keys()))

    def _remove_wrappers(self):
        if not self._patched:
            return
        client = getattr(self.kernel, "client", None)
        if client is None:
            return
        for name, orig in self._orig.items():
            try:
                setattr(client, name, orig)
            except Exception:
                pass
        self._orig.clear()
        self._patched = False

    def _make_wrapper(self, name, orig):
        async def wrapper(*args, **kwargs):
            return await self._call(name, orig, *args, **kwargs)
        wrapper.__name__ = name
        wrapper.__wrapped__ = orig
        return wrapper

    async def _call(self, name, orig, *args, **kwargs):
        if not self.cfg.get("enabled", True):
            return await orig(*args, **kwargs)

        if self._suspended_until > time.time():
            self._stats["blocked"] += 1
            remaining = int(self._suspended_until - time.time())
            raise RuntimeError("TAPI suspended for %ds" % remaining)

        wl = self.cfg.get("whitelist_methods") or []
        bl = self.cfg.get("blacklist_methods") or []
        if name in bl:
            self._stats["blocked"] += 1
            raise RuntimeError("TAPI blacklisted: %s" % name)
        if wl and name not in wl:
            return await orig(*args, **kwargs)

        per_method = self.cfg.get("per_method_limits") or {}
        limit_override = per_method.get(name)

        await self._throttle(name, limit_override)

        self._stats["total_calls"] += 1
        retries = int(self.cfg.get("max_retries", 3))
        do_retry = bool(self.cfg.get("floodwait_retry", True))

        attempt = 0
        while True:
            try:
                return await orig(*args, **kwargs)
            except Exception as e:
                ename = type(e).__name__

                if ename == "FloodWaitError":
                    self._stats["floodwaits"] += 1
                    seconds = int(getattr(e, "seconds", 30)) + 1
                    self._flood_events.append((time.time(), name, "floodwait", seconds))
                    self._method_floods[name] += 1
                    self._track_chat(args, kwargs)
                    if self.cfg.get("log_floodwaits", True):
                        self.log.warning("FloodWait %ds on %s", seconds, name)
                    if self.cfg.get("notify_owner_on_flood", True):
                        self._queue_notify("⚠️ FloodWait %ds on <code>%s</code>" % (seconds, name))
                    self._maybe_circuit_break()
                    if self.cfg.get("adaptive_mode", False):
                        asyncio.create_task(self._adapt())
                    if not do_retry or attempt >= retries:
                        raise
                    attempt += 1
                    self._stats["retries"] += 1
                    await asyncio.sleep(seconds)
                    continue

                if ename == "PeerFloodError":
                    self._stats["peerfloods"] += 1
                    self._flood_events.append((time.time(), name, "peerflood", 0))
                    self._method_floods[name] += 1
                    self._track_chat(args, kwargs)
                    self.log.error("PeerFlood on %s", name)
                    if self.cfg.get("auto_suspend_on_peerflood", True):
                        sec = int(self.cfg.get("peerflood_suspend_seconds", 1800))
                        await self._suspend(sec, reason="PeerFlood")
                    raise

                if ename in ("SpamBlockedError", "UserBannedInChannelError", "ChatWriteForbiddenError"):
                    self._stats["spamblocks"] += 1
                    self._flood_events.append((time.time(), name, "spamblock", 0))
                    self._method_floods[name] += 1
                    self.log.error("SpamBlock on %s", name)
                    await self._suspend(86400, reason="SpamBlock")
                    raise

                raise

    def _track_chat(self, args, kwargs):
        try:
            entity = kwargs.get("entity") or kwargs.get("peer") or (args[0] if args else None)
            if entity is None:
                return
            eid = getattr(entity, "id", None) or getattr(entity, "user_id", None)
            if eid is not None:
                self._chat_floods[int(eid)] += 1
        except Exception:
            pass

    def _maybe_circuit_break(self):
        thr = int(self.cfg.get("circuit_breaker_threshold", 5))
        if thr <= 0:
            return
        window = int(self.cfg.get("circuit_breaker_window", 300))
        cutoff = time.time() - window
        recent = [e for e in self._flood_events if e[0] > cutoff and e[2] == "floodwait"]
        if len(recent) < thr:
            return
        action = str(self.cfg.get("circuit_breaker_action", "safe")).lower()
        self._stats["circuit_breaks"] += 1
        self.log.error("circuit breaker: %d floodwaits in %ds → %s", len(recent), window, action)

        if action == "safe":
            self.cfg.set("mode", "safe")
            for k, v in MODES["safe"].items():
                self.cfg.set(k, v)
            self._queue_notify("🔌 Circuit breaker → safe mode (%d FloodWait за %ds)" % (len(recent), window))
        elif action == "paranoid":
            self.cfg.set("mode", "paranoid")
            for k, v in MODES["paranoid"].items():
                self.cfg.set(k, v)
            self._queue_notify("🔌 Circuit breaker → paranoid mode")
        elif action == "suspend":
            sec = int(self.cfg.get("peerflood_suspend_seconds", 1800))
            self._queue_notify("🔌 Circuit breaker → suspend %ds" % sec)
            asyncio.create_task(self._suspend(sec, reason="CircuitBreaker"))
        self._flood_events.clear()

    async def _throttle(self, method, limit_override=None):
        async with self._lock:
            per_min = int(limit_override or self.cfg.get("per_minute", 20))
            per_min = max(1, per_min)
            delay = float(self.cfg.get("delay", 1.0))
            burst = max(1, int(self.cfg.get("burst", 8)))

            now = time.time()
            q = self._recent[method]
            cutoff = now - 60
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= per_min:
                oldest = q[0]
                wait = 60 - (now - oldest) + 0.05
                if wait > 0:
                    await asyncio.sleep(wait)

            if delay > 0 and len(q) >= burst:
                await asyncio.sleep(delay)

            ts = time.time()
            q.append(ts)
            self._recent_all.append((ts, method))

    async def _suspend(self, seconds, reason=""):
        self._suspended_until = time.time() + seconds
        self._stats["suspends"] += 1
        self.log.error("suspended %ds (%s)", seconds, reason)
        self._save_state()
        if self.cfg.get("notify_owner_on_suspend", True):
            await self._notify_now("🛑 TAPI suspend %ds — %s" % (seconds, reason))

    def _queue_notify(self, text):
        self._notify_buffer.append((time.time(), text))
        if self._notify_task is None or self._notify_task.done():
            self._notify_task = asyncio.create_task(self._flush_notifies())

    async def _flush_notifies(self):
        try:
            batch_sec = int(self.cfg.get("notify_batch_seconds", 15))
            await asyncio.sleep(batch_sec)
            buf = list(self._notify_buffer)
            self._notify_buffer.clear()
            if not buf:
                return
            if len(buf) == 1:
                await self._notify_now(buf[0][1])
                return
            counts = Counter(t for _, t in buf)
            lines = ["📊 TAPI batch (%d events за %ds):" % (len(buf), batch_sec), ""]
            for t, n in counts.most_common(10):
                lines.append("×%d  %s" % (n, t))
            await self._notify_now("\n".join(lines))
        except Exception as e:
            self.log.warning("flush_notifies: %s", e)

    async def _notify_now(self, text):
        try:
            admin = getattr(self.kernel.context, "admin_id", None)
            if admin is None:
                return
            orig = self._orig.get("send_message")
            if orig:
                await orig(admin, text, parse_mode="html")
        except Exception as e:
            self.log.warning("notify failed: %s", e)

    async def _adapt(self):
        window = 300
        cutoff = time.time() - window
        events = [e for e in self._flood_events if e[0] > cutoff and e[2] == "floodwait"]
        if len(events) < 3:
            return
        cur = int(self.cfg.get("per_minute", 20))
        decay = float(self.cfg.get("adaptive_decay", 0.7))
        floor = int(self.cfg.get("adaptive_min_per_minute", 3))
        new = max(floor, int(cur * decay))
        if new < cur:
            self.cfg.set("per_minute", new)
            self.log.warning("adaptive: per_minute %d -> %d", cur, new)
            self._queue_notify("📉 Adaptive: per_minute %d → %d" % (cur, new))

    def _status_text(self):
        now = time.time()
        suspended = int(self._suspended_until - now) if self._suspended_until > now else 0
        uptime = int(now - self._started_at)
        uh, ur = divmod(uptime, 3600)
        um, us = divmod(ur, 60)

        s = self._stats

        cmds = [
            "suspended  : " + (str(suspended) + "s" if suspended > 0 else "no"),
            "uptime     : %dh %dm %ds" % (uh, um, us),
            "wrapped    : " + str(len(self._orig)) + " methods",
            "",
            "calls      : " + str(s["total_calls"]),
            "floodwaits : " + str(s["floodwaits"]),
            "peerfloods : " + str(s["peerfloods"]),
            "spamblocks : " + str(s["spamblocks"]),
            "retries    : " + str(s["retries"]),
            "suspends   : " + str(s["suspends"]),
            "cb_breaks  : " + str(s["circuit_breaks"]),
            "blocked    : " + str(s["blocked"]),
        ]

        if self._method_floods:
            cmds.append("")
            cmds.append("top methods by FloodWait:")
            for m, n in self._method_floods.most_common(5):
                cmds.append("  " + str(m) + "  ×" + str(n))

        if self._chat_floods:
            cmds.append("")
            cmds.append("top chats:")
            for cid, n in self._chat_floods.most_common(5):
                cmds.append("  chat " + str(cid) + "  ×" + str(n))

        recent = list(self._flood_events)[-5:]
        if recent:
            cmds.append("")
            cmds.append("last events:")
            for ts, name, kind, sec in recent:
                when = time.strftime("%H:%M:%S", time.localtime(ts))
                extra = ("%ds" % sec) if sec else ""
                cmds.append("  " + when + "  " + kind + "  " + name + " " + extra)

        return shell.wrap(cmds, cmd="tapi", trailing=True)


    @command(name="tapi", description="API protection status")
    async def cmd_tapi(self, event, args):
        await event.edit(self._status_text(), parse_mode="html")

    @command(name="tapi_reset", description="Reset TAPI stats", only_for="owner")
    async def cmd_tapi_reset(self, event, args):
        for k in self._stats:
            self._stats[k] = 0
        self._flood_events.clear()
        self._method_floods.clear()
        self._chat_floods.clear()
        self._recent.clear()
        self._recent_all.clear()
        self._save_state()
        await event.edit(shell.wrap(["stats cleared"], cmd="tapi_reset", trailing=True), parse_mode="html")

    @command(name="tapi_suspend", description="Suspend TAPI", only_for="owner")
    async def cmd_tapi_suspend(self, event, args):
        sec = int(args[0]) if args and args[0].isdigit() else 300
        await self._suspend(sec, reason="manual")
        await event.edit("suspended %ds" % sec, parse_mode="html")

    @command(name="tapi_resume", description="Resume TAPI", only_for="owner")
    async def cmd_tapi_resume(self, event, args):
        self._suspended_until = 0
        self._save_state()
        await event.edit("resumed", parse_mode="html")

    @command(name="tapi_wrap", description="Wrap method", only_for="owner")
    async def cmd_tapi_wrap(self, event, args):
        if not args:
            await event.edit("usage: tapi_wrap <method>", parse_mode="html")
            return
        m = args[0]
        client = getattr(self.kernel, "client", None)
        if client is None:
            await event.edit("no client", parse_mode="html")
            return
        cur = getattr(client, m, None)
        if cur is None:
            await event.edit("method not found: " + m, parse_mode="html")
            return
        if hasattr(cur, "__wrapped__"):
            await event.edit("already wrapped: " + m, parse_mode="html")
            return
        self._orig[m] = cur
        setattr(client, m, self._make_wrapper(m, cur))
        await event.edit("wrapped: " + m, parse_mode="html")

    @command(name="tapi_unwrap", description="Unwrap method", only_for="owner")
    async def cmd_tapi_unwrap(self, event, args):
        if not args:
            await event.edit("usage: tapi_unwrap <method>", parse_mode="html")
            return
        m = args[0]
        orig = self._orig.pop(m, None)
        if orig is None:
            await event.edit("not wrapped: " + m, parse_mode="html")
            return
        client = getattr(self.kernel, "client", None)
        if client is not None:
            try:
                setattr(client, m, orig)
            except Exception:
                pass
        await event.edit("unwrapped: " + m, parse_mode="html")
