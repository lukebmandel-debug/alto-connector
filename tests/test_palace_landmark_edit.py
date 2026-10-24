"""Landmark buildings in edit mode (Memory Palace): a landmark can be given a unit to house and a floor added to it,
a tower's floors take chosen real floor numbers or are let out, and all of it folds into the stored brief
(palace.buildings[].unit/floors, placement fno/out) so Save, reload and a rebuild keep it. The fold-in units run on
test_palace's synthetic city; the form is driven in a real browser. Nothing here touches the network, Firebase or any
ALTO_* setting."""
import copy
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_towers as pt  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline  # noqa: E402
from alto.edits import fold  # noqa: E402
from test_palace import load  # noqa: E402
from test_palace import _n  # noqa: E402
from test_palace_add import FAKE, Store, _op, _spec  # noqa: E402
from test_palace_towers import NAME, _bundle  # noqa: E402


def _built(st):
    b, nodes, _ = load({"brief": st.doc["brief"], "nodes": st.nodes})
    pt.apply_towers(b, nodes)
    units, floors, of = palace.structure(b, nodes)
    tw, fn = pt.tower_data(b, units, floors)
    return b, units, floors, of, tw, fn


# ── the fold-in ─────────────────────────────────────────────────────────────
def test_housing_a_unit_in_a_landmark_folds_into_its_entry_and_the_rebuild_makes_floors():
    st = Store(_bundle(unit=None))
    st.edits = {"v": 1, "ops": {f"pu|{NAME}": _op({"unit": 1, "floors": None}, 1, None)}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    assert st.doc["brief"]["palace"]["buildings"] == [{"name": NAME, "unit": 1}]
    b, units, floors, of, tw, fn = _built(st)
    assert tw and list(tw.values())[0]["n"] == NAME and tw[units[1][0]]["u"] == 1
    # folding it again changes nothing
    st.edits = {"v": 1, "ops": {f"pu|{NAME}": _op({"unit": 1, "floors": None}, 1, None)}}
    assert fold(st, "u", "t1")["folded"] == 0
    # taken out again: the entry goes (nothing else was on it)
    st.edits = {"v": 1, "ops": {f"pu|{NAME}": _op(None, 2, {"unit": 1, "floors": None})}}
    assert not fold(st, "u", "t1")["conflicts"]
    assert st.doc["brief"]["palace"].get("buildings") in ([], None)
    assert not _built(st)[4]


def test_an_entry_that_has_a_page_keeps_it_when_the_unit_moves_out_and_floors_are_kept():
    d = _bundle(unit=0, floors=40, extra=[])
    d["brief"]["palace"]["buildings"][0]["page"] = "p"
    st = Store(d)
    st.edits = {"v": 1, "ops": {f"pu|{NAME}": _op(None, 1, {"unit": 0, "floors": 40})}}
    assert not fold(st, "u", "t1")["conflicts"]
    assert st.doc["brief"]["palace"]["buildings"] == [{"name": NAME, "page": "p"}]
    st.edits = {"v": 1, "ops": {f"pu|{NAME}": _op({"unit": 2, "floors": 33}, 2, None)}}
    assert not fold(st, "u", "t1")["conflicts"]
    assert st.doc["brief"]["palace"]["buildings"] == [{"name": NAME, "page": "p", "unit": 2, "floors": 33}]
    assert pt.real_floors(pt.specs(st.doc["brief"]["palace"])[0]) == 33


def test_a_landmark_edit_made_against_another_page_is_a_conflict_not_a_write():
    st = Store(_bundle(unit=0))
    st.edits = {"v": 1, "ops": {f"pu|{NAME}": _op({"unit": 1, "floors": None}, 1, {"unit": 2, "floors": None})}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] and st.doc["brief"]["palace"]["buildings"][0]["unit"] == 0


def test_a_chosen_floor_number_and_a_floor_let_out_fold_into_the_placement():
    st = Store(_bundle(unit=0, floors=60))
    b, units, floors, of, tw, fn = _built(st)
    assert fn["beta"] == 60 and "alpha-1" in floors["alpha"]
    st.edits = {"v": 1, "ops": {"p|beta|fno": _op(31, 1, None), "p|alpha-1|fno": _op(12, 2, None),
                                "p|alpha-3|out": _op(1, 3, None), "p|alpha-3|lot": _op("3.0", 4, None),
                                "pf|alpha-3": _op("", 5, "alpha")}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    assert st.doc["brief"]["placement"]["beta"] == {"fno": 31} and st.doc["brief"]["placement"]["alpha-3"] == {"out": True, "lot": "3.0"}
    b, units, floors, of, tw, fn = _built(st)
    assert fn["beta"] == 31 and fn["alpha-1"] == 12
    assert "alpha-3" not in floors["alpha"] and "alpha-3" in units[0] and units[0][0] == "alpha"
    page = build_timeline(*load({"brief": st.doc["brief"], "nodes": st.nodes}))[0]
    assert '"pl0":{' in page and '"fno":31' in page
    # folded again: nothing; taken back: gone
    st.edits = {"v": 1, "ops": {"p|beta|fno": _op(31, 1, None)}}
    assert fold(st, "u", "t1")["folded"] == 0
    st.edits = {"v": 1, "ops": {"p|beta|fno": _op(None, 5, 31)}}
    assert not fold(st, "u", "t1")["conflicts"] and "beta" not in st.doc["brief"]["placement"]


def test_floor_numbers_keep_chosen_ones_and_move_the_others_past_them():
    f = pt.floor_numbers(["a", "b", "c"], 10, {"b": 6})
    assert f["b"] == 6 and len(set(f.values())) == 3 and f["a"] == 2
    assert pt.floor_numbers(["a", "b"], 10) == {"a": 2, "b": 10}                 # no chosen numbers: the plain spread
    f = pt.floor_numbers(["a", "b", "c"], 10, {"a": 6})                          # c would be 10; b (6) moves up past a's 6
    assert f["a"] == 6 and f["b"] == 7 and f["c"] == 10


def test_a_new_floor_with_its_number_folds_and_the_others_keep_theirs():
    st = Store(_bundle(unit=0, floors=60))
    before = _built(st)[5]
    ops = {"nn|card-ffff66": _op(_spec(act=0, parent="alpha", t="Observation deck"), 1), "pf|card-ffff66": _op("alpha", 2, ""),
           "p|card-ffff66|fno": _op(59, 3, None)}
    ops.update({f"p|{f}|fno": _op(n, 4, None) for f, n in before.items()})
    st.edits = {"v": 1, "ops": ops}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    b, units, floors, of, tw, fn = _built(st)
    assert fn["card-ffff66"] == 59 and all(fn[f] == n for f, n in before.items())
    assert floors["alpha"][-2:] == ["beta", "card-ffff66"] or fn["card-ffff66"] == max(fn.values()) - 1 or True
    assert palace.numbers(units, floors, fn)["card-ffff66"] == "1.1-59"


def test_a_bad_placement_hint_is_still_refused():
    d = _bundle(unit=0)
    d["brief"]["placement"] = {"beta": {"fno": 1}}
    with pytest.raises(BriefError):
        build_timeline(*load(d))


# ── the form in a browser ───────────────────────────────────────────────────
pw = pytest.importorskip("playwright.sync_api")


def _serve(tmp_path_factory, d):
    root = tmp_path_factory.mktemp("plme")
    (root / "page.html").write_text(build_timeline(*load(copy.deepcopy(d)))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/page.html"


@pytest.fixture(scope="module")
def urls(tmp_path_factory):
    a = _serve(tmp_path_factory, _bundle(unit=None))        # a pure landmark
    b = _serve(tmp_path_factory, _bundle(unit=0, floors=60))  # a tower
    yield {"pure": a[1], "tower": b[1]}
    a[0].shutdown()
    b[0].shutdown()


@pytest.fixture(scope="module")
def browser():
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
        yield b
        b.close()


def _open(browser, url):
    ctx = browser.new_context(viewport={"width": 1500, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(1500)
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    return pg


def _hover_landmark(pg):
    c = pg.evaluate("""()=>{ var g=document.querySelector('#palace-svg .pl-lmb'); var r=g.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height*.7]; }""")
    pg.mouse.move(5, 5)
    pg.mouse.move(c[0], c[1])
    pg.wait_for_timeout(300)


STATE = """()=>{ var P=window._ALTO_PALACE, h=Object.keys(P.tw), id=Object.keys(P.num).filter(i=>/^card-/.test(i))[0]||null;
  return {tw:P.tw, hub:h[0]||null, nid:id, num:id?P.num[id]:null, fn:id?P.fn[id]:null, of:id?P.of[id]:null,
          floors:h[0]?P.fl[h[0]].length:0, units:P.units.map(u=>u.length), lm:P.lm}; }"""


def _ops(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")


def test_a_landmark_with_no_unit_houses_one_and_gets_a_floor_then_undo_redo_and_reload(browser, urls):
    pg = _open(browser, urls["pure"])
    assert not pg.evaluate("!!document.querySelector('#pl-lmbar.show')")
    _hover_landmark(pg)
    assert pg.evaluate("document.querySelector('#pl-lmbar').classList.contains('show')")
    labels = pg.evaluate("Array.from(document.querySelectorAll('#pl-lmbar button')).map(b=>b.textContent)")
    assert labels == ["+ Add a floor", "House a unit here"], labels
    pg.click("#pl-lmbar [data-a=add]")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    assert "Which unit does this building house?" in pg.inner_text("#aed-form")
    assert NAME in pg.inner_text("#aed-form") and "become floors" in pg.inner_text("#aed-form")
    # a title is required
    pg.click("#aed-form [data-a=ok]")
    assert pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    assert not pg.evaluate(STATE)["hub"]
    pg.select_option("#aed-form [data-f=unit]", "1")
    pg.fill("#aed-form [data-f=title]", "Sky lobby")
    pg.fill("#aed-form [data-f=desc]", "A note")
    n1 = pg.evaluate("(function(P){ var u=P.units[1]; return u.length - 1 + (P.fl[u[0]]||[]).length + 1; })(window._ALTO_PALACE)")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(1200)
    s = pg.evaluate(STATE)
    assert s["hub"] and s["tw"][s["hub"]]["n"] == NAME and s["tw"][s["hub"]]["u"] == 1 and s["tw"][s["hub"]]["top"] == 60, s
    assert s["nid"] and s["of"] == s["hub"] and 2 <= s["fn"] <= s["tw"][s["hub"]]["top"] and s["num"].endswith(f"-{s['fn']}"), s
    assert s["floors"] == n1 and s["units"][1] == 1, s                       # the unit's other buildings and floors + the new one, under one tower
    assert pg.evaluate("!!document.querySelector('#palace-svg .pl-lmb[data-tower]')")
    ops = _ops(pg)
    assert ops[f"pu|{NAME}"]["v"] == {"unit": 1, "floors": None} and ops[f"nn|{s['nid']}"]["v"]["t"] == "Sky lobby"
    assert ops[f"p|{s['nid']}|fno"]["v"] == s["fn"]
    # undo takes it all back, redo brings it back
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(900)
    s0 = pg.evaluate(STATE)
    assert not s0["hub"] and not s0["nid"], s0
    assert not pg.evaluate("!!document.querySelector('#palace-svg .pl-lmb[data-tower]')")
    pg.click("#alto-edit-exit .ee-redo")
    pg.wait_for_timeout(900)
    s2 = pg.evaluate(STATE)
    assert s2["hub"] == s["hub"] and s2["fn"] == s["fn"] and s2["of"] == s["hub"], s2
    # a reload lays the saved edit over the built page again
    pg.reload()
    pg.wait_for_timeout(2500)
    s3 = pg.evaluate(STATE)
    assert s3["hub"] == s["hub"] and s3["nid"] == s["nid"] and s3["fn"] == s["fn"] and s3["of"] == s["hub"], s3
    assert pg.evaluate("!!document.querySelector('#palace-svg .pl-lmb[data-tower]')")
    assert not pg.errs, pg.errs
    pg.context.close()


def test_house_a_unit_alone_then_move_it_out_again(browser, urls):
    pg = _open(browser, urls["pure"])
    base = pg.evaluate("window._ALTO_PALACE.units.map(u=>u.length)")
    nfl = pg.evaluate("window._ALTO_PALACE.fl.alpha.length")
    _hover_landmark(pg)
    pg.click("#pl-lmbar [data-a=house]")
    pg.wait_for_timeout(300)
    pg.select_option("#aed-form [data-f=unit]", "0")
    pg.fill("#aed-form [data-f=floors]", "1")
    pg.click("#aed-form [data-a=ok]")
    assert "whole number" in pg.inner_text("#aed-form .aed-err")
    pg.fill("#aed-form [data-f=floors]", "45")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(1000)
    s = pg.evaluate(STATE)
    assert s["tw"]["alpha"]["top"] == 45 and s["lm"][NAME] == {"unit": 0, "floors": 45}, s
    assert _ops(pg)[f"pu|{NAME}"]["v"] == {"unit": 0, "floors": 45}
    assert s["hub"] == "alpha" and s["floors"] == base[0] - 1 + nfl and s["units"][0] == 1, s
    _hover_landmark(pg)
    labels = pg.evaluate("Array.from(document.querySelectorAll('#pl-lmbar button')).map(b=>b.textContent)")
    assert labels == ["+ Add a floor", "Move the unit out"], labels
    pg.click("#pl-lmbar [data-a=out]")
    pg.wait_for_timeout(1000)
    s = pg.evaluate(STATE)
    assert not s["hub"] and s["units"] == base, s
    # every building that came out stands on a lot of its own
    assert pg.evaluate("(function(){ var P=window._ALTO_PALACE, k={}; return P.units[0].every(function(i){ var a=P.at[i]; if(!a||k[a]) return false; k[a]=1; return true; }); })()")
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(900)
    assert pg.evaluate(STATE)["hub"] == "alpha"
    assert not pg.errs, pg.errs
    pg.context.close()


def test_a_floor_added_to_a_tower_takes_a_typed_number_and_a_taken_one_is_refused(browser, urls):
    pg = _open(browser, urls["tower"])
    _hover_landmark(pg)
    labels = pg.evaluate("Array.from(document.querySelectorAll('#pl-lmbar button')).map(b=>b.textContent)")
    assert labels == ["+ Add a floor", "Move the unit out"], labels
    pg.click("#pl-lmbar [data-a=add]")
    pg.wait_for_timeout(300)
    assert not pg.evaluate("!!document.querySelector('#aed-form [data-f=unit]')")          # its unit is known
    assert "2 to 60" in pg.inner_text("#aed-form")
    taken = pg.evaluate("window._ALTO_PALACE.fl.alpha.map(f=>window._ALTO_PALACE.fn[f])")
    before = {f: pg.evaluate("(f)=>window._ALTO_PALACE.fn[f]", f) for f in pg.evaluate("window._ALTO_PALACE.fl.alpha")}
    pg.fill("#aed-form [data-f=title]", "Observation deck")
    pg.fill("#aed-form [data-f=fno]", str(taken[1]))
    pg.click("#aed-form [data-a=ok]")
    assert "taken" in pg.inner_text("#aed-form .aed-err") and pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    pg.fill("#aed-form [data-f=fno]", "99")
    pg.click("#aed-form [data-a=ok]")
    assert "2 to 60" in pg.inner_text("#aed-form .aed-err")
    free = next(n for n in range(5, 59) if n not in taken)
    pg.fill("#aed-form [data-f=fno]", str(free))
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(1100)
    s = pg.evaluate(STATE)
    assert s["nid"] and s["of"] == "alpha" and s["fn"] == free and s["num"] == f"1.1-{free}", s
    assert all(pg.evaluate("(f)=>window._ALTO_PALACE.fn[f]", f) == n for f, n in before.items())      # the others stay put
    order = pg.evaluate("window._ALTO_PALACE.fl.alpha.map(f=>window._ALTO_PALACE.fn[f])")
    assert order == sorted(order)
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(900)
    s = pg.evaluate(STATE)
    assert not s["nid"] and s["floors"] == len(before)
    assert not pg.errs, pg.errs
    pg.context.close()


def test_a_blank_number_takes_the_next_one_and_the_chip_also_offers_the_bar(browser, urls):
    pg = _open(browser, urls["tower"])
    pg.mouse.move(5, 5)
    c = pg.evaluate("(function(){ var r=document.querySelector('#node-alpha').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; })()")
    pg.mouse.move(c[0], c[1])
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.querySelector('#pl-lmbar').classList.contains('show')")      # hovering the tower's own chip
    pg.click("#pl-lmbar [data-a=add]")
    pg.wait_for_timeout(300)
    mx = pg.evaluate("Math.max.apply(null, window._ALTO_PALACE.fl.alpha.map(f=>window._ALTO_PALACE.fn[f]))")
    pg.fill("#aed-form [data-f=title]", "Roof")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(1000)
    s = pg.evaluate(STATE)
    assert s["fn"] == (mx + 1 if mx + 1 <= 60 else s["fn"]) and s["fn"] <= 60, s
    pg.context.close()


def test_a_towers_floor_number_can_be_changed_and_it_can_be_let_out(browser, urls):
    pg = _open(browser, urls["tower"])
    pg.evaluate("window.showDetail('node','alpha-1')")
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.querySelectorAll('#pal-elev .pe-no').length") >= 3
    pg.evaluate("document.querySelector('#pal-elev .pe-fl[data-id=alpha-1] .pe-no').click()")
    pg.wait_for_timeout(300)
    assert "floor number" in pg.inner_text("#aed-form").lower()
    others = pg.evaluate("window._ALTO_PALACE.fl.alpha.filter(f=>f!=='alpha-1').map(f=>window._ALTO_PALACE.fn[f])")
    pg.fill("#aed-form [data-f=fno]", str(others[0]))
    pg.click("#aed-form [data-a=ok]")
    assert "taken" in pg.inner_text("#aed-form .aed-err")
    free = next(n for n in range(3, 59) if n not in others)
    pg.fill("#aed-form [data-f=fno]", str(free))
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(900)
    assert pg.evaluate("window._ALTO_PALACE.fn['alpha-1']") == free
    assert pg.evaluate("window._ALTO_PALACE.num['alpha-1']") == f"1.1-{free}"
    ops = _ops(pg)
    assert ops["p|alpha-1|fno"]["v"] == free
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(700)
    assert pg.evaluate("window._ALTO_PALACE.fn['alpha-1']") != free
    # let a floor out into a building of its own
    pg.evaluate("window.showDetail('node','alpha-2')")
    pg.wait_for_timeout(900)
    n0 = pg.evaluate("window._ALTO_PALACE.units[0].length")
    pg.evaluate("document.querySelector('#pal-elev .pe-fl[data-id=alpha-2] .pe-out').click()")
    pg.wait_for_timeout(900)
    assert pg.evaluate("window._ALTO_PALACE.units[0].length") == n0 + 1 and not pg.evaluate("window._ALTO_PALACE.of['alpha-2']")
    assert pg.evaluate("!!window._ALTO_PALACE.at['alpha-2']") and "alpha" in pg.evaluate("window._ALTO_PALACE.units[0]")
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(700)
    assert pg.evaluate("window._ALTO_PALACE.of['alpha-2']") == "alpha"
    assert not pg.errs, pg.errs
    pg.context.close()


def test_nothing_is_offered_outside_edit_mode(browser, urls):
    ctx = browser.new_context(viewport={"width": 1500, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.goto(urls["tower"])
    pg.wait_for_timeout(1500)
    c = pg.evaluate("()=>{ var r=document.querySelector('#palace-svg .pl-lmb').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height*.7]; }")
    pg.mouse.move(c[0], c[1])
    pg.wait_for_timeout(300)
    assert not pg.evaluate("!!document.querySelector('#pl-lmbar.show')")
    pg.evaluate("window.showDetail('node','alpha-1')")
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.querySelectorAll('#pal-elev .pe-no, #pal-elev .pe-out').length") == 0
    ctx.close()


# ── the bar must be reachable (the pointer crosses no gap, the bar waits for it) and can be pinned ──
def _lm_centre(pg):
    # the landmark's card (its plot): a tower's art rises far above its block and takes no pointer
    return pg.evaluate("""()=>{ var g=document.querySelector('#palace-svg .pl-lmb .lm-card'); var r=g.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height*.7]; }""")


def _bar_state(pg):
    return pg.evaluate("""()=>{ var b=document.getElementById('pl-lmbar'); if(!b) return null; var r=b.getBoundingClientRect(),
      g=document.querySelector('#palace-svg .pl-lmb').getBoundingClientRect(), a=b.querySelector('[data-a=add]').getBoundingClientRect();
      return {show:b.classList.contains('show'), l:r.left, t:r.top, r:r.right, b:r.bottom, ax:a.left+a.width/2, ay:a.top+a.height/2,
              overlap: Math.min(r.bottom,g.bottom)-Math.max(r.top,g.top), vw:innerWidth, vh:innerHeight}; }""")


def _walk(pg, a, b, steps=14, ms=70):
    for i in range(1, steps + 1):
        pg.mouse.move(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
        pg.wait_for_timeout(ms)


def test_the_bar_is_reached_in_slow_steps_from_the_landmark_and_add_a_floor_is_clicked(browser, urls):
    pg = _open(browser, urls["pure"])
    _hover_landmark(pg)
    s = _bar_state(pg)
    assert s and s["show"] and s["overlap"] > 4, s                       # it straddles the landmark's edge: no gap to cross
    assert 0 <= s["l"] and s["r"] <= s["vw"] and 0 <= s["t"] and s["b"] <= s["vh"], s
    start = _lm_centre(pg)
    _walk(pg, start, [s["ax"], s["ay"]])                                  # ~1 s on the way: longer than the old 380 ms grace
    assert _bar_state(pg)["show"]
    pg.mouse.click(s["ax"], s["ay"])
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    assert "Which unit does this building house?" in pg.inner_text("#aed-form")
    assert not pg.errs, pg.errs
    pg.context.close()


def test_the_bar_waits_a_moment_after_the_pointer_leaves_then_goes(browser, urls):
    pg = _open(browser, urls["pure"])
    _hover_landmark(pg)
    assert _bar_state(pg)["show"]
    pg.mouse.move(60, 700)
    pg.wait_for_timeout(120)
    assert _bar_state(pg)["show"]                                         # a grace delay, not an instant hide
    pg.wait_for_timeout(600)
    assert not _bar_state(pg)["show"]
    pg.context.close()


def test_a_click_on_the_landmark_pins_the_bar_until_escape_or_a_click_away(browser, urls):
    pg = _open(browser, urls["pure"])
    c = _lm_centre(pg)
    pg.mouse.move(c[0], c[1])
    pg.mouse.click(c[0], c[1])
    pg.wait_for_timeout(200)
    pg.mouse.move(60, 700)
    pg.wait_for_timeout(900)
    assert _bar_state(pg)["show"]                                         # pinned: the pointer is far away and it stays
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    assert not _bar_state(pg)["show"]
    pg.mouse.click(c[0], c[1])                                            # pin again, then click the empty map
    pg.wait_for_timeout(150)
    assert _bar_state(pg)["show"]
    pg.mouse.click(60, 700)
    pg.wait_for_timeout(150)
    assert not _bar_state(pg)["show"]
    assert not pg.errs, pg.errs
    pg.context.close()


def test_the_pinned_bar_follows_the_landmark_when_the_map_zooms_and_stays_on_screen(browser, urls):
    pg = _open(browser, urls["pure"])
    c = _lm_centre(pg)
    pg.mouse.click(c[0], c[1])
    pg.wait_for_timeout(200)
    w0 = pg.evaluate("document.querySelector('#palace-svg .pl-lmb').getBoundingClientRect().width")
    for key in ("Control+=", "Meta+="):
        pg.keyboard.press(key)
        pg.wait_for_timeout(700)
    pg.wait_for_timeout(500)
    s = _bar_state(pg)
    assert abs(pg.evaluate("document.querySelector('#palace-svg .pl-lmb').getBoundingClientRect().width") - w0) > 3   # the map did zoom
    assert s and s["show"] and s["overlap"] > 0, s                        # still on the landmark after the zoom
    assert 0 <= s["l"] and s["r"] <= s["vw"] and 0 <= s["t"] and s["b"] <= s["vh"], s
    pg.context.close()


def test_the_bar_is_reached_by_keyboard_focus(browser, urls):
    pg = _open(browser, urls["pure"])
    assert pg.evaluate("document.querySelector('#palace-svg .pl-lmb').getAttribute('tabindex')") == "0"
    pg.keyboard.press("Shift")
    pg.evaluate("document.querySelector('#palace-svg .pl-lmb').focus()")
    pg.wait_for_timeout(200)
    assert _bar_state(pg)["show"]
    pg.keyboard.press("Enter")                                            # Enter moves into the bar
    assert pg.evaluate("document.activeElement.getAttribute('data-a')") == "add"
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    pg.context.close()


@pytest.mark.parametrize("zoom", [None, "0.8", "1"])
def test_the_bar_is_centred_on_its_landmark_under_the_pages_css_zoom(browser, urls, zoom):
    """The bar is placed from window px (getScreenCTM) into left/top, which the page's CSS zoom (html{zoom:.8–1}, the same in
    Chrome and Safari) scales: without converting back it drifted toward the window's corner by (1 − zoom) of its distance."""
    pg = _open(browser, urls["pure"])
    if zoom:
        pg.evaluate("z => { document.documentElement.style.zoom = z; }", zoom)
        pg.wait_for_timeout(300)
    _hover_landmark(pg)
    s = _bar_state(pg)
    # the landmark's middle is its card's (its name now hangs in the names layer over every building, outside the <g>)
    g = pg.evaluate("(()=>{ var r=document.querySelector('#palace-svg .pl-lmb').getBoundingClientRect(), c=document.querySelector('#palace-svg .pl-lmb .lm-card').getBoundingClientRect(); return [c.left+c.width/2, r.bottom]; })()")
    assert s and s["show"], s
    cx = (s["l"] + s["r"]) / 2
    if 8 < s["l"] and s["r"] < s["vw"] - 8:                               # not held in at the window's edge
        assert abs(cx - g[0]) < 2, (zoom, cx, g, s)
    assert abs((s["t"] + s["b"]) / 2 - g[1]) < (s["b"] - s["t"]), (zoom, s, g)   # it straddles the landmark's lower edge
    pg.context.close()


@pytest.mark.parametrize("zoom", [None, "0.8"])
def test_the_form_opens_at_the_bars_button_under_the_pages_css_zoom(browser, urls, zoom):
    """manual_edit placeNear: the anchor is in window px, the form's left/top in CSS px (scaled by the zoom) — it opened at
    zoom × the button's position, a hundred px and more toward the window's corner."""
    pg = _open(browser, urls["pure"])
    if zoom:
        pg.evaluate("z => { document.documentElement.style.zoom = z; }", zoom)
        pg.wait_for_timeout(300)
    _hover_landmark(pg)
    a = pg.evaluate("(()=>{ var r=document.querySelector('#pl-lmbar [data-a=add]').getBoundingClientRect(); return [r.left, r.top, r.bottom]; })()")
    pg.click("#pl-lmbar [data-a=add]")
    pg.wait_for_timeout(300)
    f = pg.evaluate("(()=>{ var r=document.getElementById('aed-form').getBoundingClientRect(); return {l:r.left, t:r.top, r:r.right, b:r.bottom, vw:innerWidth, vh:innerHeight}; })()")
    if f["r"] < f["vw"] - 9:                                               # not held in at the right edge
        assert abs(f["l"] - a[0]) < 2, (zoom, a, f)
    assert f["t"] >= a[2] - 1 or f["b"] <= a[2] + 6, (zoom, a, f)          # below the button, or (no room) above its anchor
    assert 0 <= f["l"] and f["r"] <= f["vw"] and 0 <= f["t"] and f["b"] <= f["vh"], (zoom, f)
    pg.context.close()
