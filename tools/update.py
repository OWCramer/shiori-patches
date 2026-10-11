#!/usr/bin/env python3
"""Reads the patch sites, merges what they list into patches/<appid>.json, records each new
file's size and SHA-256, and rewrites index.json.

    tools/update.py                       # every source, new uncensorpat.ch pages only
    tools/update.py --full                # every uncensorpat.ch page again
    tools/update.py --sources nekonyan    # one source
    tools/update.py --hash-limit-gb 10    # stop hashing after this much downloading
    tools/update.py --app-ids 333600,451760   # limit uncensorpat.ch and VNDB to these games

What a person set by hand (verified, notes, install, kind) is kept; what a site says (names,
links, languages) is refreshed."""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from common import fetch_json, slug, today  # noqa: E402
import download  # noqa: E402
from sources import denpasoft, nekonyan, patchmoe, saikey, uncensorpatch, vndb, wingedcloud  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
PATCHES = os.path.join(ROOT, "patches")
COMPATIBILITY = "https://raw.githubusercontent.com/OWCramer/shiori-compatibility/main/engines/{}.json"
ENGINES = ("renpy", "artemis", "kirikiri", "siglus", "luca")
SITE_FIELDS = ("name", "official", "by", "languages", "adult")


def load():
    games = {}
    for path in glob.glob(os.path.join(PATCHES, "*.json")):
        game = json.load(open(path))
        games[game["appID"]] = game
    return games


def save(games):
    os.makedirs(PATCHES, exist_ok=True)
    index = {}
    for app_id, game in sorted(games.items()):
        if not game["patches"]:
            continue
        game["patches"].sort(key=lambda p: (not p["official"], p["source"]["site"], p["id"]))
        path = os.path.join(PATCHES, f"{app_id}.json")
        text = json.dumps(game, ensure_ascii=False, indent=2) + "\n"
        if not os.path.exists(path) or open(path).read() != text:
            open(path, "w").write(text)
        index[str(app_id)] = {
            "title": game["title"],
            "patches": len(game["patches"]),
            "updated": max(max(p["checked"], p["added"]) for p in game["patches"]),
        }
    data = {"version": 1, "games": index}
    open(os.path.join(ROOT, "index.json"), "w").write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def steam_title(app_id):
    try:
        data = fetch_json(f"https://store.steampowered.com/api/appdetails?appids={app_id}&filters=basic", delay=1.5)
        return data[str(app_id)]["data"]["name"]
    except Exception:
        return None


def _same_file(old, new):
    return old.get("url") == new.get("url") and old.get("host") == new.get("host")


def merge(games, entry):
    """Adds or refreshes one patch a site listed. Returns 'added', 'updated' or None."""
    app_id = entry["appID"]
    candidate = dict(entry["patch"])
    community_checked = candidate.pop("communityVerified", None)
    game = games.get(app_id)
    if game is None:
        title = entry.get("title") or steam_title(app_id) or str(app_id)
        game = games[app_id] = {"appID": app_id, "title": title, "patches": []}
    key = (candidate["source"]["site"], candidate["source"].get("key"))
    existing = next((p for p in game["patches"] if (p["source"]["site"], p["source"].get("key")) == key), None)
    if community_checked:
        note = "uncensorpat.ch checked this patch on PC."
        candidate["notes"] = (candidate.get("notes", "") + " " + note).strip()
    installer = any(f.get("installer") or f.get("format") == "exe" for f in candidate["files"])

    if existing is None:
        def plain(url):
            return url.split("?")[0].rstrip("/").replace("/products/", "/product/")
        urls = {plain(f["url"]) for f in candidate["files"]}
        other = next((p for p in game["patches"]
                      if any(plain(f["url"]) in urls or any(plain(m["url"]) in urls for m in f.get("mirrors", []))
                             for f in p["files"])), None)
        if other is not None:
            # Another site already lists this file. The publisher's own listing takes it over.
            if candidate["official"] and other["source"]["site"] == "uncensorpatch":
                for field in ("name", "kind", "official", "by", "source", "languages", "adult"):
                    other[field] = candidate[field]
                if other["files"][0]["host"] in ("store", "page") or candidate["files"][0]["host"] not in ("store", "page"):
                    other["files"] = [dict(f, size=None, sha256=None) if "size" not in f else f for f in candidate["files"]]
                if candidate.get("notes"):
                    other["notes"] = candidate["notes"]
                other["checked"] = today()
                return "updated"
            return None
        ids = {p["id"] for p in game["patches"]}
        base = slug(f"{candidate['source']['site']}-{candidate['name']}")
        patch_id, n = base, 2
        while patch_id in ids:
            patch_id, n = f"{base}-{n}", n + 1
        patch = {
            "id": patch_id,
            **{k: candidate[k] for k in ("name", "kind", "official", "by", "source", "version", "languages", "adult")},
            "branch": None,
            "status": "unsupported" if installer else "ok",
            "verified": False,
            "notes": candidate.get("notes", ""),
            "files": [{k: v for k, v in f.items()} for f in candidate["files"]],
            "added": today(),
            "checked": today(),
        }
        for f in patch["files"]:
            f.setdefault("size", None)
            f.setdefault("sha256", None)
        if candidate.get("install"):
            patch["install"] = candidate["install"]
        game["patches"].append(patch)
        return "added"

    changed = False
    for field in SITE_FIELDS + ("source",):
        if existing.get(field) != candidate.get(field):
            existing[field] = candidate[field]
            changed = True
    files = []
    for new in candidate["files"]:
        old = next((f for f in existing["files"] if _same_file(f, new)), None)
        if old:
            merged = dict(old)
            for k in ("mirrors", "dlc"):
                if k in new:
                    merged[k] = new[k]
            files.append(merged)
        else:
            files.append({**new, "size": None, "sha256": None})
            changed = True
    if len(files) != len(existing["files"]):
        changed = True
    existing["files"] = files
    if existing.get("status") == "dead":
        existing["status"] = "ok"
        changed = True
    if not existing.get("notes") and candidate.get("notes"):
        existing["notes"] = candidate["notes"]
        changed = True
    existing["checked"] = today()
    return "updated" if changed else None


