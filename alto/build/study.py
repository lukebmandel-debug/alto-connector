"""Flash cards and quizzes inside a page (Section.cards, Section.quiz).

Like a decision tree (subtree.py), a page section may carry a study aid drawn
inside it, under the section's own text; a page without one is unchanged.

    cards = {"cards": [{id?, front, back}, ...],
             "shuffle": false,              # true: starts in a shuffled order
             "label": ""}                   # the bar's name ("Flash cards")

    quiz  = {"questions": [{id?, q, choices: [str, ...], answer: int | [int, ...],
                            explain?}, ...],
             "label": ""}                   # the bar's name ("Quiz")

`answer` is the index (0-based) of the right choice; a LIST of indexes makes the
question "select all that apply" (graded right only when exactly those are
chosen). A section carries ONE of tree / cards / quiz. §0 applies as
everywhere: every question, answer and explanation is grounded in the user's
own materials — a quiz is a way to study THEIR notes, never new material.

The reader marks cards "Know it" / "Still learning" and takes the quiz on the
page; its progress (card marks, best and last score, attempts) is kept in the
browser under `{page hl key}-st` and, for the owner, in their account
(alto-cloud.js: `study` on users/{uid}/tl/{tid}, merged newest-wins).

Build path: brief._check_sections → check_cards / check_quiz (shape);
sanitize.sanitize_brief → sanitize_study (plain text, ids, on a deepcopy);
builder → prepare (a hidden .ast-slot with the words, so search finds them, and
the data) → study_block (data + renderer, on every page: manual edit mode can
add a quiz to any section). Manual edit mode edits a section's whole list as one
change (`sd|<key>|study`, alto/edits.py folds it).
"""
from __future__ import annotations

import json
import re

from .sanitize import js_json

MAX_CARDS = 300
MAX_QUESTIONS = 100
MIN_CHOICES, MAX_CHOICES = 2, 8
CARDS_KEYS = {"cards", "shuffle", "label"}
CARD_KEYS = {"id", "front", "back"}
QUIZ_KEYS = {"questions", "label"}
Q_KEYS = {"id", "q", "choices", "answer", "explain"}
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
_LIM = {"front": 800, "back": 3000, "q": 1200, "choice": 500, "explain": 3000, "label": 120}


def _err(msg):
    from .brief import BriefError
    return BriefError(msg)


def _text(v) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _ids(items, what, kind):
    seen = set()
    for i, x in enumerate(items):
        nid = x.get("id")
        if nid in (None, ""):
            continue                       # given one at sanitize
        if not isinstance(nid, str) or not _ID.match(nid):
            raise _err(f"{what} {kind} {i + 1}: id {nid!r} must be a lowercase slug (a-z, 0-9, hyphens)")
        if nid in seen:
            raise _err(f"{what} {kind} {i + 1}: id {nid!r} is used twice")
        seen.add(nid)


def check_cards(cards, what: str) -> None:
    """Shape only: keys, ids, text on both sides, limits."""
    if not cards:
        return
    if not isinstance(cards, dict):
        raise _err(f"{what} cards: must be an object {{cards: [{{front, back}}, ...]}}")
    bad = sorted(set(cards) - CARDS_KEYS)
    if bad:
        raise _err(f"{what} cards: unknown key(s) {', '.join(bad)} — allowed: "
                   + ", ".join(sorted(CARDS_KEYS)))
    if not isinstance(cards.get("shuffle", False), bool):
        raise _err(f"{what} cards: shuffle must be true or false")
    if len(_text(cards.get("label"))) > _LIM["label"]:
        raise _err(f"{what} cards: label is longer than {_LIM['label']} characters")
    items = cards.get("cards")
    if not isinstance(items, list) or not items:
        raise _err(f"{what} cards: needs a non-empty `cards` list of {{front, back}}")
    if len(items) > MAX_CARDS:
        raise _err(f"{what} cards: {len(items)} cards exceeds the {MAX_CARDS}-card limit")
    for i, c in enumerate(items):
        w = f"{what} card {i + 1}"
        if not isinstance(c, dict):
            raise _err(f"{w}: must be an object {{front, back}}")
        bad = sorted(set(c) - CARD_KEYS)
        if bad:
            raise _err(f"{w}: unknown key(s) {', '.join(bad)} — allowed: front, back, id")
        for k in ("front", "back"):
            v = c.get(k)
            if not isinstance(v, str) or not v.strip():
                raise _err(f"{w}: needs `{k}` text (a question or term on the front, "
                           "its answer on the back, from the user's own notes)")
            if len(v) > _LIM[k]:
                raise _err(f"{w}: {k} is longer than {_LIM[k]} characters")
    _ids([c for c in items if isinstance(c, dict)], what, "card")


