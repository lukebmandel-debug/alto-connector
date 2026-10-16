"""The Mind Palace (brief.mode "palace"): validation, structure and numbers,
the geometry (palace_place), the built page and its isolation from the other
modes, manual-edit folds (lot / floor), get_timeline's city summary and the
set_up_palace tool. A tiny synthetic city is used throughout; nothing here
touches the network, Firebase or any ALTO_* setting."""
import copy
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto import palace_map  # noqa: E402
from alto.build import palace, palace_place as pp  # noqa: E402
from alto.build.brief import BriefError, validate_brief, validate_nodes  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.edits import fold  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

# ── the synthetic city ──────────────────────────────────────────────────────
W, H = 900, 600
# a box whose projection at scale 1 is about 900 x 600 px
BBOX = [39.95, -75.17, 39.95 + H / 110574, -75.17 + W / (math.cos(math.radians(39.95 + H / 221148)) * 111320)]
VERT = [(150, "South 15th Street"), (350, "South 16th Street"),
        (550, "South 17th Street"), (750, "South 18th Street")]
HORZ = [(100, "Walnut Street"), (300, "John F. Kennedy Boulevard"), (500, "Market Street")]


def city_map():
    streets = [{"n": n, "k": 4, "p": [x, 0, x, H]} for x, n in VERT]
    streets += [{"n": n, "k": 1, "p": [0, y, W, y]} for y, n in HORZ]
    return {
        "v": 1, "place": "Testville", "bbox": list(BBOX), "scale": 1.0, "W": W, "H": H,
        "attribution": "© OpenStreetMap contributors",
        "water": [[0, 570, W, 570, W, H, 0, H]],                       # along the bottom edge
        "rivers": [{"n": "Test River", "p": [0, 585, W, 585]}],
        "parks": [{"n": "Rittenhouse", "r": [[20, 130, 110, 130, 110, 270, 20, 270]]}],
        "streets": streets,
        "trails": [],
        "rails": [{"n": "Surface line", "r": "Line", "c": "#888888", "k": 0, "p": [0, 40, W, 40], "u": 0},
                  {"n": "Tunnel line", "r": "Line", "c": "#444444", "k": 0, "p": [60, 0, 60, H], "u": 1}],
        "stations": [{"n": "Central", "x": 350, "y": 300, "k": 0, "l": ["Surface line"]},
                     {"n": "Eastgate", "x": 750, "y": 500, "k": 0, "l": ["Tunnel line"]}],
        "landmarks": [{"n": "City Hall", "x": 840, "y": 200,
                       "r": [[810, 160, 880, 160, 880, 240, 810, 240]]}],
        "majors": ["John F. Kennedy Boulevard", "Market Street"],
    }


def districts():
    s, w, n, e = BBOX
    step = (e - w) / 3
    return [{"unit": i, "name": f"District {i}", "bounds": [s, w + i * step, n, w + (i + 1) * step]}
            for i in range(3)]


def packed():
    m = city_map()
    return palace.pack({"map": m, "blocks": pp.lots(m)})


def acts():
    return [{"label": "ONE", "short": "One", "color": "#4a9eff"},
            {"label": "TWO", "short": "Two", "color": "#22c55e"},
            {"label": "THREE", "short": "Three", "color": "#f59e0b"}]


def node(i, act, parent=None, **kw):
    d = {"id": i, "act": act, "tag": "Room", "title": i.upper(), "desc": f"About {i}."}
    if parent:
        d["parent"] = parent
    d.update(kw)
    return d


def bundle(with_city=True, **brief_kw):
    pal = {"place": "Testville", "bbox": list(BBOX), "districts": districts()}
    if with_city:
        pal["data_z"] = packed()
    brief = {"title": "Test Palace", "subject": "A made-up city", "timeline_id": "test-palace",
             "mode": "palace", "node_noun": "Room", "period_noun": "Wing",
             "accent": "#5b8def", "acts": acts(), "palace": pal}
    brief.update(brief_kw)
    nodes = [
        node("alpha", 0), node("alpha-1", 0, "alpha"), node("alpha-2", 0, "alpha-1"),   # nested floor
        node("alpha-3", 0, "alpha"), node("beta", 0),
        node("gamma", 1), node("gamma-1", 1, "gamma"), node("delta", 2), node("eps", 2),
    ]
    return {"brief": brief, "nodes": nodes, "connections": []}


def load(d):
    b, nodes, conns = load_brief(copy.deepcopy(d))
    return b, nodes, conns


def check(d):
    """Run both validators the way a build does; return the warnings."""
    b, nodes, _ = load(d)
    w = list(validate_brief(b) or [])
    w += list(validate_nodes(b, nodes) or [])
    return w


# ── 1. validation ───────────────────────────────────────────────────────────
def test_palace_mode_is_accepted():
    check(bundle())
    b, nodes, _ = load(bundle())
    assert b.mode == "palace"


def test_palace_object_needs_palace_mode():
    d = bundle()
    d["brief"]["mode"] = "linear"
    with pytest.raises(BriefError, match="mode 'palace'"):
        check(d)


