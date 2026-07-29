"""Build-brief data model — the validated object the interview produces.

Kept dependency-light (dataclasses + explicit validation) so the build library
runs anywhere; the MCP layer wraps this with its own schema. Follows the spec
(ALTO_CONNECTOR_INTERVIEW_SPEC.md): everything about the timeline's structure
is user-defined; §0 (closed knowledge container) is enforced at the tool layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Per-field ceilings. Without these a single oversized value produces a page no
# browser can open and can wedge the layout resolver long before any of the
# count-based quotas in mcp_server.py would trigger.
MAX_LEN = {
    "title": 300, "subject": 500, "label": 300, "short": 300, "tag": 200,
    "name": 200, "role": 500, "singular": 200, "node_noun": 100,
    "desc": 20_000, "section_h": 300, "section_t": 100_000,
    "overview_html": 200_000, "symbol_svg": 20_000, "owner": 300,
}
MAX_BRIEF_BYTES = 4_000_000
MAX_SECTIONS = 24


def _check_len(value, kind, what) -> str:
    limit = MAX_LEN[kind]
    s = value or ""
    if len(s) > limit:
        raise BriefError(
            f"{what}: {len(s)} characters exceeds the {limit}-character limit")
    return s

# A pleasant default palette assigned to entities/acts when colors are omitted.
PALETTE = ["#4a9eff", "#e8a87c", "#a78bfa", "#f43f5e", "#10b981", "#fb923c",
           "#94a3b8", "#7dd3fc", "#f472b6", "#a3e635", "#fbbf24", "#2dd4bf"]

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]

COL_SETS = {
    3: {"left": 450, "center": 850, "right": 1250},
    5: {"far-left": 210, "left": 450, "center": 850, "right": 1250,
        "far-right": 1490},
}


class BriefError(ValueError):
    pass


def _check_id(s, what):
    if not ID_RE.match(s or ""):
        raise BriefError(f"{what} id {s!r}: must be a lowercase slug "
                         "(a-z, 0-9, hyphens, ≤48 chars)")
    return s


def _check_hex(s, what, default):
    if s is None:
        return default
    if not HEX_RE.match(s):
        raise BriefError(f"{what}: color {s!r} is not #rrggbb")
    return s


@dataclass
class Section:
    h: str          # heading, user-defined (e.g. "Holding", "Why It Matters")
    t: str          # verbatim user-material text (may contain inline HTML)


@dataclass
class Entity:
    id: str
    name: str
    role: str = ""
    color: str = ""            # #rrggbb; auto-assigned when empty
    symbol_svg: str = ""       # inline SVG glyph; fallback glyph when empty
    sections: list[Section] = field(default_factory=list)   # entity detail page


@dataclass
class AxisValue:
    id: str
    name: str
    symbol_svg: str = ""
    color: str = ""
    role: str = ""
    sections: list[Section] = field(default_factory=list)


@dataclass
class Axis:
    """A filter axis mapped onto one of the engine's two extra slots."""
    label: str                 # plural, e.g. "Environments" / "Doctrines"
    singular: str              # e.g. "Environment"
    values: list[AxisValue] = field(default_factory=list)


@dataclass
class Act:
    label: str                 # band label, e.g. "ACT ONE — ARRIVAL"
    short: str = ""            # detail-page form, e.g. "Act One — Arrival"
    color: str = ""            # #rrggbb; band tint + numeral color


@dataclass
class Relation:
    key: str                   # connection vocabulary key, e.g. "overrules"
    label: str = ""
    color: str = ""            # #rrggbb; "spine" key always renders neutral


@dataclass
class Node:
    id: str
    act: int                   # 0-based act index
    tag: str                   # small header chip text
    title: str
    desc: str                  # card text — verbatim user material
    col: str = ""              # column key; auto-assigned when empty
    entity_ids: list[str] = field(default_factory=list)
    axis1_values: list[str] = field(default_factory=list)
    axis2_values: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)   # detail page
    color: str = ""            # css color ref; defaults to first entity's var
    base_y: int = 0            # filled by layout


@dataclass
class Brief:
    title: str
    subject: str = ""
    acts: list[Act] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    entity_axis_label: str = "Characters"       # plural
    entity_axis_singular: str = "Character"
    axes: list[Axis] = field(default_factory=list)          # 0-2 extra axes
    relations: list[Relation] = field(default_factory=list)
    columns: int = 5
    node_noun: str = "Event"                    # detail badge, e.g. "Case"
    accent: str = "#a78bfa"
    overview_html: str = ""
    timeline_id: str = "timeline"               # tid: keys + URLs
    owner_name: str = ""
    owner_email: str = ""


def _check_sections(sections, what) -> None:
    if len(sections or []) > MAX_SECTIONS:
        raise BriefError(f"{what}: {len(sections)} sections exceeds the "
                         f"{MAX_SECTIONS}-section limit")
    for i, s in enumerate(sections or []):
        _check_len(s.h, "section_h", f"{what} section {i+1} heading")
        _check_len(s.t, "section_t", f"{what} section {i+1} text")


