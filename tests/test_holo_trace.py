"""Holographic's "Alto" wordmark, traced by light on a loop (alto/build/holo_trace.py; Luke, 2026-11-05: "Alto logo should sort of be traced by a holo on loop as opposed to
spinning"; Art's look ORG/notes-art/holo-wordmark-trace.md). A cyan-white bead with a magenta ghost runs along the letters' outlines once every 7 s, then the wordmark
rests lit and still; the corner clef keeps its turn; Reduce Motion and print draw nothing; a phone has it too (Luke's standing phone yes, L-1105-160112@Board).
The code is in the hosted Holographic script, the page holds none of it. The browser parts are skipped when Playwright is not installed."""
import http.server
import json
import math
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds_import as bi, holo, holo_trace, pages, retro      # noqa: E402
from alto.build.builder import build_timeline, load_brief                            # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
HOME = [{"name": "Law", "pid": "p", "courses": [{"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff"]}]}]


def _outline():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


# ── by reading the rules ──

def test_the_trace_moves_a_dash_and_nothing_costly_is_on_it():
    c = holo_trace.CSS
    for banned in ("filter", "blur", "box-shadow", "mask", "drop-shadow", "background-clip"):
        assert banned not in c, banned
    j = holo_trace.WORD_JS
    assert "requestAnimationFrame" not in j and "setInterval" not in j and "feTurbulence" not in j
    assert "setInterval" not in holo_trace.JS and "feTurbulence" not in holo_trace.JS
    assert "strokeDashoffset" in j and ".animate(" in j and "steps(" in j      # 30 frames a second while it moves, nothing at all while it rests
    assert "perspective" not in c and "rotate" not in c and "scale" not in c and "animation" not in c       # it never spins; the script, not a CSS loop, runs each pass


def test_reduce_motion_print_and_a_hidden_tab_are_in_the_rules():
    c = holo_trace.CSS
    assert "@media (prefers-reduced-motion:reduce){.ho-trace{display:none !important}}" in c
    assert "@media print{.ho-trace{display:none !important}}html.printing .ho-trace{display:none !important}" in c
    assert "document.hidden" in holo_trace.JS and "hp-hid" in holo_trace.JS
    assert "matchMedia('(prefers-reduced-motion: reduce)')" in holo_trace.JS


def test_art_colours_and_timing():
    c = holo_trace.CSS
    assert "#e8fffd" in c and "rgb(255,95,210)" in c and "#12b5d6" in c and "rgb(214,40,170)" in c
    assert "stroke-width:3.5" in c and "stroke-width:5}" in c and "stroke-opacity:.45" in c and "stroke-opacity:.35" in c      # (Art ART-LOOK 7 Nov: the ghost no longer paints over the letter)
    assert holo_trace.LOOP == 7 and holo_trace.DELAY == 0.12 and "setTimeout(trPass, 7000)" in holo_trace.JS
    assert holo_trace.SWEEP == 40 and holo_trace.CORE == 0.06 and holo_trace.GHOST == 0.1


def test_it_rides_in_the_hosted_script_and_the_page_holds_none_of_it():
    pg = [_outline(), pages.build_home(HOME), pages.build_reports([{"title": "X", "href": "x", "sub": "", "courseId": "a", "reports": True, "units": []}], "a")]
    for needle in ("ho-trace", "trPass", "alto-holo-trace", "trKeys"):
        assert needle in holo.ASSET, needle
        assert all(needle not in p for p in pg), needle


# ── in a browser ──

@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("holotrace")
    (d / "t.html").write_text(_outline(), encoding="utf-8")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    (d / "r.html").write_text(pages.build_reports([{"title": "X", "href": "x", "sub": "", "courseId": "a", "reports": True, "units": []}], "a"), encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    n, t = holo.holo_asset()
    (d / "holo" / n).write_text(t, encoding="utf-8")
    n, t = retro.retro_asset()
    (d / "retro" / n).write_text(t, encoding="utf-8")
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
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


# The script starts the next pass with setTimeout(trPass, 7000) off the wall clock, so a test that scrubs a pass by hand (_at) and then keeps screenshotting for several
# seconds on a starved Mac races that second pass (live, un-paused beads in the "rest" frames). Those tests open the page with `frozen=True`: the page's timers are held
# (Playwright's clock) once the first pass is built, and the test releases the next pass itself with _next_pass(). Nothing a test asserts changes.
NAV_MS = 120000          # (a 1.4 MB page parsing under 3 other browser seats on an 8 GB Mac has run past Playwright's 30 s load default; the load is not what the test checks)


def _freeze(pg):
    pg.clock.pause_at(pg.evaluate("Date.now()") + 500)


def _next_pass(pg):
    pg.clock.run_for(7000)
    pg.wait_for_timeout(250)


def _open(browser, site, page="t.html", phone=False, width=None, reduce=False, dark=None, style="holo", wait=900, frozen=False, init=None):
    ctx = browser.new_context(viewport={"width": 390 if phone else (width or 1400), "height": 844 if phone else 860}, has_touch=phone, is_mobile=phone,
                              user_agent=IPHONE if phone else None, reduced_motion="reduce" if reduce else "no-preference")
    ctx.set_default_navigation_timeout(NAV_MS)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    if init:
        pg.add_init_script(init)
    if frozen:
        pg.clock.install()
    pg.goto(site + "/" + page)
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear()")
    if dark is not None:
        pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false"))
    pg.evaluate("window._altoStyle.set('%s')" % style)
    pg.wait_for_timeout(wait)
    if frozen:
        _freeze(pg)
    return pg, ctx, errors


BOXES = """(function(){
  var w=document.querySelector('svg.brand-word'), o=document.querySelector('svg.ho-trace');
  if(!w||!o) return null;
  var a=w.getBoundingClientRect(), b=o.getBoundingClientRect();
  return {w:[a.left,a.top,a.width,a.height], o:[b.left,b.top,b.width,b.height]};
})()"""
LIVE = "document.getAnimations().filter(a=>a.playState==='running' && a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('.ho-trace')).length"


def _same(pg):
    b = pg.evaluate(BOXES)
    assert b, "no overlay"
    assert all(abs(x - y) <= 0.5 for x, y in zip(b["w"], b["o"])), b
    return b


def test_desktop_the_overlay_sits_exactly_on_the_wordmark_and_animates_its_twelve_paths(browser, site):
    pg, ctx, errors = _open(browser, site)
    assert pg.evaluate("document.querySelectorAll('svg.ho-trace').length") == 1
    assert pg.evaluate("document.querySelector('svg.brand-word').nextElementSibling.classList.contains('ho-trace')")
    assert pg.evaluate("document.querySelectorAll('.ho-trace path').length") == 12     # six contours, a ghost and a core of each
    assert pg.evaluate(LIVE) >= 6
    b = _same(pg)
    assert 20 < b["w"][3] < 27 and abs(b["w"][2] / b["w"][3] - 190.7 / 85.1) < 0.02, b
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-trace')).pointerEvents") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-trace path')).pointerEvents") == "none"       # (clear_top.py turns pointer events back on for an svg's children)
    assert pg.evaluate("document.querySelector('.ho-trace').getAttribute('aria-hidden')") == "true"
    # the title bar's three cells did not move: the overlay is out of the grid's flow
    assert pg.evaluate("[...document.querySelectorAll('#title-bar > *')].filter(e=>getComputedStyle(e).position!=='absolute').map(e=>Math.round(e.getBoundingClientRect().top)).join()") != ""
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("width,zoom", [(1400, "1"), (1000, "1"), (1400, "0.8"), (1000, "0.8")])
def test_desktop_the_overlay_follows_the_wordmark_at_two_widths_and_two_zooms(browser, site, width, zoom):
    pg, ctx, errors = _open(browser, site, width=width)
    pg.evaluate("document.documentElement.style.zoom='%s'; window.dispatchEvent(new Event('resize'))" % zoom)
    pg.wait_for_timeout(700)
    _same(pg)
    assert not errors, errors
    ctx.close()


