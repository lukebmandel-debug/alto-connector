"""Towers of the Mind Palace: Center City's big skyscrapers as landmark buildings, and the
elevator a unit can take from one.

- The art (`ART`, `MATCH`, `FLOORS`): One and Two Liberty Place, Comcast Center, Comcast Technology
  Center, BNY Mellon Center, Three Logan Square, Cira Centre and FMC Tower, each a tall narrow
  elevation drawn by the building generator (palace_skyline.py) at the one scale every building
  shares, each its own silhouette: a crown, a taper, a notch, a sloped glass wall.
- The assignment. A landmark in `brief.palace.buildings` may carry `unit` (0-based section) and
  `floors` (the real floor count; the table below knows the famous ones). That unit's buildings then
  stand INSIDE the tower: its first building (the hub) is the tower, standing on the landmark's
  block, and every other building of the unit becomes a floor of it, numbered up the real tower
  between floor 2 and the roof. `apply_towers` does it to the nodes at build time (the stored
  nodes are never touched, so taking `unit` off puts the buildings back on their lots).
"""
from __future__ import annotations

import math
import re


# name pattern → (art key, real floors).  Floors as counted by the Skyscraper Center / Wikipedia.
TOWERS = [
    ("lib1", r"one liberty place|liberty place one|liberty one", 61),
    ("lib2", r"two liberty place|liberty place two|liberty two", 58),
    ("ccc", r"comcast center(?! tech)|comcast building", 57),
    ("ctc", r"comcast tech", 60),
    ("bny", r"bny mellon|mellon bank center|mellon center", 54),
    ("tls", r"three logan square|3 logan square", 55),
    ("cira", r"cira centre(?! south)|cira center(?! south)", 29),
    ("fmc", r"fmc tower", 49),
]
MATCH = [[k, p] for k, p, _ in TOWERS]
FLOORS = {k: n for k, _, n in TOWERS}


def tower_key(name: str) -> str:
    for k, p, _ in TOWERS:
        if re.search(p, name or "", re.I):
            return k
    return ""


def real_floors(spec: dict) -> int:
    """The real number of floors a landmark entry stands for: its own `floors`, else the famous count."""
    n = spec.get("floors")
    if isinstance(n, int) and not isinstance(n, bool) and n >= 2:
        return n
    return FLOORS.get(tower_key(spec.get("label") or spec.get("name") or ""), 30)


# ── the art ─────────────────────────────────────────────────────────────────
# Drawn by palace_skyline.py from each tower's parts in real metres, all at one scale (SCALE px per
# metre): Comcast Technology Center (342 m) tallest, Cira Centre (133 m) shortest, Two Liberty Place
# (258 m) 0.9 of One Liberty Place (288 m) whatever cells their outlines cover.
def build_art() -> dict:
    from .palace_skyline import LANDMARKS, build
    return {k: build(LANDMARKS[k]()) for k in FLOORS}


# ── the assignment ──────────────────────────────────────────────────────────
def specs(pal: dict) -> list:
    """The landmark entries that carry a unit, [{name, label?, unit, floors}] with the real count filled in."""
    out = []
    for s in (pal or {}).get("buildings") or []:
        if isinstance(s, dict) and s.get("unit") is not None:
            out.append({**s, "floors": real_floors(s)})
    return out


