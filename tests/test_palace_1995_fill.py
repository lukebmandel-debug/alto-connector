"""1.9.95 fill-in over the whole city: the building tiles of the entire box (not only the districts + 1 km), the size
budget past the reach, no building in a river's green bank or on its trail, footprints in the free domains, and the
Auto setting that shows the row houses beyond the downtown. Offline: Overpass is a stub, nothing touches the network."""
import collections
import math

from alto import palace_map as pm
from alto.build import palace as pal
from alto.build import palace_fillin as pf
from alto.build.palace_banks import BANK_GAP
from alto.build.palace_grid import Mapping, mapping_from

_REAL_FETCH = pm.fetch_buildings                 # conftest stubs it for every module but test_palace_fillin: the tests of the fetching put it back

CITY = (39.895, -75.245, 40.005, -75.085)
REACH = (39.93445628267043, -75.21821908858978, 39.97774371732957, -75.12788091141023)      # Luke's districts + 1 km


def _way(lat0, lon0, dlat, dlon, **tags):
    pts = [(lat0, lon0), (lat0, lon0 + dlon), (lat0 + dlat, lon0 + dlon), (lat0 + dlat, lon0), (lat0, lon0)]
    return {"type": "way", "tags": {"building": "yes", **tags}, "geometry": [{"lat": a, "lon": o} for a, o in pts]}


def _map(**extra):
    bbox = (39.95, -75.17, 39.96, -75.15)
    W, H = pm.project(bbox[0], bbox[3], bbox)
    mp = Mapping(0.0, W / 2, H / 2, [0, W / 2, W], [110, 350, 590], [0, H / 2, H], [110, 280, 450])
    return bbox, {"bbox": list(bbox), "scale": 1.0, "grid": mp.tables(), "tiles": [[110, 110, 350, 280], [350, 110, 590, 280]],
                  "landmarks": [], **extra}


# ── the lattice: every tile of the city, on the reach's own tiles ───────────
def test_lattice_covers_the_whole_city_on_the_reach_tiles():
    cells = pf.lattice(REACH, CITY)
    assert len(cells) == 64
    assert min(c[0] for c in cells) <= CITY[0] and max(c[2] for c in cells) >= CITY[2]
    assert min(c[1] for c in cells) <= CITY[1] and max(c[3] for c in cells) >= CITY[3]
    inner = set(pm.tile_boxes(REACH, *pm.BLD_TILE))
    assert inner <= set(cells)                                   # the tiles cached for the reach are still the ones asked for
    for c in cells:                                              # a cell is one building tile: fetch_buildings names its cache file after it
        assert pm.tile_boxes(c, *pm.BLD_TILE) == [c]


def test_lattice_without_districts_is_the_citys_own_tiles():
    assert pf.lattice(CITY, CITY) == pm.tile_boxes(CITY, *pm.BLD_TILE)


def test_footprints_are_fetched_for_every_cell_cached_ones_are_free(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "fetch_buildings", _REAL_FETCH)
    sleeps, asked = [], []
    monkeypatch.setattr(pm, "_sleep", sleeps.append)

    def post(q, timeout):
        asked.append(q)
        return {"elements": [{"type": "way", "id": len(asked), "tags": {"building": "yes"}, "geometry": []}]}
    monkeypatch.setattr(pm, "_post_overpass", post)
    r = pf.fetch_footprints(REACH, CITY, cache_dir=tmp_path)
    assert len(asked) == 64 and not r["missing"] and len(r["elements"]) == 64
    asked.clear()
    r = pf.fetch_footprints(REACH, CITY, cache_dir=tmp_path)
    assert not asked and len(r["elements"]) == 64                # every cell is cached now
    for f in list(tmp_path.glob("bld-*.json"))[:5]:
        f.unlink()
    r = pf.fetch_footprints(REACH, CITY, cache_dir=tmp_path, offline=True)
    assert not asked and len(r["missing"]) == 5                  # offline: the missing cells are reported, never asked for


def test_two_failed_cells_in_a_row_leave_overpass_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "fetch_buildings", _REAL_FETCH)
    monkeypatch.setattr(pm, "_sleep", lambda s: None)
    asked = []

    def post(q, timeout):
        asked.append(q)
        raise RuntimeError("Overpass HTTP 500")
    monkeypatch.setattr(pm, "_post_overpass", post)
    r = pf.fetch_footprints(REACH, CITY, cache_dir=tmp_path)
    assert len(r["missing"]) == 64 and len(asked) < 10


