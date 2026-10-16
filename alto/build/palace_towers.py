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

import math
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
# One common scale (0.8 px per metre of real height) so the eight stand in true proportion: Comcast
# Technology Center (342 m) tallest, Cira Centre (133 m) shortest. Each canvas is its tip-to-ground
# height plus a margin. Sources: the buildings' own architects' notes (Jahn, Stern, Foster, KPF,
# Pelli Clarke Pelli) as summarised on Wikipedia / Skyscraper Center / Philadelphia YIMBY.
def _grid(a: _Art, y0, y1, l0, r0, l1, r1, fh=5.0, nv=7, sw=.6, band=0, op=1.0):
    """A curtain-wall grid over a (maybe tapered) front face, floor lines counted up from the foot:
    l0/r0 are the edges at the top y0, l1/r1 at the foot y1; every `band`th floor a pale spandrel strip."""
    hs = bs = vs = ""
    k = 1
    while y1 - k * fh > y0 + .5:
        y = y1 - k * fh
        t = (y - y0) / (y1 - y0)
        l, r = l0 + (l1 - l0) * t, r0 + (r1 - r0) * t
        hs += f"M{_f(l)} {_f(y)}H{_f(r)}"
        if band and k % band == 0:
            bs += f"M{_f(l)} {_f(y - .7)}H{_f(r)}v1.4H{_f(l)}z"
        k += 1
    for j in range(1, nv):
        u = j / nv
        vs += f"M{_f(l0 + (r0 - l0) * u)} {_f(y0)}L{_f(l1 + (r1 - l1) * u)} {_f(y1)}"
    if bs:
        a.add(f'<path class="lz-sl" d="{bs}" opacity=".7"/>')
    a.add(f'<path class="lz-mu" d="{hs}{vs}" style="stroke-width:{sw}px" opacity="{op}"/>')


def _prism(a: _Art, y0, y1, l0, r0, l1, r1, m, d=8.0, top=True):
    """A shaft whose edges may lean (an obelisk, a taper): its right face, its top, then its front."""
    dx, dy = d, -d * .5
    a.face([(r0, y0), (r0 + dx, y0 + dy), (r1 + dx, y1 + dy), (r1, y1)], m, "s")
    if top:
        a.face([(l0, y0), (l0 + dx, y0 + dy), (r0 + dx, y0 + dy), (r0, y0)], m, "t")
    a.poly([(l0, y0), (r0, y0), (r1, y1), (l1, y1)], m)


def _gable(a: _Art, xc, yb, w, wall, m, d=7.0, rise=.42):
    """One gabled stage of a crown (the ridge running back): the roof slope behind, then the lit front gable."""
    hw, ap = w / 2, yb - wall - w * rise
    a.face([(xc + hw, yb), (xc + hw + d, yb - d / 2), (xc + hw + d, yb - wall - d / 2), (xc + d, ap - d / 2),
            (xc, ap), (xc + hw, yb - wall)], m, "s")
    a.poly([(xc - hw, yb), (xc - hw, yb - wall), (xc, ap), (xc + hw, yb - wall), (xc + hw, yb)], m)
    a.line(f"M{_f(xc - hw + 2.4)} {_f(yb - wall + .4)}L{_f(xc)} {_f(ap + 3)}L{_f(xc + hw - 2.4)} {_f(yb - wall + .4)}")
    return ap


def _podium(a: _Art, x, w, base, m="granite", h=20, d=8.0):
    a.solid(x, base - h, w, h, m, d=d, course="ashlar")
    a.add(f'<path class="lz-win" d="M{_f(x + 5)} {_f(base - h + 5)}h{_f(w - 10)}v{_f(max(2, h - 11))}h{_f(-(w - 10))}z" opacity=".8"/>')
    a.add(f'<path class="lz-door" d="M{_f(x + w / 2 - 4)} {_f(base)}v-7a4 4 0 0 1 8 0v7z"/>')
    a.front(x - 2, base - h - 1.6, w + 4, 2.4, "trim")


