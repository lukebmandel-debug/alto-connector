"""Fill-in (palace_fillin.py): off by default and byte-identical; tiers; packing round trip; reach; the polite
tiled fetch; v2 domains (a turned lattice); set_up's wiring."""
import math
from types import SimpleNamespace

from alto import palace_map as pm
from alto.build import palace as pal
from alto.build import palace_fillin as pf
from alto.build.palace_grid import Mapping


def test_off_is_unchanged():
    b = SimpleNamespace(palace={"data_z": "x"})
    assert pal.palace_js(b) is pal.PALACE_JS
    assert pal.palace_css(b) is pal.PALACE_CSS


def test_on_splices_every_hook_once():
    b = SimpleNamespace(palace={"fill_z": "x"})
    js = pal.palace_js(b)
    for fn in ("function fillDraw(", "function fillPaint(", "function fillHover(", "h+=fillKeyRow();", "Key to the city'); fillWire(k);",
               "pmSheetClicks(); fillWirePhone(box);", "h+=fillPhoneRow();", "fillDraw(svg);\n  drawBuildings(svg);"):
        assert js.count(fn) == 1, (fn, js.count(fn))
    assert pal.palace_css(b).endswith(pf.FILL_CSS)


def test_tiers():
    assert pf.tier_of({"building": "yes"}, 10, 0) is None
    assert pf.tier_of({"building": "shed"}, 25, 3) is None              # a shed behind the row
    assert pf.tier_of({"building": "office", "height": "150"}, 900, 150) == 1
    assert pf.tier_of({"building": "yes", "building:levels": "9"}, 400, pf.height_of({"building:levels": "9"})) == 2
    assert pf.tier_of({"building": "yes"}, 500, 9) == 3
    assert pf.tier_of({"building": "house"}, 80, 8) == 4
    assert pf.height_of({"height": "120 m"}) == 120


def _ring_set(r):
    return sorted((round(x, 3), round(y, 3)) for x, y in r)


def test_pack_round_trip_every_kind():
    sq = [(0, 0), (10, 0), (10, 30), (0, 30)]
    row = [[(x, 50), (x + 6, 50), (x + 6, 50 + d), (x, 50 + d)] for x, d in ((20, 30), (26, 30), (32, 31))]   # one front, one depth
    deep = [[(x, 100), (x + 5, 100), (x + 5, 100 + d), (x, 100 + d)] for x, d in ((0, 10), (5, 25))]         # one front, two depths
    ell = [(60, 0), (80, 0), (80, 10), (70, 10), (70, 20), (60, 20)]
    tri = [(90, 0), (100, 0), (95, 9)]
    recs = [(0, 0, 0, sq, 0, ""), (0, 0, 0, ell, 0, ""), (0, 0, 1, tri, 0, "")]
    recs += [(0, 1, 0, r, 0, "") for r in row + deep]
    recs.append((0, 2, 0, ("t", 5, 200, 10, 12, 4), 0, ""))
    s, hs, ns, n = pf._encode(recs, strips=True)
    f = {"L": ["", "", "", s], "q": [1, 1, 1, 1], "doms": [[0.0, 0.0, 0.0]]}
    got = sorted(_ring_set(r) for r in pf.decode(f, 4))
    row[2] = [(32, 50), (38, 50), (38, 80), (32, 80)]          # a back one unit off its row's takes the row's depth
    want = [_ring_set(r) for r in [sq, ell, tri] + row + deep]
    for w in want:
        assert w in got, w
    tb = [r for r in pf.decode(f, 4) if any(abs(x - round(x)) > 1e-6 for x, _y in r)]
    assert len(tb) == 1                                        # the turned box
    a = math.radians(10 * 90 / 64)
    assert abs(tb[0][1][0] - (5 + 12 * math.cos(a))) < 1e-6
    assert n == len(want) + 1


def test_names_and_heights_follow_their_records():
    recs = [(0, 0, 0, [(0, 0), (9, 0), (9, 9), (0, 9)], 88, "Tall One"), (0, 0, 1, [(20, 0), (29, 0), (29, 9), (20, 9)], 0, "")]
    s, hs, ns, n = pf._encode(recs, strips=False)
    assert hs == [88, 0] and ns == {"0": "Tall One"}


def test_reach_is_the_districts_plus_a_km():
    d = [{"unit": 0, "bounds": [39.95, -75.17, 39.96, -75.16]}]
    s, w, n, e = pf.reach(d, (39.9, -75.25, 40.0, -75.08))
    assert abs((39.95 - s) * 110.574 - 1) < 1e-6 and abs((n - 39.96) * 110.574 - 1) < 1e-6
    assert w < -75.17 and e > -75.16
    assert pf.reach([], (1, 2, 3, 4)) == (1.0, 2.0, 3.0, 4.0)


