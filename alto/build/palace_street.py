"""Street-level data of any city for the first-person view (2.0.0): HOSTED, content-hashed, SHARDED files, never part of the page.

The private palace page is within ~15 KB of its 1,000,000 byte cap, so the real street scene (building materials, roofs, shop fronts, doors, street trees, lamps,
benches, lane widths, parks, fences ...) is read from OpenStreetMap at build time and written to site/street/ (palace_assets.py registers and publishes it, the hosting
headers keep it for a year, Firebase Hosting gzips it). The page holds only  m["street"] = {"h": "<12 hex>"}  (the manifest's hash, 41 bytes of JSON).

FILES (plain JSON, compact)
  /street/palace-street-<h12>.json   the MANIFEST (h12 = first 12 hex of the sha256 of its text)
  /street/s-<h8>.json                one SHARD per 2 x 2 cells (1000 m square), named by the hash of its own text, so a client loads only the files near it
MANIFEST
  v 2, a "© OpenStreetMap contributors, ODbL", o [south, west, north, east] (the box in degrees; the origin of every coordinate is (south, west)), q 0.1 (metres per unit),
  cs 5000 (cell size in units = 500 m), kx (metres per degree of longitude, cos(mid latitude)*111320), ky 110574 — the SAME equirectangular frame as palace_map.project:
  X_m = (lon-west)*kx, Y_m = (lat-south)*ky; Y grows NORTH here, the palace map's y grows south (y_map = (north-lat)*ky, = _palStreet.toMap), n [nx, ny] cells, g 2 (cells per shard
  side), preset ("philadelphia" | "generic": the style preset used), f {shard id: bytes}, c {"ix,iy": shard id} (non-empty cells only).
SHARD   {"S": [string table, "" first], "c": {"ix,iy": cell}} — its own string table, every string below is an index into it (0 = none).
CELL    (ix, iy) covers units [ix*cs, (ix+1)*cs) east and [iy*cs, ...) north. A feature lives in the cell of its first point (buildings and areas: centroid) and is NOT cut, so a
        client asks the cell AND its 8 neighbours; polylines (highways, barriers, tree rows) are cut at cell borders (each piece in the cell where it lies, the joint vertex repeated).
        x, y are integers LOCAL to the cell (add ix*cs, iy*cs). A polyline / ring is a flat array [x0, y0, dx1, dy1, ...]; a ring is closed implicitly.
  b buildings / parts [ring, props(, [hole ring ...])]   props (BFIELDS, trailing zeros dropped):
      k building=* ("p:"+value for a building:part)  lv levels (OSM, else inferred)  h height in units (OSM, else inferred)  bc colour RGB565 int (OSM, else the preset's)
      bm material code (palace_street_style.MATERIALS: 1 brick 2 stone 3 stucco 4 painted 5 concrete 6 glass 7 metal 8 wood 9 brownstone 10 cladding 11 tile 12 plaster)
      rs roof:shape  rc roof colour RGB565  rm roof:material  rl roof:levels  nm name  ad address "12 Walnut St"  po "shop=bakery"/"amenity=cafe"...  sd start_date  wd wikidata
      fl flags: 1 storefront (shop windows on the ground floor), 2 colour/material inferred, 4 levels inferred, 8 height inferred, 16 old (pre-1900 / old row house)
      mh min_height in units (building:part floating above the ground)
  r highways [line, props]  (RFIELDS): hw highway=*  nm name  ln lanes  wd width (units)  ow oneway (0, 1 forward, 2 reverse)  sw sidewalk  cy cycleway  sf surface  ms maxspeed
      lt lit (0 unknown, 1 yes, 2 no)  sl/sr sidewalk left/right ("yes"|"no"|"separate"...)  cl/cr cycleway left/right  br bridge 1  tn tunnel 1  la layer
  a areas [ring, props(, holes)] (AFIELDS): k leisure=park|pitch|playground|garden|... / "parking" / landuse  nm name  sp sport  sf surface
  w barriers [line, props] (WFIELDS): k fence|wall|hedge|retaining_wall|guard_rail|...  ht height (units)  mt material
  l tree rows [line, props] (LFIELDS): sp species/genus  lf leaf_type
  t trees, flat 4-tuples x, y, species, leaf      f furniture, flat 4-tuples x, y, kind, dir   (kind: street_lamp traffic_signals crossing stop bus_stop bench bicycle_parking
  waste_basket post_box fire_hydrant; dir = compass bearing the thing faces/controls + 1, 0 = unknown: from direction=* or forward/backward along the way)
  p storefront signs / POIs with a name, flat 5-tuples x, y, name, cat, ad       e entrances and doors, flat 3-tuples x, y, kind ("entrance=main", "door=hinged")

Data side, like palace_fleet.py: fetch() asks Overpass tile by tile (street-<tile>.json in the same cache dir, polite, offline = the cache only); the building tiles are the
ones the fill-in already cached (bld-<tile>.json, palace_map.fetch_buildings). palace_street_style.py fills the gaps of the sparse OSM tags. build() makes (manifest, shards);
make() builds and stores them in the blob folder (blob_dir(), ALTO_STREET_DIR) and returns the manifest hash; attach() records m["street"]. palace_assets.assets() lists the
files to publish (the newest manifest of each box and the shards it names — older ones are not copied).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path

from .. import palace_map as pmap

VERSION = 2
ATTRIBUTION = "© OpenStreetMap contributors, ODbL"
Q = 0.1                       # metres per stored unit
CS = 5000                     # cell size in units (500 m)
KY = 110574.0
FOLDER = "street"
MAN_RE = re.compile(r"^palace-street-([0-9a-f]{12})\.json$")        # the manifest (the page names it)
SHARD_RE = re.compile(r"^s-([0-9a-f]{8})\.json$")

BFIELDS = ("k", "lv", "h", "bc", "bm", "rs", "rc", "rm", "rl", "nm", "ad", "po", "sd", "wd", "fl", "mh")
RFIELDS = ("hw", "nm", "ln", "wd", "ow", "sw", "cy", "sf", "ms", "lt", "sl", "sr", "cl", "cr", "br", "tn", "la")
AFIELDS = ("k", "nm", "sp", "sf")
WFIELDS = ("k", "ht", "mt")
LFIELDS = ("sp", "lf")
_BSTR = {"k", "rs", "rm", "nm", "ad", "po", "sd", "wd"}                       # (bc / rc are rgb565 ints, bm a material code; wd: wikidata here, a NUMBER (width) in a highway)
_RSTR = {"hw", "nm", "sw", "cy", "sf", "ms", "sl", "sr", "cl", "cr"}
_FURNITURE_HW = {"street_lamp", "traffic_signals", "crossing", "stop", "bus_stop"}
_FURNITURE_AM = {"bench", "bicycle_parking", "waste_basket", "post_box", "fire_hydrant"}
_POI_KEYS = ("shop", "amenity", "tourism", "office")
_SKIP_HW = {"proposed", "construction", "razed", "abandoned", "platform", "bus_guideway", "corridor", "elevator", "no", "services", "rest_area"}
STREET_TILE = (0.015, 0.03)           # degrees; the same tile size as the building cache


# ── fetching ────────────────────────────────────────────────────────────────
def street_query(bbox, timeout: int = 170) -> str:
    """Trees, street furniture, entrances, named shops/amenities/tourism/offices and every highway of one tile (buildings come from the fill-in's cache)."""
    b = "(%r,%r,%r,%r)" % tuple(float(v) for v in bbox)
    return "\n".join([
        "[out:json][timeout:%d];" % timeout, "(",
        "  node[natural=tree]%s;" % b,
        '  node[highway~"^(street_lamp|traffic_signals|crossing|stop|bus_stop)$"]%s;' % b,
        '  node[amenity~"^(bench|bicycle_parking|waste_basket|post_box|fire_hydrant)$"]%s;' % b,
        "  node[emergency=fire_hydrant]%s;" % b,
        "  node[entrance]%s;" % b, "  node[door]%s;" % b,
        '  nwr[~"^(shop|amenity|tourism|office)$"~"."][name]%s;' % b,
        ");", "out center;", "(", "  way[highway]%s;" % b,
        '  way[barrier~"^(fence|wall|hedge|retaining_wall|guard_rail|city_wall|handrail)$"]%s;' % b, "  way[natural=tree_row]%s;" % b,
        '  nwr[leisure~"^(park|pitch|playground|garden|dog_park|common|recreation_ground|golf_course|track|nature_reserve)$"]%s;' % b, "  nwr[amenity=parking]%s;" % b,
        '  way[landuse~"^(grass|recreation_ground|village_green)$"]%s;' % b, ");", "out geom;"])


def _tile_path(cache_dir, tb):
    return Path(cache_dir) / ("street-%.4f_%.4f_%.4f_%.4f.json" % tuple(tb)) if cache_dir else None


def fetch(bbox, cache_dir=None, offline: bool = False, log=None) -> dict:
    """The street answers of the box, tile by tile, each cached as street-<tile>.json and never asked for again. Polite: a pause between fetched tiles, a failed tile
    waits and after two failures in a row nothing more is asked this time. offline: the cache only. Returns the merged answer plus "missing" (the tiles not fetched)."""
    raws, missing, fails, asked = [], [], 0, False
    for tb in pmap.tile_boxes(bbox, *STREET_TILE):
        path = _tile_path(cache_dir, tb)
        if path is not None and path.exists():
            try:
                raws.append(json.loads(path.read_text("utf-8")))
                continue
            except (OSError, ValueError):
                pass
        if offline or fails >= 2:
            missing.append(list(tb))
            continue
        if asked:
            pmap._sleep(pmap.BLD_PAUSE)
        asked = True
        try:
            raw = pmap._post_overpass(street_query(tb), 190)
        except RuntimeError as e:
            missing.append(list(tb))
            fails += 1
            if log:
                log("FAIL %s %s" % (tb, str(e)[:80]))
            pmap._sleep(pmap.BLD_BACKOFF[min(fails, len(pmap.BLD_BACKOFF)) - 1])
            continue
        fails = 0
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(raw, separators=(",", ":")), "utf-8")
                os.replace(tmp, path)
            except OSError:
                pass
        raws.append(raw)
    out = pmap.merge_raw(*raws) if raws else {"elements": []}
    out["missing"] = missing
    return out


