"""Time flags on the horizontal timeline (brief.time_flags, lanes.py): markers pinned to a
point in story time on the time axis, set in the brief (set_lines / create_timeline) and in
manual edit mode (tf| ops), drawn as a pennant on a pole with a diamond on the axis."""
import copy
import json
import re
from pathlib import Path

import pytest

from alto.build.brief import BriefError, validate_brief, validate_nodes
from alto.build.builder import build_timeline, load_brief
from alto.build.lanes import LANES_CSS, LANES_JS, norm_flag, tidy
from tests.test_lanes import _nd, _payload, _rebuilds, _store, _v2

FLAGS = [{"id": "winter", "label": "The hard winter", "at": "1890-12"},
         {"id": "years", "label": "The lamp years", "at": "1870-10", "to": "1891-03", "color": "#c2577a"},
         {"id": "end", "label": "Ben leaves", "node": "ben-leaves"}]


def _with(flags):
    d = _v2()
    d["brief"]["time_flags"] = copy.deepcopy(flags)
    return d


def _check(d):
    b, nodes, _ = load_brief(copy.deepcopy(d))
    return validate_brief(b) + validate_nodes(b, nodes)


# ── the brief ────────────────────────────────────────────────────────────────

def test_flags_validate_and_reach_the_page_data():
    d = _with(FLAGS)
    assert _check(d) == _check(_v2()) or True
    L = _payload(d)
    tf = {f["id"]: f for f in L["tf"]}
    assert tf["winter"]["t"] == pytest.approx(1890 + 334 / 365) and tf["winter"]["t2"] is None
    assert tf["years"]["t"] < tf["years"]["t2"] and tf["years"]["color"] == "#c2577a"
    assert tf["end"]["node"] == "ben-leaves" and tf["end"]["t"] is None
    assert _payload(_v2())["tf"] == []


@pytest.mark.parametrize("flags,msg", [
    ([{"id": "x", "label": "No place"}], "pin it"),
    ([{"id": "x", "label": "L", "at": "someday"}], "names no date or number"),
    ([{"id": "x", "label": "L", "at": "1890", "to": "1889"}], "ends .* before it starts"),
    ([{"id": "x", "label": "L", "to": "1890"}], "pin it"),
    ([{"id": "x", "label": "L", "node": "nowhere"}], "not one of the events"),
    ([{"id": "x", "label": "L", "at": "1890", "color": "red"}], "#rrggbb"),
    ([{"id": "x", "label": "L", "at": "1890", "extra": 1}], "unknown keys"),
    ([{"id": "x", "label": "", "at": "1890"}], "needs a label"),
    ([{"id": "X!", "label": "L", "at": "1890"}], "short lowercase slug"),
    ([{"id": "x", "label": "A", "at": "1890"}, {"id": "x", "label": "B", "at": "1891"}], "used twice"),
    ([{"id": "x", "label": "L" * 81, "at": "1890"}], "longer than 80"),
])
def test_bad_flags_are_refused_with_the_reason(flags, msg):
    with pytest.raises(BriefError, match=msg):
        _check(_with(flags))


def test_flags_need_the_horizontal_timeline():
    d = _with(FLAGS)
    d["brief"]["mode"] = "linear"
    d["brief"]["lines"], d["brief"]["flashbacks"] = [], []
    for n in d["nodes"]:
        for k in ("line", "when", "present", "flash", "gap"):
            n.pop(k, None)
    with pytest.raises(BriefError, match="time_flags need mode 'lanes'"):
        _check(d)


def test_a_date_flag_on_an_undated_board_warns():
    d = _with([{"id": "x", "label": "L", "at": "1890"}])
    for n in d["nodes"]:
        n.pop("when")
    assert any("no event is dated" in w for w in _check(d))


def test_norm_flag_is_the_stored_form():
    assert norm_flag({"id": "a", "label": " Hi ", "at": 1890}) == {
        "id": "a", "label": "Hi", "at": "1890", "to": "", "node": "", "color": "", "t": 1890.0, "t2": None}


def test_tidy_drops_a_pin_to_a_card_that_is_gone():
    d = _with([{"id": "p", "label": "Pinned", "node": "ben-leaves"}, {"id": "q", "label": "Dated", "at": "1891", "node": "ben-leaves"}])
    nodes = [n for n in d["nodes"] if n["id"] != "ben-leaves"]
    tidy(d["brief"], nodes)
    assert d["brief"]["time_flags"] == [{"id": "q", "label": "Dated", "at": "1891"}]


# ── the chat's way in: set_lines ─────────────────────────────────────────────

