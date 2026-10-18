"""The solar outline's front doors (the UI/integration side of layout 'solar'):
the homepage's starter and its preview, the connector's tool arguments and
docstrings, the interview guide's section, and what folding the owner's manual
edits does on a solar timeline (alto/edits.py, alto/build/manual_edit.py).

How solar is planned and drawn is alto/build/solar.py and solar_draw.py."""
import copy
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto.build import starter  # noqa: E402
from alto.build.brief import LAYOUTS  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.brief import validate_brief, validate_nodes  # noqa: E402
from alto.edits import fold  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

from tests.test_manual_edit import Store, _node  # noqa: E402

needs_solar = pytest.mark.skipif("solar" not in LAYOUTS, reason="needs alto-solar-lead's layout 'solar'")
GUIDE = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")


def _draft(**brief_extra):
    d = starter.draft("solar")
    d["brief"].update(brief_extra)
    return d


# ── the starter ──────────────────────────────────────────────────────────────

def test_the_solar_starter_is_an_outline_of_two_systems():
    s = starter._STARTERS["solar"]
    b = s["brief"]
    assert "solar" in starter.KINDS and b["mode"] == "outline" and b["layout"] == "solar"
    assert b["hub_style"] == "orbit" and len(b["acts"]) == 2
    by = {n["id"]: n for n in s["nodes"]}
    roots = [n for n in s["nodes"] if not n.get("parent")]
    assert sorted(n["act"] for n in roots) == [0, 1]                       # one sun to a unit
    # sun, planets and a moon: the three depths the picture is made of
    assert by["unit-1-a"]["parent"] == "unit-1-start" and by["unit-1-a1"]["parent"] == "unit-1-a"
    assert all(by[n["parent"]]["act"] == n["act"] for n in s["nodes"] if n.get("parent"))


@needs_solar
def test_the_solar_starter_page_builds_and_carries_its_brief():
    d = starter.draft("solar")
    b, nodes, conns = load_brief(d)
    validate_brief(b)
    validate_nodes(b, nodes)
    assert b.layout == "solar" and b.hub_style == "orbit"
    page = starter.page("solar")
    assert starter.TID in page and starter.TITLE in page


def test_the_solar_button_sits_after_the_horizontal_one_with_a_moving_preview():
    h = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    blk = h[h.index('class="nt-kinds"'):h.index('id="nt-msg"')]
    i = blk.index('data-kind="solar"')
    assert blk.index('data-kind="lanes"') < i
    mine = blk[i:]
    assert mine.count("<circle") >= 8 and "pv-o1" in mine and "pv-om" in mine     # a sun, rings, planets, a moon
    assert "Solar" in mine and "<svg" in mine and 'aria-hidden="true"' in mine
    css = h[h.index(".nt-pv{"):h.index(".nt-make{")]
    assert "@keyframes ntorb" in css
    # the orbit preview stands still for anyone who asks for reduced motion
    red = [m for m in re.findall(r"@media \(prefers-reduced-motion:reduce\)\{[^}]*\{[^}]*\}[^}]*\}", css) if "pv-o1" in m]
    assert red and "animation:none" in red[0]


def test_the_picker_stays_inside_the_dialog_with_four_choices():
    h = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    assert "#nt-modal{ width:720px; }" in h and "max-width:calc(100vw - 32px)" in h


# ── tools ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tool", ["run_layout_preview", "build_timeline"])
def test_the_layout_tools_take_a_hub_style_and_explain_it(tool):
    fn = getattr(srv, tool)
    assert "hub_style" in inspect.signature(fn).parameters
    assert inspect.signature(fn).parameters["hub_style"].default == ""        # '' keeps the brief's
    doc = fn.__doc__
    assert "solar" in doc and "orbit" in doc and "spoke" in doc


def test_create_timeline_explains_the_solar_layout_and_its_two_styles():
    doc = " ".join(srv.create_timeline.__doc__.split())
    for want in ("layout?: 'auto'|'tree'|'flow'|'solar'", "hub_style?: 'orbit'|'spoke'", "SUN", "PLANETS", "MOONS",
                 "SATELLITES", "planets' order is the outline's order", "innermost ring",
                 "one unit", "several units", "per timeline", "single-column"):
        assert want in doc, want


