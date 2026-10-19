"""Generic city set-up: everything a city preset (city_presets) holds, worked out from OpenStreetMap alone, so a
user can name a city the engine has never seen and the Mind Palace draws it by the same rules.

    bbox = bbox_for("Lyon")                         # Nominatim lookup + the size rule (5-8 km a side)
    raw  = fetch_city(bbox, cache_dir, names=[...]) # the engine's own Overpass query, tiled, reusing every cached tile
    disc = discover(bbox, cache_dir)                # one small tags-only query: neighbourhood names, notable places, towers
    p    = auto_params(merge(raw, disc), bbox, "Lyon")

auto_params -> {majors, landmarks, landmark_buildings, diagonals, parks, areas, transit} in the preset's format
(palace.set_up / set_up_palace take them as they are). The rules:

- majors: named streets of road class k <= 1, and k 2 streets with >= 1.5 km of street under one name, whose
  longest continuous course (city_avenues.chains) is >= 800 m; the 70 longest. Motorways are left to the grid
  (it keeps k 0 roads as majors itself).
- landmarks: named places tagged tourism / historic / a building / a place of worship ... that carry wikidata or
  wikipedia, ranked by prominence (how many languages name them, wikipedia, heritage, attraction), distinct
  (not within 150 m of a better one, not a station, park or neighbourhood name), the best 16.
- landmark_buildings: the towers (named buildings >= 120 m or >= 35 floors, tallest first, 8 at most) with
  their real floors / height kept as data, then the best landmarks that are buildings (6 at most).
- parks: named parks / gardens / squares >= 0.5 ha (the big ones are drawn anyway), the 24 biggest.
- areas: place=suburb (rank 1) / quarter (2) / neighbourhood (3) names inside the box; population >= 50,000
  lifts one rank, many-language names lift one; 120 at most.
- diagonals: city_domains.detect + city_avenues.classify: an avenue whose length is mostly "diagonal" pieces
  (off its domain's axes), >= 1.2 km; the 12 longest.
- transit: route relations in the box (subway / light rail / tram / train), one family per network and colour.
Nothing here edits the engine: it only picks the parameters the engine already takes.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

KM_LAT = 110.574
CELL = 0.0025                     # degrees: the coverage raster for cached tiles
TILE_LAT, TILE_LON = 0.02, 0.03   # degrees: a new tile (the scout's polite size)
POLITE_S = 2.0                    # seconds between two Overpass requests
MIN_SIDE_KM, MAX_SIDE_KM = 5.0, 8.0
TOWN_MIN_KM = 2.0
CITY_SIDE_KM = (6.0, 7.0)         # (north-south, east-west) of a big city's centre box

_CACHE_RX = re.compile(r"^osm-(-?\d+\.\d{4})_(-?\d+\.\d{4})_(-?\d+\.\d{4})_(-?\d+\.\d{4})(-light)?(?:-[0-9a-f]{8})?\.json$")


# ── the box ─────────────────────────────────────────────────────────────────
def km_box(lat, lon, ns_km, ew_km):
    dlat = ns_km / 2 / KM_LAT
    dlon = ew_km / 2 / (111.320 * math.cos(math.radians(lat)))
    return [round(lat - dlat, 5), round(lon - dlon, 5), round(lat + dlat, 5), round(lon + dlon, 5)]


def box_km(bbox):
    s, w, n, e = bbox
    return ((n - s) * KM_LAT, (e - w) * 111.320 * math.cos(math.radians((s + n) / 2)))


def size_rule(g) -> list:
    """A geocoder answer {lat, lon, bbox} -> the box to draw. A city bigger than 8 km: a 6 x 7 km box around its
    centre (Nominatim's point is the centre: city hall, the old town). A town: its own box, grown to at least
    2 km a side, at most 8."""
    lat, lon = float(g["lat"]), float(g["lon"])
    bb = g.get("bbox") or [lat, lon, lat, lon]
    ns, ew = box_km(bb)
    if max(ns, ew) > MAX_SIDE_KM:
        return km_box(lat, lon, *CITY_SIDE_KM)
    cl, cn = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    return km_box(cl, cn, min(MAX_SIDE_KM, max(TOWN_MIN_KM, ns)), min(MAX_SIDE_KM, max(TOWN_MIN_KM, ew)))


def bbox_for(place: str, area: str = "", geocode=None):
    """Nominatim lookup of the place (palace_map.geocode) and the size rule. None when the place is unknown."""
    if geocode is None:
        from .. import palace_map as pm
        geocode = pm.geocode
    g = geocode(", ".join(x for x in (area, place) if x))
    return size_rule(g) if g else None


# ── fetching (the engine's own query, cache first) ──────────────────────────
def cached_tiles(cache_dir):
    """[(bbox, light, path)] of every fetch_osm cache file in cache_dir (any landmark hash)."""
    out = []
    d = Path(cache_dir) if cache_dir else None
    if not d or not d.exists():
        return out
    for f in sorted(d.iterdir()):
        mt = _CACHE_RX.match(f.name)
        if mt:
            out.append((tuple(float(mt.group(i)) for i in range(1, 5)), bool(mt.group(5)), f))
    return out


def _points(bbox, step=CELL):
    """Sample points (cell centres) over a box, every `step` degrees."""
    s, w, n, e = bbox
    ny, nx = max(1, math.ceil((n - s) / step - 1e-9)), max(1, math.ceil((e - w) / step - 1e-9))
    return [(s + (n - s) * (i + .5) / ny, w + (e - w) * (j + .5) / nx) for i in range(ny) for j in range(nx)]


def _covers(b, p):
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def _meets(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def plan_tiles(bbox, cache_dir=None, allow_light=True):
    """-> (cached files to read, new tile boxes to fetch). A cached tile counts where it covers the box (a light tile
    too, unless allow_light is False); what is left is fetched in tiles of TILE_LAT x TILE_LON, each shrunk to the
    part it still has to cover (sampled every CELL degrees)."""
    have = [(b, lt, p) for b, lt, p in cached_tiles(cache_dir) if _meets(b, bbox) and (allow_light or not lt)]
    from .. import palace_map as pm
    need = []
    h = CELL / 2
    for tb in pm.tile_boxes(bbox, TILE_LAT, TILE_LON):
        open_ = [q for q in _points(tb) if not any(_covers(b, q) for b, _, _ in have)]
        if open_:
            need.append(tuple(round(v, 4) for v in (max(tb[0], min(q[0] for q in open_) - h), max(tb[1], min(q[1] for q in open_) - h),
                                                    min(tb[2], max(q[0] for q in open_) + h), min(tb[3], max(q[1] for q in open_) + h))))
    return [p for _, _, p in have], need


def _fetch_split(pm, tb, cache_dir, timeout, log, depth=0):
    try:
        t = time.time()
        raw = pm.fetch_osm(tb, cache_dir=cache_dir, timeout=timeout)
        if log:
            log("ok full %s %ds %d" % (tb, time.time() - t, len(json.dumps(raw))))
        return [raw]
    except RuntimeError as e:
        if log:
            log("FAIL full %s %s" % (tb, str(e)[:100]))
        if depth >= 2:
            raise
        s, w, n, e_ = tb
        ml, mn = round((s + n) / 2, 4), round((w + e_) / 2, 4)
        out = []
        for q in ((s, w, ml, mn), (s, mn, ml, e_), (ml, w, n, mn), (ml, mn, n, e_)):
            time.sleep(POLITE_S * 4)
            out += _fetch_split(pm, q, cache_dir, timeout, log, depth + 1)
        return out


RETRY_S = (30, 60)                # seconds before the second and third try of a small query (Overpass answers 500 under load)
NAMES_TILE = (0.02, 0.03)         # degrees: the names query is asked tile by tile (a whole city centre in one went unanswered)
NAMES_CHUNK = 40                  # names per request
_sleep = time.sleep               # tests replace this


def post_retry(query, timeout, log=None, sleep=None, retries=None):
    """palace_map._post_overpass (every server in turn), the whole round tried again after RETRY_S when no server
    answers. retries: how many of the RETRY_S waits to use (default all)."""
    from .. import palace_map as pm
    waits = RETRY_S[:len(RETRY_S) if retries is None else retries]
    for i in range(len(waits) + 1):
        try:
            return pm._post_overpass(query, timeout)
        except RuntimeError as e:
            if i == len(waits):
                raise
            if log:
                log("retry in %ds: %s" % (waits[i], str(e)[:100]))
            (sleep or _sleep)(waits[i])


def names_query(bbox, names, timeout=90) -> str:
    from .. import palace_map as pm
    b = "(%r,%r,%r,%r)" % tuple(float(v) for v in bbox)
    q = ["[out:json][timeout:%d];" % timeout, "("]
    q += ['  nwr["name"~"^%s$",i]%s;' % (pm._ql_regex(n), b) for n in names]
    return "\n".join(q + [");", "out geom;"])


def _names_path(cache_dir, bbox, names):
    return Path(cache_dir) / ("names-%.4f_%.4f_%.4f_%.4f-%s.json" % (tuple(float(v) for v in bbox) + (
        hashlib.sha1("\n".join(names).encode()).hexdigest()[:8],))) if cache_dir else None


def _names_piece(tb, names, cache_dir, timeout, log, depth=0) -> list:
    """One tile x one chunk of names (cached on its own, so a rerun asks only for what is missing); a piece no server
    answers is split in four once (each quarter tried one round), and raises RuntimeError if a quarter fails too."""
    path = _names_path(cache_dir, tb, names)
    if path is not None and path.exists():
        try:
            return [json.loads(path.read_text("utf-8"))]
        except (OSError, ValueError):
            pass
    try:
        raw = post_retry(names_query(tb, names, timeout), timeout, log, retries=None if depth == 0 else 0)
    except RuntimeError as e:
        if depth >= 1:
            raise
        if log:
            log("FAIL names %s %s — in quarters" % (tuple(tb), str(e)[:100]))
        s, w, n, e_ = tb
        ml, mn = round((s + n) / 2, 4), round((w + e_) / 2, 4)
        out = []
        for q in ((s, w, ml, mn), (s, mn, ml, e_), (ml, w, n, mn), (ml, mn, n, e_)):
            _sleep(POLITE_S)
            out += _names_piece(q, names, cache_dir, timeout, log, depth + 1)
        return out
    if log:
        log("ok names %s %d names %d elements" % (tuple(tb), len(names), len(raw.get("elements", []))))
    if path is not None:
        _store(path, raw)
    return [raw]


def fetch_names(bbox, names, cache_dir=None, timeout=90, log=None) -> dict:
    """The landmarks by name (the full query's last block, on its own, so the street tiles stay reusable), asked in
    NAMES_TILE tiles x NAMES_CHUNK names and merged (an element on a tile edge is kept once); cached whole as well."""
    from .. import palace_map as pm
    names = sorted({str(n) for n in names or () if n})
    if not names:
        return {"elements": []}
    path = _names_path(cache_dir, bbox, names)
    if path is not None and path.exists():
        return json.loads(path.read_text("utf-8"))
    tiles = pm.tile_boxes(bbox, *NAMES_TILE)
    chunks = [names[i:i + NAMES_CHUNK] for i in range(0, len(names), NAMES_CHUNK)]
    if len(tiles) == 1 and len(chunks) == 1:
        raws = _names_piece(tuple(float(v) for v in bbox), names, None, timeout, log)
    else:
        raws = []
        for k, (tb, ch) in enumerate((tb, ch) for tb in tiles for ch in chunks):
            if k:
                _sleep(POLITE_S)
            raws += _names_piece(tb, ch, cache_dir, timeout, log)
    raw = pm.merge_raw(*raws)
    if path is not None:
        _store(path, raw)
    return raw


def _store(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, separators=(",", ":")), "utf-8")
    os.replace(tmp, path)


def fetch_city(bbox, cache_dir=None, names=None, timeout=120, log=None, allow_light=True, offline=False,
               whole=True) -> dict:
    """The raw OSM of the box: every cached tile that covers it, then what is missing: first as one request
    (whole=True: the quick way when Overpass is calm), else in tiles fetched one at a time (a failed tile is split in
    four, twice); and the named landmarks. offline=True never touches the network (a missing tile raises
    RuntimeError)."""
    from .. import palace_map as pm
    files, need = plan_tiles(bbox, cache_dir, allow_light)
    if need and offline:
        raise RuntimeError("tiles not cached: %s" % need)
    raws = [json.loads(Path(f).read_text("utf-8")) for f in files]
    if whole and len(need) > 1:
        u = (min(t[0] for t in need), min(t[1] for t in need), max(t[2] for t in need), max(t[3] for t in need))
        try:
            t0 = time.time()
            raws.append(pm.fetch_osm(u, cache_dir=cache_dir, timeout=timeout))
            if log:
                log("ok full %s %ds (whole)" % (u, time.time() - t0))
            need = []
        except RuntimeError as e:
            if log:
                log("FAIL full %s (whole) %s" % (u, str(e)[:100]))
    for i, tb in enumerate(need):
        if i or files:
            time.sleep(POLITE_S)
        raws += _fetch_split(pm, tb, cache_dir, timeout, log)
    if names:
        nm = None
        if cache_dir:
            if _names_path(cache_dir, bbox, sorted({str(n) for n in names if n})).exists() or not offline:
                nm = fetch_names(bbox, names, cache_dir, log=log)
        elif not offline:
            nm = fetch_names(bbox, names, None, log=log)
        if nm is None:
            raise RuntimeError("landmark names not cached for %s" % (tuple(bbox),))
        raws.append(nm)
    return pm.merge_raw(*raws)


# ── discovery: one small tags-only query ────────────────────────────────────
def discover_query(bbox, timeout=90) -> str:
    b = "(%r,%r,%r,%r)" % tuple(float(v) for v in bbox)
    return "\n".join([
        "[out:json][timeout:%d];" % timeout,
        "(",
        '  node[place~"^(suburb|quarter|neighbourhood)$"][name]%s;' % b,
        '  rel[place~"^(suburb|quarter|neighbourhood)$"][name]%s;' % b,
        '  nwr[tourism~"^(attraction|museum|gallery|viewpoint|zoo|aquarium)$"][name][wikidata]%s;' % b,
        "  nwr[historic][name][wikidata]%s;" % b,
        "  nwr[building][name][wikidata]%s;" % b,
        '  nwr[amenity~"^(place_of_worship|townhall|university|theatre|library|arts_centre)$"][name][wikidata]%s;' % b,
        '  nwr[leisure~"^(stadium|park|garden)$"][name][wikidata]%s;' % b,
        '  nwr[man_made~"^(tower|obelisk|lighthouse)$"][name]%s;' % b,
        '  way[building][name](if: number(t["height"]) >= 120)%s;' % b,
        '  way[building][name](if: number(t["building:levels"]) >= 35)%s;' % b,
        '  rel[building][name](if: number(t["height"]) >= 120)%s;' % b,
        ");",
        "out tags center;",
    ])


def discover(bbox, cache_dir=None, timeout=90, log=None, offline=False) -> dict:
    """The discovery answer (cached as disc-<bbox>.json)."""
    path = Path(cache_dir) / ("disc-%.4f_%.4f_%.4f_%.4f.json" % tuple(float(v) for v in bbox)) if cache_dir else None
    if path is not None and path.exists():
        return json.loads(path.read_text("utf-8"))
    if offline:
        raise RuntimeError("discovery not cached for %s" % (tuple(bbox),))
    from .. import palace_map as pm
    t = time.time()
    raw = post_retry(discover_query(bbox, timeout), timeout, log)
    if log:
        log("ok disc %s %ds %d elements" % (tuple(bbox), time.time() - t, len(raw.get("elements", []))))
    if path is not None:
        _store(path, raw)
    return raw


# ── the rules ───────────────────────────────────────────────────────────────
def _plen(p):
    return sum(math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1]) for i in range(0, len(p) - 2, 2))


def _ring_area(r):
    a = 0.0
    for i in range(0, len(r) - 2, 2):
        a += r[i] * r[i + 3] - r[i + 2] * r[i + 1]
    return abs(a) / 2


def _num(v):
    try:
        return float(re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", str(v)).group(1))
    except (AttributeError, TypeError, ValueError):
        return None


def _latlon(e):
    if "lat" in e and "lon" in e:
        return float(e["lat"]), float(e["lon"])
    c = e.get("center")
    if c:
        return float(c["lat"]), float(c["lon"])
    g = [q for q in e.get("geometry") or [] if q]
    if g:
        return sum(q["lat"] for q in g) / len(g), sum(q["lon"] for q in g) / len(g)
    b = e.get("bounds")
    if b:
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    return None


def _in(bbox, ll):
    return ll is not None and bbox[0] <= ll[0] <= bbox[2] and bbox[1] <= ll[1] <= bbox[3]


def _dist_m(a, b):
    kx = 111320 * math.cos(math.radians(a[0]))
    return math.hypot((a[1] - b[1]) * kx, (a[0] - b[0]) * 110574)


def _langs(t):
    return sum(1 for k in t if k.startswith("name:") and len(k) <= 8)


_GENERIC = re.compile(r"^(park|garden|square|plaza|station|church|museum|tower|building|memorial|monument|statue|fountain)$", re.I)
_PLACE_RANK = {"suburb": 1, "quarter": 2, "neighbourhood": 3}


def majors_of(m, n_max=70):
    from . import city_avenues as ca
    tot, kmin, spell = {}, {}, {}
    for s in m.get("streets", []):
        n = s.get("n")
        if not n or s.get("t"):
            continue
        k = int(s.get("k", 9))
        tot[n] = tot.get(n, 0.0) + _plen(s["p"])
        kmin[n] = min(kmin.get(n, 9), k)
    sc = m.get("scale") or 1.0
    cand = [n for n in tot if kmin[n] == 1 or (kmin[n] == 2 and tot[n] >= 1500 * sc)
            or (kmin[n] == 3 and tot[n] >= 1800 * sc)]
    chains = ca.chains(m, None)
    from .palace_grid import norm
    longest = {nm: max((ca.plen(c) for c in cs), default=0.0) for nm, cs in chains.items()}
    keep = [n for n in cand if longest.get(norm(n), tot[n]) >= 800 * sc]
    keep.sort(key=lambda n: -tot[n])
    return keep[:n_max]


def landmarks_of(els, bbox, n_max=16, skip_names=()):
    """-> [(score, name, ll, element)] best first."""
    skip = {str(x).lower() for x in skip_names}
    rows = []
    for e in els:
        t = e.get("tags") or {}
        n = t.get("name")
        if not n or len(n) > 60 or _GENERIC.match(n) or n.lower() in skip:
            continue
        if t.get("place") or t.get("railway") or t.get("public_transport") or t.get("leisure") in ("park", "garden") \
                or t.get("type") in ("route", "boundary", "multilinestring") or t.get("route") or t.get("highway") \
                or t.get("historic") in ("memorial", "plaque", "milestone", "boundary_stone") or t.get("memorial") \
                or t.get("office") == "diplomatic" or t.get("amenity") in ("embassy", "grave_yard") \
                or t.get("diplomatic") or t.get("landuse") == "cemetery":
            continue
        if not (t.get("wikidata") or t.get("wikipedia")):
            continue
        ll = _latlon(e)
        if not _in(bbox, ll):
            continue
        langs = _langs(t)
        outline = e.get("type") in ("way", "relation")
        if not outline and langs < 5:
            continue                                   # a point (a plaque, an event) is a landmark only when famous
        sc = langs + 4 * bool(t.get("wikipedia")) + 3 * bool(t.get("heritage")) + 3 * outline \
            + 3 * (t.get("tourism") in ("attraction", "museum")) + 2 * bool(t.get("historic")) \
            + 2 * (_num(t.get("height")) or 0) / 100.0
        rows.append((sc, n, ll, e))
    rows.sort(key=lambda r: (-r[0], r[1]))
    out, seen = [], set()
    for r in rows:
        if r[1].lower() in seen or any(_dist_m(r[2], o[2]) < 150 for o in out):
            continue
        seen.add(r[1].lower())
        out.append(r)
        if len(out) >= n_max:
            break
    return out


def stations_of(els, bbox, n_max=3):
    """The city's main-line railway stations (named, trains calling, not a subway or tram stop) as landmark names, the
    biggest first: an outline or an intercity operator or a famous one, 200 m apart at least."""
    rows = []
    for e in els:
        t = e.get("tags") or {}
        n = t.get("name")
        if not n or len(n) > 60:
            continue
        if not (t.get("railway") == "station" or t.get("public_transport") == "station"):
            continue
        if t.get("subway") == "yes" or t.get("light_rail") == "yes" or t.get("tram") == "yes" or t.get("station") in ("subway", "light_rail", "tram"):
            continue
        if not (t.get("train") == "yes" or t.get("station") == "train" or re.search(r"amtrak|rail|nj ?transit|metra|marc|vre|mbta commuter", str(t.get("network") or "") + " " + str(t.get("operator") or ""), re.I)):
            continue
        ll = _latlon(e)
        if not _in(bbox, ll):
            continue
        sc = 3 * bool(re.search(r"amtrak", str(t.get("network") or "") + str(t.get("operator") or ""), re.I)) \
            + 2 * (e.get("type") in ("way", "relation")) + 2 * bool(t.get("wikidata") or t.get("wikipedia")) \
            + bool(re.search(r"station|terminal|union", n, re.I)) + (_num(t.get("height")) or 0) / 100.0
        rows.append((sc, n, ll))
    rows.sort(key=lambda r: (-r[0], r[1]))
    out, seen = [], set()
    for sc, n, ll in rows:
        k = re.sub(r"(?i)^philadelphia |\bstation\b|[^a-z0-9]", "", n.lower())
        if k in seen or any(_dist_m(ll, o[1]) < 200 for o in out):
            continue
        seen.add(k)
        out.append((n, ll))
        if len(out) >= n_max:
            break
    return [n for n, _ll in out]


def towers_of(els, bbox, n_max=8):
    """Named buildings >= 120 m or >= 35 floors, tallest first: [{name, floors?, height_m?}]."""
    rows = {}
    for e in els:
        t = e.get("tags") or {}
        n = t.get("name")
        if not n or not t.get("building") and not t.get("man_made"):
            continue
        h, lv = _num(t.get("height")), _num(t.get("building:levels"))
        if not ((h or 0) >= 120 or (lv or 0) >= 35):
            continue
        if not _in(bbox, _latlon(e)):
            continue
        key = n.lower()
        hh = h or (lv or 0) * 3.8
        if key not in rows or hh > rows[key][0]:
            rows[key] = (hh, {"name": n, **({"floors": int(lv)} if lv and 2 <= lv <= 250 else {}),
                              **({"height_m": round(h)} if h else {})})
    return [r for _, r in sorted(rows.values(), key=lambda r: -r[0])][:n_max]


def parks_of(m, n_max=24, min_ha=0.5):
    sc = (m.get("scale") or 1.0) ** 2
    area = {}
    for p in m.get("parks", []):
        n = p.get("n")
        if not n or _GENERIC.match(n):
            continue
        a = sum(_ring_area(r) for r in p.get("r") or []) / sc
        area[n] = area.get(n, 0.0) + a
    keep = [n for n, a in area.items() if a >= min_ha * 1e4]
    keep.sort(key=lambda n: -area[n])
    return keep[:n_max]


def areas_of(els, bbox, n_max=120):
    out = {}
    for e in els:
        t = e.get("tags") or {}
        r = _PLACE_RANK.get(t.get("place"))
        n = (t.get("name") or "").strip()
        ll = _latlon(e)
        if not r or not n or len(n) > 60 or not _in(bbox, ll):
            continue
        if (_num(t.get("population")) or 0) >= 50000:
            r -= 1
        if _langs(t) >= 8:
            r -= 1
        r = max(1, min(4, r))
        key = re.sub(r"\W+", "", n).lower()
        if key not in out or r < out[key]["rank"] or (e.get("type") == "node" and r == out[key]["rank"]):
            out[key] = {"name": n, "lat": round(ll[0], 4), "lon": round(ll[1], 4), "rank": r}
    rows = sorted(out.values(), key=lambda a: (a["rank"], a["name"]))
    return rows[:n_max]


def diagonals_of(m, majors=(), n_max=12, min_len=1200.0):
    from . import city_avenues as ca, city_domains
    try:
        det = city_domains.detect(m)
        recs = ca.classify(m, list(det.domains), majors, ())
    except Exception:                                   # noqa: BLE001 — a map the detector cannot read: no diagonals
        return []
    tot = {}
    for r in recs:
        L = sum(pc["len"] for pc in r["pieces"]) or 1.0
        dg = sum(pc["len"] for pc in r["pieces"] if pc["kind"] == "diagonal")
        if dg / L >= 0.5 and dg >= min_len * (m.get("scale") or 1.0):
            tot[r["n"]] = tot.get(r["n"], 0.0) + dg
    # spelled as the data spells it (the page matches norm() names, the labels the spelling)
    from .palace_grid import norm
    spell = {}
    for s in m.get("streets", []):
        if s.get("n"):
            spell.setdefault(norm(s["n"]), set()).add(s["n"])
    out = []
    for n in sorted(tot, key=lambda n: -tot[n])[:n_max]:
        out += sorted(spell.get(n, {n}))
    return out


_ROUTE_KIND = {"subway": "metro", "light_rail": "tram", "tram": "tram", "train": "rail", "monorail": "metro"}


def transit_of(els):
    """One family per (network, route kind, colour) for metro lines, per network for trains and trams:
    [{id, name, colour, kind, network, operator, route, refs}] (C2's data-driven reader takes this shape)."""
    fam = {}
    for e in els:
        t = e.get("tags") or {}
        if e.get("type") != "relation" or t.get("type") != "route" or t.get("route") not in _ROUTE_KIND:
            continue
        net = t.get("network") or t.get("operator") or ""
        if not net:
            continue
        kind = _ROUTE_KIND[t["route"]]
        col = (t.get("colour") or "").lower() if kind == "metro" else ""
        key = (net, t["route"], col)
        f = fam.setdefault(key, {"network": net, "operator": t.get("operator", ""), "route": t["route"], "kind": kind,
                                 "colour": t.get("colour") or "", "refs": set(), "n": 0})
        if t.get("ref"):
            f["refs"].add(t["ref"])
        f["n"] += 1
    out = []
    for (net, route, col), f in sorted(fam.items(), key=lambda kv: (-kv[1]["n"], kv[0])):
        refs = sorted(f["refs"], key=lambda r: (len(r), r))
        nm = net + (" " + "/".join(refs[:6]) if f["kind"] == "metro" and refs else "")
        fid = re.sub(r"[^a-z0-9]+", "", (net + "".join(refs[:3])).lower())[:12] or "t%d" % len(out)
        out.append({"id": fid, "name": nm, "colour": f["colour"], "kind": f["kind"], "network": net,
                    "operator": f["operator"], "route": route, "refs": refs if f["kind"] == "metro" else None})
    return out[:16]


def auto_params(raw, bbox, place, m=None, n_landmarks=16) -> dict:
    """Everything a preset holds, from raw OSM (the engine's fetch merged with discover()) alone."""
    from .. import palace_map as pm
    bbox = tuple(float(v) for v in bbox)
    if m is None:
        m = pm.build_map(raw, bbox, place=place, scale=1.0, majors=None, landmarks=None)
    els = raw.get("elements", [])
    majors = majors_of(m)
    parks = parks_of(m)
    areas = areas_of(els, bbox)
    lms = landmarks_of(els, bbox, n_landmarks, skip_names=[a["name"] for a in areas] + parks)
    towers = towers_of(els, bbox)
    tower_names = {t["name"].lower() for t in towers}
    blds = [dict(t) for t in towers]
    for _sc, n, _ll, e in lms:
        t = e.get("tags") or {}
        if len(blds) >= len(towers) + 6:
            break
        if e.get("type") in ("way", "relation") and (t.get("building") or t.get("historic") or t.get("amenity")) \
                and n.lower() not in tower_names:
            blds.append({"name": n})
    stn = [n for n in stations_of(els, bbox) if n.lower() not in tower_names and n.lower() not in {x[1].lower() for x in lms}]
    blds += [{"name": n} for n in stn]                  # the main-line stations are landmark buildings too (art: stations)
    landmarks = list(dict.fromkeys([n for _s, n, _l, _e in lms] + [t["name"] for t in towers] + stn))
    return {"place": place, "bbox": [round(v, 5) for v in bbox], "majors": majors, "landmarks": landmarks,
            "landmark_buildings": blds, "diagonals": diagonals_of(m, majors), "parks": parks, "areas": areas,
            "rail_lines": [], "transit": transit_of(els), "auto": True}
