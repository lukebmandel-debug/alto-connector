"""Study plan, the cross-piece tests (item 18; spec ORG/notes-tl-studyplan-spec.md).

The builders write their own unit tests (plan_check, the tool, the renderer). These tests join the pieces, PUBLIC code only:
  1. flag-off: a brief with no study_plan builds a page with nothing of the plan in it (outline, lanes, System);
  2. the record: a built page carries the plan and the right per-node class (sp-today / sp-soon / sp-late / sp-done) on a
     fixed local date, on an outline card, a lanes card and a System disc;
  3. the tool round trip: set_study_plan then the built page shows it; a bad node, bad date, duplicate or 201-character why is
     refused and nothing is saved; a closed entitlement refuses the same way with zero change;
  4. print takes the rings off.
Tests that need the builders' code carry an xfail that LIFTS BY ITSELF as soon as the module/tool exists (strict=False), so a
real failure shows red the day the code lands. Chromium only, silent, no network, no cloud env."""
import copy
import functools
import http.server
import importlib.util
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto import mcp_server as srv  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402
from test_lanes_fit import _doc as lanes_doc  # noqa: E402
from test_solar_draw import SMALL, SMALL_LINKS, solar_doc  # noqa: E402

TODAY = "2026-11-10"                      # the page's "today" in the browser tests (local noon)
SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))
OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))

HAS_RENDER = importlib.util.find_spec("alto.build.study_plan") is not None
HAS_CHECK = importlib.util.find_spec("alto.build.plan_check") is not None
HAS_TOOL = hasattr(srv, "set_study_plan")
needs_render = pytest.mark.xfail(not HAS_RENDER, strict=False, reason="alto/build/study_plan.py (bench-tl-3's render) has not landed")
needs_tool = pytest.mark.xfail(not HAS_TOOL, strict=False, reason="the set_study_plan tool (bench-tl-2) has not landed")
needs_both = pytest.mark.xfail(not (HAS_RENDER and HAS_TOOL), strict=False, reason="needs the tool and the render heads")

MARKERS = ("sp-today", "sp-soon", "sp-late", "sp-done", "study_plan", "study-plan", "STUDY_PLAN")


# ── the three formats ──────────────────────────────────────────────────────────

FORMATS = {
    "outline": lambda: copy.deepcopy(OUTLINE),
    "lanes": lambda: copy.deepcopy(lanes_doc()),
    "system": lambda: copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS)),
}


def _page(doc):
    return build_timeline(*load_brief(copy.deepcopy(doc)))[0]


def _ids(doc, n=6):
    return [x["id"] for x in doc["nodes"]][:n]


def _plan(ids, why="Marked Still learning on the cards you flagged."):
    """today / soon / late / done / later, on the fixed date."""
    a, b, c, d, e = ids[:5]
    return {"v": 1, "exam_date": "2026-11-20", "days_per_week": 5, "minutes_per_day": 45, "items": [
        {"node": a, "day": TODAY, "why": why, "signal": "marks"},
        {"node": b, "day": "2026-11-12", "why": "Missed two quiz questions on it.", "signal": "quiz"},
        {"node": c, "day": "2026-11-08", "why": "You said you are weak on it.", "signal": "told"},
        {"node": d, "day": "2026-11-08", "why": "The exam outline stresses it.", "signal": "exam"},
        {"node": e, "day": "2026-11-20", "why": "Syllabus week 3.", "signal": "syllabus"},
    ]}


# ── 1. flag off: nothing of the plan on a page without one ───────────────────────

