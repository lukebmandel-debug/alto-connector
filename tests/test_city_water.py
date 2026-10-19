"""The water between a far-bank city and the land across it (build/city_water.py): islands come to the band's gap off
the root across real water only, and the bands are one smooth river of one width along the gap's midline."""
import math
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import city_presets, city_water as cw  # noqa: E402
from alto import palace_map as pm  # noqa: E402
from alto.build.palace_river import STEP  # noqa: E402

BLK = 240.0


class _Map:
    """A domain mapping stub: local lattice px -> page px by a shift."""

    def __init__(self, o, gv=BLK, gh=170.0):
        self.o = o
        self.loc = SimpleNamespace(gv=gv, gh=gh)

    def page(self, lx, ly):
        return (lx + self.o[0], ly + self.o[1])

    def __call__(self, x, y):                  # real px -> page px (the stubs' real px are their page px)
        return self.page(x, y)


def _lay(offsets, nx=6, ny=30):
    lay = SimpleNamespace(maps={}, rect={})
    for did, o in offsets.items():
        lay.maps[did] = _Map(o)
        lay.rect[did] = [0.0, 0.0, nx * BLK, ny * 170.0]
    return lay


def _doms(*ids):
    return {i: SimpleNamespace(id=i) for i in ids}


def _real(loc, lx, ly):                    # real px = local px (the stub maps are rigid)
    return (lx, ly)


def _water_between(x0, x1, y0=-500.0, y1=6000.0):
    """A big water ring in REAL px between two lattices that sit side by side in real px."""
    return [x0, y0, x1, y0, x1, y1, x0, y1]


def _case(gap_page, water=True, island_at=None):
    """A root lattice at x 0..1440 and an island `gap_page` px to its east; real px = page px before the move."""
    root_o, isl_o = (0.0, 0.0), (1440.0 + gap_page, 0.0)
    lay = _lay({0: root_o, 1: isl_o})
    # real positions follow the page ones, so the water polygon lies in the gap
    m = {"water": [_water_between(1440.0, 1440.0 + gap_page)] if water else []}

    def in_real(d, rx, ry):
        return True

    def unlocal(loc, lx, ly):
        # the island's real px are its page px (it was placed there); the root's likewise
        return (lx + (isl_o[0] if loc is lay.maps[1].loc else 0.0), ly)
    return lay, m, in_real, unlocal


def test_island_across_water_comes_to_the_target_gap():
    lay, m, in_real, unlocal = _case(6000.0)
    rep, fp = cw.compact(lay, _doms(0, 1), 0, [], m, in_real, unlocal, BLK)
    assert len(rep) == 1 and rep[0]["river"] and rep[0]["shift"] is not None
    root_x = max(c[0][0] for c in fp[0])
    isl_x = min(c[0][0] for c in fp[1])
    assert rep[0]["w"] == cw.MAX_W                       # 6000 px of real water: as wide as a band gets
    assert abs((isl_x - root_x) - (rep[0]["w"] + 2 * cw.MARGIN + 2 * cw.CELL_HALF)) < 1.0
    assert lay.maps[1].o[0] < 1440.0 + 6000.0           # moved west, toward the root
    assert abs(lay.maps[1].o[1]) < 1e-6                 # and only along the line between them


def test_island_on_land_is_not_moved():
    lay, m, in_real, unlocal = _case(6000.0, water=False)
    before = lay.maps[1].o
    rep, _ = cw.compact(lay, _doms(0, 1), 0, [], m, in_real, unlocal, BLK)
    assert rep[0]["shift"] is None and not rep[0]["river"]
    assert lay.maps[1].o == before


def test_island_already_at_the_gap_stays():
    lay, m, in_real, unlocal = _case(600.0)            # 600 px of water: the cells are about a band (600) + margins apart already
    rep, _ = cw.compact(lay, _doms(0, 1), 0, [], m, in_real, unlocal, BLK)
    assert rep[0]["shift"] is None or max(abs(v) for v in rep[0]["shift"]) < 0.1 * cw.TARGET


def test_seam_joined_domain_is_no_island():
    lay, m, in_real, unlocal = _case(6000.0)
    seam = SimpleNamespace(a=0, b=1)
    rep, fp = cw.compact(lay, _doms(0, 1), 0, [seam], m, in_real, unlocal, BLK)
    assert rep == [] and fp == {}


def test_channels_is_one_smooth_band_of_one_width_run_off_the_glass():
    lay, m, in_real, unlocal = _case(6000.0)
    rep, fp = cw.compact(lay, _doms(0, 1), 0, [], m, in_real, unlocal, BLK)
    bands = cw.channels(m, 0, fp, rep, (0.0, 0.0), 9000.0, [])
    assert len(bands) == 1
    b = bands[0]
    assert b["w"] == rep[0]["w"] == cw.MAX_W and b["n"] == "" and b["ch"] == 1
    q = b["_q"]
    ys = [p[1] for p in q]
    # between the two shores' cells, a straight vertical course here, and carried well past both ends of the land
    root_x = max(c[0][0] for c in fp[0])
    isl_x = min(c[0][0] for c in fp[1])
    mid = (root_x + isl_x) / 2
    inside = [p for p in q if 0 <= p[1] <= 5000]
    assert inside and all(abs(p[0] - mid) < 40 for p in inside)
    assert max(ys) - min(ys) > 9000                      # run off the ends
    steps = [math.dist(a, c) for a, c in zip(q, q[1:])]
    assert max(steps) < 2 * STEP and min(steps) > 0
    assert b["p"][:2] == [round(q[0][0], 1), round(q[0][1], 1)]


