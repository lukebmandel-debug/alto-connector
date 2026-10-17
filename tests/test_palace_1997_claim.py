"""1.9.97: a background (fill-in) building claimed as one of the user's building nodes, which then stands on the real
footprint's SHAPE (palace_claim.py): the validation of brief.placement[id]["shape"], the page's lot for it, the edit op
p|<id>|shape and its fold-in, the JS hooks, and (headless) picking a background building in add mode, the glass block drawn
from its polygon, undo and a reload. Uses test_palace's synthetic city; nothing here touches the network, Firebase or any
ALTO_* setting."""
import copy
import functools
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_claim as pc, palace_fillin as pf  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline  # noqa: E402
from alto.edits import fold  # noqa: E402
from test_palace import _grid_bundle, bundle, check, load  # noqa: E402
from test_palace_add import FAKE, Store, _op  # noqa: E402

L_SHAPE = {"x": 200.0, "y": 160.0, "a": 0, "w": 60, "h": 40,
           "r": [[-30, -20], [30, -20], [30, 0], [0, 0], [0, 20], [-30, 20]]}          # an L, clockwise on the screen


# ── the validation ──────────────────────────────────────────────────────────
def test_a_good_shape_is_kept_and_a_counter_clockwise_one_is_turned_round():
    s = pc.check_shape(L_SHAPE)
    assert s["r"] == L_SHAPE["r"] and s["w"] == 60 and s["a"] == 0
    ccw = {**L_SHAPE, "r": L_SHAPE["r"][::-1]}
    assert pc.check_shape(ccw)["r"] == L_SHAPE["r"][::-1][::-1] or pc.check_shape(ccw)["r"] != ccw["r"]
    area = lambda r: sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))   # noqa: E731
    assert area(pc.check_shape(ccw)["r"]) > 0 and area(pc.check_shape(L_SHAPE)["r"]) > 0
    assert pc.lot_of(s) == [200.0, 160.0, 60, 40, 0, L_SHAPE["r"]]


@pytest.mark.parametrize("bad", [
    {**L_SHAPE, "r": L_SHAPE["r"][:2]},                                     # 2 points
    {**L_SHAPE, "r": [[i, (i * 7) % 11 - 5] for i in range(-20, 21)]},      # 41 points
    {**L_SHAPE, "r": [[-30, -20], [30, -20], [30.5, 0], [0, 0]]},           # not whole numbers
    {**L_SHAPE, "r": [[-30, -20], [60, -20], [60, 20], [-30, 20]]},         # outside its box
    {**L_SHAPE, "r": [[0, 0], [10, 0], [20, 0]]},                           # no area
    {**L_SHAPE, "w": 2}, {**L_SHAPE, "w": 5000}, {**L_SHAPE, "a": 120},
    {**L_SHAPE, "extra": 1}, {"x": 1, "y": 2}, "a ring", None, [],
])
def test_a_bad_shape_is_refused(bad):
    with pytest.raises(BriefError):
        pc.check_shape(bad)


def test_the_brief_validator_takes_a_shape_in_a_palace_placement_and_refuses_a_bad_one():
    d = bundle()
    d["brief"]["placement"] = {"beta": {"shape": L_SHAPE}, "gamma": {"lot": "3.0"}}
    check(d)                                                                # valid
    d["brief"]["placement"] = {"beta": {"shape": {**L_SHAPE, "r": [[0, 0]]}}}
    with pytest.raises(BriefError, match="placement beta"):
        check(d)
    d["brief"]["placement"] = {"beta": {"shape": L_SHAPE, "tier": 1}}
    with pytest.raises(BriefError):
        check(d)


# ── the page's data ─────────────────────────────────────────────────────────
def _data(d):
    page = build_timeline(*load(d))[0]
    return page, json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", page, re.S).group(1))


def test_a_claimed_building_stands_on_a_block_of_its_own_with_the_ring_in_its_lot():
    d = _grid_bundle()
    _page0, base = _data(d)
    d["brief"]["placement"] = {"beta": {"shape": L_SHAPE}}
    page, data = _data(d)
    key = data["at"]["beta"]
    bi, k = (int(x) for x in key.split("."))
    assert bi == len(data["b"]) - 1 and k == 0 and len(data["b"][bi]) == 1       # one block after the others
    assert data["b"][bi][0] == [200.0, 160.0, 60, 40, 0, L_SHAPE["r"]]
    assert data["pl0"]["beta"]["shape"]["r"] == L_SHAPE["r"]
    assert len(data["b"]) == len(base["b"]) + 1
    for i in ("alpha", "gamma", "delta", "eps"):                                 # the others still have lots, none of them its own
        assert data["at"][i] and data["at"][i] != key
    assert len({v for i, v in data["at"].items() if i in data["num"] and not data["of"].get(i)}) == len(
        [i for i in data["at"] if not data["of"].get(i)])                        # no lot twice