def test_fetch_buildings_is_cached_polite_and_gives_up(tmp_path, monkeypatch):
    sleeps, asked = [], []
    monkeypatch.setattr(pm, "_sleep", sleeps.append)
    box = (39.95, -75.17, 39.98, -75.11)                      # 2 x 2 tiles

    def post(q, timeout):
        asked.append(q)
        if len(asked) == 2:
            raise RuntimeError("Overpass HTTP 500")
        return {"elements": [{"type": "way", "id": len(asked), "tags": {"building": "yes"}, "geometry": []}]}
    monkeypatch.setattr(pm, "_post_overpass", post)
    r = pm.fetch_buildings(box, cache_dir=tmp_path)
    assert len(asked) == 4 and len(r["missing"]) == 1 and len(r["elements"]) == 3
    assert pm.BLD_BACKOFF[0] in sleeps and pm.BLD_PAUSE in sleeps
    asked.clear()
    r = pm.fetch_buildings(box, cache_dir=tmp_path)            # the cached tiles are never asked for again
    assert len(asked) == 1 and not r["missing"]
    monkeypatch.setattr(pm, "_post_overpass", lambda q, t: (_ for _ in ()).throw(RuntimeError("down")))
    for f in tmp_path.glob("bld-*.json"):
        f.unlink()
    r = pm.fetch_buildings(box, cache_dir=tmp_path)
    assert len(r["missing"]) == 4                              # after the last wait it stops asking


def _way(lat0, lon0, dlat, dlon, **tags):
    pts = [(lat0, lon0), (lat0, lon0 + dlon), (lat0 + dlat, lon0 + dlon), (lat0 + dlat, lon0), (lat0, lon0)]
    return {"type": "way", "tags": {"building": "yes", **tags}, "geometry": [{"lat": a, "lon": o} for a, o in pts]}


def _grid_map():
    bbox = (39.95, -75.17, 39.96, -75.15)
    W, H = pm.project(bbox[0], bbox[3], bbox)
    mp = Mapping(0.0, W / 2, H / 2, [0, W / 2, W], [110, 350, 590], [0, H / 2, H], [110, 280, 450])
    return bbox, {"bbox": list(bbox), "scale": 1.0, "grid": mp.tables(), "tiles": [[110, 110, 350, 280], [350, 110, 590, 280]],
                  "landmarks": [{"n": "L", "box": [350, 110, 590, 280]}]}


def test_footprints_land_in_their_block_and_skip_landmarks():
    bbox, m = _grid_map()
    raw = {"elements": [_way(39.957, -75.168, .0006, .0012, name="Big Hall", height="80"),   # north-west block
                        _way(39.957, -75.158, .0006, .0012),                               # north-east: a landmark's block
                        _way(39.951, -75.168, .0003, .0003)]}                              # south-west: not a block
    f = pf.fill_data(raw, m)
    assert pf.counts(f) == [1, 0, 0, 0]
    (r,) = pf.decode(f, 1)
    assert all(110 + 12 <= x <= 350 - 12 and 110 + 12 <= y <= 280 - 12 for x, y in r)
    assert f["n"][0] == ["0", "Big Hall"] and f["h"][0] == "4"


def test_a_turned_domain_carries_its_buildings_turned():
    """engine v2: m["doms"] — the footprint goes through its domain's local tables and is turned by a onto the page."""
    bbox, m = _grid_map()
    g = m["grid"]
    a, o = 30.0, (1000.0, 500.0)
    m2 = {"bbox": m["bbox"], "scale": 1.0, "landmarks": [], "tiles": [],
          "doms": [{"id": 0, "a": a, "o": list(o), "mapping": g, "cwch": [240, 170], "xg": [110, 3], "yg": [110, 3], "clip": None, "poly": None}]}
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    lx, ly = 230, 195                                         # the north-west cell's middle, local
    blocks = [{"x": lx * c - ly * s + o[0], "y": lx * s + ly * c + o[1], "lots": []}]
    raw = {"elements": [_way(39.957, -75.168, .0006, .0012, height="80")]}
    f = pf.fill_data(raw, m2, blocks)
    assert pf.counts(f) == [1, 0, 0, 0] and f["doms"] == [[30.0, 1000.0, 500.0]]
    (r,) = pf.decode(f, 1)
    for X, Y in r:                                            # back to local: inside the cell, 12 px in
        x, y = X - o[0], Y - o[1]
        u, v = x * c + y * s, -x * s + y * c
        assert 110 + 12 - 1e-6 <= u <= 350 - 12 + 1e-6 and 110 + 12 - 1e-6 <= v <= 280 - 12 + 1e-6


def test_set_up_fills_in_and_opens_on_skyline(monkeypatch):
    bbox, m = _grid_map()
    monkeypatch.setattr(pm, "fetch_buildings", lambda box, **kw: {"elements": [_way(39.957, -75.168, .0006, .0012, height="80")], "missing": []})
    z = pf.fill_for(m, [], [{"unit": 0, "bounds": list(bbox)}], bbox)
    f = pal.unpack(z)
    assert f["lvl"] == 1 and pf.counts(f) == [1, 0, 0, 0] and len(f["reach"]) == 4
    monkeypatch.setattr(pm, "fetch_buildings", lambda box, **kw: {"elements": [], "missing": []})
    assert pf.fill_for(m, [], [], bbox) is None
    s = pal.summary({"fill_z": z})
    assert s["fill"]["opens_on"] == 1 and "fill_z" not in s
