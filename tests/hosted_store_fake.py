"""An in-memory stand-in for the Firebase ADMIN Firestore client, backed by cloudfake.FakeFirebase's own document table, so a CloudStore
(REST, as the user) and an AdminCloudStore (admin SDK, as the hosted function) see the SAME documents. Enough surface for alto/store/admin_cloud.py."""
from __future__ import annotations

from alto.store.admin_cloud import to_native, to_typed

DELETE_FIELD, SERVER_TIMESTAMP = object(), object()
ROOT = "projects/{p}/databases/(default)/documents"


class Snap:
    def __init__(self, id_, fields):
        self.id, self.exists, self._f = id_, fields is not None, fields

    def to_dict(self):
        return None if self._f is None else {k: to_native(v) for k, v in self._f.items()}


class Ref:
    def __init__(self, db, rel):
        self.db, self.rel = db, rel
        self.name = db.root + "/" + rel

    def get(self):
        return Snap(self.rel.rsplit("/", 1)[-1], self.db.docs.get(self.name))

    def set(self, data, merge=False):
        self.db.log.append(("set", self.rel))
        cur = dict(self.db.docs.get(self.name, {})) if merge else {}
        for k, v in data.items():
            if v is DELETE_FIELD:
                cur.pop(k, None)
            elif v is SERVER_TIMESTAMP:
                cur[k] = {"timestampValue": "2026-09-24T00:00:00Z"}
            else:
                cur[k] = to_typed(v)
        self.db.docs[self.name] = cur

    def create(self, data):
        assert self.name not in self.db.docs
        self.set(data)

    def delete(self):
        self.db.log.append(("delete", self.rel))
        self.db.docs.pop(self.name, None)


class Coll:
    def __init__(self, db, rel):
        self.db, self.rel = db, rel

    def stream(self):
        pre, depth = self.db.root + "/" + self.rel + "/", self.rel.count("/") + 2
        return [Snap(n.rsplit("/", 1)[-1], f) for n, f in sorted(self.db.docs.items())
                if n.startswith(pre) and n[len(self.db.root) + 1:].count("/") + 1 == depth]


class Batch:
    def __init__(self):
        self.ops = []

    def set(self, ref, data, merge=False):
        self.ops.append(lambda: ref.set(data, merge))

    def create(self, ref, data):
        self.ops.append(lambda: ref.create(data))

    def delete(self, ref):
        self.ops.append(ref.delete)

    def commit(self):
        for op in self.ops:
            op()


class FakeAdminDb:
    DELETE_FIELD, SERVER_TIMESTAMP = DELETE_FIELD, SERVER_TIMESTAMP

    def __init__(self, fake):
        self.docs, self.root, self.log = fake.docs, ROOT.format(p=fake.project), []

    def document(self, rel):
        return Ref(self, rel)

    def collection(self, rel):
        return Coll(self, rel)

    def batch(self):
        return Batch()
