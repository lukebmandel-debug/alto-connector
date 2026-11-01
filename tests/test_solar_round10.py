"""System, Luke's round 10: upright glyph chips and level named chips on the enlarged disc, clickable
spokes, unit borders (a hue ring / an Oort cloud), Flights and Spokes-only switches, navigation hints,
and brief.wallpaper_top (the wallpaper and the chart up behind the two top bars, their controls kept).

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import json
import math
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


def test_the_ship_shows_in_the_star_charts_only(browser, page):
    """(Flights and Ship are one picker now, and Spokes only is gone: test_solar_controls.py)"""
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => window._altoSolarLook.set('hub')")
    pg.wait_for_timeout(300)
    assert pg.evaluate("() => [document.getElementById('sol-craft').hidden, !!document.querySelector('#sol-fly,#sol-lock')]") == [True, False]
    pg.evaluate("() => window._altoSolarLook.set('stars')")
    pg.wait_for_timeout(300)
    assert not pg.evaluate("() => document.getElementById('sol-craft').hidden")
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
    assert pg.eval_on_selector_all("#sol-sty [data-style]", "b => b.map(x => x.textContent)") == \
        ["System", "Star chart", "Retro", "3D Star chart", "Holographic"]               # one switch of four styles (2026-10-22), Holographic the fifth (holo.py)
    assert not pg.evaluate("() => document.documentElement.classList.contains('sk-retro')")
    pg.click("#sol-sty [data-style=retro]")
    pg.wait_for_timeout(300)
    s = pg.evaluate("""() => { var c=document.querySelector('#node-u1 .node-card'), b=document.querySelector('#solar-svg .sol-oband'), sp=document.querySelector('#solar-svg .sol-spoke');
      return [document.documentElement.classList.contains('sk-retro'), getComputedStyle(c).backgroundColor, getComputedStyle(b).display, getComputedStyle(sp).stroke,
              Object.keys(localStorage).filter(function(k){ return /alto-solar-style:/.test(k); }).map(function(k){ return localStorage.getItem(k); })]; }""")
    assert s[0] and s[1] == "rgb(245, 230, 189)" and s[2] != "none" and s[3] == "rgb(240, 193, 94)" and s[4] == ["retro"], s
    pg.click("#sol-sty [data-style=chart]")
    assert not pg.evaluate("() => document.documentElement.classList.contains('sk-retro')")
    pg.context.close()
    assert not errs, errs


def test_a_choice_kept_by_the_old_two_switches_opens_in_the_matching_style(browser, page):
    """Luke (2026-10-22): one style switch, System | Star chart | Retro | 3D Star chart, in place of the look switch and the
    Star chart's own Classic | Retro | Realistic 3D. A reader's kept look + style reads as the matching one of the four."""
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('hub'); window._altoSolarStyle.set('retro'); }")     # both keys now kept
    sk = pg.evaluate("() => Object.keys(localStorage).filter(function(k){ return /^alto-solar-style:/.test(k); })")
    assert len(sk) == 1, sk                                              # (the look this page opens in writes nothing: name both keys)
    keys = [sk[0], sk[0].replace("-style:", "-look:")]
    for look, sty, want in (("hub", "retro", "system"), ("hub", "real", "system"), ("plain", "classic", "system"),
                            ("stars", "classic", "chart"), ("stars", "retro", "retro"), ("stars", "real", "3d")):
        ctx = browser.new_context(viewport={"width": 1500, "height": 950}, reduced_motion="reduce")
        vals = {k: (look if "-look:" in k else sty) for k in keys}       # kept before the page loads, as a returning viewer's
        ctx.add_init_script("(function(v){ try{ for(var k in v) localStorage.setItem(k, v[k]); }catch(e){} })(%s)" % json.dumps(vals))
        q = ctx.new_page(); q.goto(page.as_uri()); q.wait_for_timeout(1400)
        st = q.evaluate("""() => { var de=document.documentElement; return [window._altoSolarStyles.get(),
            [].map.call(document.querySelectorAll('#sol-sty [aria-checked=true]'), function(b){ return b.getAttribute('data-style'); }),
            de.classList.contains('sk-retro'), de.classList.contains('sk-real'), de.classList.contains('alto-solar-hub')]; }""")
        ctx.close()
        assert st[0] == want and st[1] == [want], (look, sty, st)
        assert st[2] == (want == "retro") and st[3] == (want == "3d") and st[4] == (want == "system"), (look, sty, st)
    for v in ("chart", "3d", "system", "retro"):                                     # the switch itself
        pg.click(f"#sol-sty [data-style='{v}']"); pg.wait_for_timeout(200)
        assert pg.evaluate("() => window._altoSolarStyles.get()") == v
    assert not pg.evaluate("() => document.getElementById('sol-craft').hidden")
    pg.click("#sol-sty [data-style=system]"); pg.wait_for_timeout(200)
    assert pg.evaluate("() => document.getElementById('sol-craft').hidden && !document.querySelector('#sol-fly,#sol-lock')")
    pg.context.close()
    assert not errs, errs


def test_without_webgl_the_realistic_style_turns_each_globe_in_2d(browser, page):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    ctx.add_init_script("(() => { var g=HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext=function(k){ return /webgl/.test(k) ? null : g.apply(this, arguments); }; })()")
    pg = ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.goto(page.as_uri()); pg.wait_for_timeout(1400)
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


def test_realistic_3d_is_a_3d_scene_with_a_free_camera(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }")
    pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pytest.skip("no WebGL in this browser")
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#node-u1-p1')).visibility") == "hidden"    # the board is under the scene
    assert pg.evaluate("() => document.querySelectorAll('#sk3d-l b').length") >= 6                              # names over the scene
    # a click on a body (where the scene draws it) enlarges it; the hints are pills at their bodies
    q = pg.evaluate("() => window._altoSolar3D.project('u1-p2')")
    pg.mouse.click(q["x"], q["y"])
    pg.wait_for_timeout(1500)
    assert pg.evaluate("() => window._focusedNodeId") == "u1-p2"
    pills = pg.evaluate("() => [].filter.call(document.querySelectorAll('#sk3d-l i'), function(e){ return e.style.display!=='none'; }).map(function(e){ return e.textContent; })")
    kids = pg.evaluate("() => window._altoSolarNavApi.kids('u1-p2').map(window._altoSolarNavApi.name)")
    assert sorted(p.strip() for p in pills) == sorted(kids), (pills, kids)               # (the nav, 2026-10-26: what is beside it, by name, no arrows)
    # a drag turns the camera; the wheel comes nearer; Reset view puts it back
    c0 = pg.evaluate("() => window._altoSolar3D.cam()")
    pg.mouse.move(200, 600); pg.mouse.down(); pg.mouse.move(380, 520, steps=6); pg.mouse.up()
    c1 = pg.evaluate("() => window._altoSolar3D.cam()")
    assert abs(c1["az"] - c0["az"]) > .5 and abs(c1["el"] - c0["el"]) > .2 and pg.evaluate("() => window._focusedNodeId") == "u1-p2", (c0, c1)
    nx = pg.evaluate("() => { var s=window._altoNavOpt.scope('u1-p2'), i=s.indexOf('u1-p2'); return i<0 ? s[0] : s[(i+1)%s.length]; }")
    pg.mouse.move(200, 600); pg.mouse.wheel(0, 300); pg.wait_for_timeout(1500)             # (close up, a scroll goes round what is beside it: Luke, 2026-10-26)
    assert pg.evaluate("() => window._focusedNodeId") == nx
    pg.keyboard.press("Escape"); pg.wait_for_timeout(1100)
    c1 = pg.evaluate("() => window._altoSolar3D.cam()")
    pg.mouse.move(200, 600); pg.mouse.wheel(0, 300); pg.wait_for_timeout(1100)             # (nothing enlarged: scrolling out flies back out)
    assert pg.evaluate("() => window._altoSolar3D.cam().d") > c1["d"] * 1.2 and not pg.evaluate("() => window._focusedNodeId")
    pg.click("#sk3d-reset"); pg.wait_for_timeout(1000)
    c2 = pg.evaluate("() => window._altoSolar3D.cam()")
    assert abs(c2["az"] + .6) < .01 and abs(c2["el"] - .62) < .01, c2
    # Classic: no scene
    pg.keyboard.press("Escape"); pg.wait_for_timeout(600)
    pg.evaluate("() => window._altoSolarStyle.set('classic')"); pg.wait_for_timeout(800)
    assert not pg.evaluate("() => document.documentElement.classList.contains('sk-3d')")
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#node-u1-p1')).visibility") == "visible"
    pg.context.close()
    assert not errs, errs


def test_an_enlarged_body_is_its_globe_close_up(browser, page):
    """Luke (2026-10-21): the enlarged body a game close-up, one camera move in and back, the card's content over the globe."""
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }")
    pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pytest.skip("no WebGL in this browser")
    c0 = pg.evaluate("() => window._altoSolar3D.cam()")
    pg.evaluate("() => window.enterFocus('u1-p2')")
    # one continuous move: the distance only falls, never jumps, on the way in
    ds = pg.evaluate("""() => new Promise(function(res){ var o=[]; (function f(){ o.push(window._altoSolar3D.cam().d); if(o.length<75) requestAnimationFrame(f); else res(o); })(); })""")
    assert all(b <= a * 1.001 for a, b in zip(ds, ds[1:])), ds
    assert max(a / b for a, b in zip(ds, ds[1:])) < 1.25, ds
    pg.wait_for_timeout(1200)
    q = pg.evaluate("""() => { var c=document.querySelector('#node-u1-p2 .node-card').getBoundingClientRect(), g=window._altoSolarGeo().bodies['u1-p2'], p=window._altoSolar3D.project('u1-p2');
      return {cx:c.left+c.width/2, cy:c.top+c.height/2, r:c.width/2, px:p.x, py:p.y, pr:g.d/2*p.s, lock:window._altoSolar3D.closeup().lock,
        bg:getComputedStyle(document.querySelector('#node-u1-p2 .node-card')).backgroundColor, op:getComputedStyle(document.querySelector('#node-u1-p2 .sol-body')).opacity}; }""")
    assert q["lock"] == "u1-p2", q
    assert abs(q["px"] - q["cx"]) < 4 and abs(q["py"] - q["cy"]) < 4 and abs(q["pr"] / q["r"] - 1) < .06, q   # the globe fills the disc's circle
    assert q["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and float(q["op"]) > .95, q                        # no flat disc: the content over the globe
    pg.keyboard.press("Escape"); pg.wait_for_timeout(1300)
    c1 = pg.evaluate("() => window._altoSolar3D.cam()")
    assert abs(c1["d"] / c0["d"] - 1) < .05 and abs(c1["az"] - c0["az"]) < .05, (c0, c1)                   # and back to where it was
    pg.context.close()
    assert not errs, errs


def test_3d_small_bodies_are_varied_real_objects_and_nothing_blocks_the_close_up(browser, page):
    """Luke (2026-10-22): an enlarged satellite was a blank grid sphere beside a giant black moon. Moons cycle six kinds by their
    order under their planet; the satellite level is a satellite, station, asteroid or comet, neighbours never alike; a plan's
    look is honoured; close up, a body in front of the enlarged one (or bigger on screen than its disc, but not its parent) fades away."""
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    S = pg.evaluate("() => { var N=window._ALTO_SOLAR.nodes, g=window._altoSolarGeo().bodies, o={}; Object.keys(g).forEach(function(id){ o[id]={role:g[id].role, p:g[id].p}; }); return o; }")
    planet = [i for i in S if S[i]["role"] == "planet"][-1]
    pg.evaluate("id => { window._ALTO_SOLAR.nodes[id].look='blackhole'; }", planet)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }")
    pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pytest.skip("no WebGL in this browser")
    K = pg.evaluate("() => window._altoSolar3D.kinds()")
    assert K[planet] == "blackhole"
    for role, kinds in (("moon", {"moon", "icy", "sulphur", "rust", "carbon", "haze"}), ("sat", {"sat", "station", "asteroid", "comet"})):
        ids = [i for i in S if S[i]["role"] == role]
        assert ids and all(K[i] in kinds for i in ids), (role, {i: K[i] for i in ids})
        by = {}
        for i in ids:
            by.setdefault(S[i]["p"], []).append(K[i])
        assert all(len(set(v)) == len(v) for v in by.values() if len(v) <= len(kinds)), by          # siblings never alike
    sat = [i for i in S if S[i]["role"] == "sat"][0]
    pg.evaluate("id => window.enterFocus(id)", sat)
    pg.wait_for_timeout(2400)
    q = pg.evaluate("""id => { var G=window._altoSolarGeo().bodies, P=window._altoSolar3D, f=P.project(id), F=P.fades(), rf=G[id].d/2*f.s, out=[];
      Object.keys(G).forEach(function(k){ var p=P.project(k); if(k===id || !p) return; var r=G[k].d/2*p.s, d=Math.hypot(p.x-f.x, p.y-f.y);
        if((r>rf*1.25 && k!==G[id].p) || (p.w<f.w*.93 && d<r+rf*1.1)) out.push([k, F[k]==null ? 1 : F[k]]); }); return {lock:P.closeup().lock, out:out}; }""", sat)   # (its parent: only when in front, 2026-10-30)
    assert q["lock"] == sat and all(f < .1 for _, f in q["out"]), q
    pg.keyboard.press("Escape"); pg.wait_for_timeout(1400)
    assert pg.evaluate("() => Object.keys(window._altoSolar3D.fades()).length") == 0                     # all back on the way out
    pg.context.close()
    assert not errs, errs


