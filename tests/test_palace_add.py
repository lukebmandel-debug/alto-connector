"""Adding a building (or a floor) to a Memory Palace in manual edit mode: the
fold-in into the stored nodes and placement (alto/edits.py), and the page's own
flow in a real browser — a faint + on a free lot, the glass form, a numbered
building on that lot, undo, redo, a floor, search. Uses the tiny synthetic city
of test_palace.py; nothing here touches the network, Firebase or any ALTO_*
setting."""
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

from alto.build import palace  # noqa: E402
from alto.build.builder import build_timeline  # noqa: E402
from alto.edits import fold  # noqa: E402
from test_palace import Store as _Store  # noqa: E402
from test_palace import _grid_bundle, _n, bundle, load  # noqa: E402


class Store(_Store):
    """test_palace's store, but one that keeps the nodes a fold creates."""

    def put_nodes(self, uid, tid, nodes):
        by = {n["id"]: n for n in nodes}
        have = {n["id"] for n in self.nodes}
        self.nodes = ([copy.deepcopy(by.get(n["id"], n)) for n in self.nodes]
                      + [copy.deepcopy(n) for n in nodes if n["id"] not in have])

FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


def _spec(act=0, parent="", **kw):
    return {"p": parent, "a": act, "t": "New hall", "g": "Room", "d": "A hall added here.", "c": "var(--accent)", **kw}


def _op(v, t, b=None):
    return {"b": b, "v": v, "t": t}


def _numbers(st):
    b, nodes, _ = load({"brief": st.doc["brief"], "nodes": st.nodes})
    units, floors, _of = palace.structure(b, nodes)
    return palace.numbers(units, floors)


# ── the fold-in ─────────────────────────────────────────────────────────────
def test_a_building_added_on_the_page_folds_into_its_unit_and_lot():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"nn|card-aaaa11": _op(_spec(act=0), 1), "p|card-aaaa11|lot": _op("3.0", 2)}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    n = _n(st, "card-aaaa11")
    assert n["act"] == 0 and n["title"] == "New hall" and n["tag"] == "Room" and n["desc"] == "A hall added here."
    assert not n.get("parent")
    assert st.doc["brief"]["placement"]["card-aaaa11"] == {"lot": "3.0"}
    assert _numbers(st)["card-aaaa11"] == "1.3"                      # after alpha and beta
    page = build_timeline(*load({"brief": st.doc["brief"], "nodes": st.nodes}))[0]
    assert "card-aaaa11" in page
    # folding it again changes nothing
    st.edits = {"v": 1, "ops": {"nn|card-aaaa11": _op(_spec(act=0), 1), "p|card-aaaa11|lot": _op("3.0", 2)}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 0 and not r["conflicts"], r
    assert sum(1 for x in st.nodes if x["id"] == "card-aaaa11") == 1


def test_a_floor_added_on_the_page_folds_under_its_building():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"nn|card-bbbb22": _op(_spec(act=1, parent="gamma"), 1),
                                "pf|card-bbbb22": _op("gamma", 2, "")}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    n = _n(st, "card-bbbb22")
    assert n["parent"] == "gamma" and n["act"] == 1
    assert _numbers(st)["card-bbbb22"] == "2.1-2"                    # above gamma-1
    build_timeline(*load({"brief": st.doc["brief"], "nodes": st.nodes}))


def test_a_unit_given_by_its_id_and_two_new_buildings_on_one_lot():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"nn|card-cccc33": _op(_spec(act=2), 1), "p|card-cccc33|lot": _op("3.0", 2),
                                "nn|card-dddd44": _op(_spec(act=2, t="Other"), 3), "p|card-dddd44|lot": _op("3.0", 4)}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    nums = _numbers(st)
    assert nums["card-cccc33"] == "3.3" and nums["card-dddd44"] == "3.4"
    # both asked for the lot; the build gives it to one and never stacks two on it
    data = palace.unpack(st.doc["brief"]["palace"]["data_z"])
    b, nodes, _ = load({"brief": st.doc["brief"], "nodes": st.nodes})
    units, _f, _o = palace.structure(b, nodes)
    at = palace.pp.place(data["map"], data["blocks"], units, b.palace["districts"],
                         {k: v["lot"] for k, v in b.placement.items() if v.get("lot")})
    assert at["card-cccc33"] != at["card-dddd44"]


