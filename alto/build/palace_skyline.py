"""The Mind Palace's building generator: every landmark and tower drawn from data, at ONE scale.

Why: the art used to be hand-drawn per building and then squeezed into whatever card its block
gave it (`preserveAspectRatio meet`), so a tower's size on the map said how many grid cells its OSM
outline happened to touch, not how tall it is (One Liberty Place on 2 x 2 cells drew 2.7 x Two
Liberty Place on 1 cell; Comcast Technology Center, the tallest, drew smaller than BNY Mellon).

The rule now:
- ONE SCALE. Every building is drawn in real metres (1 art unit = 1 m, both axes) and shown at
  `SCALE` map px per metre at every size of card: drawn height = SCALE x real height, for towers
  and low landmarks alike. A tower stands on its plot (a card of one fixed size) and rises above
  it as far as it really does; a low landmark stands at the foot of its block's card.
- PARAMETRIC. A building is a short list of parts in metres (a shaft that may taper or step,
  a podium, and a crown: flat, stepped, gables, spire, angled slice, pyramid, dome, barrel vault,
  pediment, hip, cut corners, glass blades, diamond facets ...). `spec_from_osm(tags)` turns OSM
  tags (height, building:levels, roof:shape, roof:height, building:material, min width) into the
  same parts, so ANY city's notable buildings are drawn the same way; the famous ones below are
  hand-tuned overrides of that generic spec (`LANDMARKS`).
- ALTO GLASS. Each solid is a frosted front face (a soft gradient, slightly translucent), a darker
  side face and a light top stepping back to the upper right, one line weight in the district's
  colour, one white sheen line, a few faint floor lines instead of window grids, round joins.

Heights (m, to the tip): Skyscraper Center / Wikipedia. Widths are the main face's real width,
rounded; the parts are simplified silhouettes, not copies of any drawing or photograph.
"""
from __future__ import annotations

import re

SCALE = 1.3          # map px per real metre, both axes, EVERY building (about the grid's own scale: a 240 px block ~ 160-185 m of Center City with its street)
TOP, FOOT, SIDE = 3.0, 3.0, 4.0     # canvas margins (m): above the tip, below the ground line, each side


def _f(n: float) -> str:
    s = f"{n:.1f}"
    return s[:-2] if s.endswith(".0") else s


def _dep(w: float) -> float:
    """How far a solid's side face steps back (m): thin for a thin part, never deep."""
    return max(1.2, min(6.0, w * .12))