def test_a_lot_next_to_a_shape_is_ignored_and_a_floor_cannot_carry_one():
    d = _grid_bundle()
    d["brief"]["placement"] = {"beta": {"lot": "3.0", "shape": L_SHAPE}, "alpha-1": {"shape": L_SHAPE}}
    _page, data = _data(d)
    assert data["b"][int(data["at"]["beta"].split(".")[0])][0][5] == L_SHAPE["r"]
    assert "alpha-1" not in data["at"] and "shape" not in data["pl0"].get("alpha-1", {})


def test_the_page_without_a_fill_or_a_shape_is_unchanged_and_with_either_it_carries_the_hooks():
    plain = SimpleNamespace(palace={"data_z": "x"}, placement={})
    assert palace.palace_js(plain) is palace.PALACE_JS
    for b in (SimpleNamespace(palace={"fill_z": "x"}, placement={}),
              SimpleNamespace(palace={}, placement={"beta": {"shape": L_SHAPE}})):
        js = palace.palace_js(b)
        for s in ("function clmAt(", "function clmField(", "var C=L[5]?L[5].map(", "i<C.length;i++){ var A=C[i], B=C[(i+1)%C.length]",
                  "if(L[5]) return clmRing(L,cls,parent);", "var cl=clmAt(p); if(cl) return cl;", "p[2]==='shape' && TT[p[1]]) return clmField(p[1]);",
                  "clmSh()[id]) return;", "addForm(hit.cl||hit.key, null,",
                  "['p|'+id+'|shape', CL]", "res.C=L[5]?null:C"):
            assert js.count(s) == 1, s
    js = palace.palace_js(SimpleNamespace(palace={"fill_z": "x"}, placement={}))
    for s in ("if(L[5]){ clmCut(x,L); return; }", "(!t[4] || clmNear(t[4], s.p, 8))) return; }", "L[5]?clmAbs(L):null]); });"):
        assert js.count(s) == 1, s
    assert "clmCut(" not in palace.palace_js(SimpleNamespace(palace={}, placement={"beta": {"shape": L_SHAPE}})).replace("function clmCut(", "")   # no fill-in: no clearing hooks
    assert 'p[2]==="shape"' not in palace.PALACE_JS and "clmAt" not in palace.PALACE_JS        # (hooks are spliced, palace.py has none)
    me = (ROOT / "alto/build/manual_edit.py").read_text()
    assert me.count("/^(lot|fno|out|shape)$/") == 2


def test_the_hook_anchors_are_found_once_in_the_fill_in_patched_page():
    js = pc.patch_js(pf.patch_js(palace.PALACE_JS))
    assert "function clmNear(" in js and js.count("function nbDraw(") == 1


# ── the fold-in ─────────────────────────────────────────────────────────────
def test_a_claim_made_on_the_page_folds_into_the_placement_and_survives_every_rebuild():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"p|beta|shape": _op(L_SHAPE, 1)}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 1 and not r["conflicts"], r
    assert st.doc["brief"]["placement"]["beta"]["shape"] == pc.check_shape(L_SHAPE)
    # the same edit again is already in the draft; a different footprint made against none is a conflict
    st.edits = {"v": 1, "ops": {"p|beta|shape": _op(L_SHAPE, 2)}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 0 and r["already_in_draft"] == 1
    st.edits = {"v": 1, "ops": {"p|beta|shape": _op({**L_SHAPE, "x": 210.0}, 3)}}
    assert fold(st, "u", "t1")["conflicts"] == ["p|beta|shape"]
    assert st.doc["brief"]["placement"]["beta"]["shape"]["x"] == 200.0
    # a footprint that is not one is a conflict too, never written
    st.edits = {"v": 1, "ops": {"p|alpha|shape": _op({**L_SHAPE, "r": [[0, 0]]}, 4)}}
    assert fold(st, "u", "t1")["conflicts"] == ["p|alpha|shape"]
    assert "alpha" not in st.doc["brief"].get("placement", {})
    # builds, and builds again from the stored draft with the shape still there
    for _ in range(2):
        page, data = _data({"brief": st.doc["brief"], "nodes": st.nodes})
        assert data["pl0"]["beta"]["shape"]["r"] == L_SHAPE["r"]
        assert data["b"][int(data["at"]["beta"].split(".")[0])][0][5] == L_SHAPE["r"]


def test_a_new_building_claimed_and_taken_back_before_saving_goes_away():
    st = Store(bundle())
    spec = {"p": "", "a": 0, "t": "Annex", "g": "Room", "d": "Claimed.", "c": "var(--accent)"}
    st.edits = {"v": 1, "ops": {"nn|card-aaaa11": _op(spec, 1), "p|card-aaaa11|shape": _op(L_SHAPE, 2)}}
    assert not fold(st, "u", "t1")["conflicts"]
    assert st.doc["brief"]["placement"]["card-aaaa11"]["shape"]["w"] == 60
    st.edits = {"v": 1, "ops": {"nn|card-aaaa11": _op(None, 3, spec), "p|card-aaaa11|shape": _op(None, 4, L_SHAPE)}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    assert "card-aaaa11" not in (st.doc["brief"].get("placement") or {})
    build_timeline(*load({"brief": st.doc["brief"], "nodes": st.nodes}))


def test_moving_a_claimed_building_to_a_lot_puts_it_off_its_footprint():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"p|beta|shape": _op(L_SHAPE, 1)}}
    fold(st, "u", "t1")
    st.edits = {"v": 1, "ops": {"p|beta|shape": _op(L_SHAPE, 1), "p|beta|lot": {"b": None, "v": "3.0", "t": 5}}}
    r = fold(st, "u", "t1")
    assert st.doc["brief"]["placement"]["beta"] == {"lot": "3.0"}, (r, st.doc["brief"]["placement"])


