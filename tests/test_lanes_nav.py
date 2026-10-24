"""Going round a horizontal timeline (lanes_nav.py): guided travel with a magnetic settle.

The wheel, a trackpad and a drag move the camera continuously along the main line
in page order, as far as the hand says (a small scroll a little, a big flick
several events); its height follows the line by itself, into a flashback's dip and
back; when the input stops it settles exactly on an event, centred and clear of the
rail, and new input mid-settle takes over with no jump. ← / → still step exactly
one event; a burst never skips or jams; the whole timeline fits the window and a
click there comes back down; a character in the key restricts the path to its
events; reduced motion jumps; phones are left to the engine's card view.

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
LANES_V2 = ROOT / "samples" / "lanes_v2_brief.json"
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
    assert ": ease(p);" in js.split("function tick(", 1)[1].split("\nfunction ", 1)[0]       # glides and settles: the engine's curve
    for fn in ("draw", "land", "tick", "glideTo"):                                       # every camera write: the whole-px axis
        body = js.split("function " + fn + "(", 1)[1].split("\nfunction ", 1)[0]
        assert not re.search(r"\.scroll(Left|Top)\s*=", body), fn
    assert "axis('scrollLeft').go(L); axis('scrollTop').go(T);" in js


def test_reduced_motion_jumps():
    js = lanes_nav.NAV_JS
    assert "matchMedia('(prefers-reduced-motion: reduce)')" in js
    assert "var ms=(opt.instant || reduced() || d<.5) ? 0 :" in js and "if(!ms){" in js
    assert "var kk=(reduced() || M.drag) ? 1 :" in js                                   # travel follows the hand unsmoothed
    assert "if(reduced()){ ovSet(to);" in js


def test_no_lockouts_the_tail_is_travel():
    js = lanes_nav.NAV_JS
    # 1.9.88's one-gesture-one-step machinery is gone: no gesture lockout, no re-flick arming
    for gone in ("RETRAVEL", "GRACE", "SPIKE", "W.armed", "wfire("):
        assert gone not in js, gone
    wheel = js.split("function onWheel(", 1)[1].split("\nfunction ", 1)[0]
    assert "addTravel(d, soft);" in wheel and "if(_busy" not in wheel


def test_steps_queue_like_the_engines_hops():
    js = lanes_nav.NAV_JS
    assert "QMAX=3" in js and "if(_busy){ if(repeat ? !_q.length : _q.length<QMAX) _q.push([dir,src]); return; }" in js


def test_phones_are_left_to_the_engine():
    js, css = lanes_nav.NAV_JS, lanes_nav.NAV_CSS
    head = js.split("var SETTLE=", 1)[0]
    assert "if(de.classList.contains('mobile')) return;" in head
    assert "html.mobile #lanes-nav" in css and "html.alto-editing #lanes-nav" in css


def test_the_kept_line_is_readable_for_character_focus():
    assert "window._altoLanesLock=function(id)" in lanes.LANES_JS


# ── in a browser ────────────────────────────────────────────────────────────

try:                                               # the browser tests only: the checks above run anywhere
    import playwright.sync_api as pw
except ImportError:                                # pragma: no cover
    pw = None


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
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


@pytest.fixture(scope="module")
def v2_file(tmp_path_factory):
    f = tmp_path_factory.mktemp("lanesnav2") / "page.html"
    f.write_text(_build(LANES_V2), encoding="utf-8")
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
TRAVEL = "window._altoLanesTravel()"
# wheel events [delay ms, dx, dy, mode] dispatched on the board at real times
WHEEL = """(evs) => new Promise(res => { const t=document.getElementById('world'); let i=0;
  function go(){ const e=evs[i++]; t.dispatchEvent(new WheelEvent('wheel',{deltaX:e[1],deltaY:e[2],deltaMode:e[3]||0,bubbles:true,cancelable:true}));
    if(i<evs.length) setTimeout(go, evs[i][0]); else setTimeout(res, 30); }
  setTimeout(go, evs[0][0]); })"""
TRACK = """() => { window._seen=[]; (function f(){ const c=window._altoLanesCurrent(); if(window._seen[window._seen.length-1]!==c) window._seen.push(c);
  window._trk=requestAnimationFrame(f); })(); }"""
# every frame: [t, scrollLeft, scrollTop, a neighbouring card's left, top]
REC = """(sel) => { window._rec=[]; const cv=document.getElementById('canvas');
  (function fr(t){ const s=document.querySelector(sel), r=s.getBoundingClientRect();
    window._rec.push([t, cv.scrollLeft, cv.scrollTop, r.left, r.top]); window._recRaf=requestAnimationFrame(fr); })(performance.now()); }"""
RECSTOP = "() => { cancelAnimationFrame(window._recRaf); return window._rec; }"
RESTED = """(id) => { const cv=document.getElementById('canvas'), cr=cv.getBoundingClientRect(),
    c=document.querySelector('#node-'+id+' .node-card').getBoundingClientRect(), nav=document.getElementById('lanes-nav').getBoundingClientRect();
  return {cur:_altoLanesCurrent(), l:cv.scrollLeft, max:cv.scrollWidth-cv.clientWidth, dx:(c.left+c.right)/2-(cr.left+cr.width/2),
          top:c.top, bottom:c.bottom, navTop:nav.top, cTop:cr.top, n:document.querySelector('#lanes-nav .lnv-n').textContent,
          ring:document.getElementById('node-'+id).classList.contains('ln-cur'), moving:_altoLanesTravel().moving}; }"""


def _trackpad(total, sign=1):
    """a trackpad swipe: a short ramp, then its inertia tail (smaller and smaller events) summing to ~total px"""
    peak = max(3.0, min(70.0, total * 0.045))
    out, left = [], total
    for v in (peak * x for x in (0.08, 0.25, 0.5, 0.8, 1.0)):
        v = min(v, left); out.append(v); left -= v
    v = peak * 0.955
    while left > 0.3:
        v = max(0.3, min(v, left)); out.append(v); left -= v; v *= 0.955
    return [[10 if i == 0 else 16, 0, round(sign * x, 3)] for i, x in enumerate(out) if x > 0]


def _kick(rec):
    """the largest change of the card's on-screen speed (px/ms) from one frame to the next, and its top speed"""
    sp = [((b[3] - a[3]) ** 2 + (b[4] - a[4]) ** 2) ** .5 / (b[0] - a[0]) for a, b in zip(rec, rec[1:]) if b[0] > a[0]]
    mv = [i for i, v in enumerate(sp) if v > 1e-4]
    if not mv:
        return 0, 0
    sp = sp[max(0, mv[0] - 1): mv[-1] + 2]
    return max([abs(b - a) for a, b in zip(sp, sp[1:])] or [0]), max(sp)


