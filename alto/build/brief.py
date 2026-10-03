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
    "persona_prompt": 5_000, "summary": 4_000, "flag_name": 80,
}
MAX_FLAGS = 12
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
    # Where the text stands relative to the material (ALTO-014): "quoted" —
    # the source's own words; "notes" — the user's notes, restated; "summary"
    # — a condensation. Shown beside the heading. A section headed "Text"
    # (or "Rule text", "Quote"…) claims to be primary text, so validation
    # warns unless it is marked quoted.
    prov: str = ""


PROVENANCE = {"quoted": "Quoted", "notes": "From your notes",
              "summary": "Summary"}
# Headings that read as the primary source's own words.
PRIMARY_TEXT_HEADINGS = {"text", "rule text", "statutory text", "quote",
                         "quotation", "verbatim"}


@dataclass
class Entity:
    id: str
    name: str
    role: str = ""
    color: str = ""            # #rrggbb; auto-assigned when empty
    symbol_svg: str = ""       # inline SVG glyph; fallback glyph when empty
    sections: list[Section] = field(default_factory=list)   # entity detail page
    aliases: list[str] = field(default_factory=list)   # other names prose uses
    sources: list[str] = field(default_factory=list)   # Brief.source_docs ids


@dataclass
class AxisValue:
    id: str
    name: str
    symbol_svg: str = ""
    color: str = ""
    role: str = ""
    sections: list[Section] = field(default_factory=list)
    # Other names the material uses for this value ("Carroll Towing" for
    # "United States v. Carroll Towing Co."); running text naming any of them
    # links to this value's page. Short forms are generated at build as well —
    # these are the ones generation cannot guess.
    aliases: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)   # Brief.source_docs ids
    # Where the value is found in a book: {ch?, p?, note?}. `ch` is the
    # chapter as the material names it ("Chapter 3 — Negligence"); `note`
    # stands alone when there is no page ("not in the casebook").
    cite: dict = field(default_factory=dict)
    # A hide_nav axis whose values fall into named families gets one Index chip
    # per family in the top bar instead of one for the whole axis — a law
    # outline's statutes, say: "Federal Rules of Civil Procedure" and
    # "28 U.S.C.", each chip opening the sections of its own. Empty: the value
    # sits under the axis's own chip.
    group: str = ""


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
    # A section for this axis in the Filter panel. None = the default: on for
    # an axis in the nav, off for a hide_nav axis, which gets an index page
    # of its own instead (ALTO-006).
    filter: bool | None = None
    sources: list[str] = field(default_factory=list)   # shown on its index page
    # Turns each value's `cite` into a link (ALTO-012):
    # {label?: "Casebook", url: "https://…/{sec}#page-{p}", sections: {"3": id}}.
    # `{sec}` is looked up by the chapter number in cite.ch; a chapter with no
    # entry prints unlinked. Without `{sec}` the template is used as-is.
    cite_link: dict = field(default_factory=dict)
    # The index page (hide_nav axes). nav_label: the button's name when the
    # plural label is too long for the nav row ("Restatement"). index_blurb:
    # which section headings, in order of preference, give each row's one-line
    # excerpt (default: the first section). index_sections: {h, t} shown at
    # the top of the index, e.g. where its page numbers come from.
    nav_label: str = ""
    index_blurb: list[str] = field(default_factory=list)
    index_sections: list[Section] = field(default_factory=list)


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
LAYOUTS = ("auto", "tree", "flow")
TREE_LINES = ("fan", "trunk")
# How an outline's outcome cards (Liable / Not Liable: a leaf whose tag differs
# from its parent's) sit. "stack": down the parent's spine like any child.
# "beside": on either side of the parent when there is room, else side by side
# directly under it.
OUTCOME_LAYOUTS = ("stack", "beside")
# Placement hints (layout.outline_plan): how a card's children are arranged,
# and where one card goes. PLACE_WORLD_W mirrors layout.WORLD_W (layout imports
# this module, so it cannot be imported here; a test holds the two equal).
ARRANGEMENTS = ("auto", "column", "row", "branches")
PLACE_KEYS = ("arrange", "x", "dx", "y", "dy", "w", "child_w", "float", "order", "tier")
PLACE_WORLD_W = 1700
PLACE_MAX_SHIFT = 2000
PLACE_MAX_Y = 40000
PLACE_WIDTHS = (120, 420)


