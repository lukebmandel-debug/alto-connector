"""Free-tier publishing: regenerate a static Alto site and deploy it with the
Firebase CLI (Spark plan — no server, no card).

Site layout (Firebase Hosting site `alto-connector`, static only):
  /index.html            — the owner's Alto homepage (published timelines)
  /t/{tid}/index.html    — hosted timeline page
  /t/{tid}/offline.html  — downloadable single-file bundle
  /reports/index.html    — reports viewer (?course={tid})
  /alto-cloud.js         — v3 sync layer (page ↔ Firestore directly; Spark-free)
  /privacy/index.html

Only timelines with visibility 'link' are in the static site; 'private' drafts
never leave the machine. Every publish regenerates home + reports so the site
always reflects the current published set.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .build.builder import load_brief
from .build.pages import build_home, build_reports, course_entry_for
from .hosted import hosted_home, hosted_reports
from .cloud import write_cloud_js
from .store.local import check_component

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SITE = REPO / "firebase" / "site"

# Firebase Hosting site ids and GCP project ids: lowercase alphanumeric plus
# hyphens. Enforced because both are interpolated into a subprocess argument
# (`--only hosting:<site>`), where a leading '-' would read as a flag.
_FB_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")


def firebase_bin() -> str:
    """The user's firebase CLI: explicit override, then PATH, then the
    user-space npm prefix. The old hardcoded ~/.local/node path only ever
    existed on the author's machine."""
    override = os.environ.get("ALTO_FIREBASE_BIN")
    if override:
        return override
    found = shutil.which("firebase")
    if found:
        return found
    return str(Path.home() / ".local" / "node" / "bin" / "firebase")


class PublishError(RuntimeError):
    pass


def _published(store, uid: str) -> list[dict]:
    out = []
    for t in store.list_timelines(uid):
        if t.get("visibility") == "link" and t.get("status") == "published":
            out.append(t)
    return out


def regenerate_site(store, uid: str, site_dir: Path | None = None) -> Path:
    site = Path(site_dir or os.environ.get("ALTO_SITE_DIR", DEFAULT_SITE))
    site.mkdir(parents=True, exist_ok=True)

    published = _published(store, uid)
    courses = []
    projects_by_pid = {}
    for t in published:
        # These become directories that are written and later rmtree'd, so they
        # are re-checked here even though the store already refuses a bad one.
        tid = check_component(t["timeline_id"], "timeline_id")
        # The public path carries a random tail so a link cannot be guessed
        # from the title; the timeline id stays the sync key (courseId).
        slug = check_component(t.get("share_slug") or tid, "share_slug")
        b, _, _ = load_brief({"brief": t["brief"]})
        entry = course_entry_for(b, href=f"/t/{slug}/")
        courses.append(entry)
        projects_by_pid.setdefault(t.get("project_id", ""), []).append(entry)

        tdir = site / "t" / slug
        tdir.mkdir(parents=True, exist_ok=True)
        hosted = store.get_artifact(uid, tid, "hosted.html")
        offline = store.get_artifact(uid, tid, "offline.html")
        if not hosted:
            raise PublishError(f"{tid}: no built artifact — build_timeline first")
        (tdir / "index.html").write_text(hosted, encoding="utf-8")
        if offline:
            (tdir / "offline.html").write_text(offline, encoding="utf-8")

    # prune timelines no longer published — this is what makes revocation real
    tdir_root = site / "t"
    live = {t.get("share_slug") or t["timeline_id"] for t in published}
    if tdir_root.exists():
        for d in tdir_root.iterdir():
            if d.is_dir() and d.name not in live:
                shutil.rmtree(d)

    # homepage: project slabs from the owner's project containers
    projects = []
    for p in store.list_projects(uid):
        cs = projects_by_pid.get(p["project_id"], [])
        if cs:
            projects.append({"name": p["name"], "courses": cs})
    orphaned = projects_by_pid.get("", [])
    if orphaned:
        projects.append({"name": "Alto", "courses": orphaned})
    (site / "index.html").write_text(hosted_home(build_home(projects)),
                                     encoding="utf-8")

    # reports viewer (all published courses selectable via ?course=)
    rdir = site / "reports"
    rdir.mkdir(exist_ok=True)
    default_course = courses[0]["courseId"] if courses else ""
    (rdir / "index.html").write_text(
        hosted_reports(build_reports(courses, default_course)), encoding="utf-8")

    # Emitted, not copied: the Firebase project comes from the publisher's own
    # ALTO_FIREBASE_CONFIG, and is empty (sync off) when they have not set one.
    write_cloud_js(site / "alto-cloud.js")
    pdir = site / "privacy"
    pdir.mkdir(exist_ok=True)
    shutil.copy(REPO / "alto" / "privacy.html", pdir / "index.html")
    return site


