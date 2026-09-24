"""Free-tier publishing: regenerate a static Alto site and deploy it with the
Firebase CLI (Spark plan — no server, no card).

Site layout (Firebase Hosting site `alto-connector`, static only):
  /index.html            — the owner's Alto homepage (published timelines)
  /t/{tid}/index.html    — hosted timeline page
  /t/{tid}/offline.html  — downloadable single-file bundle (one timeline)
  /p/{pid}/offline.html  — one bundle for a whole project (only when it holds
                           2+ timelines; otherwise it would duplicate the
                           timeline's own offline.html)
  /offline.html          — one bundle for every published timeline (only when
                           the site holds 2+)
  /pv/{key}/index.html   — sign-in shell for a 'private-web' timeline; the
                           page itself is NOT here, it is in Firestore
  /s/index.html          — shell for every share link; /s/{key}/ rewrites to
                           it, so creating or revoking a share is a Firestore
                           write and never a deploy
  /reports/index.html    — reports viewer (?course={tid})
  /alto-cloud.js         — v3 sync layer (page ↔ Firestore directly; Spark-free)
  /privacy/index.html

Only timelines with visibility 'link' are in the static site; 'private' drafts
never leave the machine. Every publish regenerates home + reports so the site
always reflects the current published set.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import urllib.error
import urllib.request

from .build.builder import build_timeline, load_brief
from .build.fingerprint import META_NAME, build_fingerprint
from .build.pages import build_home, build_reports, course_entry_for
from .build.private_shell import shell as private_shell
from .build.share_shell import shell as share_shell
from .build.single_file import bundle, bundle_many, private_page
from .hosted import hosted_home, hosted_reports, hosted_timeline
from .cloud import emit_cloud_js, load_config, write_cloud_js
from .store.local import check_component

REPO = Path(__file__).resolve().parent.parent


def default_site_dir() -> Path:
    """Where the generated static site is staged before deploy.

    Under the user's store, NOT under the package. `REPO` resolves to
    site-packages for an installed Alto, so the old default would have written
    a site into the installed package directory — read-only on many systems,
    and wrong on all of them.
    """
    from .mcp_server import store_dir
    return Path(store_dir()) / "_site"

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


# Timelines the last regenerate_site() could not rebuild, so had to ship
# from a build-time artifact. Read by publish_timeline; a stdio MCP server
# cannot print, so a silent fallback would otherwise be invisible.
LAST_STALE: list[str] = []


def _published(store, uid: str) -> list[dict]:
    out = []
    for t in store.list_timelines(uid):
        if t.get("visibility") == "link" and t.get("status") == "published":
            out.append(t)
    return out


def _private_web(store, uid: str) -> list[dict]:
    """Timelines published as 'private-web'.

    Deliberately NOT merged into _published(): everything that function returns
    reaches build_home(), and a private timeline's title and URL must never
    appear on the public homepage.
    """
    out = []
    for t in store.list_timelines(uid):
        if (t.get("visibility") == "private-web"
                and t.get("status") == "published" and t.get("private_key")):
            out.append(t)
    return out


def _rebuild(store, uid: str, doc: dict) -> tuple[str | None, str]:
    """Re-emit a timeline from its stored nodes, against the CURRENT engine.

    Publishing used to ship whatever `build_timeline` stored, which meant an
    engine fix never reached a timeline nobody happened to rebuild — the
    fit-to-window work sat unshipped for weeks that way, invisibly. Rebuilding
    here makes a publish always as new as the code.

    Never fatal: a timeline that cannot be rebuilt (no nodes, or a brief the
    current verifier rejects) falls back to its stored artifact, so one bad
    timeline cannot block publishing the rest. Returns (html, reason_if_stale).
    """
    tid = doc["timeline_id"]
    try:
        nodes = [{k: v for k, v in n.items() if not k.startswith("_")}
                 for n in store.list_nodes(uid, tid)]
        if not nodes:
            return None, "no stored nodes"
        b, nodes, conns = load_brief({"brief": doc["brief"], "nodes": nodes,
                                      "connections": store.get_connections(uid, tid)})
        html, _ = build_timeline(b, nodes, conns)
        return html, ""
    except Exception as e:                      # noqa: BLE001 — see docstring
        return None, f"{type(e).__name__}: {e}"


def regenerate_site(store, uid: str, site_dir: Path | None = None) -> Path:
    site = Path(site_dir or os.environ.get("ALTO_SITE_DIR")
                or default_site_dir())
    site.mkdir(parents=True, exist_ok=True)

    published = _published(store, uid)
    # project kind drives the periodization label ("Units" for a course, "Acts"
    # for a novel, …) unless the brief sets period_noun explicitly.
    kind_by_pid = {p["project_id"]: p.get("kind", "")
                   for p in store.list_projects(uid)}
    name_by_pid = {p["project_id"]: p["name"] for p in store.list_projects(uid)}
    courses = []
    projects_by_pid = {}
    # timelines that had to fall back to a build-time artifact, reported back so
    # a silently stale page is at least a visible one
    stale_notes = LAST_STALE
    stale_notes.clear()
    # (Brief, raw timeline html) per project, for the combined offline bundles
    briefs_by_pid = {}
    for t in published:
        # These become directories that are written and later rmtree'd, so they
        # are re-checked here even though the store already refuses a bad one.
        tid = check_component(t["timeline_id"], "timeline_id")
        # The public path carries a random tail so a link cannot be guessed
        # from the title; the timeline id stays the sync key (courseId).
        slug = check_component(t.get("share_slug") or tid, "share_slug")
        b, _, _ = load_brief({"brief": t["brief"]})
        entry = course_entry_for(
            b, href=f"/t/{slug}/",
            kind=kind_by_pid.get(t.get("project_id", ""), ""))
        courses.append(entry)
        projects_by_pid.setdefault(t.get("project_id", ""), []).append(entry)

        tdir = site / "t" / slug
        tdir.mkdir(parents=True, exist_ok=True)
        pname = name_by_pid.get(t.get("project_id", ""), "Alto")

        # Current engine first; the stored artifacts are only as new as the last
        # build_timeline call (see _rebuild).
        raw, stale = _rebuild(store, uid, t)
        if raw is None:
            raw = store.get_artifact(uid, tid, "timeline.html")
            stale_notes.append(f"{tid}: {stale}")
        hosted = hosted_timeline(raw, tid) if raw else store.get_artifact(
            uid, tid, "hosted.html")
        if not hosted:
            raise PublishError(f"{tid}: no built artifact — build_timeline first")
        (tdir / "index.html").write_text(hosted, encoding="utf-8")

        offline = bundle(b, raw, pname) if raw else store.get_artifact(
            uid, tid, "offline.html")
        if raw:
            briefs_by_pid.setdefault(t.get("project_id", ""), []).append((b, raw))
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
            # pid only when a project bundle actually exists at /p/{pid}/ — the
            # homepage uses its presence to decide what its slab button offers.
            has_bundle = len(briefs_by_pid.get(p["project_id"], [])) > 1
            projects.append({"name": p["name"], "courses": cs,
                             "pid": p["project_id"] if has_bundle else ""})
    orphaned = projects_by_pid.get("", [])
    if orphaned:
        projects.append({"name": "Alto", "courses": orphaned})
    (site / "index.html").write_text(hosted_home(build_home(projects)),
                                     encoding="utf-8")

    # ── combined offline bundles ────────────────────────────────────────────
    # A project holding ONE timeline would produce a byte-identical copy of that
    # timeline's own /t/{slug}/offline.html, so it is skipped and the homepage's
    # slab button points at the single timeline instead. Same for a whole site
    # that only has one timeline.
    pdir_root = site / "p"
    groups_all = []
    live_pids = set()
    for pid, items in briefs_by_pid.items():
        pname = name_by_pid.get(pid, "Alto")
        groups_all.append({"name": pname, "items": items})
        if len(items) < 2 or not pid:
            continue
        pslug = check_component(pid, "project_id")
        live_pids.add(pslug)
        bdir = pdir_root / pslug
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / "offline.html").write_text(
            bundle_many([{"name": pname, "items": items}],
                        title=f"{pname} — Alto"),
            encoding="utf-8")

    if pdir_root.exists():
        for d in pdir_root.iterdir():
            if d.is_dir() and d.name not in live_pids:
                shutil.rmtree(d)

    # ── private timelines ───────────────────────────────────────────────────
    # Only the sign-in shell goes on the web; it is byte-identical for every
    # private timeline and carries no timeline content at all. The page itself
    # is uploaded to Firestore from the owner's browser (see private_shell.py).
    pvdir_root = site / "pv"
    live_keys = set()
    private = _private_web(store, uid)
    # Digest of the alto-cloud.js this publish ships, so the shell's script URL
    # changes whenever the file does. See private_shell.shell().
    cloud_v = hashlib.sha256(emit_cloud_js().encode()).hexdigest()[:12]
    # A private timeline is opened by signing in; with no Firebase project there
    # is nothing to sign into, so the shell would be a locked door with no key —
    # and the page would never reach Firestore to begin with. Refuse rather than
    # publish something no one, including the owner, can ever open.
    if private and not load_config().get("apiKey"):
        raise PublishError(
            f"{len(private)} timeline(s) are published as 'private-web', but "
            "this site has no Firebase project configured, so Google sign-in "
            "is off and nobody could ever open them. Set ALTO_FIREBASE_CONFIG "
            "(see README §Publishing), or republish them as 'link'/'private'.")
    for t in private:
        key = check_component(t["private_key"], "private_key")
        live_keys.add(key)
        d = pvdir_root / key
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(private_shell(cloud_v), encoding="utf-8")
        # Refresh the artifact the owner uploads, for the same reason the
        # hosted page is rebuilt above: a timeline built before private.html
        # existed has none, and one built long ago predates current engine
        # fixes. Falls back to whatever is stored if it cannot be rebuilt.
        tid = check_component(t["timeline_id"], "timeline_id")
        raw, stale = _rebuild(store, uid, t)
        if raw is None:
            raw = store.get_artifact(uid, tid, "timeline.html")
            stale_notes.append(f"{tid}: {stale}")
        if raw:
            b, _, _ = load_brief({"brief": t["brief"]})
            store.put_artifact(uid, tid, "private.html", private_page(
                b, raw, name_by_pid.get(t.get("project_id", ""), "")))

    # ── share links ─────────────────────────────────────────────────────
    # ONE shell for every share that will ever exist. /s/{key}/ is rewritten to
    # it by Hosting (see deploy_site), so the owner can mint a share from their
    # homepage and send the link immediately — no deploy, and nothing on this
    # machine ever learns the key. It is also what makes revoking instant: a
    # deleted Firestore document, not a republished site.
    sdir = site / "s"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "index.html").write_text(share_shell(cloud_v), encoding="utf-8")

    # Pruned on its own key set: `live` above is built from link-visible
    # timelines, so sharing that loop would delete every shell each publish.
    if pvdir_root.exists():
        for d in pvdir_root.iterdir():
            if d.is_dir() and d.name not in live_keys:
                shutil.rmtree(d)

    all_offline = site / "offline.html"
    if sum(len(i) for i in briefs_by_pid.values()) > 1:
        all_offline.write_text(bundle_many(groups_all, title="Alto"),
                               encoding="utf-8")
    elif all_offline.exists():
        all_offline.unlink()

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
        # gstatic serves the Firebase SDK; apis.google.com serves the gapi
        # loader signInWithPopup injects — without it Google sign-in (and so
        # cross-device sync) is dead on every published page.
        "script-src 'self' 'unsafe-inline' https://www.gstatic.com https://apis.google.com",
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
    return [
        {"source": "**", "headers": [
            {"key": "Content-Security-Policy", "value": csp},
            {"key": "X-Content-Type-Options", "value": "nosniff"},
            {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
            {"key": "X-Frame-Options", "value": "DENY"},
            # Firebase Hosting defaults to max-age=3600, and deploy_site
            # regenerates firebase.json every publish, so a hand-written cache
            # rule cannot survive there. Without this a publish takes up to an
            # hour to reach anyone who has already visited — and the failure is
            # invisible from outside: curl sees the new file, the owner does
            # not. On "**" rather than "**/*.@(js|html)" because Hosting matches
            # headers against the REQUEST path, and a page served as a directory
            # index (/t/{slug}/, /pv/{key}/) never matches a .html glob. Every
            # file this site serves is HTML or JS, so no-cache costs one
            # conditional request and makes a publish mean what it says.
            {"key": "Cache-Control", "value": "no-cache"},
        ]},
    ]


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
    # The rules travel with the site. Everything Alto stores in Firestore is
    # governed by them, and until now deploying them was a README step nobody
    # was reminded of — a Firestore left in test mode is world-readable and
    # world-writable for thirty days, and publishing into one exposes every
    # reader's highlights and notes to anyone who learns the project id.
    rules_src = REPO / "firestore.rules"
    rules_out = site_dir.parent / "firestore.rules"
    if rules_src.exists():
        shutil.copy(rules_src, rules_out)

    # keep firebase.json's site in step with the configured site name
    fbjson = site_dir.parent / "firebase.json"
    cfg_json = {"hosting": {
        "site": site, "public": site_dir.name, "ignore": ["**/.*"],
        # Every /s/{key}/ is the same shell, which reads its key from the URL.
        # A rewrite rather than a directory per share: a share is created in
        # the browser, and a share that needed a deploy to exist could not be
        # created there at all.
        "rewrites": [{"source": "/s/**", "destination": "/s/index.html"}],
        "headers": _security_headers()}}
    if rules_out.exists():
        cfg_json["firestore"] = {"rules": rules_out.name}
    fbjson.write_text(json.dumps(cfg_json, indent=2))
    (site_dir.parent / ".firebaserc").write_text(
        json.dumps({"projects": {"default": project}}, indent=2))
    env = {**os.environ,
           "PATH": f"{Path(fb).parent}:{os.environ.get('PATH', '')}"}
    targets = [f"hosting:{site}"]
    if rules_out.exists():
        targets.append("firestore:rules")
    r = subprocess.run(
        [fb, "deploy", "--only", ",".join(targets),
         "--project", project, "--non-interactive"],
        cwd=str(site_dir.parent), env=env, capture_output=True, text=True,
        timeout=240)
    if r.returncode != 0:
        # Deliberately not falling back to a hosting-only deploy. A site whose
        # pages shipped but whose rules did not is the worst of both: it looks
        # published and it is not protected.
        raise PublishError(f"firebase deploy failed:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return f"https://{site}.web.app"


def live_pages(site_dir: Path) -> list[str]:
    """Site-relative URLs of every page a deploy puts on the web.

    Derived from the generated tree rather than from the store, so it reflects
    what was actually written — including anything a future writer adds without
    remembering to update this list.
    """
    site = Path(site_dir)
    out = ["/"]
    if (site / "reports" / "index.html").exists():
        out.append("/reports/")
    if (site / "s" / "index.html").exists():
        out.append("/s/")
    for parent in ("t", "pv"):
        d = site / parent
        if not d.exists():
            continue
        for sub in sorted(d.iterdir()):
            if (sub / "index.html").exists():
                out.append(f"/{parent}/{sub.name}/")
    return out


def verify_live(site_dir: Path, base_url: str, timeout: int = 20) -> list[str]:
    """Fetch the deployed pages and confirm each carries THIS build's stamp.

    A deploy that reports success has only proved that files were uploaded. It
    has not proved that what a browser now receives is what was just built —
    a CDN edge can still be serving the previous version, and for five weeks
    once, every page on the site was a build-time artifact while the deploy
    logs looked perfect. This is the check that would have caught that.

    Returns a list of human-readable problems; empty means the site matches.
    """
    want = build_fingerprint()
    pat = re.compile(
        r'<meta\s+name="%s"\s+content="([0-9a-f]+)"' % re.escape(META_NAME))
    problems = []
    for rel in live_pages(site_dir):
        url = base_url.rstrip("/") + rel
        try:
            req = urllib.request.Request(
                url, headers={"Cache-Control": "no-cache",
                              "User-Agent": "alto-publish"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            problems.append(f"{rel}: could not be fetched ({e})")
            continue
        m = pat.search(body)
        if not m:
            problems.append(f"{rel}: carries no {META_NAME} stamp — it predates "
                            "build fingerprinting, so it is an old page")
        elif m.group(1) != want:
            problems.append(f"{rel}: serving build {m.group(1)}, expected {want}")
    return problems
