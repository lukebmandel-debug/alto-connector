"""Alto connector — MCP server (FastMCP, streamable HTTP).

Claude drives the interview (see interview_guide.md, served as both an MCP
prompt and the get_interview_guide tool); this server is the state machine:
it stores answers, enforces the §0 closed-system consent gate SERVER-SIDE,
lays out and builds the timeline, and publishes artifacts.

uid resolution: production wraps this app with OAuth middleware that puts the
authenticated uid into a contextvar (see auth/); dev mode uses ALTO_DEV_UID.
"""
from __future__ import annotations

import contextvars
import datetime
import os
import re
import secrets
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .build.brief import BriefError, ID_RE
from .build.builder import load_brief, build_timeline as _build, run_layout
from .build.single_file import bundle
from .build.verify import VerifyError
from .store.local import LocalStore

ROOT = Path(__file__).resolve().parent

current_uid: contextvars.ContextVar[str] = contextvars.ContextVar("uid")

_store = None


def get_store():
    global _store
    if _store is None:
        if os.environ.get("ALTO_STORE", "local") == "firestore":
            from .store.firestore import FirestoreStore
            _store = FirestoreStore()
        else:
            _store = LocalStore(os.environ.get(
                "ALTO_STORE_DIR", str(Path.home() / ".alto-connector-dev")))
    return _store


def set_store(store):
    global _store
    _store = store


class AuthError(RuntimeError):
    pass


# Set by alto/web.py when the OAuth-protected HTTP app is mounted. It is an
# explicit switch rather than something inferred from ALTO_TRANSPORT because
# the local CLI, the test suite and the build library all call uid() with no
# transport configured, and they are single-user by construction.
_require_auth = False


def require_auth(value: bool = True) -> None:
    global _require_auth
    _require_auth = value


def uid() -> str:
    """The owner of the current request.

    Over stdio there is one local user and no auth, so the configured dev uid
    is correct. Under the HTTP app the uid comes from the OAuth middleware's
    contextvar, and a miss means the request was never authenticated — falling
    back to a shared literal there would silently pool every caller into one
    tenant, so it fails closed instead.
    """
    try:
        return current_uid.get()
    except LookupError:
        pass
    if _require_auth:
        raise AuthError(
            "no authenticated uid in context — refusing to serve a request "
            "over a network transport without an identity")
    return os.environ.get("ALTO_DEV_UID", "dev")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40]
    return s or "item"


def _check_ref(value, what: str):
    """Gate every caller-supplied id that becomes a path or URL segment.

    `_slug()` only runs on ids we derive ourselves; ids passed straight into a
    tool (`timeline_id`, `project_id`) reach the store and the published site
    path unchanged, so they are checked against the same slug rule the build
    layer uses for every other id. Returns (value, error_dict).
    """
    s = "" if value is None else str(value)
    if not ID_RE.match(s):
        return None, {"error": "bad_id",
                      "message": (f"{what} {s!r} is not a valid id — lowercase "
                                  "letters, digits and hyphens, starting with a "
                                  "letter, up to 48 characters")}
    return s, None


_SHARE_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"   # no look-alike glyphs


def _share_slug(tid: str) -> str:
    """The published directory name: the timeline id plus 8 random characters.

    A bare `/t/contracts-i/` is share-by-obscurity with almost no obscurity —
    anyone can guess a title-derived slug. The random tail makes a published
    link genuinely unguessable while keeping it readable. The timeline id
    itself stays the sync key (`courseId`), so highlights and reports survive
    a re-publish.
    """
    tail = "".join(secrets.choice(_SHARE_ALPHABET) for _ in range(8))
    return f"{tid}-{tail}"


def _unique_slug(existing: set, base: str) -> str:
    s = base
    i = 2
    while s in existing:
        s = f"{base}-{i}"
        i += 1
    return s


MAX_NODES = 200
MAX_CONNECTIONS = 600
MAX_TIMELINES = 20
MAX_PROJECTS = 20

