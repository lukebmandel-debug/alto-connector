"""Each format's Info panel (a computer) and How to use sheet (a phone) tell the reader about that format's own controls and
no other's (Luke, 2026-11-13: "make sure the info is up to date and relevant for whichever page/format the user is on").

A line only one format has is the key: the page of that format shows its own, and none of the other six's. The static test reads the
built page; the browser test opens the panel and the sheet the way a reader does (WebKit, desktop and an iPhone), and skips without
Playwright (the repo venv has none; run it with the pw12 one)."""
import http.server
import re
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import info_help, palace_assets  # noqa: E402
from tests.info_pages import pages  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

# the page key (format_symbols.key_of) -> a line of the Info panel only that format has
DESK = {
    "timeline": "have Claude build this timeline",
    "outline": "have Claude build this outline",
    "lanes": "hold to glide",
    "solar": "stops and starts the orbits",
    "city": "plans a route between two buildings",
    "building": "lists the cards in order (C)",
    "world": "go to the lit places",
}
# ... and of the phone's sheet
PHONE = {
    "timeline": "build this timeline",
    "outline": "build this outline",
    "lanes": "steps to the previous or next event",
    "solar": "Tap a body to fly to it",
    "city": "plans a route between two buildings",
    "building": "Tap a room to open its card",
    "world": "the Tour bar steps from place to place",
}
KEY = {"solar": "system", "city": "palace"}          # the test page's name -> the key info_help uses


@pytest.fixture(scope="module")
def built():
    return pages()


def _info(html):
    return re.search(r'<div id="info-content">(.*?)\n    </div>', html, re.S).group(1)


def _sheet(html):
    i = html.index('id="tutorial-body"')
    return html[i:html.index("'  </div>',", i)]


def _plain(s):
    return re.sub(r"<[^>]+>", "", s.replace("',", " ").replace("    '", " ")).replace("&#8217;", "'")


@pytest.mark.parametrize("name", list(DESK))
def test_the_built_page_carries_its_own_format_help_only(built, name):
    html = built[name]
    desk, phone = _plain(_info(html)), _plain(_sheet(html))
    assert DESK[name] in desk and PHONE[name] in phone
    for other in DESK:
        if other != name:
            assert DESK[other] not in desk, (name, other)
            assert PHONE[other] not in phone, (name, other)


def test_no_old_wording_is_left_on_any_page(built):
    for name, html in built.items():
        both = _plain(_info(html)) + _plain(_sheet(html))
        for stale in ("beside the &#9432;", "above the Search pill", "all 5 acts", "plot summary", "Moving between scenes",
                      "Tap Back (top-left)", "MAP (top-left)", "MENU (top-right)", "left edge, above INFO", "picture tab under Filter"):
            assert stale not in both, (name, stale)


def test_a_format_that_draws_its_own_background_does_not_offer_a_picture(built):
    for name in ("solar", "city", "building", "world"):
        t = _plain(_info(built[name]))
        assert "photograph behind this" not in t and "draws its own background" in t, name
    for name in ("timeline", "outline", "lanes"):
        assert "photograph behind this" in _plain(_info(built[name])), name


def test_every_format_is_named_where_the_words_name_it():
    assert set(info_help.FMT) == {"timeline", "lanes", "outline", "system", "palace", "building", "world"}
    assert info_help.FMT["palace"] == "Memory Map" and info_help.FMT["world"] == "Memory Atlas"
    assert info_help.FMT["building"] == "Memory Blueprint"


# ── in a browser ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        b.devices = p.devices
        yield b
        b.close()


def _serve(html):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js"
                   else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def _tap(page, sel):
    r = page.evaluate("(s)=>{var r=document.querySelector(s).getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]}", sel)
    page.touchscreen.tap(r[0], r[1])


@pytest.mark.parametrize("name", list(DESK))
@pytest.mark.parametrize("device", ["desktop", "phone"])
def test_opening_info_shows_this_formats_line_and_no_other(browser, built, name, device):
    s = _serve(built[name])
    try:
        kw = dict(browser.devices["iPhone 13"]) if device == "phone" else {"viewport": {"width": 1280, "height": 800}}
        ctx = browser.new_context(**kw)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)) if "ResizeObserver" not in str(e) else None)
        page.goto(f"http://127.0.0.1:{s.server_address[1]}/index.html")
        page.wait_for_timeout(4000)
        if device == "phone":
            if page.evaluate("(()=>{var c=document.querySelector('.pm-close');return !!c&&c.getBoundingClientRect().width>0})()"):
                _tap(page, ".pm-close")                       # (a Memory Map opens on its own map page: MENU is behind it)
                page.wait_for_timeout(900)
            _tap(page, "#hamburger-tab")                      # real touches: touchstart / touchend, then the click
            page.wait_for_timeout(900)
            _tap(page, "#pmin-tutorial-toggle")               # MENU's How to use row
            page.wait_for_function("(()=>{var r=document.getElementById('tutorial-wrap').getBoundingClientRect();return r.width>100&&r.left>=0&&r.left<50&&getComputedStyle(document.getElementById('tutorial-wrap')).display!=='none'})()", timeout=20000)
            shown = page.evaluate("document.getElementById('tutorial-wrap').innerText")
            lines = PHONE
        else:
            page.click("#info-icon")
            page.wait_for_function("document.getElementById('info-btn').classList.contains('expanded')", timeout=20000)
            shown = page.evaluate("document.getElementById('info-content').innerText")
            lines = DESK
        shown = shown.replace("’", "'").replace("\n", " ")
        assert lines[name].replace("&#8217;", "'").lower() in shown.lower(), (name, device)
        for other, line in lines.items():
            if other != name and line != lines[name]:
                assert line.lower() not in shown.lower(), (name, other, device)
        assert not errors, errors
        ctx.close()
    finally:
        s.shutdown()


