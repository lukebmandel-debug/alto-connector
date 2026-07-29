"""OAuth 2.1 flow tests: metadata, DCR, PKCE code flow, refresh rotation,
401 challenge on /mcp."""
import base64
import hashlib
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alto import mcp_server as srv  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402


# The MCP StreamableHTTP session manager's lifespan can only run once per
# process, so all tests in this module share one TestClient.
_client_cm = None


@pytest.fixture(scope="module")
def _shared_client(tmp_path_factory):
    import os
    os.environ["ALTO_DEV_UID"] = "oauth-test-user"
    os.environ.pop("ALTO_PUBLIC_BASE", None)
    srv.set_store(LocalStore(tmp_path_factory.mktemp("oauth")))
    from alto.web import app
    with TestClient(app) as c:
        yield c
    srv.set_store(None)
    os.environ.pop("ALTO_DEV_UID", None)


@pytest.fixture()
def client(_shared_client):
    return _shared_client


def _pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def test_metadata(client):
    r = client.get("/.well-known/oauth-authorization-server").json()
    assert r["code_challenge_methods_supported"] == ["S256"]
    assert r["registration_endpoint"].endswith("/oauth/register")
    pr = client.get("/.well-known/oauth-protected-resource").json()
    assert pr["resource"].endswith("/mcp")


def test_mcp_401_challenge(client):
    import os
    saved = os.environ.pop("ALTO_DEV_UID")
    try:
        r = client.post("/mcp", json={})
        assert r.status_code == 401
        assert "resource_metadata=" in r.headers["www-authenticate"]
    finally:
        os.environ["ALTO_DEV_UID"] = saved


def test_full_pkce_flow(client):
    # 1. DCR
    r = client.post("/oauth/register", json={
        "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
        "client_name": "Claude"})
    assert r.status_code == 201
    cid = r.json()["client_id"]

    # 2. authorize (dev mode auto-approves)
    verifier, challenge = _pkce()
    r = client.get("/oauth/authorize", params={
        "client_id": cid, "response_type": "code",
        "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "code_challenge": challenge, "code_challenge_method": "S256",
        "state": "xyz"}, follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["state"] == ["xyz"]
    code = q["code"][0]

    # 3. token exchange with PKCE
    r = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "client_id": cid, "code_verifier": verifier})
    assert r.status_code == 200, r.text
    tok = r.json()
    assert tok["token_type"] == "Bearer"

    # 4. code replay is rejected
    r = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "client_id": cid, "code_verifier": verifier})
    assert r.status_code == 400

    # 5. wrong verifier rejected (new code)
    r2 = client.get("/oauth/authorize", params={
        "client_id": cid, "response_type": "code",
        "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "code_challenge": challenge, "code_challenge_method": "S256"},
        follow_redirects=False)
    code2 = parse_qs(urlparse(r2.headers["location"]).query)["code"][0]
    r = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code2,
        "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "client_id": cid, "code_verifier": "wrong-verifier"})
    assert r.status_code == 400

    # 6. bearer token authenticates /mcp (uid comes from the token)
    from alto.auth.oauth import verify_access_token
    assert verify_access_token(tok["access_token"]) == "oauth-test-user"

    # 7. refresh rotation: old refresh dies after use
    r = client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    assert r.status_code == 200
    r = client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    assert r.status_code == 400


def test_register_rejects_bad_redirects(client):
    r = client.post("/oauth/register", json={
        "redirect_uris": ["http://evil.example.com/cb"]})
    assert r.status_code == 400
