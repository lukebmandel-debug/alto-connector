"""Free-tier publishing: regenerate a static Alto site and deploy it with the
Firebase CLI (Spark plan — no server, no card).

Site layout (Firebase Hosting site `alto-connector`, static only):
  /index.html            — the owner's Alto homepage; lists nothing until
                           they sign in, then their pages from Firestore
  /pv/{key}/index.html   — sign-in shell for a 'private-web' timeline; the
                           page itself is NOT here, it is in Firestore
  /pv/index.html         — the same shell, which every other /pv/{key}/
                           rewrites to (see deploy_site)
  /connect/index.html    — where Alto on the user's computer signs in as them
                           (ALTO_STORE=cloud; alto/cloud/session.py)
  /s/index.html          — shell for every share link; /s/{key}/ rewrites to
                           it, so creating or revoking a share is a Firestore
                           write and never a deploy
  /reports/index.html    — reports viewer (?course={tid})
  /alto-cloud.js         — v3 sync layer (page ↔ Firestore directly; Spark-free)
  /alto-bglib.js         — imported backgrounds: the picker's "Yours" section and
                           the import (build/backgrounds_import.py); the pictures
                           themselves are in the owner's Firestore, never here
  /privacy/, /terms/, /credits/ index.html (build/legal.py)

No timeline content is ever in the static site. 'private' timelines never
leave the machine; 'private-web' ones live in Firestore behind the owner's
Google sign-in, and reach anyone else only through a share link the owner
creates (and can revoke) from their homepage. There used to be a public
'link' visibility served from /t/{slug}/; it is gone, and every publish
deletes /t/, /p/ and /offline.html from the staged site so a page published
that way cannot survive the next deploy.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import urllib.error
import urllib.request

from .build import legal
from .build.builder import build_timeline, load_brief, stored_brief
from .build.fingerprint import META_NAME, build_fingerprint
from .build.pages import build_home, build_reports
from .build.private_shell import shell as private_shell
from .build.share_shell import shell as share_shell
from .build.single_file import private_page
from .build.engine_stamp import stamp as stamp_engine
from .hosted import hosted_home, hosted_reports
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
    from .cloud.provision import wrapper_path
    if wrapper_path().exists():             # the CLI set_up_site installed
        return str(wrapper_path())
    return str(Path.home() / ".local" / "node" / "bin" / "firebase")


class PublishError(RuntimeError):
    pass


def rules_path() -> Path:
    """The Firestore rules every deploy ships: the package's copy, else the
    checkout's. Missing is an error, never a hosting-only deploy — pages
    without their rules look published and are not protected."""
    for p in (Path(__file__).resolve().parent / "firestore.rules",
              REPO / "firestore.rules"):
        if p.exists():
            return p
    raise PublishError("firestore.rules is missing from this Alto install, so "
                       "its security rules cannot be deployed; reinstall Alto")


# Timelines the last regenerate_site() could not rebuild, so had to ship
# from a build-time artifact. Read by publish_timeline; a stdio MCP server
# cannot print, so a silent fallback would otherwise be invisible.
LAST_STALE: list[str] = []
# What the last regenerate_site() kept and pruned of the hosted folders, one line (see _keep_report); read by tests and the publish log.
LAST_PRUNE: list[str] = []


def _private_web(store, uid: str) -> list[dict]:
    """Timelines published as 'private-web'.

    Their titles and URLs never go into the static homepage: the signed-in
    owner's browser lists them from Firestore.
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
        b, nodes, conns = load_brief({"brief": stored_brief(doc), "nodes": nodes,
                                      "connections": store.get_connections(uid, tid)})
        html, _ = build_timeline(b, nodes, conns)
        return html, ""
    except Exception as e:                      # noqa: BLE001 — see docstring
        return None, f"{type(e).__name__}: {e}"


