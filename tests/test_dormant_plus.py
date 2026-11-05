"""The dormant top bar's + waits out of sight (Luke, 2026-11-01: "when top nav bar is not activated and lying dormant, the plus button can
disappear and only appear on hovering"; Art's spec): with the chips wound in, #ct-chips is invisible until the pointer is within 64 x 96 px of it
or over the clef, or it takes keyboard focus. It keeps its box (no header jump) and the open bar keeps its x as ever. Checked in every style, in
WebKit first (Luke uses Safari) and in Chromium where each is installed. Desktop only: a phone never has #ct-chips (html.mobile)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_nav_chips_overlap import STYLES, _open, browser, html, origin  # noqa: E402,F401

STATE = r"""()=>{const b=document.getElementById('ct-chips'); if(!b) return null; const q=b.getBoundingClientRect();
 return {op:+getComputedStyle(b).opacity, l:q.left, t:q.top, w:q.width, h:q.height, off:document.documentElement.classList.contains('ct-chips-off'),
         clef:(()=>{const m=document.querySelector('#title-bar .brand-mark').getBoundingClientRect(); return {x:(m.left+m.right)/2, y:(m.top+m.bottom)/2};})()};}"""


def _wind_in(page):
    """Click the x: the chips wind in and it rests as a + (the class lands when the reel stops)."""
    page.click("#ct-chips")
    page.wait_for_function("document.documentElement.classList.contains('ct-chips-off')", timeout=4000)
    page.wait_for_timeout(300)


@pytest.mark.parametrize("style", STYLES)
def test_the_dormant_plus_shows_only_near_the_pointer_or_on_focus(browser, origin, style):
    page = _open(browser, origin, 1280, style)
    try:
        open_ = page.evaluate(STATE)
        assert open_ and open_["op"] == 1 and not open_["off"], open_             # the open bar keeps its x, in plain sight
        _wind_in(page)
        page.mouse.move(700, 600)
        page.wait_for_timeout(300)
        dormant = page.evaluate(STATE)
        assert dormant["off"] and dormant["op"] == 0, dormant                    # dormant and the pointer elsewhere: invisible
        assert abs(dormant["l"] - open_["l"]) < 1 and abs(dormant["t"] - open_["t"]) < 1 and dormant["w"] == open_["w"], (open_, dormant)  # …in the same place, same size
        cx, cy = dormant["l"] + dormant["w"] / 2, dormant["t"] + dormant["h"] / 2
        page.mouse.move(cx + 28, cy + 40)                                        # inside the 64 x 96 box, not on the +
        page.wait_for_timeout(300)
        assert page.evaluate(STATE)["op"] == 1
        page.mouse.move(cx + 40, cy)                                             # outside it
        page.wait_for_timeout(300)
        assert page.evaluate(STATE)["op"] == 0
        clef = dormant["clef"]
        page.mouse.move(clef["x"], clef["y"])                                    # over the clef
        page.wait_for_timeout(300)
        assert page.evaluate(STATE)["op"] == 1
        page.mouse.move(700, 600)
        page.wait_for_timeout(300)
        assert page.evaluate(STATE)["op"] == 0
        page.keyboard.press("Tab")                                               # keyboard use, then focus it (Safari's Tab skips buttons; Chromium's reaches it)
        page.focus("#ct-chips")
        page.wait_for_timeout(300)
        assert page.evaluate(STATE)["op"] == 1
        page.evaluate("document.activeElement.blur()")
        page.wait_for_timeout(300)
        assert page.evaluate(STATE)["op"] == 0
        page.mouse.move(cx, cy)                                                  # click it: the chips run out again, the x stays visible
        page.click("#ct-chips")
        page.wait_for_function("!document.documentElement.classList.contains('ct-chips-off')", timeout=4000)
        page.mouse.move(700, 600)
        page.wait_for_timeout(300)
        assert page.evaluate(STATE)["op"] == 1
    finally:
        page.close()


@pytest.mark.parametrize("style,color,square", [("classic", "rgb(91, 63, 196)", False), ("dark", "rgb(183, 166, 255)", False), ("retro", "rgb(217, 174, 85)", True),
                                           ("holodark", "rgb(77, 232, 216)", False)])    # (Holographic is dark only on a computer, so it has no light row here)
def test_the_plus_focus_ring_is_art_s_two_pixel_outline_in_the_styles_colour(browser, origin, style, color, square):
    page = _open(browser, origin, 1280, "holo" if style == "holodark" else style, dpr=2)
    if style == "holodark":
        page.evaluate("document.documentElement.classList.add('dark')")                           # (a Retina screen: WebKit snaps an outline to whole device pixels, so at 1x the page's zoom .8 would cost it half a pixel)
    try:
        _wind_in(page)
        page.mouse.move(700, 600)
        page.keyboard.press("Tab")
        page.focus("#ct-chips")
        page.wait_for_timeout(300)
        r = page.evaluate("""()=>{const b=document.getElementById('ct-chips'), c=getComputedStyle(b);
          const z=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--alto-zoom'))||.8;
          return {op:+c.opacity, w:parseFloat(c.outlineWidth)*z, st:c.outlineStyle, col:c.outlineColor, off:parseFloat(c.outlineOffset)*z, rad:c.borderTopLeftRadius, focus:b.matches(':focus-visible')};}""")
        assert r["focus"] and r["op"] == 1, r                                     # shown while it has focus
        assert abs(r["w"] - 2) < .05 and abs(r["off"] - 2) < .05 and (r["st"], r["col"]) == ("solid", color), r   # 2 screen px (the page runs at zoom .8)
        if style == "retro":
            assert r["rad"] == "0px", r                                           # Retro's ring is square
        page.evaluate("document.activeElement.blur()")
        page.mouse.move(700, 600)
        page.wait_for_timeout(300)
        assert page.evaluate("getComputedStyle(document.getElementById('ct-chips')).outlineStyle") == "none"   # no ring without keyboard focus
    finally:
        page.close()
