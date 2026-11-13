"""The simulated Anthropic API. A real `anthropic.Anthropic` client talks to this through an httpx2 MockTransport, so
the SDK builds, sends, parses and streams exactly as it would; only the wire is fake. No socket is ever opened.

What it simulates (shapes from the claude-api skill, cached 2026-10-06):
  POST /v1/messages (JSON and `stream: true` SSE), POST /v1/messages/count_tokens, GET /v1/models/{id}
  request validation that 400s what the real API 400s; scripted scenarios; injected errors.

Token counts are a deterministic APPROXIMATION (chars / 3.5, a fixed overhead per tool). They are consistent
(count_tokens == the usage the same request later reports) so the meter's estimate-vs-actual can be tested.
The first real run replaces them with measured numbers (memo section 3).

THINKING (claude-api reference, cached 2026-11-03). Haiku 5.5 and Sonnet 5.5 think by DEFAULT (adaptive) and thinking counts inside
max_tokens. The mock does the same: unless the request turns thinking off (Haiku: thinking {type: disabled}; Sonnet: {type: between_tools};
{type: disabled} is a 400 on Sonnet 5.5), every reply starts with a `thinking` block whose text is empty (display "omitted", the default)
and whose signature is BOUND to the request it answered (system, tools, the messages before it). `think_tokens` output tokens are spent
on it first (0 by default so the older token arithmetic holds; the thinking tests raise it): when they use up max_tokens the reply is the
thinking block alone with stop_reason max_tokens and NO text, which is what a 16-token gate would get.
THE HISTORY-EDITING CHECK. A replayed thinking block whose prefix changed (an edited earlier turn, system or tools) is a 400
invalid_request_error "Invalid `signature` in `thinking` block. The block is bound to a different conversation...", decided before any
output, as the API does for accounts created after 31 Aug 2026 (`enforce_binding`, on by default: Luke's API account is new).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx2 as httpx

from . import net_guard

MOCK_KEY_PREFIX = "sk-ant-MOCK"
MOCK_KEY = MOCK_KEY_PREFIX + "-0000000000000000000000000000"
BASE_URL = "https://api.anthropic.com"

MODELS = {
    "claude-haiku-5-5": {"display_name": "Claude Haiku 5.5", "max_input_tokens": 1_000_000, "max_tokens": 128_000},
    "claude-sonnet-5-5": {"display_name": "Claude Sonnet 5.5", "max_input_tokens": 1_000_000, "max_tokens": 128_000},
}
CHARS_PER_TOKEN = 3.5
TOOL_OVERHEAD_TOKENS = 50
MESSAGE_OVERHEAD_TOKENS = 4
BASE_OVERHEAD_TOKENS = 12
MIN_CACHEABLE_TOKENS = 512


def approx_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN) if text else 0


# ── scripted replies ──────────────────────────────────────────────────────────────────────────────────────────

def text(s: str) -> dict:
    return {"type": "text", "text": s}


def thinking(s: str) -> dict:
    return {"type": "thinking", "thinking": s, "signature": "sig-" + hashlib.sha1(s.encode()).hexdigest()[:16]}


BOUND = "sigb-"                    # a signature the mock issued for one conversation prefix
BINDING_400 = ("Invalid `signature` in `thinking` block. The block is bound to a different conversation. Remove the block, or set "
               "`thinking.block_binding.prefix_mismatch_behavior` to \"drop_block\". That setting requires the "
               "`thinking-binding-controls-2026-08-01` value in the `anthropic-beta` header.")
THINKING_TYPES = ("thinking", "redacted_thinking")


def thinking_on(body: dict) -> bool:
    """Does this request leave thinking on? (the default on both models)"""
    th = body.get("thinking")
    return not (isinstance(th, dict) and th.get("type") in ("disabled", "between_tools"))


def _plain(v):
    """A message or block without what the check ignores: cache_control markers, and thinking blocks themselves."""
    if isinstance(v, list):
        return [_plain(x) for x in v if not (isinstance(x, dict) and x.get("type") in THINKING_TYPES)]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items() if k != "cache_control"}
    return v


def prefix_signature(body: dict, upto: int | None = None) -> str:
    """The binding of a thinking block produced after messages[:upto] (default: all of them): system, the name-sorted tools, those messages."""
    msgs = body.get("messages", [])
    msgs = msgs if upto is None else msgs[:upto]
    tools = sorted((_plain(t) for t in body.get("tools") or []), key=lambda t: str(t.get("name")))
    blob = json.dumps([_plain(body.get("system")), tools, _plain(msgs)], sort_keys=True)
    return BOUND + hashlib.sha1(blob.encode()).hexdigest()[:24]


_tool_counter = [0]


def tool_use(name: str, input: dict, id: str | None = None) -> dict:
    if id is None:
        _tool_counter[0] += 1
        id = f"toolu_mock{_tool_counter[0]:06d}"
    return {"type": "tool_use", "id": id, "name": name, "input": input}


@dataclass
class Reply:
    blocks: list
    stop_reason: str | None = None            # default: tool_use if any tool_use block else end_turn
    stop_details: dict | None = None
    usage: dict | None = None                 # override fields, e.g. {"cache_read_input_tokens": 500}

    def resolved_stop(self) -> str:
        if self.stop_reason:
            return self.stop_reason
        return "tool_use" if any(b["type"] == "tool_use" for b in self.blocks) else "end_turn"


def say(s: str) -> Reply:
    return Reply([text(s)])


def refusal(category: str | None = "general_harms", explanation: str = "I can't help with that.") -> Reply:
    return Reply([], stop_reason="refusal",
                 stop_details={"type": "refusal", "category": category, "explanation": explanation})


@dataclass
class Ctx:
    """What a scenario step sees of the request."""
    body: dict
    index: int                                  # 0-based request number within the scenario

    @property
    def messages(self) -> list:
        return self.body.get("messages", [])

    @property
    def model(self) -> str:
        return self.body.get("model", "")

    @property
    def last_user_text(self) -> str:
        for m in reversed(self.messages):
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, str):
                    return c
                return " ".join(b.get("text", "") for b in c if b.get("type") == "text")
        return ""

    def tool_results(self) -> list[dict]:
        """The tool_result blocks of the last user message, with `content` parsed as JSON where it is."""
        out = []
        for m in reversed(self.messages):
            if m.get("role") != "user":
                continue
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if b.get("type") == "tool_result":
                        raw = b.get("content")
                        if isinstance(raw, list):
                            raw = "".join(x.get("text", "") for x in raw)
                        try:
                            val = json.loads(raw) if isinstance(raw, str) else raw
                        except ValueError:
                            val = raw
                        out.append({"tool_use_id": b.get("tool_use_id"), "is_error": b.get("is_error", False),
                                    "content": val})
            break
        return out

    def find_in_results(self, key: str):
        for r in self.tool_results():
            if isinstance(r["content"], dict) and key in r["content"]:
                return r["content"][key]
        return None

    def tool_names(self) -> list[str]:
        return [t["name"] for t in self.body.get("tools", [])]


@dataclass
class Step:
    reply: Reply | Callable[[Ctx], Reply]
    match: Callable[[Ctx], bool] | None = None   # None = always


@dataclass
class Scenario:
    """Steps are consumed in order, one per /v1/messages request. A step with `match` is used only when it
    matches, otherwise the scenario waits at that step (and the request gets the generic fallback)."""
    name: str
    steps: list[Step]
    repeat_last: bool = False
    _i: int = 0

    def next(self, ctx: Ctx) -> Reply | None:
        if self._i >= len(self.steps):
            if not (self.repeat_last and self.steps):
                return None
            step = self.steps[-1]
        else:
            step = self.steps[self._i]
        if step.match is not None and not step.match(ctx):
            return None
        self._i += 1
        return step.reply(ctx) if callable(step.reply) else step.reply


# ── injected errors ──────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Fault:
    kind: str                       # http | read_timeout | connect_error | stream_error | stream_drop
    status: int = 500
    etype: str = "api_error"
    message: str = "Internal server error"
    headers: dict = field(default_factory=dict)
    times: int = 1
    path: str = "/v1/messages"      # only requests to exactly this path
    after_events: int = 3           # stream_error/stream_drop: SSE events delivered first
    extra: dict = field(default_factory=dict)       # more keys inside the error object (e.g. error_code)


def rate_limit(retry_after: int = 2, times: int = 1) -> Fault:
    return Fault("http", 429, "rate_limit_error", "Number of request tokens has exceeded your per-minute rate limit",
                 {"retry-after": str(retry_after), "anthropic-ratelimit-requests-limit": "50",
                  "anthropic-ratelimit-requests-remaining": "0",
                  "anthropic-ratelimit-requests-reset": "2026-10-28T20:00:00Z"}, times)


def overloaded(times: int = 1) -> Fault:
    return Fault("http", 529, "overloaded_error", "Overloaded", times=times)


def auth_error(times: int = 1) -> Fault:
    return Fault("http", 401, "authentication_error", "invalid x-api-key", times=times)


def credit_balance_low(times: int = 1) -> Fault:
    return Fault("http", 400, "invalid_request_error",
                 "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to "
                 "upgrade or purchase credits.", times=times)


def workspace_limit(times: int = 1) -> Fault:
    """The Console's monthly workspace spend limit: HTTP 400 invalid_request_error."""
    return Fault("http", 400, "invalid_request_error",
                 "You have reached your specified workspace API usage limits. You will regain access on 2026-12-01 at 00:00 UTC.",
                 times=times)


