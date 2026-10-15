"""Kagami Games (patches.kagamied.com): the publisher's own patch page, built from a static
patches.json. Each patch is listed once per language the page is written in (English, Chinese,
Japanese rows share the same file), with a direct download on kagami.zip and mirrors. No app
ids: titles are matched to Steam app ids like patch.moe's (titles.json)."""

import json
import re

from common import fetch_json, format_of, host_of
from sources.patchmoe import _titles, app_id_for, TITLES

PAGE = "https://patches.kagamied.com/"
DATA = PAGE + "patches.json"
LANGUAGES = {"english": "en", "chinese": "zh-Hans", "japanese": "ja"}
# Games listed only under their Chinese title.
ALIASES = {"极乐妹土！3": "Imouto Paradise 3", "极乐妹土！2": "Imouto Paradise 2",
           "樱花，萌放。-as the Night's, Reincarnation-": "Sakura, Moyu. -as the Night's, Reincarnation-"}


def _title(row):
    title = row["title"].strip()
    if row.get("language") == "english":
        title = re.sub(r"\s*Steam Version Patch Downloads:?\s*$", "", title).strip().strip('"').strip()
        return title
    inner = re.search(r"《(.+?)》", title)
    return ALIASES.get(inner.group(1) if inner else title)


def collect():
    rows = fetch_json(DATA)
    groups = {}
    for row in rows:
        urls = [d["url"].strip() for d in row.get("downloads") or []]
        direct = next((u for u in urls if "kagami.zip/" in u), None)
        key = direct or next((u for u in urls if host_of(u) == "mega"), None) or (urls[0] if urls else None)
        if not key:
            continue
        group = groups.setdefault(key, {"title": None, "languages": set(), "urls": urls, "version": None})
        group["languages"].add(LANGUAGES.get(row.get("language"), "en"))
        title = _title(row)
        if title and (group["title"] is None or row.get("language") == "english"):
            group["title"] = title
        tags = row.get("tags") or []
        if row.get("language") == "english" and tags:
            group["version"] = tags[0]
    titles = _titles()
    for key, group in groups.items():
        if not group["title"]:
            print(f"Kagami: no English title for {key}")
            continue
        app_id = app_id_for(group["title"], titles)
        if not app_id:
            print(f"Kagami: no Steam match for {group['title']!r}")
            continue
        if "kagami.zip/" in key:
            name = key.rsplit("/", 1)[-1]
            file = {"host": "direct", "url": key, "name": name, "format": format_of(name)}
            mirrors = [{"host": "gdrive", "url": u} for u in group["urls"] if host_of(u) == "gdrive"]
            if mirrors:
                file["mirrors"] = mirrors
        else:
            # A MEGA folder or a transfer page: opened in a browser.
            file = {"host": "page", "url": key, "name": None, "format": None}
        version = group["version"]
        if version and not re.match(r"^v?\d", version):
            version = None
        yield {
            "appID": int(app_id),
            "title": group["title"],
            "patch": {
                "name": "Steam patch",
                "kind": "adult",
                "official": True,
                "by": "Kagami Games",
                "source": {"site": "kagami", "page": PAGE, "key": key},
                "version": version,
                "languages": sorted(group["languages"]),
                "adult": True,
                "notes": "Kagami Games' own patch: restores the content cut from the Steam release.",
                "files": [file],
            },
        }
    with open(TITLES, "w") as file:
        json.dump(dict(sorted(titles.items())), file, ensure_ascii=False, indent=2)
        file.write("\n")
