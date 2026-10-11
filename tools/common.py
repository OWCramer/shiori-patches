"""Shared helpers for the patch list's tools (standard library only, plus `cryptography` for MEGA)."""

import datetime
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request

USER_AGENT = "shiori-patches/1.0 (+https://github.com/OWCramer/shiori-patches)"
BROWSER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

_cookies = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookies))
_last_request = {}


def today():
    return datetime.date.today().isoformat()


def fetch(url, data=None, headers=None, browser=False, delay=1.0, timeout=60):
    """GETs (or POSTs `data`) a URL and returns the body as bytes, waiting `delay` seconds
    between requests to the same host."""
    host = urllib.parse.urlsplit(url).netloc
    wait = _last_request.get(host, 0) + delay - time.time()
    if wait > 0:
        time.sleep(wait)
    request_headers = {"User-Agent": BROWSER_AGENT if browser else USER_AGENT}
    request_headers.update(headers or {})
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with _opener.open(request, timeout=timeout) as response:
            return response.read()
    finally:
        _last_request[host] = time.time()


def fetch_text(url, **kwargs):
    return fetch(url, **kwargs).decode("utf-8", errors="replace")


def fetch_json(url, body=None, **kwargs):
    if body is not None:
        kwargs["data"] = json.dumps(body).encode()
        kwargs.setdefault("headers", {})["Content-Type"] = "application/json"
    return json.loads(fetch(url, **kwargs))


def slug(text):
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:60].strip("-") or "patch"


def steam_app_id(url):
    match = re.search(r"store\.steampowered\.com/app/(\d+)", url or "")
    return int(match.group(1)) if match else None


def host_of(url):
    """Which of Shiori's download paths a link takes."""
    netloc = urllib.parse.urlsplit(url).netloc.lower()
    if netloc.endswith("mega.nz") or netloc.endswith("mega.co.nz"):
        return "mega"
    if netloc in ("drive.google.com", "drive.usercontent.google.com", "docs.google.com"):
        return "gdrive"
    if netloc == "we.tl" or netloc.endswith("wetransfer.com"):
        return "wetransfer"
    if netloc.endswith("store.steampowered.com"):
        return "steam"
    if any(netloc.endswith(d) for d in STORE_DOMAINS):
        return "store"
    if any(netloc.endswith(d) for d in PAGE_DOMAINS):
        return "page"
    path = urllib.parse.urlsplit(url).path.lower()
    if re.search(r"\.(zip|7z|rar|exe|rpa|xp3|pfs|arc)$", path) or "/download" in path:
        return "direct"
    return "page"


# Shops: the patch is bought there, then imported.
STORE_DOMAINS = ("denpasoft.com", "dlsite.com", "jastusa.com", "mangagamer.com", "fakku.com",
                 "nutaku.net", "johren.games", "kaguragames.com", "gog.com")
# Links that need a browser (sign-ins, expiring transfers, posts).
PAGE_DOMAINS = ("patreon.com", "itch.io", "mediafire.com",
                "pixeldrain.com", "dropbox.com", "onedrive.live.com", "1drv.ms", "anonfiles.com")


def format_of(name):
    name = (name or "").lower()
    for ext in ("zip", "7z", "rar", "exe"):
        if name.endswith("." + ext) or name.endswith("." + ext + "." + ext):
            return ext
    return "file" if name else None


LANGUAGE_WORDS = {
    "cn": "zh-Hans", "chs": "zh-Hans", "chinese": "zh-Hans", "cht": "zh-Hant",
    "kr": "ko", "korean": "ko", "japanese": "ja", "spanish": "es", "german": "de",
    "french": "fr", "russian": "ru", "portuguese": "pt-BR",
}


def languages_in(text, default=("en",)):
    words = re.findall(r"[a-z]+", (text or "").lower())
    found = [LANGUAGE_WORDS[w] for w in words if w in LANGUAGE_WORDS]
    return sorted(set(found)) or list(default)
