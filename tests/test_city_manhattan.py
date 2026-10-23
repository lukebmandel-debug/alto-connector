"""Manhattan's own layout (build/city_manhattan.py, the NYC preset's Commissioners' Grid; Luke's Direction A, 2026-10-20),
on a small synthetic island: avenues leaning like Manhattan's, numbered streets, a Village and a downtown at their own
angles, a river either side."""
import math

import pytest

from alto.build import city_manhattan as cm
from alto.build import palace_areas, palace_grid

TH = math.radians(29.0)
AVE = 250.0                     # m between avenues
ST = 80.0                       # m between streets
CX, CY = 6000.0, 9000.0
N_TOP = 60


def _real(u, v):
    """The island's own frame (u east across the avenues, v north along them; metres) -> real map px."""
    x, y = u, -v
    c, s = math.cos(TH), math.sin(TH)
    return (CX + x * c - y * s, CY + x * s + y * c)


def _line(name, a, b, k=1, n=8):
    pts = []
    for i in range(n + 1):
        t = i / n
        pts += list(_real(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return {"n": name, "k": k, "p": [round(v, 1) for v in pts]}


def _rot(p, deg, c=(0.0, 0.0)):
    r = math.radians(deg)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r))


@pytest.fixture(scope="module")
def city():
    labels = [a[0] for a in cm.AVENUES]
    W_ = (len(labels) - 1) * AVE
    streets = []
    for k, (label, names, _r) in enumerate(cm.AVENUES):
        u = k * AVE
        streets.append(_line(names[0], (u, 14 * ST if k < cm.SIXTH else 0), (u, N_TOP * ST)))
    for n in range(1, N_TOP + 1):
        u0 = cm.SIXTH * AVE if n < 14 else 0.0
        streets.append(_line("West %d%s Street" % (n, "th"), (u0, n * ST), (W_ / 2, n * ST)))
        streets.append(_line("East %d%s Street" % (n, "th"), (W_ / 2, n * ST), (W_, n * ST)))
    streets.append(_line("West Houston Street", (0, 0), (W_ / 2, 0)))
    streets.append(_line("East Houston Street", (W_ / 2, 0), (W_, 0)))
    # the Village: west of 6th Ave between Houston and 14th St, its streets 30 degrees off the grid
    vc = (cm.SIXTH * AVE / 2, 7 * ST)
    for i in range(-4, 5):
        a, b = _rot((vc[0] + i * 150, vc[1] - 500), -30, vc), _rot((vc[0] + i * 150, vc[1] + 500), -30, vc)
        streets.append(_line("Village Lane %d" % i, a, b))
        a, b = _rot((vc[0] - 700, vc[1] + i * 110), -30, vc), _rot((vc[0] + 700, vc[1] + i * 110), -30, vc)
        streets.append(_line("Village Row %d" % i, a, b))
    # downtown: below Houston St, 8 degrees off
    dc = (W_ / 2, -1500.0)
    for i in range(-9, 10):
        a, b = _rot((dc[0] + i * 220, dc[1] - 1400), -8, dc), _rot((dc[0] + i * 220, dc[1] + 1400), -8, dc)
        streets.append(_line("Down Street %d" % i, a, b))
    for i in range(-8, 9):
        a, b = _rot((dc[0] - 2000, dc[1] + i * 160), -8, dc), _rot((dc[0] + 2000, dc[1] + i * 160), -8, dc)
        streets.append(_line("Down Row %d" % i, a, b))
    streets.append(_line("Broadway", (7.5 * AVE, -3000), (7.5 * AVE, 0)))
    streets.append(_line("Broadway", (7.5 * AVE, 0), (2 * AVE, N_TOP * ST)))
    # water: a wide river either side of the island, from far south to far north
    def band(u0, u1):
        q = [_real(u0, -4000), _real(u1, -4000), _real(u1, N_TOP * ST + 3000), _real(u0, N_TOP * ST + 3000)]
        return [round(v, 1) for p in q for v in p]
    south = [_real(-1500, -4000), _real(W_ + 1500, -4000), _real(W_ + 1500, -3200), _real(-1500, -3200)]
    water = [band(-1500, -120), band(W_ + 120, W_ + 1500), [round(v, 1) for p in south for v in p]]
    m = {"W": 14000, "H": 16000, "bbox": [40.7, -74.02, 40.8, -73.93], "scale": 1.0, "streets": streets, "water": water,
         "landmarks": [], "parks": [], "transit": None, "layout": cm.LAYOUT}
    return m, cm.build(m, majors=["Broadway"], diagonals=["Broadway"])


