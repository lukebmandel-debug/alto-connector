"""Bass Documents (alto/bass/documents.py + the proxy's `docs` action and `scope_id`): the library, its silos, its caps, the 7-day recovery,
and that a second account can never see, reach, or build from another account's documents. Mock engine only: no network, no key.
The Storage side of "a second user is refused" is tests/security/bass_documents_storage.test.mjs (emulator)."""
import base64
import datetime as dt
import json
import sys

import pytest

from bass_support import ROOT  # noqa: F401
from bass_beta_support import EMAIL, build_req, make_stack, req
from test_bass_beta_upload import ERIE, RULE, make_docx, make_pdf
from alto.bass import documents as D, mock_anthropic as M
from alto.bass.beta_guard import TERMS_PREFIX

sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
import firestore_store as FS  # noqa: E402

OTHER = "tester2@example.com"
A, B = "u_tester1", "u_tester2"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


class Blobs:
    def __init__(self):
        self.deleted = []

    def delete(self, path):
        self.deleted.append(path)


def stack(tmp):
    s = make_stack(tmp, emails=(EMAIL, OTHER))
    s.blobs = Blobs()
    s.svc.library.blobs = s.blobs
    return s


def docs(s, op, email=EMAIL, **args):
    return s.svc.handle(req({"action": "docs", "args": {"op": op, **args}}, email=email))


def scope(s, kind, name, email=EMAIL, **kw):
    out = docs(s, "add_scope", email=email, kind=kind, name=name, **kw)
    assert out["ok"], out
    return out["scope"]["id"]


def add_text(s, sid, name, text, email=EMAIL):
    s.clock.advance(seconds=6)                                                  # adds count in the account's 12 a minute
    out = docs(s, "add", email=email, scope_id=sid, name=name, text=text)
    assert out["ok"], out
    return out["file"]["id"]


def b64(raw):
    return base64.b64encode(raw).decode()


def sent(s):
    return json.dumps([r["body"] for r in s.mock.requests], ensure_ascii=False)


def library(s, email=EMAIL):
    return docs(s, "list", email=email)


@pytest.fixture
def torts(tmp_path):
    """Torts class with 2 files, a Torts outline with 1 own file, Contracts class with 1 file, a Midterm group with 1 file."""
    s = stack(tmp_path)
    s.torts = scope(s, "class", "Torts")
    s.outline = scope(s, "outline", "Torts outline", class_id=s.torts)
    s.contracts = scope(s, "class", "Contracts")
    s.group = scope(s, "group", "Midterm prep")
    s.f_mid = add_text(s, s.torts, "Midterm 2, graded.txt", "TORTS-MIDTERM causation was weak")
    s.f_fb = add_text(s, s.torts, "Professor Lin, feedback.txt", "TORTS-FEEDBACK proximate cause")
    s.f_own = add_text(s, s.outline, "Outline notes.txt", "OUTLINE-OWN negligence elements")
    s.f_con = add_text(s, s.contracts, "Contracts.txt", "CONTRACTS-ONLY mirror image rule")
    s.f_grp = add_text(s, s.group, "Plan.txt", "GROUP-ONLY study plan")
    return s


# -- silos (closed-system rule) -------------------------------------------------------------------------------------------------
def test_class_files_reach_every_outline_in_the_class_and_nothing_else(torts):
    s = torts
    u = docs(s, "using", scope_id=s.outline)
    assert [f["id"] for f in u["files"]] == [s.f_own, s.f_mid, s.f_fb]
    assert u["label"] == "Using: Torts outline, 3 documents"
    assert docs(s, "using", scope_id=s.torts)["label"] == "Using: Torts, 2 documents"
    assert [f["id"] for f in docs(s, "using", scope_id=s.contracts)["files"]] == [s.f_con]
    assert [f["id"] for f in docs(s, "using", scope_id=s.group)["files"]] == [s.f_grp]


def test_the_per_outline_off_switch_keeps_only_the_outlines_own_files(torts):
    s = torts
    other = scope(s, "outline", "Torts timeline", class_id=s.torts)
    assert docs(s, "class_docs", scope_id=s.outline, on=False)["ok"]
    assert [f["id"] for f in docs(s, "using", scope_id=s.outline)["files"]] == [s.f_own]
    assert len(docs(s, "using", scope_id=other)["files"]) == 2                 # the switch is per outline
    assert docs(s, "class_docs", scope_id=s.torts, on=False)["code"] == "docs_bad_request"     # a class has no such switch


