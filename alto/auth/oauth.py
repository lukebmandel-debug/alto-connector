"""OAuth 2.1 authorization server for the MCP connector (plan §6).

One app is both resource server (/mcp) and authorization server:
  /.well-known/oauth-protected-resource   — RFC 9728
  /.well-known/oauth-authorization-server — RFC 8414 (PKCE S256 advertised)
  /oauth/register                         — RFC 7591 DCR (public clients)
  /oauth/authorize                        — Google Sign-In page → 60s code
  /oauth/token                            — code+PKCE → opaque tokens

Tokens are opaque 256-bit values stored HASHED (sha256) with expiry — instant
revocability, no key management. Identity = Firebase Auth uid, the same uid
the Alto web app uses. Dev mode (ALTO_DEV_UID set): /oauth/authorize
auto-approves as the dev uid without Firebase.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()

CODE_TTL = 60
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 86400

ALLOWED_REDIRECT_HOSTS = {"claude.ai", "claude.com", "localhost", "127.0.0.1"}


def _store():
    from ..mcp_server import get_store
    return get_store()


# Generic oauth docs live under a reserved "uid" so both backends work unchanged.
_OA = "_oauth"


def _put(kind, key, doc):
    _store().put_timeline(_OA, f"{kind}-{key}", doc)


def _get(kind, key):
    return _store().get_timeline(_OA, f"{kind}-{key}")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _b64url_sha256(verifier: str) -> str:
    return base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def base_url(request: Request) -> str:
    return os.environ.get("ALTO_PUBLIC_BASE") or str(request.base_url).rstrip("/")


def _redirect_allowed(uri: str) -> bool:
    from urllib.parse import urlparse
    try:
        p = urlparse(uri)
    except ValueError:
        return False
    if p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1"):
        return True   # RFC 8252 loopback (Claude Code)
    return p.scheme == "https" and p.hostname is not None


# ── metadata ─────────────────────────────────────────────────────────────────

@router.get("/.well-known/oauth-protected-resource")
async def protected_resource(request: Request):
    base = base_url(request)
    return {"resource": f"{base}/mcp", "authorization_servers": [base]}


@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_mcp(request: Request):
    return await protected_resource(request)


@router.get("/.well-known/oauth-authorization-server")
async def as_metadata(request: Request):
    base = base_url(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["alto"],
    }


# ── dynamic client registration ──────────────────────────────────────────────

@router.post("/oauth/register")
async def register(request: Request):
    body = await request.json()
    uris = body.get("redirect_uris") or []
    if not uris or not all(_redirect_allowed(u) for u in uris):
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
    client_id = secrets.token_urlsafe(24)
    _put("client", client_id, {
        "client_id": client_id,
        "redirect_uris": uris,
        "client_name": str(body.get("client_name", ""))[:200],
        "created": int(time.time()),
    })
    return JSONResponse({
        "client_id": client_id,
        "redirect_uris": uris,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }, status_code=201)


# ── authorize ────────────────────────────────────────────────────────────────

AUTHORIZE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alto — Authorize</title>
<style>body{font-family:Georgia,serif;display:flex;min-height:100vh;margin:0;
align-items:center;justify-content:center;background:#f0efea;color:#1a1a2e}
.card{background:#fff;border:1px solid #c8c8d8;border-radius:18px;
padding:42px 48px;text-align:center;max-width:380px;
box-shadow:0 18px 50px rgba(30,30,60,.12)}
button{font:inherit;padding:10px 22px;border-radius:999px;border:1px solid #c8c8d8;
background:#fff;cursor:pointer}button:hover{background:#f6f6fb}
p{color:#5a5a80;font-size:14px;line-height:1.5}</style></head>
<body><div class="card"><h1 style="letter-spacing:.08em">Alto</h1>
<p>Claude is asking to connect to your Alto workspace — your projects,
timelines, and study data.</p>
<button id="g">Continue with Google</button>
<p id="err" style="color:#b3384f"></p></div>
<script type="module">
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js';
import { getAuth, GoogleAuthProvider, signInWithPopup } from 'https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js';
const cfg = __FIREBASE_CONFIG__;
const auth = getAuth(initializeApp(cfg));
document.getElementById('g').onclick = async () => {
  try {
    const cred = await signInWithPopup(auth, new GoogleAuthProvider());
    const idToken = await cred.user.getIdToken();
    const r = await fetch('/oauth/approve', {method:'POST',
      headers:{'content-type':'application/json'},
      body: JSON.stringify({idToken, params: location.search})});
    const d = await r.json();
    if(d.redirect) location.href = d.redirect;
    else document.getElementById('err').textContent = d.error || 'failed';
  } catch(e){ document.getElementById('err').textContent = String(e); }
};
</script></body></html>"""


