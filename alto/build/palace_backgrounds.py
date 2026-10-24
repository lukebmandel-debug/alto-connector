"""Backgrounds made for reading a street-grid map: the Memory Palace's own set.

A Memory Palace is a city drawn as an even grid of coloured lines, with chips, numbered
buildings and street names on glass. The photographs, colours and patterns offered to
every timeline suit a timeline or an outline; a map is read differently: it wants a calm,
low-contrast ground that stays out of the way of the coloured streets, so each of these is
quiet (a pale or deep ground, never a picture) and each has a light and a dark version.

They are the same kind of thing as the colours and patterns (backgrounds.py): drawn as CSS,
no image to download, one id stored per timeline and synced like the others. They are in
the catalog, and so in the picker, of a Memory Palace page only; a Memory Palace that nobody
has chosen for opens on the first of them (DEFAULT) rather than the Alto wallpaper.

Each theme's entry carries
  b  the CSS background (layers, then the base gradient)
  a  the colour of the strip behind the top bars (and the status bar), q the colour a
     private page's gate paints while it opens
  v  the map's own custom properties for that ground (palace.py reads them): the glass the
     city stands on, its edge, the halo behind street names and chips, the ink, the parks and
     landmarks, and `--pal-ground`, the colour the streets are contrast-checked against.
"""
from __future__ import annotations

import random
from urllib.parse import quote

GROUP = "Memory Palace"


def _rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgba(h: str, a: float) -> str:
    r, g, b = _rgb(h)
    return f"rgba({r},{g},{b},{a:g})"


def _svg(body: str, w: int, h: int) -> str:
    s = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">{body}</svg>'
    return 'url("data:image/svg+xml,' + quote(s, safe="~()*!.'") + f'") 0 0/{w}px {h}px'


def _lines(ink: str, a_fine: float, step_fine: int, a_major: float, step_major: int) -> list:
    """Two rulings, fine and major (a graticule, a blueprint's grid)."""
    out = []
    for a, s in ((a_major, step_major), (a_fine, step_fine)):
        i = _rgba(ink, a)
        out.append(f"linear-gradient({i} 1px, transparent 1px) 0 0/{s}px {s}px")
        out.append(f"linear-gradient(90deg,{i} 1px, transparent 1px) 0 0/{s}px {s}px")
    return out


def _grain(ink: str, alpha: float, freq: float = 0.85, size: int = 160) -> str:
    """Fine noise in an ink colour (paper fibre, chalk dust): feTurbulence turned to alpha."""
    r, g, b = (c / 255 for c in _rgb(ink))
    body = ('<filter id="n" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" stitchTiles="stitch"/>'
            f'<feColorMatrix values="0 0 0 0 {r:.3f} 0 0 0 0 {g:.3f} 0 0 0 0 {b:.3f} {alpha * 1.2:.3f} 0 0 0 -.2"/>'
            f'</filter><rect width="{size}" height="{size}" filter="url(#n)"/>')
    return _svg(body, size, size)


def _lights(colors: list, alpha: float, n: int = 26, size: int = 240, seed: int = 11) -> str:
    """Specks of light scattered on a tile (a city seen from far off); deterministic."""
    rnd = random.Random(seed)
    body = ""
    for _ in range(n):
        c = colors[rnd.randrange(len(colors))]
        body += (f'<circle cx="{rnd.randrange(4, size - 4)}" cy="{rnd.randrange(4, size - 4)}" '
                 f'r="{rnd.choice((0.8, 1.0, 1.3, 1.7))}" fill="{c}" fill-opacity="{alpha * rnd.choice((0.55, 0.8, 1.0)):.2f}"/>')
    return _svg(body, size, size)


def _glow(at: str, color: str, a: float, stop: int = 62) -> str:
    return f"radial-gradient({at}, {_rgba(color, a)}, transparent {stop}%)"


def _base(angle: int, *stops: str) -> str:
    return f"linear-gradient({angle}deg," + ",".join(stops) + ")"


def _vars(ground: str, glass: str, edge: str, halo: str, text: str, park: str, lm: str, **more) -> dict:
    """The map's custom properties for one ground. glass/edge/halo are CSS colours."""
    r, g, b = _rgb(ground)
    v = {"--pal-ground": f"{r},{g},{b}", "--pal-glass": glass, "--pal-glass-edge": edge, "--pal-halo": halo,
         "--pal-text": text, "--pal-park": park, "--pal-lm": lm}
    v.update(more)
    return v


def _theme(layers: list, base: str, top: str, gate: str, v: dict) -> dict:
    return {"b": ",".join(layers + [base]), "a": top, "q": gate, "s": top, "v": v}