def firebase_configured() -> tuple[str, str, str] | None:
    """(firebase_bin, site, project) when web publishing is set up, else None."""
    fb = firebase_bin()
    site = os.environ.get("ALTO_FIREBASE_SITE", "")
    project = os.environ.get("ALTO_FIREBASE_PROJECT", "")
    if Path(fb).exists() and _FB_NAME.match(site) and _FB_NAME.match(project):
        return fb, site, project
    return None


def _security_headers() -> list[dict]:
    """CSP and friends for the published site.

    `'unsafe-inline'` in script-src is unavoidable and deliberate: the engine is
    one large inline <script>, and engine/ is frozen. So this is not the primary
    XSS control — build/sanitize.py is. What it does buy is the rest of the
    blast radius: no third-party script origins, no plugins, no framing, no form
    posts, and no <base> rewriting.
    """
    csp = "; ".join([
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://www.gstatic.com",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https://*.googleusercontent.com",
        "font-src 'self' data:",
        # Firestore + Identity Toolkit, which alto-cloud.js talks to directly.
        "connect-src 'self' https://*.googleapis.com https://*.firebaseio.com "
        "wss://*.firebaseio.com https://*.firebaseapp.com",
        "frame-src https://*.firebaseapp.com",   # the Google sign-in popup
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ])
    return [{"source": "**", "headers": [
        {"key": "Content-Security-Policy", "value": csp},
        {"key": "X-Content-Type-Options", "value": "nosniff"},
        {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
        {"key": "X-Frame-Options", "value": "DENY"},
    ]}]


def deploy_site(site_dir: Path) -> str:
    """firebase deploy --only hosting:<site> (CLI must be logged in to the
    project). Site/project come from ALTO_FIREBASE_SITE / ALTO_FIREBASE_PROJECT."""
    cfg = firebase_configured()
    if not cfg:
        raise PublishError(
            "web publishing not configured — set ALTO_FIREBASE_SITE and "
            "ALTO_FIREBASE_PROJECT (a free Firebase Hosting site; see README) "
            "or share the offline file instead")
    fb, site, project = cfg
    # keep firebase.json's site in step with the configured site name
    fbjson = site_dir.parent / "firebase.json"
    fbjson.write_text(json.dumps({"hosting": {
        "site": site, "public": site_dir.name, "ignore": ["**/.*"],
        "headers": _security_headers()}}, indent=2))
    (site_dir.parent / ".firebaserc").write_text(
        json.dumps({"projects": {"default": project}}, indent=2))
    env = {**os.environ,
           "PATH": f"{Path(fb).parent}:{os.environ.get('PATH', '')}"}
    r = subprocess.run(
        [fb, "deploy", "--only", f"hosting:{site}",
         "--project", project, "--non-interactive"],
        cwd=str(site_dir.parent), env=env, capture_output=True, text=True,
        timeout=240)
    if r.returncode != 0:
        raise PublishError(f"firebase deploy failed:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return f"https://{site}.web.app"
