"""uncensorpat.ch: a community database of uncensor patches, one page per Steam app id.
A page says whether there's a patch, whether the site verified it, how to install it, and
where to get it: a Steam DLC, a shop, or a download link (often MEGA)."""

import html as htmllib
import re

from common import direct_link, fetch_text, file_links, host_of, steam_app_id

SITE = "https://www.uncensorpat.ch"
# Links on these hosts come from the game's publisher.
PUBLISHER_HOSTS = ("nekonyansoft.com", "wingedcloud", "sekaiproject.com", "mangagamer.com",
                   "denpasoft.com", "jastusa.com", "kaguragames.com", "shiravune.com",
                   "frontwing.jp", "sol-press.com", "dlsite.com")

_gate_passed = False


def _page(path):
    global _gate_passed
    if not _gate_passed:
        fetch_text(SITE + "/checked/", browser=True)  # the age check sets a cookie
        _gate_passed = True
    return fetch_text(SITE + path, browser=True, delay=1.5)


def _text(html):
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    html = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>', r" ⟦\1⟧ ", html)
    html = re.sub(r"<br\s*/?>|</p>|</li>", "\n", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]+", " ", htmllib.unescape(html))


def patched_app_ids():
    """Every app id the site lists as having a patch."""
    html = _page("/game-list/patches")
    return sorted({int(x) for x in re.findall(r'href="/game/(\d+)"', html)})


def _section(text, start, ends):
    i = text.find(start)
    if i < 0:
        return ""
    i += len(start)
    j = min([k for k in (text.find(e, i) for e in ends) if k >= 0] or [len(text)])
    return text[i:j].strip()


def _links(section):
    links = []
    for url in re.findall(r"⟦(https?://[^⟧\s]+)⟧", section):
        url = url.replace("&amp;", "&")
        if url not in links:
            links.append(url)
    return links


def _clean_store(url):
    # Drop the site's affiliate parameters.
    return re.sub(r"\?(rfsn|utm_)[^#]*", "", url)


PUBLISHER_NAMES = {"nekonyansoft": "NekoNyan", "denpasoft": "Denpasoft", "wingedcloud": "Winged Cloud",
                   "Winged Cloud": "Winged Cloud", "sekaiproject": "Sekai Project", "mangagamer": "MangaGamer",
                   "jastusa": "JAST", "dlsite": "DLsite", "kaguragames": "Kagura Games", "shiravune": "Shiravune"}


def _publisher(text):
    for needle, name in PUBLISHER_NAMES.items():
        if needle in text:
            return name
    return "Publisher"


def read(app_id):
    """The site's patch for one game, or None."""
    text = _text(_page(f"/game/{app_id}"))
    if "There IS an uncensor patch" not in text:
        return None
    title_match = re.search(r"There IS an uncensor patch available for (.+?)!", text)
    title = title_match.group(1).strip() if title_match else str(app_id)
    verified = "HAS been verified" in text
    ends = ["Install Instructions:", "It's Working If:", "Patch download:", "Steam store:", "Please enable JavaScript"]
    install = _section(text, "Install Instructions:", ends[1:])
    working = _section(text, "It's Working If:", ends[2:])
    downloads = [direct_link(u) for u in _links(_section(text, "Patch download:", ends[3:])) if "steam://" not in u]
    info = _section(text, "Patch Information:", ends)
    # Other places to get the file, mentioned in passing ("There's also a Dropbox link if the
    # Google Drive link is no good"): mirrors of the download.
    alternates = [u for u in file_links(_links(info) + _links(install)) if u not in downloads]

    files = []
    dlc = re.search(r"found as DLC for the game on the Steam Store: ⟦https://store\.steampowered\.com/app/(\d+)", text)
    stores = [_clean_store(u) for u in _links(info) + downloads if host_of(u) == "store"]
    if dlc:
        dlc_id = int(dlc.group(1))
        files.append({"host": "steam", "url": f"https://store.steampowered.com/app/{dlc_id}", "dlc": dlc_id,
                      "name": None, "format": None,
                      "mirrors": [{"host": "store", "url": u} for u in dict.fromkeys(stores)]})
    else:
        for url in downloads:
            host = host_of(url)
            if host == "store":
                continue
            files.append({"host": host, "url": url, "name": None, "format": None})
        if not files and stores:
            files.append({"host": "store", "url": stores[0], "name": None, "format": None,
                          "mirrors": [{"host": "store", "url": u} for u in dict.fromkeys(stores[1:])]})
        elif len(files) > 1:
            # Several links are usually mirrors of one archive.
            files = [dict(files[0], mirrors=[{"host": f["host"], "url": f["url"]} for f in files[1:]])]
        if files and files[0]["host"] not in ("steam", "store") and alternates:
            files[0]["mirrors"] = files[0].get("mirrors", []) + [{"host": host_of(u), "url": u} for u in alternates]
    if not files:
        return None
    for f in files:
        if not f.get("mirrors"):
            f.pop("mirrors", None)

    publisher_link = "publisher's link" in info or any(
        h in (files[0]["url"] or "") for h in PUBLISHER_HOSTS)
    # "The patch information is taken from the [link] Winged Cloud Patreon": the publisher's
    # own post, which is where the patch comes from.
    origin = next((u for u in _links(info) if "uncensorpat.ch" not in u and host_of(u) not in ("steam", "store")
                   and direct_link(u) not in alternates and direct_link(u) not in downloads), None)
    from_publisher = "taken from the" in info and _publisher(info) != "Publisher"
    official = bool(dlc) or publisher_link or from_publisher or files[0]["host"] == "store"
    installer = bool(re.search(r"\.exe\b|patch installer|patcher", install, re.I))
    notes = []
    if install:
        notes.append("Install (PC): " + re.sub(r"\s+", " ", install)[:400])
    if working:
        notes.append("It's working if: " + re.sub(r"\s+", " ", working)[:300])
    if installer:
        for f in files:
            f["installer"] = True
    into = "game" if re.search(r'"game" folder|folder named .game.|\bgame/ ?folder|enter the .game. folder', install, re.I) else None

    patch = {
        "name": "18+ DLC on Steam" if dlc else ("Uncensor patch (to buy)" if files[0]["host"] == "store" else "Uncensor patch"),
        "kind": "adult",
        "official": official,
        "by": "Steam" if dlc else _publisher(info + " " + " ".join(f["url"] for f in files)) if official else "uncensorpat.ch community",
        "source": {"site": "uncensorpatch", "page": f"{SITE}/game/{app_id}", "key": str(app_id),
                   **({"origin": origin} if origin else {})},
        "version": None,
        "languages": ["en"],
        "adult": True,
        "notes": " ".join(notes),
        "files": files,
        "communityVerified": verified,
    }
    if into:
        patch["install"] = {"into": into}
    return {"appID": app_id, "title": title, "patch": patch}


def collect(app_ids=None):
    for app_id in app_ids if app_ids is not None else patched_app_ids():
        try:
            entry = read(app_id)
        except Exception as error:  # one page failing shouldn't stop the run
            print(f"uncensorpat.ch {app_id}: {error}")
            continue
        if entry:
            yield entry