def _jump(rec):
    return max([max(abs(b[1] - a[1]), abs(b[2] - a[2])) for a, b in zip(rec, rec[1:])] or [0])


def _at(pg, id_):
    pg.evaluate("(id) => window._altoLanesStep(id)", id_)
    pg.wait_for_timeout(1400)
    assert pg.evaluate(CUR) == id_


def _rested_ok(r):
    # centred across (unless the board's end stops it), marked, still. Not asked: that the card clears the rail or the bars —
    # the camera stays with the MAIN LINE and never moves up or down to suit one event's card (test_the_camera_stays_with_the_main_line)
    return ((abs(r["dx"]) < 1.5 or r["l"] <= 0.5 or r["l"] >= r["max"] - 1)
            and r["ring"] and not r["moving"])


MAINSCREEN = """(id) => { const G=window._altoLanesGeo, cv=document.getElementById('canvas'), ev=G.at && G.at[id];
  return ((ev && ev.line === 'main') ? ev.y : G.mainY) - cv.scrollTop; }"""


def test_the_camera_stays_with_the_main_line(browser, v2_file):
    """No bounce: at every stop the main line is at the same height on screen — except that it follows a flashback's dip."""
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    ys, dips = [], pg.evaluate("() => (window._altoLanesGeo.detours || []).map(d => d.nodes)")
    inside = {i for d in dips for i in d}
    for id_ in S:
        _at(pg, id_)
        ys.append((id_, pg.evaluate(MAINSCREEN, id_)))
    plain = [y for i, y in ys if i not in inside]
    assert plain and max(plain) - min(plain) <= 1.5, ys                         # the page's own events: one height
    for i, y in ys:
        if i in inside:                                                          # a flashback: the main line is down on the past track, the camera went with it
            assert abs(y - plain[0]) <= 1.5, ys
    assert not errs


