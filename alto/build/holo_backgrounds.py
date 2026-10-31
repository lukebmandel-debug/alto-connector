"""Backgrounds made for the Holographic style (holo.py): its own set, offered only while a page is in Holographic.

Luke, 2026-10-30: "For holographic style, please add some style-specific backgrounds based on blade runner and other sci-fi stuff
to the backgrounds". Each is an original scene in the genre's vocabulary (rain-soaked neon towers, amber smog, a lit grid running
to the horizon, falling signal, a targeting display, a jump to lightspeed), drawn here as SVG: no film's imagery, no photograph,
nothing to download. Like the Memory Palace's grounds (palace_backgrounds.py) each has a light and a dark version, and each theme's
entry carries
  b  the CSS background (the scene, then its base gradient)
  a  the colour of the strip behind the top bars, s the status bar's, q the colour a private page's gate paints while it opens.

The page's catalog never carries them: the hosted Holographic script adds them to the picker when the style comes on and takes
them away when it goes off (holo.py), so Classic and Retro pages are unchanged and a Holographic choice shows nothing elsewhere.

Readability: the cards, chips and bars are solid plates in Holographic, so text never sits on the scene itself; even so every scene
keeps its marks faint and its ground near the theme's own (dark under the dark theme, pale under the light), and tests/test_holo.py
holds each ground to the style's text tokens at WCAG AA.
"""
from __future__ import annotations

import math
import random
from urllib.parse import quote

GROUP = "Holographic"
W, H = 1600, 1000


def _svg(body: str, defs: str = "") -> str:
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice">'
         + (f"<defs>{defs}</defs>" if defs else "") + body + "</svg>")
    # attributes in single quotes, and only what a quoted CSS url() needs escaped (#, %, <, >, the double quote): a third the size
    return 'url("data:image/svg+xml,' + quote(s.replace('"', "'"), safe=" '=/:;,.-()!") + '")'


def _entry(svg: str, top: str, bottom: str, mid: str) -> dict:
    return {"b": f"{svg} center bottom / cover no-repeat, linear-gradient(180deg,{top},{mid} 62%,{bottom})",
            "a": top, "s": top, "q": mid}


# ── the scenes: each (light, dark) ──

def neon_rain():
    """A city of towers at night in the rain, lit windows and a magenta and cyan haze over the street."""
    def one(dark):
        R = random.Random(7)
        tower, win, rain = (("#060812", ("#4ff0e0", "#ff4fa8", "#ffb347"), "#a8d8ff") if dark
                            else ("#c3d3dc", ("#0a6f8c", "#b0306e", "#9a5a10"), "#2a5a70"))
        defs = (f'<radialGradient id="m" cx=".22" cy=".86" r=".5"><stop offset="0" stop-color="#ff3fa0" stop-opacity="{.32 if dark else .12}"/>'
                '<stop offset="1" stop-color="#ff3fa0" stop-opacity="0"/></radialGradient>'
                f'<radialGradient id="c" cx=".8" cy=".8" r=".55"><stop offset="0" stop-color="#2fe6ff" stop-opacity="{.26 if dark else .12}"/>'
                '<stop offset="1" stop-color="#2fe6ff" stop-opacity="0"/></radialGradient>')
        out = ['<rect width="1600" height="1000" fill="url(#m)"/><rect width="1600" height="1000" fill="url(#c)"/>']
        for depth, op in ((0, .55), (1, 1)):                      # a far row, paler, then the near one
            x = -20
            while x < W:
                w = R.randint(40, 110)
                h = R.randint(220, 520) if depth == 0 else R.randint(140, 430)
                y = H - h
                out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{tower}" fill-opacity="{op if dark else op * .55:.2f}"/>')
                if depth == 1:
                    for _ in range(R.randint(2, 6)):
                        c = R.choice(win)
                        out.append(f'<rect x="{x + R.randint(4, w - 8)}" y="{y + R.randint(8, h - 10)}" width="3" height="5" fill="{c}" '
                                   f'fill-opacity="{R.uniform(.35, .8) if dark else R.uniform(.2, .4):.2f}"/>')
                    if R.random() < .12:                           # a tall sign down the side of a tower
                        c = R.choice(win[:2])
                        out.append(f'<rect x="{x + 3}" y="{y + 20}" width="5" height="{min(140, h - 40)}" fill="{c}" fill-opacity="{.55 if dark else .25}"/>')
                x += w + R.randint(-6, 14)
        d = "".join(f"M{R.randint(0, W)} {R.randint(-60, H)}l-14 {R.randint(40, 90)}" for _ in range(140))
        out.append(f'<path d="{d}" stroke="{rain}" stroke-opacity="{.16 if dark else .14}" stroke-width="1"/>')
        top, mid, bot = ("#04050c", "#0a0c1c", "#160b1e") if dark else ("#eef4f8", "#e3edf3", "#e9e3ee")
        return _entry(_svg("".join(out), defs), top, bot, mid)
    return one(False), one(True)