@dataclass
class Act:
    label: str                 # band label, e.g. "ACT ONE — ARRIVAL"
    short: str = ""            # detail-page form, e.g. "Act One — Arrival"
    color: str = ""            # #rrggbb; band tint + numeral color
    # The Overview's paragraph for this section, drawn from the user's own
    # materials. Empty: an outline's Overview composes one from the section's
    # hub description and its concepts (detail_extras.outline_overview).
    summary: str = ""


@dataclass
class Relation:
    key: str                   # connection vocabulary key, e.g. "overrules"
    label: str = ""
    color: str = ""            # #rrggbb; "spine" key always renders neutral
    # The entity this relation's lines follow (a story's per-character lines).
    # Defaults to the entity whose id equals `key`; an uncoloured relation that
    # follows an entity takes that entity's colour, so the line and the chip
    # read as one thing.
    entity: str = ""


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
    # Brief.flags ids this node carries. Unlike `filters` (one value per node)
    # a node may carry several: a case can be pivotal AND overruled.
    flags: list[str] = field(default_factory=list)
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
    # Brief.source_docs ids this node was built from. In outline mode a node
    # with none inherits its nearest ancestor's (ALTO-011).
    sources: list[str] = field(default_factory=list)


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
    # How the desktop map is arranged. "auto" lets the builder pick the clearest
    # arrangement: an outline whose concepts really do group (sections, or
    # concepts with outcomes of their own) becomes a tree (layout.outline_tree)
    # when that crosses no more lines than the flowing cascade does; anything
    # else — a linear story, a flat list — flows. "tree" / "flow" force one.
    layout: str = "auto"
    # A tree's lines down a branch's spine. "fan": a section's lines spread
    # across the top of its first card and drop to each child at its own point,
    # so every child has a line of its own to hover and follow; "trunk": one
    # shared line straight down the spine.
    tree_lines: str = "fan"
    # Where a tree puts an outline's outcome cards (OUTCOME_LAYOUTS). An author
    # who wants every Liable / Not Liable beside its concept sets "beside" once
    # rather than placing each card.
    outcomes: str = "stack"
    # Where individual cards go, {node id: hints} (layout.outline_plan). The
    # tree's own arrangement is the default; a hint overrides it for one card
    # and the cards under it follow. `arrange` says how a card's children sit
    # ("auto", "column", "row", "branches") and `tier` which line of a row a
    # child goes on; `x` / `dx` and `y` / `dy` move the card (its progeny hang
    # from wherever it ends up; `y` pins its top to the page, `dy` is relative)
    # and `w` sets its width; `float` takes it out of the flow so it does not
    # push what follows down; `order` is its place among its siblings (1 =
    # first). Kept apart from the nodes on purpose: add_nodes replaces a node
    # whole, so a hint stored on one would vanish with an edit.
    placement: dict = field(default_factory=dict)
    # The "Filter · Lines" chips in the nav bar isolate one relation's lines.
    # A useful working tool for an author (or a law outline's "Overrules"), and
    # noise on a story where lines just follow characters — so it is a choice.
    line_filter: bool = True
    # The Filter toggle carries a section for every kind of sub-chip a card has
    # (characters, environments, themes, doctrines…), so any of them can be
    # filtered by. Set false for a timeline that should not offer that.
    chip_filters: bool = True
    # The user's own marks in their notes, [{id, name}] — "pivotal", "not
    # tested", "revisit"… The interview asks which marks they want. Each gets
    # a chip in the Filter toggle's "Flags" section; a node carries any number
    # (Node.flags), so it shows under every flag it has.
    flags: list[dict] = field(default_factory=list)
    # The documents the material came from, [{id, name, url?, local?}] — the
    # source map every node and sub-chip's `sources` point into, rendered as a
    # "Source notes" section on its page. Filled from the consent manifest
    # (record_materials_consent) for every entry that carries an id. `local`
    # is the file's path on the author's own computer: a copy opened from
    # disk opens it in place of `url` when there is no internet, and offers it
    # beside every link to that source (detail_extras.LOCAL_SOURCES).
    source_docs: list[dict] = field(default_factory=list)
    # The nav group that holds the index buttons of hide_nav axes.
    index_label: str = "Index"
    # Which kinds of page are linked by name in running text (ALTO-010):
    # "char" (entities), "env" (axis 1), "theme" (axis 2). A story whose
    # settings and themes are ordinary words ("Control", "Love") links its
    # characters only. autolink_overview=False keeps the Overview unlinked.
    autolink: list[str] = field(default_factory=lambda: ["env", "theme"])
    autolink_overview: bool = True
    # A node's detail page never shows less than its card: the card's number
    # and summary line open the page (a "Summary" lead) ahead of everything
    # else. False keeps the older page for a timeline whose authored sections
    # already restate every card in full.
    card_on_detail: bool = True
    # The study companion (guide §G): {name, prompt}. Not rendered on any page;
    # get_timeline hands it back so the conversation that picks the timeline up
    # again speaks as it. Its prompt must restate the closed-system rule.
    persona: dict = field(default_factory=dict)