def check_buildings(pal: dict, n_acts: int) -> None:
    """Validation of the landmark entries (palace.check_palace calls it)."""
    from .brief import BriefError
    seen = {}
    for i, s in enumerate(pal.get("buildings") or []):
        if not isinstance(s, dict) or not str(s.get("name") or "").strip():
            raise BriefError(f"palace.buildings[{i}]: needs a name (the landmark's name on the map)")
        for k in ("label", "page"):
            if k in s and not isinstance(s[k], str):
                raise BriefError(f"palace.buildings[{i}].{k}: must be text")
        if "floors" in s and s["floors"] is not None and "unit" not in s:
            raise BriefError(f"palace.buildings[{i}]: floors only means something with a unit (the section "
                             "whose buildings become this tower's floors)")
        u = s.get("unit")
        if u is None:
            continue
        if not isinstance(u, int) or isinstance(u, bool) or not 0 <= u < n_acts:
            raise BriefError(f"palace.buildings[{i}]: unit {u!r} is not a section index (0..{n_acts - 1})")
        f = s.get("floors")
        if f is not None and (not isinstance(f, int) or isinstance(f, bool) or not 2 <= f <= 250):
            raise BriefError(f"palace.buildings[{i}]: floors must be a whole number from 2 to 250")
        if u in seen:
            raise BriefError(f"palace.buildings[{i}]: section {u} is already the tower of "
                             f"{seen[u]!r} — a section has one tower")
        seen[u] = s["name"]


def placed(b) -> dict:
    """{unit: (spec, landmark)} for the towers that made it onto the map (the landmark found, drawn)."""
    pal = b.palace or {}
    sp = specs(pal)
    if not sp or not pal.get("data_z"):
        return {}
    from .palace import unpack
    lms = {l.get("n"): l for l in (unpack(pal["data_z"]).get("map") or {}).get("landmarks", []) if l.get("box")}
    out = {}
    for s in sp:
        lm = lms.get(s.get("label") or s["name"])
        if lm:
            out[s["unit"]] = (s, lm)
    return out


def apply_towers(b, nodes) -> list:
    """Make each assigned unit's buildings the floors of its tower, in place on `nodes`. Returns warnings."""
    if b.mode != "palace":
        return []
    warnings = []
    pal = b.palace or {}
    on_map = placed(b)
    for s in specs(pal):
        if s["unit"] not in on_map:
            warnings.append(f"palace: {s.get('label') or s['name']!r} is the tower of section {s['unit']} but "
                            "is not on the map (run set_up_palace again so the landmark is found) — "
                            "that section keeps its buildings")
    for u, (s, lm) in on_map.items():
        out = {k for k, h in (b.placement or {}).items() if isinstance(h, dict) and h.get("out")}   # floors let out of the tower
        roots = [n for n in nodes if n.act == u and not n.parent and n.id not in out]
        if not roots:
            from .brief import Node
            title = s.get("label") or s["name"]
            hub = Node(id=f"tower-{u}", act=u, tag="Tower", title=title, desc="")
            first = next((i for i, n in enumerate(nodes) if n.act >= u), len(nodes))
            nodes.insert(first, hub)
            roots = [hub]
            warnings.append(f"palace: section {u} had no building; {title} stands there as an empty tower")
        hub = roots[0]
        for n in roots[1:]:
            n.parent = hub.id
            b.__dict__.setdefault("_tower_kids", set()).add(n.id)       # (the page tells these from a floor's own children)
    return warnings


def floor_numbers(floors: list, top: int, fixed: dict | None = None) -> dict:
    """{floor id: its real floor number}: the floors in reading order spread over 2..top (gaps allowed).
    `fixed` {floor id: number} are numbers the user chose; the other floors keep their place in the
    spread, moving up to the next free number if a chosen one sits on theirs."""
    m = len(floors)
    if not m:
        return {}
    top = max(top, m + 1)
    spread = {floors[0]: top} if m == 1 else {f: 2 + round(i * (top - 2) / (m - 1)) for i, f in enumerate(floors)}
    fixed = {f: int(n) for f, n in (fixed or {}).items() if f in spread and isinstance(n, int) and not isinstance(n, bool) and n >= 2}
    if not fixed:
        return spread
    used = set(fixed.values())
    out = dict(fixed)
    for f in floors:
        if f in out:
            continue
        n = spread[f]
        while n in used:
            n += 1
        used.add(n)
        out[f] = n
    return out


