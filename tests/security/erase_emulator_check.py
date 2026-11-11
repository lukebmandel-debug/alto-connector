"""Account erasure against the Firebase Auth, Firestore and Storage EMULATORS (run by .github/workflows/security.yml).

tests/test_account_erase.py proves alto/store/erase.py against an in-memory fake. This runs the real admin path,
tools/erase_account.py (dry run, wrong confirmation, then the real erase), against the three emulators, with a user
who has photos (Storage objects and Firestore picture documents) and the rest of what an account owns, and asserts
that NOTHING of that account is left in Auth, Firestore or Storage while a second account is untouched.

Emulator only: it refuses to run unless all three emulator hosts are set, the project id is a demo- one (which the
emulator never connects to a real project) and the bucket is that demo project's. It never takes a credential, and
it is never pointed at the luke-alto cloud env.

    npx firebase emulators:exec --only firestore,storage,auth --project demo-alto-security "python erase_emulator_check.py"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT = os.environ.get("GCLOUD_PROJECT") or "demo-alto-security"
BUCKET = f"{PROJECT}.appspot.com"
GONE, KEEP = "erase-me-uid", "keep-me-uid"
GONE_EMAIL, KEEP_EMAIL = "erase.me@example.com", "keep.me@example.com"


def guard() -> None:
    if not PROJECT.startswith("demo-"):
        raise SystemExit(f"refusing to run: project {PROJECT!r} is not a demo- emulator project")
    if "luke-alto" in " ".join(os.environ.values()):
        raise SystemExit("refusing to run: the luke-alto cloud env is in the environment")
    for var in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST"):
        if not os.environ.get(var):
            raise SystemExit(f"refusing to run: {var} is not set (run it under `firebase emulators:exec`)")
    storage_host = os.environ.get("STORAGE_EMULATOR_HOST") or os.environ.get("FIREBASE_STORAGE_EMULATOR_HOST")
    if not storage_host:
        raise SystemExit("refusing to run: no Storage emulator host is set")
    os.environ["STORAGE_EMULATOR_HOST"] = storage_host if "://" in storage_host else f"http://{storage_host}"
    for var in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "STORAGE_EMULATOR_HOST"):
        host = os.environ[var].split("://")[-1].split(":")[0]
        if host not in ("127.0.0.1", "localhost", "::1", "[::1]"):
            raise SystemExit(f"refusing to run: {var}={os.environ[var]!r} is not local")
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)


guard()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import firebase_admin  # noqa: E402
import google.auth.credentials  # noqa: E402
from firebase_admin import auth, credentials, storage  # noqa: E402
from google.cloud import firestore  # noqa: E402


class _Owner(google.auth.credentials.Credentials):
    """What the emulators accept as the admin (`Authorization: Bearer owner`); no real credential exists here."""

    def __init__(self):
        super().__init__()
        self.token = "owner"

    def refresh(self, request):
        self.token = "owner"

    @property
    def expired(self):
        return False

    @property
    def valid(self):
        return True


class _EmuCred(credentials.Base):
    def get_credential(self):
        return _Owner()


_real_init = firebase_admin.initialize_app


def _init(credential=None, options=None, name="[DEFAULT]"):          # tools/erase_account.py calls initialize_app(options=...) with ADC
    return _real_init(_EmuCred(), options, name)


firebase_admin.initialize_app = _init
OPTS = {"projectId": PROJECT, "storageBucket": BUCKET}
seed_app = firebase_admin.initialize_app(options=OPTS, name="seed")
db = firestore.Client(project=PROJECT)
bucket = storage.bucket(app=seed_app)


def fresh_default_app() -> None:                                            # the tool initialises the default app on every real run
    try:
        firebase_admin.delete_app(firebase_admin.get_app())
    except ValueError:
        pass


def put(path: str, data=None) -> None:
    db.document(path).set(data or {"x": 1})


def seed(uid: str, email: str, share: str) -> None:
    auth.create_user(uid=uid, email=email, app=seed_app)
    put(f"users/{uid}", {"email": email})
    for coll in ("tl", "pages", "pics", "picbig", "bglib", "bgimg", "edits"):
        put(f"users/{uid}/{coll}/c1", {"d": b"photo" if coll.startswith("pic") else "x"})
    put(f"users/{uid}/tl/t1/reports/r1")                                  # a nested one
    put(f"users/{uid}/pics/photo-1", {"d": b"\xff\xd8\xff"})
    put(f"users/{uid}/picbig/photo-1", {"d": b"\xff\xd8\xff"})
    put(f"shares/{share}", {"title": "t"})
    put(f"shares/{share}/private/owner", {"owner": uid})
    put(f"shares/{share}/pics/photo-1", {"d": b"\xff\xd8\xff"})
    put(f"shares/{share}/picbig/photo-1", {"d": b"\xff\xd8\xff"})
    put(f"hosted_shares/{uid}_t1", {"uid": uid})
    put(f"terms_acceptance/{uid}_v1", {"uid": uid, "version": "v1"})
    put(f"bass_credits/{uid}", {"entries": []})
    put(f"bass_docs/{uid}", {"files": {"f1": {"name": "x"}}})
    put(f"bass_doc_text/{uid}_f1", {"t": "x"})
    put(f"bass_beta_meta/{uid}_2026-11-01", {"n": 1})
    put(f"bass_research_consent/{uid}", {"v": 1})
    for name in (f"builds/{uid}/t1/page.html", f"builds/{uid}/t1/photo-1.jpg", f"builds/{uid}/t1/photo-2.jpg",
                 f"users/{uid}/bass/f1", f"users/{uid}/photos/photo-1.jpg"):
        bucket.blob(name).upload_from_string(b"x" * 64, content_type="application/octet-stream")


def walk(coll) -> list[str]:
    """Every document path under a collection, including ones that exist only as a parent of a subcollection."""
    out = []
    for ref in coll.list_documents():
        out.append(ref.path)
        for sub in ref.collections():
            out += walk(sub)
    return out


def all_paths() -> list[str]:
    out = []
    for coll in db.collections():
        out += walk(coll)
    return out


def blobs() -> list[str]:
    return [b.name for b in bucket.list_blobs()]


def auth_uids() -> set[str]:
    return {u.uid for u in auth.list_users(app=seed_app).iterate_all()}


def mine(items, uid):
    return [i for i in items if uid in i]


def main() -> int:
    seed(GONE, GONE_EMAIL, "E" * 22)
    seed(KEEP, KEEP_EMAIL, "K" * 22)
    put("bass_beta/allowlist", {"emails": [GONE_EMAIL, KEEP_EMAIL]})

    before_docs, before_blobs = all_paths(), blobs()
    assert len(mine(before_docs, GONE)) >= 15 and len(mine(blobs(), GONE)) == 5, "the seed did not land (the check would pass for nothing)"
    assert any("photo-1" in p for p in mine(before_docs, GONE)) and any("photo-" in b for b in mine(before_blobs, GONE))
    assert GONE in auth_uids() and KEEP in auth_uids()
    kept_docs, kept_blobs = mine(before_docs, KEEP) + [f"shares/{'K' * 22}"], mine(before_blobs, KEEP)
    kept_docs_n = len(mine(before_docs, KEEP))

    import builtins
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
    import erase_account
    argv = ["--project", PROJECT, "--bucket", BUCKET, "--uid", GONE, "--email", GONE_EMAIL]

    assert erase_account.main(argv) == 0                                    # a dry run changes nothing
    assert len(all_paths()) == len(before_docs) and len(blobs()) == len(before_blobs) and GONE in auth_uids()

    real_input = builtins.input
    builtins.input = lambda prompt="": KEEP                                 # the uid typed again must be the same uid
    try:
        assert erase_account.main(argv + ["--yes"]) == 1
    finally:
        builtins.input = real_input
    assert len(all_paths()) == len(before_docs) and len(blobs()) == len(before_blobs) and GONE in auth_uids()

    builtins.input = lambda prompt="": GONE
    fresh_default_app()
    try:
        assert erase_account.main(argv + ["--yes"]) == 0                    # the real erase: Firestore, Storage, then the Auth user
    finally:
        builtins.input = real_input

    left_docs, left_blobs, left_uids = mine(all_paths(), GONE), mine(blobs(), GONE), [GONE] if GONE in auth_uids() else []
    left_docs += [p for p in all_paths() if p.startswith(f"shares/{'E' * 22}")]
    allow = db.document("bass_beta/allowlist").get().to_dict()["emails"]
    problems = {"firestore": left_docs, "storage": left_blobs, "auth": left_uids,
                "allowlist": [e for e in allow if e == GONE_EMAIL]}
    assert not any(problems.values()), f"left behind after the erase: {problems}"
    try:
        auth.get_user(GONE, app=seed_app)
        raise AssertionError("the Auth user is still there")
    except auth.UserNotFoundError:
        pass
    # the other account is untouched
    now_docs, now_blobs = all_paths(), blobs()
    assert len(mine(now_docs, KEEP)) == kept_docs_n and all(p in now_docs for p in kept_docs), "the other account lost documents"
    assert sorted(mine(now_blobs, KEEP)) == sorted(kept_blobs), "the other account lost Storage objects"
    assert KEEP in auth_uids() and allow == [KEEP_EMAIL]
    # a second run is harmless
    builtins.input = lambda prompt="": GONE
    fresh_default_app()
    try:
        assert erase_account.main(argv + ["--yes"]) == 0
    finally:
        builtins.input = real_input
    print(f"erase against the emulators: {len(before_docs) - len(now_docs)} documents, {len(before_blobs) - len(now_blobs)} objects "
          f"and the Auth user gone; the other account intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
