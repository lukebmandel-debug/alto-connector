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


def resolve(nodes, columns: int, act_count: int):
    """Compute baseY hints. Returns (positions, heights, world_height, report).
    nodes must be in narrative order (ACT_SEQS order); node.col must be set."""
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
