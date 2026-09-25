"""Build orchestrator: Brief + nodes + connections → verified timeline HTML."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .brief import Brief, Node, Act, Axis, AxisValue, Entity, FilterSpec, \
    FilterValue, Relation, Section, validate_brief, validate_nodes
from .blocks import timeline_blocks, connections_block
JUMP_WITHOUT_REASON = 3   # places a line may skip before it needs a stated reason
from .emit import emit
from .engine_patches import apply_patches
from .layout import assign_columns, resolve, mobile_grid, \
    outline_order_and_columns, outline_spokes
from .sanitize import sanitize_brief, sanitize_connections
from ..engine import template as engine_template
from .verify import verify_data, verify_output, verify_scripts, VerifyError


def load_brief(d: dict) -> tuple[Brief, list[Node], list]:
    """Parse the JSON build-brief bundle {brief, nodes, connections}."""
    bd = dict(d.get("brief") or {})
    bd["acts"] = [Act(**a) for a in bd.get("acts", [])]
    bd["entities"] = [
        Entity(**{**e, "sections": [Section(**s) for s in e.get("sections", [])]})
        for e in bd.get("entities", [])]
    bd["axes"] = [
        Axis(label=ax["label"], singular=ax["singular"],
             hide_nav=bool(ax.get("hide_nav", False)),
             values=[AxisValue(**{**v, "sections": [Section(**s) for s in v.get("sections", [])]})
                     for v in ax.get("values", [])])
        for ax in bd.get("axes", [])]
    bd["relations"] = [Relation(**r) for r in bd.get("relations", [])]
    bd["filters"] = [
        FilterSpec(**{**f, "values": [FilterValue(**v)
                                      for v in f.get("values", [])]})
        for f in bd.get("filters", [])]
    brief = Brief(**bd)
    nodes = [
        Node(**{**n, "sections": [Section(**s) for s in n.get("sections", [])]})
        for n in d.get("nodes", [])]
    connections = d.get("connections", [])
    return brief, nodes, connections


def place(brief: Brief, nodes: list[Node]) -> None:
    """Order and column-assign nodes for the brief's mode. Idempotent."""
    if brief.mode == "outline":
        outline_order_and_columns(nodes, brief.columns)
    else:
        assign_columns(nodes, brief.columns)


def run_layout(brief: Brief, nodes: list[Node]):
    """Column assignment + baseY resolution + mobile grid. Returns layout info."""
    place(brief, nodes)
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
    # engine's innerHTML sinks — may assume text is already escaped. Sanitize
    # also rewrites overview deep links and reports unknown-node demotions.
    warnings += sanitize_brief(brief, nodes)
    connections, _cw = sanitize_connections(brief, nodes, connections)
    warnings += _cw

    # A line between neighbours is continuity and needs no explaining. One that
    # jumps well ahead is a claim about the material, so it should carry its
    # reason (the fourth element), which the node's page shows as "How they
    # connect".
    _pos = {n.id: i for i, n in enumerate(nodes)}
    for c in connections:
        if len(c) >= 3 and c[0] in _pos and c[1] in _pos:
            gap = _pos[c[1]] - _pos[c[0]]
            if gap > JUMP_WITHOUT_REASON and not (len(c) == 4 and c[3].strip()):
                warnings.append(
                    f"connection {c[0]} → {c[1]} jumps {gap} places ahead with no "
                    "explanation — add how they connect, or redraw the line")

    place(brief, nodes)
    # The tree is the single source of truth for structure, so the parent→child
    # spokes are derived here rather than authored — an authored copy could
    # disagree with `parent` and nothing would catch it.
    if brief.mode == "outline":
        connections = outline_spokes(nodes, connections)
    failures = verify_data(brief, nodes, connections)
    if failures:
        raise VerifyError(failures)

    positions, heights, world_h, mgrid, mobile_h, layout_report = \
        run_layout(brief, nodes)

    regions, tokens = timeline_blocks(
        brief, nodes, positions, heights, mgrid, mobile_h,
        reports_href=reports_href, connections=connections,
        warnings=warnings)
    regions["connections"] = connections_block(connections)

    template = engine_template("timeline_template.html")
    html = apply_patches(emit(template, regions, tokens))

    # Deep links that survived sanitize (unknown ones were demoted) must reach
    # the output as engine chip markup — assert each one did.
    deeplink_ids = re.findall(
        r"onclick=\"showDetail\('node','([a-z][a-z0-9-]{0,47})'\)\"",
        brief.overview_html or "")
    failures = verify_output(html, deeplink_ids)
    if failures:
        raise VerifyError(failures)

    # Parse-gate every emitted script: a SyntaxError must abort, not ship silent.
    js_failures, js_warnings = verify_scripts(html, "timeline")
    if js_failures:
        raise VerifyError(js_failures)
    warnings += js_warnings

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
