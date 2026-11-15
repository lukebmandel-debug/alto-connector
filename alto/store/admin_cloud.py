"""CloudStore's exact layout and encoding, written with the Firebase ADMIN SDK for ONE pinned account.

The hosted Bass function (deploy/bass-proxy) has no user token to send to Firestore's REST API: it is a server with its own service account. But what
Luke's homepage on luke-alto reads is CloudStore's layout (users/{uid}/alto_projects | alto_timelines | nodes | meta/connections, and pages + pagemeta),
each document `{data: JSON text, created}`. A second store with its own encoding would drift from it. So this one IS a CloudStore: every
method, every field name and every encode/decode is CloudStore's own code. Only its one transport, `_req`, is replaced: it answers the same
REST-shaped calls (get a document, list a collection, patch, commit of updates/deletes/transforms) from the admin Firestore client.

One uid. Every document path the store touches must be users/{pinned uid} or below it; anything else raises before Firestore is called.
Built artifacts stay in memory-sized LocalStore files under a per-request temp dir (CloudStore already keeps them off Firestore); no bucket.
Nothing here imports the SDK: the client and the two sentinels are handed in.
"""
from __future__ import annotations

import base64
import datetime as _dt
import urllib.parse

from ..cloud.session import CloudError
from .cloud import CloudStore
from .local import LocalStore, check_component


class _Project:
    """The only part of a Session that CloudStore's constructor reads."""

    def __init__(self, project: str):
        self.project = project

    def id_token(self, force: bool = False):                       # pragma: no cover - never reached: `_req` is replaced
        raise CloudError("the hosted store has no user token")


def to_native(v):
    """A Firestore REST typed value -> the Python value the admin client stores."""
    if "stringValue" in v:
        return v["stringValue"]
    if "integerValue" in v:
        return int(v["integerValue"])
    if "doubleValue" in v:
        return float(v["doubleValue"])
    if "booleanValue" in v:
        return bool(v["booleanValue"])
    if "bytesValue" in v:
        return base64.b64decode(v["bytesValue"])
    if "arrayValue" in v:
        return [to_native(x) for x in v["arrayValue"].get("values", [])]
    if "mapValue" in v:
        return {k: to_native(x) for k, x in v["mapValue"].get("fields", {}).items()}
    if "nullValue" in v:
        return None
    if "timestampValue" in v:
        return _dt.datetime.fromisoformat(v["timestampValue"].replace("Z", "+00:00"))
    raise CloudError(f"unsupported Firestore value: {sorted(v)}")


def to_typed(v) -> dict:
    """The admin client's Python value -> the REST typed value CloudStore decodes."""
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, str):
        return {"stringValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, (bytes, bytearray)):
        return {"bytesValue": base64.b64encode(bytes(v)).decode("ascii")}
    if isinstance(v, (list, tuple)):
        return {"arrayValue": {"values": [to_typed(x) for x in v]}}
    if isinstance(v, dict):
        return {"mapValue": {"fields": {k: to_typed(x) for k, x in v.items()}}}
    if isinstance(v, _dt.datetime):
        return {"timestampValue": v.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if v is None:
        return {"nullValue": None}
    raise CloudError(f"unsupported stored value: {type(v).__name__}")


class AdminCloudStore(CloudStore):
    def __init__(self, db, uid: str, local: LocalStore, project: str, *, delete_field, server_timestamp):
        super().__init__(_Project(project), local)
        self.db, self.pinned = db, check_component(uid, "uid")
        self._delete_field, self._server_ts = delete_field, server_timestamp

    # -- the one door: nothing outside users/{pinned uid} is ever read or written -----------------------------
    def _rel(self, name: str) -> str:
        pre = self.root + "/"
        if not name.startswith(pre):
            raise CloudError("hosted store: a path outside this project's documents")
        rel = name[len(pre):]
        for seg in rel.split("/"):                                 # every segment is an id: non-empty, no "/", never "." or "..", the store's own id rule
            try:
                check_component(seg)
            except ValueError:
                raise CloudError("hosted store: a path segment that is not an id") from None
        mine = "users/" + self.pinned
        if rel != mine and not rel.startswith(mine + "/"):
            raise CloudError("hosted store: a path outside the pinned account")
        return rel

    def _ref(self, name: str):
        return self.db.document(self._rel(name))

    @staticmethod
    def _typed_fields(data: dict | None, mask=None) -> dict:
        return {k: to_typed(v) for k, v in (data or {}).items() if mask is None or k in mask}

    def _req(self, method: str, path: str, body=None, params: str = "", ok404: bool = False):
        q = urllib.parse.parse_qs(params.lstrip("?"), keep_blank_values=True)
        if path == self.root + ":commit":
            if method != "POST":
                raise CloudError("hosted store: bad commit")
            self._commit_writes((body or {}).get("writes") or [])
            return {}
        rel = self._rel(path)
        mask = set(q.get("mask.fieldPaths") or []) or None
        if rel.count("/") % 2 == 0:                                # users/{uid}/coll...: a collection
            if method != "GET":
                raise CloudError("hosted store: only a document is written")
            return self._list_docs(path, rel, q, mask)
        if method == "GET":
            snap = self.db.document(rel).get()
            if not snap.exists:
                if ok404:
                    return None
                raise CloudError("Firestore GET failed (404): not found")
            return {"name": path, "fields": self._typed_fields(snap.to_dict(), mask)}
        if method == "PATCH":                                      # no update mask: replaces the whole document
            self.db.document(rel).set({k: to_native(v) for k, v in (body or {}).get("fields", {}).items()})
            return {}
        raise CloudError(f"hosted store: {method} is not used")

    def _list_docs(self, path, rel, q, mask):
        size = int((q.get("pageSize") or ["300"])[0])
        start = int((q.get("pageToken") or ["0"])[0] or 0)
        docs = sorted(self.db.collection(rel).stream(), key=lambda d: d.id)
        page = docs[start:start + size]
        out = {"documents": [{"name": f"{path}/{d.id}", "fields": self._typed_fields(d.to_dict(), mask)} for d in page]}
        if start + size < len(docs):
            out["nextPageToken"] = str(start + size)
        return out if page else {}

    def _commit_writes(self, writes: list) -> None:
        batch = self.db.batch()
        for w in writes:
            if "delete" in w:
                batch.delete(self._ref(w["delete"]))
                continue
            u = w["update"]
            ref = self._ref(u["name"])
            fields = {k: to_native(v) for k, v in (u.get("fields") or {}).items()}
            if "updateMask" in w:                                  # merge those paths; one in the mask but not the fields is deleted
                data = {p: fields.get(p, self._delete_field) for p in w["updateMask"].get("fieldPaths", [])}
                for t in w.get("updateTransforms", []):
                    if t.get("setToServerValue") != "REQUEST_TIME":
                        raise CloudError("hosted store: unsupported field transform")
                    data[t["fieldPath"]] = self._server_ts
                batch.set(ref, data, merge=True)
            elif (w.get("currentDocument") or {}).get("exists") is False:
                batch.create(ref, fields)
            else:
                batch.set(ref, fields)
        batch.commit()