# Luke, 2026-10-30 (L-1030-142055): "When coming into orbit of something, the parent planet disappears"
PARENT = """id => { var G=window._altoSolarGeo().bodies, P=window._altoSolar3D, f=P.project(id), p=P.project(G[id].p), F=P.fades(), rf=G[id].d/2*f.s;
  var r=G[G[id].p].d/2*p.s, d=Math.hypot(p.x-f.x, p.y-f.y);
  return {lock:P.closeup().lock, par:G[id].p, fa:F[G[id].p]==null ? 1 : F[G[id].p], front:p.w<f.w*.93 && d<r+rf*1.1, big:r/rf}; }"""


def test_3d_in_orbit_of_a_moon_or_satellite_its_parent_planet_stays_in_view(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }")
    pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pytest.skip("no WebGL in this browser")
    S = pg.evaluate("() => { var g=window._altoSolarGeo().bodies, o={}; Object.keys(g).forEach(function(id){ o[id]={role:g[id].role, p:g[id].p}; }); return o; }")
    kids = [i for i in S if S[i]["role"] in ("moon", "sat") and S.get(S[i]["p"], {}).get("role") == "planet"][:3]
    assert kids, S
    seen = []
    for i in kids:
        pg.evaluate("id => window.enterFocus(id)", i)
        pg.wait_for_function("id => window._altoSolar3D.closeup().lock===id && !window._altoSolar3D.closeup().moving", arg=i, timeout=20000)
        pg.wait_for_timeout(600)
        seen.append((i, pg.evaluate(PARENT, i)))
    pg.context.close()
    assert not errs, errs
    behind = [(i, q) for i, q in seen if not q["front"]]
    assert behind, seen                                                       # (the case Luke saw: the planet behind its moon, bigger on screen)
    assert all(q["fa"] > .9 for _, q in behind), behind                       # it stays; only a planet between the camera and the disc may fade