def _check_sections(sections, what, warnings=None) -> None:
    if len(sections or []) > MAX_SECTIONS:
        raise BriefError(f"{what}: {len(sections)} sections exceeds the "
                         f"{MAX_SECTIONS}-section limit")
    for i, s in enumerate(sections or []):
        _check_len(s.h, "section_h", f"{what} section {i+1} heading")
        _check_len(s.t, "section_t", f"{what} section {i+1} text")
        if s.prov and s.prov not in PROVENANCE:
            raise BriefError(f"{what} section {i+1}: prov {s.prov!r} must be "
                             f"one of {sorted(PROVENANCE)}")
        if (warnings is not None and s.t and s.prov != "quoted"
                and (s.h or "").strip().lower() in PRIMARY_TEXT_HEADINGS):
            warnings.append(
                f"{what} section {i+1} is headed {s.h!r}, which reads as the "
                "source's own words — mark it prov:'quoted' only if it is a "
                "quote present in the material; otherwise head it for what it "
                "is (e.g. 'From your notes', prov:'notes')")


_TEXT_WARN = re.compile(r"^(.+) section \d+ is headed '([^']*)', which reads as")
_EMPTY_WARN = re.compile(r"^entity (\S+) \(.*\): no sections of its own")


def _collapse(warnings: list) -> list:
    """One line per new provenance / empty-element finding, not one per item
    (a Restatement axis can hold dozens)."""
    text, empty, out = [], [], []
    for w in warnings:
        m, e = _TEXT_WARN.match(w), _EMPTY_WARN.match(w)
        if m:
            text.append(m.group(1))
        elif e:
            empty.append(e.group(1))
        else:
            out.append(w)
    def ids(xs):
        return ", ".join(xs[:6]) + (f" and {len(xs) - 6} more" if len(xs) > 6 else "")
    if text:
        out.append(
            f"{len(text)} section(s) are headed like primary text ('Text', "
            f"'Quote'…) but not marked prov:'quoted' ({ids(text)}) — mark them "
            "quoted only if the words are a quote present in the material; "
            "otherwise head them for what they are (e.g. 'From your notes', "
            "prov:'notes')")
    if empty:
        out.append(
            f"{len(empty)} element page(s) have no sections of their own "
            f"({ids(empty)}) — each will list its concepts but not how it is "
            "satisfied; add sections from the material where it says")
    return out


def _check_refs(refs, doc_ids, what, warnings) -> None:
    for r in refs or []:
        if r not in doc_ids:
            warnings.append(f"{what}: source {r!r} is not in source_docs — "
                            "it will not be shown")