def org_limit(times: int = 1) -> Fault:
    """The organisation-level wording of the Console limit (no 'workspace')."""
    return Fault("http", 400, "invalid_request_error", "You have reached your specified API usage limits. You will regain access on 2026-12-01 at 00:00 UTC.",
                 times=times)


def spend_limit_429(times: int = 1) -> Fault:
    """The organisation spend cap as documented: HTTP 429 rate_limit_error, error.details.error_code = enforced_spend_limit_reached,
    no retry-after."""
    return Fault("http", 429, "rate_limit_error", "This request would exceed your organization's spend limit.", times=times,
                 extra={"details": {"error_code": "enforced_spend_limit_reached"}})


def spend_limit_429_flat(times: int = 1) -> Fault:
    """The same cap with the code flat inside error (an older shape): handled the same."""
    return Fault("http", 429, "rate_limit_error", "This request would exceed your organization's spend limit.", times=times,
                 extra={"error_code": "enforced_spend_limit_reached"})


def input_400(message: str, times: int = 1) -> Fault:
    """A 400 one tester's input can cause (prompt too long, too many pages, a bad image or document)."""
    return Fault("http", 400, "invalid_request_error", message, times=times)


def unexpected_400(times: int = 1) -> Fault:
    return Fault("http", 400, "invalid_request_error", "messages.0: something Alto never sends", times=times)


