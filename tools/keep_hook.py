#!/usr/bin/env python3
"""The luke-alto publish step's hook keeper (v1.9.233, Board B-1115-173757).

A release that does not touch the extension must not take it away from luke-alto. The release seat, only when live_go is on (read by the seat
by hand, NEVER by this tool: it uses no Firestore, no network and no account), runs this for the luke-alto publish ONLY:

    ALTO_KEEP_HOOK=1 ALTO_EXT_URL=https://us-central1-terrarium-alto.cloudfunctions.net/altoext python3 tools/keep_hook.py

It prints `export ALTO_EXT_URL=...` (exit 0) when the deployed-pin record (a file OUTSIDE the repo: ~/.alto-work/altoext-deployed-pin.txt, or ALTO_EXT_DEPLOYED_PIN_FILE) lists the pin in alto/cloud/ext_pin.txt and the bundle this tree serves has it, so the publish re-attaches
the hook with the currently deployed pin; otherwise it prints why and exits 2 (publish without the hook, and redeploy the function first). The
alto-connector publish and the default build never run it: no flag, no hook, no extension text (tests/test_keep_hook_233.py)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alto.cloud import ext_hook  # noqa: E402


def main() -> int:
    if os.environ.get(ext_hook.KEEP_ENV, "").strip() != "1":
        print("ALTO_KEEP_HOOK=1 is not set: no hook (the default).", file=sys.stderr)
        return 2
    u = ext_hook.keep_url()
    if not u:
        print("not kept: ALTO_EXT_URL is missing or not a Cloud Functions/Run address, the deployed-pin record is missing, inside the repo, or lacks the tree's pin, "
              "or the served bundle does not have that pin (redeploy the function for the new pin first).", file=sys.stderr)
        return 2
    print("export ALTO_EXT_URL=" + u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
