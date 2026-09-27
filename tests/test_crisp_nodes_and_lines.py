"""1.8.28: desktop node cards and chip outlines paint on whole device pixels,
and connecting lines can be followed (click) and singled out (hover).

The pixel behaviour itself was measured in Playwright WebKit 26.6 and Chromium
at 1x and 2x (see engine_patches: D-GRID); these tests pin the mechanism so a
later edit cannot quietly bring the transform-centred, measured-nudge version
back."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402

LINEAR = ROOT / "samples" / "contracts_brief.json"


def _html():
    return build_timeline(*load_brief(json.loads(LINEAR.read_text(encoding="utf-8"))))[0]


def test_desktop_nodes_are_centred_by_layout_on_every_engine():
    html = _html()
    assert '<style id="d-grid-centre">' in html
    assert ('html:not(.mobile) #world .node.dg:not([style*="transform"]){\n'
            '  transform:none; margin:var(--my,0px) 0 0 var(--mx,0px);') in html
    q = html[html.index('<script id="d-grid-quantize">'):]
    q = q[:q.index("</script>")]
    assert "ResizeObserver" in q and "MutationObserver" in q
    assert "is-blink" not in q and "vw-unzoomed" not in q     # no engine gate
    assert "getBoundingClientRect" not in q                   # nothing measured


def test_readers_of_a_node_centre_subtract_the_centring_margin():
    html = _html()
    assert "el.offsetLeft-(parseFloat(_cs.marginLeft)||0)+ox" in html      # focus fly
    assert "node.offsetLeft-(parseFloat(_ns.marginLeft)||0)" in html        # search


def test_chip_outlines_are_borders_one_visual_pixel_wide():
    html = _html()
    assert "--chip-rule:round(up, calc(1px / var(--alto-zoom, 0.8) - 0.001px), 0.5px);" in html
    assert ("html:not(.mobile) .csym-btn{ background:var(--chip-plate) !important; "
            "opacity:1 !important; border:var(--chip-rule) solid currentColor;") in html
    assert "box-shadow:inset 0 0 0 1px currentColor; }" not in html
    assert "html:not(.mobile) .tsym-btn{ box-shadow:none; border:var(--chip-rule)" in html


def test_lines_can_be_followed_and_singled_out():
    html = _html()
    assert "if(window._altoLineNav) return;" in html
    assert "h.setAttribute('data-edge-hit',t.getAttribute('data-edge'));" in html
    assert "window.enterFocus(best);" in html                    # click → far end, enlarged
    assert "#river-svg [data-edge-hit]{pointer-events:stroke;cursor:pointer;}" in html
    assert "#canvas.edge-hover .node:not(.edge-end) .node-card{opacity:.35 !important;}" in html
    # the relation label follows the same resting-pointer rule as the fade
    assert "document.addEventListener('alto:edge-dwell', function(e){" in html
    assert "var DWELL=300, SLOP=6" in html
    # the hit path is not a data-edge: the audit sampler and filters count those
    assert "setAttribute('data-edge',t" not in html


def test_fading_waits_for_the_pointer_to_rest_and_masks_lines_under_cards():
    html = _html()
    assert "arm=setTimeout(function(){ arm=null; if(akey) light(akey,ax,ay); },DWELL);" in html
    assert "e.setAttribute('mask','url(#alto-hover-mask)')" in html
    assert "cardMask(svg,'alto-hover-mask');" in html


def test_faded_lines_never_show_through_faded_cards():
    """Enlarging a card fades the rest; so do filters. Safari masks each line
    path under every card while anything is faded (not the outer <svg>, which
    WebKit stops drawing when masked)."""
    html = _html()
    assert "e.setAttribute('mask','url(#alto-fade-mask)')" in html
    assert "cv.classList.contains('focus-mode')" in html
    assert "svg.setAttribute('mask','url(#alto-fade-mask)')" not in html


def test_hovered_cards_grow_by_zoom_not_transform():
    html = _html()
    assert "transform: none;   /* D-GRID: enlarged by a zoom ramp" in html
    assert "var HK=1.08, HMS=160;" in html


def test_arrow_keys_follow_structure_then_reading_order_then_alignment():
    html = _html()
    f = html[html.index("  function focusNeighbor(dir){"):]
    f = f[:f.index("    if(best) enterFocus(best);")]
    s_ = f.index("if(dir==='s'){"); r = f.index("var seq=[].concat.apply([],ACT_SEQS)")
    a = f.index("if(ov<=0) return;"); c = f.index("Math.abs(diff)>60")
    assert s_ < r < a < c          # structure → reading order → aligned → compass


def test_an_enlarged_card_settles_into_layout_too():
    html = _html()
    assert "      if(window._altoSettle) window._altoSettle(el);\n" in html     # fly lands
    assert "if(window._altoUnsettle) window._altoUnsettle(el);" in html         # flies home
    assert "p._settled=0; p.style.margin='';" in html                           # focus moves on
