"""The Mind Palace (brief.mode "palace"): a timeline drawn as a real city.

The user names a city (and, if they like, the part of it); Claude fetches its
streets, rivers, parks and railways from OpenStreetMap (palace_map.py) and
finds its blocks and building lots (palace_place.py) once, with the tool
set_up_palace. The result is kept, packed, in brief.palace.data_z, so every
later build draws the same city without going back to the internet.

Every node is a building or a floor of one:
  - a node with no `parent` is a BUILDING. It stands on a lot of a city block
    in its section's district (brief.palace.districts), the district's
    buildings spread along a walk through it in reading order;
  - a node with a `parent` is a FLOOR of the building it sits under (nested
    floors are allowed and stack in reading order). Its detail page is a
    storey of that building, reached by the elevator.

On the map a building shows only its number; pointing at it gives its name,
where it stands and its floors; a click enlarges it to the ordinary card, and
opening it goes inside. Streets show their names when pointed at (two names at
a corner); the major ones are always labelled. The timeline's connections are
not lines between cards here: pointing at a building lights the routes along
the streets to the buildings it connects with, in the relation's color.

Map data © OpenStreetMap contributors (ODbL) — the page carries the credit.
"""
from __future__ import annotations

import base64
import lzma
import gzip
import json
import math
import re

from .brief import BriefError
from .key_toggle import KEY_CSS, KEY_JS
from .palace_directions import DIR_CSS, DIR_JS
from .palace_pan import PAN_JS
from .palace_landmarks import LANDMARK_CSS, LANDMARK_JS
from .palace_fleet_asset import FLEET_LOADER                     # the toy fleet is a hosted script (1.9.99): boats, bases, their weapons, sound, crowd, rebuild
from .palace_labels import LABELS_CSS, LABELS_JS
from .palace_towers import tower_data, tower_lots, apply_towers, landmark_state      # noqa: F401  (towers: a unit inside a skyscraper)
from .palace_mobile import MOBILE_CSS, MOBILE_JS
from .palace_claim import claimed as claimed_shapes, claim_lots, migrate_shapes      # a node on a background building's footprint
from .palace_airport import AIRPORT_CSS, AIRPORT_JS, clean_destinations
from .palace_transit_js import TRANSIT_CSS, TRANSIT_JS
from .palace_ride import RIDE_LOADER
from .palace_highway_js import HIGHWAY_CSS, HIGHWAY_JS     # C3 highways
from .palace_bridges import BRIDGE_CSS, BRIDGE_JS          # bridge design elements
from .sanitize import js_json
from . import palace_place as pp

PALACE_KEYS = {"place", "area", "bbox", "districts", "majors", "landmarks", "diagonals", "lines",
               "buildings", "parks", "areas", "portals", "scale", "data_z", "made", "transit", "preset",
               "fill_z", "banners"}      # banners: giant words across a river (palace_areas.py); fill_z: the simulated buildings (palace_fillin.py; absent = off)


# ── the packed city ────────────────────────────────────────────────────────
# A city is mostly numbers in long runs (lots, blocks, polylines), every one on a 0.1 map-unit grid. pack() stores them as
# columns of whole-number steps (a lot's x after the last lot's x, a polyline's point after the one before), which xz squeezes
# to a fraction of the gzip'd JSON (Philadelphia v2: 432 kB -> about 165 kB). The shape round-trips exactly; a value off the
# 0.1 grid is kept as it is. "xz2:" marks the format; an older palace (base64 gzip JSON) still unpacks.
_PACK2 = "xz2:"


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _ints(vals):
    """[numbers] -> (1, ints) when all are ints, (10, ints) when all are floats on the 0.1 grid, else None."""
    if all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
        return 1, list(vals)
    out = []
    for v in vals:
        if not isinstance(v, float) or v != v or abs(v) > 1e12:          # a mix of ints and floats stays as it is (types kept)
            return None
        q = round(v * 10)
        if abs(q / 10 - v) > 1e-9:
            return None
        out.append(q)
    return 10, out


def _delta(a, stride):
    return a[:stride] + [a[i] - a[i - stride] for i in range(stride, len(a))]


def _undelta(a, stride):
    a = list(a)
    for i in range(stride, len(a)):
        a[i] += a[i - stride]
    return a


def _enc(o):
    if isinstance(o, dict):
        return {k: _enc(v) for k, v in o.items()}
    if not isinstance(o, list) or not o:
        return o
    if len(o) >= 6 and all(_num(v) for v in o):                        # a polyline / flat ring: x,y steps
        q = _ints(o)
        if q:
            return {"~n": q[0], "d": _delta(q[1], 2)}
    if len(o) >= 4 and all(isinstance(r, list) and r and all(_num(v) for v in r) for r in o) and len({len(r) for r in o}) == 1:
        cols = [list(c) for c in zip(*o)]                                # a table of rows (tiles, lots): one column at a time
        qs = [_ints(c) for c in cols]
        if all(qs):
            return {"~t": [q[0] for q in qs], "c": [_delta(q[1], 1) for q in qs]}
    if len(o) >= 4 and all(isinstance(r, dict) for r in o) and len({tuple(r) for r in o}) == 1:
        keys = list(o[0])                                                # records with the same fields (blocks): by field
        return {"~r": keys, "c": [_enc_col([r[k] for r in o]) for k in keys]}
    return [_enc(v) for v in o]


def _enc_col(col):
    if len(col) >= 4 and all(_num(v) for v in col):
        q = _ints(col)
        if q:
            return {"~v": q[0], "d": _delta(q[1], 1)}
    if all(isinstance(v, list) for v in col):                           # e.g. each block's lots: one table, cut by counts
        flat = [x for v in col for x in v]
        return {"~s": [len(v) for v in col], "v": _enc(flat)}
    return _enc(col)


def _scale(vals, sc):
    return list(vals) if sc == 1 else [v / 10 for v in vals]


def _dec(o):
    if isinstance(o, list):
        return [_dec(v) for v in o]
    if not isinstance(o, dict):
        return o
    if "~n" in o:
        return _scale(_undelta(o["d"], 2), o["~n"])
    if "~t" in o:
        cols = [_scale(_undelta(c, 1), sc) for c, sc in zip(o["c"], o["~t"])]
        return [list(r) for r in zip(*cols)]
    if "~r" in o:
        cols = [_dec_col(c) for c in o["c"]]
        return [dict(zip(o["~r"], vals)) for vals in zip(*cols)]
    return {k: _dec(v) for k, v in o.items()}


def _dec_col(c):
    if isinstance(c, dict) and "~v" in c:
        return _scale(_undelta(c["d"], 1), c["~v"])
    if isinstance(c, dict) and "~s" in c:
        flat, out, i = _dec(c["v"]), [], 0
        for n in c["~s"]:
            out.append(flat[i:i + n]); i += n
        return out
    return _dec(c)


