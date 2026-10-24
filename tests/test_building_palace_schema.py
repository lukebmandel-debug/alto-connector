"""The Memory Blueprint's plan format (alto/build/building_schema.py): validation, hashing, storage, assignment, size."""
import copy
import gzip
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs  # noqa: E402


class N:
    def __init__(self, i, parent=""):
        self.id, self.parent = i, parent


def bad(mutate, *want):
    p = bs.fixture()
    mutate(p)
    with pytest.raises(bs.PlanError) as e:
        bs.validate_plan(p)
    text = " | ".join(e.value.problems)
    for w in want:
        assert w in text, (w, text)
    return e.value


def test_the_fixture_is_valid_and_fake():
    p = bs.fixture()
    warns = bs.validate_plan(p)
    assert any("placeholder" in w for w in warns)                       # the confidence-0 print room says so
    assert p["name"] == "Alto Test Pavilion" and "Invented" in p["src"][0]["t"]
    assert {lv["id"] for lv in p["lv"]} == {"g", "u"} and len(p["rm"]) == 4 and p["st"] and p["sl"] and p["cols"] and p["en"]
    assert bs.summary(p)["rooms_by_confidence"] == {"0": 1, "1": 1, "2": 2}


def test_errors_name_the_element_and_come_all_at_once():
    e = bad(lambda p: (p["rm"][0].update(p=[[0, 0], [4, 4], [4, 0], [0, 4]]), p["rm"][1].update(ch=0.5), p["wl"][0].update(t=0)),
            "rm[0] 'hall': polygon crosses itself", "rm[1] 'g101': ch", "wl[0] 'g-out': t")
    assert len(e.problems) == 3
    bad(lambda p: p["rm"][0].update(l="nope"), "level 'nope' is not in lv")
    bad(lambda p: p["rm"][0].update(id="g101"), "duplicate id")
    bad(lambda p: p["rm"][0].update(fm="unobtainium"), "not in the material vocabulary")
    bad(lambda p: p["rm"][0].update(ty="dungeon"), "ty must be one of")
    bad(lambda p: p.update(v=2), "v: must be 1")
    bad(lambda p: p.update(surprise=1), "unknown key 'surprise'")
    bad(lambda p: p["rm"][0].update(s=["ghost"]), "source 'ghost' is not in src")
    bad(lambda p: p["rm"][0].update(c=7), "c is a whole number 0-3")
    bad(lambda p: p.update(lv=[]), "at least one level")
    bad(lambda p: p["lv"][1].update(e=0), "share an elevation")


def test_a_one_off_material_is_allowed():
    p = bs.fixture()
    p["rm"][0]["fm"] = "x:green terrazzo"
    bs.validate_plan(p)


def test_openings_must_fit_their_wall():
    bad(lambda p: p["wl"][0]["o"].append({"k": "door", "a": 70, "w": 2, "h": 2.5}), "runs off the wall")
    bad(lambda p: p["wl"][0]["o"].append({"k": "window", "a": 4.5, "w": 1.0, "h": 2.0, "z": 1.0}), "overlap")
    bad(lambda p: p["wl"][1]["o"].append({"k": "door", "a": 3, "w": 1, "h": 9}), "above the wall's")
    bad(lambda p: p["wl"][1]["o"].append({"k": "portcullis", "a": 3, "w": 1, "h": 2}), "k must be one of")


def test_stairs_slots_entrances_and_tour_are_checked():
    bad(lambda p: p["st"][0].update(to="g"), "from and to are the same level")
    bad(lambda p: p["st"][0].update(to="roof"), "level 'roof' is not in lv")
    bad(lambda p: p["sl"][0].update(rm="vault"), "room 'vault' is not in rm")
    bad(lambda p: p["sl"][0].update(w="g-mid", rm="u201"), "another level")
    bad(lambda p: p["sl"][0].update(al=["selfie"]), "al is a non-empty list")
    bad(lambda p: p["en"][0].update(wall="ghost"), "wall 'ghost' is not in wl")
    bad(lambda p: p.update(tour=["hall", "hall"]), "appears twice")
    bad(lambda p: p.update(tour=["nowhere"]), "'nowhere' is not a room")
    p = bs.fixture()
    p["sl"][0]["p"] = [60, 60]
    assert any("outside room" in w for w in bs.validate_plan(p))
    p = bs.fixture()
    p["st"][0]["n"] = 8                                        # 5.5 m in 8 steps
    assert any("riser" in w for w in bs.validate_plan(p))


def test_confidence_and_source_are_per_element_and_every_source_should_be_used():
    p = bs.fixture()
    p["src"].append({"id": "spare", "t": "Unused", "k": "photo"})
    assert any("'spare': no element cites it" in w for w in bs.validate_plan(p))
    p["src"][1]["u"] = "ftp://x"
    with pytest.raises(bs.PlanError, match="http"):
        bs.validate_plan(p)


def test_the_hash_and_the_stored_form_are_stable():
    p = bs.fixture()
    h = bs.plan_hash(p)
    assert len(h) == 12
    q = copy.deepcopy(p)
    q["rm"][0]["p"] = [[float(x) + 0.0004, float(y)] for x, y in q["rm"][0]["p"]]      # below a centimetre: the same plan
    assert bs.plan_hash(q) == h
    q["rm"][0]["n"] = "Entrance Hall 2"
    assert bs.plan_hash(q) != h
    q = {k: p[k] for k in reversed(list(p))}                   # key order does not matter
    assert bs.plan_hash(q) == h
    assert bs.unpack(bs.pack(p)) == bs.normalize(p)
    name, text = bs.hosted_json(p)
    assert name == f"plan-{h}.json" and json.loads(text) == bs.normalize(p)
    assert "None" not in text and ": " not in text             # compact


