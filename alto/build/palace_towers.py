"""Towers of the Mind Palace: Center City's big skyscrapers as landmark buildings, and the
elevator a unit can take from one.

- The art (`ART`, `MATCH`, `FLOORS`): One and Two Liberty Place, Comcast Center, Comcast Technology
  Center, BNY Mellon Center, Three Logan Square, Cira Centre and FMC Tower, each a tall narrow
  elevation in the same glass look as the other landmarks (palace_landmarks._Art), each its own
  silhouette: a crown, a taper, a notch, a sloped glass wall.
- The assignment. A landmark in `brief.palace.buildings` may carry `unit` (0-based section) and
  `floors` (the real floor count; the table below knows the famous ones). That unit's buildings then
  stand INSIDE the tower: its first building (the hub) is the tower, standing on the landmark's
  block, and every other building of the unit becomes a floor of it, numbered up the real tower
  between floor 2 and the roof. `apply_towers` does it to the nodes at build time (the stored
  nodes are never touched, so taking `unit` off puts the buildings back on their lots).
"""
from __future__ import annotations

import re

from .palace_landmarks import _Art, _f

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
def _curtain(a: _Art, x, y, w, h, fh=5.2, mw=6.4, m=None):
    """A glass curtain wall over a face: a floor line every fh, a mullion every mw."""
    hs = "".join(f"M{_f(x)} {_f(y + k * fh)}h{_f(w)}" for k in range(1, int((h - 1) / fh) + 1))
    vs = "".join(f"M{_f(x + k * mw)} {_f(y)}v{_f(h)}" for k in range(1, int((w - 1) / mw) + 1))
    a.add(f'<path class="lz-mu" d="{hs}{vs}" style="stroke-width:.6px"/>')


def _glints(a: _Art, x, y, w, h):
    a.add(f'<path class="lz-hi" d="M{_f(x + w * .14)} {_f(y + h * .94)}l{_f(w * .5)} {_f(-h * .36)}M{_f(x + w * .46)} {_f(y + h * .94)}l{_f(w * .5)} {_f(-h * .36)}"/>')


def _shaft(a: _Art, x, y, w, h, m, d=8.0, fh=5.2, mw=6.4):
    a.solid(x, y, w, h, m, d=d)
    _curtain(a, x, y, w, h, fh, mw)
    _glints(a, x, y, w, h)


def _podium(a: _Art, x, w, base, m="granite", h=20, d=8.0):
    a.solid(x, base - h, w, h, m, d=d, course="ashlar")
    a.add(f'<path class="lz-win" d="M{_f(x + 5)} {_f(base - h + 6)}h{_f(w - 10)}v{_f(h - 12)}h{_f(-(w - 10))}z" opacity=".8"/>')
    a.add(f'<path class="lz-door" d="M{_f(x + w / 2 - 5)} {_f(base)}v-10a5 5 0 0 1 10 0v10z"/>')
    a.front(x - 2, base - h - 1.6, w + 4, 2.4, "trim")


def _lib1() -> dict:
    """One Liberty Place: a pale-glass shaft with deep setbacks, then the crown of diagonal
    facets that comes to a point, with a mast."""
    a = _Art(100, 262)
    base = 252
    a.shadow(6, 94, base, 8)
    _podium(a, 10, 80, base)
    _shaft(a, 26, 96, 48, base - 20 - 96, "glass")
    # the setbacks: two narrower stages
    a.front(24, 94, 52, 2.4, "trim")
    _shaft(a, 31, 62, 38, 34, "glass", d=7)
    a.front(29, 60.4, 42, 2.2, "trim")
    # the crown: facets cut on the diagonal, the left lit, the right in shade, the side face behind
    a.face([(69, 60), (76, 56.5), (76, 38), (62.5, 14), (57, 4), (50, 8)], "glass", "s")
    a.poly([(31, 60), (31, 40), (50, 6), (50, 60)], "trim")
    a.poly([(50, 6), (69, 40), (69, 60), (50, 60)], "granite")
    a.line("M31 40L50 60M69 40L50 60M40.5 23L50 60M59.5 23L50 60M31 50h38M36 32h28M43 18h14")
    a.add('<path class="lz-hi" d="M34 56l14 -44"/>')
    a.line("M50 6V-2")
    return a.out()


