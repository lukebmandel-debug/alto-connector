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
import gzip
import json
import math
import re

from .brief import BriefError
from .key_toggle import KEY_CSS, KEY_JS
from .palace_landmarks import LANDMARK_CSS, LANDMARK_JS
from .palace_transit_js import TRANSIT_CSS, TRANSIT_JS
from .sanitize import js_json
from . import palace_place as pp

PALACE_KEYS = {"place", "area", "bbox", "districts", "majors", "landmarks", "diagonals", "lines",
               "buildings", "scale", "data_z", "made"}


# ── the packed city ────────────────────────────────────────────────────────
def pack(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, 9, mtime=0)).decode("ascii")


def unpack(z: str) -> dict:
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
    if not pal.get("data_z"):
        warnings.append("palace: no city yet — run set_up_palace(timeline_id, place, …) "
                        "before building; the page has nothing to draw until then")
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
    bad = [k for k, v in (b.placement or {}).items() if set(v) - {"lot"}]
    if bad:
        raise BriefError(f"placement: a Mind Palace places buildings by lot only ({', '.join(bad[:5])})")


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


def numbers(units, floors) -> dict:
    """"3.4" for the 4th building of section 3; "3.4-2" for its 2nd floor up."""
    num = {}
    for a, ids in enumerate(units):
        for k, bid in enumerate(ids):
            num[bid] = f"{a + 1}.{k + 1}"
            for j, f in enumerate(floors.get(bid, [])):
                num[f] = f"{a + 1}.{k + 1}-{j + 1}"
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


def palace_data(b, nodes) -> str:
    """window._ALTO_PALACE — the city, where each building stands, its floors."""
    pal = b.palace or {}
    data = unpack(pal["data_z"]) if pal.get("data_z") else None
    units, floors, of = structure(b, nodes)
    num = numbers(units, floors)
    par = {n.id: n.parent for n in nodes if n.parent}
    if not data:
        return ("\nwindow._ALTO_PALACE=" + js_json({"none": 1, "fl": floors, "of": of, "num": num,
                                                    "par": par}, separators=(",", ":")) + ";")
    m, blocks = data["map"], data["blocks"]
    fixed = {k: v["lot"] for k, v in (b.placement or {}).items() if isinstance(v, dict) and v.get("lot")}
    districts = [d for d in pal.get("districts") or []]
    at = pp.place(m, blocks, units, districts, fixed)
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
    mp["streets"] = [{**s, "n": short(s.get("n") or "")} for s in m.get("streets", [])]
    mp["majors"] = [short(s) for s in m.get("majors", [])]
    mp["cols"] = [short(s) for s in m.get("cols", [])]      # the grid's streets by column / row, to tell a major from a minor one
    mp["rows"] = [short(s) for s in m.get("rows", [])]
    mp["top"] = sorted({short(s.get("n")) for s in m.get("streets", [])
                        if s.get("n") and s.get("k", 9) <= 1 and short(s.get("n")) in mp["majors"]})
    out = {"m": mp, "b": [bl["lots"] for bl in blocks], "at": at, "fl": floors, "of": of,
           "par": par, "num": num, "near": near, "d": dist, "place": pal.get("place") or m.get("place") or ""}
    return "\nwindow._ALTO_PALACE=" + js_json(out, separators=(",", ":")) + ";"


def set_up(place: str, bbox, districts=None, majors=None, landmarks=None, scale: float = 1.0,
           cache_dir=None, diagonals=None, lines=None, buildings=None) -> dict:
    """lines: hypothetical railways [{name, color?, stops: [names]}]; buildings:
    the landmark buildings [{name, page?, label?}] (palace_grid.grid)."""
    """Fetch and prepare a city: the brief.palace dict to store (data_z packed)."""
    from .. import palace_map as pm
    raw = pm.fetch_osm(tuple(bbox), cache_dir=cache_dir, landmarks=landmarks or None)
    m = pm.build_map(raw, tuple(bbox), place=place, scale=scale, majors=majors or None,
                     landmarks=landmarks or None)
    # a landmark found both as an outline and as a point (a station node beside
    # its building) is named once, by its outline
    lms = m.get("landmarks", [])
    m["landmarks"] = [l for l in lms if l.get("r") or not any(
        o.get("r") and math.hypot(o["x"] - l["x"], o["y"] - l["y"]) < 260 for o in lms)]
    # the drawing: an even grid of the city's streets, the river and a few
    # diagonals the only exceptions (palace_grid)
    from .palace_grid import grid
    m = grid(m, majors=majors or (), diagonals=diagonals or (), lines=lines or (), landmarks=buildings or ())
    blocks = m.pop("blocks")
    return {"place": place, "bbox": list(bbox), "districts": districts or [],
            "majors": majors or [], "landmarks": landmarks or [], "diagonals": diagonals or [],
            "lines": lines or [], "buildings": buildings or [], "scale": scale,
            "data_z": pack({"map": m, "blocks": blocks})}


