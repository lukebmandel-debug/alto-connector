"""Holographic backgrounds 7-11 (Luke, 2026-11-17, "1,2,3,6,7 are good" from Art's round-2 sheet): Rooftop aurora, Docking bay, Jade alley, Dune beacon, Sky tether.
Same delivery as holo_backgrounds.py (one inline SVG as a data-URI CSS background over a base gradient), but each scene is built in depth (far/mid/near layers, one light source with
a bloom, fog and a light grain). Holographic is always dark, so each entry is a (light, dark) pair whose light half is only the plain light ground (no picture, nothing to carry twice).
Each one's 12 s motion is made as a video loop (docs/holo-video/render_frames.py) and played by holo_anim.py, like the first six."""
from __future__ import annotations

import math
import random

from .holo_backgrounds import W, H, _entry, _svg

LIGHT = ("#f1f7fc", "#e6f4f8", "#ece9f6")      # top, bottom, middle: the existing light grounds


def _pair(body: str, defs: str, top: str, bot: str, mid: str):
    return _entry("none", *LIGHT) | {"b": f"linear-gradient(180deg,{LIGHT[0]},{LIGHT[2]} 62%,{LIGHT[1]})"}, _entry(_svg(body, defs), top, bot, mid)


def _st(ss): return "".join(f'<stop offset="{o}" stop-color="{c}"' + ("" if a == 1 else f' stop-opacity="{a}"') + "/>" for o, c, a in ss)
def LG(i, ss, x1=0, y1=0, x2=0, y2=1, user=False):
    return f'<linearGradient id="{i}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"' + (' gradientUnits="userSpaceOnUse"' if user else "") + f">{_st(ss)}</linearGradient>"
def RG(i, ss, cx=None, cy=None, r=None):
    if cx is None: return f'<radialGradient id="{i}">{_st(ss)}</radialGradient>'      # object box: an ellipse gets an elliptical glow
    return f'<radialGradient id="{i}" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">{_st(ss)}</radialGradient>'
def BL(i, s): return f'<filter id="{i}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{s}"/></filter>'
def FOG(i, bf, octv, rgb, gain, bias, seed=1):
    r, g, b = (int(rgb[k:k + 2], 16) / 255 for k in (1, 3, 5))
    return (f'<filter id="{i}" x="0" y="0" width="1" height="1"><feTurbulence type="fractalNoise" baseFrequency="{bf}" numOctaves="{octv}" seed="{seed}"/>'
            f'<feColorMatrix values="0 0 0 0 {r:.2f} 0 0 0 0 {g:.2f} 0 0 0 0 {b:.2f} {gain} 0 0 0 {bias}"/></filter>')
GRAIN_D = ('<filter id="gr" x="0" y="0" width="1" height="1"><feTurbulence type="fractalNoise" baseFrequency="1.3" numOctaves="1" seed="5"/>'
           '<feColorMatrix values="0 0 0 0 .8 0 0 0 0 .95 0 0 0 0 1 1.2 0 0 0 -.5"/></filter>')
GRAIN = f'<rect width="{W}" height="{H}" filter="url(#gr)" opacity=".15"/>'
def R_(i="", **k): return f'<rect width="{W}" height="{H}" ' + " ".join(f'{a.replace("_", "-")}="{v}"' for a, v in k.items()) + "/>"
def dots(pts, col, w, op=1, cap="round"):
    if not pts: return ""
    return f'<path d="{"".join(f"M{x:.0f} {y:.0f}h0" for x, y in pts)}" stroke="{col}" stroke-width="{w}" stroke-linecap="{cap}" stroke-opacity="{op}"/>'
def stars(R, n, ymax, col="#dff6ff", xr=(0, W)):
    out = ""
    for w, op, k in ((1.3, .5, .6), (2, .65, .32), (2.6, .75, .08)):
        out += dots([(R.uniform(*xr), ymax * R.random() ** 1.5) for _ in range(int(n * k))], col, w, op)
    return out
