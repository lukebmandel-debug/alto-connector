"""1.9.62 follow-ups: the phone's homepage search, the filter toggle's double-click, and a Freewrite attached to a report.

* the homepage's phone layout is a media query (the page never carries `.mobile`), so the desktop's expand control
  (search.py SX_*) used to show up on a phone and, tapped, shoved the pill under the avatar: it is a no-op there now;
* a double-click on the Filter toggle only switches filters off or on: the panel never opens or closes for it;
* Notes' footer offers "Attach my Freewrite" once something is written, and a report then carries it.
The browser parts are skipped without Playwright."""
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto.build.builder import build_timeline, load_brief   # noqa: E402
from alto.build.pages import build_home                      # noqa: E402
from alto.build import search                                # noqa: E402
from alto.build import freewrite                             # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None
needs_browser = pytest.mark.skipif(pw is None, reason="Playwright is not installed")
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


# ── source ──────────────────────────────────────────────────────────────────

def test_the_expand_control_is_off_on_a_phone_in_css_and_script():
    assert "@media (max-width:640px){#sx-toggle,#sx-scrim,.sx-hint{display:none !important;}}" in search.SX_CSS
    js = search.SX_JS
    assert "function phone(){ return window.innerWidth<=640; }" in js
    assert "window._altoSX={big:big, set:set, collapse:collapse};" in js
    assert "root.classList.toggle('sx-big',on)" not in js            # every class change goes through big()


def test_the_report_asks_the_freewrite_for_its_document():
    from alto.build.engine_patches import PATCHES
    names = {p["name"] for p in PATCHES}
    assert {"freewrite-report-guard", "freewrite-report-css", "freewrite-report-mail-text", "freewrite-report-section"} <= names
    assert "window._altoFwReport = function(force)" in freewrite.FREEWRITE
    assert "Attach my Freewrite" in freewrite.FREEWRITE


