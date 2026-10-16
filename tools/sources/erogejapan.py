"""Eroge Japan (erogejapan.com), the publisher's own R18 patch pages. Its robots.txt allows
everything but /admin/ and points to a sitemap, which lists one page per patch
(/patch/<slug>/, in English at the root and translated under /<language>/). Each patch page
links its game's page, which links the game on Steam, and the patch's mirrors: the file on
erogejapan.com itself, and sometimes MEGA, Google Drive or Baidu (Baidu needs a code, so it's
left out). The site was rebuilt on 2026-10-09 and every file moved, so the links are always
taken from the pages as they are now, never kept from before."""

import html as htmllib
import re
import urllib.parse

import download
from common import fetch_text, format_of, host_of

SITE = "https://erogejapan.com"
SITEMAP = SITE + "/sitemap.xml"
DELAY = 2.0
def _text(fragment):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def patch_pages():
    """The English patch pages the sitemap lists."""
    xml = fetch_text(SITEMAP, delay=DELAY)
    pages = re.findall(r"<loc>(https://erogejapan\.com/patch/[^/<]+/)</loc>", xml)
    return sorted(set(pages))


# What a download's label says: its language, or a platform Shiori doesn't run.
LABELS = {"english": "en", "日本語": "ja", "简体中文": "zh-Hans", "繁體中文": "zh-Hant", "한국어": "ko",
          "pc": None, "windows": None, "": None}
LANGUAGE_NAMES = {"ja": "Japanese", "zh-Hans": "Simplified Chinese", "zh-Hant": "Traditional Chinese", "ko": "Korean"}
# Mirrors Shiori can fetch, best first; MediaFire is offered as a page.
PREFERENCE = ("erogejapan", "mega", "gdrive", "googledrive", "mediafire")


def read_page(url):
    """(game, game page, version, [(language, [links best first])]) of one patch page. A page
    has a download box per release (`ej-download`) and in it a block per file (`ej-file`),
    labelled by language or platform, listing that file's mirrors (`data-mirror`)."""
    page = fetch_text(url, delay=DELAY)
    page = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", page, flags=re.S)
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    game = _text(title.group(1)).split("|")[0].strip() if title else ""
    game = re.sub(r"\s+R18G? Patch$", "", game, flags=re.I).strip() or None
    game_page = re.search(r'href="(/games/[^"/]+/)"', page)
    box = page.split('class="ej-card ej-download"', 1)[1] if 'class="ej-card ej-download"' in page else ""
    box = box.split("ej-howto", 1)[0]
    version = re.search(r'class="ej-version"[^>]*>(.*?)</span>', box, re.S)
    version = re.sub(r"\bVer\.\s*", "", _text(version.group(1))) if version else None
    files = []
    for block in box.split('class="ej-file"')[1:]:
        label = _text(block.split("<ul", 1)[0].split(">", 1)[-1]).lower()
        if label not in LABELS and label.lower() not in LABELS:
            continue  # Mac, Linux, Android
        mirrors = re.findall(r'<a [^>]*href="([^"]+)"[^>]*data-mirror="([^"]+)"', block)
        mirrors = sorted(((htmllib.unescape(h), k) for h, k in mirrors if k in PREFERENCE),
                         key=lambda m: PREFERENCE.index(m[1]))
        if mirrors:
            files.append((LABELS[label] or "en", [h for h, _ in mirrors]))
    return game, urllib.parse.urljoin(SITE, game_page.group(1)) if game_page else None, version or None, files


def steam_id(game_page):
    page = fetch_text(game_page, delay=DELAY)
    ids = {int(m) for m in re.findall(r"store\.steampowered\.com/app/(\d+)", page)}
    return ids.pop() if len(ids) == 1 else None


def collect():
    for url in patch_pages():
        try:
            game, game_page, version, files = read_page(url)
            app_id = steam_id(game_page) if game_page else None
        except Exception as error:
            print(f"Eroge Japan {url}: {error}")
            continue
        if not app_id or not files:
            print(f"Eroge Japan {url}: {'no Steam app' if not app_id else 'no download for Windows'}; skipped")
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        for language, links in files:
            main = links[0]
            name = urllib.parse.unquote(main.rsplit("/", 1)[-1]) if host_of(main) == "direct" else None
            file = {"host": host_of(main), "url": main, "name": name, "format": format_of(name)}
            if file["format"] == "zip" and download.is_installer(download.zip_entries(main)):
                # Some patches are a Windows setup program in a zip; Shiori can't run one.
                file["installer"] = True
            if links[1:]:
                file["mirrors"] = [{"host": host_of(m), "url": m} for m in links[1:]]
            yield {
                "appID": app_id,
                "title": game,
                "patch": {
                    "name": "R18 patch" + (f" ({LANGUAGE_NAMES.get(language, language)})" if language != "en" else ""),
                    "kind": "adult",
                    "official": True,
                    "by": "Eroge Japan",
                    "source": {"site": "erogejapan", "page": url, "key": slug + ("" if language == "en" else "-" + language)},
                    "version": version,
                    "languages": [language],
                    "adult": True,
                    "files": [file],
                },
            }
