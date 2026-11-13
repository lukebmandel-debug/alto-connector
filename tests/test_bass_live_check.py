"""tools/bass_live_check.py, the LOCAL live check: prepared and tested only against the mock. It must refuse without both gates,
make zero requests when refusing, run end to end in dry-run, stop on the first error, respect its own cap, and write metadata only."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")   # public CI has no SDK: these skip there (listed in test_bass_sdk_free.py) and run in the SDK env
_pytest_sdk.importorskip("httpx2")
import csv
import importlib.util
import json
import sys

import pytest

from bass_support import bass_guard, ROOT  # noqa: F401
from alto.bass import client as C
from alto.bass import mock_anthropic as M

spec = importlib.util.spec_from_file_location("bass_live_check", ROOT / "tools" / "bass_live_check.py")
BLC = importlib.util.module_from_spec(spec)
sys.modules["bass_live_check"] = BLC
spec.loader.exec_module(BLC)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


@pytest.fixture
def boom(monkeypatch):
    """Anything that would build a live client, read the key or touch the Keychain fails the test."""
    calls = []

    def no_live(*a, **k):
        calls.append("make_client(live)")
        raise AssertionError("a live client was constructed")
    real = C.make_client
    monkeypatch.setattr(BLC.C, "make_client", lambda mode="mock", **k: no_live() if mode == "live" else real(mode, **k))
    from alto.bass import studio_key
    monkeypatch.setattr(studio_key, "get_key", lambda: calls.append("keychain") or (_ for _ in ()).throw(AssertionError("key read")))
    return calls


def test_it_refuses_without_the_go_flag_even_with_the_env_gate_and_makes_zero_requests(tmp_path, monkeypatch, boom, capsys):
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-such-flag"))
    assert BLC.main(["--out", str(tmp_path / "o")], env={"ALTO_LIVE_ANTHROPIC": "1"}) == 2
    assert "no go flag" in capsys.readouterr().err and boom == [] and not (tmp_path / "o").exists()


def test_it_refuses_with_the_flag_but_without_the_env_gate_and_never_reads_the_key(tmp_path, monkeypatch, boom, capsys):
    flag = tmp_path / "LIVE_GO"
    flag.write_text("go")
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(flag))
    assert BLC.main(["--out", str(tmp_path / "o")], env={}) == 2
    assert "ALTO_LIVE_ANTHROPIC=1" in capsys.readouterr().err and boom == [] and not (tmp_path / "o").exists()


def test_bad_arguments_are_refused(tmp_path):
    assert BLC.main(["--dry-run", "--builds", "4", "--out", str(tmp_path)]) == 2
    assert BLC.main(["--dry-run", "--builds", "11", "--out", str(tmp_path)]) == 2
    assert BLC.main(["--dry-run", "--cap-credits", "0", "--out", str(tmp_path)]) == 2


def test_dry_run_runs_every_step_against_the_mock_and_writes_json_and_csv(tmp_path, monkeypatch, boom, capsys):
    monkeypatch.setenv("ALTO_BASS_LIVE_GO", str(tmp_path / "no-flag"))        # dry-run needs neither gate
    mock = M.MockAnthropic()
    assert BLC.main(["--dry-run", "--builds", "6", "--out", str(tmp_path / "o")], env={}, mock=mock) == 0
    data = json.loads((tmp_path / "o" / "measurements.dry-run.json").read_text("utf-8"))
    steps = [r["step"] for r in data["rows"]]
    assert steps == ["count_tokens", "edit"] + ["build"] * 6
    assert data["meta"]["mode"].startswith("dry-run") and data["meta"]["result"] == "completed"
    builds = [r for r in data["rows"] if r["step"] == "build"]
    assert [r["materials_chars"] for r in builds] == list(BLC.SIZES[:6]) and all(r["status"] == "ok" for r in builds)
    assert all(r["input_tokens"] > 0 and r["output_tokens"] > 0 and r["credits"] > 0 and r["estimate_credits"] for r in builds)
    assert {"median_credits", "p90_credits", "estimate_refit", "suggested_price_per_build_credits"} <= set(data["summary"])
    with (tmp_path / "o" / "measurements.dry-run.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 8 and {"step", "credits", "estimate_credits", "wall_s"} <= set(rows[0])
    assert mock.message_requests and boom == []                              # every request was the mock's
    assert not (tmp_path / "o" / "measurements.json").exists()                # a dry run never writes the live file name
    assert "wrote" in capsys.readouterr().out


def test_it_stops_on_the_first_error_with_no_retry(tmp_path):
    mock = M.MockAnthropic().inject(M.auth_error(times=9))
    assert BLC.main(["--dry-run", "--out", str(tmp_path)], mock=mock) == 1
    data = json.loads((tmp_path / "measurements.dry-run.json").read_text("utf-8"))
    assert [r["step"] for r in data["rows"]] == ["count_tokens", "edit"] and data["rows"][-1]["status"] != "ok"
    assert "stopped at the edit" in data["meta"]["result"] and len(mock.errors_sent) == 1


def test_a_low_balance_or_the_workspace_limit_also_stops_the_run(tmp_path):
    for fault in (M.credit_balance_low, M.workspace_limit):
        out = tmp_path / fault.__name__
        mock = M.MockAnthropic().inject(fault(times=9))
        assert BLC.main(["--dry-run", "--out", str(out)], mock=mock) == 1
        assert len(mock.errors_sent) == 1


def test_its_own_cap_ends_the_run_and_the_spend_never_passes_it(tmp_path):
    assert BLC.main(["--dry-run", "--builds", "10", "--cap-credits", "30", "--out", str(tmp_path)]) == 1
    data = json.loads((tmp_path / "measurements.dry-run.json").read_text("utf-8"))
    builds = [r for r in data["rows"] if r["step"] == "build"]
    assert len(builds) < 10 and builds[-1]["status"] != "ok" and builds[-1]["code"] == "no_credits"
    assert data["meta"]["spent_credits"] <= 30 and data["meta"]["balance_left_credits"] >= 0


def test_outputs_are_metadata_only(tmp_path):
    assert BLC.main(["--dry-run", "--builds", "5", "--out", str(tmp_path)]) == 0
    blob = (tmp_path / "measurements.dry-run.json").read_text("utf-8") + (tmp_path / "measurements.dry-run.csv").read_text("utf-8")
    assert "Acceptance must mirror" not in blob and "Contracts notes" not in blob and "Your timeline is built" not in blob
    assert "sk-" + "ant" not in blob and "x-api-key" not in blob.lower()


def test_the_summary_maths():
    assert BLC.pct([1, 2, 3, 4, 5], 0.9) == pytest.approx(4.6) and BLC.pct([], 0.9) == 0.0
    a, b = BLC.fit_line([0, 1000, 2000], [5, 7, 9])
    assert (round(a, 6), round(b * 1000, 6)) == (5.0, 2.0)
    assert BLC.fit_line([5, 5], [1, 3]) == (2.0, 0.0)
    rows = [{"step": "build", "status": "ok", "credits": c, "estimate_credits": 10, "materials_chars": x}
            for c, x in ((5, 0), (7, 1000), (9, 2000))] + [{"step": "build", "status": "error", "credits": 99, "materials_chars": 1}]
    s = BLC.summarize(rows)
    assert s["builds_ok"] == 3 and s["median_credits"] == 7 and s["suggested_price_per_build_credits"] == 9
    assert s["estimate_refit"] == {"base_credits": 5.0, "per_1k_chars_credits": 2.0} and s["median_actual_over_estimate"] == 0.7
    assert BLC.summarize([])["builds_ok"] == 0


def test_the_script_has_no_key_and_no_network_code_of_its_own():
    src = (ROOT / "tools" / "bass_live_check.py").read_text("utf-8")
    assert "sk-" + "ant" not in src and "x-api-key" not in src.lower() and "requests" not in src.replace("zero requests", "")
    import re
    assert not re.search(r"\b(?:Async)?Anthropic(?:Bedrock|Vertex|Foundry)?\s*\(", src)      # the one client door is alto.bass.client.make_client