class Sky:
    """One building drawn from its parts (metres, y up from the ground, x from the centre line)."""

    def __init__(self, parts: list, tip: float):
        half = 0.0
        for p in parts:
            w = max(p.get("w", 0), p.get("w1", 0))
            half = max(half, abs(p.get("x", 0)) + w / 2 + (_dep(w) if p["k"] in ("box", "slice", "cut") else 0))
        self.W = round(2 * half + 2 * SIDE, 1)
        self.G = tip + TOP                       # canvas y of the ground line
        self.H = round(self.G + FOOT, 1)
        self.cx = self.W / 2
        self.tip = tip
        self.parts = []
        self.add(f'<path class="lz-gs" d="M{_f(self.X(-half))} {_f(self.G)}l{_f(SIDE)} {_f(-SIDE / 2)}H{_f(self.X(half) + SIDE)}l{_f(-SIDE)} {_f(SIDE / 2)}z"/>')
        for p in parts:
            getattr(self, "_" + p["k"])(p)

    # coordinates
    def X(self, x):
        return self.cx + x

    def Y(self, y):
        return self.G - y

    def add(self, s):
        self.parts.append(s)

    def pts(self, ps):
        return "M" + "L".join(f"{_f(a)} {_f(b)}" for a, b in ps) + "z"

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
        """A shaft, a podium, a stage: may taper (w at the foot, w1 at the top). fl: a faint floor line
        every fl metres; mu: that many faint mullion lines; rib: dark glazing ribbons every rib metres."""
        x, w, w1, y0, y1, m = p.get("x", 0), p["w"], p.get("w1", p["w"]), p["y0"], p["y1"], p.get("m", "glass")
        l0, r0, l1, r1 = self.X(x - w / 2), self.X(x + w / 2), self.X(x - w1 / 2), self.X(x + w1 / 2)
        Y0, Y1, d = self.Y(y0), self.Y(y1), _dep(max(w, w1))
        if p.get("side", True):
            self.face([(r1, Y1), (r1 + d, Y1 - d / 2), (r0 + d, Y0 - d / 2), (r0, Y0)], m, "s")
        if p.get("top", True):
            self.face([(l1, Y1), (l1 + d, Y1 - d / 2), (r1 + d, Y1 - d / 2), (r1, Y1)], m, "t")
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
        d = _dep(w)
        self.face([(r, self.Y(yr)), (r + d, self.Y(yr) - d / 2), (r + d, self.Y(y0) - d / 2), (r, self.Y(y0))], m, "s")
        self.face([(l, self.Y(yl)), (l + d, self.Y(yl) - d / 2), (r + d, self.Y(yr) - d / 2), (r, self.Y(yr))], m, "t")
        self.front([(l, self.Y(y0)), (l, self.Y(yl)), (r, self.Y(yr)), (r, self.Y(y0))], m)
        roof = (lambda X_: yl + (yr - yl) * (X_ - l) / (r - l))
        self._lines(l, r, l, r, y0, max(yl, yr), p, roof)
        for c in p.get("creases", []):                          # folded planes: a lit strip and a shaded one
            xa, xb = self.X(x - w / 2 + w * c[0]), self.X(x - w / 2 + w * c[1])
            self.add(f'<path class="{"lz-sl" if c[2] == "lit" else "lz-gs"}" d="{self.pts([(xa, self.Y(y0)), (xa, self.Y(roof(xa))), (xb, self.Y(roof(xb))), (xb, self.Y(y0))])}" opacity="{.38 if c[2] == "lit" else .7}"/>')
        if p.get("facets"):                                     # a diamond lattice, clipped to the face (clipPath: Safari-safe, no mask)
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
        l, r, d = self.X(x - w / 2), self.X(x + w / 2), _dep(w)
        Y0, Y1, Yc = self.Y(y0), self.Y(y1), self.Y(y1 - c)
        self.face([(r, Yc), (r + d, Yc - d / 2), (r + d, Y0 - d / 2), (r, Y0)], m, "s")
        self.face([(r - c, Y1), (r - c + d, Y1 - d / 2), (r + d, Yc - d / 2), (r, Yc)], m, "s")
        self.face([(l + c, Y1), (l + c + d, Y1 - d / 2), (r - c + d, Y1 - d / 2), (r - c, Y1)], m, "t")
        self.front([(l, Y0), (l, Yc), (l + c, Y1), (r - c, Y1), (r, Yc), (r, Y0)], m)
        if p.get("band"):
            self.add(f'<path class="lz-win" d="M{_f(l + c * .6)} {_f(Yc + 1)}H{_f(r - c * .6)}v{_f(c * .6)}H{_f(l + c * .6)}z" opacity=".75"/>')

    def _gables(self, p):
        """A crown of stacked gables, each narrower (the Liberty Places, after the Chrysler Building).
        Returns nothing; the apex height is p['apex'] (filled in by `gables_apex`)."""
        x, y, m, rise = p.get("x", 0), p["y0"], p.get("m", "glass"), p.get("rise", .42)
        for w, wall in zip(p["ws"], p["walls"]):
            hw, yw = w / 2, y + wall
            ap = yw + w * rise
            d = _dep(w) * .8
            l, r = self.X(x - hw), self.X(x + hw)
            self.face([(r, self.Y(y)), (r + d, self.Y(y) - d / 2), (r + d, self.Y(yw) - d / 2), (self.X(x) + d, self.Y(ap) - d / 2),
                       (self.X(x), self.Y(ap)), (r, self.Y(yw))], m, "s")
            self.front([(l, self.Y(y)), (l, self.Y(yw)), (self.X(x), self.Y(ap)), (r, self.Y(yw)), (r, self.Y(y))], m)
            self.add(f'<path class="lz-mu" d="M{_f(l + w * .1)} {_f(self.Y(yw) - .4)}L{_f(self.X(x))} {_f(self.Y(ap) + w * .1)}L{_f(r - w * .1)} {_f(self.Y(yw) - .4)}"/>')
            y = yw + w * rise * .55

    def _spire(self, p):
        x, y0, y1, w = p.get("x", 0), p["y0"], p["y1"], p.get("w", 1.6)
        self.front([(self.X(x - w / 2), self.Y(y0)), (self.X(x), self.Y(y1)), (self.X(x + w / 2), self.Y(y0))], p.get("m", "trim"), "lz-f")
        self.add(f'<path class="lz-ln" d="M{_f(self.X(x))} {_f(self.Y(y0))}V{_f(self.Y(y1))}"/>')

    def _pyramid(self, p):
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "glass")
        l, r, d = self.X(x - w / 2), self.X(x + w / 2), _dep(w)
        self.face([(r, self.Y(y0)), (r + d, self.Y(y0) - d / 2), (self.X(x) + d * .5, self.Y(y1) - d / 4), (self.X(x), self.Y(y1))], m, "s")
        self.front([(l, self.Y(y0)), (self.X(x), self.Y(y1)), (r, self.Y(y0))], m)
        self.add(f'<path class="lz-mu" d="M{_f(self.X(x))} {_f(self.Y(y1))}V{_f(self.Y(y0))}M{_f(l + w * .18)} {_f(self.Y(y0 + (y1 - y0) * .36))}H{_f(r - w * .18)}"/>')

    def _pediment(self, p):
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "trim")
        l, r = self.X(x - w / 2), self.X(x + w / 2)
        self.front([(l, self.Y(y0)), (self.X(x), self.Y(y1)), (r, self.Y(y0))], m, "lz-f")

    def _hip(self, p):
        """A hipped / mansard roof seen from the front, its side slope behind."""
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "slate")
        ins = p.get("inset", (y1 - y0) * 1.1)
        l, r, d = self.X(x - w / 2), self.X(x + w / 2), _dep(w) * .8
        self.face([(r, self.Y(y0)), (r + d, self.Y(y0) - d / 2), (r - ins + d, self.Y(y1) - d / 2), (r - ins, self.Y(y1))], m, "s")
        self.front([(l, self.Y(y0)), (l + ins, self.Y(y1)), (r - ins, self.Y(y1)), (r, self.Y(y0))], m, "lz-f")

    def _dome(self, p):
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "slate")
        l, r, h = self.X(x - w / 2), self.X(x + w / 2), y1 - y0
        arc = f"M{_f(l)} {_f(self.Y(y0))}C{_f(l)} {_f(self.Y(y0 + h * .78))} {_f(self.X(x - w * .28))} {_f(self.Y(y1))} {_f(self.X(x))} {_f(self.Y(y1))}" \
              f"S{_f(r)} {_f(self.Y(y0 + h * .78))} {_f(r)} {_f(self.Y(y0))}z"
        self.add(f'<path class="lz-f" d="{arc}" fill="url(#lzg-{m}-{{s}})"/>')
        self.add(f'<path class="lz-mu" d="M{_f(self.X(x))} {_f(self.Y(y1))}V{_f(self.Y(y0))}M{_f(self.X(x - w * .25))} {_f(self.Y(y0 + h * .86))}Q{_f(self.X(x - w * .36))} {_f(self.Y(y0 + h * .4))} {_f(self.X(x - w * .36))} {_f(self.Y(y0))}'
                 f'M{_f(self.X(x + w * .25))} {_f(self.Y(y0 + h * .86))}Q{_f(self.X(x + w * .36))} {_f(self.Y(y0 + h * .4))} {_f(self.X(x + w * .36))} {_f(self.Y(y0))}"/>')

    def _vault(self, p):
        """A barrel vault seen end on: a glass arch on steel ribs, its long roof running back (the train shed)."""
        x, w, y0, y1, m = p.get("x", 0), p["w"], p["y0"], p["y1"], p.get("m", "glass")
        l, r, h, d = self.X(x - w / 2), self.X(x + w / 2), y1 - y0, 9.0
        arc = lambda dx, dy: (f"M{_f(l + dx)} {_f(self.Y(y0) + dy)}V{_f(self.Y(y0 + h * .45) + dy)}C{_f(l + dx)} {_f(self.Y(y1) + dy)} {_f(r + dx)} {_f(self.Y(y1) + dy)} "
                              f"{_f(r + dx)} {_f(self.Y(y0 + h * .45) + dy)}V{_f(self.Y(y0) + dy)}z")
        self.add(f'<path class="lz-sd lz-s-{m}" d="{arc(d, -d / 2)}"/>')
        self.add(f'<path class="lz-f lz-gl" d="{arc(0, 0)}" fill="url(#lzg-{m}-{{s}})"/>')
        ribs = ""
        for u in (.2, .4, .6, .8):
            xa = l + (r - l) * u
            ribs += f"M{_f(xa)} {_f(self.Y(y0))}V{_f(self.Y(y0 + h * (.45 + .5 * (1 - abs(u - .5) * 2) ** .5 * .55)))}"
        ribs += f"M{_f(l)} {_f(self.Y(y0 + h * .45))}C{_f(l)} {_f(self.Y(y1 - h * .12))} {_f(r)} {_f(self.Y(y1 - h * .12))} {_f(r)} {_f(self.Y(y0 + h * .45))}"
        self.add(f'<path class="lz-mu" d="{ribs}"/>')

    def _cols(self, p):
        """A colonnade's rhythm: n columns as white strokes over the front (one weight, no texture)."""
        x, w, y0, y1, n = p.get("x", 0), p["w"], p["y0"], p["y1"], p["n"]
        d = "".join(f"M{_f(self.X(x - w / 2 + w * (i + .5) / n))} {_f(self.Y(y0))}V{_f(self.Y(y1))}" for i in range(n))
        self.add(f'<path class="lz-col-l" d="{d}"/>')

    def _blades(self, p):
        """A lantern of glass blades, the centre tallest (Comcast Technology Center)."""
        x, w, y0, tops = p.get("x", 0), p["w"], p["y0"], p["tops"]
        n = len(tops)
        bw = w / n * .55
        for i, t in enumerate(tops):
            cx = self.X(x - w / 2 + w * (i + .5) / n)
            self.front([(cx - bw / 2, self.Y(y0)), (cx - bw / 2, self.Y(t)), (cx + bw / 2, self.Y(t)), (cx + bw / 2, self.Y(y0))], p.get("m", "trim"), "lz-f")

    def _brace(self, p):
        """Cross-bracing bands over a (tapering) face (the CTC's corset)."""
        x, w, w1, y0, y1, n = p.get("x", 0), p["w"], p.get("w1", p["w"]), p["y0"], p["y1"], p["n"]
        d = ""
        for k in range(n):
            ya, yb = y0 + (y1 - y0) * k / n, y0 + (y1 - y0) * (k + 1) / n
            wa, wb = w + (w1 - w) * k / n, w + (w1 - w) * (k + 1) / n
            d += (f"M{_f(self.X(x - wa / 2))} {_f(self.Y(ya))}L{_f(self.X(x + wb / 2))} {_f(self.Y(yb))}"
                  f"M{_f(self.X(x + wa / 2))} {_f(self.Y(ya))}L{_f(self.X(x - wb / 2))} {_f(self.Y(yb))}")
        self.add(f'<path class="lz-mu lz-mu2" d="{d}"/>')

    def _strip(self, p):
        """A plain flat strip over a face: notches, ultra-clear corners, a cornice line (no 3D)."""
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
        self.add(f'<path class="lz-f" d="M{_f(x - h * .14)} {_f(b)}L{_f(x - h * .09)} {_f(b - h * .72)}H{_f(x + h * .09)}L{_f(x + h * .14)} {_f(b)}z'
                 f'M{_f(x + h * .08)} {_f(b - h * .66)}l{_f(h * .3)} {_f(-h * .16)}l0 {_f(h * .08)}l{_f(-h * .28)} {_f(h * .16)}z" fill="url(#lzg-bronze-{{s}})"/>'
                 f'<circle class="lz-f" cx="{_f(x)}" cy="{_f(b - h * .82)}" r="{_f(h * .1)}" fill="url(#lzg-bronze-{{s}})"/>'
                 f'<path class="lz-ln" d="M{_f(x - h * .16)} {_f(b - h * .9)}h{_f(h * .32)}"/>')

    def _door(self, p):
        x, w, h = self.X(p.get("x", 0)), p["w"], p["h"]
        self.add(f'<path class="lz-door" d="M{_f(x - w / 2)} {_f(self.G)}V{_f(self.G - h + w / 2)}a{_f(w / 2)} {_f(w / 2)} 0 0 1 {_f(w)} 0V{_f(self.G)}z"/>')

    def out(self, **meta) -> dict:
        return {"w": self.W, "h": self.H, "svg": "".join(self.parts), "hm": self.tip, **meta}


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
    y = y0
    ap = y0
    for w, wall in zip(ws, walls):
        ap = y + wall + w * rise
        y = y + wall + w * rise * .55
    return ap


