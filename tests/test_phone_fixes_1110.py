"""Phone fixes from Simulator batch 1110b (Luke, 2026-11-10): the Retro and Holographic homepage on a phone.

WebKit with a phone's size and touch (portrait 375x812, landscape 812x375). Browser rows are skipped without Playwright.
- the plate: a card's title sits inside the card (padding), in Retro and Holographic, portrait and landscape, with or without the page's format symbol
- the top rows stand on solid ground (Retro, Holographic), portrait header + chip row, landscape header; Classic's chip row has its veil
- turning a phone does not flip Holographic's theme (it was dark in landscape, light in portrait: "loses the dark theme and the background")
- Holographic's picker lists only the Holographic backgrounds (and the Import tile), in both orientations"""
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds_import as bi, holo, pages, retro   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
FMTS = ["timeline", "lanes", "outline", "system", "palace", "building", "world"]
PORTRAIT, LAND = {"width": 375, "height": 812}, {"width": 812, "height": 375}


def _live_home(n=8):
    """Cards the way the signed-in page draws them (format symbol on each), the cloud stub."""
    pageset = [dict(key=f"k{i}", title=f"T{i}", heading=f"Civil Procedure {i}", project="Law", fmt=FMTS[i % 7], tid=f"t{i}", units=["#4a9eff", "#e8a87c"][: i % 2 + 1]) for i in range(n)]
    stub = ("<script>window.AltoCloud={enabled:true,known:true,user:{uid:'u1',email:'a@b.c',displayName:'A'},listPages:()=>Promise.resolve(%s),"
            "listShared:()=>Promise.resolve([]),signOut:()=>Promise.resolve(),createTimeline:()=>Promise.resolve({}),signIn:()=>Promise.resolve(),"
            "getPage:()=>Promise.resolve(''),forgetShare:()=>Promise.resolve()};</script>" % json.dumps(pageset))
    return pages.build_home([]).replace("<head>", "<head>" + stub, 1)


def _static_home():
    """Cards from the static course list: no format symbol on them (the tile has no emblem)."""
    return pages.build_home([{"name": "Law", "pid": "p", "courses": [
        {"title": f"Civil Procedure {i}", "href": "t.html", "sub": f"{i + 3} units", "courseId": f"c{i}", "units": ["#4a9eff"]} for i in range(6)]}])


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("phonefix1110")
    (d / "live.html").write_text(_live_home(), encoding="utf-8")
    (d / "static.html").write_text(_static_home(), encoding="utf-8")
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


def _open(browser, site, page, style, size, dark=None):
    ctx = browser.new_context(viewport=size, user_agent=UA, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s')%s}catch(e){}" % (
        style, ";localStorage.setItem('alto-theme','%s')" % dark if dark else ""))
    pg.goto(f"{site}/{page}.html")
    if style != "classic":
        pg.wait_for_function("document.documentElement.classList.contains('alto-%s')" % style, timeout=15000)
    pg.wait_for_timeout(1200)
    return pg, ctx


# ── the plate: the title sits inside the card ────────────────────────────────

_PLATE = """()=>[...document.querySelectorAll('.course-tile:not(.new-tile)')].map(t=>{const m=t.querySelector('.t-main'), ti=t.querySelector('.tile-title'), tb=t.getBoundingClientRect(), b=ti.getBoundingClientRect();
    return {main:!!m, em:!!t.querySelector('.tile-emblem'), padL:Math.round(b.left-tb.left), padR:Math.round(tb.right-b.right), over:ti.scrollWidth>ti.clientWidth+1, right:Math.round(tb.right), iw:innerWidth}})"""


@pytest.mark.parametrize("page", ["live", "static"])
@pytest.mark.parametrize("style", ["retro", "holo"])
@pytest.mark.parametrize("size", [PORTRAIT, LAND], ids=["portrait", "landscape"])
def test_a_phone_card_keeps_its_title_inside_its_plate(browser, site, page, style, size):
    pg, ctx = _open(browser, site, page, style, size)
    rows = pg.evaluate(_PLATE)
    assert rows, "no cards"
    for r in rows:
        assert r["main"] and r["em"], (page, style, r)              # decorated, with a medallion (a static card gets one drawn)
        assert r["padL"] >= 10 and r["padR"] >= 8, (page, style, r)     # not flush on the card's edge
        assert r["right"] <= r["iw"], (page, style, r)              # nothing runs off the right edge
    ctx.close()


def test_a_card_without_its_format_symbol_gets_a_medallion_and_loses_it_with_the_style(browser, site):
    pg, ctx = _open(browser, site, "static", "retro", PORTRAIT)
    assert pg.evaluate("document.querySelectorAll('.course-tile:not(.new-tile) > .tile-emblem').length") == 6
    pg.evaluate("window._altoRetro.off()")
    pg.wait_for_timeout(400)
    assert pg.evaluate("document.querySelectorAll('.tile-emblem,.t-main').length") == 0, "the drawn medallion must go with the style"
    ctx.close()


# ── the top rows stand on solid ground ───────────────────────────────────────

_BACK = """()=>{const q=getComputedStyle(document.documentElement,'::before'), a=getComputedStyle(document.body,'::after'); const f=s=>({c:s.content,h:parseFloat(s.height)||0,pos:s.position,z:s.zIndex,bg:s.backgroundImage+'|'+s.backgroundColor});return {before:f(q), after:f(a)}}"""