def regenerate_site(store, uid: str, site_dir: Path | None = None) -> Path:
    site = Path(site_dir or os.environ.get("ALTO_SITE_DIR")
                or default_site_dir())
    site.mkdir(parents=True, exist_ok=True)

    # Public pages from the old 'link' visibility, and the offline bundles
    # built from them. Nothing writes these any more; deleting them here is what
    # takes a formerly public timeline off the web on the next deploy.
    for gone in (site / "t", site / "p"):
        if gone.exists():
            shutil.rmtree(gone)
    if (site / "offline.html").exists():
        (site / "offline.html").unlink()
    stale_notes = LAST_STALE
    stale_notes.clear()
    LAST_PRUNE.clear()
    name_by_pid = {p["project_id"]: p["name"] for p in store.list_projects(uid)}

    (site / "index.html").write_text(hosted_home(build_home([])),
                                     encoding="utf-8")
    # What the homepage starts a timeline from when the owner makes one there
    # themselves (alto/build/starter.py). Only where there is an account to
    # keep it in.
    starters = site / "new"
    if starters.exists():
        shutil.rmtree(starters)
    if load_config().get("apiKey"):
        from .build.starter import write as write_starters
        write_starters(site)

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
    # This deploy's stamp, in every private shell: a page cached under an
    # older one is fetched fresh instead of shown and then swapped (see
    # private_shell, SITE_V). Opaque and compared only for equality.
    # Derived from what the deploy ships (this code, the script), not random: a
    # random one made every regenerate differ, so a one-timeline publish could
    # never be told apart from a changed site and always redeployed it.
    site_v = hashlib.sha256(f"{cloud_v}|{build_fingerprint()}".encode()).hexdigest()[:12]
    # A private timeline is opened by signing in; with no Firebase project there
    # is nothing to sign into, so the shell would be a locked door with no key —
    # and the page would never reach Firestore to begin with. Refuse rather than
    # publish something no one, including the owner, can ever open.
    if private and not load_config().get("apiKey"):
        raise PublishError(
            f"{len(private)} page(s) are published as 'private-web', but "
            "this site has no Firebase project configured, so Google sign-in "
            "is off and nobody could ever open them. Call set_up_site: it "
            "reads the project's web config itself (never ask the user to "
            "paste it).")
    from .build import palace_tiles
    cmap_refs: set = set()
    named_refs, store_ok = _stored_page_refs(store, uid)     # the hosted files the pages stored BEFORE this run name (binned ones too): a republish may be refused, and then they stay
    for t in private:
        key = check_component(t["private_key"], "private_key")
        live_keys.add(key)
        d = pvdir_root / key
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(private_shell(cloud_v, site_v), encoding="utf-8")
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
            # Stamped here too: this artifact REPLACES the one build_timeline
            # stamped, and it is what gets stored. Unstamped, no page could say
            # which Alto built it and the no-downgrade guard had nothing to compare.
            page = stamp_engine(private_page(b, raw, name_by_pid.get(t.get("project_id", ""), "")))
            cmap_refs |= palace_tiles.page_refs(page)          # the city base the page loads (build/palace_tiles.py)
            named_refs |= hosted_refs(page)
            store.put_artifact(uid, tid, "private.html", page)

    # Never prune what a stored page names (a refused or skipped republish leaves its page naming the file of an earlier build): read those
    # files now, before any folder below is replaced, and put back whichever the replacing dropped (see _pin_named / _restore_kept).
    from .build.palace_assets import assets as palace_assets, folders as palace_folders, BLOB_FOLDERS, RETIRED_FOLDERS
    from .build import fpv_gfx
    from .buildings.pma_art import ART_FOLDER, files as art_files
    new_assets = palace_assets(building_plans=_building_plans(store, uid), cmap_refs=cmap_refs)
    fresh_by = {}
    for f_, n_, _t in new_assets:
        fresh_by.setdefault(f_, set()).add(n_)
    fresh_by.setdefault(fpv_gfx.FOLDER, set()).update(n for n, _b in fpv_gfx.files())
    fresh_by.setdefault(ART_FOLDER, set()).update(n for n, _b in art_files())
    # The previous release's versioned files stay one release (a connector one release behind builds pages that name them): the manifest decides which.
    keep_prev, manifest = _keep_plan(site, fresh_by)
    named_refs = set(named_refs) | {f"{f_}/{n_}" for f_, ns in keep_prev.items() for n_ in ns}
    keep_all = not store_ok                                    # the store could not be read: nothing is pruned (item "never prune blind")
    before = _listing(site, fresh_by)
    pinned = _pin_named(site, named_refs)

    # ── share links ─────────────────────────────────────────────────────
    # ONE shell for every share that will ever exist. /s/{key}/ is rewritten to
    # it by Hosting (see deploy_site), so the owner can mint a share from their
    # homepage and send the link immediately — no deploy, and nothing on this
    # machine ever learns the key. It is also what makes revoking instant: a
    # deleted Firestore document, not a republished site.
    sdir = site / "s"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "index.html").write_text(share_shell(cloud_v), encoding="utf-8")

    if pvdir_root.exists():
        for d in pvdir_root.iterdir():
            if d.is_dir() and d.name not in live_keys:
                shutil.rmtree(d)
    # The shell is identical for every key and carries nothing, so it also
    # answers /pv/{key}/ for keys this site did not publish — a private
    # timeline listed on the homepage because the SAME account published it
    # from another site on this Firebase project. Without it that chip was a
    # 404. Firestore's rules, not the shell, still decide who reads the page.
    if load_config().get("apiKey"):
        pvdir_root.mkdir(parents=True, exist_ok=True)
        (pvdir_root / "index.html").write_text(private_shell(cloud_v, site_v),
                                               encoding="utf-8")
        # Where Alto on the user's computer signs in as them (ALTO_STORE=cloud).
        from .build.connect_page import connect_page
        cdir = site / "connect"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "index.html").write_text(connect_page(cloud_v), encoding="utf-8")

    # Bass "Add from Drive": the Picker's own page (build/drive_picker_page.py); written only when the Bass UI is built in with a proxy base, or manual edit's Add from Drive is on (all three ALTO_DRIVE_* set)
    if _picker_csp():
        from .build.drive_picker_page import FOLDER as _PK, picker_js, picker_page
        pkdir = site / _PK
        pkdir.mkdir(parents=True, exist_ok=True)
        (pkdir / "index.html").write_text(picker_page(), encoding="utf-8")
        (pkdir / "picker.js").write_text(picker_js(), encoding="utf-8")

    # reports viewer (no public courses to preselect)
    rdir = site / "reports"
    rdir.mkdir(exist_ok=True)
    (rdir / "index.html").write_text(
        hosted_reports(build_reports([], "")), encoding="utf-8")

    # Emitted, not copied: the Firebase project comes from the publisher's own
    # ALTO_FIREBASE_CONFIG, and is empty (sync off) when they have not set one.
    write_cloud_js(site / "alto-cloud.js")
    # The script behind imported backgrounds (build/backgrounds_import.py): fetched by a page only when its picker
    # opens or one of the account's own pictures is in use, never part of the page.
    from .build.backgrounds_import import site_file as _bglib_file
    _bl_name, _bl_text = _bglib_file()
    (site / _bl_name).write_text(_bl_text, encoding="utf-8")
    # The photographs a user can choose as a background (build/backgrounds.py),
    # in a versioned folder the headers let browsers keep for a year.
    from .build.backgrounds import BG_V
    bg_src = Path(__file__).resolve().parent / "assets" / "backgrounds"
    bg_out = site / "bg"
    if bg_out.exists():
        shutil.rmtree(bg_out)
    if bg_src.is_dir():
        shutil.copytree(bg_src, bg_out / f"v{BG_V}")
    # The Memory Palace's hosted scripts (build/palace_assets.py: the fleet's toy weapons, the Memory Blueprint, ...): code, not page, each in a
    # folder named by the content hash of its file.
    for folder in RETIRED_FOLDERS:                                # the city's first-person view, retired: nothing of it stays on the site
        if (site / folder).exists():
            shutil.rmtree(site / folder)
    for folder in palace_folders():
        out_ = site / folder
        if folder in BLOB_FOLDERS:
            # content-hash-named blobs: remove only the files no page names and this publish does not write (never one still referenced)
            out_.mkdir(parents=True, exist_ok=True)
            fresh = {n for f, n, _t in new_assets if f == folder}
            keep = fresh
            for p_ in out_.iterdir():
                if p_.name not in keep and not keep_all:
                    p_.unlink() if p_.is_file() else shutil.rmtree(p_)
            continue
        kept = _bldg_kept(out_) if folder == "bldg" else {}      # (every other folder's earlier files come back through the pins above)
        if folder in NEVER_PRUNED:
            kept.update(_never_pruned(out_, NEVER_PRUNED[folder]))
        if out_.exists() and not keep_all:
            shutil.rmtree(out_)
        out_.mkdir(exist_ok=True)
        for kname, (kbytes, kt) in kept.items():
            (out_ / kname).write_bytes(kbytes)
            os.utime(out_ / kname, (kt, kt))                 # its age kept: the oldest go first
    for folder, aname, atext in new_assets:
        (site / folder).mkdir(parents=True, exist_ok=True)
        (site / folder / aname).write_text(atext, encoding="utf-8")
    # The FPV graphics pass (build/fpv_gfx.py): CC0 material sets and the HDRI sky as KTX2, the Basis transcoder; binary, content-hash named, under /gfx/,
    # fetched lazily by the Memory Blueprint's first-person renderer (never by their low tiers); without them the procedural look stays
    gfx_out = site / fpv_gfx.FOLDER
    if gfx_out.exists() and not keep_all:
        shutil.rmtree(gfx_out)
    for gname, gbytes in fpv_gfx.files():
        gfx_out.mkdir(parents=True, exist_ok=True)
        (gfx_out / gname).write_bytes(gbytes)
    # Holographic's looping background clips (build/holo_video.py): binary, content-hash named, under /hvid/, named only by the hosted Holographic script
    from .build import holo_video
    hv_out = site / holo_video.FOLDER
    if hv_out.exists() and not keep_all:
        shutil.rmtree(hv_out)
    for hname, hbytes in holo_video.files():
        hv_out.mkdir(parents=True, exist_ok=True)
        (hv_out / hname).write_bytes(hbytes)
    # The curated buildings' artwork images (alto/buildings: the PMA's public-domain paintings), binary, content-hash named, under /bart/
    art_out = site / ART_FOLDER
    if art_out.exists() and not keep_all:
        shutil.rmtree(art_out)
    for aname, abytes in art_files():
        art_out.mkdir(parents=True, exist_ok=True)
        (art_out / aname).write_bytes(abytes)
    # A page names a city file the cache does not have: its map would not load. Say so (publish_timeline refuses a stale build unless ALTO_ALLOW_STALE).
    for name in palace_tiles.LAST_MISSING:
        if name not in _on_site(site / palace_tiles.FOLDER):
            stale_notes.append(f"city data {name}: a published palace names it, but it is not in {palace_tiles.blob_dir()} — rebuild that page "
                               "(or restore the folder) before publishing, or its map does not load")
    _restore_kept(site, pinned)
    _keep_report(site, before, fresh_by, keep_prev, keep_all, manifest)
    for key, text in legal.pages().items():              # /privacy/ /terms/ /credits/: the words are alto/legal/*.md
        ldir = site / key
        ldir.mkdir(exist_ok=True)
        (ldir / "index.html").write_text(text, encoding="utf-8")
    return site


