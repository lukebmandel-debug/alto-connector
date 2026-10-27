"""System: moving round, Luke's own design (2026-10-26; solar_navopt.py). One small control just right of the Ship
picker, in the bottom bar's style: Back (the parent), where you are, Next (the next at the same level), the minimap's
switch. The bodies beside an enlarged one are bigger and titled, a click away, with no arrows drawn; the arrow keys
and a scroll only go round them. The minimap names the body under the pointer. The Nav A card is gone. On a phone the
control waits in MENU ("Where you are").

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import gzip
import re
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.solar_navopt import NAVOPT_CSS, NAVOPT_JS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import SMALL, SMALL_LINKS, _open, browser, solar_doc  # noqa: E402,F401


def test_the_control_stays_small_and_the_card_is_gone():
    assert len(gzip.compress((NAVOPT_JS + NAVOPT_CSS).encode("utf-8"), 9)) < 9600   # (the minimap, the scoped arrows and scroll, the phone row; the minimap's box, drag, free-room placement: 2026-10-26)
    for gone in (r"nvo-[bcd](?![\w-])", "nvo-pick", "data-nav", "Same level:", "Inside:", r"\.nv-r", r"\.nv-hd"):
        assert not re.search(gone, NAVOPT_JS + NAVOPT_CSS), gone


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))
    f = tmp_path_factory.mktemp("navopt") / "nv.html"
    f.write_text(html, encoding="utf-8")
    return f


AT = "u1-p1"            # a planet with two moons (u1-p1-m1, u1-p1-m2), the first of three planets round u1


def _at(pg, at=AT, style="system"):
    pg.evaluate("a => { window._altoSolarStyles.set(a[1]); window.enterFocus(a[0]); }", [at, style])
    _arrive(pg, at)


def _arrive(pg, want):
    pg.wait_for_function("id => window._focusedNodeId===id && !window._altoSolarLock.riding() && !window._altoSolarFlight()", arg=want, timeout=9000)
    pg.wait_for_timeout(450)


def _hood(pg, at=AT):
    return pg.evaluate("h => { var A=window._altoSolarNavApi; return {up:A.up(h), sibs:A.sibs(h), kids:A.kids(h)}; }", at)


@pytest.mark.parametrize("style", ["system", "chart", "retro", "3d"])
def test_one_small_row_just_right_of_ship(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, style=style)
    box = pg.evaluate("""() => { var a=document.getElementById('nvo-a'), s=document.getElementById('sol-craft'), v=s; while(v && !v.getClientRects().length) v=v.previousElementSibling; var R=e=>e.getBoundingClientRect(), r=R(a), q=R(v);
      return {inBar:a.parentNode.id, prev:a.previousElementSibling && a.previousElementSibling.id, h:r.height, sh:q.height, top:r.top, stop:q.top, gap:r.left-q.right, w:r.width,
        tour:!!document.querySelector('#sol-tour') && getComputedStyle(document.querySelector('#sol-tour')).display!=='none',
        card:!!document.querySelector('#nvo-a .nv-r,#nvo-a .nv-hd'), pills:[].filter.call(document.querySelectorAll('.sol-nh,#sol-way path'), e=>e.getClientRects().length).length}; }""")
    assert box["inBar"] == "sol-ctl" and box["prev"] == "sol-craft", box          # in the bottom bar, just right of Ship (in System, where Ship hides: of the styles)
    assert abs(box["h"] - box["sh"]) <= 2 and abs(box["top"] - box["stop"]) <= 2, box   # the same height and line as Ship
    assert 0 <= box["gap"] <= 20 and box["w"] <= 460, box                         # beside it, and small
    assert not box["tour"] and not box["card"] and box["pills"] == 0, box         # no Tour bar, no card, no arrows on the map
    pg.context.close()
    assert not errs, errs


def test_back_is_the_parent_and_next_the_next_at_this_level(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg)
    n = _hood(pg)
    assert "Back to " in pg.get_attribute("#nvo-a [data-n=up]", "title")
    pg.click("#nvo-a [data-n=up]")
    _arrive(pg, n["up"])
    _at(pg)
    pg.click("#nvo-a [data-n=next]")
    _arrive(pg, n["sibs"][n["sibs"].index(AT) + 1])                               # the next sibling
    last = n["sibs"][-1]
    _at(pg, last)
    nx = pg.evaluate("() => window._altoNavOpt.next()")
    assert nx and nx not in n["sibs"] and pg.evaluate("id => window._altoSolarGeo().bodies[id].role", nx) == "planet", nx   # then the next concept at this level
    pg.click("#nvo-a [data-n=next]")
    _arrive(pg, nx)
    pg.click("#nvo-a .nv-at")                                                      # where you are: stays there
    pg.wait_for_timeout(400)
    assert pg.evaluate("() => window._focusedNodeId") == nx
    pg.context.close()
    assert not errs, errs


def test_arrows_and_scroll_only_go_round_what_is_beside_it(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg)
    k = _hood(pg)["kids"]
    assert len(k) == 2
    pg.keyboard.press("ArrowRight")
    _arrive(pg, k[0])                                                              # the planet: round its moons
    pg.keyboard.press("ArrowRight")
    _arrive(pg, k[1])                                                              # a moon: still round those moons
    pg.keyboard.press("ArrowRight")
    _arrive(pg, k[0])                                                              # round, never out to another planet
    pg.keyboard.press("ArrowUp")
    _arrive(pg, k[1])                                                              # (no arrow goes up a level)
    pg.mouse.move(300, 300)
    pg.mouse.wheel(0, 120)
    _arrive(pg, k[0])                                                              # a scroll: the same round
    pg.wait_for_timeout(400)
    pg.mouse.wheel(0, -120)
    _arrive(pg, k[1])
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", ["chart", "3d"])
def test_the_bodies_beside_it_are_bigger_titled_and_a_click_away(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, style=style)
    k = _hood(pg)["kids"]
    if style == "3d":
        sel = '#sk3d-l i[data-go="%s"]' % k[0]
        pg.wait_for_selector(sel, state="visible", timeout=4000)
        pg.wait_for_timeout(1200)                                                  # (the scene settles: the pills stop moving)
        assert pg.inner_text(sel).strip() == pg.evaluate("id => window._altoSolarNavApi.name(id)", k[0])   # its name, no key glyph
    else:
        fl = pg.evaluate("""ks => ks.map(id => { var n=document.getElementById('node-'+id), l=n.querySelector('.sol-lbl'), c=n.querySelector('.node-card').getBoundingClientRect();
          return {flank:n.classList.contains('sol-flank'), w:c.width, lbl:getComputedStyle(l).opacity, fs:parseFloat(getComputedStyle(l).fontSize), t:l.getAttribute('data-l')}; })""", k)
        for f in fl:
            assert f["flank"] and f["w"] >= 40 and f["lbl"] == "1" and f["fs"] >= 13 and f["t"], fl
        sel = "#node-%s > .sol-lbl" % k[0]
    pg.click(sel)
    _arrive(pg, k[0])
    pg.context.close()
    assert not errs, errs


def test_the_minimap_names_what_you_point_at(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => localStorage.removeItem('alto-solar-map')")
    _at(pg, style="chart")
    pg.wait_for_selector("#nvo-map", state="visible")
    to = "u1-p3"
    c = pg.evaluate("id => { var e=document.querySelector('#nvo-map circle[data-b=\"'+id+'\"]').getBoundingClientRect(); return [e.left+e.width/2, e.top+e.height/2]; }", to)
    pg.mouse.move(c[0], c[1])
    pg.wait_for_selector("#nvo-tip", state="visible")
    assert pg.inner_text("#nvo-tip") == pg.evaluate("id => window._altoSolarNavApi.name(id)", to)
    pg.mouse.click(c[0], c[1])
    _arrive(pg, to)
    pg.click("#nvo-a [data-n=map]")                                                # its switch: off, and kept
    pg.wait_for_timeout(350)
    assert not pg.is_visible("#nvo-map") and pg.evaluate("() => localStorage.getItem('alto-solar-map')") == "0"
    pg.click("#nvo-a [data-n=map]")
    pg.wait_for_timeout(350)
    assert pg.is_visible("#nvo-map")
    pg.context.close()
    assert not errs, errs


def test_on_a_phone_the_control_is_in_menu(browser, page):
    """The phone seen whole: the control is not on the page at rest; "Where you are" (in the System's controls, which
    MENU lists) opens it as one row above the corner controls; Back goes up and the row stays."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=browser.browser_type.name == "chromium")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page.as_uri())
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { document.documentElement.classList.add('phone-whole'); window.enterFocus('%s'); }" % AT)
    _arrive(pg, AT)
    assert not pg.is_visible("#nvo-a")
    pg.evaluate("() => document.getElementById('nvo-where').click()")
    pg.wait_for_timeout(400)
    assert pg.is_visible("#nvo-a")
    r = pg.evaluate("() => { var r=document.getElementById('nvo-a').getBoundingClientRect(); return [r.left, r.right, r.height, innerWidth]; }")
    assert r[0] >= 0 and r[1] <= r[3] + 1 and r[2] <= 48, r
    up = _hood(pg)["up"]
    pg.tap("#nvo-a [data-n=up]")
    _arrive(pg, up)
    assert pg.is_visible("#nvo-a")
    ctx.close()
    assert not errs, errs


