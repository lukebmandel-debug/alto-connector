"""The Scene / Background panel (alto/build/backgrounds.py, backgrounds_import.py, retro.py, holo.py).

F3a (Luke, 2026-11-04: "The things here are cut off ... not a problem in classic, but it is in retro and holo"): in every style the
panel's style switch, its tiles and its credit line sit inside the panel at every width, on a timeline, the homepage and the reports page.
F3b (Luke: "we shouldn't be showing background options in places that don't accept them"): a Memory Atlas, Blueprint, city map and System
show only the style picker (their detail pages show the full options again), and Retro is plain black on every page, with only the style
picker in the panel; the saved choice is kept and comes back in Classic and Holographic.
The browser parts are skipped when Playwright is not installed."""
import http.server
import json
import re
import shutil
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds as bg, backgrounds_import as bi, holo, pages, retro      # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402
from alto.build.blocks import ID_PATTERNS                       # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
import test_building_palace_tools as _bld                       # noqa: E402
import test_solar_draw as _sol                                  # noqa: E402
import test_world_palace as _wld                                # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

ASSETS = ROOT / "alto" / "assets" / "backgrounds"
HOME = [{"name": "Law", "pid": "p", "courses": [
    {"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e", "#10b981"]}]}]
PHOTO = "aurora-lofoten"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def _real(errors):
    """Page errors that are not the browser's own ResizeObserver noise."""
    return [e for e in errors if "ResizeObserver" not in e]


def _brief_page(name):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0], d["brief"]["timeline_id"]


def _city():
    b = {"title": "City", "timeline_id": "cityx", "mode": "palace", "columns": 5, "node_noun": "Concept", "period_noun": "Unit",
         "acts": [{"label": "A", "color": "#5b6cff"}, {"label": "B", "color": "#9b5de5"}]}
    b, ns, cs = load_brief({"brief": b, "nodes": json.loads(json.dumps(_wld.NODES))})
    return build_timeline(b, ns, cs)[0]


# page -> (file, key of its saved choice, page's own detail opener)
PAGES = {}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("scenepanel")
    out, tid = _brief_page("outline")
    lanes, ltid = _brief_page("lanes")
    built = {"outline": (out, tid), "lanes": (lanes, ltid),
             "atlas": (_wld.built()[0], "civpro"), "blueprint": (_bld.built()[0], "walk"),
             "system": (_sol._page(), _sol.solar_doc(_sol.SMALL, "orbit", _sol.SMALL_LINKS)["brief"]["timeline_id"]), "city": (_city(), "cityx")}
    for name, (html, t) in built.items():
        (d / f"{name}.html").write_text(html, encoding="utf-8")
        PAGES[name] = (f"{name}.html", ID_PATTERNS["hl_key"].format(tid=t) + "-bg" if t else None)
    (d / "home.html").write_text(pages.build_home(HOME), encoding="utf-8")
    (d / "reports.html").write_text(pages.build_reports([], ""), encoding="utf-8")
    PAGES["home"] = ("home.html", pages.HOME_BG_KEY)
    PAGES["reports"] = ("reports.html", pages.HOME_BG_KEY)
    shutil.copytree(ASSETS, d / "bg" / f"v{bg.BG_V}")
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


@pytest.fixture(params=["webkit"])
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


# ── helpers ─────────────────────────────────────────────────────────────────

# Every box inside the panel against the edge it must not touch: the picker's body clips at its own edge, and a ring, a border or a tile that
# reaches it is cut (Luke's shot: the right column of tiles and the style switch's last segment). Pieces in the body keep 2px of air from the
# body's edges; the rest (head, credit line) stay inside the panel's border.
OVERFLOW_JS = r"""(function(){
  var p=document.getElementById('bg-panel'); if(!p) return {err:'no panel'};
  var pr=p.getBoundingClientRect(), cs=getComputedStyle(p), body=p.querySelector('.bg-body'), br=body.getBoundingClientRect();
  var PL=pr.left+parseFloat(cs.borderLeftWidth), PR=pr.right-parseFloat(cs.borderRightWidth), bad=[], seen=0;
  var BL=br.left+2, BR=br.left+body.clientWidth-2;
  function name(e){ return e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(typeof e.className==='string'&&e.className?'.'+e.className.trim().split(/\s+/).join('.'):''); }
  p.querySelectorAll('*').forEach(function(e){
    var r=e.getBoundingClientRect(), s=getComputedStyle(e);
    if(!r.width || s.display==='none' || s.visibility==='hidden' || e.classList.contains('bg-sec')) return;     // (a section is a padding box: what is in it is measured)
    seen++;
    var inBody=body.contains(e) && e!==body, L=inBody ? BL : PL, R=inBody ? BR : PR;
    if(r.right>R+.5 || r.left<L-.5) bad.push({el:name(e), left:Math.round(r.left*10)/10, right:Math.round(r.right*10)/10, from:Math.round(L*10)/10, to:Math.round(R*10)/10});
  });
  return {seen:seen, bad:bad.slice(0,6), hscroll:body.scrollWidth-body.clientWidth, panelW:Math.round(pr.width), panelOn:pr.right<=innerWidth+1 && pr.left>=-1};
})()"""


