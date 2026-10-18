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
    assert b["hub_style"] == "spoke" and len(b["acts"]) == 2
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
    assert b.layout == "solar" and b.hub_style == "spoke"
    page = starter.page("solar")
    assert starter.TID in page and starter.TITLE in page


def test_hub_and_spoke_has_a_still_preview_and_the_star_chart_a_moving_one():
    h = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    blk = h[h.index('class="nt-kinds"'):h.index('id="nt-msg"')]
    hub = blk[blk.index('data-kind="solar"'):blk.index('data-kind="palace"')]
    assert "Hub &amp; spoke" in hub and "Solar" not in hub and "pv-o1" not in hub and "<animate" not in hub
    assert hub.count("<circle") >= 6 and 'aria-hidden="true"' in hub                   # a hub and circles on spokes
    assert "star chart anytime" in hub and "Ask Claude to turn it into" in hub          # the way to the moving one
    stars = blk[blk.index('data-for="stars" viewBox'):]
    assert "pv-o1" in stars and "pv-om" in stars and stars.count("<circle") >= 8       # it orbits
    css = h[h.index(".nt-pv{"):h.index(".nt-make{")]
    assert "@keyframes ntorb" in css
    # the orbit preview stands still for anyone who asks for reduced motion
    red = [m for m in re.findall(r"@media \(prefers-reduced-motion:reduce\)\{[^}]*\{[^}]*\}[^}]*\}", css) if "pv-o1" in m]
    assert red and "animation:none" in red[0]


def test_the_picker_stays_inside_the_dialog_with_four_tiles():
    h = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    assert "#nt-modal{ width:720px; }" in h and "max-width:calc(100vw - 32px)" in h


def test_the_star_chart_starter_is_a_palace_without_a_city():
    s = starter._STARTERS["stars"]
    b = s["brief"]
    assert b["mode"] == "palace" and b["palace_view"] == "stars" and "palace" not in b      # no map, so it can be made in a browser
    roots = [n for n in s["nodes"] if not n.get("parent")]
    assert sorted(n["act"] for n in roots) == [0, 1]
    assert ("stars" in starter.KINDS) == ("palace_view" in __import__("alto.build.brief", fromlist=["Brief"]).Brief.__dataclass_fields__)


# ── tools ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tool", ["run_layout_preview", "build_timeline"])
def test_the_layout_tools_take_a_hub_style_and_explain_it(tool):
    fn = getattr(srv, tool)
    assert "hub_style" in inspect.signature(fn).parameters
    assert inspect.signature(fn).parameters["hub_style"].default == ""        # '' keeps the brief's
    doc = fn.__doc__
    assert "solar" in doc and "spoke" in doc and "Hub & spoke" in doc


def test_create_timeline_explains_hub_and_spoke_and_the_star_chart():
    doc = " ".join(srv.create_timeline.__doc__.split())
    for want in ("layout?: 'auto'|'tree'|'flow'|'solar'", "HUB & SPOKE", "hub_style?: 'spoke'|'orbit'", "SUN", "PLANETS", "MOONS",
                 "SATELLITES", "planets' order is the outline's order", "innermost ring", "ONE unit", "just one", "several units",
                 "single-column", "palace_view?: 'city'|'stars'", "STAR CHART", "convert_timeline", "content is kept, both ways"):
        assert want in doc, want


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
    pre = srv.run_layout_preview(tid, hub_style="orbit")
    assert "error" not in pre, pre
    assert srv.get_timeline(tid)["brief"].get("hub_style") == "spoke"   # a preview stores nothing
    built = srv.build_timeline(tid, layout="solar", hub_style="orbit")
    assert built.get("verify") == "passed", built
    assert srv.get_timeline(tid)["brief"]["hub_style"] == "orbit"                # kept for every later build
    assert "error" not in srv.build_timeline(tid)                                # and used by it
    assert srv.get_timeline(tid)["brief"]["hub_style"] == "orbit"
    r = srv.build_timeline(tid, hub_style="swirl")
    assert r["error"] == "invalid_hub_style"
    w = srv.place_nodes(tid, {"unit-1-a": {"arrange": "row"}})
    assert any("solar" in x for x in w["warnings"]), w