def summary(pal: dict) -> dict:
    """What get_timeline shows of the city instead of the packed data."""
    if not pal:
        return pal
    out = {k: v for k, v in pal.items() if k != "data_z"}
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
    --pal-park:rgba(255,255,255,.20);--pal-lm:rgba(255,255,255,.38);--pal-text:#2c2f3d;--pal-halo:rgba(255,255,255,.88);--pal-trail:#4f9a4a;--pal-ground:238,238,242;}
  html.dark{--pal-river:#3f78b4;--pal-rv-rim:rgba(255,255,255,.16);--pal-casing:rgba(18,22,34,.55);--pal-br-edge:rgba(214,222,244,.62);--pal-br-pier:rgba(214,222,244,.42);--pal-br-text:#dfe6fa;--pal-rv-lite:#9fcaf2;--pal-rv-sheen:rgba(255,255,255,.34);--pal-glass:rgba(22,24,34,.42);--pal-glass-edge:rgba(255,255,255,.16);--pal-water:rgba(38,64,100,.92);--pal-water-edge:rgba(255,255,255,.28);
    --pal-park:rgba(255,255,255,.06);--pal-lm:rgba(255,255,255,.10);--pal-text:#e4e2ec;--pal-halo:rgba(14,16,24,.88);--pal-trail:#6fbf68;--pal-ground:28,30,40;}
  html.alto-palace:not(.mobile) #world{margin:0 !important;translate:var(--ppan-x,0px) var(--ppan-y,0px);}
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
  .pal-svg .pl-lmb.has-page{cursor:pointer;}
  .pal-svg .pl-lmb .lm-shadow{fill:rgba(20,26,55,.16);}
  .pal-svg .pl-lmb .lm-card{fill:rgba(255,255,255,.92);stroke-width:2.5;vector-effect:non-scaling-stroke;}
  html.dark .pal-svg .pl-lmb .lm-card{fill:rgba(34,36,48,.94);}
  .pal-svg .pl-lmb.has-page:hover .lm-card{stroke-width:4;}
  .pal-svg .pl-lmb .lm-name{font-weight:800;letter-spacing:.01em;stroke:none;}
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
  .pal-svg .pl-stn{transform:translate(var(--sx),var(--sy)) scale(var(--tw,1));}
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
  .pal-svg .pl-stt{transform:translate(calc(var(--tw,1) * 13px),calc(var(--tw,1) * -9px));}
  .pal-svg .pl-stt.hub{transform:translate(calc(var(--tw,1) * 20px),calc(var(--tw,1) * -15px));}
  .pal-svg .pl-dtint{fill-opacity:0;pointer-events:all;}
  .pal-svg .pl-dist{font-size:calc(26px / var(--pz,1));font-weight:700;letter-spacing:.2em;text-transform:uppercase;
    stroke-width:calc(7px / var(--pz,1));pointer-events:all;cursor:pointer;}
  .pal-svg.far .pl-dist{font-size:calc(30px / var(--pz,1));}
  .pal-svg .pl-credit{font-size:calc(10px / var(--pz,1));opacity:.7;stroke-width:calc(2.5px / var(--pz,1));}
  .pal-svg .pl-bld{pointer-events:all;cursor:pointer;}
  .pal-svg .pl-bld .b-card{fill:rgba(255,255,255,.9);stroke-width:1.4;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-bld .b-floor{fill:rgba(255,255,255,.75);stroke-width:1;stroke-opacity:.6;vector-effect:non-scaling-stroke;}
  html.dark .pal-svg .pl-bld .b-card{fill:rgba(36,38,50,.92);}
  html.dark .pal-svg .pl-bld .b-floor{fill:rgba(36,38,50,.75);}
  .pal-svg .pl-bld .b-num{font-weight:800;stroke:none;}
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
  .pal-svg .pl-addp{fill:none;stroke:var(--accent);stroke-width:2;stroke-linecap:round;vector-effect:non-scaling-stroke;pointer-events:none;}
  .pal-svg.pl-adding{cursor:copy;}
  #alto-edit-exit .ee-addb{width:auto;padding:0 10px;line-height:1.2;font:inherit;font-size:12.5px;white-space:nowrap;}
  #alto-edit-exit .ee-addb.on{background:var(--accent);color:#fff;}
  .pal-svg .pl-slot{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-dasharray:5 4;vector-effect:non-scaling-stroke;}
  @keyframes pal-flow{to{stroke-dashoffset:-22;}}
  @media (prefers-reduced-motion: reduce){.pal-svg .pl-route-sh{animation:none;}}
  .pal-svg.far .pl-lmt,.pal-svg.far .pl-chip,.pal-svg.far .pl-stt:not(.hub),.pal-svg.far .pl-ring:not(.hub),
  .pal-svg.far .pl-st:not(.top),.pal-svg.far .pl-st:not(.r0){display:none;}
  .pal-svg.mid .pl-st.minor{display:none;}
  /* on the board a building IS its card: the size of its lot, turned to its street grid,
     its number on it, its floors stacked behind it; enlarged it is the ordinary card */
  html.alto-palace #world .node{z-index:3;}
  html.alto-palace #world .node.pal-floor{display:none !important;}
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card{width:var(--pw,40px) !important;height:var(--ph,26px) !important;
    min-width:0 !important;max-width:none !important;min-height:0 !important;padding:0 !important;border-radius:5px !important;
    display:flex !important;align-items:center;justify-content:center;overflow:hidden !important;rotate:var(--pr,0deg);
    border:1.5px solid color-mix(in srgb,var(--pc,#888) 70%,transparent) !important;border-top:3px solid var(--pc,#888) !important;
    box-shadow:var(--pfl,0 0 0 transparent),0 3px 10px rgba(20,26,55,.18) !important;}
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card > *:not(.node-order){display:none !important;}
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-order{position:static !important;display:block !important;margin:0 !important;
    font-size:var(--pf,11px) !important;line-height:1.1 !important;font-weight:800 !important;letter-spacing:.01em;color:var(--text) !important;
    opacity:1 !important;white-space:nowrap;transform:none !important;rotate:calc(-1 * var(--pr,0deg));}
  html.alto-palace:not(.mobile) #world .node.pal-hot:not(.focused) .node-card{outline:3px solid var(--pc,#888);outline-offset:2px;}
  html.alto-palace:not(.mobile) #world .node.pal-dim:not(.focused){opacity:.3;}
  #canvas.focus-mode .node.pal-floor{display:none !important;}
  /* pointing is quiet: no box follows the cursor. A building under the pointer (or focused) lifts with a soft glow and its
     chip widens in place into a pill with its number and title; a street / neighbourhood name just brightens; the unit a
     neighbourhood holds comes in the docked card (#pal-dock), pinned bottom centre until dismissed. */
  html.alto-palace:not(.mobile) #world .node.pal-lab:not(.focused),html.alto-palace:not(.mobile) #world .node.pal-dest:not(.focused){z-index:9;}
  html.alto-palace:not(.mobile) #world .node.pal-lab:not(.focused) .node-card,
  html.alto-palace:not(.mobile) #world .node.pal-dest:not(.focused) .node-card,
  html.alto-palace:not(.mobile) #world .node:not(.focused) .node-card:focus-visible{
    position:absolute !important;left:calc(var(--pw,40px) / 2);top:calc(var(--ph,26px) / 2);translate:-50% calc(-50% - 2px);rotate:0deg !important;
    width:max-content !important;height:auto !important;min-width:var(--pw,40px) !important;min-height:var(--ph,26px) !important;max-width:270px !important;
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
  .pal-svg .pl-dist{transition:filter .15s;}
  .pal-svg .pl-dist:hover,.pal-svg .pl-dist.pal-lit{filter:brightness(1.22) saturate(1.25) drop-shadow(0 0 calc(5px / var(--pz,1)) var(--pal-halo));}
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
  #pal-mmap{position:fixed;left:0;right:0;bottom:0;z-index:400;display:none;background:var(--page-grad,var(--bg));background-attachment:fixed;}
  #pal-mmap.on{display:block;}
  html.alto-bg-map #pal-mmap{background:var(--alto-bg);background-attachment:scroll;}   /* the map ground chosen for this city (palace_backgrounds.py) */
  #pal-mmap .pm-scroll{position:absolute;inset:0;overflow:auto;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;}
  /* the phone's map page wears the same glass as the desktop's zoom row: a round close, a grouped pill (closer over farther), the whole city */
  #pal-mmap .pm-close,#pal-mmap .pm-pill,#pal-mmap .pm-city{background:var(--card-glass-bg,var(--surface));color:var(--muted);border:1px solid var(--card-glass-border,var(--border));
    -webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);box-shadow:0 10px 26px var(--node-rest-shadow),inset 0 0 0 .5px var(--card-glass-rim);}
  #pal-mmap .pm-close{position:absolute;right:12px;top:10px;z-index:3;width:44px;height:44px;border-radius:50%;padding:0;display:flex;align-items:center;justify-content:center;}
  #pal-mmap .pm-zoom{position:absolute;right:12px;bottom:calc(20px + env(safe-area-inset-bottom,0px));z-index:3;display:flex;flex-direction:column;align-items:center;gap:12px;}
  #pal-mmap .pm-pill{display:flex;flex-direction:column;width:44px;border-radius:22px;}
  #pal-mmap .pm-zoom button{display:flex;align-items:center;justify-content:center;padding:0;margin:0;border:0;background:none;color:inherit;-webkit-tap-highlight-color:transparent;}
  #pal-mmap .pm-pill button{width:44px;height:48px;}
  #pal-mmap .pm-pill button:first-child{border-radius:22px 22px 0 0;}
  #pal-mmap .pm-pill button:last-child{border-radius:0 0 22px 22px;}
  #pal-mmap .pm-div{height:1px;margin:0 10px;background:color-mix(in srgb,var(--muted) 45%,transparent);}
  #pal-mmap .pm-city{width:44px;height:44px;border-radius:50%;padding:0;}
  #pal-mmap .pm-zoom button:active,#pal-mmap .pm-close:active{color:var(--text);background:color-mix(in srgb,var(--text) 10%,transparent);}
  #pal-mmap svg.pm-ic{display:block;}
  #pal-mmap .pm-card{position:absolute;left:12px;right:68px;bottom:calc(20px + env(safe-area-inset-bottom,0px));z-index:3;display:none;
    padding:10px 12px;border-radius:14px;background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 8px 24px rgba(0,0,0,.25);font-size:13px;}
  #pal-mmap .pm-card.on{display:block;}
  #pal-mmap .pm-card b{display:block;font-size:14px;}
  #pal-mmap .pm-card small{display:block;color:var(--muted);margin-top:2px;}
  #pal-mmap .pm-card button{margin-top:8px;font:inherit;font-weight:700;padding:7px 14px;border-radius:9px;border:0;background:var(--accent);color:#fff;}
  #pal-mmap svg{display:block;}
  /* ═══ INTERACTION (rise · routes · elevator): delimited block ═══ */
  /* an enlarged building's card stands ABOVE it; the building stays, with a notch pointing down onto it */
  html.alto-palace:not(.mobile) #world .node .pal-ghost,html.alto-palace:not(.mobile) #world .node .pal-tail{display:none;}
  html.alto-palace:not(.mobile) #world .alto-fshadow{display:none !important;}
  html.alto-palace:not(.mobile) #world .node.focused{pointer-events:none;}
  html.alto-palace:not(.mobile) #world .node.focused .node-card{pointer-events:auto;top:var(--rt,0px);left:var(--rl,0px);
    box-shadow:0 26px 60px var(--node-hover-shadow),0 2px 10px rgba(20,26,55,.10) !important;}
  html.alto-palace:not(.mobile) #world .node.focused .pal-ghost{display:flex;position:absolute;left:50%;top:50%;width:var(--pw,40px);height:var(--ph,26px);
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
""" + LANDMARK_CSS + TRANSIT_CSS


PALACE_JS = KEY_JS + LANDMARK_JS + TRANSIT_JS + r"""
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
  var nm={}; units.forEach(function(ids,a){ ids.forEach(function(b,k){ nm[b]=(a+1)+'.'+(k+1); (fl[b]||[]).forEach(function(f,j){ nm[f]=(a+1)+'.'+(k+1)+'-'+(j+1); }); }); });
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
function freeLot(x,y,skip){ var t=taken(), best=null, bd=1e18;
  P.b.forEach(function(ls,i){ ls.forEach(function(L,k){ var key=i+'.'+k; if(t[key] && t[key]!==skip) return;
    var d=(L[0]-x)*(L[0]-x)+(L[1]-y)*(L[1]-y); if(d<bd){ bd=d; best=key; } }); });
  return best; }
