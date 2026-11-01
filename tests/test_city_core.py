"""The shared city code (rules doc section 11): the LayoutSpec record (city_spec; NYC the first spec, its output unchanged),
auto_params' water / layout / alias fields (city_setup), the computed fill budget (palace_fillin.budget) and the scored
gate (city_gate)."""
import copy
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import city_coast, city_engine, city_gate, city_manhattan as cm, city_setup as cs, city_spec, palace_fillin, palace_grid  # noqa: E402

from test_city_manhattan import city  # noqa: E402,F401 — the synthetic Manhattan (a fixture)

FIX = ROOT / "tests" / "fixtures" / "cities"


def _fixture(name):
    return json.loads(gzip.decompress((FIX / ("%s.json.gz" % name)).read_bytes()).decode())


def _digest(g):
    return hashlib.sha256(json.dumps(g, sort_keys=True, default=lambda o: getattr(o, "__dict__", type(o).__name__)).encode()).hexdigest()[:16]


# ── LayoutSpec ─────────────────────────────────────────────────────────────
def test_nyc_is_the_first_spec_and_round_trips_as_data():
    sp = city_spec.get("manhattan")
    assert sp is cm.NYC and sp.builder == "axes" and sp.name == cm.LAYOUT
    assert [a[0] for a in sp.root_axes] == [a[0] for a in cm.AVENUES] and sp.hinge_axis == "6th Avenue"
    assert sp.must_parks == cm.PARKS and sp.fill_budget == palace_fillin.BUDGET_MANHATTAN
    assert [c.region[0] for c in sp.children] == ["west_of", "south_of"]
    d = json.loads(json.dumps(sp.to_dict()))
    assert city_spec.from_dict(d) == sp
    assert city_spec.resolve(None) is None and city_spec.resolve("no-such-layout") is None
    with pytest.raises(ValueError):
        city_spec.LayoutSpec(name="x", builder="axes")             # a fixed-axes layout needs its axes


def test_the_spec_as_data_draws_manhattan_exactly_as_its_name_does(city):
    m, g = city
    by_name = palace_grid.grid(copy.deepcopy(m), majors=["Broadway"], diagonals=["Broadway"])
    by_spec = palace_grid.grid(dict(copy.deepcopy(m), layout=cm.NYC.to_dict()), majors=["Broadway"], diagonals=["Broadway"])
    via_engine = city_engine.build(copy.deepcopy(m), None, ["Broadway"], ["Broadway"], spec=cm.NYC)
    assert _digest(g) == _digest(by_name) == _digest(via_engine)
    assert by_spec.pop("layout") == cm.NYC.to_dict()                                   # the map carries the spec it was drawn by
    assert _digest(dict(g, layout=None)) == _digest(dict(by_spec, layout=None))


def test_manhattans_layout_is_unchanged_on_the_real_fixture():
    # pinned on v1.9.189 before the LayoutSpec extraction: the NYC preset's layout must draw the same bytes
    m = _fixture("manhattan")
    m["layout"] = "manhattan"
    g = palace_grid.grid(m, majors=m.get("majors", []), diagonals=["Broadway"], parks=["Washington Square Park"])
    assert g["engine"]["path"] == "manhattan"
    assert _digest(g) == "334b3e50a5e1edc1"


def test_an_engine_spec_adds_its_must_parks():
    sp = city_spec.LayoutSpec(name="x", must_parks=("Pocket Park",))
    seen = {}
    real = city_engine.build
    m = _fixture("chicago")
    try:
        city_engine.build = lambda *a, **k: seen.update(parks=a[6] if len(a) > 6 else k.get("parks")) or {"engine": {}}
        from alto.build import city_types
        old, city_types.ENGINE_V2 = city_types.ENGINE_V2, True
        palace_grid.grid(dict(m, layout=sp.to_dict()), parks=["Big Park"])
    finally:
        city_engine.build = real
        city_types.ENGINE_V2 = old
    assert tuple(seen["parks"]) == ("Big Park", "Pocket Park")


# ── auto_params: water, river names, layout, aliases ───────────────────────
def _river_map(gap):
    """A 4 x 3 km box: the city's streets west, a river `gap` m wide, a named district's land east of it."""
    W, H = 4000, 3000
    x0 = 2400
    streets = [{"n": "Street %d" % i, "k": 3, "p": [100, 100 + i * 200, x0 - 100, 100 + i * 200]} for i in range(12)]
    water = [[x0, 0, x0 + gap, 0, x0 + gap, H, x0, H]]
    return {"W": W, "H": H, "scale": 1.0, "bbox": [40.0, -75.0, 40.0 + H / 110574, -75.0 + W / (111320 * math.cos(math.radians(40.0135)))],
            "streets": streets, "water": water, "rivers": [{"n": "Big River", "p": [x0 + gap / 2, 0, x0 + gap / 2, H]}]}


def _area_at(m, x, y, name="Farside"):
    la, lo = cs._unproject(x, y, m["bbox"])
    return {"name": name, "lat": la, "lon": lo, "rank": 1}


