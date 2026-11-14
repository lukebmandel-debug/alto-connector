#!/usr/bin/env python3
"""REHEARSAL of Bass's first live call, against the MOCK client only. Never goes live; nothing here reads the key.

    ALTO_NO_NETWORK=1 python3 tools/bass_firstcall_rehearse.py                 # the whole path, B = $100 (the default)
    ALTO_NO_NETWORK=1 python3 tools/bass_firstcall_rehearse.py --balance-usd 62.5   # same, with the caps for that promo balance

It walks the first-call path in order and prints every step: (1) the gates, (2) the cap check, (3) the request that WOULD be sent
(the key field shown as <keychain>), (4) the send through the mock and the spend accounting (hold, settle, local reserve), (5) the turn-off.

It REFUSES TO RUN (exit 2, nothing built, zero requests) if a real key lookup could happen: ALTO_LIVE_ANTHROPIC set at all, a LIVE_GO file
present, ALTO_NO_NETWORK not 1, or any store but a local one. While it runs, the Keychain readers and `security` are tripwired: any call
fails the run. It never creates LIVE_GO and never sets ALTO_LIVE_ANTHROPIC; the gates are modelled in memory.

run_first_call() is the ONE function both the rehearsal and the live day use (the runbook, ORG/bass-firstcall-runbook.md, passes it the
live client); build_request() is the one request. caps() is the formula of notes-testing/alto-bass-live/CAPS.md.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.bass import client as C                      # noqa: E402
from alto.bass import config as P                      # noqa: E402
from alto.bass import meter                            # noqa: E402
from alto.bass import mock_anthropic as M              # noqa: E402
from alto.bass.ledger import Ledger, MemoryStore       # noqa: E402
from alto.bass.local_reserve import LocalReserve, ReservedLedger   # noqa: E402

MC = P.MC
MODEL = P.HAIKU                       # the cheapest model
MAX_TOKENS = 16                       # the smallest budget that still holds the one-word reply
PROMPT = "Reply with the single word ready."
INPUT_BOUND_TOKENS = 64               # a bound on the prompt's tokens (it is about 10): used only for the hold
RUN_CAP_CREDITS = 5                   # the first call's own hard cap: 5 credits = 5 cents. It is the ceiling; the call costs about 0.001
ORG_LIMIT_CREDITS = 500               # the $5 org limit, the real ceiling for now
RESERVE_CREDITS = 1000                # R in CAPS.md: local_reserve.CAP_CREDITS
SLACK_FRACTION = 0.20                 # S = 20% of B (CAPS.md)
TESTERS = 10
UID = "first-call"
KEY_SHOWN = "<keychain>"


# 1. the gates ---------------------------------------------------------------------------------------------------------------------
def gate_state(env, go_path) -> dict:
    """What the two live gates (alto/bass/studio_key.py, client.py) would see. Reads nothing but the env and one path's existence."""
    return {"ALTO_LIVE_ANTHROPIC=1": env.get("ALTO_LIVE_ANTHROPIC") == "1", "LIVE_GO file": Path(go_path).is_file()}


def refusals(env, go_path) -> list:
    """Why the rehearsal must not run here (empty = fine). Stricter than 'both gates open': any open gate refuses."""
    out = []
    if "ALTO_LIVE_ANTHROPIC" in env:
        out.append("ALTO_LIVE_ANTHROPIC is set (a real key lookup could happen)")
    if Path(go_path).is_file():
        out.append(f"a LIVE_GO file exists at {go_path} (a real key lookup could happen)")
    if env.get("ALTO_NO_NETWORK") != "1":
        out.append("ALTO_NO_NETWORK=1 is not set")
    store = env.get("ALTO_STORE", "").strip().lower()
    if store not in ("", "local"):
        out.append(f"ALTO_STORE={store!r} (only a local store is allowed)")
    if any("luke-alto" in (k + "=" + v).lower() for k, v in env.items()):
        out.append("a luke-alto env is set")
    return out


