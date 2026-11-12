"""Holographic's "Alto" wordmark, traced by light on a loop (alto/build/holo_trace.py; Luke, 2026-11-05: "Alto logo should sort of be traced by a holo on loop as opposed to
spinning"; Art's look ORG/notes-art/holo-wordmark-trace.md). A cyan-white bead with a magenta ghost runs along the letters' outlines once every 7 s, then the wordmark
rests lit and still; the corner clef keeps its turn; Reduce Motion and print draw nothing; a phone has it too (Luke's standing phone yes, L-1105-160112@Board).
The code is in the hosted Holographic script, the page holds none of it. The browser parts are skipped when Playwright is not installed."""
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


def _open(browser, site, page="t.html", phone=False, width=None, reduce=False, dark=None, style="holo", wait=900, frozen=False):
    ctx = browser.new_context(viewport={"width": 390 if phone else (width or 1400), "height": 844 if phone else 860}, has_touch=phone, is_mobile=phone,
                              user_agent=IPHONE if phone else None, reduced_motion="reduce" if reduce else "no-preference")
    ctx.set_default_navigation_timeout(NAV_MS)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
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
    assert ".node.dimmed .ho-nt" in c and "#e8fffd" in c and "rgba(255,95,210,.55)" in c and "#12b5d6" in c


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

def test_the_tube_is_a_stack_of_slices_in_one_turning_box_and_no_script_runs_per_frame():
    c, j = holo_trace.TUBE_CSS, holo_trace.TUBE_JS
    for banned in ("filter", "blur", "box-shadow"):
        assert banned not in c, banned
    assert "transform-style:preserve-3d" in c and "@keyframes ho-tube{0%,100%{transform:perspective(260px) rotateY(-55deg)}50%{transform:perspective(260px) rotateY(55deg)}}" in c and "animation:ho-tube 10s ease-in-out -2.5s infinite" in c   # the clef's swing (never edge-on), the 10 s kept
    assert "@media (prefers-reduced-motion:reduce){.ho-tube .sp{animation:none;transform:perspective(260px) rotateY(24deg)}}" in c           # and its still angle
    assert "@media print{.ho-tube .sp{animation:none;transform:none}}" in c and "html.hp-hid .ho-tube .sp{animation-play-state:paused}" in c
    assert "requestAnimationFrame" not in j and "setInterval" not in j and "setTimeout" not in j
    assert holo_trace.TUBE_RHO == 3.6 and len(holo_trace.TUBE_T) == 9


def _tube_open(browser, site, **kw):
    pg, ctx, errors = _open(browser, site, wait=1200, **kw)
    return pg, ctx, errors


SLICES = "[...document.querySelectorAll('.ho-tube .sp > svg')]"
BOX = "(()=>{var a=document.querySelector('svg.brand-mark').getBoundingClientRect(), o=document.querySelector('.ho-tube').getBoundingClientRect();return [[a.left,a.top,a.width,a.height],[o.left,o.top,o.width,o.height]];})()"


def test_the_tube_sits_on_the_glyph_and_the_glyph_underneath_is_hidden_not_removed(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1
    assert pg.evaluate("document.querySelector('svg.brand-mark').nextElementSibling.classList.contains('ho-tube')")
    assert pg.evaluate("document.querySelectorAll('.ho-tube .sp > svg').length") == 11        # nine depths, the glow behind and the ghost
    b = pg.evaluate(BOX)
    assert all(abs(x - y) <= 0.5 for x, y in zip(*b)), b
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-mark')).opacity") == "0"
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-mark')).animationName") == "none"
    assert pg.evaluate("(()=>{var r=document.querySelector('svg.brand-mark').getBoundingClientRect(); var e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); return !!e && !e.closest('.ho-tube');})()")
    assert not errors, errors
    ctx.close()


def test_the_tube_swings_and_is_never_edge_on(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).animationName") == "ho-tube"
    assert pg.evaluate("document.getAnimations().filter(a=>a.animationName==='ho-tube').length") == 1
    span = """()=>{var a=document.getAnimations().find(a=>a.animationName==='ho-tube'); a.pause(); a.currentTime=%d;
      var r=%s.filter(s=>/^q/.test(s.getAttribute('class'))).map(s=>s.getBoundingClientRect()); var h=document.querySelector('.ho-tube').getBoundingClientRect().height;
      return (Math.max(...r.map(x=>x.right))-Math.min(...r.map(x=>x.left)))/h;}"""
    face = pg.evaluate(span % (0, SLICES))
    turns = [pg.evaluate(span % (t, SLICES)) for t in range(0, 10000, 250)]
    assert face > 0.7, face                                               # a fresh load: face-on, the glyph's width
    # a swing of 55deg to each side (it used to turn right round, and edge-on was a bar 0.03-0.2 of the height wide): never under 40% of its face-on width
    assert min(turns) >= face * .4 and max(turns) <= face * 1.05, (face, min(turns), max(turns))
    assert abs(turns[10] - turns[30]) < face * .12 and turns[10] < face * .8, (turns[10], turns[30])      # 2.5 s and 7.5 s: the two ends of the swing, as far to each side
    # the middle slice is the clef at its own stroke widths; the outer ones are the narrower bright ones: a round cross-section
    w = lambda q: pg.evaluate("[...new Set([...document.querySelectorAll('.ho-tube svg.q%d path')].map(p=>+p.getAttribute('stroke-width')))].sort((a,b)=>a-b).join()" % q)
    assert w(0) == "2.90,5.00,5.80,6.60,7.20".replace(",", ",") or w(0) == "2.9,5,5.8,6.6,7.2", w(0)
    assert max(float(x) for x in w(4).split(",")) < 4.5, w(4)
    assert not errors, errors
    ctx.close()


def test_the_tube_is_still_under_reduce_motion_and_shaded_the_same(browser, site):
    pg, ctx, errors = _tube_open(browser, site, reduce=True)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1
    assert pg.evaluate("document.querySelectorAll('.ho-tube .sp > svg').length") == 11
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).animationName") == "none"
    m = pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).transform")
    assert m != "none", m                                                  # standing at its 24 degrees
    pg.wait_for_timeout(900)
    assert m == pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).transform")
    pg.emulate_media(reduced_motion="no-preference")
    pg.wait_for_timeout(500)
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).animationName") == "ho-tube"
    ctx.close()


def test_the_tube_goes_with_the_style_and_gives_the_glyph_back(browser, site):
    pg, ctx, errors = _tube_open(browser, site)
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(600)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 0
    assert pg.evaluate("getComputedStyle(document.querySelector('svg.brand-mark')).opacity") != "0"
    assert pg.evaluate("document.querySelector('svg.brand-mark').getAttribute('style')") in (None, "")
    ctx.close()


@pytest.mark.parametrize("page", ["t.html", "h.html"])
def test_the_phone_glyph_is_a_tube_too(browser, site, page):
    pg, ctx, errors = _tube_open(browser, site, phone=True, page=page, dark=True)
    assert pg.evaluate("document.querySelectorAll('.ho-tube').length") == 1
    b = pg.evaluate(BOX)
    assert all(abs(x - y) <= 0.8 for x, y in zip(*b)), b
    assert b[0][1] >= 0 and b[0][1] + b[0][3] <= 56
    assert pg.evaluate("getComputedStyle(document.querySelector('.ho-tube .sp')).animationName") == "ho-tube"
    assert not errors, errors
    ctx.close()