# Art, 2026-10-30 (alto-art-1030-2000-b): a moon hidden behind its planet kept its name floating over the planet
HIDDEN_NAMES = """() => { var G=window._altoSolarGeo().bodies, P=window._altoSolar3D, F=P.fades(), by={}, out=[], named=0;
  Object.keys(G).forEach(function(k){ var n=document.getElementById('node-'+k), lb=n && n.querySelector('.sol-lbl'); by[(lb && lb.getAttribute('data-l')) || (n && n.getAttribute('data-title')) || '']=k; });
  [].forEach.call(document.querySelectorAll('#sk3d-l > b'), function(e){ if(e.style.display==='none') return; var id=by[e.textContent], q=id && P.project(id); if(!q) return; named++;
    Object.keys(G).forEach(function(k){ var p=P.project(k); if(k===id || !p || (F[k]!=null && F[k]<.5)) return;
      if(p.w<q.w && Math.hypot(p.x-q.x, p.y-q.y)<G[k].d/2*p.s) out.push([e.textContent, id, 'behind', k]); }); });
  return {named:named, hidden:out}; }"""


def test_3d_a_body_hidden_behind_another_shows_no_name(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoSolarStyle.set('real'); }")
    pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pytest.skip("no WebGL in this browser")
    seen = []
    for i in ("u1-p1-m1", "u1-p1-m2", "u1-p3-m1"):
        pg.evaluate("id => window.enterFocus(id)", i)
        pg.wait_for_function("id => window._altoSolar3D.closeup().lock===id && !window._altoSolar3D.closeup().moving", arg=i, timeout=20000)
        pg.wait_for_timeout(900)
        seen.append((i, pg.evaluate(HIDDEN_NAMES)))
    pg.context.close()
    assert not errs, errs
    assert any(q["named"] for _, q in seen), seen                            # (names were read: the check is not empty)
    assert all(not q["hidden"] for _, q in seen), seen