def forbidden(times: int = 1) -> Fault:
    return Fault("http", 403, "permission_error", "Your API key does not have permission to use the specified resource.",
                 times=times)


def api_error(times: int = 1) -> Fault:
    return Fault("http", 500, "api_error", "Internal server error", times=times)


def read_timeout(times: int = 1) -> Fault:
    return Fault("read_timeout", times=times)


def connect_error(times: int = 1) -> Fault:
    return Fault("connect_error", times=times)


def stream_error(after_events: int = 3, times: int = 1) -> Fault:
    return Fault("stream_error", 200, "overloaded_error", "Overloaded", times=times, after_events=after_events)


def stream_drop(after_events: int = 3, times: int = 1) -> Fault:
    return Fault("stream_drop", times=times, after_events=after_events)


# ── the simulated server ─────────────────────────────────────────────────────────────────────────────────────

class MockAnthropic:
    def __init__(self, scenario: Scenario | None = None):
        net_guard.install()          # belt and braces: a real Anthropic host is refused from here on
        self.scenario = scenario
        self.faults: list[Fault] = []
        self.requests: list[dict] = []        # every request the mock saw: {method, path, body, headers}
        self.responses: list[dict] = []       # every Message the mock returned (JSON form)
        self.errors_sent: list[dict] = []
        self.fallback: Callable[[Ctx], Reply] = lambda ctx: say("OK.")
        self.n_messages = 0
        self.think_tokens = 0                 # output tokens every thinking-on reply spends on thinking before any text
        self.enforce_binding = True           # the history-editing check (a new API account: enforced)
        self._seq = 0
        self._cache: set[str] = set()

    # -- wiring -----------------------------------------------------------------------------------------------
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def use(self, scenario: Scenario | None) -> "MockAnthropic":
        self.scenario = scenario
        return self

    def inject(self, *faults: Fault) -> "MockAnthropic":
        self.faults.extend(faults)
        return self

    @property
    def message_requests(self) -> list[dict]:
        return [r for r in self.requests if r["path"] == "/v1/messages"]

    # -- ids ----------------------------------------------------------------------------------------------------
    def _next(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_01MOCK{self._seq:08d}"

    # -- errors -------------------------------------------------------------------------------------------------
    def _error(self, status: int, etype: str, message: str, headers: dict | None = None, extra: dict | None = None) -> httpx.Response:
        rid = self._next("req")
        body = {"type": "error", "error": {"type": etype, "message": message, **(extra or {})}, "request_id": rid}
        self.errors_sent.append({"status": status, "type": etype, "message": message})
        h = {"request-id": rid, "content-type": "application/json"}
        h.update(headers or {})
        return httpx.Response(status, json=body, headers=h)

    def _bad(self, message: str) -> httpx.Response:
        return self._error(400, "invalid_request_error", message)

    # -- token model --------------------------------------------------------------------------------------------
    @staticmethod
    def _block_text(b: Any) -> str:
        if isinstance(b, str):
            return b
        t = b.get("type")
        if t == "text":
            return b.get("text", "")
        if t == "tool_use":
            return b.get("name", "") + json.dumps(b.get("input", {}), sort_keys=True)
        if t == "tool_result":
            c = b.get("content", "")
            return c if isinstance(c, str) else "".join(MockAnthropic._block_text(x) for x in c)
        if t == "thinking":
            return b.get("thinking", "")
        if t == "image":
            return "x" * 1500
        if t == "document":
            return "x" * 3000
        return json.dumps(b, sort_keys=True)

    def _content_tokens(self, content: Any) -> int:
        if isinstance(content, str):
            return approx_tokens(content)
        return sum(approx_tokens(self._block_text(b)) for b in content)

    def count_input(self, body: dict) -> dict:
        """-> {input, cacheable} token pieces: system+tools prefix tokens (cache candidates) and the rest."""
        sys_ = body.get("system")
        sys_tokens = 0
        has_cc = False
        if isinstance(sys_, str):
            sys_tokens = approx_tokens(sys_)
        elif isinstance(sys_, list):
            for b in sys_:
                sys_tokens += approx_tokens(b.get("text", ""))
                has_cc = has_cc or bool(b.get("cache_control"))
        tool_tokens = 0
        for t in body.get("tools") or []:
            tool_tokens += TOOL_OVERHEAD_TOKENS + approx_tokens(json.dumps(t, sort_keys=True))
            has_cc = has_cc or bool(t.get("cache_control"))
        msg_tokens = BASE_OVERHEAD_TOKENS
        for m in body.get("messages", []):
            msg_tokens += MESSAGE_OVERHEAD_TOKENS + self._content_tokens(m.get("content", ""))
            if isinstance(m.get("content"), list):
                has_cc = has_cc or any(isinstance(b, dict) and b.get("cache_control") for b in m["content"])
        prefix = sys_tokens + tool_tokens
        key = hashlib.sha1(json.dumps([body.get("model"), body.get("system"), body.get("tools")],
                                      sort_keys=True).encode()).hexdigest()
        return {"prefix": prefix, "rest": msg_tokens, "has_cache_control": has_cc, "prefix_key": key,
                "total": prefix + msg_tokens}

    def usage_for(self, body: dict, out_tokens: int, override: dict | None = None) -> dict:
        c = self.count_input(body)
        cw = cr = 0
        inp = c["total"]
        if c["has_cache_control"] and c["prefix"] >= MIN_CACHEABLE_TOKENS:
            if c["prefix_key"] in self._cache:
                cr, inp = c["prefix"], c["rest"]
            else:
                self._cache.add(c["prefix_key"])
                cw, inp = c["prefix"], c["rest"]
        u = {"input_tokens": inp, "output_tokens": out_tokens,
             "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr}
        if override:
            u.update(override)
        return u

    # -- request validation -------------------------------------------------------------------------------------
    def validate(self, body: dict, *, counting: bool = False) -> httpx.Response | None:
        model = body.get("model")
        if not model or not isinstance(model, str):
            return self._bad("model: Field required")
        if model not in MODELS:
            return self._error(404, "not_found_error", f"model: {model}")
        if not counting:
            mt = body.get("max_tokens")
            if mt is None:
                return self._bad("max_tokens: Field required")
            if not isinstance(mt, int) or isinstance(mt, bool) or mt < 1:
                return self._bad("max_tokens: Input should be a valid integer greater than or equal to 1")
            if mt > MODELS[model]["max_tokens"]:
                return self._bad(f"max_tokens: {mt} > {MODELS[model]['max_tokens']}, which is the maximum allowed "
                                 f"number of output tokens for {model}")
        msgs = body.get("messages")
        if not isinstance(msgs, list) or not msgs:
            return self._bad("messages: at least one message is required")
        for k in ("temperature", "top_p", "top_k"):
            if k in body and body[k] is not None:
                return self._bad(f"`{k}` is deprecated for this model. Remove it from the request.")
        th = body.get("thinking")
        oc = body.get("output_config")
        effort = (oc or {}).get("effort") if isinstance(oc, dict) else None
        if effort is not None and effort not in ("low", "medium", "high", "xhigh", "max"):
            return self._bad(f"output_config.effort: Input should be 'low', 'medium', 'high', 'xhigh' or 'max'")
        if isinstance(th, dict):
            tt = th.get("type")
            if tt == "enabled" or "budget_tokens" in th:
                return self._bad("thinking.enabled.budget_tokens: not supported for this model; "
                                 "use thinking.type=adaptive")
            if tt == "disabled" and model == "claude-sonnet-5-5":
                return self._bad('thinking.type: "disabled" is not supported for this model')
            if tt == "disabled" and model == "claude-haiku-5-5" and effort in ("xhigh", "max"):
                return self._bad('thinking.type: "disabled" is only supported at effort high or below')
            if tt not in ("adaptive", "disabled", "between_tools", None):
                return self._bad(f"thinking.type: unknown value {tt!r}")
            if tt == "between_tools" and model != "claude-sonnet-5-5":
                return self._bad('thinking.type: "between_tools" is not supported for this model')
            if tt == "between_tools" and (effort in ("xhigh", "max") or set(th) - {"type"}):
                return self._bad('thinking.type: "between_tools" takes no other field and is only supported at effort high or below')
        if self.enforce_binding:
            for i, m in enumerate(msgs if isinstance(msgs, list) else []):
                if isinstance(m, dict) and m.get("role") == "assistant" and isinstance(m.get("content"), list):
                    for j, b in enumerate(m["content"]):
                        if isinstance(b, dict) and b.get("type") == "thinking" and str(b.get("signature", "")).startswith(BOUND) \
                                and b["signature"] != prefix_signature(body, i):
                            return self._bad(f"messages.{i}.content.{j}: " + BINDING_400)
        tc = body.get("tool_choice")
        if isinstance(tc, dict) and tc.get("type") in ("any", "tool"):
            return self._bad('tool_choice: type "tool" and "any" are not supported for this model.')
        if msgs[-1].get("role") == "assistant":
            return self._bad("This model does not support assistant message prefill. The conversation must end "
                             "with a user message.")
        prev = None
        ids_open: set[str] = set()
        for i, m in enumerate(msgs):
            role = m.get("role")
            if role not in ("user", "assistant", "system"):
                return self._bad(f"messages.{i}.role: Input should be 'user' or 'assistant'")
            if role == "system":
                continue
            if i == 0 and role != "user":
                return self._bad("messages: first message must use the \"user\" role")
            if prev == role:
                return self._bad('messages: roles must alternate between "user" and "assistant"')
            prev = role
            content = m.get("content")
            if content in (None, "", []):
                return self._bad(f"messages.{i}: content cannot be empty")
            blocks = content if isinstance(content, list) else []
            if role == "assistant":
                if ids_open:
                    return self._bad(f"messages.{i}: `tool_use` ids were found without `tool_result` blocks "
                                     f"immediately after: {', '.join(sorted(ids_open))}")
                ids_open = {b["id"] for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"}
                if len(ids_open) != sum(1 for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"):
                    return self._bad(f"messages.{i}: duplicate tool_use ids")
            else:
                results = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"]
                got = {b.get("tool_use_id") for b in results}
                if ids_open and not ids_open <= got:
                    return self._bad(f"messages.{i}: `tool_use` ids were found without `tool_result` blocks "
                                     f"immediately after: {', '.join(sorted(ids_open - got))}")
                unknown = got - ids_open
                if unknown:
                    return self._bad(f"messages.{i}.content: unexpected `tool_use_id` found in `tool_result` "
                                     f"blocks: {', '.join(sorted(map(str, unknown)))}. Each `tool_result` block "
                                     f"must have a corresponding `tool_use` block in the previous message.")
                if ids_open and blocks and any(b.get("type") != "tool_result" for b in blocks[:len(results)]):
                    return self._bad(f"messages.{i}: `tool_result` blocks must come first in the content")
                ids_open = set()
        tools = body.get("tools")
        if tools is not None:
            if not isinstance(tools, list):
                return self._bad("tools: Input should be a valid list")
            seen = set()
            for i, t in enumerate(tools):
                name = t.get("name", "")
                if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name or ""):
                    return self._bad(f"tools.{i}.custom.name: String should match pattern '^[a-zA-Z0-9_-]{{1,64}}$'")
                if name in seen:
                    return self._bad(f"tools: Tool names must be unique. Found duplicate: {name}")
                seen.add(name)
                sch = t.get("input_schema")
                if not isinstance(sch, dict) or sch.get("type") != "object":
                    return self._bad(f"tools.{i}.custom.input_schema.type: Input should be 'object'")
                if t.get("strict") and not _strict_ok(sch):
                    return self._bad(f"tools.{i}.custom.input_schema: strict tool schemas must set "
                                     f"additionalProperties to false on every object")
        if self.count_input(body)["total"] > MODELS[model]["max_input_tokens"]:
            return self._bad("prompt is too long: exceeds the context window")
        return None

    # -- routing --------------------------------------------------------------------------------------------------
    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        raw = request.content
        body: Any = None
        if request.method == "POST":
            try:
                body = json.loads(raw) if raw else None
            except ValueError:
                body = None
        self.requests.append({"method": request.method, "path": path, "body": body, "host": request.url.host,
                              "headers": dict(request.headers)})
        for h in ("x-api-key", "anthropic-version"):
            if h not in request.headers:
                if h == "x-api-key" and "authorization" in request.headers:
                    continue
                return self._error(401 if h == "x-api-key" else 400,
                                   "authentication_error" if h == "x-api-key" else "invalid_request_error",
                                   "x-api-key header is required" if h == "x-api-key"
                                   else "anthropic-version: header is required")
        for f in self.faults:
            if f.times > 0 and path == f.path:
                f.times -= 1
                if f.kind == "http":
                    return self._error(f.status, f.etype, f.message, f.headers, f.extra)
                if f.kind == "read_timeout":
                    raise httpx.ReadTimeout("simulated read timeout", request=request)
                if f.kind == "connect_error":
                    raise httpx.ConnectError("simulated connect error", request=request)
                if f.kind in ("stream_error", "stream_drop"):
                    return self._messages(request, body, stream_fault=f)
        if request.method == "POST" and path == "/v1/messages":
            return self._messages(request, body)
        if request.method == "POST" and path == "/v1/messages/count_tokens":
            if not isinstance(body, dict):
                return self._bad("Request body must be a JSON object")
            bad = self.validate({**body, "max_tokens": body.get("max_tokens", 1)}, counting=True)
            if bad:
                return bad
            return httpx.Response(200, json={"input_tokens": self.count_input(body)["total"]},
                                  headers={"request-id": self._next("req")})
        m = re.fullmatch(r"/v1/models/([^/]+)", path)
        if request.method == "GET" and m:
            mid = m.group(1)
            if mid not in MODELS:
                return self._error(404, "not_found_error", f"model: {mid}")
            info = MODELS[mid]
            return httpx.Response(200, json={"id": mid, "type": "model", "display_name": info["display_name"],
                                             "created_at": "2026-09-01T00:00:00Z",
                                             "max_input_tokens": info["max_input_tokens"],
                                             "max_tokens": info["max_tokens"], "capabilities": {}},
                                  headers={"request-id": self._next("req")})
        return self._error(404, "not_found_error", f"Not Found: {request.method} {path}")

    # -- /v1/messages --------------------------------------------------------------------------------------------
    def _messages(self, request: httpx.Request, body: Any, stream_fault: Fault | None = None) -> httpx.Response:
        if not isinstance(body, dict):
            return self._bad("Request body must be a JSON object")
        bad = self.validate(body)
        if bad:
            return bad
        ctx = Ctx(body, self.n_messages)
        self.n_messages += 1
        reply = self.scenario.next(ctx) if self.scenario else None
        if reply is None:
            reply = self.fallback(ctx)
        out_tokens = self._reply_tokens(reply)
        stop = reply.resolved_stop()
        if thinking_on(body) and stop != "refusal":
            # the model thinks first: an omitted-display thinking block bound to this request, costing think_tokens of the max_tokens budget
            block = {"type": "thinking", "thinking": "", "signature": prefix_signature(body)}
            if self.think_tokens >= body["max_tokens"]:
                reply, stop = Reply([block], stop_reason="max_tokens", usage=reply.usage), "max_tokens"
            else:
                rest = [b for b in reply.blocks]
                if stop != "max_tokens" and out_tokens + self.think_tokens > body["max_tokens"]:
                    cut = self._truncate(reply, body["max_tokens"] - self.think_tokens)
                    rest, stop = cut.blocks, "max_tokens"
                reply = Reply([block] + rest, stop_reason=stop, stop_details=reply.stop_details, usage=reply.usage)
                out_tokens += self.think_tokens
        if stop == "max_tokens":
            out_tokens = body["max_tokens"]
        elif out_tokens > body["max_tokens"]:
            # the real API cuts the reply at max_tokens: do the same
            reply, out_tokens, stop = self._truncate(reply, body["max_tokens"]), body["max_tokens"], "max_tokens"
        usage = self.usage_for(body, out_tokens, reply.usage)
        msg = {"id": self._next("msg"), "type": "message", "role": "assistant", "model": body["model"],
               "content": reply.blocks, "stop_reason": stop, "stop_sequence": None, "usage": usage}
        if reply.stop_details is not None:
            msg["stop_details"] = reply.stop_details
        rid = self._next("req")
        self.responses.append(msg)
        if body.get("stream"):
            return self._sse(msg, rid, stream_fault)
        return httpx.Response(200, json=msg, headers={"request-id": rid})

    def _reply_tokens(self, reply: Reply) -> int:
        n = 0
        for b in reply.blocks:
            n += approx_tokens(self._block_text(b)) + (3 if b["type"] == "tool_use" else 0)
        return max(n, 1)

    def _truncate(self, reply: Reply, max_tokens: int) -> Reply:
        budget = int(max_tokens * CHARS_PER_TOKEN)
        blocks = []
        for b in reply.blocks:
            if b["type"] == "text":
                t = b["text"][:max(budget, 0)]
                budget -= len(b["text"])
                blocks.append(text(t))
                if budget <= 0:
                    break
            elif b["type"] == "tool_use":
                # a cut-off tool_use is never delivered whole: drop it, as a truncated one is unusable
                break
            else:
                blocks.append(b)
        return Reply(blocks, stop_reason="max_tokens", usage=reply.usage)

    # -- SSE ----------------------------------------------------------------------------------------------------
    def _sse(self, msg: dict, rid: str, fault: Fault | None) -> httpx.Response:
        events: list[tuple[str, dict]] = []
        u = msg["usage"]
        start = {**msg, "content": [], "stop_reason": None,
                 "usage": {**u, "output_tokens": 1}}
        start.pop("stop_details", None)
        events.append(("message_start", {"type": "message_start", "message": start}))
        events.append(("ping", {"type": "ping"}))
        for i, b in enumerate(msg["content"]):
            t = b["type"]
            if t == "text":
                events.append(("content_block_start", {"type": "content_block_start", "index": i,
                                                       "content_block": {"type": "text", "text": ""}}))
                for ch in _chunks(b["text"], 24):
                    events.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                                           "delta": {"type": "text_delta", "text": ch}}))
            elif t == "thinking":
                events.append(("content_block_start", {"type": "content_block_start", "index": i,
                                                       "content_block": {"type": "thinking", "thinking": "",
                                                                         "signature": ""}}))
                for ch in _chunks(b["thinking"], 24):
                    events.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                                           "delta": {"type": "thinking_delta", "thinking": ch}}))
                events.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                                       "delta": {"type": "signature_delta",
                                                                 "signature": b.get("signature", "")}}))
            elif t == "tool_use":
                events.append(("content_block_start", {"type": "content_block_start", "index": i,
                                                       "content_block": {"type": "tool_use", "id": b["id"],
                                                                         "name": b["name"], "input": {}}}))
                for ch in _chunks(json.dumps(b["input"]), 18):
                    events.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                                           "delta": {"type": "input_json_delta",
                                                                     "partial_json": ch}}))
            else:
                events.append(("content_block_start", {"type": "content_block_start", "index": i,
                                                       "content_block": b}))
            events.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
        delta = {"stop_reason": msg["stop_reason"], "stop_sequence": None}
        if msg.get("stop_details") is not None:
            delta["stop_details"] = msg["stop_details"]
        events.append(("message_delta", {"type": "message_delta", "delta": delta, "usage": u}))
        events.append(("message_stop", {"type": "message_stop"}))
        if fault is not None:
            n = max(1, min(fault.after_events, len(events) - 1))
            events = events[:n]
            if fault.kind == "stream_error":
                events.append(("error", {"type": "error", "error": {"type": fault.etype, "message": fault.message},
                                         "request_id": rid}))
                self.errors_sent.append({"status": 200, "type": fault.etype, "message": fault.message,
                                         "mid_stream": True})
        payload = "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in events).encode()
        headers = {"request-id": rid, "content-type": "text/event-stream", "cache-control": "no-cache"}
        if fault is not None and fault.kind == "stream_drop":
            return httpx.Response(200, headers=headers, stream=_DroppingStream(payload))
        return httpx.Response(200, headers=headers, content=payload)


