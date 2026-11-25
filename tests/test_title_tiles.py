"""The title header (a hanging tab with the format symbol; Luke 2026-11-05, "1, B") and the New / Import tiles (a frame; "2, A").

Non-browser: what the pages and the hosted scripts carry. Browser (WebKit and Chromium; skipped without Playwright): the tab hangs from the
top edge on the homepage, Reports and a timeline, in Classic, Retro and Holographic; the format's symbol sits beside the name; a phone keeps
its own header; the New tiles and the Import tile lose their dashed outline in Retro and Holographic (Classic keeps it) and their plus and
words are centred in them."""
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
    {"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e", "#10b981"]},
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
    assert 'id="alto-title-tab"' in t and "border-radius:0 0 14px 14px" in t and "--tt-w:0px" in t   # (Luke 2026-11-22/24: no format symbol in a page's title tab)
    tpl = json.dumps(format_symbols.SYMBOLS["outline"][1])
    assert t.count(tpl) == 1 and "--tt-sym:" not in t and "stroke='%231a1a2e'" not in t        # (the drawing once; the inks are put in by the script, checked in a browser below)
    assert json.dumps(format_symbols.SYMBOLS["lanes"][1]) in _build("lanes") and "currentColor" not in t.split('id="alto-title-tab"')[1].split("</style>")[0]
    s = _build("outline", layout="solar")
    assert json.dumps(format_symbols.SYMBOLS["system"][1]) in s and "html.alto-stars:not(.mobile) #title-bar #title-text" in s
    assert "html.alto-stars:not(.mobile) #title-bar #title-text" not in t


@pytest.mark.parametrize("name,key", [("t", "outline"), ("l", "lanes"), ("s", "system")])
def test_the_one_drawing_gets_the_same_url_in_every_ink_as_ever(browser, site, name, key):
    pg = _open(browser, site, name, "classic")
    got = pg.evaluate("n => ['sym','syd','syr','syh','syk'].map(k => getComputedStyle(document.documentElement).getPropertyValue('--tt-' + k).trim())")
    want = {k: format_symbols.ink_uri(key, v) for k, v in title_tab.INKS.items()}
    if key == "system":
        want["sym"] = format_symbols.ink_uri(key, "#eef2ff")
        want["syd"] = want["sym"]
    assert got == [want[k] for k in ("sym", "syd", "syr", "syh", "syk")]
    pg.close()


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
    assert "#title-bar #title-text:not(#_){--tt-pt:10px" in r and "clip-path:none" in r and "clip-path:polygon" not in r.split("#title-text:not(#_){--tt-pt:10px")[1][:600]
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


PRIV = [{"key": "k1", "title": "Torts", "project": "Law", "units": ["#4a9eff", "#f43f5e", "#10b981"], "fmt": "timeline"},
        {"key": "k2", "title": "Contracts", "project": "Law", "units": ["#f43f5e"], "fmt": "outline"},
        {"key": "k3", "title": "Atlas", "project": "Law", "units": ["#10b981"], "fmt": "world"}]