def _lib2() -> dict:
    """Two Liberty Place: a green-glass shaft under twin crowns, two stepped peaks side by side."""
    a = _Art(92, 236)
    base = 226
    a.shadow(6, 86, base, 8)
    _podium(a, 8, 76, base, h=18)
    _shaft(a, 22, 70, 48, base - 18 - 70, "green", fh=5.6, mw=6.0)
    # the twin crown: two slim stepped peaks and the notch between
    for x in (22, 48):
        a.solid(x, 46, 22, 24, "green", d=6, top=False)
        a.front(x - 1, 44.4, 24, 2.2, "trim")
        a.poly([(x + 1, 44), (x + 4, 24), (x + 11, 8), (x + 18, 24), (x + 21, 44)], "trim")
        a.line(f"M{x + 11} 8V44M{x + 4} 24h14")
    a.face([(70, 70), (76, 67), (76, 21), (62.5, 5), (59, 8)], "green", "s")
    a.line("M33 8V0M59 8V0")
    return a.out()


def _ccc() -> dict:
    """Comcast Center: a clean, flat-topped glass slab; low at its foot a wall of glass slopes out
    over the entrance, and a fine grid of mullions runs the whole height."""
    a = _Art(84, 244)
    base = 234
    a.shadow(4, 78, base, 8)
    _shaft(a, 18, 30, 46, base - 30 - 22, "glass", d=9, fh=4.8, mw=5.8)
    a.front(16, 28.2, 50, 2.6, "trim")
    a.add('<path class="lz-win" d="M20 33h42v4H20z" opacity=".9"/>')
    # the sloped glass wall at the foot: leaning out over the lobby
    a.face([(64, base - 22), (73, base - 26.5), (73, base - 6), (64, base)], "glass", "s")
    a.poly([(6, base), (18, base - 22), (64, base - 22), (78, base)], "glass")
    a.add(f'<path class="lz-mu" d="M12 {base - 8}H72M16 {base - 15}H69M30 {base - 22}L24 {base}M44 {base - 22}L44 {base}M58 {base - 22}L64 {base}"/>')
    a.add(f'<path class="lz-door" d="M37 {base}v-9h10v9z"/>')
    a.front(4, base, 76, 3, "granite")
    return a.out()


def _ctc() -> dict:
    """Comcast Technology Center: a glass tower that tapers as it climbs in long folded planes, its
    top cut with a deep notch and capped by a crown of glass."""
    a = _Art(96, 270)
    base = 260
    a.shadow(6, 90, base, 8)
    _podium(a, 8, 78, base, "granite", h=16)
    # the shaft narrows: a tapering front, the shaded side behind it
    a.face([(70, 12), (78, 8), (80, base - 16 - 4), (74, base - 16)], "teal", "s")
    a.poly([(24, base - 16), (30, 12), (70, 12), (74, base - 16)], "teal")
    n = 30
    ln = ""
    for k in range(1, n):
        t = k / n
        y = 12 + (base - 16 - 12) * t
        ln += f"M{_f(30 - 6 * t)} {_f(y)}H{_f(70 + 4 * t)}"
    for k in range(1, 9):
        t = k / 9
        ln += f"M{_f(30 + 40 * t)} 12L{_f(24 + 50 * t)} {base - 16}"
    a.add(f'<path class="lz-mu" d="{ln}" style="stroke-width:.55px"/>')
    # the folds: one lit plane running up the front
    a.add(f'<path class="lz-hi" d="M40 {base - 24}L38 24M60 {base - 24}L63 24"/>')
    # the notch at the top and the crown above it
    a.poly([(30, 12), (30, 22), (50, 36), (70, 22), (70, 12), (60, 12), (50, 26), (40, 12)], "glass")
    a.add('<path class="lz-win" d="M40 12L50 26L60 12z" opacity=".55"/>')
    a.poly([(34, 12), (38, 4), (44, 12)], "trim")
    a.poly([(56, 12), (62, 4), (66, 12)], "trim")
    a.line("M30 22L50 36L70 22")
    return a.out()


