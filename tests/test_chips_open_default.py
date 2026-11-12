"""The top chip bar opens OPEN, a shut bar is remembered per timeline, and a card's sub-chip lights the + that reopens it (Luke, 2026-11-05:
"have anything open with the top nav chip bar starting open by default. If a user closes it, then remember that for the next time they enter
that file. If they are hovering on a subchip in a node, the plus button should be faintly highlighted so they know they can open it again").

The choice is {v:'on'|'off', t} under `alto-hl-{tid}-chips` (the background's own mechanism: a share re-stamps it, alto-cloud.js syncs it, the
newest wins). The old global `alto-chips-off` is ignored. Checked in WebKit first (Luke uses Safari) and in Chromium; Classic light/dark, Retro and
Holographic; plus a touch viewport (no hover there, so no hint). Skipped without Playwright."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import clear_top, holo, retro  # noqa: E402
from alto.build.blocks import ID_PATTERNS  # noqa: E402
from alto.build.builder import build_from_file, build_timeline, load_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

STYLES = ("classic", "dark", "retro", "holo")
OP = "+getComputedStyle(document.getElementById('ct-chips')).opacity"


def _page():
    html, _ = build_from_file(str(ROOT / "samples" / "outline_brief.json"))
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    b, _n, _c = load_brief(d)
    return html, ID_PATTERNS["hl_key"].format(tid=b.timeline_id)


@pytest.fixture(scope="module", params=("webkit", "chromium"))
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


@pytest.fixture(scope="module")
def site():
    html, key = _page()

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            ok = path in ("/", "/index.html", "/alto-cloud.js")
            body = (html if path != "/alto-cloud.js" else "").encode("utf-8")
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "text/javascript" if path == "/alto-cloud.js" else "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body) if ok else 2))
            self.end_headers()
            self.wfile.write(body if ok else b"no")

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d/index.html" % srv.server_address[1], key
    srv.shutdown()


def _open(browser, url, style, w=1280, h=800, touch=False, seed=None):
    ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=False)
    if seed:
        ctx.add_init_script("try{%s}catch(e){}" % seed)
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_selector("#ct-chips", state="attached", timeout=8000)
    if style == "dark":
        page.evaluate("document.documentElement.classList.add('dark')")
    elif style == "retro":
        page.add_script_tag(content=retro.ASSET)
        page.evaluate("window._altoRetro && window._altoRetro.on()")
    elif style == "holo":
        page.add_script_tag(content=holo.ASSET)
        page.evaluate("window._altoHolo && window._altoHolo.on()")
    page.wait_for_timeout(700)
    return page


def _sub(page):
    """The centre of a visible sub-chip (a card's character / environment / theme button)."""
    return page.evaluate("""()=>{for(const e of document.querySelectorAll('.csym-btn,.esym-btn,.tsym-btn')){const q=e.getBoundingClientRect();
      if(q.width>2&&q.height>2&&q.left>0&&q.right<innerWidth&&q.top>120&&q.bottom<innerHeight) return {x:(q.left+q.right)/2,y:(q.top+q.bottom)/2};} return null;}""")


def _is_off(page):
    return page.evaluate("document.documentElement.classList.contains('ct-chips-off')")


def _stored(page, key):
    return page.evaluate("k=>{try{return JSON.parse(localStorage.getItem(k)||'null');}catch(e){return 'bad';}}", key + "-chips")


def test_the_keys_and_the_hint_rules_are_in_the_page():
    html, key = _page()
    assert "alto-hl-" in key
    assert key + "-chips" in html and "alto-chips-off" not in html
    assert "ct-hint" in html and ".csym-btn,.esym-btn,.tsym-btn" in html
    assert "alto-chips" in (ROOT / "alto/cloud/alto-cloud.js").read_text(encoding="utf-8")
    assert "__HLK__" not in clear_top.block(hl_key="alto-hl-t1") and "alto-hl-t1-chips" in clear_top.block(hl_key="alto-hl-t1")


@pytest.mark.parametrize("style", STYLES)
def test_opens_open_a_close_is_remembered_and_reopening_forgets_it(browser, site, style):
    url, key = site
    page = _open(browser, url, style)
    try:
        assert not _is_off(page) and page.evaluate(OP) == 1                       # open by default, in plain sight
        assert _stored(page, key) is None
        page.click("#ct-chips")
        page.wait_for_function("document.documentElement.classList.contains('ct-chips-off')", timeout=4000)
        st = _stored(page, key)
        assert st["v"] == "off" and st["t"] > 1e12, st                            # shut: remembered for this file
        page.reload()
        page.wait_for_selector("#ct-chips", state="attached", timeout=8000)
        page.wait_for_timeout(500)
        assert _is_off(page)                                                      # …and still shut on the next visit
        page.click("#ct-chips")
        page.wait_for_function("!document.documentElement.classList.contains('ct-chips-off')", timeout=4000)
        assert _stored(page, key)["v"] == "on"
        page.reload()
        page.wait_for_selector("#ct-chips", state="attached", timeout=8000)
        page.wait_for_timeout(500)
        assert not _is_off(page)
    finally:
        page.context.close()


def test_the_old_global_choice_is_ignored_and_another_timelines_choice_does_not_carry(browser, site):
    url, key = site
    seed = "localStorage.setItem('alto-chips-off','1');localStorage.setItem('alto-hl-someone-else-chips',JSON.stringify({v:'off',t:Date.now()}));"
    page = _open(browser, url, "classic", seed=seed)
    try:
        assert not _is_off(page)
    finally:
        page.context.close()


def test_a_choice_from_another_device_is_applied_when_it_arrives(browser, site):
    url, key = site
    page = _open(browser, url, "classic")
    try:
        page.evaluate("k=>{localStorage.setItem(k, JSON.stringify({v:'off',t:Date.now()})); window.dispatchEvent(new Event('alto-chips'));}", key + "-chips")
        page.wait_for_timeout(300)
        assert _is_off(page) and "Show" in page.get_attribute("#ct-chips", "title")
        page.evaluate("k=>{localStorage.setItem(k, JSON.stringify({v:'on',t:Date.now()})); window.dispatchEvent(new Event('alto-chips'));}", key + "-chips")
        page.wait_for_timeout(300)
        assert not _is_off(page)
    finally:
        page.context.close()


@pytest.mark.parametrize("style", STYLES)
def test_a_sub_chip_lights_the_plus_faintly_only_while_the_bar_is_shut(browser, site, style):
    url, key = site
    page = _open(browser, url, style)
    try:
        c = _sub(page)
        assert c, "no sub-chip on screen"
        page.mouse.move(c["x"], c["y"])                                           # open bar: nothing to hint
        page.wait_for_timeout(250)
        assert not page.evaluate("document.documentElement.classList.contains('ct-hint')")
        page.click("#ct-chips")
        page.wait_for_function("document.documentElement.classList.contains('ct-chips-off')", timeout=4000)
        page.mouse.move(700, 700)
        page.wait_for_timeout(300)
        box0 = page.evaluate("(()=>{const q=document.getElementById('ct-chips').getBoundingClientRect();return [q.left,q.top,q.width,q.height];})()")
        assert page.evaluate(OP) == 0                                             # shut and the pointer elsewhere: the + is out of sight
        c = _sub(page)
        page.mouse.move(c["x"], c["y"])                                           # over a sub-chip: faintly lit
        page.wait_for_timeout(350)
        lit = page.evaluate(OP)
        assert 0.3 < lit < 0.8, lit
        assert page.evaluate("(()=>{const q=document.getElementById('ct-chips').getBoundingClientRect();return [q.left,q.top,q.width,q.height];})()") == box0   # no layout shift
        page.mouse.move(700, 700)                                                 # off it: gone again
        page.wait_for_timeout(350)
        assert page.evaluate(OP) == 0
        page.mouse.move(c["x"], c["y"])
        page.wait_for_timeout(300)
        assert page.evaluate(OP) < 1
        cx, cy = box0[0] + box0[2] / 2, box0[1] + box0[3] / 2
        page.mouse.move(cx, cy)                                                   # the pointer on the + itself still shows it in full
        page.wait_for_timeout(300)
        assert page.evaluate(OP) == 1
    finally:
        page.context.close()


def test_a_touch_screen_has_no_hover_hint(browser, site):
    """A tap on a sub-chip opens its page (the + is hidden there), so touch gets no hint; the shut + stays in sight and the bar's choice is the same."""
    url, key = site
    seed = "localStorage.setItem(%s,JSON.stringify({v:'off',t:Date.now()}));" % json.dumps(key + "-chips")
    page = _open(browser, url, "classic", touch=True, seed=seed)
    try:
        assert _is_off(page)
        c = _sub(page)
        assert c
        page.touchscreen.tap(c["x"], c["y"])
        page.wait_for_timeout(300)
        assert not page.evaluate("document.documentElement.classList.contains('ct-hint')")
    finally:
        page.context.close()
