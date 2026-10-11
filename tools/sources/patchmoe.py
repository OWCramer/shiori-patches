"""patch.moe: publishers' DLC patches as direct zips, listed by title (no app ids). The list
is shown in the language the page is read in, so each language is read in turn. Titles are
matched to Steam app ids through the store's search; matches are kept in titles.json, where
a wrong or missing one can be fixed by hand."""

import html as htmllib
import json
import os
import re
import unicodedata
import urllib.parse

from common import fetch_json, fetch_text, format_of

SITE = "https://www.patch.moe/"
LANGUAGES = {"en": "en", "zh_tw": "zh-Hant", "zh_cn": "zh-Hans"}
TITLES = os.path.join(os.path.dirname(__file__), "..", "titles.json")


def _normalise(title):
    title = unicodedata.normalize("NFKC", title).lower()
    return re.sub(r"[^0-9a-z぀-鿿]+", "", title)


def _titles():
    try:
        return json.load(open(TITLES))
    except FileNotFoundError:
        return {}


def app_id_for(title, titles):
    if title in titles:
        return titles[title]
    query = urllib.parse.quote(title)
    found = None
    try:
        results = fetch_json(f"https://store.steampowered.com/api/storesearch/?term={query}&cc=us&l=english")
        for item in results.get("items", []):
            if _normalise(item.get("name", "")) == _normalise(title):
                found = item["id"]
                break
    except Exception as error:
        print(f"patch.moe: Steam search for {title!r} failed: {error}")
        return None
    titles[title] = found
    return found


def _rows(html):
    for title, release, url in re.findall(
            r'<td class="title">(.*?)</td><td class="release">(.*?)</td><td class="patch"><a download href="\s*([^"]+?)\s*"',
            html, re.S):
        yield htmllib.unescape(title).strip(), release.strip(), url.strip()


def collect():
    titles = _titles()
    seen = {}
    for form, language in LANGUAGES.items():
        html = fetch_text(SITE, data={"lang": form}, browser=True, headers={"Cookie": "age_flag=1"})
        if "<td class=\"title\">" not in html:
            html = fetch_text(SITE + "?flag=1", browser=True)
            html = fetch_text(SITE, data={"lang": form}, browser=True)
        for title, release, url in _rows(html):
            if release.upper().startswith("COMING"):
                continue
            seen.setdefault(url, (title, release, set()))[2].add(language)
    for url, (title, release, languages) in seen.items():
        app_id = app_id_for(title, titles)
        if not app_id:
            continue
        name = url.rsplit("/", 1)[-1]
        yield {
            "appID": int(app_id),
            "title": title,
            "patch": {
                "name": f"{title} DLC patch",
                "kind": "adult",
                "official": True,
                "by": "patch.moe",
                "source": {"site": "patchmoe", "page": SITE, "key": url},
                "version": None,
                "languages": sorted(languages),
                "adult": True,
                "files": [{"host": "direct", "url": url, "name": name, "format": format_of(name)}],
            },
        }
    with open(TITLES, "w") as file:
        json.dump(dict(sorted(titles.items())), file, ensure_ascii=False, indent=2)
        file.write("\n")
