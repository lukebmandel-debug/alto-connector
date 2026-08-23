"""Printing an outline gives you an outline.

The engine's "main timeline" print lays every node out as a card on a vertical
spine — right for a sequence, wrong for a containment tree. On paper a concept
outline wants the outline itself: nesting, real outline numerals, the rule under
each heading and the authority beside it.

`ACT_SEQS` / `NODES` / `PHASE_META` / `ENVS` are module-scoped in the frozen
engine, so a builder-side override is impossible; a two-line engine patch hands
them to a renderer this repo controls. The patch is a permanent guard that
no-ops when a page carries no outline data.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
OUTLINE = ROOT / "samples" / "outline_brief.json"


def _build(path):
    return build_timeline(*load_brief(
        json.loads(Path(path).read_text(encoding="utf-8"))))


def _renderer_src(html: str) -> str:
    """The emitted renderer body. Split on the next top-level marker rather
    than on '};', which occurs inside the function itself."""
    after = html.split("window._altoPrintOutline = function", 1)[1]
    return after.split("</script>", 1)[0]


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_the_outline_print_renderer_ships_for_an_outline():
    html, _ = _build(OUTLINE)
    assert "window._altoPrintOutline = function" in html
    assert ".print-ol-row{display:flex" in html


def test_a_linear_build_ships_the_guard_but_not_the_renderer():
    html, _ = _build(SAMPLE)
    assert "if(window._ALTO_OUTLINE && window._altoPrintOutline)" in html
    assert "window._altoPrintOutline = function" not in html
    assert ".print-ol-row" not in html


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_the_print_heading_follows_the_mode():
    outline, _ = _build(OUTLINE)
    linear, _ = _build(SAMPLE)
    assert "— Outline</h1>" in outline
    assert "— Timeline</h1>" in linear


def test_the_print_patch_is_registered_and_anchored():
    names = {p["name"] for p in PATCHES}
    assert "outline-prints-as-an-outline" in names
    entry = next(p for p in PATCHES if p["name"] == "outline-prints-as-an-outline")
    assert entry["count"] == 1          # a moved anchor must fail the build


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_indentation_and_numerals_come_from_the_tree():
    """The renderer reads _ALTO_OUTLINE, so the printed nesting is the same
    tree the canvas and the detail pages use — never a second copy."""
    html, _ = _build(OUTLINE)
    src = _renderer_src(html)
    assert "O.label[id]" in src            # the numeral for this level
    assert "O.kids[id]" in src             # children, recursed
    assert "--lvl:' + depth" in src        # depth drives the indent


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_authority_is_printed_beside_the_rule_it_supports():
    html, _ = _build(OUTLINE)
    src = _renderer_src(html)
    assert "n.envs" in src and "ENVS[e]" in src
    assert "print-ol-cite" in src


@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_nothing_is_invented_for_an_empty_concept():
    """'With what is given': a concept the student wrote nothing under still
    gets its heading, and no placeholder prose."""
    html, _ = _build(OUTLINE)
    src = _renderer_src(html)
    assert "if(n.desc)" in src             # the one-liner is conditional
    assert "if(cites.length)" in src       # so is the citation line


def test_the_search_box_says_search_everywhere():
    """Three surfaces had three different placeholders, and the desktop
    timeline's still named the reference build's own subject matter."""
    from alto.build.pages import build_home
    tl, _ = _build(SAMPLE)
    assert tl.count('placeholder="Search"') == 2      # desktop + mobile
    assert "scenes, characters, themes" not in tl
    assert 'placeholder="Search…"' not in tl
    home = build_home([{"name": "P", "courses": []}])
    assert 'placeholder="Search"' in home
    assert "Search all of Alto" not in home


def test_the_home_placeholder_swap_fails_loudly_if_the_template_moves():
    from alto.build.pages import _rep, PageError
    with pytest.raises(PageError, match="home search placeholder"):
        _rep("<html>nothing here</html>", 'placeholder="Search all of Alto"',
             'placeholder="Search"', 1, "home search placeholder")