def test_a_band_is_named_by_the_nearest_river_point():
    lay, m, in_real, unlocal = _case(6000.0)
    rep, fp = cw.compact(lay, _doms(0, 1), 0, [], m, in_real, unlocal, BLK)
    # real px of the root's shore cells are their page px: the gap's west edge is x ~ 1440
    hints = [{"n": "East River", "x": 1500.0, "y": 2000.0}, {"n": "Elsewhere", "x": 90000.0, "y": 0.0}]
    assert cw.channels(m, 0, fp, rep, (0.0, 0.0), 9000.0, hints)[0]["n"] == "East River"
    far = [{"n": "Elsewhere", "x": 90000.0, "y": 0.0}]
    assert cw.channels(m, 0, fp, rep, (0.0, 0.0), 9000.0, far)[0]["n"] == ""


def test_wet_line_reads_only_big_water():
    big = [0, 0, 4000, 0, 4000, 4000, 0, 4000]
    pond = [5000, 5000, 5100, 5000, 5100, 5100, 5000, 5100]
    m = {"water": [big, pond]}
    assert cw.wet_line(m, [(100, 100), (200, 300), (3000, 3000)])
    assert not cw.wet_line(m, [(5050, 5050), (6000, 6000)])           # a pond is not the river
    assert not cw.wet_line({"water": []}, [(1, 1)])


def test_the_far_bank_flag_is_set_only_when_far_banks_are_kept():
    raw = {"elements": []}
    bbox = (40.7, -74.0, 40.71, -73.99)
    assert "far_bank" not in pm.build_map(raw, bbox, place="x")
    old = pm.FAR_BANK_SHARE
    try:
        pm.FAR_BANK_SHARE = -1.0
        assert pm.build_map(raw, bbox, place="x").get("far_bank") is True
    finally:
        pm.FAR_BANK_SHARE = old


def test_the_nyc_preset_names_its_two_rivers_from_points_beside_its_shores():
    pre = city_presets.get("New York City")
    assert pre["far_bank"] is True
    names = {n for n, _la, _lo in pre["river_names"]}
    assert names == {"Hudson River", "East River"}
    assert all(40.69 <= la <= 40.81 and -74.03 <= lo <= -73.92 for _n, la, lo in pre["river_names"])      # Manhattan's waters, the widened box included
    hs = cw.hints_of({"place": "New York City", "bbox": pre["bbox"], "scale": 1.0})
    assert len(hs) == len(pre["river_names"]) and all(h["x"] >= 0 for h in hs)
    assert cw.hints_of({"place": "Nowhere At All", "bbox": pre["bbox"]}) == []


# ── the open water ──────────────────────────────────────────────────────────
def _inside(rings, x, y):
    """Even-odd over all the rings (the page fills them as one path)."""
    n = 0
    for r in rings:
        c = False
        k = len(r) // 2
        for i in range(k):
            x0, y0, x1, y1 = r[2 * i], r[2 * i + 1], r[2 * ((i + 1) % k)], r[2 * ((i + 1) % k) + 1]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
        n += c
    return n % 2 == 1


def _bands_g():
    """Two bands down a 6000 x 9000 page, an island of blocks between them standing from y 600 to 5400."""
    def band(x):
        return {"n": "", "w": 230, "p": [v for y in range(-500, 9500, 40) for v in (float(x), float(y))]}
    tiles = [[x, y, x + 240, y + 170] for x in range(1500, 4200, 240) for y in range(600, 5400, 170)]
    return {"W": 6000, "H": 9000, "river": [band(900), band(5100)], "tiles": tiles, "streets": [], "parks": []}


def test_the_water_between_the_bands_is_filled_and_the_land_stays_dry():
    rings = cw.sea(_bands_g(), [])
    assert rings and all(len(r) >= 6 for r in rings)
    assert _inside(rings, 1100, 3000) and _inside(rings, 4600, 7600)           # beside the island, and south of it: harbour
    assert not _inside(rings, 2800, 3000)                                       # the island's blocks
    assert not _inside(rings, 300, 3000) and not _inside(rings, 5700, 3000)      # the land beyond each band
    assert _inside(rings, 900, 3000)                                            # a band's own course is water (it runs out into it)


def test_nothing_past_the_box_edge_is_sea():
    rings = cw.sea(_bands_g(), [], outside=lambda x, y: y < 600)                 # Manhattan goes on north of the box
    assert _inside(rings, 1100, 3000) and not _inside(rings, 3000, 300)           # no sea north of the edge between the bands ...
    assert _inside(rings, 900, 300)                                                # ... but each river runs on as a river


def test_a_free_domain_outline_is_land_too():
    ring = [(2000, 6200), (4000, 6200), (4000, 7800), (2000, 7800)]
    rings = cw.sea(_bands_g(), [ring])
    assert _inside(rings, 2000, 5800) and not _inside(rings, 3000, 7000)


def test_fewer_than_two_bands_draw_no_open_water():
    g = _bands_g()
    g["river"] = g["river"][:1]
    assert cw.sea(g, []) == []
