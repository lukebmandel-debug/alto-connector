"""Helpers for the city engine tests: synthetic street grids and the multi-city fixtures (tests/fixtures/cities)."""
import gzip
import json
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures" / "cities"


def load_city(name):
    """The compact map of a fixture city (see fixtures/cities/make_city_fixtures.py), or None if absent."""
    p = FIX / ("%s.json.gz" % name)
    if not p.exists():
        return None
    return json.loads(gzip.decompress(p.read_bytes()).decode())


def _clip(p, q, rect):
    """Liang-Barsky: the part of segment pq inside rect (x0, y0, x1, y1), or None."""
    x0, y0, x1, y1 = rect
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return None
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return (p[0] + dx * t0, p[1] + dy * t0), (p[0] + dx * t1, p[1] + dy * t1)


def grid(rect, theta_deg, spacing=(100.0, 80.0), k=4, name="G", phase=0.0):
    """Streets of a straight lattice at theta (screen degrees) filling rect, each street one segment.
    Family 0 runs along theta, family 1 across it."""
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = math.hypot(x1 - x0, y1 - y0)
    th = math.radians(theta_deg)
    u = (math.cos(th), math.sin(th))
    v = (-u[1], u[0])
    out = []
    for fam, (d, n, sp) in enumerate(((u, v, spacing[0]), (v, u, spacing[1]))):
        j = -int(R / sp) - 1
        while j * sp <= R:
            o = (cx + n[0] * (j * sp + phase), cy + n[1] * (j * sp + phase))
            seg = _clip((o[0] - d[0] * R, o[1] - d[1] * R), (o[0] + d[0] * R, o[1] + d[1] * R), rect)
            if seg and math.dist(*seg) > 1:
                (ax, ay), (bx, by) = seg
                out.append({"n": "%s%d-%d" % (name, fam, j), "k": k, "p": [round(ax, 1), round(ay, 1), round(bx, 1), round(by, 1)]})
            j += 1
    return out


def irregular(rect, n=400, seed=7, k=4, length=(40, 140)):
    """Short streets at pseudo-random angles (an irregular old town)."""
    x0, y0, x1, y1 = rect
    s = seed
    out = []

    def rnd():
        nonlocal s
        s = (s * 1103515245 + 12345) % (1 << 31)
        return s / float(1 << 31)
    for i in range(n):
        x, y = x0 + rnd() * (x1 - x0), y0 + rnd() * (y1 - y0)
        a = rnd() * math.pi
        L = length[0] + rnd() * (length[1] - length[0])
        p = [x, y]
        for _ in range(3):
            a += (rnd() - .5) * 1.2
            x, y = min(x1, max(x0, x + math.cos(a) * L / 3)), min(y1, max(y0, y + math.sin(a) * L / 3))
            p += [x, y]
        out.append({"n": "I%d" % i, "k": k, "p": [round(v, 1) for v in p]})
    return out


def city(W, H, streets, water=None, rivers=None):
    return {"W": W, "H": H, "scale": 1.0, "bbox": [0.0, 0.0, H / 111000.0, W / 85000.0],
            "streets": streets, "water": water or [], "rivers": rivers or []}
