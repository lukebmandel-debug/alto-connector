"""Shared test fixtures.

The one piece of genuinely global state in this codebase is
`alto.mcp_server._require_auth`. Importing `alto.web` sets it True for the
whole process — correct in production, where a process is either the stdio
server or the OAuth-protected web app and never both, but in a test session
both live in the same interpreter. Whichever module imported first then
decides whether unrelated tests see a working `uid()`.

That is a test-ordering bug waiting to happen, so reset it around every test
rather than remembering to do it in each one.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_global_server_state(tmp_path_factory, monkeypatch):
    from alto import mcp_server as srv

    # Point the default store at a temp directory for EVERY test. Without
    # this, any test that exercises a code path reaching get_store() without
    # setting ALTO_STORE_DIR writes into the real ~/Documents/Alto — which is
    # exactly what happened: a test run left OAuth token fixtures in the
    # author's home directory. A test suite must never touch it.
    monkeypatch.setenv(
        "ALTO_STORE_DIR", str(tmp_path_factory.mktemp("alto-store")))

    previous_auth = srv._require_auth
    srv.require_auth(False)
    yield
    srv.require_auth(previous_auth)
    # The store is a module-level singleton; a test that swapped it in must
    # not leak that store into the next test's assertions.
    srv.set_store(None)