PIN_SKIP = ("street/", "tex/")                        # retired folders (palace_assets.RETIRED_FOLDERS): a publish removes them on purpose


def _stored_page_refs(store, uid: str, timelines=None) -> tuple[set, bool]:
    """(refs, ok): every hosted file (hosted_refs) named by ANY page stored for ANY of the user's timelines (private.html and timeline.html), binned
    (Recently deleted) ones, drafts and unpublished ones included: a binned timeline can be restored, and its page must still find its files. The one
    exception is a Memory Blueprint plan (bldg/plan-<hash>.json, the user's own building data, publicly hosted): only a published, unbinned
    timeline keeps its plan, so a plan is still pruned once its timeline stops being published or is binned. Recomputed on every deploy.
    ok is False when the store could not be read (quota or error): the deploy then prunes NOTHING (see regenerate_site / _warn_unpinned)."""
    out = set()
    try:
        rows = store.list_timelines(uid) if timelines is None else timelines
        binned = {pg["key"] for pg in store.list_pages(uid) if pg.get("binned")} if hasattr(store, "list_pages") else set()
    except Exception as e:                                  # noqa: BLE001
        _warn_unpinned(f"the stored pages could not be listed ({e})")
        return out, False
    ok = True
    for t in rows:
        live = t.get("status") == "published" and t.get("visibility") == "private-web" and not t.get("binned") and t.get("private_key") not in binned
        try:
            refs = set()
            for art in ("private.html", "timeline.html"):
                refs |= hosted_refs(store.get_artifact(uid, t.get("timeline_id") or t.get("id"), art))
        except Exception as e:                              # noqa: BLE001
            _warn_unpinned(f"{t.get('timeline_id') or t.get('id')}: its stored page could not be read ({e})")
            ok = False
            continue
        out |= refs if live else {r for r in refs if not r.startswith("bldg/plan-")}
    return out, ok


def _warn_unpinned(why: str) -> None:
    msg = f"stored pages could not be read ({why}); this deploy keeps EVERY hosted file already on the site and prunes nothing"
    logging.getLogger(__name__).warning(msg)
    LAST_STALE.append(msg)