def test_the_grid_is_the_avenues_by_every_street(city):
    _m, g = city
    assert g["engine"]["path"] == cm.LAYOUT
    assert g["cols"] == [a[0] for a in cm.AVENUES]                     # only the avenues, west to east: no downtown street
    assert g["rows"][-1] == "Houston Street" and g["rows"][0] == "%dth Street" % N_TOP


def test_every_root_block_is_the_same_long_block(city):
    _m, g = city
    sizes = {(round(t[2] - t[0]), round(t[3] - t[1])) for t in g["tiles"]}
    assert sizes == {(cm.CWM, cm.CHM)} and abs(cm.CWM / cm.CHM - 2.6) < .01


def test_the_village_and_downtown_are_their_own_grids_at_their_own_angles(city):
    _m, g = city
    a = {d["id"]: d["a"] for d in g["doms"]}
    assert set(a) == {0, 1, 2} and a[0] == 0
    assert abs(abs(a[1]) - 30) < 3 and abs(abs(a[2]) - 8) < 3 and a[1] * a[2] > 0     # (the synthetic turns them the same way)
    assert all(d["clip"] for d in g["doms"] if d["id"])                 # the children are clipped, the root is not


def test_the_water_is_one_body_and_nothing_lies_north_of_the_box(city):
    _m, g = city
    top = min(t[1] for t in g["tiles"])
    sea = g["sea"][0]
    assert len(g["sea"]) == 1 and min(sea[1::2]) >= top - cm.CHM
    assert all(r["ch"] == 1 for r in g["river"]) and {r["n"] for r in g["river"]} == {"Hudson River", "East River"}
    assert g["land"] and g.get("ghost") and {f["n"] for f in g["far"]} == {"New Jersey", "Brooklyn", "Queens"}


def test_broadway_is_one_diagonal_meeting_downtowns_broadway_at_houston(city):
    _m, g = city
    bw = [s for s in g["streets"] if s["n"] == "Broadway"]
    yH = max(t[3] for t in g["tiles"])
    assert any(s.get("L") and abs(s["p"][-1] - yH) < 1 for s in bw)


def test_a_far_bank_name_is_dropped_and_the_boroughs_are_named(city):
    _m, g = city
    g = dict(g, bbox=[40.7, -74.02, 40.8, -73.93])
    out = palace_areas.layout(g, [{"name": "Out West", "lat": 40.75, "lon": -74.019}], [])
    names = [a["n"] for a in out]
    assert "Out West" not in names and {"New Jersey", "Brooklyn", "Queens"} <= set(names)


def test_grid_takes_the_layout_and_falls_back_when_it_cannot_read_the_box(city):
    m, _g = city
    assert palace_grid.grid(dict(m))["engine"]["path"] == cm.LAYOUT
    bad = dict(m, streets=[s for s in m["streets"] if "Houston" not in s["n"]])
    assert palace_grid.grid(bad).get("engine", {}).get("path") != cm.LAYOUT


def test_the_ghost_page_code_is_spliced_in_only_for_a_map_that_has_it():
    from alto.build.palace import PALACE_JS
    from alto.build.palace_manhattan_js import patch_js, ANCHOR
    assert ANCHOR in PALACE_JS and "M.ghost" not in PALACE_JS
    assert "M.ghost" in patch_js(PALACE_JS)


def test_only_manhattans_fill_gets_the_bigger_budget():
    from alto.build import palace_fillin as pf
    assert pf.BUDGET_MANHATTAN > pf.BUDGET_CHARS == 118_000


def test_downtown_runs_on_to_the_tip_and_a_park_there_is_drawn(city):
    # Luke, 2026-10-22: "I feel like Battery Park is missing": no street crosses it, so the even spread squeezed it into the
    # half-block margin; unnamed rows carry downtown on to the tip, and Battery Park is drawn whatever its size
    m, _g = city
    W_ = (len(cm.AVENUES) - 1) * AVE
    q = [_real(W_ / 2 - 300, -3150), _real(W_ / 2 + 300, -3150), _real(W_ / 2 + 300, -2850), _real(W_ / 2 - 300, -2850)]
    pk = {"n": "Battery Park", "r": [[round(v, 1) for p in q for v in p]]}
    g = cm.build(dict(m, parks=[pk]), majors=["Broadway"], diagonals=["Broadway"])
    bp = [p for p in g["parks"] if p["n"] == "Battery Park"]
    assert bp and sum((i1 - i0) * (j1 - j0) for i0, j0, i1, j1 in bp[0]["c"]) >= 4
    assert "Battery Park" in cm.PARKS