def _lib1() -> dict:
    """One Liberty Place (Jahn, 945 ft, 61 floors): sapphire glass in horizontal bands of glass and
    pale granite, chamfered corners, three deep setbacks, then a crown of four stacked gables (straight,
    angular chevrons, after the Chrysler Building) running up to a steel spire."""
    a = _Art(84, 248)
    base = 236
    a.shadow(6, 78, base, 8)
    _podium(a, 6, 72, base, h=16)
    a.solid(17, 96, 46, base - 16 - 96, "sapphire", d=8)
    _grid(a, 96, base - 16, 17, 63, 17, 63, fh=4.4, nv=8, band=3)
    for x in (17, 57.5):                                                # the chamfered corners
        a.add(f'<path class="lz-sl" d="M{x} 96h5.5v{base - 16 - 96}h-5.5z" opacity=".34"/>')
    a.add(f'<path class="lz-hi" d="M30 {base - 24}L28 108M48 {base - 24}L46 108"/>')
    a.front(15, 94.4, 50, 2.4, "trim")
    a.solid(22, 58, 36, 38, "sapphire", d=7)
    _grid(a, 58, 96, 22, 58, 22, 58, fh=4.4, nv=6, band=3)
    a.front(20, 56.4, 40, 2.2, "trim")
    a.solid(27, 44, 26, 14, "sapphire", d=6)
    _grid(a, 44, 58, 27, 53, 27, 53, fh=4.4, nv=4)
    for xc, yb, w, wall in ((40, 44, 26, 5), (40, 34, 20, 5), (40, 26, 14, 4), (40, 19, 8, 3)):
        ap = _gable(a, xc, yb, w, wall, "sapphire", d=6)
    a.line(f"M40 {_f(ap)}V2")
    return a.out()


def _lib2() -> dict:
    """Two Liberty Place (Jahn, 848 ft, 58 floors): the same blue steel-and-glass skin over a stone
    base, a lower slab wing beside it, and a shorter, squatter crown of three gables and a stub of spire."""
    a = _Art(100, 225)
    base = 213
    a.shadow(6, 94, base, 8)
    _podium(a, 6, 88, base, h=16)
    a.solid(8, 118, 30, base - 16 - 118, "silver", d=6)                  # the slab wing, behind
    _grid(a, 118, base - 16, 8, 38, 8, 38, fh=4.4, nv=5)
    a.front(6, 116.4, 34, 2.2, "trim")
    a.solid(36, 56, 44, base - 16 - 56, "sapphire", d=8)
    _grid(a, 56, base - 16, 36, 80, 36, 80, fh=4.4, nv=8, band=3)
    a.front(36, base - 16 - 22, 44, 22, "granite", extra=' opacity=".95"')   # stone on the lower levels
    a.course(36, base - 16 - 22, 44, 22, "ashlar")
    a.add(f'<path class="lz-hi" d="M48 {base - 46}L46 70M66 {base - 46}L64 70"/>')
    a.front(34, 54.4, 48, 2.4, "trim")
    a.solid(41, 40, 34, 16, "sapphire", d=7)
    _grid(a, 40, 56, 41, 75, 41, 75, fh=4.4, nv=5)
    for yb, w, wall in ((40, 26, 4), (31, 18, 3), (24, 10, 2)):
        ap = _gable(a, 58, yb, w, wall, "sapphire", d=6)
    a.line(f"M58 {_f(ap)}V8")
    return a.out()


