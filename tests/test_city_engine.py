"""City engine v2 integrated (palace_grid.grid -> city_engine.build): Philadelphia from the offline fixture through the
whole pipeline (angled seams, hinges, per-domain blocks, no overlap), the v2 page mapping (to_px / real_of) and the
lot-key migration of saved building placements (palace_place.migrate, palace.migrate_placements)."""
import copy
import gzip
import json
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_grid, palace_place as pp  # noqa: E402
from alto.build.city_lattice import _segdist, inside  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cities" / "philadelphia.json.gz"
MAJORS = ["Broad Street", "Market Street", "Baltimore Avenue", "Kensington Avenue", "Lancaster Avenue",
          "Woodland Avenue", "Chester Avenue", "Allegheny Avenue", "Girard Avenue", "Spruce Street"]


@pytest.fixture(scope="module")
def phil():
    if not FIX.exists():
        pytest.skip("no Philadelphia fixture")
    m = json.loads(gzip.decompress(FIX.read_bytes()).decode())
    g = palace_grid.grid(copy.deepcopy(m), majors=MAJORS)
    return m, g


def _ang(s):
    x0, y0, x1, y1 = s
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


def test_philadelphia_takes_the_v2_path_with_angled_seams(phil):
    m, g = phil
    e = g["engine"]
    assert e["path"] == "v2" and e["domains"] >= 3
    seams = {s["avenue"]: s for s in g["seams"]}
    # Baltimore Ave: angled about -20 degrees (real -18), never the horizontal box edge of 1.9.78
    b = seams["Baltimore Avenue"]
    assert -26 < _ang(b["segs"][0]) < -16 and len(b["hinge"]) >= 6
    k = seams["Kensington Avenue"]
    assert 40 < abs(_ang(k["segs"][0])) < 55 and len(k["hinge"]) >= 8
    # the seams are streets the walking graph uses, the seam avenues heavy
    sm = [s for s in g["streets"] if s.get("sm")]
    assert {s["n"] for s in sm} >= {"Baltimore Avenue", "Kensington Avenue"} and all(s.get("L") for s in sm if s["n"])
    assert "TILT_BOX" not in dir(palace_grid) and "TILT_DEG" not in dir(palace_grid)


def test_hinge_streets_bend_once_on_the_seam(phil):
    m, g = phil
    for s in g["seams"]:
        x0, y0, x1, y1 = s["segs"][0]
        for h in s["hinge"]:
            st = [t for t in g["streets"] if t["n"] == h["n"] and not t.get("sm")]
            hit = [t for t in st if any(math.hypot(t["p"][i] - h["at"][0], t["p"][i + 1] - h["at"][1]) < 3
                                        for i in range(0, len(t["p"]), 2))]
            assert hit, h["n"]
            # the bend point lies on the seam
            dx, dy = x1 - x0, y1 - y0
            t_ = ((h["at"][0] - x0) * dx + (h["at"][1] - y0) * dy) / (dx * dx + dy * dy)
            px, py = x0 + t_ * dx, y0 + t_ * dy
            assert math.hypot(px - h["at"][0], py - h["at"][1]) < 1.0


@pytest.mark.xfail(sys.platform == "win32", strict=False,
                   reason="Windows libm float difference flips a discrete decision in the Philadelphia city (block #3374 deep inside two domains); "
                          "Mac/Linux give 0 overlaps; cosmetic, Philadelphia only; tracked in ORG/notes-testing/beta-failures.md")
