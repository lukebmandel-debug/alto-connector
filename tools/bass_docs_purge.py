"""Bass Documents erase job. IT schedules it; nothing here runs by itself, and a cloud seat never runs it against a real project.

    python tools/bass_docs_purge.py --project <gcp project> [--bucket <Documents Storage bucket>]
        DAILY: erases every account's documents deleted 7 or more days ago (index entry, text, original). Prints counts only.
    python tools/bass_docs_purge.py --project <gcp project> [--bucket ...] --erase-account <uid>
        ACCOUNT DELETION: erases every document of that account at once, the ones in their 7-day recovery included.

Needs Firestore read/write on bass_docs + bass_doc_text and, with --bucket, delete on users/<uid>/bass/* in that bucket. Without --bucket
the originals stay until removed by hand, but storage.rules already refuse them to everyone once the index no longer lists them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "deploy" / "bass-proxy"))

from alto.bass import documents as D  # noqa: E402
from alto.bass.beta_config import BetaConfig  # noqa: E402


def run(store, blobs=None, erase_account=None, clock=None, cfg=None) -> dict:
    cfg = cfg or BetaConfig(testers=1)
    clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
    if erase_account is not None:
        if not re.match(r"^[A-Za-z0-9_-]{1,128}$", erase_account):
            raise SystemExit("not a uid")
        return {"erased": D.Library(store, cfg, clock, blobs=blobs).erase_account(erase_account)}
    return D.purge_expired(store, cfg, clock, blobs=blobs)


def _google(project, bucket):
    from google.cloud import firestore, storage
    from firestore_store import FirestoreStore
    blobs = None
    if bucket:
        b = storage.Client(project=project).bucket(bucket)

        class _Blobs:
            def delete(self, path):
                if not re.match(r"^users/[A-Za-z0-9_-]+/bass/[A-Za-z0-9_-]+$", path):
                    raise ValueError("not a Bass Documents path")
                b.blob(path).delete()
        blobs = _Blobs()
    return FirestoreStore(firestore.Client(project=project)), blobs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bass Documents erase job (daily 7-day purge, or one account's deletion).")
    ap.add_argument("--project", required=True)
    ap.add_argument("--bucket")
    ap.add_argument("--erase-account", metavar="UID")
    a = ap.parse_args(argv)
    from alto.cloud import offline
    if offline.reason() is not None:                                    # incident 11 Nov: no Google credential read in a test/mock process
        print(f"refused: {Path(__file__).name} reads Firestore with Google's default credentials, and this process is offline "
              f"({offline.reason()}). Run it from IT's own environment without ALTO_NO_NETWORK.", file=sys.stderr)
        return 2
    store, blobs = _google(a.project, a.bucket)
    print(json.dumps(run(store, blobs, a.erase_account)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