def _outer_stub(sea=lambda x, y: False):
    from alto.build import city_boroughs as cb
    o = object.__new__(cb.Outer)
    o.P1 = lambda lat, lon: ((lon + 74.3) * 84000.0, (41.0 - lat) * 111000.0)
    o.is_sea = sea
    o.city = lambda x, y: x < 30000
    o.detailed = lambda x, y: 20000 <= x < 22000
    o.aff = lambda x, y: (x, y)
    o._field = lambda x, y: (0.0, 0.0)
    o.o = (0.0, 0.0)
    o.boros, o.places = {}, []
    return o


def test_the_five_boroughs_name_their_water_islands_and_famous_neighbourhoods_first():
    from alto.build import city_boroughs as cb
    gi = next(l_ for l_ in cb.LABELS if l_[0] == "Governors Island")
    o = _outer_stub()
    wet = {o.P1(l_[1], l_[2]) for l_ in cb.LABELS if "w" in l_[4]}
    o.is_sea = lambda x, y: (x, y) in wet
    gx, gy = o.P1(gi[1], gi[2])
    o.places = [("Nolan Park", "neighbourhood", gx + 200, gy), ("Obscure Corner", "neighbourhood", 1000.0, 1000.0),
                ("Park Slope", "neighbourhood", 1500.0, 1000.0)]
    out = o.names_page(man=lambda x, y: (-x, -y))
    by = {f["n"]: f for f in out}
    assert "Nolan Park" not in by and by["Governors Island"]["r"] == 2               # an island is named as the island
    assert by["Upper New York Bay"]["k"] == "w" and by["New Jersey"]["k"] == "b"
    assert by["Manhattan"]["k"] == "b" and by["Manhattan"]["x"] < 0                   # Manhattan's names by its own mapping
    assert "Park Slope" in by and "Obscure Corner" not in by                          # the famous one wins the spot


def test_a_bridge_reaches_the_island_and_new_jerseys_overpasses_stay_out():
    o = _outer_stub()
    o.roads = [(("Brooklyn Bridge", 1, 1), [(21000.0, 0.0), (23000.0, 0.0), (25000.0, 0.0)]),
               (("NJ Overpass", 2, 1), [(31000.0, 0.0), (32000.0, 0.0)])]
    out = dict(o.roads_page(man=lambda x, y: (x, y + 1)))
    br = out[("Brooklyn Bridge", 1, 1)]
    assert br[0] == (21000.0, 1.0) and br[-1] == (25000.0, 0.0)                      # from the lattice to the far bank
    assert ("NJ Overpass", 2, 1) not in out


def test_the_five_boroughs_names_page_code_is_spliced_in_only_for_manhattans_layout():
    from alto.build.palace import PALACE_JS
    from alto.build.palace_manhattan_js import patch_labels
    assert "pl-nyc-css" not in PALACE_JS and "pl-nyc-css" in patch_labels(PALACE_JS)


def test_manhattans_fill_buildings_are_boxes_square_to_their_block():
    # Luke, 2026-10-22: "in NYC background buildings look really weird": a footprint carried through an angled grid's frame
    # came out a slanted sliver; it is drawn as Philadelphia's are, a box square to its block, as big as the footprint
    from alto.build import palace_fillin as pf
    sheared = [(0, 0), (100, 30), (100, 90), (0, 60)]                            # a parallelogram, 6000 px2
    g = pf._boxed(sheared, 50, 45, 0, 0, 390, 150)
    xs, ys = {p[0] for p in g}, {p[1] for p in g}
    assert len(g) == 4 and len(xs) == 2 and len(ys) == 2                         # square to the block
    assert abs((max(xs) - min(xs)) * (max(ys) - min(ys)) - 6000) < 1             # the footprint's own area
    g = pf._boxed(sheared, 385, 145, 0, 0, 390, 150)                              # moved inside the block, never cut
    assert max(p[0] for p in g) <= 390 and max(p[1] for p in g) <= 150
    assert pf._boxed([(0, 0), (2, 0), (2, 2), (0, 2)], 1, 1, 0, 0, 390, 150) is None    # a speck


def test_manhattans_glass_is_not_painted_over_so_the_fill_canvas_shows():
    from alto.build.palace import PALACE_JS
    from alto.build.palace_manhattan_js import patch_labels, ANCHOR
    js = patch_labels(PALACE_JS)
    assert ANCHOR in PALACE_JS and "M.layout!=='manhattan'" in js and "M.layout!=='manhattan'" not in PALACE_JS
    assert "pl-land-top" not in PALACE_JS.split("/* ── parks:")[1].split("/* ── /parks")[0]   # the land is cut out of the water, not laid over it
