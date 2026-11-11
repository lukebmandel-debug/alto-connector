"""The Memory Atlas Tour wears the country's flag (Luke, 2026-11-05, item 9: "the background of the country be its flag when zoomed in on the tour within that
country"; Art's tour-flag-fill B + C and holo-flag-anim C): while the Tour stands in a country the flag is laid over its unit colour at about a third, plain while
the camera flies, faded in ~300 ms after it settles, faded out when the Tour leaves the country. Holographic holds the fill still under a 7 s scan line with a
magenta ghost drifting in step with the card flag's turn; a phone and reduced motion keep the still look. The flag is the card's own hosted file (nothing more
is fetched). The data tests need no browser; the browser tests are WebKit and Chromium (a page is never closed on its own; the browser's close gets 15 s by an alarm)."""
import http.server
import re
import signal
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace_assets, palace_world, world_plan as wp  # noqa: E402
from tests.test_world_palace import built  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

HAND = {"pj": wp.resolve("France"), "pj1": wp.resolve("Texas"), "ms": wp.resolve("Libya")}


def test_the_looks_live_in_the_hosted_script_not_the_page():
    html = built(world={"places": HAND})[0]
    assert "wp-ff" not in html and "wpff-" not in html and "ffShow" not in html
    js = palace_world.WORLD_ASSET
    assert "function ffShow" in js and "wp-ff-drift" in js and "wp-ff-scan" in js and "wp-gflag" in js


def test_holo_motion_is_computers_only_and_off_under_reduced_motion():
    css = palace_world.WORLD_CSS
    i = css.index("@media (min-width:701px) and (prefers-reduced-motion:no-preference){")
    block = css[i:css.index("@keyframes wp-ff-scan")]
    assert "wp-ff-drift 10s linear infinite" in block and "wp-ff-scan 7s linear infinite" in block
    assert "animation" not in css[:i].split("the Tour's flag fill")[-1]                 # (no motion rule outside that query)
    assert "transform-box:fill-box" in block and not re.search(r"\b(left|top|width|height)\s*:\s*[^;]*;\s*}?\s*animation", block)


@pytest.fixture(scope="module")
def origin():
    html = built(world={"places": HAND})[0]
    log = []

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            log.append(path)
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", log
    srv.shutdown()


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    p = pw.sync_playwright().start()
    try:
        b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
    except Exception as e:
        p.stop()
        pytest.skip(f"no {request.param}: {e}")
    yield b
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("browser close hung")))
    signal.alarm(15)
    try:
        b.close()
        p.stop()
    except Exception:
        pass
    finally:
        signal.alarm(0)


FILL = """() => { const g = document.querySelector('#wpal-root .wp-ff'); if (!g) return null; const cs = e => e ? getComputedStyle(e) : null, a = g.querySelector('.ff-a'),
  gh = g.querySelector('.ff-g'), sc = g.querySelector('.ff-s'), pth = document.querySelector('#wpff-c path');
  return {on: g.classList.contains('on'), op: +cs(g).opacity, vis: cs(g).visibility, href: a.getAttribute('href'), aop: +cs(g.querySelector('.ff-m')).opacity, clip: pth ? pth.getAttribute('d').length : 0,
    ghost: cs(gh).display, ganim: cs(gh).animationName, gdur: cs(gh).animationDuration, scan: cs(sc).display, sanim: cs(sc).animationName, sdur: cs(sc).animationDuration,
    gstate: gh.getAnimations ? gh.getAnimations().map(x => x.animationName) : null, w: +a.getAttribute('width'), h: +sc.getAttribute('height'), fh: +a.getAttribute('height'), fw: +a.getAttribute('width'), bw: +sc.getAttribute('width')}; }"""


def _open(browser, base, style="classic", size=(1400, 900), reduced=False, globe=False):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 500, is_mobile=size[0] < 500,
                              reduced_motion="reduce" if reduced else "no-preference")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    page.evaluate("document.documentElement.classList.add('dark')")
    page.evaluate("window._altoStyle.set(%r)" % style)
    page.wait_for_timeout(600)
    if globe and not page.evaluate("AltoWorld.globe(true)"):
        pytest.skip("no WebGL here")
    if globe:
        page.wait_for_timeout(1500)                                              # (the world fly that turning the globe on makes: a stop must not meet it)
    assert page.evaluate("AltoWorld.tourMode()")                               # (the Tour is on by default; turning it on here would start a flight)
    return page, errors