def check_quiz(quiz, what: str) -> None:
    """Shape only: keys, ids, choices, the answer's indexes, limits."""
    if not quiz:
        return
    if not isinstance(quiz, dict):
        raise _err(f"{what} quiz: must be an object {{questions: [{{q, choices, answer}}, ...]}}")
    bad = sorted(set(quiz) - QUIZ_KEYS)
    if bad:
        raise _err(f"{what} quiz: unknown key(s) {', '.join(bad)} — allowed: "
                   + ", ".join(sorted(QUIZ_KEYS)))
    if len(_text(quiz.get("label"))) > _LIM["label"]:
        raise _err(f"{what} quiz: label is longer than {_LIM['label']} characters")
    items = quiz.get("questions")
    if not isinstance(items, list) or not items:
        raise _err(f"{what} quiz: needs a non-empty `questions` list of {{q, choices, answer}}")
    if len(items) > MAX_QUESTIONS:
        raise _err(f"{what} quiz: {len(items)} questions exceeds the {MAX_QUESTIONS}-question limit")
    for i, q in enumerate(items):
        w = f"{what} question {i + 1}"
        if not isinstance(q, dict):
            raise _err(f"{w}: must be an object {{q, choices, answer, explain?}}")
        bad = sorted(set(q) - Q_KEYS)
        if bad:
            raise _err(f"{w}: unknown key(s) {', '.join(bad)} — allowed: q, choices, answer, explain, id")
        if not isinstance(q.get("q"), str) or not q["q"].strip():
            raise _err(f"{w}: needs `q`, the question")
        if len(q["q"]) > _LIM["q"]:
            raise _err(f"{w}: q is longer than {_LIM['q']} characters")
        ch = q.get("choices")
        if not isinstance(ch, list) or not MIN_CHOICES <= len(ch) <= MAX_CHOICES:
            raise _err(f"{w}: `choices` must be a list of {MIN_CHOICES}-{MAX_CHOICES} answers")
        seen = set()
        for j, c in enumerate(ch):
            if not isinstance(c, str) or not c.strip():
                raise _err(f"{w}: choice {j + 1} is empty")
            if len(c) > _LIM["choice"]:
                raise _err(f"{w}: choice {j + 1} is longer than {_LIM['choice']} characters")
            if c.strip().lower() in seen:
                raise _err(f"{w}: choice {j + 1} repeats an earlier choice")
            seen.add(c.strip().lower())
        a = q.get("answer")
        want = a if isinstance(a, list) else [a]
        if (not want or any(not isinstance(x, int) or isinstance(x, bool) or not 0 <= x < len(ch) for x in want)
                or len(set(want)) != len(want)):
            raise _err(f"{w}: `answer` must be the number (0-based) of the right choice, "
                       f"0-{len(ch) - 1}, or a list of such numbers for \"select all that apply\"")
        if isinstance(a, list) and len(a) == len(ch):
            raise _err(f"{w}: every choice is marked right — a question needs at least one wrong choice")
        if q.get("explain") is not None and (not isinstance(q["explain"], str)
                                             or len(q["explain"]) > _LIM["explain"]):
            raise _err(f"{w}: explain must be text of at most {_LIM['explain']} characters")
    _ids([q for q in items if isinstance(q, dict)], what, "question")


def _fill_ids(items, prefix):
    used = {x["id"] for x in items if x.get("id")}
    n = 0
    for x in items:
        if not x.get("id"):
            n += 1
            while f"{prefix}{n}" in used:
                n += 1
            x["id"] = f"{prefix}{n}"
            used.add(x["id"])


def sanitize_study(sec) -> None:
    """Plain text everywhere (the page shows it with textContent), a slug id
    for every item, and the answer in its canonical form. In place — on the
    section's own copy (the stored dict is never touched)."""
    from .sanitize import plain_text
    if sec.cards:
        c = sec.cards
        c["label"] = plain_text(c.get("label") or "").strip()
        c["shuffle"] = bool(c.get("shuffle"))
        for x in c["cards"]:
            x["front"] = plain_text(x["front"]).strip()
            x["back"] = plain_text(x["back"]).strip()
        _fill_ids(c["cards"], "c")
    if sec.quiz:
        z = sec.quiz
        z["label"] = plain_text(z.get("label") or "").strip()
        for x in z["questions"]:
            x["q"] = plain_text(x["q"]).strip()
            x["choices"] = [plain_text(c).strip() for c in x["choices"]]
            if isinstance(x["answer"], list):
                x["answer"] = sorted(x["answer"])
            e = plain_text(x.get("explain") or "").strip()
            if e:
                x["explain"] = e
            else:
                x.pop("explain", None)
        _fill_ids(z["questions"], "q")


def _all_sections(b, nodes):
    from .subtree import _all_sections as walk
    return walk(b, nodes)


def prepare(b, nodes) -> dict:
    """After sanitize: give every section with cards or a quiz a slot at the end
    of its text (the words inside it, hidden, so search finds them) and return
    the data the renderer reads, {key: compact}. The key is the section's place,
    as for trees."""
    from .sanitize import esc
    reg = {}
    for owner, secs in _all_sections(b, nodes):
        for i, s in enumerate(secs or []):
            if not (getattr(s, "cards", None) or getattr(s, "quiz", None)):
                continue
            c = compact(s)
            if not c:
                continue
            key = f"{owner}-{i}"
            if c["k"] == "c":
                words = " · ".join(f"{x['f']} {x['b']}" for x in c["n"])
            else:
                words = " · ".join(" ".join([x["q"], *x["c"], x.get("x", "")]).strip() for x in c["n"])
            s.t = (s.t or "") + (f'<span class="ast-slot" data-ast="{key}" hidden>{esc(words)}</span>')
            reg[key] = c
    return reg


def compact(sec) -> dict | None:
    """The form the page keeps (and edit mode changes whole): {k: 'c'|'q', lab,
    …, n: [...]} — see from_compact for the way back."""
    if getattr(sec, "cards", None) and sec.cards.get("cards"):
        c = sec.cards
        return {"k": "c", "lab": c.get("label") or "", "sh": bool(c.get("shuffle")),
                "n": [{"i": x["id"], "f": x["front"], "b": x["back"]} for x in c["cards"]]}
    if getattr(sec, "quiz", None) and sec.quiz.get("questions"):
        n = []
        for x in sec.quiz["questions"]:
            o = {"i": x["id"], "q": x["q"], "c": list(x["choices"]), "a": x["answer"]}
            if x.get("explain"):
                o["x"] = x["explain"]
            n.append(o)
        return {"k": "q", "lab": sec.quiz.get("label") or "", "n": n}
    return None