def _bny() -> dict:
    """BNY Mellon Center (the old Mellon Bank Center): a dark granite shaft with a stepped crown,
    each stage narrower, ending in a pyramid roof."""
    a = _Art(96, 240)
    base = 230
    a.shadow(6, 90, base, 8)
    _podium(a, 8, 78, base, "granite", h=20)
    a.solid(22, 72, 52, base - 20 - 72, "granite", d=9)
    ps = "".join(f"M{_f(26 + 6.4 * k)} 74v{base - 20 - 76}" for k in range(7))
    a.add(f'<path class="lz-win" d="{ps}" style="stroke:var(--lz-win);stroke-width:3.4;opacity:.8"/>')
    a.add(f'<path class="lz-mu" d="M22 90h52M22 130h52M22 170h52"/>')
    a.front(20, 70.4, 56, 2.4, "trim")
    for i, (x, w, y, h) in enumerate([(28, 40, 50, 22), (34, 28, 34, 16)]):
        a.solid(x, y, w, h, "granite", d=8 - i)
        a.front(x - 1, y - 1.6, w + 2, 2.2, "trim")
        a.add(f'<path class="lz-win" d="M{x + 4} {y + 4}h{w - 8}v{h - 8}h{-(w - 8)}z" opacity=".7"/>')
    a.face([(62, 34), (70, 30), (56, 8)], "granite", "s")
    a.poly([(34, 34), (48, 6), (62, 34)], "trim")
    a.line("M48 6V34M41 20h14")
    a.line("M48 6V-1")
    return a.out()


def _tls() -> dict:
    """Three Logan Square: a pale tower of horizontal bands, a chamfered corner, the flat roof held
    up by a row of columns and a deep recess."""
    a = _Art(92, 232)
    base = 222
    a.shadow(6, 86, base, 8)
    _podium(a, 8, 76, base, "sand", h=18)
    a.solid(20, 40, 52, base - 18 - 40, "sand", d=9)
    bands = "".join(f"M20 {_f(46 + 5.6 * k)}h52" for k in range(int((base - 18 - 46) / 5.6)))
    a.add(f'<path class="lz-mu" d="{bands}" style="stroke-width:.7px"/>')
    a.add(f'<path class="lz-win" d="' + "".join(f"M20 {_f(48.6 + 11.2 * k)}h52v3h-52z" for k in range(int((base - 18 - 48) / 11.2))) + '" opacity=".75"/>')
    a.add('<path class="lz-hi" d="M24 200L52 120M42 200L70 120"/>')
    # the chamfered corner: a lit diagonal down the left edge
    a.poly([(20, 40), (26, 40), (26, base - 18), (20, base - 18)], "trim")
    # the crown: a recessed top with a ring of columns
    a.front(18, 38.4, 56, 2.6, "trim")
    a.solid(24, 22, 44, 17, "sand", d=8)
    a.add('<path class="lz-win" d="M27 25h38v11H27z" opacity=".9"/>')
    a.cols(29, 25, 6, 6.6, 3.2, 11, cap=False)
    a.front(22, 20.4, 48, 2.2, "trim")
    return a.out()