def test_unknown_palace_keys_rejected():
    d = bundle()
    d["brief"]["palace"]["colour"] = "red"
    with pytest.raises(BriefError, match="unknown keys"):
        check(d)


@pytest.mark.parametrize("bad", [
    {"unit": "0", "bounds": [0, 0, 1, 1]},                       # unit not an int
    {"unit": 7, "bounds": [0, 0, 1, 1]},                         # no such section
    {"unit": 0},                                                 # no bounds
    {"unit": 0, "bounds": [0, 0, 1]},                            # wrong length
    {"unit": 0, "bounds": [1, 0, 0, 1]},                         # south >= north
    {"unit": 0, "bounds": [0, 1, 1, 0]},                         # west >= east
    {"unit": 0, "bounds": [0, 0, "1", 1]},                       # not numbers
])
def test_bad_districts_rejected(bad):
    d = bundle()
    d["brief"]["palace"]["districts"] = [bad]
    with pytest.raises(BriefError, match="districts"):
        check(d)


def test_floor_in_another_section_rejected():
    d = bundle()
    d["nodes"][1]["parent"] = "gamma"                           # alpha-1 is in act 0, gamma in act 1
    with pytest.raises(BriefError, match="stays in its building's section"):
        check(d)


def test_parent_cycle_rejected():
    d = bundle()
    d["nodes"][0]["parent"] = "alpha-2"                         # alpha -> alpha-2 -> alpha-1 -> alpha
    with pytest.raises(BriefError, match="loop|parent"):
        check(d)


def test_missing_parent_rejected():
    d = bundle()
    d["nodes"][1]["parent"] = "nowhere"
    with pytest.raises(BriefError, match="not a node"):
        check(d)


@pytest.mark.parametrize("hint", [
    {"shift": [1, 2]}, {"slide": 0.5}, {"lot": "1.0", "shift": [1, 2]}, {"lot": 3}, "1.0",
])
def test_palace_placement_is_a_lot_only(hint):
    d = bundle()
    d["brief"]["placement"] = {"alpha": hint}
    with pytest.raises(BriefError):
        check(d)


def test_palace_placement_with_a_lot_is_fine():
    d = bundle()
    d["brief"]["placement"] = {"alpha": {"lot": "0.0"}}
    check(d)


def test_no_city_is_a_warning_not_an_error():
    w = check(bundle(with_city=False))
    assert any("no city yet" in x for x in w)
    assert not any("no city yet" in x for x in check(bundle()))


# ── 2. structure and numbers ────────────────────────────────────────────────
def test_structure_and_numbers():
    b, nodes, _ = load(bundle())
    units, floors, of = palace.structure(b, nodes)
    assert units == [["alpha", "beta"], ["gamma"], ["delta", "eps"]]
    # bottom -> top, depth first: the nested floor comes right after its parent floor
    assert floors == {"alpha": ["alpha-1", "alpha-2", "alpha-3"], "gamma": ["gamma-1"]}
    assert of == {"alpha-1": "alpha", "alpha-2": "alpha", "alpha-3": "alpha", "gamma-1": "gamma"}
    num = palace.numbers(units, floors)
    assert num == {"alpha": "1.1", "alpha-1": "1.1-1", "alpha-2": "1.1-2", "alpha-3": "1.1-3",
                   "beta": "1.2", "gamma": "2.1", "gamma-1": "2.1-1", "delta": "3.1", "eps": "3.2"}


def test_a_section_with_no_buildings_still_numbers():
    d = bundle()
    d["nodes"] = [n for n in d["nodes"] if n["act"] != 1]
    b, nodes, _ = load(d)
    units, floors, _ = palace.structure(b, nodes)
    assert units[1] == []
    assert palace.numbers(units, floors)["delta"] == "3.1"


# ── 3. geometry ─────────────────────────────────────────────────────────────
def test_lots_finds_the_blocks_of_the_grid():
    m = city_map()
    blocks = pp.lots(m)
    # 3 columns between the 4 vertical streets; 4 rows (the surface rail at y=40
    # and the water at y=570 close off a strip each); the ring of blocks that
    # runs off the map's edge is cut away
    assert len(blocks) == 12
    assert [b["id"] for b in blocks] == list(range(12))
    assert sorted({round(b["x"]) for b in blocks}) == [250, 450, 650]
    xs = [x for x, _ in VERT]
    for bl in blocks:
        assert xs[0] < bl["x"] < xs[-1] and 40 < bl["y"] < 570
        assert 1 <= len(bl["lots"]) <= 4
        for cx, cy, w, h, deg in bl["lots"]:
            assert 0 < cx < W and 0 < cy < H
            assert w >= 20 and h >= 20
            # a lot's centre is clear of every street centre-line
            for x, _ in VERT:
                assert abs(cx - x) > 12
            for y, _ in HORZ:
                assert abs(cy - y) > 12


