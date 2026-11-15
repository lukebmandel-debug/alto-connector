#!/usr/bin/env python3
"""DRY RUN ONLY. Prints the exact commands that would deploy the Bass beta proxy and the IAM it needs. There is no apply mode:
Blaze is off and nothing is deployed until Luke turns it on and says go; then IT runs the printed commands by hand.

    python3 deploy/bass-proxy/deploy.py --project <firebase-project-id> --testers 10 --bucket <alto-bass-bucket> [--region us-central1]

The project id and the bucket name are NOT written in this repository (review finding D3): pass them, or set ALTO_BASS_PROJECT and
ALTO_BASS_BUCKET in the operator's own environment (IT keeps the real values in its private notes).
"""
import argparse
import os
import sys
from pathlib import Path

FUNCTION = "bass-proxy"
SECRET = "alto-bass-beta-key"


def service_account(project: str) -> str:
    return f"bass-proxy@{project}.iam.gserviceaccount.com"


def iam(project: str, bucket: str = "<bucket>") -> list:
    sa = service_account(project)
    return [
        f"serviceAccount:{sa}  roles/datastore.user            (Firestore read/write: credits, counters, kill switch, allowlist)",
        f"serviceAccount:{sa}  roles/secretmanager.secretAccessor ON SECRET {SECRET} ONLY (never project-wide)",
        f"serviceAccount:{sa}  roles/storage.objectAdmin ON gs://{bucket} ONLY (the Alto store writes build artifacts there; never project-wide)",
        "NOT granted: roles/firebaseauth.viewer (verify_id_token with check_revoked=False checks signatures against Google's public keys and needs no role), "
        "any Compute role, secretmanager.admin, owner/editor. No one but the function reads the key.",
    ]