# ── the minimap, round 2 (Luke 2026-10-26): it starts in the bottom-right corner, moves anywhere, and a box on it is
#    the window's view (drag it to pan, pull its edges to zoom: a bigger box shows more) ──
RECT = "s => { var e=document.querySelector(s); if(!e) return null; var r=e.getBoundingClientRect(); return {l:r.left, t:r.top, r:r.right, b:r.bottom, w:r.width, h:r.height}; }"
VIEW = """() => { var g=window._altoSolarCam.get(), c=document.getElementById('canvas'), sv=document.querySelector('#nvo-map svg'), v=sv.viewBox.baseVal, b=document.querySelector('#nvo-map .vb'),
  P=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0, w=c.clientWidth/g.scale, h=c.clientHeight/g.scale, x0=g.cx-w/2, y0=g.cy+P-h/2;
  return {s:g.scale, cx:g.cx, cy:g.cy, want:[Math.max(x0, v.x), Math.max(y0, v.y), Math.min(x0+w, v.x+v.width), Math.min(y0+h, v.y+v.height)],
    got:['x', 'y', 'width', 'height'].map(a => +b.getAttribute(a)), shown:b.style.display!=='none'}; }"""


def _map(browser, page, style="chart", clear=True):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    if clear:
        pg.evaluate("() => { localStorage.removeItem('alto-solar-map'); localStorage.removeItem('alto-solar-map-at'); }")
    _at(pg, style=style)
    pg.wait_for_selector("#nvo-map", state="visible")
    pg.wait_for_timeout(300)
    return pg, errs


