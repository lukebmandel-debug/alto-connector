# Lanes v2 contract (horizontal timeline, `brief.mode: "lanes"`)

Owner: agent A (data model, validation, tools, edit-mode fold). Agents B
(drawing) and C (navigation) code against this. Field names here are stable;
anything added later is additive.

## The model in one paragraph

The **main line** is what is on the page, in the order the story tells it
(page order = units in order, and inside a unit the material's node order —
exactly `ACT_SEQS` flattened). Every other line is a **character** (or a place,
a thread) while they are **not** on the page. When a character is on the page
at a main-line event, the character's solid line dips onto the main line,
meets it at that event, and leaves again. A **flashback** is a run of
consecutive main-line events that the story tells out of time: the main line
itself dips onto a labelled past stretch (its events' `when` is story time),
then rises back where the present resumes. No dashed lines carry "flashback"
or "on the page" any more; dashes are only for genuine extra meaning (e.g. the
material's own connections between events).

## Authored data (brief + nodes)

### brief

| field | type | meaning |
|---|---|---|
| `main_line` | string | the main line's label ("" = none) |
| `lines` | `[{id, label, color?, side?, from?, to?}]` | characters / places / threads. `id` lowercase slug (`^[a-z0-9][a-z0-9_-]{0,40}$`), not `main`. `color` `#rrggbb` (palette default). `side` `"above"`/`"below"` (alternates by default). **`from`/`to` are LEGACY** (v1 "branches off at / converges into" a node); still accepted and still validated, see Back-compat. |
| `flashbacks` | `[{id, label}]` | NEW. Each a labelled past detour of the main line. `id` slug as above, unique, must not equal a line id or `main`. `label` required, e.g. "Ten years earlier". |

### node (lanes fields only)

| field | type | meaning |
|---|---|---|
| `line` | string | `""` or `"main"` = a main-line event (on the page). A line id = an event on that character's own line, off the page (backstory, what they do while not in the story). Unchanged from v1. |
| `when` | string | when it happened, in the material's words ("1842-03", "Day 3"). For flashback events it is **story time** (the past); surrounding present events keep theirs. |
| `present` | `[line id]` | NEW, main-line events only. The characters on the page at this event. Each must be a known line id, no duplicates, never `main`. |
| `flash` | string | NEW, main-line events only. A `brief.flashbacks` id: this event is inside that flashback. |

### Validation (`lanes.check_lines` / `lanes.check_nodes`)

Errors (`BriefError`):
- `flashbacks` / node `present` / node `flash` without `mode: "lanes"`.
- `flashbacks`: not a list, entry not an object, bad / duplicate id, id equal
  to a line id or `main`, missing label, unknown keys.
- node `present` on an event that is on a character's own line ("present is
  only for main-line events…"); unknown line id in `present`; `main` in
  `present`; `present` not a list of strings.
- node `flash` on a non-main event; `flash` not a declared flashback id.
- **consecutive rule**: the main-line events carrying one flash id must be
  consecutive among main-line events in page order (character-line events in
  between do not break a run). A second, separate run of the same id is an
  error ("…use a second flashback for the later one").

Warnings:
- a flashback with no events; a line with no events and no presence.
- a flashback whose latest dated `when` is not earlier than the dated `when`
  of the main-line event right after it (where the present resumes) — "a
  flashback should be set before the moment the story returns to".
- duplicate ids inside one `present` list are an error; an event that lists a
  character in `present` and is also that character's legacy `from`/`to` is fine.

## What the page receives: `window._ALTO_LANES`

Emitted by `lanes.lanes_data(b, nodes)` (before `LANES_JS`). Exact shape:

```js
window._ALTO_LANES = {
  v: 2,
  main: "The town",                 // brief.main_line ("" = none)
  order: ["a", "b", ...],           // every node id, page order (== ACT_SEQS flattened)
  lines: [{
    id: "mara", label: "Mara",
    color: "#e07a5f",               // always filled (palette default)
    side: "above" | "below",        // always filled
    from: "" | node id,             // LEGACY, as authored ("" = none)
    to:   "" | node id,             // LEGACY
    events:   [node ids],           // its own events (node.line == id), page order
    presence: [node ids],           // main-line events where it is on the page, page order:
                                    //   ev[x].present contains id, PLUS legacy from/to
                                    //   when that node is a main-line event
    span: [first id, last id] | []  // page-order extent of events ∪ presence
                                    //   (the stretch over which its line is drawn continuous)
  }],
  ev: {                             // one per node
    "a": {
      l: "main" | line id,          // the line it is on
      w: "1852-06",                 // when, as written ("" = none)
      t: 1852.41 | null,            // parse_when(w)
      i: 0,                         // index in `order`
      present: [line ids],          // AS AUTHORED on the node (no legacy additions); [] if none
      flash: "" | flashback id      // as authored
    }
  },
  flashbacks: [{
    id: "storm", label: "The storm of 1810",
    nodes: [node ids],              // its events, page order (one consecutive run)
    prev: "" | node id,             // the main-line event just before the detour ("" = it opens the story)
    next: "" | node id              // the main-line event where the present resumes ("" = story ends in it)
  }]
};
window._altoLanesDerive(L, order?)  // recomputes the derived fields, see below
```

Kept from v1 for existing drawing code: `main`, `lines[].{id,label,color,side,from,to}`,
`ev[].{l,w,t}`. Everything else is new.

**Authored vs derived.** `ev[].l/w/t/present/flash`, `lines[].{id,label,color,side,from,to}`,
`flashbacks[].{id,label}` and `main` are the authored state — manual edit mode
mutates exactly these. `order`, `ev[].i`, `lines[].events/presence/span` and
`flashbacks[].nodes/prev/next` are derived. After any edit (or when the page's
order differs, e.g. edit mode added a card), call
`window._altoLanesDerive(window._ALTO_LANES, order)` — `order` defaults to
`ACT_SEQS` flattened when that global exists, else `L.order`. It returns `L`,
mutated in place, and computes exactly what Python computed (tested). Manual
edit mode already calls it before its relayout. Drawing code (B) should read
derived fields fresh on each layout pass rather than caching them.

## Tools (Claude's side)

- `create_timeline` brief: `main_line`, `lines`, `flashbacks`.
- `add_nodes`: `line`, `when`, `present`, `flash` per node (validated against the brief).
- `set_lines(timeline_id, lines, flashbacks?, main_line?)` (NEW tool): replaces
  lines (and flashbacks / main_line when given); refused while an event still
  names something it would remove.
- Interview guide §D-Lanes asks: "Who is on the page in each scene, and where
  does the story jump back in time?"

## Samples

- `samples/lanes_v2_brief.json` — v2: three characters (one with no own
  events, only presence), a two-event flashback mid-story, character-line
  events between main-line ones. Use it for drawing / navigation work.
- `samples/lanes_brief.json` — v1 (legacy from/to, a to-only "flashback"
  line); must keep building and look sensible.
- The homepage "lanes" starter (`alto/build/starter.py`) is v2: two
  characters, one off-page event, a one-event flashback.

## Back-compat (v1 timelines and briefs)

- `from`/`to` still validate as before (must name a node not on the line
  itself; `to` not dated before `from`). In the page data they become
  **presence**: a legacy `from`/`to` that is a main-line event is added to
  `lines[].presence` (and so to `span`). A `from`/`to` on another character's
  line stays only in `from`/`to`. B may additionally use `from`/`to` to draw
  the old branch-off / converge shape, but the v2 picture (dip onto the main
  line at each presence) is the intended one.
- A line with no `from` and no `to` is a plain continuous character line. A
  line with only `to` (v1 "dashed flashback") is **not** dashed any more: it
  is a character line present at `to`. Real flashbacks are `brief.flashbacks`
  + `node.flash`.
- v1 data had no `v`; v2 always sends `v: 2`.

## Manual edit mode (page ops, folded by `alto/edits.py`)

All ops are `{b: what the page showed, v: what it shows now, t}` like every
other field.

| key | v | meaning |
|---|---|---|
| `n|<id>|when` | string | unchanged |
| `n|<id>|line` | `""` or line id | unchanged |
| `ln|<lineid>` | whole line `{id,label,color,side,from,to}` or `null` | unchanged (removing a line also needs its presence gone: the fold strips a removed line's id from every node's `present`) |
| `n|<id>|present` | `[line ids]` | NEW. The whole list after the change (a toggle sends the full new list). Compared as a set; stored in brief line order; `[]` removes the key. |
| `n|<id>|flash` | `""` or flashback id | NEW. Mark / unmark one event. Marking a group = one op per event (send them together with `changes([...])`). |
| `fb|<fbid>` | `{id, label}` or `null` | NEW. Add / rename / remove a flashback. Removing it also clears `flash` on its events (the fold does this). New ids from the page: `fb-` + 5 base-36 chars. |

Page side (manual_edit.py, done by A): `field()` handles the three new keys
against `window._ALTO_LANES` and calls `_altoLanesDerive` + relayout. The card's
line menu (the ⟿ "Which line is … on?" menu) gains, for a main-line event:
"On the page here: <character>" toggles, "Part of a flashback…" (pick one /
new one / "Not a flashback"). B/C may restyle or move these; the op keys and
values above are the contract.
