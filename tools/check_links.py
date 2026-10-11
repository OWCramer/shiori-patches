#!/usr/bin/env python3
"""Checks that every downloadable link still answers, marking patches whose every source is
gone as `dead` (and dead ones that came back as `ok`). Downloads nothing: plain links get a
ranged GET of one byte, MEGA a metadata request, Google Drive a look at the download page."""

import glob
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

from common import BROWSER_AGENT, fetch  # noqa: E402
import download  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def alive(host, url):
    """True, False (gone), or None (couldn't tell: a quota, a timeout)."""
    try:
        if host == "mega":
            link = download.mega_link(url)
            if not link:
                return None
            reply = json.loads(fetch("https://g.api.mega.co.nz/cs?id=0",
                                     data=json.dumps([{"a": "g", "p": link[0]}]).encode(),
                                     headers={"Content-Type": "application/json"}))[0]
            if isinstance(reply, int):
                return False if reply in (-9, -16, -6) else None
            return True
        if host == "wetransfer":
            return bool(download.wetransfer_direct(url))
        if host == "gdrive":
            file_id = download.drive_file_id(url)
            if not file_id:
                return bool(download.drive_folder_files(url)) or None
            url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
        request = urllib.request.Request(url, headers={"User-Agent": BROWSER_AGENT, "Range": "bytes=0-0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status in (200, 206)
    except urllib.error.HTTPError as error:
        return False if error.code in (404, 410) else None
    except download.Unavailable as error:
        return False if error.dead else None
    except Exception:
        return None


def main():
    changed = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "patches", "*.json"))):
        game = json.load(open(path))
        dirty = False
        for patch in game["patches"]:
            if patch["status"] == "unsupported":
                continue
            results = []
            for file in patch["files"]:
                sources = [(file["host"], file["url"])] + [(m["host"], m["url"]) for m in file.get("mirrors", [])]
                checks = [alive(h, u) for h, u in sources if h in ("direct", "gdrive", "mega", "wetransfer")]
                if checks:
                    results.append(True if True in checks else (False if all(c is False for c in checks) else None))
            if not results:
                continue
            status = "dead" if any(r is False for r in results) else ("ok" if all(r is True for r in results) else patch["status"])
            if status != patch["status"]:
                print(f"{game['appID']} {patch['id']}: {patch['status']} -> {status}")
                patch["status"] = status
                dirty = True
        if dirty:
            changed += 1
            open(path, "w").write(json.dumps(game, ensure_ascii=False, indent=2) + "\n")
    print(f"{changed} game files changed")


if __name__ == "__main__":
    main()
