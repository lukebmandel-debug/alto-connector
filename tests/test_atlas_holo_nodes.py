"""The Memory Atlas's nodes in Holographic and Retro (Luke, 2026-11-04: "Somehow the holo style didn't make it to nodes, fix it"): the map's pins, the
card a pin enlarges with its authority chips, and the unit labels wear the same Holographic look as the other formats' cards (a square glass plate, the
edge glow, the Holo type, the token inks), flat and on the globe, in both themes; Retro's own look reaches the same nodes. Computed styles in WebKit.

Skipped without Playwright. Served from 127.0.0.1 like test_world_palace_render.py. A WebKit page.close() can hang at teardown, so a page is never
closed on its own (its context lives to the end of the run) and the browser's own close is given 15 s by an alarm, then left behind."""
import http.server
import json
import signal
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import holo, palace_assets, world_plan as wp  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _rgb(h):
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def test_the_holo_sheet_says_the_boards_card_rules_again_for_the_enlarged_atlas_card():
    c = holo.css()
    for sel in ("#wpal-root .wp-enl .node-card", "#wpal-root .wp-enl .node-footer", "#wpal-root .wp-enl .node-title", "#wpal-root .wp-enl .node.focused .node-card"):
        assert "html.alto-holo " + sel in c, sel
    assert "html.alto-holo #wpal-root .wp-pin" in c and "html.alto-holo #wpal-root .wp-tag" in c
    assert "#wpal-root .wp-enl .node[data-solar]" not in c and "phase" not in holo.atlas_cards(holo.ink(holo.HOLO_CSS)).split("{")[0]


def _page():
    d = json.load(open(ROOT / "samples" / "outline_brief.json"))
    d["brief"].update({"mode": "palace", "palace_view": "world"})
    d["brief"]["world"] = {"places": {d["nodes"][0]["id"]: wp.resolve("Mali")}}
    return build_timeline(*load_brief(d))[0], d["nodes"][0]["id"]


@pytest.fixture(scope="module")
def origin():
    html, _ = _page()

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    p = pw.sync_playwright().start()
    try:
        b = p.webkit.launch()
    except Exception as e:
        p.stop()
        pytest.skip(f"no webkit: {e}")
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


PROBE = """() => { const q = s => document.querySelector(s);
  const cs = (e, ps) => { if (!e) return null; const c = getComputedStyle(e), o = {}; ps.forEach(p => o[p] = c[p]); return o; };
  const P = ['backgroundColor', 'color', 'borderTopLeftRadius', 'borderTopColor', 'borderTopWidth', 'boxShadow', 'fontFamily', 'textTransform'];
  return {pin: cs(q('#wpal-root .wp-pin.n:not(.wp-hint):not(.wp-on)'), P), tag: cs(q('#wpal-root .wp-tag'), P), card: cs(q('#wpal-root .wp-enl .node-card'), P),
          chip: cs(q('#wpal-root .wp-enl .node-footer .esym-btn'), P), unit: cs(q('#wpal-root .wp-enl .node-unit'), P), tt: cs(q('#wpal-root .wp-row .wp-tt'), P)}; }"""


def _look(browser, origin, style, dark, globe, size=(1400, 900)):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 500, is_mobile=size[0] < 500)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(origin + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
    tog = "document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false")
    page.evaluate(tog)
    page.evaluate("window._altoStyle.set(%r)" % style)
    page.wait_for_timeout(600)
    page.evaluate(tog)
    if globe:
        page.evaluate("AltoWorld.globe(true)")
    page.evaluate("AltoWorld.select(%r)" % _page()[1])
    page.wait_for_timeout(2500)
    out = page.evaluate(PROBE)
    out["errors"] = errors
    return out


@pytest.mark.parametrize("globe", [False, True])
@pytest.mark.parametrize("dark", [True, False])
def test_holo_reaches_the_pins_the_enlarged_card_its_chips_and_the_unit_labels(browser, origin, dark, globe):
    t = holo.TOKENS["dark" if dark else "light"]
    r = _look(browser, origin, "holo", dark, globe)
    assert not r["errors"], r["errors"]
    for k in ("pin", "tag", "card", "chip", "unit"):
        assert r[k], k
    # the pin: a square plate, rimmed and glowing, in the cards' type
    assert r["pin"]["borderTopLeftRadius"] == "0px" and r["pin"]["borderTopWidth"] == "1px" and r["pin"]["boxShadow"] != "none"
    assert "Georgia" in r["pin"]["fontFamily"] and r["pin"]["backgroundColor"] == _rgb(t["sf"])
    # the unit label: square, glowing, spaced capitals
    assert r["tag"]["borderTopLeftRadius"] == "0px" and r["tag"]["boxShadow"] != "none" and r["tag"]["textTransform"] == "uppercase"
    assert r["tag"]["backgroundColor"] == _rgb(t["bg"]) and r["tag"]["color"] == _rgb(t["tx"])
    # the Start Tour pill (Art 2026-11-05): the page's dark ink on the cyan plate, square, 4.5:1 or better
    assert r["tt"] and r["tt"]["color"] == _rgb(t["bg"]) and r["tt"]["borderTopLeftRadius"] == "0px", r["tt"]
    # the enlarged card: the board's Holo card (the glass plate, the cyan rim, the glow), not the engine's rounded dark glass
    assert r["card"]["backgroundColor"] == _rgb(t["sf"]) and r["card"]["borderTopLeftRadius"] == "0px" and r["card"]["borderTopWidth"] == "1px"
    assert t["rgb"].replace(",", ", ") in r["card"]["boxShadow"]
    assert r["card"]["color"] == _rgb(t["tx"])
    # its authority chips: a square plate, the rim and the light's ink; the unit numeral in the controls' ink
    assert r["chip"]["borderTopLeftRadius"] == "0px" and r["chip"]["backgroundColor"] == _rgb(t["bg"]) and r["chip"]["color"] == _rgb(t["ac"])
    assert r["unit"]["color"] == _rgb(t["ac2"])


@pytest.mark.parametrize("globe", [False, True])
def test_retro_reaches_the_same_nodes(browser, origin, globe):
    r = _look(browser, origin, "retro", True, globe)
    assert not r["errors"], r["errors"]
    assert r["card"]["backgroundColor"] == "rgb(5, 7, 11)" and r["card"]["borderTopLeftRadius"] == "2px"       # Retro's plate, not the engine's glass
    assert r["chip"]["color"] == "rgb(217, 174, 85)" and r["chip"]["borderTopLeftRadius"] == "0px"              # its gold chips
    assert r["tag"]["borderTopLeftRadius"] == "0px" and r["tag"]["backgroundColor"] == "rgb(0, 0, 0)"            # the unit label
    assert r["pin"]["backgroundColor"] == "rgb(5, 7, 11)" and r["pin"]["boxShadow"] == "none"                   # the pin


def test_classic_is_untouched(browser, origin):
    r = _look(browser, origin, "classic", True, False)
    assert r["card"]["borderTopLeftRadius"] == "14px" and r["pin"]["borderTopLeftRadius"] == "999px"


def test_the_start_tour_pill_wears_the_pages_dark_ink_square_in_holographic():
    """Art, 2026-11-05: white on the cyan plate was 1.41:1 (a blank block). The pill takes --ho-bg, square, and that pair reads 4.5:1 in both themes."""
    c = holo.css()
    assert "#wpal-root .wp-row .wp-tt" in c and "color:var(--ho-bg) !important;border-radius:0" in c
    for mode in ("dark", "light"):
        t = holo.TOKENS[mode]
        assert holo.contrast(t["bg"], t["ac"]) >= 4.5, mode
