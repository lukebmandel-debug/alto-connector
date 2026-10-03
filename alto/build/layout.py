"""Server-side layout: column assignment, baseY hints, lane feasibility,
mobile grid.

The baseY resolver is a verbatim Python port of the engine's initLayout()
(engine/FROZEN/terrarium_glass.html ~l.2387): Pass A per-act collision
resolution, Pass B act-boundary enforcement, outer loop to fixpoint, then the
act-1 LABEL_RESERVE shift. The engine re-runs the same algorithm in the
browser over real DOM heights, so these positions are hints that must already
be a fixpoint under the ESTIMATED heights — the browser then only makes small
adjustments for real text metrics.

NOTE the y-model quirk mirrored from the engine: positions are treated as card
CENTERS in the vgap formula but as card TOPS in the topGap formula; the push
writes max(center-model, top-model) exactly as the patched engine does.
"""
from __future__ import annotations

from .brief import COL_SETS
from .estimate import card_height

CARD_W = 285
GAP = 40
LABEL_RESERVE = 184
BOTTOM_PAD = 40
ACT_BOUNDARY_GAP = 210
RHYTHM_STEP = 90          # median inter-node cascade step in the reference build
HUB_DROP = RHYTHM_STEP    # outline (flow): a child's top sits at least this far below its hub's

# Lane-feasibility constants (verify_terrarium.py §D2)
WORLD_W, HALF, HALF_CENTER, CLR, EDGE = 1700, 135, 145, 24, 8

MOBILE_STEP = 200
MOBILE_OX = 80
MOBILE_OY = 400
MOBILE_WORLD_W = 960


class LayoutError(ValueError):
    pass


def check_columns(columns: int):
    """Port of verify §D2: the grid must be symmetric about 850 and leave ≥4
    mirror-paired free vertical lanes ≥24px for the offset-lane router."""
    colx = COL_SETS[columns]
    xs = sorted(colx.values())
    for a, b in zip(xs, reversed(xs)):
        if a + b != 2 * 850:
            raise LayoutError(f"column set not symmetric about 850: {xs}")
    bands = sorted((x - (HALF_CENTER if k == "center" else HALF) - CLR,
                    x + (HALF_CENTER if k == "center" else HALF) + CLR)
                   for k, x in colx.items())
    merged = []
    for lo, hi in bands:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    free, cur = [], EDGE
    for lo, hi in merged:
        if lo > cur:
            free.append((cur, min(lo, WORLD_W - EDGE)))
        cur = max(cur, hi)
    if cur < WORLD_W - EDGE:
        free.append((cur, WORLD_W - EDGE))
    free = [g for g in free if g[1] - g[0] >= 24]
    if len(free) < 4:
        raise LayoutError(f"only {len(free)} free lanes: {free}")
    for a, b in zip(free, reversed(free)):
        if not (abs((a[0] + b[1]) - 1700) <= 2 and abs((a[1] + b[0]) - 1700) <= 2):
            raise LayoutError(f"lanes not mirror-paired about 850: {free}")
    return free


def assign_columns(nodes, columns: int):
    """Fill in missing node.col values: center for each act's first node, then
    a deterministic zig-zag, spilling to far columns (5-col) when one side runs
    ≥120px deeper than the alternative. Claude normally assigns cols itself;
    this is the fallback."""
    colx = COL_SETS[columns]
    inner = ["left", "right"]
    outer = ["far-left", "far-right"] if columns == 5 else inner
    bottoms = {k: 0.0 for k in colx}
    side = 0
    last_act = None
    for n in nodes:
        h = card_height(n.desc, n.title)
        if not n.col:
            if n.act != last_act:
                n.col = "center"
            else:
                cand = inner[side % 2]
                # spill outward if the inner column is much deeper
                if columns == 5 and bottoms[cand] - bottoms[outer[side % 2]] >= 120:
                    cand = outer[side % 2]
                n.col = cand
                side += 1
        last_act = n.act
        bottoms[n.col] += h + GAP


def _initial_positions(nodes, heights):
    """Sequential cascade: each node starts RHYTHM_STEP below the previous
    node's top, clamped so no estimated overlap exists with any earlier node in
    a horizontally-conflicting column. Positions are card CENTERS."""
    colx = None  # set per call below
    positions = {}
    prev_top = None
    for n in nodes:
        h = heights[n.id]
        top = LABEL_RESERVE if prev_top is None else prev_top + RHYTHM_STEP
        positions[n.id] = top + h / 2
        prev_top = top
    return positions