class _DroppingStream(httpx.SyncByteStream):
    """Delivers the bytes, then fails like a dropped connection."""

    def __init__(self, payload: bytes):
        self.payload = payload

    def __iter__(self):
        yield self.payload
        raise httpx.ReadError("simulated dropped connection")


def _chunks(s: str, n: int):
    if not s:
        yield ""
        return
    for i in range(0, len(s), n):
        yield s[i:i + n]


def _strict_ok(schema: Any) -> bool:
    """Strict tool schemas: every object schema must be closed (additionalProperties: false)."""
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            if schema.get("additionalProperties") is not False:
                return False
        return all(_strict_ok(v) for v in schema.values())
    if isinstance(schema, list):
        return all(_strict_ok(v) for v in schema)
    return True


# ── built-in scenarios ──────────────────────────────────────────────────────────────────────────────────────────

def interview() -> Scenario:
    return Scenario("interview", [Step(say(
        "Happy to help. What are you studying, and which materials should the timeline be built from?"))])


def propose_chips(entities: list[dict] | None = None) -> Scenario:
    ents = entities or [{"id": "offer", "name": "Offer"}, {"id": "accept", "name": "Acceptance"}]
    return Scenario("propose_chips", [
        Step(lambda c: Reply([text("Here are the chips I propose."),
                              tool_use("set_entities", {"timeline_id": c.find_in_results("timeline_id") or "t",
                                                        "entities": ents})])),
        Step(say("The chips are set. Confirm or tweak them.")),
    ])