def test_a_small_scroll_moves_less_than_a_big_one(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[1])
    pg.evaluate(WHEEL, [[10, 0, 1], [16, 0, 2], [16, 0, 1]])                     # a brush of the trackpad: back where it was
    pg.wait_for_timeout(1000)
    assert pg.evaluate(CUR) == S[1]
    pg.evaluate(WHEEL, _trackpad(80))                                            # a small scroll: on to the next
    pg.wait_for_timeout(1200)
    assert pg.evaluate(CUR) == S[2]
    _at(pg, S[1])
    pg.evaluate(WHEEL, _trackpad(1500))                                          # a big flick and its long tail: several
    pg.wait_for_timeout(1500)
    big = S.index(pg.evaluate(CUR)) - 1
    assert big >= 3, big
    r = pg.evaluate(RESTED, pg.evaluate(CUR))
    assert _rested_ok(r), r
    pg.evaluate(WHEEL, _trackpad(400, -1))                                        # and back
    pg.wait_for_timeout(1300)
    assert S.index(pg.evaluate(CUR)) < 1 + big
    assert not errs


def test_the_inertia_tail_is_more_travel_not_a_new_gesture(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[1])
    swipe = _trackpad(1500)
    pg.evaluate(WHEEL, swipe[:12])                                               # the swipe without its tail
    pg.wait_for_timeout(1300)
    short = pg.evaluate(TRAVEL)["u"]
    _at(pg, S[1])
    u0 = pg.evaluate(TRAVEL)["u"]
    pg.evaluate("() => { window._us=[]; (function f(){ window._us.push(_altoLanesTravel().u); window._ur=requestAnimationFrame(f); })(); }")
    pg.evaluate(WHEEL, swipe)
    pg.wait_for_timeout(1500)
    us = pg.evaluate("cancelAnimationFrame(window._ur), window._us")
    assert pg.evaluate(TRAVEL)["u"] > short + 300                                # the tail carried it on
    peak = max(us)
    rise = us[: us.index(peak) + 1]
    assert all(b >= a - 0.01 for a, b in zip(rise, rise[1:])) and rise[-1] > u0   # one movement: it never went back mid-tail
    assert not errs


def test_a_notch_goes_on_to_the_next_event_and_a_spin_further(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[1])
    pg.evaluate(WHEEL, [[10, 0, 100]])                                           # a mouse notch
    pg.wait_for_timeout(1200)
    assert pg.evaluate(CUR) == S[2]
    pg.evaluate(WHEEL, [[10, 0, -4.000244140625]])                               # Safari's small notch, back
    pg.wait_for_timeout(1200)
    assert pg.evaluate(CUR) == S[1]
    pg.evaluate(WHEEL, [[10, 0, 3, 1]])                                          # lines (deltaMode 1)
    pg.wait_for_timeout(1200)
    assert pg.evaluate(CUR) == S[2]
    _at(pg, S[0])
    pg.evaluate(WHEEL, [[10, 0, 100]] + [[45, 0, 100]] * 9)                      # a quick spin: no notch is swallowed
    pg.wait_for_timeout(1500)
    assert S.index(pg.evaluate(CUR)) >= 2
    assert not errs