# ── the rivers (palace_river) ───────────────────────────────────────────────
def _turn_degrees(flat):
    pts = list(zip(flat[0::2], flat[1::2]))
    worst = 0.0
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        t1 = math.atan2(b[1] - a[1], b[0] - a[0])
        t2 = math.atan2(c[1] - b[1], c[0] - b[0])
        worst = max(worst, abs(math.degrees((t2 - t1 + math.pi) % (2 * math.pi) - math.pi)))
    return worst


def test_a_river_course_is_smooth_and_runs_off_both_ends():
    from alto.build import palace_river as pr
    # a lumpy real centre line: a bend with a kink and a little loop of noise in it
    wob = [(0, 0), (300, 40), (600, 10), (900, 120), (1000, 480), (1040, 520), (1010, 560), (1100, 900), (1500, 1300), (2000, 1330)]
    c = pr.course(wob)
    assert _turn_degrees([v for q in c for v in q]) < 6            # no kink: every step bends a few degrees at most
    assert c[0][0] < wob[0][0] - 500 and c[-1][0] > wob[-1][0] + 500   # carried well past the ends, off the glass
    # its two ends stay where the river was
    assert any(math.dist(q, wob[0]) < 1 for q in c) and any(math.dist(q, wob[-1]) < 1 for q in c)


def _wide_city():
    m = city_map()
    m["water"] = []
    m["rivers"] = [{"n": "Big River", "p": [1100, 600, 1060, 300, 1100, 0]}]
    m["bank"] = {"n": "Big River", "w": 600, "side": "e", "bridges": [{"n": "Test Bridge", "at": [700, 300]}]}
    return m


def test_a_wide_river_is_a_broad_band_along_the_east_edge_the_glass_holds():
    from alto.build import palace_grid, palace_river as pr
    g = palace_grid.grid(_wide_city(), majors=["Market Street"])
    base = palace_grid.grid({**_wide_city(), "bank": None, "rivers": []})
    last_col = base["W"] - palace_grid.PAD
    (rv,) = g["river"]
    assert rv["n"] == "Big River" and rv["w"] == pr.WIDE_W
    xs = rv["p"][0::2]
    assert min(xs) - rv["w"] / 2 >= last_col                       # its near bank is east of the last street
    assert g["W"] >= max(x for x, y in zip(xs, rv["p"][1::2]) if 0 <= y <= g["H"]) + rv["w"] / 2   # the glass holds it
    assert g["W"] > base["W"]


def test_a_bridge_over_the_wide_river_leaves_the_end_of_a_street_and_is_named():
    from alto.build import palace_grid
    g = palace_grid.grid(_wide_city(), majors=["Market Street"])
    (br,) = [s for s in g["streets"] if s.get("br")]
    assert br["n"] == "Test Bridge" and br["o"] == 1 and br["p"][1] == br["p"][3]       # straight, east
    assert br["p"][2] > g["W"]                                                        # across to the far side
    assert "Test Bridge" in g["majors"]                                               # so the page labels it
    rows = {palace_grid.PAD + j * palace_grid.CH for j in range(len(g["rows"]))}
    assert br["p"][1] in rows                                                         # it begins on a street's own row


def test_lots_are_deterministic_and_keep_clear_of_water_and_park():
    m = city_map()
    assert pp.lots(m) == pp.lots(copy.deepcopy(m))
    for bl in pp.lots(m):
        for cx, cy, *_ in bl["lots"]:
            assert cy < 570                                        # not in the water
            assert not (20 <= cx <= 110 and 130 <= cy <= 270)      # not in the park


def test_a_map_with_no_room_has_no_lots():
    m = city_map()
    m["streets"] = [{"n": "Wide", "k": 0, "p": [0, y, W, y]} for y in range(0, H + 1, 40)]
    assert pp.lots(m) == []


def test_graph_splits_crossing_streets():
    g = pp.graph(city_map())
    assert g["s"].count("Walnut Street") == 1
    named = {tuple(names) for _, names in g["x"]}
    assert ("South 15th Street", "Walnut Street") in named
    assert ("John F. Kennedy Boulevard", "South 17th Street") in named
    assert len(g["x"]) == 12                                       # 4 x 3 crossings
    # an intersection node sits at the crossing of those streets
    pts = g["n"]
    by_node = {nd: names for nd, names in g["x"]}
    for nd, names in by_node.items():
        x, y = pts[2 * nd], pts[2 * nd + 1]
        if "Walnut Street" in names:
            assert y == pytest.approx(100, abs=2)
        if "South 16th Street" in names:
            assert x == pytest.approx(350, abs=2)
    # every street is cut at its crossings: a vertical street has 3 crossings -> 4 edges
    edges = g["e"]
    sid = g["s"].index("South 15th Street")
    assert sum(1 for i in range(0, len(edges), 3) if edges[i + 2] == sid) == 4


def units3():
    return [["a1", "a2", "a3"], ["b1", "b2"], ["c1"]]


def test_place_is_deterministic_with_distinct_lots():
    m = city_map()
    blocks = pp.lots(m)
    at = pp.place(m, blocks, units3(), districts())
    assert at == pp.place(m, copy.deepcopy(blocks), units3(), districts())
    assert set(at) == {"a1", "a2", "a3", "b1", "b2", "c1"}
    assert len(set(at.values())) == 6
    keys = {f"{b['id']}.{k}" for b in blocks for k in range(len(b["lots"]))}
    assert set(at.values()) <= keys


