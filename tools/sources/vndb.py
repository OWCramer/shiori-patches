"""VNDB (api.vndb.org/kana): patches for games on Steam. Fan-made ones (translations,
restorations) always; official ones only for a game no other source lists an official patch
for, since the publishers' own lists carry the files. VNDB lists the release and its website
but not a download, so these entries point to the patch's page until someone adds the file
by hand."""

import json
import os
import re

from common import fetch_json, file_links, host_of

API = "https://api.vndb.org/kana/release"
ADULT_WORDS = re.compile(r"uncensor|mosaic|18\+|\br-?18\b|\badult\b|\bh-?scenes?\b|\bnsfw\b", re.I)
GONE_WORDS = re.compile(r"no longer available|taken down|dead link", re.I)


ADULT_DLC = re.compile(r"18\+|\badult\b|uncensor|\buncut\b|\br-?18\b|restoration|de-?censor|\bh-?scenes?\b", re.I)
DLC_BASES = os.path.join(os.path.dirname(__file__), "..", "..", "steam-dlc.json")


def _base_game(dlc, bases):
    """The Steam game a DLC belongs to (Steam's appdetails `fullgame`), kept in steam-dlc.json."""
    key = str(dlc)
    if key not in bases:
        try:
            data = fetch_json(f"https://store.steampowered.com/api/appdetails?appids={dlc}&filters=basic,fullgame", delay=1.5)
            app = data.get(key) or {}
            full = (app.get("data") or {}).get("fullgame") or {}
            bases[key] = int(full["appid"]) if app.get("success") and app["data"].get("type") == "dlc" and full.get("appid") else None
        except Exception as error:
            print(f"Steam DLC {dlc}: {error}")
            return None
    return bases[key]


def collect_official_dlc():
    """Publishers' 18+ patches sold or given away as Steam DLC, as VNDB lists them (official
    English patch releases for Windows with a Steam link). Story and extra DLC are left to the
    game page's own Steam DLC list."""
    try:
        bases = json.load(open(DLC_BASES))
    except FileNotFoundError:
        bases = {}
    page, more = 1, True
    try:
        while more:
            body = {"filters": ["and", ["patch", "=", 1], ["official", "=", 1], ["lang", "=", "en"],
                                ["platform", "=", "win"], ["extlink", "=", "steam"]],
                    "fields": "id,title,producers.name,extlinks.name,extlinks.id,languages.lang",
                    "results": 100, "page": page, "sort": "id"}
            data = fetch_json(API, body=body, delay=2.5)
            more, page = data.get("more"), page + 1
            for release in data.get("results", []):
                title = release.get("title") or ""
                if not ADULT_DLC.search(title) or "demo" in title.lower():
                    continue
                for link in release.get("extlinks") or []:
                    if link.get("name") != "steam" or not str(link.get("id", "")).isdigit():
                        continue
                    dlc = int(link["id"])
                    base = _base_game(dlc, bases)
                    if not base:
                        continue
                    parts = title.split(" - ", 1)
                    yield {
                        "appID": base,
                        "patch": {
                            "name": parts[1] if len(parts) == 2 else "18+ DLC on Steam",
                            "kind": "adult",
                            "official": True,
                            "by": ", ".join(p["name"] for p in release.get("producers") or []) or "Publisher",
                            "source": {"site": "vndb", "page": f"https://vndb.org/{release['id']}", "key": f"{release['id']}-{dlc}"},
                            "version": None,
                            "languages": sorted({l["lang"] for l in release.get("languages") or []}) or ["en"],
                            "adult": True,
                            "notes": "A DLC of the game on Steam: once owned, it downloads with the game.",
                            "files": [{"host": "steam", "url": f"https://store.steampowered.com/app/{dlc}", "dlc": dlc,
                                       "name": None, "format": None}],
                        },
                    }
    finally:
        with open(DLC_BASES, "w") as file:
            file.write(json.dumps(dict(sorted(bases.items(), key=lambda kv: int(kv[0]))), indent=2) + "\n")


