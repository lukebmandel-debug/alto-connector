"""Projects and timelines in the user's own Firestore, reached as the user.

The same account the homepage lists from, so what the homepage shows is what
Claude can open — from any computer where the connector is signed in. No admin
credentials: every request carries the user's Firebase ID token and passes the
security rules like the browser does (users/{uid}/** belongs to uid).

Layout, beside the collections the browser already owns (tl, pages, pagemeta,
shared — untouched here):

  users/{uid}/alto_projects/{pid}                       {data, created}
  users/{uid}/alto_timelines/{tid}                      {data, created}
  users/{uid}/alto_timelines/{tid}/nodes/{nodeId}       {data, _seq}
  users/{uid}/alto_timelines/{tid}/meta/connections     {data}

`data` is the document as JSON text. Firestore forbids arrays inside arrays —
which is exactly what connections are — and mapping every shape through its
typed-value format is where bugs would live; one string field sidesteps both,
and nothing here ever needs to query inside a document.

Built artifacts and the parked hosted server's share index stay on this
computer (LocalStore): artifacts are rebuilt from nodes on every publish, the
paths are shown to the user, and at ~600 KB apiece they would eat the free
write quota for nothing.

Stdlib only — `urllib` through the session's transport.
"""
from __future__ import annotations

import json
import time
import urllib.parse

from .base import Store
from .local import LocalStore, check_component
from ..cloud.session import CloudError, Session

API = "https://firestore.googleapis.com/v1"


def _sv(s: str) -> dict:
    return {"stringValue": s}


