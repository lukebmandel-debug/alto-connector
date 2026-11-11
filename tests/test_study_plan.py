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

def test_a_page_without_a_plan_carries_nothing_of_the_feature():
    base = _build("outline")
    assert _build("outline", plan={}) == base
    assert _build("outline", plan={"v": 1, "items": []}) == base
    assert _build("outline", plan={"v": 1, "items": [dict(node="not-a-node", day="2026-11-05", why="x", signal="marks")]}) == base
    assert 'id="alto-sp-data"' not in base and 'id="alto-sp"' not in base and "alto-sp-css" not in base and "sp-chip" not in base
    # (Luke L-1101-222655: the study plan is offered on the homepage card and in the interview only; a plan-less page is byte-identical to before)


def test_a_plan_adds_only_its_own_block():
    page = _build("outline", plan=PLAN)
    assert page.count('id="alto-sp-data"') == 1 and page.count('id="alto-sp"') == 1 and page.count('id="alto-sp-css"') == 1
    assert len(page) - len(_build("outline")) < 40000                        # (data + the plan's style and script)
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
    (d / "n.html").write_text(_build("outline"), encoding="utf-8")
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


@pytest.fixture(scope="module")
def site_hosted(tmp_path_factory):
    """The plan page served with the hosted Retro / Holographic scripts beside it (the look lives there, not in the page)."""
    if pw is None:
        pytest.skip("Playwright is not installed")
    from alto.build import backgrounds_import as bi, holo, retro
    d = tmp_path_factory.mktemp("splanh")
    (d / "o.html").write_text(_build("outline", plan=PLAN), encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    n, t = holo.holo_asset()
    (d / "holo" / n).write_text(t, encoding="utf-8")
    n, t = retro.retro_asset()
    (d / "retro" / n).write_text(t, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")

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
    ua = {"user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"} if mobile else {}
    ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, **ua)      # (the page picks its phone design from the iPhone user agent)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(init)
    pg.goto(url)
    pg.wait_for_timeout(1200)
    return ctx, pg, errs


def test_holographic_late_is_red_on_both_grounds_and_today_follows_the_theme_accent(browser, site):
    """Art alto-art-1101-4800-a: late = #b42318 on the pale ground, #ff8a7a on the dark one; today stays the theme's own colour."""
    ctx, pg, errs = _open(browser, site + "/o.html")
    col = "getComputedStyle(document.querySelector('#node-acceptance > .node-card')).outlineColor"
    today = "getComputedStyle(document.querySelector('#node-formation > .node-card')).outlineColor"
    pg.evaluate("document.documentElement.classList.add('alto-holo'); document.documentElement.style.setProperty('--accent', '#0a6f8c')")
    assert pg.evaluate(col) == "rgb(180, 35, 24)" and pg.evaluate(today) == "rgb(10, 111, 140)"
    pg.evaluate("document.documentElement.classList.add('dark'); document.documentElement.style.setProperty('--accent', '#4ff0e0')")
    assert pg.evaluate(col) == "rgb(255, 138, 122)" and pg.evaluate(today) == "rgb(79, 240, 224)"
    assert not errs, errs
    ctx.close()


@pytest.mark.parametrize("page", ["o.html", "s.html"])
def test_the_day_tags_show_and_the_rings_and_fills_are_readable(browser, site, page):
    """Art's e5aef87 note: tags were display:none; a78bfa fills were ~2.5:1; today solid 3px, soon dashed in full colour, late red."""
    ctx, pg, errs = _open(browser, site + "/" + page)
    st = pg.evaluate("""()=>{const q=s=>getComputedStyle(document.querySelector(s));
      return {tag:q('#node-formation .sp-tag').display, today:[q('#node-formation > .node-card').outlineStyle,q('#node-formation > .node-card').outlineWidth],
        soon:[q('#node-offer > .node-card').outlineStyle,q('#node-offer > .node-card').outlineWidth,q('#node-offer > .node-card').outlineColor,q('#node-formation > .node-card').outlineColor],
        late:[q('#node-acceptance > .node-card').outlineStyle,q('#node-acceptance > .node-card').outlineWidth], fill:q('#node-formation .sp-tag').backgroundColor}}""")
    assert st["tag"] != "none"
    w = lambda v: float(v[:-2])                                       # the page scales its cards, so widths are compared to each other, not to 3px
    assert st["today"][0] == "solid" and st["late"][0] == "solid" and st["today"][1] == st["late"][1]
    assert st["soon"][0] == "dashed" and 0.5 < w(st["soon"][1]) / w(st["today"][1]) < 0.8 and st["soon"][2] == st["soon"][3]     # 2px vs 3px, full colour like today's
    assert st["fill"] == "rgb(91, 63, 196)"                                                               # #5b3fc4
    pg.evaluate("document.documentElement.classList.add('dark')")
    assert pg.evaluate("getComputedStyle(document.querySelector('#node-formation .sp-tag')).backgroundColor") == "rgb(183, 166, 255)"
    assert not errs, errs
    ctx.close()


@pytest.mark.parametrize("page", ["o.html", "s.html"])
def test_a_planned_node_wears_one_class_by_the_readers_date(browser, site, page):
    ctx, pg, errs = _open(browser, site + "/" + page)
    got = pg.evaluate(CLASSES)
    assert got["formation"][0] == "sp-today" and got["formation"][1] == "Today"
    assert got["offer"][0] == "sp-soon" and got["offer"][1] == "Sat"
    assert got["acceptance"][0] == "sp-late" and got["acceptance"][1] == "3 days late"
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
    pg.click("#sp-chip")                                                  # (the tab on the right rail: no need to open the notes panel)
    pg.wait_for_timeout(200)
    assert pg.evaluate("document.getElementById('sp-sheet').classList.contains('open')")
    text = pg.evaluate("document.getElementById('sp-sheet').innerText")
    text = text.lower()                                                    # (the group names are set in capitals)
    assert "3 days late" in text and "today" in text and "this week" in text and "you marked 4 cards still learning" in text and "exam" in text
    pg.evaluate("document.querySelector('#sp-sheet .sp-li input').click()")          # tick the first (the late one)
    pg.wait_for_timeout(200)
    st = pg.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>/-st$/.test(k))))")
    assert list(st["s"]["__plan__"]["k"].values())[0][0] == 1 and st["v"] == 1
    got = pg.evaluate(CLASSES)
    assert got["acceptance"][0] == "sp-done" and got["acceptance"][1] == "✓ Done"
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
    pg.click("#sp-chip")
    pg.click("#sp-sheet .sp-go >> nth=0")
    assert pg.evaluate("document.querySelector('.node.sp-go') !== null")
    pg.click("#sp-sheet .sp-btn:not(.o)")
    assert "set_study_plan" in pg.evaluate("document.querySelector('#sp-sheet textarea').value")
    pg.evaluate("window._altoStudyPlanRoutes={open:function(){window.__routed=1}}")
    pg.click("#sp-sheet .sp-btn:not(.o)")
    assert pg.evaluate("window.__routed") == 1
    assert not errs, errs
    ctx.close()


