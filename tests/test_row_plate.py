"""B-1126-BUTTONS-OPAQUE: in Retro and Holographic the bottom-right button row stands on one solid plate (union of its buttons), so card text never shows in the gaps or through the glass."""
import pytest

from alto.build import holo, retro
from tests.test_lanes_extend_1125 import site, _open, pw  # noqa: F401


def test_both_styles_carry_the_row_plate_script_once_each():
    for a in (retro.ASSET, holo.ASSET):
        assert a.count("alto-row-plate") == 1 and "ROWPLATE" not in a and "window._altoRowPlate" in a


@pytest.mark.parametrize("style", ["retro", "holo"])
def test_the_plate_lies_exactly_behind_the_row_and_is_solid(site, style):
    b, base = site
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("localStorage.setItem('alto-hl-lanes-children-style', '%s')" % style)
    pg = ctx.new_page()
    pg.goto(f"{base}/on.html", wait_until="load")
    pg.wait_for_timeout(3500)
    d = pg.evaluate("""() => { const p = document.getElementById('alto-row-plate'); if (!p) return null; const r = p.getBoundingClientRect(), c = getComputedStyle(p);
      const bs = ['search-btn', 'key-toggle', 'info-btn'].map(i => document.getElementById(i)).filter(Boolean).map(e => e.getBoundingClientRect());
      return {r: [r.left, r.top, r.right, r.bottom], bg: c.backgroundColor, pe: c.pointerEvents, z: c.zIndex, bs: bs.map(x => [x.left, x.top, x.right, x.bottom])}; }""")
    assert d and d["pe"] == "none" and d["bg"].startswith("rgb(") and "rgba" not in d["bg"], d
    assert len(d["bs"]) >= 2
    for x in d["bs"]:                                                    # every button of the row sits inside the plate
        assert x[0] >= d["r"][0] - 1 and x[2] <= d["r"][2] + 1 and x[1] >= d["r"][1] - 1 and x[3] <= d["r"][3] + 1, d
    ctx.close()


def test_classic_has_no_plate(site):
    ctx, pg = _open(site, "on", 1440, 900)
    pg.wait_for_timeout(1500)
    assert pg.evaluate("() => !document.getElementById('alto-row-plate')")
    ctx.close()