def _go(browser, site, page, width, style=None, saved=None, dark=False, height=900, detail=False):
    """Open a page of the site in `style` (classic|retro|holo) with `saved` as its kept background; return (page, ctx, errors)."""
    phone = width < 500
    ctx = browser.new_context(viewport={"width": width, "height": height}, has_touch=phone, is_mobile=phone, device_scale_factor=2 if phone else 1,
                              user_agent=IPHONE if phone else None)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    f, key = PAGES[page]
    pg.goto(site + "/" + f)
    pg.wait_for_timeout(300)
    pg.evaluate("localStorage.clear()")
    sk = (key[:-3] if key.endswith("-bg") else key) + "-style"
    if style and page != "system":
        pg.evaluate("([k,v])=>localStorage.setItem(k,v)", [sk, style])
    if saved is not None and key:
        pg.evaluate("([k,v])=>localStorage.setItem(k,JSON.stringify({v:v,t:Date.now()}))", [key, saved])
    if dark:
        pg.evaluate("localStorage.setItem('alto-theme-v1','dark')")
    pg.reload()
    pg.wait_for_timeout(1800)
    return pg, ctx, errors


def _shot(pg, *name):
    """SCENE_SHOTS=<dir> keeps a picture of each panel the fit tests open (what Art looks at)."""
    import os
    d = os.environ.get("SCENE_SHOTS")
    if d:
        os.makedirs(d, exist_ok=True)
        pg.screenshot(path=os.path.join(d, "-".join(str(n) for n in name) + ".png"))


def _open_panel(pg):
    tab = pg.query_selector("#bg-toggle")
    assert tab, "no Scene tab"
    pg.evaluate("document.getElementById('bg-toggle').click()") if pg.evaluate("innerWidth") < 641 or pg.evaluate("document.documentElement.classList.contains('mobile')") else tab.click()
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.getElementById('bg-panel').classList.contains('open')")


# ── F3a: nothing runs off the panel ─────────────────────────────────────────

@pytest.mark.parametrize("width", [1400, 700, 390])
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_the_panel_holds_everything_inside_it_in_every_style_at_every_width(browser, site, style, width):
    pg, ctx, errors = _go(browser, site, "outline", width, style=style)
    _open_panel(pg)
    r = pg.evaluate(OVERFLOW_JS)
    _shot(pg, "outline", style, width)
    assert r["seen"] > 4, r
    assert not r["bad"], (style, width, r)
    assert r["hscroll"] <= 1, (style, width, r)
    assert not _real(errors), errors
    ctx.close()


@pytest.mark.parametrize("width", [1400, 390])
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
@pytest.mark.parametrize("page", ["home", "reports"])
def test_the_homepage_and_reports_panels_fit_too(browser, site, page, style, width):
    if page == "reports" and style == "retro":
        pytest.skip("the reports page has no Retro")
    pg, ctx, errors = _go(browser, site, page, width, style=style)
    _open_panel(pg)
    r = pg.evaluate(OVERFLOW_JS)
    _shot(pg, page, style, width)
    assert r["seen"] > 4, r
    assert not r["bad"], (page, style, width, r)
    assert r["hscroll"] <= 1, (page, style, width, r)
    ctx.close()


def test_holographic_is_dark_only_so_its_credit_line_never_says_light(browser, site):
    pg, ctx, errors = _go(browser, site, "outline", 1400, style="holo")
    _open_panel(pg)
    pg.click('.bg-tile[data-bg="h-targeting"]')
    pg.wait_for_timeout(400)
    foot = pg.evaluate("document.querySelector('#bg-panel .bg-foot').textContent")
    assert "Targeting" in foot and "light" not in foot.lower() and "dark" not in foot.lower(), foot
    tip = pg.evaluate("document.querySelector('#bg-style .bg-segb[data-sty=holo]').title").lower()
    assert "light or dark" not in tip and "light and dark" not in tip, tip
    ctx.close()