# A source's copy on the author's own computer: absolute (POSIX or a Windows
# drive) or under ~. No control characters, no URL schemes — it becomes a
# file:// URL only at click time, inside a copy opened from disk.
LOCAL_PATH = re.compile(r"^(?:/|~/|[A-Za-z]:[\\/])[^\x00-\x1f]{1,1000}$")


def _check_sources(b) -> set:
    ids = set()
    for d in b.source_docs:
        if not isinstance(d, dict) or not d.get("id"):
            raise BriefError("source_docs: every entry needs an id")
        _check_id(d["id"], "source doc")
        _check_len(d.get("name", ""), "name", f"source doc {d['id']} name")
        u = d.get("url") or ""
        if u and not u.startswith("https://"):
            raise BriefError(f"source doc {d['id']}: url must be https://")
        loc = d.get("local") or ""
        if loc and not LOCAL_PATH.match(loc):
            raise BriefError(f"source doc {d['id']}: local must be a full path "
                             "to the file on this computer ('/…', '~/…' or "
                             "'C:\\…')")
        ids.add(d["id"])
    return ids


_PERSONA_KEYS = {"name", "prompt"}
# Words a prompt restating §0 cannot avoid: it has to say the companion works
# only from the user's own material.
_CLOSED_WORDS = ("only", "never")
_MATERIAL_WORDS = ("material", "notes", "outline", "sources", "§0")