def test_a_build_reads_only_the_active_scope_and_drops_whatever_the_page_sent(torts):
    s = torts
    s.mock.use(M.propose_chips())
    r = {"action": "propose", "args": {"materials": [], "scope_id": s.outline,
                                        "library": [{"name": "x", "text": "INJECTED-BY-PAGE"}]}}
    out = s.svc.handle(req(r))
    assert out["ok"] is True, out
    up = sent(s)
    for own in ("OUTLINE-OWN", "TORTS-MIDTERM", "TORTS-FEEDBACK"):
        assert own in up
    for never in ("CONTRACTS-ONLY", "GROUP-ONLY", "INJECTED-BY-PAGE"):
        assert never not in up


def test_the_documents_block_is_one_cached_block_ahead_of_the_request(torts):
    s = torts
    s.mock.use(M.propose_chips())
    assert s.svc.handle(req({"action": "propose", "args": {"scope_id": s.torts}}))["ok"]
    first = s.mock.message_requests[-1]["body"]["messages"][0]["content"]
    assert isinstance(first, list) and first[0].get("cache_control") == {"type": "ephemeral"}
    assert "TORTS-MIDTERM" in first[0]["text"] and "TORTS-MIDTERM" not in first[1]["text"]


def test_switched_off_and_deleted_documents_are_not_used(torts):
    s = torts
    docs(s, "use", doc_id=s.f_mid, on=False)
    docs(s, "delete", doc_id=s.f_fb)
    assert [f["id"] for f in docs(s, "using", scope_id=s.outline)["files"]] == [s.f_own]
    s.mock.use(M.propose_chips())
    s.svc.handle(req({"action": "propose", "args": {"scope_id": s.outline}}))
    up = sent(s)
    assert "OUTLINE-OWN" in up and "TORTS-MIDTERM" not in up and "TORTS-FEEDBACK" not in up


def test_rename_and_move_between_scopes(torts):
    s = torts
    assert docs(s, "rename", doc_id=s.f_con, name="Contracts, week 3.txt")["ok"]
    assert docs(s, "move", doc_id=s.f_con, scope_id=s.group)["ok"]
    assert sorted(f["name"] for f in docs(s, "using", scope_id=s.group)["files"]) == ["Contracts, week 3.txt", "Plan.txt"]
    assert docs(s, "using", scope_id=s.contracts)["files"] == []
    assert docs(s, "rename_scope", scope_id=s.group, name="Finals")["ok"]
    assert docs(s, "using", scope_id=s.group)["label"] == "Using: Finals, 2 documents"
    assert docs(s, "remove_scope", scope_id=s.group)["code"] == "docs_bad_request"            # not empty: nothing deleted by surprise
    assert docs(s, "remove_scope", scope_id=s.contracts)["ok"]


# -- two accounts: no user may ever see or reach another user's files --------------------------------------------------------
def test_a_second_account_sees_an_empty_library(torts):
    out = library(torts, email=OTHER)
    assert out["files"] == [] and out["scopes"] == [] and out["deleted"] == []
    assert "TORTS" not in json.dumps(out)


@pytest.mark.parametrize("op,args", [
    ("rename", lambda s: {"doc_id": s.f_mid, "name": "mine.txt"}), ("move", lambda s: {"doc_id": s.f_mid, "scope_id": s.torts}),
    ("use", lambda s: {"doc_id": s.f_mid, "on": False}), ("delete", lambda s: {"doc_id": s.f_mid}),
    ("restore", lambda s: {"doc_id": s.f_mid}), ("using", lambda s: {"scope_id": s.torts}),
    ("rename_scope", lambda s: {"scope_id": s.torts, "name": "x"}), ("class_docs", lambda s: {"scope_id": s.outline, "on": False}),
    ("remove_scope", lambda s: {"scope_id": s.contracts}), ("add", lambda s: {"scope_id": s.torts, "name": "x.txt", "text": "hi"}),
])
def test_a_second_account_cannot_reach_any_of_the_first_accounts_ids(torts, op, args):
    s = torts
    snap = lambda: json.dumps({k: v for k, v in s.store.docs.items() if k.startswith(("bass_docs/", "bass_doc_text/"))}, sort_keys=True)
    before = snap()
    out = docs(s, op, email=OTHER, **args(s))
    assert out["ok"] is False and out["code"] == "docs_not_found", out
    assert snap() == before                                                     # nothing written anywhere, A's library untouched