def resolve(nodes, columns: int, act_count: int, parent: dict = None):
    """Compute baseY hints. Returns (positions, heights, world_height, report).
    nodes must be in narrative order (ACT_SEQS order); node.col must be set.

    `parent` (an outline laid out as flow rather than a tree: child id → hub
    id) adds Pass C, which keeps every hub above its own children. Without it
    a hub in `center` is pushed down by the tall hubs before it while its
    leaves, out in `left`/`right`, collide with nothing and stay put — so the
    leaves ride up beside or above the hub and its spokes have to double back
    (ALTO-001). The engine's initLayout carries the same pass
    (engine_patches: outline-hub-above-children)."""
    colx = COL_SETS[columns]
    heights = {n.id: card_height(n.desc, n.title) for n in nodes}
    act_seqs = [[] for _ in range(act_count)]
    for n in nodes:
        act_seqs[n.act].append(n.id)
    node_by_id = {n.id: n for n in nodes}

    positions = _initial_positions(nodes, heights)

    # ── verbatim port of the engine resolver ──
    def run_resolver():
        outer_changed, outer_passes = True, 0
        while outer_changed and outer_passes < 100:
            outer_changed = False
            outer_passes += 1
            # Pass A: per-act collision resolution
            for ids in act_seqs:
                act_nodes = [node_by_id[i] for i in ids]
                changed, passes = True, 0
                while changed and passes < 500:
                    changed = False
                    passes += 1
                    act_nodes.sort(key=lambda x: positions[x.id])
                    for i in range(len(act_nodes)):
                        for j in range(i + 1, len(act_nodes)):
                            a, b = act_nodes[i], act_nodes[j]
                            dx = abs(colx[a.col] - colx[b.col])
                            hA, hB = heights[a.id], heights[b.id]
                            vgap = (positions[b.id] - hB / 2) - (positions[a.id] + hA / 2)
                            top_gap = positions[b.id] - (positions[a.id] + hA)
                            if dx < CARD_W + GAP and (vgap < GAP or top_gap < 16):
                                positions[b.id] = max(
                                    positions[a.id] + hA / 2 + GAP + hB / 2 + 2,
                                    positions[a.id] + hA + 16)
                                changed = True
                                nonlocal_changed[0] = True
            # Pass B: act boundary enforcement
            for ai in range(len(act_seqs) - 1):
                ids_a, ids_b = act_seqs[ai], act_seqs[ai + 1]
                if not ids_a or not ids_b:
                    continue
                bottom_a = max(positions[i] + heights[i] / 2 for i in ids_a)
                top_b = min(positions[i] - heights[i] / 2 for i in ids_b)
                needed = bottom_a + ACT_BOUNDARY_GAP
                if top_b < needed:
                    shift = needed - top_b
                    for bi in range(ai + 1, len(act_seqs)):
                        for i in act_seqs[bi]:
                            positions[i] += shift
                    nonlocal_changed[0] = True
            # Pass C (outline): a hub sits above every direct child. Pushes
            # only downward, like A and B, so the outer loop still converges.
            for cid, pid in (parent or {}).items():
                if cid not in positions or pid not in positions:
                    continue
                need = (positions[pid] - heights[pid] / 2 + HUB_DROP
                        + heights[cid] / 2)
                if positions[cid] < need - 0.5:
                    positions[cid] = need
                    nonlocal_changed[0] = True
            if nonlocal_changed[0]:
                outer_changed = True
                nonlocal_changed[0] = False

    nonlocal_changed = [False]
    run_resolver()

    # Act-1 LABEL_RESERVE shift
    if act_seqs and act_seqs[0]:
        top_b = min(positions[i] - heights[i] / 2 for i in act_seqs[0])
        deficit = LABEL_RESERVE - top_b
        if deficit > 0:
            for i in positions:
                positions[i] += deficit

    world_h = max(positions[i] + heights[i] / 2 for i in positions) + BOTTOM_PAD

    # Fixpoint audit: re-run the resolver; nothing should move.
    snapshot = dict(positions)
    nonlocal_changed[0] = False
    run_resolver()
    moved = [i for i in positions if abs(positions[i] - snapshot[i]) > 0.01]
    report = {
        "world_height": round(world_h),
        "moved_on_recheck": moved,
        "per_column": {
            k: sum(1 for n in nodes if n.col == k) for k in colx
        },
    }
    if moved:
        raise LayoutError(f"resolver not at fixpoint: {moved}")
    return positions, heights, round(world_h), report


def _siblings_in_order(ks: list, placement: dict) -> list:
    """A parent's children, in the order the material gives them except that a
    child with a placement `order` n sits n-th (1 = first). Applied in
    ascending n, so "Cause in Fact: 4" means exactly that."""
    want = [(placement[k.id]["order"], j, k) for j, k in enumerate(ks)
            if (placement.get(k.id) or {}).get("order")]
    if not want:
        return ks
    moved = {id(k) for _, _, k in want}
    out = [k for k in ks if id(k) not in moved]
    for pos, _, k in sorted(want, key=lambda t: t[:2]):
        out.insert(min(pos - 1, len(out)), k)
    return out


