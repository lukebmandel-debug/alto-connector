"""Fill-in: the rest of the city as simulated buildings, on a slider (brief.palace.fill_z; absent = off).

The Mind Palace draws only the user's own buildings (numbered cards on lots), the landmark art and the
towers. Fill-in adds the city's real building footprints (OpenStreetMap building=* ways) inside the
user's reach (their districts plus about 1 km), carried onto the graph paper by the same mapping the
streets go through — per domain on the v2 city engine (a tilted district's lattice) — clipped inside
their block, and drawn as calm frosted glass that never looks like (and never stands on) one of the
user's buildings.

  Level 0  Landmarks       nothing added (the page as it was)
  Level 1  Skyline         towers: height >= 60 m (or >= 18 storeys)            SVG, named on hover
  Level 2  Notable         + tall (>= 25 m), named non-houses, civic / large    SVG, named on hover
  Level 3  Most            + every footprint >= 300 m2 or >= 14 m              one window-sized canvas
  Level 4  Every building  + every footprint >= 20 m2 (row houses)             one window-sized canvas

New palaces open on level 1 (fill["lvl"]); a viewer's own choice is kept per timeline in localStorage.
Nothing is emitted unless fill_z is present, so a page without it is byte-identical to before.

Packed form (fill_data): {"v": 2, "doms": [[a, ox, oy], ...], "q": [q1..q4], "L": [s1..s4], "h": [digits, digits],
"n": [[index steps, names joined by |], ...], "ch": [cw, ch], "c": [n1..n4], "lvl": 1}. Each level string is its order k
(one character) and then exp-Golomb codes of order k, six bits a base64url character (zigzag for signed): sections [dom, count] of records, each
anchored as a delta from the previous record (local lattice units of q px):
  header & 3 == 0  rect          dx dy w h
  header & 3 == 1  strip         o = (h>>2)&3, u = (h>>4)&1, k = (h>>5)+2: dx dy, then (u: one depth, then k x along;
                                 else k x (along, across)) — houses side by side on one front (o: 0 top, 1 bottom, 2 left, 3 right)
  header & 3 == 2  rectilinear   n = 2*(h>>2)+6 vertices: dx dy, n-2 signed edge lengths (h, v, h, ...)
  header & 3 == 3  polygon       h>>2 == 0: a turned box: dx dy, angle (zigzag, 90/64 degree steps), w, h;
                                 else n = (h>>2)+2 vertices: dx dy, (n-1) x (ddx, ddy)
"""
from __future__ import annotations

import math
from bisect import bisect_right

from .. import palace_map as pmap
from .palace_grid import mapping_from          # read-only use: the grid's own Mapping (and a v2 domain's tables)

TIER_NAMES = ["Landmarks", "Skyline", "Notable", "Most", "Every building"]
CIVIC = {"cathedral", "church", "hospital", "university", "college", "school", "stadium", "train_station",
         "museum", "civic", "government", "public", "hotel", "office", "commercial", "retail", "transportation"}
HOUSES = {"house", "terrace", "semidetached_house", "detached", "garage", "garages", "shed", "roof", "hut"}
QUANT = (1, 2, 2, 3)              # local px per stored unit, levels 1..4 (about 1-1.5 m at levels 2-4: below what a row house needs)
INSET = 12.0                      # px between a footprint and its block's streets (the lots' own front gap)
REACH_KM = 1.0                    # the densest levels reach this far past the user's districts
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


# ── what a building is ──────────────────────────────────────────────────────
def _num(v):
    try:
        return float(str(v).replace(",", ".").split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def height_of(tags) -> float:
    h = _num(tags.get("height"))
    lv = _num(tags.get("building:levels"))
    return max(h or 0.0, (lv or 0.0) * 3.3)


def tier_of(tags, area_m2: float, h: float):
    """1..4 (the lowest level that shows it), or None (too small to draw)."""
    if area_m2 < 20:
        return None
    b = str(tags.get("building") or tags.get("building:part") or "yes")
    if h >= 60:
        return 1
    if h >= 25 or area_m2 >= 2500 or (b in CIVIC and area_m2 >= 600) or (tags.get("name") and b not in HOUSES and area_m2 >= 150):
        return 2
    if area_m2 >= 300 or h >= 14:
        return 3
    return 4 if area_m2 >= 30 else None           # a shed or a garage behind the row is left out


def _rings(e):
    if e.get("type") == "way":
        g = e.get("geometry") or []
        return [[(p["lat"], p["lon"]) for p in g if p]] if len(g) >= 3 else []
    out = []
    for m in e.get("members") or ():
        if m.get("role") == "outer" and len(m.get("geometry") or []) >= 3:
            out.append([(p["lat"], p["lon"]) for p in m["geometry"] if p])
    return out


def _area_m2(ring):
    lat0 = ring[0][0]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    pts = [(lon * kx, lat * ky) for lat, lon in ring]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def buildings(raw):
    """[(ring [(lat, lon)], tags, area m2, height m)] — a building:part's height lifts the building it stands in."""
    parts, out = [], []
    for e in raw.get("elements") or []:
        t = e.get("tags") or {}
        rings = _rings(e)
        if not rings:
            continue
        if "building" not in t:
            if "building:part" in t:
                r = rings[0]
                parts.append((sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r), height_of(t)))
            continue
        for r in rings:
            out.append([r, t, _area_m2(r), height_of(t)])
    if parts:
        cell: dict = {}
        box = []
        for k, (r, *_x) in enumerate(out):
            la, lo = [p[0] for p in r], [p[1] for p in r]
            box.append((min(la), min(lo), max(la), max(lo)))
            cell.setdefault((int(box[-1][0] * 500), int(box[-1][1] * 500)), []).append(k)
        for la, lo, h in parts:
            for k in cell.get((int(la * 500), int(lo * 500)), []):
                a, b, c, d = box[k]
                if a <= la <= c and b <= lo <= d and h > out[k][3]:
                    out[k][3] = h
    return out


# ── where: the user's reach ─────────────────────────────────────────────────
def reach(districts, bbox, km: float = REACH_KM):
    """(s, w, n, e): the districts' bounds grown by km, inside the city's box (the whole box without districts)."""
    bs = [d["bounds"] for d in districts or () if isinstance(d, dict) and isinstance(d.get("bounds"), (list, tuple))]
    if not bs:
        return tuple(float(v) for v in bbox)
    s, w = min(b[0] for b in bs), min(b[1] for b in bs)
    n, e = max(b[2] for b in bs), max(b[3] for b in bs)
    dla = km / 110.574
    dlo = km / (111.320 * math.cos(math.radians((s + n) / 2)))
    return (max(bbox[0], s - dla), max(bbox[1], w - dlo), min(bbox[2], n + dla), min(bbox[3], e + dlo))


