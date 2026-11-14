"""Bass Documents: the per-account library Bass reads from (Luke's picks, 2026-10-30: design A; class files reach every outline in the
class, with a per-outline off switch; a deleted document can be recovered for 7 days).

Shape (one index doc per account plus one text doc per file, all SERVER-ONLY: Firestore rules match only users/ and shares/, so a page
can never read or write these; only the proxy can, and only under the uid of the verified token):
    bass_docs/<uid>               {scopes: {sid: {kind, name, class_id?, class_docs}}, files: {fid: {scope, name, type, bytes, chars,
                                   use, added, deleted?}}}
    bass_doc_text/<uid>_<fid>     {uid, text}
The original file (for the owner to open again) sits in Firebase Storage at users/<uid>/bass/<fid> under owner-only rules (storage.rules);
the rules let a page write it only when this index already lists <fid> for that uid and not deleted (the count and size caps live here).

Siloing (the closed-system rule, ORG notes/closed-system.md): Bass uses ONLY the documents of the scope the request names, resolved here
from the VERIFIED uid; anything a page sends as "library" is dropped. A class or group uses its own files; an outline or timeline uses its
own files plus its class's files, unless that outline's class_docs switch is off. Only files with use=True and not deleted count, and the
whole set is at most MAX_ACTION_CHARS (refused, never cut).

Nothing here makes a model call or logs content, names or sizes.
"""
from __future__ import annotations

import base64
import binascii
import datetime as dt
import re
import secrets

from .beta_store import MAX_DOC_BYTES, StoreError
from .extract import Extractor, UploadRefused

MAX_ACTION_CHARS = 60_000             # Bass reads at most this much document text per action (Luke's brief)
MAX_TEXT_BYTES = MAX_DOC_BYTES - 4_096  # one file's text in UTF-8, under Firestore's 1 MiB document limit with room for the other fields.
                                       # 60,000 characters are at most 240,000 bytes even in 4-byte scripts, so MAX_ACTION_CHARS refuses first;
                                       # this is the explicit second line, so no file can ever reach the store's own size refusal
MAX_FILES = 20                         # per account, deleted-but-recoverable files included (they still hold storage)
MAX_BYTES = 50_000_000                 # per account, originals in Storage
MAX_SCOPES = 60
MAX_NAME = 120
RECOVERY_DAYS = 7
TEXT_TYPES = (".txt", ".md", ".markdown", ".text", ".csv")
IMAGES_IN_BETA = False                 # D4 (security review): no picture reader in the beta, so pictures are refused like any unsupported
                                       # type and never listed (so storage.rules never let their bytes in). A reader comes with real content checks
