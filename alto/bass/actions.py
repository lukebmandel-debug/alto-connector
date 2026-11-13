"""The action layer the Bass UI calls. JSON in, JSON out; thin wrappers over Engine, no model logic of their own.

Control #1 of the memo's section 4.5: the browser never talks to Claude. It sends one of the structured actions below and
gets back a structured result; there is no free-text passthrough (the one free-text door, `edit`, goes through the
off-topic gate first). Contract + real sample JSON for every call and state: docs/bass-api.md (generated from a run on
the mock by tests/bass_apidoc.py, and checked by tests/test_bass_actions.py).

  Actions(engine, ledger).dispatch(uid, {"action": "build", "args": {...}}, on_event=fn)   # the one door an endpoint uses
  balance | estimate | propose | build | edit | stop                                       # the same, as methods

Every result has the same top-level keys (see `_result`). status is one of:
  ok, estimate, no_credits, busy, paused, off_topic, refused, capped, stopped, error
"""
from __future__ import annotations

import inspect
import json
import math
import uuid
from typing import Callable

import jsonschema

from . import config as P
from . import meter
from . import shapes
from .engine import Engine, strip_thinking
from .errors import POLICIES
from .tools import ToolOutcome

STATUSES = ("ok", "estimate", "no_credits", "busy", "paused", "off_topic", "refused", "capped", "stopped", "error")
ENGINE_TO_STATUS = {"done": "ok", "off_topic": "off_topic", "capped": "capped", "no_credits": "no_credits",
                    "refused": "refused", "paused": "paused", "busy": "busy", "stopped": "stopped",
                    "max_tokens": "error", "error": "error"}
RETRYABLE_CODES = {"rate_limited", "overloaded", "timeout", "connection", "upstream", "busy", "bass_paused",
                   "max_tokens"}

# tool -> (step, label the student sees while a build runs)
STEPS = {
    "create_project": ("setup", "Setting up your timeline"), "create_timeline": ("setup", "Setting up your timeline"),
    "record_materials_consent": ("consent", "Checking your materials"),
    "set_entities": ("chips", "Adding your chips"), "set_axis_values": ("chips", "Adding your chips"),
    "set_flags": ("chips", "Adding your chips"), "set_lines": ("chips", "Adding your chips"),
    "add_nodes": ("cards", "Writing cards"), "delete_nodes": ("cards", "Writing cards"),
    "add_connections": ("links", "Linking cards"),
    "set_overview": ("layout", "Laying it out"), "place_nodes": ("layout", "Laying it out"),
    "run_layout_preview": ("layout", "Laying it out"),
    "build_timeline": ("build", "Building your page"),
    "get_timeline": ("look", "Looking over your timeline"), "list_projects": ("look", "Looking over your timeline"),
    "get_nodes": ("look", "Looking over your timeline"),
    "preview_timeline": ("look", "Looking over your timeline"),
}

PROPOSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "acts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                            "properties": {"label": {"type": "string"}, "summary": {"type": "string"}},
                                            "required": ["label"]}},
        "entities": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                "properties": {"id": {"type": "string"}, "name": {"type": "string"},
                                                               "role": {"type": "string"}},
                                                "required": ["id", "name"]}},
        "fields": {"type": "array", "items": {"type": "string"}},
        "card_estimate": {"type": "integer"},
        "goal": {"type": "string"},
        "shape": {"type": "string", "enum": list(shapes.SHAPES)},
        "extras": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "properties": {"kind": {"type": "string",
                                                                      "enum": ["quiz", "cards", "tree", "timeline"]},
                                                             "where": {"type": "string"}},
                                              "required": ["kind"]}},
    },
    "required": ["title", "acts", "entities"],
}


