"""2.0.0 street data for the first-person view: palace_street.py (Overpass -> hosted content-hashed blob), its registration in palace_assets / publish_static and the
JS decoder (palace_street_js.py). Overpass is stubbed (no network); the size check runs on the real Philadelphia building tiles when the QA kit has them."""
import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from alto import palace_map as pmap
from alto.build import palace_assets, palace_street as ps
from alto.build.palace_street_js import STREET_JS

BBOX = (39.9489, -75.1731, 39.9633, -75.1505)
NODE = Path.home() / ".local" / "node" / "bin" / "node"
QA_BLD = Path.home() / "Desktop" / "Alto Development" / "_qa" / "osm" / "buildings"


def _geom(*pts):
    return [{"lat": la, "lon": lo} for la, lo in pts]


def _sq(la, lo, d=0.0002):
    return _geom((la, lo), (la, lo + d), (la + d, lo + d), (la + d, lo), (la, lo))


BLD = {"elements": [
    {"type": "way", "id": 1, "geometry": _sq(39.9500, -75.1700),
     "tags": {"building": "house", "building:levels": "3", "height": "10.5 m", "building:colour": "#a05040", "building:material": "brick", "roof:shape": "flat",
              "roof:colour": "grey", "roof:material": "tar_paper", "roof:levels": "1", "name": "Rowhouse", "addr:housenumber": "12", "addr:street": "Walnut St",
              "start_date": "1840", "wikidata": "Q1", "shop": "bakery"}},
    {"type": "way", "id": 2, "geometry": _sq(39.9500, -75.1650), "tags": {"building": "yes", "building:material": "brick"}},
    {"type": "way", "id": 3, "geometry": _sq(39.9520, -75.1600), "tags": {"building:part": "roof", "height": "30 ft"}},
    {"type": "relation", "id": 4, "tags": {"building": "retail", "type": "multipolygon"}, "members": [
        {"type": "way", "role": "outer", "geometry": _sq(39.9560, -75.1550, 0.001)},
        {"type": "way", "role": "inner", "geometry": _sq(39.9564, -75.1546, 0.0002)}]},
    {"type": "way", "id": 5, "geometry": _sq(39.9300, -75.1700), "tags": {"building": "yes"}},     # outside the box: dropped
]}
ST = {"elements": [
    {"type": "node", "id": 10, "lat": 39.9501, "lon": -75.1699, "tags": {"natural": "tree", "species": "Platanus x acerifolia", "leaf_type": "broadleaved"}},
    {"type": "node", "id": 11, "lat": 39.9502, "lon": -75.1699, "tags": {"natural": "tree", "genus": "Quercus"}},
    {"type": "node", "id": 12, "lat": 39.9503, "lon": -75.1698, "tags": {"highway": "street_lamp"}},
    {"type": "node", "id": 13, "lat": 39.9503, "lon": -75.1697, "tags": {"highway": "traffic_signals"}},
    {"type": "node", "id": 14, "lat": 39.9504, "lon": -75.1697, "tags": {"amenity": "bench"}},
    {"type": "node", "id": 15, "lat": 39.9504, "lon": -75.1696, "tags": {"emergency": "fire_hydrant"}},
    {"type": "node", "id": 16, "lat": 39.9505, "lon": -75.1696, "tags": {"amenity": "post_box"}},
    {"type": "node", "id": 17, "lat": 39.9506, "lon": -75.1695, "tags": {"entrance": "main"}},
    {"type": "node", "id": 18, "lat": 39.9506, "lon": -75.1694, "tags": {"door": "hinged"}},
    {"type": "node", "id": 19, "lat": 39.9507, "lon": -75.1693, "tags": {"shop": "bakery", "name": "Fresh Loaf", "addr:housenumber": "14", "addr:street": "Walnut St"}},
    {"type": "way", "id": 20, "center": {"lat": 39.9510, "lon": -75.1690}, "tags": {"amenity": "cafe", "name": "Cafe Uno"}},
    {"type": "node", "id": 21, "lat": 39.9511, "lon": -75.1690, "tags": {"amenity": "cafe"}},                # no name: no sign
    {"type": "way", "id": 30, "tags": {"highway": "residential", "name": "Walnut St", "lanes": "2", "width": "7", "oneway": "yes", "sidewalk": "both",
                                         "cycleway": "lane", "surface": "asphalt", "maxspeed": "25 mph", "lit": "yes"},
     "geometry": _geom((39.9495, -75.1730), (39.9495, -75.1600), (39.9495, -75.1510))},
    {"type": "way", "id": 31, "tags": {"highway": "construction"}, "geometry": _geom((39.95, -75.17), (39.95, -75.16))},
]}


