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
            if n.line or n.when or n.present or n.flash or n.gap:
                raise BriefError(f"node {n.id}: line / when / present / flash / gap need mode 'lanes'")
        return
    by = {n.id: n for n in nodes}
    lids = {ln["id"] for ln in b.lines}
    fids = {fb["id"] for fb in (b.flashbacks or [])}
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
    lines were the only lines drawn, so a character the brief never named (SONYA, Anya,
    Daisy, Elana on terrarium-horizontal) had a chip and no line. An entity is matched to
    a brief line by id, or by its name / an alias against the line's label ("Marc Voss");
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


def lanes_payload(b, nodes) -> dict:
    """The page's data (docs/lanes-v2-contract.md), as a dict."""
    lines, of = chip_lines(b, nodes)
    ev = {}
    for n in nodes:
        main = (n.line or MAIN) == MAIN
        chips = [] if not main else [of[e] for e in (n.entity_ids or []) if e in of and of[e] != n.line]
        ev[n.id] = {"l": n.line or MAIN, "w": n.when or "", "t": parse_when(n.when), "i": 0,
                    "present": [str(x) for x in (n.present or [])], "flash": n.flash or "",
                    "ent": list(dict.fromkeys(chips)),
                    "g": GAPS.get(n.gap or "", 0), "gap": n.gap or ""}
    L = {"v": 2, "main": b.main_line or "",
         "order": [n.id for n in page_order(b, nodes)],
         "lines": lines,
         "ev": ev,
         "flashbacks": [{"id": fb["id"], "label": fb.get("label") or ""} for fb in b.flashbacks or []],
         "tf": [norm_flag(f) for f in b.time_flags or []]}
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
  .lanes-unit .lu-chip{position:absolute;left:14px;top:22px;white-space:nowrap;font-size:12px;font-weight:800;
    letter-spacing:.12em;text-transform:uppercase;color:var(--unit-color);padding:6px 12px;border-radius:9px;
    background:color-mix(in srgb,var(--surface) 80%,transparent);border:1.5px solid color-mix(in srgb,var(--unit-color) 45%,transparent);}
  .lanes-unit .lu-chip b{font-weight:800;margin-right:7px;}
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
  if((q=vis(document.getElementById('key-toggle'))) && q.bottom>r.top) t=Math.max(t, (q.bottom-r.top)/k+12);
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
window._altoLanes=function(h){
  if(de.classList.contains('mobile')) return false;
  var world=document.getElementById('world'); if(!world) return false;
  derive();
  hideOut();
  var order=[].concat.apply([],ACT_SEQS).filter(function(id){ return !!L.ev[id] && document.getElementById('node-'+id) && !hidEv(id); });
  NODES.forEach(function(n){ if(order.indexOf(n.id)<0 && L.ev[n.id] && document.getElementById('node-'+n.id) && !hidEv(n.id)) order.push(n.id); });
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
  world.querySelectorAll('.lanes-tag,.lanes-past,.lanes-gap,.lanes-flag,.lanes-flaglist').forEach(function(e){ e.remove(); });
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
  var FLG=timeFlags(order, fbOf), hasFl=FLG.length>0, FLR=hasFl ? (FLG.length>1 ? 2*FL_ROW : FL_ROW) : 0, AX=(nums||hasFl)?54:0;
  var hIn=h, hh={}, cards=order.filter(function(id){ return !!document.querySelector('#node-'+id+' .node-card'); });
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
  var rows={'-1':mode.one?0:mode.R, '1':mode.R}, placed={'-1':[], '1':[]}, sideOf={}, offOf={}, alt=0, cum=0, PX=[], X0={};
  var rowOff=function(sd,r){ return band[sd]+STm+r*(HR+CARD_GAP); };
  order.slice().sort(function(a,b){ return X[a]-X[b] || idx[a]-idx[b]; }).forEach(function(id){
    var ln=lineOfEv(id), x0=X[id], x=x0+cum, half=w[id]/2+CARD_PAD;
    var sides=mode.one ? ['1'] : ln===main ? (fbOf[id]?['1']:(alt?['1','-1']:['-1','1'])) : [String(ln.sd)];
    var pick=null, best=null;
    for(var r=0;r<3 && !pick;r++) sides.forEach(function(sd){
      if(pick || r>=rows[sd]) return;
      var row=placed[sd][r]||[], lo=x-half, hi=x+half, blk=row.filter(function(q){ return lo<q[1] && hi>q[0]; });
      if(!blk.length){ pick={sd:sd, r:r, x:x}; return; }
      var nx=Math.max.apply(null, blk.map(function(q){ return q[1]; }))+half;
      if(!best || nx<best.x-.5) best={sd:sd, r:r, x:nx};
    });
    pick=pick||best;
    cum+=pick.x-x; X0[id]=x0; X[id]=pick.x; PX.push([x0, cum]);
    (placed[pick.sd][pick.r]=placed[pick.sd][pick.r]||[]).push([pick.x-half, pick.x+half]);
    sideOf[id]=+pick.sd; offOf[id]=rowOff(pick.sd, pick.r);
    if(ln===main && !fbOf[id]) alt=1-alt;
  });
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
  var cy={};
  order.forEach(function(id){ cy[id]=sideOf[id]*(offOf[id]+(h[id]||HR)/2); });
  var ys=[-16*mode.cz, 16*mode.cz, hasPast?pastY+30:0];
  L.lines.forEach(function(l){ if(l.drawn) ys.push(l.y-TH/2, l.y+TH/2); });
  order.forEach(function(id){ ys.push(cy[id]-(h[id]||HR)/2, cy[id]+(h[id]||HR)/2); });
  /* the flags' lane: pennants in rows above everything (a flag that would overlap the one before it goes up a row) */
  var frows=flagRows(world, FLG), flTop=Math.min.apply(null,ys)-6;
  if(frows) ys.push(flTop-frows*FL_ROW);
  FLG.forEach(function(f){ f.y=flTop-FL_ROW*(f.row+.5); });
  var y0=Math.min.apply(null,ys), y1=Math.max.apply(null,ys)+AX;
  /* the board's top where the room starts (the slack shared above and below); the page no taller than the canvas */
  var dy=room ? room.top-room.wo-WORLD_PAD_TOP-y0+Math.max(0, A-(y1-y0))/2 : TOP-y0;
  var xe=[S.end+sh, push(S.end)+sh, main.x1]; L.lines.forEach(function(l){ if(l.drawn) xe.push(l.x1); });
  order.forEach(function(id){ xe.push(X[id]+w[id]/2); });
  var W=Math.max.apply(null,xe)+RIGHT, H=y1-AX+dy+((nums||hasFl)?AX+BOTTOM-56:24);
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
                       pastY:pastY, sideOf:sideOf, shift:shiftAll, z:mode.cz, flags:FLG, w:w});
  units(world, order, X, w, H, W);
  /* the frosted slab (units() placed it) ends at the board's foot — at the canvas's when the board fits, never short of the
     canvas less its top padding (the engine's place() would lay the page out again every 250ms) — its height corrected by
     the difference, whatever its box; and the world ends where it does, in place()'s own terms (two different heights
     ping-pong in its ResizeObserver: WebKit's "loop completed with undelivered notifications") */
  var slab=document.getElementById('glass-slab');
  if(slab){
    var foot=Math.ceil((room && y1-y0<=A) ? room.ch-room.pt : H+WORLD_PAD_TOP);
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
  window._altoLanesGeo={flags:FLG.map(function(f){ return {id:f.id, label:f.label, x:f.x, x2:f.x2, row:f.row, y:f.y}; }), x:X, y:pos, h:h, lines:lines, W:W, H:H, mainY:main.y, at:geo.at, presence:geo.presence,
    detours:runs.map(function(r){ return {id:r.id, label:r.label, range:r.range, nodes:r.nodes.slice(), x0:r.x0, x1:r.x1,
      d0:r.d0, d1:r.d1, f0:r.f0, f1:r.f1, y:r.y, prev:r.prev, next:r.next}; })};
  _actBands=ACT_SEQS.map(function(){ return {startY:0, endY:H}; });
  /* the bars and the rail arrive after the first layout: lay out again if the room they leave changed */
  window._altoLanesH=hIn;
  if(!window._altoLanesRefit){ window._altoLanesRefit=1;
    var again=function(){ var f=window._altoLanesFit, r2=lanesRoom(world); if(!f || !f.room || !r2 || !window._altoLanesH || de.classList.contains('mobile')) return;
      if(Math.abs(r2.b-f.room.b)>6 || Math.abs(r2.top-f.room.top)>6 || Math.abs(r2.ch-f.room.ch)>6) window._altoLanes(window._altoLanesH); };
    [700, 1800].forEach(function(ms){ setTimeout(again, ms); });
    window.addEventListener('load', function(){ setTimeout(again, 300); }); }
  /* the first time: open at the start of time, not the engine's centre */
  if(!window._altoLanesOpened){ window._altoLanesOpened=1; var cv=document.getElementById('canvas'); if(cv){ cv.scrollLeft=0; setTimeout(function(){ if(!window._focusedNodeId) cv.scrollLeft=0; }, 60); } }
  var svgR=document.getElementById('river-svg'); if(svgR) svgR.innerHTML='';
  /* last of all, the world ends where the slab now does, in the engine's place()'s own terms: two different heights
     ping-pong in its ResizeObserver (WebKit: "loop completed with undelivered notifications") */
  var sl=document.getElementById('glass-slab');
  if(sl && sl.offsetHeight){ var wcs=getComputedStyle(world), pads=(parseFloat(wcs.paddingTop)||0)+(parseFloat(wcs.paddingBottom)||0);
    var mh=Math.max(0, sl.offsetTop+sl.offsetHeight-pads)+'px'; if(world.style.minHeight!==mh) world.style.minHeight=mh; }
  return true;
};
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
  var F=(L.tf||[]).filter(function(f){ return f && f.label; }); if(!F.length) return;
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
      s.className='lanes-fchip'; if(f.color) s.style.setProperty('--flag-c', f.color);
      s.textContent=f.label+(f.at ? ' · '+f.at+era : ''); box.appendChild(s); });
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
/* the units: columns of time, each from its first event to its last */
function units(world, order, X, w, H, W){
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
  var stops=[];
  ACT_SEQS.forEach(function(ids,a){
    var pm=PHASE_META[a]; if(!pm || !R[a]) return;
    var u=document.createElement('div'); u.className='lanes-unit';
    u.style.left=cuts[a]+'px'; u.style.width=(cuts[a+1]-cuts[a])+'px'; u.style.height=(H+WORLD_PAD_TOP)+'px';
    u.style.setProperty('--unit-color', pm.colorRaw);
    u.innerHTML='<div class="lu-chip"><b></b><span></span></div>';
    if(cuts[a]<=0) u.querySelector('.lu-chip').style.left='66px';   // clear of the key's toggle at the top left
    u.querySelector('b').textContent=pm.numeral; u.querySelector('span').textContent=(pm.label.split(' — ')[1]||pm.label);
    world.insertBefore(u, world.firstChild);
    stops.push(pm.colorRaw+'b3 '+((cuts[a]+cuts[a+1])/2/W*100).toFixed(1)+'%');
  });
  var slab=document.getElementById('glass-slab');
  if(!slab){ slab=document.createElement('div'); slab.id='glass-slab'; world.insertBefore(slab, world.firstChild); }
  slab.style.top='0px'; slab.style.height=(H+WORLD_PAD_TOP+200)+'px';
  ['width',W+'px','left','0px','transform','none'].forEach(function(v,i,a){ if(i%2===0) slab.style.setProperty(v,a[i+1],'important'); });
  if(stops.length) slab.style.backgroundImage='linear-gradient(90deg, '+stops[0].split(' ')[0]+' 0%, '+stops.join(', ')+', '+stops[stops.length-1].split(' ')[0]+' 100%)';
  window._headerTint={slabTop:0, slabH:H, stops:[{p:0,c:PHASE_META[0].colorRaw},{p:100,c:PHASE_META[0].colorRaw}]};
  if(window.updateHeaderTint) try{ window.updateHeaderTint(); }catch(e){}
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
document.addEventListener('keydown', function(e){ if(e.key==='Escape' && PICK.length && !_escBusy) setPick([]); });
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
})();
"""

# going round the timeline: step event to event (lanes_nav.py)
LANES_CSS += NAV_CSS
LANES_JS += NAV_JS
