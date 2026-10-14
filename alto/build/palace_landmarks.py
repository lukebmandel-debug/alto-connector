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
    "sand": (("#f4e9cd", "#dcc799", "#c3ad7a", "#fbf3dd"), ("#80745b", "#5d5441", "#463f31", "#908469")),
    "green": (("#cfe3dc", "#8fb8ac", "#74a094", "#e0f0ea"), ("#4f7d70", "#33574d", "#26433b", "#5f8f81")),
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
        v.append("--lz-win:rgba(34,40,66,.30);--lz-hi:rgba(255,255,255,.55);--lz-gs:rgba(20,26,55,.20);"
                 if mode == 0 else
                 "--lz-win:rgba(8,10,20,.50);--lz-hi:rgba(255,255,255,.20);--lz-gs:rgba(0,0,0,.40);")
        sel = ".pal-svg" if mode == 0 else "html.dark .pal-svg"
        lines.append(f"  {sel}{{{''.join(v)}}}")
    mats = []
    for m in _MATS:
        mats.append(f"  .lz-s-{m}{{fill:var(--lz-{m}-s);}} .lz-t-{m}{{fill:var(--lz-{m}-t);}}")
    return "\n".join(lines) + "\n" + "\n".join(mats) + r"""
  .lz-f,.lz-sd,.lz-tp{stroke:var(--lz-line,#667);stroke-width:1;stroke-opacity:.62;stroke-linejoin:round;vector-effect:non-scaling-stroke;}
  .lz-ln{fill:none;stroke:var(--lz-line,#667);stroke-width:1;stroke-opacity:.55;stroke-linecap:round;vector-effect:non-scaling-stroke;}
  .lz-win{fill:var(--lz-win);stroke:none;}
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
  /* the key's row for them */
"""


# ── the art ─────────────────────────────────────────────────────────────────
def _f(n: float) -> str:
    s = f"{n:.1f}"
    return s[:-2] if s.endswith(".0") else s


class _Art:
    """One building: a list of SVG parts, drawn back to front. Every solid is a front
    face (a gradient lit from the top left) with, when it stands out, a side face to
    its right and a top face above it, stepped back up and to the right."""

    def __init__(self, w: int, h: int):
        self.w, self.h, self.parts = w, h, []
        self.dx, self.dy = 0.0, 0.0

    def add(self, s: str):
        self.parts.append(s)

    def front(self, x, y, w, h, m, extra=""):
        self.add(f'<rect class="lz-f" x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" fill="url(#lzg-{m}-{{s}})"{extra}/>')

    def solid(self, x, y, w, h, m, d=7.0, side=True, top=True):
        """A box: its top, its right side, then its front."""
        dx, dy = d, -d * 0.5
        if top:
            self.add(f'<path class="lz-tp lz-t-{m}" d="M{_f(x)} {_f(y)}l{_f(dx)} {_f(dy)}h{_f(w)}l{_f(-dx)} {_f(-dy)}z"/>')
        if side:
            self.add(f'<path class="lz-sd lz-s-{m}" d="M{_f(x + w)} {_f(y)}l{_f(dx)} {_f(dy)}v{_f(h)}l{_f(-dx)} {_f(-dy)}z"/>')
        self.front(x, y, w, h, m)

    def side(self, x, y, h, m, d=7.0):
        dx, dy = d, -d * 0.5
        self.add(f'<path class="lz-sd lz-s-{m}" d="M{_f(x)} {_f(y)}l{_f(dx)} {_f(dy)}v{_f(h)}l{_f(-dx)} {_f(-dy)}z"/>')

    def poly(self, pts, m):
        p = "M" + "L".join(f"{_f(a)} {_f(b)}" for a, b in pts) + "z"
        self.add(f'<path class="lz-f" d="{p}" fill="url(#lzg-{m}-{{s}})"/>')

    def top_(self, pts, m):
        p = "M" + "L".join(f"{_f(a)} {_f(b)}" for a, b in pts) + "z"
        self.add(f'<path class="lz-tp lz-t-{m}" d="{p}"/>')

    def wins(self, x0, y0, nx, ny, dx, dy, w, h, arch=False):
        d = ""
        for j in range(ny):
            for i in range(nx):
                x, y = x0 + i * dx, y0 + j * dy
                if arch:
                    d += f"M{_f(x)} {_f(y + h)}v{_f(-h + w / 2)}a{_f(w / 2)} {_f(w / 2)} 0 0 1 {_f(w)} 0v{_f(h - w / 2)}z"
                else:
                    d += f"M{_f(x)} {_f(y)}h{_f(w)}v{_f(h)}h{_f(-w)}z"
        self.add(f'<path class="lz-win" d="{d}"/>')

    def cols(self, x0, y, n, gap, w, h, m="trim"):
        """A colonnade: n columns, each its own lit round shaft."""
        for i in range(n):
            x = x0 + i * gap
            self.add(f'<rect class="lz-col" x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" fill="url(#lzc-{{s}})"/>')

    def line(self, d):
        self.add(f'<path class="lz-ln" d="{d}"/>')

    def shadow(self, x0, x1, y, d=9.0):
        self.add(f'<path class="lz-gs" d="M{_f(x0)} {_f(y)}L{_f(x0 + d)} {_f(y - d * .5)}H{_f(x1 + d)}L{_f(x1)} {_f(y)}z"/>')

    def out(self) -> dict:
        return {"w": self.w, "h": self.h, "svg": "".join(self.parts)}