IMAGE_TYPES = {".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".heic": None, ".webp": b"RIFF"}
SCOPE_KINDS = ("class", "group", "outline", "timeline")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

MESSAGES = {
    "docs_not_found": "That document or folder is not in your library.",
    "docs_full": f"Your library is full ({MAX_FILES} files). Delete one first; deleted files count until they are gone for good after {RECOVERY_DAYS} days.",
    "docs_too_big": "That file would take your library over its size limit. Delete something first.",
    "docs_too_long": f"That file has more text than Bass can read at once ({MAX_ACTION_CHARS:,} characters). Split it, or upload just the part you need.",
    "docs_over_limit": f"Bass can read up to {MAX_ACTION_CHARS:,} characters of documents at a time. Switch off a document under Using, then try again.",
    "docs_bad_name": "Please give it a name (up to 120 characters).",
    "docs_bad_request": "Bass could not read that request.",
    "docs_scopes_full": "You have too many classes and groups. Remove one first.",
    "docs_picture": "Bass can keep pictures in your library but cannot read them yet, so it will not use this one.",
    "docs_not_saved": "Bass could not save that document, so nothing was added. Please try again, or upload a shorter part of it.",
}


class DocsError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def index_key(uid: str) -> str:
    _uid(uid)
    return f"bass_docs/{uid}"


def text_key(uid: str, fid: str) -> str:
    _uid(uid)
    if not _ID.match(fid or ""):
        raise DocsError("docs_not_found")
    return f"bass_doc_text/{uid}_{fid}"


def storage_path(uid: str, fid: str) -> str:
    return f"users/{uid}/bass/{fid}"


def _uid(uid) -> None:
    # a uid is part of every key: never empty, never a path
    if not isinstance(uid, str) or not re.match(r"^[A-Za-z0-9_-]{1,128}$", uid):
        raise DocsError("docs_bad_request")


def _name(v) -> str:
    if not isinstance(v, str) or not v.strip() or len(v.strip()) > MAX_NAME:
        raise DocsError("docs_bad_name")
    return " ".join(v.split())


def _empty() -> dict:
    return {"scopes": {}, "files": {}}


class Library:
    """All library operations for ONE verified uid. `store` is the beta store interface (get / put / run_transaction)."""

    def __init__(self, store, cfg, clock, extractor: Extractor | None = None, blobs=None, ids=None):
        self.store, self.cfg, self.clock = store, cfg, clock
        self.extractor = extractor or Extractor(cfg)
        self.blobs = blobs                                               # Storage adapter: delete(path); None in tests = nothing to delete
        self.ids = ids or (lambda: secrets.token_urlsafe(12).replace("-", "a").replace("_", "b"))

    # -- reading -------------------------------------------------------------------------------------------------
    def _load(self, uid: str) -> dict:
        doc = self.store.get(index_key(uid))
        return doc if isinstance(doc, dict) and isinstance(doc.get("files"), dict) else _empty()

    def _now(self) -> dt.datetime:
        return self.clock()

    def _expired(self, f: dict) -> bool:
        d = f.get("deleted")
        if not d:
            return False
        return self._now() - dt.datetime.fromisoformat(d) >= dt.timedelta(days=RECOVERY_DAYS)

    def _purge(self, uid: str) -> None:
        """Files deleted RECOVERY_DAYS ago or more are gone for good: index entry, text and the original."""
        lib = self._load(uid)
        gone = [fid for fid, f in lib["files"].items() if self._expired(f)]
        if not gone:
            return

        self._erase(uid, gone)

    def _erase(self, uid: str, fids: list, whole: bool = False) -> int:
        """Erase for good: the index entries and texts in ONE transaction (whole=True: the index doc too), then the originals. -> how many."""
        def work(txn):
            cur = txn.get(index_key(uid)) or _empty()
            for fid in fids:
                cur["files"].pop(fid, None)
                txn.delete(text_key(uid, fid))
            if whole:
                txn.delete(index_key(uid))
            else:
                txn.put(index_key(uid), cur)
        self.store.run_transaction(work)
        for fid in fids:
            if self.blobs is not None:
                try:
                    self.blobs.delete(storage_path(uid, fid))
                except Exception:
                    pass                                                 # once unlisted, the Storage rules refuse the page anyway
        return len(fids)

    def erase_account(self, uid: str) -> int:
        """The account is being deleted: every document goes NOW, the ones in their 7-day recovery and the live ones, with the index.
        IT calls it from the account-deletion path (Firebase Auth user deleted). -> how many files were erased."""
        lib = self._load(uid)
        return self._erase(uid, list(lib["files"]), whole=True)

    def listing(self, uid: str) -> dict:
        self._purge(uid)
        lib = self._load(uid)
        now = self._now()
        files, deleted = [], []
        for fid, f in sorted(lib["files"].items(), key=lambda kv: kv[1].get("added", "")):
            row = {"id": fid, **{k: f.get(k) for k in ("scope", "name", "type", "bytes", "chars", "use", "added")},
                   "readable": f.get("type") != "image", "path": storage_path(uid, fid)}
            if f.get("deleted"):
                left = dt.timedelta(days=RECOVERY_DAYS) - (now - dt.datetime.fromisoformat(f["deleted"]))
                row["days_left"] = max(1, -(-int(left.total_seconds()) // 86400))
                deleted.append(row)
            else:
                files.append(row)
        live = [f for f in lib["files"].values()]
        return {"ok": True, "status": "ok", "scopes": [{"id": k, **v} for k, v in lib["scopes"].items()],
                "files": files, "deleted": deleted,
                "caps": {"files": len(live), "files_max": MAX_FILES, "bytes": sum(int(f.get("bytes") or 0) for f in live),
                         "bytes_max": MAX_BYTES, "action_chars_max": MAX_ACTION_CHARS}}

    # -- writing (every write is one transaction on the index) ----------------------------------------------------
    def _edit(self, uid: str, fn):
        out = {}

        def work(txn):
            lib = txn.get(index_key(uid)) or _empty()
            lib.setdefault("scopes", {})
            lib.setdefault("files", {})
            out["r"] = fn(lib, txn)
            txn.put(index_key(uid), lib)
        self.store.run_transaction(work)
        return out.get("r")

    @staticmethod
    def _scope(lib: dict, sid) -> dict:
        s = lib["scopes"].get(sid) if isinstance(sid, str) else None
        if s is None:
            raise DocsError("docs_not_found")
        return s

    @staticmethod
    def _file(lib: dict, fid, live=True) -> dict:
        f = lib["files"].get(fid) if isinstance(fid, str) else None
        if f is None or (live and f.get("deleted")) or (not live and not f.get("deleted")):
            raise DocsError("docs_not_found")
        return f

    def add_scope(self, uid: str, kind, name, class_id=None, ref=None) -> dict:
        """ref: the timeline id an outline or timeline scope belongs to, so its Bass panel finds it (a label, never a key)."""
        if kind not in SCOPE_KINDS or (ref is not None and (kind not in ("outline", "timeline") or not isinstance(ref, str)
                                                            or not re.match(r"^[A-Za-z0-9._-]{1,80}$", ref))):
            raise DocsError("docs_bad_request")
        nm = _name(name)
        sid = self.ids()

        def fn(lib, txn):
            if len(lib["scopes"]) >= MAX_SCOPES:
                raise DocsError("docs_scopes_full")
            s = {"kind": kind, "name": nm}
            if kind in ("outline", "timeline"):
                if class_id is not None:
                    if self._scope(lib, class_id)["kind"] != "class":
                        raise DocsError("docs_bad_request")
                    s["class_id"] = class_id
                s["class_docs"] = True                                   # Luke: class files reach every outline, switch per outline
                if ref is not None:
                    s["ref"] = ref
            lib["scopes"][sid] = s
            return {"id": sid, **s}
        return {"ok": True, "status": "ok", "scope": self._edit(uid, fn)}

    def rename_scope(self, uid: str, scope_id, name) -> dict:
        nm = _name(name)
        self._edit(uid, lambda lib, txn: self._scope(lib, scope_id).__setitem__("name", nm))
        return {"ok": True, "status": "ok"}

    def set_class_docs(self, uid: str, scope_id, on) -> dict:
        if not isinstance(on, bool):
            raise DocsError("docs_bad_request")

        def fn(lib, txn):
            s = self._scope(lib, scope_id)
            if s["kind"] not in ("outline", "timeline"):
                raise DocsError("docs_bad_request")
            s["class_docs"] = on
        self._edit(uid, fn)
        return {"ok": True, "status": "ok"}

    def remove_scope(self, uid: str, scope_id) -> dict:
        """Only an empty scope (no live or recoverable files, no outlines under it) can go: nothing is ever deleted by surprise."""
        def fn(lib, txn):
            self._scope(lib, scope_id)
            if any(f.get("scope") == scope_id for f in lib["files"].values()) or \
                    any(s.get("class_id") == scope_id for s in lib["scopes"].values()):
                raise DocsError("docs_bad_request")
            del lib["scopes"][scope_id]
        self._edit(uid, fn)
        return {"ok": True, "status": "ok"}

    def add_file(self, uid: str, scope_id, name, file_b64=None, text=None) -> dict:
        """One file into one scope. PDF / .docx go through the proxy's extractor (caps before parsing, child process, deadline, fail
        closed); text files arrive as text; pictures are kept but not read. Everything is checked BEFORE the index is touched."""
        nm = _name(name)
        ext = ("." + nm.rsplit(".", 1)[1].lower()) if "." in nm else ""
        if ext in (".pdf", ".docx"):
            if not isinstance(file_b64, str):
                raise DocsError("docs_bad_request")
            mat = [{"name": nm, "kind": "notes", "text": "", "file_b64": file_b64}]
            self.extractor.prepare(mat)                                  # raises UploadRefused(upload_*)
            body, typ = mat[0]["text"], ext[1:]
            size = (len(file_b64) * 3) // 4
        elif ext in TEXT_TYPES or (ext == "" and isinstance(text, str)):
            if not isinstance(text, str) or not text.strip():
                raise UploadRefused("upload_no_text")
            body, typ, size = text, "text", len(text.encode("utf-8"))
        elif ext in IMAGE_TYPES and IMAGES_IN_BETA:
            if not isinstance(file_b64, str) or len(file_b64) > (self.cfg.upload_max_file_bytes * 4) // 3 + 8:
                raise UploadRefused("upload_too_big")
            try:
                raw = base64.b64decode(file_b64, validate=True)
            except (binascii.Error, ValueError):
                raise UploadRefused("upload_unreadable")
            magic = IMAGE_TYPES[ext]
            if magic is not None and not raw.startswith(magic):
                raise UploadRefused("upload_unreadable")
            body, typ, size = "", "image", len(raw)
        else:
            raise UploadRefused("upload_unsupported")
        if size > self.cfg.upload_max_file_bytes:
            raise UploadRefused("upload_too_big")
        if len(body) > MAX_ACTION_CHARS or len(body.encode("utf-8")) > MAX_TEXT_BYTES:
            raise DocsError("docs_too_long")
        fid = self.ids()
        self._purge(uid)

        def fn(lib, txn):
            self._scope(lib, scope_id)
            if len(lib["files"]) >= MAX_FILES:
                raise DocsError("docs_full")
            if sum(int(f.get("bytes") or 0) for f in lib["files"].values()) + size > MAX_BYTES:
                raise DocsError("docs_too_big")
            f = {"scope": scope_id, "name": nm, "type": typ, "bytes": size, "chars": len(body),
                 "use": typ != "image", "added": self._now().isoformat()}
            lib["files"][fid] = f
            txn.put(text_key(uid, fid), {"uid": uid, "text": body})
            return {"id": fid, **f, "readable": typ != "image", "path": storage_path(uid, fid)}
        try:
            saved = self._edit(uid, fn)
        except StoreError:                                               # the store refused (size, outage): nothing was written, and the
            raise DocsError("docs_not_saved")                            # page says so instead of showing a file that is not there
        out = {"ok": True, "status": "ok", "file": saved}
        if typ == "image":
            out["note"] = MESSAGES["docs_picture"]
        return out

    def rename_file(self, uid: str, doc_id, name) -> dict:
        nm = _name(name)
        self._edit(uid, lambda lib, txn: self._file(lib, doc_id).__setitem__("name", nm))
        return {"ok": True, "status": "ok"}

    def move_file(self, uid: str, doc_id, scope_id) -> dict:
        def fn(lib, txn):
            self._scope(lib, scope_id)
            self._file(lib, doc_id)["scope"] = scope_id
        self._edit(uid, fn)
        return {"ok": True, "status": "ok"}

    def set_use(self, uid: str, doc_id, on) -> dict:
        if not isinstance(on, bool):
            raise DocsError("docs_bad_request")

        def fn(lib, txn):
            f = self._file(lib, doc_id)
            if on and f.get("type") == "image":
                raise DocsError("docs_picture")
            f["use"] = on
        self._edit(uid, fn)
        return {"ok": True, "status": "ok"}

    def delete_file(self, uid: str, doc_id) -> dict:
        def fn(lib, txn):
            self._file(lib, doc_id)["deleted"] = self._now().isoformat()
        self._edit(uid, fn)
        return {"ok": True, "status": "ok", "recover_days": RECOVERY_DAYS}

    def restore_file(self, uid: str, doc_id) -> dict:
        self._purge(uid)

        def fn(lib, txn):
            f = self._file(lib, doc_id, live=False)
            f.pop("deleted", None)
            if f.get("scope") not in lib["scopes"]:                      # its folder went meanwhile: refuse rather than guess one
                raise DocsError("docs_not_found")
        self._edit(uid, fn)
        return {"ok": True, "status": "ok"}

    # -- what Bass reads -------------------------------------------------------------------------------------------
    def active(self, uid: str, scope_id) -> tuple[dict, list]:
        """-> (scope, [file rows]) Bass uses for scope_id, in reading order (the scope's own files, then its class's)."""
        lib = self._load(uid)
        s = self._scope(lib, scope_id)
        homes = [scope_id]
        if s["kind"] in ("outline", "timeline") and s.get("class_docs", True) and s.get("class_id") in lib["scopes"]:
            homes.append(s["class_id"])
        rows = []
        for home in homes:
            for fid, f in sorted(lib["files"].items(), key=lambda kv: kv[1].get("added", "")):
                if f.get("scope") == home and f.get("use") and not f.get("deleted") and f.get("type") != "image" \
                        and not self._expired(f):
                    rows.append({"id": fid, "name": f["name"], "chars": int(f.get("chars") or 0), "from": home})
        return {"id": scope_id, **s}, rows

    def using(self, uid: str, scope_id) -> dict:
        s, rows = self.active(uid, scope_id)
        n, total = len(rows), sum(r["chars"] for r in rows)
        return {"ok": True, "status": "ok", "scope": s, "files": rows, "chars": total, "chars_max": MAX_ACTION_CHARS,
                "over": total > MAX_ACTION_CHARS,
                "label": f"Using: {s['name']}, {n} document" + ("" if n == 1 else "s")}

    def materials(self, uid: str, scope_id) -> list:
        """The documents as materials for an action. Raises DocsError(docs_over_limit) when they are over the per-action limit."""
        s, rows = self.active(uid, scope_id)
        if sum(r["chars"] for r in rows) > MAX_ACTION_CHARS:
            raise DocsError("docs_over_limit")
        out = []
        for r in rows:
            doc = self.store.get(text_key(uid, r["id"]))
            if not isinstance(doc, dict) or doc.get("uid") != uid or not isinstance(doc.get("text"), str):
                raise StoreError("document text unreadable")             # fail closed: never build from a partial set
            out.append({"name": r["name"], "kind": "document", "text": doc["text"]})
        if sum(len(m["text"]) for m in out) > MAX_ACTION_CHARS:
            raise DocsError("docs_over_limit")
        return out

    # -- the one door for the proxy ------------------------------------------------------------------------------
    OPS = {"list": ("listing", ()), "add_scope": ("add_scope", ("kind", "name", "class_id", "ref")),
           "rename_scope": ("rename_scope", ("scope_id", "name")), "class_docs": ("set_class_docs", ("scope_id", "on")),
           "remove_scope": ("remove_scope", ("scope_id",)), "add": ("add_file", ("scope_id", "name", "file_b64", "text")),
           "rename": ("rename_file", ("doc_id", "name")), "move": ("move_file", ("doc_id", "scope_id")),
           "use": ("set_use", ("doc_id", "on")), "delete": ("delete_file", ("doc_id",)),
           "restore": ("restore_file", ("doc_id",)), "using": ("using", ("scope_id",))}

    def handle(self, uid: str, args) -> dict:
        if not isinstance(args, dict) or args.get("op") not in self.OPS:
            return refusal("docs_bad_request")
        meth, names = self.OPS[args["op"]]
        extra = set(args) - set(names) - {"op"}
        if extra:
            return refusal("docs_bad_request")
        try:
            return getattr(self, meth)(uid, **{k: args.get(k) for k in names if k in args})
        except TypeError:
            return refusal("docs_bad_request")
        except DocsError as e:
            return refusal(e.code)


def purge_expired(store, cfg, clock, blobs=None) -> dict:
    """The DAILY job (IT schedules it; nothing here runs by itself): every account's documents deleted RECOVERY_DAYS ago or more are erased
    for good, index entry, text and original. Accounts nobody opens are covered too (the library also purges on each open). One account's
    failure never stops the others. -> counts only, never names or uids."""
    lib, out = Library(store, cfg, clock, blobs=blobs), {"accounts": 0, "erased": 0, "failed": 0}
    for key, _doc in store.scan("bass_docs/"):
        uid = key[len("bass_docs/"):]
        out["accounts"] += 1
        try:
            before = len(lib._load(uid)["files"])
            lib._purge(uid)
            out["erased"] += before - len(lib._load(uid)["files"])
        except Exception:
            out["failed"] += 1
    return out


def refusal(code: str) -> dict:
    return {"ok": False, "status": "refused", "code": code, "message": MESSAGES.get(code, MESSAGES["docs_bad_request"]),
            "retryable": False}
