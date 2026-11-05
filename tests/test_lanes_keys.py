"""Held arrows on a horizontal timeline (Luke, 2026-11-01): a quick press steps to the next event, a long press travels smoothly along
the line and settles on an event when the key goes up; ↑ / ↓ held go on to other lines, and ↑ / ↓ with ← / → hop a line and travel along it.
Real key events from the browser (Playwright's keyboard is trusted), WebKit and Chromium; skipped without Playwright."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_lanes_nav import (CUR, RESTED, STOPS, REC, RECSTOP, _desk, _jump, _rested_ok, browser, page_file, v2_file)  # noqa: E402,F401

LINE = "(id) => (window._ALTO_LANES.ev[id] || {}).l || 'main'"


def _home(pg):
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1500)


def test_a_held_right_arrow_travels_smoothly_and_settles_on_an_event(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _home(pg)
    pg.evaluate(REC, "#canvas")
    pg.keyboard.down("ArrowRight")
    pg.wait_for_timeout(1600)
    held = pg.evaluate(CUR)
    pg.keyboard.up("ArrowRight")
    pg.wait_for_timeout(1500)
    rec = pg.evaluate(RECSTOP)
    end = pg.evaluate(CUR)
    assert S.index(held) >= 2, (held, S)                                          # further than one step
    assert S.index(end) >= S.index(held) and _rested_ok(pg.evaluate(RESTED, end))  # on an event, centred, still
    assert _jump(rec) < 140, _jump(rec)                                           # smooth: no frame jumps
    assert not errs


def test_a_held_left_arrow_travels_back(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    pg.keyboard.press("End")
    pg.wait_for_timeout(1500)
    pg.keyboard.down("ArrowLeft")
    pg.wait_for_timeout(1500)
    pg.keyboard.up("ArrowLeft")
    pg.wait_for_timeout(1500)
    end = pg.evaluate(CUR)
    assert S.index(end) <= len(S) - 3, (end, S)
    assert _rested_ok(pg.evaluate(RESTED, end))
    assert not errs


def test_a_quick_press_is_still_one_step_and_lets_go_at_once(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    S = pg.evaluate(STOPS)
    _home(pg)
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(1600)
    assert pg.evaluate(CUR) == S[1]
    assert not errs


def _at_arrive(pg):
    pg.evaluate("(id) => window._altoLanesStep(id)", "arrive")                       # the page's first event, on the main line (Ben's line is just below it)
    pg.wait_for_timeout(1400)
    assert pg.evaluate(CUR) == "arrive"


def test_held_down_goes_to_the_other_line_and_held_up_comes_back(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    _at_arrive(pg)
    pg.keyboard.down("ArrowDown")
    pg.wait_for_timeout(1500)
    pg.keyboard.up("ArrowDown")
    pg.wait_for_timeout(1300)
    assert pg.evaluate(CUR) == "ben-letter" and pg.evaluate(LINE, "ben-letter") == "ben"
    assert _rested_ok(pg.evaluate(RESTED, "ben-letter"))
    pg.keyboard.down("ArrowUp")
    pg.wait_for_timeout(1500)
    pg.keyboard.up("ArrowUp")
    pg.wait_for_timeout(1300)
    assert pg.evaluate(CUR) == "arrive"
    assert _rested_ok(pg.evaluate(RESTED, "arrive"))
    assert not errs


def test_down_and_right_hops_a_line_and_travels_along_it(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    _at_arrive(pg)
    pg.keyboard.down("ArrowDown")
    pg.keyboard.down("ArrowRight")
    pg.wait_for_timeout(1900)
    path = pg.evaluate("window._altoLanesTravel().ids")
    pg.keyboard.up("ArrowRight")
    pg.keyboard.up("ArrowDown")
    pg.wait_for_timeout(1600)
    end = pg.evaluate(CUR)
    assert "ben-leaves" in path and "ben-letter" in path, path                       # the travel follows Ben's line, not the main line
    xs = pg.evaluate("(ids) => ids.map(i => window._altoLanesGeo.x[i])", ["ben-letter", end])
    assert xs[1] > xs[0] + 150 and end != "ben-letter", (end, xs)                    # and went on along it
    assert _rested_ok(pg.evaluate(RESTED, end))
    assert not errs


def test_a_wheel_or_home_returns_the_travel_to_the_main_line(browser, v2_file):
    pg, errs = _desk(browser, v2_file)
    _at_arrive(pg)
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(1400)
    assert pg.evaluate(CUR) == "ben-letter"
    pg.keyboard.press("Home")
    pg.wait_for_timeout(1400)
    assert "ben-leaves" not in pg.evaluate("window._altoLanesTravel().ids")
    assert not errs


def test_letting_go_is_one_ease_out_to_the_event_never_a_stop_and_a_restart(browser, v2_file):
    """Art (1101-4401-a): after key-up the camera must not nearly stop and then set off again for the event."""
    pg, errs = _desk(browser, v2_file)
    _home(pg)
    pg.evaluate(REC, "#canvas")
    pg.keyboard.down("ArrowRight")
    pg.wait_for_timeout(1500)
    pg.evaluate("window._rel = performance.now()")
    pg.keyboard.up("ArrowRight")
    pg.wait_for_timeout(1600)
    rec = pg.evaluate(RECSTOP)
    rel = pg.evaluate("window._rel")
    sp = [(b[0], (b[1] - a[1]) / (b[0] - a[0])) for a, b in zip(rec, rec[1:]) if b[0] > a[0]]
    dts = sorted(b[0] - a[0] for a, b in zip(rec, rec[1:]))
    if dts[len(dts) // 2] > 20:                       # a loaded headless Chromium draws this page at 25-30 fps: one frame says nothing there
        pytest.skip("frames slower than 50 fps (median %.0f ms): the per-frame speed cannot show a stall" % dts[len(dts) // 2])
    cruise = sorted(v for t, v in sp if t < rel - 150)[-20:]
    v0 = sum(cruise) / len(cruise)
    after = [v for t, v in sp if t >= rel]
    end = max(i for i, v in enumerate(after) if v > 0.02 * v0)                       # the last frame still moving
    body = after[:max(1, end - 4)]                                                    # all but the final few frames of the arrival
    assert v0 > 0.8, v0                                                               # it was travelling (px/ms)
    assert min(body) > 0.12 * v0, (v0, [round(x, 2) for x in after])                  # never near a stop on the way
    dur = (rec[-1][0] and next(t for t, v in reversed(sp) if v > 0.02 * v0)) - rel
    assert 380 <= dur <= 900, dur                                                     # about half a second, as Art asked
    jitter = max(abs(v - v0) for t, v in sp if rel - 750 < t < rel - 250)
    assert jitter < 0.45 * v0, (v0, jitter)                                           # the cruise is level (Art: +-200 px/s of 1500)
    assert not errs