def hash_files(games, limit_bytes):
    """Downloads files with no SHA-256 yet, up to `limit_bytes` in all."""
    spent = 0
    for game in games.values():
        for patch in game["patches"]:
            for file in patch["files"]:
                if file.get("sha256") or file["host"] not in ("direct", "gdrive", "mega", "wetransfer"):
                    continue
                if file["host"] == "gdrive" and not download.drive_file_id(file["url"]):
                    try:
                        folder = download.drive_folder_files(file["url"])
                    except Exception as error:
                        print(f"{game['appID']} {patch['id']}: Drive folder: {error}")
                        continue
                    archives = [f for f in folder if f[1].lower().endswith((".zip", ".7z", ".rar"))]
                    if len(archives) != 1:
                        continue
                    file.setdefault("mirrors", []).insert(0, {"host": "gdrive", "url": file["url"]})
                    file["url"] = f"https://drive.google.com/file/d/{archives[0][0]}/view"
                if spent >= limit_bytes:
                    return
                try:
                    info = download.inspect(file["host"], file["url"], limit=limit_bytes - spent)
                except download.Unavailable as error:
                    print(f"{game['appID']} {patch['id']}: {error}")
                    if error.dead:
                        patch["status"] = "dead"
                    continue
                except Exception as error:
                    print(f"{game['appID']} {patch['id']}: {error}")
                    continue
                spent += info["size"]
                file["size"] = info["size"]
                file["sha256"] = info["sha256"]
                if info["name"]:
                    file["name"] = info["name"]
                    lower = info["name"].lower()
                    file["format"] = next((e for e in ("zip", "7z", "rar", "exe") if lower.endswith("." + e)), "file")
                entries = info["entries"] or []
                exes = [e for e in entries if e.lower().endswith(".exe")]
                if file["format"] == "exe" or (exes and len(exes) * 2 >= len([e for e in entries if not e.endswith("/")])):
                    file["installer"] = True
                    patch["status"] = "unsupported"
                print(f"{game['appID']} {patch['id']}: {info['size']} bytes, {len(entries)} entries")


def compatibility_app_ids():
    ids = set()
    for engine in ENGINES:
        try:
            for game in fetch_json(COMPATIBILITY.format(engine))["games"]:
                ids.add(game["appID"])
        except Exception as error:
            print(f"compatibility {engine}: {error}")
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="nekonyan,saikey,patchmoe,wingedcloud,denpasoft,uncensorpatch,vndb")
    parser.add_argument("--full", action="store_true", help="read every uncensorpat.ch page again")
    parser.add_argument("--app-ids", help="comma-separated app ids for uncensorpat.ch and VNDB")
    parser.add_argument("--hash-limit-gb", type=float, default=10)
    parser.add_argument("--summary", help="write a Markdown summary of the changes here")
    args = parser.parse_args()

    games = load()
    sources = args.sources.split(",")
    only = [int(x) for x in args.app_ids.split(",")] if args.app_ids else None
    results = {"added": [], "updated": []}

    def take(name, entries):
        try:
            for entry in entries:
                outcome = merge(games, entry)
                if outcome:
                    results[outcome].append(f"{name}: {entry['appID']} {entry['patch']['name']}")
        except Exception as error:
            print(f"{name} failed: {error}")

    if "nekonyan" in sources:
        take("NekoNyan", nekonyan.collect())
    if "saikey" in sources:
        take("Saikey", saikey.collect())
    if "patchmoe" in sources:
        take("patch.moe", patchmoe.collect())
    if "wingedcloud" in sources:
        take("Winged Cloud", wingedcloud.collect())
    if "denpasoft" in sources:
        take("Denpasoft", denpasoft.collect())
    if "uncensorpatch" in sources:
        if only is not None:
            ids = only
        else:
            try:
                listed = uncensorpatch.patched_app_ids()
            except Exception as error:
                print(f"uncensorpat.ch list failed: {error}")
                listed = []
            known = {g["appID"] for g in games.values()
                     if any(p["source"]["site"] == "uncensorpatch" for p in g["patches"])}
            ids = listed if args.full else [i for i in listed if i not in known]
        take("uncensorpat.ch", uncensorpatch.collect(ids))
    if "vndb" in sources:
        ids = only if only is not None else sorted(set(games) | compatibility_app_ids())
        take("VNDB", vndb.collect(ids))

    try:
        hash_files(games, int(args.hash_limit_gb * (1 << 30)))
    finally:
        save(games)  # keep what was read and hashed even if something failed late

    lines = [f"- Added {item}" for item in results["added"]] + [f"- Updated {item}" for item in results["updated"]]
    print("\n".join(lines) or "No changes from the sites.")
    if args.summary:
        open(args.summary, "w").write(("\n".join(lines) or "Recorded file sizes and hashes.") + "\n")


if __name__ == "__main__":
    main()
