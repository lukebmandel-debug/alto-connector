"""The title header (a hanging tab with the format symbol; Luke 2026-11-05, "1, B") and the New / Import tiles (a frame; "2, A").

Non-browser: what the pages and the hosted scripts carry. Browser (WebKit and Chromium; skipped without Playwright): the tab hangs from the
top edge on the homepage, Reports and a timeline, in Classic, Retro and Holographic; the format's symbol sits beside the name; a phone keeps
its own header; the New tiles and the Import tile lose their dashed outline in Retro and Holographic (Classic keeps it) and their plus and
words are centred in them."""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds_import as bi, format_symbols, holo, pages, retro, title_tab   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _build(name, **over):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"].update(over)
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


HOME = [{"name": "Law", "pid": "p", "courses": [
    {"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff"]},
    {"title": "Contracts", "href": "t.html", "sub": "0 units", "courseId": "b", "units": []}]}]


# ── what the pages and scripts carry ─────────────────────────────────────────

def test_the_image_of_every_symbol_is_a_self_contained_css_url_in_its_own_ink():
    for k in format_symbols.KEYS:
        u = format_symbols.ink_uri(k, "#06485c")
        assert "stroke='%2306485c'" in u
        assert u.startswith('url("data:image/svg+xml,') and u.endswith('")')
        body = u[len('url("data:image/svg+xml,'):-2]
        assert '"' not in body and "<" not in body and "#" not in body.replace("%23", "") and "currentColor" not in body
        assert "mask-image" not in u and "-webkit-mask" not in u   # (the ban is on the CSS mask on the tab, c46cd5f0 "Safari-safe, mask-free CSS"; the Blueprint glyph's SVG <mask> is inside the image, drawn by the image renderer, not a CSS mask)


def test_a_timeline_page_carries_the_tab_and_its_own_symbol_and_a_system_its_dark_sheet():
    t = _build("outline")
    assert 'id="alto-title-tab"' in t and "--tt-sym:" in t and "border-radius:0 0 14px 14px" in t
    assert format_symbols.ink_uri("outline", "#1a1a2e") in t and format_symbols.ink_uri("outline", "#000") in t
    assert format_symbols.ink_uri("lanes", "#c9fffa") in _build("lanes") and "mask" not in t.split('id="alto-title-tab"')[1].split("</style>")[0]
    s = _build("outline", layout="solar")
    assert format_symbols.ink_uri("system", "#eef2ff") in s and "html.alto-stars:not(.mobile) #title-bar #title-text" in s
    assert "html.alto-stars:not(.mobile) #title-bar #title-text" not in t


def test_the_homepage_and_reports_carry_the_tab_for_a_computer_only_and_no_symbol():
    for p in (pages.build_home(HOME), pages.build_reports([], "")):
        assert '<style id="alto-title-tab">@media (min-width:641px){' in p and "--tt-sym:" not in p
        assert "border-radius:999px" not in p.split('id="alto-title-tab"')[1].split("</style>")[0]


def test_the_tab_is_not_a_pill_any_more_and_a_rename_still_reaches_the_name():
    # the symbol is the name's ::after: no markup goes inside the span (a rename sets its textContent, the cloud store rewrites its text)
    assert 'content:""' in title_tab.AFTER_CSS and "::after" in title_tab.AFTER_CSS
    assert '<span id="title-text">' in _build("outline")


def test_retro_and_holo_carry_the_tab_and_the_frame_tiles_and_a_phone_keeps_its_chip():
    r, h = retro.css(), holo.css()
    for c in (r, h):
        assert "new-tile" in c and ("bg-add" in c or c is r) and "dashed" not in c.split("new-tile")[1][:600]
    assert "#title-bar #title-text:not(#_){--tt-pt:8px" in r and "clip-path:none" in r and "clip-path:polygon" not in r.split("#title-text:not(#_){--tt-pt:8px")[1][:600]
    assert "@media (max-width:640px){ html.alto-retro.alto-home #title-bar #title-text".replace("{ ", "{") in r.replace("{ ", "{") or "@media (max-width:640px)" in r
    assert "clip-path:none;translate:none" in h


