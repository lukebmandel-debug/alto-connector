"""Opt-in conversation sharing (alto-bass-optin; IT design it/bass-conversation-storage-paper.md): the isolation matrix, mock only.
Invented text only. No network, no key, never the cloud env. A tester's conversation is stored ONLY with a current opt-in, with the server-side
switch on; every other path stores nothing."""
import json
import logging
import re
from pathlib import Path

import pytest

from bass_support import ROOT  # noqa: F401
from bass_beta_support import EMAIL, FakeClock, MATERIALS, edit_req, make_stack, req
from alto.bass import research_share as RS
from alto.bass.beta_store import FakeStore, StoreError
from alto.bass.errors import POLICIES

SECRET = "s" * 40
OTHER = "tester2@example.com"
A, B = "u_" + EMAIL.split("@")[0], "u_" + OTHER.split("@")[0]
V = "1.0-test"                                              # a stamped version: the placeholder keeps the switch ignored
SAID = "Add a card about quokka consideration and promissory zebra estoppel."


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


class Rig:
    def __init__(self, tmp):
        self.st = make_stack(tmp, emails=(EMAIL, OTHER), store=FakeStore(auto_terms=True))
        self.bucket = RS.FakeObjectStore()
        self.secret_ok = True
        self.share = RS.ResearchShare(self.st.store, self.bucket.writer(), self._secret, self.st.clock, version=V)
        self.share.on_error = lambda u, code: self.st.svc.meta.write(uid=u, action="research_record", status="error", code=code)
        self.st.svc.research = self.share

    def _secret(self):
        if not self.secret_ok:
            raise RuntimeError("secret manager down")
        return SECRET

    def switch(self, on=True):
        self.st.store.put(RS.SWITCH_KEY, {"enabled": on})

    def ask(self, uid, op, **kw):
        email = EMAIL if uid == A else OTHER
        return self.st.svc.handle(req({"action": RS.RESEARCH, "args": {"op": op, **kw}}, email=email, uid=uid))

    def optin(self, uid, version=V):
        return self.ask(uid, "optin", agree=True, version=version)

    def say(self, uid, text=SAID):
        email = EMAIL if uid == A else OTHER
        out = self.st.svc.handle(req(edit_req(text), email=email, uid=uid))
        assert out["ok"], out
        return out

    def paths(self, uid=None):
        ps = sorted(self.bucket.objects)
        return [p for p in ps if uid is None or f"/{RS.pseudonym(uid, SECRET)}/" in p]


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


# -- zero stored unless every condition holds -------------------------------------------------------------------------------
def test_no_opt_in_means_zero_stored_even_with_the_switch_on(rig):
    rig.switch(True)
    rig.say(A)
    rig.say(B)
    assert rig.bucket.objects == {} and not [k for k in rig.st.store.docs if k.startswith("bass_research")][1:]


def test_the_switch_is_off_by_default_and_opt_in_is_refused_while_it_is_off(rig):
    out = rig.optin(A)
    assert out["ok"] is False and out["code"] == "research_off"
    assert RS.CONSENT_PREFIX + A not in rig.st.store.docs                    # nothing recorded for a refused opt-in
    st = rig.ask(A, "status")["research"]
    assert st["available"] is False and st["needs_optin"] is False and st["on"] is False
    rig.st.store.put(RS.CONSENT_PREFIX + A, {"uid": A, "version": V, "on": True, "acceptedAt": "2026-11-03T15:00:00+00:00"})
    rig.say(A)                                                               # a consent doc exists, but the switch was never turned on
    assert rig.bucket.objects == {}
    for bad in ({"enabled": False}, {"enabled": "true"}, {"enabled": 1}, {}, {"on": True}):
        rig.st.store.put(RS.SWITCH_KEY, bad)
        rig.say(A)
    assert rig.bucket.objects == {}                                          # only the boolean true turns it on