def from_compact(v: dict) -> tuple[str, dict]:
    """The page's list → ("cards" | "quiz", the stored form). Raises BriefError
    when the shape is not one a section may carry."""
    from .sanitize import plain_text
    if not isinstance(v, dict) or v.get("k") not in ("c", "q") or not isinstance(v.get("n"), list):
        raise _err("study: not a list of cards or questions")
    if v["k"] == "c":
        out = {"cards": [{"id": x.get("i") or "", "front": plain_text(x.get("f") or "").strip(),
                          "back": plain_text(x.get("b") or "").strip()} for x in v["n"]]}
        for c in out["cards"]:
            if not c["id"]:
                del c["id"]
        if v.get("lab"):
            out["label"] = plain_text(v["lab"]).strip()
        if v.get("sh"):
            out["shuffle"] = True
        check_cards(out, "study")
        return "cards", out
    qs = []
    for x in v["n"]:
        q = {"id": x.get("i") or "", "q": plain_text(x.get("q") or "").strip(),
             "choices": [plain_text(c).strip() for c in x.get("c") or []], "answer": x.get("a")}
        if not q["id"]:
            del q["id"]
        if x.get("x"):
            q["explain"] = plain_text(x["x"]).strip()
        qs.append(q)
    out = {"questions": qs}
    if v.get("lab"):
        out["label"] = plain_text(v["lab"]).strip()
    check_quiz(out, "study")
    return "quiz", out


def study_block(reg: dict, hl_key: str = "") -> str:
    """The data and the renderer. Always there, with or without a section that
    uses it: manual edit mode can add one to any page (an empty registry draws
    nothing). `hl_key` is the page's own notes key (`alto-hl-{tid}`, which a
    share re-stamps like every other copy); progress lives under it + '-st'."""
    data = js_json(reg, separators=(",", ":"))
    return (f'<script id="alto-st-data">window._ALTO_ST={data};</script>\n'
            + STUDY_CSS + "\n" + STUDY_JS.replace("__ALTO_HL_KEY__", hl_key) + "\n")


def study_block_for(b, reg: dict) -> str:
    from .blocks import ID_PATTERNS
    return study_block(reg, ID_PATTERNS["hl_key"].format(tid=b.timeline_id))


