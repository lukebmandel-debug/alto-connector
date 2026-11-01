"""The Chicago preset (city_presets.CHICAGO) on its own fixture (tests/fixtures/cities/chicago_preset.json.gz: the preset's
box, its streets, the Chicago River's three branches, Lake Michigan from city_coast, the
preset's parks): one grid split by the river and joined across it, the river a Y of three narrow channels meeting at one
point, the lake one sea body at the east edge, the parks lattice holes, the avenues crossing their streets in order."""
import copy
import gzip
import itertools
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import city_gate, city_presets as cp, city_report as cr, city_types, palace_grid  # noqa: E402

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
    ends = [((b["p"][0], b["p"][1]), (b["p"][-2], b["p"][-1])) for b in bands.values()]
    # Wolf Point: one end of each channel at one point, no cross (the Chicago River's mouth is on the glass too, since it reaches the shore)
    assert min(max(math.dist(a, b), math.dist(a, c), math.dist(b, c)) for a, b, c in itertools.product(*ends)) < 1.0


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
