"""v1.3.0: coverage filter (Part E), filter redundancy warnings (Part E), and
gap-radar badges on the doctrine nav chips (Part D)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.brief import validate_brief  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build(mutate=None):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if mutate:
        mutate(d)
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)


def test_coverage_filter_assigns_solid_thin():
    html, _ = _build(lambda d: d["brief"].__setitem__(
        "filters", [{"id": "cov", "label": "Coverage", "source": "coverage"}]))
    assert "era:'solid'" in html and "era:'thin'" in html
    from panel import slot_ids
    assert set(slot_ids(html, "era")) == {"solid", "thin"}
    # no redundancy warning for a cross-cutting filter
    _, rep = _build(lambda d: d["brief"].__setitem__(
        "filters", [{"id": "cov", "label": "Coverage", "source": "coverage"}]))
    assert not any("repeats" in w for w in rep["warnings"])


def test_redundancy_warning_for_acts_and_entity_filters():
    _, rep_acts = _build(lambda d: d["brief"].__setitem__(
        "filters", [{"id": "u", "label": "Unit", "source": "acts"}]))
    assert any("repeats the act bands" in w for w in rep_acts["warnings"])
    _, rep_ent = _build(lambda d: d["brief"].__setitem__(
        "filters", [{"id": "dz", "label": "Doctrine", "source": "entity"}]))
    assert any("repeats the nav chips" in w for w in rep_ent["warnings"])


def test_entity_filter_replace_nav_not_flagged():
    # a filter-only entity dimension isn't "repeating the nav chips" — it
    # replaces them — so no redundancy warning.
    _, rep = _build(lambda d: d["brief"].__setitem__(
        "filters", [{"id": "dz", "label": "Doctrine", "source": "entity",
                     "replace_nav": True}]))
    assert not any("repeats" in w for w in rep["warnings"])


def test_gap_radar_badge_on_nav_chips():
    html, _ = _build()
    # each doctrine nav chip carries a member-count badge; thin ones are marked
    assert 'class="nav-chip-count' in html
    assert 'nav-chip-count thin"' in html   # the sample has a ≤2-member doctrine