def _box_is_the_view(v, tol=2.5):
    g = v["got"]
    assert v["shown"], v
    got = [g[0], g[1], g[0] + g[2], g[1] + g[3]]
    assert all(abs(a - b) <= tol * max(1, 1 / v["s"]) for a, b in zip(got, v["want"])), v


CLEAR = """() => { var m=document.getElementById('nvo-map').getBoundingClientRect(), bad=[];
  document.querySelectorAll('#world .node.focused .node-card,#world .node.sol-flank .node-card,#world .node.sol-flank>.sol-lbl,#sk3d-l i,#nvo-a,#sol-ctl,#sol-craft,#search-btn,#info-btn,#mode-toggle,#alto-edit-pill,#hamburger-tab').forEach(function(e){
    var r=e.getBoundingClientRect(), cs=getComputedStyle(e); if(!r.width || cs.visibility==='hidden' || cs.display==='none') return;
    if(m.left<r.right && r.left<m.right && m.top<r.bottom && r.top<m.bottom) bad.push(e.id || e.className); });
  return {bad:bad, w:m.width, h:m.height, in:m.left>=0 && m.top>=0 && m.right<=innerWidth && m.bottom<=innerHeight}; }"""


@pytest.mark.parametrize("style", ["system", "chart", "retro", "3d"])
def test_the_minimap_shows_only_with_a_body_enlarged_big_and_clear(browser, page, style):
    """Luke, 2026-10-26: "Minimap only shows up when nodes are enlarged, and it should be big enough that you can
    realistically see where you are in the entire system page, without obstructing other elements of the page"."""
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { localStorage.removeItem('alto-solar-map'); localStorage.removeItem('alto-solar-map-at'); }")
    pg.evaluate("s => window._altoSolarStyles.set(s)", style)
    pg.wait_for_timeout(600)
    assert not pg.is_visible("#nvo-map")                                            # nothing enlarged: no minimap
    _at(pg, style=style)
    pg.wait_for_timeout(500)
    assert pg.is_visible("#nvo-map")                                                # enlarged: it fades in
    c = pg.evaluate(CLEAR)
    assert c["in"] and not c["bad"], c                                              # over nothing: the card, beside it, the bar, the corner
    assert c["h"] >= 200 and c["w"] >= 200, c                                       # big enough to see the whole system
    assert pg.evaluate("() => !!document.querySelector('#nvo-map circle.h') && !!document.querySelector('#nvo-map circle.hr')")   # you, ringed
    pg.keyboard.press("o")                                                          # the whole system: it fades out
    pg.wait_for_timeout(700)
    assert not pg.is_visible("#nvo-map")
    pg.keyboard.press("Escape")
    pg.evaluate("id => window.enterFocus(id)", AT)
    _arrive(pg, AT)
    pg.evaluate("() => window.exitFocus()")                                          # let go: it fades out
    pg.wait_for_timeout(700)
    assert not pg.is_visible("#nvo-map")
    pg.context.close()
    assert not errs, errs


