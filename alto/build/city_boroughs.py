"""The rest of New York around Manhattan's layout (city_manhattan.py): Brooklyn, Queens, the Bronx, Staten Island and
upper Manhattan, drawn lighter (Luke, 2026-10-21: "I wanted all 5 boroughs though"; Manhattan in full, the other four
lighter: main avenues, parks, names, bridges and water, no individual buildings).

fetch() asks OpenStreetMap for the five boroughs' box, a tile at a time (each tile cached on its own): the main roads
(motorway / trunk / primary / secondary), the coastline, the named parks, the neighbourhood names and the boroughs'
outlines. Everything is kept in lat/lon; city_manhattan carries it onto the page."""
from __future__ import annotations

import json
import math
from pathlib import Path

BBOX = (40.477, -74.260, 40.918, -73.700)          # the five boroughs (Staten Island's south tip to the Bronx's north edge)
TILES = (4, 4)
ROADS = ("motorway", "trunk", "primary", "secondary")
PLACES = ("suburb", "neighbourhood")
BOROUGHS = {"Brooklyn": "Brooklyn", "Kings County": "Brooklyn", "Queens": "Queens", "Queens County": "Queens",
            "The Bronx": "The Bronx", "Bronx": "The Bronx", "Bronx County": "The Bronx", "Staten Island": "Staten Island",
            "Richmond County": "Staten Island", "Manhattan": "Manhattan", "New York County": "Manhattan"}
CITY = "New York"                                    # the city's own outline (admin level 5): New Jersey and Nassau are not New York


def _tiles(bbox=BBOX, n=TILES):
    s, w, nn, e = bbox
    for i in range(n[0]):
        for j in range(n[1]):
            yield (round(s + (nn - s) * i / n[0], 4), round(w + (e - w) * j / n[1], 4),
                   round(s + (nn - s) * (i + 1) / n[0], 4), round(w + (e - w) * (j + 1) / n[1], 4))


def _query(b):
    bb = "(%r,%r,%r,%r)" % b
    return "\n".join([
        "[out:json][timeout:180];",
        '(way[highway~"^(%s)$"][area!=yes]%s;);' % ("|".join(ROADS), bb), "out geom qt;",
        "(way[natural=coastline]%s;);" % bb, "out geom qt;",
        "(way[leisure=park][name]%s;rel[leisure=park][name]%s;);" % (bb, bb), "out geom qt;",
        'node[place~"^(%s)$"][name]%s;' % ("|".join(PLACES), bb), "out qt;"])


def _boro_query(b):
    return '[out:json][timeout:180];rel[boundary=administrative][admin_level~"^(5|6)$"]%s;out geom qt;' % ("(%r,%r,%r,%r)" % b)


def _cached(cache_dir, key, query, offline):
    p = Path(cache_dir) / ("boro-%s.json" % key) if cache_dir else None
    if p and p.exists():
        return json.loads(p.read_text("utf-8"))
    if offline:
        return None
    from .. import palace_map as pm
    data = pm._post_overpass(query, 200)
    if p:
        p.write_text(json.dumps(data), "utf-8")
    return data


