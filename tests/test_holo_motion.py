"""Holographic's Motion: On | Still switch in the background picker (cleanup-241, Board B-1118-MOTION). Still shows the poster and never fetches or plays a clip;
the choice rides in the background choice's own record ({v, t, m:'still'}), On is the default, Reduce Motion still forces Still."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_holo_anim import KIND, browser, _open, _can_h264, _make_site, pw      # noqa: E402,F401
from tests.test_holo_video import HVID, vsite                                         # noqa: E402,F401

VIDEO = "document.querySelectorAll('video').length"
PLAYING = "[...document.querySelectorAll('video')].filter(v=>!v.paused && !v.ended).length"


def _still(pg, key, bg):
    pg.evaluate("([k,b])=>localStorage.setItem(k+'-bg', JSON.stringify({v:b,t:Date.now(),m:'still'}))", [key, bg])
    pg.reload()
    pg.wait_for_timeout(1500)


@pytest.mark.parametrize("bg", list(KIND))
def test_still_fetches_and_plays_nothing_for_all_eleven(browser, vsite, bg):
    seen = []
    pg, ctx, errors = _open(browser, vsite, bg, mode=None, wait=300)
    ctx.on("request", lambda r: seen.append(r.url) if "/hvid/" in r.url else None)
    _still(pg, vsite[1], bg)
    assert pg.evaluate("window._altoMotion.get()") == "still"
    assert not seen and pg.evaluate(HVID) == 0 and pg.evaluate(VIDEO) == 0
    assert pg.evaluate("!!document.getElementById('alto-ha')") is False
    ctx.close()


def test_the_default_is_on_and_the_clip_plays(browser, vsite):
    pg, ctx, _ = _open(browser, vsite, "h-neon-rain", mode=None)
    if not _can_h264(pg):
        pytest.skip("no H.264")
    assert pg.evaluate("window._altoMotion.get()") == "on"
    assert pg.evaluate(VIDEO) == 1
    ctx.close()


@pytest.mark.parametrize("phone", [False, True])
def test_the_switch_is_in_the_picker_stills_live_and_is_remembered(browser, vsite, phone):
    pg, ctx, _ = _open(browser, vsite, "h-neon-rain", mode=None, phone=phone)
    can = _can_h264(pg)
    pg.evaluate("document.getElementById('bg-panel').classList.contains('open') || document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(500)
    row = pg.locator("#bg-motion")
    assert row.is_visible() and [b.inner_text() for b in row.locator(".bg-segb").all()] == ["On", "Still"]
    assert row.locator("[data-mo=on]").get_attribute("aria-pressed") == "true"
    if phone:
        for sel in ("[data-mo=on]", "[data-mo=still]"):
            box = row.locator(sel).bounding_box()
            assert box["height"] >= 44 and box["width"] >= 44, box
    if can:
        pg.wait_for_timeout(500)
        assert pg.evaluate(VIDEO) == 1
    row.locator("[data-mo=still]").click()
    pg.wait_for_timeout(400)
    assert pg.evaluate(VIDEO) == 0 and pg.evaluate(PLAYING) == 0           # the playing clip is paused and removed, live
    assert row.locator("[data-mo=still]").get_attribute("aria-pressed") == "true"
    rec = json.loads(pg.evaluate("k => localStorage.getItem(k+'-bg')", vsite[1]))
    assert rec["m"] == "still" and rec["v"] == "h-neon-rain"                 # kept in the background choice's own record
    pg.reload()
    pg.wait_for_timeout(1200)
    assert pg.evaluate("window._altoMotion.get()") == "still" and pg.evaluate(VIDEO) == 0
    pg.evaluate("document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(400)
    pg.locator("#bg-motion [data-mo=on]").click()                           # and On brings it back, and choosing another background keeps the choice
    assert pg.evaluate("window._altoMotion.get()") == "on"
    ctx.close()


def test_the_switch_is_keyboard_reachable_buttons_and_only_in_holographic(browser, vsite):
    pg, ctx, _ = _open(browser, vsite, "h-neon-rain", mode=None)
    pg.evaluate("document.getElementById('bg-panel').classList.contains('open') || document.getElementById('bg-toggle').click()")
    pg.wait_for_timeout(400)
    assert pg.evaluate("[...document.querySelectorAll('#bg-motion .bg-segb')].every(b=>b.tagName==='BUTTON' && b.tabIndex>=0)")
    pg.locator("#bg-style [data-sty=classic]").click()
    assert pg.locator("#bg-motion").is_hidden()
    ctx.close()


def test_reduce_motion_still_forces_still_with_motion_on(browser, vsite):
    pg, ctx, _ = _open(browser, vsite, "h-neon-rain", mode=None, reduce=True)
    assert pg.evaluate("window._altoMotion.get()") == "on"
    assert pg.evaluate(VIDEO) == 0 and pg.evaluate(HVID) == 0
    ctx.close()
