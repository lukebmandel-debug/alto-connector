"""Mind Palace towers (palace_towers.py): the skyscraper art, a landmark entry's `unit`/`floors`, a unit's
buildings becoming the tower's floors with real floor numbers, the elevator, edit mode, and that a palace with
no `unit` is unchanged. Runs on test_palace's synthetic city; nothing here touches the network or any ALTO_* setting."""
import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_landmarks as pl, palace_towers as pt  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
import test_palace as tp  # noqa: E402

NAME = "Comcast Technology Center"


def _bundle(unit=0, floors=60, extra=None):
    d = tp.bundle()
    m = tp.city_map()
    m["landmarks"].append({"n": NAME, "x": 700, "y": 200, "r": [], "box": [610, 120, 790, 330], "page": ""})
    d["brief"]["palace"]["data_z"] = palace.pack({"map": m, "blocks": tp.pp.lots(m)})
    if unit is not None:
        d["brief"]["palace"]["buildings"] = [{"name": NAME, **({"floors": floors} if floors else {}), "unit": unit}]
    if extra:
        d["brief"]["palace"]["buildings"] += extra
    return d


def _html(d):
    return build_timeline(*load_brief(copy.deepcopy(d)))[0]


# ── the module ──────────────────────────────────────────────────────────────
def test_every_tower_has_its_art_and_a_name_pattern():
    keys = {k for k, _, _ in pt.TOWERS}
    assert len(keys) == 8
    for k in keys:
        a = pl.ART[k]
        assert a["h"] > a["w"] * 1.8 and "<" in a["svg"] and "{s}" in a["svg"]        # tall and narrow
        assert "<script" not in a["svg"] and "<filter" not in a["svg"]
    for k, p in pl.MATCH:
        assert isinstance(re.compile(p, re.I), re.Pattern)
    for name, key in [("One Liberty Place", "lib1"), ("Two Liberty Place", "lib2"), ("Comcast Center", "ccc"),
                      ("Comcast Technology Center", "ctc"), ("BNY Mellon Center", "bny"), ("Three Logan Square", "tls"),
                      ("Cira Centre", "cira"), ("FMC Tower", "fmc")]:
        assert pt.tower_key(name) == key, name
    assert len({pl.ART[k]["svg"] for k in keys}) == 8                                  # each its own silhouette


def test_real_floor_counts():
    assert pt.real_floors({"name": "Comcast Technology Center"}) == 60
    assert pt.real_floors({"name": "Comcast Center"}) == 57
    assert pt.real_floors({"name": "One Liberty Place"}) == 61
    assert pt.real_floors({"name": "Two Liberty Place"}) == 58
    assert pt.real_floors({"name": "BNY Mellon Center"}) == 54
    assert pt.real_floors({"name": "Cira Centre"}) == 29
    assert pt.real_floors({"name": "Comcast Center", "floors": 70}) == 70


def test_floors_spread_between_2_and_the_roof():
    f = pt.floor_numbers([f"f{i}" for i in range(17)], 60)
    v = list(f.values())
    assert v[0] == 2 and v[-1] == 60 and v == sorted(v) and len(set(v)) == 17
    assert list(pt.floor_numbers(["a", "b", "c"], 3).values()) == [2, 3, 4]               # more floors than the tower has: it grows


@pytest.mark.parametrize("bad", [{"name": NAME, "unit": "1"}, {"name": NAME, "unit": 9}, {"name": NAME, "unit": 0, "floors": 1},
                                 {"name": NAME, "unit": 0, "floors": "60"}, {"name": NAME, "floors": 60}, {"unit": 0}])
def test_bad_landmark_entries_are_rejected(bad):
    d = tp.bundle()
    d["brief"]["palace"]["buildings"] = [bad]
    b, nodes, _ = tp.load(d)
    with pytest.raises(BriefError):
        palace.check_palace(b, [])


def test_one_tower_per_unit():
    d = tp.bundle()
    d["brief"]["palace"]["buildings"] = [{"name": NAME, "unit": 0}, {"name": "Cira Centre", "unit": 0}]
    b, _, _ = tp.load(d)
    with pytest.raises(BriefError, match="one tower"):
        palace.check_palace(b, [])


# ── the assignment ──────────────────────────────────────────────────────────
def test_a_units_buildings_become_the_towers_floors():
    b, nodes, _ = tp.load(_bundle())
    assert pt.apply_towers(b, nodes) == []
    by = {n.id: n for n in nodes}
    assert by["alpha"].parent == "" and by["beta"].parent == "alpha"             # the unit's first building is the tower
    assert by["alpha-1"].parent == "alpha" and by["alpha-2"].parent == "alpha-1"  # its own floors keep their nesting
    assert by["gamma"].parent == "" and by["delta"].parent == ""                 # other units untouched
    units, floors, of = palace.structure(b, nodes)
    assert units[0] == ["alpha"] and set(floors["alpha"]) == {"alpha-1", "alpha-2", "alpha-3", "beta"}
    tw, fn = pt.tower_data(b, units, floors)
    assert tw["alpha"]["top"] == 60 and tw["alpha"]["n"] == NAME
    nums = [fn[f] for f in floors["alpha"]]
    assert nums[0] == 2 and nums[-1] == 60 and nums == sorted(nums)
    num = palace.numbers(units, floors, fn)
    assert num["alpha"] == "1.1" and num["beta"] == "1.1-60" and num["alpha-1"] == "1.1-2"