def test_the_3d_scene_is_small_and_on_system_pages_only():
    import gzip
    from alto.build import blocks
    from alto.build.solar_3d import SOLAR3D_CSS, SOLAR3D_JS
    size = len(gzip.compress((SOLAR3D_JS + SOLAR3D_CSS).encode("utf-8"), 9))
    assert size < 22600, size                   # (~22.3 KB with 1.9.187's camera keep-out shell and sun-side choice; ~21.2 KB with 1.9.17x's flame plumes, rocket flip, warp streaks and flashes; ~16.3 KB gz: a small WebGL kit with its shaders, the close-up's procedural detail and the flying craft, no library; ~20.2 KB with 1.9.146's moon kinds, satellites, stations, asteroids, comets and black holes)
    assert "SOLAR3D_JS" in open(blocks.__file__, encoding="utf-8").read()


def test_a_detail_page_keeps_its_top_bars(browser, page):
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    bars = """() => ['title-bar', 'nav'].map(function(id){ var c=getComputedStyle(document.getElementById(id)); return c.backgroundColor; })"""
    assert all(b == "rgba(0, 0, 0, 0)" for b in pg.evaluate(bars))                    # the main page: clear
    pg.evaluate("() => showDetail('node', 'u1-p1')")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => document.documentElement.classList.contains('detail-open')")
    assert not any(b == "rgba(0, 0, 0, 0)" for b in pg.evaluate(bars)), pg.evaluate(bars)   # the detail page: its glass back
    assert pg.evaluate("() => { var b=document.getElementById('ct-chips'); return !b || getComputedStyle(b).display==='none'; }")
    pg.context.close()
    assert not errs, errs


SPOT = """id => { var n=document.getElementById('node-'+id).getBoundingClientRect(); return [n.left+n.width/2, n.top+n.height/2]; }"""
SCROLL = "() => [document.getElementById('canvas').scrollLeft, document.getElementById('canvas').scrollTop]"


def test_retro_flies_a_regal_ship_smoothly(browser, page):
    """Retro's craft (Luke, 2026-10-21: "more of a spaceship ... Foundation ... more regal"), drawn every frame (no
    stop-motion), on a slower clock, its heading eased; the same ship rides the spokes. (The Halo, Retro's default,
    jumps since 2026-10-25 — test_the_halo_jumps_in_a_flash_of_light — so a craft that flies the way: the Rocket.) Spokes only and its rides are gone: 2026-10-25.)"""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoCraft.set('rocket'); window._altoSolarLook.set('stars'); window._altoSolarStyle.set('retro'); window._altoFlyOff=false; window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u2-p1')")
    f = pg.evaluate("""() => new Promise(function(done){ var seen=[], n=0, t0=performance.now();
      (function g(){ var c=document.querySelector('#solar-fly-svg .fly-craft'); if(c){ seen.push(c.getAttribute('transform')); n++; }
        if(performance.now()-t0<900) requestAnimationFrame(g); else done({n:n, distinct:new Set(seen).size, ship:getComputedStyle(document.querySelector('#solar-fly-svg .fly-ship')).display,
          hull:getComputedStyle(document.querySelector('#solar-fly-svg .fly-hull')).display, fl:window._altoSolarFlight(), ms:window._altoFlyMs}); })(); })""")
    assert f["ship"] == "inline" and f["hull"] == "none", f
    assert f["n"] > 20 and f["distinct"] >= f["n"] * .8, f                     # every frame, not 12 a second
    assert f["fl"] and f["ms"] >= min(f["fl"]["D"] * 1000 * 1.25, 5000), f       # the stately clock (a flight at most 5 s on the screen)
    pg.wait_for_timeout(int(f["ms"]) + 600)
    pg.context.close()
    assert not errs, errs


def test_ships_to_choose_explorer_and_halo(browser, page):
    """Luke (2026-10-21): "give users choice ships/crafts"; (2026-10-22, from three options sheets) "P4 is the best ...
    i want high def graphics" and Halo kept; (2026-10-25) "add a classic rocket ship design" — one choice per viewer, in
    every Star chart style; Retro's Halo its default there, the Explorer elsewhere; each a dense high-definition model."""
    pg, errs = _open(browser, page, reduced=True, wait=1400)
    pg.evaluate("() => { window._altoSolarLook.set('stars'); window._altoSolarStyle.set('retro'); }")
    L = pg.evaluate("() => window._altoCraft.list.map(function(c){ var m=window._altoCraft.mesh(c.id); return [c.id, c.real, m.p.length, m.k.length]; })")
    assert [c for c, _, _, _ in L] == ["explorer", "halo", "rocket"], L
    assert all(n >= 9 * 10000 and n % 9 == 0 and k * 3 == n * 4 for _, _, n, k in L), L   # each a dense model (10,000+ triangles)
    assert pg.evaluate("() => window._altoCraft.id()") == "halo"
    pg.evaluate("() => window._altoSolarStyle.set('classic')")
    assert pg.evaluate("() => window._altoCraft.id()") == "explorer"
    pg.click("#sol-craft"); pg.wait_for_timeout(200)
    assert pg.evaluate("() => document.querySelectorAll('#sol-craft-pop [data-craft]').length") == len(L)
    assert pg.evaluate("() => document.querySelectorAll('#sol-craft-pop .cr-g').length") == 1      # (no empty group)
    pg.click("#sol-craft-pop [data-craft=halo]"); pg.wait_for_timeout(200)
    assert pg.evaluate("() => [localStorage.getItem('alto-ship'), !!document.getElementById('sol-craft-pop'), document.getElementById('sol-craft').title]") == [
        "halo", False, "Your ship: Halo, flying you between bodies (click to choose another, or Off)"]
    pg.evaluate("() => window._altoSolarStyle.set('retro')")
    assert pg.evaluate("() => window._altoCraft.id()") == "halo"                       # a choice holds in every style
    pg.evaluate("() => window._altoCraft.set('explorer')"); pg.evaluate("() => window._altoSolarStyle.set('classic')")
    assert pg.evaluate("() => window._altoCraft.id()") == "explorer"
    RO = """() => { var s=document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.innerHTML='<g class="fly-ship">'+window._altoCraft.svg('explorer')+'</g>';
      document.body.appendChild(s); var d=getComputedStyle(s.querySelector('.sh-ro')).display; s.remove(); return d; }"""
    assert pg.evaluate(RO) == "none"                                                    # the flat top-down drawing in Classic,
    pg.evaluate("() => window._altoSolarStyle.set('retro')")
    assert pg.evaluate(RO) == "inline"                                                  # with its gold deco details in Retro
    pg.click("#sol-craft"); pg.wait_for_timeout(150); pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    assert not pg.evaluate("() => !!document.getElementById('sol-craft-pop')")
    pg.context.close()
    assert not errs, errs