@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_page_without_a_plan_carries_nothing_of_it(fmt):
    doc = FORMATS[fmt]()
    assert "study_plan" not in doc["brief"]
    a, b = _page(doc), _page(doc)
    assert a == b, "the build is not deterministic, so byte-identity cannot be checked"
    for m in MARKERS:
        assert m not in a, f"{fmt}: a page with no plan carries {m!r}"


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_the_plan_code_is_not_in_the_page_unless_a_plan_is_set(fmt):
    """The page without a plan is the same bytes with or without the plan module on disk: building with the key absent twice
    around a build WITH a plan (which may import/cache the module) gives identical bytes."""
    doc = FORMATS[fmt]()
    before = _page(doc)
    withp = copy.deepcopy(doc)
    withp["brief"]["study_plan"] = _plan(_ids(doc))
    try:
        _page(withp)
    except Exception:             # the loader may refuse the key until the builders land; irrelevant to the flag-off rule
        pass
    assert _page(doc) == before


# ── helpers for the browser ────────────────────────────────────────────────────

FIXED_DATE = """(function(){ var RD = Date, T = new RD('%sT12:00:00').getTime();
  function FD(){ var a = arguments; return a.length ? new (Function.prototype.bind.apply(RD, [null].concat([].slice.call(a))))() : new RD(T); }
  FD.prototype = RD.prototype; FD.now = function(){ return T; }; FD.parse = RD.parse; FD.UTC = RD.UTC; window.Date = FD; })();""" % TODAY

FAKE_CLOUD = """(function(){ var store = null;
 var C = {enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store = JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window, 'AltoCloud', {get:function(){ return C; }, set:function(){}, configurable:true}); })();"""

NODE = "(id) => document.querySelector('#node-' + CSS.escape(id) + ', [data-id=\"' + id + '\"]')"
CLASSES = """(id) => { var e = document.querySelector('#node-' + CSS.escape(id)) || document.querySelector('[data-id="' + id + '"]');
  return e ? Array.prototype.filter.call(e.classList, function(c){ return /^sp-/.test(c); }).sort() : null; }"""
RING = """(id) => { var e = document.querySelector('#node-' + CSS.escape(id)) || document.querySelector('[data-id="' + id + '"]');
  if(!e) return null; var out = [], els = [e].concat([].slice.call(e.querySelectorAll('*')).slice(0, 8));
  els.forEach(function(x){ var s = getComputedStyle(x); out.push([s.outlineStyle, s.outlineWidth, s.boxShadow, s.filter, s.strokeWidth, s.stroke].join('|')); });
  return out.join('~'); }"""


@pytest.fixture(scope="module")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                                       # noqa: BLE001
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


def _open(browser, tmp_path, html, media=None):
    (tmp_path / "page.html").write_text(html, encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv_ = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv_.serve_forever, daemon=True).start()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    ctx.add_init_script(FIXED_DATE)
    ctx.add_init_script(FAKE_CLOUD)
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{srv_.server_address[1]}/page.html")
    pg.wait_for_timeout(2800)
    pg._srv = srv_
    return pg


def _close(pg):
    pg.context.close()
    pg._srv.shutdown()


# ── 2. the record: the page carries it, the right class lands on the right node ──────────

@needs_render
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_the_page_carries_the_plan_and_marks_each_node_by_its_day(fmt, browser, tmp_path):
    doc = FORMATS[fmt]()
    ids = _ids(doc)
    doc["brief"]["study_plan"] = _plan(ids)
    html = _page(doc)
    assert "Marked Still learning on the cards you flagged." in html          # the record rides in the page
    pg = _open(browser, tmp_path, html)
    try:
        a, b, c, d, e = ids[:5]
        assert pg.evaluate(CLASSES, a) == ["sp-today"], fmt
        assert pg.evaluate(CLASSES, b) == ["sp-soon"], fmt
        assert pg.evaluate(CLASSES, c) == ["sp-late"], fmt
        assert "sp-today" not in pg.evaluate(CLASSES, e) and "sp-late" not in pg.evaluate(CLASSES, e), fmt      # later than the next 3 days
        # a node the plan does not name wears nothing
        other = [i for i in _ids(doc, 12) if i not in ids[:5]][0]
        assert pg.evaluate(CLASSES, other) in ([], None), fmt
        assert pg.errs == []
    finally:
        _close(pg)