def validate_brief(b: Brief) -> list[str]:
    """Raise BriefError on hard violations; return soft warnings."""
    warnings = []
    if not (b.title or "").strip():
        raise BriefError("title is required")
    _check_len(b.title, "title", "title")
    _check_len(b.subject, "subject", "subject")
    _check_len(b.overview_html, "overview_html", "overview_html")
    _check_len(b.entity_axis_label, "label", "entity_axis_label")
    _check_len(b.entity_axis_singular, "singular", "entity_axis_singular")
    _check_len(b.node_noun, "node_noun", "node_noun")
    _check_len(b.owner_name, "owner", "owner_name")
    _check_len(b.owner_email, "owner", "owner_email")
    if not 2 <= len(b.acts) <= 7:
        raise BriefError(f"{len(b.acts)} acts: the engine supports 2-7")
    if b.columns not in COL_SETS:
        raise BriefError(f"columns={b.columns}: engine grids are 3 or 5 columns")
    if len(b.axes) > 2:
        raise BriefError("at most 2 extra filter axes (plus the entity axis)")
    if len(b.entities) > 12:
        raise BriefError("at most 12 entities")
    if not b.entities:
        warnings.append("no entities defined — cards will carry no chips")
    _check_id(b.timeline_id, "timeline")
    _check_hex(b.accent, "accent", None)

    seen = set()
    for i, e in enumerate(b.entities):
        _check_id(e.id, "entity")
        if e.id in seen:
            raise BriefError(f"duplicate entity id {e.id!r}")
        seen.add(e.id)
        _check_len(e.name, "name", f"entity {e.id} name")
        _check_len(e.role, "role", f"entity {e.id} role")
        _check_len(e.symbol_svg, "symbol_svg", f"entity {e.id} symbol_svg")
        _check_sections(e.sections, f"entity {e.id}")
        e.color = _check_hex(e.color or None, f"entity {e.id}",
                             PALETTE[i % len(PALETTE)])
    for ax in b.axes:
        _check_len(ax.label, "label", "axis label")
        _check_len(ax.singular, "singular", "axis singular")
        for v in ax.values:
            _check_id(v.id, f"axis {ax.label!r} value")
            if v.id in seen:
                raise BriefError(f"axis value id {v.id!r} collides with another id")
            seen.add(v.id)
            _check_len(v.name, "name", f"axis value {v.id} name")
            _check_len(v.role, "role", f"axis value {v.id} role")
            _check_len(v.symbol_svg, "symbol_svg", f"axis value {v.id} symbol_svg")
            _check_sections(v.sections, f"axis value {v.id}")
    for i, a in enumerate(b.acts):
        _check_len(a.label, "label", f"act {i+1} label")
        _check_len(a.short, "short", f"act {i+1} short")
        a.color = _check_hex(a.color or None, f"act {i+1}",
                             PALETTE[i % len(PALETTE)])
        if not a.short:
            a.short = a.label.title()
    rel_keys = set()
    for r in b.relations:
        _check_id(r.key, "relation")
        if r.key in rel_keys:
            raise BriefError(f"duplicate relation key {r.key!r}")
        rel_keys.add(r.key)
        if r.key != "spine" and r.color:
            _check_hex(r.color, f"relation {r.key}", None)
    if "spine" not in rel_keys:
        warnings.append("no 'spine' relation — the neutral main-thread line "
                        "style is unused")
    return warnings


def validate_nodes(b: Brief, nodes: list[Node]) -> list[str]:
    warnings = []
    entity_ids = {e.id for e in b.entities}
    ax1 = {v.id for v in b.axes[0].values} if len(b.axes) > 0 else set()
    ax2 = {v.id for v in b.axes[1].values} if len(b.axes) > 1 else set()
    col_keys = set(COL_SETS[b.columns])
    seen = set()
    for n in nodes:
        _check_id(n.id, "node")
        if n.id in seen:
            raise BriefError(f"duplicate node id {n.id!r}")
        seen.add(n.id)
        if not 0 <= n.act < len(b.acts):
            raise BriefError(f"node {n.id}: act {n.act} out of range "
                             f"(0-{len(b.acts)-1})")
        if n.col and n.col not in col_keys:
            raise BriefError(f"node {n.id}: col {n.col!r} not in "
                             f"{sorted(col_keys)}")
        for eid in n.entity_ids:
            if eid not in entity_ids:
                raise BriefError(f"node {n.id}: unknown entity {eid!r}")
        for vid in n.axis1_values:
            if vid not in ax1:
                raise BriefError(f"node {n.id}: unknown axis-1 value {vid!r}")
        for vid in n.axis2_values:
            if vid not in ax2:
                raise BriefError(f"node {n.id}: unknown axis-2 value {vid!r}")
        _check_len(n.title, "title", f"node {n.id} title")
        _check_len(n.tag, "tag", f"node {n.id} tag")
        _check_len(n.desc, "desc", f"node {n.id} desc")
        _check_sections(n.sections, f"node {n.id}")
        if not (n.desc or "").strip():
            warnings.append(f"node {n.id}: empty desc (sparse by design?)")
    return warnings