def test_a_flight_in_3d_flies_the_chosen_craft_then_dives_close_up(browser, page):
    """Luke (2026-10-21): "i want a real ship" — in Realistic 3D the chosen craft is a lit model on the route, the camera
    behind it, and the landing hands into the close-up's dive; in 2D the same craft's art flies."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoCraft.set('halo'); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('classic'); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u2-p1')"); pg.wait_for_timeout(500)
    assert pg.evaluate("() => !!document.querySelector('#solar-fly-svg .fly-ship circle.sh-hull[r=\"20\"]')")   # the Halo's own art
    pg.wait_for_timeout(int(pg.evaluate("() => window._altoFlyMs")) + 400)
    pg.evaluate("() => window._altoSolarStyle.set('real')"); pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close(); pytest.skip("no WebGL in this browser")
    pg.evaluate("() => window.enterFocus('u1-p1')"); pg.wait_for_timeout(1000)
    s = pg.evaluate("() => { var f=window._altoSolarFlight(), s=window._altoSolar3D.ship(); return {f:!!f, s:s, d:window._altoSolar3D.cam().d}; }")
    assert s["f"] and s["s"] and s["s"]["craft"] == "halo" and s["s"]["on"], s
    assert s["d"] < 700 and abs(s["s"]["sx"] - 650) < 400, s                          # the camera is with the craft
    pg.wait_for_timeout(int(pg.evaluate("() => window._altoFlyMs")) + 1600)
    q = pg.evaluate("() => [window._focusedNodeId, window._altoSolar3D.closeup().lock, window._altoSolarFlight()]")
    assert q[0] == "u1-p1" and q[1] == "u1-p1" and q[2] is None, q
    pg.context.close()
    assert not errs, errs


def test_ships_point_along_their_way_and_arrive_into_an_orbit(browser, page):
    """Luke (2026-10-22): "it should come into a gentle orbit around planets ... always be sort of pointing accurately
    according to its line ... we don't need the ship to be massive, just clear" — the 2D craft's nose is the way's
    tangent every frame, it is small, it lands in an orbit round the body (never on it) and stays in it; in 3D the model
    goes on round the body while the close-up shows."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoCraft.set('explorer'); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('classic'); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u2-p1')")
    f = pg.evaluate("""() => new Promise(function(done){ var off=[], n=0, big=0;
      (function g(){ var F=window._altoSolarFlight(), c=document.querySelector('#solar-fly-svg .fly-craft');
        if(F && c){ var m=/rotate\\((-?[\\d.]+)\\)/.exec(c.getAttribute('transform')), sp=Math.hypot(F.v[0], F.v[1]);
          if(m && sp>60){ var d=Math.abs(((+m[1]-Math.atan2(F.v[1], F.v[0])*180/Math.PI)%360+540)%360-180); off.push(d); if(d>12) big++; }
          n++; requestAnimationFrame(g); }
        else done({n:n, off:off.length, big:big, k:document.querySelector('#solar-fly-svg .fly-ship').getAttribute('transform'),
          w:document.querySelector('#solar-fly-svg .fly-ship').getBoundingClientRect().width}); })(); })""")
    assert f["n"] > 30 and f["off"] > 20 and f["big"] <= f["off"] * .05, f        # the nose on the way's tangent
    assert f["k"] == "scale(0.4)" and f["w"] < 40, f                               # small and clear
    pg.wait_for_timeout(300)
    o = pg.evaluate(r"""() => { var n=document.getElementById('node-u2-p1'), P=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0,
      c=[parseFloat(n.style.left), parseFloat(n.style.top)-P], d=window._altoSolarGeo().bodies['u2-p1'].d, a=window._altoCraft.parked('u2-p1', c);
      return {id:window._focusedNodeId, on:window._altoCraft.orbiting(), r:a && Math.hypot(a.p[0]-c[0], a.p[1]-c[1]), R:d/2, sp:a && Math.hypot(a.v[0], a.v[1])}; }""")
    assert o["id"] == "u2-p1" and o["on"] == "u2-p1", o
    assert o["R"] + 4 < o["r"] < o["R"] * 1.4 + 40 and 0 < o["sp"] < o["r"] * .6, o   # in a gentle orbit, clear of the body
    pg.evaluate("() => window._altoSolarStyle.set('real')"); pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close(); pytest.skip("no WebGL in this browser")
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(int(pg.evaluate("() => window._altoFlyMs")) + 1800)
    S = """() => { var s=window._altoSolar3D.ship(), g=window._altoSolarGeo().bodies['u1-p1']; return s && {on:s.on, al:s.al, d:Math.hypot(s.x-g.x, s.y-g.y), R:g.d/2, x:s.x, y:s.y,
      lock:window._altoSolar3D.closeup().lock}; }"""
    a = pg.evaluate(S); pg.wait_for_timeout(600); b = pg.evaluate(S)
    assert a and a["on"] and a["lock"] == "u1-p1" and a["d"] > a["R"] + 4 and abs(a["d"] - b["d"]) < 2, (a, b)   # round the globe, never in it
    assert 0.5 < math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < a["d"], (a, b)                                    # slowly round
    pg.keyboard.press("Escape"); pg.wait_for_timeout(1500)
    assert not pg.evaluate("() => window._altoCraft.orbiting()")
    pg.context.close()
    assert not errs, errs