def outline_order_and_columns(nodes, columns: int, placement: dict = None) -> None:
    """Order and place an outline's concepts from its containment tree.

    Ordering is depth-first per band — a hub, then each child's whole subtree,
    children in the order the material gives them (or the placement `order`
    the author set) — which is simply outline reading order, so it also fixes
    the outline numerals, ACT_SEQS, the prev/next hop and the mobile grid for
    free.

    `col` follows one rule: **a concept that contains others sits in `center`;
    a leaf sits out to one side.** Mobile lays its grid out from it; desktop
    places an outline as a tree instead (outline_tree).

    Authored `col` is ignored in outline mode: the geometry is structural, not
    editorial, and letting a brief pin a hub off-centre would break the shape
    the whole mode is for.
    """
    inner = ["left", "right"]
    outer = ["far-left", "far-right"] if columns == 5 else inner

    kids: dict[str, list] = {}
    roots = []
    by_id = {n.id: n for n in nodes}
    for n in nodes:
        if n.parent and n.parent in by_id:
            kids.setdefault(n.parent, []).append(n)
        else:
            roots.append(n)
    if placement:
        for pid in kids:
            kids[pid] = _siblings_in_order(kids[pid], placement)

    ordered = []

    def walk(node):
        children = kids.get(node.id, [])
        node.col = "center" if children else None      # filled below for leaves
        ordered.append(node)
        i = 0
        for c in children:
            if kids.get(c.id):
                walk(c)
            else:
                c.col = (outer if i >= 2 and columns == 5 else inner)[i % 2]
                ordered.append(c)
                i += 1

    for root in sorted(roots, key=lambda n: n.act):
        walk(root)

    # Anything the walk never reached (a parent outside the node set — verify
    # rejects it at build, but validation may still be mid-upsert) keeps its
    # place rather than vanishing from the page.
    seen = {id(n) for n in ordered}
    ordered += [n for n in nodes if id(n) not in seen]
    for n in ordered:
        if not n.col:
            n.col = inner[0]
    nodes[:] = ordered


# ── outline tree ────────────────────────────────────────────────────────────
# A desktop outline reads as a tree growing down from each band's root:
#
#                       [Intentional Torts]
#              [Battery]                    [Trespass]
#   (L)-[Intent and Volition]-(NL)   (L)-[Trespass to Land]-(NL)
#   (L)-[Minimum Requirements]-(NL)      [Trespass to Chattels]
#   (L)-[Consent and Limits]-(NL)    (L)-[Conversion]-(NL)
#
# Every node is a LEAF (no children), a CONCEPT (children, all leaves) or a
# SECTION (at least one child with children of its own). Left to itself the
# tree sets a root's sections side by side as BRANCHES, two to a row; its other
# children form one more branch hanging straight off the root. A branch is one
# vertical spine: its section on top, then its children in order, a nested
# section starting a new run of the same spine. A concept's first two leaves
# flank it on its own row (left, right), narrower than a spine card so six
# lanes fit the 1700px world with a clear margin (MARGIN) at each edge; further
# leaves take rows of their own below it, in the same narrow flank lanes. Rows
# are centred, so every concept-to-flank line is a straight horizontal run.
#
# That is only the default. brief.placement overrides it one card at a time
# (see outline_plan): a card's children can be set side by side in a ROW or
# stacked in a COLUMN, and any card can be moved, nudged, taken out of the
# flow, or reordered among its siblings. The layout is a small program over
# (x, width) fixed by structure alone and the cards' heights, which are only
# known in the browser: outline_plan writes the program, run_plan and the page's
# _altoTree (detail_extras.TREE_GLUE) both run it over the heights they have.
# Mobile keeps its own single-column grid (mobile_grid, col).
TREE = {
    "CX": 850, "BRANCH_X": [470, 1230], "FLANK_DX": 265, "FLANK_W": 180,
    "TOP": LABEL_RESERVE, "ROOT_GAP": 70, "HEAD_GAP": 56, "ROW_GAP": 40,
    "GROUP_GAP": 90, "ACT_GAP": ACT_BOUNDARY_GAP,
    # a spine card, and the clear margin kept at each edge of the world
    "CARD_W": 270, "MARGIN": 115,
    # `arrange: row`: a band of at most MAX_ROW cards, PITCH_MAX apart at most,
    # BAND_GAP clear between neighbours in a row (closer than that they stagger
    # into two rows, STAGGER_GAP apart), progeny cards none narrower than MIN_W
    "MAX_ROW": 7, "PITCH_MAX": 420, "BAND_GAP": 30, "STAGGER_GAP": 28, "MIN_W": 180,
    # a parent's lines turn on one bus halfway down the gap to its nearest
    # child, unless that gap is longer than BUS_SPAN: then the bus runs
    # BUS_ABOVE over the children, so the long drop is in the parent's own column
    "BUS_SPAN": 160, "BUS_ABOVE": 50,
}


def outline_kids(nodes) -> dict:
    by_id = {n.id for n in nodes}
    kids: dict[str, list] = {}
    for n in nodes:
        if n.parent and n.parent in by_id:
            kids.setdefault(n.parent, []).append(n.id)
    return kids


def _roots(nodes) -> set:
    by_id = {n.id for n in nodes}
    return {n.id for n in nodes if not (n.parent and n.parent in by_id)}


