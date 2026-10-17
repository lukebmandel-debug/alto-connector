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
                          if lid in (ev[i].get("present") or []) or i in (ln.get("from"), ln.get("to"))]
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


def lanes_payload(b, nodes) -> dict:
    """The page's data (docs/lanes-v2-contract.md), as a dict."""
    ev = {}
    for n in nodes:
        ev[n.id] = {"l": n.line or MAIN, "w": n.when or "", "t": parse_when(n.when), "i": 0,
                    "present": [str(x) for x in (n.present or [])], "flash": n.flash or "",
                    "g": GAPS.get(n.gap or "", 0)}
    L = {"v": 2, "main": b.main_line or "",
         "order": [n.id for n in page_order(b, nodes)],
         "lines": [norm_line(ln, i) for i, ln in enumerate(b.lines)],
         "ev": ev,
         "flashbacks": [{"id": fb["id"], "label": fb.get("label") or ""} for fb in b.flashbacks or []]}
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
    l.presence=mains.filter(function(i){ return (ev[i].present||[]).indexOf(l.id)>=0 || i===l.from || i===l.to; });
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
  #lanes-svg g{transition:opacity .2s;}
  .node[data-ln] .node-card{transition:opacity .2s;}
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
    pointer-events:auto;cursor:pointer;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);}
  .lanes-tag:hover{background:var(--surface);}
  .lanes-tag.ln-main-tag{color:var(--accent);}
  .lanes-unit{position:absolute;z-index:6;top:0;border-left:1.5px solid color-mix(in srgb,var(--unit-color) 30%,transparent);pointer-events:none;}
  .lanes-unit:first-child{border-left:0;}
  .lanes-unit .lu-chip{position:absolute;left:14px;top:22px;white-space:nowrap;font-size:12px;font-weight:800;
    letter-spacing:.12em;text-transform:uppercase;color:var(--unit-color);padding:6px 12px;border-radius:9px;
    background:color-mix(in srgb,var(--surface) 80%,transparent);border:1.5px solid color-mix(in srgb,var(--unit-color) 45%,transparent);}
  .lanes-unit .lu-chip b{font-weight:800;opacity:.6;margin-right:7px;}
  html.alto-lanes:not(.mobile) #world .node-card:not(.focused) .node-desc{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;line-clamp:3;overflow:hidden;}
  .node-card .lanes-when:empty{display:none;}
  html.alto-editing .node-card .lanes-when:empty{display:block;}
  html.alto-editing .node-card .lanes-when:empty::before{content:'+ When';opacity:.7;}
  html.alto-editing:not(.mobile) .node-card .lanes-when{pointer-events:auto;cursor:text;border-radius:4px;}
  html.alto-editing:not(.mobile) .node-card .lanes-when:hover{background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--text);}
  html.alto-editing .lanes-tag{cursor:context-menu;}
  .node-card .lanes-when{display:block;font-size:10.5px;font-weight:700;letter-spacing:.06em;color:var(--muted);
    margin:-2px 0 4px;font-variant-numeric:tabular-nums;}
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
var SPAN=190, MAXPX=1000, BREAK=190, BASE=190;
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
    l.presence=mains.filter(function(i){ return (L.ev[i].present||[]).indexOf(l.id)>=0 || i===l.from || i===l.to; });
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
window._altoLanes=function(h){
  if(de.classList.contains('mobile')) return false;
  var world=document.getElementById('world'); if(!world) return false;
  derive();
  var order=[].concat.apply([],ACT_SEQS).filter(function(id){ return !!L.ev[id] && document.getElementById('node-'+id); });
  NODES.forEach(function(n){ if(order.indexOf(n.id)<0 && L.ev[n.id] && document.getElementById('node-'+n.id)) order.push(n.id); });
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
  world.querySelectorAll('.lanes-tag,.lanes-past').forEach(function(e){ e.remove(); });
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
  /* the main line: 200px either side of its events; a story that opens in a
     flashback starts just before the dip (a short present, then down) */
  var mx=mains.filter(function(i){ return !fbOf[i]; }).map(function(i){ return X[i]; }), dx=runs.map(function(r){ return r.x0; });
  if(!mx.length && !dx.length) mx=order.map(function(i){ return X[i]; });
  main.x0=Math.min(mx.length?Math.min.apply(null,mx)-200:Infinity, dx.length?Math.min.apply(null,dx)-30:Infinity);
  main.x1=Math.max(mx.length?Math.max.apply(null,mx)+200:-Infinity, runs.length?runs[runs.length-1].x1+60:-Infinity);
  var hasPast=runs.length>0;
  /* each character: where it is on the page (its presence, plus a legacy
     from / to on another character's line) and its own events */
  L.lines.forEach(function(l){
    var pr=(l.presence||[]).filter(function(i){ return X[i]!=null; });
    [l.from,l.to].forEach(function(f){ if(f && X[f]!=null && pr.indexOf(f)<0 && L.ev[f].l!==l.id) pr.push(f); });
    l.pr=pr; l.sd=l.side==='below'?1:-1;
    var xs=pr.map(function(i){ return X[i]; }).concat(l.ev.map(function(i){ return X[i]; }));
    l.drawn=xs.length>0;
    if(!xs.length){ l.x0=l.x1=null; return; }
    var a=Math.min.apply(null,xs), b=Math.max.apply(null,xs);
    var lead=pr.some(function(i){ return X[i]===a; }) ? RAMP_MAX+SPREAD*2 : 30;
    var tail=pr.some(function(i){ return X[i]===b; }) ? RAMP_MAX+SPREAD*2+40 : 70;
    l.x0=a-lead-l.tagW-6; l.x1=b+tail;
  });
  /* tracks: nearest the main line first, a track shared by lines that never run at the same time */
  var track={'-1':[], '1':[]};
  L.lines.forEach(function(l){
    if(!l.drawn) return;
    var T=track[String(l.sd)], k=0;
    for(;k<T.length;k++){ if(T[k].every(function(o){ return l.x1+40<o.x0 || o.x1+40<l.x0; })) break; }
    (T[k]=T[k]||[]).push(l); l.track=k;
  });
  main.y=0; var pastY=PAST;
  var base={'-1':BAND0, '1':hasPast?PAST+BAND0-14:BAND0};
  L.lines.forEach(function(l){ if(l.drawn) l.y=l.sd*(base[String(l.sd)]+l.track*TRACK); else l.y=0; });
  var band={'-1':track['-1'].length?base['-1']+(track['-1'].length-1)*TRACK+22:0,
            '1':track['1'].length?base['1']+(track['1'].length-1)*TRACK+22:(hasPast?PAST+22:0)};
  /* the cards: beyond the band, packed outward wherever one would overlap another */
  var placed={'-1':[], '1':[]}, sideOf={}, offOf={}, alt=0;
  function fit(sd, id, minOff){
    var lo=X[id]-w[id]/2-CARD_PAD, hi=X[id]+w[id]/2+CARD_PAD, hh=h[id]||120, off=minOff, moved=true;
    while(moved){ moved=false;
      placed[sd].forEach(function(r){ if(lo<r.hi && hi>r.lo && off<r.y1+CARD_GAP && off+hh+CARD_GAP>r.y0){ off=r.y1+CARD_GAP; moved=true; } }); }
    return {off:off, lo:lo, hi:hi, y0:off, y1:off+hh};
  }
  order.slice().sort(function(a,b){ return X[a]-X[b] || idx[a]-idx[b]; }).forEach(function(id){
    var ln=lineOfEv(id), sides=ln===main ? (fbOf[id]?['1']:['-1','1']) : [String(ln.sd)], best=null;
    sides.forEach(function(sd, si){
      var from=ln===main ? (fbOf[id]?pastY:0) : Math.abs(ln.y);
      var c=fit(sd, id, Math.max(band[sd], ln===main&&!fbOf[id]?0:from)+STEM);
      if(!best || c.off<best.c.off-1 || (Math.abs(c.off-best.c.off)<=1 && si===alt)) best={sd:sd, c:c};
    });
    placed[best.sd].push(best.c); sideOf[id]=+best.sd; offOf[id]=best.c.off;
    if(ln===main && !fbOf[id]) alt=1-alt;
  });
  var cy={};
  order.forEach(function(id){ cy[id]=sideOf[id]*(offOf[id]+(h[id]||120)/2); });
  var ys=[0, hasPast?pastY+30:0];
  L.lines.forEach(function(l){ if(l.drawn) ys.push(l.y-16, l.y+16); });
  order.forEach(function(id){ ys.push(cy[id]-(h[id]||120)/2, cy[id]+(h[id]||120)/2); });
  var y0=Math.min.apply(null,ys), y1=Math.max.apply(null,ys), dy=TOP-y0;
  var xe=[S.end, main.x1]; L.lines.forEach(function(l){ if(l.drawn) xe.push(l.x1); });
  var W=Math.max.apply(null,xe)+RIGHT, H=y1+dy+BOTTOM;
  lines.forEach(function(l){ l.y+=dy; }); pastY+=dy;
  runs.forEach(function(r){ r.y=pastY; });
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
                       pastY:pastY, sideOf:sideOf, shift:shift});
  units(world, order, X, w, H, W);
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
  window._altoLanesGeo={x:X, y:pos, h:h, lines:lines, W:W, H:H, mainY:main.y, at:geo.at, presence:geo.presence,
    detours:runs.map(function(r){ return {id:r.id, label:r.label, range:r.range, nodes:r.nodes.slice(), x0:r.x0, x1:r.x1,
      d0:r.d0, d1:r.d1, f0:r.f0, f1:r.f1, y:r.y, prev:r.prev, next:r.next}; })};
  _actBands=ACT_SEQS.map(function(){ return {startY:0, endY:H}; });
  /* the first time: open at the start of time, not the engine's centre */
  if(!window._altoLanesOpened){ window._altoLanesOpened=1; var cv=document.getElementById('canvas'); if(cv){ cv.scrollLeft=0; setTimeout(function(){ if(!window._focusedNodeId) cv.scrollLeft=0; }, 60); } }
  var svgR=document.getElementById('river-svg'); if(svgR) svgR.innerHTML='';
  return true;
};
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
  var nums=order.every(function(id){ var w=L.ev[id].w; return !w || /^-?\d{1,6}(-\d{1,2}){0,2}$/.test(String(w).trim()); });
  if(!order.some(function(id){ return L.ev[id].t!=null && !fbOf[id]; })) nums=false;   // nothing dated: no clock to show
  var inDetour=function(x){ return runs.some(function(r){ return x>r.x0-4 && x<r.x1+4; }); };
  if(nums){ var cuts=[main.x0]; runs.forEach(function(r){ cuts.push(r.x0, r.x1); }); cuts.push(main.x1);
    for(var c=0;c+1<cuts.length;c+=2) if(cuts[c+1]>cuts[c]+60) el('line',{'class':'ln-rule', x1:cuts[c], x2:cuts[c+1], y1:ay, y2:ay},tk); }
  S.segs.forEach(function(sg){
    if(sg.t1==null || sg.t1<=sg.t0 || !nums) return;
    var step=nice(220/S.s); if(step<1) step=1;
    for(var v=Math.ceil(sg.t0/step)*step; v<=sg.t1+1e-9; v+=step){
      var raw=sg.x0+(v-sg.t0)*S.s, x=raw+G.shift(raw, -1); if(x<main.x0+30 || x>main.x1-30 || inDetour(x)) continue;
      el('line',{'class':'ln-tick', x1:x, x2:x, y1:ay, y2:ay+8},tk);
      var tl=el('text',{'class':'ln-ticklbl', x:x, y:ay+22, 'text-anchor':'middle'},tk); tl.textContent=String(Math.round(v*100)/100);
    }
  });
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
    var hug=HUG0+l.track*HUG_STEP;
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
    if(!meets[id]) el('circle',{'class':'ln-dot', cx:x, cy:ly, r:6.5, fill:c},g);   // with characters there, their rings mark it
  });
  /* where a character meets the page: a ring in its colour, on top of everything */
  marks.forEach(function(m){
    var g=el('g',{'data-ln':m.l.id, 'class':'ln-meet'},svg);
    el('circle',{'class':'ln-ring', cx:m.x, cy:m.y, r:5.5, stroke:m.c},g);
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
  document.querySelectorAll('.node[id^="node-"]').forEach(function(n){ whenChip(n.querySelector('.node-card'), n.id.slice(5)); }); }
['DOMContentLoaded','load'].forEach(function(ev){ window.addEventListener(ev, function(){ phoneChips(); setTimeout(phoneChips, 400); }); });
function lineOf(lines,id){ for(var i=0;i<lines.length;i++) if(lines[i].ev.indexOf(id)>=0) return lines[i]; return null; }
function tag(world, l, x, y, c, before){
  var t=document.createElement('div'); t.className='lanes-tag'+(l.id==='main'?' ln-main-tag':''); t.style.left=x+'px'; t.style.top=y+'px';
  if(before) t.style.transform='translate(-100%,-50%)';
  t.style.color=c; t.textContent=l.label||''; t.setAttribute('data-ln-tag', l.id);
  t.title='Show only this line — click again for all';
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
  function live(i){ var c=document.querySelector('#node-'+i+' .node-card'); return c && !c.classList.contains('dimmed') && !c.classList.contains('ent-dimmed') && !c.classList.contains('rel-dimmed'); }
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
   arcs to it. A click keeps it; hovering shows it for as long as you point. */
var _lock=null, _ht=null;
/* the kept line, for stepping (lanes_nav.py: a character's events only); with an
   argument, keep that line (null: all of them again) */
window._altoLanesLock=function(id){ if(arguments.length){ _lock=id||null; isolate(_lock); } return _lock; };
function isolate(id){
  var cv=document.getElementById('canvas'); if(!cv) return;
  document.querySelectorAll('.ln-on').forEach(function(x){ x.classList.remove('ln-on'); });
  if(!id){ cv.classList.remove('ln-dimline'); return; }
  cv.classList.add('ln-dimline');
  /* the line, its own events, and the main-line events where it is on the page (data-lp) */
  document.querySelectorAll('[data-ln~="'+id+'"],[data-lp~="'+id+'"],[data-ln-tag="'+id+'"],.lk-row[data-k="'+id+'"]').forEach(function(x){ x.classList.add('ln-on'); });
  var l=null; L.lines.forEach(function(q){ if(q.id===id) l=q; });
  if(l) [l.from,l.to].forEach(function(f){ var n=f && document.getElementById('node-'+f); if(n) n.classList.add('ln-on'); });
}
function lnOf(t){
  if(!t || !t.closest) return null;
  var k=t.closest('.lk-row[data-k],.lanes-tag'); if(k) return k.getAttribute('data-k')||k.getAttribute('data-ln-tag');
  var h=t.closest('#lanes-svg g[data-ln]'); if(h && t.classList.contains('ln-hit')) return h.getAttribute('data-ln');
  var n=t.closest('#canvas .node[data-ln]'); return n ? n.getAttribute('data-ln') : null;
}
document.addEventListener('mouseover', function(e){
  if(_lock || de.classList.contains('mobile') || !window._altoLanesGeo) return;
  var id=lnOf(e.target), cv=document.getElementById('canvas');
  if(cv && cv.classList.contains('focus-mode')) return;
  clearTimeout(_ht); _ht=setTimeout(function(){ if(!_lock) isolate(id); }, id ? 140 : 220);
});
document.addEventListener('click', function(e){
  var t=e.target.closest && e.target.closest('.lanes-tag,.lk-row[data-k]'); if(!t || de.classList.contains('alto-editing')) return;
  e.stopPropagation(); var id=t.getAttribute('data-ln-tag')||t.getAttribute('data-k');
  _lock=(_lock===id)?null:id; isolate(_lock||id);
}, true);
document.addEventListener('keydown', function(e){ if(e.key==='Escape' && _lock){ _lock=null; isolate(null); } });
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
  h+='<div class="lk-row" data-k="main">'+sw('var(--accent)','',5)+'<div><b>'+esc(L.main||'Main line')+'</b><small>The main line: what is on the page, in the order the story tells it</small></div></div>';
  L.lines.forEach(function(l){
    var n=(l.presence||[]).length, o=(l.events||[]).length, w=[];
    if(n) w.push('on the page at '+n+' event'+(n>1?'s':'')+((l.presence||[])[0]?', first at “'+esc(T(l.presence[0]))+'”':''));
    if(o) w.push(o+' event'+(o>1?'s':'')+' of its own');
    h+='<div class="lk-row" data-k="'+esc(l.id)+'">'+sw(l.color,'',5)+'<div><b>'+esc(l.label)+'</b><small>'+(w.join(' · ')||'not on the page yet')+'</small></div></div>';
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
  h+='<small style="margin-top:4px">Point at a line, its label or a card to follow it; click a label to keep it.</small></div>';
  k.innerHTML=h; window._altoKeyToggle(k, 'alto-lanes-key', 'Key to the lines');
}
window.addEventListener('load', function(){ setTimeout(key, 300); });
})();
"""

# going round the timeline: step event to event (lanes_nav.py)
LANES_CSS += NAV_CSS
LANES_JS += NAV_JS
