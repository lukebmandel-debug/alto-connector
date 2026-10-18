"""2.0.0 street data for the first-person view: palace_street.py (Overpass -> hosted content-hashed blob), its registration in palace_assets / publish_static and the
JS decoder (palace_street_js.py). Overpass is stubbed (no network); the size check runs on the real Philadelphia building tiles when the QA kit has them."""
import gzip
import json
import os
import time
import shutil
import subprocess
from pathlib import Path

import pytest

from alto import palace_map as pmap
from alto.build import palace_assets, palace_street as ps, palace_street_style as sty
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
    {"type": "way", "id": 32, "nodes": [100, 101], "tags": {"highway": "primary", "bridge": "yes", "layer": "1", "sidewalk:left": "yes", "sidewalk:right": "no", "cycleway:right": "track"},
     "geometry": _geom((39.9540, -75.1700), (39.9540, -75.1695))},
    {"type": "node", "id": 100, "lat": 39.9540, "lon": -75.1700, "tags": {"highway": "traffic_signals", "traffic_signals:direction": "forward"}},
    {"type": "node", "id": 101, "lat": 39.9540, "lon": -75.1695, "tags": {"highway": "stop", "direction": "270"}},
    {"type": "way", "id": 40, "geometry": _sq(39.9570, -75.1620, 0.001), "tags": {"leisure": "park", "name": "Little Park"}},
    {"type": "way", "id": 41, "geometry": _sq(39.9580, -75.1600, 0.0003), "tags": {"leisure": "pitch", "sport": "soccer", "surface": "grass"}},
    {"type": "way", "id": 42, "geometry": _sq(39.9585, -75.1590, 0.0003), "tags": {"amenity": "parking"}},
    {"type": "way", "id": 43, "geometry": _geom((39.9590, -75.1700), (39.9590, -75.1690)), "tags": {"barrier": "fence", "height": "1.8", "material": "metal"}},
    {"type": "way", "id": 44, "geometry": _geom((39.9592, -75.1700), (39.9592, -75.1690)), "tags": {"natural": "tree_row", "genus": "Platanus"}},
    {"type": "way", "id": 31, "tags": {"highway": "construction"}, "geometry": _geom((39.95, -75.17), (39.95, -75.16))},
]}


def _shards_of(man, shards):
    return {k: ps.decode_cell(man, k, shards) for k in man["c"]}


def test_the_query_asks_for_every_feature_kind_politely():
    q = ps.street_query((39.95, -75.17, 39.96, -75.16))
    for w in ("natural=tree", "street_lamp|traffic_signals|crossing|stop|bus_stop", "bench|bicycle_parking|waste_basket|post_box|fire_hydrant", "emergency=fire_hydrant",
              "node[entrance]", "node[door]", "shop|amenity|tourism|office", "way[highway]", "out center", "out geom", "barrier~", "tree_row", "leisure~", "amenity=parking"):
        assert w in q


def test_tags_are_parsed():
    assert len(ps.parse_buildings(BLD)) == 5
    st = ps.parse_street(ST)
    assert [t[3] for t in st["trees"]] == ["Platanus x acerifolia", "Quercus"]
    assert sorted(f[3] for f in st["furn"]) == ["bench", "fire_hydrant", "post_box", "stop", "street_lamp", "traffic_signals", "traffic_signals"]
    assert sorted(d[3] for d in st["door"]) == ["door=hinged", "entrance=main"]
    assert sorted(p[3] for p in st["poi"]) == ["Cafe Uno", "Fresh Loaf"]
    assert sorted(h[2]["highway"] for h in st["hw"]) == ["primary", "residential"]            # the construction way is skipped
    assert len(st["areas"]) == 3 and len(st["barriers"]) == 1 and len(st["rows"]) == 1


def test_signal_direction_follows_the_way_or_the_tag():
    st = ps.parse_street(ST)
    f = {x[2]: x for x in st["furn"]}
    assert f[100][4] == 90                                     # forward along an east-going way
    assert f[101][4] == 270                                    # direction=270
    assert f[12][4] is None