# The guided start (propose only): the single Bass copy of the interview guide's section S. Materials come first.
GUIDED_START = (
    "Guided start. The student's materials come first, and the student does the thinking: what matters in their notes and how it is organized is theirs to decide. Never boil the notes down for them, never choose, rank or group a concept they have not named, never add one that is not in their materials.\n"
    'How you talk to the student: plain everyday words, like a helpful classmate. Never say "chips", "extras", "goal", "fields", "schema" or any internal word to them; say "plan", "quiz", "flash cards", "decision tree", "timeline". ONE question per message, never two, and keep a message to about 60 words.\n'
    'Opening question: ask "What is this for, and how do you like to study?" Skip it ONLY when the materials or an earlier answer give BOTH what the work is for AND how they like to study. If they give only what it is for, ask just how they like to study; if only how they study, ask just what it is for. A stated habit IS the study style ("I read my notes first", "I learn by doing questions", "I use flash cards", "I like seeing the whole structure"): treat it as given and do not ask how they study. Ask the missing half in their own words with NO menu of options: do not list study methods, formats or extras in the question; name one only if they ask or have already mentioned it.\n'
    'Then make the plan and OFFER at most three things that fit. Every sentence that proposes an extra is a question that ends in a question mark and has its reason in the same sentence, pointing at a place in their notes or at what they said about how they study ("Your notes on Hearsay list its exceptions: would a short quiz on them help?"). Never write "I\'ll write/add/make ..." about an extra before they say yes. If the student has given no goal or study style, ask the missing half first and do not offer yet. The reason must quote or name a specific heading or phrase from their notes ("Your notes on Personal Jurisdiction give the three steps: would a quiz on them help?"); "your notes" alone does not count. An offer is a QUESTION with a reason that names the place in THEIR notes ("Would a quiz on X help? Your notes give the rules and exceptions there."). Never state one as decided or planned (never "the plan is ...", "I\'ll add ..."); what you offer is not in the plan until they say yes. Ask which parts it should cover only AFTER they say yes. The kinds to offer: a quiz where the notes hold rules and exceptions (multiple-choice exams); a decision tree where the notes are a test with yes/no branches (essay, issue-spotting); a timeline where the notes have dates or a clear order; flash cards for terms. Fit offers to what they asked for and to what the notes hold: a decision tree only where the notes hold a real yes/no test you can quote in the reason (tiers or lists are not a test); flash cards or a quiz only for an exam, memorizing or practice goal, never on a plain simple timeline; if nothing fits, say so in one sentence and ask nothing more. Offer ONE kind of help per message: the second waits for their answer. Ask about only one thing at a time, for example which parts a quiz should cover, and ask about practice questions in a later message, once, saying they can paste or upload them and, in the same message, that if they have none you will write the questions only from their notes. Say nothing about a kind that does not fit; a no is final: do not offer it again and say nothing more about that kind afterwards (no "if you decide later, tell me"). Never reclassify, regroup or relabel anything the student named; a name the student did not say is asked, not added, even when it is in their notes ("Your notes list three exceptions to hearsay: do you want them as sub-concepts?"); When you read their outline back, keep the student\'s exact nesting (what is under what) and print it with indentation or numbering (I. A. 1.) so the nesting shows, never as one flat list; if you are unsure of the nesting, ask. When the build needs divisions or sections the student has not given, ASK where they would break it up, if anywhere ("Where would you break this up, if anywhere?"); never choose a split, a date to break at, or a grouping yourself, and after a no do not choose one either. A plain timeline needs at least two parts to show anything: if they want none, say so plainly and let them name two ("This kind of timeline needs at least two parts. What would you call the two stretches?"). if something looks like a different kind (a case rather than a concept), ASK ("Do you want Lopez as a case or as its own concept?") and do not decide. When you describe what a quiz or cards will contain, name only words that appear in their notes, or just say "questions written from your notes". Record their goal and the offers they accept in the plan\'s goal and extras fields (never mention those words). If they ask directly ("should I add anything extra?", "what else could help?"), that is a request for offers: give up to three offers, each a question with a reason pointing at a place in their notes and fitting how they study; never refuse it. Naming a kind of help is fine; never name a concept the student has not given. If you must decline, use two short sentences and the one question that moves them on; any other line before building is one or two sentences (40 words or fewer) with no second question. A list that only echoes their own plan back for confirmation is exempt from the length limit. Build only from their materials; never invent content.\n'
    'Study plan: when the student mentions an exam or test, or asks for a plan, a study plan is one of the at-most-three offers of that round, as a question with its reason ("You said the exam is on 12 December: would you like a study plan that tells you which concepts to study each day?"); a no is final. After a yes ask ONE question per message: how many days a week and how long each day, then which concepts they already know they are weak on. The student decides what goes first: propose at most six concepts from their own materials, each with its reason quoting what THEY said or what their own marks and quiz scores show, then ask "keep, drop or add?". Never pick a concept for them because it seems important and never add one that is not in their materials. A plan holds at most six concepts even after an add: if they add one to a full plan, ask which one to swap out. An answer about the plan\'s order or days ("follow the order in my notes") is not an answer about the outline: do not expand names from their notes because of it; the outline step still starts by asking for the units or main concepts. Record the exam date, time and chosen concepts in the plan fields; never mention fields to the student.')


