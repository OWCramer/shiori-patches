"""Downloads a patch file from a plain link, Google Drive or MEGA, as Shiori does, so the
updater can record its size and SHA-256 and see what the archive holds."""

import base64
import hashlib
import html as htmllib
import json
import re
import struct
import subprocess
import tempfile
import urllib.parse
import urllib.request

from common import BROWSER_AGENT, fetch, fetch_text

CHUNK = 1 << 20


class Unavailable(Exception):
    """The link is gone (or over its quota); `dead` says whether it's gone for good."""

    def __init__(self, message, dead=True):
        super().__init__(message)
        self.dead = dead


def _open(url, headers=None):
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_AGENT, **(headers or {})})
    try:
        return urllib.request.urlopen(request, timeout=120)
    except urllib.error.HTTPError as error:
        raise Unavailable(f"HTTP {error.code}", dead=error.code in (403, 404, 410)) from error


def _name_from(response, url):
    disposition = response.headers.get("Content-Disposition") or ""
    match = re.search(r"filename\*=UTF-8''([^;]+)", disposition) or re.search(r'filename="?([^";]+)"?', disposition)
    if match:
        return urllib.parse.unquote(match.group(1)).strip()
    return urllib.parse.unquote(urllib.parse.urlsplit(response.geturl() or url).path.rsplit("/", 1)[-1]) or None


# Google Drive

def drive_file_id(url):
    match = re.search(r"/file/d/([\w-]+)", url) or re.search(r"[?&]id=([\w-]+)", url)
    return match.group(1) if match else None


def drive_folder_files(url):
    """(id, name) of each file in a shared Drive folder."""
    match = re.search(r"/folders/([\w-]+)", url) or re.search(r"[?&]id=([\w-]+)", url)
    if not match:
        return []
    html = fetch_text(f"https://drive.google.com/embeddedfolderview?id={match.group(1)}", browser=True)
    files = re.findall(r'href="https://drive\.google\.com/file/d/([\w-]+)/view[^"]*".*?<div class="flip-entry-title">([^<]+)<', html, re.S)
    return [(file_id, htmllib.unescape(name).strip()) for file_id, name in files]


def _drive_response(file_id):
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    response = _open(url)
    if "text/html" in (response.headers.get("Content-Type") or ""):
        page = response.read().decode("utf-8", errors="replace")
        form = re.search(r'<form[^>]+action="([^"]+)"(.*?)</form>', page, re.S)
        if not form:
            raise Unavailable("Google Drive returned a page instead of the file", dead="not found" in page.lower())
        fields = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', form.group(2)))
        response = _open(htmllib.unescape(form.group(1)) + "?" + urllib.parse.urlencode(fields))
        if "text/html" in (response.headers.get("Content-Type") or ""):
            raise Unavailable("Google Drive refused the download (quota or permissions)", dead=False)
    return response


# MEGA

def _b64(text):
    text = text.replace("-", "+").replace("_", "/").replace(",", "")
    return base64.b64decode(text + "=" * (-len(text) % 4))


def mega_link(url):
    """(file id, key) from mega.nz/file/ID#KEY or mega.nz/#!ID!KEY; None for folders."""
    match = re.search(r"mega\.(?:co\.)?nz/file/([\w-]+)#([\w-]+)", url) or re.search(r"mega\.(?:co\.)?nz/#!([\w-]+)!([\w-]+)", url)
    return (match.group(1), match.group(2)) if match else None