def _check_persona(p, warnings) -> None:
    if not p:
        return
    if not isinstance(p, dict) or set(p) - _PERSONA_KEYS:
        raise BriefError("persona must be {name, prompt}")
    for k in _PERSONA_KEYS:
        if not isinstance(p.get(k, ""), str):
            raise BriefError(f"persona.{k} must be text")
    _check_len(p.get("name", ""), "name", "persona name")
    _check_len(p.get("prompt", ""), "persona_prompt", "persona prompt")
    low = (p.get("prompt") or "").lower()
    if not (any(w in low for w in _CLOSED_WORDS)
            and any(w in low for w in _MATERIAL_WORDS)):
        warnings.append("persona prompt does not restate the closed-system "
                        "rule (§0): say it answers only from the user's own "
                        "material and never adds outside facts")


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
    _check_persona(b.persona, warnings)
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
    if b.layout not in LAYOUTS:
        raise BriefError(f"layout {b.layout!r}: must be one of {LAYOUTS}")
    if b.tree_lines not in TREE_LINES:
        raise BriefError(f"tree_lines {b.tree_lines!r}: must be one of {TREE_LINES}")
    if b.outcomes not in OUTCOME_LAYOUTS:
        raise BriefError(f"outcomes {b.outcomes!r}: must be one of {OUTCOME_LAYOUTS}")
    if b.outcomes == "beside" and b.mode != "outline":
        raise BriefError("outcomes 'beside' needs mode 'outline': outcomes are "
                         "the leaves of an outline's tree")
    if b.layout == "tree" and b.mode != "outline":
        raise BriefError("layout 'tree' needs mode 'outline': a tree is drawn "
                         "from the nodes' parents")
    _check_placement(b, warnings)
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
    doc_ids = _check_sources(b)
    if not isinstance(b.autolink, list) or set(b.autolink) - {"char", "env", "theme"}:
        raise BriefError("autolink: a list drawn from 'char', 'env', 'theme'")
    if not isinstance(b.autolink_overview, bool):
        raise BriefError("autolink_overview: must be true or false")

    seen = set()
    for i, e in enumerate(b.entities):
        _check_id(e.id, "entity")
        if e.id in seen:
            raise BriefError(f"duplicate entity id {e.id!r}")
        seen.add(e.id)
        _check_len(e.name, "name", f"entity {e.id} name")
        _check_len(e.role, "role", f"entity {e.id} role")
        _check_len(e.symbol_svg, "symbol_svg", f"entity {e.id} symbol_svg")
        _check_sections(e.sections, f"entity {e.id}", warnings)
        _check_refs(e.sources, doc_ids, f"entity {e.id}", warnings)
        for a in e.aliases:
            _check_len(a, "name", f"entity {e.id} alias")
        if b.mode == "outline" and not any(s.t for s in e.sections):
            # ALTO-015: the page then shows only the concept list.
            warnings.append(
                f"entity {e.id} ({e.name}): no sections of its own — its page "
                "will list its concepts but not how it is satisfied; add "
                "sections from the material if it says")
        e.color = _check_hex(e.color or None, f"entity {e.id}",
                             PALETTE[i % len(PALETTE)])
    for ax in b.axes:
        _check_len(ax.label, "label", "axis label")
        _check_len(ax.singular, "singular", "axis singular")
        if ax.filter is not None and not isinstance(ax.filter, bool):
            raise BriefError(f"axis {ax.label!r}: filter must be true, false or omitted")
        _check_refs(ax.sources, doc_ids, f"axis {ax.label!r}", warnings)
        _check_len(ax.nav_label, "label", f"axis {ax.label!r} nav_label")
        _check_sections(ax.index_sections, f"axis {ax.label!r} index", warnings)
        if ax.cite_link:
            u = ax.cite_link.get("url") or ""
            if not u.startswith("https://") or "{p}" not in u:
                raise BriefError(f"axis {ax.label!r}: cite_link.url must be an "
                                 "https:// template containing {p}")
            if not isinstance(ax.cite_link.get("sections", {}), dict):
                raise BriefError(f"axis {ax.label!r}: cite_link.sections must map "
                                 "chapter numbers to section ids")
        for v in ax.values:
            _check_id(v.id, f"axis {ax.label!r} value")
            if v.id in seen:
                raise BriefError(f"axis value id {v.id!r} collides with another id")
            seen.add(v.id)
            _check_len(v.name, "name", f"axis value {v.id} name")
            _check_len(v.role, "role", f"axis value {v.id} role")
            _check_len(v.symbol_svg, "symbol_svg", f"axis value {v.id} symbol_svg")
            _check_sections(v.sections, f"axis value {v.id}", warnings)
            _check_refs(v.sources, doc_ids, f"axis value {v.id}", warnings)
            for a in v.aliases:
                _check_len(a, "name", f"axis value {v.id} alias")
            if v.cite and not isinstance(v.cite, dict):
                raise BriefError(f"axis value {v.id}: cite must be {{ch?, p?, note?}}")
            if set(v.cite) - {"ch", "p", "note", "short"}:
                raise BriefError(f"axis value {v.id}: cite keys are ch, p, note, short")
    for i, a in enumerate(b.acts):
        _check_len(a.label, "label", f"act {i+1} label")
        _check_len(a.short, "short", f"act {i+1} short")
        _check_len(a.summary, "summary", f"act {i+1} summary")
        a.color = _check_hex(a.color or None, f"act {i+1}",
                             PALETTE[i % len(PALETTE)])
        if not a.short:
            a.short = a.label.title()
    if not isinstance(b.flags, list) or len(b.flags) > MAX_FLAGS:
        raise BriefError(f"flags: a list of at most {MAX_FLAGS} {{id, name}}")
    flag_ids = set()
    for fl in b.flags:
        if not isinstance(fl, dict):
            raise BriefError("flags: each flag is {id, name}")
        _check_id(fl.get("id", ""), "flag")
        if fl["id"] in flag_ids:
            raise BriefError(f"duplicate flag id {fl['id']!r}")
        flag_ids.add(fl["id"])
        if not (fl.get("name") or "").strip():
            raise BriefError(f"flag {fl['id']}: needs a name")
        _check_len(fl["name"], "flag_name", f"flag {fl['id']} name")
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
            ents = {e.id: e for e in b.entities}
            if r.entity and r.entity not in ents:
                # Relations arrive in create_timeline, entities after it.
                warnings.append(f"relation {r.key}: entity {r.entity!r} is not "
                                "on the entity axis (yet) — its lines keep a "
                                "palette color until it is")
            follows = ents.get(r.entity or r.key)
            if r.color:
                _check_hex(r.color, f"relation {r.key}", None)
            elif follows is not None:
                r.color = follows.color
            else:
                r.color = PALETTE[(len(b.entities) + non_spine) % len(PALETTE)]
            non_spine += 1
    if "spine" not in rel_keys:
        warnings.append("no 'spine' relation — the neutral main-thread line "
                        "style is unused")
    return _collapse(warnings)


