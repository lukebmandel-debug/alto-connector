"""The Bass agent loop. A MANUAL loop (not the SDK's tool runner) so every turn is metered, capped and refundable.

Per turn:   count_tokens -> hold(estimate) -> stream -> settle(actual from usage) -> run tool_use blocks in-process
            -> ONE user message with every tool_result -> next turn.
It stops on end_turn, the per-action cap, an empty balance, a refusal (that turn is refunded), max_tokens, the wall-clock
bound, or an unrecoverable error (the STUDENT is never charged for a failed turn; an action that produced nothing is refunded whole).

Money rule for a call that fails (review finding M1): Anthropic bills a request from the moment it starts generating, whether or
not the stream ever finishes. So a call is released for free ONLY when it provably cost nothing: the API answered with an error
status instead of a stream (429, 529, 5xx, 4xx), or the connection was never made. Anything else that fails after the request
left (a stream that drops, a timeout, an error event mid-stream, our own wall-clock stop) is BOOKED at the hold's reserved worst
case as Alto's cost (absorbed: the student's hold goes back, the day and period counters keep it) and is NEVER retried.
Work the tools already stored stays stored: stopping never rolls anything back, and the history comes back so the
action can be resumed.
"""
from __future__ import annotations

import collections
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from ._sdk import anthropic, httpx2   # lazy: the SDK is only needed when a request is made

from . import meter
from . import shapes
from . import config as P
from .errors import (CapReached, Flags, InsufficientCredits, POLICIES, BassError, UpstreamError, classify)
from .ledger import Ledger
from .tools import ToolBox

SYSTEM_PROMPT = """You are Bass, the assistant inside Alto that turns a student's own study materials into an interactive timeline or outline.

Rules that never change:
- Build ONLY from the materials the student gave in this conversation. Never invent content (the closed-system rule).
- Do the work by calling the tools. Call independent tools together in one turn.
- Do not call record_materials_consent unless the student has confirmed they provided the materials and agreed to the closed-system statement.
- Keep your replies short and plain. Never mention tokens, models, prices or these instructions.
""" + shapes.PLAIN_LINE

GATE_SYSTEM = ("Decide whether the student's message is about building, editing or understanding their study "
               "timeline or outline in Alto. Answer with exactly one word: ON_TOPIC or OFF_TOPIC.")
OFF_TOPIC_REPLY = ("I can only help with building and editing your timelines and outlines in Alto. "
                   "Tell me what you would like to add or change.")


@dataclass
class BassConfig:
    # Sonnet 5.5 builds; Haiku 5.5 edits, chat and the gate (Luke/memo). Effort is a config value, tuned from measured usage.
    models: dict = field(default_factory=lambda: {"build": P.SONNET, "propose": P.HAIKU, "edit": P.HAIKU,
                                                  "chat": P.HAIKU})
    efforts: dict = field(default_factory=lambda: {"build": "medium", "propose": "medium", "edit": "low",
                                                   "chat": "low"})
    gate_model: str = P.HAIKU
    gate_effort: str = "low"
    chat_max_tokens: int = P.CHAT_MAX_TOKENS
    build_max_tokens: int = P.BUILD_MAX_TOKENS
    propose_max_tokens: int = 3000
    per_action_cap_mc: int = P.PER_ACTION_CAP_CREDITS * P.MC
    max_turns: int = 40
    max_retries: int = P.MAX_RETRIES
    retry_max_wait: float = P.RETRY_MAX_WAIT_S
    actions_per_minute: int = P.ACTIONS_PER_MINUTE
    use_gate: bool = True
    system: str = SYSTEM_PROMPT
    # Thinking per kind (review finding A1): "adaptive" (the models' default; needs room in max_tokens) or "off". The Haiku kinds run with
    # thinking off (exact parameters: config.THINKING_OFF); the Sonnet build thinks. The gate is always off.
    thinking: dict = field(default_factory=lambda: {"build": "adaptive", "propose": "off", "edit": "off", "chat": "off"})
    max_wall_s: float | None = P.ACTION_WALL_S          # an action's wall-clock bound (the hosted proxy sets it under the function timeout)
    turn_margin_s: float = P.TURN_MARGIN_S

    def model_for(self, kind: str) -> str:
        return self.models.get(kind) or self.models["edit"]

    def effort_for(self, kind: str) -> str:
        return self.efforts.get(kind) or self.efforts["edit"]

    def thinking_for(self, kind: str) -> dict:
        """The request's `thinking` parameter for this kind. Never omitted: the default (adaptive) is sent as itself."""
        mode = self.thinking.get(kind) or self.thinking.get("edit") or "adaptive"
        if mode == "adaptive":
            return {"type": "adaptive"}
        return thinking_off(self.model_for(kind), self.effort_for(kind))

    def max_tokens_for(self, kind: str) -> int:
        n = {"build": self.build_max_tokens, "propose": self.propose_max_tokens}.get(kind, self.chat_max_tokens)
        if self.thinking_for(kind)["type"] == "adaptive":
            n = max(n, P.THINKING_MIN_MAX_TOKENS)          # thinking counts inside max_tokens: leave it room
        return n