@needs_render
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_a_node_done_by_the_reader_shows_the_tick_not_the_late_ring(fmt, browser, tmp_path):
    """Progress is the READER's state (spec: plan_done {"<node>|<day>": true} in the existing study state, next to the card marks)."""
    doc = FORMATS[fmt]()
    ids = _ids(doc)
    doc["brief"]["study_plan"] = _plan(ids)
    pg = _open(browser, tmp_path, _page(doc))
    try:
        d = ids[3]
        assert pg.evaluate(CLASSES, d) == ["sp-late"]                              # past due and not done
        key = pg.evaluate("Object.keys(localStorage).filter(function(k){ return /-st$/.test(k); })[0] || null")
        assert key, "no study state key found (the '-st' key next to the card marks)"
        state = json.loads(pg.evaluate("k => localStorage.getItem(k)", key) or "{}")
        state.setdefault("plan_done", {})[f"{d}|2026-11-08"] = True
        pg.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, json.dumps(state)])
        pg.reload()
        pg.wait_for_timeout(2500)
        assert pg.evaluate(CLASSES, d) == ["sp-done"]
        assert pg.errs == []
    finally:
        _close(pg)


# ── 4. print takes the rings off ───────────────────────────────────────────────────────

@needs_render
@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_print_removes_the_rings(fmt, browser, tmp_path):
    doc = FORMATS[fmt]()
    ids = _ids(doc)
    doc["brief"]["study_plan"] = _plan(ids)
    pg = _open(browser, tmp_path, _page(doc))
    try:
        a = ids[0]
        other = [i for i in _ids(doc, 12) if i not in ids[:5]][0]
        screen = pg.evaluate(RING, a)
        assert screen != pg.evaluate(RING, other), "a node due today wears a ring on screen"
        pg.emulate_media(media="print")
        pg.wait_for_timeout(300)
        assert pg.evaluate(RING, a) == pg.evaluate(RING, other), "in print the ring is gone (ink)"
    finally:
        _close(pg)


# ── 3. the tool round trip ─────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_store(tmp_path):
    srv.set_store(LocalStore(tmp_path))
    yield tmp_path
    srv.set_store(None)