@needs_solar
def test_a_wrong_hub_style_is_told_plainly():
    doc = {"brief": {"layout": "solar"}}
    assert srv._layout_error(doc, "", "") is None and srv._layout_error(doc, "", "orbit") is None
    assert srv._layout_error(doc, "solar", "spoke") is None
    assert srv._layout_error({"brief": {}}, "solar", "orbit") is None
    assert srv._layout_error(doc, "", "swirl")["error"] == "invalid_hub_style"
    r = srv._layout_error({"brief": {"layout": "tree"}}, "", "spoke")
    assert r["error"] == "invalid_hub_style" and "layout 'solar'" in r["message"]
    r = srv._layout_error({"brief": {}}, "tree", "orbit")
    assert r["error"] == "invalid_hub_style"


def test_a_layout_choice_is_kept_in_the_brief_only_when_given():
    doc = {"brief": {"layout": "solar", "hub_style": "orbit", "tree_lines": "fan"}}
    assert srv._layout_choice(doc, "", "")["brief"] == doc["brief"]
    assert srv._layout_choice(doc, "", "", "spoke")["brief"]["hub_style"] == "spoke"
    assert srv._layout_choice({"brief": {}}, "solar", "", "orbit")["brief"] == {"layout": "solar", "hub_style": "orbit"}
    assert doc["brief"]["hub_style"] == "orbit"                                # the stored one is not touched


@pytest.fixture
def local_store(tmp_path):
    srv.set_store(LocalStore(tmp_path))
    yield
    srv.set_store(None)