def buildings(bbox, cache_dir=None, offline: bool = False, log=None) -> dict:
    """The building tiles (bld-<tile>.json) the fill-in cached, one by one through palace_map.fetch_buildings (a cached tile costs nothing)."""
    raws = [pmap.fetch_buildings(tb, cache_dir=cache_dir, offline=offline, log=log) for tb in pmap.tile_boxes(bbox, *pmap.BLD_TILE)]
    return pmap.merge_raw(*raws) if raws else {"elements": []}


# ── the frame ───────────────────────────────────────────────────────────────
class Frame:
    """lat/lon -> integer units (0.1 m) east/north of the bbox origin, the equirectangular frame of palace_map.project."""

    def __init__(self, bbox):
        self.s, self.w, self.n, self.e = (float(v) for v in bbox)
        self.kx = math.cos(math.radians((self.s + self.n) / 2)) * 111320
        self.nx = int((self.e - self.w) * self.kx / Q) // CS + 1
        self.ny = int((self.n - self.s) * KY / Q) // CS + 1

    def xy(self, lat, lon):
        return int(round((lon - self.w) * self.kx / Q)), int(round((lat - self.s) * KY / Q))

    def cell(self, X, Y):
        return X // CS, Y // CS

    def inside(self, X, Y):
        return 0 <= X // CS < self.nx and 0 <= Y // CS < self.ny