STUDY_CSS = r"""<style id="alto-st-css">
  .ast{--ast-ok:#15803d;--ast-bad:#dc2626;--ast-okbg:rgba(22,163,74,.11);--ast-badbg:rgba(220,38,38,.09);--ast-acc:var(--accent,#7c6cf0);
    margin:18px 0 6px;border:1px solid var(--border);border-radius:16px;background:color-mix(in srgb,var(--surface) 55%,transparent);
    font-size:14px;line-height:1.5;color:var(--text);-webkit-user-select:text;user-select:text;}
  html.dark .ast{--ast-ok:#4ade80;--ast-bad:#f87171;--ast-okbg:rgba(74,222,128,.12);--ast-badbg:rgba(248,113,113,.11);}
  .ast-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:9px 12px 9px 14px;border-bottom:1px solid var(--border);}
  .ast-name{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);}
  .ast-meta{font-size:12px;color:var(--muted);opacity:.9;}
  .ast-sp{flex:1;}
  .ast-btn{font:inherit;font-size:12.5px;line-height:1;padding:7px 11px;border-radius:999px;border:1px solid var(--btn-border,var(--border));
    background:transparent;color:var(--text);cursor:pointer;-webkit-tap-highlight-color:transparent;white-space:nowrap;}
  .ast-btn:hover{background:var(--btn-hover-bg,rgba(0,0,0,.06));border-color:var(--btn-hover-border,var(--muted));}
  .ast-btn.on{background:color-mix(in srgb,var(--ast-acc) 16%,transparent);border-color:var(--ast-acc);}
  .ast-btn.pri{background:var(--ast-acc);border-color:var(--ast-acc);color:#fff;font-weight:600;}
  .ast-btn.pri:hover{filter:brightness(1.07);}
  .ast-btn[disabled]{opacity:.45;cursor:default;}
  .ast-btn.ok{border-color:color-mix(in srgb,var(--ast-ok) 55%,var(--border));color:var(--ast-ok);}
  .ast-btn.bad{border-color:color-mix(in srgb,var(--ast-bad) 55%,var(--border));color:var(--ast-bad);}
  .ast-btn.ok:hover{background:var(--ast-okbg);} .ast-btn.bad:hover{background:var(--ast-badbg);}
  .ast :focus-visible{outline:2px solid var(--ast-acc);outline-offset:2px;}
  .ast-body{padding:16px 16px 14px;}
  .ast-print{display:none;}
  /* flash cards */
  .asc-stage{display:flex;align-items:center;gap:10px;}
  .asc-nav{flex:none;width:38px;height:38px;border-radius:50%;padding:0;font-size:20px;line-height:1;display:flex;align-items:center;justify-content:center;
    border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;-webkit-tap-highlight-color:transparent;}
  .asc-nav:hover{border-color:var(--muted);} .asc-nav[disabled]{opacity:.35;cursor:default;}
  .asc-stage{max-width:680px;margin:0 auto;}
  .asc-slide{flex:1;min-width:0;perspective:1400px;-webkit-perspective:1400px;touch-action:pan-y;}
  .asc-slide.from-r{animation:ast-in-r .22s ease-out;} .asc-slide.from-l{animation:ast-in-l .22s ease-out;}
  @keyframes ast-in-r{from{opacity:0;transform:translateX(26px);}} @keyframes ast-in-l{from{opacity:0;transform:translateX(-26px);}}
  .asc-card{position:relative;cursor:pointer;outline-offset:3px;-webkit-tap-highlight-color:transparent;}
  .asc-in{display:grid;transition:transform .5s cubic-bezier(.3,.7,.2,1);transform-style:preserve-3d;-webkit-transform-style:preserve-3d;}
  .asc-card.nt .asc-in{transition:none;}
  .asc-card.flip .asc-in{transform:rotateY(180deg);}
  .asc-face{position:relative;grid-area:1/1;min-height:190px;box-sizing:border-box;padding:30px 26px 34px;border-radius:14px;border:1px solid var(--border);
    background:var(--card-glass-bg,var(--surface));box-shadow:0 6px 20px var(--node-rest-shadow,rgba(0,0,0,.08));
    display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;
    backface-visibility:hidden;-webkit-backface-visibility:hidden;}
  .asc-back{transform:rotateY(180deg);background:color-mix(in srgb,var(--ast-acc) 9%,var(--card-glass-bg,var(--surface)));}
  .asc-side{position:absolute;top:10px;left:14px;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);}
  .asc-tx{font-size:19px;line-height:1.45;font-weight:600;white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%;}
  .asc-back .asc-tx{font-weight:500;font-size:17px;}
  .asc-hint{position:absolute;bottom:9px;left:0;right:0;text-align:center;font-size:11px;color:var(--muted);opacity:.8;}
  .asc-mark{position:absolute;top:9px;right:12px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;}
  .asc-mark.k{color:var(--ast-ok);} .asc-mark.l{color:#d97706;} html.dark .asc-mark.l{color:#fbbf24;}
  .asc-row{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;margin-top:14px;}
  .asc-count{font-size:13px;color:var(--muted);min-width:70px;text-align:center;font-variant-numeric:tabular-nums;}
  .asc-prog{display:flex;height:6px;border-radius:99px;overflow:hidden;background:color-mix(in srgb,var(--text) 10%,transparent);margin-top:14px;}
  .asc-prog i{display:block;height:100%;transition:width .3s;} .asc-prog .k{background:var(--ast-ok);} .asc-prog .l{background:#f59e0b;}
  .asc-empty{padding:34px 12px;text-align:center;color:var(--muted);}
  .asc-empty b{display:block;color:var(--text);font-size:16px;margin-bottom:6px;}
  .asc-empty .ast-btn{margin:10px 4px 0;}
  @media (prefers-reduced-motion:reduce){.asc-in{transition:none;}.asc-slide.from-r,.asc-slide.from-l{animation:none;}}
  /* quiz */
  .asq-sum{font-size:12.5px;color:var(--muted);}
  .asq-sum b{color:var(--text);font-weight:650;}
  .asq-q,.asq-res,.asq-foot{max-width:820px;}
  .asq-q{margin:0 0 18px;padding:0;border:0;min-width:0;}
  .asq-q:last-of-type{margin-bottom:12px;}
  .asq-qh{display:flex;gap:10px;align-items:flex-start;margin:0 0 8px;padding:0;float:none;width:100%;font-size:15.5px;font-weight:600;line-height:1.5;}
  .asq-n{flex:none;min-width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:700;
    border:1px solid var(--border);color:var(--muted);margin-top:-1px;}
  .asq-qt{flex:1;white-space:pre-wrap;overflow-wrap:anywhere;}
  .asq-flag{flex:none;font-size:11px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;padding:3px 9px;border-radius:99px;margin-top:1px;}
  .asq-q.right .asq-flag{color:var(--ast-ok);background:var(--ast-okbg);} .asq-q.wrong .asq-flag{color:var(--ast-bad);background:var(--ast-badbg);}
  .asq-q.right .asq-n{border-color:var(--ast-ok);color:var(--ast-ok);} .asq-q.wrong .asq-n{border-color:var(--ast-bad);color:var(--ast-bad);}
  .asq-multi{margin:-4px 0 8px 36px;font-size:12px;color:var(--muted);}
  .asq-ch{display:flex;gap:10px;align-items:flex-start;margin:0 0 6px 36px;padding:9px 12px;border-radius:11px;border:1px solid var(--border);
    background:color-mix(in srgb,var(--surface) 70%,transparent);cursor:pointer;-webkit-tap-highlight-color:transparent;}
  .asq-ch:hover{border-color:var(--muted);}
  .asq-ch input{flex:none;margin:3px 0 0;accent-color:var(--ast-acc);width:16px;height:16px;}
  .asq-ch.pick{border-color:var(--ast-acc);background:color-mix(in srgb,var(--ast-acc) 10%,transparent);}
  .asq-ch .asq-tx{flex:1;white-space:pre-wrap;overflow-wrap:anywhere;}
  .asq-ch.done{cursor:default;} .asq-ch.done:hover{border-color:var(--border);}
  .asq-ch.pick.done{border-color:var(--ast-acc);}
  .asq-ch.ok{border-color:var(--ast-ok);background:var(--ast-okbg);} .asq-ch.bad{border-color:var(--ast-bad);background:var(--ast-badbg);}
  .asq-tag{flex:none;font-size:10.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;margin-top:2px;}
  .asq-ch.ok .asq-tag{color:var(--ast-ok);} .asq-ch.bad .asq-tag{color:var(--ast-bad);}
  .asq-ex{margin:8px 0 0 36px;padding:9px 13px;border-left:3px solid var(--ast-acc);border-radius:0 9px 9px 0;font-size:13.5px;line-height:1.55;
    background:color-mix(in srgb,var(--ast-acc) 7%,transparent);white-space:pre-wrap;overflow-wrap:anywhere;}
  .asq-ex b{display:block;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:2px;}
  .asq-foot{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:6px;}
  .asq-opt{display:flex;align-items:center;gap:7px;font-size:12.5px;color:var(--muted);cursor:pointer;}
  .asq-opt input{accent-color:var(--ast-acc);}
  .asq-left{font-size:12.5px;color:var(--muted);}
  .asq-res{margin:0 0 18px;padding:14px 16px;border-radius:14px;border:1px solid var(--border);background:color-mix(in srgb,var(--ast-acc) 8%,transparent);}
  .asq-score{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;}
  .asq-score b{font-size:30px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums;}
  .asq-score span{font-size:16px;color:var(--muted);}
  .asq-score em{font-style:normal;font-size:13px;color:var(--muted);}
  .asq-gauge{height:7px;border-radius:99px;margin:10px 0 4px;background:color-mix(in srgb,var(--text) 11%,transparent);overflow:hidden;}
  .asq-gauge i{display:block;height:100%;background:var(--ast-ok);border-radius:99px;}
  .asq-note{margin:6px 0 0;font-size:12.5px;color:var(--muted);}
  .asq-acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;}
  html.mobile .ast{margin-left:-4px;margin-right:-4px;}
  html.mobile .ast-body{padding:12px 10px 12px;}
  html.mobile .asc-nav{width:28px;height:28px;font-size:17px;} html.mobile .asc-stage{gap:4px;}
  html.mobile .asc-face{min-height:170px;padding:30px 16px 34px;} html.mobile .asc-tx{font-size:17px;}
  html.mobile .asq-ch,html.mobile .asq-ex{margin-left:0;} html.mobile .asq-multi{margin-left:0;}
  html.mobile .asq-ch{padding:11px 12px;}
  @media print{
    .ast{border:0;background:none;margin:12px 0;}
    .ast-live{display:none !important;} .ast-print{display:block !important;}
    .ast-bar{border:0;padding:0 0 6px;} .ast-bar .ast-btn,.ast-bar .ast-sp{display:none;}
    .ast-pi{margin:0 0 9px;break-inside:avoid;page-break-inside:avoid;font-size:13px;}
    .ast-pi b{font-weight:650;} .ast-pi div{margin:2px 0 0 18px;} .ast-pk{margin-top:14px;padding-top:8px;border-top:1px solid #999;}
  }
</style>"""


