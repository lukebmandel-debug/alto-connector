"""Relation line key: labels + line-color swatches in the desktop nav and mobile
drawer, plus the --rel-* CSS vars that actually resolve the connection colors."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build(relations=None, connections=None):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if relations is not None:
        d["brief"]["relations"] = relations
    if connections is not None:
        d["connections"] = connections
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)


def test_rel_css_vars_emitted_for_line_rendering():
    # regression for the latent bug: without --rel-* the engine's _lineResolveVar
    # put a literal var(--rel-…) into the SVG stroke and skipped contrast adapt.
    html, _ = _build()          # sample: cites #a78bfa, limits #f43f5e
    assert "--rel-cites:#a78bfa;" in html
    assert "--rel-limits:#f43f5e;" in html


def test_used_relation_gets_nav_key_and_drawer_row():
    html, _ = _build()
    # interactive line-key chips carry data-rel-key + a live edge count
    assert 'class="nav-btn line-key-btn" data-rel-key="cites"' in html      # desktop
    assert 'background:var(--rel-cites)' in html                            # swatch color
    assert 'drawer-btn line-key-btn" data-rel-key="cites"' in html          # mobile
    assert 'class="line-key-count">1</span>' in html                        # cites used once
    assert "function isolateRelation" in html                              # the isolate glue
    # The desktop chips now sit with the filter groups (they filter nodes too,
    # not just line tubes); the mobile drawer keeps its own "Lines" section.
    assert 'nav-group-label">Filter \u00b7 Lines</span>' in html
    assert 'drawer-section-label">Lines</div>' in html


def test_labeled_spine_appears_last_and_neutral():
    html, _ = _build()          # spine label "leads to", used by the sample
    assert 'data-rel-key="spine"' in html
    assert 'background:var(--line-flow)' in html
    assert "--rel-spine" not in html


def test_unused_relation_omitted_from_key():
    rels = [{"key": "spine", "label": "leads to"},
            {"key": "cites", "label": "Cites", "color": "#a78bfa"},
            {"key": "distinguishes", "label": "Distinguishes", "color": "#22d3ee"}]
    conns = [["lucy-v-zehmer", "carbolic", "spine"],
             ["carbolic", "hamer", "cites"]]
    html, _ = _build(relations=rels, connections=conns)
    assert 'data-rel-key="cites"' in html         # used → in the key
    assert "Distinguishes" not in html            # unused → absent from the key (incl. REL_LABELS)
    assert "--rel-distinguishes:#22d3ee;" in html  # var still defined (harmless)


def test_no_colored_relations_no_legend_artifacts():
    # an all-spine timeline: neutral thread is self-evident, no key, zero bytes
    rels = [{"key": "spine", "label": "leads to"}]
    conns = [["lucy-v-zehmer", "carbolic", "spine"],
             ["carbolic", "hamer", "spine"],
             ["hamer", "kirksey", "spine"],
             ["kirksey", "ricketts", "spine"],
             ["ricketts", "feinberg", "spine"]]
    html, _ = _build(relations=rels, connections=conns)
    assert 'nav-group-label">Lines</span>' not in html
    assert 'drawer-section-label">Lines</div>' not in html
    assert "--rel-" not in html
