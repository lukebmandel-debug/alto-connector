"""Memory Palace street maps (alto/palace_map.py): offline tests on small synthetic
Overpass-shaped data. Nothing here touches the network."""
from __future__ import annotations

import io
import json
import math
import urllib.error

import pytest

from alto import palace_map as pm

BB = (39.0, -75.0, 39.01, -74.99)          # ~855 x 1106 m


def way(i, pts, **tags):
    return {"type": "way", "id": i, "tags": tags,
            "geometry": [{"lat": a, "lon": b} for a, b in pts]}


def test_projection():
    s, w, n, e = BB
    assert pm.project(n, w, BB) == (0, 0)
    x, y = pm.project(s, e, BB)
    assert y == pytest.approx((n - s) * 110574)
    assert x == pytest.approx((e - w) * math.cos(math.radians(39.005)) * 111320)
    assert pm.project(s, e, BB, 2.0)[0] == pytest.approx(2 * x)
    m = pm.build_map({"elements": []}, BB)
    assert (m["W"], m["H"]) == (math.ceil(x), math.ceil(y))
    assert m["attribution"].startswith("©")


def test_douglas_peucker():
    line = [(0, 0), (5, 0.3), (10, 0), (10, 10)]
    assert pm.douglas_peucker(line, 0.8) == [(0, 0), (10, 0), (10, 10)]
    assert pm.douglas_peucker(line, 0.1) == line
    ring = [(0, 0), (5, 0.2), (10, 0), (10, 10), (0, 10)]
    out = pm.simplify_ring(ring, 0.8)
    assert len(out) == 4 and out[0] != out[-1]


def test_clip_polygon():
    sq = [(-5, -5), (15, -5), (15, 15), (-5, 15)]
    assert sorted(pm.clip_polygon(sq, 10, 10)) == [(0, 0), (0, 10), (10, 0), (10, 10)]
    assert pm.clip_polygon([(20, 20), (30, 20), (30, 30)], 10, 10) == []
    inside = [(1, 1), (5, 1), (5, 5)]
    assert pm.clip_polygon(inside, 10, 10) == inside
    half = pm.clip_polygon([(5, 5), (15, 5), (15, 8), (5, 8)], 10, 10)
    assert abs(pm.ring_area(half)) == pytest.approx(15)


def test_clip_polyline_splits():
    # leaves through the right side and comes back lower down
    line = [(1, 1), (15, 1), (15, 5), (1, 5)]
    pieces = pm.clip_polyline(line, 10, 10)
    assert len(pieces) == 2
    assert pieces[0][0] == (1, 1) and pieces[0][-1] == (10, 1)
    assert pieces[1][0] == (10, 5) and pieces[1][-1] == (1, 5)
    assert pm.clip_polyline([(20, 0), (20, 9)], 10, 10) == []
    assert pm.clip_polyline([(1, 1), (2, 2), (3, 1)], 10, 10) == [[(1, 1), (2, 2), (3, 1)]]
    crossing = pm.clip_polyline([(-5, 5), (15, 5)], 10, 10)
    assert crossing == [[(0, 5), (10, 5)]]


def test_assemble_rings_unordered_and_reversed():
    a, b, c, d = (0, 0), (0, 1), (1, 1), (1, 0)
    ways = [[c, d], [a, b], [a, d], [b, c]]          # d->a is stored reversed
    rings = pm.assemble_rings(ways)
    assert len(rings) == 1 and set(rings[0]) == {a, b, c, d} and len(rings[0]) == 4
    assert abs(pm.ring_area(rings[0])) == pytest.approx(1)
    closed = [(5, 5), (5, 6), (6, 6), (5, 5)]
    assert len(pm.assemble_rings([closed, [a, b], [b, c]])) == 1   # open chain dropped


def test_multipolygon_outer_inner_wound_opposite():
    big = [(39.0, -75.0), (39.0, -74.99), (39.01, -74.99), (39.01, -75.0)]
    hole = [(39.004, -74.996), (39.004, -74.994), (39.006, -74.994), (39.006, -74.996)]
    rel = {"type": "relation", "id": 1, "tags": {"type": "multipolygon", "natural": "water"},
           "members": [
               {"type": "way", "ref": 1, "role": "outer",
                "geometry": [{"lat": a, "lon": b} for a, b in big[:3]]},
               {"type": "way", "ref": 2, "role": "outer",
                "geometry": [{"lat": a, "lon": b} for a, b in [big[2], big[3], big[0]]]},
               {"type": "way", "ref": 3, "role": "inner",
                "geometry": [{"lat": a, "lon": b} for a, b in hole + [hole[0]]]}]}
    m = pm.build_map({"elements": [rel]}, BB)
    assert len(m["water"]) == 2
    areas = sorted(pm.ring_area(list(zip(r[0::2], r[1::2]))) for r in m["water"])
    assert areas[0] < 0 < areas[1]