def test_the_homepage_and_a_hover_keep_the_overlay_on_the_word(browser, site):
    pg, ctx, errors = _open(browser, site, page="h.html")
    _same(pg)
    pg.hover("svg.brand-word")
    pg.wait_for_timeout(300)
    _same(pg)
    assert pg.evaluate(LIVE) >= 6
    assert not errors, errors
    ctx.close()


def test_the_wordmark_never_turns_and_the_page_glyph_hands_its_turn_to_the_tube(browser, site):
    pg, ctx, errors = _open(browser, site)
    names = pg.evaluate("document.getAnimations().map(a=>[a.animationName||'', a.effect.target.closest('svg.brand-mark')?'mark':a.effect.target.closest('svg.brand-word')?'word':a.effect.target.closest('.ho-trace')?'trace':'other'])")
    assert not [n for n in names if n[1] == "mark"], names                       # the page's own glyph no longer turns: the tube (below) does
    assert not [n for n in names if n[1] == "word"], names
    assert all(n[0] == "" for n in names if n[1] == "trace"), names                # (the script's own animations, not a CSS loop)
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-word')).animationName") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-word')).transform") == "none"
    ctx.close()


def _at(pg, ms):
    pg.evaluate("t=>document.getAnimations().filter(a=>a.effect.target.closest&&a.effect.target.closest('.ho-trace')).forEach(a=>{a.pause();a.currentTime=t;})", ms)
    pg.wait_for_timeout(120)


def _lit_dashes(pg):
    """how many of the six core contours show a bead right now (their dash overlaps the outline)"""
    return pg.evaluate("""[...document.querySelectorAll('.ho-trace .tc')].map(p=>{
      var cs=getComputedStyle(p), off=parseFloat(cs.strokeDashoffset), len=parseFloat(cs.strokeDasharray), L=p.getTotalLength();
      return (-off+len>0.5 && -off<L-0.5) ? 1 : 0; })""")


def test_a_pass_walks_the_letters_left_to_right_then_the_wordmark_rests(browser, site):
    pg, ctx, errors = _open(browser, site, frozen=True)
    seen = []
    for ms in (200, 900, 1600, 2300, 2700):
        _at(pg, ms)
        seen.append(_lit_dashes(pg))
    assert any(any(s) for s in seen[:4]), seen
    first = [next((i for i, v in enumerate(s) if v), None) for s in seen]
    firsts = [f for f in first if f is not None]
    assert firsts == sorted(firsts), first                                     # never goes back along the word
    for ms in (3000, 5000, 6900):                                              # the rest: no bead anywhere, not at the start of the A either
        _at(pg, ms)
        assert not any(_lit_dashes(pg)), ms
    # the repeat: the script starts the next pass 7 s after the first (the page's clock is held, so release it)
    _next_pass(pg)
    assert pg.evaluate(LIVE) >= 6
    ctx.close()


def test_the_rest_frame_is_the_static_wordmark_pixel_for_pixel(browser, site):
    pg, ctx, errors = _open(browser, site, frozen=True)
    _at(pg, 900)
    box = pg.evaluate("(()=>{var r=document.querySelector('svg.brand-word').getBoundingClientRect();return {x:r.left-8,y:r.top-8,width:r.width+16,height:r.height+16};})()")
    mid = pg.screenshot(clip=box)
    _at(pg, 5000)
    with_trace = pg.screenshot(clip=box)
    pg.evaluate("document.querySelector('.ho-trace').style.display='none'")
    pg.wait_for_timeout(150)
    without = pg.screenshot(clip=box)
    assert with_trace == without
    assert mid != without                                                       # and a pass does draw something
    ctx.close()


def test_the_rest_leaves_no_trace_pixel_at_3x_and_the_loop_still_runs(browser, site):
    """Art 1111: 241 trace pixels stayed frozen through the rest (stubs on l, t, o): 'both' held a dash that the chord-short length never moved off the path"""
    ctx = browser.new_context(viewport={"width": 1400, "height": 860}, device_scale_factor=3)
    ctx.set_default_navigation_timeout(NAV_MS)
    pg = ctx.new_page()
    pg.clock.install()
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(900)
    _freeze(pg)
    box = pg.evaluate("(()=>{var r=document.querySelector('svg.brand-word').getBoundingClientRect();return {x:r.left-6,y:r.top-4,width:r.width+12,height:r.height+8};})()")
    _at(pg, 900)
    mid = pg.screenshot(clip=box)
    for ms in (3000, 4400, 6900):
        _at(pg, ms)
        with_trace = pg.screenshot(clip=box)
        pg.evaluate("document.querySelector('.ho-trace').style.visibility='hidden'")
        pg.wait_for_timeout(120)
        without = pg.screenshot(clip=box)
        pg.evaluate("document.querySelector('.ho-trace').style.visibility=''")
        assert with_trace == without, ms
    # no animation holds its end frame: after a pass each dash is back at its base offset
    assert pg.evaluate("document.getAnimations().filter(a=>a.effect.target.closest&&a.effect.target.closest('.ho-trace')).every(a=>a.effect.getComputedTiming().fill==='backwards')")
    assert mid != without                                                       # a pass still draws
    _next_pass(pg)
    assert pg.evaluate(LIVE) >= 1                                              # and the loop still runs (the paused first pass is not counted: these are the second pass)
    ctx.close()