def test_a_far_bank_is_kept_only_across_wide_water_with_a_district_on_it():
    wide = _river_map(600)
    assert cs.water_of(wide, [_area_at(wide, 3500, 1500)])["far_bank"] is True
    assert cs.water_of(wide, [])["far_bank"] is False                                  # nobody lives there that matters
    narrow = _river_map(100)                                                           # the Chicago River: a channel, not a far bank
    assert cs.water_of(narrow, [_area_at(narrow, 3200, 1500)])["far_bank"] is False


def test_river_names_sample_the_named_water_and_skip_fountains():
    m = _river_map(600)
    els = [{"type": "way", "tags": {"name": "A Fountain", "natural": "water", "water": "fountain"}, "center": {"lat": m["bbox"][0] + .01, "lon": m["bbox"][1] + .01}},
           {"type": "way", "tags": {"name": "The Harbor", "natural": "water", "water": "harbour"}, "center": {"lat": m["bbox"][0] + .01, "lon": m["bbox"][1] + .01}}]
    rn = cs.river_names_of(m, els)
    assert [r[0] for r in rn].count("Big River") == 3 and "The Harbor" in [r[0] for r in rn] and "A Fountain" not in [r[0] for r in rn]
    x, y = __import__("alto.palace_map", fromlist=["project"]).project(rn[0][1], rn[0][2], m["bbox"], 1.0)
    assert abs(x - 2700) < 5 and abs(y) < 15


def test_aliases_come_from_the_landmarks_own_tags():
    els = [{"type": "way", "tags": {"name": "Willis Tower", "alt_name": "Sears Tower"}},
           {"type": "way", "tags": {"name": "875 N Michigan", "official_name": "John Hancock Center;Hancock"}},
           {"type": "way", "tags": {"name": "Elsewhere", "alt_name": "Not asked"}}]
    assert cs.aliases_of(els, ["Willis Tower", "875 N Michigan"]) == {"Willis Tower": ["Sears Tower"],
                                                                      "875 N Michigan": ["John Hancock Center", "Hancock"]}


def test_auto_params_give_a_layout_spec_not_a_name():
    m = _fixture("chicago")
    ap = cs.auto_params({"elements": []}, tuple(m["bbox"]), "Chicago", m=m)
    sp = city_spec.from_dict(ap["layout"])
    assert sp.builder == "engine" and sp.name == "chicago" and sp.fill_budget is None
    assert ap["far_bank"] is False and {r[0] for r in ap["river_names"]} >= {"Chicago River"}
    assert all(abs(c.angle) < 3 for c in sp.children)                                  # one angle, split by the river
    assert ap["aliases"] == {}


# ── the fill budget ────────────────────────────────────────────────────────
def test_the_fill_budget_is_the_specs_or_computed_from_the_page(monkeypatch):
    assert palace_fillin.budget({"layout": "manhattan"}) == 150_000
    assert palace_fillin.budget({"W": 100, "H": 100, "streets": []}) == palace_fillin.BUDGET_MANHATTAN   # an empty map leaves the most
    m = _fixture("philadelphia")
    data = len(gzip.compress(json.dumps({"map": m, "blocks": []}, separators=(",", ":")).encode(), 6, mtime=0))
    monkeypatch.setattr(palace_fillin, "PAGE_FIXED", palace_fillin.PAGE_CAP - palace_fillin.PAGE_HEADROOM - data - 75_000)
    assert abs(palace_fillin.budget(m) - 100_000) < 2                                   # 75 kB of page left: 100k packed chars
    monkeypatch.setattr(palace_fillin, "PAGE_FIXED", palace_fillin.PAGE_CAP)
    assert palace_fillin.budget(m) == palace_fillin.BUDGET_MIN


# ── the gate ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def chi():
    from alto.build import city_types
    old, city_types.ENGINE_V2 = city_types.ENGINE_V2, True
    try:
        m = _fixture("chicago")
        g = palace_grid.grid(copy.deepcopy(m), majors=m["majors"])
    finally:
        city_types.ENGINE_V2 = old
    return m, g


def _lm(n, x, y, w=240, h=260):
    return {"n": n, "x": x, "y": y, "box": [x - w / 2, y - h / 2, x + w / 2, y + h / 2], "r": []}


def test_the_gate_scores_every_row_it_can_run(chi):
    m, g = chi
    rep = city_gate.gate(g, m)
    assert 0 <= rep["score"] <= 100 and set(rep["skipped"]) == {"G19", "G20", "G21", "G22"}
    assert set(rep["ran"]) == {r for r, _n, _w in city_gate.ROWS} - set(rep["skipped"])
    assert sum(w for _r, _n, w in city_gate.ROWS) == 98
    assert rep["checks"]["G17"]["status"] == "fail"                                     # the fixture has no landmarks
    page = {"stored": 700 * 1024, "buildings": 100}
    rep2 = city_gate.gate(g, m, page=page, tiles={"base_gz": 100_000, "max": 30_000, "tiles": 4, "bytes": 90_000},
                          timing={"set_up_s": 12.0}, same={"same": True})
    assert not rep2["skipped"] and rep2["score"] > rep["score"]                         # four clean rows more
    assert city_gate.markdown(rep2, "Chicago").startswith("# Chicago: city gate")


