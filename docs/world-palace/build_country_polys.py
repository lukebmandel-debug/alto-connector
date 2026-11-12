"""Makes alto/assets/world/a1p-<ISO>.json.gz for the other countries with state data (AUS BRA CAN CHN IDN IND RUS ZAF): their states / provinces as filled shapes, the
same way build_state_polys.py makes the US's. The shapes are the faces of the planar graph made by the SAME Natural Earth 1:50m pieces the map already ships: ALL the
country's coast rings (its continent tier) plus its admin-1 border lines (a1-<ISO>); a face is named by the gazetteer places inside it (the state capital counts 5); a
coast face with no place in it (an island) joins the nearest named face when it is big enough to see. No insets. Tier format: {"v":1,"q":q,"s":[[name,[ring flat deltas, ...]], ...]}.
Run from the repo root:  python3 docs/world-palace/build_country_polys.py AUS [BRA ...]"""
import collections, glob, gzip, json, math, os, sys

sys.path.insert(0, os.getcwd())
from alto.build.world_geo import gazetteer, project  # noqa: E402

DIR = "alto/assets/world"
SNAP = int(os.environ.get("SNAP", "200"))
L = lambda n: json.loads(gzip.open(f"{DIR}/{n}.json.gz").read())
MIN_ISLAND = 600       # world units x 50 squared: a coast face this big (and unnamed) joins the nearest state


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


TOL = 150
JOIN = 15
def _seg(px, py, A, B):
    dx, dy = B[0] - A[0], B[1] - A[1]; d2 = dx * dx + dy * dy or 1
    t = max(0, min(1, ((px - A[0]) * dx + (py - A[1]) * dy) / d2))
    return math.hypot(A[0] + t * dx - px, A[1] + t * dy - py)


def build(iso):
    cont = next(c for c in (os.path.basename(f)[:-8] for f in glob.glob(f"{DIR}/cont-*.json.gz")) if iso in L(c)["c"])
    c = L(cont); q = c["q"]
    rings = []
    for r in c["c"][iso]:
        p = dec(r)
        rings.append(p[:-1] if p[0] == p[-1] else p)
    lines = [dec(r) for r in L("a1-" + iso)["l"]]
    canon = []                                    # the lines were quantised one by one: a junction's ends can differ by a unit or two, so ends within JOIN of each other are one point
    def cn(p):
        for c0 in canon:
            if abs(c0[0] - p[0]) <= JOIN and abs(c0[1] - p[1]) <= JOIN: return c0
        canon.append(p); return p
    lines = [[cn(ln[0])] + ln[1:-1] + [cn(ln[-1])] for ln in lines]
    ins = collections.defaultdict(list); ends = {}
    for ln in lines:
        for p in (ln[0], ln[-1]):
            if p in ends:
                continue
            best = None
            for ri, ring in enumerate(rings):
                for i in range(len(ring)):
                    A, B = ring[i], ring[(i + 1) % len(ring)]
                    dx, dy = B[0] - A[0], B[1] - A[1]; d2 = dx * dx + dy * dy or 1
                    t = max(0, min(1, ((p[0] - A[0]) * dx + (p[1] - A[1]) * dy) / d2)); r = (A[0] + t * dx, A[1] + t * dy)
                    d = math.hypot(r[0] - p[0], r[1] - p[1])
                    if best is None or d < best[0]:
                        best = (d, ri, i, t, r)
            if best[0] <= SNAP:
                rp = (round(best[4][0]), round(best[4][1])); ends[p] = rp; ins[(best[1], best[2])].append((best[3], rp))
            else:
                ends[p] = p
    edges = set()
    def add(a, b):
        if a != b: edges.add((a, b) if a < b else (b, a))
    for ri, ring in enumerate(rings):
        ring2 = []
        for i in range(len(ring)):
            ring2.append(ring[i]); ring2 += [rp for _, rp in sorted(ins[(ri, i)])]
        ring2.append(ring2[0])
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
    faces = [f for f in faces if area(f) > 0]
    pls = [(r[3], project(r[4], r[5]), r[7]) for r in gazetteer()["places"] if r[2] == iso and r[3]]
    named = []; loose = []
    for f in faces:
        vote = collections.Counter(n for n, (x, y), k in pls if pip((x * q, y * q), f) for _ in range(5 if k == 1 else 1))
        if not vote:                                  # a capital that sits on the coast can fall just outside the coarse coast ring: places within TOL of the face count
            for n, (x, y), k in pls:
                px, py = x * q, y * q
                if min(_seg(px, py, f[i], f[(i + 1) % len(f)]) for i in range(len(f))) <= TOL:
                    vote[n] += 5 if k == 1 else 1
        if vote: named.append((vote.most_common(1)[0][0], f))
        elif area(f) >= MIN_ISLAND: loose.append(f)
    cen = lambda f: (sum(p[0] for p in f) / len(f), sum(p[1] for p in f) / len(f))
    by = collections.OrderedDict()
    for n, f in named: by.setdefault(n, []).append(enc(f + [f[0]]))
    for f in loose:
        cx, cy = cen(f); n = min(named, key=lambda t: min(math.hypot(p[0] - cx, p[1] - cy) for p in t[1]))[0]
        by.setdefault(n, []).append(enc(f + [f[0]]))
    out = [[n, r] for n, r in by.items()]
    states = {r[3] for r in gazetteer()["places"] if r[2] == iso and r[3] and r[7] == 1}
    print(iso, "faces", len(faces), "states", len(out), "loose islands", len(loose), "no face:", sorted(states - set(by))[:12])
    with gzip.open(f"{DIR}/a1p-{iso}.json.gz", "wt") as fh:
        json.dump({"v": 1, "q": q, "s": out}, fh, separators=(",", ":"))
    print(os.path.getsize(f"{DIR}/a1p-{iso}.json.gz"), "bytes")


if __name__ == "__main__":
    for iso in sys.argv[1:]:
        build(iso)