def amber_haze():
    """Towers in an orange dust storm: layered silhouettes fading into the haze, a low sun behind them."""
    def one(dark):
        R = random.Random(11)
        sil = "#2a1206" if dark else "#c99a6c"
        defs = (f'<radialGradient id="s" cx=".62" cy=".62" r=".35"><stop offset="0" stop-color="{"#ffb15a" if dark else "#fff3df"}" stop-opacity="{.55 if dark else .9}"/>'
                '<stop offset="1" stop-color="#ff9a3c" stop-opacity="0"/></radialGradient>')
        out = ['<rect width="1600" height="1000" fill="url(#s)"/>']
        for layer, op in enumerate((.18, .32, .55)):
            x = R.randint(-200, 0)
            while x < W:
                w = R.randint(90, 240)
                h = R.randint(160, 420) + layer * 60
                taper = R.randint(6, 30)
                out.append(f'<path d="M{x} {H}L{x + taper} {H - h}H{x + w - taper}L{x + w} {H}Z" fill="{sil}" fill-opacity="{op if dark else op * .6:.2f}"/>')
                x += w + R.randint(60, 260)
        dust = "".join(f'<circle cx="{R.randint(0, W)}" cy="{R.randint(0, H)}" r="{R.uniform(.6, 1.8):.1f}"/>' for _ in range(120))
        out.append(f'<g fill="{"#ffcf99" if dark else "#8a5a2a"}" fill-opacity="{.25 if dark else .18}">{dust}</g>')
        top, mid, bot = ("#140803", "#2a1306", "#3a1a08") if dark else ("#fcf3e8", "#f8e6cf", "#f6e2c8")
        return _entry(_svg("".join(out), defs), top, bot, mid)
    return one(False), one(True)


def grid_horizon():
    """A lit floor grid running away to a glowing horizon, stars above it."""
    def one(dark):
        R = random.Random(3)
        ink = "#4ff0e0" if dark else "#0a6f8c"
        hz, vx = 600, 800
        defs = (f'<linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{"#ff4fd8" if dark else "#d06aa8"}" stop-opacity="0"/>'
                f'<stop offset="1" stop-color="{"#ff4fd8" if dark else "#d06aa8"}" stop-opacity="{.35 if dark else .18}"/></linearGradient>')
        out = [f'<rect y="{hz - 220}" width="1600" height="220" fill="url(#g)"/>',
               f'<path d="M0 {hz}H1600" stroke="{ink}" stroke-opacity="{.8 if dark else .5}" stroke-width="2"/>']
        d = "".join(f"M{vx} {hz}L{vx + (i * 140)} {H + 40}" for i in range(-14, 15))
        y, step = hz, 6.0
        while y < H:
            y += step
            step *= 1.28
            d += f"M0 {y:.0f}H1600"
        out.append(f'<path d="{d}" stroke="{ink}" stroke-opacity="{.32 if dark else .22}" stroke-width="1.2" fill="none"/>')
        stars = "".join(f'<circle cx="{R.randint(0, W)}" cy="{R.randint(0, hz - 60)}" r="{R.uniform(.5, 1.5):.1f}"/>' for _ in range(110))
        out.append(f'<g fill="{"#e6fffb" if dark else "#3a6a80"}" fill-opacity="{.6 if dark else .3}">{stars}</g>')
        top, mid, bot = ("#03040d", "#0b0a24", "#04121a") if dark else ("#f1f7fc", "#ece9f6", "#e6f4f8")
        return _entry(_svg("".join(out), defs), top, bot, mid)
    return one(False), one(True)


def signal_rain():
    """Columns of signal falling down the screen, brightest at the head of each stream."""
    def one(dark):
        R = random.Random(5)
        ink = "#4ff0e0" if dark else "#0a6f8c"
        defs = ('<linearGradient id="f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".15"/>'
                '<stop offset=".7" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity=".3"/></linearGradient>'
                '<mask id="k"><rect width="1600" height="1000" fill="url(#f)"/></mask>')
        cols = []
        for x in range(12, W, 26):
            if R.random() < .35:
                continue
            y0 = R.randint(-200, 500)
            ln = R.randint(180, 620)
            dash = f"{R.randint(4, 9)} {R.randint(5, 12)}"
            cols.append(f'<path d="M{x} {y0}v{ln}" stroke-dasharray="{dash}" stroke-opacity="{R.uniform(.15, .55) if dark else R.uniform(.1, .3):.2f}"/>')
            cols.append(f'<rect x="{x - 2}" y="{y0 + ln}" width="4" height="6" fill="{ink}" fill-opacity="{.9 if dark else .45}"/>')
        out = f'<g mask="url(#k)" stroke="{ink}" stroke-width="3">{"".join(cols)}</g>'
        top, mid, bot = ("#010806", "#03110f", "#021a17") if dark else ("#f2fbf9", "#e8f6f3", "#dff1ee")
        return _entry(_svg(out, defs), top, bot, mid)
    return one(False), one(True)


