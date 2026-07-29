#!/bin/bash
# Alto Connector — deploy the HOSTED variant (Cloud Run + Firebase Hosting).
#
# This is the parked paid path; the shipped connector runs locally over stdio
# and needs none of this. Requires `gcloud auth login` and `firebase login`.
#
# Nothing about a Firebase project is hardcoded here on purpose. This script is
# public, and a project baked into it is a project every reader of every
# published timeline would be pooled into. Set these first:
#
#   export ALTO_PROJECT=your-firebase-project
#   export ALTO_BUCKET=your-firebase-project.firebasestorage.app
#   export ALTO_FIREBASE_CONFIG='{"apiKey":"…","authDomain":"…","projectId":"…",
#                                 "storageBucket":"…","messagingSenderId":"…",
#                                 "appId":"…"}'
#   # ↑ copy from Firebase console → Project settings → Your apps → SDK setup
#
set -euo pipefail

: "${ALTO_PROJECT:?set ALTO_PROJECT to your Firebase/GCP project id}"
: "${ALTO_BUCKET:?set ALTO_BUCKET to your storage bucket}"
: "${ALTO_FIREBASE_CONFIG:?set ALTO_FIREBASE_CONFIG to your web SDK config JSON}"

REGION="${ALTO_REGION:-us-central1}"
SERVICE="${ALTO_SERVICE:-alto-connector}"
PUBLIC_BASE="${ALTO_PUBLIC_BASE:-https://${SERVICE}.web.app}"

# 1. Cloud Run from source (Cloud Build does the container build — no local docker)
gcloud run deploy "$SERVICE" \
  --project "$ALTO_PROJECT" --region "$REGION" \
  --source . \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --min-instances 0 --max-instances 3 \
  --update-env-vars "ALTO_STORE=firestore,ALTO_PUBLIC_BASE=${PUBLIC_BASE},ALTO_BUCKET=${ALTO_BUCKET},ALTO_SESSION_SECRET=$(openssl rand -hex 32)" \
  --update-env-vars "^;^ALTO_FIREBASE_CONFIG=${ALTO_FIREBASE_CONFIG}"

# 2. Hosting site + rewrites (idempotent)
firebase hosting:sites:create "$SERVICE" --project "$ALTO_PROJECT" || true
(cd firebase && firebase deploy --only "hosting:${SERVICE}" --project "$ALTO_PROJECT")

echo "Live at ${PUBLIC_BASE}"
