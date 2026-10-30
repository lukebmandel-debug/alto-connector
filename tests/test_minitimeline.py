"""Mini horizontal timelines inside a detail page (a Section.tree with layout "timeline",
alto/build/subtree.py): the brief, the build, folding manual edits, and a real browser."""
import copy
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.manual_edit import jhash  # noqa: E402
from alto.build.subtree import check_tree, _compact  # noqa: E402
from alto.edits import fold, tree_list  # noqa: E402
from tests.test_lanes_flags import FAKE, browser  # noqa: E402,F401  (the browser fixture)
from tests.test_manual_edit import Store, _build as _build_store, _node, _view  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"
SHOTS = os.environ.get("ALTO_SHOTS")          # a folder: the browser tests also leave screenshots there

TL = {"label": "Road to the Charter", "layout": "timeline", "nodes": [
    {"id": "john", "title": "John crowned", "when": "1199", "text": "Succeeds Richard.", "tag": "Crown"},
    {"id": "normandy", "title": "Normandy lost", "when": "1204", "text": "Philip II takes the duchy."},
    {"id": "interdict", "title": "Interdict", "when": "1208", "tone": "red", "link": "definiteness"},
    {"id": "bouvines", "title": "Bouvines", "when": "1214",
     "sections": [{"h": "Why it matters", "t": "Sets the barons against <em>scutage</em>."}]},
    {"id": "runnymede", "title": "Runnymede", "when": "June 1215", "tone": "green"},
    {"id": "f1", "kind": "flag", "title": "Reign of John", "when": "1199", "to": "1216"},
    {"id": "f2", "kind": "flag", "title": "Papal quarrel", "when": "1205", "to": "1213", "tone": "violet"},
    {"id": "b1", "kind": "box", "title": "Barons gather at Stamford", "when": "1215"},
]}


def _d(tl=TL, t="Follow the years."):
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    d["nodes"][0]["sections"].append({"h": "Timeline", "t": t, "tree": copy.deepcopy(tl)})
    return d


def _build(d):
    return build_timeline(*load_brief(d))


def _data(html):
    m = re.search(r'<script id="alto-dt-data">window._ALTO_DT=(.*?);</script>', html)
    return json.loads(m.group(1).replace("<\\/", "</"))


# ── the brief ────────────────────────────────────────────────────────────────

def test_a_timeline_reaches_the_page_with_dates_kinds_and_a_slot():
    html, _ = _build(_d())
    data = _data(html)
    key = "n-formation-1"
    assert list(data) == [key] and data[key]["lay"] == "timeline"
    items = {n["i"]: n for n in data[key]["n"]}
    assert [n["i"] for n in data[key]["n"]][:2] == ["john", "normandy"]          # reading order kept
    assert items["john"]["k"] == "e" and items["john"]["v"] == 1199.0 and items["john"]["w"] == "1199"
    assert items["f1"]["k"] == "f" and items["f1"]["u"] == 1216.0 and items["f1"]["z"] == "1216"
    assert items["b1"]["k"] == "b" and items["interdict"]["l"] == ["node", "definiteness"]
    assert items["runnymede"]["v"] == pytest.approx(1215 + 151 / 365, abs=0.01)
    assert f'data-adt="{key}"' in html


def test_the_words_and_dates_are_in_the_page_text_for_search():
    html, _ = _build(_d())
    slot = re.search(r'<span class="adt-slot"[^>]*hidden>(.*?)</span>', html.replace("\\u003c", "<"))
    assert slot, "no slot"
    for w in ("Normandy lost", "June 1215", "Reign of John", "Barons gather at Stamford", "Philip II"):
        assert w in html


def test_pages_without_a_timeline_are_unchanged_by_the_feature():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    html, _ = _build(d)
    assert _data(html) == {}
    assert 'class="adt-slot"' not in html.replace("\\u003c", "<").split("window._ALTO_DT=")[0]
    a, _ = _build(copy.deepcopy(d))
    assert a == html                                  # and a build is repeatable byte for byte


def test_building_never_changes_the_stored_timeline():
    d = _d()
    before = copy.deepcopy(d)
    first, _ = _build(d)
    assert d == before
    second, _ = _build(d)                              # the sanitize ran on a copy: a second build works
    assert _data(first) == _data(second)


