"""Makes the first-level division tier (a1p-<ISO3>.json.gz) of the twelve G20 countries added to the Memory Atlas in 1.9.226, and re-keys the gazetteer's
states for them: python -I docs/world-palace/build_g20_divisions.py --src <folder with ne_10m_admin_1_states_provinces.geojson + ne_10m_populated_places_simple.geojson> [ISO ...]
Needs shapely 2.1+ (build time only: uv pip install --target <dir> shapely, PYTHONPATH=<dir>).

Per country: the divisions (Natural Earth 10m admin-1, dissolved for FRA regions / ITA regions / GBR nations and regions) are projected into world units, cut to the
country's 1:50m land (the rings of its continent tier, the SAME coast the map draws: no sliver of sea, no gap of land), any land they miss goes to the neighbouring
division that shares the longest border, and the whole partition is simplified once as a coverage (a shared border stays one line). Tier format as the other a1p
files: {"v":1,"q":50,"s":[[name,[ring flat deltas,...]],...]} plus "k": [[division, capital, lon, lat],...] (the capitals, hosted with the borders). Each tier is held under
10 KB gzipped (tolerance raised until it is). The gazetteer's rows of these countries get the division names (point in division) and exactly one class-1 row per division, its capital."""
import argparse, collections, glob, gzip, json, math, os, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapely  # noqa: E402
from shapely.geometry import Point, Polygon  # noqa: E402
from shapely.ops import unary_union, nearest_points  # noqa: E402
from alto.build.world_geo import project, gazetteer, DIR  # noqa: E402
import g20_divisions as G  # noqa: E402

Q = 50
CAP_GZ = 9800            # bytes: the tier must stay under 10 KB gzipped
MIN_ISLAND = 0.06        # world units squared: a piece smaller than this is dropped (unless it is all a division has)


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower().replace("ı", "i").replace("-", " ").replace("'", "").replace("`", "").replace(".", "").strip()


def dec(flat):
    x, y = flat[0], flat[1]
    o = [(x, y)]
    for i in range(2, len(flat), 2):
        x += flat[i]; y += flat[i + 1]; o.append((x, y))
    return o


def to_ee(coords):
    return [project(x, y) for x, y in coords]


