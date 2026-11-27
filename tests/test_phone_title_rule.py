"""One title rule on a phone (audit B6, B7, B13): in Classic, Retro and Holographic a long page name sits between the clef and the wordmark, never under either
(nor under the Back circle on a detail page), on one line, else two, else an ellipsis, in portrait and on its side. Runs as an iPhone in WebKit."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import palace_assets                      # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

LONG = "The Lighthouse (Child Nodes) And A Very Long Title For The Whole Page"


def _page(name):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"]["title"] = LONG
    return build_timeline(*load_brief(d))[0]


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("Playwright is not installed")
    served = {"/lanes.html": _page("lanes_v2"), "/timeline.html": _page("contracts")}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            hit = (("text/html", served[p]) if p in served else ("text/javascript", "") if p == "/alto-cloud.js" else palace_assets.find(p))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        dev = dict(p.devices["iPhone 13"])
        dev.pop("default_browser_type", None)
        yield b, dev
        b.close()


_RUN = """() => { const t = document.querySelector('#nav .title'), r = t.getBoundingClientRect(),
  c = document.querySelector('#nav .brand-mark').getBoundingClientRect(), w = document.querySelector('#nav .brand-word').getBoundingClientRect();
  const lines = Math.round(r.height / parseFloat(getComputedStyle(t).lineHeight || 16));
  return {l: r.left, r: r.right, clef: c.right, word: w.left, h: r.height, lines, two: t.classList.contains('ttl-2'), clamp: getComputedStyle(t).webkitLineClamp}; }"""


@pytest.mark.parametrize("look", ["classic", "retro", "holo"])
@pytest.mark.parametrize("fmt", ["lanes", "timeline"])
@pytest.mark.parametrize("size", [(390, 844), (375, 667), (844, 390)])
def test_a_long_title_clears_the_clef_and_the_wordmark(browser, site, look, fmt, size):
    b, dev = browser
    ctx = b.new_context(**{**dev, "viewport": {"width": size[0], "height": size[1]}})
    pg = ctx.new_page()
    try:
        pg.goto(f"{site}/{fmt}.html", wait_until="load")
        pg.wait_for_timeout(1200)
        if look != "classic":
            pg.evaluate(f"window._altoStyle.set('{look}')")
            pg.wait_for_timeout(1200)
        r = pg.evaluate(_RUN)
        assert r["l"] >= r["clef"] + 8 and r["r"] <= r["word"] - 8, r
        assert r["lines"] <= 2, r
        if r["two"]:
            assert r["clamp"] == "2", r      # a third line ends in an ellipsis in every look
    finally:
        ctx.close()


@pytest.mark.parametrize("look", ["classic", "retro", "holo"])
def test_on_a_detail_page_the_title_clears_the_back_circle(browser, site, look):
    b, dev = browser
    ctx = b.new_context(**{**dev, "viewport": {"width": 390, "height": 844}})
    pg = ctx.new_page()
    try:
        pg.goto(f"{site}/timeline.html", wait_until="load")
        pg.wait_for_timeout(1200)
        if look != "classic":
            pg.evaluate(f"window._altoStyle.set('{look}')")
            pg.wait_for_timeout(1200)
        pg.evaluate("showDetail('node', document.querySelector('.node').dataset.id)")
        pg.wait_for_timeout(1200)
        assert pg.evaluate("document.documentElement.classList.contains('detail-open')")
        r = pg.evaluate(_RUN)
        back = pg.evaluate("(() => { const e = document.elementFromPoint(66, 26); const r = e && e.closest('button,[role=button],a') ? e.closest('button,[role=button],a').getBoundingClientRect() : null; return r ? r.right : 0; })()")
        assert r["l"] >= max(back, r["clef"]) + 6 and r["r"] <= r["word"] - 8, (r, back)
    finally:
        ctx.close()


def test_holo_title_pill_has_a_solid_backing_on_a_computer_and_a_phone(browser, site):
    """Luke's Torts shot: a card's text passed under the see-through TORTS pill (text on text). The pill's ground is solid now."""
    b, dev = browser
    for kw in (dict(viewport={"width": 1440, "height": 900}), {**dev, "viewport": {"width": 390, "height": 844}}):
        ctx = b.new_context(**kw)
        pg = ctx.new_page()
        try:
            pg.goto(f"{site}/timeline.html", wait_until="load")
            pg.wait_for_timeout(1200)
            pg.evaluate("window._altoStyle.set('holo')")
            pg.wait_for_timeout(1500)
            sel = "#nav .title" if kw.get("is_mobile") else "#title-text"
            alpha = pg.evaluate("(s) => { const c = getComputedStyle(document.querySelector(s)).backgroundColor, m = c.match(/[\\d.]+/g); return m.length > 3 ? +m[3] : 1; }", sel)
            assert alpha == 1, (kw, alpha)
        finally:
            ctx.close()
