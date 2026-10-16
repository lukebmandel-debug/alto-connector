"""Highways as named route lines (alto/build/city_highways.py, palace_highway_js.py): which ways are highways, one line
for both carriageways, interchanges named by exit and crossing street, routed on the drawn domains (Chicago v2 fixture
with its real highways), the checks, and the page / Directions hooks."""
import copy
import gzip
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import palace_map as pm  # noqa: E402
from alto.build import city_highways as ch, palace_grid  # noqa: E402

CHI = ROOT / "tests" / "fixtures" / "cities" / "chicago.json.gz"
CHI_HW = ROOT / "tests" / "fixtures" / "highways" / "chicago_hw.json.gz"


def _proj(p):                       # lat/lon -> px: 1 unit of the test's lat/lon = 1 m
    return (p[1], p[0])


def _way(i, pts, **tags):
    return {"type": "way", "id": i, "tags": tags, "geometry": [{"lat": y, "lon": x} for x, y in pts]}


def _raw():
    els = [
        # I 95: two carriageways 40 m apart, north-south, 3 km
        _way(1, [(1000, 0), (1000, 1400), (1000, 1500), (1000, 3000)], highway="motorway", ref="I 95", name="Delaware Expressway",
             oneway="yes", destination="Trenton"),
        _way(2, [(1040, 3000), (1040, 1500), (1040, 0)], highway="motorway", ref="I 95", name="Delaware Expressway",
             oneway="yes", destination="Chester"),
        # an exit ramp from I 95 to Market Street at y=1500, and its exit node
        _way(3, [(1000, 1400), (1100, 1500)], highway="motorway_link"),
        _way(4, [(1100, 1500), (1100, 1450), (900, 1520), (2000, 1520)], highway="secondary", name="Market Street"),
        {"type": "node", "id": 9, "lat": 1420, "lon": 1000, "tags": {"highway": "motorway_junction", "ref": "22"}},
        # a trunk that is a city street: not a highway
        _way(5, [(0, 500), (3000, 500)], highway="trunk", ref="US 1", name="Main Street"),
        # a trunk that is an expressway by its tags
        _way(6, [(0, 2500), (3000, 2500)], highway="trunk", ref="US 30", name="Admiral Wilson Boulevard", expressway="yes"),
        # a bridge alone, no ref: left to the engine's bridges
        _way(7, [(2500, 0), (2500, 2000)], highway="motorway", name="Some Bridge"),
        # a name-only piece of I 95 (its name carries the ref elsewhere) continuing it south
        _way(8, [(1000, 3000), (1000, 3600)], highway="motorway", name="Delaware Expressway"),
        {"type": "relation", "id": 50, "tags": {"type": "route", "route": "road", "network": "US:I", "ref": "95"},
         "members": [{"type": "way", "ref": 1}, {"type": "way", "ref": 2}]},
    ]
    return els


def test_refs_labels_networks_and_which_ways_qualify():
    assert ch.refs_of({"ref": "I 90;I 94"}) == ["I 90", "I 94"]
    assert ch.refs_of({"ref": "I 395 Express"}) == ["I 395"]
    assert min(["US 50", "I 66"], key=ch._rank) == "I 66"
    assert ch.label("I 95") == "I-95" and ch.label("FDR") == "FDR" and ch.label("A501") == "A501"
    assert ch.network("I 95") == "i" and ch.network("US 1") == "us" and ch.network("NY 9A") == "st"
    assert ch.network("B-10") == "o" and ch.network("95", "US:I") == "i"
    assert ch.qualifies({"highway": "motorway"})
    assert not ch.qualifies({"highway": "trunk", "name": "Euston Road", "ref": "A501"})
    assert ch.qualifies({"highway": "trunk", "name": "Ronda Litoral", "motorroad": "yes"})
    assert ch.qualifies({"highway": "trunk", "name": "West Street"}, [{"name": "West Side Highway", "net": ""}])
    assert ch.hw_name({"name": "West Street", "alt_name": "West Side Highway"}) == "West Side Highway"
    assert ch.hw_name({"name": "Holland Tunnel"}, [{"name": "Interstate 78", "net": "US:I"}]) == "Holland Tunnel"


