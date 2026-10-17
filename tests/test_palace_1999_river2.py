"""The river and the block outlines (1.9.99): the page draws the city's lines from m.tiles / m.edges / m.tq / m.te, not from m.streets, so
clipping the streets left every block the river passes through drawn as a whole box with its sides running under the water.
palace_banks.cut_outlines cuts those outlines at the bank, lists them (tcut / ecut / qcut) and draws their dry pieces as m.te polylines."""
import math

from alto.build import palace, palace_banks as pb


XS = list(range(0, 1201, 240))
YS = [2000, 2320, 2640, 3360, 3680]                            # the band (y 2950..3050) runs through the tall block row 2640..3360


def _mk():
    st = [{"n": f"V{i}", "k": 1, "p": [x, YS[0], x, YS[-1]]} for i, x in enumerate(XS)]
    st += [{"n": f"H{j}", "k": 1, "p": [XS[0], y, XS[-1], y]} for j, y in enumerate(YS)]
    tiles = [[XS[i], YS[j], XS[i + 1], YS[j + 1]] for i in range(len(XS) - 1) for j in range(len(YS) - 1)]
    return {"river": [{"n": "R", "w": 100, "p": [-400, 3000, 1600, 3000]}], "streets": st, "tiles": tiles, "edges": [], "tq": [], "te": []}


def _slack(m, x, y):
    return pb._Riv(m, reach=2000).near(x, y)[0]


def _cut():
    m = _mk()
    pb.clip_streets(m)
    st = pb.cut_outlines(m, pb.LAST_STATS.get("ext_segs"))
    return m, st


def test_a_block_the_river_runs_through_is_not_drawn_whole():
    m, st = _cut()
    tiles = m["tiles"]
    straddling = [i for i, t in enumerate(tiles) if t[1] == 2640]
    assert set(straddling) <= set(m["tcut"])                               # every box of the row the band crosses is cut
    assert all(tiles[i][1] != 2000 for i in m["tcut"])                      # the rows far from the water are drawn as ever
    assert len(m["tiles"]) == 5 * 4 and st["tcut"] == len(m["tcut"])        # the array itself stays whole (the fill-in and districts read it)
    assert m["te"] and st["pieces"] == len(m["te"])


def test_no_drawn_piece_enters_the_water_or_its_green_bank_and_each_ends_there():
    m, _ = _cut()
    ends = 0
    for p in m["te"]:
        for i in range(0, len(p), 2):
            assert _slack(m, p[i], p[i + 1]) >= pb.BANK_GAP - 0.6, p
        for x, y in ((p[0], p[1]), (p[-2], p[-1])):
            if _slack(m, x, y) < pb.BANK_GAP + 2:
                ends += 1                                                   # an end at the strip's outer edge
    assert ends >= 8
    for p in m["te"]:
        assert sum(math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1]) for i in range(0, len(p) - 3, 2)) >= 40


def test_a_piece_drawn_where_the_streets_were_tidied_away_is_dropped_too():
    m = _mk()
    m["streets"] = [s for s in m["streets"] if s["n"] != "V1"]               # a street the tidy-up took out (V1 at x = 240)
    pb.clip_streets(m)
    pb.cut_outlines(m)
    for p in m["te"]:
        for i in range(0, len(p) - 3, 2):
            assert not (p[i] == p[i + 2] == 240.0 and abs(p[i + 1] - p[i + 3]) > 40)


def test_loose_edges_polygon_rings_and_polylines_are_cut_the_same_way():
    m, _ = _cut()
    m["edges"] = [[0, 3000, 480, 3000]]                                     # a loose segment under the water
    m["streets"].append({"n": "E", "k": 1, "p": [0, 3000, 480, 3000]})
    m["tq"] = [[240, 2700, 480, 2700, 480, 3300, 240, 3300]]                # a polygon block over it
    m["te"] = [[100, 2700, 100, 3300]]                                      # a loose polyline over it
    pb.cut_outlines(m)
    assert m.get("ecut") == [0] and m.get("qcut") == [0]
    assert [100, 2700, 100, 3300] not in m["te"]
    assert all(_slack(m, p[i], p[i + 1]) >= pb.BANK_GAP - 0.6 for p in m["te"] for i in range(0, len(p), 2))


def test_the_page_skips_what_was_cut_and_the_build_does_the_cutting():
    js = palace.PALACE_JS
    assert "TC[ti]" in js and "EC[ei]" in js and "QC[qi]" in js and "M.tcut" in js
    import inspect
    assert "cut_outlines" in inspect.getsource(palace.set_up)


def test_a_map_without_a_river_is_left_alone():
    m = {"streets": [], "tiles": [[0, 0, 10, 10]], "river": []}
    assert pb.cut_outlines(m)["pieces"] == 0 and "tcut" not in m
