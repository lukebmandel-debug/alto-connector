"""Erasing an account's data (Admin SDK shape: `db` is a google.cloud.firestore.Client, `bucket` an optional
google.cloud.storage Bucket).

There was no account-deletion code before this (deletion was by email, by hand);
this is the one place that says what an account owns, so a hand run or a future
Auth "user deleted" trigger removes all of it:

  Firestore
  users/{uid}/**                  every collection the account owns (tl, pages, bglib/bgimg,
                                  pics/picbig, edits, ...) and anything added later
  shares/{key}/** for each share  the page, its owner record and the picture copies
                                  (shares/{key}/pics|picbig) of every share the account owns
  hosted_shares/{uid}_{tid}       the hosted index entries
  terms_acceptance/{uid}_{ver}    the Beta Terms record (found by its `uid` field)
  bass_credits/{uid}              the Bass credit ledger
  bass_docs/{uid}                 the Bass Documents index, and bass_doc_text/{uid}_{fid} for each file in it
  bass_beta_meta/{uid}_{day}      the per-day Bass metadata lines
  bass_research_consent/{uid}     the opt-in conversation-sharing record
  bass_beta/allowlist             the account's EMAIL is removed from the list (pass `email`)
  Storage (pass `bucket`)
  builds/{uid}/                   built artifacts (alto/store/firestore.py)
  users/{uid}/                    the originals of Bass Documents (users/{uid}/bass/{fid}, storage.rules)

NOT done here, so the admin run below must do them:
  1. The Firebase Auth user: client code cannot delete it. tools/erase_account.py (never run by a builder)
     does it with firebase_admin.auth.delete_user(uid) after this function; or Console > Authentication.
  2. Opt-in Bass conversation objects (bucket conv/<pseudonym>/...): they are named by an HMAC of the uid
     with a secret this code does not hold. The Bass proxy's account-deleted hook
     (deploy/bass-proxy/main.py bass_docs_account_deleted, on the Auth user-delete event) tickets
     them for the purge; if the Auth user is deleted by tools/erase_account.py that hook runs by itself.
  3. Logs age out in 30 days (policy); a manual export copy, if one was made, is deleted by hand.

Nothing here is wired to a trigger or deployed. Never call it on a real account
from a test or a builder; the tests use an in-memory fake."""
from __future__ import annotations

import re

_UID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# The collections firestore.rules names as an account's own (ownCollection). A test keeps this
# equal to the rules, so a collection added there cannot be forgotten here.
USER_COLLECTIONS = ("tl", "pages", "pagemeta", "shared", "bglib", "bgimg", "pics", "picbig",
                    "edits", "alto_projects", "alto_snapshots", "alto_timelines")
SHARE_COPY_COLLECTIONS = ("pics", "picbig")
# The top-level collections firestore.rules matches (users and shares are handled above; a test keeps
# this equal to the rules, so a new top-level collection must be classified here).
RULES_TOP_LEVEL = {"users": "users/{uid}/**", "shares": "owned shares", "terms_acceptance": "by uid field",
                   "bass_beta": "allowlist entry (email)"}
# Server-only collections (no client rule matches them) that hold an account's data, by document id.
SERVER_BY_UID = ("bass_credits", "bass_docs", "bass_research_consent")
SERVER_BY_UID_PREFIX = ("bass_beta_meta",)           # {uid}_{YYYY-MM-DD}
STORAGE_PREFIXES = ("builds/{uid}/", "users/{uid}/")


def owned_share_refs(db, uid: str) -> list:
    """Every share the account owns: by its owner record (shares/{key}/private/owner), and the
    older shares that name the owner on the share document itself."""
    refs = {}
    for snap in db.collection_group("private").where("owner", "==", uid).stream():
        share = snap.reference.parent.parent
        if share is not None and share.parent.id == "shares":
            refs[share.path] = share
    for snap in db.collection("shares").where("owner", "==", uid).stream():
        refs[snap.reference.path] = snap.reference
    return list(refs.values())


def _delete_doc(db, coll: str, doc_id: str) -> int:
    ref = db.collection(coll).document(doc_id)
    snap = ref.get()
    if not snap.exists:
        return 0
    ref.delete()
    return 1


def _erase_bass(db, uid: str) -> int:
    n = 0
    index = db.collection("bass_docs").document(uid).get()
    if index.exists:                                       # one text document per file the index lists (deleted ones too)
        for fid in sorted(((index.to_dict() or {}).get("files") or {})):
            if isinstance(fid, str) and re.match(r"^[A-Za-z0-9_-]{1,64}$", fid):
                n += _delete_doc(db, "bass_doc_text", f"{uid}_{fid}")
    for coll in SERVER_BY_UID:
        n += _delete_doc(db, coll, uid)
    day = re.compile(r"^" + re.escape(uid) + r"_\d{4}-\d{2}-\d{2}$")
    for coll in SERVER_BY_UID_PREFIX:
        for snap in list(db.collection(coll).stream()):
            if day.match(snap.reference.id):
                snap.reference.delete()
                n += 1
    return n


def _erase_terms(db, uid: str) -> int:
    snaps = list(db.collection("terms_acceptance").where("uid", "==", uid).stream())
    for snap in snaps:
        snap.reference.delete()
    return len(snaps)


def _erase_allowlist(db, email: str) -> int:
    ref = db.collection("bass_beta").document("allowlist")
    snap = ref.get()
    if not snap.exists:
        return 0
    emails = list((snap.to_dict() or {}).get("emails") or [])
    keep = [e for e in emails if str(e).strip().lower() != email.strip().lower()]
    if len(keep) == len(emails):
        return 0
    ref.update({"emails": keep})
    return 1


def _erase_storage(bucket, uid: str) -> int:
    n = 0
    for pat in STORAGE_PREFIXES:
        for blob in list(bucket.list_blobs(prefix=pat.format(uid=uid))):
            blob.delete()
            n += 1
    return n


def erase_user(db, uid: str, email: str = "", bucket=None) -> dict:
    """Remove everything the account owns (see the module docstring for what, and for the admin steps
    that remain). `email` removes the beta allowlist entry; `bucket` removes the Storage files.
    Returns counts only."""
    if not isinstance(uid, str) or not _UID.match(uid):
        raise ValueError("not a user id")
    if email and (not isinstance(email, str) or "@" not in email or len(email) > 320):
        raise ValueError("not an email address")
    shares = owned_share_refs(db, uid)
    for ref in shares:                       # share copies first, while the owner record still names the account
        db.recursive_delete(ref)
    hosted = list(db.collection("hosted_shares").where("uid", "==", uid).stream())
    for snap in hosted:
        snap.reference.delete()
    out = {"shares": len(shares), "hosted": len(hosted)}
    out["terms"] = _erase_terms(db, uid)
    out["bass"] = _erase_bass(db, uid)
    out["allowlist"] = _erase_allowlist(db, email) if email else 0
    out["files"] = _erase_storage(bucket, uid) if bucket is not None else 0
    db.recursive_delete(db.collection("users").document(uid))
    return out