P.par=P.par||{}; P.par0=JSON.parse(JSON.stringify(P.par)); restructure();

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
window._palTr.init({M:M, P:P, graph:graph, nearest:nearest, entrance:entrance, lot:lot, bOf:bOf, isB:isB, order:function(){ return ORDER; }, flyMap:function(x,y,z){ flyMap(x,y,z); },
  Z:function(){ return Z; }, svg:function(){ return svgD; }, palaceOn:function(){ return palaceOn(); }, el:el, pts:pts, rp:rp, tube:tube, tubeCol:tubeCol, NEUTRAL:function(){ return NEUTRAL(); }});

/* ── the city, drawn once into an <svg> (a page may hold two: the desktop board, a phone's map page) ── */
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
/* which district a point lies in: inside a district's box, else the nearest one */
function distAt(x,y){ var D=P.d||[], best=null, bd=1e18;
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
/* a smooth path through points (Catmull-Rom as cubic curves): a river bends in wide, even curves */
function smoothD(a){ var n=a.length>>1, d='M'+a[0]+' '+a[1];
  for(var i=0;i<n-1;i++){ var i0=Math.max(0,i-1), i3=Math.min(n-1,i+2), x0=a[2*i0], y0=a[2*i0+1], x1=a[2*i], y1=a[2*i+1], x2=a[2*i+2], y2=a[2*i+3], x3=a[2*i3], y3=a[2*i3+1];
    d+='C'+(x1+(x2-x0)/6).toFixed(1)+' '+(y1+(y2-y0)/6).toFixed(1)+' '+(x2-(x3-x1)/6).toFixed(1)+' '+(y2-(y3-y1)/6).toFixed(1)+' '+x2+' '+y2; }
  return d; }
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
    tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=r.n; } }
function tube(parent, d, col, w, op, cls){
  var t=el('path',{'class':'pl-tube'+(cls?' '+cls:''), d:d, stroke:col, 'stroke-width':w},parent); if(op<1) t.setAttribute('stroke-opacity',op);
  el('path',{'class':'pl-sheen'+(cls?' '+cls:''), d:d, stroke:sheen(), 'stroke-width':Math.max(.9, w*.34)},parent); return t; }
/* the lines (rails, transit, tours, routes, stops) tuck BEHIND the landmark buildings and the building chips: they stay the last two layers
   (before the invisible hit paths and the hover pill), however late something else is added to the map */
function stackLayers(svg){
  var lm=svg.querySelector(':scope > .pl-lms'), bl=svg.querySelector(':scope > .pl-blds'); if(!lm || !bl) return;
  var ch=[].filter.call(svg.children, function(c){ return !c.matches('.pl-route-hits,.pl-tr-hits,.pl-hov'); }), n=ch.length;
  if(ch[n-2]===lm && ch[n-1]===bl) return;
  svg.appendChild(lm); svg.appendChild(bl);
  [].forEach.call(svg.querySelectorAll(':scope > .pl-route-hits,:scope > .pl-tr-hits,:scope > .pl-hov'), function(h){ svg.appendChild(h); }); }
