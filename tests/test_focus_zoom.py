"""The focus magnifier grows the card with CSS `zoom`, not `transform:scale`.

`transform:scale(1.7)` magnifies the card's existing 1x raster instead of
re-rendering it, so at 1.7x the text is a blown-up bitmap — reported as "blurry
when I enlarge a node", worst in Safari where `.node-card`'s backdrop-filter
pins the layer to its first rasterisation. `zoom` re-lays the card out, so the
glyphs are rendered at their final size.

The engine already carried this mechanism as the `.crisp` rule, but reached it
by scaling first and swapping at settle — and that swap frame re-flowed every
glyph advance at once, the "text jumps" glitch that keeps ALTO_CRISP_SWAP off.
There is no swap frame if the card is never scaled, so the zoom is ramped from
1 instead. These tests pin the mechanism, not the pixels.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.engine_patches import PATCHES, PatchError, apply_patches  # noqa: E402
from alto.engine import template as engine_template  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


@pytest.fixture(scope="module")
def html():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


def _focus_rule(html):
    i = html.index("html:not(.mobile) .node.focused .node-card{")
    return html[i:html.index("\n}", i)]


def test_the_focused_card_is_not_transform_scaled(html):
    assert "transform:scale(1.7) !important" not in html
    assert "transform:scale(1) !important" in _focus_rule(html)


def test_the_focused_card_grows_by_zoom(html):
    assert "_zoomRamp(el,FOCUS_K,240);" in html      # enter
    assert "_zoomRamp(el,1,220);" in html            # exit
    assert "var FOCUS_K=1.7" in html


def test_the_zoom_is_ramped_rather_than_swapped_in(html):
    """A settle-time swap from scale to zoom re-flows every glyph in one frame.
    Ramping the zoom itself means every frame is laid out, so there is no swap."""
    assert "requestAnimationFrame(step)" in html
    # and the old swap stays dormant — two mechanisms would compound to 2.89x
    assert "window.ALTO_CRISP_SWAP = false;" in html


def test_a_half_ramped_card_is_never_stranded(html):
    """Hopping focus before the ramp lands cancels it; the abandoned card has to
    be put back, or it keeps a partial inline zoom forever."""
    assert "if(_zwCard && _zwCard!==card) _setZoom(_zwCard,_zwTo);" in html
    assert "_setZoom(_cardOf(p),1);" in html          # previous node on re-focus


def test_exit_clears_the_inline_zoom_rather_than_pinning_it_to_1(html):
    """zoom:1 on an element is not the same as no zoom — it still forces the
    subtree into its own layout scope. Clear the property instead."""
    assert "card.style.zoom = (k>1.0005) ? String(k) : '';" in html


def test_only_safaris_fallback_background_is_raised(html):
    """--node-glass-bg is Blink-only and already at 0.90 so the card occludes the
    connector lines Chrome's dead backdrop-filter cannot hide. Raising the value
    would *lower* it there; raising the fallback touches Safari only."""
    assert "background:var(--node-glass-bg, var(--panel-glass-bg));" in _focus_rule(html)


def test_the_mobile_path_is_untouched(html):
    """Every focus rule is desktop-only, and the focus IIFE returns early on
    mobile — a phone must not pay for any of this."""
    rule = _focus_rule(html)
    assert rule.startswith("html:not(.mobile)")
    assert "if(document.documentElement.classList.contains('mobile')) return;" in html


@pytest.mark.parametrize("name", [p["name"] for p in PATCHES if p["name"].startswith("focus-")])
def test_each_focus_anchor_matches_the_engine_exactly_once(name):
    """The whole point of routing engine fixes through counted anchors: an engine
    refresh that moves one must fail the build, not silently drop the fix."""
    t = engine_template("timeline_template.html")
    p = next(x for x in PATCHES if x["name"] == name)
    assert p["count"] == 1
    assert t.count(p["old"]) == 1, f"{name}: anchor no longer unique in the engine"


@pytest.mark.parametrize("name", [p["name"] for p in PATCHES if p["name"].startswith("focus-")])
def test_a_moved_focus_anchor_fails_the_build_by_name(name):
    p = next(x for x in PATCHES if x["name"] == name)
    moved = engine_template("timeline_template.html").replace(p["old"], "/* moved */", 1)
    with pytest.raises(PatchError, match=name):
        apply_patches(moved)
