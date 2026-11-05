"""Erasing an account's data from Firestore (Admin SDK shape: `db` is a
google.cloud.firestore.Client).

There was no account-deletion code before this (deletion was by email, by hand);
this is the one place that says what an account owns, so a hand run or a future
Auth "user deleted" trigger removes all of it:

  users/{uid}/**                  every collection the account owns (tl, pages, bglib/bgimg,
                                  pics/picbig, edits, ...) and anything added later
  shares/{key}/** for each share  the page, its owner record and the picture copies
                                  (shares/{key}/pics|picbig) of every share the account owns
  hosted_shares/{uid}_{tid}       the hosted index entries

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


def erase_user(db, uid: str) -> dict:
    """Remove everything the account owns. Returns counts only."""
    if not isinstance(uid, str) or not _UID.match(uid):
        raise ValueError("not a user id")
    shares = owned_share_refs(db, uid)
    for ref in shares:                       # share copies first, while the owner record still names the account
        db.recursive_delete(ref)
    hosted = list(db.collection("hosted_shares").where("uid", "==", uid).stream())
    for snap in hosted:
        snap.reference.delete()
    db.recursive_delete(db.collection("users").document(uid))
    return {"shares": len(shares), "hosted": len(hosted)}