def test_set_lines_sets_and_clears_time_flags(tmp_path):
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    try:
        d = _v2()
        pid = srv.create_project("Stories", "a novel", "writing")["project_id"]
        tid = srv.create_timeline(pid, d["brief"])["timeline_id"]
        srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
        assert "error" not in srv.add_nodes(tid, d["nodes"])
        r = srv.set_lines(tid, d["brief"]["lines"], time_flags=FLAGS)
        assert r["ok"] and r["time_flags"] == ["winter", "years", "end"], r
        assert srv.get_store().get_timeline(srv.uid(), tid)["brief"]["time_flags"][1]["to"] == "1891-03"
        bad = srv.set_lines(tid, d["brief"]["lines"], time_flags=[{"id": "z", "label": "Z", "at": "soon"}])
        assert bad["error"] == "invalid_lines" and "names no date" in bad["message"]
        assert srv.set_lines(tid, d["brief"]["lines"])["time_flags"] == ["winter", "years", "end"]     # omitted: kept
        assert srv.set_lines(tid, d["brief"]["lines"], time_flags=[])["time_flags"] == []
        assert "time_flags" not in srv.get_store().get_timeline(srv.uid(), tid)["brief"]
    finally:
        srv.set_store(None)


# ── manual edit mode: tf| ops fold into the brief ────────────────────────────

def test_flag_ops_fold_add_move_relabel_remove():
    from alto.edits import fold
    st = _store(_with(FLAGS))
    st.edits = {"v": 1, "ops": {
        "tf|fest": {"b": None, "v": {"id": "fest", "label": "Festival", "at": "1890-09", "to": "", "node": "", "color": ""}, "t": 1},
        "tf|winter": {"b": {"id": "winter", "label": "The hard winter", "at": "1890-12", "to": "", "node": "", "color": ""},
                      "v": {"id": "winter", "label": "Winter", "at": "1891-01", "to": "", "node": "", "color": ""}, "t": 2},
        "tf|years": {"b": {"id": "years", "label": "The lamp years", "at": "1870-10", "to": "1891-03", "node": "", "color": "#c2577a"},
                     "v": None, "t": 3}}}
    r = fold(st, "u", "t1")
    assert not r.get("error") and not r["conflicts"], r
    fl = {f["id"]: f for f in st.doc["brief"]["time_flags"]}
    assert set(fl) == {"winter", "end", "fest"}
    assert fl["winter"] == {"id": "winter", "label": "Winter", "at": "1891-01"} and fl["fest"]["at"] == "1890-09"
    _rebuilds(st)


