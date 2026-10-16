"""City engine v2: avenues (design section 3) — chains, classification, the octilinear path, seam continuity,
naming by vote, labels."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import alto.build.palace  # noqa: F401  (import order: palace before palace_grid's lazy imports)
from alto.build import city_avenues as ca
from alto.build.city_types import Domain, Seam
from alto.build.palace_grid import grid, CW, CH, mapping_from
from city_synth import grid_city, tilted_streets, W, H


def _octi(a, b, tol=0.6):
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 45
    return min(ang, 45 - ang) <= tol


def test_chains_join_gaps_and_order_the_course():
    m = grid_city()
    ch = ca.chains(m, {"Diagonal Avenue"})["Diagonal Avenue"]
    assert len(ch) == 1                                   # the two ways and the gap are one course
    P = ch[0]
    assert ca.plen(P) > 1900
    xs = [p[0] for p in P]
    assert xs == sorted(xs) or xs == sorted(xs, reverse=True)


def test_a_dual_carriageway_counts_once():
    m = grid_city(diagonal=False)
    m["streets"].append({"n": "Twin Boulevard", "k": 2, "p": [100, 1500, 2400, 1500]})
    m["streets"].append({"n": "Twin Boulevard", "k": 2, "p": [2400, 1520, 100, 1520]})
    ch = ca.chains(m, {"Twin Boulevard"})["Twin Boulevard"]
    assert len(ch) == 1 and abs(ca.plen(ch[0]) - 2300) < 5


def test_classify_lattice_diagonal_and_seam():
    m = grid_city()
    # a second domain in the east, its boundary along 'Seam Road' (an avenue that runs on the boundary)
    m["streets"].append({"n": "Seam Road", "k": 2, "p": [1700, 0, 1700, 1700]})
    root = Domain(id=0, kind="grid", theta=0.0, poly=[(0, 0), (W, 0), (W, H), (0, H)])
    east = Domain(id=1, kind="grid", theta=math.radians(30), poly=[(1700, 0), (W, 0), (W, H), (1700, H)])
    recs = {r["n"]: r for r in ca.classify(m, [root, east], majors=["Row A Street"])}
    d = recs["Diagonal Avenue"]
    kinds = {(p["dom"], p["kind"]) for p in d["pieces"]}
    assert (0, "diagonal") in kinds
    a = {p["dom"]: p for p in recs["Row A Street"]["pieces"]}
    assert a[0]["kind"] == "lattice" and a[0]["fam"] == "h"
    assert a[1]["kind"] == "diagonal"                     # 30 degrees off the east domain's axes
    s = recs["Seam Road"]
    assert s["seam_share"] >= .6 and all(p["kind"] == "seam" and p["seam"] == (0, 1) for p in s["pieces"])


def test_forced_diagonal_and_motorways_are_not_avenues():
    m = grid_city()
    m["streets"].append({"n": "Quick Expressway", "k": 0, "p": [0, 50, W, 1900]})
    assert "Quick Expressway" not in ca.candidates(m)
    assert "Quick Expressway" in ca.candidates(m, diagonals=["Quick Expressway"])


def test_octi_path_runs_on_axes_or_45_with_at_most_two_bends():
    chain = [(0, 0), (300, 40), (700, 300), (1000, 640), (1400, 700)]
    for ends_a, ends_b in (([(0, 0)], [(1400, 700)]), ([(0, 0), (40, 0)], [(1400, 680)])):
        res = ca.octi_path(chain, ends_a, ends_b)
        P = res["p"]
        assert res["bends"] <= 2 and len(P) - 2 == res["bends"]
        assert P[0] in ends_a and P[-1] in ends_b
        assert all(_octi(a, b) for a, b in zip(P, P[1:]))
        assert res["fit"] < 90                    # close to the real course


def test_octi_path_node_mode_uses_the_lattice_diagonal():
    res = ca.octi_path([(0, 0), (CW * 3, CH * 3)], [(0, 0)], [(CW * 3, CH * 3)], mode="node")
    assert res["bends"] == 0                      # |di| = |dj|: one straight node-to-node run


def test_draw_on_todays_lattice_ends_on_drawn_nodes_with_leads():
    m = grid_city()
    g = grid(m, majors=["Row A Street"])
    root = Domain(id=0, kind="grid", theta=g["grid"]["t"], poly=[(0, 0), (W, 0), (W, H), (0, H)],
                  mapping=mapping_from(g["grid"]))
    nodes = sorted({(x, y) for t in g["tiles"] for x, y in ((t[0], t[1]), (t[2], t[1]), (t[0], t[3]), (t[2], t[3]))})
    recs = [r for r in ca.classify(m, [root]) if r["n"] == "Diagonal Avenue"]
    out = ca.draw(recs, [root], {0: nodes})
    assert len(out) == 1
    s = out[0]
    P = list(zip(s["p"][0::2], s["p"][1::2]))
    core = P[1:-1]
    assert s["j"] == [1, 1] and core[0] in nodes and core[-1] in nodes
    assert all(_octi(a, b) for a, b in zip(P, P[1:]))
    assert max(s["bends"]) <= 2
    assert abs(math.dist(P[0], P[1]) - 40) < .01 and abs(math.dist(P[-1], P[-2]) - 40) < .01


def test_pieces_in_two_domains_meet_at_one_seam_node():
    # one avenue crossing from domain 0 (west) into domain 1 (east), which is drawn turned by 20 degrees
    m = grid_city(diagonal=False, river=False)
    m["streets"].append({"n": "Long Avenue", "k": 2, "p": [100, 200, 1300, 1000, 2500, 1600]})
    d0 = Domain(id=0, kind="grid", theta=0.0, poly=[(0, 0), (1300, 0), (1300, H), (0, H)], mapping=lambda x, y: (x, y))
    d1 = Domain(id=1, kind="grid", theta=0.0, poly=[(1300, 0), (W, 0), (W, H), (1300, H)],
                mapping=lambda x, y: (x - 1300, y - 1000), a=20.0, o=(1300.0, 1000.0))
    seam = Seam(a=0, b=1, kind="fold", segs=[(1300, 0, 1300, H)])
    nodes0 = [(x, y) for x in range(100, 1301, 100) for y in range(100, 1901, 100)]
    nodes1 = [(x, y) for x in range(0, 1301, 100) for y in range(-1000, 1001, 100)]
    recs = [r for r in ca.classify(m, [d0, d1]) if r["n"] == "Long Avenue"]
    assert sorted(p["dom"] for p in recs[0]["pieces"]) == [0, 1]
    out = ca.draw(recs, [d0, d1], {0: nodes0, 1: nodes1}, seams=[seam])
    assert len(out) == 1, out                         # one street: end-to-end continuity
    P = list(zip(out[0]["p"][0::2], out[0]["p"][1::2]))
    assert any(abs(x - 1300) < .5 for x, y in P)      # the seam node is on the seam
    assert len(out[0]["bends"]) == 2 and max(out[0]["bends"]) <= 2


def test_name_lines_votes_like_the_tilted_district():
    m = grid_city(diagonal=False, river=False)
    m["streets"] += tilted_streets(1300, 1000, 40, n=6, step=150)
    th = math.radians(40)
    c, s = math.cos(-th), math.sin(-th)

    def local(x, y):                              # the tilted lattice's frame: lines at multiples of 150
        x, y = x - 1300, y - 1000
        return (x * c - y * s, x * s + y * c)
    names = ca.name_lines(m, th, local, {"h": 150, "v": 150},
                          inside=lambda x, y: math.hypot(x - 1300, y - 1000) < 500, min_len=300)
    assert names[("h", 0)][0]["n"] == "Tilt H6 Street"
    assert names[("v", 1)][0]["n"] == "Tilt V5 Street"     # the generator counts this family the other way
    assert names[("v", -1)][0]["n"] == "Tilt V7 Street"
    assert all(k[0] in "hv" for k in names)


def test_name_lines_names_each_span():
    m = {"streets": [{"n": "Alder Street", "k": 3, "p": [0, 100, 900, 100]},
                     {"n": "Birch Street", "k": 3, "p": [1100, 102, 2000, 102]}]}
    names = ca.name_lines(m, 0.0, lambda x, y: (x, y), {"h": 100, "v": 100}, min_len=300)
    assert {n["n"] for n in names[("h", 1)]} == {"Alder Street", "Birch Street"}


def test_labels_read_left_to_right_and_do_not_overlap():
    sts = [{"n": "Grand Avenue", "k": 0, "d": 1, "p": [0, 0, 2000, -2000]},
           {"n": "Main Street", "k": 0, "p": [0, 500, 3000, 500]},
           {"n": "Over Street", "k": 0, "p": [0, 505, 3000, 505]}]
    lab = ca.labels(sts)
    assert all(-90 < l["a"] <= 90 for l in lab)
    assert {l["n"] for l in lab} >= {"Grand Avenue", "Main Street"}
    assert "Over Street" not in {l["n"] for l in lab}       # it would sit on Main Street's label


def test_two_avenues_never_share_a_run():
    # two parallel avenues a third of a block apart: the second takes its own row
    nodes = [(x, y) for x in range(0, 2401, 240) for y in range(0, 1701, 170)]
    dom = Domain(id=0, kind="grid", theta=0.0, poly=[(-100, -100), (2600, -100), (2600, 1900), (-100, 1900)])
    recs = [{"n": "First Avenue", "len": 2000, "pieces": [{"dom": 0, "kind": "diagonal",
             "pts": [(0, 330), (1200, 350), (2400, 340)]}]},
            {"n": "Second Avenue", "len": 1900, "pieces": [{"dom": 0, "kind": "diagonal",
             "pts": [(0, 380), (1200, 400), (2400, 390)]}]}]
    out = ca.draw(recs, [dom], {0: nodes})
    a, b = (list(zip(s["p"][0::2], s["p"][1::2])) for s in out)
    assert ca.shared(a, list(zip(b, b[1:]))) < CW
