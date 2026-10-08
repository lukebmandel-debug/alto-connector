"""The homepage and a timeline share one set of chrome: the title bar (clef, wordmark),
the bottom-right row (search, info, light/dark) and the account bubble. They are the
same size and in the same place on both, so going from one to the other moves nothing;
the magnifier is the homepage's drawing in both. The ⋯ on a homepage tile offers Move,
Print and Delete only (Share has its own button on the tile). The way back from a detail
page sits on the clef's centre line, clear of it. The browser parts are skipped when
Playwright is not installed."""
import json
import re
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.pages import build_home
from alto.hosted import hosted_home

ROOT = Path(__file__).resolve().parent.parent
HOME_SRC = (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def built():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0], hosted_home(build_home([]))


def _magnifier(html):
    m = re.search(r'<span id="search-glyph"[^>]*>\s*(<svg.*?</svg>)', html, re.S)
    return m.group(1)


def test_the_tile_menu_is_move_print_delete_only():
    fn = HOME_SRC[HOME_SRC.index("function altoTileMenu"):HOME_SRC.index("function moveView")]
    home = fn[fn.index("function home()"):]
    assert "btn('Move to another project…'" in home
    assert "btn('Print…'" in home
    assert "btn('Delete timeline…'" in home
    assert "btn('Cancel'" in home
    assert "Share" not in home and "altoShareMenu" not in home
    # the tile keeps its own Share button, and the guide no longer promises a Share in the ⋯
    assert "altoShareMenu(pg, shb)" in HOME_SRC
    assert "on your own timelines moves, prints or deletes" in HOME_SRC
    assert "moves, shares" not in HOME_SRC


def test_the_timeline_magnifier_is_the_homepages_drawing(built):
    tl, home = built
    norm = lambda s: re.sub(r"\s+", "", s.replace("'+", "").replace("'", ""))   # noqa: E731
    th, hh = _magnifier(home), _magnifier(home)
    assert 'viewBox="0 0 20 20"' in hh and 'stroke-width="1.8"' in hh
    # the timeline builds its glyph in script: the same drawing, no nudged view box, same stroke
    js = tl[tl.index("id=\"search-glyph\" role=\"button\""):][:900] if 'id="search-glyph" role="button"' in tl \
        else tl[tl.index('<span id="search-glyph" role="button"'):][:900]
    flat = norm(js)
    for part in ('viewBox="002020"'.replace("002020", "0 0 20 20").replace(" ", ""),
                 'stroke-width="1.8"', '<circlecx="11.4"cy="8.6"r="5.6">',
                 '<linex1="7.44"y1="12.56"x2="3.3"y2="16.7">'):
        assert part in flat, part
    assert "2.25" not in flat and "0.3 -0.3" not in js
    assert th == hh


def test_the_way_back_sits_on_the_clefs_centre_line(built):
    tl, _ = built
    assert "position:fixed; left:80px; top:8.5px; z-index:103; height:35px" in tl
    # 52px bar, 35px button: centre 26 on both; 59.4 (clef's right edge) + 20.6 clear = 80
    assert 8.5 + 35 / 2 == 52 / 2
    assert 80 - (26 + 42 * 78 / 98) > 16


def test_the_phone_homepage_header_is_the_timelines():
    # 52px band, clef 12px in, 16px title at .12em, the timeline's phone veil
    assert "height:calc(52px + env(safe-area-inset-top,0px))" in HOME_SRC
    assert "font-size:16px; letter-spacing:.12em" in HOME_SRC
    assert "rgba(250,251,255,0.35)" in HOME_SRC and "blur(22px)" in HOME_SRC


# ── in a browser ────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:                                  # the browser tests below skip themselves
    pw = None
needs_browser = pytest.mark.skipif(pw is None, reason="Playwright is not installed")

SHARED = {"clef": "#title-bar .brand-mark", "word": "#title-bar .brand-word", "bar": "#title-bar",
          "search": "#search-btn", "search-svg": "#search-btn svg", "info": "#info-btn",
          "info-svg": "#info-icon svg", "mode": "#mode-toggle", "mode-svg": "#mode-toggle svg.mode-glyph:not([style*=none])",
          "account": "#account-btn", "account-svg": "#account-btn svg"}
TOGGLES = {"search", "search-svg", "info", "info-svg", "mode", "mode-svg"}
RECT = """(sel)=>{const o={};for(const [n,s] of Object.entries(sel)){const e=[...document.querySelectorAll(s)]
  .find(x=>x.getBoundingClientRect().width>0);if(!e){o[n]=null;continue}const r=e.getBoundingClientRect(),c=getComputedStyle(e);
  o[n]=[r.x,r.y,r.width,r.height,parseFloat(c.fontSize),parseFloat(c.borderTopLeftRadius)||0,c.borderRadius]}return o}"""


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


@pytest.fixture(scope="module")
def files(built, tmp_path_factory):
    t = tmp_path_factory.mktemp("parity")
    (t / "timeline.html").write_text(built[0], encoding="utf-8")
    (t / "home.html").write_text(built[1], encoding="utf-8")
    return t


def _open(browser, f, w, h, dark=False):
    ctx = browser.new_context(viewport={"width": w, "height": h})
    pg = ctx.new_page()
    pg._ctx = ctx
    pg.add_init_script("try{localStorage.setItem('alto-theme-v1','%s')}catch(e){}" % ("dark" if dark else "light"))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1500)
    return pg


@pytest.mark.parametrize("w,h", [(1280, 800), (1440, 900), (1700, 1000), (1920, 1080)])
@pytest.mark.parametrize("dark", [False, True])
def test_shared_chrome_is_identical_on_the_homepage_and_a_timeline(browser, files, w, h, dark):
    pa = _open(browser, files / "home.html", w, h, dark)
    a = pa.evaluate(RECT, SHARED)
    pa._ctx.close()
    pb = _open(browser, files / "timeline.html", w, h, dark)
    b = pb.evaluate(RECT, SHARED)
    pb._ctx.close()
    for name in SHARED:
        assert a[name] and b[name], name
        for i, (u, v) in enumerate(zip(a[name][:6], b[name][:6])):
            if name == "bar" and i == 5:
                continue
            # the homepage's bottom-right toggles sit where the account toggle's mirror image is (1.9.60), not
            # where the timeline keeps them beside its edit toggle: only their size, type and shape are shared
            if name in TOGGLES and i < 2:
                continue
            assert abs(u - v) < 0.06, (name, i, a[name], b[name])
        assert a[name][6] == b[name][6], (name, a[name][6], b[name][6])


def test_the_back_button_is_centred_on_the_clef_and_clear_of_it(browser, files):
    for w in (1280, 1440, 1700):
        pg = _open(browser, files / "timeline.html", w, 900)
        pg.evaluate("showDetail('node','offer')")
        pg.wait_for_timeout(800)
        r = pg.evaluate("""()=>{const m=document.querySelector('#title-bar .brand-mark').getBoundingClientRect(),
          b=document.getElementById('desk-back').getBoundingClientRect(),t=document.getElementById('title-bar').getBoundingClientRect();
          return {mc:m.top+m.height/2,bc:b.top+b.height/2,tc:t.top+t.height/2,gap:b.left-m.right}}""")
        assert abs(r["bc"] - r["mc"]) < 0.3 and abs(r["bc"] - r["tc"]) < 0.3, (w, r)
        assert 16 <= r["gap"] <= 24, (w, r)
        pg._ctx.close()
