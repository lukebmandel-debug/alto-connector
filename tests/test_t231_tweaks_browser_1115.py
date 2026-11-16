"""v1.9.232 small fixes in a real WebKit (headless, offline, silent): phone corner buttons, the terms-denied dialog. Skips when Playwright is missing."""
import http.server
import json
import socketserver
import threading
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
from alto.build import pages   # noqa: E402

HOME = [{"name": "Law", "pid": "p", "courses": [{"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e"]}]}]


@pytest.fixture(scope="module")
def webkit():
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    d = tmp_path_factory.mktemp("t231")
    (d / "t.html").write_text("<html><body>t</body></html>")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    (d / "blank.html").write_text("<!doctype html><html><body></body></html>", encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


CORNERS = """()=>{if(!document.getElementById('bin-btn')){const b=document.createElement('button');b.id='bin-btn';document.body.appendChild(b)}
  const o={};for(const id of ['account-btn','search-btn','info-btn','mode-toggle','bin-btn','bg-toggle']){const e=document.getElementById(id);if(!e)continue;const r=e.getBoundingClientRect();o[id]=[r.x,r.y,r.width,r.height]}return o}"""


@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_corner_buttons_are_44_pt_and_never_overlap(webkit, site, size):
    ctx = webkit.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.goto(site + "/h.html", wait_until="load")
    pg.wait_for_timeout(3000)
    r = pg.evaluate(CORNERS)
    ctx.close()
    assert ("bg-toggle" in r) or size[0] > 640
    for k in ("account-btn", "search-btn", "info-btn", "bin-btn") + (("bg-toggle",) if size[0] <= 640 else ()):
        assert r[k][2] >= 43.9 and r[k][3] >= 43.9, (k, r[k])                 # 44 pt on the screen
    ids = [k for k in r if k != 'bg-toggle' or size[0] <= 640]
    for i, a in enumerate(ids):
        x, y, w, h = r[a]
        assert x >= 0 and y >= 0 and x + w <= size[0] and y + h <= size[1], (a, r[a])
        for b in ids[i + 1:]:
            x2, y2, w2, h2 = r[b]
            assert x + w <= x2 + .01 or x2 + w2 <= x + .01 or y + h <= y2 + .01 or y2 + h2 <= y + .01, ("overlap", a, b, r[a], r[b])


def test_terms_permission_denied_shows_invite_only_and_a_sign_out(webkit, site):
    js = (ROOT / "alto/cloud/alto-cloud.js").read_text("utf-8")
    a, b = js.index("  const TERMS_V ="), js.index("  onAuthStateChanged(auth,")
    body = js[a:b].replace("__ALTO_TERMS_V__", "v1")
    harness = ("(async()=>{const db={},auth={},cloud={};let termsTicked=false,_signedOut=0;const _signOut=async()=>{_signedOut++;};"
               "const doc=()=>({}),serverTimestamp=()=>0;let MODE='denied';"
               "const setDoc=async()=>{const e=new Error('x');e.code=MODE==='denied'?'permission-denied':'unavailable';throw e;};"
               "const getDoc=async()=>({exists:()=>false});" + body +
               "window._h={termsDialog,out:()=>({msg:document.getElementById('alto-terms-msg').textContent,"
               "box:getComputedStyle(document.querySelector('.acct-terms')).display,go:getComputedStyle(document.getElementById('alto-terms-go')).display,"
               "no:document.getElementById('alto-terms-no').textContent,so:_signedOut}),setMode:m=>{MODE=m}};})()")
    ctx = webkit.new_context(viewport={"width": 390, "height": 700})
    pg = ctx.new_page()
    pg.goto(site + "/blank.html")
    pg.evaluate(harness)
    pg.evaluate("()=>{window._h.termsDialog({uid:'u1'});const ok=document.getElementById('alto-terms-ok');ok.checked=true;ok.dispatchEvent(new Event('change'));document.getElementById('alto-terms-go').click()}")
    pg.wait_for_function("()=>window._h.out().msg.includes('invite-only')")
    o = pg.evaluate("()=>window._h.out()")
    assert o["msg"] == "This feature is invite-only during the beta, and this account isn't on the list."
    assert o["box"] == "none" and o["go"] == "none" and o["no"] == "Sign out"
    pg.click("#alto-terms-no")
    # any other failure keeps the old message and the box
    pg.evaluate("()=>{window._h.setMode('other');document.getElementById('alto-terms-scrim')&&document.getElementById('alto-terms-scrim').remove();window._h.termsDialog({uid:'u1'});"
                "const ok=document.getElementById('alto-terms-ok');ok.checked=true;ok.dispatchEvent(new Event('change'));document.getElementById('alto-terms-go').click()}")
    pg.wait_for_function("()=>window._h.out().msg.includes('try again')")
    o = pg.evaluate("()=>window._h.out()")
    assert o["box"] != "none" and o["go"] != "none"
    ctx.close()
