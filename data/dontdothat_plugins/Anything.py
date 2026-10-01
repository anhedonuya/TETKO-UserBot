# fuck off anhedonuya, im the leader
PLUGIN = {
    "name": "Anything",
    "version": "1.0.0",
    "author": "@flexOwnerAL",
    "description": "fixes and enhances DontDoThat output: titles, ddg redirects, snippets, links",
    "min_core": "6.7.0",
    "access": ["module"],
    "tags": ["post", "res", "fix"],
    "hooks": ["after_fetch", "on_result", "on_search"],
}

import html as _html
import re
import time
from urllib.parse import unquote, urlparse

try:
    from readability import Document as _ReadableDoc
    _HAS_READABILITY = True
except Exception:
    _ReadableDoc = None
    _HAS_READABILITY = False

try:
    from trafilatura import extract as _trafilatura_extract
    _HAS_TRAFILATURA = True
except Exception:
    _trafilatura_extract = None
    _HAS_TRAFILATURA = False


_DDG_REDIRECT = re.compile(
    r"^https?://(?:lite\.|html\.|www\.)?duckduckgo\.com/l/\?[^\"']*?uddg=([^&\s\"']+)",
    re.IGNORECASE,
)
_DDG_REDIRECT_INLINE = re.compile(
    r"https?://(?:lite\.|html\.|www\.)?duckduckgo\.com/l/\?[^\"'\s>]*?uddg=([^&\s\"'>]+)",
    re.IGNORECASE,
)
_TITLE_RX = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_HEAD_RX = re.compile(r"(?is)<head[^>]*>.*?</head>")
_H1_RX = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")
_OG_TITLE_RX = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)
_TW_TITLE_RX = re.compile(r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)

_JUNK_MARKERS = (
    "javascript is required", "please enable javascript", "enable javascript to continue",
    "you need to enable javascript", "verify you are human", "are you a robot",
    "checking your browser", "just a moment", "ddos protection by cloudflare",
    "attention required", "cf-browser-verification",
)

_TITLE_JUNK = (
    "untitled page", "untitled", "no title", "document", "index of",
    "access denied", "forbidden", "404 not found", "error",
)

_KNOWN_SITE_SUFFIXES = (
    " — Википедия", " - Wikipedia", " | Wikipedia", " — Wikipedia",
    " - DuckDuckGo", " at DuckDuckGo", " — DuckDuckGo",
    " - Google Search", " - Bing",
)


def _unwrap_ddg(url: str) -> str:
    if not url:
        return url
    m = _DDG_REDIRECT.match(url)
    if not m:
        m = _DDG_REDIRECT_INLINE.search(url)
    if not m:
        return url
    try:
        return unquote(m.group(1))
    except Exception:
        return url


def _unwrap_ddg_in_html(html: str) -> str:
    if not html or "uddg=" not in html:
        return html
    try:
        return _DDG_REDIRECT_INLINE.sub(lambda m: unquote(m.group(1)), html)
    except Exception:
        return html


def _clean_title(raw: str) -> str:
    if not raw:
        return ""
    t = _html.unescape(raw)
    t = re.sub(r"\s+", " ", t).strip()
    for suffix in _KNOWN_SITE_SUFFIXES:
        if t.lower().endswith(suffix.lower()):
            t = t[: -len(suffix)].strip()
    if t.lower() in _TITLE_JUNK:
        return ""
    return t


def _extract_title(html: str) -> str:
    if not html:
        return ""
    for rx in (_OG_TITLE_RX, _TW_TITLE_RX):
        try:
            m = rx.search(html)
            if m:
                t = _clean_title(m.group(1))
                if t:
                    return t
        except Exception:
            continue
    try:
        m = _TITLE_RX.search(html)
        if m:
            t = _clean_title(re.sub(r"<[^>]+>", " ", m.group(1)))
            if t:
                return t
    except Exception:
        pass
    try:
        m = _H1_RX.search(html)
        if m:
            t = _clean_title(re.sub(r"<[^>]+>", " ", m.group(1)))
            if t:
                return t
    except Exception:
        pass
    return ""


def _extract_title_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        path = p.path.strip("/")
        if not path:
            return p.netloc
        last = path.split("/")[-1]
        last = re.sub(r"\.(?:html?|php|aspx?|jsp)$", "", last, flags=re.IGNORECASE)
        last = unquote(last)
        last = last.replace("_", " ").replace("-", " ").strip()
        last = re.sub(r"\s+", " ", last)
        if len(last) < 3:
            return p.netloc
        return last
    except Exception:
        return ""