def _vns(app_id):
    """The VNDB visual novels a Steam app is a release of, with each one's original language."""
    body = {"filters": ["extlink", "=", ["steam", app_id]], "fields": "vns.id,vns.olang", "results": 25}
    results = fetch_json(API, body=body, delay=1.0).get("results", [])
    return {vn["id"]: vn.get("olang") for release in results for vn in release.get("vns") or []}


def wanted(release, olang):
    """Whether a patch release applies to the Steam release: for Windows, not a demo, still
    offered, and either in English or, for a game written in English, in any language (it
    translates what Steam sells). Most other patches translate the Japanese edition and won't
    apply to the English one."""
    title = (release.get("title") or "").lower()
    languages = {l["lang"] for l in release.get("languages") or []}
    if "win" not in (release.get("platforms") or ["win"]) or "demo" in title or "trial" in title:
        return False
    if GONE_WORDS.search(release.get("notes") or ""):
        return False
    return "en" in languages or olang == "en"


def collect(app_ids, has_official=frozenset()):
    """`has_official`: games another source already lists an official patch for."""
    # Two queries per game: VNDB rejects a release filter nested inside a VN filter inside a
    # release query, so the game's VNs are found first, then their patches.
    for app_id in app_ids:
        try:
            results = []
            for vn, olang in sorted(_vns(app_id).items()):
                body = {
                    "filters": ["and", ["patch", "=", 1], ["vn", "=", ["id", "=", vn]]],
                    "fields": "id,title,official,languages.lang,producers.name,released,extlinks.url,extlinks.label,notes,platforms",
                    "results": 50,
                }
                for release in fetch_json(API, body=body, delay=1.0).get("results", []):
                    if release.get("official") and app_id in has_official:
                        continue
                    if wanted(release, olang):
                        results.append(release)
        except Exception as error:
            print(f"VNDB {app_id}: {error}")
            continue
        for release in results:
            title = release.get("title") or ""
            official = bool(release.get("official"))
            # Steam links are the game or its DLC, which Shiori lists from Steam itself.
            links = [l["url"] for l in release.get("extlinks") or [] if l.get("url") and host_of(l["url"]) != "steam"]
            # An official patch on Steam comes from collect_official_dlc.
            on_steam = any(host_of(l.get("url") or "") == "steam" for l in release.get("extlinks") or [])
            if official and (not links or on_steam):
                continue
            page = f"https://vndb.org/{release['id']}"
            languages = sorted({l["lang"] for l in release.get("languages") or []}) or ["en"]
            # A release named after the game itself says nothing; "<game> - <what>" names the patch.
            parts = title.split(" - ", 1)
            name = parts[1] if len(parts) == 2 else (
                "Patch" if official else "Fan patch" if languages == ["en"] else "Fan translation")
            adult = bool(ADULT_WORDS.search(title) or ADULT_WORDS.search(release.get("notes") or ""))
            source = {"site": "vndb", "page": page, "key": release["id"]}
            if links:
                source["origin"] = links[0]
            # Other links (more of the release's links, or ones its notes give) to the file itself.
            noted = re.findall(r"https?://[^\s\[\]<>\"']+", release.get("notes") or "")
            alternates = [u for u in file_links(links[1:] + noted) if u not in links[:1]]
            file = {"host": "store" if links and host_of(links[0]) == "store" else "page",
                    "url": links[0] if links else page, "name": None, "format": None}
            if alternates:
                file["mirrors"] = [{"host": host_of(u), "url": u} for u in alternates]
            yield {
                "appID": app_id,
                "patch": {
                    "name": name,
                    "kind": "adult" if adult else ("other" if official else "translation"),
                    "official": official,
                    "by": ", ".join(p["name"] for p in release.get("producers") or []) or ("Publisher" if official else "Fan patch"),
                    "source": source,
                    "version": None,
                    "languages": languages,
                    "adult": adult,
                    "notes": "Listed on VNDB; the download is on the patch's own page.",
                    # A blog post, a forum thread or a shop, never a file Shiori has checked.
                    "files": [file],
                },
            }
