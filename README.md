# Shiori patches

Patches for Steam visual novels, listed by Steam app id, for Shiori: the iOS and iPadOS app that downloads the PC games you own and runs them with native engine runtimes. Shiori shows a game's patches on its page and installs them into the game's `patch/` folder, which it layers over the Steam files (so Remove puts the game back exactly as Steam delivered it).

The list holds links, not patches. Every file stays where its publisher or uploader put it; Shiori downloads it from there and checks it against the SHA-256 recorded here.

## What's in it

One file per game in `patches/<appid>.json`, and `index.json` listing every game with a patch. Each patch says:

- `kind`: `adult` (restores content cut from the Steam release), `translation`, `update`, `restoration`, `voice` or `other`.
- `official`: from the game's publisher, or a community patch.
- `verified`: `false`, or who played the game with the patch in Shiori, when, and on which engine.
- `status`: `ok`, `dead` (the link stopped working) or `unsupported` (a Windows installer, which Shiori can't run).
- `files`: every part of the patch. `host` is how Shiori gets it:
  - `direct`, `gdrive`, `mega` and `wetransfer` download inside Shiori;
  - `steam` is a DLC of the game on Steam;
  - `store` is a shop that sells it, or gives it away (`price` says which; buy or claim it, then use Import Patch);
  - `page` opens in a browser.
  
  `mirrors` lists other places to get the same file.
- `install` (optional): `into` forces the game's own folder (`root`) or Ren'Py's `game/` folder (`game`); `strip` steps into a wrapper folder in the archive.

`schema.json` is the full format.

## Where the entries come from

`tools/update.py` runs every day as a GitHub Action and opens a pull request with what changed:

| Source | What it gives |
| --- | --- |
| [NekoNyan](https://patches.nekonyansoft.com) | Official 18+ patches with Steam app ids and direct downloads. |
| [Saikey Studios](https://saikeystudios.com/patches/) | Official patches with Steam app ids; files from their Google Drive mirrors. |
| [uncensorpat.ch](https://www.uncensorpat.ch) | Community database of uncensor patches per Steam app id: Steam DLCs, shops and download links (often MEGA). |
| [Winged Cloud](https://www.patreon.com/wingedcloud/posts/sakura-patch-37106416) | Official 18+ patches for the Sakura games, from Winged Cloud's public Patreon post, on their WeTransfer portal. |
| [Denpasoft](https://denpasoft.com/category/dlc-18) | Its 18+ and uncensor DLCs, many free with a Denpasoft account; kept by hand in `denpasoft.json` (the site blocks automated reading). Listed as shop links with their price. |
| [patch.moe](https://www.patch.moe) | Publishers' DLC patches, listed by title and matched to Steam app ids (`titles.json` holds the matches, for Winged Cloud too; fix a wrong one there). |
| [VNDB](https://vndb.org) | Fan translations and other fan patches for games with a Steam release; the download link is added by hand. |

The Action records each new file's size and SHA-256 (downloading it once, up to 10 GB a day), and checks every link once a week.

## Adding or fixing a patch

Open a pull request that edits the game's file (or adds one):

```json
{
  "appID": 402180,
  "title": "Sakura Swim Club",
  "patches": [
    {
      "id": "manual-sakura-swim-club-restoration",
      "name": "Restoration patch",
      "kind": "adult",
      "official": false,
      "by": "your-github-name",
      "source": { "site": "manual", "page": "https://example.com/where-you-found-it" },
      "version": "1.0",
      "languages": ["en"],
      "adult": true,
      "branch": null,
      "status": "ok",
      "verified": false,
      "notes": "Anything a player should know.",
      "files": [
        { "host": "mega", "url": "https://mega.nz/file/…#…", "name": null, "size": null, "sha256": null, "format": null }
      ],
      "added": "2026-10-11",
      "checked": "2026-10-11"
    }
  ]
}
```

Leave `size` and `sha256` as `null`; the Action fills them in. If you've played the game with the patch in Shiori, set `verified` to `{ "by": "your-github-name", "date": "…", "engine": "renpy" }`.

The list is dedicated to the public domain under [CC0 1.0](LICENSE): by contributing you agree to the same. The patches themselves belong to their makers.