CONSENT_ERROR = {
    "error": "consent_gate",
    "message": ("Alto builds only from the user's own materials (§0). Before "
                "authoring nodes: gather real materials in the conversation, "
                "give the §A consent statement, and after an explicit yes call "
                "record_materials_consent(timeline_id, sources, consent=true)."),
}

RO = ToolAnnotations(readOnlyHint=True)
RW = ToolAnnotations(readOnlyHint=False, destructiveHint=False)

__version__ = "1.0.1"
WEBSITE_URL = "https://alto-get.web.app"


def _server_icons():
    """The Alto mark as data-URI icons in the `initialize` response.

    PNG first, then SVG: MCP clients that render icons MUST support PNG but
    only SHOULD support SVG, so an SVG-only list is skippable by a conforming
    client. `theme` is not a field on `Icon` in the installed SDK, but the
    model allows extras, so it rides along for clients that read it.

    Worth knowing where this does and does not show up: Claude Desktop renders
    the icon from an .mcpb bundle's manifest, not from here, and claude.ai
    ignores serverInfo icons entirely today (anthropics/claude-ai-mcp#152).
    This is the spec-correct channel and costs nothing; packaging/ is what
    actually puts the glyph in front of a user.

    Only the 128px PNG rides along per theme. These are inlined into every
    `initialize` response, and shipping all four sizes cost ~600KB per
    handshake; the SVG covers every larger size at 2.8KB, and the bigger PNGs
    are referenced as files by the .mcpb manifest, where size does not matter.
    """
    import base64
    from mcp.types import Icon

    def data_uri(path: Path, mime: str) -> str:
        return f"data:{mime};base64," + base64.b64encode(
            path.read_bytes()).decode()

    icons = []
    for theme in ("light", "dark"):
        png = ROOT / "assets" / "png" / f"alto-{theme}-128.png"
        if png.exists():
            icons.append(Icon(src=data_uri(png, "image/png"),
                              mimeType="image/png",
                              sizes=["128x128"], theme=theme))
        svg = ROOT / "assets" / f"alto-icon-{theme}.svg"
        if svg.exists():
            icons.append(Icon(src=data_uri(svg, "image/svg+xml"),
                              mimeType="image/svg+xml",
                              sizes=["any"], theme=theme))
    return icons or None


mcp = FastMCP(
    "Alto",
    icons=_server_icons(),
    website_url=WEBSITE_URL,
    instructions=(
        "Alto builds interactive timelines EXCLUSIVELY from the user's own "
        "materials — it never invents content (closed-system rule §0). Start "
        "any new session with get_interview_guide; it returns the interview "
        "to run and any resumable drafts."),
)

# FastMCP takes no version kwarg, so without this the server reports the MCP
# SDK's version as its own (create_initialization_options falls back to
# pkg_version("mcp")).
mcp._mcp_server.version = __version__


def _timeline_or_error(tid: str):
    # Every tool that takes a timeline_id funnels through here, so this is the
    # one place the id has to be proven safe before it becomes a store path.
    tid, err = _check_ref(tid, "timeline_id")
    if err:
        return None, err
    doc = get_store().get_timeline(uid(), tid)
    if not doc:
        return None, {"error": "not_found",
                      "message": f"timeline {tid!r} not found — list_projects "
                                 "shows existing drafts"}
    return doc, None


def _consent_ok(doc) -> bool:
    return bool((doc.get("consent") or {}).get("granted"))


def _completeness(doc, nodes, connections) -> dict:
    return {
        "has_consent": _consent_ok(doc),
        "entities": len((doc.get("brief") or {}).get("entities", [])),
        "nodes": len(nodes),
        "connections": len(connections),
        "status": doc.get("status", "draft"),
    }


@mcp.tool(title="Get interview guide", annotations=RO)
def get_interview_guide() -> dict:
    """START HERE in any Alto session. Returns the interview/build guide
    (including the non-negotiable closed-system rule §0) plus the user's
    resumable drafts."""
    guide = (ROOT / "interview_guide.md").read_text(encoding="utf-8")
    drafts = []
    st = get_store()
    for t in st.list_timelines(uid()):
        tid = t["timeline_id"]
        drafts.append({
            "timeline_id": tid,
            "title": (t.get("brief") or {}).get("title", tid),
            **_completeness(t, st.list_nodes(uid(), tid),
                            st.get_connections(uid(), tid)),
        })
    return {"guide_markdown": guide, "drafts": drafts}