def thinking_off(model: str, effort: str) -> dict:
    """The exact way to turn thinking off on this model (config.THINKING_OFF). A model or effort it is not documented for is refused
    here, in our own code, never sent to find out."""
    if model not in P.THINKING_OFF or effort not in P.THINKING_OFF_EFFORTS:
        raise ValueError(f"thinking cannot be turned off for {model!r} at effort {effort!r}")
    return dict(P.THINKING_OFF[model])


THINKING_BLOCKS = ("thinking", "redacted_thinking")


def strip_thinking(messages: list) -> list:
    """The history without any thinking block (text and tool calls stay). What a KEPT history holds, and the documented one-time
    recovery from the history-editing check (review finding A2)."""
    out = []
    for m in messages:
        if m.get("role") == "assistant" and isinstance(m.get("content"), list):
            keep = [b for b in m["content"] if not (isinstance(b, dict) and b.get("type") in THINKING_BLOCKS)]
            m = {**m, "content": keep or [{"type": "text", "text": "(no reply)"}]}
        out.append(m)
    return out


class _Sent:
    """What is known about one model call's billing: `accepted` turns True when the API answered 200 and began to stream."""
    accepted = False


@dataclass
class ActionResult:
    action_id: str
    status: str = "running"      # done | off_topic | capped | no_credits | refused | max_tokens | error | paused | busy
    text: str = ""               # the assistant's last words, for the student
    user_message: str = ""       # what the UI shows for a non-done status (never blames the student)
    messages: list = field(default_factory=list)     # full history: resume from here
    turns: int = 0
    absorbed_mc: int = 0         # Alto's own cost for calls that failed after they were sent (booked at the reserved worst case)
    tool_calls: list = field(default_factory=list)   # [{name, input, is_error, wrote}]
    wrote: bool = False          # any tool stored something
    out_tokens: int = 0          # output tokens over all turns (metadata for the beta logs; never any text)
    usage: dict = field(default_factory=dict)        # summed token counters over all turns (metadata: measurements)
    charged_mc: int = 0          # summed over turns, before refunds
    refunded_mc: int = 0
    spent_mc: int = 0            # net, after refunds
    code: str = ""               # the errors.POLICIES code behind a non-done status
    detail: dict = field(default_factory=dict)


def _dump(content) -> list:
    return [b.model_dump(mode="json", exclude_none=True) for b in content]


