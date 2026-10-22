"""Build the World Palace's geodata (alto/assets/world/) from Natural Earth (public domain, naturalearthdata.com, v5.1.2 GeoJSON).

Run:  python -I docs/world-palace/build_world_geo.py --src <folder holding the Natural Earth .geojson files>

Needs ne_110m_admin_0_countries, ne_50m_admin_0_countries, ne_10m_populated_places_simple and ne_50m_admin_1_states_provinces_lines.
Writes, gzipped and deterministic (same sources, same bytes):

  gazetteer.json.gz   build side only (world_plan.py): every country (name, other names, subregion, continent, label point, capital) and the
                      populated places (capitals of countries and states, and towns over 50,000) that set_up_world resolves names against
  base.json.gz        hosted: the whole world at 1:110m — one ring list per country, plus the graticule and the outline of the globe
  cont-<slug>.json.gz hosted: one continent at 1:50m, fetched when the reader zooms into it
  a1-<ISO3>.json.gz   hosted: a country's state or province lines at 1:50m, fetched when several of its states are in use

Geometry is projected here (Equal Earth, world.project) into world units (the globe 2000 wide, north up), simplified with the borders shared between
countries simplified once (a border stays one line for both neighbours), and stored as integer rings: [x0, y0, dx1, dy1, ...] in tenths of a unit
(base) or fiftieths (detail). The page smooths them into curves (palace_world.py).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from alto.build.world_geo import project, SUBREGIONS, slug       # noqa: E402

OUT = os.path.join(ROOT, "alto", "assets", "world")
TIERS = {"base": {"tol": 1.0, "min_area": 3.0, "q": 10}, "detail": {"tol": 0.18, "min_area": 0.08, "q": 50}}


def _load(src, name):
    with open(os.path.join(src, name + ".geojson"), encoding="utf-8") as f:
        return json.load(f)["features"]


def _rings(geom):
    if not geom:
        return []
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"] if geom["type"] == "MultiPolygon" else []
    out = []
    for poly in polys:
        for ring in poly:
            out += _split_dateline(ring)
    return out


def _split_dateline(ring):
    """A ring that crosses the 180th meridian (the Aleutians, Chukotka, Fiji) as two rings, one each side, each clamped to its edge of the map —
    drawn whole it would run straight across the world."""
    if not any(abs(b[0] - a[0]) > 180 for a, b in zip(ring, ring[1:])):
        return [ring]
    east = [((x + 360) if x < 0 else x, y) for x, y in ring]                   # 0..360: the ring is continuous
    a = [(min(x, 180.0), y) for x, y in east]                                  # the part in the eastern hemisphere
    b = [(max(x - 360, -180.0), y) for x, y in east]                           # the part in the western
    return [r for r in (a, b) if len({p for p in r}) >= 3 and any(abs(x) < 179.999 for x, _ in r)]


def _key(p):
    return (round(p[0], 6), round(p[1], 6))


def _dp(pts, tol):
    """Douglas-Peucker on a list of (x, y), endpoints kept."""
    if len(pts) < 3:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / L if L else math.hypot(x - x1, y - y1)
            if d > best:
                best, bi = d, i
        if bi > 0 and best > tol:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def _area(pts):
    return 0.5 * sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))


def simplify(features, tier):
    """{country id: [rings of projected (x, y)]}: shared borders simplified once, tiny islands dropped (never a country's largest ring)."""
    tol, min_area = TIERS[tier]["tol"], TIERS[tier]["min_area"]
    raw = {}
    for cid, geom in features:
        rings = []
        for r in _rings(geom):
            pts = [_key(p) for p in r]
            if pts and pts[0] == pts[-1]:
                pts = pts[:-1]
            if len(pts) >= 3:
                rings.append(pts)
        if rings:
            raw.setdefault(cid, []).extend(rings)
    owners = {}
    for cid, rings in raw.items():
        for ri, r in enumerate(rings):
            for p in r:
                owners.setdefault(p, set()).add((cid, ri))
    out = {}
    for cid, rings in raw.items():
        done = []
        for ri, r in enumerate(rings):
            n = len(r)
            own = [frozenset(owners[p]) for p in r]
            # a vertex is fixed where the set of rings sharing it changes: the ends of every shared border
            fixed = [i for i in range(n) if len(own[i]) > 2 or own[i] != own[i - 1] or own[i] != own[(i + 1) % n]]
            if not fixed:
                m = min(range(n), key=lambda i: r[i])
                seq = r[m:] + r[:m]
                pts = [project(*p) for p in seq + [seq[0]]]
                simp = _dp(pts, tol)[:-1]
            else:
                simp = []
                for k, a in enumerate(fixed):
                    b = fixed[(k + 1) % len(fixed)]
                    seg = [r[i % n] for i in range(a, (b if b > a else b + n) + 1)]
                    flip = seg[-1] < seg[0]                          # one orientation per border, so both neighbours simplify it alike
                    pts = [project(*p) for p in (seg[::-1] if flip else seg)]
                    s = _dp(pts, tol)
                    if flip:
                        s = s[::-1]
                    simp += s[:-1]
            if len(simp) >= 3:
                done.append(simp)
        keep = [s for s in done if abs(_area(s)) >= min_area]
        if not keep and done:
            keep = [max(done, key=lambda s: abs(_area(s)))]
        if keep:
            out[cid] = keep
    return out


def encode(rings, q):
    """Integer delta rings: [x0, y0, dx1, dy1, ...] in 1/q units; repeated points dropped."""
    enc = []
    for r in rings:
        pts = []
        for x, y in r:
            p = (round(x * q), round(y * q))
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(pts) < 3:
            continue
        flat = [pts[0][0], pts[0][1]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            flat += [bx - ax, by - ay]
        enc.append(flat)
    return enc


def graticule(step=20):
    lines = []
    for lon in range(-180, 181, step):
        lines.append([project(lon, lat / 2) for lat in range(-180, 181, 4)])
    for lat in range(-80, 81, step):
        lines.append([project(lon / 2, lat) for lon in range(-360, 361, 4)])
    return lines


def sphere():
    pts = [project(180, lat / 2) for lat in range(180, -181, -2)] + [project(-180, lat / 2) for lat in range(-180, 181, 2)]
    return pts


def _write(name, obj):
    os.makedirs(OUT, exist_ok=True)
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    with open(os.path.join(OUT, name), "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9, mtime=0, filename="") as g:
            g.write(raw)
    return len(raw)


def _cid(p):
    a = p.get("ADM0_A3") or p.get("adm0_a3")
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    args = ap.parse_args()
    c110 = _load(args.src, "ne_110m_admin_0_countries")
    c50 = _load(args.src, "ne_50m_admin_0_countries")
    pp = _load(args.src, "ne_10m_populated_places_simple")
    a1 = _load(args.src, "ne_50m_admin_1_states_provinces_lines")

    # ── gazetteer ────────────────────────────────────────────────────────
    places = []
    for f in pp:
        p = f["properties"]
        # a country's capital is the seat of government NE marks adm0cap without capalt (Pretoria, not Johannesburg or Cape Town)
        cls = 0 if p.get("adm0cap") == 1 and not p.get("capalt") else 1 if p["featurecla"].startswith("Admin-1") else 2
        pop = int(p.get("pop_max") or 0)
        if cls == 2 and pop < 50000:
            continue
        clean = lambda t: " ".join((t or "").split())
        places.append([clean(p["name"]), clean(p.get("nameascii") or p["name"]), p["adm0_a3"], clean(p.get("adm1name")),
                       round(p["longitude"], 4), round(p["latitude"], 4), pop, cls])
    places.sort(key=lambda r: (r[2], -r[6], r[0]))
    countries = {}
    for f in c50:
        p = f["properties"]
        cid = _cid(p)
        if p.get("SUBREGION") == "Seven seas (open ocean)" and p.get("CONTINENT") != "Antarctica" and cid not in ("ATF",):
            pass
        names = sorted({n for n in (p.get("NAME"), p.get("NAME_LONG"), p.get("ADMIN"), p.get("NAME_EN"), p.get("FORMAL_EN"), p.get("BRK_NAME"),
                                    p.get("NAME_SORT"), p.get("ABBREV"))
                        if n and isinstance(n, str)} - {p.get("NAME")})
        caps = [r for r in places if r[2] == cid and r[7] == 0]
        cap = max(caps, key=lambda r: r[6]) if caps else None
        if not cap:
            own = [r for r in places if r[2] == cid]
            cap = max(own, key=lambda r: (r[7] == 1, r[6])) if own else None
        # the name on the map: the shorter of NAME / NAME_LONG without abbreviations ("United States", "Russia", "Central African Republic")
        plain = [n for n in (p.get("NAME"), p.get("NAME_LONG")) if n and "." not in n and len(n) <= 26]
        short = min(plain, key=lambda n: (len(n), n)) if plain else p["NAME"]
        names = sorted(set(names) | {p["NAME"]} - {short})
        countries[cid] = {"n": short, "alt": names, "iso2": p.get("ISO_A2_EH") if p.get("ISO_A2_EH") not in (None, "-99") else "",
                          "iso3": p.get("ISO_A3_EH") if p.get("ISO_A3_EH") not in (None, "-99") else "",
                          "sub": p.get("SUBREGION") or "", "cont": p.get("CONTINENT") or "",
                          "lab": [round(p["LABEL_X"], 3), round(p["LABEL_Y"], 3)],
                          "cap": [cap[0], cap[4], cap[5]] if cap else None, "rank": p.get("LABELRANK") or 9,
                          "big": 0, "area": 0}
    for f in c110:
        cid = _cid(f["properties"])
        if cid in countries:
            countries[cid]["big"] = 1
    det = simplify([(_cid(f["properties"]), f["geometry"]) for f in c50], "detail")
    for cid, rings in det.items():
        if cid in countries:
            countries[cid]["area"] = round(sum(abs(_area(r)) for r in rings), 1)
    gz = _write("gazetteer.json.gz", {"v": 1, "countries": countries, "places": places})

    # ── hosted tiers ─────────────────────────────────────────────────────
    base = simplify([(_cid(f["properties"]), f["geometry"]) for f in c110], "base")
    q = TIERS["base"]["q"]
    sizes = {"gazetteer": gz}
    sizes["base"] = _write("base.json.gz", {"v": 1, "q": q, "c": {cid: encode(r, q) for cid, r in sorted(base.items())},
                                            "grat": [encode([l], q)[0] for l in graticule()],
                                            "sphere": encode([sphere()], q)[0]})
    qd = TIERS["detail"]["q"]
    by_cont = {}
    for f in c50:
        p = f["properties"]
        by_cont.setdefault(slug(p.get("CONTINENT") or "other"), []).append(_cid(p))
    for cs, ids in sorted(by_cont.items()):
        rings = {cid: encode(det[cid], qd) for cid in sorted(ids) if cid in det}
        xs = [x for cid in ids if cid in det for r in det[cid] for x, _ in r]
        ys = [y for cid in ids if cid in det for r in det[cid] for _, y in r]
        sizes["cont-" + cs] = _write(f"cont-{cs}.json.gz", {"v": 1, "q": qd, "c": rings,
                                                             "bb": [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]})
    lines = {}
    for f in a1:
        p = f["properties"]
        cid = p.get("adm0_a3") or p.get("ADM0_A3")
        g = f["geometry"]
        parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
        for part in parts:
            lines.setdefault(cid, []).append(_dp([project(*c) for c in part], TIERS["detail"]["tol"]))
    for cid, ls in sorted(lines.items()):
        enc = []
        for l in ls:
            pts = [(round(x * qd), round(y * qd)) for x, y in l]
            if len(pts) >= 2:
                flat = [pts[0][0], pts[0][1]]
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    flat += [bx - ax, by - ay]
                enc.append(flat)
        sizes["a1-" + cid] = _write(f"a1-{cid}.json.gz", {"v": 1, "q": qd, "l": enc})
    with open(os.path.join(OUT, "NOTICE"), "w", encoding="utf-8") as f:
        f.write("Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com (public domain), v5.1.2:\n"
                "ne_110m_admin_0_countries, ne_50m_admin_0_countries, ne_10m_populated_places_simple, ne_50m_admin_1_states_provinces_lines.\n"
                "Projected (Equal Earth), simplified and re-encoded by docs/world-palace/build_world_geo.py.\n")
    for k, v in sizes.items():
        print(f"{k:24s} {v:9,d} B json")
    print("subregions not in the sweep:", sorted({c["sub"] for c in countries.values()} - set(SUBREGIONS)))


if __name__ == "__main__":
    main()