def test_it_settles_exactly_on_an_event_centred_and_clear_of_the_rail(browser, page_file):
    pg, errs = _desk(browser, page_file)
    S = pg.evaluate(STOPS)
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1300)
    for k, amt in enumerate((40, 90, 160, 250, 380, 700, 120, 60)):
        sign = -1 if k in (4, 7) else 1
        pg.evaluate(WHEEL, _trackpad(amt, sign))
        pg.wait_for_timeout(1300)
        cur = pg.evaluate(CUR)
        r = pg.evaluate(RESTED, cur)
        assert cur in S and _rested_ok(r), (amt, r)
        assert r["n"] == str(S.index(cur) + 1)                                   # the rail says which, at rest
    assert not errs


def test_the_rail_follows_the_nearest_event_while_travelling(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[0])
    pg.evaluate("""() => { window._ns=[]; (function f(){ const n=document.querySelector('#lanes-nav .lnv-n').textContent;
      if(window._ns[window._ns.length-1]!==n) window._ns.push(n); window._nr=requestAnimationFrame(f); })(); }""")
    pg.evaluate(WHEEL, [[10, 0, 3]] + [[16, 0, 12]] * 110)                       # a long, even scroll
    pg.wait_for_timeout(1300)
    ns = pg.evaluate("cancelAnimationFrame(window._nr), window._ns")
    idx = [int(n) for n in ns]
    assert len(idx) >= 4 and all(b - a == 1 for a, b in zip(idx, idx[1:])), ns   # it counted up through them, one by one
    assert not errs


