"""Doctrine/entity detail pages get a never-empty auto-body (member roster +
relations) emitted from the student's own material — no template edit."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)


def test_autobody_function_and_wiring_emitted():
    html, _ = _build()
    assert "function _altoDoctrineBody(id, kind, have){" in html
    # desktop (id) and mobile (targetId) section-builders of every sub-chip kind
    # append it, telling it which sections the author already wrote
    for kind in ("char", "env", "theme"):
        assert f"_altoDoctrineBody(id,'{kind}'," in html
        assert f"_altoDoctrineBody(targetId,'{kind}'," in html
    assert "function _altoOrder(secs){" in html   # nodes read before the steps between them
    # the delegated row-click binding ships
    assert "_altoDocRowBound" in html


def test_rel_labels_and_node_noun_emitted():
    html, _ = _build()
    # used relations carry labels (quoted keys); node noun for the roster heading
    assert "var REL_LABELS={" in html
    assert "'cites':'cites'" in html
    assert "var _ALTO_NODE_NOUN=" in html
