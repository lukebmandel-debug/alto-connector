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
    assert "if(hot) return !n.classList.contains('edge-end');" in html


def test_faded_lines_never_show_through_faded_cards():
    """Enlarging a card fades the rest; so do filters and line hover. Each
    faded line is redrawn with the stretches under faded cards left out —
    plain geometry. Not an SVG <mask> (Safari re-rendered masked lines every
    frame of a fly, 1.8.30-31) and not a clipPath (Safari did not apply it,
    1.8.32)."""
    html = _html()
    assert "function cutD(d,R){" in html
    assert "e.setAttribute('d',cutD(d0,R));" in html                 # cut…
    assert "e.setAttribute('d',d0); e.removeAttribute('data-d0');" in html   # …and restored
    for gone in ("'mask','url(#alto-fade-mask)'", "'clip-path','url(#alto-fade-mask)'",
                 "'mask','url(#alto-hover-mask)'", "'clip-path','url(#alto-hover-mask)'"):
        assert gone not in html


def test_hovered_cards_grow_by_zoom_not_transform():
    html = _html()
    assert "transform: none;   /* D-GRID: enlarged by a zoom ramp" in html
    assert "var HK=1.08, HMS=160;" in html


def test_arrow_keys_follow_structure_then_reading_order_then_alignment():
    html = _html()
    f = html[html.index("  function focusNeighbor(dir){"):]
    f = f[:f.index("    if(best) enterFocus(best);")]
    t = f.index("if(vert && tree){")                      # a tree: within the branch
    k = f.index("best=kidsBelow() || aligned(all.filter(inScope),true,1);")
    h = f.index("if(!best && sc) best=sc.id;")           # …else up to the branch's head
    r = f.index("var seq=[].concat.apply([],ACT_SEQS)")  # a flowing page: reading order
    a = f.index("if(!best) best=aligned(all,vert,sg);")  # then straight ahead
    c = f.index("Math.abs(diff)>60")                     # then the compass
    assert t < k < h < r < a < c
    assert "e.preventDefault(); _hop(d, e.repeat);" in html      # one hop at a time


def test_only_faded_cards_hide_lines():
    html = _html()
    assert "if(focus) return !n.classList.contains('focused');" in html
    assert "return dimmed(c);" in html


def test_cut_boxes_come_from_layout_not_screen_coordinates():
    """Measured in Safari 26.6.2: a card's box run back through getScreenCTM
    from getBoundingClientRect landed 38px left and 190px below its layout
    position under the page's CSS zoom, so every mask/clip/cut placed from it
    (1.8.30-33) missed the cards. The line layer's units are the world's
    layout px; the boxes are taken there."""
    html = _html()
    g = html[html.index("function holes(svg,faded){"):]
    g = g[:g.index("function inside(x,y,R){")]
    assert "n.offsetLeft+c.offsetLeft" in g and "n.offsetTop+c.offsetTop" in g
    assert "getScreenCTM()" not in g and "getBoundingClientRect" not in g