function drawCity(svg){
  if(!svg._stk){ svg._stk=new MutationObserver(function(){ stackLayers(svg); }); svg._stk.observe(svg,{childList:true}); }
  GR=groundNow();
  svg.innerHTML='';
  var defs=el('defs',{},svg);
  /* the glass the city stands on */
  /* it runs on past the city's edge (the page never scrolls that far): an enlarged building at the
     very edge of the city pulls the board a little off-centre, and what shows there is more glass */
  var BL=1600; el('rect',{'class':'pl-glass', x:-MX-BL, y:-MY-BL, width:VW+2*BL, height:VH+2*BL, rx:34},svg);
  /* each neighbourhood's ground, unseen: pointing at it names the unit it holds */
  var wash=el('g',{'class':'pl-washes'},svg);
  (P.d||[]).forEach(function(d){ var pm=PHASE_META[d.u], b=d.box; if(!pm||!b) return; var ins=16;
    el('rect',{'class':'pl-dtint', x:b[0]+ins, y:b[1]+ins, width:Math.max(10,b[2]-b[0]-2*ins), height:Math.max(10,b[3]-b[1]-2*ins), rx:34, fill:pm.colorRaw, 'data-u':d.u},wash); });
  /* the streets: every block a rounded tile of connecting line, so each street
     curves at every intersection; the tiles in their district's colour */
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
  var byM={}, seen={};
  function major(x0,y0,x1,y1){ if(!okGrid) return; var k=x0+','+y0+','+x1+','+y1; if(seen[k]) return; seen[k]=1;
    if(x0===x1? !colMaj[x0] : !rowMaj[y0]) return;
    var u=distAt((x0+x1)/2,(y0+y1)/2); byM[u]=(byM[u]||'')+'M'+x0+' '+y0+'L'+x1+' '+y1; }
  (M.tiles||[]).forEach(function(t){ var u=distAt((t[0]+t[2])/2,(t[1]+t[3])/2); byU[u]=(byU[u]||'')+tileD(t);
    major(t[0],t[1],t[2],t[1]); major(t[0],t[3],t[2],t[3]); major(t[0],t[1],t[0],t[3]); major(t[2],t[1],t[2],t[3]); });
  (M.edges||[]).forEach(function(e){ var u=distAt((e[0]+e[2])/2,(e[1]+e[3])/2); byU[u]=(byU[u]||'')+'M'+e[0]+' '+e[1]+'L'+e[2]+' '+e[3]; major(e[0],e[1],e[2],e[3]); });
  function tc(u){ return tubeCol(dcol(u==='null'?null:+u)||NEUTRAL()); }
  Object.keys(byU).forEach(function(u){ tube(sg, byU[u], tc(u), 3.6, .95, 't-min'); });
  Object.keys(byM).forEach(function(u){ tube(sg, byM[u], tc(u), 5.6, .95, 't-maj'); });
  /* the diagonals: one clean line, joining the grid with rounded elbows */
  M.streets.forEach(function(st){ if(st.d) tube(sg, rp(st.p), tubeCol(dcol(distAt(st.p[2],st.p[3]))||NEUTRAL()), 5.6, .95, 't-maj'); });
  /* the rivers: each a broad glass band (a connecting line grown wide: edge, body, a light
     centre, a sheen) on a smooth course, run off the glass at its ends; the bridges over it */
  var cp=el('clipPath',{id:'plclip'+(svg._sid||'')},defs); el('rect',{x:-MX, y:-MY, width:VW, height:VH, rx:34},cp);
  var rv=el('g',{'class':'pl-river-g','clip-path':'url(#plclip'+(svg._sid||'')+')'},svg);
  (M.river||[]).forEach(function(r){ var d=smoothD(r.p), w=r.w||100;
    el('path',{'class':'pl-rv-rim', d:d, 'stroke-width':w+12},rv);
    el('path',{'class':'pl-rv-body', d:d, 'stroke-width':w},rv);
    /* the glass: lighter toward the middle in soft steps, then the sheen of Alto's own connecting lines */
    [[.84,.10],[.68,.12],[.52,.14],[.36,.18]].forEach(function(l){ el('path',{'class':'pl-rv-lite', d:d, 'stroke-width':w*l[0], 'stroke-opacity':l[1]},rv); });
    el('path',{'class':'pl-rv-sheen', d:d, 'stroke-width':Math.max(2, w*.13)},rv); });
  var bridges=el('g',{'class':'pl-bridges'},svg), labels0=el('g',{'class':'pl-brnames'},svg);
  /* a bridge has a deck, so it reads over the water in any colour: piers, rail lines, the deck, then the street's own line on it; the big ones are named */
  var brSeen=[];
  M.streets.forEach(function(st){ if(!st.o) return; var d=pts(st.p);
    el('path',{'class':'pl-br-pier', d:d},bridges); el('path',{'class':'pl-br-edge', d:d},bridges); el('path',{'class':'pl-casing', d:d},bridges);
    tube(bridges, d, tubeCol(dcol(distAt(st.p[0],st.p[1]))||NEUTRAL()), 5.6, .95, 't-maj'); });
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
    tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=nm; });
  var lg=el('g',{'class':'pl-lms'},svg);
  /* the railway: straight, above ground, a connecting line with ties */
  var rg=el('g',{'class':'pl-rails'},svg);
  (M.rails||[]).forEach(function(r){ var d=pts(r.p), c=r.c||NEUTRAL();
    el('path',{'class':'pl-ties', d:d, stroke:c},rg); tube(rg, d, c, 4.6, .95, 'r-line'); });
  window._palTr.lines(svg);                    /* the real lines: SEPTA, PATCO (palace_transit.py) */
  var bg=el('g',{'class':'pl-blds'},svg);
  var route=el('g',{'class':'pl-routes'},svg);
  /* stations: Alto's ring (a tube bent into a circle, its sheen on top); a hub is a double ring */
  var stl=el('g',{'class':'pl-stns'},svg);
  (M.stations||[]).forEach(function(s){
    var hub=s.hub || s.k==='rail';
    var c=NEUTRAL(), sg_=el('g',{'class':'pl-stn', style:'--sx:'+s.x+'px;--sy:'+s.y+'px'},stl);
    /* a ring is drawn at the origin of its own group, which the page scales to the screen (a ring keeps its size at every zoom) */
    if(hub){ el('circle',{'class':'pl-ring hub', cx:0, cy:0, r:13, stroke:c},sg_); el('circle',{'class':'pl-ring-sh', cx:0, cy:0, r:13},sg_);
      el('circle',{'class':'pl-ring', cx:0, cy:0, r:6, stroke:c},sg_); }
    else { el('circle',{'class':'pl-ring', cx:0, cy:0, r:6.5, stroke:c},sg_); el('circle',{'class':'pl-ring-sh', cx:0, cy:0, r:6.5},sg_); }
    lbl(stl, 'pl-stt'+(hub?' hub':''), s.n, s.x, s.y, 'start').setAttribute('data-n', s.n);
  });
  window._palTr.stations(svg);
  var labels=el('g',{},svg);
  (M.river||[]).forEach(function(r,i){ if(r.n) riverLabels(svg, defs, labels, r, i); });
  streetLabels(svg, defs, labels);
  /* landmark buildings: each fills its block with a little 3D of the real building, named (palace_landmarks.py); one with a page shows what is inside and opens it */
  (M.landmarks||[]).forEach(function(l){ var b=l.box; if(!b) return; var c=dcol(distAt(l.x,l.y))||NEUTRAL();
    var g=el('g',{'class':'pl-lmb'+(l.page?' has-page':''), 'data-page':l.page||'', 'data-name':l.n},lg);
    window._palLm.draw(g, l, {defs:defs, sid:svg._sid||'', color:c, ins:14, pageName:pageName, open:openPage}); });
  /* districts: the neighbourhood's own name over its buildings (the unit it holds is in its pop-up) */
  (P.d||[]).forEach(function(d){ var pm=PHASE_META[d.u]; if(!pm) return;
    var c=districtCentre(d), t=el('text',{'class':'pl-dist', x:c[0], y:c[1], 'text-anchor':'middle', fill:tubeCol(pm.colorRaw), 'data-u':d.u},labels);
    t.textContent=d.n || pm.label; });
  lbl(labels,'pl-credit','Map data © OpenStreetMap contributors', M.W+MX-18, M.H+MY-18, 'end');
  var hits=el('g',{'class':'pl-hits'},svg);
  M.streets.forEach(function(s){ if(!s.n || s.t) return; var h=el('path',{'class':'pl-hit', d:pts(s.p)},hits); h._n=s.n; });
  window._palTr.hits(svg);
  svg._b=bg; svg._r=route;
  drawBuildings(svg);
  sizeChips(svg);
  if(svg===svgD) window._palTr.ready();
}
/* chips keep a constant size on screen: re-measured when the zoom settles */
function sizeChips(svg){ var z=svg===svgD?Z:(MM.z||1);
  if(window._palLm) window._palLm.relayout(svg, z);
  svg.querySelectorAll('.pl-chip').forEach(function(g){ var t=g._t, bx=g._bx; if(!t) return; var w=0; try{ w=t.getComputedTextLength(); }catch(e){}
    if(!w) w=String(t.textContent).length*6.4/z; var h=20/z, pad=9/z;
    bx.setAttribute('x', -w/2-pad); bx.setAttribute('y', -h/2); bx.setAttribute('width', w+2*pad); bx.setAttribute('height', h); bx.setAttribute('rx', h/2); }); }
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
    var b=el('g',{'class':'pl-bld'+(k===0?' hub':''), 'data-id':id, transform:'rotate('+L[4]+' '+L[0]+' '+L[1]+')'},g);
    for(var i=fl;i>=1;i--) el('rect',{'class':'b-floor', x:L[0]-L[2]/2+i*2.2, y:L[1]-L[3]/2+i*2.2, width:L[2], height:L[3], rx:5, stroke:c},b);
    el('rect',{'class':'b-card', x:L[0]-L[2]/2, y:L[1]-L[3]/2, width:L[2], height:L[3], rx:5, stroke:c},b);
    el('rect',{'class':'b-top', x:L[0]-L[2]/2+2, y:L[1]-L[3]/2, width:L[2]-4, height:3.2, rx:1.6, fill:c},b);
    var nl=String(num(id)).length||3, fz=Math.min(L[3]*.55, L[2]/(nl*.62+.6));
    var t=el('text',{'class':'b-num', x:L[0], y:L[1], 'text-anchor':'middle', dy:'.35em', 'font-size':fz.toFixed(1)},b); t.textContent=num(id);
  }); });
}

