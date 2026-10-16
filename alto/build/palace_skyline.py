"""The Mind Palace's building generator: every landmark and tower drawn from data, at ONE scale,
standing on its REAL FOOTPRINT.

Why: the art used to be hand-drawn per building and then squeezed into whatever card its block
gave it (`preserveAspectRatio meet`), so a tower's size on the map said how many grid cells its OSM
outline happened to touch, not how tall it is (One Liberty Place on 2 x 2 cells drew 2.8 x Two
Liberty Place on 1 cell; Comcast Technology Center, the tallest, drew smaller than BNY Mellon).

The rule now (Luke, 2026-10-16: towers at true scale; low landmarks "fill the square footage area
and look normal proportions"):
- ONE SCALE. Every building is modelled in real metres and shown at `SCALE` map px per metre:
  width, plan depth and height alike, for towers and low landmarks.
- ON ITS FOOTPRINT. The map is a plan, so a building is drawn as a glass volume standing on its
  footprint in a 3/4 (planometric) view: plan depth runs straight up the page at map scale (the
  footprint covers its real area on the map) and leans right by `KV` per metre, so the right side
  shows; height rises straight up at the same scale. The front (street) face is a true elevation,
  the roof is the footprint lifted by the height. The landmark's card is exactly the projected
  footprint's bounding box (`fp`), so the card hugs the building and the building fills it;
  anything tall (a tower, City Hall's tower) rises above the card as far as it really does.
  Card size comes from footprint METRES, never from how many grid cells the block has.
- PARAMETRIC. A building is a short list of parts in metres, each with a plan place (x across,
  v back from the front edge, d deep; or cv, its plan centre): box (tapers, setbacks), slice
  (angled roof), cut corners, stacked gables, spire, pyramid, dome, barrel vault, hip / mansard,
  pediment, columns, glass blades, cross-bracing, courtyard, clock, statue, door.
  `spec_from_osm(tags, width, depth)` makes the same parts from OSM tags (height, building:levels,
  roof:shape, roof:height, building:material) so ANY city's notable buildings are drawn the same
  way; the famous ones below are hand-tuned overrides (`LANDMARKS`).
- ALTO GLASS. Frosted front faces (a soft gradient, slightly translucent), darker sides, light
  roofs, one line weight in the district's colour, one white sheen, a few faint floor lines, round
  joins, no textures. Static SVG; Safari-safe (no masks, no filters; one clipPath for Cira).

Heights (m, to the tip): Skyscraper Center / Wikipedia. Footprints: rounded real dimensions; the
parts are simplified silhouettes, not copies of any drawing or photograph.
"""
from __future__ import annotations

import math
import re

SCALE = 1.3      # map px per real metre: width, plan depth and height, EVERY building (about the grid's own scale)
KV = 0.25        # 3/4 view: how far (m across) a metre of plan depth leans to the right, so the right sides show
TOP, FOOT, SIDE = 3.0, 2.0, 3.0     # canvas margins (m): above the top, below the ground line, each side
SOLID = ("box", "slice", "cut", "gables", "pyramid", "dome", "vault", "hip", "court")
CENTRED = ("spire", "statue", "blades")          # these stand on the plan centre of the part under them


def _f(n: float) -> str:
    s = f"{n:.1f}"
    return s[:-2] if s.endswith(".0") else s


