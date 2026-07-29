"""Alto connector web app: MCP endpoint + hosted Alto experience.

Routes:
  /mcp            — MCP streamable HTTP (mounted FastMCP app)
  /               — per-user Alto homepage (session) or sign-in page
  /session        — POST {idToken} → verify (Firebase) → session cookie
  /dev-login      — dev only (ALTO_DEV_UID): set session without Firebase
  /t/{tid}        — hosted timeline (visibility-gated)
  /t/{tid}/download — offline single-file artifact
  /reports        — reports page (?course=tid)
  /alto-cloud.js  — cloud sync layer (v3)
  /privacy, /healthz
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, \
    RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

from .build.pages import build_home, build_reports, course_entry_for
from .build.builder import load_brief
from .hosted import hosted_home, hosted_reports
from .mcp_server import mcp, get_store, current_uid, require_auth

ROOT = Path(__file__).resolve().parent

SESSION_COOKIE = "alto_session"


def _signer():
    secret = os.environ.get("ALTO_SESSION_SECRET", "dev-secret-not-for-prod")
    return URLSafeSerializer(secret, salt="alto-session")


def session_uid(request: Request) -> str | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        return _signer().loads(raw)
    except BadSignature:
        return None


# ── MCP mount ────────────────────────────────────────────────────────────────
# From here on every request is a network request, so a missing authenticated
# uid must be an error rather than a fallback to a shared tenant.
require_auth(True)

mcp.settings.streamable_http_path = "/"
mcp_app = mcp.streamable_http_app()

app = FastAPI(title="Alto Connector", lifespan=lambda _app: mcp.session_manager.run())
app.mount("/mcp", mcp_app)


from .auth.oauth import router as oauth_router, verify_access_token  # noqa: E402

app.include_router(oauth_router)


@app.middleware("http")
async def put_uid_in_context(request: Request, call_next):
    """Resolve uid for MCP requests: OAuth bearer token, dev token, or dev env.
    Unauthenticated /mcp requests get 401 + resource metadata (RFC 9728)."""
    uid = None
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        dev = os.environ.get("ALTO_DEV_TOKEN")
        if dev and token == dev:
            uid = os.environ.get("ALTO_DEV_UID", "local")
        else:
            uid = verify_access_token(token)
    if uid is None:
        uid = os.environ.get("ALTO_DEV_UID") or None
    if uid is None and request.url.path.startswith("/mcp"):
        from .auth.oauth import base_url
        meta = f"{base_url(request)}/.well-known/oauth-protected-resource"
        return Response(status_code=401, headers={
            "WWW-Authenticate": f'Bearer resource_metadata="{meta}"'})
    tok = current_uid.set(uid) if uid else None
    try:
        return await call_next(request)
    finally:
        if tok:
            current_uid.reset(tok)


# ── helpers ──────────────────────────────────────────────────────────────────

def _user_courses(uid: str) -> list[dict]:
    st = get_store()
    out = []
    for t in st.list_timelines(uid):
        if t.get("status") not in ("built", "published"):
            continue
        try:
            b, _, _ = load_brief({"brief": t["brief"]})
        except Exception:
            continue
        c = course_entry_for(b, href=f"/t/{t['timeline_id']}")
        c["project"] = t.get("project_id", "")
        out.append((t.get("project_id", ""), c))
    return out


SIGNIN_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alto — Sign in</title>
<style>body{font-family:Georgia,serif;display:flex;min-height:100vh;margin:0;
align-items:center;justify-content:center;background:#f0efea;color:#1a1a2e}
.card{background:#fff;border:1px solid #c8c8d8;border-radius:18px;
padding:42px 48px;text-align:center;box-shadow:0 18px 50px rgba(30,30,60,.12)}
button{font:inherit;padding:10px 22px;border-radius:999px;border:1px solid #c8c8d8;
background:#fff;cursor:pointer}button:hover{background:#f6f6fb}</style></head>
<body><div class="card"><h1 style="letter-spacing:.08em">Alto</h1>
<p>Sign in to open your workspace.</p>
<button id="g">Continue with Google</button></div>
<script type="module">
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js';
import { getAuth, GoogleAuthProvider, signInWithPopup } from 'https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js';
const cfg = __FIREBASE_CONFIG__;
const auth = getAuth(initializeApp(cfg));
document.getElementById('g').onclick = async () => {
  const cred = await signInWithPopup(auth, new GoogleAuthProvider());
  const idToken = await cred.user.getIdToken();
  const r = await fetch('/session', {method:'POST',
    headers:{'content-type':'application/json'},
    body: JSON.stringify({idToken})});
  if(r.ok) location.href = '/';
};
</script></body></html>"""


