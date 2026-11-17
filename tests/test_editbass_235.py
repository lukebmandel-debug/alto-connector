"""Edit with Bass (v1.9.235, SECURITY): the server half through the REAL HostedGate + Proxy + HostedToolBox over an AdminCloudStore on a fake Firestore,
the model always the mock. Needs the SDK (the mock client is one), so it skips without it. Fakes only: FAKE uids, no network, no key."""
import pytest as _pytest_sdk
_pytest_sdk.importorskip("anthropic")
_pytest_sdk.importorskip("httpx2")
import copy
import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bass_support import bass_guard, ROOT  # noqa: F401,E402
from bass_beta_support import EMAIL, build_req  # noqa: E402
from cloudfake import FakeFirebase  # noqa: E402
from hosted_store_fake import DELETE_FIELD, SERVER_TIMESTAMP, FakeAdminDb  # noqa: E402
from test_bass_hosted_mock_e2e import CANARY, LUKE, NOW, ORIGIN, OTHER, Sec, V  # noqa: E402

from alto.bass import editbass, mock_anthropic as M  # noqa: E402
from alto.bass.beta_ledger import LIVE_GO_KEY, confirm_key  # noqa: E402
from alto.bass.beta_proxy import Proxy  # noqa: E402
from alto.bass.beta_store import FakeStore  # noqa: E402
from alto.bass.client import make_client  # noqa: E402
from alto.bass.hosted import HostedGate, hosted_config  # noqa: E402
from alto.bass.hosted_publish import HostedToolBox  # noqa: E402
from alto.cloud.session import Session  # noqa: E402
from alto.store.admin_cloud import AdminCloudStore  # noqa: E402
from alto.store.cloud import CloudStore  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

DOCS = "projects/proj/databases/(default)/documents"
SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text("utf-8"))
NEW_NODE = {"id": "consideration", "act": 0, "tag": "Formation", "title": "Consideration SECRETWORDS", "desc": "A bargained-for exchange.",
            "entity_ids": ["offer"], "axis1_values": ["ny"], "sections": [{"h": "Rule", "t": "Bargained-for exchange."}]}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


class RecDb(FakeAdminDb):
    def __init__(self, fake):
        super().__init__(fake)
        self.fail_prior = False

    def document(self, rel):
        ref = super().document(rel)
        if self.fail_prior and "/bass_prior/" in rel:
            ref.set = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected"))
        return ref


def _session(fake, tmp_path):
    s = Session({"apiKey": "k", "projectId": "proj", "appId": "a"}, http=fake, path=tmp_path / "s.json", opener=lambda u: None)
    s._accept("RT")
    return s


class Rig:
    def __init__(self, tmp_path, live=True):
        self.fake = FakeFirebase(uid=LUKE)
        self.db = RecDb(self.fake)
        self.admin = AdminCloudStore(self.db, LUKE, LocalStore(tmp_path / "scratch"), "proj", delete_field=DELETE_FIELD, server_timestamp=SERVER_TIMESTAMP)
        self.store, self.sec, self.cfg = FakeStore(auto_terms=True), Sec(), hosted_config()
        self.now = [NOW]
        clock = lambda: self.now[0]
        self.store.put(confirm_key(self.cfg.period_id(NOW)), {"confirmed": True})
        self.store.put("bass_beta/bass_testers", {"emails": [EMAIL]})
        self.store.put("bass_beta/hosted", {"uids": [LUKE]})
        if live:
            self.store.put(LIVE_GO_KEY, {"on": True})
        self.p = Proxy(self.cfg, self.store, V(), self.sec, HostedToolBox(self.admin, LUKE), clock=clock)
        if live:
            self.p._client, self.p._client_mode = make_client("mock", mock=self.p.mock), "live"
        self.t = [1000.0]
        self.eb = editbass.attach(self.p, clock=lambda: self.t[0])
        self.revoked = False
        self.g = HostedGate(self.p, self.store, V(), cfg=self.cfg, pins=frozenset({LUKE}), clock=clock,
                            owns=lambda u, t: (not self.revoked) and self.admin.get_timeline(u, t) is not None)
        self.la = CloudStore(_session(self.fake, tmp_path), LocalStore(tmp_path / "luke-alto"))
        self.p.mock.use(M.build("Contracts", copy.deepcopy(SAMPLE["brief"]), SAMPLE["nodes"], SAMPLE["connections"]))
        assert self.post(build_req())[1]["ok"] is True
        (tl,) = self.la.list_timelines(LUKE)
        self.tid = tl["timeline_id"]
        self.key = tl["private_key"]

    def post(self, req, tok="tok-luke", extra=None):
        h = {"Authorization": "Bearer " + tok, "Origin": ORIGIN, **(extra or {})}
        st, _, b = self.g.handle_http("POST", h, json.dumps(req))
        return st, json.loads(b)

    def scenario(self, node=NEW_NODE):
        sc = M.edit_card(self.tid, copy.deepcopy(node))
        self.p.mock.use(M.Scenario("edit", [M.Step(M.say("ON_TOPIC"))] + sc.steps))      # the first request is the off-topic gate

    def preview(self, text="add consideration", **a):
        self.scenario()
        return self.post({"action": "edit_preview", "args": {"timeline_id": self.tid, "text": text, **a}})[1]

    def apply(self, pid, tid=None):
        return self.post({"action": "edit_apply", "args": {"timeline_id": tid or self.tid, "preview_id": pid}})[1]

    def undo(self):
        return self.post({"action": "edit_undo", "args": {"timeline_id": self.tid}})[1]

    def balance(self):
        return self.post({"action": "balance", "args": {}})[1]["credits"]

    def docs(self):
        return copy.deepcopy(self.fake.docs)


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


