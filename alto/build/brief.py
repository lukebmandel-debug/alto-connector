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

_ROMAN_PARTS = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
                (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
                (5, "V"), (4, "IV"), (1, "I"))


def roman(n: int) -> str:
    """Roman numeral for a 1-based band number. Generated rather than
    tabulated: a timeline carries as many bands as the user's own material
    has, so there is no fixed set to enumerate."""
    if n < 1:
        raise BriefError(f"roman({n}): band numbers start at 1")
    out = []
    for value, sym in _ROMAN_PARTS:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)

# Domain-appropriate name for the periodization axis (the horizontal bands).
# The engine determines it: an explicit brief.period_noun wins; otherwise it is
# derived from the project kind; otherwise "Unit" (studying is Alto's primary
# use). A novel's bands read "Acts", a course's "Units", history's "Eras".
_PERIOD_BY_KIND = {"studying": "Unit", "writing": "Act", "research": "Phase"}


def period_words(kind: str = "", override: str = "") -> "tuple[str, str]":
    """(singular, plural) label for the periodization axis. Explicit override
    wins; else derived from the project kind; else 'Unit'."""
    sing = (override or "").strip() or _PERIOD_BY_KIND.get(
        (kind or "").strip().lower(), "Unit")
    return sing, sing + "s"

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
    # Drop this axis from the top nav bar, the mobile drawer and the legend,
    # while KEEPING its chips on the cards and its detail pages reachable.
    # For a large uncapped axis — a course's cases — a nav row listing every
    # value is unusable, but the per-card chips are exactly how you reach the
    # one you want. Distinct from FilterSpec.replace_nav, which also strips the
    # card chips because a filter-only axis has no pages worth opening.
    hide_nav: bool = False


@dataclass
class FilterValue:
    id: str
    name: str


@dataclass
class FilterSpec:
    """A canvas filter mapped onto one of the engine's two scalar filter
    slots (first filter → 'era', second → 'weight'). Filter chips dim
    non-matching nodes; they never navigate. Where values come from:
      entity / axis1 / axis2 — mirror that axis's values; a node's filter
        value is its first value on that axis (multi-valued nodes warn).
      acts   — one value per act; nodes filter by the act they sit in.
      coverage — derived Solid/Thin from how much the student authored on each
        node (Thin = a stub with no detail sections). §0-safe: it measures the
        shape of the student's own notes, so it surfaces gaps without inventing.
      depth — derived from how deep each node sits in the structure the
        connections describe: Level 1 for the roots of each band, Level 2 for
        their children, Level 3+ for everything below. §0-safe for the same
        reason — it measures the shape of the student's own outline. The one a
        concept outline actually wants: show just the skeleton for a review
        pass, then drill.
      custom — caller-defined `values`, assigned per node via Node.filters.
    `replace_nav` makes a mirrored axis1/axis2 **filter-only**: its
    navigation chips, drawer section, legend dot, and per-node card/detail
    chips are all suppressed, so the dimension exists solely as filter chips
    (no reachable detail pages, no identical fallback glyphs on cards) —
    recommended for axes whose detail pages carry no authored sections. For
    source 'entity' it only swaps the nav chips: entity chips stay on cards
    because they are the nodes' color identity."""
    id: str
    label: str                 # chip-group label, e.g. "Filter by Type"
    source: str = "custom"     # entity | axis1 | axis2 | acts | coverage | custom
    values: list[FilterValue] = field(default_factory=list)  # custom only
    replace_nav: bool = False  # entity/axis1/axis2 sources only


FILTER_SOURCES = ("entity", "axis1", "axis2", "acts", "coverage", "depth",
                  "custom")

MODES = ("linear", "outline")


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
    filters: dict = field(default_factory=dict)   # custom-filter id → value id
    sections: list[Section] = field(default_factory=list)   # detail page
    color: str = ""            # css color ref; defaults to first entity's var
    base_y: int = 0            # filled by layout
    # Outline mode: the concept that CONTAINS this one. "" makes it the root of
    # its band. Single-valued and stored on the child, matching how every other
    # reference in this model works (entity_ids, axis*_values) — and upsert-safe,
    # since adding a child touches exactly one record. A stored outline *path*
    # ("I.A.2") would be silently invalidated by inserting a sibling, so the
    # numbering is derived at build and never stored.
    parent: str = ""