def test_big_riverbank_is_clipped_to_box():
    far = [(38.0, -76.0), (38.0, -74.0), (40.0, -74.0), (40.0, -76.0), (38.0, -76.0)]
    m = pm.build_map({"elements": [way(1, far, natural="water")]}, BB)
    (ring,) = m["water"]
    xs, ys = ring[0::2], ring[1::2]
    assert min(xs) == 0 and min(ys) == 0 and max(xs) <= m["W"] and max(ys) <= m["H"]
    assert abs(pm.ring_area(list(zip(xs, ys)))) == pytest.approx(m["W"] * m["H"], rel=0.01)


def test_merge_ways():
    items = [
        {"key": ("A", 3), "pts": [(0, 0), (0, 1)]},
        {"key": ("A", 3), "pts": [(0, 2), (0, 1)]},          # reversed
        {"key": ("A", 3), "pts": [(0, 2), (0, 3)]},
        {"key": ("B", 3), "pts": [(0, 3), (0, 4)]},          # other key: never joined
        {"key": ("A", 4), "pts": [(0, 3), (0, 9)]},
    ]
    out = pm.merge_ways(items)
    assert len(out) == 3
    a = next(o for o in out if o["key"] == ("A", 3))
    assert a["pts"] in ([(0, 0), (0, 1), (0, 2), (0, 3)], [(0, 3), (0, 2), (0, 1), (0, 0)])


def test_merge_prefers_straight_continuation():
    items = [{"key": "s", "pts": [(0, 0), (0, 1)]},
             {"key": "s", "pts": [(0, 1), (1, 1)]},          # sharp turn
             {"key": "s", "pts": [(0, 1), (0, 2)]}]          # straight on
    out = pm.merge_ways(items)
    longest = max(out, key=lambda o: len(o["pts"]))
    assert (0, 2) in longest["pts"] and (1, 1) not in longest["pts"]


def test_street_merge_through_build_map():
    raw = {"elements": [
        way(1, [(39.002, -74.995), (39.004, -74.995)], highway="residential", name="Oak St"),
        way(2, [(39.004, -74.995), (39.006, -74.995)], highway="residential", name="Oak St"),
        way(3, [(39.006, -74.995), (39.008, -74.995)], highway="residential", name="Oak St", bridge="yes"),
        way(4, [(39.002, -74.996), (39.008, -74.996)], highway="service"),     # unnamed service: dropped
        way(5, [(39.002, -74.997), (39.008, -74.997)], highway="footway", name="River Trail"),
        way(6, [(39.002, -74.998), (39.008, -74.998)], highway="footway"),     # unnamed: dropped
    ]}
    m = pm.build_map(raw, BB)
    assert [(s["n"], s.get("b")) for s in m["streets"]] == [("Oak St", None), ("Oak St", 1)]
    assert len(m["streets"][0]["p"]) == 4                   # two ways merged, collinear -> 2 points
    assert [t["n"] for t in m["trails"]] == ["River Trail"]
    assert all(v is not None for s in m["streets"] for v in s.values())


def test_majors_selection():
    streets = [{"n": "Main", "k": 1, "len": 10}, {"n": "Ring Rd", "k": 0, "len": 5},
               {"n": "Long", "k": 2, "len": 1000}, {"n": "Long", "k": 2, "len": 600},
               {"n": "Short", "k": 2, "len": 900}, {"n": "Elm", "k": 4, "len": 99999},
               {"n": "", "k": 1, "len": 5000}]
    assert pm.pick_majors(streets) == ["Long", "Main", "Ring Rd"]
    assert pm.pick_majors(streets, ["elm", "MAIN", "Nowhere", "main"]) == ["Elm", "Main"]


def test_dedupe_stations():
    st = [{"n": "City Hall", "x": 0, "y": 0, "k": "subway", "l": ["A"]},
          {"n": "city hall", "x": 50, "y": 50, "k": "subway", "l": ["B", "A"]},
          {"n": "City Hall", "x": 500, "y": 0, "k": "subway", "l": ["C"]},    # far: separate
          {"n": "Other", "x": 1, "y": 1, "k": "rail", "l": []}]
    out = pm.dedupe_stations(st)
    assert len(out) == 3 and out[0]["l"] == ["A", "B"]


