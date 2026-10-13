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
  html{--pal-river:#7fb6e8;--pal-glass:rgba(255,255,255,.34);--pal-glass-edge:rgba(255,255,255,.75);--pal-water:rgba(196,222,246,.92);--pal-water-edge:rgba(255,255,255,.85);
    --pal-park:rgba(255,255,255,.20);--pal-lm:rgba(255,255,255,.38);--pal-text:#2c2f3d;--pal-halo:rgba(255,255,255,.88);--pal-trail:#4f9a4a;}
  html.dark{--pal-river:#3f78b4;--pal-glass:rgba(22,24,34,.42);--pal-glass-edge:rgba(255,255,255,.16);--pal-water:rgba(38,64,100,.92);--pal-water-edge:rgba(255,255,255,.28);
    --pal-park:rgba(255,255,255,.06);--pal-lm:rgba(255,255,255,.10);--pal-text:#e4e2ec;--pal-halo:rgba(14,16,24,.88);--pal-trail:#6fbf68;}
  html.alto-palace:not(.mobile) #world{margin:0 !important;}
  html.alto-palace:not(.mobile) #glass-slab,html.alto-palace:not(.mobile) #river-svg,
  html.alto-palace:not(.mobile) #world .phase-band,html.alto-palace:not(.mobile) #world .phase-label-float,
  html.alto-palace:not(.mobile) #world .unit-bar{display:none !important;}
  #palace-svg{position:absolute;left:0;z-index:1;overflow:visible;pointer-events:none;
    -webkit-user-select:none;user-select:none;transition:opacity .3s;}
  #canvas.focus-mode #palace-svg{opacity:.55;}
  .pal-svg .pl-glass{fill:var(--pal-glass);stroke:var(--pal-glass-edge);stroke-width:1.5;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-water{fill:var(--pal-water);}
  .pal-svg .pl-river-g .pl-sheen{opacity:.8;}
  .pal-svg .pl-lmb{pointer-events:all;cursor:default;}
  .pal-svg .pl-lmb.has-page{cursor:pointer;}
  .pal-svg .pl-lmb .lm-shadow{fill:rgba(20,26,55,.16);}
  .pal-svg .pl-lmb .lm-card{fill:rgba(255,255,255,.92);stroke-width:2.5;vector-effect:non-scaling-stroke;}
  html.dark .pal-svg .pl-lmb .lm-card{fill:rgba(34,36,48,.94);}
  .pal-svg .pl-lmb.has-page:hover .lm-card{stroke-width:4;}
  .pal-svg .pl-lmb .lm-name{font-weight:800;letter-spacing:.01em;stroke:none;}
  .pal-svg .pl-bridges .pl-tube{filter:drop-shadow(0 1px 2px rgba(20,26,55,.35));}
  .pal-svg .pl-water-edge{fill:none;stroke:var(--pal-water-edge);stroke-width:2;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-park{fill:var(--pal-park);stroke-width:1.2;stroke-opacity:.45;stroke-dasharray:5 4;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-lm{fill:var(--pal-lm);stroke-width:1.8;stroke-opacity:.8;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-tube,.pal-svg .pl-sheen{fill:none;stroke-linecap:round;stroke-linejoin:round;}
  .pal-svg .pl-tun{fill:none;stroke-width:2;stroke-dasharray:6 6;stroke-opacity:.35;}
  .pal-svg .pl-trail{fill:none;stroke:var(--pal-trail);stroke-width:2.6;stroke-dasharray:7 5;stroke-linecap:round;opacity:.85;}
  .pal-svg .pl-ties{fill:none;stroke-width:11;stroke-dasharray:1.8 7;stroke-opacity:.75;}
  .pal-svg .pl-tube.r-under{stroke-dasharray:10 8;}
  .pal-svg .pl-sheen.r-under{stroke-dasharray:10 8;opacity:.6;}
  .pal-svg .pl-ring{fill:var(--pal-halo);stroke-width:4;}
  .pal-svg .pl-ring.hub{stroke-width:5.5;fill:none;}
  .pal-svg .pl-ring-sh{fill:none;stroke:rgba(255,255,255,.7);stroke-width:1.4;}
  .pal-svg text{fill:var(--pal-text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    paint-order:stroke;stroke:var(--pal-halo);stroke-linejoin:round;}
  .pal-svg .pl-st{font-size:calc(11.5px / var(--pz,1));font-weight:650;stroke-width:calc(3.4px / var(--pz,1));letter-spacing:.03em;}
  .pal-svg .pl-river{font-size:calc(14px / var(--pz,1));font-style:italic;fill:#3e6f99;stroke-width:calc(3px / var(--pz,1));letter-spacing:.14em;}
  html.dark .pal-svg .pl-river{fill:#9cc4e6;}
  .pal-svg .pl-chip-bg{fill:var(--pal-halo);stroke-width:1.4;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-lmt{font-size:calc(11px / var(--pz,1));font-weight:650;stroke:none;letter-spacing:.02em;}
  .pal-svg .pl-stt{font-size:calc(11px / var(--pz,1));font-weight:700;stroke-width:calc(3px / var(--pz,1));}
  .pal-svg .pl-stt.hub{font-size:calc(13px / var(--pz,1));font-weight:800;}
  .pal-svg .pl-dist{font-size:calc(19px / var(--pz,1));font-weight:850;letter-spacing:.14em;text-transform:uppercase;
    stroke-width:calc(5px / var(--pz,1));pointer-events:all;cursor:pointer;}
  .pal-svg .pl-dist tspan.only{display:none;}
  .pal-svg.far .pl-dist tspan.full,.pal-svg.far .pl-dist tspan.nb{display:none;}
  .pal-svg.far .pl-dist tspan.only{display:inline;font-size:calc(26px / var(--pz,1));}
  .pal-svg .pl-dist tspan.nb{font-size:calc(12px / var(--pz,1));font-weight:600;letter-spacing:.08em;fill:var(--pal-text);opacity:.75;}
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
  .pal-tip{position:fixed;z-index:9999;pointer-events:none;display:none;background:var(--surface);color:var(--text);
    border:1px solid var(--border);border-radius:9px;padding:7px 10px;font-size:12.5px;line-height:1.35;max-width:320px;
    box-shadow:0 6px 22px rgba(0,0,0,.22);}
  .pal-tip b{display:block;font-size:13px;}
  .pal-tip .pt-num{color:var(--muted);font-weight:800;margin-right:6px;}
  .pal-tip small{display:block;color:var(--muted);margin-top:2px;}
  .pal-tip .pt-rel{display:block;margin-top:3px;font-size:12px;}
  .pal-tip .pt-rel i{display:inline-block;width:14px;height:4px;border-radius:2px;vertical-align:middle;margin-right:6px;}
  #pal-ctl{position:fixed;left:16px;bottom:18px;z-index:310;display:flex;flex-direction:column;gap:8px;align-items:flex-start;max-width:300px;}
  #pal-ctl .pc-z{display:flex;gap:6px;}
  #pal-ctl button{font:inherit;font-size:15px;font-weight:700;min-width:34px;height:34px;padding:0 10px;border-radius:10px;cursor:pointer;
    color:var(--text);background:color-mix(in srgb,var(--surface) 88%,transparent);border:1px solid var(--border);
    box-shadow:0 4px 14px rgba(0,0,0,.14);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);}
  #pal-ctl button:hover{background:var(--surface);}
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
  #pal-mmap .pm-scroll{position:absolute;inset:0;overflow:auto;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;}
  #pal-mmap .pm-close{position:absolute;right:12px;top:10px;z-index:3;width:40px;height:40px;border-radius:20px;font-size:20px;
    background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 4px 14px rgba(0,0,0,.2);}
  #pal-mmap .pm-zoom{position:absolute;right:12px;bottom:calc(20px + env(safe-area-inset-bottom,0px));z-index:3;display:flex;flex-direction:column;gap:8px;}
  #pal-mmap .pm-zoom button{width:44px;height:44px;border-radius:12px;font-size:22px;font-weight:700;background:var(--surface);color:var(--text);
    border:1px solid var(--border);box-shadow:0 4px 14px rgba(0,0,0,.2);}
  #pal-mmap .pm-card{position:absolute;left:12px;right:68px;bottom:calc(20px + env(safe-area-inset-bottom,0px));z-index:3;display:none;
    padding:10px 12px;border-radius:14px;background:var(--surface);color:var(--text);border:1px solid var(--border);box-shadow:0 8px 24px rgba(0,0,0,.25);font-size:13px;}
  #pal-mmap .pm-card.on{display:block;}
  #pal-mmap .pm-card b{display:block;font-size:14px;}
  #pal-mmap .pm-card small{display:block;color:var(--muted);margin-top:2px;}
  #pal-mmap .pm-card button{margin-top:8px;font:inherit;font-weight:700;padding:7px 14px;border-radius:9px;border:0;background:var(--accent);color:#fff;}
  #pal-mmap svg{display:block;}
"""


PALACE_JS = KEY_JS + r"""
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
        var tp=el('textPath',{href:'#'+id, startOffset:off, 'text-anchor':'middle'},t); tp.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href','#'+id); tp.textContent=n; }
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
/* the engine's contrast rule (_lineAdapt): a line is pushed away from the glass behind it */
function tubeCol(c){ var r=rgbOf(c), bg=dk()?[28,30,40]:[238,238,242], d=lum(r)-lum(bg), MIN=.3;
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
function tube(parent, d, col, w, op, cls){
  var t=el('path',{'class':'pl-tube'+(cls?' '+cls:''), d:d, stroke:col, 'stroke-width':w},parent); if(op<1) t.setAttribute('stroke-opacity',op);
  el('path',{'class':'pl-sheen'+(cls?' '+cls:''), d:d, stroke:sheen(), 'stroke-width':Math.max(.9, w*.34)},parent); return t; }
function drawCity(svg){
  svg.innerHTML='';
  var defs=el('defs',{},svg);
  /* the glass the city stands on */
  el('rect',{'class':'pl-glass', x:-MX, y:-MY, width:VW, height:VH, rx:34},svg);
  /* the streets: every block a rounded tile of connecting line, so each street
     curves at every intersection; the tiles in their district's colour */
  var sg=el('g',{'class':'pl-streets'},svg), byU={};
  function tileD(t){ var x0=t[0], y0=t[1], x1=t[2], y1=t[3], r=Math.min(R, (x1-x0)/2, (y1-y0)/2);
    return 'M'+(x0+r)+' '+y0+'H'+(x1-r)+'Q'+x1+' '+y0+' '+x1+' '+(y0+r)+'V'+(y1-r)+'Q'+x1+' '+y1+' '+(x1-r)+' '+y1
      +'H'+(x0+r)+'Q'+x0+' '+y1+' '+x0+' '+(y1-r)+'V'+(y0+r)+'Q'+x0+' '+y0+' '+(x0+r)+' '+y0+'Z'; }
  (M.tiles||[]).forEach(function(t){ var u=distAt((t[0]+t[2])/2,(t[1]+t[3])/2); byU[u]=(byU[u]||'')+tileD(t); });
  (M.edges||[]).forEach(function(e){ var u=distAt((e[0]+e[2])/2,(e[1]+e[3])/2); byU[u]=(byU[u]||'')+'M'+e[0]+' '+e[1]+'L'+e[2]+' '+e[3]; });
  Object.keys(byU).forEach(function(u){ tube(sg, byU[u], tubeCol(dcol(u==='null'?null:+u)||NEUTRAL()), TUBE, .95); });
  /* the diagonals: one clean line, joining the grid with rounded elbows */
  M.streets.forEach(function(st){ if(st.d) tube(sg, rp(st.p), tubeCol(dcol(distAt(st.p[2],st.p[3]))||NEUTRAL()), TUBE, .95); });
  /* the river: a very thick connecting line along its course; the bridges over it */
  var rv=el('g',{'class':'pl-river-g'},svg);
  (M.river||[]).forEach(function(r){ tube(rv, rp(r.p, 12), 'var(--pal-river)', r.w||64, 1, 'river'); });
  var bridges=el('g',{'class':'pl-bridges'},svg);
  M.streets.forEach(function(st){ if(st.o) tube(bridges, pts(st.p), tubeCol(dcol(distAt(st.p[0],st.p[1]))||NEUTRAL()), TUBE, .95); });
  var lg=el('g',{'class':'pl-lms'},svg);
  /* the railway: straight, above ground, a connecting line with ties */
  var rg=el('g',{'class':'pl-rails'},svg);
  (M.rails||[]).forEach(function(r){ var d=pts(r.p), c=r.c||NEUTRAL();
    el('path',{'class':'pl-ties', d:d, stroke:c},rg); tube(rg, d, c, 4.6, .95, 'r-line'); });
  var bg=el('g',{'class':'pl-blds'},svg);
  var route=el('g',{'class':'pl-routes'},svg);
  /* stations: Alto's ring (a tube bent into a circle, its sheen on top); a hub is a double ring */
  var stl=el('g',{'class':'pl-stns'},svg);
  (M.stations||[]).forEach(function(s){
    var hub=s.hub || s.k==='rail';
    var c=NEUTRAL();
    if(hub){ el('circle',{'class':'pl-ring hub', cx:s.x, cy:s.y, r:13, stroke:c},stl); el('circle',{'class':'pl-ring-sh', cx:s.x, cy:s.y, r:13},stl);
      el('circle',{'class':'pl-ring', cx:s.x, cy:s.y, r:6, stroke:c},stl); }
    else { el('circle',{'class':'pl-ring', cx:s.x, cy:s.y, r:6.5, stroke:c},stl); el('circle',{'class':'pl-ring-sh', cx:s.x, cy:s.y, r:6.5},stl); }
    lbl(stl, 'pl-stt'+(hub?' hub':''), s.n, s.x+(hub?18:11), s.y-(hub?15:9), 'start');
  });
  var labels=el('g',{},svg);
  (M.rivers||[]).forEach(function(r,i){ var p=r.p; if(p.length<4) return; var L=0; for(var j=0;j+3<p.length;j+=2) L+=Math.hypot(p[j+2]-p[j],p[j+3]-p[j+1]); if(L<500) return;
    var id='plr'+(svg._sid||'')+i; el('path',{id:id, d:pts(p)},defs);
    var t=el('text',{'class':'pl-river', dy:'.35em'},labels), tp=el('textPath',{href:'#'+id, startOffset:'50%', 'text-anchor':'middle'},t); tp.textContent=r.n; });
  streetLabels(svg, defs, labels);
  /* landmark buildings: each fills its block, named; one with a page opens it */
  (M.landmarks||[]).forEach(function(l){ var b=l.box; if(!b) return; var c=dcol(distAt(l.x,l.y))||NEUTRAL(), ins=14;
    var g=el('g',{'class':'pl-lmb'+(l.page?' has-page':''), 'data-page':l.page||'', 'data-name':l.n},lg);
    el('rect',{'class':'lm-shadow', x:b[0]+ins+4, y:b[1]+ins+5, width:b[2]-b[0]-2*ins, height:b[3]-b[1]-2*ins, rx:9},g);
    el('rect',{'class':'lm-card', x:b[0]+ins, y:b[1]+ins, width:b[2]-b[0]-2*ins, height:b[3]-b[1]-2*ins, rx:9, stroke:c},g);
    el('rect',{'class':'lm-top', x:b[0]+ins+3, y:b[1]+ins, width:b[2]-b[0]-2*ins-6, height:5, rx:2.5, fill:c},g);
    /* its name inside it: a word to a line where that reads better, as big as the building allows */
    var bw=b[2]-b[0]-2*ins-16, bh=b[3]-b[1]-2*ins-14, words=String(l.n).split(' ');
    var lines=words.length>1 && bw/bh<4 ? words : [String(l.n)], longest=Math.max.apply(null, lines.map(function(q){ return q.length; }));
    var fs=Math.min(34, bw/(longest*.62), bh/(lines.length*1.2));
    var t=el('text',{'class':'lm-name', x:l.x, y:l.y-(lines.length-1)*fs*.6, 'text-anchor':'middle', 'font-size':fs.toFixed(1)},g);
    lines.forEach(function(s_,i){ var ts=el('tspan',{x:l.x, dy:i?'1.2em':'.35em'},t); ts.textContent=s_; }); });
  /* districts: the section's name over its buildings, as a unit's label floats over its band */
  (P.d||[]).forEach(function(d){ var pm=PHASE_META[d.u]; if(!pm) return;
    var c=districtCentre(d), t=el('text',{'class':'pl-dist', x:c[0], y:c[1], 'text-anchor':'middle', fill:pm.colorRaw, 'data-u':d.u},labels);
    var a=el('tspan',{'class':'full', x:c[0]},t); a.textContent=pm.numeral+' · '+(pm.label.split(' — ')[1]||pm.label);
    var a2=el('tspan',{'class':'only', x:c[0]},t); a2.textContent=pm.numeral;
    if(d.n){ var b=el('tspan',{'class':'nb', x:c[0], dy:'1.35em'},t); b.textContent=d.n; } });
  lbl(labels,'pl-credit','Map data © OpenStreetMap contributors', M.W+MX-18, M.H+MY-18, 'end');
  var hits=el('g',{'class':'pl-hits'},svg);
  M.streets.forEach(function(s){ if(!s.n || s.t) return; var h=el('path',{'class':'pl-hit', d:pts(s.p)},hits); h._n=s.n; });
  svg._b=bg; svg._r=route;
  drawBuildings(svg);
  sizeChips(svg);
}
/* chips keep a constant size on screen: re-measured when the zoom settles */
function sizeChips(svg){ var z=svg===svgD?Z:(MM.z||1);
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
function fitZ(){ var cv=document.getElementById('canvas'); if(!cv) return .3; return Math.max(.08, Math.min(cv.clientWidth/VW, cv.clientHeight/VH)); }
/* the farthest the board zooms out: where a building's number is still 10px tall */
var ZREAD=(function(){ var L=null; for(var i=0;i<P.b.length && !L;i++) if(P.b[i] && P.b[i][0]) L=P.b[i][0]; if(!L) return .1;
  return Math.max(10/(L[3]*.55), 10*(4*.62+.6)/L[2]); })();
function zmin(){ return Math.max(fitZ()*.92, ZREAD); }
function setClasses(){ de.classList.toggle('pz-far', Z<.42); de.classList.toggle('pz-mid', Z<.8);
  if(svgD){ svgD.classList.toggle('far', Z<.42); svgD.classList.toggle('mid', Z<.8); } }
function placeAll(){
  var world=document.getElementById('world'); if(!world) return;
  world.style.setProperty('width', Math.round(VW*Z)+'px', 'important'); world.style.minHeight=Math.round(VH*Z+WORLD_PAD_TOP)+'px';
  /* a city smaller than the window sits in the middle of it */
  var cv=document.getElementById('canvas'), gap=cv?Math.max(0,(cv.clientWidth-VW*Z)/2):0;
  world.style.setProperty('margin-left', Math.round(gap)+'px', 'important');
  if(svgD){ svgD.setAttribute('width', VW*Z); svgD.setAttribute('height', VH*Z); svgD.style.setProperty('--pz', Z); svgD.style.top=WORLD_PAD_TOP+'px'; }
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
    /* its number always inside it: as big as the building allows, up to 18px */
    var nl=String(num(n.id)).length||3, f=Math.min(18, L[3]*Z*.55, L[2]*Z/(nl*.62+.6));
    e.style.setProperty('--pf', Math.max(6, f).toFixed(1)+'px');
    var f=Math.min(5,(P.fl[n.id]||[]).length), sh=[], o=Math.max(1.5, Math.min(3.2, 3.2*Z));
    for(var i=1;i<=f;i++){ var q=(i*o).toFixed(1); sh.push(q+'px '+q+'px 0 0 rgba(255,255,255,.8)', q+'px '+q+'px 0 1px '+ucol(n.id)); }
    if(sh.length) e.style.setProperty('--pfl', sh.join(',')); else e.style.removeProperty('--pfl');
  });
}
window._altoPalace=function(h){
  if(mob()) return false;
  var world=document.getElementById('world'); if(!world) return false;
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
    cv.scrollLeft=Math.max(0,(VW*Z-cv.clientWidth)/2); cv.scrollTop=Math.max(0,(VH*Z+WORLD_PAD_TOP-cv.clientHeight)/2); } }); }
  ctl();
  return true;
};

