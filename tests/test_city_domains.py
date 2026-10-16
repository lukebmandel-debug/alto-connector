"""City engine v2: domain detection, ownership, seam candidates (alto/build/city_domains.py)."""
import math
import time

import pytest

import city_synth as cs
from alto.build import city_domains as cd
from alto.build import city_field as cf
from alto.build.city_types import Domain, Seam


def _deg(d):
    return math.degrees(d.theta)


def _rel(d, root):
    return (_deg(d) - _deg(root) + 45) % 90 - 45


def _centre(d):
    xs = [p[0] for p in d.poly]
    ys = [p[1] for p in d.poly]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _total(streets):
    tot = 0.0
    for s in streets:
        p = s["p"]
        tot += sum(math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1]) for i in range(0, len(p) - 3, 2))
    return tot


def _check_contract(m, det):
    doms = det.domains
    assert doms and all(isinstance(d, Domain) for d in doms)
    assert [d.id for d in doms] == list(range(len(doms)))
    grids = [d for d in doms if d.kind == "grid"]
    if grids:                                  # the root is the largest grid domain (a free-only city has none)
        assert doms[0] is grids[0] and all(doms[0].area >= d.area for d in grids)
    for d in doms:
        assert d.kind in ("grid", "free")
        assert -math.pi / 4 - 1e-9 < d.theta <= math.pi / 4 + 1e-9
        assert len(d.poly) >= 3 and abs(cd.ring_area(d.poly)) > 0
        for s in d.streets:
            assert 0 <= s["id"] < len(m["streets"]) and len(s["p"]) >= 4
            assert s.get("n") == m["streets"][s["id"]].get("n")
    assert all(isinstance(s, Seam) for s in det.seams)
    # every metre of street is owned by exactly one domain (or left unowned)
    owned = sum(_total(d.streets) for d in doms) + _total(det.unowned)
    assert owned == pytest.approx(_total(m["streets"]), rel=1e-4)


# ------------------------------------------------------------------------------------------------ synthetic

def test_two_grids_two_domains_and_the_hinge_street_switches_at_its_bend():
    streets = cs.grid((0, 0, 4000, 4000), 9.0) + cs.grid((4000, 0, 8000, 4000), 46.5, name="H")
    # a street that runs along the left grid to the boundary and bends onto the right grid's axis there
    t9, t46 = math.radians(9), math.radians(46.5)
    bend = (4000.0, 1500 + 2500 * math.tan(t9))
    end = (bend[0] + 1500 * math.cos(t46), bend[1] + 1500 * math.sin(t46))
    streets.append({"n": "Hinge St", "k": 3, "p": [1500, 1500, round(bend[0], 1), round(bend[1], 1),
                                                  round(end[0], 1), round(end[1], 1)]})
    m = cs.city(8000, 4000, streets)
    det = cd.detect(m)
    _check_contract(m, det)
    grids = [d for d in det.domains if d.kind == "grid"]
    assert len(grids) == 2
    angs = sorted(cf.wrap45(_deg(d)) for d in grids)
    assert angs[0] == pytest.approx(-43.5, abs=0.5) and angs[1] == pytest.approx(9.0, abs=0.5)
    left = min(grids, key=lambda d: _centre(d)[0])
    right = max(grids, key=lambda d: _centre(d)[0])
    assert _centre(left)[0] < 3000 < 5000 < _centre(right)[0]
    hl = [s for s in left.streets if s["n"] == "Hinge St"]
    hr = [s for s in right.streets if s["n"] == "Hinge St"]
    assert len(hl) == 1 and len(hr) == 1
    assert math.dist(hl[0]["p"][-2:], bend) < 1 and math.dist(hr[0]["p"][:2], bend) < 1
    seam = next(s for s in det.seams if {s.a, s.b} == {left.id, right.id})
    assert seam.kind == "grid" and len(seam.real) >= 2
    assert any(n == "Hinge St" for n, _ in seam.bends)
    # the boundary runs north-south near x = 4000
    assert all(abs(x - 4000) <= 400 for x, _ in seam.real)