def test_the_blob_round_trips_every_tag():
    man, shards = ps.build(BBOX, BLD, ST)
    assert man["v"] == 2 and man["a"] == ps.ATTRIBUTION and man["q"] == 0.1 and man["cs"] == 5000 and man["o"] == list(BBOX) and man["preset"] == "philadelphia"
    cells = _shards_of(man, shards)
    bs = [b for c in cells.values() for b in c["b"]]
    assert len(bs) == 4                                                              # the building outside the box is dropped
    house = next(b for b in bs if b["nm"] == "Rowhouse")
    assert (house["k"], house["lv"], house["colour"], house["material"], house["rs"], house["rm"], house["rl"], house["ad"], house["po"], house["sd"], house["wd"]) == \
        ("house", 3, sty.rgb565_to_hex(sty.colour565("#a05040")), "brick", "flat", "tar_paper", 1, "12 Walnut St", "shop=bakery", "1840", "Q1")
    assert house["rc"] == sty.colour565("grey") and house["fl"] & sty.FL_STOREFRONT and not house["fl"] & sty.FL_STYLED
    assert house["h"] == 105 and len(house["ring"]) == 4
    x0 = (-75.1700 - BBOX[1]) * man["kx"]
    y0 = (39.9500 - BBOX[0]) * man["ky"]
    assert abs(house["ring"][0][0] - x0) < 0.1 and abs(house["ring"][0][1] - y0) < 0.1
    part = next(b for b in bs if b["k"] == "p:roof")
    assert abs(part["h"] - 91) <= 1
    assert len(next(b for b in bs if b["k"] == "retail")["holes"]) == 1
    flat = {k: [x for c in cells.values() for x in c[k]] for k in "rtfpeawl"}
    assert [(t["sp"], t["lf"]) for t in flat["t"]] == [("Platanus x acerifolia", "broadleaved"), ("Quercus", "")]
    assert sorted(f["kind"] for f in flat["f"]) == ["bench", "fire_hydrant", "post_box", "stop", "street_lamp", "traffic_signals", "traffic_signals"]
    assert sorted(f["dir"] for f in flat["f"] if f["dir"] is not None) == [90, 270]
    assert sorted(e["kind"] for e in flat["e"]) == ["door=hinged", "entrance=main"]
    assert sorted((p["name"], p["cat"], p["ad"]) for p in flat["p"]) == [("Cafe Uno", "amenity=cafe", ""), ("Fresh Loaf", "shop=bakery", "14 Walnut St")]
    roads = [r for r in flat["r"] if r["hw"] == "residential"]
    assert all((r["nm"], r["ln"], r["wd"], r["ow"], r["sw"], r["cy"], r["sf"], r["ms"], r["lt"], r["br"]) == ("Walnut St", 2, 70, 1, "both", "lane", "asphalt", "25 mph", 1, 0) for r in roads)
    assert len(roads) >= 2
    assert abs(roads[0]["line"][0][0] - (-75.1730 - BBOX[1]) * man["kx"]) < 0.1
    assert abs(roads[-1]["line"][-1][0] - (-75.1510 - BBOX[1]) * man["kx"]) < 0.1
    ends = {(round(r["line"][-1][0], 1), round(r["line"][-1][1], 1)) for r in roads}
    assert all((round(r["line"][0][0], 1), round(r["line"][0][1], 1)) in ends for r in roads[1:])
    br = next(r for r in flat["r"] if r["hw"] == "primary")
    assert (br["br"], br["tn"], br["la"], br["sl"], br["sr"], br["cl"], br["cr"]) == (1, 0, 1, "yes", "no", "", "track")
    assert sorted((a["k"], a["nm"], a["sp"], a["sf"]) for a in flat["a"]) == \
        sorted([("parking", "", "", ""), ("park", "Little Park", "", ""), ("pitch", "", "soccer", "grass")])
    w = flat["w"][0]
    assert (w["k"], w["mt"]) == ("fence", "metal") and abs(w["ht"] - 1.8) < 0.06 and len(w["line"]) == 2
    assert (flat["l"][0]["sp"], flat["l"][0]["lf"]) == ("Platanus", "")