def _ccc() -> dict:
    """Comcast Center (Stern, 975 ft, 57 floors): a slab of lightly tinted silver glass, its corners
    and its glass-box crown in ultra-clear glass, the shaft tapering in under two notches cut near the
    top (the taller on the south), over a low three-storey glass winter garden."""
    a = _Art(78, 256)
    base = 244
    a.shadow(4, 72, base, 8)
    a.solid(6, base - 20, 66, 20, "glass", d=7)                           # the winter garden
    _grid(a, base - 20, base, 6, 72, 6, 72, fh=6.6, nv=9, sw=.7)
    a.add(f'<path class="lz-door" d="M34 {base}v-9h10v9z"/>')
    a.front(4, base - 21.6, 70, 2, "trim")
    ly = base - 20
    _prism(a, 64, ly, 16, 62, 16, 62, "silver", d=8, top=False)           # the straight shaft
    _prism(a, 24, 64, 20, 58, 16, 62, "silver", d=8)                      # tapering in under the crown
    _grid(a, 64, ly, 16, 62, 16, 62, fh=4.2, nv=10, sw=.55, op=.9)
    _grid(a, 24, 64, 20, 58, 16, 62, fh=4.2, nv=10, sw=.55, op=.9)
    a.add(f'<path class="lz-win" d="M54 38h8v26h-8zM16 54h5v8h-5z" opacity=".5"/>')   # the two notches
    a.front(16, 26, 3.2, ly - 26, "trim", ' opacity=".55"')               # ultra-clear corners
    a.front(58.8, 26, 3.2, ly - 26, "trim", ' opacity=".55"')
    a.add('<path class="lz-hi" d="M30 214L26 70M46 214L44 70"/>')
    a.solid(19, 8, 40, 16, "trim", d=7)                                   # the glass-box crown
    a.add('<path class="lz-mu" d="M19 8L59 24M59 8L19 24M39 8V24" style="stroke-width:.7px"/>')
    a.front(17, 22.4, 44, 2.2, "trim")
    return a.out()


def _ctc() -> dict:
    """Comcast Technology Center (Foster + Partners, 1,121 ft): a slim tower in lightly tinted glass
    wrapped in a zigzag corset of cross-bracing, easing in as it climbs, rising on columns from a long
    corrugated podium and ending in a lantern of glass blades."""
    a = _Art(100, 291)
    base = 279
    a.shadow(4, 96, base, 8)
    a.solid(4, base - 16, 92, 16, "granite", d=8)                         # the podium, ribbed like a train car
    a.add(f'<path class="lz-ln" d="' + "".join(f"M4 {base - 16 + 2.6 * k}h92" for k in range(1, 6)) + '" opacity=".5"/>')
    a.add(f'<path class="lz-win" d="M8 {base - 12}h18v3H8zM74 {base - 12}h18v3H74z" opacity=".7"/>')
    a.front(2, base - 17.6, 96, 2.2, "trim")
    ty, by = 40, base - 16
    _prism(a, ty, by, 32, 68, 29, 71, "green", d=8)
    _grid(a, ty, by, 32, 68, 29, 71, fh=4.8, nv=9, sw=.5, op=.5)
    z = ""                                                                # the corset: four zigzag bands of X-bracing
    n = 5
    for k in range(n):
        ya, yb = ty + (by - ty) * k / n, ty + (by - ty) * (k + 1) / n
        la, ra = 32 - 3 * k / n, 68 + 3 * k / n
        lb, rb = 32 - 3 * (k + 1) / n, 68 + 3 * (k + 1) / n
        z += f"M{_f(la)} {_f(ya)}L{_f(rb)} {_f(yb)}M{_f(ra)} {_f(ya)}L{_f(lb)} {_f(yb)}"
    a.add(f'<path class="lz-mu" d="{z}" style="stroke-width:1.3px"/>')
    a.add(f'<path class="lz-hi" d="M40 {by - 8}L38 {ty + 8}"/>')
    a.front(30.4, ty - 1.8, 39.2, 2.2, "trim")
    for x, top in ((33, 28), (39.5, 20), (46, 8), (52.5, 20), (59, 28)):  # the lantern of glass blades, the centre tallest
        a.front(x, top, 3.6, ty - 1.8 - top, "trim")
    a.add('<path class="lz-hi" d="M47.8 12V34M41.3 24V34M54.3 24V34"/>')
    return a.out()


