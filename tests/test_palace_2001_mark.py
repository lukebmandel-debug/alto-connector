"""2.0.1 content buildings made obvious in first-person (alto/build/palace_ride_mark.py): place labels, beams, signs, Nearby panel, mini-map.

Source assertions always run. The runtime checks reuse the 1.9.100 FPV test's synthetic city (two node buildings with doors, a landmark with a page) in WebKit and
Chromium (skipped without Playwright). Nothing here touches the network or any ALTO_* setting.
"""
import math
import os
import sys

import pytest

from alto.build import palace_ride, palace_ride_door, palace_ride_e, palace_ride_mark as mk

sys.path.insert(0, os.path.dirname(__file__))
import test_palace_2000_fpv as F  # noqa: E402  (the synthetic city and its page stub)

J = mk.JS_MARK


# ───────────────────────────── source contract ─────────────────────────────
def test_the_mark_part_is_spliced_into_roam_with_fenced_glue():
    assert J in palace_ride.RIDE_JS and "/*@MARK@*/" not in palace_ride.RIDE_JS and mk.CSS_MARK in palace_ride.RIDE_CSS
    e = palace_ride_e._JS_E
    for glue in ("markHud(h);", "markKey(e)) return;", "markSteer(dt); tick(dt,false);", "markDraw(ctx);", "markReset();", "marks:MARKAPI,"):
        assert glue in e
    assert e.count("/*@MARK-glue@*/") >= 5
    assert "if(mem.page) mkOpenPage(mem.page); else window.showDetail('node', mem.id);" in palace_ride_door.JS_DOORS


def test_untrusted_names_only_ever_reach_text():
    # labels, list, plaque and banner: textContent / fillText; innerHTML only for fixed markup
    assert ".textContent=" in J and "fillText(" in J
    for line in J.splitlines():
        if "innerHTML" in line:
            assert not any(v in line for v in ("it.name", "it.num", "E.name", "E.title", "l.n", "mkPageName"))
    assert "function mkCol(c)" in J                                        # colours are checked before they reach a style


def test_quiet_and_cheap():
    css = mk.CSS_MARK
    for gamey in ("@keyframes", "infinite", "bounce", "pulse"):
        assert gamey not in css and gamey not in J
    assert "prefers-reduced-motion" in css and "reduced()" in J
    assert "will-change:transform,opacity" in css and "translate3d(" in J     # moved by transform, one layer
    assert "window.addEventListener" not in J and "document.addEventListener" not in J     # no new global listeners: keys come through roam's capture
    assert "localStorage" in J and "try{" in J


# ───────────────────────────── runtime ─────────────────────────────
pw = F.pw
page = F.page
roam = F.roam

LAYOUT = "([c,W,H,m]) => window._palRide.roam.marks.layout(c,W,H,m)"


def test_layout_takes_the_best_first_and_never_overlaps(roam):
    pg = roam
    c = [{"id": "a%d" % i, "sx": 700 + (i % 3) * 4, "sy": 500, "w": 160, "h": 26, "pri": i} for i in range(12)]
    out = pg.evaluate(LAYOUT, [c, 1400, 900, 8])
    assert out[0]["id"] == "a0"                                                  # the best is placed first, where it wants to be
    ids = [o["id"] for o in out]
    assert ids == sorted(ids, key=lambda s: int(s[1:]))                          # by priority
    assert len(out) <= 3                                                         # one place and two rows above it: the rest wait
    rs = [(o["x"], o["y"], o["x"] + 160, o["y"] + 26) for o in out]
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
    spread = [{"id": "s%d" % i, "sx": 100 + i * 150, "sy": 500, "w": 120, "h": 26, "pri": i} for i in range(10)]
    assert len(pg.evaluate(LAYOUT, [spread, 1400, 900, 8])) == 8                 # at most eight
    off = [{"id": "o", "sx": -500, "sy": 500, "w": 120, "h": 26, "pri": 0}, {"id": "t", "sx": 700, "sy": 30, "w": 120, "h": 26, "pri": 1}]
    assert pg.evaluate(LAYOUT, [off, 1400, 900, 8]) == []                       # off screen / under the HUD's top band: none