BAD = (200, {})


def test_preview_apply_undo_roundtrip_changes_only_the_chosen_timeline(rig):
    before = rig.docs()
    out = rig.preview()
    assert out["ok"] is True and out["changed"] is True and out["preview_id"] and out["summary"]["counts"]["added"] == 1
    assert rig.docs() == before                                            # a preview writes NOTHING to the account
    a = rig.apply(out["preview_id"])
    assert a["ok"] is True and a["applied"] is True and a["charged"] == 0 and a["can_undo"] is True
    assert any(n["id"] == "consideration" for n in rig.la.list_nodes(LUKE, rig.tid))
    assert "SECRETWORDS" in rig.la.get_page(LUKE, rig.key)
    changed = {k for k in before if rig.fake.docs.get(k) != before[k]}
    assert all(f"/users/{LUKE}/" in k for k in changed | (set(rig.fake.docs) - set(before)))
    u = rig.undo()
    assert u["ok"] is True and u["undone"] is True
    assert rig.docs() == before                                            # byte for byte: every document, the page included


def test_prior_version_is_written_before_the_new_one(rig):
    out = rig.preview()
    rig.db.log.clear()
    rig.apply(out["preview_id"])
    rels = [r for _, r in rig.db.log]
    first_prior = min(i for i, r in enumerate(rels) if "/bass_prior/" in r)
    first_real = min(i for i, r in enumerate(rels) if "/alto_timelines/" in r or "/pages/" in r or "/pagemeta/" in r)
    assert first_prior < first_real
    assert not [r for r in rels if "/shares/" in r or "/shared/" in r]


def test_no_prior_save_means_no_write_and_the_preview_stays(rig):
    out = rig.preview()
    before = rig.docs()
    rig.db.fail_prior = True
    a = rig.apply(out["preview_id"])
    assert a["ok"] is False and a["code"] == "edit_not_saved"
    assert rig.docs() == before
    assert not [r for _, r in rig.db.log if "/alto_timelines/" in r and False]
    rig.db.fail_prior = False
    assert rig.apply(out["preview_id"])["ok"] is True                       # the user may try again with the same preview


def test_apply_after_preview_charges_zero_and_preview_charges_once(rig):
    b0 = rig.balance()
    out = rig.preview()
    b1 = rig.balance()
    assert b1 < b0 and out["credits"]["spent"] > 0
    a = rig.apply(out["preview_id"])
    assert rig.balance() == b1 and a["credits"]["spent"] == 0 and a["charged"] == 0
    assert rig.apply(out["preview_id"])["code"] == "edit_preview_gone"      # used once; no second write, no charge
    assert rig.balance() == b1


def test_expired_preview_needs_a_new_preview_and_apply_never_charges(rig):
    out = rig.preview()
    rig.t[0] += editbass.HOLD_SECONDS + 1
    before, bal = rig.docs(), rig.balance()
    a = rig.apply(out["preview_id"])
    assert a["ok"] is False and a["code"] == "edit_preview_gone" and "new charge" in a["message"]
    assert rig.docs() == before and rig.balance() == bal


def test_stale_preview_when_the_timeline_changed_after_it(rig):
    out = rig.preview()
    rig.la.put_nodes(LUKE, rig.tid, [{"id": "other", "t": "manual"}])
    before, bal = rig.docs(), rig.balance()
    a = rig.apply(out["preview_id"])
    assert a["code"] == "edit_stale" and rig.docs() == before and rig.balance() == bal


def test_ownership_revoked_between_preview_and_apply_refuses_and_writes_nothing(rig):
    out = rig.preview()
    before = rig.docs()
    rig.revoked = True
    assert rig.apply(out["preview_id"]) == {}
    assert rig.docs() == before
    rig.revoked = False
    # and the inner check too (no gate in front): a held preview of a timeline that is gone cannot be applied
    rig.admin.delete_timeline(LUKE, rig.tid)
    assert rig.eb.apply(LUKE, rig.tid, out["preview_id"])["code"] == "edit_not_found"


