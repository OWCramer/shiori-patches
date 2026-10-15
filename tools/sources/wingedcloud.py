"""Winged Cloud's "Sakura Patch Collection": a public Patreon post linking each Sakura game's
official 18+ patch on Winged Cloud's WeTransfer portal. Patreon's robots.txt keeps automated
readers off its API (/api/) and its pages answer with a bot check, so the post is copied by
hand into wingedcloud.json; this reads that file. Winged Cloud's later games, which have a
post each instead, come from uncensorpat.ch, which links those posts."""

import json
import os

FILE = os.path.join(os.path.dirname(__file__), "..", "..", "wingedcloud.json")


def collect():
    data = json.load(open(FILE))
    for row in data["patches"]:
        yield {
            "appID": int(row["appID"]),
            "title": row["game"],
            "patch": {
                "name": "18+ patch",
                "kind": "adult",
                "official": True,
                "by": "Winged Cloud",
                "source": {"site": "wingedcloud", "page": row.get("post") or data["post"], "key": row["game"]},
                "version": None,
                "languages": ["en"],
                "adult": True,
                "notes": "Winged Cloud's own patch, from its public Sakura Patch Collection on Patreon.",
                "files": [{"host": "wetransfer", "url": row["url"], "name": None, "format": None}],
            },
        }
