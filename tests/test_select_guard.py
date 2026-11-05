"""No accidental page selection on any board (Luke, 2026-11-05: "whatever happens here with accidental highlighting of the whole page, please
fix. I've noticed this problem in other formats as well"). select_guard.py is ONE rule set that builder._add_tail adds to every page.

The page tests build every format with the repo's own builder (timeline, lanes, outline, System in its five styles, city map, Blueprint,
Museum, Atlas) and serve them over local HTTP, WebKit only on this Mac (Chromium too where it is installed). On each board a script
drags across it, double-clicks and triple-clicks its labels, and presses select-all, then asserts window.getSelection().toString()==''
(a selection wholly inside text that is meant to be read, an enlarged card, does not count). They also assert that the detail page's text
and a search field still select, and a phone keeps the rest of its behaviour. Skipped without Playwright."""
import copy
import http.server
import json
import os
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import building_schema as bs, palace_assets, select_guard  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

SHOT_DIR = os.environ.get("ALTO_SHOT_DIR", "")


# ── the pages ────────────────────────────────────────────────────────────────

def _sample(name):
    d = json.loads((ROOT / "samples" / name).read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


def _system():
    from tests.test_solar_draw import SMALL, SMALL_LINKS, solar_doc
    return build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))[0]


def _city():
    from tests.test_palace_chrome import bundle
    return build_timeline(*load_brief(copy.deepcopy(bundle())))[0]


def _blueprint():
    from tests.test_building_palace_tools import built
    return built()[0]


def _museum():
    from tests.test_building_pma_render import _html
    return _html()


def _atlas():
    from alto.build import world_plan as wp
    from tests.test_world_palace import built
    return built(world={"places": {"erie": wp.resolve("Peru")}})[0]


# name -> (builder, the style the System is put in or None)
FORMATS = {
    "timeline": (lambda: _sample("contracts_brief.json"), None),
    "lanes": (lambda: _sample("lanes_brief.json"), None),
    "outline": (lambda: _sample("outline_brief.json"), None),
    "system": (_system, "system"),
    "starchart": (_system, "chart"),
    "retro": (_system, "retro"),
    "star3d": (_system, "3d"),
    "holographic": (_system, "holo"),
    "city": (_city, None),
    "blueprint": (_blueprint, None),
    "museum": (_museum, None),
    "atlas": (_atlas, None),
}


@pytest.fixture(scope="module")
def pages():
    return {}


@pytest.fixture(scope="module")
def origin(pages):
    plan_name, plan_text = bs.hosted_json(bs.fixture())
    from alto import buildings
    from alto.buildings import pma_art
    pma = buildings.load("pma")
    pma_name, pma_text = bs.hosted_json(pma)
    art = dict(pma_art.files())

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            body, ct, code = b"no", "text/plain", 404
            if path.startswith("/p/") and path.endswith(".html") and path[3:-5] in pages:
                body, ct, code = pages[path[3:-5]].encode("utf-8"), "text/html; charset=utf-8", 200
            elif path == "/alto-cloud.js":
                body, ct, code = b"", "text/javascript", 200
            elif path.startswith("/bart/") and path[6:] in art:
                body, ct, code = art[path[6:]], "image/jpeg", 200
            else:
                hit = palace_assets.find(path, building_plans={plan_name: plan_text, pma_name: pma_text})
                if hit:
                    body, ct, code = hit[1].encode("utf-8"), hit[0], 200
            self.send_response(code)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {str(e)[:80]}")
        yield b
        try:
            b.close()
        except Exception:
            pass


# ── no browser: the rule set is shared, small and on every page ──────────────

def test_every_format_carries_the_one_rule_set_once():
    for name in ("contracts_brief.json", "lanes_brief.json", "outline_brief.json"):
        h = _sample(name)
        assert h.count('id="alto-select-css"') == 1 and h.count('id="alto-select-js"') == 1, name
    for make in (_system, _city, _blueprint, _museum, _atlas):
        h = make()
        assert h.count('id="alto-select-css"') == 1 and h.count('id="alto-select-js"') == 1, make.__name__


