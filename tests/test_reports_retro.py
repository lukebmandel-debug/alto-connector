"""The Reports page (Torts Report Repository) offers Classic | Retro | Holographic, Retro applies, and in Holographic nothing opaque is painted over the top of the
background (cleanup-241, Board B-1118-REPRETRO; the bar was a solid ~67px strip with its own rim and glow)."""
import http.server
import io
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import backgrounds_import as bi, holo, pages, retro                    # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

KEY = "alto-bg-home-v1"


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("reportsite")
    (d / "r.html").write_text(pages.build_reports([], "x"), encoding="utf-8")
    for sub, (name, text) in (("retro", retro.retro_asset()), ("holo", holo.holo_asset())):
        (d / sub).mkdir()
        (d / sub / name).write_text(text, encoding="utf-8")
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


@pytest.fixture(params=["webkit", "chromium"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, base, w, h, style=None, bg=None):
    ctx = browser.new_context(viewport={"width": w, "height": h})
    pg = ctx.new_page()
    init = "localStorage.clear();"
    if style:
        init += f"localStorage.setItem('{KEY}-style','{style}');"
    if bg:
        init += f"localStorage.setItem('{KEY}', JSON.stringify({{v:'{bg}',t:Date.now()}}));"
    pg.add_init_script("if(!sessionStorage.__i){sessionStorage.__i=1;" + init + "}")
    pg.goto(base + "/r.html")
    pg.wait_for_timeout(2200)
    return pg, ctx


def test_the_picker_offers_three_styles_and_retro_applies(browser, base):
    pg, ctx = _open(browser, base, 1440, 900)
    pg.evaluate("document.getElementById('bg-toggle').click()")
    pg.wait_for_selector("#bg-style .bg-segb[data-sty=retro]", timeout=8000)
    assert pg.eval_on_selector_all("#bg-style .bg-segb", "b => b.map(x => x.textContent)") == ["Classic", "Retro", "Holographic"]
    pg.click("#bg-style .bg-segb[data-sty=retro]")
    pg.wait_for_timeout(800)
    assert pg.evaluate("document.documentElement.classList.contains('alto-retro')")
    assert pg.evaluate("getComputedStyle(document.body).backgroundColor === 'rgb(0, 0, 0)' || getComputedStyle(document.documentElement).backgroundColor === 'rgb(0, 0, 0)' || getComputedStyle(document.getElementById('page-bg')).backgroundColor === 'rgb(0, 0, 0)'")
    ctx.close()


@pytest.mark.parametrize("w,h", [(1440, 900), (1000, 760)])
def test_retro_scene_button_keeps_20px_from_the_edge_on_reports(browser, base, w, h):
    pg, ctx = _open(browser, base, w, h, style="retro")
    assert pg.evaluate("document.documentElement.classList.contains('alto-retro')")
    right = pg.evaluate("innerWidth - document.getElementById('bg-toggle').getBoundingClientRect().right")
    assert right >= 19.5, right
    ctx.close()


@pytest.mark.parametrize("w,h", [(1440, 900), (1000, 760)])
def test_nothing_flat_is_painted_over_the_top_of_the_background_on_reports(browser, base, w, h):
    Image = pytest.importorskip("PIL.Image")
    pg, ctx = _open(browser, base, w, h, style="holo", bg="h-neon-rain")
    pg.wait_for_timeout(1500)
    pg.evaluate("(()=>{const v=document.querySelector('#alto-ha video'); if(v){ v.pause(); v.currentTime=6 }})()")
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo')")
    assert pg.evaluate("getComputedStyle(document.getElementById('title-bar')).backgroundColor") == "rgba(0, 0, 0, 0)", "the bar paints nothing over the background"
    im = Image.open(io.BytesIO(pg.screenshot())).convert("L")
    sc = im.width / w
    vals = [im.getpixel((int(x * sc), int(y * sc))) for x in range(100, 600, 3) for y in range(2, 41)]
    assert max(vals) - min(vals) > 10, (min(vals), max(vals))
    ctx.close()