class Sky:
    """One building from its spec {h: tip m, D: footprint depth m, parts: [...]}; y up from the ground,
    x from the centre line, v back from the footprint's front edge."""

    def __init__(self, spec: dict):
        self.tip = spec["h"]
        raw = spec["parts"]
        ground = [p for p in raw if p["k"] in SOLID and p.get("y0", 0) == 0]
        self.D = float(spec.get("D") or max((p.get("d", p.get("w", 0)) for p in ground), default=20))
        self.u0 = min((p.get("x", 0) - max(p.get("w", 0), p.get("w1", 0)) / 2 for p in ground), default=-10)
        self.u1 = max((p.get("x", 0) + max(p.get("w", 0), p.get("w1", 0)) / 2 for p in ground), default=10)
        self.items = self._place(raw)
        # pass 1: the bounds (every coordinate computed is recorded); pass 2: the drawing
        self.cx = self.G = self.ov = 0.0
        self.rec, self.b, self.parts = True, [0.0, 0.0, 0.0, 0.0], []
        self._rec(self.u0, 0)
        self._rec(self.u1 + self.D * KV, -self.D)
        self._run()
        x0, y0, x1, y1 = self.b
        self.cx, self.G = SIDE - x0, TOP - y0
        self.W, self.H = round(x1 - x0 + 2 * SIDE, 1), round(y1 - y0 + TOP + FOOT, 1)
        self.rec, self.parts = False, []
        self._run()

    def _place(self, raw):
        """Each part's plan place: v (front plane, m back from the footprint's front edge) and d (depth).
        A solid with neither is centred in the footprint (cv = D/2) and square in plan (d = w); a part
        on top of another (a crown, columns, a door) defaults to the plane of the solid before it."""
        out, last = [], (0.0, self.D)
        for p in raw:
            p = dict(p)
            if p["k"] in SOLID:
                d = float(p.get("d", p.get("w", p.get("ws", [10])[0] if p["k"] == "gables" else 10)))
                if "v" not in p:
                    p["v"] = (p["cv"] if "cv" in p else (last[0] + last[1] / 2 if p.get("on") else self.D / 2)) - d / 2
                p["d"] = d
                last = (p["v"], d)
            elif p["k"] in CENTRED:
                p.setdefault("v", p["cv"] if "cv" in p else last[0] + last[1] / 2)
                p.setdefault("d", last[1])
            else:
                p.setdefault("v", last[0])
                p.setdefault("d", last[1])
            out.append(p)
        return out

    def _run(self):
        for p in self.items:
            self.ov = p["v"]
            getattr(self, "_" + p["k"])(p)
        self.ov = 0.0

    # coordinates: x across and z up on the plane `ov` metres back from the footprint's front edge
    def _rec(self, X, Y):
        if self.rec:
            b = self.b
            b[0], b[1], b[2], b[3] = min(b[0], X), min(b[1], Y), max(b[2], X), max(b[3], Y)

    def X(self, x):
        v = self.cx + x + self.ov * KV
        if self.rec:
            self._rec(v, self.b[1])
        return v

    def Y(self, z):
        v = self.G - z - self.ov
        if self.rec:
            self._rec(self.b[0], v)
        return v

    def back(self, d):
        """The screen offset (dx, dy) of going d metres back in plan."""
        return d * KV, d

    def add(self, s):
        if not self.rec:
            self.parts.append(s)

    def pts(self, ps):
        for a, b_ in ps:
            self._rec(a, b_)
        return "M" + "L".join(f"{_f(a)} {_f(b_)}" for a, b_ in ps) + "z"

    def front(self, ps, m, cls="lz-f lz-gl", extra=""):
        self.add(f'<path class="{cls}" d="{self.pts(ps)}" fill="url(#lzg-{m}-{{s}})"{extra}/>')

    def face(self, ps, m, kind="s"):
        self.add(f'<path class="lz-{"sd" if kind == "s" else "tp"} lz-{kind}-{m}" d="{self.pts(ps)}"/>')

    def sheen(self, l0, r0, l1, r1, y0, y1):
        """The one white sheen line, up the lit third of a front face."""
        if y1 - y0 < 18:
            return
        a, b = self.Y(y0 + (y1 - y0) * .05), self.Y(y1 - (y1 - y0) * .1)
        self.add(f'<path class="lz-hi" d="M{_f(l0 + (r0 - l0) * .2)} {_f(a)}L{_f(l1 + (r1 - l1) * .16)} {_f(b)}"/>')

    # ── parts ──
    def _box(self, p):
        """A volume: a shaft, a podium, a wing, a stage; may taper (w at the foot, w1 at the top). fl: a faint
        floor line every fl metres; mu: that many faint mullions; rib: dark glazing ribbons every rib metres."""
        x, w, w1, y0, y1, m = p.get("x", 0), p["w"], p.get("w1", p["w"]), p["y0"], p["y1"], p.get("m", "glass")
        l0, r0, l1, r1 = self.X(x - w / 2), self.X(x + w / 2), self.X(x - w1 / 2), self.X(x + w1 / 2)
        Y0, Y1 = self.Y(y0), self.Y(y1)
        dx, dy = self.back(p["d"])
        tx, ty = self.back(p["d"] * w1 / w)                          # (a taper narrows the plan too)
        if p.get("side", True):
            self.face([(r1, Y1), (r1 + tx, Y1 - ty), (r0 + dx, Y0 - dy), (r0, Y0)], m, "s")
        if p.get("top", True):
            self.face([(l1, Y1), (l1 + tx, Y1 - ty), (r1 + tx, Y1 - ty), (r1, Y1)], m, "t")
        self.front([(l0, Y0), (l1, Y1), (r1, Y1), (r0, Y0)], m, "lz-f" if p.get("solid") else "lz-f lz-gl")
        self._lines(l0, r0, l1, r1, y0, y1, p)
        if p.get("sheen", True):
            self.sheen(l0, r0, l1, r1, y0, y1)

    def _lines(self, l0, r0, l1, r1, y0, y1, p, roof=None):
        """Floor lines (clipped under a sloping roof `roof(x)->y`), mullions and glazing ribbons over a front face."""
        def at(y):
            t = (y - y0) / (y1 - y0)
            return l0 + (l1 - l0) * t, r0 + (r1 - r0) * t
        d = ""
        fl = p.get("fl", 0)
        if fl:
            y = y0 + fl
            while y < y1 - fl * .4:
                l, r = at(y)
                if roof:
                    if y >= roof(l) and y >= roof(r):
                        break
                    if y >= roof(l):
                        l = _cut(roof, l, r, y)
                    elif y >= roof(r):
                        r = _cut(roof, r, l, y)
                d += f"M{_f(l)} {_f(self.Y(y))}H{_f(r)}"
                y += fl
        n = p.get("mu", 0)
        for j in range(1, n + 1):
            u = j / (n + 1)
            xa, xb = l0 + (r0 - l0) * u, l1 + (r1 - l1) * u
            top = roof(xb) if roof else y1
            d += f"M{_f(xa)} {_f(self.Y(y0))}L{_f(xb)} {_f(self.Y(top))}"
        if d:
            self.add(f'<path class="lz-mu" d="{d}"/>')
        rib = p.get("rib", 0)
        if rib:
            r_ = ""
            y = y0 + rib * .6
            while y + rib * .45 < y1:
                l, r = at(y)
                r_ += f"M{_f(l + 1)} {_f(self.Y(y + rib * .42))}H{_f(r - 1)}v{_f(rib * .42)}H{_f(l + 1)}z"
                y += rib
            self.add(f'<path class="lz-win" d="{r_}" opacity=".75"/>')

    def _slice(self, p):
        """A prism whose roof is cut in one slope: the left edge stops at yl, the right at yr (Cira, FMC)."""
        x, w, y0, yl, yr, m = p.get("x", 0), p["w"], p["y0"], p["yl"], p["yr"], p.get("m", "glass")
        l, r = self.X(x - w / 2), self.X(x + w / 2)
        dx, dy = self.back(p["d"])
        self.face([(r, self.Y(yr)), (r + dx, self.Y(yr) - dy), (r + dx, self.Y(y0) - dy), (r, self.Y(y0))], m, "s")
        self.face([(l, self.Y(yl)), (l + dx, self.Y(yl) - dy), (r + dx, self.Y(yr) - dy), (r, self.Y(yr))], m, "t")
        self.front([(l, self.Y(y0)), (l, self.Y(yl)), (r, self.Y(yr)), (r, self.Y(y0))], m)
        roof = (lambda X_: yl + (yr - yl) * (X_ - l) / (r - l))
        self._lines(l, r, l, r, y0, max(yl, yr), p, roof)
        for c in p.get("creases", []):                          # folded planes: a lit strip and a shaded one
            xa, xb = self.X(x - w / 2 + w * c[0]), self.X(x - w / 2 + w * c[1])
            self.add(f'<path class="{"lz-sl" if c[2] == "lit" else "lz-gs"}" d="{self.pts([(xa, self.Y(y0)), (xa, self.Y(roof(xa))), (xb, self.Y(roof(xb))), (xb, self.Y(y0))])}" opacity="{.38 if c[2] == "lit" else .7}"/>')
        if p.get("facets") and not self.rec:                    # a diamond lattice, clipped to the face (clipPath: Safari-safe, no mask)
            cid = f'sky-{p["facets"]}-{{s}}'
            self.add(f'<clipPath id="{cid}"><path d="{self.pts([(l, self.Y(y0)), (l, self.Y(yl)), (r, self.Y(yr)), (r, self.Y(y0))])}"/></clipPath>')
            st, hgt = w / 3.2, max(yl, yr) - y0
            lat = ""
            k = -int(hgt / st) - 2
            while l + k * st < r + hgt:
                xa = l + k * st
                lat += f"M{_f(xa)} {_f(self.Y(y0))}L{_f(xa + hgt * .9)} {_f(self.Y(y0 + hgt))}M{_f(xa + hgt * .9)} {_f(self.Y(y0))}L{_f(xa)} {_f(self.Y(y0 + hgt))}"
                k += 1
            self.add(f'<path class="lz-mu" clip-path="url(#{cid})" d="{lat}"/>')
        self.add(f'<path class="lz-ln" d="M{_f(l)} {_f(self.Y(yl))}L{_f(r)} {_f(self.Y(yr))}"/>')
        self.sheen(l, r, l, r, y0, min(yl, yr))

    def _cut(self, p):
        """A crown with its top corners cut away at 45 degrees (Three Logan Square)."""
        x, w, y0, y1, c, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p["c"], p.get("m", "glass")
        l, r = self.X(x - w / 2), self.X(x + w / 2)
        dx, dy = self.back(p["d"])
        Y0, Y1, Yc = self.Y(y0), self.Y(y1), self.Y(y1 - c)
        self.face([(r, Yc), (r + dx, Yc - dy), (r + dx, Y0 - dy), (r, Y0)], m, "s")
        self.face([(r - c, Y1), (r - c + dx, Y1 - dy), (r + dx, Yc - dy), (r, Yc)], m, "s")
        self.face([(l + c, Y1), (l + c + dx, Y1 - dy), (r - c + dx, Y1 - dy), (r - c, Y1)], m, "t")
        self.front([(l, Y0), (l, Yc), (l + c, Y1), (r - c, Y1), (r, Yc), (r, Y0)], m)
        if p.get("band"):
            self.add(f'<path class="lz-win" d="M{_f(l + c * .6)} {_f(Yc + 1)}H{_f(r - c * .6)}v{_f(c * .6)}H{_f(l + c * .6)}z" opacity=".75"/>')

    def _gables(self, p):
        """A crown of stacked gables, each narrower, the ridges running back (the Liberty Places, after the
        Chrysler Building); every stage square in plan about the crown's plan centre."""
        x, y, m, rise = p.get("x", 0), p["y0"], p.get("m", "glass"), p.get("rise", .42)
        vc = p["v"] + p["d"] / 2
        for w, wall in zip(p["ws"], p["walls"]):
            self.ov = vc - w / 2
            hw, yw = w / 2, y + wall
            ap = yw + w * rise
            dx, dy = self.back(w)
            l, r, c = self.X(x - hw), self.X(x + hw), self.X(x)
            self.face([(r, self.Y(y)), (r + dx, self.Y(y) - dy), (r + dx, self.Y(yw) - dy), (c + dx, self.Y(ap) - dy),
                       (c, self.Y(ap)), (r, self.Y(yw))], m, "s")
            self.front([(l, self.Y(y)), (l, self.Y(yw)), (c, self.Y(ap)), (r, self.Y(yw)), (r, self.Y(y))], m)
            self.add(f'<path class="lz-mu" d="M{_f(l + w * .1)} {_f(self.Y(yw) - .4)}L{_f(c)} {_f(self.Y(ap) + w * .1)}L{_f(r - w * .1)} {_f(self.Y(yw) - .4)}"/>')
            y = yw + w * rise * .55

    def _spire(self, p):
        x, y0, y1, w = p.get("x", 0), p["y0"], p["y1"], p.get("w", 1.6)
        self.front([(self.X(x - w / 2), self.Y(y0)), (self.X(x), self.Y(y1)), (self.X(x + w / 2), self.Y(y0))], p.get("m", "trim"), "lz-f")
        self.add(f'<path class="lz-ln" d="M{_f(self.X(x))} {_f(self.Y(y0))}V{_f(self.Y(y1))}"/>')

    def _pyramid(self, p):
        """A pyramid on a square base: the front and right slopes meeting at the apex over the plan centre."""
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "glass")
        l, r = self.X(x - w / 2), self.X(x + w / 2)
        dx, dy = self.back(p["d"])
        ax, ay = self.X(x) + dx / 2, self.Y(y1) - dy / 2
        self.face([(r, self.Y(y0)), (r + dx, self.Y(y0) - dy), (ax, ay)], m, "s")
        self.front([(l, self.Y(y0)), (ax, ay), (r, self.Y(y0))], m)
        self.add(f'<path class="lz-mu" d="M{_f(ax)} {_f(ay)}L{_f(self.X(x))} {_f(self.Y(y0))}"/>')

    def _pediment(self, p):
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "trim")
        l, r = self.X(x - w / 2), self.X(x + w / 2)
        self.front([(l, self.Y(y0)), (self.X(x), self.Y(y1)), (r, self.Y(y0))], m, "lz-f")

    def _hip(self, p):
        """A hipped / mansard roof over a w x d plan: every side slopes in by `inset` to a flat top."""
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "slate")
        d = p["d"]
        ins = min(p.get("inset", (y1 - y0) * 1.1), w / 2 - .5, d / 2 - .5)
        l, r = self.X(x - w / 2), self.X(x + w / 2)
        Y0, Y1 = self.Y(y0), self.Y(y1)
        bx, by = self.back(d)
        ix, iy = self.back(ins)
        jx, jy = self.back(d - ins)
        self.face([(l + ins + ix, Y1 - iy), (l + ins + jx, Y1 - jy), (r - ins + jx, Y1 - jy), (r - ins + ix, Y1 - iy)], m, "t")
        self.face([(r, Y0), (r + bx, Y0 - by), (r - ins + jx, Y1 - jy), (r - ins + ix, Y1 - iy)], m, "s")
        self.front([(l, Y0), (l + ins + ix, Y1 - iy), (r - ins + ix, Y1 - iy), (r, Y0)], m, "lz-f")

    def _court(self, p):
        """A courtyard: a dark opening in a roof at height y0, w x d in plan."""
        x, w, z = p.get("x", 0), p["w"], p["y0"]
        dx, dy = self.back(p["d"])
        l, r, Y = self.X(x - w / 2), self.X(x + w / 2), self.Y(z)
        self.add(f'<path class="lz-win" d="{self.pts([(l, Y), (l + dx, Y - dy), (r + dx, Y - dy), (r, Y)])}" opacity=".55"/>')

    def _dome(self, p):
        """A dome over its plan centre (its silhouette, drawn on the plane through the centre)."""
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "slate")
        self.ov = p["v"] + p["d"] / 2
        l, r, h = self.X(x - w / 2), self.X(x + w / 2), y1 - y0
        arc = f"M{_f(l)} {_f(self.Y(y0))}C{_f(l)} {_f(self.Y(y0 + h * .78))} {_f(self.X(x - w * .28))} {_f(self.Y(y1))} {_f(self.X(x))} {_f(self.Y(y1))}" \
              f"S{_f(r)} {_f(self.Y(y0 + h * .78))} {_f(r)} {_f(self.Y(y0))}z"
        self.add(f'<path class="lz-f" d="{arc}" fill="url(#lzg-{m}-{{s}})"/>')
        self.add(f'<path class="lz-mu" d="M{_f(self.X(x))} {_f(self.Y(y1))}V{_f(self.Y(y0))}M{_f(self.X(x - w * .25))} {_f(self.Y(y0 + h * .86))}Q{_f(self.X(x - w * .36))} {_f(self.Y(y0 + h * .4))} {_f(self.X(x - w * .36))} {_f(self.Y(y0))}'
                 f'M{_f(self.X(x + w * .25))} {_f(self.Y(y0 + h * .86))}Q{_f(self.X(x + w * .36))} {_f(self.Y(y0 + h * .4))} {_f(self.X(x + w * .36))} {_f(self.Y(y0))}"/>')

    def _vault(self, p):
        """A barrel vault running back d metres: its glass roof swept between the back and the front arch,
        steel ribs across it, the front arch on top (the Reading train shed)."""
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "glass")
        h = y1 - y0
        l, r = self.X(x - w / 2), self.X(x + w / 2)
        ys, yt = self.Y(y0 + h * .45), self.Y(y1)
        bx, by = self.back(p["d"])

        def arch(dx, dy, close=True):
            s_ = (f"M{_f(l + dx)} {_f(self.Y(y0) - dy)}V{_f(ys - dy)}C{_f(l + dx)} {_f(yt - dy)} {_f(r + dx)} {_f(yt - dy)} "
                  f"{_f(r + dx)} {_f(ys - dy)}V{_f(self.Y(y0) - dy)}")
            self._rec(l + dx, yt - dy); self._rec(r + dx, self.Y(y0) - dy)
            return s_ + ("z" if close else "")
        band = (f"M{_f(l)} {_f(ys)}C{_f(l)} {_f(yt)} {_f(r)} {_f(yt)} {_f(r)} {_f(ys)}L{_f(r + bx)} {_f(ys - by)}"
                f"C{_f(r + bx)} {_f(yt - by)} {_f(l + bx)} {_f(yt - by)} {_f(l + bx)} {_f(ys - by)}z")
        self.add(f'<path class="lz-sd lz-s-{m}" d="{arch(bx, by)}"/>')
        self.add(f'<path class="lz-tp lz-t-{m}" d="{band}"/>')
        ribs = "".join(f"M{_f(l + bx * t)} {_f(ys - by * t)}C{_f(l + bx * t)} {_f(yt - by * t)} {_f(r + bx * t)} {_f(yt - by * t)} {_f(r + bx * t)} {_f(ys - by * t)}"
                       for t in (.2, .4, .6, .8))
        self.add(f'<path class="lz-mu" d="{ribs}"/>')
        self.add(f'<path class="lz-f lz-gl" d="{arch(0, 0)}" fill="url(#lzg-{m}-{{s}})"/>')
        fr = "".join(f"M{_f(l + (r - l) * u)} {_f(self.Y(y0))}V{_f(ys + (yt - ys) * .6 * (1 - abs(u - .5) * 2) ** .5)}" for u in (.25, .5, .75))
        self.add(f'<path class="lz-mu" d="{fr}"/>')

    def _cols(self, p):
        """A colonnade's rhythm: n columns as white strokes over the front (one weight, no texture)."""
        x, w, y0, y1, n = p.get("x", 0), p["w"], p["y0"], p["y1"], p["n"]
        d = "".join(f"M{_f(self.X(x - w / 2 + w * (i + .5) / n))} {_f(self.Y(y0))}V{_f(self.Y(y1))}" for i in range(n))
        self.add(f'<path class="lz-col-l" d="{d}"/>')

    def _blades(self, p):
        """A lantern of glass blades on the plan centre, the middle one tallest (Comcast Technology Center)."""
        x, w, y0, tops = p.get("x", 0), p["w"], p["y0"], p["tops"]
        n = len(tops)
        bw = w / n * .55
        for i, t in enumerate(tops):
            cx = self.X(x - w / 2 + w * (i + .5) / n)
            self.front([(cx - bw / 2, self.Y(y0)), (cx - bw / 2, self.Y(t)), (cx + bw / 2, self.Y(t)), (cx + bw / 2, self.Y(y0))], p.get("m", "trim"), "lz-f")

    def _brace(self, p):
        """Cross-bracing bands over a (tapering) front face (the CTC's corset)."""
        x, w, w1, y0, y1, n = p.get("x", 0), p["w"], p.get("w1", p["w"]), p["y0"], p["y1"], p["n"]
        d = ""
        for k in range(n):
            ya, yb = y0 + (y1 - y0) * k / n, y0 + (y1 - y0) * (k + 1) / n
            wa, wb = w + (w1 - w) * k / n, w + (w1 - w) * (k + 1) / n
            d += (f"M{_f(self.X(x - wa / 2))} {_f(self.Y(ya))}L{_f(self.X(x + wb / 2))} {_f(self.Y(yb))}"
                  f"M{_f(self.X(x + wa / 2))} {_f(self.Y(ya))}L{_f(self.X(x - wb / 2))} {_f(self.Y(yb))}")
        self.add(f'<path class="lz-mu lz-mu2" d="{d}"/>')

    def _strip(self, p):
        """A plain flat strip over a front face: notches, ultra-clear corners, a band of glazing (no 3D)."""
        x, w, y0, y1 = p.get("x", 0), p["w"], p["y0"], p["y1"]
        cls = {"win": "lz-win", "lit": "lz-sl", "shade": "lz-gs"}[p.get("t", "win")]
        self.add(f'<path class="{cls}" d="{self.pts([(self.X(x - w / 2), self.Y(y0)), (self.X(x - w / 2), self.Y(y1)), (self.X(x + w / 2), self.Y(y1)), (self.X(x + w / 2), self.Y(y0))])}" opacity="{p.get("op", .6)}"/>')

    def _clock(self, p):
        cx, cy, r = self.X(p.get("x", 0)), self.Y(p["y"]), p["r"]
        self.add(f'<circle class="lz-f" cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="url(#lzg-trim-{{s}})"/>'
                 f'<path class="lz-ln" d="M{_f(cx)} {_f(cy)}v{_f(-r * .62)}M{_f(cx)} {_f(cy)}l{_f(r * .44)} {_f(r * .24)}"/>')

    def _statue(self, p):
        """A figure on top (William Penn on City Hall): a robed body, the head, the hat brim, the arm out."""
        x, y0, y1 = self.X(p.get("x", 0)), p["y0"], p["y1"]
        h = y1 - y0
        b = self.Y(y0)
        self._rec(x - h * .2, b - h); self._rec(x + h * .4, b)
        self.add(f'<path class="lz-f" d="M{_f(x - h * .14)} {_f(b)}L{_f(x - h * .09)} {_f(b - h * .72)}H{_f(x + h * .09)}L{_f(x + h * .14)} {_f(b)}z'
                 f'M{_f(x + h * .08)} {_f(b - h * .66)}l{_f(h * .3)} {_f(-h * .16)}l0 {_f(h * .08)}l{_f(-h * .28)} {_f(h * .16)}z" fill="url(#lzg-bronze-{{s}})"/>'
                 f'<circle class="lz-f" cx="{_f(x)}" cy="{_f(b - h * .82)}" r="{_f(h * .1)}" fill="url(#lzg-bronze-{{s}})"/>'
                 f'<path class="lz-ln" d="M{_f(x - h * .16)} {_f(b - h * .9)}h{_f(h * .32)}"/>')

    def _seal(self, p):
        """The court's level, calm: a small disc in the level's accent with a white glyph (federal: a star,
        state: a diamond, city: a rounded square) on the pediment or over the door."""
        lv = p.get("lv", "state")
        cx, cy, r = self.X(p.get("x", 0)), self.Y(p["y"]), p.get("r", 2.6)
        self._rec(cx - r, cy - r); self._rec(cx + r, cy + r)
        if lv == "federal":
            g = "".join(f"{'M' if i == 0 else 'L'}{_f(cx + r * .62 * (1 if i % 2 == 0 else .42) * _sin(i))} {_f(cy - r * .62 * (1 if i % 2 == 0 else .42) * _cos(i))}" for i in range(10)) + "z"
        elif lv == "city":
            q = r * .42
            g = f"M{_f(cx - q)} {_f(cy - q)}h{_f(2 * q)}v{_f(2 * q)}h{_f(-2 * q)}z"
        else:
            q = r * .55
            g = f"M{_f(cx)} {_f(cy - q)}L{_f(cx + q)} {_f(cy)}L{_f(cx)} {_f(cy + q)}L{_f(cx - q)} {_f(cy)}z"
        self.add(f'<circle class="lz-seal lz-seal-{lv}" cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}"/><path class="lz-seal-g" d="{g}"/>')

    def _door(self, p):
        x, w, h = self.X(p.get("x", 0)), p["w"], p["h"]
        g = self.Y(0)
        self.add(f'<path class="lz-door" d="M{_f(x - w / 2)} {_f(g)}V{_f(g - h + w / 2)}a{_f(w / 2)} {_f(w / 2)} 0 0 1 {_f(w)} 0V{_f(g)}z"/>')

    def out(self, **meta) -> dict:
        """{w, h, svg} plus hm (tip m), fp (the footprint's projected bounding box in the canvas: the card),
        fw / fd (the footprint's width and depth, m)."""
        fp = [round(self.cx + self.u0, 2), round(self.G - self.D, 2), round(self.cx + self.u1 + self.D * KV, 2), round(self.G, 2)]
        return {"w": self.W, "h": self.H, "svg": "".join(self.parts), "hm": self.tip, "fp": fp,
                "fw": round(self.u1 - self.u0, 1), "fd": round(self.D, 1), **meta}