def _check_placement(b: Brief, warnings: list[str]) -> None:
    """The shape of the placement hints: each is a known key with a value the
    layout can use. Which nodes they name is checked once the nodes are known
    (_validate_outline_tree); a typo'd key fails here, loudly, because a hint
    that silently does nothing looks exactly like one that worked."""
    pl = b.placement
    if not isinstance(pl, dict):
        raise BriefError("placement: must be an object {node id: {hint: value}}")
    if not pl:
        return
    if b.mode != "outline":
        raise BriefError("placement needs mode 'outline': it positions the "
                         "cards of a tree")

    def number(nid, key, v, lo, hi):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise BriefError(f"placement {nid}: {key} must be a number from "
                             f"{lo} to {hi}, not {v!r}")

    for nid, hints in pl.items():
        if not isinstance(hints, dict):
            raise BriefError(f"placement {nid}: must be an object of hints, "
                             f"e.g. {{\"arrange\": \"row\"}}")
        for key, v in hints.items():
            if key not in PLACE_KEYS:
                raise BriefError(f"placement {nid}: unknown hint {key!r}; use "
                                 f"one of {', '.join(PLACE_KEYS)}")
            if key == "arrange" and v not in ARRANGEMENTS:
                raise BriefError(f"placement {nid}: arrange {v!r} must be one "
                                 f"of {ARRANGEMENTS}")
            elif key == "x":
                number(nid, key, v, 0, PLACE_WORLD_W)
            elif key in ("dx", "dy"):
                number(nid, key, v, -PLACE_MAX_SHIFT, PLACE_MAX_SHIFT)
            elif key == "y":
                number(nid, key, v, 0, PLACE_MAX_Y)
            elif key in ("w", "child_w"):
                number(nid, key, v, *PLACE_WIDTHS)
            elif key == "float" and not isinstance(v, bool):
                raise BriefError(f"placement {nid}: float must be true or false")
            elif key in ("order", "tier") and (isinstance(v, bool) or not isinstance(v, int) or v < 1):
                raise BriefError(f"placement {nid}: {key} must be a whole number "
                                 "from 1" + (" (first among its siblings)" if key == "order"
                                             else " (the first line of its parent's row)"))
    if b.layout == "flow" and any(set(h) - {"order"} for h in pl.values()):
        warnings.append("placement: layout is 'flow', which ignores everything "
                        "but `order` — use layout 'auto' or 'tree' to see the rest")


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

    stray = sorted(set(b.placement or {}) - ids)
    if stray:
        warnings.append("placement names " + ", ".join(stray[:6])
                        + (" …" if len(stray) > 6 else "")
                        + ": not nodes in this timeline, so ignored")

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



# ── cited authorities ───────────────────────────────────────────────────────
# A law outline's notes cite statutes and court rules by name ("28 U.S.C. §
# 1367", "Rule 4(h)"). Each one belongs on the timeline as a section of its
# own (guide §C3). This finds the explicit citations so that, as more notes come
# in, the ones that have no section yet are named in the build/add_nodes
# warnings and the next step is obvious. A bare "§ 8A" names no source, so it
# is not matched.
_USC_CITE = re.compile(
    r"\b(\d{1,2})\s*U\.?\s?S\.?\s?C\.?\s*(?:§§?|sec(?:tion)?s?\.?)\s*"
    r"(\d+[A-Za-z]?)((?:\s*(?:,|&|and)\s*\d+[A-Za-z]?(?![\dA-Za-z]|\s*U\.?\s?S\.?\s?C))*)")