def fetch(cache_dir=None, offline=False, bbox=BBOX) -> dict:
    """{roads: [{n, c, br, p: [lat, lon, ...]}], coast: [[lat, lon, ...]], parks: [{n, r: [[lat, lon, ...]]}],
    places: [{n, k, lat, lon}], boroughs: {name: [[lat, lon, ...]]}, missing: [tile]} (a tile no server gave is missing)."""
    out = {"roads": [], "coast": [], "parks": [], "places": [], "boroughs": {}, "missing": []}
    seen = set()
    for t in _tiles(bbox):
        d = _cached(cache_dir, "%.4f_%.4f_%.4f_%.4f" % t, _query(t), offline)
        if d is None:
            out["missing"].append(list(t))
            continue
        for el in d.get("elements", []):
            key = (el["type"], el["id"])
            if key in seen:
                continue
            seen.add(key)
            tg = el.get("tags") or {}
            if el["type"] == "node" and tg.get("place") in PLACES:
                out["places"].append({"n": tg["name"], "k": tg["place"], "lat": el["lat"], "lon": el["lon"]})
            elif el["type"] == "way" and tg.get("highway") in ROADS and el.get("geometry"):
                out["roads"].append({"n": tg.get("name") or tg.get("ref") or "", "c": ROADS.index(tg["highway"]),
                                     "br": 1 if tg.get("bridge") not in (None, "no") else 0,
                                     "tn": 1 if tg.get("tunnel") not in (None, "no") else 0,
                                     "p": [round(v, 6) for g in el["geometry"] for v in (g["lat"], g["lon"])]})
            elif el["type"] == "way" and tg.get("natural") == "coastline" and el.get("geometry"):
                out["coast"].append([round(v, 6) for g in el["geometry"] for v in (g["lat"], g["lon"])])
            elif tg.get("leisure") == "park":
                rings = _rings(el)
                if rings:
                    out["parks"].append({"n": tg.get("name", ""), "r": rings})
    b = _cached(cache_dir, "admin56-%.3f_%.3f_%.3f_%.3f" % tuple(bbox), _boro_query(bbox), offline)
    for el in (b or {}).get("elements", []):
        tg = el.get("tags") or {}
        nm = CITY if (tg.get("admin_level") == "5" and tg.get("name") == CITY) else BOROUGHS.get(tg.get("name", ""))
        if nm and nm not in out["boroughs"]:
            out["boroughs"][nm] = _rings(el)
    return out


def _rings(el):
    """Closed rings [lat, lon, ...] of a way or a multipolygon relation's outer members."""
    from ..palace_map import assemble_rings
    if el["type"] == "way":
        g = el.get("geometry") or []
        if len(g) >= 4 and (g[0]["lat"], g[0]["lon"]) == (g[-1]["lat"], g[-1]["lon"]):
            return [[round(v, 6) for p in g[:-1] for v in (p["lat"], p["lon"])]]
        return []
    ways = [[(p["lat"], p["lon"]) for p in m.get("geometry") or []] for m in el.get("members", [])
            if m.get("type") == "way" and m.get("role", "outer") in ("outer", "")]
    return [[round(v, 6) for p in r for v in p] for r in assemble_rings(ways)]


def ring_area_m2(r):
    """Area of a [lat, lon, ...] ring in square metres (small-area approximation)."""
    n = len(r) // 2
    if n < 3:
        return 0.0
    lat0 = math.radians(sum(r[0::2]) / n)
    kx, ky = 111320 * math.cos(lat0), 110574
    pts = [(r[2 * i + 1] * kx, r[2 * i] * ky) for i in range(n)]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


# ── the page: the rest of the city around Manhattan's lattice ───────────────
SEA_CELL = 25.0           # m: the real water raster (coastline flood; at 50 m the Harlem River's banks met and Manhattan ran into the Bronx)
PAGE_CELL = 110.0          # page px: the drawn water's raster
FIELD = 250.0             # m: the displacement field's grid
FADE = 1800.0             # m: how far from Manhattan's shore its lattice still pulls the rest of the city
PARK_HA = 25.0            # hectares: the parks drawn outside Manhattan
NAME_GAP = 2600.0         # m: neighbourhood names at least this far apart
SEA_SEED = (40.50, -73.90)  # the Atlantic south of the Rockaways
# the names a New Yorker looks for first (a blind audit, 2026-10-22: Williamsburg, DUMBO, Harlem, LIC... were crowded out by
# whichever neighbourhood OSM listed first): placed before the rest, and allowed closer together
FAMOUS = ("Harlem", "East Harlem", "Washington Heights", "Inwood", "Williamsburg", "DUMBO", "Brooklyn Heights", "Park Slope",
          "Bedford-Stuyvesant", "Bushwick", "Greenpoint", "Red Hook", "Coney Island", "Brighton Beach", "Bay Ridge",
          "Crown Heights", "Flatbush", "Sunset Park", "Long Island City", "Astoria", "Flushing", "Jamaica",
          "Jackson Heights", "Forest Hills", "Sunnyside", "Riverdale", "Mott Haven", "Fordham", "St. George")