def pack(data: dict) -> str:
    raw = json.dumps(_enc(data), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _PACK2 + base64.b64encode(lzma.compress(raw, preset=9 | lzma.PRESET_EXTREME)).decode("ascii")


def unpack(z: str) -> dict:
    if z.startswith(_PACK2):
        return _dec(json.loads(lzma.decompress(base64.b64decode(z[len(_PACK2):])).decode("utf-8")))
    return json.loads(gzip.decompress(base64.b64decode(z)).decode("utf-8"))


_ABBR = [(r"\bStreet\b", "St"), (r"\bAvenue\b", "Ave"), (r"\bBoulevard\b", "Blvd"),
         (r"\bDrive\b", "Dr"), (r"\bRoad\b", "Rd"), (r"\bParkway\b", "Pkwy"),
         (r"\bPlace\b", "Pl"), (r"\bExpressway\b", "Expwy"), (r"\bLane\b", "Ln"),
         (r"\bSquare\b", "Sq"), (r"\bCourt\b", "Ct"), (r"\bTerrace\b", "Ter")]


def short(name: str) -> str:
    """A street's name the way a map prints it: "South 15th Street" → "S 15th St"."""
    s = str(name or "").strip()
    s = re.sub(r"^(North|South|East|West)\s+(?=\S+\s)", lambda m: m.group(1)[0] + " ", s)
    for a, b in _ABBR:
        s = re.sub(a, b, s)
    return s


# ── checks ─────────────────────────────────────────────────────────────────
def check_palace(b, warnings: list) -> None:
    pal = b.palace
    if not isinstance(pal, dict):
        raise BriefError("palace: must be an object")
    if pal and b.mode != "palace":
        raise BriefError("palace needs mode 'palace': it is the Mind Palace's city")
    if b.mode != "palace":
        return
    unknown = set(pal) - PALACE_KEYS
    if unknown:
        raise BriefError(f"palace: unknown keys {sorted(unknown)}")
    if not pal.get("data_z") and getattr(b, "palace_view", "city") == "city":
        warnings.append("palace: no city yet — run set_up_palace(timeline_id, place, …) "
                        "before building; the page has nothing to draw until then")
    from .palace_towers import check_buildings            # (towers: a landmark entry with a unit)
    check_buildings(pal, len(b.acts))
    from .palace_areas import check_areas                  # (neighbourhood names drawn label-only)
    check_areas(pal.get("areas"))
    from .palace_areas import check_banners
    check_banners(pal.get("banners"))
    from .city_presets import check_transit                # (the real networks: city presets / generic set-up)
    check_transit(pal.get("transit"))
    for i, d in enumerate(pal.get("districts") or []):
        if not isinstance(d, dict) or not isinstance(d.get("unit"), int):
            raise BriefError(f"palace.districts[{i}]: needs unit (the section's index)")
        if not 0 <= d["unit"] < len(b.acts):
            raise BriefError(f"palace.districts[{i}]: unit {d['unit']} is not a section")
        bd = d.get("bounds")
        if not (isinstance(bd, list) and len(bd) == 4 and all(isinstance(v, (int, float)) for v in bd)
                and bd[0] < bd[2] and bd[1] < bd[3]):
            raise BriefError(f"palace.districts[{i}]: bounds must be [south, west, north, east]")


def check_nodes(b, nodes, warnings: list) -> None:
    """A floor sits in a building of the same section, and no building is a floor of itself."""
    if b.mode != "palace":
        return
    by = {n.id: n for n in nodes}
    for n in nodes:
        if not n.parent:
            continue
        p = by.get(n.parent)
        if not p:
            raise BriefError(f"node {n.id}: parent {n.parent!r} is not a node — a floor's parent "
                             "is the building (or floor) it sits on")
        if p.act != n.act:
            raise BriefError(f"node {n.id}: a floor stays in its building's section "
                             f"(it is in {n.act}, {p.id} in {p.act})")
        seen, cur = {n.id}, p
        while cur and cur.parent:
            if cur.parent in seen:
                raise BriefError(f"node {n.id}: its floors loop back on themselves")
            seen.add(cur.id); cur = by.get(cur.parent)
    bad = [k for k, v in (b.placement or {}).items() if set(v) - {"lot", "fno", "out", "shape"}]
    if bad:
        raise BriefError(f"placement: a Mind Palace places buildings by lot (and a tower's floors by fno/out) only ({', '.join(bad[:5])})")


# ── structure ──────────────────────────────────────────────────────────────
def structure(b, nodes):
    """(buildings per unit in reading order, {building: [floors bottom→top]}, {floor: building})."""
    kids: dict = {}
    for n in nodes:
        if n.parent:
            kids.setdefault(n.parent, []).append(n.id)
    units = [[] for _ in b.acts]
    floors, of = {}, {}
    for n in nodes:
        if n.parent:
            continue
        units[n.act].append(n.id)
        out, stack = [], list(reversed(kids.get(n.id, [])))
        while stack:
            f = stack.pop(); out.append(f); of[f] = n.id
            stack.extend(reversed(kids.get(f, [])))
        if out:
            floors[n.id] = out
    return units, floors, of


def numbers(units, floors, fn=None) -> dict:
    """"3.4" for the 4th building of section 3; "3.4-2" for its 2nd floor up (fn: a tower's floors
    carry their real floor number instead, "3.1-17")."""
    num = {}
    fn = fn or {}
    for a, ids in enumerate(units):
        for k, bid in enumerate(ids):
            num[bid] = f"{a + 1}.{k + 1}"
            for j, f in enumerate(floors.get(bid, [])):
                num[f] = f"{a + 1}.{k + 1}-{fn.get(f, j + 1)}"
    return num


def _near(graph, lots_at, kmin=None) -> dict:
    """The corner nearest each building, "Walnut St & S 15th St" — a corner of
    through streets is worth walking a little further for than an alley's."""
    pts = graph["n"]
    kmin = kmin or {}
    grid: dict = {}
    for nd, names in graph["x"]:
        x, y = pts[2 * nd], pts[2 * nd + 1]
        pen = sum(90 if kmin.get(s, 4) >= 5 else 35 if kmin.get(s, 4) >= 4 else 0 for s in names[:2])
        names = sorted(names, key=lambda s: (kmin.get(s, 4), s))
        grid.setdefault((int(x // 200), int(y // 200)), []).append((x, y, names, pen))
    out = {}
    for bid, (x, y) in lots_at.items():
        best, bd = None, 1e18
        gx, gy = int(x // 200), int(y // 200)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for px, py, names, pen in grid.get((gx + i, gy + j), []):
                    d = (math.hypot(px - x, py - y) + pen) ** 2
                    if d < bd:
                        best, bd = names, d
        if best:
            nm = [short(s) for s in best][:2]
            out[bid] = " & ".join(nm)
    return out


def palace_stub(b, nodes) -> str:
    """window._ALTO_PALACE with no city: the buildings' floors and their
    numbers (3.4, 3.4-2) only — what a palace without a city yet, and a Star
    chart (palace_view "stars", which never draws the city), number cards by."""
    units, floors, of = structure(b, nodes)
    par = {n.id: n.parent for n in nodes if n.parent}
    return ("\nwindow._ALTO_PALACE=" + js_json({"none": 1, "fl": floors, "of": of,
                                                "num": numbers(units, floors), "par": par},
                                               separators=(",", ":")) + ";")


def palace_data(b, nodes) -> str:
    """window._ALTO_PALACE — the city, where each building stands, its floors."""
    pal = b.palace or {}
    data = unpack(pal["data_z"]) if pal.get("data_z") else None
    units, floors, of = structure(b, nodes)
    tw, fn = tower_data(b, units, floors)          # towers: {hub: {n, top}}, {floor: its real number}
    num = numbers(units, floors, fn)
    par = {n.id: n.parent for n in nodes if n.parent}
    if not data:
        return ("\nwindow._ALTO_PALACE=" + js_json({"none": 1, "fl": floors, "of": of, "num": num,
                                                    "par": par}, separators=(",", ":")) + ";")
    m, blocks = data["map"], data["blocks"]
    claims = claimed_shapes(b.placement, {i for u in units for i in u} - set(tw))      # footprints claimed from the fill-in (palace_claim.py)
    fixed = {k: v["lot"] for k, v in (b.placement or {}).items() if isinstance(v, dict) and v.get("lot") and k not in claims}
    districts = [d for d in pal.get("districts") or []]
    at = pp.place(m, blocks, [[i for i in u if i not in claims] for u in units], districts, fixed)
    nb0 = len(blocks)
    blocks = tower_lots(m, blocks, at, tw)         # a tower stands on its landmark's block, not on a lot
    blocks = claim_lots(blocks, claims, at)        # a claimed footprint is a block of one lot after them
    by_key = {f"{bl['id']}.{k}": lt for bl in blocks for k, lt in enumerate(bl["lots"])}
    graph = pp.graph(m)
    kmin: dict = {}
    for s in m.get("streets", []):
        if s.get("n"):
            kmin[s["n"]] = min(kmin.get(s["n"], 9), s.get("k", 4))
    near = _near(graph, {bid: (by_key[k][0], by_key[k][1]) for bid, k in at.items() if k in by_key}, kmin)
    dist = []
    for d in districts:
        x0, y0, x1, y1 = pp.district_box(m, d)
        dist.append({"u": d["unit"], "n": d.get("name") or "", "box": [round(x0), round(y0), round(x1), round(y1)]})
    mp = {k: v for k, v in m.items() if k not in ("bbox",)}
    from .palace_areas import layout as area_layout
    mp["areas"] = area_layout(m, pal.get("areas"), [d.get("name") or "" for d in districts])
    from .palace_areas import banners_layout
    mp["banners"] = banners_layout(m, pal.get("banners"))
    # the parks, less the blocks a building stands on (a park never moves a building)
    from .palace_parks import shape as shape_parks
    g_ = m.get("grid") or {}
    mp["parks"] = shape_parks(m.get("parks"), g_.get("xg") or [], g_.get("yg") or [],
                              [(by_key[k][0], by_key[k][1]) for k in at.values() if k in by_key])
    mp["streets"] = [{**s, "n": short(s.get("n") or "")} for s in m.get("streets", [])]
    mp["majors"] = [short(s) for s in m.get("majors", [])]
    mp["cols"] = [short(s) for s in m.get("cols", [])]      # the grid's streets by column / row, to tell a major from a minor one
    mp["rows"] = [short(s) for s in m.get("rows", [])]
    mp["top"] = sorted({short(s.get("n")) for s in m.get("streets", [])
                        if s.get("n") and s.get("k", 9) <= 1 and short(s.get("n")) in mp["majors"]})
    ls = landmark_state(b, m)
    pl0 = {k: {x: (claims[k] if x == "shape" else v[x]) for x in ("lot", "fno", "out", "shape") if v.get(x) and (x != "shape" or k in claims)}
           for k, v in (b.placement or {}).items()
           if isinstance(v, dict) and (v.get("lot") or v.get("fno") or v.get("out") or k in claims)}
    out = {"m": mp, "b": [bl["lots"] for bl in blocks], "at": at, "fl": floors, "of": of,
           "par": par, "num": num, "tw": tw, "fn": fn, "near": near, "d": dist, "place": pal.get("place") or m.get("place") or "",
           "lm0": ls["lm"], "lmtop": ls["top"], "pl0": pl0,
           "tk": sorted(getattr(b, "_tower_kids", ())), "nb": nb0, "po": check_portals(pal.get("portals"))}
    js = "\nwindow._ALTO_PALACE=" + js_json(out, separators=(",", ":")) + ";"
    if pal.get("fill_z"):                           # fill-in (palace_fillin.py): only a palace that has it says anything
        js += "\nwindow._ALTO_FILL=" + js_json(unpack(pal["fill_z"]), separators=(",", ":")) + ";"
    return js


def palace_js(b) -> str:
    """PALACE_JS, with the fill-in hooks spliced in when the palace has simulated buildings (else unchanged)."""
    js = PALACE_JS
    if (b.palace or {}).get("fill_z"):
        from .palace_fillin import patch_js
        js = patch_js(js)
    if (b.palace or {}).get("fill_z") or any(isinstance(v, dict) and v.get("shape") for v in (getattr(b, "placement", None) or {}).values()):
        from .palace_claim import patch_js as claim_js          # a node on a background building's footprint (palace_claim.py)
        js = claim_js(js)
    return js


def palace_css(b) -> str:
    if (b.palace or {}).get("fill_z"):
        from .palace_fillin import FILL_CSS
        return PALACE_CSS + FILL_CSS
    return PALACE_CSS


def check_portals(portals) -> list:
    """Gateways to places off the map: [{id, name, via?, line?, stations: [names]}]. A station named here shows a
    portal pin; its card names the place and the stations it is reached from. Nothing else is invented."""
    out = []
    for i, po in enumerate(portals or []):
        if not isinstance(po, dict) or not str(po.get("name") or "").strip():
            raise BriefError(f"portals[{i}] needs a name")
        sts = [str(x).strip() for x in (po.get("stations") or []) if str(x).strip()]
        if not sts:
            raise BriefError(f"portal '{po['name']}' needs the stations it is reached from")
        name = str(po["name"]).strip()
        out.append({"id": str(po.get("id") or f"portal{i + 1}"), "name": name,
                    "via": str(po.get("via") or "").strip(), "line": str(po.get("line") or "").strip(), "stations": sts,
                    **({"code": str(po["code"]).strip().upper()[:4]} if po.get("code") else {}),
                    **({"kind": "airport"} if "airport" in name.lower() or po.get("kind") == "airport" else {}),
                    "destinations": clean_destinations(po.get("destinations"))})
    return out


def set_up(place: str, bbox, districts=None, majors=None, landmarks=None, scale: float = 1.0,
           cache_dir=None, diagonals=None, lines=None, buildings=None, parks=None, areas=None, portals=None,
           raw=None, tiled: bool = False, offline: bool = False, transit=None, preset=None,
           far_bank: bool = False, fill: bool = False) -> dict:
    """lines: hypothetical railways [{name, color?, stops: [names]}]; buildings:
    the landmark buildings [{name, page?, label?}] (palace_grid.grid); parks: names
    of parks to draw whatever their size (palace_parks; the big ones are drawn anyway); areas: the
    neighbourhood names drawn label-only, [{name, lat, lon, rank 1-4}] (palace_areas; omitted: Philadelphia's own).
    raw: the Overpass answer already fetched (nothing is fetched). tiled: fetch with city_setup.fetch_city (every
    cached tile reused, the missing ones fetched one at a time, landmarks by name on their own); offline: never
    touch the network. transit: the real networks to draw (city_presets' `transit` field), kept with the city for
    the transit reader. preset: the city preset's id (or "auto" for the generic set-up), kept for the record.
    far_bank: keep the land across a wide river (Brooklyn and Queens facing Manhattan, Cambridge across the
    Charles) instead of cutting it away as the city's edge (palace_map's wide-river rule)."""
    """Fetch and prepare a city: the brief.palace dict to store (data_z packed)."""
    from .. import palace_map as pm
    from .palace_areas import check_areas, default_areas
    areas = default_areas(place, bbox) if areas is None else areas
    check_areas(areas)
    if raw is None and (tiled or offline):
        from .city_setup import fetch_city
        raw = fetch_city(tuple(bbox), cache_dir=cache_dir, names=landmarks or None, offline=offline)
    elif raw is None:
        raw = pm.fetch_osm(tuple(bbox), cache_dir=cache_dir, landmarks=landmarks or None)
    share = pm.FAR_BANK_SHARE
    if far_bank:
        pm.FAR_BANK_SHARE = -1.0                      # palace_map keeps a far bank holding more than this share
    try:
        m = pm.build_map(raw, tuple(bbox), place=place, scale=scale, majors=majors or None,
                         landmarks=landmarks or None)
    finally:
        pm.FAR_BANK_SHARE = share
    # a landmark found both as an outline and as a point (a station node beside
    # its building) is named once, by its outline
    lms = m.get("landmarks", [])
    m["landmarks"] = [l for l in lms if l.get("r") or not any(
        o.get("r") and math.hypot(o["x"] - l["x"], o["y"] - l["y"]) < 260 for o in lms)]
    # the drawing: an even grid of the city's streets, the river and a few
    # diagonals the only exceptions (palace_grid)
    from .palace_grid import grid
    hw_real = m.get("highways")                                     # C3: the highways ride through the grid
    real_trails = [dict(t) for t in (m.get("trails") or [])]                     # the grid drawing drops every path: the river trails are kept (palace_banks.py)
    real_rivers = [dict(r) for r in (m.get("rivers") or [])]                     # (and the real river lines, to read which bank a trail keeps)
    m = grid(m, majors=majors or (), diagonals=diagonals or (), lines=lines or (), landmarks=buildings or (), parks=parks or ())
    from .city_highways import attach as attach_highways              # C3 (a no-op when city_engine attached them)
    attach_highways(m, {"highways": hw_real})
    try:
        from .palace_banks import clip_streets, trails_on_page, cut_outlines, LAST_STATS
        clip_streets(m)                                      # no street runs through a river but a bridge
        m["rtrails"] = trails_on_page(m, real_trails, real_rivers)        # the Schuylkill River Trail along its bank
        cut_outlines(m, LAST_STATS.get("ext_segs"))          # ...and no block outline is drawn through it (the page draws m.tiles/edges/tq/te, not m.streets)
    except Exception:                                       # noqa: BLE001 — a river that cannot be read keeps the streets as drawn
        pass
    blocks = m.pop("blocks")
    # fill-in (palace_fillin.py): the real buildings of the whole city box (past the districts + 1 km as the size budget allows), opening on level 1 (Skyline).
    # Never fatal: a busy Overpass leaves the palace without them (set_up_palace again adds them).
    fz, ships = None, []
    if fill:
        try:
            from .palace_fillin import fill_for
            fz = fill_for(m, blocks, districts or [], bbox, cache_dir=cache_dir, offline=offline, ships_out=ships)
        except Exception:                                   # noqa: BLE001 — network, Overpass
            fz = None
    # boats (palace_boats.py): a ship is put in the river's water, not on a block, and is no landmark card
    try:
        from .palace_boats import find as find_ships, place as place_ships
        ships += find_ships(raw, m.get("bbox") or bbox, m.get("scale", 1.0))
        uniq = []
        for sh in ships:
            if not any((sh["n"] and sh["n"] == q["n"]) or math.hypot(sh["rx"] - q["rx"], sh["ry"] - q["ry"]) < 25 for q in uniq):
                uniq.append(sh)
        boats = place_ships(m, uniq)
        if boats:
            m["boats"] = boats
            nm = {b["n"] for b in boats if b["n"]}
            m["landmarks"] = [l for l in m.get("landmarks", []) if l.get("n") not in nm]
    except Exception:                                       # noqa: BLE001 — a city whose water cannot be read keeps its boats off the map
        pass
    # the fleet (palace_fleet.py): museum warships the building tiles missed and military bases, each a toy that attacks (the hosted palace_fleet_asset.py)
    try:
        from . import palace_fleet
        palace_fleet.attach(m, palace_fleet.fetch(m.get("bbox") or bbox, cache_dir=cache_dir, offline=offline), bbox)
    except Exception:                                       # noqa: BLE001 — a busy Overpass or a city with neither: no fleet beyond the boats found
        pass
    # the street-level data of the first-person view (palace_street.py): one hosted, content-hashed blob; the page holds only its 10 character hash (m["street"])
    try:
        from . import palace_street
        try:
            from .palace_ride_real import scope_for
            scope = scope_for(m, districts or [], bbox)      # first-person view scope: only the districts with nodes, the fleet and the landmarks (+ buffer) get street data
        except Exception:                                   # noqa: BLE001 — a map the scope cannot be read from keeps the whole box
            scope = None
        palace_street.attach(m, bbox, cache_dir=cache_dir, offline=offline, scope=scope)
    except Exception:                                       # noqa: BLE001 — a busy Overpass or a city with nothing: no street data, the ride is as before
        pass
    # buses (palace_buses.py): the main routes, drawn along the page's streets from their real stops, ridden like any line
    try:
        from . import palace_buses
        palace_buses.attach(m, palace_buses.fetch(m.get("bbox") or bbox, cache_dir=cache_dir, offline=offline))
    except Exception:                                       # noqa: BLE001 — a busy Overpass or a city with no bus relations: no buses
        pass
    out = {"place": place, "bbox": list(bbox), "districts": districts or [],
           "majors": majors or [], "landmarks": landmarks or [], "diagonals": diagonals or [],
           "lines": lines or [], "buildings": buildings or [], "parks": parks or [], "areas": areas, "portals": check_portals(portals), "scale": scale,
           **({"transit": transit} if transit else {}), **({"preset": preset} if preset else {}),
           "data_z": pack({"map": m, "blocks": blocks})}
    if fz:
        out["fill_z"] = fz
    return out


def migrate_placements(old_pal: dict, new_pal: dict, placement: dict) -> tuple:
    """A city set up again keeps its saved building lots (palace_place.migrate): each fixed "lot" moves to the new lot
    at the nearest real place; one that cannot be carried over loses only its lot (the building is placed afresh, its
    floor and other settings stay). -> (placement, {"moved", "dropped", "kept"})."""
    from . import palace_place as pp
    placement = {k: dict(v) if isinstance(v, dict) else v for k, v in (placement or {}).items()}
    keys = [v["lot"] for v in placement.values() if isinstance(v, dict) and v.get("lot")]
    rep = {"moved": 0, "dropped": 0, "kept": 0}
    if not keys:
        return migrate_shapes(old_pal, new_pal, placement), rep
    try:
        od, nd = unpack(old_pal["data_z"]), unpack(new_pal["data_z"])
        mp = pp.migrate(dict(od["map"], bbox=old_pal.get("bbox")), od["blocks"],
                        dict(nd["map"], bbox=new_pal.get("bbox")), nd["blocks"], keys)
    except Exception:                                       # noqa: BLE001 — an old city that cannot be read
        mp = {k: None for k in keys}
    for v in placement.values():
        if isinstance(v, dict) and v.get("lot"):
            nk = mp.get(v["lot"])
            if nk is None:
                v.pop("lot", None); rep["dropped"] += 1
            else:
                rep["kept" if nk == v["lot"] else "moved"] += 1
                v["lot"] = nk
    placement = migrate_shapes(old_pal, new_pal, placement)
    placement = {k: v for k, v in placement.items() if not (isinstance(v, dict) and not v)}
    return placement, rep


def summary(pal: dict) -> dict:
    """What get_timeline shows of the city instead of the packed data."""
    if not pal:
        return pal
    out = {k: v for k, v in pal.items() if k not in ("data_z", "fill_z")}
    if pal.get("fill_z"):
        try:
            f = unpack(pal["fill_z"])
            out["fill"] = {"buildings_per_level": f.get("c"), "opens_on": f.get("lvl"), "reach": f.get("reach"),
                           "stored_kb": round(len(pal["fill_z"]) / 1024), **({"missing_tiles": len(f["missing"])} if f.get("missing") else {})}
        except Exception:                                   # noqa: BLE001
            out["fill"] = "unreadable"
    if pal.get("data_z"):
        try:
            d = unpack(pal["data_z"])
            out["city"] = {"W": d["map"]["W"], "H": d["map"]["H"], "blocks": len(d["blocks"]),
                           "lots": sum(len(x["lots"]) for x in d["blocks"]),
                           "streets": len(d["map"].get("streets", [])),
                           "stored_kb": round(len(pal["data_z"]) / 1024)}
        except Exception:                                   # noqa: BLE001
            out["city"] = "unreadable — run set_up_palace again"
    return out


# ── the page ───────────────────────────────────────────────────────────────
PALACE_CSS = KEY_CSS + r"""
  html{--pal-river:#7fb6e8;--pal-rv-rim:rgba(255,255,255,.7);--pal-casing:rgba(255,255,255,.93);--pal-br-edge:rgba(44,52,84,.62);--pal-br-pier:rgba(44,52,84,.42);--pal-br-text:#2a3358;--pal-rv-lite:#ffffff;--pal-rv-sheen:rgba(255,255,255,.7);--pal-glass:rgba(255,255,255,.34);--pal-glass-edge:rgba(255,255,255,.75);--pal-water:rgba(196,222,246,.92);--pal-water-edge:rgba(255,255,255,.85);
    --pal-park:rgba(255,255,255,.20);--pal-pk:rgba(86,170,98,.42);--pal-pk-edge:rgba(255,255,255,.78);--pal-pk-path:rgba(255,255,255,.82);--pal-pk-txt:#2c6a3a;--pal-lm:rgba(255,255,255,.38);--pal-text:#2c2f3d;--pal-halo:rgba(255,255,255,.88);--pal-trail:#4f9a4a;--pal-ground:238,238,242;}
  html.dark{--pal-river:#3f78b4;--pal-rv-rim:rgba(255,255,255,.16);--pal-casing:rgba(18,22,34,.55);--pal-br-edge:rgba(214,222,244,.62);--pal-br-pier:rgba(214,222,244,.42);--pal-br-text:#dfe6fa;--pal-rv-lite:#9fcaf2;--pal-rv-sheen:rgba(255,255,255,.34);--pal-glass:rgba(22,24,34,.42);--pal-glass-edge:rgba(255,255,255,.16);--pal-water:rgba(38,64,100,.92);--pal-water-edge:rgba(255,255,255,.28);
    --pal-park:rgba(255,255,255,.06);--pal-pk:rgba(86,178,104,.26);--pal-pk-edge:rgba(255,255,255,.2);--pal-pk-path:rgba(214,240,214,.5);--pal-pk-txt:#a8e0b0;--pal-lm:rgba(255,255,255,.10);--pal-text:#e4e2ec;--pal-halo:rgba(14,16,24,.88);--pal-trail:#6fbf68;--pal-ground:28,30,40;}
  html.alto-palace:not(.mobile) #world{margin:0 !important;translate:var(--ppan-x,0px) var(--ppan-y,0px);}
  /* the board is its own compositing layer all the time (it already is a stacking context: translate): made one only for a zoom,
     WebKit painted the whole window into the new layer on a zoom's first frame and into the old one again at its end (~100 ms each) */
  html.alto-palace:not(.mobile) #world{will-change:transform;}
  html.alto-palace:not(.mobile) #glass-slab,html.alto-palace:not(.mobile) #river-svg,
  html.alto-palace:not(.mobile) #world .phase-band,html.alto-palace:not(.mobile) #world .phase-label-float,
  html.alto-palace:not(.mobile) #world .unit-bar{display:none !important;}
  #palace-svg{position:absolute;left:0;z-index:1;overflow:visible;pointer-events:none;
    -webkit-user-select:none;user-select:none;transition:opacity .3s;}
  #canvas.focus-mode #palace-svg{opacity:.55;}
  .pal-svg .pl-glass{fill:var(--pal-glass);stroke:var(--pal-glass-edge);stroke-width:1.5;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-water{fill:var(--pal-water);}
  .pal-svg .pl-river-g path{fill:none;stroke-linecap:round;stroke-linejoin:round;}
  .pal-svg .pl-rv-rim{stroke:var(--pal-rv-rim);}
  .pal-svg .pl-rv-body{stroke:var(--pal-river);}
  .pal-svg .pl-rv-lite{stroke:var(--pal-rv-lite);}
  .pal-svg .pl-rv-sheen{stroke:var(--pal-rv-sheen);}
  .pal-svg .pl-lmb{pointer-events:all;cursor:default;}
  .pal-svg .pl-lmn{pointer-events:none;}               /* the names layer over the buildings: a label, never a target */
  .pal-svg .pl-lmb.has-page{cursor:pointer;}
  .pal-svg .pl-lmb .lm-shadow{fill:rgba(20,26,55,.16);}
  .pal-svg .pl-lmb .lm-card{fill:rgba(255,255,255,.92);stroke-width:2.5;vector-effect:non-scaling-stroke;}
  html.dark .pal-svg .pl-lmb .lm-card{fill:rgba(34,36,48,.94);}
  .pal-svg .pl-lmb.has-page:hover .lm-card,.pal-svg .pl-lmb:focus-visible .lm-card{stroke-width:4;}
  .pal-svg .pl-lmb:focus{outline:none;}
  .pal-svg :is(.pl-lmb,.pl-lmn) .lm-name{font-weight:800;letter-spacing:.01em;stroke:none;}
  .pal-svg .pl-bridges .pl-tube{filter:drop-shadow(0 1px 2px rgba(20,26,55,.35));}
  /* a bridge: a deck (a light band) between two fine rail lines, piers ticked out into the water either side, its name beside it;
     all measured on the screen (--tw), so it keeps its look at every zoom */
  .pal-svg .pl-casing{fill:none;stroke:var(--pal-casing);stroke-width:calc(var(--tw,1) * 12.5px);stroke-linecap:round;}
  .pal-svg .pl-br-edge{fill:none;stroke:var(--pal-br-edge);stroke-width:calc(var(--tw,1) * 14.5px);stroke-linecap:round;}
  .pal-svg .pl-br-pier{fill:none;stroke:var(--pal-br-pier);stroke-width:calc(var(--tw,1) * 21px);stroke-linecap:butt;
    stroke-dasharray:calc(var(--tw,1) * 1.7px) calc(var(--tw,1) * 17px);}
  .pal-svg .pl-brn{font-size:calc(9.5px / var(--pz,1));font-weight:750;letter-spacing:.09em;text-transform:uppercase;fill:var(--pal-br-text);
    stroke-width:calc(3px / var(--pz,1));pointer-events:none;}
  .pal-svg.far .pl-brn:not(.big){display:none;}
  .pal-svg .pl-water-edge{fill:none;stroke:var(--pal-water-edge);stroke-width:2;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-park{fill:var(--pal-park);stroke-width:1.2;stroke-opacity:.45;stroke-dasharray:5 4;vector-effect:non-scaling-stroke;}
  /* parks (palace_parks.py): green glass with a thin light edge, under the streets; walkways and plazas in light line */
  .pal-svg .pl-pk{fill:var(--pal-pk);stroke:var(--pal-pk-edge);stroke-width:1.5;vector-effect:non-scaling-stroke;fill-rule:evenodd;pointer-events:none;}
  .pal-svg .pl-pkp{fill:none;stroke:var(--pal-pk-path);stroke-width:calc(var(--tw,1) * 2.6px);stroke-linecap:round;stroke-linejoin:round;pointer-events:none;}
  .pal-svg .pl-pko{fill:var(--pal-pk);stroke:var(--pal-pk-path);stroke-width:calc(var(--tw,1) * 2.2px);pointer-events:none;}
  .pal-svg .pl-pkt{font-size:calc(10.5px / var(--pz,1));font-weight:750;letter-spacing:.14em;text-transform:uppercase;fill:var(--pal-pk-txt);
    stroke-width:calc(3px / var(--pz,1));pointer-events:none;}
  .pal-svg.far .pl-pkt:not(.big){display:none;}
  .pal-svg .pl-lm{fill:var(--pal-lm);stroke-width:1.8;stroke-opacity:.8;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-tube,.pal-svg .pl-sheen{fill:none;stroke-linecap:round;stroke-linejoin:round;}
  /* the streets weigh what an ordinary timeline's connecting lines weigh (5px tube, a frosted centre line
     a third as wide), measured on the SCREEN: --tw is the unit the page gives one screen px (placeAll),
     so a street keeps its weight at every zoom instead of thinning with the map. A major street is the
     full tube; a minor one a lighter tube of the same family. */
  .pal-svg .pl-tube.t-min{stroke-width:calc(var(--tw,1) * 3.6px);}
  .pal-svg .pl-sheen.t-min{stroke-width:calc(var(--tw,1) * 1.3px);}
  .pal-svg .pl-tube.t-maj{stroke-width:calc(var(--tw,1) * 5.6px);}
  .pal-svg .pl-sheen.t-maj{stroke-width:calc(var(--tw,1) * 1.9px);}
  .pal-svg .pl-tube.r-line{stroke-width:calc(var(--tw,1) * 4.4px);}
  .pal-svg .pl-sheen.r-line{stroke-width:calc(var(--tw,1) * 1.5px);}
  /* a stop / station sits at its map point by the SVG transform ATTRIBUTE (map units, which no CSS zoom touches), and keeps
     its size on the screen by a UNITLESS CSS scale on an inner group (.pl-sc). Never a CSS translate in px here: Safari
     multiplies px inside an SVG element's CSS transform by the page's CSS zoom (html{zoom:.8–1}), so a stop at map x
     drew at x·zoom — rings strung across empty map, ever farther off toward the city's far corner. */
  .pal-svg .pl-sc{transform:scale(var(--tw,1));}
  .pal-svg .pl-tun{fill:none;stroke-width:2;stroke-dasharray:6 6;stroke-opacity:.35;}
  .pal-svg .pl-trail{fill:none;stroke:var(--pal-trail);stroke-width:2.6;stroke-dasharray:7 5;stroke-linecap:round;opacity:.85;}
  .pal-svg .pl-ties{fill:none;stroke-width:calc(var(--tw,1) * 9px);stroke-dasharray:calc(var(--tw,1) * 1.4px) calc(var(--tw,1) * 5.6px);stroke-opacity:.75;}
  .pal-svg .pl-tube.r-under{stroke-dasharray:10 8;}
  .pal-svg .pl-sheen.r-under{stroke-dasharray:10 8;opacity:.6;}
  .pal-svg .pl-ring{fill:var(--pal-halo);stroke-width:4;}
  .pal-svg .pl-ring.hub{stroke-width:5.5;fill:none;}
  .pal-svg .pl-ring-sh{fill:none;stroke:rgba(255,255,255,.7);stroke-width:1.4;}
  .pal-svg text{fill:var(--pal-text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    paint-order:stroke;stroke:var(--pal-halo);stroke-linejoin:round;}
  .pal-svg .pl-st{font-size:calc(11.5px / var(--pz,1));font-weight:650;stroke-width:calc(3.4px / var(--pz,1));letter-spacing:.03em;}
  .pal-svg .pl-river{font-weight:750;text-transform:uppercase;fill:#21507f;stroke:none;letter-spacing:.3em;pointer-events:none;}
  html.dark .pal-svg .pl-river{fill:#d6e8fa;}
  .pal-svg .pl-chip-bg{fill:var(--pal-halo);stroke-width:1.4;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-lmt{font-size:calc(11px / var(--pz,1));font-weight:650;stroke:none;letter-spacing:.02em;}
  .pal-svg .pl-stt{font-size:calc(11px / var(--pz,1));font-weight:700;stroke-width:calc(3px / var(--pz,1));}
  .pal-svg .pl-stt.hub{font-size:calc(13px / var(--pz,1));font-weight:800;}
  /* a station's name: placed beside its ring inside the ring's scaled group (stLbl), the text un-scaled again so its own
     font size (per --pz) holds — no px in any transform (see .pl-sc) */
  .pal-svg .pl-stt{transform:scale(calc(1 / var(--tw,1)));}
  .pal-svg .pl-dtint{fill-opacity:0;pointer-events:all;}
  /* a neighbourhood's name is an area label, as on an ordinary map: small and light at the whole-city zoom (about 11px on the screen),
     growing gently as you come closer (to 20px), tracked only a little, with a halo; at the far zoom it lets every click through to
     the streets and buildings under it (the Key's rows still fly to a neighbourhood) */
  .pal-svg .pl-dist{--dfs:clamp(11px, calc(10.5px + 8px * var(--pz,1)), 20px);font-size:calc(var(--dfs) / var(--pz,1));font-weight:650;letter-spacing:.07em;text-transform:uppercase;
    opacity:.8;stroke-width:calc(3.2px / var(--pz,1));pointer-events:all;cursor:pointer;}
  .pal-svg.far .pl-dist{opacity:.6;pointer-events:none;}
  /* neighbourhood names (palace_areas.py): label-only, smaller and lighter than the units' names, never a click target; which show is decided by rank and room (areaFit) */
  .pal-svg .pl-area{--afs:clamp(9px, calc(7.5px + 5px * var(--pz,1)), 13px);font-size:calc(var(--afs) / var(--pz,1));font-weight:600;letter-spacing:.09em;text-transform:uppercase;
    opacity:.74;stroke-width:calc(3px / var(--pz,1));pointer-events:none;}
  #palace-svg-m .pl-area{--afs:clamp(10.5px, calc(8.5px + 5px * var(--pz,1)), 13px);opacity:.7;}
  .pal-svg .pl-rv-bank{fill:none;stroke:rgba(112,170,100,.34);stroke-linecap:round;stroke-linejoin:round;} html.dark .pal-svg .pl-rv-bank{stroke:rgba(90,150,90,.3);}
  .pal-svg .pl-rtrail{fill:none;stroke:#3f8a4f;stroke-width:calc(var(--tw,1) * 2.6px);stroke-dasharray:calc(var(--tw,1) * 7px) calc(var(--tw,1) * 5px);stroke-linecap:round;stroke-linejoin:round;pointer-events:none;}
  .pal-svg .pl-rtrail-c{stroke:rgba(255,255,255,.7);stroke-width:calc(var(--tw,1) * 5px);stroke-dasharray:none;}
  .pal-svg .pl-rtname{font-size:calc(11px / var(--pz,1));font-style:italic;font-weight:650;fill:#2f6f3d;stroke:rgba(255,255,255,.75);stroke-width:calc(3px / var(--pz,1));paint-order:stroke;pointer-events:none;} html.dark .pal-svg .pl-rtname{fill:#8fd29b;stroke:rgba(0,0,0,.45);}
  .pal-svg.far .pl-rtname{display:none;}
  .pal-svg .pl-banner{font-weight:900;letter-spacing:.04em;fill:rgba(176,38,28,.5);stroke:rgba(255,255,255,.55);stroke-width:calc(5px / var(--pz,1));paint-order:stroke;stroke-linejoin:round;pointer-events:none;text-transform:none;}
  html.dark .pal-svg .pl-banner{fill:rgba(255,110,90,.55);stroke:rgba(0,0,0,.4);}
  .pal-svg .pl-credit{font-size:calc(10px / var(--pz,1));opacity:.7;stroke-width:calc(2.5px / var(--pz,1));}
  .pal-svg .pl-bld{pointer-events:all;cursor:pointer;}
  .pal-svg .pl-bld .b-card{fill:rgba(255,255,255,.9);stroke-width:1.4;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-bld .b-floor{fill:rgba(255,255,255,.75);stroke-width:1;stroke-opacity:.6;vector-effect:non-scaling-stroke;}
  html.dark .pal-svg .pl-bld .b-card{fill:rgba(36,38,50,.92);}
  html.dark .pal-svg .pl-bld .b-floor{fill:rgba(36,38,50,.75);}
  .pal-svg .pl-bld .b-num{font-weight:800;stroke:none;}
  .pal-svg .pl-bld .b-tag{fill:var(--surface,#fff);stroke-width:1.5;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-bld.pal-hot .b-tag,.pal-svg .pl-bld:hover .b-tag{stroke-width:3;}
  .pal-svg .pl-bld.pal-hot .b-card,.pal-svg .pl-bld:hover .b-card{stroke-width:3;}
  .pal-svg .pl-bld.pal-dim{opacity:.3;}
  .pal-svg .pl-hit{fill:none;stroke:transparent;stroke-width:14;pointer-events:stroke;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-route{fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-width:7;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-route-sh{fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-width:2.4;vector-effect:non-scaling-stroke;
    stroke:rgba(255,255,255,.8);stroke-dasharray:10 12;animation:pal-flow 1.1s linear infinite;}
  .pal-svg .pl-walk{fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-width:4;vector-effect:non-scaling-stroke;stroke-dasharray:2 7;}
  .pal-svg .pl-addr{fill:var(--accent);fill-opacity:.12;stroke:var(--accent);stroke-width:1.5;stroke-dasharray:4 3;vector-effect:non-scaling-stroke;pointer-events:none;}
  .pal-svg .pl-addpend{fill-opacity:.32;stroke-width:2;stroke-dasharray:none;}
  .pal-svg .pl-addr0{fill-opacity:.05;stroke-opacity:.55;}
  #pl-lmbar{position:fixed;z-index:70;display:none;gap:4px;padding:4px;border-radius:12px;background:rgba(255,255,255,.86);backdrop-filter:blur(14px) saturate(1.4);-webkit-backdrop-filter:blur(14px) saturate(1.4);
    border:1px solid rgba(0,0,0,.12);box-shadow:0 6px 22px rgba(0,0,0,.18);}
  #pl-lmbar.show{display:flex;}
  #pl-lmbar button{font:700 12px/1 system-ui,sans-serif;padding:7px 10px;border-radius:8px;border:0;background:transparent;color:#1d1d1f;cursor:pointer;white-space:nowrap;}
  #pl-lmbar button:hover{background:rgba(0,0,0,.07);}
  #pl-lmbar button[data-a=add]{background:var(--accent,#2d6cdf);color:#fff;}
  #pl-lmbar button[data-a=add]:hover{filter:brightness(1.08);}
  .pal-svg .pl-addp{fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round;vector-effect:non-scaling-stroke;pointer-events:none;}
  .pal-svg.pl-adding{cursor:copy;}
  #alto-edit-exit .ee-addb{width:auto;padding:0 10px;line-height:1.2;font:inherit;font-size:12.5px;white-space:nowrap;}
  #alto-edit-exit .ee-addb.on{background:var(--accent);color:#fff;}
  .pal-svg .pl-slot{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-dasharray:5 4;vector-effect:non-scaling-stroke;}
  @keyframes pal-flow{to{stroke-dashoffset:-22;}}
  @media (prefers-reduced-motion: reduce){.pal-svg .pl-route-sh{animation:none;}}
  .pal-svg.far .lm-tagp,
  .pal-svg.far .pl-lmt,.pal-svg.far .pl-chip,.pal-svg.far .pl-stt:not(.hub),.pal-svg.far .pl-ring:not(.hub),
  .pal-svg.far .pl-st:not(.top),.pal-svg.far .pl-st:not(.r0){display:none;}
  .pal-svg.mid .pl-st.minor{display:none;}
  /* on the board a building IS its card: the size of its lot, turned to its street grid,
     its number on it, its floors stacked behind it; enlarged it is the ordinary card */
  html.alto-palace #world .node{z-index:3;}
  html.alto-palace #world .node.pal-floor{display:none !important;}
  /* v1.9.85+: a building is a glass block on its lot (.nb3d, drawn once per lot by nbBuild, scaled by --z), as tall as what is inside it;
     its card is a number TAG floating above the roof (the same size at every zoom), so the number is never hidden by the 3D part */
  html.alto-palace:not(.mobile) #world .node:not(.focused){width:var(--pw,40px);height:var(--ph,26px);z-index:var(--nz,3);}
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card{position:absolute !important;left:50%;top:50%;width:max-content !important;height:auto !important;
    translate:calc(-50% + var(--z,1) * var(--bx,0) * 1px + var(--tdx,0px)) calc(-50% - var(--z,1) * (var(--hh,0) - var(--hc,0)) * 1px - 12px + var(--tdy,0px));
    min-width:24px !important;max-width:none !important;min-height:0 !important;padding:2px 7px !important;border-radius:999px !important;
    display:flex !important;align-items:center;justify-content:center;overflow:hidden !important;rotate:0deg;transform-origin:50% 50% !important;
    border:2px solid var(--pc,#888) !important;background:var(--surface,#fff) !important;
    box-shadow:0 0 0 2px rgba(255,255,255,.85),0 3px 9px rgba(20,26,55,.30) !important;}
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card > *:not(.node-order):not(.aed-cc){display:none !important;}
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-order{position:static !important;display:block !important;margin:0 !important;
    font-size:var(--pf,11px) !important;line-height:1.15 !important;font-weight:800 !important;letter-spacing:.01em;color:var(--text) !important;
    opacity:1 !important;white-space:nowrap;transform:none !important;rotate:0deg;}
  .node .nb-ld{position:absolute;left:50%;top:50%;width:1px;height:1px;overflow:visible;pointer-events:none;}
  .node .nb-ld line{stroke:var(--pc,#888);stroke-width:1.2;stroke-linecap:round;stroke-opacity:.6;}
  .node .nb-ld circle{fill:var(--pc,#888);fill-opacity:.7;}
  html.mobile .node .nb-ld{display:none;}
  /* the whole city: a number on every building is a smear, so the blocks stand alone (a lit, pointed-at or filtered building keeps its tag) */
  html.nb-far:not(.mobile) #world .node:not(.focused):not(.pal-hot):not(.pal-chip-hot):not(.pal-lab):not(.pal-dest) .node-card,html.nb-far .node .nb-ld{display:none !important;}
  .node .nb3d{position:absolute;left:50%;top:50%;overflow:visible;pointer-events:none;
    width:calc(var(--z,1) * var(--nbw,1) * 1px);height:calc(var(--z,1) * var(--nbh,1) * 1px);margin-left:calc(var(--z,1) * var(--nbx,0) * 1px);margin-top:calc(var(--z,1) * var(--nby,0) * 1px);
    transition:opacity .22s ease;transform-origin:var(--ox,50%) var(--oy,100%);}
  html:not(.alto-palace) .node .nb3d,html.mobile .node .nb3d{display:none;}
  .nb3d *{pointer-events:all;cursor:pointer;}
  .nb-f,.nb-s,.nb-r{stroke:var(--pc,#888);stroke-width:2.2;stroke-linejoin:round;vector-effect:non-scaling-stroke;}
  .nb-gf0{stop-color:color-mix(in srgb,var(--pc,#888) 30%,#f2f7ff);} .nb-gf1{stop-color:color-mix(in srgb,var(--pc,#888) 62%,#a9c2ea);}
  .nb-gs0{stop-color:color-mix(in srgb,var(--pc,#888) 62%,#8fa0c6);} .nb-gs1{stop-color:color-mix(in srgb,var(--pc,#888) 80%,#4b5a82);}
  .nb-gr0{stop-color:color-mix(in srgb,var(--pc,#888) 12%,#ffffff);} .nb-gr1{stop-color:color-mix(in srgb,var(--pc,#888) 30%,#eaf1fc);}
  .nb-f,.nb-s{fill-opacity:.97;}
  .node.nb-front .nb3d,.pl-bld.nb-front .nb-body{opacity:.5;}
  .nb-sheen{fill:#fff;fill-opacity:.38;stroke:none;pointer-events:none;}
  .nb-l{stroke:var(--pc,#888);stroke-opacity:.35;stroke-width:1;vector-effect:non-scaling-stroke;fill:none;pointer-events:none;}
  .nb-sh{fill:rgba(20,26,55,.30);stroke:none;pointer-events:none;}
  html.dark .nb-gf0{stop-color:color-mix(in srgb,var(--pc,#888) 26%,#2c3146);} html.dark .nb-gf1{stop-color:color-mix(in srgb,var(--pc,#888) 38%,#1c2030);}
  html.dark .nb-gs0{stop-color:color-mix(in srgb,var(--pc,#888) 30%,#1a1d2b);} html.dark .nb-gs1{stop-color:color-mix(in srgb,var(--pc,#888) 40%,#10121b);}
  html.dark .nb-gr0{stop-color:color-mix(in srgb,var(--pc,#888) 24%,#3a3f58);} html.dark .nb-gr1{stop-color:color-mix(in srgb,var(--pc,#888) 30%,#2c3046);}
  html.dark .nb-sheen{fill-opacity:.12;}
  .node.pal-hot .nb-r,.node.pal-dest .nb-r,.pl-bld.pal-hot .nb-r{stroke-width:3.4;}
  .node.pal-dim .nb3d{opacity:.3;}
  html.alto-palace:not(.mobile) #world .node.pal-hot:not(.focused) .node-card{outline:3px solid var(--pc,#888);outline-offset:2px;}
  html.alto-palace:not(.mobile) #world .node.pal-dim:not(.focused){opacity:.3;}
  #canvas.focus-mode .node.pal-floor{display:none !important;}
  /* pointing is quiet: no box follows the cursor. A building under the pointer (or focused) lifts with a soft glow and its
     chip widens in place into a pill with its number and title; a street / neighbourhood name just brightens; the unit a
     neighbourhood holds comes in the docked card (#pal-dock), pinned bottom centre until dismissed. */
  html.alto-palace:not(.mobile) #world .node.pal-lab:not(.focused),html.alto-palace:not(.mobile) #world .node.pal-dest:not(.focused){z-index:calc(var(--nz,3) + 1000);}
  html.alto-palace:not(.mobile) #world .node.pal-lab:not(.focused) .node-card,
  html.alto-palace:not(.mobile) #world .node.pal-dest:not(.focused) .node-card,
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card:focus-visible{
    position:absolute !important;left:50%;top:50%;translate:calc(-50% + var(--z,1) * var(--bx,0) * 1px + var(--tdx,0px)) calc(-50% - var(--z,1) * (var(--hh,0) - var(--hc,0)) * 1px - 12px + var(--tdy,0px));rotate:0deg !important;
    width:max-content !important;height:auto !important;min-width:24px !important;min-height:0 !important;max-width:270px !important;
    padding:3px 11px !important;gap:6px;border-radius:999px !important;border:2px solid var(--pc,#888) !important;background:var(--surface) !important;
    box-shadow:0 0 0 4px color-mix(in srgb,var(--pc,#888) 26%,transparent),0 0 20px color-mix(in srgb,var(--pc,#888) 55%,transparent),0 7px 18px rgba(20,26,55,.28) !important;
    outline:none;animation:pal-pill-in .14s ease-out;}
  html.alto-palace:not(.mobile) #world .node.pal-lab:not(.focused) .node-card > .node-title,
  html.alto-palace:not(.mobile) #world .node.pal-dest:not(.focused) .node-card > .node-title,
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card:focus-visible > .node-title{
    display:block !important;position:static !important;margin:0 !important;padding:0 !important;font-size:12.5px !important;line-height:1.25 !important;font-weight:700 !important;
    color:var(--text) !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px;-webkit-line-clamp:unset !important;transform:none !important;}
  html.alto-palace:not(.mobile) #world .node.pal-lab:not(.focused) .node-order,
  html.alto-palace:not(.mobile) #world .node.pal-dest:not(.focused) .node-order,
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card:focus-visible .node-order{font-size:12px !important;color:var(--muted) !important;rotate:0deg !important;}
  @keyframes pal-pill-in{from{opacity:.4;scale:.9;}to{opacity:1;scale:1;}}
  @media (prefers-reduced-motion: reduce){html.alto-palace #world .node-card{animation:none !important;}}
  .pal-svg .pl-st.pal-lit,.pal-svg .pl-stt.pal-lit{fill:var(--accent);font-weight:850;}
  /* no CSS filter here: a filter on the hovered neighbourhood name made WebKit re-rasterise the whole city layer on every pan frame (p90 68 ms vs 19 ms) */
  .pal-svg .pl-dist:hover,.pal-svg .pl-dist.pal-lit{font-weight:800;stroke:var(--pal-halo);stroke-width:calc(5px / var(--pz,1));paint-order:stroke;stroke-linejoin:round;}
  .pal-svg .pl-hov{pointer-events:none;}
  .pal-svg .pl-hov rect{fill:var(--surface);stroke:var(--border);stroke-width:1.2;vector-effect:non-scaling-stroke;filter:drop-shadow(0 2px 4px rgba(0,0,0,.25));}
  .pal-svg .pl-hov text{font-size:calc(12px / var(--pz,1));font-weight:700;stroke:none;fill:var(--text);}
  #pal-dock{position:fixed;left:50%;bottom:78px;transform:translateX(-50%);z-index:305;display:none;width:min(380px,calc(100vw - 32px));box-sizing:border-box;
    padding:11px 38px 11px 14px;border-radius:16px;color:var(--text);font-size:12.5px;line-height:1.35;
    background:color-mix(in srgb,var(--surface) 80%,transparent);-webkit-backdrop-filter:blur(16px) saturate(1.5);backdrop-filter:blur(16px) saturate(1.5);
    border:1px solid color-mix(in srgb,var(--border) 70%,transparent);box-shadow:0 10px 30px rgba(0,0,0,.22);}
  #pal-dock.on{display:block;animation:pal-pill-in .16s ease-out;}
  html.mobile #pal-dock,html.detail-open #pal-dock,html.printing #pal-dock,html:not(.alto-palace) #pal-dock{display:none !important;}
  #pal-dock b{display:block;font-size:13px;}
  #pal-dock .pt-num{color:var(--muted);font-weight:800;margin-right:6px;}
  #pal-dock small{display:block;color:var(--muted);margin-top:2px;}
  #pal-dock .pd-x{position:absolute;top:6px;right:6px;width:26px;height:26px;border:0;border-radius:50%;background:transparent;color:var(--muted);font:inherit;font-size:17px;line-height:1;cursor:pointer;}
  #pal-dock .pd-x:hover{background:color-mix(in srgb,var(--text) 10%,transparent);color:var(--text);}
  #pal-dock.hint .pd-x{display:none;}
  #pal-dock .pt-unit,.pm-card .pt-unit{font-weight:650;color:var(--text);}
  #pal-dock .pt-unit i,.pm-card .pt-unit i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:baseline;}
  #pal-dock .pt-rel,.pm-card .pt-rel{display:block;margin-top:3px;font-size:12px;}
  #pal-dock .pt-rel i,.pm-card .pt-rel i{display:inline-block;width:14px;height:4px;border-radius:2px;vertical-align:middle;margin-right:6px;}
  /* the zoom controls: Alto's round glass (the search / info / key buttons), in a row beside the account toggle —
     the same inset, the same 35px, the same centre line; a grouped pill for closer / farther with a divider, and
     the whole city as a pill of its own. left = the account toggle's 24 + 35 + the row's 12.5 gap. */
  #pal-ctl{position:fixed;left:71.5px;bottom:24px;z-index:310;display:flex;align-items:center;gap:12.5px;height:35px;}
  #pal-ctl .pc-pill,#pal-ctl .pc-city{position:relative;height:35px;box-sizing:border-box;display:inline-flex;align-items:stretch;border-radius:17.5px;
    background:var(--card-glass-bg,var(--surface));border:1px solid var(--card-glass-border,var(--border));color:var(--muted);
    -webkit-backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright,1));backdrop-filter:blur(18px) saturate(190%) brightness(var(--card-glass-bright,1));
    box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #pal-ctl .pc-pill:hover,#pal-ctl .pc-city:hover{border-color:var(--muted);}
  #pal-ctl button{position:relative;display:flex;align-items:center;justify-content:center;gap:7px;margin:0;padding:0;border:0;background:none;color:inherit;
    font:inherit;font-size:14px;letter-spacing:.04em;cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation;
    -webkit-backdrop-filter:none;backdrop-filter:none;box-shadow:none;transition:color .12s,background .12s,opacity .12s;}
  #pal-ctl .pc-pill button{width:40px;min-width:0;height:100%;}
  #pal-ctl .pc-pill button:first-child{border-radius:17px 0 0 17px;}
  #pal-ctl .pc-pill button:last-child{border-radius:0 17px 17px 0;}
  #pal-ctl .pc-city{min-width:0;height:35px;padding:0 15px 0 12px;border-radius:17.5px;align-items:center;justify-content:center;gap:7px;}
  #pal-ctl .pc-city span{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;font-weight:600;letter-spacing:.02em;line-height:1;}
  #pal-ctl button:hover,#pal-ctl button:focus-visible{color:var(--text);background:color-mix(in srgb,var(--text) 7%,transparent);outline:none;}
  #pal-ctl button:active{background:color-mix(in srgb,var(--text) 13%,transparent);}
  #pal-ctl .pc-city:hover,#pal-ctl .pc-city:focus-visible,#pal-ctl .pc-city:active{background:color-mix(in srgb,var(--text) 7%,var(--card-glass-bg,var(--surface)));}
  #pal-ctl button:focus-visible{box-shadow:inset 0 0 0 2px var(--accent,#6d5bd0);}
  #pal-ctl .pc-div{width:1px;margin:8px 0;background:color-mix(in srgb,var(--muted) 45%,transparent);}
  #pal-ctl button.off{opacity:.38;cursor:default;pointer-events:none;}
  #pal-ctl .pc-city.on{color:var(--accent,#6d5bd0);border-color:color-mix(in srgb,var(--accent,#6d5bd0) 55%,transparent);}
  #pal-ctl svg{display:block;flex:none;}
  #pal-ctl button::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 12px);left:50%;transform:translateX(-50%);padding:5px 10px;border-radius:8px;
    background:var(--surface);color:var(--text);border:1px solid var(--border);font-size:12px;letter-spacing:.02em;white-space:nowrap;
    box-shadow:0 6px 18px var(--node-rest-shadow);opacity:0;pointer-events:none;transition:opacity .12s;}
  #pal-ctl button:hover::after,#pal-ctl button:focus-visible::after{opacity:1;}
  /* the key is a floating toggle's panel (key_toggle.py) */
  #pal-key h5{margin:0 0 4px;}
  #pal-key .pk-row{display:flex;gap:9px;align-items:center;padding:4px 3px;border-radius:7px;}
  #pal-key .pk-row[data-u]{cursor:pointer;}
  #pal-key .pk-row[data-u]:hover{background:color-mix(in srgb,var(--text) 7%,transparent);}
  #pal-key .pk-sw{flex:none;width:16px;height:12px;border-radius:3px;}
  #pal-key small{display:block;color:var(--muted);font-size:11px;}
  #pal-key .pk-sep{border-top:1px solid var(--border);margin:6px 0 4px;}
  #pal-key .pk-credit{margin-top:6px;font-size:10.5px;color:var(--muted);}
  html.mobile #pal-ctl,html.detail-open #pal-ctl,html.printing #pal-ctl,html:not(.alto-palace) #pal-ctl{display:none !important;}
  /* the elevator */
  #pal-elev{position:fixed;left:18px;z-index:60;width:212px;display:none;flex-direction:column;border-radius:16px;overflow:hidden;
    background:color-mix(in srgb,var(--surface) 92%,transparent);border:1px solid var(--border);box-shadow:0 14px 40px rgba(0,0,0,.22);
    -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);}
  html.pal-elev-on #pal-elev{display:flex;}
  #pal-elev .pe-roof{padding:10px 12px 9px;color:#fff;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
    clip-path:polygon(0 18%,50% 0,100% 18%,100% 100%,0 100%);padding-top:18px;text-shadow:0 1px 2px rgba(0,0,0,.35);}
  #pal-elev .pe-roof small{display:block;font-weight:600;letter-spacing:.04em;text-transform:none;font-size:11.5px;opacity:.92;margin-top:2px;}
  #pal-elev .pe-shaft{position:relative;overflow:auto;padding:6px 6px 6px 34px;}
  #pal-elev .pe-shaft::before{content:'';position:absolute;left:12px;top:6px;bottom:6px;width:14px;border-radius:7px;
    background:color-mix(in srgb,var(--text) 8%,transparent);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--text) 12%,transparent);}
  #pal-elev .pe-car{position:absolute;left:9px;width:20px;height:30px;border-radius:6px;background:var(--pal-car,var(--accent));
    box-shadow:0 2px 8px rgba(0,0,0,.35),inset 0 0 0 2px rgba(255,255,255,.5);transition:top .4s cubic-bezier(.45,0,.25,1);}
  #pal-elev .pe-car::after{content:'';position:absolute;left:9px;top:4px;bottom:4px;width:2px;background:rgba(255,255,255,.65);}
  #pal-elev .pe-fl{display:flex;align-items:flex-start;gap:8px;width:100%;text-align:left;font:inherit;font-size:12.5px;line-height:1.3;
    color:var(--text);background:transparent;border:0;border-bottom:1px dashed color-mix(in srgb,var(--text) 14%,transparent);
    padding:7px 6px;border-radius:8px;cursor:pointer;min-height:30px;}
  #pal-elev .pe-fl:last-child{border-bottom:0;}
  #pal-elev .pe-fl:hover{background:color-mix(in srgb,var(--text) 6%,transparent);}
  #pal-elev .pe-fl.on{background:color-mix(in srgb,var(--pal-car,var(--accent)) 16%,transparent);font-weight:700;}
  #pal-elev .pe-n{flex:none;min-width:22px;font-size:11px;font-weight:800;color:var(--muted);padding-top:1px;}
  #pal-elev .pe-out{flex:none;margin-left:auto;font-size:12px;opacity:.6;padding:0 3px;}
  #pal-elev .pe-out:hover{opacity:1;}
  #pal-elev .pe-no{flex:none;margin-left:auto;font-size:12px;font-weight:800;opacity:.6;padding:0 4px;}
  #pal-elev .pe-no + .pe-out{margin-left:0;}
  #pal-elev .pe-no:hover{opacity:1;}
  #pal-elev .pe-street{display:block;width:100%;font:inherit;font-size:12px;padding:9px 12px;border:0;border-top:1px solid var(--border);
    background:color-mix(in srgb,var(--text) 5%,transparent);color:var(--text);cursor:pointer;text-align:left;}
  #pal-elev .pe-street:hover{background:color-mix(in srgb,var(--text) 10%,transparent);}
  #pal-elev .pe-street small{display:block;color:var(--muted);}
  html.pal-elev-on:not(.mobile) #detail-content{padding-left:236px;}
  #pal-doors{position:fixed;right:0;bottom:0;z-index:58;display:none;pointer-events:none;overflow:hidden;}
  #pal-doors.on{display:block;pointer-events:auto;}
  #pal-doors .pd{position:absolute;top:0;bottom:0;width:50.5%;transition:transform .32s cubic-bezier(.45,0,.25,1);
    background:linear-gradient(90deg,color-mix(in srgb,var(--surface) 96%,#888),color-mix(in srgb,var(--surface) 86%,#888));
    box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--text) 10%,transparent);}
  #pal-doors .pd-l{left:0;transform:translateX(-101%);border-right:2px solid color-mix(in srgb,var(--text) 22%,transparent);}
  #pal-doors .pd-r{right:0;transform:translateX(101%);border-left:2px solid color-mix(in srgb,var(--text) 22%,transparent);}
  #pal-doors.shut .pd-l,#pal-doors.shut .pd-r{transform:none;}
  #pal-doors .pd-ind{position:absolute;left:50%;top:38%;transform:translate(-50%,-50%);z-index:2;padding:10px 18px;border-radius:12px;
    background:#16181b;color:#ffcf6b;font:800 26px/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;opacity:0;transition:opacity .2s;
    box-shadow:0 6px 20px rgba(0,0,0,.35);}
  #pal-doors.shut .pd-ind{opacity:1;}
  @media (prefers-reduced-motion: reduce){#pal-doors .pd{transition:none;}#pal-elev .pe-car{transition:none;}}
  html.printing #pal-elev,html.printing #pal-doors{display:none !important;}
  /* phones: the elevator is a row of floors at the top of the page */
  html.mobile #pal-elev{left:12px;right:12px;width:auto;flex-direction:row;align-items:stretch;border-radius:14px;}
  html.mobile #pal-elev .pe-roof{clip-path:none;padding:8px 12px;display:flex;align-items:center;font-size:13px;letter-spacing:.04em;}
  html.mobile #pal-elev .pe-roof .pe-sec{display:none;}
  html.mobile #pal-elev .pe-roof small{display:none;}
  html.mobile #pal-elev .pe-shaft{display:flex;flex-direction:row-reverse;justify-content:flex-end;gap:4px;padding:6px;overflow-x:auto;overflow-y:hidden;flex:1;}
  html.mobile #pal-elev .pe-shaft::before,html.mobile #pal-elev .pe-car,html.mobile #pal-elev .pe-street{display:none;}
  html.mobile #pal-elev .pe-fl{flex:none;width:auto;min-width:40px;justify-content:center;border:1px solid var(--border);border-radius:9px;padding:6px 8px;}
  html.mobile #pal-elev .pe-fl .pe-t{display:none;}
  html.mobile #pal-elev .pe-fl .pe-n{min-width:0;font-size:13px;color:var(--text);}
  html.mobile #pal-elev .pe-fl.on{background:var(--pal-car,var(--accent));}
  html.mobile #pal-elev .pe-fl.on .pe-n{color:#fff;}
  html.mobile.pal-elev-on #detail-content{padding-top:76px;}
  .node-card .pal-where{display:none;}
  html.mobile .node-card .pal-where{display:block;font-size:10.5px;font-weight:700;letter-spacing:.04em;color:var(--muted);margin:-2px 0 4px;}
  /* phones: the city on its own page */
  /* the phone's map page and its bottom sheet: palace_mobile.py */
  /* ═══ INTERACTION (rise · routes · elevator): delimited block ═══ */
  /* an enlarged building's card stands ABOVE it; the building stays, with a notch pointing down onto it */
  html.alto-palace:not(.mobile) #world .node .pal-ghost,html.alto-palace:not(.mobile) #world .node .pal-tail{display:none;}
  html.alto-palace:not(.mobile) #world .alto-fshadow{display:none !important;}
  html.alto-palace:not(.mobile) #world .node.focused{pointer-events:none;}
  html.alto-palace:not(.mobile) #world .node.focused .node-card{pointer-events:auto;top:var(--rt,0px);left:var(--rl,0px);
    box-shadow:0 26px 60px var(--node-hover-shadow),0 2px 10px rgba(20,26,55,.10) !important;}
  html.alto-palace:not(.mobile) #world .node.focused .pal-ghost{display:none;position:absolute;left:50%;top:50%;width:var(--pw,40px);height:var(--ph,26px);
    box-sizing:border-box;align-items:center;justify-content:center;pointer-events:auto;cursor:pointer;border-radius:5px;
    transform:translate(-50%,-50%) rotate(var(--pr,0deg));background:var(--node-glass-bg,var(--card-glass-bg,rgba(255,255,255,.9)));
    border:1.5px solid color-mix(in srgb,var(--pc,#888) 70%,transparent);border-top:3px solid var(--pc,#888);
    box-shadow:var(--pfl,0 0 0 transparent),0 0 0 3px color-mix(in srgb,var(--pc,#888) 28%,transparent),0 3px 10px rgba(20,26,55,.18);
    animation:pal-ghost-in .3s ease-out both;}
  html.alto-palace:not(.mobile) #world .node.focused .pal-ghost span{display:block;rotate:calc(-1 * var(--pr,0deg));font-size:var(--pf,11px);line-height:1.1;
    font-weight:800;letter-spacing:.01em;color:var(--text);white-space:nowrap;font-family:var(--serif,Georgia,serif);font-style:italic;pointer-events:none;}
  html.alto-palace:not(.mobile) #world .node.focused .pal-tail{display:block;position:absolute;left:50%;top:calc(50% - var(--pe,13px) - var(--pt,13px) - 1px);
    width:28px;height:14px;margin-left:-14px;overflow:hidden;pointer-events:none;animation:pal-tail-in .22s ease-out .16s both;}
  html.alto-palace:not(.mobile) #world .node.focused .pal-tail i{position:absolute;left:4px;top:-10px;width:20px;height:20px;box-sizing:border-box;rotate:45deg;
    background:var(--node-glass-bg,var(--panel-glass-bg,rgba(255,255,255,.92)));border-right:1px solid var(--card-glass-border,rgba(0,0,0,.12));border-bottom:1px solid var(--card-glass-border,rgba(0,0,0,.12));
    border-bottom-right-radius:2px;}
  /* no room above: the card goes below the building and the notch points up */
  html.alto-palace:not(.mobile) #world .node.focused.pal-below .pal-tail{top:calc(50% + var(--pe,13px) + var(--pt,13px) - 13px);}
  html.alto-palace:not(.mobile) #world .node.focused.pal-below .pal-tail i{top:auto;bottom:-10px;rotate:225deg;}
  @keyframes pal-ghost-in{from{opacity:.4;}to{opacity:1;}}
  @keyframes pal-tail-in{from{opacity:0;}to{opacity:1;}}
  @media (prefers-reduced-motion: reduce){html.alto-palace #world .node.focused .pal-ghost,html.alto-palace #world .node.focused .pal-tail{animation:none;}}
  /* the lit routes: clickable, like a line on an ordinary timeline */
  .pal-svg .pl-route-hit{fill:none;stroke:transparent;stroke-width:18;stroke-linecap:round;stroke-linejoin:round;pointer-events:stroke;cursor:pointer;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-rt.hot .pl-route{stroke-width:11;}
  .pal-svg .pl-rt.hot .pl-route-sh{stroke-width:3.4;}
  #canvas.focus-mode #palace-svg{opacity:1;}
  #canvas.focus-mode #palace-svg > *:not(.pl-routes):not(.pl-route-hits){opacity:.55;}
  html.alto-palace:not(.mobile) #world .node.pal-dest:not(.focused) .node-card{outline:4px solid var(--pc,#888);outline-offset:3px;}
  /* the elevator: where the car is, and the other ways to move it */
  #pal-elev .pe-shaft{flex:1 1 auto;min-height:0;} #pal-elev .pe-roof,#pal-elev .pe-call,#pal-elev .pe-street{flex:none;}
  #pal-elev .pe-roof{cursor:pointer;}
  #pal-elev .pe-where{display:block;margin-top:6px;font-size:10.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;opacity:.9;}
  #pal-elev .pe-fl{position:relative;transition:background .2s;}
  #pal-elev .pe-fl.on{box-shadow:inset 3px 0 0 var(--pal-car,var(--accent));}
  #pal-elev .pe-fl.on .pe-n{color:#fff;background:var(--pal-car,var(--accent));border-radius:6px;text-align:center;padding:1px 5px;}
  #pal-elev .pe-fl.pass{background:color-mix(in srgb,var(--pal-car,var(--accent)) 24%,transparent);}
  #pal-elev .pe-fl.aim{outline:2px solid var(--pal-car,var(--accent));outline-offset:-2px;background:color-mix(in srgb,var(--pal-car,var(--accent)) 18%,transparent);}
  #pal-elev .pe-car{cursor:grab;touch-action:none;z-index:2;}
  #pal-elev .pe-car::before{content:'';position:absolute;left:-8px;right:-8px;top:-5px;bottom:-5px;}
  #pal-elev.pe-drag{user-select:none;-webkit-user-select:none;} #pal-elev.pe-drag .pe-car{cursor:grabbing;transition:none;box-shadow:0 6px 16px rgba(0,0,0,.4),inset 0 0 0 2px rgba(255,255,255,.7);}
  #pal-elev .pe-call{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:7px 10px 8px;border-top:1px solid var(--border);}
  #pal-elev .pe-call button{width:34px;height:28px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--text);cursor:pointer;font-size:11px;padding:0;}
  #pal-elev .pe-call button:hover:not(:disabled){background:color-mix(in srgb,var(--pal-car,var(--accent)) 18%,transparent);}
  #pal-elev .pe-call button:disabled{opacity:.28;cursor:default;}
  #pal-elev .pe-call small{flex:1 0 100%;font-size:10.5px;line-height:1.3;color:var(--muted);}
  html.mobile #pal-elev .pe-call,html.mobile #pal-elev .pe-where{display:none;}
  #pal-pull{position:fixed;z-index:61;display:none;left:calc(50% + 118px);transform:translateX(-50%);align-items:center;gap:9px;padding:8px 16px;border-radius:999px;
    font-size:12.5px;color:var(--text);pointer-events:none;max-width:70vw;white-space:nowrap;
    background:linear-gradient(90deg,color-mix(in srgb,var(--pal-car,var(--accent)) 38%,var(--surface)) calc(var(--p,0) * 100%),var(--surface) calc(var(--p,0) * 100%));
    border:1px solid var(--border);box-shadow:0 8px 26px rgba(0,0,0,.2);}
  #pal-pull.on{display:flex;} #pal-pull b{font-weight:800;} #pal-pull span{overflow:hidden;text-overflow:ellipsis;}
  #pal-pull.pp-up{top:calc(var(--dpt,96px) + 12px);} #pal-pull.pp-dn{bottom:18px;} #pal-pull.go{border-color:var(--pal-car,var(--accent));}
  html.mobile #pal-pull{left:50%;} html.printing #pal-pull{display:none !important;}
""" + LANDMARK_CSS + LABELS_CSS + TRANSIT_CSS + HIGHWAY_CSS + BRIDGE_CSS + AIRPORT_CSS + DIR_CSS + MOBILE_CSS


PALACE_JS = KEY_JS + LANDMARK_JS + LABELS_JS + FLEET_LOADER + TRANSIT_JS + RIDE_LOADER + HIGHWAY_JS + BRIDGE_JS + AIRPORT_JS + r"""
(function(){
var P=window._ALTO_PALACE; if(!P || P.none) return;
var de=document.documentElement, M=P.m, NS='http://www.w3.org/2000/svg';
function mob(){ return de.classList.contains('mobile'); }
if(!mob()) de.classList.add('alto-palace');
var MX=90, MY=90, VW=M.W+2*MX, VH=M.H+2*MY, Z=null, opened=0;
var ACT={}, TT={}, ORDER=[];
/* the cards as the page has them now (manual edit mode adds and removes some) */
function tables(){ ACT={}; TT={}; ORDER=[];
  (ACT_SEQS||[]).forEach(function(ids,a){ ids.forEach(function(id){ ACT[id]=a; }); });
  (typeof NODES_SRC!=='undefined'?NODES_SRC:[]).forEach(function(n){ TT[n.id]=n; ORDER.push(n.id); if(ACT[n.id]==null && n.act!=null) ACT[n.id]=n.act; }); }
tables();
function esc(v){ return String(v==null?'':v).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function el(tag,attrs,parent){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; }
function ucol(id){ var pm=(typeof PHASE_META!=='undefined')?PHASE_META[ACT[id]]:null; return pm?pm.colorRaw:'#8a8a8a'; }
function title(id){ var n=TT[id]; return n?n.title:id; }
function num(id){ return (P.num||{})[id]||''; }
function lot(k){ var p=String(k||'').split('.'), b=P.b[+p[0]]; return b?b[+(p[1]||0)]:null; }
function bOf(id){ return P.of[id]||id; }
function towerOf(id){ return (P.tw||{})[bOf(id)]||null; }                          /* the skyscraper a building stands for, if it is one */
function floorNo(id){ var b=bOf(id); return (P.tw&&P.tw[b]&&P.fn[id]!=null)?P.fn[id]:((P.fl[b]||[]).indexOf(id)+1); }
function isB(id){ return !P.of[id] && !!TT[id]; }
function pts(a){ var s=''; for(var i=0;i<a.length;i+=2) s+=(i?'L':'M')+a[i]+' '+a[i+1]; return s; }

/* ── the structure (re-derived after an edit: a building made a floor, a floor let out) ── */
function restructure(live){
  if(live) tables();
  var kids={}; ORDER.forEach(function(id){ var p=P.par[id]; if(p && TT[p]) (kids[p]=kids[p]||[]).push(id); });
  var fl={}, of={}, units=(ACT_SEQS||[]).map(function(){ return []; });
  ORDER.forEach(function(id){ if(P.par[id] && TT[P.par[id]]) return; if(units[ACT[id]]) units[ACT[id]].push(id);
    var out=[], st=(kids[id]||[]).slice().reverse();
    while(st.length){ var f=st.pop(); out.push(f); of[f]=id; (kids[f]||[]).slice().reverse().forEach(function(k){ st.push(k); }); }
    if(out.length) fl[id]=out; });
  /* a tower's floors carry real floor numbers (P.fn); one added in edit mode takes the next one up, and the floors stand in order */
  P.fn=P.fn||{}; Object.keys(P.tw||{}).forEach(function(b){ var t=P.tw[b], l=fl[b]; if(!l) return;
    l.forEach(function(f){ if(P.fx[f]!=null) P.fn[f]=P.fx[f]; });             /* a number the user chose stays */
    var top=0; l.forEach(function(f){ if(P.fn[f]!=null) top=Math.max(top,P.fn[f]); });
    l.forEach(function(f){ if(P.fn[f]==null) P.fn[f]=++top; });
    l.sort(function(x,y){ return P.fn[x]-P.fn[y]; }); t.top=Math.max(t.top0||0, top); });
  var nm={}; units.forEach(function(ids,a){ ids.forEach(function(b,k){ nm[b]=(a+1)+'.'+(k+1); (fl[b]||[]).forEach(function(f,j){ nm[f]=(a+1)+'.'+(k+1)+'-'+(P.tw&&P.tw[b]&&P.fn[f]!=null?P.fn[f]:j+1); }); }); });
  P.fl=fl; P.of=of; P.num=nm; P.units=units;
  if(live && typeof NODE_ORDER_MAP!=='undefined') Object.keys(nm).forEach(function(id){ NODE_ORDER_MAP[id]=nm[id];
    var o=document.querySelector('#node-'+id+' .node-order'); if(o) o.textContent=nm[id]; });
  /* a building with no lot (a floor just let out): the free lot nearest where it was */
  P.units.forEach(function(ids){ ids.forEach(function(id){ if(lot(P.at[id])) return; var near=null, home=null;
    var p0=P.par0&&P.par0[id]; if(p0) home=lot(P.at[bOf(p0)]);
    if(!home){ var d=(P.d||[]).filter(function(q){ return q.u===ACT[id]; })[0]; if(d) home=[(d.box[0]+d.box[2])/2, (d.box[1]+d.box[3])/2]; }
    near=freeLot(home?home[0]:M.W/2, home?home[1]:M.H/2); if(near) P.at[id]=near; }); });
}
function taken(){ var t={}; Object.keys(P.at).forEach(function(id){ if(isB(id)) t[P.at[id]]=id; }); return t; }
function freeLot(x,y,skip,extra){ var t=taken(), best=null, bd=1e18;
  P.b.forEach(function(ls,i){ ls.forEach(function(L,k){ var key=i+'.'+k; if(t[key] && t[key]!==skip) return; if(extra && extra[key]) return;
    var d=(L[0]-x)*(L[0]-x)+(L[1]-y)*(L[1]-y); if(d<bd){ bd=d; best=key; } }); });
  return best; }
P.par=P.par||{}; P.par0=JSON.parse(JSON.stringify(P.par));
/* what edit mode can change on a landmark: the unit it houses (P.lm), a tower floor's chosen number (P.fx) and whether it was let out (P.out) */
var tk0=Array.isArray(P.tk)?P.tk:[]; P.fx={}; P.out={}; P.tk={}; P.prevAt={}; P.fn=P.fn||{}; P.fn0=JSON.parse(JSON.stringify(P.fn)); P.lm=JSON.parse(JSON.stringify(P.lm0||{}));
Object.keys(P.pl0||{}).forEach(function(k){ if(P.pl0[k].fno) P.fx[k]=P.pl0[k].fno; if(P.pl0[k].out) P.out[k]=1; });
tk0.forEach(function(k){ P.tk[k]=1; });
Object.keys(P.tw||{}).forEach(function(h){ P.tw[h].top0=P.tw[h].top; });
restructure();

/* ── the street graph, built once from the streets: crossings split them ── */
var G=null;
function graph(){
  if(G) return G;
  var segs=[], B=64, bk={};
  M.streets.forEach(function(s,si){ if(s.t) return; var p=s.p; for(var i=0;i+3<p.length;i+=2) segs.push([si,p[i],p[i+1],p[i+2],p[i+3]]); });
  segs.forEach(function(g,k){ for(var bx=Math.floor(Math.min(g[1],g[3])/B);bx<=Math.floor(Math.max(g[1],g[3])/B);bx++)
    for(var by=Math.floor(Math.min(g[2],g[4])/B);by<=Math.floor(Math.max(g[2],g[4])/B);by++){ var kk=bx+','+by; (bk[kk]=bk[kk]||[]).push(k); } });
  var cuts=segs.map(function(){ return []; }), seen={};
  Object.keys(bk).forEach(function(kk){ var ks=bk[kk]; for(var a=0;a<ks.length;a++) for(var b=a+1;b<ks.length;b++){
    var i=ks[a], j=ks[b], key=i<j?i+'_'+j:j+'_'+i; if(seen[key]) continue; seen[key]=1;
    var A=segs[i], C=segs[j]; if(A[0]===C[0] && Math.abs(i-j)===1) continue;
    var d=(A[3]-A[1])*(C[4]-C[2])-(A[4]-A[2])*(C[3]-C[1]); if(Math.abs(d)<1e-9) continue;
    var t=((C[1]-A[1])*(C[4]-C[2])-(C[2]-A[2])*(C[3]-C[1]))/d, u=((C[1]-A[1])*(A[4]-A[2])-(C[2]-A[2])*(A[3]-A[1]))/d;
    if(t>=-1e-6&&t<=1+1e-6&&u>=-1e-6&&u<=1+1e-6){ cuts[i].push(Math.min(1,Math.max(0,t))); cuts[j].push(Math.min(1,Math.max(0,u))); } } });
  var idx={}, X=[], Y=[], adj=[], names=[];
  function node(x,y){ var k=Math.round(x/1.5)+','+Math.round(y/1.5); if(idx[k]==null){ idx[k]=X.length; X.push(x); Y.push(y); adj.push([]); names.push({}); } return idx[k]; }
  segs.forEach(function(g,k){ var ts=[0,1].concat(cuts[k].filter(function(t){ return t>0&&t<1; })).sort(function(a,b){ return a-b; }), prev=null;
    var nm=M.streets[g[0]].n||'';
    ts.forEach(function(t){ var n=node(g[1]+(g[3]-g[1])*t, g[2]+(g[4]-g[2])*t); if(nm) names[n][nm]=1;
      if(prev!=null && prev!==n){ var L=Math.hypot(X[n]-X[prev],Y[n]-Y[prev]); adj[prev].push([n,L]); adj[n].push([prev,L]); } prev=n; }); });
  /* a grid of nodes to find the nearest one */
  var NG={}; X.forEach(function(x,i){ var k=Math.floor(x/120)+','+Math.floor(Y[i]/120); (NG[k]=NG[k]||[]).push(i); });
  G={X:X,Y:Y,adj:adj,names:names,NG:NG}; return G;
}
function nearest(x,y,named,maxd){ var g=graph(), best=-1, bd=(maxd||400)*(maxd||400), gx=Math.floor(x/120), gy=Math.floor(y/120), r=Math.ceil((maxd||400)/120);
  for(var i=-r;i<=r;i++) for(var j=-r;j<=r;j++){ var c=g.NG[(gx+i)+','+(gy+j)]; if(!c) continue;
    c.forEach(function(n){ if(named && Object.keys(g.names[n]).length<named) return; var d=(g.X[n]-x)*(g.X[n]-x)+(g.Y[n]-y)*(g.Y[n]-y); if(d<bd){ bd=d; best=n; } }); }
  return best; }
function route(a,b){
  var g=graph(); if(a<0||b<0) return null; if(a===b) return [a];
  var dist={}, prev={}, H=[[0,a]]; dist[a]=0;
  function push(it){ H.push(it); var i=H.length-1; while(i>0){ var p=(i-1)>>1; if(H[p][0]<=H[i][0]) break; var t=H[p]; H[p]=H[i]; H[i]=t; i=p; } }
  function pop(){ var top=H[0], last=H.pop(); if(H.length){ H[0]=last; var i=0; for(;;){ var l=2*i+1, r=l+1, m=i;
    if(l<H.length&&H[l][0]<H[m][0]) m=l; if(r<H.length&&H[r][0]<H[m][0]) m=r; if(m===i) break; var t=H[m]; H[m]=H[i]; H[i]=t; i=m; } } return top; }
  while(H.length){ var it=pop(), d=it[0], u=it[1]; if(d>dist[u]) continue; if(u===b) break;
    g.adj[u].forEach(function(e){ var nd=d+e[1]; if(dist[e[0]]==null || nd<dist[e[0]]){ dist[e[0]]=nd; prev[e[0]]=u; push([nd,e[0]]); } }); }
  if(dist[b]==null) return null;
  var out=[b]; while(out[out.length-1]!==a) out.push(prev[out[out.length-1]]); return out.reverse();
}
var ENT={};
function entrance(id){ var L=lot(P.at[bOf(id)]); if(!L) return -1; var k=P.at[bOf(id)]; if(ENT[k]==null) ENT[k]=nearest(L[0],L[1],1,300); return ENT[k]; }
/* the real transit (palace_transit_js.py) is given the palace's own parts */
window._palTr.init({M:M, P:P, graph:graph, nearest:nearest, entrance:entrance, lot:lot, bOf:bOf, isB:isB, order:function(){ return ORDER; }, flyMap:function(x,y,z,done){ flyAway(x,y,z,done); }, leave:leaveBoard,
  center:function(x,y){ var cv=document.getElementById('canvas'); if(!cv) return; if(PV) placeAll(); cv.scrollLeft=(x+MX)*Z+gapAt(Z,cv.clientWidth)-cv.clientWidth/2; cv.scrollTop=(y+MY)*Z+gyAt(Z,cv.clientHeight)-cv.clientHeight/2; },
  name:function(id){ var b=bOf(id); return (num(b)?num(b)+' ':'')+title(b); },
  Z:function(){ return Z; }, svg:function(){ return svgD; }, palaceOn:function(){ return palaceOn(); }, el:el, pin:pin, stLbl:stLbl, pts:pts, rp:rp, tube:tube, tubeCol:tubeCol, NEUTRAL:function(){ return NEUTRAL(); }});
if(window._palRide) window._palRide.init({M:M, P:P, lot:lot, bOf:bOf, ucol:ucol, dcol:dcol, tubeCol:tubeCol, NEUTRAL:function(){ return NEUTRAL(); }, nbH:nbHeight, name:function(id){ var b=bOf(id); return (num(b)?num(b)+' ':'')+title(b); }, title:function(id){ return title(id); },
  fillGroups:(typeof fillGroups==='function'?function(){ return fillGroups(); }:null),
  curView:function(){ var cv=document.getElementById('canvas'); if(!cv||!cv.clientWidth) return null; if(PV) placeAll(); return {z:Z, x:cv.scrollLeft, y:cv.scrollTop}; },
  putView:function(v){ if(!v) return; holdView={z:v.z, x:v.x, y:v.y}; restoreView(); },
  fly:function(x,y,z,done){ flyAway(x,y,z,done); }, Z:function(){ return Z; }, palaceOn:function(){ return palaceOn(); },   /* drop in from the aerial view (palace_ride_f.py) */
  mapAt:function(cx,cy){ var cv=document.getElementById('canvas'); if(!cv||!cv.clientWidth) return null; var p=canvasPt(cv,cx,cy), sx=PV?PV.tx:cv.scrollLeft, sy=PV?PV.ty:cv.scrollTop, sz=cvSize(cv); return [(sx+p[0]-gapAt(Z,sz[0]))/Z-MX, (sy+p[1]-gyAt(Z,sz[1]))/Z-MY]; }});   /* the first-person ride (palace_ride.py) */
window._palAirport.init({P:P, Z:function(){ return Z; }, fly:function(x,y,z,done){ flyAway(x,y,z,done); }});
window._palHw.init({M:M, graph:graph, nearest:nearest, flyMap:function(x,y,z){ flyAway(x,y,z); }, Z:function(){ return Z; }, svg:function(){ return svgD; }, pin:pin, stLbl:stLbl, pts:pts, rp:rp, tube:tube});   /* the highways (palace_highway_js.py) */
window._palBr.init({M:M, el:el, pts:pts, pin:pin});     /* the bridges' design elements (palace_bridges.py) */

/* ── the city, drawn once into an <svg> (a page may hold two: the desktop board, a phone's map page) ── */
/* a thing that keeps its size on the screen, at map point (x,y): <g class=cls transform="translate(x y)"><g class="pl-sc">…</g></g>.
   The position is an SVG attribute in map units; the size a unitless CSS scale (--tw) — so the page's CSS zoom cannot move it in
   any browser (Safari zooms px inside an SVG element's CSS transform; Chrome does not). Returns the inner, scaled group. */
function pin(parent, cls, x, y, attrs){ var o={'class':cls, transform:'translate('+(+x)+' '+(+y)+')'}; for(var k in attrs||{}) o[k]=attrs[k];
  var g=el('g',o,parent); return el('g',{'class':'pl-sc'},g); }
/* a station's name beside its ring: dx,dy screen px from the stop, scaled with the ring; the text itself un-scaled (.pl-stt) */
function stLbl(parent, cls, text, x, y, hub, attrs){ var g=pin(parent, 'pl-stl', x, y, attrs), o=el('g',{transform:hub?'translate(20 -15)':'translate(13 -9)'},g);
  var t=el('text',{'class':cls, x:0, y:0, 'text-anchor':'start'},o); t.textContent=text; return t; }
function lbl(parent, cls, text, x, y, anchor){ var t=el('text',{'class':cls, x:x, y:y, 'text-anchor':anchor||'middle'},parent); t.textContent=text; return t; }
function streetLabels(svg, defs, g){
  var by={}, MJ={}, TOP={}; (M.majors||[]).forEach(function(n){ MJ[n]=1; }); (M.top||[]).forEach(function(n){ TOP[n]=1; });
  M.streets.forEach(function(s){ if(s.n && MJ[s.n] && !s.t) (by[s.n]=by[s.n]||[]).push(s); });
  var uid=0;
  Object.keys(by).forEach(function(n){
    var pieces=by[n].map(function(s){ var p=s.p, L=0; for(var i=0;i+3<p.length;i+=2) L+=Math.hypot(p[i+2]-p[i],p[i+3]-p[i+1]); return {p:p,L:L,k:s.k}; })
      .filter(function(q){ return q.L>160; }).sort(function(a,b){ return b.L-a.L; });
    /* one carriageway of a divided street, and no two pieces side by side */
    var kept=[]; pieces.forEach(function(q){ var mx=q.p[q.p.length>>1&~1], my=q.p[(q.p.length>>1&~1)+1];
      if(kept.length<4 && kept.every(function(o){ return Math.hypot(o.mx-mx,o.my-my)>700; })){ q.mx=mx; q.my=my; kept.push(q); } });
    kept.forEach(function(q, pi){
      var p=q.p.slice(), dx=p[p.length-2]-p[0], dy=p[p.length-1]-p[1];
      if((Math.abs(dx)>=Math.abs(dy) && dx<0) || (Math.abs(dx)<Math.abs(dy) && dy>0)){ var r=[]; for(var i=p.length-2;i>=0;i-=2) r.push(p[i],p[i+1]); p=r; }
      var id='pls'+(svg._sid||'')+'-'+(uid++); el('path',{id:id, d:pts(p)},defs);
      var every=1150, n0=Math.max(1,Math.floor(q.L/every));
      for(var j=0;j<n0;j++){ var off=(q.L/n0)*(j+.5);
        var t=el('text',{'class':'pl-st'+(TOP[n]?' top':'')+(q.k>=2?' minor':'')+(pi===0 && j===(n0>>1)?' r0':''), dy:'.35em'},g);
        t._g=atLen(p, off); t._pr=(TOP[n]?600:q.k>=2?150:300)+Math.min(90, q.L/400)+(pi===0 && j===(n0>>1)?5:0)-pi;   /* the label pass (lblFit) */
        t.setAttribute('data-n', n); var tp=el('textPath',{href:'#'+id, startOffset:off, 'text-anchor':'middle'},t); tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=n; }
    });
  });
}
/* ── the city, made of Alto's own parts: every street a connecting line (a coloured
   tube with a frosted centre line), in the colour of the section whose district it
   runs through; the river a glass band; parks and landmarks glass outlines with a
   chip; railways connecting lines with ties. The real map is only the guide. ── */
var TUBE=5, R=20;
function dk(){ return de.classList.contains('dark'); }
function rgbOf(c){ c=String(c||'').trim(); if(c[0]==='#'){ var h=c.slice(1); if(h.length===3) h=h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
  return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)]; }
  var m=/rgba?\(([^)]+)\)/.exec(c); return m?m[1].split(',').slice(0,3).map(function(v){ return parseFloat(v)|0; }):[120,120,140]; }
function lum(r){ return (.2126*r[0]+.7152*r[1]+.0722*r[2])/255; }
/* the colour the map stands on (--pal-ground: the chosen map ground's, palace_backgrounds.py), what the lines are checked against */
var GR=null;
function groundNow(){ var v=getComputedStyle(de).getPropertyValue('--pal-ground').trim(); return v?v.split(',').map(function(q){ return parseFloat(q)||0; }):null; }
/* the engine's contrast rule (_lineAdapt): a line is pushed away from the glass behind it */
function tubeCol(c){ var r=rgbOf(c), bg=GR&&GR.length===3?GR:(dk()?[28,30,40]:[238,238,242]), d=lum(r)-lum(bg), MIN=.3;
  if(Math.abs(d)<MIN){ var dir=lum(bg)>=.5?-1:1, amt=(MIN-Math.abs(d))*255; r=r.map(function(v){ return Math.max(0,Math.min(255,Math.round(v+dir*amt))); }); }
  return 'rgb('+r[0]+','+r[1]+','+r[2]+')'; }
function sheen(){ return dk()?'rgba(255,255,255,0.50)':'rgba(255,255,255,0.72)'; }
var NEUTRAL=function(){ return dk()?'rgb(208,212,226)':'rgb(60,64,84)'; };
/* which district a point lies in: inside a district's box, or within a block of it (the streets just outside an edge keep its colour);
   farther out the city is nobody's (neutral): a neighbourhood is as big as its box, not everything south of it */
var DIST_REACH=200;
function distAt(x,y){ var D=P.d||[], best=null, bd=DIST_REACH*DIST_REACH;
  for(var i=0;i<D.length;i++){ var b=D[i].box; if(x>=b[0]&&x<=b[2]&&y>=b[1]&&y<=b[3]) return D[i].u;
    var cx=Math.max(b[0],Math.min(x,b[2])), cy=Math.max(b[1],Math.min(y,b[3])), d=(cx-x)*(cx-x)+(cy-y)*(cy-y); if(d<bd){ bd=d; best=D[i].u; } }
  return best; }
function dcol(u){ var pm=(typeof PHASE_META!=='undefined')?PHASE_META[u]:null; return pm?pm.colorRaw:null; }
/* a polyline whose corners are Alto's rounded elbows (the connecting lines' r=20) */
function rp(a, r){ r=r||R; if(a.length<6) return pts(a); var d='M'+a[0]+' '+a[1];
  for(var i=2;i+3<a.length;i+=2){ var x=a[i], y=a[i+1], px=a[i-2], py=a[i-1], nx=a[i+2], ny=a[i+3];
    var l1=Math.hypot(x-px,y-py)||1, l2=Math.hypot(nx-x,ny-y)||1, rr=Math.min(r,l1/2,l2/2);
    var cr=Math.abs((x-px)*(ny-y)-(y-py)*(nx-x))/(l1*l2); if(cr<.05){ d+='L'+x+' '+y; continue; }
    d+='L'+(x+(px-x)/l1*rr)+' '+(y+(py-y)/l1*rr)+'Q'+x+' '+y+' '+(x+(nx-x)/l2*rr)+' '+(y+(ny-y)/l2*rr); }
  return d+'L'+a[a.length-2]+' '+a[a.length-1]; }
/* one street in its districts' colours: cut where it passes from one district into the next */
function runsOf(p){ var out=[], cur=null, run=null;
  function push(x,y,u){ if(u!==cur){ if(run) out.push({u:cur, p:run.concat([x,y])}); run=run?[run[run.length-2],run[run.length-1]]:[]; run=[x,y]; cur=u; } else run.push(x,y); }
  for(var i=0;i+3<p.length;i+=2){ var x0=p[i], y0=p[i+1], x1=p[i+2], y1=p[i+3], n=Math.max(1, Math.ceil(Math.hypot(x1-x0,y1-y0)/60));
    for(var k=0;k<n;k++){ var t0=k/n, t1=(k+1)/n, ax=x0+(x1-x0)*t0, ay=y0+(y1-y0)*t0, bx=x0+(x1-x0)*t1, by=y0+(y1-y0)*t1;
      var u=distAt((ax+bx)/2,(ay+by)/2); if(i===0 && k===0){ run=[ax,ay]; cur=u; } if(u!==cur){ out.push({u:cur, p:run.concat([ax,ay])}); run=[ax,ay]; cur=u; } run.push(bx,by); } }
  if(run) out.push({u:cur, p:run}); return out; }
/* v2: a polyline cut where it passes from one district into the next, keeping its own corners (so each run is rounded where the line turns) */
function lruns(p){ var out=[], cur, run=null;
  for(var i=0;i+3<p.length;i+=2){ var x0=p[i], y0=p[i+1], x1=p[i+2], y1=p[i+3], n=Math.max(1, Math.ceil(Math.hypot(x1-x0,y1-y0)/60));
    for(var k=0;k<n;k++){ var ax=x0+(x1-x0)*k/n, ay=y0+(y1-y0)*k/n, bx=x0+(x1-x0)*(k+1)/n, by=y0+(y1-y0)*(k+1)/n, u=distAt((ax+bx)/2,(ay+by)/2);
      if(!run){ run=[x0,y0]; cur=u; }
      if(u!==cur){ if(k) run.push(ax,ay); out.push({u:cur, p:run}); run=[ax,ay]; cur=u; }
      if(k===n-1) run.push(bx,by); } }
  if(run) out.push({u:cur, p:run}); return out.filter(function(r){ return r.p.length>=4; }); }
/* the centre of a flat ring [x0,y0,x1,y1,...] (its vertices' mean: a tile's district) */
function bbx(p){ var b=[1e18,1e18,-1e18,-1e18]; for(var i=0;i+1<p.length;i+=2){ if(p[i]<b[0]) b[0]=p[i]; if(p[i]>b[2]) b[2]=p[i]; if(p[i+1]<b[1]) b[1]=p[i+1]; if(p[i+1]>b[3]) b[3]=p[i+1]; } return b; }
/* Which super-block each tile is in: tiles that share a side not under a heavy line are joined (union-find), so the chunks'
   borders all run under heavy lines; a super-block wider than SB_MAX is cut on its own heavy lines only (never through a street). */
function superBlocks(rings, heavy){
  var n=rings.length, par=new Int32Array(n), HC=64, hz={}, E={}, i, j;
  for(i=0;i<n;i++) par[i]=i;
  function find(a){ while(par[a]!==a){ par[a]=par[par[a]]; a=par[a]; } return a; }
  heavy.forEach(function(h){ var x0=Math.min(h[0],h[2]), x1=Math.max(h[0],h[2]), y0=Math.min(h[1],h[3]), y1=Math.max(h[1],h[3]);
    for(var a=Math.floor((x0-2)/HC);a<=Math.floor((x1+2)/HC);a++) for(var b=Math.floor((y0-2)/HC);b<=Math.floor((y1+2)/HC);b++) (hz[a+','+b]=hz[a+','+b]||[]).push(h); });
  function onHeavy(x, y, dx, dy){ var c=hz[Math.floor(x/HC)+','+Math.floor(y/HC)]; if(!c) return false; var L=Math.hypot(dx,dy)||1;
    return c.some(function(h){ var hx=h[2]-h[0], hy=h[3]-h[1], hl=Math.hypot(hx,hy)||1; if(Math.abs(hx*dy-hy*dx)/(hl*L)>.02) return false;
      var t=((x-h[0])*hx+(y-h[1])*hy)/(hl*hl); if(t<-1e-3 || t>1+1e-3) return false; return Math.abs((x-h[0])*hy-(y-h[1])*hx)/hl<2; }); }
  /* every side, hashed by the cell of its middle: collinear overlapping sides of two tiles are a shared street */
  rings.forEach(function(r, k){ var a=r.t?[r.t[0],r.t[1],r.t[2],r.t[1],r.t[2],r.t[3],r.t[0],r.t[3]]:r.q, m=a.length>>1;
    for(var q=0;q<m;q++){ var x0=a[2*q], y0=a[2*q+1], x1=a[2*((q+1)%m)], y1=a[2*((q+1)%m)+1]; if(Math.hypot(x1-x0,y1-y0)<1) continue;
      var key=Math.round((x0+x1)/2/HC)+','+Math.round((y0+y1)/2/HC); (E[key]=E[key]||[]).push([k,x0,y0,x1,y1]); } });
  function coll(A, B){ var dx=A[3]-A[1], dy=A[4]-A[2], L=Math.hypot(dx,dy)||1;
    function off(x,y){ return Math.abs((x-A[1])*dy-(y-A[2])*dx)/L; } if(off(B[1],B[2])>.6 || off(B[3],B[4])>.6) return null;
    var t0=((B[1]-A[1])*dx+(B[2]-A[2])*dy)/L, t1=((B[3]-A[1])*dx+(B[4]-A[2])*dy)/L, lo=Math.max(0,Math.min(t0,t1)), hi=Math.min(L,Math.max(t0,t1));
    return hi-lo>1?[A[1]+dx/L*(lo+hi)/2, A[2]+dy/L*(lo+hi)/2, dx, dy]:null; }
  Object.keys(E).forEach(function(key){ var p=key.split(','), px=+p[0], py=+p[1], here=E[key];
    for(var a=-1;a<=1;a++) for(var b=-1;b<=1;b++){ var there=E[(px+a)+','+(py+b)]; if(!there) continue;
      here.forEach(function(A){ there.forEach(function(B){ if(A[0]>=B[0]) return; var m=coll(A, B); if(m && !onHeavy(m[0], m[1], m[2], m[3])){ var ra=find(A[0]), rb=find(B[0]); if(ra!==rb) par[ra]=rb; } }); }); } });
  var out=new Array(n); for(i=0;i<n;i++) out[i]=find(i); return out; }
/* the point s along a polyline and the direction there (radians): where a label on a path sits */
function atLen(p, s){ for(var i=0;i+3<p.length;i+=2){ var dx=p[i+2]-p[i], dy=p[i+3]-p[i+1], l=Math.hypot(dx,dy);
    if(s<=l || i+4>=p.length){ var f=l?Math.max(0,Math.min(1,s/l)):0; return [p[i]+dx*f, p[i+1]+dy*f, Math.atan2(dy,dx)]; } s-=l; }
  return [p[0]||0, p[1]||0, 0]; }
function ringC(a){ var n=a.length>>1, x=0, y=0; for(var i=0;i<n;i++){ x+=a[2*i]; y+=a[2*i+1]; } return [x/n, y/n]; }
/* a smooth path through points (Catmull-Rom as cubic curves): a river bends in wide, even curves */
function smoothD(a, i0, i1){ var n=a.length>>1; i0=i0||0; i1=(i1==null)?n-1:i1; var d='M'+a[2*i0]+' '+a[2*i0+1];
  for(var i=i0;i<i1;i++){ var i0=Math.max(0,i-1), i3=Math.min(n-1,i+2), x0=a[2*i0], y0=a[2*i0+1], x1=a[2*i], y1=a[2*i+1], x2=a[2*i+2], y2=a[2*i+3], x3=a[2*i3], y3=a[2*i3+1];
    d+='C'+(x1+(x2-x0)/6).toFixed(1)+' '+(y1+(y2-y0)/6).toFixed(1)+' '+(x2-(x3-x1)/6).toFixed(1)+' '+(y2-(y3-y1)/6).toFixed(1)+' '+x2+' '+y2; }
  return d; }
/* the river's bands as opaque colours (the water, each light step laid over it, the sheen over those), or null where the water is not opaque */
function rgbaOf(c){ c=String(c||'').trim(); if(c[0]==='#'){ var r=rgbOf(c); return [r[0],r[1],r[2],1]; }
  var m=/rgba?\(([^)]+)\)/.exec(c); if(!m) return null; var v=m[1].split(',').map(function(q){ return parseFloat(q); }); return [v[0],v[1],v[2],v.length>3?v[3]:1]; }
function riverBands(LITE){ var cs=getComputedStyle(de), b=rgbaOf(cs.getPropertyValue('--pal-river')), l=rgbaOf(cs.getPropertyValue('--pal-rv-lite')), sh=rgbaOf(cs.getPropertyValue('--pal-rv-sheen'));
  if(!b || !l || !sh || b[3]<1) return null;
  function over(c, o, a){ return [0,1,2].map(function(i){ return c[i]*(1-a)+o[i]*a; }); }
  function css(c){ return 'rgb('+c.map(function(v){ return Math.round(v); }).join(',')+')'; }
  var out=[css(b)], c=b.slice(0,3); LITE.forEach(function(q){ c=over(c, l, q[1]*l[3]); out.push(css(c)); }); out.push(css(over(c, sh, sh[3]))); return out; }
/* a river's name set along the band, as often as its length on the glass allows, reading upward (or rightward) */
function riverLabels(svg, defs, parent, r, k){
  var p=r.p, n=p.length>>1, cum=[0], i;
  for(i=1;i<n;i++) cum.push(cum[i-1]+Math.hypot(p[2*i]-p[2*i-2],p[2*i+1]-p[2*i-1]));
  var lo=-1, hi=-1; for(i=0;i<n;i++){ var x=p[2*i], y=p[2*i+1], on=x>40 && x<M.W-40 && y>40 && y<M.H-40; if(on){ if(lo<0) lo=i; hi=i; } }
  if(lo<0 || hi-lo<4) return;
  var s0=cum[lo], s1=cum[hi], fs=Math.max(20, (r.w||100)*.21), tot=cum[n-1], L=s1-s0;
  var fw=null, bw=null, cnt=Math.max(1,Math.round(L/(fs*r.n.length*1.5+1500)));
  function tangent(s){ for(var q=1;q<n-1 && cum[q]<s;q++); var a=Math.max(0,q-3), b=Math.min(n-1,q+3); return [p[2*b]-p[2*a], p[2*b+1]-p[2*a+1]]; }
  for(var j=0;j<cnt;j++){ var s=s0+L*(j+.5)/cnt, tg=tangent(s), tl=Math.hypot(tg[0],tg[1])||1, rev=tg[0]<-.35*tl?true:tg[0]>.35*tl?false:tg[1]>0, id='plr'+(svg._sid||'')+k+(rev?'b':'f');
    if(rev? !bw : !fw){ var pp=p; if(rev){ pp=[]; for(i=n-1;i>=0;i--) pp.push(p[2*i],p[2*i+1]); } el('path',{id:id, d:smoothD(pp)},defs); if(rev) bw=1; else fw=1; }
    var t=el('text',{'class':'pl-river', dy:'.35em', style:'font-size:max(calc(13px / var(--pz,1)),'+fs.toFixed(0)+'px)'},parent), tp=el('textPath',{href:'#'+id, startOffset:(rev?tot-s:s).toFixed(0), 'text-anchor':'middle'},t);
    t._g=atLen(p, s); t._fs=fs; t._pr=800-j-k*.1;
    tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=r.n; } }
/* the streets' tubes, chunk by chunk ({'district|chunk': d}): the .95 tube over the ground and the sheen over it are worked out as
   opaque colours, and each district's tubes are all drawn before its sheens, so the chunks look exactly as one path per district
   did (where two chunks meet on a street, or two lines overlap, a line is drawn twice in one colour: no darker seam, no lost sheen) */
function stubes(parent, by, tc, w, cls){ var g=GR&&GR.length===3?GR:(dk()?[28,30,40]:[238,238,242]), sh=rgbaOf(sheen())||[255,255,255,.7], us=[], ks={};
  function css(a){ return 'rgb('+a.map(function(v){ return Math.round(v); }).join(',')+')'; }
  Object.keys(by).forEach(function(k){ var u=String(k).split('|')[0]; if(!ks[u]){ ks[u]=[]; us.push(u); } ks[u].push(k); });
  us.forEach(function(u){ var c=rgbOf(tc(ks[u][0])), t=[0,1,2].map(function(i){ return c[i]*.95+g[i]*.05; }), s2=t.map(function(v,i){ return v*(1-sh[3])+sh[i]*sh[3]; });
    ks[u].forEach(function(k){ el('path',{'class':'pl-tube '+cls, d:by[k], stroke:css(t), 'stroke-width':w},parent); });
    ks[u].forEach(function(k){ el('path',{'class':'pl-sheen '+cls, d:by[k], stroke:css(s2), 'stroke-width':Math.max(.9, w*.34)},parent); }); }); }
function tube(parent, d, col, w, op, cls){
  var t=el('path',{'class':'pl-tube'+(cls?' '+cls:''), d:d, stroke:col, 'stroke-width':w},parent); if(op<1) t.setAttribute('stroke-opacity',op);
  el('path',{'class':'pl-sheen'+(cls?' '+cls:''), d:d, stroke:sheen(), 'stroke-width':Math.max(.9, w*.34)},parent); return t; }
/* the lines (rails, transit, tours, routes, stops) tuck BEHIND the landmark buildings and the building chips: they stay the last two layers
   (before the invisible hit paths and the hover pill), however late something else is added to the map */
function stackLayers(svg){
  var lm=svg.querySelector(':scope > .pl-lms'), bl=svg.querySelector(':scope > .pl-blds'), ts=svg.querySelector(':scope > .pl-tstns'); if(!lm || !bl) return;
  var ch=[].filter.call(svg.children, function(c){ return !c.matches('.pl-route-hits,.pl-tr-hits,.pl-hov,.pl-portals,.pl-fx'); }), n=ch.length;
  if(ch[n-2]===lm && ch[n-1]===bl && (!ts || ch[n-3]===ts)) return;
  if(ts) svg.appendChild(ts);                       /* the stations over the highways and street names, under the landmarks */
  svg.appendChild(lm); svg.appendChild(bl);
  [].forEach.call(svg.querySelectorAll(':scope > .pl-portals,:scope > .pl-fx'), function(h){ svg.appendChild(h); });      /* the airport portals ride over the buildings they stand on */
  [].forEach.call(svg.querySelectorAll(':scope > .pl-route-hits,:scope > .pl-tr-hits,:scope > .pl-hov'), function(h){ svg.appendChild(h); }); }
function drawCity(svg){
  if(!svg._stk){ svg._stk=new MutationObserver(function(){ stackLayers(svg); }); svg._stk.observe(svg,{childList:true}); }
  GR=groundNow(); var tD0=performance.now();
  svg.innerHTML=''; svg._li=null; svg._dcKey=null;
  var defs=el('defs',{},svg);
  /* the glass the city stands on */
  /* it runs on past the city's edge (the page never scrolls that far): an enlarged building at the
     very edge of the city pulls the board a little off-centre, and what shows there is more glass */
  var BL=1600; el('rect',{'class':'pl-glass', x:-MX-BL, y:-MY-BL, width:VW+2*BL, height:VH+2*BL, rx:34},svg);
  /* each neighbourhood's ground, unseen: pointing at it names the unit it holds */
  var wash=el('g',{'class':'pl-washes'},svg);
  (P.d||[]).forEach(function(d){ var pm=PHASE_META[d.u], b=d.box; if(!pm||!b) return; var ins=16;
    el('rect',{'class':'pl-dtint', x:b[0]+ins, y:b[1]+ins, width:Math.max(10,b[2]-b[0]-2*ins), height:Math.max(10,b[3]-b[1]-2*ins), rx:34, fill:pm.colorRaw, 'data-u':d.u},wash); });
  /* ── parks: green glass shapes snapped to the grid, their walkways and plazas; above the washes, under every street ── */
  var pkg=el('g',{'class':'pl-parks'},svg);
  function rpc(a, r){ var n=a.length>>1, d=''; for(var i=0;i<n;i++){ var x=a[2*i], y=a[2*i+1], px=a[2*((i+n-1)%n)], py=a[2*((i+n-1)%n)+1], nx=a[2*((i+1)%n)], ny=a[2*((i+1)%n)+1],
      l1=Math.hypot(x-px,y-py)||1, l2=Math.hypot(nx-x,ny-y)||1, rr=Math.min(r,l1/2,l2/2), sx=x+(px-x)/l1*rr, sy=y+(py-y)/l1*rr;
    d+=(i?'L':'M')+sx+' '+sy+'Q'+x+' '+y+' '+(x+(nx-x)/l2*rr)+' '+(y+(ny-y)/l2*rr); } return d+'Z'; }
  (M.parks||[]).forEach(function(pk){ var g=el('g',{'class':'pl-pk-g','data-name':pk.n},pkg);
    el('path',{'class':'pl-pk', d:(pk.r||[]).map(function(r){ return rpc(r, R); }).join('')},g);
    (pk.p||[]).forEach(function(p){ el('path',{'class':'pl-pkp', d:rp(p)},g); });
    (pk.o||[]).forEach(function(o){ el('circle',{'class':'pl-pko', cx:o[0], cy:o[1], r:o[2]},g); }); });
  /* ── /parks ── */
  /* the streets: every block a rounded tile of connecting line, so each street
     curves at every intersection; the tiles in their district's colour */
  /* Each colour's blocks were one path per district: WebKit stroked all of it again for every 512 px tile it repainted (a zoom's
     end or a pan exposing new tiles cost 150-400 ms). They are now one path per district per SUPER-BLOCK (the blocks between
     heavy lines, superBlocks), which a repainted tile skips unless it shows it. Two blocks side by side share a street; drawn in
     two paths that street would be stroked twice (its anti-aliased edge darker), so every border between two chunks runs under a
     heavy line, which is drawn over it. The heavy lines, loose edges and the tubes' colours stay as they were (per district). */
  var sg=el('g',{'class':'pl-streets'},svg), byU={};
  function tileD(t){ var x0=t[0], y0=t[1], x1=t[2], y1=t[3], r=Math.min(R, (x1-x0)/2, (y1-y0)/2);
    return 'M'+(x0+r)+' '+y0+'H'+(x1-r)+'Q'+x1+' '+y0+' '+x1+' '+(y0+r)+'V'+(y1-r)+'Q'+x1+' '+y1+' '+(x1-r)+' '+y1
      +'H'+(x0+r)+'Q'+x0+' '+y1+' '+x0+' '+(y1-r)+'V'+(y0+r)+'Q'+x0+' '+y0+' '+(x0+r)+' '+y0+'Z'; }
  /* two weights, as the connecting lines have: every block's outline is a minor street; the sides that
     lie on a major street (the grid's columns and rows are named in M.cols / M.rows) are drawn again,
     heavier, over it, so a major street runs straight through the junctions and the minor ones curve into it */
  var MJs={}; (M.majors||[]).forEach(function(n){ MJs[n]=1; });
  var gx=[], gy=[]; (M.tiles||[]).concat(M.edges||[]).forEach(function(t){ gx.push(t[0],t[2]); gy.push(t[1],t[3]); });
  function uniq(a){ return a.sort(function(p,q){ return p-q; }).filter(function(v,i,r){ return !i || v!==r[i-1]; }); }
  gx=uniq(gx); gy=uniq(gy);
  var colMaj={}, rowMaj={}, okGrid=(M.cols||[]).length===gx.length && (M.rows||[]).length===gy.length;
  if(okGrid){ gx.forEach(function(v,i){ colMaj[v]=!!MJs[M.cols[i]]; }); gy.forEach(function(v,i){ rowMaj[v]=!!MJs[M.rows[i]]; }); }
  var byM={}, seen={}, heavy=[];
  /* v2 (city_lattice.py): when any street carries L (a heavy lattice line, in any domain) the heavy lines are drawn from those
     streets and this overlay of the upright tiles' edges is off */
  var hasL=M.streets.some(function(st){ return st.L; });
  function major(x0,y0,x1,y1){ if(!okGrid || hasL) return; var k=x0+','+y0+','+x1+','+y1; if(seen[k]) return; seen[k]=1;
    if(x0===x1? !colMaj[x0] : !rowMaj[y0]) return;
    var u=distAt((x0+x1)/2,(y0+y1)/2); byM[u]=(byM[u]||'')+'M'+x0+' '+y0+'L'+x1+' '+y1; heavy.push([x0,y0,x1,y1]); }
  var rings=[];
  /* a block or loose line the river runs through is not drawn whole: palace_banks.cut_outlines lists it (tcut / ecut / qcut) and draws its dry
     pieces as M.te polylines that end at the bank */
  var TC={}, EC={}, QC={}; (M.tcut||[]).forEach(function(i){ TC[i]=1; }); (M.ecut||[]).forEach(function(i){ EC[i]=1; }); (M.qcut||[]).forEach(function(i){ QC[i]=1; });
  (M.tiles||[]).forEach(function(t,ti){ if(TC[ti]) return; rings.push({t:t, c:[(t[0]+t[2])/2,(t[1]+t[3])/2]});
    major(t[0],t[1],t[2],t[1]); major(t[0],t[3],t[2],t[3]); major(t[0],t[1],t[0],t[3]); major(t[2],t[1],t[2],t[3]); });
  (M.edges||[]).forEach(function(e,ei){ if(EC[ei]) return; var u=distAt((e[0]+e[2])/2,(e[1]+e[3])/2); byU[u]=(byU[u]||'')+'M'+e[0]+' '+e[1]+'L'+e[2]+' '+e[3]; major(e[0],e[1],e[2],e[3]); });
  /* v2 (city_lattice.py): a tilted domain's blocks and every block a seam cuts are polygon tiles (M.tq: flat rings), rounded at
     each corner like any tile; the loose lines of those domains are polylines (M.te), rounded where they turn (a T onto a seam) */
  (M.tq||[]).forEach(function(a,qi){ if(QC[qi]) return; rings.push({q:a, c:ringC(a)}); });
  (M.te||[]).forEach(function(p){ if(p.length<4) return; var u=distAt((p[0]+p[p.length-2])/2,(p[1]+p[p.length-1])/2); byU[u]=(byU[u]||'')+rp(p); });
  if(hasL) M.streets.forEach(function(st){ if(st.L) for(var i=0;i+3<st.p.length;i+=2) heavy.push([st.p[i],st.p[i+1],st.p[i+2],st.p[i+3]]); });
  var sbk=superBlocks(rings, heavy);
  rings.forEach(function(r, i){ var u=distAt(r.c[0], r.c[1]), k=u+'|'+sbk[i]; byU[k]=(byU[k]||'')+(r.t?tileD(r.t):rpc(r.q, R)); });
  function tc(k){ var u=String(k).split('|')[0]; return tubeCol(dcol(u==='null'?null:+u)||NEUTRAL()); }
  stubes(sg, byU, tc, 3.6, 't-min'); stubes(sg, byM, tc, 5.6, 't-maj');
  /* v2: a heavy lattice line (st.L) runs straight through its crossings and turns, rounded, where it bends; in each district's colour */
  if(hasL){ var byL={}; M.streets.forEach(function(st){ if(st.L) lruns(st.p).forEach(function(r){ byL[r.u]=(byL[r.u]||'')+rp(r.p); }); });
    stubes(sg, byL, tc, 5.6, 't-maj'); }
  /* the diagonals: one clean line, joining the grid with rounded elbows */
  M.streets.forEach(function(st){ if(st.d) tube(sg, rp(st.p), tubeCol(dcol(distAt(st.p[2],st.p[3]))||NEUTRAL()), 5.6, .95, 't-maj'); });
  /* the rivers: each a broad glass band (a connecting line grown wide: edge, body, a light
     centre, a sheen) on a smooth course, run off the glass at its ends; the bridges over it */
  var cp=el('clipPath',{id:'plclip'+(svg._sid||'')},defs); el('rect',{x:-MX, y:-MY, width:VW, height:VH, rx:34},cp);
  var rv=el('g',{'class':'pl-river-g','clip-path':'url(#plclip'+(svg._sid||'')+')'},svg);
  /* the glass: lighter toward the middle in soft steps, then the sheen of Alto's own connecting lines. The steps are the light
     laid over the (opaque) water at .10/.12/.14/.18, the sheen over them: each band's colour is worked out here and drawn opaque,
     in pieces of the course, so a repainted tile strokes only the pieces it shows (one whole river's five wide strokes, for every
     tile, were a third of a frame); opaque pieces of one colour overlap with no seam. The rim (translucent, over the ground) stays whole. */
  var LITE=[[.84,.10],[.68,.12],[.52,.14],[.36,.18]], bands=riverBands(LITE);
  (M.river||[]).forEach(function(r){ var d=smoothD(r.p), w=r.w||100;
    el('path',{'class':'pl-rv-bank', d:d, 'stroke-width':w+64},rv);                           /* the banks: a green margin either side */
    el('path',{'class':'pl-rv-rim', d:d, 'stroke-width':w+12},rv);
    if(!bands){ el('path',{'class':'pl-rv-body', d:d, 'stroke-width':w},rv);
      LITE.forEach(function(l){ el('path',{'class':'pl-rv-lite', d:d, 'stroke-width':w*l[0], 'stroke-opacity':l[1]},rv); });
      el('path',{'class':'pl-rv-sheen', d:d, 'stroke-width':Math.max(2, w*.13)},rv); return; }
    var n=r.p.length>>1, cut=[0], acc=0; for(var i=1;i<n;i++){ acc+=Math.hypot(r.p[2*i]-r.p[2*i-2], r.p[2*i+1]-r.p[2*i-1]); if(acc>=1800 && i<n-1){ cut.push(i); acc=0; } } cut.push(n-1);
    var parts=[]; for(var c=0;c+1<cut.length;c++) parts.push(smoothD(r.p, cut[c], cut[c+1]));
    var ws=[w].concat(LITE.map(function(l){ return w*l[0]; }), [Math.max(2, w*.13)]), cls=['pl-rv-body','pl-rv-lite','pl-rv-lite','pl-rv-lite','pl-rv-lite','pl-rv-sheen'];
    ws.forEach(function(sw, li){ parts.forEach(function(pd){ el('path',{'class':cls[li]+' rv-op', d:pd, 'stroke-width':sw, style:'stroke:'+bands[li]+';stroke-opacity:1'},rv); }); }); });
  /* the river trails along the banks (palace_banks.py): a dashed path with its name along it */
  var rtg=el('g',{'class':'pl-rtrails'},svg);
  (M.rtrails||[]).forEach(function(t,i){ var id='rtr'+(svg._sid||'')+i; el('path',{'class':'pl-rtrail pl-rtrail-c', d:pts(t.p)},rtg); var pa=el('path',{'class':'pl-rtrail', d:pts(t.p), id:id},rtg);
    var tx=el('text',{'class':'pl-rtname'},rtg), tp=el('textPath',{startOffset:'50%','text-anchor':'middle'},tx); tp.setAttribute('href','#'+id); tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=t.n; });
  var bridges=el('g',{'class':'pl-bridges'},svg), labels0=el('g',{'class':'pl-brnames'},svg);
  /* a bridge has a deck, so it reads over the water in any colour: piers, rail lines, the deck, then the street's own line on it; the big ones are named */
  var brSeen=[];
  M.streets.forEach(function(st){ if(!st.o) return; var d=pts(st.p);
    var plan=window._palBr.under(bridges, st, d);              /* piers or pilasters, cables, the deck, joints or hangers (palace_bridges.py) */
    tube(bridges, d, tubeCol(dcol(distAt(st.p[0],st.p[1]))||NEUTRAL()), 5.6, .95, 't-maj'); window._palBr.over(bridges, plan); });
  M.streets.forEach(function(st){ if(!st.o || !st.n || st.k>0) return; var p=st.p, n=p.length, L=0, i;
    for(i=0;i+3<n;i+=2) L+=Math.hypot(p[i+2]-p[i],p[i+3]-p[i+1]); if(L<120) return;
    var mx=(p[0]+p[n-2])/2, my=(p[1]+p[n-1])/2, nm=/bridge/i.test(st.n)?st.n:st.n+' Bridge';
    if(brSeen.some(function(q){ return q.n===nm && Math.hypot(q.x-mx,q.y-my)<400; })) return; brSeen.push({n:nm,x:mx,y:my});
    var q=p.slice(); if(q[n-2]<q[0] || (Math.abs(q[n-2]-q[0])<1 && q[n-1]>q[1])){ q=[]; for(i=n-2;i>=0;i-=2) q.push(p[i],p[i+1]); }
    /* the name's path runs a little past both ends of the deck, so a long name is never cut short */
    var dx=q[q.length-2]-q[0], dy=q[q.length-1]-q[1], dl=Math.hypot(dx,dy)||1, ex=dx/dl*240, ey=dy/dl*240;
    q=[q[0]-ex,q[1]-ey].concat(q,[q[q.length-2]+ex,q[q.length-1]+ey]);
    var id='plb'+(svg._sid||'')+'-'+brSeen.length; el('path',{id:id, d:pts(q)},defs);
    var t=el('text',{'class':'pl-brn'+(st.br?' big':''), dy:'-1.25em'},labels0), tp=el('textPath',{href:'#'+id, startOffset:'50%', 'text-anchor':'middle'},t);
    var ql=0; for(i=0;i+3<q.length;i+=2) ql+=Math.hypot(q[i+2]-q[i],q[i+3]-q[i+1]); t._g=atLen(q, ql/2); t._up=1.6;
    tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=nm; });
  var lg=el('g',{'class':'pl-lms'},svg);
  /* the railway: straight, above ground, a connecting line with ties */
  var rg=el('g',{'class':'pl-rails'},svg);
  (M.rails||[]).forEach(function(r){ var d=pts(r.p), c=r.c||NEUTRAL();
    el('path',{'class':'pl-ties', d:d, stroke:c},rg); tube(rg, d, c, 4.6, .95, 'r-line'); });
  window._palHw.lines(svg);                    /* the highways, under the transit (palace_highway_js.py) */
  window._palTr.lines(svg);                    /* the real lines: SEPTA, PATCO (palace_transit.py) */
  var bg=el('g',{'class':'pl-blds'},svg);
  var route=el('g',{'class':'pl-routes'},svg);
  /* stations: Alto's ring (a tube bent into a circle, its sheen on top); a hub is a double ring */
  var stl=el('g',{'class':'pl-stns'},svg);
  (M.stations||[]).forEach(function(s){
    var hub=s.hub || s.k==='rail';
    var c=NEUTRAL(), sg_=pin(stl, 'pl-stn', s.x, s.y);
    /* a ring is drawn at the origin of its own group, which the page scales to the screen (a ring keeps its size at every zoom) */
    if(hub){ el('circle',{'class':'pl-ring hub', cx:0, cy:0, r:13, stroke:c},sg_); el('circle',{'class':'pl-ring-sh', cx:0, cy:0, r:13},sg_);
      el('circle',{'class':'pl-ring', cx:0, cy:0, r:6, stroke:c},sg_); }
    else { el('circle',{'class':'pl-ring', cx:0, cy:0, r:6.5, stroke:c},sg_); el('circle',{'class':'pl-ring-sh', cx:0, cy:0, r:6.5},sg_); }
    stLbl(stl, 'pl-stt'+(hub?' hub':''), s.n, s.x, s.y, hub).setAttribute('data-n', s.n);
  });
  window._palTr.stations(svg);
  window._palHw.stops(svg);
  var labels=el('g',{},svg);
  (M.river||[]).forEach(function(r,i){ if(r.n) riverLabels(svg, defs, labels, r, i); });
  streetLabels(svg, defs, labels);
  (M.parks||[]).forEach(function(pk){ if(pk.n && pk.t){ var t=lbl(labels, 'pl-pkt'+(pk.z>3?' big':''), pk.n, pk.t[0], pk.t[1]); t._g=[pk.t[0], pk.t[1], 0]; t._up=.35; } });
  /* landmark buildings: each fills its block with a little 3D of the real building, named (palace_landmarks.py); one with a page shows what is inside and opens it */
  /* back to front (the ground line further down the map stands in front): a tower rises over the blocks behind it */
  (M.landmarks||[]).slice().sort(function(p,q){ return ((p.box||[0,0,0,0])[3])-((q.box||[0,0,0,0])[3]); }).forEach(function(l){ var b=l.box; if(!b) return; var c=dcol(distAt(l.x,l.y))||NEUTRAL();
    var g=el('g',{'class':'pl-lmb'+(l.page?' has-page':''), 'data-page':l.page||'', 'data-name':l.n},lg);
    /* v2: a landmark of a tilted domain (l.a): palace_landmarks.draw turns its CARD square to its blocks (an SVG attribute, never CSS px)
       and stands the building upright on the turned card's middle (the 3/4 view's up is the page's up) */
    var tw_=null; Object.keys(P.tw||{}).forEach(function(h){ if(P.tw[h].n===l.n) tw_=h; });
    if(tw_) g.setAttribute('data-tower', tw_);
    window._palLm.draw(g, l, {defs:defs, sid:svg._sid||'', color:c, ins:14, all:M.landmarks||[], pageName:pageName, open:openPage, tower:tw_?{hub:tw_, top:P.tw[tw_].top, num:num(tw_), title:title(tw_)}:null}); });
  /* boats (palace_boats.py) and bases (palace_fleet.py): the hosted fleet script draws them, each for what it is — a battleship, a carrier, a submarine, a tall ship — and arms the warships */
  if(!window._palFleet && ((M.boats&&M.boats.length)||(M.bases&&M.bases.length))) palLoadFleet();
  if(window._palFleet) window._palFleet.draw(lg, M, fleetHost());
  /* the landmark names over every building: a tower in front (the next block down a column of towers, rising 300 m+ at
     true scale, more than a row) would otherwise hide the name hanging under the card behind it. Each name keeps its
     landmark's colours, --lm-nat and (tilted district) offset on its own .pl-lmn wrapper, data-name tying it back */
  var lmn=el('g',{'class':'pl-lmns'},lg);
  [].forEach.call(lg.querySelectorAll('.pl-lmb'), function(g){ var L=g._lm; if(!L || !L.nameT) return; var up=L.nameT.parentNode;
    var w=el('g',{'class':'pl-lmn'+(g.classList.contains('has-page')?' has-page':''), 'data-name':g.getAttribute('data-name')||'', 'data-page':g.getAttribute('data-page')||''},lmn);
    w._lm=L;   /* the name's wrapper knows its landmark (lblFit reads the card from it: the over-the-card spot needs it) */
    w.setAttribute('style', g.getAttribute('style')||''); if(up!==g && up.getAttribute('transform')) w.setAttribute('transform', up.getAttribute('transform'));
    w.appendChild(L.nameT); if(L.sub) w.appendChild(L.sub); });
  /* districts: the neighbourhood's own name over its buildings (the unit it holds is in its pop-up) */
  (P.d||[]).forEach(function(d){ var pm=PHASE_META[d.u]; if(!pm) return;
    var c=districtCentre(d), t=el('text',{'class':'pl-dist', x:c[0], y:c[1], 'text-anchor':'middle', fill:tubeCol(pm.colorRaw), 'data-u':d.u},labels);
    t._g=[c[0], c[1], 0]; t._up=.35;
    t.textContent=d.n || pm.label; });
  /* ── neighbourhood names: label only ── */
  (M.banners||[]).forEach(function(b){ var t=el('text',{'class':'pl-banner', x:b.x, y:b.y, 'text-anchor':'middle', 'font-size':b.s, 'aria-hidden':'true'},labels); t.textContent=b.n; });
  (M.areas||[]).forEach(function(a){ var t=el('text',{'class':'pl-area', x:a.x, y:a.y, 'text-anchor':'middle', 'data-r':a.r||2, 'aria-hidden':'true'},labels); t.textContent=a.n; t._g=[a.x, a.y, 0]; t._up=.35; });
  /* ── /neighbourhood names ── */
  lbl(labels,'pl-credit','Map data © OpenStreetMap contributors', M.W+MX-18, M.H+MY-18, 'end');
  var hits=el('g',{'class':'pl-hits'},svg);
  M.streets.forEach(function(s){ if(!s.n || s.t) return; var h=el('path',{'class':'pl-hit', d:pts(s.p)},hits); h._n=s.n; });
  window._palTr.hits(svg);
  window._palHw.hits(svg);
  window._palTr.portals(svg);                  /* the airport portals, over the stations' buildings (palace_transit_js.py) */
  svg._b=bg; svg._r=route;
  drawBuildings(svg);
  sizeChips(svg);
  if(svg===svgD){ window._palTr.ready(); window._palHw.ready(); }
  (window._palT=window._palT||{}).draw=Math.round(performance.now()-tD0);
}
/* ── the names on the map: which show. Every name keeps its size on the screen, so far out they would pile up (Center City:
   the towers', the neighbourhoods', the streets'). When a zoom settles the names are taken in priority order: a unit's district
   (always), a landmark (one with a page, a tower, the bigger first), a river, a main street (the longer first), a neighbourhood
   by rank, a big bridge or park, the other streets, the small bridges and parks, the minor streets; one that would touch a name
   already kept is hidden (a landmark's card, a chip, a station's name shown and, for a neighbourhood, a building also count).
   A name of rank r appears once the board is zoomed AREA_K[r] times in from the whole city. Each name's box (turned along its
   street) is worked out from the map, not measured from the page, so a hidden name costs nothing; and only names within reach of
   the window are laid out at all (display), checked again when a pan stops: the page lays out tens of names, not a thousand. ── */
var AREA_K=[0, 0, 2, 4, 8];
function areaSoon(svg){ clearTimeout(svg._arT); svg._arT=setTimeout(function(){ if(svg===svgD && PV){ areaSoon(svg); return; } lblFit(svg); }, 90); }
function areaFit(svg){ lblFit(svg); }
var LBL_UP={'pl-area':1,'pl-dist':1,'pl-river':1,'pl-brn':1,'pl-pkt':1}, LBL_LS={'pl-st':.03,'pl-area':.09,'pl-dist':.07,'pl-river':.3,'pl-brn':.09,'pl-pkt':.14,'lm-name':.01};
/* a name's size on the screen in px (as its CSS sets it) */
function lblFS(it, z, phone){ var t=it.t; switch(it.k){ case 'pl-st': return 11.5; case 'pl-brn': return 9.5; case 'pl-pkt': return 10.5;
  case 'pl-dist': return Math.max(11, Math.min(20, 10.5+8*z)); case 'pl-area': return phone?Math.max(10.5, Math.min(13, 8.5+5*z)):Math.max(9, Math.min(13, 7.5+5*z));
  case 'pl-river': return Math.max(13, (t._fs||20)*z);
  case 'lm-name': var n=parseFloat(t.parentNode.style.getPropertyValue('--lm-nat'))||12; return Math.min(Math.max(11.5, n*z), 21); } return 11; }
function lblItems(svg){ if(svg._li) return svg._li; var L=[];
  function add(t, k, pr, fixed){ if(t) L.push({t:t, k:k, pr:pr, fixed:!!fixed, q:0, n:(t.textContent||'').length, vis:t.style.display!=='none'}); }
  svg.querySelectorAll('text.pl-dist').forEach(function(t){ add(t, 'pl-dist', 1000, 1); });
  svg.querySelectorAll('.pl-lmb').forEach(function(g){ var m=g._lm; if(m) add(m.nameT, 'lm-name', 900+(m.page?50:0)+(m.tower?30:0)+Math.min(40, m.w*m.h/2e4)); });
  svg.querySelectorAll('text.pl-river').forEach(function(t){ add(t, 'pl-river', t._pr||800); });
  svg.querySelectorAll('text.pl-st').forEach(function(t){ add(t, 'pl-st', t._pr||300); });
  svg.querySelectorAll('text.pl-area').forEach(function(t){ add(t, 'pl-area', 560-40*Math.min(4, Math.max(1, +t.getAttribute('data-r')||2))); });
  svg.querySelectorAll('text.pl-brn,text.pl-pkt').forEach(function(t){ add(t, t.classList.contains('pl-brn')?'pl-brn':'pl-pkt', t.classList.contains('big')?500:250); });
  L.sort(function(a,b){ return b.pr-a.pr; }); return svg._li=L; }
/* what the zoom's own rules (the CSS: .far / .mid) let show */
function lblLod(it, svg, z, zf){ var c=it.t.classList, far=svg.classList.contains('far'), mid=svg.classList.contains('mid');
  switch(it.k){ case 'pl-st': return far?(c.contains('top') && c.contains('r0')):mid?!c.contains('minor'):true;
    case 'pl-brn': case 'pl-pkt': return !far || c.contains('big');
    case 'pl-area': return z>=zf*AREA_K[Math.min(4, Math.max(1, +it.t.getAttribute('data-r')||2))]*.999; }
  return true; }
function obb(x, y, a, hl, hh){ var c=Math.cos(a), s=Math.sin(a), ex=Math.abs(c)*hl+Math.abs(s)*hh, ey=Math.abs(s)*hl+Math.abs(c)*hh;
  return {x:x, y:y, c:c, s:s, hl:hl, hh:hh, l:x-ex, t:y-ey, r:x+ex, b:y+ey}; }
function rbox(r, sr){ var x=(r.left+r.right)/2-sr.left, y=(r.top+r.bottom)/2-sr.top; return obb(x, y, 0, r.width/2, r.height/2); }
/* two turned boxes touch (separating axes) */
function obbHit(A, B){ if(A.r<B.l || B.r<A.l || A.b<B.t || B.b<A.t) return false;
  var ax=[[A.c,A.s],[-A.s,A.c],[B.c,B.s],[-B.s,B.c]], dx=B.x-A.x, dy=B.y-A.y;
  for(var i=0;i<4;i++){ var u=ax[i][0], v=ax[i][1], d=Math.abs(dx*u+dy*v);
    var ra=A.hl*Math.abs(A.c*u+A.s*v)+A.hh*Math.abs(-A.s*u+A.c*v), rb=B.hl*Math.abs(B.c*u+B.s*v)+B.hh*Math.abs(-B.s*u+B.c*v);
    if(d>ra+rb) return false; }
  return true; }
function lblFit(svg, viewOnly){
  var sr=svg.getBoundingClientRect(); if(!sr.width) return;
  var t0=performance.now(), phone=svg!==svgD, z=phone?(MM.z||1):Z, zf=phone?(typeof pmZmin==='function'?pmZmin():(MM.z||1)*.4):zmin();
  var k=sr.width/VW, items=lblItems(svg), key=z.toFixed(5)+svg.getAttribute('class');
  if(!viewOnly || svg._dcKey!==key){
    svg._dcKey=key;
    var P4=4, CELL=128, grid={}, obs=[], nodes=[];
    function cells(b, f){ for(var i=Math.floor(b.l/CELL);i<=Math.floor(b.r/CELL);i++) for(var j=Math.floor(b.t/CELL);j<=Math.floor(b.b/CELL);j++) f(i+','+j); }
    function put(b){ cells(b, function(c){ (grid[c]=grid[c]||[]).push(b); }); }
    var hitBy=null;
    function hitKept(b){ var hit=false; cells(b, function(c){ if(!hit) (grid[c]||[]).some(function(o){ return (hit=obbHit(b, o)) && (hitBy=o); }); }); return hit; }
    [].forEach.call(svg.querySelectorAll('.pl-lmb .lm-card,.pl-chip,.pl-stt,.tr-lbl,.pl-portal'), function(e){ var r=e.getBoundingClientRect(); if(r.width>0 && r.height>0){ var b=rbox(r, sr); b.own=e.closest('.pl-lmb'); b.el=e; b.portal=e.classList.contains('pl-portal'); obs.push(b); } });
    if(!phone) [].forEach.call(document.querySelectorAll('#world .node:not(.pal-floor)'), function(e){ var r=e.getBoundingClientRect(); if(r.width>0 && r.height>0) { var nb=rbox(r, sr); nb.el=e; nodes.push(nb);
      /* a landmark's name also keeps off what hangs over the node's box: its number card above it and its tall building (the 3D art) */
      var u=[r.left, r.top, r.right, r.bottom]; [].forEach.call(e.querySelectorAll(':scope > .nb3d, :scope > .node-card'), function(c){ var q=c.getBoundingClientRect(); if(q.width>0 && q.height>0){ u[0]=Math.min(u[0], q.left); u[1]=Math.min(u[1], q.top); u[2]=Math.max(u[2], q.right); u[3]=Math.max(u[3], q.bottom); } });
      nb.ext=rbox({left:u[0], top:u[1], right:u[2], bottom:u[3], width:u[2]-u[0], height:u[3]-u[1]}, sr); } });
    /* a landmark name that was showing goes first among its equals: when two compete for a spot, the one already there stays (no swapping while zooming) */
    items.sort(function(a, b){ return (b.pr+(b.k==='lm-name' && b.keep?45:0))-(a.pr+(a.k==='lm-name' && a.keep?45:0)); });
    items.forEach(function(it){
      var t=it.t, ok=lblLod(it, svg, z, zf), g=t._g, up=t._up||0; it.box=null;
      var alt=null, altY=0, held=it.keep, spots=null, card=null, tf=null;
      if(ok && it.k==='lm-name'){ if(/\bin\b/.test(t.getAttribute('class')||'')){ it.keep=true; return; }
        /* a landmark's name hangs under its card; where that is taken it slides to the nearest free place (palace_labels.py) */
        var ts=t.firstChild, lm=t.parentNode._lm, fn0=lblFS(it, z, phone)/z;
        if(it.y0==null || it.yz!==z){ it.y0=+t.getAttribute('y')||0; it.x0=ts?(+ts.getAttribute('x')||0):0; it.yz=z; } else { t.setAttribute('y', it.y0); if(ts){ t.setAttribute('x', it.x0); ts.setAttribute('x', it.x0); } }
        g=ts?[it.x0, it.y0, 0]:null; up=.35; tf=t.parentNode.getAttribute('transform');
        if(g && lm){ altY=lm.y-fn0*.42; alt=[g[0], altY]; card={x:lm.x, y:lm.y, w:lm.w, h:lm.h}; } }
      if(ok && !g) ok=false;
      if(ok){ var fs=lblFS(it, z, phone);
        if(!it.qm && it.vis){ var w=0; try{ w=t.getComputedTextLength(); }catch(e){} if(w>0){ it.q=w*z/fs+it.n*(LBL_LS[it.k]||0); it.qm=1; } }   /* WebKit's text length leaves the letter-spacing out */
        if(!it.qm) it.q=it.n*((LBL_UP[it.k]?.68:.56)+(LBL_LS[it.k]||0));
        var pad=(it.k==='lm-name' && held)?1:P4;   /* a name that was showing keeps its place with a thinner margin: no blinking at a zoom step's edge */
        function boxAt(q){ var a=q[2]||0; return obb((q[0]+MX)*k+Math.sin(a)*up*fs, (q[1]+MY)*k-Math.cos(a)*up*fs, a, it.q*fs/2+pad, fs*.6+pad); }
        function free(b, relax){ it.why='';
          if(hitKept(b)){ it.why='name:'+(hitBy.it?hitBy.it.t.textContent:''); return false; }
          var ho=null; if(obs.some(function(o){ return (it.pr<800 || (it.k==='lm-name' && ((o.own && !(relax && o.el.classList.contains('lm-card')) && o.own.getAttribute('data-name')!==t.parentNode.getAttribute('data-name')) || o.portal))) && obbHit(b, o) && (ho=o); })){ it.why='card:'+(ho.el.getAttribute('class')||'')+':'+(ho.own?ho.own.getAttribute('data-name'):''); return false; }   /* a landmark's name never under another's card (unless nothing else is free) */
          var hn=null; if((it.k==='pl-area' || it.k==='lm-name') && nodes.some(function(o){ return obbHit(b, (it.k==='lm-name' && o.ext) || o) && (hn=o); })){ it.why='node:'+(hn.el?hn.el.getAttribute('data-id')||hn.el.id:''); return false; }
          return true; }
        var b=null;
        if(card){ spots=lmSpots(card, [g[0], g[1]], alt, fs, it.q*fs, z, it.spot); ok=false;
          for(var tier=0;tier<2 && !ok;tier++) for(var si=0;si<spots.length;si++){ var sp=spots[si], q=lmToBoard([sp.x, sp.y], tf);
            if(tf && !/rotate/.test(tf)) q[2]=0; b=boxAt(q); if(free(b, tier)){ ok=true; it.spot=sp.id; it.tier=tier;
              t.setAttribute('y', sp.y); t.setAttribute('x', sp.x); if(t.firstChild) t.firstChild.setAttribute('x', sp.x);
              var ld=lmLead(card, sp.x, sp.y, fs, it.q*fs, z), ln=t._lead;
              if(ld){ if(!ln){ ln=t._lead=document.createElementNS('http://www.w3.org/2000/svg','line'); ln.setAttribute('class','lm-lead'); t.parentNode.insertBefore(ln, t); }
                ln.setAttribute('x1', ld[0]); ln.setAttribute('y1', ld[1]); ln.setAttribute('x2', ld[2]); ln.setAttribute('y2', ld[3]); ln._on=1; } else if(ln) ln._on=0;
              break; } }
          if(!ok) it.spot=null; }
        else { b=boxAt(g); if(!it.fixed && !free(b)){ ok=false; if(alt){ var b2=boxAt(alt); if(free(b2)){ ok=true; b=b2; t.setAttribute('y', altY); } } } }
        if(ok){ it.box=b; b.it=it; put(b); } }
      it.keep=ok; });
  }
  /* only what is within reach of the window is laid out */
  var cv=document.getElementById('canvas'), v=null;
  if(!phone && cv){ var cr=cv.getBoundingClientRect(), m=.75*Math.max(cr.width, cr.height); v=[cr.left-sr.left-m, cr.top-sr.top-m, cr.right-sr.left+m, cr.bottom-sr.top+m]; }
  items.forEach(function(it){ var b=it.box, show=it.keep && (!v || it.fixed || !b || (b.r>=v[0] && b.l<=v[2] && b.b>=v[1] && b.t<=v[3]));
    var ln=it.t._lead; if(ln) lmFade(ln, !!(show && ln._on));
    if(show!==it.vis){ if(it.k==='lm-name') lmFade(it.t, show); else it.t.style.display=show?'':'none'; it.vis=show; } });
  (window._palT=window._palT||{}).lbl=Math.round(performance.now()-t0);
}
/* chips keep a constant size on screen: re-measured when the zoom settles */
function sizeChips(svg){ var z=svg===svgD?Z:(MM.z||1);
  if(window._palLm) window._palLm.relayout(svg, z);
  svg.querySelectorAll('.pl-chip').forEach(function(g){ var t=g._t, bx=g._bx; if(!t) return; var w=0; try{ w=t.getComputedTextLength(); }catch(e){}
    if(!w) w=String(t.textContent).length*6.4/z; var h=20/z, pad=9/z;
    bx.setAttribute('x', -w/2-pad); bx.setAttribute('y', -h/2); bx.setAttribute('width', w+2*pad); bx.setAttribute('height', h); bx.setAttribute('rx', h/2); });
  areaSoon(svg); }
function districtCentre(d){
  var xs=[], ys=[]; ((P.units||[])[d.u]||[]).forEach(function(id){ var L=lot(P.at[id]); if(L){ xs.push(L[0]); ys.push(L[1]); } });
  if(!xs.length) return [(d.box[0]+d.box[2])/2, (d.box[1]+d.box[3])/2];
  xs.sort(function(a,b){ return a-b; }); ys.sort(function(a,b){ return a-b; });
  return [xs[xs.length>>1], ys[0]-70];
}
/* On the board the buildings ARE the cards (placeAll sizes each to its lot). The
   phone's map page has no cards, so there each building is drawn as one: a glass
   card on its lot with its number, edged in its section's colour. */
function drawBuildings(svg){
  var g=svg._b; if(!g) return; g.innerHTML='';
  if(svg===svgD) return;
  (P.units||[]).forEach(function(ids){ ids.forEach(function(id, k){
    var L=lot(P.at[id]); if(!L) return;
    var c=ucol(id), fl=Math.min(5,(P.fl[id]||[]).length);
    var H=nbHeight(id), b=el('g',{'class':'pl-bld'+(k===0?' hub':''), 'data-id':id, style:'--pc:'+c},g), body=el('g',{'class':'nb-body'},b);
    var bb=nbDraw(body, L, H, L[0], L[1], id); b._o=[L[0], L[1]+bb[4]]; b._hh=H+L[3]; b._hc=L[3]/2; b._bx=NB_SK*L[3]/2; b._ctr=[L[0], L[1]];
    /* its number: a tag over the roof, the same size on the screen at every zoom */
    var tg=pin(b, 'pl-nbtag', L[0]+NB_SK*L[3]/2, L[1]-H-L[3]/2, {}); b._tag=tg.parentNode; var nl=String(num(id)).length||3, tw_=Math.max(24, nl*7.4+12);
    el('rect',{'class':'b-tag', x:-tw_/2, y:-24, width:tw_, height:18, rx:9, stroke:c},tg);
    var t=el('text',{'class':'b-num', x:0, y:-15, 'text-anchor':'middle', dy:'.35em', 'font-size':11},tg); t.textContent=num(id);
  }); });
}

/* ── the board: the city under the cards, at the current zoom ── */
var svgD=null;
/* the canvas's size, read once while placeAll lays the board out (CVS): each read of it after a write forced the page to lay
   out the whole city again (four times in one zoom's last frame) */
var CVS=null;
function cvSize(cv){ return CVS||[cv.clientWidth, cv.clientHeight]; }
function fitZ(){ var cv=document.getElementById('canvas'); if(!cv) return .3; var c=cvSize(cv); return Math.max(.01, Math.min(c[0]/VW, c[1]/VH)); }
/* the zoom a building's number is first 10px tall: where the board opens (it zooms out past it, to the whole city) */
var ZREAD=(function(){ var L=null; for(var i=0;i<P.b.length && !L;i++) if(P.b[i] && P.b[i][0]) L=P.b[i][0]; if(!L) return .1;
  return Math.max(10/(L[3]*.55), 10*(4*.62+.6)/L[2]); })();
/* one screen px in map units, a touch more on screen as the map comes close (lines and rings keep their weight, not their scale) */
function tw(z){ return (Math.max(.88, Math.min(1.4, Math.pow(z,.3)))/z*Math.max(.34, Math.min(1, z/.24))).toFixed(4); }   /* far out the lines thin too, so a whole city of blocks stays a grid and not a blur */
function zmin(){ return fitZ()*.97; }       /* the farthest the board zooms out is the whole city in the window (a thin margin of glass round it) */
function setClasses(){ de.classList.toggle('nb-far', Z<.3); de.classList.toggle('pz-far', Z<.42); de.classList.toggle('pz-mid', Z<.8);
  if(svgD){ svgD.classList.toggle('far', Z<.42); svgD.classList.toggle('mid', Z<.8); } ctlState(); }
/* the zoom buttons say where the board is: no farther at the whole city, no closer at the nearest */
function ctlState(){ var c=document.getElementById('pal-ctl'); if(!c || Z==null) return; var lo=Z<=zmin()*1.004, hi=Z>=2.4*.996;
  var o=c.querySelector('[data-z=out]'), i=c.querySelector('[data-z=in]'), f=c.querySelector('[data-z=fit]');
  if(o) o.classList.toggle('off', lo); if(i) i.classList.toggle('off', hi); if(f) f.classList.toggle('on', lo); }
/* where the city's top edge sits in the canvas's scroll range: 0, or the gap that centres a short city */
function gy(){ var cv=document.getElementById('canvas'); return cv?Math.max(0,Math.round((cvSize(cv)[1]-VH*Z)/2)):0; }
/* While the board is being zoomed (a glide, a pinch, the wheel) it is not laid out again on every frame: laying out and
   repainting the whole city took ~200 ms a frame, so a zoom was three jumps. The board (#world: the city and its cards) is
   only SCALED and shifted by a transform while the zoom runs, and laid out for real once when it settles (placeAll). */
var PV=null, pvTimer=null;
/* where the board's left edge / top edge sit (the margins placeBoard gives a city smaller than the window) at zoom z */
function gapAt(z, cw){ return Math.max(0,(cw-VW*z)/2); }
function gyAt(z, ch){ return Math.max(0,Math.round((ch-VH*z)/2)); }
function pvSet(z, sxT, syT){
  var cv=document.getElementById('canvas'), world=document.getElementById('world'); if(!cv || !world) return;
  var cw=cvSize(cv)[0], ch=cvSize(cv)[1];
  if(!PV){ PV={zc:Z, sx:cv.scrollLeft, sy:cv.scrollTop, gx:gapAt(Z,cw), gy:gyAt(Z,ch)}; world.style.transformOrigin='0 '+WORLD_PAD_TOP+'px'; }
  /* the scroll the settled board can take: the page stops scrolling at the city's edge, so the preview stops there too
     (else it shows bare glass past the edge and then jumps back when it is laid out for real) */
  var gx=gapAt(z,cw), g=gyAt(z,ch);
  sxT=Math.max(0, Math.min(sxT, Math.max(0, Math.round(VW*z)+Math.round(gx)*2-cw)));
  syT=Math.max(0, Math.min(syT, Math.max(0, g+Math.round(VH*z)-ch)));
  PV.tx=sxT; PV.ty=syT; Z=z;
  /* scaled about the city's top-left corner (the pad above it stays put), shifted by what the margins and the scroll will do */
  world.style.transform='translate('+(PV.sx-sxT+Math.round(gx)-Math.round(PV.gx))+'px,'+(PV.sy-syT+g-PV.gy)+'px) scale('+(z/PV.zc)+')';
  if(window._altoPalaceGeo) window._altoPalaceGeo.Z=Z;
  clearTimeout(pvTimer); pvTimer=setTimeout(function(){ if(PV) placeAll(); }, 160);
}
function placeAll(){
  var cvh=document.getElementById('canvas'); if(cvh && !cvh.clientWidth && de.classList.contains('detail-open')) return;   /* hidden under a detail page: laid out when it closes */
  if(PV){ var p=PV; PV=null; clearTimeout(pvTimer); var w=document.getElementById('world');
    if(w) w.style.transform='';
    placeAllReal(); var cv=document.getElementById('canvas'); if(cv){ cv.scrollLeft=p.tx; cv.scrollTop=p.ty; } return; }
  placeAllReal();
}
function placeAllReal(){
  var world=document.getElementById('world'); if(!world) return; var tP0=performance.now();
  var cv=document.getElementById('canvas'); CVS=cv?[cv.clientWidth, cv.clientHeight]:null;
  try{ placeBoard(world, cv); } finally { CVS=null; }
  (window._palT=window._palT||{}).place=Math.round(performance.now()-tP0);
}

/* the toy fleet (palace_fleet_*.py, a hosted script: boats and bases, and what the armed ones do): it draws the boats and bases, and is handed the page's own parts */
var FHO=null;
function fleetHost(){ return FHO||(FHO={el:el, pin:pin, nbDraw:nbDraw, svgPt:svgPt, de:de, palaceOn:palaceOn, mob:mob, graph:graph, nearest:nearest, route:route, dk:dk,
  get svg(){ return svgD; }, get Z(){ return Z; }, get sk(){ return NB_SK; }}); }
/* ── node buildings: a glass block on each lot, as tall as what is inside it ── */
var NB_SK=.25;     /* the landmarks' 3/4 view: a building's depth leans right by this much, so its right wall shows; walls stand straight up */
function nbWeight(id){ var t=TT[id]||{}, w=(t.envs||[]).length+(t.themes||[]).length; (P.fl[id]||[]).forEach(function(f){ var q=TT[f]||{}; w+=(q.envs||[]).length+(q.themes||[]).length; }); return w; }
function nbHeight(id){ return Math.round(Math.min(100, 28+9*nbWeight(id))); }
/* the block's shapes into `parent`, its lot centre at (ox,oy); returns its box [x0,y0,x1,y1] relative to the centre */
function nbDraw(parent, L, H, ox, oy, uid){
  var w=L[2]/2, h=L[3]/2, a=(+L[4]||0)*Math.PI/180, ca=Math.cos(a), sa=Math.sin(a), o=[0, -H];
  var C=[[-w,-h],[w,-h],[w,h],[-w,h]].map(function(q){ return [q[0]*ca-q[1]*sa, q[0]*sa+q[1]*ca]; });
  var yb=Math.max.apply(null, C.map(function(q){ return q[1]; }));
  var rx0=Math.min.apply(null, C.map(function(q){ return q[0]; })), rx1=Math.max.apply(null, C.map(function(q){ return q[0]; }));
  C=C.map(function(q){ return [q[0]+NB_SK*(yb-q[1]), q[1]]; });                 /* the back leans right: the footprint is a parallelogram ... */
  var sx0=Math.min.apply(null, C.map(function(q){ return q[0]; })), sx1=Math.max.apply(null, C.map(function(q){ return q[0]; })), fw=(rx1-rx0)/((sx1-sx0)||1);
  C=C.map(function(q){ return [(q[0]-(sx0+sx1)/2)*fw+(rx0+rx1)/2, q[1]]; });    /* ... squeezed back inside its lot, so it never runs over into the street beside it (a curved or angled block's lot is as wide as it is) */
  var x0=1e9, y0=1e9, x1=-1e9, y1=-1e9;
  C.forEach(function(q){ [q, [q[0]+o[0], q[1]+o[1]]].forEach(function(r){ x0=Math.min(x0,r[0]); x1=Math.max(x1,r[0]); y0=Math.min(y0,r[1]); y1=Math.max(y1,r[1]); }); });
  function P4(pts){ return pts.map(function(q){ return (q[0]+ox).toFixed(1)+','+(q[1]+oy).toFixed(1); }).join(' '); }
  function ln(A,B,cls){ return el('line',{'class':cls, x1:(A[0]+ox).toFixed(1), y1:(A[1]+oy).toFixed(1), x2:(B[0]+ox).toFixed(1), y2:(B[1]+oy).toFixed(1)},parent); }
  var gid='nbg'+String(uid||'').replace(/[^a-z0-9]/gi,'_'), dfs=el('defs',{},parent);
  function grad(k, x2, y2){ var g=el('linearGradient',{id:gid+k, x1:0, y1:0, x2:x2, y2:y2},dfs); el('stop',{offset:0, 'class':'nb-g'+k+'0'},g); el('stop',{offset:1, 'class':'nb-g'+k+'1'},g); }
  grad('f',0,1); grad('s',1,0); grad('r',1,1);                          /* glass: lighter at the top of a wall, darker down it; the right wall darker; the roof palest */
  el('polygon',{'class':'nb-sh', points:P4(C.map(function(q){ return [q[0]+5, q[1]+6]; }))},parent);                    /* its shadow on the ground */
  var st=Math.max(2, Math.round(H/9)), faces=[];
  for(var i=0;i<4;i++){ var A=C[i], B=C[(i+1)%4], nx=B[1]-A[1], ny=-(B[0]-A[0]); if(nx*o[0]+ny*o[1]<0) faces.push({A:A, B:B}); }
  faces.sort(function(p,q){ return (p.A[1]+p.B[1])-(q.A[1]+q.B[1]); });        /* the wall further back first */
  faces.forEach(function(f){ var A=f.A, B=f.B, up=[A[0]+o[0],A[1]+o[1]], ub=[B[0]+o[0],B[1]+o[1]];
    var front=Math.abs(B[0]-A[0])>=Math.abs(B[1]-A[1]);
    el('polygon',{'class':front?'nb-f':'nb-s', style:'fill:url(#'+gid+(front?'f':'s')+')', points:P4([A,B,ub,up])},parent);
    if(front){ var d1=[A[0]+(B[0]-A[0])*.12, A[1]+(B[1]-A[1])*.12], d2=[A[0]+(B[0]-A[0])*.34, A[1]+(B[1]-A[1])*.34];            /* a soft diagonal sheen */
      el('polygon',{'class':'nb-sheen', points:P4([d1, d2, [d2[0]+o[0]*.8,d2[1]+o[1]*.8], [d1[0]+o[0]*.8,d1[1]+o[1]*.8]])},parent); }
    for(var k=1;k<st;k++){ var t=k/st; ln([A[0]+o[0]*t, A[1]+o[1]*t], [B[0]+o[0]*t, B[1]+o[1]*t], 'nb-l'); }
    var nm=Math.max(1, Math.round(Math.hypot(B[0]-A[0], B[1]-A[1])/22));                                           /* window mullions */
    for(var m=1;m<nm;m++){ var u=m/nm, bx=A[0]+(B[0]-A[0])*u, by=A[1]+(B[1]-A[1])*u; ln([bx,by], [bx+o[0],by+o[1]], 'nb-l'); } });
  el('polygon',{'class':'nb-r', style:'fill:url(#'+gid+'r)', points:P4(C.map(function(q){ return [q[0]+o[0], q[1]+o[1]]; }))},parent);
  var res=[x0,y0,x1,y1,yb]; res.C=C; return res;                      /* (the footprint is kept: the rebuild after a hit works from it) */
}
/* on the desktop board: an <svg> inside the building's card wrapper, drawn once and scaled by CSS (--z) */
function nbBuild(e, id, L, H){
  var old=e.querySelector(':scope > .nb3d'); if(old) old.remove();
  var s=el('svg',{'class':'nb3d', 'aria-hidden':'true', preserveAspectRatio:'none'}), b=nbDraw(s, L, H, 0, 0, id);
  var x0=b[0]-3, y0=b[1]-3, x1=b[2]+8, y1=b[3]+9;
  s.setAttribute('viewBox', x0.toFixed(1)+' '+y0.toFixed(1)+' '+(x1-x0).toFixed(1)+' '+(y1-y0).toFixed(1));
  s.style.setProperty('--ox', ((0-x0)/(x1-x0)*100).toFixed(2)+'%'); s.style.setProperty('--oy', ((b[4]-y0)/(y1-y0)*100).toFixed(2)+'%');
  s.style.setProperty('--nbx', x0.toFixed(1)); s.style.setProperty('--nby', y0.toFixed(1)); s.style.setProperty('--nbw', (x1-x0).toFixed(1)); s.style.setProperty('--nbh', (y1-y0).toFixed(1));
  s._nb={C:b.C, H:H, id:id}; e.insertBefore(s, e.firstChild); return b;
}

/* ── seeing what a building hides: a node building that stands in front of another and covers a good part of it is drawn as glass, and
   only that one (always the same ones at a given layout: nothing flickers); a filter dims the rest (.pal-dim). nbOccl is in map units. ── */
function nbOcclude(){
  var els=[].slice.call(document.querySelectorAll('#world .node')).filter(function(e){ return e._nbS; }), hit={};
  els.forEach(function(a){ els.forEach(function(b){ if(a===b || a._nbS[4]<=b._nbS[4]) return;          /* a stands in front of b (nearer: lower on the map) */
    var A=a._nbS, B=b._nbS, ix=Math.min(A[2],B[2])-Math.max(A[0],B[0]), iy=Math.min(A[3],B[3])-Math.max(A[1],B[1]); if(ix<=0 || iy<=0) return;
    if(A[5]>=B[5]*1.0 && ix*iy > .3*(B[2]-B[0])*(B[3]-B[1])) hit[a.id]=1; }); });
  /* a big landmark's name that a node building would stand over: that building turns to glass, so the name reads (screen boxes, at rest) */
  var names=[].slice.call(document.querySelectorAll('#palace-svg .pl-lmn')).map(function(n){ var cs=getComputedStyle(n); if(cs.display==='none' || cs.visibility==='hidden' || +cs.opacity<.1) return null; var r=n.getBoundingClientRect(); return r.width>2&&r.height>2?r:null; }).filter(Boolean);
  els.forEach(function(e){ var v=e.querySelector(':scope > .nb3d'), over=false;
    if(v && names.length && !e.classList.contains('focused')){ var r=v.getBoundingClientRect();
      for(var i=0;i<names.length && !over;i++){ var q=names[i]; over = r.left<q.right+2 && r.right>q.left-2 && r.top<q.bottom+2 && r.bottom>q.top-2; } }
    e.classList.toggle('nb-front', !!hit[e.id] || over); });
}
/* ── the tags at a distance: where tags would run into one another each is moved aside, a thin pointer joining it to its roof ── */
var nbSpT=0;
function nbSpreadSoon(){ clearTimeout(nbSpT); nbSpT=setTimeout(function(){ nbSpread(); nbOcclude(); }, 40); }
function nbSpread(){
  if(mob() || !svgD) return;
  if(Z<.3){ [].forEach.call(document.querySelectorAll('#world .node .nb-ld'), function(l){ l.remove(); }); [].forEach.call(document.querySelectorAll('#world .node'), function(e){ e.style.setProperty('--tdx','0px'); e.style.setProperty('--tdy','0px'); }); return; }
  var els=[].slice.call(document.querySelectorAll('#world .node')).filter(function(e){ return e._nbA && !e.classList.contains('pal-floor') && !e.classList.contains('focused'); });
  var it=els.map(function(e){ var A=e._nbA, len=String(e._nbN||'').length||3, w=Math.max(28, len*7.6+18), h=24;
    return {e:e, ax:e._nbx+A[0]*Z, ay:e._nby-(A[1]-A[2])*Z-12, rx:e._nbx+A[0]*Z, ry:e._nby-(A[1]-A[2])*Z, w:w, h:h, dx:0, dy:0}; });
  it.sort(function(p,q){ return p.ay-q.ay || p.ax-q.ax; });
  var placed=[], dirs=[-90,-50,-130,0,180,50,130], rings=[0,22,40];
  function clash(x,y,w,h){ for(var i=0;i<placed.length;i++){ var r=placed[i]; if(x-w/2<r[0]+r[2]/2+3 && x+w/2>r[0]-r[2]/2-3 && y-h/2<r[1]+r[3]/2+2 && y+h/2>r[1]-r[3]/2-2) return true; } return false; }
  it.forEach(function(t){
    var done=false;
    for(var ri=0; ri<rings.length && !done; ri++){ var r=rings[ri];
      for(var di=0; di<(r?dirs.length:1) && !done; di++){ var a=dirs[di]*Math.PI/180, dx=r?Math.cos(a)*r*1.5:0, dy=r?Math.sin(a)*r:0;
        if(!clash(t.ax+dx, t.ay+dy, t.w, t.h)){ t.dx=dx; t.dy=dy; done=true; } } }
    placed.push([t.ax+t.dx, t.ay+t.dy, t.w, t.h]); });
  it.forEach(function(t){ var e=t.e, moved=Math.hypot(t.dx,t.dy)>12, ld=e.querySelector(':scope > .nb-ld');
    var k=moved?Math.round(t.dx)+','+Math.round(t.dy):'';
    e.style.setProperty('--tdx', moved?t.dx.toFixed(1)+'px':'0px'); e.style.setProperty('--tdy', moved?t.dy.toFixed(1)+'px':'0px');
    if(!moved){ if(ld) ld.remove(); e._nbLk=''; return; }
    if(!ld){ ld=el('svg',{'class':'nb-ld','aria-hidden':'true'}); el('line',{},ld); el('circle',{r:3},ld); e.insertBefore(ld, e.firstChild.nextSibling||null); }
    var x1=t.rx-e._nbx, y1=t.ry-e._nby, x2=t.ax+t.dx-e._nbx, y2=t.ay+t.dy-e._nby, l=ld.firstChild, c=ld.lastChild;
    l.setAttribute('x1',x1.toFixed(1)); l.setAttribute('y1',y1.toFixed(1)); l.setAttribute('x2',x2.toFixed(1)); l.setAttribute('y2',y2.toFixed(1)); c.setAttribute('cx',x1.toFixed(1)); c.setAttribute('cy',y1.toFixed(1)); });
}
function placeBoard(world, cv){
  world.style.setProperty('--z', Z); world.style.setProperty('width', Math.round(VW*Z)+'px', 'important'); world.style.minHeight=Math.round(VH*Z+WORLD_PAD_TOP)+'px';
  /* a city smaller than the window sits in the middle of it */
  var gap=cv?Math.max(0,(CVS[0]-VW*Z)/2):0;
  world.style.setProperty('margin-left', Math.round(gap)+'px', 'important');
  /* the board's top pad (the engine's WORLD_PAD_TOP) is pulled up out of the scroll range: the
     city's own top edge is where the page stops scrolling, so panning up never shows bare
     background between the bars and the map. A city shorter than the window is centred. */
  world.style.setProperty('margin-top', Math.round(gy()-WORLD_PAD_TOP)+'px', 'important');
  if(svgD){ svgD.setAttribute('width', Math.round(VW*Z)); svgD.setAttribute('height', Math.round(VH*Z+WORLD_PAD_TOP)-WORLD_PAD_TOP); svgD.style.setProperty('--pz', Z); svgD.style.setProperty('--tw', tw(Z)); svgD.style.top=WORLD_PAD_TOP+'px'; }
  setClasses();
  var nzRank={}; (typeof NODES!=='undefined'?NODES:[]).map(function(n){ var q=isB(n.id)?lot(P.at[n.id]):null; return q?[n.id, q[1]+q[3]/2]:null; }).filter(Boolean)
    .sort(function(p,q){ return p[1]-q[1]; }).forEach(function(p,i){ nzRank[p[0]]=i; });       /* back to front: a building stands in front of the ones behind it */
  (typeof NODES!=='undefined'?NODES:[]).forEach(function(n){
    var e=document.getElementById('node-'+n.id); if(!e) return;
    var L=isB(n.id)?lot(P.at[n.id]):null;
    if(!L){ e.classList.add('pal-floor'); return; }
    e.classList.remove('pal-floor');
    var x=(L[0]+MX)*Z, y=(L[1]+MY)*Z; n.displayX=x; n.y=y;
    e.style.left=x+'px'; e.style.top=(y+WORLD_PAD_TOP)+'px';
    var pw=Math.max(10, L[2]*Z), ph=Math.max(8, L[3]*Z);
    e.style.setProperty('--pw', pw.toFixed(1)+'px'); e.style.setProperty('--ph', ph.toFixed(1)+'px');
    /* centred now, not a frame later when the engine's resize watcher sees the new size (the city jittered as a zoom landed) */
    if(!e.classList.contains('focused') && e._hov==null){ e.style.setProperty('--mx', (-Math.round(+pw.toFixed(1))/2)+'px'); e.style.setProperty('--my', (-Math.round(+ph.toFixed(1))/2)+'px'); }
    e.style.setProperty('--pr', L[4]+'deg'); e.style.setProperty('--pc', ucol(n.id));
    var H=nbHeight(n.id), key=[L[0],L[1],L[2],L[3],L[4],H].join('|');
    if(e._nbk!==key || !e.querySelector(':scope > .nb3d')){ e._nbk=key; e._nbH=H; var bx_=nbBuild(e, n.id, L, H); e._nbS=[L[0]+bx_[0], L[1]+bx_[1], L[0]+bx_[2], L[1]+bx_[3], L[1]+L[3]/2, H]; }
    e.style.setProperty('--bx', (NB_SK*L[3]/2).toFixed(1)); e.style.setProperty('--hh', (H+L[3]).toFixed(1)); e.style.setProperty('--hc', (L[3]/2).toFixed(1)); e._nbx=x; e._nby=y+WORLD_PAD_TOP; e._nbN=num(n.id); e._nbA=[NB_SK*L[3]/2, H+L[3], L[3]/2]; e.style.setProperty('--bh', H); e.style.setProperty('--nz', 3+(nzRank[n.id]||0));
    var cd=e.querySelector('.node-card'); if(cd && !mob()){ cd.tabIndex=0; cd.setAttribute('role','button'); cd.setAttribute('aria-label', num(n.id)+' '+title(n.id)); }   /* focus shows the same in-place pill */
    /* its number always inside it: as big as the building allows, up to 18px */
    e.style.setProperty('--pf', Math.max(9, Math.min(13, 8+Z*9)).toFixed(1)+'px');                 /* the tag's number: easy to read, a touch larger as you come closer */
    var f=Math.min(5,(P.fl[n.id]||[]).length), sh=[], o=Math.max(1.5, Math.min(3.2, 3.2*Z));
    for(var i=1;i<=f;i++){ var q=(i*o).toFixed(1); sh.push(q+'px '+q+'px 0 0 rgba(255,255,255,.8)', q+'px '+q+'px 0 1px '+ucol(n.id)); }
    if(sh.length) e.style.setProperty('--pfl', sh.join(',')); else e.style.removeProperty('--pfl');
  });
  nbSpreadSoon(); trackView();
  /* last: the chips and landmark names measure the page (one layout, after every write above) */
  if(svgD) sizeChips(svgD);
}
/* Enlarging a building asks the engine to pan the board (--pan-x/--pan-y) until the card is in the
   middle of the window. Near the city's edge that pulls the edge inwards and shows the bare page
   behind it, so the pan the board actually takes (--ppan-x/--ppan-y) is held to what keeps the
   city over the whole window — except as far as the enlarged card itself needs, so it is never
   cut off by the bars: it then sits nearer the edge than the middle, with the city under it. */
var panLast='', focW=0, focH=0;
function holdPan(){
  var w=document.getElementById('world'), cv=document.getElementById('canvas'); if(!w||!cv||!svgD) return;
  var px=parseFloat(w.style.getPropertyValue('--pan-x'))||0, py=parseFloat(w.style.getPropertyValue('--pan-y'))||0;
  var f=w.querySelector('.node.focused .node-card'), k=(cv.getBoundingClientRect().height/cv.clientHeight)||1;
  if(f){ var r=f.getBoundingClientRect(); focW=r.width/k; focH=r.height/k; } else if(!px && !py){ focW=focH=0; }
  function hold(p, near, view, size, card){
    var hi=Math.max(0,-near), lo=Math.min(0,view-size-near), c=Math.max(lo, Math.min(hi, p)), room=Math.max(0,(view-card)/2-24);
    return Math.abs(p-c)>room ? p-(p>c?room:-room) : c; }
  var ox=w.offsetLeft-cv.scrollLeft, oy=w.offsetTop+WORLD_PAD_TOP-cv.scrollTop;     /* where the city's corner is in the window at rest */
  var cx=hold(px, ox, cv.clientWidth, VW*Z, focW), cy=hold(py, oy, cv.clientHeight, VH*Z, focH);
  var key=cx+','+cy; if(key===panLast) return; panLast=key;
  if(cx||cy){ w.style.setProperty('--ppan-x', cx+'px'); w.style.setProperty('--ppan-y', cy+'px'); }
  else { w.style.removeProperty('--ppan-x'); w.style.removeProperty('--ppan-y'); }
}
/* the middle of the buildings' own neighbourhoods, which a city grown past them leaves off-centre */
function centreCity(cv){
  var D=P.d||[], bx0=1e9, by0=1e9, bx1=-1e9, by1=-1e9; D.forEach(function(d){ var b=d.box; bx0=Math.min(bx0,b[0]); by0=Math.min(by0,b[1]); bx1=Math.max(bx1,b[2]); by1=Math.max(by1,b[3]); });
  var mx=D.length?(bx0+bx1)/2+MX:VW/2, my=D.length?(by0+by1)/2+MY:VH/2;
  cv.scrollLeft=Math.max(0,mx*Z-cv.clientWidth/2); cv.scrollTop=Math.max(0,my*Z-cv.clientHeight/2); }
window._altoPalace=function(h){
  if(mob()) return false;
  var world=document.getElementById('world'); if(!world) return false;
  if(!world._holdPan){ world._holdPan=1; new MutationObserver(holdPan).observe(world, {attributes:true, attributeFilter:['style']}); }
  if(Z==null) Z=Math.max(fitZ(), ZREAD);
  if(P._dirty){ P._dirty=0; restructure(true); if(svgD) drawBuildings(svgD); }
  if(P._lmDirty && svgD){ P._lmDirty=0; drawCity(svgD); if(MM.svg) drawCity(MM.svg); }
  if(!svgD){ svgD=el('svg',{id:'palace-svg', 'class':'pal-svg', viewBox:(-MX)+' '+(-MY)+' '+VW+' '+VH, preserveAspectRatio:'none'}); svgD._sid='d'; drawCity(svgD); }
  if(svgD.parentNode!==world) world.insertBefore(svgD, world.firstChild);
  /* a pan that stops brings in the names now within reach of the window (lblFit) */
  var cvL=document.getElementById('canvas'); if(cvL && !cvL._lblScroll){ cvL._lblScroll=1; cvL.addEventListener('scroll', function(){ if(!svgD) return; clearTimeout(cvL._lblT);
    cvL._lblT=setTimeout(function(){ if(svgD && !PV && palaceOn()){ lblFit(svgD, true); nbSpreadSoon(); } }, 120); }, {passive:true}); }
  placeAll();
  _actBands=ACT_SEQS.map(function(){ return {startY:0, endY:VH*Z}; });
  window._headerTint={slabTop:0, slabH:VH*Z, stops:[{p:0,c:PHASE_META[0].colorRaw},{p:100,c:PHASE_META[0].colorRaw}]};
  if(window.updateHeaderTint) try{ window.updateHeaderTint(); }catch(e){}
  var r=document.getElementById('river-svg'); if(r) r.innerHTML='';
  window._altoPalaceGeo={Z:Z};
  if(!opened){ opened=1; requestAnimationFrame(function(){ var cv=document.getElementById('canvas'); if(cv && !window._focusedNodeId){
    /* it opens on the buildings' own neighbourhoods, which a city grown past them leaves off-centre */
    centreCity(cv); } }); }
  ctl();
  return true;
};

/* light/dark: the lines take their contrast from the glass behind them, so the city is drawn again */
var wasDark=dk(), wasGround=groundNow()+'';
function redraw(){ if(dk()===wasDark && groundNow()+''===wasGround) return; wasDark=dk(); wasGround=groundNow()+'';
  if(svgD){ drawCity(svgD); placeAll(); } if(MM.svg){ drawCity(MM.svg); } }
new MutationObserver(redraw).observe(de, {attributes:true, attributeFilter:['class']});
window.addEventListener('alto-bg-painted', redraw);   /* another map ground: the streets are checked against it again */

/* ── zoom: the board drawn larger or smaller about a point, the cards keep their size ── */
function canvasPt(cv, cx, cy){ var r=cv.getBoundingClientRect(); return [(cx-r.left)/r.width*cv.clientWidth, (cy-r.top)/r.height*cv.clientHeight]; }
function zoomTo(z, ax, ay){
  var cv=document.getElementById('canvas'); if(!cv || !svgD) return;
  z=Math.max(zmin(), Math.min(2.4, z)); if(Math.abs(z-Z)<1e-4) return;
  if(ax==null){ ax=cv.clientWidth/2; ay=cv.clientHeight/2; }
  var sx=PV?PV.tx:cv.scrollLeft, sy=PV?PV.ty:cv.scrollTop;
  var cw=cvSize(cv)[0], ch=cvSize(cv)[1], mx=(sx+ax-gapAt(Z,cw))/Z, my=(sy+ay-gyAt(Z,ch))/Z;
  pvSet(z, mx*z+gapAt(z,cw)-ax, my*z+gyAt(z,ch)-ay);
}
var zAnim=null;
function zoomAnim(z, ax, ay, ms, done){
  cancelAnimationFrame(zAnim); var z0=Z, t0=performance.now(); ms=ms||320;
  if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) ms=1;
  (function step(t){ var k=Math.min(1,(t-t0)/ms), e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;
    zoomTo(Math.exp(Math.log(z0)+(Math.log(z)-Math.log(z0))*e), ax, ay);
    if(k<1) zAnim=requestAnimationFrame(step); else { if(PV) placeAll(); if(done) done(); } })(t0);
}
/* centre a map point at zoom z, gliding */
function flyMap(mx, my, z, done){
  var cv=document.getElementById('canvas'); if(!cv) return;
  var z0=Z, sx0=cv.scrollLeft, sy0=cv.scrollTop, t0=performance.now(), ms=520;
  if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) ms=1;
  var cx=cv.clientWidth/2, cy=cv.clientHeight/2;
  /* the map point at the centre now */
  var fx=(sx0+cx-gapAt(z0,cv.clientWidth))/z0-MX, fy=(sy0+cy-gyAt(z0,cv.clientHeight))/z0-MY;
  cancelAnimationFrame(zAnim);
  (function step(t){ var k=Math.min(1,(t-t0)/ms), e=k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
    var zz=Math.exp(Math.log(z0)+(Math.log(z)-Math.log(z0))*e), px=fx+(mx-fx)*e, py=fy+(my-fy)*e;
    var zc=Math.max(zmin(),Math.min(2.4,zz));
    pvSet(zc, (px+MX)*zc+gapAt(zc,cv.clientWidth)-cx, (py+MY)*zc+gyAt(zc,cv.clientHeight)-cy);
    if(k<1) zAnim=requestAnimationFrame(step); else { placeAll(); if(done) done(); } })(t0);
}
/* a fly that works from anywhere: a detail page open or a building enlarged is left first (the board is not under the window then) */
function leaveBoard(then){
  var wait=0;
  if(de.classList.contains('detail-open') && typeof showTimeline==='function'){ try{ showTimeline(); }catch(e){} wait=160; }
  if(window._focusedNodeId && window.exitFocus){ try{ window.exitFocus(); }catch(e){} wait=Math.max(wait, 380); }
  if(!wait) then(); else setTimeout(then, wait);
}
function flyAway(mx, my, z, done){ leaveBoard(function(){ flyMap(mx, my, z, done); }); }
function palaceOn(){ return de.classList.contains('alto-palace') && !mob() && !de.classList.contains('detail-open'); }
function focused(){ var cv=document.getElementById('canvas'); return !!(cv && cv.classList.contains('focus-mode')); }
window.addEventListener('wheel', function(e){
  if(!palaceOn() || !e.ctrlKey || focused()) return;
  var cv=document.getElementById('canvas'); if(!cv || !cv.contains(e.target)) return;
  e.preventDefault(); e.stopImmediatePropagation();
  var p=canvasPt(cv, e.clientX, e.clientY); zoomTo(Z*Math.exp(-e.deltaY*(e.deltaMode===1?.05:.0025)), p[0], p[1]);
}, {passive:false, capture:true});
var gz=null;
window.addEventListener('gesturestart', function(e){ if(!palaceOn() || focused()) return; e.preventDefault(); e.stopImmediatePropagation(); gz=Z; }, true);
window.addEventListener('gesturechange', function(e){ if(gz==null) return; e.preventDefault(); e.stopImmediatePropagation();
  var cv=document.getElementById('canvas'), p=canvasPt(cv, e.clientX, e.clientY); zoomTo(gz*e.scale, p[0], p[1]); }, true);
window.addEventListener('gestureend', function(e){ if(gz==null) return; e.preventDefault(); e.stopImmediatePropagation(); gz=null; }, true);
window.addEventListener('keydown', function(e){
  if(!palaceOn() || focused() || !(e.metaKey||e.ctrlKey)) return;
  var k=e.key; if(k!=='='&&k!=='+'&&k!=='-'&&k!=='0') return;
  e.preventDefault(); e.stopImmediatePropagation();
  if(k==='0') zoomAnim(zmin()); else zoomAnim(Z*(k==='-'?1/1.6:1.6));
}, true);

/* ── pointing: a building's name, a street's, a corner's ── */
var tipT=null, labEl=null, litEls=[], dock=null, dockU=null, lastB=null;
/* a building's chip widens in place into a pill (CSS .pal-lab); a street's / neighbourhood's name brightens (.pal-lit) */
function labelB(id){ var n=id?document.getElementById('node-'+id):null; if(labEl && labEl!==n) labEl.classList.remove('pal-lab'); labEl=n; if(n && !n.classList.contains('focused')) n.classList.add('pal-lab'); }
function lit(list){ litEls.forEach(function(x){ x.classList.remove('pal-lit'); }); litEls=list||[]; litEls.forEach(function(x){ x.classList.add('pal-lit'); }); }
function litStreet(nm){ if(!svgD||!nm) return lit(null); lit([].slice.call(svgD.querySelectorAll('.pl-st,.pl-stt')).filter(function(x){ return x.getAttribute('data-n')===nm; })); }
/* pointing at a street (or a block's side): its name in the same quiet in-place label a building gets, two names at a corner */
var stPill=0;
function streetPill(h, e){
  var svg=svgD; if(!svg || !window._palHover) return;
  var pt=svgPt(svg,e), m=svg._hp; if(!m || m.parentNode!==svg){ m=svg._hp=el('circle',{'class':'pl-hovpt', r:1, fill:'none', 'pointer-events':'none'},svg); }
  m.setAttribute('cx',pt[0]); m.setAttribute('cy',pt[1]);
  var c=cornerAt(svg, e, h._n); window._palHover(m, c&&c.length>1 ? c.join(' & ') : h._n); stPill=1; }
function streetPillOff(){ if(stPill){ stPill=0; if(window._palHover) window._palHover(null); } }
document.addEventListener('mousemove', function(e){ if(!stPill || !palaceOn()) return; var h=e.target.closest && e.target.closest('#palace-svg .pl-hit'); if(!h){ streetPillOff(); return; }
  var m=svgD&&svgD._hp, pt=svgPt(svgD,e); if(m && Math.hypot(+m.getAttribute('cx')-pt[0], +m.getAttribute('cy')-pt[1])*Z > 36) streetPill(h, e); });
function litDist(u){ lit(svgD?[].slice.call(svgD.querySelectorAll('.pl-dist')).filter(function(x){ return +x.getAttribute('data-u')===u; }):null); }
/* window._palHover(el, text): label ANY svg element of the map in place (a quiet pill just above it, never following the cursor).
   Call it from a hover / focus handler with the text; call it with no text to clear. One pill at a time; returns the pill's <g> or null. */
var hov=null;
window._palHover=function(elm, text){
  if(hov){ hov.remove(); hov=null; }
  if(!elm || !text) return null;
  var svg=elm.ownerSVGElement||(elm.tagName==='svg'?elm:null); if(!svg) return null;
  var z=(svg===svgD?Z:(MM.z||1))||1, r=elm.getBoundingClientRect(), p=svgPt(svg,{clientX:r.left+r.width/2, clientY:r.top});
  var g=el('g',{'class':'pl-hov', transform:'translate('+p[0]+' '+p[1]+')'},svg), rc=el('rect',{},g), t=el('text',{'text-anchor':'middle'},g); t.textContent=text;
  var k=1/z, b=t.getBBox(), pw=8*k, ph=4*k; t.setAttribute('y', -(b.height+8*k+ph)+(-b.y)); rc.setAttribute('rx', (b.height+2*ph)/2);
  rc.setAttribute('x', b.x-pw); rc.setAttribute('width', b.width+2*pw); rc.setAttribute('y', -(b.height+8*k+2*ph)); rc.setAttribute('height', b.height+2*ph);
  hov=g; return g; };
/* the docked card: the one box left, pinned bottom centre above the controls, until Esc / a click away / its x */
function dockEl(){ if(!dock){ dock=document.createElement('div'); dock.id='pal-dock'; dock.setAttribute('role','dialog'); document.body.appendChild(dock);
  dock.addEventListener('click', function(e){ if(e.target.closest('.pd-x')) closeDock(); }); } return dock; }
function openDock(u){ var d=dockEl(); dockU=u; d.className='on'; d.setAttribute('aria-label', 'Neighbourhood: '+((P.d||[]).filter(function(q){ return q.u===u; })[0]||{}).n);
  d.innerHTML='<button type="button" class="pd-x" aria-label="Close">×</button>'+distTip(u)+'<small>The dotted line is the walk through them in order.</small>'; if(!focused()) drawRoutes(svgD, null, u); }
function closeDock(){ if(!dock || dockU==null) return; dockU=null; dock.className=''; if(!focused() && svgD) drawRoutes(svgD, null); }
/* a transient hint in the same docked spot (a drag's "make it a floor of …") */
function hint(html){ var d=dockEl(); d.className='on hint'; d.innerHTML=html; }
function unhint(){ if(!dock || !dock.classList.contains('hint')) return; if(dockU!=null) openDock(dockU); else dock.className=''; }
function rels(id){
  var mine={}; mine[id]=1; (P.fl[id]||[]).forEach(function(f){ mine[f]=1; });
  return (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).filter(function(c){ return c && c[2]!=='spine' && (mine[c[0]]||mine[c[1]]) && bOf(c[0])!==bOf(c[1]); });
}
function bTip(id){
  var fl=P.fl[id]||[], tw_=towerOf(id), h='<b><span class="pt-num">'+esc(num(id))+'</span> '+esc(title(id))+'</b>';
  var where=(P.near||{})[id]; h+='<small>'+(where?esc(where)+' · ':'')+(tw_?tw_.top+' floors':fl.length?(fl.length+1)+' floors':'one floor')+'</small>';
  if(fl.length){ h+='<small>'+fl.slice(0,4).map(function(f,i){ return (i+1)+'. '+esc(title(f)); }).join('<br>')+(fl.length>4?'<br>…':'')+'</small>'; }
  var rl=(typeof REL_LABELS!=='undefined')?REL_LABELS:{};
  rels(id).slice(0,5).forEach(function(c){ var other=bOf(c[0])===id?c[1]:c[0], col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[c[2]])||'var(--accent)';
    h+='<span class="pt-rel"><i style="background:'+col+'"></i>'+esc(rl[c[2]]||c[2])+': '+esc(num(bOf(other)))+' '+esc(title(other))+'</span>'; });
  return h;
}
/* a landmark building's page: an Index list, an element's page, a card's page */
function pageName(pg){ var q=String(pg||'').split(':'), k=q.slice(1).join(':');
  if(q[0]==='index'){ var b=document.querySelector('[data-axis-index="'+k+'"]'); return b?b.textContent.replace(/\d+\s*$/,'').replace(/^[^A-Za-z§]+/,'').trim():k; }
  if(q[0]==='node') return title(k);
  if(q[0]==='char'){ var c=(typeof CHARS!=='undefined')?CHARS[k]:null; return c&&c.name?c.name:k; }
  return k; }
function openPage(pg){ var q=String(pg||'').split(':'), k=q.slice(1).join(':'); if(!k) return;
  if(q[0]==='index' && window.showAxisIndex) window.showAxisIndex(k); else if(q[0]==='char') window.showDetail('char',k); else if(q[0]==='node') window.showDetail('node',k); }
function lmTip(g){ return window._palLm.tip(g, esc, pageName); }
/* a neighbourhood's pop-up: its name, the unit it holds (number and label), and what stands in it */
function distTip(u){ var pm=PHASE_META[u]; if(!pm) return ''; var d=(P.d||[]).filter(function(q){ return q.u===u; })[0]||{}, ids=(P.units||[])[u]||[];
  var h='<b>'+esc(d.n||pm.label)+'</b><small class="pt-unit"><i style="background:'+esc(tubeCol(pm.colorRaw))+'"></i>Unit '+esc(pm.numeral)+' · '+esc(pm.label)+'</small>';
  h+='<small>'+ids.length+' building'+(ids.length===1?'':'s')+': '+ids.slice(0,3).map(function(id){ return esc(num(id)+' '+title(id)); }).join(' · ')+(ids.length>3?' …':'')+'</small>';
  return h; }
function svgPt(svg, e){ var r=svg.getBoundingClientRect(), vb=svg.viewBox.baseVal; return [vb.x+(e.clientX-r.left)/r.width*vb.width, vb.y+(e.clientY-r.top)/r.height*vb.height]; }
function cornerAt(svg, e, street){
  var p=svgPt(svg,e), g=graph(), zz=(svg===svgD?Z:(MM.z||1)), n=nearest(p[0],p[1],2,16/zz);
  if(n<0) return null; var nm=Object.keys(g.names[n]); if(street && nm.indexOf(street)<0) return null; return nm;
}

/* routes: from a building along the streets to each building it connects with */
var hotB=null;
function drawRoutes(svg, id, walkUnit){
  if(svg===svgD && window._palTr.holds()) return;       /* an Element chip's tour is up: it takes precedence */
  var g=svg._r; if(!g) return; g.innerHTML=''; if(svg._rh) svg._rh.innerHTML='';
  function bl(svg, id){ return svg===svgD ? document.getElementById('node-'+id) : svg.querySelector('.pl-bld[data-id="'+id+'"]'); }
  function all(svg){ return svg===svgD ? document.querySelectorAll('#world .node') : svg.querySelectorAll('.pl-bld'); }
  function idOf(e){ return e.getAttribute('data-id') || (e.id||'').replace(/^node-/,''); }
  all(svg).forEach(function(b){ b.classList.remove('pal-hot','pal-dim'); });
  if(id==null && walkUnit==null) return;
  function path(a,b){ var A=lot(P.at[a]), B=lot(P.at[b]); if(!A||!B) return null; var q=window._palTR&&window._palTR(a,b); if(q) return q;
    var r=route(entrance(a), entrance(b)), gg=graph();
    var d='M'+A[0]+' '+A[1]; (r||[]).forEach(function(n){ d+='L'+gg.X[n]+' '+gg.Y[n]; }); return d+'L'+B[0]+' '+B[1]; }
  if(walkUnit!=null){
    var ids=(P.units||[])[walkUnit]||[], col=PHASE_META[walkUnit]?PHASE_META[walkUnit].colorRaw:'var(--accent)';
    for(var i=0;i+1<ids.length;i++){ var d=path(ids[i],ids[i+1]); if(d) el('path',{'class':'pl-walk', d:d, stroke:col},g); }
    all(svg).forEach(function(b){ b.classList.toggle('pal-dim', ids.indexOf(idOf(b))<0); });
    return;
  }
  var me=bl(svg, id); if(me) me.classList.add('pal-hot');
  rels(id).forEach(function(c){ var other=bOf(bOf(c[0])===id?c[1]:c[0]), d=path(id, other); if(!d) return;
    var col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[c[2]])||'var(--accent)';
    var rt=el('g',{'class':'pl-rt'},g);
    el('path',{'class':'pl-route', d:d, stroke:col},rt); el('path',{'class':'pl-route-sh', d:d},rt);
    if(svg===svgD){ var h=el('path',{'class':'pl-route-hit', d:d},rtHits(svg)); h._rt={from:id, to:other, rel:c[2], g:rt, d:d}; }
    var ob=bl(svg, other); if(ob) ob.classList.add('pal-hot'); });
}
/* each lit route has a wide invisible path over it (above every street's own) so it can be pointed at and clicked */
function rtHits(svg){ var h=svg._rh; if(!h || h.parentNode!==svg){ h=svg._rh=el('g',{'class':'pl-route-hits'},svg); } else svg.appendChild(h); return h; }
function bAt(t){ if(!t||!t.closest) return null; var b=t.closest('.pl-bld[data-id]'); if(b) return b.getAttribute('data-id');
  var n=t.closest('#world .node[id^="node-"]'); if(n && !n.classList.contains('focused')){ var id=n.id.slice(5); return isB(id)?id:null; } return null; }
document.addEventListener('mouseover', function(e){
  if(!palaceOn() || dragging) return;
  var T=e.target, cl=function(q){ return T.closest && T.closest(q); };
  var id=bAt(T), st=cl('#palace-svg .pl-hit'), du=cl('#palace-svg .pl-dist'), da=cl('#palace-svg .pl-dtint'), rh=cl('#palace-svg .pl-route-hit');
  clearTimeout(tipT);
  routeHot(rh);
  labelB(id);
  if(rh){ lit(null); return; }                                  /* its far building (lit by routeHot) shows its pill */
  if(id){ lit(null); tipT=setTimeout(function(){ if(!focused()){ hotB=id; drawRoutes(svgD, id); } }, 110); return; }
  if(du){ litDist(+du.getAttribute('data-u')); return; }
  if(st){ litStreet(st._n); streetPill(st, e); return; }
  streetPillOff();
  if(da){ litDist(+da.getAttribute('data-u')); }                /* the neighbourhood's own ground (under streets, buildings, landmarks) */
  else lit(null);
  tipT=setTimeout(function(){ if(!focused() && hotB){ hotB=null; drawRoutes(svgD, null, dockU); } else if(!focused() && dockU==null && svgD && svgD._r && svgD._r.firstChild) drawRoutes(svgD, null); }, 120);
});
window.addEventListener('keydown', function(e){
  if(!palaceOn()) return;
  if(e.key==='Escape' && dockU!=null && !de.classList.contains('detail-open')){ e.preventDefault(); e.stopPropagation(); closeDock(); return; }
  if((e.key==='Enter'||e.key===' ') && !mob() && !e.metaKey && !e.ctrlKey && !e.altKey){ var c=e.target.closest && e.target.closest('#world .node:not(.focused) .node-card'), n=c&&c.closest('.node');
    if(c && c===e.target && n && n.id && isB(n.id.slice(5))){ e.preventDefault(); e.stopPropagation(); enlarge(n.id.slice(5)); } }
}, true);
document.addEventListener('mouseout', function(e){ if(!e.relatedTarget){ clearTimeout(tipT); labelB(null); lit(null); } });
/* a click on a building enlarges it (the map comes closer first); a double click goes inside: the second click of the pair
   (it lands on the rising card, its ghost, or the moving map) never toggles anything, it opens the building's page */
/* a building's page opened while the glide to it was still running (a double-click) must not let that glide land on the hidden board */
var flyId=null, pendEnl=null, holdView=null;
function enlarge(id){
  var L=lot(P.at[id]); if(!L) return; labelB(null); closeDock();
  if(Z<.85){ flyId=id; flyMap(L[0], L[1], 1.05, function(){ flyId=null; if(de.classList.contains('detail-open')){ pendEnl=id; return; } window.enterFocus(id); setTimeout(function(){ drawRoutes(svgD, id); }, 30); }); }
  else { window.enterFocus(id); setTimeout(function(){ drawRoutes(svgD, id); }, 30); }
}
document.addEventListener('click', function(e){
  if(!palaceOn() || de.classList.contains('alto-editing') && moved) return;
  if(dockU!=null && !e.target.closest('#pal-dock,#palace-svg .pl-dist')) closeDock();            /* a click away dismisses the docked card */
  var now=Date.now(), recent=lastB && now-lastB.t<(e.detail>=2?900:450);
  if(recent){ var fn=e.target.closest && e.target.closest('#world .node.focused[id^="node-"]');
    if(e.detail>=2 || (fn && fn.id==='node-'+lastB.id) || bAt(e.target)===lastB.id){ var did=lastB.id; lastB=null;
      e.stopPropagation(); e.preventDefault(); window.showDetail('node', did); return; } }
  var rh=e.target.closest && e.target.closest('#palace-svg .pl-route-hit');
  if(rh){ e.stopPropagation(); e.preventDefault(); followRoute(e); return; }
  var gh=e.target.closest && e.target.closest('.pal-ghost');
  if(gh){ e.stopPropagation(); e.preventDefault(); if(window.exitFocus) window.exitFocus(); return; }
  var lmc=e.target.closest && e.target.closest('#palace-svg .pl-lmb.has-page');
  if(lmc){ e.stopPropagation(); openPage(lmc.getAttribute('data-page')); return; }
  var tcl=e.target.closest && e.target.closest('#palace-svg .pl-lmb[data-tower]');         /* a tower's card: the same as its building chip */
  if(tcl && !editing()){ e.stopPropagation(); e.preventDefault(); lastB={id:tcl.getAttribute('data-tower'), t:now}; enlarge(tcl.getAttribute('data-tower')); return; }
  var du=e.target.closest && e.target.closest('#palace-svg .pl-dist');
  if(du){ e.stopPropagation(); var d=(P.d||[]).filter(function(q){ return q.u===+du.getAttribute('data-u'); })[0]; if(!mob()) openDock(+du.getAttribute('data-u')); if(d) flyToBox(d.box); return; }
  var id=bAt(e.target); if(!id) return;
  e.stopPropagation(); e.preventDefault();
  lastB={id:id, t:now}; enlarge(id);
}, true);
/* ═══ ROUTES (interaction pass): a lit route is a line you can follow ═══
   On an ordinary timeline a click on a connecting line flies to the node at its far end (blocks.py, LINE_NAV_GLUE).
   Here the routes all start at the building you are pointing at or have enlarged, so the far end is always the other
   building. Where several routes share a street, the click picks the one whose building is nearest along the line. */
var hotR=null;
function routeHot(h){ if(h===hotR) return;
  if(hotR && hotR._rt){ hotR._rt.g.classList.remove('hot'); var o=document.getElementById('node-'+hotR._rt.to); if(o) o.classList.remove('pal-dest'); }
  hotR=h||null;
  if(hotR){ hotR._rt.g.classList.add('hot'); var n=document.getElementById('node-'+hotR._rt.to); if(n) n.classList.add('pal-dest'); } }
function polyOf(d){ var v=(d.match(/-?\d*\.?\d+/g)||[]).map(parseFloat), a=[]; for(var i=0;i+1<v.length;i+=2) a.push([v[i],v[i+1]]); return a; }
/* how far along a route (from its start) the point nearest p lies, and the route's whole length */
function alongRoute(pl, p){ var tot=0, best=1e18, at=0, run=0;
  for(var i=0;i+1<pl.length;i++){ var a=pl[i], b=pl[i+1], dx=b[0]-a[0], dy=b[1]-a[1], L=Math.hypot(dx,dy)||1e-6,
      t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(L*L))), q=Math.hypot(a[0]+dx*t-p[0], a[1]+dy*t-p[1]);
    if(q<best){ best=q; at=run+t*L; } run+=L; }
  return {s:at, len:run}; }
function followRoute(e){
  var hits=document.elementsFromPoint(e.clientX, e.clientY).filter(function(x){ return x.classList && x.classList.contains('pl-route-hit') && x._rt; });
  if(!hits.length) return;
  var p=svgPt(svgD, e), best=null, bd=1e18;
  hits.forEach(function(h){ var r=h._rt; if(!r._pl) r._pl=polyOf(r.d); var a=alongRoute(r._pl, p), rest=a.len-a.s; if(rest<bd){ bd=rest; best=r; } });
  if(!best) return; routeHot(null);
  enlarge(best.to);
}
/* ═══ RISE (interaction pass): an enlarged building's card stands ABOVE its building ═══
   The enlarged card is still the node's ordinary card; it is moved up (top/left on the card, which the engine's CSS zoom
   scales along with it) so its bottom edge clears the building, and the building is drawn again under it (.pal-ghost)
   with a notch (.pal-tail) pointing down onto it. The engine centres the card and building TOGETHER because
   _altoFocusShift moves the point it centres (engine_patches.py, palace-focus-centres-card-and-building). */
var RISE_T=15, FK=1.7;
function riseEls(el, id){
  var g=el.querySelector(':scope > .pal-ghost'), t=el.querySelector(':scope > .pal-tail');
  if(!g){ g=document.createElement('div'); g.className='pal-ghost'; g.setAttribute('title','Close the card'); el.appendChild(g); }
  g.innerHTML='<span>'+esc(num(id))+'</span>';
  if(!t){ t=document.createElement('div'); t.className='pal-tail'; t.innerHTML='<i></i>'; el.appendChild(t); }
}
function riseVars(el, up){ var R=el._rise; if(!R) return;
  var top=(up?-1:1)*((R.pe+RISE_T)/FK+R.h/2);
  el.style.setProperty('--pe', R.pe.toFixed(1)+'px'); el.style.setProperty('--pt', RISE_T+'px'); el.style.setProperty('--rt', top.toFixed(1)+'px'); el.style.setProperty('--rl', (R.rl/FK).toFixed(1)+'px');
  el.classList.toggle('pal-below', !up); R.up=up; }
window._altoFocusShift=function(el){
  if(mob() || !de.classList.contains('alto-palace') || !el) return null;
  var id=el.id.slice(5); if(!isB(id)) return null;
  var R=el._rise; if(R && performance.now()-R.t<120) return R.shift;
  var card=el.querySelector('.node-card'); if(!card) return null;
  riseEls(el, id);
  /* the card as the enlarged one is — measured at the enlarged zoom with .focused on, as the engine measures its shadow */
  var had=el.classList.contains('focused'), z0=card.style.zoom;
  if(!had) el.classList.add('focused'); card.style.zoom=String(FK);
  var h0=card.offsetHeight; card.style.zoom=z0; if(!had) el.classList.remove('focused');
  var w=parseFloat(el.style.getPropertyValue('--pw'))||40, hh=parseFloat(el.style.getPropertyValue('--ph'))||26, th=(parseFloat(el.style.getPropertyValue('--pr'))||0)*Math.PI/180;
  var pe=(Math.abs(w*Math.sin(th))+Math.abs(hh*Math.cos(th)))/2+(el._nbH||0)*Z;
  var cv=document.getElementById('canvas'), ch=cv.clientHeight, par=el.offsetParent, ay=(parseFloat(el.style.top)||0)+((par&&par!==cv)?par.offsetTop:0);
  var H=h0*FK, d=(RISE_T+H)/2;
  function resid(sy){ var a=ay+sy, tt=Math.max(0,Math.min(Math.round(a-ch/2), Math.max(0,cv.scrollHeight-ch))); return Math.abs(a-(tt+ch/2)); }
  var up=resid(-d)<=resid(d)+36;
  R=el._rise={t:performance.now(), h:h0, pe:pe, rl:0, up:up, shift:[0, up?-d:d]};
  riseVars(el, up); return R.shift;
};
/* once it has landed (and on a resize): inside the window, the notch still over the building */
function riseFit(){
  var id=window._focusedNodeId, el=id&&document.getElementById('node-'+id), card=el&&el.querySelector('.node-card'), cv=document.getElementById('canvas');
  if(!el || !el._rise || !card || !cv || mob()) return;
  var R=el._rise, cr=cv.getBoundingClientRect(), r=card.getBoundingClientRect(), m=10;
  if(r.width<20) return;
  if(r.top<cr.top+m && R.up){ el.classList.add('pal-below'); riseVars(el,false); var r2=card.getBoundingClientRect();
    if(r2.bottom>cr.bottom-m && r2.bottom>r.bottom+0){ riseVars(el,true); } }
  else if(r.bottom>cr.bottom-m && !R.up){ riseVars(el,true); var r3=card.getBoundingClientRect(); if(r3.top<cr.top+m) riseVars(el,false); }
  r=card.getBoundingClientRect();
  var dx=0; if(r.left<cr.left+m) dx=cr.left+m-r.left; else if(r.right>cr.right-m) dx=cr.right-m-r.right;
  if(dx){ var z=parseFloat(getComputedStyle(de).zoom)||1, lim=r.width/2/z-26; R.rl=Math.max(-lim, Math.min(lim, R.rl+dx/z)); riseVars(el, R.up); }
}
function riseSoon(){ clearTimeout(riseSoon.t); riseSoon.t=setTimeout(riseFit, (window._altoFlyMs||420)+120); }
new MutationObserver(function(ms){ for(var i=0;i<ms.length;i++){ var n=ms[i].target; if(n.classList && n.classList.contains('focused') && n.classList.contains('node') && n._rise){ n._rise.rl=0; riseSoon(); return; } } })
  .observe(document.getElementById('world')||document.documentElement, {attributes:true, subtree:true, attributeFilter:['class']});
window.addEventListener('resize', function(){ if(window._focusedNodeId){ var el=document.getElementById('node-'+window._focusedNodeId); if(el && el._rise){ el._rise.t=0; el._rise.rl=0; riseSoon(); } } });
function flyToBox(b){ var cv=document.getElementById('canvas'); if(!cv) return;
  var z=Math.min(1.3, Math.min(cv.clientWidth/((b[2]-b[0])+260), cv.clientHeight/((b[3]-b[1])+260)));
  flyMap((b[0]+b[2])/2, (b[1]+b[3])/2, Math.max(z, zmin())); }
document.addEventListener('dblclick', function(e){
  if(!palaceOn() || focused() || bAt(e.target) || (lastB && Date.now()-lastB.t<900)) return;
  if(e.target.closest && e.target.closest('#palace-svg .pl-lmb,#pal-dock,.pal-ghost,#detail-page')) return;
  var cv=document.getElementById('canvas'); if(!cv || !cv.contains(e.target) || (e.target.closest && e.target.closest('.node'))) return;
  var p=canvasPt(cv, e.clientX, e.clientY); zoomAnim(Z*1.8, p[0], p[1]);
});


/* a floor has no card on the map: finding one (search, a link) goes inside its building at that floor */
function wrapFocus(){ var _ef=window.enterFocus; if(!_ef || _ef._pal) return;
  window.enterFocus=function(id){ if(P.of[id] && !mob()){ return window.showDetail('node', id); } return _ef.apply(this, arguments); }; window.enterFocus._pal=1; }
['DOMContentLoaded','load'].forEach(function(ev){ window.addEventListener(ev, wrapFocus); });
/* The board is not under the window while a detail page is open (the canvas is display:none: no size, no scroll). So the view is
   settled and remembered before the page opens, nothing is laid out against the hidden canvas, and the view is put back, laid out
   for real, when the page closes — else the map came back scrolled to its empty top-left corner. */
var LV=null, lastRv=0;
/* the view as it was last seen on the map: kept as it changes, so that however a page opens over the map (any function, any link) the map can be put back */
function trackView(){ var cv=document.getElementById('canvas'); if(!cv || mob() || !cv.clientWidth || PV || de.classList.contains('detail-open') || !de.classList.contains('alto-palace')) return; LV={z:Z, x:cv.scrollLeft, y:cv.scrollTop}; }
(function(){ var c=document.getElementById('canvas'); if(c && !c._lvS){ c._lvS=1; c.addEventListener('scroll', trackView, {passive:true}); } })();
/* put the map back as it was (or, with nothing remembered, in the middle of the city — never the empty top-left corner) and keep it there against anything
   that resets it a moment later, until the person moves it themself */
function restoreView(){
  var cv=document.getElementById('canvas'); if(!cv || mob() || !de.classList.contains('alto-palace') || de.classList.contains('detail-open')) return;
  var hv=holdView||null; holdView=null; lastRv=performance.now();
  var live=true; function stop(){ live=false; ['wheel','pointerdown','keydown','touchstart'].forEach(function(t){ window.removeEventListener(t, stop, true); }); }
  ['wheel','pointerdown','keydown','touchstart'].forEach(function(t){ window.addEventListener(t, stop, true); });
  function put(first){
    if(hv){ if(Math.abs(Z-hv.z)>1e-6 && first){ Z=hv.z; placeAllReal(); if(window._altoPalaceGeo) window._altoPalaceGeo.Z=Z; }
      if(first || Math.abs(cv.scrollLeft-hv.x)>2 || Math.abs(cv.scrollTop-hv.y)>2){ cv.scrollLeft=hv.x; cv.scrollTop=hv.y; } }
    else if(!window._focusedNodeId && (cv.scrollWidth>cv.clientWidth+4 || cv.scrollHeight>cv.clientHeight+4) && (first || (!cv.scrollLeft && !cv.scrollTop))){ if(first) placeAllReal(); centreCity(cv); }
  }
  put(true);
  [0,90,320,800].forEach(function(ms,i){ setTimeout(function(){ if(live && !de.classList.contains('detail-open')) put(false); if(i===3) stop(); }, ms||16); });
}
function wrapDetail(){ var sd=window.showDetail, st=window.showTimeline; if(!sd || !st || sd._pal) return;
  window.showDetail=function(){
    if(!mob() && de.classList.contains('alto-palace') && !de.classList.contains('detail-open')){
      var cv=document.getElementById('canvas');
      if(flyId){ pendEnl=flyId; flyId=null; }
      cancelAnimationFrame(zAnim);
      if(cv && cv.clientWidth){ if(PV) placeAll(); holdView={z:Z, x:cv.scrollLeft, y:cv.scrollTop}; }
    }
    return sd.apply(this, arguments); };
  window.showDetail._pal=1;
  window.showTimeline=function(){
    var r=st.apply(this, arguments), pe=pendEnl; pendEnl=null;
    if(!mob() && de.classList.contains('alto-palace')){ if(pe) holdView=null; restoreView();
      if(pe && !window._focusedNodeId) setTimeout(function(){ if(!de.classList.contains('detail-open')) enlarge(pe); }, 60); }
    return r; };
  window.showTimeline._pal=1; }
/* whatever opens or closes a page over the map (the elevator, a landmark's page, an index, a search hit, Back): the class on <html> says so */
(function(){ var was=de.classList.contains('detail-open');
  new MutationObserver(function(){ var now=de.classList.contains('detail-open'); if(now===was) return; was=now;
    if(now){ if(!holdView && LV) holdView={z:LV.z, x:LV.x, y:LV.y}; }
    else if(performance.now()-lastRv>400) restoreView(); }).observe(de, {attributes:true, attributeFilter:['class']}); })();
['DOMContentLoaded','load'].forEach(function(ev){ window.addEventListener(ev, wrapDetail); });
document.addEventListener('alto-focus-exit', function(){ drawRoutes(svgD, null); });
/* arrows while a building is enlarged: to the nearest building that way */
window._altoPalaceNav=function(id, dir){
  if(mob()) return null; var A=lot(P.at[bOf(id)]); if(!A) return null;
  var V={e:[1,0],w:[-1,0],n:[0,-1],s:[0,1],ne:[.7071,-.7071],nw:[-.7071,-.7071],se:[.7071,.7071],sw:[-.7071,.7071]}[dir]; if(!V) return null;
  var best=null, bd=1e18, diag=dir.length===2, near=null, nd=1e18;
  (P.units||[]).forEach(function(ids){ ids.forEach(function(o){ if(o===id) return; var c=document.querySelector('#node-'+o+' .node-card');
    if(c && (c.classList.contains('dimmed')||c.classList.contains('ent-dimmed')||c.classList.contains('rel-dimmed'))) return;
    var B=lot(P.at[o]); if(!B) return; var dx=B[0]-A[0], dy=B[1]-A[1], along=dx*V[0]+dy*V[1]; if(along<=10) return;
    var across=Math.abs(dx*V[1]-dy*V[0]), cost=along+across*2.2; if(cost<bd){ bd=cost; best=o; }
    /* a diagonal asks for a building on that diagonal (within 35 degrees of it), the nearest of those; none there: the best of any */
    if(diag && across<=along*.7 && Math.hypot(dx,dy)<nd){ nd=Math.hypot(dx,dy); near=o; } }); });
  return near||best;
};

/* ── the key and the zoom buttons ── */
function ctl(){
  if(mob() || document.getElementById('pal-ctl')) return;
  var c=document.createElement('div'); c.id='pal-ctl';
  var h='<h5><span>'+esc(P.place||'The city')+'</span><span></span></h5><div class="pk-body">';
  (P.d||[]).forEach(function(d){ var pm=PHASE_META[d.u]; if(!pm) return;
    h+='<div class="pk-row" data-u="'+d.u+'"><span class="pk-sw" style="background:'+pm.colorRaw+'"></span><div><b>'+esc(d.n||pm.label)+'</b><small>Unit '+esc(pm.numeral)+' · '+esc(pm.label)+'</small></div></div>'; });
  var sw=function(s){ return '<svg width="26" height="12" style="flex:none">'+s+'</svg>'; };
  h+='<div class="pk-sep"></div>';
  if(window._palTr.has()) h+=window._palTr.keyHtml(sw); else {
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#59616c" stroke-width="7" stroke-dasharray="1.4 4.6"/><line x1="1" y1="6" x2="25" y2="6" stroke="#59616c" stroke-width="2.6"/>')+'<div>Railway <small>above ground — the cross-ties mark a train line</small></div></div>';
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#3d6fb6" stroke-width="2.6" stroke-dasharray="6 4" opacity=".7"/>')+'<div>Subway or tunnel</div></div>';
  h+='<div class="pk-row">'+sw('<circle cx="13" cy="6" r="5" fill="#fff" stroke="#2f3338" stroke-width="2.5"/><circle cx="13" cy="6" r="2" fill="#2f3338"/>')+'<div>Station <small>a big ring is a hub</small></div></div>'; }
  if(window._palHw.has()) h+='<div class="pk-sep"></div>'+window._palHw.keyHtml(sw);   /* the highways (palace_highway_js.py) */
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="var(--pal-trail)" stroke-width="2.6" stroke-dasharray="6 3"/>')+'<div>Trail</div></div>';
  h+=window._palLm.keyRow();
  var rk={}; (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).forEach(function(x){ if(x && x[2]!=='spine') rk[x[2]]=1; });
  Object.keys(rk).forEach(function(r){ var col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[r])||'var(--accent)', lb=(typeof REL_LABELS!=='undefined'&&REL_LABELS[r])||r;
    h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="'+col+'" stroke-width="4" stroke-dasharray="7 4"/>')+'<div>Route: '+esc(lb)+'</div></div>'; });
  if(window._palRide&&window._palRide.ui&&window._palRide.ui.keyRows) h+=window._palRide.ui.keyRows();   /* aerial / first-person, first-person rides (palace_ride_f.py) */
  h+='<small style="margin-top:4px">Point at a building for its name and its routes; click to enlarge it, again to go inside. Point at a street for its name.</small>';
  h+='<div class="pk-credit">Map data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors</div></div>';
  var ic=function(d){ return '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; };
  var z='<div class="pc-pill" role="group" aria-label="Zoom">'
    +'<button type="button" data-z="in" data-tip="Closer · ⌘ +" aria-label="Zoom in">'+ic('<path d="M10 4.5v11M4.5 10h11"/>')+'</button><span class="pc-div"></span>'
    +'<button type="button" data-z="out" data-tip="Farther · ⌘ −" aria-label="Zoom out">'+ic('<path d="M4.5 10h11"/>')+'</button></div>'
    +'<button type="button" class="pc-city" data-z="fit" data-tip="The whole city · ⌘ 0" aria-label="Show the whole city">'
    +ic('<path d="M3.5 7.3V5.4a1.9 1.9 0 0 1 1.9-1.9h1.9M12.7 3.5h1.9a1.9 1.9 0 0 1 1.9 1.9v1.9M16.5 12.7v1.9a1.9 1.9 0 0 1-1.9 1.9h-1.9M7.3 16.5H5.4a1.9 1.9 0 0 1-1.9-1.9v-1.9"/>'
      +'<rect x="7.2" y="7.2" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="10.5" y="7.2" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/>'
      +'<rect x="7.2" y="10.5" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="10.5" y="10.5" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/>')
    +'<span>City</span></button>';
  c.setAttribute('role','toolbar'); c.setAttribute('aria-label','Map zoom'); c.innerHTML=z; document.body.appendChild(c); window._palDirMount(c); if(window._palRide&&window._palRide.ui&&window._palRide.ui.mount) window._palRide.ui.mount(c);
  /* the key is a toggle floating at the top left (key_toggle.py); its rows act like the buttons' neighbours did */
  var k=document.createElement('div'); k.id='pal-key'; k.innerHTML=h;
  window._altoKeyToggle(k, 'alto-palace-key', 'Key to the city');
  ctlState();
  [c,k].forEach(function(c){
  c.addEventListener('click', function(e){ var b=e.target.closest('[data-z]'); if(b){ var z=b.getAttribute('data-z'); if(window._focusedNodeId && window.exitFocus) window.exitFocus();
      zoomAnim(z==='fit'?zmin():Z*(z==='in'?1.6:1/1.6)); return; }
    var r=e.target.closest('.pk-row[data-u]'); if(r){ var d=(P.d||[]).filter(function(q){ return q.u===+r.getAttribute('data-u'); })[0]; if(d){ if(window._focusedNodeId && window.exitFocus) window.exitFocus(); flyToBox(d.box); } } });
  c.addEventListener('mouseover', function(e){ var r=e.target.closest('.pk-row[data-u]'); if(r && svgD && !focused()) drawRoutes(svgD, null, +r.getAttribute('data-u')); });
  c.addEventListener('mouseout', function(e){ if(!e.relatedTarget || !c.contains(e.relatedTarget)){ if(svgD && !focused()) drawRoutes(svgD, null); } });
  });
}

/* ── inside: the elevator ── */
var cur=null, riding=false, elev=null, doors=null;
function stack(id){ var b=bOf(id); return [b].concat(P.fl[b]||[]); }
function buildElev(){
  if(elev) return; elev=document.createElement('div'); elev.id='pal-elev'; document.body.appendChild(elev); elevWire(elev);
  doors=document.createElement('div'); doors.id='pal-doors'; doors.innerHTML='<div class="pd pd-l"></div><div class="pd pd-r"></div><div class="pd-ind"></div>'; document.body.appendChild(doors);
  elev.addEventListener('click', function(e){
    var out=e.target.closest('.pe-out'); if(out){ e.stopPropagation(); letOut(out.getAttribute('data-id')); return; }
    var pno=e.target.closest('.pe-no'); if(pno){ e.stopPropagation(); var rr=pno.getBoundingClientRect(); numberForm(pno.getAttribute('data-id'), anchorAt(rr.left, rr.bottom)); return; }
    var f=e.target.closest('.pe-fl'); if(f){ ride(f.getAttribute('data-id')); return; }
    if(e.target.closest('.pe-street')){ var b=bOf(cur); if(window.showTimeline) window.showTimeline(); setTimeout(function(){ if(!mob() && isB(b)) enlarge(b); else if(mob() && window.featureNode) window.featureNode(b,true); }, 80); }
  });
}
function editing(){ return de.classList.contains('alto-editing'); }
function drawElev(id){
  buildElev(); var s=stack(id), b=s[0], c=ucol(b), tw=towerOf(b);
  elev.style.setProperty('--pal-car', c);
  var h='<div class="pe-roof" style="background:'+c+'">'+esc(num(b))+'<span class="pe-sec"> · '+esc(PHASE_META[ACT[b]]?(PHASE_META[ACT[b]].label.split(' — ')[1]||PHASE_META[ACT[b]].label):'')+'</span><small>'+esc(title(b))+(tw?' · tower, '+tw.top+' floors':'')+'</small><span class="pe-where"></span></div><div class="pe-shaft"><div class="pe-car" title="Drag to another floor"></div>';
  for(var i=s.length-1;i>=0;i--){ var f=s[i], gap=(tw&&i>1)?floorNo(f)-floorNo(s[i-1])-1:(tw&&i===1?floorNo(f)-1:0);
    /* in a tower the floors are spaced by how many real floors lie between them */
    h+='<button class="pe-fl'+(f===id?' on':'')+(gap>0?' gap':'')+'"'+(gap>0?' style="margin-bottom:'+Math.min(26,gap*3)+'px"':'')+' data-id="'+esc(f)+'"><span class="pe-n">'+(i===0?'G':floorNo(f))+'</span><span class="pe-t">'+esc(title(f))+'</span>'
      +(i>0 && tw && editing() && !mob()?'<span class="pe-no" data-id="'+esc(f)+'" title="Change this floor\'s number">#</span>':'')
      +(i>0 && editing() && !mob()?'<span class="pe-out" data-id="'+esc(f)+'" title="Let this floor out into a building of its own">⇱</span>':'')+'</button>'; }
  var where=(P.near||{})[b];
  h+='</div><div class="pe-call"><button class="pe-up" title="Up a floor (↑)" aria-label="Up a floor">▲</button><button class="pe-dn" title="Down a floor (↓)" aria-label="Down a floor">▼</button>'
    +'<small>↑ ↓ keys · drag the car · scroll past an edge</small></div><button class="pe-street">⌂ Out to the street<small>'+esc(where||'')+'</small></button>';
  elev.innerHTML=h; place(); carTo(id, true);
}
function carTo(id, now){ if(!elev) return; var row=elev.querySelector('.pe-fl[data-id="'+id+'"]'), car=elev.querySelector('.pe-car'); if(!row||!car) return;
  if(now){ car.style.transition='none'; car.style.top=(row.offsetTop+row.offsetHeight/2-15)+'px'; car.offsetTop; car.style.transition=''; }
  else car.style.top=(row.offsetTop+row.offsetHeight/2-15)+'px';
  elev.querySelectorAll('.pe-fl').forEach(function(r){ r.classList.toggle('on', r===row); });
  elevState(id);
  var sh=elev.querySelector('.pe-shaft'); if(sh && !mob()){ var t=row.offsetTop-sh.clientHeight/2; sh.scrollTop=Math.max(0,t); }
}
function place(){
  var dp=document.getElementById('detail-page'); if(!dp || !elev) return;
  var top=dp.offsetTop;
  if(mob()){ elev.style.top=(top+68)+'px'; elev.style.maxHeight=''; }
  else { elev.style.top=(top+16)+'px'; elev.style.maxHeight='calc(100vh - '+(top+32)+'px)'; }
  doors.style.top=top+'px'; doors.style.left=mob()?'0px':'246px';
}
function sync(){
  var dp=document.getElementById('detail-page'), vis=dp && dp.classList.contains('visible');
  var id=vis && window._currentDetailType==='node' ? window._currentDetailId : null;
  if(!id || !TT[id] || stack(id).length<2){ de.classList.remove('pal-elev-on'); cur=id; return; }
  de.classList.add('pal-elev-on');
  if(riding){ cur=id; return; }
  if(cur && elev && elev.querySelector('.pe-fl[data-id="'+id+'"]') && stack(cur)[0]===stack(id)[0]){ cur=id; carTo(id); return; }
  cur=id; drawElev(id);
}
function ride(to){
  if(riding || !cur || to===cur) return;
  var s=stack(cur), a=s.indexOf(cur), b=s.indexOf(to); if(b<0) return;
  var calm=window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(calm){ window.showDetail('node', to); return; }
  riding=true; place();
  var ind=doors.querySelector('.pd-ind'), up=b>a; ind.textContent=(up?'▲ ':'▼ ')+(a===0?'G':a);
  doors.classList.add('on'); doors.offsetTop; doors.classList.add('shut');
  setTimeout(function(){
    var floors=Math.abs(b-a), per=Math.max(180, Math.min(420, 1100/floors)), car=elev.querySelector('.pe-car');
    if(car) car.style.transitionDuration=(per*floors)+'ms';
    carTo(to);
    var i=a; var tick=setInterval(function(){ i+=up?1:-1; ind.textContent=(up?'▲ ':'▼ ')+(i===0?'G':i); elevPass(s[i]); if(i===b){ clearInterval(tick); } }, per);
    setTimeout(function(){
      window.showDetail('node', to); var dp=document.getElementById('detail-page'); if(dp) dp.scrollTop=0;
      ind.textContent=(b===0?'G':b)+(b===s.length-1?' · top':'');
      setTimeout(function(){ doors.classList.remove('shut');
        setTimeout(function(){ doors.classList.remove('on'); if(car) car.style.transitionDuration=''; riding=false; cur=to; sync(); }, 340); }, 260);
    }, per*floors+120);
  }, 340);
}
function watch(){
  var dp=document.getElementById('detail-page'), dc=document.getElementById('detail-content'); if(!dp||!dc) return;
  var mo=new MutationObserver(function(){ requestAnimationFrame(sync); });
  mo.observe(dp, {attributes:true, attributeFilter:['class']}); mo.observe(dc, {childList:true});
  window.addEventListener('resize', function(){ if(de.classList.contains('pal-elev-on')) place(); });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', watch); else watch();

/* ═══ ELEVATOR (interaction pass): more ways to change floors, and the car's place made plain ═══
   The floor buttons stay. Added: the call buttons ▲ ▼; ↑ ↓ / PgUp PgDn (when the page cannot scroll further that way, or with Alt);
   scrolling or swiping PAST the top or bottom edge of the page (a pull shows where it leads, a gesture that began mid-page
   never counts, so momentum does not carry you through a floor); the wheel over the elevator; dragging the car; the roof is
   the ground floor. ← → keep their meaning (the previous / next card, as on every detail page). Up = the next floor above:
   scroll past the TOP of a floor and you go up, past the BOTTOM and you go down. */
function elevOn(){ return de.classList.contains('pal-elev-on') && !riding && !!cur; }
function stepFloor(d){ if(!elevOn()) return false; var s=stack(cur), i=s.indexOf(cur)+d; if(i<0||i>=s.length) return false; ride(s[i]); return true; }
function elevState(id){ if(!elev) return; var s=stack(id), i=s.indexOf(id);
  var w=elev.querySelector('.pe-where'), tw=towerOf(id); if(w) w.textContent=i===0?'Ground floor':(tw?'Floor '+floorNo(id)+' of '+tw.top:'Floor '+i+' of '+(s.length-1));
  var up=elev.querySelector('.pe-up'), dn=elev.querySelector('.pe-dn'); if(up) up.disabled=i>=s.length-1; if(dn) dn.disabled=i<=0;
  var rf=elev.querySelector('.pe-roof'); if(rf) rf.title=i===0?'':'Back to the ground floor';
  elev.querySelectorAll('.pe-fl.pass').forEach(function(r){ r.classList.remove('pass'); }); }
function elevPass(id){ if(!elev) return; elev.querySelectorAll('.pe-fl').forEach(function(r){ r.classList.toggle('pass', r.getAttribute('data-id')===id); }); }
function dpEl(){ return document.getElementById('detail-page'); }
/* is the detail page at its top (dir -1) or bottom (dir 1) edge? (a page that does not scroll is at both) */
function edgeAt(dir){ var dp=dpEl(); if(!dp) return false; var max=dp.scrollHeight-dp.clientHeight; return dir<0 ? dp.scrollTop<=1 : dp.scrollTop>=max-1; }
var pull=null, PULL=110;
function pullShow(dir, p){
  if(!pull){ pull=document.createElement('div'); pull.id='pal-pull'; document.body.appendChild(pull); }
  if(!(p>0) || !cur){ pull.classList.remove('on','go'); return; }
  var s=stack(cur), i=s.indexOf(cur)+(dir<0?1:-1); if(i<0||i>=s.length){ pull.classList.remove('on','go'); return; }
  var dp=dpEl(); pull.style.setProperty('--pal-car', ucol(s[0])); pull.style.setProperty('--dpt', ((dp&&dp.offsetTop)||96)+'px'); pull.style.setProperty('--p', Math.min(1,p));
  pull.className='on '+(dir<0?'pp-up':'pp-dn')+(p>=1?' go':'');
  pull.innerHTML='<b>'+(dir<0?'▲':'▼')+' '+(i===0?'G':i)+'</b><span>'+esc(title(s[i]))+'</span>'; }
var pAcc=0, pDir=0, pLast=-1e9, pStart=false, pLock=0, pDecay=null;
window.addEventListener('wheel', function(e){
  if(mob() || !elevOn() || e.ctrlKey) return;
  var dp=dpEl(); if(!dp || !dp.contains(e.target)) return;
  var dy=e.deltaY*(e.deltaMode===1?16:1); if(!dy || Math.abs(dy)<=Math.abs(e.deltaX)) return;
  var dir=dy<0?-1:1, now=e.timeStamp;
  if(now-pLast>140){ pStart=now>=pLock && edgeAt(dir); }           /* a new gesture: only one that BEGINS at the edge can pull */
  pLast=now; if(!pStart) return;
  if(pDir!==dir){ pAcc=0; pDir=dir; }
  pAcc+=Math.abs(dy); pullShow(dir, pAcc/PULL);
  clearTimeout(pDecay); pDecay=setTimeout(function(){ pAcc=0; pullShow(dir,0); }, 650);
  if(pAcc>=PULL){ pAcc=0; pullShow(dir,0); pLock=now+900; pStart=false; stepFloor(dir<0?1:-1); }
}, {passive:true});
window.addEventListener('keydown', function(e){
  if(mob() || !elevOn() || e.ctrlKey || e.metaKey || e.shiftKey) return;
  var k=e.key, up=(k==='ArrowUp'||k==='PageUp'), dn=(k==='ArrowDown'||k==='PageDown'); if(!up && !dn) return;
  var a=document.activeElement, tg=a&&a.tagName; if(tg==='INPUT'||tg==='TEXTAREA'||tg==='SELECT'||(a&&a.isContentEditable)) return;
  var dir=up?-1:1; if(!e.altKey && !edgeAt(dir)) return;           /* the page still has room: let it scroll */
  if(e.repeat){ e.preventDefault(); return; }
  if(stepFloor(dir<0?1:-1)){ e.preventDefault(); e.stopPropagation(); }
}, true);
function elevWire(el){
  var eAcc=0, eLast=-1e9, eLock=false, drag=null;
  el.addEventListener('wheel', function(e){
    if(mob() || e.ctrlKey) return; e.preventDefault();
    var dy=e.deltaY*(e.deltaMode===1?16:1); if(!dy || Math.abs(dy)<Math.abs(e.deltaX)) return;
    var now=e.timeStamp; if(now-eLast>160){ eAcc=0; eLock=false; } eLast=now; if(eLock) return;
    eAcc+=dy; if(Math.abs(eAcc)>=45){ eLock=true; eAcc=0; stepFloor(dy>0?-1:1); }
  }, {passive:false});
  el.addEventListener('click', function(e){
    if(e.target.closest('.pe-up')){ stepFloor(1); return; }
    if(e.target.closest('.pe-dn')){ stepFloor(-1); return; }
    if(e.target.closest('.pe-roof') && cur){ var s=stack(cur); if(s[0]!==cur) ride(s[0]); }
  });
  /* dragging the car: it follows the pointer, the floor it would stop at lights, and on release it rides there */
  el.addEventListener('pointerdown', function(e){
    var car=e.target.closest && e.target.closest('.pe-car'); if(!car || mob() || riding || e.button) return;
    var sh=el.querySelector('.pe-shaft'); e.preventDefault(); try{ car.setPointerCapture(e.pointerId); }catch(x){}
    var r=sh.getBoundingClientRect(), sc=(r.height/sh.offsetHeight)||1, cr=car.getBoundingClientRect();
    drag={car:car, sh:sh, sc:sc, grab:(e.clientY-cr.top)/sc, y0:e.clientY, moved:false, to:null};
    car.style.transition='none'; el.classList.add('pe-drag'); });
  el.addEventListener('pointermove', function(e){
    if(!drag) return; if(Math.abs(e.clientY-drag.y0)>3) drag.moved=true;
    var rows=[].slice.call(el.querySelectorAll('.pe-fl')); if(!rows.length) return;
    var cents=rows.map(function(q){ return q.offsetTop+q.offsetHeight/2; }), r=drag.sh.getBoundingClientRect();
    var t=(e.clientY-r.top)/drag.sc+drag.sh.scrollTop-drag.grab+15;
    t=Math.max(cents[0], Math.min(cents[cents.length-1], t)); drag.car.style.top=(t-15)+'px';
    var bi=0, bd=1e9; cents.forEach(function(c,i){ var d=Math.abs(c-t); if(d<bd){ bd=d; bi=i; } });
    rows.forEach(function(q,i){ q.classList.toggle('aim', drag.moved && i===bi); }); drag.to=rows[bi].getAttribute('data-id'); });
  function endDrag(e){ if(!drag) return; var d=drag; drag=null; el.classList.remove('pe-drag');
    el.querySelectorAll('.pe-fl.aim').forEach(function(q){ q.classList.remove('aim'); });
    d.car.style.transition=''; try{ d.car.releasePointerCapture(e.pointerId); }catch(x){}
    if(d.moved && d.to && d.to!==cur) ride(d.to); else if(cur) carTo(cur); }
  el.addEventListener('pointerup', endDrag); el.addEventListener('pointercancel', endDrag);
  touchWire();
}
/* a swipe past an edge of the page, on a phone: finger down at the top = up a floor, finger up at the bottom = down a floor */
function touchWire(){
  var dp=dpEl(); if(!dp || dp._palTouch) return; dp._palTouch=1;
  var y0=null, x0=0, atTop=false, atBot=false, tDir=0, tP=0;
  dp.addEventListener('touchstart', function(e){ if(!elevOn() || e.touches.length!==1){ y0=null; return; }
    y0=e.touches[0].clientY; x0=e.touches[0].clientX; atTop=edgeAt(-1); atBot=edgeAt(1); tDir=0; tP=0; }, {passive:true});
  dp.addEventListener('touchmove', function(e){ if(y0==null || e.touches.length!==1) return;
    var dy=e.touches[0].clientY-y0, dx=e.touches[0].clientX-x0;
    if(Math.abs(dx)>20 && Math.abs(dx)>Math.abs(dy)*.8){ y0=null; pullShow(0,0); return; }     /* sideways: the page-to-page swipe */
    var dir=dy>0?-1:1; if(!(dir<0?atTop:atBot)){ pullShow(0,0); return; }
    tDir=dir; tP=Math.abs(dy)/110; pullShow(dir, tP); }, {passive:true});
  function end(){ if(y0!=null && tP>=1) stepFloor(tDir<0?1:-1); pullShow(0,0); y0=null; tP=0; }
  dp.addEventListener('touchend', end, {passive:true}); dp.addEventListener('touchcancel', function(){ pullShow(0,0); y0=null; tP=0; }, {passive:true});
}
/* ── phones: each card says where it stands; the MAP button opens the city ── */
function phoneWhere(){ if(!mob()) return;
  document.querySelectorAll('.node[id^="node-"]').forEach(function(n){ var id=n.id.slice(5), c=n.querySelector('.node-card'); if(!c || c.querySelector('.pal-where')) return;
    var d=document.createElement('div'); d.className='pal-where';
    if(P.of[id]){ var s=stack(id); d.textContent='Floor '+floorNo(id)+' of '+num(s[0])+' '+title(s[0]); }
    else d.textContent=((P.near||{})[id]||'')+((P.fl[id]||[]).length?' · '+((towerOf(id)||{}).top||((P.fl[id]||[]).length+1))+' floors':'');
    if(!d.textContent) return; var tg=c.querySelector('.node-tag'); c.insertBefore(d, tg||c.firstChild); }); }
['DOMContentLoaded','load'].forEach(function(ev){ window.addEventListener(ev, function(){ phoneWhere(); setTimeout(phoneWhere, 400); }); });
var MM={z:.46, svg:null, box:null};
/* the map page itself (mmapOpen, mmapClose and the sheet) is palace_mobile.py's; Directions is palace_directions.py's */
document.addEventListener('click', function(e){
  if(!mob()) return; var t=e.target.closest && e.target.closest('#minimap-toggle'); if(!t) return;
  e.preventDefault(); e.stopImmediatePropagation(); mmapOpen();
}, true);
document.addEventListener('touchend', function(e){
  if(!mob()) return; var t=e.target.closest && e.target.closest('#minimap-toggle'); if(!t) return;
  e.preventDefault(); e.stopImmediatePropagation(); mmapOpen();
}, true);

/* ── manual edit mode: drag a building to another lot, or onto a building to make it a floor of it ── */
var dragging=null, moved=false;
window._altoPalaceField=function(k){
  var p=k.split('|');
  if(p[1] && !TT[p[1]]) tables();                    // a building just added on the page
  if(p[0]==='p' && p[2]==='lot' && TT[p[1]]) return {kind:'card', sig:function(){ var h=(P.pl0||{})[p[1]]; return h&&h.lot?h.lot:null; }, get:function(){ return P.at[p[1]]||null; },
    set:function(v){ if(v) P.at[p[1]]=v; else delete P.at[p[1]]; P._dirty=1; }};
  /* a tower floor's real number (null: the spread's own) */
  if(p[0]==='p' && p[2]==='fno' && TT[p[1]]) return {kind:'card', sig:function(){ var h=(P.pl0||{})[p[1]]; return h&&h.fno?h.fno:null; }, get:function(){ return P.fx[p[1]]!=null?P.fx[p[1]]:null; },
    set:function(v){ var id=p[1]; if(v){ P.fx[id]=+v; P.fn[id]=+v; } else { delete P.fx[id]; if(P.fn0[id]!=null) P.fn[id]=P.fn0[id]; else delete P.fn[id]; } P._dirty=1; }};
  /* a floor let out of its tower (an ordinary building of its section again) */
  if(p[0]==='p' && p[2]==='out' && TT[p[1]]) return {kind:'card', sig:function(){ var h=(P.pl0||{})[p[1]]; return h&&h.out?1:null; }, get:function(){ return P.out[p[1]]?1:null; },
    set:function(v){ var id=p[1]; if(v){ P.out[id]=1; P.par[id]=''; } else { delete P.out[id]; var th=towerOfUnit(ACT[id]); if(th) P.par[id]=th; } P._dirty=1; }};
  /* the unit a landmark houses: {unit, floors} (null: none) */
  if(p[0]==='pu' && lmOf(p[1])){ var nm=p[1], one=function(s){ return s?{unit:s.unit, floors:s.floors==null?null:s.floors}:null; };
    return {kind:'card', sig:function(){ return one((P.lm0||{})[nm]); }, get:function(){ return one(P.lm[nm]); }, set:function(v){ applyTower(nm, v); }}; }
  if(p[0]==='pf' && TT[p[1]]) return {kind:'card', get:function(){ return P.par[p[1]]||''; },
    set:function(v){ if(v) P.par[p[1]]=v; else delete P.par[p[1]]; P._dirty=1; }};
  return null;
};
window._altoPalaceRefresh=function(){ P._dirty=0; restructure(true);
  if(P._lmDirty && svgD){ P._lmDirty=0; drawCity(svgD); if(MM.svg) drawCity(MM.svg); }
  if(svgD){ drawBuildings(svgD); var labels=svgD.querySelectorAll('.pl-dist');
    labels.forEach(function(t){ var u=+t.getAttribute('data-u'), d=(P.d||[]).filter(function(q){ return q.u===u; })[0]; if(!d) return; var c=districtCentre(d);
      t.setAttribute('x',c[0]); t.setAttribute('y',c[1]); [].forEach.call(t.querySelectorAll('tspan'),function(s){ s.setAttribute('x',c[0]); }); }); }
  ENT={}; placeAll(); if(de.classList.contains('pal-elev-on') && cur){ drawElev(cur); } };
window._altoPalaceDirty=function(){ P._dirty=1; };
function chg(list){ if(window._altoEditChanges) return window._altoEditChanges(list); return false; }
function letOut(fid){
  var b=bOf(fid), L=lot(P.at[b]), key=freeLot(L?L[0]:M.W/2, L?L[1]:M.H/2);
  if(towerOf(fid)){ var l=lmOf(towerOf(fid).n), k2=l?freeLot(l.x,l.y):key;                 /* a tower's floor: out to a lot beside its landmark; the rest keep their numbers */
    var list=(P.tk[fid]?[]:[['pf|'+fid, '']]).concat([['p|'+fid+'|out', 1], ['p|'+fid+'|lot', k2], ['p|'+fid+'|fno', null]]);    /* (a floor of a floor leaves its parent too) */
    chg(list.concat(freezeOps(b, fid))); return; }
  chg([['pf|'+fid, ''], ['p|'+fid+'|lot', key]]);
}
/* ── a landmark that houses a unit: its floors are that unit's buildings (palace_towers.py); edit mode can house one, move it out,
   add a floor, give a floor another real number or let it out. The edits are P.lm / P.fx / P.out, laid over the built page. ── */
function lmOf(name){ var r=null; (M.landmarks||[]).forEach(function(l){ if(l.box && l.n===name) r=l; }); return r; }
/* v2: a landmark turned by l.a (degrees, about its box's centre): its box is in its own upright frame, so a map point is turned back
   by -a before it is tested against the box, and a point of the box is turned by a to reach the map */
function lmC(l){ var b=l.box; return [(b[0]+b[2])/2, (b[1]+b[3])/2]; }
function lmTurn(l, p, sgn){ if(!l.a) return p; var c=lmC(l), r=sgn*l.a*Math.PI/180, co=Math.cos(r), si=Math.sin(r), dx=p[0]-c[0], dy=p[1]-c[1];
  return [c[0]+dx*co-dy*si, c[1]+dx*si+dy*co]; }
function lmLocal(l, p){ return lmTurn(l, p, -1); }
function towerHub(name){ var h=null; Object.keys(P.tw||{}).forEach(function(k){ if(P.tw[k].n===name) h=k; }); return h; }
function towerOfUnit(u){ var h=null; Object.keys(P.tw||{}).forEach(function(k){ if(P.tw[k].u===u) h=k; }); return h; }
function pyRound(x){ var f=Math.floor(x), d=x-f; return d<.5?f:d>.5?f+1:(f%2===0?f:f+1); }
/* the real floor numbers of a tower's floors in reading order: spread over 2..top, a chosen number kept, the rest moved up past it (palace_towers.floor_numbers) */
function spreadNo(ids, top, fixed){ var m=ids.length, out={}, used={}, sp={}; if(!m) return out; top=Math.max(top, m+1);
  ids.forEach(function(f,i){ sp[f]=m===1?top:2+pyRound(i*(top-2)/(m-1)); });
  ids.forEach(function(f){ if(fixed && fixed[f]!=null){ out[f]=fixed[f]; used[fixed[f]]=1; } });
  ids.forEach(function(f){ if(out[f]!=null) return; var n=sp[f]; while(used[n]) n++; used[n]=1; out[f]=n; });
  return out; }
function floorsOf(h){ var kids={}; ORDER.forEach(function(id){ var q=P.par[id]; if(q && TT[q]) (kids[q]=kids[q]||[]).push(id); });
  var out=[], st=(kids[h]||[]).slice().reverse(); while(st.length){ var f=st.pop(); out.push(f); (kids[f]||[]).slice().reverse().forEach(function(k){ st.push(k); }); } return out; }
/* a tower's chip stands in the corner of its landmark's card: one more block, one lot (palace_towers.tower_lots) */
function chipLot(name){ var l=lmOf(name); if(!l) return null; var lots=[]; P.b.forEach(function(ls){ if(ls && ls.length) lots.push(ls[0]); }); lots=lots.slice(0,50);
  var ws=lots.map(function(q){ return q[2]; }).sort(function(a,b){ return a-b; }), hs=lots.map(function(q){ return q[3]; }).sort(function(a,b){ return a-b; });
  var lw=lots.length?ws[lots.length>>1]:24, lh=lots.length?hs[lots.length>>1]:16, x0=l.box[0], y0=l.box[1], x1=l.box[2], y1=l.box[3];
  var C=window._palLm.cardOf(l, M.landmarks||[]), left=C[0], w=Math.max(30,Math.min(lw,left-x0-18)), h=lh*w/lw, r=function(v){ return Math.round(v*10)/10; };
  var cx=left+10-w/2, cy=C[1]+22+h/2; if(l.a){ var q=lmTurn(l, [cx,cy], 1); cx=q[0]; cy=q[1]; }
  return [r(cx), r(cy), r(w), r(h), l.a?+l.a:0]; }
function applyTower(name, v){
  var h=towerHub(name); if(!lmOf(name)) return;
  if(h){                                                  /* move the unit out: its buildings are buildings again */
    var bi=parseInt(String(P.at[h]||'').split('.')[0],10); if(!isNaN(bi) && bi>=(P.nb||0)) P.b[bi]=[];
    Object.keys(P.tk).forEach(function(id){ if(P.par[id]===h){ P.par[id]=''; P.par0[id]=''; delete P.fn[id]; var pa=P.prevAt[id]; if(pa && !lotUsed(pa)) P.at[id]=pa; } });
    delete P.at[h]; var pa=P.prevAt[h]; if(pa && !lotUsed(pa)) P.at[h]=pa;
    delete P.tw[h]; P.lm[name]=null; }
  if(v){
    var u=+v.unit, roots=((P.units||[])[u]||[]).filter(function(id){ return !P.out[id] && !P.tw[id]; });
    if(roots.length){ var hub=roots[0], cl=chipLot(name), top0=v.floors||(P.lmtop||{})[name]||30;
      roots.slice(1).forEach(function(r){ P.prevAt[r]=P.at[r]; delete P.at[r]; P.par[r]=hub; P.tk[r]=1; });
      P.prevAt[hub]=P.at[hub]; P.tw[hub]={n:name, u:u, top:top0, top0:top0}; P.lm[name]={unit:u, floors:v.floors||null};
      if(cl){ P.b.push([cl]); P.at[hub]=(P.b.length-1)+'.0'; }
      var fl=floorsOf(hub), nums=spreadNo(fl, Math.max(top0,fl.length+1), P.fx), top=Math.max(top0, fl.length+1);
      fl.forEach(function(f){ P.fn[f]=nums[f]; top=Math.max(top, nums[f]); }); P.tw[hub].top=top; P.tw[hub].top0=Math.min(top0, top); } }
  P._dirty=1; P._lmDirty=1;
}
function lotUsed(key){ var u=false; Object.keys(P.at).forEach(function(id){ if(P.at[id]===key && !P.par[id]) u=true; }); return u; }
/* the numbers of a tower's floors that come from the spread, written down (so adding, removing or renumbering a floor leaves the others where they are) */
function freezeOps(h, ex){ var ops=[]; (P.fl[h]||[]).forEach(function(f){ if(f!==ex && P.fx[f]==null && P.fn[f]!=null) ops.push(['p|'+f+'|fno', P.fn[f]]); }); return ops; }
function nextNo(h){ var t=P.tw[h], used={}, mx=1; (P.fl[h]||[]).forEach(function(f){ var n=P.fn[f]; used[n]=1; if(n>mx) mx=n; });
  if(mx+1<=t.top) return mx+1; for(var n=t.top;n>=2;n--) if(!used[n]) return n; return null; }
function pickLots(ids, x, y){ var ex={}, ops=[]; ids.forEach(function(id){ var k=freeLot(x,y,null,ex); if(k){ ex[k]=1; ops.push(['p|'+id+'|lot', k]); } }); return ops; }
function houseUnits(name){ var E=window._altoEdit; if(!E) return []; return E.units().filter(function(u){ return (P.units[u.i]||[]).filter(function(id){ return !P.out[id]; }).length && !towerOfUnit(u.i); }); }
function moveUnitOut(name){
  var h=towerHub(name), l=lmOf(name), E=window._altoEdit; if(!h || !l || !E) return;
  var ids=[h].concat(Object.keys(P.tk).filter(function(id){ return P.par[id]===h; }));
  var list=[['pu|'+name, null]].concat(pickLots(ids, l.x, l.y));
  if(chg(list)) E.toast('Moved the unit out of '+name+' — ⌘Z takes it back.'); }
function houseForm(name, at, withFloor){
  var E=window._altoEdit; if(!E || !E.editing()) return; var l=lmOf(name); if(!l) return;
  var h=towerHub(name); if(h){ if(withFloor) addForm(null, h, at); return; }
  var us=houseUnits(name); if(!us.length){ E.toast('Every section with a building already has a tower — or has none yet.'); return; }
  var def=addUnitAt([l.x,l.y]); if(!us.some(function(u){ return u.i===def; })) def=us[0].i;
  var top0=(P.lmtop||{})[name]||30, top=top0;
  var fields=[{k:'unit', l:'Which unit does this building house?', type:'select', val:String(def), hint:'Its buildings will become floors of '+name+', numbered up the tower from 2 to '+top+'.',
    opts:us.map(function(u){ return [String(u.i), (u.i+1)+'. '+u.name+' ('+(P.units[u.i]||[]).length+')']; })}];
  fields.push({k:'floors', l:'Real floors of the building (optional)', ph:'default '+top, hint:'The top of the tower: floors are numbered from 2 up to it.'});
  if(withFloor) fields.push({k:'title', l:'New floor — title', req:1, ph:'What is on this floor'}, {k:'desc', l:'Short description (optional)', type:'area'}, {k:'tag', l:'Tag (optional)', ph:'e.g. RULE'});
  E.ask(at, withFloor?'Add a floor to '+name:'House a unit in '+name, fields, withFloor?'House it and add':'House it', function(v){
    var ui=+v.unit, roots=(P.units[ui]||[]).filter(function(id){ return !P.out[id]; }), hub=roots[0]; if(!hub) return;
    var fl0=v.floors?+v.floors:null, top=fl0||top0; var list=[['pu|'+name, {unit:ui, floors:fl0}]];
    if(withFloor){
      var id=E.rid('card-'), uk=(E.units().filter(function(u){ return u.i===ui; })[0]||{}).key, like=TT[hub]; if(uk==null) return;
      /* the numbers the unit's buildings will have as floors (so the new one can take the next) */
      var sim={}, kids={}; Object.keys(P.par).forEach(function(q){ sim[q]=P.par[q]; }); roots.slice(1).forEach(function(r){ sim[r]=hub; });
      ORDER.forEach(function(q){ var pp=sim[q]; if(pp && TT[pp]) (kids[pp]=kids[pp]||[]).push(q); });
      var order=[], st=(kids[hub]||[]).slice().reverse();
      while(st.length){ var f=st.pop(); order.push(f); (kids[f]||[]).slice().reverse().forEach(function(k){ st.push(k); }); }
      var nums=spreadNo(order, Math.max(top, order.length+1), P.fx), mx=1, used={};
      order.forEach(function(f){ used[nums[f]]=1; if(nums[f]>mx) mx=nums[f]; });
      var nn=mx+1<=top?mx+1:null; for(var q=top; nn==null && q>=2; q--) if(!used[q]) nn=q;
      if(nn==null){ E.toast('That tower has no free floor number left.'); return; }
      list.push(['nn|'+id, {p:hub, a:uk, t:v.title, g:v.tag||'', d:v.desc||'', c:(like&&like.color)||'var(--accent)'}], ['pf|'+id, hub], ['p|'+id+'|fno', nn]);
      order.forEach(function(f){ if(P.fx[f]==null) list.push(['p|'+f+'|fno', nums[f]]); });
      if(!chg(list)){ E.toast('That could not be added.'); return; }
      setTimeout(function(){ E.toast('Added floor '+nn+' to '+name+' — ⌘Z takes it back.'); }, 60);
    } else if(chg(list)) E.toast(name+' now houses section '+(ui+1)+' — ⌘Z takes it back.');
  }, function(v){ if(v.floors && (!/^\d+$/.test(v.floors) || +v.floors<2 || +v.floors>250)) return 'Floors: a whole number from 2 to 250.';
    return ''; });
}
/* a floor's number in its tower: its own small form */
function numberForm(id, at){
  var E=window._altoEdit, t=towerOf(id), h=bOf(id); if(!E || !t) return;
  var others=(P.fl[h]||[]).filter(function(f){ return f!==id; }).map(function(f){ return P.fn[f]; }).sort(function(a,b){ return a-b; });
  E.ask(at, 'Floor number of '+num(id)+' '+title(id), [{k:'fno', l:'Real floor number', req:1, val:String(floorNo(id)), hint:'From 2 to '+t.top+'. Taken: '+(others.join(', ')||'none')+'.'}], 'Change', function(v){
    var n=+v.fno; if(n===floorNo(id)) return;
    if(chg([['p|'+id+'|fno', n]].concat(freezeOps(h, id)))) E.toast('Floor '+n+' — ⌘Z takes it back.'); },
    function(v){ var n=+v.fno; if(!/^\d+$/.test(v.fno) || n<2 || n>t.top) return 'A whole number from 2 to '+t.top+'.';
      if(others.indexOf(n)>=0) return 'Floor '+n+' is taken.'; return ''; });
}
function within(a){ var s=[a], i=0; while(i<s.length){ var x=s[i++]; ORDER.forEach(function(id){ if(P.par[id]===x) s.push(id); }); } return s; }
var slot=null;
window.addEventListener('mousedown', function(e){
  if(!palaceOn() || !editing() || e.button!==0 || focused()) return;
  var id=bAt(e.target); if(!id) return;
  if(P.tw && P.tw[id]) return;                       /* a tower stands on its landmark: it is not moved, and nothing is dropped onto it by mistake */
  e.preventDefault(); e.stopImmediatePropagation();
  dragging={id:id, x:e.clientX, y:e.clientY}; moved=false; unhint();
}, true);
window.addEventListener('mousemove', function(e){
  if(!dragging) return;
  if(!moved && Math.hypot(e.clientX-dragging.x, e.clientY-dragging.y)<5) return;
  moved=true; e.preventDefault(); e.stopImmediatePropagation();
  var p=svgPt(svgD, e), id=dragging.id;
  var nd=document.getElementById('node-'+id); if(nd){ nd.style.left=((p[0]+MX)*Z)+'px'; nd.style.top=((p[1]+MY)*Z+WORLD_PAD_TOP)+'px'; }
  /* onto another building: a floor of it; else the nearest free lot */
  var onto=null; (P.units[ACT[id]]||[]).forEach(function(o){ if(o===id || within(id).indexOf(o)>=0 || (P.tw && P.tw[o])) return; var B=lot(P.at[o]); if(!B) return;
    if(Math.abs(p[0]-B[0])<B[2]/2+4 && Math.abs(p[1]-B[1])<B[3]/2+4) onto=o; });
  if(slot) slot.remove(); slot=null; dragging.onto=onto; dragging.key=null;
  if(onto){ var B=lot(P.at[onto]); slot=el('rect',{'class':'pl-slot', x:B[0]-B[2]/2-5, y:B[1]-B[3]/2-5, width:B[2]+10, height:B[3]+10, rx:5, transform:'rotate('+B[4]+' '+B[0]+' '+B[1]+')'},svgD._r);
    hint('<b>Make it a floor of '+esc(num(onto)+' '+title(onto))+'</b><small>Its own floors come with it.</small>'); }
  else { var key=freeLot(p[0], p[1], id), K=lot(key); if(K && Math.hypot(K[0]-p[0],K[1]-p[1])<140){ dragging.key=key;
      slot=el('rect',{'class':'pl-slot', x:K[0]-K[2]/2, y:K[1]-K[3]/2, width:K[2], height:K[3], rx:3, transform:'rotate('+K[4]+' '+K[0]+' '+K[1]+')'},svgD._r); }
    unhint(); }
}, true);
window.addEventListener('mouseup', function(e){
  if(!dragging) return; var d=dragging; dragging=null; if(slot){ slot.remove(); slot=null; } unhint();
  if(!moved) { return; }
  e.preventDefault(); e.stopImmediatePropagation();
  setTimeout(function(){ moved=false; }, 50);
  var ok=false;
  if(d.onto) ok=chg([['pf|'+d.id, d.onto], ['p|'+d.id+'|lot', null]]);
  else if(d.key && d.key!==P.at[d.id]) ok=chg([['p|'+d.id+'|lot', d.key]]);
  if(!ok) window._altoPalaceRefresh();
}, true);

/* ── manual edit mode: add a building on a free lot, or a floor on a building ──
   A free lot shows a faint + under the pointer (and every free lot does while "Add building" is on);
   choosing one opens the glass form. The card is made the way any card is (nn|card-…, with the lot as
   p|card-…|lot, or pf|card-… for a floor), so Save, undo, reload and republish already know it. */
var addMode=false, ghost=null, ghostKey=null, freeLayer=null, addBtn=null, formAt=null;
function lotAt(p){
  var t=taken();
  for(var i=0;i<P.b.length;i++){ var ls=P.b[i]; for(var k=0;k<ls.length;k++){ var L=ls[k], r=Math.max(L[2],L[3]);
    if(Math.abs(p[0]-L[0])>r || Math.abs(p[1]-L[1])>r) continue;
    var a=-L[4]*Math.PI/180, dx=p[0]-L[0], dy=p[1]-L[1], c=Math.cos(a), s=Math.sin(a), rx=dx*c-dy*s, ry=dx*s+dy*c;
    if(Math.abs(rx)<=L[2]/2+4 && Math.abs(ry)<=L[3]/2+4){ var key=i+'.'+k; return {key:key, L:L, by:t[key]||null}; } } }
  return null;
}
function lotRect(L, cls, parent, pad){ pad=pad||0;
  return el('rect',{'class':cls, x:L[0]-L[2]/2-pad, y:L[1]-L[3]/2-pad, width:L[2]+2*pad, height:L[3]+2*pad, rx:3, transform:'rotate('+L[4]+' '+L[0]+' '+L[1]+')'},parent); }
function addLayer(){ if(!svgD) return null; if(!svgD._a || svgD._a.parentNode!==svgD) svgD._a=el('g',{'class':'pl-addlayer'},svgD); return svgD._a; }
function hideGhost(){ if(ghost){ ghost.remove(); ghost=null; } ghostKey=null; }
function showGhost(hit){
  if(ghostKey===hit.key && ghost && ghost.parentNode) return; hideGhost(); if(!addLayer()) return; ghostKey=hit.key;
  var L=hit.L, g=el('g',{'class':'pl-addg'},addLayer()); lotRect(L,'pl-addr',g,2);
  var h=Math.min(L[2],L[3])*.3+2; el('path',{'class':'pl-addp', d:'M'+(L[0]-h)+' '+L[1]+'L'+(L[0]+h)+' '+L[1]+'M'+L[0]+' '+(L[1]-h)+'L'+L[0]+' '+(L[1]+h)},g); ghost=g; }
function addUnitAt(L){
  var best=null, bd=1e18;
  (P.d||[]).forEach(function(d){ var b=d.box; if(best==null && L[0]>=b[0]&&L[0]<=b[2]&&L[1]>=b[1]&&L[1]<=b[3]) best=d.u; });
  if(best==null) (P.d||[]).forEach(function(d){ var c=districtCentre(d), dd=Math.hypot(c[0]-L[0],c[1]-L[1]); if(dd<bd){ bd=dd; best=d.u; } });
  return best==null?0:best;
}
function anchorAt(x,y){ return {getBoundingClientRect:function(){ return {left:x, right:x, top:y, bottom:y}; }}; }
/* the form: a new building on lot `key`, or (floorOf) a floor of that building */
function addForm(key, floorOf, at){
  var E=window._altoEdit; if(!E || !E.editing()) return;
  var L=key?lot(key):null; if(!floorOf && (!L || taken()[key])){ E.toast('That lot is taken — pick an empty one.'); return; }
  var us=E.units(), def=floorOf?ACT[floorOf]:addUnitAt(L);
  var fields=[{k:'title',l:'Title',req:1,ph:floorOf?'What is on this floor':'What stands here'},
              {k:'desc',l:'Short description (optional)',type:'area'}];
  if(!floorOf) fields.push({k:'unit',l:'Section',type:'select',val:String(def),
    opts:us.map(function(u){ var n=(P.units[u.i]||[]).length; return [String(u.i), (u.i+1)+'. '+u.name+' ('+n+')']; })});
  fields.push({k:'tag',l:'Tag (optional)',ph:'e.g. RULE'});
  var twr=floorOf&&P.tw&&P.tw[floorOf]?P.tw[floorOf]:null, taken_=twr?(P.fl[floorOf]||[]).map(function(f){ return P.fn[f]; }):[], nxt=twr?nextNo(floorOf):null;
  if(twr) fields.splice(2,0,{k:'fno', l:'Floor number (optional)', ph:nxt!=null?'next: '+nxt:'none free', hint:'The tower has floors 2 to '+twr.top+'. Taken: '+(taken_.slice().sort(function(a,b){ return a-b; }).join(', ')||'none')+'.'});
  var pend=null; if(L && !floorOf && addLayer()){ pend=lotRect(L,'pl-addr pl-addpend',addLayer(),2); }
  var gone=function(){ if(pend){ pend.remove(); pend=null; } };
  var head=floorOf?'Add a floor to '+num(floorOf)+' '+title(floorOf):'Add a building';
  E.ask(at, head, fields, 'Add', function(v){
    gone();
    var ui=floorOf?ACT[floorOf]:(+v.unit), id=E.rid('card-'), uk=(us.filter(function(u){ return u.i===ui; })[0]||{}).key;
    if(uk==null) return;
    var fno=twr?(v.fno?+v.fno:nxt):null; if(twr && fno==null){ E.toast('That tower has no free floor number left.'); return; }
    var like=(P.units[ui]||[]).map(function(i){ return TT[i]; })[0];
    var spec={p:floorOf||'', a:uk, t:v.title, g:v.tag||'', d:v.desc||'', c:(like&&like.color)||'var(--accent)'};
    var list=[['nn|'+id, spec]];
    if(floorOf) list.push(['pf|'+id, floorOf]); else list.push(['p|'+id+'|lot', key]);
    if(twr){ list.push(['p|'+id+'|fno', fno]); freezeOps(floorOf).forEach(function(o){ list.push(o); }); }
    if(!chg(list)){ E.toast('That could not be added.'); return; }
    addMode=false; syncAdd();
    setTimeout(function(){ E.toast('Added '+num(id)+' '+v.title+' — ⌘Z takes it back.'); }, 60);
  }, twr?function(v){ if(!v.fno) return nxt==null?'No floor number is free — type one.':'';
    var n=+v.fno; if(!/^\d+$/.test(v.fno) || n<2 || n>twr.top) return 'A whole number from 2 to '+twr.top+'.';
    return taken_.indexOf(n)>=0?'Floor '+n+' is taken.':''; }:null);
  var fm=document.getElementById('aed-form');       // the marker goes with the form, however it closes
  if(fm){ var mo=new MutationObserver(function(){ if(!fm.classList.contains('show')){ gone(); mo.disconnect(); } }); mo.observe(fm,{attributes:true,attributeFilter:['class']}); }
}
window._altoPalaceAddFloor=function(id, btn){
  var b=bOf(id), r=btn&&btn.getBoundingClientRect?btn.getBoundingClientRect():{left:innerWidth/2,bottom:innerHeight/3,top:innerHeight/3,right:innerWidth/2};
  addForm(null, b, anchorAt(r.left, r.bottom)); };
function syncAdd(){
  var on=palaceOn() && editing();
  if(freeLayer){ freeLayer.remove(); freeLayer=null; }
  if(svgD) svgD.classList.toggle('pl-adding', !!(addMode&&on));
  if(addMode && on && addLayer()){
    freeLayer=el('g',{'class':'pl-addfree'},addLayer()); var t=taken();
    /* the empty lots in and around the neighbourhoods (the whole city has thousands) */
    var D=(P.d||[]).map(function(d){ return d.box; });
    P.b.forEach(function(ls,i){ ls.forEach(function(L,k){ if(t[i+'.'+k]) return;
      if(D.some(function(b){ return L[0]>=b[0]-50 && L[0]<=b[2]+50 && L[1]>=b[1]-50 && L[1]<=b[3]+50; })) lotRect(L,'pl-addr pl-addr0',freeLayer,1); }); }); }
  if(!on) hideGhost();
  var bar=document.getElementById('alto-edit-exit');
  if(bar && on && !bar.querySelector('.ee-addb')){
    addBtn=document.createElement('button'); addBtn.type='button'; addBtn.className='ee-h ee-addb'; addBtn.textContent='+ Add building';
    addBtn.title='Then click an empty lot'; var done=bar.querySelector('.ee-done'); bar.insertBefore(addBtn, done);
    addBtn.addEventListener('click', function(e){ e.stopPropagation(); addMode=!addMode; syncAdd(); }); }
  var ab=bar&&bar.querySelector('.ee-addb'); if(ab){ ab.style.display=on?'':'none'; ab.classList.toggle('on', !!(addMode&&on)); }
  if(addMode&&on){ var E=window._altoEdit; if(E) E.toast('Click an empty lot to put a building there · Esc to cancel'); }
}
new MutationObserver(function(){ if(!editing()) addMode=false; syncAdd(); }).observe(de,{attributes:true,attributeFilter:['class']});
window.addEventListener('mousemove', function(e){
  if(dragging || !palaceOn() || !editing() || focused() || !svgD){ if(ghost) hideGhost(); return; }
  if(!e.target.closest || !e.target.closest('#canvas') || e.target.closest('.node,.aed-cc,button') || bAt(e.target)){ hideGhost(); return; }
  var hit=lotAt(svgPt(svgD,e)); if(hit && !hit.by) showGhost(hit); else hideGhost();
});
window.addEventListener('click', function(e){
  if(!palaceOn() || !editing() || focused() || moved || !svgD || e.button!==0) return;
  var t=e.target; if(!t.closest || !t.closest('#canvas') || t.closest('.node,.aed-cc,button,input,select,textarea,a') || bAt(t)) return;
  var hit=lotAt(svgPt(svgD,e)); if(!hit) return;
  if(hit.by){ if(addMode){ e.stopImmediatePropagation(); var E=window._altoEdit; if(E) E.toast('That lot is taken — pick an empty one.'); } return; }
  e.preventDefault(); e.stopImmediatePropagation(); hideGhost(); formAt=hit.key; addForm(hit.key, null, anchorAt(e.clientX+14, e.clientY+14));
}, true);
window.addEventListener('keydown', function(e){ if(e.key==='Escape' && addMode){ addMode=false; syncAdd(); } }, true);

/* ── manual edit mode: a landmark building offers "Add a floor" (and houses a unit, or moves it out) ──
   Hover a landmark — or a tower's own chip — and a small glass bar straddles its lower edge (so the pointer never has to cross a gap),
   it waits 350 ms after the pointer leaves both, a click on the landmark pins it open (until Esc, a click away or another landmark),
   keyboard focus and a touch tap reach it too, and it follows the landmark as the map pans and zooms, flipping inside the viewport
   edge. A landmark with no unit asks which unit it houses first; a tower adds a floor of its unit, with the next real floor number
   or the one typed. */
var lmBar=null, lmFor=null, lmT=null, lmPin=false, lmRaf=0, lmKey='';
function lmBarEl(){
  if(lmBar && lmBar.parentNode) return lmBar;
  lmBar=document.createElement('div'); lmBar.id='pl-lmbar'; lmBar.setAttribute('role','toolbar'); lmBar.setAttribute('aria-label','Landmark building');
  ['mousedown','dblclick'].forEach(function(n){ lmBar.addEventListener(n, function(e){ e.stopPropagation(); }); });
  lmBar.addEventListener('mouseenter', function(){ clearTimeout(lmT); });
  lmBar.addEventListener('mouseleave', function(){ lmHideSoon(); });
  lmBar.addEventListener('click', function(e){ e.stopPropagation(); var b=e.target.closest('button'); if(!b || !lmFor) return;
    var r=b.getBoundingClientRect(), at=anchorAt(r.left, r.bottom+6), name=lmFor, a=b.getAttribute('data-a'); lmHide();
    if(a==='add') houseForm(name, at, true); else if(a==='house') houseForm(name, at, false); else if(a==='out') moveUnitOut(name); });
  document.body.appendChild(lmBar); return lmBar; }
function lmHide(){ clearTimeout(lmT); lmPin=false; lmFor=null; lmKey=''; if(lmRaf){ cancelAnimationFrame(lmRaf); lmRaf=0; } if(lmBar) lmBar.classList.remove('show'); }
function lmHideSoon(){ if(lmPin) return; clearTimeout(lmT); lmT=setTimeout(function(){ if(!lmPin) lmHide(); }, 350); }
function lmG(name){ return svgD?[].filter.call(svgD.querySelectorAll('.pl-lmb'), function(q){ return q.getAttribute('data-name')===name; })[0]||null:null; }
function lmRect(name){                                                           /* the landmark's block on screen (what the pointer test uses too) */
  var l=lmOf(name), m=svgD && svgD.getScreenCTM && svgD.getScreenCTM();
  if(l && m && svgD.createSVGPoint){ var b=l.box, p=svgD.createSVGPoint(), xs=[], ys=[];
    [[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]].forEach(function(q){ q=lmTurn(l, q, 1); p.x=q[0]; p.y=q[1]; var s=p.matrixTransform(m); xs.push(s.x); ys.push(s.y); });
    return {left:Math.min.apply(null,xs), right:Math.max.apply(null,xs), top:Math.min.apply(null,ys), bottom:Math.max.apply(null,ys)}; }
  var g=lmG(name); return g?g.getBoundingClientRect():null; }
function lmPlace(){
  if(!lmFor || !lmBar) return; var r=lmRect(lmFor); if(!r) return;
  /* all in window px (what getScreenCTM and getBoundingClientRect give); the bar's left/top are CSS px, which the page's CSS
     zoom scales (html{zoom:.8–1}, in Chrome and Safari alike) — so k, the window px per CSS px, measured, converts back */
  var br=lmBar.getBoundingClientRect(), k=(lmBar.offsetWidth && br.width)?br.width/lmBar.offsetWidth:1;
  var bw=br.width||250, bh=br.height||34, vw=innerWidth, vh=innerHeight;
  var off=r.right<0 || r.left>vw || r.bottom<0 || r.top>vh;
  var x=Math.max(8, Math.min(vw-bw-8, (r.left+r.right)/2-bw/2));
  var y=r.bottom-bh*.55;                                                           /* straddling the card's lower edge */
  if(y+bh>vh-8) y=r.top-bh*.45;                                                    /* no room below: its upper edge */
  if(y<8) y=r.bottom-bh-6;                                                         /* none there either: inside the card's foot */
  y=Math.max(8, Math.min(vh-bh-8, y));
  var key=Math.round(x)+','+Math.round(y)+','+off;
  if(key!==lmKey){ lmKey=key; lmBar.style.left=(x/k).toFixed(1)+'px'; lmBar.style.top=(y/k).toFixed(1)+'px'; lmBar.style.visibility=off?'hidden':''; } }
function lmLoop(){ if(!lmFor){ lmRaf=0; return; } if(!palaceOn() || !editing() || focused()){ lmHide(); return; } lmPlace(); lmRaf=requestAnimationFrame(lmLoop); }
function lmShow(name){
  clearTimeout(lmT); var bar=lmBarEl(); if(lmFor===name && bar.classList.contains('show')) return; lmFor=name; lmKey='';
  var h=towerHub(name);
  bar.innerHTML='<button type="button" data-a="add" title="'+(h?'A new floor of the tower':'Choose the unit this building houses, then add a floor')+'">+ Add a floor</button>'
    +(h?'<button type="button" data-a="out" title="Its buildings go back to their own lots">Move the unit out</button>':'<button type="button" data-a="house" title="Its buildings become the floors of this one">House a unit here</button>');
  bar.classList.add('show'); lmPlace(); if(!lmRaf) lmRaf=requestAnimationFrame(lmLoop); }
function lmNameAt(t, e){                                                          /* the landmark under the pointer: a tower's chip, or its block (whatever layer is on top there) */
  var nd=t.closest('.node'); if(nd){ var id=nd.id.replace(/^node-/,''); return P.tw && P.tw[id]?P.tw[id].n:null; }
  var p=svgPt(svgD,e), hit=null, ha=1e18, cur=null;
  (M.landmarks||[]).forEach(function(l){ var b=l.box, q=b?lmLocal(l, p):p; if(b && q[0]>=b[0] && q[0]<=b[2] && q[1]>=b[1] && q[1]<=b[3]){ if(l.n===lmFor) cur=l.n; var a=(b[2]-b[0])*(b[3]-b[1]); if(a<ha){ ha=a; hit=l.n; } } });
  return cur||hit; }
function lmTab(){ if(svgD) [].forEach.call(svgD.querySelectorAll('.pl-lmb'), function(g){ if(editing()) g.setAttribute('tabindex','0'); else g.removeAttribute('tabindex'); }); }
document.addEventListener('mousemove', function(e){
  if(!palaceOn() || !editing() || dragging || focused() || !svgD){ if(lmFor) lmHide(); return; }
  if(lmPin) return;
  var t=e.target; if(!t.closest || t.closest('#pl-lmbar,#aed-form,.aed-cc')) return;
  if(!t.closest('#canvas')){ if(lmFor) lmHideSoon(); return; }
  var name=lmNameAt(t, e);
  if(name && lmG(name)) lmShow(name); else if(lmFor) lmHideSoon();
});
document.addEventListener('click', function(e){                                    /* a click (or a touch tap) on a landmark pins the bar open */
  if(!palaceOn() || !editing() || !svgD){ if(lmFor) lmHide(); return; }
  var t=e.target; if(!t.closest || t.closest('#pl-lmbar,#aed-form,.aed-cc')) return;
  var name=t.closest('#canvas')?lmNameAt(t, e):null;
  if(name && lmG(name)){ lmPin=true; lmShow(name); var g=lmG(name); if(g.classList.contains('has-page')) e.stopPropagation(); }
  else if(lmFor) lmHide();
}, true);
window.addEventListener('keydown', function(e){
  if(e.key==='Escape' && lmFor){ lmHide(); return; }
  if(e.key==='Tab' && editing()) lmTab();
  if((e.key==='Enter' || e.key===' ' || e.key==='ArrowDown') && lmFor && e.target.closest && e.target.closest('.pl-lmb') && lmBar){
    var b=lmBar.querySelector('button'); if(b){ e.preventDefault(); b.focus(); } }
}, true);
document.addEventListener('focusin', function(e){                                   /* keyboard focus on a landmark opens (and pins) its bar */
  if(!palaceOn() || !editing() || !svgD || !e.target.closest) return;
  var g=e.target.closest('.pl-lmb'); if(!g || !svgD.contains(g) || !(e.target.matches && e.target.matches(':focus-visible'))) return;
  lmPin=true; lmShow(g.getAttribute('data-name')); });
document.addEventListener('focusout', function(e){
  var to=e.relatedTarget; if(lmFor && lmPin && to && to.closest && !to.closest('#pl-lmbar,.pl-lmb')) lmHide(); });
new MutationObserver(function(){ if(!editing()) lmHide(); lmTab(); }).observe(de,{attributes:true,attributeFilter:['class']});
""" + DIR_JS + MOBILE_JS + PAN_JS + r"""
})();
"""