@pytest.mark.parametrize("style,dark", [("classic", False), ("classic", True), ("holo", False), ("retro", False)])
def test_every_home_tile_wears_a_visible_glyph_plate_and_says_its_count_once(browser, site, style, dark):
    """Luke's v2 sheet: a plate inside every card, in Classic, Classic dark, Holo and Retro, for the course tiles the page ships and the account's own."""
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s');%s}catch(e){}" % (style, "localStorage.setItem('alto-theme-v1','dark')" if dark else ""))
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(1500)
    pg.evaluate("(P) => { drawPrivate(P); }", PRIV)
    pg.wait_for_timeout(1500)
    pg.add_style_tag(content="*,*::before,*::after{animation:none !important;transition:none !important}")
    n = pg.evaluate("document.querySelectorAll('.course-tile:not(.new-tile)').length")
    assert n == 5, n                                                       # (two the page ships, three the account's)
    for i in range(n):
        d = pg.evaluate("""(i) => { const t = document.querySelectorAll('.course-tile:not(.new-tile)')[i], e = t.querySelector('.tile-emblem');
            if(!e) return {none: true}; const r = e.getBoundingClientRect(), s = getComputedStyle(e), sv = e.querySelector('svg'), sr = sv && sv.getBoundingClientRect(), tr = t.getBoundingClientRect(),
              sub = t.querySelector('.tile-sub'), ss = sub && getComputedStyle(sub), c = t.querySelector('.t-units');
            const vis = sub && e.contains(sub) && ss.display !== 'none' && !sub.querySelector('.priv-sym') && sub.textContent.trim();   // (Classic keeps its count under the title, off the plate)
            return {w: r.width, h: r.height, inside: r.left >= tr.left && r.right <= tr.right && r.top >= tr.top && r.bottom <= tr.bottom, op: +s.opacity, vis: s.visibility, disp: s.display,
                    sv: sr ? [sr.width, sr.height] : null, hasMark: !!(sv && (sv.querySelector('mask') || sv.querySelector('path,circle,rect'))), plateText: vis || '',
                    box: {x: r.left, y: r.top, w: r.width, h: r.height}}; }""", i)
        assert not d.get("none"), (style, dark, i, "no plate")
        assert d["w"] >= 40 and d["h"] >= 40 and d["inside"] and d["op"] > 0.2 and d["vis"] == "visible" and d["disp"] != "none" and d["sv"] and d["sv"][0] >= 40 and d["hasMark"], (style, dark, i, d)
        assert d["plateText"] == "", (style, dark, i, "a plain-text count over the plate's corner", d)
        b = d["box"]
        clip = {"x": b["x"], "y": b["y"], "width": b["w"], "height": b["h"]}
        shown = pg.screenshot(clip=clip)
        pg.evaluate("(i) => document.querySelectorAll('.course-tile:not(.new-tile)')[i].querySelector('.tile-emblem').style.visibility = 'hidden'", i)
        hidden = pg.screenshot(clip=clip)
        pg.evaluate("(i) => document.querySelectorAll('.course-tile:not(.new-tile)')[i].querySelector('.tile-emblem').style.visibility = ''", i)
        assert shown != hidden, (style, dark, i, "the plate draws no pixel")
    pg.close()


@pytest.mark.parametrize("dark", [False, True])
def test_classic_cards_stay_about_as_tall_as_before_the_plates_with_a_small_plate_in_the_corner(browser, site, dark):
    """Luke 2026-11-18, "file cards in classic are too tall now" (1.9.244 made them 190px; 1.9.243's were 120px for a card the page ships and 145px for an account's).
    At 1440: each card within 10% of its 243 height, the title on one line where it fits, a 56-70px plate inside the top-right corner, the unit count shown once."""
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','classic');%s}catch(e){}" % ("localStorage.setItem('alto-theme-v1','dark')" if dark else ""))
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(1500)
    pg.evaluate("(P) => { drawPrivate(P); }", [dict(PRIV[0], title="Civil Procedure", units=["#4a9eff"] * 7)] + PRIV[1:])
    pg.wait_for_timeout(1500)
    cards = pg.evaluate("""() => [...document.querySelectorAll('.course-tile:not(.new-tile)')].map(t => { const r = t.getBoundingClientRect(), ti = t.querySelector('.tile-title'), e = t.querySelector('.tile-emblem').getBoundingClientRect(),
        sub = t.querySelector('.tile-sub'), lh = parseFloat(getComputedStyle(ti).fontSize) * 1.5;
        return {h: r.height, oneLine: ti.getBoundingClientRect().height < lh, ew: e.width, top: e.top - r.top, right: r.right - e.right, left: e.left - r.left, bottom: e.bottom - r.top, w: r.width,
                subText: sub && getComputedStyle(sub).display !== 'none' ? sub.textContent.trim() : '', lock: !!(sub && sub.querySelector('.priv-sym'))}; })""")
    assert len(cards) == 5
    for i, c in enumerate(cards):
        base = 120 if i < 2 else 145                              # (the page's own cards, then the account's: their 1.9.243 heights)
        assert c["h"] <= base * 1.10 and c["h"] >= base * 0.9, (dark, i, c)
        assert c["oneLine"], (dark, i, c)
        assert 56 <= c["ew"] <= 70 and 0 <= c["right"] <= 24 and 0 <= c["top"] <= 50 and c["bottom"] < c["h"] * 0.9 and c["left"] > c["w"] * 0.5, (dark, i, c)
        assert re.fullmatch(r"\d+ units?", c["subText"]) or c["lock"], (dark, i, c)     # (a card the page ships says its count; an account's says its lock)
    pg.close()


