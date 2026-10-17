"""Street-level data of any city for the first-person view (2.0.0): a HOSTED, content-hashed blob, never part of the page.

The private palace page is within ~15 KB of its 1,000,000 byte cap, so the real street scene (building materials, roofs, shop signs, doors, street trees,
lamps, benches, lane widths ...) is read from OpenStreetMap at build time and written to  site/street/palace-street-<hash>.json  (palace_assets.py registers
and publishes it, the hosting headers keep it for a year). The page holds only  m["street"] = {"h": "<hash>"}  (12 hex chars, ~28 bytes); the ride asks for
/street/palace-street-<hash>.json and decodes it with STREET_JS (palace_street_js.py).

BLOB FORMAT, v1 (one JSON object, compact separators; features are sorted before encoding so the same data gives the same bytes and the same hash)
  v    1                                    format version
  a    "© OpenStreetMap contributors, ODbL" attribution to show wherever the data is used
  o    [south, west, north, east]           the bbox in degrees; the origin of every coordinate is (south, west)
  q    0.1                                  metres per stored unit
  cs   5000                                 cell size in units (500 m)
  kx   metres per degree of longitude (cos(mid latitude) * 111320), ky metres per degree of latitude (110574): the SAME equirectangular frame as
       palace_map.project, so  X_m = (lon - west) * kx,  Y_m = (lat - south) * ky   (Y grows NORTH here; the palace map's y grows south: y_map = (north-lat)*ky)
  n    [nx, ny]                             number of cells east and north
  S    ["", "string", ...]                  string table; every string below is an index into it (0 = none), so a repeated word is stored once
  c    {"ix,iy": cell}                      only the non-empty cells; cell (ix, iy) covers units [ix*cs, (ix+1)*cs) east and [iy*cs, (iy+1)*cs) north of the origin.
       A feature lives in the cell of its first point (buildings: centroid); one that spills over is NOT cut, so a client asks the cell AND its 8 neighbours.
       Highway lines are cut at cell borders instead (each piece lives in the cell where it starts; the joint vertex is repeated in both pieces).
Every x, y is an integer in units LOCAL to its cell (add ix*cs, iy*cs; may lie slightly outside 0..cs for a spill-over). A polyline/ring is a flat int array
[x0, y0, dx1, dy1, dx2, dy2, ...] (deltas from the previous vertex); a ring is closed implicitly (the first vertex is not repeated).
Cell keys (each present only if non-empty):
  b  buildings and building parts:  [ring, props]  or  [ring, props, [hole ring, ...]]
     props = ints / string indexes in this order, trailing zeros dropped (BFIELDS):
       k   building=* value (a building:part has "p:" + its value)        lv  building:levels (int)           h   height in units (0.1 m)
       bc  building:colour   bm building:material   rs roof:shape   rc roof:colour   rm roof:material   rl roof:levels (int)
       nm  name   ad address "12 Walnut St"   po what is inside "shop=bakery" / "amenity=cafe" / "tourism=hotel" / "office=lawyer"
       sd  start_date   wd wikidata
  r  highways:  [line, props]       props (RFIELDS): hw highway=* value, nm name, ln lanes (int), wd width in units, ow oneway (0 no, 1 forward, 2 reverse),
                                    sw sidewalk (string: both|left|right|no|separate), cy cycleway (string), sf surface, ms maxspeed (string), lt lit (0 unknown, 1 yes, 2 no)
  t  trees, flat 4-tuples:   x, y, species (species or genus string), leaf (leaf_type string: broadleaved|needleleaved)
  f  street furniture, flat 3-tuples:  x, y, kind (string: street_lamp traffic_signals crossing stop bus_stop bench bicycle_parking waste_basket post_box fire_hydrant)
  p  storefront signs / POIs with a name, flat 5-tuples:  x, y, name, cat ("shop=bakery" ...), ad (address string or 0)
  e  entrances and doors, flat 3-tuples:  x, y, kind ("entrance=main", "door=hinged", ...)

Data side, like palace_fleet.py: fetch() asks Overpass tile by tile (street-<tile>.json in the same cache dir, polite, offline = the cache only); the building tiles are
the ones the fill-in already cached (bld-<tile>.json, palace_map.fetch_buildings). build()/encode() make the blob; make() builds, stores it in the blob folder
(blob_dir(), ALTO_STREET_DIR) and returns its hash; attach() records m["street"] = {"h": hash}. palace_assets.assets() lists every stored blob and publish_static writes them.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path

from .. import palace_map as pmap

VERSION = 1
ATTRIBUTION = "© OpenStreetMap contributors, ODbL"
Q = 0.1                       # metres per stored unit
CS = 5000                     # cell size in units (500 m)
KY = 110574.0
FOLDER = "street"
NAME_RE = re.compile(r"^palace-street-([0-9a-f]{12})\.json$")

BFIELDS = ("k", "lv", "h", "bc", "bm", "rs", "rc", "rm", "rl", "nm", "ad", "po", "sd", "wd")
RFIELDS = ("hw", "nm", "ln", "wd", "ow", "sw", "cy", "sf", "ms", "lt")
_BSTR = {"k", "bc", "bm", "rs", "rc", "rm", "nm", "ad", "po", "sd", "wd"}     # (wd: wikidata in a building, a NUMBER (width) in a highway)
_RSTR = {"hw", "nm", "sw", "cy", "sf", "ms"}
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
        ");", "out center;", "(", "  way[highway]%s;" % b, ");", "out geom;"])


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
    """[(sort key, ring [(lat, lon)], [holes], tags)] — every building / building:part way and relation with its tags."""
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


def parse_street(raw: dict) -> dict:
    """{"trees", "furn", "poi", "door", "hw"} of an Overpass street answer. Trees (lat, lon, id, species, leaf), furniture (lat, lon, id, kind),
    POIs (lat, lon, id, name, cat, address), doors (lat, lon, id, kind), highways (id, [(lat, lon)], tags)."""
    trees, furn, poi, door, hw = [], [], [], [], []
    for e in (raw or {}).get("elements") or []:
        t = e.get("tags") or {}
        ty = e.get("type")
        if ty == "way" and "highway" in t and e.get("geometry"):
            if t["highway"] not in _SKIP_HW:
                hw.append((e.get("id", 0), pmap._pts(e["geometry"]), t))
            continue
        c = pmap._center(e)
        if c is None:
            continue
        lat, lon = c
        i = e.get("id", 0)
        if t.get("natural") == "tree" and ty == "node":
            trees.append((lat, lon, i, str(t.get("species") or t.get("genus") or t.get("species:en") or ""), str(t.get("leaf_type") or "")))
            continue
        fk = (t.get("highway") if t.get("highway") in _FURNITURE_HW else t.get("amenity") if t.get("amenity") in _FURNITURE_AM
              else "fire_hydrant" if t.get("emergency") == "fire_hydrant" else "")
        if fk and ty == "node":
            furn.append((lat, lon, i, fk))
            continue
        if ty == "node" and ("entrance" in t or "door" in t):
            door.append((lat, lon, i, ("entrance=" + t["entrance"]) if "entrance" in t else ("door=" + t["door"])))
            continue
        cat = _poi_cat(t)
        if cat and t.get("name"):
            poi.append((lat, lon, i, str(t["name"]), cat, _addr(t)))
    return {"trees": trees, "furn": furn, "poi": poi, "door": door, "hw": hw}


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


def build(bbox, bld_raw: dict, street_raw: dict) -> dict:
    """The blob (a dict) for the box from the building answer and the street answer."""
    fr = Frame(bbox)
    S = _Strings()
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

    for _key, ring, holes, t in sorted(parse_buildings(bld_raw), key=lambda b: b[0]):
        pts = quant(ring)
        if len(pts) < 3:
            continue
        cx, cy = sum(p[0] for p in pts) // len(pts), sum(p[1] for p in pts) // len(pts)
        if not fr.inside(cx, cy):
            continue
        k = fr.cell(cx, cy)
        part = "building" not in t
        h = _metres(t.get("height"))
        props = _trim([S(("p:" if part else "") + str((t.get("building:part") if part else t.get("building")) or "yes")),
                       _int(t.get("building:levels")), int(round(h / Q)) if h and h > 0 else 0,
                       S(t.get("building:colour")), S(t.get("building:material")), S(t.get("roof:shape")), S(t.get("roof:colour")), S(t.get("roof:material")),
                       _int(t.get("roof:levels")), S(t.get("name")), S(_addr(t)), S(_poi_cat(t)), S(t.get("start_date")), S(t.get("wikidata"))])
        rec = [_delta(local(pts, k)), props]
        hs = [_delta(local(q, k)) for q in (quant(h_) for h_ in holes) if len(q) >= 3]
        if hs:
            rec.append(hs)
        put(k, "b", rec)

    st = parse_street(street_raw)
    for la, lo, _i, sp, lf in sorted(st["trees"], key=lambda r: r[:3]):
        X, Y = fr.xy(la, lo)
        if fr.inside(X, Y):
            k = fr.cell(X, Y)
            flat(k, "t", [X - k[0] * CS, Y - k[1] * CS, S(sp), S(lf)])
    for la, lo, _i, kind in sorted(st["furn"], key=lambda r: r[:3]):
        X, Y = fr.xy(la, lo)
        if fr.inside(X, Y):
            k = fr.cell(X, Y)
            flat(k, "f", [X - k[0] * CS, Y - k[1] * CS, S(kind)])
    for la, lo, _i, name, cat, ad in sorted(st["poi"], key=lambda r: r[:3]):
        X, Y = fr.xy(la, lo)
        if fr.inside(X, Y):
            k = fr.cell(X, Y)
            flat(k, "p", [X - k[0] * CS, Y - k[1] * CS, S(name), S(cat), S(ad)])
    for la, lo, _i, kind in sorted(st["door"], key=lambda r: r[:3]):
        X, Y = fr.xy(la, lo)
        if fr.inside(X, Y):
            k = fr.cell(X, Y)
            flat(k, "e", [X - k[0] * CS, Y - k[1] * CS, S(kind)])
    for _i, ll, t in sorted(st["hw"], key=lambda r: r[0]):
        pts = quant(ll)
        if len(pts) < 2 or (len(ll) > 2 and ll[0] == ll[-1] and len(pts) < 3):
            continue
        if len(ll) > 2 and ll[0] == ll[-1]:
            pts.append(pts[0])                                    # a closed way (a roundabout) stays closed
        w = _metres(t.get("width"))
        ow = {"yes": 1, "1": 1, "true": 1, "-1": 2, "reverse": 2}.get(str(t.get("oneway") or ""), 0)
        lt = {"yes": 1, "no": 2}.get(str(t.get("lit") or ""), 0)
        props = _trim([S(t.get("highway")), S(t.get("name")), _int(t.get("lanes")), int(round(w / Q)) if w and w > 0 else 0, ow, S(t.get("sidewalk")),
                       S(t.get("cycleway") or t.get("cycleway:both") or t.get("cycleway:right") or t.get("cycleway:left")), S(t.get("surface")), S(t.get("maxspeed")), lt])
        piece, pk = [], None
        for p in pts + [None]:
            kk = fr.cell(*p) if p is not None and fr.inside(*p) else None
            if kk is not None and kk == pk:
                piece.append(p)
                continue
            if kk is not None and pk is not None:
                piece.append(p)                                   # the joint vertex ends this piece and starts the next
            if len(piece) > 1:
                put(pk, "r", [_delta(local(piece, pk)), props])
            piece, pk = ([p], kk) if kk is not None else ([], None)

    return {"v": VERSION, "a": ATTRIBUTION, "o": [fr.s, fr.w, fr.n, fr.e], "q": Q, "cs": CS, "kx": round(fr.kx, 3), "ky": KY, "n": [fr.nx, fr.ny],
            "S": S.tab, "c": {k: cells[k] for k in sorted(cells, key=lambda s: tuple(int(v) for v in s.split(",")))}}


def encode(blob: dict) -> str:
    """The blob as compact JSON text (what is hosted and hashed)."""
    return json.dumps(blob, separators=(",", ":"), ensure_ascii=False)


def blob_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def file_name(h: str) -> str:
    return "palace-street-%s.json" % h


def url_of(h: str) -> str:
    return "/%s/%s" % (FOLDER, file_name(h))


# ── the blob folder (what publish_static writes into site/street/) ──────────
def blob_dir() -> Path:
    return Path(os.environ.get("ALTO_STREET_DIR") or (Path.home() / ".cache" / "alto" / "street"))


def store(text: str, directory=None) -> str:
    """Writes the blob text as palace-street-<hash>.json (once) into the blob folder; returns the hash."""
    h = blob_hash(text)
    d = Path(directory) if directory else blob_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / file_name(h)
    if not p.exists():
        tmp = p.with_suffix(".tmp")
        tmp.write_text(text, "utf-8")
        os.replace(tmp, p)
    return h


def blobs(directory=None) -> list:
    """[(file name, text)] of every stored blob whose content still matches its hash (a damaged one is not published)."""
    d = Path(directory) if directory else blob_dir()
    out = []
    if d.is_dir():
        for p in sorted(d.iterdir()):
            m = NAME_RE.match(p.name)
            if m:
                try:
                    txt = p.read_text("utf-8")
                except OSError:
                    continue
                if blob_hash(txt) == m.group(1):
                    out.append((p.name, txt))
    return out


def make(bbox, cache_dir=None, offline: bool = False, log=None, directory=None):
    """Fetch (cached), build and store the street blob of the box. Returns (hash, size in bytes) or None when the box has nothing in it."""
    blob = build(bbox, buildings(bbox, cache_dir, offline, log), fetch(bbox, cache_dir=cache_dir, offline=offline, log=log))
    if not blob["c"]:
        return None
    text = encode(blob)
    return store(text, directory), len(text.encode("utf-8"))


def attach(m: dict, bbox, cache_dir=None, offline: bool = False) -> None:
    """Builds the blob for the map's box and records the hosted file on the page's map data: m["street"] = {"h": "<12 hex>"}. Never fatal."""
    try:
        r = make(m.get("bbox") or bbox, cache_dir=cache_dir, offline=offline)
    except Exception:                                       # noqa: BLE001 — a busy Overpass or a box with nothing: the ride simply has no street data
        return
    if r:
        m["street"] = {"h": r[0]}


# ── reference decoder (tests; the ride uses STREET_JS) ──────────────────────
def decode_cell(blob: dict, key: str) -> dict:
    """The cell `key` ("ix,iy") with absolute coordinates in metres east/north of the origin and strings resolved."""
    S = blob["S"]
    ix, iy = (int(v) for v in key.split(","))
    ox, oy, q = ix * blob["cs"], iy * blob["cs"], blob["q"]
    c = blob["c"].get(key) or {}

    def line(a):
        out, x, y = [], 0, 0
        for i in range(0, len(a), 2):
            x = a[i] if i == 0 else x + a[i]
            y = a[i + 1] if i == 0 else y + a[i + 1]
            out.append(((x + ox) * q, (y + oy) * q))
        return out

    def props(names, strs, p):
        d = {}
        for i, nm in enumerate(names):
            v = p[i] if i < len(p) else 0
            d[nm] = S[v] if nm in strs else v
        return d

    out = {"b": [], "r": [], "t": [], "f": [], "p": [], "e": []}
    for rec in c.get("b", []):
        d = props(BFIELDS, _BSTR, rec[1])
        d["ring"], d["holes"] = line(rec[0]), [line(h) for h in (rec[2] if len(rec) > 2 else [])]
        out["b"].append(d)
    for rec in c.get("r", []):
        d = props(RFIELDS, _RSTR, rec[1])
        d["line"] = line(rec[0])
        out["r"].append(d)
    for key_, width, names in (("t", 4, ("sp", "lf")), ("f", 3, ("kind",)), ("p", 5, ("name", "cat", "ad")), ("e", 3, ("kind",))):
        a = c.get(key_, [])
        for i in range(0, len(a), width):
            d = {"x": (a[i] + ox) * q, "y": (a[i + 1] + oy) * q}
            for j, nm in enumerate(names):
                d[nm] = S[a[i + 2 + j]]
            out[key_].append(d)
    return out