def build(spec: dict) -> dict:
    """A building's art from its spec {h: tip height m, parts: [...], fw: plot width m}."""
    return Sky(spec["parts"], spec["h"]).out(fw=spec.get("fw") or max(p.get("w", 0) for p in spec["parts"]))


# ── the generic building, from OSM tags (any city) ──────────────────────────
ROOF = {"flat": "flat", "skillion": "angled", "lean_to": "angled", "saltbox": "angled", "pyramidal": "pyramid",
        "dome": "dome", "onion": "dome", "round": "vault", "half-round": "vault", "gabled": "gable", "gambrel": "gable",
        "hipped": "hip", "half-hipped": "hip", "mansard": "hip", "side_hipped": "hip", "spire": "spire", "cone": "spire"}
MATERIAL = {"glass": "glass", "brick": "brick", "stone": "stone", "sandstone": "sand", "limestone": "sand", "marble": "marble",
            "granite": "granite", "concrete": "stone", "metal": "silver", "steel": "silver", "aluminium": "silver", "wood": "sand"}


def parse_height(v) -> float:
    """OSM height text in metres: '288', '288 m', '945 ft', "945'", "945'6\"" (None when it is not a height)."""
    if v is None:
        return 0.0
    s = str(v).strip().lower().replace(",", ".")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:'|ft|feet)\s*(?:(\d+(?:\.\d+)?)\s*(?:\"|in))?$", s)
    if m:
        return round(float(m.group(1)) * .3048 + float(m.group(2) or 0) * .0254, 1)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(m|metres?|meters?)?$", s)
    return float(m.group(1)) if m else 0.0