def test_place_keeps_a_valid_fixed_lot_and_ignores_an_unknown_one():
    m = city_map()
    blocks = pp.lots(m)
    free = pp.place(m, blocks, units3(), districts())
    want = next(k for k in (f"{b['id']}.{j}" for b in blocks for j in range(len(b["lots"])))
                if k not in free.values())
    at = pp.place(m, blocks, units3(), districts(), {"b1": want})
    assert at["b1"] == want
    assert len(set(at.values())) == 6
    at2 = pp.place(m, blocks, units3(), districts(), {"b1": "99.9", "a1": "nope"})
    assert at2["b1"] != "99.9" and at2["a1"] != "nope"
    assert len(set(at2.values())) == 6


def test_place_two_nodes_never_share_a_fixed_lot():
    m = city_map()
    blocks = pp.lots(m)
    at = pp.place(m, blocks, units3(), districts(), {"a1": "0.0", "a2": "0.0"})
    assert len(set(at.values())) == 6


def test_place_spreads_a_unit_inside_its_district_box():
    m = city_map()
    blocks = pp.lots(m)
    ds = districts()
    at = pp.place(m, blocks, [["a", "b", "c"], [], []], ds)
    x0, y0, x1, y1 = pp.district_box(m, ds[0])
    by_key = {f"{b['id']}.{k}": b for b in blocks for k in range(len(b["lots"]))}
    assert (x1 - x0) == pytest.approx(W / 3, abs=3)
    for nid in "abc":
        bl = by_key[at[nid]]
        assert x0 <= bl["x"] <= x1 and y0 <= bl["y"] <= y1
    # buildings stand several to a block, like row houses (PER), the blocks spread along the walk:
    # three buildings take ceil(3 / PER) blocks, never PER + 1 on one
    per_block = {}
    for n in "abc":
        per_block[by_key[at[n]]["id"]] = per_block.get(by_key[at[n]]["id"], 0) + 1
    assert len(per_block) == -(-3 // pp.PER) and max(per_block.values()) <= pp.PER


def test_place_a_crowded_district_spills_over_without_losing_anyone():
    m = city_map()
    blocks = pp.lots(m)
    total = sum(len(b["lots"]) for b in blocks)
    ids = [f"n{i}" for i in range(total)]
    at = pp.place(m, blocks, [ids], districts()[:1])
    assert len(set(at.values())) == total


def test_a_small_district_stacks_its_buildings_instead_of_spilling_out_of_its_box():
    m = city_map()
    blocks = pp.lots(m)
    ds = districts()
    x0, y0, x1, y1 = pp.district_box(m, ds[0])
    inside = [b for b in blocks if x0 <= b["x"] <= x1 and y0 <= b["y"] <= y1 and len(b["lots"]) >= 3]
    assert len(inside) >= 2
    n = len(inside) * pp.PER + 1                   # more than PER to a block would hold, fewer than all its lots
    ids = [f"n{i}" for i in range(n)]
    at = pp.place(m, blocks, [ids, [], []], ds)
    by_key = {f"{b['id']}.{k}": b for b in blocks for k in range(len(b["lots"]))}
    assert len(set(at.values())) == n
    assert all(x0 <= by_key[at[i]]["x"] <= x1 and y0 <= by_key[at[i]]["y"] <= y1 for i in ids)


def test_district_box_and_to_px():
    m = city_map()
    assert pp.to_px(m, BBOX[2], BBOX[1]) == pytest.approx((0, 0), abs=1e-6)
    x, y = pp.to_px(m, BBOX[0], BBOX[3])
    assert x == pytest.approx(W, abs=1) and y == pytest.approx(H, abs=1)
    box = pp.district_box(m, {"bounds": BBOX})
    assert box == pytest.approx((0, 0, W, H), abs=1)


# ── 4. short ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,want", [
    ("South 15th Street", "S 15th St"),
    ("John F. Kennedy Boulevard", "John F. Kennedy Blvd"),
    ("North Broad Street", "N Broad St"),
    ("Market Street", "Market St"),
    ("West Girard Avenue", "W Girard Ave"),
    ("Parkway", "Pkwy"),
    ("", ""), (None, ""),
])
def test_short(name, want):
    assert palace.short(name) == want


# ── 5. the built page ───────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def page():
    html, _ = build_timeline(*load(bundle()))
    return html