def test_a_second_account_cannot_build_from_the_first_accounts_scope(torts):
    s = torts
    s.mock.use(M.propose_chips())
    out = s.svc.handle(req({"action": "propose", "args": {"scope_id": s.torts}}, email=OTHER))
    assert out["code"] == "docs_not_found" and s.mock.requests == []
    out = s.svc.handle(req(build_req(scope_id=s.outline), email=OTHER))
    assert out["code"] == "docs_not_found" and s.mock.requests == []


def test_keys_are_built_from_the_verified_uid_only():
    for bad in ("", "a/b", "../x", "a b", None, 5):
        with pytest.raises(D.DocsError):
            D.index_key(bad)
    with pytest.raises(D.DocsError):
        D.text_key("u1", "../u2_x")
    assert FS._path("bass_docs/u1") == ("bass_docs", "u1")
    assert FS._path("bass_doc_text/u1_f1") == ("bass_doc_text", "u1_f1")


def test_the_docs_action_needs_the_allowlist_and_the_terms(tmp_path):
    s = stack(tmp_path)
    out = s.svc.handle(req({"action": "docs", "args": {"op": "list"}}, email="stranger@example.com"))
    assert out["code"] == "bass_off"
    s2 = make_stack(tmp_path / "t")                                             # terms not accepted
    s2.store.auto_terms = False
    assert s2.svc.handle(req({"action": "docs", "args": {"op": "list"}}))["code"] == "terms_required"
    assert not any(k.startswith(TERMS_PREFIX) for k in s2.store.docs)