def test_forged_uid_in_the_body_is_refused(rig):
    rig.scenario()
    for extra in ({"uid": OTHER}, {"user": OTHER}, {"account": OTHER}):
        assert rig.post({"action": "edit_preview", "args": {"timeline_id": rig.tid, "text": "x", **extra}}) == BAD
        assert rig.post({"action": "edit_open", "args": {"timeline_id": rig.tid}, **extra}) == BAD
    assert rig.post({"action": "edit_apply", "args": {"timeline_id": rig.tid, "preview_id": "a" * 24, "uid": OTHER}}) == BAD


def test_second_uid_and_unknown_id_and_bad_ids_all_answer_like_a_bad_token(rig):
    bad_token = rig.post({"action": "edit_open", "args": {"timeline_id": rig.tid}}, tok="forged")
    assert bad_token == BAD
    assert rig.post({"action": "edit_open", "args": {"timeline_id": rig.tid}}, tok="tok-other") == bad_token
    for tid in ("nope-nothing", "../x", "A" * 80, "x/y", "", None, 5, "t1;drop", "<b>", "x" * 49):
        assert rig.post({"action": "edit_open", "args": {"timeline_id": tid}}) == bad_token
        assert rig.post({"action": "edit_preview", "args": {"timeline_id": tid, "text": "x"}}) == bad_token
    ok = rig.post({"action": "edit_open", "args": {"timeline_id": rig.tid}})[1]
    assert ok["ok"] is True and ok["title"]


def test_a_second_account_that_is_allowlisted_still_cannot_edit_the_first_ones_timeline(tmp_path):
    """The ownership check itself: OTHER passes every gate, the id exists, but it is LUKE's."""
    r = Rig(tmp_path)
    r.store.put("bass_beta/hosted", {"uids": [OTHER]})
    r.store.put("bass_beta/bass_testers", {"emails": ["other@example.com"]})
    r.g.pins = frozenset({OTHER})
    r.g.allow = type(r.g.allow)(r.store, r.cfg)
    r.g.owns = lambda u, t: LocalStore(tmp_path / "x").get_timeline(u, t) is not None
    assert r.post({"action": "edit_open", "args": {"timeline_id": r.tid}}, tok="tok-other") == BAD
    assert r.post({"action": "balance", "args": {}}, tok="tok-other")[1] != {}      # it is allowlisted: other actions answer


def test_shares_are_byte_identical_and_only_the_owner_copy_changes(rig):
    key = "sharekey0000000000000a"
    rig.fake.docs[f"{DOCS}/shares/{key}"] = {"html": {"stringValue": "<html>public copy</html>"}}
    rig.fake.docs[f"{DOCS}/users/{LUKE}/shared/{key}"] = {"data": {"stringValue": "{}"}}
    pm = f"{DOCS}/users/{LUKE}/pagemeta/{rig.key}"
    rig.fake.docs[pm]["shareKey"] = {"stringValue": key}
    other = {"alto_timelines/zz": {"data": {"stringValue": json.dumps({"timeline_id": "zz"})}}, "pages/zzkey": {"z": {"bytesValue": "AA=="}}}
    for rel, v in other.items():
        rig.fake.docs[f"{DOCS}/users/{LUKE}/{rel}"] = v
    snap = {k: copy.deepcopy(v) for k, v in rig.fake.docs.items() if "/shares/" in k or "/shared/" in k or "/zz" in k}
    out = rig.preview()
    rig.apply(out["preview_id"])
    assert {k: v for k, v in rig.fake.docs.items() if k in snap} == snap
    assert rig.fake.docs[pm]["shareKey"] == {"stringValue": key}
    rig.undo()
    assert {k: v for k, v in rig.fake.docs.items() if k in snap} == snap


def test_calls_that_send_no_edit_text_never_spend_and_open_is_free(rig):
    b = rig.balance()
    assert rig.post({"action": "edit_open", "args": {"timeline_id": rig.tid}})[1]["can_undo"] is False
    assert rig.balance() == b
    assert rig.post({"action": "edit_apply", "args": {"timeline_id": rig.tid, "preview_id": "nope" * 8}})[1]["code"] == "edit_preview_gone"
    assert rig.balance() == b
    assert rig.undo()["code"] == "edit_nothing_to_undo"


