"""System, Luke 2026-10-28 (item 6): "you're literally like flying through a planet in the visual view of 3D star chart ...
it's the camera view for the viewer" — in Realistic 3D the eye never goes into a body, nor so near it that the near plane
cuts it, in a free drag / zoom, on a flight, a dive or a zoom out; and the ship never touches a body on the way."""
import copy
import random
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401

UNITS = [[[2, 1, 0], [1, 0], [0], [3, 1]], [[1, 1], [0, 2], [2]], [[], [0]]]
LINKS = [("u1-p1", "u2-p2"), ("u1-p1-m1", "u1-p3")]

EYE = r"""() => { var P=window._altoSolar3D, G=window._altoSolarGeo(), e=P.eye(), m=1e9, id=null;
  Object.keys(G.bodies).forEach(function(i){ var o=G.bodies[i], h=Math.hypot(e[0]-o.x, e[1], e[2]-o.y)-o.d/2; if(h<m){ m=h; id=i; } }); return [m, id]; }"""
REC = r"""() => { window.__R=[]; (function g(){ var P=window._altoSolar3D, G=window._altoSolarGeo(), e=P.eye(), s=P.ship(), m=1e9, q=1e9;
  Object.keys(G.bodies).forEach(function(i){ var o=G.bodies[i], R=o.d/2; m=Math.min(m, Math.hypot(e[0]-o.x, e[1], e[2]-o.y)-R);
    if(s && s.on) q=Math.min(q, Math.hypot(s.x-o.x, s.lift||3, s.y-o.y)-R); });
  window.__R.push([m, q]); requestAnimationFrame(g); })(); }"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(UNITS, "spoke", LINKS))))
    f = tmp_path_factory.mktemp("cam") / "cam.html"
    f.write_text(html, encoding="utf-8")
    return f


def _in_3d(browser, page):
    pg, errs = _open(browser, page, wait=1500)
    pg.evaluate("() => { window._altoCraft.set('explorer'); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }")
    pg.wait_for_timeout(2800)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close()
        pytest.skip("no WebGL in this browser")
    return pg, errs


def test_a_free_camera_is_never_inside_a_body(browser, page):
    pg, errs = _in_3d(browser, page)
    random.seed(7)
    ids = pg.evaluate("() => Object.keys(window._altoSolarGeo().bodies)")
    worst = 1e9
    for _ in range(80):
        b = random.choice(ids)
        st = {"d": random.choice([60, 80, 120, 200, 400]), "az": random.uniform(-3.1, 3.1), "el": random.uniform(-1.2, 1.4)}
        pg.evaluate("a => { var g=window._altoSolarGeo().bodies[a[0]]; window._altoSolar3D.set({tx:g.x, tz:g.y, d:a[1].d, az:a[1].az, el:a[1].el}); }", [b, st])
        pg.wait_for_timeout(70)
        m, i = pg.evaluate(EYE)
        worst = min(worst, m)
        assert m > 4, (b, st, m, i)                  # (outside every body, with a clear shell)
    pg.context.close()
    assert not errs, errs


@pytest.mark.parametrize("a,b", [("u1", "u1-p3-m1"), ("u1-p1-m1", "u1-p1-m1-s1"), ("u1-p1", "u2-p1")])
def test_a_flight_a_dive_and_a_zoom_out_keep_the_eye_and_the_ship_clear(browser, page, a, b):
    pg, errs = _in_3d(browser, page)
    pg.evaluate("a => window.enterFocus(a)", a)
    pg.wait_for_timeout(500)
    pg.wait_for_function("() => !window._altoSolarFlight()", timeout=60000)
    pg.wait_for_timeout(2500)
    pg.evaluate(REC)
    pg.evaluate("b => window.enterFocus(b)", b)
    pg.wait_for_timeout(500)
    pg.wait_for_function("() => !window._altoSolarFlight()", timeout=60000)
    pg.wait_for_timeout(2600)
    pg.evaluate("() => window.exitFocus()")
    pg.wait_for_timeout(2200)
    R = pg.evaluate("() => window.__R")
    assert len(R) > 100
    assert min(r[0] for r in R) > 6, min(r[0] for r in R)           # the eye: outside every body, a shell clear
    assert min(r[1] for r in R) > 3, min(r[1] for r in R)           # the ship: its centre well off every surface
    pg.context.close()
    assert not errs, errs