def test_a_phone_card_carries_the_day_tag_and_no_ring_and_the_whole_view_draws_nothing(browser, site):
    """Luke L-1101-222655: a planned phone card shows its day tag (the desktop words), with no ring, outline or chip; the phone's Whole view draws nothing."""
    ctx, pg, errs = _open(browser, site + "/o.html", w=390, h=844, mobile=True)
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    got = pg.evaluate(CLASSES)
    assert {k: v for k, v in got.items()} == {"formation": ["sp-today", "Today"], "offer": ["sp-soon", "Sat"], "acceptance": ["sp-late", "3 days late"], "definiteness": ["sp-today", "Today"]}, got
    assert pg.evaluate("[...document.querySelectorAll('.node[class*=\"sp-\"] > .node-card')].every(c => getComputedStyle(c).outlineStyle === 'none' && getComputedStyle(c).boxShadow.indexOf('rgba(91') < 0)")
    assert pg.evaluate("[...document.querySelectorAll('.sp-tag')].every(t => getComputedStyle(t).display === 'block' && getComputedStyle(t).position === 'absolute')")
    assert pg.evaluate("getComputedStyle(document.getElementById('sp-row')).display") == "none"
    assert pg.evaluate("getComputedStyle(document.getElementById('sp-chip')).display") == "none"
    pg.evaluate("document.documentElement.classList.remove('mobile'); document.documentElement.classList.add('phone-whole'); window._altoStudyPlan.paint()")
    assert pg.evaluate(CLASSES) == {} and pg.evaluate("document.querySelector('.sp-tag')") is None            # the Whole view: nothing new
    assert not errs, errs
    ctx.close()
    ctx, pg, errs = _open(browser, site + "/o.html")
    pg.emulate_media(media="print")
    assert pg.evaluate("getComputedStyle(document.querySelector('#node-formation > .node-card')).outlineStyle") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('.sp-tag')).display") == "none"
    ctx.close()