def _sin(i):
    return math.sin(i * math.pi / 5)


def _cos(i):
    return math.cos(i * math.pi / 5)


def _cut(roof, a, b, y):
    """Where a floor line at height y meets the sloping roof between x=a (above the roof) and x=b."""
    lo, hi = b, a
    for _ in range(18):
        mid = (lo + hi) / 2
        if roof(mid) > y:
            lo = mid
        else:
            hi = mid
    return lo


def gables_apex(y0, ws, walls, rise=.42) -> float:
    y = ap = y0
    for w, wall in zip(ws, walls):
        ap = y + wall + w * rise
        y = y + wall + w * rise * .55
    return ap


def build(spec: dict) -> dict:
    """A building's art from its spec {h: tip height m, D: footprint depth m, parts: [...]}."""
    return Sky(spec).out()


# ── the generic building, from OSM tags (any city) ──────────────────────────
ROOF = {"flat": "flat", "skillion": "angled", "lean_to": "angled", "saltbox": "angled", "pyramidal": "pyramid",
        "dome": "dome", "onion": "dome", "round": "vault", "half-round": "vault", "gabled": "gable", "gambrel": "gable",
        "hipped": "hip", "half-hipped": "hip", "mansard": "hip", "side_hipped": "hip", "spire": "spire", "cone": "spire"}
