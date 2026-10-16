"""P4: free domains (city_free.FreeMap / streets_in wired into city_engine), the motorway-over-street line rule."""
import math

from alto.build import city_free, city_lines


def test_freemap_exact_at_anchors_and_inverts():
    src = [(0, 0), (1000, 0), (1000, 1000), (0, 1000), (500, 0), (0, 500), (1000, 500)]
    dst = [(100 + 2 * x + (5 if x > 600 else 0), 50 + 2 * y) for x, y in src]
    fm = city_free.FreeMap(src, dst)
    for p, q in zip(src, dst):
        r = fm(*p)
        assert math.dist(r, q) < 3.0
    x, y = fm.inverse(*fm(420.0, 610.0))
    assert math.dist((x, y), (420.0, 610.0)) < 2.0
    tb, a, o = fm.tables()
    assert abs(a) < 1.0 and tb["xg"][1] / tb["xr"][1] > 1.9


def test_motorway_never_takes_a_streets_line():
    # I-95 (k 0, a major) runs 2 px from Front Street: the line keeps Front Street's name, and is still major
    sts = [{"n": "Front Street", "k": 1, "p": [1000, 0, 1000, 3000]},
           {"n": "Delaware Expressway", "k": 0, "p": [1002, 0, 1002, 4000]},
           {"n": "2nd Street", "k": 1, "p": [800, 0, 800, 3000]}]
    c = city_lines.candidates(sts, 0.0, (1000, 1500), majors=("Delaware Expressway",))
    names = [l["n"] for l in c["v"]]
    assert "Front Street" in names and "Delaware Expressway" not in names
    assert next(l for l in c["v"] if l["n"] == "Front Street")["major"]