# ── domains: the grid (v1) or each lattice of the v2 city engine ───────────
def _in_ring(r, x, y):
    c, n = False, len(r)
    for i in range(n):
        (x0, y0), (x1, y1) = r[i], r[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _ring_d2(r, x, y):
    return min((px - x) ** 2 + (py - y) ** 2 for px, py in r) if r else 1e30


class Dom:
    """One lattice: real px -> local lattice px (its Mapping), local -> page (turned by a degrees, moved by o).
    Columns at x0 + i*gv (nx of them), rows at y0 + j*gh."""

    def __init__(self, k, a, o, tables, x0, nx, gv, y0, ny, gh, clip=None, poly=None):
        self.k, self.a, self.o = k, float(a or 0.0), (float(o[0]), float(o[1]))
        self.mp = mapping_from(tables)
        self.x0, self.nx, self.gv, self.y0, self.ny, self.gh = x0, nx, gv, y0, ny, gh
        self.clip = [tuple(p) for p in clip] if clip else None
        self.poly = [tuple(p) for p in poly] if poly else None
        r = math.radians(self.a)
        self.c, self.s = math.cos(r), math.sin(r)

    def page(self, lx, ly):
        return (lx * self.c - ly * self.s + self.o[0], lx * self.s + ly * self.c + self.o[1])

    def to_local(self, X, Y):
        x, y = X - self.o[0], Y - self.o[1]
        return (x * self.c + y * self.s, -x * self.s + y * self.c)

    def cell(self, lx, ly):
        i, j = math.floor((lx - self.x0) / self.gv), math.floor((ly - self.y0) / self.gh)
        return (i, j) if 0 <= i < self.nx - 1 and 0 <= j < self.ny - 1 else None

    def rect(self, i, j):
        return (self.x0 + i * self.gv, self.y0 + j * self.gh, self.x0 + (i + 1) * self.gv, self.y0 + (j + 1) * self.gh)


def domains(m) -> list:
    """The map's lattices: m["doms"] (engine v2: mapping tables, page angle a, origin o, cwch, xg/yg = [first, count],
    clip = the child's page ring, poly = its real ring) or the one v1 grid."""
    if m.get("doms"):
        return [Dom(k, d.get("a"), d.get("o") or (0, 0), d["mapping"], float(d["xg"][0]), int(d["xg"][1]), float(d["cwch"][0]),
                    float(d["yg"][0]), int(d["yg"][1]), float(d["cwch"][1]), d.get("clip"), d.get("poly"))
                for k, d in enumerate(m["doms"])]
    g = m["grid"]
    xg, yg = g["xg"], g["yg"]
    return [Dom(0, 0.0, (0.0, 0.0), g, float(xg[0]), len(xg), float(xg[1] - xg[0]) if len(xg) > 1 else 240.0,
                float(yg[0]), len(yg), float(yg[1] - yg[0]) if len(yg) > 1 else 170.0)]


def _owners(doms):
    kids = [d for d in doms if d.clip]
    root = next((d for d in doms if not d.clip), doms[0])

    def by_page(X, Y):
        for d in kids:
            if _in_ring(d.clip, X, Y):
                return d
        return root

    def by_real(x, y):
        if len(doms) == 1:
            return doms[0]
        best, bd = None, 1e30
        for d in doms:
            if d.poly and _in_ring(d.poly, x, y):
                return d
            dd = _ring_d2(d.poly, x, y)
            if dd < bd:
                best, bd = d, dd
        return best or root
    return by_page, by_real


# ── shapes ──────────────────────────────────────────────────────────────────
def _clip(poly, x0, y0, x1, y1):
    for axis, val, ge in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
        poly = pmap._clip_edge(poly, axis, val, ge)
        if not poly:
            return []
    return poly if len(poly) >= 3 else []


def _snap(pts, tol=math.tan(math.radians(8))):
    """A footprint whose every edge is within 8 degrees of the lattice's axes, made exactly rectilinear (a real
    building square to its streets stays square: the mapping is a turn and then separate in x and y)."""
    ori = []
    n = len(pts)
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        dx, dy = abs(bx - ax), abs(by - ay)
        ori.append("h" if dy <= tol * dx else "v" if dx <= tol * dy else None)
    if None in ori:
        return pts
    # merge runs of one orientation (drop the vertex between two h edges, or two v edges)
    keep = [pts[i] for i in range(n) if ori[i - 1] != ori[i]]
    if len(keep) < 4 or len(keep) % 2:
        return pts
    n = len(keep)
    o0 = "h" if abs(keep[1][1] - keep[0][1]) <= tol * abs(keep[1][0] - keep[0][0]) else "v"
    out = []
    for i in range(n):
        a, b, p = keep[i - 1], keep[(i + 1) % n], keep[i]
        hor = (o0 == "h") == (i % 2 == 0)             # edge i (p -> next) is horizontal
        if hor:                                         # y from this edge, x from the edge before (vertical)
            out.append(((a[0] + p[0]) / 2, (p[1] + b[1]) / 2))
        else:
            out.append(((p[0] + b[0]) / 2, (a[1] + p[1]) / 2))
    return out


def _clean(q):
    """Integer ring: no repeated points, no straight-through vertices."""
    out = []
    for p in q:
        if not out or p != out[-1]:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    changed = True
    while changed and len(out) >= 3:
        changed = False
        for i in range(len(out)):
            a, p, b = out[i - 1], out[i], out[(i + 1) % len(out)]
            if (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0]) == 0:
                out.pop(i)
                changed = True
                break
    return out if len(out) >= 3 else []


def _rectilinear(q):
    n = len(q)
    return n % 2 == 0 and all((q[i][0] == q[(i + 1) % n][0]) != (q[i][1] == q[(i + 1) % n][1]) for i in range(n))