MATERIAL = {"glass": "glass", "brick": "brick", "stone": "stone", "sandstone": "sand", "limestone": "sand", "marble": "marble",
            "granite": "granite", "concrete": "stone", "metal": "silver", "steel": "silver", "aluminium": "silver", "wood": "sand"}


def parse_height(v) -> float:
    """OSM height text in metres: '288', '288 m', '945 ft', "945'", "945'6\"" (0 when it is not a height)."""
    if v is None:
        return 0.0
    s = str(v).strip().lower().replace(",", ".")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:'|ft|feet)\s*(?:(\d+(?:\.\d+)?)\s*(?:\"|in))?$", s)
    if m:
        return round(float(m.group(1)) * .3048 + float(m.group(2) or 0) * .0254, 1)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(m|metres?|meters?)?$", s)
    return float(m.group(1)) if m else 0.0


def spec_from_osm(tags: dict, width_m: float | None = None, depth_m: float | None = None) -> dict:
    """The parts of an ordinary notable building from its OSM tags (Wikidata-like facts in the same keys:
    height, building:levels, roof:shape, roof:height, building:material). width_m / depth_m: its footprint
    (the outline's extent across and back), when known."""
    t = tags or {}
    if str(t.get("amenity") or "").lower() == "courthouse" or str(t.get("kind") or "").lower() == "courthouse":
        hh = parse_height(t.get("height")) or (parse_height(t.get("building:levels")) * 3.8)
        st = court_style(hh, 0, t.get("court_style"), t)
        return {**courthouse_spec(st, court_level(t.get("name"), t.get("level")), width_m or 0, depth_m or 0, hh or 0), "shape": "court-" + st}
    h = parse_height(t.get("height"))
    lv = parse_height(t.get("building:levels"))
    rh = parse_height(t.get("roof:height"))
    if not h:
        h = (lv * 3.5 if lv else 12.0) + rh
    shape = ROOF.get(str(t.get("roof:shape") or "flat").lower(), "flat")
    m = MATERIAL.get(str(t.get("building:material") or t.get("building:facade:material") or "").lower(),
                     "glass" if h >= 60 else "stone")
    tall = h >= 60
    W = float(width_m) if width_m else (max(16.0, min(60.0, h * .3)) * 1.35 if tall else 40.0)
    W = max(8.0, min(W, 400.0))
    D = max(6.0, min(float(depth_m) if depth_m else W, 400.0))
    w = W / 1.35 if tall else W                                     # a tower's shaft stands on a wider podium
    d = D / 1.35 if tall else D
    if not rh:
        rh = {"flat": 0, "angled": w * .35, "pyramid": w * .45, "dome": w * .45, "vault": w * .4, "gable": w * .3,
              "hip": w * .2, "spire": max(h * .25, w * .8)}[shape]
    rh = min(rh, h * .6)
    body = h - rh
    parts = []
    if tall:
        parts.append({"k": "box", "w": W, "d": D, "y0": 0, "y1": min(16, body * .08), "m": "granite", "solid": 1, "sheen": False})
    y0 = parts[-1]["y1"] if parts else 0
    fl = 3.5 * (4 if tall else 1)
    if shape == "angled":
        parts.append({"k": "slice", "w": w, "d": d, "y0": y0, "yl": body, "yr": h, "m": m, "fl": fl, "mu": 4 if tall else 2})
    else:
        parts.append({"k": "box", "w": w, "d": d, "y0": y0, "y1": body, "m": m, "fl": fl, "mu": max(2, int(w / 9)), "solid": m != "glass"})
        crown = {"pyramid": {"k": "pyramid", "w": min(w, d), "d": min(w, d)}, "dome": {"k": "dome", "w": min(w, d) * .8, "d": min(w, d) * .8},
                 "vault": {"k": "vault", "w": w, "d": d}, "gable": {"k": "pediment", "w": w * 1.02, "m": "slate"},
                 "hip": {"k": "hip", "w": w, "d": d, "inset": rh * 1.1}, "spire": {"k": "spire", "w": max(2.0, w * .35), "m": "slate" if not tall else "trim"}}.get(shape)
        if crown:
            parts.append({**crown, "y0": body, "y1": h})
    return {"h": round(h, 1), "D": D, "parts": parts, "shape": shape}


