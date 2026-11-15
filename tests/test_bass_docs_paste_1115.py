"""Documents "Paste text" + the oversize-PDF hint (Board B-1115-143853, B-1115-144103)."""
import json

import pytest

pytest.importorskip("pypdf")        # (the stack needs the extractor stack; public CI has neither it nor the SDK)
from bass_support import ROOT  # noqa: F401
from bass_beta_support import EMAIL, make_stack, req
from alto.bass import documents as D, errors as E
from alto.build import bass_ui_docs as UI

A = "u_tester1"
HINT = "If you printed this from a web page, save it as text instead."


def docs(s, op, **a):
    return s.svc.handle(req({"action": "docs", "args": {"op": op, **a}}))


def test_panel_offers_paste_text_through_the_existing_text_add():
    js = UI.DOCS_JS
    assert "Paste text" in js and "Pasted notes.txt" in js and "bs-dpt" in js
    assert "{op:'add',scope_id:d.sel,name:pn,text:" in js                 # the same op an uploaded .txt uses; no new server op
    assert "upload_no_text" in js and "250,000" in js and "60,000" not in js
    assert "op:'paste" not in js


def test_a_pdf_too_big_says_to_save_it_as_text_and_other_files_do_not(tmp_path):
    s = make_stack(tmp_path, emails=(EMAIL,))
    c = docs(s, "add_scope", kind="class", name="Torts")["scope"]["id"]
    big = docs(s, "add", scope_id=c, name="Page.pdf", file_b64="A" * 7_000_000)
    assert big["code"] == "upload_too_big" and HINT in big["message"] and "paste the text" in big["message"]
    s.clock.advance(seconds=6)
    other = docs(s, "add", scope_id=c, name="Notes.docx", file_b64="A" * 7_000_000)
    assert other["code"] == "upload_too_big" and HINT not in other["message"]
    assert other["message"] == E.POLICIES["upload_too_big"].user_message
    assert E.too_big_message(["x.PDF"]).endswith(HINT) and E.too_big_message([]) == other["message"]
    assert HINT in UI.DOCS_JS and "upload_too_big_pdf" in UI.DOCS_JS


def test_per_file_too_big_and_account_full_messages_differ(tmp_path, monkeypatch):
    assert D.MESSAGES["docs_too_big"] != E.POLICIES["upload_too_big"].user_message
    assert "5 MB" not in D.MESSAGES["docs_too_big"] and "library" in D.MESSAGES["docs_too_big"]
    s = make_stack(tmp_path, emails=(EMAIL,))
    monkeypatch.setattr(D, "MAX_BYTES", 10)
    c = docs(s, "add_scope", kind="class", name="Torts")["scope"]["id"]
    docs(s, "add", scope_id=c, name="a.txt", text="12345678")
    s.clock.advance(seconds=6)
    acct = docs(s, "add", scope_id=c, name="b.txt", text="12345")
    s.clock.advance(seconds=6)
    per_file = docs(s, "add", scope_id=c, name="c.pdf", file_b64="A" * 7_000_000)
    assert acct["code"] == "docs_too_big" and per_file["code"] == "upload_too_big" and acct["message"] != per_file["message"]
