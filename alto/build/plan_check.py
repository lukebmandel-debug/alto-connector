"""The study plan: its record and the ONE check both routes use (the connector's `set_study_plan` and Bass's `make_study_plan`).

brief.study_plan = {"v": 1, "exam_date": "YYYY-MM-DD" | "", "days_per_week": int | None, "minutes_per_day": int | None,
                    "items": [{"node": <a node id of this timeline>, "day": "YYYY-MM-DD", "why": <= 200 characters of plain text
                               that quotes the student's own signal, "signal": "marks" | "quiz" | "exam" | "told" | "syllabus"}]}
An empty or absent plan changes nothing: a page is built exactly as it was. What a student has ticked off is the reader's own
state (next to the card marks); nothing here ever writes it.

Closed system: a plan names only nodes the timeline has and carries only the student's own words (the `why`). Nothing is added
or picked here: a plan that fails is refused whole, with every problem named, and nothing is stored.
"""
from __future__ import annotations

import datetime as _dt
import re

SIGNALS = ("marks", "quiz", "exam", "told", "syllabus")
MAX_ITEMS = 120
MAX_DAYS = 366                       # how far from today a day may be, either way (set-time check only)
MAX_WHY = 200
PLAN_KEYS = frozenset({"v", "exam_date", "days_per_week", "minutes_per_day", "items"})
ITEM_KEYS = frozenset({"node", "day", "why", "signal"})
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _err(msg):
    from .brief import BriefError
    return BriefError(msg)


def node_ids(nodes) -> set | None:
    """The ids of `nodes`: Node objects, node dicts or plain ids; None (no node check) for None."""
    if nodes is None:
        return None
    out = set()
    for n in nodes:
        nid = n if isinstance(n, str) else (n.get("id") if isinstance(n, dict) else getattr(n, "id", None))
        if isinstance(nid, str):
            out.add(nid)
    return out


def _date(v, what: str, problems: list, today=None):
    if not isinstance(v, str) or not _DATE.match(v):
        problems.append(f"{what}: {v!r} is not a date (YYYY-MM-DD)")
        return None
    try:
        d = _dt.date.fromisoformat(v)
    except ValueError:
        problems.append(f"{what}: {v!r} is not a real date")
        return None
    if today is not None and abs((d - today).days) > MAX_DAYS:
        problems.append(f"{what}: {v} is more than {MAX_DAYS} days from today")
        return None
    return d


def _int(v, what: str, lo: int, hi: int, problems: list):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        problems.append(f"{what}: {v!r} must be a whole number from {lo} to {hi}")
        return None
    return v


def check_plan(nodes, plan, *, today=None, strict: bool = True) -> dict:
    """The plan as it will be stored (text made plain, a day-by-day order), or BriefError naming every problem.

    nodes: this timeline's nodes (objects, dicts or ids); None skips the node check. today: a date, to hold every day within a
    year of it (the set-time check; left out when an old plan is read back). strict=False drops what is wrong instead of
    refusing (how a build reads a plan whose node was deleted since: the rest of the plan stands)."""
    from .sanitize import plain_text
    problems: list = []
    ids = node_ids(nodes)
    if plan in (None, {}):
        return {}
    if not isinstance(plan, dict):
        raise _err("study_plan must be an object")
    extra = sorted(set(plan) - PLAN_KEYS)
    if extra:
        problems.append(f"study_plan: unknown field(s) {extra}")
    if plan.get("v", 1) != 1:
        problems.append(f"study_plan.v: {plan.get('v')!r} is not a version this build reads (1)")
    exam = plan.get("exam_date") or ""
    if exam:
        _date(exam, "exam_date", problems)
    dpw = _int(plan.get("days_per_week"), "days_per_week", 1, 7, problems)
    mpd = _int(plan.get("minutes_per_day"), "minutes_per_day", 5, 1440, problems)
    raw = plan.get("items")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise _err("study_plan.items must be a list")
    if len(raw) > MAX_ITEMS:
        problems.append(f"study_plan.items: {len(raw)} items; at most {MAX_ITEMS}")
        raw = raw[:MAX_ITEMS]
    items, seen = [], set()
    for i, it in enumerate(raw, 1):
        where = f"item {i}"
        bad: list = []
        if not isinstance(it, dict):
            bad.append(f"{where}: must be an object")
        else:
            extra = sorted(set(it) - ITEM_KEYS)
            if extra:
                bad.append(f"{where}: unknown field(s) {extra}")
            node = it.get("node")
            if not isinstance(node, str) or not node:
                bad.append(f"{where}: node is required")
            elif ids is not None and node not in ids:
                bad.append(f"{where}: node {node!r} is not in this timeline")
            day = it.get("day")
            _date(day, f"{where} day", bad, today)
            why = plain_text(it.get("why") if isinstance(it.get("why"), str) else "")
            why = re.sub(r"\s+", " ", why).strip()
            if not why:
                bad.append(f"{where}: why is required (quote the student's own signal)")
            elif len(why) > MAX_WHY:
                bad.append(f"{where}: why is {len(why)} characters; at most {MAX_WHY}")
            sig = it.get("signal")
            if sig not in SIGNALS:
                bad.append(f"{where}: signal {sig!r} must be one of {list(SIGNALS)}")
            if not bad:
                key = (node, day)
                if key in seen:
                    bad.append(f"{where}: {node!r} is already planned for {day}")
                else:
                    seen.add(key)
        if bad:
            problems.extend(bad)
            continue
        items.append({"node": node, "day": day, "why": why, "signal": sig})
    if problems and strict:
        raise _err("study plan refused: " + "; ".join(problems[:12]) + (f" (+{len(problems) - 12} more)" if len(problems) > 12 else ""))
    items.sort(key=lambda x: (x["day"], x["node"]))
    out = {"v": 1, "exam_date": exam, "days_per_week": dpw, "minutes_per_day": mpd, "items": items}
    return out


def sanitize_in_place(b, nodes) -> None:
    """At build: the plan made plain, and an item whose node has since gone dropped (the rest stands). Idempotent."""
    if not getattr(b, "study_plan", None):
        return
    try:
        b.study_plan = check_plan(nodes, b.study_plan, strict=False)
    except Exception:                                    # noqa: BLE001 — a plan that cannot be read is left out, never breaks a build
        b.study_plan = {}