@pytest.mark.parametrize("style", ["retro", "holo"])
def test_retro_and_holo_top_rows_have_a_ground_behind_the_header_and_the_chip_row(browser, site, style):
    pg, ctx = _open(browser, site, "live", style, PORTRAIT)
    b = pg.evaluate(_BACK)["before"]
    assert b["c"] != "none" and b["pos"] == "fixed" and b["h"] >= 100 and int(b["z"]) == 101 and "gradient" in b["bg"], b       # header (52) + chip row (to 97) + a little
    pg.set_viewport_size(LAND)
    pg.wait_for_timeout(500)
    b = pg.evaluate(_BACK)["before"]
    assert b["pos"] == "fixed" and 50 <= b["h"] <= 70, b                                                                        # sideways: the header row alone
    ctx.close()


def test_the_scrolled_cards_do_not_show_through_the_header_in_retro(browser, site):
    pg, ctx = _open(browser, site, "live", "retro", PORTRAIT)
    top = pg.evaluate("""()=>{const e=document.elementFromPoint(40,40), g=document.elementFromPoint(187,100); return [e.closest('#title-bar')?'bar':e.tagName, g.tagName+'.'+(g.className||'').toString().slice(0,20)]}""")
    assert top[0] == "bar" or top[0] == "HTML", top
    ctx.close()


def test_classic_chip_row_has_a_veil_under_it_on_a_phone(browser, site):
    pg, ctx = _open(browser, site, "live", "classic", PORTRAIT)
    a = pg.evaluate(_BACK)["after"]
    assert a["c"] != "none" and a["pos"] == "fixed" and 50 <= a["h"] <= 70 and int(a["z"]) == 101 and "gradient" in a["bg"], a
    ctx.close()


# ── turning the phone keeps Holographic's theme and background ───────────────

_THEME = """()=>{const bg=document.getElementById('page-bg'); const r=bg.getBoundingClientRect(); return {dark:document.documentElement.classList.contains('dark'), holo:document.documentElement.classList.contains('alto-holo'), bgh:document.documentElement.classList.contains('alto-bg-h'),
    covers:r.left<=0 && r.right>=innerWidth && r.top<=0 && r.bottom>=innerHeight, iw:innerWidth}}"""


@pytest.mark.parametrize("dark", [None, "dark"])
@pytest.mark.parametrize("first", ["portrait", "landscape"])
def test_turning_a_phone_does_not_flip_holographics_theme_or_lose_the_background(browser, site, first, dark):
    sizes = {"portrait": PORTRAIT, "landscape": LAND}
    other = LAND if first == "portrait" else PORTRAIT
    pg, ctx = _open(browser, site, "live", "holo", sizes[first], dark=dark)
    pg.evaluate("document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(600)
    pg.evaluate("document.querySelector('.bg-tile[data-bg=\"h-neon-rain\"]').click()")
    pg.wait_for_timeout(900)
    pg.evaluate("document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(400)
    start = pg.evaluate(_THEME)
    assert start["holo"] and start["bgh"] and start["covers"], start
    for size in (other, sizes[first]):
        pg.set_viewport_size(size)
        pg.wait_for_timeout(900)
        now = pg.evaluate(_THEME)
        assert now["dark"] == start["dark"] and now["holo"] and now["bgh"] and now["covers"], (start, now)
    ctx.close()


def test_a_computer_still_gets_holographics_dark_ground(browser, site):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','holo')}catch(e){}")
    pg.goto(f"{site}/live.html")
    pg.wait_for_function("document.documentElement.classList.contains('alto-holo')", timeout=15000)
    pg.wait_for_timeout(800)
    assert pg.evaluate("document.documentElement.classList.contains('dark')")
    ctx.close()


# ── Holographic's picker ─────────────────────────────────────────────────────

@pytest.mark.parametrize("size", [PORTRAIT, LAND], ids=["portrait", "landscape"])
def test_holographics_picker_lists_only_holographic_backgrounds(browser, site, size):
    pg, ctx = _open(browser, site, "live", "holo", size)
    pg.evaluate("document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(900)
    r = pg.evaluate("""()=>({def:[...document.querySelectorAll('#bg-panel .bg-def')].filter(e=>e.getBoundingClientRect().width>0).length,
        tiles:[...document.querySelectorAll('#bg-panel .bg-tile')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.getAttribute('data-bg'))})""")
    assert r["def"] == 0, r
    assert [t for t in r["tiles"] if t] == ["h-neon-rain", "h-amber-haze", "h-grid-horizon", "h-signal-rain", "h-targeting", "h-lightspeed"], r      # (the one tile with no id is Import)
    assert len(r["tiles"]) == 7, r
    ctx.close()


def test_the_phone_rules_are_in_the_scripts():
    assert "function phone()" in holo.JS and "hdark(desk() && !phone())" in holo.JS
    assert ':has(.bg-tile[data-bg^="h-"],.bg-def)' not in holo.css()
    assert "em._rhMade" in retro.HOME_B_JS
    c = retro.HOME_CSS
    assert "@media (max-width:640px){ X.alto-home::before" in c and "@media (min-width:641px) and (max-height:500px){ X.alto-home::before" in c