def edit_card(timeline_id: str, node: dict) -> Scenario:
    return Scenario("edit_card", [
        Step(Reply([text("Updating that card."), tool_use("add_nodes", {"timeline_id": timeline_id,
                                                                         "nodes": [node]})])),
        Step(say("Done: the card is updated.")),
    ])


def parallel_tool_use(calls: list[tuple[str, dict]]) -> Scenario:
    return Scenario("parallel", [
        Step(Reply([text("Doing these together.")] + [tool_use(n, i) for n, i in calls])),
        Step(say("Both done.")),
    ])


def off_topic_gate(on_topic: bool = False) -> Scenario:
    return Scenario("off_topic_gate", [Step(say("ON_TOPIC" if on_topic else "OFF_TOPIC"))])


def refusal_scenario() -> Scenario:
    return Scenario("refusal", [Step(refusal())])


def max_tokens_cut(long_text: str | None = None) -> Scenario:
    return Scenario("max_tokens_cut", [Step(Reply([text(long_text or ("The timeline has many parts. " * 400))],
                                                  stop_reason="max_tokens"))])


def build(project_name: str, brief: dict, nodes: list[dict], connections: list | None = None,
          sources: list[dict] | None = None, entities: list[dict] | None = None) -> Scenario:
    """create_project -> create_timeline -> consent -> set_entities -> add_nodes -> add_connections ->
    build_timeline -> final text. The ids chain through the tool results, so it works against the real tools."""
    sources = sources or [{"name": "notes.pdf", "kind": "notes"}]
    ents = entities if entities is not None else brief.get("entities", [])

    def tid(c: Ctx) -> str:
        return c.find_in_results("timeline_id") or "t"

    steps = [
        Step(Reply([text("Starting the build."), tool_use("create_project", {"name": project_name})])),
        Step(lambda c: Reply([tool_use("create_timeline", {"project_id": c.find_in_results("project_id") or "p",
                                                           "brief": brief})])),
        Step(lambda c: Reply([tool_use("record_materials_consent",
                                       {"timeline_id": tid(c), "sources": sources, "consent": True})])),
    ]
    steps.append(Step(lambda c: Reply([tool_use("set_entities", {"timeline_id": TL[0], "entities": ents})])))
    steps.append(Step(lambda c: Reply([tool_use("add_nodes", {"timeline_id": TL[0], "nodes": nodes})])))
    if connections:
        steps.append(Step(lambda c: Reply([tool_use("add_connections",
                                                    {"timeline_id": TL[0], "connections": connections})])))
    steps.append(Step(lambda c: Reply([tool_use("build_timeline", {"timeline_id": TL[0]})])))
    steps.append(Step(say("Your timeline is built.")))
    TL = ["t"]
    # remember the timeline id once create_timeline has answered
    orig = steps[2].reply

    def capture(c: Ctx) -> Reply:
        TL[0] = tid(c)
        return orig(c)
    steps[2] = Step(capture)
    return Scenario("build", steps)