# ── F3b: which pages offer what ─────────────────────────────────────────────

# the picture of the page as drawn: the saved choice's mark on <html>, and what is behind everything
DRAWN_JS = r"""(function(){
  var r=document.documentElement, pb=document.getElementById('page-bg'), p=document.getElementById('bg-panel');
  function col(e){ return e ? getComputedStyle(e).backgroundColor : ''; }
  function lit(w){ if(!pb) return false; var s=getComputedStyle(pb,w); return s.display!=='none' && s.backgroundImage!=='none' && s.content!=='none'; }
  var vis=[].filter.call(p ? p.querySelectorAll('.bg-body > .bg-sec') : [], function(s){ return getComputedStyle(s).display!=='none' && !s.classList.contains('bg-auto'); }).map(function(s){ return s.id || (s.querySelector('.bg-h')||{}).textContent || s.className; });
  var det=document.getElementById('detail-page');
  return {id:window._altoBgId||'', bgOn:r.classList.contains('alto-bg'), map:r.classList.contains('alto-bg-map'), only:!!(p && p.classList.contains('bg-only')),
    html:col(r), body:col(document.body), pb:col(pb), before:lit('::before'), after:pb ? getComputedStyle(pb,'::after').display : '', detail:col(det), sections:vis,
    retro:r.classList.contains('alto-retro')||r.classList.contains('sk-retro'), holo:r.classList.contains('alto-holo'), dp:r.classList.contains('detail-open')};
})()"""
BLACK = ("rgb(0, 0, 0)", "rgba(0, 0, 0, 0)")

NODE = {"outline": "formation", "lanes": "tomas", "atlas": "erie", "blueprint": "a", "city": "erie", "system": "u1-p1"}
AUTO = ("atlas", "blueprint", "city", "system")
ALL = ("outline", "lanes") + AUTO + ("home",)


def _drawn(pg):
    return pg.evaluate(DRAWN_JS)


def _detail(pg, page, on=True):
    if on:
        pg.evaluate("(id)=>showDetail('node', id)", NODE[page])
    else:
        pg.evaluate("()=>{ if(typeof closeDetail==='function') closeDetail(); else if(typeof showTimeline==='function') showTimeline(); }")
    pg.wait_for_timeout(900)


def _style_of(pg, page, style):
    """Put a page in a style (a System through its own switch)."""
    if page == "system" and not pg.evaluate("!!window._altoStyleC && !!window._altoSolarBar"):      # (Style C, the default: the page style is the Scene panel's, like every format's)
        pg.evaluate("s=>window._altoSolarStyles.set(s)", {"classic": "system", "retro": "retro", "holo": "holo"}[style])
        pg.wait_for_timeout(1500)
    else:
        pg.evaluate("s=>window._altoStyle.set(s)", style)
        pg.wait_for_timeout(1200)


@pytest.mark.parametrize("page", ALL)
def test_retro_is_plain_black_whatever_is_saved_and_the_choice_returns(browser, site, page):
    f, key = PAGES[page]
    pg, ctx, errors = _go(browser, site, page, 1400, style="classic", saved=PHOTO)
    if page not in AUTO:
        assert _drawn(pg)["id"] == PHOTO                      # (before: Classic draws it)
    _style_of(pg, page, "retro")
    for detail in ([False, True] if page in NODE else [False]):
        if detail:
            _detail(pg, page)
        d = _drawn(pg)
        _shot(pg, "retro-with-a-saved-photo", page, "detail" if detail else "main")
        assert d["retro"] and not d["bgOn"] and not d["id"] and not d["map"], (page, detail, d)
        assert d["html"] in BLACK or d["body"] in BLACK or d["pb"] in BLACK, (page, detail, d)
        assert not d["before"] and d["after"] in ("none", ""), (page, detail, d)
        if page != "home" and detail:
            assert d["detail"] in BLACK, (page, d)
    if page in NODE:
        _detail(pg, page, False)
    _open_panel(pg)
    d = _drawn(pg)
    _shot(pg, "retro-scene-panel", page)
    assert d["only"] and d["sections"] in (["bg-style"],), (page, d)          # the style picker, nothing else
    # the choice is kept and returns in Classic
    _style_of(pg, page, "classic")
    d = _drawn(pg)
    if page not in AUTO:
        assert d["bgOn"] and d["id"] == PHOTO, (page, d)
    assert json.loads(pg.evaluate("k=>localStorage.getItem(k)", key))["v"] == PHOTO, page
    assert not _real(errors), errors
    ctx.close()