def fill_data(raw, m, blocks=None, ins: float = INSET, chunk: int = 4) -> dict:
    """Footprints on the graph paper, packed. Each building goes into the domain that owns its real centre, through
    that domain's mapping into the block (cell) its centre falls in, snapped square where it is nearly square, and
    clipped `ins` px inside the block's streets. None in a landmark's block, in a park, outside a block (a cell
    with a drawn tile or lots), or where its domain does not own the page (the far side of a seam)."""
    bbox, scale = m["bbox"], m.get("scale", 1.0)
    doms = domains(m)
    by_page, by_real = _owners(doms)
    valid = set()
    for X, Y in [((t[0] + t[2]) / 2, (t[1] + t[3]) / 2) for t in m.get("tiles") or []] + [(b["x"], b["y"]) for b in blocks or ()]:
        d = by_page(X, Y)
        ij = d.cell(*d.to_local(X, Y))
        if ij:
            valid.add((d.k, ij))
    lmb = [l["box"] for l in m.get("landmarks") or [] if l.get("box")]
    parks = []
    for pk in m.get("parks") or []:
        for r in pk.get("r") or []:
            ring = list(zip(r[0::2], r[1::2]))
            if len(ring) >= 3:
                xs, ys = [p[0] for p in ring], [p[1] for p in ring]
                parks.append((min(xs), min(ys), max(xs), max(ys), ring))

    def blocked(X, Y):
        if any(b[0] <= X <= b[2] and b[1] <= Y <= b[3] for b in lmb):
            return True
        return any(p[0] <= X <= p[2] and p[1] <= Y <= p[3] and _in_ring(p[4], X, Y) for p in parks)

    recs = [[], [], [], []]              # per level: (dom, j, i, points in units, height, name)
    turned = []                          # turned boxes (levels 3-4): (level, dom, cell, mbr, height)
    for ring, tags, area, h in buildings(raw):
        t = tier_of(tags, area, h)
        if t is None:
            continue
        real = [pmap.project(la, lo, bbox, scale) for la, lo in ring]
        if len(real) > 3 and real[0] == real[-1]:
            real = real[:-1]
        rx, ry = sum(p[0] for p in real) / len(real), sum(p[1] for p in real) / len(real)
        d = by_real(rx, ry)
        loc = [d.mp(x, y) for x, y in real]
        lx, ly = sum(p[0] for p in loc) / len(loc), sum(p[1] for p in loc) / len(loc)
        ij = d.cell(lx, ly)
        if not ij or (d.k, ij) not in valid:
            continue
        x0, y0, x1, y1 = d.rect(*ij)
        if blocked(*d.page((x0 + x1) / 2, (y0 + y1) / 2)) or blocked(*d.page(lx, ly)):
            continue
        if len(doms) > 1 and by_page(*d.page(lx, ly)) is not d:
            continue
        g = _clip(_snap(loc), x0 + ins, y0 + ins, x1 - ins, y1 - ins)
        if not g:
            continue
        if len(g) > 4 and not _rectilinear([(round(x), round(y)) for x, y in g]):
            if t >= 3:                                # the canvas levels: a nearly boxy building is drawn as its box
                xs_, ys_ = [p[0] for p in g], [p[1] for p in g]
                bx = (max(xs_) - min(xs_)) * (max(ys_) - min(ys_))
                ar = abs(pmap.ring_area(g))
                mb = _mbr(g)
                if bx > 0 and ar >= .78 * bx:
                    g = [(min(xs_), min(ys_)), (max(xs_), min(ys_)), (max(xs_), max(ys_)), (min(xs_), max(ys_))]
                elif mb and mb[0] > 0 and ar >= .7 * mb[0]:
                    if abs(mb[1]) > 20:
                        turned.append((t, d.k, ij, mb, h))
                        continue
                    # within 20 degrees of the lattice: squared to it (graph paper), same middle and size
                    r_ = math.radians(mb[1])
                    cx_ = mb[2][0] + (mb[3] * math.cos(r_) - mb[4] * math.sin(r_)) / 2
                    cy_ = mb[2][1] + (mb[3] * math.sin(r_) + mb[4] * math.cos(r_)) / 2
                    g = _clip([(cx_ - mb[3] / 2, cy_ - mb[4] / 2), (cx_ + mb[3] / 2, cy_ - mb[4] / 2), (cx_ + mb[3] / 2, cy_ + mb[4] / 2),
                               (cx_ - mb[3] / 2, cy_ + mb[4] / 2)], x0 + ins, y0 + ins, x1 - ins, y1 - ins)
                    if not g:
                        continue
                else:
                    g = pmap.simplify_ring(g, 3.0)
            else:
                g = pmap.simplify_ring(g, float(t))
        elif t >= 3 and len(g) > 4:                   # a nearly boxy rectilinear one too
            xs_, ys_ = [p[0] for p in g], [p[1] for p in g]
            bx = (max(xs_) - min(xs_)) * (max(ys_) - min(ys_))
            if bx > 0 and abs(pmap.ring_area(g)) >= .85 * bx:
                g = [(min(xs_), min(ys_)), (max(xs_), min(ys_)), (max(xs_), max(ys_)), (min(xs_), max(ys_))]
        q = QUANT[t - 1]
        u = _clean([(int(round(x / q)), int(round(y / q))) for x, y in g])
        if not u or abs(pmap.ring_area(u)) * q * q < 6:
            continue
        nm = str(tags.get("name") or "")[:60] if t <= 2 else ""
        recs[t - 1].append((d.k, ij[1], ij[0], u, int(round(min(h, 400))), nm))
    for t, dk, ij, (ar, ang, (cx, cy), bw, bh), h in turned:
        q = QUANT[t - 1]
        k_ = int(round(ang / (90 / 64)))
        if bw / q < .5 or bh / q < .5:
            continue
        recs[t - 1].append((dk, ij[1], ij[0], ("t", int(round(cx / q)), int(round(cy / q)), k_, max(1, int(round(bw / q))), max(1, int(round(bh / q)))), h, ""))
    L, H, N, C = [], [], [], []
    for lv in range(4):
        s, hs, ns, cnt = _encode(recs[lv], strips=lv >= 2)
        L.append(s)
        C.append(cnt)
        if lv < 2:
            # depth of the drawn side, one digit a record (px: height / 22, at most 9); the names: index steps and the names
            H.append("".join(str(min(9, int(round(h / 22)))) for h in hs))
            ix = sorted(int(k) for k in ns)
            N.append([",".join(str(b - a) for a, b in zip([0] + ix, ix)), "|".join(ns[str(k)].replace("|", "/") for k in ix)])
    return {"v": 2, "doms": [[round(d.a, 4), round(d.o[0], 2), round(d.o[1], 2)] for d in doms], "q": list(QUANT),
            "L": L, "h": H, "n": N, "c": C, "ch": [chunk * doms[0].gv, chunk * doms[0].gh], "lvl": 0}


# ── the stream ──────────────────────────────────────────────────────────────
def _mbr(pts):
    """The smallest turned box round a ring: (area, angle deg in [-45, 45), corner (x, y), w, h) or None. The box is
    corner + [0, w] along the angle's direction + [0, h] across it."""
    best = None
    n = len(pts)
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        if math.hypot(bx - ax, by - ay) < 1e-9:
            continue
        th = math.atan2(by - ay, bx - ax)
        ux, uy = math.cos(th), math.sin(th)
        us = [x * ux + y * uy for x, y in pts]
        vs = [-x * uy + y * ux for x, y in pts]
        a = (max(us) - min(us)) * (max(vs) - min(vs))
        if best is None or a < best[0]:
            best = (a, math.degrees(th))
    if not best:
        return None
    ang = (best[1] + 45) % 90 - 45
    r = math.radians(ang)
    ux, uy = math.cos(r), math.sin(r)
    us = [x * ux + y * uy for x, y in pts]
    vs = [-x * uy + y * ux for x, y in pts]
    u0, v0 = min(us), min(vs)
    return best[0], ang, (u0 * ux - v0 * uy, u0 * uy + v0 * ux), max(us) - u0, max(vs) - v0


def _zz(v):
    return v * 2 if v >= 0 else -v * 2 - 1