def test_new_input_mid_settle_never_jumps(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    sel = f"#node-{S[4]} .node-card"
    _at(pg, S[3])
    pg.evaluate(REC, sel)
    pg.evaluate(WHEEL, _trackpad(200))                                           # the same stream from rest, for comparison
    pg.wait_for_timeout(1300)
    base = pg.evaluate(RECSTOP)
    for sign in (1, -1):
        _at(pg, S[3])
        pg.evaluate(REC, sel)
        pg.evaluate(WHEEL, _trackpad(150))
        for _ in range(80):
            if pg.evaluate(TRAVEL)["settling"]:
                break
            pg.wait_for_timeout(8)
        assert pg.evaluate(TRAVEL)["settling"]
        pg.wait_for_timeout(90)
        pg.evaluate(WHEEL, _trackpad(200 if sign > 0 else 120, sign))             # on again, or back, mid-settle
        pg.wait_for_timeout(1300)
        rec = pg.evaluate(RECSTOP)
        assert _jump(rec) <= _jump(base) * 1.5 + 4, (sign, _jump(rec), _jump(base))
        assert _kick(rec)[0] <= _kick(base)[0] * 1.6 + 0.15, (sign, _kick(rec), _kick(base))
        r = pg.evaluate(RESTED, pg.evaluate(CUR))
        assert _rested_ok(r), r
    assert not errs


def test_the_height_follows_the_line_through_a_flashback(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    fb = pg.evaluate("(ids) => ids.map(id => (_ALTO_LANES.ev[id]||{}).flash||'')", S)
    j = next(i for i, x in enumerate(fb) if x)
    k = next(i for i in range(j, len(S)) if not fb[i])                           # the first event back in the present
    _at(pg, S[j - 1])
    t = pg.evaluate(TRAVEL)
    P = t["P"]
    assert P[j][1] > P[j - 1][1] + 20 and abs(P[k][1] - P[j - 1][1]) < 2        # its rest dips with the line, and comes back up
    pg.evaluate(REC, f"#node-{S[k]} .node-card")
    n = int((t["U"][k] - t["U"][j - 1] - 3) / 10)                                # ends just short of it: the settle goes on
    pg.evaluate(WHEEL, [[10, 0, 3]] + [[16, 0, 10]] * n)                          # a steady sideways scroll across it
    pg.wait_for_timeout(1300)
    rec = pg.evaluate(RECSTOP)
    tops = [r[2] for r in rec]
    assert max(tops) >= P[j][1] - 2 and abs(tops[-1] - P[k][1]) < 2              # down into the past, back up after
    assert max(abs(b - a) for a, b in zip(tops, tops[1:])) < 12                  # gently, never a jump
    lefts = [r[1] for r in rec]
    assert all(b >= a - 0.5 for a, b in zip(lefts, lefts[1:]))                   # across: only ever onward
    assert not errs


def test_up_and_down_input_is_the_same_travel(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[1])
    t0 = pg.evaluate("document.getElementById('canvas').scrollTop")
    pg.mouse.move(750, 450)
    pg.mouse.wheel(0, 120)                                                       # a real vertical wheel
    pg.wait_for_timeout(1400)
    assert pg.evaluate(CUR) == S[2]
    r = pg.evaluate(RESTED, S[2])
    assert _rested_ok(r), r
    assert pg.evaluate("(t) => Math.abs(document.getElementById('canvas').scrollTop - _altoLanesTravel().P[_altoLanesTravel().ids.indexOf(_altoLanesCurrent())][1]) < 1.5", t0)
    assert not errs


def _bare(pg, y):
    """An x on row y with only the board's background under it (no card, line, tag or button) and room to drag leftward."""
    return pg.evaluate("""(y) => { for (let x = 1500; x > 700; x -= 10) { const e = document.elementFromPoint(x, y);
        if (e && (e.id === 'canvas' || e.id === 'world' || e.id === 'glass-slab' || e.id === 'lanes-svg' || e.classList.contains('lanes-unit'))) return x; } return 1200; }""", y)


def test_dragging_the_background_travels_and_settles(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[1])
    y = pg.evaluate("document.getElementById('lanes-nav').getBoundingClientRect().top - 30")
    t0 = pg.evaluate("document.getElementById('canvas').scrollTop")
    x0 = _bare(pg, y)                                                            # events sit close now: start where there is only background
    pg.mouse.move(x0, y)
    pg.mouse.down()
    for k in range(1, 21):
        pg.mouse.move(x0 - k * 25, y + k * 3)                                    # a slightly sloping drag leftward
        pg.wait_for_timeout(16)
    pg.wait_for_timeout(150)                                                     # held still, then let go: no throw
    pg.mouse.up()
    pg.wait_for_timeout(1500)
    cur = pg.evaluate(CUR)
    assert S.index(cur) >= 2 and not pg.evaluate("!!window._focusedNodeId")
    r = pg.evaluate(RESTED, cur)
    assert _rested_ok(r), r
    i0 = S.index(cur)
    x0 = _bare(pg, y)
    pg.mouse.move(x0, y)
    pg.mouse.down()
    for k in range(1, 8):
        pg.mouse.move(x0 - k * 40, y)
        pg.wait_for_timeout(16)
    pg.mouse.up()                                                                # thrown: it coasts on, then rests
    pg.wait_for_timeout(2000)
    cur = pg.evaluate(CUR)
    assert S.index(cur) > i0 and _rested_ok(pg.evaluate(RESTED, cur))
    assert pg.evaluate("document.getElementById('canvas').scrollTop") >= 0 and t0 >= 0
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


def test_arrows_step_exactly_one_even_mid_travel(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[1])
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(1300)
    assert pg.evaluate(CUR) == S[2]
    pg.keyboard.press("ArrowLeft")
    pg.wait_for_timeout(1300)
    assert pg.evaluate(CUR) == S[1]
    pg.evaluate(WHEEL, [[10, 0, 3]] + [[16, 0, 4]] * 6)                          # a little way along, still moving
    pg.keyboard.press("ArrowRight")                                              # → : the next event ahead of the camera
    pg.wait_for_timeout(1400)
    assert pg.evaluate(CUR) == S[2]
    assert _rested_ok(pg.evaluate(RESTED, S[2]))
    assert not errs


def test_every_stop_rests_centred_and_clear_of_the_rail(browser, page_file):
    pg, errs = _desk(browser, page_file)
    S = pg.evaluate(STOPS)
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1500)
    for k in range(1, len(S)):
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1300)
        r = pg.evaluate(RESTED, S[k])
        assert r["cur"] == S[k] and _rested_ok(r), r
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(900)
    assert pg.evaluate(CUR) == S[-1]                                           # the last one is reachable, and the end
    assert not errs


