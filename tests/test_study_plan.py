"""The study plan on the page (alto/build/study_plan.py): flag off = byte-identical, what a plan draws by the reader's date on every format
(card, System disc, lanes), the sheet and the ticks, nothing on a phone. Browser parts are skipped without Playwright."""
import functools
import http.server
import json
import re
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import study_plan as sp   # noqa: E402
from alto.build.builder import build_timeline, load_brief   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _build(name, plan=None, **over):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"].update(over)
    if plan is not None:
        d["brief"]["study_plan"] = plan
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


def _items(*rows, ids=("formation", "offer", "acceptance", "revocation", "definiteness")):
    out = [dict(node=n, day=d, why=w, signal="marks") for n, (d, w) in zip(ids, rows)]
    return {"v": 1, "exam_date": "2026-12-01", "items": out}


PLAN = _items(("2026-11-05", "you marked 4 cards Still learning"), ("2026-11-07", "quiz: 2 of 5"), ("2026-11-02", "missed it Monday"),
              ("2026-11-20", "exam stresses it"), ("2026-11-05", "told: weak on this"))


# ── the flag ───────────────────────────────────────────────────────────

def test_a_page_without_a_plan_is_byte_identical():
    base = _build("outline")
    assert _build("outline", plan={}) == base
    assert _build("outline", plan={"v": 1, "items": []}) == base
    assert _build("outline", plan={"v": 1, "items": [dict(node="not-a-node", day="2026-11-05", why="x", signal="marks")]}) == base
    assert "alto-sp" not in base and "_ALTO_SP" not in base


def test_a_plan_adds_only_its_own_block():
    page = _build("outline", plan=PLAN)
    assert page.count('id="alto-sp-data"') == 1 and page.count('id="alto-sp"') == 1 and page.count('id="alto-sp-css"') == 1
    assert "alto-hl-" in re.search(r"var KEY = '([^']*)-st'", page).group(0)
    assert "onload" not in sp.JS and "filter:" not in sp.CSS


def test_clean_keeps_only_what_can_be_drawn():
    ids = ["a", "b"]
    plan = {"v": 1, "exam_date": "nope", "items": [
        dict(node="a", day="2026-11-05", why="<b>x</b> y", signal="quiz"), dict(node="a", day="2026-11-05", why="dup", signal="quiz"),
        dict(node="c", day="2026-11-05", why="no such node"), dict(node="b", day="2026-13-45", why="bad day"), dict(node="b", day="2026-11-06", why=""),
        dict(node="b", day="2026-11-06", why="w" * 500, signal="made-up")]}
    got = sp.clean(plan, ids)
    assert got["exam"] == "" and [(i["node"], i["day"]) for i in got["items"]] == [("a", "2026-11-05"), ("b", "2026-11-06")]
    assert got["items"][0]["why"] == "x y" and len(got["items"][1]["why"]) == 200 and got["items"][1]["signal"] == ""
    assert sp.clean(None, ids) == {} and sp.clean({"items": "x"}, ids) == {}
    assert len(sp.clean({"items": [dict(node="a", day="2026-11-%02d" % (i % 28 + 1), why="w") for i in range(400)]}, ids)["items"]) <= 56