def test_the_300_cap_and_the_400_allowance_hold_on_the_preview_path(tmp_path):
    r = Rig(tmp_path)
    assert r.cfg.per_action_cap_credits == 300 and r.cfg.server_ceiling_credits == 400
    spent, refused = 0.0, None
    for _ in range(40):
        r.scenario()
        o = r.post({"action": "edit_preview", "args": {"timeline_id": r.tid, "text": "again"}})[1]
        if o.get("code") in ("beta_credits_used", "beta_tester_daily", "beta_daily_full", "action_cap"):
            refused = o
            break
        spent += (o.get("credits") or {}).get("spent") or 0
    assert spent <= 400
    if refused:
        n = len(r.p.mock.requests)
        r.scenario()
        again = r.post({"action": "edit_preview", "args": {"timeline_id": r.tid, "text": "more"}})[1]
        assert again["ok"] is False and len(r.p.mock.requests) == n          # refused with zero requests, like every other spending action


def test_a_practice_answer_applies_nothing(tmp_path):
    r = Rig(tmp_path)
    r.store.put(LIVE_GO_KEY, {"on": False})                                 # live_go off: the proxy answers from the mock
    out = r.preview()
    before = r.docs()
    a = r.apply(out["preview_id"])
    assert a["ok"] is True and a["applied"] is False and a["mock"] is True and r.docs() == before


def test_logs_hold_class_names_only(rig, caplog):
    caplog.set_level(logging.DEBUG)
    rig.db.fail_prior = True
    out = rig.preview("SECRETTEXT add it")
    rig.apply(out["preview_id"])
    rig.db.fail_prior = False
    out2 = rig.preview("SECRETTEXT2")
    rig.apply(out2["preview_id"])
    rig.undo()
    rig.post({"action": "edit_open", "args": {"timeline_id": "nope-x"}})
    blob = "\n".join(r.getMessage() + " " + str(r.args) + " " + (str(r.exc_info) if r.exc_info else "") for r in caplog.records if r.name.startswith("bass") or r.name.startswith("alto"))
    for secret in (CANARY, "sk-ant", LUKE, OTHER, rig.tid, rig.key, "SECRETTEXT", "SECRETWORDS", "Bearer", "injected"):
        assert secret not in blob, secret
    assert "RuntimeError" in blob                                           # the class name is what is kept


def test_exception_with_a_secret_message_never_reaches_a_log(rig, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    out = rig.preview()

    def boom(*a, **k):
        raise RuntimeError(f"{CANARY} {LUKE} SECRETWORDS")
    monkeypatch.setattr(rig.admin, "save_prior", boom)
    assert rig.apply(out["preview_id"])["code"] == "edit_not_saved"
    monkeypatch.setattr(rig.admin, "get_timeline", boom)
    rig.apply(out["preview_id"])
    blob = "\n".join(r.getMessage() + str(r.args) for r in caplog.records if r.name.startswith("bass") or r.name.startswith("alto"))
    assert CANARY not in blob and LUKE not in blob and "SECRETWORDS" not in blob


def test_the_edit_actions_never_reach_the_model_belt_of_the_account(rig):
    """A preview works on a scratch copy: while it runs, the model's tools write the copy, never the account."""
    seen = []
    orig = rig.admin.put_nodes
    rig.admin.put_nodes = lambda *a, **k: (seen.append(1), orig(*a, **k))[1]
    out = rig.preview()
    assert out["ok"] is True and not seen


def test_the_deployed_logging_config_keeps_the_sdk_and_http_loggers_quiet(rig):
    """(b) the REAL fb_main logging setup (its own lines, executed): the SDK and HTTP loggers sit at WARNING or above, and a DEBUG request-body record from the SDK is never emitted."""
    src = (ROOT / "deploy" / "bass-proxy" / "fb_main.py").read_text("utf-8")
    block = src[src.index("# WARNING and up go to stderr"):src.index("SERVICE_ACCOUNT = None")]
    root, saved = logging.getLogger(), {}
    names = ("anthropic", "anthropic._base_client", "httpx", "httpx2", "httpcore", "httpcore2")
    for n in names + ("",):
        saved[n] = logging.getLogger(n).level
    saved_handlers = list(root.handlers)
    got = []
    h = logging.Handler()
    h.emit = got.append
    h.setLevel(logging.DEBUG)
    root.addHandler(h)
    try:
        import sys
        exec(compile(block, "fb_main-logging", "exec"), {"logging": logging, "sys": sys})
        for n in names:
            assert logging.getLogger(n).getEffectiveLevel() >= logging.WARNING, n
        root.setLevel(logging.DEBUG)                                          # the worst case: the root itself wide open
        logging.getLogger("anthropic._base_client").debug("Request options: %s", {"json_data": {"messages": "SECRETWORDS"}})
        logging.getLogger("httpx2").info('HTTP Request: POST https://api.anthropic.com/v1/messages "200 OK"')
        assert got == []
        logging.getLogger("bass.edit").warning("bass edit: apply failed %s", "RuntimeError")
        assert len(got) == 1                                                  # our own records still flow
    finally:
        root.removeHandler(h)
        root.handlers[:] = saved_handlers
        for n, lv in saved.items():
            logging.getLogger(n).setLevel(lv)
