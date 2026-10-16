"""Going round a horizontal timeline (lanes_nav.py): step event to event.

Every way of moving — the wheel, a trackpad, a touch swipe, ← / →, Space — moves
one stop along the main line in page order, with the camera on the engine's own
glide; a burst never skips or jams; the camera comes to rest exactly, clear of
the rail; the whole timeline fits the window and a click there comes back down;
a character in the key restricts the steps to its events; reduced motion jumps;
phones are left to the engine's card view.

The browser tests are skipped without Playwright's browsers.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import lanes, lanes_nav  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402

LANES = ROOT / "samples" / "lanes_brief.json"
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def _build(path=LANES):
    html, _ = build_timeline(*load_brief(json.loads(Path(path).read_text(encoding="utf-8"))))
    return html


# ── what the page carries ───────────────────────────────────────────────────

def test_the_nav_rides_with_the_lanes_script_only():
    assert lanes_nav.NAV_JS in lanes.LANES_JS and lanes_nav.NAV_CSS in lanes.LANES_CSS
    html = _build()
    assert "window._altoLanesStep=function" in html
    other = build_timeline(*load_brief(json.loads((ROOT / "samples" / "contracts_brief.json").read_text())))[0]
    assert "window._altoLanesStep" not in other


def test_the_old_free_scroll_and_slide_are_gone():
    js = lanes.LANES_JS
    assert "function _slideTo" not in js and "_tp=e.timeStamp" not in js
    # the wheel is held on the canvas only (Safari keeps scrolling everything else off the main thread),
    # and the one document-level wheel listener left is edit mode's free scroll
    assert "c.addEventListener('wheel', onWheel, {passive:false})" in js
    doc = js.split("document.addEventListener('wheel'")
    assert len(doc) == 2 and "de.classList.contains('alto-editing')" in doc[1].split("}, {passive:false});")[0]


def test_steps_glide_on_the_engines_curve_and_scroll_axis():
    p = next(x for x in PATCHES if x["name"] == "lanes-share-the-glide")
    assert "window._altoEase=_altoEase; window._altoScrollAxis=_scrollAxis;" in p["new"]
    html = _build()
    assert html.count("window._altoEase=_altoEase; window._altoScrollAxis=_scrollAxis;") == 1
    js = lanes_nav.NAV_JS
    assert "if(window._altoEase) return window._altoEase(p);" in js
    assert "if(window._altoScrollAxis) return window._altoScrollAxis(prop);" in js
    glide = js.split("function glideTo(", 1)[1].split("\nfunction ", 1)[0]
    assert "qx.go(" in glide and "qy.go(" in glide and not re.search(r"\.scroll(Left|Top)\s*=", glide)


def test_reduced_motion_jumps():
    js = lanes_nav.NAV_JS
    assert "matchMedia('(prefers-reduced-motion: reduce)')" in js
    assert "if(opt.instant || reduced() || d<0.5){ qx.go(tl); qy.go(tt); finish(); return; }" in js
    assert "if(reduced()){ ovSet(to);" in js


def test_steps_queue_like_the_engines_hops():
    js = lanes_nav.NAV_JS
    assert "QMAX=3" in js and "if(_busy){ if(repeat ? !_q.length : _q.length<QMAX) _q.push([dir,src]); return; }" in js


def test_phones_are_left_to_the_engine():
    js, css = lanes_nav.NAV_JS, lanes_nav.NAV_CSS
    head = js.split("var NOTCH=", 1)[0]
    assert "if(de.classList.contains('mobile')) return;" in head
    assert "html.mobile #lanes-nav" in css and "html.alto-editing #lanes-nav" in css


def test_the_kept_line_is_readable_for_character_focus():
    assert "window._altoLanesLock=function(id)" in lanes.LANES_JS


# ── in a browser ────────────────────────────────────────────────────────────

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:                                    # no bundled Chromium: the installed Chrome will do
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page_file(tmp_path_factory):
    f = tmp_path_factory.mktemp("lanesnav") / "page.html"
    f.write_text(_build(), encoding="utf-8")
    return f


def _desk(browser, f, **kw):
    ctx = browser.new_context(viewport={"width": 1500, "height": 900}, **kw)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1500)
    return pg, errs


STOPS = """() => { const o=[].concat.apply([],ACT_SEQS), L=_ALTO_LANES;
  const lg=!(L.flashbacks||[]).length && !Object.values(L.ev).some(e=>(e.present||[]).length);
  return o.filter(id=>L.ev[id] && (lg || (L.ev[id].l||'main')==='main')); }"""
CUR = "window._altoLanesCurrent()"
# wheel events [delay ms, dx, dy, mode] dispatched on the board at real times
WHEEL = """(evs) => new Promise(res => { const t=document.getElementById('world'); let i=0;
  function go(){ const e=evs[i++]; t.dispatchEvent(new WheelEvent('wheel',{deltaX:e[1],deltaY:e[2],deltaMode:e[3]||0,bubbles:true,cancelable:true}));
    if(i<evs.length) setTimeout(go, evs[i][0]); else setTimeout(res, 60); }
  setTimeout(go, evs[0][0]); })"""
TRACK = """() => { window._seen=[]; (function f(){ const c=window._altoLanesCurrent(); if(window._seen[window._seen.length-1]!==c) window._seen.push(c);
  window._trk=requestAnimationFrame(f); })(); }"""


def _inertia(sign=1):
    ev = [[10, 0, 2 * sign]] + [[16, 0, v * sign] for v in (6, 14, 30, 48, 60, 64, 60)]
    v = 58.0
    while v > 0.6:
        ev.append([16, 0, round(v * sign, 2)])
        v *= 0.955
    return ev


def test_the_wheel_steps_once_per_notch_and_once_per_trackpad_flick(browser, page_file):
    pg, errs = _desk(browser, page_file)
    S = pg.evaluate(STOPS)
    i0 = S.index(pg.evaluate(CUR))
    pg.evaluate(WHEEL, [[10, 0, 100]] + [[300, 0, 100]] * 3)                   # four mouse notches
    pg.wait_for_timeout(3200)
    i1 = S.index(pg.evaluate(CUR))
    assert i1 - i0 == 4
    pg.evaluate(WHEEL, [[10, 0, -4.000244140625]] + [[260, 0, -4.000244140625]])  # Safari's small notches, back
    pg.wait_for_timeout(2200)
    i2 = S.index(pg.evaluate(CUR))
    assert i2 - i1 == -2
    pg.evaluate(WHEEL, _inertia())                                            # a flick and its 1.4s inertia tail
    pg.wait_for_timeout(1400)
    i3 = S.index(pg.evaluate(CUR))
    assert i3 - i2 == 1
    pg.evaluate(WHEEL, [[10, 0, 1], [16, 0, 2], [16, 0, 1]])                  # a brush of the trackpad
    pg.wait_for_timeout(700)
    assert S.index(pg.evaluate(CUR)) == i3
    assert not errs


def test_a_real_wheel_never_free_scrolls(browser, page_file):
    pg, errs = _desk(browser, page_file)
    pg.mouse.move(750, 450)
    l0 = pg.evaluate("document.getElementById('canvas').scrollLeft")
    pg.mouse.wheel(500, 0)
    pg.wait_for_timeout(20)
    assert pg.evaluate("document.getElementById('canvas').scrollLeft") == l0   # nothing moved by itself
    assert not errs


def test_a_burst_of_arrows_never_skips_or_jams(browser, page_file):
    pg, errs = _desk(browser, page_file)
    S = pg.evaluate(STOPS)
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1500)
    pg.evaluate(TRACK)
    pg.evaluate("""() => new Promise(r => { let i=0; (function go(){ document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
       if(++i<100) setTimeout(go,4); else r(); })(); })""")
    pg.wait_for_timeout(4500)
    seen = pg.evaluate("cancelAnimationFrame(window._trk), window._seen")
    idx = [S.index(x) for x in seen]
    assert all(b - a == 1 for a, b in zip(idx, idx[1:])), seen               # every stop in turn, none skipped
    assert 1 <= idx[-1] - idx[0] <= 1 + 3 + 2                                 # the queue holds three (+ instant steps at the start)
    before = idx[-1]
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(1500)
    assert S.index(pg.evaluate(CUR)) == min(before + 1, len(S) - 1)           # not jammed
    assert not errs


def test_every_stop_rests_centred_and_clear_of_the_rail(browser, page_file):
    pg, errs = _desk(browser, page_file)
    S = pg.evaluate(STOPS)
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1500)
    for k in range(1, len(S)):
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1300)
        r = pg.evaluate("""(id) => { const cv=document.getElementById('canvas'), cr=cv.getBoundingClientRect(),
            c=document.querySelector('#node-'+id+' .node-card').getBoundingClientRect(), nav=document.getElementById('lanes-nav').getBoundingClientRect();
          return {cur:_altoLanesCurrent(), l:cv.scrollLeft, max:cv.scrollWidth-cv.clientWidth, dx:(c.left+c.right)/2-(cr.left+cr.width/2),
                  top:c.top, bottom:c.bottom, navTop:nav.top, cTop:cr.top, ring:document.getElementById('node-'+id).classList.contains('ln-cur')}; }""", S[k])
        assert r["cur"] == S[k] and r["ring"]
        assert abs(r["dx"]) < 1.5 or r["l"] <= 0.5 or r["l"] >= r["max"] - 1, r       # centred unless at an end
        assert r["bottom"] <= r["navTop"] + 0.5 and r["top"] >= r["cTop"] - 0.5, r      # clear of the rail and the bars
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(900)
    assert pg.evaluate(CUR) == S[-1]                                           # the last one is reachable, and the end
    assert not errs


def test_the_whole_timeline_and_back_down(browser, page_file):
    pg, errs = _desk(browser, page_file)
    S = pg.evaluate(STOPS)
    pg.click("#lanes-nav .lnv-ov")
    pg.wait_for_timeout(900)
    assert "scale(" in pg.evaluate("document.getElementById('world').style.transform")
    box = pg.evaluate("""() => { const r=document.getElementById('world').getBoundingClientRect(); return [r.left, r.right, innerWidth]; }""")
    assert box[0] >= 0 and box[1] <= box[2]                                    # it all fits
    tgt = S[len(S) // 2]
    pt = pg.evaluate("""(id) => { const r=document.querySelector('#node-'+id+' .node-card').getBoundingClientRect(); return [(r.left+r.right)/2, (r.top+r.bottom)/2]; }""", tgt)
    pg.mouse.click(*pt)
    pg.wait_for_timeout(1200)
    assert pg.evaluate(CUR) == tgt and not pg.evaluate("window._focusedNodeId")
    assert pg.evaluate("document.getElementById('world').style.transform") == ""
    pg.click("#lanes-nav .lnv-ov")
    pg.wait_for_timeout(900)
    pg.keyboard.press("Escape")                                                # Esc: back where the steps were
    pg.wait_for_timeout(1000)
    assert pg.evaluate(CUR) == tgt
    assert not errs


def test_reduced_motion_steps_in_one_frame(browser, page_file):
    pg, errs = _desk(browser, page_file, reduced_motion="reduce")
    pg.evaluate("""() => { window._rec=[]; const cv=document.getElementById('canvas');
      (function f(){ window._rec.push(cv.scrollLeft); window._raf=requestAnimationFrame(f); })(); }""")
    pg.keyboard.press("End")
    pg.wait_for_timeout(500)
    rec = pg.evaluate("cancelAnimationFrame(window._raf), window._rec")
    assert sum(1 for a, b in zip(rec, rec[1:]) if a != b) == 1
    assert not errs


def test_a_character_in_the_key_restricts_the_steps(browser, page_file):
    pg, errs = _desk(browser, page_file)
    pg.click("#key-toggle")
    pg.click('#lanes-key .lk-row[data-k="tomas"]')
    pg.wait_for_timeout(1500)
    pg.click("#key-toggle")
    mine = pg.evaluate("""() => { const L=_ALTO_LANES, t=L.lines.find(l=>l.id==='tomas');
        return [].concat.apply([],ACT_SEQS).filter(id => L.ev[id].l==='tomas' || t.from===id || t.to===id); }""")
    seen = [pg.evaluate(CUR)]
    for _ in range(len(mine) + 1):
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1250)
        if pg.evaluate(CUR) != seen[-1]:
            seen.append(pg.evaluate(CUR))
    assert seen == mine
    assert "Tomas only" in pg.evaluate("document.querySelector('#lanes-nav .lnv-tag').textContent")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(200)
    assert pg.evaluate("window._altoLanesLock()") is None
    assert "only" not in pg.evaluate("document.querySelector('#lanes-nav .lnv-tag').textContent")
    assert not errs


def test_phones_keep_the_card_view(browser, page_file):
    kw = {"viewport": {"width": 390, "height": 760}, "user_agent": PHONE_UA}
    if browser.browser_type.name == "chromium":
        kw.update(is_mobile=True, has_touch=True)
    pg = browser.new_context(**kw).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page_file.as_uri())
    pg.wait_for_timeout(1500)
    r = pg.evaluate("({m: document.documentElement.classList.contains('mobile'), rail: !!document.getElementById('lanes-nav'), step: typeof window._altoLanesStep})")
    assert r == {"m": True, "rail": False, "step": "undefined"}
    assert not errs
