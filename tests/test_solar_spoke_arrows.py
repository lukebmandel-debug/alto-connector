"""System, Spokes only: the arrows on the map. Luke (2026-10-23): "The problem with the navigation directions on spoke
only mode is that you don't know which arrow to look at and its not intuitive why something is in a certain direction".
He chose arrows drawn on the spoke lines leaving the current body, pointing where each destination really is on the
screen, each naming its destination; an arrow key takes the arrow that points its way.

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import math
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401
from test_solar_pool import SMALL, SMALL_LINKS  # noqa: E402


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))
    f = tmp_path_factory.mktemp("spoke_arrows") / "sa.html"
    f.write_text(html, encoding="utf-8")
    return f


# each arrow: its far end, its name, where it sits and points (from the enlarged disc's middle), its name's box
ARROWS = r"""() => {
  var f=window._focusedNodeId, c=document.querySelector('#node-'+f+' .node-card').getBoundingClientRect(), cx=c.left+c.width/2, cy=c.top+c.height/2,
    S=window._altoSolar3D, D3=document.documentElement.classList.contains('sk-3d') && S && S.on();
  return {r:c.width/2, f:f, spokes:window._altoSolarLock.spokes(f), hidden:document.getElementById('sol-arw').hidden,
    pills:document.querySelectorAll('#world .node.sol-hint').length,
    a:[].map.call(document.querySelectorAll('#sol-arw .sol-ar'), function(a){ var id=a.dataset.id, l=document.querySelector('#sol-arw .sol-al[data-id="'+id+'"]'),
      r=a.querySelector('svg').getBoundingClientRect(), lr=l.getBoundingClientRect(), q=D3 && S.project(id), n;
      if(!q){ n=document.querySelector('#node-'+id+' .node-card').getBoundingClientRect(); q={x:n.left+n.width/2, y:n.top+n.height/2}; }
      var m=new DOMMatrix(getComputedStyle(a).transform);
      return {id:id, name:l.textContent, shown:!l.classList.contains('sol-alx') && +getComputedStyle(l).opacity>0, at:[r.left+r.width/2-cx, r.top+r.height/2-cy],
        dir:[m.a, m.b], to:[q.x-cx, q.y-cy], l:[lr.left-cx, lr.top-cy, lr.right-cx, lr.bottom-cy], fs:getComputedStyle(l).fontSize}; })};
}"""


def _arrive(pg, want, timeout=7000):
    pg.wait_for_function("id => window._focusedNodeId===id && !window._altoSolarLock.riding()", arg=want, timeout=timeout)
    pg.wait_for_timeout(400)


def _lock_at(pg, style, at):
    pg.evaluate("a => { window._altoSolarStyles.set(a[0]); window._altoSolarLock.set(true); window.enterFocus(a[1]); }", [style, at])
    pg.wait_for_timeout(1800)


def _check(h):
    """One arrow per spoke, on its spoke just outside the disc, pointing at its far end, named for it; the names clear
    of the disc and of each other, at one size."""
    assert not h["hidden"] and h["pills"] == 0, h                                     # the arrows, not the pills
    assert sorted(a["id"] for a in h["a"]) == sorted(h["spokes"]) and h["a"], h
    shown = []
    for a in h["a"]:
        L = math.hypot(*a["to"]) or 1
        ux, uy = a["to"][0] / L, a["to"][1] / L
        assert ux * a["dir"][0] + uy * a["dir"][1] > .995, a                          # it points where its body is on the screen
        d = math.hypot(*a["at"])
        assert h["r"] + 14 < d < h["r"] + 70, (a, h["r"])                               # just outside the disc ...
        assert abs(ux * a["at"][1] - uy * a["at"][0]) < 3, a                          # ... on the spoke
        assert a["name"] and a["fs"] == h["a"][0]["fs"], a                              # one size, whatever the body
        if a["shown"]:
            x0, y0, x1, y1 = a["l"]
            nx, ny = max(x0, min(x1, 0)), max(y0, min(y1, 0))
            assert math.hypot(nx, ny) >= h["r"], a                                     # clear of the disc
            assert all(not (x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1) for b in shown), a   # and of the other names
            shown.append(a["l"])
    assert shown, h


@pytest.mark.parametrize("style", ["system", "chart", "retro"])
def test_an_arrow_on_each_spoke_points_at_its_far_end_and_names_it(browser, page, style):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    for at in ("u1-p2", "u1"):                                                         # a planet (up and down) and a sun (its planets, its linked sun)
        _lock_at(pg, style, at)
        h = pg.evaluate(ARROWS)
        _check(h)
        names = pg.evaluate("ids => ids.map(function(id){ return document.getElementById('node-'+id).querySelector('.sol-lbl').getAttribute('data-l'); })", [a["id"] for a in h["a"]])
        assert [a["name"] for a in h["a"]] == names, h
    pg.evaluate("() => window._altoSolarLock.set(false)")
    pg.wait_for_timeout(400)
    assert pg.evaluate("() => document.querySelectorAll('#sol-arw .sol-ar').length") == 0      # normal mode: its named pills
    pg.context.close()
    assert not errs, errs


def test_an_arrow_key_rides_the_arrow_pointing_its_way(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _lock_at(pg, "system", "u1-p2")
    for _ in range(3):
        h = pg.evaluate(ARROWS)
        best = {}
        for key, v in (("ArrowUp", (0, -1)), ("ArrowDown", (0, 1)), ("ArrowLeft", (-1, 0)), ("ArrowRight", (1, 0))):
            k = max(h["a"], key=lambda a: a["dir"][0] * v[0] + a["dir"][1] * v[1])
            if k["dir"][0] * v[0] + k["dir"][1] * v[1] > .5:
                best[key] = k["id"]
        assert best, h
        key, want = sorted(best.items())[0]
        pg.keyboard.press(key)
        _arrive(pg, want)
    # a key with no arrow its way says so and stays
    h = pg.evaluate(ARROWS)
    free = [key for key, v in (("ArrowUp", (0, -1)), ("ArrowDown", (0, 1)), ("ArrowLeft", (-1, 0)), ("ArrowRight", (1, 0)))
            if all(a["dir"][0] * v[0] + a["dir"][1] * v[1] < .3 for a in h["a"])]
    if free:
        f = h["f"]
        pg.keyboard.press(free[0])
        pg.wait_for_timeout(500)
        assert pg.evaluate("() => window._focusedNodeId") == f and not pg.evaluate("() => window._altoSolarLock.riding()")
        assert pg.evaluate("() => document.querySelector('.sol-nope').textContent") == "No spoke that way"
    pg.context.close()
    assert not errs, errs


def test_a_click_rides_and_a_hover_lights_the_arrow_its_name_and_its_spoke(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _lock_at(pg, "chart", "u1")
    h = pg.evaluate(ARROWS)
    to = h["a"][0]["id"]
    pg.hover(f'#sol-arw .sol-ar[data-id="{to}"]')
    pg.wait_for_timeout(150)
    hot = pg.evaluate("""id => [document.querySelector('#sol-arw .sol-al[data-id="'+id+'"]').classList.contains('hot'),
      +getComputedStyle(document.querySelector('#sol-arw .sol-al[data-id="'+id+'"]')).opacity, document.querySelectorAll('#solar-svg .sol-route').length]""", to)
    assert hot[0] and hot[1] == 1 and hot[2] >= 1, hot
    pg.click(f'#sol-arw .sol-ar[data-id="{to}"]')
    _arrive(pg, to)
    _check(pg.evaluate(ARROWS))                                                         # and the arrows of the body arrived at
    pg.context.close()
    assert not errs, errs


def test_on_a_phone_a_tap_on_an_arrow_rides_there(browser, page):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, reduced_motion="reduce")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page.as_uri())
    pg.wait_for_timeout(1400)
    if pg.evaluate("() => document.documentElement.classList.contains('mobile')"):
        pytest.skip("the one-card phone view (no System board)")
    _lock_at(pg, "system", "u1-p2")
    h = pg.evaluate(ARROWS)
    assert h["a"] and not h["hidden"], h
    on = pg.evaluate("""() => [].map.call(document.querySelectorAll('#sol-arw .sol-ar'), function(a){ var r=a.getBoundingClientRect();
      return [a.dataset.id, r.left>=0 && r.right<=innerWidth && r.top>=0 && r.bottom<=innerHeight, r.width, r.height]; })""")
    assert all(o[1] for o in on), on                                                     # every arrow on the window
    assert all(a["shown"] for a in h["a"]), h                                            # every name shown (no hover on a phone)
    assert pg.evaluate("""() => [].every.call(document.querySelectorAll('#sol-arw .sol-al'), function(l){ var r=l.getBoundingClientRect();
      return r.left>=0 && r.right<=innerWidth && r.top>=0 && r.bottom<=innerHeight; })""")                 # on the window, at the page's own zoom
    to = on[0][0]
    pg.tap(f'#sol-arw .sol-ar[data-id="{to}"]')
    _arrive(pg, to)
    ctx.close()
    assert not errs, errs


def test_3d_star_chart_points_at_the_scene_and_keeps_its_spokes_lit(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    _lock_at(pg, "3d", "u1-p2")
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pytest.skip("no WebGL in this browser")
    pg.wait_for_timeout(1200)
    h = pg.evaluate(ARROWS)
    _check(h)
    assert pg.evaluate("() => document.querySelectorAll('#sk3d-l i:not([style*=\"display: none\"])').length") == 0     # its own pills give way
    pg.context.close()
    assert not errs, errs


FLYING = """() => { var p=document.querySelector('#solar-fly-svg .fly-path'), s=p && p.closest('svg');
  return {flight:!!window._altoSolarFlight(), ride:!!window._altoSolarLock.riding(),
    path:!!p && (p.getAttribute('d')||'').length>20 && !s.classList.contains('fly-out') && getComputedStyle(s).display!=='none'}; }"""


@pytest.mark.parametrize("style", ["chart", "retro"])
def test_normal_mode_moves_fly_their_flight_paths_and_spokes_only_rides_the_spokes(browser, page, style):
    """Luke on v1.9.150 (2026-10-23): "spoke only mode on classic star chart works correctly, but it has since gotten rid
    of the actual flight paths for non-spoke only mode incorrectly". With Spokes only off, a move (the bar's Next, an
    arrow key, a named button) flies the flight's own course again; with it on, it rides the spokes."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("s => { window._altoSolarStyles.set(s); window._altoSolarLock.set(false); window._altoFlyOff=false; window.enterFocus('u1-p3'); }", style)
    pg.wait_for_timeout(2500)
    pg.mouse.move(2, 600)
    pg.click("#sol-tour .tb-next")
    pg.wait_for_timeout(400)
    st = pg.evaluate(FLYING)
    assert st == {"flight": True, "ride": False, "path": True}, st                  # its flight path drawn, not a spoke ride
    pg.wait_for_function("() => !window._altoSolarFlight() && window._focusedNodeId && window._focusedNodeId!=='u1-p3'", timeout=12000)
    pg.wait_for_timeout(700)
    pg.keyboard.press("ArrowLeft")                                                   # an arrow key: the same
    pg.wait_for_timeout(400)
    st = pg.evaluate(FLYING)
    assert st["flight"] and not st["ride"] and st["path"], st
    pg.wait_for_function("() => !window._altoSolarFlight() && window._focusedNodeId==='u1-p3'", timeout=12000)
    pg.wait_for_timeout(700)
    pg.evaluate("() => window._altoSolarLock.set(true)")                             # Spokes only: rides along the spokes, no flight
    pg.wait_for_timeout(300)
    pg.click("#sol-tour .tb-next")
    pg.wait_for_timeout(400)
    st = pg.evaluate(FLYING)
    assert st["ride"] and not st["flight"] and not st["path"], st
    pg.evaluate("() => window._altoSolarLock.set(false)")
    pg.context.close()
    assert not errs, errs