# 2. the caps ----------------------------------------------------------------------------------------------------------------------
def caps(balance_usd: float, testers: int = TESTERS) -> dict:
    """CAPS.md formula, in credits (1 credit = 1 cent). B is the PROMO balance only, never the purchased credit.
    unclamped: R=1000, S=round(0.2 B), C=floor((B-R-S)/100)*100, per tester = floor(C/N), pool = B.
    clamped to the $5 org limit: B_eff=min(B,500); the formula's C goes to 0 (R alone is over B_eff), so the proxy has NO ceiling and stays
    undeployed; the only spender is the local reserve, and its ceiling is min(R, B_eff - S_eff)."""
    B = int(round(balance_usd * 100))
    R = RESERVE_CREDITS
    S = round(SLACK_FRACTION * B)
    C_raw = math.floor((B - R - S) / 100) * 100
    un = {"B": B, "R": R, "S": S, "server_ceiling_C": max(0, C_raw), "per_tester": max(0, C_raw) // testers, "pool_credits": B}
    Be = min(B, ORG_LIMIT_CREDITS)
    Se = round(SLACK_FRACTION * Be)
    Ce = max(0, math.floor((Be - R - Se) / 100) * 100)
    cl = {"B_eff": Be, "R_eff": min(R, Be), "S_eff": Se, "server_ceiling_C": Ce, "per_tester": Ce // testers, "pool_credits": Be,
          "local_ceiling": max(0, min(R, Be - Se)), "first_call_hard_cap": RUN_CAP_CREDITS, "org_limit": ORG_LIMIT_CREDITS}
    return {"unclamped": un, "clamped": cl}


# 3. the request -------------------------------------------------------------------------------------------------------------------
def build_request() -> dict:
    """The ONE smallest call: Haiku, 16 max tokens, thinking off (Haiku thinks by default and thinking counts inside max_tokens), no tools,
    no system prompt, no streaming. This dict is what messages.create(**build_request()) sends."""
    return {"model": MODEL, "max_tokens": MAX_TOKENS, "thinking": P.THINKING_OFF[MODEL],
            "messages": [{"role": "user", "content": PROMPT}]}


def redacted_wire(req: dict) -> dict:
    """What would go on the wire, for printing. The key is never in it."""
    return {"POST": "https://api.anthropic.com/v1/messages",
            "headers": {"x-api-key": KEY_SHOWN, "anthropic-version": "(the SDK's pinned default)", "content-type": "application/json"},
            "body": req}


def cost_bounds() -> dict:
    hold = meter.worst_turn(MODEL, INPUT_BOUND_TOKENS, MAX_TOKENS)
    return {"hold_mc": hold, "hold_cents": hold / MC, "model": MODEL, "max_tokens": MAX_TOKENS, "input_tokens_bound": INPUT_BOUND_TOKENS}


# 4. the send and the spend accounting ---------------------------------------------------------------------------------------------
def run_first_call(client, reserve: LocalReserve, *, log=print, run_cap_credits: int = RUN_CAP_CREDITS) -> dict:
    """The cap check, the hold, ONE messages.create(**build_request()), the settle, and the books. No retry, ever.
    The hold is taken from the shared local reserve first: when it cannot be, no request is made. A failed request is settled at the HOLD
    (the worst case), so a doubtful spend is never booked as free."""
    req = build_request()
    hold_mc = cost_bounds()["hold_mc"]
    left_mc = reserve.left_mc()
    log(f"  cap check: hold {hold_mc} mc ({hold_mc / MC} credits), the call's cap {run_cap_credits} credits, reserve left {left_mc / MC} credits")
    if hold_mc > run_cap_credits * MC or hold_mc > left_mc:
        return {"status": "refused", "reason": "the hold does not fit the first call's cap or the local reserve", "requests": 0}
    inner = Ledger(MemoryStore())
    inner.grant_allowance(UID, run_cap_credits)
    ledger = ReservedLedger(inner, reserve, "first-call")
    ledger.hold(UID, "hold-1", hold_mc, "first-call")
    log(f"  hold taken: {hold_mc} mc from the allowance and the local reserve")
    try:
        msg = client.messages.create(**req)
    except Exception as e:                                # 401, 400, 429, timeout...: stop, no retry, no detail beyond class and status
        ledger.settle(UID, "hold-1", hold_mc, note="request failed: booked at the hold")
        return {"status": "error", "error": type(e).__name__, "http_status": getattr(e, "status_code", None), "requests": 1,
                "booked_mc": hold_mc, "reserve": reserve.status()}
    usage = meter.usage_dict(msg.usage)
    actual_mc = meter.credits_for_usage(MODEL, msg.usage)
    ledger.settle(UID, "hold-1", actual_mc)
    reply = "".join(getattr(b, "text", "") for b in msg.content).strip()
    ok = (msg.stop_reason in ("end_turn", "max_tokens") and "ready" in reply.lower() and usage.get("output_tokens", 99) <= MAX_TOKENS
          and actual_mc <= hold_mc)
    return {"status": "ok" if ok else "unexpected", "stop_reason": msg.stop_reason, "reply_has_ready": "ready" in reply.lower(),
            "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "actual_mc": actual_mc,
            "actual_cents": actual_mc / MC, "hold_mc": hold_mc, "requests": 1, "reserve": reserve.status()}


# 5. the turn-off ------------------------------------------------------------------------------------------------------------------
OFF_SWITCH = ("rm -f ~/.config/alto/bass/LIVE_GO ; unset ALTO_LIVE_ANTHROPIC ; "
              "test ! -e ~/.config/alto/bass/LIVE_GO && echo 'LIVE_GO gone'")


def turn_off(state: dict) -> dict:
    """The in-memory model of the off-switch: both gates closed again."""
    state = dict(state)
    state["LIVE_GO file"] = False
    state["ALTO_LIVE_ANTHROPIC=1"] = False
    return state


# the tripwire ---------------------------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def no_key_lookup():
    """Any key read (studio_key.get_key, the Keychain provider, `security`) or live client during the block records a hit and raises."""
    from alto.bass import keys, studio_key
    hits = []

    def boom(what):
        def f(*a, **k):
            hits.append(what)
            raise AssertionError(f"tripwire: {what}")
        return f
    real_run, real_popen, real_make = subprocess.run, subprocess.Popen, C.make_client

    def run(*a, **k):
        if "security" in str(a[:1]) + str(k.get("args", "")):
            boom("security")()
        return real_run(*a, **k)

    class Popen(real_popen):
        def __init__(self, *a, **k):
            if "security" in str(a[:1]) + str(k.get("args", "")):
                boom("security")()
            super().__init__(*a, **k)

    def make(mode="mock", **k):
        if mode != "mock":
            boom(f"make_client({mode})")()
        return real_make(mode, **k)
    saved = (studio_key.get_key, studio_key.key_present, keys.KeychainKeyProvider.get_key)
    studio_key.get_key, studio_key.key_present = boom("studio_key.get_key"), boom("studio_key.key_present")
    keys.KeychainKeyProvider.get_key = boom("KeychainKeyProvider.get_key")
    subprocess.run, subprocess.Popen, C.make_client = run, Popen, make
    try:
        yield hits
    finally:
        studio_key.get_key, studio_key.key_present, keys.KeychainKeyProvider.get_key = saved
        subprocess.run, subprocess.Popen, C.make_client = real_run, real_popen, real_make


# the rehearsal --------------------------------------------------------------------------------------------------------------------
def rehearse(balance_usd: float = 100.0, *, env=None, go_path=None, log=print, mock=None) -> dict:
    env = os.environ if env is None else env
    go_path = go_path if go_path is not None else C.go_flag_path()
    bad = refusals(env, go_path)
    if bad:
        for b in bad:
            print("refused: " + b, file=sys.stderr)
        return {"refused": bad, "requests": 0}
    result = {}
    with no_key_lookup() as hits:
        log("STEP 1  gates (modelled in memory: this rehearsal never sets either)")
        state = gate_state(env, go_path)
        log("  now:     " + json.dumps(state))
        live = {"ALTO_LIVE_ANTHROPIC=1": True, "LIVE_GO file": True}
        log("  on the day, for ONE command: " + json.dumps(live) + "  (IT sets ALTO_LIVE_ANTHROPIC=1 inline and creates LIVE_GO)")
        log("STEP 2  caps for a promo balance of $%.2f" % balance_usd)
        c = caps(balance_usd)
        log("  unclamped formula: " + json.dumps(c["unclamped"]))
        log("  clamped to the $5 org limit: " + json.dumps(c["clamped"]))
        assert c["clamped"]["local_ceiling"] <= ORG_LIMIT_CREDITS and c["clamped"]["B_eff"] <= ORG_LIMIT_CREDITS
        result["caps"] = c
        log("STEP 3  the request that WOULD be sent (key field: %s)" % KEY_SHOWN)
        wire = redacted_wire(build_request())
        log(json.dumps(wire, indent=2))
        assert KEY_SHOWN in json.dumps(wire) and "sk-ant" not in json.dumps(wire)
        b = cost_bounds()
        log(f"  worst case: {b['hold_mc']} mc = {b['hold_cents']} cent; expected about 0.001 cent")
        log("STEP 4  send through the MOCK client and book the spend")
        mock = mock or M.MockAnthropic(M.Scenario("first-call", [M.Step(M.say("ready."))]))
        client = C.make_client("mock", mock=mock)
        reserve_dir = Path(tempfile.mkdtemp(prefix="bass-firstcall-reserve-"))
        reserve = LocalReserve(reserve_dir / "reserve.rehearsal.json")
        reserve.open_period("rehearsal")
        res = run_first_call(client, reserve, log=log)
        log("  result: " + json.dumps(res, sort_keys=True))
        result["call"] = res
        result["mock_requests"] = len(mock.message_requests)
        log("STEP 5  turn off")
        log("  off-switch: " + OFF_SWITCH)
        off = turn_off(live)
        log("  gates after: " + json.dumps(off))
        assert not any(off.values())
        result["gates_after"] = off
    assert not hits, hits
    result["tripwire_hits"] = hits
    result["ok"] = res.get("status") == "ok" and result["mock_requests"] == 1
    log("REHEARSAL " + ("OK" if result["ok"] else "FAILED") + f": {result['mock_requests']} mock request, key never touched, nothing live")
    return result


def main(argv=None, *, env=None, go_path=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--balance-usd", type=float, default=100.0, help="the PROMO balance B in dollars (never the purchased credit)")
    a = ap.parse_args(argv)
    if a.balance_usd <= 0:
        print("refused: --balance-usd must be positive.", file=sys.stderr)
        return 2
    r = rehearse(a.balance_usd, env=env, go_path=go_path)
    if r.get("refused"):
        return 2
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    # Refuse BEFORE the private HOME is made (isolate would hide the real LIVE_GO path), then isolate like the other Bass tools.
    _bad = refusals(os.environ, C.go_flag_path())
    if _bad:
        for _b in _bad:
            print("refused: " + _b, file=sys.stderr)
        sys.exit(2)
    from alto.bass import isolate
    isolate.start("bass_firstcall_rehearse", mock=True)
    sys.exit(main())
