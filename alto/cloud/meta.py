"""The homepage's listing record for a private page — the Python side.

A port of `_metaOf` in alto-cloud.js, which stays the source of truth: the
browser writes this record when a page is uploaded by hand, and the connector
writes the same record when it publishes the page itself. Two writers that
disagreed would sort one timeline into two different homepage boxes, so
tests/test_cloud_store.py runs both over the same real pages.
"""
from __future__ import annotations

import html as _html
import json
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
_PLAN = re.compile(r'<script id="alto-sp-data">window\._ALTO_SP=(\{.*?\});</script>', re.S)
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
PLAN_CAP = 120


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


# The format a built page is, read off the line each format's own script starts
# with (the same tests as _fmtOf in alto-cloud.js). A System is checked
# first: it is an outline with more on top.
_FMT = (("system", re.compile(r"^window\._ALTO_SOLAR=", re.M)),
        ("building", re.compile(r"^window\._ALTO_BUILDING=", re.M)),
        ("world", re.compile(r"^window\._ALTO_WORLD=", re.M)),
        ("palace", re.compile(r"^window\._altoPalace=function", re.M)),
        ("outline", re.compile(r"^window\._ALTO_OUTLINE=", re.M)),
        ("lanes", re.compile(r"^window\._ALTO_LANES=", re.M)))


def fmt_of(h: str) -> str:
    for key, rx in _FMT:
        if rx.search(h or ""):
            return key
    return "timeline"


def plan_of(h: str) -> dict | None:
    """The study plan's summary for the homepage card (plan_of in alto-cloud.js is its twin): the day and the node of each item, in order, and
    the exam date. NOTHING else: no reason text, no minutes, no signals. None when the page has no plan."""
    m = _PLAN.search(h or "")
    if not m:
        return None
    try:
        p = json.loads(m.group(1).replace("<\\!--", "<!--"))
    except ValueError:
        return None
    days, nodes = [], []
    items = p.get("items") if isinstance(p, dict) else None
    for it in items if isinstance(items, list) else []:
        if len(days) >= PLAN_CAP:
            break
        d, n = it.get("day") if isinstance(it, dict) else None, it.get("node") if isinstance(it, dict) else None
        if isinstance(d, str) and _DAY.fullmatch(d) and isinstance(n, str) and 0 < len(n) <= 80:
            days.append(d)
            nodes.append(n)
    if not days:
        return None
    ex = p.get("exam")
    return {"days": days, "nodes": nodes, "exam": ex if isinstance(ex, str) and _DAY.fullmatch(ex) else ""}


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
    out = {"title": project or heading, "heading": heading, "project": project,
           "tid": cm.group(1) if cm else "", "units": units, "search": search,
           "fmt": fmt_of(h), "v": META_V}
    plan = plan_of(h)
    if plan:                                          # a page with no plan has no "plan" key: the writer then removes the field
        out["plan"] = plan
    return out


def title_of(h: str) -> str:
    """The private shell's titleOf: the alto-label, else the <title>."""
    lm = _LABEL.search(h or "")
    if lm and lm.group(1):
        return _html.unescape(lm.group(1)).strip()
    tm = _TITLE.search(h or "")
    return re.sub(r"\s*—\s*Alto(\s+Timeline)?\s*$", "", tm.group(1)).strip() if tm else ""