_RULE_CITE = re.compile(
    r"\b(?:Federal |Fed\.\s?R\.\s?Civ\.\s?P\.\s?|FRCP\s)Rule\s(\d+[A-Z]?)((?:\([a-z0-9]+\))*)"
    r"|\bRule\s(\d+[A-Z]?)((?:\([a-z0-9]+\))*)"
    r"|\bFed\.\s?R\.\s?Civ\.\s?P\.\s?(\d+[A-Z]?)((?:\([a-z0-9]+\))*)")


def _auth_key(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").lower()).strip()
    t = re.sub(r"fed\.?\s?r\.?\s?civ\.?\s?p\.?\s?", "rule ", t)
    t = re.sub(r"\bfederal rule( of civil procedure)?\s", "rule ", t)
    t = re.sub(r"(\d+)\s*u\.?\s?s\.?\s?c\.?\s*§§?\s*", r"\1 u.s.c. § ", t)
    return t.replace("rule  ", "rule ").strip()


def cited_authorities(b: Brief, nodes: list) -> dict:
    """{display cite: [node ids]} for each explicitly cited statute section or
    rule that no axis value names (by name or alias) and no covered value
    contains or extends — Rule 12(b)(6) is covered by "Rule 12(b)", and Rule 4
    by any "Rule 4(x)"."""
    have = set()
    for ax in b.axes:
        for v in ax.values:
            have.add(_auth_key(v.name))
            have.update(_auth_key(a) for a in v.aliases)
    for e in b.entities:
        have.add(_auth_key(e.name))
        have.update(_auth_key(a) for a in e.aliases)

    def covered(key: str) -> bool:
        for h in have:
            if h == key or h.startswith(key + "(") or key.startswith(h + "("):
                return True
        return False

    found: dict = {}
    for n in nodes:
        text = " ".join([n.title or "", n.desc or ""]
                        + [f"{s.h} {s.t}" for s in n.sections])
        text = re.sub(r"<[^>]+>", " ", text)
        for m in _USC_CITE.finditer(text):
            title = m.group(1)
            nums = [m.group(2)] + re.findall(r"\d+[A-Za-z]?", m.group(3) or "")
            for num in nums:
                cite = f"{title} U.S.C. § {num}"
                if not covered(_auth_key(cite)):
                    found.setdefault(cite, [])
                    if n.id not in found[cite]:
                        found[cite].append(n.id)
        for m in _RULE_CITE.finditer(text):
            num = next(g for g in (m.group(1), m.group(3), m.group(5)) if g)
            sub = (m.group(2) or m.group(4) or m.group(6) or "")
            cite = f"Rule {num}{sub}"
            if not covered(_auth_key(cite)):
                found.setdefault(cite, [])
                if n.id not in found[cite]:
                    found[cite].append(n.id)
    return found


def _authority_warnings(b: Brief, nodes: list) -> list:
    found = cited_authorities(b, nodes)
    if not found:
        return []
    items = [f"{c} ({', '.join(ids[:3])})" for c, ids in list(found.items())[:14]]
    more = f" and {len(found) - 14} more" if len(found) > 14 else ""
    return ["statutes/rules cited in the notes with no section page yet — "
            + "; ".join(items) + more + ". Add each as a section of the "
            "Statutes & Rules axis (guide §C3: group per source, aliases, and — "
            "if the user wants — the official text quoted with a summary)"]


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
        _check_sections(n.sections, f"node {n.id}", warnings)
        if not (n.desc or "").strip():
            warnings.append(f"node {n.id}: empty desc (sparse by design?)")

    if b.mode == "outline":
        warnings += _validate_outline_tree(b, nodes)
    doc_ids = {d.get("id") for d in b.source_docs if isinstance(d, dict)}
    for n in nodes:
        _check_refs(n.sources, doc_ids, f"node {n.id}", warnings)

    flag_ids = {fl.get("id") for fl in b.flags if isinstance(fl, dict)}
    for n in nodes:
        for fid in n.flags:
            if fid not in flag_ids:
                raise BriefError(f"node {n.id}: unknown flag {fid!r} "
                                 "(declare it in the brief's flags first)")
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
    if b.mode == "outline":
        warnings += _authority_warnings(b, nodes)
    return _collapse(warnings)