def test_read_one_line_for_both_carriageways_and_named_interchange():
    H = ch.read(_raw(), _proj, 4000, 4000)
    refs = sorted(r["ref"] for r in H["roads"])
    assert refs == ["I-95", "US-30"]                          # Main Street and the lone bridge are not highways
    i95 = next(r for r in H["roads"] if r["ref"] == "I-95")
    assert len(i95["parts"]) == 1 and i95["net"] == "i" and i95["n"] == "Delaware Expressway"
    xs = [p for p in ch._pairs(i95["parts"][0]["p"])]
    assert all(995 <= x <= 1045 for x, _y in xs)               # one line between the carriageways
    assert max(y for _x, y in xs) >= 3500                      # the name-only piece joined it
    words = {d[0]: d[1] for d in i95["dir"]}
    assert set(words) == {"north", "south"} and words["south"] == "Trenton" and words["north"] == "Chester"
    xx = [x for x in H["x"] if x["r"] == i95["id"] and not x.get("end")]
    assert len(xx) == 1 and xx[0]["ex"] == ["22"] and xx[0]["n"] == "Market Street"
    assert 1350 < xx[0]["y"] < 1550


def test_build_map_carries_the_highways_and_the_query_asks_for_exits():
    q = pm.build_query((39.9, -75.2, 40.0, -75.1))
    assert "motorway_junction" in q and "route=road" in q
    raw = {"elements": [_way(1, [(-75.15, 39.91), (-75.15, 39.99)], highway="motorway", ref="I 95", name="Delaware Expressway")]}
    m = pm.build_map(raw, (39.9, -75.2, 40.0, -75.1), place="Test")
    assert [r["ref"] for r in m["highways"]["roads"]] == ["I-95"]


@pytest.fixture(scope="module")
def chicago():
    if not (CHI.exists() and CHI_HW.exists()):
        pytest.skip("no Chicago fixture")
    from alto.build import city_types
    old = city_types.ENGINE_V2
    city_types.ENGINE_V2 = True
    m = json.loads(gzip.decompress(CHI.read_bytes()).decode())
    m["highways"] = json.loads(gzip.decompress(CHI_HW.read_bytes()).decode())
    try:
        g = palace_grid.grid(copy.deepcopy(m))
        ch.attach(g, m)                                       # a no-op when city_engine attached them
    finally:
        city_types.ENGINE_V2 = old
    return m, g


def test_chicago_highways_are_clean_named_lines(chicago):
    m, g = chicago
    hw = g["hw"]
    assert "highways" not in g                                # the real data does not reach the page
    refs = {r["ref"]: r for r in hw["roads"]}
    assert {"I-90", "I-290", "US-41"} <= set(refs)
    st = ch.measure(g, m)
    for rid, s in st.items():
        assert s["octi"] is None or s["octi"] >= 0.95, s     # along the domain's axes / 45 degrees
        assert s["stray"] <= 2.5, s
        assert s["x_off_line"] == 0, s                        # every interchange ring on its road
    k = next(s for s in st.values() if s["ref"] == "I-90")
    assert k["turns"] <= 4 and k["x"] >= 3                    # Kennedy + Dan Ryan: one line, few bends
    assert all(r["sh"] for r in hw["roads"])                  # shields along every road
    status, msg, data = ch.report(g, m)
    assert status in ("ok", "warn"), msg
    assert ch.attach(g, m) is hw                              # idempotent


def test_order_of_the_chicago_highways_is_true(chicago):
    m, g = chicago
    refs = {r["ref"]: r for r in g["hw"]["roads"]}
    xs = lambda r: [x for f in r["p"] for x in f[0::2]]       # noqa: E731
    # the Dan Ryan / Kennedy runs west of Lake Shore Drive, the Eisenhower runs east-west between them
    assert max(xs(refs["I-90"])) < min(xs(refs["US-41"]))
    e = refs["I-290"]["p"][0]
    assert abs(e[1] - e[-1]) < 0.2 * abs(e[0] - e[-2])


def test_page_and_directions_hooks():
    from alto.build import palace, palace_directions
    from alto.build.palace_highway_js import HIGHWAY_JS, HIGHWAY_CSS
    assert HIGHWAY_JS in palace.PALACE_JS and "window._palHw.init(" in palace.PALACE_JS
    for call in ("window._palHw.lines(svg)", "window._palHw.stops(svg)", "window._palHw.hits(svg)", "window._palHw.keyHtml(sw)"):
        assert call in palace.PALACE_JS
    assert ".pl-tube.hw" in HIGHWAY_CSS
    src = Path(palace_directions.__file__).read_text(encoding="utf-8")
    assert "window._palHw.drive(A, B)" in src and "window._palHw.places()" in src and "'Drive'" in src
