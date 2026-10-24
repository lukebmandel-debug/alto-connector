"""Memory Palace geometry (brief.mode "palace"): the city's blocks, the lots a
building can stand on, the street graph routes follow, and which lot each
building gets.

Everything here works on the projected map that palace_map.build_map makes
(map px, north up, origin top-left) and is pure and deterministic, so a
rebuild of the same timeline puts every building in the same place.

- Blocks: the land left over once streets (buffered by class), surface
  railways, water, parks and landmark footprints are taken out, found by
  flood-filling a raster of CELL px.
- Lots: the largest rectangle inside a block, turned to the block's own street
  grid (Philadelphia's grid sits ~8° off north; University City's more), cut
  into up to four building-sized pieces along its long side. Lot keys are
  "<block>.<piece>".
- Graph: street centre-lines split wherever two streets cross, so a route can
  turn there; every intersection keeps the names of the streets that meet.
- Placement: each section (unit) is a district — a box the brief names — and
  its buildings stand along a walk through it: serpentine rows across the
  district, one building per block, spread evenly from where the walk starts.
"""
from __future__ import annotations

import math
from collections import deque

CELL = 3                      # raster cell, map px
PER = 2                       # buildings to a block when a district has room
# half-width of what a street takes out of the land, by class k (map px)
STREET_HALF = {0: 13, 1: 8, 2: 7, 3: 6, 4: 4.5, 5: 2.5}
RAIL_HALF = 4
MIN_LOT = (30, 20)            # smallest building (long side, short side)
MAX_LOT = (96, 64)            # largest a lot grows to
LOT_GAP = 8                   # between buildings cut from one block
MARGIN = 6                    # building edge to street edge (beyond the street buffer)