def test_a_city_set_up_again_carries_the_footprints_or_drops_them_never_keeps_a_stale_one():
    d = _grid_bundle()
    pal = d["brief"]["palace"]
    placement = {"beta": {"shape": pc.check_shape(L_SHAPE)}, "alpha": {"lot": "3.0"}}
    out, rep = palace.migrate_placements(pal, pal, copy.deepcopy(placement))
    s = out["beta"].get("shape")
    assert s is None or (abs(s["x"] - 200.0) < 40 and abs(s["y"] - 160.0) < 40 and s["r"] == L_SHAPE["r"]), s
    only = palace.migrate_placements(pal, pal, {"beta": {"shape": pc.check_shape(L_SHAPE)}})[0]          # no saved lot at all: the shape is still carried
    assert "shape" in only["beta"] or only == {}, only
    out2, _ = palace.migrate_placements(pal, {**pal, "data_z": "garbage"}, copy.deepcopy(placement))
    assert "shape" not in out2.get("beta", {})                                  # a city that cannot be read: placed afresh


# ── in a browser: pick a background building, claim it, undo, reload ─────────
def _fill():
    """A little fill-in: a rectangle, an L and a long thin strip (level 2, whole-number points)."""
    sq = [(250, 140), (300, 140), (300, 180), (250, 180)]
    ell = [(60, 140), (100, 140), (100, 190), (80, 190), (80, 170), (60, 170)]
    strip = [(20, 40), (230, 40), (230, 52), (20, 52)]
    s, hs, ns, n = pf._encode([(0, 0, 0, sq, 0, ""), (0, 0, 0, ell, 0, ""), (0, 0, 0, strip, 0, "")], strips=False)
    return palace.pack({"v": 2, "doms": [[0.0, 0.0, 0.0]], "q": [1, 1, 1, 1], "L": ["", s, "", ""], "h": ["", hs and "".join(str(min(9, int(x))) for x in hs) or "", "", ""],
                        "n": [["", ""]] * 4, "ch": [600, 600], "c": [0, n, 0, 0], "lvl": 2, "reach": [0, 0, 1, 1]})


