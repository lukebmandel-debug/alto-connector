"""Backgrounds made for the Retro style (retro.py): its own set, offered only while a page is in Retro, never on a System.

Luke, 2026-11-20, asked for "a great gatsby themed background option for retro" ("not for system retro though"); the first one, "Green Light",
was replaced on 2026-11-27: "i hate the green lighthouse background, i want something that really feels art deco and not done at an
elementary school level". Of three directions drawn as mocks (ORG/notes-art/deco-1127) he picked two: "i like a and c for art deco
background, go with both". Each is original geometry drawn here as flat vector SVG, nothing traced from a jacket, a film or any existing
artwork, in Retro's black and gold:
  Setback  black lacquer and gold leaf: one symmetrical stepped tower on the axis, fluted, a fine-ruled sunburst behind it, low mirrored
           setbacks at the sides, and a double gilt rule round the window with stepped corners and a quarter fan in each.

How it rides, like holo_backgrounds.py: the hosted Retro script (retro.py) adds the entries to the picker's catalog while Retro is on
(kind 'h', group 'Retro': drawn as a CSS ground, painted through Retro's own background layer) and takes them away when Retro goes off
or on a System; the page never carries them. Retro is always dark, so the light and the dark entry are the same picture. Three framings
of each, for a landscape window, a portrait one and a short wide one (a phone on its side), are chosen by a custom property of the hosted sheet (SCENES[..]['var']).
A page that had Green Light chosen gets the first of these instead (retro.py, bgs()).

Readability: the cards, chips and bars are opaque or black plates in Retro, so text sits on the scene only in a few free labels and
rules. Inside the content band every stroke stays under a luminance that keeps Retro's gold (#d9ae55) and cream (#efe6cf) text at WCAG AA
(4.5:1): the rays and flutes are drawn in the dimmest gold, damped where cards and text pass, and the bright gilding (EDGE) lives only in
the frame, 20 px in from the window's edge, and the margins outside the band (on a phone, where the band runs to the edge, the frame is
drawn in the dim gold too). Grounds are gradients, never a flat colour band. tests/test_retro_backgrounds.py holds this.
"""
from __future__ import annotations

import math
from urllib.parse import quote

GROUP = "Retro"
FRAME_M = 20                                         # the frame keeps 20 px off the window's edge


def _f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _svg(W, H, body, c0, c1):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c0}"/><stop offset="1" stop-color="{c1}"/>'
            f'</linearGradient></defs><rect width="{W}" height="{H}" fill="url(#g)"/>' + "".join(body) + "</svg>")


def _frame(W, H, m, col, gap=5, w=1.1, step=14):
    """a thin double rule round the window with stepped (setback) corners"""
    out = []
    for k in (0, gap):
        a, s = m + k, step - k * .5
        d = (f"M{_f(a + s)} {_f(a)}H{_f(W - a - s)}V{_f(a + s / 2)}H{_f(W - a - s / 2)}V{_f(a + s)}H{_f(W - a)}"
             f"V{_f(H - a - s)}H{_f(W - a - s / 2)}V{_f(H - a - s / 2)}H{_f(W - a - s)}V{_f(H - a)}"
             f"H{_f(a + s)}V{_f(H - a - s / 2)}H{_f(a + s / 2)}V{_f(H - a - s)}H{_f(a)}"
             f"V{_f(a + s)}H{_f(a + s / 2)}V{_f(a + s / 2)}H{_f(a + s)}Z")
        out.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w}"/>')
    return out