def tower_data(b, units, floors) -> tuple:
    """({hub id: {n: landmark name, u: unit, top: real floors}}, {floor id: real floor number}) for the page.
    The floors of each tower are put in floor order (in place)."""
    tw, fn = {}, {}
    pl = b.placement or {}
    for u, (s, lm) in placed(b).items():
        hub = units[u][0] if u < len(units) and units[u] else None
        if not hub:
            continue
        fl = floors.get(hub, [])
        top = max(real_floors(s), len(fl) + 1)
        fixed = {f: (pl.get(f) or {}).get("fno") for f in fl}
        nums = floor_numbers(fl, top, {f: n for f, n in fixed.items() if n})
        top = max([top] + list(nums.values()))
        fl.sort(key=lambda f: nums[f])
        tw[hub] = {"n": lm["n"], "u": u, "top": top}
        fn.update(nums)
    return tw, fn


def landmark_state(b, m: dict) -> dict:
    """What the page needs to house a unit in a landmark: {lm: {name: its stored {unit, floors} or None}, top: {name: the
    real floor count it would have}} for each landmark with a block on the map."""
    pal = b.palace or {}
    cur = {}
    for u, (s, lm) in placed(b).items():
        raw = next((e for e in pal.get("buildings") or [] if isinstance(e, dict) and e.get("unit") == u), {})
        cur[lm["n"]] = {"unit": u, "floors": raw.get("floors") if isinstance(raw.get("floors"), int) else None}
    names = [l["n"] for l in m.get("landmarks", []) if l.get("box") and l.get("n")]
    return {"lm": {n: cur.get(n) for n in names},
            "top": {n: (real_floors({"name": n}) if n not in cur or cur[n]["floors"] is None else cur[n]["floors"]) for n in names}}


def lm_dx(m: dict) -> dict:
    """{landmark name: dx} the page slides each tower card by (palace_skyline.stagger; palace_landmarks plan() mirrors it)."""
    from .palace_skyline import stagger
    return stagger(m.get("landmarks", []), lm_art, lambda l: lm_art(l)["_k"] in FLOORS or (lm_art(l)["_k"].startswith(("g-", "ct-")) and float(l.get("hm") or 0) >= 60))


def lm_art(l: dict) -> dict:
    """The art a map landmark record gets, with its key as "_k" (the page's keyOf)."""
    from .palace_landmarks import ART, art_key
    k = art_key(l)
    return {**(ART.get(k) or ART["gen"]), "_k": k}


def tower_lots(m: dict, blocks: list, at: dict, tw: dict) -> list:
    """A tower's building chip stands in the corner of its landmark's card: one more block, one lot,
    appended after the buildings have been placed (so no ordinary building can take it)."""
    if not tw:
        return blocks
    lots = [lt for bl in blocks for lt in bl["lots"][:1]][:50]
    lw = sorted(lt[2] for lt in lots)[len(lots) // 2] if lots else 24
    lh = sorted(lt[3] for lt in lots)[len(lots) // 2] if lots else 16
    blocks = list(blocks)
    for hub, t in tw.items():
        lm = next((l for l in m.get("landmarks", []) if l.get("n") == t["n"] and l.get("box")), None)
        if not lm:
            continue
        from .palace_skyline import card
        left, cy, _nw, _nh = card(lm["box"], lm_art(lm), lm)          # the tower's card (its footprint) ...
        left += lm_dx(m).get(t["n"], 0.0)                           # ... slid aside of a tower in front / behind
        w = max(30.0, min(lw, left - lm["box"][0] - 18))
        h = lh * w / lw                                             # the chip stands at the card's left edge, a little over it
        bid = len(blocks)
        cx, cy, deg = left + 10 - w / 2, cy + 22 + h / 2, 0
        if lm.get("a"):                                             # a landmark of a tilted domain (city_lattice): turned with it
            deg = lm["a"]
            r = math.radians(deg)
            x0, y0, x1, y1 = lm["box"]
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            cx, cy = mx + (cx - mx) * math.cos(r) - (cy - my) * math.sin(r), my + (cx - mx) * math.sin(r) + (cy - my) * math.cos(r)
        blocks.append({"id": bid, "lots": [[round(cx, 1), round(cy, 1), round(w, 1), round(h, 1), deg]]})
        at[hub] = f"{bid}.0"
    return blocks