def test_a_ship_picked_on_the_way_or_in_orbit_shows_at_once(browser, page):
    """Luke (2026-10-22): "Ship switching doesn't work" — since 1.9.144 the 3D ship stays on in its orbit between
    flights, so its model was read only once; a pick now shows at once: on the way in Classic and Retro, and round the
    enlarged body in Realistic 3D."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoCraft.set('explorer'); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('classic'); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    ART = "s => !!document.querySelector('#solar-fly-svg .fly-ship '+s)"
    pg.evaluate("() => window.enterFocus('u2-p1')"); pg.wait_for_timeout(400)
    assert pg.evaluate(ART, ".sh-ro") and pg.evaluate("() => !!window._altoSolarFlight()")
    pg.evaluate("() => window._altoCraft.set('halo')"); pg.wait_for_timeout(50)
    assert pg.evaluate(ART, 'circle.sh-hull[r="20"]')                                # Classic, on the way
    pg.wait_for_timeout(int(pg.evaluate("() => window._altoFlyMs")) + 400)
    pg.evaluate("() => window._altoSolarStyle.set('retro')"); pg.wait_for_timeout(400)
    pg.evaluate("() => window.enterFocus('u1-p1')"); pg.wait_for_timeout(400)
    pg.evaluate("() => window._altoCraft.set('explorer')"); pg.wait_for_timeout(50)
    assert pg.evaluate(ART, ".sh-ro")                                                # Retro, on the way
    pg.wait_for_timeout(int(pg.evaluate("() => window._altoFlyMs")) + 400)
    pg.evaluate("() => window._altoSolarStyle.set('real')"); pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close(); pytest.skip("no WebGL in this browser")
    pg.evaluate("() => window.enterFocus('u2-p1')")
    pg.wait_for_timeout(int(pg.evaluate("() => window._altoFlyMs")) + 1800)
    assert pg.evaluate("() => [window._altoCraft.orbiting(), window._altoSolar3D.ship().craft]") == ["u2-p1", "explorer"]
    pg.evaluate("() => window._altoCraft.set('halo')"); pg.wait_for_timeout(300)
    s = pg.evaluate("() => window._altoSolar3D.ship()")
    assert s["craft"] == "halo" and s["on"] and s["al"] > .9, s                      # Realistic 3D, in orbit
    pg.context.close()
    assert not errs, errs


FLIGHT = """() => new Promise(function(done){ var F=[], t0=performance.now(), seen=false;
  (function g(){ var f=window._altoSolarFlight(), c=document.querySelector('#solar-fly-svg .fly-craft'), m=document.querySelector('#solar-fly-svg .sh-fl[data-f=m]');
    if(f && c){ seen=true; var r=/rotate\\(([-\\d.e]+)\\)/.exec(c.getAttribute('transform')), s3=window._altoSolar3D && window._altoSolar3D.on() ? window._altoSolar3D.ship() : null;
      F.push({x:f.tau/f.D, b:f.thr.b, f:f.thr.f, rot:r ? +r[1]*Math.PI/180 : null, vh:Math.atan2(f.v[1], f.v[0]), fl:m ? +m.getAttribute('opacity') : 0, k:f.k, D:f.D,
        lift:s3 && s3.lift, nose:s3 && s3.nose, h3:s3 && s3.h, e3:s3 && s3.e}); }
    if((seen && !f) || performance.now()-t0>9000) done(F); else requestAnimationFrame(g); })(); })"""


def _wr(a):
    return math.atan2(math.sin(a), math.cos(a))


def test_the_rocket_brakes_tail_first_into_a_smooth_orbit(browser, page):
    """Luke (2026-10-25): "add a classic rocket ship design for the three star chart modes that have ship designs. And
    it should apply the brakes when approaching a planet like a normal rocket would." The Rocket in the picker, drawn in
    each style; on the way in it turns tail first (smoothly, never a snap), its engine's flame lit as it brakes, and
    turns nose first again as it settles into its orbit; in Realistic 3D the model does the same, flying in the plane
    (never lifted over the body it goes to); the flight at most 5 s on the screen."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoCraft.set('rocket'); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('classic'); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u1-p2')")
    F = [f for f in pg.evaluate(FLIGHT.replace("var F=[]", "var F=[], red=document.querySelectorAll('#solar-fly-svg .fly-ship .sh-red').length") .replace("done(F)", "done(F.concat([{red:red}]))")) if f.get("rot") is not None or "red" in f]
    assert F.pop()["red"] >= 3                                                                     # its red nose and fins
    assert len(F) > 30 and F[0]["D"] * F[0]["k"] <= 5.01, (len(F), F[:1])                   # at most 5 s on the screen
    braking = [f for f in F if f["b"] > .6 and f["f"] > .95]
    assert braking and all(abs(_wr(f["rot"] - f["vh"] - math.pi)) < .3 and f["fl"] > .5 for f in braking), braking[:3]   # tail first, burning
    end = [f for f in F if f["x"] > .985]
    assert end and all(abs(_wr(f["rot"] - f["vh"])) < .3 and f["fl"] < .05 for f in end), end[-3:]                   # nose first into its orbit
    assert max(abs(_wr(b["rot"] - a["rot"])) for a, b in zip(F, F[1:])) < 1.2, "the flip snapped"
    pg.wait_for_timeout(1200)
    pg.evaluate("() => window._altoSolarStyle.set('retro')"); pg.wait_for_timeout(300)
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#solar-fly-svg .fly-ship .sh-red')).fill") in ("rgb(12, 14, 18)", "#0c0e12")   # gold on black in Retro
    pg.evaluate("() => window._altoSolarStyle.set('real')"); pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close(); pytest.skip("no WebGL in this browser")
    pg.evaluate("() => window.enterFocus('u1-p1-m1')")
    F = [f for f in pg.evaluate(FLIGHT) if f["nose"] is not None]
    assert len(F) > 20, len(F)
    assert all(f["lift"] <= 3.01 for f in F if f["x"] > .7), [f["lift"] for f in F if f["x"] > .7][:20]           # in the plane on the way in
    flipped = [f for f in F if f["e3"]["f"] > .95]
    assert flipped and all(abs(_wr(f["nose"] - f["h3"] - math.pi)) < (1 - f["e3"]["f"]) * math.pi + .05 for f in flipped), flipped[:2]   # tail first,
    assert max(f["e3"]["m"] for f in flipped) > .9                                                                   # on its main engine
    pg.context.close()
    assert not errs, errs