@pytest.mark.parametrize("w, h", [(390, 844), (320, 568), (844, 390)])
def test_the_phone_menu_has_a_todays_plan_row_that_opens_the_list(browser, site, w, h):
    """Luke L-1101-231956: the first row of the phone MENU drawer, only with a plan; it opens the list (checkbox, node, tag), a tap on a line goes to that card."""
    ctx, pg, errs = _open(browser, site + "/o.html", w=w, h=h, mobile=True)
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(400)
    row = pg.evaluate("(() => { const r = document.getElementById('sp-today-row'); if(!r) return null; const b = r.getBoundingClientRect();"
                      " return [r.textContent.trim(), r === document.getElementById('nav-drawer-body').firstElementChild, Math.round(b.height), b.left >= 0 && b.right <= innerWidth]; })()")
    assert row and row[0].endswith("Today\u2019s plan \u00b7 3") and row[1] and row[2] >= 44 and row[3], row                # 2 today + 1 late
    pg.click("#sp-today-row")
    pg.wait_for_timeout(500)
    sh = pg.evaluate("(() => { const s = document.getElementById('sp-sheet'), c = getComputedStyle(s), b = s.getBoundingClientRect(); return [s.classList.contains('open'), c.position, Math.round(b.width), Math.round(b.height),"
                     " [...s.querySelectorAll('.sp-li')].map(l => [l.querySelector('.sp-go').textContent.replace(/^[0-9.]+ /, ''), l.querySelector('.sp-pill').textContent]), document.documentElement.scrollWidth <= innerWidth,"
                     " Math.round(s.querySelector('.sp-btn.o').getBoundingClientRect().height), getComputedStyle(s.querySelector('.sp-btn:not(.o)')).display]; })()")
    assert sh[0] and sh[1] == "fixed" and sh[2] == w and sh[3] == h and sh[5] and sh[6] >= 44 and sh[7] == "none", sh
    assert sorted(x[1] for x in sh[4]) == ["3 days late", "Today", "Today"], sh
    pg.click("#sp-sheet .sp-li input >> nth=0")                                                                      # a tick writes the reader's own plan state and the row's count follows
    assert "__plan__" in pg.evaluate("localStorage.getItem(Object.keys(localStorage).filter(k => /-st$/.test(k))[0]) || ''")
    pg.click("#sp-sheet .sp-btn.o")
    assert not pg.evaluate("document.getElementById('sp-sheet').classList.contains('open')")
    pg.evaluate("window.openNavDrawer()")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.getElementById('sp-today-row').textContent.trim()").endswith("Today\u2019s plan \u00b7 2")
    pg.click("#sp-today-row")
    pg.wait_for_timeout(400)
    pg.click("#sp-sheet .sp-go >> nth=0")                                                                             # a tap on a line: that node's own card, the sheet gone
    pg.wait_for_timeout(700)
    assert not pg.evaluate("document.getElementById('sp-sheet').classList.contains('open')")
    assert pg.evaluate("(document.querySelector('.node.mobile-featured') || {}).id") in ("node-acceptance", "node-formation", "node-definiteness")
    assert not errs, errs
    ctx.close()


def test_the_phone_menu_has_no_todays_plan_row_without_a_plan_or_on_a_computer(browser, site):
    ctx, pg, errs = _open(browser, site + "/n.html", w=390, h=844, mobile=True)
    pg.evaluate("window.openNavDrawer()")
    assert pg.evaluate("document.getElementById('sp-today-row') === null && document.getElementById('sp-sheet') === null")
    ctx.close()
    ctx, pg, errs = _open(browser, site + "/o.html")
    assert pg.evaluate("document.getElementById('sp-today-row') === null")
    assert not errs, errs
    ctx.close()