# ── the eight ────────────────────────────────────────────────────────────────
def _atlas():
    light = _theme(
        [_glow("ellipse at 50% 38%", "#fffaf0", .55, 70), _grain("#8a6a3a", .22)] + _lines("#7a5c34", .045, 40, .10, 160),
        _base(160, "#f4ecd9", "#e9ddc2"), "#f4ecd9", "#f1e8d3",
        _vars("#efe6d0", "rgba(255,250,236,.38)", "rgba(122,92,52,.42)", "rgba(246,239,222,.92)", "#33291a",
              "rgba(116,150,86,.18)", "rgba(255,250,236,.50)"))
    dark = _theme(
        [_glow("ellipse at 50% 38%", "#6a5538", .22, 70), _grain("#d9bf8f", .12)] + _lines("#e6cfa6", .035, 40, .075, 160),
        _base(160, "#2b251c", "#1d1912"), "#2b251c", "#241f17",
        _vars("#2a241b", "rgba(24,19,12,.40)", "rgba(230,207,166,.20)", "rgba(28,23,15,.90)", "#eadfc8",
              "rgba(150,185,110,.10)", "rgba(230,207,166,.10)"))
    return light, dark


def _blueprint():
    light = _theme(
        _lines("#2f6db3", .075, 20, .16, 100),
        _base(160, "#e8f2fc", "#d4e5f6"), "#e8f2fc", "#dfecf9",
        _vars("#dde9f7", "rgba(255,255,255,.34)", "rgba(47,109,179,.40)", "rgba(236,244,253,.92)", "#17314f",
              "rgba(255,255,255,.22)", "rgba(255,255,255,.46)"))
    dark = _theme(
        _lines("#cfe4ff", .07, 20, .15, 100),
        _base(160, "#16396c", "#0e264a"), "#16396c", "#122f58",
        _vars("#14315d", "rgba(255,255,255,.05)", "rgba(190,215,255,.30)", "rgba(14,38,74,.90)", "#e6eefb",
              "rgba(255,255,255,.07)", "rgba(255,255,255,.11)",
              **{"--pal-river": "#7fb2ee", "--pal-water": "rgba(86,137,201,.88)", "--pal-water-edge": "rgba(210,228,255,.40)"}))
    return light, dark


def _dusk():
    light = _theme(
        [_glow("ellipse at 50% 108%", "#ffd9c4", .50, 60), _glow("ellipse at 50% -10%", "#ffffff", .45, 55)],
        _base(180, "#efe6f2", "#e3e1f2 55%", "#f2e3e6"), "#efe6f2", "#e8e2f1",
        _vars("#e8e3f2", "rgba(255,255,255,.34)", "rgba(255,255,255,.72)", "rgba(244,239,248,.92)", "#2d2c40",
              "rgba(255,255,255,.22)", "rgba(255,255,255,.42)"))
    dark = _theme(
        [_glow("ellipse at 50% 108%", "#8a4f63", .30, 62), _glow("ellipse at 50% -10%", "#5a4c9a", .22, 55)],
        _base(180, "#29254a", "#221e3d 55%", "#33243d"), "#29254a", "#262243",
        _vars("#2a2644", "rgba(18,15,38,.38)", "rgba(255,255,255,.14)", "rgba(24,20,48,.90)", "#e8e4f2",
              "rgba(255,255,255,.07)", "rgba(255,255,255,.10)"))
    return light, dark


def _chalk():
    light = _theme(
        [_glow("ellipse at 30% 25%", "#ffffff", .30, 55), _glow("ellipse at 78% 80%", "#ffffff", .22, 50),
         _grain("#ffffff", .34, .55, 200)],
        _base(160, "#e3e8e7", "#d1d9d7"), "#e3e8e7", "#dce2e0",
        _vars("#dbe1df", "rgba(255,255,255,.30)", "rgba(255,255,255,.75)", "rgba(238,242,241,.92)", "#263130",
              "rgba(255,255,255,.22)", "rgba(255,255,255,.44)"))
    dark = _theme(
        [_glow("ellipse at 30% 25%", "#ffffff", .06, 55), _glow("ellipse at 78% 80%", "#ffffff", .05, 50),
         _grain("#e9f0ee", .14, .55, 200)],
        _base(160, "#2a3534", "#1e2726"), "#2a3534", "#243030",
        _vars("#243030", "rgba(255,255,255,.04)", "rgba(235,243,241,.22)", "rgba(30,39,38,.90)", "#e6eeec",
              "rgba(255,255,255,.07)", "rgba(255,255,255,.10)"))
    return light, dark


def _seaglass():
    light = _theme(
        [_glow("circle at 22% 30%", "#ffffff", .38, 26), _glow("circle at 72% 62%", "#ffffff", .30, 30),
         _glow("circle at 48% 90%", "#ffffff", .26, 22), _glow("circle at 90% 16%", "#ffffff", .24, 20)],
        _base(160, "#e0f2ef", "#c5e5e0"), "#e0f2ef", "#d6ece8",
        _vars("#d4ebe7", "rgba(255,255,255,.32)", "rgba(255,255,255,.75)", "rgba(237,248,246,.92)", "#173633",
              "rgba(255,255,255,.22)", "rgba(255,255,255,.44)"))
    dark = _theme(
        [_glow("circle at 22% 30%", "#7fe0d4", .10, 26), _glow("circle at 72% 62%", "#7fe0d4", .08, 30),
         _glow("circle at 48% 90%", "#7fe0d4", .07, 22), _glow("circle at 90% 16%", "#7fe0d4", .06, 20)],
        _base(160, "#0f3d3f", "#0a2b2d"), "#0f3d3f", "#0d3436",
        _vars("#0e3638", "rgba(6,28,30,.38)", "rgba(180,240,232,.20)", "rgba(9,40,42,.90)", "#def3f0",
              "rgba(255,255,255,.07)", "rgba(255,255,255,.10)",
              **{"--pal-river": "#4d92c8", "--pal-water": "rgba(52,108,150,.90)"}))
    return light, dark


