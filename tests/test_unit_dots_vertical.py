"""The five beads on a unit divider are centred on the divider line (Luke 2026-11-27: "vertical centering"). Measured in WebKit in every look at desktop widths
(page zoom 0.8 to 1) and on a phone upright and on its side (the Whole view): each bead's vertical centre is within 0.5px of the bar's centre, and of the line
itself (Holographic's 6px tube and Retro's hairline are the bar's ::before, laid from the same middle). A guard: it holds today in headless WebKit."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_phone_minimal import pages, site, phone_ctx   # noqa: E402,F401

_J = """() => [...document.querySelectorAll('#world .unit-bar')].map(b => {
  const br = b.getBoundingClientRect(), bf = getComputedStyle(b, '::before'), k = br.height / b.offsetHeight || 1,
    mid = (br.top + br.bottom) / 2, beads = [...b.querySelectorAll('.unit-dots .ud-base > *')].map(c => { const r = c.getBoundingClientRect(); return (r.top + r.bottom) / 2; });
  let line = mid;
  if (bf.content !== 'none' && bf.position === 'absolute') line = br.top + (parseFloat(bf.top) + parseFloat(bf.marginTop) + parseFloat(bf.height) / 2) * k - (parseFloat(getComputedStyle(b).borderTopWidth) || 0) * 0;
  return {mid, line, beads, h: br.height}; })"""


def _check(pg):
    rows = pg.evaluate(_J)
    rows = [r for r in rows if r["h"] > 2]
    assert rows, "no unit dividers"
    for r in rows:
        for y in r["beads"]:
            assert abs(y - r["mid"]) <= .5, r
            assert abs(y - r["line"]) <= .5, r


@pytest.mark.parametrize("look", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(1960, 1000), (1600, 900), (1440, 900), (1280, 800)])
def test_beads_are_centred_on_the_line_on_a_computer(phone_ctx, site, look, size):
    b, _ = phone_ctx
    ctx = b.new_context(viewport={"width": size[0], "height": size[1]})
    pg = ctx.new_page()
    try:
        pg.goto(site + "/timeline.html", wait_until="load")
        pg.wait_for_timeout(1200)
        if look != "classic":
            pg.evaluate(f"window._altoStyle.set('{look}')")
            pg.wait_for_timeout(1200)
        _check(pg)
    finally:
        ctx.close()


@pytest.mark.parametrize("look", ["classic", "retro", "holo"])
@pytest.mark.parametrize("size", [(390, 844), (844, 390)])
def test_beads_are_centred_on_the_line_on_a_phone_whole_view(phone_ctx, site, look, size):
    b, dev = phone_ctx
    ctx = b.new_context(**{**dev, "viewport": {"width": size[0], "height": size[1]}})
    pg = ctx.new_page()
    try:
        pg.goto(site + "/timeline.html", wait_until="load")
        pg.wait_for_timeout(1200)
        if look != "classic":
            pg.evaluate(f"window._altoStyle.set('{look}')")
            pg.wait_for_timeout(1200)
        pg.evaluate("[...document.querySelectorAll('#nav-drawer .drawer-btn')].find(b => /Whole view/.test(b.textContent)).click()")
        pg.wait_for_timeout(2200)
        assert pg.evaluate("document.documentElement.classList.contains('phone-whole')")
        _check(pg)
    finally:
        ctx.close()


def test_holo_tubes_bright_line_runs_through_the_beads(phone_ctx, site):
    """Luke's Safari crop (Torts, Holo): the beads were centred on the 6px tube but its bright hairline sat on the tube's top edge, so they hung below the line.
    The highlight is now a hairline at the tube's centre: no inset top highlight, a 1px centred layer in the tube's own background."""
    b, _ = phone_ctx
    ctx = b.new_context(viewport={"width": 1960, "height": 1000}, device_scale_factor=2)
    pg = ctx.new_page()
    try:
        pg.goto(site + "/timeline.html", wait_until="load")
        pg.wait_for_timeout(1200)
        pg.evaluate("window._altoStyle.set('holo')")
        pg.wait_for_timeout(1500)
        bf = pg.evaluate("(() => { const c = getComputedStyle(document.querySelector('#world .unit-bar'), '::before'); return [c.boxShadow, c.backgroundImage, c.backgroundPosition, c.backgroundSize]; })()")
        assert "inset" not in bf[0], bf
        assert "1px" in bf[3] and "50%" in bf[2], bf
        _check(pg)
    finally:
        ctx.close()