def mix(a, b, t):
    A = [int(a[k:k + 2], 16) for k in (1, 3, 5)]; B = [int(b[k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(A, B))
def P(pts): return "M" + "L".join(f"{x:.0f} {y:.0f}" for x, y in pts) + "Z"



def rooftop_aurora():
    """From a rooftop at night: an aurora in rays over a hazy skyline, the city's own glow on the horizon."""
    R = random.Random(3)
    defs = (LG("s", [(0, "#01040d", 1), (.5, "#04132a", 1), (.8, "#0a3340", 1)]) + BL("b", 16) + BL("b2", 5) + GRAIN_D +
            LG("a1", [(0, "#8a5cff", 0), (.45, "#7a6cff", .32), (.8, "#49ffb0", .6), (1, "#b8ffd8", .7)], 0, 0, 0, 480, True) +
            LG("a2", [(0, "#ff5fd0", 0), (.7, "#c05cff", .4), (1, "#5fd0ff", .45)], 0, 0, 0, 300, True) +
            '<filter id="af" x="0" y="0" width="1" height="1"><feTurbulence type="fractalNoise" baseFrequency=".011 .0002" numOctaves="2" seed="8"/>'
            '<feColorMatrix values="1.5 0 0 0 -.2 1.5 0 0 0 -.2 1.5 0 0 0 -.2 0 0 0 0 1"/></filter>'
            f'<mask id="am"><rect width="{W}" height="640" filter="url(#af)"/></mask>' +
            RG("cg", [(0, "#b8ffe4", .7), (.4, "#2fb0a0", .3), (1, "#2fb0a0", 0)]) +
            LG("hz", [(0, "#1c6a70", 0), (1, "#2a8a86", .5)]) + RG("rd", [(0, "#ff5a4a", .9), (1, "#ff5a4a", 0)]))
    o = [R_(fill="url(#s)"), stars(R, 170, 620)]
    def band(y0, amp, ph, thick):
        top = [(x, y0 + amp * math.sin(x / 250 + ph) + amp * .35 * math.sin(x / 83 + ph * 2) + x * .1) for x in range(-60, W + 100, 40)]
        edge = "M" + "L".join(f"{x} {y:.0f}" for x, y in top)
        return edge, edge + f"L{W + 60} {top[-1][1] - thick:.0f}L" + "L".join(f"{x} {y - thick:.0f}" for x, y in reversed(top)) + "Z"
    e2, f2 = band(170, 40, 2.4, 230); e1, f1 = band(290, 55, 1, 340)
    o.append(f'<g mask="url(#am)"><path d="{f2}" fill="url(#a2)" filter="url(#b)" opacity=".7"/><path d="{f1}" fill="url(#a1)" filter="url(#b)"/>'
             f'<path d="{e1}" fill="none" stroke="#c8ffe0" stroke-width="7" stroke-opacity=".55" filter="url(#b2)"/></g>')
    o.append(f'<path d="{f1}" fill="#3dffb0" opacity=".12" filter="url(#b)"/><ellipse cx="1150" cy="380" rx="800" ry="300" fill="url(#cg)" opacity=".3"/>')                 # the soft body the rays sit in
    o.append('<ellipse cx="800" cy="830" rx="1000" ry="300" fill="url(#cg)"/>')
    def skyline(base, hmin, hmax, col, wmin, wmax, win):
        d, pts, x = "", [], -20
        while x < W:
            w = R.randint(wmin, wmax); h = R.randint(hmin, hmax) * (1.5 if R.random() < .12 else 1); y = base - h
            d += f"M{x} {H}V{y:.0f}h{w}V{H}"
            if R.random() < .4: d += f"M{x + w * .25:.0f} {y:.0f}v-{R.randint(8, 26)}h{w * .5:.0f}V{y:.0f}"
            if R.random() < .22: d += f"M{x + w // 2} {y:.0f}v-{R.randint(30, 80)}h2V{y:.0f}"
            for _ in range(int(win * w * h / 2600)): pts.append((x + R.randint(3, w - 3), y + R.randint(6, int(h))))
            x += w + R.randint(-4, 10)
        return f'<path d="{d}" fill="{col}"/>', pts
    for base, hmin, hmax, col, wmin, wmax, win in ((800, 40, 150, "#0f3d4a", 22, 60, 0), (830, 50, 190, "#092a36", 30, 80, .5), (870, 40, 170, "#04161e", 44, 110, 1)):
        s, pts = skyline(base, hmin, hmax, col, wmin, wmax, win)
        o.append(s)
        o.append(dots(pts[::2], "#ffc978", 2.6, .85, "square") + dots(pts[1::3], "#7ff5e6", 2.6, .7, "square"))
        o.append(f'<rect y="{base - 150}" width="{W}" height="170" fill="url(#hz)" opacity=".55"/>')
    # the roof we stand on: parapet, water tank, vents, a mast with its red lamp
    roof = ("M0 1000V930H1600V1000Z" "M110 930V900h12v-50h-8v-74l52-22 52 22v74h-8v50h12v30Z" "M330 930v-34h90v34Z" "M352 896v-14h46v14Z"
            "M1180 930v-26h120v26Z" "M1392 930V610h4V930Z" "M1370 700h48v3h-48Z" "M1378 660h32v3h-32Z" "M1470 930v-60h3v60Z" "M1452 872a20 20 0 0 1 40 0Z")
    o.append(f'<path d="{roof}" fill="#010507"/><path d="M0 930H1600M114 776l52-22 52 22" fill="none" stroke="#5fffd0" stroke-opacity=".3" stroke-width="1.5"/>')
    o.append('<circle cx="1394" cy="606" r="34" fill="url(#rd)"/><circle cx="1394" cy="606" r="3" fill="#ffb0a0"/>')
    o.append(GRAIN)
    return _pair("".join(o), defs, "#01040d", "#010507", "#04132a")


def docking_bay():
    """Inside a starship hangar: ribbed frames running to an open bay door, a planet's light flooding in, guide lights on the deck."""
    R = random.Random(5)
    cx, cy = 800, 655
    def frame(s):
        a, u, d, c = 1000 * s, 560 * s, 330 * s, 190 * s
        return [(cx - a + c, cy - u), (cx + a - c, cy - u), (cx + a, cy - u + c), (cx + a, cy + d - c * .5), (cx + a - c * .5, cy + d),
                (cx - a + c * .5, cy + d), (cx - a, cy + d - c * .5), (cx - a, cy - u + c)]
    S = [1.55 * .74 ** k for k in range(8)]
    far = frame(S[-1])
    defs = (BL("b", 22) + BL("b2", 4) + GRAIN_D + LG("sp", [(0, "#020814", 1), (.5, "#0a3550", 1), (.8, "#8fefff", 1), (1, "#f2ffff", 1)]) +
            RG("bm", [(0, "#eaffff", .95), (.12, "#8ff3ff", .6), (.4, "#2fb6d0", .2), (1, "#2fb6d0", 0)], cx, cy + 20, 560) +
            RG("fl", [(0, "#dffcff", .7), (.4, "#4fd8e8", .22), (1, "#4fd8e8", 0)]) + RG("am", [(0, "#ffb347", .8), (1, "#ffb347", 0)]) +
            FOG("fg", ".004 .009", 3, "#7fe0f0", 1.3, -.5, 4) + RG("fm", [(0, "#fff", .9), (1, "#fff", 0)], cx, cy, 620) +
            f'<mask id="m"><rect width="{W}" height="{H}" fill="url(#fm)"/></mask><clipPath id="op"><path d="{P(far)}"/></clipPath>')
    o = [R_(fill="#061c24")]
    # through the door: space, and the lit limb of a planet below
    o.append(f'<g clip-path="url(#op)"><rect x="{far[0][0] - 60:.0f}" y="{far[0][1]:.0f}" width="{far[1][0] - far[0][0] + 120:.0f}" height="{far[4][1] - far[0][1]:.0f}" fill="url(#sp)"/>'
             + stars(R, 26, 60, xr=(far[7][0], far[2][0])).replace('d="M', f'transform="translate(0 {far[0][1]:.0f})" d="M') +
             f'<circle cx="{cx - 40}" cy="{cy + 560}" r="520" fill="#03101a"/><circle cx="{cx - 40}" cy="{cy + 560}" r="520" fill="none" stroke="#fff" stroke-width="3" filter="url(#b2)"/></g>')
    n = len(S)
    for k in range(n - 2, -1, -1):                                 # far to near: each bay's skin, then its rib
        t = k / (n - 1)
        o.append(f'<path fill-rule="evenodd" d="{P(frame(S[k]))}{P(frame(S[k + 1]))}" fill="{mix("#0e3d4a", "#010608", (1 - t) ** .8)}"/>')
    f0 = frame(S[0])
    o.append('<path d="' + "".join(f"M{a[0]:.0f} {a[1]:.0f}L{b[0]:.0f} {b[1]:.0f}" for a, b in zip(f0, far)) + '" stroke="#5fe6f0" stroke-opacity=".16" stroke-width="1.5"/>')
    for k in range(n - 1, -1, -1):
        s, t = S[k], k / (n - 1)
        o.append(f'<path d="{P(frame(s))}" fill="none" stroke="{mix("#04121a", "#1b5a68", t ** 1.5)}" stroke-width="{52 * s:.0f}" stroke-linejoin="round"/>'
                 f'<path d="{P(frame(s * .962))}" fill="none" stroke="#a8fbff" stroke-opacity="{.12 + .5 * t ** 2:.2f}" stroke-width="{max(1, 3 * s):.1f}"/>')
    # the deck: sheen, guide lights, centre line
    o.append(f'<ellipse cx="{cx}" cy="{cy + 250}" rx="330" ry="330" fill="url(#fl)"/>')
    amber, glow, strip = [], [], ""
    for k in range(n - 1):
        for f in (0, .5):
            s = S[k] + (S[k + 1] - S[k]) * f
            if cy + 330 * s > H + 40: continue
            for sg in (-1, 1):
                x, y = cx + sg * 430 * s, cy + 330 * s - 6 * s
                o.append(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{34 * s:.0f}" ry="{12 * s:.0f}" fill="url(#am)"/><ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{6 * s:.1f}" ry="{2.6 * s:.1f}" fill="#fff1c8"/>')
        a, b = S[k] * .93, S[k + 1] * 1.08                           # strip lights in the upper corners
        for sg in (-1, 1):
            strip += f"M{cx + sg * 810 * a:.0f} {cy - 560 * a:.0f}L{cx + sg * 810 * b:.0f} {cy - 560 * b:.0f}"
        o.append(f'<path d="M{cx} {cy + 330 * a:.0f}V{cy + 330 * (a + b) / 2:.0f}" stroke="#7ff5ff" stroke-opacity=".5" stroke-width="{max(1, 4 * a):.1f}"/>')
    o.append(f'<path d="{strip}" stroke="#bff8ff" stroke-width="9" stroke-opacity=".5" filter="url(#b2)"/><path d="{strip}" stroke="#eaffff" stroke-width="2" stroke-opacity=".8"/>')
    # light pouring in: rays, haze, bloom; two crew and a shuttle against it for scale
    rays = "".join(f"M{cx + dx} {cy}L{cx + ex - 90} {ey}L{cx + ex + 90} {ey}Z" for dx, ex, ey in ((-90, -820, 1000), (-30, -260, 1000), (40, 330, 1000), (100, 900, 1000), (-120, -900, 300), (120, 900, 250)))
    o.append(f'<path d="{rays}" fill="#bff8ff" opacity=".06" filter="url(#b)"/>')
    o.append(f'<g mask="url(#m)"><rect width="{W}" height="{H}" filter="url(#fg)" opacity=".5"/></g>' + R_(fill="url(#bm)"))
    gy = cy + 330 * S[-1] + 4
    o.append(f'<path d="M{cx - 112} {gy:.0f}l6 -9 44 -9 30 4 12 9 -8 3 -4 6h-4l-2 -5h-52l-2 5h-4l-2 -5ZM{cx + 64} {gy + 5:.0f}v-11h3v11ZM{cx + 78} {gy + 6:.0f}v-12h3v12Z" fill="#01080c"/>'
             f'<circle cx="{cx + 65.5}" cy="{gy - 8:.0f}" r="2" fill="#01080c"/><circle cx="{cx + 79.5}" cy="{gy - 8:.0f}" r="2" fill="#01080c"/>')
    o.append(GRAIN)
    return _pair("".join(o), defs, "#02090d", "#02090d", "#061c24")


def jade_alley():
    """Street level in a narrow alley after rain: jade and gold signs in the mist, their light running down the wet road."""
    R = random.Random(12)
    vy = 720
    defs = (BL("b", 18) + BL("b2", 3) + BL("rb", "3 26") + GRAIN_D + LG("s", [(0, "#020a09", 1), (.45, "#0a2d27", 1), (.72, "#3f9a80", 1)]) +
            RG("vg", [(0, "#d8ffe8", .85), (.25, "#63e0a8", .4), (1, "#2a9a78", 0)], 800, vy - 20, 430) +
            LG("rd", [(0, "#06201b", 1), (1, "#010605", 1)], 0, vy, 0, H, True) + LG("rm", [(0, "#fff", .75), (1, "#fff", 0)], 0, vy, 0, H, True) +
            f'<mask id="m"><rect y="{vy}" width="{W}" height="{H - vy}" fill="url(#rm)"/></mask>' +
            FOG("fg", ".003 .012", 3, "#7fe8c0", 1.4, -.55, 9) + LG("fm", [(0, "#fff", 0), (.6, "#fff", .8), (1, "#fff", .1)], 0, 380, 0, 900, True) +
            f'<mask id="m2"><rect width="{W}" height="{H}" fill="url(#fm)"/></mask>' + RG("ln", [(0, "#ffd070", .9), (1, "#ffd070", 0)]) + RG("sh", [(0, "#c8ffe0", .5), (1, "#c8ffe0", 0)]))
    o = [R_(fill="url(#s)")]
    o.append(f'<path d="M742 {vy}V470h26V{vy}ZM812 {vy}V520h40V{vy}ZM776 {vy}V590h22V{vy}Z" fill="#1d6a5a" opacity=".8"/>' + R_(fill="url(#vg)"))
    # walls step in toward the far end, paler with distance
    L = [(735, 455), (665, 360), (575, 250), (455, 110), (290, -40)]
    Rt = [(880, 480), (960, 390), (1060, 270), (1190, 120), (1370, -40)]
    signs, fac = [], []
    win = {"#3dffa0": [], "#ffc24d": []}
    for k in range(5):
        t = k / 4; col = mix("#195a4c", "#030d0b", t ** .7)
        (xl, yl), (xr, yr) = L[k], Rt[k]
        pl, pr = (L[k - 1][0] if k else 760), (Rt[k - 1][0] if k else 860)
        o.append(f'<path d="M0 {H}V{yl}H{xl}V{H}ZM{W} {H}V{yr}H{xr}V{H}Z" fill="{col}"/>'
                 f'<path d="M{xl} {yl}V{H}M{xr} {yr}V{H}" stroke="#8fffd0" stroke-opacity="{.3 - .04 * k:.2f}" stroke-width="{1 + t:.1f}"/>')
        ledge = "".join(f"M{a} {y:.0f}H{b}" for a, b, y0 in ((pl + 6, xl - 3, yl), (xr + 3, pr - 6, yr)) for y in (y0 + 30 + j * (30 + 34 * t) for j in range(9)) if y < vy + 60)
        o.append(f'<path d="{ledge}" stroke="#7fe8c0" stroke-opacity=".07" stroke-width="{1 + t:.0f}"/>')
        for a, b, y0 in ((xl + 10, pl - 12, yl), (pr + 12, xr - 10, yr)):
            for _ in range(5 + k * 2):
                if b - a > 8: win[R.choice(list(win))].append((R.uniform(a, b), R.uniform(max(y0, 150) + 30, vy - 30)))
        if k < 4: o.append(f'<rect y="200" width="{W}" height="{vy - 180}" fill="#3f9a80" opacity="{.10 - .02 * k:.2f}"/>')
    o.append("".join(dots(p, c, 3, .2, "square") for c, p in win.items()))
    # signs: (x, y, w, h, colour); blades hung off the wall edges, small on the left, big and bright on the right
    SG = [(668, 566, 12, 84, "#ffc24d"), (579, 540, 20, 120, "#3dffa0"), (461, 530, 28, 140, "#3dffa0"), (296, 600, 44, 88, "#ffc24d"),
          (906, 560, 40, 16, "#3dffa0"), (964, 440, 16, 150, "#ffc24d"), (1012, 330, 34, 238, "#3dffa0"), (1118, 452, 66, 44, "#ff6a3c"), (1196, 196, 52, 364, "#ffc24d"),
          (1290, 540, 156, 66, "#3dffa0")]
    sg = ""
    def glyph(x, y, c):
        g = ""
        for _ in range(R.randint(3, 4)):
            p, q = R.choice((0, .5, 1)), R.choice((0, .5))
            ln = c * R.choice((.5, 1 - q))
            g += f"M{x + q * c:.0f} {y + p * c:.0f}h{ln:.0f}" if R.random() < .5 else f"M{x + p * c:.0f} {y + q * c:.0f}v{ln:.0f}"
        return g
    for x, y, w, h, c in SG:
        sg += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/>'
        m = min(w, h) * .2; cc = min(w, h) - 2 * m
        g = "".join(glyph(x + m, yy, cc) for yy in range(int(y + m), int(y + h - cc), int(cc + m * 1.6))) if h > w else \
            "".join(glyph(xx, y + m, cc) for xx in range(int(x + m), int(x + w - cc), int(cc + m * 1.6)))
        sg += f'<path d="{g}" stroke="#03120d" stroke-opacity=".8" stroke-width="{max(1.2, cc / 7):.1f}" fill="none"/>'
    o.append('<use href="#S" filter="url(#b)" opacity=".9"/>' + f'<g id="S">{sg}</g>')
    # overhead cables with lanterns
    cab, lan = "", ""
    for x1, y1, x2, y2, sag in ((455, 190, 1190, 240, 80), (575, 300, 1060, 330, 50), (290, 40, 1370, 90, 130)):
        cab += f"M{x1} {y1}Q{(x1 + x2) // 2} {(y1 + y2) // 2 + sag * 2} {x2} {y2}"
    o.append(f'<path d="{cab}" fill="none" stroke="#020b09" stroke-width="2.5"/>')
    for x, y, r in ((700, 372, 5), (930, 384, 5), (1010, 302, 7), (640, 262, 7)):
        lan += f'<circle cx="{x}" cy="{y}" r="{r * 6}" fill="url(#ln)"/><circle cx="{x}" cy="{y}" r="{r}" fill="#fff0c0"/>'
    o.append(lan)
    # the wet road: sign light smeared down it, a sheen from the far glow, mist over the lot
    o.append(f'<path d="M0 {vy + 92}L735 {vy}H880L{W} {vy + 92}V{H}H0Z" fill="url(#rd)"/>')
    o.append(f'<g mask="url(#m)"><use href="#S" transform="matrix(1 0 0 -1.5 0 {vy * 2.5})" filter="url(#rb)" opacity=".8"/></g>')
    o.append(f'<ellipse cx="800" cy="{vy + 110}" rx="150" ry="280" fill="url(#sh)"/>')
    o.append('<path d="' + "".join(f"M{R.randint(100, 1500)} {R.randint(vy + 40, H - 10)}h{R.randint(30, 160)}" for _ in range(26)) + '" stroke="#bfffe0" stroke-opacity=".12" stroke-width="1.5"/>')
    o.append(f'<g mask="url(#m2)"><rect width="{W}" height="{H}" filter="url(#fg)" opacity=".42"/></g>')
    rain = lambda n, a, b: "".join(f"M{R.randint(0, W)} {R.randint(-60, H)}l-{b // 9} {R.randint(a, b)}" for _ in range(n))
    o.append(f'<path d="{rain(150, 14, 30)}" stroke="#c8ffe8" stroke-opacity=".12" stroke-width="1"/><path d="{rain(40, 60, 110)}" stroke="#c8ffe8" stroke-opacity=".1" stroke-width="1.6"/>')
    o.append('<path d="M0 0H470L400 96 0 150Z" fill="#010605"/><path d="M400 96L0 150" stroke="#3dffa0" stroke-opacity=".25" stroke-width="2"/>')
    o.append(GRAIN)
    return _pair("".join(o), defs, "#020a09", "#010605", "#0a2d27")


def dune_beacon():
    """A desert under a low moon: long dunes in silver light, and far off one spaceport beacon holding a thin beam on the sky."""
    R = random.Random(17)
    mx, my = 1010, 255
    defs = (BL("b", 24) + BL("b2", 2) + BL("b3", 6) + GRAIN_D + LG("s", [(0, "#03050f", 1), (.4, "#0a1232", 1), (.7, "#26386e", 1)]) +
            RG("mh", [(0, "#dfe8ff", .55), (.12, "#aebfff", .28), (.45, "#5a70d0", .1), (1, "#5a70d0", 0)], mx, my, 620) +
            RG("mo", [(0, "#fbfdff", 1), (.8, "#e3ebff", 1), (1, "#c2d0f8", 1)], mx - 12, my - 12, 70) +
            FOG("mc", ".02 .03", 3, "#7080b8", 1.6, -.75, 2) + f'<clipPath id="mk"><circle cx="{mx}" cy="{my}" r="58"/></clipPath>' +
            FOG("cl", ".0018 .016", 4, "#a8b8f0", 1.8, -.9, 14) + LG("cm", [(0, "#fff", 0), (.5, "#fff", .9), (1, "#fff", 0)], 0, 150, 0, 600, True) + f'<mask id="m">{R_(fill="url(#cm)")}</mask>' +
            LG("hz", [(0, "#7088d8", 0), (1, "#8aa0e8", .4)]) +
            LG("d1", [(0, "#3a4f8e", 1), (1, "#141d44", 1)], 0, 700, 0, 860, True) + LG("d2", [(0, "#2b3c78", 1), (1, "#0a102c", 1)], 0, 750, 0, 960, True) +
            LG("d3", [(0, "#1c2a5c", 1), (1, "#03061a", 1)], 0, 850, 0, 1000, True) + LG("sh", [(0, "#02040f", .55), (.7, "#02040f", .1), (1, "#02040f", 0)], 1, 0, 0, 0) + LG("h2", [(0, "#8aa0e8", 0), (.5, "#8aa0e8", .22), (1, "#8aa0e8", 0)]) +
            LG("rm", [(0, "#fff", .1), (.6, "#fff", 1), (1, "#fff", .35)], 0, 0, 1, 0) + f'<mask id="r">{R_(fill="url(#rm)")}</mask>' +
            LG("bm", [(0, "#ffb090", 0), (.5, "#ff9a70", .35), (1, "#ffc8a0", .95)]) + RG("bg", [(0, "#ff8a5a", .9), (.3, "#ff6a4a", .3), (1, "#ff6a4a", 0)]))
    o = [R_(fill="url(#s)"), stars(R, 240, 640), R_(fill="url(#mh)")]
    o.append(f'<g mask="url(#m)"><rect width="{W}" height="620" filter="url(#cl)" opacity=".55"/></g>')
    o.append(f'<circle cx="{mx}" cy="{my}" r="58" fill="url(#mo)"/><g clip-path="url(#mk)"><rect x="{mx - 60}" y="{my - 60}" width="120" height="120" filter="url(#mc)" opacity=".55"/></g>')
    # far mesas, the port and its beam
    d, x = "M0 1000V700", 0
    while x < W:
        w = R.randint(60, 220); y = 700 - R.choice((0, 0, 8, 16, 30, 44)); d += f"L{x + 8} {y}H{x + w - 8}"; x += w
    o.append(f'<path d="{d}L{W} 700V1000Z" fill="#2c3f80"/><rect y="560" width="{W}" height="150" fill="url(#hz)"/>')
    bx, by = 700, 612
    o.append(f'<rect x="{bx - 5}" y="0" width="10" height="{by}" fill="url(#bm)" filter="url(#b3)" opacity=".7"/><rect x="{bx - 1}" y="0" width="2" height="{by}" fill="url(#bm)"/>')
    o.append(f'<path d="M{bx - 1.5} 700V{by}h3V700ZM{bx - 70} 700v-14a16 16 0 0 1 32 0v14ZM{bx - 30} 700v-30h14v30ZM{bx + 16} 700v-44h8v44ZM{bx + 34} 700v-20h40v20ZM{bx + 90} 700v-10a30 9 0 0 1 60 0v10ZM{bx - 120} 700v-24h3v24Z" fill="#17234f"/>')
    o.append(f'<ellipse cx="{bx}" cy="{by}" rx="70" ry="70" fill="url(#bg)"/><circle cx="{bx}" cy="{by}" r="3" fill="#ffe8d0"/>')
    o.append(dots([(bx - 54, 690), (bx - 22, 680), (bx + 44, 688), (bx + 62, 688), (bx + 120, 692)], "#ffd0a0", 2.4, .9) + dots([(bx + 20, 664), (bx - 118, 676)], "#8ffcf2", 2.4, .9))
    # three dunes: lit crest, shadowed slip face (the moon is to the right)
    D = [("d1", "M0 760C200 700 380 690 560 730S900 800 1100 745S1450 700 1600 735", "M560 730C610 780 500 830 420 1000H0V760C200 700 380 690 560 730ZM1100 745C1150 790 1060 850 1030 1000H800V780C900 800 1000 780 1100 745Z"),
         ("d2", "M0 850C250 770 500 750 700 805S1100 900 1300 825S1520 795 1600 805", "M700 805C780 860 640 930 600 1000H0V850C250 770 500 750 700 805ZM1300 825C1350 880 1270 950 1240 1000H950V890C1100 900 1200 860 1300 825Z"),
         ("d3", "M0 955C300 925 560 850 860 890S1300 990 1600 915", "M860 890C960 940 900 980 890 1000H0V955C300 925 560 850 860 890Z")]
    for g, crest, shade in D:
        o.append(f'<path d="{crest}V1000H0Z" fill="url(#{g})"/>' + "".join(f'<path d="{p}" fill="url(#sh)"/>' for p in shade.replace("ZM", "Z|M").split("|")) +
                 f'<g mask="url(#r)"><path d="{crest}" fill="none" stroke="#c8d6ff" stroke-opacity=".55" stroke-width="2.5" filter="url(#b2)"/></g>')
        if g == "d2": o.append(f'<rect y="740" width="{W}" height="200" fill="url(#h2)"/>')
    rip = "".join(f"M{860 + i * 9} {893 + i * 7}C{1010 + i * 4} {925 + i * 8} {1300 - i * 6} {993 + i * 6} {1600} {918 + i * 7}" for i in range(1, 12))
    o.append(f'<path d="{rip}" fill="none" stroke="#9fb4ff" stroke-opacity=".09" stroke-width="1.5"/>')
    o.append(GRAIN)
    return _pair("".join(o), defs, "#03050f", "#03061a", "#0a1232")


def sky_tether():
    """An orbital elevator at first light: a buttressed spire thinning to a thread that climbs through the cloud deck and out of sight."""
    R = random.Random(23)
    tx, gy = 930, 830
    defs = (BL("b", 22) + BL("b2", 2.5) + BL("rb", "2 16") + GRAIN_D +
            LG("s", [(0, "#020a12", 1), (.4, "#06303e", 1), (.68, "#2a6a6c", 1), (.8, "#c88a80", 1), (.83, "#ffc2a0", 1)]) +
            RG("sn", [(0, "#fff4e0", 1), (.1, "#ffd8a8", .8), (.35, "#ff8f88", .34), (1, "#ff8f88", 0)], tx + 40, gy + 14, 640) +
            FOG("c1", ".0022 .011", 5, "#2f7480", 2.2, -1.0, 21) + FOG("c2", ".003 .014", 5, "#ffb0a0", 2.2, -1.1, 5) + FOG("c3", ".002 .012", 4, "#7fc8c8", 2, -1.0, 33) +
            LG("m1", [(0, "#fff", 0), (.5, "#fff", 1), (1, "#fff", 0)], 0, 250, 0, 640, True) + f'<mask id="k1">{R_(fill="url(#m1)")}</mask>' +
            LG("m2", [(0, "#fff", 0), (.6, "#fff", 1), (1, "#fff", 0)], 0, 520, 0, 800, True) + f'<mask id="k2">{R_(fill="url(#m2)")}</mask>' +
            LG("m3", [(0, "#fff", 0), (.5, "#fff", .8), (1, "#fff", 0)], 0, 300, 0, 520, True) + f'<mask id="k3">{R_(fill="url(#m3)")}</mask>' +
            LG("tw", [(0, "#0f3d48", 1), (.6, "#174450", 1), (1, "#a8706c", 1)], 0, 300, 0, gy, True) + LG("th", [(0, "#bff", 0), (.3, "#bff", .5), (1, "#0f3d48", 1)], 0, 0, 0, 420, True) + RG("sr", [(0, "#fff0d8", .7), (1, "#ffc8a0", 0)]) +
            LG("wt", [(0, "#ffb89a", 1), (.25, "#7a5a68", 1), (1, "#04141a", 1)], 0, gy, 0, 960, True) + RG("gw", [(0, "#dffcff", .9), (1, "#7fe8f0", 0)]) +
            LG("rm", [(0, "#fff", .8), (1, "#fff", 0)], 0, gy, 0, 960, True) + f'<mask id="kr">{R_(fill="url(#rm)")}</mask>')
    o = [R_(fill="url(#s)"), stars(R, 150, 420), R_(fill="url(#sn)")]
    o.append(f'<g mask="url(#k1)"><rect width="{W}" height="700" filter="url(#c1)"/></g><g mask="url(#k2)"><rect width="{W}" height="{gy}" filter="url(#c2)" opacity=".8"/></g>')
    # the elevator: spire, three pairs of flying buttresses with pinnacles, ring decks, then the thread
    T = f'<path d="M{tx - 36} {gy}L{tx - 11} 540L{tx - 2.2} 300h4.4L{tx + 11} 540L{tx + 36} {gy}Z"/>'
    for dx, top, w in ((110, 640, 9), (210, 705, 7), (330, 760, 5)):
        for sg in (-1, 1):
            T += (f'<path d="M{tx + sg * dx} {gy}Q{tx + sg * dx * .96:.0f} {top} {tx + sg * 10} {top - dx * .9:.0f}" fill="none" stroke="url(#tw)" stroke-width="{w}"/>'
                  f'<path d="M{tx + sg * dx - w * .6:.0f} {gy}v-{(gy - top) * .8:.0f}l{w * .6:.0f} -{dx * .3:.0f}l{w * .6:.0f} {dx * .3:.0f}V{gy}Z"/>')
    for y, w in ((560, 30), (640, 52), (720, 80), (790, 118)):
        T += f'<path d="M{tx - w} {y}h{w * 2}l-6 7h-{w * 2 - 12}Z"/>'
    o.append(f'<g fill="url(#tw)" transform="translate({tx} {gy}) scale(.8) translate(-{tx} -{gy})">{T}</g><path d="M{tx - 1.5} 410L{tx - .5} 0h1L{tx + 1.5} 410Z" fill="url(#th)"/>')
    o.append(dots([(tx, y) for y in (760, 700, 640, 580, 520, 460, 400, 340, 270, 180, 100)], "#ffe9c8", 2.6, .9) +
             f'<ellipse cx="{tx}" cy="212" rx="26" ry="26" fill="url(#gw)"/><rect x="{tx - 2.5}" y="204" width="5" height="14" fill="#eaffff"/>'
             f'<path d="M{tx - 16} 26h32M{tx} 14v24" stroke="#eaffff" stroke-width="1.5" stroke-opacity=".8"/>')
    o.append(f'<g mask="url(#k3)"><rect width="{W}" height="700" filter="url(#c3)" opacity=".85"/></g>')
    # the plain: far hills, town lights at the foot, still water carrying the dawn and the spire
    hills = "M0 1000V822" + "".join(f"L{x} {gy - 4 - 16 * abs(math.sin(x / 190)) - 8 * math.sin(x / 61):.0f}" for x in range(0, W + 40, 40)) + "V1000Z"
    o.append(f'<path d="{hills}" fill="#143842"/>' + dots([(tx + R.gauss(0, 260), gy + R.uniform(-4, 6)) for _ in range(46)], "#ffd9a0", 2, .85))
    o.append(f'<rect y="{gy + 8}" width="{W}" height="140" fill="url(#wt)"/>'
             f'<ellipse cx="{tx + 40}" cy="{gy + 40}" rx="330" ry="80" fill="url(#sr)"/>'
             f'<g mask="url(#kr)"><rect x="{tx - 9}" y="{gy + 8}" width="18" height="130" fill="#0c2a34" filter="url(#rb)" opacity=".7"/></g>')
    o.append('<path d="' + "".join(f"M{R.randint(0, W)} {R.randint(gy + 16, 950)}h{R.randint(40, 200)}" for _ in range(22)) + '" stroke="#ffd8c0" stroke-opacity=".12"/>')
    shore = "M0 1000V930" + "".join(f"L{x} {950 - 22 * math.sin(x / 300 + 1) ** 2 - R.randint(0, 6) + (x / 1600 - .5) ** 2 * -90:.0f}" for x in range(0, W + 40, 32)) + "V1000Z"
    o.append(f'<path d="{shore}" fill="#020a0d"/>')
    o.append(GRAIN)
    return _pair("".join(o), defs, "#020a12", "#020a0d", "#06303e")


SCENES = [
    ("h-rooftop-aurora", "Rooftop aurora", rooftop_aurora),
    ("h-docking-bay", "Docking bay", docking_bay),
    ("h-jade-alley", "Jade alley", jade_alley),
    ("h-dune-beacon", "Dune beacon", dune_beacon),
    ("h-sky-tether", "Sky tether", sky_tether),
]