@mcp.tool(title="List projects", annotations=RO)
def list_projects() -> dict:
    """List the user's Alto projects and the timelines inside them."""
    st = get_store()
    timelines = st.list_timelines(uid())
    projects = []
    for p in st.list_projects(uid()):
        projects.append({
            **{k: p[k] for k in ("project_id", "name", "purpose", "kind")},
            "timelines": [
                {"timeline_id": t["timeline_id"],
                 "title": (t.get("brief") or {}).get("title"),
                 "status": t.get("status", "draft")}
                for t in timelines if t.get("project_id") == p["project_id"]],
        })
    return {"projects": projects}


@mcp.tool(title="Create project", annotations=RW)
def create_project(name: str, purpose: str = "",
                   kind: str = "studying") -> dict:
    """Create a project container (Flow 1). kind: studying|writing|research.
    Name + purpose only — Alto never stores generated blurbs."""
    st = get_store()
    existing = {p["project_id"] for p in st.list_projects(uid())}
    if len(existing) >= MAX_PROJECTS:
        return {"error": "quota", "message": f"max {MAX_PROJECTS} projects"}
    pid = _unique_slug(existing, _slug(name))
    st.put_project(uid(), pid, {
        "project_id": pid, "name": name.strip(), "purpose": purpose.strip(),
        "kind": kind, "created": _now()})
    return {"project_id": pid}


@mcp.tool(title="Create timeline draft", annotations=RW)
def create_timeline(project_id: str, brief: dict) -> dict:
    """Create a timeline draft from the build brief (Flow 2 §B–§I). brief:
    {title, subject?, timeline_id?, columns?: 3|5, node_noun?, accent?,
     entity_axis_label?, entity_axis_singular?,
     acts: [{label, short?, color?}] (2-7),
     axes?: [{label, singular, values:[{id,name,...}]}] (≤2),
     relations?: [{key,label?,color?}] ('spine' = neutral main thread),
     overview_html?, owner_name?, owner_email?}.
    Entities are set separately via set_entities. Returns validation warnings."""
    st = get_store()
    project_id, err = _check_ref(project_id, "project_id")
    if err:
        return err
    if not st.get_project(uid(), project_id):
        return {"error": "not_found", "message": f"project {project_id!r} not found"}
    existing = {t["timeline_id"] for t in st.list_timelines(uid())}
    if len(existing) >= MAX_TIMELINES:
        return {"error": "quota", "message": f"max {MAX_TIMELINES} timelines"}
    # A caller-supplied timeline_id becomes a store directory and a published
    # URL segment, so it is checked here; a derived one is already a slug.
    if brief.get("timeline_id"):
        tid, err = _check_ref(brief["timeline_id"], "brief.timeline_id")
        if err:
            return err
    else:
        tid = _slug(brief.get("title", ""))
    tid = _unique_slug(existing, tid)
    brief = {**brief, "timeline_id": tid}
    try:
        b, _, _ = load_brief({"brief": brief})
        from .build.brief import validate_brief
        warnings = validate_brief(b)
    except (BriefError, TypeError) as e:
        return {"error": "invalid_brief", "message": str(e)}
    st.put_timeline(uid(), tid, {
        "timeline_id": tid, "project_id": project_id, "brief": brief,
        "consent": {"granted": False}, "status": "draft",
        "visibility": "private", "created": _now()})
    return {"timeline_id": tid, "warnings": warnings,
            "next": "record_materials_consent (§A gate) before any nodes"}


