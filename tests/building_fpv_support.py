"""Shared by the first-person view's browser tests: a real local HTTP server (Playwright WebKit does not route the page's synchronous loader
request, so a fake origin is not enough), the browsers, and opening the view on a plan. Not a test module."""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs, palace_assets  # noqa: E402
from alto.build.palace_building_asset import BLUEPRINT_FPV  # noqa: E402

import pytest  # noqa: E402

# The Memory Blueprint's first-person walk is OFF for users (palace_building_asset.BLUEPRINT_FPV; ORG/handbooks/blueprint-fpv.md): its tests wait for the flag, none is deleted.
needs_fpv = pytest.mark.skipif(not BLUEPRINT_FPV, reason="Blueprint FPV is off (palace_building_asset.BLUEPRINT_FPV = False)")

SHOTS = Path("/private/tmp/claude-501/bldg/shots")


class Server:
    """One threaded server per test module: the page, /bldg/<scripts>, and whatever plan is current (every /bldg/plan-*.json answers with it)."""

    def __init__(self):
        self.html, self.plan, self.block = "", "", set()
        srv = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                path = self.path.split("?")[0]
                body, ct, code = b"no", "text/plain", 404
                if any(b in path for b in srv.block):
                    pass
                elif path in ("/", "/index.html"):
                    body, ct, code = srv.html.encode(), "text/html; charset=utf-8", 200
                elif path == "/alto-cloud.js":
                    body, ct, code = b"", "text/javascript", 200
                elif path.startswith("/bldg/plan-"):
                    body, ct, code = srv.plan.encode(), "application/json", 200
                elif path.startswith("/bart/"):
                    from alto.buildings import pma_art
                    for name, data in pma_art.files():
                        if path == "/bart/" + name:
                            body, ct, code = data, "image/jpeg", 200
                elif path.startswith("/gfx/"):
                    from alto.build import fpv_gfx
                    for name, data in fpv_gfx.files():
                        if path == "/gfx/" + name:
                            body, ct, code = data, ("application/wasm" if name.endswith(".wasm") else "text/javascript" if name.endswith(".js") else "application/octet-stream"), 200
                elif path.startswith("/bldg/"):
                    hit = palace_assets.find(path)
                    if hit:
                        body, ct, code = hit[1].encode(), hit[0], 200
                self.send_response(code)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.origin = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def launch(p, which):
    if which == "webkit":
        return p.webkit.launch()
    try:
        return p.chromium.launch()
    except Exception:
        return p.chromium.launch(channel="chrome")


def open_view(browser, srv, html, plan, room=None, ctx=None, width=1280, height=800, enter=True):
    """The built page with `plan` as its hosted plan, walked into (room None: outside, at the main entrance). Returns (page, errors)."""
    srv.html, srv.plan = html, bs.hosted_json(plan)[1]
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)   # the page's own optional files 404 here
    page.goto(srv.origin + "/index.html")
    page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
    if enter:
        page.evaluate("([r, c]) => AltoBuilding.enterFPV(r, c || {from: 'plan'})", [room, ctx])
        page.wait_for_function("window.AltoBuildingFPV && AltoBuildingFPV.state() && AltoBuildingFPV.state().on", timeout=30000)
    return page, errors


def shot(page, name, place=None):
    """Stand somewhere, let everything build, wait for the eye to adapt, and save a screenshot; returns the frame stats."""
    if place:
        page.evaluate("a => AltoBuildingFPV.place(...a)", place)
    page.evaluate("AltoBuildingFPV.settle()")
    page.wait_for_timeout(600)
    st = page.evaluate("AltoBuildingFPV.settle()")
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / (name + ".png")))
    return st


PIXELS = """(() => { AltoBuildingFPV.settle(); const c = document.querySelector('#bf-root canvas'), w = 64, h = 40, t = document.createElement('canvas'); t.width = w; t.height = h;
  const g = t.getContext('2d'); g.drawImage(c, 0, 0, w, h); const d = g.getImageData(0, 0, w, h).data; let s = 0, s2 = 0, n = w * h;
  for (let i = 0; i < d.length; i += 4) { const l = (d[i] * .3 + d[i + 1] * .59 + d[i + 2] * .11) / 255; s += l; s2 += l * l; }
  return {mean: s / n, sd: Math.sqrt(Math.max(0, s2 / n - (s / n) ** 2))}; })()"""
