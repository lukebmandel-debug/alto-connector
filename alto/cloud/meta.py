"""The homepage's listing record for a private page — the Python side.

A port of `_metaOf` in alto-cloud.js, which stays the source of truth: the
browser writes this record when a page is uploaded by hand, and the connector
writes the same record when it publishes the page itself. Two writers that
disagreed would sort one timeline into two different homepage boxes, so
tests/test_cloud_store.py runs both over the same real pages.
"""
from __future__ import annotations

import html as _html
import re

META_V = 1
SEARCH_CAP, DESC_CAP = 600, 280

_LABEL = re.compile(r'<meta name="alto-label" content="([^"]*)"', re.I)
_TITLE = re.compile(r"<title>([^<]*)</title>", re.I)
_TITLE_TAIL = re.compile(r"\s*—\s*Alto(\s+Timeline)?\s*$")
_COLOR = re.compile(r"colorRaw:'(#[0-9a-fA-F]{3,8})'")
_NODE = re.compile(
    r"\{id:'((?:[^'\\]|\\.)*)'[\s\S]*?title:'((?:[^'\\]|\\.)*)'\s*,\s*"
    r"desc:'((?:[^'\\]|\\.)*)'")
_COURSE = re.compile(r"var COURSE_ID = '([^']*)';")


def _unq(s: str) -> str:
    # JS: .replace(/\\'/g, "'").replace(/\\\\/g, '\\')
    return (s or "").replace("\\'", "'").replace("\\\\", "\\")


def _unent(s: str) -> str:
    # JS order: &quot; &#x27; &lt; &gt; then &amp; last.
    return (s or "").replace("&quot;", '"').replace("&#x27;", "'") \
        .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _block(h: str, start: str, cap: int) -> str:
    i = h.find(start)
    if i < 0:
        return ""
    j = h.find("\n];", i)
    return h[i:(i + cap if j < 0 else j)]


def meta_of(h: str) -> dict:
    h = h or ""
    lm = _LABEL.search(h)
    project = _unent(lm.group(1)).strip() if lm else ""
    tm = _TITLE.search(h)
    heading = _TITLE_TAIL.sub("", _unent(tm.group(1))).strip() if tm else ""
    units = _COLOR.findall(_block(h, "const PHASE_META = [", 20000))
    search = []
    for m in _NODE.finditer(_block(h, "const NODES_SRC=[", 400000)):
        if len(search) >= SEARCH_CAP:
            break
        search.append({"id": _unq(m.group(1)), "t": _unq(m.group(2)),
                       "d": _unq(m.group(3))[:DESC_CAP]})
    cm = _COURSE.search(h)
    return {"title": project or heading, "heading": heading, "project": project,
            "tid": cm.group(1) if cm else "", "units": units, "search": search,
            "v": META_V}


def title_of(h: str) -> str:
    """The private shell's titleOf: the alto-label, else the <title>."""
    lm = _LABEL.search(h or "")
    if lm and lm.group(1):
        return _html.unescape(lm.group(1)).strip()
    tm = _TITLE.search(h or "")
    return re.sub(r"\s*—\s*Alto(\s+Timeline)?\s*$", "", tm.group(1)).strip() if tm else ""