def test_rails_and_stations_from_routes():
    ways = [
        way(10, [(39.002, -74.998), (39.004, -74.998)], railway="subway", tunnel="yes"),
        way(11, [(39.004, -74.998), (39.006, -74.998)], railway="subway", tunnel="yes"),
        way(12, [(39.002, -74.996), (39.006, -74.996)], railway="subway", bridge="yes"),
        way(13, [(39.002, -74.994), (39.006, -74.994)], railway="rail", service="yard"),
        way(14, [(39.002, -74.992), (39.006, -74.992)], railway="rail", name="Own Name"),
    ]
    rels = [
        {"type": "relation", "id": 100, "tags": {"type": "route", "route": "subway", "ref": "L",
                                                 "name": "Blue Line: A => B", "colour": "#0097D6"},
         "members": [{"type": "way", "ref": 10, "role": ""}, {"type": "way", "ref": 11, "role": ""},
                     {"type": "way", "ref": 12, "role": ""},
                     {"type": "node", "ref": 7, "role": "stop"}]},
        {"type": "relation", "id": 101, "tags": {"type": "route", "route": "subway", "ref": "X",
                                                 "name": "Plain"},
         "members": [{"type": "way", "ref": 10, "role": ""}]},
    ]
    nodes = [{"type": "node", "id": 7, "lat": 39.003, "lon": -74.998, "tags": {"name": "Elm"}},
             {"type": "node", "id": 8, "lat": 39.003, "lon": -74.9981,
              "tags": {"name": "Elm", "railway": "station", "station": "subway"}}]
    m = pm.build_map({"elements": ways + rels + nodes}, BB)
    rails = m["rails"]
    assert len(rails) == 4            # yard dropped; ways 10 (L/X) and 11 (L) differ so stay apart
    w10 = next(r for r in rails if r["r"] == "L/X")
    assert w10["n"] == "Blue Line" and w10["c"] == "#0097d6" and w10["k"] == "subway" and w10["u"] == 1
    bridge = next(r for r in rails if r.get("e"))
    assert "u" not in bridge and bridge["r"] == "L"
    own = next(r for r in rails if r["n"] == "Own Name")
    assert own["c"] == "" and "u" not in own and "e" not in own
    (st,) = m["stations"]             # the stop node and the station node share a name and spot
    assert st["n"] == "Elm" and st["k"] == "subway" and st["l"] == ["Blue Line"]


def test_landmark_prefers_outline_and_case_insensitive():
    sq = [(39.004, -74.996), (39.004, -74.994), (39.006, -74.994), (39.006, -74.996), (39.004, -74.996)]
    els = [{"type": "node", "id": 1, "lat": 39.001, "lon": -74.999, "tags": {"name": "city hall"}},
           way(2, sq, name="City Hall", building="yes")]
    m = pm.build_map({"elements": els}, BB, landmarks=["CITY HALL", "Nowhere"])
    (lm,) = m["landmarks"]
    assert lm["n"] == "City Hall" and len(lm["r"]) == 1
    assert 0 < lm["x"] < m["W"]


def test_query_escapes_landmarks():
    q = pm.build_query(BB, ['Say "Hi" (x).'])
    assert '\\"Hi\\"' in q and "\\\\(x\\\\)\\\\." in q
    assert "out geom;" in q and q.startswith("[out:json]")


def test_overpass_retries_then_falls_back(monkeypatch):
    calls = []

    def fake(req, timeout=0, **kw):
        calls.append(req.full_url)
        assert req.get_header("User-agent") == pm.UA
        if req.full_url == pm.OVERPASS:
            raise urllib.error.HTTPError(req.full_url, 429, "busy", {}, io.BytesIO(b""))
        return io.BytesIO(b'{"elements": []}')

    monkeypatch.setattr(pm.urllib.request, "urlopen", fake)
    monkeypatch.setattr(pm, "_sleep", lambda s: None)
    assert pm.fetch_osm(BB) == {"elements": []}
    assert calls == [pm.OVERPASS] * 2 + [pm.OVERPASS_FALLBACK]     # a busy server: one more try, then the next mirror


def test_fetch_cache(tmp_path, monkeypatch):
    n = []
    monkeypatch.setattr(pm, "_post_overpass", lambda q, t: n.append(1) or {"elements": [1]})
    assert pm.fetch_osm(BB, tmp_path) == {"elements": [1]}
    assert pm.fetch_osm(BB, tmp_path) == {"elements": [1]}
    assert len(n) == 1 and len(list(tmp_path.glob("osm-*.json"))) == 1


def test_geocode(monkeypatch):
    body = json.dumps([{"lat": "39.95", "lon": "-75.16", "display_name": "Philadelphia",
                        "boundingbox": ["39.8", "40.1", "-75.3", "-74.9"]}]).encode()
    monkeypatch.setattr(pm.urllib.request, "urlopen", lambda req, timeout=0: io.BytesIO(body))
    g = pm.geocode("Philadelphia")
    assert g["bbox"] == [39.8, -75.3, 40.1, -74.9] and g["name"] == "Philadelphia"
    monkeypatch.setattr(pm.urllib.request, "urlopen", lambda req, timeout=0: io.BytesIO(b"[]"))
    assert pm.geocode("zzzz") is None


