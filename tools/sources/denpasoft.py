"""Denpasoft's 18+ and uncensor DLCs, from denpasoft.json (kept by hand: the site answers
automated requests with a bot check). Free ones need a Denpasoft account to claim, so they
are `store` links Shiori opens; the player then uses Import Patch. Game titles are matched
to Steam app ids like patch.moe's (titles.json)."""

import json
import os

from sources.patchmoe import _titles, app_id_for, TITLES

FILE = os.path.join(os.path.dirname(__file__), "..", "..", "denpasoft.json")


def collect():
    titles = _titles()
    for product in json.load(open(FILE))["products"]:
        app_id = product.get("appID") or app_id_for(product["game"], titles)
        if not app_id:
            print(f"Denpasoft: no Steam match for {product['game']!r}")
            continue
        url = f"https://denpasoft.com/product/{product['slug']}"
        free = product["price"].lower() == "free"
        yield {
            "appID": int(app_id),
            "title": product["game"],
            "patch": {
                "name": "18+ DLC" + (" (free on Denpasoft)" if free else " (Denpasoft)"),
                "kind": "adult",
                "official": True,
                "by": "Denpasoft",
                "source": {"site": "denpasoft", "page": url, "key": product["slug"]},
                "version": None,
                "languages": ["en"],
                "adult": True,
                "notes": ("Free with a Denpasoft account: claim it on the page, download it, then use Import in Shiori."
                          if free else "Sold by Denpasoft; after buying, download it and use Import in Shiori."),
                "files": [{"host": "store", "url": url, "name": None, "format": None, "price": product["price"]}],
            },
        }
    with open(TITLES, "w") as file:
        json.dump(dict(sorted(titles.items())), file, ensure_ascii=False, indent=2)
        file.write("\n")