def test_an_added_building_taken_back_before_saving_is_removed_again():
    st = Store(bundle())
    st.edits = {"v": 1, "ops": {"nn|card-eeee55": _op(_spec(act=0), 1), "p|card-eeee55|lot": _op("3.0", 2)}}
    assert not fold(st, "u", "t1")["conflicts"]
    assert any(x["id"] == "card-eeee55" for x in st.nodes)
    # undo on the page: the card and its lot both go back to nothing
    st.edits = {"v": 1, "ops": {"nn|card-eeee55": _op(None, 3, _spec(act=0)), "p|card-eeee55|lot": _op(None, 4, "3.0")}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    assert not any(x["id"] == "card-eeee55" for x in st.nodes)
    assert "card-eeee55" not in (st.doc["brief"].get("placement") or {})
    build_timeline(*load({"brief": st.doc["brief"], "nodes": st.nodes}))


# ── the page ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def url(tmp_path_factory):
    root = tmp_path_factory.mktemp("padd")
    (root / "page.html").write_text(build_timeline(*load(_grid_bundle()))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
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


FREE_LOT = """()=>{ var P=window._ALTO_PALACE, svg=document.getElementById('palace-svg'), r=svg.getBoundingClientRect(), vb=svg.viewBox.baseVal;
  var t={}; Object.keys(P.at).forEach(function(i){ if(!P.of[i]) t[P.at[i]]=1; }); var best=null;
  P.b.forEach(function(ls,i){ ls.forEach(function(L,k){ if(best||t[i+'.'+k]) return;
    var x=r.left+(L[0]-vb.x)/vb.width*r.width, y=r.top+(L[1]-vb.y)/vb.height*r.height;
    if(x>260&&x<1000&&y>150&&y<700) best=[x,y,i+'.'+k]; }); }); return best; }"""
STATE = """(id)=>{ var P=window._ALTO_PALACE; return {at:P.at[id]||null, num:P.num[id]||null, of:P.of[id]||null,
  node:!!document.getElementById('node-'+id), units:P.units.map(function(u){return u.length;})}; }"""


def _new_id(pg):
    return pg.evaluate("Object.keys(window._ALTO_PALACE.num).filter(i=>/^card-/.test(i))[0]||null")


def _add(pg, lot, title="Test hall", unit=None):
    x, y, key = lot
    pg.mouse.move(x, y)
    pg.wait_for_timeout(150)
    pg.mouse.click(x, y)
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    pg.fill("#aed-form [data-f=title]", title)
    pg.fill("#aed-form [data-f=desc]", "A short note")
    if unit is not None:
        pg.select_option("#aed-form [data-f=unit]", str(unit))
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(900)


def test_in_edit_mode_a_free_lot_offers_a_plus_and_the_form_makes_a_numbered_building(pg):
    # nothing offered outside edit mode
    lot = pg.evaluate(FREE_LOT)
    pg.mouse.move(lot[0], lot[1])
    pg.wait_for_timeout(150)
    assert not pg.evaluate("!!document.querySelector('.pl-addg')") and not pg.evaluate("!!document.querySelector('.ee-addb')")
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    assert pg.evaluate("!!document.querySelector('.ee-addb')")
    before = pg.evaluate(STATE, "none")["units"]
    pg.mouse.move(lot[0], lot[1])
    pg.wait_for_timeout(200)
    assert pg.evaluate("!!document.querySelector('.pl-addg')")                       # the faint +
    # a title is required
    pg.mouse.click(lot[0], lot[1])
    pg.wait_for_timeout(300)
    pg.click("#aed-form [data-a=ok]")
    assert pg.evaluate("document.getElementById('aed-form').classList.contains('show')")
    assert pg.evaluate("!!document.querySelector('.pl-addpend')")                    # the chosen lot stays marked
    pg.click("#aed-form [data-a=cancel]")
    pg.wait_for_timeout(200)
    assert not pg.evaluate("!!document.querySelector('.pl-addpend')") and not _new_id(pg)
    _add(pg, lot, "Test hall", unit=1)
    nid = _new_id(pg)
    s = pg.evaluate(STATE, nid)
    assert nid and s["at"] == lot[2] and s["node"] and s["of"] is None
    assert s["num"] == f"2.{before[1] + 1}", s                                       # numbered after its section's buildings
    assert s["units"][1] == before[1] + 1
    ops = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0])).ops")
    assert ops[f"nn|{nid}"]["v"]["t"] == "Test hall" and ops[f"p|{nid}|lot"]["v"] == lot[2], ops
    assert pg.evaluate("(id)=>document.querySelector('#node-'+id+' .node-title,#node-'+id).textContent", nid)
    # the lot is taken now: no + over it
    pg.mouse.move(5, 5)
    pg.mouse.move(lot[0], lot[1])
    pg.wait_for_timeout(200)
    assert not pg.evaluate("!!document.querySelector('.pl-addg')")
    # searchable, with its number
    hits = pg.evaluate("(q)=>window._altoSearch.search(q).map(function(r){return r.id||r.nid||JSON.stringify(r);})", "Test hall")
    assert any(nid in str(h) for h in hits), hits
    # undo takes it away, redo brings it back
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(700)
    s = pg.evaluate(STATE, nid)
    assert not s["node"] and s["at"] is None and s["units"] == before, s
    pg.click("#alto-edit-exit .ee-redo")
    pg.wait_for_timeout(700)
    s = pg.evaluate(STATE, nid)
    assert s["node"] and s["at"] == lot[2] and s["num"] == f"2.{before[1] + 1}", s
    # a reload keeps it (the page lays the saved edit over the built page again)
    pg.reload()
    pg.wait_for_timeout(2500)
    s = pg.evaluate(STATE, nid)
    assert s["node"] and s["at"] == lot[2] and s["num"] == f"2.{before[1] + 1}", s
    assert not pg.errs, pg.errs