# ── a wide river that is the edge of the city (the Delaware at Philadelphia) ──
def wide_map(east_len=300.0):
    """A 2000 x 800 box: a 400 px wide river runs down it at x=1200; three long streets on the
    west bank, one short street (and a station) on the far bank, and a bridge walkway across."""
    W, H = 2000, 800
    return {
        "W": W, "H": H, "scale": 1.0,
        "water": [[1000, 0, 1400, 0, 1400, 800, 1000, 800]],
        "rivers": [{"n": "Big River", "p": [1200, 800, 1200, 0]}],
        "streets": [{"n": "West %d" % i, "k": 3, "p": [100, 100 + 200 * i, 950, 100 + 200 * i]} for i in range(3)]
                   + [{"n": "Far Street", "k": 3, "p": [1500, 100, 1500, 100 + east_len]}],
        "trails": [{"n": "Test Bridge Walkway (North)", "p": [900, 300, 1100, 300, 1300, 300, 1700, 300]}],
        "rails": [], "parks": [], "landmarks": [],
        "stations": [{"n": "Far Station", "x": 1600, "y": 400, "k": "rail", "l": []},
                     {"n": "Near Station", "x": 500, "y": 400, "k": "rail", "l": []}],
    }


def test_a_wide_river_across_the_box_cuts_away_the_far_bank():
    out = pm._across_wide_river(wide_map(), 1.0)
    assert out["bank"]["n"] == "Big River" and out["bank"]["side"] == "e"
    assert out["bank"]["w"] == pytest.approx(400, abs=5)
    assert [s["n"] for s in out["streets"]] == ["West 0", "West 1", "West 2"]
    assert [s["n"] for s in out["stations"]] == ["Near Station"]
    # the walkway is cut at the river's line, and is named as a bridge, where it leaves the near bank
    (tr,) = out["trails"]
    assert tr["p"][-2] == pytest.approx(1200, abs=1) and tr["p"][0] == 900
    assert out["bank"]["bridges"] == [{"n": "Test Bridge", "at": [900.0, 300.0]}]


def test_a_river_the_streets_mostly_lie_across_leaves_the_box_alone():
    m = wide_map(east_len=700.0)                    # the far bank holds as many streets as the near one
    m["streets"] += [{"n": "Far %d" % i, "k": 3, "p": [1500, 0, 1500, 700]} for i in range(3)]
    out = pm._across_wide_river(m, 1.0)
    assert "bank" not in out and len(out["streets"]) == 7


def test_a_narrow_river_is_not_a_bank():
    m = wide_map()
    m["water"] = [[1150, 0, 1250, 0, 1250, 800, 1150, 800]]          # 100 px across
    out = pm._across_wide_river(m, 1.0)
    assert "bank" not in out and any(s["n"] == "Far Street" for s in out["streets"])


def test_light_query_and_tiles(tmp_path, monkeypatch):
    q = pm.build_query((40.0, -75.2, 40.02, -75.1), landmarks=["City Hall"], light=True,
                       streets=["Germantown Avenue"])
    assert "highway=service" not in q and "footway" not in q and "City Hall" not in q
    assert "Germantown Avenue" in q and "tertiary" in q and "route" in q
    full = pm.build_query((40.0, -75.2, 40.02, -75.1), landmarks=["City Hall"])
    assert len(q) < len(full) and "highway=service" in full
    tiles = pm.tile_boxes((39.9683, -75.245, 40.005, -75.085))
    assert len(tiles) == 8 and tiles[0][0] == 39.9683 and tiles[-1][2:] == (40.005, -75.085)
    seen = []

    def post(query, t):
        seen.append(query)
        i = len(seen)
        return {"elements": [{"type": "way", "id": 1, "tags": {}},                    # on every tile edge
                             {"type": "way", "id": 10 + i, "tags": {}, "geometry": [1]}]}
    monkeypatch.setattr(pm, "_post_overpass", post)
    raw = pm.fetch_tiled((39.9683, -75.245, 40.005, -75.085), cache_dir=tmp_path)
    assert len(seen) == 8 and len(raw["elements"]) == 9           # the shared way is kept once
    pm.fetch_tiled((39.9683, -75.245, 40.005, -75.085), cache_dir=tmp_path)
    assert len(seen) == 8                                         # every tile came from the cache
    assert len(list(tmp_path.glob("osm-*-light.json"))) == 8


def test_fetch_tiled_names_the_failed_tile(tmp_path, monkeypatch):
    def post(q, t):
        raise RuntimeError("Overpass failed")
    monkeypatch.setattr(pm, "_post_overpass", post)
    with pytest.raises(RuntimeError, match="tiles failed"):
        pm.fetch_tiled((40.0, -75.2, 40.02, -75.16), cache_dir=tmp_path)