GENERIC = {}    # the page's fallback for a mapped building with a height but no art of its own: one per roof shape at 100 m
for _shape, _tags in (("flat", {}), ("angled", {"roof:shape": "skillion"}), ("pyramid", {"roof:shape": "pyramidal"}),
                      ("dome", {"roof:shape": "dome"}), ("spire", {"roof:shape": "spire"}), ("gable", {"roof:shape": "gabled"})):
    GENERIC["g-" + _shape] = build(spec_from_osm({"height": "100", **_tags}, 40, 40))


# ── the famous ones: hand-tuned specs (metres; v = back from the front edge, cv = plan centre) ──
def _lib1():
    """One Liberty Place (Jahn, 1987; 288 m, 61 floors): sapphire glass banded in pale granite, two
    setbacks, a crown of four stacked gables (after the Chrysler Building) and a steel spire. The
    first tower above William Penn's hat."""
    ws, walls = [34, 27, 20, 13], [4, 4, 3, 3]
    ap = gables_apex(222, ws, walls)
    return {"h": 288, "D": 64, "parts": [
        {"k": "box", "w": 64, "y0": 0, "y1": 14, "m": "granite", "solid": 1, "sheen": False, "mu": 5},
        {"k": "box", "w": 50, "y0": 14, "y1": 176, "m": "sapphire", "fl": 13.5, "mu": 5},
        {"k": "strip", "w": 4, "x": -23, "y0": 14, "y1": 176, "t": "lit", "op": .35},
        {"k": "box", "w": 42, "y0": 176, "y1": 204, "m": "sapphire", "fl": 9, "mu": 4},
        {"k": "box", "w": 34, "y0": 204, "y1": 222, "m": "sapphire", "fl": 9, "mu": 3},
        {"k": "gables", "ws": ws, "walls": walls, "y0": 222, "m": "sapphire"},
        {"k": "spire", "y0": ap - 3, "y1": 288, "w": 2.2}]}


def _lib2():
    """Two Liberty Place (Jahn, 1990; 258 m, 58 floors): the same sapphire-and-granite skin, slimmer,
    with a squatter crown of three angled gables and a short spire stub."""
    ws, walls = [32, 23, 14], [4, 3, 3]
    ap = gables_apex(214, ws, walls)
    return {"h": 258, "D": 56, "parts": [
        {"k": "box", "w": 56, "y0": 0, "y1": 14, "m": "granite", "solid": 1, "sheen": False, "mu": 4},
        {"k": "box", "w": 42, "y0": 14, "y1": 194, "m": "sapphire", "fl": 13.5, "mu": 4},
        {"k": "strip", "w": 3.5, "x": -19.2, "y0": 14, "y1": 194, "t": "lit", "op": .35},
        {"k": "box", "w": 34, "y0": 194, "y1": 214, "m": "sapphire", "fl": 9, "mu": 3},
        {"k": "gables", "ws": ws, "walls": walls, "y0": 214, "m": "sapphire"},
        {"k": "spire", "y0": ap - 2, "y1": 258, "w": 2}]}


def _ccc():
    """Comcast Center (Stern, 2008; 297 m, 57 floors): a slab of silver glass over a glass winter
    garden, easing in near the top under two notches, ultra-clear corners and a glass-box crown."""
    return {"h": 297, "D": 56, "parts": [
        {"k": "box", "w": 70, "d": 56, "y0": 0, "y1": 22, "m": "glass", "fl": 7, "mu": 8, "sheen": False},
        {"k": "box", "w": 52, "d": 40, "y0": 22, "y1": 238, "m": "silver", "fl": 14, "mu": 6},
        {"k": "box", "w": 52, "w1": 46, "d": 40, "y0": 238, "y1": 279, "m": "silver", "fl": 14, "mu": 6, "top": False, "sheen": False},
        {"k": "strip", "w": 3, "x": -24.5, "y0": 22, "y1": 279, "t": "lit", "op": .5},
        {"k": "strip", "w": 7, "x": 19, "y0": 250, "y1": 276, "t": "win", "op": .45},
        {"k": "box", "w": 44, "d": 34, "y0": 279, "y1": 297, "m": "trim", "mu": 3, "sheen": False}]}


def _ctc():
    """Comcast Technology Center (Foster + Partners, 2018; 342 m, 60 floors): a slim tower of clear
    glass easing in as it climbs, wrapped in bands of cross-bracing, on a long ribbed podium, ending in
    a lantern of glass blades. Philadelphia's tallest."""
    return {"h": 342, "D": 50, "parts": [
        {"k": "box", "w": 92, "d": 50, "y0": 0, "y1": 20, "m": "granite", "solid": 1, "fl": 4, "sheen": False},
        {"k": "box", "w": 46, "w1": 41, "d": 40, "y0": 20, "y1": 304, "m": "glass", "fl": 16, "mu": 4},
        {"k": "brace", "w": 46, "w1": 41, "y0": 20, "y1": 304, "n": 5},
        {"k": "blades", "w": 40, "y0": 304, "tops": [318, 330, 342, 330, 318]}]}


def _bny():
    """BNY Mellon Center (KPF, 1990; 241 m, 54 floors): an obelisk of silver metal and glass tapering
    from a stone podium, a cornice and a pyramid of metal under a mast."""
    return {"h": 241, "D": 66, "parts": [
        {"k": "box", "w": 66, "y0": 0, "y1": 20, "m": "granite", "solid": 1, "sheen": False, "mu": 5},
        {"k": "box", "w": 54, "w1": 42, "y0": 20, "y1": 199, "m": "silver", "fl": 15, "mu": 2},
        {"k": "box", "w": 46, "y0": 199, "y1": 204, "m": "trim", "sheen": False},
        {"k": "pyramid", "w": 44, "y0": 204, "y1": 233, "m": "silver"},
        {"k": "spire", "y0": 232, "y1": 241, "w": 1.4}]}


