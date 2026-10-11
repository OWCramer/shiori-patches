"""VNDB (api.vndb.org/kana): fan-made patches (translations, restorations) for games on
Steam. VNDB lists the release and its website but not a download, so these entries point to
the patch's page until someone adds the file by hand."""

from common import fetch_json

API = "https://api.vndb.org/kana/release"
LANGUAGE_NAMES = {"zh-Hans": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)"}


def _vn_ids(app_id):
    """The VNDB visual novels a Steam app is a release of."""
    body = {"filters": ["extlink", "=", ["steam", app_id]], "fields": "vns.id", "results": 25}
    results = fetch_json(API, body=body, delay=1.0).get("results", [])
    return sorted({vn["id"] for release in results for vn in release.get("vns") or []})


def collect(app_ids):
    # Two queries per game: VNDB rejects a release filter nested inside a VN filter inside a
    # release query, so the game's VNs are found first, then their unofficial patches.
    for app_id in app_ids:
        try:
            vns = _vn_ids(app_id)
            results = []
            for vn in vns:
                body = {
                    "filters": ["and", ["patch", "=", 1], ["vn", "=", ["id", "=", vn]]],
                    "fields": "id,title,official,languages.lang,producers.name,released,extlinks.url,extlinks.label,notes,platforms",
                    "results": 25,
                }
                results += [r for r in fetch_json(API, body=body, delay=1.0).get("results", []) if not r.get("official")]
        except Exception as error:
            print(f"VNDB {app_id}: {error}")
            continue
        for release in results:
            title = release.get("title") or ""
            languages = {l["lang"] for l in release.get("languages") or []}
            # Patches for the Steam (English) release: English ones, for Windows, no demos.
            # Most other unofficial patches translate the Japanese edition and won't apply.
            if "win" not in (release.get("platforms") or ["win"]) or "en" not in languages or "demo" in title.lower():
                continue
            links = [l["url"] for l in release.get("extlinks") or [] if l.get("url")]
            page = f"https://vndb.org/{release['id']}"
            languages = sorted({l["lang"] for l in release.get("languages") or []}) or ["en"]
            # A release named after the game itself says nothing; its notes' first line does.
            parts = title.split(" - ", 1)
            name = parts[1] if len(parts) == 2 else "Fan patch"
            yield {
                "appID": app_id,
                "patch": {
                    "name": name,
                    "kind": "translation",
                    "official": False,
                    "by": ", ".join(p["name"] for p in release.get("producers") or []) or "Fan patch",
                    "source": {"site": "vndb", "page": page, "key": release["id"]},
                    "version": None,
                    "languages": languages,
                    "adult": False,
                    "notes": "Listed on VNDB; the download is on the patch's own page.",
                    "files": [{"host": "page", "url": links[0] if links else page, "name": None, "format": None}],
                },
            }