def test_the_query_asks_for_every_feature_kind_politely():
    q = ps.street_query((39.95, -75.17, 39.96, -75.16))
    for w in ("natural=tree", "street_lamp|traffic_signals|crossing|stop|bus_stop", "bench|bicycle_parking|waste_basket|post_box|fire_hydrant", "emergency=fire_hydrant",
              "node[entrance]", "node[door]", "shop|amenity|tourism|office", "way[highway]", "out center", "out geom"):
        assert w in q


def test_tags_are_parsed():
    bl = ps.parse_buildings(BLD)
    assert len(bl) == 5
    st = ps.parse_street(ST)
    assert [t[3] for t in st["trees"]] == ["Platanus x acerifolia", "Quercus"]
    assert sorted(f[3] for f in st["furn"]) == ["bench", "fire_hydrant", "post_box", "street_lamp", "traffic_signals"]
    assert sorted(d[3] for d in st["door"]) == ["door=hinged", "entrance=main"]
    assert sorted(p[3] for p in st["poi"]) == ["Cafe Uno", "Fresh Loaf"]
    assert [h[2]["highway"] for h in st["hw"]] == ["residential"]            # the construction way is skipped


def test_the_blob_round_trips_every_tag():
    blob = ps.build(BBOX, BLD, ST)
    assert blob["v"] == 1 and blob["a"] == ps.ATTRIBUTION and blob["q"] == 0.1 and blob["cs"] == 5000 and blob["o"] == list(BBOX)
    assert blob["S"][0] == "" and len(set(blob["S"])) == len(blob["S"])              # a string table without repeats
    cells = {k: ps.decode_cell(blob, k) for k in blob["c"]}
    bs = [b for c in cells.values() for b in c["b"]]
    assert len(bs) == 4                                                              # the building outside the box is dropped
    house = next(b for b in bs if b["nm"] == "Rowhouse")
    assert (house["k"], house["lv"], house["bc"], house["bm"], house["rs"], house["rc"], house["rm"], house["rl"], house["ad"], house["po"], house["sd"], house["wd"]) == \
        ("house", 3, "#a05040", "brick", "flat", "grey", "tar_paper", 1, "12 Walnut St", "shop=bakery", "1840", "Q1")
    assert house["h"] == 105 and len(house["ring"]) == 4
    # real positions: the ring sits where the lat/lon says (metres east/north of the box's south-west corner)
    x0 = (-75.1700 - BBOX[1]) * blob["kx"]
    y0 = (39.9500 - BBOX[0]) * blob["ky"]
    assert abs(house["ring"][0][0] - x0) < 0.1 and abs(house["ring"][0][1] - y0) < 0.1
    part = next(b for b in bs if b["k"] == "p:roof")
    assert abs(part["h"] - 91) <= 1                                                  # 30 ft = 9.144 m
    hole = next(b for b in bs if b["k"] == "retail")
    assert len(hole["holes"]) == 1
    flat = {k: [x for c in cells.values() for x in c[k]] for k in "rtfpe"}
    assert [(t["sp"], t["lf"]) for t in flat["t"]] == [("Platanus x acerifolia", "broadleaved"), ("Quercus", "")]
    assert sorted(f["kind"] for f in flat["f"]) == ["bench", "fire_hydrant", "post_box", "street_lamp", "traffic_signals"]
    assert sorted(e["kind"] for e in flat["e"]) == ["door=hinged", "entrance=main"]
    assert sorted((p["name"], p["cat"], p["ad"]) for p in flat["p"]) == [("Cafe Uno", "amenity=cafe", ""), ("Fresh Loaf", "shop=bakery", "14 Walnut St")]
    roads = flat["r"]
    assert all((r["hw"], r["nm"], r["ln"], r["wd"], r["ow"], r["sw"], r["cy"], r["sf"], r["ms"], r["lt"]) == ("residential", "Walnut St", 2, 70, 1, "both", "lane", "asphalt", "25 mph", 1)
               for r in roads)
    # the 1.2 km street is cut at the cell borders, the pieces joined by a shared vertex
    assert len(roads) >= 2
    assert abs(roads[0]["line"][0][0] - (-75.1730 - BBOX[1]) * blob["kx"]) < 0.1
    assert abs(roads[-1]["line"][-1][0] - (-75.1510 - BBOX[1]) * blob["kx"]) < 0.1
    ends = {(round(r["line"][-1][0], 1), round(r["line"][-1][1], 1)) for r in roads}
    assert all((round(r["line"][0][0], 1), round(r["line"][0][1], 1)) in ends for r in roads[1:])      # each piece starts where an earlier one ended


