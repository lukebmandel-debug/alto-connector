"""New York's other boroughs at full detail (city_outer_lattice.py): grids fitted in place, blocks as faces of the street lattice,
the buildings on them; tunnels and ferries (palace_crossings.py); the boroughs' landmark art (palace_skyline)."""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import city_outer_lattice as col, palace, palace_crossings, palace_skyline  # noqa: E402


def _grid_map(nu=12, nv=10, pu=240.0, pv=90.0, deg=20.0, skip_row=None):
    """A real map of one tilted grid: nu avenues pu apart (named "N Avenue") crossing nv streets pv apart ("N Street")."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)

    def P(u, v):
        return (round(2000 + u * c - v * s, 1), round(2000 + u * s + v * c, 1))
    streets = []
    for i in range(nu):
        p0, p1 = P(i * pu, 0), P(i * pu, (nv - 1) * pv)
        streets.append({"n": "%d Avenue" % (i + 1), "k": 3 if i % 4 else 1, "p": [*p0, *p1]})
    for j in range(nv):
        if j == skip_row:
            continue
        p0, p1 = P(0, j * pv), P((nu - 1) * pu, j * pv)
        streets.append({"n": "%d Street" % (j + 1), "k": 4, "p": [*p0, *p1]})
    return {"W": 7000, "H": 6000, "scale": 1.0, "streets": streets, "rivers": [], "water": [], "parks": []}


def test_a_regular_grid_becomes_its_blocks():
    m = _grid_map()
    out = col.build(m, lambda x, y: (x, y), lambda x, y: True, lambda x, y: False)
    assert out["doms"], out["stats"]
    blocks = sum(st["blocks"] for st in out["stats"].values())
    assert 11 * 9 - 6 <= blocks <= 11 * 9                    # every cell between two avenues and two streets (a corner or two lost where
                                                              # the detection's cells round the grid's edge)
    d = out["doms"][0]
    assert abs((d["a"] % 90) - 20) < 1.5 or abs((d["a"] % 90) - 70) < 1.5
    heavy = [s for s in out["streets"] if s.get("L")]
    assert {s["n"] for s in heavy} == {"1 Avenue", "5 Avenue", "9 Avenue"}      # primary roads: the heavy lines
    assert not out["te"]                                      # no loose line: every street borders a block


def test_a_missing_street_makes_one_long_block_not_a_hole():
    m = _grid_map(skip_row=4)
    out = col.build(m, lambda x, y: (x, y), lambda x, y: True, lambda x, y: False)
    n = sum(st["blocks"] for st in out["stats"].values())
    assert 11 * 8 - 6 <= n <= 11 * 8                          # the two cells either side of the gap are one face
    assert any(len(r) > 8 or max(abs(r[i] - r[i + 4]) for i in (0, 1)) > 150 for r in out["tq"])


def test_water_and_parks_are_no_blocks():
    m = _grid_map()
    park = col.Mask(7000, 6000, [[2300, 2300, 2900, 2300, 2900, 2900, 2300, 2900]])
    wet = col.Mask(7000, 6000, [[4500, 0, 7000, 0, 7000, 6000, 4500, 6000]])
    out = col.build(m, lambda x, y: (x, y), lambda x, y: not wet(x, y), park)
    n = sum(st["blocks"] for st in out["stats"].values())
    assert 0 < n < 11 * 9
    for r in out["tq"]:
        xs, ys = r[0::2], r[1::2]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        assert not wet(cx, cy) and not park(cx, cy)


def test_even_ladder_keeps_the_real_places_and_leaves_a_rung_for_a_missing_street():
    lines = [{"off": o, "L": 900.0, "iv": [[0, 900]], "n": "", "k": 4} for o in (0, 101, 199, 302, 500, 601, 699)]
    pos, at = col._even(lines)
    assert sorted(at) == [0, 1, 2, 3, 5, 6, 7]                # the gap 302 -> 500 is two rungs
    assert all(abs(pos[k] - at[k]["off"]) < 12 for k in at)
    steps = [b - a for a, b in zip(pos, pos[1:])]
    assert max(steps) - min(steps) < 8                        # locally even


def test_outline_of_an_l_shaped_face():
    ring = col._outline([(0, 0), (1, 0), (0, 1)])
    assert len(ring) == 6 and (0, 0) in ring and (2, 0) in ring and (1, 1) in ring


def test_the_crossings_splice_into_the_city_drawing():
    js = palace_crossings.patch_js(palace.PALACE_JS)
    assert "(M.tun||[]).forEach" in js and js.index("(M.tun||[])") < js.index(palace_crossings.ANCHOR)
    with pytest.raises(ValueError):
        palace_crossings.patch_js("no anchor here")


@pytest.mark.parametrize("key", ["bcl", "yank", "citi", "uni", "ww", "pj", "sgt", "bkm", "ssa", "nybg", "clo"])
def test_the_boroughs_landmarks_have_their_own_art(key):
    art = palace_skyline.build(palace_skyline.LANDMARKS[key]())
    assert art["w"] > 0 and art["h"] > 0 and "<" in art["svg"]


def test_every_borough_landmark_names_art_that_exists():
    for n, la, lo, art, w, d in col.LANDMARKS:
        assert art in palace_skyline.LANDMARKS, n
        assert 40.4 < la < 41.0 and -74.3 < lo < -73.6 and w > 0 and d > 0
