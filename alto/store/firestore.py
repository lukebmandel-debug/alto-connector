"""Firestore + Cloud Storage backend (production).

Layout (plan §4):
  users/{uid}/projects/{pid}
  users/{uid}/timelines/{tid}                     — doc.json equivalent
  users/{uid}/timelines/{tid}/nodes/{nodeId}      — one doc per node (_seq order)
  users/{uid}/timelines/{tid}/meta/connections    — {list: [...]}
  shares/{tid}                                    — {uid, visibility}
  gs://{bucket}/builds/{uid}/{tid}/{name}         — built artifacts

users/{uid} and users/{uid}/tl/** (alto-cloud v3 sync) are client-owned and
untouched here. Admin SDK bypasses security rules; client rules never allow
`shares` or `oauth`, so those stay server-only.
"""
from __future__ import annotations

import os

from .base import Store


class FirestoreStore(Store):
    def __init__(self, bucket: str | None = None):
        import firebase_admin
        from firebase_admin import firestore, storage
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        self.db = firestore.client()
        bucket = bucket or os.environ.get("ALTO_BUCKET", "")
        if not bucket:
            raise RuntimeError(
                "ALTO_BUCKET is not set — the Firestore store needs the "
                "deployer's own storage bucket. There is deliberately no "
                "default: one baked in would send every operator's data to "
                "whichever project happened to be hardcoded.")
        self.bucket = storage.bucket(bucket)

    # ── projects ─────────────────────────────────────────────────────────────
    def _projects(self, uid):
        return self.db.collection("users").document(uid).collection("projects")

    def list_projects(self, uid):
        return sorted((d.to_dict() for d in self._projects(uid).stream()),
                      key=lambda x: x.get("created", ""))

    def get_project(self, uid, pid):
        snap = self._projects(uid).document(pid).get()
        return snap.to_dict() if snap.exists else None

    def put_project(self, uid, pid, doc):
        self._projects(uid).document(pid).set(doc)

    # ── timelines ────────────────────────────────────────────────────────────
    def _timelines(self, uid):
        return self.db.collection("users").document(uid).collection("timelines")

    def list_timelines(self, uid):
        return sorted((d.to_dict() for d in self._timelines(uid).stream()),
                      key=lambda x: x.get("created", ""))

    def get_timeline(self, uid, tid):
        snap = self._timelines(uid).document(tid).get()
        return snap.to_dict() if snap.exists else None

    def put_timeline(self, uid, tid, doc):
        self._timelines(uid).document(tid).set(doc)

    # ── nodes / connections ──────────────────────────────────────────────────
    def _nodes(self, uid, tid):
        return self._timelines(uid).document(tid).collection("nodes")

    def list_nodes(self, uid, tid):
        nodes = [d.to_dict() for d in self._nodes(uid, tid).stream()]
        return sorted(nodes, key=lambda n: n.get("_seq", 0))

    def put_nodes(self, uid, tid, nodes):
        existing = {n["id"]: n for n in self.list_nodes(uid, tid)}
        seq = max((n.get("_seq", 0) for n in existing.values()), default=0)
        batch = self.db.batch()
        for n in nodes:
            n = dict(n)
            if n["id"] in existing:
                n["_seq"] = existing[n["id"]]["_seq"]
            else:
                seq += 1
                n["_seq"] = seq
            batch.set(self._nodes(uid, tid).document(n["id"]), n)
        batch.commit()

    def delete_nodes(self, uid, tid, node_ids):
        batch = self.db.batch()
        for nid in node_ids:
            batch.delete(self._nodes(uid, tid).document(nid))
        batch.commit()

    def get_connections(self, uid, tid):
        snap = self._timelines(uid).document(tid) \
            .collection("meta").document("connections").get()
        return (snap.to_dict() or {}).get("list", []) if snap.exists else []

    def put_connections(self, uid, tid, connections):
        self._timelines(uid).document(tid).collection("meta") \
            .document("connections").set({"list": connections})

    # ── artifacts / shares ───────────────────────────────────────────────────
    def _blob(self, uid, tid, name):
        return self.bucket.blob(f"builds/{uid}/{tid}/{name}")

    def put_artifact(self, uid, tid, name, content):
        blob = self._blob(uid, tid, name)
        blob.upload_from_string(content, content_type="text/html")
        return f"gs://{self.bucket.name}/{blob.name}"

    def get_artifact(self, uid, tid, name):
        blob = self._blob(uid, tid, name)
        if not blob.exists():
            return None
        return blob.download_as_text()

    def get_share(self, tid):
        snap = self.db.collection("shares").document(tid).get()
        return snap.to_dict() if snap.exists else None

    def put_share(self, tid, doc):
        self.db.collection("shares").document(tid).set(doc)
