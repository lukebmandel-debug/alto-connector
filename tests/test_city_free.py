"""City engine v2: free mode (design section 6)."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import alto.build.palace  # noqa: F401
from alto.build import city_free as cf
from alto.build.palace_place import graph
from city_synth import free_city


def test_fit_similarity_recovers_a_transform():
    T = (1.7, 0.3, 120.0, -40.0)
    src = [(0, 0), (100, 0), (40, 90), (300, 210)]
    dst = [cf.sim(T, p) for p in src]
    s, a, tx, ty = cf.fit_similarity(src, dst)
    assert abs(s - 1.7) < 1e-6 and abs(a - .3) < 1e-6 and abs(tx - 120) < 1e-4 and abs(ty + 40) < 1e-4
    s0, a0, _, _ = cf.fit_similarity(src, dst, rotate=False)
    assert a0 == 0.0


def test_select_keeps_main_streets_and_the_street_a_landmark_fronts():
    m = free_city()
    m["streets"].append({"n": "Tiny Mews", "k": 5, "p": [100, 100, 130, 100]})
    m["streets"].append({"n": "Front Lane", "k": 5, "p": [1300, 1000, 1330, 1010]})   # at The Cross
    names = {s["n"] for s in cf.select(m)}
    assert "Radial 0 Road" in names and "Ring 1" in names
    assert "Tiny Mews" not in names and "Front Lane" in names


def test_smooth_is_dp_then_chaikin():
    zig = [(x, 3 * (x % 2)) for x in range(0, 200, 10)] + [(200, 0), (200, 200)]
    sm = cf.smooth(zig)
    assert max(abs(y) for x, y in sm if x < 120) < 3.1        # the wobble under 12 px is gone
    turns = [abs(math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0]))
             for a, b, c in zip(sm, sm[1:], sm[2:])]
    assert max(turns) < math.radians(50)                       # the corner is rounded


def test_snap_ends_makes_t_joins_the_graph_routes_through():
    polys = [[(0, 0), (500, 0)], [(250, 18), (250, 300)]]
    cf.snap_ends(polys)
    assert polys[1][0] == (250.0, 0.0) and (250.0, 0.0) in polys[0]
    g = graph({"streets": [{"n": "A", "k": 3, "p": [v for q in polys[0] for v in q]},
                           {"n": "B", "k": 3, "p": [v for q in polys[1] for v in q]}]})
    assert any(set(names) == {"A", "B"} for _, names in g["x"])


def test_clip_out_and_join_keep_free_streets_off_the_lattice():
    ring = [(400, -100), (900, -100), (900, 600), (400, 600)]
    polys = [[(0, 100), (1200, 100)], [(100, 300), (395, 300)]]
    pieces = cf.clip_out(polys, [ring])
    assert len(pieces) == 3                               # the first street is cut in two
    assert all(not (400 < x < 900) for _, P in pieces for x, y in P)
    joined = cf.join(pieces, [ring], nodes=[(400, 110), (900, 90)])
    ends = [P[-1] for i, P in joined if i == 0][:1] + [P[0] for i, P in joined if i == 0][1:]
    assert (400, 110) in ends and (900, 90) in ends


def test_build_free_city_draws_blocks_lots_and_a_routable_graph():
    m = free_city()
    page = cf.build(m)
    assert page["streets"] and page["tq"] and page["blocks"]
    assert 1.0 <= page["free"]["sigma"] <= 3.5
    degs = {round(l[4]) for b in page["blocks"] for l in b["lots"]}
    assert len(degs) > 2                                  # lots turned to their block's own streets
    g = graph(page)
    # every radial meets the first ring: named intersections exist between them
    xs = {tuple(sorted(n)) for _, n in g["x"]}
    assert sum(1 for n in xs if "Ring 0" in n) >= 8
    # the landmark is carried by the same transform
    lm = page["landmarks"][0]
    q = cf.sim(page["free"]["T"], (m["landmarks"][0]["x"], m["landmarks"][0]["y"]))
    assert math.dist((lm["x"], lm["y"]), q) < .2
