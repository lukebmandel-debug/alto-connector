"""The Chicago preset (city_presets.CHICAGO) on its own fixture (tests/fixtures/cities/chicago_preset.json.gz: the preset's
box, its streets, the Chicago River's three branches, Lake Michigan from city_coast, the
preset's parks): one grid split by the river and joined across it, the river a Y of three narrow channels meeting at one
point, the lake one sea body at the east edge, the parks lattice holes, the avenues crossing their streets in order.
Also city_coast and the transit stub trim on synthetic data."""
import copy
import gzip
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import city_coast, city_gate, city_presets as cp, city_report as cr, city_types, palace_grid  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cities" / "chicago_preset.json.gz"


@pytest.fixture(scope="module")
def chi():
    m = json.loads(gzip.decompress(FIX.read_bytes()).decode())
    m["layout"] = cp.CHICAGO["layout"]
    old, city_types.ENGINE_V2 = city_types.ENGINE_V2, True
    try:
        g = palace_grid.grid(copy.deepcopy(m), majors=cp.CHICAGO["majors"], diagonals=cp.CHICAGO["diagonals"],
                             parks=cp.CHICAGO["parks"])
    finally:
        city_types.ENGINE_V2 = old
    return m, g


def test_the_preset_is_found_by_name_and_carries_its_water():
    assert cp.find("Chicago, IL") == "chicago" and cp.get("chicago")["place"] == "Chicago"
    pre = cp.get("chicago")
    assert pre["layout"]["shore"] == "sea" and len(pre["channels"]) == 3
    assert 8 <= len(pre["landmarks"]) <= 24
    assert {c["level"] for c in cp.COURTS["chicago"]} == {"federal", "state", "city"}


def test_one_grid_joined_across_the_river(chi):
    _m, g = chi
    assert g["engine"]["path"] == "v2" and g["engine"]["domains"] == 1 and g["engine"]["across_merged"]
    assert g["engine"]["layout"] == "chicago"


def test_the_river_is_a_y_of_three_channels_meeting_at_one_point(chi):
    _m, g = chi
    bands = {b["n"]: b for b in g["river"]}
    assert set(bands) == set(cp.CHICAGO["channels"])
    assert all(b["w"] >= city_gate.CHANNEL_PX for b in bands.values())
    ends = [(b["p"][0], b["p"][1]) for b in bands.values()] + [(b["p"][-2], b["p"][-1]) for b in bands.values()]
    meet = [e for e in ends if 0 < e[0] < g["W"] and 0 < e[1] < g["H"]]
    assert len(meet) >= 3 and max(math.dist(meet[0], e) for e in meet[:3]) < 1.0     # Wolf Point: one point, no cross


def test_lake_michigan_is_one_sea_body_east_of_the_city(chi):
    _m, g = chi
    assert g.get("sea") and len(g["sea"]) >= 1
    big = max(g["sea"], key=len)
    mich = [s for s in g["streets"] if s.get("n") == "Michigan Avenue" and s.get("L")]
    xm = min(x for s in mich for x in s["p"][0::2])
    assert mich and sum(x > xm for x in big[0::2]) >= .95 * len(big[0::2])    # east of Michigan Avenue (it meets it at Oak St)
    st, _msg, data = city_gate.g_dry_land(g, g["blocks"], cp.CHICAGO["channels"])
    assert st == "ok", data


def test_avenues_cross_their_streets_in_order_and_lots_keep_their_bank(chi):
    m, g = chi
    M = cr._model(g, m, None, None)
    assert cr.c_order(g, m, M)[0] == "ok"
    assert cr.c_side(g, m, M, g["blocks"])[0] == "ok"
    assert {s["n"] for s in g["streets"] if s.get("d")} >= {"Milwaukee Avenue", "Ogden Avenue"}


def test_grant_park_is_a_hole_only_its_real_roads_cross(chi):
    m, g = chi
    st, _msg, data = city_gate.g_parks(g, (), cp.CHICAGO["layout"]["must_parks"], m)
    assert not data["through"] and not data["missing_must"], data
    assert ("Columbus Drive", "Grant Park") in {(a, b) for a, b, _r in data["real"]}       # a real road through the park stays


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