def _mega(url):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    link = mega_link(url)
    if not link:
        raise Unavailable("MEGA folder links aren't supported yet", dead=False)
    file_id, key_text = link
    key = struct.unpack(">8I", _b64(key_text))
    aes_key = struct.pack(">4I", key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
    iv = struct.pack(">4I", key[4], key[5], 0, 0)
    reply = json.loads(fetch("https://g.api.mega.co.nz/cs?id=0",
                             data=json.dumps([{"a": "g", "g": 1, "ssl": 2, "p": file_id}]).encode(),
                             headers={"Content-Type": "application/json"}))[0]
    if isinstance(reply, int):
        raise Unavailable(f"MEGA error {reply}", dead=reply in (-9, -16, -6))
    attributes = Cipher(algorithms.AES(aes_key), modes.CBC(b"\0" * 16)).decryptor().update(_b64(reply["at"]))
    name = None
    if attributes.startswith(b"MEGA{"):
        name = json.loads(attributes[4:].rstrip(b"\0").decode("utf-8", errors="replace")).get("n")
    response = _open(reply["g"])
    decryptor = Cipher(algorithms.AES(aes_key), modes.CTR(iv)).decryptor()
    return response, name, reply.get("s"), decryptor.update


# WeTransfer

def wetransfer_link(url):
    """(transfer id, security hash) of a WeTransfer link, following we.tl short links."""
    if "we.tl/" in url:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": BROWSER_AGENT})
        try:
            url = urllib.request.urlopen(request, timeout=60).geturl()
        except urllib.error.HTTPError as error:
            raise Unavailable(f"HTTP {error.code}") from error
    match = re.search(r"/downloads/([0-9a-f]+)/(?:[0-9a-f]+/)?([0-9a-f]+)", url)
    return (match.group(1), match.group(2)) if match else None


def wetransfer_direct(url):
    link = wetransfer_link(url)
    if not link:
        raise Unavailable("not a WeTransfer download link", dead=False)
    try:
        reply = json.loads(fetch(f"https://wetransfer.com/api/v4/transfers/{link[0]}/download",
                                 data=json.dumps({"security_hash": link[1], "intent": "entire_transfer"}).encode(),
                                 headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                                 browser=True))
    except urllib.error.HTTPError as error:
        raise Unavailable(f"WeTransfer HTTP {error.code}", dead=error.code in (404, 410)) from error
    if not reply.get("direct_link"):
        raise Unavailable("WeTransfer gave no download (the transfer may have expired)")
    return reply["direct_link"]


def open_file(host, url):
    """(byte stream, file name, size or None, transform) for a downloadable file."""
    if host == "direct":
        response = _open(url)
        size = response.headers.get("Content-Length")
        return response, _name_from(response, url), int(size) if size else None, None
    if host == "gdrive":
        file_id = drive_file_id(url)
        if not file_id:
            raise Unavailable("Google Drive folder", dead=False)
        response = _drive_response(file_id)
        size = response.headers.get("Content-Length")
        return response, _name_from(response, url), int(size) if size else None, None
    if host == "mega":
        return _mega(url)
    if host == "wetransfer":
        direct = wetransfer_direct(url)
        response = _open(direct)
        size = response.headers.get("Content-Length")
        return response, _name_from(response, direct), int(size) if size else None, None
    raise Unavailable(f"{host} links aren't downloadable", dead=False)


def inspect(host, url, limit=None):
    """Downloads the file into a temporary file and returns its name, size, SHA-256 and
    archive listing (None when bsdtar can't read it)."""
    stream, name, size, transform = open_file(host, url)
    if limit and size and size > limit:
        stream.close()
        raise Unavailable(f"{size} bytes is over this run's limit", dead=False)
    digest = hashlib.sha256()
    total = 0
    with tempfile.NamedTemporaryFile(suffix="-" + re.sub(r"[^\w.]", "_", name or "patch")) as temp:
        with stream:
            while True:
                chunk = stream.read(CHUNK)
                if not chunk:
                    break
                if transform:
                    chunk = transform(chunk)
                digest.update(chunk)
                temp.write(chunk)
                total += len(chunk)
        temp.flush()
        if total < 4096:
            # Error pages, "file not found" notes and redirects to a login aren't patches.
            temp.seek(0)
            head = temp.read(4096).lower()
            if total == 0 or b"<html" in head or b"<!doctype" in head or (name or "").lower().endswith((".html", ".htm")):
                raise Unavailable(f"the link gave a {total}-byte page, not a file", dead=False)
        listing = subprocess.run(["bsdtar", "-tf", temp.name], capture_output=True, text=True)
        entries = listing.stdout.splitlines() if listing.returncode == 0 else None
    return {"name": name, "size": total, "sha256": digest.hexdigest(), "entries": entries}
