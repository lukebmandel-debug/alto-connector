"""Retro for every format (alto/build/retro.py): the Star chart's Retro (black and gold, the art-deco frame, spaced capitals)
as a per-timeline style, Classic | Retro, of the timeline, the horizontal timeline, the outline and both palaces' plans.

A page carries only the switch's hook; the look is a hosted script fetched only when Retro is chosen. The browser parts are
skipped when Playwright is not installed."""
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds as bg, backgrounds_import as bi, palace_assets, retro   # noqa: E402
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


@pytest.fixture(scope="module")
def outline():
    return _build("outline")


# ── what a page carries ─────────────────────────────────────────────────────

def test_the_look_is_a_hosted_script_and_the_page_holds_only_its_hook(outline):
    name, text = retro.retro_asset()
    assert retro.PATH == "/retro/" + name and ("retro", name, text) in palace_assets.assets()
    assert palace_assets.find(retro.PATH)[1] == text
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', outline, re.S).group(1)
    assert json.dumps(retro.PATH) in head and "-style" in head
    assert "alto-retro-css" not in outline and "html.alto-retro" not in outline     # none of the rules ride in the page


@pytest.mark.parametrize("anchor", ["#sk-frame", "#sk-mark", "#world .phase-band", "#world .node-card", "#river-svg path",
                                    "#detail-page", "#lanes-svg .ln-main", ".pal-svg .pl-tube", "#bldg-root", ".lu-chip"])
def test_every_format_has_its_rules(anchor):
    assert "html.alto-retro" in retro.css() and anchor in retro.css()
    assert "X " not in retro.css() and "X:" not in retro.css() and "FONT" not in retro.css()


def test_the_system_keeps_its_own_styles_and_shares_the_frame():
    page = _build("outline", layout="solar")
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', page, re.S).group(1)
    assert retro.PATH not in head and "if(0)" in head
    from alto.build.solar_stars import STARS_CSS
    frame = retro.FRAME_CSS.strip().split("\n")[2].strip().replace("X ", "html.alto-stars.sk-retro:not(.mobile) ")
    assert frame in STARS_CSS


def test_the_homepage_offers_the_style_switch():
    # item 15 (Luke 2026-10-28, "8A"): the homepage follows Classic | Retro like the other formats; the choice is kept
    # under its own key, never over the background's
    from alto.build import pages
    page = pages.build_home([])
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', page, re.S).group(1)
    assert retro.PATH in head and "if(0)" not in head
    assert "KEY+'-style'" in head.replace(" ", "")
    assert "html.alto-retro.alto-home #search-btn" in retro.css()


def test_the_picker_draws_the_switch_from_the_hosted_library():
    js = bi.lib_js()
    assert "function styles()" in js and "window._altoStyle" in js and "'Retro'" in js


# ── in a browser ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def site(outline, tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("retrosite")
    (d / "t.html").write_text(outline, encoding="utf-8")
    (d / "old.html").write_text(outline.replace(retro.PATH, "/retro/alto-retro-0000000000.js"), encoding="utf-8")   # a file the site lacks
    (d / "retro").mkdir()
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")
    hits = []

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def do_GET(self):
            hits.append(self.path)
            return super().do_GET()

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", hits
    srv.shutdown()
    srv.server_close()


