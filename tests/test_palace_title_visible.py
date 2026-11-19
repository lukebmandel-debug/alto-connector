"""Board B-1119-SHOTS245-COND: the page's title was missing from the top centre of the world map in Retro (retro.py hid #title-text for the cartouche the
palace pages never draw). The title is visible (non-empty, on screen, not covered) in every style at d1440 and p390 on the world map and the Blueprint,
and it never meets the cartouche (#sk-mark) where one is drawn. Chromium and WebKit; the style by the page's own switch, then a reload."""
import http.server
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace_assets, world_plan as wp  # noqa: E402
from tests.test_world_palace import built  # noqa: E402
from test_building_pma_render import PLAN, _html as blueprint_html  # noqa: E402
from alto.build import building_schema as bs  # noqa: E402
import test_palace as tp  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
import copy  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
READY = {"world": "window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", "blueprint": "document.documentElement.classList.contains('bldg-open') && document.querySelector('#bldg-root .bl-room')", "city": "document.querySelector('#title-text')"}
TITLE = {"world": "civ pro", "blueprint": "walk", "city": "test palace"}


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def pages():
    return {"world": built(world={"places": {"erie": wp.resolve("Peru")}})[0], "blueprint": blueprint_html(),
            "city": build_timeline(*load_brief(copy.deepcopy(tp.bundle())))[0]}


def _serve(html, plans=None):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path, building_plans=plans))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


FIND = """(want) => { var vw = innerWidth, vh = innerHeight, cands = [...document.querySelectorAll('#title-text, span.title, #sk-mark')].filter(e => (e.textContent || '').trim().toLowerCase() === want), out = null;
  cands.forEach(e => { var r = e.getBoundingClientRect(), c = getComputedStyle(e); if (r.width < 4 || r.height < 4 || c.visibility !== 'visible' || c.display === 'none' || +c.opacity < .5) return;
    var x = (r.left + r.right) / 2, y = (r.top + r.bottom) / 2, hit = document.elementFromPoint(x, y);
    out = out || {isMark: e.id === 'sk-mark', text: e.textContent.trim(), rect: [r.left, r.top, r.right, r.bottom], on: r.left >= 0 && r.right <= vw && r.top >= 0 && r.bottom <= vh, covered: e.id !== 'sk-mark' && !(hit && (e === hit || e.contains(hit) || hit.contains(e))),   /* (the cartouche takes no touch, so a hit test sees through it) */ hit: hit && (hit.id || hit.className)}; });
  var k = document.getElementById('sk-mark'), kr = k && k.getBoundingClientRect(), mark = kr && kr.width > 1 && getComputedStyle(k).display !== 'none' ? [kr.left, kr.top, kr.right, kr.bottom] : null;
  return {title: out, mark: mark, cands: cands.length}; }"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", ["d1440", "p390"])
@pytest.mark.parametrize("kind", ["world", "blueprint", "city"])
def test_the_page_title_is_visible_clear_of_the_cartouche(browser, pages, kind, size, style):
    if kind == "city" and size == "p390":
        pytest.skip("the Memory Map is full-screen on a phone by design (Apple-Maps feel): its header, title included, is under the map there")
    srv = _serve(pages[kind], dict([bs.hosted_json(PLAN)]) if kind == "blueprint" else None)
    o = f"http://127.0.0.1:{srv.server_address[1]}"
    vp, mob = ({"width": 1440, "height": 900}, False) if size == "d1440" else ({"width": 390, "height": 844}, True)
    cx = browser.new_context(viewport=vp, **({"is_mobile": True, "has_touch": True, "user_agent": UA} if mob else {}))
    page = cx.new_page()
    try:
        page.goto(o + "/index.html")
        page.wait_for_function(READY[kind], timeout=20000)
        if style != "classic":
            page.evaluate("(s) => (window._altoStyle || window._altoStyleC).set(s)", style)
            page.reload()
            page.wait_for_function(READY[kind], timeout=20000)
        page.wait_for_timeout(2500)
        r = page.evaluate(FIND, TITLE[kind])
        t = r["title"]
        assert t and t["text"] and t["on"] and not t["covered"], r                                  # non-empty, on screen, not covered
        if r["mark"] and not t["isMark"]:                                                                              # and clear of the cartouche, where one is drawn
            m, q = r["mark"], t["rect"]
            assert q[2] <= m[0] or q[0] >= m[2] or q[3] <= m[1] or q[1] >= m[3], r
    finally:
        cx.close()
        srv.shutdown()
