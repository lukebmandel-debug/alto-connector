"""Landmark buildings of the Mind Palace: a little 3D detail from real life, and a
clear sign when one has reference material inside.

Everything about a landmark building lives here; palace.py has four small hooks
(`LANDMARK_CSS`, `LANDMARK_JS`, `window._palLm.draw / relayout / tip / keyRow`).

- The art. Independence Hall, City Hall, the Museum of Art, the Franklin
  Institute, the Convention Center, 30th Street Station and a tidy default are
  drawn here as simplified, extruded elevations in Alto's glass look: a front
  face lit from the top left, a darker side and a lighter top where the building
  steps back, thin strokes in the landmark's own (district) colour, a soft shadow
  to the lower right. They are static `<symbol>`s, built once from Python and
  instanced with `<use>`, so they cost nothing at run time and weigh a few KB.
  Not a copy of any map or photograph: the real silhouette, simplified.
- The way in. A landmark whose `page` is an Index list (the Cases, a code, the
  Federal Rules …) is marked: a glass tag on its corner with the page's icon
  and its real count ("20 rules"), a glow in the page's colour, a lit doorway in
  the art, an "Open" cue on hover, a legend row, and a keyboard / screen reader
  label ("Independence Hall — inside: Federal Rules of Civil Procedure, 20
  rules. Open"). The counts are read from the page's own Index chips.
"""
from __future__ import annotations

import json

# ── materials ───────────────────────────────────────────────────────────────
# name: (front a, front b, side, top) for light mode, then for dark mode
_MATS = {
    "stone": (("#f7f5ef", "#dcd8cb", "#c2bdae", "#fdfcf8"), ("#5d627c", "#3f4459", "#2c2f41", "#70769230")),
    "trim": (("#ffffff", "#ecebe5", "#d3d0c6", "#ffffff"), ("#8a8fa9", "#62677f", "#464a5f", "#9a9fba")),
    "brick": (("#de9279", "#bd5a43", "#9a4838", "#e8a891"), ("#a65a49", "#82402f", "#5e2d22", "#b96c5a")),
    "slate": (("#8b95a9", "#5e6980", "#485166", "#a4adbf"), ("#454c62", "#2b3042", "#1f2331", "#555d78")),
    "glass": (("#dbf1fb", "#8cc2e4", "#6aa3c8", "#eaf8fe"), ("#4b80a7", "#2c5779", "#224867", "#5b94bc")),
    "bronze": (("#e0bb74", "#a97e38", "#876229", "#ecd093"), ("#d9b36a", "#a37a35", "#7f5d27", "#e6c98a")),
    "sand": (("#f2e1b8", "#d8bd86", "#bf9f66", "#f9edcf"), ("#8a7a58", "#665a3f", "#4a412d", "#9b8b69")),
    "marble": (("#f8f7f4", "#dedcd6", "#c4c2bc", "#fdfcfa"), ("#6a7090", "#4a5070", "#363b55", "#7c82a2")),
    "granite": (("#cdd0d8", "#9ea3b0", "#838998", "#dadde4"), ("#4c5068", "#383c52", "#2a2d40", "#5b607a")),
    "teal": (("#7fc1b8", "#3f8f88", "#2f726c", "#9dd3cb"), ("#3e7d78", "#2a5c58", "#1f4744", "#4e8f89")),
    "green": (("#cfe3dc", "#8fb8ac", "#74a094", "#e0f0ea"), ("#4f7d70", "#33574d", "#26433b", "#5f8f81")),
    # the skyscrapers' own skins (palace_towers.py): sapphire glass, silver metal, red granite, aqua and steel-blue glass
    "sapphire": (("#d6e6f7", "#86a9dc", "#6489bf", "#e6f0fb"), ("#4a6d9f", "#2f4d7a", "#243c61", "#5c82b6")),
    "silver": (("#f1f4f6", "#c3ccd4", "#a4afba", "#fafcfd"), ("#7a8696", "#576273", "#434c5b", "#8b98a9")),
    "garnet": (("#cf9684", "#96503f", "#783d30", "#dca796"), ("#8f5a4c", "#6c3d32", "#512b23", "#a06b5c")),
    "aqua": (("#d4f6f1", "#72cdc6", "#4fb0ac", "#e6faf7"), ("#3f8f8d", "#2a6d6c", "#1f5252", "#52a3a1")),
    "steel": (("#dbe8f0", "#8eb0c8", "#7095af", "#e8f1f7"), ("#4d7391", "#315069", "#263f55", "#5f87a8")),
}
_MATS["stone"] = (_MATS["stone"][0], ("#5d627c", "#3f4459", "#2c2f41", "#70768f"))