@pytest.mark.parametrize("mut,msg", [
    (lambda t: t["nodes"][0].update(parent="x"), "no parents"),
    (lambda t: t["nodes"][0].update(kind="banner"), "kind must be"),
    (lambda t: t["nodes"][0].update(side="left"), "side must be"),
    (lambda t: t["nodes"][5].pop("when"), "stands at a date"),
    (lambda t: t["nodes"][0].update(to="1300"), "belongs to a flag"),
    (lambda t: t["nodes"][5].update(text="no"), "just its words"),
    (lambda t: t["nodes"][7].update(link="definiteness"), "just its words"),
    (lambda t: t["nodes"][1].update(id="john"), "used twice"),
    (lambda t: t["nodes"][0].update(when="x" * 81), "longer than 80"),
    (lambda t: t.update(nodes=[{"id": f"e{i}", "title": "E"} for i in range(61)]), "60-item limit"),
])
def test_bad_timelines_are_refused_with_the_reason(mut, msg):
    t = copy.deepcopy(TL)
    mut(t)
    with pytest.raises(BriefError, match=msg):
        check_tree(t, "x")


def test_when_to_kind_belong_to_a_timeline_only():
    with pytest.raises(BriefError, match="belong to a timeline"):
        check_tree({"nodes": [{"id": "q", "title": "Q", "when": "1215"}]}, "x")


def test_an_unknown_link_is_dropped_with_a_warning():
    t = copy.deepcopy(TL)
    t["nodes"][2]["link"] = "no-such-page"
    html, rep = _build(_d(t))
    assert any("no-such-page" in w for w in rep["warnings"])
    assert "l" not in {n["i"]: n for n in _data(html)["n-formation-1"]["n"]}["interdict"]


def test_markup_in_a_timeline_is_stripped():
    t = copy.deepcopy(TL)
    t["nodes"][0]["title"] = "<img src=x onerror=alert(1)>John"
    t["nodes"][0]["when"] = "<b>1199</b>"
    html, _ = _build(_d(t))
    n = {n["i"]: n for n in _data(html)["n-formation-1"]["n"]}["john"]
    assert "<" not in n["t"] and "<" not in n["w"]


def test_a_section_cannot_carry_a_timeline_and_cards():
    d = _d()
    d["nodes"][0]["sections"][-1]["cards"] = {"cards": [{"front": "a", "back": "b"}]}
    with pytest.raises(BriefError, match="one of"):
        _build(d)