def poly_from(geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    out = []
    for p in polys:
        ext = Polygon(to_ee(p[0]), [to_ee(h) for h in p[1:]])
        out.append(ext if ext.is_valid else shapely.make_valid(ext))
    return unary_union(out)


def land(iso, only=None):
    """The country's 1:50m land: the XOR of its rings in the continent tier(s) (an even-odd fill, as the page draws it)."""
    polys = []
    for f in sorted(glob.glob(os.path.join(DIR, "cont-*.json.gz"))):
        if only and only not in f:
            continue
        c = json.loads(gzip.open(f).read())
        for r in c["c"].get(iso, []):
            pts = [(x / Q, y / Q) for x, y in dec(r)]
            if len(pts) >= 3:
                polys.append(Polygon(pts).buffer(0))
    polys.sort(key=lambda p: -p.area)
    g = Polygon()
    for p in polys:
        g = g.symmetric_difference(p)
    return g


def pieces(g):
    return [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon" and not p.is_empty]


def divisions(iso, feats):
    """{display name: geometry in world units} in the table's order."""
    by = collections.defaultdict(list)
    for f in feats:
        p = f["properties"]
        key = p["region"] if iso in ("FRA", "ITA") else G.GBR_GROUP.get(p["region"]) if iso == "GBR" else p["name"]
        if key is None:
            continue
        by[key].append(poly_from(f["geometry"]))
    return {disp: unary_union(by[ne]) for ne, disp, *_ in G.DIV[iso] if ne in by}


def partition(L, divs):
    """Cut each division to L; give the land they miss to the division that shares the longest border (else the nearest)."""
    names = list(divs)
    taken = Polygon()
    cut = {}
    for n in sorted(names, key=lambda n: divs[n].area):          # the small ones first: a big one never swallows them where Natural Earth's faces overlap
        g = divs[n].intersection(L).difference(taken)
        g = shapely.make_valid(g) if not g.is_valid else g
        cut[n] = unary_union(pieces(g)) if not g.is_empty else Polygon()
        taken = taken.union(cut[n])
    for n in names:
        if cut[n].area < 0.02:                                 # (a division the 1:50m land barely has: Lakshadweep, Chandigarh: its own 1:10m shape)
            cut[n] = unary_union(pieces(divs[n].difference(taken)))
            taken = taken.union(cut[n])
    left = L.difference(taken)
    for p in sorted(pieces(left), key=lambda p: -p.area):
        if p.area < 1e-4:
            continue
        near = [n for n in names if not cut[n].is_empty and cut[n].distance(p) <= 0.05]
        best = max(near, key=lambda n: cut[n].intersection(p.buffer(0.02)).length) if near else min((n for n in names if not cut[n].is_empty), key=lambda n: cut[n].distance(p))
        cut[best] = unary_union([cut[best], p.buffer(0.004)])
    return cut


def ring_flat(pts):
    P = []
    for x, y in pts:
        t = (round(x * Q), round(y * Q))
        if not P or t != P[-1]:
            P.append(t)
    if len(P) > 1 and P[0] == P[-1]:
        P.pop()
    if len(P) < 3:
        return None
    P.append(P[0])
    flat = [P[0][0], P[0][1]]
    for a, b in zip(P, P[1:]):
        flat += [b[0] - a[0], b[1] - a[1]]
    return flat


def shapes(cut, tol, min_island, pins):
    names = list(cut)
    arr = shapely.coverage_simplify([cut[n] for n in names], tol) if tol else [cut[n] for n in names]
    out, simp = [], {}
    for n, g in zip(names, arr):
        ps = sorted(pieces(g), key=lambda p: -p.area)
        keep = [p for p in ps if p.area >= min_island]
        if ps:                                                   # the piece the capital stands on is never dropped (Kavaratti, Daman), nor are the pieces of a tiny division
            home = min(ps, key=lambda p: p.distance(pins[n]))
            small = sum(p.area for p in ps) < 4
            keep += [p for p in ps if p.area < min_island and (p is home or (small and p.area > 0.0004))]     # (each piece once: two identical rings would cancel under the even-odd fill)
        keep = keep or ps[:1]
        rings = []
        for p in keep:
            for r in [p.exterior] + list(p.interiors):
                fl = ring_flat(list(r.coords))
                if fl:
                    rings.append(fl)
        simp[n] = unary_union(keep) if keep else Polygon()
        out.append([n, rings])
    return out, simp


def ee_inv(x, y):
    """Equal Earth world units -> (lon, lat): the inverse of world_geo.project (Newton on the latitude)."""
    from alto.build.world_geo import _A1, _A2, _A3, _A4, _M, SCALE
    X, Y = x / SCALE, -y / SCALE
    th = Y / _A1
    for _ in range(12):
        t2 = th * th; t6 = t2 * t2 * t2
        f = th * (_A1 + _A2 * t2 + t6 * (_A3 + _A4 * t2)) - Y
        th -= f / (_A1 + 3 * _A2 * t2 + t6 * (7 * _A3 + 9 * _A4 * t2))
    t2 = th * th; t6 = t2 * t2 * t2
    lam = X * _M * (_A1 + 3 * _A2 * t2 + t6 * (7 * _A3 + 9 * _A4 * t2)) / math.cos(th)
    return math.degrees(lam), math.degrees(math.asin(math.sin(th) / _M))


def inside_point(g, pt):
    """None when pt stands well inside g (0.02 world units from the border, more than the tier's rounding), else the point to pin at: the nearest point of g drawn
    in from the border; a division too small for that (Chandigarh, Daman) is pinned at its representative point."""
    inner = g.buffer(-0.02)
    if inner.is_empty:
        return None if g.contains(pt) and g.exterior.distance(pt) > 0.012 else g.representative_point()
    return None if inner.contains(pt) else nearest_points(inner, pt)[0]


def snap_legacy(isos):
    """The earlier tiers (AUS BRA CHN IDN RUS USA ZAF) come from the 1:50m coast: a coastal capital can sit a hair outside its own face (Darwin, Salvador, Belem). Moves those
    gazetteer pins (class 1, else 0, as world_plan._state_pin takes them) to the nearest point just inside, a few kilometres at most."""
    gaz = gazetteer()
    places = [list(r) for r in gaz["places"]]
    for iso in isos:
        T = json.loads(gzip.open(os.path.join(DIR, f"a1p-{iso}.json.gz")).read())
        by = collections.defaultdict(list)
        for r in places:
            if r[2] == iso and r[3]:
                by[r[3]].append(r)
        for name, flats in T["s"]:
            g = Polygon()
            for fl in flats:
                pts = [(x / T["q"], y / T["q"]) for x, y in dec(fl)]
                if len(pts) >= 3:
                    g = g.symmetric_difference(Polygon(pts).buffer(0))
            rows = by.get(name)
            if not rows or g.is_empty:
                continue
            caps = [r for r in rows if r[7] == 1] or [r for r in rows if r[7] == 0]
            pin = max(caps or rows, key=lambda r: r[6])
            pt = Point(project(pin[4], pin[5]))
            q = inside_point(g, pt)
            if q is not None:
                old = (pin[4], pin[5])
                pin[4], pin[5] = (round(v, 4) for v in ee_inv(q.x, q.y))
                print(iso, name, pin[0], "moved", round(g.distance(pt), 2), "world units:", old, "->", (pin[4], pin[5]))
    gaz["places"] = places
    write_gz(os.path.join(DIR, "gazetteer.json.gz"), gaz)


def write_gz(path, obj):
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    with open(path, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9, mtime=0, filename="") as g:
            g.write(raw)
    return os.path.getsize(path)


def capital_rows(iso, feats, pp, gaz_rows):
    """[(division display, capital name, lon, lat)] in the table's order; coordinates from the table, else Natural Earth's places, else the gazetteer."""
    res, miss = [], []
    if iso == "TUR":
        rows = []
        for f in feats:
            p = f["properties"]
            disp = p["name_en"] or p["name"]
            rows.append((p["name"], disp, *G.TUR_CAP.get(disp, (disp,))))
    else:
        rows = G.DIV[iso]
    for ne, disp, cap, *xy in rows:
        if len(xy) == 2:
            res.append((disp, cap, xy[0], xy[1])); continue
        k = fold(cap)
        cands = [p for p in pp if p["properties"]["adm0_a3"] == iso]
        hit = [p for p in cands if k in (fold(p["properties"]["name"]), fold(p["properties"]["nameascii"]), fold(p["properties"].get("namealt") or ""))]
        hit = hit or [p for p in cands if fold(p["properties"]["adm1name"]) in (fold(disp), fold(ne)) and "Admin-1" in p["properties"]["featurecla"]]
        if hit:
            g = hit[0]["geometry"]["coordinates"]; res.append((disp, cap, round(g[0], 3), round(g[1], 3)))
            continue
        gr = [r for r in gaz_rows if r[2] == iso and k in (fold(r[0]), fold(r[1]))]
        if gr:
            res.append((disp, cap, gr[0][4], gr[0][5])); continue
        miss.append((disp, cap))
    return res, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("isos", nargs="*")
    ap.add_argument("--snap-legacy", action="store_true", help="only: snap the earlier countries' capital pins inside their faces (AUS BRA CHN IDN RUS USA ZAF)")
    a = ap.parse_args()
    if a.snap_legacy:
        return snap_legacy(a.isos or ["USA", "AUS", "BRA", "CHN", "IDN", "RUS", "ZAF"])
    isos = a.isos or list(G.COUNT)
    A1 = json.load(open(os.path.join(a.src, "ne_10m_admin_1_states_provinces.geojson"), encoding="utf-8"))["features"]
    PP = json.load(open(os.path.join(a.src, "ne_10m_populated_places_simple.geojson"), encoding="utf-8"))["features"]
    gaz = gazetteer()
    places = [list(r) for r in gaz["places"]]
    for iso in isos:
        feats = [f for f in A1 if f["properties"]["adm0_a3"] == iso and f["properties"]["name"] is not None]
        L = land(iso, "europe" if iso == "FRA" else None)
        if iso == "TUR":                                        # the table is built from the features themselves
            G.DIV["TUR"] = [(f["properties"]["name"], f["properties"]["name_en"] or f["properties"]["name"], "") for f in feats]
        divs = divisions(iso, feats)
        assert len(divs) == G.COUNT[iso], (iso, len(divs), G.COUNT[iso])
        cut = partition(L, divs)
        caps, miss = capital_rows(iso, feats, PP, places)
        assert not miss, (iso, "capitals with no coordinates", miss)
        capxy = {d: (c, lon, lat) for d, c, lon, lat in caps}
        tol, isl = 0.12, MIN_ISLAND
        steps = [(0.12, .06), (0.12, .25), (0.15, .5), (0.2, 1.0), (0.3, 1.5), (0.45, 2.0), (0.7, 3.0), (1.0, 4.0)]
        for si, (tol, isl) in enumerate(steps):
            out, simp = shapes(cut, tol, isl, {d: Point(project(v[1], v[2])) for d, v in capxy.items()})
            kk, snapped = [], []
            for n, _ in out:
                c, lon, lat = capxy[n]
                pt = Point(project(lon, lat))
                g = simp[n]
                q = inside_point(g, pt)
                if q is not None:                              # a coastal capital on the coarse coast: pinned at the nearest point just inside its division
                    snapped.append((n, c, round(g.distance(pt), 2)))
                    lon, lat = (round(v, 4) for v in ee_inv(q.x, q.y))
                kk.append([n, c, lon, lat])
            size = write_gz(os.path.join(DIR, f"a1p-{iso}.json.gz"), {"v": 1, "q": Q, "s": out, "k": kk})
            if size <= CAP_GZ:
                break
        print(iso, "divisions", len(out), "tol", tol, "min island", isl, "gz bytes", size, "capitals moved inside (world units):", snapped)
        # the gazetteer: every place of the country stands in a division; the capitals are the class-1 rows
        def which(lon, lat):
            pt = Point(project(lon, lat))
            for n, g in simp.items():
                if g.contains(pt):
                    return n
            return min(simp, key=lambda n: simp[n].distance(pt))
        keep = [r for r in places if r[2] != iso]
        mine = [r for r in places if r[2] == iso]
        for r in mine:
            r[3] = which(r[4], r[5])
            if r[7] == 1:
                r[7] = 2
        for n, c, lon, lat in kk:
            cand = [r for r in mine if r[3] == n and fold(c) in (fold(r[0]), fold(r[1]))]
            if cand:
                r = max(cand, key=lambda r: r[6])
                if r[7] != 0:
                    r[7] = 1
                r[4], r[5] = lon, lat
            else:
                near = [p for p in PP if p["properties"]["adm0_a3"] == iso and fold(p["properties"]["name"]) == fold(c)]
                pop = int(near[0]["properties"]["pop_max"]) if near else 0
                mine.append([c, unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode(), iso, n, lon, lat, pop, 1])
        places = keep + mine
    gaz["places"] = places
    write_gz(os.path.join(DIR, "gazetteer.json.gz"), gaz)
    print("gazetteer rows", len(places))


if __name__ == "__main__":
    main()