def _independence() -> dict:
    a = _Art(200, 124)
    base = 116
    a.shadow(8, 192, base)
    # the wings (arcades) and their small roofs
    for x in (10, 158):
        a.solid(x, 92, 32, base - 92, "brick", d=6)
        a.poly([(x - 2, 92), (x + 6, 82), (x + 26, 82), (x + 34, 92)], "slate")
        a.top_([(x + 6, 82), (x + 12, 79), (x + 32, 79), (x + 26, 82)], "slate")
        a.wins(x + 5, 98, 4, 1, 7, 0, 4, 10)
        a.add(f'<rect class="lz-col" x="{x + 25}" y="73" width="3" height="9" fill="url(#lzg-brick-{{s}})"/>')
    # the main block, its roof and chimneys
    a.solid(40, 76, 120, base - 76, "brick", d=8)
    a.add('<path class="lz-sd lz-s-slate" d="M160 70l8-4v10l-8 4z"/>')
    a.poly([(36, 76), (48, 62), (152, 62), (164, 76)], "slate")
    a.top_([(48, 62), (56, 58), (160, 58), (152, 62)], "slate")
    a.add('<path class="lz-sd lz-s-slate" d="M152 62l8-4 8 14-4 4z"/>')
    for x in (58, 134):
        a.solid(x, 50, 6, 12, "brick", d=3)
    a.add('<rect class="lz-f" x="40" y="76" width="120" height="3.2" fill="url(#lzg-trim-{s})"/>')   # cornice
    a.add('<rect class="lz-f" x="40" y="94" width="120" height="1.6" fill="url(#lzg-trim-{s})"/>')   # string course
    a.wins(48, 82, 7, 1, 14, 0, 5, 9)
    a.wins(48, 98, 7, 1, 14, 0, 5, 11)
    # the tower: brick stage, white clock stage, belfry, steeple
    a.solid(88, 56, 24, 60, "brick", d=6)
    a.add('<rect class="lz-f" x="86" y="56" width="28" height="3" fill="url(#lzg-trim-{s})"/>')
    a.solid(90, 38, 20, 18, "trim", d=5)
    a.add('<circle class="lz-f" cx="100" cy="47" r="6" fill="url(#lzg-trim-{s})"/>')
    a.line("M100 47v-4M100 47l3 2")
    a.solid(92, 24, 16, 14, "trim", d=4)
    a.wins(95.5, 27, 2, 1, 7, 0, 3, 8, arch=True)
    a.poly([(91, 24), (100, 4), (109, 24)], "trim")
    a.add('<path class="lz-sd lz-s-trim" d="M109 24l4-2-9-18-4 0z" opacity=".6"/>')
    a.line("M100 4v-4")
    a.add('<circle class="lz-f" cx="100" cy="6.5" r="1.6" fill="url(#lzg-bronze-{s})"/>')
    # the door, lit (the way in)
    a.add('<path class="lz-door glow" d="M94 116v-9a6 6 0 0 1 12 0v9z"/>')
    a.line("M92 116h16M90 118h20")
    a.add('<rect class="lz-f" x="8" y="116" width="184" height="3.5" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _cityhall() -> dict:
    a = _Art(220, 168)
    base = 158
    a.shadow(8, 212, base, 10)
    # the great block with its end pavilions
    a.solid(12, 108, 196, base - 108, "stone", d=9)
    for x in (12, 176):
        a.solid(x, 94, 32, base - 94, "stone", d=9)
        a.poly([(x - 3, 94), (x + 5, 82), (x + 27, 82), (x + 35, 94)], "slate")
        a.top_([(x + 5, 82), (x + 12, 78.5), (x + 34, 78.5), (x + 27, 82)], "slate")
        a.wins(x + 4, 100, 3, 1, 10, 0, 5, 11)
        a.wins(x + 4, 120, 3, 1, 10, 0, 5, 11)
        a.wins(x + 4, 140, 3, 1, 10, 0, 5, 11)
    a.add('<rect class="lz-f" x="12" y="108" width="196" height="3.4" fill="url(#lzg-trim-{s})"/>')
    for r in (116, 132, 146):
        for x in (57, 163):
            a.wins(x, r, 1, 1, 0, 0, 6, 10 if r < 140 else 9)
    # the pavilion that carries the tower
    a.solid(70, 70, 80, base - 70, "stone", d=8)
    a.add('<rect class="lz-f" x="68" y="70" width="84" height="3.4" fill="url(#lzg-trim-{s})"/>')
    a.add('<path class="lz-win" d="M80 80h60v16H80z"/>')
    for i in range(5):
        a.add(f'<rect class="lz-col" x="{82 + i * 13}" y="82" width="4" height="12" fill="url(#lzc-{{s}})"/>')
    a.wins(76, 106, 5, 1, 13, 0, 6, 12)
    a.wins(76, 126, 5, 1, 13, 0, 6, 12)
    # the mansard over it
    a.poly([(66, 70), (76, 56), (144, 56), (154, 70)], "slate")
    a.top_([(76, 56), (84, 52), (152, 52), (144, 56)], "slate")
    a.add('<path class="lz-sd lz-s-slate" d="M144 56l8-4 6 14-4 4z"/>')
    # the tower: shaft, clock stage, lantern, cap, and Penn
    a.solid(88, 40, 44, 16, "stone", d=7)
    a.solid(92, 24, 36, 16, "trim", d=6)
    a.add('<circle class="lz-f" cx="110" cy="32" r="6" fill="url(#lzg-trim-{s})"/>')
    a.line("M110 32v-4M110 32l3.2 2")
    a.solid(96, 12, 28, 12, "stone", d=5)
    a.wins(99, 14, 4, 1, 6.5, 0, 3.4, 8, arch=True)
    a.poly([(94, 12), (100, 6), (120, 6), (126, 12)], "slate")
    a.add('<path class="lz-sd lz-s-slate" d="M126 12l5-2.5-6-4-5 .5z"/>')
    # the statue: bronze William Penn on top
    a.add('<path class="lz-f" d="M107.8 6v-5.5h4.4v5.5z" fill="url(#lzg-bronze-{s})"/>')
    a.add('<circle class="lz-f" cx="110" cy="-1" r="1.9" fill="url(#lzg-bronze-{s})"/>')
    a.add('<path class="lz-f" d="M112 1.5l5-3.5" fill="none"/>')
    # the lit archway (the way in), steps
    a.add('<path class="lz-door glow" d="M103 158v-14a7 7 0 0 1 14 0v14z"/>')
    a.add('<rect class="lz-f" x="94" y="158" width="32" height="2.4" fill="url(#lzg-stone-{s})"/>')
    a.add('<rect class="lz-f" x="90" y="160.4" width="40" height="2.4" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _art() -> dict:
    a = _Art(300, 118)
    base = 108
    a.shadow(10, 290, base + 2, 10)
    # the wings: a podium and a long wall with its colonnade
    for x, side in ((14, False), (204, True)):
        a.solid(x, 54, 82, base - 54, "sand", d=7, side=side)
        a.add(f'<rect class="lz-f" x="{x - 1}" y="52" width="84" height="3.4" fill="url(#lzg-trim-{{s}})"/>')
        a.wins(x + 8, 62, 6, 1, 12, 0, 6, 12)
        a.add(f'<rect class="lz-f" x="{x - 2}" y="{base - 3}" width="86" height="3" fill="url(#lzg-stone-{{s}})"/>')
    # the end pavilions' small pediments
    for x in (14, 252):
        a.poly([(x - 2, 52), (x + 15, 41), (x + 32, 52)], "sand")
    # the grand steps
    for i in range(5):
        a.add(f'<rect class="lz-f" x="{96 - i * 3}" y="{base - 10 + i * 4}" width="{108 + i * 6}" height="4" fill="url(#lzg-stone-{{s}})"/>')
    # the temple front: stylobate, eight columns, entablature, pediment with its sculpture
    a.solid(108, 40, 84, 5, "trim", d=8, side=True, top=False)
    a.add('<path class="lz-f" d="M104 40h92v3H104z" fill="url(#lzg-trim-{s})"/>')
    a.add('<rect class="lz-f" x="112" y="43" width="76" height="52" fill="url(#lzg-sand-{s})"/>')
    a.add('<path class="lz-door glow" d="M142 95v-22a8 8 0 0 1 16 0v22z"/>')
    a.cols(111, 43, 8, 10.2, 4.6, 50)
    a.add('<path class="lz-sd lz-s-trim" d="M196 40l8-4v7l-8 4z"/>')
    a.poly([(100, 40), (150, 14), (200, 40)], "trim")
    a.add('<path class="lz-sd lz-s-green" d="M104 38l46-23 46 23z" opacity=".55"/>')
    a.add('<path class="lz-sd lz-s-trim" d="M200 40l8-4-50-25-8 3z" opacity=".7"/>')
    a.add('<circle class="lz-f" cx="150" cy="30" r="3.2" fill="url(#lzg-bronze-{s})"/>')
    a.line("M125 36h14M161 36h14")
    a.add('<path class="lz-f" d="M148 14h4l-2-5z" fill="url(#lzg-bronze-{s})"/>')
    a.add('<rect class="lz-f" x="100" y="94" width="100" height="3" fill="url(#lzg-trim-{s})"/>')
    return a.out()


def _franklin() -> dict:
    a = _Art(240, 138)
    base = 128
    a.shadow(8, 232, base, 9)
    # wings
    for x in (12, 172):
        a.solid(x, 74, 56, base - 74, "stone", d=7)
        a.add(f'<rect class="lz-f" x="{x - 1}" y="72" width="58" height="3.4" fill="url(#lzg-trim-{{s}})"/>')
        a.wins(x + 6, 84, 4, 2, 12, 20, 5, 11)
    # the rotunda: drum and the green dome
    a.solid(88, 46, 64, 40, "stone", d=7, top=False)
    a.add('<path class="lz-sd lz-s-green" d="M90 46c0-24 12-38 30-38s30 14 30 38z" transform="translate(7 -3.5)"/>')
    a.add('<path class="lz-f" d="M90 46c0-24 12-38 30-38s30 14 30 38z" fill="url(#lzg-green-{s})"/>')
    a.line("M120 8v38M104 12c-4 9-6 20-6 34M136 12c4 9 6 20 6 34")
    a.add('<path class="lz-f" d="M118 8l2-6 2 6z" fill="url(#lzg-bronze-{s})"/>')
    a.wins(97, 54, 5, 1, 10, 0, 4, 12)
    # the portico: six columns and the pediment
    a.add('<rect class="lz-f" x="80" y="72" width="80" height="4" fill="url(#lzg-trim-{s})"/>')
    a.poly([(76, 72), (120, 54), (164, 72)], "trim")
    a.add('<circle class="lz-f" cx="120" cy="65" r="3" fill="url(#lzg-bronze-{s})"/>')
    a.add('<rect class="lz-f" x="82" y="76" width="76" height="46" fill="url(#lzg-stone-{s})"/>')
    a.add('<path class="lz-door glow" d="M113 122v-18a7 7 0 0 1 14 0v18z"/>')
    a.cols(83, 76, 6, 14.2, 5, 46)
    a.add('<rect class="lz-f" x="76" y="122" width="88" height="3" fill="url(#lzg-trim-{s})"/>')
    a.add('<rect class="lz-f" x="72" y="125" width="96" height="3" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _convention() -> dict:
    a = _Art(300, 112)
    base = 102
    a.shadow(8, 292, base, 10)
    # low glass halls either side
    for x in (12, 220):
        a.solid(x, 66, 68, base - 66, "glass", d=7)
        a.add('<path class="lz-ln" d="' + "".join(f"M{_f(x + i * 11.3 + 11.3)} 66v{base - 66}" for i in range(5)) + '"/>')
        a.add(f'<path class="lz-hi" d="M{x + 6} {base - 8}l18 -26M{x + 24} {base - 8}l18 -26"/>')
    # the great barrel vault, its ribs, and the brick headhouse arch
    a.add('<path class="lz-sd lz-s-glass" d="M78 102V54c0-26 16-40 72-40s72 14 72 40v48z" transform="translate(6 -3)"/>')
    a.add('<path class="lz-f" d="M78 102V54c0-26 16-40 72-40s72 14 72 40v48z" fill="url(#lzg-glass-{s})"/>')
    a.add('<path class="lz-ln" d="M96 102V50c0-18 4-28 10-32M114 102V48c0-20 8-30 18-32M132 102V46c0-22 8-32 18-32M150 102V46c0-22 8-32 18-32M168 102V48c0-20-4-30-14-34M186 102V50c0-16-4-26-12-32M204 102V54c0-14-4-24-10-30"/>')
    a.add('<path class="lz-hi" d="M90 94l26-62M116 94l20-48"/>')
    a.add('<rect class="lz-f" x="108" y="62" width="84" height="40" fill="url(#lzg-brick-{s})"/>')
    a.wins(114, 70, 5, 1, 16, 0, 8, 22, arch=True)
    a.add('<path class="lz-door glow" d="M142 102v-14a8 8 0 0 1 16 0v14z"/>')
    a.add('<rect class="lz-f" x="104" y="58" width="92" height="4" fill="url(#lzg-trim-{s})"/>')
    a.add('<rect class="lz-f" x="4" y="102" width="292" height="3.5" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _station() -> dict:
    a = _Art(280, 108)
    base = 98
    a.shadow(8, 272, base, 9)
    a.solid(12, 34, 256, base - 34, "stone", d=8)
    a.add('<rect class="lz-f" x="8" y="26" width="264" height="8" fill="url(#lzg-trim-{s})"/>')
    a.add('<rect class="lz-f" x="12" y="20" width="256" height="6" fill="url(#lzg-stone-{s})"/>')
    a.add('<path class="lz-win" d="M30 42h220v50H30z" opacity=".5"/>')
    a.cols(30, 36, 12, 20, 6.5, 56)
    a.add('<path class="lz-door glow" d="M133 98v-16a7 7 0 0 1 14 0v16z"/>')
    a.add('<rect class="lz-f" x="22" y="92" width="236" height="3" fill="url(#lzg-trim-{s})"/>')
    a.add('<rect class="lz-f" x="16" y="95" width="248" height="3" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _generic() -> dict:
    a = _Art(160, 100)
    base = 90
    a.shadow(14, 146, base, 9)
    a.solid(24, 38, 112, base - 38, "stone", d=8)
    a.poly([(20, 38), (80, 12), (140, 38)], "trim")
    a.add('<path class="lz-sd lz-s-trim" d="M140 38l8-4-60-26-8 4z" opacity=".7"/>')
    a.add('<rect class="lz-f" x="22" y="38" width="116" height="3.4" fill="url(#lzg-trim-{s})"/>')
    a.wins(36, 50, 5, 1, 20, 0, 8, 22)
    a.add('<path class="lz-door glow" d="M71 90v-14a9 9 0 0 1 18 0v14z"/>')
    a.add('<rect class="lz-f" x="16" y="90" width="128" height="3" fill="url(#lzg-stone-{s})"/>')
    return a.out()


def _build_art() -> dict:
    return {"ind": _independence(), "city": _cityhall(), "art": _art(), "frank": _franklin(),
            "conv": _convention(), "stn": _station(), "gen": _generic()}


ART = _build_art()
# which landmark names get which art (the page's own label, case-insensitive)
MATCH = [["ind", r"independence hall"], ["city", r"city hall"], ["art", r"art museum|museum of art|philadelphia museum"],
         ["frank", r"franklin institute"], ["conv", r"convention cent(er|re)"], ["stn", r"(30th|thirtieth) street station"]]


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
    return "".join(g)


LANDMARK_CSS = landmark_css()


# ── the page side ───────────────────────────────────────────────────────────
_JS = r"""
(function(){
var NS='http://www.w3.org/2000/svg', XL='http://www.w3.org/1999/xlink';
var ART=__ART__, GRAD='__GRAD__';
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
  g._lm={x:x,y:y,w:w,h:h,name:nm,info:info,page:l.page,strip:strip,art:art,use:use,nameT:name,sub:sub,tag:tag,tbg:tbg,tn:tn,to:to,pn:o.pageName};
  /* keyboard and screen readers */
  g.setAttribute('aria-label', label(nm, info));
  if(info){ g.setAttribute('role','link'); g.setAttribute('tabindex','0');
    g.addEventListener('keydown', function(e){ if(e.key==='Enter' || e.key===' '){ e.preventDefault(); e.stopPropagation(); o.open(l.page); } }); }
  else g.setAttribute('role','img');
}
/* the layout that depends on the zoom: names and tags keep a size on the screen, so where they would not
   fit inside a small card the name hangs under it; the building takes what is left */
function relayout(svg, Z){
  Z=Z||1; var u=1/Z, far=Z<.42, near=Z>=.8;
  svg.querySelectorAll('.pl-lmb').forEach(function(g){ var L=g._lm; if(!L) return;
    if(L.page && L.info && !L.info.count){ L.info=pageInfo(L.page, L.pn); g.setAttribute('aria-label', label(L.name, L.info)); }
    var x=L.x, y=L.y, w=L.w, h=L.h, n=L.name.length, fit=Math.min(26, w*.94/(Math.max(n,3)*.6));
    g.style.setProperty('--lm-nat', fit.toFixed(1)+'px');
    var fn=Math.min(Math.max(11.5*u, fit), 21*u), words=L.name.split(' '), lines=[L.name];
    if(n*.6*fn>w*.98 && words.length>1){ var half=Math.ceil(words.length/2); lines=[words.slice(0,half).join(' '), words.slice(half).join(' ')]; }
    var wide=Math.max.apply(null, lines.map(function(s){ return s.length; }))*.6*fn;
    var subH=(L.sub && near)?13*u:0, stripH=lines.length*fn*1.22+fn*.42+subH, hang=(wide>w*1.02) || stripH>h*.46;
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
            .replace("__MATCH__", json.dumps(MATCH)))


LANDMARK_JS = landmark_js()