/* ── the board: the city under the cards, at the current zoom ── */
var svgD=null;
function fitZ(){ var cv=document.getElementById('canvas'); if(!cv) return .3; return Math.max(.01, Math.min(cv.clientWidth/VW, cv.clientHeight/VH)); }
/* the zoom a building's number is first 10px tall: where the board opens (it zooms out past it, to the whole city) */
var ZREAD=(function(){ var L=null; for(var i=0;i<P.b.length && !L;i++) if(P.b[i] && P.b[i][0]) L=P.b[i][0]; if(!L) return .1;
  return Math.max(10/(L[3]*.55), 10*(4*.62+.6)/L[2]); })();
/* one screen px in map units, a touch more on screen as the map comes close (lines and rings keep their weight, not their scale) */
function tw(z){ return (Math.max(.88, Math.min(1.4, Math.pow(z,.3)))/z*Math.max(.34, Math.min(1, z/.24))).toFixed(4); }   /* far out the lines thin too, so a whole city of blocks stays a grid and not a blur */
function zmin(){ return fitZ()*.97; }       /* the farthest the board zooms out is the whole city in the window (a thin margin of glass round it) */
function setClasses(){ de.classList.toggle('pz-far', Z<.42); de.classList.toggle('pz-mid', Z<.8);
  if(svgD){ svgD.classList.toggle('far', Z<.42); svgD.classList.toggle('mid', Z<.8); } ctlState(); }
/* the zoom buttons say where the board is: no farther at the whole city, no closer at the nearest */
function ctlState(){ var c=document.getElementById('pal-ctl'); if(!c || Z==null) return; var lo=Z<=zmin()*1.004, hi=Z>=2.4*.996;
  var o=c.querySelector('[data-z=out]'), i=c.querySelector('[data-z=in]'), f=c.querySelector('[data-z=fit]');
  if(o) o.classList.toggle('off', lo); if(i) i.classList.toggle('off', hi); if(f) f.classList.toggle('on', lo); }