def test_a_real_sized_plan_stays_small_when_hosted():
    """A museum of 400 rooms, 3000 walls with openings, 600 slots: tens of KB gzipped, well under the page's own cap."""
    rnd = random.Random(7)
    p = bs.fixture()
    p["lv"] = [{"id": f"l{i}", "n": f"Level {i}", "e": i * 6.0, "h": 5.5} for i in range(4)]
    p["rm"], p["wl"], p["sl"], p["st"], p["cols"], p["fx"] = [], [], [], [], [], []
    p["en"] = [{"id": "main", "l": "l0", "p": [10, 0], "fc": -90, "w": 2.4}]
    for i in range(400):
        l, x, y = f"l{i % 4}", (i // 4 % 20) * 9.0 + rnd.random(), (i // 80) * 12.0 + rnd.random()
        poly = [[x, y], [x + 8.5, y], [x + 8.5, y + 11], [x, y + 11]]
        p["rm"].append({"id": f"r{i}", "l": l, "n": f"Gallery {i}", "no": str(100 + i), "ty": "gallery", "p": poly, "ch": 4.5,
                        "fm": "wood", "wm": "paint", "cm": "plaster", "li": {"k": "art", "lx": 200}, "c": i % 3 + 1, "s": ["inv"]})
        for j in range(7):
            p["wl"].append({"id": f"w{i}-{j}", "l": l, "p": [[x + j, y], [x + j + 1.3, y + 0.77], [x + j + 2.1, y + 3.31]], "t": 0.3, "m": "plaster",
                            "o": [{"k": "door", "a": 0.5, "w": 0.9, "h": 2.4, "d": "single"}] if j % 2 else [], "c": 2})
        for j in range(2):
            p["sl"].append({"id": f"s{i}-{j}", "rm": f"r{i}", "p": [x + 0.2, y + 2 + j * 3.37], "z": 1.6, "sz": [1.2, 0.9], "fc": 0, "al": ["painting"]})
    for i in range(400):
        p["cols"].append({"id": f"c{i}", "l": f"l{i % 4}", "p": [rnd.random() * 100, rnd.random() * 50], "r": 0.4})
    bs.validate_plan(p)
    s = bs.summary(p)
    assert s["bytes_gzip"] < 90_000 and s["bytes_json"] < 600_000, s
    assert len(bs.pack(p)) < 130_000


def test_the_size_guard_refuses_a_runaway_plan():
    p = bs.fixture()
    p["n"] = "x" * (bs.MAX_PLAN_BYTES + 10)
    with pytest.raises(bs.PlanError, match="bytes of JSON"):
        bs.validate_plan(p)


def test_rooms_are_handed_out_along_the_walk():
    p = bs.fixture()
    assert bs.room_order(p) == ["hall", "g101", "u201", "u202"]        # entrance level first, then up, by number
    p["tour"] = ["u201", "hall"]
    assert bs.room_order(p) == ["u201", "hall"]
    p = bs.fixture()
    p["rm"].append({"id": "gcorr", "l": "g", "n": "Corridor", "ty": "corridor", "p": [[0, 12], [20, 12], [20, 14], [0, 14]], "ch": 3})
    assert "gcorr" not in bs.room_order(p)                             # circulation is never a stop


def test_room_mode_gives_each_top_node_a_room_and_its_children_the_anchors():
    p = bs.fixture()
    nodes = [N("a"), N("a1", "a"), N("b"), N("b1", "b"), N("b2", "b"), N("c"), N("d"), N("e")]
    r = bs.assign_nodes(p, nodes)
    assert [r["assign"][i]["r"] for i in ("a", "b", "c", "d")] == ["hall", "g101", "u201", "u202"]
    assert r["unplaced"] == ["e"] and r["notes"]
    assert r["assign"]["a1"] == {"r": "hall", "a": None}               # the hall has no anchor: the child just stands in it
    assert [r["assign"][i]["a"] for i in ("b1", "b2")] == ["sl-101a", "sl-101b"]


def test_anchor_mode_walks_slots_and_fixtures_and_overrides_win():
    p = bs.fixture()
    nodes = [N(c) for c in "abcdefg"]
    r = bs.assign_nodes(p, nodes, "anchor")
    got = [r["assign"][i]["a"] for i in "abcde" if i in r["assign"]]
    assert got == ["sl-101a", "sl-101b", "plinth-a", "sl-201a", "sl-202a"] and r["unplaced"] == ["f", "g"]
    r = bs.assign_nodes(p, nodes, "anchor", {"c": "sl-202a", "z": "hall"})
    assert r["assign"]["c"] == {"r": "u202", "a": "sl-202a"} and "z" not in r["assign"]
    assert "sl-202a" not in [v["a"] for k, v in r["assign"].items() if k != "c"]      # an override's anchor is not handed out twice
    with pytest.raises(bs.PlanError, match="not a room, art slot or fixture"):
        bs.assign_nodes(p, nodes, "anchor", {"a": "attic"})
    with pytest.raises(bs.PlanError, match="mode"):
        bs.assign_nodes(p, nodes, "stroll")
    r = bs.assign_nodes(p, nodes, "room", {"a": "u202"})                # a room taken by hand is not handed out again
    assert r["assign"]["a"]["r"] == "u202" and [v["r"] for k, v in r["assign"].items() if k != "a"].count("u202") == 0