def test_sharding_and_chunking():
    man, shards = ps.build(BBOX, BLD, ST)
    assert man["n"] == [ps.Frame(BBOX).nx, ps.Frame(BBOX).ny] and man["g"] == 2
    assert set(man["f"]) == set(shards) and set(man["c"].values()) == set(shards)
    for sid, sh in shards.items():
        text = ps.encode(sh)
        assert ps.blob_hash(text, 8) == sid and man["f"][sid] == len(text.encode()) and sh["S"][0] == "" and len(set(sh["S"])) == len(sh["S"])   # own string table, no repeats
        ids = {ps.decode_cell(man, k, shards) is not None and man["c"][k] for k in sh["c"]}
        assert ids == {sid}
        for key in sh["c"]:
            ix, iy = (int(v) for v in key.split(","))
            assert (ix // 2, iy // 2) == (int(next(iter(sh["c"])).split(",")[0]) // 2, int(next(iter(sh["c"])).split(",")[1]) // 2)       # one 2 x 2 group per shard
    assert len(shards) >= 2                                                           # the data spans more than one 1 km square
    for key in man["c"]:
        ix, iy = (int(v) for v in key.split(","))
        c = ps.decode_cell(man, key, shards)
        for b in c["b"]:
            cx = sum(p[0] for p in b["ring"]) / len(b["ring"])
            cy = sum(p[1] for p in b["ring"]) / len(b["ring"])
            assert ix * 500 <= cx < (ix + 1) * 500 and iy * 500 <= cy < (iy + 1) * 500
    assert ps.decode_cell(man, "0,0", {}) is None or man["c"].get("0,0") is None           # not loaded: None; absent: an empty cell
    assert ps.decode_cell(man, "99,99", {})["b"] == []


def test_the_same_data_gives_the_same_hash_whatever_the_order():
    def hashes(b, s):
        man, shards = ps.build(BBOX, b, s)
        return ps.blob_hash(ps.encode(man)), sorted(shards)
    a = hashes(BLD, ST)
    b = hashes({"elements": list(reversed(BLD["elements"]))}, {"elements": list(reversed(ST["elements"]))})
    assert a == b and len(a[0]) == 12 and all(len(x) == 8 for x in a[1])
    changed = {"elements": [dict(e) for e in ST["elements"]]}
    changed["elements"][0] = dict(changed["elements"][0], lat=39.9502)
    assert hashes(BLD, changed)[0] != a[0]
    assert ps.url_of(a[0]) == "/street/palace-street-%s.json" % a[0] and ps.url_of(a[1][0]) == "/street/s-%s.json" % a[1][0]


def test_a_repeated_word_is_stored_once_and_it_is_small():
    els = [{"type": "way", "id": i, "geometry": _sq(39.9500 + (i % 20) * 0.0003, -75.1700 + (i // 20) * 0.0003, 0.0002),
            "tags": {"building": "house", "building:material": "brick", "roof:shape": "flat", "addr:street": "Walnut St", "addr:housenumber": str(i)}} for i in range(400)]
    man, shards = ps.build(BBOX, {"elements": els}, {"elements": []})
    for sh in shards.values():
        assert sh["S"].count("flat") <= 1 and sh["S"].count("house") <= 1 and sh["S"].count("Walnut St") == 0       # (the address is one string "12 Walnut St")
    total = sum(man["f"].values())
    assert len(gzip.compress("".join(ps.encode(s) for s in shards.values()).encode())) < 150_000 and total / 400 < 110


# ── the style resolver ───────────────────────────────────────────────────────
def test_osm_values_win_and_the_gaps_are_filled():
    r = sty.resolve("philadelphia", {"building": "house", "building:colour": "#336699", "building:material": "stone"}, 90, 9.0, 3, 7)
    assert r["bc"] == sty.colour565("#336699") and r["bm"] == sty.MAT["stone"] and r["lv"] == 3 and r["h"] == 9.0 and not r["fl"] & (sty.FL_LEVELS | sty.FL_HEIGHT | sty.FL_STYLED)
    r = sty.resolve("philadelphia", {"building": "house"}, 90, 0.0, 0, 7)
    assert r["lv"] == 3 and r["h"] > 8 and r["fl"] & sty.FL_LEVELS and r["fl"] & sty.FL_HEIGHT and r["fl"] & sty.FL_STYLED and r["bc"] and r["bm"]
    assert sty.resolve("philadelphia", {"building": "yes"}, 90, 9.9, 0, 7)["lv"] == 3           # levels from a known height
    assert sty.resolve("philadelphia", {"building": "yes"}, 90, 0.0, 4, 7)["h"] == 13.2         # height from known levels


def test_the_philadelphia_mix_and_the_other_kinds():
    mats = [sty.MATERIALS[sty.resolve("philadelphia", {"building": "house"}, 80, 10.0, 3, sty.seed_of(i))["bm"]] for i in range(400)]
    assert 0.6 < mats.count("brick") / 400 < 0.85 and mats.count("brownstone") > 10 and mats.count("stucco") > 5 and mats.count("painted") > 2
    tall = {sty.MATERIALS[sty.resolve("philadelphia", {"building": "office"}, 1500, 120.0, 30, sty.seed_of(i))["bm"]] for i in range(200)}
    assert tall <= {"glass", "metal", "concrete"} and "glass" in tall
    assert sty.MATERIALS[sty.resolve("philadelphia", {"building": "yes", "start_date": "1880", "height": "40"}, 1500, 40.0, 0, 3)["bm"]] == "stone"
    civ = sty.resolve("philadelphia", {"building": "cathedral", "name": "Old St"}, 1200, 0.0, 0, 5)
    assert sty.MATERIALS[civ["bm"]] in ("stone", "brick") and civ["lv"] >= 3
    assert sty.resolve("philadelphia", {"building": "retail"}, 300, 6.0, 1, 5)["fl"] & sty.FL_STOREFRONT
    assert sty.resolve("philadelphia", {"building": "yes"}, 300, 6.0, 1, 5, commercial=True)["fl"] & sty.FL_STOREFRONT
    assert not sty.resolve("philadelphia", {"building": "house"}, 80, 9.0, 3, 5)["fl"] & sty.FL_STOREFRONT
    assert sty.resolve("philadelphia", {"building": "house"}, 80, 9.0, 3, 11) == sty.resolve("philadelphia", {"building": "house"}, 80, 9.0, 3, 11)     # stable
    assert sty.preset_for(BBOX) == "philadelphia" and sty.preset_for((48.8, 2.3, 48.9, 2.4)) == "generic"
    g = sty.resolve("generic", {"building": "house"}, 80, 9.0, 3, 5)
    assert g["bc"] and g["bm"]
    assert sty.rgb565_to_hex(sty.rgb565((150, 70, 55))).startswith("#")


def test_a_storefront_is_found_from_a_shop_standing_inside_the_footprint():
    bld = {"elements": [{"type": "way", "id": 7, "geometry": _sq(39.9507, -75.1694, 0.0003), "tags": {"building": "yes"}},
                        {"type": "way", "id": 8, "geometry": _sq(39.9507, -75.1650, 0.0003), "tags": {"building": "yes"}}]}
    man, shards = ps.build(BBOX, bld, ST)
    bs = [b for c in _shards_of(man, shards).values() for b in c["b"]]
    assert sorted(b["storefront"] for b in bs) == [False, True]            # Fresh Loaf (39.9507, -75.1693) stands in the first one only


# ── fetching ─────────────────────────────────────────────────────────────────
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
    assert len(asked) == n


def test_a_failing_overpass_is_left_alone_after_two_tiles(tmp_path, monkeypatch):
    calls = []

    def fail(q, t):
        calls.append(1)
        raise RuntimeError("busy")
    monkeypatch.setattr(pmap, "_post_overpass", fail)
    monkeypatch.setattr(pmap, "_sleep", lambda s: None)
    r = ps.fetch((39.90, -75.30, 40.00, -75.10), cache_dir=tmp_path)
    assert len(calls) == 2 and r["missing"]


def _stub(monkeypatch, bld=BLD, st=ST):
    first = tuple(pmap.tile_boxes(BBOX, *pmap.BLD_TILE)[0])
    monkeypatch.setattr(pmap, "fetch_buildings", lambda tb, **kw: bld if tuple(tb) == first else {"elements": [], "missing": []})
    monkeypatch.setattr(ps, "fetch", lambda box, **kw: st)


def test_make_stores_the_files_and_only_referenced_ones_are_published(tmp_path, monkeypatch):
    _stub(monkeypatch)
    h, size = ps.make(BBOX, cache_dir=tmp_path)
    man, shards = ps.load(h)
    assert len(h) == 12 and size == len(ps.encode(man).encode()) + sum(man["f"].values())
    got = {(f, n): t for f, n, t in palace_assets.assets()}
    assert ("street", ps.file_name(h)) in got and all(("street", ps.file_name(sid)) in got for sid in shards)
    assert all(ps.blob_hash(t) == n[len("palace-street-"):-5] for (f, n), t in got.items() if f == "street" and n.startswith("palace"))
    ctype, text = palace_assets.find("/street/" + ps.file_name(h) + "?x=1")
    assert ctype.startswith("application/json") and json.loads(text)["v"] == 2
    assert palace_assets.find("/street/palace-street-000000000000.json") is None
    # a damaged file, an orphan shard, and an older manifest of the same box are not published
    (ps.blob_dir() / "palace-street-aaaaaaaaaaaa.json").write_text("damaged", "utf-8")
    ps._write(ps.blob_dir(), "s-bbbbbbbb.json", "{}")
    names = {n for f, n, _t in palace_assets.assets() if f == "street"}
    assert "palace-street-aaaaaaaaaaaa.json" not in names and "s-bbbbbbbb.json" not in names
    st2 = {"elements": ST["elements"][:3]}
    _stub(monkeypatch, st=st2)
    h2, _s = ps.make(BBOX, cache_dir=tmp_path)
    assert h2 != h
    old_ = ps.blob_dir() / ps.file_name(h)
    os.utime(old_, (time.time() - 40 * 86400,) * 2)           # (an older manifest that no page names and that is not recent is dropped; a referenced or recent one stays: test_palace_street_publish.py)
    names = {n for f, n, _t in palace_assets.assets() if f == "street"}
    assert ps.file_name(h2) in names and ps.file_name(h) not in names
    # the site writes exactly those, keeps them for a year
    from alto.publish_static import regenerate_site, _headers
    from alto.store.local import LocalStore
    site = tmp_path / "site"
    (site / "street").mkdir(parents=True)
    (site / "street" / "s-cccccccc.json").write_text("old", "utf-8")
    regenerate_site(LocalStore(tmp_path / "store"), "local", site)
    assert {p.name for p in (site / "street").iterdir()} == names
    rule = next(x for x in _headers("c", "c", sorted(names)) if x["source"].startswith("/street/"))      # (only files that exist are kept for a year: test_palace_street_publish.py)
    assert {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"} in rule["headers"]


def test_the_page_grows_by_a_hash_and_nothing_else(tmp_path, monkeypatch):
    _stub(monkeypatch)
    m = {"bbox": list(BBOX)}
    ps.attach(m, BBOX, cache_dir=tmp_path)
    assert set(m) == {"bbox", "street"} and len(m["street"]["h"]) == 12
    assert len(json.dumps({"street": m["street"]}, separators=(",", ":"))) - 2 <= 41
    m2 = {"bbox": [0.0, 0.0, 0.001, 0.001]}
    ps.attach(m2, (0.0, 0.0, 0.001, 0.001), cache_dir=tmp_path)
    assert "street" not in m2


@pytest.mark.skipif(not NODE.exists(), reason="node not on this machine")
def test_the_js_decoder_agrees_with_the_python_one_and_loads_shards_on_demand(tmp_path):
    man, shards = ps.build(BBOX, BLD, ST)
    for sid, sh in shards.items():
        (tmp_path / ("s-%s.json" % sid)).write_text(ps.encode(sh), "utf-8")
    (tmp_path / "man.json").write_text(ps.encode(man), "utf-8")
    (tmp_path / "street.js").write_text(STREET_JS, "utf-8")
    (tmp_path / "probe.js").write_text("""
global.window = global; const fs = require('fs'); const path = require('path');
global.fetch = (u) => { const f = path.join(process.cwd(), path.basename(u)); fs.appendFileSync('log.txt', path.basename(u) + '\\n');
  return Promise.resolve(fs.existsSync(f) ? {ok: true, status: 200, json: () => Promise.resolve(JSON.parse(fs.readFileSync(f, 'utf8')))} : {ok: false, status: 404}); };
require('./street.js');
const out = {};
(async () => {
  await _palStreet.load('/street/man.json');
  const M = JSON.parse(fs.readFileSync('man.json', 'utf8'));
  const x = (-75.1700 - M.o[1]) * M.kx, y = (39.9500 - M.o[0]) * M.ky;
  out.before = _palStreet.near(x, y, 40).b.length;                      // shards not loaded: nothing, no throw
  out.undef = Object.keys(M.c).some(k => _palStreet.cell(...k.split(',').map(Number)) === undefined);
  out.loadedBefore = _palStreet.loaded(x, y, 40);
  await _palStreet.need(x, y, 40);
  out.loadedAfter = _palStreet.loaded(x, y, 40);
  out.fetched = fs.readFileSync('log.txt', 'utf8').trim().split('\\n');
  const n = _palStreet.near(x + 5, y + 5, 40);
  out.near = {b: n.b.length, t: n.t.length, f: n.f.length, p: n.p.length, e: n.e.length, r: n.r.length};
  out.house = n.b.find(b => b.nm === 'Rowhouse');
  await Promise.all(Object.keys(M.f).map(id => _palStreet.need(...(() => { const k = Object.keys(M.c).find(c => M.c[c] === id).split(',').map(Number); return [(k[0] + .5) * 500, (k[1] + .5) * 500, 1]; })())));
  out.cells = {}; for (const k of Object.keys(M.c)) out.cells[k] = _palStreet.cell(...k.split(',').map(Number));
  const ll = _palStreet.toLatLon(..._palStreet.fromLatLon(39.951, -75.16)); out.ll = ll; out.attr = _palStreet.attribution();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
""", "utf-8")
    r = subprocess.run([str(NODE), "probe.js"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    js = json.loads(r.stdout)
    assert js["before"] == 0 and js["undef"] and js["loadedBefore"] is False and js["loadedAfter"] is True
    assert js["fetched"][0] == "man.json" and len(js["fetched"]) >= 2 and len(set(js["fetched"])) == len(js["fetched"]) and len(js["fetched"]) - 1 < len(shards) + 1
    assert js["house"]["colour"] == sty.rgb565_to_hex(sty.colour565("#a05040")) and js["house"]["material"] == "brick" and js["house"]["storefront"] is True
    assert js["near"]["b"] >= 1 and js["near"]["t"] == 2 and js["near"]["f"] >= 1
    for k in man["c"]:
        py = ps.decode_cell(man, k, shards)
        for kind in "brtfpeawl":
            assert len(js["cells"][k][kind]) == len(py[kind]), (k, kind)
        for a, b in zip(js["cells"][k]["b"], py["b"]):
            assert all(a[f] == b[f] for f in ("nm", "k", "lv", "h", "bc", "bm", "rc", "fl", "mh", "colour", "material"))
            assert all(abs(p[0] - q[0]) < 1e-6 and abs(p[1] - q[1]) < 1e-6 for p, q in zip(a["ring"], b["ring"]))
        for a, b in zip(js["cells"][k]["r"], py["r"]):
            assert all(a[f] == b[f] for f in ps.RFIELDS) and len(a["line"]) == len(b["line"])
        assert [f["dir"] for f in js["cells"][k]["f"]] == [f["dir"] for f in py["f"]]
        assert [(a["k"], a["nm"], a["sp"]) for a in js["cells"][k]["a"]] == [(a["k"], a["nm"], a["sp"]) for a in py["a"]]
    assert abs(js["ll"][0] - 39.951) < 1e-9 and abs(js["ll"][1] + 75.16) < 1e-9 and js["attr"] == ps.ATTRIBUTION


@pytest.mark.skipif(not QA_BLD.exists(), reason="the QA kit's Philadelphia building tiles are not on this machine")
def test_size_on_real_philadelphia_buildings():
    bld = json.loads((QA_BLD / "bld-39.9489_-75.1731_39.9633_-75.1505.json").read_text("utf-8"))
    bbox = (39.9489, -75.1731, 39.9633, -75.1505)
    man, shards = ps.build(bbox, bld, {"elements": []})
    gz = sum(len(gzip.compress(ps.encode(s).encode(), 6)) for s in shards.values()) + len(gzip.compress(ps.encode(man).encode(), 6))
    km2 = (0.0144 * 110.574) * (0.0226 * 85.4)
    print("PHILLY buildings only: %d buildings, %d shards, %d bytes json, %d gz, %.0f KB gz per km2" % (sum(len(c.get("b", [])) for s in shards.values() for c in s["c"].values()),
          len(shards), sum(man["f"].values()), gz, gz / km2 / 1000))
    assert gz / km2 < 150_000