@pytest.mark.parametrize("page", AUTO)
def test_a_page_that_makes_its_own_background_offers_only_the_style_picker_until_a_detail_page_opens(browser, site, page):
    f, key = PAGES[page]
    pg, ctx, errors = _go(browser, site, page, 1400, style="classic", saved=PHOTO)
    _open_panel(pg)
    d = _drawn(pg)
    _shot(pg, "own-background-main", page)
    assert d["only"] and d["sections"] == ["bg-style"], (page, d)
    assert d["id"] != PHOTO and (not d["bgOn"] or d["map"]), (page, d)         # the saved choice is not drawn (a city's own map ground is)
    _detail(pg, page)
    d = _drawn(pg)
    assert d["dp"] and d["bgOn"] and d["id"] == PHOTO, (page, d)               # a detail page takes it
    _open_panel(pg)
    d = _drawn(pg)
    _shot(pg, "own-background-detail", page)
    assert not d["only"] and len(d["sections"]) > 3, (page, d)                 # and the full options
    _detail(pg, page, False)
    assert _drawn(pg)["id"] != PHOTO
    assert json.loads(pg.evaluate("k=>localStorage.getItem(k)", key))["v"] == PHOTO, page
    assert not _real(errors), errors
    ctx.close()


@pytest.mark.parametrize("style", ["classic", "holo"])
@pytest.mark.parametrize("page", ["outline", "lanes", "home"])
def test_classic_and_holographic_keep_their_options_where_the_page_takes_them(browser, site, page, style):
    pg, ctx, errors = _go(browser, site, page, 1400, style=style, saved=PHOTO)
    d = _drawn(pg)
    assert d["bgOn"] and d["id"] == PHOTO and d["holo"] == (style == "holo"), (page, style, d)
    _open_panel(pg)
    d = _drawn(pg)
    assert not d["only"] and "bg-style" in d["sections"], (page, style, d)
    if style == "holo":     # Holographic lists only its own backgrounds (Art PASS, Luke L-1105-155249): the style picker, the Holographic tiles and the Import tile (#bg-yours, never removed)
        assert d["sections"] == ["bg-style", "Holographic", "bg-yours"], (page, style, d)      # (Luke, 2026-11-10: "Only the holo backgrounds should be available": the Alto wallpaper section is gone too)
    else:
        assert len(d["sections"]) > 4, (page, style, d)
    assert not _real(errors), errors
    ctx.close()


def test_holographic_on_an_atlas_shows_the_style_picker_only(browser, site):
    pg, ctx, errors = _go(browser, site, "atlas", 1400, style="holo", saved=PHOTO)
    _open_panel(pg)
    d = _drawn(pg)
    assert d["holo"] and d["only"] and d["sections"] == ["bg-style"] and not d["bgOn"], d
    ctx.close()


# ── what a page carries (no browser) ────────────────────────────────────────

def _auto(html):
    return re.search(r"AUTO=(\d)", re.search(r'<script id="alto-bg-head">(.*?)</script>', html, re.S).group(1)).group(1)


def test_only_the_formats_that_make_their_own_background_are_marked_for_it():
    assert _auto(_brief_page("outline")[0]) == "0" and _auto(_brief_page("lanes")[0]) == "0"
    assert _auto(_wld.built()[0]) == "1" and _auto(_bld.built()[0]) == "1"                  # a Memory Atlas, a Blueprint
    assert _auto(_city()) == "1" and _auto(_sol._page()) == "1"                              # a city map, a System
    assert _auto(pages.build_home([])) == "0" and _auto(pages.build_reports([], "")) == "0"


def test_a_chosen_background_is_drawn_only_where_the_page_takes_it():
    head = bg.head_block("alto-hl-x-bg", retro=True, auto=True)
    assert "function only()" in head and "function want()" in head
    assert "r.classList.contains('alto-retro')||r.classList.contains('sk-retro')" in head.replace(" ", "")     # Retro, whatever the format
    assert "r.classList.contains('detail-open')||r.classList.contains('summary-open')" in head.replace(" ", "")   # a page opened from the format
    ui = bg.ui_block("This timeline", rail=True)
    assert "bg-only" in ui and "bg-auto" in ui and "bg-solar-seg" in ui
    assert "for the light and the dark theme" in ui and "alto-holo" in ui                      # (and Holographic never says it)