def _bny() -> dict:
    """BNY Mellon Center (KPF, 792 ft, 54 floors): an obelisk, a five-storey stone podium, a silver
    metal-and-glass tower tapering as it rises with its columns and corner straps showing, a sweeping
    cornice and a pyramid of metal."""
    a = _Art(84, 211)
    base = 199
    a.shadow(5, 78, base, 8)
    _podium(a, 5, 74, base, h=20)
    ty, by = 44, base - 20
    _prism(a, ty, by, 22, 62, 15, 69, "silver", d=8)
    _grid(a, ty, by, 22, 62, 15, 69, fh=4.6, nv=9, sw=.5, op=.8)
    cols = ""
    for u in (.3333, .6667):                                              # the central columns
        cols += f"M{_f(22 + 40 * u)} {ty}L{_f(15 + 54 * u)} {by}"
    a.add(f'<path class="lz-mu" d="{cols}" style="stroke-width:1.5px"/>')
    straps = ""
    for k in range(1, 9):                                                 # the corner straps
        y = by - k * 16.6
        t = (y - ty) / (by - ty)
        l, r = 22 - 7 * t, 62 + 7 * t
        straps += f"M{_f(l)} {_f(y)}h4.4v1.8h-4.4zM{_f(r - 4.4)} {_f(y)}h4.4v1.8h-4.4z"
    a.add(f'<path class="lz-win" d="{straps}" opacity=".8"/>')
    a.add(f'<path class="lz-hi" d="M30 {by - 6}L33 {ty + 8}"/>')
    a.face([(62, ty), (70, ty - 4), (70, ty - 10), (62, ty - 6)], "silver", "s")                          # the cornice
    a.poly([(22, ty), (19.5, ty - 6), (65, ty - 6), (62, ty)], "trim")
    a.face([(61, ty - 6), (68, ty - 9.5), (49, 6), (42, 8)], "silver", "s")                              # the pyramid
    a.poly([(23, ty - 6), (42, 8), (61, ty - 6)], "silver")
    a.line(f"M42 8V{ty - 6}M33 {ty - 21}h18M28 {ty - 12}h28")
    a.add('<path class="lz-hi" d="M30 ' + str(ty - 8) + 'L41 14"/>')
    a.line("M42 8V1")
    return a.out()


def _tls() -> dict:
    """Three Logan Square (Kling Lindquist, 739 ft, 55 floors): red granite in ribbons of dark glazing,
    stepping in twice to a crown whose top corners are cut at an angle."""
    a = _Art(84, 198)
    base = 186
    a.shadow(5, 78, base, 8)
    _podium(a, 6, 72, base, "garnet", h=16)

    def ribbons(x, y0, y1, w, fh=5.2):
        n = int((y1 - y0 - 2) / fh)
        a.add('<path class="lz-win" d="' + "".join(f"M{_f(x + 1.5)} {_f(y1 - 3.4 - k * fh)}h{_f(w - 3)}v2.8h{_f(-(w - 3))}z" for k in range(n)) + '" opacity=".85"/>')
        a.add('<path class="lz-mu" d="' + "".join(f"M{_f(x + w * j / 5)} {_f(y0)}v{_f(y1 - y0)}" for j in range(1, 5)) + '" style="stroke-width:.5px" opacity=".55"/>')

    a.solid(18, 40, 46, base - 16 - 40, "garnet", d=8)
    ribbons(18, 40, base - 16, 46)
    a.add(f'<path class="lz-hi" d="M24 {base - 26}L22 56"/>')
    a.front(16, 38.4, 50, 2.4, "trim")
    a.solid(22, 24, 38, 16, "garnet", d=7)
    ribbons(22, 24, 40, 38, 5.2)
    a.front(20, 22.4, 42, 2.2, "trim")
    a.face([(51, 6), (58, 2.5), (63, 9.5), (63, 20.5), (56, 24), (56, 13)], "garnet", "s")          # the crown: top corners cut away
    a.face([(31, 6), (38, 2.5), (58, 2.5), (51, 6)], "garnet", "t")
    a.poly([(26, 24), (26, 13), (31, 6), (51, 6), (56, 13), (56, 24)], "garnet")
    a.add('<path class="lz-win" d="M30 14h22v6H30z" opacity=".85"/>')
    a.line("M26 13L31 6M56 13L51 6M31 6H51")
    return a.out()