def test_reduce_motion_builds_nothing_and_removes_it_live(browser, site):
    pg, ctx, errors = _open(browser, site, reduce=True)
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 0
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo')")
    pg.emulate_media(reduced_motion="no-preference")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 1
    pg.emulate_media(reduced_motion="reduce")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 0
    ctx.close()


def test_print_draws_no_trace(browser, site):
    pg, ctx, errors = _open(browser, site)
    pg.emulate_media(media="print")
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-trace')).display") == "none"
    pg.emulate_media(media="screen")
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-trace')).display") != "none"
    pg.evaluate("document.documentElement.classList.add('printing')")
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-trace')).display") == "none"
    ctx.close()


def test_classic_and_retro_have_none_and_going_back_removes_it(browser, site):
    pg, ctx, errors = _open(browser, site)
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 1
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 0
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 0
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 1
    _same(pg)
    ctx.close()


@pytest.mark.parametrize("dark", [True, False])
def test_the_phone_timeline_has_it_in_the_header_in_both_themes(browser, site, dark):
    pg, ctx, errors = _open(browser, site, phone=True, dark=dark)
    assert pg.evaluate("document.documentElement.classList.contains('mobile')")
    assert pg.evaluate("document.querySelector('.ho-trace').parentNode.id") == "nav"
    b = _same(pg)
    assert 20 < b["w"][3] < 22 and b["o"][0] + b["o"][2] <= 390 - 10, b          # 21 px high, 14 px in from the right edge
    assert b["o"][1] >= 0 and b["o"][1] + b["o"][3] <= 52, b                     # inside the 52 px band
    core = pg.evaluate("getComputedStyle(document.querySelector('.ho-trace .tc')).stroke")
    assert core == ("rgb(232, 255, 253)" if dark else "rgb(18, 181, 214)"), core
    assert pg.evaluate(LIVE) >= 6
    assert not errors, errors
    ctx.close()


def test_the_phone_homepage_has_it_and_the_phone_reports_page_has_none(browser, site):
    pg, ctx, errors = _open(browser, site, page="h.html", phone=True, dark=True)
    _same(pg)
    assert pg.evaluate(LIVE) >= 6
    ctx.close()
    pg, ctx, errors = _open(browser, site, page="r.html", phone=True, dark=True)
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-word')).display") == "none"
    assert pg.evaluate("document.querySelectorAll('.ho-trace').length") == 0           # the wordmark is not drawn there, so nothing is built
    assert not errors, errors
    ctx.close()


# ── part 2: the same trace on a card's border ──

def test_the_node_trace_is_four_beads_on_transform_alone():
    c = holo_trace.NODE_CSS
    for banned in ("filter", "blur", "box-shadow", "stroke-dashoffset", "mask"):
        assert banned not in c, banned
    assert holo_trace.NODE_MODE in ("full", "view", "walk")
    assert "@media (prefers-reduced-motion:reduce){.ho-nt{display:none !important}}" in c
    assert "@media print{.ho-nt{display:none !important}}html.printing .ho-nt{display:none !important}" in c
    assert ".node.dimmed .ho-nt" in c


def test_the_node_runner_is_one_small_light_in_one_colour():
    """Luke, 2026-11-12: "the running outline of nodes is a bit much, make it one color of light, just like the border of it is actually lighting up in one small runner\""""
    c = holo_trace.NODE_CSS
    # one colour a theme, and it is the border's own light at full strength (Holographic's --ho-ac2): no white bead, no magenta ghost, no second trail
    hexrgb = lambda h: ",".join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5))
    assert holo_trace.NODE_RGB == {k: hexrgb(holo.TOKENS[k]["ac2"]) for k in ("dark", "light")}
    assert c.count("--hn-c:") == 2 and "--hn-c:%s}" % holo_trace.NODE_RGB["light"] in c and "html.dark .ho-nt{--hn-c:%s}" % holo_trace.NODE_RGB["dark"] in c
    for gone in ("--hn-g", "--hn-d2", "255,95,210", "214,40,170", "#e8fffd", "#12b5d6", "#fff"):
        assert gone not in c, gone
    assert set(re.findall(r"rgba\((.*?\),[^)]*)\)", c)) == {"var(--hn-c),0", "var(--hn-c),1", "var(--hn-c),.4"} and c.count("rgba(") == 16 and "rgb(" not in c       # every paint on it is that one colour
    # a short stretch of the line that fades to nothing along the line at both ends (2 px on the border, in a 4 px halo of the same light and length)
    assert c.count("linear-gradient(var(--hn-a),rgba(var(--hn-c),0),rgba(var(--hn-c),1) 55%,rgba(var(--hn-c),1) 82%,rgba(var(--hn-c),0))") == 2
    assert c.count("linear-gradient(var(--hn-a),rgba(var(--hn-c),0),rgba(var(--hn-c),.4) 55%,rgba(var(--hn-c),.4) 82%,rgba(var(--hn-c),0))") == 2
    assert "/ 64px 2px no-repeat" in c and "/ 64px 4px no-repeat" in c and "/ 2px 64px no-repeat" in c and "/ 4px 64px no-repeat" in c
    assert holo_trace.RUNNER == 64 and holo_trace.RUNNER <= holo_trace.LEAD <= 80          # small, and each strip shorter than the old one (130)
    # calmer than the 2.8 s lap every 7 s it was, and never lit a larger share of the time
    assert holo_trace.NODE_PASS >= 4 and holo_trace.NODE_LOOP >= 10 and holo_trace.NODE_PASS / holo_trace.NODE_LOOP <= 2.8 / 7
    assert "v=per/4.5/1000" in holo_trace.JS and "loop=12000" in holo_trace.JS
    # the wordmark keeps its own bead and ghost
    assert "rgb(255,95,210)" in holo_trace.CSS and holo_trace.LOOP == 7


