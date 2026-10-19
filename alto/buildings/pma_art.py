"""The Philadelphia Museum of Art plan's hosted artwork images: a handful of small public-domain reproductions under /bart/ (content-hash named, immutable).

The files are in alto/assets/bldg/pma/ and described, with their licence and credit, in pma_art.json (the manifest). `files()` is what publish_static writes into the site
(like the ride's textures, palace_ride_gfx.tex_files); `manifest()` adds each image's hosted URL. Nothing here is fetched at run time.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ART_DIR = Path(__file__).resolve().parent.parent / "assets" / "bldg" / "pma"
MANIFEST = Path(__file__).resolve().parent / "pma_art.json"
ART_FOLDER = "bart"
ART_RE = re.compile(r"^[a-z0-9-]{1,40}-[0-9a-f]{10}\.jpg$")


def _raw() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def published_name(stem: str, data: bytes) -> str:
    return f"pma-{stem}-" + hashlib.sha256(data).hexdigest()[:10] + ".jpg"


def files() -> list:
    """[(published name, bytes)] of every image whose file exists."""
    out = []
    for key, im in _raw()["images"].items():
        p = ART_DIR / im["file"]
        if p.is_file():
            b = p.read_bytes()
            out.append((published_name(key, b), b))
    return out


def manifest() -> dict:
    """The manifest with each image's hosted `url` ("/bart/<name>") and `bytes`; images whose file is missing are left out."""
    m = _raw()
    imgs = {}
    for key, im in m["images"].items():
        p = ART_DIR / im["file"]
        if not p.is_file():
            continue
        b = p.read_bytes()
        name = published_name(key, b)
        imgs[key] = {**im, "name": name, "url": f"/{ART_FOLDER}/{name}", "bytes": len(b)}
    return {**m, "images": imgs}