@pytest.mark.parametrize("dark", [False, True])
def test_classic_phone_cards_are_back_to_about_their_old_height_with_the_plate_clear_of_the_buttons(browser, site, dark):
    """The same ask on a phone (390 wide; Luke's asks ship to phones): 1.9.244 made a card 204px against 156px before the plates. Now within 10% of 156 or shorter
    (never taller), a 50-66px plate wholly inside the card, and no button touching it."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = ctx.new_page()
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','classic');%s}catch(e){}" % ("localStorage.setItem('alto-theme-v1','dark')" if dark else ""))
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(1500)
    pg.evaluate("(P) => { drawPrivate(P); }", PRIV)
    pg.wait_for_timeout(1500)
    cards = pg.evaluate("""() => [...document.querySelectorAll('.course-tile:not(.new-tile)')].map(t => { const r = t.getBoundingClientRect(), e = t.querySelector('.tile-emblem').getBoundingClientRect(),
        hit = (a, b) => !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
        return {h: r.height, ew: e.width, inside: e.left >= r.left && e.right <= r.right && e.top >= r.top && e.bottom <= r.bottom,
                btn: [...t.querySelectorAll('.tile-reports,.tile-share,.tile-download')].map(b => { const q = b.getBoundingClientRect(); return {w: q.width, h: q.height, touchesPlate: hit(q, e), left: q.left - r.left}; })}; })""")
    assert len(cards) == 5
    for i, c in enumerate(cards):
        assert c["h"] <= 156 * 1.10 and c["h"] >= 120, (dark, i, c)
        assert 50 <= c["ew"] <= 66 and c["inside"], (dark, i, c)
        assert all(not b["touchesPlate"] and b["w"] >= 28 and b["h"] >= 28 and b["left"] >= 10 for b in c["btn"] if b["w"]), (dark, i, c)      # (a phone draws no download button)
    ctx.close()


@pytest.mark.parametrize("style,dark", [("classic", False), ("classic", True), ("holo", False), ("retro", False)])
@pytest.mark.parametrize("phone", [False, True])
def test_the_study_plan_line_is_a_real_button_and_never_makes_a_card_taller(browser, site, style, dark, phone):
    """Luke 2026-11-19, "make the study plan button more of a button" (1.9.250): "+ Make a study plan" and "Study plan [Today 2]" are a tinted pill (Classic), a glass outline
    (Holo) or a gold-ruled box (Retro), with the + kept and hover and pressed states. A computer's page only (the line is hidden at 640 and under, as it always was: a phone card
    has no room for it and the cards must not grow). The card is exactly as tall as with the old plain text."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844} if phone else {"width": 1440, "height": 900}, has_touch=phone, is_mobile=phone, device_scale_factor=2 if phone else 1)
    pg = ctx.new_page()
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s');%s}catch(e){}" % (style, "localStorage.setItem('alto-theme-v1','dark')" if dark else ""))
    pg.goto(f"{site}/h.html")
    pg.wait_for_timeout(1500)
    pg.evaluate("(P) => { drawPrivate(P); }", [dict(PRIV[0], plan={"days": ["2099-01-01", "2099-01-02"]})] + PRIV[1:])
    pg.wait_for_timeout(1500)
    pg.add_style_tag(content="*,*::before,*::after{animation:none !important;transition:none !important}")
    q = """() => [...document.querySelectorAll('.course-tile:not(.new-tile) .sp-card')].map(e => { const s = getComputedStyle(e), t = e.closest('.course-tile').getBoundingClientRect();
        return {text: e.textContent.trim(), make: e.classList.contains('sp-make'), disp: s.display, h: e.getBoundingClientRect().height, bw: parseFloat(s.borderTopWidth), bg: s.backgroundColor, card: t.height}; })"""
    lines = pg.evaluate(q)
    assert len(lines) == 3 and [l["make"] for l in lines] == [False, True, True], lines
    if phone:
        assert all(l["disp"] == "none" for l in lines), lines            # (hidden at 640 and under, unchanged)
    else:
        for l in lines:
            assert l["disp"] != "none" and l["h"] >= 24 and (l["bw"] >= 1 or l["bg"] not in ("rgba(0, 0, 0, 0)", "transparent")), ("not a button", style, dark, l)
        assert lines[1]["text"].startswith("+ Make a study plan") and lines[0]["text"].startswith("Study plan"), lines
        pg.hover(".sp-card.sp-make")
        hov = pg.evaluate("getComputedStyle(document.querySelector('.sp-card.sp-make')).backgroundColor")
        assert hov != lines[1]["bg"], (style, dark, "no hover state", hov)
    base = {("classic", False): 150, ("classic", True): 132, ("holo", False): 170, ("holo", True): 215.9, ("retro", False): 172.5, ("retro", True): 221.9}[(style, phone)]
    assert all(abs(l["card"] - base) <= 1 for l in lines), (style, dark, phone, [l["card"] for l in lines], base)    # (the heights the cards had in 1.9.248, with the plain text: the button makes none taller)
    ctx.close()