def _stop(page, id_="pj", instant=False):
    page.evaluate("AltoWorld.select(%r%s)" % (id_, ", {instant: true}" if instant else ""))


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_plain_while_flying_then_fades_in_after_it_settles_then_out_on_leaving(browser, origin, style):
    base, log = origin
    log.clear()
    page, errors = _open(browser, base, style)
    _stop(page)
    page.wait_for_timeout(150)
    f = page.evaluate(FILL)
    assert f is None or not f["on"]                                              # (flying: nothing)
    page.wait_for_function("(() => { var g = document.querySelector('#wpal-root .wp-ff'); return g && g.classList.contains('on'); })()", timeout=8000)
    page.wait_for_timeout(900)
    r = page.evaluate(FILL)
    assert not errors, errors
    assert r["on"] and r["op"] > .95 and r["vis"] == "visible" and r["href"].startswith("/world/flag-FRA-") and r["clip"] > 100 and .3 <= r["aop"] <= .36 and r["w"] > 5
    assert any(f.startswith("/world/flag-FRA-") for f in log) and not any(f.startswith("/world/flag-USA-") for f in log)       # (the card's own file; no other country's)
    if style == "holo":
        offs = page.evaluate("[].map.call(document.querySelectorAll('#wpff-s stop'), s => +s.getAttribute('offset'))")        # (the scan line is ~14 px, whatever the country's size)
        k = page.evaluate("+/scale\\(([\\d.]+)\\)/.exec(document.querySelector('#wpal-root svg.wp-svg > g').getAttribute('transform'))[1]")
        assert offs[0] == 0 and offs[1] < offs[2] < offs[3] == 1 and abs((1 - offs[1]) * r["h"] * k - 14) < .5
        assert r["ghost"] == "inline" and r["ganim"] == "wp-ff-drift" and r["gdur"] == "10s" and r["scan"] == "inline" and r["sanim"] == "wp-ff-scan" and r["sdur"] == "7s"
        assert page.evaluate("document.querySelectorAll('#wpal-root .wp-enl .fl-spin').length") == 0 and page.evaluate("document.querySelector('#wpal-root .wp-ff .ff-g').getAnimations()[0].playState") == 'running'      # (the card's flag no longer turns: the ghost drifts on its own)
    else:
        assert r["ghost"] == "none" and r["scan"] == "none" and r["ganim"] == "none"
    page.evaluate("AltoWorld.tourMode(false)")                                   # leaving: fades out
    page.wait_for_timeout(700)
    r2 = page.evaluate(FILL)
    assert not r2["on"] and r2["vis"] == "hidden" and r2["op"] == 0


def test_a_hop_inside_one_country_keeps_it_and_a_hop_to_another_drops_and_refills(browser, origin):
    page, errors = _open(browser, origin[0])
    _stop(page, "pj", True)
    page.wait_for_function("document.querySelector('#wpal-root .wp-ff.on')", timeout=8000)
    page.evaluate("AltoWorld.select('pj2')")                                     # a card of the cluster that is open: no flight
    page.wait_for_timeout(500)
    assert page.evaluate(FILL)["on"]
    page.evaluate("AltoWorld.select('pj1')")                                     # the US
    page.wait_for_timeout(120)
    assert not page.evaluate(FILL)["on"]                                         # (plain while it flies)
    page.wait_for_function("document.querySelector('#wpal-root .wp-ff.on')", timeout=8000)
    page.wait_for_timeout(700)
    r = page.evaluate(FILL)
    assert r["href"].startswith("/world/flag-USA-") and r["op"] > .95 and not errors


def test_free_roaming_never_gets_the_fill(browser, origin):
    page, errors = _open(browser, origin[0])
    page.evaluate("AltoWorld.tourMode(false)")
    _stop(page, "pj", True)
    page.wait_for_timeout(1200)
    assert page.evaluate("document.querySelector('#wpal-root .wp-ff.on')") is None and not errors


def test_reduced_motion_holo_is_still_and_does_not_fade(browser, origin):
    page, errors = _open(browser, origin[0], "holo", reduced=True)
    _stop(page, "pj", True)
    page.wait_for_function("document.querySelector('#wpal-root .wp-ff.on')", timeout=8000)
    r = page.evaluate(FILL)
    assert r["ghost"] == "none" and r["scan"] == "none" and r["ganim"] == "none" and r["gstate"] == [] and r["op"] == 1 and not errors


@pytest.mark.parametrize("style", ["classic", "holo"])
def test_a_phone_gets_the_tint_and_the_fade_but_no_holo_motion(browser, origin, style):
    page, errors = _open(browser, origin[0], style, size=(390, 844))
    _stop(page, "pj")
    page.wait_for_function("document.querySelector('#wpal-root .wp-ff.on')", timeout=8000)
    page.wait_for_timeout(900)
    r = page.evaluate(FILL)
    assert r["on"] and r["op"] > .95 and .3 <= r["aop"] <= .36 and r["ghost"] == "none" and r["scan"] == "none" and r["ganim"] == "none" and not errors