def test_travel_and_settle_are_as_smooth_as_a_step(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    sel = f"#node-{S[4]} .node-card"
    _at(pg, S[3])
    pg.evaluate(REC, sel)
    pg.keyboard.press("ArrowRight")                                              # the reference: a step's glide
    pg.wait_for_timeout(1400)
    ref = _kick(pg.evaluate(RECSTOP))[0]
    _at(pg, S[3])
    pg.evaluate(REC, sel)
    pg.evaluate(WHEEL, [[10, 0, 100]])                                           # a notch, then its settle
    pg.wait_for_timeout(1400)
    notch = _kick(pg.evaluate(RECSTOP))[0]
    _at(pg, S[3])
    pg.evaluate(REC, sel)
    pg.evaluate(WHEEL, [[10, 0, 2]] + [[16, 0, 8]] * 30)                         # an even trackpad scroll, then its settle
    pg.wait_for_timeout(1400)
    even = _kick(pg.evaluate(RECSTOP))[0]
    assert notch <= ref * 1.6 + 0.15 and even <= ref * 1.6 + 0.15, (ref, notch, even)
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
    pg.evaluate(WHEEL, _trackpad(120))                                           # travel goes on from there
    pg.wait_for_timeout(1300)
    ahead = pg.evaluate(CUR)
    assert S.index(ahead) > S.index(tgt)                                       # it went on ahead (how many events 120px is depends on the spacing)
    pg.click("#lanes-nav .lnv-ov")
    pg.wait_for_timeout(900)
    pg.keyboard.press("Escape")                                                # Esc: back where the camera was
    pg.wait_for_timeout(1000)
    assert pg.evaluate(CUR) == ahead
    assert not errs


SKY = """() => { const k=document.getElementById('lanes-ov-sky'), e=document.getElementById('glass-slab'), c=document.getElementById('canvas').getBoundingClientRect();
  const r=k && k.getBoundingClientRect();
  return {sky: !!k, t:r&&r.top, b:r&&r.bottom, l:r&&r.left, r:r&&r.right, ct:c.top, cb:c.bottom, op:k&&getComputedStyle(k).opacity, slabOp:getComputedStyle(e).opacity,
          slab:[e.style.top, e.style.height, e.style.getPropertyValue('width'), e.style.getPropertyValue('left')], world:document.getElementById('world').offsetHeight}; }"""


def test_zoomed_out_a_backdrop_fills_the_window_and_leaves_with_the_zoom(browser, page_file):
    pg, errs = _desk(browser, page_file)
    before = pg.evaluate(SKY)
    assert not before["sky"]
    pg.click("#lanes-nav .lnv-ov")
    pg.wait_for_timeout(1100)
    z = pg.evaluate(SKY)
    assert z["sky"] and z["t"] <= z["ct"] + 1 and z["b"] >= z["cb"] - 1 and z["l"] <= 1 and z["r"] >= 1500   # no bare page around the board
    assert float(z["op"]) > 0.5 and float(z["slabOp"]) == 0                                               # the slab hands over to it
    assert z["slab"] == before["slab"] and z["world"] == before["world"]                                    # nothing is resized (the page's height follows the slab)
    pg.click("#lanes-nav .lnv-ov")
    pg.wait_for_timeout(1100)
    after = pg.evaluate(SKY)
    assert not after["sky"] and float(after["slabOp"]) == float(before["slabOp"]) and after["slab"] == before["slab"]
    assert not errs


def test_reduced_motion_steps_and_settles_in_one_frame(browser, page_file):
    pg, errs = _desk(browser, page_file, reduced_motion="reduce")
    pg.evaluate("""() => { window._rec=[]; const cv=document.getElementById('canvas');
      (function f(){ window._rec.push(cv.scrollLeft); window._raf=requestAnimationFrame(f); })(); }""")
    pg.keyboard.press("End")
    pg.wait_for_timeout(500)
    rec = pg.evaluate("cancelAnimationFrame(window._raf), window._rec")
    assert sum(1 for a, b in zip(rec, rec[1:]) if a != b) == 1
    S = pg.evaluate(STOPS)
    pg.evaluate(WHEEL, [[10, 0, -100]])                                          # a notch back: travel, then the settle jumps
    pg.wait_for_timeout(900)
    assert pg.evaluate(CUR) == S[-2] and _rested_ok(pg.evaluate(RESTED, S[-2]))
    assert not errs


def test_a_character_in_the_key_restricts_the_steps(browser, page_file):
    pg, errs = _desk(browser, page_file)
    pg.click("#key-toggle")
    pg.click('#lanes-key .lk-row[data-k="tomas"]')
    pg.wait_for_timeout(1500)
    pg.click("#key-toggle")
    mine = pg.evaluate("""() => { const L=_ALTO_LANES, t=L.lines.find(l=>l.id==='tomas');
        return [].concat.apply([],ACT_SEQS).filter(id => L.ev[id].l==='tomas' || t.from===id || t.to===id); }""")
    pg.evaluate("document.activeElement && document.activeElement.blur()")       # (a focused button keeps the key for itself)
    pg.keyboard.press("Home")                                                    # the first of theirs, wherever the view happened to be
    pg.wait_for_timeout(1300)
    seen = [pg.evaluate(CUR)]
    for _ in range(len(mine) + 1):
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1250)
        if pg.evaluate(CUR) != seen[-1]:
            seen.append(pg.evaluate(CUR))
    assert seen == mine
    assert "Tomas only" in pg.evaluate("document.querySelector('#lanes-nav .lnv-tag').textContent")
    assert pg.evaluate(TRAVEL)["ids"] == mine                                     # the wheel's path is the character's too
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1300)
    pg.evaluate(WHEEL, [[10, 0, 100]])
    pg.wait_for_timeout(1300)
    assert pg.evaluate(CUR) == mine[1]
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(200)
    assert pg.evaluate("window._altoLanesLock()") is None
    assert "only" not in pg.evaluate("document.querySelector('#lanes-nav .lnv-tag').textContent")
    pg.evaluate(WHEEL, [[10, 0, 100]])                                           # and all of them again
    pg.wait_for_timeout(1300)
    assert pg.evaluate(TRAVEL)["ids"] == pg.evaluate(STOPS)
    assert not errs


