"""Box tags on the horizontal timeline (brief.box_tags, lanes.py): plain dashed labelled boxes on the
board that are not nodes — no detail page, no step, no click-through. Set in the brief (set_lines /
create_timeline) and in manual edit mode (bx| ops)."""
import copy
import re

import pytest

from alto.build.brief import BriefError, validate_brief, validate_nodes
from alto.build.builder import build_timeline, load_brief
from alto.build.lanes import LANES_CSS, LANES_JS, norm_box, tidy
from tests.test_lanes import _payload, _rebuilds, _store, _v2
from tests.test_lanes_flags import FAKE, browser  # noqa: F401  (the browser fixture)

BOXES = [{"id": "siege", "label": "The siege begins", "on": "axis", "at": "1890-09"},
         {"id": "quiet", "label": "Years of silence", "on": "main", "at": "1891-01", "glyph": "clock"},
         {"id": "ada", "label": "Ada keeps the log", "on": "ada", "node": "logbooks", "side": "below"}]


def _with(boxes):
    d = _v2()
    d["brief"]["box_tags"] = copy.deepcopy(boxes)
    return d


def _check(d):
    b, nodes, _ = load_brief(copy.deepcopy(d))
    return validate_brief(b) + validate_nodes(b, nodes)


def _glyph():
    from alto.build.glyphs import LIBRARY
    return LIBRARY[0]["n"]


def _boxes():
    return [dict(b, glyph=_glyph()) if b.get("glyph") else b for b in BOXES]


# ── the brief ────────────────────────────────────────────────────────────────

def test_box_tags_validate_and_reach_the_page_data():
    L = _payload(_with(_boxes()))
    bt = {t["id"]: t for t in L["bt"]}
    assert bt["siege"]["on"] == "axis" and bt["siege"]["t"] == pytest.approx(1890 + 243 / 365)
    assert bt["quiet"]["svg"].startswith("<svg") and bt["quiet"]["on"] == "main"
    assert bt["ada"]["node"] == "logbooks" and bt["ada"]["side"] == "below" and bt["ada"]["t"] is None
    assert _payload(_v2())["bt"] == []
    assert _check(_with(_boxes())) is not None


@pytest.mark.parametrize("boxes,msg", [
    ([{"id": "x", "label": "No place"}], "place it"),
    ([{"id": "x", "label": "L", "at": "someday"}], "names no date or number"),
    ([{"id": "x", "label": "L", "at": "1890", "on": "nobody"}], "is not 'axis', 'main' or one of the brief's lines"),
    ([{"id": "x", "label": "L", "node": "nowhere"}], "not one of the events"),
    ([{"id": "x", "label": "L", "at": "1890", "glyph": "no-such"}], "glyph library"),
    ([{"id": "x", "label": "L", "at": "1890", "side": "left"}], "side must be"),
    ([{"id": "x", "label": "L", "at": "1890", "to": "1891"}], "unknown keys"),
    ([{"id": "x", "label": "", "at": "1890"}], "needs a label"),
    ([{"id": "X!", "label": "L", "at": "1890"}], "short lowercase slug"),
    ([{"id": "x", "label": "A", "at": "1890"}, {"id": "x", "label": "B", "at": "1891"}], "used twice"),
    ([{"id": "x", "label": "L" * 61, "at": "1890"}], "longer than 60"),
])
def test_bad_box_tags_are_refused_with_the_reason(boxes, msg):
    with pytest.raises(BriefError, match=msg):
        _check(_with(boxes))


def test_box_tags_need_the_horizontal_timeline():
    d = _with(BOXES[:1])
    d["brief"]["mode"] = "linear"
    d["brief"]["lines"], d["brief"]["flashbacks"] = [], []
    for n in d["nodes"]:
        for k in ("line", "when", "present", "flash", "gap"):
            n.pop(k, None)
    with pytest.raises(BriefError, match="box_tags need mode 'lanes'"):
        _check(d)


