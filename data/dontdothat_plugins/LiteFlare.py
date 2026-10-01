PLUGIN = {
    "name": "LiteFlare",
    "version": "1.1.0",
    "author": "@flexOwnerAL",
    "description": "Light Cloudflare/captcha/JS bypass strategies with cookie jar, site handlers, parallel warmup and strategy stats.",
    "hooks": ["on_blocked", "on_error", "on_js_required", "after_fetch"],
    "min_core": "5.0.0",
    "tags": ["bypass", "cloudflare", "captcha", "js"],
}

import asyncio
import json
import random
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

try:
    from curl_cffi.requests import AsyncSession as _CurlSession
    _HAS_CURL = True
except Exception:
    _CurlSession = None
    _HAS_CURL = False

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False


DB_PATH = Path("data/dontdothat.db")

CF_MARKERS = (
    "just a moment",
    "checking your browser",
    "cf-browser-verification",
    "cf-challenge",
    "cf_chl_",
    "__cf_chl",
    "attention required",
    "ddos protection",
)

IMPERSONATE_PROFILES = [
    "chrome", "chrome110", "chrome116", "chrome119",
    "chrome120", "chrome124", "chrome131",
    "safari17_0", "safari17_2_ios", "firefox133",
]

SITE_HANDLERS = {
    "duckduckgo.com": lambda q: f"https://lite.duckduckgo.com/lite/?q={quote_plus(q)}",
    "html.duckduckgo.com": lambda q: f"https://lite.duckduckgo.com/lite/?q={quote_plus(q)}",
    "google.com": lambda q: f"https://www.google.com/search?q={quote_plus(q)}&num=20&gbv=1",
    "reddit.com": lambda q: f"https://old.reddit.com/search?q={quote_plus(q)}",
    "www.reddit.com": lambda q: f"https://old.reddit.com/search?q={quote_plus(q)}",
    "twitter.com": lambda q: f"https://nitter.net/search?q={quote_plus(q)}",
    "x.com": lambda q: f"https://nitter.net/search?q={quote_plus(q)}",
    "youtube.com": lambda q: f"https://www.youtube.com/results?search_query={quote_plus(q)}&sp=EgIQAQ%253D%253D",
    "github.com": lambda q: f"https://github.com/search?q={quote_plus(q)}&type=repositories",
}

DEAD_SERVICES = set()


