"""City tiles (palace_tiles.py): the base and the detail tiles off the page, the loader, the publish folder."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace, palace_tiles as pt  # noqa: E402
from alto.build.builder import build_timeline  # noqa: E402
from alto.build.single_file import private_page  # noqa: E402
from alto.hosted import hosted_timeline  # noqa: E402
from tests.test_palace import bundle, load  # noqa: E402

PAL = re.compile(r"window\._ALTO_PALACE=(\{.*?\});\n", re.S)


def _map():
    """Two cells: one inside the zone (cells 0..0), one well outside it (cell 5,0)."""
    far = 5 * pt.CELL + 100
    return {"W": 6 * pt.CELL, "H": pt.CELL, "streets": [
        {"n": "Near St", "k": 2, "p": [100, 100, 900, 100]},
        {"n": "Far St", "k": 2, "p": [far, 100, far + 800, 100]},
        {"n": "Far Ave", "k": 0, "L": 1, "p": [far, 300, far + 800, 300]},          # a heavy lattice line: overview, base
        {"n": "Far Bridge", "k": 3, "o": 1, "p": [far, 500, far + 800, 500]}],      # a bridge: base
        "tiles": [[100, 100, 400, 250], [far, 100, far + 300, 250]],
        "tq": [[far, 600, far + 200, 600, far + 200, 800, far, 800]],
        "te": [[far, 900, far + 200, 900], [far, 1000, far + 5000, 1000]],          # the long one is an avenue-sized line: base
        "edges": [], "tcut": [], "parks": [
            {"n": "Small", "z": 1, "r": [[far, 1200, far + 100, 1200, far + 100, 1300, far, 1300]]},
            {"n": "Big", "z": 4, "r": [[far, 1400, far + 900, 1400, far + 900, 1900, far, 1900]]}]}


def test_cut_moves_the_detail_outside_the_zone_into_tiles(monkeypatch, tmp_path):
    monkeypatch.setattr(pt, "zone_cells", lambda m, d: [0, 0, 0, 0])
    m = _map()
    blocks = [{"id": 0, "x": 200, "y": 200, "lots": [[200, 200, 50, 40, 0]]}, {"id": 1, "x": 5 * pt.CELL + 200, "y": 200, "lots": []}]
    kept, st = pt.cut(m, blocks, [], fill={"parts": {"5,0": {"L": ["", "", "", ""], "h": ["", ""], "n": [["", ""], ["", ""]], "c": [0, 0, 0, 0]}}},
                      directory=tmp_path)
    assert [s["n"] for s in m["streets"]] == ["Near St", "Far Ave", "Far Bridge"]
    assert m["tiles"] == [[100, 100, 400, 250]] and m["tq"] == [] and len(m["te"]) == 1
    assert [p["n"] for p in m["parks"]] == ["Big"]
    assert [b["id"] for b in kept] == [0]
    assert m["ct"]["zone"] == [0, 0, 0, 0] and list(m["ct"]["c"]) == ["5,0"] and st["tiles"] == 1
    t = json.loads((tmp_path / ("t-%s.json" % m["ct"]["c"]["5,0"])).read_text())
    assert [s["n"] for s in t["streets"]] == ["Far St"] and len(t["tiles"]) == 1 and len(t["tq"]) == 1 and len(t["te"]) == 1
    assert [p["n"] for p in t["parks"]] == ["Small"] and t["f"]["c"] == [0, 0, 0, 0]
    assert "tcut" not in m


def test_a_big_cell_is_split_into_quarters(monkeypatch, tmp_path):
    monkeypatch.setattr(pt, "zone_cells", lambda m, d: [0, 0, 0, 0])
    monkeypatch.setattr(pt, "TILE_MAX", 300)
    m = _map()
    far = 5 * pt.CELL
    m["te"] += [[far + x, y, far + x + 50, y] for x in (100, 1500) for y in range(50, 1900, 37)]
    pt.cut(m, [], [], directory=tmp_path)
    keys = sorted(m["ct"]["c"])
    assert all(k.startswith("5,0/") for k in keys) and len(keys) >= 2
    for k in keys:
        assert (tmp_path / ("t-%s.json" % m["ct"]["c"][k])).is_file()


def test_the_site_page_loads_its_city_from_cmap():
    html, _ = build_timeline(*load(bundle()))
    assert pt.MARK0 in html and pt.MARK1 in html                     # timeline.html / offline: the city inline, as before
    full = json.loads(PAL.search(html).group(1))
    b, _n, _c = load(bundle())
    for page in (private_page(b, html), hosted_timeline(html, "test-palace")):
        assert pt.MARK0 not in page and "window._ALTO_CITY_F" not in page
        core = json.loads(PAL.search(page).group(1))
        assert core["at"] == full["at"] and core["num"] == full["num"] and core["b"] == []
        assert "streets" not in core["m"] and core["m"]["W"] == full["m"]["W"]
        assert re.fullmatch(r"b-[0-9a-f]{12}", core["cb"])
        assert "'/cmap/'+P.cb+'.json'" in page
        base = json.loads((pt.blob_dir() / (core["cb"] + ".json")).read_text())
        assert base["m"]["streets"] == full["m"]["streets"] and base["b"] == full["b"]
        assert pt.page_refs(page) == {core["cb"] + ".json"}
    assert pt.LAST_BASE["gz"] < pt.BASE_MAX


def test_strip_is_a_no_op_without_a_city():
    assert pt.strip("<script>var x=1;</script>") == "<script>var x=1;</script>"


def test_blobs_keep_every_published_base_and_its_tiles(tmp_path):
    t = pt.text_of({"v": 1, "k": "1,1"})
    tn = "t-%s.json" % pt.digest(t, 10)
    pt.store(tn, t, tmp_path)
    b = pt.text_of({"v": 1, "m": {"ct": {"c": {"1,1": tn[2:-5]}}}, "b": []})
    bn = "b-%s.json" % pt.digest(b, 12)
    pt.store(bn, b, tmp_path)
    got = dict(pt.blobs({bn}, tmp_path))
    assert set(got) == {bn, tn} and not pt.LAST_MISSING
    assert dict(pt.blobs(set(), tmp_path)).keys() == {bn, tn}          # published once, kept (a share still names it)
    missing = "b-%s.json" % ("0" * 12)
    pt.blobs({missing}, tmp_path)
    assert pt.LAST_MISSING == [missing]


def test_the_site_headers_keep_bases_a_year_and_tiles_a_day():
    from alto.publish_static import _cmap_rules
    r = _cmap_rules(["b-0123456789ab.json", "t-0123456789.json", "x.json"])
    assert r[0]["source"] == "/cmap/b-0123456789ab.json" and "immutable" in r[0]["headers"][0]["value"]
    assert r[1]["regex"].startswith("^/cmap/t-") and "86400" in r[1]["headers"][0]["value"] and len(r) == 2


def test_the_tiles_loader_splices_into_the_palace_script():
    js = pt.patch_js(palace.PALACE_JS)
    assert "function ctTick(){" in js and "ctDrawAll(svg);\n  svg._b=bg;" in js
    assert "CT_ON" not in js and str(pt.CT_ON) in js


def test_a_palace_with_tiles_gets_the_loader(monkeypatch, tmp_path):
    d = bundle()
    data = palace.unpack(d["brief"]["palace"]["data_z"])
    data["map"]["ct"] = {"v": 1, "cell": pt.CELL, "zone": [0, 0, 0, 0], "c": {"9,9": "0123456789"}}
    d["brief"]["palace"]["data_z"] = palace.pack(data)
    html, _ = build_timeline(*load(d))
    assert "function ctTick(){" in html and ".pal-svg g.ct.ct-off{display:none;}" in html
    plain, _ = build_timeline(*load(bundle()))
    assert "function ctTick(){" not in plain


def test_find_serves_the_blob_folder():
    t = pt.text_of({"v": 1, "k": "0,0"})
    n = "t-%s.json" % pt.digest(t, 10)
    pt.store(n, t)
    assert pt.find("/cmap/" + n) == ("application/json; charset=utf-8", t)
    assert pt.find("/cmap/../secret") is None and pt.find("/street/x.json") is None



def test_tiles_live_on_the_shared_host_and_bases_on_each_site(monkeypatch, tmp_path):
    t = pt.text_of({"v": 1, "k": "1,1"})
    tn = "t-%s.json" % pt.digest(t, 10)
    pt.store(tn, t, tmp_path)
    b = pt.text_of({"v": 1, "m": {"ct": {"c": {"1,1": tn[2:-5]}}}, "b": []})
    bn = "b-%s.json" % pt.digest(b, 12)
    pt.store(bn, b, tmp_path)
    monkeypatch.setenv("ALTO_TILE_HOST", "https://alto-connector.web.app")
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "luke-alto")
    assert dict(pt.blobs({bn}, tmp_path)).keys() == {bn} and not pt.LAST_MISSING      # a user's site: its bases only
    monkeypatch.setenv("ALTO_FIREBASE_SITE", "alto-connector")
    assert tn in dict(pt.blobs(set(), tmp_path))                                       # the host: every tile
    from alto.publish_static import _tile_src
    assert _tile_src() == " https://alto-connector.web.app"
    html, _ = build_timeline(*load(bundle()))
    b_, _n, _c = load(bundle())
    assert json.loads(PAL.search(private_page(b_, html)).group(1))["cu"] == "https://alto-connector.web.app"
    assert "(P.cu||'')+'/cmap/t-'" in pt.TILES_JS