class _W:
    """The level's numbers, written at the end as exp-Golomb codes of order k (the k that is shortest for them),
    six bits a character."""
    def __init__(self):
        self.out = []

    def u(self, v):
        self.out.append(v)

    def s(self, v):
        self.out.append(_zz(v))

    @staticmethod
    def bits(v, k):
        return 2 * (v + (1 << k)).bit_length() - 1 - k

    def text(self):
        if not self.out:
            return 0, ""
        k = min(range(6), key=lambda k: sum(self.bits(v, k) for v in self.out))
        acc, n, chars = 0, 0, []
        for v in self.out:
            x = v + (1 << k)
            nb = x.bit_length()
            acc = (acc << (2 * nb - 1 - k)) | x            # nb-1-k zeros, then x in nb bits
            n += 2 * nb - 1 - k
            while n >= 6:
                n -= 6
                chars.append(B64[(acc >> n) & 63])
            acc &= (1 << n) - 1
        if n:
            chars.append(B64[(acc << (6 - n)) & 63])
        return k, "".join(chars)


def _strips(rects):
    """Chains of houses side by side on one front: [(o, front, [rect, ...])] (o: 0 top, 1 bottom, 2 left, 3 right), and
    the rects left over. A rect is (x0, y0, x1, y1, index). A house may stand one unit off its neighbour's front or
    wall (the decoded house keeps its own far edges)."""
    used, out = set(), []
    spec = ((0, 1, 0, 2), (1, 3, 0, 2), (2, 0, 1, 3), (3, 2, 1, 3))      # o, front coord, along start, along end
    for o, fi, a0, a1 in spec:
        free = [r for r in rects if r[4] not in used]
        at = {}
        for r in free:
            at.setdefault((r[fi], r[a0]), []).append(r)
        for r in sorted(free, key=lambda r: (r[fi], r[a0])):
            if r[4] in used:
                continue
            ch, front = [r], r[fi]
            while True:
                end, nxt = ch[-1][a1], None
                for df in (0, -1, 1):
                    for de in (0, -1, 1):
                        for q in at.get((front + df, end + de), ()):
                            if q[4] not in used and q is not ch[-1] and all(q is not c for c in ch) and q[a1] > end:
                                nxt = q
                                break
                        if nxt:
                            break
                    if nxt:
                        break
                if not nxt:
                    break
                ch.append(nxt)
            if len(ch) >= 2:
                out.append((o, front, ch))
                used.update(c[4] for c in ch)
    return out, [r for r in rects if r[4] not in used]


STATS = None                      # {kind: [records, chars]} when set (the report's size breakdown)


