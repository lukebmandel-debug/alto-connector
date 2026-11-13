"""The simulated Anthropic API, seen through the REAL anthropic SDK: response shapes, SSE streaming, count_tokens,
the request validators (what the real API would 400), and the injected errors."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: skip, never fail
import anthropic
import pytest

from bass_support import bass_guard  # noqa: F401  (autouse guard)
from alto.bass import mock_anthropic as M
from alto.bass.client import make_client

H, S = "claude-haiku-5-5", "claude-sonnet-5-5"
U = [{"role": "user", "content": "hello"}]
OFF = {H: {"type": "disabled"}, S: {"type": "between_tools"}}


def client(scn=None):
    m = M.MockAnthropic(scn)
    return m, make_client("mock", mock=m)


def create(c, **kw):
    kw.setdefault("model", H)
    kw.setdefault("max_tokens", 200)
    kw.setdefault("messages", U)
    # these tests are about the answer's own blocks: thinking is turned off the way each model allows (the mock, like the API, thinks by
    # default and then every reply starts with a thinking block; that has its own tests at the end of this file)
    if kw["model"] in OFF and (kw.get("output_config") or {}).get("effort") not in ("xhigh", "max"):      # off is not allowed at those two
        kw.setdefault("thinking", OFF[kw["model"]])
    return c.messages.create(**kw)


# ── response shapes ────────────────────────────────────────────────────────────────────────────────────────────

def test_message_shape_and_usage():
    m, c = client(M.Scenario("t", [M.Step(M.say("Hi there."))]))
    r = create(c)
    assert r.id.startswith("msg_") and r.type == "message" and r.role == "assistant" and r.model == H
    assert r.content[0].type == "text" and r.content[0].text == "Hi there."
    assert r.stop_reason == "end_turn" and r.stop_sequence is None
    u = r.usage
    assert u.input_tokens > 0 and u.output_tokens > 0
    assert u.cache_creation_input_tokens == 0 and u.cache_read_input_tokens == 0


def test_request_id_header():
    m, c = client()
    raw = c.messages.with_raw_response.create(model=H, max_tokens=50, messages=U, thinking=OFF[H])
    assert raw.headers["request-id"].startswith("req_")
    assert raw.parse().content[0].type == "text"


def test_tool_use_block_parsed():
    scn = M.Scenario("t", [M.Step(M.Reply([M.text("ok"), M.tool_use("add_nodes", {"timeline_id": "x", "nodes": []})]))])
    m, c = client(scn)
    r = create(c, tools=[{"name": "add_nodes", "description": "d",
                          "input_schema": {"type": "object", "properties": {}}}])
    assert r.stop_reason == "tool_use"
    tu = r.content[1]
    assert tu.type == "tool_use" and tu.name == "add_nodes" and tu.input == {"timeline_id": "x", "nodes": []}
    assert tu.id.startswith("toolu_")


def test_thinking_block_parsed():
    m, c = client(M.Scenario("t", [M.Step(M.Reply([M.thinking("hmm"), M.text("done")]))]))
    r = create(c, model=S)
    assert [b.type for b in r.content] == ["thinking", "text"] and r.content[0].thinking == "hmm"
    assert r.content[0].signature


def test_refusal_stop_reason_and_details():
    m, c = client(M.refusal_scenario())
    r = create(c)
    assert r.stop_reason == "refusal" and r.content == []
    assert r.stop_details.category == "general_harms"


def test_max_tokens_cut():
    m, c = client(M.max_tokens_cut())
    r = create(c, max_tokens=30)
    assert r.stop_reason == "max_tokens" and r.usage.output_tokens == 30


def test_reply_longer_than_max_tokens_is_cut_like_the_real_api():
    m, c = client(M.Scenario("t", [M.Step(M.say("word " * 500))]))
    r = create(c, max_tokens=20)
    assert r.stop_reason == "max_tokens" and r.usage.output_tokens == 20 and len(r.content[0].text) <= 20 * 3.5


def test_count_tokens_matches_usage():
    m, c = client(M.Scenario("t", [M.Step(M.say("fine"))]))
    tools = [{"name": "t1", "description": "x" * 100, "input_schema": {"type": "object", "properties": {}}}]
    n = c.messages.count_tokens(model=H, messages=U, system="be brief", tools=tools).input_tokens
    r = create(c, system="be brief", tools=tools)
    assert n == r.usage.input_tokens
    assert n > c.messages.count_tokens(model=H, messages=U).input_tokens   # tools + system cost something


def test_models_retrieve_and_missing():
    m, c = client()
    info = c.models.retrieve(S)
    assert info.id == S and info.max_input_tokens == 1_000_000
    with pytest.raises(anthropic.NotFoundError):
        c.models.retrieve("claude-nope")


def test_prompt_cache_creation_then_read():
    m, c = client(M.Scenario("t", [M.Step(M.say("a")), M.Step(M.say("b"))]))
    sysblocks = [{"type": "text", "text": "rules " * 600, "cache_control": {"type": "ephemeral"}}]
    r1 = create(c, system=sysblocks)
    r2 = create(c, system=sysblocks)
    assert r1.usage.cache_creation_input_tokens > 0 and r1.usage.cache_read_input_tokens == 0
    assert r2.usage.cache_read_input_tokens == r1.usage.cache_creation_input_tokens
    assert r2.usage.cache_creation_input_tokens == 0


# ── validators: what the real API 400s ─────────────────────────────────────────────────────────────────────────

def _bad(msg_part, **kw):
    m, c = client()
    with pytest.raises(anthropic.BadRequestError) as e:
        create(c, **kw)
    assert msg_part in str(e.value), str(e.value)
    return e.value


def test_missing_max_tokens():
    m, c = client()
    with pytest.raises(TypeError):                       # the SDK itself requires it ...
        c.messages.create(model=H, messages=U)
    # ... and the mock rejects it if it ever reaches the wire
    r = m.handle(__import__("httpx2").Request("POST", "https://api.anthropic.com/v1/messages",
                 headers={"x-api-key": "k", "anthropic-version": "2023-06-01"},
                 json={"model": H, "messages": U}))
    assert r.status_code == 400 and "max_tokens" in r.text


def test_max_tokens_over_model_cap():
    _bad("maximum allowed", max_tokens=200_000)


def test_empty_messages():
    _bad("at least one message", messages=[])


def test_must_start_with_user():
    _bad('first message must use the "user" role', messages=[{"role": "assistant", "content": "x"},
                                                              {"role": "user", "content": "y"}])


def test_roles_must_alternate():
    _bad("roles must alternate", messages=[{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])


def test_prefill_rejected():
    _bad("prefill", messages=U + [{"role": "assistant", "content": "{"}])


@pytest.mark.parametrize("model", [H, S])
def test_forced_tool_choice_rejected(model):
    tool = {"name": "x", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    _bad('type "tool" and "any" are not supported', model=model, tools=[tool], tool_choice={"type": "any"})
    _bad('type "tool" and "any" are not supported', model=model, tools=[tool],
         tool_choice={"type": "tool", "name": "x"})


def test_tool_choice_auto_ok():
    m, c = client()
    tool = {"name": "x", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    assert create(c, tools=[tool], tool_choice={"type": "auto"}).stop_reason == "end_turn"


@pytest.mark.parametrize("model", [H, S])
def test_budget_tokens_rejected(model):
    _bad("budget_tokens", model=model, max_tokens=4000, thinking={"type": "enabled", "budget_tokens": 1024})


def test_sonnet_thinking_disabled_rejected_but_adaptive_ok():
    _bad("disabled", model=S, thinking={"type": "disabled"})
    m, c = client()
    assert create(c, model=S, thinking={"type": "adaptive"}).type == "message"


@pytest.mark.parametrize("k,v", [("temperature", 0.2), ("top_p", 0.9), ("top_k", 5)])
def test_sampling_params_rejected(k, v):
    m, c = client()
    with pytest.raises(TypeError):                       # SDK 2.x no longer even has the parameter ...
        create(c, **{k: v})
    r = m.handle(__import__("httpx2").Request("POST", "https://api.anthropic.com/v1/messages",   # ... and the API 400s it
                 headers={"x-api-key": "k", "anthropic-version": "2023-06-01"},
                 json={"model": H, "max_tokens": 10, "messages": U, k: v}))
    assert r.status_code == 400 and k in r.text


def test_unknown_model_404():
    m, c = client()
    with pytest.raises(anthropic.NotFoundError):
        create(c, model="claude-opus-9")


def test_tool_use_without_tool_result():
    msgs = [{"role": "user", "content": "go"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_a", "name": "x", "input": {}}]},
            {"role": "user", "content": "forgot the result"}]
    _bad("without `tool_result` blocks", messages=msgs)


def test_tool_result_for_unknown_id():
    msgs = [{"role": "user", "content": "go"},
            {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_zzz", "content": "x"}]}]
    _bad("unexpected `tool_use_id`", messages=msgs)


def test_tool_result_ok_roundtrip():
    msgs = [{"role": "user", "content": "go"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_a", "name": "x", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_a", "content": "{}"}]}]
    m, c = client()
    assert create(c, messages=msgs).stop_reason == "end_turn"


def test_tool_name_and_schema_validation():
    _bad("pattern", tools=[{"name": "bad name!", "description": "d", "input_schema": {"type": "object"}}])
    _bad("input_schema", tools=[{"name": "ok", "description": "d", "input_schema": {"type": "string"}}])
    t = {"name": "ok", "description": "d", "input_schema": {"type": "object"}}
    _bad("unique", tools=[t, t])


def test_strict_tool_needs_closed_schema():
    open_ = {"name": "t", "description": "d", "strict": True,
             "input_schema": {"type": "object", "properties": {"a": {"type": "object", "additionalProperties": True}},
                              "additionalProperties": False}}
    _bad("additionalProperties", tools=[open_])
    closed = {"name": "t", "description": "d", "strict": True,
              "input_schema": {"type": "object", "properties": {"a": {"type": "string"}},
                               "required": ["a"], "additionalProperties": False}}
    m, c = client()
    assert create(c, tools=[closed]).type == "message"


def test_missing_api_key_is_401_at_the_wire():
    m, _ = client()
    r = m.handle(__import__("httpx2").Request("POST", "https://api.anthropic.com/v1/messages", json={}))
    assert r.status_code == 401 and r.json()["error"]["type"] == "authentication_error"


# ── streaming ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_stream_event_order_and_final_message():
    scn = M.Scenario("t", [M.Step(M.Reply([M.thinking("plan it"), M.text("Building " * 8),
                                           M.tool_use("add_nodes", {"timeline_id": "t1", "nodes": [{"id": "a"}]})]))])
    m, c = client(scn)
    tool = {"name": "add_nodes", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    seen = []
    with c.messages.stream(model=S, max_tokens=500, messages=U, tools=[tool], thinking=OFF[S]) as s:
        for ev in s:
            seen.append(ev.type)
        final = s.get_final_message()
    assert seen[0] == "message_start" and seen[-1] == "message_stop"
    assert seen.index("ping") == 1 if "ping" in seen else True
    starts = [i for i, t in enumerate(seen) if t == "content_block_start"]
    stops = [i for i, t in enumerate(seen) if t == "content_block_stop"]
    assert len(starts) == len(stops) == 3
    assert seen.index("message_delta") > stops[-1] and seen.index("message_stop") > seen.index("message_delta")
    assert [b.type for b in final.content] == ["thinking", "text", "tool_use"]
    assert final.content[1].text == "Building " * 8
    assert final.content[2].input == {"timeline_id": "t1", "nodes": [{"id": "a"}]}   # input_json_delta assembled
    assert final.stop_reason == "tool_use"
    assert final.usage.output_tokens == m.responses[-1]["usage"]["output_tokens"] > 1
    assert final.usage.input_tokens == m.responses[-1]["usage"]["input_tokens"]


def test_stream_text_stream_and_usage_match_nonstream():
    scn = M.Scenario("t", [M.Step(M.say("alpha beta gamma delta " * 5)), M.Step(M.say("alpha beta gamma delta " * 5))])
    m, c = client(scn)
    with c.messages.stream(model=H, max_tokens=300, messages=U, thinking=OFF[H]) as s:
        got = "".join(s.text_stream)
        fin = s.get_final_message()
    non = create(c, max_tokens=300)
    assert got == non.content[0].text == fin.content[0].text
    assert fin.usage.input_tokens == non.usage.input_tokens and fin.usage.output_tokens == non.usage.output_tokens


def test_stream_refusal_carries_stop_details():
    m, c = client(M.refusal_scenario())
    with c.messages.stream(model=H, max_tokens=100, messages=U, thinking=OFF[H]) as s:
        fin = s.get_final_message()
    assert fin.stop_reason == "refusal" and fin.stop_details.category == "general_harms"


def test_mid_stream_error_event_raises():
    m, c = client(M.Scenario("t", [M.Step(M.say("long " * 60))]))
    m.inject(M.stream_error(after_events=4))
    with pytest.raises(anthropic.APIStatusError) as e:
        with c.messages.stream(model=H, max_tokens=300, messages=U, thinking=OFF[H]) as s:
            s.get_final_message()
    assert "Overloaded" in str(e.value)


def test_stream_drop_is_a_connection_error():
    m, c = client(M.Scenario("t", [M.Step(M.say("long " * 60))]))
    m.inject(M.stream_drop(after_events=4))
    with pytest.raises(Exception) as e:
        with c.messages.stream(model=H, max_tokens=300, messages=U, thinking=OFF[H]) as s:
            s.get_final_message()
    assert isinstance(e.value, (anthropic.APIConnectionError, __import__("httpx2").ReadError)) or "simulated" in str(e.value)


# ── injected errors, through the SDK ──────────────────────────────────────────────────────────────────────────

def test_429_has_retry_after_and_ratelimit_headers():
    m, c = client()
    m.inject(M.rate_limit(retry_after=2))
    with pytest.raises(anthropic.RateLimitError) as e:
        create(c)
    assert e.value.status_code == 429 and e.value.response.headers["retry-after"] == "2"
    assert "anthropic-ratelimit-requests-remaining" in e.value.response.headers
    assert e.value.body["error"]["type"] == "rate_limit_error"
    assert create(c).type == "message"     # fault consumed, next call succeeds


@pytest.mark.parametrize("fault,exc,status,etype", [
    (M.overloaded(), anthropic.APIStatusError, 529, "overloaded_error"),
    (M.auth_error(), anthropic.AuthenticationError, 401, "authentication_error"),
    (M.credit_balance_low(), anthropic.BadRequestError, 400, "invalid_request_error"),
    (M.api_error(), anthropic.InternalServerError, 500, "api_error"),
])
def test_http_error_shapes(fault, exc, status, etype):
    m, c = client()
    m.inject(fault)
    with pytest.raises(exc) as e:
        create(c)
    assert e.value.status_code == status
    body = e.value.body
    assert body["error"]["type"] == etype and body["request_id"].startswith("req_")


def test_credit_balance_message_text():
    m, c = client()
    m.inject(M.credit_balance_low())
    with pytest.raises(anthropic.BadRequestError) as e:
        create(c)
    assert "credit balance is too low" in str(e.value)


def test_timeout_and_connect_error():
    m, c = client()
    m.inject(M.read_timeout(), M.connect_error())
    with pytest.raises(anthropic.APITimeoutError):
        create(c)
    with pytest.raises(anthropic.APIConnectionError):
        create(c)


def test_scenario_waits_on_unmatched_step_and_falls_back():
    scn = M.Scenario("t", [M.Step(M.say("matched"), match=lambda c: "magic" in c.last_user_text)])
    m, c = client(scn)
    assert create(c).content[0].text == "OK."                       # fallback, scenario did not advance
    r = create(c, messages=[{"role": "user", "content": "magic word"}])
    assert r.content[0].text == "matched"


def test_mock_records_every_request():
    m, c = client()
    create(c)
    c.messages.count_tokens(model=H, messages=U)
    assert [r["path"] for r in m.requests] == ["/v1/messages", "/v1/messages/count_tokens"]
    assert m.message_requests[0]["body"]["model"] == H


@pytest.mark.parametrize("model", [H, S])
def test_effort_levels_accepted_and_recorded_bad_value_rejected(model):
    m, c = client()
    for lvl in ("low", "medium", "high", "xhigh", "max"):
        assert create(c, model=model, output_config={"effort": lvl}).type == "message"
        assert m.message_requests[-1]["body"]["output_config"] == {"effort": lvl}
    _bad("effort", model=model, output_config={"effort": "turbo"})


# ── thinking is ON by default, counts inside max_tokens, and is bound to its conversation (claude-api reference, 2026-11-03) ──────────

def test_a_default_request_thinks_first_and_the_block_has_empty_text_and_a_signature():
    m, c = client(M.Scenario("t", [M.Step(M.say("Hi."))]))
    r = c.messages.create(model=H, max_tokens=200, messages=U)                 # no `thinking`: adaptive, the default
    assert [b.type for b in r.content] == ["thinking", "text"] and r.content[0].thinking == "" and r.content[0].signature.startswith(M.BOUND)
    r2 = create(c)                                                             # turned off: the answer only
    assert [b.type for b in r2.content] == ["text"]


def test_thinking_counts_inside_max_tokens_so_a_small_cap_returns_no_text_at_all():
    m, c = client(M.Scenario("t", [M.Step(M.say("ON_TOPIC"))], repeat_last=True))
    m.think_tokens = 40
    r = c.messages.create(model=H, max_tokens=16, messages=U)                  # what the 16-token gate did before finding A1 was fixed
    assert r.stop_reason == "max_tokens" and [b.type for b in r.content] == ["thinking"] and r.usage.output_tokens == 16
    r = c.messages.create(model=H, max_tokens=16, messages=U, thinking={"type": "disabled"})
    assert r.stop_reason == "end_turn" and r.content[0].text == "ON_TOPIC"
    r = c.messages.create(model=H, max_tokens=400, messages=U)                 # with room, thinking is paid for and the text arrives
    assert [b.type for b in r.content] == ["thinking", "text"] and r.usage.output_tokens > 40


def test_disabled_is_a_400_on_sonnet_and_between_tools_is_a_400_on_haiku():
    m, c = client()
    for model, bad in ((S, {"type": "disabled"}), (H, {"type": "between_tools"}), (H, {"type": "enabled", "budget_tokens": 2000})):
        with pytest.raises(anthropic.BadRequestError):
            c.messages.create(model=model, max_tokens=100, messages=U, thinking=bad)
    with pytest.raises(anthropic.BadRequestError):
        c.messages.create(model=H, max_tokens=100, messages=U, thinking={"type": "disabled"}, output_config={"effort": "xhigh"})
    assert c.messages.create(model=S, max_tokens=100, messages=U, thinking={"type": "between_tools"}).content[0].type == "text"


def test_a_replayed_thinking_block_is_refused_after_an_earlier_turn_was_edited_and_accepted_when_nothing_changed():
    m, c = client(M.Scenario("t", [M.Step(M.say("One."))], repeat_last=True))
    first = c.messages.create(model=H, max_tokens=200, messages=U)
    kept = [b.model_dump(mode="json", exclude_none=True) for b in first.content]
    same = U + [{"role": "assistant", "content": kept}, {"role": "user", "content": "more"}]
    assert c.messages.create(model=H, max_tokens=200, messages=same).stop_reason == "end_turn"           # append-only: fine
    edited = [{"role": "user", "content": "hello (edited)"}] + same[1:]
    with pytest.raises(anthropic.BadRequestError) as e:
        c.messages.create(model=H, max_tokens=200, messages=edited)
    assert "bound to a different conversation" in str(e.value) and "messages.1.content.0" in str(e.value)
    with pytest.raises(anthropic.BadRequestError):
        c.messages.count_tokens(model=H, messages=edited)                                                # the count endpoint runs the same check
    stripped = [edited[0], {"role": "assistant", "content": [b for b in kept if b["type"] != "thinking"]}, edited[2]]
    assert c.messages.create(model=H, max_tokens=200, messages=stripped).stop_reason == "end_turn"       # the documented recovery
