"""City engine v2: the pipeline (design 8.1) that palace_grid.grid() runs when a city detects as more than one grid
domain, or as a grid domain with a free one beside it. A one-domain city never comes here (grid() keeps the v1 code
for it, byte-identical, tests/test_grid_snapshot.py).

    1-2  city_field / city_domains.detect      domains, ownership, seam candidates        (E1; grid() calls detect)
    3    city_avenues.classify                  every avenue's pieces per domain           (E5)
    4-6  city_seams.plan                        lines per domain, angled seams, layout     (E3)
    7    DomLattice + city_lattice.emit         complete lines and blocks per domain       (E2), clipped by the seams
                                                (Layout), the domain's real outline and the river band
    8    city_avenues.draw                      octilinear avenues                         (E5)
    9    rivers + bridges                       the river course through each bank's own mapping
    10   landmarks / stations / parks           per domain through T_d
    11   palace_transit.snap(doms=...)          transit on the drawn domains, after the avenues  (E4)
    12   blocks/lots per domain (cut blocks included)
    13   free domains                           voids (no lattice; their own streets are not drawn)
    14   city_report                            the summary is stored in g["engine"]["report"]

build(m, det, majors, diagonals, lines, landmarks, parks) -> the map dict the page draws (v1 keys plus tq, te, doms,
seams, engine). Pure: no I/O.
"""
from __future__ import annotations

import math
import time
from bisect import bisect_left
from types import SimpleNamespace

from . import city_avenues, city_lattice, city_seams
from .city_lattice import Lattice, emit, join_hinges, inside as ring_inside, area as ring_area
from .palace_grid import CW, CH, PAD, LEAD, norm, _pairs, _segd, Mapping
from .palace_river import course, resample, _main_piece, _len, NARROW_W, WIDE_W, GAP as RIVER_GAP, EDGE as RIVER_EDGE

OWN_TOL = 150.0         # real px: a cell whose centre is this close outside its domain's outline still belongs to it
SEAM_NEAR = 1.5         # blocks: near a seam the Layout alone decides (the real outline is only a coarse ring)
SEAM_FAR = 6.0          # blocks: up to here a cell whose real place is in the domain across the seam is still drawn
MIN_LINES = 3           # a grid domain needs this many lines a family to be a lattice (else it is a void)
RASTER = 40.0           # page px: the occupancy raster that keeps two domains' blocks from overlapping


# ── small geometry ──────────────────────────────────────────────────────────
def _ring_d(p, ring):
    n = len(ring)
    return min(_segd(p, ring[i], ring[(i + 1) % n]) for i in range(n)) if n > 1 else 1e18


def _in_real(d, x, y):
    if not d.poly or not ring_inside(d.poly, x, y):
        return False
    return not any(h and ring_inside(h, x, y) for h in (d.holes or ()))