def _pin_named(site: Path, refs) -> dict:
    """{ref: (bytes, mtime)} of the files in `refs` the site dir holds now, plus, transitively (each file once), the hosted files those scripts and
    data files name (the hosted Holographic script names its /hvid/ clips). Retired folders and symlinks are left out."""
    out, todo = {}, sorted(refs)
    while todo:
        ref = todo.pop()
        p = site / ref
        if ref in out or ref.startswith(PIN_SKIP) or ".." in ref or p.is_symlink() or not p.is_file():
            continue
        out[ref] = (p.read_bytes(), p.stat().st_mtime)
        if ref.endswith((".js", ".json")):
            todo += sorted(hosted_refs(out[ref][0].decode("utf-8", "replace")))
    return out


def _building_plans(store, uid: str) -> dict:
    """{plan-<hash>.json: JSON text} of every published Memory Blueprint (build/building_schema.py): the file its page fetches from /bldg/."""
    from .build import building_schema as bs
    out = {}
    try:
        timelines = store.list_timelines(uid)
    except Exception:                                       # noqa: BLE001
        return out
    for t in timelines:
        if t.get("status") != "published":
            continue
        brief = t.get("brief") or {}
        z = (brief.get("building") or {}).get("plan_z") if brief.get("palace_view") == "building" else None
        if not z:
            continue
        try:
            name, text = bs.hosted_json(bs.unpack(z))
        except Exception:                                   # noqa: BLE001 — a plan that cannot be read ships nothing (the page keeps its cards)
            continue
        out[name] = text
    return out


ASSET_NAME_RE = re.compile(r"^(?P<kind>[^ ]+?)-[0-9a-f]{8,12}(?P<ext>\.[A-Za-z0-9.]+)$")


KEEP_MANIFEST = ".release-keep.json"          # a dotfile: Hosting's ignore ("**/.*") never deploys it; it lives in the site folder
KEEP_SKIP = ("bldg/plan-",)                   # a Memory Blueprint plan is the user's data, kept only while its timeline is published (see _stored_page_refs)


def _kind(name: str):
    m = ASSET_NAME_RE.match(name)
    return (m.group("kind") + m.group("ext")) if m else None


def _keep_plan(site: Path, fresh_by: dict) -> tuple[dict, dict]:
    """(keep, manifest): `keep` is {folder: {names}} of earlier versioned hosted files to keep through THIS publish, `manifest` the record to write
    at its end. Deterministic, from the manifest alone: for each kind of file (<kind>-<hash><ext>) the manifest holds the names this release wrote
    ("current", every build of the same version) and the previous release's ("previous"). A publish of a NEW version makes what the old release wrote
    and this one no longer writes the "previous" (kept from then on until the NEXT change of that kind); a publish of the same version only adds
    to "current" (and keeps those earlier builds). With no manifest (first run) the newest earlier file of each kind on disk (_kept_earlier) is
    the previous. mcp_server.__version__ names the release."""
    try:
        from .mcp_server import __version__ as release
    except Exception:                                       # noqa: BLE001
        release = ""
    try:
        old = json.loads((site / KEEP_MANIFEST).read_text("utf-8"))
        assert old.get("v") == 1 and isinstance(old["current"], dict) and isinstance(old["previous"], dict)
    except Exception:                                       # noqa: BLE001 — missing or unreadable: start from the disk
        old = None
    cur, prev, keep = {}, {}, {}
    for folder, names in sorted(fresh_by.items()):
        by_kind = {}
        for n in sorted(names):
            if _kind(n) and not f"{folder}/{n}".startswith(KEEP_SKIP):
                by_kind.setdefault(_kind(n), set()).add(n)
        kinds = {}
        if old is None:
            ek = {}
            for n in _kept_earlier(site / folder, names):
                if not f"{folder}/{n}".startswith(KEEP_SKIP):
                    ek.setdefault(_kind(n), set()).add(n)
            for k in sorted(set(by_kind) | set(ek)):
                kinds[k] = (by_kind.get(k, set()), ek.get(k, set()), set())
        else:
            oc, op = old["current"].get(folder, {}), old["previous"].get(folder, {})
            for k in sorted(set(by_kind) | set(oc) | set(op)):
                fresh_k, cur_old, prev_old = by_kind.get(k, set()), set(oc.get(k, ())), set(op.get(k, ()))
                if old.get("release") == release:           # the same version again: its earlier builds stay beside this one
                    kinds[k] = (fresh_k, prev_old - fresh_k, cur_old - fresh_k)
                else:                                       # a new version: what the old one wrote and this one does not is the previous release's
                    gone = cur_old - fresh_k
                    kinds[k] = (fresh_k, gone or ((prev_old - fresh_k) if fresh_k else set()), set())
        for k, (f_, p_, same) in kinds.items():
            if f_ | same:
                cur.setdefault(folder, {})[k] = sorted(f_ | same)
            if p_:
                prev.setdefault(folder, {})[k] = sorted(p_)
            keep.setdefault(folder, set()).update((p_ | same) - names)
    pr = (old or {}).get("release")
    manifest = {"v": 1, "release": release, "previous_release": (old or {}).get("previous_release") if pr == release else pr,
                "current": cur, "previous": prev}
    return keep, manifest


def _listing(site: Path, fresh_by: dict) -> dict:
    """{folder: {file names}} now on disk, for the folders a publish replaces (and hvid, the clips the hosted Holographic script names)."""
    return {f: {p.name for p in (site / f).iterdir()} for f in list(fresh_by) + ["hvid"] if (site / f).is_dir()}


