"""System: the four nav options to try (solar_navopt.py; Luke, 2026-10-23). Each moves to the parent, a sibling and
a child by name, from its own buttons and keys; the chooser keeps its pick per device; ?nav= picks for one visit.

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import gzip
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.solar_navopt import NAVOPT_CSS, NAVOPT_JS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import SMALL, SMALL_LINKS, _open, browser, solar_doc  # noqa: E402,F401


def test_the_options_stay_small():
    assert len(gzip.compress((NAVOPT_JS + NAVOPT_CSS).encode("utf-8"), 9)) < 6800


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))
    f = tmp_path_factory.mktemp("navopt") / "nv.html"
    f.write_text(html, encoding="utf-8")
    return f


AT = "u1-p1"


def _at(pg, opt, at=AT):
    pg.evaluate("a => { window._altoSolarStyles.set('system'); window._altoNavOpt.set(a[0]); window.enterFocus(a[1]); }", [opt, at])
    _arrive(pg, at)


def _arrive(pg, want):
    pg.wait_for_function("id => window._focusedNodeId===id && !window._altoSolarLock.riding()", arg=want, timeout=8000)
    pg.wait_for_timeout(450)


def _hood(pg, at=AT):
    return pg.evaluate("h => { var A=window._altoSolarNavApi; return {up:A.up(h), sibs:A.sibs(h), kids:A.kids(h), order:A.order()}; }", at)


def test_a_breadcrumb_and_named_neighbours(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, "a")
    n = _hood(pg)
    assert pg.is_hidden("#sol-tour") and pg.is_visible("#nvo-a")
    assert "You are in:" in pg.inner_text("#nvo-a .nv-at")
    pg.click(f'#nvo-a button[data-go="{n["up"]}"]')
    _arrive(pg, n["up"])
    _at(pg, "a")
    sib = [s for s in n["sibs"] if s != AT][0]
    pg.click(f'#nvo-a button[data-go="{sib}"]')
    _arrive(pg, sib)
    _at(pg, "a")
    pg.click(f'#nvo-a button[data-go="{n["kids"][0]}"]')
    _arrive(pg, n["kids"][0])
    pg.keyboard.press("ArrowUp")                                    # keys: up, then a sibling, then child 1
    _arrive(pg, AT)
    i = n["sibs"].index(AT)
    pg.keyboard.press("ArrowRight" if i + 1 < len(n["sibs"]) else "ArrowLeft")
    _arrive(pg, n["sibs"][i + 1] if i + 1 < len(n["sibs"]) else n["sibs"][i - 1])
    _at(pg, "a")
    pg.keyboard.press("1")
    _arrive(pg, n["kids"][0])
    pg.context.close()
    assert not errs, errs


def test_b_a_ring_of_neighbours_on_the_body(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, "b")
    n = _hood(pg)
    pg.click(f"#node-{AT} .node-card")
    pg.wait_for_selector("#nvo-b button")
    ring = pg.evaluate("() => [].map.call(document.querySelectorAll('#nvo-b [data-go]'), function(b){ var r=b.getBoundingClientRect(); return [b.dataset.go, r.left+r.width/2, r.top+r.height/2]; })")
    pos = {r[0]: r[1:] for r in ring}
    assert n["up"] in pos and n["kids"][0] in pos
    assert pos[n["up"]][1] < min(pos[k][1] for k in n["kids"] if k in pos)    # the parent above, the children below
    pg.click(f'#nvo-b button[data-go="{n["kids"][0]}"]')
    _arrive(pg, n["kids"][0])
    pg.keyboard.press("r")
    pg.wait_for_selector("#nvo-b button")
    pg.keyboard.press("ArrowUp")
    _arrive(pg, AT)
    pg.keyboard.press("r")
    pg.wait_for_selector("#nvo-b button")
    sib = [s for s in n["sibs"] if s != AT]
    pg.click(f'#nvo-b button[data-go="{sib[0]}"]') if sib[0] in pos else None
    if sib[0] in pos:
        _arrive(pg, sib[0])
    pg.context.close()
    assert not errs, errs


def test_c_the_minimap_flies_and_lights_the_route(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, "c")
    n = _hood(pg)
    assert pg.is_visible(f'#nvo-c circle.h[data-id="{AT}"]')
    for to in (n["up"], [s for s in n["sibs"] if s != AT][0], n["kids"][0]):
        pg.dispatch_event(f'#nvo-c circle.t[data-id="{to}"]', "pointerup")
        lit = pg.evaluate("() => document.querySelectorAll('#nvo-c line.r').length")
        assert lit >= 1
        _arrive(pg, to)
        _at(pg, "c")
    pg.context.close()
    assert not errs, errs


def test_d_next_and_back_in_reading_order(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _at(pg, "d")
    o = _hood(pg)["order"]
    i = o.index(AT)
    assert f"{i + 1} of {len(o)}" in pg.inner_text("#nvo-d")
    pg.click("#nvo-d .nv-go")
    _arrive(pg, o[i + 1])
    pg.click('#nvo-d button[title^="Back"]')
    _arrive(pg, AT)
    pg.keyboard.press("ArrowRight")
    _arrive(pg, o[i + 1])
    pg.keyboard.press("ArrowLeft")
    _arrive(pg, AT)
    pg.context.close()
    assert not errs, errs


def test_the_chooser_is_kept_and_the_address_picks(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    assert pg.evaluate("window._altoNavOpt.get()") == "current" and pg.is_visible("#nvo-pick")
    pg.click('#nvo-pick [data-nav="c"]')
    assert pg.evaluate("window._altoNavOpt.get()") == "c"
    pg.reload()
    pg.wait_for_timeout(1400)
    assert pg.evaluate("window._altoNavOpt.get()") == "c"
    pg.goto(page.as_uri() + "?nav=d")
    pg.wait_for_timeout(1400)
    assert pg.evaluate("window._altoNavOpt.get()") == "d"
    pg.click('#nvo-pick [data-nav="?"]')
    assert "Next" in pg.inner_text("#nvo-help")
    pg.click('#nvo-help [data-nav="current"]')
    assert pg.evaluate("window._altoNavOpt.get()") == "current"
    pg.context.close()
    assert not errs, errs