def test_an_opted_in_tester_is_stored_text_only_under_a_pseudonym(rig):
    rig.switch()
    assert rig.ask(A, "status")["research"]["needs_optin"] is True
    assert rig.optin(A)["research"]["on"] is True
    rig.say(A)
    (path,) = rig.paths()
    p = RS.pseudonym(A, SECRET)
    assert path.startswith(f"conv/{p}/") and A not in path and "tester1" not in path
    rec = json.loads(rig.bucket.objects[path][0])
    assert set(rec) == {"v", "optin_version", "at", "action", "user", "bass", "documents_used", "tools", "credits_spent"}
    assert rec["user"] == SAID and rec["action"] == "edit" and rec["optin_version"] == V and isinstance(rec["bass"], str)
    blob = json.dumps(rec)
    assert A not in blob and EMAIL not in blob and "203.0.113.7" not in blob                  # no uid, email or ip


def test_a_opted_in_b_not_only_a_is_written_and_a_does_not_cover_b(rig):
    rig.switch()
    rig.optin(A)
    rig.say(B)
    assert rig.bucket.objects == {}
    rig.say(A)
    rig.say(B)
    assert len(rig.paths(A)) == 1 and rig.paths(B) == [] and len(rig.bucket.objects) == 1
    assert rig.ask(B, "status")["research"]["on"] is False
    rig.st.store.put(RS.CONSENT_PREFIX + B, {"uid": A, "version": V, "on": True, "acceptedAt": "x"})   # a consent doc under B naming A
    rig.say(B)
    assert rig.paths(B) == []


def test_an_old_opt_in_version_regates_and_only_the_current_one_records(rig):
    rig.switch()
    rig.st.store.put(RS.CONSENT_PREFIX + A, {"uid": A, "version": "0.0-old", "on": True, "acceptedAt": "2026-11-01T10:00:00+00:00"})
    rig.say(A)
    assert rig.bucket.objects == {}
    st = rig.ask(A, "status")["research"]
    assert st["on"] is False and st["needs_optin"] is True and st["version"] == V
    assert rig.optin(A, version="0.0-old")["code"] == "research_version"        # an answer to the old text does not count
    assert rig.ask(A, "optin", version=V)["code"] == "research_version"       # no `agree: true` = no yes, never a default
    assert rig.ask(A, "optin", agree="yes", version=V)["code"] == "research_version"
    assert rig.optin(A)["ok"] is True
    rig.say(A)
    assert len(rig.paths(A)) == 1


def test_opt_in_is_write_once_per_version(rig):
    rig.switch()
    rig.optin(A)
    first = dict(rig.st.store.docs[RS.CONSENT_PREFIX + A])
    rig.st.clock.advance(days=3)
    rig.optin(A)
    assert rig.st.store.docs[RS.CONSENT_PREFIX + A] == first and first["acceptedAt"] and set(first) == {"uid", "version", "on", "acceptedAt"}


# -- withdrawal, purge, account deletion -----------------------------------------------------------------------------------
def test_withdraw_stops_the_next_request_and_the_purge_removes_only_that_testers_prefix(rig):
    rig.switch()
    rig.optin(A)
    rig.optin(B)
    rig.say(A)
    rig.say(B)
    out = rig.ask(A, "withdraw")
    assert out["ok"] and out["research"]["on"] is False and out["research"]["purge_within_days"] == RS.PURGE_DAYS
    rig.say(A)
    assert len(rig.paths(A)) == 1 and len(rig.paths(B)) == 1                 # nothing new for A
    tickets = [k for k in rig.st.store.docs if k.startswith(RS.PURGE_PREFIX)]
    assert tickets == [RS.PURGE_PREFIX + RS.pseudonym(A, SECRET)] and A not in json.dumps(rig.st.store.docs[tickets[0]])
    assert RS.purge_due(rig.st.store, rig.bucket.admin(), rig.st.clock())["tickets"] == 0        # not due yet
    rig.st.clock.advance(days=RS.PURGE_DAYS, seconds=1)
    assert RS.purge_due(rig.st.store, rig.bucket.admin(), rig.st.clock()) == {"tickets": 1, "objects": 1, "failed": 0}
    assert rig.paths(A) == [] and len(rig.paths(B)) == 1 and not [k for k in rig.st.store.docs if k.startswith(RS.PURGE_PREFIX)]
    assert rig.ask(A, "status")["research"]["on"] is False and rig.optin(A)["ok"]       # turning back on is a fresh, explicit yes