FAMOUS_GAP = 700.0        # m
# what OSM's neighbourhood nodes never name: the water, the islands, the airports, the far shore, and Manhattan itself.
# (name, lat, lon, rank, kind): kind b = a borough-sized name, w = water, m = on Manhattan's lattice (placed by its mapping),
# i = an island too small for the page's water raster, drawn as its own land (isles_page)
LABELS = [("Manhattan", 40.7790, -73.9665, 1, "bm"), ("Upper West Side", 40.7870, -73.9754, 2, "m"),
          ("Upper East Side", 40.7736, -73.9566, 2, "m"),
          ("New Jersey", 40.7780, -74.0700, 1, "b"), ("Jersey City", 40.7215, -74.0630, 3, ""), ("Hoboken", 40.7445, -74.0300, 3, ""),
          ("Upper New York Bay", 40.6640, -74.0450, 1, "w"), ("Lower New York Bay", 40.5350, -74.0400, 1, "w"),
          ("Atlantic Ocean", 40.5250, -73.8700, 1, "w"), ("Jamaica Bay", 40.6150, -73.8400, 1, "w"),
          ("Long Island Sound", 40.8150, -73.7650, 1, "w"), ("Harlem River", 40.8450, -73.9280, 2, "w"),
          ("Hudson River", 40.8650, -73.9420, 2, "w"), ("Newark Bay", 40.6750, -74.1350, 2, "w"),
          ("Raritan Bay", 40.5050, -74.2000, 2, "w"), ("The Narrows", 40.6070, -74.0440, 3, "w"),
          ("Flushing Bay", 40.7660, -73.8560, 3, "w"), ("Kill Van Kull", 40.6450, -74.1200, 3, "w"),
          ("Arthur Kill", 40.5900, -74.2050, 3, "w"), ("Gravesend Bay", 40.5900, -74.0150, 3, "w"),
          ("Governors Island", 40.6890, -74.0165, 2, ""), ("Statue of Liberty", 40.6892, -74.0445, 2, "i"),
          ("Ellis Island", 40.6990, -74.0395, 3, "i"), ("Roosevelt Island", 40.7620, -73.9495, 2, ""),
          ("Randalls Island", 40.7935, -73.9215, 2, ""), ("Rikers Island", 40.7930, -73.8855, 3, ""),
          ("JFK Airport", 40.6413, -73.7781, 2, ""), ("LaGuardia Airport", 40.7769, -73.8740, 2, ""),
          # famous neighbourhoods OSM tags as something other than a suburb or neighbourhood node
          ("Harlem", 40.8116, -73.9465, 3, ""), ("Washington Heights", 40.8417, -73.9394, 3, ""),
          ("Williamsburg", 40.7081, -73.9571, 3, ""), ("Bushwick", 40.6944, -73.9213, 3, ""),
          ("Coney Island", 40.5755, -73.9707, 3, ""), ("Brighton Beach", 40.5781, -73.9597, 3, ""),
          ("Flatbush", 40.6409, -73.9566, 3, ""), ("Long Island City", 40.7447, -73.9485, 3, ""),
          ("Flushing", 40.7675, -73.8331, 3, ""), ("Jamaica", 40.7027, -73.7890, 3, ""),
          ("St. George", 40.6437, -74.0736, 3, "")]
LABEL_GAP = 900.0         # m: no neighbourhood node this near a fixed name (Governors Island's "Nolan Park")


