"""sakura-patcher (github.com/gan-of-culture/sakura-patcher): an open-source desktop tool that
installs Winged Cloud's official 18+ patches for the Sakura games. Its `ALL_PATCHES` list names
each game, the patch's link on Winged Cloud's WeTransfer portal (the same links as Winged
Cloud's Sakura Patch Collection on Patreon, which automated readers can't reach) and the MD5 of
each file the patch puts in the game's `game/` folder. It fills in what wingedcloud.json, the
hand copy of that post, doesn't have, and only those: a game that wingedcloud.json or another
site (uncensorpat.ch, which links each game's own Patreon post) already lists a Winged Cloud
18+ patch for is left as it is, and a link that leads to a different transfer is reported.

The tool's repository has no licence file, so only facts are taken from it (game titles, the
publisher's own links, file hashes), with credit, and none of its code: the file is read from
GitHub and its list parsed as a Python literal (ast.literal_eval), never run. The patches are
Winged Cloud's, so each entry names Winged Cloud as maker and its Patreon post as origin.

The schema has no field for hashes of installed files, so the MD5s are only checked here
(every listed file must have one) and not carried into the list."""

import ast
import json
import os
import re
import time

import download
from common import fetch_json, fetch_text, host_of
from sources import wingedcloud
from sources.patchmoe import _normalise, _titles, app_id_for, TITLES

REPOSITORY = "https://github.com/gan-of-culture/sakura-patcher"
RAW = "https://raw.githubusercontent.com/gan-of-culture/sakura-patcher/main/sakura_patcher.py"
POST = "https://www.patreon.com/wingedcloud/posts/sakura-patch-37106416"
MAKER = "Winged Cloud"

# Where the tool's name for a game isn't the one Steam's store search finds.
STEAM_NAMES = {
    "Would you like to run an idol café": "Would you like to run an idol café?",
    "Would you like to run an idol café 2": "Would you like to run an idol café? 2",
    "Would you like to run an idol café 3": "Would you like to run an idol café? 3",
}


def parse(source):
    """The `ALL_PATCHES` list from the tool's source, as plain data: the module is parsed, not
    run, and only that assignment's literal is evaluated."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ALL_PATCHES" for t in node.targets):
            rows = ast.literal_eval(node.value)
            break
    else:
        raise ValueError("no ALL_PATCHES in sakura_patcher.py")
    patches = []
    for row in rows:
        game, url, hashes = row.get("game"), row.get("URL"), row.get("hashes") or {}
        if not isinstance(game, str) or not isinstance(url, str) or not url.strip():
            continue
        if host_of(url) != "wetransfer":
            print(f"sakura-patcher: {game}: not a WeTransfer link ({url}); skipped")
            continue
        if not hashes or not all(re.fullmatch(r"[0-9A-Fa-f]{32}", str(v)) for v in hashes.values()):
            print(f"sakura-patcher: {game}: missing or odd MD5s; skipped")
            continue
        patches.append({"game": game.strip(), "url": url.strip(), "md5": {k: v.lower() for k, v in hashes.items()}})
    return patches


def _by_winged_cloud(app_id):
    """Whether Steam names Winged Cloud as the game's developer or publisher."""
    try:
        data = fetch_json(f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english", delay=1.5)
        game = data[str(app_id)]["data"]
    except Exception:
        return False
    names = (game.get("developers") or []) + (game.get("publishers") or [])
    return any("winged cloud" in n.lower() for n in names)


def app_id(game, titles):
    """The game's Steam app id, matched like patch.moe's titles (titles.json). A match found for
    the first time must be a Winged Cloud game on Steam, or it's kept as null for a person to fix."""
    title = STEAM_NAMES.get(game, game)
    known = title in titles
    found = app_id_for(title, titles)
    if found and not known and not _by_winged_cloud(found):
        print(f"sakura-patcher: {game} matched {found}, which isn't a Winged Cloud game on Steam; left unmatched")
        titles[title] = None
        return None
    return found


PATCHES = os.path.join(os.path.dirname(__file__), "..", "..", "patches")
_transfers = {}


def transfer(url):
    """The WeTransfer transfer a link leads to (a we.tl short link is followed with a HEAD
    request, slowly: it sometimes answers a quick run of them with no transfer), or None."""
    if url not in _transfers:
        link = None
        for attempt in range(2):
            if "we.tl/" in url:
                time.sleep(1.5 * (attempt + 1))
            try:
                link = download.wetransfer_link(url)
            except Exception:
                link = None
            if link:
                break
        _transfers[url] = link[0] if link else None
    return _transfers[url]


def _listed_elsewhere(app_id):
    """Links of the Winged Cloud 18+ patches the list already has for a game from other sites."""
    try:
        game = json.load(open(os.path.join(PATCHES, f"{app_id}.json")))
    except FileNotFoundError:
        return []
    return [f["url"] for p in game["patches"]
            if p["adult"] and p["official"] and p["by"] == MAKER and p["source"]["site"] != "sakurapatcher"
            for f in p["files"] if f["host"] == "wetransfer"]


def _report(game, app_id, url, others, where):
    mine, theirs = transfer(url), [transfer(u) for u in others]
    if mine is None or None in theirs:
        print(f"sakura-patcher: {game} ({app_id}): couldn't tell whether {url} is the transfer {where} links")
    elif mine not in theirs:
        print(f"sakura-patcher: {game} ({app_id}) links {url}, another transfer than {where}'s {', '.join(others)}")


def collect():
    rows = parse(fetch_text(RAW))
    hand = json.load(open(wingedcloud.FILE))["patches"]
    hand_titles = {_normalise(r["game"]): r for r in hand}
    hand_ids = {int(r["appID"]): r for r in hand}
    titles = _titles()
    try:
        for row in rows:
            listed = hand_titles.get(_normalise(row["game"]))
            found = int(listed["appID"]) if listed else app_id(row["game"], titles)
            if not found:
                print(f"sakura-patcher: no Steam app id for {row['game']}")
                continue
            listed = listed or hand_ids.get(found)
            if listed:
                # wingedcloud.json lists this game: it wins; a different transfer is only reported.
                if listed["url"] != row["url"]:
                    _report(row["game"], found, row["url"], [listed["url"]], "wingedcloud.json")
                continue
            others = _listed_elsewhere(found)
            if others:
                if row["url"] not in others:
                    _report(row["game"], found, row["url"], others, "the list")
                continue
            yield {
                "appID": found,
                "title": row["game"],
                "patch": {
                    "name": "18+ patch",
                    "kind": "adult",
                    "official": True,
                    "by": MAKER,
                    "source": {"site": "sakurapatcher", "page": REPOSITORY, "origin": POST, "key": row["game"]},
                    "version": None,
                    "languages": ["en"],
                    "adult": True,
                    "notes": "Winged Cloud's own patch; the link comes from sakura-patcher's list.",
                    "files": [{"host": "wetransfer", "url": row["url"], "name": None, "format": None}],
                },
            }
    finally:
        with open(TITLES, "w") as file:
            json.dump(dict(sorted(titles.items())), file, ensure_ascii=False, indent=2)
            file.write("\n")