def test_withdraw_works_with_the_switch_off_and_for_someone_who_never_opted_in(rig):
    assert rig.ask(B, "withdraw")["ok"] is True
    assert RS.CONSENT_PREFIX + B not in rig.st.store.docs


def test_account_deletion_drops_the_consent_and_tickets_the_prefix(rig):
    rig.switch()
    rig.optin(A)
    rig.say(A)
    rig.share.erase_account(A)
    assert RS.CONSENT_PREFIX + A not in rig.st.store.docs
    rig.say(A)
    assert len(rig.paths(A)) == 1
    rig.st.clock.advance(days=8)
    RS.purge_due(rig.st.store, rig.bucket.admin(), rig.st.clock())
    assert rig.paths(A) == []


# -- fail closed -------------------------------------------------------------------------------------------------------------
def test_every_failure_stores_nothing_and_leaves_the_answer_alone(rig):
    rig.switch()
    rig.optin(A)
    rig.st.store.make_unreadable(RS.CONSENT_PREFIX + A)                      # consent read fails
    rig.say(A)
    rig.st.store.make_unreadable(RS.CONSENT_PREFIX + A, False)
    rig.st.store.make_unreadable(RS.SWITCH_KEY)                              # switch read fails
    rig.say(A)
    rig.st.store.make_unreadable(RS.SWITCH_KEY, False)
    rig.secret_ok = False                                                    # secret unreadable
    rig.say(A)
    rig.secret_ok = True
    rig.bucket.fail_create = True                                            # bucket down
    rig.say(A)
    rig.bucket.fail_create = False
    assert rig.bucket.objects == {}
    rig.say(A)
    assert len(rig.paths(A)) == 1                                            # and it works again when everything is back
    rig.st.store.put(RS.CONSENT_PREFIX + A, {"uid": A, "version": V, "on": "true", "acceptedAt": "x"})
    rig.say(A)
    rig.st.store.put(RS.CONSENT_PREFIX + A, {"version": V, "on": True, "acceptedAt": "x"})
    rig.say(A)
    assert len(rig.bucket.objects) == 1


def test_a_short_or_missing_secret_and_a_bad_uid_cannot_make_a_path():
    for bad in ("", "short", None, 5):
        with pytest.raises(RS.ResearchError):
            RS.pseudonym("u1", bad)
    for uid in ("", "a/b", "x" * 200, None, "u 1"):
        with pytest.raises(RS.ResearchError):
            RS.pseudonym(uid, SECRET)
    assert RS.pseudonym("u1", SECRET) == RS.pseudonym("u1", SECRET) != RS.pseudonym("u2", SECRET) != RS.pseudonym("u1", "t" * 40)


def test_the_pseudonym_comes_from_the_verified_uid_not_the_request_body(rig):
    rig.switch()
    rig.optin(A)
    body = edit_req(SAID)
    body["uid"] = B
    body["args"]["uid"] = B
    r = req(body, email=EMAIL, uid=A)
    r["request"]["uid"] = B
    rig.st.svc.handle(r)
    assert rig.paths(B) == []


def test_without_the_terms_nothing_runs_and_nothing_is_stored(tmp_path):
    r = Rig(tmp_path)
    r.st.store = r.share.store = FakeStore()                                  # no terms record for anyone
    r.st.svc.store = r.st.store
    r.st.svc.terms.store = r.st.store
    r.switch()
    out = r.ask(A, "optin", agree=True, version=V)
    assert out["code"] == "terms_required" and r.bucket.objects == {}


def test_no_research_wired_the_action_answers_off_and_nothing_is_stored(rig):
    rig.st.svc.research = None
    out = rig.ask(A, "optin", agree=True, version=V)
    assert out["code"] == "research_off" and out["ok"] is False
    rig.say(A)
    assert rig.bucket.objects == {}


