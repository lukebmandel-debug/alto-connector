"""B-1126-CLASSIC-CHROME-OPAQUE: Classic's bottom-right row and the lanes step bar are ~opaque over the cards (no card text reads through them); Retro and Holo keep their own fills."""
import pytest

from tests.test_lanes_extend_1125 import site, pw  # noqa: F401

EFF = """() => { const eff = e => { const s = getComputedStyle(e), a = (s.backgroundColor.match(/[\\d.]+/g) || []).map(Number), al = a.length > 3 ? a[3] : 1;
    return 1 - Math.pow(1 - al, 1 + (s.backgroundImage.match(/linear-gradient/g) || []).length); };
  const o = {}; for (const id of ['search-btn', 'key-toggle', 'info-btn', 'mode-toggle', 'alto-edit-pill', 'lanes-nav']) { const e = document.getElementById(id); if (e && e.getBoundingClientRect().width) o[id] = +eff(e).toFixed(3); } return o; }"""


@pytest.mark.parametrize("dark", [False, True])
def test_classic_row_and_step_bar_are_opaque(site, dark):
    b, base = site
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.goto(f"{base}/on.html", wait_until="load")
    pg.wait_for_timeout(3000)
    pg.evaluate("d => document.documentElement.classList.toggle('dark', d)", dark)
    pg.wait_for_timeout(500)
    o = pg.evaluate(EFF)
    assert {"search-btn", "lanes-nav"} <= set(o), o
    assert all(v >= 0.9 for v in o.values()), o
    ctx.close()


def test_retro_is_left_to_its_own_fills(site):
    b, base = site
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("localStorage.setItem('alto-hl-lanes-children-style', 'retro')")
    pg = ctx.new_page()
    pg.goto(f"{base}/on.html", wait_until="load")
    pg.wait_for_timeout(3000)
    assert pg.evaluate("() => getComputedStyle(document.getElementById('search-btn')).backgroundImage") == "none"
    ctx.close()
