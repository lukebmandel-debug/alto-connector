"""Parks kept on dry land (build/palace_parkfit.py; Luke, 2026-10-22: "There are parks going into the water, make parks
accurate"): a park reaching the water the page draws is fitted again to its own outline less that water and a beach."""
from alto.build import palace_parkfit as pf
from alto.build.palace_parks import shape


def _sq(x0, y0, x1, y1):
    return [x0, y0, x1, y0, x1, y1, x0, y1]


SEA = {"sea": [_sq(1000, -500, 3000, 2500)], "land": [], "river": []}       # the water: everything east of x = 1000


def _xs(rings):
    return [v for r in rings for v in r[0::2]]


def test_a_park_half_in_the_sea_keeps_only_its_dry_half_and_a_beach():
    out = pf.fit([_sq(0, 0, 2000, 1000)], pf.Water(SEA))
    assert out and max(_xs(out)) <= 1000 - pf.MARGIN + pf.STEP          # nothing past the shore less the beach
    assert min(_xs(out)) <= pf.STEP                                      # the dry part is all there
    assert not any(pf.inside(out, x, 500) for x in range(1001, 2000, 50))


def test_a_dry_park_is_drawn_exactly_as_before():
    assert pf.fit([_sq(0, 0, 800, 600)], pf.Water(SEA)) is None
    assert pf.fit([_sq(0, 0, 800, 600)], pf.Water({"sea": [], "land": [], "river": []})) is None


def test_land_laid_over_the_water_is_dry_and_a_river_band_is_wet():
    island = dict(SEA, land=[_sq(1400, 200, 2600, 800)])
    out = pf.fit([_sq(1500, 300, 2500, 700)], pf.Water(island))     # a park on an island in the sea stays as it is
    assert out is None
    band = {"sea": [], "land": [], "river": [{"n": "R", "w": 200, "p": [500, -1000, 500, 3000]}]}
    out = pf.fit([_sq(0, 0, 1000, 800)], pf.Water(band))            # a park across the river: both banks, none in it
    assert out and len(out) == 2 and not any(pf.inside(out, 500, y) for y in range(50, 800, 100))


def test_shape_takes_the_water_and_keeps_walkways_plazas_and_the_name_on_the_green():
    xg, yg = [0, 400, 800, 1200], [0, 300, 600]
    raw = [{"n": "Shore Park", "c": [[0, 0, 3, 2]]}]
    water = pf.Water({"sea": [_sq(900, -500, 3000, 1500)], "land": [], "river": []})
    before, = shape(raw, xg, yg)
    after, = shape(raw, xg, yg, water=water)
    assert max(_xs(before["r"])) > 900 and max(_xs(after["r"])) < 900
    assert all(pf.inside(after["r"], o[0], o[1]) for o in after["o"])
    assert after["t"][0] < 900 and pf.inside(after["r"], *after["t"])
    assert all(x < 900 for p in after["p"] for x in p[0::2])
