"""Manual edit mode happens IN PLACE (Luke, 2026-10-29: "any visual mode like memory atlas should not do this, stay in the mode we are in").

For every format a reader can open — timeline, outline, lanes (horizontal), System in each of its styles, Memory Map (city), Memory Atlas
(world) and Memory Blueprint (building) — the page takes its "format signature" (the html classes that name the look, and which of the
big views are on screen), enters edit mode, takes it again, and the two must match. Leaving edit mode must also give back the first.

Known gaps are listed in XFAIL (format -> why) and each is strict: when one is fixed the test fails until it comes off the list, so the
list only shrinks. Chromium and WebKit (Playwright; skipped without them). A local http server serves the pages and the hosted assets
(the world map, the blueprint's plan); nothing touches the network, Firebase or any ALTO_* setting."""
import copy
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import building_schema as bs, palace_assets  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from test_lanes_fit import _doc as lanes_doc  # noqa: E402
from test_palace import _grid_bundle, load  # noqa: E402
from test_solar_draw import SMALL, SMALL_LINKS, solar_doc  # noqa: E402

# format -> why edit mode still leaves it (each is strict: remove the entry when the format stays put)
XFAIL = {
    "solar:3d": "the 3D Star chart drops to the flat view while editing (solar_3d.py want() needs !alto-editing)",
}

FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""

SIG = """() => { var de = document.documentElement, vis = function(sel){ var e = document.querySelector(sel); if(!e) return false;
    var r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && !e.hidden; };
  return {cls: Array.prototype.slice.call(de.classList).filter(function(c){ return !/^(alto-editing|alto-solar-edit|alto-drag-ok|aed-|navx$|has-filter-tab$|dark$|detail-open$|focus|printing$)/.test(c); }).sort().join(' '),
          vis: ['#canvas', '#wpal-root', '#bldg-root', '#solar-svg', '.pal-svg'].filter(vis).join(' ')}; }"""


def _page_of(doc):
    return build_timeline(*load_brief(copy.deepcopy(doc)))[0]


def _sample(name):
    return json.loads((ROOT / "samples" / f"{name}_brief.json").read_text())


def _pages():
    from test_building_palace_tools import built as bld_built
    from test_world_palace import built as world_built
    return {
        "timeline": _page_of(_sample("contracts")),
        "outline": _page_of(_sample("outline")),
        "lanes": _page_of(lanes_doc()),
        "solar": _page_of(solar_doc(SMALL, "orbit", SMALL_LINKS)),
        "city": build_timeline(*load(_grid_bundle()))[0],
        "atlas": world_built()[0],
        "blueprint": bld_built()[0],
    }


@pytest.fixture(scope="module")
def site():
    pages = _pages()
    pname, ptext = bs.hosted_json(bs.fixture())

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            body, ct = None, "text/html"
            if path.startswith("/p/") and path[3:-5] in pages:
                body = pages[path[3:-5]]
            elif path == "/alto-cloud.js":
                body, ct = "", "text/javascript"
            else:
                hit = palace_assets.find(path, building_plans={pname: ptext})
                if hit:
                    ct, body = hit
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:                                    # noqa: BLE001
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


FORMATS = ["timeline", "outline", "lanes", "city", "atlas", "blueprint", "solar:system", "solar:chart", "solar:retro", "solar:3d"]


@pytest.mark.parametrize("fmt", FORMATS)
def test_entering_edit_stays_in_the_format(browser, site, fmt):
    page_id, _, style = fmt.partition(":")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"{site}/p/{page_id}.html")
    pg.wait_for_timeout(2600)
    if style:
        have = pg.evaluate("window._altoSolarStyles ? window._altoSolarStyles.list() : []")
        if style not in have:
            pytest.skip(f"no {style} style here ({have})")
        pg.evaluate("s => window._altoSolarStyles.set(s)", style)
        pg.wait_for_timeout(1800)
    assert pg.evaluate("!!(window._altoManual && window._altoManual.canEdit && window._altoManual.canEdit())"), "edit mode cannot start here"
    before = pg.evaluate(SIG)
    pg.evaluate("window._altoManual.enter()")
    pg.wait_for_timeout(1800)
    assert pg.evaluate("document.documentElement.classList.contains('alto-editing')")
    during = pg.evaluate(SIG)
    pg.evaluate("window._altoManual.exit && window._altoManual.exit()")
    pg.wait_for_timeout(1500)
    after = pg.evaluate(SIG)
    ctx.close()
    stays = during == before
    if fmt in XFAIL:
        assert not stays, f"{fmt} now stays put — take it off XFAIL: {XFAIL[fmt]}"
        return
    assert stays, f"{fmt}: entering edit changed the format\nbefore {before}\nduring {during}"
    assert after == before, f"{fmt}: leaving edit did not give the format back\nbefore {before}\nafter  {after}"
    assert not errs, errs
