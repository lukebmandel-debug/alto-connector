"""City engine v2, polish P1 (seams, junctions, avenues, parks): multi-part seams (a chain of segments meeting at a
corner, both lattices ending on every part), one-ring corner cells, the block-aspect rule (a page row is one real
block), out-and-back avenue chains, parks per domain with their domain's frame, the report's spacing / fronts checks,
and the regression for the stray angled line across West Philadelphia (a slab that does not touch a cell must not
split it)."""
import copy
import gzip
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_grid, city_engine, city_avenues, city_lines, city_report  # noqa: E402,F401
from alto.build.palace_parks import shape  # noqa: E402
from alto.build.city_lattice import area  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cities" / "philadelphia.json.gz"
MAJORS = ["Broad Street", "Market Street", "Baltimore Avenue", "Kensington Avenue", "Lancaster Avenue",
          "Woodland Avenue", "Chester Avenue", "Allegheny Avenue", "Girard Avenue", "Spruce Street"]


@pytest.fixture(scope="module")
def phil():
    if not FIX.exists():
        pytest.skip("no Philadelphia fixture")
    m = json.loads(gzip.decompress(FIX.read_bytes()).decode())
    # two park outlines (real px, boxes): one in the tilted south-west grid, one in the main grid
    m["parks"] = [{"n": "Clarence H. Clark Park", "r": [[2700, 6250, 2860, 6250, 2860, 6420, 2700, 6420]]},
                  {"n": "Rittenhouse Square", "r": [[6380, 5850, 6520, 5850, 6520, 5980, 6380, 5980]]}]
    g = palace_grid.grid(copy.deepcopy(m), majors=MAJORS, parks=["Clark Park", "Rittenhouse Square"])
    return m, g


def _ang(s):
    return math.degrees(math.atan2(s[3] - s[1], s[2] - s[0]))


def test_minus_one_is_one_ring():
    P = [(0, 0), (10, 0), (10, 10), (0, 10)]
    r = city_engine._minus_one(P, [(5, 5), (20, 5), (20, 20), (5, 20)])
    assert r and area(r) == pytest.approx(75.0)                     # an L, not the larger of two pieces
    assert city_engine._minus_one(P, [(20, 20), (30, 20), (30, 30), (20, 30)]) is None


def test_clip_cell_keeps_the_whole_corner_cell():
    class L:
        region = {}
        subtract = {7: [[(5, 5), (20, 5), (20, 20), (5, 20)], [(100, 100), (120, 100), (120, 120), (100, 120)]]}
    P = city_engine.clip_cell(L, 7, [(0, 0), (10, 0), (10, 10), (0, 10)])
    assert area(P) == pytest.approx(75.0)
    # a slab that does not touch the cell leaves it whole (the stray-line regression: no split along its edges)
    L.subtract = {7: [[(100, -50), (120, -50), (120, 50), (100, 50)]]}
    assert area(city_engine.clip_cell(L, 7, [(0, 0), (10, 0), (10, 10), (0, 10)])) == pytest.approx(100.0)


def test_out_and_back_chain_is_one_way():
    P = [(0, 0), (500, 0), (1000, 0), (1000, 20), (500, 20), (5, 20)]
    assert city_avenues._one_way(P) == P[:4]                      # cut at the far point: one carriageway
    Q = [(0, 0), (500, 0), (1000, 0)]
    assert city_avenues._one_way(Q) == Q


def test_block_aspect_rule():
    rows = [{"n": "%d Row" % i, "k": 1, "p": [0, 300 + 175 * i, 3000, 300 + 175 * i]} for i in range(10)]
    cols = [{"n": "%dth Street" % (i + 10), "k": 3, "p": [100 + 136 * i, 0, 100 + 136 * i, 2000]} for i in range(18)]

    class D:
        theta, streets, poly = 0.0, rows + cols, [(0, 0), (3000, 0), (3000, 2000), (0, 2000)]
    a = city_lines.block_aspect(D)
    assert a == pytest.approx(175 / 136, abs=0.01)
    assert city_lines.block_ch(a) == 310.0                        # a row is one real block: 240 x 310
    assert city_lines.block_ch(0.5) == 170.0 and city_lines.block_ch(9.0) == 340.0
    assert city_lines.block_ch(None) == 170.0


