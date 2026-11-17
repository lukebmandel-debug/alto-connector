"""Edit with Bass (v1.9.235): change ONE existing timeline of the signed-in owner, Preview first, then Apply, with one step of Undo.

Four actions, all behind the hosted gate (alto/bass/hosted.py), which checks BEFORE anything here runs that the verified token's uid owns the
timeline id (a non-owned or unknown id gets the same empty answer as a bad token), and that no uid, user or account is smuggled in the body:

    edit_open     free     the owner's timeline exists -> its title and whether an Undo is waiting
    edit_preview  SPENDS   the model edits a SCRATCH COPY (never the real store); the result is held on the server, tied to this uid + timeline,
                           for a short time. Same holds, caps, allowance and refunds as every other action (it runs through BetaService/Engine).
    edit_apply    free     writes the held result: the PRIOR version is saved first (if that fails, nothing is written), then the new one.
                           Charges 0: only the preview ever spends. Ownership is checked again here, and the timeline must still be exactly
                           what the preview started from (else: preview again).
    edit_undo     free     puts the prior version back, byte for byte (one step).

Only the chosen timeline's own documents are written (its project, nodes, connections, page and list entry). The owner's copy only: a share's
documents live outside the account's own tree and are never touched, so share docs and links stay byte-identical.

Logs: class names and codes only. Never document text, a uid, a timeline id, a key or an exception message (this module logs nothing else)."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import secrets
import tempfile
import threading
import time
from pathlib import Path

from .tools import STORE_LOCK, ToolBox

log = logging.getLogger("bass.edit")

EDIT_ACTIONS = ("edit_open", "edit_preview", "edit_apply", "edit_undo")
FREE_EDIT = ("edit_open", "edit_apply", "edit_undo")            # these send nothing upstream and charge nothing
TID_RE = re.compile(r"^[a-z][a-z0-9-]{0,47}$")                   # alto.build.brief.ID_RE: the one timeline-id pattern
PREVIEW_RE = re.compile(r"^[A-Za-z0-9_-]{22,64}$")
FORBIDDEN_KEYS = frozenset({"uid", "user", "user_id", "userid", "account", "owner", "email", "token", "project_id"})
HOLD_SECONDS = 15 * 60
MAX_HOLDS = 8
SUMMARY_MAX = 40
TEXT_MAX = 4000


def valid_tid(tid) -> bool:
    return isinstance(tid, str) and bool(TID_RE.match(tid))


def smuggled(request) -> bool:
    """A uid (or anything naming an account) in the body or its args: refused. The account comes only from the verified token."""
    if not isinstance(request, dict):
        return True
    args = request.get("args", {})
    if not isinstance(args, dict):
        return True
    return bool(FORBIDDEN_KEYS & {str(k).lower() for k in request}) or bool(FORBIDDEN_KEYS & {str(k).lower() for k in args})


def _fail(code: str, message: str, status: str = "error", **extra) -> dict:
    out = {"ok": False, "status": status, "code": code, "message": message, "action_id": None, "work_saved": False, "credits": None,
           "retryable": False, "events": []}
    out.update(extra)
    return out


def _canon(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _fp(state: dict) -> str:
    return hashlib.sha256(_canon([state["doc"], state["nodes"], state["conns"]]).encode("utf-8")).hexdigest()


class _Held:
    __slots__ = ("id", "uid", "tid", "expires", "base_fp", "brief", "nodes", "conns", "page", "summary")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class EditBass:
    def __init__(self, actions, *, tools, live=lambda: True, clock=time.time, ttl: int = HOLD_SECONDS, max_holds: int = MAX_HOLDS):
        self.A = actions
        self._tools = tools                       # callable -> the REAL tool belt (its .store is the account's store); read for the state, written only by apply/undo
        self.live = live                          # callable -> bool: live_go. Off = a practice answer: apply writes nothing
        self.clock, self.ttl, self.max_holds = clock, ttl, max_holds
        self._held: dict = {}
        self._lock = threading.Lock()
        self._tlocks: dict = {}

    # -- plumbing -----------------------------------------------------------------------------------------------
    def _store(self):
        return self._tools().store

    def _tlock(self, uid: str, tid: str):
        with self._lock:
            return self._tlocks.setdefault((uid, tid), threading.Lock())

    def _purge(self) -> None:
        now = self.clock()
        with self._lock:
            for k in [k for k, h in self._held.items() if h.expires <= now]:
                self._held.pop(k, None)

    def _read(self, st, uid: str, tid: str):
        """The account's own timeline as it is now: {doc, nodes, conns, project} or None when there is no such timeline."""
        cache = getattr(st, "_nodes_cache", None)
        if isinstance(cache, dict):
            cache.clear()                                          # never a node list a few seconds old: the stale check must see what is stored now
        doc = st.get_timeline(uid, tid)
        if not isinstance(doc, dict) or doc.get("timeline_id") != tid:
            return None
        pid = doc.get("project_id") or ""
        proj = st.get_project(uid, pid) if pid else None
        return {"doc": doc, "nodes": st.list_nodes(uid, tid), "conns": st.get_connections(uid, tid), "project": proj}

    def _owned(self, uid: str, tid):
        """(store, state) when the verified uid owns this timeline id, else (store, None). Never raises."""
        try:
            if not valid_tid(tid):
                return None, None
            st = self._store()
            return st, self._read(st, uid, tid)
        except Exception as e:                    # noqa: BLE001 - the same answer as a missing timeline; the class only
            log.warning("bass edit: read failed %s", type(e).__name__)
            return None, None

    @staticmethod
    def _gone():
        return _fail("edit_not_found", "Bass could not open that timeline.")

    # -- edit_open ----------------------------------------------------------------------------------------------
    def open(self, uid: str, timeline_id: str) -> dict:
        st, state = self._owned(uid, timeline_id)
        if state is None:
            return self._gone()
        title = str((state["doc"].get("brief") or {}).get("title") or "")[:120]
        try:
            can_undo = bool(getattr(st, "has_prior", lambda *a: False)(uid, timeline_id))
        except Exception as e:                    # noqa: BLE001
            log.warning("bass edit: prior check failed %s", type(e).__name__)
            can_undo = False
        return {"ok": True, "status": "ok", "code": None, "message": "", "action_id": None, "work_saved": False, "credits": None,
                "retryable": False, "events": [], "title": title, "cards": len(state["nodes"]), "can_undo": can_undo,
                "hold_minutes": self.ttl // 60}

    # -- edit_preview (the only spend) ----------------------------------------------------------------------------
    def preview(self, uid: str, timeline_id: str, text: str, materials: list | None = None, on_event=None, library: list | None = None) -> dict:
        from .actions import _with_library, materials_text
        from . import shapes
        A = self.A
        if not isinstance(text, str) or not text.strip() or len(text) > TEXT_MAX:
            return A._bad("edit_preview needs timeline_id and text")
        if materials is not None:
            err = A._check_materials(materials, library) if materials else None
            if err:
                return err
        st, state = self._owned(uid, timeline_id)
        if state is None:
            return self._gone()
        base_fp = _fp(state)
        scratch = self._seed(uid, timeline_id, state)
        tb = ToolBox(scratch)                                      # the scratch belt: the model can only ever write a copy
        action_id = A.ids()
        events = A._start(uid, action_id, "edit", on_event)
        progress = {"cards_done": 0, "cards_total": None, "timeline_id": timeline_id}
        mats = ("\n\nThe student also gave these materials for this change; use ONLY them and this timeline's own cards:\n\n"
                + materials_text(materials)) if materials else ""
        turn = _with_library(f"{shapes.edit_text()}\n\n[Timeline {timeline_id}] {text.strip()}{mats}", library)
        res = A.engine.run_action(uid, turn, kind="chat", action_id=action_id, tools=tb, on_tool=A._progress(uid, action_id, progress, events, on_event))
        out = A._result(uid, res, events, on_event)
        out.update(timeline_id=timeline_id, changed=False, preview_id=None)
        if res.status != "done" or not res.wrote:
            return out
        try:
            made = self._finish(uid, timeline_id, state, scratch, tb)
        except Exception as e:                                     # noqa: BLE001 - nothing is held; the class only
            log.warning("bass edit: preview failed %s", type(e).__name__)
            out.update(ok=False, status="error", code="edit_preview_failed", work_saved=False,
                       message="Bass could not prepare that preview. Nothing was changed.")
            return out
        summary = made.pop("summary")
        if not (summary["added"] or summary["removed"] or summary["changed"]):
            out["message"] = (out.get("message") or "") or "Bass found nothing to change."
            return out
        pid = secrets.token_urlsafe(24)
        held = _Held(id=pid, uid=uid, tid=timeline_id, expires=self.clock() + self.ttl, base_fp=base_fp, summary=summary, **made)
        self._purge()
        with self._lock:
            while len(self._held) >= self.max_holds:
                oldest = min(self._held, key=lambda k: self._held[k].expires)
                self._held.pop(oldest, None)
            self._held[(uid, timeline_id, pid)] = held
        out.update(changed=True, preview_id=pid, summary=summary, expires_in=self.ttl, apply_charges=0)
        return out

    def _seed(self, uid: str, tid: str, state: dict):
        from alto.store.local import LocalStore
        sc = LocalStore(Path(tempfile.mkdtemp(prefix="bass-edit-")))
        if state["project"]:
            sc.put_project(uid, state["doc"].get("project_id"), copy.deepcopy(state["project"]))
        sc.put_timeline(uid, tid, copy.deepcopy(state["doc"]))
        sc.put_nodes(uid, tid, copy.deepcopy(state["nodes"]))
        sc.put_connections(uid, tid, copy.deepcopy(state["conns"]))
        return sc

    def _finish(self, uid: str, tid: str, before: dict, scratch, tb) -> dict:
        """After the model: build the page in the scratch copy (free, no upstream call), and make everything apply needs."""
        from alto import mcp_server as srv
        from ..build.engine_stamp import stamp as engine_stamp
        from ..build.private_shell import MAX_PAGE_BYTES, stored_bytes
        from ..build.single_file import private_page
        built = tb.execute(uid, "build_timeline", {"timeline_id": tid})
        if built.is_error:
            raise RuntimeError("build")
        doc = scratch.get_timeline(uid, tid)
        raw = scratch.get_artifact(uid, tid, "timeline.html")
        if not doc or not raw:
            raise RuntimeError("page")
        nodes = scratch.list_nodes(uid, tid)
        conns = scratch.get_connections(uid, tid)
        with STORE_LOCK:
            b, _, _ = srv.load_brief({"brief": doc["brief"]})
            name = (before["project"] or {}).get("name", "")
            page = engine_stamp(private_page(b, raw, name))
        if stored_bytes(page) > MAX_PAGE_BYTES:
            raise RuntimeError("size")
        old = {n["id"]: {k: v for k, v in n.items() if k != "_seq"} for n in before["nodes"]}
        new = {n["id"]: {k: v for k, v in n.items() if k != "_seq"} for n in nodes}

        def label(n):
            return str(n.get("title") or n.get("t") or n.get("name") or n.get("id"))[:120]
        summary = {"added": [label(new[i]) for i in new if i not in old][:SUMMARY_MAX],
                   "removed": [label(old[i]) for i in old if i not in new][:SUMMARY_MAX],
                   "changed": [label(new[i]) for i in new if i in old and new[i] != old[i]][:SUMMARY_MAX],
                   "counts": {"added": sum(1 for i in new if i not in old), "removed": sum(1 for i in old if i not in new),
                              "changed": sum(1 for i in new if i in old and new[i] != old[i])}}
        if (before["doc"].get("brief") or {}) != (doc.get("brief") or {}) and not summary["counts"]["changed"]:
            summary["changed"].append("the timeline's own details")
            summary["counts"]["changed"] += 1
        return {"brief": copy.deepcopy(doc["brief"]), "nodes": nodes, "conns": conns, "page": page, "summary": summary}

    # -- edit_apply (charges 0) -----------------------------------------------------------------------------------
    def apply(self, uid: str, timeline_id: str, preview_id: str, on_event=None) -> dict:
        A = self.A
        if not valid_tid(timeline_id) or not isinstance(preview_id, str) or not PREVIEW_RE.match(preview_id):
            return self._gone()
        with self._tlock(uid, timeline_id):
            st, state = self._owned(uid, timeline_id)                  # ownership again, at Apply
            if state is None:
                return self._gone()
            self._purge()
            with self._lock:
                held = self._held.get((uid, timeline_id, preview_id))
            if held is None or held.uid != uid or held.tid != timeline_id:
                return _fail("edit_preview_gone", "That preview has expired, so Bass needs to make it again. A new preview is a new charge.",
                             status="refused")
            if _fp(state) != held.base_fp:
                self._drop(uid, timeline_id, preview_id)
                return _fail("edit_stale", "The timeline changed after that preview, so Bass needs to make it again. A new preview is a new charge.",
                             status="refused")
            if not self.live():                                         # a practice answer: nothing is saved (the proxy adds the notice)
                self._drop(uid, timeline_id, preview_id)
                return self._applied(uid, applied=False, can_undo=False)
            try:
                self._write(st, uid, timeline_id, state, held)
            except _NothingWritten as e:
                return _fail(e.code, e.message, status="refused" if e.code != "edit_not_saved" else "error")
            except Exception as e:                                      # noqa: BLE001
                log.warning("bass edit: apply failed %s", type(e).__name__)
                return _fail("edit_apply_failed", "Bass could not save that change. Your timeline was put back as it was.")
            self._drop(uid, timeline_id, preview_id)
            return self._applied(uid, applied=True, can_undo=True)

    def _applied(self, uid: str, *, applied: bool, can_undo: bool) -> dict:
        return {"ok": True, "status": "ok", "code": None, "action_id": None, "work_saved": applied, "retryable": False, "events": [],
                "message": "Your timeline was changed. You can undo it." if applied else "Practice mode: nothing was saved to your account.",
                "applied": applied, "can_undo": can_undo, "charged": 0, "credits": self.A._credits_block(uid, 0, 0)}

    def _drop(self, uid, tid, pid) -> None:
        with self._lock:
            self._held.pop((uid, tid, pid), None)

    def _snapshot(self, st, uid: str, tid: str, state: dict, key: str, added: int) -> dict:
        page = st.get_page(uid, key) if key else ""
        return {"v": 1, "key": key, "added": added, "doc": state["doc"], "nodes": state["nodes"], "conns": state["conns"], "page": page}

    def _write(self, st, uid: str, tid: str, state: dict, held: _Held) -> None:
        from alto import mcp_server as srv
        from ..build.engine_stamp import StaleEngineError, check_no_downgrade
        from ..cloud.meta import meta_of, title_of
        need = [m for m in ("save_prior", "put_nodes_exact", "restore_page") if not hasattr(st, m)]
        if need:
            raise _NothingWritten("edit_unavailable", "Bass cannot change timelines here.")
        doc = state["doc"]
        key = doc.get("private_key") or ""                              # a page exists only for a timeline that is on the homepage; none is made here
        added = 0
        if key:
            with STORE_LOCK:
                tok = srv.current_uid.set(uid)
                try:
                    if srv._store is not st:
                        srv.set_store(st)
                    added = srv._added_epoch(doc)
                finally:
                    srv.current_uid.reset(tok)
            try:
                check_no_downgrade(st.get_page(uid, key), held.page)
            except StaleEngineError:
                raise _NothingWritten("edit_stale_engine", "This timeline's page was built by a newer Alto than Bass's, so Bass did not change it.") from None
        prior = self._snapshot(st, uid, tid, state, key, added)
        try:
            st.save_prior(uid, tid, prior)                              # FIRST, and read back: no prior version saved = no write at all
            if not st.has_prior(uid, tid):
                raise RuntimeError("prior")
        except Exception as e:                                          # noqa: BLE001
            log.warning("bass edit: prior not saved %s", type(e).__name__)
            raise _NothingWritten("edit_not_saved", "Bass could not save a copy of your timeline first, so it changed nothing.") from None
        new_doc = {**copy.deepcopy(doc), "brief": copy.deepcopy(held.brief)}      # the same URL, privacy, owner and shares: only the content changes
        nodes = [dict(n, _seq=i + 1) for i, n in enumerate(held.nodes)]
        try:
            self._put_state(st, uid, tid, new_doc, nodes, copy.deepcopy(held.conns))
            if key:
                st.restore_page(uid, key, held.page, title_of(held.page), {**meta_of(held.page), "added": added})
        except Exception as e:                                          # noqa: BLE001 - put the prior version back, best effort; it stays saved either way
            log.warning("bass edit: write failed %s", type(e).__name__)
            try:
                self._restore(st, uid, tid, prior)
            except Exception as e2:                                     # noqa: BLE001
                log.warning("bass edit: put-back failed %s", type(e2).__name__)
            raise

    @staticmethod
    def _put_state(st, uid, tid, doc, nodes, conns) -> None:
        keep = {n["id"] for n in nodes}
        gone = [n["id"] for n in st.list_nodes(uid, tid) if n["id"] not in keep]
        if gone:
            st.delete_nodes(uid, tid, gone)
        st.put_nodes_exact(uid, tid, nodes)
        st.put_connections(uid, tid, conns)
        st.put_timeline(uid, tid, doc)

    def _restore(self, st, uid: str, tid: str, prior: dict) -> None:
        from ..cloud.meta import meta_of, title_of
        self._put_state(st, uid, tid, prior["doc"], prior["nodes"], prior["conns"])
        if prior.get("key") and prior.get("page"):
            st.restore_page(uid, prior["key"], prior["page"], title_of(prior["page"]), {**meta_of(prior["page"]), "added": prior.get("added", 0)})

    # -- edit_undo (charges 0) ------------------------------------------------------------------------------------
    def undo(self, uid: str, timeline_id: str) -> dict:
        if not valid_tid(timeline_id):
            return self._gone()
        with self._tlock(uid, timeline_id):
            st, state = self._owned(uid, timeline_id)
            if state is None:
                return self._gone()
            if not self.live():
                return self._applied(uid, applied=False, can_undo=False)
            try:
                prior = st.load_prior(uid, timeline_id)
            except Exception as e:                                      # noqa: BLE001
                log.warning("bass edit: prior read failed %s", type(e).__name__)
                prior = None
            if not isinstance(prior, dict) or prior.get("doc", {}).get("timeline_id") != timeline_id:
                return _fail("edit_nothing_to_undo", "There is nothing to undo for this timeline.", status="refused")
            try:
                self._restore(st, uid, timeline_id, prior)
                st.drop_prior(uid, timeline_id)
            except Exception as e:                                      # noqa: BLE001
                log.warning("bass edit: undo failed %s", type(e).__name__)
                return _fail("edit_undo_failed", "Bass could not put the earlier version back. Your saved copy is still there; try again.")
            out = self._applied(uid, applied=True, can_undo=False)
            out["message"] = "Your timeline is back the way it was."
            out["undone"] = True
            return out


class _NothingWritten(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(code)
        self.code, self.message = code, message


def attach(proxy, *, clock=time.time, **kw) -> EditBass:
    """Give a built Proxy its edit actions (the hosted function does this once; a build without it answers every edit_* action 'paused')."""
    eb = EditBass(proxy.service.actions, tools=lambda: proxy.real_tools, live=proxy.live_go, clock=clock, **kw)
    proxy.service.actions.editbass = eb
    return eb
