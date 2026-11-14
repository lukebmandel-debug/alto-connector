"""tools/bass_firstcall_rehearse.py: the rehearsal of the first live call, mock only. It must run the whole path against the mock, show the key
as <keychain>, refuse (zero requests) if a real key lookup could happen, trip on any key read, and compute the caps of CAPS.md."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import importlib.util
import json
import subprocess
import sys

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from alto.bass import client as C
from alto.bass import keys, studio_key
from alto.bass import mock_anthropic as M
from alto.bass.beta_config import BetaConfig

spec = importlib.util.spec_from_file_location("bass_firstcall_rehearse", ROOT / "tools" / "bass_firstcall_rehearse.py")
BFR = importlib.util.module_from_spec(spec)
sys.modules["bass_firstcall_rehearse"] = BFR
spec.loader.exec_module(BFR)

ENV = {"ALTO_NO_NETWORK": "1"}


@pytest.fixture
def nogo(tmp_path):
    return tmp_path / "no-such-go-flag"


def test_the_rehearsal_runs_every_step_prints_the_key_as_keychain_and_makes_one_mock_request(nogo, capsys):
    out = []
    mock = M.MockAnthropic(M.Scenario("t", [M.Step(M.say("ready."))]))
    r = BFR.rehearse(100, env=ENV, go_path=nogo, log=out.append, mock=mock)
    text = "\n".join(out)
    for step in ("STEP 1", "STEP 2", "STEP 3", "STEP 4", "STEP 5"):
        assert step in text
    assert r["ok"] and r["mock_requests"] == 1 and r["tripwire_hits"] == []
    assert '"x-api-key": "<keychain>"' in text and "sk-ant" not in text
    body = mock.message_requests[0]["body"]
    assert body == BFR.build_request() and body["max_tokens"] == 16 and body["model"] == "claude-haiku-5-5" and "tools" not in body
    assert r["call"]["actual_mc"] <= r["call"]["hold_mc"] and r["call"]["actual_cents"] < 0.01
    assert r["gates_after"] == {"ALTO_LIVE_ANTHROPIC=1": False, "LIVE_GO file": False}
    assert not nogo.exists()                                   # the rehearsal never creates LIVE_GO


@pytest.mark.parametrize("env,make_flag,why", [
    ({"ALTO_NO_NETWORK": "1", "ALTO_LIVE_ANTHROPIC": "1"}, False, "ALTO_LIVE_ANTHROPIC"),
    ({"ALTO_NO_NETWORK": "1", "ALTO_LIVE_ANTHROPIC": "0"}, False, "ALTO_LIVE_ANTHROPIC"),
    ({"ALTO_NO_NETWORK": "1"}, True, "LIVE_GO"),
    ({"ALTO_NO_NETWORK": "1", "ALTO_LIVE_ANTHROPIC": "1"}, True, "LIVE_GO"),
    ({}, False, "ALTO_NO_NETWORK"),
    ({"ALTO_NO_NETWORK": "1", "ALTO_STORE": "cloud"}, False, "ALTO_STORE"),
])
def test_it_refuses_when_a_real_key_lookup_could_happen_and_makes_zero_requests(tmp_path, monkeypatch, capsys, env, make_flag, why):
    flag = tmp_path / "LIVE_GO"
    if make_flag:
        flag.write_text("go")
    calls = []
    monkeypatch.setattr(studio_key, "get_key", lambda: calls.append("key"))
    monkeypatch.setattr(C, "make_client", lambda *a, **k: calls.append("client"))
    r = BFR.rehearse(100, env=env, go_path=flag, log=lambda s: calls.append("log"))
    assert r["refused"] and why in " ".join(r["refused"]) and r["requests"] == 0 and calls == []
    assert BFR.main([], env=env, go_path=flag) == 2
    assert "refused:" in capsys.readouterr().err


def test_a_real_lookup_attempted_inside_the_rehearsal_is_caught_by_the_tripwire(monkeypatch):
    with BFR.no_key_lookup() as hits:
        for f in (studio_key.get_key, studio_key.key_present, keys.KeychainKeyProvider().get_key, lambda: C.make_client("live"),
                  lambda: subprocess.run(["security", "find-generic-password", "-s", "alto-anthropic-test", "-w"])):
            with pytest.raises(AssertionError, match="tripwire"):
                f()
    assert len(hits) == 5
    assert studio_key.get_key.__name__ != "f" and C.make_client("mock") is not None      # everything is put back


def test_the_command_line_refuses_with_a_gate_open_and_runs_clean_without(tmp_path):
    import os
    base = {k: v for k, v in os.environ.items() if not k.startswith("ALTO_") and not k.startswith("ANTHROPIC_")}
    base.update({"ALTO_NO_NETWORK": "1", "HOME": str(tmp_path)})
    exe = [sys.executable, str(ROOT / "tools" / "bass_firstcall_rehearse.py")]
    bad = subprocess.run(exe, env={**base, "ALTO_LIVE_ANTHROPIC": "1"}, capture_output=True, text=True)
    assert bad.returncode == 2 and "refused" in bad.stderr and "STEP" not in bad.stdout
    (tmp_path / ".config" / "alto" / "bass").mkdir(parents=True)
    (tmp_path / ".config" / "alto" / "bass" / "LIVE_GO").write_text("go")
    bad = subprocess.run(exe, env=base, capture_output=True, text=True)
    assert bad.returncode == 2 and "LIVE_GO" in bad.stderr and "STEP" not in bad.stdout
    (tmp_path / ".config" / "alto" / "bass" / "LIVE_GO").unlink()
    good = subprocess.run(exe, env=base, capture_output=True, text=True)
    assert good.returncode == 0 and "REHEARSAL OK" in good.stdout and "<keychain>" in good.stdout


def test_caps_follow_the_formula_and_clamp_to_the_org_limit():
    c = BFR.caps(100)
    assert c["unclamped"] == {"B": 10000, "R": 1000, "S": 2000, "server_ceiling_C": 7000, "per_tester": 700, "pool_credits": 10000}
    assert BetaConfig(testers=10, pool_credits=10000, server_ceiling_credits=7000).problems() == []
    assert BFR.caps(60)["unclamped"]["server_ceiling_C"] == 3800 and BFR.caps(60)["unclamped"]["per_tester"] == 380
    k = c["clamped"]
    assert k["B_eff"] == 500 and k["pool_credits"] == 500 and k["server_ceiling_C"] == 0 and k["local_ceiling"] == 400
    assert k["first_call_hard_cap"] == 5 and k["R_eff"] <= 500 and k["local_ceiling"] + k["S_eff"] <= 500
    assert BFR.caps(3)["clamped"]["B_eff"] == 300 and BFR.caps(3)["clamped"]["local_ceiling"] == 240      # a balance under the limit is not raised


def test_the_first_call_is_the_smallest_and_costs_a_fraction_of_a_cent(nogo):
    b = BFR.cost_bounds()
    assert b["hold_mc"] <= 5 and b["hold_cents"] < 0.01
    req = BFR.build_request()
    assert req["thinking"] == {"type": "disabled"} and set(req) == {"model", "max_tokens", "thinking", "messages"}


def test_a_hold_that_does_not_fit_makes_no_request_and_a_failed_call_is_booked_at_the_hold_with_no_retry(tmp_path):
    mock = M.MockAnthropic()
    client = C.make_client("mock", mock=mock)
    from alto.bass.local_reserve import LocalReserve
    full = LocalReserve(tmp_path / "r1.json", cap_credits=1)
    full.open_period("t")
    r = BFR.run_first_call(client, full, log=lambda s: None, run_cap_credits=0)
    assert r["status"] == "refused" and r["requests"] == 0 and mock.requests == []
    mock = M.MockAnthropic().inject(M.Fault("http", 401, "authentication_error", "bad key"))
    client = C.make_client("mock", mock=mock)
    res = LocalReserve(tmp_path / "r2.json")
    res.open_period("t")
    r = BFR.run_first_call(client, res, log=lambda s: None)
    assert r["status"] == "error" and r["http_status"] == 401 and r["requests"] == 1 and len(mock.message_requests) == 1
    assert r["booked_mc"] == r["reserve"]["used_credits"] * 1000