def _validate_authorize_params(q) -> tuple[dict | None, str | None]:
    client = _get("client", q.get("client_id", ""))
    if not client:
        return None, "unknown client_id"
    if q.get("redirect_uri") not in client["redirect_uris"]:
        return None, "redirect_uri not registered"
    if q.get("response_type") != "code":
        return None, "response_type must be code"
    if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
        return None, "PKCE S256 required"
    return client, None


def _mint_code(uid: str, q) -> str:
    code = secrets.token_urlsafe(32)
    _put("code", _sha(code), {
        "uid": uid, "client_id": q["client_id"],
        "redirect_uri": q["redirect_uri"],
        "challenge": q["code_challenge"],
        "exp": int(time.time()) + CODE_TTL, "used": False,
    })
    return code


@router.get("/oauth/authorize")
async def authorize(request: Request):
    q = dict(request.query_params)
    _, err = _validate_authorize_params(q)
    if err:
        return JSONResponse({"error": "invalid_request",
                             "error_description": err}, status_code=400)
    dev_uid = os.environ.get("ALTO_DEV_UID")
    if dev_uid:  # local dev: skip Google
        code = _mint_code(dev_uid, q)
        sep = "&" if "?" in q["redirect_uri"] else "?"
        loc = f"{q['redirect_uri']}{sep}code={code}"
        if q.get("state"):
            loc += f"&state={q['state']}"
        return RedirectResponse(loc, status_code=302)
    from ..web import firebase_web_config
    return HTMLResponse(AUTHORIZE_HTML.replace(
        "__FIREBASE_CONFIG__", json.dumps(firebase_web_config())))


@router.post("/oauth/approve")
async def approve(request: Request):
    body = await request.json()
    from urllib.parse import parse_qs
    raw = parse_qs((body.get("params") or "").lstrip("?"))
    q = {k: v[0] for k, v in raw.items()}
    _, err = _validate_authorize_params(q)
    if err:
        return JSONResponse({"error": err}, status_code=400)
    try:
        from .firebase import verify_id_token
        uid = verify_id_token(body.get("idToken", ""))
    except Exception as e:
        return JSONResponse({"error": f"sign-in failed: {e}"}, status_code=401)
    code = _mint_code(uid, q)
    sep = "&" if "?" in q["redirect_uri"] else "?"
    loc = f"{q['redirect_uri']}{sep}code={code}"
    if q.get("state"):
        loc += f"&state={q['state']}"
    return {"redirect": loc}


# ── token ────────────────────────────────────────────────────────────────────

def _mint_tokens(uid: str, client_id: str) -> dict:
    access = secrets.token_urlsafe(32)
    refresh = secrets.token_urlsafe(32)
    now = int(time.time())
    _put("access", _sha(access), {"uid": uid, "client_id": client_id,
                                  "exp": now + ACCESS_TTL})
    _put("refresh", _sha(refresh), {"uid": uid, "client_id": client_id,
                                    "exp": now + REFRESH_TTL, "used": False})
    return {"access_token": access, "token_type": "Bearer",
            "expires_in": ACCESS_TTL, "refresh_token": refresh,
            "scope": "alto"}


@router.post("/oauth/token")
async def token(request: Request):
    form = dict(await request.form())
    grant = form.get("grant_type")

    if grant == "authorization_code":
        rec = _get("code", _sha(form.get("code", "")))
        now = int(time.time())
        if not rec or rec["used"] or rec["exp"] < now:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        if form.get("redirect_uri") != rec["redirect_uri"]:
            return JSONResponse({"error": "invalid_grant",
                                 "error_description": "redirect_uri mismatch"},
                                status_code=400)
        if rec["client_id"] != form.get("client_id", rec["client_id"]):
            return JSONResponse({"error": "invalid_client"}, status_code=400)
        if _b64url_sha256(form.get("code_verifier", "")) != rec["challenge"]:
            return JSONResponse({"error": "invalid_grant",
                                 "error_description": "PKCE verification failed"},
                                status_code=400)
        rec["used"] = True
        _put("code", _sha(form.get("code", "")), rec)
        return _mint_tokens(rec["uid"], rec["client_id"])

    if grant == "refresh_token":
        h = _sha(form.get("refresh_token", ""))
        rec = _get("refresh", h)
        now = int(time.time())
        if not rec or rec.get("used") or rec["exp"] < now:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        rec["used"] = True                       # rotation: old refresh dies
        _put("refresh", h, rec)
        return _mint_tokens(rec["uid"], rec["client_id"])

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


# ── resource-server verification ─────────────────────────────────────────────

def verify_access_token(token_str: str) -> str | None:
    rec = _get("access", _sha(token_str))
    if not rec or rec["exp"] < int(time.time()):
        return None
    return rec["uid"]