def test_chunking_by_500_m_cells():
    blob = ps.build(BBOX, BLD, ST)
    assert blob["n"] == [ps.Frame(BBOX).nx, ps.Frame(BBOX).ny] and blob["n"][0] >= 3
    for key in blob["c"]:
        ix, iy = (int(v) for v in key.split(","))
        assert 0 <= ix < blob["n"][0] and 0 <= iy < blob["n"][1]
        c = ps.decode_cell(blob, key)
        for b in c["b"]:                                                             # a building lives in the cell of its centroid
            cx = sum(p[0] for p in b["ring"]) / len(b["ring"])
            cy = sum(p[1] for p in b["ring"]) / len(b["ring"])
            assert ix * 500 <= cx < (ix + 1) * 500 and iy * 500 <= cy < (iy + 1) * 500
        for t in c["t"]:
            assert ix * 500 <= t["x"] < (ix + 1) * 500 and iy * 500 <= t["y"] < (iy + 1) * 500
    assert len(blob["c"]) >= 3                                                       # the street and the buildings are in different cells


def test_the_same_data_gives_the_same_hash_whatever_the_order():
    a = ps.encode(ps.build(BBOX, BLD, ST))
    rev = {"elements": list(reversed(BLD["elements"]))}
    rst = {"elements": list(reversed(ST["elements"]))}
    b = ps.encode(ps.build(BBOX, rev, rst))
    assert ps.blob_hash(a) == ps.blob_hash(b) and a == b
    changed = {"elements": [dict(e) for e in ST["elements"]]}
    changed["elements"][0] = dict(changed["elements"][0], lat=39.9502)
    assert ps.blob_hash(ps.encode(ps.build(BBOX, BLD, changed))) != ps.blob_hash(a)
    assert len(ps.blob_hash(a)) == 12 and ps.url_of(ps.blob_hash(a)) == "/street/palace-street-%s.json" % ps.blob_hash(a)