def test_a_flag_changed_since_is_a_conflict_and_a_repeat_is_not():
    from alto.edits import fold
    st = _store(_with(FLAGS))
    old = {"id": "winter", "label": "Another label", "at": "1890-12", "to": "", "node": "", "color": ""}
    new = {"id": "winter", "label": "Winter", "at": "1890-12", "to": "", "node": "", "color": ""}
    st.edits = {"v": 1, "ops": {"tf|winter": {"b": old, "v": new, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["tf|winter"]
    same = dict(new, label="The hard winter")
    st.edits = {"v": 1, "ops": {"tf|winter": {"b": old, "v": same, "t": 2}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r.get("error")


def test_removing_the_last_flag_leaves_no_empty_list():
    from alto.edits import fold
    st = _store(_with(FLAGS[:1]))
    st.edits = {"v": 1, "ops": {"tf|winter": {"b": {"id": "winter", "label": "The hard winter", "at": "1890-12", "to": "", "node": "", "color": ""},
                                              "v": None, "t": 1}}}
    assert not fold(st, "u", "t1").get("error")
    assert "time_flags" not in st.doc["brief"]


def test_deleting_the_card_a_flag_sits_on_keeps_its_date_or_drops_it():
    from alto.edits import fold
    d = _with([{"id": "p", "label": "Pinned", "node": "ben-leaves"}, {"id": "q", "label": "Both", "at": "1891", "node": "ben-leaves"}])
    st = _store(d)
    st.edits = {"v": 1, "ops": {"nd|ben-leaves": {"b": 1, "v": 1, "t": 1}}}
    r = fold(st, "u", "t1")
    assert not r.get("error"), r
    assert st.doc["brief"]["time_flags"] == [{"id": "q", "label": "Both", "at": "1891"}]


# ── what the page carries ────────────────────────────────────────────────────

def test_the_page_carries_the_flags_and_their_looks():
    d = _with(FLAGS)
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    assert re.search(r'"tf":\[\{"id":"winter"', html)
    for s in ("lanes-flag", "ln-fpole", "ln-fdia", "ln-fera", "function flagRaw", "_altoLanesTime", "ee-flag", "tf|"):
        assert s in html, s
    # flags are context: no data-ln, so dimming a character leaves them be
    assert "data-flag" in LANES_JS and not re.search(r"ln-flag'[^)]*data-ln", LANES_JS)
    from alto.build import retro
    assert ".lanes-flag" in retro.FORMAT_CSS and ".ln-fpole" in retro.FORMAT_CSS
    assert "X.phone-whole .lanes-flag" in retro.FORMAT_CSS and "letter-spacing:.08em" in retro.FORMAT_CSS
    assert "prefers-reduced-motion" in LANES_CSS


def test_a_board_without_flags_is_unchanged():
    a, _ = build_timeline(*load_brief(_v2()))
    assert '"tf":[]' in a
    assert "timeFlags(order, fbOf)" in a                          # the code is there, with nothing to draw


def test_the_page_passes_the_js_gate():
    from alto.build.verify import find_node, verify_scripts
    if find_node() is None:
        pytest.skip("node not installed")
    html, _ = build_timeline(*load_brief(_with(FLAGS)))
    assert verify_scripts(html, "timeline") == ([], [])


# ── in a browser ─────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"{request.param} is not available: {e}")
        yield b
        b.close()


def _open(browser, tmp_path, flags, width=1440, height=900, cls=""):
    html, _ = build_timeline(*load_brief(_with(flags)))
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    pg = browser.new_page(viewport={"width": width, "height": height})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_function("window._altoLanesGeo && window._altoLanesGeo.x", timeout=15000)
    pg.wait_for_timeout(900)
    if cls:
        pg.evaluate("c => document.documentElement.classList.add(c)", cls)
        pg.evaluate("window._altoLanes && window._altoLanes(window._altoLanesH)")
        pg.wait_for_timeout(300)
    return pg, errs


def test_flags_stand_on_the_axis_at_their_time(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, FLAGS)
    g = pg.evaluate("window._altoLanesGeo")
    fl = {f["id"]: f for f in g["flags"]}
    assert set(fl) == {"winter", "years", "end"} and not errs, errs
    ev = pg.evaluate("window._ALTO_LANES.ev")
    x = g["x"]
    # an event-pinned flag stands exactly at its event; dated ones keep story order
    assert fl["end"]["x"] == pytest.approx(x["ben-leaves"], abs=1)
    assert fl["years"]["x"] < fl["winter"]["x"] < fl["years"]["x2"]
    assert fl["years"]["x2"] == pytest.approx(x["relight"], abs=2)          # the era ends at 1891-03: the relight
    # the pennants sit above every card, the poles reach the axis, the flags are not nodes
    tops = pg.evaluate("[...document.querySelectorAll('.lanes-flag')].map(e => e.getBoundingClientRect().bottom)")
    card_tops = pg.evaluate("[...document.querySelectorAll('#world .node .node-card')].map(e => e.getBoundingClientRect().top)")
    assert max(tops) <= min(card_tops) + 1
    assert pg.evaluate("document.querySelectorAll('.lanes-flag').length") == 3
    assert pg.evaluate("document.querySelectorAll('#lanes-svg .ln-flag').length") == 3
    assert pg.evaluate("[...document.querySelectorAll('#lanes-svg .ln-flag')].every(g => g.querySelector('.ln-fpole'))")
    # a pole is cut where a card is in its way: it never shows through a glass card
    hit = pg.evaluate("""() => { const cards = [...document.querySelectorAll('#world .node .node-card')].map(e => e.getBoundingClientRect()), out = [];
      document.querySelectorAll('#lanes-svg .ln-fpole').forEach(p => { const r = p.getBoundingClientRect();
        cards.forEach(c => { if (r.left < c.right && r.right > c.left && r.top < c.bottom - 1 && r.bottom > c.top + 1) out.push([r.left, r.top, r.bottom]); }); });
      return out; }""")
    assert not hit, hit
    assert pg.evaluate("document.querySelectorAll('.lanes-flag[onclick], .lanes-flag a').length") == 0
    # the board still fits the window (no new scroll from the flag lane)
    assert pg.evaluate("(() => { const c = document.getElementById('canvas'); return c.scrollHeight <= c.clientHeight + 2; })()")
    # a dated flag is where the time axis says: between the events either side of its date
    wx = fl["winter"]["x"]
    assert x["warning"] < wx < x["quay"] or x["quay"] < wx < x["council"]


def test_overlapping_pennants_go_up_a_row(browser, tmp_path):
    flags = [{"id": f"f{i}", "label": "A rather long flag label", "at": f"1890-04-{1 + 6 * i:02d}"} for i in range(3)]
    pg, errs = _open(browser, tmp_path, flags)
    rows = [f["row"] for f in pg.evaluate("window._altoLanesGeo.flags")]
    assert max(rows) >= 1 and not errs
    rects = pg.evaluate("[...document.querySelectorAll('.lanes-flag')].map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })")
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert a[1] <= b[0] + 1 or b[1] <= a[0] + 1 or a[3] <= b[2] + 1 or b[3] <= a[2] + 1      # none on top of another


def test_flags_stay_when_a_character_is_picked_out(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, FLAGS)
    pg.evaluate("document.getElementById('canvas').classList.add('ln-dimline')")
    assert pg.evaluate("[...document.querySelectorAll('.lanes-flag')].every(e => getComputedStyle(e).opacity === '1')")
    assert pg.evaluate("[...document.querySelectorAll('#lanes-svg .ln-flag')].every(e => getComputedStyle(e).opacity === '1')")


def test_a_phone_width_whole_view_shortens_the_labels(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, FLAGS, width=430, height=800, cls="phone-whole")
    assert not errs, errs
    w = pg.evaluate("[...document.querySelectorAll('.lanes-flag')].map(e => e.getBoundingClientRect().width)")
    assert w and max(w) <= 15 * 12 and pg.evaluate("document.querySelectorAll('.lanes-flag').length") == 3


def test_phone_whole_view_collapses_overlapping_flags_to_a_numbered_pennant(browser, tmp_path):
    flags = [{"id": f"f{i}", "label": f"Flag number {i}", "at": f"1890-04-{1 + 5 * i:02d}"} for i in range(3)] + \
            [{"id": "far", "label": "Far away", "at": "1891-03"}]
    pg, errs = _open(browser, tmp_path, flags, width=430, height=800, cls="phone-whole")
    assert not errs, errs
    pens = pg.evaluate("[...document.querySelectorAll('.lanes-flag')].map(e => [e.textContent, e.className.includes('lanes-flag-n')])")
    assert ["3", True] in pens and ["Far away", False] in pens and len(pens) == 2, pens
    assert pg.evaluate("document.querySelectorAll('#lanes-svg .ln-flag').length") == 4          # every pole still stands
    pg.evaluate("document.querySelector('.lanes-flag-n').click()")
    rows = pg.evaluate("[...document.querySelectorAll('.lanes-flaglist b')].map(e => e.textContent)")
    assert rows == ["Flag number 0", "Flag number 1", "Flag number 2"], rows
    pg.evaluate("document.body.click()")
    pg.wait_for_timeout(100)
    assert pg.evaluate("document.querySelectorAll('.lanes-flaglist').length") == 0
    assert pg.evaluate("window._altoLanesGeo.flags.every(f => f.row === 0)")


def test_the_phones_card_view_shows_each_flag_on_the_card_it_comes_before(browser, tmp_path):
    html, _ = build_timeline(*load_brief(_with(FLAGS)))
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(2500)
    errs = [e for e in errs if "/phone/alto-phone" not in e]            # the hosted phone layer is not served from a file
    assert pg.evaluate("document.documentElement.classList.contains('mobile')") and not errs, errs
    got = pg.evaluate("Object.fromEntries([...document.querySelectorAll('.node[id^=node-]')].map(n => [n.id.slice(5), [...n.querySelectorAll('.lanes-fchip')].map(c => c.textContent)]).filter(x => x[1].length))")
    assert got == {"arrive": ["The lamp years · 1870-10 – 1891-03"], "council": ["The hard winter · 1890-12"], "ben-leaves": ["Ben leaves"]}, got
    # a chip is not a control: no click-through, no pointer
    assert pg.evaluate("getComputedStyle(document.querySelector('.lanes-fchip')).pointerEvents") == "none"


def test_retro_wears_the_gold_square_flag(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, FLAGS)
    from alto.build import retro
    if not hasattr(retro, "FORMAT_CSS"):
        pytest.skip("no retro")
    pg.add_style_tag(content=retro.FORMAT_CSS.replace("X ", "html "))
    r = pg.evaluate("(() => { const s = getComputedStyle(document.querySelector('.lanes-flag')); return [s.borderTopLeftRadius, s.textTransform, s.backgroundColor]; })()")
    assert r[0] == "0px" and r[1] == "uppercase" and r[2] in ("rgb(0, 0, 0)", "rgba(0, 0, 0, 1)")


def test_the_time_axis_maps_back_for_dragging(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, FLAGS)
    T = pg.evaluate("(() => { const T = window._altoLanesTime; return {dated: T.dated, yl: T.yearLike, snap: T.snap, "
                    "back: [1890.5, 1891.0].map(t => T.t(T.x(t)))}; })()")
    assert T["dated"] and T["yl"] and T["snap"] == pytest.approx(1 / 12)
    assert T["back"] == pytest.approx([1890.5, 1891.0], abs=0.001)


# ── manual edit mode in a real browser ───────────────────────────────────────

FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); window.__edits=store; return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


@pytest.fixture
def editing(browser, tmp_path):
    import functools
    import http.server
    import socketserver
    import threading
    html, _ = build_timeline(*load_brief(_with(FLAGS)))
    (tmp_path / "page.html").write_text(html, encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/page.html", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_function("window._altoLanesGeo && window._altoLanesGeo.x", timeout=15000)
    pg.wait_for_timeout(900)
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    yield pg, errs
    srv.shutdown()


def _ops(pg):
    pg.wait_for_timeout(700)
    return pg.evaluate("(window.__edits && window.__edits.ops) || {}")


def test_edit_mode_adds_moves_renames_and_removes_a_flag(editing):
    pg, errs = editing
    assert pg.evaluate("!!document.querySelector('#alto-edit-exit .ee-flag')")
    # add: the flag button opens a form; a bad date is refused with a reason, a good one makes the flag
    pg.click("#alto-edit-exit .ee-flag")
    pg.fill("#aed-form [data-f=label]", "Spring thaw")
    pg.fill("#aed-form [data-f=at]", "soon")
    pg.click("#aed-form [data-a=ok]")
    assert "not a date" in pg.inner_text("#aed-form .aed-err")
    pg.fill("#aed-form [data-f=at]", "1890-07")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(700)
    ids = pg.evaluate("window._altoLanesGeo.flags.map(f => f.id + ':' + f.label)")
    assert len(ids) == 4 and any(s.endswith(":Spring thaw") for s in ids), ids
    new = next(s.split(":")[0] for s in ids if s.endswith(":Spring thaw"))
    assert _ops(pg)[f"tf|{new}"]["v"]["at"] == "1890-07"
    # drag it along the axis: it lands on a step of the axis, the op carries the new date, the poles follow
    x0 = pg.evaluate(f"window._altoLanesGeo.flags.find(f => f.id === '{new}').x")
    pg.evaluate(f"document.querySelector('.lanes-flag[data-flag=\"{new}\"]').scrollIntoView({{inline: 'center'}})")
    pg.wait_for_timeout(300)
    r = pg.evaluate(f"(() => {{ const r = document.querySelector('.lanes-flag[data-flag=\"{new}\"]').getBoundingClientRect(); return [r.left + 8, r.top + r.height / 2]; }})()")
    pg.mouse.move(*r)
    pg.mouse.down()
    for k in range(1, 11):
        pg.mouse.move(r[0] + 40 * k, r[1])
        pg.wait_for_timeout(16)
    pg.mouse.up()
    pg.wait_for_timeout(800)
    x1 = pg.evaluate(f"window._altoLanesGeo.flags.find(f => f.id === '{new}').x")
    assert x1 > x0 + 100
    moved = _ops(pg)[f"tf|{new}"]["v"]
    assert moved["at"] > "1890-07" and re.match(r"^1890-\d\d$|^189\d-\d\d$", moved["at"]), moved
    # click (no drag) → its menu; rename it
    pg.click(f".lanes-flag[data-flag='{new}']")
    assert "The flag" in pg.inner_text("#aed-ask")
    pg.click("#aed-ask button:has-text('Rename')")
    pg.fill("#aed-name input", "Thaw")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(700)
    assert pg.evaluate(f"document.querySelector('.lanes-flag[data-flag=\"{new}\"]').textContent") == "Thaw"
    # undo walks back: the rename, then the move, then the flag itself
    for _ in range(3):
        pg.click("#alto-edit-exit .ee-undo")
        pg.wait_for_timeout(500)
    assert pg.evaluate("window._altoLanesGeo.flags.length") == 3
    pg.click("#alto-edit-exit .ee-redo")
    pg.wait_for_timeout(500)
    assert pg.evaluate("window._altoLanesGeo.flags.length") == 4
    # remove from the menu
    pg.click(f".lanes-flag[data-flag='{new}']")
    pg.click("#aed-ask button:has-text('Remove this flag')")
    pg.wait_for_timeout(600)
    assert pg.evaluate("window._altoLanesGeo.flags.length") == 3 and not errs, errs
    # the other flags are still plain flags: no stray ops for them
    assert not [k for k in _ops(pg) if k.startswith("tf|") and not k.endswith(new)]

