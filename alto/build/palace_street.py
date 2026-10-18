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
  src [{k "osm"|"opa"|"lif"|"wikidata", n name, l licence, a attribution(, rows)}] the sources used (palace_street_city.SOURCES); sn [notes] what was not available this build.
  a gains "; City of Philadelphia (OPA, L&I), OpenDataPhilly" when city records were joined (show `a` as the attribution).
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
    ── 2.0.0 accuracy block (appended to the same props array, index 16 on; an old client reads the first 16 names and ignores the rest; trailing zeros dropped) ──
      ty typology (TYPOLOGY): 0 unknown 1 rowhouse 2 twin/semi-detached 3 detached house 4 low-rise apartments (<=4 st) 5 mid-rise (5-11 st) 6 high-rise tower (>=12 st / >=40 m)
         7 commercial storefront row 8 institutional/civic 9 industrial/warehouse 10 religious 11 parking/garage 12 office 13 hotel 14 school/university 15 hospital 16 mixed use
         (from the city's parcel record when one matched — OPA building_code_description / category_code_description — else OSM building=* + shape + height)
      yr year built (0 unknown; OPA year_built, else OSM start_date / building:start_date)
      er era (ERAS): 0 unknown 1 colonial/federal (<1830) 2 Victorian (1830-1899) 3 early modern (1900-1945) 4 postwar (1946-1979) 5 contemporary (1980+)
      st stories (a recorded count, 0 unknown; `lv` above stays the count to DRAW, filled in when nothing is recorded)
      ss stories source: 0 none 1 OSM building:levels 2 city parcel (OPA number_stories) 3 Overture num_floors 4 derived from the height (h / 3.3)
      hs height source of `h`: 0 none 1 OSM height 2 city building footprints (L&I max_hgt/approx_hgt) 3 Overture 4 stories x 3.3 (+ roof) 5 guess (footprint + kind)
      fr frontage in units (0.1 m): the lot's street frontage (OPA frontage ft, else the length of the front edge `fe`); 0 unknown
      by window bays across the front (estimated: fr / ~1.9 m for houses, / ~3 m otherwise, 1..40; 0 unknown)
      pe party-wall EDGE bitmask: bit i set when ring edge i (vertex i -> i+1, the last edge closes the ring; ring as decoded, before holes) lies along another footprint
         (>= 50% of its length within 0.5 m of a neighbour's edge) — draw it blank (no windows, no cornice return); edges >= 31 are never flagged
      fe front edge: 1 + index of the ring edge that faces the street (the edge whose outward normal points at the nearest highway, longest such on ties); 0 unknown
      pw party walls seen from the street (standing in the street, facing fe): 1 shared on the left 2 shared on the right 4 rear shared 8 known free-standing (no edge shared)
      pc roof pitch class: 0 unknown 1 flat 2 low pitch (<20 deg; skillion/shed/low gabled) 3 steep (gabled/hipped/gambrel/... or roof:angle >= 20) 4 mansard 5 dome/onion/cone/spire
      rd roof:direction + 1 (degrees, 0 unknown)
      cf provenance / confidence bits: 1 matched to a city parcel record 2 ... by address (else point-in-polygon) 4 year recorded (not estimated) 8 height measured (hs 1-3)
         16 colour from data (OSM/Overture) 32 material from data (OSM) 64 roof shape or colour from data 128 stories recorded (ss 1-3)
      ar architect (string)  hr heritage (string: "heritage=<n>", "nrhp=<ref>", "phlrhp" joined by ";")  wp wikipedia (string "en:Title")
      sy architectural style (string, Wikidata P149 labels: "Second Empire architecture")
      tp top height in units: the highest point known (its building:parts, Wikidata P2048 incl. spires, the city footprint's max_hgt) — >= h; 0 = h
      (codes added with Wikidata: hs 6 Wikidata P2048, ss 5 Wikidata P1101; yr from Wikidata P571 inception wins over OSM start_date and the parcel's year; a Wikidata
       instance-of (P31) that names a kind — courthouse, church, Masonic temple, skyscraper, hotel... — wins over the parcel's code and OSM's building=*)
      ex exterior condition of the city record (OPA exterior_condition: 1 new/rehabbed 2 above average 3 ... 4 average 5 below average 6 vacant 7 sealed/compromised; 0 unknown)
  r highways [line, props]  (RFIELDS): hw highway=*  nm name  ln lanes  wd width (units)  ow oneway (0, 1 forward, 2 reverse)  sw sidewalk  cy cycleway  sf surface  ms maxspeed
      lt lit (0 unknown, 1 yes, 2 no)  sl/sr sidewalk left/right ("yes"|"no"|"separate"...)  cl/cr cycleway left/right  br bridge 1  tn tunnel 1  la layer
  a areas [ring, props(, holes)] (AFIELDS): k leisure=park|pitch|playground|garden|... / "parking" / landuse  nm name  sp sport  sf surface
  w barriers [line, props] (WFIELDS): k fence|wall|hedge|retaining_wall|guard_rail|...  ht height (units)  mt material
  l tree rows [line, props] (LFIELDS): sp species/genus  lf leaf_type
  t trees, flat 4-tuples x, y, species, leaf      f furniture, flat 4-tuples x, y, kind, dir   (kind: street_lamp traffic_signals crossing stop bus_stop bench bicycle_parking
  waste_basket post_box fire_hydrant; dir = compass bearing the thing faces/controls + 1, 0 = unknown: from direction=* or forward/backward along the way)
  p storefront signs / POIs with a name, flat 5-tuples x, y, name, cat, ad       e entrances and doors, flat 3-tuples x, y, kind ("entrance=main", "door=hinged")
    ── 2.0.1 water (palace_street_water.py; appended keys an old client ignores) ──
  q water pieces [ring, [k, nm, h]] cut PER CELL (unlike buildings): outer rings counter-clockwise, islands (h 1) clockwise, the union is the non-zero rule
  v waterways [line, [k, wd]]   o water points, flat 3-tuples x, y, kind ("fountain")   k piers / quays / bridges [ring or line, [k, closed, wd]]
  (natural=wood/scrub/grassland/wetland/heath and landuse=meadow/forest join `a`; water is written to the in-bounds cells and those within 600 m of them)

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

BFIELDS = ("k", "lv", "h", "bc", "bm", "rs", "rc", "rm", "rl", "nm", "ad", "po", "sd", "wd", "fl", "mh",
           "ty", "yr", "er", "st", "ss", "hs", "fr", "by", "pe", "fe", "pw", "pc", "rd", "cf", "ar", "hr", "wp", "ex", "sy", "tp")       # 16..: the accuracy block (see the docstring)
TYPOLOGY = ("unknown", "rowhouse", "twin", "detached", "lowrise_apts", "midrise", "highrise", "storefront_row", "civic", "industrial", "religious", "parking", "office", "hotel",
            "school", "hospital", "mixed_use")
ERAS = ("unknown", "colonial_federal", "victorian", "early_modern", "postwar", "contemporary")
RFIELDS = ("hw", "nm", "ln", "wd", "ow", "sw", "cy", "sf", "ms", "lt", "sl", "sr", "cl", "cr", "br", "tn", "la")
AFIELDS = ("k", "nm", "sp", "sf")
WFIELDS = ("k", "ht", "mt")
LFIELDS = ("sp", "lf")
_BSTR = {"k", "rs", "rm", "nm", "ad", "po", "sd", "wd", "ar", "hr", "wp", "sy"}                     # (bc / rc are rgb565 ints, bm a material code; wd: wikidata here, a NUMBER (width) in a highway)
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
        '  way[landuse~"^(grass|recreation_ground|village_green)$"]%s;' % b,
        '  nwr[place~"^(neighbourhood|suburb|quarter)$"][name]%s;' % b, ");", "out geom;"])


def _tile_path(cache_dir, tb):
    return Path(cache_dir) / ("street-%.4f_%.4f_%.4f_%.4f.json" % tuple(tb)) if cache_dir else None


def fetch(bbox, cache_dir=None, offline: bool = False, log=None, scope=None) -> dict:
    """The street answers of the box, tile by tile, each cached as street-<tile>.json and never asked for again. Polite: a pause between fetched tiles, a failed tile
    waits and after two failures in a row nothing more is asked this time. offline: the cache only. Returns the merged answer plus "missing" (the tiles not fetched)."""
    raws, missing, fails, asked = [], [], 0, False
    for tb in pmap.tile_boxes(bbox, *STREET_TILE):
        if scope is not None and not scope.tile_ok(tb):          # out of bounds (palace_ride_real.Scope): nothing is asked for it
            continue
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


def buildings(bbox, cache_dir=None, offline: bool = False, log=None, scope=None) -> dict:
    """The building tiles (bld-<tile>.json) the fill-in cached, one by one through palace_map.fetch_buildings (a cached tile costs nothing); only the tiles in bounds with a scope."""
    raws = [pmap.fetch_buildings(tb, cache_dir=cache_dir, offline=offline, log=log) for tb in pmap.tile_boxes(bbox, *pmap.BLD_TILE)
            if scope is None or scope.tile_ok(tb)]
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
PLACES = {"neighbourhood": 1, "suburb": 2, "quarter": 3}      # place=* kinds that name an area people call their neighbourhood (manifest "pl": the HUD's real area label)
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
    trees, furn, poi, door, hw, areas, bars, rows, places = [], [], [], [], [], [], [], [], []
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
        if t.get("place") in PLACES and t.get("name"):
            rings = [r for r, inner in pmap._rings_of(e) if not inner and len(r) >= 3] if (e.get("geometry") or e.get("members")) else []
            c = pmap._center(e)
            if c is not None or rings:
                places.append((i, str(t["place"]), str(t["name"]), c, rings))
            continue
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
    return {"trees": trees, "furn": furn, "poi": poi, "door": door, "hw": hw, "areas": areas, "barriers": bars, "rows": rows, "places": places}


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


MAX_RING = 120                 # vertices kept of a place polygon (a stride sample: it only names the area under the walker)


def _places(fr, places):
    """[[name, kind code, x, y, [x0,y0,x1,y1,..] or 0]] in metres east/north of the origin: a place's point (its node or the middle of its outline) and, when OSM draws it, its outline."""
    out = []
    for _i, kind, name, c, rings in sorted(places, key=lambda p: (p[2], p[0])):
        ring = max(rings, key=len) if rings else None
        flat = 0
        if ring:
            step = max(1, -(-len(ring) // MAX_RING))
            pts = [fr.xy(la, lo) for la, lo in ring[::step]]
            flat = [round(v * Q, 1) for p in pts for v in p]
            if c is None:
                c = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
        X, Y = fr.xy(c[0], c[1])
        out.append([name, PLACES[kind], round(X * Q, 1), round(Y * Q, 1), flat])
    return out


GROUP = 2                      # cells per shard side (a shard is a 1000 m x 1000 m square of cells)
HS_GUESS = 5
_HOUSES = (1, 2, 3)


def _roof_dir(t):
    v = str(t.get("roof:direction") or "").strip().lower()
    if not v:
        return 0
    if v in _CARD:
        return _CARD[v] + 1
    x = _fnum(v)
    return int(round(x)) % 360 + 1 if x is not None else 0


def _heritage(t):
    out = []
    if t.get("heritage"):
        out.append("heritage=%s" % t["heritage"])
    if t.get("ref:nrhp"):
        out.append("nrhp=%s" % t["ref:nrhp"])
    if t.get("heritage:operator") and not t.get("ref:nrhp"):
        out.append("op=%s" % t["heritage:operator"])
    if t.get("historic") and t.get("historic") not in ("no",):
        out.append("historic=%s" % t["historic"])
    return ";".join(out)


def _accuracy(fr, recs, st, preset, city, report):
    """The accuracy block of every building record (palace_street_acc): {"h" metres or 0, "lv" stories to draw or 0, + every BFIELDS[16:] name}."""
    from . import palace_street_acc as acc
    philly = preset == "philadelphia"
    whole = [i for i, r in enumerate(recs) if not r[4]]
    pw_ = acc.party_walls([recs[i][1] for i in whole])
    mask, nbs = {}, {}
    for j, i in enumerate(whole):
        mask[i], nbs[i] = pw_[j][0], {whole[x] for x in pw_[j][1]}
    roads = []
    for _i, ll, t, _n in st["hw"]:
        if t.get("highway") in acc.ROADS:
            p = [fr.xy(la, lo) for la, lo in ll]
            roads += [(p[m][0], p[m][1], p[m + 1][0], p[m + 1][1]) for m in range(len(p) - 1) if p[m] != p[m + 1]]
    fe_ = acc.front_edges([recs[i][1] for i in whole], roads, [mask[i] for i in whole])
    fe = {i: fe_[j] for j, i in enumerate(whole)}
    ci = acc.CityIndex(fr.xy, (city or {}).get("opa"), (city or {}).get("lif")) if city and ((city.get("opa") or city.get("lif"))) else None
    from . import palace_street_wikidata as pwd
    wdi = (city or {}).get("wd") or {}
    wpts: dict = {}
    for la, lo, q in (city or {}).get("wdp") or ():
        if q in wdi:
            X, Y = fr.xy(la, lo)
            wpts.setdefault((X // acc.GRID, Y // acc.GRID), []).append((X, Y, q))
    # building:parts -> the outline they stand in (the tallest part is the outline's top)
    wgrid: dict = {}
    for i in whole:
        p = recs[i][1]
        for gx in range(min(q[0] for q in p) // acc.GRID, max(q[0] for q in p) // acc.GRID + 1):
            for gy in range(min(q[1] for q in p) // acc.GRID, max(q[1] for q in p) // acc.GRID + 1):
                wgrid.setdefault((gx, gy), []).append(i)
    ptop: dict = {}                                             # outline -> the top of its tallest part (a spire, a tower): tp
    pbody: dict = {}                                            # outline -> the top of its tallest BODY part (>= 25 % of the outline): h
    for i, r in enumerate(recs):
        if not r[4]:
            continue
        ph = _metres(r[3].get("height"))
        if not ph or ph <= 0:
            continue
        for j in wgrid.get((r[6] // acc.GRID, r[7] // acc.GRID), ()):
            if _pip(r[6], r[7], recs[j][1]):
                ptop[j] = max(ptop.get(j, 0.0), ph)
                if _area_m2(r[1]) >= 0.25 * _area_m2(recs[j][1]):
                    pbody[j] = max(pbody.get(j, 0.0), ph)
                break
    out = []
    for n_, (key, pts, holes, t, part, k, cx, cy) in enumerate(recs):
        area = _area_m2(pts)
        cf = 0
        o = lf = None
        if ci is not None and not part:
            ids = ci.by_address(t, cx, cy)
            o = acc.pick_opa([ci.opa[i] for i in ids]) if ids else None
            if o is not None:
                cf |= acc.CF_PARCEL | acc.CF_ADDR
            else:
                ids = ci.opa_in(pts, _pip)
                o = acc.pick_opa([ci.opa[i] for i in ids]) if ids else None
                if o is not None:
                    cf |= acc.CF_PARCEL
            lids = ci.lif_in(pts, _pip)
            if lids:
                lf = max((ci.lif[i] for i in lids), key=lambda r: (r.get("ar") or 0, r["ah"], r["lat"]))
        oty, ost, half, exact = acc.opa_typology(o["bc"], o.get("bcn"), o.get("cat")) if o else (0, 0, False, False)
        # Wikidata: the item OSM names, else one Wikidata places inside the outline
        w = None
        if not part:
            q = str(t.get("wikidata") or "").split(";")[0].strip()
            w = wdi.get(q)
            if w is None and wpts:
                x0, x1, y0, y1 = min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)
                for gx in range(x0 // acc.GRID, x1 // acc.GRID + 1):
                    for gy in range(y0 // acc.GRID, y1 // acc.GRID + 1):
                        for X, Y, q2 in sorted(wpts.get((gx, gy), ())):
                            if w is None and x0 <= X <= x1 and y0 <= Y <= y1 and _pip(X, Y, pts) and pwd.is_building(wdi[q2]):
                                w = wdi[q2]
        # height: OSM, unless the city's (LiDAR) footprint height says it is far too low (a big building drawn as its podium); a part-less outline's parts' top
        h, hs = _metres(t.get("height")), 0
        if h and h > 0:
            hs = acc.HS_OSM
            if lf and lf.get("ah", 0) > 2 and h < 0.6 * lf["ah"] and area > 300:
                h, hs = lf["ah"], acc.HS_CITY
        elif n_ in pbody:
            h, hs = pbody[n_], acc.HS_OSM
        elif lf and lf.get("ah", 0) > 2:
            h, hs = lf["ah"], acc.HS_CITY
        elif w and w.get("h"):
            h, hs = w["h"], 6
        # stories
        s_, ss = _int(t.get("building:levels")), 0
        if s_:
            ss = acc.SS_OSM
        elif w and w.get("fl"):
            s_, ss = w["fl"], 5
        elif o and (o.get("st") or (ost and exact)):
            s_, ss = (o.get("st") or ost), acc.SS_CITY
        if not hs and s_:
            h, hs = round(s_ * 3.3 + (1.0 if s_ > 1 else 0.0) + (2.0 if half else 0.0), 1), acc.HS_STORIES
        # year
        yr = (w or {}).get("yr") or sty_year(t.get("start_date") or t.get("building:start_date") or t.get("construction_date"))
        if yr:
            cf |= acc.CF_YEAR
        elif o and o.get("yr"):
            yr = o["yr"]
            cf |= 0 if o.get("yre") else acc.CF_YEAR
        # typology
        nb = nbs.get(n_, set())
        twin = len(nb) == 1 and nbs.get(next(iter(nb)), set()) == {n_}
        ty = acc.choose_typology(oty, acc.osm_typology(t, area, h or 0.0, s_ or 0, len(nb), twin, philly), t.get("building") or t.get("building:part"))
        wty = pwd.typology(w) if w else 0
        if wty:
            ty = wty
        if yr and not w and not (cf & acc.CF_YEAR and yr == sty_year(t.get("start_date") or t.get("building:start_date") or t.get("construction_date"))) \
                and (t.get("ref:nrhp") or t.get("heritage")) and yr > 1975:
            yr = 0                                                  # a listed historic building "built" after 1975: the parcel's record is of something else
            cf &= ~acc.CF_YEAR
        tall = (h or 0) >= 40 or (s_ or 0) >= 12
        if ty in (acc.TY["lowrise_apts"], acc.TY["midrise"]) and tall:
            ty = acc.TY["highrise"]
        elif ty == acc.TY["lowrise_apts"] and ((s_ or 0) >= 5 or (h or 0) >= 17):
            ty = acc.TY["midrise"]
        elif ty == acc.TY["rowhouse"] and len(nb) == 1 and twin and not oty:
            ty = acc.TY["twin"]
        # front, party walls, frontage, bays
        m = mask.get(n_, 0)
        f = fe.get(n_, -1)
        pw = acc.side_flags(pts, f, m) if not part else 0
        frm = 0.0
        if o and ty in (1, 2, 7) and 2 < (o.get("fr") or 0) < 80:
            frm = o["fr"] * 0.3048
        elif f >= 0:
            (ax, ay), (bx, by) = pts[f], pts[(f + 1) % len(pts)]
            frm = math.hypot(bx - ax, by - ay) * Q
        by_ = max(1, min(40, int(round(frm / (1.6 if ty in _HOUSES else 3.0))))) if frm else 0
        # roof
        pc = acc.pitch_of(t)
        if pc or t.get("roof:colour"):
            cf |= acc.CF_ROOF
        if not pc and ty:
            pc = (4 if (half and ty == 1) else 3) if (ty in (2, 3, 10) or half) else 1
        if hs in (1, 2, 3, 6):
            cf |= acc.CF_HEIGHT
        if ss in (1, 2, 3, 5):
            cf |= acc.CF_STORIES
        if t.get("building:colour"):
            cf |= acc.CF_COLOUR
        if t.get("building:material"):
            cf |= acc.CF_MATERIAL
        a = {"h": h or 0.0, "lv": s_ or 0, "ty": ty, "yr": yr or 0, "er": acc.era_of(yr), "st": s_ or 0, "ss": ss, "hs": hs,
             "fr": int(round(frm / Q)) if frm else 0, "by": by_, "pe": m if not part else 0, "fe": f + 1 if (f >= 0 and not part) else 0, "pw": pw, "pc": pc,
             "rd": _roof_dir(t), "cf": cf, "ar": str(t.get("architect") or (w or {}).get("ar") or ""), "hr": ";".join(x for x in (_heritage(t), ("wd=" + w["her"]) if (w or {}).get("her") else "") if x),
             "wp": str(t.get("wikipedia") or ""), "ex": int((o or {}).get("ex") or 0), "sy": str((w or {}).get("sy") or "")}
        top = max([h or 0.0, ptop.get(n_, 0.0), (w or {}).get("h") or 0.0, (lf or {}).get("mh") or 0.0])
        a["tp"] = int(round(top / Q)) if top > (h or 0.0) + 0.5 else 0
        out.append(a)
    return out


def sty_year(v):
    from .palace_street_style import year_of
    y = year_of(v)
    return y if y and 1600 < y <= 2100 else 0


def _coverage(blk, recs, city):
    """{"n": buildings, field: {"any": %, source: %}} — the build report's coverage table (whole buildings, not parts)."""
    idx = [i for i, r in enumerate(recs) if not r[4]]
    n = len(idx) or 1

    def pct(c):
        return round(100.0 * c / n, 1)
    rep = {"n": len(idx), "parts": len(recs) - len(idx)}
    hs = {}
    ss = {}
    for i in idx:
        hs[blk[i]["hs"]] = hs.get(blk[i]["hs"], 0) + 1
        ss[blk[i]["ss"]] = ss.get(blk[i]["ss"], 0) + 1
    rep["height_src"] = {["none", "osm", "city", "overture", "stories", "guess", "wikidata"][k]: pct(v) for k, v in sorted(hs.items())}
    rep["stories_src"] = {["none", "osm", "city", "overture", "from_height", "wikidata"][k]: pct(v) for k, v in sorted(ss.items())}
    for nm, test in (("typology", lambda a: a["ty"] > 0), ("year", lambda a: a["yr"] > 0), ("year_recorded", lambda a: a["cf"] & 4), ("parcel", lambda a: a["cf"] & 1),
                     ("parcel_by_address", lambda a: a["cf"] & 2), ("party_wall", lambda a: a["pe"] > 0), ("front_edge", lambda a: a["fe"] > 0),
                     ("frontage", lambda a: a["fr"] > 0), ("roof_data", lambda a: a["cf"] & 64), ("colour_data", lambda a: a["cf"] & 16),
                     ("material_data", lambda a: a["cf"] & 32), ("architect", lambda a: a["ar"]), ("heritage", lambda a: a["hr"]), ("style", lambda a: a["sy"]), ("top_height", lambda a: a["tp"]), ("condition", lambda a: a["ex"])):
        rep[nm] = pct(sum(1 for i in idx if test(blk[i])))
    tys = {}
    for i in idx:
        tys[blk[i]["ty"]] = tys.get(blk[i]["ty"], 0) + 1
    rep["typology_mix"] = {TYPOLOGY[k]: pct(v) for k, v in sorted(tys.items())}
    rep["notes"] = list((city or {}).get("notes") or [])
    return rep


def build(bbox, bld_raw: dict, street_raw: dict, preset=None, scope=None, city=None, report=None, water_raw=None):
    """(manifest, shards) for the box: shards {id: {"S": [...], "c": {cell key: cell}}} (one per GROUP x GROUP cells, each with its own string table, named by the hash
    of its text) and the manifest {header, "f": {id: bytes}, "c": {cell key: id}}. city: {"opa": rows, "lif": rows, "notes": [..]} (palace_street_city; None = OSM only).
    report: an optional dict the build fills with coverage counts (palace_street_acc.coverage)."""
    from . import palace_street_style as sty
    from . import palace_street_acc as acc
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

    recs = []
    for key, ring, holes, t in sorted(parse_buildings(bld_raw), key=lambda b: b[0]):
        pts = quant(ring)
        if len(pts) < 3:
            continue
        cx, cy = sum(p[0] for p in pts) // len(pts), sum(p[1] for p in pts) // len(pts)
        if not fr.inside(cx, cy):
            continue
        recs.append((key, pts, holes, t, "building" not in t, fr.cell(cx, cy), cx, cy))
    blk = _accuracy(fr, recs, st, preset, city, report)
    for n_, (key, pts, holes, t, part, k, cx, cy) in enumerate(recs):
        a = blk[n_]
        h = a["h"]
        mh = _metres(t.get("min_height"))
        if not mh and _fnum(t.get("building:min_level")):
            mh = _fnum(t.get("building:min_level")) * 3.3
        res = sty.resolve(preset, t, _area_m2(pts), h or 0.0, a["lv"], sty.seed_of(key), commercial=(not part) and (bool(_poi_cat(t)) or has_poi(pts)),
                          ty=a["ty"], year=a["yr"])
        if not a["hs"]:
            a["hs"] = HS_GUESS if res["h"] else 0
        if not a["st"] and a["hs"] in (1, 2, 3) and h:              # a measured height, no recorded count: stories from the height (tall old floors)
            a["st"], a["ss"] = max(1, int(round(h / acc.storey_m(a["ty"], a["er"])))), 4
            if not _int(t.get("building:levels")):
                res["lv"] = a["st"]

        props = _trim(["%s%s" % ("p:" if part else "", (t.get("building:part") if part else t.get("building")) or "yes"),
                       res["lv"], int(round(res["h"] / Q)) if res["h"] else 0, res["bc"], res["bm"], str(t.get("roof:shape") or ""), res["rc"], str(t.get("roof:material") or ""),
                       _int(t.get("roof:levels")), str(t.get("name") or ""), _addr(t), _poi_cat(t), str(t.get("start_date") or t.get("building:start_date") or ""),
                       str(t.get("wikidata") or ""), res["fl"], int(round(mh / Q)) if mh and mh > 0 else 0]
                      + [a[f] for f in BFIELDS[16:]])
        rec = [_delta(local(pts, k)), props]
        hs = [_delta(local(q, k)) for q in (quant(h_) for h_ in holes) if len(q) >= 3]
        if hs:
            rec.append(hs)
        put(k, "b", rec)
    if report is not None:
        report.update(_coverage(blk, recs, city))

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
    # ── 2.0.1 water (palace_street_water.py): q water pieces cut per cell, v waterways, o fountains, k piers/quays/bridges; the green land along the banks joins `a` ──
    wcells: dict = {}
    if water_raw:
        from . import palace_street_water as pw
        wp = pw.parse(water_raw)
        for key, ring, holes, t in sorted(wp["green"], key=lambda a: (round(a[1][0][0], 7), round(a[1][0][1], 7), a[0])):
            pts = quant(ring)
            if len(pts) < 3:
                continue
            cx, cy = sum(p[0] for p in pts) // len(pts), sum(p[1] for p in pts) // len(pts)
            if not fr.inside(cx, cy):
                continue
            k = fr.cell(cx, cy)
            rec = [_delta(local(pts, k)), _trim([t["_kind"], str(t.get("name") or ""), "", ""])]
            hs = [_delta(local(q, k)) for q in (quant(h_) for h_ in holes) if len(q) >= 3]
            if hs:
                rec.append(hs)
            put(k, "a", rec)

        def wput(k, key, rec):
            wcells.setdefault("%d,%d" % k, {}).setdefault(key, []).append(rec)

        def wflat(k, key, items):
            wcells.setdefault("%d,%d" % k, {}).setdefault(key, []).extend(items)
        pw.add(fr, wp, wput, wflat, lambda ll, rec_of: list(cut(ll, rec_of)), quant)

    ib = None
    if scope is not None:                                       # out of bounds: a cell that does not touch the region (+ buffer) is not written, the manifest says what is
        keep = scope.cells(CS * Q, fr.nx, fr.ny)
        cells = {k: v for k, v in cells.items() if tuple(int(t) for t in k.split(",")) in keep}
        if wcells:                                              # water reaches WATER_REACH_M past the region (the river beside an in-bounds district)
            from . import palace_street_water as pw
            wkeep = pw.reach(scope, keep, fr.nx, fr.ny, CS * Q)
            wcells = {k: v for k, v in wcells.items() if tuple(int(t) for t in k.split(",")) in wkeep}
        runs: dict = {}
        for ix, iy in sorted(keep, key=lambda c: (c[1], c[0])):
            r = runs.setdefault(iy, [])
            if r and r[-1][1] == ix - 1:
                r[-1][1] = ix
            else:
                r.append([ix, ix])
        ib = {"b": int(scope.buffer), "r": [[iy, a, b] for iy in sorted(runs) for a, b in runs[iy]]}
    for ck, wv in wcells.items():
        cells.setdefault(ck, {}).update(wv)
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
    pl = _places(fr, st["places"])
    from . import palace_street_city as pcity
    src = [dict(pcity.SOURCES["osm"], k="osm")]
    att = ATTRIBUTION
    for kk in ("opa", "lif"):
        if (city or {}).get(kk):
            src.append(dict(pcity.SOURCES[kk], k=kk, rows=len(city[kk])))
    if (city or {}).get("wd"):
        from . import palace_street_wikidata as pwd
        src.append(dict(pwd.SOURCE, rows=len(city["wd"])))
    if any(x.get("k") in ("opa", "lif") for x in src):
        att += "; City of Philadelphia (OPA, L&I), OpenDataPhilly"
    manifest = {"v": VERSION, "a": att, "o": [fr.s, fr.w, fr.n, fr.e], "q": Q, "cs": CS, "kx": round(fr.kx, 3), "ky": KY, "n": [fr.nx, fr.ny], "g": GROUP,
                "preset": preset, "f": {k: files[k] for k in sorted(files)}, "c": cmap}
    if pl:
        manifest["pl"] = pl                                     # real neighbourhood / suburb / quarter names: [name, kind code, x m, y m, flat polygon metres or 0]
    if ib is not None:
        manifest["ib"] = ib
    manifest["src"] = src                                       # the sources, their licences and attribution (+ notes on what failed): [{k, n, l, a(, rows)}]
    notes = list((city or {}).get("notes") or [])
    if notes:
        manifest["sn"] = notes                                     # the in-bounds extent: the street cells [iy, ix0, ix1] runs of the region (with b metres of buffer)
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


# Referenced files the last blobs() could not find in the cache (or found damaged): "palace-street-<h>.json" / "s-<h>.json". publish_static reads it
# (and turns what is neither in the cache nor already on the site into a LAST_STALE note) — a publish must never drop a palace's street data silently.
LAST_MISSING: list = []
RECENT_DAYS = 14                                            # a manifest younger than this is kept even when no page names it (a page already stored in Firestore may)


def street_hash(palace) -> str:
    """The manifest hash (12 hex) a brief.palace dict (data_z packed) or an unpacked palace map names in m["street"]["h"]; "" when it names none."""
    try:
        m = palace
        if isinstance(palace, dict) and palace.get("data_z"):
            from .palace import unpack
            m = (unpack(palace["data_z"]) or {}).get("map") or {}
        elif isinstance(palace, dict) and isinstance(palace.get("map"), dict):
            m = palace["map"]
        h = ((m or {}).get("street") or {}).get("h")
    except Exception:                                       # noqa: BLE001 — a palace that cannot be read names nothing
        return ""
    return h if isinstance(h, str) and re.fullmatch(r"[0-9a-f]{12}", h) else ""


def blobs(directory=None, referenced=None) -> list:
    """[(file name, text)] to publish: EVERY manifest a published page names (`referenced`: manifest hashes), plus for each box its newest manifest and any younger
    than RECENT_DAYS, and the shards any kept manifest names. Two palaces over one box therefore both keep their data. A file that does not match its hash is skipped;
    a referenced file the cache lacks is listed in LAST_MISSING (never silently dropped)."""
    import time
    LAST_MISSING.clear()
    refs = {h for h in (referenced or ()) if isinstance(h, str) and re.fullmatch(r"[0-9a-f]{12}", h)}
    d = Path(directory) if directory else blob_dir()
    valid: dict = {}
    if d.is_dir():
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
            valid[m.group(1)] = (mt, p.name, txt, man)
    newest: dict = {}
    for h, (mt, name, _t, man) in valid.items():
        box = tuple(man.get("o") or ())
        if box not in newest or (mt, name) > (valid[newest[box]][0], valid[newest[box]][1]):
            newest[box] = h
    now = time.time()
    kept = {h for h in valid if h in refs or h in newest.values() or now - valid[h][0] < RECENT_DAYS * 86400}
    out, want = [], {}
    for h in sorted(kept):
        _mt, name, txt, man = valid[h]
        out.append((name, txt))
        for sid in (man.get("f") or {}):
            want.setdefault(sid, set()).add(h)
    for h in sorted(refs - set(valid)):
        LAST_MISSING.append(file_name(h))
    for sid in sorted(want):
        try:
            txt = (d / file_name(sid)).read_text("utf-8")
        except OSError:
            txt = None
        if txt is not None and blob_hash(txt, 8) == sid:
            out.append((file_name(sid), txt))
        elif want[sid] & refs:
            LAST_MISSING.append(file_name(sid))
    return sorted(out)


def load(h: str, directory=None):
    """(manifest, {id: shard}) of a stored manifest hash (the reference reader the tests use)."""
    d = Path(directory) if directory else blob_dir()
    man = json.loads((d / file_name(h)).read_text("utf-8"))
    return man, {sid: json.loads((d / file_name(sid)).read_text("utf-8")) for sid in man["f"]}


LAST_REPORT: dict = {}                                       # the coverage report of the last make() (palace_street_acc fields, sources, notes)


def city_data(bbox, scope=None, offline: bool = False, log=None, directory=None):
    """{"opa": rows, "lif": rows, "notes": [...]} of the city's open data for the box (Philadelphia only; None elsewhere). Never fatal: a source that fails is absent
    and noted. ALTO_STREET_CITY=0 turns it off."""
    from . import palace_street_city as pcity
    from . import palace_street_style as sty
    if os.environ.get("ALTO_STREET_CITY", "1") == "0" or sty.preset_for(bbox) != "philadelphia":
        return None
    out = {"notes": [pcity.NOTES["overture"]]}
    for kk in ("opa", "lif"):
        rows, note = getattr(pcity, kk)(bbox, scope=scope, offline=offline, log=log, directory=directory)
        out[kk] = rows
        if note:
            out["notes"].append(note)
    return out


def wikidata_data(bbox, bld_raw, scope=None, offline: bool = False, log=None, directory=None):
    """{"wd": {qid: rec}, "wdp": [(lat, lon, qid)], "notes": [...]} — the Wikidata items the in-bounds buildings name (wikidata=*) and the buildings Wikidata places in
    the in-bounds part of the box. ALTO_STREET_WIKIDATA=0 turns it off. Never fatal."""
    from . import palace_street_wikidata as pwd
    if os.environ.get("ALTO_STREET_WIKIDATA", "1") == "0":
        return None
    fr = Frame(bbox)
    qids = set()
    for _k, ring, _h, t in parse_buildings(bld_raw):
        if t.get("wikidata"):
            X, Y = fr.xy(*ring[0])
            if scope is None or scope.contains(X * Q, Y * Q):
                qids.add(str(t["wikidata"]).split(";")[0].strip())
    pts, note1 = pwd.in_box(bbox, offline=offline, log=log, directory=directory)
    pts = [p for p in pts if scope is None or scope.contains(*(lambda X, Y: (X * Q, Y * Q))(*fr.xy(p[0], p[1])))]
    recs, note2 = pwd.items(sorted(qids | {p[2] for p in pts}), offline=offline, log=log, directory=directory)
    return {"wd": recs, "wdp": pts, "notes": [n for n in (note1, note2) if n]}


def make(bbox, cache_dir=None, offline: bool = False, log=None, directory=None, scope=None):
    """Fetch (cached), build and store the street data of the box. Returns (manifest hash, total bytes of the manifest and its shards) or None when the box has nothing."""
    try:
        city = city_data(bbox, scope=scope, offline=offline, log=log)
    except Exception as e:                                  # noqa: BLE001 — the city's data is a bonus, never a failure
        city = {"notes": ["city data: %s" % str(e)[:80]]}
    LAST_REPORT.clear()
    braw = buildings(bbox, cache_dir, offline, log, scope=scope)
    try:
        wd = wikidata_data(bbox, braw, scope=scope, offline=offline, log=log)
    except Exception as e:                                  # noqa: BLE001 — never fatal
        wd = {"notes": ["wikidata: %s" % str(e)[:80]]}
    if wd:
        city = dict(city or {})
        city["wd"], city["wdp"] = wd.get("wd") or {}, wd.get("wdp") or []
        city["notes"] = list(city.get("notes") or []) + list(wd.get("notes") or [])
    from . import palace_street_water as pw
    wraw = None if os.environ.get("ALTO_STREET_WATER", "1") == "0" else pw.fetch(bbox, cache_dir=cache_dir, offline=offline, log=log)
    man, shards = build(bbox, braw, fetch(bbox, cache_dir=cache_dir, offline=offline, log=log, scope=scope), scope=scope, city=city, report=LAST_REPORT, water_raw=wraw)
    if not man["c"]:
        return None
    h = store(man, shards, directory)
    return h, len(encode(man).encode("utf-8")) + sum(man["f"].values())


def attach(m: dict, bbox, cache_dir=None, offline: bool = False, scope=None) -> None:
    """Builds the street data for the map's box and records it on the page's map data: m["street"] = {"h": "<12 hex>"} (the manifest). Never fatal."""
    try:
        r = make(m.get("bbox") or bbox, cache_dir=cache_dir, offline=offline, scope=scope)
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
        d["frm"] = d["fr"] * q
        d["tpm"] = max(d["tp"] * q, d["hm"])
        d["typology"] = TYPOLOGY[d["ty"]] if 0 <= d["ty"] < len(TYPOLOGY) else "unknown"
        d["era"] = ERAS[d["er"]] if 0 <= d["er"] < len(ERAS) else "unknown"
        d["front"] = d["fe"] - 1 if d["fe"] else -1
        d["party"] = [i for i in range(min(31, len(d["ring"]))) if (d["pe"] >> i) & 1]
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
    from . import palace_street_water as pw
    out.update(pw.decode(c, S, ox, oy, q, line))
    for key_, width, names in (("t", 4, ("sp", "lf")), ("f", 4, ("kind", "dir")), ("p", 5, ("name", "cat", "ad")), ("e", 3, ("kind",))):
        a = c.get(key_, [])
        for i in range(0, len(a), width):
            d = {"x": (a[i] + ox) * q, "y": (a[i + 1] + oy) * q}
            for j, nm in enumerate(names):
                v = a[i + 2 + j]
                d[nm] = (v - 1 if v else None) if nm == "dir" else S[v]
            out[key_].append(d)
    return out