def test_norm_box_and_tidy():
    assert norm_box({"id": "a", "label": " Hi ", "at": 1890})["at"] == "1890"
    d = _with([{"id": "p", "label": "Pinned", "node": "ben-leaves"}, {"id": "q", "label": "Both", "at": "1891", "node": "ben-leaves"},
               {"id": "r", "label": "On a gone line", "on": "gone", "at": "1891"}])
    d["brief"]["box_tags"][2]["on"] = "gone"
    nodes = [n for n in d["nodes"] if n["id"] != "ben-leaves"]
    tidy(d["brief"], nodes)
    assert d["brief"]["box_tags"] == [{"id": "q", "label": "Both", "at": "1891"}, {"id": "r", "label": "On a gone line", "on": "axis", "at": "1891"}]


def test_set_lines_sets_and_clears_box_tags(tmp_path):
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    try:
        d = _v2()
        pid = srv.create_project("Stories", "a novel", "writing")["project_id"]
        tid = srv.create_timeline(pid, d["brief"])["timeline_id"]
        srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
        assert "error" not in srv.add_nodes(tid, d["nodes"])
        r = srv.set_lines(tid, d["brief"]["lines"], box_tags=_boxes())
        assert r["ok"] and r["box_tags"] == ["siege", "quiet", "ada"], r
        bad = srv.set_lines(tid, d["brief"]["lines"], box_tags=[{"id": "z", "label": "Z"}])
        assert bad["error"] == "invalid_lines" and "place it" in bad["message"]
        assert srv.set_lines(tid, d["brief"]["lines"])["box_tags"] == ["siege", "quiet", "ada"]
        assert srv.set_lines(tid, d["brief"]["lines"], box_tags=[])["box_tags"] == []
        assert "box_tags" not in srv.get_store().get_timeline(srv.uid(), tid)["brief"]
    finally:
        srv.set_store(None)


# ── manual edit mode: bx| ops fold into the brief ────────────────────────────

def _full(b):
    z = norm_box(dict(b))
    return {k: z[k] for k in ("id", "label", "glyph", "on", "at", "node", "side")}


def test_box_ops_fold_add_move_relabel_remove():
    from alto.edits import fold
    st = _store(_with(_boxes()))
    new = {"id": "fest", "label": "Festival", "glyph": "", "on": "axis", "at": "1890-07", "node": "", "side": ""}
    st.edits = {"v": 1, "ops": {
        "bx|fest": {"b": None, "v": new, "t": 1},
        "bx|siege": {"b": _full(BOXES[0]), "v": dict(_full(BOXES[0]), label="Siege", at="1890-10"), "t": 2},
        "bx|ada": {"b": _full(BOXES[2]), "v": None, "t": 3}}}
    r = fold(st, "u", "t1")
    assert not r.get("error") and not r["conflicts"], r
    bx = {b["id"]: b for b in st.doc["brief"]["box_tags"]}
    assert set(bx) == {"siege", "quiet", "fest"} and bx["siege"] == {"id": "siege", "label": "Siege", "at": "1890-10"}
    assert bx["fest"] == {"id": "fest", "label": "Festival", "at": "1890-07"}
    _rebuilds(st)


