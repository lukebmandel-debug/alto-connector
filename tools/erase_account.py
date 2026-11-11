"""Erase one Alto account completely: Firestore, Storage and the Firebase Auth user.

NOT RUN by builders and not wired to anything. IT / Release runs it by hand, per the deletion rule: a dry run
first, then the uid typed again, then the work. It uses the Admin SDK with the operator's own credentials.

    python tools/erase_account.py --project <id> --bucket <storage bucket> --uid <uid> [--email <their email>]
    ... add --yes to do it (it then asks for the uid once more)

What it removes is alto/store/erase.py (read its docstring), then the Auth user (firebase_admin.auth.delete_user), which
also fires the Bass proxy's account-deleted hook (documents, opt-in conversation purge ticket) if that is deployed."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--uid", required=True)
    ap.add_argument("--email", default="")
    ap.add_argument("--yes", action="store_true", help="do it (otherwise a dry run that only says what it would do)")
    a = ap.parse_args(argv)
    from alto.store import erase
    if not erase._UID.match(a.uid):
        print("not a user id")
        return 2
    if not a.yes:
        print(f"DRY RUN for {a.uid}: would erase Firestore (users/, shares owned, hosted_shares, terms_acceptance, bass_*), "
              f"Storage builds/{a.uid}/ and users/{a.uid}/ in {a.bucket}, the allowlist entry"
              f"{' for ' + a.email if a.email else ' (no --email: NOT removed)'}, and the Auth user. Add --yes.")
        return 0
    if input(f"Type the uid ({a.uid}) again to erase it for good: ").strip() != a.uid:
        print("not the same; nothing done")
        return 1
    import firebase_admin
    from firebase_admin import auth, storage
    from google.cloud import firestore
    firebase_admin.initialize_app(options={"projectId": a.project, "storageBucket": a.bucket})
    counts = erase.erase_user(firestore.Client(project=a.project), a.uid, email=a.email, bucket=storage.bucket())
    print("erased:", counts)
    try:
        auth.delete_user(a.uid)
        print("Auth user deleted")
    except auth.UserNotFoundError:
        print("no Auth user with that uid (already deleted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