def firebase_web_config() -> dict:
    import json
    raw = os.environ.get("ALTO_FIREBASE_CONFIG", "")
    return json.loads(raw) if raw else {}


# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    uid = session_uid(request)
    if not uid:
        if os.environ.get("ALTO_DEV_UID"):
            return RedirectResponse("/dev-login")
        import json as _json
        return HTMLResponse(SIGNIN_HTML.replace(
            "__FIREBASE_CONFIG__", _json.dumps(firebase_web_config())))
    st = get_store()
    by_project = {}
    for pid, course in _user_courses(uid):
        by_project.setdefault(pid, []).append(course)
    projects = []
    for p in st.list_projects(uid):
        courses = by_project.get(p["project_id"], [])
        if courses:
            projects.append({"name": p["name"], "courses": courses})
    orphans = [c for pid, cs in by_project.items() for c in cs
               if not any(p2["project_id"] == pid for p2 in st.list_projects(uid))]
    if orphans:
        projects.append({"name": "Alto", "courses": orphans})
    html = hosted_home(build_home(projects))
    return HTMLResponse(html)


@app.get("/dev-login")
async def dev_login():
    dev_uid = os.environ.get("ALTO_DEV_UID")
    if not dev_uid:
        return PlainTextResponse("not available", status_code=404)
    resp = RedirectResponse("/")
    resp.set_cookie(SESSION_COOKIE, _signer().dumps(dev_uid),
                    httponly=True, samesite="lax", max_age=30 * 86400)
    return resp


@app.post("/session")
async def create_session(request: Request):
    body = await request.json()
    id_token = body.get("idToken", "")
    try:
        from .auth.firebase import verify_id_token
        uid = verify_id_token(id_token)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, _signer().dumps(uid), httponly=True,
                    samesite="lax", secure=True, max_age=30 * 86400)
    return resp


def _serve_artifact(request: Request, tid: str, name: str):
    st = get_store()
    share = st.get_share(tid)
    if not share:
        return PlainTextResponse("Not found", status_code=404)
    owner, visibility = share["uid"], share.get("visibility", "private")
    if visibility != "link" and session_uid(request) != owner:
        return RedirectResponse("/")     # sign in / not yours
    html = st.get_artifact(owner, tid, name)
    if html is None:
        return PlainTextResponse("Not built", status_code=404)
    return html


@app.get("/t/{tid}", response_class=HTMLResponse)
async def timeline(request: Request, tid: str):
    r = _serve_artifact(request, tid, "hosted.html")
    return r if isinstance(r, Response) else HTMLResponse(r)


@app.get("/t/{tid}/download")
async def timeline_download(request: Request, tid: str):
    r = _serve_artifact(request, tid, "offline.html")
    if isinstance(r, Response):
        return r
    return Response(r, media_type="text/html", headers={
        "Content-Disposition": f'attachment; filename="{tid}-alto.html"'})


@app.get("/reports", response_class=HTMLResponse)
async def reports(request: Request, course: str = ""):
    st = get_store()
    share = st.get_share(course) if course else None
    if not share:
        return PlainTextResponse("Not found", status_code=404)
    owner, visibility = share["uid"], share.get("visibility", "private")
    if visibility != "link" and session_uid(request) != owner:
        return RedirectResponse("/")
    t = st.get_timeline(owner, course)
    if not t:
        return PlainTextResponse("Not found", status_code=404)
    b, _, _ = load_brief({"brief": t["brief"]})
    entry = course_entry_for(b, href=f"/t/{course}")
    html = hosted_reports(build_reports([entry], course))
    return HTMLResponse(html)


@app.get("/alto-cloud.js")
async def cloud_js():
    from .cloud import SOURCE, emit_cloud_js
    if not SOURCE.exists():
        return PlainTextResponse("// alto-cloud v3 not yet deployed\n",
                                 media_type="text/javascript")
    # Same emit path as static publishing, so the hosted variant can never
    # serve a different Firebase project than the one that was configured.
    return Response(emit_cloud_js(),
                    media_type="text/javascript",
                    headers={"Cache-Control": "no-cache"})


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    p = ROOT / "privacy.html"
    if p.exists():
        return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Alto Connector — Privacy</h1><p>Coming soon.</p>")