def _keep_report(site: Path, before: dict, fresh_by: dict, keep: dict, keep_all: bool, manifest: dict) -> None:
    """Write the manifest and the ONE log line of this publish (per site): how many earlier files were kept and pruned, the names pruned, and any
    file the manifest wants kept that this site does not have (the only way two sites' keep sets can differ)."""
    after = _listing(site, fresh_by)
    pruned = sorted(f"{f}/{n}" for f, ns in before.items() for n in ns - after.get(f, set()))
    kept = sorted(f"{f}/{n}" for f, ns in before.items() for n in ns & after.get(f, set()) if n not in fresh_by.get(f, set()))
    missing = sorted(f"{f}/{n}" for f, ns in keep.items() for n in ns if n not in after.get(f, set()))
    try:
        site_id = (firebase_configured() or (None, site.parent.name))[1]
    except Exception:                                       # noqa: BLE001
        site_id = site.parent.name
    line = (f"prune [{site_id}] release {manifest.get('release') or '?'}: kept {len(kept)} earlier hosted file(s), pruned {len(pruned)}"
            + (" (store unreadable: pruned NOTHING)" if keep_all else "")
            + (f"; pruned: {', '.join(pruned[:20])}{' ...' if len(pruned) > 20 else ''}" if pruned else "")
            + (f"; wanted by the keep manifest but missing here: {', '.join(missing[:20])}" if missing else ""))
    LAST_PRUNE.append(line)
    logging.getLogger(__name__).log(logging.WARNING if (missing or keep_all) else logging.INFO, line)
    try:
        (site / KEEP_MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=1), encoding="utf-8")
    except OSError as e:
        logging.getLogger(__name__).warning("the keep manifest could not be written (%s): the next publish starts from the disk", e)


def _kept_earlier(d: Path, fresh, per_kind: int = 1) -> dict:
    """{name: (bytes, mtime)} of the hashed hosted files the PREVIOUS release left in folder d, for every kind of file (retro, world, phone, gfx, ...):
    a stored page names the file of the release that built it, and a deploy from newer code replaces the folder, so the page loses its file
    (Oct 23 the Museum; Oct 26 the Retro style and the Memory Atlas, between a partial publish and its finish). Keep the newest `per_kind`
    earlier file of each kind that this release does not write itself: with the new one that is the last two releases. mtimes are kept, so the
    oldest go first. Files whose names are not <kind>-<hash><ext> (and anything with a space in it) are never kept."""
    if not d.is_dir():
        return {}
    by_kind = {}
    for p in d.iterdir():
        m = p.is_file() and not p.is_symlink() and p.name not in fresh and ASSET_NAME_RE.match(p.name)
        if m:
            by_kind.setdefault(m.group("kind") + m.group("ext"), []).append(p)
    out = {}
    for files in by_kind.values():
        for p in sorted(files, key=lambda q: q.stat().st_mtime, reverse=True)[:per_kind]:
            out[p.name] = (p.read_bytes(), p.stat().st_mtime)
    return out


def _restore_kept(d: Path, kept: dict) -> None:
    for name, (data, t) in kept.items():
        d.mkdir(parents=True, exist_ok=True)
        if not (d / name).exists():
            (d / name).parent.mkdir(parents=True, exist_ok=True)     # a pinned ref is "<folder>/<file>", restored under the site dir
            (d / name).write_bytes(data)
            os.utime(d / name, (t, t))


BLDG_KEEP = 12
BLDG_RENDERER_RE = re.compile(r"^palace-building-(fpv-)?[0-9a-f]{10}\.js$")


def _bldg_kept(d: Path) -> dict:
    """{name: (bytes, mtime)} of the Memory Blueprint renderers an earlier publish left in /bldg/ (the newest BLDG_KEEP of each kind): a stored
    page names the renderer of the release that built it, so a deploy from newer code must not take that file away (civ-pro-museum,
    built by 1.9.154, lost its blueprint when the 1.9.155 site replaced the folder, 2026-10-23)."""
    if not d.is_dir():
        return {}
    files = sorted((p for p in d.iterdir() if p.is_file() and not p.is_symlink() and BLDG_RENDERER_RE.match(p.name)), key=lambda p: p.stat().st_mtime, reverse=True)
    out = {}
    for fpv in (False, True):
        for p in [p for p in files if ("-fpv-" in p.name) == fpv][:BLDG_KEEP]:
            out[p.name] = (p.read_bytes(), p.stat().st_mtime)
    return out


# hosted scripts every old published page keeps naming (pages other users published are not republished each release): never pruned, by folder
NEVER_PRUNED = {"pics": re.compile(r"^alto-ink-[0-9a-f]{8,12}\.js$"), "phone": re.compile(r"^alto-swipe-[0-9a-f]{8,12}\.js$")}


def _never_pruned(d: Path, rx) -> dict:
    """{name: (bytes, mtime)} of EVERY file in d whose name matches rx, left by earlier publishes (never a symlink)."""
    if not d.is_dir():
        return {}
    return {p.name: (p.read_bytes(), p.stat().st_mtime) for p in d.iterdir() if p.is_file() and not p.is_symlink() and rx.match(p.name)}


def _on_site(d: Path) -> set:
    return {p.name for p in d.iterdir()} if d.is_dir() else set()


def firebase_configured() -> tuple[str, str, str] | None:
    """(firebase_bin, site, project) when web publishing is set up, else None."""
    fb = firebase_bin()
    site = os.environ.get("ALTO_FIREBASE_SITE", "")
    project = os.environ.get("ALTO_FIREBASE_PROJECT", "")
    if Path(fb).exists() and _FB_NAME.match(site) and _FB_NAME.match(project):
        return fb, site, project
    return None


def _security_headers(site_dir: Path | None = None, site: str | None = None) -> list[dict]:
    """CSP and friends for the published site.

    `'unsafe-inline'` in script-src is unavoidable and deliberate: the engine is
    one large inline <script>, and engine/ is frozen. So this is not the primary
    XSS control — build/sanitize.py is. What it does buy is the rest of the
    blast radius: no third-party script origins, no plugins, no framing, no form
    posts, and no <base> rewriting.
    """
    own = (" https://%s.web.app" % site) if site and _FB_NAME.fullmatch(site) else ""

    def build(form_action: str) -> str:
        return _csp(form_action, own)
    csp = build("'none'")
    # /connect/ hands the connector its sign-in by posting a form to the user's
    # own machine (alto/build/connect_page.py) — the one place a form may go.
    connect_csp = build("http://127.0.0.1:*")
    return _headers(csp, connect_csp, _art_names(site_dir), _bldg_names(site_dir), _gfx_names(site_dir), _cmap_names(site_dir), _hv_names(site_dir), picker_csp=_picker_csp())