def _weave(ink: str, a: float) -> list:
    i = _rgba(ink, a)
    return [f"repeating-linear-gradient(0deg,{i} 0,{i} 1px,transparent 1px,transparent 3px)",
            f"repeating-linear-gradient(90deg,{i} 0,{i} 1px,transparent 1px,transparent 3px)"]


def _linen():
    light = _theme(
        _weave("#826946", .055) + [_glow("ellipse at 50% 40%", "#fffaf0", .40, 70)],
        _base(160, "#f1eadd", "#e6dcc8"), "#f1eadd", "#ece3d2",
        _vars("#ebe2d0", "rgba(255,252,244,.36)", "rgba(130,105,70,.32)", "rgba(246,241,229,.92)", "#33291c",
              "rgba(116,150,86,.16)", "rgba(255,252,244,.50)"))
    dark = _theme(
        _weave("#e8d9bb", .045) + [_glow("ellipse at 50% 40%", "#6a5a42", .16, 70)],
        _base(160, "#2d2a25", "#201e1a"), "#2d2a25", "#262420",
        _vars("#282622", "rgba(20,18,14,.40)", "rgba(232,217,187,.18)", "rgba(30,28,24,.90)", "#ece3d0",
              "rgba(150,185,110,.10)", "rgba(232,217,187,.10)"))
    return light, dark


def _midnight():
    light = _theme(
        [_lights(["#4a5fb0", "#6a55c8"], .26, 24), _glow("ellipse at 50% 112%", "#ffffff", .45, 60)],
        _base(180, "#e5e9f4", "#ced5ea"), "#e5e9f4", "#dce1f1",
        _vars("#d9deee", "rgba(255,255,255,.32)", "rgba(255,255,255,.72)", "rgba(238,241,250,.92)", "#1d2540",
              "rgba(255,255,255,.22)", "rgba(255,255,255,.44)"))
    dark = _theme(
        [_lights(["#ffd98a", "#ffe9b8", "#8fb3ff"], .34, 30), _glow("ellipse at 50% 112%", "#ffbe6e", .12, 62)],
        _base(180, "#0f1529", "#070a17"), "#0f1529", "#0a0f20",
        _vars("#0b1022", "rgba(8,11,26,.36)", "rgba(200,215,255,.16)", "rgba(8,12,28,.90)", "#e6ebfa",
              "rgba(255,255,255,.06)", "rgba(255,255,255,.09)",
              **{"--pal-river": "#3a6fae"}))
    return light, dark


def _mist():
    light = _theme(
        [_glow("ellipse at 18% 22%", "#ffffff", .75, 48), _glow("ellipse at 82% 70%", "#ffffff", .70, 52),
         _glow("ellipse at 52% 100%", "#b9c6d8", .22, 55)],
        _base(180, "#f6f8fb", "#e7ecf2"), "#f6f8fb", "#eef1f6",
        _vars("#eaeef4", "rgba(255,255,255,.40)", "rgba(255,255,255,.80)", "rgba(248,250,252,.92)", "#252b38",
              "rgba(255,255,255,.28)", "rgba(255,255,255,.50)"))
    dark = _theme(
        [_glow("ellipse at 18% 22%", "#aebfd6", .10, 48), _glow("ellipse at 82% 70%", "#aebfd6", .08, 52)],
        _base(180, "#1e232c", "#12161d"), "#1e232c", "#181c24",
        _vars("#181d25", "rgba(14,17,23,.40)", "rgba(255,255,255,.14)", "rgba(20,24,31,.90)", "#e6eaf1",
              "rgba(255,255,255,.07)", "rgba(255,255,255,.10)"))
    return light, dark


# (id, name, builder); the first is the default of every Memory Palace nobody has chosen for
PALACE_BGS = [
    ("m-atlas", "Atlas paper", _atlas),
    ("m-blueprint", "Blueprint", _blueprint),
    ("m-dusk", "Quiet dusk", _dusk),
    ("m-chalk", "Chalk slate", _chalk),
    ("m-seaglass", "Sea glass", _seaglass),
    ("m-linen", "Sand linen", _linen),
    ("m-midnight", "Midnight city", _midnight),
    ("m-mist", "Pale mist", _mist),
]
DEFAULT = PALACE_BGS[0][0]


def client_entries() -> dict:
    """Catalog entries a Memory Palace page adds to the others (backgrounds.client_catalog):
    {id: {g, k 'm', n, l, d}}."""
    out = {}
    for pid, name, build in PALACE_BGS:
        light, dark = build()
        out[pid] = {"g": GROUP, "k": "m", "n": name, "l": light, "d": dark}
    return out