def _serve(tmp_path_factory, name, d):
    root = tmp_path_factory.mktemp(name)
    (root / "page.html").write_text(build_timeline(*load(d))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    d = _grid_bundle()
    d["brief"]["palace"]["fill_z"] = _fill()
    srv = _serve(tmp_path_factory, "pclaim", d)
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


@pytest.fixture(scope="module")
def url_shaped(tmp_path_factory):
    d = _grid_bundle()
    d["brief"]["placement"] = {"beta": {"shape": L_SHAPE}}
    srv = _serve(tmp_path_factory, "pshaped", d)
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


@pytest.fixture
def pg(url):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        b = None
        for launch in (lambda: p.chromium.launch(), lambda: p.chromium.launch(channel="chrome")):
            try:
                b = launch()
                break
            except Exception:                                # noqa: BLE001
                continue
        if b is None:
            pytest.skip("no browser to drive")
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_init_script(FAKE)
        page = ctx.new_page()
        page.errs = []
        page.on("pageerror", lambda e: page.errs.append(str(e)))
        page.goto(url)
        page.wait_for_timeout(1500)
        yield page
        b.close()


SCR = """(pt)=>{ var s=document.getElementById('palace-svg'); var r=s.getBoundingClientRect(), vb=s.viewBox.baseVal;
  return [r.x+(pt[0]-vb.x)/vb.width*r.width, r.y+(pt[1]-vb.y)/vb.height*r.height]; }"""
STATE = """()=>{ var P=window._ALTO_PALACE; return Object.keys(P.num).filter(i=>/^card-/.test(i)).map(function(i){ var L=P.at[i]?P.b[+P.at[i].split('.')[0]][0]:null;
  return {id:i, ring:L&&L[5]?L[5].length:0, box:L?L.slice(0,5):null, poly:document.querySelectorAll('#node-'+i+' .nb3d polygon').length}; }); }"""


def _claim(pg, pt, title):
    x, y = pg.evaluate(SCR, pt)
    pg.mouse.move(x - 2, y - 2)
    pg.mouse.move(x, y)
    pg.wait_for_timeout(250)
    out = {"outline": pg.evaluate("(document.querySelector('.pl-addg path.pl-addr')||{getAttribute:()=>null}).getAttribute('d')")}
    pg.mouse.click(x, y)
    pg.wait_for_timeout(350)
    out["form"] = pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    if out["form"]:
        pg.fill("#aed-form [data-f=title]", title)
        pg.click("#aed-form [data-a=ok]")
        pg.wait_for_timeout(900)
    return out


def test_in_add_mode_a_background_building_is_outlined_claimed_drawn_from_its_polygon_and_survives_undo_and_a_reload(pg):
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    # not in add mode: nothing is outlined over a background building
    x, y = pg.evaluate(SCR, [80, 160])
    pg.mouse.move(x, y)
    pg.wait_for_timeout(250)
    assert not pg.evaluate("!!document.querySelector('.pl-addg path.pl-addr')")
    pg.click(".ee-addb")
    pg.wait_for_timeout(300)
    got = _claim(pg, [70, 150], "L annex")                                       # inside the L's upright
    assert got["outline"] and got["outline"].count("L") == 5 and got["form"], got   # its 6 corners, outlined
    s = pg.evaluate(STATE)
    assert len(s) == 1 and s[0]["ring"] == 6 and s[0]["box"][2:4] == [40, 50] and s[0]["poly"] >= 4, s
    ops = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")
    shape = ops[f"p|{s[0]['id']}|shape"]["v"]
    assert shape["w"] == 40 and shape["h"] == 50 and len(shape["r"]) == 6 and pc.check_shape(shape)
    # the fill-in no longer draws what the node stands on (nor the 8 px round it); the rest stays
    pg.click(".ee-addb")
    pg.wait_for_timeout(300)
    got2 = _claim(pg, [270, 160], "Rect annex")
    pg.click(".ee-addb")                                                         # (an add ends add mode)
    pg.wait_for_timeout(300)
    got3 = _claim(pg, [100, 46], "Strip annex")
    assert got2["form"] and got3["form"], (got2, got3)
    s = pg.evaluate(STATE)
    assert sorted(x["ring"] for x in s) == [4, 4, 6] and all(x["poly"] >= 4 for x in s), s
    # undo takes the last claim away (its block goes empty), redo brings it back
    pg.keyboard.press("Escape")
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(700)
    assert len(pg.evaluate(STATE)) == 2
    pg.click("#alto-edit-exit .ee-redo")
    pg.wait_for_timeout(700)
    assert sorted(x["ring"] for x in pg.evaluate(STATE)) == [4, 4, 6]
    # a reload lays the saved edits over the built page again: the same three on their footprints
    pg.reload()
    pg.wait_for_timeout(2500)
    s = pg.evaluate(STATE)
    assert sorted(x["ring"] for x in s) == [4, 4, 6] and all(x["poly"] >= 4 for x in s), s
    assert not pg.errs, pg.errs
    # the glass block of the L has walls of its own: more faces than a rectangle's two
    l_id = next(x["id"] for x in s if x["ring"] == 6)
    assert pg.evaluate("(i)=>document.querySelectorAll('#node-'+i+' .nb3d .nb-f, #node-'+i+' .nb3d .nb-s').length", l_id) >= 3


def test_a_built_page_draws_a_node_with_a_shape_from_its_ring_and_one_without_as_a_box(url_shaped):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:                                    # noqa: BLE001
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception:                                # noqa: BLE001
                pytest.skip("no browser to drive")
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url_shaped)
        pg.wait_for_timeout(1500)
        n = pg.evaluate("""()=>{ var c=function(i){ var e=document.querySelector('#node-'+i+' .nb3d'); return e?[e.querySelectorAll('.nb-f,.nb-s').length, e.querySelector('.nb-r').getAttribute('points').split(' ').length]:null; }; return {beta:c('beta'), alpha:c('alpha')}; }""")
        b.close()
    assert not errs, errs
    assert n["beta"][1] == 6 and n["beta"][0] >= 3, n          # the roof is the 6-point ring; an L shows 3 or more walls
    assert n["alpha"][1] == 4 and n["alpha"][0] == 2, n        # a plain lot: the roof's 4 corners, a front and a right wall