def test_the_rule_set_is_small_and_names_the_places_text_is_read():
    b = select_guard.block()
    assert len(b) < 3000
    for sel in ("#detail-page", "#summary-wrap", "#notes-panel", "textarea", "contenteditable", ".node.focused .node-card"):
        assert sel in b, sel
    assert "user-select:none" in b and "-webkit-touch-callout:none" in b       # the board and the chrome, and a phone's long press


def test_no_format_keeps_a_copy_of_the_rule():
    """One shared module: no other build module restates the page-wide none."""
    for f in (ROOT / "alto" / "build").glob("*.py"):
        if f.name == "select_guard.py":
            continue
        assert "html body{-webkit-user-select:none" not in f.read_text(encoding="utf-8").replace(" ", ""), f.name


# ── in a browser ─────────────────────────────────────────────────────────────

# the sentinel zones where text is read or written: a selection wholly inside one is allowed
ZONES = ("input,textarea,select,[contenteditable]:not([contenteditable=\"false\"]),#detail-page.visible,#summary-wrap.open,#notes-panel.open,"
         "#share-dialog.visible,[data-alto-select],.node.focused .node-card")

POINTS = """(zones) => {
  const out = [], seen = new Set();
  const W = innerWidth, H = innerHeight;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode()) && out.length < 40) {
    if (!/\\S{3}/.test(n.textContent)) continue;
    const el = n.parentElement;
    if (!el || el.closest(zones) || el.closest('script,style,svg defs')) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    const b = r.getBoundingClientRect();
    if (b.width < 12 || b.height < 6 || b.left < 0 || b.top < 0 || b.right > W || b.bottom > H) continue;
    const x = Math.round(b.left + b.width / 2), y = Math.round(b.top + b.height / 2);
    const hit = document.elementFromPoint(x, y);
    if (!hit || hit.closest(zones) || hit.closest('button,a,input,select,textarea,[role=button]')) continue;
    const k = Math.round(x / 40) + ':' + Math.round(y / 20);
    if (seen.has(k)) continue; seen.add(k);
    out.push([x, y, (n.textContent || '').trim().slice(0, 24)]);
  }
  return out;
}"""

BAD = """(zones) => {
  const s = window.getSelection();
  const t = String(s || '');
  if (!t.trim()) return '';
  const inZone = n => { const e = n && (n.nodeType === 1 ? n : n.parentElement); return !!(e && e.closest(zones)); };
  return (inZone(s.anchorNode) && inZone(s.focusNode)) ? '' : t.slice(0, 60);
}"""

STRICT = "String(window.getSelection() || '')"


def _serve(pages, name):
    builder, style = FORMATS[name]
    key = name if style is None else "system"
    if key not in pages:
        pages[key] = builder()
    return key


def _drive(browser, origin, pages, name, width=1280, height=800):
    key = _serve(pages, name)
    builder, style = FORMATS[name]
    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{origin}/p/{key}.html")
    page.wait_for_timeout(2500)
    if style:
        page.wait_for_function("window._altoSolarStyles", timeout=20000)
        page.evaluate("s => window._altoSolarStyles.set(s)", style)
        page.wait_for_timeout(1500)
    return page, ctx, errors


