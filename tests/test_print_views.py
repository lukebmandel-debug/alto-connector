"""Printing a timeline three ways, from two places.

  outline                      the numbered outline (the engine's own print)
  outline + all detail pages   that, then every detail page in outline order
  timeline picture, ink-saver  cards and lines, white paper, black and grey

The page owns the code (alto/build/print_views.py + the `print-views-*` engine
patches). Two things ask it: the notes panel's share dialog (its PRINT list) and
the homepage's Print... dialog, which opens the private page with
`#altoprint=<mode>` and lets the page print itself, so the same code serves both.

The browser tests are skipped without Playwright's Chromium; they stand in for
the account with routes (no network, no real account) and stub window.print so
the staged document can be inspected and rendered to PDF.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402
from alto.build import print_views  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"
HOME = ROOT / "alto" / "engine" / "home_template.html"


def _build(path=OUTLINE):
    return build_timeline(*load_brief(json.loads(Path(path).read_text(encoding="utf-8"))))


# ── source: wired in, anchored, and named for the user ─────────────────────

def test_the_print_patches_are_registered_and_anchored():
    names = {p["name"]: p for p in PATCHES}
    for n in ("print-views-stage", "print-views-unstage", "print-views-dialog-button"):
        assert n in names and names[n]["count"] == 1      # a moved anchor fails the build


def test_every_page_carries_the_print_views_and_the_dialog_button():
    html, _ = _build()
    assert 'id="alto-print-views-js"' in html
    assert "window._altoInkStage = function" in html
    assert 'data-print="ink">Timeline picture, ink-saver</button>' in html
    assert "if(mode === 'full'){" in html


def test_the_hash_is_read_without_the_word_the_bundler_counts():
    """single_file.py rewrites every `location.hash` (4 in the engine); a fifth
    would break every private page and bundle."""
    js = print_views.PRINT_JS
    assert "location.hash" not in js and "location['hash']" in js
    assert "__altoQuery.hash" in js          # what the private shell hands over
    from alto.build.single_file import private_page
    brief, nodes, conns = load_brief(json.loads(OUTLINE.read_text(encoding="utf-8")))
    page = private_page(brief, build_timeline(brief, nodes, conns)[0])   # raises on a miscount
    assert "alto-print-views-js" in page


def test_the_homepage_offers_print_with_three_named_choices():
    h = HOME.read_text(encoding="utf-8")
    assert "function altoPrintMenu(pg)" in h
    assert "['outline', 'Outline'," in h
    assert "['full', 'Outline + all detail pages'," in h
    assert "['ink', 'Timeline picture, ink-saver'," in h
    assert "privateHref(pg) + '#altoprint=' + mode" in h
    assert """<button data-a="print">Print…</button>""" in h          # in the share dialog
    assert "btn('Print…', ''" in h                                    # and in the ⋯ menu


# ── in a browser ───────────────────────────────────────────────────────────

pw = pytest.importorskip("playwright.sync_api")

STUB_PRINT = ("window.__printed=0;window.__at=null;window.print=function(){window.__printed++;"
              "window.__at=document.documentElement.className;};")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    html, _ = _build()
    f = tmp_path_factory.mktemp("print") / "page.html"
    f.write_text(html, encoding="utf-8")
    return html, f


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                          # no browser downloaded
            pytest.skip(f"no Chromium: {e}")
        yield b
        b.close()


def _open(browser, f, dark=False, hash_=""):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_init_script(STUB_PRINT + f"try{{localStorage.setItem('alto-theme-v1','{'dark' if dark else 'light'}')}}catch(e){{}}")
    pg = ctx.new_page()
    pg.goto(f.as_uri() + hash_)
    pg.wait_for_timeout(1200)
    return pg


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


GREY_CHECK = """() => {
  const bad = [], grey = c => { const m = /rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/.exec(c); return !m || (m[1] === m[2] && m[2] === m[3]); };
  document.querySelectorAll('#alto-ink-host, #alto-ink-host *').forEach(e => {
    const cs = getComputedStyle(e);
    ['color', 'borderTopColor', 'borderLeftColor', 'outlineColor', 'backgroundColor'].forEach(k => { if(!grey(cs[k])) bad.push(e.tagName + '.' + k + '=' + cs[k]); });
    if(e instanceof SVGElement){ ['fill', 'stroke'].forEach(k => { if(!grey(cs[k])) bad.push(e.tagName + '.' + k + '=' + cs[k]); }); }
    if(cs.backgroundImage !== 'none') bad.push(e.tagName + '.bg-image');
    if(cs.boxShadow !== 'none') bad.push(e.tagName + '.shadow');
    if(cs.backdropFilter && cs.backdropFilter !== 'none') bad.push(e.tagName + '.blur');
  });
  return bad.slice(0, 8);
}"""


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_the_ink_saver_picture_is_white_and_grey(browser, built, dark):
    _, f = built
    pg = _open(browser, f, dark)
    assert pg.evaluate("window._altoInkStage()") is True
    pg.evaluate("document.documentElement.classList.add('printing','print-ink')")
    pg.emulate_media(media="print")
    assert pg.evaluate(GREY_CHECK) == []
    # the paper is white and the live canvas is not on it
    assert pg.evaluate("getComputedStyle(document.body).backgroundColor") in ("rgb(255, 255, 255)", "rgba(0, 0, 0, 0)")
    assert pg.evaluate("getComputedStyle(document.getElementById('canvas')).display") == "none"
    # no pixel anywhere has a colour (when Pillow is here to look)
    try:
        from PIL import Image
        import io
    except ImportError:
        Image = None
    if Image:
        im = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB")
        assert all(r == g == b for r, g, b in im.getdata())
    pdf = pg.pdf(prefer_css_page_size=True)
    assert _pages(pdf) >= 1


def test_the_picture_fits_the_sheet_or_goes_across_several(browser, built):
    _, f = built
    pg = _open(browser, f)
    plan = lambda w, h, boxes="[]", segs="[]": pg.evaluate(f"window._altoInkPlan({w},{h},{boxes},{segs})")
    one = plan(900, 500)                                    # small: one sheet, landscape
    assert one["orient"] == "landscape" and len(one["rows"]) == 1 and one["cols"] == 1 and one["s"] >= 0.9
    # a tall picture is still on landscape sheets: one strip running down them, never cut through a card
    tall = plan(1000, 7000, "[{x:0,y:100,w:200,h:100},{x:0,y:900,w:200,h:100}]")
    assert tall["orient"] == "landscape" and len(tall["rows"]) > 3 and tall["s"] >= 0.42 and tall["cols"] == 1
    for _, end in tall["rows"][:-1]:
        assert not (100 < end < 200 or 900 < end < 1000)
    wide = plan(3000, 400)                                  # a long thin picture: a strip across, no more sheets than it needs
    assert wide["orient"] == "landscape" and wide["cols"] == 2 and len(wide["rows"]) == 1


def test_every_sheet_of_a_picture_has_the_same_scale_and_lines_up(browser, built):
    """The pieces tile the picture exactly, and every one is cut at a gap (no card) when there is one."""
    _, f = built
    pg = _open(browser, f)
    boxes = "[" + ",".join(f"{{x:0,y:{y},w:300,h:120}}" for y in range(0, 4000, 200)) + "]"      # cards every 200, gaps of 80
    plan = pg.evaluate(f"window._altoInkPlan(1400, 4100, {boxes}, [])")
    rows = plan["rows"]
    assert rows[0][0] == 0 and abs(rows[-1][1] - 4100) < 1
    for (_, e), (s2, _) in zip(rows, rows[1:]):
        assert e == s2                                              # no gap and no overlap between pieces
    cap = plan["h"] / plan["s"]
    assert all(e - s <= cap + 1 for s, e in rows)                    # every piece fits its sheet
    for _, e in rows[:-1]:
        assert not any(y < e < y + 120 for y in range(0, 4000, 200))   # never through a card
    sizes = [e - s for s, e in rows]
    assert max(sizes) - min(sizes[:-1] or sizes) < cap * 0.5        # even pieces, not one full sheet and a sliver


def test_a_cut_prefers_the_gap_the_fewest_lines_cross(browser, built):
    _, f = built
    pg = _open(browser, f)
    spans = "[[0,600],[700,1200],[1300,1600]]"                # clean gaps at 608/692 and 1208 within one 1250px sheet
    free = pg.evaluate(f"window._altoInkCuts(1600, 1250, {spans}, [])")
    assert abs(free[0][1] - 1208) < 1                          # nothing crosses either: the later gap, a fuller sheet
    busy = "[" + ",".join("[1180,1230]" for _ in range(6)) + "]"   # six lines run across the later gap
    cut = pg.evaluate(f"window._altoInkCuts(1600, 1250, {spans}, {busy})")
    assert abs(cut[0][1] - 692) < 1                            # so the cut moves to the clear one
    assert cut[-1][1] == 1600 and all(cut[i][1] == cut[i + 1][0] for i in range(len(cut) - 1))


def test_a_tall_timeline_prints_across_pages_without_a_blank_one(browser, built):
    _, f = built
    for fmt in ("Letter", "A4"):                                  # the two sheets the plan must fit
        pg = _open(browser, f)
        pg.evaluate("window.altoPrint('ink')")
        pg.wait_for_timeout(300)
        plan = pg.evaluate("window._altoInkLast")
        assert plan["orient"] == "landscape"
        assert pg.evaluate("document.querySelectorAll('.ink-tile').length") == len(plan["rows"]) * plan["cols"]
        pg.emulate_media(media="print")
        pdf = pg.pdf(prefer_css_page_size=True, format=fmt)
        assert _pages(pdf) == len(plan["rows"]) * plan["cols"], fmt   # one sheet per tile, none left over


def test_outline_and_all_detail_pages_come_in_outline_order(browser, built):
    _, f = built
    pg = _open(browser, f)
    order = pg.evaluate("NODE_ORDER")
    pg.evaluate("window.altoPrint('full')")
    pg.wait_for_timeout(300)
    assert "print-full" in pg.evaluate("document.documentElement.className")
    got = pg.evaluate("""() => {
      const host = document.getElementById('print-timeline-host'), all = document.getElementById('print-all');
      return {outlineFirst: !!(host.compareDocumentPosition(all) & Node.DOCUMENT_POSITION_FOLLOWING),
              outline: host.textContent.slice(0, 80),
              secs: [...all.querySelectorAll('.print-detail')].map(s => s.textContent)}
    }""")
    assert got["outlineFirst"] and "Outline" in got["outline"]
    byid = {n["id"]: n["title"] for n in pg.evaluate("NODES")}
    assert len(got["secs"]) == len(order)
    for sec, nid in zip(got["secs"], order):                      # page i is node i of the outline order
        assert byid[nid] in sec[:200]
    pg.emulate_media(media="print")
    pages = _pages(pg.pdf(prefer_css_page_size=True))
    assert pages >= len(order) + 1                               # the outline, then a sheet per page


def test_the_url_asks_the_page_to_print_itself_once(browser, built):
    _, f = built
    for mode, cls in (("outline", "print-timeline"), ("full", "print-full"), ("ink", "print-ink")):
        pg = _open(browser, f, hash_=f"#altoprint={mode}")
        pg.wait_for_function("window.__printed > 0", timeout=20000)
        assert cls in pg.evaluate("window.__at")
        assert "altoprint" not in pg.evaluate("location.href")   # a reload must not print again


def test_the_notes_panel_dialog_offers_the_picture(browser, built):
    _, f = built
    pg = _open(browser, f)
    pg.evaluate("window.AltoShare.open()")
    btn = pg.locator('#share-dialog .print-opt[data-print="ink"]')
    assert btn.inner_text() == "Timeline picture, ink-saver"
    btn.click()
    pg.wait_for_function("window.__printed > 0")
    assert "print-ink" in pg.evaluate("window.__at")


def test_printing_from_an_open_detail_page_returns_to_it(browser, built):
    _, f = built
    pg = _open(browser, f)
    pg.evaluate("showDetail('node', NODE_ORDER[2])")
    pg.evaluate("window.altoPrint('ink')")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.querySelectorAll('.ink-tile').length") >= 1
    pg.evaluate("window.dispatchEvent(new Event('afterprint'))")     # the print sheet closed
    pg.wait_for_timeout(300)
    assert pg.evaluate("window._currentDetailId") == pg.evaluate("NODE_ORDER[2]")
    assert pg.evaluate("document.getElementById('alto-ink-host')") is None


# ── the homepage, signed in to a stand-in account, through the private shell ──

CLOUD_STUB = """
const pages = [{key:'K1', tid:'contracts-outline', title:'Law', project:'Law', heading:'Contracts', units:['#4a9eff'], search:[], binned:0}];
window.AltoCloud = {
  enabled:true, known:true, user:{uid:'U1', email:'me@x.test', displayName:'Me'},
  signIn: async()=>{}, signOut: async()=>{}, onAuth(){},
  listPages: async()=>pages, listShared: async()=>[], purgeExpired: async()=>0,
  getPage: async()=>await (await fetch('/__page')).text(), getPageMeta: async()=>({updatedAt:'1'}),
  ensureMeta: async()=>{}, ensureTitle: async()=>{}, markViewed: async()=>{}, setTid(){},
  shareUrl: k=>location.origin+'/s/'+k, binTimeline: async()=>{}, moveTimeline: async()=>({}),
};
setTimeout(()=>{ try{ window.renderAccount && window.renderAccount(); }catch(e){} }, 0);
"""


@pytest.fixture()
def homepage(browser):
    from alto.build.pages import build_home
    from alto.build import private_shell
    from alto.build.single_file import private_page
    from alto.hosted import hosted_home
    brief, nodes, conns = load_brief(json.loads(OUTLINE.read_text(encoding="utf-8")))
    page = private_page(brief, build_timeline(brief, nodes, conns)[0], "Contracts")
    home = hosted_home(build_home([]))
    shell = private_shell.shell()
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_init_script(STUB_PRINT.replace("window.print=function(){",
        "window.print=function(){window.__text=document.body.innerText.slice(0,200);"))
    ctx.add_init_script("try{localStorage.setItem('alto-account-v1',JSON.stringify({provider:'google',name:'Me',email:'me@x.test',ts:'2026-10-06',v:1}))}catch(e){}")

    def route(r):
        u = r.request.url.split("#")[0]
        path = u.split("alto.test", 1)[-1]
        if path in ("/", "") or path.startswith("/?"):
            return r.fulfill(body=home, content_type="text/html")
        if path.startswith("/alto-cloud.js"):
            return r.fulfill(body=CLOUD_STUB, content_type="text/javascript")
        if path.startswith("/pv/"):
            return r.fulfill(body=shell, content_type="text/html")
        if path == "/__page":
            return r.fulfill(body=page, content_type="text/html")
        return r.fulfill(status=404, body="")
    ctx.route("http://alto.test/**", route)
    ctx.route(re.compile(r"^(?!http://alto\.test).*"), lambda r: r.abort())
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://alto.test/")
    pg.wait_for_selector("a.course-tile.live", timeout=15000)
    yield ctx, pg, errors
    ctx.close()


@pytest.mark.parametrize("label,cls", [("Outline", "print-timeline"),
                                       ("Outline + all detail pages", "print-full"),
                                       ("Timeline picture, ink-saver", "print-ink")])
def test_the_homepage_prints_a_private_timeline_through_the_shell(homepage, label, cls):
    ctx, pg, errors = homepage
    pg.locator("a.course-tile.live .tile-share").click()
    pg.locator('.share-menu button[data-a="print"]').click()
    assert pg.locator(".share-menu .sm-title").inner_text() == "Contracts"
    labels = [b.inner_text().split("\n")[0] for b in pg.locator(".share-menu .sm-pick").all()]
    assert labels == ["Outline", "Outline + all detail pages", "Timeline picture, ink-saver"]
    with ctx.expect_page() as popup:
        pg.locator(".share-menu .sm-pick", has_text=label).first.click()
    tab = popup.value
    tab.wait_for_function("window.__printed > 0", timeout=30000)
    assert cls in tab.evaluate("window.__at")
    assert "altoprint" not in tab.evaluate("location.href")        # the shell dropped it
    assert pg.url.rstrip("/") == "http://alto.test"                # the user stays where they were
    assert not pg.locator(".share-scrim").count()                   # and the dialog is gone
    assert errors == []


def test_the_dialog_can_be_dismissed_without_opening_anything(homepage):
    ctx, pg, _ = homepage
    pg.locator("a.course-tile.live .tile-more").click()
    pg.locator(".share-menu button", has_text="Print…").click()
    n = len(ctx.pages)
    pg.keyboard.press("Escape")
    assert not pg.locator(".share-scrim").count() and len(ctx.pages) == n