@pytest.fixture(params=["webkit", "chromium"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


_STATE = """[document.documentElement.classList.contains('alto-retro'), !!document.getElementById('alto-retro-css'),
  !!document.getElementById('sk-frame'), document.documentElement.classList.contains('dark'), window._altoStyle.get()]"""


def test_classic_fetches_nothing_and_retro_is_kept_per_timeline(browser, site):
    base, hits = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    hits.clear()
    pg.goto(base + "/t.html")
    pg.wait_for_timeout(600)
    assert pg.evaluate(_STATE) == [False, False, False, False, "classic"]
    assert not any(h.startswith("/retro/") for h in hits)                  # Classic never fetches the look
    # chosen in the picker: the switch heads it
    pg.click("#bg-toggle")
    pg.wait_for_selector("#bg-style .bg-segb[data-sty=retro]", timeout=8000)
    assert pg.eval_on_selector_all("#bg-style .bg-segb", "b => b.map(x => x.textContent)") == ["Classic", "Retro"]
    pg.click("#bg-style .bg-segb[data-sty=retro]")
    assert pg.evaluate(_STATE) == [True, True, True, True, "retro"]
    assert pg.get_attribute("#bg-style .bg-segb[data-sty=retro]", "aria-pressed") == "true"
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg')).backgroundColor") == "rgb(0, 0, 0)"
    assert pg.evaluate("!!document.querySelector('#sk-mark') && document.querySelector('#sk-mark').textContent.length > 0")
    # remembered: the next visit opens in Retro before anything is drawn
    pg.add_init_script("document.addEventListener('DOMContentLoaded', function(){ window.__atReady=document.documentElement.classList.contains('alto-retro'); });")
    pg.reload()
    pg.wait_for_timeout(600)
    assert pg.evaluate("window.__atReady") is True
    assert pg.evaluate(_STATE)[:4] == [True, True, True, True]
    # back to Classic: the reader's own (light) theme returns
    pg.evaluate("window._altoStyle.set('classic')")
    assert pg.evaluate(_STATE) == [False, True, False, False, "classic"]
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg')).backgroundColor") != "rgb(0, 0, 0)"
    assert not errors, errors
    ctx.close()


def test_a_page_without_the_hosted_file_stays_classic(browser, site):
    base, _ = site
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(base + "/old.html")
    pg.wait_for_timeout(300)
    pg.evaluate("window._altoStyle.set('retro')")
    st = pg.evaluate(_STATE)
    assert st[:3] == [False, False, False] and st[4] == "retro"
    ctx.close()


# ── controls drawn round in Classic are deliberate squares in Retro (Luke, 2026-10-23) ──

_ROUND = ["#ct-chips", "#info-btn", "#notes-close", ".nt-btn", ".ef-chip", "#ef-close", ".csym-btn", "#fw-seg"]


def test_the_round_controls_have_square_rules_shared_with_the_system():
    from alto.build.solar_stars import STARS_CSS
    for sel in ["#ct-chips", "#info-btn", "#notes-panel button", ".nt-btn", ".ef-chip", "#ef-close", ".csym-btn", "#fw-seg", "#sol-tour", ".hl-color-swatch", "#m-search"]:
        assert sel in retro.CHROME_CSS, sel
    assert "html.alto-stars.sk-retro:not(.mobile) #sol-tour" in STARS_CSS                 # (the System's Retro wears the same chrome)
    for sel in (".lnv-thumb", ".pr-tk", "#pal-ctl button,#alto-edit-pill .aep-half)::after"):
        assert sel in retro.FORMAT_CSS, sel


_RADII = """(sels)=>sels.map(function(s){ var e=document.querySelector(s); if(!e) return [s, null];
  var r=e.getBoundingClientRect(), c=getComputedStyle(e), rad=parseFloat(c.borderTopLeftRadius)||0;
  var inner=[].slice.call(e.querySelectorAll('*')).map(function(k){ return parseFloat(getComputedStyle(k).borderTopLeftRadius)||0; });
  return [s, rad, Math.max.apply(null, [0].concat(inner)), Math.round(r.width), Math.round(r.height)]; })"""


def test_in_retro_every_round_control_is_square_inside_and_out_and_keeps_its_box(browser, site):
    base, _ = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(base + "/t.html")
    pg.wait_for_timeout(600)
    pg.evaluate("toggleNotes()")
    pg.click("#filter-toggle")
    pg.wait_for_timeout(500)
    classic = {r[0]: r for r in pg.evaluate(_RADII, _ROUND) if r[1] is not None and r[3] > 0}   # (drawn in Classic: a panel's close is hidden on a desktop)
    assert classic["#ct-chips"][1] >= classic["#ct-chips"][3] / 2 - 1 and classic[".ef-chip"][1] >= 12   # (round in Classic)
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(1200)                       # (#info-btn eases its corners: measure once settled)
    for s, rad, inner, w, h in pg.evaluate(_RADII, list(classic)):
        assert rad == 0 and inner == 0, (s, rad, inner)
        if s in (".ef-chip", "#fw-seg"):          # text chips: Retro's own lettering sets their width; their height stays
            assert abs(h - classic[s][4]) <= 2, (s, w, h, classic[s][3:5])
        else:                                     # icon controls: the same box, so the same hit area
            assert (w, h) == tuple(classic[s][3:5]), (s, w, h, classic[s][3:5])
    assert pg.evaluate("getComputedStyle(document.querySelector('#fw-seg button[aria-selected=true]')).backgroundColor") == "rgb(217, 174, 85)"
    pg.evaluate("window._altoStyle.set('classic')")
    assert pg.evaluate(_RADII, ["#ct-chips"])[0][1] > 0                                       # Classic stays round
    ctx.close()


def test_in_retro_the_bottom_right_row_has_no_gap_and_every_control_its_frame(browser, site):
    """Luke, 2026-10-25: "The Google sign-in is still a circle within a square. The square around search doesn't look right,
    and there's no square around information. And then now there's a gap where light or dark mode used to be." Retro hides the
    light / dark toggle (it is always dark), so search and info take its place; info is framed like search; a photo is square."""
    base, _ = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(base + "/t.html")
    pg.wait_for_timeout(600)
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(1200)
    pg.evaluate("""() => { var b=document.getElementById('account-btn'), m=document.getElementById('acct-avatar-mini'), g=document.getElementById('acct-glyph');
      b.classList.add('signed-in'); g.style.display='none'; m.style.display='flex';
      m.innerHTML='<img alt="" src="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%228%22 height=%228%22/%3E">'; }""")
    h = pg.evaluate("""() => { var R=id=>document.getElementById(id).getBoundingClientRect(), s=R('search-btn'), i=R('info-btn'), p=R('alto-edit-pill'),
        a=R('account-btn'), m=document.querySelector('#acct-avatar-mini img').getBoundingClientRect(), cs=e=>getComputedStyle(e);
      return {mode:cs(document.getElementById('mode-toggle')).display, gap1:i.left-s.right, gap2:p.left-i.right, info:cs(document.getElementById('info-btn')).boxShadow,
        search:cs(document.getElementById('search-btn')).boxShadow, iw:i.width, sw:s.width, img:[m.width, m.height, a.width, a.height],
        rad:[cs(document.getElementById('acct-avatar-mini')).borderTopLeftRadius, cs(document.querySelector('#acct-avatar-mini img')).borderTopLeftRadius]}; }""")
    ctx.close()
    assert h["mode"] == "none", h
    assert abs(h["gap1"] - h["gap2"]) <= 4 and h["gap1"] < 20, h                 # even spacing, no hole
    assert "217, 174, 85" in h["info"] and h["info"] == h["search"], h          # the same gold rim
    assert abs(h["iw"] - h["sw"]) <= 1, h
    assert h["rad"] == ["0px", "0px"] and h["img"][0] >= h["img"][2] - 2, h     # a square photo filling its frame


def test_in_retro_the_corner_controls_stay_square_after_opening_and_closing(browser, site):
    """Luke, 2026-10-25: "in retro style when I expand the info button and collapse it again. While it originally looks
    square, it then reverts to a circle incorrectly." The engine's open / shut animation wrote the corners inline
    (50% shut, 12px open, !important); Retro's are square in every state, and back in Classic they are round again."""
    base, _ = site
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(base + "/t.html")
    pg.wait_for_timeout(600)
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(1200)
    rad = "id => getComputedStyle(document.getElementById(id)).borderTopLeftRadius"
    for _ in range(3):
        pg.click("#info-icon")
        pg.wait_for_timeout(500)
        assert pg.evaluate(rad, "info-btn") == "0px"                                   # open
        pg.click("#info-icon")
        pg.wait_for_timeout(500)
        assert pg.evaluate(rad, "info-btn") == "0px"                                   # shut
        pg.hover("#info-btn")
        assert pg.evaluate(rad, "info-btn") == "0px"                                   # hovered
        pg.click("#search-glyph")
        pg.wait_for_timeout(400)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        assert pg.evaluate(rad, "search-btn") == "0px" and pg.evaluate(rad, "account-btn") == "0px"
        pg.mouse.move(5, 450)
    pg.evaluate("window._altoStyle.set('classic')")                                    # Classic: round again
    pg.wait_for_timeout(500)
    assert pg.evaluate(rad, "info-btn") not in ("0px", "")
    ctx.close()