# ── the interview guide

def _sec(a, b):
    return " ".join(GUIDE[GUIDE.index(a):GUIDE.index(b)].split())


def test_the_guide_has_a_hub_and_spoke_section_that_asks_one_or_several():
    sec = _sec("### §D-Solar.", "### §D-Stars.")
    for want in ("Hub & spoke", "layout: 'solar'", "hub_style: 'spoke'", "sun", "planets", "moons", "satellites",
                 "One system in great detail, or several", "outline's order", "innermost ring", "single-column",
                 "Nothing goes deeper", "Do not flatten it quietly", "a one-unit Hub & spoke is valid",
                 "drag its circle onto the other circle", "pivotal, critical or extremely important", "zooms out"):
        assert want in sec, want
    assert "§D-Solar**" in GUIDE[GUIDE.index("### B0."):GUIDE.index("### §D-Palace.")]
    assert "hub_style='spoke'" in GUIDE[GUIDE.index("## Build sequence"):]


def test_the_guide_offers_the_star_chart_conversion_once_and_says_nothing_is_lost():
    sec = _sec("**Moving it: the Star chart.**", "### §D-Stars.")
    for want in ("ringed-planet tile", "Turn this into a star chart", "once, at the end of the build",
                 "move, orbit, or look like a solar system or a galaxy", "convert_timeline(timeline_id, to='star_chart')",
                 "Nothing is lost", "convert_timeline(timeline_id, to='hub_and_spoke')", "never rebuild the timeline by hand"):
        assert want in sec, want


def test_the_guide_has_a_star_chart_section_for_the_palace_view():
    sec = _sec("### §D-Stars.", "### B. Subject & spine")
    for want in ("palace_view: 'stars'", "sun", "planets", "moons", "satellites", "fifth level", "do not ask which city",
                 "bigger the more hangs off", "pivotal, critical or extremely important", "inner rings faster",
                 "reduced motion", "zoom out", "convert_timeline", "Nothing is lost", "Mind Palace keeps its city"):
        assert " ".join(want.split()) in sec or want.lower() in sec.lower(), want


def test_the_guide_never_has_claude_choose_the_students_structure_for_solar():
    sec = _sec("### §D-Solar.", "### §D-Stars.")
    assert "never invent a unit or a hub" in sec and "their structure; you do not choose for them" in sec


# ── turning a Hub & spoke timeline into a star chart ─────────────────────────

def test_a_hub_and_spoke_page_carries_a_ringed_planet_tile_never_the_sparkle():
    js = (ROOT / "alto" / "build" / "manual_edit.py").read_text(encoding="utf-8")
    assert "S.style !== 'spoke'" in js and "tid.indexOf('s-') === 0" in js            # Hub & spoke only; not on a share
    assert "Turn this into a star chart" in js and "convert_timeline" in js and "window._altoAskClaude" in js
    assert "html.mobile #alto-star-tile,html.alto-editing #alto-star-tile,html.printing #alto-star-tile{display:none !important;}" in js
    svg = js[js.index("var STAR_SVG = '") + 16:]
    svg = svg[:svg.index("';")]
    assert "<circle" in svg and "<ellipse" in svg and 'aria-hidden="true"' in svg and "currentColor" in svg
    assert 'viewBox="0 0 24 24"' in svg and "17" in svg
    # the four-point sparkle is the Overview's icon: nothing new here uses one
    h = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    assert "\u2726" not in js + h and "✦" not in js + h and "&#10022;" not in js + h


def test_the_homepage_menu_offers_it_on_a_hub_and_spoke_timeline():
    h = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")
    m = h[h.index("function altoTileMenu(pg)"):h.index("function moveView()")]
    assert "if(pg.view === 'hubspoke')" in m and "Turn this into a star chart" in m and "openClaude(altoStarChartPrompt(pg))" in m
    pr = h[h.index("function altoStarChartPrompt(pg)"):h.index("function altoTileMenu(pg)")]
    for want in ("pg.heading || pg.title", "pg.tid", "Hub & spoke into a Star chart", "convert_timeline", "keeping all of its content", "list_projects(account=\"all\")"):
        assert want in pr, want