@pytest.mark.parametrize("name", ["timeline", "outline", "lanes", "building", "world"])
def test_the_first_menu_tile_has_a_label_that_names_what_it_does(browser, built, name):
    """The symbol-only first tile of a phone's MENU (back to the format's page) now has its name under it, like the others."""
    s = _serve(built[name])
    try:
        ctx = browser.new_context(**dict(browser.devices["iPhone 13"]))
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{s.server_address[1]}/index.html")
        page.wait_for_timeout(4000)
        _tap(page, "#hamburger-tab")
        page.wait_for_timeout(900)
        label = page.evaluate("document.querySelector('#drawer-timeline-btn .drawer-label').textContent")
        aria = page.evaluate("document.getElementById('drawer-timeline-btn').getAttribute('aria-label')")
        assert label.startswith("Back to the ") and label == aria, (name, label, aria)
        assert page.evaluate("(()=>{var l=document.querySelector('#drawer-timeline-btn .drawer-label').getBoundingClientRect();return l.width>20&&l.height>6})()"), name
        ctx.close()
    finally:
        s.shutdown()


def test_phone_detail_text_keeps_clear_of_mark_and_notes():
    """On a phone's detail page the MARK and NOTES buttons float at the right edge; no line of text may reach under them."""
    if pw is None:
        pytest.skip("Playwright is not installed")
    from alto.build.builder import build_from_file
    html = build_from_file(str(ROOT / "samples" / "contracts_brief.json"))[0]
    s = _serve(html)
    try:
        with pw.sync_playwright() as p:
            b = p.webkit.launch()
            ctx = b.new_context(**dict(p.devices["iPhone 13"]))
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{s.server_address[1]}/index.html")
            page.wait_for_timeout(4000)
            r = page.evaluate("(()=>{var r=document.querySelector('[id^=node-]').getBoundingClientRect();return [r.x+30,r.y+30]})()")
            page.touchscreen.tap(r[0], r[1])
            page.wait_for_timeout(2000)
            assert page.evaluate("document.documentElement.classList.contains('detail-open')")
            got = page.evaluate("""(()=>{var L=1e9;['hl-mode-btn','notes-toggle'].forEach(function(i){var e=document.getElementById(i),r=e&&e.getBoundingClientRect();if(r&&r.width>0)L=Math.min(L,r.left)});
              var R=0,w=document.createTreeWalker(document.getElementById('detail-content'),NodeFilter.SHOW_TEXT);
              while(w.nextNode()){if(!w.currentNode.nodeValue.trim())continue;var g=document.createRange();g.selectNodeContents(w.currentNode);[].forEach.call(g.getClientRects(),function(r){R=Math.max(R,r.right)})}
              return [L,R]})()""")
            assert got[0] < 1e8, "MARK / NOTES are not on the page"
            assert got[1] <= got[0] - 2, got
            b.close()
    finally:
        s.shutdown()


def test_holographic_phone_menu_drops_dark_light_and_classic_keeps_it():
    if pw is None:
        pytest.skip("Playwright is not installed")
    from alto.build.builder import build_from_file
    s = _serve(build_from_file(str(ROOT / "samples" / "contracts_brief.json"))[0])
    try:
        with pw.sync_playwright() as p:
            b = p.webkit.launch()
            ctx = b.new_context(**dict(p.devices["iPhone 13"]))
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{s.server_address[1]}/index.html")
            page.wait_for_timeout(4000)
            disp = "getComputedStyle(document.getElementById('drawer-mode-btn')).display"
            assert page.evaluate(disp) != "none"
            page.evaluate("localStorage.clear(); window._altoStyle.set('holo')")
            page.wait_for_function(f"document.documentElement.classList.contains('alto-holo') && {disp}==='none'", timeout=20000)
            page.evaluate("window._altoStyle.set('retro')")
            page.wait_for_function(f"!document.documentElement.classList.contains('alto-holo') && {disp}!=='none'", timeout=20000)
            b.close()
    finally:
        s.shutdown()
