"""Generates docs/bass-api.md from real runs of the action layer on the simulated API.

    ~/.local/share/alto/venv-studio/bin/python tests/bass_apidoc.py --write      # refresh the doc (own temp store + private HOME; any other ALTO_STORE is refused)

tests/test_bass_actions.py runs the same samples again and checks the doc still has the same shapes, so the contract the
browser UI is built against cannot drift from the code. Mock only: no network, no key, a temp local store.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DOC = ROOT / "docs" / "bass-api.md"
SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))

MATERIALS = [{"name": "Contracts notes.pdf", "kind": "notes",
              "text": "Offer and acceptance. The mirror image rule. Consideration and promissory estoppel. "
                      "Statute of frauds. Remedies: expectation, reliance, restitution."}]
CHIPS = {"title": "Contracts", "acts": [{"label": "Formation"}, {"label": "Defences"}, {"label": "Remedies"}],
         "entities": [{"id": "offer", "name": "Offer"}, {"id": "consideration", "name": "Consideration"}],
         "fields": ["Case", "Rule"], "card_estimate": 6}


def make_env(store_dir, allowance=500):
    from alto.store.local import LocalStore
    from alto.bass import engine as E, mock_anthropic as M
    from alto.bass.actions import Actions
    from alto.bass.client import make_client
    from alto.bass.errors import Flags
    from alto.bass.ledger import Ledger, MemoryStore
    from alto.bass.tools import ToolBox

    class Env:
        pass
    e = Env()
    e.M = M
    e.mock = M.MockAnthropic()
    e.client = make_client("mock", mock=e.mock)
    e.ledger = Ledger(MemoryStore())
    e.ledger.grant_allowance("student", allowance)
    e.tools = ToolBox(LocalStore(Path(store_dir)))
    e.flags = Flags()
    e.engine = E.Engine(e.client, e.ledger, e.tools, flags=e.flags, sleep=lambda s: None)
    n = [0]

    def ids():
        n[0] += 1
        return f"act_{n[0]:04d}"
    e.acts = Actions(e.engine, e.ledger, ids=ids)
    return e


def build_scenario(M):
    return M.build("Contracts", SAMPLE["brief"], SAMPLE["nodes"], SAMPLE["connections"])


def samples(store_dir) -> list[dict]:
    """Ordered list of {key, title, note, request, response}. Each response is a real return value."""
    e = make_env(store_dir)
    M, acts, out = e.M, e.acts, []

    def run(key, title, note, request, uid="student", on_event=None):
        resp = acts.dispatch(uid, request, on_event=on_event)
        out.append({"key": key, "title": title, "note": note, "request": request, "response": resp})
        return resp

    run("balance", "balance", "The credits meter and the homepage balance line.", {"action": "balance", "args": {}})

    run("estimate_small", "estimate (small, no prompt)", "A quick edit: nothing to ask the student.",
        {"action": "estimate", "args": {"kind": "edit", "text": "Add a card about promissory estoppel."}})
    poor = make_env(store_dir, allowance=5)
    resp = poor.acts.dispatch("student", {"action": "estimate", "args": {"kind": "build", "materials": MATERIALS}})
    out.append({"key": "estimate_big", "title": "estimate (big, prompt, short of credits)",
                "note": "show_prompt is true above 20 credits; short_by > 0 means the student cannot afford it yet.",
                "request": {"action": "estimate", "args": {"kind": "build", "materials": MATERIALS}},
                "response": resp})

    e.mock.use(M.Scenario("propose", [M.Step(M.Reply([M.text("Here is my plan."), M.tool_use("propose_chips", CHIPS)]))]))
    run("propose", "propose (chips)", "The interview step. Nothing is written; the UI shows the chips as removable pills.",
        {"action": "propose", "args": {"materials": MATERIALS}})
    e.mock.use(M.Scenario("propose_q", [M.Step(M.say("Which course is this for, and which weeks should it cover?"))]))
    run("propose_question", "propose (a question instead)", "chips is null: show the message and let the student answer.",
        {"action": "propose", "args": {"materials": [{"name": "scrap.txt", "kind": "notes", "text": "week 3"}]}})

    run("build_consent", "build (consent missing)", "The UI must send consent:true only after the student ticks the "
        "closed-system statement.", {"action": "build", "args": {"chips": CHIPS, "materials": MATERIALS}})
    run("build_estimate", "build (estimate state)", "Above 20 credits the first call stops here, without calling the model. "
        "Show credits_text, then call again with accepted:true.",
        {"action": "build", "args": {"chips": CHIPS, "materials": MATERIALS, "consent": True}})
    e.mock.use(build_scenario(M))
    events = []
    run("build_ok", "build (ok, with progress events)", "events are also pushed one by one to the on_event callback / SSE "
        "stream while the build runs.",
        {"action": "build", "args": {"chips": CHIPS, "materials": MATERIALS, "consent": True, "accepted": True}},
        on_event=events.append)
    tid = out[-1]["response"]["timeline_id"]

    e.mock.use(M.Scenario("edit", [
        M.Step(M.say("ON_TOPIC")),
        M.Step(M.Reply([M.text("Updating that card."), M.tool_use("add_nodes", {"timeline_id": tid, "nodes": [
            dict(SAMPLE["nodes"][0], title="Offer (revised)")]})])),
        M.Step(M.say("Done: the card now reads \"Offer (revised)\"."))]))
    e.engine.cfg.actions_per_minute = 100
    run("edit_ok", "edit (ok)", "Free text goes through the off-topic gate, then the edit runs on the real tools.",
        {"action": "edit", "args": {"timeline_id": tid, "text": "Rename the first card to Offer (revised)."}})
    e.mock.use(M.off_topic_gate(on_topic=False))
    run("edit_off_topic", "edit (off topic)", "Costs the student nothing.",
        {"action": "edit", "args": {"timeline_id": tid, "text": "Write me a poem about cats."}})

    e.mock.use(M.refusal_scenario())
    run("refused", "propose (refused)", "The model's safety classifier declined. Nothing is charged.",
        {"action": "propose", "args": {"materials": MATERIALS}})

    e.mock.use(M.Scenario("err", [M.Step(M.say("never"))]))
    e.mock.inject(M.overloaded(times=99))
    run("error", "propose (error, retries exhausted)", "Alto or Anthropic side. Nothing is charged; offer Try again.",
        {"action": "propose", "args": {"materials": MATERIALS}})
    e.mock.faults.clear()

    e.engine.cfg.per_action_cap_mc = 20_000                # a turn whose worst case no longer fits is not started (about 17 credits a Sonnet turn)
    e.mock.use(build_scenario(M))
    run("capped", "build (capped, work saved)", "The per-action credit cap stopped it. work_saved is true: what was written stays.",
        {"action": "build", "args": {"chips": CHIPS, "materials": MATERIALS, "consent": True, "accepted": True}})
    e.engine.cfg.per_action_cap_mc = 300 * 1000

    e.mock.use(build_scenario(M))
    stopper = []

    def stop_after_first(ev):
        if ev["event"] == "progress" and not stopper:
            stopper.append(acts.dispatch("student", {"action": "stop", "args": {"action_id": ev["action_id"]}}))
    run("stopped", "build (stopped by the student)", "stop(action_id) takes effect at the next step boundary.",
        {"action": "build", "args": {"chips": CHIPS, "materials": MATERIALS, "consent": True, "accepted": True}},
        on_event=stop_after_first)
    out.append({"key": "stop", "title": "stop", "note": "Returns at once; the build's own result says stopped.",
                "request": {"action": "stop", "args": {"action_id": stopper[0]["stopping"]}}, "response": stopper[0]})

    broke = make_env(store_dir, allowance=0)
    broke.mock.use(build_scenario(M))
    out.append({"key": "no_credits", "title": "build (no credits)", "note": "Fails before any model call; nothing was written.",
                "request": {"action": "build", "args": {"chips": CHIPS, "materials": MATERIALS, "consent": True,
                                                        "accepted": True}},
                "response": broke.acts.dispatch("student", {"action": "build", "args": {
                    "chips": CHIPS, "materials": MATERIALS, "consent": True, "accepted": True}})})

    busy = make_env(store_dir)
    busy.engine.cfg.actions_per_minute = 1
    busy.mock.use(M.Scenario("b", [M.Step(M.say("ON_TOPIC")), M.Step(M.say("ok"))]))
    busy.acts.dispatch("student", {"action": "edit", "args": {"timeline_id": "t", "text": "hello"}})
    out.append({"key": "busy", "title": "edit (busy)", "note": "Too many actions in a minute for one account.",
                "request": {"action": "edit", "args": {"timeline_id": "t", "text": "hello again"}},
                "response": busy.acts.dispatch("student", {"action": "edit", "args": {"timeline_id": "t",
                                                                                      "text": "hello again"}})})

    from alto.bass.errors import POLICIES
    paused = make_env(store_dir)
    paused.flags.trip(POLICIES["auth"])
    out.append({"key": "paused", "title": "propose (paused)", "note": "Bass is switched off for everyone (kill switch / "
                "Anthropic balance empty). No model call; nobody is blamed.",
                "request": {"action": "propose", "args": {"materials": MATERIALS}},
                "response": paused.acts.dispatch("student", {"action": "propose", "args": {"materials": MATERIALS}})})

    run("bad_input", "bad input", "Any malformed request.", {"action": "build", "args": {"chips": {}, "materials": []}})
    return out


def shape(x):
    """The structure of a JSON value, with numbers/strings abstracted, for the doc-drift test."""
    ENUM = {"status", "code", "event", "step", "kind"}
    if isinstance(x, dict):
        return {k: (v if k in ENUM and isinstance(v, str) else shape(v)) for k, v in x.items()}
    if isinstance(x, list):
        uniq = {json.dumps(shape(v), sort_keys=True) for v in x}
        return sorted(uniq)
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, (int, float)):
        return "number"
    if isinstance(x, str):
        return "string"
    return None


def render(samp: list[dict]) -> str:
    from alto.bass import actions as A, config as P
    from alto.bass.errors import POLICIES

    def block(obj):
        return "```json\n" + json.dumps(obj, indent=2, ensure_ascii=False) + "\n```\n"
    s = ["# Bass API: the contract between the browser and the action layer\n",
         "Generated from real runs on the simulated API by `tests/bass_apidoc.py` (do not edit by hand; "
         "`tests/test_bass_actions.py` checks this file still matches the code). Mock only: no live call exists yet.\n",
         "## How it works\n",
         "The browser never talks to Claude. It sends ONE JSON object `{\"action\": ..., \"args\": {...}}` to the Bass "
         "endpoint (`Actions.dispatch(uid, request, on_event)` in `alto/bass/actions.py`) and gets ONE JSON object back. "
         "The only free text the student can type is the `edit` request, and it goes through the off-topic gate first.\n",
         "Actions: `balance`, `estimate`, `propose`, `build`, `edit`, `stop`. The user is the signed-in uid on the server "
         "side; the browser never sends it.\n",
         "### Every result has these keys\n",
         "| key | meaning |\n|---|---|\n"
         "| `ok` | true only for status `ok` |\n"
         "| `status` | one of the states below; the UI switches on this |\n"
         "| `code` | machine reason behind a non-ok status (null when ok) |\n"
         "| `message` | text to show. For `ok` it is the assistant's last words; otherwise a plain sentence that never blames the student |\n"
         "| `action_id` | id of this action (`stop` takes it); null if no action started |\n"
         "| `work_saved` | true if anything was written to the student's timeline (stopping never rolls it back) |\n"
         "| `credits` | `{spent, refunded, balance, label}` in credits (1 credit = 1 cent of real cost); null if no action ran |\n"
         "| `retryable` | the UI may offer Try again |\n"
         "| `events` | the progress events of this action, in order (also pushed live to `on_event`) |\n",
         "build and edit add `timeline_id`; build adds `cards: {done, total}`; propose adds `chips`; edit adds `changed`. "
         "Credits are plain numbers (2 decimals); `label` is the words to print (\"41 credits\"). Students never see tokens.\n",
         "### States (`status`)\n",
         "| status | when | UI |\n|---|---|---|\n"
         "| `ok` | done | show `message`; refresh the timeline |\n"
         "| `estimate` | `build` would cost more than %d credits and `accepted` was not sent | show `credits_text`, `have`, `short_by`; "
         "Continue calls `build` again with `accepted:true` |\n" % P.ESTIMATE_THRESHOLD_CREDITS +
         "| `no_credits` | balance too low (before or part-way) | show `message`; `work_saved` says if anything is kept |\n"
         "| `busy` | too many actions in a minute | Try again |\n"
         "| `paused` | Bass is switched off for everyone | show `message` |\n"
         "| `off_topic` | the edit text was not about the timeline | show `message`; nothing charged |\n"
         "| `refused` | the model declined | show `message`; nothing charged |\n"
         "| `capped` | per-action, daily or monthly credit limit | show `message`; work is saved |\n"
         "| `stopped` | the student pressed stop | work is saved |\n"
         "| `error` | anything else (see `code`) | show `message`; offer Try again if `retryable` |\n",
         "### Progress events\n",
         "`start` `{event, action_id, kind}` first; then `progress` after each step "
         "`{event, action_id, step, label, detail, ok, cards_done, cards_total, spent_credits}` where `step` is one of "
         "`setup consent chips cards links layout build look work` and `detail` is e.g. \"cards 4 of 6\" (empty otherwise; "
         "`cards_total` comes from the chips' `card_estimate`, null if unknown); last `result` `{event, action_id, status, message}`.\n",
         "### Codes\n",
         "| code | message |\n|---|---|\n" + "".join(f"| `{c}` | {p.user_message} |\n" for c, p in POLICIES.items()),
         "## Calls and states, with real responses\n"]
    for sm in samp:
        s.append(f"### {sm['title']}\n")
        s.append(sm["note"] + "\n")
        s.append("Request:\n" + block(sm["request"]))
        s.append("Response:\n" + block(sm["response"]))
    return "\n".join(s)


def build_doc() -> str:
    with tempfile.TemporaryDirectory() as d:
        return render(samples(d))


if __name__ == "__main__":
    # Outside pytest: only its own throw-away local store (any other ALTO_STORE is refused), under a private temp HOME / XDG_CONFIG_HOME,
    # so this Mac's real ~/.config/alto is not even reachable; update check off (alto/bass/isolate.py, incident 11 Nov).
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from alto.bass import isolate
    isolate.start("bass_apidoc", mock=True)
    for k in list(os.environ):
        if k == "ALTO_LIVE_ANTHROPIC" or "luke-alto" in (k + os.environ[k]).lower():
            sys.exit(f"refusing to run with {k} set")
        if k.startswith("ANTHROPIC_"):
            del os.environ[k]
    from alto.bass import net_guard
    net_guard.install()
    text = build_doc()
    if "--write" in sys.argv:
        DOC.parent.mkdir(exist_ok=True)
        DOC.write_text(text, encoding="utf-8")
        print("wrote", DOC, len(text))
    else:
        print(text)
