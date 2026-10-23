"""The FPV graphics pass in a real browser (WebKit, then Chromium if present): the museum walk with the pass on loads the HDRI sky and the real
material sets through the Basis transcoder, runs its post chain (SSAO + bloom) without a GL error, and still paints a lit frame; ?bldgfx=0 is the
look before the pass; the low tier fetches nothing from /gfx/. Skipped without Playwright."""
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build import building_schema as bs  # noqa: E402
from alto.buildings import pma  # noqa: E402
from tests.building_fpv_support import PIXELS, Server, launch  # noqa: E402
from tests.test_building_pma_render import _html  # noqa: E402

HALL = [-8, 9, 12.5, 3.39, 0.12]


@pytest.fixture(scope="module")
def env():
    srv = Server()
    srv.html, srv.plan = _html(), bs.hosted_json(pma.plan())[1]
    with pw.sync_playwright() as p:
        b = launch(p, "webkit")
        yield srv, b
        b.close()
    srv.close()


def _walk(srv, b, qs):
    page = b.new_page(viewport={"width": 960, "height": 600})
    errors, gfx = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.on("request", lambda r: gfx.append(r.url) if "/gfx/" in r.url else None)
    page.goto(srv.origin + "/index.html" + qs)
    page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
    page.evaluate("() => { window._altoFpv = {view: 'first'}; AltoBuilding.enterFPV(null, {from: 'plan'}); }")
    page.wait_for_function("window.AltoBuildingFPV && AltoBuildingFPV.state() && AltoBuildingFPV.state().on", timeout=30000)
    page.evaluate("a => AltoBuildingFPV.place(...a)", HALL)
    t0 = time.time()
    while time.time() - t0 < 30:
        page.evaluate("AltoBuildingFPV.settle()")
        f = page.evaluate("AltoBuildingFPV.fx()")
        if f["pending"] == 0 and (f["tier"] == "low" or f["fx"]["ao"] == 0 or (f["env"] and f["real"] >= 3)):
            break
        page.wait_for_timeout(300)
    page.wait_for_timeout(900)
    return page, errors, gfx, page.evaluate("AltoBuildingFPV.fx()"), page.evaluate(PIXELS)


def test_the_pass_on_high(env):
    page, errors, gfx, f, px = _walk(*env, "?bldgtier=high")
    assert f["tier"] == "high" and f["post"] and f["env"] and f["real"] >= 3, f
    assert not f["err"] and not errors, (f["err"], errors)
    assert .12 < px["mean"] < .85 and px["sd"] > .04, px                  # a lit, varied frame (not black, not blown out)
    assert any("basis_transcoder" in u for u in gfx) and any("-a1024-" in u for u in gfx) and not any("-a512-" in u for u in gfx)
    page.close()


def test_off_is_the_look_before_and_low_fetches_nothing(env):
    for qs in ("?bldgtier=high&bldgfx=0", "?bldgtier=low"):
        page, errors, gfx, f, px = _walk(*env, qs)
        assert not f["post"] and not f["env"] and f["real"] == 0 and gfx == [], (qs, f, gfx)
        assert not errors and px["mean"] > .1, (qs, errors, px)
        page.close()