def spec_from_osm(tags: dict, width_m: float | None = None) -> dict:
    """The parts of an ordinary notable building from its OSM tags (and Wikidata-like facts in the same
    keys: height, building:levels, roof:shape, roof:height, building:material). width_m: the narrower
    side of its footprint, when the outline is known."""
    t = tags or {}
    h = parse_height(t.get("height"))
    lv = parse_height(t.get("building:levels"))
    rh = parse_height(t.get("roof:height"))
    if not h:
        h = (lv * 3.5 if lv else 12.0) + rh
    shape = ROOF.get(str(t.get("roof:shape") or "flat").lower(), "flat")
    m = MATERIAL.get(str(t.get("building:material") or t.get("building:facade:material") or "").lower(),
                     "glass" if h >= 60 else "stone")
    w = float(width_m) if width_m else max(16.0, min(60.0, h * .3 if h >= 60 else 40.0))
    w = max(8.0, min(w, 120.0))
    if not rh:
        rh = {"flat": 0, "angled": w * .35, "pyramid": w * .45, "dome": w * .45, "vault": w * .4, "gable": w * .3,
              "hip": w * .2, "spire": max(h * .25, w * .8)}[shape]
    rh = min(rh, h * .6)
    body = h - rh
    parts = []
    tall = h >= 60
    if tall:
        parts.append({"k": "box", "w": w * 1.35, "y0": 0, "y1": min(16, body * .08), "m": "granite", "solid": 1, "sheen": False})
    y0 = parts[-1]["y1"] if parts else 0
    fl = 3.5 * (4 if tall else 1)
    if shape == "angled":
        parts.append({"k": "slice", "w": w, "y0": y0, "yl": body, "yr": h, "m": m, "fl": fl, "mu": 4 if tall else 2})
    else:
        parts.append({"k": "box", "w": w, "y0": y0, "y1": body, "m": m, "fl": fl, "mu": max(2, int(w / 9)), "solid": m != "glass"})
        crown = {"pyramid": {"k": "pyramid", "w": w}, "dome": {"k": "dome", "w": w * .8}, "vault": {"k": "vault", "w": w},
                 "gable": {"k": "pediment", "w": w * 1.04, "m": "slate"}, "hip": {"k": "hip", "w": w * 1.04, "inset": rh * 1.1},
                 "spire": {"k": "spire", "w": max(2.0, w * .35), "m": "slate" if not tall else "trim"}}.get(shape)
        if crown:
            parts.append({**crown, "y0": body, "y1": h})
    return {"h": round(h, 1), "parts": parts, "fw": round(w * (1.35 if tall else 1), 1), "shape": shape}


