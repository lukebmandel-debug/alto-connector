"""Outline mode: concept-first hub-and-spoke, case chips, and deep links in
detail-page text.

Three behaviours, all built on the existing engine (nothing here touches
`engine/`):

  * `Axis.hide_nav` keeps an axis's chips on the cards and its detail pages
    reachable while removing it from the nav bar, drawer and legend — for a
    course's cases, which are far too many for a nav row.
  * a hide_nav axis labels its chips with the value's name instead of falling
    back to a glyph, since a row of identical diamonds names nothing.
  * `showDetail()` links inside `Section.t` become `alto-link` spans resolved
    by id, with one delegated handler that works on desktop, mobile and peek.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.sanitize import clean_linked_markup  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
OUTLINE = ROOT / "samples" / "outline_brief.json"


def _build(path=SAMPLE, mutate=None):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if mutate:
        mutate(d)
    return build_timeline(*load_brief(d))


def _nav(html):
    """Just the nav bar, so a match can't come from the canvas or a detail page.
    blocks.py closes the block with a literal '\\n  </div>'."""
    assert '<div id="nav">' in html
    return html.split('<div id="nav">', 1)[1].split("\n  </div>", 1)[0]


# ── Axis.hide_nav ───────────────────────────────────────────────────────────

def test_hide_nav_removes_the_axis_from_the_navigation_chrome():
    html, _ = _build(mutate=lambda d: d["brief"]["axes"][0].__setitem__(
        "hide_nav", True))
    assert "showDetail('env'" not in _nav(html)
    assert "background:var(--env-color);border-radius:2px" not in html  # legend dot
    assert 'data-sd-type=\\"env\\"' not in html                          # drawer row


def test_hide_nav_keeps_the_card_chips_and_the_detail_pages():
    html, _ = _build(mutate=lambda d: d["brief"]["axes"][0].__setitem__(
        "hide_nav", True))
    assert 'envs:["ny"]' in html          # still on the node, so the chip renders
    assert "const ENVS" in html           # registry kept, so the page still opens


def test_hide_nav_defaults_off_and_leaves_the_nav_alone():
    html, _ = _build()
    assert "showDetail('env'" in _nav(html)


def test_hide_nav_survives_the_json_loader():
    """Axis is built with named kwargs in load_brief, so a new field is easy to
    drop on the floor."""
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["axes"][0]["hide_nav"] = True
    assert load_brief(d)[0].axes[0].hide_nav is True


def test_replace_nav_still_strips_card_chips():
    """hide_nav is additive — it must not weaken replace_nav, whose whole point
    is that a filter-only axis shows no chips at all."""
    html, _ = _build(mutate=lambda d: d["brief"].__setitem__(
        "filters", [{"id": "f", "label": "Court", "source": "axis1",
                     "replace_nav": True}]))
    assert "envs:[]" in html
    assert 'envs:["ny"]' not in html


# ── named chips on a hide_nav axis ──────────────────────────────────────────

def test_hide_nav_axis_labels_its_chips_with_the_value_name():
    html, _ = _build(mutate=lambda d: d["brief"]["axes"][0].__setitem__(
        "hide_nav", True))
    env_sym = html.split("const ENV_SYM={", 1)[1].split("};", 1)[0]
    assert "New York" in env_sym
    assert ".esym-btn,.tsym-btn{max-width:" in html      # so it can't blow out the card


def test_a_navigable_axis_still_uses_glyphs():
    html, _ = _build()
    env_sym = html.split("const ENV_SYM={", 1)[1].split("};", 1)[0]
    assert "New York" not in env_sym


# ── deep links in Section.t ─────────────────────────────────────────────────

LINK = "<a href=\"#\" onclick=\"showDetail('{t}','{i}')\">{x}</a>"


def _with_section(text):
    def mutate(d):
        d["nodes"][0]["sections"].append({"h": "See also", "t": text})
    return _build(mutate=mutate)


def test_case_link_in_section_text_becomes_an_alto_link():
    html, _ = _with_section("Compare " + LINK.format(t="env", i="ny", x="New York"))
    assert 'class="alto-link" data-sd-type="env" data-sd-id="ny"' in html


def test_concept_link_in_section_text_resolves_to_a_node():
    html, _ = _with_section("See " + LINK.format(t="node", i="hamer", x="Hamer"))
    assert 'data-sd-type="node" data-sd-id="hamer"' in html


def test_a_mistyped_link_is_corrected_by_id_and_warns():
    """Nobody remembers that a concept is 'node' and a case is 'env' across a
    whole outline, so the id decides and the authored type is advisory."""
    html, report = _with_section(LINK.format(t="node", i="eng", x="England"))
    assert 'data-sd-type="env" data-sd-id="eng"' in html
    assert any("resolves as 'env'" in w for w in report["warnings"])


def test_an_unknown_id_demotes_to_prose_and_warns():
    html, report = _with_section("See " + LINK.format(t="node", i="ghost", x="Ghost"))
    assert "data-sd-id=\"ghost\"" not in html
    assert "Ghost" in html                                  # text kept
    assert any("unknown id 'ghost'" in w for w in report["warnings"])


def test_the_link_ends_where_the_anchor_ends():
    """Regression: the </a> handler only recognised overview mode, so in detail
    text the span stayed open and swallowed the rest of the paragraph."""
    out, _ = clean_linked_markup(
        "Contrast " + LINK.format(t="env", i="hamer", x="Hamer") + ", then stop.",
        {"hamer": "env"})
    assert out.count("<span") == 1 and out.count("</span>") == 1
    assert ">Hamer</span>" in out
    assert out.endswith(", then stop.")


def test_a_plain_link_is_still_a_plain_link():
    out, warnings = clean_linked_markup(
        '<p>See <a href="https://example.test/x">docs</a>.</p>', {"a": "node"})
    assert 'href="https://example.test/x"' in out
    assert "alto-link" not in out and not warnings


def test_the_delegated_handler_and_its_guard_ship():
    html, _ = _with_section(LINK.format(t="env", i="ny", x="New York"))
    assert "_altoLinkBound" in html
    assert ".alto-link[data-sd-id]" in html


def test_node_desc_stays_plain_text():
    """desc renders escaped on the card but raw in the detail fallback, so it
    cannot carry markup — the card's chip is the link there."""
    html, _ = _build(mutate=lambda d: d["nodes"][0].__setitem__(
        "desc", "Compare " + LINK.format(t="env", i="ny", x="New York")))
    assert 'class="alto-link"' not in html
    src = html.split("NODES_SRC", 1)[1][:4000]
    assert "<a " not in src and "New York" in src      # anchor stripped, text kept


