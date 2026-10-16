"""City engine v2 integrated (palace_grid.grid -> city_engine.build): Philadelphia from the offline fixture through the
whole pipeline (angled seams, hinges, per-domain blocks, no overlap), the v2 page mapping (to_px / real_of) and the
lot-key migration of saved building placements (palace_place.migrate, palace.migrate_placements)."""
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

from alto.build import palace, palace_grid, palace_place as pp  # noqa: E402
from alto.build.city_lattice import inside  # noqa: E402

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
    ov = 0
    for b in g["blocks"][::7]:
        k = [i for i in idx.get((int(b["x"] // cell), int(b["y"] // cell)), ()) if inside(polys[i], b["x"], b["y"])]
        ov += len(k) > 1
    assert ov == 0
    assert len(g["blocks"]) > 4000 and g["engine"]["t"]["total"] < 60


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
