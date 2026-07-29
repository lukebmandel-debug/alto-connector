"""Build-time verifier — generalized from Terrarium's verify_terrarium.py.

Runs on every build. Data-level cross-refs are checked before emit; the
emitted HTML is then gated for leftover template slots and secrets. Any
failure aborts the build with a structured report (nothing is published).
"""
from __future__ import annotations

import re

from .brief import Brief, Node, COL_SETS
from .layout import check_columns


class VerifyError(ValueError):
    def __init__(self, failures):
        self.failures = failures
        super().__init__("; ".join(failures))


def verify_data(b: Brief, nodes: list[Node], connections: list) -> list[str]:
    failures = []
    node_ids = {n.id for n in nodes}
    rel_keys = {r.key for r in b.relations} | {"spine"}

    for c in connections:
        if len(c) != 3:
            failures.append(f"connection {c!r}: must be [src, tgt, relation]")
            continue
        src, tgt, rel = c
        if src not in node_ids:
            failures.append(f"connection {c!r}: unknown source node")
        if tgt not in node_ids:
            failures.append(f"connection {c!r}: unknown target node")
        if rel not in rel_keys:
            failures.append(f"connection {c!r}: relation {rel!r} not in vocabulary")
        if src == tgt:
            failures.append(f"connection {c!r}: self-loop")

    # every node in exactly one act sequence (construction guarantees it, but
    # assert anyway — this is the ACT_SEQS/NODE_ACT coverage gate)
    per_act = [0] * len(b.acts)
    for n in nodes:
        if 0 <= n.act < len(b.acts):
            per_act[n.act] += 1
        else:
            failures.append(f"node {n.id}: act {n.act} out of range")
    for i, count in enumerate(per_act):
        if count == 0:
            failures.append(f"act {i+1} ({b.acts[i].label!r}) has no nodes")

    for n in nodes:
        if n.col not in COL_SETS[b.columns]:
            failures.append(f"node {n.id}: column {n.col!r} invalid")

    try:
        check_columns(b.columns)
    except Exception as e:  # LayoutError
        failures.append(str(e))

    # overview deep links must target live nodes
    for m in re.finditer(r"showDetail\('node','([^']+)'\)", b.overview_html or ""):
        if m.group(1) not in node_ids:
            failures.append(f"overview links to unknown node {m.group(1)!r}")
    return failures


def verify_output(html: str) -> list[str]:
    failures = []
    leftover = re.search(r"ALTO:(BEGIN|END) [\w-]+|__ALTO_TOK_\w+__", html)
    if leftover:
        failures.append(f"unconsumed template slot: {leftover.group(0)!r}")
    if "sk-ant" in html:
        failures.append("output contains an API-key-like token (sk-ant)")
    for tok in ("function initLayout(", "function laneRoute(", "var LANE_CLEAR = 24;"):
        if tok not in html:
            failures.append(f"engine token missing from output: {tok!r}")
    return failures