def targeting():
    """A ship's targeting display: rings with tick marks, crosshairs and arcs, off to one side."""
    def one(dark):
        ink = "#4ff0e0" if dark else "#0a6f8c"
        a = (lambda v: v) if dark else (lambda v: v * .6)
        cx, cy = 1150, 520
        out = []
        for r, op, dash in ((90, .5, ""), (170, .35, "2 10"), (260, .28, ""), (380, .2, "40 14"), (520, .14, "")):
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ink}" stroke-opacity="{a(op):.2f}"'
                       + (f' stroke-dasharray="{dash}"' if dash else "") + ' stroke-width="1.4"/>')
        ticks = ""
        for i in range(72):
            t = i * math.pi / 36
            r1, r2 = 260, 260 + (16 if i % 6 == 0 else 7)
            ticks += f"M{cx + r1 * math.cos(t):.0f} {cy + r1 * math.sin(t):.0f}L{cx + r2 * math.cos(t):.0f} {cy + r2 * math.sin(t):.0f}"
        out.append(f'<path d="{ticks}" stroke="{ink}" stroke-opacity="{a(.4):.2f}" stroke-width="1.2"/>')
        out.append(f'<path d="M{cx - 600} {cy}H{cx - 110}M{cx + 110} {cy}H{cx + 600}M{cx} {cy - 560}V{cy - 110}M{cx} {cy + 110}V{cy + 560}" '
                   f'stroke="{ink}" stroke-opacity="{a(.3):.2f}" stroke-width="1"/>')
        for r, s, e in ((330, -.5, .4), (450, 2.4, 3.3), (600, 3.9, 4.4)):
            out.append(f'<path d="M{cx + r * math.cos(s):.0f} {cy + r * math.sin(s):.0f}A{r} {r} 0 0 1 {cx + r * math.cos(e):.0f} {cy + r * math.sin(e):.0f}" '
                       f'fill="none" stroke="{ink}" stroke-opacity="{a(.5):.2f}" stroke-width="3"/>')
        out.append(f'<path d="M{cx - 30} {cy - 30}h18M{cx - 30} {cy - 30}v18M{cx + 30} {cy + 30}h-18M{cx + 30} {cy + 30}v-18" '
                   f'stroke="{ink}" stroke-opacity="{a(.8):.2f}" stroke-width="2" fill="none"/>')
        top, mid, bot = ("#020a0e", "#03141a", "#020c10") if dark else ("#f0f9fb", "#e7f4f7", "#eef8fa")
        return _entry(_svg("".join(out)), top, bot, mid)
    return one(False), one(True)


def lightspeed():
    """The jump: stars stretched into streaks running out from the middle."""
    def one(dark):
        R = random.Random(9)
        ink = "#dffcff" if dark else "#1f5a74"
        cx, cy = 800, 500
        d = ""
        for _ in range(220):
            t = R.uniform(0, 2 * math.pi)
            r0 = R.uniform(60, 520)
            ln = r0 * R.uniform(.25, .8)
            d += (f"M{cx + r0 * math.cos(t):.0f} {cy + r0 * math.sin(t):.0f}"
                  f"L{cx + (r0 + ln) * math.cos(t):.0f} {cy + (r0 + ln) * math.sin(t):.0f}")
        defs = (f'<radialGradient id="o" cx=".5" cy=".5" r=".6"><stop offset="0" stop-color="{"#7fdcff" if dark else "#ffffff"}" stop-opacity="{.3 if dark else .8}"/>'
                '<stop offset="1" stop-color="#7fdcff" stop-opacity="0"/></radialGradient>')
        out = (f'<rect width="1600" height="1000" fill="url(#o)"/>'
               f'<path d="{d}" stroke="{ink}" stroke-opacity="{.4 if dark else .3}" stroke-width="1.3" stroke-linecap="round"/>')
        top, mid, bot = ("#02030a", "#060a1c", "#02030a") if dark else ("#eef3fb", "#f6f9fe", "#eef3fb")
        return _entry(_svg(out, defs), top, bot, mid)
    return one(False), one(True)


HOLO_BGS = [
    ("h-neon-rain", "Neon rain", neon_rain),
    ("h-amber-haze", "Amber haze", amber_haze),
    ("h-grid-horizon", "Grid horizon", grid_horizon),
    ("h-signal-rain", "Signal rain", signal_rain),
    ("h-targeting", "Targeting", targeting),
    ("h-lightspeed", "Lightspeed", lightspeed),
]


def client_entries() -> dict:
    """Catalog entries the Holographic script adds while the style is on: {id: {g, k 'h', n, l, d}}."""
    out = {}
    for hid, name, build in HOLO_BGS:
        light, dark = build()
        out[hid] = {"g": GROUP, "k": "h", "n": name, "l": light, "d": dark}
    return out
