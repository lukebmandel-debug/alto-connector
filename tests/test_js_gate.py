"""JS parse gate: every emitted <script> and onclick handler is syntax-checked,
so a SyntaxError can never ship as a "0 warnings" build (the blank-canvas bug)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import verify as V  # noqa: E402
from alto.build import blocks  # noqa: E402
from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.verify import verify_scripts, find_node, VerifyError  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"

requires_node = pytest.mark.skipif(
    find_node() is None, reason="node not installed — gate degrades to a warning")


def _build(mutate=None):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if mutate:
        mutate(d)
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)


@requires_node
def test_sample_build_passes_js_gate():
    html, _ = _build()
    assert verify_scripts(html, "timeline") == ([], [])


@requires_node
def test_inline_syntax_error_fails():
    failures, _ = verify_scripts("<script>let x = ;</script>", "t")
    assert failures and "SyntaxError" in failures[0]


@requires_node
def test_src_and_json_scripts_skipped():
    # src → external; application/json & importmap → not JS. All skipped, so
    # their deliberately-invalid-JS bodies produce no failure.
    html = ('<script src="x.js">garbage ((( not js</script>'
            '<script type="application/json">{"a": }</script>'
            '<script type="importmap">{ "imports": }</script>')
    assert verify_scripts(html, "t") == ([], [])


@requires_node
def test_module_scripts_checked_as_modules():
    ok, _ = verify_scripts('<script type="module">export const a = 1;</script>', "t")
    assert ok == []
    bad, _ = verify_scripts('<script type="module">export const = ;</script>', "t")
    assert bad


@requires_node
def test_bad_onclick_handler_fails():
    # a malformed showDetail() — exactly what a broken overview rewrite emits
    failures, _ = verify_scripts("<div onclick=\"showDetail('node',\">x</div>", "t")
    assert failures and "onclick" in failures[0]


@requires_node
def test_onclick_inside_script_string_is_not_flagged():
    # onclick="..." text inside a JS string literal is assembled into HTML at
    # runtime; the \' is correct string escaping, not a DOM attribute. The script
    # body is checked whole (and is valid); the substring must not be re-scanned.
    html = "<script>var h = '<b onclick=\"f(\\'g\\')\">'; </script>"
    assert verify_scripts(html, "t") == ([], [])


def test_missing_node_degrades_to_warning(monkeypatch):
    monkeypatch.setattr(V, "find_node", lambda: None)
    failures, warnings = V.verify_scripts("<script>let x = ;</script>", "t")
    assert failures == []
    assert warnings and "node not found" in warnings[0]


def test_build_still_succeeds_without_node(monkeypatch):
    monkeypatch.setattr(V, "find_node", lambda: None)
    html, report = _build()
    assert html
    assert any("node not found" in w for w in report["warnings"])


@requires_node
def test_build_aborts_on_script_failure(monkeypatch):
    # inject a SyntaxError into an emitted region (FILTER_GLUE ships only with
    # filters) and confirm the build refuses to produce it
    monkeypatch.setattr(blocks, "FILTER_GLUE", "\nlet = ;")

    def add_filter(d):
        d["brief"]["filters"] = [
            {"id": "court", "label": "Court", "source": "axis1"}]

    with pytest.raises(VerifyError):
        _build(add_filter)