# -- what a record holds ---------------------------------------------------------------------------------------------------
def test_no_document_text_no_materials_and_the_log_never_holds_the_conversation(rig, caplog):
    rig.switch()
    rig.optin(A)
    secret_note = "my zebra-note says the quokka rule"
    caplog.set_level(logging.DEBUG)
    out = rig.st.svc.handle(req({"action": "propose", "args": {"materials": MATERIALS, "note": secret_note}}, uid=A))
    assert out["ok"]
    (path,) = rig.paths(A)
    blob = rig.bucket.objects[path][0].decode()
    assert secret_note in blob                                                # the student's own note is the user turn
    for m in MATERIALS:
        assert m["text"][:30] not in blob and m.get("name", "\0") not in blob  # no document text, no file name
    ours = " ".join(r.getMessage() for r in caplog.records if r.name.startswith("bass"))     # Alto's own log calls (the SDK's debug lines are not ours)
    assert ours and "zebra" not in ours and "quokka" not in ours and not any("zebra" in json.dumps(l) for l in rig.st.svc.meta.lines)


def test_redaction_catches_emails_links_keys_and_phones_and_leaves_ordinary_text():
    s = ("Mail me at jane.doe@example.com or +1 (212) 555-0147, see https://alto.example/s/AbC123xyz?key=Zq9 and www.example.org/x "
         "key " + "sk-" + "ant-api03-ABCDEFGHIJKLMNOP1234 Bearer abcdef1234567890XYZ token Zq9Zq9Zq9Zq9Zq9Zq9Zq9Zq9Zq9Zq9Zq9 "
         "hash 0123456789abcdef0123456789abcdef0123")
    r = RS.redact(s)
    for gone in ("jane.doe", "555-0147", "alto.example", "example.org", "sk-ant", "abcdef1234567890XYZ", "Zq9Zq9Zq9", "0123456789abcdef"):
        assert gone not in r, gone
    assert "[email]" in r and "[link]" in r and "[key]" in r and "[number]" in r
    ordinary = "In 1861 the Fort Sumter fight began; the claim was $75,000 over 3 counts, page 12-14, 2026-11-03."
    assert RS.redact(ordinary) == ordinary
    assert len(RS.redact("ab " * 40_000)) == RS.MAX_FIELD_CHARS and RS.redact("x" * 100_000) == "[key]" and RS.redact(None) == ""      # capped; one huge run is replaced whole


# -- the three narrow views, export, retention -----------------------------------------------------------------------------
def test_the_views_hold_only_their_own_permissions(rig):
    b = rig.bucket
    b.writer().create("conv/p/1.json", b"{}")
    w, a, r = b.writer(), b.admin(), b.reader()
    for call in (lambda: w.list("conv/"), lambda: w.read("conv/p/1.json"), lambda: w.delete("conv/p/1.json"),
                 lambda: a.create("conv/p/2.json", b"{}"), lambda: a.read("conv/p/1.json"),
                 lambda: r.create("conv/p/2.json", b"{}"), lambda: r.delete("conv/p/1.json")):
        with pytest.raises(PermissionError):
            call()
    with pytest.raises(RS.ResearchError):
        w.create("conv/p/1.json", b"{}")                                       # never overwritten
    assert "conv/p/1.json" in r.list("conv/") and a.list("conv/") == r.list("conv/")


def test_export_is_read_only_logged_by_name_and_stays_inside_the_prefix(rig):
    rig.switch()
    rig.optin(A)
    rig.say(A)
    rig.say(A)
    log = []
    recs = RS.export_opted_in(rig.bucket.reader(), log, "analyst-1", rig.st.clock())
    assert len(recs) == 2 and [l["path"] for l in log] == rig.paths(A) and all(set(l) == {"path", "by", "at"} for l in log)
    assert SAID not in json.dumps(log)                                         # the access log holds names, never content
    with pytest.raises(RS.ResearchError):
        RS.export_opted_in(rig.bucket.reader(), log, "x", rig.st.clock(), prefix="bass_credits/")
    with pytest.raises(PermissionError):
        RS.export_opted_in(rig.bucket.writer(), log, "x", rig.st.clock())