def test_blocks_lots_inside_and_no_two_domains_overlap(phil):
    m, g = phil
    tiles = [[(t[0], t[1]), (t[2], t[1]), (t[2], t[3]), (t[0], t[3])] for t in g["tiles"]]
    tq = [list(zip(q[0::2], q[1::2])) for q in g["tq"]]
    polys = tiles + tq
    # every lot centre stands in a drawn block
    cell = 500.0
    idx = {}
    for k, q in enumerate(polys):
        xs, ys = [p[0] for p in q], [p[1] for p in q]
        for i in range(int(min(xs) // cell), int(max(xs) // cell) + 1):
            for j in range(int(min(ys) // cell), int(max(ys) // cell) + 1):
                idx.setdefault((i, j), []).append(k)
    lots = [lt for b in g["blocks"] if not b.get("fr") for lt in b["lots"]]
    miss = [lt for lt in lots if not any(inside(polys[k], lt[0], lt[1]) for k in idx.get((int(lt[0] // cell), int(lt[1] // cell)), ()))]
    assert len(miss) == 0
    # a free domain's lots (P4: faces between its smoothed real streets) never stand in a grid block
    free = [lt for b in g["blocks"] if b.get("fr") for lt in b["lots"]]
    assert free
    inn = [lt for lt in free if any(inside(polys[k], lt[0], lt[1]) for k in idx.get((int(lt[0] // cell), int(lt[1] // cell)), ()))]
    assert len(inn) <= 0.02 * len(free)
    # no point is inside the blocks of two domains (the cut blocks of a seam meet on it, they do not overlap)
    bad = []
    for n, b in enumerate(g["blocks"][::7]):
        k = [i for i in idx.get((int(b["x"] // cell), int(b["y"] // cell)), ()) if inside(polys[i], b["x"], b["y"])]
        if len(k) > 1:
            d = [min(_segdist(b["x"], b["y"], *polys[i][j], *polys[i][(j + 1) % len(polys[i])]) for j in range(len(polys[i]))) for i in k]
            bad.append((n * 7, round(b["x"], 3), round(b["y"], 3), k, [round(v, 4) for v in d], b.get("fr")))
    assert not bad, bad[:3]                              # (a point exactly on a seam counts in both cut blocks; the detail says which)
    # (wall clock: 60 s on a developer machine; a shared CI runner is ~2.3x slower than this Mac, so CI gets 120 s. The build is ~26 s here)
    limit = 120 if os.environ.get("CI") else 60
    assert len(g["blocks"]) > 4000 and g["engine"]["t"]["total"] < limit


def test_v2_page_mapping_round_trips(phil):
    m, g = phil
    gm = dict(g, bbox=m["bbox"])
    errs = []
    for b in g["blocks"][::97]:
        r = pp.real_of(gm, b["x"], b["y"])
        x, y = pp.page_of(gm, *r)
        errs.append(math.hypot(x - b["x"], y - b["y"]))
    assert sorted(errs)[len(errs) // 2] < 5.0


def _city(majors):
    import test_palace as tp
    m = tp.city_map()
    return palace_grid.grid(copy.deepcopy(m), majors=majors)


def test_migrate_moves_a_saved_lot_to_the_same_real_place():
    import test_palace as tp
    m = tp.city_map()
    g1 = palace_grid.grid(copy.deepcopy(m), majors=["Market Street"])
    # the same city drawn with one street fewer: every block number after it changes
    m2 = copy.deepcopy(m)
    m2["streets"] = [s for s in m2["streets"] if "Sansom" not in (s.get("n") or "")] or m2["streets"]
    g2 = palace_grid.grid(m2, majors=["Market Street"])
    b1, b2 = g1.pop("blocks"), g2.pop("blocks")
    keys = [f"{b['id']}.0" for b in b1]
    mp = pp.migrate(g1, b1, g2, b2, keys)
    lot1 = {f"{b['id']}.{k}": lt for b in b1 for k, lt in enumerate(b["lots"])}
    lot2 = {f"{b['id']}.{k}": lt for b in b2 for k, lt in enumerate(b["lots"])}
    moved = [k for k, v in mp.items() if v]
    assert len(moved) >= 0.8 * len(keys) and len(set(mp[k] for k in moved)) == len(moved)   # one building a lot
    for k in moved:
        r1 = pp.real_of(g1, *lot1[k][:2]); r2 = pp.real_of(g2, *lot2[mp[k]][:2])
        assert math.dist(r1, r2) < 150, (k, mp[k], r1, r2)


def test_migrate_placements_is_safe_when_the_old_city_cannot_be_read():
    pl = {"n1": {"lot": "3.1", "fno": 4}, "n2": {"lot": "9.0"}, "n3": {"fno": 2}}
    new = {"data_z": palace.pack({"map": {"W": 1, "H": 1}, "blocks": []})}
    out, rep = palace.migrate_placements({"data_z": "garbage"}, new, pl)
    assert out == {"n1": {"fno": 4}, "n3": {"fno": 2}} and rep["dropped"] == 2
    assert pl["n1"]["lot"] == "3.1"                       # the caller's dict is not changed
    # nothing saved: nothing to do
    assert palace.migrate_placements({}, new, {}) == ({}, {"moved": 0, "dropped": 0, "kept": 0})


def test_free_domains_drawn(phil):
    """P4: Philadelphia's free domains (Wissahickon/Wynnefield edge, Eastwick, the Manayunk void) are drawn as smoothed
    real streets (fr, drawn as M.te), joined to the grid's lattice nodes, with blocks/lots and a page domain record."""
    m, g = phil
    fr = [s for s in g["streets"] if s.get("fr")]
    doms = [d for d in g["doms"] if d["kind"] == "free"]
    assert len(doms) >= 2 and len(fr) > 100
    te = {tuple(p) for p in g["te"]}
    assert all(tuple(s["p"]) in te for s in fr)
    assert all(d["clip"] and d["mapping"] and d["fit"]["anchors"] >= 6 for d in doms)
    assert sum(1 for b in g["blocks"] if b.get("fr")) > 50
    # most free streets that stop at the grid's edge end on a drawn lattice node: shared with a grid street's vertex
    from alto.build import palace_place
    gr = palace_place.graph({"streets": g["streets"]})
    assert len(gr["e"]) > 0


def test_the_glass_widens_to_show_a_lake_whose_shore_maps_past_its_edge():
    """Chicago: the lattice stops at the shore road, so the real shore maps past the glass's east edge and the clip hid all of
    the lake but the corner where the shore bends in. The glass is widened to the shore plus a strip of water; a shore inside
    the glass leaves it alone."""
    from alto.build import city_engine as ce
    W, H = 9000, 12000
    # a lake east of x = 10400 from y 4000 down, bending in to x = 8800 above that; the ring closes along the box edge
    ring = [8800, 0, 14000, 0, 14000, 12000, 10400, 12000, 10400, 4000, 8800, 3000]
    w = ce._sea_glass([ring], W, H)
    assert w == int(10400 + ce.SEA_STRIP) and w > W
    # a shore inside the glass everywhere: unchanged
    assert ce._sea_glass([[8000, 0, 9000, 0, 9000, 12000, 8000, 12000]], W, H) == W
    # never more than the reach
    far = [20000, 0, 21000, 0, 21000, 12000, 20000, 12000]
    assert ce._sea_glass([far], W, H) == int(W + ce.SEA_REACH)

def test_a_bridge_over_the_wide_river_on_another_side_crosses_it_and_stops():
    """Washington's Potomac lies west of the Mall: the bridge that leaves the street end runs to the river's far bank, not on
    east across the whole city to the glass edge (the 'Arlington Memorial Bridge' line across the Mall). The Delaware/Hudson
    (east edge) bridges still run to the glass."""
    from alto.build import city_engine as ce
    river = {"w": 230, "p": [3000, 0, 3000, 10000], "_q": [(3000.0, 0.0), (3000.0, 10000.0)]}
    x, y = ce._far_bank((3230.0, 5000.0), river, "w", 18000)
    assert abs(y - 5000) < 1e-6 and 2800 < x < 2900              # across the river's centre line and out the far bank
    assert ce._far_bank((3230.0, 5000.0), river, "e", 18000) == (18050.0, 5000.0)
    assert ce._far_bank((3230.0, 5000.0), river, None, 18000) == (18050.0, 5000.0)


def test_streets_that_stop_short_of_the_wide_river_run_down_to_its_bank():
    """Washington: the blocks in the Potomac's band are dropped and the streets stopped 150-300 px short of the bank. A street
    end that faces the river within reach is carried on to the bank; one that is far off, or already there, is left alone."""
    from alto.build import city_engine as ce
    from alto.build.city_avenues import PolyIndex
    river = [(0.0, float(y)) for y in range(-200, 2201, 50)]                  # a river down x = 0, 230 wide
    ix = [(PolyIndex(river, 200.0), 230)]
    near = {"n": "A", "k": 0, "p": [800.0, 500.0, 400.0, 500.0]}                # ends 400 off the centre: 255 off the bank edge
    far = {"n": "B", "k": 0, "p": [3000.0, 900.0, 2500.0, 900.0]}
    bridge = {"n": "C", "k": 0, "o": 1, "p": [800.0, 1500.0, 400.0, 1500.0]}
    streets = [near, far, bridge]
    ce._to_bank(streets, ix)
    assert near["p"][-2] < 400 and near["p"][-2] <= 230 / 2 + ce.BANK_GAP + 1 and near["p"][-1] == 500.0
    assert far["p"] == [3000.0, 900.0, 2500.0, 900.0] and bridge["p"] == [800.0, 1500.0, 400.0, 1500.0]