# ── raster helpers ──────────────────────────────────────────────────────────
class _Grid:
    def __init__(self, W, H, cell=CELL):
        self.c = cell
        self.w = int(math.ceil(W / cell)) + 1
        self.h = int(math.ceil(H / cell)) + 1
        self.a = bytearray(self.w * self.h)     # 0 = land, 1 = taken, 2+ = block labels live elsewhere

    def stroke(self, pts, half):
        """Take out every cell within `half` px of the polyline."""
        c, w, h, a = self.c, self.w, self.h, self.a
        r = half / c
        for i in range(0, len(pts) - 2, 2):
            x0, y0, x1, y1 = pts[i] / c, pts[i + 1] / c, pts[i + 2] / c, pts[i + 3] / c
            dx, dy = x1 - x0, y1 - y0
            L2 = dx * dx + dy * dy or 1e-9
            gx0 = max(0, int(min(x0, x1) - r - 1)); gx1 = min(w - 1, int(max(x0, x1) + r + 1))
            gy0 = max(0, int(min(y0, y1) - r - 1)); gy1 = min(h - 1, int(max(y0, y1) + r + 1))
            r2 = r * r
            for gy in range(gy0, gy1 + 1):
                py = gy + .5
                row = gy * w
                for gx in range(gx0, gx1 + 1):
                    px = gx + .5
                    t = ((px - x0) * dx + (py - y0) * dy) / L2
                    t = 0 if t < 0 else 1 if t > 1 else t
                    ex, ey = x0 + t * dx - px, y0 + t * dy - py
                    if ex * ex + ey * ey <= r2:
                        a[row + gx] = 1

    def fill(self, rings):
        """Take out the inside of a set of rings (even-odd), by scanline."""
        c, w, h, a = self.c, self.w, self.h, self.a
        edges = []
        for ring in rings:
            n = len(ring) // 2
            for i in range(n):
                x0, y0 = ring[2 * i] / c, ring[2 * i + 1] / c
                j = (i + 1) % n
                x1, y1 = ring[2 * j] / c, ring[2 * j + 1] / c
                if y0 != y1:
                    edges.append((x0, y0, x1, y1))
        if not edges:
            return
        ys = [e[1] for e in edges] + [e[3] for e in edges]
        for gy in range(max(0, int(min(ys))), min(h - 1, int(max(ys)) + 1) + 1):
            py = gy + .5
            xs = []
            for x0, y0, x1, y1 in edges:
                if (y0 <= py < y1) or (y1 <= py < y0):
                    xs.append(x0 + (py - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            row = gy * w
            for k in range(0, len(xs) - 1, 2):
                for gx in range(max(0, int(xs[k] + .5)), min(w - 1, int(xs[k + 1] - .5)) + 1):
                    a[row + gx] = 1


def _blocks(m, grid):
    """Flood-fill the land left in the grid: [(label, [cell indices])]."""
    w, h, a = grid.w, grid.h, grid.a
    lab = [0] * (w * h)
    out = []
    nxt = 1
    for start in range(w * h):
        if a[start] or lab[start]:
            continue
        q = deque([start]); lab[start] = nxt; cells = []
        edge = False
        while q:
            i = q.popleft(); cells.append(i)
            x, y = i % w, i // w
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                edge = True
            for j in (i - 1 if x else -1, i + 1 if x < w - 1 else -1, i - w if y else -1, i + w if y < h - 1 else -1):
                if j >= 0 and not a[j] and not lab[j]:
                    lab[j] = nxt; q.append(j)
        out.append((nxt, cells, edge))
        nxt += 1
    return out


def _grid_angle(m, x0, y0, x1, y1):
    """The block's own grid: the length-weighted street direction near it, mod 90°."""
    sx = sy = 0.0
    for s in m.get("streets", []):
        if s.get("t"):
            continue
        p = s["p"]
        for i in range(0, len(p) - 2, 2):
            ax, ay, bx, by = p[i], p[i + 1], p[i + 2], p[i + 3]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if not (x0 - 20 <= mx <= x1 + 20 and y0 - 20 <= my <= y1 + 20):
                continue
            L = math.hypot(bx - ax, by - ay)
            th = math.atan2(by - ay, bx - ax)
            sx += L * math.cos(4 * th); sy += L * math.sin(4 * th)
    if not sx and not sy:
        return 0.0
    th = math.atan2(sy, sx) / 4
    return th          # radians, in (-45°, 45°]


def _max_rect(rows):
    """Largest all-ones rectangle in a 0/1 matrix → (r0, c0, r1, c1) inclusive, or None."""
    if not rows:
        return None
    n = len(rows[0]); hts = [0] * n; best = (0, None)
    for r, row in enumerate(rows):
        for c in range(n):
            hts[c] = hts[c] + 1 if row[c] else 0
        st = []
        for c in range(n + 1):
            hc = hts[c] if c < n else 0
            s = c
            while st and st[-1][1] >= hc:
                s, hh = st.pop()
                area = hh * (c - s)
                if area > best[0]:
                    best = (area, (r - hh + 1, s, r, c - 1))
            st.append((s, hc))
    return best[1]


def lots(m, cell=CELL) -> list[dict]:
    """Every block that can hold a building: [{id, x, y, lots: [[cx, cy, w, h, deg], ...]}].
    Block ids number blocks top-left to bottom-right; a lot's key is "<id>.<k>". cell: the raster (a city engine
    free domain uses a coarser one: its window is large)."""
    W, H = m["W"], m["H"]
    g = _Grid(W, H, cell)
    for s in m.get("streets", []):
        if not s.get("t"):
            g.stroke(s["p"], STREET_HALF.get(s.get("k", 4), 4) + MARGIN)
    for t in m.get("trails", []):
        g.stroke(t["p"], 2 + MARGIN / 2)
    for r in m.get("rails", []):
        if not r.get("u"):
            g.stroke(r["p"], RAIL_HALF + MARGIN)
    if m.get("water"):
        g.fill(m["water"])
    for p in m.get("parks", []):
        g.fill(p["r"])
    for lm in m.get("landmarks", []):
        if lm.get("r"):
            g.fill(lm["r"])
    c, w = g.c, g.w
    found = []
    for _lab, cells, edge in _blocks(m, g):
        if edge or len(cells) * c * c < MIN_LOT[0] * MIN_LOT[1] * 1.2:
            continue          # cut off by the map's edge, or too small to stand on
        xs = [(i % w) for i in cells]; ys = [(i // w) for i in cells]
        gx0, gx1, gy0, gy1 = min(xs), max(xs), min(ys), max(ys)
        inside = set(cells)
        cx, cy = (gx0 + gx1 + 1) / 2 * c, (gy0 + gy1 + 1) / 2 * c
        # a schematic is square to the screen: every building stands upright
        th = 0.0 if m.get("schematic") else _grid_angle(m, gx0 * c, gy0 * c, (gx1 + 1) * c, (gy1 + 1) * c)
        co, si = math.cos(th), math.sin(th)
        # sample the block in its own frame (u along the grid, v across)
        R = math.hypot(gx1 - gx0 + 1, gy1 - gy0 + 1) * c / 2 + c
        n = int(2 * R / c) + 1
        rows = []
        for iv in range(n):
            v = -R + (iv + .5) * c
            row = []
            for iu in range(n):
                u = -R + (iu + .5) * c
                x, y = cx + u * co - v * si, cy + u * si + v * co
                gx, gy = int(x // c), int(y // c)
                row.append(1 if 0 <= gx < w and 0 <= gy < g.h and (gy * w + gx) in inside else 0)
            rows.append(row)
        rect = _max_rect(rows)
        if not rect:
            continue
        r0, c0, r1, c1 = rect
        lu, lv = (c1 - c0 + 1) * c, (r1 - r0 + 1) * c
        mu, mv = -R + (c0 + c1 + 1) / 2 * c, -R + (r0 + r1 + 1) / 2 * c
        long_u = lu >= lv
        L, S = (lu, lv) if long_u else (lv, lu)
        if L < MIN_LOT[0] or S < MIN_LOT[1]:
            continue
        S2 = min(S, MAX_LOT[1])
        k = max(1, min(4, int((L + LOT_GAP) // (MIN_LOT[0] * 1.6 + LOT_GAP))))
        piece = min(MAX_LOT[0], (L - LOT_GAP * (k - 1)) / k)
        span = piece * k + LOT_GAP * (k - 1)
        out = []
        for j in range(k):
            off = -span / 2 + piece / 2 + j * (piece + LOT_GAP)
            uu, vv = (mu + off, mv) if long_u else (mu, mv + off)
            x, y = cx + uu * co - vv * si, cy + uu * si + vv * co
            lw, lh = (piece, S2) if long_u else (S2, piece)
            out.append([round(x, 1), round(y, 1), round(lw, 1), round(lh, 1), round(math.degrees(th), 2)])
        found.append({"x": round(cx, 1), "y": round(cy, 1), "lots": out})
    found.sort(key=lambda b: (round(b["y"] / 40), b["x"]))
    for i, b in enumerate(found):
        b["id"] = i
    return found


# ── street graph ────────────────────────────────────────────────────────────
def graph(m) -> dict:
    """Streets as a routable graph: {"n": [x, y, ...] node coords, "e": [a, b, street, ...]
    edges (street = index into the street list), "s": [names], "x": [[node, [name, ...]], ...]
    the named intersections (two or more different names meet)}."""
    streets = [s for s in m.get("streets", []) if not s.get("t")]
    segs = []                      # (street index, x0, y0, x1, y1)
    for si, s in enumerate(streets):
        p = s["p"]
        for i in range(0, len(p) - 2, 2):
            segs.append((si, p[i], p[i + 1], p[i + 2], p[i + 3]))
    # bucket segments to find crossings
    B = 64
    buckets: dict = {}
    for k, (si, x0, y0, x1, y1) in enumerate(segs):
        for bx in range(int(min(x0, x1) // B), int(max(x0, x1) // B) + 1):
            for by in range(int(min(y0, y1) // B), int(max(y0, y1) // B) + 1):
                buckets.setdefault((bx, by), []).append(k)
    cuts = {k: [] for k in range(len(segs))}       # parameter t along each segment
    seen = set()
    for ks in buckets.values():
        for a_i in range(len(ks)):
            for b_i in range(a_i + 1, len(ks)):
                a, b = ks[a_i], ks[b_i]
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                sa, sb = segs[a], segs[b]
                if sa[0] == sb[0] and abs(a - b) == 1:
                    continue
                hit = _cross(sa[1:], sb[1:])
                if hit:
                    cuts[a].append(hit[0]); cuts[b].append(hit[1])
    nodes: dict = {}
    coords: list = []

    def node(x, y):
        key = (round(x / 1.5), round(y / 1.5))
        if key not in nodes:
            nodes[key] = len(coords) // 2; coords.extend((round(x, 1), round(y, 1)))
        return nodes[key]
    edges = []
    names_at: dict = {}
    for k, (si, x0, y0, x1, y1) in enumerate(segs):
        ts = sorted(set([0.0, 1.0] + [t for t in cuts[k] if 0 < t < 1]))
        prev = None
        for t in ts:
            nd = node(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
            nm = streets[si].get("n") or ""
            if nm:
                names_at.setdefault(nd, set()).add(nm)
            if prev is not None and prev != nd:
                edges.extend((prev, nd, si))
            prev = nd
    x = [[nd, sorted(v)] for nd, v in sorted(names_at.items()) if len(v) >= 2]
    return {"n": coords, "e": edges, "s": [s.get("n") or "" for s in streets], "x": x}


def _cross(a, b):
    x1, y1, x2, y2 = a; x3, y3, x4, y4 = b
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-9:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
    if -1e-6 <= t <= 1 + 1e-6 and -1e-6 <= u <= 1 + 1e-6:
        return (min(1, max(0, t)), min(1, max(0, u)))
    return None


# ── placing buildings ──────────────────────────────────────────────────────
def to_px(m, lat, lon):
    s, w, n, e = m["bbox"]
    lat0 = math.radians((s + n) / 2)
    sc = m.get("scale", 1.0)
    x, y = (lon - w) * math.cos(lat0) * 111320 * sc, (n - lat) * 110574 * sc
    if m.get("doms"):          # city engine v2: through the domain the point is in (its lattice, turned and placed)
        return page_of(m, x, y)
    if m.get("grid"):          # the even grid (palace_grid): turned, then carried through its streets
        from .palace_grid import mapping_from
        return mapping_from(m["grid"])(x, y)
    r = m.get("rot")
    if r:            # a schematic (palace_schematic): turned square to its grid, moved to the corner
        c, s_ = math.cos(-r["t"]), math.sin(-r["t"])
        x, y = x - r["cx"], y - r["cy"]
        x, y = x * c - y * s_ + r["cx"] - r["dx"], x * s_ + y * c + r["cy"] - r["dy"]
    return (x, y)


def _in_ring(r, x, y):
    c = False
    n = len(r)
    for i in range(n):
        (x0, y0), (x1, y1) = r[i], r[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _ring_dist(r, x, y):
    best = 1e18
    n = len(r)
    for i in range(n):
        (ax, ay), (bx, by) = r[i], r[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-12
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        best = min(best, math.hypot(ax + t * dx - x, ay + t * dy - y))
    return best


def _dom_of_real(m, x, y):
    ds = [d for d in m["doms"] if d.get("poly")]
    own = [d for d in ds if _in_ring(d["poly"], x, y) and not any(_in_ring(h, x, y) for h in d.get("holes") or ())]
    if own:
        return min(own, key=lambda d: abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(d["poly"], d["poly"][1:] + d["poly"][:1]))))
    return min(ds, key=lambda d: _ring_dist(d["poly"], x, y))


def page_of(m, x, y):
    """Real map px -> page px on a v2 map (m["doms"]: mapping tables, page angle a, origin o)."""
    from .palace_grid import mapping_from
    d = _dom_of_real(m, x, y)
    lx, ly = mapping_from(d["mapping"])(x, y)
    a = math.radians(d.get("a") or 0.0)
    c, s_ = math.cos(a), math.sin(a)
    o = d.get("o") or (0.0, 0.0)
    return (lx * c - ly * s_ + o[0], lx * s_ + ly * c + o[1])


def real_of(m, X, Y):
    """Page px -> real map px (the inverse of to_px's mapping), on a v1 or a v2 map; None when the map has neither."""
    from .city_report import unmap
    if m.get("doms"):
        doms = m["doms"]
        d = next((d for d in doms if d.get("clip") and _in_ring(d["clip"], X, Y)), None) or \
            next((d for d in doms if not d.get("clip")), doms[0])
        a = math.radians(d.get("a") or 0.0)
        c, s_ = math.cos(a), math.sin(a)
        o = d.get("o") or (0.0, 0.0)
        dx, dy = X - o[0], Y - o[1]
        lx, ly = dx * c + dy * s_, -dx * s_ + dy * c
        return unmap(d["mapping"], lx, ly)
    if m.get("grid"):
        return unmap(m["grid"], X, Y)
    return None


MIGRATE_MAX = 1.5            # blocks: a saved lot farther than this from every new lot is not carried over


def migrate(old_m, old_blocks, new_m, new_blocks, keys):
    """Saved building lots ("<block>.<lot>") of an old city drawing -> lots of the new drawing (the city was set up
    again: block numbers change). A lot that existed before goes to the free new lot nearest the same real place
    (old page -> real -> new page). -> {old key: new key or None}; None (the old lot is gone, or either map has no
    mapping) means: drop the fixed lot, the building is placed afresh — never a stale key that now points elsewhere."""
    from .palace_grid import CW
    old = {f"{b['id']}.{k}": lt for b in old_blocks or () for k, lt in enumerate(b["lots"])}
    new = [(f"{b['id']}.{k}", lt[0], lt[1]) for b in new_blocks or () for k, lt in enumerate(b["lots"])]
    cell = 400.0
    idx = {}
    for key, x, y in new:
        idx.setdefault((int(x // cell), int(y // cell)), []).append((key, x, y))
    out, taken = {}, set()
    for key in keys:
        lt = old.get(key)
        rp = real_of(old_m, lt[0], lt[1]) if lt else None
        if rp is None or not (new_m.get("doms") or new_m.get("grid")):
            out[key] = None
            continue
        px, py = (page_of(new_m, *rp) if new_m.get("doms") else to_px_real(new_m, *rp))
        best = None
        ci, cj = int(px // cell), int(py // cell)
        R = int(MIGRATE_MAX * CW // cell) + 1
        for i in range(ci - R, ci + R + 1):
            for j in range(cj - R, cj + R + 1):
                for k2, x, y in idx.get((i, j), ()):
                    if k2 in taken:
                        continue
                    d = math.hypot(x - px, y - py)
                    if d <= MIGRATE_MAX * CW and (best is None or d < best[0]):
                        best = (d, k2)
        out[key] = best[1] if best else None
        if best:
            taken.add(best[1])
    return out


def to_px_real(m, x, y):
    """Real map px -> page px on a v1 map (the even grid's tables)."""
    from .palace_grid import mapping_from
    return mapping_from(m["grid"])(x, y) if m.get("grid") else (x, y)


def district_box(m, d) -> tuple:
    """A district's box in map px from its [south, west, north, east]. The city is
    drawn turned square to its streets, so the district's real rectangle comes out
    a little tilted; the box is the largest upright rectangle INSIDE it (not the one
    around it, which would reach a block or two past every edge, far south of a
    district that stops at South Street). Falls back to the box around when the
    inscribed one is under a block."""
    s, w, n, e = d["bounds"]
    sw, se, nw, ne = to_px(m, s, w), to_px(m, s, e), to_px(m, n, w), to_px(m, n, e)
    pts = (sw, se, nw, ne)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    around = (min(xs), min(ys), max(xs), max(ys))
    x0, x1 = max(sw[0], nw[0]), min(se[0], ne[0])
    y0, y1 = max(nw[1], ne[1]), min(sw[1], se[1])
    if x1 - x0 < 150 or y1 - y0 < 110:
        return around
    return (x0, y0, x1, y1)


def walk(blocks, box, start=None):
    """The blocks inside a district in walking order: serpentine rows (about
    two blocks tall) across the district's long side, starting at the end
    nearest `start` (a point, e.g. where the previous district ended)."""
    x0, y0, x1, y1 = box
    inside = [b for b in blocks if x0 <= b["x"] <= x1 and y0 <= b["y"] <= y1]
    if not inside:
        return []
    wide = (x1 - x0) >= (y1 - y0)
    band = 230
    def along(b): return b["x"] if wide else b["y"]
    def across(b): return b["y"] if wide else b["x"]
    lo = y0 if wide else x0
    rows: dict = {}
    for b in inside:
        rows.setdefault(int((across(b) - lo) // band), []).append(b)
    order = []
    flip = False
    if start is not None:
        sx, sy = start
        # start at whichever end of the first row is nearer
        flip = (sx if wide else sy) > ((x0 + x1) / 2 if wide else (y0 + y1) / 2)
    for k in sorted(rows):
        r = sorted(rows[k], key=along, reverse=flip)
        order.extend(r); flip = not flip
    return order


def place(m, blocks, units, districts, fixed=None) -> dict:
    """{node id: lot key} for every building.

    units: [[building id, ...] per unit, in reading order] — the unit's first
    building is its hub. districts: [{unit, bounds, name?}] (unit = index).
    fixed: {id: lot key} the author (or an edit) chose; those are kept when the
    lot exists and is free, and the rest are walked around them."""
    fixed = fixed or {}
    by_key = {f"{b['id']}.{k}": (b, k) for b in blocks for k in range(len(b["lots"]))}
    taken_blocks: dict = {}
    out = {}
    for nid, key in fixed.items():
        if key in by_key and key not in out.values():
            out[nid] = key
            taken_blocks[by_key[key][0]["id"]] = taken_blocks.get(by_key[key][0]["id"], 0) + 1
    dmap = {d["unit"]: d for d in districts}
    prev = None
    used = set(out.values())
    for ui, ids in enumerate(units):
        need = [i for i in ids if i not in out]
        if not need:
            continue
        d = dmap.get(ui)
        box = district_box(m, d) if d else (0, 0, m["W"], m["H"])
        order = [b for b in walk(blocks, box, prev) if b["id"] not in taken_blocks]
        # the buildings stand PER to a block, like row houses; a small district (a tight real boundary) with
        # fewer blocks than that needs stacks them more to a block (up to its lots) before anything spills out of it
        n = len(need)
        per = PER
        if order and len(order) * per < n:
            per = min(max(len(b["lots"]) for b in order), -(-n // len(order)))
        if len(order) * per < n:           # a crowded district spills into lots of taken blocks, then anywhere
            order += [b for b in walk(blocks, box, prev) if b["id"] in taken_blocks]
            order += [b for b in blocks if b not in order]
        # the blocks spread evenly along the walk
        N = len(order)
        nb = max(1, -(-n // per))
        chosen = [order[min(N - 1, int((j + .5) * N / nb))] for j in range(nb)] if nb <= N else order
        slots = []
        for b in chosen:
            free = [f"{b['id']}.{k}" for k in range(len(b["lots"])) if f"{b['id']}.{k}" not in used]
            slots += free[:per]
        for nid in need:
            key = slots.pop(0) if slots else next((k for k in by_key if k not in used), None)
            if key is None:
                continue
            out[nid] = key; used.add(key)
            taken_blocks[by_key[key][0]["id"]] = 1
        last = by_key[out[need[-1]]][0]
        prev = (last["x"], last["y"])
    return out