# ── in a browser ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("splan")
    (d / "o.html").write_text(_build("outline", plan=PLAN), encoding="utf-8")
    (d / "s.html").write_text(_build("outline", plan=PLAN, layout="solar"), encoding="utf-8")
    lanes = _items(("2026-11-05", "told"), ("2026-11-07", "quiz"), ids=("storm-1810", "arrive"))
    (d / "l.html").write_text(_build("lanes", plan=lanes), encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


NOW = "window._altoSpNow='2026-11-05T10:00:00';"
CLASSES = """()=>{const o={};document.querySelectorAll('.node[class*="sp-"]').forEach(n=>{const t=n.querySelector('.sp-tag');o[n.id.replace('node-','')]=[[...n.classList].filter(c=>/^sp-(today|soon|late|done)$/.test(c)).join(),t?t.textContent:'']});return o}"""


def _open(browser, url, w=1440, h=900, mobile=False, init=NOW):
    ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(init)
    pg.goto(url)
    pg.wait_for_timeout(1200)
    return ctx, pg, errs


@pytest.mark.parametrize("page", ["o.html", "s.html"])
def test_a_planned_node_wears_one_class_by_the_readers_date(browser, site, page):
    ctx, pg, errs = _open(browser, site + "/" + page)
    got = pg.evaluate(CLASSES)
    assert got["formation"][0] == "sp-today" and got["formation"][1] == "Today"
    assert got["offer"][0] == "sp-soon" and got["offer"][1].startswith("Sat Nov 7") or got["offer"][1] == "Sat Nov 7"
    assert got["acceptance"][0] == "sp-late" and got["acceptance"][1].startswith("Late")
    assert "revocation" not in got                                        # a week and more away: no ring yet
    assert got["definiteness"][0] == "sp-today"
    ring = pg.evaluate("getComputedStyle(document.querySelector('#node-formation > .node-card')).outlineStyle")
    assert ring == "solid"
    pg.evaluate("document.documentElement.classList.toggle('dark')")
    assert pg.evaluate("getComputedStyle(document.querySelector('#node-formation > .node-card')).outlineStyle") == "solid"
    assert not errs, errs
    ctx.close()


def test_lanes_draw_the_same_classes(browser, site):
    ctx, pg, errs = _open(browser, site + "/l.html")
    got = pg.evaluate(CLASSES)
    assert got["storm-1810"][0] == "sp-today" and got["arrive"][0] == "sp-soon", got
    assert not errs, errs
    ctx.close()


def test_the_date_moving_on_changes_the_rings_and_a_tick_is_the_readers_own(browser, site):
    ctx, pg, errs = _open(browser, site + "/o.html")
    pg.evaluate("toggleNotes()")                                          # (the row sits in the notes panel)
    pg.wait_for_timeout(500)
    pg.click("#sp-row")
    pg.wait_for_timeout(200)
    assert pg.evaluate("document.getElementById('sp-sheet').classList.contains('open')")
    text = pg.evaluate("document.getElementById('sp-sheet').innerText")
    text = text.lower()                                                    # (the group names are set in capitals)
    assert "late" in text and "today" in text and "this week" in text and "you marked 4 cards still learning" in text and "exam" in text
    pg.evaluate("document.querySelector('#sp-sheet .sp-it input').click()")          # tick the first (the late one)
    pg.wait_for_timeout(200)
    st = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>/-st$/.test(k))))")
    assert list(st["s"]["__plan__"]["k"].values())[0][0] == 1 and st["v"] == 1
    got = pg.evaluate(CLASSES)
    assert got["acceptance"][0] == "sp-done" and got["acceptance"][1] == "✓"
    pg.reload()
    pg.wait_for_timeout(800)
    assert pg.evaluate(CLASSES)["acceptance"][0] == "sp-done"                          # kept
    pg.evaluate("window._altoSpNow='2026-11-06T09:00:00'; window._altoStudyPlan.paint()")
    got = pg.evaluate(CLASSES)
    assert got["formation"][0] == "sp-late" and got["offer"][0] == "sp-soon" and "revocation" not in got          # (the 20th is still two weeks off)
    assert not errs, errs
    ctx.close()


def test_go_to_node_and_make_my_plan(browser, site):
    ctx, pg, errs = _open(browser, site + "/o.html")
    pg.evaluate("toggleNotes()")
    pg.wait_for_timeout(500)
    pg.click("#sp-row")
    pg.click("#sp-sheet .sp-go >> nth=0")
    assert pg.evaluate("document.querySelector('.node.sp-go') !== null")
    pg.click("#sp-sheet .sp-mk")
    assert "set_study_plan" in pg.evaluate("document.querySelector('#sp-sheet textarea').value")
    pg.evaluate("window._altoStudyPlanRoutes={open:function(){window.__routed=1}}")
    pg.click("#sp-sheet .sp-mk")
    assert pg.evaluate("window.__routed") == 1
    assert not errs, errs
    ctx.close()


def test_a_phone_draws_nothing_and_print_removes_the_rings(browser, site):
    ctx, pg, errs = _open(browser, site + "/o.html", w=390, h=844, mobile=True)
    assert pg.evaluate(CLASSES) == {}
    assert pg.evaluate("document.querySelector('.sp-tag')") is None
    assert pg.evaluate("getComputedStyle(document.getElementById('sp-row')).display") == "none"
    assert not errs, errs
    ctx.close()
    ctx, pg, errs = _open(browser, site + "/o.html")
    pg.emulate_media(media="print")
    assert pg.evaluate("getComputedStyle(document.querySelector('#node-formation > .node-card')).outlineStyle") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('.sp-tag')).display") == "none"
    ctx.close()
