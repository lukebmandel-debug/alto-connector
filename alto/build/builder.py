"""Build orchestrator: Brief + nodes + connections → verified timeline HTML."""
from __future__ import annotations

import json
from pathlib import Path

from .brief import Brief, Node, Act, Axis, AxisValue, Entity, Relation, Section, \
    validate_brief, validate_nodes
from .blocks import timeline_blocks, connections_block
from .emit import emit
from .layout import assign_columns, resolve, mobile_grid
from .sanitize import sanitize_brief
from ..engine import template as engine_template
from .verify import verify_data, verify_output, VerifyError


def load_brief(d: dict) -> tuple[Brief, list[Node], list]:
    """Parse the JSON build-brief bundle {brief, nodes, connections}."""
    bd = dict(d.get("brief") or {})
    bd["acts"] = [Act(**a) for a in bd.get("acts", [])]
    bd["entities"] = [
        Entity(**{**e, "sections": [Section(**s) for s in e.get("sections", [])]})
        for e in bd.get("entities", [])]
    bd["axes"] = [
        Axis(label=ax["label"], singular=ax["singular"],
             values=[AxisValue(**{**v, "sections": [Section(**s) for s in v.get("sections", [])]})
                     for v in ax.get("values", [])])
        for ax in bd.get("axes", [])]
    bd["relations"] = [Relation(**r) for r in bd.get("relations", [])]
    brief = Brief(**bd)
    nodes = [
        Node(**{**n, "sections": [Section(**s) for s in n.get("sections", [])]})
        for n in d.get("nodes", [])]
    connections = d.get("connections", [])
    return brief, nodes, connections


def run_layout(brief: Brief, nodes: list[Node]):
    """Column assignment + baseY resolution + mobile grid. Returns layout info."""
    assign_columns(nodes, brief.columns)
    positions, heights, world_h, report = resolve(nodes, brief.columns,
                                                  len(brief.acts))
    mgrid, mobile_h = mobile_grid(nodes, brief.columns)
    return positions, heights, world_h, mgrid, mobile_h, report


def build_timeline(brief: Brief, nodes: list[Node], connections: list,
                   *, reports_href: str = None) -> tuple[str, dict]:
    """Returns (html, report). Raises VerifyError/BriefError on any failure."""
    warnings = validate_brief(brief)
    warnings += validate_nodes(brief, nodes)

    # Validation first (it reads raw values and fills defaults), then make the
    # content inert. Everything downstream of here — blocks.py, emit, the
    # engine's innerHTML sinks — may assume text is already escaped.
    sanitize_brief(brief, nodes)

    assign_columns(nodes, brief.columns)
    failures = verify_data(brief, nodes, connections)
    if failures:
        raise VerifyError(failures)

    positions, heights, world_h, mgrid, mobile_h, layout_report = \
        run_layout(brief, nodes)

    regions, tokens = timeline_blocks(
        brief, nodes, positions, heights, mgrid, mobile_h,
        reports_href=reports_href)
    regions["connections"] = connections_block(connections)

    template = engine_template("timeline_template.html")
    html = emit(template, regions, tokens)

    failures = verify_output(html)
    if failures:
        raise VerifyError(failures)

    report = {
        "warnings": warnings,
        "layout": layout_report,
        "bytes": len(html.encode("utf-8")),
        "nodes": len(nodes),
        "connections": len(connections),
    }
    return html, report


def build_from_file(path: str) -> tuple[str, dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    brief, nodes, connections = load_brief(d)
    return build_timeline(brief, nodes, connections)