def _lstsq3(rows, vals):
    """Least squares a*x + b*y + c ~ v (normal equations, 3 x 3)."""
    S = [[0.0] * 3 for _ in range(3)]
    t = [0.0] * 3
    for (x, y), v in zip(rows, vals):
        r = (x, y, 1.0)
        for i in range(3):
            t[i] += r[i] * v
            for j in range(3):
                S[i][j] += r[i] * r[j]
    # Gauss-Jordan
    M = [S[i] + [t[i]] for i in range(3)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(3):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    return [M[i][3] / M[i][i] for i in range(3)]


def _in(ring, x, y):
    c = False
    n = len(ring)
    for i in range(n):
        (x0, y0), (x1, y1) = ring[i], ring[i - 1]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


class _Rings:
    """Point-in-polygon over many rings, with a coarse grid of candidate rings for speed."""

    def __init__(self, rings, cell=2000.0):
        self.rings = [r for r in rings if len(r) >= 3]
        self.cell = cell
        self.ix = {}
        for k, r in enumerate(self.rings):
            xs, ys = [p[0] for p in r], [p[1] for p in r]
            for i in range(int(min(xs) // cell), int(max(xs) // cell) + 1):
                for j in range(int(min(ys) // cell), int(max(ys) // cell) + 1):
                    self.ix.setdefault((i, j), []).append(k)

    def __call__(self, x, y):
        c = 0
        for k in self.ix.get((int(x // self.cell), int(y // self.cell)), ()):
            if _in(self.rings[k], x, y):
                c += 1
        return c % 2 == 1


def _dp(pts, tol):
    if len(pts) < 3:
        return pts
    (ax, ay), (bx, by) = pts[0], pts[-1]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    k, dmax = 0, -1.0
    for i in range(1, len(pts) - 1):
        d = abs((pts[i][0] - ax) * dy - (pts[i][1] - ay) * dx) / L if L > 1e-9 else math.dist(pts[i], pts[0])
        if d > dmax:
            k, dmax = i, d
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return _dp(pts[:k + 1], tol)[:-1] + _dp(pts[k:], tol)


def _merge(lines):
    """Ways of one street joined end to end: [(key, [points])] -> [(key, [points])] (fewer, longer)."""
    out = []
    by_key = {}
    for key, pts in lines:
        by_key.setdefault(key, []).append(list(pts))
    for key, segs in by_key.items():
        ends = {}
        for i, s in enumerate(segs):
            ends.setdefault(s[0], []).append(i)
            ends.setdefault(s[-1], []).append(i)
        used = [False] * len(segs)
        for i in range(len(segs)):
            if used[i]:
                continue
            used[i] = True
            ch = list(segs[i])
            for _side in (0, 1):
                while True:
                    nxt = next((j for j in ends.get(ch[-1], ()) if not used[j]), None)
                    if nxt is None:
                        break
                    used[nxt] = True
                    s = segs[nxt]
                    ch.extend((s if s[0] == ch[-1] else s[::-1])[1:])
                ch.reverse()
            out.append((key, ch))
    return out


class Outer:
    """The rest of the city in real map px (Manhattan's box projection), and how it reaches the page: an affine fit of
    Manhattan's lattice, bent near Manhattan's shore so the two meet (a displacement field that fades out by FADE)."""

    def __init__(self, m, tr, xr, yr, xg, yg, cw, ch, land, isl):
        from ..palace_map import project
        bbox, sc = m["bbox"], m.get("scale", 1.0)
        d = m["outer"]

        def P(flat_):
            return [project(flat_[k], flat_[k + 1], bbox, sc) for k in range(0, len(flat_) - 1, 2)]
        self.P1 = lambda lat, lon: project(lat, lon, bbox, sc)
        self.city = _Rings([P(r) for r in d["boroughs"].get("New York", [])])
        self.boros = {n: [P(r) for r in rs] for n, rs in d["boroughs"].items() if n != "New York"}
        self.roads = [((r["n"], r["c"], r["br"]), P(r["p"])) for r in d["roads"] if not r.get("tn")]
        self.coast = [P(c) for c in d["coast"]]
        self.parks = [(p["n"], [P(r) for r in p["r"]]) for p in d["parks"]
                      if sum(ring_area_m2(r) for r in p["r"]) >= PARK_HA * 1e4]
        self.places = [(p["n"], p["k"]) + self.P1(p["lat"], p["lon"]) for p in d["places"]]
        self.tr, self.xr, self.yr, self.xg, self.yg, self.cw, self.ch = tr, xr, yr, xg, yg, cw, ch
        self.land, self.isl = land, isl
        # the affine fit of the lattice over Manhattan's own land (page origin 0)
        smp = []
        for p in land.cells(isl)[::5]:
            u, v = tr(*p)
            if xr[0] <= u <= xr[-1] and yr[0] <= v <= yr[-1]:
                smp.append(p)
        tgt = [self.r0(*p) for p in smp]
        self.ax = _lstsq3(smp, [q[0] for q in tgt])
        self.ay = _lstsq3(smp, [q[1] for q in tgt])
        xs, ys = [], []
        for r in self.city.rings:
            for p in r[::5]:
                q = self.aff(*p)
                xs.append(q[0])
                ys.append(q[1])
        self.need = (-min(xs) + 900, -min(ys) + 900)
        self.ext = (max(xs), max(ys))

    def r0(self, x, y):
        from .city_manhattan import _interp
        u, v = self.tr(x, y)
        xr, yr, xg, yg = self.xr, self.yr, self.xg, self.yg
        return (_interp(u, xr, xg, xr[1] - xr[0] if u < xr[0] else xr[-1] - xr[-2], self.cw),
                _interp(v, yr, yg, yr[1] - yr[0] if v < yr[0] else yr[-1] - yr[-2], self.ch))

    def aff(self, x, y):
        return (self.ax[0] * x + self.ax[1] * y + self.ax[2], self.ay[0] * x + self.ay[1] * y + self.ay[2])

    def detailed(self, x, y):
        """Manhattan as its lattice draws it (the island in the box, south of the grid's top street)."""
        return self.land.cid(x, y) == self.isl and self.tr(x, y)[1] >= self.yr[0] - 20

    # ── the bend near Manhattan ──
    def setup(self, o, shore_real):
        self.o = o
        smp = [(p, self.r0(*p)) for p in shore_real]
        disp = [(p, (q[0] - (self.aff(*p)[0]), q[1] - self.aff(*p)[1])) for p, q in smp]
        xs = [p[0] for r in self.city.rings for p in r]
        ys = [p[1] for r in self.city.rings for p in r]
        self.fx0, self.fy0 = min(xs) - FIELD, min(ys) - FIELD
        self.fnx = int((max(xs) - self.fx0) / FIELD) + 3
        self.fny = int((max(ys) - self.fy0) / FIELD) + 3
        F = []
        for j in range(self.fny):
            row = []
            y = self.fy0 + j * FIELD
            for i in range(self.fnx):
                x = self.fx0 + i * FIELD
                sw = sx = sy = 0.0
                dmin = 1e18
                for (px, py), (dx, dy) in disp:
                    d2 = (px - x) ** 2 + (py - y) ** 2
                    dmin = min(dmin, d2)
                    w = 1.0 / (d2 + 300.0 ** 2)
                    sw += w
                    sx += w * dx
                    sy += w * dy
                f = math.exp(-dmin / FADE ** 2) if disp else 0.0
                row.append((sx / sw * f, sy / sw * f) if sw else (0.0, 0.0))
            F.append(row)
        self.F = F

    def _field(self, x, y):
        fx, fy = (x - self.fx0) / FIELD, (y - self.fy0) / FIELD
        i, j = max(0, min(self.fnx - 2, int(fx))), max(0, min(self.fny - 2, int(fy)))
        tx, ty = min(1.0, max(0.0, fx - i)), min(1.0, max(0.0, fy - j))
        a, b, c, e = self.F[j][i], self.F[j][i + 1], self.F[j + 1][i], self.F[j + 1][i + 1]
        return ((a[0] * (1 - tx) + b[0] * tx) * (1 - ty) + (c[0] * (1 - tx) + e[0] * tx) * ty,
                (a[1] * (1 - tx) + b[1] * tx) * (1 - ty) + (c[1] * (1 - tx) + e[1] * tx) * ty)

    def __call__(self, x, y):
        a = self.aff(x, y)
        d = self._field(x, y)
        return (a[0] + d[0] + self.o[0], a[1] + d[1] + self.o[1])

    def back(self, X, Y):
        """Page -> real (the inverse, by a few fixed-point steps)."""
        det = self.ax[0] * self.ay[1] - self.ax[1] * self.ay[0]
        x, y = 0.0, 0.0
        tx, ty = X - self.o[0], Y - self.o[1]
        for _ in range(4):
            d = self._field(x, y)
            u, v = tx - d[0] - self.ax[2], ty - d[1] - self.ay[2]
            x, y = (self.ay[1] * u - self.ax[1] * v) / det, (-self.ay[0] * u + self.ax[0] * v) / det
        return x, y

    # ── the drawing ──
    def sea_real(self):
        """The real water: the coastline drawn as a wall, the sea flooded from the Atlantic."""
        # exactly the fetched box: its edges are the flood's walls where the coastline runs on outside it (Long Island)
        s_, w_, n_, e_ = BBOX
        (self.sx0, self.sy0), (x1, y1) = self.P1(n_, w_), self.P1(s_, e_)
        nx, ny = int((x1 - self.sx0) / SEA_CELL) + 1, int((y1 - self.sy0) / SEA_CELL) + 1
        self.snx, self.sny = nx, ny
        bar = [bytearray(nx) for _ in range(ny)]
        for pts in self.coast:
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                n = int(math.hypot(x1 - x0, y1 - y0) / (SEA_CELL / 3)) + 1
                for t in range(n + 1):
                    i = int((x0 + (x1 - x0) * t / n - self.sx0) // SEA_CELL)
                    j = int((y0 + (y1 - y0) * t / n - self.sy0) // SEA_CELL)
                    if 0 <= i < nx and 0 <= j < ny:            # one cell: an 8-connected wall stops a 4-way flood,
                        bar[j][i] = 1                          # and a thin island (Roosevelt) keeps its land
        sea = [bytearray(nx) for _ in range(ny)]
        x, y = self.P1(*SEA_SEED)
        st = [(int((x - self.sx0) // SEA_CELL), int((y - self.sy0) // SEA_CELL))]
        while st:
            i, j = st.pop()
            if 0 <= i < nx and 0 <= j < ny and not sea[j][i] and not bar[j][i]:
                sea[j][i] = 1
                st += [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)]
        # the wall cells themselves: water when most of their neighbours are
        for j in range(1, ny - 1):
            for i in range(1, nx - 1):
                if bar[j][i] and sea[j][i - 1] + sea[j][i + 1] + sea[j - 1][i] + sea[j + 1][i] >= 2:
                    sea[j][i] = 2
        self.sea = sea

    def is_sea(self, x, y):
        """Real water? Past the fetched box the box's edge runs on (the Atlantic stays sea, New Jersey stays land)."""
        j = int((y - self.sy0) // SEA_CELL)
        if j >= self.sny:
            return True                                     # south of the box: the Atlantic
        i = min(self.snx - 1, max(0, int((x - self.sx0) // SEA_CELL)))
        j = max(0, j)
        return self.sea[j][i] > 0

    def page_sea(self, W, H, man_ring, band):
        """The water on the page as rings (one even-odd shape): every page cell whose real place is water, plus
        Manhattan's own bands, less Manhattan's land; a cell outside Manhattan's drawn shore whose real place is
        Manhattan's lattice land is water too (the lattice and the rest of the city never quite agree there)."""
        from .city_lattice import inside as ring_inside
        M = 16                                              # cells past the page's edges (the glass runs on beyond them)
        nx, ny = int(W / PAGE_CELL) + 1 + 2 * M, int(H / PAGE_CELL) + 1 + 2 * M
        g = [bytearray(nx) for _ in range(ny)]
        mx0, mx1 = min(p[0] for p in man_ring), max(p[0] for p in man_ring)
        my0, my1 = min(p[1] for p in man_ring), max(p[1] for p in man_ring)
        bx0, bx1 = min(p[0] for p in band), max(p[0] for p in band)
        by0, by1 = min(p[1] for p in band), max(p[1] for p in band)
        for j in range(ny):
            Y = (j - M + .5) * PAGE_CELL
            for i in range(nx):
                X = (i - M + .5) * PAGE_CELL
                in_man = mx0 <= X <= mx1 and my0 <= Y <= my1 and ring_inside(man_ring, X, Y)
                if in_man:
                    continue
                x, y = self.back(X, Y)
                if self.is_sea(x, y) or self.detailed(x, y):
                    g[j][i] = 1
        return [[(x - M * PAGE_CELL, y - M * PAGE_CELL) for x, y in r] for r in _trace(g, nx, ny, PAGE_CELL)]

    def roads_page(self, man=None):
        """Main roads in New York outside Manhattan's lattice: (key, page points) runs. A bridge runs on past the city's
        line (the GWB to New Jersey), and with man (real -> page on Manhattan's lattice) it is joined to its last point on
        the lattice, so its deck reaches the island (else every East River bridge stopped at the water)."""
        runs = []
        for key, pts in _merge(self.roads):
            cur, head, prev = [], None, None
            cross = key[2] and any(self.city(*p) for p in pts)     # a bridge into the city (not New Jersey's overpasses)
            for p in pts:
                det = self.detailed(*p)
                if (cross or self.city(*p)) and not det:
                    if not cur and key[2] and prev is not None and self.detailed(*prev):
                        head = prev
                    cur.append(p)
                else:
                    tail = p if key[2] and det else None
                    if len(cur) >= 2 or (cur and (head or tail)):
                        runs.append((key, cur, head, tail))
                    cur, head = [], None
                prev = p
            if len(cur) >= 2 or (cur and head):
                runs.append((key, cur, head, None))
        out = []
        for key, pts, head, tail in runs:
            pg = _dp([self(*p) for p in _dp(pts, 8.0)], 14.0)
            if man is not None:
                pg = ([man(*head)] if head else []) + pg + ([man(*tail)] if tail else [])
            if len(pg) >= 2 and sum(math.dist(a, b) for a, b in zip(pg, pg[1:])) > 60:
                out.append((key, pg))
        return out

    def parks_page(self):
        out = []
        for n, rings in self.parks:
            big = max(rings, key=len)
            cx = sum(p[0] for p in big) / len(big)
            cy = sum(p[1] for p in big) / len(big)
            if not self.city(cx, cy) or self.detailed(cx, cy):
                continue
            rs = []
            for r in rings:
                q = _dp([self(*p) for p in r] + [self(*r[0])], 24.0)[:-1]
                if len(q) >= 3:
                    rs.append([round(v) for p in q for v in p])
            if rs:
                t = self(cx, cy)
                out.append({"n": n, "k": "park", "z": 1, "r": rs, "p": [], "o": [], "t": [round(t[0]), round(t[1])], "pg": 1})
        return out

    def isles_page(self, reach=24):
        """The small islands of LABELS (kind i: Liberty, Ellis) as page rings: the real raster's land around each name, one
        island's hull; one that runs on past `reach` cells (joined to the mainland) is left to the water raster."""
        out = []
        for n, lat, lon, _r, k in LABELS:
            if "i" not in k:
                continue
            x0, y0 = self.P1(lat, lon)
            st, seen, bad = [(0, 0)], set(), False
            while st and not bad:
                i, j = st.pop()
                if (i, j) in seen or self.is_sea(x0 + i * SEA_CELL, y0 + j * SEA_CELL):
                    continue
                if abs(i) > reach or abs(j) > reach:
                    bad = True
                    break
                seen.add((i, j))
                st += [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)]
            if bad or len(seen) < 4:
                continue
            h = _hull2([(x0 + (i + a) * SEA_CELL, y0 + (j + b) * SEA_CELL) for i, j in seen for a in (-.5, .5) for b in (-.5, .5)])
            out.append([round(v) for p in h for v in self(*p)])
        return out

    def names_page(self, man=None):
        """The boroughs' names (rank 1) and neighbourhoods (rank 3, spaced; the famous ones first) outside Manhattan's
        lattice, and the fixed LABELS (water, islands, airports, New Jersey, Manhattan's own with man)."""
        out, fixed = [], []
        for n, lat, lon, r, k in LABELS:
            x, y = self.P1(lat, lon)
            if "m" in k:
                if man is None:
                    continue
                X, Y = man(x, y)
            else:
                if ("w" in k) != self.is_sea(x, y):
                    continue                                # a water name only on water, a place's only on land
                X, Y = self(x, y)
            fixed.append((x, y))
            f = {"n": n, "x": round(X), "y": round(Y), "r": r}
            if k.strip("mi"):
                f["k"] = k.strip("mi")
            out.append(f)
        for n, rings in self.boros.items():
            if n == "Manhattan" or not rings:
                continue
            big = max(rings, key=len)
            # the borough's label stands on its land: the real point of its land cells nearest its centre
            cx = sum(p[0] for p in big) / len(big)
            cy = sum(p[1] for p in big) / len(big)
            best = None
            for k in range(0, len(big), max(1, len(big) // 200)):
                for t in (.25, .5, .75):
                    x, y = cx + (big[k][0] - cx) * t, cy + (big[k][1] - cy) * t
                    if _in(big, x, y) and not self.is_sea(x, y):
                        d = math.hypot(x - cx, y - cy)
                        if best is None or d < best[0]:
                            best = (d, x, y)
            if best:
                X, Y = self(best[1], best[2])
                out.append({"n": n, "x": round(X), "y": round(Y), "r": 1, "k": "b"})
        taken = []
        boro_names = {b_.lower() for b_ in BOROUGHS} | {b_.lower() for b_ in self.boros}
        fam = {f.lower(): i for i, f in enumerate(FAMOUS)}
        named = set()
        for n, k, x, y in sorted(self.places, key=lambda p: (fam.get(p[0].lower(), len(fam)), p[1] != "suburb")):
            if n.lower() in boro_names or n.lower() in named:
                continue                                    # a borough is named once, as a borough
            if not self.city(x, y) or self.detailed(x, y) or self.is_sea(x, y):
                continue
            if any(math.hypot(x - a, y - b) < LABEL_GAP for a, b in fixed):
                continue
            gap = FAMOUS_GAP if n.lower() in fam else NAME_GAP
            if any(math.hypot(x - a, y - b) < gap for a, b in taken):
                continue
            taken.append((x, y))
            named.add(n.lower())
            X, Y = self(x, y)
            out.append({"n": n, "x": round(X), "y": round(Y), "r": 3})
        return out


def _hull2(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cr(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _trace(g, nx, ny, cs):
    """The boundary loops of the set cells of a raster, page px, each closed (even-odd: holes are their own loops)."""
    def on(i, j):
        return 0 <= i < nx and 0 <= j < ny and g[j][i]
    # a simple, robust tracer: collect directed unit edges (sea on the left), then walk them
    nxt = {}
    for j in range(ny):
        for i in range(nx):
            if not g[j][i]:
                continue
            if not on(i, j - 1):
                nxt.setdefault((i, j), []).append((i + 1, j))
            if not on(i + 1, j):
                nxt.setdefault((i + 1, j), []).append((i + 1, j + 1))
            if not on(i, j + 1):
                nxt.setdefault((i + 1, j + 1), []).append((i, j + 1))
            if not on(i - 1, j):
                nxt.setdefault((i, j + 1), []).append((i, j))
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop = [start]
        cur = start
        while True:
            outs = nxt.get(cur)
            if not outs:
                break
            nx_ = outs.pop()
            if not outs:
                del nxt[cur]
            cur = nx_
            if cur == start:
                break
            loop.append(cur)
        if len(loop) >= 4:
            pts = [(x * cs, y * cs) for x, y in loop]
            pts = _dp(pts + [pts[0]], cs * 1.3)[:-1]          # the cells' stair-steps become straight runs
            if len(pts) >= 3:
                loops.append(pts)
    return loops
