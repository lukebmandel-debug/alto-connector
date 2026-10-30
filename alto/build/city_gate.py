"""The scored city gate (rules doc section 10): one 0-100 score for a built Memory Palace city, so a preset (or a city a
user's own Claude made) is checked by numbers before anyone looks at it.

    rep = gate(g, m, blocks=blocks, preset=pre, page=page, tiles=tiles, timing=timing, same=same)
    rep -> {"score", "pass", "checks": {"G1": {status, msg, data?, w, rule}, ...}, "fail": [...], "warn": [...],
            "blind_audit": None}

g is what palace_grid.grid() returned (with its "blocks"), m the real map build_map made (before grid): the same pair
city_report.report takes, whose 16 checks are rows G1-G14 here. G10 is city_highways.report (it had no caller).
G15-G18 are new and read g alone; G19-G22 need the runner's measurements (the stored page, the tiles, the wall clock,
a second build) and are left out when not given: a row that did not run gives its weight to the rows that did.

Scoring: ok = the row's weight, warn = half of it, fail = 0. PASS = no fail, score >= PASS_SCORE, and the zero-tolerance
rows (G5 side, G7 ends, G15 dry land) ran. Pure: no network.

Runner (offline from a cache folder; --fetch fills the cache through the repo's own Overpass code, mirror fallback):
    python -m alto.build.city_gate chicago --cache DIR [--fetch] [--fill] [--json OUT] [--md OUT]
"""
from __future__ import annotations

import math

PASS_SCORE = 85
ZERO_TOL = ("G5", "G7", "G15")
# (row, rule, weight): rules doc 10.2
ROWS = [
    ("G1", "domains sane", 3), ("G2", "phantom lines", 6), ("G3", "landmark/stop displacement", 6), ("G4", "order", 6),
    ("G5", "side of river/seam", 8), ("G6", "seams", 6), ("G7", "dangling ends", 5), ("G8", "avenues", 3),
    ("G9", "transit", 6), ("G10", "highways", 4), ("G11", "cut blocks", 3), ("G12", "data size per km2", 3),
    ("G13", "page overlap", 3), ("G14", "landmark spacing / fronts", 6), ("G15", "dry land", 5), ("G16", "parks", 3),
    ("G17", "landmarks", 4), ("G18", "labels", 4), ("G19", "page bytes", 6), ("G20", "tiles", 3),
    ("G21", "build time", 2), ("G22", "determinism", 3),
]
FROM_REPORT = {"G1": ("domains",), "G2": ("phantom",), "G3": ("displacement",), "G4": ("order",), "G5": ("side",),
               "G6": ("seam_fidelity", "tjoin", "cross_seam"), "G7": ("ends",), "G8": ("avenues",), "G9": ("transit",),
               "G11": ("cut",), "G12": ("size",), "G13": ("overlap",), "G14": ("spacing", "fronts")}
CHANNEL_PX = 40.0               # page px: a named channel keeps at least this much water
LM_MIN, LM_MAX = 8, 24          # landmarks drawn
PAGE_FAIL, PAGE_WARN = 976 * 1024, 900 * 1024
BASE_MAX, TILE_MAX = 350 * 1024, 64 * 1024
VIEW = (1440, 900)              # px: the screen the whole-city zoom fits (the labels row)
SLOW_S = 60.0                   # s: a set-up from the cache takes at most this long
_RANK = {"ok": 0, "warn": 1, "fail": 2}


# ── geometry ───────────────────────────────────────────────────────────────
def _pairs(p):
    return list(zip(p[0::2], p[1::2]))