def _cira() -> dict:
    """Cira Centre (Pelli, 437 ft, 29 floors): a glass prism of bright blue-green, its roof cut in one
    long diagonal, a white lattice of crossing diagonals over the faces and a lit facet at each corner."""
    a = _Art(66, 124)
    base = 112
    a.shadow(4, 58, base, 8)
    yb = base - 3
    a.face([(50, yb), (58, yb - 4), (58, 4), (50, 8)], "aqua", "s")
    a.face([(6, 38), (14, 34), (58, 4), (50, 8)], "aqua", "t")
    a.poly([(6, yb), (6, 38), (50, 8), (50, yb)], "aqua")
    a.add(f'<clipPath id="cira-c-{{s}}"><path d="M6 {yb}V38L50 8V{yb}z"/></clipPath>')
    lat = "".join(f"M{6 + k * 11} {yb}L{6 + k * 11 + 44} {yb - 88}M{6 + k * 11} {yb - 88}L{6 + k * 11 + 44} {yb}" for k in range(-4, 5))
    a.add(f'<path class="lz-mu" clip-path="url(#cira-c-{{s}})" d="{lat}" style="stroke-width:.8px"/>')
    a.add(f'<path class="lz-win" d="M6 {yb}L6 {yb - 34}L28 {yb}zM50 8V40L30 21.6z" opacity=".22"/>')
    a.add(f'<path class="lz-hi" d="M12 {yb - 12}L44 36"/>')
    a.line(f"M50 8V{yb}M6 38L50 8")
    a.front(3, yb, 52, 3, "trim")
    return a.out()


def _fmc() -> dict:
    """FMC Tower (Pelli Clarke Pelli, 730 ft, 49 floors): a slender sculptural tower in reflective
    steel-blue glass, its faces folded into creased planes (one lit, one in shade) and its roof sliced
    at an angle, standing over a lower wing."""
    a = _Art(60, 196)
    base = 184
    a.shadow(4, 54, base, 8)
    a.solid(4, 150, 26, base - 150, "steel", d=6)                         # the lower wing
    _grid(a, 150, base, 4, 30, 4, 30, fh=4.4, nv=4)
    a.front(2, 148.4, 30, 2.2, "trim")
    a.face([(46, base), (52, base - 3), (52, 3), (46, 6)], "steel", "s")
    a.face([(18, 20), (24, 17), (52, 3), (46, 6)], "steel", "t")
    a.poly([(18, base), (18, 20), (46, 6), (46, base)], "steel")
    _grid(a, 20, base, 18, 46, 18, 46, fh=4.4, nv=7, sw=.5, op=.8)
    a.add(f'<path class="lz-f" d="M18 {base}V20L27 16V{base}z" fill="url(#lzg-trim-{{s}})" opacity=".32"/>')
    a.add(f'<path class="lz-gs" d="M38 {base}V10L46 6V{base}z"/>')
    a.add(f'<path class="lz-hi" d="M21 {base - 8}L24 28M31 {base - 14}L33 40"/>')
    a.line(f"M27 16V{base}M38 10V{base}M18 20L46 6")
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
        cx, cy, deg = left + 10 - w / 2, y0 + 14 + 22 + h / 2, 0
        if lm.get("a"):                                             # a landmark of a tilted domain (city_lattice): turned with it
            deg = lm["a"]
            r = math.radians(deg)
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            cx, cy = mx + (cx - mx) * math.cos(r) - (cy - my) * math.sin(r), my + (cx - mx) * math.sin(r) + (cy - my) * math.cos(r)
        blocks.append({"id": bid, "lots": [[round(cx, 1), round(cy, 1), round(w, 1), round(h, 1), deg]]})
        at[hub] = f"{bid}.0"
    return blocks