def test_water_splits_one_angle_into_two_domains():
    streets = cs.grid((0, 0, 3850, 4000), 10.0) + cs.grid((4150, 0, 8000, 4000), 10.0, name="E")
    water = [[3850, -10, 4150, -10, 4150, 4010, 3850, 4010, 3850, -10]]
    m = cs.city(8000, 4000, streets, water=water, rivers=[{"n": "River", "p": [4000, 0, 4000, 4000]}])
    det = cd.detect(m)
    _check_contract(m, det)
    grids = [d for d in det.domains if d.kind == "grid"]
    assert len(grids) == 2
    assert all(abs(_deg(d) - 10) < .5 for d in grids)
    assert [n for n, _, _ in det.rivers] == ["River"]
    assert (0, 1) in det.across
    for d in grids:                       # no domain reaches across the river
        xs = [p[0] for p in d.poly]
        assert max(xs) <= 4000 or min(xs) >= 4000
    assert any(s.b == "water" and s.kind == "water" for s in det.seams)


def test_a_narrow_creek_does_not_split():
    streets = cs.grid((0, 0, 8000, 4000), 10.0)
    water = [[3985, -10, 4015, -10, 4015, 4010, 3985, 4010, 3985, -10]]       # 30 m wide
    m = cs.city(8000, 4000, streets, water=water, rivers=[{"n": "Creek", "p": [4000, 0, 4000, 4000]}])
    det = cd.detect(m)
    assert len([d for d in det.domains if d.kind == "grid"]) == 1 and det.rivers == []


def test_a_small_tilted_patch_joins_its_neighbour():
    # 600 x 600 m (0.36 km2) of a 40 degree grid inside a 9 degree city: too small to matter (R2)
    streets = cs.grid((0, 0, 6000, 6000), 9.0)
    streets = [s for s in streets if not all(2700 <= v <= 3300 for v in s["p"])]
    streets += cs.grid((2700, 2700, 3300, 3300), 40.0, name="T")
    m = cs.city(6000, 6000, streets)
    doms = cd.domains(m)
    assert len(doms) == 1 and doms[0].kind == "grid" and abs(_deg(doms[0]) - 9) < 1


def test_an_irregular_old_town_is_a_free_domain():
    streets = cs.grid((0, 0, 4000, 4000), 0.0) + cs.irregular((4000, 0, 6500, 4000), n=1400)
    m = cs.city(6500, 4000, streets)
    det = cd.detect(m)
    _check_contract(m, det)
    kinds = sorted(d.kind for d in det.domains)
    assert kinds == ["free", "grid"]
    free = next(d for d in det.domains if d.kind == "free")
    assert _centre(free)[0] > 4500 and free.area >= 4
    s = next(s for s in det.seams if s.kind == "free")
    assert {s.a, s.b} == {0, free.id}


def test_describe_lists_every_domain():
    m = cs.city(8000, 4000, cs.grid((0, 0, 4000, 4000), 9.0) + cs.grid((4000, 0, 8000, 4000), 46.5, name="H"))
    det = cd.detect(m)
    txt = cd.describe(det.domains, m, det.seams)
    lines = txt.splitlines()
    assert lines[0].startswith("A #0") and lines[2].startswith("B #1")
    assert any(l.startswith("seam A|B") for l in lines)
    assert any(set(l.strip()) <= {"A", "B", "."} and "A" in l and "B" in l for l in lines)


# ------------------------------------------------------------------------------------------------ real cities

def _city(name):
    m = cs.load_city(name)
    if m is None:
        pytest.skip("no fixture for %s" % name)
    return m


