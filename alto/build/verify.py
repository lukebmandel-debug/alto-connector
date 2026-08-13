"""Build-time verifier — generalized from Terrarium's verify_terrarium.py.

Runs on every build. Data-level cross-refs are checked before emit; the
emitted HTML is then gated for leftover template slots and secrets. Any
failure aborts the build with a structured report (nothing is published).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from html import unescape as _unescape
from pathlib import Path

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


def verify_output(html: str, deeplink_ids=None) -> list[str]:
    failures = []
    leftover = re.search(r"ALTO:(BEGIN|END) [\w-]+|__ALTO_TOK_\w+__", html)
    if leftover:
        failures.append(f"unconsumed template slot: {leftover.group(0)!r}")
    if "sk-ant" in html:
        failures.append("output contains an API-key-like token (sk-ant)")
    for tok in ("function initLayout(", "function laneRoute(", "var LANE_CLEAR = 24;"):
        if tok not in html:
            failures.append(f"engine token missing from output: {tok!r}")

    # Overview deep links: each surviving link must be the engine's chip markup
    # in the emitted page (the old post-sanitize check passed vacuously because
    # sanitize had already stripped every onclick). This is what makes the
    # deep-link contract real end to end.
    for nid in deeplink_ids or []:
        chip = ('<span class="ov-node-link"><button class="ov-node-btn" '
                f"onclick=\"showDetail('node','{nid}')\"></button>")
        if chip not in html:
            failures.append(f"overview deep link to {nid!r} did not survive to output")
    if deeplink_ids and "function initOverviewNavLinks(){" not in html:
        failures.append("engine token missing from output: initOverviewNavLinks")
    return failures


# ── JS parse gate ────────────────────────────────────────────────────────────
# A SyntaxError in an emitted <script> block kills the whole engine script at
# parse time and would otherwise ship as "0 warnings" (this was the blank-canvas
# bug: one unquoted hyphenated object key took the entire engine down). So every
# inline script — and every onclick handler, which is where a bad overview
# deep-link rewrite would land — is syntax-checked with `node --check` before a
# build is allowed to succeed. No node on the machine degrades to a single
# warning; it never crashes the build.
_SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.S | re.I)
_ONCLICK_RE = re.compile(r'onclick="([^"]*)"', re.I)
_TYPE_RE = re.compile(r'\btype\s*=\s*["\']([^"\']*)["\']', re.I)
_SRC_RE = re.compile(r"\bsrc\s*=", re.I)
_ID_RE = re.compile(r'\bid\s*=\s*["\']([^"\']*)["\']', re.I)
_JS_TYPES = {"", "text/javascript", "application/javascript", "module"}

# body-hash + module-flag → error string (or None). Shared across the three
# documents a build checks (timeline / hosted / offline), which overlap almost
# entirely, so identical blocks are spawned through node only once.
_script_cache: dict[tuple[str, bool], "str | None"] = {}


def find_node() -> "str | None":
    """The node binary used for syntax-checking, or None if none is installed.
    Env override first, then PATH, then the user-space install (node is not on
    PATH on the author's machine, so the last fallback is load-bearing here)."""
    override = os.environ.get("ALTO_NODE_BIN")
    if override and Path(override).exists():
        return override
    found = shutil.which("node")
    if found:
        return found
    fallback = Path.home() / ".local" / "node" / "bin" / "node"
    return str(fallback) if fallback.exists() else None


def _check_one(node: str, body: str, is_module: bool) -> "str | None":
    """`node --check` one script body via stdin. None on success, else a short
    error string. A missing/slow/erroring node degrades to None (the caller has
    already surfaced the no-node warning) rather than failing the build."""
    key = (hashlib.sha256(body.encode("utf-8")).hexdigest(), is_module)
    if key in _script_cache:
        return _script_cache[key]
    cmd = [node, "--check"] + (["--input-type=module"] if is_module else []) + ["-"]
    try:
        r = subprocess.run(cmd, input=body.encode("utf-8"),
                           capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        _script_cache[key] = None
        return None
    if r.returncode == 0:
        _script_cache[key] = None
        return None
    # node prints: "[stdin]:N", the offending source line, a caret, a blank
    # line, then "SyntaxError: …". Keep the location and the actual error message
    # (the source echo and caret in between are noise for a report).
    lines = [l.strip() for l in
             r.stderr.decode("utf-8", "replace").splitlines() if l.strip()]
    loc = lines[0] if lines else ""
    err = next((l for l in lines if "Error" in l), lines[-1] if lines else "")
    msg = (f"{loc} {err}".strip() or "syntax check failed")
    _script_cache[key] = msg
    return msg


def verify_scripts(html: str, label: str = "page") -> "tuple[list[str], list[str]]":
    """Syntax-check every inline <script> and every onclick handler in `html`.

    Returns (failures, warnings). A non-empty `failures` must fail the build.
    With no node available, `failures` is empty and `warnings` carries one line
    recording that scripts were not checked (a degraded gate, never a crash).
    """
    node = find_node()
    if not node:
        return [], [f"js-gate: node not found (tried $ALTO_NODE_BIN, PATH, "
                    f"~/.local/node/bin/node) — inline scripts in {label} not "
                    f"syntax-checked"]

    failures: list[str] = []
    for i, m in enumerate(_SCRIPT_RE.finditer(html)):
        attrs, body = m.group(1), m.group(2)
        if _SRC_RE.search(attrs):
            continue                      # external script — nothing inline to parse
        tm = _TYPE_RE.search(attrs)
        typ = tm.group(1).strip().lower() if tm else ""
        if typ not in _JS_TYPES:
            continue                      # JSON / importmap / template — not JS
        err = _check_one(node, body, typ == "module")
        if err:
            idm = _ID_RE.search(attrs)
            where = f"#{idm.group(1)}" if idm else f"block {i + 1}"
            failures.append(f"{label} <script {where}>: {err}")

    # onclick handlers are function bodies in the browser, so wrapping each in a
    # function and checking them together is semantically faithful — and is what
    # catches a malformed showDetail() emitted by the overview deep-link rewrite.
    # Scan only markup OUTSIDE <script> blocks: an onclick="..." substring inside
    # a JS string literal (e.g. the engine assembling a button at runtime, where
    # `\'` is correct string escaping) is not a DOM attribute, and the script
    # body carrying it was already parsed whole above.
    outside = _SCRIPT_RE.sub("", html)
    handlers = [_unescape(v) for v in _ONCLICK_RE.findall(outside)]
    if handlers:
        wrapped = "\n".join(f"function __h{j}(){{ {h}\n}}"
                            for j, h in enumerate(handlers))
        err = _check_one(node, wrapped, False)
        if err:
            failures.append(f"{label} onclick handler: {err}")
    return failures, []
