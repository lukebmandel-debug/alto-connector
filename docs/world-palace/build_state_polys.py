"""Makes alto/assets/world/a1p-USA.json.gz: the US states as filled shapes (Luke 2026-11-06: "where are state borders?" in a one-country Atlas).

No new geometry: the shapes are the faces of the planar graph made by the SAME Natural Earth 1:50m pieces the map already ships, the lower-48 coast ring
(cont-north-america) and the admin-1 border lines (a1-USA), so the flat map and the globe draw one set of borders. Each face is named by the state capital
inside it (gazetteer); Alaska and Hawaii are their own coast rings. Tier format: {"v":1,"q":50,"s":[[state name, [ring flat deltas, ...]], ...]} (rings as in the other tiers).
Run from the repo root:  python3 docs/world-palace/build_state_polys.py
"""
import collections, gzip, json, math, os, sys

sys.path.insert(0, os.getcwd())
from alto.build.world_geo import gazetteer, project  # noqa: E402

DIR = "alto/assets/world"
INLAND = {(-17450, -14955)}   # Rhode Island's north-west corner (-71.8, 42.01): three border lines meet there, 2 units from Providence Bay on this coarse coast, and must not be pulled onto it
SNAP = 200   # world units x 50: a border line's end this close to the coast ring is joined to it (3 units)
L = lambda n: json.loads(gzip.open(f"{DIR}/{n}.json.gz").read())


def dec(flat):
    x, y = flat[0], flat[1]
    o = [(x, y)]
    for i in range(2, len(flat), 2):
        x += flat[i]; y += flat[i + 1]; o.append((x, y))
    return o


def enc(pts):
    out = [pts[0][0], pts[0][1]]
    for i in range(1, len(pts)):
        out += [pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]]
    return out


def area(f):
    return sum(f[i][0] * f[(i + 1) % len(f)][1] - f[(i + 1) % len(f)][0] * f[i][1] for i in range(len(f))) / 2


def pip(pt, f):
    x, y = pt; ins = False; n = len(f)
    for i in range(n):
        x1, y1 = f[i]; x2, y2 = f[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def main():
    c = L("cont-north-america"); q = c["q"]
    rings = [dec(r) for r in c["c"]["USA"]]
    main_ring = max(rings, key=len)
    lines = [dec(r) for r in L("a1-USA")["l"]]
    ring = list(main_ring[:-1] if main_ring[0] == main_ring[-1] else main_ring)
    ins = collections.defaultdict(list); ends = {}
    for ln in lines:
        for p in (ln[0], ln[-1]):
            if p in ends:
                continue
            best = None
            for i in range(len(ring)):
                A, B = ring[i], ring[(i + 1) % len(ring)]
                dx, dy = B[0] - A[0], B[1] - A[1]; d2 = dx * dx + dy * dy or 1
                t = max(0, min(1, ((p[0] - A[0]) * dx + (p[1] - A[1]) * dy) / d2)); r = (A[0] + t * dx, A[1] + t * dy)
                d = math.hypot(r[0] - p[0], r[1] - p[1])
                if best is None or d < best[0]:
                    best = (d, i, t, r)
            if best[0] <= SNAP and p not in INLAND:
                rp = (round(best[3][0]), round(best[3][1])); ends[p] = rp; ins[best[1]].append((best[2], rp))
            else:
                ends[p] = p
    ring2 = []
    for i in range(len(ring)):
        ring2.append(ring[i]); ring2 += [rp for _, rp in sorted(ins[i])]
    ring2.append(ring2[0])
    edges = set()
    def add(a, b):
        if a != b: edges.add((a, b) if a < b else (b, a))
    for i in range(len(ring2) - 1): add(ring2[i], ring2[i + 1])
    for ln in lines:
        pts = [ends.get(ln[0], ln[0])] + ln[1:-1] + [ends.get(ln[-1], ln[-1])]
        for i in range(len(pts) - 1): add(pts[i], pts[i + 1])
    adj = collections.defaultdict(set)
    for a, b in edges: adj[a].add(b); adj[b].add(a)
    ch = True
    while ch:
        ch = False
        for n in list(adj):
            if len(adj[n]) <= 1:
                for m in adj[n]: adj[m].discard(n)
                del adj[n]; ch = True
    order = {n: sorted(adj[n], key=lambda m: math.atan2(m[1] - n[1], m[0] - n[0])) for n in adj}
    seen = set(); faces = []
    for a in adj:
        for b in adj[a]:
            if (a, b) in seen: continue
            f = []; u, v = a, b
            while (u, v) not in seen:
                seen.add((u, v)); f.append(u)
                o = order[v]; w = o[(o.index(u) - 1) % len(o)]; u, v = v, w
            faces.append(f)
    faces = [f for f in faces if area(f) > 0]            # (the outer face winds the other way)
    pls = [(r[3], project(r[4], r[5]), r[7]) for r in gazetteer()["places"] if r[2] == "USA" and r[3]]
    caps = [(n, xy) for n, xy, k in pls if k == 1]
    by = collections.OrderedDict(); used = set()
    for f in faces:
        vote = collections.Counter(n for n, (x, y), k in pls if pip((x * q, y * q), f) for _ in range(5 if k == 1 else 1))
        if not vote: print("no place in a face of", len(f), "points, area", int(area(f))); continue
        mix = [(n, c) for n, c in vote.most_common() if c >= 5]
        if len(mix) > 1: print("mixed face", len(f), "points:", mix[:6])
        by.setdefault(vote.most_common(1)[0][0], []).append(enc(f + [f[0]]))
    out = [[n, r] for n, r in by.items()]; used = set(by)
    # Alaska and Hawaii: their own coast rings (by where the ring stands)
    for nm, test in (("Alaska", lambda lon, lat: lat > 50 and (lon < -129 or lon > 165)), ("Hawaii", lambda lon, lat: lat < 25 and -165 < lon < -150)):
        rs = []
        for r in rings:
            if r is main_ring: continue
            mx = sum(p[0] for p in r) / len(r) / q; my = sum(p[1] for p in r) / len(r) / q
            lon, lat = _inv(mx, my)
            if test(lon, lat): rs.append(enc(r))
        out.append([nm, rs]); used.add(nm)
    print("states", len(out), "missing", sorted(n for n, _ in caps if n not in used))
    with gzip.open(f"{DIR}/a1p-USA.json.gz", "wt") as fh:
        json.dump({"v": 1, "q": q, "s": out}, fh, separators=(",", ":"))
    print(os.path.getsize(f"{DIR}/a1p-USA.json.gz"), "bytes")


def _inv(x, y):
    """Equal Earth world units -> (lon, lat) degrees (newton on the forward map in world_geo)."""
    from alto.build import world_geo as g
    lon, lat = x / 5.0, -y / 5.0
    for _ in range(30):
        px, py = g.project(lon, lat); e = (px - x, py - y)
        px2, py2 = g.project(lon + 1e-3, lat); px3, py3 = g.project(lon, lat + 1e-3)
        a, b, c2, d = (px2 - px) / 1e-3, (px3 - px) / 1e-3, (py2 - py) / 1e-3, (py3 - py) / 1e-3
        det = a * d - b * c2 or 1e-9
        lon -= (d * e[0] - b * e[1]) / det; lat -= (-c2 * e[0] + a * e[1]) / det
    return lon, lat


if __name__ == "__main__":
    main()
