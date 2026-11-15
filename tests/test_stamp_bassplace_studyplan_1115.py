"""STAMP-bassplace (independent author): the homepage study-plan line's server path, make_study_plan, end to end through the REAL
HostedGate + Proxy + HostedToolBox over an AdminCloudStore on a fake Firestore, the model always the mock. Needs the SDK (the mock client
is an SDK client), so it skips without it; named outside test_bass_* so test_bass_sdk_free's pinned list is unchanged. No network, no key.

Rows: only the pinned uid's ONE named timeline is read and written; the page is re-published private-web under the same key with the
same visibility and shares; forged tokens, a second uid, someone else's timeline id and path tricks read and write nothing; live_go off
writes only the throw-away store."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")
_pytest_sdk.importorskip("httpx2")
import copy
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bass_support import bass_guard, ROOT  # noqa: F401,E402
from test_hosted2_e2e_stamp_1114 import DOCS, _mine, _others, post, rig, seed_other   # noqa: E402
from test_bass_hosted_mock_e2e import LUKE, OTHER   # noqa: E402

from alto.bass import mock_anthropic as M                  # noqa: E402
from alto.bass.beta_ledger import LIVE_GO_KEY              # noqa: E402

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text("utf-8"))
NODES = OUTLINE["nodes"]
KEY0, KEY9 = "lukeoldkey000000000000", "lukeotherkey0000000000"
TODAY = dt.date.today()
D = lambda n: (TODAY + dt.timedelta(days=n)).isoformat()
ANS = {"exam_date": D(20), "days_per_week": 7, "minutes_per_day": 60, "weak": ["remedies"], "told": ""}
ITEMS = [{"node": NODES[0]["id"], "day": D(1), "why": "Your exam is on " + D(20) + ".", "signal": "exam"},
         {"node": NODES[1]["id"], "day": D(2), "why": "Your exam is on " + D(20) + ".", "signal": "exam"}]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")
    monkeypatch.delenv("ALTO_PAYWALL", raising=False)


def seed(la, p=None):
    """Two of Luke's own private-web timelines, written as luke-alto writes them, each with a page and a share."""
    la.put_project(LUKE, "p0", {"project_id": "p0", "name": "Contracts", "created": "2026-10-01T10:00:00Z"})
    for tid, key in (("t0", KEY0), ("t9", KEY9)):
        la.put_timeline(LUKE, tid, {"timeline_id": tid, "project_id": "p0", "created": "2026-10-01T10:00:00Z",
                                    "brief": {**copy.deepcopy(OUTLINE["brief"]), "timeline_id": tid}, "private_key": key, "visibility": "private-web",
                                    "status": "published", "shares": [{"key": "sharekey" + tid + "0000000000000", "on": True}]})
        la.put_nodes(LUKE, tid, copy.deepcopy(NODES))
        la.put_connections(LUKE, tid, copy.deepcopy(OUTLINE["connections"]))
        la.put_page(LUKE, key, "<!doctype html><html><head></head><body>" + tid + "</body></html>", "Contracts",
                    {"tid": tid, "title": "Contracts", "units": [], "search": [], "v": 1})
        if p is not None:                                   # as made in luke-alto: the materials consent is on record
            r = p.real_tools.execute(LUKE, "record_materials_consent", {"timeline_id": tid, "consent": True,
                                     "sources": [{"name": "Contracts notes.docx", "kind": "notes"}]})
            assert not r.is_error, r


def plan_req(tid="t0", accepted=True, **over):
    args = {"timeline_id": tid, "answers": ANS, "consent": True, "accepted": accepted}
    args.update(over)
    return {"action": "make_study_plan", "args": args}


def _plan_mock(p, items=ITEMS):
    p.mock.use(M.Scenario("plan", [M.Step(M.Reply([M.text("Here is the plan."), M.tool_use("propose_study_plan", {"items": items})]))]))


def _docs_of(fake, tid):
    return {k: copy.deepcopy(v) for k, v in fake.docs.items() if f"/users/{LUKE}/alto_timelines/{tid}" in k}


