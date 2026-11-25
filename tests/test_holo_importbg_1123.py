"""An imported background shows behind Holographic pages (Board L-1123-HOLO-IMPORTBG).
The cause: Holographic paints its grid on body, #canvas and #page-bg for every page that is not `.alto-bg-h` (one of its own grounds),
and a picture the user imported only set `.alto-bg`, so the grid sat over it. An imported picture now sets `.alto-bg-h` too.
Retro is plain black on every page by design (backgrounds.py retroNow), so an import is chosen and kept there but not drawn.
Fixture account (u1) and an in-memory Firestore only."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_backgrounds_import as T                              # noqa: E402
from test_backgrounds_import import browser, site, timeline      # noqa: E402,F401

from alto.build import holo, retro                              # noqa: E402

LAYERS = """()=>{ const g=(e,p)=>getComputedStyle(e,p||null), pb=document.getElementById('page-bg'), r=document.documentElement;
  const grid=s=>/repeating-linear|linear-gradient\\(rgba/.test(s);
  return {cls:r.className, id:window._altoBgId||'', var:g(r).getPropertyValue('--alto-bg').trim(),
    pbImg:g(pb).backgroundImage, before:g(pb,'::before').backgroundImage, beforeDisplay:g(pb,'::before').display,
    bodyBg:g(document.body).backgroundImage, canvasBg:document.getElementById('canvas')?g(document.getElementById('canvas')).backgroundImage:'none',
    pbBgColor:g(pb).backgroundColor, grid:[g(pb).backgroundImage,g(document.body).backgroundImage].some(grid)}}"""


def _with_holo(site):
    base, tid, d = site
    for sub, asset in (("holo", holo.holo_asset()), ("retro", retro.retro_asset())):
        (d / sub).mkdir(exist_ok=True)
        (d / sub / asset[0]).write_text(asset[1], encoding="utf-8")
    return base, tid, d


def _style(pg, s):
    pg.evaluate("window._altoStyle.set(%r)" % s)
    pg.wait_for_function("document.documentElement.classList.contains(%r)" % ("alto-" + s) if s != "classic" else "!document.documentElement.classList.contains('alto-holo')", timeout=15000)
    pg.wait_for_timeout(500)


def _shown(L):
    """the picture is what paints behind the page: on the page-bg layer's ::before, which is displayed, with no grid under or over it"""
    assert "blob:" in L["var"], L
    assert "blob:" in L["before"] and L["beforeDisplay"] != "none", L
    assert not L["grid"], L                                           # no opaque Holographic plate above or beside it
    assert "blob:" not in L["bodyBg"] and L["bodyBg"] == "none" and L["canvasBg"] in ("none", ""), L


@pytest.mark.parametrize("size", [(1400, 860), (390, 844)])
def test_an_import_shows_in_holo_as_in_classic_and_survives_a_reload(browser, site, size):
    base, tid, d = _with_holo(site)
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 500, is_mobile=size[0] < 500)
    pg = T._page(ctx, base)
    T._import(pg, d / "beach.jpg", name="Dusk")
    uid = pg.evaluate("window._altoBgId")
    _shown(pg.evaluate(LAYERS))                                       # Classic
    _style(pg, "holo")
    L = pg.evaluate(LAYERS)
    assert "alto-holo" in L["cls"] and "alto-bg-h" in L["cls"] and L["id"] == uid, L
    _shown(L)                                                         # Holographic
    pg.reload(); pg.wait_for_function("window._altoBgId", timeout=15000)
    pg.wait_for_function("document.documentElement.classList.contains('alto-holo')", timeout=15000); pg.wait_for_timeout(800)
    L = pg.evaluate(LAYERS)
    assert L["id"] == uid and "alto-holo" in L["cls"]
    _shown(L)                                                         # and after a reload
    # Retro stays plain black, as designed: the choice is kept, nothing is drawn
    _style(pg, "retro")
    L = pg.evaluate(LAYERS)
    assert L["beforeDisplay"] == "none" and "blob:" not in L["pbImg"], L
    _style(pg, "holo")
    assert pg.evaluate("window._altoBgId") == uid                     # (back in Holographic it is still chosen and drawn)
    _shown(pg.evaluate(LAYERS))
    ctx.close()


def test_a_catalogue_photo_stays_off_in_holo_and_the_grid_shows_without_a_choice(browser, site):
    base, tid, d = _with_holo(site)
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = T._page(ctx, base)
    pg.evaluate("window._altoBg.choose('')"); _style(pg, "holo")
    L = pg.evaluate(LAYERS)
    assert L["grid"] and "alto-bg-h" not in L["cls"], L                # the plain Holographic grid, as before
    ctx.close()


def test_a_shared_view_without_the_library_falls_back_to_the_style_default(browser, site):
    """A viewer's browser has no copy of someone else's import (the library is per account): the id is unknown there, so nothing is
    drawn for it, no broken image, and Holographic shows its own grid. This is what shared pages do today."""
    base, tid, d = _with_holo(site)
    ctx = browser.new_context(viewport={"width": 1400, "height": 860})
    pg = T._page(ctx, base)
    key = pg.evaluate("window._altoBg.key")
    pg.evaluate("(k)=>localStorage.setItem(k, JSON.stringify({v:'u:abcdefghij', t:Date.now()}))", key)
    _style(pg, "holo"); pg.reload(); pg.wait_for_timeout(1200)
    L = pg.evaluate(LAYERS)
    assert L["grid"] and "alto-bg-h" not in L["cls"] and "blob:" not in L["var"], L
    ctx.close()