def test_the_lifecycle_rule_deletes_after_the_retention_period(rig):
    rig.switch()
    rig.optin(A)
    rig.say(A)
    assert RS.RETENTION_DAYS == 90 and rig.bucket.lifecycle_rule()["rule"][0]["condition"] == {"age": 90}
    assert rig.bucket.expire(rig.st.clock() + __import__("datetime").timedelta(days=89)) == 0
    assert rig.bucket.expire(rig.st.clock() + __import__("datetime").timedelta(days=91)) == 1 and rig.bucket.objects == {}


# -- static: rules, key map, no client path --------------------------------------------------------------------------------
def test_firestore_rules_deny_every_research_collection_and_stay_identical():
    t = (ROOT / "firestore.rules").read_text(encoding="utf-8")
    assert (ROOT / "alto" / "firestore.rules").read_bytes() == (ROOT / "firestore.rules").read_bytes()
    for coll in ("bass_research", "bass_research_consent", "bass_research_purge"):
        assert re.search(r"match /" + coll + r"/\{document=\*\*\} \{\s*allow read, write: if false;\s*\}", t), coll
    assert not re.search(r"match /\{[^}]*\}\s*\{", t)                                             # no catch-all added
    assert not re.search(r"bass_research[^\n]*\n[^\n]*allow [^\n]*if (?!false)", t)


def test_the_firestore_key_map_covers_the_research_keys():
    sys_path = str(ROOT / "deploy" / "bass-proxy")
    import sys
    sys.path.insert(0, sys_path)
    try:
        import firestore_store as FS
    finally:
        sys.path.remove(sys_path)
    assert FS._path(RS.SWITCH_KEY) == ("bass_research", "switch")
    assert FS._path(RS.CONSENT_PREFIX + "u1") == ("bass_research_consent", "u1")
    assert FS._path(RS.PURGE_PREFIX + "ab" * 20) == ("bass_research_purge", "ab" * 20)
    with pytest.raises(StoreError):
        FS._path(RS.CONSENT_PREFIX + "u1/x")


def test_the_gcs_adapter_creates_with_no_overwrite_and_stays_in_the_prefix():
    import sys
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    try:
        import gcs_object_store as G
    finally:
        sys.path.remove(str(ROOT / "deploy" / "bass-proxy"))

    class Blob:
        def __init__(self, name, log):
            self.name, self.log = name, log

        def upload_from_string(self, data, content_type=None, if_generation_match=None, timeout=None):
            self.log.append(("up", self.name, if_generation_match, timeout))

    class Bucket:
        def __init__(self):
            self.log = []

        def blob(self, name):
            return Blob(name, self.log)
    b = Bucket()
    G.CreateOnly(b).create("conv/p/1.json", b"{}")
    assert b.log == [("up", "conv/p/1.json", 0, 10)]                            # ifGenerationMatch=0: create only; a 10 s timeout
    for bad in ("other/1.json", "conv/../x", ""):
        with pytest.raises(RS.ResearchError):
            G.CreateOnly(b).create(bad, b"{}")
    assert not hasattr(G.CreateOnly, "read") and not hasattr(G.CreateOnly, "delete") and not hasattr(G.CreateOnly, "list")


def test_policies_for_the_new_codes_exist_and_are_plain():
    for c in ("research_off", "research_version", "research_error"):
        assert POLICIES[c].user_message.endswith(".") and "Traceback" not in POLICIES[c].user_message


