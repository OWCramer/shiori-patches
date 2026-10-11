"""Winged Cloud's "Sakura Patch Collection": a public Patreon post, kept up to date, linking
each Sakura game's official 18+ patch on Winged Cloud's WeTransfer portal. The post's text is
read through Patreon's post API (its `content_json_string`); game names are matched to Steam
app ids like patch.moe's (titles.json)."""

import json

from common import fetch_json
from sources.patchmoe import _titles, app_id_for, TITLES

POST = "https://www.patreon.com/wingedcloud/posts/sakura-patch-37106416"
API = "https://www.patreon.com/api/posts/37106416?fields%5Bpost%5D=title,content_json_string"


def _paragraphs(doc):
    """(text, bold parts, links) per paragraph of Patreon's rich-text document."""
    def walk(node, parts):
        if node.get("type") == "text":
            marks = node.get("marks", [])
            href = next((m["attrs"]["href"] for m in marks if m["type"] == "link"), None)
            parts.append((node["text"], any(m["type"] == "bold" for m in marks), href))
        for child in node.get("content", []):
            walk(child, parts)
    for block in doc.get("content", []):
        parts = []
        walk(block, parts)
        yield parts


def collect():
    data = fetch_json(API, browser=True)
    doc = json.loads(data["data"]["attributes"]["content_json_string"])
    titles = _titles()
    for parts in _paragraphs(doc):
        links = [href for _, _, href in parts if href]
        names = [text.strip() for text, bold, href in parts if bold and not href and text.strip() not in (">>>", "<<<")]
        names = [n for n in names if n and not set(n) <= set("<>")]
        if not links or not names:
            continue
        title = names[0]
        app_id = app_id_for(title, titles)
        if not app_id:
            print(f"Winged Cloud: no Steam match for {title!r}")
            continue
        yield {
            "appID": int(app_id),
            "title": title,
            "patch": {
                "name": "18+ patch",
                "kind": "adult",
                "official": True,
                "by": "Winged Cloud",
                "source": {"site": "wingedcloud", "page": POST, "key": title},
                "version": None,
                "languages": ["en"],
                "adult": True,
                "notes": "Winged Cloud's own patch, from its public Sakura Patch Collection on Patreon.",
                "files": [{"host": "wetransfer", "url": links[0], "name": None, "format": None}],
            },
        }
    with open(TITLES, "w") as file:
        json.dump(dict(sorted(titles.items())), file, ensure_ascii=False, indent=2)
        file.write("\n")