GENERIC = {}    # the page's fallback for a mapped building with a height but no art of its own: one per roof shape at 100 m
for _shape, _tags in (("flat", {}), ("angled", {"roof:shape": "skillion"}), ("pyramid", {"roof:shape": "pyramidal"}),
                      ("dome", {"roof:shape": "dome"}), ("spire", {"roof:shape": "spire"}), ("gable", {"roof:shape": "gabled"})):
    GENERIC["g-" + _shape] = build(spec_from_osm({"height": "100", **_tags}, 30))


# ── the famous ones: hand-tuned specs (metres) ──────────────────────────────
def _lib1():
    """One Liberty Place (Jahn, 1987; 288 m, 61 floors): sapphire glass banded in pale granite,
    two setbacks, a crown of four stacked gables (after the Chrysler Building) and a steel spire.
    The first tower above William Penn's hat."""
    ws, walls = [34, 27, 20, 13], [4, 4, 3, 3]
    ap = gables_apex(222, ws, walls)
    return {"h": 288, "fw": 66, "parts": [
        {"k": "box", "w": 66, "y0": 0, "y1": 14, "m": "granite", "solid": 1, "sheen": False, "mu": 5},
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
    return {"h": 258, "fw": 58, "parts": [
        {"k": "box", "w": 58, "y0": 0, "y1": 14, "m": "granite", "solid": 1, "sheen": False, "mu": 4},
        {"k": "box", "w": 42, "y0": 14, "y1": 194, "m": "sapphire", "fl": 13.5, "mu": 4},
        {"k": "strip", "w": 3.5, "x": -19.2, "y0": 14, "y1": 194, "t": "lit", "op": .35},
        {"k": "box", "w": 34, "y0": 194, "y1": 214, "m": "sapphire", "fl": 9, "mu": 3},
        {"k": "gables", "ws": ws, "walls": walls, "y0": 214, "m": "sapphire"},
        {"k": "spire", "y0": ap - 2, "y1": 258, "w": 2}]}


def _ccc():
    """Comcast Center (Stern, 2008; 297 m, 57 floors): a slab of silver glass over a glass winter
    garden, easing in near the top under two notches, ultra-clear corners and a glass-box crown."""
    return {"h": 297, "fw": 70, "parts": [
        {"k": "box", "w": 70, "y0": 0, "y1": 22, "m": "glass", "fl": 7, "mu": 8, "sheen": False},
        {"k": "box", "w": 52, "y0": 22, "y1": 238, "m": "silver", "fl": 14, "mu": 6},
        {"k": "box", "w": 52, "w1": 46, "y0": 238, "y1": 279, "m": "silver", "fl": 14, "mu": 6, "top": False, "sheen": False},
        {"k": "strip", "w": 3, "x": -24.5, "y0": 22, "y1": 279, "t": "lit", "op": .5},
        {"k": "strip", "w": 7, "x": 19, "y0": 250, "y1": 276, "t": "win", "op": .45},
        {"k": "box", "w": 44, "y0": 279, "y1": 297, "m": "trim", "mu": 3, "sheen": False}]}


def _ctc():
    """Comcast Technology Center (Foster + Partners, 2018; 342 m, 60 floors): a slim tower of clear
    glass easing in as it climbs, wrapped in bands of cross-bracing, on a long ribbed podium, ending in
    a lantern of glass blades. Philadelphia's tallest."""
    return {"h": 342, "fw": 92, "parts": [
        {"k": "box", "w": 92, "y0": 0, "y1": 20, "m": "granite", "solid": 1, "fl": 4, "sheen": False},
        {"k": "box", "w": 46, "w1": 41, "y0": 20, "y1": 304, "m": "glass", "fl": 16, "mu": 4},
        {"k": "brace", "w": 46, "w1": 41, "y0": 20, "y1": 304, "n": 5},
        {"k": "blades", "w": 40, "y0": 304, "tops": [318, 330, 342, 330, 318]}]}


def _bny():
    """BNY Mellon Center (KPF, 1990; 241 m, 54 floors): an obelisk of silver metal and glass tapering
    from a stone podium, its centre columns showing, a cornice and a pyramid of metal under a mast."""
    return {"h": 241, "fw": 68, "parts": [
        {"k": "box", "w": 68, "y0": 0, "y1": 20, "m": "granite", "solid": 1, "sheen": False, "mu": 5},
        {"k": "box", "w": 54, "w1": 42, "y0": 20, "y1": 199, "m": "silver", "fl": 15, "mu": 2},
        {"k": "box", "w": 46, "y0": 199, "y1": 204, "m": "trim", "sheen": False},
        {"k": "pyramid", "w": 44, "y0": 204, "y1": 233, "m": "silver"},
        {"k": "spire", "y0": 232, "y1": 241, "w": 1.4}]}


def _tls():
    """Three Logan Square (Kling Lindquist, 1991; 225 m, 55 floors): red granite in ribbons of dark
    glazing, stepping in twice to a crown whose top corners are cut away."""
    return {"h": 225, "fw": 60, "parts": [
        {"k": "box", "w": 60, "y0": 0, "y1": 14, "m": "garnet", "solid": 1, "sheen": False},
        {"k": "box", "w": 44, "y0": 14, "y1": 188, "m": "garnet", "solid": 1, "rib": 7, "mu": 3},
        {"k": "box", "w": 36, "y0": 188, "y1": 205, "m": "garnet", "solid": 1, "rib": 7},
        {"k": "cut", "w": 32, "y0": 205, "y1": 225, "c": 8, "m": "garnet", "band": 1}]}


def _cira():
    """Cira Centre (Pelli Clarke Pelli, 2005; 133 m, 29 floors): a prism of blue-green glass whose
    faceted faces read as diamonds, the roof cut in one long slope."""
    return {"h": 133, "fw": 52, "parts": [
        {"k": "slice", "w": 50, "y0": 0, "yl": 100, "yr": 133, "m": "aqua", "facets": "cira",
         "creases": [[0, .14, "lit"], [.86, 1, "shade"]]}]}


def _fmc():
    """FMC Tower (Pelli Clarke Pelli, 2016; 223 m, 49 floors): a slender tower of steel-blue glass
    folded into creased planes, its roof sliced at an angle, over a lower wing."""
    return {"h": 223, "fw": 56, "parts": [
        {"k": "box", "x": -15, "w": 26, "y0": 0, "y1": 40, "m": "steel", "fl": 10, "mu": 2, "sheen": False},
        {"k": "slice", "x": 6, "w": 36, "y0": 0, "yl": 204, "yr": 223, "m": "steel", "fl": 14, "mu": 3,
         "creases": [[0, .3, "lit"], [.72, 1, "shade"]]}]}


def _cityhall():
    """City Hall (McArthur, 1901; 167 m to the top of William Penn): the Second Empire block in white
    marble under slate mansards, corner and centre pavilions, and the tower — five times the block's
    height — rising in a shaft, a clock stage, an open colonnade and a dome, with Penn on top."""
    return {"h": 167, "fw": 145, "parts": [
        {"k": "hip", "w": 145, "y0": 34, "y1": 43, "inset": 9},
        {"k": "box", "w": 145, "y0": 0, "y1": 34, "m": "marble", "solid": 1, "fl": 11.5, "mu": 12, "top": False},
        *[q for x in (-61, 61) for q in (
            {"k": "box", "x": x, "w": 23, "y0": 0, "y1": 39, "m": "marble", "solid": 1, "fl": 11.5, "mu": 2, "sheen": False, "top": False},
            {"k": "hip", "x": x, "w": 23, "y0": 39, "y1": 50, "inset": 6})],
        {"k": "box", "w": 40, "y0": 0, "y1": 38, "m": "marble", "solid": 1, "top": False},
        {"k": "cols", "w": 36, "y0": 4, "y1": 34, "n": 8},
        {"k": "hip", "w": 40, "y0": 38, "y1": 47, "inset": 7},
        {"k": "box", "w": 26, "y0": 43, "y1": 102, "m": "marble", "solid": 1, "mu": 2},
        {"k": "box", "w": 23, "y0": 102, "y1": 117, "m": "marble", "solid": 1, "sheen": False},
        {"k": "clock", "y": 109.5, "r": 5.2},
        {"k": "box", "w": 18, "y0": 117, "y1": 131, "m": "trim", "solid": 1, "sheen": False},
        {"k": "cols", "w": 15, "y0": 118, "y1": 130, "n": 5},
        {"k": "dome", "w": 17, "y0": 131, "y1": 148, "m": "slate"},
        {"k": "box", "w": 5, "y0": 148, "y1": 152, "m": "trim", "solid": 1, "sheen": False, "side": False},
        {"k": "statue", "y0": 152, "y1": 167},
        {"k": "door", "w": 9, "h": 14}]}


def _independence():
    """Independence Hall (1753; 51 m to the tip): the Georgian main block of red brick under a hipped
    roof, the covered arcades and the two end buildings, and the white steeple — brick tower, clock
    stage, belfry, lantern and spire."""
    return {"h": 51, "fw": 104, "parts": [
        *[q for x in (-42, 42) for q in (
            {"k": "hip", "x": x, "w": 21, "y0": 11, "y1": 15},
            {"k": "box", "x": x, "w": 20, "y0": 0, "y1": 11, "m": "brick", "solid": 1, "mu": 4, "top": False},
            {"k": "hip", "x": x * .64, "w": 11, "y0": 6.5, "y1": 8.5},
            {"k": "box", "x": x * .64, "w": 10, "y0": 0, "y1": 6.5, "m": "brick", "solid": 1, "mu": 2, "top": False, "side": False})],
        {"k": "hip", "w": 34, "y0": 13, "y1": 19, "inset": 6},
        {"k": "box", "w": 33, "y0": 0, "y1": 13, "m": "brick", "solid": 1, "fl": 6.5, "mu": 8, "top": False},
        {"k": "box", "w": 9, "y0": 0, "y1": 29, "m": "brick", "solid": 1, "sheen": False},
        {"k": "box", "w": 8, "y0": 29, "y1": 34, "m": "trim", "solid": 1, "sheen": False},
        {"k": "clock", "y": 31.5, "r": 2},
        {"k": "box", "w": 6, "y0": 34, "y1": 40, "m": "trim", "solid": 1, "sheen": False, "mu": 2},
        {"k": "dome", "w": 5, "y0": 40, "y1": 43.5, "m": "trim"},
        {"k": "spire", "y0": 43, "y1": 51, "w": 1.5},
        {"k": "door", "w": 3.6, "h": 6}]}


def _artmuseum():
    """Philadelphia Museum of Art (1928; ~36 m): the temple front with its columns and pediment, the
    blue-green tiled roofs, the two long wings of tan limestone and their pedimented end pavilions."""
    return {"h": 36, "fw": 200, "parts": [
        *[q for x in (-61, 61) for q in (
            {"k": "hip", "x": x, "w": 64, "y0": 21, "y1": 26, "m": "teal"},
            {"k": "box", "x": x, "w": 62, "y0": 0, "y1": 21, "m": "sand", "solid": 1, "mu": 5, "top": False})],
        *[q for x in (-89, 89) for q in (
            {"k": "box", "x": x, "w": 22, "y0": 0, "y1": 23, "m": "sand", "solid": 1, "top": False, "sheen": False},
            {"k": "cols", "x": x, "w": 19, "y0": 1, "y1": 22, "n": 4},
            {"k": "pediment", "x": x, "w": 24, "y0": 23, "y1": 29})],
        {"k": "hip", "w": 56, "y0": 25, "y1": 32, "m": "teal"},
        {"k": "box", "w": 60, "y0": 0, "y1": 27, "m": "sand", "solid": 1, "top": False},
        {"k": "cols", "w": 54, "y0": 2, "y1": 24, "n": 8},
        {"k": "pediment", "w": 64, "y0": 27, "y1": 36},
        {"k": "door", "w": 6, "h": 11}]}


def _franklin():
    """The Franklin Institute (1934; ~38 m): a limestone block, its six-column portico and pediment,
    and the dome of the Benjamin Franklin National Memorial behind."""
    return {"h": 38, "fw": 140, "parts": [
        {"k": "box", "w": 34, "y0": 16, "y1": 26, "m": "stone", "solid": 1, "sheen": False},
        {"k": "dome", "w": 34, "y0": 26, "y1": 38, "m": "green"},
        {"k": "box", "w": 140, "y0": 0, "y1": 19, "m": "stone", "solid": 1, "mu": 10, "top": False},
        {"k": "box", "w": 50, "y0": 0, "y1": 21, "m": "stone", "solid": 1, "top": False, "sheen": False},
        {"k": "cols", "w": 44, "y0": 1, "y1": 20, "n": 6},
        {"k": "pediment", "w": 54, "y0": 21, "y1": 28},
        {"k": "door", "w": 6, "h": 10}]}


def _convention():
    """Pennsylvania Convention Center: the Reading Terminal headhouse of red brick with the great glass
    barrel vault of the train shed behind it, and the long glass halls of the expansion either side."""
    return {"h": 36, "fw": 330, "parts": [
        *[{"k": "box", "x": x, "w": 116, "y0": 0, "y1": 26, "m": "glass", "fl": 8.5, "mu": 9} for x in (-106, 106)],
        {"k": "vault", "w": 84, "y0": 0, "y1": 36},
        {"k": "hip", "w": 62, "y0": 27, "y1": 31, "m": "slate"},
        {"k": "box", "w": 60, "y0": 0, "y1": 27, "m": "brick", "solid": 1, "fl": 9, "mu": 7, "top": False},
        {"k": "door", "w": 8, "h": 14}]}


def _station():
    """30th Street Station (1933; ~30 m): the long block of pale stone, its giant columns, the stepped parapet."""
    return {"h": 32, "fw": 195, "parts": [
        {"k": "box", "w": 70, "y0": 26, "y1": 32, "m": "stone", "solid": 1, "sheen": False},
        {"k": "box", "w": 195, "y0": 0, "y1": 26, "m": "stone", "solid": 1, "top": False},
        {"k": "strip", "w": 170, "y0": 3, "y1": 21, "t": "win", "op": .55},
        {"k": "cols", "w": 172, "y0": 2, "y1": 22, "n": 12},
        {"k": "door", "w": 9, "h": 12}]}


def _generic():
    s = spec_from_osm({"height": "25", "roof:shape": "gabled", "building:material": "stone"}, 60)
    s["parts"].append({"k": "door", "w": 8, "h": 10})
    return s


LANDMARKS = {"ind": _independence, "city": _cityhall, "art": _artmuseum, "frank": _franklin, "conv": _convention,
             "stn": _station, "gen": _generic,
             "lib1": _lib1, "lib2": _lib2, "ccc": _ccc, "ctc": _ctc, "bny": _bny, "tls": _tls, "cira": _cira, "fmc": _fmc}


def build_all() -> dict:
    out = {k: build(f()) for k, f in LANDMARKS.items()}
    out.update(GENERIC)
    return out


def drawn_height(key: str, art: dict | None = None) -> float:
    """The map px a building's tip stands above its ground line at zoom 1 (= SCALE x real height)."""
    from .palace_landmarks import ART
    return round((art or ART[key])["hm"] * SCALE, 1)


def tall_card(box: list, fw: float) -> tuple:
    """A tower's plot on its landmark block: (x, y, w, h) of its card — the same size for every tower
    (one block's card, as narrow as its podium allows), centred across the landmark's cells and standing
    on their front (lower) edge however many cells its real outline covers. palace_landmarks' draw() and palace.py's chipLot() mirror this."""
    ins = 14
    x, y, w, h = box[0] + ins, box[1] + ins, box[2] - box[0] - 2 * ins, box[3] - box[1] - 2 * ins
    nw = min(w, max(72.0, fw * SCALE + 36))
    nh = min(h, 142.0)
    return x + (w - nw) / 2, y + h - nh, nw, nh


def stagger(landmarks: list, art: dict, is_tall) -> dict:
    """{landmark name: dx}: a tower whose art would stand in front of (or behind) another tower's in the same
    column of blocks slides to one side of its block (never past it) so both stay readable. Towers are taken back
    to front; each takes the first of [0, left, right] that overlaps the towers already placed least.
    palace_landmarks' plan() (the page) mirrors this exactly."""
    ts = sorted((l for l in landmarks if l.get("box") and is_tall(l)), key=lambda l: (l["box"][3], l["box"][0], str(l.get("n"))))
    placed, out = [], {}
    for l in ts:
        a = art(l)
        b = l["box"]
        x, y, w, h = tall_card(b, a.get("fw") or 40)
        room = max(0.0, (b[2] - b[0] - 28 - w) / 2)
        bw, top, gy = (a.get("fw") or 40) * SCALE * .8, a.get("hm", 100) * SCALE, y + h - 6
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


__all__ = ["SCALE", "build", "build_all", "spec_from_osm", "parse_height", "tall_card", "stagger", "drawn_height", "LANDMARKS", "GENERIC"]