def test_priority_and_fade_rules(roam):
    pg = roam
    r = pg.evaluate("""() => { var M=window._palRide.roam.marks;
      return {near:M.pri(100,0,false,false), side:M.pri(100,.9,false,false), far:M.pri(300,0,false,false), tgt:M.pri(390,.9,true,false), shown:M.pri(100,0,false,true),
        w0:M.want(100,0), w250:M.want(250,0), w325:M.want(325,0), w400:M.want(400,0), occFar:M.want(100,120), occNear:M.want(100,10)}; }""")
    assert r["near"] < r["side"] < r["far"] and r["tgt"] < r["near"] and r["shown"] < r["near"]
    assert r["w0"] == 1 and r["w250"] == 1 and 0 < r["w325"] < 1 and r["w400"] == 0             # full to 250 m, a smooth fade to nothing at 400 m
    assert r["occFar"] == pytest.approx(.4) and r["occNear"] == 0                                 # hidden behind a far building: dimmed; right behind a near one: faded out


def _stand(pg, dx, yaw, door=F.DOOR1):
    F.stand(pg, dx, yaw, door=door)
    pg.evaluate("() => { var R=window._palRide.roam; for(var i=0;i<40;i++) R.draw(); }")


def test_content_buildings_are_known_and_labelled(roam):
    pg = roam
    _stand(pg, 60, math.pi)
    L = pg.evaluate("() => window._palRide.roam.marks.list()")
    ids = {q["id"]: q for q in L}
    assert {"n1", "n2"} <= set(ids) and ids["n1"]["door"] and ids["n1"]["k"] == "n"
    lms = [q for q in L if q["k"] == "l"]
    assert lms and all(q["page"] for q in lms)                                    # landmarks count only with a page
    st = pg.evaluate("() => window._palRide.roam.marks.state()")
    assert any(l["id"] == "n1" and l["a"] > .5 for l in st["labels"])
    lab = pg.evaluate("""() => { var l=[].slice.call(document.querySelectorAll('#pal-ride .mk-lab')).filter(function(e){ return +e.style.opacity>.3; })[0];
      return l && {name:l.querySelector('.mk-nm').textContent, no:l.querySelector('.mk-no').textContent, tr:l.style.transform, hidden:l.closest('.mk-layer').getAttribute('aria-hidden')}; }""")
    assert lab["no"] + " " + lab["name"] == F.NAMES["n1"] and lab["no"] == "1.1" and "translate3d" in lab["tr"] and lab["hidden"] == "true"


def test_n_cycles_and_turns_g_walks_any_move_key_stops(roam):
    pg = roam
    _stand(pg, 60, 0.0)                                                           # facing away from both
    pg.keyboard.press("n")
    st = pg.evaluate("() => window._palRide.roam.marks.state()")
    first = st["tgt"]
    assert first in ("n1", "n2") and st["turn"] and "of 2" in st["said"]
    assert pg.evaluate("() => document.querySelector('#pal-ride .mk-live').getAttribute('aria-live')") == "polite"
    pg.evaluate("() => { var M=window._palRide.roam.marks; for(var i=0;i<60;i++) M.steer(1/60); }")
    yaw = pg.evaluate("() => window._palRide.roam.state().yaw")
    it = [q for q in pg.evaluate("() => window._palRide.roam.marks.list()") if q["id"] == first][0]
    s = pg.evaluate("() => window._palRide.roam.state()")
    want = math.atan2(it["y"] - s["y"], it["x"] - s["x"])
    assert abs(math.remainder(yaw - want, 2 * math.pi)) < .05                     # turned toward it
    pg.keyboard.press("n")
    assert pg.evaluate("() => window._palRide.roam.marks.state().tgt") != first   # the next one
    pg.keyboard.press("g")
    assert pg.evaluate("() => window._palRide.roam.marks.state().auto")
    pg.keyboard.press("w")
    assert not pg.evaluate("() => window._palRide.roam.marks.state().auto")       # a move key takes over
    assert pg.evaluate("() => window.__keys.filter(function(k){ return k==='n'||k==='g'||k==='m'; }).length") == 0      # swallowed by roam, never the page's