# ── the outline sample, and the linear path it must not disturb ─────────────

@pytest.mark.skipif(not OUTLINE.exists(), reason="outline sample not present")
def test_the_outline_sample_builds_hub_and_spoke():
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    html, report = build_timeline(*load_brief(d))
    assert report["layout"]["moved_on_recheck"] == []       # resolver at fixpoint
    # The only expected warning: the structural spine touches every concept, so
    # a filter on it would light everything — the build drops that chip.
    assert [w for w in report["warnings"]] == [
        "line filter 'Contains': matches every node, so filtering by it "
        "changes nothing \u2014 chip dropped"]

    # The brief declares a tree, not a layout: no authored columns, and the
    # parent→child spokes are generated at build.
    assert not any("col" in n for n in d["nodes"])
    assert not any(c[2] == "spine" for c in d["connections"])

    brief, nodes, conns = load_brief(d)
    from alto.build.builder import place
    from alto.build.layout import outline_spokes
    place(brief, nodes)
    children_of = {}
    for n in nodes:
        if n.parent:
            children_of.setdefault(n.parent, []).append(n.id)

    # a concept that contains others is a hub in the centre column; a concept
    # that contains none sits out to one side
    for n in nodes:
        if children_of.get(n.id):
            assert n.col == "center", n.id
        else:
            assert n.col != "center", n.id

    # one root per unit band, and the DFS puts it first in its band
    roots = [n for n in nodes if not n.parent]
    assert len(roots) == len(brief.acts)
    assert {r.act for r in roots} == set(range(len(brief.acts)))
    for act_i in range(len(brief.acts)):
        assert next(n for n in nodes if n.act == act_i).parent == ""

    # one generated spoke per child, and the authored cross-links survive
    spokes = outline_spokes(nodes, conns)
    derived = [c for c in spokes if c[2] == "spine"]
    assert len(derived) == sum(1 for n in nodes if n.parent)
    assert all(c in spokes for c in conns)

    # cases are on the cards but nowhere in the nav
    assert "showDetail('env'" not in _nav(html)
    assert "Hamer v. Sidway" in html


def test_the_linear_sample_gains_no_outline_machinery():
    """Every outline path is opt-in; a brief that uses none of it must not pay
    for any of it."""
    html, _ = _build()
    # Not the drawer's data-sd-* attributes — those are ordinary axis chrome.
    for marker in ("alto-link", "_altoLinkBound"):
        assert marker not in html, f"{marker} shipped in a brief that has no links"