@pytest.mark.parametrize("dark", [True, False])
def test_a_card_runner_paints_one_colour_and_laps_calmly(browser, site, dark):
    pg, ctx, errors = _open(browser, site, wait=1800, phone=not dark, dark=dark)       # (Holographic is dark on a computer; a phone has the pale page too)
    r = pg.evaluate("""(()=>{var out=[]; [...document.querySelectorAll('.ho-nt')].slice(0,6).forEach(s=>{ [...s.children].forEach(i=>{ var cs=getComputedStyle(i), a=i.getAnimations()[0];
      out.push({k:i.className, bg:cs.backgroundImage, d:a.effect.getTiming().duration, n:i.getAnimations().length, f:cs.filter, sh:cs.boxShadow, kf:a.effect.getKeyframes().map(k=>Object.keys(k).filter(p=>!/^(offset|computedOffset|easing|composite)$/.test(p)).join())}); }); }); return out;})()""")
    assert len(r) >= 8, r
    want = holo_trace.NODE_RGB["dark" if dark else "light"].split(",")
    for x in r:
        cols = re.findall(r"rgba?\(([^)]*)\)", x["bg"])
        assert len(cols) == 8, x                                                # two gradients of four stops, nothing else painted
        assert all([p.strip() for p in col.split(",")][:3] == want for col in cols), x
        assert x["d"] == 12000 and x["n"] == 1 and x["f"] == "none" and x["sh"] == "none", x
        assert set(x["kf"]) == {"transform"}, x                                 # moved by transform alone
    assert not errors, errors
    ctx.close()


NODE_BOXES = """(function(){
  var cs=[...document.querySelectorAll('.node-card')].filter(c=>!c.closest('.compass-mini-node') && c.querySelector(':scope > .ho-nt'));
  return cs.map(c=>{var a=c.getBoundingClientRect(), o=c.querySelector(':scope > .ho-nt').getBoundingClientRect();
    return {card:[a.left,a.top,a.right,a.bottom], ov:[o.left,o.top,o.right,o.bottom], beads:c.querySelectorAll(':scope > .ho-nt > i').length,
            anims:c.querySelector(':scope > .ho-nt').getAnimations({subtree:true}).filter(x=>x.playState==='running').length};});
})()"""
ONSCREEN = """[...document.querySelectorAll('.node-card')].filter(c=>{var b=c.getBoundingClientRect();return b.width>0&&b.bottom>60&&b.top<innerHeight&&b.right>0&&b.left<innerWidth;}).length"""


def test_cards_in_view_wear_a_border_trace_that_sits_on_the_border(browser, site):
    pg, ctx, errors = _open(browser, site, wait=1800)
    mode = holo_trace.NODE_MODE
    boxes = pg.evaluate(NODE_BOXES)
    if mode == "walk":
        pg.wait_for_timeout(6000)
        assert pg.evaluate("document.querySelectorAll('.ho-nt').length") <= 2
    else:
        assert boxes, "no card has the trace"
        if mode == "full":
            assert len(boxes) == pg.evaluate("[...document.querySelectorAll('.node-card')].filter(c=>!c.closest('.compass-mini-node')).length")
        assert len(boxes) >= pg.evaluate(ONSCREEN) - 1
        for b in boxes:
            assert b["beads"] == 4 and b["anims"] == 4, b
            # the overlay is the card's border box with 2 px of room all round (a page zoom of .8 to 1)
            for k, sign in ((0, -1), (1, -1), (2, 1), (3, 1)):
                assert 1.2 <= sign * (b["ov"][k] - b["card"][k]) <= 2.6, b
    # the cards did not move for it, and it takes no pointer
    assert pg.evaluate("(()=>{var c=[...document.querySelectorAll('.node-card')][0], r=c.getBoundingClientRect(); var e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); return !e.closest('.ho-nt');})()")
    assert not errors, errors
    ctx.close()


def test_the_node_trace_goes_with_reduce_motion_print_and_the_style(browser, site):
    pg, ctx, errors = _open(browser, site, reduce=True, wait=1500)
    assert pg.evaluate("document.querySelectorAll('.ho-nt').length") == 0
    pg.emulate_media(reduced_motion="no-preference")
    pg.wait_for_timeout(1500)
    if holo_trace.NODE_MODE != "walk":
        assert pg.evaluate("document.querySelectorAll('.ho-nt').length") > 0
        pg.emulate_media(media="print")
        assert pg.evaluate("getComputedStyle(document.querySelector('.ho-nt')).display") == "none"
        pg.emulate_media(media="screen")
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.querySelectorAll('.ho-nt').length") == 0
    ctx.close()


def test_the_node_cards_keep_their_own_phase(browser, site):
    pg, ctx, errors = _open(browser, site, wait=1800)
    if holo_trace.NODE_MODE != "walk":
        t = pg.evaluate("[...document.querySelectorAll('.ho-nt > i.t')].map(i=>i.getAnimations()[0].effect.getTiming().delay)")
        assert len(t) >= 2 and len({round(x) for x in t}) > 1, t         # not in unison
    ctx.close()


# ── part 3: the corner glyph as a tube ──
# Tube 2 (Luke, 2026-11-12: "tubular glyph isn't quite there yet, make it actually tubular as it spins"): a real pipe, swept from the clef's strokes and lit by a light
# that stands still. Its 89 frames are rendered once with WebGL into a sheet, and the swing is a CSS animation stepping that sheet behind a small window (drawing it
# live cost +10 points of a core). The slices of the first version are still built: they are what a browser without WebGL shows, and paper.

def test_the_tube_is_a_rendered_pipe_stepped_from_a_sheet_and_the_slices_are_its_fallback():
    c, p, j = holo_trace.TUBE_CSS, holo_trace.TUBE_PIPE_CSS, holo_trace.TUBE_JS
    for banned in ("filter", "blur", "box-shadow"):
        assert banned not in c and banned not in p, banned
    assert "will-change" not in p and "rotate" not in p and "perspective" not in p and "preserve-3d" not in p      # (iOS: nothing turning in 3D, promoted or shadowed in the fixed header)
    # the fallback keeps the clef's swing (never edge-on), its 10 s and its still angle
    assert "transform-style:preserve-3d" in c and "@keyframes ho-tube{0%,100%{transform:perspective(260px) rotateY(-55deg)}50%{transform:perspective(260px) rotateY(55deg)}}" in c and "animation:ho-tube 10s ease-in-out -2.5s infinite" in c
    assert "@media (prefers-reduced-motion:reduce){.ho-tube .sp{animation:none;transform:perspective(260px) rotateY(24deg)}}" in c
    assert "@media print{.ho-tube .sp{animation:none;transform:none}}" in c and "html.hp-hid .ho-tube .sp{animation-play-state:paused}" in c
    # the pipe: the same 10 s, from the same face-on start; paused in a hidden tab and off screen; still under Reduce Motion; the screen shows the sheet, paper the slices
    assert ".ho-tube.go canvas{animation:ho-pipe 10s step-end -2.5s infinite}" in p
    assert "html.hp-hid .ho-tube canvas,.ho-tube.off canvas{animation-play-state:paused}" in p
    assert "@media (prefers-reduced-motion:reduce){.ho-tube:not(#_) canvas{animation:none;transform:%s}}" % holo_trace._cell(holo_trace.tube_frame(24)) in p
    assert "@media screen{.ho-tube.g3 .sp{display:none}}" in p and "@media print{.ho-tube .cl{display:none !important}}" in p
    assert holo_trace.TUBE_RHO == 3.6 and len(holo_trace.TUBE_T) == 9
    assert (holo_trace.TUBE_SWING, holo_trace.TUBE_PERIOD, holo_trace.TUBE_STILL, holo_trace.TUBE_FRAMES) == (55, 10, 24, 89)           # size, speed and swing kept
    assert holo_trace.TUBE_COLS * holo_trace.TUBE_ROWS >= holo_trace.TUBE_FRAMES
    assert "getContext('webgl'" in j and "DEPTH_TEST" in j and "isContextLost" in j and "WEBGL_lose_context" in j and "IntersectionObserver" in j
    assert "setInterval" not in j and "setTimeout" not in j and "preserveDrawingBuffer" not in j and "drop-shadow" not in j
    assert j.count("requestAnimationFrame") == 1                                # only while the sheet is being filled
    assert "location.hash" not in holo_trace.JS                                # (the private-web bundler counts the page's hash reads)