def origins() -> list:
    """The pages allowed to call the proxy: the config default (alto/bass/beta_config.py), one place."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from alto.bass.beta_config import BetaConfig
    return list(BetaConfig(testers=1).allowed_origins)


def plan(project: str, region: str, testers: int, bucket: str) -> list:
    sa = service_account(project)
    allowed = origins()                                  # also puts the repo root on sys.path
    from alto.bass.beta_config import BetaConfig
    timeout = BetaConfig(testers=1).function_timeout_s
    env = f"^;^GCP_PROJECT={project};BASS_BETA_TESTERS={testers};ALTO_BUCKET={bucket};BASS_ALLOWED_ORIGINS={','.join(allowed)}"
    return [
        f"gcloud iam service-accounts create bass-proxy --project {project} --display-name 'Bass beta proxy'",
        f"gcloud secrets create {SECRET} --project {project} --replication-policy automatic      # then add the key as a version: IT, from the Console key, never via chat or a file in the repo",
        f"gcloud secrets add-iam-policy-binding {SECRET} --project {project} --member serviceAccount:{sa} --role roles/secretmanager.secretAccessor",
        f"gcloud projects add-iam-policy-binding {project} --member serviceAccount:{sa} --role roles/datastore.user",
        f"gcloud storage buckets add-iam-policy-binding gs://{bucket} --member serviceAccount:{sa} --role roles/storage.objectAdmin      # the bucket must already exist: IT names it; this script creates nothing",
        "python3 deploy/bass-proxy/build_bundle.py   # copies alto + the function files + merged requirements into a clean folder: the tested code is the deployed code",
        (f"gcloud functions deploy {FUNCTION} --gen2 --project {project} --region {region} --runtime python312 "
         f"--source <bundle-folder> --entry-point bass_proxy --trigger-http --allow-unauthenticated "
         f"--service-account {sa} --max-instances 5 --min-instances 0 --memory 512Mi --concurrency 4 --timeout {timeout}s "
         f"--set-env-vars '{env}'"),
        "# --allow-unauthenticated is deliberate: callers prove themselves with a Firebase ID token in the handler, which also verifies the email.",
        "# --max-instances is a COST ceiling, not a defence (it locks out real users when reached). --concurrency 4 because the in-flight limit is per process.",
        "# --timeout is BetaConfig.function_timeout_s. An action stops itself at action_wall_s (below it) and books what it started; a build that needs longer is resumed, never cut mid-stream.",
        "uploads: pypdf (pinned in requirements.txt) reads PDFs in a child process; caps are BetaConfig values (docs/bass-beta-runbook.md, Uploads). Request body up to max_request_bytes (9 MB): keep the function's own limit above it.",
        "firestore doc map: the Beta Terms record terms_acceptance/<uid>_<version> is written by the page and only READ by the proxy (Bass refuses a uid without the current version).",
        "opt-in conversation sharing (DARK): BASS_RESEARCH_BUCKET names the separate research bucket; the proxy account gets objectCreator only; bass_research/switch {enabled: true} is absent = OFF; secret bass-research-hmac. Nothing is saved before the independent attack passes and IT's roles question is answered.",
        "Add from Drive (names only, IT sets the values, ORG/it/bass-drive-deploy.md): ALTO_DRIVE_CLIENT_ID, ALTO_DRIVE_API_KEY, ALTO_DRIVE_APP_ID on the function (all three or none: a partial set stops the cold start with a message naming the missing ones); the site build gets ALTO_BASS_UI=1 + ALTO_BASS_BASE and publishes /drive-picker/ with its own CSP.",
        "firestore docs, by hand in the Console: bass_beta/bass_testers {emails: [...]} (Bass's OWN tester list, at most N emails: a longer list admits nobody), bass_beta/live_go {on: false}. bass_beta/allowlist is the Alto cloud beta's list and gives no Bass access.",
        "firestore docs that stay ABSENT until needed: bass_beta/kill (trips itself; delete or {on:false} to reset), bass_beta/disabled (IT's budget cutoff sets it).",
        "each credit period (the 17th): IT sets bass_beta_periods/<period id> {confirmed: true} ONLY after Luke confirms the credit refreshed (first id 2026-10-17); no marker, no Bass.",
    ]


HOSTED_FUNCTION = "altoext"


def hosted_plan(project: str, sa=None) -> list:
    """Hosted Bass for ONE account (alto/bass/hosted.py) with the firebase CLI only (no gcloud on Home). Printed, never run."""
    fb = "~/.local/node/bin/firebase"
    url = f"https://us-central1-{project}.cloudfunctions.net/{HOSTED_FUNCTION}"
    return [
        "# 0. Console (no gcloud): Secret Manager > alto-bass-beta-key exists with Luke's NEW key named `bass-proxy` (he makes it and puts it there himself; he disables it in the Anthropic Console after the promo);",
        "#    its Permissions: the function's runtime service account gets Secret Manager Secret Accessor on THIS secret only.",
        f"~/.local/share/alto/venv/bin/python deploy/bass-proxy/build_bundle.py --firebase <bundle> --service-account {sa}   # <bundle> outside ~/Desktop; refuses without the account",
        "cd <bundle>/functions && ~/.local/bin/python3.12 -m venv venv && venv/bin/pip install -r requirements.txt   # the firebase CLI needs this venv",
        f"printf 'ALTO_EXT_PROJECT={project}\\nALTO_EXT_UIDS=<LUKE_UID>\\n' > <bundle>/functions/.env",
        f"cd <bundle> && {fb} deploy --only functions:{HOSTED_FUNCTION}:{HOSTED_FUNCTION} --project {project}",
        f"# then CHECK in the Console (Cloud Run > {HOSTED_FUNCTION} > Security): the service account is {sa}, not <number>-compute@developer.gserviceaccount.com",
        f"# the function URL: {url}  (generic: it is in the CSP and the hook of every luke-alto visitor)",
        "# Firestore docs (Console, by hand; bass_beta/** is server-only in firestore.rules):",
        "#   bass_beta/hosted        {uids: ['<LUKE_UID>']}",
        "#   bass_beta/bass_testers  {emails: ['<LUKE_EMAIL>']}      (one entry: N = 1, a longer list admits nobody)",
        "#   bass_beta_periods/2026-11-01 {confirmed: true}           (the hosted period starts on the 1st)",
        "#   bass_beta/live_go       {on: false}  -> mock;  {on: true} only on the Board's GO",
        f"# then publish luke-alto as usual with ALTO_EXT_URL={url} in the publish environment (ALTO_BASS_UI stays UNSET)",
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", default=os.environ.get("ALTO_BASS_PROJECT", ""), help="the Firebase project id (or ALTO_BASS_PROJECT); never written in the repo")
    ap.add_argument("--region", default="us-central1")
    ap.add_argument("--testers", type=int, default=0, help="N, up to 15; config, no default")
    ap.add_argument("--bucket", default=os.environ.get("ALTO_BASS_BUCKET", ""), help="the Cloud Storage bucket the Alto store writes to (or ALTO_BASS_BUCKET; IT names it; nothing is created here)")
    ap.add_argument("--hosted", action="store_true", help="print the firebase-CLI plan for hosted Bass (one account)")
    ap.add_argument("--service-account", default="", help="--hosted: the function's dedicated service account (required)")
    ap.add_argument("--apply", action="store_true", help="REFUSED: there is no apply mode")
    a = ap.parse_args(argv)
    if a.apply:
        print("refused: this script only prints. Blaze is off and nothing is deployed until Luke says go.", file=sys.stderr)
        return 2
    if a.hosted:
        if not a.project or not a.service_account:
            print("refused: give --project and --service-account (never the default compute account).", file=sys.stderr)
            return 2
        print("DRY RUN. Nothing was executed.\n")
        print("\n".join("  " + c for c in hosted_plan(a.project, a.service_account or None)))
        return 0
    if a.testers <= 0 or not a.bucket or not a.project:
        print("refused: give --project, --testers (N) and --bucket (IT names it); they are config, not defaults.", file=sys.stderr)
        return 2
    print("DRY RUN. Nothing was executed.\n\nIAM:")
    print("\n".join("  " + x for x in iam(a.project, a.bucket)))
    print("\nCommands (run by hand, in order, after Luke turns on Blaze and says go):")
    print("\n".join("  " + c for c in plan(a.project, a.region, a.testers, a.bucket)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
