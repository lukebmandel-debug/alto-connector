"""City engine v2: the quality report R10 (design section 7.1)."""
import copy
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import alto.build.palace  # noqa: F401
from alto.build import city_report as cr
from alto.build.city_types import Seam
from alto.build.palace_grid import grid, Mapping, mapping_from
from city_synth_e5 import grid_city

CHECKS = {"domains", "phantom", "displacement", "order", "side", "seam_fidelity", "tjoin", "ends", "cross_seam",
          "avenues", "transit", "cut", "size", "overlap"}


def _built(**kw):
    m = grid_city(**kw)
    g = grid(copy.deepcopy(m), majors=["Row A Street"], diagonals=["Diagonal Avenue"],
             landmarks=[{"name": "Town Hall"}])
    return m, g


def test_report_runs_every_check_on_todays_grid():
    m, g = _built()
    rep = cr.report(g, m)
    assert set(rep["checks"]) == CHECKS
    assert all(c["status"] in ("ok", "warn", "fail") for c in rep["checks"].values())
    assert not any("could not run" in c["msg"] for c in rep["checks"].values()), cr.summary(rep)
    assert rep["fail"] == [k + ": " + v["msg"] for k, v in rep["checks"].items() if v["status"] == "fail"]


def test_a_clean_grid_city_is_clean_where_it_should_be():
    m, g = _built()
    ch = cr.report(g, m)["checks"]
    assert ch["domains"]["status"] == "ok" and len(ch["domains"]["data"]["domains"]) == 1
    assert ch["phantom"]["status"] == "ok" and ch["phantom"]["data"]["median"] > .9
    assert ch["displacement"]["status"] == "ok"
    assert ch["side"]["status"] == "ok"
    assert ch["overlap"]["status"] == "ok"


def test_unmap_inverts_the_mapping():
    mp = Mapping(0.15, 500, 400, [10, 200, 330, 800], [110, 350, 590, 830], [5, 90, 300], [110, 280, 450])
    t = mp.tables()
    for p in ((50, 40), (300, 200), (900, 500), (-40, 700)):
        q = cr.unmap(t, *mp(*p))
        assert math.dist(p, q) < 0.2


def test_side_of_a_line():
    L = [(0, 0), (100, 0), (200, 10)]
    assert cr._side((50, 20), L) == -cr._side((50, -20), L) != 0
    assert cr._side((-500, 3), L) == 0          # beyond the end: not defined


def test_a_bent_or_off_angle_or_dangling_avenue_fails():
    m, g = _built()
    g2 = copy.deepcopy(g)
    x0, y0 = g2["grid"]["xg"][2] + 60, g2["grid"]["yg"][2] + 50          # mid-block, inside the grid
    g2["streets"].append({"n": "Bad Avenue", "k": 0, "d": 1, "p": [x0, y0, x0 + 100, y0 + 70, x0 + 300, y0 + 100,
                                                                   x0 + 400, y0 + 300, x0 + 500, y0 + 350]})
    a = cr.report(g2, m)["checks"]["avenues"]
    assert a["status"] == "fail" and "Bad Avenue" in a["msg"]
    row = a["data"]["avenues"]["Bad Avenue"]
    assert row["non_octi"] >= 1 and row["dangling"] == 2 and max(row["bends"]) > 2


def test_a_line_ending_mid_block_fails():
    m, g = _built()
    g2 = copy.deepcopy(g)
    x = g2["grid"]["xg"][3] + 50
    y = g2["grid"]["yg"][3] + 40
    g2["streets"].append({"n": "Stub Street", "k": 1, "p": [x, y, x + 80, y]})
    e = cr.report(g2, m)["checks"]["ends"]
    assert e["status"] == "fail" and any(r[0] == "Stub Street" for r in e["data"]["examples"])


def test_seam_checks_measure_the_angle_and_crossings():
    m, g = _built()
    t = g["grid"]
    mp = mapping_from(t)
    real = [(300, 400), (1500, 1000)]                    # a real seam at about 27 degrees
    a, b = mp(*real[0]), mp(*real[1])
    flat = Seam(a=0, b=None, kind="box", real=real, segs=[(a[0], a[1], b[0], a[1])])   # drawn flat
    good = Seam(a=0, b=None, kind="fold", real=real, segs=[(a[0], a[1], b[0], b[1])])
    rf = cr.report(g, m, seams=[flat])["checks"]
    rg = cr.report(g, m, seams=[good])["checks"]
    assert rf["seam_fidelity"]["status"] == "fail" and rf["seam_fidelity"]["data"]["seams"][0]["err"] > 12
    assert rg["seam_fidelity"]["status"] == "ok"
    assert rg["cross_seam"]["status"] == "fail"           # today's lattice lines run straight through it


def test_overlapping_domains_fail():
    m, g = _built()
    doms = [{"id": 0, "kind": "grid", "theta": 0.0, "poly": [(0, 0), (2600, 0), (2600, 2000), (0, 2000)],
             "mapping": g["grid"], "clip": [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]},
            {"id": 1, "kind": "grid", "theta": 0.5, "poly": [(1200, 0), (2600, 0), (2600, 2000), (1200, 2000)],
             "mapping": g["grid"], "clip": [(800, 0), (2000, 0), (2000, 1000), (800, 1000)]}]
    ov = cr.report(g, m, doms=doms)["checks"]["overlap"]
    assert ov["status"] == "fail" and ov["data"]["bad"][0][:2] == (0, 1)


def test_inversions():
    assert cr._inversions([1, 2, 3]) == 0 and cr._inversions([3, 1, 2]) == 2
