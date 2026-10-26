"""System: the one way of moving (solar_navopt.py). Luke tried four nav options side by side (2026-10-23) and chose
the breadcrumb panel, the old "A", as the default beside the Tour bar (2026-10-25): it moves to the parent, a sibling
and a child by name, from its own buttons and keys; the Tour bar stays under it; the chooser and the other options
are gone, and ?nav= or a choice kept from them changes nothing. On a phone the panel waits in MENU ("Where you are").

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


def test_the_panel_stays_small_and_the_other_options_are_gone():
    assert len(gzip.compress((NAVOPT_JS + NAVOPT_CSS).encode("utf-8"), 9)) < 3600
    for gone in (r"nvo-[bcd](?![\w-])", "nvo-pick", "data-nav", "Radial ring", "Minimap"):
        assert not re.search(gone, NAVOPT_JS + NAVOPT_CSS), gone


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))
    f = tmp_path_factory.mktemp("navopt") / "nv.html"
    f.write_text(html, encoding="utf-8")
    return f


AT = "u1-p1"


def _at(pg, at=AT, style="system"):
    pg.evaluate("a => { window._altoSolarStyles.set(a[1]); window.enterFocus(a[0]); }", [at, style])
    _arrive(pg, at)


def _arrive(pg, want):
    pg.wait_for_function("id => window._focusedNodeId===id && !window._altoSolarLock.riding()", arg=want, timeout=8000)
    pg.wait_for_timeout(450)


def _hood(pg, at=AT):
    return pg.evaluate("h => { var A=window._altoSolarNavApi; return {up:A.up(h), sibs:A.sibs(h), kids:A.kids(h), order:A.order()}; }", at)


def test_the_breadcrumb_and_named_neighbours(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg)
    n = _hood(pg)
    assert pg.is_visible("#sol-tour") and pg.is_visible("#nvo-a")              # both: the panel and the Tour bar
    assert pg.inner_text("#nvo-a .nv-at").count("›") >= 2
    assert pg.evaluate("() => document.querySelectorAll('.sol-nh,#sol-way path').length") == 0   # nothing named on the map
    pg.click(f'#nvo-a button[data-go="{n["up"]}"]')
    _arrive(pg, n["up"])
    _at(pg)
    sib = [s for s in n["sibs"] if s != AT][0]
    pg.click(f'#nvo-a button[data-go="{sib}"]')
    _arrive(pg, sib)
    _at(pg)
    pg.click(f'#nvo-a button[data-go="{n["kids"][0]}"]')
    _arrive(pg, n["kids"][0])
    pg.keyboard.press("ArrowUp")                                    # keys: up, then a sibling, then child 1
    _arrive(pg, AT)
    i = n["sibs"].index(AT)
    pg.keyboard.press("ArrowRight" if i + 1 < len(n["sibs"]) else "ArrowLeft")
    _arrive(pg, n["sibs"][i + 1] if i + 1 < len(n["sibs"]) else n["sibs"][i - 1])
    _at(pg)
    pg.keyboard.press("1")
    _arrive(pg, n["kids"][0])
    pg.keyboard.press("?")
    assert "How to move" in pg.inner_text("#nvo-help")
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("style", ["system", "chart", "retro", "3d"])
def test_the_panel_sits_over_the_tour_bar_and_the_tour_still_walks(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, style=style)
    box = pg.evaluate("""() => { var R=id=>document.getElementById(id).getBoundingClientRect(), a=R('nvo-a'), t=R('sol-tour'), c=R('sol-ctl');
      return {a:[a.top, a.bottom, a.left, a.right], t:[t.top, t.bottom], c:c.top, w:innerWidth}; }""")
    assert box["a"][1] <= box["t"][0] + 1 and box["t"][1] <= box["c"] + 1, box     # panel, then Tour bar, then the controls
    assert box["a"][2] >= 0 and box["a"][3] <= box["w"], box
    T = _hood(pg)["order"]
    pg.click("#sol-tour [data-t=next]")
    _arrive(pg, T[T.index(AT) + 1])
    pg.context.close()
    assert not errs, errs


def test_an_old_choice_or_the_address_changes_nothing(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=600)
    pg.evaluate("() => { localStorage.setItem('alto-solar-nav', 'c'); }")
    pg.goto(page.as_uri() + "?nav=b")
    pg.wait_for_timeout(1400)
    _at(pg)
    assert pg.evaluate("window._altoNavOpt.get()") == "a"
    assert pg.is_visible("#nvo-a") and pg.is_visible("#sol-tour")
    assert pg.evaluate("() => !document.querySelector('#nvo-b,#nvo-c,#nvo-d,#nvo-pick,[data-nav]')")
    pg.context.close()
    assert not errs, errs


def test_on_a_phone_the_panel_is_in_menu(browser, page):
    """The phone seen whole (?mobile): the panel is not on the page at rest; "Where you are" (in the System's controls,
    which MENU lists) opens it as a sheet; a name goes there and closes it."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=browser.browser_type.name != "firefox"
                              and browser.browser_type.name == "chromium")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page.as_uri())
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { document.documentElement.classList.add('phone-whole'); window.enterFocus('%s'); }" % AT)
    _arrive(pg, AT)
    assert not pg.is_visible("#nvo-a")
    pg.evaluate("() => document.getElementById('nvo-where').click()")
    pg.wait_for_timeout(300)
    assert pg.is_visible("#nvo-a")
    r = pg.evaluate("() => { var r=document.getElementById('nvo-a').getBoundingClientRect(); return [r.left, r.right, innerWidth]; }")
    assert r[0] >= 0 and r[1] <= r[2] + 1, r
    up = _hood(pg)["up"]
    pg.click(f'#nvo-a button[data-go="{up}"]')
    _arrive(pg, up)
    assert not pg.is_visible("#nvo-a")
    ctx.close()
    assert not errs, errs