@mcp.tool(title="Record materials + consent (§0 gate)", annotations=RW)
def record_materials_consent(timeline_id: str, sources: list[dict],
                             consent: bool) -> dict:
    """THE HARD GATE (§A). Call only after (1) the user provided real
    materials in the conversation and (2) they explicitly agreed to the
    closed-system statement. sources: factual manifest, e.g.
    [{name:'ConLaw syllabus.pdf', kind:'syllabus'}] — the materials themselves
    stay in the conversation. Until consent=true, node authoring is locked."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    if consent and not sources:
        return {"error": "no_sources",
                "message": "consent without a source manifest is not a gate — "
                           "list the actual materials provided"}
    doc["consent"] = {"granted": bool(consent), "at": _now(),
                      "sources": sources}
    get_store().put_timeline(uid(), timeline_id, doc)
    return {"gate": "open" if consent else "closed"}


@mcp.tool(title="Set entities", annotations=RW)
def set_entities(timeline_id: str, entities: list[dict]) -> dict:
    """Define the entity axis (the chips): ≤12 entities
    [{id, name, role?, color?, symbol_svg?, sections?: [{h,t}]}].
    Omitted colors get a clean palette. Detail-page sections must come
    verbatim from the user's materials (§0)."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    brief = {**doc["brief"], "entities": entities}
    try:
        b, _, _ = load_brief({"brief": brief})
        from .build.brief import validate_brief
        warnings = validate_brief(b)
    except BriefError as e:
        return {"error": "invalid_entities", "message": str(e)}
    doc["brief"] = brief
    get_store().put_timeline(uid(), timeline_id, doc)
    return {"palette": {e.id: e.color for e in b.entities},
            "warnings": warnings}


@mcp.tool(title="Add or update nodes", annotations=RW)
def add_nodes(timeline_id: str, nodes: list[dict]) -> dict:
    """Batch-add/update timeline nodes (idempotent upsert by id). Each:
    {id, act (0-based), tag, title, desc, col?, entity_ids?, axis1_values?,
     axis2_values?, sections?: [{h,t}]}.
    §0: title/desc/sections are authored VERBATIM from the user's materials —
    never fill gaps, never collapse multi-item arcs into one node. Column
    guidance: alternate sides; 'center' for pivotal beats; omit col for the
    deterministic fallback. Locked until the consent gate is open."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    if not _consent_ok(doc):
        return CONSENT_ERROR
    st = get_store()
    existing = st.list_nodes(uid(), timeline_id)
    merged = {n["id"]: n for n in existing}
    for n in nodes:
        merged[n.get("id", "")] = {**n}
    if len(merged) > MAX_NODES:
        return {"error": "quota", "message": f"max {MAX_NODES} nodes"}
    try:
        b, all_nodes, _ = load_brief({
            "brief": doc["brief"],
            "nodes": [{k: v for k, v in n.items() if not k.startswith("_")}
                      for n in merged.values()]})
        from .build.brief import validate_nodes
        warnings = validate_nodes(b, all_nodes)
    except BriefError as e:
        return {"error": "invalid_nodes", "message": str(e),
                "hint": "fix the listed node and resend just that node"}
    st.put_nodes(uid(), timeline_id, nodes)
    return {"accepted": [n["id"] for n in nodes],
            "total_nodes": len(merged), "warnings": warnings}


@mcp.tool(title="Add connections", annotations=RW)
def add_connections(timeline_id: str, connections: list[list[str]]) -> dict:
    """Set the full connection list: [[source_id, target_id, relation_key],
    ...]. Endpoints must be existing nodes; relation_key must be in the
    brief's vocabulary ('spine' = neutral main thread). Replaces the stored
    list (send the complete set)."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    if not _consent_ok(doc):
        return CONSENT_ERROR
    if len(connections) > MAX_CONNECTIONS:
        return {"error": "quota", "message": f"max {MAX_CONNECTIONS} connections"}
    st = get_store()
    nodes = st.list_nodes(uid(), timeline_id)
    from .build.verify import verify_data
    b, all_nodes, _ = load_brief({"brief": doc["brief"],
                                  "nodes": [{k: v for k, v in n.items()
                                             if not k.startswith("_")}
                                            for n in nodes]})
    from .build.layout import assign_columns
    assign_columns(all_nodes, b.columns)
    failures = [f for f in verify_data(b, all_nodes, connections)
                if "has no nodes" not in f]      # act coverage checked at build
    if failures:
        return {"error": "invalid_connections", "failures": failures}
    st.put_connections(uid(), timeline_id, connections)
    return {"accepted": len(connections)}


