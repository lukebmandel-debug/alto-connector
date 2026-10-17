"""Run by the QA kit's python (Playwright): a bare page that carries palace_ride.RIDE_LOADER, served next to the real ride file.
Checks (webkit | chromium): the ride file is requested once, synchronously, and window._palRide exists right after the loader (so the code that
follows it can call _palRide.init); with the file answering 404 or aborted the loader leaves _palRide undefined, throws nothing, and the page goes on."""
import http.server
import os
import socketserver
import sys
import threading

sys.path.insert(0, os.environ["ALTO_REPO"])
from alto.build import palace_ride  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

eng = sys.argv[1] if len(sys.argv) > 1 else "webkit"
name, js = palace_ride.ride_asset()
PAGE = ("<!doctype html><html><head><meta charset=utf-8></head><body><div id=canvas></div><script>window.__before=typeof window._palRide;"
        + palace_ride.RIDE_LOADER + "window.__after=typeof window._palRide; window.__ran=true;</script>"
        "<script>window.__next=typeof window._palRide;</script></body></html>")
hits = []
mode = {"serve": True}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/page":
            b = PAGE.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        elif self.path == palace_ride.RIDE_PATH and mode["serve"]:
            hits.append(self.path); b = js.encode()
            self.send_response(200); self.send_header("Content-Type", "text/javascript"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        else:
            if self.path.startswith("/ride/"):
                hits.append(self.path)
            self.send_error(404)


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
fails = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


with sync_playwright() as p:
    b = p.webkit.launch() if eng == "webkit" else p.chromium.launch(channel="chrome")
    for case in ("served", "404", "aborted"):
        mode["serve"] = case == "served"; del hits[:]
        ctx = b.new_context(); pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" and "404" not in m.text and "Failed to load resource" not in m.text else None)
        if case == "aborted":
            ctx.route("**/ride/**", lambda r: r.abort())
        pg.goto(base + "/page"); pg.wait_for_timeout(600)
        r = pg.evaluate("()=>({before:window.__before, after:window.__after, ran:window.__ran, next:window.__next, init:window._palRide&&typeof window._palRide.init, ui:window._palRide&&!!window._palRide.ui})")
        check(r["before"] == "undefined" and r["ran"], case + ": the page script ran to its end")
        if case == "served":
            check(r["after"] == "object" and r["next"] == "object" and r["init"] == "function", "served: _palRide exists right after the loader and for the next script")
            check(hits == [palace_ride.RIDE_PATH], "served: exactly one request, for " + palace_ride.RIDE_PATH + " (%s)" % hits)
            check(r["ui"], "served: the ride's UI part is there")
        else:
            check(r["after"] == "undefined" and r["next"] == "undefined", case + ": _palRide stays undefined")
        check(not errs, case + ": no page errors / console errors %s" % errs)
        ctx.close()
    b.close()
print("RESULT", "FAIL" if fails else "PASS")
sys.exit(1 if fails else 0)