/* where the city's top edge sits in the canvas's scroll range: 0, or the gap that centres a short city */
function gy(){ var cv=document.getElementById('canvas'); return cv?Math.max(0,Math.round((cv.clientHeight-VH*Z)/2)):0; }
function placeAll(){
  var world=document.getElementById('world'); if(!world) return;
  world.style.setProperty('width', Math.round(VW*Z)+'px', 'important'); world.style.minHeight=Math.round(VH*Z+WORLD_PAD_TOP)+'px';
  /* a city smaller than the window sits in the middle of it */
  var cv=document.getElementById('canvas'), gap=cv?Math.max(0,(cv.clientWidth-VW*Z)/2):0;
  world.style.setProperty('margin-left', Math.round(gap)+'px', 'important');
  /* the board's top pad (the engine's WORLD_PAD_TOP) is pulled up out of the scroll range: the
     city's own top edge is where the page stops scrolling, so panning up never shows bare
     background between the bars and the map. A city shorter than the window is centred. */
  world.style.setProperty('margin-top', Math.round(gy()-WORLD_PAD_TOP)+'px', 'important');
  if(svgD){ svgD.setAttribute('width', Math.round(VW*Z)); svgD.setAttribute('height', Math.round(VH*Z+WORLD_PAD_TOP)-WORLD_PAD_TOP); svgD.style.setProperty('--pz', Z); svgD.style.setProperty('--tw', tw(Z)); svgD.style.top=WORLD_PAD_TOP+'px'; }
  setClasses(); if(svgD) sizeChips(svgD);
  (typeof NODES!=='undefined'?NODES:[]).forEach(function(n){
    var e=document.getElementById('node-'+n.id); if(!e) return;
    var L=isB(n.id)?lot(P.at[n.id]):null;
    if(!L){ e.classList.add('pal-floor'); return; }
    e.classList.remove('pal-floor');
    var x=(L[0]+MX)*Z, y=(L[1]+MY)*Z; n.displayX=x; n.y=y;
    e.style.left=x+'px'; e.style.top=(y+WORLD_PAD_TOP)+'px';
    e.style.setProperty('--pw', Math.max(10, L[2]*Z).toFixed(1)+'px'); e.style.setProperty('--ph', Math.max(8, L[3]*Z).toFixed(1)+'px');
    e.style.setProperty('--pr', L[4]+'deg'); e.style.setProperty('--pc', ucol(n.id));
    var cd=e.querySelector('.node-card'); if(cd && !mob()){ cd.tabIndex=0; cd.setAttribute('role','button'); cd.setAttribute('aria-label', num(n.id)+' '+title(n.id)); }   /* focus shows the same in-place pill */
    /* its number always inside it: as big as the building allows, up to 18px */
    var nl=String(num(n.id)).length||3, f=Math.min(18, L[3]*Z*.55, L[2]*Z/(nl*.62+.6));
    e.style.setProperty('--pf', Math.max(6, f).toFixed(1)+'px');
    var f=Math.min(5,(P.fl[n.id]||[]).length), sh=[], o=Math.max(1.5, Math.min(3.2, 3.2*Z));
    for(var i=1;i<=f;i++){ var q=(i*o).toFixed(1); sh.push(q+'px '+q+'px 0 0 rgba(255,255,255,.8)', q+'px '+q+'px 0 1px '+ucol(n.id)); }
    if(sh.length) e.style.setProperty('--pfl', sh.join(',')); else e.style.removeProperty('--pfl');
  });
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
window._altoPalace=function(h){
  if(mob()) return false;
  var world=document.getElementById('world'); if(!world) return false;
  if(!world._holdPan){ world._holdPan=1; new MutationObserver(holdPan).observe(world, {attributes:true, attributeFilter:['style']}); }
  if(Z==null) Z=Math.max(fitZ(), ZREAD);
  if(P._dirty){ P._dirty=0; restructure(true); if(svgD) drawBuildings(svgD); }
  if(!svgD){ svgD=el('svg',{id:'palace-svg', 'class':'pal-svg', viewBox:(-MX)+' '+(-MY)+' '+VW+' '+VH, preserveAspectRatio:'none'}); svgD._sid='d'; drawCity(svgD); }
  if(svgD.parentNode!==world) world.insertBefore(svgD, world.firstChild);
  placeAll();
  _actBands=ACT_SEQS.map(function(){ return {startY:0, endY:VH*Z}; });
  window._headerTint={slabTop:0, slabH:VH*Z, stops:[{p:0,c:PHASE_META[0].colorRaw},{p:100,c:PHASE_META[0].colorRaw}]};
  if(window.updateHeaderTint) try{ window.updateHeaderTint(); }catch(e){}
  var r=document.getElementById('river-svg'); if(r) r.innerHTML='';
  window._altoPalaceGeo={Z:Z};
  if(!opened){ opened=1; requestAnimationFrame(function(){ var cv=document.getElementById('canvas'); if(cv && !window._focusedNodeId){
    /* it opens on the buildings' own neighbourhoods, which a city grown past them leaves off-centre */
    var D=P.d||[], bx0=1e9, by0=1e9, bx1=-1e9, by1=-1e9; D.forEach(function(d){ var b=d.box; bx0=Math.min(bx0,b[0]); by0=Math.min(by0,b[1]); bx1=Math.max(bx1,b[2]); by1=Math.max(by1,b[3]); });
    var mx=D.length?(bx0+bx1)/2+MX:VW/2, my=D.length?(by0+by1)/2+MY:VH/2;
    cv.scrollLeft=Math.max(0,mx*Z-cv.clientWidth/2); cv.scrollTop=Math.max(0,my*Z-cv.clientHeight/2); } }); }
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
  var mx=(cv.scrollLeft+ax)/Z, my=(cv.scrollTop+ay-gy())/Z;
  Z=z; placeAll();
  cv.scrollLeft=mx*Z-ax; cv.scrollTop=my*Z+gy()-ay;
  if(window._altoPalaceGeo) window._altoPalaceGeo.Z=Z;
}
var zAnim=null;
function zoomAnim(z, ax, ay, ms, done){
  cancelAnimationFrame(zAnim); var z0=Z, t0=performance.now(); ms=ms||320;
  if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) ms=1;
  (function step(t){ var k=Math.min(1,(t-t0)/ms), e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;
    zoomTo(Math.exp(Math.log(z0)+(Math.log(z)-Math.log(z0))*e), ax, ay);
    if(k<1) zAnim=requestAnimationFrame(step); else if(done) done(); })(t0);
}
/* centre a map point at zoom z, gliding */
function flyMap(mx, my, z, done){
  var cv=document.getElementById('canvas'); if(!cv) return;
  var z0=Z, sx0=cv.scrollLeft, sy0=cv.scrollTop, t0=performance.now(), ms=520;
  if(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) ms=1;
  var cx=cv.clientWidth/2, cy=cv.clientHeight/2;
  /* the map point at the centre now */
  var fx=(sx0+cx)/z0-MX, fy=(sy0+cy-gy())/z0-MY;
  cancelAnimationFrame(zAnim);
  (function step(t){ var k=Math.min(1,(t-t0)/ms), e=k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
    var zz=Math.exp(Math.log(z0)+(Math.log(z)-Math.log(z0))*e), px=fx+(mx-fx)*e, py=fy+(my-fy)*e;
    Z=Math.max(zmin(),Math.min(2.4,zz)); placeAll();
    cv.scrollLeft=(px+MX)*Z-cx; cv.scrollTop=(py+MY)*Z+gy()-cy;
    if(window._altoPalaceGeo) window._altoPalaceGeo.Z=Z;
    if(k<1) zAnim=requestAnimationFrame(step); else if(done) done(); })(t0);
}
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
  var fl=P.fl[id]||[], h='<b><span class="pt-num">'+esc(num(id))+'</span> '+esc(title(id))+'</b>';
  var where=(P.near||{})[id]; h+='<small>'+(where?esc(where)+' · ':'')+(fl.length?(fl.length+1)+' floors':'one floor')+'</small>';
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
function enlarge(id){
  var L=lot(P.at[id]); if(!L) return; labelB(null); closeDock();
  if(Z<.85) flyMap(L[0], L[1], 1.05, function(){ window.enterFocus(id); setTimeout(function(){ drawRoutes(svgD, id); }, 30); });
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
  var pe=(Math.abs(w*Math.sin(th))+Math.abs(hh*Math.cos(th)))/2;
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
document.addEventListener('alto-focus-exit', function(){ drawRoutes(svgD, null); });
/* arrows while a building is enlarged: to the nearest building that way */
window._altoPalaceNav=function(id, dir){
  if(mob()) return null; var A=lot(P.at[bOf(id)]); if(!A) return null;
  var V={e:[1,0],w:[-1,0],n:[0,-1],s:[0,1],ne:[.7,-.7],nw:[-.7,-.7],se:[.7,.7],sw:[-.7,.7]}[dir]; if(!V) return null;
  var best=null, bd=1e18;
  (P.units||[]).forEach(function(ids){ ids.forEach(function(o){ if(o===id) return; var c=document.querySelector('#node-'+o+' .node-card');
    if(c && (c.classList.contains('dimmed')||c.classList.contains('ent-dimmed')||c.classList.contains('rel-dimmed'))) return;
    var B=lot(P.at[o]); if(!B) return; var dx=B[0]-A[0], dy=B[1]-A[1], along=dx*V[0]+dy*V[1]; if(along<=10) return;
    var across=Math.abs(dx*V[1]-dy*V[0]), cost=along+across*2.2; if(cost<bd){ bd=cost; best=o; } }); });
  return best;
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
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="var(--pal-trail)" stroke-width="2.6" stroke-dasharray="6 3"/>')+'<div>Trail</div></div>';
  h+=window._palLm.keyRow();
  var rk={}; (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).forEach(function(x){ if(x && x[2]!=='spine') rk[x[2]]=1; });
  Object.keys(rk).forEach(function(r){ var col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[r])||'var(--accent)', lb=(typeof REL_LABELS!=='undefined'&&REL_LABELS[r])||r;
    h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="'+col+'" stroke-width="4" stroke-dasharray="7 4"/>')+'<div>Route: '+esc(lb)+'</div></div>'; });
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
  c.setAttribute('role','toolbar'); c.setAttribute('aria-label','Map zoom'); c.innerHTML=z; document.body.appendChild(c);
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
    var f=e.target.closest('.pe-fl'); if(f){ ride(f.getAttribute('data-id')); return; }
    if(e.target.closest('.pe-street')){ var b=bOf(cur); if(window.showTimeline) window.showTimeline(); setTimeout(function(){ if(!mob() && isB(b)) enlarge(b); else if(mob() && window.featureNode) window.featureNode(b,true); }, 80); }
  });
}
function editing(){ return de.classList.contains('alto-editing'); }
function drawElev(id){
  buildElev(); var s=stack(id), b=s[0], c=ucol(b);
  elev.style.setProperty('--pal-car', c);
  var h='<div class="pe-roof" style="background:'+c+'">'+esc(num(b))+'<span class="pe-sec"> · '+esc(PHASE_META[ACT[b]]?(PHASE_META[ACT[b]].label.split(' — ')[1]||PHASE_META[ACT[b]].label):'')+'</span><small>'+esc(title(b))+'</small><span class="pe-where"></span></div><div class="pe-shaft"><div class="pe-car" title="Drag to another floor"></div>';
  for(var i=s.length-1;i>=0;i--){ var f=s[i];
    h+='<button class="pe-fl'+(f===id?' on':'')+'" data-id="'+esc(f)+'"><span class="pe-n">'+(i===0?'G':i)+'</span><span class="pe-t">'+esc(title(f))+'</span>'
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
  var w=elev.querySelector('.pe-where'); if(w) w.textContent=i===0?'Ground floor':'Floor '+i+' of '+(s.length-1);
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
    if(P.of[id]){ var s=stack(id); d.textContent='Floor '+s.indexOf(id)+' of '+num(s[0])+' '+title(s[0]); }
    else d.textContent=((P.near||{})[id]||'')+((P.fl[id]||[]).length?' · '+((P.fl[id]||[]).length+1)+' floors':'');
    if(!d.textContent) return; var tg=c.querySelector('.node-tag'); c.insertBefore(d, tg||c.firstChild); }); }