def _tls():
    """Three Logan Square (Kling Lindquist, 1991; 225 m, 55 floors): red granite in ribbons of dark
    glazing, stepping in twice to a crown whose top corners are cut away."""
    return {"h": 225, "D": 58, "parts": [
        {"k": "box", "w": 58, "y0": 0, "y1": 14, "m": "garnet", "solid": 1, "sheen": False},
        {"k": "box", "w": 44, "y0": 14, "y1": 188, "m": "garnet", "solid": 1, "rib": 7, "mu": 3},
        {"k": "box", "w": 36, "y0": 188, "y1": 205, "m": "garnet", "solid": 1, "rib": 7},
        {"k": "cut", "w": 32, "y0": 205, "y1": 225, "c": 8, "m": "garnet", "band": 1}]}


def _cira():
    """Cira Centre (Pelli Clarke Pelli, 2005; 133 m, 29 floors): a prism of blue-green glass whose
    faceted faces read as diamonds, the roof cut in one long slope."""
    return {"h": 133, "D": 40, "parts": [
        {"k": "slice", "w": 50, "d": 36, "y0": 0, "yl": 100, "yr": 133, "m": "aqua", "facets": "cira",
         "creases": [[0, .14, "lit"], [.86, 1, "shade"]]}]}


def _fmc():
    """FMC Tower (Pelli Clarke Pelli, 2016; 223 m, 49 floors): a slender tower of steel-blue glass
    folded into creased planes, its roof sliced at an angle, beside a lower wing."""
    return {"h": 223, "D": 40, "parts": [
        {"k": "box", "x": -15, "w": 26, "d": 34, "y0": 0, "y1": 40, "m": "steel", "fl": 10, "mu": 2, "sheen": False},
        {"k": "slice", "x": 6, "w": 36, "d": 36, "y0": 0, "yl": 204, "yr": 223, "m": "steel", "fl": 14, "mu": 3,
         "creases": [[0, .3, "lit"], [.72, 1, "shade"]]}]}


def _cityhall():
    """City Hall (McArthur, 1901; 148 x 145 m, 167 m to the top of William Penn): the Second Empire block
    in white marble round its courtyard under slate mansards, corner and centre pavilions, and the tower
    over the north wing — five times the block's height — in a shaft, a clock stage, an open colonnade
    and a dome, with Penn on top."""
    tw = 125.0                                                     # the tower's plan centre (north wing)
    return {"h": 167, "D": 145, "parts": [
        *[{"k": "box", "x": x, "w": 24, "v": 121, "d": 24, "y0": 0, "y1": 39, "m": "marble", "solid": 1, "sheen": False} for x in (-62, 62)],
        *[{"k": "hip", "x": x, "w": 24, "v": 121, "d": 24, "y0": 39, "y1": 50, "inset": 6} for x in (-62, 62)],
        {"k": "box", "w": 148, "v": 4, "d": 137, "y0": 0, "y1": 34, "m": "marble", "solid": 1, "fl": 11.5, "mu": 12, "top": False},
        {"k": "hip", "w": 148, "v": 4, "d": 137, "y0": 34, "y1": 43, "inset": 9},
        {"k": "court", "w": 64, "v": 42, "d": 62, "y0": 43},
        {"k": "box", "w": 27, "cv": tw, "d": 27, "y0": 43, "y1": 102, "m": "marble", "solid": 1, "mu": 2},
        {"k": "box", "w": 23, "cv": tw, "d": 23, "y0": 102, "y1": 117, "m": "marble", "solid": 1, "sheen": False},
        {"k": "clock", "y": 109.5, "r": 5.2},
        {"k": "box", "w": 18, "cv": tw, "d": 18, "y0": 117, "y1": 131, "m": "trim", "solid": 1, "sheen": False},
        {"k": "cols", "w": 15, "y0": 118, "y1": 130, "n": 5},
        {"k": "dome", "w": 17, "cv": tw, "d": 17, "y0": 131, "y1": 148, "m": "slate"},
        {"k": "spire", "cv": tw, "y0": 148, "y1": 152, "w": 4, "m": "trim"},
        {"k": "statue", "cv": tw, "y0": 152, "y1": 167},
        *[q for x in (-62, 62) for q in (
            {"k": "box", "x": x, "w": 24, "v": 0, "d": 24, "y0": 0, "y1": 39, "m": "marble", "solid": 1, "fl": 11.5, "mu": 2, "sheen": False},
            {"k": "hip", "x": x, "w": 24, "v": 0, "d": 24, "y0": 39, "y1": 50, "inset": 6})],
        {"k": "box", "w": 40, "v": 0, "d": 20, "y0": 0, "y1": 38, "m": "marble", "solid": 1},
        {"k": "cols", "w": 36, "y0": 4, "y1": 34, "n": 8},
        {"k": "hip", "w": 40, "v": 0, "d": 20, "y0": 38, "y1": 47, "inset": 7},
        {"k": "door", "v": 0, "w": 9, "h": 14},
        {"k": "seal", "x": -6, "y": 42.5, "r": 2.4, "lv": "city"},                # the courts inside: city (Common Pleas) and state
        {"k": "seal", "x": 6, "y": 42.5, "r": 2.4, "lv": "state"}]}


def _independence():
    """Independence Hall (1753; 104 x 22 m with its wings, 51 m to the tip): the Georgian main block of red
    brick under a hipped roof, the covered arcades and the two end buildings (Congress Hall, Old City Hall),
    and on its south front the tower and white steeple: clock stage, belfry, lantern, spire."""
    tc = 4.5                                                       # the tower's plan centre (it stands out from the south front)
    return {"h": 51, "D": 22, "parts": [
        *[q for x in (-27, 27) for q in (
            {"k": "box", "x": x, "w": 12, "v": 12, "d": 6, "y0": 0, "y1": 6.5, "m": "brick", "solid": 1, "mu": 2, "sheen": False},
            {"k": "hip", "x": x, "w": 12, "v": 12, "d": 6, "y0": 6.5, "y1": 8.5})],
        *[q for x in (-43, 43) for q in (
            {"k": "box", "x": x, "w": 18, "v": 2, "d": 20, "y0": 0, "y1": 11, "m": "brick", "solid": 1, "mu": 4, "top": False},
            {"k": "hip", "x": x, "w": 18, "v": 2, "d": 20, "y0": 11, "y1": 15})],
        {"k": "box", "w": 33, "v": 8, "d": 14, "y0": 0, "y1": 13, "m": "brick", "solid": 1, "fl": 6.5, "mu": 8, "top": False},
        {"k": "hip", "w": 33, "v": 8, "d": 14, "y0": 13, "y1": 19, "inset": 5},
        {"k": "box", "w": 9, "cv": tc, "d": 9, "y0": 0, "y1": 29, "m": "brick", "solid": 1, "sheen": False},
        {"k": "door", "w": 3.6, "h": 6},
        {"k": "box", "w": 8, "cv": tc, "d": 8, "y0": 29, "y1": 34, "m": "trim", "solid": 1, "sheen": False},
        {"k": "clock", "y": 31.5, "r": 2},
        {"k": "box", "w": 6, "cv": tc, "d": 6, "y0": 34, "y1": 40, "m": "trim", "solid": 1, "sheen": False, "mu": 2},
        {"k": "dome", "w": 5, "cv": tc, "d": 5, "y0": 40, "y1": 43.5, "m": "trim"},
        {"k": "spire", "cv": tc, "y0": 43, "y1": 51, "w": 1.5}]}