def _picker_csp() -> str | None:
    """The wider policy of /drive-picker/ (build/drive_picker_page.py), the one page that loads Google's Picker; None unless the Bass UI is built in
    (ALTO_BASS_UI and a proxy base), so a site without Bass is byte-identical. Never applied to any other path."""
    from .build import bass_ui
    from .build.drive_picker_page import PICKER_CSP
    from .drive_common import enabled as drive_on           # manual edit's Add from Drive (alto/drive_common.py): the same page, in "ref" mode
    return PICKER_CSP if (bass_ui.enabled() and bass_ui.base_url()) or drive_on() else None


def _csp(form_action: str, own: str = "") -> str:
    """`own` is " https://<site>.web.app" or "". WebKit does not match 'self' inside a sandboxed (opaque-origin) frame, so the shared-page
    frame, which inherits this policy, could not load the hosted palace scripts and data in Safari. Naming the site's own origin beside
    'self' fixes that and grants nothing new: the frame's origin is opaque (no storage, cookies or sign-in), and a cross-origin READ
    still needs the Access-Control-Allow-Origin header, which only the public hashed folders carry."""
    return "; ".join([
        "default-src 'self'",
        # gstatic serves the Firebase SDK; apis.google.com serves the gapi
        # loader signInWithPopup injects — without it Google sign-in (and so
        # cross-device sync) is dead on every published page.
        # 'wasm-unsafe-eval' lets WebAssembly compile (the FPV's Basis texture transcoder, build/fpv_gfx.py) and nothing else: no eval(), no new Function.
        "script-src 'self'" + own + " 'unsafe-inline' 'wasm-unsafe-eval' https://www.gstatic.com https://apis.google.com",
        "style-src 'self'" + own + " 'unsafe-inline'",
        "img-src 'self'" + own + " data: blob: https://*.googleusercontent.com",
        "font-src 'self'" + own + " data:",
        # Firestore + Identity Toolkit, which alto-cloud.js talks to directly.
        "connect-src 'self'" + own + " https://*.googleapis.com https://*.firebaseio.com "
        "wss://*.firebaseio.com https://*.firebaseapp.com" + _tile_src() + _bass_src(),
        # The Google sign-in popup's helper frame, on the project's authDomain:
        # *.firebaseapp.com by default, or this site itself when authDomain is
        # set to the site (<site>.web.app), hence 'self'.
        "frame-src 'self' https://*.firebaseapp.com",
        "object-src 'none'",
        "base-uri 'self'",
        f"form-action {form_action}",
        "frame-ancestors 'none'",
    ])


def _tile_src() -> str:
    """The palace's detail tiles' host (build/palace_tiles.tile_host) when it is another site than this one."""
    from .build.palace_tiles import tile_host
    h = tile_host()
    return (" " + h) if re.fullmatch(r"https://[a-z0-9-]+\.(web\.app|firebaseapp\.com)", h or "") else ""


def _bass_src() -> str:
    """The Bass beta proxy's origin (ALTO_BASS_BASE), only when the Bass UI is built in (ALTO_BASS_UI) AND the base is set: without both,
    the CSP is byte-identical to a build without Bass. One https origin, no wildcard; a Cloud Run (<svc>-<hash>-uc.a.run.app or <svc>-<projectnumber>.<region>.run.app) or Cloud Functions host only, https, lowercase, no port (a
    same-site path needs nothing: 'self' covers it). Anything else adds nothing, so the page's own connect-src stays closed."""
    from .build import bass_ui
    from .cloud import ext_hook                  # the generic extension hook's origin (cloud/ext_hook.py): "" unless ALTO_EXT_URL is set
    ext = ext_hook.origin()
    if not bass_ui.enabled():
        if not ext:
            return ""
        return " " + ext
    m = re.fullmatch(r"(https://[a-z0-9][a-z0-9.-]*\.(?:run\.app|cloudfunctions\.net))(?:/.*)?", bass_ui.base_url())
    if ext and not (m and m.group(1) == ext):
        return " " + ext + ((" " + m.group(1)) if m else "")
    return (" " + m.group(1)) if m else ""


def _palace_folders() -> list:
    from .build.palace_assets import folders
    return folders()


