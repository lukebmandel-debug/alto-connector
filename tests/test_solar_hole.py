"""The black hole (solar_hole.py, Luke 2026-10-28 item 7): a quiz graded under the pass mark (study.py QUIZ_FAIL_PCT) on a
Star chart or 3D Star chart page sends the ship off to a black hole and back, with a Try again offer; never on a pass,
never on the System look or Retro; Esc skips, reduced motion fades; the quiz's own record is untouched.

Browser checks run in Chromium and WebKit (Playwright; skipped without them)."""
import copy
import json
import sys
from pathlib import Path

import pytest

from alto.build import study
from alto.build.builder import build_timeline, load_brief

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import _open, browser, solar_doc  # noqa: E402,F401
from test_solar_pool import SMALL, SMALL_LINKS  # noqa: E402
from test_study_browser import QUIZ  # noqa: E402


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    d = solar_doc(SMALL, "orbit", SMALL_LINKS)
    for n in d["nodes"]:
        if n["id"] == "u1-p1":
            n["sections"] = [{"h": "Synopsis", "t": "Text."}, {"h": "Quiz", "t": "", "quiz": copy.deepcopy(QUIZ)}]
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    assert "FAIL = 60" in html and "alto-quiz-fail" in html           # the one constant, and the event
    f = tmp_path_factory.mktemp("hole") / "hole.html"
    f.write_text(html, encoding="utf-8")
    return f


def test_the_pass_mark_is_one_constant():
    assert study.QUIZ_FAIL_PCT == 60
    assert "__ALTO_FAIL__" not in study.STUDY_JS.replace("__ALTO_FAIL__", "", 1)        # (replaced once, in the one place)


def _take(pg, good, look="stars", style="classic", craft="explorer", reset=True):
    pg.evaluate("([c, l, s, r]) => { window._altoCraft.set(c); window._altoFlyOff=false; window._altoSolarLook.set(l); window._altoSolarStyle.set(s); if (r) window._altoHole && window._altoHole.reset(); }", [craft, look, style, reset])
    pg.wait_for_timeout(900)
    pg.evaluate("() => window.enterFocus('u1-p1')"); pg.wait_for_timeout(1700)
    pg.evaluate("() => showDetail('node', 'u1-p1')"); pg.wait_for_timeout(400)
    pg.evaluate("""(good) => { document.querySelectorAll('.ast-quiz fieldset').forEach(function(f, qi){ var i=f.querySelectorAll('input');
      if(!good) i[i.length-1].click(); else (qi===0 ? [0] : qi===1 ? [0, 1] : [1]).forEach(function(k){ i[k].click(); }); });
      [].find.call(document.querySelectorAll('.ast-quiz button'), function(b){ return /Submit/.test(b.textContent); }).click(); }""", good)
    pg.wait_for_timeout(350)


def _key(pg, k):
    pg.bring_to_front()
    pg.keyboard.press(k)


def _esc(pg):
    _key(pg, "Escape")


STATE = "() => JSON.stringify({s: window._altoHole && window._altoHole.state(), bh: !!document.getElementById('bh'), on: document.documentElement.classList.contains('bh-on'), chip: !!document.getElementById('bh-chip'), detail: !!document.querySelector('#detail-page.visible')})"


def _st(pg):
    return json.loads(pg.evaluate(STATE))


def test_a_pass_or_a_calm_style_shows_no_black_hole(browser, page):
    pg, errs = _open(browser, page, wait=1500)
    _take(pg, True)
    s = _st(pg)
    assert not s["bh"] and not s["chip"] and s["detail"], s                       # a pass: the page stays
    pg.evaluate("() => showTimeline()")
    _take(pg, False, look="hub")                                                    # the System look: nothing of this runs
    s = _st(pg); assert not s["bh"] and not s["chip"] and s["detail"], s
    pg.evaluate("() => showTimeline()")
    _take(pg, False, style="retro")                                                 # Retro: not affected
    s = _st(pg); assert not s["bh"] and not s["chip"] and s["detail"], s
    pg.context.close()
    assert not errs, errs