def _artmuseum():
    """Philadelphia Museum of Art (1928; about 196 x 110 m, 36 m): the U of tan Kasota limestone — the
    central block with its temple front at the back of the court, the long wings running forward to the
    two pedimented end pavilions — under blue-green tiled roofs."""
    return {"h": 36, "D": 110, "parts": [
        {"k": "box", "w": 124, "v": 66, "d": 44, "y0": 0, "y1": 27, "m": "sand", "solid": 1, "mu": 6, "top": False},
        {"k": "hip", "w": 124, "v": 66, "d": 44, "y0": 27, "y1": 33, "m": "teal"},
        *[q for x in (-80, 80) for q in (
            {"k": "box", "x": x, "w": 26, "v": 20, "d": 90, "y0": 0, "y1": 21, "m": "sand", "solid": 1, "mu": 2, "top": False, "sheen": False},
            {"k": "hip", "x": x, "w": 26, "v": 20, "d": 90, "y0": 21, "y1": 26, "m": "teal"})],
        {"k": "box", "w": 60, "v": 56, "d": 10, "y0": 0, "y1": 27, "m": "sand", "solid": 1, "top": False},
        {"k": "cols", "w": 54, "y0": 2, "y1": 24, "n": 8},
        {"k": "pediment", "w": 64, "y0": 27, "y1": 36},
        {"k": "door", "w": 6, "h": 11},
        *[q for x in (-84, 84) for q in (
            {"k": "box", "x": x, "w": 28, "v": 0, "d": 24, "y0": 0, "y1": 23, "m": "sand", "solid": 1, "top": False, "sheen": False},
            {"k": "cols", "x": x, "w": 24, "y0": 1, "y1": 22, "n": 4},
            {"k": "hip", "x": x, "w": 28, "v": 0, "d": 24, "y0": 23, "y1": 27, "m": "teal"},
            {"k": "pediment", "x": x, "w": 30, "v": 0, "y0": 23, "y1": 29})]]}


def _franklin():
    """The Franklin Institute (1934; about 110 x 70 m): a limestone block, its six-column portico and
    pediment on the Parkway front, and the dome of the Benjamin Franklin National Memorial behind."""
    return {"h": 38, "D": 70, "parts": [
        {"k": "box", "w": 110, "v": 8, "d": 62, "y0": 0, "y1": 19, "m": "stone", "solid": 1, "mu": 10},
        {"k": "box", "w": 36, "cv": 36, "d": 36, "y0": 19, "y1": 26, "m": "stone", "solid": 1, "sheen": False},
        {"k": "dome", "w": 34, "cv": 36, "d": 34, "y0": 26, "y1": 38, "m": "green"},
        {"k": "box", "w": 50, "v": 0, "d": 9, "y0": 0, "y1": 21, "m": "stone", "solid": 1, "sheen": False},
        {"k": "cols", "w": 44, "y0": 1, "y1": 20, "n": 6},
        {"k": "pediment", "w": 54, "y0": 21, "y1": 28},
        {"k": "door", "w": 6, "h": 10}]}


def _convention():
    """Pennsylvania Convention Center (about 230 x 260 m as drawn): the Reading Terminal headhouse of red
    brick on Market Street, the great glass barrel vault of the train shed running back behind it, and the
    long glass exhibition halls beyond."""
    return {"h": 36, "D": 260, "parts": [
        {"k": "box", "w": 230, "v": 120, "d": 140, "y0": 0, "y1": 28, "m": "glass", "fl": 9, "mu": 10},
        {"k": "vault", "w": 80, "v": 28, "d": 150, "y0": 0, "y1": 32},
        {"k": "box", "w": 62, "v": 0, "d": 30, "y0": 0, "y1": 27, "m": "brick", "solid": 1, "fl": 9, "mu": 7, "top": False},
        {"k": "hip", "w": 62, "v": 0, "d": 30, "y0": 27, "y1": 31, "m": "slate"},
        {"k": "door", "w": 8, "h": 14}]}


def _station():
    """30th Street Station (1933; about 195 x 100 m, 32 m): the long block of pale stone, its giant
    columns, the stepped parapet."""
    return {"h": 32, "D": 100, "parts": [
        {"k": "box", "w": 195, "v": 0, "d": 100, "y0": 0, "y1": 26, "m": "stone", "solid": 1},
        {"k": "strip", "w": 170, "y0": 3, "y1": 21, "t": "win", "op": .55},
        {"k": "cols", "w": 172, "y0": 2, "y1": 22, "n": 12},
        {"k": "door", "w": 9, "h": 12},
        {"k": "box", "w": 70, "cv": 50, "d": 40, "y0": 26, "y1": 32, "m": "stone", "solid": 1, "sheen": False}]}


# ── courthouses (law classes: federal / state / city courts as landmarks) ───
LEVELS = ("federal", "state", "city")
COURT_STYLES = ("classical", "modern", "tower")


def court_level(name: str = "", hint: str = "") -> str:
    """federal | state | city: the preset's hint (C1's city presets: level=...), else read from the name."""
    h = str(hint or "").lower()
    if h in LEVELS:
        return h
    n = str(name or "").lower()
    if re.search(r"united states|\bu\.? ?s\.?\b|federal|supreme court of the united states", n):
        return "federal"
    if re.search(r"county|city|municipal|criminal justice|traffic|family court|housing court|magistrate", n):
        return "city"
    return "state"


def court_style(h: float = 0, levels: float = 0, hint: str = "", tags: dict | None = None) -> str:
    """classical | modern | tower, from a hint, the architecture tag, or the height."""
    s = str(hint or "").lower()
    if s in COURT_STYLES:
        return s
    arch = str((tags or {}).get("building:architecture") or "").lower()
    if re.search(r"classic|revival|beaux|georgian|federal|greek|roman|historic", arch):
        return "classical"
    hh = h or (levels * 3.8 if levels else 0)
    if hh >= 60:
        return "tower"
    if hh and hh <= 32:
        return "classical"
    return "modern" if hh else "classical"


def courthouse_spec(style: str = "classical", level: str = "state", W: float = 0, D: float = 0, h: float = 0, dome: bool = False) -> dict:
    """A courthouse on its footprint, W x D m, h m to the top, in one of three types:
    - classical: a columned portico and pediment on steps between flanking wings, a dome or cupola when asked
      (US Supreme Court, Suffolk County Courthouse, Prettyman);
    - modern: a stone podium and a glass-and-stone slab with a glass atrium on the street (Moakley,
      Moynihan, Thurgood Marshall);
    - tower: a granite podium with a ribbon-windowed tower above (Criminal Justice Center, 60 Centre St as a
      municipal court building).
    The level shows as a small seal in its accent (federal / state / city), on the pediment or over the door."""
    lv = level if level in LEVELS else "state"
    if style == "modern":
        W, D, h = W or 80, D or 55, h or 60
        return {"h": h, "D": D, "kind": "courthouse", "level": lv, "parts": [
            {"k": "box", "w": W, "v": 0, "d": D, "y0": 0, "y1": 12, "m": "granite", "solid": 1, "mu": 6, "sheen": False},
            {"k": "box", "w": W * .78, "cv": D * .55, "d": D * .62, "y0": 12, "y1": h, "m": "stone", "solid": 1, "fl": 8, "mu": 5},
            {"k": "box", "x": -W * .12, "w": W * .42, "cv": D * .55 - D * .31 - 3, "d": 6, "y0": 12, "y1": h * .82, "m": "glass", "fl": 8, "mu": 4},
            {"k": "box", "w": W * .5, "v": 0, "d": 8, "y0": 0, "y1": 14, "m": "glass", "fl": 7, "mu": 5, "sheen": False},
            {"k": "door", "w": 6, "h": 7},
            {"k": "seal", "y": 10.5, "r": 2.6, "lv": lv}]}
    if style == "tower":
        W, D, h = W or 80, D or 60, h or 80
        return {"h": h, "D": D, "kind": "courthouse", "level": lv, "parts": [
            {"k": "box", "w": W, "v": 0, "d": D, "y0": 0, "y1": 20, "m": "granite", "solid": 1, "mu": 7, "sheen": False},
            {"k": "box", "w": W * .58, "cv": D * .55, "d": D * .55, "y0": 20, "y1": h - 4, "m": "granite", "solid": 1, "rib": 4.2, "mu": 3},
            {"k": "box", "w": W * .5, "cv": D * .55, "d": D * .47, "y0": h - 4, "y1": h, "m": "trim", "solid": 1, "sheen": False},
            {"k": "box", "w": W * .36, "v": 0, "d": 7, "y0": 0, "y1": 16, "m": "glass", "fl": 5, "mu": 4, "sheen": False},
            {"k": "door", "w": 6, "h": 7},
            {"k": "seal", "y": 18, "r": 2.8, "lv": lv}]}
    W, D, h = W or 90, D or 45, h or (40 if dome else 28)
    body = h * (.52 if dome else .7)
    pw = min(W * .58, 70)
    parts = [
        {"k": "box", "w": W, "v": 10, "d": D - 10, "y0": 0, "y1": body, "m": "stone", "solid": 1, "mu": 8, "fl": body / 2.2, "top": False},
        {"k": "hip", "w": W, "v": 10, "d": D - 10, "y0": body, "y1": body + 3.5, "m": "marble", "inset": 5},
    ]
    if dome:
        parts += [{"k": "box", "w": W * .24, "cv": D * .55, "d": W * .24, "y0": body, "y1": body + h * .14, "m": "stone", "solid": 1, "sheen": False},
                  {"k": "dome", "w": W * .22, "cv": D * .55, "d": W * .22, "y0": body + h * .14, "y1": h - 2, "m": "slate"},
                  {"k": "spire", "cv": D * .55, "y0": h - 2.5, "y1": h, "w": 1.2}]
    parts += [
        {"k": "box", "w": pw + 8, "v": 0, "d": 6, "y0": 0, "y1": 2, "m": "stone", "solid": 1, "sheen": False, "top": True},
        {"k": "box", "w": pw, "v": 2, "d": 12, "y0": 2, "y1": body + 1, "m": "marble", "solid": 1, "sheen": False, "top": False},
        {"k": "hip", "w": pw, "v": 2, "d": 12, "y0": body + 1, "y1": body + pw * .22, "m": "marble", "inset": pw * .5 - .6},
        {"k": "cols", "w": pw * .9, "y0": 2.5, "y1": body - .5, "n": 6 if pw < 45 else 8},
        {"k": "pediment", "w": pw + 3, "y0": body + 1, "y1": body + 1 + pw * .22},
        {"k": "door", "w": 4, "h": 7},
        {"k": "seal", "y": body + 1 + pw * .08, "r": min(3.6, pw * .07), "lv": lv}]
    return {"h": max(h, body + 1 + pw * .22), "D": D, "kind": "courthouse", "level": lv, "parts": parts}