def outline_flanks(nodes) -> set:
    """Ids of the leaves that flank their concept (the narrow cards) when the
    tree is left to itself. A band's root is never flanked: its own leaves hang
    down its spine."""
    kids = outline_kids(nodes)
    roots = _roots(nodes)
    flanks = set()
    for pid, ks in kids.items():
        if pid not in roots and ks and all(not kids.get(k) for k in ks):
            flanks.update(ks)
    return flanks


def _fit_pair(k: int, bx: float):
    """(card width, centres, flanks fit) for one or two columns side by side,
    centred on bx and kept clear of the page edges: the tree's own branch
    spacing, with the room a flanked concept needs."""
    T = TREE
    w, reach = T["CARD_W"], T["FLANK_DX"] + T["FLANK_W"] / 2
    pitch = T["BRANCH_X"][1] - T["BRANCH_X"][0]
    xs = [bx] if k == 1 else [bx - pitch / 2, bx + pitch / 2]
    lo, hi = T["MARGIN"] + reach, WORLD_W - T["MARGIN"] - reach
    shift = max(0, lo - min(xs)) - max(0, max(xs) - hi)
    return w, [round(v + shift, 2) for v in xs], True


def _band(k: int, bx: float):
    """(xs, card width, progeny width, staggered) for a band of k >= 3 cards
    centred on bx. The cards keep their full width: when that leaves them closer
    than BAND_GAP they stagger into two rows instead (neighbours alternate), so
    a column can run straight down between the cards of the other row. The
    progeny hanging from the band are as wide as the pitch allows."""
    T = TREE
    usable = WORLD_W - 2 * T["MARGIN"]
    w = T["CARD_W"]
    pitch = min(T["PITCH_MAX"], (usable - w) / (k - 1))
    xs = [bx + (j - (k - 1) / 2) * pitch for j in range(k)]
    lo, hi = T["MARGIN"] + w / 2, WORLD_W - T["MARGIN"] - w / 2
    shift = max(0, lo - min(xs)) - max(0, max(xs) - hi)
    stagger = pitch < w + T["BAND_GAP"]
    # In one row a column is as wide as the pitch leaves. Staggered, a column
    # runs beside the cards of the other row, so it is sized to clear them by
    # half the gap each side; it then never has to wait for a tall neighbour.
    cw = int(max(T["MIN_W"], min(w, (2 * (pitch - w / 2 - T["BAND_GAP"] / 2)) if stagger
                                 else pitch - T["BAND_GAP"])))
    return [round(v + shift, 2) for v in xs], w, cw, stagger


