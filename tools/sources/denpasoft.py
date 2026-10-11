"""Denpasoft's 18+ and uncensor DLCs, from its public catalog API (denpasoft.com/developers:
documented, keyless, read-only), with denpasoft.json as the copy to fall back to when the API
answers a bot check. Free ones still need a Denpasoft account to claim, so they are `store`
links; Shiori installs them through the player's own Denpasoft sign-in. Game titles are
matched to Steam app ids like patch.moe's (titles.json)."""

import json
import os
import re
import urllib.parse

from common import fetch_json, today
from sources.patchmoe import _titles, app_id_for, TITLES

API = "https://denpasoft.com/api/public/v1/catalog/list?scope=category&category=dlc-18&page={page}&per_page=48"


def _game(name):
    name = re.sub(r"\s*[-–]\s*(18\+ (Adult |Restoration )?DLC|Uncensor DLC|18\+ Restoration DLC|Expansion DLC|DLC)\s*$", "", name.strip())
    return re.sub(r"\s*-\s*18\+\s*DLC$", "", name).strip(" -")


def refresh_from_api():
    """Rewrites denpasoft.json from the API; False when the API can't be reached."""
    products, page, pages = [], 1, 1
    try:
        while page <= pages:
            data = fetch_json(API.format(page=page), delay=1.0)
            pages = data.get("totalPages") or 0
            products += data.get("products") or []
            page += 1
    except Exception as error:
        print(f"Denpasoft API: {error}; using denpasoft.json")
        return False
    if not products:
        return False
    saved = json.load(open(FILE))
    known = {p["slug"]: p for p in saved["products"]}
    rows = []
    for product in products:
        slug = urllib.parse.unquote(product["slug"])
        price = product.get("salePrice") or product.get("regularPrice")
        free = price is not None and float(price) == 0
        row = {"slug": slug, "game": _game(product["name"]), "product": product["name"],
               "price": "Free" if free else f"${float(price):.2f}" if price else "?", "checked": today()}
        if known.get(slug, {}).get("appID"):
            row["appID"] = known[slug]["appID"]
        rows.append(row)
    saved["products"] = rows
    with open(FILE, "w") as file:
        file.write(json.dumps(saved, ensure_ascii=False, indent=2) + "\n")
    return True

FILE = os.path.join(os.path.dirname(__file__), "..", "..", "denpasoft.json")


def collect():
    refresh_from_api()
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
                "name": "18+ DLC" + (" (free on Denpasoft)" if free else f" (Denpasoft, {product['price']})"),
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