@mcp.tool(title="Set overview", annotations=RW)
def set_overview(timeline_id: str, overview_html: str) -> dict:
    """Optional prose overview panel (HTML paragraphs; may deep-link nodes via
    onclick=\"showDetail('node','<id>')\"). Authored from the user's material
    (§0). Link targets are validated at build."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    if not _consent_ok(doc):
        return CONSENT_ERROR
    doc["brief"] = {**doc["brief"], "overview_html": overview_html}
    get_store().put_timeline(uid(), timeline_id, doc)
    return {"ok": True}


def _load_full(doc):
    st = get_store()
    nodes = [{k: v for k, v in n.items() if not k.startswith("_")}
             for n in st.list_nodes(uid(), doc["timeline_id"])]
    return load_brief({"brief": doc["brief"], "nodes": nodes,
                       "connections": st.get_connections(uid(), doc["timeline_id"])})


@mcp.tool(title="Run layout (preview)", annotations=RO)
def run_layout_preview(timeline_id: str) -> dict:
    """Cheap layout dry-run: resolves columns + vertical positions and reports
    world height, per-column balance, and warnings — iterate here before
    build_timeline."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    try:
        b, nodes, conns = _load_full(doc)
        from .build.brief import validate_brief, validate_nodes
        warnings = validate_brief(b) + validate_nodes(b, nodes)
        if not nodes:
            return {"error": "no_nodes", "message": "add_nodes first"}
        _, _, world_h, _, mobile_h, report = run_layout(b, nodes)
    except (BriefError, VerifyError, ValueError) as e:
        return {"error": "layout_failed", "message": str(e)}
    return {**report, "mobile_world_height": mobile_h, "warnings": warnings}


@mcp.tool(title="Build timeline", annotations=RW)
def build_timeline(timeline_id: str) -> dict:
    """Emit the timeline from the engine template, verify it (structure,
    geometry, no invented slots), and store the artifacts (hosted page +
    offline single-file). Fails with the exact check list on any violation."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    if not _consent_ok(doc):
        return CONSENT_ERROR
    try:
        b, nodes, conns = _load_full(doc)
        if not nodes:
            return {"error": "no_nodes", "message": "add_nodes first"}
        html, report = _build(b, nodes, conns)
        offline = bundle(b, html)
    except VerifyError as e:
        return {"error": "verify_failed", "failures": e.failures}
    except (BriefError, ValueError) as e:
        return {"error": "build_failed", "message": str(e)}
    from .hosted import hosted_timeline
    st = get_store()
    st.put_artifact(uid(), timeline_id, "timeline.html", html)
    st.put_artifact(uid(), timeline_id, "hosted.html",
                    hosted_timeline(html, timeline_id))
    st.put_artifact(uid(), timeline_id, "offline.html", offline)
    doc["status"] = "built"
    doc["build_report"] = report
    st.put_timeline(uid(), timeline_id, doc)
    return {"verify": "passed", **report,
            "next": "publish_timeline to get shareable links"}


@mcp.tool(title="Publish timeline", annotations=RW)
def publish_timeline(timeline_id: str, visibility: str = "private") -> dict:
    """Publish the built timeline. visibility: 'private' (only the signed-in
    owner) or 'link' (anyone with the URL). Returns view + offline-download
    URLs."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    if doc.get("status") not in ("built", "published"):
        return {"error": "not_built", "message": "build_timeline first"}
    if visibility not in ("private", "link"):
        return {"error": "bad_visibility", "message": "private|link"}
    st = get_store()
    st.put_share(timeline_id, {"uid": uid(), "visibility": visibility})
    doc["status"] = "published"
    doc["visibility"] = visibility
    # Minted once and kept, so re-publishing does not invalidate a link the
    # owner has already shared. Revoking (visibility='private') removes the
    # directory; publishing again reuses the same slug.
    if visibility == "link" and not doc.get("share_slug"):
        doc["share_slug"] = _share_slug(timeline_id)

    mode = os.environ.get("ALTO_PUBLISH_MODE", "")
    base = os.environ.get("ALTO_PUBLIC_BASE", "")
    if mode == "firebase-static":
        # Free-tier path: regenerate the static site (all link-visible
        # timelines + homepage + reports) and deploy with the Firebase CLI.
        from .publish_static import regenerate_site, deploy_site, \
            firebase_configured, PublishError
        st.put_timeline(uid(), timeline_id, doc)
        if not firebase_configured():
            # No web publishing set up (new user without a Firebase site):
            # the timeline is still fully usable/shareable as the offline file.
            offline_path = st.put_artifact(
                uid(), timeline_id, "offline.html",
                st.get_artifact(uid(), timeline_id, "offline.html") or "")
            urls = {"offline_path": offline_path,
                    "note": ("Web publishing isn't configured, so there is no "
                             "URL — but the offline file above IS the full "
                             "timeline (double-click to open, send to share). "
                             "To get shareable links, set up a free Firebase "
                             "Hosting site (see README §Publishing).")}
            doc["urls"] = urls
            st.put_timeline(uid(), timeline_id, doc)
            return {"visibility": visibility, **urls}
        try:
            site = regenerate_site(st, uid())
            live = deploy_site(site)
        except PublishError as e:
            return {"error": "publish_failed", "message": str(e)}
        slug = doc.get("share_slug") or timeline_id
        urls = ({"view_url": f"{live}/t/{slug}/",
                 "download_url": f"{live}/t/{slug}/offline.html",
                 "note": ("anyone with this link can read it — it is public, "
                          "just unguessable. publish_timeline(visibility="
                          "'private') takes it down.")}
                if visibility == "link" else
                {"note": "private — removed from the public site"})
    elif base:
        slug = doc.get("share_slug") or timeline_id
        urls = {"view_url": f"{base}/t/{slug}",
                "download_url": f"{base}/t/{slug}/download"}
    else:  # local dev: artifact paths
        urls = {"view_path": st.put_artifact(uid(), timeline_id, "timeline.html",
                                             st.get_artifact(uid(), timeline_id, "timeline.html") or ""),
                "offline_path": st.put_artifact(uid(), timeline_id, "offline.html",
                                                st.get_artifact(uid(), timeline_id, "offline.html") or "")}
    doc["urls"] = urls
    st.put_timeline(uid(), timeline_id, doc)
    return {"visibility": visibility, **urls}