class _Strings:
    def __init__(self):
        self.tab, self.ix = [""], {"": 0}

    def __call__(self, s):
        s = ("" if s is None else str(s)).strip()
        if not s:
            return 0
        i = self.ix.get(s)
        if i is None:
            i = self.ix[s] = len(self.tab)
            self.tab.append(s)
        return i


# ── tags ────────────────────────────────────────────────────────────────────
def _fnum(v):
    try:
        return float(str(v).replace(",", ".").split()[0].rstrip("'"))
    except (TypeError, ValueError, IndexError):
        return None


def _metres(v):
    x = _fnum(v)
    if x is None:
        return None
    s = str(v).lower()
    return x * 0.3048 if ("ft" in s or "'" in s) else x


def _int(v):
    x = _fnum(v)
    return int(round(x)) if x is not None and 0 <= x < 1000 else 0


def _addr(t):
    st, hn = t.get("addr:street"), t.get("addr:housenumber")
    if st:
        return "%s %s" % (hn, st) if hn else str(st)
    return str(t.get("addr:housename") or "")


def _poi_cat(t):
    for k in _POI_KEYS:
        v = t.get(k)
        if v:
            return k if v == "yes" else "%s=%s" % (k, v)
    return ""


def _in_ring(lat, lon, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        yi, xi, yj, xj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


# ── parsing the answers ─────────────────────────────────────────────────────
def parse_buildings(raw: dict) -> list:
    """[(sort key, ring [(lat, lon)], [holes], tags)] — every building / building:part way and relation with its tags. The key ends with the OSM id."""
    out = []
    for e in (raw or {}).get("elements") or []:
        t = e.get("tags") or {}
        if "building" not in t and "building:part" not in t:
            continue
        rings = pmap._rings_of(e)
        outers = [r for r, inner in rings if not inner and len(r) >= 3]
        inners = [r for r, inner in rings if inner and len(r) >= 3]
        for r in outers:
            holes = [h for h in inners if _in_ring(h[0][0], h[0][1], r)]
            out.append(((round(r[0][0], 7), round(r[0][1], 7), e.get("id", 0)), r, holes, t))
    return out


_CARD = {"n": 0, "north": 0, "ne": 45, "e": 90, "east": 90, "se": 135, "s": 180, "south": 180, "sw": 225, "w": 270, "west": 270, "nw": 315}


def _bearing(a, b):
    dlat, dlon = b[0] - a[0], (b[1] - a[1]) * math.cos(math.radians(a[0]))
    return int(round(math.degrees(math.atan2(dlon, dlat)))) % 360


def _dir_of(t):
    """('deg', n) / ('fwd',) / ('back',) / None of a node's direction tags."""
    v = str(t.get("direction") or t.get("traffic_signals:direction") or t.get("stop:direction") or "").strip().lower()
    if not v or v in ("both", "all"):
        return None
    if v in ("forward", "backward"):
        return ("fwd",) if v == "forward" else ("back",)
    if v in _CARD:
        return ("deg", _CARD[v])
    x = _fnum(v)
    return ("deg", int(round(x)) % 360) if x is not None else None


_AREA_LEISURE = {"park", "pitch", "playground", "garden", "dog_park", "common", "recreation_ground", "golf_course", "track", "nature_reserve"}
_BARRIERS = {"fence", "wall", "hedge", "retaining_wall", "guard_rail", "city_wall", "handrail"}


def _area_kind(t):
    if t.get("leisure") in _AREA_LEISURE:
        return t["leisure"]
    if t.get("amenity") == "parking":
        return "parking"
    if t.get("landuse") in ("grass", "recreation_ground", "village_green"):
        return t["landuse"]
    return ""


def parse_street(raw: dict) -> dict:
    """{"trees", "furn", "poi", "door", "hw", "areas", "barriers", "rows"} of an Overpass street answer. Trees (lat, lon, id, species, leaf), furniture (lat, lon, id, kind,
    bearing or None), POIs (lat, lon, id, name, cat, address), doors (lat, lon, id, kind), highways (id, [(lat, lon)], tags, node ids), areas (id, ring, [holes], tags),
    barriers (id, [(lat, lon)], tags), tree rows (id, [(lat, lon)], tags)."""
    trees, furn, poi, door, hw, areas, bars, rows = [], [], [], [], [], [], [], []
    els = (raw or {}).get("elements") or []
    want = {}                                                  # furniture node id -> its direction tag (forward / backward need the way's heading)
    for e in els:
        t = e.get("tags") or {}
        if e.get("type") == "node" and t and _dir_of(t):
            want[e.get("id")] = _dir_of(t)
    head = {}
    for e in sorted((x for x in els if x.get("type") == "way" and x.get("nodes") and x.get("geometry")), key=lambda x: x.get("id", 0)):
        g = pmap._pts(e["geometry"])
        ids = e["nodes"]
        if len(ids) != len(g):
            continue
        for i, nid in enumerate(ids):
            if nid in want and nid not in head and len(g) > 1:
                head[nid] = _bearing(g[i], g[i + 1]) if i + 1 < len(g) else _bearing(g[i - 1], g[i])
    for e in els:
        t = e.get("tags") or {}
        ty = e.get("type")
        i = e.get("id", 0)
        if ty == "way" and "highway" in t and e.get("geometry"):
            if t["highway"] not in _SKIP_HW:
                hw.append((i, pmap._pts(e["geometry"]), t, e.get("nodes") or []))
            continue
        if ty == "way" and t.get("barrier") in _BARRIERS and e.get("geometry"):
            bars.append((i, pmap._pts(e["geometry"]), t))
            continue
        if ty == "way" and t.get("natural") == "tree_row" and e.get("geometry"):
            rows.append((i, pmap._pts(e["geometry"]), t))
            continue
        if ty in ("way", "relation") and _area_kind(t) and (e.get("geometry") or e.get("members")):
            rings = pmap._rings_of(e)
            inners = [r for r, inner in rings if inner and len(r) >= 3]
            for r in [r for r, inner in rings if not inner and len(r) >= 3]:
                areas.append((i, r, [h for h in inners if _in_ring(h[0][0], h[0][1], r)], t))
            continue
        c = pmap._center(e)
        if c is None:
            continue
        lat, lon = c
        if t.get("natural") == "tree" and ty == "node":
            trees.append((lat, lon, i, str(t.get("species") or t.get("genus") or t.get("species:en") or ""), str(t.get("leaf_type") or "")))
            continue
        fk = (t.get("highway") if t.get("highway") in _FURNITURE_HW else t.get("amenity") if t.get("amenity") in _FURNITURE_AM
              else "fire_hydrant" if t.get("emergency") == "fire_hydrant" else "")
        if fk and ty == "node":
            d = want.get(i)
            b = None
            if d:
                b = d[1] if d[0] == "deg" else (head.get(i) if d[0] == "fwd" else (head[i] + 180) % 360 if i in head else None)
            furn.append((lat, lon, i, fk, b))
            continue
        if ty == "node" and ("entrance" in t or "door" in t):
            door.append((lat, lon, i, ("entrance=" + t["entrance"]) if "entrance" in t else ("door=" + t["door"])))
            continue
        cat = _poi_cat(t)
        if cat and t.get("name"):
            poi.append((lat, lon, i, str(t["name"]), cat, _addr(t)))
    return {"trees": trees, "furn": furn, "poi": poi, "door": door, "hw": hw, "areas": areas, "barriers": bars, "rows": rows}


# ── encoding ────────────────────────────────────────────────────────────────
def _delta(pts):
    out, px, py = [], 0, 0
    for k, (x, y) in enumerate(pts):
        out += [x, y] if k == 0 else [x - px, y - py]
        px, py = x, y
    return out


def _trim(props):
    while props and props[-1] == 0:
        props.pop()
    return props


def _side(t, key):
    """(left, right) strings of sidewalk=* / cycleway=* (a bare value or :both applies to both sides; :left / :right win)."""
    both = str(t.get(key + ":both") or t.get(key) or "")
    l = str(t.get(key + ":left") or "")
    r = str(t.get(key + ":right") or "")
    if both in ("both", "yes"):
        l, r = l or "yes", r or "yes"
    elif both == "left":
        l, r = l or "yes", r or "no"
    elif both == "right":
        l, r = l or "no", r or "yes"
    elif both:
        l, r = l or both, r or both
    return l, r


def _area_m2(pts):
    a = 0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2 * Q * Q


def _pip(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi, xj, yj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1) + xi:
            inside = not inside
        j = i
    return inside


def _conv(v, S):
    if isinstance(v, str):
        return S(v)
    if isinstance(v, list):
        return [_conv(x, S) for x in v]
    if isinstance(v, dict):
        return {k: _conv(x, S) for k, x in v.items()}
    return v


GROUP = 2                      # cells per shard side (a shard is a 1000 m x 1000 m square of cells)


def build(bbox, bld_raw: dict, street_raw: dict, preset=None):
    """(manifest, shards) for the box: shards {id: {"S": [...], "c": {cell key: cell}}} (one per GROUP x GROUP cells, each with its own string table, named by the hash
    of its text) and the manifest {header, "f": {id: bytes}, "c": {cell key: id}}."""
    from . import palace_street_style as sty
    fr = Frame(bbox)
    preset = preset or sty.preset_for(bbox)
    cells: dict = {}

    def put(k, key, rec):
        cells.setdefault("%d,%d" % k, {}).setdefault(key, []).append(rec)

    def flat(k, key, items):
        cells.setdefault("%d,%d" % k, {}).setdefault(key, []).extend(items)

    def local(pts, k):
        return [(x - k[0] * CS, y - k[1] * CS) for x, y in pts]

    def quant(ring):
        pts = []
        for la, lo in ring:
            p = fr.xy(la, lo)
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts.pop()
        return pts

    st = parse_street(street_raw)
    grid: dict = {}                                            # where shops / amenities stand (storefronts)
    for la, lo, _i, _n, cat, _a in st["poi"]:
        if cat not in ("amenity=parking", "amenity=bench", "amenity=shelter"):
            X, Y = fr.xy(la, lo)
            grid.setdefault((X // 2000, Y // 2000), []).append((X, Y))

    def has_poi(pts):
        x0, x1, y0, y1 = min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)
        for gx in range(x0 // 2000, x1 // 2000 + 1):
            for gy in range(y0 // 2000, y1 // 2000 + 1):
                for X, Y in grid.get((gx, gy), ()):
                    if x0 <= X <= x1 and y0 <= Y <= y1 and _pip(X, Y, pts):
                        return True
        return False

    for key, ring, holes, t in sorted(parse_buildings(bld_raw), key=lambda b: b[0]):
        pts = quant(ring)
        if len(pts) < 3:
            continue
        cx, cy = sum(p[0] for p in pts) // len(pts), sum(p[1] for p in pts) // len(pts)
        if not fr.inside(cx, cy):
            continue
        k = fr.cell(cx, cy)
        part = "building" not in t
        h = _metres(t.get("height"))
        mh = _metres(t.get("min_height"))
        if not mh and _fnum(t.get("building:min_level")):
            mh = _fnum(t.get("building:min_level")) * 3.3
        res = sty.resolve(preset, t, _area_m2(pts), h or 0.0, _int(t.get("building:levels")), sty.seed_of(key), commercial=(not part) and (bool(_poi_cat(t)) or has_poi(pts)))
        props = _trim(["%s%s" % ("p:" if part else "", (t.get("building:part") if part else t.get("building")) or "yes"),
                       res["lv"], int(round(res["h"] / Q)) if res["h"] else 0, res["bc"], res["bm"], str(t.get("roof:shape") or ""), res["rc"], str(t.get("roof:material") or ""),
                       _int(t.get("roof:levels")), str(t.get("name") or ""), _addr(t), _poi_cat(t), str(t.get("start_date") or ""), str(t.get("wikidata") or ""),
                       res["fl"], int(round(mh / Q)) if mh and mh > 0 else 0])
        rec = [_delta(local(pts, k)), props]
        hs = [_delta(local(q, k)) for q in (quant(h_) for h_ in holes) if len(q) >= 3]
        if hs:
            rec.append(hs)
        put(k, "b", rec)

    def pt_items(src, key, mk):
        for row in sorted(src, key=lambda r: r[:3]):
            X, Y = fr.xy(row[0], row[1])
            if fr.inside(X, Y):
                k = fr.cell(X, Y)
                flat(k, key, [X - k[0] * CS, Y - k[1] * CS] + mk(row))

    pt_items(st["trees"], "t", lambda r: [r[3], r[4]])
    pt_items(st["furn"], "f", lambda r: [r[3], (r[4] % 360) + 1 if r[4] is not None else 0])
    pt_items(st["poi"], "p", lambda r: [r[3], r[4], r[5]])
    pt_items(st["door"], "e", lambda r: [r[3]])

    def cut(ll, rec_of):
        """Cuts a polyline at the cell borders; each piece goes to the cell where it lies, the joint vertex shared."""
        pts = quant(ll)
        if len(pts) < 2 or (len(ll) > 2 and ll[0] == ll[-1] and len(pts) < 3):
            return
        if len(ll) > 2 and ll[0] == ll[-1]:
            pts.append(pts[0])                                    # a closed way (a roundabout) stays closed
        piece, pk = [], None
        for p in pts + [None]:
            kk = fr.cell(*p) if p is not None and fr.inside(*p) else None
            if kk is not None and kk == pk:
                piece.append(p)
                continue
            if kk is not None and pk is not None:
                piece.append(p)
            if len(piece) > 1:
                yield pk, [_delta(local(piece, pk))] + rec_of
            piece, pk = ([p], kk) if kk is not None else ([], None)

    for _i, ll, t, _nodes in sorted(st["hw"], key=lambda r: r[0]):
        w = _metres(t.get("width"))
        ow = {"yes": 1, "1": 1, "true": 1, "-1": 2, "reverse": 2}.get(str(t.get("oneway") or ""), 0)
        lt = {"yes": 1, "no": 2}.get(str(t.get("lit") or ""), 0)
        sl, sr = _side(t, "sidewalk")
        cl, cr = _side(t, "cycleway")
        br = 1 if str(t.get("bridge") or "no") not in ("no", "") else 0
        tn = 1 if str(t.get("tunnel") or "no") not in ("no", "") else 0
        la_ = _fnum(t.get("layer"))
        props = _trim([str(t.get("highway") or ""), str(t.get("name") or ""), _int(t.get("lanes")), int(round(w / Q)) if w and w > 0 else 0, ow, str(t.get("sidewalk") or ""),
                       str(t.get("cycleway") or t.get("cycleway:both") or t.get("cycleway:right") or t.get("cycleway:left") or ""), str(t.get("surface") or ""),
                       str(t.get("maxspeed") or ""), lt, sl, sr, cl, cr, br, tn, int(la_) if la_ and -6 < la_ < 6 else 0])
        for k, rec in cut(ll, [props]):
            put(k, "r", rec)
    for _i, ll, t in sorted(st["barriers"], key=lambda r: r[0]):
        h_ = _metres(t.get("height"))
        props = _trim([str(t["barrier"]), int(round(h_ / Q)) if h_ and h_ > 0 else 0, str(t.get("material") or "")])
        for k, rec in cut(ll, [props]):
            put(k, "w", rec)
    for _i, ll, t in sorted(st["rows"], key=lambda r: r[0]):
        props = _trim([str(t.get("species") or t.get("genus") or ""), str(t.get("leaf_type") or "")])
        for k, rec in cut(ll, [props]):
            put(k, "l", rec)
    for key, ring, holes, t in sorted(st["areas"], key=lambda a: (round(a[1][0][0], 7), round(a[1][0][1], 7), a[0])):
        pts = quant(ring)
        if len(pts) < 3:
            continue
        cx, cy = sum(p[0] for p in pts) // len(pts), sum(p[1] for p in pts) // len(pts)
        if not fr.inside(cx, cy):
            continue
        k = fr.cell(cx, cy)
        props = _trim([_area_kind(t), str(t.get("name") or ""), str(t.get("sport") or ""), str(t.get("surface") or "")])
        rec = [_delta(local(pts, k)), props]
        hs = [_delta(local(q, k)) for q in (quant(h_) for h_ in holes) if len(q) >= 3]
        if hs:
            rec.append(hs)
        put(k, "a", rec)

    # shards: GROUP x GROUP cells each, a string table of their own
    groups: dict = {}
    for ck in sorted(cells, key=lambda s: tuple(int(v) for v in s.split(","))):
        ix, iy = (int(v) for v in ck.split(","))
        groups.setdefault((ix // GROUP, iy // GROUP), []).append(ck)
    shards, files, cmap = {}, {}, {}
    for gk in sorted(groups):
        S = _Strings()
        body = {ck: _conv(cells[ck], S) for ck in groups[gk]}
        sh = {"S": S.tab, "c": body}
        text = encode(sh)
        sid = blob_hash(text, 8)
        shards[sid] = sh
        files[sid] = len(text.encode("utf-8"))
        for ck in groups[gk]:
            cmap[ck] = sid
    manifest = {"v": VERSION, "a": ATTRIBUTION, "o": [fr.s, fr.w, fr.n, fr.e], "q": Q, "cs": CS, "kx": round(fr.kx, 3), "ky": KY, "n": [fr.nx, fr.ny], "g": GROUP,
                "preset": preset, "f": {k: files[k] for k in sorted(files)}, "c": cmap}
    return manifest, shards


def encode(blob: dict) -> str:
    """A manifest or a shard as compact JSON text (what is hosted and hashed)."""
    return json.dumps(blob, separators=(",", ":"), ensure_ascii=False)


def blob_hash(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def file_name(h: str) -> str:
    """The manifest's file (12 hex chars) or a shard's (8): palace-street-<h12>.json / s-<h8>.json."""
    return ("palace-street-%s.json" % h) if len(h) == 12 else ("s-%s.json" % h)


def url_of(h: str) -> str:
    return "/%s/%s" % (FOLDER, file_name(h))


# ── the blob folder (what publish_static writes into site/street/) ──────────
def blob_dir() -> Path:
    return Path(os.environ.get("ALTO_STREET_DIR") or (Path.home() / ".cache" / "alto" / "street"))


def _write(d: Path, name: str, text: str):
    p = d / name
    if not p.exists():
        tmp = p.with_suffix(".tmp")
        tmp.write_text(text, "utf-8")
        os.replace(tmp, p)
    else:
        os.utime(p)                                        # (the newest manifest of a box is the one that stays)


def store(manifest: dict, shards: dict, directory=None) -> str:
    """Writes every shard (s-<h8>.json) and the manifest (palace-street-<h12>.json) into the blob folder; returns the manifest's hash."""
    d = Path(directory) if directory else blob_dir()
    d.mkdir(parents=True, exist_ok=True)
    for sid, sh in shards.items():
        _write(d, file_name(sid), encode(sh))
    text = encode(manifest)
    h = blob_hash(text)
    _write(d, file_name(h), text)
    return h


def blobs(directory=None) -> list:
    """[(file name, text)] to publish: for each box only its NEWEST manifest, and only the shards a kept manifest names. A file that does not match its hash is skipped."""
    import time
    d = Path(directory) if directory else blob_dir()
    if not d.is_dir():
        return []
    keep: dict = {}
    for p in d.iterdir():
        m = MAN_RE.match(p.name)
        if not m:
            continue
        try:
            txt, mt = p.read_text("utf-8"), p.stat().st_mtime
            man = json.loads(txt)
        except (OSError, ValueError):
            continue
        if blob_hash(txt) != m.group(1) or not isinstance(man, dict) or man.get("v") != VERSION:
            continue
        box = tuple(man.get("o") or ())
        if box not in keep or (mt, p.name) > (keep[box][0], keep[box][1]):
            keep[box] = (mt, p.name, txt, man)
    out, want = [], set()
    for _mt, name, txt, man in keep.values():
        out.append((name, txt))
        want |= set(man.get("f") or {})
    for sid in sorted(want):
        p = d / file_name(sid)
        try:
            txt = p.read_text("utf-8")
        except OSError:
            continue
        if blob_hash(txt, 8) == sid:
            out.append((p.name, txt))
    return sorted(out)


def load(h: str, directory=None):
    """(manifest, {id: shard}) of a stored manifest hash (the reference reader the tests use)."""
    d = Path(directory) if directory else blob_dir()
    man = json.loads((d / file_name(h)).read_text("utf-8"))
    return man, {sid: json.loads((d / file_name(sid)).read_text("utf-8")) for sid in man["f"]}


def make(bbox, cache_dir=None, offline: bool = False, log=None, directory=None):
    """Fetch (cached), build and store the street data of the box. Returns (manifest hash, total bytes of the manifest and its shards) or None when the box has nothing."""
    man, shards = build(bbox, buildings(bbox, cache_dir, offline, log), fetch(bbox, cache_dir=cache_dir, offline=offline, log=log))
    if not man["c"]:
        return None
    h = store(man, shards, directory)
    return h, len(encode(man).encode("utf-8")) + sum(man["f"].values())


def attach(m: dict, bbox, cache_dir=None, offline: bool = False) -> None:
    """Builds the street data for the map's box and records it on the page's map data: m["street"] = {"h": "<12 hex>"} (the manifest). Never fatal."""
    try:
        r = make(m.get("bbox") or bbox, cache_dir=cache_dir, offline=offline)
    except Exception:                                       # noqa: BLE001 — a busy Overpass or a box with nothing: the ride simply has no street data
        return
    if r:
        m["street"] = {"h": r[0]}


# ── reference decoder (tests; the ride uses STREET_JS) ──────────────────────
def decode_cell(man: dict, key: str, shards: dict):
    """The cell `key` ("ix,iy") with absolute coordinates in metres east/north of the origin and strings resolved; None when its shard is not in `shards`
    (not loaded yet); an empty cell when the manifest has none."""
    from . import palace_street_style as sty
    out = {"b": [], "r": [], "t": [], "f": [], "p": [], "e": [], "a": [], "w": [], "l": []}
    sid = man["c"].get(key)
    if sid is None:
        return out
    sh = shards.get(sid)
    if sh is None:
        return None
    S = sh["S"]
    ix, iy = (int(v) for v in key.split(","))
    ox, oy, q = ix * man["cs"], iy * man["cs"], man["q"]
    c = sh["c"].get(key) or {}

    def line(a):
        o, x, y = [], 0, 0
        for i in range(0, len(a), 2):
            x = a[i] if i == 0 else x + a[i]
            y = a[i + 1] if i == 0 else y + a[i + 1]
            o.append(((x + ox) * q, (y + oy) * q))
        return o

    def props(names, strs, p):
        d = {}
        for i, nm in enumerate(names):
            v = p[i] if i < len(p) else 0
            d[nm] = S[v] if nm in strs else v
        return d

    for rec in c.get("b", []):
        d = props(BFIELDS, _BSTR, rec[1])
        d["ring"], d["holes"] = line(rec[0]), [line(h) for h in (rec[2] if len(rec) > 2 else [])]
        d["hm"], d["mhm"] = d["h"] * q, d["mh"] * q
        d["colour"], d["material"], d["storefront"] = (sty.rgb565_to_hex(d["bc"]) if d["bc"] else ""), sty.MATERIALS[d["bm"]], bool(d["fl"] & sty.FL_STOREFRONT)
        out["b"].append(d)
    for rec in c.get("r", []):
        d = props(RFIELDS, _RSTR, rec[1])
        d["line"] = line(rec[0])
        out["r"].append(d)
    for rec in c.get("w", []):
        d = props(WFIELDS, {"k", "mt"}, rec[1])
        d["ht"] = d["ht"] * q
        d["line"] = line(rec[0])
        out["w"].append(d)
    for rec in c.get("l", []):
        d = props(LFIELDS, set(LFIELDS), rec[1])
        d["line"] = line(rec[0])
        out["l"].append(d)
    for rec in c.get("a", []):
        d = props(AFIELDS, set(AFIELDS), rec[1])
        d["ring"], d["holes"] = line(rec[0]), [line(h) for h in (rec[2] if len(rec) > 2 else [])]
        out["a"].append(d)
    for key_, width, names in (("t", 4, ("sp", "lf")), ("f", 4, ("kind", "dir")), ("p", 5, ("name", "cat", "ad")), ("e", 3, ("kind",))):
        a = c.get(key_, [])
        for i in range(0, len(a), width):
            d = {"x": (a[i] + ox) * q, "y": (a[i + 1] + oy) * q}
            for j, nm in enumerate(names):
                v = a[i + 2 + j]
                d[nm] = (v - 1 if v else None) if nm == "dir" else S[v]
            out[key_].append(d)
    return out