/* light/dark: the lines take their contrast from the glass behind them, so the city is drawn again */
var wasDark=dk();
new MutationObserver(function(){ if(dk()===wasDark) return; wasDark=dk();
  if(svgD){ drawCity(svgD); placeAll(); } if(MM.svg){ drawCity(MM.svg); } }).observe(de, {attributes:true, attributeFilter:['class']});

/* ── zoom: the board drawn larger or smaller about a point, the cards keep their size ── */
function canvasPt(cv, cx, cy){ var r=cv.getBoundingClientRect(); return [(cx-r.left)/r.width*cv.clientWidth, (cy-r.top)/r.height*cv.clientHeight]; }
function zoomTo(z, ax, ay){
  var cv=document.getElementById('canvas'); if(!cv || !svgD) return;
  z=Math.max(zmin(), Math.min(2.4, z)); if(Math.abs(z-Z)<1e-4) return;
  if(ax==null){ ax=cv.clientWidth/2; ay=cv.clientHeight/2; }
  var mx=(cv.scrollLeft+ax)/Z, my=(cv.scrollTop+ay-WORLD_PAD_TOP)/Z;
  Z=z; placeAll();
  cv.scrollLeft=mx*Z-ax; cv.scrollTop=my*Z+WORLD_PAD_TOP-ay;
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
  var fx=(sx0+cx)/z0-MX, fy=(sy0+cy-WORLD_PAD_TOP)/z0-MY;
  cancelAnimationFrame(zAnim);
  (function step(t){ var k=Math.min(1,(t-t0)/ms), e=k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
    var zz=Math.exp(Math.log(z0)+(Math.log(z)-Math.log(z0))*e), px=fx+(mx-fx)*e, py=fy+(my-fy)*e;
    Z=Math.max(zmin(),Math.min(2.4,zz)); placeAll();
    cv.scrollLeft=(px+MX)*Z-cx; cv.scrollTop=(py+MY)*Z+WORLD_PAD_TOP-cy;
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
var tip=null, tipT=null;
function showTip(html, x, y){ if(!tip){ tip=document.createElement('div'); tip.className='pal-tip'; document.body.appendChild(tip); }
  tip.innerHTML=html; tip.style.display='block'; moveTip(x,y); }
function moveTip(x,y){ if(!tip||tip.style.display!=='block') return; var w=tip.offsetWidth, h=tip.offsetHeight;
  var X=x+14, Y=y+16; if(X+w>innerWidth-8) X=x-w-14; if(Y+h>innerHeight-8) Y=y-h-14; tip.style.left=X+'px'; tip.style.top=Y+'px'; }
function hideTip(){ if(tip) tip.style.display='none'; }
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
function lmTip(g){ var pg=g.getAttribute('data-page'); return '<b>'+esc(g.getAttribute('data-name'))+'</b>'+(pg?'<small>Inside: '+esc(pageName(pg))+' · click to go in</small>':''); }
function svgPt(svg, e){ var r=svg.getBoundingClientRect(), vb=svg.viewBox.baseVal; return [vb.x+(e.clientX-r.left)/r.width*vb.width, vb.y+(e.clientY-r.top)/r.height*vb.height]; }
function cornerAt(svg, e, street){
  var p=svgPt(svg,e), g=graph(), zz=(svg===svgD?Z:(MM.z||1)), n=nearest(p[0],p[1],2,16/zz);
  if(n<0) return null; var nm=Object.keys(g.names[n]); if(street && nm.indexOf(street)<0) return null; return nm;
}

/* routes: from a building along the streets to each building it connects with */
var hotB=null;
function drawRoutes(svg, id, walkUnit){
  var g=svg._r; if(!g) return; g.innerHTML='';
  function bl(svg, id){ return svg===svgD ? document.getElementById('node-'+id) : svg.querySelector('.pl-bld[data-id="'+id+'"]'); }
  function all(svg){ return svg===svgD ? document.querySelectorAll('#world .node') : svg.querySelectorAll('.pl-bld'); }
  function idOf(e){ return e.getAttribute('data-id') || (e.id||'').replace(/^node-/,''); }
  all(svg).forEach(function(b){ b.classList.remove('pal-hot','pal-dim'); });
  if(id==null && walkUnit==null) return;
  function path(a,b){ var A=lot(P.at[a]), B=lot(P.at[b]); if(!A||!B) return null; var r=route(entrance(a), entrance(b)), gg=graph();
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
    el('path',{'class':'pl-route', d:d, stroke:col},g); el('path',{'class':'pl-route-sh', d:d},g);
    var ob=bl(svg, other); if(ob) ob.classList.add('pal-hot'); });
}
function bAt(t){ if(!t||!t.closest) return null; var b=t.closest('.pl-bld[data-id]'); if(b) return b.getAttribute('data-id');
  var n=t.closest('#world .node[id^="node-"]'); if(n && !n.classList.contains('focused')){ var id=n.id.slice(5); return isB(id)?id:null; } return null; }
document.addEventListener('mouseover', function(e){
  if(!palaceOn() || dragging) return;
  var id=bAt(e.target), st=e.target.closest && e.target.closest('#palace-svg .pl-hit'), du=e.target.closest && e.target.closest('#palace-svg .pl-dist');
  var lm=e.target.closest && e.target.closest('#palace-svg .pl-lmb');
  clearTimeout(tipT);
  if(lm){ tipT=setTimeout(function(){ showTip(lmTip(lm), e.clientX, e.clientY); }, 90); return; }
  if(id){ tipT=setTimeout(function(){ showTip(bTip(id), e.clientX, e.clientY); if(!focused()){ hotB=id; drawRoutes(svgD, id); } }, 110); return; }
  if(du){ var u=+du.getAttribute('data-u'); tipT=setTimeout(function(){ if(!focused()) drawRoutes(svgD, null, u);
    showTip('<b>'+esc(du.textContent)+'</b><small>'+(((P.units||[])[u]||[]).length)+' buildings · the dotted line is the walk through them in order · click to go there</small>', e.clientX, e.clientY); }, 110); return; }
  if(st){ var nm=st._n; tipT=setTimeout(function(){ var c=cornerAt(svgD, e, nm); showTip('<b>'+esc(c?c.join(' & '):nm)+'</b>', e.clientX, e.clientY); }, 90); return; }
  tipT=setTimeout(function(){ hideTip(); if(!focused() && hotB){ hotB=null; drawRoutes(svgD, null); } else if(!focused() && svgD && svgD._r && svgD._r.firstChild) drawRoutes(svgD, null); }, 120);
});
document.addEventListener('mousemove', function(e){
  if(!tip || tip.style.display!=='block') return; moveTip(e.clientX, e.clientY);
  var st=e.target.closest && e.target.closest('#palace-svg .pl-hit'); if(st){ var c=cornerAt(svgD, e, st._n); var b=tip.querySelector('b'); if(b) b.textContent=c?c.join(' & '):st._n; }
});
/* a click on a building enlarges it (the map comes closer first); a click on the enlarged card, or a double click, goes inside */
function enlarge(id){
  var L=lot(P.at[id]); if(!L) return; hideTip();
  if(Z<.85) flyMap(L[0], L[1], 1.05, function(){ window.enterFocus(id); setTimeout(function(){ drawRoutes(svgD, id); }, 30); });
  else { window.enterFocus(id); setTimeout(function(){ drawRoutes(svgD, id); }, 30); }
}
document.addEventListener('click', function(e){
  if(!palaceOn() || de.classList.contains('alto-editing') && moved) return;
  var lmc=e.target.closest && e.target.closest('#palace-svg .pl-lmb.has-page');
  if(lmc){ e.stopPropagation(); hideTip(); openPage(lmc.getAttribute('data-page')); return; }
  var du=e.target.closest && e.target.closest('#palace-svg .pl-dist');
  if(du){ e.stopPropagation(); var d=(P.d||[]).filter(function(q){ return q.u===+du.getAttribute('data-u'); })[0]; if(d) flyToBox(d.box); return; }
  var id=bAt(e.target); if(!id) return;
  e.stopPropagation(); e.preventDefault();
  if(e.detail>=2){ window.showDetail('node', id); return; }
  enlarge(id);
}, true);
function flyToBox(b){ var cv=document.getElementById('canvas'); if(!cv) return;
  var z=Math.min(1.3, Math.min(cv.clientWidth/((b[2]-b[0])+260), cv.clientHeight/((b[3]-b[1])+260)));
  flyMap((b[0]+b[2])/2, (b[1]+b[3])/2, Math.max(z, zmin())); }
document.addEventListener('dblclick', function(e){
  if(!palaceOn() || focused() || bAt(e.target)) return;
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
    h+='<div class="pk-row" data-u="'+d.u+'"><span class="pk-sw" style="background:'+pm.colorRaw+'"></span><div><b>'+esc(pm.numeral+' · '+(pm.label.split(' — ')[1]||pm.label))+'</b><small>'+esc(d.n)+'</small></div></div>'; });
  var sw=function(s){ return '<svg width="26" height="12" style="flex:none">'+s+'</svg>'; };
  h+='<div class="pk-sep"></div>';
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#59616c" stroke-width="7" stroke-dasharray="1.4 4.6"/><line x1="1" y1="6" x2="25" y2="6" stroke="#59616c" stroke-width="2.6"/>')+'<div>Railway <small>above ground — the cross-ties mark a train line</small></div></div>';
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="#3d6fb6" stroke-width="2.6" stroke-dasharray="6 4" opacity=".7"/>')+'<div>Subway or tunnel</div></div>';
  h+='<div class="pk-row">'+sw('<circle cx="13" cy="6" r="5" fill="#fff" stroke="#2f3338" stroke-width="2.5"/><circle cx="13" cy="6" r="2" fill="#2f3338"/>')+'<div>Station <small>a big ring is a hub</small></div></div>';
  h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="var(--pal-trail)" stroke-width="2.6" stroke-dasharray="6 3"/>')+'<div>Trail</div></div>';
  var rk={}; (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).forEach(function(x){ if(x && x[2]!=='spine') rk[x[2]]=1; });
  Object.keys(rk).forEach(function(r){ var col=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[r])||'var(--accent)', lb=(typeof REL_LABELS!=='undefined'&&REL_LABELS[r])||r;
    h+='<div class="pk-row">'+sw('<line x1="1" y1="6" x2="25" y2="6" stroke="'+col+'" stroke-width="4" stroke-dasharray="7 4"/>')+'<div>Route: '+esc(lb)+'</div></div>'; });
  h+='<small style="margin-top:4px">Point at a building for its name and its routes; click to enlarge it, again to go inside. Point at a street for its name.</small>';
  h+='<div class="pk-credit">Map data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors</div></div>';
  var z='<div class="pc-z"><button data-z="in" title="Closer (⌘ +)">+</button><button data-z="out" title="Farther (⌘ −)">−</button><button data-z="fit" title="The whole city (⌘ 0)">⤢ City</button></div>';
  c.innerHTML=z; document.body.appendChild(c);
  /* the key is a toggle floating at the top left (key_toggle.py); its rows act like the buttons' neighbours did */
  var k=document.createElement('div'); k.id='pal-key'; k.innerHTML=h;
  window._altoKeyToggle(k, 'alto-palace-key', 'Key to the city');
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
  if(elev) return; elev=document.createElement('div'); elev.id='pal-elev'; document.body.appendChild(elev);
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
  var h='<div class="pe-roof" style="background:'+c+'">'+esc(num(b))+'<span class="pe-sec"> · '+esc(PHASE_META[ACT[b]]?(PHASE_META[ACT[b]].label.split(' — ')[1]||PHASE_META[ACT[b]].label):'')+'</span><small>'+esc(title(b))+'</small></div><div class="pe-shaft"><div class="pe-car"></div>';
  for(var i=s.length-1;i>=0;i--){ var f=s[i];
    h+='<button class="pe-fl'+(f===id?' on':'')+'" data-id="'+esc(f)+'"><span class="pe-n">'+(i===0?'G':i)+'</span><span class="pe-t">'+esc(title(f))+'</span>'
      +(i>0 && editing() && !mob()?'<span class="pe-out" data-id="'+esc(f)+'" title="Let this floor out into a building of its own">⇱</span>':'')+'</button>'; }
  var where=(P.near||{})[b];
  h+='</div><button class="pe-street">⌂ Out to the street<small>'+esc(where||'')+'</small></button>';
  elev.innerHTML=h; place(); carTo(id, true);
}
function carTo(id, now){ if(!elev) return; var row=elev.querySelector('.pe-fl[data-id="'+id+'"]'), car=elev.querySelector('.pe-car'); if(!row||!car) return;
  if(now){ car.style.transition='none'; car.style.top=(row.offsetTop+row.offsetHeight/2-15)+'px'; car.offsetTop; car.style.transition=''; }
  else car.style.top=(row.offsetTop+row.offsetHeight/2-15)+'px';
  elev.querySelectorAll('.pe-fl').forEach(function(r){ r.classList.toggle('on', r===row); });
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
    var i=a; var tick=setInterval(function(){ i+=up?1:-1; ind.textContent=(up?'▲ ':'▼ ')+(i===0?'G':i); if(i===b){ clearInterval(tick); } }, per);
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
    box.innerHTML='<div class="pm-scroll"></div><button class="pm-close" aria-label="Close">✕</button><div class="pm-zoom"><button data-z="in">+</button><button data-z="out">−</button></div><div class="pm-card"></div>';
    document.body.appendChild(box); MM.box=box;
    MM.svg=el('svg',{viewBox:(-MX)+' '+(-MY)+' '+VW+' '+VH, preserveAspectRatio:'none', id:'palace-svg-m', 'class':'pal-svg'}); MM.svg._sid='m'; drawCity(MM.svg);
    MM.svg.style.setProperty('--pz', MM.z);
    box.querySelector('.pm-scroll').appendChild(MM.svg);
    box.querySelector('.pm-close').addEventListener('click', mmapClose);
    box.querySelector('.pm-zoom').addEventListener('click', function(e){ var b=e.target.closest('[data-z]'); if(!b) return; var sc=box.querySelector('.pm-scroll'); mz(MM.z*(b.getAttribute('data-z')==='in'?1.6:1/1.6), sc.clientWidth/2, sc.clientHeight/2); });
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
      var du=e.target.closest('.pl-dist'); if(du){ drawRoutes(MM.svg, null, +du.getAttribute('data-u')); card.innerHTML='<b>'+esc(du.textContent)+'</b><small>The dotted line walks through its buildings in order.</small>'; card.classList.add('on'); return; }
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
  MM.svg.setAttribute('width', VW*z); MM.svg.setAttribute('height', VH*z); MM.svg.style.setProperty('--pz', z);
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
  dragging={id:id, x:e.clientX, y:e.clientY}; moved=false; hideTip();
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
    showTip('<b>Make it a floor of '+esc(num(onto)+' '+title(onto))+'</b><small>Its own floors come with it.</small>', e.clientX, e.clientY); }
  else { var key=freeLot(p[0], p[1], id), K=lot(key); if(K && Math.hypot(K[0]-p[0],K[1]-p[1])<140){ dragging.key=key;
      slot=el('rect',{'class':'pl-slot', x:K[0]-K[2]/2, y:K[1]-K[3]/2, width:K[2], height:K[3], rx:3, transform:'rotate('+K[4]+' '+K[0]+' '+K[1]+')'},svgD._r); }
    hideTip(); }
}, true);
window.addEventListener('mouseup', function(e){
  if(!dragging) return; var d=dragging; dragging=null; if(slot){ slot.remove(); slot=null; } hideTip();
  if(!moved) { return; }
  e.preventDefault(); e.stopImmediatePropagation();
  setTimeout(function(){ moved=false; }, 50);
  var ok=false;
  if(d.onto) ok=chg([['pf|'+d.id, d.onto], ['p|'+d.id+'|lot', null]]);
  else if(d.key && d.key!==P.at[d.id]) ok=chg([['p|'+d.id+'|lot', d.key]]);
  if(!ok) window._altoPalaceRefresh();
}, true);
})();
"""
