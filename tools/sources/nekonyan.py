"""NekoNyan (patches.nekonyansoft.com): the page's Remix data lists each patch with its
Steam store link and a direct CDN download."""

import json
import re

from common import fetch_text, format_of, languages_in, steam_app_id

PAGE = "https://patches.nekonyansoft.com/"


def _entries(value):
    """Every object in the page data with a download link."""
    if isinstance(value, dict):
        if isinstance(value.get("download"), str) and value["download"].startswith("http"):
            yield value
        for child in value.values():
            yield from _entries(child)
    elif isinstance(value, list):
        for child in value:
            yield from _entries(child)


def _kind(name):
    lower = name.lower()
    if "voice" in lower:
        return "voice"
    if "18+" in lower or "r18" in lower or "uncensor" in lower:
        return "adult"
    if "update" in lower:
        return "update"
    return "other"


def collect():
    html = fetch_text(PAGE, browser=True)
    match = re.search(r"window\.__remixContext\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not match:
        raise RuntimeError("NekoNyan: page data not found")
    data = json.loads(match.group(1))
    seen = set()
    for entry in _entries(data):
        app_id = steam_app_id(entry.get("steam"))
        url = entry["download"]
        if not app_id or url in seen:
            continue
        seen.add(url)
        name = entry.get("name") or url.rsplit("/", 1)[-1]
        file_name = url.rsplit("/", 1)[-1]
        yield {
            "appID": app_id,
            "patch": {
                "name": name,
                "kind": _kind(name),
                "official": True,
                "by": "NekoNyan",
                "source": {"site": "nekonyan", "page": PAGE, "key": url},
                "version": None,
                "languages": languages_in(name + " " + file_name),
                "adult": _kind(name) == "adult",
                "files": [{"host": "direct", "url": url, "name": file_name, "format": format_of(file_name)}],
            },
        }
