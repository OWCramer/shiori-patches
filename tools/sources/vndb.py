"""VNDB (api.vndb.org/kana): fan-made patches (translations, restorations) for games on
Steam. VNDB lists the release and its website but not a download, so these entries point to
the patch's page until someone adds the file by hand."""

from common import fetch_json

API = "https://api.vndb.org/kana/release"
LANGUAGE_NAMES = {"zh-Hans": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)"}


def collect(app_ids):
    for app_id in app_ids:
        body = {
            "filters": ["and", ["patch", "=", 1], ["official", "!=", 1],
                        ["vn", "=", ["release", ["extlink", "=", ["steam", app_id]]]]],
            "fields": "id,title,languages.lang,producers.name,released,extlinks.url,extlinks.label,notes,platforms",
            "results": 25,
        }
        try:
            results = fetch_json(API, body=body, delay=1.0).get("results", [])
        except Exception as error:
            print(f"VNDB {app_id}: {error}")
            continue
        for release in results:
            if "win" not in (release.get("platforms") or ["win"]):
                continue
            links = [l["url"] for l in release.get("extlinks") or [] if l.get("url")]
            page = f"https://vndb.org/{release['id']}"
            languages = sorted({l["lang"] for l in release.get("languages") or []}) or ["en"]
            name = release.get("title") or "Fan patch"
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