def _built_draft():
    pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
    tid = srv.create_timeline(pid, SAMPLE["brief"])["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "notes", "kind": "notes"}], True)
    srv.add_nodes(tid, SAMPLE["nodes"])
    srv.add_connections(tid, SAMPLE["connections"])
    assert srv.build_timeline(tid).get("verify") == "passed"
    return tid


def _stored(tid):
    st = srv.get_store()
    return json.dumps(st.get_timeline(srv.uid(), tid), sort_keys=True, default=str)


def _node_ids():
    return [n["id"] for n in SAMPLE["nodes"]]


def _items(ids):
    return [{"node": ids[0], "day": TODAY, "why": "Marked Still learning on the cards you flagged.", "signal": "marks"},
            {"node": ids[1], "day": "2026-11-12", "why": "Missed two quiz questions on it.", "signal": "quiz"}]


@needs_tool
def test_set_study_plan_then_the_built_page_shows_it(fresh_store):
    tid = _built_draft()
    ids = _node_ids()
    r = srv.set_study_plan(tid, _items(ids), exam_date="2026-11-20", days_per_week=5, minutes_per_day=45)
    assert not r.get("error"), r
    assert srv.build_timeline(tid).get("verify") == "passed"
    html = srv.get_store().get_artifact(srv.uid(), tid, "timeline.html")
    html = html.decode("utf-8") if isinstance(html, bytes) else html
    assert "Marked Still learning on the cards you flagged." in html and "Missed two quiz questions on it." in html
    # replace=True (the default) swaps the plan, it does not stack a second one
    r = srv.set_study_plan(tid, _items(ids)[:1], exam_date="2026-11-20")
    assert not r.get("error"), r
    assert srv.build_timeline(tid).get("verify") == "passed"
    html = srv.get_store().get_artifact(srv.uid(), tid, "timeline.html")
    html = html.decode("utf-8") if isinstance(html, bytes) else html
    assert "Missed two quiz questions on it." not in html


def _bad_cases(ids):
    good = _items(ids)
    return {
        "bad node id": [{**good[0], "node": "no-such-node"}],
        "bad date": [{**good[0], "day": "2026-13-45"}],
        "date not a date": [{**good[0], "day": "next tuesday"}],
        "duplicate": [good[0], dict(good[0])],
        "201-character why": [{**good[0], "why": "x" * 201}],
        "empty why": [{**good[0], "why": ""}],
        "markup in why": [{**good[0], "why": "<script>alert(1)</script>"}],
        "unknown signal": [{**good[0], "signal": "vibes"}],
    }


@needs_tool
@pytest.mark.parametrize("case", sorted(_bad_cases(["a", "b"])))
def test_a_bad_plan_is_refused_and_nothing_is_saved(fresh_store, case):
    tid = _built_draft()
    ids = _node_ids()
    before = _stored(tid)
    r = srv.set_study_plan(tid, _bad_cases(ids)[case], exam_date="2026-11-20")
    assert r.get("error"), f"{case}: the tool accepted it: {r}"
    assert _stored(tid) == before, f"{case}: something was saved although it was refused"


@needs_tool
def test_a_plan_with_a_good_item_and_a_bad_one_saves_neither(fresh_store):
    tid = _built_draft()
    ids = _node_ids()
    before = _stored(tid)
    r = srv.set_study_plan(tid, _items(ids) + [{"node": "ghost", "day": TODAY, "why": "x", "signal": "told"}])
    assert r.get("error")
    assert _stored(tid) == before


@needs_tool
def test_too_many_items_or_too_far_ahead_is_refused(fresh_store):
    tid = _built_draft()
    ids = _node_ids()
    before = _stored(tid)
    many = [{"node": ids[i % len(ids)], "day": f"2026-12-{1 + i // len(ids):02d}", "why": "w", "signal": "told"} for i in range(121)]
    assert srv.set_study_plan(tid, many).get("error")
    assert srv.set_study_plan(tid, [{**_items(ids)[0], "day": "2030-01-01"}]).get("error")      # more than 366 days ahead
    assert _stored(tid) == before


@needs_tool
def test_a_closed_entitlement_refuses_the_same_way_with_zero_change(fresh_store, monkeypatch):
    if importlib.util.find_spec("alto.entitlements") is None:
        pytest.xfail("alto/entitlements.py (the study_plan FEATURE row) has not landed")
    import alto.entitlements as ent
    tid = _built_draft()
    before = _stored(tid)
    real = ent.allowed
    monkeypatch.setattr(ent, "allowed", lambda account, feature, *a, **k: False if feature == "study_plan" else real(account, feature, *a, **k))
    r = srv.set_study_plan(tid, _items(_node_ids()), exam_date="2026-11-20")
    assert r.get("error"), r
    assert _stored(tid) == before
    # and it is the same refusal wording whichever way it is closed (no leaking whether the plan itself was valid)
    r2 = srv.set_study_plan(tid, [{"node": "ghost", "day": "nope", "why": "", "signal": "x"}])
    assert r2.get("error") == r.get("error")


@needs_both
def test_a_plan_set_by_the_tool_is_marked_on_the_page_in_the_browser(fresh_store, browser, tmp_path_factory):
    tid = _built_draft()
    ids = _node_ids()
    assert not srv.set_study_plan(tid, _items(ids), exam_date="2026-11-20").get("error")
    assert srv.build_timeline(tid).get("verify") == "passed"
    html = srv.get_store().get_artifact(srv.uid(), tid, "timeline.html")
    html = html.decode("utf-8") if isinstance(html, bytes) else html
    pg = _open(browser, tmp_path_factory.mktemp("sp"), html)
    try:
        assert pg.evaluate(CLASSES, ids[0]) == ["sp-today"]
        assert pg.evaluate(CLASSES, ids[1]) == ["sp-soon"]
        assert pg.errs == []
    finally:
        _close(pg)
