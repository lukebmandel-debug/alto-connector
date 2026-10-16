"""Make the multi-city test fixtures <city>.json.gz in this folder from the scout's offline OSM cache.

    python tests/fixtures/cities/make_city_fixtures.py <scout cities folder> [city ...]

The scout folder holds load.py (load_city, place_of) and the Overpass tiles. Each fixture is the compact map of
alto.palace_map.build_map (scale 1.0, majors None), cut down to what the city engine's tests need: streets of class
k <= 4 (names, class, tunnel/bridge flags), rivers, water, rails, stations, the wide-river bank, bbox and size.
Coordinates are rounded to whole metres and water rings simplified at 4 m, so a fixture stays a few hundred kB.
Re-running it on the same cache gives the same files (no network).
"""
import gzip
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))            # the worktree: alto importable

from alto import palace_map as pm                     # noqa: E402

KEEP = ("v", "place", "bbox", "scale", "W", "H", "bank", "majors")


def _dp(pts, tol):
    if len(pts) < 3:
        return pts
    (ax, ay), (bx, by) = pts[0], pts[-1]
    L = math.hypot(bx - ax, by - ay)
    best, bi = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / L if L else math.hypot(px - ax, py - ay)
        if d > best:
            best, bi = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:bi + 1], tol)[:-1] + _dp(pts[bi:], tol)


def _r(flat):
    return [int(round(v)) for v in flat]


def compact(m):
    out = {k: m[k] for k in KEEP if k in m}
    out["streets"] = [{k: (_r(v) if k == "p" else v) for k, v in s.items()}
                      for s in m["streets"] if s.get("k", 9) <= 4]
    out["rivers"] = [{"n": r.get("n"), "p": _r(r["p"])} for r in m.get("rivers", [])]
    water = []
    for ring in m.get("water", []):
        pts = [(ring[i], ring[i + 1]) for i in range(0, len(ring) - 1, 2)]
        pts = _dp(pts, 4.0)
        if len(pts) >= 4:
            water.append(_r([v for q in pts for v in q]))
    out["water"] = water
    out["rails"] = [{k: (_r(v) if k == "p" else v) for k, v in r.items()} for r in m.get("rails", [])]
    out["stations"] = [{**s, "x": int(round(s["x"])), "y": int(round(s["y"]))} for s in m.get("stations", [])]
    return out


def main(argv):
    scout = Path(argv[0])
    sys.path.insert(0, str(scout))
    from load import load_city, place_of, CITIES   # noqa: E402
    for city in argv[1:] or CITIES:
        try:
            raw, bbox, lms = load_city(city)
        except Exception as e:                      # a city the scout could not fetch
            print(city, "skipped:", e)
            continue
        m = pm.build_map(raw, tuple(bbox), place=place_of(city), scale=1.0, majors=None, landmarks=lms)
        data = json.dumps(compact(m), separators=(",", ":"), ensure_ascii=False).encode()
        dst = HERE / ("%s.json.gz" % city)
        dst.write_bytes(gzip.compress(data, 9, mtime=0))
        print("%-13s %6d streets  %5.0f kB" % (city, len(m["streets"]), dst.stat().st_size / 1024))


if __name__ == "__main__":
    main(sys.argv[1:])
