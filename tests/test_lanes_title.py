"""The page's title in the Retro crown on the horizontal timeline (lanes_title.py; Board B-1120-PICK267, option A).
Long title: one line, ellipsis, full name on hover and as the accessible name, 20px clear of the logo and wordmark. Short title:
whole. Classic draws nothing extra. Flag-free: no ?lanestitle switch remains."""
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

from alto.build import holo, phone, retro  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.lanes import LANES_CSS, LANES_JS  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

LONG = "The Ambassador and the Terrarium: A Story of Wren, Harlan and the Long Winter of Complicity"
SHORT = "The Lighthouse"


def test_no_flag_or_dead_variants_remain():
    for s in (LANES_CSS, LANES_JS):
        assert "lanestitle" not in s and "alto-lanes-title" not in s and "lt-b" not in s and "lt-c" not in s


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("lanes_title")
    base = json.loads((ROOT / "samples" / "lanes_v2_brief.json").read_text(encoding="utf-8"))
    for name, t in (("long", LONG), ("short", SHORT)):
        b = copy.deepcopy(base)
        b["brief"]["title"] = t
        (d / f"{name}.html").write_text(build_timeline(*load_brief(b))[0], encoding="utf-8")
    for mod, folder in ((holo, "holo"), (retro, "retro"), (phone, "phone")):
        n, t = getattr(mod, folder + "_asset")()
        (d / folder).mkdir(exist_ok=True)
        (d / folder / n).write_text(t, encoding="utf-8")

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


def _open(browser, site, page, style, width=1440):
    ctx = browser.new_context(viewport={"width": width, "height": 900})
    ctx.add_init_script("try{localStorage.setItem('alto-bg-v1-style',%s)}catch(e){}" % json.dumps(style))
    pg = ctx.new_page()
    pg.goto(f"{site}/{page}", wait_until="load")
    pg.wait_for_timeout(1500)
    pg.evaluate("s=>window._altoStyle&&window._altoStyle.set(s)", style)
    pg.wait_for_timeout(1200)
    return ctx, pg


PROBE = """()=>{const w=document.querySelector('#lt-t .lt-w'); if(!w) return null; const r=w.getBoundingClientRect(), c=document.querySelector('#lt-t').getBoundingClientRect();
 const m=document.querySelector('#title-bar .brand-mark').getBoundingClientRect(), b=document.querySelector('#title-bar .brand-word').getBoundingClientRect();
 return {l:r.left,r:r.right,cl:c.left,cr:c.right,over:w.scrollWidth>w.clientWidth,hover:document.getElementById('lt-t').title,aria:document.getElementById('lt-t').getAttribute('aria-label'),
 text:w.textContent,disp:getComputedStyle(document.getElementById('lt-t')).display,markR:m.right,wordL:b.left,frame:getComputedStyle(document.querySelector('#sk-frame b')).display}}"""


@pytest.mark.parametrize("page,title,long", [("long.html", LONG, True), ("short.html", SHORT, False)])
@pytest.mark.parametrize("width", [1440, 1100])
def test_retro_crown_carries_the_title(browser, site, page, title, long, width):
    ctx, pg = _open(browser, site, page, "retro", width)
    try:
        m = pg.evaluate(PROBE)
        assert m and m["disp"] == "flex" and m["text"] == title and m["hover"] == title and m["aria"] == title
        assert m["over"] is long                                  # ellipsis only when it does not fit
        assert m["l"] >= m["markR"] + 20 and m["r"] <= m["wordL"] - 20, m   # 20px clear of the logo and the wordmark
        assert m["frame"] == "none"                                # the rule is the title's own, broken round the words
    finally:
        ctx.close()


@pytest.mark.parametrize("style", ["classic", "holo"])
def test_other_styles_draw_no_extra_title(browser, site, style):
    ctx, pg = _open(browser, site, "long.html", style)
    try:
        assert pg.evaluate("getComputedStyle(document.getElementById('lt-t')).display") == "none"
    finally:
        ctx.close()


@pytest.mark.parametrize("page,title", [("long.html", LONG), ("short.html", SHORT)])
def test_phone_width_title_shows_at_least_18_characters(browser, site, page, title):
    ctx, pg = _open(browser, site, page, "retro", 390)
    try:
        m = pg.evaluate("""()=>{const w=document.querySelector('#lt-t .lt-w'), B=document.getElementById('lt-t').getBoundingClientRect(), n=w.textContent.length, over=w.scrollWidth>w.clientWidth,
          k=over ? Math.max(0, Math.floor(n*w.clientWidth/w.scrollWidth)-1) : n, mk=document.querySelector('#title-bar .brand-mark').getBoundingClientRect(), cs=getComputedStyle(w);
          return {k, n, over, ls:cs.letterSpacing, fs:cs.fontSize, bl:B.left, br:B.right, vw:innerWidth, markR:mk.right, bw:getComputedStyle(document.getElementById('lt-t')).width}}""")
        assert m["k"] >= min(18, len(title)), str(m)   # at least 18 characters, or the whole of a shorter title
        assert not (len(title) <= 18 and m["over"]), str(m)                              # a short title is whole: no ellipsis
        assert float(m["ls"][:-2]) <= 0.21 * float(m["fs"][:-2]), str(m)    # about half the desktop spacing
        assert m["bl"] >= m["markR"] + 20 and m["br"] <= m["vw"] - 20, str(m)   # the crown run: 20px clear of the logo and of the right edge
    finally:
        ctx.close()


def test_phone_width_short_title_is_centred_between_the_logo_and_the_wordmark(browser, site):
    ctx, pg = _open(browser, site, "short.html", "retro", 390)
    try:
        m = pg.evaluate("""()=>{const w=document.querySelector('#lt-t .lt-w').getBoundingClientRect(), mk=document.querySelector('#title-bar .brand-mark').getBoundingClientRect(),
          b=document.querySelector('#title-bar .brand-word').getBoundingClientRect(), edge=(b.width && b.left<innerWidth) ? b.left : innerWidth;
          return {c:(w.left+w.right)/2, free:(mk.right+edge)/2, l:w.left, r:w.right}}""")
        assert abs(m["c"] - m["free"]) <= 4, str(m)
    finally:
        ctx.close()