def test_the_add_building_button_marks_the_free_lots_and_a_floor_goes_on_a_building(pg):
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    pg.click(".ee-addb")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.querySelectorAll('.pl-addfree .pl-addr').length") > 5
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(200)
    assert not pg.evaluate("!!document.querySelector('.pl-addfree')")
    # a floor on the first building: the same form, no section to choose
    bid = pg.evaluate("window._ALTO_PALACE.units[0][0]")
    n0 = pg.evaluate("(window._ALTO_PALACE.fl[window._ALTO_PALACE.units[0][0]]||[]).length")
    pg.evaluate("(id)=>window._altoPalaceAddFloor(id, null)", bid)
    pg.wait_for_timeout(300)
    assert pg.evaluate("!document.querySelector('#aed-form [data-f=unit]')")
    pg.fill("#aed-form [data-f=title]", "Attic")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(900)
    nid = _new_id(pg)
    s = pg.evaluate(STATE, nid)
    assert s["of"] == bid and s["num"] == f"1.1-{n0 + 1}" and not s["at"], s
    assert pg.evaluate("(b)=>window._ALTO_PALACE.fl[b].indexOf(window._ALTO_PALACE.num && Object.keys(window._ALTO_PALACE.num).filter(i=>/^card-/.test(i))[0])", bid) >= 0
    pg.click("#alto-edit-exit .ee-undo")
    pg.wait_for_timeout(700)
    assert not pg.evaluate(STATE, nid)["node"]
    assert not pg.errs, pg.errs
