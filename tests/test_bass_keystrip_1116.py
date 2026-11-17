"""Hosted Bass key strip + safe upstream-failure log (16 Nov). Fakes only: a local listener, a fake key, a fake uid. No network beyond 127.0.0.1."""
import pytest as _p
_p.importorskip("anthropic")
_p.importorskip("httpx2")
import http.server
import logging
import threading

import pytest

from alto.bass import engine as E
from alto.bass._sdk import anthropic, httpx2
from alto.bass.beta_proxy import SecretKeyProvider, SecretReader
from alto.bass.errors import NotConfigured

FAKE = "sk-" + "ant-FAKE-keystrip-0000"
UID = "uid-FAKE-9f8e7d6c5b4a"


class _R(SecretReader):
    def __init__(self, v):
        self.v = v

    def read(self, name):
        return self.v


@pytest.fixture
def listener():
    seen = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length", 0)))
            seen.append((self.headers.get("x-api-key") or self.headers.get("authorization") or "").replace("Bearer ", ""))
            body = b'{"id":"m","type":"message","role":"assistant","model":"x","content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}'
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, seen
    srv.shutdown()


def _call(port, key):
    c = anthropic.Anthropic(api_key=key, base_url=f"http://127.0.0.1:{port}", max_retries=0, timeout=5)
    return c.messages.create(model="x", max_tokens=1, messages=[{"role": "user", "content": "hi"}])


@pytest.mark.parametrize("raw", [FAKE + "\n", FAKE + "\r\n", "  " + FAKE + "  ", "\t" + FAKE + " \n"])
def test_a_key_with_whitespace_is_stripped_and_reaches_the_listener(listener, raw):
    srv, seen = listener
    key = SecretKeyProvider(_R(raw)).get_key()
    assert key == FAKE
    _call(srv.server_port, key)
    assert seen == [FAKE]


def test_control_the_unstripped_key_fails_as_connection(listener):
    srv, seen = listener
    with pytest.raises(anthropic.APIConnectionError):
        _call(srv.server_port, FAKE + "\n")
    assert seen == []


@pytest.mark.parametrize("raw", ["", " ", "\n", " \r\n\t "])
def test_a_whitespace_only_key_is_bass_paused_and_no_attempt(raw):
    prov = SecretKeyProvider(_R(raw))
    for _ in range(2):
        with pytest.raises(NotConfigured) as e:
            prov.get_key()
        assert e.value.code == "bass_paused"


def _engine():
    return E.Engine(None, None, None, sleep=lambda s: None)


def test_the_failure_log_holds_class_names_and_the_code_only(caplog):
    import h11
    caplog.set_level(logging.DEBUG)          # root: every level, every logger
    leak = f"Illegal header value b'Bearer {FAKE}\\n' for {UID}"

    def boom():
        try:
            raise h11.LocalProtocolError(leak)
        except h11.LocalProtocolError as c:
            raise anthropic.APIConnectionError(request=httpx2.Request("POST", "http://127.0.0.1/v1")) from c

    with pytest.raises(Exception):
        _engine()._call(boom)
    text = "\n".join(r.getMessage() + " " + str(r.args) + " " + str(r.exc_info) + " " + str(r.__dict__) for r in caplog.records)
    assert "code=connection" in text and "APIConnectionError" in text and "LocalProtocolError" in text
    for bad in (FAKE, "sk-ant", "Bearer", UID, "Illegal header"):
        assert bad not in text
    assert [r.levelno for r in caplog.records if r.name == "bass.upstream"] and all(r.levelno == logging.WARNING for r in caplog.records if r.name == "bass.upstream")


def test_a_key_and_uid_in_any_exception_message_never_reach_any_log_record(caplog):
    caplog.set_level(logging.DEBUG)
    msg = f"{FAKE} {UID}"
    for exc in (httpx2.ConnectError(msg), httpx2.ReadTimeout(msg), OSError(msg),
                anthropic.APIConnectionError(message=msg, request=httpx2.Request("POST", "http://127.0.0.1/v1"))):
        def boom(exc=exc):
            raise exc
        with pytest.raises(Exception):
            _engine()._call(boom)
    assert caplog.records
    for r in caplog.records:
        blob = r.getMessage() + repr(r.args) + repr(r.exc_info) + repr(r.__dict__)
        assert FAKE not in blob and UID not in blob and "sk-ant" not in blob


def test_the_meta_log_line_carries_no_uid(caplog):
    import datetime as dt
    from alto.bass.beta_guard import MetaLog
    caplog.set_level(logging.DEBUG)
    MetaLog(lambda: dt.datetime(2026, 11, 16)).write(uid=UID, action="build", status="ok", code=None)
    assert caplog.records and all(UID not in r.getMessage() for r in caplog.records)


def test_the_real_fb_main_logging_config_keeps_sdk_loggers_at_warning_or_above(monkeypatch):
    import importlib.util
    import sys
    import types
    from pathlib import Path
    ff = types.ModuleType("firebase_functions")
    ff.https_fn = types.SimpleNamespace(on_request=lambda **k: (lambda f: f), Response=object)
    ff.options = types.SimpleNamespace(MemoryOption=types.SimpleNamespace(MB_512=512))
    monkeypatch.setitem(sys.modules, "firebase_functions", ff)
    monkeypatch.setitem(sys.modules, "proxy_main", types.ModuleType("proxy_main"))
    names = ("anthropic", "httpx", "httpx2", "httpcore", "h11")
    saved = {n: logging.getLogger(n).level for n in names}
    try:
        for n in names:
            logging.getLogger(n).setLevel(logging.DEBUG)             # as ANTHROPIC_LOG=debug would leave them
        path = Path(__file__).resolve().parents[1] / "deploy" / "bass-proxy" / "fb_main.py"
        spec = importlib.util.spec_from_file_location("fb_main_under_test", path)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
        for n in names:
            assert logging.getLogger(n).getEffectiveLevel() >= logging.WARNING, n
            assert not logging.getLogger(n).isEnabledFor(logging.DEBUG) and not logging.getLogger(n).isEnabledFor(logging.INFO)
    finally:
        for n, v in saved.items():
            logging.getLogger(n).setLevel(v)
