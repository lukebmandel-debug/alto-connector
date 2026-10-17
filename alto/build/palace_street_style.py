"""Per-city building style for the street blob (palace_street.py): what a building is made of when OpenStreetMap does not say.

OSM tags are sparse (Philadelphia: building:colour 0.05%, building:material 0.9%, building:levels 8%, height 82%), so a preset fills the gaps from the height, the
footprint, the age (start_date), the kind of building and a hash of its OSM id (the same building always gets the same look; a street of row houses is varied, not
uniform). An OSM value ALWAYS wins. Output per building: rgb565 colour, material code (MATERIALS), roof colour, levels, storefront flag, flags (FL_*).

  preset_for(bbox)   -> "philadelphia" when the box lies in the Philadelphia area, else "generic"
  resolve(preset, tags, area_m2, height_m, levels, seed, commercial) -> {"bc","bm","rc","lv","h","fl"}
"""
from __future__ import annotations

import zlib

from .. import palace_map as pmap

MATERIALS = ["", "brick", "stone", "stucco", "painted", "concrete", "glass", "metal", "wood", "brownstone", "cladding", "tile", "plaster"]
MAT = {m: i for i, m in enumerate(MATERIALS) if m}
_OSM_MAT = {"brick": "brick", "bricks": "brick", "stone": "stone", "sandstone": "brownstone", "limestone": "stone", "granite": "stone", "marble": "stone", "stucco": "stucco",
            "plaster": "plaster", "render": "stucco", "concrete": "concrete", "cement_block": "concrete", "glass": "glass", "metal": "metal", "steel": "metal", "aluminium": "metal",
            "wood": "wood", "timber_framing": "wood", "tile": "tile", "painted": "painted", "paint": "painted", "vinyl": "cladding", "cladding": "cladding"}
FL_STOREFRONT = 1          # shop windows on the ground floor
FL_STYLED = 2              # colour / material were inferred (not from OSM)
FL_LEVELS = 4              # levels were inferred
FL_HEIGHT = 8              # height was inferred
FL_OLD = 16                # built before 1900 (or an old district's row house)

_ROW = {"house", "terrace", "terraced", "semidetached_house", "detached", "residential", "row_house", "townhouse", "yes", "apartments", "dormitory"}
_CIVIC = {"cathedral", "church", "chapel", "synagogue", "mosque", "temple", "hospital", "university", "college", "school", "government", "civic", "public", "museum",
          "train_station", "courthouse", "stadium", "library", "fire_station", "kindergarten"}
_COMMERCIAL = {"retail", "commercial", "supermarket", "kiosk", "shop", "mixed_use"}
_INDUSTRIAL = {"industrial", "warehouse", "factory", "manufacture", "garage", "garages", "shed", "service", "hangar", "storage_tank", "roof", "hut", "carport"}

# (weight, (r, g, b)) palettes
PHILLY_BRICK = [(5, (150, 70, 55)), (4, (165, 85, 62)), (3, (128, 58, 48)), (3, (140, 98, 78)), (2, (176, 110, 80)), (2, (110, 60, 52)), (1, (190, 130, 100))]
BROWNSTONE = [(3, (112, 78, 64)), (2, (130, 92, 74)), (1, (96, 70, 62))]
STUCCO = [(3, (216, 204, 180)), (2, (200, 188, 160)), (2, (225, 215, 198)), (1, (190, 170, 140))]
PAINTED = [(2, (204, 214, 220)), (2, (214, 190, 170)), (2, (176, 190, 170)), (1, (230, 226, 210)), (1, (180, 150, 130))]
STONE_OLD = [(3, (186, 178, 160)), (2, (160, 152, 140)), (2, (200, 194, 178)), (1, (140, 134, 126))]
GLASS = [(3, (120, 156, 176)), (2, (96, 132, 150)), (2, (150, 176, 190)), (1, (70, 96, 110))]
METAL = [(2, (150, 156, 162)), (1, (120, 126, 132)), (1, (176, 180, 184))]
CONCRETE = [(3, (170, 168, 162)), (2, (150, 148, 144)), (1, (190, 186, 178))]
DARK_BRICK = [(3, (112, 64, 54)), (2, (96, 58, 52)), (1, (130, 84, 70))]
ROOF = [(3, (90, 88, 86)), (2, (70, 68, 66)), (2, (110, 100, 94)), (1, (140, 80, 60))]


def rgb565(rgb) -> int:
    r, g, b = rgb
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def rgb565_to_hex(v: int) -> str:
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return "#%02x%02x%02x" % ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def colour565(v) -> int:
    """rgb565 of an OSM colour value ('#aabbcc' or a CSS name), 0 when it cannot be read. (0 is also pure black, which no building is.)"""
    h = pmap._colour(v)
    return rgb565((int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))) if h else 0


def _pick(pal, seed):
    tot = sum(w for w, _c in pal)
    k = seed % tot
    for w, c in pal:
        if k < w:
            return c
        k -= w
    return pal[-1][1]


def seed_of(key) -> int:
    return zlib.crc32(str(key).encode("utf-8")) & 0xFFFFFFFF


