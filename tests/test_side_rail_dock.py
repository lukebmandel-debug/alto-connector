"""The right-side rail (sparkle, Notes, filter, background) is docked on the bottom-right toggle row, not floating mid-page
(Luke 2026-11-20: "you see the right side toggles are incorrectly free floating"; Lanes and the world map, shared chrome).

It stands on the row's top, level with the toggle row's right end (within 2px) at d1440 and d2000, all corners rounded, glyphs centred, on an opaque backing so no line or map shows
through it, and the desktop minimap clears it. The browser tests are skipped without Playwright's browsers."""
import copy
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import filter_panel, minimap_home, palace_assets, world_plan as wp  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except Exception:  # pragma: no cover
    pw = None


def _lanes():
    return build_timeline(*load_brief(json.load(open(ROOT / "samples" / "lanes_v2_brief.json"))))[0]


def _world():
    d = json.load(open(ROOT / "samples" / "outline_brief.json"))
    d["brief"].update({"mode": "palace", "palace_view": "world"})
    ids = [n["id"] for n in d["nodes"] if n.get("parent")][:2]
    d["brief"]["world"] = {"places": {ids[0]: wp.resolve("France"), ids[1]: wp.resolve("Peru")}}
    return build_timeline(*load_brief(d))[0]


def test_the_rail_stands_on_the_right_edge_as_on_1_9_281():   # Luke 2026-11-23: "put them back where they were"
    css = filter_panel.RAIL_CSS
    assert "top:calc(50% - 32px)" in css and "html.mobile #account-btn{display:none !important;}" in css
    assert "bottom:calc(var(--alto-row-b,24px) + 43px)" not in css


def test_the_minimap_row_no_longer_counts_the_rail():
    assert "R[1]=Math.min(R[1],q.top)" not in minimap_home.MM_HOME_JS


@pytest.fixture(scope="module")
def origin():
    pages = {"lanes": _lanes(), "world": _world()}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            k = p.strip("/").split(".")[0]
            hit = ("text/html", pages[k]) if k in pages else ("text/javascript", "") if p == "/alto-cloud.js" else palace_assets.find(p)
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
    try:
        b.close()
        p.stop()
    except Exception:
        pass


PROBE = """() => { const r = document.getElementById('tab-rail'), b = r.getBoundingClientRect(), s = getComputedStyle(r), z = parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  const rowEls = ['search-btn', 'info-btn', 'alto-edit-pill'].map(i => document.getElementById(i)).filter(e => e && e.getBoundingClientRect().width > 2), row = rowEls.map(e => e.getBoundingClientRect().top), rowRight = Math.min.apply(null, rowEls.map(e => innerWidth - e.getBoundingClientRect().right));
  const mid = [b.left + b.width / 2, b.top + b.height / 2], hit = document.elementFromPoint(mid[0], b.top + 1 + (b.height - 2) / 2);
  const bt = Array.from(r.children), rad = bt.map(x => { const c = getComputedStyle(x); return [c.borderTopLeftRadius, c.borderTopRightRadius, c.borderBottomRightRadius, c.borderBottomLeftRadius]; }),
    off = bt.map(x => { const q = x.getBoundingClientRect(); let g = x.querySelector('svg,img'); const rg = document.createRange(); if (g) { var c = g.getBoundingClientRect(); } else { rg.selectNodeContents(x); c = rg.getBoundingClientRect(); }
      return Math.max(Math.abs((c.left + c.right) / 2 - (q.left + q.right) / 2), Math.abs((c.top + c.bottom) / 2 - (q.top + q.bottom) / 2)); });
  const bd = bt.map(x => { const c = getComputedStyle(x); return [c.borderRightStyle, c.borderRightWidth, c.borderRightColor, c.borderLeftStyle, c.borderLeftWidth, c.borderLeftColor]; });
  return {bd, rad, off, rowRight, right: innerWidth - b.right, bottom: b.bottom, rowTop: Math.min.apply(null, row), top: b.top, h: innerHeight, bg: s.backgroundColor, onTopOfPage: !!(hit && r.contains(hit)), n: r.children.length, z}; }"""


@pytest.mark.parametrize("fmt", ["lanes", "world"])
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(1440, 900), (2000, 1250)])
def test_the_rail_is_docked_level_with_the_row_on_an_opaque_backing(browser, origin, fmt, style, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"{origin}/{fmt}.html")
    pg.wait_for_timeout(2000)
    pg.evaluate("document.documentElement.classList.add('dark')")
    pg.evaluate("window._altoStyle && window._altoStyle.set(%r)" % style)
    pg.wait_for_timeout(1200)
    r = pg.evaluate(PROBE)
    ctx.close()
    assert not errs, errs
    assert r["n"] >= 3
    assert abs(r["right"] - r["rowRight"]) <= 2, r               # its right edge is the toggle row's right edge
    for q in r["rad"]:
        assert len(set(q)) == 1 and (style == "retro" or float(q[0][:-2]) > 0), r      # all four corners alike (Retro is square by design; the others round)
    for q in r["bd"]:
        assert q[:3] == q[3:], r                                 # no leftover edge-tab stroke: border-right equals border-left
    assert max(r["off"]) <= 2, r                                 # glyphs and the vertical Notes sit centred in their buttons
    assert r["bottom"] <= r["rowTop"] + 0.5 and r["rowTop"] - r["bottom"] < 20, r   # standing on the toggle row, not mid-page
    assert r["top"] > r["h"] * 0.5, r
    m = r["bg"].replace(" ", "")
    assert m.startswith("rgb(") or m.endswith(",1)"), r         # opaque: no line or map shows through