class ProposeTools:
    """The propose step's whole tool belt: one Bass-owned tool that hands back chips WITHOUT writing anything."""

    def __init__(self):
        self.chips: dict | None = None

    def specs(self) -> list:
        return [{"name": "propose_chips", "strict": True,
                 "description": ("Propose the chips the student will confirm before anything is built: a title, the acts "
                                 "(sections), the entities (the people, cases, themes the timeline is organised around), "
                                 "optional extra fields, roughly how many cards the materials will make, and (optional) the "
                                 "student's goal and the extras they accepted. Use only what "
                                 "the materials say. Call it once."),
                 "input_schema": PROPOSE_SCHEMA}]

    def execute(self, uid: str, name: str, tool_input) -> ToolOutcome:
        try:
            jsonschema.validate(tool_input, PROPOSE_SCHEMA)
        except jsonschema.ValidationError as e:
            return ToolOutcome(json.dumps({"error": "invalid_input", "message": e.message[:300]}), True, name=name)
        self.chips = tool_input
        return ToolOutcome(json.dumps({"ok": True}), name=name, final=True)


def credits(mc: int) -> float:
    return round(mc / P.MC, 2)


def credits_label(mc: int) -> str:
    n = mc // P.MC
    if mc <= 0:
        return "0 credits"
    if n == 0:
        return "less than 1 credit"
    return f"{n} credit" + ("" if n == 1 else "s")


def materials_text(materials: list) -> str:
    parts = []
    for i, m in enumerate(materials, 1):
        parts.append(f"=== Material {i}: {m.get('name', 'untitled')} ({m.get('kind', 'notes')}) ===\n{m.get('text', '')}")
    return "\n\n".join(parts)


def library_block(library: list | None) -> dict | None:
    """The student's Bass Documents for this action (resolved by the proxy from the verified uid and the active scope, never sent by the
    page) as ONE text block marked for prompt caching: it comes first in the turn, so the next action in the same scope reads it from cache."""
    if not library:
        return None
    parts = [f"=== Document {i}: {m.get('name', 'untitled')} ===\n{m.get('text', '')}" for i, m in enumerate(library, 1)]
    return {"type": "text", "cache_control": {"type": "ephemeral"},
            "text": "The student's own documents for this class or outline (use ONLY these and the materials below; nothing else):\n\n"
                    + "\n\n".join(parts)}


def _with_library(text: str, library: list | None):
    blk = library_block(library)
    return [blk, {"type": "text", "text": text}] if blk else text


