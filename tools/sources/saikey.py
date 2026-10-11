"""Saikey Studios: its public patch JSON lists each product with the Steam app id of every
patch and a Google Drive mirror. (The site's own download goes through its launcher.)"""

import html

from common import fetch_json, host_of

API = "https://saikeystudios.com/sk-json/saikey/v1/patches/en/{page}/"
PAGE = "https://saikeystudios.com/patches/"


def _name(product, link):
    title = html.unescape(product.get("title") or "")
    steam_links = [l for l in product.get("direct_patch_links") or [] if l.get("platform") == "Steam"]
    language = link.get("displayName") or link.get("language") or ""
    if len(steam_links) > 1 and language and language != "All Languages":
        return f"{title} patch ({language})"
    return f"{title} patch"


def collect():
    seen = set()
    for page in range(0, 40):
        items = fetch_json(API.format(page=page), browser=True)
        if not items:
            break
        fresh = 0
        for product in items:
            if product.get("is_unreleased") or product.get("is_upcoming"):
                continue
            for link in product.get("direct_patch_links") or []:
                source = link.get("source") or {}
                if link.get("platform") != "Steam" or source.get("kind") != "steam" or not source.get("appId"):
                    continue
                key = link.get("url") or f"{product['id']}-{source['appId']}"
                if key in seen:
                    continue
                seen.add(key)
                fresh += 1
                mirror = link.get("mirror") or ""
                page_url = link.get("url") or product.get("product_url") or PAGE
                if mirror:
                    file = {"host": host_of(mirror), "url": mirror, "name": None, "format": None,
                            "mirrors": [{"host": "page", "url": page_url}]}
                else:
                    file = {"host": "page", "url": page_url, "name": None, "format": None}
                yield {
                    "appID": int(source["appId"]),
                    "title": html.unescape(product.get("title") or ""),
                    "patch": {
                        "name": _name(product, link),
                        "kind": "adult",
                        "official": True,
                        "by": "Saikey Studios",
                        "source": {"site": "saikey", "page": product.get("product_url") or PAGE, "key": key},
                        "version": None,
                        "languages": link.get("contentLanguages") or ["en"],
                        "adult": True,
                        "files": [file],
                    },
                }
        if fresh == 0 and page > 0:
            break
