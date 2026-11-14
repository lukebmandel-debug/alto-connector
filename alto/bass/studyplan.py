"""Bass makes the student's study plan (mock-only until the first live call; the model route of `set_study_plan`).

The student decides what matters; Bass only schedules what they gave it. Input: this timeline's own nodes, and the student's
answers (exam date, time, topics they say they are weak on, a syllabus they pasted) and, if the page sends them, their card marks
and quiz scores. The model gets ONE Bass-owned tool, `propose_study_plan`, and nothing that writes. Before anything is saved
`ground_plan()` checks the result with no model involved: every node is one of the timeline's, every signal is one the student
really gave, every `why` quotes it, every day is real and inside the window. One failure: nothing saved, the call refunded.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from .tools import ToolOutcome

STUDYPLAN_SAFE_CREDITS = 30            # until the first live call's numbers are in: above the estimate prompt's line, so it always asks
MAX_WEAK, MAX_PHRASE, MAX_TOLD, MAX_SYLLABUS = 20, 120, 1000, 20000
DEFAULT_WINDOW_DAYS = 14               # with no exam date the plan covers the next two weeks
QUIZ_LOW = 70                          # a quiz percentage below this is a signal

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["node", "day", "why", "signal"],
        "properties": {"node": {"type": "string"}, "day": {"type": "string"}, "why": {"type": "string"},
                       "signal": {"type": "string", "enum": ["marks", "quiz", "exam", "told", "syllabus"]}}}}}}


def clean_inputs(answers, marks, quiz):
    """-> (answers, marks, quiz, error message or None). Bounded and typed; nothing here is trusted."""
    a = answers if isinstance(answers, dict) else {}
    weak = [str(w).strip() for w in (a.get("weak") or []) if str(w).strip()] if isinstance(a.get("weak"), list) else []
    if len(weak) > MAX_WEAK or any(len(w) > MAX_PHRASE for w in weak):
        return None, None, None, f"weak: at most {MAX_WEAK} topics of {MAX_PHRASE} characters"
    told, syl = str(a.get("told") or "").strip(), str(a.get("syllabus") or "").strip()
    if len(told) > MAX_TOLD or len(syl) > MAX_SYLLABUS:
        return None, None, None, "told / syllabus is too long"
    exam = str(a.get("exam_date") or "").strip()
    out = {"exam_date": exam, "days_per_week": a.get("days_per_week"), "minutes_per_day": a.get("minutes_per_day"),
           "weak": weak, "told": told, "syllabus": syl}
    m = {str(k): v for k, v in (marks or {}).items() if v in ("still_learning", "know_it")} if isinstance(marks, dict) else {}
    q = {str(k): v for k, v in (quiz or {}).items() if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100} if isinstance(quiz, dict) else {}
    return out, m, q, None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", s.lower().replace("’", "'"))).strip()


def plan_text(title: str, nodes: list, a: dict, marks: dict, quiz: dict, today: dt.date) -> str:
    last = a["exam_date"] or (today + dt.timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
    cards = [{"id": n["id"], "title": n.get("title", "")} for n in nodes]
    given = {"exam_date": a["exam_date"] or None, "days_per_week": a["days_per_week"], "minutes_per_day": a["minutes_per_day"],
             "weak_topics_the_student_named": a["weak"], "the_student_said": a["told"] or None,
             "syllabus_the_student_pasted": a["syllabus"] or None,
             "cards_marked": marks or None, "quiz_percent_by_node": quiz or None}
    return (f"Make a study plan for the student's timeline \"{title}\". Today is {today.isoformat()}. Plan days from today to {last}. "
            "The student decides what matters: schedule ONLY what they gave you below, never your own idea of importance, and never a "
            "node that is not in the list. Each item is one node on one day. `signal` says which of the student's own signals puts it "
            "there: marks (they marked it Still learning), quiz (their quiz percent for it is low), exam (the exam date they gave), "
            "told (they named the topic), syllabus (it is in the syllabus they pasted). `why` is one short plain sentence that "
            "quotes that signal in their words (their topic as they said it, the node's title, the score, the exam date). If they "
            "gave no signal for a node, leave it out. Respect days_per_week and minutes_per_day when given. Call propose_study_plan once.\n\n"
            "The timeline's nodes:\n" + json.dumps(cards, ensure_ascii=False) + "\n\nWhat the student gave:\n" + json.dumps(given, ensure_ascii=False))


def ground_plan(nodes: list, items, a: dict, marks: dict, quiz: dict, today: dt.date) -> dict:
    """The closed-system check for a proposed plan, pure. -> {ok, reasons, nodes, days}."""
    why: list = []
    ids = {str(n["id"]): n for n in nodes}
    if not isinstance(items, list) or not items:
        return {"ok": False, "reasons": ["no plan proposed"], "nodes": 0, "days": 0}
    last = None
    if a["exam_date"]:
        try:
            last = dt.date.fromisoformat(a["exam_date"])
        except ValueError:
            return {"ok": False, "reasons": ["the exam date is not a date"], "nodes": 0, "days": 0}
    else:
        last = today + dt.timedelta(days=DEFAULT_WINDOW_DAYS)
    phrases = [p for p in [_norm(w) for w in a["weak"]] + [_norm(c) for c in re.split(r"[.;,\n]", a["told"])] if len(p) >= 4]
    syl = _norm(a["syllabus"])
    for n, it in enumerate(items, 1):
        if not isinstance(it, dict):
            why.append(f"item {n} is not an item")
            continue
        node, sig, text = str(it.get("node", "")), it.get("signal"), _norm(str(it.get("why", "")))
        if node not in ids:
            why.append(f"item {n}: node {node!r} is not in this timeline")
            continue
        title = _norm(str(ids[node].get("title", "")))
        try:
            day = dt.date.fromisoformat(str(it.get("day", "")))
            if day < today or day > last:
                why.append(f"item {n}: {it.get('day')} is outside {today.isoformat()} to {last.isoformat()}")
        except ValueError:
            why.append(f"item {n}: {it.get('day')!r} is not a date")
        if sig == "marks":
            if marks.get(node) != "still_learning":
                why.append(f"item {n}: {node!r} was not marked Still learning")
            elif not (title and title in text) and "learning" not in text and "marked" not in text:
                why.append(f"item {n}: the why does not quote the mark")
        elif sig == "quiz":
            if node not in quiz or quiz[node] >= QUIZ_LOW:
                why.append(f"item {n}: {node!r} has no low quiz score")
            elif str(quiz[node]) not in text and "quiz" not in text:
                why.append(f"item {n}: the why does not quote the score")
        elif sig == "exam":
            if not a["exam_date"]:
                why.append(f"item {n}: no exam date was given")
            elif "exam" not in text:
                why.append(f"item {n}: the why does not name the exam")
        elif sig == "told":
            if not phrases:
                why.append(f"item {n}: the student named no topic")
            elif not (any(p in text for p in phrases) or (title and title in text and any(title in p for p in phrases))):
                why.append(f"item {n}: the why does not quote what the student said")
        elif sig == "syllabus":
            if not syl:
                why.append(f"item {n}: no syllabus was given")
            elif not (title and title in syl):
                why.append(f"item {n}: {node!r} is not in the syllabus")
        else:
            why.append(f"item {n}: signal {sig!r} is not one of the student's")
    days = {str(it.get("day")) for it in items if isinstance(it, dict)}
    return {"ok": not why, "reasons": why, "nodes": len({str(it.get('node')) for it in items if isinstance(it, dict)}), "days": len(days)}


def summary(items: list) -> str:
    """'6 nodes, Mon-Fri' / '6 nodes, Mon, Wed and Fri' / '6 nodes, 1 day': what the student is asked to accept."""
    nodes = len({i["node"] for i in items})
    names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    wd = sorted({dt.date.fromisoformat(i["day"]).weekday() for i in items})
    if len(wd) == 1:
        span = names[wd[0]]
    elif wd == list(range(wd[0], wd[-1] + 1)):
        span = f"{names[wd[0]]}-{names[wd[-1]]}"
    else:
        span = ", ".join(names[d] for d in wd[:-1]) + f" and {names[wd[-1]]}"
    return f"{nodes} node{'' if nodes == 1 else 's'}, {span}"


class PlanTools:
    """The plan action's whole tool belt: one Bass-owned tool that hands a proposal back WITHOUT writing anything."""

    def __init__(self):
        self.items: list | None = None

    def specs(self) -> list:
        return [{"name": "propose_study_plan", "strict": True,
                 "description": ("Hand back the student's study plan: for each node to study, the day and why (quoting the student's "
                                 "own signal). Use only the nodes and signals given. Call it once."),
                 "input_schema": PLAN_SCHEMA}]

    def execute(self, uid: str, name: str, tool_input) -> ToolOutcome:
        import jsonschema
        if name != "propose_study_plan":
            return ToolOutcome(json.dumps({"error": "unknown_tool", "message": f"no tool named {name}"}), True, name=name)
        try:
            jsonschema.validate(tool_input, PLAN_SCHEMA)
        except jsonschema.ValidationError as e:
            return ToolOutcome(json.dumps({"error": "invalid_input", "message": e.message[:300]}), True, name=name)
        self.items = tool_input["items"]
        return ToolOutcome(json.dumps({"ok": True}), name=name, final=True)
