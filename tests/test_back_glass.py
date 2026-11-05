"""The Back strip of a detail page is quiet glass (Luke, 2026-11-05, "6 B"): no colour of its own in Classic, Retro and Holographic; in Holographic a solid
plate that reads on every ground; the arrow on the label's centre line; a phone's floating Back pill and its Back to Overview bar keep their green."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds_import as bi, holo, retro   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

GREEN = ("rgb(47, 93, 58)", "rgb(31, 62, 42)")


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d0 = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d0)
    d = tmp_path_factory.mktemp("bgsite")
    (d / "t.html").write_text(build_timeline(brief, nodes, conns)[0], encoding="utf-8")
    for sub, asset in (("holo", holo.holo_asset()), ("retro", retro.retro_asset())):
        (d / sub).mkdir()
        (d / sub / asset[0]).write_text(asset[1], encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(params=["chromium", "webkit"])
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


IPHONE = dict(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
              is_mobile=True, has_touch=True, device_scale_factor=3)


def _open(browser, site, style, dark=False, size=(1400, 900), hop=True, **kw):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, **kw)
    pg = ctx.new_page()
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(500)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false"))
    if style != "classic":
        pg.evaluate("window._altoStyle.set('%s')" % style)
        pg.wait_for_timeout(500)
    pg.evaluate("showDetail('node', NODE_ORDER[0])")
    pg.wait_for_timeout(800)
    if hop:
        pg.evaluate("document.querySelector('#detail-content .char-chip, #detail-content .hc-arrow').click()")
        pg.wait_for_timeout(800)
    return ctx, pg


def _show_both(pg):
    pg.evaluate("document.getElementById('back-to-overview-bar').removeAttribute('hidden'); document.getElementById('desktop-banner-row').classList.add('active')")
    pg.wait_for_timeout(300)


@pytest.mark.parametrize("style,dark", [("classic", False), ("classic", True), ("retro", True), ("holo", True)])
def test_the_strip_has_no_green_and_wears_the_page_s_ink(browser, site, style, dark):
    ctx, pg = _open(browser, site, style, dark)
    _show_both(pg)
    r = pg.evaluate("""()=>['.dbr-back','.dbr-prev'].map(s=>{const e=document.querySelector('#desktop-banner-row '+s), c=getComputedStyle(e);
      return {s, bg:c.backgroundColor, color:c.color, shown:c.display!=='none', kid:getComputedStyle(e.querySelector('.dbr-lab')).color}})""")
    for e in r:
        assert e["shown"], e
        assert e["bg"] not in GREEN, e
        assert e["kid"] == e["color"] and e["color"] != "rgb(255, 255, 255)" or style != "classic", e
    ctx.close()


def test_holographic_strip_is_a_solid_plate_with_the_lightest_ink_on_every_ground(browser, site):
    ctx, pg = _open(browser, site, "holo", True)
    _show_both(pg)
    for bgid in ("h-neon-rain", "h-amber-haze", "h-grid-horizon", "h-signal-rain", "h-targeting", "h-lightspeed"):
        pg.evaluate("document.querySelector('#bg-toggle').click()")
        pg.wait_for_timeout(200)
        pg.evaluate("document.querySelector('.bg-tile[data-bg=\"%s\"]').click()" % bgid)
        pg.wait_for_timeout(300)
        pg.evaluate("document.querySelector('#bg-toggle').click()")
        r = pg.evaluate("""()=>{const e=document.querySelector('#desktop-banner-row .dbr-prev'), c=getComputedStyle(e), row=getComputedStyle(document.getElementById('desktop-banner-row'));
          return {bg:c.backgroundColor, ink:c.color, shadow:row.boxShadow, bf:c.backdropFilter}}""")
        assert r["bg"] == "rgb(1, 10, 14)", (bgid, r)                  # the page's own black, fully opaque
        assert r["ink"] == "rgb(201, 255, 250)", (bgid, r)             # --ho-tx, 15+:1 on that plate
        assert "rgb(79, 240, 224)" in r["shadow"], (bgid, r)           # the light's full-strength rim
    ctx.close()


@pytest.mark.parametrize("style,dark", [("classic", False), ("classic", True), ("retro", True), ("holo", True)])
def test_the_arrow_sits_on_the_label_s_centre_line(browser, site, style, dark):
    ctx, pg = _open(browser, site, style, dark)
    pg.evaluate("document.querySelector('#desktop-banner-row').scrollIntoView()")
    r = pg.evaluate("""()=>{const e=document.querySelector('#desktop-banner-row .dbr-prev'), a=e.querySelector('.dbr-arr').getBoundingClientRect(), l=e.querySelector('.dbr-lab').getBoundingClientRect();
      return {ac:a.top+a.height/2, lc:l.top+l.height/2, ah:a.height}}""")
    assert abs(r["ac"] - r["lc"]) <= 1.0, r      # (the label's line box centre; the ink is checked in the screenshots)
    ctx.close()


def test_a_phone_keeps_its_floating_pill_and_its_green(browser, site):
    ctx, pg = _open(browser, site, "classic", False, size=(390, 844), **IPHONE)
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    r = pg.evaluate("""()=>{const b=document.getElementById('alto-back-prev'); if(!b) return null; const c=getComputedStyle(b);
      return {bg:c.backgroundColor, pos:c.position, arrow:b.firstElementChild.textContent, inRow:!!b.closest('#desktop-banner-row')}}""")
    if r:                                           # (a hop only exists where a page links to a page)
        assert r["bg"] == "rgb(47, 93, 58)" and r["arrow"] == "←" and not r["inRow"], r
    ctx.close()