def test_the_tab_on_the_rail_counts_with_a_plan_and_a_page_without_one_has_none(browser, site):
    ctx, pg, errs = _open(browser, site + "/n.html")
    assert pg.evaluate("document.getElementById('sp-chip') === null && document.getElementById('sp-row') === null && document.getElementById('sp-sheet') === null")
    assert pg.evaluate("document.querySelectorAll('.sp-tag').length") == 0 and pg.evaluate("window._altoStudyPlan") is None
    ctx.close()
    ctx, pg, errs = _open(browser, site + "/o.html")
    assert pg.evaluate("document.getElementById('sp-chip').textContent") == "1 late \u00b7 Today: 2"
    pg.click("#sp-chip")
    pg.click("#sp-sheet .sp-tabs button[data-t=week]")
    text = pg.evaluate("document.getElementById('sp-sheet').innerText").lower()
    assert "offer" in text and "formation" not in text and "minutes a day" not in text      # (the plan names no minutes)
    assert not errs, errs
    ctx.close()


def _home(pageset):
    from alto.build import pages
    stub = ("<script>window.AltoCloud={enabled:true,known:true,user:{uid:'u1',email:'a@b.c',displayName:'A'},listPages:()=>Promise.resolve(%s),"
            "listShared:()=>Promise.resolve([]),signOut:()=>Promise.resolve(),createTimeline:()=>Promise.resolve({}),signIn:()=>Promise.resolve(),"
            "getPage:()=>Promise.resolve(''),forgetShare:()=>Promise.resolve()};</script>" % json.dumps(pageset))
    return pages.build_home([]).replace("<head>", "<head>" + stub, 1)


