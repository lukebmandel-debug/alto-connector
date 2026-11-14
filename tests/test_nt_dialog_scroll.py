"""The New / Start new project dialog fits the window and scrolls itself (Luke 2026-11-13: "I'm unable to scroll up or down here on the whole
builder thing, fix it please"). With Memory Palace > Memory Atlas > A country chosen, the dialog stood taller than the window, centred in a
fixed scrim: its name field was cut off above, the country list below, and neither the wheel nor the trackpad moved it.

Browser (WebKit; skipped without Playwright): Classic, Retro and Holographic at 1440x700, 1000x520, 402x874 and 874x292. The dialog is opened
on Memory Atlas with the country list showing, then wheel-scrolled: its scrollTop moves, the name field and the last country can each be
brought into view, the dialog fits the window, and the page behind does not move."""
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import holo, pages, retro            # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("ntscroll")
    (d / "h.html").write_text(pages.build_home([]), encoding="utf-8")
    for sub, asset in (("holo", holo.holo_asset), ("retro", retro.retro_asset)):
        (d / sub).mkdir()
        name, text = asset()
        (d / sub / name).write_text(text, encoding="utf-8")

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
def browser():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


def _pages(n):
    return [{"key": "k%d" % i, "project": "Project %d" % (i // 4), "title": "Tile number %d" % i, "heading": "Tile number %d" % i, "tid": "t%d" % i,
             "added": 1.7e12 - i, "viewedAt": 1.7e12 - i, "fmt": "timeline", "units": [{"label": "U", "color": "#7c5cff"}]} for i in range(n)]


def open_atlas(browser, site, style, size, dark=False):
    """The home page with enough tiles to scroll, scrolled a little, and the dialog open on Memory Atlas > A country."""
    pg = browser.new_page(viewport={"width": size[0], "height": size[1]})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s');localStorage.removeItem('alto-home-view-v1');"
                       "localStorage.setItem('alto-theme-v1','%s')}catch(e){}" % (style, "dark" if dark else "light"))
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(700)
    pg.evaluate("p=>{drawPrivate(p)}", _pages(40))
    pg.wait_for_timeout(200)
    pg.evaluate("""()=>{const s=document.scrollingElement; s.scrollTop=40; const w=document.getElementById('projects-wrap'); if(w) w.scrollTop=40;
      ntOpen('', true); ntModes.palace='world'; ntPick('palace');
      ntScope={scope:'country', iso:'', name:''}; ntScopeSync();}""")
    pg.wait_for_timeout(300)
    return pg


BODY = "()=>[document.scrollingElement.scrollTop, (document.getElementById('projects-wrap')||{}).scrollTop||0]"


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(1440, 700), (1000, 520), (402, 874), (874, 292)], ids=["wide700", "narrow520", "phone-up", "phone-side"])
def test_the_new_dialog_scrolls_and_the_page_stays(browser, site, style, size):
    pg = open_atlas(browser, site, style, size, dark=(style == "holo"))
    try:
        assert pg.evaluate("!document.getElementById('nt-clist').hidden"), "the country list should show"
        m = pg.evaluate("""()=>{const d=document.getElementById('nt-modal').getBoundingClientRect();
          return {top:d.top, bottom:d.bottom, vh:innerHeight, sh:document.getElementById('nt-modal').scrollHeight}}""")
        assert m["top"] >= -0.5 and m["bottom"] <= m["vh"] + 0.5, f"the dialog does not fit the window: {m}"
        assert m["sh"] > m["vh"], f"the case should be taller than the window: {m}"
        body0 = pg.evaluate(BODY)
        box = pg.evaluate("()=>{const r=document.getElementById('nt-modal').getBoundingClientRect(); return [r.left+r.width/2, r.top+30]}")
        pg.mouse.move(*box)
        st0 = pg.evaluate("document.getElementById('nt-modal').scrollTop")
        for _ in range(4):
            pg.mouse.wheel(0, 300)
            pg.wait_for_timeout(120)
        st1 = pg.evaluate("document.getElementById('nt-modal').scrollTop")
        assert st1 > st0, f"the wheel did not scroll the dialog ({st0} -> {st1})"
        # the last country can be reached and seen (the list, then the dialog, scroll it into view)
        vis = pg.evaluate("""()=>{const rows=[...document.querySelectorAll('#nt-clist .nt-crow')].filter(r=>!r.hidden), last=rows[rows.length-1];
          last.scrollIntoView({block:'nearest'}); const r=last.getBoundingClientRect(), l=document.querySelector('#nt-clist .nt-crows').getBoundingClientRect();
          return r.top>=-0.5 && r.bottom<=innerHeight+0.5 && r.bottom<=l.bottom+0.5}""")
        assert vis, "the last country could not be brought into view"
        # wheel back up to the top: the name field shows again
        pg.mouse.move(*box)
        for _ in range(30):
            pg.mouse.wheel(0, -400)
            pg.wait_for_timeout(40)
        pg.wait_for_timeout(200)
        top = pg.evaluate("""()=>{const r=document.getElementById('nt-project').getBoundingClientRect(); return [r.top, r.bottom, innerHeight]}""")
        assert top[0] >= -0.5 and top[1] <= top[2] + 0.5, f"the name field is out of view after scrolling up: {top}"
        # keyboard focus keeps the focused field in view (focus the search after scrolling to the top)
        pg.evaluate("document.getElementById('nt-cq').focus()")
        pg.wait_for_timeout(150)
        f = pg.evaluate("()=>{const r=document.getElementById('nt-cq').getBoundingClientRect(); return [r.top, r.bottom, innerHeight]}")
        assert f[0] >= -0.5 and f[1] <= f[2] + 0.5, f"the focused field is out of view: {f}"
        # a wheel over the dimmed scrim, outside the dialog, does not move the page behind
        pg.mouse.move(4, size[1] - 4)
        pg.mouse.wheel(0, 400)
        pg.wait_for_timeout(200)
        assert pg.evaluate(BODY) == body0, "the page behind the dialog scrolled"
    finally:
        pg.close()