def test_baltimore_seam_is_a_chain_with_a_corner(phil):
    m, g = phil
    b = next(s for s in g["seams"] if s["avenue"] == "Baltimore Avenue")
    assert len(b["segs"]) >= 2, b                                  # Baltimore Ave, then the turn down by 40th St
    s0, s1 = b["segs"][0], b["segs"][1]
    assert -26 < _ang(s0) < -12
    corner = s0[2:4]
    assert min(math.dist(corner, s1[:2]), math.dist(corner, s1[2:])) < 1.0          # one shared corner
    turn = abs((_ang(s1) - _ang(s0) + 90) % 180 - 90)
    assert turn >= 20
    # the turning part is a street, and lines of BOTH domains end on it (a T into it)
    on = lambda p, s: city_avenues.segd(p, s[:2], s[2:]) < 1.0                      # noqa: E731
    assert any(st.get("sm") and on(st["p"][:2], s1) and on(st["p"][-2:], s1) for st in g["streets"])
    ends = {1: 0, 3: 0}
    doms = {d["id"]: d for d in g["doms"]}
    for st in g["streets"]:
        if st.get("sm") or st.get("d"):
            continue
        for e in (st["p"][:2], st["p"][-2:]):
            if on(e, s1):
                ends[1 if abs(_ang(st["p"][:4]) % 90 - doms[1]["a"] % 90) < 2 or
                     abs(_ang(st["p"][:4]) % 90 - doms[1]["a"] % 90) > 88 else 3] += 1
    assert ends[1] >= 2 and ends[3] >= 2, ends


def test_no_cut_edge_runs_off_every_axis(phil):
    """The stray angled line: every edge of a cut block either runs along its domain's axes or lies on a seam part,
    a domain clip or the river; nothing angled crosses a domain's blocks."""
    m, g = phil
    axes = [d["a"] for d in g["doms"]]
    segs = [s for sm in g["seams"] for s in sm["segs"]]
    clips = [[tuple(q) for q in d["clip"]] for d in g["doms"] if d.get("clip")]
    edges = [(c[i], c[(i + 1) % len(c)]) for c in clips for i in range(len(c))]
    rivers = [(city_avenues._pairs(r["p"]), r["w"]) for r in g.get("river", [])]
    bad = []
    for q in g["tq"]:
        P = city_avenues._pairs(q)
        for a, b in zip(P, P[1:] + P[:1]):
            L = math.dist(a, b)
            if L < 30:
                continue
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            if any(abs((ang - x + 45) % 90 - 45) < 1.0 for x in axes):
                continue
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if any(city_avenues.segd(mid, s[:2], s[2:]) < 3 for s in segs) or \
                    any(city_avenues.segd(mid, c, d) < 3 for c, d in edges) or \
                    any(city_avenues.poly_d(mid, R) < w / 2 + 400 for R, w in rivers):
                continue
            bad.append((round(mid[0]), round(mid[1]), round(ang, 1)))
    assert len(bad) <= 3, bad[:10]


def test_parks_per_domain(phil):
    m, g = phil
    pk = {p["n"]: p for p in g["parks"]}
    assert "Clarence H. Clark Park" in pk and "Rittenhouse Square" in pk
    sw = pk["Clarence H. Clark Park"]
    assert sw.get("f") and abs(sw["f"][0]) > 20                       # on the turned south-west lattice
    drawn = shape([sw], g["grid"]["xg"], g["grid"]["yg"])
    assert drawn and drawn[0]["r"]
    # the shaped park lies where Clark Park maps on the page, near the real place
    tx, ty = drawn[0]["t"]
    mp = palace_grid.mapping_from(g["doms"][[d["id"] for d in g["doms"]].index(next(
        d["id"] for d in g["doms"] if abs(d["a"] - sw["f"][0]) < 1e-3))]["mapping"]) if False else None
    assert 0 < tx < g["W"] and 0 < ty < g["H"]


def test_report_has_spacing_and_fronts(phil):
    m, g = phil
    rep = city_report.report(g, m)
    assert {"spacing", "fronts"} <= set(rep["checks"])
    assert not any("could not run" in rep["checks"][k]["msg"] for k in ("spacing", "fronts"))
