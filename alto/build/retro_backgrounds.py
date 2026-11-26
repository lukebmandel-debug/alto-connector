"""Backgrounds made for the Retro style (retro.py): its own set, offered only while a page is in Retro, never on a System.

Luke, 2026-11-20: "i want you to add a great gatsby themed background option for retro, think the green lighthouse scene and the
abstract art style of the time, maybe bauhaus" / "not for system retro though". "Green Light" is original art drawn here as flat SVG,
nothing traced from the 1925 jacket, a film or any existing artwork: a small green light at the end of a dock across a dark bay, an Art
Deco sunburst fanning from it, a stepped skyline on the far shore and concentric arches, in Retro's black and gold with the green
light as the only bright accent. (The 2026-11-26 art round picked mock A, Deco-forward: ORG/notes-art/gatsby-1126.)

How it rides, like holo_backgrounds.py: the hosted Retro script (retro.py) adds the entry to the picker's catalog while Retro is on
(kind 'h', group 'Retro': drawn as a CSS ground, painted through Retro's own background layer) and takes it away when Retro goes off
or on a System; the page never carries it. Retro is always dark, so the light and the dark entry are the same picture. Two framings,
one for a landscape window and one for a portrait one, are chosen by the hosted sheet's custom property `--rt-gl`.

Readability: the cards, chips and bars are opaque or black plates in Retro, so text sits on the scene only in a few free labels and
rules; every shape stays under a luminance that keeps Retro's gold (#d9ae55) and cream (#efe6cf) text at WCAG AA (4.5:1), and a flat veil
damps the rays across the middle of the board where cards and text pass. tests/test_retro_backgrounds.py holds this.
"""
from __future__ import annotations

import math
from urllib.parse import quote

GROUP = "Retro"
BG_ID = "r-green-light"
BASE = ("#06070a", "#0a0e12", "#08141a")            # sky top, horizon haze, water
GOLD_D, GOLD_M = "#241f11", "#332b15"              # rays, thin strokes: dim gold
HALO = ("#0b3322", "#0c4328")                       # the dark halo round the light
CORE = "#3dff8a"                                    # the green light: the one bright thing, kept off the card band


def _rays(cx, cy, r, n, a0, a1, fill, op):
    d = []
    for i in range(0, n, 2):
        t0 = math.radians(a0 + (a1 - a0) * i / n)
        t1 = math.radians(a0 + (a1 - a0) * (i + 1) / n)
        d.append(f"M{cx} {cy}L{cx + r * math.cos(t0):.0f} {cy - r * math.sin(t0):.0f}L{cx + r * math.cos(t1):.0f} {cy - r * math.sin(t1):.0f}Z")
    return f'<path d="{"".join(d)}" fill="{fill}" opacity="{op}"/>'


def _skyline(base, steps, w, fill):
    d = f"M0 {base}"
    for h in steps:
        d += f"V{base - h}h{w}"
    return f'<path d="{d}V{base}Z" fill="{fill}"/>'


def _scene(W, H, land):
    s = 1 if land else .62
    hy = round(H * (.62 if land else .80))
    lx = round(W * .93) if land else 300                 # phone: nudged inward, well clear of the card edge (Board, 2026-11-26)
    ly = hy - round(16 * s)
    b = [f'<rect width="{W}" height="{H}" fill="{BASE[0]}"/><rect y="{hy - round(H * .3)}" width="{W}" height="{round(H * .3)}" fill="{BASE[1]}"/>',
         _rays(lx, hy, W * 1.1, 24, 6, 174, GOLD_D, .9)]
    for r in (260, 190, 120):
        r = r * s
        b.append(f'<path d="M{lx - r:.0f} {hy}A{r:.0f} {r:.0f} 0 0 1 {lx + r:.0f} {hy}" fill="none" stroke="{GOLD_M}" stroke-width="2"/>')
    sw = round(34 * s)
    b.append(_skyline(hy, [60, 110, 80, 150, 120, 200, 140, 90, 60], sw, "#0d1015"))
    b.append(_skyline(hy, [30, 40, 30, 60, 40, 70, 50, 30, 20], sw + 10, "#10141a"))
    # the veil: where cards and text cross the middle of the board the rays and arches are damped (a flat horizontal fade,
    # darkest across the card band, open at the far right where the light sits)
    b.append(f'<defs><linearGradient id="v" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="{BASE[0]}" stop-opacity=".55"/>'
             f'<stop offset=".72" stop-color="{BASE[0]}" stop-opacity=".55"/><stop offset="1" stop-color="{BASE[0]}" stop-opacity="0"/></linearGradient></defs>'
             f'<rect width="{W}" height="{hy}" fill="url(#v)"/>')
    b.append(f'<rect y="{hy}" width="{W}" height="{H - hy}" fill="{BASE[2]}"/>')
    b.extend(f'<rect y="{hy + round(30 * s) + i * round(38 * s)}" width="{W}" height="1" fill="{GOLD_D}"/>' for i in range(12))
    b.extend(f'<rect x="{lx - round((30 - i * 3) * s)}" y="{hy + round(14 * s) + i * round(14 * s)}" width="{round((60 - i * 6) * s)}" height="{round(3 * s) or 2}" fill="{HALO[1]}" opacity="{.7 - i * .09:.2f}"/>' for i in range(6))
    px = lx - round(150 * s)
    b.append(f'<rect x="{px}" y="{hy + round(2 * s)}" width="{W - px}" height="{round(5 * s)}" fill="{GOLD_M}"/>'
             f'<rect x="{px - round(3 * s)}" y="{hy + round(2 * s) - round(22 * s)}" width="{round(6 * s)}" height="{round(22 * s)}" fill="{GOLD_M}"/>')
    halo = ((46, HALO[0]), (30, HALO[1])) if land else ((34, HALO[0]), (20, HALO[1]))
    b.extend(f'<circle cx="{lx}" cy="{ly}" r="{k * (s if land else 1)}" fill="{c}"/>' for k, c in halo)
    b.append(f'<circle cx="{lx}" cy="{ly}" r="{8 if land else 7}" fill="{CORE}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice">' + "".join(b) + "</svg>")


def svg_landscape() -> str:
    return _scene(1440, 900, True)


def svg_portrait() -> str:
    return _scene(390, 844, False)


def _url(svg: str) -> str:
    return 'url("data:image/svg+xml,' + quote(svg.replace('"', "'"), safe=" '=/:;,.-()!") + '")'


def css_vars() -> str:
    """The two framings as a custom property of the Retro sheet: the portrait one in a portrait window, the landscape one otherwise."""
    return (f"html.alto-retro{{--rt-gl:{_url(svg_landscape())};}}"
            f"@media (max-aspect-ratio:1/1){{html.alto-retro{{--rt-gl:{_url(svg_portrait())};}}}}")


def _entry() -> dict:
    ground = f"var(--rt-gl) center bottom / cover no-repeat, linear-gradient(180deg,{BASE[0]},{BASE[1]} 62%,{BASE[2]})"
    return {"b": ground, "a": BASE[0], "s": BASE[0], "q": BASE[1]}


def client_entries() -> dict:
    """Catalog entries the Retro script adds while the style is on: {id: {g, k 'h', n, l, d}} (Retro is always dark: l == d)."""
    e = _entry()
    return {BG_ID: {"g": GROUP, "k": "h", "n": "Green Light", "l": e, "d": dict(e)}}