def _headers(csp: str, connect_csp: str, art_files=(), bldg_files=(), gfx_files=(), cmap_files=(), hv_files=(), picker_csp: str | None = None) -> list[dict]:
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
        # The background photographs are versioned by folder (/bg/v1/) and never
        # change under that name, so they are kept, unlike the pages around them.
        {"source": "/bg/**", "headers": [
            {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"},
        ]},
        # A hosted palace script (the fleet, the Retro style, ...) is named by a hash of its own text: it never changes under that name.
        *({"source": "/%s/**" % f, "headers": [
            {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"},
            _ANY_ORIGIN,
        ]} for f in _palace_folders() if f not in _blob_folders() and f != "bldg"),
        # bldg: the Memory Blueprint's renderers and plans, one literal immutable rule per file that exists: a plan a page names before the
        # site has it answers 404, and a folder-wide rule would make browsers keep that 404 for a year
        *_bldg_rules(bldg_files),
        # cmap: the city's base and tiles (build/palace_tiles.py), named by their content's hash, one literal immutable rule per file that exists: Hosting matches
        # headers against the request path, so a folder-wide rule would stamp "immutable" on the 404 a missing file answers with
        *_cmap_rules(cmap_files),
        # bart: the curated buildings' artwork images, one literal immutable rule per file that exists
        *_art_rules(art_files),
        # gfx: the FPV graphics pass's textures, sky and transcoder, one literal immutable rule per file that exists
        *_gfx_rules(gfx_files),
        # hvid: Holographic's looping background clips (build/holo_video.py), one literal immutable rule per file that exists
        *_hv_rules(hv_files),
        # After "**" so it wins for this path (Hosting applies matching
        # header blocks in order; a later one overrides the same key).
        {"source": "/connect/**", "headers": [
            {"key": "Content-Security-Policy", "value": connect_csp},
        ]},
        # Bass "Add from Drive": the Picker's page and ONLY that page (build/drive_picker_page.py) gets the Google origins the Picker needs.
        *([{"source": "/drive-picker/**", "headers": [
            {"key": "Content-Security-Policy", "value": picker_csp},
        ]}] if picker_csp else []),
    ]


def _blob_folders() -> tuple:
    from .build.palace_assets import BLOB_FOLDERS
    return BLOB_FOLDERS


def _gfx_names(site_dir) -> list:
    """The FPV graphics files in the site folder (build/fpv_gfx.py), only names of the published shape."""
    if site_dir is None:
        return []
    from .build.fpv_gfx import FOLDER, NAME_RE
    d = Path(site_dir) / FOLDER
    return sorted(p.name for p in d.iterdir() if p.is_file() and NAME_RE.match(p.name)) if d.is_dir() else []


def _gfx_rules(names) -> list:
    from .build.fpv_gfx import FOLDER, NAME_RE
    return [{"source": "/%s/%s" % (FOLDER, n), "headers": [
        {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}, _ANY_ORIGIN]} for n in names if NAME_RE.match(n)]


def _hv_names(site_dir) -> list:
    """The Holographic background clips in the site folder (build/holo_video.py), only names of the published shape."""
    if site_dir is None:
        return []
    from .build.holo_video import FOLDER, NAME_RE
    d = Path(site_dir) / FOLDER
    return sorted(p.name for p in d.iterdir() if p.is_file() and NAME_RE.match(p.name)) if d.is_dir() else []


def _hv_rules(names) -> list:
    from .build.holo_video import FOLDER, NAME_RE
    return [{"source": "/%s/%s" % (FOLDER, n), "headers": [{"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}]} for n in names if NAME_RE.match(n)]


def _art_names(site_dir) -> list:
    """The curated buildings' image files in the site folder (buildings/pma_art.py), only names of the published shape."""
    if site_dir is None:
        return []
    from .buildings.pma_art import ART_FOLDER, ART_RE
    d = Path(site_dir) / ART_FOLDER
    return sorted(p.name for p in d.iterdir() if p.is_file() and ART_RE.match(p.name)) if d.is_dir() else []


# A shared page runs in a sandboxed frame (share_shell.py), an opaque origin: its fetches of these hashed public files are cross-origin, the
# hosted scripts included (palace_assets.loader reads them by XHR). alto-cloud.js stays out of this: a sandboxed page has no business with it.
_ANY_ORIGIN = {"key": "Access-Control-Allow-Origin", "value": "*"}

BLDG_RE = re.compile(r"^(palace-building-(fpv-)?[0-9a-f]{10}\.js|plan-[0-9a-f]{12}\.json)$")


def _bldg_names(site_dir) -> list:
    """The Memory Blueprint files in the site folder (renderers and plans), only names of the published shape."""
    if site_dir is None:
        return []
    d = Path(site_dir) / "bldg"
    return sorted(p.name for p in d.iterdir() if p.is_file() and BLDG_RE.match(p.name)) if d.is_dir() else []


def _bldg_rules(names) -> list:
    return [{"source": "/bldg/%s" % n, "headers": [
        {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}, _ANY_ORIGIN]} for n in names if BLDG_RE.match(n)]


def _art_rules(names) -> list:
    from .buildings.pma_art import ART_FOLDER, ART_RE
    return [{"source": "/%s/%s" % (ART_FOLDER, n), "headers": [
        {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}, _ANY_ORIGIN]} for n in names if ART_RE.match(n)]


def _cmap_names(site_dir) -> list:
    """The city files in the site folder (build/palace_tiles.py), only names of the published shape."""
    if site_dir is None:
        return []
    from .build import palace_tiles
    d = Path(site_dir) / palace_tiles.FOLDER
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file() and (palace_tiles.BASE_RE.match(p.name) or palace_tiles.TILE_RE.match(p.name)))


def _cmap_rules(names) -> list:
    """Each base (a few per published palace) gets a literal immutable rule. The tiles, which may number in the thousands (a rule each
    would bloat firebase.json), share one pattern kept a day: a tile a page asks for before its host is deployed answers 404, and a
    day is the longest a browser may remember that."""
    from .build import palace_tiles
    rules = [{"source": "/%s/%s" % (palace_tiles.FOLDER, n), "headers": [
        {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}, _ANY_ORIGIN]} for n in names if palace_tiles.BASE_RE.match(n)]
    if any(palace_tiles.TILE_RE.match(n) for n in names):
        rules.append({"regex": "^/%s/t-[0-9a-f]{10}\\.json$" % palace_tiles.FOLDER, "headers": [
            {"key": "Cache-Control", "value": "public, max-age=86400"},
            # the tiles are shared geography, fetched by the palaces of other sites (palace_tiles.tile_host)
            _ANY_ORIGIN]})
    return rules


def site_digest(site_dir: Path) -> str:
    """One hash of everything a deploy ships: every file of the site, the
    security rules and the headers. Equal digests mean a deploy would put the
    same site on the web again."""
    h = hashlib.sha256()
    for p in sorted(Path(site_dir).rglob("*")):
        if p.is_file():
            h.update(p.relative_to(site_dir).as_posix().encode() + b"\0")
            h.update(hashlib.sha256(p.read_bytes()).digest())
    cfg = firebase_configured()
    h.update(rules_path().read_bytes())
    h.update(json.dumps(_security_headers(Path(site_dir), cfg[1] if cfg else None), sort_keys=True).encode())
    return h.hexdigest()


def deploy_if_changed(site_dir: Path) -> tuple[str, bool]:
    """deploy_site, unless the site's own files are what the last successful
    deploy shipped. Publishing one timeline only changes its page in Firestore,
    so it no longer redeploys the whole site (and re-verifies it). Returns
    (live url, deployed). A first publish, a changed file, key, rules or header
    always deploys."""
    marker = _marker(site_dir)
    digest = site_digest(site_dir)
    cfg = firebase_configured()
    if cfg and marker.exists() and marker.read_text().strip() == digest:
        return f"https://{cfg[1]}.web.app", False
    live = deploy_site(site_dir)      # (deploy_site clears the marker; it is written again only by mark_deployed, after the live check passes)
    return live, True


def _marker(site_dir: Path) -> Path:
    return Path(site_dir).parent / ".alto-deployed-digest"


def mark_deployed(site_dir: Path) -> None:
    """Record that this site's files are what is live AND verified (verify_live found no drift). Called by the publish only after that check, so a
    live_mismatch leaves no record and the re-run it asks for deploys and verifies again (STAMP-233 pubstamp fix)."""
    _marker(site_dir).write_text(site_digest(site_dir))


def deploy_site(site_dir: Path) -> str:
    """firebase deploy --only hosting:<site> (CLI must be logged in to the
    project). Site/project come from ALTO_FIREBASE_SITE / ALTO_FIREBASE_PROJECT."""
    cfg = firebase_configured()
    if not cfg:
        raise PublishError(
            "web publishing not configured — call set_up_site, which gives "
            "the user their own site (never ask them to set it up) "
            "or share the offline file instead")
    fb, site, project = cfg
    try:                              # a direct deploy changes what is live: any earlier "deployed and verified" record is void until a check passes again
        _marker(site_dir).unlink()
    except FileNotFoundError:
        pass
    # The rules travel with the site. Everything Alto stores in Firestore is
    # governed by them, and until now deploying them was a README step nobody
    # was reminded of — a Firestore left in test mode is world-readable and
    # world-writable for thirty days, and publishing into one exposes every
    # reader's highlights and notes to anyone who learns the project id.
    # They used to be read from the repo root, which a .mcpb bundle or a pip
    # install does not have — so every such deploy silently shipped hosting
    # only. The package carries its own copy now, and a deploy without rules
    # is refused rather than shipped.
    rules_src = rules_path()
    rules_out = site_dir.parent / "firestore.rules"
    shutil.copy(rules_src, rules_out)
    # Storage rules: one owner-only path (Bass Documents originals), every
    # other path denied. Shipped beside firestore.rules so
    # `firebase deploy --only storage` uses them.
    storage_src = rules_src.parent / "storage.rules"
    if storage_src.exists():
        shutil.copy(storage_src, site_dir.parent / "storage.rules")

    # keep firebase.json's site in step with the configured site name
    fbjson = site_dir.parent / "firebase.json"
    cfg_json = {"hosting": {
        "site": site, "public": site_dir.name, "ignore": ["**/.*"],
        # Every /s/{key}/ is the same shell, which reads its key from the URL.
        # A rewrite rather than a directory per share: a share is created in
        # the browser, and a share that needed a deploy to exist could not be
        # created there at all.
        "rewrites": [{"source": "/s/**", "destination": "/s/index.html"},
                     # Same idea for private timelines: any account's page
                     # opens from any of its sites (see regenerate_site).
                     {"source": "/pv/**", "destination": "/pv/index.html"}],
        "headers": _security_headers(site_dir, site)}}
    cfg_json["firestore"] = {"rules": rules_out.name}
    if (site_dir.parent / "storage.rules").exists():
        cfg_json["storage"] = {"rules": "storage.rules"}
    fbjson.write_text(json.dumps(cfg_json, indent=2))
    (site_dir.parent / ".firebaserc").write_text(
        json.dumps({"projects": {"default": project}}, indent=2))
    env = {**os.environ,
           "PATH": f"{Path(fb).parent}:{os.environ.get('PATH', '')}"}
    targets = [f"hosting:{site}", "firestore:rules"]
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


HOSTED_REF_RE = re.compile(r"(?<![A-Za-z0-9_.-])/((?:retro|holo|pics|world|phone|bldg|gfx|fleet|bart|tex|street|cmap|hvid)/[A-Za-z0-9_.-]+-[0-9a-f]{8,12}\.[A-Za-z0-9.]+)")


def hosted_refs(html: str) -> set:
    """Every hashed hosted file (/retro/alto-retro-<hash>.js, /world/..., /bldg/..., /cmap/...) a stored page names."""
    return {m.group(1) for m in HOSTED_REF_RE.finditer(html or "")}


def verify_assets(store, uid: str, base_url: str, timeout: int = 20) -> list[str]:
    """Walk every stored private page of the user, collect the hosted files it names and ask the live site for each: a page built by an earlier
    release must still find its files after a deploy from newer code (it did not on Oct 23 and Oct 26). Returns the problems (empty when all
    answer 200). Needs the store (the Firestore daily limit stops it: then it says so instead of passing)."""
    problems, seen = [], {}
    try:
        timelines = store.list_timelines(uid)
    except Exception as e:                                                # noqa: BLE001
        return [f"assets: the stored pages could not be read ({e})"]
    for t in timelines:
        tid = t.get("timeline_id") or t.get("id")
        try:
            page = store.get_artifact(uid, tid, "private.html")
        except Exception as e:                                            # noqa: BLE001
            problems.append(f"{tid}: its stored page could not be read ({e})")
            continue
        for ref in sorted(hosted_refs(page)):
            seen.setdefault(ref, []).append(tid)
    for ref, tids in sorted(seen.items()):
        try:
            req = urllib.request.Request(base_url.rstrip("/") + "/" + ref, method="HEAD", headers={"User-Agent": "alto-publish"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            code = str(e)[:40]
        if code != 200:
            problems.append(f"/{ref}: {code} (named by {', '.join(tids)})")
    return problems


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