def preset_for(bbox) -> str:
    s, w, n, e = (float(v) for v in bbox)
    la, lo = (s + n) / 2, (w + e) / 2
    return "philadelphia" if 39.80 <= la <= 40.20 and -75.45 <= lo <= -74.85 else "generic"


def year_of(v):
    import re
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})", str(v or ""))
    return int(m.group(1)) if m else None


def resolve(preset: str, tags: dict, area_m2: float, height_m: float, levels: int, seed: int, commercial: bool = False) -> dict:
    """The look of one building. `height_m` / `levels` are the OSM values (0 when missing); the result's h (metres, 0 = keep OSM's) and lv are filled in when both are
    missing. `commercial`: a shop / amenity / POI stands inside the footprint (storefront on the ground floor)."""
    t = tags or {}
    kind = str(t.get("building") or t.get("building:part") or "yes")
    year = year_of(t.get("start_date"))
    fl = 0
    philly = preset == "philadelphia"

    # levels and height
    lv, hm = levels, height_m
    if not lv and not hm:
        if kind in _INDUSTRIAL:
            lv = 1 if area_m2 < 400 else 2
        elif kind in _CIVIC:
            lv = 3 if area_m2 > 600 else 2
        elif area_m2 < 60:
            lv = 2 if kind in _ROW else 1
        elif area_m2 < 200:
            lv = 3 if philly else 2
        elif area_m2 < 800:
            lv = 4 if kind in ("apartments", "commercial", "retail", "office") else 3
        else:
            lv = 5
        hm = round(lv * 3.2 + (1.0 if lv > 1 else 0.0), 1)
        fl |= FL_LEVELS | FL_HEIGHT
    elif not lv:
        lv = max(1, int(round(hm / 3.3)))
        fl |= FL_LEVELS
    elif not hm:
        hm = round(lv * 3.3, 1)
        fl |= FL_HEIGHT
    tall = hm >= 40 or lv >= 12
    old = (year is not None and year < 1900) or (year is None and philly and kind in _ROW and area_m2 < 220 and hm < 16)
    if old:
        fl |= FL_OLD

    # material and colour: OSM first
    mat_osm = _OSM_MAT.get(str(t.get("building:material") or "").strip().lower().replace(" ", "_"), "")
    col = colour565(t.get("building:colour"))
    mat, rgb = mat_osm, None
    r = seed % 100
    if not mat or not col:
        if tall:
            if year is not None and year < 1950:
                m_, pal = "stone", STONE_OLD
            elif r < 55:
                m_, pal = "glass", GLASS
            elif r < 80:
                m_, pal = "metal", METAL
            else:
                m_, pal = "concrete", CONCRETE
        elif kind in _CIVIC or (t.get("name") and area_m2 > 700 and kind not in _ROW):
            m_, pal = ("stone", STONE_OLD) if r < 70 else ("brick", PHILLY_BRICK)
        elif kind in _INDUSTRIAL:
            m_, pal = ("brick", DARK_BRICK) if r < 60 else (("metal", METAL) if r < 85 else ("concrete", CONCRETE))
        elif philly and kind in _ROW and area_m2 < 400 and hm < 24:
            if r < 74:
                m_, pal = "brick", PHILLY_BRICK
            elif r < 84:
                m_, pal = "brownstone", BROWNSTONE
            elif r < 92:
                m_, pal = "stucco", STUCCO
            else:
                m_, pal = "painted", PAINTED
        elif kind in _COMMERCIAL or commercial:
            m_, pal = ("brick", PHILLY_BRICK) if r < 40 else (("painted", PAINTED) if r < 70 else (("stucco", STUCCO) if r < 85 else ("concrete", CONCRETE)))
        else:
            m_, pal = ("brick", PHILLY_BRICK) if (philly and r < 55) else (("stucco", STUCCO) if r < 75 else (("concrete", CONCRETE) if r < 90 else ("painted", PAINTED)))
        if not mat:
            mat = m_
        rgb = _pick(pal, (seed >> 8) & 0xFFFF)
        if mat_osm and mat != m_:                                # OSM's material, the preset's palette for it
            rgb = _pick({"brick": PHILLY_BRICK, "stone": STONE_OLD, "brownstone": BROWNSTONE, "stucco": STUCCO, "plaster": STUCCO, "painted": PAINTED, "concrete": CONCRETE,
                         "glass": GLASS, "metal": METAL}.get(mat, CONCRETE), (seed >> 8) & 0xFFFF)
        fl |= FL_STYLED if (not mat_osm or not col) else 0
    out_col = col or (rgb565(rgb) if rgb else 0)

    rc = colour565(t.get("roof:colour")) or rgb565(_pick(ROOF, (seed >> 4) & 0xFFFF))

    # storefront: shop windows on the ground floor of a commercial building, or any building with a shop / amenity inside
    if commercial or kind in _COMMERCIAL or any(t.get(k) for k in ("shop", "amenity", "office", "craft")) and t.get("amenity") not in ("parking", "shelter", "bench"):
        if not tall or commercial:
            fl |= FL_STOREFRONT
    return {"bc": out_col, "bm": MAT.get(mat, 0), "rc": rc, "lv": lv, "h": hm, "fl": fl}
