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
    assert len(gzip.compress((NAVOPT_JS + NAVOPT_CSS).encode("utf-8"), 9)) < 6200   # (the minimap, the scoped arrows and scroll, the phone row: 2026-10-26)
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
    r = pg.evaluate("() => { var m=document.getElementById('nvo-map').getBoundingClientRect(), a=document.getElementById('nvo-a').getBoundingClientRect(); return [m.bottom, a.top, m.height]; }")
    assert r[0] <= r[1] and r[2] <= 130, r                                         # small, above the control
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