@pytest.mark.parametrize("name", list(FORMATS))
def test_a_board_never_starts_a_selection(browser, origin, pages, name):
    page, ctx, errors = _drive(browser, origin, pages, name)
    try:
        # select-all with a board in front of you selects nothing (strict)
        page.mouse.move(640, 400)
        page.keyboard.press("Meta+a")
        assert page.evaluate(STRICT).strip() == "", ("select-all", name, page.evaluate(STRICT)[:80])
        page.evaluate("window.getSelection().removeAllRanges()")
        pts = page.evaluate(POINTS, ZONES)
        assert len(pts) >= 1, (name, "no board text found to try")
        # drags across the board: from label to label and over empty board (strict: a drag never selects)
        trails = [(pts[0], pts[-1])] + [(pts[i], pts[(i + 1) % len(pts)]) for i in range(min(3, len(pts)))]
        trails += [([120, 330, ""], [1100, 640, ""]), ([300, 700, ""], [700, 200, ""])]
        for a, b in trails:
            page.mouse.move(a[0], a[1])
            page.mouse.down()
            page.mouse.move((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, steps=6)
            page.mouse.move(b[0], b[1], steps=6)
            page.mouse.up()
            assert page.evaluate(BAD, ZONES) == "", ("drag", name, a, b, page.evaluate(STRICT)[:80])
        page.keyboard.press("Escape")
        # double- and triple-clicks on the labels
        for p in pts[:4]:
            for count in (2, 3):
                page.mouse.click(p[0], p[1], click_count=count)
                assert page.evaluate(BAD, ZONES) == "", (f"click x{count}", name, p, page.evaluate(STRICT)[:80])
                page.keyboard.press("Escape")
                page.evaluate("window.getSelection().removeAllRanges()")
        # the chrome: every bar, chip and toggle on the page is none
        bad = page.evaluate("""(zones) => [...document.querySelectorAll('#title-bar,#nav,#node-nav-bar,#minimap-wrap,#minimap-toggle,#sol-ctl,#sol-tour,.node-card,button')]
            .filter(e => !e.closest(zones) && e.getBoundingClientRect().width > 0)
            .filter(e => { const s = getComputedStyle(e); return (s.userSelect || s.webkitUserSelect) !== 'none' && s.webkitUserSelect !== 'none'; })
            .map(e => e.id || e.className).slice(0, 5)""", ZONES)
        assert bad == [], (name, bad)
        assert not [e for e in errors if "ResizeObserver" not in e], errors
        if SHOT_DIR and name == "star3d" and browser.browser_type.name == "webkit":
            Path(SHOT_DIR).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(SHOT_DIR) / "select-fix-3d-after-drag-dblclick.png"))
    finally:
        ctx.close()


@pytest.mark.parametrize("name", ["timeline", "outline", "lanes", "system", "city", "atlas", "blueprint"])
def test_detail_text_and_a_search_field_still_select(browser, origin, pages, name):
    page, ctx, errors = _drive(browser, origin, pages, name)
    try:
        opened = page.evaluate("""() => { if (typeof showDetail !== 'function') return 'no showDetail';
            showDetail('node', NODES[0].id);
            return document.querySelector('#detail-page.visible') ? 'ok' : 'closed'; }""")
        page.wait_for_timeout(900)
        if opened != "ok":
            pytest.skip(f"{name}: detail page not reachable here ({opened})")
        style = page.evaluate("(() => { const e = document.querySelector('#detail-content') || document.querySelector('#detail-page'); const s = getComputedStyle(e); return s.userSelect + '|' + s.webkitUserSelect; })()")
        assert "text" in style, style
        p = page.evaluate("""() => { const w = document.createTreeWalker(document.querySelector('#detail-page'), NodeFilter.SHOW_TEXT); let n;
            while ((n = w.nextNode())) { if (!/\\S{3}/.test(n.textContent)) continue; const r = document.createRange(); r.selectNodeContents(n);
              const b = r.getBoundingClientRect(); if (b.width > 40 && b.top > 60 && b.bottom < innerHeight - 20 && b.left > 0)
              { const x = Math.round(b.left + b.width / 2), y = Math.round(b.top + b.height / 2); const h = document.elementFromPoint(x, y);
                if (h && h.closest('#detail-page') && !h.closest('button,a')) return [x, y]; } }
            return null; }""")
        if not p:
            p = page.evaluate("""() => { const d = document.querySelector('#detail-page'); const w = document.createTreeWalker(d, NodeFilter.SHOW_TEXT); let n, out = [];
                while ((n = w.nextNode()) && out.length < 4) { if (!/\\S{3}/.test(n.textContent)) continue; const r = document.createRange(); r.selectNodeContents(n); const q = r.getBoundingClientRect();
                  const h = document.elementFromPoint(Math.round(q.left + q.width / 2), Math.round(q.top + q.height / 2));
                  out.push([n.textContent.trim().slice(0, 20), Math.round(q.left), Math.round(q.top), Math.round(q.width), h && (h.id || h.className || h.tagName)]); }
                return [d.className, out]; }""")
        assert isinstance(p, list) and isinstance(p[0], int), ("no readable text in the detail page", name, p)
        # (Alto's own highlighter turns a selection in the detail page into a highlight at once, so watch the selection as it is made)
        page.evaluate("window.__sel = ''; document.addEventListener('selectionchange', () => { const t = String(getSelection() || ''); if (t.length > window.__sel.length) window.__sel = t; })")
        page.mouse.click(p[0], p[1], click_count=3)
        page.wait_for_timeout(200)
        assert page.evaluate("window.__sel").strip() != "", (name, "the detail page's text no longer selects")
    finally:
        ctx.close()