def test_the_minimap_moves_anywhere_and_keeps_its_place(browser, page):
    pg, errs = _map(browser, page)
    m = pg.evaluate(RECT, "#nvo-map")
    x, y = m["l"] + 6, m["t"] + 4                                                   # its frame (not the box, not a body)
    pg.mouse.move(x, y)
    pg.mouse.down()
    tx, ty = 30 - m["l"], 860 - m["b"]                                             # to the bottom-left, over the bar: free room
    pg.mouse.move(x + tx, y + ty, steps=8)
    pg.mouse.up()
    pg.wait_for_timeout(400)
    n = pg.evaluate(RECT, "#nvo-map")
    assert abs(n["l"] - m["l"] - tx) < 6 and abs(n["t"] - m["t"] - ty) < 6, (m, n)
    assert not pg.evaluate(CLEAR)["bad"]
    assert pg.evaluate("() => window._focusedNodeId") == AT                        # a drag is not a click: nothing went anywhere
    kept = pg.evaluate("() => JSON.parse(localStorage.getItem('alto-solar-map-at'))")
    assert 0 < kept["x"] < 1 and 0 < kept["y"] < 1, kept
    pg.reload()
    pg.wait_for_timeout(1400)
    _at(pg)
    pg.wait_for_selector("#nvo-map", state="visible")
    pg.wait_for_timeout(300)
    r = pg.evaluate(RECT, "#nvo-map")
    assert abs(r["l"] - n["l"]) < 3 and abs(r["t"] - n["t"]) < 3, (n, r)            # kept on this device
    pg.mouse.move(r["l"] + 6, r["t"] + 4)
    pg.mouse.down()
    pg.mouse.move(r["l"] + 3000, r["t"] + 3000, steps=6)                           # flung off the edge: it stays on screen
    pg.mouse.up()
    pg.set_viewport_size({"width": 900, "height": 600})                           # and a smaller window keeps it in view
    pg.wait_for_timeout(500)
    r = pg.evaluate(RECT, "#nvo-map")
    assert 0 <= r["l"] and r["r"] <= 900 and 0 <= r["t"] and r["b"] <= 600, r
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", ["system", "retro"])
def test_the_box_is_what_the_window_shows_live(browser, page, style):
    pg, errs = _map(browser, page, style)
    _box_is_the_view(pg.evaluate(VIEW))
    v = pg.evaluate(VIEW)
    for cx, cy, s in ((v["cx"] + 400, v["cy"] - 150, .6), (v["cx"] - 300, v["cy"] + 100, .35), (v["cx"], v["cy"], 1)):
        pg.evaluate("a => window._altoSolarCam.set(a[0], a[1], a[2])", [cx, cy, s])
        pg.wait_for_timeout(450)
        _box_is_the_view(pg.evaluate(VIEW))                                         # it follows every pan and zoom
    pg.context.close()
    assert not errs, errs