def test_the_balance_answer_carries_the_sharing_state_with_one_read_while_the_switch_is_off(rig):
    BAL = {"action": "balance", "args": {}}
    reads = []
    real = rig.st.store.get
    rig.st.store.get = lambda k: (reads.append(k), real(k))[1]
    out = rig.st.svc.handle(req(BAL, uid=A))
    assert out["research"] == {"available": False, "on": False, "version": V, "needs_optin": False}
    assert [k for k in reads if k.startswith("bass_research")] == [RS.SWITCH_KEY]            # one read, no consent read, nothing else
    rig.switch()
    assert rig.st.svc.handle(req(BAL, uid=A))["research"]["needs_optin"] is True
    rig.optin(A)
    assert rig.st.svc.handle(req(BAL, uid=A))["research"] == {"available": True, "on": True, "version": V, "needs_optin": False}
    rig.st.svc.research = None
    assert "research" not in rig.st.svc.handle(req(BAL, uid=A))


def test_while_the_version_is_the_placeholder_the_switch_is_ignored(rig):
    ph = RS.ResearchShare(rig.st.store, rig.bucket.writer(), rig._secret, rig.st.clock, version=RS.PLACEHOLDER_VERSION)
    assert ph.version == RS.PLACEHOLDER_VERSION != RS.OPTIN_VERSION == "optin-1"     # the real version is stamped; the placeholder still disables
    rig.st.svc.research = ph
    rig.switch()
    assert ph.enabled() is False and ph.status(A)["available"] is False
    assert rig.optin(A, version=RS.PLACEHOLDER_VERSION)["code"] == "research_off" and RS.CONSENT_PREFIX + A not in rig.st.store.docs
    rig.st.store.put(RS.CONSENT_PREFIX + A, {"uid": A, "version": RS.PLACEHOLDER_VERSION, "on": True, "acceptedAt": "x"})
    rig.say(A)
    assert rig.bucket.objects == {}


def test_a_swallowed_recording_error_leaves_one_meta_line_with_a_code_and_no_text(rig):
    rig.switch()
    rig.optin(A)
    n = len(rig.st.svc.meta.lines)
    rig.secret_ok = False
    rig.say(A)
    errs = [l for l in rig.st.svc.meta.lines if l.get("action") == "research_record"]
    assert len(errs) == 1 and errs[0]["status"] == "error" and errs[0]["code"] == "RuntimeError" and errs[0]["uid"] == A
    assert SAID not in json.dumps(rig.st.svc.meta.lines) and rig.bucket.objects == {} and len(rig.st.svc.meta.lines) == n + 2   # the error line + the call's own line
    rig.secret_ok = True
    rig.bucket.fail_create = True
    rig.say(A)
    assert [l["code"] for l in rig.st.svc.meta.lines if l.get("action") == "research_record"] == ["RuntimeError", "ResearchError"]
    rig.bucket.fail_create = False
    rig.say(A)
    assert len([l for l in rig.st.svc.meta.lines if l.get("action") == "research_record"]) == 2          # a good turn adds none


def test_the_secret_read_and_upload_have_ten_second_timeouts_and_the_env_is_listed():
    main = (ROOT / "deploy" / "bass-proxy" / "main.py").read_text(encoding="utf-8")
    assert main.count("access_secret_version(name=hmac_name, timeout=10)") == 1 and "access_secret_version(name=name, timeout=10)" in main
    assert not re.search(r"bass-research-hmac[^\n]*\n[^\n]*access_secret_version\(name=[a-z_]+\)", main)
    assert '"BASS_RESEARCH_BUCKET"' in main.split("OPTIONAL_ENV = (")[1].split(")")[0]


def test_the_service_wires_the_error_counter_itself(rig):
    from alto.bass.beta_guard import Allowlist, BetaService
    st = rig.st
    share = RS.ResearchShare(st.store, rig.bucket.writer(), rig._secret, st.clock, version=V)
    svc = BetaService(st.cfg, st.acts, st.ledger, store=st.store, kill=st.kill, allow=Allowlist(st.store, st.cfg), sink=st.sink,
                      clock=st.clock, research=share)
    assert share.on_error is not None
    rig.switch()
    st.store.put(RS.CONSENT_PREFIX + A, {"uid": A, "version": V, "on": True, "acceptedAt": "x"})
    rig.secret_ok = False
    assert svc.handle(req(edit_req(SAID), uid=A))["ok"]
    assert [l["code"] for l in svc.meta.lines if l.get("action") == "research_record"] == ["RuntimeError"]