def test_the_swing_steps_one_frame_at_a_time_along_the_old_cosine():
    k = holo_trace.tube_keyframes()
    assert k.startswith("@keyframes ho-pipe{0%,100%{transform:translate(-0%,-0%)}") and k.count("transform:") == 2 * 88 + 1 and k.count("{") == k.count("}")
    steps = [(float(a), holo_trace.TUBE_COLS * round(float(y) * holo_trace.TUBE_ROWS / 100) + round(float(x) * holo_trace.TUBE_COLS / 100))
             for a, x, y in re.findall(r"(?<=\})([\d.]+)%\{transform:translate\(-([\d.]+)%,-([\d.]+)%\)\}", k)]
    assert len(steps) == 176 and all(a < b for (a, _), (b, _) in zip(steps, steps[1:])), steps[:4]
    frames = [0] + [f for _, f in steps]
    assert all(abs(a - b) == 1 for a, b in zip(frames, frames[1:])) and max(frames) == 88 and frames[88] == 88 and frames[-1] == 0      # there and back, never a jump
    # every frame is on show while the cosine is within its own 1.25 degrees
    for (a, f), (b, _) in zip(steps, steps[1:]):
        for t in (a + 1e-6, (a + b) / 2, b - 1e-6):
            assert abs(-55 * math.cos(2 * math.pi * t / 100) - holo_trace.tube_angle(f)) <= 0.63, (t, f)
    # at the animation's start (a quarter in: its -2.5 s delay) the frame is the face-on one, the one shown while the sheet is filled
    at = lambda pct: [f for a, f in steps if a <= pct][-1]
    assert at(25) == holo_trace.tube_frame(0) == 44 and holo_trace.tube_angle(44) == 0 and holo_trace.tube_frame(24) == 63
    assert min(b - a for (a, _), (b, _) in zip(steps, steps[1:])) * 100 >= 33          # ms: never more than 30 steps a second


def test_the_pipe_rides_in_the_hosted_script_and_costs_the_page_nothing():
    pg = [_outline(), pages.build_home(HOME)]
    for needle in ("tbMesh", "webgl", "ho-tube", "ho-pipe"):
        assert needle in holo.ASSET, needle
        assert all(needle not in p for p in pg), needle


def _tube_open(browser, site, **kw):
    pg, ctx, errors = _open(browser, site, wait=1500, **kw)
    # The sheet bakes a few frames per animation frame. Chromium headless renders WebGL in software (SwiftShader), so the 89 frames take ~4 s there against under 1.5 s in WebKit;
    # wait for the bake to finish (or for the tube to give up the WebGL path: no GL, reduced motion, a free'd tube) instead of assuming a fixed time.
    _baked(pg)
    return pg, ctx, errors


def _baked(pg):
    try:
        pg.wait_for_function("()=>{var t=document.querySelector('.ho-tube'); return !t || !t._hoG || t.classList.contains('go') || (t._hoG.n>=2 && matchMedia('(prefers-reduced-motion: reduce)').matches);}", timeout=20000)
    except Exception:
        pass


NO_GL = "(()=>{var o=HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext=function(t){ return /webgl/.test(t) ? null : o.apply(this, arguments); };})()"
SLICES = "[...document.querySelectorAll('.ho-tube .sp > svg')]"
BOX = "(()=>{var a=document.querySelector('svg.brand-mark').getBoundingClientRect(), o=document.querySelector('.ho-tube').getBoundingClientRect();return [[a.left,a.top,a.width,a.height],[o.left,o.top,o.width,o.height]];})()"
G3 = "(()=>{var t=document.querySelector('.ho-tube'); return !!t && t.classList.contains('g3') && t.querySelectorAll('.cl > canvas').length===1 && t.querySelectorAll('canvas').length===1;})()"
GO = "(()=>{var t=document.querySelector('.ho-tube'); return !!t && t.classList.contains('go') && t._hoG.n===89 && t._hoG.R===null;})()"       # every frame in, the WebGL context given back
ANIMS = "document.querySelector('.ho-tube').getAnimations({subtree:true}).map(a=>[a.animationName, a.playState])"
# The frame showing now: which cell of the sheet stands in the window.
FRAME = "(()=>{var t=document.querySelector('.ho-tube'), c=t.querySelector('canvas'), w=t.querySelector('.cl').getBoundingClientRect(), b=c.getBoundingClientRect(); return Math.round((w.top-b.top)/w.height)*12+Math.round((w.left-b.left)/w.width);})()"
# Read one frame of the pipe: {deg} renders it at that angle (any angle, the swing's or not), {cell} reads that cell of the sheet. Lengths come back in glyph units
# (the clef is 98 tall, its widest stroke 7.2). `run`: the narrowest row of the pipe over the middle 60% of its height (each row's widest unbroken stretch); `bar`: the
# brightness of each pixel across the left upright at a quarter of its height; `lum`: the mean brightness of the pipe; `edge`: the most alpha on the frame's outer edge.
PIX = """(q)=>{
  var t=document.querySelector('.ho-tube'), g=t._hoG, k, x, W=g.fw, H=g.fh, depth=null;
  if(q.deg!==undefined){ k=t._hoShot(q.deg); depth=k._depth; x=k.getContext('2d'); }
  else { k=document.createElement('canvas'); k.width=W; k.height=H; x=k.getContext('2d'); x.drawImage(g.cv,(q.cell%12)*W,Math.floor(q.cell/12)*H,W,H,0,0,W,H); }
  var d=x.getImageData(0,0,W,H).data, u=(parseFloat(t.style.height)/98)*(W/parseFloat(t.querySelector('.cl').style.width));
  var solid=function(X,Y){ var i=(Y*W+X)*4; return d[i+3]>250 && !(d[i]>d[i+1]); }, L=function(X,Y){ var i=(Y*W+X)*4; return (d[i]*.3+d[i+1]*.59+d[i+2]*.11); };
  var x0=W,x1=-1,y0=H,y1=-1,X,Y,n=0,s=0,any=0,edge=0;
  for(Y=0;Y<H;Y++) for(X=0;X<W;X++){ var al=d[(Y*W+X)*4+3]; if(al) any++; if((X===0||Y===0||X===W-1||Y===H-1) && al>edge) edge=al; if(solid(X,Y)){ if(X<x0)x0=X; if(X>x1)x1=X; if(Y<y0)y0=Y; if(Y>y1)y1=Y; n++; s+=L(X,Y); } }
  if(!n) return {n:0, any:any};
  var run=1e9, a=Math.round(y0+(y1-y0)*.2), b=Math.round(y0+(y1-y0)*.8);
  for(Y=a;Y<=b;Y++){ var best=0, cur=0; for(X=0;X<W;X++){ if(solid(X,Y)){ cur++; if(cur>best) best=cur; } else cur=0; } if(best<run) run=best; }
  Y=Math.round(y0+(y1-y0)*.25); X=x0; while(X<W && !solid(X,Y)) X++; var b0=X; while(X<W && solid(X,Y)) X++; var b1=X-1, bar=[];
  for(X=b0;X<=b1;X++) bar.push(Math.round(L(X,Y)));
  return {n:n, any:any, w:(x1-x0+1)/u, h:(y1-y0+1)/u, cx:((x0+x1)/2-W/2)/u, run:run/u, lum:s/n, bar:bar, barw:(b1-b0+1)/u, edge:edge, depth:depth};
}"""


