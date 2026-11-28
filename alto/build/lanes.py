"""The horizontal timeline (brief.mode "lanes"): the story left to right.

The MAIN line is what is on the page, in the order the story tells it (page
order: unit by unit, the material's order inside each — ACT_SEQS). Every other
line is a character (or a place, a thread) while they are NOT on the page.
Where a character is on the page at a main-line event (node.present), their
solid line dips onto the main line, meets it at that event and leaves again.
A flashback is a run of consecutive main-line events the story tells out of
time (node.flash): the main line itself dips onto a labelled past stretch
whose events carry story dates, then rises back where the present resumes.
docs/lanes-v2-contract.md is the contract between this data and the page.

Data:
  brief.main_line   the main line's label ("" = none).
  brief.lines       [{id, label, color?, side?: "above"|"below", from?, to?}]
                    — the characters. from / to are LEGACY (v1: the event a
                    line branched off at / converged into); still accepted,
                    and on the page they count as presence. A line with
                    neither is just a continuous character line.
  brief.flashbacks  [{id, label}] — labelled past detours of the main line.
  node.line         the line it is on ("" / "main" = the main line, on the
                    page; a line id = that character's own event, off it).
  node.when         when it happened, as the material says it: "1842",
                    "1842-03-15", "March 1842", "500 BC", "Year 3", "Day 12".
                    Story time — inside a flashback too.
  node.present      main-line events: the line ids on the page at it.
  node.flash        main-line events: the flashback id it is inside.

Time is drawn to scale wherever events are dated; a long empty stretch is
squeezed and marked ≈. Undated events are spaced evenly by their order between
the dated ones around them. Cards hang off their line on a short stem.

The page side (LANES_JS) runs inside the engine's initLayout once every card
has been measured (engine patch lanes-layout-hook) and replaces the engine's
vertical layout on desktop; phones keep the engine's card-by-card view, in
the same order. Everything shown is the material's own words.
"""
from __future__ import annotations

import re

from .brief import BriefError
from .key_toggle import KEY_CSS, KEY_JS
from .lanes_nav import NAV_CSS, NAV_JS
from .lanes_title import LT_CSS, LT_JS
from .sanitize import js_json

MAIN = "main"
SIDES = ("above", "below")
# node.gap — how long after the event before it (page order) this one happens, as the material
# says it. The weight is how far apart they are drawn, in ordinary steps; with no gap it is 1.
GAPS = {"moments": 0.35, "hours": 0.5, "day": 0.65, "days": 0.85, "weeks": 1.3, "months": 1.7, "years": 2.4}

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DAYS_IN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def parse_when(s) -> "float | None":
    """A sortable number for a `when`, or None when it names no time.

    ISO-ish dates and "March 1842" / "15 March 1842" become fractional years;
    "500 BC" / "500 BCE" is -500; otherwise the first number in it ("Year 3",
    "Day 12", "Ch. 4" → 3, 12, 4). Mixing kinds (years with days) in one
    timeline is the author's call — the scale just follows the numbers."""
    if s is None:
        return None
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    t = str(s).strip().lower()
    if not t:
        return None
    bc = re.search(r"(\d+)\s*b\.?\s?c\.?(?:e\.?)?(?![a-z])", t)
    if bc:
        return -float(bc.group(1))
    m = re.match(r"^(-?\d{1,6})(?:-(\d{1,2}))?(?:-(\d{1,2}))?(?:[t ].*)?$", t)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2)) if m.group(2) else 0
        d = int(m.group(3)) if m.group(3) else 0
        return _frac(y, mo, d)
    mon = re.search(r"\b(" + "|".join(_MONTHS) + r")[a-z]*\.?\b", t)
    yr = re.search(r"\b(\d{3,4})\b", t)
    if mon and yr:
        day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", t.replace(yr.group(1), ""))
        return _frac(int(yr.group(1)), _MONTHS[mon.group(1)], int(day.group(1)) if day else 0)
    n = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(n.group(0)) if n else None


def _frac(y: int, mo: int, d: int) -> float:
    if not mo:
        return float(y)
    mo = max(1, min(12, mo))
    days = sum(_DAYS_IN[:mo - 1]) + max(0, min(31, d) - 1 if d else 0)
    return y + days / 365.0


SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def check_lines(b, warnings: list) -> None:
    """The brief's lines and flashbacks: shape, ids, sides. Which nodes they
    name is checked with the nodes (check_nodes)."""
    lines = b.lines
    if not isinstance(lines, list):
        raise BriefError("lines: must be a list of {id, label, color?, side?, from?, to?}")
    if lines and b.mode != "lanes":
        raise BriefError("lines need mode 'lanes': they are the horizontal timeline's storylines")
    seen = set()
    for i, ln in enumerate(lines):
        if not isinstance(ln, dict):
            raise BriefError(f"lines[{i}]: must be an object")
        lid = str(ln.get("id") or "").strip()
        if not lid or not SLUG.match(lid):
            raise BriefError(f"lines[{i}]: id {lid!r} must be a short lowercase slug")
        if lid == MAIN:
            raise BriefError("lines: 'main' is the main line itself — don't list it")
        if lid in seen:
            raise BriefError(f"lines: id {lid!r} is used twice")
        seen.add(lid)
        if not str(ln.get("label") or "").strip():
            raise BriefError(f"line {lid}: needs a label (what the line follows)")
        unknown = set(ln) - {"id", "label", "color", "side", "from", "to"}
        if unknown:
            raise BriefError(f"line {lid}: unknown keys {sorted(unknown)}")
        if ln.get("side") not in (None, "") + SIDES:
            raise BriefError(f"line {lid}: side must be 'above' or 'below'")
        c = ln.get("color")
        if c and not re.match(r"^#[0-9a-fA-F]{6}$", str(c)):
            raise BriefError(f"line {lid}: color must be #rrggbb")
    fbs = b.flashbacks if b.flashbacks is not None else []
    if not isinstance(fbs, list):
        raise BriefError("flashbacks: must be a list of {id, label}")
    if fbs and b.mode != "lanes":
        raise BriefError("flashbacks need mode 'lanes': they are detours of the horizontal timeline's main line")
    fseen = set()
    for i, fb in enumerate(fbs):
        if not isinstance(fb, dict):
            raise BriefError(f"flashbacks[{i}]: must be an object {{id, label}}")
        fid = str(fb.get("id") or "").strip()
        if not fid or not SLUG.match(fid):
            raise BriefError(f"flashbacks[{i}]: id {fid!r} must be a short lowercase slug")
        if fid == MAIN or fid in seen:
            raise BriefError(f"flashback {fid}: id is already a line's — give the flashback its own id")
        if fid in fseen:
            raise BriefError(f"flashbacks: id {fid!r} is used twice")
        fseen.add(fid)
        if not str(fb.get("label") or "").strip():
            raise BriefError(f"flashback {fid}: needs a label (e.g. 'Ten years earlier')")
        unknown = set(fb) - {"id", "label"}
        if unknown:
            raise BriefError(f"flashback {fid}: unknown keys {sorted(unknown)} — a flashback is {{id, label}}; "
                             "its events say they are in it with node.flash")
    check_flags(b, warnings)
    check_boxes(b, warnings)


BOX_KEYS = {"id", "label", "glyph", "on", "at", "node", "side"}


def check_boxes(b, warnings: list) -> None:
    """brief.box_tags: labelled boxes on the board that are not nodes. `on` is where one sits
    ('axis' — the default —, 'main', or a line id), `at` (a date or number, as node.when) or `node`
    (an event: it sits beside it) says where along the story, `side` which side of its line."""
    from .glyphs import LIBRARY
    bt = b.box_tags if b.box_tags is not None else []
    if not isinstance(bt, list):
        raise BriefError("box_tags: must be a list of {id, label, glyph?, on?, at?, node?, side?}")
    if bt and b.mode != "lanes":
        raise BriefError("box_tags need mode 'lanes': they are boxes on the horizontal timeline's board")
    seen, lids, names = set(), {ln.get("id") for ln in b.lines if isinstance(ln, dict)}, {g["n"] for g in LIBRARY}
    for i, t in enumerate(bt):
        if not isinstance(t, dict):
            raise BriefError(f"box_tags[{i}]: must be an object {{id, label, glyph?, on?, at?, node?, side?}}")
        tid = str(t.get("id") or "").strip()
        if not tid or not SLUG.match(tid):
            raise BriefError(f"box_tags[{i}]: id {tid!r} must be a short lowercase slug")
        if tid in seen:
            raise BriefError(f"box_tags: id {tid!r} is used twice")
        seen.add(tid)
        if not str(t.get("label") or "").strip():
            raise BriefError(f"box tag {tid}: needs a label")
        if len(str(t["label"])) > 60:
            raise BriefError(f"box tag {tid}: label is longer than 60 characters — a box tag is a few words")
        unknown = set(t) - BOX_KEYS
        if unknown:
            raise BriefError(f"box tag {tid}: unknown keys {sorted(unknown)} — a box tag is {{id, label, glyph?, on?, at?, node?, side?}}")
        if t.get("glyph") and t["glyph"] not in names:
            raise BriefError(f"box tag {tid}: glyph {t['glyph']!r} is not one of the glyph library's names")
        on = str(t.get("on") or "axis").strip()
        if on not in ("axis", MAIN) and on not in lids:
            raise BriefError(f"box tag {tid}: `on` {on!r} is not 'axis', 'main' or one of the brief's lines")
        if t.get("side") not in (None, "") + SIDES:
            raise BriefError(f"box tag {tid}: side must be 'above' or 'below'")
        at, node = str(t.get("at") if t.get("at") is not None else "").strip(), str(t.get("node") or "").strip()
        if not at and not node:
            raise BriefError(f"box tag {tid}: place it — `at` (a date or number, like an event's `when`) "
                             "or `node` (the event it sits beside)")
        if at and parse_when(at) is None:
            raise BriefError(f"box tag {tid}: `at` {at!r} names no date or number — use one, or give `node`")


FLAG_KEYS = {"id", "label", "at", "to", "node", "color"}


def check_flags(b, warnings: list) -> None:
    """brief.time_flags: markers pinned to a point in story time on the horizontal
    timeline's time axis. `at` (a date or number, as node.when) or `node` (an event whose
    place the flag takes) says where; `to` ends an era that starts at `at`."""
    fl = b.time_flags if b.time_flags is not None else []
    if not isinstance(fl, list):
        raise BriefError("time_flags: must be a list of {id, label, at?, to?, node?, color?}")
    if fl and b.mode != "lanes":
        raise BriefError("time_flags need mode 'lanes': they are flags on the horizontal timeline's time axis")
    seen = set()
    for i, f in enumerate(fl):
        if not isinstance(f, dict):
            raise BriefError(f"time_flags[{i}]: must be an object {{id, label, at?, to?, node?, color?}}")
        fid = str(f.get("id") or "").strip()
        if not fid or not SLUG.match(fid):
            raise BriefError(f"time_flags[{i}]: id {fid!r} must be a short lowercase slug")
        if fid in seen:
            raise BriefError(f"time_flags: id {fid!r} is used twice")
        seen.add(fid)
        if not str(f.get("label") or "").strip():
            raise BriefError(f"time flag {fid}: needs a label (a date, an era or a few words)")
        if len(str(f["label"])) > 80:
            raise BriefError(f"time flag {fid}: label is longer than 80 characters — keep it to a few words")
        unknown = set(f) - FLAG_KEYS
        if unknown:
            raise BriefError(f"time flag {fid}: unknown keys {sorted(unknown)} — a flag is {{id, label, at?, to?, node?, color?}}")
        at, to, node = (str(f.get(k) if f.get(k) is not None else "").strip() for k in ("at", "to", "node"))
        if not at and not node:
            raise BriefError(f"time flag {fid}: pin it — `at` (a date or number, like an event's `when`) "
                             "or `node` (the event whose place it takes)")
        if at and parse_when(at) is None:
            raise BriefError(f"time flag {fid}: `at` {at!r} names no date or number — use one (\"1852-06\", "
                             "\"500 BC\", \"Day 3\"), or give `node` to pin it to an event")
        if to:
            if not at:
                raise BriefError(f"time flag {fid}: `to` ends an era that starts at `at` — give `at` too")
            if parse_when(to) is None:
                raise BriefError(f"time flag {fid}: `to` {to!r} names no date or number")
            if parse_when(to) < parse_when(at):
                raise BriefError(f"time flag {fid}: the era ends ({to}) before it starts ({at})")
        c = f.get("color")
        if c and not re.match(r"^#[0-9a-fA-F]{6}$", str(c)):
            raise BriefError(f"time flag {fid}: color must be #rrggbb")


def page_order(b, nodes) -> list:
    """The nodes in the order the page tells them: unit by unit, the
    material's order inside each (blocks.py ACT_SEQS)."""
    return [nodes[i] for i in sorted(range(len(nodes)), key=lambda i: (nodes[i].act, i))]


def check_nodes(b, nodes, warnings: list) -> None:
    """Each event is on a known line; who is on the page at a main-line event
    (present) and which flashback it is in (flash) name known lines and
    flashbacks; a flashback's events are one consecutive run of the main
    line; a line's legacy from / to name events on another line, the join
    after the branch."""
    if b.mode != "lanes":
        for n in nodes:
            if n.line or n.when or n.present or n.flash or n.gap or n.nest:
                raise BriefError(f"node {n.id}: line / when / present / flash / gap / nest need mode 'lanes'")
        return
    by = {n.id: n for n in nodes}
    lids = {ln["id"] for ln in b.lines}
    fids = {fb["id"] for fb in (b.flashbacks or [])}
    for t in b.box_tags or []:
        if t.get("node") and t["node"] not in by:
            raise BriefError(f"box tag {t.get('id')}: node {t['node']!r} is not one of the events")
        if t.get("at") and not t.get("node") and nodes and not any(parse_when(n.when) is not None for n in nodes):
            warnings.append(f"box tag {t.get('id')}: no event is dated, so there is no time axis to pin `at` to — give it `node`")
    for f in b.time_flags or []:
        if f.get("node") and f["node"] not in by:
            raise BriefError(f"time flag {f.get('id')}: node {f['node']!r} is not one of the events")
        if f.get("at") and not f.get("node") and nodes and not any(parse_when(n.when) is not None for n in nodes):
            warnings.append(f"time flag {f.get('id')}: no event is dated, so there is no time axis to pin `at` to — "
                            "give it `node` (an event) or date the events")
    on = {}
    undated = []
    shown = set()
    for n in nodes:
        ln = n.line or MAIN
        if ln != MAIN and ln not in lids:
            raise BriefError(f"node {n.id}: line {n.line!r} is not one of the brief's lines "
                             f"({', '.join(sorted(lids)) or 'none yet — add it with lines'})")
        on.setdefault(ln, []).append(n)
        if n.when and parse_when(n.when) is None:
            warnings.append(f"node {n.id}: when {n.when!r} names no time it can place — "
                            "it is spaced by its order instead")
        if not n.when:
            undated.append(n.id)
        if n.gap and n.gap not in GAPS:
            raise BriefError(f"node {n.id}: gap {n.gap!r} must be one of {', '.join(GAPS)} — how long after the "
                             "event before it this one happens, as the material says it")
        pr = n.present
        if not isinstance(pr, list) or not all(isinstance(x, str) for x in pr):
            raise BriefError(f"node {n.id}: present must be a list of line ids")
        if pr and ln != MAIN:
            raise BriefError(f"node {n.id}: present is only for main-line events (who is on the page "
                             f"there) — this event is on {ln!r}'s own line")
        for x in pr:
            if x == MAIN:
                raise BriefError(f"node {n.id}: present lists 'main' — list the characters on the page, "
                                 "the main line is the page itself")
            if x not in lids:
                raise BriefError(f"node {n.id}: present {x!r} is not one of the brief's lines "
                                 f"({', '.join(sorted(lids)) or 'none yet — add it with lines'})")
        if len(set(pr)) != len(pr):
            raise BriefError(f"node {n.id}: present names a line twice")
        shown.update(pr)
        if not isinstance(n.flash, str):
            raise BriefError(f"node {n.id}: flash must be a flashback id")
        if n.flash:
            if ln != MAIN:
                raise BriefError(f"node {n.id}: flash is only for main-line events — a flashback is a "
                                 f"detour of the main line, and this event is on {ln!r}'s own line")
            if n.flash not in fids:
                raise BriefError(f"node {n.id}: flash {n.flash!r} is not one of the brief's flashbacks "
                                 f"({', '.join(sorted(fids)) or 'none yet — add it with flashbacks'})")
    check_nests(nodes, by, warnings)
    # a flashback is one consecutive run of main-line events, set before the present it returns to
    mains = [n for n in page_order(b, nodes) if (n.line or MAIN) == MAIN]
    runs = {}
    for i, n in enumerate(mains):
        if n.flash:
            r = runs.setdefault(n.flash, [])
            if r and r[-1][-1] != i - 1:
                r.append([i])
            elif r:
                r[-1].append(i)
            else:
                r.append([i])
    for fid, r in runs.items():
        if len(r) > 1:
            gap = mains[r[0][-1] + 1]
            raise BriefError(f"flashback {fid}: its events must be consecutive on the main line — "
                             f"{mains[r[0][-1]].id!r} and {mains[r[1][0]].id!r} have {gap.id!r} "
                             "between them; use a second flashback for the later one")
        ts = [parse_when(mains[i].when) for i in r[0]]
        ts = [t for t in ts if t is not None]
        after = r[0][-1] + 1
        if ts and after < len(mains):
            ta = parse_when(mains[after].when)
            if ta is not None and max(ts) >= ta:
                warnings.append(f"flashback {fid}: its events are dated as late as or later than "
                                f"{mains[after].id!r}, where the story returns — a flashback is "
                                "usually set before the moment the story comes back to")
    for fb in b.flashbacks or []:
        if fb["id"] not in runs:
            warnings.append(f"flashback {fb['id']}: has no events yet — mark them with flash")
    for ln in b.lines:
        lid = ln["id"]
        for k in ("from", "to"):
            v = ln.get(k)
            if not v:
                continue
            if v not in by:
                raise BriefError(f"line {lid}: {k} {v!r} is not a node")
            if (by[v].line or MAIN) == lid:
                raise BriefError(f"line {lid}: {k} {v!r} is on the line itself — it must be an "
                                 "event on the line it branches from / converges into")
        if not on.get(lid) and lid not in shown and not (ln.get("from") or ln.get("to")):
            warnings.append(f"line {lid}: has no events yet and is on the page nowhere")
        f, t = parse_when(by[ln["from"]].when) if ln.get("from") else None, \
            parse_when(by[ln["to"]].when) if ln.get("to") else None
        if f is not None and t is not None and t < f:
            raise BriefError(f"line {lid}: converges ({ln['to']}) before it branches off ({ln['from']})")
    if undated and len(undated) < len(nodes):
        warnings.append(f"{len(undated)} event(s) have no `when` and are spaced by their order "
                        f"between the dated ones: {', '.join(undated[:8])}"
                        + ("…" if len(undated) > 8 else ""))


def check_nests(nodes, by, warnings: list) -> None:
    """Child nodes (node.nest = the event it is nested under). A child hangs beyond its parent on the
    parent's own side of the line, so it is on the SAME line (a child never crosses the line); it is
    one with its parent's moment, so it carries no `present` / `flash` of its own; and a chain of
    parents never loops. A parent that is not an event (yet) is a warning, like an outline's: an
    upsert may bring the child first."""
    for n in nodes:
        if not n.nest:
            continue
        if not isinstance(n.nest, str):
            raise BriefError(f"node {n.id}: nest must be the id of the event it is nested under")
        if n.nest == n.id:
            raise BriefError(f"node {n.id}: nest is itself")
        p = by.get(n.nest)
        if p is None:
            warnings.append(f"node {n.id}: nest {n.nest!r} is not an event yet — add it before building "
                            "(until then it is drawn as an event of its own)")
            continue
        if (p.line or MAIN) != (n.line or MAIN):
            raise BriefError(f"node {n.id}: nested under {n.nest!r}, which is on a different line "
                             f"({p.line or MAIN!r} / {n.line or MAIN!r}). A child hangs beyond its parent on the "
                             "same side of the line — it is on its parent's line")
        if n.present or n.flash:
            raise BriefError(f"node {n.id}: a nested event shares its parent's moment — it has no `present` "
                             "or `flash` of its own (those belong to the parent)")
    for n in nodes:
        seen, cur = {n.id}, n
        while cur.nest and cur.nest in by:
            if cur.nest in seen:
                raise BriefError(f"node {n.id}: nest chain loops back on itself — an event cannot be "
                                 "nested under one of its own children")
            seen.add(cur.nest)
            cur = by[cur.nest]


def tidy(brief: dict, nodes: list) -> list:
    """Manual edit mode's fold (alto/edits.py), after the page's edits are in:
    what no longer means anything is dropped rather than refusing every edit —
    `present` / `flash` on an event moved onto a character's own line, ids of
    lines / flashbacks that are gone, and a flashback's events after its first
    consecutive run (a card moved out of the middle of one). Works on the
    stored dicts; returns the ids of the nodes it changed."""
    if brief.get("mode") != "lanes":
        return []
    lids = {ln.get("id") for ln in brief.get("lines") or [] if isinstance(ln, dict)}
    fids = {fb.get("id") for fb in brief.get("flashbacks") or [] if isinstance(fb, dict)}
    changed = set()
    # a flag pinned to an event that is gone is pinned to nothing: it goes, or keeps its date
    ids = {n.get("id") for n in nodes}
    keep = []
    for f in brief.get("time_flags") or []:
        if isinstance(f, dict) and f.get("node") and f["node"] not in ids:
            if not f.get("at"):
                continue
            f.pop("node")
        keep.append(f)
    if keep:
        brief["time_flags"] = keep
    else:
        brief.pop("time_flags", None)
    # a box tag on a line that is gone moves to the time axis; one beside a gone event with no date goes
    keepb = []
    for t in brief.get("box_tags") or []:
        if not isinstance(t, dict):
            continue
        if t.get("on") not in (None, "", "axis", MAIN) and t["on"] not in lids:
            t["on"] = "axis"
        if t.get("node") and t["node"] not in ids:
            if not t.get("at"):
                continue
            t.pop("node")
        keepb.append(t)
    if keepb:
        brief["box_tags"] = keepb
    else:
        brief.pop("box_tags", None)
    byid = {n.get("id"): n for n in nodes}
    for n in nodes:
        par = n.get("nest")
        if par is None:
            continue
        p = byid.get(par)
        bad = (not par) or p is None or par == n.get("id") or (p.get("line") or MAIN) != (n.get("line") or MAIN)
        seen, cur = {n.get("id")}, p
        while not bad and cur is not None and cur.get("nest"):      # a loop (a card moved under one of its own children)
            if cur.get("nest") in seen:
                bad = True
                break
            seen.add(cur.get("id"))
            cur = byid.get(cur.get("nest"))
        if bad:
            n.pop("nest")
            changed.add(n["id"])
    for n in nodes:
        main = (n.get("line") or MAIN) == MAIN
        pr = n.get("present")
        if pr is not None:
            keep = [] if not main else [x for i, x in enumerate(pr) if x in lids and x not in pr[:i]]
            if keep != pr:
                if keep:
                    n["present"] = keep
                else:
                    n.pop("present")
                changed.add(n["id"])
        if n.get("nest") and (n.get("present") or n.get("flash")):      # a child shares its parent's moment
            n.pop("present", None)
            n.pop("flash", None)
            changed.add(n["id"])
        if "flash" in n and (not n["flash"] or not main or n["flash"] not in fids):
            n.pop("flash")
            changed.add(n["id"])
    order = [nodes[i] for i in sorted(range(len(nodes)), key=lambda i: (int(nodes[i].get("act") or 0), i))]
    mains = [n for n in order if (n.get("line") or MAIN) == MAIN]
    ended, cur = set(), None
    for n in mains:
        f = n.get("flash") or None
        if f != cur and cur:
            ended.add(cur)
        if f and f in ended:
            n.pop("flash")
            changed.add(n["id"])
            f = None
        cur = f
    return sorted(changed)


_PALETTE = ["#e07a5f", "#3d9a8b", "#8a6fd1", "#d4a017", "#4a90d9", "#c2577a", "#5a9e4b", "#b8763e"]


def norm_line(ln: dict, i: int) -> dict:
    """A line as the page shows it: every key, defaults filled (manual edit
    mode compares and stores lines in this form)."""
    return {"id": ln["id"], "label": ln.get("label") or "",
            "color": ln.get("color") or _PALETTE[i % len(_PALETTE)],
            "side": ln.get("side") or SIDES[i % 2],
            "from": ln.get("from") or "", "to": ln.get("to") or ""}


def norm_flag(f: dict) -> dict:
    """A time flag as the page shows it: every key, `t` / `t2` the parsed `at` / `to`
    (manual edit mode compares and stores flags in this form, without t / t2)."""
    at, to = str(f.get("at") or "").strip(), str(f.get("to") or "").strip()
    return {"id": f["id"], "label": str(f.get("label") or "").strip(), "at": at, "to": to,
            "node": str(f.get("node") or "").strip(), "color": f.get("color") or "",
            "t": parse_when(at) if at else None, "t2": parse_when(to) if to else None}


def norm_box(t: dict) -> dict:
    """A box tag as the page shows it: every key; `t` the parsed `at`, `svg` the glyph (manual edit
    mode compares and stores tags without t / svg)."""
    from .glyphs import LIBRARY
    at = str(t.get("at") if t.get("at") is not None else "").strip()
    g = str(t.get("glyph") or "").strip()
    svg = next((x["s"] for x in LIBRARY if x["n"] == g), "") if g else ""
    on = str(t.get("on") or "axis").strip()
    return {"id": t["id"], "label": str(t.get("label") or "").strip(), "glyph": g, "on": on, "at": at,
            "node": str(t.get("node") or "").strip(), "side": t.get("side") or "",
            "t": parse_when(at) if at else None, "svg": svg}


def derive(L: dict, order: "list | None" = None) -> dict:
    """Fill the page data's derived fields from its authored ones (the
    contract's "derived": order, ev[].i, lines[].events / presence / span,
    flashbacks[].nodes / prev / next). LANES_DERIVE_JS is the same on the
    page, run again after every edit."""
    ev = L["ev"]
    order = [i for i in (order if order is not None else L.get("order") or []) if i in ev]
    have = set(order)
    order += [i for i in ev if i not in have]
    L["order"] = order
    for k, i in enumerate(order):
        ev[i]["i"] = k
    lids = {ln["id"] for ln in L["lines"]}
    mains = [i for i in order if ev[i]["l"] == MAIN or ev[i]["l"] not in lids]
    for ln in L["lines"]:
        lid = ln["id"]
        ln["events"] = [i for i in order if ev[i]["l"] == lid]
        ln["presence"] = [i for i in mains
                          if lid in (ev[i].get("present") or []) or lid in (ev[i].get("ent") or [])
                          or i in (ln.get("from"), ln.get("to"))]
        both = set(ln["events"]) | set(ln["presence"])
        on = [i for i in order if i in both]
        ln["span"] = [on[0], on[-1]] if on else []
    for fb in L["flashbacks"]:
        ids = [i for i in mains if ev[i].get("flash") == fb["id"]]
        fb["nodes"] = ids
        a = mains.index(ids[0]) if ids else -1
        z = mains.index(ids[-1]) if ids else -1
        fb["prev"] = mains[a - 1] if a > 0 else ""
        fb["next"] = mains[z + 1] if ids and z + 1 < len(mains) else ""
    return L


