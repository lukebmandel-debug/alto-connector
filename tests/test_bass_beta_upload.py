"""Upload extraction (bench-tl-1 job, 2026-10-30): a PDF / .docx sent as material {name, kind, text:"", file_b64} becomes text on the proxy,
AFTER the allowlist, terms and allowance checks and BEFORE any hold or upstream call. Tiny fixtures are built here (no files on disk, no
network, mock only): a PDF written by hand, a .docx written with zipfile, a zip bomb, an encrypted PDF (pypdf's writer), a corrupt file,
a scan (no text), an oversized upload, a stand-in worker that never ends (the deadline kills it) and a two-account case.
The worker is the REAL one, run as a child process (the pinned pypdf is in the Bass test venv)."""
import base64
import io
import json
import sys
import time
import zipfile
from dataclasses import replace

import pytest

pypdf = pytest.importorskip("pypdf")

from bass_support import ROOT  # noqa: F401
from bass_beta_support import EMAIL, FakeClock, make_stack, req
from test_bass_beta_proxy import FakeSecrets, FakeVerifier, ORIGIN, post
from alto.bass import extract as X, extract_worker as W, mock_anthropic as M
from alto.bass.beta_config import BetaConfig
from alto.bass.beta_guard import UPLOAD_ACTIONS
from alto.bass.beta_ledger import confirm_key, pc_key
from alto.bass.beta_proxy import Proxy
from alto.bass.beta_store import FakeStore
from alto.bass.errors import POLICIES
from alto.bass.tools import ToolBox
from alto.store.local import LocalStore

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
ERIE = "Erie doctrine: federal courts in diversity apply state substantive law."
RULE = "Twombly plausibility standard governs a motion to dismiss."


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setenv("ALTO_NO_NETWORK", "1")


# -- fixtures built in the test -------------------------------------------------------------------------------------------
def make_pdf(pages):
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for i, t in enumerate(pages):
        content = f"BT /F1 12 Tf 72 720 Td ({t}) Tj ET".encode() if t else b""
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n" + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()


def encrypted_pdf():
    w = pypdf.PdfWriter()
    w.add_blank_page(200, 200)
    w.encrypt("secret", algorithm="RC4-128")
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def doc_xml(paras=(), rows=()):
    body = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in paras)
    for row in rows:
        body += "<w:tbl><w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr></w:tbl>"
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{body}</w:body></w:document>'.encode()


def make_docx(xml=None, paras=(), rows=(), extra=0, name="word/document.xml"):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(name, xml if xml is not None else doc_xml(paras, rows))
        for i in range(extra):
            z.writestr(f"word/media/i{i}.bin", b"x")
    return b.getvalue()


def mat(name, raw, **kw):
    return {"name": name, "kind": "notes", "text": "", "file_b64": base64.b64encode(raw).decode(), **kw}


def body(action, *mats, **args):
    a = {"materials": list(mats)}
    a.update(args)
    return {"action": action, "args": a}


class Runs:
    """Wraps the real runner and counts the worker runs."""

    def __init__(self, real=None):
        self.n, self.real = 0, real

    def __call__(self, kind, data, lim, timeout):
        self.n += 1
        return (self.real or X.subprocess_runner)(kind, data, lim, timeout)


def stack(tmp, runner=None, worker_cmd=None, **over):
    s = make_stack(tmp, **over)
    s.runs = Runs()
    s.svc.extractor = X.Extractor(s.cfg, runner=runner or s.runs, worker_cmd=worker_cmd)
    return s


def refused(out, code):
    return (out["ok"] is False and out["code"] == code and out["status"] == "refused" and out["message"] == POLICIES[code].user_message
            and out["retryable"] is False and "Traceback" not in json.dumps(out))


def counters(s):
    return {k: v for k, v in s.store.docs.items() if k.startswith("bass_beta/day/") or k.startswith("bass_beta/pc/")}


def upstream_text(s):
    return json.dumps([r["body"] for r in s.mock.requests], ensure_ascii=False)