def _is_junk_title(title: str) -> bool:
    if not title:
        return True
    low = title.lower().strip()
    if low in _TITLE_JUNK:
        return True
    for marker in _JUNK_MARKERS:
        if marker in low:
            return True
    if len(title) < 3:
        return True
    return False


def _looks_like_junk(text: str) -> bool:
    if not text:
        return True
    low = text.lower()
    for marker in _JUNK_MARKERS:
        if marker in low:
            return True
    return False


def _readable_html(html: str) -> str:
    out = None
    if _HAS_TRAFILATURA:
        try:
            out = _trafilatura_extract(
                html,
                output_format="html",
                include_links=True,
                include_images=False,
                include_tables=True,
            )
        except Exception:
            out = None
    if not out and _HAS_READABILITY:
        try:
            out = _ReadableDoc(html).summary()
        except Exception:
            out = None
    return out or ""


def _preserve_head(original: str, cleaned: str) -> str:
    if not cleaned:
        return original
    if not original:
        return cleaned
    try:
        m = _HEAD_RX.search(original)
        if not m:
            return cleaned
        head = m.group(0)
        if "<title" not in head.lower() and "og:title" not in head.lower():
            return cleaned
        return head + cleaned
    except Exception:
        return cleaned


def _strip_junk_lines(snippet: str) -> str:
    if not snippet:
        return snippet
    lines = snippet.split("\n")
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(marker in low for marker in _JUNK_MARKERS):
            continue
        out.append(s)
    return "\n".join(out) if out else snippet


def _shorten_snippet(snippet: str, max_len: int = 900) -> str:
    if not snippet:
        return snippet
    s = re.sub(r"\s+", " ", snippet).strip()
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    last_dot = cut.rfind(". ")
    if last_dot > max_len * 0.5:
        return cut[: last_dot + 1]
    return cut.rstrip() + "..."


async def after_fetch(ctx):
    html = ctx.get("html")
    if not html:
        return None
    original = html
    html = _unwrap_ddg_in_html(html)
    title = _extract_title(html)
    ctx["_anything_title"] = title
    cleaned = _readable_html(html)
    if cleaned:
        cleaned = _preserve_head(html, cleaned)
        return cleaned
    return html


async def on_result(ctx):
    result = ctx.get("result")
    if not isinstance(result, dict):
        return None
    url = result.get("url") or ""
    title = result.get("title") or ""
    snippet = result.get("snippet") or ""
    if _is_junk_title(title):
        new_title = ""
        try:
            new_title = _extract_title(ctx.get("html") or "")
        except Exception:
            new_title = ""
        if not new_title:
            new_title = _extract_title_from_url(url)
        if new_title:
            result["title"] = new_title
    links = result.get("links") or []
    if links:
        unwrapped = [_unwrap_ddg(l) for l in links if l]
        result["links"] = list(dict.fromkeys(unwrapped))
    files = result.get("files") or []
    if files:
        result["files"] = list(dict.fromkeys([_unwrap_ddg(f) for f in files if f]))
    images = result.get("images") or []
    if images:
        result["images"] = [_unwrap_ddg(i) for i in images if i]
    if snippet:
        snippet = _strip_junk_lines(snippet)
        snippet = _shorten_snippet(snippet, 900)
        result["snippet"] = snippet
        result["snippet_esc"] = _html.escape(snippet)
        query = ctx.get("query") or ""
        if query:
            try:
                words = [w for w in re.findall(r"\w+", query, re.UNICODE) if len(w) > 1]
                if words:
                    pattern = r"(?<![\w])(?:" + "|".join(re.escape(_html.escape(w)) for w in sorted(set(words), key=len, reverse=True)) + r")(?![\w])"
                    result["snippet_hl"] = re.sub(pattern, lambda m: f"<b>{m.group(0)}</b>", result["snippet_esc"], flags=re.IGNORECASE | re.UNICODE)
            except Exception:
                pass
    if _looks_like_junk(snippet):
        result["_junk"] = True
    return None


async def on_search(ctx):
    query = ctx.get("query") or ""
    if not query:
        return None
    cleaned = re.sub(r"\s+", " ", query).strip()
    if cleaned != query:
        ctx["query"] = cleaned
    return None