def test_s1_the_plan_reaches_only_the_named_timeline_and_republishes_it_private_web_under_the_same_key(tmp_path):
    g, p, fake, db, la, _ = rig(tmp_path)
    seed_other(fake)
    seed(la, p); db.touched.clear()
    others, t9, before0 = _others(fake), _docs_of(fake, "t9"), la.get_timeline(LUKE, "t0")
    page9 = copy.deepcopy(fake.docs.get(f"{DOCS}/users/{LUKE}/pages/{KEY9}"))
    pages0 = {k for k in fake.docs if f"/users/{LUKE}/pages/" in k}
    assert pages0 and f"{DOCS}/users/{LUKE}/pages/{KEY0}" in pages0
    st, est = post(g, plan_req(accepted=False), "tok-luke")
    assert st == 200 and est["status"] == "estimate" and est["kind"] == "make_study_plan", est
    _plan_mock(p)
    st, out = post(g, plan_req(), "tok-luke")
    assert st == 200 and out.get("plan_saved") is True and out.get("page_rebuilt") is True, out
    after = la.get_timeline(LUKE, "t0")
    assert after["brief"]["study_plan"]["items"] and after["private_key"] == KEY0
    for k in ("visibility", "status", "shares", "project_id", "created"):
        assert after.get(k) == before0.get(k), k
    assert "<body>t0</body>" not in json.dumps(fake.docs[f"{DOCS}/users/{LUKE}/pages/{KEY0}"])        # re-published under the SAME key
    assert {k for k in fake.docs if f"/users/{LUKE}/pages/" in k} == pages0                            # no new page key
    assert _docs_of(fake, "t9") == t9 and fake.docs.get(f"{DOCS}/users/{LUKE}/pages/{KEY9}") == page9   # the other timeline: untouched
    assert _others(fake) == others
    assert db.touched and all(_mine(r) for r in db.touched), sorted({r for r in db.touched if not _mine(r)})
    assert not [r for r in db.touched if "/alto_timelines/t9" in r]                                     # never even read


BAD_IDS = ["t1", f"../{OTHER}/alto_timelines/t1", f"../../users/{OTHER}/alto_timelines/t1", "t0/../t1", "t0/../../t1", "..", ".",
           "", "t0/", "/t0", "t0\\..\\t1", "%2e%2e", "t0\x00", "t" * 600, None, ["t0"], {"t": "t0"}, 7]


def test_s2_forged_tokens_a_second_uid_another_accounts_timeline_and_path_tricks_read_and_write_nothing(tmp_path):
    g, p, fake, db, la, _ = rig(tmp_path)
    seed_other(fake)
    seed(la, p); db.touched.clear()
    before = copy.deepcopy(fake.docs)
    for tok in ("tok-other", "forged", ""):
        for tid in ("t0", "t1"):
            assert post(g, plan_req(tid), tok, {"X-Uid": LUKE}) == (200, {})
    assert fake.docs == before and db.touched == []
    for tid in BAD_IDS:
        _plan_mock(p)
        st, out = post(g, plan_req(tid), "tok-luke", {"X-Uid": OTHER, "X-Forwarded-User": OTHER})
        assert st == 200 and not out.get("plan_saved") and out.get("ok") is not True, (tid, out)
    for extra in ({"uid": OTHER}, {"user": OTHER}, {"account": OTHER}):
        _plan_mock(p)
        out = post(g, plan_req("t1", **extra), "tok-luke")[1]
        assert not out.get("plan_saved"), out
    body = plan_req("t1")
    body.update(uid=OTHER, user=OTHER)
    assert not post(g, body, "tok-luke")[1].get("plan_saved")
    changed = {k for k in set(fake.docs) | set(before) if fake.docs.get(k) != before.get(k)}
    assert not changed, sorted(changed)                                                              # not even Luke's docs moved
    assert all(_mine(r) for r in db.touched), sorted({r for r in db.touched if not _mine(r)})
    assert not [r for r in db.touched if ".." in r or r.count("/alto_timelines/") > 1 or "\\" in r or "%" in r]


def test_s3_the_ui_shaped_request_saves_nothing_unless_the_plan_is_grounded(tmp_path):
    g, p, fake, db, la, _ = rig(tmp_path)
    seed(la, p); db.touched.clear()
    before = copy.deepcopy(fake.docs)
    st, est = post(g, plan_req(accepted=False, answers={"told": "Exam in three weeks, an hour a day, remedies are hard."}), "tok-luke")
    assert st == 200 and est["status"] in ("estimate", "error", "refused"), est
    _plan_mock(p, [{"node": "not-a-node", "day": D(1), "why": "made up", "signal": "told"}])
    out = post(g, plan_req(), "tok-luke")[1]
    assert not out.get("plan_saved")
    assert la.get_timeline(LUKE, "t0").get("brief", {}).get("study_plan") is None
    assert {k: v for k, v in fake.docs.items() if "/alto_timelines/" in k or "/pages/" in k} == \
           {k: v for k, v in before.items() if "/alto_timelines/" in k or "/pages/" in k}


def test_s4_live_go_off_the_plan_goes_only_to_the_throw_away_store(tmp_path, monkeypatch):
    for k in ("ALTO_LIVE_ANTHROPIC", "LIVE_GO", "ALTO_BASS_LIVE"):
        monkeypatch.setenv(k, "1")
    g, p, fake, db, la, store = rig(tmp_path, live=False)
    seed(la, p); db.touched.clear()
    before = copy.deepcopy(fake.docs)
    for acc in (False, True):
        _plan_mock(p)
        st, out = post(g, plan_req(accepted=acc), "tok-luke")
        assert st == 200 and not out.get("plan_saved"), out
    assert fake.docs == before and db.touched == []
    assert p.live_go() is False and store.get(LIVE_GO_KEY) in (None, {})