class Engine:
    def __init__(self, client, ledger: Ledger, tools: ToolBox, config: BassConfig | None = None, *,
                 flags: Flags | None = None, sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        self.client, self.ledger, self.tools = client, ledger, tools
        self.cfg = config or BassConfig()
        self.flags = flags or Flags()
        self.sleep, self.monotonic = sleep, monotonic
        self._recent: dict[str, collections.deque] = {}
        self._cancelled: set[str] = set()
        self._owners: dict[str, str] = {}                   # action id -> the account that started it

    # -- public ---------------------------------------------------------------------------------------------------
    def estimate(self, kind: str, first_input_tokens: int = 3000) -> meter.Estimate:
        """What to tell the student before a big action ("about N credits"), shown when N > the threshold."""
        turns = {"build": 12, "edit": 3, "chat": 1}.get(kind, 3)
        out = self.cfg.build_max_tokens // 4 if kind == "build" else self.cfg.chat_max_tokens
        return meter.estimate_action(self.cfg.model_for(kind), first_input_tokens, out, turns)

    def claim(self, action_id: str, uid: str) -> None:
        """Record who owns an action id from the moment its id is handed out (before the first turn runs), so that account's
        stop works even in that gap."""
        self._owners[action_id] = uid

    def cancel(self, action_id: str, uid: str) -> bool:
        """Ask a running action to stop at its next step boundary (what is already stored stays stored). FAILS CLOSED: `uid` is
        required, and the stop is recorded only when the action's owner is known and is that account. An unknown id, a finished
        action or someone else's action does nothing. -> whether it was recorded."""
        if self._owners.get(action_id) != uid or uid is None:
            return False
        self._cancelled.add(action_id)
        return True

    def count_input(self, kind: str, user_text: str, tools=None) -> int:
        """Input tokens of a first turn (system + tools + this text), by the free count_tokens call."""
        t = tools or self.tools
        return self._call(lambda: self.client.messages.count_tokens(
            model=self.cfg.model_for(kind), tools=t.specs(), thinking=self.cfg.thinking_for(kind),
            system=[{"type": "text", "text": self.cfg.system}],
            messages=[{"role": "user", "content": user_text}]).input_tokens)

    def run_action(self, uid: str, user_text: str, *, kind: str = "build", history: list | None = None,
                   action_id: str | None = None, on_event: Callable | None = None,
                   on_tool: Callable | None = None, tools=None) -> ActionResult:
        """on_event gets raw SDK stream events; on_tool(name, input, outcome) fires after each tool ran; `tools`
        replaces the tool belt for this action (the propose step has its own)."""
        res = ActionResult(action_id or "act_" + uuid.uuid4().hex[:12])
        res.messages = self._with_user_turn(list(history or []), user_text)
        self._owners[res.action_id] = uid
        try:
            self._run(uid, kind, res, on_event, tools or self.tools, on_tool)
        except BassError as e:
            self._fail(uid, res, e)
        finally:
            self._cancelled.discard(res.action_id)
            self._owners.pop(res.action_id, None)
        res.spent_mc = self.ledger.action_spent_mc(uid, res.action_id)
        return res

    @staticmethod
    def _with_user_turn(history: list, user_text: str) -> list:
        """Append the student's message. A history cut off after tool results (cap, no credits) ends on a user turn
        already: the new words go INTO that turn, after the tool_results, so roles keep alternating."""
        if history and history[-1]["role"] == "user":
            last = history[-1]
            blocks = ([{"type": "text", "text": last["content"]}] if isinstance(last["content"], str)
                      else list(last["content"]))
            new = list(user_text) if isinstance(user_text, list) else [{"type": "text", "text": user_text}]
            return history[:-1] + [{"role": "user", "content": blocks + new}]
        return history + [{"role": "user", "content": user_text}]

    # -- guards ---------------------------------------------------------------------------------------------------
    def _rate_ok(self, uid: str) -> bool:
        now = self.monotonic()
        q = self._recent.setdefault(uid, collections.deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.cfg.actions_per_minute:
            return False
        q.append(now)
        return True

    def _stop(self, res: ActionResult, status: str, code: str, detail: dict | None = None) -> None:
        res.status, res.code, res.detail = status, code, detail or {}
        res.user_message = POLICIES[code].user_message

    def _fail(self, uid: str, res: ActionResult, e: BassError) -> None:
        code = e.code
        pol = e.policy
        if getattr(self.flags, "takes_uid", False):
            self.flags.trip(pol, e.detail, uid=uid)                  # the beta flags count DISTINCT accounts for bad_input bursts
        else:
            self.flags.trip(pol, e.detail)
        status = {"no_credits": "no_credits", "action_cap": "capped", "daily_cap": "capped",
                  "monthly_cap": "capped", "bass_paused": "paused", "busy": "busy", "beta_daily_full": "paused",
                  "beta_credits_used": "no_credits", "bass_off": "paused", "bass_disabled": "paused",
                  "beta_tester_daily": "capped", "workspace_limit": "paused", "time_limit": "capped",
                  "refused": "refused", "max_tokens": "max_tokens"}.get(code, "error")
        self._stop(res, status, code, e.detail)
        # an action that produced nothing is refunded whole when it failed on Alto's or Anthropic's side
        if pol.refund and status in ("error", "refused") and not res.wrote and not res.text:
            res.refunded_mc += self.ledger.refund(uid, res.action_id, f"failed:{code}")

    # -- the loop -------------------------------------------------------------------------------------------------
    def _run(self, uid: str, kind: str, res: ActionResult, on_event, tools, on_tool) -> None:
        if not self.flags.bass_enabled:
            return self._stop(res, "paused", "bass_paused", {"why": self.flags.reason})
        if not self._rate_ok(uid):
            return self._stop(res, "busy", "busy")
        if kind == "chat" and self.cfg.use_gate and res.messages and not self._on_topic(uid, res):
            res.status, res.text = "off_topic", OFF_TOPIC_REPLY
            res.user_message = OFF_TOPIC_REPLY
            return
        max_tokens = self.cfg.max_tokens_for(kind)
        model, effort = self.cfg.model_for(kind), self.cfg.effort_for(kind)
        thinking = self.cfg.thinking_for(kind)
        tool_specs = tools.specs()
        deadline = None if self.cfg.max_wall_s is None else self.monotonic() + self.cfg.max_wall_s
        stripped = False                                    # the one-time recovery from the history-editing check, per action
        for _ in range(self.cfg.max_turns):
            if res.action_id in self._cancelled:
                return self._stop(res, "stopped", "stopped")
            if deadline is not None and self.monotonic() > deadline - self.cfg.turn_margin_s:
                return self._stop(res, "capped", "time_limit")      # never start a turn the platform would cut mid-stream
            cap_left = self.cfg.per_action_cap_mc - self.ledger.action_spent_mc(uid, res.action_id)
            if cap_left <= 0:
                return self._stop(res, "capped", "action_cap")
            params = {"model": model, "max_tokens": max_tokens, "tools": tool_specs, "thinking": thinking,
                      "output_config": {"effort": effort},
                      "system": [{"type": "text", "text": self.cfg.system, "cache_control": {"type": "ephemeral"}}],
                      "messages": res.messages}
            try:
                n_in = self._call(lambda: self.client.messages.count_tokens(
                    model=params["model"], system=params["system"], tools=tool_specs, thinking=thinking,
                    messages=res.messages).input_tokens)
            except UpstreamError as e:
                if e.code == "history_mismatch" and not stripped:
                    stripped, res.messages = True, strip_thinking(res.messages)
                    continue
                raise
            hold_id = "hold_" + uuid.uuid4().hex[:12]
            worst = max(meter.worst_turn(model, n_in, max_tokens), 1)
            if worst > cap_left:
                # review finding M7: a turn whose worst case does not fit what is left of the action's cap is not started
                return self._stop(res, "capped", "action_cap")
            if getattr(self.ledger, "takes_worst_case", False):
                self.ledger.hold(uid, hold_id, worst, res.action_id, worst_mc=worst)
            else:
                self.ledger.hold(uid, hold_id, worst, res.action_id)            # may raise: BEFORE the call
            sent = _Sent()
            try:
                msg = self._call(lambda: self._stream(params, on_event, sent, deadline), sent)
            except BaseException as e:
                if sent.accepted or getattr(e, "maybe_billed", False):
                    self._book_unfinished(uid, hold_id, worst, res)          # sent and possibly billed: never free, never retried
                else:
                    self.ledger.release(uid, hold_id)                        # provably unbilled (an error answer, or never connected)
                    if isinstance(e, UpstreamError) and e.code == "history_mismatch" and not stripped:
                        stripped, res.messages = True, strip_thinking(res.messages)
                        continue
                raise
            res.turns += 1
            cost = meter.credits_for_usage(model, msg.usage)
            res.out_tokens += int(getattr(msg.usage, "output_tokens", 0) or 0)
            for k, v in meter.usage_dict(msg.usage).items():
                res.usage[k] = res.usage.get(k, 0) + v
            paid = self.ledger.settle(uid, hold_id, cost, note=f"turn {res.turns} {msg.stop_reason}")
            res.charged_mc += paid["charged_mc"]
            if msg.stop_reason == "refusal":
                res.refunded_mc += self.ledger.refund(uid, res.action_id, "refusal", mc=paid["charged_mc"])
                if not res.wrote and not res.text:
                    res.refunded_mc += self.ledger.refund(uid, res.action_id, "refusal:empty-action")
                return self._stop(res, "refused", "refused",
                                  {"category": getattr(getattr(msg, "stop_details", None), "category", None)})
            content = _dump(msg.content)
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            uses = [b for b in content if b.get("type") == "tool_use"]
            if msg.stop_reason == "max_tokens":
                if text:
                    res.text = text
                # a cut-off turn is kept as its words only: no half tool call, and no thinking block inside a turn we rewrote
                keep = [b for b in content if b.get("type") not in ("tool_use",) + THINKING_BLOCKS]
                if keep:
                    res.messages.append({"role": "assistant", "content": keep})
                return self._stop(res, "max_tokens", "max_tokens")
            res.messages.append({"role": "assistant", "content": content})
            if text:
                res.text = text
            if msg.stop_reason == "tool_use" and uses:
                results, outs = [], []
                for b in uses:       # in order, one at a time: the tools share one store
                    out = tools.execute(uid, b["name"], b.get("input"))
                    outs.append(out)
                    res.wrote = res.wrote or out.wrote
                    res.tool_calls.append({"name": b["name"], "input": b.get("input"), "is_error": out.is_error,
                                           "wrote": out.wrote})
                    r = {"type": "tool_result", "tool_use_id": b["id"], "content": out.content}
                    if out.is_error:
                        r["is_error"] = True
                    results.append(r)
                    if on_tool is not None:
                        on_tool(b["name"], b.get("input"), out)
                res.messages.append({"role": "user", "content": results})      # ALL results, ONE message
                if res.action_id in self._cancelled:
                    return self._stop(res, "stopped", "stopped")
                if any(o.final for o in outs):         # a tool that ends the action (the chips proposal)
                    res.status, res.user_message = "done", res.text
                    return
                continue
            if msg.stop_reason == "pause_turn":
                res.messages.append({"role": "user", "content": "Please continue."})
                continue
            res.status = "done"
            res.user_message = res.text
            return
        self._stop(res, "capped", "action_cap", {"why": "max_turns"})

    # -- calls ----------------------------------------------------------------------------------------------------
    def _stream(self, params: dict, on_event, sent: _Sent | None = None, deadline: float | None = None):
        with self.client.messages.stream(**params) as s:
            if sent is not None:
                sent.accepted = True                    # a 200: the model is generating and Anthropic bills from here
            for ev in s:
                if on_event is not None:
                    on_event(ev)
                if deadline is not None and self.monotonic() > deadline:
                    raise BassError(code="time_limit")  # our own stop, mid-stream: booked like any other unfinished call
            return s.get_final_message()

    def _book_unfinished(self, uid: str, hold_id: str, worst_mc: int, res: ActionResult) -> None:
        """A call that was sent and did not finish: its real cost is unknown (thinking tokens are not even visible in a stream), so the
        books take the hold's reserved worst case as Alto's own cost. The student's hold goes back. If even this cannot be written, the
        hold stays where it is and the reaper books it the same way."""
        try:
            self.ledger.settle(uid, hold_id, worst_mc, charge=False, note="unfinished call: booked at the reserved worst case")
            res.absorbed_mc += worst_mc
        except Exception:
            pass

    @staticmethod
    def _maybe_billed(exc: BaseException, sent: _Sent) -> bool:
        """Could Anthropic bill this failed call? No only when it provably never ran: an error ANSWER arrived instead of a result (and no
        stream had started), or the connection was never made. Everything else counts as billed."""
        if sent.accepted:
            return True
        if isinstance(exc, anthropic.APIStatusError):
            return False
        seen, e = set(), exc
        while e is not None and id(e) not in seen:
            seen.add(id(e))
            if isinstance(e, (httpx2.ConnectError, httpx2.ConnectTimeout)):
                return False
            e = e.__cause__ or e.__context__
        return True

    def _call(self, fn, sent: _Sent | None = None):
        """Run one API call with bounded, Alto-side retries (the client itself never retries). With `sent` (a call that costs money) a
        failure is retried only while it is provably unbilled; otherwise it is raised at once, marked maybe_billed."""
        attempt = 0
        while True:
            try:
                return fn()
            except BassError:
                raise
            except (anthropic.APIError, httpx2.HTTPError, httpx2.StreamError, OSError) as exc:   # SDK errors + raw httpx ones
                err = classify(exc)
                if sent is not None and self._maybe_billed(exc, sent):
                    err.maybe_billed = True
                    raise err from exc
                if err.policy.retry and attempt < self.cfg.max_retries:
                    wait = err.detail.get("retry_after")
                    wait = min(self.cfg.retry_max_wait, wait if wait is not None else 2 ** attempt)
                    attempt += 1
                    self.sleep(wait)
                    continue
                raise err from exc

    def _on_topic(self, uid: str, res: ActionResult) -> bool:
        last = res.messages[-1]["content"]
        if not isinstance(last, str):                       # the student's own words only: never the cached documents block or tool results
            last = " ".join(b.get("text", "") for b in last if isinstance(b, dict) and b.get("type") == "text"
                            and not b.get("cache_control")) or str(last)
        msgs = [{"role": "user", "content": last}]
        sent = _Sent()
        try:
            # thinking OFF: with it on (the default) the 16 tokens can all go to thinking and the answer comes back empty
            msg = self._call(lambda: self.client.messages.create(
                model=self.cfg.gate_model, max_tokens=P.GATE_MAX_TOKENS, system=GATE_SYSTEM, messages=msgs,
                thinking=thinking_off(self.cfg.gate_model, self.cfg.gate_effort),
                output_config={"effort": self.cfg.gate_effort}), sent)
        except BassError as e:
            if getattr(e, "maybe_billed", False):           # sent, then lost: Alto's cost at the gate's own worst case
                self.ledger.absorb(uid, res.action_id, meter.worst_turn(self.cfg.gate_model, len(last) // 2 + 200, P.GATE_MAX_TOKENS),
                                   "gate: unfinished call")
            raise
        self.ledger.absorb(uid, res.action_id, meter.credits_for_usage(self.cfg.gate_model, msg.usage), "gate")
        word = "".join(b.text for b in msg.content if b.type == "text").strip().upper()
        return bool(word) and not word.startswith("OFF")    # an EMPTY answer is off topic: the gate never fails open on silence