def _sized_fill(monkeypatch, per_deg2):
    """fill_data stubbed: the packed size is the area of the reach it was asked for (per_deg2 chars a square degree)."""
    seen = []
    monkeypatch.setattr(pm, "_sleep", lambda s: None)

    def fake(raw, m_, blocks=None, core=None, far_tiers=None, **kw):
        seen.append(core)
        c = core or (39.895, -75.245, 40.005, -75.085)
        return {"v": 2, "doms": [], "q": [1, 2, 2, 3], "L": ["", "", "", ""], "h": [], "n": [], "c": [1, 0, 0, 0], "ch": [1, 1], "lvl": 0,
                "area": (c[2] - c[0]) * (c[3] - c[1])}
    monkeypatch.setattr(pf, "fill_data", fake)
    monkeypatch.setattr(pal, "pack", lambda f: "z" * int(f["area"] * per_deg2))
    return seen


def test_the_reach_grows_while_the_packed_fill_fits_the_budget(monkeypatch):
    big = (39.895, -75.245, 40.005, -75.085)
    m = {"bbox": list(big), "scale": 1.0}
    asked = []
    monkeypatch.setattr(pm, "fetch_buildings", lambda box, **kw: asked.append(tuple(box)) or {"elements": [], "missing": []})
    d = [{"bounds": [39.945, -75.17, 39.955, -75.16]}]
    seen = _sized_fill(monkeypatch, 1_000_000)
    r15 = (pf.reach(d, big, 1.5)[2] - pf.reach(d, big, 1.5)[0]) * (pf.reach(d, big, 1.5)[3] - pf.reach(d, big, 1.5)[1])
    r20 = (pf.reach(d, big, 2.0)[2] - pf.reach(d, big, 2.0)[0]) * (pf.reach(d, big, 2.0)[3] - pf.reach(d, big, 2.0)[1])
    monkeypatch.setattr(pf, "BUDGET_CHARS", int((r15 + r20) / 2 * 1_000_000))         # 1.5 km fits, 2 km does not
    z = pf.fill_for(m, [], d, big)
    assert seen[-1] == pf.reach(d, big, 2.0) and len(seen) == 3                     # 1, 1.5, 2: stops at the first that does not fit
    assert len(z) == int(r15 * 1_000_000)
    assert max(b[2] for b in asked) <= pf.reach(d, big, 2.0)[2] + .02                # only the tiles those reaches need were fetched
    assert len(set(asked)) < 20                                                     # (a stub has no cache: the repeats are the same cells)


def test_a_budget_that_holds_the_city_gets_the_whole_city(monkeypatch):
    big = (39.895, -75.245, 40.005, -75.085)
    m = {"bbox": list(big), "scale": 1.0}
    monkeypatch.setattr(pm, "fetch_buildings", lambda box, **kw: {"elements": [], "missing": []})
    d = [{"bounds": [39.945, -75.17, 39.955, -75.16]}]
    seen = _sized_fill(monkeypatch, 1000)
    z = pf.fill_for(m, [], d, big)
    assert seen[-1] is None and len(z) >= 1
    assert len(seen) == 1 + len([k for k in pf.REACH_LADDER if k > pf.REACH_KM]) + 1


def test_the_one_km_reach_is_kept_even_over_budget(monkeypatch):
    big = (39.895, -75.245, 40.005, -75.085)
    monkeypatch.setattr(pm, "fetch_buildings", lambda box, **kw: {"elements": [], "missing": []})
    d = [{"bounds": [39.945, -75.17, 39.955, -75.16]}]
    seen = _sized_fill(monkeypatch, 10 ** 9)
    monkeypatch.setattr(pf, "BUDGET_CHARS", 10)
    z = pf.fill_for({"bbox": list(big), "scale": 1.0}, [], d, big)
    assert z and len(seen) == 2 and seen[0] == pf.reach(d, big)


def test_past_the_core_only_the_levels_up_to_far_max_are_kept():
    bbox, m = _map()
    raw = {"elements": [_way(39.957, -75.168, .0006, .0012, height="80"),                    # tier 1
                        _way(39.9575, -75.1665, .0002, .0002)]}                                 # tier 4 (a 440 m2... row house)
    inside = (39.9, -75.2, 40.0, -75.1)
    outside = (39.0, -75.2, 39.1, -75.1)
    all_ = pf.counts(pf.fill_data(raw, m, core=inside, far_max=2))
    assert all_[0] == 1 and sum(all_) >= 1
    far = pf.fill_data(raw, m, core=outside, far_max=2)
    assert pf.counts(far)[0] == 1 and pf.counts(far)[2:] == [0, 0]


# ── no building in a river's green bank or on its trail ─────────────────────
def test_nothing_stands_in_the_green_bank_of_a_river():
    bbox, m = _map()
    # a river running down the page through the north-west block (x 110-350): centre x = 230, half width 20 -> its bank strip starts at x = 230 - 20 - BANK_GAP
    m["river"] = [{"p": [230, 0, 230, 600], "w": 40, "n": "R"}]
    wet_x = 230 - 20 - BANK_GAP                                                     # the west edge of the bank strip
    in_bank = _way(39.957, -75.1665, .0004, .0002, name="Wet Hall", height="80")    # page x 194-199: inside the strip
    on_land = _way(39.957, -75.168, .0004, .0002, name="Dry Hall", height="80")
    why = collections.Counter()
    f = pf.fill_data({"elements": [in_bank, on_land]}, m, why=why)
    rings = pf.decode(f, 1)
    assert rings and all(max(x for x, _y in r) <= wet_x + 1e-6 for r in rings)
    f0 = pf.fill_data({"elements": [in_bank, on_land]}, dict(m, river=[]))
    assert why["river_bank_t1"] == 1 and pf.counts(f0)[0] == pf.counts(f)[0] + 1      # the river is what took one away