def _round(bar):
    """shaded across its width like a round pipe under a light from the upper left: brightest toward the lit side, clearly darker on the side turned away"""
    peak = bar.index(max(bar))
    return len(bar) >= 3 and max(bar) - bar[-1] >= 25 and peak < len(bar) - 1 and peak <= len(bar) // 2


def test_the_tube_sits_on_the_glyph_and_the_glyph_underneath_is_hidden_not_removed(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1
    assert pg.evaluate("document.querySelector('svg.brand-mark').nextElementSibling.classList.contains('ho-tube')")
    assert pg.evaluate(G3) and pg.evaluate(GO)                                                 # one sheet, every frame rendered
    assert pg.evaluate("document.querySelectorAll('.ho-tube .sp > svg').length") == 11        # the fallback's nine depths, glow and ghost: built, not displayed
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).display") == "none"
    b = pg.evaluate(BOX)
    assert all(abs(x - y) <= 0.5 for x, y in zip(*b)), b
    # the window is the glyph's box and a small margin for the turn's perspective and the glow, in whole pixels; the sheet is 12 x 8 of it
    cv = pg.evaluate("""(()=>{var t=document.querySelector('.ho-tube'), w=t.querySelector('.cl'), c=t.querySelector('canvas'), r=w.getBoundingClientRect(), g=t.getBoundingClientRect(), a=getComputedStyle(c), z=getComputedStyle(w);
      var k=r.width/parseFloat(z.width); return {w:parseFloat(z.width),h:parseFloat(z.height),l:(g.left-r.left)/k,t:(g.top-r.top)/k,rr:(r.right-g.right)/k,bb:(r.bottom-g.bottom)/k,sw:parseFloat(a.width),sh:parseFloat(a.height),pw:c.width,ph:c.height,ov:z.overflow,fx:a.filter+z.filter,wc:a.willChange+z.willChange,tf:a.transform,fw:t._hoG.fw,fh:t._hoG.fh};})()""")
    assert 3 <= cv["l"] <= 9 and 3 <= cv["t"] <= 9 and abs(cv["l"] - cv["rr"]) <= 1 and abs(cv["t"] - cv["bb"]) <= 1, cv
    assert abs(cv["w"] - round(cv["w"])) < 0.02 and abs(cv["h"] - round(cv["h"])) < 0.02 and cv["w"] < 60 and cv["h"] < 60 and cv["ov"] == "hidden", cv
    assert abs(cv["sw"] - 12 * cv["w"]) < 0.3 and abs(cv["sh"] - 8 * cv["h"]) < 0.3, cv
    assert cv["pw"] == 12 * cv["fw"] and cv["ph"] == 8 * cv["fh"] and cv["fw"] in (2 * round(cv["w"]), 3 * round(cv["w"])) and cv["pw"] <= 2200 and cv["ph"] <= 1500, cv      # (a sheet of a few MB at most)
    assert cv["fx"] == "nonenone" and cv["wc"] == "autoauto" and cv["tf"].startswith("matrix("), cv       # a flat slide of the sheet, nothing in 3D
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-mark')).opacity") == "0"
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-mark')).animationName") == "none"
    assert pg.evaluate("(()=>{var r=document.querySelector('svg.brand-mark').getBoundingClientRect(); var e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); return !!e && !e.closest('.ho-tube');})()")
    assert not errors, errors
    ctx.close()