TRAVEL = """() => new Promise(function(done){ var F=[], t0=performance.now(), seen=false;
  (function g(){ var f=window._altoSolarFlight(), c=document.querySelector('#solar-fly-svg .fly-craft'), pr=document.querySelector('#solar-fly-svg .fly-ship'),
      w=document.querySelector('#solar-fly-svg .fly-warp'), t=document.querySelector('#solar-fly-svg .fly-trail'), p=document.querySelector('#solar-fly-svg .fly-path'),
      fl=[].map.call(document.querySelectorAll('#solar-fly-svg .fly-flash'), function(e){ return +e.getAttribute('opacity'); });
    if(f && c){ seen=true; var sc=/scale\\(([\\d.]+) ([\\d.]+)\\)/.exec(pr.getAttribute('transform')||''), s3=window._altoSolar3D && window._altoSolar3D.on() ? window._altoSolar3D.ship() : null;
      F.push({x:f.x, mode:f.mode, S:f.S, u:f.tau/f.D, fx:f.fx, op:c.getAttribute('opacity'), sx:sc ? +sc[1] : 0, sy:sc ? +sc[2] : 0, wd:(w && w.getAttribute('d'))||'',
        trail:(t && t.getAttribute('d'))||'', path:p ? getComputedStyle(p).display : '', fl:fl, vis3:s3 && s3.vis, warp3:s3 && s3.warp}); }
    if((seen && !f) || performance.now()-t0>9000) done(F); else requestAnimationFrame(g); })(); })"""


def test_the_explorer_warps_between_systems_and_flies_on_impulse_within_one(browser, page):
    """Luke (2026-10-25): "the enterprise-based ship, it should be able to go to warp speed between units or solar
    systems. But it goes at impulse speed inside a single star system." Within a system: the ordinary course (impulse,
    braking into its orbit). Between systems: off on impulse, the warp — most of the way in a moment, the craft
    stretched, the stars streaking past — a flash as it drops out, then on impulse into its orbit; about 3 s. And
    (Luke, 2026-10-28) "a little bit of start to the animation before a jump or a warp speed jump, so it doesn't just
    look like a glitch": first a wind-up with the craft where it is — its engines spooling up, a faint glow, a light
    stretch, a beat's pause — about 1 s more."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoCraft.set('explorer'); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('classic'); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u1-p2')")
    F = pg.evaluate(TRAVEL)
    assert F and all(f["mode"] is None for f in F), F[:2]                                     # impulse within a system
    pg.wait_for_timeout(1000)
    pg.evaluate("() => window.enterFocus('u2-p1')")
    F = pg.evaluate(TRAVEL)
    assert F and F[0]["mode"] == "warp" and F[0]["S"] <= 4.01, F[:1]                      # (3 s of warp + 1 s of wind-up)
    warp = [f for f in F if f["fx"]["warp"] > .9]
    assert warp and all(f["wd"] and f["sx"] > f["sy"] * 1.8 for f in warp), warp[:2]       # stretched, the stars streaking
    wind = [f for f in F if f["x"] < .2]                                                    # the wind-up: still where it is
    assert wind and max(f["u"] for f in wind) < .01 and all(f["op"] in (None, "1") for f in wind), wind[:2]
    assert max(f["fx"]["wu"] for f in wind) > .8 and max(f["fx"]["ws"] for f in wind) > .2 and max(f["fl"][2] for f in wind) > .15    # engines up, a light stretch, a glow
    assert max(f["sx"] for f in wind) > 1.1 * min(f["sx"] for f in wind) and not any(f["wd"] for f in wind)              # (stretched a little, no streaks yet)
    assert max(f["u"] for f in F if f["x"] < .6) > .85                                      # most of the way in a moment
    assert max(f["fl"][0] for f in F if .5 < f["x"] < .66) > .5                             # the flash as it drops out
    assert all(not f["wd"] and abs(f["sx"] - f["sy"]) < .01 for f in F if f["x"] > .72), "impulse into its orbit"
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => window._altoCraft.orbiting()") == "u2-p1"
    pg.context.close()
    assert not errs, errs


def test_the_halo_jumps_in_a_flash_of_light(browser, page):
    """Luke (2026-10-25): "the Halo ship, try to make that travel like a ship in Foundation would, how it just sort of
    pops out at the location ... goes into a flash of light and comes out of a flash of light." A flash where it is and
    it is gone (no trail, no course drawn), a flash where it comes out and it is there easing into its orbit; in Retro
    too, and in Realistic 3D. Only between systems (Luke, 2026-10-28: "warp speed and ship jumping happens only when
    you're going between solar systems, not within solar systems": inside one it flies as it is, no braking burn), and
    after a wind-up: a glow growing round it, then light gathering in on it in a flash."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoCraft.set('halo'); window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('classic'); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u1-p2')")                                          # within a system: no jump, no flash, no braking burn
    F = pg.evaluate(TRAVEL)
    assert F and all(f["mode"] is None and max(f["fl"]) < .01 and f["path"] != "none" for f in F), F[:2]
    pg.wait_for_timeout(1000)
    for sty, to in (("classic", "u2-p1"), ("retro", "u1-p2")):
        pg.evaluate("s => window._altoSolarStyle.set(s)", sty); pg.wait_for_timeout(300)
        pg.evaluate("i => window.enterFocus(i)", to)
        F = pg.evaluate(TRAVEL)
        assert F and F[0]["mode"] == "jump" and F[0]["S"] <= 2.51 and all(f["path"] == "none" for f in F), (sty, F[:1])
        wind = [f for f in F if f["x"] < .39]                                                  # the wind-up: where it is, a glow gathering in
        assert wind and max(f["u"] for f in wind) < .01 and all(f["op"] == "1" for f in wind), (sty, wind[:2])
        assert max(f["fl"][2] for f in wind) > .6 and max(f["fx"]["gr"] for f in wind) > 60 and min(f["fx"]["gr"] for f in wind if f["fl"][2] > .5) < 40, sty
        gone = [f for f in F if .62 < f["x"] < .78]
        assert gone and all(f["op"] == "0" and f["trail"].count("L") == 0 for f in gone), (sty, gone[:2])   # no transit seen
        assert max(f["fl"][0] for f in F if .4 < f["x"] < .56) > .6 and max(f["fl"][1] for f in F if f["x"] > .85) > .6, sty   # out in a flash, in in a flash
        assert all(f["op"] == "1" for f in F if f["x"] > .97), sty                                                       # there, into its orbit
        pg.wait_for_timeout(900)
        assert pg.evaluate("() => window._altoCraft.orbiting()") == to, sty
    pg.evaluate("() => window._altoSolarStyle.set('real')"); pg.wait_for_timeout(2500)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close(); pytest.skip("no WebGL in this browser")
    pg.evaluate("() => window.enterFocus('u2-p1')")
    F = [f for f in pg.evaluate(TRAVEL) if f["vis3"] is not None]
    assert F and min(f["vis3"] for f in F if .62 < f["x"] < .78) < .01 and max(f["vis3"] for f in F if f["x"] > .97) > .99, F[:3]
    pg.context.close()
    assert not errs, errs


