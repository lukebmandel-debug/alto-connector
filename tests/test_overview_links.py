"""Overview deep links: showDetail() anchors become engine chip markup for live
nodes, and are demoted to plain text (with a warning) for unknown ids."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.sanitize import clean_overview, sanitize_brief  # noqa: E402
from alto.build.verify import verify_output  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
CHIP = ('<span class="ov-node-link"><button class="ov-node-btn" '
        "onclick=\"showDetail('node','{}')\"></button>")


def _build(overview):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["overview_html"] = overview
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)


def test_showdetail_anchor_rewrites_to_engine_chip():
    html, _ = _build(
        '<p>See <a href="#" onclick="showDetail(\'node\',\'carbolic\')">'
        'Carbolic</a>.</p>')
    assert CHIP.format("carbolic") in html
    assert "function initOverviewNavLinks(){" in html


def test_unknown_node_id_demotes_to_text_and_warns():
    html, report = _build(
        '<p>See <a href="#" onclick="showDetail(\'node\',\'ghost\')">Ghost</a>.</p>')
    assert "showDetail('node','ghost')" not in html
    assert "Ghost" in html                       # text kept as prose
    assert any("unknown node" in w for w in report["warnings"])


def test_return_false_and_javascript_href_variants_rewrite():
    out, warnings = clean_overview(
        "<a onclick=\"showDetail('node','carbolic'); return false;\">a</a>"
        "<a href=\"javascript:showDetail('node','hamer')\">b</a>",
        {"carbolic", "hamer"})
    assert CHIP.format("carbolic") in out
    assert CHIP.format("hamer") in out
    assert warnings == []


def test_non_showdetail_onclick_still_stripped():
    out, _ = clean_overview(
        '<a onclick="window.x=1" href="https://example.test">x</a>', {"carbolic"})
    assert "onclick" not in out
    assert 'href="https://example.test"' in out


def test_verify_output_fails_when_chip_missing():
    failures = verify_output("<html>no chip here</html>", deeplink_ids=["carbolic"])
    assert any("did not survive" in f for f in failures)


def test_sanitize_idempotent_with_links():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    d["brief"]["overview_html"] = (
        '<p><a href="#" onclick="showDetail(\'node\',\'carbolic\')">C</a></p>')
    brief, nodes, conns = load_brief(d)
    w1 = sanitize_brief(brief, nodes)
    first = brief.overview_html
    w2 = sanitize_brief(brief, nodes)            # second call is a no-op
    assert brief.overview_html == first
    assert CHIP.format("carbolic") in first
    assert w1 == w2