def test_the_pipe_is_round_lit_and_as_thick_from_the_side_as_from_the_front(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    assert pg.evaluate(G3)
    f = pg.evaluate(PIX, {"deg": 0})
    assert f["n"] > 300 and f["depth"] >= 16, f                                # drawn, with a depth buffer (the nearer stroke hides the farther one where they cross)
    assert 60 < f["w"] < 80 and 84 < f["h"] < 102, f                           # face-on: the clef at its own size (78 x 98 with its strokes)
    assert f["edge"] == 0, f                                                   # nothing behind the pipe and nothing cut off: a clear frame, never a plate
    # a round cross-section: the upright is its stroke's width, lit from the upper left and darker on the side turned away
    assert 5.4 < f["barw"] < 8.2, f
    assert _round(f["bar"]), f
    # every angle of the swing, and beyond it to edge-on: a pipe is never thinner than its own width (the flat cut-out went to a hairline, the slices to a flat bar)
    for deg in (-55, -40, -24, 24, 40, 55, 75, 90, -90):
        s = pg.evaluate(PIX, {"deg": deg})
        assert s["n"] > 150 and 84 < s["h"] < 110, (deg, s)
        assert s["run"] >= 4.2, (deg, s)                                       # (the thinner upright is 5.0 wide)
        assert s["w"] >= max(6.0, 0.85 * f["w"] * abs(math.cos(math.radians(deg)))), (deg, s)
        if abs(deg) <= 55:
            assert s["edge"] == 0, (deg, s)                                    # the whole swing fits its window, glow and all
    # the light stands still while the pipe turns: turned toward it and away from it the pipe is not lit alike (a turning drawing would be its own mirror image)
    a, b = pg.evaluate(PIX, {"deg": -40}), pg.evaluate(PIX, {"deg": 40})
    assert abs(a["lum"] - b["lum"]) > 4, (a["lum"], b["lum"])
    assert abs(a["w"] - b["w"]) < 6, (a["w"], b["w"])
    assert not errors, errors
    ctx.close()


def test_the_sheet_holds_every_frame_of_the_swing_and_each_is_the_pipe_at_its_angle(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    assert pg.evaluate(GO)
    cells = [pg.evaluate(PIX, {"cell": i}) for i in range(96)]
    assert all(c["n"] > 150 and c["edge"] == 0 and c["run"] >= 4.2 for c in cells[:89]), [i for i, c in enumerate(cells[:89]) if not (c["n"] > 150 and c["edge"] == 0 and c["run"] >= 4.2)]
    assert all(c["n"] == 0 and c["any"] == 0 for c in cells[89:])              # the sheet's spare cells are clear
    for i in (0, 20, 44, 63, 88):                                              # a cell is the pipe rendered at its own angle
        s = pg.evaluate(PIX, {"deg": holo_trace.tube_angle(i)})
        assert abs(s["w"] - cells[i]["w"]) < 0.8 and abs(s["lum"] - cells[i]["lum"]) < 2 and abs(s["cx"] - cells[i]["cx"]) < 0.8, (i, s, cells[i])
    w = [c["w"] for c in cells[:89]]
    assert w[44] == max(w) or w[44] > max(w) - 1.5, (w[44], max(w))            # widest face-on, narrowing to each end of the swing, and the pipe's thickness kept
    assert all(a <= b + 0.9 for a, b in zip(w[:44], w[1:45])) and all(a + 0.9 >= b for a, b in zip(w[44:], w[45:])), w
    assert min(w) > 0.5 * max(w)
    assert not errors, errors
    ctx.close()


def test_the_pipe_swings_by_css_alone_and_stops_when_hidden_or_off_screen(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    assert pg.evaluate(GO)
    assert pg.evaluate(ANIMS) == [["ho-pipe", "running"]]                       # one animation, on the sheet; the slices under it do not turn
    seen = []
    for _ in range(8):
        pg.wait_for_timeout(250)
        seen.append(pg.evaluate(FRAME))
    assert all(0 <= f <= 88 for f in seen) and len(set(seen)) >= 4, seen        # it swings
    # scrubbed: the frame on show follows the old swing, face-on at the start and 55 degrees to each side
    at = lambda ms: pg.evaluate("(t)=>{var a=document.querySelector('.ho-tube canvas').getAnimations()[0]; a.currentTime=t; return %s;}" % FRAME, ms)
    got = {ms: at(ms) for ms in (0, 2500, 5000, 7500, 10000, 12500)}
    assert got == {0: 44, 2500: 88, 5000: 44, 7500: 0, 10000: 44, 12500: 88} or all(abs(got[k] - v) <= 1 for k, v in {0: 44, 2500: 88, 5000: 44, 7500: 0, 10000: 44, 12500: 88}.items()), got
    pg.evaluate("document.documentElement.classList.add('hp-hid')")           # a hidden tab (holo.py sets the class)
    pg.wait_for_timeout(200)
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube canvas')).animationPlayState") == "paused"
    h0 = pg.evaluate(FRAME)
    pg.wait_for_timeout(700)
    assert pg.evaluate(FRAME) == h0
    pg.evaluate("document.documentElement.classList.remove('hp-hid')")
    pg.wait_for_timeout(200)
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube canvas')).animationPlayState") == "running"
    pg.evaluate("document.querySelector('.ho-tube').style.left='-4000px'")      # off screen
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelector('.ho-tube').classList.contains('off')") and pg.evaluate("getComputedStyle(document.querySelector('.ho-tube canvas')).animationPlayState") == "paused"
    pg.evaluate("document.querySelector('.ho-tube').style.left=''")
    pg.wait_for_timeout(500)
    assert not pg.evaluate("document.querySelector('.ho-tube').classList.contains('off')") and pg.evaluate("getComputedStyle(document.querySelector('.ho-tube canvas')).animationPlayState") == "running"
    assert not errors, errors
    ctx.close()


def test_without_webgl_the_slices_swing_as_before_and_are_never_edge_on(browser, site):
    pg, ctx, errors = _tube_open(browser, site, init=NO_GL)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1
    assert pg.evaluate("document.querySelectorAll('.ho-tube canvas, .ho-tube .cl').length") == 0 and not pg.evaluate("document.querySelector('.ho-tube').classList.contains('g3')")
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).display") == "block"
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).animationName") == "ho-tube"
    assert pg.evaluate("document.getAnimations().filter(a=>a.animationName==='ho-tube').length") == 1
    span = """()=>{var a=document.getAnimations().find(a=>a.animationName==='ho-tube'); a.pause(); a.currentTime=%d;
      var r=%s.filter(s=>/^q/.test(s.getAttribute('class'))).map(s=>s.getBoundingClientRect()); var h=document.querySelector('.ho-tube').getBoundingClientRect().height;
      return (Math.max(...r.map(x=>x.right))-Math.min(...r.map(x=>x.left)))/h;}"""
    face = pg.evaluate(span % (0, SLICES))
    turns = [pg.evaluate(span % (t, SLICES)) for t in range(0, 10000, 250)]
    assert face > 0.7, face                                               # a fresh load: face-on, the glyph's width
    assert min(turns) >= face * .4 and max(turns) <= face * 1.05, (face, min(turns), max(turns))
    assert abs(turns[10] - turns[30]) < face * .12 and turns[10] < face * .8, (turns[10], turns[30])      # 2.5 s and 7.5 s: the two ends of the swing, as far to each side
    w = lambda q: pg.evaluate("[...new Set([...document.querySelectorAll('.ho-tube svg.q%d path')].map(p=>+p.getAttribute('stroke-width')))].sort((a,b)=>a-b).join()" % q)
    assert w(0) == "2.9,5,5.8,6.6,7.2", w(0)
    assert max(float(x) for x in w(4).split(",")) < 4.5, w(4)
    assert not errors, errors
    ctx.close()


def test_when_webgl_goes_away_the_next_sheet_falls_back_to_the_slices(browser, site):
    pg, ctx, errors = _tube_open(browser, site, phone=True, dark=True)
    assert pg.evaluate(GO)
    pg.evaluate(NO_GL)                                                          # the browser stops handing out WebGL contexts
    pg.evaluate("document.documentElement.classList.remove('dark')")           # a new theme asks for a new sheet
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1
    assert pg.evaluate("document.querySelectorAll('.ho-tube canvas, .ho-tube .cl').length") == 0 and not pg.evaluate("document.querySelector('.ho-tube').classList.contains('g3')")
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).display") == "block"
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).animationName") == "ho-tube"
    assert not errors, errors
    ctx.close()