def test_walk_reaches_the_door(roam):
    pg = roam
    _stand(pg, 40, 0.0)
    pg.evaluate("() => window._palRide.roam.marks.aim('n1')")
    pg.evaluate("() => window._palRide.roam.marks.walk()")
    r = pg.evaluate("""() => { var R=window._palRide.roam, M=R.marks; for(var i=0;i<60*20 && M.state().auto;i++){ M.steer(1/60); R.tick(1/60,null,false,true); } return {auto:M.state().auto, said:M.state().said}; }""")
    assert not r["auto"] and r["said"].startswith("At ")
    s = pg.evaluate("() => window._palRide.roam.state()")
    assert math.hypot(s["x"] - (F.DOOR1[0] + 3 * 1.3), s["y"] - F.DOOR1[1]) < 4


def test_mini_map_and_panel_toggle_and_remember(roam):
    pg = roam
    _stand(pg, 60, math.pi)
    m0 = pg.evaluate("() => window._palRide.roam.marks.state().map")
    pg.keyboard.press("m")
    r = pg.evaluate("""() => ({map:window._palRide.roam.marks.state().map, ls:(function(){ try{ return localStorage.getItem('alto-palace-fpv-map'); }catch(x){ return 'blocked'; } })(), on:document.querySelector('#pal-ride .mk-map').classList.contains('on'),
      pressed:document.querySelector('#pal-ride .mk-mb').getAttribute('aria-pressed')})""")
    assert r["map"] != m0 and r["ls"] in ("1" if r["map"] else "0", "blocked") and r["on"] == r["map"] and r["pressed"] == ("true" if r["map"] else "false")
    pg.keyboard.press("m")
    pg.evaluate("() => window._palRide.roam.marks.toggleNear(false)")
    r = pg.evaluate("""() => ({ls:(function(){ try{ return localStorage.getItem('alto-palace-fpv-near'); }catch(x){ return '0'; } })(), exp:document.querySelector('#pal-ride .mk-tg').getAttribute('aria-expanded'), hid:document.querySelector('#pal-ride .mk-ol').hidden})""")
    assert r == {"ls": "0", "exp": "false", "hid": True}
    pg.evaluate("() => window._palRide.roam.marks.toggleNear(true)")
    # the list: real buttons with spoken labels, a click aims
    b = pg.evaluate("""() => { var b=[].slice.call(document.querySelectorAll('#pal-ride .mk-it')).filter(function(x){ return !x.parentNode.hidden; }); return b.map(function(x){ return x.getAttribute('aria-label'); }); }""")
    assert b and all("metres" in x for x in b)
    pg.click("#pal-ride .mk-it >> nth=0")
    assert pg.evaluate("() => window._palRide.roam.marks.state().tgt")


def test_no_leaks_across_entries(roam):
    pg = roam
    for i in range(3):
        _stand(pg, 60, math.pi)
        pg.evaluate("() => window._palRide.roam.exit(false)")
    _stand(pg, 60, math.pi)
    r = pg.evaluate("""() => ({labs:document.querySelectorAll('#pal-ride .mk-lab').length, layers:document.querySelectorAll('#pal-ride .mk-layer').length,
      panels:document.querySelectorAll('#pal-ride .mk-near').length, maps:document.querySelectorAll('#pal-ride .mk-map').length, pool:window._palRide.roam.marks.state().pool})""")
    assert r["labs"] == r["pool"] == 12 and r["layers"] == r["panels"] == r["maps"] == 1
    pg.evaluate("() => window._palRide.roam.exit(false)")
    assert pg.evaluate("() => window._palRide.roam.marks.state()")["labels"] == []


def test_reduced_motion_turns_snap(roam):
    pg = roam
    pg.emulate_media(reduced_motion="reduce")
    _stand(pg, 60, 0.0)
    pg.keyboard.press("n")
    st = pg.evaluate("() => window._palRide.roam.marks.state()")
    assert not st["turn"]                                                          # no scripted turn: already facing it
    it = [q for q in pg.evaluate("() => window._palRide.roam.marks.list()") if q["id"] == st["tgt"]][0]
    s = pg.evaluate("() => window._palRide.roam.state()")
    assert abs(math.remainder(s["yaw"] - math.atan2(it["y"] - s["y"], it["x"] - s["x"]), 2 * math.pi)) < 1e-6


def test_typing_on_the_page_is_untouched_after_leaving(roam):
    pg = roam
    _stand(pg, 60, math.pi)
    pg.evaluate("() => window._palRide.roam.exit(false)")
    pg.keyboard.press("n"); pg.keyboard.press("m"); pg.keyboard.press("g")
    assert pg.evaluate("() => window.__keys.slice(-3)") == ["n", "m", "g"]