class Actions:
    def __init__(self, engine: Engine, ledger, *, ids: Callable[[], str] | None = None,
                 max_materials_chars: int = 600_000, keep_messages: int = 20):
        self.engine, self.ledger = engine, ledger
        self.ids = ids or (lambda: "act_" + uuid.uuid4().hex[:12])
        self.max_materials_chars = max_materials_chars
        self.keep_messages = keep_messages
        self.conversations: dict = {}      # (uid, timeline_id) -> messages; in memory: the hosted server swaps in a store

    # -- the one door -------------------------------------------------------------------------------------------
    def dispatch(self, uid: str, request: dict, on_event: Callable[[dict], None] | None = None) -> dict:
        if not isinstance(request, dict) or not isinstance(request.get("args", {}), dict):
            return self._bad("request must be {action, args}")
        name, args = request.get("action"), request.get("args", {})
        table = {"balance": self.balance, "estimate": self.estimate, "propose": self.propose, "build": self.build,
                 "edit": self.edit, "convert": self.convert, "make_study_plan": self.make_study_plan, "stop": self.stop}
        fn = table.get(name)
        if fn is None:
            return self._bad(f"unknown action {name!r}; one of {sorted(table)}")
        if name in ("build", "propose", "edit", "convert", "make_study_plan"):
            args = {**args, "on_event": on_event}
        try:
            inspect.signature(fn).bind(uid, **args)
        except TypeError as e:
            return self._bad(f"{name}: {e}")
        return fn(uid, **args)

    # -- calls ----------------------------------------------------------------------------------------------------
    def balance(self, uid: str) -> dict:
        mc = self.ledger.balance_mc(uid)
        return {"ok": True, "status": "ok", "credits": credits(mc), "label": credits_label(mc),
                "available": self.engine.flags.bass_enabled}

    def estimate(self, uid: str, kind: str = "build", materials: list | None = None, text: str = "",
                 library: list | None = None) -> dict:
        bad = self._check_kind(kind, ("build", "propose", "edit"))
        if bad:
            return bad
        mats = materials or []
        if sum(len(m.get("text", "")) for m in mats + (library or [])) > self.max_materials_chars:
            return self._error("too_large")
        body = ((library_block(library) or {}).get("text", "") + "\n\n" if library else "") \
            + (GUIDED_START + "\n\n" + shapes.MENU + "\n\n" if kind == "propose" else "") \
            + materials_text(mats) + ("\n\n" + text if text else "")
        engine_kind = "chat" if kind == "edit" else kind
        n_in = self.engine.count_input(engine_kind, body or "x")
        return self._estimate_dict(uid, kind, self.engine.estimate(engine_kind, n_in))

    def propose(self, uid: str, materials: list | None = None, note: str = "", on_event=None, library: list | None = None) -> dict:
        materials = materials if materials is not None or not library else []
        err = self._check_materials(materials, library)
        if err:
            return err
        action_id = self.ids()
        events = self._start(uid, action_id, "propose", on_event)
        tools = ProposeTools()
        text = ("Read the student's materials and propose the chips for their timeline. If the materials are not enough "
                "to propose anything, ask ONE short question instead.\n\n" + GUIDED_START + "\n\n" + shapes.MENU + "\n\n" + materials_text(materials)
                + (f"\n\nStudent's note: {note}" if note else ""))
        res = self.engine.run_action(uid, _with_library(text, library), kind="propose", action_id=action_id, tools=tools)
        out = self._result(uid, res, events, on_event)
        out["chips"] = tools.chips
        out["message"] = res.text if res.status == "done" else out["message"]
        return out

    def build(self, uid: str, chips: dict, materials: list | None = None, consent: bool = False, accepted: bool = False,
              on_event=None, library: list | None = None) -> dict:
        if not isinstance(chips, dict) or not chips.get("title") or not chips.get("acts"):
            return self._bad("chips needs at least a title and acts")
        materials = materials if materials is not None or not library else []
        err = self._check_materials(materials, library)
        if err:
            return err
        if consent is not True:
            return self._error("consent_required")
        body = ("The student confirmed the closed-system statement and agreed that Bass builds ONLY from the materials "
                "below (consent = true). Build the whole timeline from the confirmed plan.\n\nConfirmed plan:\n"
                + json.dumps(chips, ensure_ascii=False) + "\n\n" + materials_text(materials))
        if chips.get("extras"):
            body = body.replace("\n\nConfirmed plan:", " The plan's extras are what the student accepted (a quiz, flash cards, a decision "
                                "tree or a mini timeline on the named concept pages): build exactly those, from the materials only.\n\nConfirmed plan:", 1)
        if shapes.section(chips.get("shape")):
            body += "\n\n" + shapes.section(chips.get("shape"))
        body = _with_library(body, library)
        est = self.engine.estimate("build", self.engine.count_input("build", body))
        if est.show_prompt and not accepted:
            out = self._estimate_dict(uid, "build", est)
            out.update(status="estimate", ok=False, message=est.message, work_saved=False,
                       credits=self._credits_block(uid, 0, 0), events=[], code=None, retryable=False,
                       action_id=None)
            return out
        action_id = self.ids()
        events = self._start(uid, action_id, "build", on_event)
        state = {"cards_done": 0, "cards_total": chips.get("card_estimate"), "timeline_id": None}
        res = self.engine.run_action(uid, body, kind="build", action_id=action_id,
                                     on_tool=self._progress(uid, action_id, state, events, on_event))
        out = self._result(uid, res, events, on_event)
        out.update(timeline_id=state["timeline_id"], cards={"done": state["cards_done"], "total": state["cards_total"]})
        return out

    def convert(self, uid: str, timeline_id: str, target: str, consent: bool = False, accepted: bool = False,
                on_event=None) -> dict:
        """Turn the student's own timeline into another format, from its own cards only (convert.py). A new timeline in the same
        project; the original is never touched. Fails closed: a card with no source, a source left out or a word the source
        does not hold removes the draft, refunds the call and says so."""
        from alto import entitlements
        from . import convert as C
        if target not in C.BASS_TARGETS:
            return self._bad(f"convert: target must be one of {list(C.BASS_TARGETS)} (the palaces are made with Claude)")
        ok = entitlements.allowed(uid, target)                  # before anything is read, held or sent
        if not ok["ok"]:
            out = self._error("needs_plan")
            out.update(message=ok["message"], plan=ok["needs_plan"], format=target)
            return out
        if consent is not True:
            return self._error("consent_required")
        tb = self.engine.tools
        srv = tb.srv
        if tb.store is not None and srv._store is not tb.store:
            srv.set_store(tb.store)
        st = srv.get_store()
        doc = st.get_timeline(uid, timeline_id) if isinstance(timeline_id, str) and timeline_id else None
        if not doc:
            return self._bad("convert: no such timeline")
        if entitlements.format_of_brief(doc.get("brief") or {}) == target:
            return self._bad("convert: it already is that format")
        source = st.list_nodes(uid, timeline_id)
        if not source:
            return self._bad("convert: the timeline has no cards")
        title = (doc.get("brief") or {}).get("title") or timeline_id
        body = C.convert_text(title, source, target, entitlements.format_of_brief(doc.get("brief") or {}))
        real = self.engine.estimate("build", self.engine.count_input("build", body))
        est = meter.Estimate(mc=max(real.mc, C.CONVERT_SAFE_CREDITS * P.MC), turns=real.turns, show_prompt=True)   # a safe constant until live numbers
        if not accepted:
            out = self._estimate_dict(uid, "build", est)
            out.update(status="estimate", ok=False, message=est.message, work_saved=False, kind="convert",
                       credits=self._credits_block(uid, 0, 0), events=[], code=None, retryable=False, action_id=None,
                       cards_in=len(source))
            return out
        action_id = self.ids()
        events = self._start(uid, action_id, "build", on_event)
        state = {"cards_done": 0, "cards_total": len(source), "timeline_id": None}
        tools = C.ConvertTools(tb)
        res = self.engine.run_action(uid, body, kind="build", action_id=action_id, tools=tools,
                                     on_tool=self._progress(uid, action_id, state, events, on_event))
        if res.status != "done":
            out = self._result(uid, res, events, on_event)
            out.update(timeline_id=state["timeline_id"], cards={"done": state["cards_done"], "total": state["cards_total"]})
            return out
        made = st.list_nodes(uid, tools.timeline_id) if tools.timeline_id else []
        g = C.ground(source, made, tools.report)
        if not g["ok"]:
            if tools.timeline_id:
                st.delete_timeline(uid, tools.timeline_id)      # only the draft this action made: nothing is kept
            res.refunded_mc += self.ledger.refund(uid, action_id, "failed:conversion_failed")
            res.wrote, res.status, res.code = False, "error", "conversion_failed"
            res.user_message = POLICIES["conversion_failed"].user_message
        out = self._result(uid, res, events, on_event)
        out.update(timeline_id=None if not g["ok"] else tools.timeline_id, from_timeline=timeline_id, to=target,
                   cards_in=g["cards_in"], cards_out=g["cards_out"], grounding=g["reasons"][:5])
        return out

    def make_study_plan(self, uid: str, timeline_id: str, answers: dict | None = None, marks: dict | None = None,
                        quiz: dict | None = None, consent: bool = False, accepted: bool = False, on_event=None, today=None) -> dict:
        """Make the student's study plan from this timeline's own nodes and what the student gave (studyplan.py), and save it.
        Asks (an estimate) before it spends. Fails closed: a node that is not theirs, a signal they did not give, a why that does
        not quote it, or a day outside the window saves nothing and refunds the call."""
        import datetime as dt
        from alto import entitlements
        from alto.build.plan_check import check_plan
        from . import studyplan as SP
        from .errors import POLICIES
        ok = entitlements.allowed(uid, "study_plan")           # before anything is read, held or sent
        if not ok["ok"]:
            out = self._error("needs_plan")
            out.update(message=ok["message"], plan=ok["needs_plan"], feature="study_plan")
            return out
        if consent is not True:
            return self._error("consent_required")
        a, m, q, bad = SP.clean_inputs(answers, marks, quiz)
        if bad:
            return self._bad("make_study_plan: " + bad)
        tb = self.engine.tools
        srv = tb.srv
        if tb.store is not None and srv._store is not tb.store:
            srv.set_store(tb.store)
        st = srv.get_store()
        doc = st.get_timeline(uid, timeline_id) if isinstance(timeline_id, str) and timeline_id else None
        if not doc:
            return self._bad("make_study_plan: no such timeline")
        nodes = st.list_nodes(uid, timeline_id)
        if not nodes:
            return self._bad("make_study_plan: the timeline has no nodes")
        today = today or dt.date.today()
        body = SP.plan_text((doc.get("brief") or {}).get("title") or timeline_id, nodes, a, m, q, today)
        real = self.engine.estimate("propose", self.engine.count_input("propose", body))
        est = meter.Estimate(mc=max(real.mc, SP.STUDYPLAN_SAFE_CREDITS * P.MC), turns=real.turns, show_prompt=True)   # a safe constant until live numbers
        if not accepted:
            out = self._estimate_dict(uid, "build", est)
            out.update(status="estimate", ok=False, message=est.message, work_saved=False, kind="make_study_plan",
                       credits=self._credits_block(uid, 0, 0), events=[], code=None, retryable=False, action_id=None,
                       nodes_in=len(nodes))
            return out
        action_id = self.ids()
        events = self._start(uid, action_id, "propose", on_event)
        tools = SP.PlanTools()
        res = self.engine.run_action(uid, body, kind="propose", action_id=action_id, tools=tools)
        if res.status != "done":
            return self._result(uid, res, events, on_event)
        g = SP.ground_plan(nodes, tools.items, a, m, q, today)
        plan = None
        if g["ok"]:
            try:
                plan = check_plan(nodes, {"v": 1, "exam_date": a["exam_date"], "days_per_week": a["days_per_week"],
                                          "minutes_per_day": a["minutes_per_day"], "items": tools.items}, today=today)
            except Exception as e:                       # noqa: BLE001 — the shared check has the last word: a refusal is a failure, not a crash
                g = {"ok": False, "reasons": [str(e)[:300]], "nodes": 0, "days": 0}
        if not g["ok"]:
            res.refunded_mc += self.ledger.refund(uid, action_id, "failed:plan_failed")
            res.wrote, res.status, res.code = False, "error", "plan_failed"
            res.user_message = POLICIES["plan_failed"].user_message
            out = self._result(uid, res, events, on_event)
            out.update(plan_saved=False, grounding=g["reasons"][:5])
            return out
        brief = dict(doc["brief"])
        brief["study_plan"] = plan
        doc["brief"] = brief
        st.put_timeline(uid, timeline_id, doc)
        res.wrote = True
        built = tb.execute(uid, "build_timeline", {"timeline_id": timeline_id})        # free: no upstream call
        out = self._result(uid, res, events, on_event)
        out.update(plan_saved=True, nodes=g["nodes"], days=g["days"], summary=SP.summary(plan["items"]),
                   page_rebuilt=not built.is_error, grounding=[])
        return out

    def edit(self, uid: str, timeline_id: str, text: str, reset: bool = False, on_event=None, library: list | None = None) -> dict:
        if not isinstance(text, str) or not text.strip() or not isinstance(timeline_id, str) or not timeline_id:
            return self._bad("edit needs timeline_id and text")
        key = (uid, timeline_id)
        history = [] if reset else list(self.conversations.get(key, []))
        action_id = self.ids()
        events = self._start(uid, action_id, "edit", on_event)
        state = {"cards_done": 0, "cards_total": None, "timeline_id": timeline_id}
        # "chat" is the engine's free-text kind: it runs the off-topic gate first, and prices/models like an edit
        first = (shapes.edit_text() + "\n\n") if not history else ""       # the shapes ride on the first turn; the kept history carries them on
        turn = _with_library(f"{first}[Timeline {timeline_id}] {text.strip()}", library)
        res = self.engine.run_action(uid, turn, kind="chat", history=history,
                                     action_id=action_id,
                                     on_tool=self._progress(uid, action_id, state, events, on_event))
        if res.status == "done":
            # the documents ride on every edit (cached), so the kept conversation holds a short marker instead of a second copy
            lib = turn[0] if isinstance(turn, list) else None
            # The KEPT history never carries a thinking block (review finding A2): the marker swap below and the next edit's words rewrite
            # kept turns, and the API's history-editing check refuses a thinking block replayed after such an edit. Trimming only ever
            # drops whole turns from the front, at a plain user turn.
            self.conversations[key] = self._trim(strip_thinking([
                {**m, "content": [({"type": "text", "text": "[the student's documents were shown here]"} if b is lib else b)
                                  for b in m["content"]]} if lib is not None and isinstance(m.get("content"), list) else m
                for m in res.messages]))
        elif res.code == "history_mismatch":
            self.conversations.pop(key, None)             # this conversation's kept history is not usable: the next edit starts clean
        out = self._result(uid, res, events, on_event)
        out.update(timeline_id=timeline_id, changed=bool(res.wrote))
        return out

    def stop(self, uid: str, action_id: str) -> dict:
        self.engine.cancel(action_id, uid)                  # fails closed: only the account that started a running action can stop it
        return {"ok": True, "status": "ok", "stopping": action_id}

    # -- shared -------------------------------------------------------------------------------------------------------
    def _check_kind(self, kind, allowed):
        if kind not in allowed:
            return self._bad(f"kind must be one of {list(allowed)}")
        return None

    def _check_materials(self, materials, library=None):
        if (not isinstance(materials, list) or (not materials and not library)
                or not all(isinstance(m, dict) and isinstance(m.get("text", ""), str) for m in materials)):
            return self._bad("materials must be a non-empty list of {name, kind, text}")
        if sum(len(m.get("text", "")) for m in materials + list(library or [])) > self.max_materials_chars:
            return self._error("too_large")
        return None

    def _estimate_dict(self, uid: str, kind: str, est) -> dict:
        have = self.ledger.balance_mc(uid)
        return {"ok": True, "status": "ok", "kind": kind, "credits_text": meter.credits_text(est.mc),
                "estimate_credits": math.ceil(est.mc / P.MC), "show_prompt": est.show_prompt,
                "have": credits(have), "have_label": credits_label(have),
                "short_by": max(0, math.ceil((est.mc - have) / P.MC))}

    def _credits_block(self, uid: str, spent_mc: int, refunded_mc: int) -> dict:
        bal = self.ledger.balance_mc(uid)
        return {"spent": credits(spent_mc), "refunded": credits(refunded_mc), "balance": credits(bal),
                "label": credits_label(bal)}

    def _start(self, uid: str, action_id: str, kind: str, on_event) -> list:
        self.engine.claim(action_id, uid)                  # the id is theirs from the moment the start event hands it out
        events = []
        self._emit(events, on_event, {"event": "start", "action_id": action_id, "kind": kind})
        return events

    @staticmethod
    def _emit(events: list, on_event, ev: dict) -> None:
        events.append(ev)
        if on_event is not None:
            on_event(ev)

    def _progress(self, uid, action_id, state, events, on_event):
        def on_tool(name, tool_input, out: ToolOutcome):
            step, label = STEPS.get(name, ("work", "Working"))
            result = None
            try:
                result = json.loads(out.content)
            except ValueError:
                pass
            if isinstance(result, dict) and not out.is_error:
                if result.get("timeline_id"):
                    state["timeline_id"] = result["timeline_id"]
                if name == "add_nodes" and isinstance(result.get("total_nodes"), int):
                    state["cards_done"] = result["total_nodes"]
            detail = ""
            if step == "cards" and state["cards_done"]:
                t = state["cards_total"]
                detail = f"cards {state['cards_done']} of {t}" if t else f"cards {state['cards_done']}"
            self._emit(events, on_event, {
                "event": "progress", "action_id": action_id, "step": step, "label": label, "detail": detail,
                "ok": not out.is_error, "cards_done": state["cards_done"], "cards_total": state["cards_total"],
                "spent_credits": credits(self.ledger.action_spent_mc(uid, action_id))})
        return on_tool

    def _result(self, uid: str, res, events: list, on_event) -> dict:
        status = ENGINE_TO_STATUS.get(res.status, "error")
        message = res.user_message
        if not res.wrote:      # nothing was written, so never promise saved work
            message = message.replace(" Your work so far is saved.", "")
        out = {"ok": status == "ok", "status": status, "code": res.code or None, "message": message,
               "action_id": res.action_id, "work_saved": bool(res.wrote),
               "credits": self._credits_block(uid, res.spent_mc, res.refunded_mc),
               "retryable": status in ("busy", "paused") or res.code in RETRYABLE_CODES, "events": events}
        self._emit(events, on_event, {"event": "result", "action_id": res.action_id, "status": status,
                                      "message": out["message"]})
        return out

    def _bad(self, message: str) -> dict:
        return {"ok": False, "status": "error", "code": "bad_input", "message": message, "action_id": None,
                "work_saved": False, "credits": None, "retryable": False, "events": []}

    def _error(self, code: str) -> dict:
        from .errors import POLICIES
        return {"ok": False, "status": "error", "code": code, "message": POLICIES[code].user_message,
                "action_id": None, "work_saved": False, "credits": None, "retryable": False, "events": []}

    def _trim(self, messages: list) -> list:
        """Keep the last few messages: whole turns are dropped from the FRONT only, and the kept part starts at a plain user turn so
        tool_use/tool_result pairs stay whole. No kept turn is ever rewritten here. With no plain user turn to start at, nothing is kept
        (the next edit starts a fresh conversation) rather than cutting inside a tool round."""
        if len(messages) <= self.keep_messages:
            return messages
        for i in range(len(messages) - self.keep_messages, len(messages)):
            m = messages[i]
            if m["role"] == "user" and (isinstance(m["content"], str) or not any(
                    b.get("type") == "tool_result" for b in m["content"])):
                return messages[i:]
        return []