# -- the independent attack (alto-org reports/optin-attack.md): O1, O2, O3, O5 -------------------------------------------------------------------
def test_o1_redaction_catches_share_and_page_keys_scheme_less_links_unicode_ips_and_jwts():
    zw = "\u200b"
    cases = ["my link key is wk9wmv6g4iehtqre7q6jg8", "alto-timelines.web.app/s/AbCd1234EfGh5678IjKl/", "page key Zq9Zq9Zq9Zq9Zq9Zq9Zq91 here",
             "write to alice\uff20example.com now", f"alice@exa{zw}mple.com", f"h{zw}ttps://alto.example/s/KEYKEY12345678901234", "server 10.0.0.12 down",
             "ip 2001:db8::1 and fe80::1ff:fe23:4567:890a", "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c end"]
    secrets_ = ["wk9wmv6g4iehtqre7q6jg8", "web.app/s/", "Zq9Zq9Zq9Zq9", "example.com", "alice", "mple.com", "KEYKEY1234", "10.0.0.12", "2001:db8", "fe80::1ff", "eyJhbGci", "SflKxwRJ"]
    for s, gone in zip(cases, secrets_):
        r = RS.redact(s)
        assert gone not in r, (s, r)
    assert RS.redact("meet at 12:30:45 on 2026-11-03 for Marbury v. Madison, 5 U.S. 137") == "meet at 12:30:45 on 2026-11-03 for Marbury v. Madison, 5 U.S. 137"
    assert RS.redact("Restatement (Second) of Contracts section 90, e.g. reliance") == "Restatement (Second) of Contracts section 90, e.g. reliance"


def test_o2_a_second_withdraw_never_postpones_the_purge(rig):
    rig.switch()
    rig.optin(A)
    rig.say(A)
    rig.ask(A, "withdraw")
    first = dict(rig.st.store.docs[RS.PURGE_PREFIX + RS.pseudonym(A, SECRET)])
    rig.st.clock.advance(days=6)
    rig.ask(A, "withdraw")                                                   # the switch-off path invites a repeat
    rig.share.erase_account(A)                                               # and so does account deletion
    again = rig.st.store.docs[RS.PURGE_PREFIX + RS.pseudonym(A, SECRET)]
    assert again["purgeBy"] == first["purgeBy"] and again["requestedAt"] == first["requestedAt"]
    rig.st.clock.advance(days=1, seconds=3600)                               # day 7.04: past the FIRST date, before a postponed one
    assert RS.purge_due(rig.st.store, rig.bucket.admin(), rig.st.clock())["objects"] == 1 and rig.paths(A) == []
    rig.st.store.put(RS.PURGE_PREFIX + RS.pseudonym(A, SECRET), {"pseudonym": RS.pseudonym(A, SECRET), "requestedAt": "garbage", "purgeBy": "garbage"})
    rig.ask(A, "withdraw")                                                   # an unreadable old ticket is replaced by a fresh one
    assert RS.PURGE_PREFIX + RS.pseudonym(A, SECRET) in rig.st.store.docs


def test_o3_one_malformed_purge_ticket_does_not_stop_the_others_and_is_counted(rig):
    rig.switch()
    rig.optin(A)
    rig.say(A)
    rig.st.store.put(RS.PURGE_PREFIX + "0" * 40, {"pseudonym": "0" * 40, "requestedAt": "x", "purgeBy": "not-a-date"})     # scans first
    rig.ask(A, "withdraw")
    rig.st.clock.advance(days=8)
    out = RS.purge_due(rig.st.store, rig.bucket.admin(), rig.st.clock())
    assert out == {"tickets": 1, "objects": 1, "failed": 1} and rig.paths(A) == []