def test_adds_count_in_the_accounts_limit_but_tidying_has_its_own(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Torts")
    outs = [docs(s, "add", scope_id=c, name=f"{i}.txt", text="n") for i in range(13)]
    assert [o.get("code") for o in outs].count("busy") >= 1 and s.mock.requests == []
    s.clock.advance(seconds=61)
    assert all(docs(s, "list")["ok"] for _ in range(25))                      # past the 12 a minute (the IP limit is 30)


def test_library_management_spends_nothing_and_sends_nothing(torts):
    s = torts
    before = s.ledger.balance_mc(A)
    docs(s, "list"); docs(s, "using", scope_id=s.outline); docs(s, "rename", doc_id=s.f_own, name="n.txt")
    assert s.mock.requests == [] and s.ledger.balance_mc(A) == before


# -- the 60,000-character limit ----------------------------------------------------------------------------------------------
def test_over_the_per_action_limit_is_refused_with_nothing_upstream(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Evidence")
    add_text(s, c, "a.txt", "x" * 40_000)
    add_text(s, c, "b.txt", "y" * 30_000)
    u = docs(s, "using", scope_id=c)
    assert u["over"] is True and u["chars"] == 70_000
    s.mock.use(M.propose_chips())
    out = s.svc.handle(req({"action": "propose", "args": {"scope_id": c}}))
    assert out["code"] == "docs_over_limit" and out["message"] == D.MESSAGES["docs_over_limit"] and s.mock.requests == []
    docs(s, "use", doc_id=docs(s, "list")["files"][1]["id"], on=False)
    assert s.svc.handle(req({"action": "propose", "args": {"scope_id": c}}))["ok"]


def test_one_file_over_the_limit_is_refused_at_upload(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Evidence")
    out = docs(s, "add", scope_id=c, name="huge.txt", text="z" * 60_001)
    assert out["code"] == "docs_too_long" and library(s)["files"] == []


# -- caps -----------------------------------------------------------------------------------------------------------------------
def test_count_cap_includes_recoverable_files(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Torts")
    ids = [add_text(s, c, f"{i}.txt", "notes") for i in range(D.MAX_FILES)]
    s.clock.advance(seconds=60)
    assert docs(s, "add", scope_id=c, name="one more.txt", text="n")["code"] == "docs_full"
    docs(s, "delete", doc_id=ids[0])
    assert docs(s, "add", scope_id=c, name="one more.txt", text="n")["code"] == "docs_full"
    assert library(s)["caps"]["files"] == D.MAX_FILES


def test_size_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "MAX_BYTES", 10)
    s = stack(tmp_path)
    c = scope(s, "class", "Torts")
    add_text(s, c, "a.txt", "12345678")
    assert docs(s, "add", scope_id=c, name="b.txt", text="12345")["code"] == "docs_too_big"


# -- 7-day recovery ---------------------------------------------------------------------------------------------------------------
def test_deleted_files_can_be_recovered_for_seven_days_then_are_gone(torts):
    s = torts
    assert docs(s, "delete", doc_id=s.f_mid)["recover_days"] == 7
    lib = library(s)
    assert [f["id"] for f in lib["deleted"]] == [s.f_mid] and lib["deleted"][0]["days_left"] == 7
    s.clock.advance(days=6, seconds=3600)
    assert library(s)["deleted"][0]["days_left"] == 1
    assert docs(s, "restore", doc_id=s.f_mid)["ok"]
    assert s.f_mid in [f["id"] for f in docs(s, "using", scope_id=s.torts)["files"]]
    docs(s, "delete", doc_id=s.f_mid)
    s.clock.advance(days=7)
    lib = library(s)
    assert lib["deleted"] == [] and s.f_mid not in [f["id"] for f in lib["files"]]
    assert s.store.get(D.text_key(A, s.f_mid)) is None                           # the text is erased too (deleted, not blanked)
    assert s.blobs.deleted == [D.storage_path(A, s.f_mid)]                       # and the original
    assert docs(s, "restore", doc_id=s.f_mid)["code"] == "docs_not_found"


def test_a_deleted_file_cannot_be_renamed_moved_or_switched_on(torts):
    s = torts
    docs(s, "delete", doc_id=s.f_mid)
    for op, a in (("rename", {"name": "x.txt"}), ("move", {"scope_id": s.group}), ("use", {"on": True}), ("delete", {})):
        assert docs(s, op, doc_id=s.f_mid, **a)["code"] == "docs_not_found"


# -- uploads through the proxy's extractor --------------------------------------------------------------------------------------
def test_pdf_and_docx_become_text_in_the_library(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Civ Pro")
    p = docs(s, "add", scope_id=c, name="Outline.pdf", file_b64=b64(make_pdf([ERIE, RULE])))
    w = docs(s, "add", scope_id=c, name="Feedback.docx", file_b64=b64(make_docx(paras=["Professor: work on Erie."])))
    assert p["ok"] and w["ok"], (p, w)
    assert p["file"]["type"] == "pdf" and p["file"]["path"] == f"users/{A}/bass/{p['file']['id']}"
    assert "Twombly" in s.store.get(D.text_key(A, p["file"]["id"]))["text"]
    assert "work on Erie" in s.store.get(D.text_key(A, w["file"]["id"]))["text"]
    assert "file_b64" not in json.dumps(s.store.docs)                           # bytes never stored server-side
    assert s.mock.requests == []


def test_a_scanned_pdf_gets_the_friendly_message(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Civ Pro")
    out = docs(s, "add", scope_id=c, name="scan.pdf", file_b64=b64(make_pdf(["", ""])))
    assert out["code"] == "upload_scanned" and "scanned PDF" in out["message"] and library(s)["files"] == []


def test_a_renamed_file_is_refused(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Civ Pro")
    assert docs(s, "add", scope_id=c, name="notes.pdf", file_b64=b64(b"PK\x03\x04 not a pdf"))["code"] == "upload_unreadable"
    assert docs(s, "add", scope_id=c, name="x.exe", file_b64=b64(b"MZ"))["code"] == "upload_unsupported"


@pytest.mark.parametrize("name,raw", [
    ("board.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50), ("photo.jpg", b"\xff\xd8\xff" + b"0" * 50), ("photo.jpeg", b"\xff\xd8\xff" + b"0" * 50),
    ("any.heic", b"not an image at all"), ("riff.webp", b"RIFF\x00\x00\x00\x00WAVEfmt "), ("real.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 "),
])
def test_d4_pictures_are_refused_in_the_beta_with_nothing_written(tmp_path, name, raw):
    """D4 (security review): no reader for pictures in the beta, so no picture enters the library, whatever its bytes. Unlisted, it cannot
    reach Storage either (storage.rules accept only a fid the proxy listed)."""
    s = stack(tmp_path)
    c = scope(s, "class", "Torts")
    before = {k: v for k, v in s.store.docs.items() if k.startswith(("bass_docs/", "bass_doc_text/"))}
    out = docs(s, "add", scope_id=c, name=name, file_b64=b64(raw))
    assert out["ok"] is False and out["code"] == "upload_unsupported", out
    assert {k: v for k, v in s.store.docs.items() if k.startswith(("bass_docs/", "bass_doc_text/"))} == before
    assert library(s)["files"] == []


def test_unknown_fields_and_ops_are_refused(torts):
    s = torts
    assert docs(s, "nope")["code"] == "docs_bad_request"
    assert docs(s, "list", uid="u_tester2")["code"] == "docs_bad_request"     # no way to name another account
    assert docs(s, "rename", doc_id=s.f_mid, name="")["code"] == "docs_bad_name"
    assert docs(s, "rename", doc_id=s.f_mid, name="x" * 121)["code"] == "docs_bad_name"


# -- edit carries the documents, the kept conversation does not double them --------------------------------------------------------
def test_edit_with_a_scope_sends_the_documents_and_keeps_a_marker(torts):
    s = torts
    s.mock.use(M.edit_card("t1", {"id": "n1", "title": "Causation"}))
    out = s.svc.handle(req({"action": "edit", "args": {"timeline_id": "t1", "text": "Add a card on causation.", "scope_id": s.outline}}))
    assert out["ok"] is True, out
    assert "TORTS-FEEDBACK" in sent(s)
    kept = json.dumps(s.acts.conversations[(A, "t1")])
    assert "TORTS-FEEDBACK" not in kept and "documents were shown here" in kept


# -- Firestore's 1 MiB document limit (Strategy's Documents plan) ------------------------------------------------------------------
def test_text_in_a_four_byte_script_at_the_limit_is_stored_whole(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Torts")
    text = "\U0001d538" * D.MAX_ACTION_CHARS                                    # 60,000 characters x 4 bytes = 240,000 bytes
    fid = add_text(s, c, "math.txt", text)
    assert s.store.get(D.text_key(A, fid))["text"] == text                      # whole, never cut


def test_300000_characters_of_non_english_script_is_refused_with_nothing_written(tmp_path):
    s = stack(tmp_path)
    c = scope(s, "class", "Torts")
    before = json.dumps(s.store.docs, sort_keys=True, ensure_ascii=False)
    out = docs(s, "add", scope_id=c, name="notes.txt", text="漢" * 300_000)      # 900,000 bytes of UTF-8
    assert out["code"] == "docs_too_long" and out["message"] == D.MESSAGES["docs_too_long"]
    after = json.dumps({k: v for k, v in s.store.docs.items() if not k.startswith("bass_beta/meta/")}, sort_keys=True, ensure_ascii=False)
    assert after == json.dumps({k: v for k, v in json.loads(before).items() if not k.startswith("bass_beta/meta/")}, sort_keys=True, ensure_ascii=False)


def test_the_store_refuses_any_document_over_1_mib_and_the_page_hears_it(tmp_path, monkeypatch):
    from alto.bass import beta_store as BS
    s = stack(tmp_path)
    with pytest.raises(BS.StoreError):
        s.store.put("bass_docs/x", {"t": "x" * (BS.MAX_DOC_BYTES + 1)})
    with pytest.raises(BS.StoreError):                                          # inside a transaction too: nothing lands
        s.store.run_transaction(lambda txn: txn.put("bass_docs/y", {"t": "é" * BS.MAX_DOC_BYTES}))
    assert "bass_docs/y" not in s.store.docs
    c = scope(s, "class", "Torts")
    monkeypatch.setattr(D, "MAX_TEXT_BYTES", 10 ** 9)                           # if the library's own check ever let one through...
    monkeypatch.setattr(D, "MAX_ACTION_CHARS", 10 ** 9)
    out = docs(s, "add", scope_id=c, name="big.txt", text="漢" * 400_000)
    assert out["ok"] is False and out["code"] == "docs_not_saved" and "nothing was added" in out["message"]     # ...never silent
    assert library(s)["files"] == []


# -- 7-day recovery: hidden at once, erased by the daily job after 7 days, erased at once on account deletion -------------------------
def test_delete_hides_the_document_from_bass_at_once(torts):
    s = torts
    docs(s, "delete", doc_id=s.f_mid)
    s.mock.use(M.propose_chips())
    s.svc.handle(req({"action": "propose", "args": {"scope_id": s.torts}}))
    assert "TORTS-MIDTERM" not in sent(s) and "TORTS-FEEDBACK" in sent(s)


def test_the_daily_job_erases_after_seven_days_even_for_accounts_nobody_opens(torts):
    s = torts
    docs(s, "delete", doc_id=s.f_mid)
    s.clock.advance(seconds=60)
    fid_b = add_text(s, scope(s, "class", "Evidence", email=OTHER), "b.txt", "OTHER-ACCOUNT", email=OTHER)
    docs(s, "delete", email=OTHER, doc_id=fid_b)
    s.clock.advance(days=6)
    out = D.purge_expired(s.store, s.cfg, s.clock, blobs=s.blobs)
    assert out == {"accounts": 2, "erased": 0, "failed": 0}                   # day 6: still recoverable
    assert s.store.get(D.text_key(A, s.f_mid)) is not None
    s.clock.advance(days=1)
    out = D.purge_expired(s.store, s.cfg, s.clock, blobs=s.blobs)
    assert out == {"accounts": 2, "erased": 2, "failed": 0}
    assert s.store.get(D.text_key(A, s.f_mid)) is None and s.store.get(D.text_key(B, fid_b)) is None
    assert sorted(s.blobs.deleted) == sorted([D.storage_path(A, s.f_mid), D.storage_path(B, fid_b)])
    assert s.f_fb in s.store.get(D.index_key(A))["files"]                      # live files untouched
    assert "TORTS" not in json.dumps(out)                                       # counts only


def test_account_deletion_erases_every_document_at_once(torts):
    s = torts
    docs(s, "delete", doc_id=s.f_mid)                                           # one in its recovery window, the rest live
    fids = list(s.store.get(D.index_key(A))["files"])
    n = s.svc.library.erase_account(A)
    assert n == len(fids) == 5
    assert s.store.get(D.index_key(A)) is None
    assert all(s.store.get(D.text_key(A, f)) is None for f in fids)
    assert sorted(s.blobs.deleted) == sorted(D.storage_path(A, f) for f in fids)
    assert library(s)["files"] == [] and library(s, email=OTHER)["files"] == []


def test_the_erase_job_entry_point(torts):
    sys.path.insert(0, str(ROOT / "tools"))
    import bass_docs_purge as J
    s = torts
    docs(s, "delete", doc_id=s.f_mid)
    s.clock.advance(days=7)
    assert J.run(s.store, s.blobs, clock=s.clock) == {"accounts": 1, "erased": 1, "failed": 0}
    assert J.run(s.store, s.blobs, erase_account=A, clock=s.clock) == {"erased": 4}
    with pytest.raises(SystemExit):
        J.run(s.store, erase_account="../x")


# -- D5 / D6: the deploy entry points (deploy/bass-proxy/main.py) on the same mock store ----------------------------------------------------
@pytest.fixture
def entry(torts, monkeypatch):
    sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))
    import main as MAIN
    monkeypatch.setattr(MAIN, "_docs_env", lambda: (torts.store, torts.blobs))
    monkeypatch.setattr(MAIN, "_clock", torts.clock)
    return MAIN


def test_d6_the_auth_user_deleted_trigger_erases_every_document_record_marked_ones_included(torts, entry):
    s = torts
    docs(s, "delete", doc_id=s.f_mid)
    fids = list(s.store.get(D.index_key(A))["files"])
    other_before = library(s, email=OTHER)
    assert entry.bass_docs_account_deleted({"uid": A}) == {"erased": 5, "drive": False}
    assert s.store.get(D.index_key(A)) is None
    assert not [k for k in s.store.docs if k.startswith(("bass_doc_text/" + A + "_", "bass_docs/" + A))]
    assert sorted(s.blobs.deleted) == sorted(D.storage_path(A, f) for f in fids)
    assert library(s, email=OTHER) == other_before                              # nobody else touched
    for bad in ({}, {"uid": ""}, {"uid": "a/b"}, None):
        with pytest.raises(ValueError):
            entry.bass_docs_account_deleted(bad)


def test_d5_the_daily_http_entry_erases_after_seven_days(torts, entry):
    from types import SimpleNamespace
    s = torts
    docs(s, "delete", doc_id=s.f_mid)
    s.clock.advance(days=7)
    body, status, _ = entry.bass_docs_daily(SimpleNamespace(method="POST"))
    assert status == 200 and json.loads(body) == {"accounts": 1, "erased": 1, "failed": 0}
    assert s.store.get(D.text_key(A, s.f_mid)) is None
    assert entry.bass_docs_daily(SimpleNamespace(method="GET"))[1] == 405