def _inside(ring, x, y):
    pts = _pairs(ring) if ring and not isinstance(ring[0], (list, tuple)) else ring
    c = False
    for (x0, y0), (x1, y1) in zip(pts, pts[-1:] + pts[:-1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _seg_d(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L))
    return math.hypot(px - x0 - t * dx, py - y0 - t * dy)


def _line_d(p, x, y):
    pts = _pairs(p)
    return min((_seg_d(x, y, *a, *b) for a, b in zip(pts, pts[1:])), default=1e18)


def _rings(v):
    """g["water"] / g["sea"]: a list of flat rings (or one flat ring)."""
    if not v:
        return []
    if isinstance(v[0], (int, float)):
        return [v]
    return [r for r in v if r and len(r) >= 6]


def _worst(sts):
    return max(sts, key=lambda s: _RANK.get(s, 0)) if sts else "ok"


# ── the new rows ───────────────────────────────────────────────────────────
def wet_at(g):
    """A test (x, y) -> name of the water there (page px) or None: the water rings, the sea, the river bands."""
    rings = [("water", r) for r in _rings(g.get("water"))] + [("sea", r) for r in _rings(g.get("sea"))]
    bands = [(b.get("n") or "river", b["p"], float(b.get("w") or 0) / 2) for b in g.get("river") or [] if b.get("p")]

    def at(x, y):
        for n, b, hw in bands:
            if _line_d(b, x, y) < hw - 2:
                return n
        for n, r in rings:
            if _inside(r, x, y):
                return n
        return None
    return at


def _points(g, blocks):
    """(kind, name, x, y) of everything that must stand on land: landmarks (and their card centres), stations, lot
    centres."""
    out = [("landmark", l.get("n"), l["x"], l["y"]) for l in g.get("landmarks") or [] if "x" in l]
    out += [("station", s.get("n"), s["x"], s["y"]) for s in g.get("stations") or [] if "x" in s]
    for b in blocks or []:
        for lot in b.get("lots") or []:
            r = lot.get("r") if isinstance(lot, dict) else None
            if r and len(r) >= 6:
                xs, ys = r[0::2], r[1::2]
                out.append(("lot", lot.get("id") or "", sum(xs) / len(xs), sum(ys) / len(ys)))
            elif isinstance(lot, dict) and "x" in lot and "y" in lot:
                out.append(("lot", lot.get("id") or "", lot["x"], lot["y"]))
    return out


def g_dry_land(g, blocks=None, channels=()):
    """G15: no landmark, station or lot centre in the water the page draws; every named channel still a band of at
    least CHANNEL_PX (a channel the preset names and the page lacks is a fail)."""
    at = wet_at(g)
    wet = [(k, n, round(x), round(y), w) for k, n, x, y in _points(g, blocks) for w in [at(x, y)] if w]
    bands = {}
    for b in g.get("river") or []:
        n = b.get("n") or ""
        bands[n] = max(bands.get(n, 0.0), float(b.get("w") or 0))
    thin = sorted(n for n, w in bands.items() if w < CHANNEL_PX)
    missing = [c for c in channels or () if not any(c.lower() == n.lower() for n in bands)]
    st = "fail" if wet or thin or missing else "ok"
    msg = "%d points in water (%s); %d bands, %d under %d px; channels missing: %s" % (
        len(wet), ", ".join(sorted({k for k, *_ in wet})) or "-", len(bands), len(thin), CHANNEL_PX, ", ".join(missing) or "none")
    return st, msg, {"wet": wet[:20], "thin": thin, "missing": missing, "bands": {k: round(v) for k, v in bands.items()}}


def park_shapes(g):
    """The parks as the page shapes them (palace_parks.shape): [{n, r: [page rings]}]."""
    from .palace_parks import shape
    gr = g.get("grid") or {}
    return shape(g.get("parks") or [], gr.get("xg") or [], gr.get("yg") or [])


def g_parks(g, named=(), must=()):
    """G16: every must-park drawn (fail), the preset's named parks drawn (warn); no street runs through a park's green
    (fail); no landmark card stands in a park (warn)."""
    try:
        shaped = park_shapes(g)
    except Exception as e:                                  # noqa: BLE001
        return "warn", "parks could not be shaped: %s" % e, {}
    drawn = {(p.get("n") or "").lower() for p in g.get("parks") or []}
    drawn |= {(p.get("n") or "").lower() for p in shaped}

    def has(n):
        from .palace_parks import short_name
        return n.lower() in drawn or short_name(n).lower() in drawn
    miss_must = [n for n in must or () if not has(n)]
    miss = [n for n in named or () if not has(n) and n not in miss_must]
    through = []
    for s in g.get("streets") or []:
        pts = _pairs(s.get("p") or [])
        for pk in shaped:
            for r in pk.get("r") or []:
                xs, ys = r[0::2], r[1::2]
                bb = (min(xs), min(ys), max(xs), max(ys))
                run = 0.0
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    if max(x0, x1) < bb[0] or min(x0, x1) > bb[2] or max(y0, y1) < bb[1] or min(y0, y1) > bb[3]:
                        continue
                    L = math.hypot(x1 - x0, y1 - y0)
                    k = max(1, int(L // 10))
                    run += sum(L / k for i in range(k) if _inside(r, x0 + (x1 - x0) * (i + .5) / k, y0 + (y1 - y0) * (i + .5) / k))
                if run > 30:
                    through.append((s.get("n") or "", pk.get("n"), round(run)))
    on = [(l.get("n"), pk.get("n")) for l in g.get("landmarks") or [] if "x" in l for pk in shaped
          for r in pk.get("r") or [] if _inside(r, l["x"], l["y"])]
    st = "fail" if miss_must or through else ("warn" if miss or on else "ok")
    msg = "%d parks drawn; must-parks missing %d, named missing %d; %d streets through a park; %d landmarks on a park" % (
        len(shaped), len(miss_must), len(miss), len(through), len(on))
    return st, msg, {"missing_must": miss_must, "missing": miss[:20], "through": through[:20], "on": on[:10]}


def g_landmarks(g):
    """G17: LM_MIN to LM_MAX landmarks drawn, and no two landmark cards overlap."""
    L = [l for l in g.get("landmarks") or [] if l.get("box")]
    n = len(g.get("landmarks") or [])
    hits = []
    for i in range(len(L)):
        a = L[i]["box"]
        for b_ in L[i + 1:]:
            b = b_["box"]
            ox, oy = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
            if ox > 1 and oy > 1:
                hits.append((L[i].get("n"), b_.get("n"), round(ox * oy)))
    st = "fail" if hits or not (LM_MIN <= n <= LM_MAX) else "ok"
    return st, "%d landmarks drawn (%d-%d); %d card overlaps" % (n, LM_MIN, LM_MAX, len(hits)), {"overlaps": hits[:20]}


def _text_box(x, y, text, fs, z, spacing, up=0.0):
    """A label's box in page px at zoom z (screen px per page px): font fs screen px, centred on x, its baseline at y."""
    w = len(text) * fs * (.62 + spacing) / z
    h = fs / z
    y0 = y - h * (1 + up)
    return (x - w / 2, y0, x + w / 2, y0 + h)


def g_labels(g, areas=None):
    """G18: at the whole-city zoom (the city fitted to a VIEW screen) no two of the rank-1 names and the landmark names
    overlap (the page would hide one), and none runs off the glass. Sizes as the page's CSS sets them (lblFS)."""
    W, H = float(g.get("W") or 1), float(g.get("H") or 1)
    z = min(VIEW[0] / W, VIEW[1] / H)
    labs = []
    for a in areas if areas is not None else g.get("areas") or []:
        if (a.get("r") or 2) == 1:
            labs.append(("area", a["n"], _text_box(a["x"], a["y"], a["n"].upper(), max(9.0, min(13.0, 7.5 + 5 * z)), z, .09)))
    for l in g.get("landmarks") or []:
        if "x" in l:
            labs.append(("landmark", l.get("n") or "", _text_box(l["x"], (l.get("box") or [0, l["y"]])[1], l.get("n") or "",
                                                                 11.5, z, .01)))
    hits = []
    for i in range(len(labs)):
        a = labs[i][2]
        for k, n, b in labs[i + 1:]:
            if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                hits.append((labs[i][1], n))
    off = [n for _k, n, b in labs if b[0] < 0 or b[1] < 0 or b[2] > W or b[3] > H]
    st = "fail" if hits else ("warn" if off else "ok")
    return st, "%d top names at the whole-city zoom (x%.3f): %d overlapping pairs, %d off the glass" % (
        len(labs), z, len(hits), len(off)), {"overlaps": hits[:20], "off": off[:10]}


def g_page(page):
    """G19: the stored private page (with the runner's 100-building brief) <= PAGE_FAIL, warn over PAGE_WARN."""
    b = page["stored"]
    st = "fail" if b > PAGE_FAIL else ("warn" if b > PAGE_WARN else "ok")
    return st, "stored page %d KB with %d buildings (fail > %d KB, warn > %d KB)" % (
        b // 1024, page.get("buildings", 0), PAGE_FAIL // 1024, PAGE_WARN // 1024), dict(page)


def g_tiles(tiles):
    """G20: the base <= BASE_MAX gz, every tile <= TILE_MAX gz."""
    base, big = tiles.get("base_gz") or 0, tiles.get("max") or 0
    st = "fail" if base > BASE_MAX or big > TILE_MAX else "ok"
    return st, "base %d KB gz (max %d); %d tiles, largest %d KB gz (max %d); %d KB gz in all" % (
        base // 1024, BASE_MAX // 1024, tiles.get("tiles") or 0, big // 1024, TILE_MAX // 1024,
        (tiles.get("bytes") or 0) // 1024), dict(tiles)


def g_time(timing):
    s = timing["set_up_s"]
    return ("ok" if s <= SLOW_S else "warn"), "set_up %.1f s from the cache (warn > %d s); map from %s" % (
        s, SLOW_S, timing.get("source") or "cache"), dict(timing)


def g_same(same):
    return ("ok" if same["same"] else "fail"), ("two builds give identical map data" if same["same"]
                                                else "two builds differ: %s" % same.get("why", "")), dict(same)


# ── the gate ───────────────────────────────────────────────────────────────
def gate(g, m, blocks=None, preset=None, aliases=None, page=None, tiles=None, timing=None, same=None, areas=None) -> dict:
    """The scored checklist. preset: the city's preset dict (parks, channels, layout); aliases: {page label: real name}."""
    from . import city_report, city_highways
    from .city_spec import resolve
    preset = preset or {}
    blocks = blocks if blocks is not None else g.get("blocks")
    rep = city_report.report(g, m, aliases=aliases, blocks=blocks)
    spec = resolve(preset.get("layout")) or resolve(m.get("layout")) or resolve(g.get("layout"))
    checks, fail, warn = {}, [], []

    def run(fn):
        try:
            return fn()
        except Exception as e:                              # noqa: BLE001 — a row that cannot run is a finding, never a crash
            return "warn", "check could not run: %s: %s" % (type(e).__name__, e), {}
    rows = {}
    for row, names in FROM_REPORT.items():
        parts = [rep["checks"][n] for n in names if n in rep["checks"]]
        st = _worst([p["status"] for p in parts])
        rows[row] = (st, "; ".join("%s: %s" % (n, rep["checks"][n]["msg"]) for n in names if n in rep["checks"]),
                     {n: rep["checks"][n].get("data") for n in names if rep["checks"].get(n, {}).get("data")})
    rows["G10"] = run(lambda: city_highways.report(g, m)) if g.get("hw") else ("ok", "no highways drawn", {})
    rows["G15"] = run(lambda: g_dry_land(g, blocks, preset.get("channels") or ()))
    rows["G16"] = run(lambda: g_parks(g, preset.get("parks") or (), spec.must_parks if spec else ()))
    rows["G17"] = run(lambda: g_landmarks(g))
    rows["G18"] = run(lambda: g_labels(g, areas))
    if page:
        rows["G19"] = run(lambda: g_page(page))
    if tiles:
        rows["G20"] = run(lambda: g_tiles(tiles))
    if timing:
        rows["G21"] = run(lambda: g_time(timing))
    if same:
        rows["G22"] = run(lambda: g_same(same))
    tot = got = 0.0
    for row, rule, w in ROWS:
        if row not in rows:
            continue
        st, msg, data = rows[row]
        st = st if st in _RANK else "warn"
        tot += w
        got += w * {"ok": 1.0, "warn": .5, "fail": 0.0}[st]
        checks[row] = {"rule": rule, "w": w, "status": st, "msg": msg, **({"data": data} if data else {})}
        if st == "fail":
            fail.append("%s %s: %s" % (row, rule, msg))
        elif st == "warn":
            warn.append("%s %s: %s" % (row, rule, msg))
    score = round(100.0 * got / tot, 1) if tot else 0.0
    ok = not fail and score >= PASS_SCORE and all(r in checks for r in ZERO_TOL)
    return {"score": score, "pass": ok, "checks": checks, "fail": fail, "warn": warn, "blind_audit": None,
            "ran": [r for r, _n, _w in ROWS if r in checks], "skipped": [r for r, _n, _w in ROWS if r not in checks]}


def summary(rep) -> str:
    lines = ["score %.1f  %s" % (rep["score"], "PASS" if rep["pass"] else "NOT PASSED")]
    for row, c in rep["checks"].items():
        lines.append("%-4s %-28s %-4s w%-2d %s" % (row, c["rule"], c["status"], c["w"], c["msg"]))
    if rep.get("skipped"):
        lines.append("not run: " + ", ".join(rep["skipped"]))
    return "\n".join(lines)


def markdown(rep, title) -> str:
    out = ["# %s: city gate" % title, "", "Score **%.1f** / 100, %s (pass = score >= %d, no fail, rows %s ran)." % (
        rep["score"], "**PASS**" if rep["pass"] else "**not passed**", PASS_SCORE, ", ".join(ZERO_TOL)), "",
        "| row | rule | w | status | measured |", "|---|---|---|---|---|"]
    for row, c in rep["checks"].items():
        out.append("| %s | %s | %d | %s | %s |" % (row, c["rule"], c["w"], c["status"], c["msg"].replace("|", "/")))
    if rep.get("skipped"):
        out += ["", "Not run: %s." % ", ".join(rep["skipped"])]
    return "\n".join(out) + "\n"


# ── the runner ─────────────────────────────────────────────────────────────
def _districts(bbox, n=6):
    """The runner's user: n districts in the middle third of the box (a 3 x 2 split), so the zone and the tiles are those of a
    real palace, not the whole box."""
    s, w, nn, e = bbox
    la0, la1 = s + (nn - s) / 3, s + 2 * (nn - s) / 3
    lo0, lo1 = w + (e - w) / 3, w + 2 * (e - w) / 3
    cols, rows = 3, max(1, n // 3)
    out = []
    for k in range(n):
        i, j = k % cols, k // cols
        out.append({"unit": k, "name": "", "bounds": [la0 + (la1 - la0) * j / rows, lo0 + (lo1 - lo0) * i / cols,
                                                       la0 + (la1 - la0) * (j + 1) / rows, lo0 + (lo1 - lo0) * (i + 1) / cols]})
    return out


def page_bytes(pal, n_buildings=100, n_sections=6) -> dict:
    """The stored private page of a palace on this city with n_buildings top-level buildings in n_sections sections (the rules
    doc's 100-building brief), and the base file's gzip size (palace_tiles.strip)."""
    import copy
    from .builder import build_timeline, load_brief
    from .single_file import private_page
    from .private_shell import stored_bytes
    from . import palace_tiles
    acts = [{"label": "SECTION %d" % (i + 1), "short": "S%d" % (i + 1), "color": "#4a9eff"} for i in range(n_sections)]
    nodes = [{"id": "b%03d" % i, "act": i % n_sections, "tag": "Room", "title": "Building %d" % (i + 1),
              "desc": "A test building, number %d." % (i + 1)} for i in range(n_buildings)]
    brief = {"title": "Gate", "subject": "City gate", "timeline_id": "city-gate", "mode": "palace", "node_noun": "Room",
             "period_noun": "Wing", "accent": "#5b8def", "acts": acts, "palace": copy.deepcopy(pal)}
    b, nd, cn = load_brief({"brief": brief, "nodes": nodes, "connections": []})
    html, _ = build_timeline(b, nd, cn)
    p = private_page(b, html)
    return {"stored": stored_bytes(p), "buildings": n_buildings, "base_gz": palace_tiles.LAST_BASE.get("gz")}


def run_city(pid, cache, fetch=False, fill=False, log=print) -> dict:
    """Build the preset `pid` offline from `cache` (fetch=True fills the cache first) the way set_up_palace does, then the gate."""
    import copy
    import os
    import tempfile
    import time
    from .. import palace_map as pm
    from . import city_presets, city_setup, palace, palace_grid, palace_tiles
    pre = city_presets.get(pid)
    if pre is None:
        raise SystemExit("no preset %r" % pid)
    os.environ.setdefault("ALTO_TILES_DIR", tempfile.mkdtemp(prefix="alto-gate-tiles-"))
    bbox = tuple(pre["bbox"])
    blds = city_presets.buildings_for(pre)
    names = list(dict.fromkeys(list(pre["landmarks"]) + [b["name"] for b in blds if b.get("name")]))
    mark = pm.overpass_mark()
    raw = city_setup.fetch_city(bbox, cache_dir=cache, names=names, offline=not fetch, log=log if fetch else None)
    src = pm.overpass_report(mark)
    dists = _districts(bbox)
    cap, stats = {}, {}
    g0, cut0 = palace_grid.grid, palace_tiles.cut

    def grid(m, **kw):
        cap["m"] = copy.deepcopy(m)
        g = g0(m, **kw)
        cap["g"] = copy.deepcopy(g)
        return g

    def cut(*a, **kw):
        out = cut0(*a, **kw)
        stats.update(out[1])
        return out

    def build():
        return palace.set_up(pre["place"], list(bbox), districts=dists, majors=pre["majors"], landmarks=names, cache_dir=cache,
                             raw=copy.deepcopy(raw), diagonals=pre["diagonals"], buildings=blds, parks=pre["parks"],
                             areas=pre["areas"], transit=pre.get("transit"), preset=pid, far_bank=bool(pre.get("far_bank")),
                             layout=pre.get("layout"), river_names=pre.get("river_names"), fill=fill, offline=not fetch)
    palace_grid.grid, palace_tiles.cut = grid, cut
    try:
        t0 = time.time()
        pal = build()
        dt = time.time() - t0
        g, m = cap["g"], cap["m"]
        pal2 = build()
    finally:
        palace_grid.grid, palace_tiles.cut = g0, cut0
    d1, d2 = palace.unpack(pal["data_z"]), palace.unpack(pal2["data_z"])
    same = {"same": d1 == d2, **({} if d1 == d2 else {"why": "data_z differs"})}
    page = page_bytes(pal)
    tiles = dict(stats, base_gz=page.pop("base_gz", None))
    from .palace_areas import layout as area_layout
    areas = area_layout(d1["map"], pre["areas"], [])
    aliases = {b.get("label"): b["name"] for b in blds if b.get("label")}
    rep = gate(g, m, preset=pre, aliases=aliases or None, page=page, tiles=tiles,
               timing={"set_up_s": round(dt, 1), "source": "fetch" if fetch else "cache", "overpass": src}, same=same,
               areas=areas)
    rep["city"] = {"preset": pid, "place": pre["place"], "bbox": list(bbox), "engine": {k: v for k, v in (g.get("engine") or {}).items()
                                                                                        if k in ("path", "domains", "seams", "layout")}}
    return rep


def main(argv=None):
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Build a preset city offline and score it (rules doc section 10).")
    ap.add_argument("city")
    ap.add_argument("--cache", required=True, help="the OSM cache folder (city_setup.fetch_city's)")
    ap.add_argument("--fetch", action="store_true", help="fetch what the cache lacks (Overpass, mirror fallback)")
    ap.add_argument("--fill", action="store_true", help="with the fill-in buildings (fetched or cached footprints)")
    ap.add_argument("--json")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    rep = run_city(a.city, a.cache, fetch=a.fetch, fill=a.fill)
    print(summary(rep))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1, sort_keys=True, default=str)
            f.write("\n")
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(markdown(rep, rep["city"]["place"]))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