def _fan(cx, cy, r, n, a0, a1, col, w=1, rings=()):
    """a fan: n fine rays between angles a0..a1 (degrees, 0 = right, counter-clockwise, screen y down), with concentric arcs"""
    d = []
    for i in range(n + 1 if n else 0):
        t = math.radians(a0 + (a1 - a0) * i / n)
        d.append(f"M{_f(cx)} {_f(cy)}L{_f(cx + r * math.cos(t))} {_f(cy - r * math.sin(t))}")
    for k in rings:
        rr = r * k
        t0, t1 = math.radians(a0), math.radians(a1)
        d.append(f"M{_f(cx + rr * math.cos(t0))} {_f(cy - rr * math.sin(t0))}A{_f(rr)} {_f(rr)} 0 {1 if a1 - a0 > 180 else 0} 0 "
                 f"{_f(cx + rr * math.cos(t1))} {_f(cy - rr * math.sin(t1))}")
    return f'<path d="{"".join(d)}" fill="none" stroke="{col}" stroke-width="{w}"/>'


def _rays(cx, cy, r0, r1, n, a0, a1, col, w=1, alt=None):
    d = []
    for i in range(n + 1):
        t = math.radians(a0 + (a1 - a0) * i / n)
        r = r1 if (alt is None or i % 2 == 0) else r1 * alt
        d.append(f"M{_f(cx + r0 * math.cos(t))} {_f(cy - r0 * math.sin(t))}L{_f(cx + r * math.cos(t))} {_f(cy - r * math.sin(t))}")
    return f'<path d="{"".join(d)}" fill="none" stroke="{col}" stroke-width="{w}"/>'


def _ziggurat(cx, base, tiers, fill, col, w=1.2):
    """a symmetrical setback silhouette: tiers [(half width, height)] bottom up; returns the outline and its top y"""
    pts, y = [], base
    for hw, h in tiers:
        pts.append((cx - hw, y)); y -= h; pts.append((cx - hw, y))
    poly = pts + [(2 * cx - x, yy) for x, yy in reversed(pts)]
    return (f'<path d="M{"L".join(f"{_f(x)} {_f(yy)}" for x, yy in poly)}Z" fill="{fill}" stroke="{col}" stroke-width="{w}" '
            f'stroke-linejoin="miter"/>'), y


def _gilding(W, H, gilt, edge, dim):
    """the frame 20 px in, a quarter fan in each corner; on a phone (the content band runs to the window's edge) it is dim gold,
    the top corners of an upright phone (above the band) excepted"""
    q = 56 if gilt else 30
    out = _frame(W, H, FRAME_M, edge if gilt else dim, 5, 1.1, 18 if gilt else 12)
    for (x, y, a0) in ((FRAME_M, FRAME_M, 270), (W - FRAME_M, FRAME_M, 180), (FRAME_M, H - FRAME_M, 0), (W - FRAME_M, H - FRAME_M, 90)):
        out.append(_fan(x, y, q, 6, a0, a0 + 90, edge if (gilt or (y < H / 2 and H > W)) else dim, .9, rings=(1, .7, .4)))
    return out


# ── Setback ────────────────────────────────────────────────────────────
A_IN, A_IN2, A_EDGE, A_FILL = "#4a3a1b", "#2c2312", "#a8843a", "#0c0b09"   # dim gold (strokes), dimmer gold (hair rays, flutes), gilt, lacquer


