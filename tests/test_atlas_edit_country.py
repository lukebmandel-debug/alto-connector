"""Adding and removing countries by hand in a Memory Atlas (Luke, 2026-10-29: "Make sure user can manually add countries"; in place,
remove too, no Claude/MCP, via the edits layer, survives republish). The page: edit mode's + Country picks one, a card is added standing on
it (two edits, one undo step: `nn|<id>` and `w|<id>|place`), a reload before any republish still shows it, its ✕ removes it, and not one
request goes to /mcp or any Claude route. The fold: `w|<id>|place` becomes brief.world.places[id] (what set_up_world keeps), so the next
build puts the card there; removing the card drops its place; any other format leaves the key waiting. Chromium and WebKit."""
import copy
import http.server
import threading

import pytest

from alto.build import palace_assets, world_plan as wp
from alto.edits import fold
from tests.test_manual_edit import Store
from tests.test_world_palace import NODES, brief, built
from tests.test_world_palace_render import browser  # noqa: F401

# the cloud the page saves its edits to, kept in sessionStorage so a reload finds them (as Firestore would)
FAKE = """(function(){ var K='fake-edits';
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ try{ return Promise.resolve(JSON.parse(sessionStorage.getItem(K)||'null')); }catch(e){ return Promise.resolve(null); } },
  putEdits:function(t,d){ sessionStorage.setItem(K, JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


def _doc(**kw):
    return {"brief": brief(**kw), "nodes": copy.deepcopy(NODES)}


# ── the fold ─────────────────────────────────────────────────────────────────

def test_the_fold_keeps_a_hand_placed_country_and_drops_it_with_its_card():
    st = Store(_doc(world={"places": {"erie": wp.resolve("Peru")}}))
    st.edits = {"v": 1, "ops": {"nn|card-abc123": {"b": None, "v": {"p": "", "a": 1, "t": "Japan", "g": "", "d": ""}, "t": 1},
                                "w|card-abc123|place": {"b": None, "v": {"c": "JPN"}, "t": 2},
                                "w|hanna|place": {"b": None, "v": {"c": "FRA"}, "t": 3}}}
    r = fold(st, "u", "t1")
    assert r and not r.get("error"), r
    pl = st.doc["brief"]["world"]["places"]
    assert pl["card-abc123"]["c"] == "JPN" and pl["hanna"]["c"] == "FRA" and pl["erie"]["c"] == "PER"      # the notes' place is kept
    from alto.build.builder import load_brief
    b, ns, _ = load_brief({"brief": copy.deepcopy(st.doc["brief"]), "nodes": copy.deepcopy(st.nodes)})
    p = wp.plan(b, ns)
    assert p["places"]["card-abc123"]["c"] == "JPN" and p["places"]["hanna"]["c"] == "FRA"                  # the next build puts them there
    st.edits["ops"]["nd|card-abc123"] = {"b": None, "v": 1, "t": 4}                                         # its ✕
    fold(st, "u", "t1")
    assert "card-abc123" not in st.doc["brief"]["world"]["places"] and "card-abc123" not in {n["id"] for n in st.nodes}


def test_another_format_leaves_the_key_and_every_other_edit_as_it_was():
    d = _doc(palace_view="city")
    st = Store(d)
    st.edits = {"v": 1, "ops": {"w|hanna|place": {"b": None, "v": {"c": "FRA"}, "t": 1},
                                "n|hanna|title": {"b": "Hanna", "v": "Hanna v. Plumer", "t": 2}}}
    r = fold(st, "u", "t1")
    assert "w|hanna|place" in r.get("missing", []) and "world" not in st.doc["brief"] or not (st.doc["brief"].get("world") or {}).get("places")
    assert next(n for n in st.nodes if n["id"] == "hanna")["title"] == "Hanna v. Plumer"                    # a plain edit folds as before
    st2 = Store(_doc())
    st2.edits = {"v": 1, "ops": {"w|hanna|place": {"b": None, "v": {"c": "XXX"}, "t": 1}}}
    r2 = fold(st2, "u", "t1")
    assert "w|hanna|place" in r2.get("conflicts", []) and not (st2.doc["brief"].get("world") or {}).get("places")


# ── the page ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def origin():
    html = built(world={"places": {"erie": wp.resolve("Peru")}})[0]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", FAKE) if path == "/alto-cloud.js"
                   else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


NEW = "Object.keys(AltoWorld.data.nodes).filter(k => /^card-/.test(k) && AltoWorld.data.nodes[k].c === 'JPN')"


def _ready(page):
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin') && window._altoManual", timeout=20000)
    page.wait_for_timeout(500)


def test_add_a_country_reload_it_is_there_remove_it(browser, origin):  # noqa: F811
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors, asked = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: asked.append(r.url))
    try:
        page.goto(origin + "/index.html")
        _ready(page)
        page.evaluate("window._altoManual.enter()")
        page.wait_for_timeout(300)
        assert page.evaluate("getComputedStyle(document.getElementById('wpal-root')).visibility") == "visible"     # edit stays in the map
        page.click("#alto-edit-exit .ee-country")
        inside = page.evaluate("(() => { var P = document.querySelector('#wpal-root .wp-pick').getBoundingClientRect(); return [].every.call(document.querySelectorAll('#wpal-root .wp-pick :is(input,select)'), e => { var r = e.getBoundingClientRect(); return r.left >= P.left && r.right <= P.right; }); })()")
        assert inside                                                                  # every field inside the plate (Art)
        bg = page.evaluate("getComputedStyle(document.querySelector('#wpal-root .wp-pick')).backgroundColor")
        assert float(bg.replace(')', '').split(',')[-1]) >= .92 if bg.startswith('rgba') else True, bg      # a solid plate (Art)
        page.fill("#wpal-root .wp-pick input", "Japan")
        page.press("#wpal-root .wp-pick input", "Enter")
        page.wait_for_timeout(1800)
        ids = page.evaluate(NEW)
        assert len(ids) == 1, ids
        nid = ids[0]
        ops = page.evaluate("window._altoManual.ops()")
        assert ops[f"w|{nid}|place"]["v"] == {"c": "JPN"} and ops[f"nn|{nid}"]["v"]["t"] == "Japan"
        assert page.evaluate(f"!!document.querySelector('#wpal-root .wp-c.wp-u') && AltoWorld.data.used.JPN != null && !!document.getElementById('node-{nid}')")
        page.wait_for_timeout(900)                                                     # (the edits are pushed after 600 ms)
        page.reload()
        _ready(page)
        assert page.evaluate(NEW) == [nid]                                             # a reload before any republish: still there
        page.evaluate("window._altoManual.enter()")
        page.evaluate(f"AltoWorld.select('{nid}')")
        page.wait_for_timeout(1800)
        page.hover(f"#wpal-root .wp-enl #node-{nid} .node-card")
        page.click(f"#wpal-root .wp-enl #node-{nid} .aed-cc [data-x=delc]")
        page.wait_for_timeout(800)
        assert page.evaluate(NEW) == [] and page.evaluate("AltoWorld.data.used.JPN == null")
        page.wait_for_timeout(900)
        page.reload()
        _ready(page)
        assert page.evaluate(NEW) == []                                                # and still gone
        assert not [u for u in asked if "/mcp" in u or "anthropic" in u or "claude" in u.lower()], asked
        assert not errors, errors
    finally:
        page.close()


def test_one_undo_takes_the_card_and_its_place_back(browser, origin):  # noqa: F811
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(origin + "/index.html")
        _ready(page)
        page.evaluate("sessionStorage.clear(); window._altoManual.enter()")
        page.evaluate("AltoWorld.pickCountry()")
        page.fill("#wpal-root .wp-pick input", "Japan")
        page.click("#wpal-root .wp-pick .l button")
        page.wait_for_timeout(1200)
        assert len(page.evaluate(NEW)) == 1
        page.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
        page.evaluate("window._altoManual.undo()")
        page.wait_for_timeout(400)
        assert page.evaluate(NEW) == []
        page.evaluate("window._altoManual.redo()")
        page.wait_for_timeout(400)
        assert len(page.evaluate(NEW)) == 1
    finally:
        page.close()


def test_the_edit_bar_clears_the_tour_strip(browser, origin):  # noqa: F811
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(origin + "/index.html")
        _ready(page)
        page.evaluate("AltoWorld.tourMode(true); window._altoManual.enter()")
        page.wait_for_timeout(400)
        gap = page.evaluate("(() => { var e = document.getElementById('alto-edit-exit').getBoundingClientRect(), t = document.querySelector('#wpal-root .wp-tour').getBoundingClientRect(); return t.top - e.bottom; })()")
        assert gap >= 0, gap                                                          # (Art: it sat on the strip)
    finally:
        page.close()