def test_a_long_flight_is_at_most_five_seconds_and_enter_lands_it(browser, page):
    """Luke (2026-10-22): "sometimes map is stuck" — a flight to another system took 7-9 s; now at most 5 s on the
    screen (its clock quicker on a long way), and Enter or a click on empty space lands it in about half a second."""
    pg, errs = _open(browser, page, wait=1400)
    pg.evaluate("() => { window._altoFlyOff=false; window._altoSolarLook.set('stars'); window._altoSolarStyle.set('retro'); window.enterFocus('u1-p1'); }")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.enterFocus('u2-p1')"); pg.wait_for_timeout(100)
    f = pg.evaluate("() => [window._altoSolarFlight(), window._altoFlyMs]")
    assert f[0] and f[0]["to"] == "u2-p1" and f[0]["D"] * f[0]["k"] <= 5.001 and f[1] <= 5000 + 600, f
    pg.wait_for_timeout(400); pg.keyboard.press("Enter"); t = pg.evaluate("() => performance.now()")
    pg.wait_for_function("() => !window._altoSolarFlight()", timeout=3000)
    assert pg.evaluate("t => performance.now()-t", t) < 1200
    assert pg.evaluate("() => [window._focusedNodeId, window._altoSolarFlight(true).how]") == ["u2-p1", "landed"]
    pg.context.close()
    assert not errs, errs


def test_the_chips_x_never_sits_on_the_first_label_at_820px_in_any_style(browser, page):
    """PARKED.md (2026-10-28): in the System star chart at an 820px window the little x that winds the chips in
    overlapped the first row label (Retro's wider labels move the row without resizing the bar, and the x was only
    placed on load, on a resize and when the bar resized). It now follows a style switch: in all four styles its right
    edge stays clear of the row's first label."""
    pg, errs = _open(browser, page, wait=1400)
    pg.set_viewport_size({"width": 820, "height": 700}); pg.wait_for_timeout(800)
    for look, sty in (("hub", "classic"), ("stars", "classic"), ("stars", "retro"), ("stars", "real"), ("hub", "classic")):
        pg.evaluate("([l, s]) => { window._altoSolarLook.set(l); window._altoSolarStyle.set(s); }", [look, sty]); pg.wait_for_timeout(1500)
        pg.evaluate("() => window.enterFocus('u1-p1')"); pg.wait_for_timeout(1400)
        g = pg.evaluate("""() => { var b=document.getElementById('ct-chips').getBoundingClientRect(), nav=document.getElementById('nav'),
          f=[].filter.call(nav.querySelectorAll('button,.nav-group-label'), function(e){ return e.offsetWidth; })[0].getBoundingClientRect();
          return {x:[b.left, b.right], first:[f.left, f.right]}; }""")
        assert 6 <= g["first"][0] - g["x"][1] <= 11, (look, sty, g)       # clear of it, 8 px before it (Art: about 8 px in every style)
        pg.evaluate("() => window.exitFocus && window.exitFocus()"); pg.wait_for_timeout(500)
    pg.context.close()
    assert not errs, errs
