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
    outline_order_and_columns, outline_spokes, outline_tree, outline_plan, \
    placement_check, outline_has_categories, line_crossings, TREE
from .brief import COL_SETS
from .estimate import card_height
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
             filter=ax.get("filter"), sources=list(ax.get("sources") or []),
             cite_link=dict(ax.get("cite_link") or {}),
             nav_label=ax.get("nav_label") or "",
             index_blurb=list(ax.get("index_blurb") or []),
             index_sections=[Section(**s) for s in ax.get("index_sections") or []],
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


def consent_source_docs(doc: dict) -> list:
    """The consent manifest's entries that carry an id: the source map node
    and sub-chip `sources` point into (ALTO-011), and the local copies
    detail_extras.local_sources opens. Every path that builds a stored
    timeline fills Brief.source_docs from here — the publish rebuild once
    did not, and shipped every private page without its source links."""
    out = []
    for s in (doc.get("consent") or {}).get("sources") or []:
        if isinstance(s, dict) and s.get("id"):
            out.append({"id": s["id"], "name": s.get("name") or s["id"],
                        "url": s.get("url") or "", "local": s.get("local") or ""})
    return out


def stored_brief(doc: dict) -> dict:
    """A stored timeline's brief as the build must see it: with the source
    map filled in from the consent manifest unless the brief carries one."""
    brief = dict(doc["brief"])
    if not brief.get("source_docs"):
        brief["source_docs"] = consent_source_docs(doc)
    return brief


def place(brief: Brief, nodes: list[Node]) -> None:
    """Order and column-assign nodes for the brief's mode. Idempotent."""
    if brief.mode == "outline":
        outline_order_and_columns(nodes, brief.columns, brief.placement)
    else:
        assign_columns(nodes, brief.columns)


def run_layout(brief: Brief, nodes: list[Node], connections: list = None):
    """Column assignment + desktop arrangement + mobile grid. Returns layout
    info; report["layout"] says which arrangement the desktop map uses.

    An outline can be a tree or flow (brief.layout). "auto" takes the tree
    when the outline has real categories to show and the tree's lines cross
    no more often than flow's, or when the author has placed cards (only a
    tree can honour that); the counts are in report["line_crossings"].
    `col` drives the mobile grid either way."""
    place(brief, nodes)
    flow_parent = ({n.id: n.parent for n in nodes if n.parent}
                   if brief.mode == "outline" else None)
    positions, heights, world_h, report = resolve(nodes, brief.columns,
                                                  len(brief.acts), flow_parent)
    report["layout"] = "flow"
    if brief.mode == "outline" and brief.layout != "flow":
        plan = outline_plan(nodes, len(brief.acts), brief.placement,
                            brief.tree_lines)
        th = {n.id: card_height(n.desc, n.title, plan["w"].get(n.id, TREE["CARD_W"]))
              for n in nodes}
        ty, tx, tworld = outline_tree(nodes, len(brief.acts), th, plan=plan)
        edges = [(c[0], c[1]) for c in outline_spokes(nodes, connections or [])
                 if c[0] in ty and c[1] in ty]
        colx = COL_SETS[brief.columns]
        fx = {n.id: colx[n.col] for n in nodes}
        crossings = {"tree": line_crossings(edges, tx, ty, th, True),
                     "flow": line_crossings(edges, fx, positions, heights, False)}
        categories = outline_has_categories(nodes)
        placed = any(set(h) - {"order"} for h in (brief.placement or {}).values())
        if brief.layout == "tree" or placed or (
                categories and crossings["tree"] <= crossings["flow"]):
            positions, heights, world_h = ty, th, tworld
            report = {"world_height": world_h, "moved_on_recheck": [],
                      "per_column": {}, "layout": "tree"}
            if brief.placement:
                check = placement_check(nodes, plan, ty, tx, th)
                report["placement"] = {"hinted": len(brief.placement),
                                       "warnings": plan["warnings"], **check}
        report["line_crossings"] = crossings
        report["categories"] = categories
    mgrid, mobile_h = mobile_grid(nodes, brief.columns)
    return positions, heights, world_h, mgrid, mobile_h, report


def _placement_warnings(pl: dict = None) -> list[str]:
    """What a placed layout got wrong, as plain sentences for the author."""
    if not pl:
        return []
    out = list(pl.get("warnings") or [])
    if pl.get("overlap_count"):
        pairs = ", ".join(f"{a}/{b}" for a, b in pl["overlaps"][:4])
        out.append(f"placement: {pl['overlap_count']} cards overlap ({pairs}"
                   f"{' …' if pl['overlap_count'] > 4 else ''}) — move one with "
                   "x, dx or dy, or float it")
    if pl.get("off_margin"):
        out.append("placement: " + ", ".join(pl["off_margin"][:4])
                   + " sit closer to the page edge than the margin — narrow or move")
    return out


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
        run_layout(brief, nodes, connections)
    warnings += _placement_warnings(layout_report.get("placement"))

    regions, tokens = timeline_blocks(
        brief, nodes, positions, heights, mgrid, mobile_h,
        reports_href=reports_href, connections=connections,
        warnings=warnings, tree=layout_report.get("layout") == "tree")
    regions["connections"] = connections_block(connections)

    template = engine_template("timeline_template.html")
    html = apply_patches(emit(template, regions, tokens))
    html = _add_tail(html, brief, nodes, warnings)

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


def _add_tail(html: str, brief: Brief, nodes: list, warnings=None) -> str:
    """Detail-page extras that must wrap showDetail last (back-to-previous,
    banner clearance, auto-linking), placed just before the page's closing
    body tag. Every page gets them: they were gated to outline and index
    pages only while private pages were stored uncompressed and Terrarium sat
    at the cap (see private_shell.MAX_PAGE_BYTES)."""
    from . import detail_extras as dx
    from .search import search_config
    table = dx.autolink_table(brief)
    # Sources with a copy on the author's computer (empty when none have one).
    local, local_warnings = dx.local_sources(brief)
    if warnings is not None:
        warnings += local_warnings
    tail = (local + "<script>window._ALTO_AUTOLINK="
            + json.dumps(table, ensure_ascii=False).replace("</", "<\\/")
            + ";</script>\n" + dx.AUTOLINK + "\n" + dx.BANNER_CLEARANCE
            + "\n" + dx.BACK_PREV + "\n" + search_config(brief)
            + "\n" + dx.edit_tile(brief) + dx.notes_trash(brief))
    at = html.rfind("</body>")
    if at < 0:
        raise VerifyError(["page has no </body> for the detail extras"])
    return html[:at] + tail + html[at:]


def build_from_file(path: str) -> tuple[str, dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    brief, nodes, connections = load_brief(d)
    return build_timeline(brief, nodes, connections)