# ── in a browser ────────────────────────────────────────────────────────────

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


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    d = tmp_path_factory.mktemp("followups")
    brief, nodes, conns = load_brief(json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8")))
    (d / "t.html").write_text(build_timeline(brief, nodes, conns)[0], encoding="utf-8")
    import test_rename as tr
    (d / "home.html").write_text(build_home([]), encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    h.log_message = lambda *a: None
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tr.FAKE_HOME
    srv.shutdown()


def _phone(browser, init=None):
    ctx = browser.new_context(viewport={"width": 390, "height": 664}, device_scale_factor=2, is_mobile=True,
                              has_touch=True, user_agent=PHONE_UA)
    if init:
        ctx.add_init_script(init)
    return ctx


@needs_browser
def test_the_phone_homepage_search_has_no_expand_control_even_when_it_was_saved_on(browser, site):
    base, fake = site
    if browser.browser_type.name != "webkit":
        pytest.skip("phone emulation is checked in WebKit")
    ctx = _phone(browser, fake + "try{localStorage.setItem('alto-search-big','1')}catch(e){}")
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(base + "/home.html"); pg.wait_for_timeout(2500)
    before = pg.evaluate("document.getElementById('search-btn').getBoundingClientRect().left")
    pg.tap("#search-btn"); pg.wait_for_timeout(600)
    pg.keyboard.type("to", delay=60); pg.wait_for_timeout(600)
    s = pg.evaluate("""(()=>{const b=document.getElementById('search-btn'),r=b.getBoundingClientRect();
      return {expanded:b.classList.contains('expanded'),left:r.left,right:r.right,inline:b.getAttribute('style'),
        big:document.documentElement.classList.contains('sx-big'),tg:getComputedStyle(document.getElementById('sx-toggle')).display,
        rich:document.querySelectorAll('.sr-rich').length,rows:document.querySelectorAll('.search-result').length,
        info:document.getElementById('info-btn').getBoundingClientRect().left}})()""")
    assert s["expanded"] and s["left"] == before and not s["inline"]       # it grew in place, nothing re-centred it
    assert not s["big"] and s["tg"] == "none" and s["rich"] == 0           # no expanded panel, no expand button, plain rows
    assert s["right"] <= s["info"] - 8 + 0.5                                 # and it stops short of the info box
    assert not errs
    ctx.close()


@needs_browser
def test_a_double_click_on_filter_switches_filters_without_opening_the_panel(browser, site):
    base, _ = site
    phone = browser.browser_type.name == "webkit"
    ctx = _phone(browser) if phone else browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(base + "/t.html"); pg.wait_for_timeout(3000)
    is_open = lambda: pg.evaluate("document.getElementById('ef-panel').classList.contains('open')")
    hit = (lambda: pg.tap("#filter-toggle")) if phone else (lambda: pg.click("#filter-toggle"))
    hit(); pg.wait_for_timeout(100)
    assert not is_open()                                  # it waits to see whether a second is coming
    pg.wait_for_timeout(500)
    assert is_open()                                      # a single click or tap opens it
    pg.evaluate("window._altoFilterOpen(false)"); pg.wait_for_timeout(400)
    seen = []
    if phone:
        hit(); pg.wait_for_timeout(60); hit()
    else:
        pg.dblclick("#filter-toggle")
    for _ in range(8):
        seen.append(is_open()); pg.wait_for_timeout(100)
    assert not any(seen)                                  # a double never opens it, not even for a moment
    ctx.close()


@needs_browser
def test_a_freewrite_can_be_attached_to_a_report(browser, site):
    base, _ = site
    stub = ("window.__w=null;window.open=function(){var d={html:'',write:function(h){this.html+=h},close:function(){}};"
            "window.__w=d;return {document:d};};")
    phone = browser.browser_type.name == "webkit"
    ctx = _phone(browser, stub) if phone else browser.new_context(viewport={"width": 1400, "height": 900})
    if not phone:
        ctx.add_init_script(stub)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    alerts = []
    pg.on("dialog", lambda d: (alerts.append(d.message), d.accept()))
    pg.goto(base + "/t.html"); pg.wait_for_timeout(3000)
    pg.evaluate("toggleNotes()"); pg.wait_for_timeout(500)
    shown = lambda: pg.evaluate("getComputedStyle(document.getElementById('fw-attach')).display")
    assert shown() == "none"                              # nothing written: nothing to attach
    pg.evaluate("window._altoFw.setMode('fw')"); pg.wait_for_timeout(300)
    pg.evaluate("""(()=>{const e=document.getElementById('fw-editor');e.innerHTML='<h1>Offer</h1><ul><li>manifest assent</li><li>definite terms</li></ul><p>Done.</p><script>x</script>';
      e.dispatchEvent(new Event('input',{bubbles:true}));})()""")
    pg.wait_for_timeout(900)
    pg.evaluate("window._altoFw.setMode('notes')"); pg.wait_for_timeout(300)
    assert shown() == "flex"
    pg.evaluate("generateNotesReport()"); pg.wait_for_timeout(300)        # not ticked, no highlights: nothing to export
    assert alerts and "Freewrite" in alerts[-1] and pg.evaluate("window.__w") is None
    pg.evaluate("(()=>{const c=document.querySelector('#fw-attach input');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));})()")
    pg.evaluate("generateNotesReport()"); pg.wait_for_timeout(500)
    html = pg.evaluate("window.__w.html")
    assert "Your Freewrite" in html and "<h1>Offer</h1>" in html and html.count("<li>") == 2 and "<script>x" not in html
    assert "Your Highlights" not in html                                  # a report may be the Freewrite alone
    assert "FREEWRITE%3A" in html and "manifest%20assent" in html          # and the email carries it as text
    # the Freewrite pane's own Report button attaches it whatever the tick says
    pg.evaluate("(()=>{const c=document.querySelector('#fw-attach input');c.checked=false;c.dispatchEvent(new Event('change',{bubbles:true}));})()")
    pg.evaluate("window.__w=null; window._altoFw.setMode('fw')"); pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('fw-report').click()"); pg.wait_for_timeout(500)
    assert "Your Freewrite" in pg.evaluate("window.__w.html")
    assert not errs
    ctx.close()