@needs_solar
def test_the_listing_record_marks_a_hub_and_spoke_page_in_both_writers():
    from alto.cloud.meta import meta_of
    page = starter.page("solar")
    assert meta_of(page)["view"] == "hubspoke"
    assert "view" not in meta_of(starter.page("outline"))                      # nothing else changes
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    assert "{ view: 'hubspoke' }" in js and "view: v.view || ''" in js


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
    ctx = browser.new_context(viewport={"width": 1500, "height": 1150})
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


def _ctl(pg, card, x):
    """A card's small control (addc, linkc, …), pressed directly: circles that
    overlap or move would otherwise take the pointer from the card under them."""
    pg.evaluate(f"document.getElementById('node-{card}').scrollIntoView({{block:'center'}})")
    pg.wait_for_timeout(200)
    pg.evaluate(f"document.querySelector('#node-{card} .node-title').dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}))")
    assert pg.evaluate(f"(()=>{{var b=document.querySelector('#node-{card} .aed-cc button[data-x=\"{x}\"]'); if(!b) return false; b.click(); return true;}})()"), (card, x)
    pg.wait_for_timeout(250)


def _toast(pg):
    return pg.evaluate("(document.getElementById('aed-toast')||{}).textContent || ''")


def _centre(pg, card):
    return pg.evaluate(f"(()=>{{var r=document.querySelector('#node-{card} .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2];}})()")


def _show(pg, *cards):
    """Scroll so every card is on screen at once (the page is tall; the viewport 1150)."""
    pg.evaluate(f"document.getElementById('node-{cards[0]}').scrollIntoView({{block:'start'}}); window.scrollBy(0, -60)")
    pg.wait_for_timeout(250)
    for c in cards:
        x, y = _centre(pg, c)
        assert 40 < y < 1100, (c, y)


def _circle_drag(pg, card, to, release=True, escape=False):
    """Drag a circle by mouse to a card (by id) or a point; returns the page's view of the drag
    mid-way (the card's translate, the drop highlights, the tip) before releasing."""
    x0, y0 = _centre(pg, card)
    x1, y1 = _centre(pg, to) if isinstance(to, str) else to
    pg.mouse.move(x0, y0 - 20)
    pg.mouse.down()
    for k in range(1, 15):
        pg.mouse.move(x0 + (x1 - x0) * k / 14, y0 - 20 + (y1 - y0 + 20) * k / 14)
        pg.wait_for_timeout(16)
    pg.wait_for_timeout(120)
    mid = pg.evaluate(f"""({{moved: document.getElementById('node-{card}').style.translate,
        ok: [...document.querySelectorAll('.aed-drop-ok')].map(n => n.id), no: [...document.querySelectorAll('.aed-drop-no')].map(n => n.id),
        tip: (document.getElementById('aed-rztip') || {{}}).textContent || ''}})""")
    if escape:
        pg.keyboard.press("Escape")
    if release:
        pg.mouse.up()
    pg.mouse.move(5, 600)
    pg.wait_for_timeout(500)
    return mid


def _home(pg, card):
    return pg.evaluate(f"document.getElementById('node-{card}').style.translate") in ("", None)