def test_philadelphia_domains():
    m = _city("philadelphia")
    t = time.time()
    det = cd.detect(m)
    assert time.time() - t < 5.0
    _check_contract(m, det)
    doms = det.domains
    A = doms[0]
    assert A.kind == "grid" and abs(_deg(A) - 9.3) < 1.0 and A.area > 45
    grids = [d for d in doms if d.kind == "grid" and d.area >= 5]
    W, H = m["W"], m["H"]

    def find(lo, hi, where):
        c = [d for d in grids if lo <= _rel(d, A) <= hi and where(*_centre(d))]
        assert c, (lo, hi, [(round(_rel(d, A), 1), _centre(d)) for d in grids])
        return c[0]
    sw = find(35, 41, lambda x, y: x < W * .4 and y > H * .45)            # Southwest, below Baltimore Ave
    ne = find(-47, -41, lambda x, y: x > W * .6 and y < H * .45)         # Kensington / Port Richmond
    nw = find(-19, -12, lambda x, y: x < W * .45 and y < H * .5)         # West / NW (Haverford Ave fan)
    west = find(-1.5, 1.5, lambda x, y: x < W * .45)                     # A's angle across the Schuylkill
    assert west is not A and (A.id, west.id) in det.across
    assert 8 <= sw.area <= 15 and 8 <= ne.area <= 15 and 5 <= nw.area <= 12
    frees = [d for d in doms if d.kind == "free"]
    assert any(_centre(d)[0] < W * .35 and _centre(d)[1] < H * .3 for d in frees)      # Wissahickon
    assert any(_centre(d)[0] < W * .3 and _centre(d)[1] > H * .65 for d in frees)      # Eastwick
    # seams: Baltimore Ave between the west bank and the Southwest, Kensington Ave between A and the NE
    s_balt = next(s for s in det.seams if {s.a, s.b} == {west.id, sw.id})
    assert s_balt.avenue == "Baltimore Avenue" and s_balt.hinges >= 6 and s_balt.rms < 30
    assert ((s_balt.angle - _deg(A) + 90) % 180 - 90) == pytest.approx(-17.6, abs=3)
    s_kens = next(s for s in det.seams if {s.a, s.b} == {A.id, ne.id})
    assert s_kens.avenue == "Kensington Avenue" and s_kens.hinges >= 6
    assert ((s_kens.angle - _deg(A) + 90) % 180 - 90) == pytest.approx(-44.8, abs=2)


def test_manhattan_main_grid_and_free_lower_manhattan():
    m = _city("manhattan")
    det = cd.detect(m)
    _check_contract(m, det)
    A = det.domains[0]
    assert 28 <= _deg(A) <= 30 and A.area >= 15
    big = [d for d in det.domains if d.kind == "grid" and d.area >= 3]
    assert big == [A]                                   # one grid on the island (the Village is a small one)
    low = [d for d in det.domains if d.kind == "free" and _centre(d)[1] > m["H"] * .7]
    assert low and sum(d.area for d in low) >= 1.5


def test_washington_is_one_grid_and_its_diagonals_are_not_a_district():
    m = _city("washington")
    det = cd.detect(m)
    _check_contract(m, det)
    grids = [d for d in det.domains if d.kind == "grid"]
    assert len(grids) == 1 and abs(_deg(grids[0])) < 2
    assert grids[0].share > .9


def test_barcelona_eixample_at_45_and_a_free_old_town():
    m = _city("barcelona")
    det = cd.detect(m)
    _check_contract(m, det)
    A = det.domains[0]
    assert abs(abs(_deg(A)) - 45) < 2.5 and A.area > 15
    old = [d for d in det.domains if d.kind == "free" and _centre(d)[1] > m["H"] * .6]
    assert old and old[0].area >= 2


def test_chicago_one_angle_split_only_by_the_river():
    m = _city("chicago")
    det = cd.detect(m)
    _check_contract(m, det)
    grids = [d for d in det.domains if d.kind == "grid"]
    assert all(abs(_deg(d)) < 3 for d in grids)
    assert not [d for d in det.domains if d.kind == "free"]
    assert len(grids) >= 2 and det.across and det.rivers


def _free_share(det):
    tot = sum(d.area for d in det.domains) or 1
    return sum(d.area for d in det.domains if d.kind == "free") / tot


def test_paris_is_mostly_free_with_small_grid_patches():
    m = _city("paris")
    det = cd.detect(m)
    _check_contract(m, det)
    assert _free_share(det) >= .6
    assert all(d.area < 8 for d in det.domains if d.kind == "grid")
    assert any("Seine" in n for n, _, _ in det.rivers)


def test_london_is_free():
    m = _city("london")
    det = cd.detect(m)
    _check_contract(m, det)
    assert _free_share(det) >= .8