def test_the_mcp_tools_document_the_timeline():
    from alto import mcp_server
    assert 'layout: "timeline"' in (mcp_server.add_nodes.__doc__ or "") or 'layout: "timeline"' in Path(mcp_server.__file__).read_text(encoding="utf-8")
    assert "Mini timelines inside a page" in (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")


# ── manual edit: folded into the draft ───────────────────────────────────────

def _dj(lst):
    return jhash(json.dumps(lst, ensure_ascii=False, separators=(",", ":")))


def test_events_added_moved_and_edited_fold_back_into_the_timeline():
    st = Store(_d())
    lst = tree_list(_view(st).owner("n", "formation").sections[1])
    assert lst and lst[0]["k"] == "e"
    new = copy.deepcopy(lst)
    new.insert(2, {"i": "s-new1", "k": "e", "t": "New event"})
    new[0], new[1] = new[1], new[0]                                                    # moved
    st.edits = {"v": 1, "ops": {
        "dt|n-formation-1|tree": {"b": _dj(lst), "v": new, "t": 1},
        "dt|n-formation-1|s-new1|title": {"b": "New event", "v": "King's council", "t": 2},
        "dt|n-formation-1|s-new1|when": {"b": "", "v": "1210", "t": 3},
        "dt|n-formation-1|f1|to": {"b": "1216", "v": "1216-10", "t": 4}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and r["folded"] == 4, r
    tree = _node(st, "formation")["sections"][1]["tree"]
    assert tree["layout"] == "timeline"
    ids = [n["id"] for n in tree["nodes"]]
    assert ids[:3] == ["normandy", "john", "s-new1"] and ids.count("s-new1") == 1
    nn = {n["id"]: n for n in tree["nodes"]}
    assert nn["s-new1"]["title"] == "King's council" and nn["s-new1"]["when"] == "1210"
    assert nn["f1"]["kind"] == "flag" and nn["f1"]["to"] == "1216-10" and "parent" not in nn["john"]
    html, _ = _build_store(st)
    assert "King's council" in html


def test_a_new_section_with_a_timeline_folds():
    st = Store(_d())
    sig = __import__("alto.edits", fromlist=["order_sig"]).order_sig(_view(st).owner("n", "formation"))
    cur = [str(j) for j in range(len(_node(st, "formation")["sections"]))]
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": cur + ["new-t1t2t3"], "t": 1},
        "n|formation|s|new-t1t2t3|h": {"b": "", "v": "Dates", "t": 2},
        "dt|n-formation-new-t1t2t3|tree": {"b": "new", "v": [{"i": "s-aaaa", "k": "e", "t": "First event"},
                                                              {"i": "s-bbbb", "k": "e", "t": "Second event"}], "t": 3},
        "dt|n-formation-new-t1t2t3|s-aaaa|when": {"b": "", "v": "1800", "t": 4},
        "dt|n-formation-new-t1t2t3|s-bbbb|when": {"b": "", "v": "1850", "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    sec = _node(st, "formation")["sections"][-1]
    assert sec["tree"]["layout"] == "timeline" and [n.get("when") for n in sec["tree"]["nodes"]] == ["1800", "1850"]
    html, _ = _build_store(st)
    assert _data(html)[f"n-formation-{len(_node(st, 'formation')['sections']) - 1}"]["lay"] == "timeline"


def test_a_timeline_changed_meanwhile_is_a_conflict():
    st = Store(_d())
    lst = tree_list(_view(st).owner("n", "formation").sections[1])
    st.edits = {"v": 1, "ops": {"dt|n-formation-1|tree": {"b": "stale", "v": lst[:2], "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["dt|n-formation-1|tree"]


# ── in a real browser ────────────────────────────────────────────────────────

def _open(browser, tmp_path, width=1440, height=900, touch=False, retro=False, d=None):
    html, _ = _build(d or _d())
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    ctx = browser.new_context(viewport={"width": width, "height": height}, has_touch=touch, is_mobile=touch, device_scale_factor=2)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f.as_uri(), wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function'", timeout=30000)
    pg.wait_for_timeout(1500)
    if retro:
        from alto.build.retro import retro_asset
        pg.add_script_tag(content=retro_asset()[1])
        pg.evaluate("window._altoRetro.on()")
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_selector(".amt .amt-i", timeout=10000)
    pg.wait_for_timeout(700)
    return pg


def _shot(pg, name):
    if SHOTS:
        el = pg.query_selector(".amt")
        el.scroll_into_view_if_needed()
        pg.wait_for_timeout(300)
        el.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def test_the_band_draws_to_scale_with_flags_and_connectors(browser, tmp_path):
    pg = _open(browser, tmp_path)
    r = pg.evaluate("""(function(){
      var b = document.querySelector('.amt'), cs = [].slice.call(b.querySelectorAll('.amt-ev')), out = {};
      out.cards = cs.length; out.flags = b.querySelectorAll('.amt-flag').length; out.boxes = b.querySelectorAll('.amt-box').length;
      out.sz = [b.offsetWidth, b.offsetHeight];
      var rs = cs.map(function(c){ var r = c.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; });
      var ov = 0; for(var i = 0; i < rs.length; i++) for(var j = i + 1; j < rs.length; j++){ var a = rs[i], c = rs[j];
        if(a[0] < c[1] - 1 && c[0] < a[1] - 1 && a[2] < c[3] - 1 && c[2] < a[3] - 1) ov++; }
      out.overlaps = ov; out.paths = b.querySelectorAll('.amt-lines .amt-con').length; out.dots = b.querySelectorAll('.amt-dot').length;
      out.ticks = b.querySelectorAll('.amt-tick').length; out.era = b.querySelectorAll('.amt-era').length;
      var above = cs.filter(function(c){ return c.offsetTop < 100; }).length; out.above = above;
      return out; })()""")
    assert r["cards"] == 5 and r["flags"] == 2 and r["boxes"] == 1, r
    assert r["overlaps"] == 0 and r["paths"] == 6 and r["dots"] == 6, r
    assert r["ticks"] >= 3 and r["era"] == 2 and 0 < r["above"] < 5, r
    assert pg.errs == []
    _shot(pg, "desktop")


def test_events_open_their_own_words_and_pages(browser, tmp_path):
    pg = _open(browser, tmp_path)
    pg.click('.amt-ev[data-i="bouvines"] .adt-t')
    pg.wait_for_timeout(300)
    assert "scutage" in pg.evaluate("document.querySelector('.amt .adt-panel').innerText")
    pg.click('.amt .adt-panel .adt-btn')                                     # Close
    assert pg.evaluate("document.querySelector('.amt .adt-panel').hidden") is True
    pg.click('.amt-ev[data-i="interdict"] [data-go]')
    pg.wait_for_timeout(400)
    assert pg.evaluate("window._currentDetailId") == "definiteness"
    assert pg.errs == []


def test_arrow_keys_move_between_events_and_the_page_still_scrolls(browser, tmp_path):
    pg = _open(browser, tmp_path)
    pg.focus('.amt-ev[data-i="john"]')
    pg.keyboard.press("ArrowRight")
    assert pg.evaluate("document.activeElement.getAttribute('data-i')") == "normandy"
    pg.keyboard.press("ArrowLeft")
    assert pg.evaluate("document.activeElement.getAttribute('data-i')") == "john"
    assert pg.evaluate("getComputedStyle(document.querySelector('.amt .adt-scroll')).overflowY") == "hidden"
    assert pg.errs == []


def test_a_narrow_band_scrolls_with_a_hint_and_hide_works(browser, tmp_path):
    pg = _open(browser, tmp_path, width=1000)
    # the band is wide enough to need no scrolling at this width? force a narrow stage
    pg.evaluate("document.querySelector('.amt .adt-scroll').style.width = '420px'")
    pg.wait_for_timeout(500)
    assert pg.evaluate("(function(){ var s = document.querySelector('.amt .adt-scroll'); return s.scrollWidth > s.clientWidth; })()")
    pg.wait_for_function("document.querySelector('.amt-nav.r').classList.contains('on')")
    pg.click(".amt-nav.r")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.querySelector('.amt .adt-scroll').scrollLeft") > 50
    pg.click(".amt .adt-bar .adt-btn")
    assert pg.evaluate("document.querySelector('.amt').classList.contains('shut')")
    assert pg.errs == []


def test_on_a_phone_the_items_are_one_row_of_chips_that_open_a_popover(browser, tmp_path):
    pg = _open(browser, tmp_path, width=390, height=844, touch=True)
    r = pg.evaluate("""(function(){ var b = document.querySelector('.amt'), cs = b.querySelectorAll('.amt-chip');
      var ys = {}; [].forEach.call(cs, function(c){ ys[Math.round(c.getBoundingClientRect().top)] = 1; });
      return {chips: cs.length, rows: Object.keys(ys).length, h: b.querySelector('.amt-row').offsetHeight, cards: b.querySelectorAll('.amt-ev').length,
              page: document.documentElement.scrollWidth <= window.innerWidth + 1}; })()""")
    assert r["chips"] == 8 and r["rows"] == 1 and r["cards"] == 0 and r["h"] >= 96 and r["page"], r
    pg.tap('.amt-chip[data-i="bouvines"]')
    pg.wait_for_timeout(300)
    assert "scutage" in pg.evaluate("document.querySelector('.amt .adt-panel').innerText")
    assert pg.errs == []
    _shot(pg, "phone")


def test_retro_wears_a_black_band_with_a_gold_rim(browser, tmp_path):
    pg = _open(browser, tmp_path, retro=True)
    r = pg.evaluate("""(function(){ var b = getComputedStyle(document.querySelector('.amt')), c = getComputedStyle(document.querySelector('.amt-ev'));
      return [b.backgroundColor, b.borderTopColor, b.borderRadius, c.borderRadius, c.borderTopColor]; })()""")
    assert r[0] == "rgb(0, 0, 0)" and "217, 174, 85" in r[1] and r[2] == "0px" and r[3] == "0px" and "217, 174, 85" in r[4], r
    _shot(pg, "desktop_retro")
    assert pg.errs == []


def test_retro_on_a_phone(browser, tmp_path):
    pg = _open(browser, tmp_path, width=390, height=844, touch=True, retro=True)
    r = pg.evaluate("getComputedStyle(document.querySelector('.amt-chip')).borderRadius")
    assert r == "0px"
    _shot(pg, "phone_retro")
    assert pg.errs == []


# ── manual edit in a real browser ────────────────────────────────────────────

@pytest.fixture
def editing(browser, tmp_path):
    import functools
    import http.server
    import socketserver
    import threading
    html, _ = _build(_d())
    (tmp_path / "page.html").write_text(html, encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/page.html", wait_until="domcontentloaded")
    pg.wait_for_function("typeof showDetail === 'function'", timeout=30000)
    pg.wait_for_timeout(1500)
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_selector(".amt .amt-i", timeout=10000)
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_selector("html.alto-editing", timeout=10000)
    pg.wait_for_timeout(800)
    yield pg
    srv.shutdown()


def _ops(pg, until=None):
    """The saved edit records (the page saves a moment after a change); `until`: a key that must be there."""
    if until:
        pg.wait_for_function("k => window.__edits && window.__edits.ops && (k in window.__edits.ops)", arg=until, timeout=8000)
    pg.wait_for_timeout(300)
    return pg.evaluate("(window.__edits && window.__edits.ops) || {}")


def test_adding_moving_and_deleting_events_in_edit_mode(editing):
    pg = editing
    pg.hover('.amt-ev[data-i="normandy"]')
    pg.click('.amt-ev[data-i="normandy"] .aed-tc button[data-x="add"]')
    pg.wait_for_timeout(500)
    ids = pg.evaluate("[].map.call(document.querySelectorAll('.amt .amt-i'), function(e){ return e.getAttribute('data-i'); })")
    assert len(ids) == 9 and ids[2].startswith("s-"), ids
    pg.keyboard.type("Council at Winchester")
    pg.keyboard.press("Enter")
    ops = _ops(pg, "dt|n-formation-1|tree")
    tree = [k for k in ops if k.endswith("|tree")]
    assert tree, ops.keys()
    first = ops[tree[0]]["v"]
    assert [x["i"] for x in first].index("normandy") + 1 == next(i for i, x in enumerate(first) if x["i"].startswith("s-"))
    # move it earlier with ←, then take it away with ✕
    new_id = next(x["i"] for x in first if x["i"].startswith("s-"))
    pg.hover(f'.amt-ev[data-i="{new_id}"]')
    pg.click(f'.amt-ev[data-i="{new_id}"] .aed-tc button[data-x="up"]')
    pg.wait_for_timeout(900)
    order = [x["i"] for x in _ops(pg)[tree[0]]["v"]]
    assert order.index(new_id) < order.index("normandy")
    pg.hover(f'.amt-ev[data-i="{new_id}"]')
    pg.click(f'.amt-ev[data-i="{new_id}"] .aed-tc button[data-x="del"]')
    pg.wait_for_timeout(900)
    assert new_id not in [x["i"] for x in _ops(pg)[tree[0]]["v"]]
    assert pg.errs == []


def test_a_date_edited_in_place_moves_the_event_and_adds_a_flag(editing):
    pg = editing
    pg.click('.amt-ev[data-i="normandy"] .amt-when')
    pg.keyboard.press("Meta+a")
    pg.keyboard.type("1212")
    pg.keyboard.press("Enter")
    assert _ops(pg, "dt|n-formation-1|normandy|when")["dt|n-formation-1|normandy|when"]["v"] == "1212"
    pg.hover('.amt-ev[data-i="bouvines"]')
    pg.click('.amt-ev[data-i="bouvines"] .aed-tc button[data-x="addf"]')
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelectorAll('.amt-flag').length") == 3
    assert pg.errs == []


def test_a_new_mini_timeline_section_can_be_added(editing):
    pg = editing
    pg.click(".aed-add")
    pg.click('#aed-kinds button[data-k="timeline"]')
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.querySelectorAll('#detail-content .amt').length") == 2
    ops = _ops(pg)
    assert any(re.match(r"dt\|n-formation-new-[a-z0-9]+\|tree$", k) for k in ops)
    assert pg.errs == []
