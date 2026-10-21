"""System, Luke's round 10: upright glyph chips and level named chips on the enlarged disc, clickable
spokes, unit borders (a hue ring / an Oort cloud), Flights and Spokes-only switches, navigation hints,
and brief.wallpaper_top (the wallpaper and the chart up behind the two top bars, their controls kept).

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401
from test_solar_pool import SMALL, SMALL_LINKS  # noqa: E402

NAMES = ["Duty", "Breach of care", "Proximate cause", "Damages", "Consent"]


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    d = solar_doc(SMALL, "spoke", SMALL_LINKS)
    d["brief"]["wallpaper_top"] = True
    d["brief"]["entities"] = [{"id": f"e{k}", "name": f"Party {k}"} for k in range(5)]
    d["brief"]["axes"] = [{"label": "Doctrines", "singular": "Doctrine", "hide_nav": True,
                           "values": [{"id": f"a{k}", "name": n} for k, n in enumerate(NAMES)]}]
    for n in d["nodes"]:
        if n["id"] == "u1-p1":
            n["entity_ids"] = [f"e{k}" for k in range(5)]
            n["axis1_values"] = [f"a{k}" for k in range(5)]
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    f = tmp_path_factory.mktemp("round10") / "r10.html"
    f.write_text(html, encoding="utf-8")
    return f


# the navigation hints now (round 11): the pills on the bodies, the ways drawn, and the edge pills
HINTS = r"""() => {
  var vis=function(e){ return !!e && e.offsetParent!==null && !e.hidden && getComputedStyle(e).display!=='none'; };
  var ps=[].slice.call(document.querySelectorAll('#world .node.sol-hint>.sol-nh')), qs=[].slice.call(document.querySelectorAll('#sol-nav .sol-nh'));
  return {pills:ps.map(function(p){ return p.parentNode.id+':'+p.dataset.k+':'+p.querySelector('kbd').textContent+':'+p.querySelector('i').getAttribute('data-a')+':'+p.querySelector('b').textContent; }).sort(),
    ways:[].map.call(document.querySelectorAll('#sol-way path'), function(w){ return w.getAttribute('data-k'); }).sort(),
    lbl:ps.map(function(p){ return +getComputedStyle(p.parentNode.querySelector(':scope>.sol-lbl')).opacity; }),
    once:ps.every(function(p){ var q=qs.filter(function(q){ return q.dataset.k===p.dataset.k; })[0]; return !!q && vis(p)!==vis(q); }),
    edge:qs.filter(vis).map(function(q){ var r=q.getBoundingClientRect(); return [q.dataset.k, q.querySelector('b').textContent, r.left>=0 && r.top>=0 && r.right<=innerWidth && r.bottom<=innerHeight]; })};
}"""


CHIPS = r"""() => {
  var c=document.querySelector('#node-u1-p1 .node-card');
  return [].filter.call(c.querySelectorAll(':scope > .node-footer > button'), function(x){ return getComputedStyle(x).display!=='none'; })
    .map(function(x){ var r=x.getBoundingClientRect(); return {txt:x.classList.contains('sol-txt'), tf:x.style.transform, top:Math.round(r.top), arc:x.getAttribute('data-arc')}; }); }"""


def test_glyph_chips_stand_upright_and_named_chips_sit_level_in_rows(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.mouse.move(2, 940)
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(1300)
    ch = pg.evaluate(CHIPS)
    glyph, named = [c for c in ch if not c["txt"]], [c for c in ch if c["txt"]]
    assert glyph and named, ch
    assert all(c["tf"] == "" for c in ch), ch                                   # nothing turned
    assert all(not str(c["arc"]).startswith("row") for c in glyph), glyph
    rows = {}
    for c in named:
        assert str(c["arc"]).startswith("row"), c
        rows.setdefault(c["arc"], set()).add(c["top"])
    assert all(len(v) == 1 for v in rows.values()), rows                        # level: one top per row
    assert max(min(v) for v in rows.values()) < min(c["top"] for c in glyph), (rows, glyph)   # above the arcs
    pg.context.close()
    assert not errs, errs


def test_a_spoke_click_goes_to_its_far_end_and_back(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    hit = """b => { var l=[].find.call(document.querySelectorAll('#solar-svg line.sol-hit'), function(x){ return x._r && x._r.sp && x._r.sp.b===b; });
      if(!l) return false; l.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true})); return true; }"""
    assert pg.evaluate(hit, "u1-p3")
    pg.wait_for_timeout(1300)
    assert pg.evaluate("() => window._focusedNodeId") == "u1-p3"
    pg.evaluate(hit, "u1-p3")
    pg.wait_for_timeout(1300)
    assert pg.evaluate("() => window._focusedNodeId") == "u1"
    assert pg.evaluate("() => document.querySelectorAll('#solar-svg .sol-bd').length") >= 3     # a border per system
    pg.context.close()
    assert not errs, errs


def test_hints_flights_and_spokes_only(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => window.enterFocus('u1-p2')")
    pg.wait_for_timeout(1300)
    h = pg.evaluate(HINTS)
    assert h["pills"] == ["node-u1-p1:w:←:Previous:Planet concept 1.1", "node-u1-p3:e:→:Next:Planet concept 1.3",
                          "node-u1:n:↑:Up a level:Doctrine 1"], h        # each target: its key, its move, its name
    assert h["ways"] == ["e", "n", "w"] and h["lbl"] == [0, 0, 0], h    # each one's way drawn; its own label steps aside
    assert h["once"], h                                                   # shown once: beside it, or at the window's edge
    # Flights: shown in the Star chart look only, kept per timeline
    assert pg.evaluate("() => document.getElementById('sol-fly').hidden")
    pg.evaluate("() => window._altoSolarLook.set('stars')")
    pg.wait_for_timeout(300)
    pg.click("#sol-fly")
    assert pg.evaluate("() => window._altoFlyOff === true && /alto-solar-fly:/.test(Object.keys(localStorage).join(' '))")
    pg.evaluate("() => window._altoSolarLook.set('hub')")
    # Spokes only: the canvas does not scroll; a wheel steps along the spokes
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(700)
    pg.click("#sol-lock")
    pg.evaluate("() => window.enterFocus('u2-p2')")
    pg.wait_for_timeout(1300)
    pg.mouse.move(650, 450)
    t0 = pg.evaluate("() => [document.getElementById('canvas').scrollLeft, document.getElementById('canvas').scrollTop]")
    pg.mouse.wheel(0, 200)
    pg.wait_for_timeout(1300)
    assert pg.evaluate("() => window._focusedNodeId") == "u2-p2-m1"
    pg.mouse.wheel(0, -200)
    pg.wait_for_timeout(1300)
    assert pg.evaluate("() => window._focusedNodeId") == "u2-p2"
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(700)
    pg.mouse.wheel(0, 400)
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => getComputedStyle(document.getElementById('canvas')).overflow") == "hidden"
    pg.context.close()
    assert not errs, errs
    assert t0


def test_hints_point_off_the_window_and_a_click_goes_there(browser, page):
    """A place off the window: its pill at the window's edge (inside it), on the way towards it; a click
    there hops. Spokes only says scroll; with nothing enlarged, one pill on the body a scroll enlarges."""
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => window._altoSolarLook.set('hub')")
    pg.evaluate("() => window.enterFocus('u2-p2')")
    pg.wait_for_timeout(1300)
    h = pg.evaluate(HINTS)
    assert h["once"] and "node-u2-p2-m1:s:↓:Down a level:Case 1" in h["pills"], h
    nxt = [e for e in h["edge"] if e[0] == "e"]
    assert nxt and nxt[0][1] == "Planet concept 3.1" and nxt[0][2], h   # the next system's first planet: off the window, pointed at
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#sol-nav .sol-nh[data-k=e]>i'), '::after').content") == '"Next system"'
    pg.click("#sol-nav .sol-nh[data-k=e]")
    pg.wait_for_timeout(1300)
    assert pg.evaluate("() => window._focusedNodeId") == "u3-p1"
    assert pg.evaluate(HINTS)["once"]
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(700)
    assert pg.evaluate("() => document.querySelectorAll('.sol-nh').length") == 0   # calm: nothing enlarged, nothing shown
    pg.click("#sol-lock")                                                       # Spokes only (it enlarges the middle body)
    pg.wait_for_timeout(1300)
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#world .sol-nh>i'), '::after').content").startswith('"Scroll')
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(800)
    o = pg.evaluate("() => [].map.call(document.querySelectorAll('.sol-nh'), function(p){ return p.dataset.k+':'+p.querySelector('i').getAttribute('data-a'); })")
    assert o == ["o:Scroll to enlarge"], o
    pg.click("#sol-lock")
    pg.context.close()
    assert not errs, errs


def test_hints_hide_in_a_flight_and_come_back_on_landing(browser, page):
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoFlyOff=false; window.enterFocus('u1-p2'); }")
    pg.wait_for_timeout(1500)
    assert pg.evaluate("() => document.querySelectorAll('#world .node.sol-hint').length") == 3
    r = pg.evaluate("""() => new Promise(function(done){ var seen=0, shown=0, t0=performance.now();
      document.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowRight', code:'ArrowRight', bubbles:true}));
      (function f(){ if(window._altoSolarFlight && window._altoSolarFlight()){ seen++;
          [].forEach.call(document.querySelectorAll('.sol-nh,#sol-way path'), function(e){ if(e.offsetParent!==null && getComputedStyle(e).opacity!=='0' && getComputedStyle(e.closest('#sol-nav,#sol-way')||e).opacity!=='0') shown++; }); }
        if(performance.now()-t0<6000 && !(seen && !window._altoSolarFlight())) requestAnimationFrame(f); else done([seen, shown]); })(); })""")
    assert r[0] > 3 and r[1] == 0, r                                            # in a flight: none shown
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => window._focusedNodeId") == "u1-p3"
    assert pg.evaluate("() => document.querySelectorAll('#world .node.sol-hint').length") >= 2  # back on landing
    pg.context.close()
    assert not errs, errs


def test_wallpaper_top_erases_the_bars_but_keeps_their_controls(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => window._altoSolarLook.set('hub')")
    pg.wait_for_timeout(300)
    s = pg.evaluate("""() => ['title-bar', 'nav'].map(function(id){ var e=document.getElementById(id), c=getComputedStyle(e);
      return [c.backgroundColor, c.backdropFilter || c.webkitBackdropFilter || 'none', getComputedStyle(e).visibility]; })""")
    assert all(x[0] == "rgba(0, 0, 0, 0)" and x[1] == "none" and x[2] == "visible" for x in s), s
    assert pg.evaluate("() => document.getElementById('canvas').getBoundingClientRect().top") == 0
    assert pg.evaluate("() => !!document.querySelector('#title-text') && document.querySelector('#title-text').offsetWidth > 0")
    pg.evaluate("() => window._altoSolarLook.set('stars')")                    # every look, every format (clear_top.py)
    pg.wait_for_timeout(300)
    assert pg.evaluate("() => document.getElementById('canvas').getBoundingClientRect().top") == 0
    assert pg.evaluate("() => getComputedStyle(document.getElementById('title-text')).color") == "rgb(238, 242, 255)"
    pg.context.close()
    assert not errs, errs


def test_a_resting_pointer_on_a_spoke_or_an_orbit_names_it(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => window._altoSolarLook.set('hub')")
    over = """sel => { var l=[].find.call(document.querySelectorAll('#solar-svg .sol-hit'), function(x){ return eval(sel); });
      l.dispatchEvent(new PointerEvent('pointerover', {bubbles:true, clientX:400, clientY:300})); return true; }"""
    tip = "() => { var t=[].filter.call(document.querySelectorAll('body > .line-tip'), function(x){ return x.style.display==='block'; })[0]; return t ? t.textContent : null; }"
    pg.evaluate(over, "x._r && x._r.sp && x._r.sp.b==='u1-p3'")
    pg.wait_for_timeout(120)
    assert pg.evaluate(tip) is None                                           # not while passing over: a dwell
    pg.wait_for_timeout(400)
    assert pg.evaluate(tip) == "Doctrine 1 — Planet concept 1.3", pg.evaluate(tip)
    assert pg.evaluate("() => document.getElementById('canvas').classList.contains('sol-lhov') && document.querySelectorAll('#world .node.edge-end').length === 2")
    pg.mouse.move(5, 5)
    pg.evaluate("() => document.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true}))")
    assert pg.evaluate(tip) is None
    pg.evaluate(over, "x._r && x._r.c==='u1' && !x._r.sp")
    pg.wait_for_timeout(500)
    assert (pg.evaluate(tip) or "").startswith("Orbit of Doctrine 1"), pg.evaluate(tip)
    pg.context.close()
    assert not errs, errs


def test_the_star_chart_has_a_retro_style_kept_per_timeline(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => window._altoSolarLook.set('hub')")
    assert pg.evaluate("() => document.getElementById('sol-sty').hidden")          # a Star chart style only
    pg.evaluate("() => window._altoSolarLook.set('stars')")
    pg.wait_for_timeout(300)
    pg.click("#sol-sty [data-sty=retro]")
    pg.wait_for_timeout(300)
    s = pg.evaluate("""() => { var c=document.querySelector('#node-u1 .node-card'), b=document.querySelector('#solar-svg .sol-band'), sp=document.querySelector('#solar-svg .sol-spoke');
      return [document.documentElement.classList.contains('sk-retro'), getComputedStyle(c).backgroundColor, getComputedStyle(b).display, getComputedStyle(sp).stroke,
              Object.keys(localStorage).filter(function(k){ return /alto-solar-style:/.test(k); }).map(function(k){ return localStorage.getItem(k); })]; }""")
    assert s[0] and s[1] == "rgb(245, 230, 189)" and s[2] != "none" and s[3] == "rgb(240, 193, 94)" and s[4] == ["retro"], s
    pg.click("#sol-sty [data-sty=classic]")
    assert not pg.evaluate("() => document.documentElement.classList.contains('sk-retro')")
    pg.context.close()
    assert not errs, errs


def test_the_realistic_style_turns_each_globe_on_its_axis(browser, page):
    pg, errs = _open(browser, page, reduced=False, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); window._altoSolarMotion.set(false); }")
    pg.wait_for_timeout(2500)
    snap = """() => [].map.call(document.querySelectorAll('#world canvas.sk-rot'), function(c){ if(!c.width) return ''; var d=c.getContext('2d').getImageData(0, 0, c.width, c.height).data, h=0;
      for(var i=0;i<d.length;i+=13) h=(h*31+d[i])>>>0; return h; })"""
    a = pg.evaluate(snap)
    drawn = [i for i, x in enumerate(a) if x]                                    # (only bodies on screen are drawn)
    assert len(drawn) >= 4, a
    pg.wait_for_timeout(1500)
    b = pg.evaluate(snap)
    assert sum(1 for i in drawn if a[i] != b[i]) >= len(drawn) // 2, (a, b)      # they turn with the orbits still
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#world canvas.sk-rot')).display") == "block"
    pg.evaluate("() => window._altoSolarStyle.set('classic')")
    pg.wait_for_timeout(200)
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#world canvas.sk-rot')).display") == "none"
    pg.context.close()
    assert not errs, errs