def test_palace_data_names_everything(page):
    m = re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", page, re.S)
    assert m, "no window._ALTO_PALACE="
    data = json.loads(m.group(1))
    for key in ("at", "fl", "of", "num", "near", "d", "m", "b", "par", "place"):
        assert key in data, key
    assert set(data["at"]) == {"alpha", "beta", "gamma", "delta", "eps"}
    assert len(set(data["at"].values())) == 5
    assert data["fl"]["alpha"] == ["alpha-1", "alpha-2", "alpha-3"]
    assert data["of"]["alpha-2"] == "alpha"
    assert data["par"] == {"alpha-1": "alpha", "alpha-2": "alpha-1", "alpha-3": "alpha", "gamma-1": "gamma"}
    assert data["num"]["alpha-2"] == "1.1-2" and data["num"]["eps"] == "3.2"
    assert len(data["d"]) == 3 and all(len(d["box"]) == 4 for d in data["d"])
    assert data["place"] == "Testville"
    # corner names are short and name two streets
    assert all(" & " in v for v in data["near"].values())
    assert all("Street" not in v and "Boulevard" not in v for v in data["near"].values())
    assert "S 15th St" in {s["n"] for s in data["m"]["streets"]}
    assert "bbox" not in data["m"]


def test_the_page_carries_the_palace(page):
    assert "window._altoPalace=function" in page
    assert "#palace-svg" in page
    assert "window._altoPalace && window._altoPalace(nodeHeights)" in page
    assert "_altoPalaceNav" in page
    assert "_altoPalaceGeo" in page
    assert "Map data © OpenStreetMap contributors" in page


def test_the_build_is_deterministic():
    a, _ = build_timeline(*load(bundle()))
    b, _ = build_timeline(*load(bundle()))
    assert re.search(r"window\._ALTO_PALACE=.*?;\n", a, re.S).group(0) == \
        re.search(r"window\._ALTO_PALACE=.*?;\n", b, re.S).group(0)


def test_a_fixed_lot_shows_in_the_page():
    d = bundle()
    free, _ = build_timeline(*load(d))
    at = json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", free, re.S).group(1))["at"]
    blocks = palace.unpack(d["brief"]["palace"]["data_z"])["blocks"]
    want = next(k for k in (f"{b['id']}.{j}" for b in blocks for j in range(len(b["lots"])))
                if k not in at.values())
    d["brief"]["placement"] = {"beta": {"lot": want}}
    html, _ = build_timeline(*load(d))
    assert json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", html, re.S).group(1))["at"]["beta"] == want


def test_a_palace_with_no_city_still_builds_with_a_none_marker():
    html, _ = build_timeline(*load(bundle(with_city=False)))
    data = json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", html, re.S).group(1))
    assert data["none"] == 1 and data["num"]["beta"] == "1.2"


def test_other_modes_carry_no_palace_code():
    """The engine patches mention the palace only as guarded hooks (a missing
    window._altoPalace is falsy); none of the palace's data, JS, CSS or credit
    is in a page of another mode."""
    for sample in ("contracts_brief.json", "lanes_brief.json", "outline_brief.json"):
        d = json.loads((ROOT / "samples" / sample).read_text())
        html, _ = build_timeline(*load_brief(d))
        for needle in ("window._ALTO_PALACE=", "#palace-svg", "window._altoPalace=function",
                       "window._altoPalaceNav=", "window._altoPalaceGeo=", "OpenStreetMap",
                       "palace-svg"):
            assert needle not in html, (sample, needle)
        # the only mention is the guarded read in the numbering line
        assert len(re.findall(r"_ALTO_PALACE", html)) == len(
            re.findall(r"\(window\._ALTO_PALACE && window\._ALTO_PALACE\.num && window\._ALTO_PALACE\.num\[id\]\)", html)) * 3, sample


# ── 6. folding manual edits ─────────────────────────────────────────────────
class Store:
    def __init__(self, d):
        self.doc = {"timeline_id": "t1", "brief": copy.deepcopy(d["brief"]), "consent": {"sources": []}}
        self.nodes = copy.deepcopy(d["nodes"])
        self.edits = None
        self.conns = []

    def get_timeline(self, uid, tid):
        return self.doc

    def put_timeline(self, uid, tid, doc):
        self.doc = copy.deepcopy(doc)

    def list_nodes(self, uid, tid):
        return self.nodes

    def put_nodes(self, uid, tid, nodes):
        by = {n["id"]: n for n in nodes}
        self.nodes = [copy.deepcopy(by.get(n["id"], n)) for n in self.nodes]

    def delete_nodes(self, uid, tid, ids):
        self.nodes = [n for n in self.nodes if n["id"] not in ids]

    def get_connections(self, uid, tid):
        return self.conns

    def put_connections(self, uid, tid, conns):
        self.conns = copy.deepcopy(conns)

    def get_edits(self, uid, tid):
        return copy.deepcopy(self.edits)

    def put_edits(self, uid, tid, data):
        self.edits = copy.deepcopy(data)


def _n(st, i):
    return next(n for n in st.nodes if n["id"] == i)


def ops(**kw):
    return {"v": 1, "ops": {k.replace("__", "|"): v for k, v in kw.items()}}