# -- the happy paths --------------------------------------------------------------------------------------------------------
def test_a_pdf_becomes_text_and_only_text_reaches_claude(tmp_path):
    s = stack(tmp_path)
    s.mock.use(M.propose_chips())
    out = s.svc.handle(req(body("propose", mat("Civ Pro outline.pdf", make_pdf([ERIE, RULE])))))
    assert out["ok"] is True, out
    sent = upstream_text(s)
    assert "Erie doctrine" in sent and "Twombly" in sent and "Civ Pro outline.pdf" in sent
    assert '"type": "document"' not in sent and "file_b64" not in sent and "application/pdf" not in sent       # no native PDF block, no raw bytes
    assert s.runs.n == 1


def test_a_docx_with_a_table_becomes_text(tmp_path):
    s = stack(tmp_path)
    s.mock.use(M.propose_chips())
    out = s.svc.handle(req(body("propose", mat("Week 3.docx", make_docx(paras=[ERIE, "Second paragraph here."], rows=[["Case", "Rule"], ["Erie", "state law"]])))))
    assert out["ok"] is True, out
    sent = upstream_text(s)
    assert "Erie doctrine" in sent and "Second paragraph here." in sent and "Case | Rule" in sent and "Erie | state law" in sent


def test_text_materials_are_untouched_and_start_no_worker(tmp_path):
    s = stack(tmp_path)
    s.mock.use(M.propose_chips())
    out = s.svc.handle(req(body("propose", {"name": "notes.txt", "kind": "notes", "text": ERIE})))
    assert out["ok"] is True and s.runs.n == 0 and "Erie doctrine" in upstream_text(s)


def test_the_extracted_text_counts_into_the_estimate(tmp_path):
    s = stack(tmp_path)
    small = s.svc.handle(req(body("estimate", mat("a.pdf", make_pdf(["x" * 60])), kind="build")))
    big = s.svc.handle(req(body("estimate", mat("b.pdf", make_pdf(["word " * 800])), kind="build")))
    assert small["ok"] is True and big["ok"] is True and big["estimate_credits"] >= small["estimate_credits"]
    assert s.runs.n == 2 and "estimate" in UPLOAD_ACTIONS


# -- every failure: friendly code, nothing upstream, no hold --------------------------------------------------------------------
def bomb_ratio():
    return make_docx(xml=b'<?xml version="1.0"?><w:document ' + NS.encode() + b'><w:body>' + b" " * 20_000_000 + b"</w:body></w:document>")


def xml_member_too_big():
    return make_docx(xml=b'<?xml version="1.0"?><w:document ' + NS.encode() + b'><w:body>' + bytes(range(256)) * 40_000 + b"</w:body></w:document>")