@pytest.mark.parametrize("name", ["timeline", "outline", "system"])
def test_a_search_field_still_selects_and_types(browser, origin, pages, name):
    page, ctx, errors = _drive(browser, origin, pages, name)
    try:
        info = page.evaluate("""() => { const i = [...document.querySelectorAll('input')].find(e => /text|search/.test(e.type) && e.getBoundingClientRect().width > 0
            && !e.closest('#detail-page,#notes-panel')) || [...document.querySelectorAll('input[type=search],input[type=text]')][0];
            if (!i) return null; const s = getComputedStyle(i); return [i.id || i.className, s.userSelect, s.webkitUserSelect, i.getBoundingClientRect().width]; }""")
        assert info, "no search field on the page"
        assert "text" in (info[1], info[2]), info
        if info[3] > 0:
            loc = page.locator("input[type=search],input[type=text]").evaluate_all("els => els.findIndex(e => e.getBoundingClientRect().width > 0)")
            box = page.locator("input[type=search],input[type=text]").nth(loc)
            box.click()
            page.keyboard.type("hello world")
            assert box.input_value() == "hello world"
            if info[3] >= 60:
                box.dblclick()
                sel = box.evaluate("e => e.value.slice(e.selectionStart, e.selectionEnd)")
                assert sel in ("hello", "world", "hello ", " world", "hello world"), sel
            else:
                # the search field starts collapsed (~11 px wide): a double-click lands on no word there, in Chromium it selects '' even with no
                # guard on the page, so a narrow field is checked with select-all, which still has to select its text under the rule set
                box.focus()
                page.keyboard.press("ControlOrMeta+a")
                sel = box.evaluate("e => e.value.slice(e.selectionStart, e.selectionEnd)")
                assert sel == "hello world", sel
    finally:
        ctx.close()


def test_a_press_in_an_editable_keeps_its_caret(browser, origin, pages):
    page, ctx, errors = _drive(browser, origin, pages, "timeline")
    try:
        page.evaluate("""() => { const d = document.createElement('div'); d.id = 'zz-ed'; d.contentEditable = 'true'; d.textContent = 'one two three';
            d.style.cssText = 'position:fixed;left:200px;top:300px;z-index:99999;background:#fff;color:#000;padding:8px;font:16px sans-serif'; document.body.appendChild(d); }""")
        page.dblclick("#zz-ed")
        assert page.evaluate(STRICT).strip() in ("one", "two", "three", "one ", "two ", "three"), page.evaluate(STRICT)
    finally:
        ctx.close()


def test_a_phone_board_has_no_long_press_but_its_text_keeps_it(browser, origin, pages):
    if browser.browser_type.name != "webkit":
        pytest.skip("phone emulation is WebKit")
    key = _serve(pages, "outline")
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2,
                              user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    page = ctx.new_page()
    try:
        page.goto(f"{origin}/p/{key}.html")
        page.wait_for_timeout(2500)
        board = page.evaluate("(() => { const s = getComputedStyle(document.querySelector('#canvas') || document.body); return [s.webkitTouchCallout, s.webkitUserSelect || s.userSelect]; })()")
        assert board[1] == "none" and board[0] in ("none", None, ""), board        # (Playwright's WebKit does not report -webkit-touch-callout; the rule is asserted on the page's sheet below)
        assert "-webkit-touch-callout:none" in page.evaluate("document.getElementById('alto-select-css').textContent")
        text = page.evaluate("(() => { const s = getComputedStyle(document.querySelector('#detail-page')); return [s.webkitTouchCallout, s.webkitUserSelect || s.userSelect]; })()")
        assert text[1] in ("text", "none") and text[0] in ("default", None, ""), text      # (the detail page is the readable text; it is "text" once open)
        page.evaluate("showDetail('node', NODES[0].id)")
        page.wait_for_timeout(900)
        assert page.evaluate("(() => { const s = getComputedStyle(document.querySelector('#detail-content') || document.querySelector('#detail-page')); return s.webkitUserSelect || s.userSelect; })()") == "text"
        assert page.evaluate("document.documentElement.classList.contains('mobile')")
    finally:
        ctx.close()