@pytest.mark.parametrize("style", ["classic", "retro"])
def test_the_homepage_card_shows_the_plan_state_on_a_computer_only(browser, tmp_path, style):
    from alto.build import retro
    ps = [dict(key="k1", title="A", heading="Contracts", project="Law", fmt="outline", tid="t1", units=["#4a9eff"], plan={"days": ["2026-11-05", "2026-11-05", "2026-11-02"], "exam": ""}),
          dict(key="k2", title="B", heading="Torts", project="Law", fmt="timeline", tid="t2", units=["#4a9eff"])]
    (tmp_path / "h.html").write_text(_home(ps), encoding="utf-8")
    (tmp_path / "retro").mkdir()
    name, js = retro.retro_asset()
    (tmp_path / "retro" / name).write_text(js, encoding="utf-8")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(type("H", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=str(tmp_path)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/h.html"
    init = NOW + "try{localStorage.setItem('alto-bg-home-v1-style','%s')}catch(e){}" % style
    ctx, pg, errs = _open(browser, url, init=init)
    assert pg.evaluate("[...document.querySelectorAll('.sp-card')].map(e=>e.textContent)") == ["Study plan Today 2 1 late ", "+ Make a study plan"]
    assert pg.evaluate("[...document.querySelectorAll('.sp-card')].every(e=>getComputedStyle(e).display==='flex')")
    if style == "retro":                                               # Art alto-art-1101-4900-a: square tags, late is #ff8a7a with black text (not the gold of Today)
        tg = pg.evaluate("(()=>{const b=document.querySelectorAll('.sp-card b');const g=e=>getComputedStyle(e);return [...b].map(e=>[e.textContent,g(e).borderRadius,g(e).backgroundColor,g(e).color])})()")
        assert tg[0][1] == "0px" and tg[1][1] == "0px" and tg[1][2] == "rgb(255, 138, 122)" and tg[1][3] == "rgb(0, 0, 0)" and tg[0][2] != tg[1][2], tg
    assert not errs, errs
    ctx.close()
    ctx, pg, errs = _open(browser, url, w=390, h=844, mobile=True, init=init)
    assert pg.evaluate("[...document.querySelectorAll('.sp-card')].every(e=>getComputedStyle(e).display==='none')")
    ctx.close()
    srv.shutdown()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("w, h", [(390, 844), (844, 390)])
def test_the_phone_day_tag_is_inside_its_card_clear_of_the_number_and_square_in_retro(site_hosted, style, w, h):
    """Sim 1107b: Retro's tag was a round pill, and in Holo held sideways it sat on the card number. Each style, portrait and landscape (WebKit)."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg, errs = _open(b, site_hosted + "/o.html", w=w, h=h, mobile=True)
        pg.evaluate("localStorage.clear()"); pg.evaluate("window._altoStyle.set('%s')" % style); pg.wait_for_timeout(1200)
        rows = pg.evaluate("""()=>[...document.querySelectorAll('.node[class*="sp-"]')].map(n=>{const t=n.querySelector('.sp-tag'),c=n.querySelector('.node-card'),o=n.querySelector('.node-order'),
          T=t.getBoundingClientRect(),C=c.getBoundingClientRect(),O=o?o.getBoundingClientRect():null;
          return {id:n.id,r:getComputedStyle(t).borderTopLeftRadius,inside:T.left>=C.left&&T.right<=C.right&&T.top>=C.top&&T.bottom<=C.bottom,
            hit:!!O&&O.width>0&&!(O.right<=T.left||O.left>=T.right||O.bottom<=T.top||O.top>=T.bottom)}})""")
        rows = [r for r in rows if r['id']]
        assert len(rows) == 4, rows
        for r in rows:
            assert r["inside"] and not r["hit"], (style, w, h, r)
            assert style != "retro" or r["r"] == "0px", (style, r)               # Retro's tags are square (Holo's own look sets its own)
        assert not errs, errs
        b.close()


@pytest.mark.parametrize("h", [390, 330])
def test_a_phone_card_held_sideways_fits_the_visible_height_and_is_not_cut(site, h):
    """Sim 1107c: held sideways the one-card view capped the card at 100dvh - 276px (114 px on a 390 px screen) and cut its body under the title. dvh follows Safari's bars: 330 is a
    landscape page with a tab strip up. The card ends above the visible bottom and shows everything it holds (WebKit 844 wide)."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg, errs = _open(b, site + "/o.html", w=844, h=h, mobile=True)
        r = pg.evaluate("""()=>{const c=document.querySelector('.node.mobile-featured .node-card'),b=c.getBoundingClientRect();
          return {vh:innerHeight,top:b.top,bottom:b.bottom,sh:c.scrollHeight,ch:c.clientHeight}}""")
        assert r["bottom"] <= r["vh"] - 8 and r["top"] >= 90, r                            # (inside the visible height, clear of the top bar)
        assert r["sh"] <= r["ch"] + 1, r                                                    # (nothing of the card cut)
        assert not errs, errs
        b.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("h", [312, 292, 280])
def test_a_phone_card_with_the_tab_strip_up_sideways_shows_its_last_row(site_hosted, style, h):
    """Sim 1107d D1: with Safari's tab strip up the visible height is ~290 px, the card was capped at ~125 px and its last row (the citation chip) was cut 10-14 px
    (and 3 px at 312). Short and sideways the card tightens so everything it holds fits, in all three looks (WebKit)."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg, errs = _open(b, site_hosted + "/o.html", w=874, h=h, mobile=True)
        pg.evaluate("localStorage.clear()"); pg.evaluate("window._altoStyle.set('%s')" % style); pg.wait_for_timeout(1000)
        r = pg.evaluate("""()=>{const c=document.querySelector('.node.mobile-featured .node-card'),f=c.querySelector('.node-footer'),cb=c.getBoundingClientRect();
          return {sh:c.scrollHeight,ch:c.clientHeight,foot:f.getBoundingClientRect().bottom,bottom:cb.bottom,vh:innerHeight}}""")
        assert r["sh"] <= r["ch"] + 1 and r["foot"] <= r["bottom"] and r["bottom"] <= r["vh"] - 8, (style, h, r)
        assert not errs, errs
        b.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_dark_toggle_keeps_the_day_tag_and_the_unit_label_even_after_the_pages_first_seconds(site_hosted, style):
    """Sim 1107d D2: the in-page Dark / Light toggle re-renders every card; the DONE / day tag (and, once the engine's 20 s label loop had ended, the unit label) stayed gone until a reload.
    On the phone, from the MENU, 22 s after load (WebKit)."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg, errs = _open(b, site_hosted + "/o.html", w=390, h=844, mobile=True)
        pg.evaluate("localStorage.clear()"); pg.evaluate("window._altoStyle.set('%s')" % style); pg.wait_for_timeout(22000)
        st = "()=>{const n=document.querySelector('.node.mobile-featured');return [(n.querySelector('.sp-tag')||{}).textContent,(n.querySelector('.node-unit')||{}).textContent]}"
        before = pg.evaluate(st)
        assert before[0] == "Today" and before[1], before
        for _ in range(2):                                                                   # dark, then light again
            pg.evaluate("window.openNavDrawer()"); pg.wait_for_timeout(300)
            pg.click("#drawer-mode-btn"); pg.wait_for_timeout(1500)
            assert pg.evaluate(st) == before, (style, pg.evaluate(st))
        assert not errs, errs
        b.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("w, h", [(390, 844), (844, 390)])
def test_the_phone_menu_shows_no_unlabelled_tile_under_todays_plan(site_hosted, style, w, h):
    """Sim 1107d D finding: under the Today's plan row the MENU showed a symbol-only tile (the "back to the timeline" tile, a no-op on the timeline itself). Every visible tile in the
    drawer now carries a word, in the three looks, portrait and landscape (WebKit)."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg, errs = _open(b, site_hosted + "/o.html", w=w, h=h, mobile=True)
        pg.evaluate("localStorage.clear()"); pg.evaluate("window._altoStyle.set('%s')" % style); pg.wait_for_timeout(1000)
        pg.evaluate("window.openNavDrawer()"); pg.wait_for_timeout(500)
        rows = pg.evaluate("""()=>[...document.querySelectorAll('#nav-drawer-body .drawer-btn')].filter(b=>b.getBoundingClientRect().height>0).map(b=>{const l=b.querySelector('.drawer-label');return [b.id,(l?l.textContent:b.textContent).trim()]})""")
        assert rows and rows[0][0] == "sp-today-row", rows
        assert all(r[1] for r in rows), rows
        # on a detail page the symbol tile is still there (it is how you go back)
        pg.evaluate("document.documentElement.classList.add('detail-open')")
        assert pg.evaluate("getComputedStyle(document.getElementById('drawer-timeline-btn')).display") != "none"
        assert not errs, errs
        b.close()


@pytest.mark.parametrize("style", ["holo", "classic"])
def test_a_tap_on_a_name_in_the_phone_sheet_closes_it_and_does_not_recentre_the_old_card(site_hosted, style):
    """Sim 1107d D4 (Holo): tapping a name left the sheet open and the card not centred. A real finger sequence (touchstart + touchend): the sheet closes at once, that node's card is
    featured, and the page's own 'any touch that is not a swipe re-centres the current card' handler is not run for touches inside the sheet (WebKit, dark, after a tick)."""
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        ctx, pg, errs = _open(b, site_hosted + "/o.html", w=390, h=844, mobile=True)
        pg.evaluate("localStorage.clear()"); pg.evaluate("window._altoStyle.set('%s')" % style); pg.evaluate("localStorage.setItem('alto-theme-v1','dark')")
        pg.reload(); pg.wait_for_timeout(1500)
        pg.evaluate("window.__fn = []; (function(){ var f = window.featureNode; window.featureNode = function(id, a){ window.__fn.push([id, a]); return f.apply(this, arguments); }; })()")
        pg.evaluate("window.openNavDrawer()"); pg.wait_for_timeout(300)
        pg.click("#sp-today-row"); pg.wait_for_timeout(600)

        def tap(sel, i):
            bb = pg.evaluate("(()=>{const r=document.querySelectorAll('%s')[%d].getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()" % (sel, i))
            pg.touchscreen.tap(bb[0], bb[1])
        pg.evaluate("window.__fn.length = 0")
        tap("#sp-sheet .sp-li input", 2); pg.wait_for_timeout(500)                           # a tick
        assert pg.evaluate("window.__fn") == [], pg.evaluate("window.__fn")                  # (a touch in the sheet does not re-centre the page's card)
        tap("#sp-sheet .sp-go", 0); pg.wait_for_timeout(500)
        assert not pg.evaluate("document.getElementById('sp-sheet').classList.contains('open')")
        assert pg.evaluate("window.__fn.filter(x=>x[1]===true).map(x=>x[0])") == ["acceptance"], pg.evaluate("window.__fn")
        assert pg.evaluate("document.querySelector('.node.mobile-featured').id") == "node-acceptance"
        assert not errs, errs
        b.close()
