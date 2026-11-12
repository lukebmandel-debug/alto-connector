"""Holo on a phone: no flat colour strip at the screen edges (Art, holo-home-int-look-1111b). The side panels are parked just off-screen
and their 4px ring + glow used to land inside the edge. WebKit, 402x874 and 874x292, homepage / timeline / detail, light and dark."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import backgrounds_import as bi, holo, pages, phone as _phone, retro   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
HOME = [{"name": "Law", "pid": "p", "courses": [
    {"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e", "#10b981"]}]}]
EDGE = 6


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("holoedge")
    data = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    b, n, c = load_brief(data)
    (d / "t.html").write_text(build_timeline(b, n, c)[0], encoding="utf-8")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    for mod, sub in ((holo, "holo"), (retro, "retro"), (_phone, "phone")):
        nm, tx = (mod.holo_asset if sub == "holo" else mod.retro_asset if sub == "retro" else mod.phone_asset)()
        (d / sub).mkdir()
        (d / sub / nm).write_text(tx, encoding="utf-8")
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


@pytest.fixture(scope="module")
def webkit():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


def _open(webkit, site, url, size, theme):
    ctx = webkit.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=UA)
    pg = ctx.new_page()
    pg.goto(site + url, wait_until="load")
    pg.wait_for_timeout(300)
    pg.evaluate("(t)=>{localStorage.clear(); localStorage.setItem('alto-bg-home-v1-style','holo'); localStorage.setItem('alto-theme-v1',t)}", theme)
    pg.goto(site + url, wait_until="load")
    pg.wait_for_timeout(600)
    pg.evaluate("window._altoStyle && window._altoStyle.set('holo')")
    pg.evaluate("(t)=>document.documentElement.classList.toggle('dark', t==='dark')", theme)
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo')")
    return ctx, pg


def _strip(pg):
    """Longest run, in css px, of columns from each outer edge that are one flat colour from top to bottom (the screenshot's middle 80%)."""
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    w, h = im.size
    s = w / pg.evaluate("innerWidth")
    px = im.load()
    ys = range(int(h * .1), int(h * .9), 3)

    def flat(x):
        col = [px[x, y] for y in ys]
        return all(max(abs(a - b) for a, b in zip(col[0], q)) <= 2 for q in col)

    def run(xs):
        n = 0
        for x in xs:
            if not flat(x):
                break
            n += 1
        return n / s
    return run(range(0, w)), run(range(w - 1, -1, -1))


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("size", [(402, 874), (874, 292)])
@pytest.mark.parametrize("page", ["h.html", "t.html", "detail"])
def test_no_flat_strip_at_the_screen_edges_on_a_holo_phone(webkit, site, page, size, theme):
    ctx, pg = _open(webkit, site, "/h.html" if page == "h.html" else "/t.html", size, theme)
    if page == "detail":
        pg.evaluate("showDetail('node', 'offer')")
        pg.wait_for_timeout(900)
    # nothing parked may still carry a ring
    # (a 874px-wide homepage is the desktop layout: its closed picker is not parked off-screen and keeps the class-less rule)
    if not pg.evaluate("document.documentElement.matches('.mobile,.rw')"):
        assert page == "h.html" and size[0] > 640
        rings = []
    else:
        rings = pg.evaluate("""[...document.querySelectorAll('#bg-panel,#ef-panel,#notes-panel,#summary-wrap')]
            .filter(e=>!e.classList.contains('open')).map(e=>[e.id,getComputedStyle(e).boxShadow]).filter(x=>x[1]!=='none')""")
    assert not rings, rings
    left, right = _strip(pg)
    assert left < EDGE and right < EDGE, (left, right)
    ctx.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_an_open_panel_keeps_its_ring_on_a_holo_phone(webkit, site, theme):
    ctx, pg = _open(webkit, site, "/t.html", (402, 874), theme)
    seen = pg.evaluate("""()=>{const o={};for(const id of ['bg-panel','ef-panel','notes-panel']){const e=document.getElementById(id);if(!e)continue;
        const before=getComputedStyle(e).boxShadow;e.classList.add('open');o[id]=[before,getComputedStyle(e).boxShadow];}return o;}""")
    assert seen, seen
    for id_, (before, after) in seen.items():
        assert before == "none", (id_, before)
        assert after != "none" and "4px" in after, (id_, after)
    ctx.close()
