"""City engine v2: orientation field and modes (alto/build/city_field.py)."""
import math
import time

import pytest

import city_synth as cs
from alto.build import city_field as cf


def test_lattice_angle_helpers():
    assert cf.lat_dist(1, 89) == pytest.approx(2)
    assert cf.lat_dist(10, 55) == pytest.approx(45)
    assert cf.lat_dist(-5, 85) == pytest.approx(0)
    assert cf.wrap45(85) == pytest.approx(-5)
    assert cf.wrap45(45) == pytest.approx(45)
    assert cf.wrap45(46.5) == pytest.approx(-43.5)
    # both families of one grid have the same lattice angle
    assert cf.seg_angle(0, 0, 10, 0) == pytest.approx(cf.seg_angle(0, 0, 0, 10))


def test_empty_map_has_no_modes():
    f = cf.field(cs.city(2000, 2000, []))
    assert f.modes == [] and f.nx == 11 and f.ny == 11
    assert all(v is None for row in cf.labels(f) for v in row)


def test_one_tilted_grid_gives_one_mode():
    m = cs.city(4000, 4000, cs.grid((0, 0, 4000, 4000), 27.7))
    f = cf.field(m)
    assert len(f.modes) == 1
    assert cf.lat_dist(f.modes[0], 27.7) < 0.5
    lab = cf.labels(f)
    assert sum(v == 0 for row in lab for v in row) > 0.8 * f.nx * f.ny


def test_two_grids_give_two_modes_and_split_labels():
    m = cs.city(8000, 4000, cs.grid((0, 0, 4000, 4000), 9.0) + cs.grid((4000, 0, 8000, 4000), 46.5, name="H"))
    f = cf.field(m)
    assert len(f.modes) == 2
    got = sorted(f.modes)
    assert abs(got[0] - 9.0) < 1 and abs(got[1] - 46.5) < 1
    lab = cf.labels(f)
    i9 = min(range(2), key=lambda i: cf.lat_dist(f.modes[i], 9))
    # the far left column is the 9 degree grid, the far right column the other one
    assert all(lab[y][1] == i9 for y in range(3, f.ny - 3))
    assert all(lab[y][f.nx - 2] == 1 - i9 for y in range(3, f.ny - 3))


def test_irregular_streets_are_incoherent():
    m = cs.city(3000, 3000, cs.irregular((0, 0, 3000, 3000), n=900))
    f = cf.field(m)
    cells = [(x, y) for y in range(f.ny) for x in range(f.nx) if f.ang[y][x] is not None]
    assert cells
    assert sum(f.coh[y][x] < cf.COH for x, y in cells) > .8 * len(cells)


EXPECT = {                      # city: (lattice angle of the strongest mode, degrees mod 90)
    "philadelphia": 9.3,
    "manhattan": 28.5,
    "washington": 0.0,
    "barcelona": 45.0,
    "chicago": 0.0,
}


@pytest.mark.parametrize("city", sorted(EXPECT))
def test_fixture_city_main_mode(city):
    m = cs.load_city(city)
    if m is None:
        pytest.skip("no fixture for %s" % city)
    f = cf.field(m)
    assert f.modes, city
    assert cf.lat_dist(f.modes[0], EXPECT[city]) <= 2.0, (city, f.modes)


def test_philadelphia_modes_and_speed():
    m = cs.load_city("philadelphia")
    if m is None:
        pytest.skip("no Philadelphia fixture")
    t = time.time()
    f = cf.field(m)
    assert time.time() - t < 3.0
    # design 1.4: 9.3 (main), 55.8 (NE, about 45 off), 46.8 (SW, 37.5 off), 85.0 (West/NW, -14 off)
    for want in (9.3, 55.8, 46.8, 85.0):
        assert min(cf.lat_dist(want, mo) for mo in f.modes) <= 2.0, (want, f.modes)
    assert cf.lat_dist(f.modes[0], 9.3) <= 1.0
    assert math.isclose(sum(f.shares), sum(f.shares))  # shares are numbers