def test_the_stored_nodes_are_not_touched_and_no_unit_means_no_change():
    d = _bundle()
    base = copy.deepcopy(d)
    _html(d)
    assert d == base
    plain = _bundle(unit=None)
    b, nodes, _ = tp.load(plain)
    assert pt.apply_towers(b, nodes) == []
    assert [n.parent for n in nodes] == [n.parent for n in tp.load(tp.bundle())[1]]
    html = _html(plain)
    assert '"tw":{}' in html and '"fn":{}' in html                                # a palace with no tower carries none
    assert NAME in html


def test_a_landmark_not_on_the_map_leaves_the_unit_alone():
    d = _bundle()
    d["brief"]["palace"]["buildings"][0]["name"] = "Nowhere Tower"
    b, nodes, _ = tp.load(d)
    w = pt.apply_towers(b, nodes)
    assert w and "not on the map" in w[0] and all(n.parent == o.parent for n, o in zip(nodes, tp.load(tp.bundle())[1]))


def test_an_empty_unit_gets_a_tower_of_its_own():
    d = _bundle(unit=2)
    d["nodes"] = [n for n in d["nodes"] if n["act"] != 2]
    b, nodes, _ = tp.load(d)
    w = pt.apply_towers(b, nodes)
    assert any(n.id == "tower-2" for n in nodes) and "empty tower" in w[-1]


def test_the_page_carries_the_tower():
    html = _html(_bundle())
    assert '"tw":{"alpha":{"n":"Comcast Technology Center","u":0,"top":60}}' in html
    assert "function towerOf" in html and "floorNo(" in html and "data-tower" in html
    assert "lib1" in html and "Tower of" in html


def test_set_up_palace_documents_unit_and_floors():
    from alto import mcp_server as srv
    doc = srv.set_up_palace.__doc__
    assert "unit" in doc and "floors" in doc and "TOWER" in doc


# ── in a browser ───────────────────────────────────────────────────────────
pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    f = tmp_path_factory.mktemp("paltw") / "page.html"
    f.write_text(_html(_bundle()), encoding="utf-8")
    return f


def _open(browser, f, w=1500, h=900):
    pg = browser.new_context(viewport={"width": w, "height": h}).new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1800)
    return pg


def test_the_tower_is_drawn_and_its_chip_stands_on_the_landmark(browser, page_file):
    pg = _open(browser, page_file)
    got = pg.evaluate("""()=>{ var g=document.querySelector('.pl-lmb[data-tower]'); if(!g) return null;
      var u=g.querySelector('use'), r=g.getBoundingClientRect(), c=document.querySelector('#node-alpha').getBoundingClientRect();
      return {art:u&&u.getAttribute('href'), label:g.getAttribute('aria-label'), inside:c.left>=r.left-2&&c.right<=r.right+2&&c.top>=r.top-2&&c.bottom<=r.bottom+2,
              ordinary:document.querySelectorAll('.node.pal-floor').length}; }""")
    assert got and got["art"].startswith("#lz-ctc-") and got["inside"], got
    assert "tower of 1.1 ALPHA, 60 floors" in got["label"]
    assert got["ordinary"] >= 4                                                    # its other buildings are floors now (no lots)
    assert not pg.errs
    pg.close()


def test_the_elevator_shows_real_floor_numbers_up_to_the_roof(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("window.showDetail('node','alpha')")
    pg.wait_for_timeout(700)
    got = pg.evaluate("""()=>({nums:Array.from(document.querySelectorAll('#pal-elev .pe-fl .pe-n')).map(e=>e.textContent),
      roof:document.querySelector('#pal-elev .pe-roof').textContent})""")
    nums = got["nums"]
    assert nums[0] == "60" and nums[-1] == "G" and "tower, 60 floors" in got["roof"]
    ints = [int(x) for x in nums[:-1]]
    assert ints == sorted(ints, reverse=True) and ints[-1] == 2 and len(set(ints)) == len(ints) == 4
    # a floor: its real number in the readout and the car beside it
    pg.evaluate("window.showDetail('node','beta')")
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.querySelector('#pal-elev .pe-where').textContent") == "Floor 60 of 60"
    assert pg.evaluate("document.querySelector('#pal-elev .pe-out')") is None       # a tower's floors are not let out
    assert not pg.errs
    pg.close()


def test_a_floor_added_to_a_tower_takes_the_next_real_floor(browser, page_file):
    """Edit mode adds a floor by giving a card a parent (pf|id); the page re-derives: no number yet, so it takes the next."""
    pg = _open(browser, page_file)
    got = pg.evaluate("""()=>{ var P=window._ALTO_PALACE, others=['alpha-1','alpha-2','alpha-3'].map(function(i){ return P.fn[i]; });
      delete P.fn.beta; window._altoPalaceRefresh();
      return {others:others, beta:P.fn.beta, num:P.num.beta, top:P.tw.alpha.top, order:P.fl.alpha.slice()}; }""")
    assert got["beta"] == max(got["others"]) + 1 and got["num"] == f"1.1-{got['beta']}"
    assert got["order"][-1] == "beta" and got["top"] == 60
    pg.close()


def test_a_tower_cannot_be_dragged_off_its_landmark(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("document.getElementById('detail-page') && 0")
    src = pg.evaluate("window._ALTO_PALACE.tw.alpha !== undefined && window._ALTO_PALACE.at.alpha")
    assert src and src.endswith(".0")
    assert "P.tw && P.tw[id]" in palace.PALACE_JS and "P.tw[o]" in palace.PALACE_JS
    pg.close()


def test_a_tower_is_not_dragged_and_the_map_tooltip_names_its_floors(browser, page_file):
    pg = _open(browser, page_file)
    tip = pg.evaluate("""()=>{ var g=document.querySelector('.pl-lmb[data-tower]'); return window._palLm.tip(g, function(s){return s;}, function(p){return p;}); }""")
    assert "Tower of 1.1 ALPHA · 60 floors" in tip
    pg.close()