def _hull(pts):
    pts = sorted(set((round(x, 1), round(y, 1)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def unlocal(loc, lx, ly):
    """The inverse of a (Local)Mapping: local lattice px -> real px."""
    def inv(v, R, G, step):
        if not G or not R:
            return v
        if len(G) == 1:
            return R[0] + (v - G[0]) / step * 100.0
        if v <= G[0]:
            return R[0] - (G[0] - v) * (R[1] - R[0]) / max(1e-9, G[1] - G[0])
        if v >= G[-1]:
            return R[-1] + (v - G[-1]) * (R[-1] - R[-2]) / max(1e-9, G[-1] - G[-2])
        i = bisect_left(G, v)
        g0, g1, r0, r1 = G[i - 1], G[i], R[i - 1], R[i]
        return r0 + (v - g0) / max(1e-9, g1 - g0) * (r1 - r0)
    tx = inv(lx, loc.xr, loc.xg, getattr(loc, "gv", CW))
    ty = inv(ly, loc.yr, loc.yg, getattr(loc, "gh", CH))
    c, s = math.cos(loc.th), math.sin(loc.th)
    tx, ty = tx - loc.cx, ty - loc.cy
    return (tx * c - ty * s + loc.cx, tx * s + ty * c + loc.cy)


# ── one domain's lattice, clipped by the Layout, its real outline and the river ──
class DomLattice(Lattice):
    own = True

    def __init__(self, dom, lay, xg, yg, cells_ok, lm_cells=(), i0=0, j0=0):
        super().__init__(dom, xg, yg, lm_cells=lm_cells)
        self.lay, self.did, self.ok = lay, dom.id, cells_ok
        self.i0, self.j0 = i0, j0
        self.clip = None                         # the Layout clips (region minus the children's slabs)

    def cell_poly(self, i, j):
        if (i, j) not in self.ok:
            return []
        q = self.cell_rect(i, j)
        pieces = self.lay.clip(self.did, q)
        if not pieces:
            return []
        return max(pieces, key=lambda p: abs(ring_area(p)))

    def inside(self, x, y):
        reg = self.lay.region.get(self.did)
        if reg and not ring_inside(reg, x, y):
            return False
        return not any(ring_inside(K, x, y) for K in self.lay.subtract.get(self.did, ()))

    def seg_in(self, a, b):
        return self.lay.segment(self.did, a, b)

    def clip_poly(self, poly):
        pieces = self.lay.clip(self.did, poly)
        return max(pieces, key=lambda p: abs(ring_area(p))) if pieces else []


class CityMapping(Mapping):
    """Real px -> page px through the domain that owns the point; between domains (the river, a seam band) the two
    nearest domains' mappings are blended by distance, so a river runs smoothly between its two banks. turn/_interp
    and the tables are the root's (palace_river's wide-river code reads them)."""

    def __init__(self, doms, maps, root_loc, root_o):
        loc = root_loc
        super().__init__(loc.th, loc.cx, loc.cy, loc.xr, [x + root_o[0] for x in loc.xg], loc.yr,
                         [y + root_o[1] for y in loc.yg])
        self.ds = [(d, maps[d.id]) for d in doms]

    def __call__(self, x, y):
        best = []
        for d, mp in self.ds:
            if _in_real(d, x, y):
                return mp(x, y)
            best.append((_ring_d((x, y), d.poly), d, mp))
        best.sort(key=lambda t: t[0])
        if len(best) == 1 or best[1][0] > 3 * best[0][0] + 400:
            return best[0][2](x, y)
        (d0, _, m0), (d1, _, m1) = best[0], best[1]
        p0, p1 = m0(x, y), m1(x, y)
        w0, w1 = 1.0 / (d0 + 1.0), 1.0 / (d1 + 1.0)
        return ((p0[0] * w0 + p1[0] * w1) / (w0 + w1), (p0[1] * w0 + p1[1] * w1) / (w0 + w1))


def multi(det) -> bool:
    """The v2 pipeline runs when there is more than one grid domain, or a grid domain beside a free one."""
    g = [d for d in det.domains if d.kind == "grid" and d.poly]
    f = [d for d in det.domains if d.kind == "free" and d.poly]
    return len(g) > 1 or (len(g) == 1 and bool(f))


# ── the pipeline ────────────────────────────────────────────────────────────
def build(m, det, majors=(), diagonals=(), rail_specs=(), lm_specs=(), parks=()) -> dict:
    T = {}
    t0 = time.time()
    doms_all = list(det.domains)
    majors_n = {norm(x) for x in majors}
    # 3. avenues (E5): every avenue's pieces per domain; the lattice / seam pieces must be kept as lines
    recs = city_avenues.classify(m, doms_all, majors, diagonals)
    av_keep = [{"n": r["n"], "dom": pc["dom"], "kind": pc["kind"]} for r in recs for pc in r["pieces"]]
    T["avenues"] = time.time() - t0
    # 4-6. lines per domain, seams, layout (E3); a grid domain too small for a lattice is a void
    grid_doms = [d for d in doms_all if d.kind == "grid" and d.poly]
    voids = []
    for _ in range(3):
        sl, lines, lay = city_seams.plan(grid_doms, avenues=av_keep, majors=majors, rivers=m.get("rivers"))
        bad = [d for d in grid_doms if min(len(lines[d.id]["v"]), len(lines[d.id]["h"])) < MIN_LINES]
        if not bad:
            break
        voids += bad
        grid_doms = [d for d in grid_doms if d not in bad]
    T["plan"] = time.time() - t0 - T["avenues"]
    by_id = {d.id: d for d in grid_doms}
    root = sl[0].info["root"] if sl else max(grid_doms, key=lambda d: ring_area(d.poly)).id
    others_real = [d for d in doms_all if d.poly]

    # 7a. which cells each domain draws: the Layout's region (the seams), the real outline (with a little slack, never
    #     into another domain's outline) and no overlap with a domain that owns the place for certain
    seam_segs = {}
    for sm in sl:
        if sm.info.get("parts") and _main_kind(sm) != "water":
            for did in (sm.a, sm.b):
                seam_segs.setdefault(did, []).extend(sm.segs)
    partners = {}
    for sm in sl:
        if _main_kind(sm) != "water":
            partners.setdefault(sm.a, set()).add(sm.b)
            partners.setdefault(sm.b, set()).add(sm.a)
    prio = {d.id: (d.id == root, abs(ring_area(d.poly))) for d in grid_doms}
    lat_ix, claim = {}, {}
    for did, d in by_id.items():
        mp = lay.maps[did]
        gv, gh = mp.loc.gv, mp.loc.gh
        x0, y0, x1, y1 = lay.rect[did]
        i0, i1 = int(math.ceil(x0 / gv - 1e-9)), int(math.floor(x1 / gv + 1e-9))
        j0, j1 = int(math.ceil(y0 / gh - 1e-9)), int(math.floor(y1 / gh + 1e-9))
        xg, yg = [i * gv for i in range(i0, i1 + 1)], [j * gh for j in range(j0, j1 + 1)]
        lat_ix[did] = (i0, j0, xg, yg)
        cl = {}
        segs = seam_segs.get(did, ())
        blk = max(gv, gh)
        pdoms = [by_id[o] for o in partners.get(did, ()) if o in by_id]
        for j in range(len(yg) - 1):
            for i in range(len(xg) - 1):
                lx, ly = (xg[i] + xg[i + 1]) / 2, (yg[j] + yg[j + 1]) / 2
                rect = [mp.page(xg[i], yg[j]), mp.page(xg[i + 1], yg[j]), mp.page(xg[i + 1], yg[j + 1]),
                        mp.page(xg[i], yg[j + 1])]
                pieces = lay.clip(did, rect)
                if not pieces:
                    continue
                piece = max(pieces, key=lambda q: abs(ring_area(q)))
                pc = city_lattice.centroid(piece)
                ds = min((_segd(pc, (s_[0], s_[1]), (s_[2], s_[3])) for s_ in segs), default=1e18)
                rx, ry = unlocal(mp.loc, lx, ly)
                if ds < SEAM_NEAR * blk or _in_real(d, rx, ry) or \
                        (ds < SEAM_FAR * blk and any(_in_real(o, rx, ry) for o in pdoms)):
                    cl[(i, j)] = (2, piece)
                elif d.poly and _ring_d((rx, ry), d.poly) < OWN_TOL * (m.get("scale") or 1.0) and \
                        not any(o is not d and o not in pdoms and _in_real(o, rx, ry) for o in others_real):
                    cl[(i, j)] = (1, piece)
        claim[did] = cl
    # occupancy: where two domains that share no seam both claim a place, the stronger claim (then the root, then
    # the larger domain) keeps it; seam partners are already kept apart by the Layout
    occ = {}

    def samples(piece):
        c = city_lattice.centroid(piece)
        return [c] + [(c[0] + .55 * (q[0] - c[0]), c[1] + .55 * (q[1] - c[1])) for q in piece]
    for did, cl in claim.items():
        for ij, (st, piece) in cl.items():
            for x, y in samples(piece):
                k = (int(x // RASTER), int(y // RASTER))
                cur = occ.get(k)
                rank = (st, prio[did])
                if cur is None or rank > cur[0]:
                    occ[k] = (rank, did)
    ok = {}
    for did, cl in claim.items():
        keep = set()
        for ij, (st, piece) in cl.items():
            lose = False
            for x, y in samples(piece):
                cur = occ.get((int(x // RASTER), int(y // RASTER)))
                if cur and cur[1] != did and cur[1] not in partners.get(did, ()) and cur[0] > (st, prio[did]):
                    lose = True
                    break
            if not lose:
                keep.add(ij)
        ok[did] = keep
    # page origin: the drawn cells start PAD from the top-left
    xs, ys = [], []
    for did, keep in ok.items():
        mp = lay.maps[did]
        i0, j0, xg, yg = lat_ix[did]
        for i, j in keep:
            for a, b in ((i, j), (i + 1, j + 1), (i + 1, j), (i, j + 1)):
                p = mp.page(xg[a], yg[b])
                xs.append(p[0]); ys.append(p[1])
    dx, dy = PAD - min(xs), PAD - min(ys)
    city_seams._shift(lay, {d.id: d for d in grid_doms}, sl, dx, dy)
    for did, cl in claim.items():
        for ij in list(cl):
            st_, piece = cl[ij]
            cl[ij] = (st_, [(x + dx, y + dy) for x, y in piece])
    maps = lay.maps
    W, H = int(max(xs) + dx + PAD), int(max(ys) + dy + PAD)
    rmp = maps[root]
    cmap = CityMapping(grid_doms, maps, rmp.loc, rmp.o)
    T["cells"] = time.time() - t0 - T["avenues"] - T["plan"]

    # 9a. the rivers: each course carried through its banks' mappings (CityMapping), smoothed; the wide one
    #     (the city's edge) a broad band, nothing drawn across it
    cents = []
    for did, keep in ok.items():
        for ij in keep:
            cents.append(city_lattice.centroid(claim[did][ij][1]))
    river, W = _rivers(m, cmap, W, H, [(x + 0.0, y + 0.0) for x, y in cents])

    r_ix = [(city_avenues.PolyIndex(rv["_q"], 200.0), rv["w"]) for rv in river if len(rv["_q"]) > 1]

    def near_river(p, extra=0.0):
        return any(ix.dist(p, w / 2 + extra + 1) < w / 2 + extra for ix, w in r_ix)
    for did in by_id:                                # no block in the river band
        mp = maps[did]
        i0, j0, xg, yg = lat_ix[did]
        ok[did] = {(i, j) for i, j in ok[did]
                   if not near_river(mp.page((xg[i] + xg[i + 1]) / 2, (yg[j] + yg[j + 1]) / 2), 10)}

    # 10a. landmark buildings: the cells their real footprint covers in their own domain
    def find(name):
        nl = name.lower()
        for coll in (m.get("stations", []), m.get("landmarks", [])):
            for x in coll:
                if x.get("n", "").lower() == nl:
                    return x
        for coll in (m.get("stations", []), m.get("landmarks", [])):
            for x in coll:
                if nl in x.get("n", "").lower() or x.get("n", "").lower() in nl:
                    return x
        return None

    def owner(x, y):
        own = [d for d in grid_doms if _in_real(d, x, y)]
        if own:
            return min(own, key=lambda d: abs(ring_area(d.poly)))
        return min(grid_doms, key=lambda d: _ring_d((x, y), d.poly))
    from .palace_towers import tower_key
    lms = []
    lm_cells = {did: set() for did in by_id}
    for spec in lm_specs or ():
        f = find(spec.get("name") or "")
        if not f:
            continue
        d = owner(f["x"], f["y"])
        mp = maps[d.id]
        i0, j0, xg, yg = lat_ix[d.id]
        rings = [q for q in (f.get("r") or []) if q]
        P = [mp.loc(x, y) for q in rings for x, y in _pairs(q)] if rings else [mp.loc(f["x"], f["y"])]
        gv, gh = mp.loc.gv, mp.loc.gh
        lx0, lx1 = min(p[0] for p in P), max(p[0] for p in P)
        ly0, ly1 = min(p[1] for p in P), max(p[1] for p in P)
        nx, ny = len(xg) - 1, len(yg) - 1
        a0 = max(0, int(math.floor((lx0 - xg[0]) / gv + .2))); a1 = min(nx, int(math.ceil((lx1 - xg[0]) / gv - .2)))
        b0 = max(0, int(math.floor((ly0 - yg[0]) / gh + .2))); b1 = min(ny, int(math.ceil((ly1 - yg[0]) / gh - .2)))
        if a1 <= a0:
            a0 = max(0, min(nx - 1, int(((lx0 + lx1) / 2 - xg[0]) // gv))); a1 = a0 + 1
        if b1 <= b0:
            b0 = max(0, min(ny - 1, int(((ly0 + ly1) / 2 - yg[0]) // gh))); b1 = b0 + 1
        cells = {(i, j) for i in range(a0, a1) for j in range(b0, b1)}
        if any(cells & l_["cells"] for l_ in lms if l_["dom"] == d.id):
            if len(cells) == 1 and tower_key(spec.get("name") or ""):
                (ci, cj), = cells
                cx_, cy_ = (lx0 + lx1) / 2, (ly0 + ly1) / 2
                near_ = sorted(((ci + u, cj + v) for u, v in ((0, 1), (0, -1), (1, 0), (-1, 0))
                                if 0 <= ci + u < nx and 0 <= cj + v < ny),
                               key=lambda c: (cx_ - (xg[c[0]] + xg[c[0] + 1]) / 2) ** 2 + (cy_ - (yg[c[1]] + yg[c[1] + 1]) / 2) ** 2)
                free_ = [c for c in near_ if not any(c in l_["cells"] for l_ in lms if l_["dom"] == d.id)]
                if not free_:
                    continue
                (a0, b0), = free_[:1]; a1, b1 = a0 + 1, b0 + 1
                cells = {(a0, b0)}
            else:
                continue
        lms.append({"n": spec.get("label") or spec["name"], "page": spec.get("page") or "", "cells": cells,
                    "dom": d.id, "ij": (a0, b0, a1, b1)})
        lm_cells[d.id] |= cells
        ok[d.id] |= cells

    # 7b. emit every domain: complete lines, T-joins on its seams, hinge lines through, blocks with lots
    av_names = {norm(sm.avenue) for sm in sl if sm.avenue}
    heavy = majors_n | av_names
    lats, outs, through_all = {}, {}, {}
    for sm in sl:
        for h in sm.hinge:
            if isinstance(h, dict):
                through_all.setdefault(sm.a, set()).add((h["fa"], h["a"]))
                through_all.setdefault(sm.b, set()).add((h["fb"], h["b"]))
    wet = lambda p: near_river(p, 6)                                              # noqa: E731
    for did, d in by_id.items():
        i0, j0, xg, yg = lat_ix[did]
        d.mapping = maps[did]
        lat = DomLattice(d, lay, [x for x in xg], [y for y in yg], ok[did], lm_cells[did], i0, j0)
        lats[did] = lat
        L = lines[did]
        names = {}
        for fam, base, cnt in (("v", i0, len(xg)), ("h", j0, len(yg))):
            byi = {l.get("i", k): (l.get("n") or "") for k, l in enumerate(L[fam])}
            names[fam] = [byi.get(base + k, "") for k in range(cnt)]
        thr = {(f, k - (i0 if f == "v" else j0)) for f, k in through_all.get(did, ())}
        outs[did] = emit(lat, names, heavy, thr, root=abs(lat.a) < 1e-9, wet=wet, seams=seam_segs.get(did, ()))
    T["emit"] = time.time() - t0 - sum(T.values())

    streets = join_hinges([s for did in outs for s in outs[did]["streets"]])
    # the seams are streets too: lines T into them, the walking graph crosses domains on them
    for sm in sl:
        if _main_kind(sm) == "water" or not sm.segs:
            continue
        n = norm(sm.avenue) if sm.avenue else ""
        for s in sm.segs[:1] if _main_part_index(sm) is None else [sm.segs[_main_part_index(sm)]]:
            st = {"n": n, "k": 0 if n else 1, "sm": 1, "p": [round(v, 1) for v in s]}
            if n:
                st["L"] = 1
            streets.append(st)
    tiles = [t for did in outs for t in outs[did]["tiles"]]
    edges = [e for did in outs for e in outs[did]["edges"]]
    tq = [q for did in outs for q in outs[did]["tq"]]
    te = [q for did in outs for q in outs[did]["te"]]

    # 8. the avenues (E5): octilinear in their domains, joined at the seams
    tdoms = {}
    for did, d in by_id.items():
        clip = lay.region.get(did)
        if clip is None and did != root:
            lat = lats[did]
            cs_ = [c for c, kd in outs[did]["cells"].items() if kd in ("full", "cut", "plaza", "lm")]
            clip = _hull([p for c in cs_ for p in lat.cell_rect(*c)])
        tdoms[did] = SimpleNamespace(id=did, kind="grid", poly=d.poly, holes=d.holes, mapping=maps[did].loc,
                                     a=maps[did].a, o=maps[did].o, clip=clip if did != root else None,
                                     theta=d.theta)
    nodes = {}
    for did, out in outs.items():
        lat = lats[did]
        pts = set()
        for (i, j), kd in out["cells"].items():
            if kd in ("full", "cut", "plaza", "lm"):
                pts |= {(lat.xg[i], lat.yg[j]), (lat.xg[i + 1], lat.yg[j]), (lat.xg[i], lat.yg[j + 1]),
                        (lat.xg[i + 1], lat.yg[j + 1])}
        nodes[did] = sorted(pts)
    av_recs = [r for r in recs if any(pc["kind"] == "diagonal" and pc["dom"] in by_id for pc in r["pieces"])]
    try:
        avs = city_avenues.draw(av_recs, list(tdoms.values()), nodes, sl)
    except Exception as ex:                                       # noqa: BLE001  (an avenue never fails a build)
        avs, T["avenue_error"] = [], repr(ex)[:200]
    for a_ in avs:
        st = {"n": norm(a_["n"]), "k": 0, "d": 1, "p": [round(v, 1) for v in a_["p"]]}
        if a_.get("j"):
            st["j"] = [int(bool(v)) for v in a_["j"]]
        streets.append(st)
    T["avenues_draw"] = time.time() - t0 - sum(T.values())

    # 9b. bridges: a line the river interrupts, crossing it where the real street bridges it, is one line over it
    over = _bridges(streets, river, lines, by_id, m)
    # the wide river's bridges: from the end of the street they leave to the far side (as v1)
    bridge_names = set()
    for br in (m.get("bank") or {}).get("bridges", []):
        gx, gy = cmap(*br["at"])
        best = None
        for s in streets:
            if s.get("o") or s.get("d") or not s.get("n") and False:
                continue
            q = _pairs(s["p"])
            for e in (q[0], q[-1]):
                dd = math.hypot(e[0] - gx, e[1] - gy)
                if dd < 2 * CW and (best is None or dd < best[0]):
                    best = (dd, e)
        wide = next((rv for rv in river if rv["w"] == WIDE_W), None)
        if best and wide:
            over.append({"n": br["n"], "k": 0, "o": 1, "br": 1,
                         "p": [round(best[1][0], 1), round(best[1][1], 1), W + 50, round(best[1][1], 1)]})
            bridge_names.add(norm(br["n"]))

    # 10b. the railways (lines=): straight, above ground, through their stops (v1 rule, page coordinates)
    rails, stations = [], []
    for ln in rail_specs or ():
        stops = []
        for nm in ln.get("stops") or []:
            f = find(nm)
            if f:
                gx, gy = cmap(f["x"], f["y"])
                stops.append((nm, gx, gy))
        if len(stops) < 2:
            continue
        ys_ = sorted(y for _, _, y in stops)
        y = ys_[len(ys_) // 2]
        xs_ = [x for _, x, _ in stops]
        rails.append({"n": ln.get("name") or "", "c": ln.get("color") or "", "k": "rail",
                      "p": [round(min(xs_), 1), round(y, 1), round(max(xs_), 1), round(y, 1)]})
        for nm, x, _ in stops:
            stations.append({"n": nm, "x": round(x, 1), "y": round(y, 1), "k": "rail", "hub": 1})
    rail_y = {r["p"][1] for r in rails}

    landmarks_out = []
    for l_ in lms:
        a0, b0, a1, b1 = l_["ij"]
        rec = city_lattice.landmark(lats[l_["dom"]], a0, b0, a1, b1, l_["n"], l_["page"])
        landmarks_out.append(rec)

    # 11. transit (E4) on the drawn domains, after the avenues are drawn (the trolleys run on them)
    from .palace_transit import snap as snap_transit
    from .palace_transit_route import drawn_segs
    tr_doms = [(tdoms[did], lats[did]) for did in sorted(by_id, key=lambda i: (i != root, i))]
    segs = drawn_segs(tiles, tq, edges, te, streets + over)
    transit = snap_transit(m.get("transit"), None, None, None, W, H, streets=streets, edges_=edges,
                           doms=tr_doms, segs=segs)
    new_streets = []
    have = set()
    for e in edges:
        have.add(tuple(round(v) for v in e))
    for t_ in transit.pop("ge", []):
        if len(t_) == 5:
            did, a0, b0, a1, b1 = t_
            lat = lats.get(did)
            if lat is None:
                continue
            p0, p1 = lat.node(a0, b0), lat.node(a1, b1)
        else:
            a0, b0, a1, b1 = t_
            lat = lats[root]
            p0, p1 = lat.node(a0, b0), lat.node(a1, b1)
        key = tuple(round(v) for v in (min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])))
        if key in have:
            continue
        have.add(key)
        if abs(lat.a) < 1e-9:
            edges.append(list(key))
        else:
            te.append([round(p0[0], 1), round(p0[1], 1), round(p1[0], 1), round(p1[1], 1)])
        new_streets.append(list(key))
    if transit.get("lines"):
        transit["new"] = new_streets
    T["transit"] = time.time() - t0 - sum(T.values())

    # 10c. parks: the root domain's lattice (the page shapes parks on g["grid"]'s columns and rows)
    from .palace_parks import pick as pick_parks
    rl = lats[root]
    rxg = [rl.page(x, 0)[0] for x in rl.xg]
    ryg = [rl.page(0, y)[1] for y in rl.yg]
    root_d = by_id[root]
    m_root = dict(m, parks=[pk for pk in m.get("parks", []) if pk.get("r") and pk["r"][0] and
                            owner(*_ring_c(pk["r"][0])) is root_d])
    rmap = Mapping(rmp.loc.th, rmp.loc.cx, rmp.loc.cy, rmp.loc.xr, rxg, rmp.loc.yr, ryg)
    park_cells = pick_parks(m_root, rmap, rxg, ryg, parks or (), lm_cells[root], lambda p: near_river(p, 0))

    # 12. blocks and lots of every domain (cut blocks at the seams and the river included)
    blocks = []
    for did in sorted(outs):
        for b in outs[did]["blocks"]:
            b = dict(b)
            b.pop("cell", None)
            b["lots"] = [lt for lt in b["lots"] if not any(abs(lt[1] - ry) < 30 for ry in rail_y)] or b["lots"]
            blocks.append(b)
    blocks.sort(key=lambda b: (b["y"], b["x"]))
    for k, b in enumerate(blocks):
        b["id"] = k

    # the map the page draws
    tables = Mapping(rmp.loc.th, rmp.loc.cx, rmp.loc.cy, rmp.loc.xr, rxg, rmp.loc.yr, ryg).tables()
    g = {k: v for k, v in m.items() if k not in ("streets", "water", "rivers", "rails", "trails", "stations",
                                                 "landmarks", "parks", "W", "H", "majors", "transit")}
    for rv in river:
        rv.pop("_q", None)
    g.update(W=W, H=H, streets=streets + over, rails=rails, trails=[], parks=park_cells, stations=stations,
             landmarks=landmarks_out, rivers=[], river=river, water=[], tiles=tiles, edges=edges, tq=tq, te=te,
             majors=sorted(majors_n | {norm(s_["n"]) for s_ in streets if s_.get("k") == 0 and s_.get("n")} | bridge_names),
             grid=tables, cols=[n for n in _names(lines[root], "v") if n], rows=[n for n in _names(lines[root], "h") if n])
    g["doms"] = [_dom_out(tdoms[did], lats[did], maps[did], did == root) for did in sorted(by_id)]
    g["seams"] = [_seam_out(sm) for sm in sl]
    g["transit"] = transit
    g["blocks"] = blocks
    T["total"] = time.time() - t0
    g["engine"] = {"path": "v2", "domains": len(by_id), "voids": [d.id for d in voids],
                   "free": [d.id for d in doms_all if d.kind == "free"],
                   "seams": [{"a": sm.a, "b": sm.b, "kind": sm.kind, "avenue": sm.avenue, "phi": round(sm.phi, 2),
                              "hinges": len(sm.hinge)} for sm in sl],
                   "t": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in T.items()}}
    return g


def _ring_c(flat):
    q = _pairs(flat)
    return (sum(p[0] for p in q) / len(q), sum(p[1] for p in q) / len(q))


def _names(L, fam):
    return [l.get("n") or "" for l in L[fam]]


def _main_part_index(sm):
    parts = sm.info.get("parts") or []
    mp = city_seams._main_part(sm) if parts else None
    return parts.index(mp) if mp is not None and mp in parts and parts.index(mp) < len(sm.segs) else None


def _main_kind(sm):
    parts = sm.info.get("parts") or []
    if not parts:
        return sm.kind
    mp = city_seams._main_part(sm)
    return mp["kind"] if mp else "water"


def _hug(pts, cents, w):
    """The wide river (the city's edge) along the drawn blocks: each mapped point moved to w/2 + a gap off the nearest
    block, on its own side (the real distance from the last street to the river is not kept, as in v1)."""
    cell = 400.0
    b = {}
    for c in cents:
        b.setdefault((int(c[0] // cell), int(c[1] // cell)), []).append(c)
    out = []
    for p in pts:
        ci, cj = int(p[0] // cell), int(p[1] // cell)
        best = None
        for r in range(0, 30):
            for i in range(ci - r, ci + r + 1):
                for j in (range(cj - r, cj + r + 1) if i in (ci - r, ci + r) else (cj - r, cj + r)):
                    for c in b.get((i, j), ()):
                        d = math.dist(p, c)
                        if best is None or d < best[0]:
                            best = (d, c)
            if best and best[0] <= r * cell:
                break
        if not best:
            out.append(p)
            continue
        d, c = best
        if d < 0.6 * CH:
            continue                                  # mapped into the blocks: the neighbours carry the course
        u = ((p[0] - c[0]) / d, (p[1] - c[1]) / d)
        off = 0.5 * (abs(u[0]) * CW + abs(u[1]) * CH) + RIVER_GAP + w / 2
        out.append((c[0] + u[0] * off, c[1] + u[1] * off))
    return out or pts


def _rivers(m, cmap, W, H, cents=()):
    """[{n, w, p, _q}] and the glass width: every long river's centre line through CityMapping, smoothed."""
    out = []
    bank = m.get("bank") or {}
    names = []
    for r in m.get("rivers", []):
        if r.get("n") and r["n"] not in names:
            names.append(r["n"])
    realW, realH = m.get("W", 1), m.get("H", 1)
    new_w = W
    for name in names:
        line = _main_piece(m["rivers"], name)
        if not line or _len(line) < .6 * min(realW, realH):
            continue
        real = resample(line, 25.0)
        wide = bank.get("n") == name and bank.get("side") == "e"
        pts = [cmap(x, y) for x, y in real]
        if wide and cents:
            pts = _hug(pts, cents, WIDE_W)
        c = course(pts, 320.0 * (1.4 if wide else 1.0))
        w = WIDE_W if wide else NARROW_W
        if wide:
            new_w = max(new_w, int(max(p[0] for p in c if -50 < p[1] < H + 50) + w / 2 + RIVER_EDGE))
        out.append({"n": name, "w": w, "p": [round(v, 1) for p in c for v in p], "_q": c})
    return out, new_w


def _bridges(streets, river, lines, by_id, m):
    """Same-named lines of two domains facing each other across a river (or one line broken by it), where the real
    street has a bridge: one 'o' street over the river from end to end."""
    if not river:
        return []
    bridged = set()
    for did, L in lines.items():
        for fam in ("v", "h"):
            for l in L[fam]:
                if l.get("bridges") and l.get("n"):
                    bridged.add(norm(l["n"]))
    for st in m.get("streets", []):
        if st.get("b") and st.get("n"):
            bridged.add(norm(st["n"]))
    ends = {}
    for s in streets:
        if not s.get("n") or s.get("d") or s.get("sm") or norm(s["n"]) not in bridged:
            continue
        q = _pairs(s["p"])
        if len(q) < 2:
            continue
        ends.setdefault(s["n"], []).append((q[0], q[1]))
        ends[s["n"]].append((q[-1], q[-2]))
    out = []
    for n, es in ends.items():
        used = set()
        for a in range(len(es)):
            if a in used:
                continue
            best = None
            for b in range(len(es)):
                if b == a or b in used:
                    continue
                p, pin = es[a]
                q, qin = es[b]
                d = math.dist(p, q)
                if d < 40 or d > 900:
                    continue
                # the two ends face each other (each runs on toward the other) and the river lies between them
                u = (p[0] - pin[0], p[1] - pin[1]); v = (q[0] - p[0], q[1] - p[1])
                if u[0] * v[0] + u[1] * v[1] <= 0.6 * math.hypot(*u) * math.hypot(*v):
                    continue
                mid = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                if not any(_segd(mid, x, y) < rv["w"] / 2 + 60 for rv in river for x, y in zip(rv["_q"], rv["_q"][1:])):
                    continue
                if best is None or d < best[0]:
                    best = (d, b)
            if best:
                used |= {a, best[1]}
                p, q = es[a][0], es[best[1]][0]
                out.append({"n": n, "k": 1, "o": 1, "p": [round(p[0], 1), round(p[1], 1), round(q[0], 1), round(q[1], 1)]})
    return out


def _dom_out(td, lat, mp, is_root):
    t = mp.loc.tables()
    return {"id": td.id, "kind": "grid", "theta": round(td.theta, 6), "a": round(mp.a, 4),
            "o": [round(mp.o[0], 2), round(mp.o[1], 2)], "mapping": t,
            "clip": None if is_root or not td.clip else [[round(x, 1), round(y, 1)] for x, y in td.clip],
            "poly": [[round(x), round(y)] for x, y in td.poly], "holes": [[[round(x), round(y)] for x, y in h] for h in (td.holes or []) if h],
            "cwch": [round(mp.loc.gv, 2), round(mp.loc.gh, 2)], "xg": [round(lat.xg[0], 2), len(lat.xg)],
            "yg": [round(lat.yg[0], 2), len(lat.yg)]}


def _seam_out(sm):
    return {"a": sm.a, "b": sm.b, "kind": sm.kind, "avenue": sm.avenue, "phi": round(sm.phi, 3),
            "segs": [[round(v, 1) for v in s] for s in sm.segs], "ratio": round(sm.ratio, 4), "err": round(sm.err, 3),
            "real": [[round(x, 1), round(y, 1)] for x, y in (sm.real or [])],
            "hinge": [{"n": h["n"], "at": [round(h["at"][0], 1), round(h["at"][1], 1)]} for h in sm.hinge if isinstance(h, dict)],
            "phi_real": round(sm.info.get("phi_real", sm.phi) if isinstance(sm.info, dict) else sm.phi, 3)}