@needs_solar
def test_a_solar_page_keeps_no_dragged_position_or_size_handle(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    assert pg.evaluate("document.documentElement.classList.contains('alto-editing')")
    assert not pg.evaluate("document.documentElement.classList.contains('alto-drag-ok')")
    assert pg.evaluate("document.documentElement.classList.contains('alto-solar-edit')")
    _show(pg, "unit-1-a", "unit-1-b")
    mid = _circle_drag(pg, "unit-1-b", (120, 700))                         # let go on empty space
    assert mid["moved"], mid                                               # it followed the pointer ...
    assert _home(pg, "unit-1-b") and _edit_ops(pg) == {}, _edit_ops(pg)     # ... and went home, storing nothing
    assert pg.evaluate("document.querySelectorAll('.aed-rz').length") == 0
    assert not errs, errs


@needs_solar
def test_a_circle_dropped_on_another_goes_under_it_and_the_layer_is_told(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    _show(pg, "unit-1-a1x", "unit-1-b")
    mid = _circle_drag(pg, "unit-1-a1x", "unit-1-b")
    assert mid["ok"] == ["node-unit-1-b"] and "Move under" in mid["tip"], mid
    assert _edit_ops(pg)["rp|unit-1-a1x"]["v"] == "unit-1-b", _edit_ops(pg)     # the card menu's own op
    assert pg.evaluate("_ALTO_OUTLINE.parent['unit-1-a1x']") == "unit-1-b"
    calls = pg.evaluate("window.__sync")
    assert calls and calls[-1]["parent"]["unit-1-a1x"] == "unit-1-b", calls
    assert not [k for k in _edit_ops(pg) if k.startswith("p|")]
    assert _home(pg, "unit-1-a1x") and not pg.evaluate("document.querySelectorAll('.aed-drop-ok, .aed-drop-no').length")
    assert "Moved under" in _toast(pg) and not errs, errs


@needs_solar
def test_a_circle_is_refused_past_the_satellites_and_on_itself_or_what_orbits_it(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    _show(pg, "unit-1-a", "unit-1-b")
    # the planet a carries a moon and a satellite: under b they would be one level too many
    mid = _circle_drag(pg, "unit-1-a", "unit-1-b")
    assert mid["no"] == ["node-unit-1-b"] and mid["ok"] == [] and "Too deep" in mid["tip"], mid
    assert "sun, planet, moon, satellite" in _toast(pg)
    assert "rp|unit-1-a" not in _edit_ops(pg) and _home(pg, "unit-1-a")
    assert pg.evaluate("_ALTO_OUTLINE.parent['unit-1-a']") == "unit-1-start"
    # never onto what orbits it
    _show(pg, "unit-1-a1x", "unit-1-a")
    mid = _circle_drag(pg, "unit-1-a", "unit-1-a1x")
    assert mid["ok"] == [] and "cannot go under itself" in mid["tip"], mid
    assert "rp|unit-1-a" not in _edit_ops(pg) and _home(pg, "unit-1-a")
    # a unit's sun has nowhere to go: it is not picked up
    _show(pg, "unit-1-start")
    x, y = _centre(pg, "unit-1-start")
    pg.mouse.move(x, y - 20); pg.mouse.down(); pg.mouse.move(x + 150, y + 60, steps=8); pg.mouse.up()
    pg.wait_for_timeout(300)
    assert _home(pg, "unit-1-start") and "rp|unit-1-start" not in _edit_ops(pg)
    assert not errs, errs


@needs_solar
def test_escape_puts_a_dragged_circle_back_without_a_trace(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    _show(pg, "unit-1-a1x", "unit-1-b")
    mid = _circle_drag(pg, "unit-1-a1x", "unit-1-b", escape=True)
    assert mid["ok"] == ["node-unit-1-b"]                                  # it was a valid drop until Escape
    assert _edit_ops(pg) == {} and _home(pg, "unit-1-a1x")
    assert pg.evaluate("_ALTO_OUTLINE.parent['unit-1-a1x']") == "unit-1-a1"
    assert not errs, errs


@needs_solar
def test_a_card_cannot_be_added_or_moved_past_the_satellites_but_can_elsewhere(browser, edit_url):
    pg, errs = _editing(browser, edit_url, hook=True)
    sat = "unit-1-a1x"
    pg.evaluate(f"document.getElementById('node-{sat}').scrollIntoView({{block:'center'}})")
    pg.wait_for_timeout(250)
    _ctl(pg, sat, "addc")
    assert "sun, planet, moon, satellite" in _toast(pg) and not [k for k in _edit_ops(pg) if k.startswith("nn|")]
    def move(card, under):
        pg.evaluate(f"document.getElementById('node-{card}').scrollIntoView({{block:'center'}})")
        pg.wait_for_timeout(200)
        _ctl(pg, card, "linkc")
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
    _ctl(pg, "unit-1-b", "linkc")
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
    _ctl(pg, "unit-1-b", "linkc")
    pg.evaluate("document.querySelector('#node-unit-1-a .node-card').click()")
    pg.wait_for_timeout(900)
    assert "rp|unit-1-b" in _edit_ops(pg)
    assert pg.evaluate("document.documentElement.classList.contains('alto-solar-stale')")
    assert not errs, errs