class CloudStore(Store):
    def __init__(self, session: Session, local: LocalStore):
        self.s = session
        self.local = local
        self.root = (f"projects/{session.project}/databases/(default)/documents")
        # Nodes read within one tool call are reused by the write that follows
        # (add_nodes lists, then put_nodes lists again). Short-lived, so a
        # write from another computer is never hidden for long.
        self._nodes_cache: dict = {}

    # ── transport ────────────────────────────────────────────────────────────
    def _req(self, method: str, path: str, body=None, params: str = "",
             ok404: bool = False):
        url = f"{API}/{path}{params}"
        data = json.dumps(body).encode() if body is not None else None
        for attempt in (0, 1):
            tok = self.s.id_token(force=bool(attempt))
            status, js = self.s.http(method, url, data, {
                "Authorization": f"Bearer {tok}",
                "Content-Type": "application/json"})
            if status == 401 and attempt == 0:
                continue
            break
        if status == 404 and ok404:
            return None
        if status >= 300:
            err = (js or {}).get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            if status == 429 or (isinstance(err, dict) and err.get("status") == "RESOURCE_EXHAUSTED"):
                raise CloudError(
                    "Alto has reached today's free Firestore limit. It resets "
                    "at midnight Pacific time; nothing is charged.")
            raise CloudError(f"Firestore {method} failed ({status}): {msg or 'no detail'}")
        return js

    def _doc(self, uid: str, *parts: str) -> str:
        return "/".join([self.root, "users", check_component(uid, "uid"),
                         *(check_component(p) for p in parts)])

    @staticmethod
    def _decode(d: dict):
        f = (d or {}).get("fields") or {}
        raw = (f.get("data") or {}).get("stringValue")
        return json.loads(raw) if raw else None

    def _get(self, path: str):
        js = self._req("GET", path, ok404=True)
        return self._decode(js) if js else None

    def _list(self, path: str) -> list[dict]:
        out, token = [], ""
        while True:
            params = "?pageSize=300" + (f"&pageToken={urllib.parse.quote(token)}" if token else "")
            js = self._req("GET", path, params=params, ok404=True) or {}
            for d in js.get("documents") or []:
                v = self._decode(d)
                if v is not None:
                    out.append(v)
            token = js.get("nextPageToken") or ""
            if not token:
                return out

    def _fields(self, doc, extra: dict | None = None) -> dict:
        f = {"data": _sv(json.dumps(doc, ensure_ascii=False))}
        for k, v in (extra or {}).items():
            f[k] = {"integerValue": str(v)} if isinstance(v, int) else _sv(str(v))
        return f

    def _put(self, path: str, doc, extra: dict | None = None) -> None:
        # PATCH without an update mask replaces the whole document.
        self._req("PATCH", path, {"fields": self._fields(doc, extra)})

    def _commit(self, writes: list[dict]) -> None:
        for i in range(0, len(writes), 400):     # Firestore caps a commit at 500
            self._req("POST", f"{self.root}:commit", {"writes": writes[i:i + 400]})

    # ── projects ─────────────────────────────────────────────────────────────
    def list_projects(self, uid):
        return sorted(self._list(self._doc(uid, "alto_projects")),
                      key=lambda x: x.get("created", ""))

    def get_project(self, uid, pid):
        return self._get(self._doc(uid, "alto_projects", pid))

    def put_project(self, uid, pid, doc):
        self._put(self._doc(uid, "alto_projects", pid), doc,
                  {"created": doc.get("created", "")})

    # ── timelines ────────────────────────────────────────────────────────────
    def list_timelines(self, uid):
        return sorted(self._list(self._doc(uid, "alto_timelines")),
                      key=lambda x: x.get("created", ""))

    def get_timeline(self, uid, tid):
        return self._get(self._doc(uid, "alto_timelines", tid))

    def put_timeline(self, uid, tid, doc):
        self._put(self._doc(uid, "alto_timelines", tid), doc,
                  {"created": doc.get("created", "")})

    # ── nodes / connections ──────────────────────────────────────────────────
    def list_nodes(self, uid, tid):
        key = (uid, tid)
        hit = self._nodes_cache.get(key)
        if hit and time.time() - hit[0] < 5:
            return [dict(n) for n in hit[1]]
        nodes = sorted(self._list(self._doc(uid, "alto_timelines", tid, "nodes")),
                       key=lambda n: n.get("_seq", 0))
        self._nodes_cache[key] = (time.time(), nodes)
        return [dict(n) for n in nodes]

    def put_nodes(self, uid, tid, nodes):
        existing = {n["id"]: n for n in self.list_nodes(uid, tid)}
        seq = max((n.get("_seq", 0) for n in existing.values()), default=0)
        writes = []
        for n in nodes:
            if n["id"] in existing:
                n["_seq"] = existing[n["id"]]["_seq"]     # keep narrative order
            else:
                seq += 1
                n["_seq"] = seq
            writes.append({"update": {
                "name": self._doc(uid, "alto_timelines", tid, "nodes", n["id"]),
                "fields": self._fields(n, {"_seq": n["_seq"]})}})
        self._commit(writes)
        self._nodes_cache.pop((uid, tid), None)

    def delete_nodes(self, uid, tid, node_ids):
        self._commit([{"delete": self._doc(uid, "alto_timelines", tid, "nodes", nid)}
                      for nid in node_ids])
        self._nodes_cache.pop((uid, tid), None)

    def get_connections(self, uid, tid):
        return self._get(self._doc(uid, "alto_timelines", tid, "meta", "connections")) or []

    def put_connections(self, uid, tid, connections):
        self._put(self._doc(uid, "alto_timelines", tid, "meta", "connections"),
                  connections)

    # ── on this computer ─────────────────────────────────────────────────────
    def put_artifact(self, uid, tid, name, content):
        return self.local.put_artifact(uid, tid, name, content)

    def get_artifact(self, uid, tid, name):
        return self.local.get_artifact(uid, tid, name)

    def get_share(self, tid):
        return self.local.get_share(tid)

    def put_share(self, tid, doc):
        self.local.put_share(tid, doc)

    # ── private pages, written the way the browser writes them ───────────────
    def put_page(self, uid: str, key: str, html: str, title: str,
                 meta: dict) -> None:
        """users/{uid}/pages/{key} + pagemeta/{key}, as alto-cloud.js _putPage
        does — so the homepage lists it and the private shell opens it, with no
        upload by hand. Update masks leave shareKey (set by the share flow)
        alone, and both updatedAt come from the server clock, which the
        shell's cache compares."""
        page = {"html": _sv(html), "title": _sv(title or ""), "tid": _sv(meta.get("tid", ""))}
        mfields = {
            "title": _sv(title or meta.get("title", "")),
            "heading": _sv(meta.get("heading", "")),
            "project": _sv(meta.get("project", "")),
            "tid": _sv(meta.get("tid", "")),
            "units": {"arrayValue": {"values": [_sv(u) for u in meta.get("units", [])]}},
            "search": {"arrayValue": {"values": [
                {"mapValue": {"fields": {"id": _sv(n["id"]), "t": _sv(n["t"]), "d": _sv(n["d"])}}}
                for n in meta.get("search", [])]}},
            "v": {"integerValue": str(meta.get("v", 1))},
        }
        now = [{"fieldPath": "updatedAt", "setToServerValue": "REQUEST_TIME"}]
        self._req("POST", f"{self.root}:commit", {"writes": [
            {"update": {"name": self._doc(uid, "pages", key), "fields": page},
             "updateMask": {"fieldPaths": list(page)}, "updateTransforms": now},
            {"update": {"name": self._doc(uid, "pagemeta", key), "fields": mfields},
             "updateMask": {"fieldPaths": list(mfields)}, "updateTransforms": now},
            {"update": {"name": f"{self.root}/users/{check_component(uid, 'uid')}",
                        "fields": {"pagemetaV": {"integerValue": "1"}}},
             "updateMask": {"fieldPaths": ["pagemetaV"]}},
        ]})
