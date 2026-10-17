"""Real-geometry ride, phase 0: the page <-> real-px map (alto/build/palace_ride_real.py) round-trips on Philadelphia's real domains."""
import json, math, random
from pathlib import Path

from alto.build.palace_ride_real import RealMap
from alto.build import palace_fillin as pf

FX = Path(__file__).parent / "fixtures" / "philly_doms_2000.json"


def _rm():
    return RealMap(json.loads(FX.read_text()))


def _near_edge(ring, x, y, tol):
    if not ring:
        return 1e9
    best = 1e9
    for i in range(len(ring)):
        (ax, ay), (bx, by) = ring[i], ring[(i + 1) % len(ring)]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1
        t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(ax + t * dx - x, ay + t * dy - y))
    return best


def test_roundtrip_real_page_real():
    rm = _rm()
    rnd = random.Random(7)
    n = bad = 0
    worst = 0.0
    for d in rm.doms:
        if not d.poly:
            continue
        xs, ys = [p[0] for p in d.poly], [p[1] for p in d.poly]
        for _ in range(400):
            x, y = rnd.uniform(min(xs), max(xs)), rnd.uniform(min(ys), max(ys))
            if not pf._in_ring(d.poly, x, y) or rm.by_real(x, y) is not d:
                continue
            X, Y, k = rm.to_page(x, y)
            if k != d.k:
                continue
            # away from seams: the page point must still be owned by the same domain on the way back
            if rm.by_page(X, Y) is not d or (d.clip and _near_edge(d.clip, X, Y, 1) < 30) or _near_edge(d.poly, x, y, 1) < 30:
                continue
            x2, y2, _ = rm.to_real(X, Y)
            err = math.hypot(x2 - x, y2 - y)
            worst = max(worst, err)
            n += 1
            bad += err >= 0.5
    assert n > 300, n
    assert bad == 0, (bad, n, worst)


def test_roundtrip_page_real_page():
    rm = _rm()
    rnd = random.Random(3)
    n = 0
    for _ in range(3000):
        X, Y = rnd.uniform(0, 27000), rnd.uniform(0, 26000)
        x, y, k = rm.to_real(X, Y)
        X2, Y2, k2 = rm.to_page(x, y)
        if k2 != k or math.hypot(X2 - X, Y2 - Y) > 40 and _near_edge(rm.doms[k].clip or [], X, Y, 1) < 60:
            continue
        if k2 == k:
            assert math.hypot(X2 - X, Y2 - Y) < 0.5, (X, Y, X2, Y2, k)
            n += 1
    assert n > 500
