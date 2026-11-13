"""Turn one of the student's own timelines into another format (the homepage's "Turn into another format…", Bass route).

Closed system, enforced three times:
  1. the model is given ONLY that file's own cards (never the library or another file) and told to copy their text, not add;
  2. it must report, for every card it makes, which of the original cards it came from (`report_sources`, a Bass-owned tool);
  3. before anything is kept, `ground()` checks that report against what was actually written, with no model involved:
     every new card names real source cards, every source card is used, and no new card holds a content word that is not in
     the cards it came from. One failure fails the whole conversion: nothing is saved (the draft is removed), nothing charged.
The original is never touched: the result is a new timeline in the same project. Which formats Bass can make is BASS_TARGETS:
the three palace formats need map data from the network, which a Bass action never fetches (the Claude route makes those).
"""
from __future__ import annotations

import json
import re

from .tools import ToolOutcome

BASS_TARGETS = ("timeline", "outline", "system", "lanes")

# Until the first live call's numbers are in, a conversion is estimated at this many credits whatever the count says
# (a safe high figure: under the $3 action cap, over the estimate prompt's line, so the student always confirms the cost).
CONVERT_SAFE_CREDITS = 200

MAX_NOVEL_WORDS = 0          # content words a new card may hold that its source cards do not
MIN_WORD = 4                 # shorter words are not content
STRUCTURAL = frozenset({"overview", "summary", "contents", "section", "sections", "part", "parts", "page", "pages", "card", "cards"})

REPORT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["cards"],
    "properties": {"cards": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["card", "from"],
        "properties": {"card": {"type": "string"}, "from": {"type": "array", "items": {"type": "string"}}}}}}}

BRIEFS = {
    "timeline": "a plain timeline (create_timeline mode 'linear': a sketch, the cards in sequence)",
    "outline": "an outline (create_timeline mode 'outline': concepts that contain one another, structure carried by each card's parent)",
    "system": "a System (create_timeline mode 'outline' with layout 'solar': every top concept a sun, its children planets, theirs moons)",
    "lanes": "a horizontal timeline (create_timeline mode 'lanes': the story left to right, each character on a line of its own)",
}


def card_text(n: dict) -> str:
    parts = [str(n.get("title") or ""), str(n.get("desc") or ""), str(n.get("tag") or "")]
    for s in n.get("sections") or []:
        if isinstance(s, dict):
            parts += [str(s.get("h") or ""), str(s.get("t") or "")]
    return " ".join(p for p in parts if p)


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower().replace("’", "'")) if len(w) >= MIN_WORD and w not in STRUCTURAL}


def ground(source: list, made: list, report) -> dict:
    """The closed-system check, pure. source / made: the original / new cards (dicts with id, title, desc, tag, sections).
    report: what the model said (REPORT_SCHEMA). -> {ok, reasons, cards_in, cards_out}."""
    why: list = []
    src = {str(n["id"]): n for n in source}
    new = {str(n["id"]): n for n in made}
    rows = report.get("cards") if isinstance(report, dict) else None
    if not isinstance(rows, list) or not rows:
        return {"ok": False, "reasons": ["no source report"], "cards_in": len(src), "cards_out": len(new)}
    said: dict = {}
    for r in rows:
        cid = str(r.get("card", ""))
        if cid in said:
            why.append(f"card {cid!r} reported twice")
        said[cid] = [str(x) for x in (r.get("from") or [])]
    for cid in new:
        if cid not in said:
            why.append(f"card {cid!r} names no source")
    for cid, froms in said.items():
        if cid not in new:
            why.append(f"report names a card that was not made: {cid!r}")
            continue
        bad = [f for f in froms if f not in src]
        if not froms or bad:
            why.append(f"card {cid!r} has no real source" if not froms else f"card {cid!r} names unknown source(s) {bad}")
            continue
        have = set().union(*(_words(card_text(src[f])) for f in froms))
        novel = sorted(_words(card_text(new[cid])) - have)
        if len(novel) > MAX_NOVEL_WORDS:
            why.append(f"card {cid!r} holds words not in its source cards: {novel[:5]}")
    used = {f for froms in said.values() for f in froms}
    left = sorted(set(src) - used)
    if left:
        why.append(f"source cards left out: {left[:8]}")
    return {"ok": not why, "reasons": why, "cards_in": len(src), "cards_out": len(new)}


def convert_text(title: str, source: list, target: str, source_format: str = "") -> str:
    """The request: the original's own cards as the only material, and what to make of them."""
    cards = [{"id": n["id"], "title": n.get("title", ""), "desc": n.get("desc", ""), "tag": n.get("tag", ""),
              "parent": n.get("parent", ""), "sections": n.get("sections", [])} for n in source]
    return (f"Turn the student's timeline \"{title}\"{' (' + source_format + ')' if source_format else ''} into {BRIEFS[target]}. "
            "The student agreed that Bass builds ONLY from the cards below (consent = true). Make a NEW timeline in the same project and never touch the "
            "original. Copy each card's own words (title, description, sections) as they are: re-arrange them, never add a fact, "
            "date, case or sentence that is not in the card, and never leave a card out. Make exactly one new card for each card "
            "below. When the build is done, call report_sources once: for each new card, its id and the ids of the original card(s) "
            "it came from.\n\nThe original's cards:\n" + json.dumps(cards, ensure_ascii=False))


class ConvertTools:
    """The engine's tool belt for a conversion: the usual build tools plus the Bass-owned report. Nothing else."""

    def __init__(self, base):
        self.base, self.report, self.timeline_id = base, None, None

    def specs(self) -> list:
        return self.base.specs() + [{
            "name": "report_sources", "strict": True,
            "description": ("Say, for every card you made, which of the original cards it came from. Call it once, last, "
                            "after build_timeline."),
            "input_schema": REPORT_SCHEMA}]

    def execute(self, uid: str, name: str, tool_input) -> ToolOutcome:
        if name != "report_sources":
            out = self.base.execute(uid, name, tool_input)
            if name == "create_timeline" and not out.is_error:
                try:
                    self.timeline_id = json.loads(out.content).get("timeline_id") or self.timeline_id
                except ValueError:
                    pass
            return out
        import jsonschema
        try:
            jsonschema.validate(tool_input, REPORT_SCHEMA)
        except jsonschema.ValidationError as e:
            return ToolOutcome(json.dumps({"error": "invalid_input", "message": e.message[:300]}), True, name=name)
        self.report = tool_input
        return ToolOutcome(json.dumps({"ok": True}), name=name, final=True)

    def __getattr__(self, k):                                  # the base belt's other attributes (strict_names ...)
        return getattr(self.base, k)