def test_dry_land_finds_a_landmark_in_the_river_and_a_lost_channel(chi):
    m, g = chi
    g = copy.deepcopy(g)
    band = g["river"][0]
    x, y = band["p"][0] + (band["p"][2] - band["p"][0]) / 2, band["p"][1] + (band["p"][3] - band["p"][1]) / 2
    g["landmarks"] = [_lm("Wet Tower", x, y)]
    st, _msg, data = city_gate.g_dry_land(g, [], channels=[band["n"], "Imaginary Canal"])
    assert st == "fail" and data["wet"][0][:2] == ("landmark", "Wet Tower") and data["missing"] == ["Imaginary Canal"]


def test_overlapping_cards_and_too_few_landmarks_fail(chi):
    _m, g = chi
    g = dict(g, landmarks=[_lm("L%d" % i, 1000 + 400 * i, 1000) for i in range(9)])
    assert city_gate.g_landmarks(g)[0] == "ok"
    g["landmarks"].append(_lm("On top", 1000, 1050))
    st, _msg, data = city_gate.g_landmarks(g)
    assert st == "fail" and data["overlaps"][0][:2] == ("L0", "On top")
    assert city_gate.g_landmarks(dict(g, landmarks=g["landmarks"][:3]))[0] == "fail"


def test_labels_overlap_at_the_whole_city_zoom(chi):
    _m, g = chi
    a = [{"n": "Near North Side", "x": 3000, "y": 3000, "r": 1}, {"n": "River North", "x": 3100, "y": 3050, "r": 1},
         {"n": "Far Away", "x": 3000, "y": 9000, "r": 1}, {"n": "Tiny Place", "x": 3000, "y": 3000, "r": 3}]
    st, _msg, data = city_gate.g_labels(dict(g, landmarks=[]), a)
    assert st == "fail" and data["overlaps"] == [("Near North Side", "River North")]
    st, _msg, data = city_gate.g_labels(dict(g, landmarks=[_lm("Tower A", 3000, 9200), _lm("Tower B", 3050, 9200)]), a[2:3])
    assert st == "fail" and data["under_landmark"][0][0] == "Far Away" and data["landmark_pairs"] == [("Tower A", "Tower B")]


# ── city_coast on synthetic data ───────────────────────────────────────────
def _way(i, pts, **tags):
    return {"type": "way", "id": i, "tags": tags, "geometry": [{"lat": la, "lon": lo} for la, lo in pts]}


def test_a_shore_crossing_the_box_closes_on_the_side_without_streets():
    bbox = (41.0, -87.10, 41.02, -87.06)
    shore = [_way(1, [(40.99, -87.075), (41.01, -87.077)], _shore="lake"), _way(2, [(41.03, -87.072), (41.01, -87.077)], _shore="lake")]
    W, H = 3360, 2211
    streets = [{"n": "Inland Street", "p": [100, 100 + 100 * k, 1500, 100 + 100 * k]} for k in range(15)]
    rings = city_coast.sea_rings({"elements": shore}, bbox, W, H, 1.0, streets)
    assert len(rings) == 1
    xs = rings[0][0::2]
    assert min(xs) > 1800 and max(xs) == W                  # the lake: from the shore to the east edge, none of the city
    rings2 = city_coast.sea_rings({"elements": [_way(3, [(40.99, -87.075), (41.03, -87.075)], natural="coastline")]}, bbox, W, H)
    assert max(rings2[0][0::2]) == W                         # a coastline keeps its land on the left: the water east


def test_an_island_inside_the_box_is_land():
    bbox = (41.0, -87.10, 41.02, -87.06)
    isl = [_way(1, [(41.005, -87.09), (41.005, -87.08), (41.015, -87.08), (41.005, -87.09)], natural="coastline")]
    assert city_coast.sea_rings({"elements": isl}, bbox, 3360, 2211) == []


# ── the transit stub trim ──────────────────────────────────────────────────
def test_track_past_a_stop_that_was_not_drawn_is_cut_a_block_past_the_last_one():
    from alto.build.palace_transit import _trim_stubs
    out = {"stops": [{"n": "A", "x": 0, "y": 0}, {"n": "B", "x": 500, "y": 0}],
           "lines": [{"id": "l", "p": [[0, 0, 500, 0, 2500, 0]], "s": [0, 1], "b": [[0, 1]]}]}
    _trim_stubs(out, 200.0)
    assert out["lines"][0]["p"][0][-2:] == [700.0, 0.0]
    short = {"stops": out["stops"], "lines": [{"id": "l", "p": [[0, 0, 500, 0, 900, 0]], "s": [0, 1]}]}
    _trim_stubs(short, 200.0)
    assert short["lines"][0]["p"][0] == [0, 0, 500, 0, 900, 0]          # two blocks on: within the audit's three