@dataclass
class Brief:
    title: str
    subject: str = ""
    acts: list[Act] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    entity_axis_label: str = "Characters"       # plural
    entity_axis_singular: str = "Character"
    axes: list[Axis] = field(default_factory=list)          # 0-2 extra axes
    filters: list[FilterSpec] = field(default_factory=list)  # 0-2 canvas filters
    relations: list[Relation] = field(default_factory=list)
    columns: int = 5
    node_noun: str = "Event"                    # detail badge, e.g. "Case"
    period_noun: str = ""                        # bands label override, e.g. "Unit"
    accent: str = "#a78bfa"
    overview_html: str = ""
    timeline_id: str = "timeline"               # tid: keys + URLs
    owner_name: str = ""
    owner_email: str = ""
    # "linear" — nodes flow through the bands in sequence (the original shape).
    # "outline" — nodes are concepts that CONTAIN one another: each band holds
    # one family, its root centred with its children radiating out, and Node
    # .parent carries the structure. Same engine and same geometry either way;
    # what changes is where the cards sit and what a detail page shows.
    mode: str = "linear"
    # The "Filter · Lines" chips in the nav bar isolate one relation's lines.
    # A useful working tool for an author (or a law outline's "Overrules"), and
    # noise on a story where lines just follow characters — so it is a choice.
    line_filter: bool = True
    # The Filter toggle carries a section for every kind of sub-chip a card has
    # (characters, environments, themes, doctrines…), so any of them can be
    # filtered by. Set false for a timeline that should not offer that.
    chip_filters: bool = True


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
    # No upper bound: the engine builds bands in a runtime loop over PHASE_META
    # and takes each band's colour from its own entry, so it renders as many as
    # the brief carries. A course with eleven units gets eleven bands.
    if len(b.acts) < 2:
        raise BriefError(f"{len(b.acts)} acts: a timeline needs at least 2 "
                         "(with one band there is no periodization to show)")
    for flag in ("line_filter", "chip_filters"):
        if not isinstance(getattr(b, flag), bool):
            raise BriefError(f"{flag}: must be true or false")
    if b.mode not in MODES:
        raise BriefError(f"mode {b.mode!r}: must be one of {MODES}")
    if b.mode == "outline" and b.columns == 3:
        warnings.append(
            "outline mode with 3 columns: depth has nowhere to spread — "
            "5 columns give a hub's children their own lanes")
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
    if len(b.filters) > 2:
        raise BriefError("at most 2 filters (the engine has two filter slots)")
    f_ids, f_sources = set(), set()
    for f in b.filters:
        _check_id(f.id, "filter")
        if f.id in f_ids:
            raise BriefError(f"duplicate filter id {f.id!r}")
        f_ids.add(f.id)
        _check_len(f.label, "label", f"filter {f.id} label")
        if f.source not in FILTER_SOURCES:
            raise BriefError(f"filter {f.id}: source {f.source!r} must be one "
                             f"of {FILTER_SOURCES}")
        if f.source != "custom":
            if f.source in f_sources:
                raise BriefError(f"two filters share source {f.source!r}")
            f_sources.add(f.source)
            if f.values:
                raise BriefError(f"filter {f.id}: values are only for "
                                 "source 'custom' — derived sources mirror "
                                 "the axis they name")
        if f.source == "entity" and not b.entities:
            raise BriefError(f"filter {f.id}: source 'entity' needs entities")
        if f.source == "axis1" and len(b.axes) < 1:
            raise BriefError(f"filter {f.id}: source 'axis1' needs an extra axis")
        if f.source == "axis2" and len(b.axes) < 2:
            raise BriefError(f"filter {f.id}: source 'axis2' needs two extra axes")
        if f.source == "custom":
            if not 2 <= len(f.values) <= 10:
                raise BriefError(f"filter {f.id}: custom filters need 2-10 values")
            v_ids = set()
            for v in f.values:
                _check_id(v.id, f"filter {f.id} value")
                if v.id in v_ids:
                    raise BriefError(f"filter {f.id}: duplicate value {v.id!r}")
                v_ids.add(v.id)
                _check_len(v.name, "name", f"filter {f.id} value {v.id} name")
        if f.replace_nav and f.source in ("acts", "coverage", "custom"):
            warnings.append(f"filter {f.id}: replace_nav has no effect for "
                            f"source {f.source!r} (nothing to replace)")
        # A filter that mirrors the act bands or the (still-navigable) entity
        # chips re-expresses a dimension already on screen — a cross-cutting
        # filter (coverage, a custom dimension, an era) helps more.
        if f.source == "acts" or (f.source == "entity" and not f.replace_nav):
            mirror = "the act bands" if f.source == "acts" else "the nav chips"
            warnings.append(
                f"filter {f.id}: source {f.source!r} mostly repeats {mirror} — "
                f"a cross-cutting filter (e.g. 'coverage' or a custom dimension) "
                f"would add more than a dimension already on screen")
    rel_keys = set()
    non_spine = 0
    for r in b.relations:
        _check_id(r.key, "relation")
        if r.key in rel_keys:
            raise BriefError(f"duplicate relation key {r.key!r}")
        rel_keys.add(r.key)
        if r.key != "spine":
            # Non-spine relations get distinct palette colors by default —
            # the line renderer's merge/de-overlap legibility ("cross-colour
            # parallels stay clearly distinct", and a merged ride is only
            # readable as a separate line past its fork when it has its own
            # color) assumes relation types are distinguishable. Offset past
            # the entity assignments so lines and chips don't pool colors.
            if r.color:
                _check_hex(r.color, f"relation {r.key}", None)
            else:
                r.color = PALETTE[(len(b.entities) + non_spine) % len(PALETTE)]
            non_spine += 1
    if "spine" not in rel_keys:
        warnings.append("no 'spine' relation — the neutral main-thread line "
                        "style is unused")
    return warnings


