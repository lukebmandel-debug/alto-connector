"""End-to-end build tests over the sample brief."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_from_file, load_brief, build_timeline  # noqa: E402
from alto.build.single_file import bundle  # noqa: E402
from alto.build.verify import VerifyError  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def test_sample_builds():
    html, report = build_from_file(str(SAMPLE))
    assert report["nodes"] == 6
    assert report["layout"]["moved_on_recheck"] == []
    assert "Lucy v. Zehmer" in html
    assert "ALTO:" not in html
    assert "__ALTO_TOK_" not in html
    # user schema present
    assert "Facts" in html and "Holding" in html
    # engine intact
    assert "function initLayout(" in html


def test_sample_bundle():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    html, _ = build_timeline(brief, nodes, conns)
    offline = bundle(brief, html)
    assert "__altoSwap" in offline
    assert 'src="alto-cloud.js"' not in offline  # script tags stripped (comments may mention it)
    assert offline.count("__DOCS") >= 1


def test_bad_connection_rejected():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["connections"].append(["lucy-v-zehmer", "no-such-node", "spine"])
    brief, nodes, conns = load_brief(d)
    with pytest.raises(VerifyError, match="unknown target"):
        build_timeline(brief, nodes, conns)


def test_bad_relation_rejected():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["connections"].append(["lucy-v-zehmer", "hamer", "made-up-relation"])
    brief, nodes, conns = load_brief(d)
    with pytest.raises(VerifyError, match="not in vocabulary"):
        build_timeline(brief, nodes, conns)