['DOMContentLoaded','load'].forEach(function(ev){ window.addEventListener(ev, function(){ phoneWhere(); setTimeout(phoneWhere, 400); }); });
var MM={z:.46, svg:null, box:null};
function mmapOpen(){
  var box=document.getElementById('pal-mmap');
  if(!box){ box=document.createElement('div'); box.id='pal-mmap';
    var pi=function(d){ return '<svg class="pm-ic" viewBox="0 0 20 20" width="21" height="21" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+d+'</svg>'; };
    box.innerHTML='<div class="pm-scroll"></div><button class="pm-close" aria-label="Close">'+pi('<path d="M5 5l10 10M15 5L5 15"/>')+'</button>'
      +'<div class="pm-zoom"><div class="pm-pill"><button type="button" data-z="in" aria-label="Zoom in">'+pi('<path d="M10 4.5v11M4.5 10h11"/>')+'</button><span class="pm-div"></span>'
      +'<button type="button" data-z="out" aria-label="Zoom out">'+pi('<path d="M4.5 10h11"/>')+'</button></div>'
      +'<button type="button" class="pm-city" data-z="fit" aria-label="The whole city">'+pi('<path d="M3.5 7.3V5.4a1.9 1.9 0 0 1 1.9-1.9h1.9M12.7 3.5h1.9a1.9 1.9 0 0 1 1.9 1.9v1.9M16.5 12.7v1.9a1.9 1.9 0 0 1-1.9 1.9h-1.9M7.3 16.5H5.4a1.9 1.9 0 0 1-1.9-1.9v-1.9"/>'
        +'<rect x="7.2" y="7.2" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="10.5" y="7.2" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="7.2" y="10.5" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/><rect x="10.5" y="10.5" width="2.3" height="2.3" rx=".7" fill="currentColor" stroke="none"/>')+'</button></div><div class="pm-card"></div>';
    document.body.appendChild(box); MM.box=box;
    MM.svg=el('svg',{viewBox:(-MX)+' '+(-MY)+' '+VW+' '+VH, preserveAspectRatio:'none', id:'palace-svg-m', 'class':'pal-svg'}); MM.svg._sid='m'; drawCity(MM.svg);
    MM.svg.style.setProperty('--pz', MM.z); MM.svg.style.setProperty('--tw', tw(MM.z));
    box.querySelector('.pm-scroll').appendChild(MM.svg);
    box.querySelector('.pm-close').addEventListener('click', mmapClose);
    box.querySelector('.pm-zoom').addEventListener('click', function(e){ var b=e.target.closest('[data-z]'); if(!b) return; var sc=box.querySelector('.pm-scroll'), k=b.getAttribute('data-z'); mz(k==='fit'?Math.min(sc.clientWidth/VW, sc.clientHeight/VH):MM.z*(k==='in'?1.6:1/1.6), sc.clientWidth/2, sc.clientHeight/2); });
    var sc=box.querySelector('.pm-scroll'), d0=0, z0=0, mid=null;
    sc.addEventListener('touchstart', function(e){ if(e.touches.length===2){ d0=Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY); z0=MM.z;
      var r=sc.getBoundingClientRect(); mid=[(e.touches[0].clientX+e.touches[1].clientX)/2-r.left, (e.touches[0].clientY+e.touches[1].clientY)/2-r.top]; } }, {passive:true});
    sc.addEventListener('touchmove', function(e){ if(e.touches.length===2 && d0){ e.preventDefault(); var d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY); mz(z0*d/d0, mid[0], mid[1]); } }, {passive:false});
    sc.addEventListener('touchend', function(e){ if(e.touches.length<2) d0=0; });
    sc.addEventListener('click', function(e){
      var card=box.querySelector('.pm-card'), b=e.target.closest('.pl-bld[data-id]');
      if(b){ var id=b.getAttribute('data-id'); drawRoutes(MM.svg, id);
        card.innerHTML=bTip(id).replace('<small>','<small>')+'<button data-open="'+esc(id)+'">Go inside</button>'; card.classList.add('on'); return; }
      var h=e.target.closest('.pl-hit'); if(h){ var c=cornerAt(MM.svg, e, h._n); card.innerHTML='<b>'+esc(c?c.join(' & '):h._n)+'</b>'; card.classList.add('on'); return; }
      var lmb=e.target.closest('.pl-lmb'); if(lmb){ var pg=lmb.getAttribute('data-page');
        card.innerHTML=lmTip(lmb)+(pg?'<button data-page="'+esc(pg)+'">Go inside</button>':''); card.classList.add('on'); return; }
      var du=e.target.closest('.pl-dist'); if(du){ drawRoutes(MM.svg, null, +du.getAttribute('data-u')); card.innerHTML=distTip(+du.getAttribute('data-u'))+'<small>The dotted line walks through its buildings in order.</small>'; card.classList.add('on'); return; }
      var dt=e.target.closest('.pl-dtint'); if(dt){ card.innerHTML=distTip(+dt.getAttribute('data-u')); card.classList.add('on'); return; }
      card.classList.remove('on'); drawRoutes(MM.svg, null);
    });
    box.querySelector('.pm-card').addEventListener('click', function(e){ var pgb=e.target.closest('[data-page]'); if(pgb){ mmapClose(); openPage(pgb.getAttribute('data-page')); return; }
      var o=e.target.closest('[data-open]'); if(!o) return; var id=o.getAttribute('data-open'); mmapClose();
      if(window.featureNode) try{ window.featureNode(id, true); }catch(x){} setTimeout(function(){ window.showDetail('node', id); }, 60); });
  }
  var top=0, tb=document.getElementById('title-bar'); if(tb) top=tb.getBoundingClientRect().bottom;
  box.style.top=Math.max(56, top)+'px';
  box.classList.add('on'); mz(MM.z, 0, 0, true);
  /* open on the card being read */
  var f=window._featuredNodeId, L=f?lot(P.at[bOf(f)]):null, sc=box.querySelector('.pm-scroll');
  if(L){ sc.scrollLeft=(L[0]+MX)*MM.z-sc.clientWidth/2; sc.scrollTop=(L[1]+MY)*MM.z-sc.clientHeight/2; drawRoutes(MM.svg, bOf(f)); }
}
function mz(z, ax, ay, keep){ var sc=MM.box.querySelector('.pm-scroll'); z=Math.max(ZREAD, Math.min(1.6, z));
  var mx=(sc.scrollLeft+ax)/MM.z, my=(sc.scrollTop+ay)/MM.z; MM.z=z;
  MM.svg.setAttribute('width', VW*z); MM.svg.setAttribute('height', VH*z); MM.svg.style.setProperty('--pz', z); MM.svg.style.setProperty('--tw', tw(z));
  MM.svg.classList.toggle('far', z<.42); MM.svg.classList.toggle('mid', z<.8);
  if(!keep){ sc.scrollLeft=mx*z-ax; sc.scrollTop=my*z-ay; } }