def test_a_click_on_a_card_still_opens_it(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _at(pg, S[2])
    pg.click(f"#node-{S[2]} .node-card")
    pg.wait_for_timeout(900)
    assert pg.evaluate("document.documentElement.classList.contains('detail-open')")   # the engine's page for it, as before
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(900)
    assert not pg.evaluate("document.documentElement.classList.contains('detail-open')")
    pg.evaluate(WHEEL, [[10, 0, 100]])
    pg.wait_for_timeout(1300)
    assert pg.evaluate(CUR) == S[3]
    assert not errs


def test_phones_keep_the_card_view(browser, page_file):
    kw = {"viewport": {"width": 390, "height": 760}, "user_agent": PHONE_UA}
    if browser.browser_type.name == "chromium":
        kw.update(is_mobile=True, has_touch=True)
    pg = browser.new_context(**kw).new_page()
    errs = []
    pg.on("pageerror", lambda e: "/phone/" in str(e) or errs.append(str(e)))   # (the phone whole-view script is hosted: a file:// copy cannot fetch it and stays one card)
    pg.goto(page_file.as_uri())
    pg.wait_for_timeout(1500)
    r = pg.evaluate("({m: document.documentElement.classList.contains('mobile'), rail: !!document.getElementById('lanes-nav'), step: typeof window._altoLanesStep, travel: typeof window._altoLanesTravel})")
    assert r == {"m": True, "rail": False, "step": "undefined", "travel": "undefined"}
    assert not errs