def test_o5_when_a_documents_scope_was_used_bass_replies_are_not_stored(rig):
    rig.switch()
    rig.optin(A)
    body = {"action": "edit", "args": {"timeline_id": "t1", "text": "what does my note say", "library": [{"name": "n.txt", "text": "private notes"}]}}
    out = {"ok": True, "message": "Your note says: the quokka private notes rule.", "credits": {"spent": 1}}
    assert rig.share.record(A, "edit", body, out, ["add_nodes"]) is True
    rec = json.loads(rig.bucket.objects[rig.paths(A)[0]][0])
    assert rec["bass"] is None and rec["documents_used"] is True and "quokka" not in json.dumps(rec) and rec["user"] == "what does my note say"
    body["args"].pop("library")
    rig.share.record(A, "edit", body, out, [])
    rec2 = json.loads(rig.bucket.objects[rig.paths(A)[1]][0])
    assert rec2["documents_used"] is False and "quokka" in rec2["bass"]


def test_redact_is_linear_five_adversarial_strings_and_a_9_mb_body_each_finish_fast_and_the_share_alphabet_key_is_caught():
    import time
    bad = ["a." * 10000, "a-" * 10000, "1." * 10000, ("a. " * 6667)[:20000], ("1 " * 10000), "x@" * 10000, "http://" * 3000, "a/" * 10000, "9" * 20000, ("ab:" * 7000)[:20000]]
    for s in bad + ["a" * 9_000_000, "a. " * 3_000_000]:
        t0 = time.perf_counter()
        r = RS.redact(s)
        assert time.perf_counter() - t0 < 0.5, (s[:12], time.perf_counter() - t0)
        assert len(r) <= RS.MAX_FIELD_CHARS
    assert RS.redact("a" * 9_000_000) == "[key]"                                # one whitespace-free run over 300 characters is replaced whole
    assert "abcdefghjkmnpqrstuvwx" not in RS.redact("key abcdefghjkmnpqrstuvwxy here") and RS.redact("key abcdefghjkmnpqrstuvwxy") .endswith("[key]")       # 22 chars from the share alphabet, no digit
    assert RS.redact("a normal sentence about estoppel and reliance") == "a normal sentence about estoppel and reliance"


def test_o6_record_and_path_times_are_rounded_to_the_hour_and_a_counter_keeps_the_order(rig):
    rig.switch()
    rig.optin(A)
    rig.st.clock.advance(seconds=1234)                                        # 10:20:34 on the fake clock
    for i in range(3):
        rig.say(A, f"turn number {i} about estoppel")
        rig.st.clock.advance(seconds=7)
    paths = rig.paths(A)
    assert len(paths) == 3 and paths == sorted(paths)                         # sorted path order = turn order (counter)
    stamp = [pp.rsplit("/", 1)[1].split("_")[0] for pp in paths]
    assert len(set(stamp)) == 1 and re.fullmatch(r"\d{8}T\d{2}", stamp[0])      # the path carries the hour only: no minutes, no seconds
    recs = [json.loads(rig.bucket.objects[pp][0]) for pp in paths]
    assert all(r["at"].endswith(":00:00+00:00") or r["at"].endswith(":00:00") for r in recs) and len({r["at"] for r in recs}) == 1
    assert [r["user"] for r in recs] == [f"turn number {i} about estoppel" for i in range(3)]


def test_the_redaction_alphabet_is_alto_cloud_real_key_alphabet_so_a_22_char_key_with_an_i_is_caught():
    """The attack's last residual: the set had no 'i'. Compare against alto-cloud.js itself so the two cannot drift again."""
    js = (Path(__file__).resolve().parents[1] / "alto" / "cloud" / "alto-cloud.js").read_text("utf-8")
    real = re.search(r"const KEY_ALPHABET = '([^']+)'", js).group(1)
    assert set(RS._SHARE_ALPHABET) == set(real)
    for key in ("abcdefghijkmnpqrstuvwx", "iiiiiiiiiiiiiiiiiiiiii", "ijkmnpqrstuvwxyzabcdhi"):
        assert len(key) == 22
        assert RS.redact(f"my key is {key} ok") == "my key is [key] ok" and key not in RS.redact(key)