def _encode(recs, strips=True):
    """recs [(dom, j, i, ring units, height, name)] -> (stream, heights in record order, {index: name}, shapes)."""
    w, hs, ns = _W(), [], {}
    items = []                                   # (dom, j, i, ay, ax, kind payload)
    rects = {}
    for k, (dk, j, i, u, h, nm) in enumerate(recs):
        if isinstance(u, tuple) and u and u[0] == "t":
            items.append((dk, j, i, u[2], u[1], u, h, nm))
            continue
        xs, ys = [p[0] for p in u], [p[1] for p in u]
        if len(u) == 4 and _rectilinear(u):
            if strips:
                rects.setdefault((dk, j, i), []).append((min(xs), min(ys), max(xs), max(ys), k))
                continue
            items.append((dk, j, i, min(ys), min(xs), ("r", min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), h, nm))
            continue
        if _rectilinear(u):
            s = next(n for n in range(len(u)) if u[n][1] == u[(n + 1) % len(u)][1])     # edge 0 horizontal
            v = u[s:] + u[:s]
            items.append((dk, j, i, v[0][1], v[0][0], ("x", v), h, nm))
        else:
            items.append((dk, j, i, u[0][1], u[0][0], ("p", u), h, nm))
    for (dk, j, i), rs in rects.items():
        chains, rest = _strips(rs)
        for o, front, ch in chains:
            ax, ay = (ch[0][0], front) if o < 2 else (front, ch[0][1])
            items.append((dk, j, i, ay, ax, ("s", o, ch), 0, ""))
        for r in rest:
            items.append((dk, j, i, r[1], r[0], ("r", r[0], r[1], r[2] - r[0], r[3] - r[1]), 0, ""))
    items.sort(key=lambda t: (t[0], t[1], t[2], t[3], t[4]))
    shapes = 0
    k = 0
    while k < len(items):
        dk = items[k][0]
        sec = [it for it in items[k:] if it[0] == dk]
        sec = sec[:next((n for n, it in enumerate(sec) if it[0] != dk), len(sec))]
        w.u(dk)
        w.u(len(sec))
        px = py = 0
        for it in sec:
            ax, ay, pay = it[4], it[3], it[5]
            n0 = len(w.out)
            if pay[0] == "r":
                w.u(0)
                w.s(ax - px)
                w.s(ay - py)
                w.u(pay[3])
                w.u(pay[4])
                shapes += 1
            elif pay[0] == "s":
                o, ch = pay[1], pay[2]
                acs = [max(1, (r[3] - ay, ay - r[1], r[2] - ax, ax - r[0])[o]) for r in ch]
                one = max(acs) - min(acs) <= 1            # one depth for the row (its backs within a unit of each other)
                w.u(1 | (o << 2) | (int(one) << 4) | ((len(ch) - 2) << 5))
                w.s(ax - px)
                w.s(ay - py)
                if one:
                    w.u(sorted(acs)[len(acs) // 2])
                cur = ax if o < 2 else ay
                for r, ac in zip(ch, acs):               # along: to the house's own far wall; across: to its own back
                    al = max(1, (r[2] if o < 2 else r[3]) - cur)
                    w.u(al)
                    if not one:
                        w.u(ac)
                    cur += al
                shapes += len(ch)
            elif pay[0] == "x":
                v = pay[1]
                w.u(2 | (((len(v) - 6) // 2) << 2))
                w.s(ax - px)
                w.s(ay - py)
                for n in range(len(v) - 2):
                    a, b = v[n], v[n + 1]
                    w.s(b[0] - a[0] if n % 2 == 0 else b[1] - a[1])
                shapes += 1
            elif pay[0] == "t":
                w.u(3)
                w.s(ax - px)
                w.s(ay - py)
                w.s(pay[3])
                w.u(pay[4])
                w.u(pay[5])
                shapes += 1
            else:
                v = pay[1]
                w.u(3 | ((len(v) - 2) << 2))
                w.s(ax - px)
                w.s(ay - py)
                for a, b in zip(v, v[1:]):
                    w.s(b[0] - a[0])
                    w.s(b[1] - a[1])
                shapes += 1
            if STATS is not None:
                st = STATS.setdefault(pay[0] + ("%d" % len(pay[2]) if pay[0] == "s" and len(pay[2]) < 4 else ""), [0, 0, 0])
                st[0] += 1
                st[1] += len(w.out) - n0
                st[2] += len(pay[2]) if pay[0] == "s" else 1
            if it[7]:
                ns[str(len(hs))] = it[7]
            hs.append(it[6])
            px, py = ax, ay
        k += len(sec)
    k, txt = w.text()
    return (B64[k] + txt) if txt else "", hs, ns, shapes


def decode(f, level):
    """The shapes of one level as page rings [(x, y), ...] (the page's own decoder, in Python: tests and the report)."""
    s, q = f["L"][level - 1], f["q"][level - 1]
    vals = []
    if s:
        k, bits = B64.index(s[0]), "".join(format(B64.index(c), "06b") for c in s[1:])
        i = 0
        while True:
            z = bits.find("1", i)
            if z < 0 or z + (z - i) + k + 1 > len(bits):
                break
            nb = (z - i) + k + 1
            vals.append(int(bits[z:z + nb], 2) - (1 << k))
            i = z + nb
    it = iter(vals)

    def z():
        u = next(it)
        return (u >> 1) ^ -(u & 1)
    out = []
    for dk in it:
        a, ox, oy = f["doms"][dk]
        c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))

        def pg(x, y):
            x, y = x * q, y * q
            return (x * c - y * s_ + ox, x * s_ + y * c + oy)
        px = py = 0
        for _ in range(next(it)):
            hd = next(it)
            kind = hd & 3
            ax, ay = px + z(), py + z()
            px, py = ax, ay
            if kind == 0:
                w_, h_ = next(it), next(it)
                out.append([pg(ax, ay), pg(ax + w_, ay), pg(ax + w_, ay + h_), pg(ax, ay + h_)])
            elif kind == 1:
                o, one, k = (hd >> 2) & 3, (hd >> 4) & 1, (hd >> 5) + 2
                dep = next(it) if one else None
                cur = ax if o < 2 else ay
                for _k in range(k):
                    al = next(it)
                    ac = dep if one else next(it)
                    if o == 0:
                        r = (cur, ay, cur + al, ay + ac)
                    elif o == 1:
                        r = (cur, ay - ac, cur + al, ay)
                    elif o == 2:
                        r = (ax, cur, ax + ac, cur + al)
                    else:
                        r = (ax - ac, cur, ax, cur + al)
                    cur += al
                    out.append([pg(r[0], r[1]), pg(r[2], r[1]), pg(r[2], r[3]), pg(r[0], r[3])])
            elif kind == 2:
                n = 2 * (hd >> 2) + 6
                pts, x, y = [(ax, ay)], ax, ay
                for e in range(n - 2):
                    if e % 2 == 0:
                        x += z()
                    else:
                        y += z()
                    pts.append((x, y))
                pts.append((ax, y))                   # the last two edges close the ring
                out.append([pg(*p) for p in pts])
            elif hd >> 2 == 0:
                k_, bw, bh = z(), next(it), next(it)
                r_ = math.radians(k_ * 90 / 64)
                ux, uy = math.cos(r_), math.sin(r_)
                out.append([pg(ax, ay), pg(ax + bw * ux, ay + bw * uy), pg(ax + bw * ux - bh * uy, ay + bw * uy + bh * ux), pg(ax - bh * uy, ay + bh * ux)])
            else:
                n = (hd >> 2) + 2
                pts, x, y = [(ax, ay)], ax, ay
                for _e in range(n - 1):
                    x += z()
                    y += z()
                    pts.append((x, y))
                out.append([pg(*p) for p in pts])
    return out


def counts(fill) -> list:
    """Shapes each level adds: [L1, L2, L3, L4]."""
    return list(fill.get("c") or [0, 0, 0, 0])


def fill_for(m, blocks, districts, bbox, cache_dir=None, level: int = 1):
    """set_up's step: fetch the footprints of the reach (districts + REACH_KM) and pack them; None when there are none."""
    from .palace import pack
    box = reach(districts, bbox)
    raw = pmap.fetch_buildings(box, cache_dir=cache_dir)
    f = fill_data(raw, m, blocks)
    if not sum(counts(f)):
        return None
    f["lvl"] = level
    f["reach"] = [round(v, 5) for v in box]
    if raw.get("missing"):
        f["missing"] = raw["missing"]
    return pack(f)


# ── the page (only when the palace has fill_z) ─────────────────────────────
FILL_CSS = r"""
  .pal-svg .pl-fill{pointer-events:none;}
  .pal-svg .pl-fill .f-body{fill:rgba(255,255,255,.72);stroke-linejoin:round;stroke-width:calc(var(--tw,1) * 1.15px);stroke-opacity:.78;}
  .pal-svg .pl-fill .f-side{fill:rgba(28,34,62,.13);stroke:none;}
  .pal-svg .pl-fill .ft3 .f-body,.pal-svg .pl-fill .ft4 .f-body{fill:rgba(255,255,255,.46);stroke-opacity:.5;}
  html.dark .pal-svg .pl-fill .f-body{fill:rgba(60,64,84,.5);}
  html.dark .pal-svg .pl-fill .f-side{fill:rgba(0,0,0,.28);}
  .pal-svg .pl-fhit{fill:none;stroke:none;pointer-events:none;}
  #pal-fillc{position:absolute;left:0;top:0;z-index:0;pointer-events:none;transition:opacity .3s;will-change:transform;}   /* its own layer: moving or redrawing it never repaints the city under it (pan p90 166 -> 17 ms at 2400x1600) */
  #canvas.focus-mode #pal-fillc{opacity:.55;}
  html.alto-editing .pal-svg .pl-fill,html.alto-editing #pal-fillc{opacity:.45;}
  #pal-key .pk-fill{display:block;box-sizing:border-box;width:100%;padding:5px 3px 3px;cursor:default;}
  #pal-key .pk-fill .pkf-h{display:flex;justify-content:space-between;align-items:baseline;gap:6px;min-width:0;}
  #pal-key .pk-fill .pkf-h b{font-weight:650;white-space:nowrap;}
  #pal-key .pk-fill .pkf-v{white-space:nowrap;opacity:.75;flex:none;}
  #pal-key .pk-fill input[type=range]{display:block;box-sizing:border-box;width:100%;max-width:100%;margin:6px 0 2px;accent-color:var(--accent,#5b6cff);}
  #pal-key .pk-fill .pkf-ticks{display:flex;justify-content:space-between;gap:6px;font-size:10px;opacity:.6;white-space:nowrap;}
  #pal-mmap .pkf-seg{display:flex;gap:4px;margin:4px 0 2px;padding:3px;border-radius:12px;background:color-mix(in srgb,var(--text) 6%,transparent);}
  #pal-mmap .pkf-seg button{flex:1;min-width:0;height:34px;border:0;border-radius:9px;background:transparent;color:var(--text);font:inherit;font-size:11.5px;font-weight:600;padding:0 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  #pal-mmap .pkf-seg button[aria-checked=true]{background:var(--surface);box-shadow:0 1px 3px rgba(0,0,0,.18);}
  #pal-mmap .pkf-note{display:block;font-size:11.5px;opacity:.7;margin:2px 2px 8px;}
"""

# function definitions, spliced inside the palace page's closure (palace_js below)
FILL_FUNCS = r"""
/* ── fill-in (palace_fillin.py): the rest of the city as simulated buildings, by level ── */
var FILL=window._ALTO_FILL||null, FILL_KEY='alto-palace-fill:'+location.pathname, FILL_NAMES=['Landmarks','Skyline','Notable','Most','Every building'];
var fillLevel=(function(){ var v=null; try{ v=localStorage.getItem(FILL_KEY); }catch(e){} v=v==null?(FILL&&FILL.lvl)||0:+v; return Math.max(0,Math.min(4,v|0)); })();
var FILL_ZMIN=[0, 0, 0, .07, .15];            /* a level shows from the zoom its smallest buildings are a couple of px across */
/* the packed footprints (palace_fillin._encode): page rings per level, each with its box, height and name */
var FS=null;
function fillShapes(){ if(FS || !FILL) return FS; FS=[null,[],[],[],[]];
  var AL='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_', D={}; for(var i=0;i<64;i++) D[AL.charCodeAt(i)]=i;
  for(var lv=1;lv<=4;lv++){ var s=FILL.L[lv-1]||'', q=FILL.q[lv-1], vals=[], H=(FILL.h||[])[lv-1]||'', NN=(FILL.n||[])[lv-1]||['',''], NM={};
    if(NN[0]){ var ix=0, st=NN[0].split(','), nm=NN[1].split('|'); for(i=0;i<st.length;i++){ ix+=+st[i]; NM[ix]=nm[i]; } }
    if(s){ var kk=D[s.charCodeAt(0)], nb=(s.length-1)*6, bp=0, bit=function(){ var c=D[s.charCodeAt(1+(bp/6|0))], b=(c>>(5-bp%6))&1; bp++; return b; };
      while(bp<nb){ var z=0, one=0; while(bp<nb){ if(bit()){ one=1; break; } z++; } if(!one) break; var x=1, m=z+kk; if(bp+m>nb) break; for(var e=0;e<m;e++) x=x*2+bit(); vals.push(x-Math.pow(2,kk)); } }
    var p=0, rec=0, out=FS[lv], U=function(){ return vals[p++]; }, Zs=function(){ var u=vals[p++]; return u%2?-(u+1)/2:u/2; };
    while(p<vals.length){ var dm=FILL.doms[U()], cnt=U(), ca=Math.cos(dm[0]*Math.PI/180), sa=Math.sin(dm[0]*Math.PI/180), ox=dm[1], oy=dm[2], px=0, py=0;
      var add=function(lp, k){ var pts=[], x0=1e9, y0=1e9, x1=-1e9, y1=-1e9; for(var n=0;n<lp.length;n+=2){ var x=lp[n]*q, y=lp[n+1]*q, X=x*ca-y*sa+ox, Y=x*sa+y*ca+oy; pts.push(X,Y);
          if(X<x0)x0=X; if(X>x1)x1=X; if(Y<y0)y0=Y; if(Y>y1)y1=Y; } out.push({p:pts, b:[x0,y0,x1,y1], h:k==null?0:(+H.charAt(k)||0), n:k==null?'':(NM[k]||'')}); };
      for(var r=0;r<cnt;r++,rec++){ var hd=U(), kind=hd&3, ax=px+Zs(), ay=py+Zs(); px=ax; py=ay;
        if(kind===0){ var w=U(), h=U(); add([ax,ay, ax+w,ay, ax+w,ay+h, ax,ay+h], rec); }
        else if(kind===1){ var o=(hd>>2)&3, one=(hd>>4)&1, k=(hd>>5)+2, dep=one?U():0, cur=o<2?ax:ay;
          for(var j=0;j<k;j++){ var al=U(), ac=one?dep:U(), R=o===0?[cur,ay,cur+al,ay+ac]:o===1?[cur,ay-ac,cur+al,ay]:o===2?[ax,cur,ax+ac,cur+al]:[ax-ac,cur,ax,cur+al]; cur+=al;
            add([R[0],R[1], R[2],R[1], R[2],R[3], R[0],R[3]], null); } }
        else if(kind===2){ var nn=2*(hd>>2)+6, lp=[ax,ay], x=ax, y=ay; for(var e=0;e<nn-2;e++){ if(e%2===0) x+=Zs(); else y+=Zs(); lp.push(x,y); } lp.push(ax,y); add(lp, rec); }
        else if((hd>>2)===0){ var an=Zs()*Math.PI/128, bw=U(), bh=U(), ux=Math.cos(an), uy=Math.sin(an); add([ax,ay, ax+bw*ux,ay+bw*uy, ax+bw*ux-bh*uy,ay+bw*uy+bh*ux, ax-bh*uy,ay+bh*ux], rec); }
        else { var nn=(hd>>2)+2, lp=[ax,ay], x=ax, y=ay; for(var e=0;e<nn-1;e++){ x+=Zs(); y+=Zs(); lp.push(x,y); } add(lp, rec); } } } }
  return FS; }
/* a building of the user's stands on its lot; nothing simulated touches it (8 px of clear glass round it, the lot's box turned with its domain) */
function fillTaken(){ var r=[]; Object.keys(P.at||{}).forEach(function(id){ var L=lot(P.at[id]); if(!L) return; var a=(L[4]||0)*Math.PI/180, c=Math.abs(Math.cos(a)), s=Math.abs(Math.sin(a)),
    hw=(L[2]*c+L[3]*s)/2+8, hh=(L[2]*s+L[3]*c)/2+8; r.push([L[0]-hw, L[1]-hh, L[0]+hw, L[1]+hh]); }); return r; }
function fillSig(){ return JSON.stringify(P.at||{}); }
/* per level: chunk -> district -> shapes not on a user's lot */
var FG=null, FGsig='';
function fillGroups(){ var sg=fillSig(); if(FG && FGsig===sg) return FG; FGsig=sg; FG=[null,{},{},{},{}]; var S=fillShapes(); if(!S) return FG;
  var CH=FILL.ch, taken=fillTaken(), grid={};
  taken.forEach(function(b){ for(var i=Math.floor(b[0]/CH[0]);i<=Math.floor(b[2]/CH[0]);i++) for(var j=Math.floor(b[1]/CH[1]);j<=Math.floor(b[3]/CH[1]);j++) (grid[i+','+j]=grid[i+','+j]||[]).push(b); });
  for(var lv=1;lv<=4;lv++) S[lv].forEach(function(s){ var b=s.b, ci=Math.floor((b[0]+b[2])/2/CH[0]), cj=Math.floor((b[1]+b[3])/2/CH[1]), key=ci+','+cj, tk=grid[key];
    if(tk) for(var q=0;q<tk.length;q++){ var t=tk[q]; if(b[0]<t[2] && b[2]>t[0] && b[1]<t[3] && b[3]>t[1]) return; }
    var C=FG[lv][key]||(FG[lv][key]={ci:ci, cj:cj, u:{}}), u=distAt((b[0]+b[2])/2,(b[1]+b[3])/2); (C.u[u]=C.u[u]||[]).push(s); });
  if(FC) FC.cache={}; return FG; }
function ringD(p){ var d='M'+p[0]+' '+p[1]; for(var k=2;k<p.length;k+=2) d+='L'+p[k]+' '+p[k+1]; return d+'Z'; }
/* levels 1-2 (and every level on the phone's map): SVG paths, merged per chunk, level and district */
function fillDraw(svg){ var t0=performance.now(); try{ fillDraw0(svg); } finally { window._fillMs=performance.now()-t0; } }
function fillDraw0(svg){
  var old=svg.querySelector(':scope > .pl-fill'); if(!FILL || !FILL.L){ if(old) old.remove(); return; }
  var G=fillGroups(), g=el('g',{'class':'pl-fill'}), top=svg===svgD?2:4;
  for(var t=1;t<=4;t++){ var tg=el('g',{'class':'ft ft'+t},g); if(t>top) continue;
    Object.keys(G[t]).forEach(function(k){ var C=G[t][k], cg=el('g',{'data-c':C.ci+','+C.cj},tg);
      Object.keys(C.u).forEach(function(u){ var b='', sd='', col=tubeCol(dcol(u==='null'?null:+u)||NEUTRAL());
        C.u[u].forEach(function(s){ b+=ringD(s.p); if(t<=2 && s.h>0){ var o=Math.max(1.5,s.h), q=s.p.map(function(v){ return v+o; }); sd+=ringD(q); } });
        if(sd) el('path',{'class':'f-side', d:sd},cg); el('path',{'class':'f-body', d:b, stroke:col},cg); }); }); }
  var anchor=svg.querySelector(':scope > .pl-river-g');
  if(old) old.remove(); svg.insertBefore(g, anchor||null); svg._fill=g; svg._fillSig=fillSig(); fillLOD(svg);
  if(svg===svgD){ if(FC) FC.cache={}; fillSoon(); }
}
function fillLOD(svg){ svg=svg||svgD; var g=svg&&svg._fill; if(!g) return; var z=svg===svgD?(Z||1):(MM.z||1);
  [].forEach.call(g.children, function(tg, k){ var t=k+1; tg.style.display=(t<=fillLevel && z>=FILL_ZMIN[t])?'':'none'; }); }
/* levels 3-4 on the board: one canvas the size of the window (plus a margin while the pixel budget allows), under the
   city's SVG, inside #world — so a zoom glide scales it with the board for free; drawn again when the zoom settles,
   when a pan leaves what it covers, and when the level changes */
var FC=null;
function fillCanvas(){ if(FC) return FC; var world=document.getElementById('world'); if(!world) return null;
  var c=document.createElement('canvas'); c.id='pal-fillc'; c.setAttribute('aria-hidden','true'); FC={c:c, x:c.getContext('2d'), cache:{}, rect:null};
  return FC; }
var fillPend=0;
function fillSoon(){ if(fillPend) return; fillPend=1; Promise.resolve().then(function(){ fillPend=0; fillPaint(); }); }
function fillPaint(){
  if(!FILL || mob() || !svgD || PV) return; var F=fillCanvas(); if(!F) return; var c=F.c, world=document.getElementById('world'), cv=document.getElementById('canvas');
  if(c.parentNode!==world) world.insertBefore(c, svgD.parentNode===world?svgD:world.firstChild);
  var lv0=3, lv1=Math.min(fillLevel,4); while(lv1>=lv0 && Z<FILL_ZMIN[lv1]) lv1--;
  if(lv1<lv0 || !cv){ c.style.display='none'; F.rect=null; return; }
  var wr=world.getBoundingClientRect(), cr=cv.getBoundingClientRect(), k=(cr.width/cv.clientWidth)||1, W=cv.clientWidth, H=cv.clientHeight;
  var vx=(cr.left-wr.left)/k, vy=(cr.top-wr.top)/k, dpr=window.devicePixelRatio||1, BUD=16e6, m=window._fillMargin!=null?window._fillMargin:.25;
  while(m>0 && W*(1+2*m)*H*(1+2*m)*dpr*dpr>BUD) m-=.05; if(m<0) m=0;
  var cw=W*(1+2*m), chh=H*(1+2*m); if(cw*chh*dpr*dpr>BUD) dpr=Math.sqrt(BUD/(cw*chh));
  var left=vx-m*W, topw=vy-m*H;
  c.style.display=''; c.style.left=left.toFixed(1)+'px'; c.style.top=topw.toFixed(1)+'px'; c.style.width=cw.toFixed(1)+'px'; c.style.height=chh.toFixed(1)+'px';
  var pw=Math.round(cw*dpr), ph=Math.round(chh*dpr); if(c.width!==pw) c.width=pw; if(c.height!==ph) c.height=ph;
  var x=F.x, t0=performance.now(); x.setTransform(1,0,0,1,0,0); x.clearRect(0,0,pw,ph);
  var sx=dpr*Z, ox=dpr*(MX*Z-left), oy=dpr*(WORLD_PAD_TOP+MY*Z-topw); x.setTransform(sx,0,0,sx,ox,oy);
  var mx0=left/Z-MX, my0=(topw-WORLD_PAD_TOP)/Z-MY, mx1=mx0+cw/Z, my1=my0+chh/Z; F.rect=[mx0,my0,mx1,my1];
  var dark=dk(), G=fillGroups(), CH=FILL.ch; x.lineJoin='round'; x.lineWidth=1.1/Z;
  for(var lv=lv0;lv<=lv1;lv++){ x.fillStyle=dark?'rgba(64,68,90,.78)':(lv===3?'rgba(255,255,255,.8)':'rgba(255,255,255,.72)');
    Object.keys(G[lv]).forEach(function(key){ var C=G[lv][key], cx0=C.ci*CH[0], cy0=C.cj*CH[1];
      if(cx0>mx1 || cx0+CH[0]<mx0 || cy0>my1 || cy0+CH[1]<my0) return;
      Object.keys(C.u).forEach(function(u){ var ck=lv+'|'+key+'|'+u, P2=F.cache[ck];
        if(!P2){ P2=new Path2D(); C.u[u].forEach(function(s){ var p=s.p; P2.moveTo(p[0],p[1]); for(var n=2;n<p.length;n+=2) P2.lineTo(p[n],p[n+1]); P2.closePath(); }); F.cache[ck]=P2; }
        x.fill(P2); x.strokeStyle=tubeCol(dcol(u==='null'?null:+u)||NEUTRAL()); x.globalAlpha=lv===3?.72:.55; x.stroke(P2); x.globalAlpha=1; }); }); }
  window._fillPaintMs=performance.now()-t0; }
/* a pan that runs past what the canvas covers draws it again (at most every 100 ms while it runs, and once when it stops) */
var fillLastPaint=0, fillScrollT=null;
function fillOnScroll(){ if(PV || !FC || !FC.rect || fillLevel<3) return; var cv=document.getElementById('canvas'), world=document.getElementById('world'), r=FC.rect, z=Z||1;
  var wr=world.getBoundingClientRect(), cr=cv.getBoundingClientRect(), k=(cr.width/cv.clientWidth)||1;
  var vx0=(cr.left-wr.left)/k/z-MX, vy0=((cr.top-wr.top)/k-WORLD_PAD_TOP)/z-MY, inside=vx0>=r[0]-1 && vy0>=r[1]-1 && vx0+cv.clientWidth/z<=r[2]+1 && vy0+cv.clientHeight/z<=r[3]+1;
  clearTimeout(fillScrollT); fillScrollT=setTimeout(fillPaint, 120);
  if(!inside && performance.now()-fillLastPaint>100){ fillLastPaint=performance.now(); fillPaint(); } }
/* levels 1-2 are named on hover: the building under the pointer, from its footprint (no element of its own) */
var fillHov=null, fillHovRaf=0, fillHovOn=false;
function fillHover(e){ if(fillHovRaf) return; var cx=e.clientX, cy=e.clientY, tg=e.target; fillHovRaf=requestAnimationFrame(function(){ fillHovRaf=0;
  var name='', hit=null;
  if(svgD && fillLevel>=1 && !mob() && !(tg && tg.closest && tg.closest('.node,.pl-lmb,.pl-hit,.pl-chip,#pal-key,#pal-ctl,#pal-dock,#pal-lmbar,.pl-route-hit,.pl-tr-hit'))){
    var r=svgD.getBoundingClientRect(); if(r.width){ var mx=(cx-r.left)/r.width*VW-MX, my=(cy-r.top)/r.height*VH-MY, S=fillShapes();
      for(var lv=1;lv<=Math.min(2,fillLevel) && !hit;lv++) for(var i=0;i<S[lv].length;i++){ var s=S[lv][i], b=s.b; if(!s.n || mx<b[0]||mx>b[2]||my<b[1]||my>b[3]) continue;
        var p=s.p, c=false; for(var a=0,n=p.length,j=n-2;a<n;j=a,a+=2){ if((p[a+1]>my)!==(p[j+1]>my) && mx<p[a]+(my-p[a+1])*(p[j]-p[a])/(p[j+1]-p[a+1])) c=!c; }
        if(c){ hit=s; break; } } } }
  if(hit){ if(fillHov===hit) return; fillHov=hit; var b=hit.b, rc=svgD.querySelector(':scope > .pl-fhit')||el('rect',{'class':'pl-fhit'},svgD);
    rc.setAttribute('x',b[0]); rc.setAttribute('y',b[1]); rc.setAttribute('width',b[2]-b[0]); rc.setAttribute('height',b[3]-b[1]); window._palHover(rc, hit.n); fillHovOn=true; }
  else if(fillHovOn){ fillHov=null; fillHovOn=false; window._palHover(null); } }); }
function fillSet(v){ fillLevel=Math.max(0,Math.min(4,v|0)); try{ localStorage.setItem(FILL_KEY, String(fillLevel)); }catch(e){}
  if(svgD){ fillLOD(svgD); fillSoon(); } if(MM.svg) fillLOD(MM.svg);
  [].forEach.call(document.querySelectorAll('.pk-fill input'), function(r){ r.value=fillLevel; });
  [].forEach.call(document.querySelectorAll('.pk-fill .pkf-v'), function(l){ l.textContent=FILL_NAMES[fillLevel]; });
  [].forEach.call(document.querySelectorAll('.pkf-seg button'), function(b){ b.setAttribute('aria-checked', String(+b.getAttribute('data-fl')===fillLevel)); }); }
function fillWire(k){
  if(!FILL) return;
  var cv=document.getElementById('canvas'); if(cv) cv.addEventListener('scroll', fillOnScroll, {passive:true});
  document.addEventListener('mousemove', fillHover, {passive:true});
  var r=k.querySelector('.pk-fill input'); if(r) r.addEventListener('input', function(){ fillSet(+r.value); }); }
function fillKeyRow(){ if(!FILL) return '';
  return '<div class="pk-sep"></div><label class="pk-fill"><span class="pkf-h"><b>Fill in the city</b><small class="pkf-v">'+FILL_NAMES[fillLevel]+'</small></span>'
    +'<input type="range" min="0" max="4" step="1" value="'+fillLevel+'" aria-label="How much of the city to fill in with buildings" aria-valuetext="'+FILL_NAMES[fillLevel]+'">'
    +'<span class="pkf-ticks"><span>Landmarks</span><span>Every building</span></span></label>'; }
/* the phone's sheet: five stops, a tap each (a range thumb is fiddly under a finger) */
function fillPhoneRow(){ if(!FILL) return ''; var short=['Landmarks','Skyline','Notable','Most','All'], h='<div class="pm-h6">Fill in the city</div><div class="pkf-seg" role="radiogroup" aria-label="How much of the city to fill in">';
  for(var i=0;i<5;i++) h+='<button type="button" role="radio" data-fl="'+i+'" aria-checked="'+(i===fillLevel)+'" aria-label="'+FILL_NAMES[i]+'">'+short[i]+'</button>';
  return h+'</div><small class="pkf-note">The city’s real buildings, drawn around yours. Yours keep their numbers.</small>'; }
window._altoFill={shapes:function(){ return fillShapes(); }, set:function(v){ fillSet(v); }, level:function(){ return fillLevel; }};
function fillWirePhone(box){ if(!FILL || !box) return; box.addEventListener('click', function(e){ var b=e.target.closest && e.target.closest('.pkf-seg [data-fl]'); if(!b) return; e.stopPropagation(); fillSet(+b.getAttribute('data-fl')); }, true); }
"""

# where the hooks go in PALACE_JS (each anchor must be found exactly once)
_HOOKS = [
    ("/* ── the board: the city under the cards, at the current zoom ── */", FILL_FUNCS + "\n/* ── the board: the city under the cards, at the current zoom ── */"),
    ("  drawBuildings(svg);\n  sizeChips(svg);", "  fillDraw(svg);\n  drawBuildings(svg);\n  sizeChips(svg);"),
    ("function drawBuildings(svg){\n  var g=svg._b; if(!g) return; g.innerHTML='';",
     "function drawBuildings(svg){\n  var g=svg._b; if(!g) return; g.innerHTML=''; if(svg._fill && svg._fillSig!==fillSig()) fillDraw(svg);"),
    ("  setClasses(); if(svgD) sizeChips(svgD);", "  setClasses(); if(svgD) sizeChips(svgD); if(svgD){ fillLOD(svgD); fillSoon(); }"),
    ("  var sw=function(s){ return '<svg width=\"26\" height=\"12\" style=\"flex:none\">'+s+'</svg>'; };",
     "  h+=fillKeyRow();\n  var sw=function(s){ return '<svg width=\"26\" height=\"12\" style=\"flex:none\">'+s+'</svg>'; };"),
    ("  window._altoKeyToggle(k, 'alto-palace-key', 'Key to the city');", "  window._altoKeyToggle(k, 'alto-palace-key', 'Key to the city'); fillWire(k);"),
    ("  return h; }\nfunction pmResults(q){", "  h+=fillPhoneRow();\n  return h; }\nfunction pmResults(q){"),
    ("  pmGestures(); pmSheetTouch(); pmSheetClicks();", "  pmGestures(); pmSheetTouch(); pmSheetClicks(); fillWirePhone(box);"),
    ("function pmCommit(z){ var sv=MM.svg; MM.z=z;", "function pmCommit(z){ var sv=MM.svg; MM.z=z; if(sv._fill) fillLOD(sv);"),
]


def patch_js(js: str) -> str:
    for a, b in _HOOKS:
        if js.count(a) != 1:
            raise RuntimeError("palace_fillin: hook anchor not found once: " + a[:60])
        js = js.replace(a, b)
    return js