def test_a_new_theme_renders_a_new_sheet_in_its_own_colours(browser, site):
    pg, ctx, errors = _tube_open(browser, site, phone=True, dark=True)
    assert pg.evaluate(GO)
    d = pg.evaluate(PIX, {"cell": 44})
    pg.evaluate("document.documentElement.classList.remove('dark')")
    pg.wait_for_timeout(300); _baked(pg)
    assert pg.evaluate(GO) and pg.evaluate(ANIMS) == [["ho-pipe", "running"]]
    lt = pg.evaluate(PIX, {"cell": 44})
    assert d["lum"] - lt["lum"] > 40 and abs(d["w"] - lt["w"]) < 1.5, (d["lum"], lt["lum"])       # the pale page's deep teal pipe, the same shape
    assert _round(lt["bar"]) and _round(d["bar"])
    assert not errors, errors
    ctx.close()


def test_the_tube_is_still_under_reduce_motion_and_shaded_the_same(browser, site):
    pg, ctx, errors = _tube_open(browser, site, reduce=True)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1 and pg.evaluate(G3)
    assert pg.evaluate(ANIMS) == []                                         # nothing moves
    assert pg.evaluate(FRAME) == 63                                         # standing at its 24 degrees (the nearest frame, 23.75)
    assert pg.evaluate("[document.querySelector('.ho-tube')._hoG.n, document.querySelector('.ho-tube')._hoG.R===null, document.querySelector('.ho-tube').classList.contains('go')]") == [2, True, False]      # only it and the face-on frame were rendered
    pg.wait_for_timeout(700)
    assert pg.evaluate(FRAME) == 63 and pg.evaluate(ANIMS) == []
    s = pg.evaluate(PIX, {"cell": 63})
    assert s["n"] > 300 and s["run"] >= 4.2 and s["edge"] == 0 and _round(s["bar"]), s      # still a round, lit pipe
    pg.emulate_media(reduced_motion="no-preference")
    pg.wait_for_timeout(300); _baked(pg)
    assert pg.evaluate(GO) and pg.evaluate(ANIMS) == [["ho-pipe", "running"]]      # and it swings again when the setting goes
    pg.emulate_media(reduced_motion="reduce")
    pg.wait_for_timeout(500)
    assert pg.evaluate(ANIMS) == [] and pg.evaluate(FRAME) == 63
    assert not errors, errors
    ctx.close()


def test_the_fallback_is_still_under_reduce_motion(browser, site):
    pg, ctx, errors = _tube_open(browser, site, reduce=True, init=NO_GL)
    assert pg.evaluate("document.querySelectorAll('.ho-tube .sp > svg').length") == 11
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).animationName") == "none"
    m = pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).transform")
    assert m != "none", m
    pg.wait_for_timeout(600)
    assert m == pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).transform")
    ctx.close()


def test_the_tube_goes_with_the_style_and_gives_the_glyph_back(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.querySelectorAll('.ho-tube, .ho-tube canvas, .cl').length") == 0
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-mark')).opacity") != "0"
    assert pg.evaluate("document.querySelector('svg.brand-mark').getAttribute('style')") in (None, "")
    pg.evaluate("window._altoStyle.set('holo')")                              # and back: one pipe again, swinging
    pg.wait_for_timeout(300); _baked(pg)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1 and pg.evaluate(GO) and pg.evaluate(ANIMS) == [["ho-pipe", "running"]]
    assert not errors, errors
    ctx.close()


def test_paper_gets_the_slices_face_on(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    pg.emulate_media(media="print")
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .cl')).display") == "none"
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).display") == "block"
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).transform") == "none"
    ctx.close()


@pytest.mark.parametrize("dark", [True, False])
@pytest.mark.parametrize("page", ["t.html", "h.html"])
def test_the_phone_glyph_is_a_tube_too(browser, site, page, dark):
    pg, ctx, errors = _tube_open(browser, site, phone=True, page=page, dark=dark)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1 and pg.evaluate(G3) and pg.evaluate(GO)
    b = pg.evaluate(BOX)
    assert all(abs(x - y) <= 0.8 for x, y in zip(*b)), b
    assert b[0][1] >= 0 and b[0][1] + b[0][3] <= 56
    assert pg.evaluate(ANIMS) == [["ho-pipe", "running"]]
    for cell in (0, 44, 88):
        s = pg.evaluate(PIX, {"cell": cell})
        assert s["n"] > 300 and s["run"] >= 4.2 and s["edge"] == 0, (cell, s)
    assert not errors, errors
    ctx.close()


def test_phone_landscape_the_pipe_is_a_flat_sheet_on_a_clear_ground_with_nothing_promoted(browser, site):
    """(a past bug: iOS composited a fixed, turning, shadowed element as a black pill in Holo phone landscape; here nothing turns in 3D, and there is no filter and no will-change)"""
    ctx = browser.new_context(viewport={"width": 844, "height": 390}, has_touch=True, is_mobile=True, user_agent=IPHONE)
    ctx.set_default_navigation_timeout(NAV_MS)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("document.documentElement.classList.add('dark')")
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(1500)
    if not pg.evaluate("!!document.querySelector('.ho-tube')"):
        ctx.close()
        pytest.skip("no glyph in this layout")
    assert pg.evaluate(G3) and pg.evaluate(GO)
    st = pg.evaluate("""(()=>{var t=document.querySelector('.ho-tube'), out=[]; [t, t.querySelector('.cl'), t.querySelector('canvas')].forEach(e=>{var a=getComputedStyle(e); out.push([a.filter, a.willChange, a.backgroundColor, a.boxShadow, a.transformStyle, /matrix3d/.test(a.transform)]);}); return out;})()""")
    assert st == [["none", "auto", "rgba(0, 0, 0, 0)", "none", "flat", False]] * 3, st
    for cell in (0, 44, 88):
        s = pg.evaluate(PIX, {"cell": cell})
        assert s["n"] > 300 and s["edge"] == 0, (cell, s)
    assert not errors, errors
    ctx.close()
