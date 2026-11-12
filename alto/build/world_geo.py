"""The Memory Atlas's geography (brief.palace_view "world"): the projection, the regions a memory route sweeps through, and the packaged data.

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

# A country's own flat projection (Art spec notes-art/atlas-country-look.md section 3). The US: Albers equal-area conic, parallels 29.5 / 45.5, with
# Alaska (scale .35) and Hawaii as insets (the same constants as d3's albersUsa, in the world's units: the earth radius is SCALE). Only the flat
# map is projected: the page's JS (palace_world.py: mkUSA) re-projects the SAME Natural Earth tiles with the same constants and un-projects them for the globe,
# so the flat map and the globe draw one geometry. Other countries keep Equal Earth until their projections are built.
_USA = {"M": dict(l0=-96, a=29.5, b=45.5, c=(-96.6, 38.7), s=1.0, o=(0.0, 0.0)),
        "A": dict(l0=-154, a=55, b=65, c=(-156, 58.5), s=.35, o=(-.307, .201)),
        "H": dict(l0=-157, a=8, b=18, c=(-160, 19.9), s=1.0, o=(-.205, .212))}


def _alb(lon, lat, l0, a, b):
    ra, rb = math.radians(a), math.radians(b)
    n = (math.sin(ra) + math.sin(rb)) / 2
    c = math.cos(ra) ** 2 + 2 * n * math.sin(ra)
    r = math.sqrt(c - 2 * n * math.sin(math.radians(lat))) / n
    t = n * math.radians(lon - l0)
    return r * math.sin(t), r * math.cos(t) - math.sqrt(c) / n


def usa_group(lon: float, lat: float) -> str:
    """Which piece of the US map a place stands on: M the lower 48, A Alaska, H Hawaii (as the page's JS tells them apart)."""
    if lat < 25 and -165 < lon < -150:
        return "H"
    if lat > 50 and (-180 < lon < -129 or lon > 165):
        return "A"
    return "M"


def usa_project(lon: float, lat: float, g: str | None = None) -> tuple[float, float]:
    g = g or usa_group(lon, lat)
    P = _USA[g]
    if g != "M":
        lon = P["l0"] + ((lon - P["l0"] + 540) % 360) - 180
    x, y = _alb(lon, lat, P["l0"], P["a"], P["b"])
    cx, cy = _alb(P["c"][0], P["c"][1], P["l0"], P["a"], P["b"])
    return ((x - cx) * P["s"] + P["o"][0]) * SCALE, ((y - cy) * P["s"] + P["o"][1]) * SCALE


# The other eight countries with state data (Art spec section 3): one flat projection each, no insets. "t": alb (Albers equal-area conic), lcc (Lambert conformal conic), merc
# (Mercator); l0 the central meridian, a / b the standard parallels, c the (lon, lat) that sits at the origin, R how far (degrees round c) a neighbour's land is still drawn.
# The page builds the same projection from this dict (palace_world.py mkConic) and un-projects it for the globe.
COUNTRY_PROJ = {
    "AUS": dict(t="alb", l0=134, a=-18, b=-36, c=(134, -25), R=48),
    "BRA": dict(t="alb", l0=-54, a=-2, b=-22, c=(-54, -14), R=48),
    "CAN": dict(t="lcc", l0=-92, a=49, b=77, c=(-92, 63), R=60),
    "CHN": dict(t="alb", l0=105, a=25, b=47, c=(105, 35), R=48),
    "IND": dict(t="alb", l0=82.5, a=13, b=28, c=(82.5, 22), R=40),
    "IDN": dict(t="merc", l0=118, c=(118, -2), R=45),
    "RUS": dict(t="alb", l0=100, a=52, b=64, c=(100, 62), R=70),
    "ZAF": dict(t="alb", l0=25, a=-24.5, b=-33, c=(25, -29), R=40),
}


def _conic_xy(spec: dict, lon: float, lat: float) -> tuple[float, float]:
    """The projection's own plane (radians units, screen y: north is up = negative)."""
    lon = spec["l0"] + ((lon - spec["l0"] + 540) % 360) - 180
    if spec["t"] == "merc":
        return math.radians(lon - spec["l0"]), -math.log(math.tan(math.pi / 4 + math.radians(max(-85.0, min(85.0, lat))) / 2))
    if spec["t"] == "alb":
        return _alb(lon, lat, spec["l0"], spec["a"], spec["b"])
    ra, rb = math.radians(spec["a"]), math.radians(spec["b"])
    n = math.log(math.cos(ra) / math.cos(rb)) / math.log(math.tan(math.pi / 4 + rb / 2) / math.tan(math.pi / 4 + ra / 2))
    f = math.cos(ra) * math.tan(math.pi / 4 + ra / 2) ** n / n
    rho = f / math.tan(math.pi / 4 + math.radians(lat) / 2) ** n
    t = n * math.radians(lon - spec["l0"])
    return rho * math.sin(t), rho * math.cos(t)   # (relative to the cone's apex; the caller takes the centre off)


def _country_fn(cid: str):
    spec = COUNTRY_PROJ[cid]
    cx, cy = _conic_xy(spec, spec["c"][0], spec["c"][1])

    def fn(lon: float, lat: float, g=None) -> tuple[float, float]:
        x, y = _conic_xy(spec, lon, lat)
        return (x - cx) * SCALE, (y - cy) * SCALE
    return fn


ALBERS_LIVE = True   # flipped on only together with the page's JS side (palace_world.py mkUSA); off = every country stays on the Equal Earth map


def country_projection(cid: str):
    """A country's own (lon, lat) -> (x, y) in world units, or None (it stays on the Equal Earth world map)."""
    if cid == "USA" and ALBERS_LIVE:
        return usa_project
    return _country_fn(cid) if cid in COUNTRY_PROJ else None


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
    m = {"base": "", "cont": {}, "a1": {}, "s": {}}
    for name, _ in hosted():
        url = "/" + FOLDER + "/" + name
        stem = name.rsplit("-", 1)[0]
        if stem == "base":
            m["base"] = url
        elif stem.startswith("cont-"):
            m["cont"][stem[5:]] = url
        elif stem.startswith("a1-"):
            m["a1"][stem[3:]] = url
        elif stem.startswith("a1p-"):                 # a country's states as filled shapes (docs/world-palace/build_state_polys.py)
            m["s"][stem[4:]] = url
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