@mcp.tool(title="Get timeline state", annotations=RO)
def get_timeline(timeline_id: str) -> dict:
    """Full draft state for resuming: brief, consent, node ids, connection
    count, status, urls."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    st = get_store()
    nodes = st.list_nodes(uid(), timeline_id)
    conns = st.get_connections(uid(), timeline_id)
    return {
        "timeline_id": timeline_id,
        "project_id": doc.get("project_id"),
        "brief": doc.get("brief"),
        "consent": doc.get("consent"),
        "node_ids": [n["id"] for n in nodes],
        "connection_count": len(conns),
        "status": doc.get("status"),
        "urls": doc.get("urls", {}),
        **_completeness(doc, nodes, conns),
    }


@mcp.tool(title="Delete nodes", annotations=ToolAnnotations(destructiveHint=True))
def delete_nodes(timeline_id: str, node_ids: list[str]) -> dict:
    """Remove nodes from the draft (e.g. after §J scope reconciliation).
    Connections touching removed nodes are dropped too."""
    doc, err = _timeline_or_error(timeline_id)
    if err:
        return err
    st = get_store()
    st.delete_nodes(uid(), timeline_id, node_ids)
    remaining = {n["id"] for n in st.list_nodes(uid(), timeline_id)}
    conns = [c for c in st.get_connections(uid(), timeline_id)
             if c[0] in remaining and c[1] in remaining]
    st.put_connections(uid(), timeline_id, conns)
    return {"deleted": node_ids, "remaining_nodes": len(remaining),
            "remaining_connections": len(conns)}


@mcp.prompt(title="Alto interview")
def alto_interview() -> str:
    """Run the Alto new-project / new-timeline interview."""
    return (ROOT / "interview_guide.md").read_text(encoding="utf-8")


def main():
    transport = os.environ.get("ALTO_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