def _db():
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cookies (
                domain TEXT PRIMARY KEY, cookie TEXT, ua TEXT,
                proxy TEXT, created REAL, expires REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_stats (
                domain TEXT, strategy TEXT, ok INTEGER, fail INTEGER,
                last_used REAL, PRIMARY KEY (domain, strategy)
            )
        """)
        conn.commit()
        return conn
    except Exception:
        return None


def _get_cookie(domain):
    conn = _db()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT cookie, ua, proxy, expires FROM cookies WHERE domain=?",
            (domain,),
        ).fetchone()
        if row is None:
            return None
        cookie, ua, proxy, expires = row
        if expires and expires < time.time():
            conn.execute("DELETE FROM cookies WHERE domain=?", (domain,))
            conn.commit()
            return None
        return {"cookie": cookie, "ua": ua, "proxy": proxy}
    except Exception:
        return None


def _save_cookie(domain, cookie, ua, proxy):
    conn = _db()
    if conn is None:
        return
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cookies (domain, cookie, ua, proxy, created, expires) VALUES (?,?,?,?,?,?)",
            (domain, cookie, ua, proxy or "", time.time(), time.time() + 3600 * 6),
        )
        conn.commit()
    except Exception:
        pass


def _record_strategy(domain, strategy, ok):
    conn = _db()
    if conn is None:
        return
    try:
        row = conn.execute(
            "SELECT ok, fail FROM strategy_stats WHERE domain=? AND strategy=?",
            (domain, strategy),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO strategy_stats (domain, strategy, ok, fail, last_used) VALUES (?,?,?,?,?)",
                (domain, strategy, 1 if ok else 0, 0 if ok else 1, time.time()),
            )
        else:
            o, f = row
            if ok:
                o += 1
            else:
                f += 1
            conn.execute(
                "UPDATE strategy_stats SET ok=?, fail=?, last_used=? WHERE domain=? AND strategy=?",
                (o, f, time.time(), domain, strategy),
            )
        conn.commit()
    except Exception:
        pass


def _is_cf(text):
    if not text:
        return False
    low = text.lower()
    return any(m in low for m in CF_MARKERS)


def _domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _site_override(url, query):
    d = _domain(url)
    for key, fn in SITE_HANDLERS.items():
        if key in d:
            try:
                return fn(query)
            except Exception:
                return None
    return None


_LAST_HEADERS = {}

async def _curl_fetch(url, impersonate="chrome", headers=None, cookie=None):
    if not _HAS_CURL:
        return None
    h = headers or {}
    if cookie:
        h = dict(h)
        h["Cookie"] = cookie
    try:
        async with _CurlSession() as session:
            r = await session.get(
                url, headers=h, timeout=20,
                impersonate=impersonate, allow_redirects=True,
            )
            try:
                _hd = {}
                for _k, _v in (r.headers or {}).items():
                    _hd[str(_k)] = str(_v)
                _LAST_HEADERS[url] = (_hd, int(getattr(r, "status_code", 200) or 200))
            except Exception:
                pass
            return (r.text or "")[:900_000]
    except Exception:
        return None


async def _httpx_fetch(url, headers=None, cookie=None):
    if not _HAS_HTTPX:
        return None
    h = headers or {}
    if cookie:
        h = dict(h)
        h["Cookie"] = cookie
    try:
        async with httpx.AsyncClient(
            http2=True, timeout=20,
            follow_redirects=True, headers=h,
        ) as client:
            r = await client.get(url)
            try:
                _hd = {}
                for _k, _v in (r.headers or {}).items():
                    _hd[str(_k)] = str(_v)
                _LAST_HEADERS[url] = (_hd, int(getattr(r, "status_code", 200) or 200))
            except Exception:
                pass
            return (r.text or "")[:900_000]
    except Exception:
        return None


def _urllib_fetch(url, headers=None, cookie=None):
    h = headers or {}
    if cookie:
        h = dict(h)
        h["Cookie"] = cookie
    try:
        req = Request(url, headers=h)
        with urlopen(req, timeout=20) as response:
            raw = response.read(900_000)
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                _hd = {}
                for _k, _v in (response.headers or {}).items():
                    _hd[str(_k)] = str(_v)
                _LAST_HEADERS[url] = (_hd, int(getattr(response, "status", 200) or 200))
            except Exception:
                pass
            try:
                return raw.decode(charset, errors="ignore")
            except LookupError:
                return raw.decode("utf-8", errors="ignore")
    except Exception:
        return None


async def _jina_fetch(url, fmt="markdown"):
    if "jina" in DEAD_SERVICES:
        return None
    h = {"X-Return-Format": "text"} if fmt == "text" else {}
    target = f"https://r.jina.ai/{url}"
    page = await _httpx_fetch(target, headers=h) if _HAS_HTTPX else None
    if page is None:
        page = await asyncio.to_thread(_urllib_fetch, target, h)
    if page and len(page) > 300 and not _is_cf(page):
        return page
    if page is None:
        DEAD_SERVICES.add("jina")
    return None


async def _wayback_fetch(url):
    if "wayback" in DEAD_SERVICES:
        return None
    try:
        api = f"https://archive.org/wayback/available?url={quote_plus(url)}"
        text = await asyncio.to_thread(_urllib_fetch, api)
        if not text:
            return None
        data = json.loads(text)
        snap = data.get("archived_snapshots", {}).get("closest")
        if not snap or not snap.get("available"):
            return None
        page = await asyncio.to_thread(_urllib_fetch, snap.get("url"))
        if page and len(page) > 500 and not _is_cf(page):
            return page
    except Exception:
        pass
    return None


async def _archive_ph_fetch(url):
    if "archive_ph" in DEAD_SERVICES:
        return None
    try:
        target = f"https://archive.ph/newest/{url}"
        page = await asyncio.to_thread(_urllib_fetch, target)
        if page and len(page) > 500 and not _is_cf(page):
            return page
    except Exception:
        pass
    return None


async def _google_cache_fetch(url):
    if "google_cache" in DEAD_SERVICES:
        return None
    try:
        target = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
        page = await asyncio.to_thread(_urllib_fetch, target)
        if page and len(page) > 500 and not _is_cf(page):
            return page
    except Exception:
        pass
    return None


async def _strategy_cookie(url):
    d = _domain(url)
    ck = _get_cookie(d)
    if not ck:
        return None
    page = await _curl_fetch(url, headers={"User-Agent": ck.get("ua") or "Mozilla/5.0"}, cookie=ck.get("cookie"))
    if not page:
        page = await _httpx_fetch(url, headers={"User-Agent": ck.get("ua") or "Mozilla/5.0"}, cookie=ck.get("cookie"))
    if page and len(page) > 500 and not _is_cf(page):
        return page
    return None


async def _strategy_curl_profiles(url):
    if not _HAS_CURL:
        return None
    profiles = random.sample(IMPERSONATE_PROFILES, min(5, len(IMPERSONATE_PROFILES)))
    for p in profiles:
        page = await _curl_fetch(url, impersonate=p)
        if page and len(page) > 500 and not _is_cf(page):
            return page
    return None


async def _strategy_curl_headers(url):
    variants = [
        {"Referer": f"https://{_domain(url)}/"},
        {"User-Agent": "Mozilla/5.0 (Linux; Android 16; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"},
        {"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"},
    ]
    for h in variants:
        page = await _curl_fetch(url, headers=h)
        if page and len(page) > 500 and not _is_cf(page):
            return page
        page = await _httpx_fetch(url, headers=h)
        if page and len(page) > 500 and not _is_cf(page):
            return page
    return None


async def _strategy_httpx_h2(url):
    page = await _httpx_fetch(url)
    if page and len(page) > 500 and not _is_cf(page):
        return page
    return None


async def _strategy_jina(url):
    page = await _jina_fetch(url, "markdown")
    if page:
        return page
    return await _jina_fetch(url, "text")


async def _strategy_wayback(url):
    return await _wayback_fetch(url)


async def _strategy_archive_ph(url):
    return await _archive_ph_fetch(url)


async def _strategy_google_cache(url):
    return await _google_cache_fetch(url)


STRATEGIES = [
    ("cookie", _strategy_cookie),
    ("curl_profiles", _strategy_curl_profiles),
    ("curl_headers", _strategy_curl_headers),
    ("httpx_h2", _strategy_httpx_h2),
    ("jina", _strategy_jina),
    ("wayback", _strategy_wayback),
    ("archive_ph", _strategy_archive_ph),
    ("google_cache", _strategy_google_cache),
]


async def _try_strategy(name, fn, url):
    try:
        page = await fn(url)
        if page and len(page) > 500:
            return page, name
    except Exception:
        pass
    return None, None


async def _run_pipeline(url):
    d = _domain(url)
    for name, fn in STRATEGIES:
        page, used = await _try_strategy(name, fn, url)
        if page:
            _record_strategy(d, used, True)
            return page, used
        _record_strategy(d, name, False)
    return None, None


async def _run_parallel(url, picks):
    tasks = [asyncio.create_task(_try_strategy(n, f, url)) for n, f in picks]
    for coro in asyncio.as_completed(tasks):
        page, used = await coro
        if page:
            for t in tasks:
                t.cancel()
            return page, used
    return None, None


async def _solve(url, reason):
    d = _domain(url)

    if _HAS_CURL:
        ok = random.random() < 0.5
        picks = random.sample(STRATEGIES[:4], k=min(2, len(STRATEGIES[:4])))
        page, used = await _run_parallel(url, picks)
        if page:
            return page

    page, used = await _run_pipeline(url)
    return page


async def solve(url, reason=""):
    return await _solve(url, reason)

def get_last_headers(url):
    return _LAST_HEADERS.get(url, ({}, 200))

def list_last_headers():
    return dict(_LAST_HEADERS)

async def on_blocked(ctx):
    url = ctx.get("url")
    if not url:
        return None
    page = await _solve(url, ctx.get("reason") or "blocked")
    return page


async def on_js_required(ctx):
    url = ctx.get("url")
    if not url:
        return None
    page = await _jina_fetch(url, "markdown")
    if page:
        return page
    page = await _jina_fetch(url, "text")
    if page:
        return page
    return await _wayback_fetch(url)


async def on_error(ctx):
    url = ctx.get("url")
    err = str(ctx.get("error") or "").lower()
    if not url:
        return None
    if "timeout" in err or "timed out" in err:
        page = await _wayback_fetch(url)
        if page:
            return page
    if "refused" in err or "connection" in err:
        page = await _jina_fetch(url, "text")
        if page:
            return page
    return await _strategy_httpx_h2(url)


async def after_fetch(ctx):
    url = ctx.get("url")
    html_text = ctx.get("html") or ""
    if not url or not html_text:
        return None
    if "cf_clearance" in html_text.lower():
        pass
    try:
        m = re.search(r'cf_clearance=([^;\"\']+)', html_text)
        if m:
            _save_cookie(_domain(url), f"cf_clearance={m.group(1)}", "Mozilla/5.0", None)
    except Exception:
        pass
    return None