function mmapClose(){ if(MM.box) MM.box.classList.remove('on'); }
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
  if(p[0]==='p' && p[2]==='lot' && TT[p[1]]) return {kind:'card', get:function(){ return P.at[p[1]]||null; },
    set:function(v){ if(v) P.at[p[1]]=v; else delete P.at[p[1]]; P._dirty=1; }};
  if(p[0]==='pf' && TT[p[1]]) return {kind:'card', get:function(){ return P.par[p[1]]||''; },
    set:function(v){ if(v) P.par[p[1]]=v; else delete P.par[p[1]]; P._dirty=1; }};
  return null;
};
window._altoPalaceRefresh=function(){ P._dirty=0; restructure(true); if(svgD){ drawBuildings(svgD); var labels=svgD.querySelectorAll('.pl-dist');
    labels.forEach(function(t){ var u=+t.getAttribute('data-u'), d=(P.d||[]).filter(function(q){ return q.u===u; })[0]; if(!d) return; var c=districtCentre(d);
      t.setAttribute('x',c[0]); t.setAttribute('y',c[1]); [].forEach.call(t.querySelectorAll('tspan'),function(s){ s.setAttribute('x',c[0]); }); }); }
  ENT={}; placeAll(); if(de.classList.contains('pal-elev-on') && cur){ drawElev(cur); } };
window._altoPalaceDirty=function(){ P._dirty=1; };
function chg(list){ if(window._altoEditChanges) return window._altoEditChanges(list); return false; }
function letOut(fid){
  var b=bOf(fid), L=lot(P.at[b]), key=freeLot(L?L[0]:M.W/2, L?L[1]:M.H/2);
  chg([['pf|'+fid, ''], ['p|'+fid+'|lot', key]]);
}
function within(a){ var s=[a], i=0; while(i<s.length){ var x=s[i++]; ORDER.forEach(function(id){ if(P.par[id]===x) s.push(id); }); } return s; }
var slot=null;
window.addEventListener('mousedown', function(e){
  if(!palaceOn() || !editing() || e.button!==0 || focused()) return;
  var id=bAt(e.target); if(!id) return;
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
  var onto=null; (P.units[ACT[id]]||[]).forEach(function(o){ if(o===id || within(id).indexOf(o)>=0) return; var B=lot(P.at[o]); if(!B) return;
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
  var pend=null; if(L && !floorOf && addLayer()){ pend=lotRect(L,'pl-addr pl-addpend',addLayer(),2); }
  var gone=function(){ if(pend){ pend.remove(); pend=null; } };
  var head=floorOf?'Add a floor to '+num(floorOf)+' '+title(floorOf):'Add a building';
  E.ask(at, head, fields, 'Add', function(v){
    gone();
    var ui=floorOf?ACT[floorOf]:(+v.unit), id=E.rid('card-'), uk=(us.filter(function(u){ return u.i===ui; })[0]||{}).key;
    if(uk==null) return;
    var like=(P.units[ui]||[]).map(function(i){ return TT[i]; })[0];
    var spec={p:floorOf||'', a:uk, t:v.title, g:v.tag||'', d:v.desc||'', c:(like&&like.color)||'var(--accent)'};
    var list=[['nn|'+id, spec]];
    if(floorOf) list.push(['pf|'+id, floorOf]); else list.push(['p|'+id+'|lot', key]);
    if(!chg(list)){ E.toast('That could not be added.'); return; }
    addMode=false; syncAdd();
    setTimeout(function(){ E.toast('Added '+num(id)+' '+v.title+' — ⌘Z takes it back.'); }, 60);
  });
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
})();
"""