def test_a_lot_edit_folds_into_the_placement():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"p|beta|lot": {"b": None, "v": "3.0", "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 1, r
    assert st.doc["brief"]["placement"]["beta"] == {"lot": "3.0"}
    # the same edit again is already in the draft
    st.edits = {"v": 1, "ops": {"p|beta|lot": {"b": None, "v": "3.0", "t": 2}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 0 and r["already_in_draft"] == 1
    # an edit made against another lot than the draft's is a conflict: the draft wins
    st.edits = {"v": 1, "ops": {"p|beta|lot": {"b": "1.0", "v": "2.0", "t": 3}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["p|beta|lot"]
    assert st.doc["brief"]["placement"]["beta"] == {"lot": "3.0"}
    # the folded draft is a valid palace and builds
    build_timeline(*load({"brief": st.doc["brief"], "nodes": st.nodes}))


def test_clearing_a_lot_removes_the_hint():
    d = bundle()
    d["brief"]["placement"] = {"beta": {"lot": "3.0"}}
    st = Store(d)
    st.edits = {"v": 1, "ops": {"p|beta|lot": {"b": "3.0", "v": "", "t": 1}}}
    assert fold(st, "u", "t1")["folded"] == 1
    assert "beta" not in (st.doc["brief"].get("placement") or {})


def test_a_floor_edit_sets_and_clears_the_parent():
    st = Store(bundle())
    # beta (a building, base "") becomes a floor of alpha
    st.edits = {"v": 1, "ops": {"pf|beta": {"b": "", "v": "alpha", "t": 1}}}
    assert fold(st, "u", "t1")["folded"] == 1
    assert _n(st, "beta")["parent"] == "alpha"
    b, nodes, _ = load({"brief": st.doc["brief"], "nodes": st.nodes})
    units, floors, _ = palace.structure(b, nodes)
    assert units[0] == ["alpha"] and floors["alpha"][-1] == "beta"
    # again: already
    st.edits = {"v": 1, "ops": {"pf|beta": {"b": "", "v": "alpha", "t": 2}}}
    assert fold(st, "u", "t1")["already_in_draft"] == 1
    # let it out
    st.edits = {"v": 1, "ops": {"pf|beta": {"b": "alpha", "v": "", "t": 3}}}
    assert fold(st, "u", "t1")["folded"] == 1
    assert not _n(st, "beta").get("parent")
    build_timeline(*load({"brief": st.doc["brief"], "nodes": st.nodes}))


def test_a_floor_edit_that_loops_or_crosses_sections_is_a_conflict():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {
        "pf|alpha": {"b": "", "v": "alpha-2", "t": 1},      # alpha under its own floor: a cycle
        "pf|beta": {"b": "", "v": "gamma", "t": 2},         # another section
        "pf|delta": {"b": "", "v": "delta", "t": 3},        # itself
    }}
    r = fold(st, "u", "t1")
    assert r["folded"] == 0
    assert sorted(r["conflicts"]) == ["pf|alpha", "pf|beta", "pf|delta"]
    assert not _n(st, "alpha").get("parent") and not _n(st, "beta").get("parent")


def test_a_stale_floor_base_is_a_conflict():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"pf|alpha-1": {"b": "beta", "v": "", "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["pf|alpha-1"]
    assert _n(st, "alpha-1")["parent"] == "alpha"


def test_lot_and_floor_keys_are_not_targets_outside_a_palace():
    d = json.loads((ROOT / "samples" / "lanes_brief.json").read_text())
    st = Store(d)
    nid = d["nodes"][0]["id"]
    other = d["nodes"][1]["id"]
    st.edits = {"v": 1, "ops": {f"p|{nid}|lot": {"b": None, "v": "1.0", "t": 1},
                                f"pf|{nid}": {"b": "", "v": other, "t": 2}}}
    r = fold(st, "u", "t1")
    assert r is None or r["folded"] == 0
    assert "lot" not in (st.doc["brief"].get("placement") or {}).get(nid, {})
    assert not _n(st, nid).get("parent")


# ── 7. get_timeline shows a summary of the city ─────────────────────────────
def test_brief_out_summarises_the_packed_city():
    brief = bundle()["brief"]
    out = srv._brief_out(brief)
    pal = out["palace"]
    assert "data_z" not in pal
    city = pal["city"]
    assert (city["W"], city["H"]) == (W, H)
    assert city["blocks"] == 12
    assert city["lots"] == sum(len(b["lots"]) for b in palace.unpack(brief["palace"]["data_z"])["blocks"])
    assert city["streets"] == len(VERT) + len(HORZ)
    assert city["stored_kb"] >= 0
    assert pal["place"] == "Testville" and len(pal["districts"]) == 3
    assert "data_z" in brief["palace"]                       # the stored brief is untouched


def test_brief_out_leaves_other_briefs_alone_and_survives_garbage():
    lin = {"title": "x", "mode": "linear"}
    assert srv._brief_out(lin) is lin
    assert srv._brief_out(None) is None
    bad = {"palace": {"data_z": "not base64 gzip"}}
    assert srv._brief_out(bad)["palace"]["city"].startswith("unreadable")


# ── 8. set_up_palace ────────────────────────────────────────────────────────
@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))      # the OSM cache folder lives under it
    (tmp_path / "home").mkdir()
    srv.set_store(LocalStore(tmp_path / "store"))
    calls = []
    monkeypatch.setattr(palace_map, "fetch_osm", lambda bbox, **kw: calls.append(("fetch", tuple(bbox))) or {"elements": []})
    monkeypatch.setattr(palace_map, "build_map", lambda raw, bbox, **kw: city_map())
    monkeypatch.setattr(palace_map, "geocode", lambda *a, **k: pytest.fail("no network"))
    yield calls
    srv.set_store(None)


def _draft(mode="palace", palace_brief=True):
    pid = srv.create_project("City", "a palace", "memory")["project_id"]
    brief = bundle(with_city=False)["brief"]
    brief["mode"] = mode
    if not palace_brief or mode != "palace":
        brief.pop("palace", None)
    r = srv.create_timeline(pid, brief)
    assert "error" not in r, r
    return r["timeline_id"]


def test_set_up_palace_refuses_a_timeline_that_is_not_a_palace(store):
    tid = _draft(mode="linear")
    r = srv.set_up_palace(tid, "Testville", bbox=BBOX)
    assert r["error"] == "not_a_palace"
    assert store == []


def test_set_up_palace_refuses_a_too_big_box(store):
    tid = _draft()
    r = srv.set_up_palace(tid, "Testville", bbox=[39.0, -76.0, 40.0, -75.0])
    assert r["error"] == "area_too_big"
    assert store == []


def test_set_up_palace_refuses_a_backwards_box(store):
    tid = _draft()
    assert srv.set_up_palace(tid, "Testville", bbox=[40.0, -75.0, 39.9, -75.1])["error"] == "invalid_bbox"


def test_set_up_palace_stores_the_city(store):
    tid = _draft()
    r = srv.set_up_palace(tid, "Testville", bbox=BBOX, area="the middle", auto=False)
    assert r.get("ok") is True, r
    assert store == [("fetch", tuple(BBOX))]
    city = r["palace"]["city"]
    # the city is redrawn as an even grid (palace_grid): the synthetic map's four numbered streets and
    # three named ones become a 940 x 560 sheet of 6 blocks, whatever size the map was
    assert (city["W"], city["H"]) == (940, 560) and city["blocks"] == 6
    assert "data_z" not in r["palace"]
    assert r["palace"]["place"] == "Testville" and r["palace"]["area"] == "the middle"
    # districts were made for every section when none were given
    assert [d["unit"] for d in r["palace"]["districts"]] == [0, 1, 2]
    # stored with the timeline; get_timeline shows the summary only
    doc = srv.get_store().get_timeline(srv.uid(), tid)
    z = doc["brief"]["palace"]["data_z"]
    assert palace.unpack(z)["map"]["W"] == 940
    got = srv.get_timeline(tid)
    assert got["brief"]["palace"]["city"]["blocks"] == 6
    assert "data_z" not in got["brief"]["palace"]
    assert "next" in r


def test_the_page_draws_the_rivers_as_bands_with_names_and_cased_bridges():
    from alto.build import palace_grid
    m = _wide_city()
    g = palace_grid.grid(m, majors=["Market Street"])
    blocks = g.pop("blocks")
    d = bundle()
    d["brief"]["palace"]["data_z"] = palace.pack({"map": g, "blocks": blocks})
    html, _ = build_timeline(*load(d))
    assert '"river":[{"n":"Big River","w":230' in html
    for needle in ("function smoothD(", "function riverLabels(", "pl-rv-body", "pl-rv-sheen", "pl-casing", "clip-path"):
        assert needle in html


# ── 8. the look: street weights and neighbourhood names ─────────────────────
def _grid_bundle(**kw):
    from alto.build.palace_grid import grid
    m = grid(city_map(), majors=["John F. Kennedy Boulevard", "Market Street", "South 16th Street"])
    blocks = m.pop("blocks")
    d = bundle(**kw)
    d["brief"]["palace"]["data_z"] = palace.pack({"map": m, "blocks": blocks})
    d["brief"]["palace"]["districts"] = [
        {**x, "name": n} for x, n in zip(districts(), ("Old City", "Center City", "Mantua"))]
    return d


def test_streets_are_drawn_in_two_weights_on_the_screen():
    page = build_timeline(*load(_grid_bundle()))[0]
    # a major street and a minor one, each a connecting-line tube with its sheen, sized in screen px
    for cls, px in (("t-min", "3.6px"), ("t-maj", "5.6px")):
        assert f".pal-svg .pl-tube.{cls}{{stroke-width:calc(var(--tw,1) * {px});}}" in page
    assert "stubes(sg, byM, tc, 5.6, 't-maj')" in page and "stubes(sg, byU, tc, 3.6, 't-min')" in page
    assert "M.cols[i]" in page and "--tw" in page


def test_the_page_carries_the_grids_street_names_by_column_and_row():
    page = build_timeline(*load(_grid_bundle()))[0]
    data = json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", page, re.S).group(1))
    m = data["m"]
    assert m["cols"] and m["rows"] and all(isinstance(x, str) for x in m["cols"] + m["rows"])
    assert "Market St" in m["rows"] and "Market St" in m["majors"]
    assert "16th St" in m["cols"] and "16th St" in m["majors"]      # the grid names a street once, by its number


def test_districts_are_named_not_numbered_and_carry_their_unit_in_a_popup():
    page = build_timeline(*load(_grid_bundle()))[0]
    data = json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", page, re.S).group(1))
    assert [d["n"] for d in data["d"]] == ["Old City", "Center City", "Mantua"]
    assert "t.textContent=d.n || pm.label;" in page            # the name, not the numeral
    assert "pm.numeral+' · '" not in page
    assert "function distTip(u)" in page and "Unit '+esc(pm.numeral)" in page
    assert "pl-dtint" in page                                    # its ground answers the pointer too


def _chrome():
    sync_api = pytest.importorskip("playwright.sync_api")
    p = sync_api.sync_playwright().start()
    for launch in (lambda: p.chromium.launch(), lambda: p.chromium.launch(channel="chrome"), lambda: p.webkit.launch()):
        try:
            return p, launch()
        except Exception:                                    # noqa: BLE001
            continue
    p.stop()
    pytest.skip("no browser to drive")


def test_in_a_browser_streets_weigh_more_than_a_hair_and_a_district_pops_up_its_unit(tmp_path):
    page = build_timeline(*load(_grid_bundle()))[0]
    f = tmp_path / "p.html"
    f.write_text(page, encoding="utf-8")
    p, b = _chrome()
    try:
        pg = b.new_page(viewport={"width": 1400, "height": 800})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f.as_uri())
        pg.wait_for_timeout(1500)
        w = pg.evaluate("""()=>{ var z=window._altoPalaceGeo.Z, q=function(s){ var e=document.querySelector(s); return e?parseFloat(getComputedStyle(e).strokeWidth)*z:0; };
          return {min:q('#palace-svg .pl-tube.t-min'), maj:q('#palace-svg .pl-tube.t-maj'), sh:q('#palace-svg .pl-sheen.t-min')}; }""")
        assert 3 <= w["min"] < w["maj"] and w["maj"] >= 5 and w["sh"] >= 1.2, w          # screen px, whatever the zoom
        names = pg.evaluate("[...document.querySelectorAll('#palace-svg .pl-dist')].map(t=>t.textContent)")
        assert names == ["Old City", "Center City", "Mantua"]
        pg.evaluate("document.querySelector('#palace-svg .pl-dist[data-u=\"1\"]').dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:400,clientY:300}))")
        pg.wait_for_timeout(400)
        tip = pg.evaluate("(document.querySelector('#pal-dock.on')||{}).innerText")      # the docked card (no cursor-following box)
        assert "Center City" in tip and "Unit II" in tip and "TWO" in tip, tip
        assert not errs, errs
    finally:
        b.close()
        p.stop()


# ── 9. the whole city in the window, and bridges with a deck ────────────────
def _wide_page():
    from alto.build import palace_grid
    g = palace_grid.grid(_wide_city(), majors=["Market Street"])
    blocks = g.pop("blocks")
    d = bundle()
    d["brief"]["palace"]["data_z"] = palace.pack({"map": g, "blocks": blocks})
    return build_timeline(*load(d))[0]


def test_the_board_zooms_out_to_the_whole_city_and_a_bridge_has_a_deck_rails_piers_and_a_name():
    page = _wide_page()
    # the farthest zoom is the whole city in the window, not where a building's number stops being readable
    assert "function zmin(){ return fitZ()*.97;" in page
    assert "Math.max(fitZ()*.92, ZREAD)" not in page
    # far out the lines thin so a whole city of blocks stays a grid
    assert "Math.max(.34, Math.min(1, z/.24))" in page
    # a bridge: deck over rails over piers, then its street's own line; named
    for needle in ("pl-br-pier", "pl-br-edge", "pl-casing", "pl-brn", "--pal-br-edge"):
        assert needle in page, needle
    assert page.count("--pal-br-edge:") == 2           # light and dark


def test_in_a_browser_the_city_button_shows_the_whole_city_and_bridges_are_decked(tmp_path):
    f = tmp_path / "p.html"
    f.write_text(_wide_page(), encoding="utf-8")
    p, b = _chrome()
    try:
        pg = b.new_page(viewport={"width": 1400, "height": 800})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f.as_uri())
        pg.wait_for_timeout(1500)
        pg.click("#pal-ctl [data-z=fit]")
        pg.wait_for_timeout(900)
        r = pg.evaluate("""()=>{ var cv=document.getElementById('canvas'), s=document.getElementById('palace-svg').getBoundingClientRect();
          return {cw:cv.clientWidth, ch:cv.clientHeight, w:s.width, h:s.height, top:cv.scrollTop, left:cv.scrollLeft}; }""")
        assert r["w"] <= r["cw"] + 1 and r["h"] <= r["ch"] + 1, r          # all of it, at once
        deck = pg.evaluate("""()=>({pier:document.querySelectorAll('#palace-svg .pl-br-pier').length, edge:document.querySelectorAll('#palace-svg .pl-br-edge').length,
          deck:document.querySelectorAll('#palace-svg .pl-bridges .pl-casing').length})""")
        assert deck["pier"] == deck["edge"] == deck["deck"] and deck["deck"] >= 1, deck
        assert not errs, errs
    finally:
        b.close()
        p.stop()