@needs_solar
def test_a_solar_timeline_goes_through_the_tools_and_keeps_its_style(local_store):
    d = starter.draft("solar")
    pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
    r = srv.create_timeline(pid, {**d["brief"], "title": "Torts"})
    assert "error" not in r, r
    tid = r["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
    assert "error" not in srv.add_nodes(tid, d["nodes"])
    pre = srv.run_layout_preview(tid, hub_style="spoke")
    assert "error" not in pre, pre
    assert srv.get_timeline(tid)["brief"].get("hub_style", "orbit") == "orbit"   # a preview stores nothing
    built = srv.build_timeline(tid, layout="solar", hub_style="spoke")
    assert built.get("verify") == "passed", built
    assert srv.get_timeline(tid)["brief"]["hub_style"] == "spoke"                # kept for every later build
    assert "error" not in srv.build_timeline(tid)                                # and used by it
    assert srv.get_timeline(tid)["brief"]["hub_style"] == "spoke"
    r = srv.build_timeline(tid, hub_style="swirl")
    assert r["error"] == "invalid_hub_style"
    w = srv.place_nodes(tid, {"unit-1-a": {"arrange": "row"}})
    assert any("solar" in x for x in w["warnings"]), w


# ── the interview guide ──────────────────────────────────────────────────────

def test_the_guide_has_a_solar_section_that_asks_the_two_questions():
    i = GUIDE.index("### §D-Solar.")
    sec = " ".join(GUIDE[i:GUIDE.index("### B. Subject & spine")].split())
    for want in ("layout: 'solar'", "hub_style: 'orbit' | 'spoke'", "sun", "planets", "moons", "satellites",
                 "One system, or one per unit?", "Orbit, or spokes?", "outline's order", "innermost ring",
                 "single-column", "reduced motion", "Nothing goes deeper", "Do not flatten it quietly"):
        assert want in sec, want
    # routed from the shape question, and into the build sequence
    assert "**§D-Solar**" in GUIDE[GUIDE.index("### B0."):i]
    assert "hub_style='orbit'|'spoke'" in GUIDE[GUIDE.index("## Build sequence"):]


def test_the_guide_never_has_claude_choose_the_students_structure_for_solar():
    sec = " ".join(GUIDE[GUIDE.index("### §D-Solar."):GUIDE.index("### B. Subject & spine")].split())
    assert "never invent a unit or a hub" in sec and "their structure; you do not choose for them" in sec


# ── editing a solar timeline by hand ─────────────────────────────────────────

def _solar_store(extra_nodes=None, **brief):
    d = starter.draft("solar")
    d["brief"].update(brief)
    d["brief"]["title"] = "Torts"
    d["nodes"] = d["nodes"] + (extra_nodes or [])
    return Store(d)


def _ops(**kw):
    return {"v": 1, "ops": {k: dict(v, t=i + 1) for i, (k, v) in enumerate(kw.items())}}


@needs_solar
def test_reparenting_and_reordering_fold_into_the_outline_on_a_solar_timeline():
    st = _solar_store()
    st.edits = {"v": 1, "ops": {
        "rp|unit-1-b": {"b": "unit-1-start", "v": "unit-1-a", "t": 1},                  # a planet becomes a moon
        "so|unit-1-start": {"b": ["unit-1-a", "unit-1-b"], "v": ["unit-1-a"], "t": 2}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"], r
    assert _node(st, "unit-1-b")["parent"] == "unit-1-a"
    html, _ = build_timeline(*load_brief({"brief": st.doc["brief"], "nodes": st.nodes}))
    assert "unit-1-b" in html


@needs_solar
def test_a_dragged_position_or_size_is_not_kept_on_a_solar_timeline():
    st = _solar_store()
    st.edits = {"v": 1, "ops": {
        "p|unit-1-a|shift": {"b": None, "v": [40, 90], "t": 1},
        "p|unit-1-a|slide": {"b": None, "v": [10, 0], "t": 2},
        "sz|unit-1-a": {"b": None, "v": {"w": 300}, "t": 3},
        "n|unit-1-a|title": {"b": "First concept", "v": "Duty", "t": 4}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 1 and _node(st, "unit-1-a")["title"] == "Duty", r
    assert r["solar_positions_ignored"] == 3 and sorted(r["gone"]) == ["p|unit-1-a|shift", "p|unit-1-a|slide", "sz|unit-1-a"]
    pl = st.doc["brief"].get("placement") or {}
    assert "shift" not in (pl.get("unit-1-a") or {}) and not st.doc["brief"].get("card_size")


def test_the_same_drag_is_still_kept_on_a_tree():
    d = starter.draft("outline")
    d["brief"]["title"] = "T"
    st = Store(d)
    st.edits = {"v": 1, "ops": {"p|unit-1-start|shift": {"b": None, "v": [40, 90], "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 1 and "solar_positions_ignored" not in r


@needs_solar
def test_a_move_or_a_new_card_past_the_satellites_is_left_out_and_said():
    deeper = [{"id": "unit-1-a1x", "act": 0, "parent": "unit-1-a1", "title": "A satellite", "tag": "", "desc": ""}]
    st = _solar_store(deeper)                       # sun > planet a > moon a1 > satellite a1x
    st.edits = {"v": 1, "ops": {
        "nn|card-aaaa11": {"b": None, "v": {"p": "unit-1-a1x", "a": "unit-1", "t": "Too deep"}, "t": 1},
        "rp|unit-1-b": {"b": "unit-1-start", "v": "unit-1-a1x", "t": 2},
        "n|unit-1-b|title": {"b": "Second concept", "v": "Breach", "t": 3}}}
    r = fold(st, "u", "t1")
    assert sorted(r["conflicts"]) == ["nn|card-aaaa11", "rp|unit-1-b"], r
    assert sorted(x["id"] for x in r["solar_too_deep"]) == ["card-aaaa11", "unit-1-b"], r
    assert "deeper than a satellite" in r["note"]
    assert _node(st, "unit-1-b")["parent"] == "unit-1-start" and _node(st, "unit-1-b")["title"] == "Breach"
    assert not any(n["id"] == "card-aaaa11" for n in st.nodes)


@needs_solar
def test_moving_a_branch_counts_its_own_depth():
    # unit-1-a has a moon: under a planet it would make a satellite, under a moon too deep
    st = _solar_store()
    st.edits = {"v": 1, "ops": {"rp|unit-1-a": {"b": "unit-1-start", "v": "unit-1-b", "t": 1}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and _node(st, "unit-1-a")["parent"] == "unit-1-b", r     # sun > b > a > a1: fine
    st = _solar_store([{"id": "unit-1-b1", "act": 0, "parent": "unit-1-b", "title": "x", "tag": "", "desc": ""}])
    st.edits = {"v": 1, "ops": {"rp|unit-1-a": {"b": "unit-1-start", "v": "unit-1-b1", "t": 1}}}
    r = fold(st, "u", "t1")                                                           # sun > b > b1 > a > a1: five levels
    assert r["conflicts"] == ["rp|unit-1-a"] and _node(st, "unit-1-a")["parent"] == "unit-1-start", r


# ── the page's side of it ────────────────────────────────────────────────────

def test_the_edit_module_keeps_a_solar_page_free_of_free_placement():
    js = (ROOT / "alto" / "build" / "manual_edit.py").read_text(encoding="utf-8")
    assert "function isSolar(){ return !!window._ALTO_SOLAR; }" in js
    assert "!isSolar() && !root.classList.contains('mobile') && !PHONE));" in js          # no drag mode
    assert "if(!editing() || isSolar() || !root.classList.contains('alto-drag-ok')" in js   # nor a drag on its own
    assert "if(!isSolar() && !card.querySelector(':scope > .aed-rz'))" in js              # no size handle
    for guard in ("if(solarDeep(p)){ solarNo(); return; }", "if(solarDeep(np, id)){ solarNo(); return false; }",
                  "if(np !== p && solarDeep(np, id)){ solarNo(); return; }"):
        assert guard in js, guard
    assert "SOLAR_MAX = 3" in js
    # the hook DRAW's layer implements, called before the cards are laid out again
    assert js.index("solarSync();\n    try{ initLayout();") > 0
    assert "window._altoSolarSync({kids:" in js


def test_the_depth_rule_is_the_same_on_the_page_and_in_the_fold():
    from alto.edits import SOLAR_MAX_DEPTH
    js = (ROOT / "alto" / "build" / "manual_edit.py").read_text(encoding="utf-8")
    assert f"SOLAR_MAX = {SOLAR_MAX_DEPTH}" in js


# ── a phone keeps the engine's card view ─────────────────────────────────────
# (Chromium and WebKit; skipped without Playwright — the repo's venv has none:
#  PYTHONPATH=<a venv's site-packages with playwright> pytest tests/test_solar_ui.py)

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _built(layout):
    d = starter.draft("solar")
    d["brief"].update(title="Torts", timeline_id="torts", layout=layout)
    for n in d["nodes"]:
        n["desc"] = f"{n['title']}: the material's words."
    return build_timeline(*load_brief(d))[0]


PHONE_VIEW = """() => ({mobile: document.documentElement.classList.contains('mobile'),
    solar_layers: [].filter.call(document.querySelectorAll('[id^=solar], [class*=solar-]'), function(e){
        var s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden' && e.getBoundingClientRect().width > 0; }).map(function(e){ return e.id || e.className; }),
    cards: [].map.call(document.querySelectorAll('.node'), function(n){
        var c = n.querySelector('.node-card') || n, r = c.getBoundingClientRect(), s = getComputedStyle(c);
        return {id: n.id, x: Math.round(r.left), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height), br: s.borderRadius}; })})"""


def _phone(browser, html, tmp_path, name):
    f = tmp_path / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, user_agent=PHONE_UA, has_touch=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1500)
    first = pg.evaluate(PHONE_VIEW)
    pg.wait_for_timeout(1200)                      # nothing orbits on a phone: a second look is the same
    again = pg.evaluate(PHONE_VIEW)
    ctx.close()
    return first, again, errs


@needs_solar
def test_a_phone_keeps_the_single_column_card_view_of_a_tree(browser, tmp_path):
    s1, s2, errs = _phone(browser, _built("solar"), tmp_path, "solar")
    t1, _, terrs = _phone(browser, _built("tree"), tmp_path, "tree")
    assert not errs and not terrs, (errs, terrs)
    assert s1["mobile"] and not s1["solar_layers"], s1["solar_layers"]       # no rings, no spokes on a phone
    assert s1["cards"] == s2["cards"]                                        # and nothing moves
    assert [c["id"] for c in s1["cards"]] == [c["id"] for c in t1["cards"]]
    assert all("50%" not in c["br"] and c["w"] > c["h"] * 1.2 for c in s1["cards"] if c["w"]), s1["cards"]   # cards, not circles
    # the same cards in the same places as the tree's phone view
    assert [(c["x"], c["y"], c["w"], c["h"]) for c in s1["cards"]] == [(c["x"], c["y"], c["w"], c["h"]) for c in t1["cards"]]


# ── manual edit mode on a solar page, in a real browser ──────────────────────
# `window._ALTO_SOLAR` is what marks the page; it is stood in for here when the
# build has not put it there, so these hold whichever way the layer is built.

import functools  # noqa: E402
import http.server  # noqa: E402
import socketserver  # noqa: E402
import threading  # noqa: E402

FAKE_CLOUD = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""
MARK_SOLAR = "if(!window._ALTO_SOLAR) window._ALTO_SOLAR = {style: 'orbit', systems: [], nodes: {}};"
SPY = "window.__sync = []; window._altoSolarSync = function(t){ window.__sync.push({kids: JSON.parse(JSON.stringify(t.kids)), parent: JSON.parse(JSON.stringify(t.parent))}); };"


def _deep_page_html():
    d = starter.draft("solar")
    d["brief"].update(title="Torts", timeline_id="torts")
    # sun > a > a1 > a1x: a satellite, as deep as it goes
    d["nodes"] += [{"id": "unit-1-a1x", "act": 0, "parent": "unit-1-a1", "title": "A satellite", "tag": "", "desc": ""}]
    for n in d["nodes"]:
        n["desc"] = f"{n['title']}: the material's words."
    return build_timeline(*load_brief(d))[0]


@pytest.fixture
def edit_url(tmp_path):
    (tmp_path / "page.html").write_text(_deep_page_html(), encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv_ = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv_.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv_.server_address[1]}/page.html"
    srv_.shutdown()


def _editing(browser, url, hook):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    ctx.add_init_script(FAKE_CLOUD)
    ctx.add_init_script(f"document.addEventListener('DOMContentLoaded', function(){{ {MARK_SOLAR} {SPY if hook else ''} }});")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(1500)
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    return pg, errs


def _edit_ops(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k=>k.indexOf('alto-ed-')===0)[0]) || '{\"ops\":{}}').ops")


def _toast(pg):
    return pg.evaluate("(document.getElementById('aed-toast')||{}).textContent || ''")


@needs_solar
def test_a_solar_page_keeps_no_dragged_position_or_size_handle(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    assert pg.evaluate("document.documentElement.classList.contains('alto-editing')")
    assert not pg.evaluate("document.documentElement.classList.contains('alto-drag-ok')")
    pg.evaluate("document.getElementById('node-unit-1-b').scrollIntoView({block:'center'})")
    pg.wait_for_timeout(250)
    x, y = pg.evaluate("(()=>{var r=document.querySelector('#node-unit-1-b .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+18];})()")
    pg.mouse.move(x, y)
    pg.mouse.down()
    for k in range(1, 13):
        pg.mouse.move(x + 200 * k / 12, y + 90 * k / 12)
        pg.wait_for_timeout(16)
    pg.mouse.up()
    pg.wait_for_timeout(500)
    assert not [k for k in _edit_ops(pg) if k.startswith(("p|", "sz|"))], _edit_ops(pg)
    assert pg.evaluate("document.querySelectorAll('.aed-rz').length") == 0
    assert not errs, errs


@needs_solar
def test_a_card_cannot_be_added_or_moved_past_the_satellites_but_can_elsewhere(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    sat = "unit-1-a1x"
    pg.evaluate(f"document.getElementById('node-{sat}').scrollIntoView({{block:'center'}})")
    pg.wait_for_timeout(250)
    pg.hover(f"#node-{sat} .node-title")
    pg.click(f'#node-{sat} .aed-cc button[data-x="addc"]')
    pg.wait_for_timeout(300)
    assert "sun, planet, moon, satellite" in _toast(pg) and not [k for k in _edit_ops(pg) if k.startswith("nn|")]
    def move(card, under):
        pg.evaluate(f"document.getElementById('node-{card}').scrollIntoView({{block:'center'}})")
        pg.wait_for_timeout(200)
        pg.hover(f"#node-{card} .node-title")
        pg.click(f'#node-{card} .aed-cc button[data-x="linkc"]')
        pg.wait_for_timeout(200)
        pg.evaluate(f"document.querySelector('#node-{under} .node-card').click()")
        pg.wait_for_timeout(600)

    DEEP = "sun, planet, moon, satellite"
    parent = lambda i: pg.evaluate(f"_ALTO_OUTLINE.parent['{i}']")
    # a leaf under a satellite would be a fifth level
    move("unit-1-b", sat)
    assert DEEP in _toast(pg) and parent("unit-1-b") == "unit-1-start" and "rp|unit-1-b" not in _edit_ops(pg)
    assert pg.evaluate("document.documentElement.classList.contains('aed-linking')")      # still choosing: another card may do
    assert pg.evaluate("document.querySelector('#node-unit-1-a1x').classList.contains('aed-link-no')")  # and the too-deep ones are marked
    pg.keyboard.press("Escape")
    # a moon with its satellite under the planet b: sun > b > a1 > a1x, the last level, is fine
    move("unit-1-a1", "unit-1-b")
    assert parent("unit-1-a1") == "unit-1-b" and _edit_ops(pg)["rp|unit-1-a1"]["v"] == "unit-1-b", _edit_ops(pg)
    # b now carries two levels below it: under the planet a it would pass the satellites
    pg.evaluate("document.getElementById('aed-toast').textContent = ''")
    move("unit-1-b", "unit-1-a")
    assert DEEP in _toast(pg) and parent("unit-1-b") == "unit-1-start" and "rp|unit-1-b" not in _edit_ops(pg)
    assert not errs, errs


@needs_solar
def test_the_solar_layer_is_told_about_every_structural_change(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    pg.evaluate("document.getElementById('node-unit-1-b').scrollIntoView({block:'center'})")
    pg.hover("#node-unit-1-b .node-title")
    pg.click('#node-unit-1-b .aed-cc button[data-x="linkc"]')
    pg.wait_for_timeout(200)
    pg.evaluate("document.querySelector('#node-unit-1-a .node-card').click()")
    pg.wait_for_timeout(900)
    calls = pg.evaluate("window.__sync")
    assert calls and calls[-1]["parent"]["unit-1-b"] == "unit-1-a" and "unit-1-b" in calls[-1]["kids"]["unit-1-a"], calls
    assert not pg.evaluate("document.documentElement.classList.contains('alto-solar-stale')")
    assert not errs, errs


@needs_solar
def test_without_the_solar_layer_a_change_is_saved_and_said_to_wait_for_the_next_build(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=False)
    pg.evaluate("document.getElementById('node-unit-1-b').scrollIntoView({block:'center'})")
    pg.hover("#node-unit-1-b .node-title")
    pg.click('#node-unit-1-b .aed-cc button[data-x="linkc"]')
    pg.wait_for_timeout(200)
    pg.evaluate("document.querySelector('#node-unit-1-a .node-card').click()")
    pg.wait_for_timeout(900)
    assert "rp|unit-1-b" in _edit_ops(pg)
    assert pg.evaluate("document.documentElement.classList.contains('alto-solar-stale')")
    assert not errs, errs
