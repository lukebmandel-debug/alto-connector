"""System, decluttered (Luke, 2026-10-25, of Torts in Retro focused on Duty: "still very, very busy and kind of hard to
understand what's going on"; of 3D Star chart: "some of the buttons like reset or spokes only doesn't really seem to change
anything"; of Retro: "some of the elements that change when you hover on them are too quick to change").

- the pills naming where each way goes sit clear of the enlarged disc, of the bodies, of each other and of the bars, in
  every style; two long names that start alike read differently (never "Duties Arising fr…" twice);
- Reset view is in the bar only in 3D Star chart, and only once the view has been turned by hand;
- Spokes only says what it changed, and a body its arrow names shows no second name;
- a hover settles: a pointer passing over a body changes nothing, one resting on it lights it, and leaving lets go after
  a short grace.

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import sys
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401

MOONS = ["Affirmative Acts: Misfeasance and Nonfeasance", "Duties Arising from Undertakings", "Liable", "Not Liable",
         "Duties Arising from Special Relationships"]


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    doc = solar_doc([[[0, 0, 0, 0, 0], [0], [0]], [[0], [0]]], "orbit")
    for n in doc["nodes"]:
        if n["id"].startswith("u1-p1-m"):
            n["title"] = MOONS[int(n["id"][-1]) - 1]
    html, _ = build_timeline(*load_brief(copy.deepcopy(doc)))
    f = tmp_path_factory.mktemp("declutter") / "dc.html"
    f.write_text(html, encoding="utf-8")
    return f


PILLS = r"""() => {
  var R=e=>{var r=e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]}, ov=(a,b)=>a[0]<b[2]-1&&b[0]<a[2]-1&&a[1]<b[3]-1&&b[1]<a[3]-1,
    d=document.querySelector('#node-'+window._focusedNodeId+' .node-card').getBoundingClientRect(), cx=d.left+d.width/2, cy=d.top+d.height/2,
    tb=document.getElementById('sol-tour').getBoundingClientRect(), ctl=document.getElementById('sol-ctl').getBoundingClientRect(),
    ps=[].filter.call(document.querySelectorAll('#sol-nav .sol-nh'), p=>!p.hidden && p.getBoundingClientRect().width);
  return {n:ps.length, top:tb.top, ctl:ctl.top, r:d.width/2, pills:ps.map(p=>{ var q=R(p), X=Math.max(q[0], Math.min(q[2], cx)), Y=Math.max(q[1], Math.min(q[3], cy));
    return {id:p.dataset.id, txt:p.querySelector('b').textContent, box:q, disc:Math.hypot(X-cx, Y-cy)-d.width/2,
      bodies:[].filter.call(document.querySelectorAll('#world .node[data-solar]:not(.focused) .node-card'), c=>{ var b=R(c); return b[2]-b[0]>4 && ov(b, q); }).length}; }),
    overlaps:ps.some((p,i)=>ps.some((o,j)=>j>i && ov(R(p), R(o))))};
}"""


def _focus(pg, style, at="u1-p1"):
    pg.evaluate("a => { window._altoSolarStyles.set(a[0]); window._altoSolarLock.set(false); window.enterFocus(a[1]); }", [style, at])
    pg.wait_for_timeout(2600)
    pg.mouse.move(700, 130)
    pg.wait_for_timeout(400)


@pytest.mark.parametrize("style", ["system", "chart", "retro"])
def test_the_pills_never_cover_anything(browser, page, style):
    pg, errs = _open(browser, page)
    _focus(pg, style)
    h = pg.evaluate(PILLS)
    pg.context.close()
    assert not errs, errs
    assert h["n"] >= 5 and not h["overlaps"], h
    for p in h["pills"]:
        assert p["disc"] > 0 and p["bodies"] == 0, p                 # off the enlarged disc, off every body
        assert p["box"][3] <= h["top"] + 1 and p["box"][1] >= 60, p     # above the Tour bar, under the chips
    txt = [p["txt"] for p in h["pills"]]
    assert len(set(txt)) == len(txt), txt                               # no two read the same
    assert not any(t.endswith("…") and txt.count(t) > 1 for t in txt), txt


def test_reset_view_only_when_there_is_a_view_to_reset(browser, page):
    pg, errs = _open(browser, page)
    shown = "() => { var b=document.getElementById('sk3d-reset'); return !!b && !b.hidden && b.getBoundingClientRect().width>0; }"
    for st in ("system", "chart", "retro"):
        _focus(pg, st)
        pg.wait_for_timeout(700)
        assert not pg.evaluate(shown), st
    pg.evaluate("() => { window._altoSolarStyles.set('3d'); window.exitFocus && window.exitFocus(); }")
    pg.wait_for_timeout(1800)
    if not pg.evaluate("() => !!(window._altoSolar3D && window._altoSolar3D.on())"):
        pg.context.close()
        pytest.skip("no WebGL here")
    assert not pg.evaluate(shown)                                        # nothing turned yet: nothing to reset
    pg.mouse.move(300, 600)
    pg.mouse.down()
    pg.mouse.move(480, 520, steps=8)
    pg.mouse.up()
    pg.wait_for_timeout(900)
    assert pg.evaluate(shown)
    pg.click("#sk3d-reset")
    pg.wait_for_timeout(900)
    assert not pg.evaluate(shown)
    pg.evaluate("() => window._altoSolarLock.set(true)")                  # Spokes only: no free camera, so no reset
    pg.mouse.move(300, 600)
    pg.mouse.down()
    pg.mouse.move(480, 520, steps=8)
    pg.mouse.up()
    pg.wait_for_timeout(900)
    assert not pg.evaluate(shown)
    pg.context.close()
    assert not errs, errs


def test_spokes_only_says_what_it_changed_and_names_once(browser, page):
    pg, errs = _open(browser, page)
    _focus(pg, "retro")
    pg.click("#sol-lock")
    pg.wait_for_timeout(1800)
    h = pg.evaluate(r"""() => { var n=document.getElementById('sol-note');
      return {lock:window._altoSolarLock.get(), note:n && n.classList.contains('on') ? n.textContent : '',
        twice:[].filter.call(document.querySelectorAll('#sol-arw .sol-al'), l=>{ var b=document.querySelector('#node-'+l.dataset.id+'>.sol-lbl');
          return b && +getComputedStyle(b).opacity>0; }).map(l=>l.dataset.id)}; }""")
    pg.context.close()
    assert not errs, errs
    assert h["lock"] and "Spokes only" in h["note"] and not h["twice"], h


def test_a_hover_settles(browser, page):
    pg, errs = _open(browser, page)
    _focus(pg, "retro", "u2")
    pg.evaluate("() => { window.exitFocus && window.exitFocus(); window._altoSolarMotion.set(false); }")   # (still bodies: the hover alone)
    pg.wait_for_timeout(1500)
    got = pg.evaluate("""() => { var hit=null; [].some.call(document.querySelectorAll('#world .node[data-solar]:not(.focused) .node-card'), function(c){
        var r=c.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2, e=x>200 && x<1300 && y>200 && y<700 && r.width>12 && document.elementFromPoint(x, y);
        if(e && e.closest('.node')===c.closest('.node')) hit=[x, y, c.closest('.node').id]; return !!hit; }); return hit; }""")
    assert got, "no body in view"
    box, nid = got[:2], got[2]
    lit = "() => document.getElementById('%s').classList.contains('sol-hov')" % nid
    pg.mouse.move(box[0] - 120, box[1] - 120)
    pg.wait_for_timeout(300)
    pg.mouse.move(box[0], box[1], steps=3)                                  # passing over it...
    pg.wait_for_timeout(60)
    pg.mouse.move(box[0] + 140, box[1] + 140, steps=3)                      # ...and on: nothing changed
    pg.wait_for_timeout(350)
    assert not pg.evaluate(lit)
    pg.mouse.move(box[0], box[1], steps=3)                                  # resting on it: it lights
    pg.wait_for_timeout(90)
    assert not pg.evaluate(lit)
    pg.wait_for_timeout(300)
    assert pg.evaluate(lit)
    pg.mouse.move(box[0] + 140, box[1] + 140, steps=2)                      # leaving: a short grace, then it lets go
    pg.wait_for_timeout(40)
    assert pg.evaluate(lit)
    pg.wait_for_timeout(400)
    assert not pg.evaluate(lit)
    pg.context.close()
    assert not errs, errs