def outline_plan(nodes, act_count: int, placement: dict = None,
                 lines: str = "fan") -> dict:
    """The tree's layout as a program, from the nodes' structure and the
    brief's placement hints alone (no card heights needed).

    Returns {x, w, acts, etx, top, act_gap, row_gap, warnings}: every card's
    centre x and width; for each act, the ops that stack its roots top to
    bottom; and the fanned lines' end points. The ops run over card heights
    (run_plan here, TREE_GLUE in the page) and are arrays:

      ["card", id, gap, dy?]      one card, then `gap`; `dy` more space above
      ["row", [ids], gap, dy?]    cards on one row, as tall as the tallest
      ["seq", [ops]]              one after another
      ["par", [ops], gap]         side by side from the same top; ends at the
                                  lowest, then `gap`
      ["band", [[id, lo, hi, row, dy]], [[lo, hi, op]], rowgap, gap, auto?]
                                  a band of cards, then the blocks that hang
                                  from them. Cards go in rows (`row`, 0 first);
                                  a card starts at the top, or `rowgap` under
                                  the lowest earlier card it overlaps in width
                                  (lo..hi). With `auto` the cards alternate rows
                                  and the page keeps whichever of the two
                                  alternations makes the shorter band (or, if
                                  equal, keeps the other cards higher). Each
                                  block (its width lo..hi) starts at the top, or
                                  `gap` under the lowest card or block already
                                  placed that shares any of its width
      ["float", op, top?]         op placed where the flow is (or at `top` on
                                  the page), which does not move on: it takes
                                  no room

    Hints (brief.placement, {id: {...}}) all optional:
      arrange  how this card's children sit under it. "auto": a band's root
               sets its sections side by side as branches and the rest of its
               children in one spine; any other card stacks its children down
               its own spine. "column": all children down the spine, sections
               and all. "row": the children are a BAND directly under the card,
               placed first, with whatever hangs from them packed in beneath.
               Up to five fit one row at full width; six or seven stagger into
               two rows (neighbours alternate, and the page keeps the alternation
               that makes the shorter band); more wrap into further bands. Each
               child's progeny hang straight below it in a column the stagger
               leaves room for, and a block too wide for its column (a child that
               is itself a row) settles below its neighbours rather than across
               them. A concept's outcomes stack under it instead of flanking it.
               "branches": the root rule, wherever it is wanted.
      tier     which row of the band this child sits in (1 = upper, the
               default). Left alone the band staggers by itself; set tiers to
               choose. Neighbours sharing a row that overlap sideways are warned
               about and stacked. The notes' order is untouched.
      x, dx    the card's centre, absolute or as a nudge. Everything under it
               hangs from wherever it ends up.
      y        the card's top, on the page. Pins it there whatever else moves;
               its progeny flow from it. With x, any card can go anywhere.
      dy       more (or less) room above the card; what follows moves with it.
      w        the card's width.
      float    leave the card and its progeny at the flow's current top,
               pushing nothing down: for setting a subtree beside another.
    A concept's outcome that has its own y, dy or float leaves the concept's
    row and is placed on its own. (order is applied earlier, to the nodes:
    outline_order_and_columns.)
    """
    T = TREE
    H = placement or {}
    kids = outline_kids(nodes)
    roots = _roots(nodes)
    leaf = lambda i: not kids.get(i)
    concept = lambda i: bool(kids.get(i)) and all(leaf(k) for k in kids[i])
    hint = lambda i, k, d=None: (H.get(i) or {}).get(k, d)
    x, w, spine, floated, warns = {}, {}, {}, set(), []

    def at(i, bx, ww, reach=None):
        """Card i's centre: the slot's, else the hint's, plus dx; held inside
        the margins (reach = how far its row extends each side)."""
        ww = hint(i, "w", ww)
        reach = ww / 2 if reach is None else reach
        cx = hint(i, "x", bx) + hint(i, "dx", 0)
        lo, hi = T["MARGIN"] + reach, WORLD_W - T["MARGIN"] - reach
        if not lo <= cx <= hi:
            if i in H:
                warns.append(f"placement: {i} moved to x={min(max(cx, lo), hi):.0f}"
                             " to keep clear of the page edge")
            cx = min(max(cx, lo), hi)
        x[i], w[i] = cx, ww
        return cx

    def card(i, gap):
        dy = hint(i, "dy", 0)
        return ["card", i, gap] + ([dy] if dy else [])

    def settled(i, frag):
        """Card i's ops: in the flow, unless its hints float or pin them."""
        top = hint(i, "y")
        if hint(i, "float") or top is not None:
            floated.add(i)
            return [["float", ["seq", frag]] + ([top] if top is not None else [])]
        return frag

    def stack(ids, bx, ww, wide):
        ops = []
        for i in ids:
            ops += item(i, bx, ww, wide)
        return ops

    def detached(l):
        """An outcome that is placed on its own rather than in its concept's row."""
        return bool(hint(l, "float")) or hint(l, "y") is not None or bool(hint(l, "dy"))

    def item(i, bx, ww, wide):
        """Card i on the axis bx and everything under it, as ops."""
        if leaf(i):
            at(i, bx, ww)
            return settled(i, [card(i, T["ROW_GAP"])])
        if concept(i) and wide and hint(i, "arrange", "auto") == "auto":
            ls = kids[i]
            rows = [[l for l in ls[k:k + 2] if not detached(l)]
                    for k in range(0, len(ls), 2)]
            reach = (T["FLANK_DX"] + T["FLANK_W"] / 2) if any(rows[0]) else None
            cx = at(i, bx, ww, reach)
            alone = []
            for j, l in enumerate(ls):
                at(l, cx + (-1 if j % 2 == 0 else 1) * T["FLANK_DX"],
                   T["FLANK_W"], T["FLANK_W"] / 2)
                if detached(l):
                    alone += settled(l, [card(l, 0)])
            first = ["row", [i] + rows[0], T["ROW_GAP"]] + (
                [hint(i, "dy")] if hint(i, "dy") else [])
            rest = [["row", r, T["ROW_GAP"]] for r in rows[1:] if r]
            return settled(i, alone + [first] + rest)
        cx = at(i, bx, ww)
        return settled(i, [card(i, T["HEAD_GAP"])]
                       + children(i, cx, ww, wide))

    def children(p, bx, ww, wide):
        """The ops for p's children, below p's own card."""
        ks = kids.get(p, [])
        mode = hint(p, "arrange", "auto")
        if mode == "auto":
            mode = "branches" if p in roots else "column"
        if mode == "column":
            spine[p] = ks
            return stack(ks, bx, ww, wide)
        if mode == "branches":
            br = [[k] for k in ks if not leaf(k) and not concept(k)]
            direct = [k for k in ks if leaf(k) or concept(k)]
            if direct:
                br.append(direct)
                spine[p] = direct
            br.sort(key=lambda b: ks.index(b[0]))
            ops = []
            for g in range(0, len(br), 2):
                grp = br[g:g + 2]
                xs = T["BRANCH_X"] if len(grp) == 2 else [T["CX"]]
                ops.append(columns([["seq", stack(b, cx, T["CARD_W"], True)]
                                    for b, cx in zip(grp, xs)], T["GROUP_GAP"]))
            return ops
        # row: the children are a BAND directly under p, ahead of anything
        # that hangs from them (see band); more than MAX_ROW make several
        n = len(ks)
        bands = -(-n // T["MAX_ROW"]) if n else 0
        ops, start = [], 0
        for r in range(bands):
            size = n // bands + (1 if r < n % bands else 0)
            chunk, start = ks[start:start + size], start + size
            ops += band(chunk, bx) if size > 2 else pair(chunk, bx)
        return ops

    def pair(chunk, bx):
        """One or two children side by side, each a column of its own: wide
        enough for a concept's outcomes to flank it."""
        cw, xs, flanks = _fit_pair(len(chunk), bx)
        return [columns([["seq", item(c, cx, cw, flanks)] for c, cx in zip(chunk, xs)],
                        T["GROUP_GAP"])]

    def columns(cols, gap):
        """Columns side by side from one top: a plain `par`, unless two of them
        share some width (a wide block of progeny inside one), when they pack
        instead and the wider settles below rather than across the other."""
        ext = []
        for o in cols:
            ids = ids_of(o)
            if ids:
                ext.append((round(min(x[i] - w[i] / 2 for i in ids), 2),
                            round(max(x[i] + w[i] / 2 for i in ids), 2), o))
        spans = sorted(ext)
        if all(b[0] >= a[1] - 0.5 for a, b in zip(spans, spans[1:])):
            return ["par", cols, gap]
        ext.sort(key=lambda t: t[1] - t[0])
        return ["band", [], [[lo, hi, o] for lo, hi, o in ext], T["STAGGER_GAP"], gap]

    def ids_of(op):
        if op[0] == "card":
            return [op[1]]
        if op[0] == "row":
            return list(op[1])
        if op[0] in ("seq", "par"):
            return [i for o in op[1] for i in ids_of(o)]
        if op[0] == "band":
            return [c[0] for c in op[1]] + [i for _, _, o in op[2] for i in ids_of(o)]
        return []                                   # float: takes no room

    def band(chunk, bx):
        """Three or more children as a band: the cards first, in one row if they
        fit and in two staggered rows if not (a `tier` hint picks a card's row),
        then everything that hangs from them packs in beneath, each block straight
        under its parent. Narrowest blocks are placed first, so a wide one (a
        child that is itself a band) settles below its neighbours' instead of
        across them."""
        xs, bw, cw, stagger = _band(len(chunk), bx)
        given = [hint(c, "tier") for c in chunk]
        if any(given):
            tiers = sorted({hint(c, "tier", 1) for c in chunk})
            row_of = {c: tiers.index(hint(c, "tier", 1)) for c in chunk}
        else:
            row_of = {c: (j % 2 if stagger else 0) for j, c in enumerate(chunk)}
        pre, cards, blocks = [], [], []
        for c, slot in zip(chunk, xs):
            cx = at(c, slot, bw)
            below = children(c, cx, cw, False)
            if hint(c, "float") or hint(c, "y") is not None:
                pre += settled(c, [card(c, T["ROW_GAP"])] + below)
                continue
            half = w[c] / 2
            cards.append([c, round(cx - half, 2), round(cx + half, 2), row_of[c],
                          hint(c, "dy", 0)])
            ids = [i for o in below for i in ids_of(o)]
            if ids:
                blocks.append((round(min(x[i] - w[i] / 2 for i in ids), 2),
                               round(max(x[i] + w[i] / 2 for i in ids), 2), below))
        blocks.sort(key=lambda t: t[1] - t[0])
        for r in {cd[3] for cd in cards}:
            line = sorted((cd for cd in cards if cd[3] == r), key=lambda cd: cd[1])
            for a_, b_ in zip(line, line[1:]):
                if b_[1] < a_[2] - 1:
                    warns.append(f"placement: {a_[0]} and {b_[0]} share tier {r + 1} "
                                 "but overlap sideways, so one is set below the other"
                                 " — give neighbours different tiers")
        auto = stagger and not any(given)
        return pre + ([["band", cards, [[lo, hi, ["seq", b]] for lo, hi, b in blocks],
                        T["STAGGER_GAP"], T["GROUP_GAP"]] + ([True] if auto else [])]
                      if cards else [])

    acts = []
    for a in range(act_count):
        ops = []
        for r in (n.id for n in nodes if n.act == a and n.id in roots):
            cx = at(r, T["CX"], T["CARD_W"])
            ops += settled(r, [card(r, T["ROOT_GAP"])]
                           + children(r, cx, T["CARD_W"], True))
        acts.append(ops)

    # Fan: the k children down a spine meet the top of its first card at k
    # equally spaced points (the first at the centre, the rest alternating left,
    # right, further left…) and each line drops from its point to its own child.
    # Offsets stay inside the card (the spacing scales with its width; at the
    # spine card's 270 it is 40-80 px, so the router has room for its 20px
    # corners). A child off the spine's axis, or floated, gets an ordinary line.
    etx = {}
    if lines == "fan":
        for p, ks in spine.items():
            ks = [k for k in ks if k not in floated]
            ks = [k for k in ks if abs(x[k] - x[ks[0]]) < 1]
            if len(ks) < 2:
                continue
            half = -(-(len(ks) - 1) // 2)
            s = (w[ks[0]] / 2 - 20) / 115 * max(40, min(80, 115 / half))
            for j, k in enumerate(ks[1:], 1):
                etx[f"{p}|{k}"] = round(x[ks[0]] + -(-j // 2) * s * (-1 if j % 2 else 1), 2)
    return {"x": x, "w": w, "acts": acts, "etx": etx, "top": T["TOP"],
            "act_gap": T["ACT_GAP"], "row_gap": T["ROW_GAP"], "cx": T["CX"],
            "bus_span": T["BUS_SPAN"], "bus_above": T["BUS_ABOVE"], "warnings": warns}


def plan_js(plan: dict) -> dict:
    """The part of a plan the page needs (it measures heights itself)."""
    return {k: plan[k] for k in ("x", "acts", "etx", "top", "act_gap", "row_gap", "cx",
                                 "bus_span", "bus_above")}


def run_plan(plan: dict, nodes, heights: dict):
    """Run a plan over card heights. Returns (centres, xs, world_height);
    centres are card-centre y like resolve()'s positions. The page's _altoTree
    (detail_extras.TREE_GLUE) does exactly this."""
    h, y, x = heights, {}, dict(plan["x"])
    bottom = [0.0]
    row_gap = plan["row_gap"]

    def put(i, top, row_h=None):
        y[i] = top + (row_h if row_h is not None else h[i]) / 2
        bottom[0] = max(bottom[0], y[i] + h[i] / 2)

    def run(op, c):
        kind = op[0]
        if kind == "card":
            c += op[3] if len(op) > 3 else 0
            put(op[1], c)
            return c + h[op[1]] + op[2]
        if kind == "row":
            c += op[3] if len(op) > 3 else 0
            rh = max(h[i] for i in op[1])
            for i in op[1]:
                put(i, c, rh)
            return c + rh + op[2]
        if kind == "seq":
            for o in op[1]:
                c = run(o, c)
            return c
        if kind == "par":
            ends = [run(o, c) - row_gap for o in op[1]]
            return max(ends) + op[2] if ends else c
        if kind == "band":
            cards, blocks, rg, gap = op[1], op[2], op[3], op[4]

            def lay(flip):
                tops, sky = {}, []                       # sky: (lo, hi, bottom)
                for k in sorted(range(len(cards)), key=lambda k: (cards[k][3] ^ flip, k)):
                    i, lo, hi, _, dy = cards[k]
                    tops[i] = max([c] + [b + rg for l, h, b in sky if l < hi and lo < h]) + dy
                    sky.append((lo, hi, tops[i] + h[i]))
                return tops, sky
            tops, sky = lay(0)
            if len(op) > 5:
                alt = lay(1)
                # the shorter band; when equally short, the one that keeps the
                # other cards higher (a tall card on the lower row holds nothing up)
                score = lambda t, s_: (max(b for _, _, b in s_), sum(t.values()))
                a0, a1 = score(tops, sky), score(*alt)
                if a1[0] < a0[0] - 1e-9 or (abs(a1[0] - a0[0]) <= 1e-9 and a1[1] < a0[1] - 1e-9):
                    tops, sky = alt
            for i, t in tops.items():
                put(i, t)
            for lo, hi, o in blocks:
                top = max([c] + [b + gap for l, h, b in sky if l < hi and lo < h])
                sky.append((lo, hi, run(o, top) - row_gap))
            return max(b for _, _, b in sky) + gap
        run(op[1], op[2] if len(op) > 2 else c)          # float / pinned
        return c

    cur = plan["top"]
    for a, ops in enumerate(plan["acts"]):
        if a and ops:
            cur = bottom[0] + plan["act_gap"]
        for op in ops:
            cur = run(op, cur)
    # anything outside the tree (verify rejects it; still never drop a card)
    for n in nodes:
        if n.id not in y:
            x[n.id] = TREE["CX"]
            put(n.id, bottom[0] + row_gap)
    return y, x, round(bottom[0] + BOTTOM_PAD)


def outline_tree(nodes, act_count: int, heights: dict, placement: dict = None,
                 plan: dict = None):
    """Tree placement for an outline (see TREE). Returns (centres, xs,
    world_height); centres are card-centre y like resolve()'s positions."""
    plan = plan or outline_plan(nodes, act_count, placement)
    return run_plan(plan, nodes, heights)


def placement_check(nodes, plan: dict, y: dict, x: dict, heights: dict) -> dict:
    """What a layout got wrong, for the author to correct with hints: cards
    that overlap, and cards closer to the page edge than the margin."""
    T = TREE
    boxes = [(n.id, x[n.id] - plan["w"].get(n.id, T["CARD_W"]) / 2,
              y[n.id] - heights[n.id] / 2,
              x[n.id] + plan["w"].get(n.id, T["CARD_W"]) / 2,
              y[n.id] + heights[n.id] / 2) for n in nodes if n.id in y]
    boxes.sort(key=lambda b: b[2])
    overlaps = []
    for i, (a, ax0, ay0, ax1, ay1) in enumerate(boxes):
        for b, bx0, by0, bx1, by1 in boxes[i + 1:]:
            if by0 >= ay1 - 2:
                break
            if min(ax1, bx1) - max(ax0, bx0) > 2:
                overlaps.append([a, b])
    off = [b[0] for b in boxes
           if b[1] < T["MARGIN"] - 1 or b[3] > WORLD_W - T["MARGIN"] + 1]
    return {"overlaps": overlaps[:20], "overlap_count": len(overlaps),
            "off_margin": off[:20]}


def outline_has_categories(nodes) -> bool:
    """Whether an outline's structure gives a tree something to show: a
    concept with outcomes of its own to flank it, or a root that splits into
    at least two sections. A flat list under one root is just a column."""
    kids = outline_kids(nodes)
    roots = _roots(nodes)
    leaf = lambda i: not kids.get(i)
    concept = lambda i: bool(kids.get(i)) and all(leaf(k) for k in kids[i])
    if any(concept(i) for i in kids if i not in roots):
        return True
    return any(sum(1 for k in kids.get(r, []) if not leaf(k) and not concept(k)) >= 2
               for r in roots)


def line_crossings(edges, xs: dict, ys: dict, heights: dict, tree: bool) -> int:
    """How many times the drawn lines cross each other, on the router's basic
    shapes: a vertical when both ends share a column, a straight run when they
    share a row, else down–across–down. A flowing layout turns halfway between
    the ends; a tree turns on one shared elbow under each parent (the
    engine's _altoTreeMid). Lines that meet at a card they share are not a
    crossing, and neither are lines running along one another."""
    mid = {}
    if tree:
        for s, t in edges:
            if ys[t] - heights[t] / 2 > ys[s] + heights[s] / 2:
                mid[s] = min(mid.get(s, float("inf")), ys[t] - heights[t] / 2)
    segs = []
    for k, (s, t) in enumerate(edges):
        sx, sy, tx, ty = xs[s], ys[s], xs[t], ys[t]
        if abs(sx - tx) < 10:
            pts = [(sx, sy), (sx, ty)]
        elif abs(sy - ty) < 1:
            pts = [(sx, sy), (tx, ty)]
        else:
            if tree and s in mid:
                pb = sy + heights[s] / 2
                m = (mid[s] - TREE["BUS_ABOVE"] if mid[s] - pb > TREE["BUS_SPAN"]
                     else pb + (mid[s] - pb) / 2)
            else:
                m = (sy + ty) / 2
            pts = [(sx, sy), (sx, m), (tx, m), (tx, ty)]
        for a, b in zip(pts, pts[1:]):
            segs.append((k, s, t, a, b))
    n = 0
    for i, (k1, s1, t1, a1, b1) in enumerate(segs):
        for k2, s2, t2, a2, b2 in segs[i + 1:]:
            if k1 == k2 or {s1, t1} & {s2, t2}:
                continue
            v, h = ((a1, b1), (a2, b2)) if a1[0] == b1[0] else ((a2, b2), (a1, b1))
            if v[0][0] != v[1][0] or h[0][1] != h[1][1]:
                continue           # both vertical or both horizontal: not a crossing
            x, y = v[0][0], h[0][1]
            if (min(h[0][0], h[1][0]) + 0.5 < x < max(h[0][0], h[1][0]) - 0.5
                    and min(v[0][1], v[1][1]) + 0.5 < y < max(v[0][1], v[1][1]) - 0.5):
                n += 1
    return n


def outline_spokes(nodes, connections: list) -> list:
    """parent → child edges, as `spine` connections.

    Generated at build rather than authored, so the tree stays the single
    source of truth: an authored copy could disagree with `parent` and nothing
    would catch it. An edge the brief already declares wins, keeping its own
    relation and label.
    """
    authored = {(c[0], c[1]) for c in (connections or []) if len(c) >= 2}
    by_id = {n.id for n in nodes}
    spokes = [[n.parent, n.id, "spine"] for n in nodes
              if n.parent and n.parent in by_id
              and (n.parent, n.id) not in authored]
    return spokes + list(connections or [])


def mobile_grid(nodes, columns: int):
    """[colIndex, row] per node in narrative order: ordinal column mapping,
    monotone row counter (+1 normally, +2 when the same mobile column repeats,
    +3 at act boundaries) — mimics the reference build's spacing."""
    order5 = ["far-left", "left", "center", "right", "far-right"]
    if columns == 5:
        cmap = {k: i for i, k in enumerate(order5)}
    else:
        cmap = {"left": 1, "center": 2, "right": 3}
    grid = {}
    row = 0
    prev_col = None
    prev_act = None
    for n in nodes:
        ci = cmap[n.col]
        if prev_act is None:
            row = 0
        elif n.act != prev_act:
            row += 3
        elif ci == prev_col:
            row += 2
        else:
            row += 1
        grid[n.id] = [ci, row]
        prev_col, prev_act = ci, n.act
    world_h = MOBILE_OY + MOBILE_STEP * (row if grid else 0) + 600
    return grid, world_h