CASES = [
    ("encrypted pdf", lambda: mat("a.pdf", encrypted_pdf()), "upload_encrypted", {}),
    ("scanned pdf, no text", lambda: mat("scan.pdf", make_pdf(["", ""])), "upload_scanned", {}),
    ("corrupt pdf", lambda: mat("a.pdf", b"%PDF-1.4\nthis is not a pdf at all" * 3), "upload_unreadable", {}),
    ("corrupt docx", lambda: mat("a.docx", b"PK\x03\x04" + b"junk" * 50), "upload_unreadable", {}),
    ("docx without document.xml", lambda: mat("a.docx", make_docx(name="word/other.xml")), "upload_unreadable", {}),
    ("too many pdf pages", lambda: mat("a.pdf", make_pdf([ERIE] * 4)), "upload_too_many_pages", {"pdf_max_pages": 3}),
    ("pdf text too long", lambda: mat("a.pdf", make_pdf([ERIE * 3])), "upload_too_long", {"extract_max_chars": 100}),
    ("docx text too long", lambda: mat("a.docx", make_docx(paras=[ERIE] * 5)), "upload_too_long", {"extract_max_chars": 100}),
    ("zip bomb by ratio", lambda: mat("a.docx", bomb_ratio()), "upload_unreadable", {}),
    ("document.xml over its hard limit", lambda: mat("a.docx", xml_member_too_big()), "upload_unreadable", {"docx_xml_max_bytes": 5_000_000}),
    ("too many zip members", lambda: mat("a.docx", make_docx(paras=[ERIE], extra=30)), "upload_unreadable", {"docx_max_members": 10}),
    ("doctype with entities", lambda: mat("a.docx", make_docx(xml=b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><w:document ' + NS.encode() + b'><w:body><w:p><w:r><w:t>&a;</w:t></w:r></w:p></w:body></w:document>')), "upload_unreadable", {}),
    ("utf-16 xml hiding a doctype", lambda: mat("a.docx", make_docx(xml=doc_xml(paras=[ERIE]).decode().encode("utf-16"))), "upload_unreadable", {}),
    ("deeply nested xml", lambda: mat("a.docx", make_docx(xml=b'<?xml version="1.0"?><w:document ' + NS.encode() + b'><w:body>' + b"<w:p>" * 300 + b"</w:body></w:document>")), "upload_unreadable", {}),
    ("oversized file", lambda: mat("a.pdf", make_pdf([ERIE])), "upload_too_big", {"upload_max_file_bytes": 500}),
    ("oversized total", lambda: [mat("a.pdf", make_pdf([ERIE])), mat("b.pdf", make_pdf([RULE]))], "upload_too_big", {"upload_max_file_bytes": 700, "upload_max_total_bytes": 1000}),
    ("too many files", lambda: [mat(f"{i}.pdf", make_pdf([ERIE])) for i in range(3)], "upload_too_big", {"upload_max_files": 2}),
    ("name says pdf, bytes say docx", lambda: mat("a.pdf", make_docx(paras=[ERIE])), "upload_unreadable", {}),
    ("unsupported type", lambda: mat("slides.pptx", make_docx(paras=[ERIE])), "upload_unsupported", {}),
    ("old .doc", lambda: mat("old.doc", b"\xd0\xcf\x11\xe0" + b"x" * 100), "upload_unsupported", {}),
    ("not base64", lambda: {"name": "a.pdf", "kind": "notes", "text": "", "file_b64": "%%%not base64%%%"}, "upload_unreadable", {}),
    ("file_b64 not a string", lambda: {"name": "a.pdf", "kind": "notes", "text": "", "file_b64": 12345}, "upload_unreadable", {}),
    ("flagged but no bytes", lambda: {"name": "a.pdf", "kind": "notes", "text": "", "needs_extraction": True}, "upload_unreadable", {}),
]


@pytest.mark.parametrize("label,make,code,over", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("action", ["propose", "build"])
def test_every_failure_fails_closed_with_nothing_upstream_and_no_hold(tmp_path, label, make, code, over, action):
    s = stack(tmp_path, **over)
    s.svc.handle(req({"action": "balance", "args": {}}))                  # the allowance is granted; this is the baseline
    books_of = lambda: json.dumps({k: v for k, v in s.store.docs.items() if not k.startswith("bass_beta/meta/")}, sort_keys=True)  # the metadata log may add a line
    base, books = counters(s), books_of()
    m = make()
    args = {"materials": m if isinstance(m, list) else [m]}
    if action == "build":
        args.update(chips={"title": "T", "acts": [{"label": "A"}]}, consent=True, accepted=True)
    out = s.svc.handle(req({"action": action, "args": args}))
    assert refused(out, code), (label, out)
    assert s.mock.requests == [] and counters(s) == base and books_of() == books    # no upstream call, no hold, nothing written
    line = s.svc.meta.lines[-1]
    assert line["code"] == code and set(line) <= {"t", "uid", "action", "status", "code", "credits_spent", "credits_refunded", "tool_calls", "out_tokens"}
    assert "a.pdf" not in json.dumps(s.svc.meta.lines) and "Erie" not in json.dumps(s.svc.meta.lines)       # metadata only


def test_a_runaway_parse_is_killed_at_the_deadline_and_refused(tmp_path):
    s = stack(tmp_path, worker_cmd=[sys.executable, "-I", "-c", "import time; time.sleep(60)"], extract_timeout_s=1.0)
    s.svc.extractor.runner = lambda kind, data, lim, t: X.subprocess_runner(kind, data, lim, t, [sys.executable, "-I", "-c", "import time; time.sleep(60)"])
    t0 = time.time()
    out = s.svc.handle(req(body("propose", mat("a.pdf", make_pdf([ERIE])))))
    assert refused(out, "upload_unreadable") and time.time() - t0 < 10 and s.mock.requests == []


def test_one_deadline_covers_all_the_files_of_a_request(tmp_path):
    clock = {"t": 0.0}

    def slow(kind, data, lim, timeout):
        clock["t"] += 15.0                                                # each file "takes" 15 s of a 20 s deadline
        return {"ok": True, "text": "Some real text here, long enough."}
    s = stack(tmp_path, runner=slow)
    s.svc.extractor = X.Extractor(s.cfg, runner=slow, clock=lambda: clock["t"])
    out = s.svc.handle(req(body("propose", mat("a.pdf", make_pdf([ERIE])), mat("b.pdf", make_pdf([RULE])))))
    assert refused(out, "upload_unreadable") and s.mock.requests == []


def test_a_worker_that_crashes_or_answers_junk_is_a_refusal(tmp_path):
    for cmd in ([sys.executable, "-I", "-c", "import sys; sys.exit(3)"], [sys.executable, "-I", "-c", "print('not json')"],
                [sys.executable, "-I", "-c", "print('[1]')"], ["/nonexistent/worker"]):
        s = stack(tmp_path)
        s.svc.extractor.runner = lambda kind, data, lim, t, cmd=cmd: X.subprocess_runner(kind, data, lim, t, cmd)
        assert refused(s.svc.handle(req(body("propose", mat("a.pdf", make_pdf([ERIE]))))), "upload_unreadable")


def test_a_stub_that_returns_more_text_than_the_cap_is_still_refused(tmp_path):
    s = stack(tmp_path, runner=lambda k, d, l, t: {"ok": True, "text": "x" * 400_000})
    assert refused(s.svc.handle(req(body("propose", mat("a.pdf", make_pdf([ERIE]))))), "upload_too_long")


# -- order: nobody who is not entitled costs a parse ---------------------------------------------------------------------------
def test_an_unlisted_or_unaccepted_account_costs_no_parsing(tmp_path):
    s = stack(tmp_path)
    m = body("propose", mat("a.pdf", make_pdf([ERIE])))
    assert s.svc.handle(req(m, email="stranger@example.com"))["code"] == "bass_off"
    s.store.auto_terms = False
    assert s.svc.handle(req(m))["code"] == "terms_required"
    assert s.runs.n == 0 and s.mock.requests == []


def test_a_closed_bass_or_used_up_pool_costs_no_parsing(tmp_path):
    s = stack(tmp_path)
    m = body("propose", mat("a.pdf", make_pdf([ERIE])))
    pid = s.ledger.period()
    s.store.put(pc_key(pid), {"period": pid, "spent_mc": s.cfg.ceiling_mc, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": []})
    assert s.svc.handle(req(m))["code"] == "beta_credits_used"
    s.store.put(pc_key(pid), {"period": pid, "spent_mc": 0, "reserved_mc": 0, "res": {}, "alerted": [], "spend_log": []})
    s.kill.trip("test")
    assert s.svc.handle(req(m))["code"] == "bass_paused"
    assert s.runs.n == 0 and s.mock.requests == []


# -- two accounts ----------------------------------------------------------------------------------------------------------------
def test_a_extracted_text_never_reaches_b(tmp_path):
    s = stack(tmp_path, emails=(EMAIL, "b@example.com"))
    s.mock.use(M.propose_chips())
    secret = "A-ONLY-PRIVILEGED-MEMO-9931 settlement figures"
    a = s.svc.handle(req(body("propose", mat("a-private.pdf", make_pdf([secret])))))
    assert a["ok"] is True and "A-ONLY-PRIVILEGED-MEMO-9931" in upstream_text(s)
    n = len(s.mock.requests)
    s.mock.use(M.propose_chips())
    b = s.svc.handle(req(body("propose", mat("b-own.docx", make_docx(paras=[ERIE])), {"name": "a-private.pdf", "kind": "notes", "text": "", "needs_extraction": True}),
                         email="b@example.com"))
    assert refused(b, "upload_unreadable")                                # B naming A's file gets nothing: the proxy keeps no copy of any upload
    c = s.svc.handle(req(body("propose", mat("b-own.docx", make_docx(paras=[ERIE]))), email="b@example.com"))
    assert c["ok"] is True
    assert "A-ONLY-PRIVILEGED-MEMO-9931" not in json.dumps([r["body"] for r in s.mock.requests[n:]], ensure_ascii=False)
    assert not hasattr(s.svc.extractor, "cache")


# -- through the HTTP door, the body cap, the config ------------------------------------------------------------------------------
def http_proxy(tmp_path, **over):
    store, clock = FakeStore(auto_terms=True), FakeClock()
    cfg = BetaConfig(testers=10, allowlist=frozenset({EMAIL}), **over)
    store.put(confirm_key(cfg.period_id(clock())), {"confirmed": True})
    p = Proxy(cfg, store, FakeVerifier(), FakeSecrets(), ToolBox(LocalStore(tmp_path / "store")), clock=clock, origins=[ORIGIN])
    p.store = store
    return p


def test_a_pdf_through_the_http_door_and_the_request_cap(tmp_path):
    p = http_proxy(tmp_path)
    p.mock.use(M.propose_chips())
    st, _, out = post(p, body("propose", mat("a.pdf", make_pdf([ERIE]))))
    assert st == 200 and out["ok"] is True and "Erie doctrine" in upstream_text(p)
    st, _, out = p.handle_http("POST", {"Authorization": "Bearer tok-ok"}, b"x" * (p.cfg.max_request_bytes + 1))
    assert st == 413


def test_the_new_numbers_are_config_and_checked():
    c = BetaConfig(testers=10)
    assert (c.upload_max_file_bytes, c.upload_max_total_bytes, c.upload_max_files, c.pdf_max_pages) == (5_000_000, 6_000_000, 5, 200)
    assert c.problems() == []
    assert BetaConfig(testers=10, max_request_bytes=7_000_000).problems()                 # base64 would not fit
    assert BetaConfig(testers=10, upload_max_file_bytes=7_000_000).problems()


def test_the_worker_module_imports_without_running_and_its_limits_hold_directly():
    lim = X.limits(BetaConfig(testers=1))
    assert W.main(["w", "pdf", json.dumps(lim)], io.BytesIO(make_pdf([ERIE])))["ok"] is True
    assert W.main(["w", "docx", json.dumps(lim)], io.BytesIO(make_docx(paras=[ERIE])))["ok"] is True
    assert W.main(["w", "docx", json.dumps(lim)], io.BytesIO(b"nope")) == {"ok": False, "code": "unreadable"}
    z = zipfile.ZipFile(io.BytesIO(make_docx(paras=[ERIE])))
    with pytest.raises(W.Refuse):
        W._read_limited(z, z.getinfo("word/document.xml"), 10)            # the byte limit holds whatever the header claims


def test_the_runbook_and_requirements_carry_the_upload_notes():
    assert "pypdf==" in (ROOT / "deploy" / "bass-proxy" / "requirements.txt").read_text("utf-8")
    rb = (ROOT / "docs" / "bass-beta-runbook.md").read_text("utf-8")
    assert "Uploads" in rb and "upload_max_file_bytes" in rb and "pdf_max_pages" in rb


def test_the_page_sends_pdf_and_docx_bytes_and_flags_the_rest():
    from alto.build import bass_ui_js
    src = bass_ui_js.__dict__.get("JS") or "".join(v for v in vars(bass_ui_js).values() if isinstance(v, str))
    assert "file_b64" in src and "readAsDataURL" in src and "FMAX=5000000" in src and "needs_extraction=true" in src


def test_the_childs_cpu_and_file_size_limits_are_really_applied_and_memory_too_where_the_os_allows():
    cfg = BetaConfig(testers=1)
    res = X.subprocess_runner("selfcheck", b"", X.limits(cfg), 20)
    assert res["ok"] is True
    got = res["limits"]
    assert got["cpu_s"] == X.limits(cfg)["cpu_s"] and got["fsize"] == 0                 # honoured on Linux and macOS
    if sys.platform.startswith("linux"):                                                # macOS ignores RLIMIT_AS: skipped there
        assert got["as"] == cfg.extract_mem_bytes
    else:
        assert got["as"] in (None, cfg.extract_mem_bytes)


def test_a_child_that_may_not_write_files_cannot(tmp_path):
    code = ("import sys, json; sys.path.insert(0, %r); import extract_worker as W; W.apply_limits({'cpu_s': 5, 'mem_bytes': 2_000_000_000});"
            "open(%r, 'w').write('x' * 100000)" % (str(ROOT / "alto" / "bass"), str(tmp_path / "out.bin")))
    import subprocess
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=30)
    out = tmp_path / "out.bin"
    assert done.returncode != 0 and (not out.exists() or out.stat().st_size == 0)