def test_a_repeated_word_is_stored_once_and_it_is_small():
    els = [{"type": "way", "id": i, "geometry": _sq(39.9500 + (i % 20) * 0.0003, -75.1700 + (i // 20) * 0.0003, 0.0002),
            "tags": {"building": "house", "building:material": "brick", "roof:shape": "flat", "addr:street": "Walnut St", "addr:housenumber": str(i)}} for i in range(400)]
    blob = ps.build(BBOX, {"elements": els}, {"elements": []})
    assert blob["S"].count("brick") == 1 and blob["S"].count("flat") == 1 and blob["S"].count("house") == 1
    text = ps.encode(blob)
    assert len(gzip.compress(text.encode())) < 150_000 and len(text) / 400 < 90        # bytes per row-house building


def test_offline_returns_the_cache_only(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network")
    monkeypatch.setattr(pmap, "_post_overpass", boom)
    r = ps.fetch(BBOX, cache_dir=tmp_path, offline=True)
    assert r["elements"] == [] and r["missing"]
    tb = pmap.tile_boxes(BBOX, *ps.STREET_TILE)[0]
    (tmp_path / ("street-%.4f_%.4f_%.4f_%.4f.json" % tb)).write_text(json.dumps(ST), "utf-8")
    r = ps.fetch(BBOX, cache_dir=tmp_path, offline=True)
    assert len(r["elements"]) == len(ST["elements"]) and len(r["missing"]) == len(pmap.tile_boxes(BBOX, *ps.STREET_TILE)) - 1


def test_fetch_asks_each_tile_once_and_caches_it(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(pmap, "_post_overpass", lambda q, t: asked.append(q) or ST)
    monkeypatch.setattr(pmap, "_sleep", lambda s: None)
    r = ps.fetch(BBOX, cache_dir=tmp_path)
    n = len(pmap.tile_boxes(BBOX, *ps.STREET_TILE))
    assert len(asked) == n and not r["missing"]
    ps.fetch(BBOX, cache_dir=tmp_path)
    assert len(asked) == n                                                            # all from the cache the second time


def test_a_failing_overpass_is_left_alone_after_two_tiles(tmp_path, monkeypatch):
    calls = []

    def fail(q, t):
        calls.append(1)
        raise RuntimeError("busy")
    monkeypatch.setattr(pmap, "_post_overpass", fail)
    monkeypatch.setattr(pmap, "_sleep", lambda s: None)
    r = ps.fetch((39.90, -75.30, 40.00, -75.10), cache_dir=tmp_path)
    assert len(calls) == 2 and r["missing"]


def test_make_stores_the_blob_and_the_registry_publishes_it(tmp_path, monkeypatch):
    monkeypatch.setattr(pmap, "fetch_buildings", lambda tb, **kw: BLD if tuple(tb) == tuple(pmap.tile_boxes(BBOX, *pmap.BLD_TILE)[0]) else {"elements": [], "missing": []})
    monkeypatch.setattr(ps, "fetch", lambda box, **kw: ST)
    h, size = ps.make(BBOX, cache_dir=tmp_path)
    assert len(h) == 12 and size > 500
    name = ps.file_name(h)
    got = {(f, n): t for f, n, t in palace_assets.assets()}
    assert got[("street", name)] == (ps.blob_dir() / name).read_text("utf-8") and ps.blob_hash(got[("street", name)]) == h
    ctype, text = palace_assets.find("/street/" + name + "?x=1")
    assert ctype.startswith("application/json") and json.loads(text)["v"] == 1
    assert palace_assets.find("/street/palace-street-000000000000.json") is None
    (ps.blob_dir() / "palace-street-aaaaaaaaaaaa.json").write_text("damaged", "utf-8")     # a file that does not match its hash is never published
    assert all(n != "palace-street-aaaaaaaaaaaa.json" for _f, n, _t in palace_assets.assets())
    # the site writes it, keeps it for a year
    from alto.publish_static import regenerate_site, _headers
    from alto.store.local import LocalStore
    site = tmp_path / "site"
    regenerate_site(LocalStore(tmp_path / "store"), "local", site)
    assert (site / "street" / name).read_text("utf-8") == got[("street", name)]
    rule = next(x for x in _headers("c", "c") if x["source"] == "/street/**")
    assert {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"} in rule["headers"]


def test_the_page_grows_by_a_hash_and_nothing_else(tmp_path, monkeypatch):
    monkeypatch.setattr(pmap, "fetch_buildings", lambda tb, **kw: BLD if tuple(tb) == tuple(pmap.tile_boxes(BBOX, *pmap.BLD_TILE)[0]) else {"elements": [], "missing": []})
    monkeypatch.setattr(ps, "fetch", lambda box, **kw: ST)
    m = {"bbox": list(BBOX)}
    ps.attach(m, BBOX, cache_dir=tmp_path)
    assert set(m) == {"bbox", "street"} and len(m["street"]["h"]) == 12
    assert len(json.dumps({"street": m["street"]}, separators=(",", ":"))) - 2 <= 40            # the added field, in bytes of JSON (the packed page grows less)
    m2 = {"bbox": [0.0, 0.0, 0.001, 0.001]}                                                     # an empty box: nothing added
    ps.attach(m2, (0.0, 0.0, 0.001, 0.001), cache_dir=tmp_path)
    assert "street" not in m2


@pytest.mark.skipif(not NODE.exists(), reason="node not on this machine")
def test_the_js_decoder_agrees_with_the_python_one(tmp_path):
    blob = ps.build(BBOX, BLD, ST)
    (tmp_path / "blob.json").write_text(ps.encode(blob), "utf-8")
    (tmp_path / "street.js").write_text(STREET_JS, "utf-8")
    probe = tmp_path / "probe.js"
    probe.write_text("""
global.window = global; const fs = require('fs');
require('./street.js');
const B = JSON.parse(fs.readFileSync('blob.json', 'utf8')); _palStreet.use(B);
const out = {cells: {}};
for (const k of Object.keys(B.c)) { const [ix, iy] = k.split(',').map(Number); out.cells[k] = _palStreet.cell(ix, iy); }
const x = (-75.1700 - B.o[1]) * B.kx, y = (39.9500 - B.o[0]) * B.ky;
const n = _palStreet.near(x + 5, y + 5, 40);
out.near = {b: n.b.length, t: n.t.length, f: n.f.length, p: n.p.length, e: n.e.length, r: n.r.length};
const far = _palStreet.near(x + 5, y + 5, 40, 't'); out.onlyTrees = far.t.length + far.b.length;
const ll = _palStreet.toLatLon(..._palStreet.fromLatLon(39.951, -75.16)); out.ll = ll;
out.attr = _palStreet.attribution();
process.stdout.write(JSON.stringify(out));
""", "utf-8")
    r = subprocess.run([str(NODE), "probe.js"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    js = json.loads(r.stdout)
    for k in blob["c"]:
        py = ps.decode_cell(blob, k)
        for kind in "brtfpe":
            assert len(js["cells"][k][kind]) == len(py[kind])
        for a, b in zip(js["cells"][k]["b"], py["b"]):
            assert a["nm"] == b["nm"] and a["k"] == b["k"] and a["lv"] == b["lv"] and a["h"] == b["h"]
            assert all(abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6 for p, q in zip(a["ring"], b["ring"]))
        for a, b in zip(js["cells"][k]["r"], py["r"]):
            assert a["hw"] == b["hw"] and a["wd"] == b["wd"] and a["ln"] == b["ln"] and len(a["line"]) == len(b["line"])
    assert js["near"]["b"] >= 1 and js["near"]["t"] == 2 and js["near"]["f"] >= 1 and js["onlyTrees"] == 2
    assert abs(js["ll"][0] - 39.951) < 1e-9 and abs(js["ll"][1] + 75.16) < 1e-9
    assert js["attr"] == ps.ATTRIBUTION


@pytest.mark.skipif(not QA_BLD.exists(), reason="the QA kit's Philadelphia building tiles are not on this machine")
def test_size_on_real_philadelphia_buildings(tmp_path):
    tile = QA_BLD / "bld-39.9489_-75.1731_39.9633_-75.1505.json"
    bld = json.loads(tile.read_text("utf-8"))
    bbox = (39.9489, -75.1731, 39.9633, -75.1505)
    blob = ps.build(bbox, bld, {"elements": []})
    text = ps.encode(blob)
    gz = len(gzip.compress(text.encode(), 6))
    km2 = (0.0144 * 110.574) * (0.0226 * 85.4)
    per_km2 = gz / km2
    print("PHILLY buildings only: %d buildings, %d bytes json, %d gz, %.0f KB gz per km2 (%.2f km2)" % (sum(len(c.get("b", [])) for c in blob["c"].values()), len(text), gz, per_km2 / 1000, km2))
    assert per_km2 < 150_000