def test_a_box_changed_since_is_a_conflict_and_the_last_removal_leaves_no_list():
    from alto.edits import fold
    st = _store(_with(BOXES[:1]))
    other = dict(_full(BOXES[0]), label="Something else")
    st.edits = {"v": 1, "ops": {"bx|siege": {"b": other, "v": dict(other, label="X"), "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["bx|siege"]
    st.edits = {"v": 1, "ops": {"bx|siege": {"b": _full(BOXES[0]), "v": None, "t": 2}}}
    assert not fold(st, "u", "t1").get("error")
    assert "box_tags" not in st.doc["brief"]


def test_deleting_the_card_a_box_sits_beside_keeps_its_date_or_drops_it():
    from alto.edits import fold
    st = _store(_with([{"id": "p", "label": "Pinned", "node": "ben-leaves"}, {"id": "q", "label": "Both", "at": "1891", "node": "ben-leaves"}]))
    st.edits = {"v": 1, "ops": {"nd|ben-leaves": {"b": 1, "v": 1, "t": 1}}}
    assert not fold(st, "u", "t1").get("error")
    assert st.doc["brief"]["box_tags"] == [{"id": "q", "label": "Both", "at": "1891"}]


# ── what the page carries ────────────────────────────────────────────────────

def test_the_page_carries_the_boxes_and_their_looks():
    html, _ = build_timeline(*load_brief(_with(_boxes())))
    assert re.search(r'"bt":\[\{"id":"siege"', html)
    for s in ("lanes-box", "ln-bstub", "function boxTags", "ee-box", "bx|", "lanes-bchip"):
        assert s in html, s
    from alto.build import retro
    assert ".lanes-box" in retro.FORMAT_CSS and ".lanes-bchip" in retro.FORMAT_CSS
    css = re.sub(r"/\*.*?\*/", "", LANES_CSS, flags=re.S)
    box = css[css.index(".lanes-box{"):css.index("}", css.index(".lanes-box{"))]
    assert "dashed" in box and "box-shadow" not in box and "pointer" not in box.replace("pointer-events:auto", "")
    assert ".lanes-box:hover" not in css.replace("html.alto-editing .lanes-box:hover", "")          # no hover lift outside editing


def test_the_page_passes_the_js_gate():
    from alto.build.verify import find_node, verify_scripts
    if find_node() is None:
        pytest.skip("node not installed")
    html, _ = build_timeline(*load_brief(_with(_boxes())))
    assert verify_scripts(html, "timeline") == ([], [])


# ── in a browser ─────────────────────────────────────────────────────────────

def _open(browser, tmp_path, boxes, width=1440, height=900, cls=""):
    html, _ = build_timeline(*load_brief(_with(boxes)))
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


def test_boxes_sit_on_their_line_or_above_the_axis_and_are_not_nodes(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, _boxes())
    assert not errs, errs
    g = pg.evaluate("window._altoLanesGeo")
    bx = {b["id"]: b for b in g["boxes"]}
    assert set(bx) == {"siege", "quiet", "ada"}
    assert bx["siege"]["y"] > g["mainY"] + 200                              # above the axis, below the cards: the foot of the board
    assert abs(bx["quiet"]["y"] - g["mainY"]) < 40 and bx["quiet"]["y"] < g["mainY"]          # beside the main line, above it
    ada = next(line for line in g["lines"] if line["id"] == "ada")
    assert bx["ada"]["y"] > ada["y"] and bx["ada"]["x"] > g["x"]["logbooks"]                    # below its line, beside the event's stem
    assert bx["siege"]["x"] < bx["quiet"]["x"]                                                # in story order
    # not nodes: not in the page's cards or order, no click-through, no pointer, no step
    assert pg.evaluate("NODES.every(n => !['siege','quiet','ada'].includes(n.id))")
    assert pg.evaluate("document.querySelectorAll('.lanes-box[onclick], .lanes-box a, .lanes-box button').length") == 0
    before = pg.evaluate("[window._currentDetailType || null, window._focusedNodeId || null]")
    pg.evaluate("document.querySelector('.lanes-box').click()")
    pg.wait_for_timeout(300)
    assert pg.evaluate("[window._currentDetailType || null, window._focusedNodeId || null]") == before
    assert pg.evaluate("getComputedStyle(document.querySelector('.lanes-box')).cursor") == "default"
    assert pg.evaluate("getComputedStyle(document.querySelector('.lanes-box')).borderTopStyle") == "dashed"
    # the board still fits the window
    assert pg.evaluate("(() => { const c = document.getElementById('canvas'); return c.scrollHeight <= c.clientHeight + 2; })()")


def test_a_hidden_line_takes_its_boxes_off_the_board(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, _boxes())
    pg.evaluate("window._altoLanes && 0")
    pg.evaluate("document.querySelector('.lanes-tag[data-ln-tag=ben]').click()")          # show only Ben: Ada’s line and its boxes leave the board
    pg.wait_for_timeout(700)
    assert not errs, errs
    assert pg.evaluate("window._altoLanesGeo.boxes.map(b => b.id).sort().join()") == "quiet,siege"


def test_a_phone_width_whole_view_shrinks_the_boxes(browser, tmp_path):
    pg, errs = _open(browser, tmp_path, _boxes(), width=430, height=800, cls="phone-whole")
    assert not errs, errs
    w = pg.evaluate("[...document.querySelectorAll('.lanes-box')].map(e => [e.getBoundingClientRect().width, getComputedStyle(e).fontSize])")
    assert w and all(x[0] <= 160.5 and x[1] == "12px" for x in w), w


def test_the_phones_card_view_shows_a_box_as_a_flat_dashed_chip(browser, tmp_path):
    html, _ = build_timeline(*load_brief(_with(_boxes())))
    f = tmp_path / "t.html"
    f.write_text(html, encoding="utf-8")
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    pg = ctx.new_page()
    pg.goto(f.as_uri())
    pg.wait_for_timeout(2500)
    got = pg.evaluate("Object.fromEntries([...document.querySelectorAll('.node[id^=node-]')].map(n => [n.id.slice(5), [...n.querySelectorAll('.lanes-bchip')].map(c => c.textContent)]).filter(x => x[1].length))")
    assert got == {"quay": ["The siege begins"], "council": ["Years of silence"], "logbooks": ["Ada keeps the log"]}, got
    assert pg.evaluate("getComputedStyle(document.querySelector('.lanes-bchip')).pointerEvents") == "none"


@pytest.fixture
def editing(browser, tmp_path):
    import functools
    import http.server
    import socketserver
    import threading
    html, _ = build_timeline(*load_brief(_with(_boxes())))
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


def test_edit_mode_adds_moves_renames_and_removes_a_box(editing):
    pg, errs = editing
    pg.click("#alto-edit-exit .ee-box")
    pg.fill("#aed-form [data-f=label]", "Spring thaw")
    pg.fill("#aed-form [data-f=at]", "soon")
    pg.click("#aed-form [data-a=ok]")
    assert "not a date" in pg.inner_text("#aed-form .aed-err")
    pg.fill("#aed-form [data-f=at]", "1890-07")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(700)
    ids = pg.evaluate("window._altoLanesGeo.boxes.map(b => b.id + ':' + b.label)")
    assert len(ids) == 4 and any(s.endswith(":Spring thaw") for s in ids), ids
    new = next(s.split(":")[0] for s in ids if s.endswith(":Spring thaw"))
    pg.wait_for_timeout(700)
    assert pg.evaluate(f"window.__edits.ops['bx|{new}'].v.at") == "1890-07"
    # drag it along the axis
    sel = f".lanes-box[data-box='{new}']"
    pg.evaluate(f"document.querySelector(\"{sel}\").scrollIntoView({{inline: 'center'}})")
    pg.wait_for_timeout(300)
    x0 = pg.evaluate(f"window._altoLanesGeo.boxes.find(b => b.id === '{new}').x")
    r = pg.evaluate(f"(() => {{ const r = document.querySelector(\"{sel}\").getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()")
    pg.mouse.move(*r)
    pg.mouse.down()
    for k in range(1, 11):
        pg.mouse.move(r[0] + 30 * k, r[1])
        pg.wait_for_timeout(16)
    pg.mouse.up()
    pg.wait_for_timeout(800)
    assert pg.evaluate(f"window._altoLanesGeo.boxes.find(b => b.id === '{new}').x") > x0 + 100
    pg.wait_for_timeout(1500)                                               # the saved copy follows the page a moment later
    assert pg.evaluate(f"window.__edits.ops['bx|{new}'].v.at") > "1890-07"
    # a click: its menu; rename it; undo walks back
    pg.click(sel)
    assert "The box" in pg.inner_text("#aed-ask")
    pg.click("#aed-ask button:has-text('Rename')")
    pg.fill("#aed-name input", "Thaw")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(700)
    assert pg.evaluate(f"document.querySelector(\"{sel}\").textContent") == "Thaw"
    for _ in range(3):
        pg.click("#alto-edit-exit .ee-undo")
        pg.wait_for_timeout(500)
    assert pg.evaluate("window._altoLanesGeo.boxes.length") == 3
    pg.click("#alto-edit-exit .ee-redo")
    pg.wait_for_timeout(500)
    pg.click(sel)
    pg.click("#aed-ask button:has-text('Remove this box')")
    pg.wait_for_timeout(600)
    assert pg.evaluate("window._altoLanesGeo.boxes.length") == 3 and not errs, errs