def _cira() -> dict:
    """Cira Centre: a glass box whose faces are cut on the diagonal, a lattice of crossing
    mullions and the top sliced into one long sloping plane."""
    a = _Art(92, 192)
    base = 182
    a.shadow(6, 86, base, 8)
    _podium(a, 10, 72, base, "glass", h=14)
    # the sloping top: higher at the right than the left
    a.face([(70, 54), (79, 49.5), (79, base - 18), (70, base - 14)], "glass", "s")
    a.poly([(22, base - 14), (22, 70), (70, 40), (70, base - 14)], "glass")
    lat = ""
    for k in range(-4, 9):
        lat += f"M{_f(22 + k * 8)} {base - 14}L{_f(22 + k * 8 + 40)} 60M{_f(22 + k * 8)} 60L{_f(22 + k * 8 + 40)} {base - 14}"
    a.add(f'<clipPath id="cira-c-{{s}}"><path d="M22 {base - 14}V70L70 40V{base - 14}z"/></clipPath>'
          f'<path class="lz-mu" clip-path="url(#cira-c-{{s}})" d="{lat}" style="stroke-width:.6px"/>')
    a.add(f'<path class="lz-hi" d="M26 {base - 22}L66 60"/>')
    a.add('<path class="lz-tp lz-t-glass" d="M22 70L70 40l9 -4.5L31 65.5z"/>')
    a.line("M22 70L70 40")
    return a.out()


def _fmc() -> dict:
    """FMC Tower: a slim bronze-glass shaft that steps in twice and ends in an open lattice crown
    with a spire."""
    a = _Art(84, 224)
    base = 214
    a.shadow(6, 78, base, 8)
    _podium(a, 8, 68, base, "bronze", h=16)
    _shaft(a, 24, 64, 36, base - 16 - 64, "bronze", d=8, fh=5.0, mw=6.0)
    a.front(22, 62.4, 40, 2.2, "trim")
    _shaft(a, 29, 42, 26, 22, "bronze", d=7, fh=5.0, mw=6.0)
    a.front(27, 40.4, 30, 2.2, "trim")
    # the open crown: four stays of a lattice and the spire
    a.face([(55, 40), (62, 36.5), (51, 14)], "bronze", "s")
    a.poly([(29, 40), (42, 8), (55, 40)], "bronze")
    a.add('<path class="lz-win" d="M36 40L42 18L48 40z" opacity=".8"/>')
    a.line("M29 40L42 8L55 40M35 40L42 14L49 40M42 8V-2M33 28h18")
    return a.out()


def build_art() -> dict:
    return {"lib1": _lib1(), "lib2": _lib2(), "ccc": _ccc(), "ctc": _ctc(), "bny": _bny(),
            "tls": _tls(), "cira": _cira(), "fmc": _fmc()}


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
        roots = [n for n in nodes if n.act == u and not n.parent]
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
    return warnings


def floor_numbers(floors: list, top: int) -> dict:
    """{floor id: its real floor number}: the floors in reading order spread over 2..top (gaps allowed)."""
    m = len(floors)
    if not m:
        return {}
    top = max(top, m + 1)
    if m == 1:
        return {floors[0]: top}
    return {f: 2 + round(i * (top - 2) / (m - 1)) for i, f in enumerate(floors)}


def tower_data(b, units, floors) -> tuple:
    """({hub id: {n: landmark name, u: unit, top: real floors}}, {floor id: real floor number}) for the page."""
    tw, fn = {}, {}
    for u, (s, lm) in placed(b).items():
        hub = units[u][0] if u < len(units) and units[u] else None
        if not hub:
            continue
        fl = floors.get(hub, [])
        top = max(real_floors(s), len(fl) + 1)
        tw[hub] = {"n": lm["n"], "u": u, "top": top}
        fn.update(floor_numbers(fl, top))
    return tw, fn


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
        x0, y0, x1, y1 = lm["box"]
        w0, h0 = (x1 - x0) - 28, (y1 - y0) - 28                    # the card (palace_landmarks: ins 14) ...
        nw = min(w0, h0 * .55)                                      # ... tall and narrow, centred
        w = max(30.0, min(lw, (w0 - nw) / 2 - 4))
        h = lh * w / lw
        left = x0 + 14 + (w0 - nw) / 2                              # the chip stands left of it, a little over its edge
        bid = len(blocks)
        blocks.append({"id": bid, "lots": [[round(left + 10 - w / 2, 1), round(y0 + 14 + 22 + h / 2, 1), round(w, 1), round(h, 1), 0]]})
        at[hub] = f"{bid}.0"
    return blocks
