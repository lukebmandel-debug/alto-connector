"""The World Palace's geography (brief.palace_view "world"): the projection, the regions a memory route sweeps through, and the packaged data.

Data lives in alto/assets/world/ (docs/world-palace/build_world_geo.py makes it from Natural Earth, public domain):
  gazetteer.json.gz   read here, at set-up and build time only: countries (names, subregion, continent, label point, capital) and populated places
  base / cont-* / a1-*  served from the site's /world/ folder (hosted(), palace_assets.py) and fetched by the page's renderer (palace_world.py)

World units: Equal Earth, the globe 2000 wide (x -1000..1000 west to east), y down (north is negative), centred on 0° / 0°.
"""
from __future__ import annotations

import functools
import gzip
import hashlib
import json
import math
import os
import re

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "world")
FOLDER = "world"

# Equal Earth (Šavrič, Patterson & Jenny 2018)
_A1, _A2, _A3, _A4 = 1.340264, -0.081106, 0.000893, 0.003796
_M = math.sqrt(3) / 2
SCALE = 1000 / (math.pi / (_M * _A1))

# The order a memory route takes the regions in (Natural Earth SUBREGION): round the world from the Americas eastward, never doubling back.
SUBREGIONS = ("Northern America", "Central America", "Caribbean", "South America",
              "Western Europe", "Northern Europe", "Southern Europe", "Eastern Europe",
              "Northern Africa", "Western Africa", "Middle Africa", "Eastern Africa", "Southern Africa",
              "Western Asia", "Central Asia", "Southern Asia", "Eastern Asia", "South-Eastern Asia",
              "Australia and New Zealand", "Melanesia", "Micronesia", "Polynesia")
# The regions a memory route gives its units, in the order it takes them (round the world from the Americas eastward, never doubling back): each a
# few Natural Earth subregions, big enough for a unit's concepts (Luke: "Unit 1 North America, Unit 2 Western Europe …").
REGIONS = (("North America", ("Northern America", "Central America", "Caribbean")),
           ("South America", ("South America",)),
           ("Western Europe", ("Western Europe", "Northern Europe")),
           ("Southern Europe", ("Southern Europe",)),
           ("Eastern Europe", ("Eastern Europe",)),
           ("North Africa and the Middle East", ("Northern Africa", "Western Asia")),
           ("West and Central Africa", ("Western Africa", "Middle Africa")),
           ("East and Southern Africa", ("Eastern Africa", "Southern Africa")),
           ("South and Central Asia", ("Southern Asia", "Central Asia")),
           ("East and Southeast Asia", ("Eastern Asia", "South-Eastern Asia")),
           ("Oceania", ("Australia and New Zealand", "Melanesia", "Micronesia", "Polynesia")))
# other words for them
REGION_WORDS = {"americas": "North America", "latin america": "South America", "central america": "North America", "caribbean": "North America",
                "europe": "Western Europe", "northern europe": "Western Europe", "scandinavia": "Western Europe", "central europe": "Eastern Europe",
                "middle east": "North Africa and the Middle East", "north africa": "North Africa and the Middle East", "west africa": "West and Central Africa",
                "central africa": "West and Central Africa", "africa": "East and Southern Africa", "east africa": "East and Southern Africa",
                "southern africa": "East and Southern Africa", "south asia": "South and Central Asia", "central asia": "South and Central Asia",
                "asia": "East and Southeast Asia", "east asia": "East and Southeast Asia", "southeast asia": "East and Southeast Asia",
                "australia": "Oceania", "pacific": "Oceania"}


def project(lon: float, lat: float) -> tuple[float, float]:
    """(x, y) in world units for a longitude / latitude in degrees."""
    lam, phi = math.radians(max(-180.0, min(180.0, lon))), math.radians(max(-90.0, min(90.0, lat)))
    th = math.asin(_M * math.sin(phi))
    t2 = th * th
    t6 = t2 * t2 * t2
    x = lam * math.cos(th) / (_M * (_A1 + 3 * _A2 * t2 + t6 * (7 * _A3 + 9 * _A4 * t2)))
    y = th * (_A1 + _A2 * t2 + t6 * (_A3 + _A4 * t2))
    return (x * SCALE, -y * SCALE)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "other"


def norm(s: str) -> str:
    """A name folded for matching: lower case, accents and punctuation gone, 'the' / 'st.' forms evened out."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"\bst\.?\s", "saint ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"^the ", "", s)


@functools.lru_cache(maxsize=1)
def gazetteer() -> dict:
    with gzip.open(os.path.join(DIR, "gazetteer.json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def hosted() -> tuple:
    """((file name under /world/, JSON text), ...) — the hosted tiers, each named by its content hash: base-<h>.json, cont-<continent>-<h>.json,
    a1-<ISO3>-<h>.json."""
    out = []
    for name in sorted(os.listdir(DIR)):
        if not name.endswith(".json.gz") or name.startswith("gazetteer"):
            continue
        with gzip.open(os.path.join(DIR, name), "rt", encoding="utf-8") as f:
            text = f.read()
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
        out.append((name[:-len(".json.gz")] + "-" + h + ".json", text))
    return tuple(out)


def manifest() -> dict:
    """{"base": url, "cont": {slug: url}, "a1": {ISO3: url}} of the hosted tiers (palace_world.py builds it into its script)."""
    m = {"base": "", "cont": {}, "a1": {}}
    for name, _ in hosted():
        url = "/" + FOLDER + "/" + name
        stem = name.rsplit("-", 1)[0]
        if stem == "base":
            m["base"] = url
        elif stem.startswith("cont-"):
            m["cont"][stem[5:]] = url
        elif stem.startswith("a1-"):
            m["a1"][stem[3:]] = url
    return m


@functools.lru_cache(maxsize=1)
def continent_boxes() -> dict:
    """{continent slug: [x0, y0, x1, y1]} in world units (the renderer fetches a continent's detail when the view meets its box)."""
    out = {}
    for name, text in hosted():
        stem = name.rsplit("-", 1)[0]
        if stem.startswith("cont-"):
            out[stem[5:]] = json.loads(text)["bb"]
    return out
