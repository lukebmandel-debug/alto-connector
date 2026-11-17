"""Stamp 234 F2 (committed in 235): a whitespace key through the REAL provider -> make_client("live") -> Engine._call, with DEBUG capture; nothing of the key or uid in any record."""
import pytest as _p
_p.importorskip("anthropic")
_p.importorskip("httpx2")
import datetime as dt, http.server, logging, os, socket, threading
import pytest
from alto.bass import client as C, engine as E
from alto.bass.beta_proxy import SecretKeyProvider, SecretReader
FAKE = "sk-" + "ant-FAKE-stamp234-5555"
UID = "uid-FAKE-stamp-abcdef"
class R(SecretReader):
    def __init__(s, v): s.v = v
    def read(s, n): return s.v
@pytest.fixture
def listener():
    seen = []
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length", 0)))
            seen.append((self.headers.get("x-api-key") or self.headers.get("authorization") or "").replace("Bearer ", ""))
            b = b'{"id":"m","type":"message","role":"assistant","model":"x","content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}'
            self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, seen
    srv.shutdown()
def _blob(caplog):
    return "\n".join(r.getMessage() + repr(r.args) + repr(r.exc_info) + repr(r.__dict__) for r in caplog.records)
def _all_debug(caplog):
    caplog.set_level(logging.DEBUG)
    for n in ("anthropic", "httpx", "httpx2", "httpcore", "httpcore2", "h11", "bass.upstream", "bass.beta"):
        caplog.set_level(logging.DEBUG, logger=n)
@pytest.mark.parametrize("raw", [FAKE + " \n", "\t" + FAKE + "\r\n  "])
def test_whitespace_key_real_provider_live_client_engine(listener, monkeypatch, caplog, raw):
    _all_debug(caplog)
    srv, seen = listener
    monkeypatch.setattr(C, "BASE_URL", f"http://127.0.0.1:{srv.server_port}")
    cl = C.make_client("live", key_provider=SecretKeyProvider(R(raw)), go_check=lambda: True, clock=lambda: dt.datetime.now(dt.timezone.utc))
    E.Engine(cl, None, None, sleep=lambda s: None)._call(lambda: cl.messages.create(model="x", max_tokens=1, messages=[{"role": "user", "content": "doc text " + UID}]))
    assert seen == [FAKE]
    b = _blob(caplog)
    assert caplog.records, "expected SDK debug records"
    sdk_leak = sorted({r.name for r in caplog.records if FAKE in repr(r.__dict__) + repr(r.exc_info)})
    print("SDK_DEBUG_RECORDS_WITH_KEY", sdk_leak)
    assert all(not n.startswith("bass") for n in sdk_leak)
    assert UID not in "".join(r.getMessage() + repr(r.__dict__) for r in caplog.records if r.name.startswith("bass"))
def test_unstripped_key_failure_with_fb_main_levels(listener, caplog):
    caplog.set_level(logging.DEBUG)                      # root at DEBUG, every handler open
    for n in ("anthropic", "httpx", "httpx2", "httpcore", "httpcore2", "h11"):
        logging.getLogger(n).setLevel(logging.WARNING)     # what fb_main pins, PLUS httpcore2 (the stamp-234 fix)
    srv, seen = listener
    try:
        cl = __import__("anthropic").Anthropic(api_key=FAKE + "\n", base_url=f"http://127.0.0.1:{srv.server_port}", max_retries=0, timeout=5)
        with pytest.raises(Exception):
            E.Engine(cl, None, None, sleep=lambda s: None)._call(lambda: cl.messages.create(model="x", max_tokens=1, messages=[{"role": "user", "content": UID}]))
    finally:
        for n in ("anthropic", "httpx", "httpx2", "httpcore", "httpcore2", "h11"):
            logging.getLogger(n).setLevel(logging.NOTSET)
    b = _blob(caplog)
    print("PROD_LEVEL_RECORDS", [(r.name, r.levelname, r.getMessage()) for r in caplog.records])
    for bad in (FAKE, "sk-ant", "Bearer", UID): assert bad not in b, bad
    print("SDK_DEBUG_HAS_DOC_TEXT", UID in b, len(caplog.records))
def test_unstripped_key_connection_failure_real_client_engine(listener, monkeypatch, caplog):
    _all_debug(caplog)
    monkeypatch.setenv("ANTHROPIC_LOG", "debug")
    srv, seen = listener
    cl = __import__("anthropic").Anthropic(api_key=FAKE + "\n", base_url=f"http://127.0.0.1:{srv.server_port}", max_retries=0, timeout=5)
    with pytest.raises(Exception) as ei:
        E.Engine(cl, None, None, sleep=lambda s: None)._call(lambda: cl.messages.create(model="x", max_tokens=1, messages=[{"role": "user", "content": UID}]))
    assert seen == []
    assert getattr(ei.value, "code", None) == "connection"
    assert FAKE not in str(ei.value) and FAKE not in repr(ei.value)
    b = _blob(caplog)
    assert "code=connection" in b and "exc=APIConnectionError" in b
    print([r.getMessage() for r in caplog.records if r.name == "bass.upstream"])
    sdk_leak = sorted({r.name for r in caplog.records if FAKE in repr(r.__dict__) + repr(r.exc_info)})
    print("SDK_DEBUG_RECORDS_WITH_KEY", sdk_leak)
    assert all(not n.startswith("bass") for n in sdk_leak)
    assert UID not in "".join(r.getMessage() + repr(r.__dict__) for r in caplog.records if r.name.startswith("bass"))
def test_unstripped_key_failure_with_fb_main_levels(listener, caplog):
    caplog.set_level(logging.DEBUG)                      # root at DEBUG, every handler open
    for n in ("anthropic", "httpx", "httpx2", "httpcore", "httpcore2", "h11"):
        logging.getLogger(n).setLevel(logging.WARNING)     # what fb_main pins, PLUS httpcore2 (the stamp-234 fix)
    srv, seen = listener
    try:
        cl = __import__("anthropic").Anthropic(api_key=FAKE + "\n", base_url=f"http://127.0.0.1:{srv.server_port}", max_retries=0, timeout=5)
        with pytest.raises(Exception):
            E.Engine(cl, None, None, sleep=lambda s: None)._call(lambda: cl.messages.create(model="x", max_tokens=1, messages=[{"role": "user", "content": UID}]))
    finally:
        for n in ("anthropic", "httpx", "httpx2", "httpcore", "httpcore2", "h11"):
            logging.getLogger(n).setLevel(logging.NOTSET)
    b = _blob(caplog)
    print("PROD_LEVEL_RECORDS", [(r.name, r.levelname, r.getMessage()) for r in caplog.records])
    for bad in (FAKE, "sk-ant", "Bearer", UID): assert bad not in b, bad