@pytest.mark.parametrize("style", ["classic", "holo"])
def test_the_globe_lays_the_same_flag_on_its_own_canvas(browser, origin, style):
    page, errors = _open(browser, origin[0], style, globe=True)
    _stop(page, "pj")
    page.wait_for_function("document.querySelector('#wpal-root canvas.wp-gflag.on')", timeout=8000)
    page.wait_for_timeout(900)
    px = page.evaluate("""() => { const c = document.querySelector('#wpal-root canvas.wp-gflag'), x = c.getContext('2d'), d = x.getImageData(0, 0, c.width, c.height).data; let n = 0, r = 0, b = 0;
      for (let i = 0; i < d.length; i += 4 * 97) if (d[i + 3] > 20) { n++; r += d[i]; b += d[i + 2]; } return {n, r, b, disp: getComputedStyle(c).display, op: +getComputedStyle(c).opacity}; }""")
    assert not errors and px["disp"] != "none" and px["n"] > 50 and px["op"] > .95


# Luke 2026-11-05 (L-1105-184206): "When the country is taller than the flag, just extend the top/bottom colors to fill in the whole country. Vice versa if too wide."
COVER = """() => { const g = document.querySelector('#wpal-root .wp-ff'), m = g.querySelector('.ff-m'), fl = m.querySelector('.ff-a'), pth = document.querySelector('#wpff-c path');
  const box = e => [+e.getAttribute('x'), +e.getAttribute('y'), +e.getAttribute('x') + +e.getAttribute('width'), +e.getAttribute('y') + +e.getAttribute('height')];
  const boxes = [...m.children].map(box), f = box(fl), bb = pth.getBBox(), svg = pth.ownerSVGElement; let inside = 0, miss = 0, outside = 0;
  for (let i = 0; i <= 160; i++) for (let j = 0; j <= 160; j++) { const p = svg.createSVGPoint(); p.x = bb.x + bb.width * i / 160; p.y = bb.y + bb.height * j / 160;
    if (!pth.isPointInFill(p)) continue; inside++; if (p.x < f[0] || p.x > f[2] || p.y < f[1] || p.y > f[3]) outside++;
    if (!boxes.some(b => p.x >= b[0] && p.x <= b[2] && p.y >= b[1] && p.y <= b[3])) miss++; }
  const r = fl.getAttribute('width') / fl.getAttribute('height');
  return {inside, outside, miss, ratio: r, kids: m.children.length, strips: [...m.querySelectorAll('image:not(.ff-a)')].map(i => (i.getAttribute('href') || '').slice(0, 14)), par: fl.getAttribute('preserveAspectRatio')}; }"""


@pytest.mark.parametrize("style", ["classic", "holo"])
@pytest.mark.parametrize("stop", ["pj", "ms"])
def test_the_flag_is_whole_and_unstretched_and_its_edges_fill_every_part_of_the_country(browser, origin, stop, style):
    """France (a tall country, vertical stripes) and Libya (horizontal stripes): the flag is drawn at 4:3, not sliced; its four edges run out as strips and its four corners as
    solid colours, so every point of the country is covered, and some of those points lie outside the flag's own box (the extension is really used)."""
    base, log = origin
    page, errors = _open(browser, base, style)
    _stop(page, stop, True)
    page.wait_for_function("(() => { var g = document.querySelector('#wpal-root .wp-ff'); return g && g.classList.contains('on') && g.querySelectorAll('.ff-m image:not(.ff-a)').length === 4; })()", timeout=10000)
    c = page.evaluate(COVER)
    assert not errors, errors
    assert c["inside"] > 100 and c["miss"] == 0 and c["outside"] > 0, c
    assert abs(c["ratio"] - 4 / 3) < 0.01 and c["par"] == "xMidYMid meet" and c["kids"] == 9 and all(s.startswith("data:image/png") for s in c["strips"]), c


@pytest.mark.parametrize("style", ["classic", "holo"])
def test_the_globe_fill_is_whole_with_its_edges_run_out(browser, origin, style):
    page, errors = _open(browser, origin[0], style, globe=True)
    _stop(page, "ms")
    page.wait_for_function("(() => { var c = document.querySelector('#wpal-root canvas.wp-gflag'); return c && c.classList.contains('on'); })()", timeout=10000)
    page.wait_for_timeout(1500)
    assert not errors, errors
    assert page.evaluate("(() => { var c = document.querySelector('#wpal-root canvas.wp-gflag'); return !!c.fe && c.fe.cv.length === 4 && c.fe.cn.length === 4; })()")