def test_dragging_the_box_pans_and_pulling_it_zooms(browser, page):
    pg, errs = _map(browser, page)                                                 # (from an enlarged body, where the map is)
    v0 = pg.evaluate(VIEW)
    b = pg.evaluate(RECT, "#nvo-map .vb")
    cx, cy = b["l"] + b["w"] / 2, b["t"] + b["h"] / 2
    pg.mouse.move(cx, cy)
    pg.mouse.down()
    pg.mouse.move(cx - 12, cy + 8, steps=6)                                         # the box dragged left and down
    pg.mouse.up()
    pg.wait_for_timeout(450)
    v1 = pg.evaluate(VIEW)
    assert v1["cx"] < v0["cx"] - 20 and v1["cy"] > v0["cy"] + 10 and abs(v1["s"] - v0["s"]) < .01, (v0, v1)
    _box_is_the_view(v1)
    assert pg.is_visible("#nvo-map")                                                # the body let go, the map stays while in use
    b = pg.evaluate(RECT, "#nvo-map .vb")
    pg.mouse.move(b["l"], b["t"])                                                   # its top-left corner, pulled out: bigger box
    pg.mouse.down()
    pg.mouse.move(b["l"] - 30, b["t"] - 26, steps=6)
    pg.mouse.up()
    pg.wait_for_timeout(450)
    v2 = pg.evaluate(VIEW)
    assert v2["s"] < v1["s"] - .05, (v1, v2)                                         # shows more of the system
    _box_is_the_view(v2)
    b = pg.evaluate(RECT, "#nvo-map .vb")
    pg.mouse.move(b["r"], b["t"] + b["h"] / 2)                                      # its right edge, pulled in: smaller box
    pg.mouse.down()
    pg.mouse.move(b["r"] - b["w"] / 3, b["t"] + b["h"] / 2, steps=6)
    pg.mouse.up()
    pg.wait_for_timeout(450)
    v3 = pg.evaluate(VIEW)
    assert v3["s"] > v2["s"] + .05, (v2, v3)                                         # shows less: zoomed in
    _box_is_the_view(v3)
    pg.context.close()
    assert not errs, errs


# ── the connecting lines keep one strength (Luke on Retro, 2026-10-26: "some of the connecting lines between nodes …
#    fade out for no apparent reason"). The cause: a resting pointer on an orbit named it and faded every other line,
#    and in Retro the orbit bands are under the pointer almost everywhere. ──
LINES = r"""() => { var o={}; document.querySelectorAll('#solar-svg :is(.sol-spoke,.sol-link,.sol-bun), #river-svg path[data-edge]').forEach(function(e, i){
  var cs=getComputedStyle(e); if(cs.display==='none' || e.classList.contains('sol-hot')) return; var a=+cs.strokeOpacity*+cs.opacity, p=e.parentNode;
  while(p && p.nodeType===1){ a*=+getComputedStyle(p).opacity; p=p.parentNode; } o[(e.getAttribute('data-edge') || e.getAttribute('class'))+'#'+i]=+a.toFixed(3); }); return o; }"""


@pytest.mark.parametrize("style", ["retro", "system"])
def test_the_connecting_lines_keep_one_strength(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("s => window._altoSolarStyles.set(s)", style)
    pg.wait_for_timeout(700)
    base = pg.evaluate(LINES)
    assert base and min(base.values()) > .15, base                                # (a sun link's dots are faint by design)
    seen = []
    for x in range(250, 1300, 210):                                                 # a pointer resting here and there
        for y in range(180, 800, 200):
            pg.mouse.move(x, y)
            pg.wait_for_timeout(380)
            if not pg.evaluate("() => document.getElementById('canvas').classList.contains('edge-hover')"):   # (on a line itself: it lights, the rest give way)
                seen.append(pg.evaluate(LINES))
    pg.mouse.move(5, 5)
    cam = pg.evaluate("() => window._altoSolarCam.get()")
    for dx, s in ((0, 1), (300, 1), (-300, .7)):                                    # panned (zoom has its own deliberate ramp: --lk)
        pg.evaluate("a => window._altoSolarCam.set(a[0], a[1], a[2])", [cam["cx"] + dx, cam["cy"], s])
        pg.wait_for_timeout(450)
        if s == 1 or style == "retro":                                              # (Retro: one strength at every zoom too)
            seen.append(pg.evaluate(LINES))
    for o in seen:
        for k, a in o.items():
            if k in base:
                assert abs(a - base[k]) < .02, (k, base[k], a)
    pg.context.close()
    assert not errs, errs
