"""Luke 2026-11-26: "the back button is not centered with everything else in that row" (a detail page, Retro). BACK stands on the same centre line as the clef and the wordmark in all three looks."""
import pytest

from tests.test_lanes_extend_1125 import site, pw  # noqa: F401

M = """() => { const q = s => document.querySelector(s), c = e => { const r = e.getBoundingClientRect(); return (r.top + r.bottom) / 2; };
  return {mark: c(q('#title-bar .brand-mark')), word: c(q('#title-bar .brand-word')), back: q('#desk-back') && c(q('#desk-back')), shown: !!q('#desk-back') && getComputedStyle(q('#desk-back')).display !== 'none'}; }"""


@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_back_is_centred_on_the_rows_centre_line(site, style):
    b, base = site
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    if style != "classic":
        ctx.add_init_script("localStorage.setItem('alto-hl-lanes-children-style', '%s')" % style)
    pg = ctx.new_page()
    pg.goto(f"{base}/on.html", wait_until="load")
    pg.wait_for_timeout(3000)
    pg.evaluate("() => { const o = document.getElementById('ln-offer'); if (o) o.remove(); }")
    pg.evaluate("() => showDetail('node', 'arrive')")
    pg.wait_for_timeout(1800)
    d = pg.evaluate(M)
    assert d["shown"], d
    assert abs(d["back"] - d["mark"]) <= 1 and abs(d["back"] - d["word"]) <= 1, d          # (it was 6.6 px low in Retro)
    ctx.close()