STUDY_JS = r"""<script id="alto-st">
(function(){
  var D = window._ALTO_ST || {}, KEY = '__ALTO_HL_KEY__-st', LET = 'ABCDEFGH';
  function el(tag, cls, txt){ var e = document.createElement(tag); if(cls) e.className = cls; if(txt != null) e.textContent = txt; return e; }
  function btn(cls, txt, fn){ var b = el('button', 'ast-btn ' + cls, txt); b.type = 'button'; if(fn) b.onclick = fn; return b; }
  function shuf(a){ a = a.slice(); for(var i = a.length - 1; i > 0; i--){ var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  function pct(s, n){ return n ? Math.round(100 * s / n) : 0; }

  /* progress: {v:1, s:{<section key>:{m, k:{<card id>:[1 know | 2 learning | 0 cleared, t]}, b:{s,n,t} best, l:{s,n,t,bl} last, a:attempts}}}
     kept in this browser; alto-cloud.js merges it with the account's copy (newest wins per card / best by score / last by time). */
  function load(){ try{ var o = JSON.parse(localStorage.getItem(KEY) || 'null'); if(o && o.s && typeof o.s === 'object') return o; }catch(e){} return {v:1, s:{}}; }
  function rec(key){ return load().s[key] || {}; }
  function upd(key, fn){ var o = load(), r = o.s[key] || (o.s[key] = {}); fn(r); r.m = Date.now(); try{ localStorage.setItem(KEY, JSON.stringify(o)); }catch(e){} }

  function head(box, name, meta){
    var bar = el('div', 'ast-bar'); bar.appendChild(el('span', 'ast-name', name));
    var m = el('span', 'ast-meta', meta); bar.appendChild(m); bar.appendChild(el('span', 'ast-sp')); box.appendChild(bar);
    return {bar: bar, meta: m};
  }

  /* ───────────────────────── flash cards ───────────────────────── */
  function cards(key, S){
    var box = el('div', 'ast ast-cards'); box.setAttribute('data-ast-key', key);
    var live = el('div', 'ast-live'); box.appendChild(live);
    var byId = {}, ids = S.n.map(function(c){ byId[c.i] = c; return c.i; });
    var order = S.sh ? shuf(ids) : ids.slice(), pos = 0, only = false, shuffled = !!S.sh, dir = '';
    var h = head(live, S.lab || 'Flash cards', '');
    var bShuf = btn('', 'Shuffle'), bOnly = btn('', 'Only still learning'), bReset = btn('', 'Reset');
    bShuf.title = 'Mix the cards up (press again for the original order)'; bReset.title = 'Clear every “Know it” / “Still learning” mark';
    h.bar.appendChild(bShuf); h.bar.appendChild(bOnly); h.bar.appendChild(bReset);
    var body = el('div', 'ast-body'); live.appendChild(body);
    var stage = el('div', 'asc-stage'), prev = el('button', 'asc-nav', '‹'), next = el('button', 'asc-nav', '›');
    prev.type = next.type = 'button'; prev.setAttribute('aria-label', 'Previous card'); next.setAttribute('aria-label', 'Next card');
    var slide = el('div', 'asc-slide'), card = el('div', 'asc-card'), inner = el('div', 'asc-in');
    card.tabIndex = 0; card.setAttribute('role', 'button'); card.setAttribute('aria-label', 'Flash card. Press Space to flip.');
    var fr = el('div', 'asc-face asc-front'), bk = el('div', 'asc-face asc-back');
    var frS = el('span', 'asc-side', 'Front'), bkS = el('span', 'asc-side', 'Back'), frT = el('div', 'asc-tx'), bkT = el('div', 'asc-tx');
    var hint = el('span', 'asc-hint', 'Click or press Space to flip · ← → to move');
    fr.appendChild(frS); fr.appendChild(frT); fr.appendChild(hint); bk.appendChild(bkS); bk.appendChild(bkT);
    inner.appendChild(fr); inner.appendChild(bk); card.appendChild(inner); slide.appendChild(card);
    stage.appendChild(prev); stage.appendChild(slide); stage.appendChild(next); body.appendChild(stage);
    var row = el('div', 'asc-row'), bL = btn('bad', '✗ Still learning'), bK = btn('ok', '✓ Know it'), cnt = el('span', 'asc-count');
    row.appendChild(bL); row.appendChild(cnt); row.appendChild(bK); body.appendChild(row);
    var prog = el('div', 'asc-prog'), pk = el('i', 'k'), pl = el('i', 'l'); prog.appendChild(pk); prog.appendChild(pl); body.appendChild(prog);
    var empty = el('div', 'asc-empty'); empty.hidden = true; body.appendChild(empty);

    function marks(){ return rec(key).k || {}; }
    function st(id){ var m = marks()[id]; return m ? m[0] : 0; }
    function list(){ if(!only) return order; var out = order.filter(function(i){ return st(i) !== 1; }); return out; }
    function stats(){ var k = 0, l = 0; ids.forEach(function(i){ var s = st(i); if(s === 1) k++; else if(s === 2) l++; }); return {k: k, l: l, n: ids.length - k - l}; }
    function paint(flipNow){
      var L = list(), s = stats();
      h.meta.textContent = ids.length + (ids.length === 1 ? ' card' : ' cards') + ' · ' + s.k + ' known · ' + s.l + ' still learning';
      bShuf.classList.toggle('on', shuffled); bOnly.classList.toggle('on', only);
      bOnly.textContent = 'Only still learning (' + (ids.length - s.k) + ')';
      pk.style.width = (100 * s.k / ids.length) + '%'; pl.style.width = (100 * s.l / ids.length) + '%';
      var none = !L.length; stage.hidden = row.hidden = none; empty.hidden = !none;
      if(none){
        empty.innerHTML = ''; empty.appendChild(el('b', '', 'You know every card.'));
        empty.appendChild(document.createTextNode('Nothing is left marked “still learning”.')); empty.appendChild(document.createElement('br'));
        var a = btn('pri', 'Show all cards', function(){ only = false; pos = 0; paint(); }), b = btn('', 'Reset marks', reset);
        empty.appendChild(a); empty.appendChild(b); return;
      }
      if(pos >= L.length) pos = L.length - 1; if(pos < 0) pos = 0;
      var c = byId[L[pos]], was = card.classList.contains('flip');
      card.classList.add('nt'); card.classList.remove('flip');
      frT.textContent = c.f; bkT.textContent = c.b;
      var ms = st(c.i); [fr, bk].forEach(function(f){ var m = f.querySelector('.asc-mark'); if(m) m.remove(); });
      if(ms){ var mm = el('span', 'asc-mark ' + (ms === 1 ? 'k' : 'l'), ms === 1 ? '✓ Known' : 'Still learning'); bk.appendChild(mm); }
      void card.offsetWidth; card.classList.remove('nt');
      if(dir){ slide.classList.remove('from-r', 'from-l'); void slide.offsetWidth; slide.classList.add(dir === 'n' ? 'from-r' : 'from-l'); dir = ''; }
      cnt.textContent = (pos + 1) + ' / ' + L.length;
      prev.disabled = pos <= 0; next.disabled = pos >= L.length - 1;
      bL.classList.toggle('on', ms === 2); bK.classList.toggle('on', ms === 1);
    }
    function flip(){ card.classList.toggle('flip'); }
    function back(){ try{ card.focus({preventScroll:true}); }catch(e){} }      // Space flips the next card, not the button just pressed
    function go(d){ var L = list(); var np = pos + d; if(np < 0 || np >= L.length) return; pos = np; dir = d > 0 ? 'n' : 'p'; paint(); back(); }
    function mark(state){
      var L = list(), id = L[pos]; if(!id) return;
      upd(key, function(r){ r.k = r.k || {}; r.k[id] = [state, Date.now()]; });
      var wasLast = pos >= L.length - 1;
      if(only && state === 1){ paint(); back(); return; }                                  // it leaves the pile; the next card slides into place
      if(!wasLast){ pos++; dir = 'n'; } paint(); back();
    }
    function reset(){
      var m = marks(), t = Date.now();
      upd(key, function(r){ r.k = r.k || {}; Object.keys(m).forEach(function(i){ r.k[i] = [0, t]; }); });
      only = false; pos = 0; paint();
    }
    prev.onclick = function(){ go(-1); }; next.onclick = function(){ go(1); };
    bL.onclick = function(){ mark(2); }; bK.onclick = function(){ mark(1); };
    bShuf.onclick = function(){ shuffled = !shuffled; var cur = list()[pos]; order = shuffled ? shuf(ids) : ids.slice(); var L = list(); pos = Math.max(0, L.indexOf(cur)); if(shuffled) pos = 0; paint(); };
    bOnly.onclick = function(){ only = !only; pos = 0; paint(); };
    bReset.onclick = function(){ if(Object.keys(marks()).some(function(i){ return st(i); })) reset(); };
    card.addEventListener('click', function(e){ if(card._sw){ card._sw = 0; return; } if(window.getSelection && String(window.getSelection()).trim()) return; flip(); });
    // swipe (phones): left = next, right = previous; a plain tap flips
    var x0 = null, y0 = 0;
    slide.addEventListener('pointerdown', function(e){ if(e.pointerType === 'mouse') return; x0 = e.clientX; y0 = e.clientY; });
    slide.addEventListener('pointerup', function(e){
      if(x0 == null) return; var dx = e.clientX - x0, dy = e.clientY - y0; x0 = null;
      if(Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.4){ card._sw = 1; setTimeout(function(){ card._sw = 0; }, 100); go(dx < 0 ? 1 : -1); }
    });
    slide.addEventListener('pointercancel', function(){ x0 = null; });
    // keys: only while the pointer is over the cards or focus is inside them
    var hot = false; box.addEventListener('mouseenter', function(){ hot = true; }); box.addEventListener('mouseleave', function(){ hot = false; });
    function keys(e){
      if(!document.contains(box)){ document.removeEventListener('keydown', keys, true); return; }
      if(e.altKey || e.ctrlKey || e.metaKey) return;
      var a = document.activeElement, inside = box.contains(a);
      if(a && !inside && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) || (a && a.isContentEditable && !inside)) return;
      if(!inside && !hot) return;
      if(live.offsetParent === null || stage.hidden) return;
      if(e.key === 'ArrowRight'){ go(1); }
      else if(e.key === 'ArrowLeft'){ go(-1); }
      else if(e.key === ' ' || e.key === 'Spacebar'){ if(a && a !== card && a.closest && a.closest('button')) return; flip(); }
      else return;
      e.preventDefault(); e.stopPropagation();
    }
    document.addEventListener('keydown', keys, true);
    box._sync = function(){ paint(); };
    paint();
    box.appendChild(printCards(S));
    return box;
  }
  function printCards(S){
    var p = el('div', 'ast-print'); p.appendChild(el('div', 'ast-name', S.lab || 'Flash cards'));
    S.n.forEach(function(c, i){ var d = el('div', 'ast-pi'); d.appendChild(el('b', '', (i + 1) + '. ' + c.f)); d.appendChild(el('div', '', c.b)); p.appendChild(d); });
    return p;
  }

  /* ───────────────────────── quiz ───────────────────────── */
  function quiz(key, S){
    var box = el('div', 'ast ast-quiz'); box.setAttribute('data-ast-key', key);
    var live = el('div', 'ast-live'); box.appendChild(live);
    var Q = S.n, picks = {}, graded = null;          // graded: {blind, rev, res:{id:bool}, s}
    var h = head(live, S.lab || 'Quiz', Q.length + (Q.length === 1 ? ' question' : ' questions'));
    var sum = el('span', 'asq-sum'); h.bar.appendChild(sum);
    var body = el('div', 'ast-body'); live.appendChild(body);
    function multi(q){ return Array.isArray(q.a); }
    function ans(q){ return multi(q) ? q.a.slice() : [q.a]; }
    function right(q){ var p = (picks[q.i] || []).slice().sort(), a = ans(q).sort(); return p.length === a.length && p.every(function(x, i){ return x === a[i]; }); }
    function summary(){
      var r = rec(key); sum.innerHTML = '';
      if(!r.a){ sum.textContent = 'Not taken yet'; return; }
      function part(lbl, o){ if(!o) return; var s = el('span'); s.appendChild(document.createTextNode(lbl + ' ')); s.appendChild(el('b', '', pct(o.s, o.n) + '%')); s.appendChild(document.createTextNode(' (' + o.s + '/' + o.n + ')')); sum.appendChild(s); }
      part('Best', r.b); if(r.b) sum.appendChild(document.createTextNode(' · ')); part('Last', r.l);
      sum.appendChild(document.createTextNode(' · ' + r.a + (r.a === 1 ? ' attempt' : ' attempts')));
      if(r.l && r.l.bl) sum.appendChild(document.createTextNode(' (last without answers)'));
    }
    function draw(){
      body.innerHTML = '';
      var shown = graded && (!graded.blind || graded.rev);
      if(graded) body.appendChild(result());
      Q.forEach(function(q, qi){
        var f = el('fieldset', 'asq-q' + (graded ? (graded.res[q.i] ? ' right' : ' wrong') : ''));
        var lg = el('legend', 'asq-qh'); lg.appendChild(el('span', 'asq-n', String(qi + 1))); lg.appendChild(el('span', 'asq-qt', q.q));
        if(graded) lg.appendChild(el('span', 'asq-flag', graded.res[q.i] ? '✓ Right' : '✗ Wrong'));
        f.appendChild(lg);
        if(multi(q)) f.appendChild(el('div', 'asq-multi', 'Select all that apply'));
        q.c.forEach(function(c, ci){
          var on = (picks[q.i] || []).indexOf(ci) >= 0, isA = ans(q).indexOf(ci) >= 0;
          var lb = el('label', 'asq-ch' + (on ? ' pick' : '') + (graded ? ' done' : ''));
          var inp = el('input'); inp.type = multi(q) ? 'checkbox' : 'radio'; inp.name = key + '-' + q.i; inp.checked = on; inp.disabled = !!graded;
          inp.setAttribute('data-q', q.i); inp.setAttribute('data-c', ci);
          lb.appendChild(inp); lb.appendChild(el('span', 'asq-tx', c));
          if(shown){
            if(isA){ lb.classList.add('ok'); lb.appendChild(el('span', 'asq-tag', on ? '✓ Correct' : (multi(q) ? 'Correct — missed' : 'Correct answer'))); }
            else if(on){ lb.classList.add('bad'); lb.appendChild(el('span', 'asq-tag', '✗ Not this one')); }
          }
          f.appendChild(lb);
        });
        if(shown && q.x){ var ex = el('div', 'asq-ex'); ex.appendChild(el('b', '', 'Why')); ex.appendChild(document.createTextNode(q.x)); f.appendChild(ex); }
        body.appendChild(f);
      });
      if(!graded){
        var ft = el('div', 'asq-foot'), left = el('span', 'asq-left'), go = btn('pri', 'Submit answers', submit);
        var ob = el('label', 'asq-opt'), oc = el('input'); oc.type = 'checkbox'; oc.checked = !!draw.blind; oc.onchange = function(){ draw.blind = oc.checked; };
        ob.appendChild(oc); ob.appendChild(document.createTextNode('Grade without showing the answers')); ob.title = 'You will see only right or wrong for each question, so you can keep trying';
        ft.appendChild(go); ft.appendChild(left); ft.appendChild(ob); body.appendChild(ft);
        var upL = function(){ var n = Q.filter(function(q){ return (picks[q.i] || []).length; }).length; left.textContent = n === Q.length ? 'All answered' : n + ' of ' + Q.length + ' answered'; };
        body._up = upL; upL();
      }
    }
    function result(){
      var n = Q.length, s = graded.s, p = pct(s, n), r = el('div', 'asq-res');
      var sc = el('div', 'asq-score'); sc.appendChild(el('b', '', s + ' / ' + n)); sc.appendChild(el('span', '', p + '%'));
      sc.appendChild(el('em', '', p === 100 ? 'Perfect.' : p >= 80 ? 'Strong.' : p >= 60 ? 'Getting there.' : 'Worth another pass.')); r.appendChild(sc);
      var g = el('div', 'asq-gauge'), gi = el('i'); gi.style.width = p + '%'; g.appendChild(gi); r.appendChild(g);
      if(graded.blind && !graded.rev) r.appendChild(el('div', 'asq-note', 'Answers are hidden. Questions marked wrong need another look; retake to try again, or show the answers when you are ready.'));
      var acts = el('div', 'asq-acts');
      acts.appendChild(btn('pri', graded.blind && !graded.rev ? 'Retake without answers' : 'Retake', function(){ retake(graded.blind && !graded.rev); }));
      if(graded.blind && !graded.rev) acts.appendChild(btn('', 'Retake', function(){ retake(false); }));
      else acts.appendChild(btn('', 'Retake without answers', function(){ retake(true); }));
      if(graded.blind && !graded.rev) acts.appendChild(btn('', 'Show the answers', function(){ graded.rev = true; draw(); }));
      r.appendChild(acts); return r;
    }
    function submit(){
      var res = {}, s = 0; Q.forEach(function(q){ var ok = right(q); res[q.i] = ok; if(ok) s++; });
      var blind = !!draw.blind; graded = {blind: blind, rev: false, res: res, s: s};
      upd(key, function(r){ var t = Date.now(); r.l = {s: s, n: Q.length, t: t, bl: blind ? 1 : 0}; r.a = (r.a || 0) + 1;
        if(!r.b || s * r.b.n > r.b.s * Q.length) r.b = {s: s, n: Q.length, t: t}; });
      summary(); draw(); scrollTo_(box);
    }
    function retake(blind){ picks = {}; graded = null; draw.blind = blind; draw(); scrollTo_(box); }
    function scrollTo_(e){ try{ var r = e.getBoundingClientRect(); if(r.top < 0 || r.top > window.innerHeight * .6) e.scrollIntoView({block:'start', behavior:'smooth'}); }catch(x){} }
    body.addEventListener('change', function(e){
      var i = e.target; if(!i || !i.getAttribute || graded) return; var q = i.getAttribute('data-q'); if(q == null) return;
      var ci = +i.getAttribute('data-c'), cur = picks[q] || [];
      if(i.type === 'radio') cur = [ci]; else { cur = cur.filter(function(x){ return x !== ci; }); if(i.checked) cur.push(ci); }
      picks[q] = cur;
      Array.prototype.forEach.call(body.querySelectorAll('input[data-q="' + q + '"]'), function(x){ x.parentNode.classList.toggle('pick', x.checked); });
      if(body._up) body._up();
    });
    box._sync = function(){ summary(); };
    summary(); draw();
    box.appendChild(printQuiz(S));
    return box;
  }
  function printQuiz(S){
    var p = el('div', 'ast-print'); p.appendChild(el('div', 'ast-name', S.lab || 'Quiz'));
    S.n.forEach(function(q, i){
      var d = el('div', 'ast-pi'), m = Array.isArray(q.a); d.appendChild(el('b', '', (i + 1) + '. ' + q.q + (m && !/all that apply/i.test(q.q) ? ' (select all that apply)' : '')));
      q.c.forEach(function(c, ci){ d.appendChild(el('div', '', LET[ci] + '.  ' + c)); }); p.appendChild(d);
    });
    var k = el('div', 'ast-pk'); k.appendChild(el('b', '', 'Answer key'));
    S.n.forEach(function(q, i){
      var a = (Array.isArray(q.a) ? q.a : [q.a]).map(function(x){ return LET[x]; }).join(', ');
      k.appendChild(el('div', 'ast-pi', (i + 1) + '. ' + a + (q.x ? ' — ' + q.x : '')));
    });
    p.appendChild(k); return p;
  }

  /* ───────────────────────── placing them ───────────────────────── */
  function render(slot){
    var key = slot.getAttribute('data-ast'), S = D[key];
    if(!S || !S.n || !S.n.length){ slot.removeAttribute('data-ast'); return; }
    var box = S.k === 'q' ? quiz(key, S) : cards(key, S);
    // after the paragraph that held the slot, inside the section; that paragraph
    // goes when it held nothing else (edit mode keeps its key mark there)
    var p = slot.parentNode, host = p && p.tagName === 'P' ? p : null;
    if(host && host.parentNode){
      host.parentNode.insertBefore(box, host.nextSibling); slot.parentNode.removeChild(slot);
      if(!host.textContent.trim() && !host.querySelector('img,svg,.aed-k')) host.parentNode.removeChild(host);
    } else slot.parentNode.replaceChild(box, slot);
  }
  function scan(){ var s = document.querySelectorAll('.ast-slot[data-ast]'); for(var i = 0; i < s.length; i++){ try{ render(s[i]); }catch(e){ if(window.console) console.warn('alto study', e); } } }
  window._altoStudy = scan;
  function syncAll(){ Array.prototype.forEach.call(document.querySelectorAll('.ast'), function(b){ try{ if(b._sync) b._sync(); }catch(e){} }); }
  window.addEventListener('alto-study-sync', syncAll);
  window.addEventListener('storage', function(e){ if(e.key === KEY) syncAll(); });
  var queued = false;
  function soon(){ if(queued) return; queued = true; Promise.resolve().then(function(){ queued = false; scan(); }); }
  function watch(){
    var mo = new MutationObserver(function(ms){
      for(var i = 0; i < ms.length; i++){ var a = ms[i].addedNodes;
        for(var j = 0; j < a.length; j++){ var x = a[j]; if(x.nodeType === 1 && (x.classList.contains('ast-slot') || x.querySelector('.ast-slot'))){ soon(); return; } } }
    });
    var dp = document.getElementById('detail-page') || document.getElementById('detail-content');
    if(dp) mo.observe(dp, {childList:true, subtree:true});
    mo.observe(document.body, {childList:true});
    scan();
  }
  if(document.body) watch(); else document.addEventListener('DOMContentLoaded', watch);
})();
</script>"""