def _usch():
    """James A. Byrne United States Courthouse (601 Market St, 1975): the modern federal courthouse of
    the Eastern District of Pennsylvania and the Third Circuit, a stone-and-glass slab over a podium
    (height and plan approximate)."""
    return courthouse_spec("modern", "federal", 100, 60, 75)


def _nix():
    """Robert N.C. Nix Sr. Federal Building and US Courthouse (900 Market St, 1941): stripped classical
    limestone, pilasters running the full height of its Market Street front, a set-back top storey
    (height and plan approximate)."""
    W, D, h = 120, 60, 45
    return {"h": h, "D": D, "kind": "courthouse", "level": "federal", "parts": [
        {"k": "box", "w": W, "v": 0, "d": D, "y0": 0, "y1": h - 6, "m": "stone", "solid": 1, "fl": 13},
        {"k": "cols", "w": W * .7, "y0": 4, "y1": h - 9, "n": 14},
        {"k": "box", "w": W * .8, "cv": D / 2 + 2, "d": D - 10, "y0": h - 6, "y1": h, "m": "stone", "solid": 1, "sheen": False},
        {"k": "box", "w": 22, "v": 0, "d": 3, "y0": 0, "y1": 9, "m": "trim", "solid": 1, "sheen": False, "top": False},
        {"k": "door", "w": 7, "h": 8},
        {"k": "seal", "y": h - 9 + 2, "r": 3, "lv": "federal"}]}


def _cjc():
    """Criminal Justice Center (1301 Filbert St, 1995): the courts of the First Judicial District, a
    granite tower in ribbons of glazing over a granite podium (height and plan approximate)."""
    return courthouse_spec("tower", "city", 80, 60, 82)


def _generic():
    s = spec_from_osm({"height": "25", "roof:shape": "gabled", "building:material": "stone"}, 60, 40)
    s["parts"].append({"k": "door", "v": (40 - 40) / 2, "w": 8, "h": 10})
    return s


LANDMARKS = {"ind": _independence, "city": _cityhall, "art": _artmuseum, "frank": _franklin, "conv": _convention,
             "stn": _station, "gen": _generic, "usch": _usch, "nix": _nix, "cjc": _cjc,
             "lib1": _lib1, "lib2": _lib2, "ccc": _ccc, "ctc": _ctc, "bny": _bny, "tls": _tls, "cira": _cira, "fmc": _fmc}


COURTS = {}     # the page's courthouse for any city: one per type and level, stretched to the record's height / width
for _st in COURT_STYLES:
    for _lv in LEVELS:
        COURTS[f"ct-{_st}-{_lv}"] = None


def build_all() -> dict:
    out = {k: build(f()) for k, f in LANDMARKS.items()}
    out.update(GENERIC)
    for k in COURTS:
        _, st, lv = k.split("-")
        out[k] = build(courthouse_spec(st, lv))
    return out


def scale_of(art: dict, l: dict | None = None) -> tuple:
    """(sx, sy): map px per canvas metre across and up for a landmark record — SCALE both ways, except a
    generic g-* building (art["_k"]) stretched to the record's own height hm (and width fw, when given)."""
    if l and art.get("fp") and str(art.get("_k", "")).startswith(("g-", "ct-")):
        try:
            hm = float(l.get("hm") or 0)
            fw = float(l.get("fw") or 0)
        except (TypeError, ValueError):
            hm = fw = 0
        if hm > 0:
            sy = SCALE * hm / art["hm"]
            return (SCALE * fw / art["fw"] if fw > 0 else sy), sy
    return SCALE, SCALE


def card(box: list, art: dict, l: dict | None = None) -> tuple:
    """A landmark's card (x, y, w, h): its footprint's projected bounding box at the one scale (from the
    footprint's METRES, never from the cell count), centred across its block and standing on the block's
    front (lower) edge. palace_landmarks' cardOf() (the page) and palace.py's chipLot() mirror this."""
    sx, sy = scale_of(art, l)
    fp = art["fp"]
    w, h = (fp[2] - fp[0]) * sx, (fp[3] - fp[1]) * sy
    return (box[0] + box[2]) / 2 - w / 2, box[3] - 14 - h, w, h


def stagger(landmarks: list, art, is_tall) -> dict:
    """{landmark name: dx}: a tower whose art would stand in front of (or behind) another tower's in the same
    column of blocks slides to one side of its block (never past it) so both stay readable. Towers are taken back
    to front; each takes the first of [0, left, right] that overlaps the towers already placed least.
    palace_landmarks' plan() (the page) mirrors this exactly."""
    ts = sorted((l for l in landmarks if l.get("box") and is_tall(l)), key=lambda l: (l["box"][3], l["box"][0], str(l.get("n"))))
    placed, out = [], {}
    for l in ts:
        a = art(l)
        b = l["box"]
        x, y, w, h = card(b, a, l)
        room = max(0.0, (b[2] - b[0] - 28 - w) / 2)
        bw, top, gy = w * .7, a.get("hm", 100) * SCALE, y + h
        best, bo = 0.0, None
        for dx in (0.0, -room, room):
            cx = x + w / 2 + dx
            o = sum(max(0.0, min(cx + bw / 2, q[1]) - max(cx - bw / 2, q[0])) * max(0.0, min(gy, q[3]) - max(gy - top, q[2])) for q in placed)
            if bo is None or o < bo - 1e-6:
                best, bo = dx, o
        cx = x + w / 2 + best
        placed.append((cx - bw / 2, cx + bw / 2, gy - top, gy))
        out[l.get("n")] = best
    return out


def drawn_height(art: dict) -> float:
    """The map px a building's tip stands above its ground line at zoom 1 (= SCALE x real height)."""
    return round(art["hm"] * SCALE, 1)


__all__ = ["SCALE", "KV", "build", "build_all", "spec_from_osm", "parse_height", "card", "stagger", "scale_of",
           "drawn_height", "LANDMARKS", "GENERIC", "courthouse_spec", "court_level", "court_style"]
