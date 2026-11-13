"""tools/bass_beta_report.py on mock data: real stack (mock engine, FakeStore), two testers over two days. The report's numbers match the
ledger's own counters, it carries no content (materials, document text, titles, prompts, emails), and it never writes."""
import json
import sys

import pytest

from bass_support import ROOT  # noqa: F401
from bass_beta_support import EMAIL, build_req, edit_req, make_stack, req
from alto.bass import mock_anthropic as M
from alto.bass.beta_config import MC

sys.path.insert(0, str(ROOT / "tools"))
import bass_beta_report as R  # noqa: E402

OTHER = "tester2@example.com"
SECRET = "SECRET-MATERIAL-TEXT-7731"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


def mats():
    return [{"name": "Private notes.pdf", "kind": "notes", "text": f"{SECRET} offer and acceptance, consideration."}]


@pytest.fixture
def beta(tmp_path):
    s = make_stack(tmp_path, emails=(EMAIL, OTHER))
    for day in range(2):
        for email in (EMAIL, OTHER):
            s.mock.use(M.build("Contracts SECRET-TITLE", {"title": "Contracts SECRET-TITLE"}, [], []))
            assert s.svc.handle(req(build_req(materials=mats()), email=email))["ok"]
            s.mock.use(M.say("Done."))
            s.svc.handle(req(edit_req(text=f"{SECRET} add a card"), email=email))
            s.clock.advance(60)
        s.clock.advance(days=1)
    return s


def test_the_report_matches_the_ledger(beta):
    s = beta
    rep = R.build(s.store, s.cfg)
    days = {k[len(R.DAY_PREFIX):]: v for k, v in s.store.docs.items() if k.startswith(R.DAY_PREFIX)}
    assert [r["day"] for r in rep["days"]] == sorted(days) and len(rep["days"]) == 2
    assert rep["total_spent"] == round(sum(v["spent_mc"] for v in days.values()) / MC, 2) > 0
    for d in rep["days"]:                                                    # every credit Alto paid is on some tester's row that day
        assert abs(sum(r["cost"] for r in rep["testers"] if r["day"] == d["day"]) - d["spent"]) < 0.05
    assert {r["uid"] for r in rep["testers"]} == {"u_tester1", "u_tester2"}
    acts = {r["action"]: r for r in rep["actions"]}
    assert acts["build"]["calls"] == 4 and acts["edit"]["calls"] == 4 and acts["build"]["spent"] > 0


def test_the_report_has_no_content_and_no_email(beta):
    out = json.dumps(R.build(beta.store, beta.cfg)) + R.text(R.build(beta.store, beta.cfg))
    assert SECRET in json.dumps([r["body"] for r in beta.mock.requests])            # the content went through the run...
    for never in (SECRET, "SECRET-TITLE", "Private notes", "offer and acceptance", "@example.com", "tester1@", "Done."):
        assert never not in out                                                     # ...and never in the report


def test_the_report_never_writes(beta):
    before = json.dumps(beta.store.docs, sort_keys=True)
    R.build(beta.store, beta.cfg, since="2026-11-03", until="2026-11-03")
    assert json.dumps(beta.store.docs, sort_keys=True) == before
    ro = R.ReadOnly(beta.store)
    with pytest.raises(PermissionError):
        ro.put("bass_beta/kill", {"on": True})
    with pytest.raises(PermissionError):
        ro.run_transaction(lambda txn: None)


def test_the_date_filter(beta):
    one = R.build(beta.store, beta.cfg, since="2026-11-04", until="2026-11-04")
    assert [r["day"] for r in one["days"]] == ["2026-11-04"] and {r["day"] for r in one["testers"]} == {"2026-11-04"}
    assert sum(r["calls"] for r in one["actions"]) == 4


def test_an_empty_store_reports_none(tmp_path):
    s = make_stack(tmp_path)
    rep = R.build(s.store, s.cfg)
    assert rep["days"] == [] and rep["total_spent"] == 0 and "none" in R.text(rep)