def test_a_failing_score_falls_into_the_black_hole_skips_and_offers_try_again(browser, page):
    pg, errs = _open(browser, page, wait=1500)
    _take(pg, False)
    s = _st(pg)
    assert s["bh"] and s["on"] and not s["detail"] and s["s"]["mode"] == "warp" and s["s"]["end"] > 6.5, s      # the chart, the Explorer's warp
    pg.wait_for_timeout(1200)
    assert _st(pg)["s"]["skipBtn"], "a skip target is up within a second or so"
    _esc(pg); pg.wait_for_timeout(700)                          # Esc cuts to the return beat
    s = _st(pg); assert s["bh"] or s["chip"], s
    pg.wait_for_timeout(1400)
    s = _st(pg); assert s["chip"] and not s["bh"] and not s["on"], s              # the ship is back, the offer stands
    chip = pg.evaluate("() => { var c=document.getElementById('bh-chip'), r=c.getBoundingClientRect(); return {t:c.textContent.trim(), l:r.left, r:r.right, tp:r.top, b:r.bottom, w:innerWidth, h:innerHeight}; }")
    assert chip["t"] == "Try again" and chip["l"] >= 16 and chip["r"] <= chip["w"] - 16 and chip["tp"] >= 16 and chip["b"] <= chip["h"] - 16, chip
    rec = pg.evaluate("() => { var o=JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(function(k){ return /-st$/.test(k); })[0])); var k=Object.keys(o.s)[0]; return o.s[k].l; }")
    assert rec["s"] == 1 and rec["n"] == 3, rec                                    # the quiz's own record is intact
    _key(pg, "Enter"); pg.wait_for_timeout(600)                           # Enter = try again: the page, the quiz fresh
    s = _st(pg); assert s["detail"] and not s["chip"], s
    fresh = pg.evaluate("() => { var b=document.querySelector('.ast-quiz'); return !!b && !b.querySelector('.asq-res') && b.querySelectorAll('input:checked').length===0; }")
    assert fresh
    _take(pg, False, reset=False)                                                   # failing again inside 30 s: no second fall
    s = _st(pg); assert not s["bh"] and s["detail"], s
    pg.context.close()
    assert not errs, errs


def test_esc_dismisses_the_offer_and_every_craft_travels_its_own_way(browser, page):
    pg, errs = _open(browser, page, wait=1500)
    for craft, mode in (("halo", "jump"), ("rocket", None)):
        _take(pg, False, craft=craft)
        s = _st(pg); assert s["bh"] and s["s"]["mode"] == mode, (craft, s)
        _esc(pg); pg.wait_for_timeout(2200)
        assert _st(pg)["chip"]
        _esc(pg); pg.wait_for_timeout(200)
        s = _st(pg); assert not s["chip"] and not s["bh"], s
        pg.evaluate("() => showTimeline()")
    pg.context.close()
    assert not errs, errs


def test_in_the_3d_star_chart_too_and_reduced_motion_only_fades(browser, page):
    pg, errs = _open(browser, page, wait=1500)
    _take(pg, False, style="real", craft="halo")
    s = _st(pg); assert s["bh"] and s["s"]["mode"] == "jump", s
    _esc(pg); pg.wait_for_timeout(2400)
    assert _st(pg)["chip"]
    pg.context.close()
    ctx = browser.new_context(viewport={"width": 1500, "height": 950}, reduced_motion="reduce"); q = ctx.new_page(); e2 = []
    q.on("pageerror", lambda e: e2.append(str(e))); q.goto(page.as_uri()); q.wait_for_timeout(1500)
    _take(q, False)
    s = _st(q); assert s["bh"] and s["s"]["rd"] and s["s"]["end"] < 2, s            # a short fade, no flight
    q.wait_for_timeout(2300)
    s = _st(q); assert s["chip"] and not s["bh"], s
    ctx.close()
    assert not errs and not e2, (errs, e2)