def landmark_css() -> str:
    """The landmark rules: materials, the card, the tag, the glow, the focus ring."""
    lines = []
    for mode in (0, 1):
        v = []
        for m, cols in _MATS.items():
            a, b, s, t = cols[mode]
            v.append(f"--lz-{m}-a:{a};--lz-{m}-b:{b};--lz-{m}-s:{s};--lz-{m}-t:{t};")
        v.append("--lz-win:rgba(34,40,66,.34);--lz-mu:rgba(255,255,255,.72);--lz-sl:#f1efe8;--lz-hi:rgba(255,255,255,.55);--lz-gs:rgba(20,26,55,.20);"
                 if mode == 0 else
                 "--lz-win:rgba(8,10,20,.52);--lz-mu:rgba(255,255,255,.30);--lz-sl:#8d92ac;--lz-hi:rgba(255,255,255,.20);--lz-gs:rgba(0,0,0,.40);")
        sel = ".pal-svg" if mode == 0 else "html.dark .pal-svg"
        lines.append(f"  {sel}{{{''.join(v)}}}")
    mats = []
    for m in _MATS:
        mats.append(f"  .lz-s-{m}{{fill:var(--lz-{m}-s);}} .lz-t-{m}{{fill:var(--lz-{m}-t);}}")
    return "\n".join(lines) + "\n" + "\n".join(mats) + r"""
  .lz-f,.lz-sd,.lz-tp{stroke:var(--lz-line,#667);stroke-width:1;stroke-opacity:.62;stroke-linejoin:round;vector-effect:non-scaling-stroke;}
  .lz-ln{fill:none;stroke:var(--lz-line,#667);stroke-width:1;stroke-opacity:.55;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  .lz-win{fill:var(--lz-win);stroke:none;}
  .lz-mu{fill:none;stroke:var(--lz-mu);stroke-width:.8px;vector-effect:non-scaling-stroke;}
  .lz-sl{fill:var(--lz-sl);stroke:none;}
  .lz-hi{fill:none;stroke:var(--lz-hi);stroke-width:1.2;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  .lz-gs{fill:var(--lz-gs);stroke:none;}
  .lz-col{stroke:none;}
  /* (the art is instanced with <use>, whose clones cannot match an ancestor selector: these rules stand alone, and the lit door is a variable set on the building's group) */
  .lz-door{fill:var(--lz-door,var(--lz-win));stroke:none;}
  /* the card the building stands on: glass with a thickness, a soft shadow, and the district's edge */
  .pal-svg .pl-lmb .lm-shadow{fill:rgba(20,26,55,.14);}
  .pal-svg .pl-lmb .lm-slab{stroke:none;fill-opacity:.38;}
  .pal-svg .pl-lmb .lm-card{fill:rgba(255,255,255,.90);}
  html.dark .pal-svg .pl-lmb .lm-card{fill:rgba(30,33,46,.92);}
  .pal-svg .pl-lmb .lm-sheen{fill:none;stroke:rgba(255,255,255,.85);stroke-width:1;vector-effect:non-scaling-stroke;}
  html.dark .pal-svg .pl-lmb .lm-sheen{stroke:rgba(255,255,255,.18);}
  .pal-svg .pl-lmb .lm-art{transition:transform .25s ease;}
  .pal-svg .pl-lmb.has-page:hover .lm-art,.pal-svg .pl-lmb.has-page:focus-visible .lm-art{transform:translateY(-3px);}
  .pal-svg .pl-lmb .lm-strip{fill:var(--lm-edge,#667);fill-opacity:.10;stroke:none;}
  .pal-svg .pl-lmb .lm-name{font-size:min(max(calc(11.5px / var(--pz,1)), var(--lm-nat,12px)), calc(21px / var(--pz,1)));font-weight:780;letter-spacing:.01em;stroke:var(--pal-halo);stroke-width:calc(3px / var(--pz,1));paint-order:stroke;stroke-linejoin:round;}
  .pal-svg .pl-lmb .lm-name.in{stroke:none;}
  .pal-svg .pl-lmb .lm-sub{font-size:calc(10px / var(--pz,1));font-weight:600;letter-spacing:.02em;stroke:none;fill:var(--lm-col,var(--pal-text));}
  .pal-svg.mid .pl-lmb .lm-sub{display:none;}
  /* "there is something inside": a glow in the page's colour, breathing slowly */
  .pal-svg .pl-lmb .lm-glow{fill:none;stroke:var(--lm-col);stroke-width:10px;stroke-opacity:.30;vector-effect:non-scaling-stroke;pointer-events:none;animation:lm-breathe 4.2s ease-in-out infinite;}
  .pal-svg .pl-lmb .lm-glow2{fill:none;stroke:var(--lm-col);stroke-width:2.5px;stroke-opacity:.85;vector-effect:non-scaling-stroke;pointer-events:none;}
  .pal-svg .pl-lmb.has-page:hover .lm-glow,.pal-svg .pl-lmb.has-page:focus-visible .lm-glow{animation:none;stroke-width:14px;stroke-opacity:.45;}
  .pal-svg .pl-lmb.has-page:hover .lm-card,.pal-svg .pl-lmb.has-page:focus-visible .lm-card{stroke-width:3.5;}
  @keyframes lm-breathe{0%,100%{stroke-opacity:.16;}50%{stroke-opacity:.42;}}
  @media (prefers-reduced-motion:reduce){ .pal-svg .pl-lmb .lm-glow{animation:none;} .pal-svg .pl-lmb .lm-art{transition:none;} }
  /* the tag: a glass door on the building's corner, the same size on screen at every zoom */
  .pal-svg .pl-lmb .lm-tagz{transform:scale(calc(1 / var(--pz,1)));}
  .pal-svg .lm-tag-sh{fill:rgba(20,26,55,.20);stroke:none;}
  .pal-svg .lm-tag-bg{fill:var(--lm-col);stroke:var(--lm-glass,rgba(255,255,255,.95));stroke-width:1.6;transition:fill .15s;}
  html.dark .pal-svg .lm-tag-bg{--lm-glass:rgba(24,26,38,.9);}
  .pal-svg .lm-tag-ic{fill:none;stroke:#fff;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;}
  .pal-svg .lm-tag text{font-size:11px;font-weight:800;letter-spacing:.01em;fill:#fff;stroke:none;}
  .pal-svg .lm-tag .t-open{display:none;}
  .pal-svg .pl-lmb.has-page:hover .lm-tag-bg,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag-bg{fill:#fff;stroke:var(--lm-col);}
  .pal-svg .pl-lmb.has-page:hover .lm-tag-ic,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag-ic{stroke:var(--lm-col);}
  .pal-svg .pl-lmb.has-page:hover .lm-tag text,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag text{fill:var(--lm-col);}
  .pal-svg .pl-lmb.has-page:hover .lm-tag .t-n,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag .t-n{display:none;}
  .pal-svg .pl-lmb.has-page:hover .lm-tag .t-open,.pal-svg .pl-lmb.has-page:focus-visible .lm-tag .t-open{display:inline;}
  .pal-svg.far .lm-tag .t-u{display:none;}
  .pal-svg .pl-lmb:focus{outline:none;}
  .pal-svg .pl-lmb:focus-visible .lm-card{stroke-width:4;}
  .pal-svg .pl-lmb:focus-visible .lm-focus{display:inline;}
  .pal-svg .pl-lmb .lm-focus{display:none;fill:none;stroke:var(--lm-col,var(--accent,#6d5bd0));stroke-width:2.5px;stroke-dasharray:6 4;vector-effect:non-scaling-stroke;}
  .pal-svg .pl-lmb.is-tower{cursor:pointer;}
  .pal-svg .pl-lmb.is-tower:hover .lm-card{stroke-width:4;}
  /* the key's row for them */
"""


# ── the art ─────────────────────────────────────────────────────────────────
def _f(n: float) -> str:
    s = f"{n:.1f}"
    return s[:-2] if s.endswith(".0") else s


def _r(x0: float, n: int, d: float) -> list:
    return [x0 + i * d for i in range(n)]


