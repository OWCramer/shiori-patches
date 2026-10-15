# Shiori patches

Patches for Steam visual novels, listed by Steam app id, for Shiori: the iOS and iPadOS app that downloads the PC games you own and runs them with native engine runtimes. Shiori shows a game's patches on its page and installs them into the game's `patch/` folder, which it layers over the Steam files (so Remove puts the game back exactly as Steam delivered it).

The list holds links, not patches. Every file stays where its publisher or uploader put it; Shiori downloads it from there and checks it against the SHA-256 recorded here.

## What's in it

One file per game in `patches/<appid>.json`, and `index.json` listing every game with a patch. Each patch says:

- `kind`: `adult` (restores content cut from the Steam release), `translation`, `update`, `restoration`, `voice` or `other`.
- `official`: from the game's publisher, or a community patch.
- `verified`: `false`, or who played the game with the patch in Shiori, when, and on which engine.
- `source`: the page the entry was read from (`page`: the publisher's patch page, the VNDB release, the uncensorpat.ch page), and, when that page names one, where it got the patch (`origin`: the publisher's post, the translator's site). Shiori links both.
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
| [Kagami Games](https://patches.kagamied.com) | Official Steam patches from the publisher's patch page (its `patches.json`), direct downloads with Google Drive mirrors; titles matched like patch.moe's. |
| [Eroge Japan](https://erogejapan.com/patch/) | Official R18 patches from the publisher's own patch pages (found through its sitemap), one per language, with their MEGA and MediaFire mirrors; each game's Steam app id from its game page. The links are read again every day, as the site moves its files. For a game it lists, uncensorpat.ch's and VNDB's copies of its patches are left out. |
| [uncensorpat.ch](https://www.uncensorpat.ch) | Community database of uncensor patches per Steam app id: Steam DLCs, shops and download links (often MEGA). |
| [Winged Cloud](https://www.patreon.com/wingedcloud/posts/sakura-patch-37106416) | Official 18+ patches for the Sakura games, from Winged Cloud's public Patreon post, on their WeTransfer portal. Patreon's robots.txt closes its API to automated readers, so the post is copied by hand into `wingedcloud.json`; Winged Cloud's later games come through uncensorpat.ch, which links each one's Patreon post. |
| [sakura-patcher](https://github.com/gan-of-culture/sakura-patcher) | An open-source installer for Winged Cloud's Sakura patches; its list of the official WeTransfer links fills in the Sakura games neither `wingedcloud.json` nor uncensorpat.ch has. Listed as Winged Cloud's patches, credited "via sakura-patcher". The tool has no licence, so only facts are taken from it (titles, the publisher's links), never its code. |
| [Denpasoft](https://denpasoft.com/category/dlc-18) | Its 18+ and uncensor DLCs, many free with a Denpasoft account; kept by hand in `denpasoft.json` (the site blocks automated reading). Listed as shop links with their price. |
| [patch.moe](https://www.patch.moe) | Publishers' DLC patches, listed by title and matched to Steam app ids (`titles.json` holds the matches, for Winged Cloud too; fix a wrong one there). |
| [VNDB](https://vndb.org) | Fan translations and other fan patches for games with a Steam release: English ones, and any language for a game written in English (they translate the Steam release). Official patches too, for games no publisher source above covers. The download link is added by hand. Publishers' 18+ patches sold or given away as Steam DLC come from VNDB's official patch releases, matched to their game through Steam (`steam-dlc.json` keeps each DLC's game). |

The Action records each new file's size and SHA-256 (downloading it once, up to 10 GB a day), and checks every link once a week. While its pull request waits for review, each day's run adds to it instead of opening another, so the hashing carries over. An entry's `checked` date moves when its site changes it, or once a week.

The tools read only what each site leaves open to automated readers (robots.txt and terms), slowly, and list only downloads the publisher or the patch's maker offers publicly.

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