def test_a_trail_is_kept_clear():
    bbox, m = _map()
    x = mapping_from(m["grid"])(*pm.project(39.957, -75.168 + .0001, bbox))[0]            # page px (the grid is the page here)
    m["rtrails"] = [{"n": "T", "p": [x, 0, x, 600]}]
    raw = {"elements": [_way(39.957, -75.168, .0004, .0002, height="80")]}
    assert pf.counts(pf.fill_data(raw, m))[0] == 0
    m["rtrails"] = []
    assert pf.counts(pf.fill_data(raw, m))[0] == 1


# ── free domains ────────────────────────────────────────────────────────────
def _free_map():
    bbox, m = _map()
    ring = [[0, 0], [700, 0], [700, 500], [0, 500]]
    return bbox, {"bbox": m["bbox"], "scale": 1.0, "landmarks": [], "tiles": [], "parks": [], "streets": [{"k": 2, "p": [120, 0, 120, 500]}],
                  "doms": [{"id": 6, "kind": "free", "a": 10.0, "o": [50.0, 20.0], "mapping": m["grid"], "cwch": [240, 170],
                            "clip": ring, "poly": [[0, 0], [5000, 0], [5000, 5000], [0, 5000]]}]}


def test_a_free_domain_keeps_buildings_that_clear_its_streets():
    bbox, m = _free_map()
    raw = {"elements": [_way(39.957, -75.168, .0006, .0012, height="80", name="Free Hall"),
                        _way(39.9575, -75.1565, .0003, .0003, height="80")]}
    why = collections.Counter()
    f = pf.fill_data(raw, m, why=why)
    assert f["doms"] == [[10.0, 50.0, 20.0]]
    rings = pf.decode(f, 1)
    assert 1 <= len(rings) and sum(pf.counts(f)) == len(rings)
    st = pf._Near([[120, 0, 120, 500]])
    for r in rings:                                          # on the page, none within the inset of the street
        for X, Y in pf._samples(r, 4.0):
            assert not st.within(X, Y, pf.INSET - 1.5)


def test_free_footprints_are_dropped_beside_a_street():
    bbox, m = _free_map()
    c, s = math.cos(math.radians(10)), math.sin(math.radians(10))
    raw = {"elements": [_way(39.957, -75.168, .0006, .0012, height="80")]}
    f = pf.fill_data(raw, dict(m, streets=[]))
    free_n = sum(pf.counts(f))
    assert free_n >= 1
    ring = pf.decode(f, 1)[0]
    mx, my = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    f2 = pf.fill_data(raw, dict(m, streets=[{"k": 2, "p": [mx - 400 * s, my + 400 * c, mx + 400 * s, my - 400 * c]}]))      # a street through its middle
    assert sum(pf.counts(f2)) == 0


# ── Auto ────────────────────────────────────────────────────────────────────
def test_auto_shows_the_row_houses_beyond_the_downtown():
    js = pf.FILL_FUNCS
    assert "FILL_DT=90, FILL_OUT=100, fillAuto=true" in js        # 40 showed only tiers 1-2 beyond the downtown: whole blocks looked empty
    assert "% downtown, '+FILL_OUT+'% beyond" in js               # the label follows the constants
    # level 4 is drawn as one shape per block front, so a share of them (85% -> 40% of the fronts) leaves blocks blank: beyond the downtown it is all of them
    assert pf.FILL_FUNCS.count("FILL_OUT") >= 4


def test_cells_past_the_reach_stop_after_the_time_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "fetch_buildings", _REAL_FETCH)
    clock = [0.0]
    import time as _t
    monkeypatch.setattr(_t, "monotonic", lambda: clock[0])
    monkeypatch.setattr(pm, "_sleep", lambda s: None)
    asked = []

    def post(q, timeout):
        asked.append(q)
        clock[0] += 60.0                                           # each tile takes a minute
        return {"elements": []}
    monkeypatch.setattr(pm, "_post_overpass", post)
    r = pf.fetch_footprints(REACH, CITY, cache_dir=tmp_path, far_s=300)
    assert len(asked) < 64 and len(asked) >= 12      # the reach is always fetched, the far cells run out of time
    assert len(r["missing"]) == 64 - len(asked)
    asked.clear()
    r2 = pf.fetch_footprints(REACH, CITY, cache_dir=tmp_path, far_s=300)    # the next set_up goes on from the cache
    assert len(asked) > 0 and len(r2["missing"]) < len(r["missing"])