class _Art:
    """One building: SVG parts drawn back to front. Every solid is a front face (a gradient lit from
    the top left) with, when it stands out, a side face to its right and a top face above it,
    stepped back up and to the right. Walls carry a coursing pattern (brick in Flemish bond,
    ashlar), windows carry lintels, sills and muntins."""

    def __init__(self, w: int, h: int):
        self.w, self.h, self.parts = w, h, []

    def add(self, s: str):
        self.parts.append(s)

    def front(self, x, y, w, h, m, extra=""):
        self.add(f'<rect class="lz-f" x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" fill="url(#lzg-{m}-{{s}})"{extra}/>')

    def course(self, x, y, w, h, kind="brick", op=.55):
        """The wall's coursing over a face: Flemish-bond brick or ashlar blocks."""
        self.add(f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" fill="url(#lzp-{kind}-{{s}})" opacity="{op}"/>')

    def solid(self, x, y, w, h, m, d=7.0, side=True, top=True, course=None):
        """A box: its top, its right side, then its front (with its coursing)."""
        dx, dy = d, -d * 0.5
        if top:
            self.add(f'<path class="lz-tp lz-t-{m}" d="M{_f(x)} {_f(y)}l{_f(dx)} {_f(dy)}h{_f(w)}l{_f(-dx)} {_f(-dy)}z"/>')
        if side:
            self.add(f'<path class="lz-sd lz-s-{m}" d="M{_f(x + w)} {_f(y)}l{_f(dx)} {_f(dy)}v{_f(h)}l{_f(-dx)} {_f(-dy)}z"/>')
        self.front(x, y, w, h, m)
        if course:
            self.course(x, y, w, h, course)

    def poly(self, pts, m):
        p = "M" + "L".join(f"{_f(a)} {_f(b)}" for a, b in pts) + "z"
        self.add(f'<path class="lz-f" d="{p}" fill="url(#lzg-{m}-{{s}})"/>')

    def face(self, pts, m, kind="s"):
        """A plain side ('s') or top ('t') face."""
        p = "M" + "L".join(f"{_f(a)} {_f(b)}" for a, b in pts) + "z"
        self.add(f'<path class="lz-{"sd" if kind == "s" else "tp"} lz-{kind}-{m}" d="{p}"/>')

    def hip(self, x0, x1, yb, yt, inset, m="slate", ov=2.5, d=7.0):
        """A hipped roof seen from the front: the slope, its top, and the side slope."""
        dx, dy = d, -d * 0.5
        self.face([(x1 + ov, yb), (x1 + ov + dx, yb + dy), (x1 - inset + dx, yt + dy), (x1 - inset, yt)], m, "s")
        self.face([(x0 + inset, yt), (x0 + inset + dx, yt + dy), (x1 - inset + dx, yt + dy), (x1 - inset, yt)], m, "t")
        self.poly([(x0 - ov, yb), (x0 + inset, yt), (x1 - inset, yt), (x1 + ov, yb)], m)
        # slates: a few fine courses
        n = max(2, int((yb - yt) / 3.2))
        d_ = "".join(f"M{_f(x0 - ov + (inset + ov) * k / (n + 1) * 1.0 + 0.6)} {_f(yb - (yb - yt) * k / (n + 1))}H{_f(x1 + ov - (inset + ov) * k / (n + 1) - 0.6)}" for k in range(1, n + 1))
        self.add(f'<path class="lz-ln" d="{d_}" opacity=".45"/>')

    def wins(self, xs, ys, w, h, arch=False, mu=True, lintel=True):
        """Windows at every (x, y): lintel and sill in white trim, the dark pane, its muntins."""
        pane = mu_ = trim = ""
        for y in ys:
            for x in xs:
                if arch:
                    r = w / 2
                    pane += f"M{_f(x)} {_f(y + h)}V{_f(y + r)}a{_f(r)} {_f(r)} 0 0 1 {_f(w)} 0V{_f(y + h)}z"
                    if mu:
                        mu_ += f"M{_f(x + r)} {_f(y)}V{_f(y + h)}M{_f(x)} {_f(y + h * .58)}h{_f(w)}"
                    trim += f"M{_f(x - .8)} {_f(y + h)}h{_f(w + 1.6)}v1.2h{_f(-w - 1.6)}z"
                else:
                    pane += f"M{_f(x)} {_f(y)}h{_f(w)}v{_f(h)}h{_f(-w)}z"
                    if mu:
                        mu_ += f"M{_f(x + w / 2)} {_f(y)}v{_f(h)}M{_f(x)} {_f(y + h / 3)}h{_f(w)}M{_f(x)} {_f(y + 2 * h / 3)}h{_f(w)}"
                    if lintel:
                        trim += (f"M{_f(x - 1)} {_f(y - 1.7)}h{_f(w + 2)}v1.4h{_f(-w - 2)}z"
                                 f"M{_f(x - 1)} {_f(y + h)}h{_f(w + 2)}v1.2h{_f(-w - 2)}z")
        if trim:
            self.add(f'<path class="lz-sl" d="{trim}"/>')
        self.add(f'<path class="lz-win" d="{pane}"/>')
        if mu_:
            self.add(f'<path class="lz-mu" d="{mu_}"/>')

    def cols(self, x0, y, n, gap, w, h, cap=True):
        """A colonnade: each column a round fluted shaft with its capital and base."""
        fl = ""
        for i in range(n):
            x = x0 + i * gap
            self.add(f'<rect class="lz-col" x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" fill="url(#lzc-{{s}})"/>')
            if cap:
                self.add(f'<rect class="lz-col" x="{_f(x - .7)}" y="{_f(y)}" width="{_f(w + 1.4)}" height="{_f(max(1.4, h * .05))}" fill="url(#lzg-trim-{{s}})"/>'
                         f'<rect class="lz-col" x="{_f(x - .6)}" y="{_f(y + h - 1.3)}" width="{_f(w + 1.2)}" height="1.3" fill="url(#lzg-trim-{{s}})"/>')
            fl += f"M{_f(x + w * .35)} {_f(y + 1.5)}v{_f(h - 3)}M{_f(x + w * .68)} {_f(y + 1.5)}v{_f(h - 3)}"
        self.add(f'<path class="lz-ln" d="{fl}" opacity=".35"/>')

    def pilasters(self, xs, y, w, h):
        for x in xs:
            self.add(f'<rect class="lz-col" x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" fill="url(#lzg-trim-{{s}})" opacity=".8"/>')

    def pediment(self, x0, x1, yb, yt, m="trim", tym=None, d=7.0):
        """A temple pediment: the raking cornice, the tympanum and the roof slope behind."""
        dx, dy = d, -d * 0.5
        xm = (x0 + x1) / 2
        self.face([(x1, yb), (x1 + dx, yb + dy), (xm + dx, yt + dy), (xm, yt)], m, "s")
        self.poly([(x0, yb), (xm, yt), (x1, yb)], m)
        if tym:
            ins = (x1 - x0) * .07
            self.add(f'<path class="lz-sd lz-s-{tym}" d="M{_f(x0 + ins * 1.6)} {_f(yb - 1.6)}L{_f(xm)} {_f(yt + (yb - yt) * .26)}L{_f(x1 - ins * 1.6)} {_f(yb - 1.6)}z" opacity=".55" stroke="none"/>')
        self.line(f"M{_f(x0 + 1.4)} {_f(yb - .8)}L{_f(xm)} {_f(yt + 1.2)}L{_f(x1 - 1.4)} {_f(yb - .8)}")

    def arches(self, xs, y, w, h, m="win"):
        """Arched openings (an arcade): dark openings with a white archivolt."""
        d = a_ = ""
        r = w / 2
        for x in xs:
            d += f"M{_f(x)} {_f(y + h)}V{_f(y + r)}a{_f(r)} {_f(r)} 0 0 1 {_f(w)} 0V{_f(y + h)}z"
            a_ += f"M{_f(x - 1)} {_f(y + h)}V{_f(y + r)}a{_f(r + 1)} {_f(r + 1)} 0 0 1 {_f(w + 2)} 0V{_f(y + h)}"
        self.add(f'<path class="lz-win" d="{d}"/><path class="lz-mu" d="{a_}" style="stroke-width:1.3px"/>')

    def clock(self, cx, cy, r, m="trim"):
        self.add(f'<circle class="lz-f" cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="url(#lzg-trim-{{s}})"/>'
                 f'<circle class="lz-ln" cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r * .78)}"/>'
                 f'<path class="lz-ln" d="M{_f(cx)} {_f(cy)}v{_f(-r * .6)}M{_f(cx)} {_f(cy)}l{_f(r * .42)} {_f(r * .24)}M{_f(cx)} {_f(cy - r * .78)}v1.3M{_f(cx + r * .78)} {_f(cy)}h-1.3M{_f(cx)} {_f(cy + r * .78)}v-1.3M{_f(cx - r * .78)} {_f(cy)}h1.3"/>')

    def line(self, d):
        self.add(f'<path class="lz-ln" d="{d}"/>')

    def shadow(self, x0, x1, y, d=9.0):
        self.add(f'<path class="lz-gs" d="M{_f(x0)} {_f(y)}L{_f(x0 + d)} {_f(y - d * .5)}H{_f(x1 + d)}L{_f(x1)} {_f(y)}z"/>')

    def steps(self, xc, y, w0, n, rise=1.9, grow=3.2, m="stone"):
        """A flight of steps in front of the doorway, each tread a little wider than the one above."""
        for i in range(n):
            self.front(xc - (w0 + i * grow) / 2, y + i * rise, w0 + i * grow, rise, m)

    def out(self) -> dict:
        return {"w": self.w, "h": self.h, "svg": "".join(self.parts)}


def _independence() -> dict:
    """Independence Hall from Chestnut Street: the 105-ft Georgian main block of Flemish-bond red
    brick, two storeys under a hipped roof with its chimneys, the white wooden steeple (clock stage,
    belfry, lantern, spire) over the tower, the covered arcades and the two 50-ft end buildings."""
    a = _Art(240, 126)
    base = 118
    a.shadow(4, 236, base, 9)
    # the end buildings (Congress Hall, Old City Hall): five bays, two storeys, hipped roofs
    for x in (6, 188):
        a.solid(x, 88, 46, base - 88, "brick", d=6, course="brick")
        a.hip(x, x + 46, 88, 77, 8, d=6)
        for cx in (x + 10, x + 31):
            a.solid(cx, 68, 5, 11, "brick", d=2.5)
            a.front(cx - .6, 67, 6.2, 1.6, "trim")
        a.front(x - 1, 86.5, 48, 2.2, "trim")
        a.wins(_r(x + 4.2, 5, 8.6), (91,), 4.6, 9)
        a.wins([v for i, v in enumerate(_r(x + 4.2, 5, 8.6)) if i != 2], (104,), 4.6, 10)
        a.arches([x + 19.8], 104, 6.4, 14)
    # the covered arcades that join them to the main block
    for x in (50, 172):
        a.solid(x, 99, 22, base - 99, "brick", d=4, course="brick")
        a.hip(x, x + 22, 99, 93, 3, ov=1.5, d=4)
        a.arches([x + 4.5, x + 12.5], 104, 5, 14)
    # the main block: nine bays wide, a belt course, a cornice, the hipped roof and its chimneys
    a.solid(70, 80, 100, base - 80, "brick", d=8, course="brick")
    a.hip(70, 170, 80, 64, 17, d=8, ov=3)
    for cx in (86, 95, 145, 154):
        a.solid(cx, 51, 5.5, 14, "brick", d=2.5)
        a.front(cx - .6, 50, 6.7, 1.6, "trim")
    a.front(67.5, 78, 105, 2.6, "trim")
    a.front(70, 98, 100, 1.8, "trim")
    a.wins(_r(73, 3, 11.1) + _r(139.5, 3, 11.1), (84,), 5.4, 12.5)
    a.wins(_r(73, 3, 11.1) + _r(139.5, 3, 11.1), (103,), 5.4, 12)
    # the tower: brick to the roofline, its Palladian window and doorway, then the white steeple
    a.solid(108, 40, 24, base - 40, "brick", d=5, course="brick")
    a.front(106.5, 38.6, 27, 2.4, "trim")
    a.wins([117.5], (84,), 5, 13, arch=True)
    a.wins([111, 125.2], (87,), 3.8, 10.5, mu=True)
    a.wins([117.8], (58,), 4.4, 10, arch=True)
    a.add('<path class="lz-door" d="M115.2 118v-8.6a4.8 4.8 0 0 1 9.6 0V118z"/><path class="lz-mu" d="M114.2 118v-8.6a5.8 5.8 0 0 1 11.6 0V118" style="stroke-width:1.5px"/>')
    a.steps(120, base, 14, 2)
    a.solid(110, 25, 20, 14, "trim", d=4)                  # the clock stage
    a.clock(120, 32, 5)
    for ux in (109.5, 128.5):
        a.add(f'<path class="lz-f" d="M{ux} 25.5h2.4l-1.2-4z" fill="url(#lzg-bronze-{{s}})"/>')
    a.front(109, 23.6, 22, 1.8, "trim")
    a.solid(112.5, 13, 15, 11, "trim", d=3.5)              # the belfry, its arched louvres
    a.wins([114.8, 118.8, 122.8], (15,), 2.8, 7, arch=True, mu=False)
    a.front(111.5, 11.6, 17, 1.6, "trim")
    a.add('<path class="lz-f" d="M115 11.6a5 6 0 0 1 10 0z" fill="url(#lzg-trim-{s})"/>')        # the lantern
    a.poly([(118.6, 6), (120, -4), (121.4, 6)], "trim")                                            # the spire
    a.add('<circle class="lz-f" cx="120" cy="-3" r="1.3" fill="url(#lzg-bronze-{s})"/>')
    a.line("M120 -4.5v-4M117.4 -7h5.2")
    a.add('<rect class="lz-f" x="2" y="118" width="236" height="3.4" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _cityhall() -> dict:
    """City Hall, Broad Street front: the French Second Empire block in white marble over a granite
    base, three classical storeys under slate mansards with dormers and iron cresting, the four
    pavilions (the centre one with paired columns and its open archway), and the tower — a columned
    stage, the clock stage with its eagles, an open colonnade, and William Penn in bronze on top."""
    a = _Art(240, 182)
    base = 172
    a.shadow(4, 236, base, 10)
    # the great block: granite ground floor, marble above, the mansard over it
    a.solid(6, 100, 228, base - 100, "marble", d=9, course="ashlar")
    a.front(6, 152, 228, base - 152, "granite")
    a.course(6, 152, 228, base - 152, "ashlar", .7)
    a.front(4, 150.4, 232, 2.2, "trim")
    a.front(4, 98, 232, 2.8, "trim")
    a.hip(6, 234, 100, 84, 20, d=9, ov=2)
    a.line("M30 84H210")
    # the corner pavilions: taller, with their own mansards and the turrets
    for x in (6, 194):
        a.solid(x, 86, 40, base - 86, "marble", d=9, course="ashlar")
        a.front(x, 152, 40, base - 152, "granite")
        a.course(x, 152, 40, base - 152, "ashlar", .7)
        a.front(x - 1.5, 84, 43, 2.6, "trim")
        a.hip(x, x + 40, 86, 68, 9, d=9, ov=2)
        a.add(f'<path class="lz-f" d="M{x + 14} 68a6 8 0 0 1 12 0z" fill="url(#lzg-slate-{{s}})"/>')
        a.line(f"M{x + 20} 60V54")
        a.pilasters([x + 2, x + 33], 90, 4.6, 60)
        a.wins([x + 8, x + 17.4, x + 26.8], (92, 116), 5.2, 14)
        a.wins([x + 8, x + 17.4, x + 26.8], (156,), 5.2, 10, lintel=False)
        a.add(f'<path class="lz-win" d="M{x + 8} 76h5v4h-5zM{x + 17.4} 76h5v4h-5zM{x + 26.8} 76h5v4h-5z"/>')
    # the wings between: two storeys of windows, a rusticated ground floor, dormers in the mansard
    a.wins([x for x in _r(54, 4, 9.8) + _r(147, 4, 9.8)], (106,), 5, 13)
    a.wins([x for x in _r(54, 4, 9.8) + _r(147, 4, 9.8)], (126,), 5, 13)
    a.wins([x for x in _r(54, 4, 9.8) + _r(147, 4, 9.8)], (156,), 5, 10, lintel=False)
    for dx_ in _r(56, 3, 13) + _r(149, 3, 13):
        a.add(f'<path class="lz-f" d="M{_f(dx_)} 98V89h6v9z" fill="url(#lzg-slate-{{s}})"/><path class="lz-win" d="M{_f(dx_ + 1)} 98V91.5h4V98z"/>'
              f'<path class="lz-f" d="M{_f(dx_ - 1)} 89L{_f(dx_ + 3)} 85l4 4z" fill="url(#lzg-trim-{{s}})"/>')
    # the centre pavilion: paired columns, the great archway, its pediment and mansard
    a.solid(88, 94, 64, base - 94, "marble", d=8, course="ashlar")
    a.front(88, 152, 64, base - 152, "granite")
    a.course(88, 152, 64, base - 152, "ashlar", .7)
    a.front(86, 92, 68, 2.8, "trim")
    a.hip(88, 152, 94, 76, 12, d=8, ov=2)
    a.cols(92, 100, 8, 8, 3.6, 50)
    a.add('<path class="lz-win" d="M105 172v-22a15 15 0 0 1 30 0v22z"/><path class="lz-mu" d="M103.4 172v-22a16.6 16.6 0 0 1 33.2 0v22" style="stroke-width:1.6px"/>')
    a.add('<path class="lz-door" d="M114 172v-11a6 6 0 0 1 12 0v11z"/>')
    a.steps(120, base, 40, 3, 1.7, 3.4)
    a.wins([107, 114, 121, 128], (106,), 4.4, 12)
    # the tower, stage by stage
    a.solid(97, 62, 46, 16, "marble", d=7, course="ashlar")             # the columned base
    a.front(95.5, 60.4, 49, 2.6, "trim")
    a.cols(100, 64.5, 6, 7.6, 3, 12.5, cap=True)
    a.solid(102, 40, 36, 20, "marble", d=6, course="ashlar")            # the clock stage
    a.clock(120, 50, 8.4)
    for ex in (103.4, 134.6):
        a.add(f'<path class="lz-f" d="M{_f(ex - 1.8)} 41.6l1.8-4.6 1.8 4.6z M{_f(ex - 3)} 40.4h6" fill="url(#lzg-bronze-{{s}})"/>')
    a.front(100.5, 38.6, 39, 2.2, "trim")
    a.solid(107, 24, 26, 14, "marble", d=5)                             # the open colonnade
    a.add('<path class="lz-win" d="M109 36V28h22v8z"/>')
    a.cols(108.4, 25, 6, 4.7, 2.2, 12, cap=False)
    a.front(105.6, 22.6, 28.8, 2, "trim")
    a.add('<path class="lz-f" d="M108 22.6C108 11 112 8 120 8s12 3 12 14.6z" fill="url(#lzg-slate-{s})"/>')   # the dome
    a.line("M114 22V11M126 22V11")
    a.front(116, 4, 8, 4.6, "trim")                                     # the pedestal
    a.add('<path class="lz-f" d="M118.2 4V-5h3.6V4z" fill="url(#lzg-bronze-{s})"/><circle class="lz-f" cx="120" cy="-7" r="2.1" fill="url(#lzg-bronze-{s})"/>'
          '<path class="lz-f" d="M121.6 -3.4l5.4-3.2 0 1.6-4.6 3.2z" fill="url(#lzg-bronze-{s})"/>')                # William Penn
    a.add('<rect class="lz-f" x="2" y="172" width="236" height="3.4" fill="url(#lzg-granite-{s})"/>')
    return a.out()


def _art() -> dict:
    """The Museum of Art, east front: the temple front with its eight columns and pediment on a long
    flight of steps, the blue-green tiled gable roofs behind, and the two long wings of tan Kasota
    limestone, each ending in a pedimented four-column pavilion."""
    a = _Art(330, 126)
    base = 114
    a.shadow(8, 322, base, 10)
    # the wings, long and two-storeyed, under their blue-green tile roofs
    for x in (22, 212):
        a.solid(x, 58, 96, base - 58, "sand", d=7, course="ashlar")
        a.hip(x, x + 96, 58, 48, 12, "teal", ov=1.5, d=7)
        a.front(x - 1, 56.6, 98, 2.6, "trim")
        a.pilasters(_r(x + 20, 6, 12.4), 61, 3.2, 45)
        a.wins(_r(x + 24, 5, 12.4), (66,), 6.4, 16)
        a.wins(_r(x + 24, 5, 12.4), (88,), 6.4, 14, lintel=False)
        a.front(x - 1, 104.6, 98, 1.8, "trim")
    # the end pavilions: a projecting pedimented front with four columns
    for x in (14, 262):
        a.solid(x, 56, 54, base - 56, "sand", d=7, course="ashlar")
        a.front(x - 1, 54, 56, 2.8, "trim")
        a.pediment(x - 2, x + 56, 54, 40, "trim", "teal")
        a.add(f'<rect class="lz-f" x="{x + 4}" y="58" width="46" height="48" fill="url(#lzg-sand-{{s}})"/>')
        a.cols(x + 5.5, 58, 4, 14.4, 5, 47)
        a.front(x - 1, 104.4, 56, 1.8, "trim")
    # the central temple: eight columns on the stylobate, the entablature, the pediment, the roof behind
    a.hip(116, 214, 38, 26, 22, "teal", ov=2, d=7)
    a.solid(112, 40, 106, base - 40, "sand", d=8, side=True, top=False)
    a.add('<rect class="lz-f" x="116" y="49" width="98" height="56" fill="url(#lzg-sand-{s})"/>')
    a.add('<path class="lz-win" d="M155 105V82a10 10 0 0 1 20 0v23z"/>')
    a.add('<path class="lz-door" d="M158 105V84a7 7 0 0 1 14 0v21z"/>')
    a.cols(118.4, 49, 8, 12.5, 5.6, 55)
    a.front(110, 40.4, 110, 8.6, "trim")                                  # the entablature
    a.line("M114 44.8H216")
    a.pediment(108, 222, 40.4, 20, "trim", "sand", d=9)
    a.add('<path class="lz-f" d="M163 19h4l-2 -4.4z" fill="url(#lzg-bronze-{s})"/>')
    # the stylobate and the long stairs
    a.front(106, 104.4, 118, 2.2, "trim")
    for i in range(9):
        w = 118 + i * 6.8
        a.front(165 - w / 2, 106.6 + i * 0.9, w, 1.0, "stone" if i % 2 else "trim", extra=' stroke-opacity=".3"')
    return a.out()


def _franklin() -> dict:
    """The Franklin Institute: a limestone Neoclassical block with a six-column portico and pediment
    over its steps, the low rotunda dome behind, and two wings of tall paned windows between pilasters."""
    a = _Art(260, 134)
    base = 124
    a.shadow(6, 254, base, 9)
    for x in (10, 182):
        a.solid(x, 72, 68, base - 72, "stone", d=7, course="ashlar")
        a.front(x - 1, 70, 70, 3, "trim")
        a.front(x - 1, 66, 70, 4, "stone")
        a.line(f"M{x} 67.2h68")
        a.pilasters(_r(x + 4, 5, 15.2), 75, 3.6, 45)
        a.wins(_r(x + 9, 4, 15.2), (80,), 6.2, 30)
        a.front(x - 1, 117, 70, 2, "trim")
    # the rotunda behind: a drum and a low dome
    a.solid(94, 50, 72, 30, "stone", d=7, top=False, course="ashlar")
    a.add('<path class="lz-sd lz-s-green" d="M92 50c0-12 16-22 38-22s38 10 38 22z" transform="translate(7 -3.5)"/>')
    a.add('<path class="lz-f" d="M92 50c0-12 16-22 38-22s38 10 38 22z" fill="url(#lzg-green-{s})"/>')
    a.line("M130 28V50M112 31C108 36 107 43 107 50M148 31C152 36 153 43 153 50")
    a.add('<path class="lz-f" d="M127.5 28a2.5 3 0 0 1 5 0z" fill="url(#lzg-trim-{s})"/>')
    a.wins(_r(100, 6, 10.8), (56,), 5, 16, arch=True)
    a.front(92, 48.4, 76, 2.4, "trim")
    # the portico: six columns, the entablature, the pediment, the doors
    a.front(76, 76, 108, 5.4, "trim")
    a.line("M78 79h104")
    a.pediment(72, 188, 76, 56, "trim", "stone", d=7)
    a.add('<rect class="lz-f" x="80" y="81.4" width="100" height="38" fill="url(#lzg-stone-{s})"/>')
    a.add('<path class="lz-win" d="M120 120V104a10 10 0 0 1 20 0v16z"/>')
    a.add('<path class="lz-door" d="M122.4 120V105a7.6 7.6 0 0 1 15.2 0v15z"/>')
    a.cols(83, 81.4, 6, 17.2, 5.4, 38)
    a.front(76, 119.4, 108, 2.2, "trim")
    a.steps(130, 121.6, 108, 3, 1.1, 3.2)
    return a.out()


def _convention() -> dict:
    """The Convention Center: the Reading Terminal headhouse in red brick with its tall arched windows
    and corner pavilions, the great arched train-shed vault of glass and steel behind it, and the
    glass halls of the expansion either side, ribbed with mullions."""
    a = _Art(330, 118)
    base = 108
    a.shadow(6, 324, base, 10)
    # the glass halls either side
    for x in (10, 246):
        a.solid(x, 62, 74, base - 62, "glass", d=7)
        a.add(f'<path class="lz-mu" d="' + "".join(f"M{_f(x + 7.4 * i)} 62v{base - 62}" for i in range(1, 10)) + f'M{x} 78h74M{x} 94h74"/>')
        a.add(f'<path class="lz-hi" d="M{x + 6} {base - 8}l20 -28M{x + 28} {base - 8}l20 -28"/>')
        a.front(x - 1, 60, 76, 2.4, "slate")
    # the train-shed vault: a glass barrel on steel ribs
    a.add('<path class="lz-sd lz-s-glass" d="M82 108V60c0-30 24-46 83-46s83 16 83 46v48z" transform="translate(7 -3.5)"/>')
    a.add('<path class="lz-f" d="M82 108V60c0-30 24-46 83-46s83 16 83 46v48z" fill="url(#lzg-glass-{s})"/>')
    a.add('<path class="lz-mu" d="M99 108V54C99 38 106 26 118 20M115 108V50C115 32 124 22 136 17M132 108V48C132 30 140 20 152 15.5M165 108V14M198 108V48C198 30 190 20 178 15.5M215 108V50C215 32 206 22 194 17M231 108V54C231 38 224 26 212 20" style="stroke-width:1.1px"/>')
    a.add('<path class="lz-hi" d="M92 98l20 -46M118 98l16 -36"/>')
    # the headhouse: brick, a tall arched window group, corner pavilions with pyramid roofs
    a.solid(106, 58, 118, base - 58, "brick", d=7, course="brick")
    a.hip(106, 224, 58, 50, 14, "slate", ov=2, d=7)
    a.front(104, 56.6, 122, 2.4, "trim")
    a.front(106, 80, 118, 1.8, "trim")
    side = [112, 122, 132, 142, 183, 193, 203, 213]
    a.arches(side, 62, 6, 16)
    a.add('<path class="lz-win" d="M154 108V74a11 11 0 0 1 22 0v34z"/>')
    a.add('<path class="lz-mu" d="M152.4 108V74a12.6 12.6 0 0 1 25.2 0v34M165 62v46M154 82h22M154 92h22" style="stroke-width:1.1px"/>')
    a.add('<path class="lz-door" d="M159.8 108V96a5.2 5.2 0 0 1 10.4 0v12z"/>')
    a.wins(side, (88,), 6, 12)
    a.add('<rect class="lz-f" x="2" y="108" width="326" height="3.6" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _station() -> dict:
    """30th Street Station: the long neoclassical block of pale stone, its twelve giant columns, tall
    bronze-framed windows between them, a stepped parapet and the long flights at the ends."""
    a = _Art(300, 112)
    base = 100
    a.shadow(8, 292, base, 9)
    a.solid(12, 38, 276, base - 38, "stone", d=8, course="ashlar")
    a.front(8, 30, 284, 8.4, "trim")
    a.front(14, 24, 272, 6, "stone")
    a.front(120, 18, 60, 6, "stone")
    a.line("M10 34h280M16 27h268")
    a.add('<path class="lz-win" d="M26 42h248v54H26z" opacity=".9"/>')
    a.add('<path class="lz-mu" d="' + "".join(f"M{_f(28 + i * 20.6)} 42v54" for i in range(12)) + 'M26 56h248M26 70h248M26 84h248"/>')
    a.cols(26, 38, 12, 22.4, 6.6, 58)
    a.add('<path class="lz-door" d="M141 100V86a9 9 0 0 1 18 0v14z"/>')
    a.front(20, 96, 260, 2.6, "trim")
    a.front(14, 98.6, 272, 2.6, "stone")
    a.steps(150, 101.2, 276, 2, 1.1, 5)
    return a.out()


def _generic() -> dict:
    a = _Art(160, 100)
    base = 90
    a.shadow(14, 146, base, 9)
    a.solid(24, 38, 112, base - 38, "stone", d=8, course="ashlar")
    a.pediment(20, 140, 38, 14, "trim", None, d=8)
    a.front(22, 38, 116, 3.4, "trim")
    a.wins(_r(36, 5, 20), (50,), 8, 22)
    a.add('<path class="lz-door" d="M71 90v-14a9 9 0 0 1 18 0v14z"/>')
    a.steps(80, base, 28, 2)
    return a.out()


def _build_art() -> dict:
    return {"ind": _independence(), "city": _cityhall(), "art": _art(), "frank": _franklin(),
            "conv": _convention(), "stn": _station(), "gen": _generic(), **_towers.build_art()}


from . import palace_towers as _towers      # (the skyscrapers: palace_towers.py)
ART = _build_art()
# which landmark names get which art (the page's own label, case-insensitive)
MATCH = [["ind", r"independence hall"], ["city", r"city hall"], ["art", r"art museum|museum of art|philadelphia museum"],
         ["frank", r"franklin institute"], ["conv", r"convention cent(er|re)"], ["stn", r"(30th|thirtieth) street station"]] + _towers.MATCH


def landmark_gradients() -> str:
    """The <defs> every instance shares, with {s} the svg's own id suffix (the JS fills it in)."""
    g = []
    for m in _MATS:
        g.append(f'<linearGradient id="lzg-{m}-{{s}}" x1="0" y1="0" x2="1" y2="1">'
                 f'<stop offset="0" style="stop-color:var(--lz-{m}-a)"/><stop offset="1" style="stop-color:var(--lz-{m}-b)"/></linearGradient>')
    # columns: a round shaft, lit from the left
    g.append('<linearGradient id="lzc-{s}" x1="0" y1="0" x2="1" y2="0">'
             '<stop offset="0" style="stop-color:var(--lz-trim-a)"/><stop offset=".55" style="stop-color:var(--lz-trim-b)"/>'
             '<stop offset="1" style="stop-color:var(--lz-trim-s)"/></linearGradient>')
    # the wall coursing: Flemish-bond brick (headers dark, alternating with stretchers) and ashlar blocks
    g.append('<pattern id="lzp-brick-{s}" width="8.4" height="6" patternUnits="userSpaceOnUse">'
             '<path d="M0 3H8.4M0 6H8.4M6 0V3M3 3V6M5.4 3V6" stroke="#fff" stroke-opacity=".22" stroke-width=".35" fill="none"/>'
             '<rect x="6" y="0" width="2.4" height="3" fill="#3a0c00" opacity=".24"/><rect x="3" y="3" width="2.4" height="3" fill="#3a0c00" opacity=".24"/></pattern>')
    g.append('<pattern id="lzp-ashlar-{s}" width="16" height="5.6" patternUnits="userSpaceOnUse">'
             '<path d="M0 5.6H16M8 0V5.6M0 2.8" stroke="#000" stroke-opacity=".13" stroke-width=".4" fill="none"/></pattern>')
    return "".join(g)


LANDMARK_CSS = landmark_css()


# ── the page side ───────────────────────────────────────────────────────────
_JS = r"""
(function(){
var NS='http://www.w3.org/2000/svg', XL='http://www.w3.org/1999/xlink';
var ART=__ART__, GRAD='__GRAD__';
var TALL=__TALL__;
var MATCH=__MATCH__.map(function(m){ return [m[0], new RegExp(m[1],'i')]; });
function E(tag,attrs,parent){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; }
function artKey(n){ for(var i=0;i<MATCH.length;i++) if(MATCH[i][1].test(n)) return MATCH[i][0]; return 'gen'; }
/* the shared gradients, and the building's <symbol>, in this svg's own <defs> (once each) */
function ensure(defs, sid, key){
  if(!defs._lz){ defs._lz={}; var d=E('defs',{},defs); d.innerHTML=GRAD.replace(/\{s\}/g, sid); }
  if(!defs._lz[key]){ defs._lz[key]=1; var a=ART[key];
    var s=E('symbol',{id:'lz-'+key+'-'+sid, viewBox:'-6 -8 '+(a.w+12)+' '+(a.h+14), preserveAspectRatio:'xMidYMax meet', overflow:'visible'},defs);
    s.innerHTML=a.svg.replace(/\{s\}/g, sid); }
}
/* what is inside a landmark's page, read from the page's own Index chips (the counts those show) */
function pageInfo(pg, pn){
  var q=String(pg||'').split(':'), k=q.slice(1).join(':'), o={name:pn?pn(pg):k, count:0, unit:'', kind:'page', col:'var(--accent,#6d5bd0)'};
  if(q[0]==='index'){
    var chip=document.querySelector('[data-axis-index="'+k+'"]'), A=(window._ALTO_AXES||{})[k]||{}, c=chip&&chip.querySelector('.nav-chip-count');
    o.count=c?(parseInt(c.textContent,10)||0):(A.ids?A.ids.length:0);
    var env=chip?chip.classList.contains('env-btn'):/^env/.test(k), lab=String(A.label||o.name||'');
    o.col=env?'var(--env-color,#8a6000)':'var(--theme-color,#6d28d9)';
    o.kind=env?'cases':(/rule|procedure/i.test(lab)?'rules':'code');
    o.unit=env?(/case/i.test(lab)?'cases':(A.unit||'items')):(/rule|procedure/i.test(lab)?'rules':(A.unit||'sections'));
    if(o.count===1) o.unit=o.unit.replace(/s$/,'');
  }
  return o;
}
/* the page's icon (16 x 16): scales for cases, an open book for rules, a leaf with a section line for a code */
var ICON={cases:'M8 2.2v11.3M5 13.6h6M2.4 4.6h11.2M2.4 4.6 .9 9.2h3zM13.6 4.6l-1.5 4.6h3z', rules:'M8 4.2C6.4 3 4.4 2.8 2 3v9.2c2.4-.2 4.4 0 6 1.2 1.6-1.2 3.6-1.4 6-1.2V3c-2.4-.2-4.4 0-6 1.2zM8 4.2v9.2',
  code:'M4 1.8h5.6l3 3.2v9.2H4zM9.6 1.8V5h3M6.2 8.4h4.4M6.2 10.8h4.4', page:'M4 1.8h5.6l3 3.2v9.2H4zM9.6 1.8V5h3M6.2 8.4h4.4M6.2 10.8h4.4'};
function label(name, i){ return name+(i?' — inside: '+i.name+(i.count?', '+i.count+' '+i.unit:'')+'. Open':''); }

function draw(g, l, o){
  var b=l.box, ins=o.ins, x=b[0]+ins, y=b[1]+ins, w=b[2]-b[0]-2*ins, h=b[3]-b[1]-2*ins, c=o.color, nm=String(l.n);
  /* a skyscraper's card is tall and narrow, centred on its block (its building chip stands to the left of it) */
  var tall=TALL.indexOf(artKey(nm))>=0;
  if(tall){ var nw=Math.min(w, h*.55); x+=(w-nw)/2; w=nw; }
  var info=l.page?pageInfo(l.page, o.pageName):null;
  g.style.setProperty('--lm-edge', c); g.style.setProperty('--lz-line', c); g.style.setProperty('--lm-col', info?info.col:c); if(info) g.style.setProperty('--lz-door', info.col);
  /* the card: a glass slab with a thickness, lit from the top left, a soft shadow to the lower right */
  E('rect',{'class':'lm-shadow', x:x+7, y:y+10, width:w, height:h, rx:9},g);
  E('rect',{'class':'lm-slab', x:x+3, y:y+5, width:w, height:h, rx:9, fill:c},g);
  if(info){ E('rect',{'class':'lm-glow', x:x-3, y:y-3, width:w+6, height:h+6, rx:12},g); E('rect',{'class':'lm-glow2', x:x-1, y:y-1, width:w+2, height:h+2, rx:10},g); }
  E('rect',{'class':'lm-card', x:x, y:y, width:w, height:h, rx:9, stroke:c},g);
  E('path',{'class':'lm-sheen', d:'M'+(x+11)+' '+(y+2.5)+'H'+(x+w-11)},g);
  var strip=E('rect',{'class':'lm-strip', rx:5},g);
  /* the building */
  var key=artKey(nm); ensure(o.defs, o.sid, key);
  var art=E('g',{'class':'lm-art'},g), use=E('use',{href:'#lz-'+key+'-'+o.sid},art); use.setAttributeNS(XL,'xlink:href','#lz-'+key+'-'+o.sid);
  var name=E('text',{'class':'lm-name','text-anchor':'middle'},g), sub=info?E('text',{'class':'lm-sub','text-anchor':'middle'},g):null;
  /* the tag (a page's way in): a glass door on the corner, drawn in screen pixels */
  var tag=null, tbg=null, tn=null, tu=null, to=null;
  if(info){
    var tp=E('g',{'class':'lm-tagp'},g), tz=E('g',{'class':'lm-tagz'},tp); tag=E('g',{'class':'lm-tag'},tz);
    E('rect',{'class':'lm-tag-sh', rx:10, height:20, y:-7},tag); tbg=E('rect',{'class':'lm-tag-bg', rx:10, height:20, y:-10},tag);
    E('path',{'class':'lm-tag-ic', d:ICON[info.kind]||ICON.page, transform:'translate(6 -8) scale(1)'},tag);
    tn=E('text',{'class':'t-n', x:24, y:4},tag); var tc=E('tspan',{'class':'t-c'},tn); tc.textContent=info.count?String(info.count):'';
    tu=E('tspan',{'class':'t-u'},tn); tu.textContent=info.count?' '+info.unit:'Inside';
    if(!info.count) tc.textContent='';
    to=E('text',{'class':'t-open', x:24, y:4},tag); to.textContent='Open ›';
    tag._p=tp;
  }
  E('rect',{'class':'lm-focus', x:x-6, y:y-6, width:w+12, height:h+12, rx:14},g);
  g._lm={tall:tall,tower:o.tower||null,x:x,y:y,w:w,h:h,name:nm,info:info,page:l.page,strip:strip,art:art,use:use,nameT:name,sub:sub,tag:tag,tbg:tbg,tn:tn,to:to,pn:o.pageName};
  /* keyboard and screen readers */
  g.setAttribute('aria-label', label(nm, info));
  if(info){ g.setAttribute('role','link'); g.setAttribute('tabindex','0');
    g.addEventListener('keydown', function(e){ if(e.key==='Enter' || e.key===' '){ e.preventDefault(); e.stopPropagation(); o.open(l.page); } }); }
  else if(o.tower){ g.classList.add('is-tower'); g.setAttribute('role','img'); g.setAttribute('aria-label', nm+' — tower of '+o.tower.num+' '+o.tower.title+', '+o.tower.top+' floors'); }
  else g.setAttribute('role','img');
}
/* the layout that depends on the zoom: names and tags keep a size on the screen, so where they would not
   fit inside a small card the name hangs under it; the building takes what is left */
function relayout(svg, Z){
  Z=Z||1; var u=1/Z, far=Z<.42, near=Z>=.8;
  svg.querySelectorAll('.pl-lmb').forEach(function(g){ var L=g._lm; if(!L) return;
    if(L.page && L.info && !L.info.count){ L.info=pageInfo(L.page, L.pn); g.setAttribute('aria-label', label(L.name, L.info)); }
    var x=L.x, y=L.y, w=L.w, h=L.h, n=L.name.length, fit=Math.min(26, (L.tall?w*2.8:w)*.94/(Math.max(n,3)*.6));
    g.style.setProperty('--lm-nat', fit.toFixed(1)+'px');
    var fn=Math.min(Math.max(11.5*u, fit), 21*u), words=L.name.split(' '), lines=[L.name];
    if(n*.6*fn>w*.98 && words.length>1){ var half=Math.ceil(words.length/2); lines=[words.slice(0,half).join(' '), words.slice(half).join(' ')]; }
    var wide=Math.max.apply(null, lines.map(function(s){ return s.length; }))*.6*fn;
    var subH=(L.sub && near)?13*u:0, stripH=lines.length*fn*1.22+fn*.42+subH, hang=L.tall || (wide>w*1.02) || stripH>h*.46;
    var cx=x+w/2, top=y-h*.22, bottom;
    while(L.nameT.firstChild) L.nameT.removeChild(L.nameT.firstChild);
    if(hang){
      lines=[L.name]; L.nameT.setAttribute('class','lm-name'); L.nameT.setAttribute('x',cx);
      var ts=document.createElementNS(NS,'tspan'); ts.setAttribute('x',cx); ts.setAttribute('dy','0'); ts.textContent=L.name; L.nameT.appendChild(ts);
      L.nameT.setAttribute('y', y+h+fn*1.02+2*u); L.strip.setAttribute('width',0); L.strip.setAttribute('height',0); bottom=y+h-5;
      if(L.sub) L.sub.setAttribute('display','none');
    } else {
      L.nameT.setAttribute('class','lm-name in'); var y0=y+h-stripH+fn*.42*.5+fn*.88;
      lines.forEach(function(s,i){ var ts=document.createElementNS(NS,'tspan'); ts.setAttribute('x',cx); ts.setAttribute('y', y0+i*fn*1.22); ts.textContent=s; L.nameT.appendChild(ts); });
      L.strip.setAttribute('x',x+3); L.strip.setAttribute('y',y+h-stripH-1); L.strip.setAttribute('width',w-6); L.strip.setAttribute('height',stripH-2);
      bottom=y+h-stripH-3*u;
      if(L.sub){ if(near){ L.sub.removeAttribute('display'); L.sub.setAttribute('x',cx); L.sub.setAttribute('y', y+h-6*u-1);
        var t1='Inside: '+L.info.name, t2=L.info.count?L.info.count+' '+L.info.unit+' inside':'', fitC=w/(5.7*u);
        t1=t1.length<=fitC?t1:(t2.length<=fitC?t2:''); L.sub.textContent=t1; } else L.sub.setAttribute('display','none'); }
    }
    var ah=Math.max(8, bottom-top); L.use.setAttribute('x',x+6); L.use.setAttribute('y',top); L.use.setAttribute('width',w-12); L.use.setAttribute('height',ah);
    if(L.tag){ var full=L.info.count?(String(L.info.count).length+(far?0:L.info.unit.length+1)):6, tw=Math.max(full,6)*6.6+34;
      L.tbg.setAttribute('width',tw); L.tag.querySelector('.lm-tag-sh').setAttribute('width',tw);
      L.tag.querySelector('.lm-tag-sh').setAttribute('x',2); L.tag.querySelector('.lm-tag-sh').setAttribute('y',-5);
      L.tag._p.setAttribute('transform','translate('+(x+w)+' '+y+')'); L.tag.setAttribute('transform','translate('+(-tw-3)+' 0)'); }
  });
}
function tip(g, esc, pn){
  var L=g._lm, nm=g.getAttribute('data-name'), pg=g.getAttribute('data-page'), i=L&&L.info;
  if(L && L.tower && !pg) return '<b>'+esc(nm)+'</b><small>Tower of '+esc(L.tower.num+' '+L.tower.title)+' · '+L.tower.top+' floors</small><small><b>Click to ride the elevator ›</b></small>';
  if(!pg) return '<b>'+esc(nm)+'</b>';
  if(!i) i=pageInfo(pg, pn);
  return '<b>'+esc(nm)+'</b><small>Inside: '+esc(i.name)+(i.count?' · '+i.count+' '+esc(i.unit):'')+'</small><small><b>Click to open ›</b></small>';
}
function keyRow(){
  var sw='<svg width="26" height="14" viewBox="0 0 34 18" aria-hidden="true" style="flex:none"><rect x="2" y="2" width="30" height="14" rx="7" fill="rgba(255,255,255,.95)" stroke="var(--theme-color,#6d28d9)" stroke-width="1.6"/>'
    +'<g transform="translate(5 1) scale(.95)" fill="none" stroke="var(--theme-color,#6d28d9)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="'+ICON.rules+'"/></g>'
    +'<rect x="21" y="6" width="8" height="2" rx="1" fill="var(--theme-color,#6d28d9)"/><rect x="21" y="10" width="6" height="2" rx="1" fill="var(--theme-color,#6d28d9)" opacity=".6"/></svg>';
  return '<div class="pk-row">'+sw+'<div>Landmark with reference material inside <small>A glowing tag on a building says what is inside and how many (20 rules, 193 cases). Point at it for Open; click to go in. Tab to a tag and press Enter.</small></div></div>';
}
window._palLm={draw:draw, relayout:relayout, tip:tip, keyRow:keyRow, pageInfo:pageInfo, artKey:artKey};
})();
"""


def landmark_js() -> str:
    return (_JS.replace("__ART__", json.dumps(ART, separators=(",", ":")))
            .replace("__GRAD__", landmark_gradients())
            .replace("__MATCH__", json.dumps(MATCH))
            .replace("__TALL__", json.dumps(sorted(_towers.FLOORS))))


LANDMARK_JS = landmark_js()
