"""System, Luke 2026-10-28 (on 1.9.187): "I'm not happy with the coming into orbits, how it often jumps over a planet.
Everything should be on the same plane, even in 3D." In the 3D Star chart every flight stays in the system's plane (the
ship's height never changes) and its path in that plane keeps clear of every body's surface: it goes round a body, never
over one, and settles into its orbit without a hop."""
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

# every frame of a flight: the ship's height, and its centre's distance in the plane to each body's surface
REC = r"""(X) => { window.__R=[]; window.__stop=false; (function g(){ if(window.__stop) return; var P=window._altoSolar3D, G=window._altoSolarGeo(), s=P.ship(), m=1e9, id=null;
  if(s && s.on && s.vis>.99 && !(s.warp>.02)){ Object.keys(G.bodies).forEach(function(i){ if(X.indexOf(i)>=0) return; var o=G.bodies[i], h=Math.hypot(s.x-o.x, s.y-o.y)-o.d/2; if(h<m){ m=h; id=i; } });
    window.__R.push([m, id, s.lift, s.x, s.y]); }
  requestAnimationFrame(g); })(); }"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(UNITS, "spoke", LINKS))))
    f = tmp_path_factory.mktemp("plane") / "plane.html"
    f.write_text(html, encoding="utf-8")
    return f


def _in_3d(browser, page, craft):
    pg, errs = _open(browser, page, wait=1500)
    pg.evaluate("c => { window._altoCraft.set(c); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }", craft)
    pg.wait_for_timeout(2800)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close()
        pytest.skip("no WebGL in this browser")
    return pg, errs


def _land(pg, i):
    pg.evaluate("i => window.enterFocus(i)", i)
    pg.wait_for_timeout(500)
    pg.wait_for_function("() => !window._altoSolarFlight()", timeout=60000)
    pg.wait_for_timeout(1800)


PAIRS = [("u1", "u1-p3-m1"), ("u1-p1-m1", "u1-p1-m1-s1"), ("u1-p1", "u1-p2"), ("u1-p3-m1", "u1-p1"), ("u1-p1-m1", "u1-p1"), ("u1-p2", "u1-p1-m1-s1"), ("u1-p1", "u2-p1")]


@pytest.mark.parametrize("craft", ["explorer", "rocket"])
def test_every_flight_stays_in_the_plane_and_clear_of_every_body(browser, page, craft):
    pg, errs = _in_3d(browser, page, craft)
    worst, rows, flat = 1e9, [], True
    for a, b in PAIRS:
        _land(pg, a)
        pg.evaluate(REC, [a, b])       # (clear of every body but the two it goes between: at those it is in their orbit, their circles enlarged)
        _land(pg, b)                                                # (the flight, the arrival, its orbit for a moment)
        pg.evaluate("() => { window.__stop=true; }")
        R = pg.evaluate("() => window.__R")
        assert len(R) > 25, (a, b, len(R))
        lo = min(R, key=lambda r: r[0])
        info = pg.evaluate("b => { var G=window._altoSolarGeo(), o=G.bodies[b], out=[[b, Math.round(o.d), 0]], s=window._altoSolar3D.ship(); Object.keys(G.bodies).forEach(function(i){ var k=G.bodies[i]; if(k.p===b) out.push([i, Math.round(k.d), Math.round(Math.hypot(k.x-o.x, k.y-o.y))]); }); out.push(['ship', Math.round(Math.hypot(s.x-o.x, s.y-o.y))]); return out; }", b)
        print("PLANE-info", a, b, info)
        ys = {round(r[2], 3) for r in R}
        rows.append((a, b, round(lo[0], 1), lo[1], round(R.index(lo) / len(R), 2), round(max(ys) - min(ys), 2)))
        worst = min(worst, lo[0])
        flat = flat and len(ys) == 1                                 # one plane, however it flew
    print("PLANE", craft, rows)
    assert flat, ("the ship's height changed", rows)
    assert worst > 2, ("the ship's path went over a body", worst, rows)
    pg.context.close()
    assert not errs, errs
