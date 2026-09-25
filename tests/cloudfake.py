"""An in-memory stand-in for Firestore REST + securetoken, for tests."""
from __future__ import annotations

import json
import urllib.parse

from alto.store.cloud import API


class FakeFirebase:
    """Firestore REST + securetoken, in memory. Rejects any request whose token
    is not the current one, and any path outside users/{its uid}."""

    def __init__(self, uid="U1"):
        self.uid, self.docs, self.calls = uid, {}, []
        self.good_rt, self.token_n = "RT", 0

    def _tok(self):
        self.token_n += 1
        return f"ID{self.token_n}"

    def __call__(self, method, url, body=None, headers=None, timeout=30):
        self.calls.append((method, url))
        if url.startswith("https://securetoken.googleapis.com/"):
            rt = urllib.parse.parse_qs(body.decode())["refresh_token"][0]
            if rt != self.good_rt:
                return 400, {"error": {"message": "INVALID_REFRESH_TOKEN"}}
            import base64
            claims = base64.urlsafe_b64encode(json.dumps(
                {"user_id": self.uid, "email": "me@example.com"}).encode()).decode().rstrip("=")
            return 200, {"id_token": f"h.{claims}.s", "refresh_token": rt,
                         "user_id": self.uid, "expires_in": "3600"}
        assert url.startswith(API + "/projects/proj/databases/(default)/documents")
        if (headers or {}).get("Authorization", "").split(".")[0] != "Bearer h":
            return 401, {"error": {"message": "unauthenticated"}}
        path, _, query = url[len(API) + 1:].partition("?")
        root = "projects/proj/databases/(default)/documents"
        if path == root + ":commit":
            for w in json.loads(body)["writes"]:
                if "delete" in w:
                    self._own(w["delete"]); self.docs.pop(w["delete"], None)
                    continue
                name = w["update"]["name"]; self._own(name)
                fields = dict(self.docs.get(name, {})) if "updateMask" in w else {}
                fields.update(w["update"]["fields"])
                for t in w.get("updateTransforms", []):
                    fields[t["fieldPath"]] = {"timestampValue": "2026-09-24T00:00:00Z"}
                self.docs[name] = fields
            return 200, {}
        self._own(path)
        if method == "PATCH":
            self.docs[path] = json.loads(body)["fields"]
            return 200, {}
        if method == "GET":
            if path in self.docs:
                return 200, {"name": path, "fields": self.docs[path]}
            rel = path[len(root) + 1:]
            if rel.count("/") % 2 == 0:          # users/U1/coll → a collection
                depth = path.count("/") + 1
                kids = [{"name": n, "fields": f} for n, f in sorted(self.docs.items())
                        if n.startswith(path + "/") and n.count("/") == depth]
                return 200, ({"documents": kids} if kids else {})
            return 404, {"error": {"message": "not found"}}
        raise AssertionError((method, url))

    def _own(self, name):
        assert (f"/documents/users/{self.uid}" in name + "/"
                or "/documents/shares/" in name), f"outside own uid: {name}"