def _name_key(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def chip_lines(b, nodes) -> "tuple[list, dict]":
    """Every character with a chip in the nav bar (brief.entities) has a line of its own.

    Luke (2026-10-23): "You left out major characters that had nav bar chips." The brief's
    lines were the only lines drawn, so a character the brief never named (some minor
    characters of terrarium-horizontal) had a chip and no line. An entity is matched to
    a brief line by id, or by its name / an alias against the line's label ("a full name");
    each one still without a line, and linked from at least one event, gets one: the
    entity's id, name and colour, on the side with fewer lines. Only on a v2 timeline (someone on
    the page somewhere, or a flashback): a v1 one keeps its side lines as they were. Returns the page's lines
    (brief lines first, normalised) and {entity id: line id}. An event's chips are then
    where that character is on the page (Luke: "a scene mentions a character if the
    mention is strong enough for a subchip"), on top of its authored `present`."""
    lines = [norm_line(ln, i) for i, ln in enumerate(b.lines)]
    if not b.flashbacks and not any(n.present for n in nodes):
        return lines, {}            # a v1 timeline (no one on the page anywhere): its side lines carry the story, as before
    used = {ln["id"] for ln in lines} | {fb["id"] for fb in b.flashbacks or []} | {MAIN}
    linked = {e for n in nodes for e in (n.entity_ids or [])}
    of = {}
    for e in b.entities or []:
        keys = {_name_key(e.name)} | {_name_key(a) for a in e.aliases or []}
        hit = next((ln for ln in lines if ln["id"] == e.id), None) or \
            next((ln for ln in lines if _name_key(ln["label"]) in keys - {""}), None)
        if hit:
            of[e.id] = hit["id"]
            continue
        if e.id not in linked:
            continue
        lid = e.id.lower() if SLUG.match(e.id.lower() or "") else "ch-" + (re.sub(r"[^a-z0-9]+", "-", e.id.lower()).strip("-")[:30] or "x")
        k, base = 2, lid
        while lid in used:
            lid, k = f"{base}-{k}", k + 1
        sides = [ln["side"] for ln in lines]
        side = "above" if sides.count("above") <= sides.count("below") else "below"
        lines.append({"id": lid, "label": e.name or e.id, "color": e.color or _PALETTE[len(lines) % len(_PALETTE)],
                      "side": side, "from": "", "to": ""})
        used.add(lid)
        of[e.id] = lid
    return lines, of


def _nest_of(n, by) -> str:
    """The id of the event `n` is nested under, or "" (not nested, or the parent is not an event of this
    timeline, or on another line, or it would loop: then it is drawn as an event of its own)."""
    p, seen = by.get(n.nest or ""), {n.id}
    if p is None or (p.line or MAIN) != (n.line or MAIN):
        return ""
    while p is not None:
        if p.id in seen:
            return ""
        seen.add(p.id)
        p = by.get(p.nest or "")
    return n.nest


def _nest_outlines(nodes, by) -> dict:
    """Each family's outline (the second way to open a nested branch): the shared outline tree layout (layout.outline_plan)
    run over the family alone — its root on top, its children by level, sections side by side — at the child cards' fixed
    size, so no browser measuring is needed. {root id: {member id: [dx, dy, w, parent id]}}: the card's centre across from the root's
    centre, its centre's distance beyond the root card's far edge, its width."""
    import copy
    from .layout import outline_plan, run_plan
    kid, fam = {}, {}
    for n in nodes:
        if _nest_of(n, by):
            kid[n.id] = n.nest
    for i in kid:
        r, g = i, 0
        while r in kid and g < 60:
            r, g = kid[r], g + 1
        fam.setdefault(r, []).append(i)
    out = {}
    for r, ids in fam.items():
        try:
            ns = []
            for i in [r] + ids:
                c = copy.copy(by[i])
                c.parent = kid.get(i)
                ns.append(c)
            plan = outline_plan(ns, 1)
            y, x, _ = run_plan(plan, ns, {c.id: 60 for c in ns})
            if any(i not in x or i not in y for i in [r] + ids):
                continue
            lift = 70 - min(y[i] - y[r] - 60 for i in ids)     # (the first level always clears the hanging tag: 40px between the cards)
            out[r] = {i: [round(x[i] - x[r]), round(y[i] - y[r] - 60 + lift), min(220, int(plan["w"].get(i, 220))), kid[i]] for i in ids}
        except Exception:                       # (a family the tree cannot lay out keeps its column: no second state)
            continue
    return out


def lanes_payload(b, nodes) -> dict:
    """The page's data (docs/lanes-v2-contract.md), as a dict."""
    lines, of = chip_lines(b, nodes)
    ev = {}
    by = {n.id: n for n in nodes}
    for n in nodes:
        main = (n.line or MAIN) == MAIN
        chips = [] if not main else [of[e] for e in (n.entity_ids or []) if e in of and of[e] != n.line]
        ev[n.id] = {"l": n.line or MAIN, "w": n.when or "", "t": parse_when(n.when), "i": 0,
                    "present": [str(x) for x in (n.present or [])], "flash": n.flash or "",
                    "ent": list(dict.fromkeys(chips)),
                    "g": GAPS.get(n.gap or "", 0), "gap": n.gap or ""}
        if _nest_of(n, by):                 # (only a child carries it: a timeline with none sends no new key)
            ev[n.id]["p"] = n.nest
    L = {"v": 2, "main": b.main_line or "",
         "order": [n.id for n in page_order(b, nodes)],
         "lines": lines,
         "ev": ev,
         "flashbacks": [{"id": fb["id"], "label": fb.get("label") or ""} for fb in b.flashbacks or []],
         "tf": [norm_flag(f) for f in b.time_flags or []],
         "bt": [norm_box(t) for t in b.box_tags or []]}
    outl = _nest_outlines(nodes, by) if any("p" in e for e in ev.values()) else {}
    if outl:
        L["out"] = outl                     # (only a timeline with nested events carries it)
    return derive(L)


# window._altoLanesDerive(L, order?): lanes.derive on the page — manual edit
# mode calls it after changing who is present, a flashback, a line.
LANES_DERIVE_JS = r"""
window._altoLanesDerive=function(L, order){
  if(!L) return L; var ev=L.ev||{};
  if(!order) order=(typeof ACT_SEQS!=='undefined') ? [].concat.apply([], ACT_SEQS) : (L.order||[]);
  order=order.filter(function(i){ return Object.prototype.hasOwnProperty.call(ev,i); });
  var have={}; order.forEach(function(i){ have[i]=1; });
  Object.keys(ev).forEach(function(i){ if(!have[i]){ order.push(i); have[i]=1; } });
  L.order=order; order.forEach(function(i,k){ ev[i].i=k; });
  var lids={}; (L.lines||[]).forEach(function(l){ lids[l.id]=1; });
  var mains=order.filter(function(i){ return ev[i].l==='main' || !lids[ev[i].l]; });
  (L.lines||[]).forEach(function(l){
    l.events=order.filter(function(i){ return ev[i].l===l.id; });
    l.presence=mains.filter(function(i){ return (ev[i].present||[]).indexOf(l.id)>=0 || (ev[i].ent||[]).indexOf(l.id)>=0 || i===l.from || i===l.to; });
    var both={}; l.events.concat(l.presence).forEach(function(i){ both[i]=1; });
    var on=order.filter(function(i){ return both[i]; });
    l.span=on.length ? [on[0], on[on.length-1]] : [];
  });
  (L.flashbacks=L.flashbacks||[]).forEach(function(f){
    var ids=mains.filter(function(i){ return ev[i].flash===f.id; });
    var a=ids.length?mains.indexOf(ids[0]):-1, z=ids.length?mains.indexOf(ids[ids.length-1]):-1;
    f.nodes=ids; f.prev=a>0?mains[a-1]:''; f.next=(ids.length && z+1<mains.length)?mains[z+1]:'';
  });
  return L;
};
"""


def lanes_data(b, nodes) -> str:
    """window._ALTO_LANES — what the page needs to lay the lines out — and
    window._altoLanesDerive, which keeps its derived fields true after edits."""
    return ("\nwindow._ALTO_LANES=" + js_json(lanes_payload(b, nodes), separators=(",", ":")) + ";\n"
            + "window._ALTO_LANES_PICK=" + js_json("alto-lanes-pick-" + (b.timeline_id or "")) + ";\n"
            + "window._ALTO_LANES_ENT=" + js_json(chip_lines(b, nodes)[1], separators=(",", ":")) + ";\n"
            + LANES_DERIVE_JS)


LANES_CSS = KEY_CSS + """
  /* the enlarged card is solid in Classic (light and dark): its glass let the cards behind it read through it (Board 2026-11-27: no text
     under text); Retro and Holographic cards are solid already */
  html.alto-lanes:not(.mobile):not(.alto-retro):not(.alto-holo) #world .node.focused .node-card:not(#_):not(#__){background:var(--surface,#fff) !important;
    -webkit-backdrop-filter:none !important;backdrop-filter:none !important;}
  html.alto-lanes:not(.mobile) #world{margin:0 !important;}
  html.alto-lanes:not(.mobile) #glass-slab{left:0 !important;transform:none !important;width:var(--lanes-w,1700px) !important;}
  html.alto-lanes:not(.mobile) #world .phase-band,html.alto-lanes:not(.mobile) #world .phase-label-float,html.alto-lanes:not(.mobile) #world .unit-bar{display:none !important;}
  html.alto-lanes:not(.mobile) #river-svg{display:none !important;}
  #lanes-svg{position:absolute;left:0;top:0;z-index:6;pointer-events:none;overflow:visible;}
  html.mobile #lanes-svg,html.mobile .lanes-unit,html.mobile .lanes-tag,html.mobile .lanes-past{display:none !important;}
  /* the page is the heaviest thing on the board: a wide soft halo, then a thick dark core, so it reads first and the characters read as lighter threads beside it */
  #lanes-svg .ln-main-halo{stroke:var(--accent);stroke-width:26;stroke-opacity:.2;fill:none;stroke-linecap:round;stroke-linejoin:round;}
  #lanes-svg .ln-main{stroke:color-mix(in srgb,var(--accent) 62%,var(--text));stroke-width:10;fill:none;stroke-linecap:round;stroke-linejoin:round;}
  /* every line is solid: the main line (the page), the characters (off it). The
     one dashed thing left is .ln-rel below. */
  #lanes-svg .ln-br{stroke-width:3;fill:none;stroke-linecap:round;stroke-linejoin:round;opacity:.9;}
  #lanes-svg .ln-ring{fill:var(--surface);stroke-width:3;}
  /* the past: a sunken, frosted strip behind the detour, its label a pill on the past track */
  #lanes-svg .ln-past-band{fill:var(--surface);fill-opacity:.34;stroke:var(--accent);stroke-opacity:.45;stroke-width:1.2;}
  .lanes-past{position:absolute;z-index:7;transform:translate(0,-50%);white-space:nowrap;pointer-events:auto;cursor:default;
    font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--accent);padding:4px 11px 4px 9px;border-radius:999px;
    background:color-mix(in srgb,var(--surface) 92%,transparent);border:1.5px solid currentColor;
    -webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);transition:opacity .2s;}
  .lanes-past i{font-style:normal;font-weight:800;margin-right:6px;}
  .lanes-past span{color:var(--muted);font-weight:600;margin-left:8px;font-variant-numeric:tabular-nums;}
  .lanes-past span:empty{display:none;}
  #lanes-svg .ln-rule{stroke:var(--muted);stroke-width:1.2;opacity:.55;}
  #lanes-svg .ln-hit{stroke:transparent;stroke-width:22;fill:none;pointer-events:stroke;cursor:pointer;}
  #lanes-svg g{transition:opacity .3s ease;}
  .node[data-ln] .node-card{transition:opacity .3s ease;}
  /* the key is a floating toggle's panel (key_toggle.py) */
  #lanes-key h5{margin:0 0 4px;}
  #lanes-key.shut .lk-body{display:none;}
  #lanes-key .lk-row{display:flex;gap:9px;align-items:flex-start;padding:5px 4px;border-radius:8px;cursor:pointer;}
  #lanes-key .lk-row:hover,#lanes-key .lk-row.ln-on{background:color-mix(in srgb,var(--text) 7%,transparent);}
  #lanes-key svg{flex:none;margin-top:3px;}
  #lanes-key small{display:block;color:var(--muted);font-size:11px;}
  #lanes-key .lk-sep{border-top:1px solid var(--border);margin:6px 0 4px;}
  #lanes-svg .ln-stem{stroke-width:1.5;opacity:.55;}
  #lanes-svg .ln-dot{stroke:var(--surface);stroke-width:2.5;}
  #lanes-svg .ln-tick{stroke:var(--muted);stroke-width:1;opacity:.6;}
  #lanes-svg .ln-ticklbl{fill:var(--muted);font-size:12px;font-variant-numeric:tabular-nums;}
  #lanes-svg .ln-break{stroke:var(--muted);stroke-width:1.6;fill:none;opacity:.8;}
  /* dashed on purpose: an arc is a link the material draws between two events,
     not a path anyone travels — the dash keeps it from reading as a character */
  #lanes-svg .ln-rel{fill:none;stroke-width:2;stroke-dasharray:7 5;opacity:.26;transition:opacity .2s;}
  #lanes-svg g.ln-on .ln-rel{opacity:.9;}
  #lanes-svg .ln-merge{stroke:var(--surface);stroke-width:2.5;}
  .lanes-tag{position:absolute;z-index:7;transform:translate(0,-50%);white-space:nowrap;
    font-size:12px;font-weight:700;letter-spacing:.04em;padding:4px 11px;border-radius:999px;
    background:color-mix(in srgb,var(--surface) 88%,transparent);border:1.5px solid currentColor;
    pointer-events:auto;cursor:pointer;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);transition:opacity .3s ease,background .2s;}
  .lanes-tag:hover{background:var(--surface);}
  .lanes-gap{position:absolute;z-index:8;transform:translate(-50%,-50%);white-space:nowrap;pointer-events:none;
    font-size:11px;font-weight:700;letter-spacing:.03em;padding:2px 9px;border-radius:999px;color:var(--text);
    background:color-mix(in srgb,var(--surface) 94%,transparent);border:1px solid color-mix(in srgb,var(--text) 22%,transparent);}
  html.mobile .lanes-gap{display:none !important;}
  .lanes-tag.ln-main-tag{color:var(--accent);}
  /* time flags (brief.time_flags): a pennant on a hairline pole that stands on the time axis; never a card — no page, no step.
     They are context: the lines dimmed to a character leave them at full strength (no data-ln). */
  .lanes-flag{position:absolute;z-index:7;transform:translate(0,-50%);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:26ch;box-sizing:border-box;
    font-size:12px;font-weight:700;letter-spacing:.02em;color:var(--text);padding:3px 11px 3px 10px;border-radius:0 6px 6px 0;cursor:default;pointer-events:auto;
    background:color-mix(in srgb,var(--flag-c,var(--accent)) 14%,var(--surface));border:1px solid color-mix(in srgb,var(--flag-c,var(--accent)) 50%,transparent);
    border-left:3px solid var(--flag-c,var(--accent));-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);animation:ln-unfurl .15s ease-out;}
  @keyframes ln-unfurl{from{opacity:0;transform:translate(-5px,-50%);}}
  @media (prefers-reduced-motion:reduce){.lanes-flag{animation:none;}}
  #lanes-svg .ln-fpole{stroke:var(--flag-c,var(--accent));stroke-width:1.5;opacity:.45;}
  #lanes-svg .ln-fdia{fill:var(--flag-c,var(--accent));stroke:var(--surface);stroke-width:1.5;}
  #lanes-svg .ln-fera{fill:var(--flag-c,var(--accent));opacity:.4;}
  html.phone-whole .lanes-flag{max-width:15ch;font-size:11px;padding:2px 8px 2px 7px;}
  .lanes-flag-n{max-width:none !important;min-width:24px;text-align:center;font-weight:800;cursor:pointer;}
  .lanes-flaglist{position:absolute;z-index:9;max-width:230px;padding:8px 10px;border-radius:8px;font-size:12px;color:var(--text);
    background:color-mix(in srgb,var(--surface) 96%,transparent);border:1px solid var(--border);box-shadow:0 6px 18px rgba(0,0,0,.18);}
  .lanes-flaglist div{padding:3px 0;} .lanes-flaglist b{display:block;font-weight:700;} .lanes-flaglist span{color:var(--muted);font-size:11px;font-variant-numeric:tabular-nums;}
  /* box tags (brief.box_tags): an annotation, like a caption on a map — flat, dashed, no number, no shadow, no lift, never a control */
  .lanes-box{position:absolute;z-index:7;transform:translate(-50%,-50%);display:flex;align-items:center;gap:6px;box-sizing:border-box;min-width:72px;max-width:220px;
    font-size:13px;font-weight:400;line-height:1.25;color:color-mix(in srgb,var(--text) 75%,transparent);padding:4px 10px;border-radius:6px;cursor:default;pointer-events:auto;
    border:1px dashed color-mix(in srgb,var(--text) 40%,transparent);background:color-mix(in srgb,var(--bg,var(--surface)) 80%,transparent);}   /* a flat backing: a line never runs through the words */
  .lanes-box .lb-t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;}
  .lanes-box .lb-g{flex:none;display:inline-flex;width:14px;height:14px;opacity:.8;}
  .lanes-box .lb-g svg{width:14px;height:14px;display:block;}
  #lanes-svg .ln-bstub{stroke:color-mix(in srgb,var(--text) 40%,transparent);stroke-width:1;}
  html.phone-whole .lanes-box{font-size:12px;max-width:160px;}
  html.alto-editing .lanes-box{cursor:pointer;}
  html.alto-editing .lanes-box:hover,.lanes-box.aed-on{outline:2px solid var(--accent);outline-offset:1px;}
  html.alto-editing .lanes-box.aed-drag{cursor:grabbing;opacity:.85;}
  html.ln-compact:not(.mobile) .lanes-box{font-size:12px;}
  html.ln-cz:not(.mobile) .lanes-box{font-size:calc(12px * var(--ln-cz,1));}
  @media print{.lanes-box{border-style:solid;border-width:1px;}}
  .lanes-bchip{font-size:11px;font-weight:500;color:var(--muted);padding:2px 9px;border-radius:6px;pointer-events:none;border:1px dashed color-mix(in srgb,var(--text) 40%,transparent);}
  /* the phone's card view: a flag is a chip under the card's date — flat, not a button, the whole label */
  .lanes-fchips{display:flex;flex-wrap:wrap;gap:5px;margin:2px 0 6px;}
  .lanes-fchip{font-size:11px;font-weight:700;letter-spacing:.02em;color:var(--text);padding:2px 9px 2px 8px;border-radius:0 6px 6px 0;pointer-events:none;
    background:color-mix(in srgb,var(--flag-c,var(--accent)) 14%,transparent);border-left:3px solid var(--flag-c,var(--accent));}
  html.alto-editing .lanes-flag{cursor:pointer;}
  html.alto-editing .lanes-flag:hover,.lanes-flag.aed-on{outline:2px solid var(--accent);outline-offset:1px;}
  html.alto-editing .lanes-flag.aed-drag{cursor:grabbing;opacity:.85;}
  html.ln-compact:not(.mobile) .lanes-flag{font-size:11px;}
  html.ln-cz:not(.mobile) .lanes-flag{font-size:calc(11px * var(--ln-cz,1));}
  @media print{.lanes-flag{border-style:solid;}}
  .lanes-unit{position:absolute;z-index:6;top:0;border-left:1.5px solid color-mix(in srgb,var(--unit-color) 30%,transparent);pointer-events:none;}
  .lanes-unit:first-child{border-left:0;}
  /* the unit labels are set into the main line where each unit begins, like a station's name on the track (Luke 2026-11-26:
     "i want unit labels embedded in the main timeline, not free floating"): the line runs into and out of them */
  #lanes-ulabels{position:absolute;left:0;top:0;width:0;height:0;z-index:60;pointer-events:none;}
  #lanes-ulabels .lu-chip{position:absolute;left:0;top:0;width:max-content;white-space:normal;text-align:center;line-height:1.25;font-size:12px;font-weight:800;
    letter-spacing:.12em;text-transform:uppercase;color:var(--unit-color);padding:5px 12px;border-radius:14px;box-sizing:border-box;overflow:hidden;
    background:var(--surface,#fff);border:1.5px solid color-mix(in srgb,var(--unit-color) 55%,transparent);}
  #lanes-ulabels .lu-chip b{font-weight:800;margin-right:7px;}
  /* each label glides in its own strip along the line, from where it rests to just short of the next unit's label (Luke 2026-11-26,
     "try to keep them as static elements as they move, and maybe make the movement more smooth going with the scroll instead of
     jumping"): sticky, so the browser moves it with the scroll frame by frame; its size is set once and never changes */
  #lanes-ulabels .lu-strip{position:absolute;pointer-events:none;}
  #lanes-ulabels .lu-strip > .lu-chip{position:sticky;left:var(--lu-l,20px);top:auto;display:block;max-width:none;will-change:transform;}
  html.mobile #lanes-ulabels{display:none !important;}
  html.alto-lanes:not(.mobile) #world .node-card:not(.focused) .node-desc{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden;}
  .node-card .lanes-when:empty{display:none;}
  /* the most compact boards (the fit in LANES_JS): a card shows its title only, the labels are smaller, and at
     the last the cards are drawn smaller; a card opened (enlarged) is whole again */
  html.ln-compact:not(.mobile) #world .node:not(.focused) .node-card:not(.focused) .node-desc,
  html.ln-compact:not(.mobile) #world .node:not(.focused) .node-card:not(.focused) .node-footer,
  html.ln-compact:not(.mobile) #world .node:not(.focused) .node-card:not(.focused) .node-summary{display:none !important;}
  html.ln-compact:not(.mobile) #world .node:not(.focused) .node-card:not(.focused){padding:9px 14px;width:auto;max-width:250px;}
  html.ln-compact:not(.mobile) #world .node:not(.focused) .node-card:not(.focused) .node-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  html.ln-compact:not(.mobile) .lanes-tag{font-size:10px;padding:1px 8px;}
  html.ln-cz:not(.mobile) #world .node:not(.focused) .node-card:not(.focused){zoom:var(--ln-cz,1);}
  html.ln-cz:not(.mobile) .lanes-tag{font-size:calc(10px * var(--ln-cz,1));padding:calc(1px * var(--ln-cz,1)) calc(8px * var(--ln-cz,1));border-width:1px;}
  html.ln-cz:not(.mobile) .lanes-gap{font-size:calc(11px * var(--ln-cz,1));}
  html.ln-cz:not(.mobile) #lanes-svg .ln-main-halo{stroke-width:calc(26px * var(--ln-cz,1));}
  html.ln-cz:not(.mobile) #lanes-svg .ln-main{stroke-width:calc(10px * var(--ln-cz,1));}
  html.ln-cz:not(.mobile) #lanes-svg .ln-br{stroke-width:calc(3px * var(--ln-cz,1));}
  /* the frosted slab is as tall as the board (the engine sized it for its vertical layout, which made the page scroll) */
  html.alto-lanes:not(.mobile) #glass-slab{height:var(--lanes-slab-h) !important;}
  html.alto-editing .node-card .lanes-when:empty{display:block;}
  html.alto-editing .node-card .lanes-when:empty::before{content:'+ When';opacity:.7;}
  html.alto-editing:not(.mobile) .node-card .lanes-when{pointer-events:auto;cursor:text;border-radius:4px;}
  html.alto-editing:not(.mobile) .node-card .lanes-when:hover{background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--text);}
  html.alto-editing .lanes-tag{cursor:context-menu;}
  .node-card .lanes-when{display:block;font-size:10.5px;font-weight:700;letter-spacing:.06em;color:var(--muted);
    margin:-2px 0 4px;font-variant-numeric:tabular-nums;}
  /* child nodes (node.nest): tucked behind the parent in the Compact view, outline-style beyond it in the Expanded */
  html.alto-lanes:not(.mobile) #world .node.ln-kid-shut{display:none !important;}
  html.alto-lanes:not(.mobile) #world .node.ln-kid{z-index:7;}
  html.alto-lanes:not(.mobile) #world .node.ln-kid:not(.focused) .node-card:not(.focused){width:var(--kw,220px) !important;min-width:0 !important;max-width:var(--kw,220px) !important;height:60px !important;
    box-sizing:border-box;padding:8px 12px !important;overflow:hidden;}
  html.alto-lanes:not(.mobile) #world .node.ln-kid:not(.focused) .node-card:not(.focused) :is(.node-desc,.node-footer,.node-summary,.lanes-when,.lanes-fchips){display:none !important;}
  html.alto-lanes:not(.mobile) #world .node.ln-kid:not(.focused) .node-card:not(.focused) .node-tag{font-size:10px;margin:0 0 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  html.alto-lanes:not(.mobile) #world .node.ln-kid:not(.focused) .node-card:not(.focused) .node-title{font-size:13px;line-height:1.2;margin:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;white-space:normal;}
  #lanes-svg .ln-kidline{stroke:color-mix(in srgb,var(--accent) 78%,var(--text));stroke-width:2;fill:none;stroke-opacity:.9;stroke-linecap:round;}
  #lanes-svg .ln-kiddot{fill:var(--accent);fill-opacity:.9;}
  /* the hide/show-inside control hangs off the card's far edge (under it, or over it on the upper side of the line): a tab outside the
     card's text box, 20px tall, its hit area 44px (Luke, 2026-11-26: "should not be covering text in a node ... a hanging tag").
     The second tag (.ln-otag) beside it sets an opened branch out as an outline. */
  .node-card .ln-chip,.node-card .ln-otag{position:absolute;z-index:3;font:700 10.5px/1 inherit;font-family:inherit;letter-spacing:.02em;padding:0 10px;height:20px;box-sizing:border-box;
    display:flex;align-items:center;border:0;background:var(--accent);color:var(--surface,#fff);cursor:pointer;pointer-events:auto;white-space:nowrap;}
  .node-card .ln-chip::before,.node-card .ln-otag::before{content:'';position:absolute;left:-4px;right:-4px;top:-12px;bottom:-12px;}
  .node.ln-sd1 .node-card :is(.ln-chip,.ln-otag){top:100%;margin-top:-1px;border-radius:0 0 9px 9px;}
  .node.ln-sd-1 .node-card :is(.ln-chip,.ln-otag){bottom:100%;margin-bottom:-1px;border-radius:9px 9px 0 0;}
  .node-card .ln-chip{left:14px;}
  .node-card .ln-otag{left:var(--ln-ox,110px);}
  .node-card .ln-otag[aria-pressed=true]{box-shadow:inset 0 0 0 2px var(--surface,#fff);}
  .node.focused .node-card :is(.ln-chip,.ln-otag){display:none;}
  #canvas.ln-dimline .node[data-ln]:not(.ln-on) :is(.ln-chip,.ln-otag){opacity:.16;}
  .node-card :is(.ln-chip,.ln-otag):hover{filter:brightness(1.12);}
  .node-card :is(.ln-chip,.ln-otag):focus-visible{outline:2px solid var(--text);outline-offset:2px;}
  html.alto-lanes:not(.mobile) #world .node.ln-has-kids:not(.ln-open){isolation:isolate;}
  html.alto-lanes:not(.mobile) #world .node.ln-has-kids:not(.ln-open):not(.focused)::before,
  html.alto-lanes:not(.mobile) #world .node.ln-has-kids:not(.ln-open):not(.focused)::after{content:'';position:absolute;z-index:-1;height:12px;background:var(--surface);
    border:1px solid var(--border);pointer-events:none;}
  html.alto-lanes:not(.mobile) #world .node.ln-sd1.ln-has-kids::before{left:9px;right:9px;bottom:-7px;border-radius:0 0 12px 12px;}
  html.alto-lanes:not(.mobile) #world .node.ln-sd1.ln-has-kids::after{left:18px;right:18px;bottom:-13px;border-radius:0 0 12px 12px;opacity:.6;}
  html.alto-lanes:not(.mobile) #world .node.ln-sd-1.ln-has-kids::before{left:9px;right:9px;top:-7px;border-radius:12px 12px 0 0;}
  html.alto-lanes:not(.mobile) #world .node.ln-sd-1.ln-has-kids::after{left:18px;right:18px;top:-13px;border-radius:12px 12px 0 0;opacity:.6;}
  /* a card enlarged: a nested card never reads stronger than the parent it hangs from (Luke 2026-11-27, "the nested nodes in the background being
     more visible than their parents"): small and all title, at the parents' .14 they read darker, and their connectors stayed at full strength */
  html.alto-lanes:not(.mobile) #canvas.focus-mode #world .node.ln-kid:not(.focused) .node-card{opacity:.1 !important;}
  html.alto-lanes:not(.mobile) #canvas.focus-mode #lanes-svg .ln-kids{opacity:.12;transition:opacity .3s;}
  html.alto-lanes:not(.mobile) #canvas.focus-mode #world .node:not(.focused) .node-card :is(.ln-chip,.ln-otag){visibility:hidden;}
  /* and no line label under the enlarged card's glass (no text under text): lanes.py underFocus() */
  html.alto-lanes:not(.mobile) #canvas.focus-mode #world :is(.lu-chip,.lanes-tag,.lanes-box).ln-ufoc{visibility:hidden;}
  .node-card.ln-kid-dim{background:var(--surface) !important;border-top-color:var(--border) !important;}
  .node-card.ln-kid-dim > *{opacity:0.15;}
  html.alto-lanes:not(.mobile) #world .node.ln-kc:not(.focused) .node-card{box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 70%,transparent), 0 10px 26px var(--node-rest-shadow) !important;}
  :is(#ln-view,#ln-olall){position:fixed;right:16px;bottom:102px;z-index:8100;width:38px;height:38px;padding:0;border-radius:12px;display:flex;align-items:center;justify-content:center;
    background:var(--card-glass-bg, var(--surface));border:1px solid var(--card-glass-border, var(--border));color:var(--text);cursor:pointer;
    -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);}
  /* a vanishing toggle (Luke, 2026-11-05): invisible until the pointer is over its corner or the board, fades in, and fades out again
     a moment after the pointer leaves; always there for the keyboard (Tab brings it into view) and while Alto's one-time offer is up */
  :is(#ln-view,#ln-olall){opacity:0;transition:opacity .28s ease;}
  :is(#ln-view,#ln-olall).ln-show,:is(#ln-view,#ln-olall):hover,:is(#ln-view,#ln-olall):focus-visible{opacity:1;}
  :is(#ln-view,#ln-olall):hover{border-color:var(--accent);color:var(--accent);}
  #ln-offer{position:fixed;right:16px;bottom:150px;z-index:8100;box-sizing:border-box;width:min(300px,calc(100vw - 32px));padding:12px 14px;border-radius:12px;
    background:var(--surface,#fff);border:1px solid var(--card-glass-border, var(--border));color:var(--text);font-size:13px;line-height:1.4;
    box-shadow:0 10px 26px var(--node-rest-shadow, rgba(0,0,0,.25));opacity:0;transition:opacity .28s ease;}
  html.alto-holo #ln-offer{background:#05070b;}
  #ln-offer.ln-on{opacity:1;}
  #ln-offer p{margin:0 0 10px;}
  #ln-offer .ln-offer-b{display:flex;gap:8px;justify-content:flex-end;}
  #ln-offer button{font:inherit;font-weight:600;padding:5px 11px;border-radius:8px;border:1px solid var(--card-glass-border, var(--border));background:transparent;color:var(--text);cursor:pointer;}
  #ln-offer button:first-child{background:var(--accent);border-color:var(--accent);color:var(--surface,#fff);}
  #ln-offer button:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
  html:not(.dark):not(.alto-retro):not(.alto-holo) #ln-offer button:first-child{color:#14122b;}
  html:is(.alto-retro,.alto-holo) #ln-offer,html:is(.alto-retro,.alto-holo) #ln-offer button{border-radius:0;}
  @media (prefers-reduced-motion:reduce){:is(#ln-view,#ln-olall),#ln-offer{transition:none;}}
  html.mobile #ln-offer,html.phone-whole #ln-offer,html.detail-open #ln-offer,html.printing #ln-offer{display:none !important;}
  @media print{#ln-offer{display:none !important;}}
  :is(#ln-view,#ln-olall)[aria-pressed=true]{background:var(--accent);color:var(--surface,#fff);}
  /* Classic light: the surface is white on a pale accent (2.72:1); dark ink there (Classic dark, Retro and Holographic keep theirs: 6.9-12:1) */
  html:not(.dark):not(.alto-retro):not(.alto-holo) :is(.node-card .ln-chip,.node-card .ln-otag,:is(#ln-view,#ln-olall)[aria-pressed=true]){color:#14122b;}
  html:is(.alto-retro,.alto-holo) :is(.node-card .ln-chip,.node-card .ln-otag,:is(#ln-view,#ln-olall)){border-radius:0 !important;}
  /* the unpressed glyph carries the card rim in Retro (gold) and Holographic (cyan), 1px, same box (Art, 2026-11-05); pressed keeps its fill, which is the same colour */
  html.alto-retro :is(#ln-view,#ln-olall):not([aria-pressed=true]){box-sizing:border-box;border:1px solid #d9ae55;}
  html.alto-holo :is(#ln-view,#ln-olall):not([aria-pressed=true]){box-sizing:border-box;border:1px solid #4ff0e0;}
  :is(#ln-view,#ln-olall):focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
  html.mobile :is(#ln-view,#ln-olall),html.phone-whole :is(#ln-view,#ln-olall),html.detail-open :is(#ln-view,#ln-olall),html.printing :is(#ln-view,#ln-olall){display:none !important;}
  body > #ln-olall{bottom:148px;}   /* (no rail: it stands over the view switch) */
  @media print{:is(#ln-view,#ln-olall),.node-card .ln-chip,.node-card .ln-otag{display:none !important;}}
  /* the switch is a tab of the right rail, straight under Scene (Luke 2026-11-26): always in view, a rail tab's size and shape (Scene's, backgrounds.py);
     Retro keeps its square with the 1px rim, Holographic its rail's glass lens (holo.py S1, #tab-rail>button), pressed lit as before */
  #tab-rail > :is(#ln-view,#ln-olall){position:static;opacity:1;width:34px;height:34px;box-sizing:border-box;padding:0;margin:0;-webkit-backdrop-filter:blur(18px) saturate(190%);backdrop-filter:blur(18px) saturate(190%);box-shadow:0 10px 26px var(--node-rest-shadow);}
  html:not(.alto-retro):not(.alto-holo) #tab-rail > :is(#ln-view,#ln-olall){border-right:none;border-radius:6px 0 0 6px;}
  #tab-rail > :is(#ln-view,#ln-olall) svg{width:18px;height:18px;}
  html.alto-retro #tab-rail>:is(#ln-view,#ln-olall)[aria-pressed=true]:not(#_):not(#__){background:#d9ae55 !important;color:#000 !important;}   /* (Retro's rail paints every tab black: pressed, the gold fill its open tabs wear) */
  /* lines picked to show only them (LANES_JS setPick): the rest leave the board */
  html.alto-lanes:not(.mobile) #world .node.ln-hid{display:none !important;}
  #lanes-key .lk-pickbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0 0 6px;padding:0 4px;font-size:11px;color:var(--muted);}
  #lanes-key .lk-all{all:unset;cursor:pointer;font-weight:700;color:var(--accent);padding:2px 6px;border-radius:6px;white-space:nowrap;}
  #lanes-key .lk-all:hover{background:color-mix(in srgb,var(--accent) 14%,transparent);}
  #lanes-key .lk-all:focus-visible,#lanes-key .lk-row:focus-visible{outline:2px solid var(--accent);outline-offset:1px;}
  #lanes-key:not(.lk-picking) .lk-all{visibility:hidden;}
  #lanes-key .lk-ck{flex:none;width:13px;height:13px;margin-top:2px;border-radius:4px;box-sizing:border-box;border:1.5px solid color-mix(in srgb,var(--muted) 70%,transparent);position:relative;transition:background .18s,border-color .18s;}
  #lanes-key .lk-row.lk-pick .lk-ck{background:var(--lk-c,var(--accent));border-color:var(--lk-c,var(--accent));}
  #lanes-key .lk-row.lk-pick .lk-ck::after{content:'';position:absolute;left:3.5px;top:.5px;width:3px;height:7px;border:solid var(--surface);border-width:0 2px 2px 0;transform:rotate(45deg);}
  #lanes-key .lk-row.lk-off{opacity:.5;}
  html.alto-lanes:not(.mobile) #nav .nav-btn.ln-chip-on{outline:2px solid currentColor;outline-offset:1px;}
  html.alto-lanes:not(.mobile) #nav .nav-btn.ln-chip-off{opacity:.5;}
  #lanes-key .lk-row.lk-off:hover{opacity:.85;}
  html.alto-lanes #canvas.ln-dimline .node[data-ln]:not(.ln-on) .node-card{opacity:.16 !important;}
  html.alto-lanes #canvas.ln-dimline #lanes-svg g[data-ln]:not(.ln-on){opacity:.1;}
  html.alto-lanes #canvas.ln-dimline #lanes-svg g[data-ln=main]:not(.ln-on){opacity:.3;}   /* the page stays in view under a character */
  html.alto-lanes #canvas.ln-dimline .lanes-past{opacity:.45;}
  html.alto-lanes #canvas.ln-dimline .lanes-tag:not(.ln-on){opacity:.3;}
"""


LANES_JS = KEY_JS + r"""
(function(){
var L=window._ALTO_LANES; if(!L) return;
var de=document.documentElement;
if(!de.classList.contains('mobile')) de.classList.add('alto-lanes');
var NS='http://www.w3.org/2000/svg';
var STEM=36, CARD_GAP=12, CARD_PAD=12, LEFT=330, RIGHT=420, TOP=96, BOTTOM=110;
var SPAN=190, MAXPX=1000, BREAK=320, BASE=190;          /* BREAK: a squeezed stretch still reads wider than an ordinary step */
/* the band between the main line and the cards: the characters' tracks, track k
   of a side BAND0+k*TRACK from the main line (the past track of the flashbacks,
   PAST below the main line, comes first on the lower side). Cards hang beyond
   the band, so a character's line never has to cross a card to reach the page. */
var BAND0=92, TRACK=60, PAST=84, RAMP_MIN=56, RAMP_MAX=130, SPREAD=22, HUG0=17, HUG_STEP=8, MINRUN=24;
/* a flashback's detour: lead-in, the S down to the past track, room for its
   label, its events (FB_STEP apart at the median), the S back up, lead-out */
var DLEAD=70, DRAMP=130, DOUT=70, FB_STEP=240;
window._altoLanesGeo=null;
/* ── child nodes (node.nest, lanes.py): an event nested under another of its line. In the Compact view it is tucked behind
   its parent ("▾ n inside"; the chip, or Down, opens it); in the Expanded view it is always shown, outline-style from the
   parent on the far side of the line. It is never an event of the line (no dot, no stem, no step of the ← → path). ── */
var KIDW=220, KIDH=60, KIDLY=70, KIDGAP=28, KIDIND=26;
var OPEN={}, OUTL={}, EXPD=false, PRINTX=false, KG=null, KC='', KSHOW=false;
var VK='alto-lanes-view-'+String(window._ALTO_LANES_PICK||'').replace(/^alto-lanes-pick-/,'');
try{ EXPD=localStorage.getItem(VK)==='expanded'; }catch(e){}
/* Luke 2026-11-27: "please add the ability when extend mode is on for all in horizontal timeline, to also turn all the nested branches into outline
   format". In the Expanded view one switch (#ln-olall, under the view switch) sets every branch out as an outline (OUTALL, remembered like the view);
   each branch's own tag still flips that one (OUTE: its exception to the switch, cleared when the switch is used). */
var OK_=VK+'-outline', OUTALL=false, OUTE={};
try{ OUTALL=localStorage.getItem(OK_)==='1'; }catch(e){}
function outWant(root){ return expandedNow() ? (root in OUTE ? !!OUTE[root] : OUTALL) : !!OUTL[root]; }
function kidsOn(){ return !de.classList.contains('mobile') && !de.classList.contains('phone-whole'); }
function nestOf(id){ var e=L.ev[id], p=e && e.p, q=p && L.ev[p]; return (kidsOn() && q && (q.l||'main')===(e.l||'main') && p!==id) ? p : ''; }
function rootOf(id){ var g=0; while(nestOf(id) && g++<40) id=nestOf(id); return id; }
function isKid(id){ return !!nestOf(id) && rootOf(id)!==id; }
function expandedNow(){ return EXPD || PRINTX; }
function openNow(root){ return expandedNow() || !!OPEN[root] || de.classList.contains('alto-editing'); }
function kidShut(id){ return isKid(id) && !openNow(rootOf(id)); }
function kidMap(ids){ var m={}; ids.forEach(function(id){ var p=nestOf(id); if(p && p!==id) (m[p]=m[p]||[]).push(id); }); return m; }
/* a family opened as an outline (lanes.py _nest_outlines: the outline tree's layout over the family at the child cards' size);
   only while its plan covers exactly the family's members now (a card moved by hand falls back to the column) */
function outPlan(root, fam){ var o=(L.out||{})[root]; if(!o || !fam || Object.keys(o).length!==fam.length) return null; for(var i=0;i<fam.length;i++){ var q=o[fam[i].id]; if(!q || q[3]!==nestOf(fam[i].id)) return null; } return o; }      /* (a card moved under another since the build: the plan no longer fits) */
function outOn(root, fam){ return outWant(root) && !de.classList.contains('alto-editing') && !!outPlan(root, fam); }
function outFan(o, ids){ var a=1e9, z=-1e9, d=0; ids.forEach(function(i){ var q=o[i]; if(!q) return; a=Math.min(a, q[0]-q[2]/2); z=Math.max(z, q[0]+q[2]/2); d=Math.max(d, q[1]+KIDH/2); }); return {l:a, r:z, d:d}; }
/* where each family of a row starts, beyond the card's far edge: 0, but where an outline fills the row the families stand one under the next, left to right */
/* where each family of a row starts, beyond the card's far edge. Families are packed: one that would run into a family already placed
   beside it (their spans across the board overlap, with a 24px gutter) goes beyond that one; one with clear room stays right under its
   card (Luke 2026-11-27: "make sure that when multiple nested branches are open in outline mode, they don't run into each other and still
   look relatively normal" — before, any row holding an outline stacked ALL its families one under the next, a staircase). kidE: each
   family's span [left, right]. Returns {vo: id -> offset, mx: 'side|row' -> the deepest a family of that row reaches}. */
function famPack(order, kidH, kidE, sideOf, rowOf){
  var vo={}, mx={}, rows={}; order.forEach(function(id){ if(!kidH[id] || !kidE[id]) return; var k=sideOf[id]+'|'+rowOf[id]; (rows[k]=rows[k]||[]).push(id); });
  Object.keys(rows).forEach(function(k){ var ids=rows[k], put=[]; ids.sort(function(a,b){ return kidE[a][0]-kidE[b][0]; });
    ids.forEach(function(i){ var e=kidE[i], v=0, moved=true;
      while(moved){ moved=false; put.forEach(function(p){ if(e[0]<p.r && p.l<e[1] && v<p.v+p.h && p.v<v+kidH[i]){ v=p.v+p.h; moved=true; } }); }
      vo[i]=v; put.push({l:e[0], r:e[1], v:v, h:kidH[i]}); mx[k]=Math.max(mx[k]||0, v+kidH[i]); }); });
  return {vo:vo, mx:mx};
}
function famOffs(order, kidH, kidE, sideOf, rowOf){ return famPack(order, kidH, kidE, sideOf, rowOf).vo; }
function fanShift(x, fa){ return Math.max(0, 24-(x+fa.l)); }      /* the fan keeps 24px clear of the board's left edge; to the right the board grows */
function famOf(m, id, d, out){ (m[id]||[]).forEach(function(k){ out.push({id:k, d:d}); famOf(m, k, d+1, out); }); return out; }
function med(a){ if(!a.length) return 0; a=a.slice().sort(function(x,y){ return x-y; }); var m=a.length>>1; return a.length%2?a[m]:(a[m-1]+a[m])/2; }
/* every event's time: dated as dated; undated spread evenly between the dated
   events around it in reading order (lanes.py) */
/* A story's pace. Where events are dated the page is to scale. Where they are not, each
   event's `gap` (how long after the one before it: moments … years, node.gap) says how far
   it sits from it — a rapid run of scenes is drawn close together, a jump of years far
   apart — and an event with no gap sits one ordinary step on. */
function times(order){
  var t={}, dated=[], W=[], acc=0;
  order.forEach(function(id,i){ var e=L.ev[id]; if(i) acc+=(e && e.g>0 ? e.g : 1); W[i]=acc; if(e && e.t!=null){ t[id]=e.t; dated.push(i); } });
  var gaps=[]; for(var k=1;k<dated.length;k++){ var g=t[order[dated[k]]]-t[order[dated[k-1]]]; if(g>0) gaps.push(g); }
  var step=med(gaps)||1;
  if(!dated.length){ order.forEach(function(id,i){ t[id]=W[i]; }); return t; }
  order.forEach(function(id,i){
    if(t[id]!=null) return;
    var a=-1,b=-1; for(var k=0;k<dated.length;k++){ if(dated[k]<i) a=dated[k]; else { b=dated[k]; break; } }
    if(a<0) t[id]=t[order[b]]-(W[b]-W[i])*step/2;
    else if(b<0) t[id]=t[order[a]]+(W[i]-W[a])*step/2;
    else { var ta=t[order[a]], tb=t[order[b]], dw=W[b]-W[a]; t[id]=ta+(tb-ta)*(dw>0?(W[i]-W[a])/dw:0); if(tb<=ta) t[id]=ta; }
  });
  return t;
}
/* time → x: to scale, a long empty stretch squeezed to BREAK and marked */
function scale(tv){
  var T=Object.keys(tv).map(function(k){ return tv[k]; }).sort(function(a,b){ return a-b; }).filter(function(v,i,a){ return !i || v>a[i-1]+1e-9; });
  var g=[]; for(var i=1;i<T.length;i++) g.push(T[i]-T[i-1]);
  var undated=!Object.keys(L.ev).some(function(k){ return L.ev[k].t!=null; });
  var s=(undated?BASE:SPAN)/(med(g)||1), X={}, breaks=[], x=LEFT, segs=[{t0:T[0], x0:LEFT}];
  T.forEach(function(v,i){
    if(i){ var px=(v-T[i-1])*s;
      if(px>MAXPX){ breaks.push(x+BREAK/2); x+=BREAK; segs[segs.length-1].t1=T[i-1]; segs[segs.length-1].x1=X[T[i-1]]; segs.push({t0:v, x0:x}); }
      else x+=px; }
    X[v]=x;
  });
  if(T.length){ segs[segs.length-1].t1=T[T.length-1]; segs[segs.length-1].x1=x; }
  return {x:function(v){ return X[v]; }, s:s, breaks:breaks, segs:segs, end:x};
}
function nice(span){ var p=Math.pow(10,Math.floor(Math.log(span)/Math.LN10)), m=span/p; return (m<1.5?1:m<3.5?2:m<7.5?5:10)*p; }
function el(tag,attrs,parent){ var e=document.createElementNS(NS,tag); for(var k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; }
/* the contract's derived fields (lines[].events / presence, flashbacks[].nodes),
   fresh on every layout: lanes.py's _altoLanesDerive when the page has it, else
   the same rules here (v1 data: presence = legacy from / to on the main line) */
function derive(){
  if(window._altoLanesDerive){ try{ window._altoLanesDerive(L); return; }catch(e){} }
  var order=[].concat.apply([],ACT_SEQS), lids={};
  L.lines.forEach(function(l){ lids[l.id]=1; });
  var mains=order.filter(function(i){ var e=L.ev[i]; return e && !lids[e.l]; });
  L.lines.forEach(function(l){
    l.events=order.filter(function(i){ return L.ev[i] && L.ev[i].l===l.id; });
    l.presence=mains.filter(function(i){ return (L.ev[i].present||[]).indexOf(l.id)>=0 || (L.ev[i].ent||[]).indexOf(l.id)>=0 || i===l.from || i===l.to; });
  });
  L.flashbacks=(L.flashbacks||[]).map(function(f){ f.nodes=mains.filter(function(i){ return L.ev[i].flash===f.id; }); return f; });
}
/* a flashback's story dates, as the material writes them: "1987–1994" */
function fbRange(ids){
  var d=ids.map(function(i){ return L.ev[i]; }).filter(function(e){ return e && e.t!=null && e.w; });
  if(!d.length) return '';
  d.sort(function(a,b){ return a.t-b.t; });
  var a=String(d[0].w).trim(), b=String(d[d.length-1].w).trim(), ya=a.match(/^-?\d{3,4}\b/), yb=b.match(/^-?\d{3,4}\b/);
  if(ya && yb){ a=ya[0]; b=yb[0]; }
  return a===b ? a : a+'–'+b;
}

/* ── the layout ─────────────────────────────────────────────────────────────
   x: the main line is the page, in page order. Present-day events (and the
   characters' own events) are placed to scale by their time; each flashback is
   a detour spliced in after the present event it follows, its own events
   spaced by their story time inside it, and everything later moves right by
   the detour's width.
   y: the main line at 0; the characters' tracks in a band either side of it
   (sharing a track when they never run at the same time); every card beyond
   the band on its side, packed outward where it would overlap another. */
/* the room the board has: the canvas between the bars at the top (under the key's toggle) and the
   rail at the bottom, in canvas layout px, as lanes_nav's band() sees it. Before the rail exists its
   place is kept: RAIL above the canvas's foot (PHONE_RAIL on a phone's whole view, where the rail sits on
   the phone's bar); once it is there the board is laid out again to it. `top` also clears the units'
   chips at the top of the world. */
var RAIL=88, PHONE_RAIL=128;
function lanesRoom(world){
  var c=document.getElementById('canvas'); if(!c || !c.clientHeight) return null;
  var r=c.getBoundingClientRect(), k=(r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1, ch=c.clientHeight, t=16, b=ch-16, q;
  var vis=function(e){ if(!e) return null; var x=e.getBoundingClientRect(); return (x.width && x.height && getComputedStyle(e).display!=='none') ? x : null; };
  if((q=vis(document.getElementById('key-toggle'))) && q.bottom>r.top && q.top<r.top+ch/2) t=Math.max(t, (q.bottom-r.top)/k+12);
  if((q=vis(document.getElementById('lanes-nav'))) && q.top<r.bottom) b=Math.min(b, (q.top-r.top)/k-14);
  else b=Math.min(b, ch-(de.classList.contains('phone-whole') ? PHONE_RAIL : RAIL));
  var wo=0, e=world; while(e && e!==c){ wo+=e.offsetTop; e=e.offsetParent; }
  return {t:t, b:b, ch:ch, wo:wo, pt:parseFloat(getComputedStyle(c).paddingTop)||0, top:Math.max(t, wo+56)};
}
/* whether the board carries a time axis: something dated in the present, and every `when` a plain number or date */
function axisNums(order, fbOf){
  if(!order.some(function(id){ return L.ev[id].t!=null && !fbOf[id]; })) return false;
  return order.every(function(id){ var w=L.ev[id].w; return !w || /^-?\d{1,6}(-\d{1,2}){0,2}$/.test(String(w).trim()); });
}
/* the Expanded / Edit board must fit the window, children included, top AND bottom (Art, 2026-11-05): the rows of a family close up
   first (KIDLY 70 -> 58, here and in layoutLanes), then fitStage() scales the whole stage into the room. The lines keep their layout. */
window._altoLanes=function(h){ KIDLY=70; return layoutLanes(h); };
function layoutLanes(h){
  if(de.classList.contains('mobile')) return false;
  var world=document.getElementById('world'); if(!world) return false;
  derive();
  hideOut();
  var order=[].concat.apply([],ACT_SEQS).filter(function(id){ return !!L.ev[id] && document.getElementById('node-'+id) && !hidEv(id) && !isKid(id); });
  NODES.forEach(function(n){ if(order.indexOf(n.id)<0 && L.ev[n.id] && document.getElementById('node-'+n.id) && !hidEv(n.id) && !isKid(n.id)) order.push(n.id); });
  /* the children (never on the line): their families, so the Expanded view can make room beyond a parent */
  var allIds=[].concat.apply([],ACT_SEQS).filter(function(id){ return !!L.ev[id] && document.getElementById('node-'+id); });
  NODES.forEach(function(n){ if(allIds.indexOf(n.id)<0 && L.ev[n.id] && document.getElementById('node-'+n.id)) allIds.push(n.id); });
  var kidIds=allIds.filter(function(id){ return isKid(id) && !hidEv(id); }), kids=kidMap(kidIds);
  var kidH={}, kidO={}, anyKids=false;
  order.forEach(function(id){ if(!openNow(id)) return; var f=famOf(kids, id, 1, []); if(f.length){ var o=outOn(id, f) ? outPlan(id, f) : null;
    kidH[id]=o ? outFan(o, f.map(function(q){ return q.id; })).d+14 : KIDGAP+KIDLY*f.length-(KIDLY-KIDH); kidO[id]=!!o; anyKids=true; } });
  var idx={}; order.forEach(function(id,i){ idx[id]=i; });
  var w={}; order.forEach(function(id){ var c=document.querySelector('#node-'+id+' .node-card'); w[id]=c?c.offsetWidth:270; });
  var main={id:'main', label:L.main, color:'', side:'both'}, LB={main:main};
  L.lines.forEach(function(l){ LB[l.id]=l; });
  var lines=[main].concat(L.lines);
  lines.forEach(function(l){ l.ev=[]; });
  var lineOfEv=function(id){ return LB[L.ev[id].l]||main; };
  order.forEach(function(id){ lineOfEv(id).ev.push(id); });
  var mains=main.ev.slice(), fbOf={};
  mains.forEach(function(i){ if(L.ev[i].flash) fbOf[i]=L.ev[i].flash; });
  /* the flashbacks: each run of consecutive main-line events with one flash id */
  var FBL={}; (L.flashbacks||[]).forEach(function(f){ FBL[f.id]=f; });
  var runs=[], cur=null;
  mains.forEach(function(i){ var f=fbOf[i]||'';
    if(f && cur && cur.id===f) cur.nodes.push(i);
    else if(f){ cur={id:f, label:(FBL[f]||{}).label||'', nodes:[i]}; runs.push(cur); }
    else cur=null; });
  var pres=order.filter(function(i){ return !fbOf[i]; });
  var tv=times(pres), S=scale(tv), Xr={};
  pres.forEach(function(id){ Xr[id]=S.x(tv[id]); });
  /* labels first: their widths decide where lines start and how much room a detour's label needs */
  world.querySelectorAll('.lanes-tag,.lanes-past,.lanes-gap,.lanes-flag,.lanes-flaglist,.lanes-box').forEach(function(e){ e.remove(); });
  L.lines.forEach(function(l){ l.tagEl=tag(world, l, 0, 0, l.color, 0); l.tagW=l.tagEl.offsetWidth||60; });
  var shiftBefore=0;
  runs.forEach(function(r){
    var k0=mains.indexOf(r.nodes[0]), k1=mains.indexOf(r.nodes[r.nodes.length-1]), p=null, n=null, k;
    for(k=k0-1;k>=0;k--) if(!fbOf[mains[k]]){ p=mains[k]; break; }
    for(k=k1+1;k<mains.length;k++) if(!fbOf[mains[k]]){ n=mains[k]; break; }
    r.prev=p; r.next=n; r.last=idx[r.nodes[r.nodes.length-1]]; r.range=fbRange(r.nodes);
    r.tagEl=pastTag(world, r); r.tagW=r.tagEl.offsetWidth||160;
    /* inside: story time to scale (its own scale), undated evenly */
    var ft=times(r.nodes), gs=[], off=[0];
    for(k=1;k<r.nodes.length;k++){ var g=ft[r.nodes[k]]-ft[r.nodes[k-1]]; if(g>0) gs.push(g); }
    var s=FB_STEP/(med(gs)||1);
    for(k=1;k<r.nodes.length;k++){ var dt=ft[r.nodes[k]]-ft[r.nodes[k-1]]; off.push(off[k-1]+(dt>0?Math.max(180,Math.min(560,dt*s)):FB_STEP)); }
    r.pin=r.tagW+46;
    r.Wd=DLEAD+DRAMP+r.pin+off[off.length-1]+DOUT+DRAMP+DLEAD;
    r.xa=p?Xr[p]:-Infinity;
    r.x0=(p?Xr[p]:LEFT-DLEAD+40)+shiftBefore; r.x1=r.x0+r.Wd;
    r.d0=r.x0+DLEAD; r.d1=r.x1-DLEAD;                 // where the main line leaves and rejoins the present
    r.f0=r.d0+DRAMP; r.f1=r.d1-DRAMP;                 // the flat past stretch
    r.off=off; shiftBefore+=r.Wd;
  });
  function shift(raw, i){ var s=0; runs.forEach(function(r){ if(raw>r.xa || (raw===r.xa && i>r.last)) s+=r.Wd; }); return s; }
  var X={};
  pres.forEach(function(id){ X[id]=Xr[id]+shift(Xr[id], idx[id]); });
  runs.forEach(function(r){ r.nodes.forEach(function(id,k){ X[id]=r.f0+r.pin+r.off[k]; }); });
  var hasPast=runs.length>0;
  /* each character: where it is on the page (its presence, plus a legacy
     from / to on another character's line) and its own events */
  L.lines.forEach(function(l){
    var pr=(l.presence||[]).filter(function(i){ return X[i]!=null; });
    [l.from,l.to].forEach(function(f){ if(f && X[f]!=null && pr.indexOf(f)<0 && L.ev[f].l!==l.id) pr.push(f); });
    l.pr=pr; l.drawn=pr.length+l.ev.length>0 && !hidLine(l.id);
  });
  /* where the main line and each character's line run: 200px either side of the main
     line's events (a story that opens in a flashback starts just before the dip), a
     character from just before its first event to just after its last */
  function span(){
    var mx=mains.filter(function(i){ return !fbOf[i]; }).map(function(i){ return X[i]; }), dx=runs.map(function(r){ return r.x0; });
    if(!mx.length && !dx.length) mx=order.map(function(i){ return X[i]; });
    main.x0=Math.min(mx.length?Math.min.apply(null,mx)-200:Infinity, dx.length?Math.min.apply(null,dx)-30:Infinity);
    main.x1=Math.max(mx.length?Math.max.apply(null,mx)+200:-Infinity, runs.length?runs[runs.length-1].x1+60:-Infinity);
    L.lines.forEach(function(l){
      if(!l.drawn){ l.x0=l.x1=null; return; }
      var xs=l.pr.map(function(i){ return X[i]; }).concat(l.ev.map(function(i){ return X[i]; }));
      var a=Math.min.apply(null,xs), b=Math.max.apply(null,xs);
      var lead=l.pr.some(function(i){ return X[i]===a; }) ? RAMP_MAX+SPREAD*2 : 30;
      var tail=l.pr.some(function(i){ return X[i]===b; }) ? RAMP_MAX+SPREAD*2+40 : 70;
      l.x0=a-lead-l.tagW-6; l.x1=b+tail;
    });
  }
  /* tracks: nearest the main line first, a track shared by lines that never run at the same time;
     `one`: every character above the main line (the most compact board, below) */
  var track;
  function tracks(one){
    track={'-1':[], '1':[]};
    L.lines.forEach(function(l){
      l.sd=one ? -1 : (l.side==='below'?1:-1);
      if(!l.drawn) return;
      var T=track[String(l.sd)], k=0;
      for(;k<T.length;k++){ if(T[k].every(function(o){ return l.x1+40<o.x0 || o.x1+40<l.x0; })) break; }
      (T[k]=T[k]||[]).push(l); l.track=k;
    });
  }
  /* ── the height: everything inside the window (Luke, 2026-10-23: "Its a problem that you have to
     scroll up or down to see them all, they should all be within the bounds of the page"). The room is
     the canvas between the bars at the top and the rail at the bottom, as lanes_nav's camera sees it.
     Boards are tried from the roomiest to the most compact until one fits: cards both sides of the main
     line, whole; the gaps (main line → tracks → cards) eased down towards their least (FIT); cards showing
     their title only (html.ln-compact); every character above the main line and every card below it;
     then the cards drawn smaller (--ln-cz). Cards never stack deeper than the room: a card that would
     overlap the one before it in its row moves later along the line instead, and everything after it
     moves with it, so the board stays in story order. */
  var FIT={b0:[34,BAND0], tr:[14,TRACK], st:[12,STEM], pad:[8,22], past:[44,PAST], none:[14,14]}, ZMIN=.35;
  function fv(k,u){ return FIT[k][0]+(FIT[k][1]-FIT[k][0])*u; }
  var room=lanesRoom(world), nums=axisNums(order, fbOf);
  /* time flags (brief.time_flags): pinned to an event's place (`node`) or to a point in story time (`at`, only on a
     board whose events are dated); they stand on the time axis, so a board with flags has the axis's room even undated */
  var FLG=timeFlags(order, fbOf), hasFl=FLG.length>0, FLR=hasFl ? (FLG.length>1 ? 2*FL_ROW : FL_ROW) : 0;
  /* box tags (brief.box_tags): labelled boxes that are not events; one on the axis has a row of its own above the ruler */
  var BTG=boxTags(order, fbOf), hasBA=BTG.some(function(t){ return t.on==='axis'; }), AX=(nums||hasFl||hasBA)?54+(hasBA?36:0):0;
  var hIn=h, hh={}, cards=order.filter(function(id){ return !!document.querySelector('#node-'+id+' .node-card'); });
  /* each card's date line goes in BEFORE the cards are measured: it adds a line to the card, so a first pass that measured without it
     (draw() used to add it afterwards) fitted rows 13 px short, and which fit a board kept depended on whether a second pass came */
  cards.forEach(function(id){ whenChip(document.querySelector('#node-'+id+' .node-card'), id); });
  function measure(compact){
    de.classList.toggle('ln-compact', !!compact); de.classList.remove('ln-cz');
    L.lines.forEach(function(l){ l.tagW=l.tagEl.offsetWidth||60; });
    order.forEach(function(id){ var c=document.querySelector('#node-'+id+' .node-card');
      hh[id]=(c && c.offsetHeight) || hIn[id] || 120; if(c) w[id]=c.offsetWidth; });
    return Math.max.apply(null, cards.map(function(id){ return hh[id]; }).concat([40]));
  }
  function sideBand(sd,u){
    var n=track[sd].length, past=sd==='1' && hasPast;
    if(!n) return past ? fv('past',u)+fv('pad',u) : fv('none',u);
    return (past ? fv('past',u)+fv('b0',u)-14 : fv('b0',u))+(n-1)*fv('tr',u)+fv('pad',u);
  }
  /* how tall a board is: one = lines above / cards below; R rows of cards a side of height hr */
  function need(one,u,R,hr){
    if(one) return sideBand('-1',u)+sideBand('1',u)+fv('st',u)+R*hr+(R-1)*CARD_GAP+AX;
    return sideBand('-1',u)+sideBand('1',u)+2*(fv('st',u)+R*hr+(R-1)*CARD_GAP)+AX;
  }
  var A=room ? room.b-room.top-FLR : Infinity, mode=null;
  [[0,0],[0,1],[1,1]].some(function(m){
    var hr=measure(m[1]); span(); tracks(m[0]);
    var n0=need(m[0],0,1,hr), n1=need(m[0],1,1,hr);
    if(n0>A) return false;
    var u=n1<=A ? 1 : (A-n0)/Math.max(1e-6,n1-n0);
    var R=1; if(u>=1){ var per=(hr+CARD_GAP)*(m[0]?1:2); R=Math.min(3, 1+Math.floor((A-n1)/per)); }
    mode={one:m[0], compact:m[1], u:u, R:R, hr:hr, cz:1}; return true;
  });
  if(!mode){                       /* still too tall (a phone held sideways): the whole board drawn smaller — gaps,
                                      cards, labels, strokes — as far as it stays legible (ZMIN) */
    var hr=measure(1); span(); tracks(1);
    var z=Math.max(ZMIN, Math.min(1, A/need(1,0,1,hr)));
    Object.keys(FIT).forEach(function(k){ FIT[k][0]*=z; });
    de.classList.add('ln-cz'); de.style.setProperty('--ln-cz', z.toFixed(3));
    L.lines.forEach(function(l){ l.tagW=l.tagEl.offsetWidth||l.tagW*z; });
    order.forEach(function(id){ hh[id]*=z; w[id]*=z; });
    span(); tracks(1);
    mode={one:1, compact:1, u:0, R:1, hr:hr*z, cz:z};
  }
  h=hh;
  var u=mode.u, STm=fv('st',u), TRm=fv('tr',u), HR=mode.hr;
  main.y=0; var pastY=fv('past',u);
  var base={'-1':fv('b0',u), '1':hasPast?pastY+fv('b0',u)-14:fv('b0',u)};
  L.lines.forEach(function(l){ if(l.drawn) l.y=l.sd*(base[String(l.sd)]+l.track*TRm); else l.y=0; });
  var band={'-1':sideBand('-1',u), '1':sideBand('1',u)};
  /* the cards, in time order: each in the first free row on its side; with no free row it moves
     later in time, just clear of the card in its way, and everything after it moves as much */
  var rows={'-1':mode.one?0:mode.R, '1':mode.R}, placed={'-1':[], '1':[]}, sideOf={}, offOf={}, rowOf={}, alt=0, cum=0, PX=[], X0={};
  var rowOff=function(sd,r){ return band[sd]+STm+r*(HR+CARD_GAP); };
  /* Luke 2026-11-28: "on outlines in extended mode for horizontal timelines, i'd like different nested branches not to overlap" — he picked
     "A: stretch the line". In the Expanded view, while any branch is set out as an outline, an outline OWNS the strip of the board it hangs in:
     no other card of its row stands over it, no other branch of its row shares its width (24px between them), and no card of a farther row
     drops its stem through it. A card that would break that moves later in time, just clear, and everything after it moves as much — the
     rule the cards themselves already keep. So every outline sits right under its own card, the card over the middle of it (at the board's
     left edge the CARD moves in, not the fan), and one wide outline no longer spreads under its neighbours and pushes their branches far
     below it. Lists beside lists pack as before; Compact and the phone never come here (expandedNow, kidsOn). */
  var strips=expandedNow() && Object.keys(kidO).some(function(k){ return kidO[k]; }), own={'-1':[], '1':[]};
  var famSpan=function(id){ if(!strips || !kidH[id]) return null; var f=famOf(kids, id, 1, []);
    if(kidO[id]){ var o=outPlan(id, f), fa=o && outFan(o, f.map(function(q){ return q.id; })); if(fa) return {l:fa.l-12, r:fa.r+12, o:true}; }
    var md=1; f.forEach(function(q){ md=Math.max(md, q.d); }); var l0=-(w[id]||270)/2; return {l:l0-12, r:l0+KIDIND*md+KIDW+12, o:false}; };
  var clearX=function(sd, r, x, half, fs){
    var hit=function(a, b){ return !!a && !!b && a[0]<b[1] && a[1]>b[0]; };
    for(var g=0;g<80;g++){ var nx=x, C=[x-half, x+half], F=fs ? [x+fs.l, x+fs.r] : null, FO=F && fs.o ? F : null, to=function(a, b){ nx=Math.max(nx, x+b[1]-a[0]); };
      if(FO && FO[0]<12) nx=Math.max(nx, x+12-FO[0]);                      /* (the fan 24px inside the board's left edge) */
      own[sd].forEach(function(e){ var EO=e.o ? e.f : null;
        if(e.r===r){ if(hit(C, e.c)) to(C, e.c); if(hit(FO, e.c)) to(FO, e.c); if(hit(C, EO)) to(C, EO); if((FO || EO) && hit(F, e.f)) to(F, e.f); }
        else if(e.r<r){ if(hit(C, EO)) to(C, EO); }
        else if(hit(FO, e.c)) to(FO, e.c); });
      if(nx<=x+.01) return x; x=nx; }
    return x; };
  order.slice().sort(function(a,b){ return X[a]-X[b] || idx[a]-idx[b]; }).forEach(function(id){
    var ln=lineOfEv(id), x0=X[id], x=x0+cum, half=w[id]/2+CARD_PAD;
    var sides=mode.one ? ['1'] : ln===main ? (fbOf[id]?['1']:(alt?['1','-1']:['-1','1'])) : [String(ln.sd)];
    var pick=null, best=null;
    for(var r=0;r<3 && !pick;r++) sides.forEach(function(sd){
      if(pick || r>=rows[sd]) return;
      if(strips){ var cx=clearX(sd, r, x, half, famSpan(id)); if(cx<=x+.01) pick={sd:sd, r:r, x:x}; else if(!best || cx<best.x-.5) best={sd:sd, r:r, x:cx}; return; }
      var row=placed[sd][r]||[], lo=x-half, hi=x+half, blk=row.filter(function(q){ return lo<q[1] && hi>q[0]; });
      if(!blk.length){ pick={sd:sd, r:r, x:x}; return; }
      var nx=Math.max.apply(null, blk.map(function(q){ return q[1]; }))+half;
      if(!best || nx<best.x-.5) best={sd:sd, r:r, x:nx};
    });
    pick=pick||best;
    cum+=pick.x-x; X0[id]=x0; X[id]=pick.x; PX.push([x0, cum]);
    (placed[pick.sd][pick.r]=placed[pick.sd][pick.r]||[]).push([pick.x-half, pick.x+half]);
    if(strips){ var fsp=famSpan(id); own[pick.sd].push({r:pick.r, c:[pick.x-half, pick.x+half], f:fsp ? [pick.x+fsp.l, pick.x+fsp.r] : null, o:!!(fsp && fsp.o)}); }
    sideOf[id]=+pick.sd; offOf[id]=rowOff(pick.sd, pick.r); rowOf[id]=pick.r;
    if(ln===main && !fbOf[id]) alt=1-alt;
  });
  /* the Expanded view: a row's cards that have children make room beyond them, so the next row of cards starts clear of the
     deepest outline above it (a row with none keeps its pitch). The cap on the height is on the LINES, so this changes nothing there. */
  var kidE={};
  if(anyKids){
    /* each family's span across the board: an outline's fan (as kids() will set it), a column's indented stack; 12px of gutter a side */
    order.forEach(function(id){ if(!kidH[id]) return; var f=famOf(kids, id, 1, []), x=X[id];
      if(kidO[id]){ var o=outPlan(id, f), fa=o && outFan(o, f.map(function(q){ return q.id; })); if(fa){ var fs=fanShift(x, fa); kidE[id]=[x+fs+fa.l-12, x+fs+fa.r+12]; return; } }
      var md=1; f.forEach(function(q){ md=Math.max(md, q.d); }); var l0=x-(w[id]||270)/2; kidE[id]=[l0-12, l0+KIDIND*md+KIDW+12]; });
    var mxk={'-1':[], '1':[]}, FP=famPack(order, kidH, kidE, sideOf, rowOf);
    Object.keys(FP.mx).forEach(function(k){ var p=k.split('|'); mxk[p[0]][+p[1]]=FP.mx[k]; });
    order.forEach(function(id){ var T=mxk[String(sideOf[id])], ex=0; for(var r=0;r<rowOf[id];r++) ex+=T[r]||0; offOf[id]+=ex; });
  }
  /* anything placed by x (a detour, the time axis, a squeezed stretch) moves as the events
     before it did; then the lines' labels, side by side where several start together */
  var push=function(x){ var s=0; for(var i=0;i<PX.length;i++) if(PX[i][0]<=x+1e-6 && PX[i][1]>s) s=PX[i][1]; return x+s; };
  runs.forEach(function(r){ ['x0','x1','d0','d1','f0','f1'].forEach(function(k){ r[k]=push(r[k]); }); });
  span();
  var tags=L.lines.filter(function(l){ return l.drawn; }).sort(function(a,b){ return Math.abs(a.y)-Math.abs(b.y); }), TH=(mode.compact?16:24)*mode.cz;
  tags.forEach(function(l,i){
    for(var k=0;k<i;k++){ var o=tags[k];
      if(Math.abs(o.y-l.y)<TH && l.x0<o.x0+o.tagW+8 && l.x0+l.tagW+8>o.x0){ l.x0=o.x0-l.tagW-10; k=-1; } }
  });
  var lmin=Math.min.apply(null, tags.map(function(l){ return l.x0; }).concat([main.x0-90, 24]));
  var sh=lmin<24 ? 24-lmin : 0;
  if(sh){ order.forEach(function(id){ X[id]+=sh; }); runs.forEach(function(r){ ['x0','x1','d0','d1','f0','f1'].forEach(function(k){ r[k]+=sh; }); });
    L.lines.forEach(function(l){ if(l.drawn){ l.x0+=sh; l.x1+=sh; } }); main.x0+=sh; main.x1+=sh; }
  var shiftAll=function(raw, i){ var x=raw+shift(raw, i); return push(x)+sh-raw; };
  FLG.forEach(function(f){
    var a=f.node ? X[f.node] : flagRaw(S, f.t); if(a==null) return;
    f.x=f.node ? a : a+shiftAll(a, -1);
    if(!f.node && f.t2!=null && f.t2>f.t){ var b=flagRaw(S, f.t2); f.x2=b+shiftAll(b, -1); }
    f.x=Math.max(main.x0+8, Math.min(main.x1-8, f.x)); if(f.x2!=null) f.x2=Math.max(f.x, Math.min(main.x1-8, f.x2));
  });
  FLG=FLG.filter(function(f){ return f.x!=null; });
  /* time ↔ x for manual edit mode's flag drag: x(t) rises with t, so t(x) is found by halving */
  (function(){
    var dated=order.some(function(id){ return L.ev[id].t!=null && !fbOf[id]; }), g=S.segs;
    if(!dated || !g.length){ window._altoLanesTime={dated:false}; return; }
    var lo0=g[0].t0, hi0=g[g.length-1].t1, rg=Math.max(hi0-lo0, 1e-6);
    var xf=function(t){ var a=flagRaw(S, t); return a+shiftAll(a, -1); };
    var yl=order.every(function(id){ var e=L.ev[id]; return e.t==null || fbOf[id] || (/^-?\d{3,4}(-\d{1,2}){0,2}$/.test(String(e.w||'').trim()) && e.t>-3000 && e.t<4000); });
    window._altoLanesTime={dated:true, yearLike:yl, pxYear:S.s, snap:yl ? 1/12 : nice(40/S.s),
      x:xf, t:function(x){ var a=lo0-8*rg, b=hi0+8*rg; for(var k=0;k<48;k++){ var m=(a+b)/2; if(xf(m)<x) a=m; else b=m; } return (a+b)/2; }};
  })();
  boxRows(world, BTG, X, w, shiftAll, S, main);
  var cy={}, VO=famOffs(order, kidH, kidE, sideOf, rowOf);
  order.forEach(function(id){ cy[id]=sideOf[id]*(offOf[id]+(h[id]||HR)/2); });
  var ys=[-16*mode.cz, 16*mode.cz, hasPast?pastY+30:0];
  L.lines.forEach(function(l){ if(l.drawn) ys.push(l.y-TH/2, l.y+TH/2); });
  order.forEach(function(id){ ys.push(cy[id]-(h[id]||HR)/2, cy[id]+(h[id]||HR)/2);
    if(kidH[id]) ys.push(cy[id]+sideOf[id]*((h[id]||HR)/2+(VO[id]||0)+kidH[id])); });             // the Expanded view's outline, beyond the card
  /* the flags' lane: pennants in rows above everything (a flag that would overlap the one before it goes up a row) */
  var frows=flagRows(world, FLG), flTop=Math.min.apply(null,ys)-6;
  if(frows) ys.push(flTop-frows*FL_ROW);
  FLG.forEach(function(f){ f.y=flTop-FL_ROW*(f.row+.5); });
  var y0=Math.min.apply(null,ys), y1=Math.max.apply(null,ys)+AX;
  /* children make the board taller than the fit allowed for: close their rows up first (fitStage() scales what is left) */
  if(room && anyKids && KIDLY>58 && (y1-y0)-A>1){ KIDLY=58; return layoutLanes(h); }
  /* the board's top where the room starts (the slack shared above and below); the page no taller than the canvas */
  var HXL=window._altoHXL||0, dy=room ? room.top-room.wo-WORLD_PAD_TOP-y0+Math.max(0, A-(y1-y0))/2+HXL : TOP+HXL-y0;   /* (HXL: a unit header that wrapped taller than its room, phone.py chips(): the board starts lower) */
  var xe=[S.end+sh, push(S.end)+sh, main.x1]; L.lines.forEach(function(l){ if(l.drawn) xe.push(l.x1); });
  order.forEach(function(id){ xe.push(X[id]+w[id]/2); if(kidO[id]){ var f=famOf(kids, id, 1, []), o=outPlan(id, f), fa=o && outFan(o, f.map(function(q){ return q.id; })); if(fa) xe.push(X[id]+fanShift(X[id], fa)+fa.r); } });
  var W=Math.max.apply(null,xe)+RIGHT, H=y1-AX+dy+((nums||hasFl||hasBA)?AX+BOTTOM-56:24);
  if(room && y1-y0<=A) H=Math.max(y1-AX+dy+8, Math.min(H, room.ch-room.pt-WORLD_PAD_TOP));
  lines.forEach(function(l){ l.y+=dy; }); pastY+=dy; FLG.forEach(function(f){ f.y+=dy; });
  runs.forEach(function(r){ r.y=pastY; });
  window._altoLanesFit={room:room, A:A, need:y1-y0, mode:mode};
  /* the cards */
  var pos={};
  order.forEach(function(id){
    var n=NODES.filter(function(q){ return q.id===id; })[0], y=cy[id]+dy;
    pos[id]=y; if(n){ n.displayX=X[id]; n.y=y; }
    var e=document.getElementById('node-'+id); if(!e) return;
    e.style.left=X[id]+'px'; e.style.top=(y+WORLD_PAD_TOP)+'px'; e.setAttribute('data-ln', L.ev[id].l);
    var lp=L.lines.filter(function(l){ return l.pr && l.pr.indexOf(id)>=0; }).map(function(l){ return l.id; });
    if(fbOf[id]) lp.push('fb:'+fbOf[id]);
    if(lp.length) e.setAttribute('data-lp', lp.join(' ')); else e.removeAttribute('data-lp');
    whenChip(e.querySelector('.node-card'), id);
  });
  world.style.setProperty('width',W+'px','important'); world.style.minHeight=(H+WORLD_PAD_TOP)+'px';
  de.style.setProperty('--lanes-w',W+'px');
  main.ev.sort(function(a,b){ return X[a]-X[b] || idx[a]-idx[b]; });
  L.lines.forEach(function(l){ l.ev.sort(function(a,b){ return X[a]-X[b] || idx[a]-idx[b]; }); });
  var geo=draw(world, {lines:lines, main:main, order:order, X:X, pos:pos, h:h, S:S, W:W, H:H, runs:runs, fbOf:fbOf, mains:mains, idx:idx,
                       pastY:pastY, sideOf:sideOf, shift:shiftAll, z:mode.cz, flags:FLG, w:w, boxes:BTG, boxOff:Math.max(14, Math.min(28, fv('b0',u)/2.4))*mode.cz});
  units(world, order, X, w, H, W, main);
  KG={order:order, X:X, pos:pos, w:w, h:h, sideOf:sideOf, rowOf:rowOf, kidH:kidH, kidO:kidO, VO:VO, kids:kids, kidIds:kidIds, P:WORLD_PAD_TOP};
  placeKids();
  /* the frosted slab (units() placed it) ends at the board's foot — at the canvas's when the board fits, never short of the
     canvas less its top padding (the engine's place() would lay the page out again every 250ms) — its height corrected by
     the difference, whatever its box; and the world ends where it does, in place()'s own terms (two different heights
     ping-pong in its ResizeObserver: WebKit's "loop completed with undelivered notifications") */
  var slab=document.getElementById('glass-slab');
  if(slab){
    /* (sim1111h A6: a phone on its side: the board does not fit the room the rail leaves, yet ends above the canvas's foot; the slab stopped with it and the
       page's own pastel showed in a strip along the foot. The slab never ends short of the canvas, fitted or not) */
    var foot=Math.ceil((room && y1-y0<=A) ? room.ch-room.pt : Math.max(H+WORLD_PAD_TOP, room ? room.ch-room.pt : 0));
    for(var k=0;k<3 && slab.offsetTop+slab.offsetHeight!==foot;k++)          // whole px, so its rounded foot cannot drift by one
      de.style.setProperty('--lanes-slab-h', Math.max(0, Math.round((parseFloat(getComputedStyle(slab).height)||0)+foot-(slab.offsetTop+slab.offsetHeight)))+'px');
  }
  /* window._altoLanesGeo — the drawing's geometry, for navigation (stepping,
     the camera) and anything else that needs to know where things are. All
     coordinates are #world layout px WITHOUT WORLD_PAD_TOP (add it for a node's
     style.top / the svg's y); never screen px.
       x[id]        the event's x (its stem, its dot on its line)
       y[id]        its card's centre y
       h[id]        its card's height
       W, H         the drawing's size
       mainY        the main line's y in the present
       lines[]      main first, then the characters: {id, label, color, side,
                    from, to, ev: [own event ids, by x], y: track y (main: mainY),
                    x0, x1: where the line runs, sd: -1 above / 1 below,
                    pr: [the main-line events where it is on the page]}
       at[id]       {x, y, line, flash}: where the event sits on its line — the
                    main line's dot (on the past track for a flashback event,
                    flash = its flashback id), or the character's track
       presence[lineId]  [{id, x, y}] in x order: where the character's line
                    meets the main line (x is spread around the event's x when
                    several characters are there; y the main / past track)
       detours[]    one per flashback run, by x: {id, label, range ("1987–1994"),
                    nodes: [ids], x0, x1 (the whole detour, lead-in to lead-out),
                    d0, d1 (where the main line leaves / rejoins the present y),
                    f0, f1 (the flat past stretch), y (the past track's y),
                    prev, next (the present events either side, or null)} */
  window._altoLanesGeo={boxes:BTG.map(function(t){ return {id:t.id, label:t.label, on:t.on, x:t.x, y:t.y}; }), flags:FLG.map(function(f){ return {id:f.id, label:f.label, x:f.x, x2:f.x2, row:f.row, y:f.y}; }), x:X, y:pos, h:h, lines:lines, W:W, H:H, mainY:main.y, at:geo.at, presence:geo.presence,
    detours:runs.map(function(r){ return {id:r.id, label:r.label, range:r.range, nodes:r.nodes.slice(), x0:r.x0, x1:r.x1,
      d0:r.d0, d1:r.d1, f0:r.f0, f1:r.f1, y:r.y, prev:r.prev, next:r.next}; })};
  if(KG){ window._altoLanesGeo.kids=KG.geoK||{}; window._altoLanesGeo.fams=KG.fams||{}; window._altoLanesGeo.VO=KG.VO||{}; }
  _actBands=ACT_SEQS.map(function(){ return {startY:0, endY:H}; });
  /* the bars and the rail arrive after the first layout: lay out again if the room they leave changed */
  window._altoLanesH=hIn;
  if(!window._altoLanesRefit){ window._altoLanesRefit=1;
    var again=function(){ var f=window._altoLanesFit, r2=lanesRoom(world); if(!f || !f.room || !r2 || !window._altoLanesH || de.classList.contains('mobile')) return;
      if(Math.abs(r2.b-f.room.b)>6 || Math.abs(r2.top-f.room.top)>6 || Math.abs(r2.ch-f.room.ch)>6) window._altoLanes(window._altoLanesH); };
    [700, 1800].forEach(function(ms){ setTimeout(again, ms); });
    window.addEventListener('load', function(){ setTimeout(again, 300); });
    /* a phone's turn (sim1112b S6): its second resize changes the height alone (Safari's bars come up, 874 x 402 -> 874 x 292), which nothing else lays out for, so the
       board stayed fitted to the taller box and its cards were 1.5x a fresh open's. Fit again in the room that is left, the cards measured afresh (their compact
       form has its own heights) */
    var rt=0; window.addEventListener('resize', function(){ clearTimeout(rt); rt=setTimeout(function(){
      var f=window._altoLanesFit, r2=lanesRoom(world); if(!f || !f.room || !r2 || !window._altoLanesH || de.classList.contains('mobile')) return;
      if(Math.abs(r2.b-f.room.b)>6 || Math.abs(r2.top-f.room.top)>6 || Math.abs(r2.ch-f.room.ch)>6){
        try{ if(typeof initLayout==='function'){ initLayout(); if(window._applyActiveFilters) window._applyActiveFilters(); } else again(); }catch(x){ again(); } } }, 220); }); }
  /* the first time: open at the start of time, not the engine's centre */
  if(!window._altoLanesOpened){ window._altoLanesOpened=1; var cv=document.getElementById('canvas'); if(cv){ cv.scrollLeft=0; setTimeout(function(){ if(!window._focusedNodeId) cv.scrollLeft=0; }, 60); } }
  var svgR=document.getElementById('river-svg'); if(svgR) svgR.innerHTML='';
  /* last of all, the world ends where the slab now does, in the engine's place()'s own terms: two different heights
     ping-pong in its ResizeObserver (WebKit: "loop completed with undelivered notifications") */
  var sl=document.getElementById('glass-slab');
  if(sl && sl.offsetHeight){ var wcs=getComputedStyle(world), pads=(parseFloat(wcs.paddingTop)||0)+(parseFloat(wcs.paddingBottom)||0);
    var mh=Math.max(0, sl.offsetTop+sl.offsetHeight-pads)+'px'; if(world.style.minHeight!==mh) world.style.minHeight=mh; }
  fitStage(KSHOW);                 // (once more, now that the world and the slab have their final heights)
  return true;
}
/* ── child nodes: where they stand ────────────────────────────────────────────
   The Expanded view (and a family opened in the Compact view): outline-style from the parent on the far side of the line,
   one row each, KIDLY apart, each depth KIDIND further in, joined by an elbow off a rail down the parent's left. The Compact view
   tucks them: hidden, a chip on the parent. Called after every layout, and on its own when a family opens or shuts. */
/* a path from a to b round boxes ([x0,y0,x1,y1], 8 px clear) on a 12 px grid, A*, four ways, a turn costing extra: the board's own px;
   null where there is no way within the box given (lanes.py outline connectors, lanes_nav.py cross-references) */
window._altoLanesRoute=function(a, b, boxes, X0, Y0, W, H){
  var C=12, P8=8, cw=Math.ceil(W/C), ch=Math.ceil(H/C), N=cw*ch; if(N>400000 || cw<2 || ch<2) return null;
  var blk=new Uint8Array(N);
  boxes.forEach(function(r){ var x0=Math.max(0, Math.floor((r[0]-P8-X0)/C)), x1=Math.min(cw-1, Math.floor((r[2]+P8-X0)/C)), y0=Math.max(0, Math.floor((r[1]-P8-Y0)/C)), y1=Math.min(ch-1, Math.floor((r[3]+P8-Y0)/C));
    for(var y=y0;y<=y1;y++) for(var x=x0;x<=x1;x++) blk[y*cw+x]=1; });
  function cell(p){ return [Math.max(0, Math.min(cw-1, Math.round((p[0]-X0)/C))), Math.max(0, Math.min(ch-1, Math.round((p[1]-Y0)/C)))]; }
  var s=cell(a), e=cell(b), si=s[1]*cw+s[0], ei=e[1]*cw+e[0]; blk[si]=0; blk[ei]=0;
  var g=new Float32Array(N*4).fill(1e9), from=new Int32Array(N*4).fill(-1), hp=[], DX=[1,-1,0,0], DY=[0,0,1,-1];
  function h(i){ return Math.abs(i%cw-e[0])+Math.abs(((i/cw)|0)-e[1]); }
  function push(k, f){ hp.push([f,k]); var i=hp.length-1; while(i>0){ var q=(i-1)>>1; if(hp[q][0]<=hp[i][0]) break; var t=hp[q]; hp[q]=hp[i]; hp[i]=t; i=q; } }
  function pop(){ var top=hp[0], last=hp.pop(); if(hp.length){ hp[0]=last; var i=0; for(;;){ var l=2*i+1, r=l+1, m=i; if(l<hp.length && hp[l][0]<hp[m][0]) m=l; if(r<hp.length && hp[r][0]<hp[m][0]) m=r; if(m===i) break; var t=hp[m]; hp[m]=hp[i]; hp[i]=t; i=m; } } return top; }
  for(var d=0;d<4;d++){ g[si*4+d]=0; push(si*4+d, h(si)); }
  var end=-1, n=0;
  while(hp.length && n++<400000){ var it=pop(), k=it[1], i=k>>2, dd=k&3; if(it[0]-h(i)>g[k]+1e-6) continue; if(i===ei){ end=k; break; }
    var x=i%cw, y=(i/cw)|0;
    for(var nd=0;nd<4;nd++){ var nx=x+DX[nd], ny=y+DY[nd]; if(nx<0||ny<0||nx>=cw||ny>=ch) continue; var j=ny*cw+nx; if(blk[j]) continue;
      var c=g[k]+1+(nd!==dd ? 4 : 0), kk=j*4+nd; if(c<g[kk]){ g[kk]=c; from[kk]=k; push(kk, c+h(j)); } } }
  if(end<0) return null;
  var pts=[]; for(var k2=end;k2>=0;k2=from[k2]){ var i2=k2>>2; pts.push([X0+(i2%cw)*C, Y0+((i2/cw)|0)*C]); }
  pts.reverse();
  /* the ends exactly where asked, joined square to the grid (a short jog where they sit between its lines) */
  var p0=pts[0], pN=pts[pts.length-1]; pts.unshift([a[0], p0[1]]); pts.unshift(a.slice()); pts.push([b[0], pN[1]]); pts.push(b.slice());
  var out=[pts[0]]; for(var q=1;q<pts.length-1;q++){ var u=out[out.length-1], v=pts[q], w2=pts[q+1]; if((u[0]===v[0] && v[0]===w2[0]) || (u[1]===v[1] && v[1]===w2[1])) continue; out.push(v); }
  out.push(pts[pts.length-1]); return out;
};
function placeKids(){
  var world=document.getElementById('world'), G=KG; if(!world) return;
  var svg=document.getElementById('lanes-svg'), old=svg && svg.querySelector('.ln-kids'); if(old) old.remove();
  world.querySelectorAll('.ln-chip,.ln-otag').forEach(function(c){ c.remove(); });
  world.querySelectorAll('.node.ln-kid,.node.ln-has-kids').forEach(function(n){ n.classList.remove('ln-kid','ln-kid-shut','ln-has-kids','ln-open','ln-sd-1','ln-sd1'); });
  var geoK={}, fams={};
  if(G && kidsOn()){
    var g=svg ? el('g',{'class':'ln-kids'}, svg) : null, P=G.P, ex=expandedNow(), later=[], FR=null;
    G.order.forEach(function(root){
      var fam=famOf(G.kids, root, 1, []); if(!fam.length) return;
      var rn=document.getElementById('node-'+root), rc=rn && rn.querySelector('.node-card'); if(!rn || !rc) return;
      fams[root]=fam.map(function(f){ return f.id; });
      var sd=G.sideOf[root], open=openNow(root), left0=G.X[root]-G.w[root]/2, far=G.pos[root]+P+sd*(G.h[root]||120)/2, r=0;
      var op=open ? outPlan(root, fam) : null, ol=op && outOn(root, fam), fa=ol ? outFan(op, fam.map(function(q){ return q.id; })) : null, fs=fa ? fanShift(G.X[root], fa) : 0, vo=(G.VO||{})[root]||0, tops={};
      rn.classList.add('ln-has-kids', 'ln-sd'+sd); if(open) rn.classList.add('ln-open');
      if(!ex && !de.classList.contains('alto-editing')){
        var b=document.createElement('button'); b.type='button'; b.className='ln-chip'; b.setAttribute('data-root', root);
        b.textContent=(open ? '▴ hide' : '▾ '+fam.length+' inside');
        b.title=open ? 'Tuck the '+(fam.length===1 ? 'entry' : fam.length+' entries')+' back behind this card' : 'Open the '+(fam.length===1 ? 'entry' : fam.length+' entries')+' inside this card (or press Down)';
        b.setAttribute('aria-expanded', open ? 'true' : 'false'); rc.appendChild(b);
        if(open && op){ otag(root, ol, rc, b.offsetWidth+14+8); }
      } else if(ex && op && !de.classList.contains('alto-editing') && !de.classList.contains('printing')){ otag(root, ol, rc, 14); }
      fam.forEach(function(f){
        var kn=document.getElementById('node-'+f.id), kc=kn && kn.querySelector('.node-card'); if(!kn || !kc) return;
        kn.classList.add('ln-kid'); kn.setAttribute('data-ln', (L.ev[f.id]||{}).l||'main');
        var lp=rn.getAttribute('data-lp'); if(lp) kn.setAttribute('data-lp', lp); else kn.removeAttribute('data-lp');
        if(!open){ kn.classList.add('ln-kid-shut'); return; }
        var q=ol ? op[f.id] : null, kw=q ? q[2] : KIDW;
        var kl=q ? G.X[root]+fs+q[0]-kw/2 : left0+KIDIND*f.d, kx=kl+kw/2, kcy=q ? far+sd*(vo+q[1]) : far+sd*(KIDGAP+KIDH/2+r*KIDLY); r++;
        kn.style.left=kx+'px'; kn.style.top=kcy+'px'; if(q) kn.style.setProperty('--kw', kw+'px'); else kn.style.removeProperty('--kw');
        var pid=nestOf(f.id), pl, pb;
        if(pid===root){ pl=left0; pb=far; } else { var pg=geoK[pid]; pl=pg ? pg.x-pg.w/2 : left0; pb=pg ? pg.y+P+sd*KIDH/2 : far; }
        geoK[f.id]={x:kx, y:kcy-P, w:kw, h:KIDH, root:root, parent:pid, d:f.d};
        if(q){ if(g){ var px=pid===root ? G.X[root] : (geoK[pid] ? geoK[pid].x : G.X[root]), pm=sd*(kcy-pb), ct=kcy-sd*KIDH/2;
            (tops[pid]=tops[pid]||[]).push({id:f.id, x:kx, cy:kcy, ct:ct, px:px, pb:pb}); }
          var nd0=NODES.filter(function(q2){ return q2.id===f.id; })[0]; if(nd0){ nd0.displayX=kx; nd0.y=kcy-P; } return; }
        var nd=NODES.filter(function(q){ return q.id===f.id; })[0]; if(nd){ nd.displayX=kx; nd.y=kcy-P; }
        if(g){ var rx=pl+12, rr=8;
          el('path',{'class':'ln-kidline', d:'M'+rx+' '+pb+' V'+(kcy-sd*rr)+' Q'+rx+' '+kcy+' '+(rx+rr)+' '+kcy+' H'+kl}, g);
          el('circle',{'class':'ln-kiddot', cx:kl, cy:kcy, r:3}, g); }
      });
      /* an outline's connectors: a card under its parent hangs from a bus halfway down the gap (a card on the parent's own row, a flank, from its side) */
      var kh=function(m){ var e=document.querySelector('#node-'+m+' .node-card'); return (e && e.offsetHeight) || KIDH; };
      /* every card on the board where it really stands, in the svg's own px, once every family is placed (measured: the plan's heights and
         frames are not the cards', and a neighbour family's outline can reach under this one) */
      var famR=function(){ if(FR) return FR; FR={}; var Mx=svg.getScreenCTM(); if(!Mx) return FR; var inv=Mx.inverse(), pt=svg.createSVGPoint();
        [].forEach.call(document.querySelectorAll('#world .node[id^="node-"]:not(.ln-kid-shut)'), function(n){ var m=n.id.slice(5), e=n.querySelector('.node-card'); if(!e) return; var r=e.getBoundingClientRect(); if(!r.width) return;
          pt.x=r.left; pt.y=r.top; var a2=pt.matrixTransform(inv); pt.x=r.right; pt.y=r.bottom; var b2=pt.matrixTransform(inv); FR[m]=[a2.x, a2.y, b2.x, b2.y]; }); return FR; };
      /* does a run of points cross any card but the two it joins (2 px inside the card's edge) */
      var crosses=function(pts, skip){ var R=famR(); for(var k=1;k<pts.length;k++){ var a=pts[k-1], b=pts[k], x0=Math.min(a[0], b[0]), x1=Math.max(a[0], b[0]), y0=Math.min(a[1], b[1]), y1=Math.max(a[1], b[1]);
        for(var m in R){ if(skip.indexOf(m)>=0) continue; var r=R[m]; if(x1>r[0]+2 && x0<r[2]-2 && y1>r[1]+2 && y0<r[3]-2) return true; } } return false; };
      var gridRoute=function(a, b, skip){ var R=famR(), rs=[]; for(var m in R) if(skip.indexOf(m)<0) rs.push(R[m]);
        var X0=Math.min(a[0], b[0])-300, X1=Math.max(a[0], b[0])+300, Y0=Math.min(a[1], b[1])-300, Y1=Math.max(a[1], b[1])+300;
        return window._altoLanesRoute ? window._altoLanesRoute(a, b, rs.filter(function(r){ return r[2]>X0 && r[0]<X1 && r[3]>Y0 && r[1]<Y1; }), X0, Y0, X1-X0, Y1-Y0) : null; };
      /* a vertical run at x from y1 to y2 meets a card of this family (not skip; half: the width the run itself takes) */
      var blocked=function(x, y1, y2, skip, half){ var lo=Math.min(y1, y2)+1, hi=Math.max(y1, y2)-1, R=famR(); return Object.keys(R).some(function(m){ if(m===skip) return false;
        var r=R[m]; return x>r[0]-half-2 && x<r[2]+half+2 && r[3]>lo && r[1]<hi; }); };
      if(ol && g) later.push(function(){ Object.keys(tops).forEach(function(pid){
        var L0=tops[pid], pg=pid===root ? null : geoK[pid], pw=pg ? pg.w : G.w[root], ph=pg ? kh(pid) : (G.h[root]||120), below=L0.filter(function(t){ return sd*(t.ct-t.pb)>=0; }),
            mid=below.length ? Math.min.apply(null, below.map(function(t){ return sd*(t.ct-t.pb); })) : 0, by=L0[0].pb+sd*mid/2;
        L0.forEach(function(t){
          if(sd*(t.ct-t.pb)<0){ var fx=t.x<t.px ? t.px-pw/2 : t.px+pw/2, tx=t.x<t.px ? t.x+(geoK[t.id].w/2) : t.x-(geoK[t.id].w/2);
            el('path',{'class':'ln-kidline', 'data-k':t.id, 'data-p':pid, d:'M'+fx+' '+(t.pb-sd*KIDH/2)+' H'+tx}, g); return; }
          /* the connector: down from the parent to a bus halfway, along it, down to the card. Where another card stands in the column the
             run goes down the column's gutter and comes in from the card's side, as a list's does; where the parent's own drop meets a card
             it leaves from the parent's side; and where any of it would still cross a card (a neighbour family's outline can reach under
             this one) it is routed round every card on a grid (Board 2026-11-27, civ-pro Outline all: 111 connectors through cards) */
          var tw=geoK[t.id].w, S=[[t.px, t.pb], [t.px, by]], pts, dot;
          if(blocked(t.px, t.pb, by, '', 0)){ var pcy=t.pb-sd*ph/2, sides=t.x<t.px ? [-1, 1] : [1, -1];
            for(var si=0; si<2; si++){ var sx=t.px+sides[si]*(pw/2+9); if(!blocked(sx, pcy, by, '', 0)){ S=[[t.px+sides[si]*pw/2, pcy], [sx, pcy], [sx, by]]; break; } } }
          if(blocked(t.x, by, t.ct, t.id, tw/2)){ var gx=t.x-tw/2-9; pts=S.concat([[gx, by], [gx, t.cy], [t.x-tw/2, t.cy]]); dot=[t.x-tw/2, t.cy]; }
          else { pts=S.concat([[t.x, by], [t.x, t.ct]]); dot=[t.x, t.ct]; }
          if(crosses(pts, [t.id, pid===root ? root : pid])){ var rr=gridRoute([t.px, t.pb], [t.x, t.ct], [t.id, pid===root ? root : pid]); if(rr){ pts=rr; dot=[t.x, t.ct]; } }
          el('path',{'class':'ln-kidline', 'data-k':t.id, 'data-p':pid, d:'M'+pts.map(function(q){ return q[0]+' '+q[1]; }).join(' L')}, g);
          el('circle',{'class':'ln-kiddot', cx:dot[0], cy:dot[1], r:3}, g); });
      }); });
    });
    later.forEach(function(f){ f(); });
  }
  if(G){ G.geoK=geoK; G.fams=fams; }
  if(window._altoLanesGeo){ window._altoLanesGeo.kids=geoK; window._altoLanesGeo.fams=fams; }
  kidsDim(); viewSwitch(Object.keys(fams).length>0);
  KSHOW=Object.keys(geoK).length>0; fitStage(KSHOW);
}
/* the whole stack inside the window: where children are showing and the cards stand beyond the room (130 px of header above, 110 of
   player bar and nav below), the stage (#world, which carries #lanes-svg) is scaled from its top to fit and centred in that room.
   Measured on the cards themselves, highest top to lowest bottom, so BOTH sides count. Never in print; the layout itself is untouched. */
function fitStage(on){
  var world=document.getElementById('world'); if(!world) return;
  world.style.translate=''; world.style.scale='';                    // (the individual properties, so the overview's own transform is left alone)
  if(!on || de.classList.contains('printing') || PRINTX) return;
  var wr=world.getBoundingClientRect(), k=(wr.width && world.offsetWidth) ? wr.width/world.offsetWidth : 1;
  /* from where the cards stand in the world (centre top + height), not from their rects: a card still easing in would be measured where it started */
  var lt=1e9, lb=-1e9;
  world.querySelectorAll('.node').forEach(function(n){
    if(getComputedStyle(n).display==='none') return; var c=n.querySelector('.node-card'), y=parseFloat(n.style.top); if(!c || !c.offsetHeight || isNaN(y)) return;
    lt=Math.min(lt, y-c.offsetHeight/2); lb=Math.max(lb, y+c.offsetHeight/2); });
  var TOPB=130, BOTB=110, room=window.innerHeight-TOPB-BOTB, ext=(lb-lt)*k;
  if(!(ext>0) || ext<=room+1) return;
  var sc=Math.max(.3, room/ext), T=TOPB+(room-ext*sc)/2, ty=(T-wr.top)/k-sc*lt;
  world.style.transformOrigin='0 0'; world.style.translate='0 '+ty.toFixed(2)+'px'; world.style.scale=sc.toFixed(4);
}
/* a child dims with its parent (any filter that dims a card: a chip, a slot, a relation) */
function kidsDim(){
  document.querySelectorAll('#world .node.ln-kid').forEach(function(n){
    var rc=document.querySelector('#node-'+rootOf(n.id.slice(5))+' .node-card'), kc=n.querySelector('.node-card');
    var dim=!!(rc && (rc.classList.contains('dimmed') || rc.classList.contains('rel-dimmed') || rc.classList.contains('ent-dimmed')));
    if(kc && kc.classList.contains('ln-kid-dim')!==dim) kc.classList.toggle('ln-kid-dim', dim);
  });
}
/* the Compact | Expanded switch, only on a timeline that has something nested: a tab of the right rail, straight under Scene
   (Luke 2026-11-26, "move the expanded view square toggle to the right sidebar below scene"); a page with no rail keeps it bottom right */
function viewSwitch(has){
  var b=document.getElementById('ln-view');
  if(!has || !kidsOn() || document.getElementById('canvas')===null){ if(b) b.remove(); var a0=document.getElementById('ln-olall'); if(a0) a0.remove(); return; }
  if(!b){
    b=document.createElement('button'); b.type='button'; b.id='ln-view'; b.tabIndex=0;
    b.addEventListener('click', function(){ closeOffer(); setView(!EXPD); });
    document.body.appendChild(b);
    var cv=document.getElementById('canvas');                       // seen while the pointer is on the board or on its corner, a moment after it leaves
    [cv, b].forEach(function(t){
      t.addEventListener('pointerenter', function(){ clearTimeout(VT); b._over=1; b.classList.add('ln-show'); });
      t.addEventListener('pointerleave', function(){ clearTimeout(VT); b._over=0; VT=setTimeout(function(){ if(!document.getElementById('ln-offer') && !b._over) b.classList.remove('ln-show'); }, 1100); });
    });
    offerSoon();
  }
  seatView(b);
  var icon=EXPD
    ? '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="15" height="5" rx="1.5"/><path d="M6 8v9h4"/><rect x="10" y="14" width="11" height="6" rx="1.5"/></svg>'
    : '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="15" height="11" rx="2"/><path d="M6 18h12M9 21h6"/></svg>';
  var tip=EXPD ? 'Expanded view: entries inside another are shown beneath it. Click for the Compact view.' : 'Compact view: entries inside another are tucked behind it. Click for the Expanded view.';
  if(b.getAttribute('data-v')!==(EXPD ? 'x' : 'c')){ b.setAttribute('data-v', EXPD ? 'x' : 'c'); b.innerHTML=icon; }
  b.title=tip; b.setAttribute('aria-label', tip); b.setAttribute('aria-pressed', EXPD ? 'true' : 'false');
  allSwitch(b);
}
/* the one switch for every branch as an outline: only in the Expanded view, and only where a branch can be one */
function allSwitch(v){
  var a=document.getElementById('ln-olall'), can=EXPD && Object.keys(L.out||{}).length>0;
  if(!can){ if(a) a.remove(); return; }
  if(!a){
    a=document.createElement('button'); a.type='button'; a.id='ln-olall'; a.tabIndex=0;
    a.innerHTML='<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="8.5" y="2.5" width="7" height="4" rx="1"/><path d="M12 6.5v3M5 9.5h14M5 9.5v3M12 9.5v3M19 9.5v3"/><rect x="2.5" y="12.5" width="5" height="3.5" rx="1"/><rect x="9.5" y="12.5" width="5" height="3.5" rx="1"/><rect x="16.5" y="12.5" width="5" height="3.5" rx="1"/><path d="M5 16v3h3"/><rect x="8" y="17.5" width="4" height="3" rx="1"/></svg>';
    a.addEventListener('click', function(){ setOutAll(!OUTALL); });
    [a].forEach(function(t){ t.addEventListener('pointerenter', function(){ v.classList.add('ln-show'); a.classList.add('ln-show'); }); });
  }
  var tip=OUTALL ? 'Every branch is set out as an outline. Click to stack each one in a column again.' : 'Set every branch out as an outline: each level fanned out under its parent';
  a.title=tip; a.setAttribute('aria-label', tip); a.setAttribute('aria-pressed', OUTALL ? 'true' : 'false');
  if(v.classList.contains('ln-show')) a.classList.add('ln-show'); else a.classList.remove('ln-show');
  if(v.nextElementSibling!==a) v.parentNode.insertBefore(a, v.nextSibling);
}
function seatView(b){
  var r=document.getElementById('tab-rail'), s=document.getElementById('bg-toggle');
  if(!r){ if(b.parentNode!==document.body) document.body.appendChild(b); return; }
  if(s && s.parentNode===r){ if(s.nextElementSibling!==b) r.insertBefore(b, s.nextSibling); }
  else if(r.lastElementChild!==b && !(b.nextElementSibling && b.nextElementSibling.id==='ln-olall' && r.lastElementChild===b.nextElementSibling)) r.appendChild(b);
  var a=document.getElementById('ln-olall'); if(a && b.nextElementSibling!==a) r.insertBefore(a, b.nextSibling);
  if(!r._lnSeat && window.MutationObserver){ r._lnSeat=1; new MutationObserver(function(){ var v=document.getElementById('ln-view'); if(v) seatView(v); }).observe(r, {childList:true}); }
}
/* Alto's one-time offer (once a board has entries tucked inside others: the Compact page shows less than it holds): says where the
   switch is and what it does; either answer ends it for good, and the glyph stays as the vanishing toggle after it */
var VT=0, OFFK='alto-compact-offer';
function offerSoon(){
  var done=false; try{ done=!!localStorage.getItem(OFFK); }catch(e){}
  if(done) return;
  setTimeout(function(){
    var fams=(window._altoLanesGeo||{}).fams||{}, n=0; Object.keys(fams).forEach(function(k){ n+=fams[k].length; });
    var b=document.getElementById('ln-view');
    if(!b || !n || EXPD || document.getElementById('ln-offer') || de.classList.contains('alto-editing') || de.classList.contains('mobile') || de.classList.contains('phone-whole')) return;
    try{ localStorage.setItem(OFFK, '1'); }catch(e){}
    var o=document.createElement('div'); o.id='ln-offer'; o.setAttribute('role','status');
    o.innerHTML='<p></p><div class="ln-offer-b"><button type="button" data-a="x">Show Expanded</button><button type="button" data-a="c">Keep Compact</button></div>';
    o.querySelector('p').textContent=(n===1 ? '1 entry is tucked inside another card.' : n+' entries are tucked inside other cards.')+' Expanded lays them out beneath their parent. The switch is on the right, under Scene.';
    o.addEventListener('click', function(e){ var a=e.target.getAttribute && e.target.getAttribute('data-a'); if(!a) return; closeOffer(); if(a==='x') setView(true); });
    document.body.appendChild(o); b.classList.add('ln-show');
    requestAnimationFrame(function(){ requestAnimationFrame(function(){ o.classList.add('ln-on'); }); });
    window._lnOfferT=setTimeout(closeOffer, 14000);
  }, 1800);
}
function closeOffer(){
  clearTimeout(window._lnOfferT); var o=document.getElementById('ln-offer'); if(!o) return;
  o.classList.remove('ln-on'); setTimeout(function(){ o.remove(); }, 300);
  var b=document.getElementById('ln-view'); if(b && !b._over) b.classList.remove('ln-show');
}
function otag(root, ol, rc, ox){
  var ob=document.createElement('button'); ob.type='button'; ob.className='ln-otag'; ob.setAttribute('data-root', root);
  ob.textContent=ol ? '☰ list' : '⑂ outline'; ob.setAttribute('aria-pressed', ol ? 'true' : 'false');
  ob.title=ol ? 'Stack the entries in one column again' : 'Set the entries out as an outline: each level fanned out under its parent, sections side by side';
  rc.appendChild(ob); ob.style.setProperty('--ln-ox', ox+'px');
}
function relayoutNow(){ if(window._altoLanesGeo && window._altoLanesH) window._altoLanes(window._altoLanesH); }
function setOutAll(on){        /* every branch of the Expanded view as an outline, or every one a column */
  OUTALL=!!on; OUTE={}; try{ if(OUTALL) localStorage.setItem(OK_, '1'); else localStorage.removeItem(OK_); }catch(e){}
  relayoutNow(); var v=document.getElementById('ln-view'); if(v) allSwitch(v);
  if(window._altoLanesRestV) window._altoLanesRestV();
  if(window._altoLanesCueLook) window._altoLanesCueLook();
}
function setView(x){
  EXPD=!!x; try{ if(EXPD) localStorage.setItem(VK, 'expanded'); else localStorage.removeItem(VK); }catch(e){}
  OPEN={}; clearKC(); relayoutNow();
  if(window._altoLanesRestV) window._altoLanesRestV();
  if(window._altoLanesCueLook) window._altoLanesCueLook();      // (Extend: the view stays on the main line as the board grows or shrinks)
}
function setOutline(root, on){        /* an opened branch as a list (one column) or as an outline */
  var cv=document.getElementById('canvas'), n=document.getElementById('node-'+root), t0=n ? n.getBoundingClientRect().top : 0;
  if(expandedNow()){ if(!!on===OUTALL) delete OUTE[root]; else OUTE[root]=!!on; }
  else if(on) OUTL[root]=1; else delete OUTL[root];
  relayoutNow();
  if(cv && n){ var d=n.getBoundingClientRect().top-t0; if(Math.abs(d)>1) cv.scrollTop+=d; }
  if(window._altoLanesCueLook) window._altoLanesCueLook();
}
function openFam(root, on){
  if(!on) delete OUTL[root];
  if(!on && KC && rootOf(KC)===root) clearKC();
  var cv=document.getElementById('canvas'), n=document.getElementById('node-'+root), t0=n ? n.getBoundingClientRect().top : 0;
  if(on) OPEN[root]=1; else delete OPEN[root];
  relayoutNow();
  if(cv && n){ var d=n.getBoundingClientRect().top-t0; if(Math.abs(d)>1) cv.scrollTop+=d; }      // the parent stays where it was on the screen
  if(on){ var f=((window._altoLanesGeo||{}).fams||{})[root]||[], k=f.length && document.getElementById('node-'+f[f.length-1]);
    if(k) try{ k.scrollIntoView({block:'nearest', inline:'nearest'}); }catch(e){} }
  if(window._altoLanesCueLook) window._altoLanesCueLook();
}
window._altoLanesKids={open:function(id, on){ openFam(rootOf(id), on!==false); }, outline:function(id, on){ var r=rootOf(id); if(arguments.length>1) setOutline(r, on!==false); return outWant(r); }, outlineAll:function(on){ if(arguments.length) setOutAll(on!==false); return OUTALL; }, view:function(x){ if(arguments.length) setView(x==='expanded' || x===true); return EXPD ? 'expanded' : 'compact'; },
  cursor:function(){ return KC; }, shut:kidShut, nest:nestOf, step:function(d){ return kidStep(d); }, nav:function(id, d){ return kidNav(id, d); }, home:function(){ return kidHome(); },
  grown:function(){ return EXPD || Object.keys(OPEN).length>0; }};      /* (Extend's on while the board holds more than its main line: lanes_ext_js) */
function clearKC(){ if(!KC) return; var n=document.getElementById('node-'+KC); if(n) n.classList.remove('ln-kc'); KC=''; }
function setKC(id){
  clearKC(); var n=document.getElementById('node-'+id); if(!n) return;
  KC=id; n.classList.add('ln-kc'); var c=n.querySelector('.node-card');
  if(c){ if(!c.hasAttribute('tabindex')) c.setAttribute('tabindex','0'); try{ c.focus({preventScroll:true}); }catch(e){} }
  try{ n.scrollIntoView({block:'nearest', inline:'nearest', behavior:(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) ? 'auto' : 'smooth'}); }catch(e){}
}

/* ── box tags ─────────────────────────────────────────────────────────────── */
/* the box tags this board can place: beside an event that is shown, or dated on a board with dated events */
function boxTags(order, fbOf){
  var dated=order.some(function(id){ return L.ev[id].t!=null && !fbOf[id]; }), shown={}; order.forEach(function(id){ shown[id]=1; });
  return (L.bt||[]).filter(function(t){ return t && t.label && (t.node ? shown[t.node] : (t.t!=null && dated)) &&
      (t.on==='axis' || t.on==='main' || !t.on || (lineBy(t.on) && !hidLine(t.on))); })
    .map(function(t){ return {id:t.id, label:t.label, glyph:t.glyph||'', svg:t.svg||'', on:t.on||'axis', at:t.at||'', node:t.node||'', side:t.side||'', t:t.t}; });
}
/* the boxes (HTML, like the line labels): measured, an event's beside its stem, those on the axis kept apart */
function boxRows(world, B, X, w, shiftAll, S, main){
  B.forEach(function(t){
    var d=document.createElement('div'); d.className='lanes-box'; d.setAttribute('data-box', t.id);
    if(t.svg){ var g=document.createElement('span'); g.className='lb-g'; g.innerHTML=t.svg; d.appendChild(g); }
    var lb=document.createElement('span'); lb.className='lb-t'; lb.textContent=t.label; d.appendChild(lb);
    world.appendChild(d); t.el=d; t.w=d.offsetWidth||90;
    if(d.scrollWidth>d.clientWidth+1 || lb.scrollWidth>lb.clientWidth+1) d.title=t.label;
    var a=t.node ? X[t.node] : flagRaw(S, t.t);
    if(a==null){ t.x=null; return; }
    t.x0=t.node ? a : a+shiftAll(a, -1);
    t.x=t.node && t.on!=='axis' ? t.x0+t.w/2+18 : t.x0;           // beside its event's stem, not over it
    t.sx=t.x0;
  });
  var gone=B.filter(function(t){ return t.x==null; }); gone.forEach(function(t){ t.el.remove(); });
  var keepB=B.filter(function(t){ return t.x!=null; }); B.length=0; keepB.forEach(function(t){ B.push(t); });
  var ends={};                                                          // on one line (or the axis): none on another
  B.slice().sort(function(a,b){ return a.x-b.x; }).forEach(function(t){
    var e=ends[t.on]; if(e!=null && t.x-t.w/2<e+8) t.x=e+8+t.w/2;
    t.x=Math.max(t.x, main.x0+t.w/2); ends[t.on]=t.x+t.w/2; });
}

/* ── time flags ──────────────────────────────────────────────────────────── */
var FL_ROW=26;
/* time → x before the detours / cards shifted anything: along the scale's segments, across a squeezed stretch
   in proportion, beyond the ends at the scale's pace */
function flagRaw(S, t){
  var g=S.segs; if(!g.length || t==null) return null;
  if(t<=g[0].t0) return g[0].x0+(t-g[0].t0)*S.s;
  for(var i=0;i<g.length;i++){
    if(g[i].t1!=null && t<=g[i].t1) return g[i].x0+(t-g[i].t0)*S.s;
    if(i+1<g.length && t<g[i+1].t0){ var a=g[i].x1, b=g[i+1].x0; return a+(b-a)*(t-g[i].t1)/(g[i+1].t0-g[i].t1); }
  }
  var z=g[g.length-1]; return z.x1+(t-z.t1)*S.s;
}
/* the flags this board can place: pinned to an event that is shown, or dated on a board with dated events */
function timeFlags(order, fbOf){
  var dated=order.some(function(id){ return L.ev[id].t!=null && !fbOf[id]; }), shown={}; order.forEach(function(id){ shown[id]=1; });
  return (L.tf||[]).filter(function(f){ return f && f.label && (f.node ? shown[f.node] : (f.t!=null && dated)); })
    .map(function(f){ return {id:f.id, label:f.label, at:f.at||'', to:f.to||'', node:f.node||'', color:f.color||'', t:f.t, t2:f.t2}; });
}
/* the pennants (HTML, like the line labels), measured and given rows: left to right, each in the lowest row
   whose last pennant ends before it */
function flagRows(world, F){
  F.sort(function(a,b){ return a.x-b.x; });
  F.forEach(function(f){
    var d=document.createElement('div'); d.className='lanes-flag'; d.setAttribute('data-flag', f.id);
    if(f.color) d.style.setProperty('--flag-c', f.color);
    var era=f.to ? ' – '+f.to : '', tip=f.label+(f.at ? ' ('+f.at+era+')' : '');
    d.title=tip; d.setAttribute('aria-label', tip); d.textContent=f.label; world.appendChild(d); f.el=d;
    f.w=d.offsetWidth||80;
  });
  if(de.classList.contains('phone-whole')){
    /* a phone has no room for rows: flags that would overlap become ONE numbered pennant ("3"); a tap lists them */
    var groups=[], cur=null;
    F.forEach(function(f){ if(cur && f.x<cur.end+10){ cur.list.push(f); cur.end=Math.max(cur.end, f.x+f.w); } else { cur={list:[f], end:f.x+f.w}; groups.push(cur); } });
    groups.forEach(function(g){
      g.list.forEach(function(f){ f.row=0; });
      if(g.list.length<2) return;
      var lead=g.list[0], d=lead.el, n=g.list.length;
      g.list.slice(1).forEach(function(f){ f.el.remove(); f.el=null; });
      d.className='lanes-flag lanes-flag-n'; d.textContent=String(n); d.removeAttribute('title');
      d.setAttribute('aria-label', n+' flags: '+g.list.map(function(f){ return f.label; }).join(', '));
      d.setAttribute('role','button'); d.tabIndex=0; d._flags=g.list;
      d.addEventListener('click', function(e){ e.stopPropagation(); flagList(world, d); });
    });
    return F.length ? 1 : 0;
  }
  var ends=[], rows=0;
  F.forEach(function(f){ var r=0; while(ends[r]!=null && ends[r]+10>f.x) r++;
    f.row=r; ends[r]=f.x+f.w; rows=Math.max(rows, r+1); });
  return rows;
}
/* the numbered pennant's list: each flag's label and date, under the pennant; a tap anywhere else shuts it */
function flagList(world, d){
  var old=world.querySelector('.lanes-flaglist'), same=old && old._for===d; if(old) old.remove(); if(same) return;
  var l=document.createElement('div'); l.className='lanes-flaglist'; l._for=d;
  d._flags.forEach(function(f){ var r=document.createElement('div'), era=f.to ? ' – '+f.to : '';
    r.innerHTML='<b></b><span></span>'; r.firstChild.textContent=f.label; r.lastChild.textContent=f.at ? f.at+era : ''; l.appendChild(r); });
  l.style.left=d.style.left; l.style.top=(parseFloat(d.style.top)+16)+'px'; world.appendChild(l);
  var shut=function(){ l.remove(); document.removeEventListener('click', shut, true); };
  setTimeout(function(){ document.addEventListener('click', shut, true); }, 0);
}
/* a smooth path through levels [{x0, x1, y}]: flat along each, an S between
   one and the next whose ends are level (so a dip meets the main line square
   on, and leaves it the same way) */
function levelsPath(lv){
  var d='M'+lv[0].x0+' '+lv[0].y;
  lv.forEach(function(v,i){
    if(i){ var p=lv[i-1];
      if(Math.abs(p.y-v.y)<.5) d+=' L'+v.x0+' '+v.y;
      else { var m=(p.x1+v.x0)/2; d+=' C'+m+' '+p.y+' '+m+' '+v.y+' '+v.x0+' '+v.y; } }
    if(v.x1>v.x0+.5) d+=' L'+v.x1+' '+v.y;
  });
  return d;
}
function draw(world, G){
  var lines=G.lines, main=G.main, order=G.order, X=G.X, pos=G.pos, h=G.h, S=G.S, W=G.W, H=G.H, runs=G.runs, fbOf=G.fbOf;
  var old=document.getElementById('lanes-svg'); if(old) old.remove();
  var P=WORLD_PAD_TOP, svg=el('svg',{id:'lanes-svg', width:W, height:H+P});
  world.insertBefore(svg, world.firstChild.nextSibling);
  var col=function(l){ return l.id==='main'?'var(--accent)':l.color; };
  var my=main.y+P, py=G.pastY+P, at={}, presence={};
  var LB={}; lines.forEach(function(l){ LB[l.id]=l; });
  var lineOfEv=function(id){ return LB[L.ev[id].l]||main; };
  /* where each event sits on its line */
  order.forEach(function(id){ var ln=lineOfEv(id);
    at[id]={x:X[id], y:ln===main?(fbOf[id]?G.pastY:main.y):ln.y, line:ln.id, flash:fbOf[id]||''}; });
  /* the past: a tinted band behind each detour, its label at the start of the flat stretch */
  runs.forEach(function(r){
    var g=el('g',{'data-ln':'main', 'class':'ln-past', 'data-fb':r.id},svg);
    el('rect',{'class':'ln-past-band', x:r.d0+DRAMP*.42, y:my+9, width:Math.max(10,r.d1-r.d0-DRAMP*.84), height:py-my+21, rx:14},g);
    r.tagEl.style.left=(r.f0+4)+'px'; r.tagEl.style.top=py+'px';   // on the past track, as a character's label sits on its line
  });
  /* the time axis: a ruler along the bottom of the page, ticks where the numbers
     are round; it stops at each detour — the present's clock does not run there */
  var ay=H+P-52, tk=el('g',{'class':'ln-axis'},svg);
  var nums=axisNums(order, fbOf);                              // nothing dated: no clock to show
  var dts=order.filter(function(id){ return L.ev[id].t!=null && !fbOf[id]; }).map(function(id){ return L.ev[id].t; });
  var tlo=Math.min.apply(null,dts.concat([Infinity])), thi=Math.max.apply(null,dts.concat([-Infinity]));   // the clock runs only where the material dates it
  var inDetour=function(x){ return runs.some(function(r){ return x>r.x0-4 && x<r.x1+4; }); };
  if(nums || G.flags.length){ var cuts=[main.x0]; runs.forEach(function(r){ cuts.push(r.x0, r.x1); }); cuts.push(main.x1);
    for(var c=0;c+1<cuts.length;c+=2) if(cuts[c+1]>cuts[c]+60) el('line',{'class':'ln-rule', x1:cuts[c], x2:cuts[c+1], y1:ay, y2:ay},tk); }
  S.segs.forEach(function(sg){
    if(sg.t1==null || sg.t1<=sg.t0 || !nums) return;
    var step=nice(220/S.s); if(step<1) step=1;
    for(var v=Math.ceil(Math.max(sg.t0,tlo)/step)*step; v<=Math.min(sg.t1,thi)+1e-9; v+=step){
      var raw=sg.x0+(v-sg.t0)*S.s, x=raw+G.shift(raw, -1); if(x<main.x0+30 || x>main.x1-30 || inDetour(x)) continue;
      el('line',{'class':'ln-tick', x1:x, x2:x, y1:ay, y2:ay+8},tk);
      var tl=el('text',{'class':'ln-ticklbl', x:x, y:ay+22, 'text-anchor':'middle'},tk); tl.textContent=String(Math.round(v*100)/100);
    }
  });
  /* time flags: a hairline pole from the pennant down to the time axis, a diamond where it stands, a bracket along the axis for an era */
  if(G.flags.length){ var fg=el('g',{'class':'ln-flags'},svg);
    G.flags.forEach(function(f){
      var g=el('g',{'class':'ln-flag', 'data-flag':f.id},fg), c=f.color||'';
      if(c) g.style.setProperty('--flag-c', c);
      /* the pole stands behind the cards: it is cut wherever a card is in its way, so a glass card never shows it through */
      var cuts=[]; order.forEach(function(id){ var hw=(G.w[id]||270)/2+4, hh=(h[id]||120)/2+10;
        if(Math.abs(X[id]-f.x)<hw) cuts.push([pos[id]+P-hh, pos[id]+P+hh]); });
      cuts.sort(function(a,b){ return a[0]-b[0]; });
      var yy=f.y+P+9, orphan=!f.el;            // a flag folded into a numbered pennant keeps its diamond, not a pole to nothing
      if(orphan) cuts=[[-1e9, 1e9]];
      cuts.forEach(function(c){ if(c[0]>yy) el('line',{'class':'ln-fpole', x1:f.x, x2:f.x, y1:yy, y2:Math.min(c[0],ay)},g); yy=Math.max(yy,c[1]); });
      if(yy<ay) el('line',{'class':'ln-fpole', x1:f.x, x2:f.x, y1:yy, y2:ay},g);
      if(f.x2!=null && f.x2-f.x>6) el('rect',{'class':'ln-fera', x:f.x, y:ay-2, width:f.x2-f.x, height:4, rx:2},g);
      el('path',{'class':'ln-fdia', d:'M'+f.x+' '+(ay-6)+' l5.5 6 l-5.5 6 l-5.5 -6 Z'},g);
      var d=f.el; if(d){ d.style.left=f.x+'px'; d.style.top=(f.y+P)+'px'; } });
  }
  /* box tags: a flat dashed box on its line (a 1px stub to the line) or standing above the time axis; not a node */
  if(G.boxes.length){ var bg=el('g',{'class':'ln-boxes'},svg);
    G.boxes.forEach(function(t){
      var d=t.el, hh=d.offsetHeight||24, y, by;
      if(t.on==='axis'){ y=ay-24; by=ay; }
      else { var ln=t.on==='main' ? main : LB[t.on];
        if(!ln || (ln!==main && !ln.drawn)){ d.style.display='none'; t.y=null; return; }
        by=(ln===main ? main.y : ln.y)+P;
        var sd=t.side==='below' ? 1 : t.side==='above' ? -1 : (ln===main ? -1 : ln.sd);
        y=by+sd*G.boxOff; }
      d.style.display=''; d.style.left=t.x+'px'; d.style.top=y+'px'; t.y=y-P;
      var sx=Math.max(t.x-t.w/2+8, Math.min(t.x+t.w/2-8, t.sx)), ey=by>y ? y+hh/2 : y-hh/2;
      el('line',{'class':'ln-bstub', x1:sx, x2:sx, y1:ey, y2:by},bg); });
  }
  /* who is on the page at each main-line event, spread around its stem: lines
     from above to the left of lines from below, the outermost track outermost */
  var at0={};
  order.forEach(function(id){
    var here=lines.slice(1).filter(function(l){ return l.drawn && l.pr.indexOf(id)>=0; });
    here.sort(function(a,b){ return (a.sd-b.sd) || (a.sd<0 ? b.track-a.track : a.track-b.track); });
    here.forEach(function(l,k){ (at0[l.id]=at0[l.id]||{})[id]=X[id]+(k-(here.length-1)/2)*SPREAD; });
  });
  /* each character: a solid line along its track that dips onto the main line
     wherever the character is on the page — meeting it square on, marked with a
     ring — and leaves again; at adjacent events it rides along beside the main
     line instead of bouncing up and down. Its own events sit on its track. */
  var marks=[];
  lines.slice(1).forEach(function(l){
    if(!l.drawn){ if(l.tagEl) l.tagEl.remove(); return; }
    var ty=l.y+P, g=el('g',{'data-ln':l.id},svg), c=col(l);
    var stops=l.pr.map(function(id){ var ln=lineOfEv(id);
      return {a:1, id:id, x:at0[l.id][id], y:(ln===main ? (fbOf[id]?py:my) : ln.y+P), main:ln===main, fb:fbOf[id]||''}; })
      .concat(l.ev.map(function(id){ return {a:0, id:id, x:X[id], y:ty}; }))
      .sort(function(p,q){ return p.x-q.x || q.a-p.a; });
    var R=function(s){ return Math.max(RAMP_MIN, Math.min(RAMP_MAX, Math.abs(ty-s.y)*1.25)); };
    var x0=l.x0+l.tagW+4, lv=[{x0:x0, x1:x0, y:ty}], top=function(){ return lv[lv.length-1]; };
    var hug=Math.min(HUG0+l.track*HUG_STEP, Math.abs(ty-my)*.6);          // beside the main line, inside the band on a compact board
    stops.forEach(function(s,i){
      var p=stops[i-1], q=stops[i+1];
      if(!s.a){ if(top().y!==ty) lv.push({x0:s.x, x1:s.x, y:ty}); else top().x1=s.x; return; }
      var Rin=R(s), Rout=R(s);
      if(p && p.a && p.low){ /* already beside the main line: down onto this event */ }
      else if(p && p.a && p.direct){ }
      else {
        if(p && !p.a) Rin=Math.max(22, Math.min(Rin, s.x-p.x-14));
        else if(p && p.a) Rin=p.rq||Rin;
        top().x1=Math.max(top().x0, s.x-Rin);
      }
      lv.push({x0:s.x, x1:s.x, y:s.y});
      if(q && q.a){
        var gap=q.x-s.x, adj=s.main && q.main && Math.abs(s.y-q.y)<.5 && (s.fb||'')===(q.fb||'') &&
          Math.abs(G.mains.indexOf(s.id)-G.mains.indexOf(q.id))<=1;
        if(adj){ s.low=1; var r=Math.min(30, gap/3), sg=ty>s.y?1:-1;
          if(gap>2*r+6) lv.push({x0:s.x+r, x1:q.x-r, y:s.y+sg*hug});
          return; }
        if(Math.abs(s.y-q.y)>.5 && gap<R(s)+R(q)+MINRUN){ s.direct=1; return; }
        var k=Math.min(1, (gap-MINRUN)/(R(s)+R(q))); Rout=Math.max(18, R(s)*k); s.rq=Math.max(18, R(q)*k);
      } else if(q){ Rout=Math.max(22, Math.min(Rout, q.x-s.x-14)); }
      lv.push({x0:s.x+Rout, x1:s.x+Rout, y:ty});
    });
    if(top().y!==ty) lv.push({x0:top().x1+RAMP_MAX, x1:top().x1+RAMP_MAX, y:ty});
    top().x1=Math.max(top().x1, l.x1);
    var d=levelsPath(lv);
    el('path',{'class':'ln-hit', d:d},g);
    el('path',{'class':'ln-br', d:d, stroke:c},g);
    el('circle',{'class':'ln-end', cx:l.x1, cy:ty, r:3.6, fill:c},g);   // where the line stops: a plain end, not a ring
    l.lv=lv;
    presence[l.id]=stops.filter(function(s){ return s.a; }).map(function(s){ return {id:s.id, x:s.x, y:s.y-P}; });
    stops.forEach(function(s){ if(s.a) marks.push({l:l, x:s.x, y:s.y, c:c, id:s.id}); });
    l.tagEl.style.left=l.x0+'px'; l.tagEl.style.top=ty+'px';
  });
  /* the main line, over the characters' dips: straight through the present, an S
     down to the past track and back up for each flashback */
  var mg=el('g',{'data-ln':'main'},svg), md='M'+main.x0+' '+my;
  runs.slice().sort(function(a,b){ return a.x0-b.x0; }).forEach(function(r){
    var m0=r.d0+DRAMP/2, m1=r.d1-DRAMP/2;
    md+=' L'+r.d0+' '+my+' C'+m0+' '+my+' '+m0+' '+py+' '+r.f0+' '+py+' L'+r.f1+' '+py+' C'+m1+' '+py+' '+m1+' '+my+' '+r.d1+' '+my; });
  md+=' L'+main.x1+' '+my;
  el('path',{'class':'ln-main-halo', d:md},mg);
  el('path',{'class':'ln-main', d:md},mg);
  el('path',{d:'M'+(main.x1-4)+' '+(my-15)+' L'+(main.x1+20)+' '+my+' L'+(main.x1-4)+' '+(my+15)+' Z', fill:'color-mix(in srgb,var(--accent) 62%,var(--text))'},mg);
  if(main.label) tag(world, main, main.x0-14, my, 'var(--accent)', 1);
  /* the pace, said on the line: where the material says how soon an event follows the one
     before it, a small caption sits on the main line between them (not for ordinary steps) */
  var GL={moments:'same time', hours:'hours later', day:'next day', days:'days later', weeks:'weeks later', months:'months later', years:'years later'};
  var pg=[];                                                   // runs of events that follow one another at one pace share one caption
  G.mains.forEach(function(id,k){ var g=(L.ev[id]||{}).gap, p=G.mains[k-1];
    if(!g || !GL[g] || !p || fbOf[id] || fbOf[p]) return;
    var last=pg[pg.length-1];
    if(last && last.g===g && last.to===p) last.to=id; else pg.push({g:g, from:p, to:id}); });
  pg.forEach(function(q){
    var c=document.createElement('div'); c.className='lanes-gap'; c.textContent=GL[q.g]; c.setAttribute('data-gap', q.g);
    c.style.left=((X[q.from]+X[q.to])/2)+'px'; c.style.top=my+'px'; world.appendChild(c);
    if(c.offsetWidth+30 > X[q.to]-X[q.from]) c.remove();       // it would cover the events either side: the spacing says it alone
  });
  /* squeezed stretches: a ≈ across every line that runs straight through them */
  S.breaks.forEach(function(raw){
    var bx=raw+G.shift(raw, -1);
    if(G.mains.some(function(i){ return X[i]<bx; }) && G.mains.some(function(i){ return X[i]>bx; }) && !inDetour(bx)) brk(svg, bx, my);
    lines.slice(1).forEach(function(l){
      if(!l.drawn || !l.lv) return;
      if(l.lv.some(function(v){ return Math.abs(v.y-(l.y+P))<.5 && bx>v.x0+12 && bx<v.x1-12; })) brk(svg, bx, l.y+P);
    });
  });
  var meets={}; marks.forEach(function(m){ meets[m.id]=1; });
  /* stems + dots at each event: the main line's (on the past track inside a
     flashback), the characters' own on their tracks */
  order.forEach(function(id){
    var l=lineOfEv(id), x=X[id], ly=at[id].y+P, cyy=pos[id]+P, hh=(h[id]||120)/2, edge=cyy+(cyy<ly?hh:-hh), c=col(l);
    var g=el('g',{'data-ln':l.id},svg);
    el('line',{'class':'ln-stem', x1:x, x2:x, y1:ly, y2:edge, stroke:c},g);
    if(!meets[id]) el('circle',{'class':'ln-dot', cx:x, cy:ly, r:6.5*(G.z||1), fill:c},g);   // with characters there, their rings mark it
  });
  /* where a character meets the page: a ring in its colour, on top of everything */
  marks.forEach(function(m){
    var g=el('g',{'data-ln':m.l.id, 'class':'ln-meet'},svg);
    el('circle',{'class':'ln-ring', cx:m.x, cy:m.y, r:5.5*(G.z||1), stroke:m.c},g);
  });
  /* connections the material draws between events (not the lines themselves) */
  (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).forEach(function(cn){
    if(!cn || cn[2]==='spine' || X[cn[0]]==null || X[cn[1]]==null) return;
    var la=lineOf(lines,cn[0]), lb=lineOf(lines,cn[1]); if(!la||!lb || la===lb) return;   // the line itself already joins them
    var ax=X[cn[0]], ayy=at[cn[0]].y+P, bx=X[cn[1]], by=at[cn[1]].y+P, mx=(ax+bx)/2, bow=Math.min(160, Math.abs(bx-ax)/3+30);
    var c=(typeof COLOR_MAP!=='undefined' && COLOR_MAP[cn[2]]) ? COLOR_MAP[cn[2]] : 'var(--muted)';
    var rg=el('g',{'data-ln':la.id+' '+lb.id},svg);
    el('path',{'class':'ln-rel', d:'M'+ax+' '+ayy+' Q'+mx+' '+(Math.min(ayy,by)-bow)+' '+bx+' '+by, stroke:c},rg);
  });
  return {at:at, presence:presence};
}
function brk(svg, bx, y){ el('path',{'class':'ln-break', d:'M'+(bx-9)+' '+(y-9)+' q4.5 -5 9 0 t9 0 M'+(bx-9)+' '+(y+1)+' q4.5 -5 9 0 t9 0'},svg); }
/* the card says when (and, on a phone, which line it is on) */
function whenChip(c, id){
  var ev=L.ev[id]; if(!c || !ev || c.querySelector('.lanes-when')) return;
  var ln=null; L.lines.forEach(function(q){ if(q.id===ev.l) ln=q; });
  var txt=ev.w || '', mob=de.classList.contains('mobile');
  if(mob && ev.l!=='main' && ln) txt=(txt ? txt+' · ' : '')+ln.label;
  else if(mob && ev.flash){ var fb=(L.flashbacks||[]).filter(function(f){ return f.id===ev.flash; })[0]; txt=(txt ? txt+' · ' : '')+'↺ '+((fb&&fb.label)||'Flashback'); }
  else if(mob && L.main && !txt) txt=L.main;
  if(!txt && mob) return;
  var d=document.createElement('div'); d.className='lanes-when'; d.textContent=txt;
  var tg=c.querySelector('.node-tag'); c.insertBefore(d, tg||c.firstChild);
}
function phoneChips(){ if(!de.classList.contains('mobile')) return;
  document.querySelectorAll('.node[id^="node-"]').forEach(function(n){ whenChip(n.querySelector('.node-card'), n.id.slice(5)); });
  phoneFlags(); }
/* the phone's card view has no axis: a time flag shows on the first card at or after its time (or the card it is pinned to),
   a chip under the card's date, its whole label and date in words */
function phoneFlags(){
  document.querySelectorAll('.lanes-fchips').forEach(function(e){ e.remove(); });
  var F=(L.tf||[]).filter(function(f){ return f && f.label; })
    .concat((L.bt||[]).filter(function(t){ return t && t.label; }).map(function(t){ return {label:t.label, at:t.at, to:'', node:t.node, t:t.t, box:true}; }));
  if(!F.length) return;
  var order=[].concat.apply([], typeof ACT_SEQS!=='undefined' ? ACT_SEQS : []).filter(function(id){ return L.ev[id] && document.getElementById('node-'+id); });
  var main=order.filter(function(id){ return !L.ev[id].flash; }), home={};
  F.forEach(function(f){
    var id=f.node && L.ev[f.node] ? f.node : null;
    if(!id && f.t!=null){ for(var k=0;k<main.length;k++){ var e=L.ev[main[k]]; if(e.t!=null && e.t>=f.t-1e-9){ id=main[k]; break; } }
      if(!id) for(var j=main.length-1;j>=0;j--) if(L.ev[main[j]].t!=null){ id=main[j]; break; } }
    if(id) (home[id]=home[id]||[]).push(f); });
  Object.keys(home).forEach(function(id){
    var c=document.querySelector('#node-'+id+' .node-card'); if(!c) return;
    var box=document.createElement('div'); box.className='lanes-fchips';
    home[id].forEach(function(f){ var s=document.createElement('span'), era=f.to ? ' – '+f.to : '';
      s.className=f.box ? 'lanes-bchip' : 'lanes-fchip'; if(f.color) s.style.setProperty('--flag-c', f.color);
      s.textContent=f.label+(f.at && !f.box ? ' · '+f.at+era : ''); box.appendChild(s); });
    var w=c.querySelector('.lanes-when'); if(w && w.nextSibling) c.insertBefore(box, w.nextSibling); else c.insertBefore(box, c.firstChild);
  }); }
['DOMContentLoaded','load'].forEach(function(ev){ window.addEventListener(ev, function(){ phoneChips(); setTimeout(phoneChips, 400); }); });
function lineOf(lines,id){ for(var i=0;i<lines.length;i++) if(lines[i].ev.indexOf(id)>=0) return lines[i]; return null; }
function tag(world, l, x, y, c, before){
  var t=document.createElement('div'); t.className='lanes-tag'+(l.id==='main'?' ln-main-tag':''); t.style.left=x+'px'; t.style.top=y+'px';
  if(before) t.style.transform='translate(-100%,-50%)';
  t.style.color=c; t.textContent=l.label||''; t.setAttribute('data-ln-tag', l.id);
  t.title='Show only this line — click again for all lines';
  world.appendChild(t);
  return t;
}
/* a flashback's label, at the start of its past stretch: ↺ what it is · when */
function pastTag(world, r){
  var t=document.createElement('div'); t.className='lanes-past'; t.setAttribute('data-fb', r.id);
  t.innerHTML='<i>↺</i><b></b><span></span>';
  t.querySelector('b').textContent=r.label||'Flashback'; t.querySelector('span').textContent=r.range||'';
  t.title='A flashback: the main line drops back in time here and comes back to the present after it';
  world.appendChild(t);
  return t;
}
/* the slab across the board: each unit's colour, changing midway between two units. (sim1112a R4) On a phone on its side the canvas runs under the Dynamic Island's insets and holds
   the board clear of them with its own side padding (phone_shell.py): the slab is the board's ground, so it runs on through that padding to the screen's edges in its first and last
   unit's colour, one piece of glass with no strip beside it to match. The shell calls this again when the insets arrive or a turn changes them (nothing is laid out again) */
function slabX(slab){
  var q=slab && slab._ln; if(!q) return;
  var cvE=document.getElementById('canvas'), csE=cvE && de.classList.contains('phone-whole') ? getComputedStyle(cvE) : null, EL=csE && parseFloat(csE.paddingLeft) || 0, ER=csE && parseFloat(csE.paddingRight) || 0, T=q.W+EL+ER;
  ['width',T+'px','left',(-EL)+'px','transform','none'].forEach(function(v,i,a){ if(i%2===0) slab.style.setProperty(v,a[i+1],'important'); });
  if(q.stops.length) slab.style.backgroundImage='linear-gradient(90deg, '+q.stops[0][0]+' 0%, '+q.stops.map(function(c){ return c[0]+' '+((c[1]+EL)/T*100).toFixed(1)+'%'; }).join(', ')+', '+q.stops[q.stops.length-1][0]+' 100%)';
}
window._altoLanesSlab=function(){ slabX(document.getElementById('glass-slab')); };
/* the units: columns of time, each from its first event to its last */
function units(world, order, X, w, H, W, main){
  world.querySelectorAll('.lanes-unit').forEach(function(e){ e.remove(); });
  var R=ACT_SEQS.map(function(ids){ var xs=ids.filter(function(i){ return X[i]!=null; }); if(!xs.length) return null;
    return [Math.min.apply(null,xs.map(function(i){ return X[i]-w[i]/2; })), Math.max.apply(null,xs.map(function(i){ return X[i]+w[i]/2; }))]; });
  var cuts=[0], last=0;
  for(var a=0;a<R.length;a++){
    if(!R[a]) { cuts.push(last); continue; }
    var nx=null; for(var b=a+1;b<R.length;b++) if(R[b]){ nx=R[b]; break; }
    var cut=nx ? Math.max(last+40, (R[a][1]+nx[0])/2) : W;
    cuts.push(cut); last=cut;
  }
  var box=document.getElementById('lanes-ulabels');
  if(!box){ box=document.createElement('div'); box.id='lanes-ulabels'; world.appendChild(box); }
  box.innerHTML='';
  /* the line's dots (its events and where other lines meet it): a label never covers one */
  var dots=(main && main.ev || []).map(function(i){ return X[i]; }).filter(function(x){ return x!=null; }).sort(function(p,q){ return p-q; });
  UL={y:(main && main.y!=null ? main.y : 0)+WORLD_PAD_TOP, dots:dots, rr:9*(MODE_Z()||1)+6, x0:(main && main.x0!=null ? main.x0 : 0)+8, x1:(main && main.x1!=null ? main.x1 : W)-8, chips:[]};
  var stops=[];
  ACT_SEQS.forEach(function(ids,a){
    var pm=PHASE_META[a]; if(!pm || !R[a]) return;
    var u=document.createElement('div'); u.className='lanes-unit';
    u.style.left=cuts[a]+'px'; u.style.width=(cuts[a+1]-cuts[a])+'px'; u.style.height=(H+WORLD_PAD_TOP)+'px';
    u.style.setProperty('--unit-color', pm.colorRaw);
    world.insertBefore(u, world.firstChild);
    var ch=document.createElement('div'); ch.className='lu-chip'; ch.setAttribute('data-unit', a);
    ch.style.setProperty('--unit-color', pm.colorRaw);
    ch.innerHTML='<b class="un-n"></b><span></span>';
    ch.querySelector('b').textContent=window._altoU(a+1, 'roman'); ch.querySelector('span').textContent=(pm.label.split(' — ')[1]||pm.label);
    box.appendChild(ch);
    var g=gapAt(cuts[a]), nat=ch.offsetWidth, cw=Math.min(nat, g[1]-g[0]);
    var x=Math.max(g[0], Math.min(g[1]-cw, cuts[a]-cw/2));
    cw=Math.min(nat, Math.max(cw, 110));                    // (never squeezed below a readable width: the old ride's least)
    UL.chips.push({el:ch, a:a, nat:nat, l:cuts[a], r:cuts[a+1], x:x, w:cw});
    stops.push([pm.colorRaw+'b3', (cuts[a]+cuts[a+1])/2]);
  });
  /* measured once: the label's width is locked (its wrap and padding with it), and its strip runs from its rest to 8 px short of the next label */
  UL.chips.forEach(function(c, i){
    var e=c.el, nx=UL.chips[i+1];
    e.style.width=Math.round(c.w)+'px'; e.style.left=''; e.style.top='';
    var st=document.createElement('div'); st.className='lu-strip'; box.appendChild(st); st.appendChild(e);
    var h=e.offsetHeight, end=nx ? nx.x-8 : Math.max(c.x+c.w, UL.x1), y0=lineYAt(c.x+c.w/2)-h/2;
    st.style.left=c.x.toFixed(1)+'px'; st.style.width=Math.max(c.w, end-c.x).toFixed(1)+'px'; st.style.top=y0.toFixed(1)+'px'; st.style.height=h+'px';
    c.h=h; c.y0=y0; c.st=st; c.dy=0;
  });
  var slab=document.getElementById('glass-slab');
  if(!slab){ slab=document.createElement('div'); slab.id='glass-slab'; world.insertBefore(slab, world.firstChild); }
  slab.style.top='0px'; slab.style.height=(H+WORLD_PAD_TOP+200)+'px';
  slab._ln={W:W, stops:stops}; slabX(slab);
  window._headerTint={slabTop:0, slabH:H, stops:[{p:0,c:PHASE_META[0].colorRaw},{p:100,c:PHASE_META[0].colorRaw}]};
  if(window.updateHeaderTint) try{ window.updateHeaderTint(); }catch(e){}
  unitPin();
}
var UL=null;
function MODE_Z(){ var f=window._altoLanesFit; return f && f.mode && f.mode.cz || 1; }
/* the stretch of line between the dots around x: [from, to] */
function gapAt(x){ var d=UL.dots, lo=UL.x0, hi=UL.x1; for(var i=0;i<d.length;i++){ if(d[i]<=x) lo=Math.max(lo, d[i]+UL.rr); else { hi=Math.min(hi, d[i]-UL.rr); break; } } return [lo, Math.max(lo+40, hi)]; }
/* the main line's height (world px) at world x: the drawn line itself, which dips where the story turns back */
function lineYAt(xw){
  var p=document.querySelector('#lanes-svg path.ln-main'), w=document.getElementById('world'); if(!p || !w || !p.getTotalLength) return UL.y;
  var m=p.getScreenCTM(), wr=w.getBoundingClientRect(), k=(w.offsetWidth && wr.width/w.offsetWidth)||1; if(!m) return UL.y;
  var L=p.getTotalLength(), lo=0, hi=L, sx=wr.left+xw*k, q;
  function X(t){ q=p.getPointAtLength(t); return m.a*q.x+m.c*q.y+m.e; }
  if(sx<=X(0)) { X(0); } else if(sx>=X(L)) { X(L); } else { for(var i=0;i<28;i++){ var t=(lo+hi)/2; if(X(t)<sx) lo=t; else hi=t; } X((lo+hi)/2); }
  return ((m.b*q.x+m.d*q.y+m.f)-wr.top)/k;
}
/* the unit labels stay in view (Luke 2026-11-25: "unit labels in expanded horizontal timeline need to be visible at all
   times"): along the main line. While a unit runs on past the window's left edge its label rides the line 20 px in (clear of
   the key's toggle and the quiet cue), in the first stretch between dots it fits, until the next unit's label meets it and
   takes over. It never leaves the line. */
var UPIN=0;
function unitPinSoon(){ if(!UPIN) UPIN=requestAnimationFrame(unitPin); }
function unitPin(){
  UPIN=0;
  var world=document.getElementById('world'), c=document.getElementById('canvas'), box=document.getElementById('lanes-ulabels'); if(!world || !c || !box || !UL || !UL.chips.length || de.classList.contains('mobile')) return;
  if(!c._lnPin){ c._lnPin=1; c.addEventListener('scroll', unitPinSoon, {passive:true}); window.addEventListener('resize', unitPinSoon); }
  var wr=world.getBoundingClientRect(), k=(world.offsetWidth && wr.width/world.offsetWidth)||1, cr=c.getBoundingClientRect(), sy=wr.top+UL.y*k, L=20;
  [].slice.call(document.querySelectorAll('#key-toggle,[data-ln-edge]')).forEach(function(e){      // (the key's toggle, Extend's quiet cues)
    if(!e || e.hidden || getComputedStyle(e).display==='none') return; var q=e.getBoundingClientRect();
    if(q.width && q.height && q.left<160 && q.top<sy+24 && q.bottom>sy-24) L=Math.max(L, q.right+12); });
  var lv=((L-cr.left)/k).toFixed(1)+'px';                  // (sticky's inset, in the board's own px: the canvas's edge, then L in)
  if(box.style.getPropertyValue('--lu-l')!==lv) box.style.setProperty('--lu-l', lv);
  /* the browser slides each label (sticky); here only its height follows the line where the line dips, as a transform */
  UL.chips.forEach(function(ch){
    var e=ch.el, r=e.getBoundingClientRect(), sr=ch.st.getBoundingClientRect(), ride=r.left>sr.left+.5+Math.abs(ch.dy)*0;
    var xw=(r.left-wr.left)/k+ch.w/2, dy=ride ? lineYAt(xw)-ch.h/2-ch.y0 : 0;
    if(Math.abs(dy-ch.dy)>.4){ ch.dy=dy; e.style.transform=dy ? 'translateY('+dy.toFixed(1)+'px)' : ''; }
    if(e.classList.contains('lu-pin')!==ride) e.classList.toggle('lu-pin', ride);
  });
}
/* arrow keys: along a line ←/→ in time; ↑/↓ to the nearest event on the next line over */
window._altoLanesNav=function(id, dir){
  var G=window._altoLanesGeo; if(!G || de.classList.contains('mobile')) return null;
  var lid=(L.ev[id]||{}).l||'main', l=null; G.lines.forEach(function(q){ if(q.id===lid) l=q; }); if(!l) return null;
  function live(i){ return !!document.querySelector('#node-'+i+' .node-card') && (!window._altoShown || window._altoShown(i)); }
  if(dir==='e'||dir==='w'){
    var ev=l.ev.filter(live), i=ev.indexOf(id), j=i+(dir==='e'?1:-1);
    if(i>=0 && j>=0 && j<ev.length) return ev[j];
    /* the end of a side line: on into the event it converges into, or back to where it branched */
    if(dir==='e' && l.to) return l.to; if(dir==='w' && l.from) return l.from;
    return null;
  }
  if(dir==='n'||dir==='s'){
    var cy=G.y[id], sg=dir==='s'?1:-1, best=null, bd=Infinity;
    Object.keys(G.y).forEach(function(k){ if(k===id || !live(k)) return;
      var dyy=(G.y[k]-cy)*sg; if(dyy<=20) return;
      var c=Math.abs(G.x[k]-G.x[id])*1.6+dyy; if(c<bd){ bd=c; best=k; } });
    return best;
  }
  return null;
};
/* stepping event to event — keys, wheel, touch, the rail and the whole-timeline
   view — is lanes_nav.py (NAV_JS, appended to this script) */
/* isolating a line: its events, its curves, where it branches and joins, the
   arcs to it. Hovering shows it (calmly, below); picking lines shows only them. */
function lineBy(id){ for(var i=0;i<L.lines.length;i++) if(L.lines[i].id===id) return L.lines[i]; return null; }
/* ── showing only some lines (Luke, 2026-10-26: "Should be able to select multiple lines at once to only show").
   The picked characters' lines stay, with their own events and the main-line events where any of them is on the
   page; every other line and event leaves the board, and the board is laid out again for what is left (the main
   line stays as the page's context). Picked in the key (a row a toggle each, "Show all" to undo) or by a line's
   label on the board (only that line; again for all). Remembered per timeline on this device; the steps, the
   wheel's path and the filters' order skip what is hidden (window._altoLanesHid). ── */
var PK=window._ALTO_LANES_PICK||'', PICK=[];
try{ PICK=JSON.parse(localStorage.getItem(PK)||'[]')||[]; }catch(e){ PICK=[]; }
function pickOk(){ var seen={}; PICK=(Array.isArray(PICK)?PICK:[]).filter(function(i){ if(seen[i] || !lineBy(i)) return false; seen[i]=1; return true; }); }
pickOk();
function hidLine(id){ return PICK.length>0 && id!=='main' && PICK.indexOf(id)<0; }
function hidEv(id){
  var e=L.ev[id]; if(!PICK.length || !e) return false;
  if(nestOf(id)) return hidEv(rootOf(id));                       // a child is shown or hidden with its parent
  if(e.l && e.l!=='main' && lineBy(e.l)) return PICK.indexOf(e.l)<0;          // a character's own event
  return !PICK.some(function(c){ var l=lineBy(c);                                // a main-line event: someone picked is on the page
    return (e.present||[]).indexOf(c)>=0 || (e.ent||[]).indexOf(c)>=0 || (!!l && ((l.presence||[]).indexOf(id)>=0 || l.from===id || l.to===id)); });
}
window._altoLanesHid=hidEv;
function hideOut(){ document.querySelectorAll('#world .node[id^="node-"]').forEach(function(n){ var id=n.id.slice(5); if(L.ev[id]) n.classList.toggle('ln-hid', hidEv(id)); }); }
function setPick(ids){
  PICK=(ids||[]).slice(); pickOk();
  try{ if(PK){ if(PICK.length) localStorage.setItem(PK, JSON.stringify(PICK)); else localStorage.removeItem(PK); } }catch(e){}
  if(window._focusedNodeId && hidEv(window._focusedNodeId) && window.exitFocus) window.exitFocus();
  hvDrop(); isolate(null);
  if(window._altoLanesGeo && window._altoLanesH) window._altoLanes(window._altoLanesH); else hideOut();
  keyPick();
  try{ document.dispatchEvent(new CustomEvent('alto:lanes-pick', {detail:PICK.slice()})); }catch(e){}
}
window._altoLanesPick=function(ids){ if(arguments.length) setPick(ids); return PICK.slice(); };
/* (one line: the older single "kept line") */
window._altoLanesLock=function(id){ if(arguments.length) setPick(id && id!=='main' ? [id] : []); return PICK[0]||null; };
/* the engine's "is this shown" (its own steps, an enlarged card's hops) leaves hidden events out too */
window.addEventListener('load', function(){ var sh=window._altoShown; if(sh && sh._ln) return;
  var f=function(id){ return !hidEv(id) && (!sh || sh.apply(this, arguments)); }; f._ln=1; window._altoShown=f; });
function isolate(id){
  var cv=document.getElementById('canvas'); if(!cv) return;
  document.querySelectorAll('.ln-on').forEach(function(x){ x.classList.remove('ln-on'); });
  if(!id){ cv.classList.remove('ln-dimline'); return; }
  cv.classList.add('ln-dimline');
  /* the line, its own events, and the main-line events where it is on the page (data-lp) */
  document.querySelectorAll('[data-ln~="'+id+'"],[data-lp~="'+id+'"],[data-ln-tag="'+id+'"],.lk-row[data-k="'+id+'"]').forEach(function(x){ x.classList.add('ln-on'); });
  var l=lineBy(id);
  if(l) [l.from,l.to].forEach(function(f){ var n=f && document.getElementById('node-'+f); if(n) n.classList.add('ln-on'); });
}
function lnOf(t){
  if(!t || !t.closest) return null;
  var k=t.closest('.lk-row[data-k],.lanes-tag'); if(k) return k.getAttribute('data-k')||k.getAttribute('data-ln-tag');
  var h=t.closest('#lanes-svg g[data-ln]'); if(h && t.classList.contains('ln-hit')) return h.getAttribute('data-ln');
  var n=t.closest('#canvas .node[data-ln]'); return n ? n.getAttribute('data-ln') : null;
}
/* ── a calm hover (Luke, 2026-10-26: "its too reactive to hovering right now"; the System's calm hover, 1.9.176):
   a line lights once the pointer has rested on it (its line, label, key row or a card on it) HI_IN ms, within
   SLOP px; it goes HI_OUT ms after the pointer leaves, and not at all if it comes back. Moving straight from one
   line to another swaps them once the new one has had its rest, with nothing lit or dimmed in between, so a
   pointer crossing the board on its way somewhere changes nothing. A wheel or a press lets it go. ── */
var HI_IN=220, HI_OUT=380, SLOP=8, _hv={on:null, want:undefined, t:0, x:0, y:0};
function hvDrop(){ clearTimeout(_hv.t); _hv.t=0; _hv.want=undefined; if(_hv.on){ _hv.on=null; isolate(null); } }
function hvArm(id){
  clearTimeout(_hv.t);
  _hv.t=setTimeout(function(){ _hv.t=0; if(_hv.want!==id) return; if(id){ _hv.on=id; isolate(id); } else if(_hv.on){ _hv.on=null; isolate(null); } }, id ? HI_IN : HI_OUT);
}
function hvQuiet(){ var cv=document.getElementById('canvas');
  return de.classList.contains('mobile') || !window._altoLanesGeo || (cv && (cv.classList.contains('focus-mode') || cv.classList.contains('ln-ov'))); }
document.addEventListener('pointerover', function(e){
  if(e.pointerType==='touch' || hvQuiet()) return;
  if(window._altoPointerStill && window._altoPointerStill(e)) return;    // a card slid under a still pointer
  var id=lnOf(e.target)||null;
  if(id===_hv.want) return;                                              // still on the same line
  _hv.want=id; _hv.x=e.clientX; _hv.y=e.clientY;
  if(id && id===_hv.on){ clearTimeout(_hv.t); _hv.t=0; return; }          // back on it within its grace: it stays
  if(!id && !_hv.on){ clearTimeout(_hv.t); _hv.t=0; return; }
  hvArm(id);
});
document.addEventListener('pointermove', function(e){
  if(!_hv.t || !_hv.want || e.pointerType==='touch') return;
  if(Math.abs(e.clientX-_hv.x)+Math.abs(e.clientY-_hv.y)>SLOP){ _hv.x=e.clientX; _hv.y=e.clientY; hvArm(_hv.want); }   // not resting yet
}, {passive:true});
['wheel','pointerdown'].forEach(function(t){ window.addEventListener(t, function(e){ if(t==='pointerdown' && e.target && e.target.closest && e.target.closest('#lanes-key')) return; hvDrop(); }, {capture:true, passive:true}); });
document.addEventListener('click', function(e){
  var t=e.target.closest && e.target.closest('.lanes-tag,.lk-row[data-k],.lk-all'); if(!t || de.classList.contains('alto-editing')) return;
  e.stopPropagation();
  if(t.classList.contains('lk-all')){ setPick([]); return; }
  var id=t.getAttribute('data-ln-tag')||t.getAttribute('data-k');
  if(id==='main' || !lineBy(id)){ setPick([]); return; }
  var nx=PICK.slice(), i=nx.indexOf(id);
  if(t.classList.contains('lanes-tag')) nx=(PICK.length===1 && i===0) ? [] : (i>=0 && PICK.length>1 ? PICK.filter(function(x){ return x!==id; }) : [id]);
  else if(i>=0) nx.splice(i,1); else nx.push(id);
  setPick(nx);
}, true);
/* Esc shows every line again — not while it is closing the key, an enlarged card or the whole timeline */
var _escBusy=false;
document.addEventListener('keydown', function(e){ if(e.key==='Escape'){ var k=document.getElementById('lanes-key'), c=document.getElementById('canvas');
  _escBusy=!!window._focusedNodeId || !!(k && k.classList.contains('open')) || !!(c && c.classList.contains('ln-ov')); } }, true);
/* (Esc does nothing on the board any more: Luke, L-1114-focus, the arrow keys only) */
/* the nav bar's character chips: a plain click is still the character's page; ⇧- or ⌘-click picks (or lets go of)
   their line, and each chip shows whether its line is picked */
var ENT=window._ALTO_LANES_ENT||{};
function chipLine(b){ var m=/showDetail\('char','([^']+)'\)/.exec(b.getAttribute('onclick')||''), l=m && ENT[m[1]]; return l && lineBy(l) ? l : null; }
function chips(){ return [].filter.call(document.querySelectorAll('#nav .nav-btn'), chipLine); }
document.addEventListener('click', function(e){
  if(!(e.shiftKey || e.metaKey || e.ctrlKey) || de.classList.contains('mobile') || de.classList.contains('alto-editing') || !window._altoLanesGeo) return;
  var b=e.target.closest && e.target.closest('#nav .nav-btn'), id=b && chipLine(b); if(!id) return;
  e.preventDefault(); e.stopPropagation();
  var nx=PICK.slice(), i=nx.indexOf(id); if(i>=0) nx.splice(i,1); else nx.push(id); setPick(nx);
}, true);
/* the key's rows say what is shown: a tick on each picked line, the others faded; "Show all" when some are hidden */
function keyPick(){
  if(!de.classList.contains('mobile')) chips().forEach(function(b){ var id=chipLine(b), on=PICK.indexOf(id)>=0;
    b.classList.toggle('ln-chip-on', on); b.classList.toggle('ln-chip-off', PICK.length>0 && !on);
    if(!b._lnT){ b._lnT=1; b.title=(b.title ? b.title+' · ' : '')+'⇧-click: show only the lines you pick'; } });
  var k=document.getElementById('lanes-key'); if(!k) return;
  k.classList.toggle('lk-picking', PICK.length>0);
  k.querySelectorAll('.lk-row[data-k]').forEach(function(r){ var id=r.getAttribute('data-k'); if(id==='main') return;
    var on=PICK.indexOf(id)>=0; r.classList.toggle('lk-pick', on); r.classList.toggle('lk-off', PICK.length>0 && !on); r.setAttribute('aria-pressed', on?'true':'false'); });
  var bar=k.querySelector('.lk-pickbar span');
  if(bar) bar.textContent=PICK.length ? 'Showing '+PICK.length+' of '+L.lines.length+' lines' : 'All lines shown — pick some to show only them';
}
/* the key: what each line follows, where it is on the page, what each shape means */
function key(){
  if(de.classList.contains('mobile')) return;
  var k=document.getElementById('lanes-key'); if(k) k.remove();
  k=document.createElement('div'); k.id='lanes-key';
  var T=function(id){ var n=(typeof NODES_SRC!=='undefined'?NODES_SRC:[]).filter(function(q){ return q.id===id; })[0]; return n?n.title:''; };
  var esc=function(v){ return String(v||'').replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
  var sw=function(c,dash,w){ return '<svg width="26" height="10"><line x1="1" y1="5" x2="25" y2="5" stroke="'+c+'" stroke-width="'+(w||4)+'" stroke-linecap="round"'+(dash?' stroke-dasharray="'+dash+'"':'')+'/></svg>'; };
  /* the picture's own language, drawn small: a dip onto the page, a detour into the past */
  var dip=function(c){ return '<svg width="26" height="16"><line x1="1" y1="12" x2="25" y2="12" stroke="var(--accent)" stroke-width="3" stroke-linecap="round"/>'+
    '<path d="M1 3 C7 3 8 12 13 12 C18 12 19 3 25 3" fill="none" stroke="'+c+'" stroke-width="3" stroke-linecap="round"/>'+
    '<circle cx="13" cy="12" r="3.4" fill="var(--surface)" stroke="'+c+'" stroke-width="2"/></svg>'; };
  var det='<svg width="26" height="18"><rect x="7" y="7" width="12" height="10" rx="3" fill="var(--accent)" fill-opacity=".16"/>'+
    '<path d="M0 4 L3 4 C8 4 6 14 11 14 L15 14 C20 14 18 4 23 4 L26 4" fill="none" stroke="var(--accent)" stroke-width="3" stroke-linecap="round"/></svg>';
  var h='<h5><span>Lines</span><span></span></h5><div class="lk-body">';
  if(L.lines.length) h+='<div class="lk-pickbar"><span></span><button type="button" class="lk-all">Show all</button></div>';
  h+='<div class="lk-row" data-k="main">'+sw('var(--accent)','',5)+'<div><b>'+esc(L.main||'Main line')+'</b><small>The main line: what is on the page, in the order the story tells it</small></div></div>';
  L.lines.forEach(function(l){
    var n=(l.presence||[]).length, o=(l.events||[]).length, w=[];
    if(n) w.push('on the page at '+n+' event'+(n>1?'s':'')+((l.presence||[])[0]?', first at “'+esc(T(l.presence[0]))+'”':''));
    if(o) w.push(o+' event'+(o>1?'s':'')+' of its own');
    h+='<div class="lk-row" data-k="'+esc(l.id)+'" role="button" tabindex="0" aria-pressed="false" style="--lk-c:'+esc(l.color)+'"><i class="lk-ck" aria-hidden="true"></i>'+sw(l.color,'',5)+'<div><b>'+esc(l.label)+'</b><small>'+(w.join(' · ')||'not on the page yet')+'</small></div></div>';
  });
  h+='<div class="lk-sep"></div>';
  if(L.lines.length) h+='<div class="lk-row">'+sw('var(--muted)','',4)+'<div>A coloured line: a character while they are off the page</div></div>'+
    '<div class="lk-row">'+dip((L.lines[0]||{}).color||'var(--muted)')+'<div>A dip onto the main line, ringed: they are on the page at that event</div></div>';
  if((L.flashbacks||[]).some(function(f){ return (f.nodes||[]).length; }))
    h+='<div class="lk-row">'+det+'<div>A detour down: a flashback <small>the main line drops into the past (its dates beside it) and comes back up where the present resumes</small></div></div>';
  var rels={}; (typeof CONNECTIONS!=='undefined'?CONNECTIONS:[]).forEach(function(c){ if(c && c[2]!=='spine') rels[c[2]]=1; });
  Object.keys(rels).forEach(function(r){ var c=(typeof COLOR_MAP!=='undefined'&&COLOR_MAP[r])||'var(--muted)', lb=(typeof REL_LABELS!=='undefined'&&REL_LABELS[r])||r;
    h+='<div class="lk-row">'+sw(c,'7 5',2)+'<div>Dashed arc: '+esc(lb)+' <small>a link the material draws between events on different lines; it brightens when you point at either line</small></div></div>'; });
  h+='<div class="lk-row"><span style="width:26px;text-align:center;flex:none">≈</span><div>Time squeezed — a long stretch with nothing in it</div></div>';
  h+='<small style="margin-top:4px">Point at a line, its label or a card to follow it. Tick lines here to show only them; click a label on the board to show only that line.</small></div>';
  k.innerHTML=h; window._altoKeyToggle(k, 'alto-lanes-key', 'Key to the lines');
  k.addEventListener('keydown', function(e){ var r=e.target.closest && e.target.closest('.lk-row[data-k]'); if(r && (e.key==='Enter' || e.key===' ')){ e.preventDefault(); r.click(); } });
  keyPick();
}
window.addEventListener('load', function(){ setTimeout(key, 300); setTimeout(keyPick, 320); });
/* ── child nodes: the chip, the keys, search, filters and print ────────────── */
document.addEventListener('click', function(e){
  var ob=e.target.closest && e.target.closest('.ln-otag');
  if(ob && !de.classList.contains('alto-editing')){ e.stopPropagation(); e.preventDefault(); var rr=ob.getAttribute('data-root'); setOutline(rr, !outWant(rr)); return; }
  var b=e.target.closest && e.target.closest('.ln-chip'); if(!b || de.classList.contains('alto-editing')) return;
  e.stopPropagation(); e.preventDefault(); var r=b.getAttribute('data-root'); openFam(r, !OPEN[r]);
}, true);
['pointerdown','mousedown'].forEach(function(t){ document.addEventListener(t, function(e){ if(e.target.closest && e.target.closest('.ln-chip,.ln-otag')) e.stopPropagation(); }, true); });
/* Into a branch and out of it (Luke 2026-11-27: "fix navigation when a nested branch is open such that if you go down/up, it gets you into the
   nested branch, and then with in outline mode on nested branch, the arrow key navigation only works within that branch instead of on the timeline
   until returned to timeline"). A branch hangs on one side of the line: the key toward it (↓ below the line, ↑ above) steps from the parent into it,
   one card deeper each press; the key back toward the line steps out, and past the branch's first level back onto the parent on the line.
   A branch set out as a column: ← → carry on along the line from the parent. A branch set out as an outline holds the arrows (and the step bar's
   ‹ ›) until the reader is back on the line (the key toward the line from its first level, Esc, or the "↑/↓ The lawsuit" button): ← → go to the
   card beside at the same level, ‹ › through the branch in outline order. The same with a card enlarged: the enlarged card moves. Enter opens it. */
function sdOf(root){ var n=document.getElementById('node-'+root); return n && n.classList.contains('ln-sd-1') ? -1 : 1; }
function famIds(root){ return (((window._altoLanesGeo||{}).fams||{})[root]||[]).slice(); }
function outRoot(id){ var r=rootOf(id); return (id && r!==id && document.querySelector('#node-'+r+' .ln-otag[aria-pressed=true]')) ? r : ''; }
function kidsOfIn(root, id){ return famIds(root).filter(function(k){ return nestOf(k)===id; }); }
function cx(id){ var n=document.getElementById('node-'+id); return n ? parseFloat(n.style.left)||0 : 0; }
function depth(id){ var d=0, q=id; while(nestOf(q) && d<40){ q=nestOf(q); d++; } return d; }
/* the card beside, at the same level of the same branch (nearest to that side) */
function beside(root, id, dir){ var dd=depth(id), x=cx(id), best='', bd=1e9;
  famIds(root).forEach(function(k){ if(k===id || depth(k)!==dd) return; var dx=(cx(k)-x)*dir; if(dx>0.5 && dx<bd){ bd=dx; best=k; } }); return best; }
var CAP=null;      /* kidNav: where an enlarged card would go, asked instead of done */
function goKid(id, enlarged){ if(!id) return; if(CAP){ CAP.t=id; return; } if(enlarged && window.enterFocus){ window.enterFocus(id); setKC(id); return; } setKC(id); }
function backToLine(root, enlarged){
  clearKC(); if(CAP){ CAP.t=root; return; } if(enlarged){ if(window.enterFocus) window.enterFocus(root); return; }
  var c=document.getElementById('canvas'); if(c) try{ c.scrollTo({left:c.scrollLeft, top:c.scrollTop, behavior:'instant'}); }catch(er){}   /* (a branch card's own smooth scroll into view stops: the glide owns the camera) */
  if(window._altoLanesStep) window._altoLanesStep(root); }
/* one arrow inside or toward a branch: what it does, or false (the line's own) */
function kidKey(k, cur, enlarged){
  var fams=(window._altoLanesGeo||{}).fams||{}, inK=cur && isKid(cur) && !kidShut(cur);
  if(!inK){                                                  // on the line: the key toward this event's branch steps into it
    var mine=fams[cur]||[]; if(!mine.length || (k!=='ArrowDown' && k!=='ArrowUp')) return false;
    var toward=sdOf(cur)<0 ? 'ArrowUp' : 'ArrowDown'; if(k!==toward) return false;
    if(!openNow(cur)) openFam(cur, true);
    goKid(kidsOfIn(cur, cur)[0] || famIds(cur)[0], enlarged); return true;
  }
  var root=rootOf(cur), sd=sdOf(root), deeper=sd<0 ? 'ArrowUp' : 'ArrowDown', ol=!!outRoot(cur);
  if(k==='ArrowLeft' || k==='ArrowRight'){
    if(!ol){ clearKC(); return false; }                      // a column: carry on along the line
    var b=beside(root, cur, k==='ArrowRight' ? 1 : -1); if(b) goKid(b, enlarged); return true;   // an outline holds the arrows (at its edge: stays)
  }
  if(k===deeper){
    if(ol){ var ch=kidsOfIn(root, cur); if(ch.length) goKid(ch[0], enlarged); return true; }
    var f=famIds(root), i=f.indexOf(cur); if(f[i+1]) goKid(f[i+1], enlarged); return true;
  }
  /* back toward the line */
  if(ol){ var pa=nestOf(cur); if(pa && pa!==root) goKid(pa, enlarged); else backToLine(root, enlarged); return true; }
  var f2=famIds(root), j=f2.indexOf(cur); if(j>0) goKid(f2[j-1], enlarged); else backToLine(root, enlarged); return true;
}
document.addEventListener('keydown', function(e){
  if(!KG || !kidsOn() || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || de.classList.contains('alto-editing') || de.classList.contains('printing')) return;
  if(de.classList.contains('detail-open')) return;
  var ae=document.activeElement, tg=ae && ae.tagName; if(tg==='INPUT' || tg==='TEXTAREA' || tg==='SELECT' || (ae && ae.isContentEditable)) return;
  var k=e.key, stop=function(){ e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); };
  var fid=window._focusedNodeId;
  if(k==='Escape' && KC && !fid){ stop(); backToLine(rootOf(KC), false); return; }
  if(k!=='ArrowDown' && k!=='ArrowUp' && k!=='ArrowLeft' && k!=='ArrowRight') return;
  if(fid) return;                                           // an enlarged card: the engine's own arrows ask kidNav (below) where to go
  var cur=KC || (window._altoLanesCurrent && window._altoLanesCurrent()); if(!cur) return;
  if(kidKey(k, cur, false)) stop();
}, true);
/* the labels on the line (a unit's, a line's name, a box) the enlarged card stands over are hidden while it is enlarged */
(function(){
  var t=0;
  function under(){
    var c=document.getElementById('canvas'), f=c && c.classList.contains('focus-mode') && document.querySelector('#world .node.focused .node-card'), r=f && f.getBoundingClientRect();
    document.querySelectorAll('#world :is(.lu-chip,.lanes-tag,.lanes-box)').forEach(function(e){
      var q=r && e.getBoundingClientRect(), hit=!!(q && q.width && q.left<r.right+4 && r.left<q.right+4 && q.top<r.bottom+4 && r.top<q.bottom+4);
      if(e.classList.contains('ln-ufoc')!==hit) e.classList.toggle('ln-ufoc', hit); });
  }
  function soon(){ clearTimeout(t); under(); t=setTimeout(under, 520); }
  function hook(){ var c=document.getElementById('canvas'); if(!c || c._lnUf || !window.MutationObserver) return; c._lnUf=1;
    new MutationObserver(soon).observe(c, {attributes:true, attributeFilter:['class']});
    document.addEventListener('alto-focus', soon); c.addEventListener('scroll', function(){ if(c.classList.contains('focus-mode')) soon(); }, {passive:true}); }
  window.addEventListener('load', function(){ hook(); });
  window._altoLanesUnderFocus=soon;
})();
/* the step bar's ‹ › (lanes_nav.py step()): inside an outline, through the branch in outline order; false = the line's own step */
function kidStep(dir){
  var cur=window._focusedNodeId || KC; if(!cur || !outRoot(cur)) return false;
  var f=famIds(rootOf(cur)), i=f.indexOf(cur), n=f[i+(dir>0 ? 1 : -1)];
  if(n) goKid(n, !!window._focusedNodeId); return true;
}
/* an enlarged card's arrows (the engine's focusNeighbor, through lanes_nav.py's _altoLanesNav): the card the branch rules send it to, null to
   stay, undefined for the line's own hop */
function kidNav(id, dir){
  var k={e:'ArrowRight', w:'ArrowLeft', n:'ArrowUp', s:'ArrowDown'}[dir]; if(!k || !KG || !kidsOn()) return undefined;
  CAP={t:null}; var h=false; try{ h=kidKey(k, id, true); }finally{ var t=CAP.t; CAP=null; }
  if(!h) return undefined; if(t && isKid(t)) setKC(t); return t || id;      // (to stay: the same card; the engine takes a null as "its own hop")
}
/* back to the line from wherever in a branch (the "↑/↓ The lawsuit" button: lanes_ext_js): an enlarged card is let go first */
function kidHome(){
  var cur=window._focusedNodeId || KC, root=cur && isKid(cur) ? rootOf(cur) : (window._focusedNodeId || '');
  if(window._focusedNodeId && window.exitFocus) try{ window.exitFocus(); }catch(er){}
  clearKC(); return root;
}
/* search (and anything else that enlarges a card by its id) finds a child tucked behind its parent: the family opens first */
window.addEventListener('load', function(){
  var ef=window.enterFocus; if(typeof ef==='function' && !ef._ln){
    window.enterFocus=function(id){ if(KG && id && kidShut(id)) openFam(rootOf(id), true); var r=ef.apply(this, arguments); if(window._altoLanesUnderFocus) window._altoLanesUnderFocus(); return r; };
    window.enterFocus._ln=1; }
  /* the engine's own "is this shown" (its hops, an enlarged card's ← →) leaves a tucked child out */
  var sh=window._altoShown; if(!sh || !sh._lk){ var f2=function(id){ return !kidShut(id) && (!sh || sh.apply(this, arguments)); }; f2._lk=1; f2._ln=sh ? sh._ln : 1; window._altoShown=f2; }
  /* print: the Expanded view, whatever the screen shows */
  var st=window._stagePrint, un=window._unstagePrint;
  if(typeof st==='function' && !st._ln){ window._stagePrint=function(){ printX(true); return st.apply(this, arguments); }; window._stagePrint._ln=1; }
  if(typeof un==='function' && !un._ln){ window._unstagePrint=function(){ var r=un.apply(this, arguments); printX(false); return r; }; window._unstagePrint._ln=1; }
});
function printX(on){
  if(!kidsOn() || PRINTX===on) return; PRINTX=on;
  if(KG && Object.keys((window._altoLanesGeo||{}).fams||{}).length) relayoutNow();
}
window.addEventListener('beforeprint', function(){ printX(true); });
window.addEventListener('afterprint', function(){ printX(false); });
/* filters: a child's card dims whenever its parent's does; entering or leaving Edit mode shows every child (or tucks them again) */
(function(){
  var raf=0, wq=function(){ if(raf) return; raf=requestAnimationFrame(function(){ raf=0; kidsDim(); }); };
  var start=function(){ var w=document.getElementById('world'); if(!w || w._lnKo || !window.MutationObserver) return; w._lnKo=1;
    new MutationObserver(wq).observe(w, {attributes:true, attributeFilter:['class'], subtree:true}); };
  window.addEventListener('load', function(){ start(); setTimeout(start, 400); });
  var was=de.classList.contains('alto-editing');
  if(window.MutationObserver) new MutationObserver(function(){ var now=de.classList.contains('alto-editing'); if(now!==was){ was=now; if(KG && (window._altoLanesGeo||{}).fams && Object.keys(window._altoLanesGeo.fams).length) relayoutNow(); } }).observe(de, {attributes:true, attributeFilter:['class']});
  document.addEventListener('alto:lanes-pick', wq);
})();
})();
"""

# going round the timeline: step event to event (lanes_nav.py)
LANES_CSS += NAV_CSS
from .minimap_home import MM_HOME_JS  # noqa: E402
LANES_JS += MM_HOME_JS + NAV_JS

# the page's name on a Retro horizontal timeline: options round (lanes_title.py)
LANES_CSS += LT_CSS
LANES_JS += LT_JS


# ── Extend on a horizontal timeline (Luke 2026-11-25: "i'll accept your recs", the mock X5bdNtnEKbRMgjoBmCUtSU) ──
# Only on a page whose owner turned Extend on (brief.extend): such a page carries this variant of LANES_JS, and
# every other page keeps LANES_JS byte for byte. On (the reader's default): the board skips the fit to the window
# (no eased gaps, no title-only cards, no smaller cards, no fitStage scale), keeps one row of cards a side and
# grows up and down instead; the view travels up and down as on a board that never fitted (lanes_nav: a trackpad,
# a drag, the cues). Children stay stacked beyond their parent and the Compact | Expanded switch stays its own.
# Off (the reader's switch beside Search, or a phone held upright): today's board, the fit and all.
_EXT_SWAPS = (
    ("var A=room ? room.b-room.top-FLR : Infinity, mode=null;",
     "var A0=room ? room.b-room.top-FLR : Infinity, A=window._altoLanesExtOn() ? 1e7 : A0, mode=null;"),
    ("R=Math.min(3, 1+Math.floor((A-n1)/per));",
     "R=window._altoLanesExtOn() ? 1 : Math.min(3, 1+Math.floor((A-n1)/per));"),
    ("Math.max(0, A-(y1-y0))/2", "Math.max(0, A0-(y1-y0))/2"),
    ("if(room && y1-y0<=A) H=", "if(room && y1-y0<=A0) H="),
    ("var foot=Math.ceil((room && y1-y0<=A) ?", "var foot=Math.ceil((room && y1-y0<=A0) ?"),     # the frosted slab runs to the board's foot
    # a board taller than the window ends with room under its lowest card (and over its highest) for the card to scroll fully clear of
    # the bottom bar and the minimap (and the top bar), 20 px more (Luke 2026-11-26, "i can't see the node hiding behind the toggle,
    # we need to be able to scroll down enough to see it fully")
    ("  fitStage(KSHOW);                 // (once more, now that the world and the slab have their final heights)",
     "  if(window._altoLanesRoomFix) window._altoLanesRoomFix();\n  fitStage(KSHOW);                 // (once more, now that the world and the slab have their final heights)"),
    ("  KSHOW=Object.keys(geoK).length>0; fitStage(KSHOW);",
     "  if(window._altoLanesRoomFix) window._altoLanesRoomFix();\n  KSHOW=Object.keys(geoK).length>0; fitStage(KSHOW);"),
    ("var W=Math.max.apply(null,xe)+RIGHT, H=y1-AX+dy+((nums||hasFl||hasBA)?AX+BOTTOM-56:24);",
     "if(window._altoLanesExtOn() && room && y1-y0>A0) dy+=window._altoLanesHeadRoom(room);\n"
     "  var W=Math.max.apply(null,xe)+RIGHT, H=y1-AX+dy+((nums||hasFl||hasBA)?AX+BOTTOM-56:24);\n"
     "  if(window._altoLanesExtOn() && room && y1-y0>A0) H=Math.max(H, y1-AX+dy+window._altoLanesFootRoom(room));"),
    ("if(!on || de.classList.contains('printing') || PRINTX) return;",
     "if(window._altoLanesCueLook){ window._altoLanesCueLook(1); setTimeout(function(){ window._altoLanesCueLook(1); if(!window._lnRested && window._altoLanesRestV){ window._lnRested=1; window._altoLanesRestV(); } }, 450); }\n"
     "  if(!on || window._altoLanesExtOn() || de.classList.contains('printing') || PRINTX) return;"),
    # the camera: the main line rests where it does, but with Extend on a card that would stand beyond the bars (a board
    # taller than the window: a phone held sideways) brings the view up or down just enough to show it whole
    ("  var tt=mainAt(id)+P+off.y-lineHome(c,B);      // the main line stays where it rests, whatever this event's card or line does\n",
     "  var tt=mainAt(id)+P+off.y-lineHome(c,B);      // the main line stays where it rests, whatever this event's card or line does\n"
     "  if(window._altoLanesExtOn() && G.y && G.y[id]!=null){ var eh=(G.h&&G.h[id])||120, et=G.y[id]-eh/2+P+off.y, X=window._altoLanesExtRoom(), cr=c.getBoundingClientRect(), zz=zk(c),\n"
     "      xt=Math.max(B.t,(X.t+8-cr.top)/zz), xb=Math.min(B.b,(X.b-8-cr.top)/zz);      // (clear of the bars)\n"
     "    if(et-tt<xt) tt=et-xt; else if(et+eh-tt>xb) tt=Math.min(et-xt, et+eh-xb); }\n"),
    # the cues' way up and down: a height the hand chose, as a trackpad's up and down sets it
    ("window._altoLanesCurrent=function(){ return current(); };",
     "window._altoLanesCurrent=function(){ return current(); };\n"
     "window._altoLanesVy=function(d){ var c=cv(); if(!c) return; var mt=c.scrollHeight-c.clientHeight; if(mt<1) return;\n"
     "  M.vy=Math.max(0,Math.min(mt,(M.vy!=null ? M.vy : c.scrollTop)+d)); if(!M.pth) resync(); M.input=performance.now(); wake(); };\n"
     # a board that opens (or turns Expanded) taller than the window rests on its main line, not on its top edge: when the
     # line at this event stands outside the room between the bars, the view comes to the event's resting height at once
     "window._altoLanesRestV=function(){ var c=cv(); if(!c || !geo() || !window._altoLanesExtOn() || M.raf) return; var id=current()||stops().ids[0]; if(!id) return;\n"
     "  var zz=zk(c), cr=c.getBoundingClientRect(), X=window._altoLanesExtRoom(), y=(mainAt(id)+PAD()+worldOff(c).y-c.scrollTop)*zz+cr.top;\n"
     "  if(y>X.t+40 && y<X.b-40) return;\n"
     "  M.vy=null; c.scrollTop=camFor(id).t; M.pth=null; };"),
)

LANES_EXT_HEAD = r"""
window._altoLanesExtOn=function(){
  var c=document.documentElement.classList;
  if(!window._ALTO_EXTEND_PAGE || c.contains('printing')) return false;
  if(c.contains('phone-whole')) return !c.contains('alto-ext-off') && window.innerWidth>window.innerHeight;     /* phones: held sideways only (upright, the board has its height); MENU's Extend row */
  if(c.contains('mobile') || (c.contains('alto-editing') && c.contains('alto-ext-off'))) return false;          /* (the owner's own switch, while editing) */
  /* the desktop has one switch (Luke 2026-11-26, "If a user exapands a nested branch or hits the expand all toggle ... then extend mode
     automatically activates"): Extend is on while the board is Expanded or a branch is open, and the board fits the window otherwise */
  var k=window._altoLanesKids; return !!(k && k.grown && k.grown());
};
/* the room between the bars, in screen px: the top bar's foot and the rail's (or the phone's bottom row's) head */
window._altoLanesExtRoom=function(){
  var ph=document.documentElement.classList.contains('phone-whole'), t=ph ? 44 : 104, b=window.innerHeight-(ph ? 68 : 62), q;
  var nav=document.getElementById('lanes-nav'); if(nav && (q=nav.getBoundingClientRect()).height && q.top<window.innerHeight) b=Math.min(b, q.top-8);
  return {t:t, b:b};
};
/* the room a board taller than the window keeps past its lowest card, in the canvas's px: from the line 20 px over the highest of the
   bottom bar (the rail, or the phone's bottom row) and the minimap (drawn or about to be, just over the bottom-right buttons) to the
   canvas's foot; and over its highest card, what the top bar's 20 px take beyond the room the layout already leaves (room.top) */
window._altoLanesFootRoom=function(room){
  var c=document.getElementById('canvas'); if(!c || !room) return 0;
  var r=c.getBoundingClientRect(), k=(r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1, clr=window._altoLanesExtRoom().b+8, q;
  var mm=document.getElementById('ln-mm'), mon=!window._altoLanesMmOn || window._altoLanesMmOn();
  if(mon && mm && mm.classList.contains('on') && (q=mm.getBoundingClientRect()).height) clr=Math.min(clr, q.top);
  else if(mon && window._altoMmRow && !document.documentElement.classList.contains('phone-whole')){ var w=window._altoMmRow(); if(w) clr=Math.min(clr, w[1]-(window._altoMmGap||12)-106); }
  return Math.max(0, room.ch-((clr-20)-r.top)/k);
};
/* and measured on the cards as they stand (a branch's cards can be taller than the rows the layout allowed them): the board's foot
   (the slab, and the world with it) moves down until the lowest card has that room under it */
window._altoLanesRoomFix=function(){
  var de=document.documentElement, w=document.getElementById('world'), sl=document.getElementById('glass-slab'), f=window._altoLanesFit;
  if(!w || !sl || !f || !f.room || !window._altoLanesExtOn() || de.classList.contains('printing')) return;
  var lo=-1e9; w.querySelectorAll('.node').forEach(function(n){ var c=n.querySelector('.node-card'), y=parseFloat(n.style.top);
    if(!c || isNaN(y) || n.classList.contains('ln-kid-shut') || getComputedStyle(n).display==='none') return; lo=Math.max(lo, y+c.offsetHeight/2); });
  if(lo<0) return;
  var end=sl.offsetTop+sl.offsetHeight, need=Math.ceil(lo+window._altoLanesFootRoom(f.room)); if(need<=end+1) return;
  de.style.setProperty('--lanes-slab-h', Math.round((parseFloat(getComputedStyle(sl).height)||0)+need-end)+'px');
  var wcs=getComputedStyle(w), pads=(parseFloat(wcs.paddingTop)||0)+(parseFloat(wcs.paddingBottom)||0);
  w.style.minHeight=Math.max(0, sl.offsetTop+sl.offsetHeight-pads)+'px';
};
window._altoLanesHeadRoom=function(room){
  var c=document.getElementById('canvas'); if(!c || !room) return 0;
  var r=c.getBoundingClientRect(), k=(r.width && c.offsetWidth) ? r.width/c.offsetWidth : 1;
  return Math.max(0, ((window._altoLanesExtRoom().t+20)-r.top)/k-room.top);
};
"""

# the quiet cue: a small round arrow 20 px in from the left, on the side that has more, 44 px to touch on a phone;
# the board runs to the top and bottom of the window, behind the bars and buttons as anywhere else (Luke 2026-11-25: no fade).
LANES_EXT_TAIL = r"""
(function(){
  var R=document.documentElement, cues={}, raf=0;
  function cv(){ return document.getElementById('canvas'); }
  function make(){
    var nav=document.getElementById('lanes-nav');
    if(cues.pill || !document.body || !nav || !document.querySelector('#world .lanes-tag.ln-main-tag')) return;
    var st=document.createElement('style');
    /* the way back to the main line, in the step bar (Luke 2026-11-26, "if you are scrolled way up or down in a nested branch, you can
       return to the timeline centered easily"; a pill floating on the board read as one more label, "clearly this is not the right
       approach"): a button at the bar's left end, its arrow pointing to where the line is and the line's own name, there only while the
       line is out of view; a click glides the view up or down until the line is centred (no sideways move) and the button fades */
    st.textContent='#lanes-nav .lnv-main{width:auto;max-width:0;padding:0;margin:0;opacity:0;overflow:visible;white-space:nowrap;gap:5px;border-radius:14px;'
      +'font-size:12px;font-weight:700;letter-spacing:.03em;color:var(--accent);position:relative;pointer-events:none;'
      +'transition:max-width .25s ease,padding .25s ease,opacity .2s ease,margin .25s ease}'
      +'#lanes-nav .lnv-main>span{overflow:hidden;text-overflow:ellipsis;max-width:150px}'
      +'#lanes-nav .lnv-main.on{max-width:200px;padding:0 10px 0 8px;margin-right:2px;opacity:1;pointer-events:auto;'
      +'background:var(--accent);color:#fff;box-shadow:0 2px 8px color-mix(in srgb,var(--accent) 35%,transparent)}'
      +'#lanes-nav .lnv-main.on:hover{color:#fff;background:color-mix(in srgb,var(--accent) 85%,#000)}'
      +'#lanes-nav .lnv-main::after{content:"";position:absolute;left:-4px;right:-4px;top:50%;height:44px;transform:translateY(-50%)}'
      +'#lanes-nav .lnv-main svg{flex:0 0 auto}'
      +'html.alto-retro #lanes-nav .lnv-main.on{border-radius:0;color:#d9ae55;background:#000;box-shadow:inset 0 0 0 1.5px #d9ae55}'
      +'html.alto-holo #lanes-nav .lnv-main.on{border-radius:0;color:#4ff0e0;background:rgba(79,240,224,.1);box-shadow:inset 0 0 0 1.5px #4ff0e0}'
      +'html.phone-whole #lanes-nav>button.lnv-main:not(#_):not(#_){flex:0 0 auto !important}'
      /* Holo's step bar is clear glass: over a board that runs under it, a card's words read through it (no text on text): opaque, as its minimap is; on phones too (Board 2026-11-27: "1.1 MOTION ANSWER" read under "1/275" in landscape) */
      +'html.alto-holo #lanes-nav:not(#_):not(#__):not(#___):not(#____):not(#_____):not(#______){background:#05070b !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important}'      /* (holo.py G273 glass: !important at five ids) */
      +'html.phone-whole:not(.alto-holo):not(.alto-retro) :is(#lanes-nav,#pmin-find,#hamburger-tab):not(#_):not(#__){background:var(--surface,#fff) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important}'
      +'html.phone-whole.alto-retro #lanes-nav:not(#_){background:#000;-webkit-backdrop-filter:none;backdrop-filter:none}'
      +'@media (prefers-reduced-motion:reduce){#lanes-nav .lnv-main{transition:none}}'
      /* the brand marks in the top corners and the name: a backing while the board runs under them (Classic and Holo frosted, Retro black). On phones only the marks
         and the name: Holo's trace overlay is an svg of #nav too, and backed it covered the word with an empty box (Board 2026-11-27) */
      +'html.ln-under:not(.phone-whole):not(.alto-retro) #title-bar>svg:is(.brand-mark,.brand-word){background:var(--surface,#fff);border-radius:10px;box-shadow:0 0 0 4px var(--surface,#fff)}'
      /* the name tab too: frosted glass let a passing card's words read under the name (no text on text): the page's own surface instead */
      +'html.ln-under:not(.phone-whole):not(.alto-retro):not(.detail-open) #title-bar #title-text:not(#_):not(#_){background:var(--surface,#fff) !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important}'
      +'html.ln-under.alto-retro:not(.phone-whole) #title-bar>svg:is(.brand-mark,.brand-word){background:#000;box-shadow:0 0 0 4px #000}'
      +'html.phone-whole.ln-under.alto-retro #nav>:is(svg.brand-mark,svg.brand-word,.title){background:#000;box-shadow:0 0 0 4px #000}'
      /* Retro's top bar is see-through (retro.py): while the board runs under it, it is the poster's black with its gold hairline, so no card's
         words stand under the name (Luke's Safari shot 2026-11-26: "EVOLUTIO… UNDER" under the title) */
      +'html.ln-under.alto-retro:not(.phone-whole):not(.detail-open) #title-bar:not(#_):not(#_){background:#000 !important;border-bottom:1px solid rgba(217,174,85,.35) !important}'
      +'html.phone-whole.ln-under:not(.alto-retro) #nav>:is(svg.brand-mark,svg.brand-word,.title){background:var(--card-glass-bg,rgba(255,255,255,.5));-webkit-backdrop-filter:blur(18px) saturate(1.9) brightness(1.1);backdrop-filter:blur(18px) saturate(1.9) brightness(1.1);border-radius:10px;box-shadow:0 0 0 4px var(--card-glass-bg,rgba(255,255,255,.5))}';
    document.head.appendChild(st);
    var tag=document.querySelector('#world .lanes-tag.ln-main-tag'), nm=(tag && tag.textContent.trim()) || 'Main timeline';
    nm=nm.charAt(0).toUpperCase()+nm.slice(1).toLowerCase();
    var b=document.createElement('button'); b.type='button'; b.className='lnv-main'; b.tabIndex=-1; b.setAttribute('aria-hidden','true');
    b.innerHTML='<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 16V4M5 9l5-5 5 5"/></svg><span></span>';
    b.querySelector('span').textContent=nm; b._nm=nm;
    b.addEventListener('click', function(e){ e.stopPropagation(); var c=cv(); if(!c || !window._altoLanesVy) return;
      /* from inside a branch, or a card of it enlarged (Luke 2026-11-27: "The lawsuit button doesn't work if a nested branch node is enlarged"):
         the card is let go, and the camera comes back to the line on the branch's parent */
      var K=window._altoLanesKids, root=(K && K.home) ? K.home() : '';
      function vy(){ var d=off(); if(d==null) return; var k=(c.offsetHeight && c.getBoundingClientRect().height/c.offsetHeight)||1; window._altoLanesVy(d/k); }
      if(root && window._altoLanesStep){ window._altoLanesStep(root); setTimeout(vy, 80); setTimeout(function(){ vy(); soon(); }, 760); return; }
      vy(); });
    nav.insertBefore(b, nav.firstChild); cues.pill=b;
  }
  /* how far the main line stands from the room's middle, screen px (+ below it), from its own label's height (the label sits on it) */
  function off(){ var y=lineY(); if(y==null) return null; var B=bounds(); return y-(B.t+B.b)/2; }
  /* the main line's screen height at the window's middle (the drawn line itself: it dips where the story turns back) */
  function lineY(){
    var pa=document.querySelector('#lanes-svg path.ln-main'); if(!pa || !pa.getTotalLength) return null; var m=pa.getScreenCTM(); if(!m) return null;
    var L=pa.getTotalLength(), lo=0, hi=L, sx=window.innerWidth/2, q;
    function X(t){ q=pa.getPointAtLength(t); return m.a*q.x+m.c*q.y+m.e; }
    if(sx<=X(0)) X(0); else if(sx>=X(L)) X(L); else { for(var i=0;i<24;i++){ var t=(lo+hi)/2; if(X(t)<sx) lo=t; else hi=t; } X((lo+hi)/2); }
    return m.b*q.x+m.d*q.y+m.f; }
  function bounds(){ return window._altoLanesExtRoom(); }
  function look(){
    raf=0; if(!cues.pill) make(); var c=cv(); if(!c || !cues.pill) return;
    var on=window._altoLanesExtOn && window._altoLanesExtOn(), mt=c.scrollHeight-c.clientHeight, y=c.scrollTop, B=bounds(), p=cues.pill;
    var a=on && mt>2 && y>2;
    if(R.classList.contains('ln-under')!==!!a) R.classList.toggle('ln-under', !!a);
    var d=on && mt>2 ? off() : null, half=(B.b-B.t)/2, side=d==null || Math.abs(d)<half-6 ? 0 : (d<0 ? -1 : 1);
    var was=p.classList.contains('on'); if(was!==!!side) p.classList.toggle('on', !!side);
    p.tabIndex=side ? 0 : -1; if(side) p.removeAttribute('aria-hidden'); else p.setAttribute('aria-hidden','true');
    if(!side || p._sd===side) return; p._sd=side;
    var sv=p.querySelector('svg'); if(sv) sv.style.transform=side<0 ? '' : 'rotate(180deg)';
    var t='Back to the main timeline, '+(side<0 ? 'above' : 'below')+': '+p._nm; p.title=t; p.setAttribute('aria-label', t);
  }
  function soon(){ if(!raf) raf=requestAnimationFrame(look); }
  var ft=0; function fix(){ clearTimeout(ft); ft=setTimeout(function(){ if(window._altoLanesRoomFix) window._altoLanesRoomFix(); }, 140); }   /* (after whatever laid the board out last: the room under its lowest card) */
  function hook(){ make(); var c=cv(); if(c && !c._lnExtCue){ c._lnExtCue=1; c.addEventListener('scroll', soon, {passive:true}); } soon(); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',hook); else hook();
  window.addEventListener('load',function(){ hook(); [400,1500,3500].forEach(function(t){ setTimeout(soon,t); setTimeout(fix,t); }); });
  window.addEventListener('resize',function(){ setTimeout(soon,80); setTimeout(fix,400); });
  if(window.MutationObserver) new MutationObserver(function(){ setTimeout(soon,60); fix(); }).observe(R,{attributes:true,attributeFilter:['class']});
  window._altoLanesCueLook=function(){ soon(); fix(); };
  window._altoLanesMainOff=function(){ return off(); };      // (how far the main line is from the room's middle: tests)
})();
"""


def lanes_ext_js(tid: str) -> str:
    """The script of a horizontal timeline whose owner turned Extend on (brief.extend): LANES_JS with the fit
    skipped while Extend is on, the reader's switch (detail_extras.EXT_VIEW_GLUE, its glyph up and down here)
    and the cues. A page without Extend carries LANES_JS untouched."""
    from .detail_extras import EXT_VIEW_GLUE
    js = LANES_JS
    for a, b in _EXT_SWAPS:
        assert js.count(a) == 1, a
        js = js.replace(a, b)
    sw = EXT_VIEW_GLUE
    for a, b in (
        ("R.classList.toggle('alto-ext-off',off); window._ALTO_TREE_PLAN=off?window._ALTO_TREE_PLAN_OFF:window._ALTO_TREE_PLAN_ON;\n"
         "    window._altoOpenLeft=(!off && window._ALTO_TREE_PLAN_ON.wide)?1:0; }",
         "R.classList.toggle('alto-ext-off',off); }"),
        ("'Extend is off: each unit fits the window. Click to let wide units scroll sideways.':'Extend is on: wide units scroll sideways. Click to fit each unit in the window.'",
         "'Extend is off: the board fits the window. Click to let it grow up and down.':'Extend is on: the board grows up and down. Click to fit it in the window.'"),
        ('<path d="M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
         '<path d="M8 4v16M8 4l-3 3M8 4l3 3M16 20V4M16 20l-3-3M16 20l3-3"/>'),
        ("if(window._ALTO_EXTEND_PAGE && R.classList.contains('phone-whole')) r.style",
         "if(window._ALTO_EXTEND_PAGE && R.classList.contains('phone-whole') && window.innerWidth>window.innerHeight) r.style"),
        ("if(window._altoUnitRefresh) setTimeout(window._altoUnitRefresh,60);",
         "if(window._altoLanesCueLook) setTimeout(window._altoLanesCueLook,80);"),
        # the desktop's switch beside Search is not made: Expanded (under Scene) and an opened branch turn Extend on (Luke 2026-11-26)
        ("    if(b || !document.body) return;\n    b=document.createElement('button'); b.type='button'; b.id='ext-view-btn';",
         "    return;\n    b=document.createElement('button'); b.type='button'; b.id='ext-view-btn';"),
    ):
        assert sw.count(a) == 1, a
        sw = sw.replace(a, b)
    return ("\nwindow._ALTO_EXTEND_PAGE=1;window._ALTO_EXT_KEY=" + js_json("alto-extview-" + tid) + ";"
            + LANES_EXT_HEAD + js + sw + LANES_EXT_TAIL)