def setback(W, H, s, gilt):
    cx, base = W / 2, H - (54 if gilt else 40) * s
    b = []
    top = base - 330 * s
    # the sunburst: 96 hair rays from below the tower's crown, long and short alternately, two pairs of thin arcs crossing them
    b.append(_rays(cx, top + 40 * s, 60 * s, max(W, H) * 1.2, 96, 0, 180, A_IN2, .9, alt=.62))
    b.append(_fan(cx, top + 40 * s, 240 * s, 0, 0, 180, A_IN, 1, rings=(1, 1.04, 1.9, 1.94)))
    # the tower: five setbacks, fluted
    tiers = [(hw * s, h * s) for hw, h in ((250, 70), (190, 80), (138, 80), (92, 60), (54, 40))]
    p, ytop = _ziggurat(cx, base, tiers, A_FILL, A_IN, 1.2)
    b.append(p)
    fl, y = [], base
    for hw, h in tiers:
        for k in range(-int(hw // (14 * s)) + 1, int(hw // (14 * s))):
            fl.append(f"M{_f(cx + k * 14 * s)} {_f(y - 6 * s)}V{_f(y - h + 6 * s)}")
        y -= h
    b.append(f'<path d="{"".join(fl)}" stroke="{A_IN2}" stroke-width=".8"/>')
    b.append(_fan(cx, ytop, 34 * s, 8, 0, 180, A_IN, 1, rings=(1, .6)))                                   # its crown
    b.append(f'<path d="M{_f(cx)} {_f(ytop - 34 * s)}V{_f(ytop - 120 * s)}" stroke="{A_IN}" stroke-width="1.2"/>')   # the mast
    # the base rule and the flanking setbacks, mirrored, low
    b.append(f'<path d="M0 {_f(base)}H{W}M0 {_f(base + 6 * s)}H{W}" stroke="{A_IN}" stroke-width="1"/>')
    for side in (-1, 1):
        x0 = cx + side * (W * .5 - FRAME_M)
        pts = ((0, 0), (0, 120), (60, 120), (60, 170), (110, 170), (110, 120), (170, 120), (170, 60), (230, 60), (230, 0))
        b.append(f'<path d="M{"L".join(f"{_f(x0 - side * px * s)} {_f(base - py * s)}" for px, py in pts)}Z" fill="{A_FILL}" '
                 f'stroke="{A_IN}" stroke-width="1"/>')
    b += _gilding(W, H, gilt, A_EDGE, A_IN)
    return _svg(W, H, b, "#060607", "#0d0c0a")


# id: picker name, the sheet's custom property, the drawing, its ground (top, bottom)
SCENES = {
    "r-deco-setback": {"n": "Setback", "var": "--rt-ds", "fn": setback, "c": ("#060607", "#0d0c0a")},
}
OLD_IDS = ("r-green-light",)                         # retired grounds: a page that chose one gets the first scene


# the framings: (window, scale, gilt). A desk window; an upright phone; a phone on its side (short and wide: drawn at its own size so the
# frame keeps its 20 px and its top rule, which the desk framing scaled down to cover it would crop away)
FRAMINGS = {"land": ((1440, 900), 1, True), "port": ((390, 844), .62, False), "short": ((844, 390), .42, False)}


def svg(bg_id: str, framing) -> str:
    """one scene in one framing ('land', 'port', 'short'; True/False stand for land/port)"""
    framing = {True: "land", False: "port"}.get(framing, framing)
    (W, H), s, gilt = FRAMINGS[framing]
    return SCENES[bg_id]["fn"](W, H, s, gilt)


def _url(s: str) -> str:
    return 'url("data:image/svg+xml,' + quote(s.replace('"', "'"), safe=" '=/:;,.-()!") + '")'


def css_vars() -> str:
    """Each scene's framings as a custom property of the Retro sheet: the portrait one in a portrait window, the short one in a wide window
    under 500 px tall (a phone on its side), the landscape one otherwise."""
    def at(fr):
        return "".join(f"{v['var']}:{_url(svg(k, fr))};" for k, v in SCENES.items())
    return (f"html.alto-retro{{{at('land')}}}@media (max-aspect-ratio:1/1){{html.alto-retro{{{at('port')}}}}}"
            f"@media (min-aspect-ratio:1/1) and (max-height:500px){{html.alto-retro{{{at('short')}}}}}")


def _entry(v: dict) -> dict:
    c0, c1 = v["c"]
    return {"b": f"var({v['var']}) center bottom / cover no-repeat, linear-gradient(180deg,{c0},{c1})", "a": c0, "s": c0, "q": c1}


def client_entries() -> dict:
    """Catalog entries the Retro script adds while the style is on: {id: {g, k 'h', n, l, d}} (Retro is always dark: l == d)."""
    out = {}
    for k, v in SCENES.items():
        e = _entry(v)
        out[k] = {"g": GROUP, "k": "h", "n": v["n"], "l": e, "d": dict(e)}
    return out