def _validate_outline_tree(b: Brief, nodes: list[Node]) -> list[str]:
    """Outline mode's containment tree: every hard rule the geometry depends on.

    Returns soft warnings; raises BriefError on anything that would produce a
    page that cannot be laid out or read.

    A dangling parent is only a *warning* here on purpose. `add_nodes` is an
    idempotent batch upsert, so a child legitimately arrives before its parent
    during an interview; it becomes a hard failure at build time, in
    verify_data, once the node set is final. That is the same split
    `add_connections` already uses for act coverage.
    """
    warnings: list[str] = []
    ids = {n.id for n in nodes}
    by_id = {n.id: n for n in nodes}

    for n in nodes:
        if not n.parent:
            continue
        if n.parent == n.id:
            raise BriefError(f"node {n.id}: parent is itself")
        if n.parent not in ids:
            warnings.append(
                f"node {n.id}: parent {n.parent!r} is not a node yet — add it "
                "before building")
            continue
        if by_id[n.parent].act != n.act:
            raise BriefError(
                f"node {n.id} (unit {n.act + 1}) has parent {n.parent!r} "
                f"(unit {by_id[n.parent].act + 1}). A concept and its "
                "sub-concepts live in the same unit — a different family of "
                "concepts gets its own unit")

    # Cycles. Walk each chain to its end; revisiting a node inside one walk is
    # a loop, and a loop makes depth and layout meaningless.
    for n in nodes:
        seen, cur = {n.id}, n
        while cur.parent and cur.parent in by_id:
            if cur.parent in seen:
                raise BriefError(
                    f"node {n.id}: parent chain loops back on itself "
                    f"({' → '.join(list(seen)[:4])}). A concept cannot "
                    "contain one of its own ancestors")
            seen.add(cur.parent)
            cur = by_id[cur.parent]

    # Exactly one root per band — the hub the rest of the band radiates from.
    roots_by_act: dict[int, list[str]] = {}
    for n in nodes:
        if not n.parent:
            roots_by_act.setdefault(n.act, []).append(n.id)
    acts_with_nodes = {n.act for n in nodes}
    for act_i in range(len(b.acts)):
        roots = roots_by_act.get(act_i, [])
        label = b.acts[act_i].short or b.acts[act_i].label
        if act_i not in acts_with_nodes:
            # Nothing authored for this unit yet. During an interview the units
            # fill one at a time, so demanding a hub here would reject every
            # add_nodes call until the last one. The empty unit is caught at
            # build instead, by verify_data's act-coverage gate.
            continue
        if not roots:
            raise BriefError(
                f"unit {act_i + 1} ({label!r}) has no top-level concept — "
                "every unit needs exactly one hub with no parent")
        if len(roots) > 1:
            raise BriefError(
                f"unit {act_i + 1} ({label!r}) has {len(roots)} top-level "
                f"concepts ({', '.join(sorted(roots)[:4])}) — a unit has one "
                "hub. Give each its own unit, or make the others its "
                "sub-concepts")
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

    if b.mode == "outline":
        warnings += _validate_outline_tree(b, nodes)

    custom_vals = {f.id: {v.id for v in f.values}
                   for f in b.filters if f.source == "custom"}
    for n in nodes:
        for fid, vid in (n.filters or {}).items():
            if fid not in custom_vals:
                raise BriefError(f"node {n.id}: filters key {fid!r} is not a "
                                 "custom filter id (derived filters assign "
                                 "automatically)")
            if vid not in custom_vals[fid]:
                raise BriefError(f"node {n.id}: filter {fid}: unknown value "
                                 f"{vid!r}")
    for f in b.filters:
        multi_attr = {"entity": "entity_ids", "axis1": "axis1_values",
                      "axis2": "axis2_values"}.get(f.source)
        if multi_attr:
            multi = [n.id for n in nodes if len(getattr(n, multi_attr)) > 1]
            if multi:
                warnings.append(
                    f"filter {f.id}: {len(multi)} node(s) carry several "
                    f"{f.source} values ({', '.join(multi[:4])}) — the filter "
                    "uses the first")
        if f.source == "custom":
            missing = [n.id for n in nodes if f.id not in (n.filters or {})]
            if missing:
                warnings.append(
                    f"filter {f.id}: {len(missing)} node(s) unassigned "
                    f"({', '.join(missing[:4])}) — they dim whenever this "
                    "filter is active")
    return warnings