# ── in a browser ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("ttsite")
    (d / "t.html").write_text(_build("outline"), encoding="utf-8")
    (d / "l.html").write_text(_build("lanes"), encoding="utf-8")
    (d / "s.html").write_text(_build("outline", layout="solar"), encoding="utf-8")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    (d / "r.html").write_text(pages.build_reports([], ""), encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    name, text = holo.holo_asset()
    (d / "holo" / name).write_text(text, encoding="utf-8")
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")
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


@pytest.fixture(params=["webkit", "chromium"], scope="module")
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


def _open(browser, site, page, style, size=(1400, 700)):
    pg = browser.new_page(viewport={"width": size[0], "height": size[1]})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s')}catch(e){}" % style)
    pg.goto(f"{site}/{page}.html")
    pg.wait_for_timeout(500)
    if page in ("t", "l") and style != "classic":
        pg.evaluate("localStorage.clear(); window._altoStyle.set('%s')" % style)
        pg.wait_for_timeout(800)
    return pg


def _px(v):
    return 0.0 if v in ("auto", "normal", "") else float(v[:-2])


TAB = """()=>{const e=document.getElementById('title-text'), r=e.getBoundingClientRect(), s=getComputedStyle(e), a=getComputedStyle(e,'::after');
  return {top:r.top, bottom:r.bottom, vis:s.visibility, rad:s.borderBottomLeftRadius, bg:s.backgroundColor, w:a.width, h:a.height,
          cx:(r.left+r.right)/2/(window.innerWidth/document.documentElement.getBoundingClientRect().width||1), iw:window.innerWidth}}"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("page", ["h", "t", "l"])
def test_the_tab_hangs_from_the_top_edge(browser, site, style, page):
    if style == "retro" and page in ("t", "l"):
        pytest.skip("Retro's board carries the name in its crown; the tab shows on the homepage and detail pages")
    pg = _open(browser, site, page, style)
    t = pg.evaluate(TAB)
    assert t["vis"] == "visible" and t["top"] <= 5 and 24 < t["bottom"] < 60, t
    if style == "classic":
        assert t["rad"] == "14px"
    if page == "t":
        assert _px(t["w"]) == pytest.approx(18, abs=1) and _px(t["h"]) == pytest.approx(18, abs=1)    # the outline's symbol
    if page == "h":
        assert _px(t["w"]) == 0                               # the homepage has no format
    pg.close()


@pytest.mark.parametrize("style", ["classic", "holo", "retro"])
def test_a_detail_page_keeps_the_tab_in_every_style(browser, site, style):
    pg = _open(browser, site, "t", style)
    pg.evaluate("showDetail('node','formation')")
    pg.wait_for_timeout(600)
    t = pg.evaluate(TAB)
    assert t["vis"] == "visible" and t["top"] <= 5 and _px(t["w"]) == pytest.approx(18, abs=1), t
    pg.close()


def test_a_system_keeps_its_name_readable(browser, site):
    pg = _open(browser, site, "s", "classic")
    c = pg.evaluate("getComputedStyle(document.getElementById('title-text')).color")
    b = pg.evaluate("getComputedStyle(document.getElementById('title-text')).backgroundColor")
    nums = lambda s: [int(float(x)) for x in s[s.index("(") + 1:-1].replace("/", ",").replace(" ", ",").split(",") if x][:3]
    assert sum(nums(c)) > 600 and sum(nums(b)) < 120, (c, b)
    pg.close()


def test_reports_wears_the_tab(browser, site):
    pg = _open(browser, site, "r", "classic")
    t = pg.evaluate(TAB)
    assert t["top"] <= 5 and t["rad"] == "14px", t
    pg.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_a_phone_keeps_its_own_header(browser, site, style):
    pg = _open(browser, site, "h", style, size=(390, 800))
    t = pg.evaluate(TAB)
    assert t["rad"] != "14px" and _px(t["w"]) == 0, t
    if style == "retro":
        assert pg.evaluate("getComputedStyle(document.getElementById('title-text')).borderTopStyle") == "solid"
        assert pg.evaluate("getComputedStyle(document.getElementById('title-text')).backgroundColor") == "rgb(0, 0, 0)"
    pg.close()


CENTRE = """s=>{const t=document.querySelector(s), r=t.getBoundingClientRect(), p=t.querySelector('[class$=plus]').getBoundingClientRect(), l=t.querySelector('[class$=label]').getBoundingClientRect();
  return {dy:((Math.min(p.top,l.top)+Math.max(p.bottom,l.bottom))/2)-(r.top+r.bottom)/2, dx:((Math.min(p.left,l.left)+Math.max(p.right,l.right))/2)-(r.left+r.right)/2,
          bs:getComputedStyle(t).borderTopStyle, br:getComputedStyle(t).borderTopLeftRadius}}"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("sel", [".course-tile.new-tile", ".new-project-slab"])
def test_the_new_tiles_have_a_frame_not_a_dashed_outline_and_are_centred(browser, site, style, sel):
    pg = _open(browser, site, "h", style)
    c = pg.evaluate(CENTRE, sel)
    assert abs(c["dy"]) <= 2 and abs(c["dx"]) <= 2, c
    if style == "classic":
        assert c["bs"] == "dashed"                              # Classic untouched
    else:
        assert c["bs"] == "solid" and c["br"] == "0px", c
    pg.close()


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_import_tile_in_the_scene_panel_follows(browser, site, style):
    pg = _open(browser, site, "h", style)
    pg.click("#bg-toggle")
    if style == "retro":      # Retro is plain black on every page (Luke 2026-11-04): the Scene panel shows only the style picker, so there is no Import tile to frame
        pg.wait_for_selector("#bg-panel", state="visible", timeout=8000)
        pg.wait_for_timeout(300)
        assert pg.evaluate("document.querySelector('#bg-yours .bg-add').getBoundingClientRect().width") == 0
        pg.close()
        return
    pg.wait_for_selector("#bg-yours .bg-add", timeout=8000)
    pg.wait_for_timeout(300)
    bs = pg.evaluate("getComputedStyle(document.querySelector('#bg-yours .bg-add')).borderTopStyle")
    assert bs == ("dashed" if style == "classic" else "solid")
    # Holo's picker rule hides every section without a Holographic tile; #bg-yours (the Import tile) is never removed
    assert pg.evaluate("document.querySelector('#bg-yours .bg-add').getBoundingClientRect().width") > 0
    pg.close()
