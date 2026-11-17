"""Firebase CLI entry for hosted Bass (one account, alto/bass/hosted.py). NOT DEPLOYED. build_bundle.py --firebase copies this file as
functions/main.py next to main.py (copied as proxy_main.py), the alto package and firebase.json; `firebase deploy --only functions:altoext`
deploys it. The function id is generic on purpose: its URL is in the CSP and the hook every luke-alto visitor downloads.

Options are fixed here, not in the Console: one instance with four requests at most (the in-flight limit is per process), 512 MiB, the
BetaConfig function timeout, public invoker (callers prove themselves with a Firebase ID token in the gate). SERVICE_ACCOUNT is written by
build_bundle.py (--service-account); None = the project's default compute account (see HOSTED-BUILD.md: a dedicated one is the plan)."""
import logging
import sys

from firebase_functions import https_fn, options

import proxy_main

# WARNING and up go to stderr, which Cloud Logging collects; INFO stays off on purpose (see LOG-AUDIT-keystrip.md)
logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(name)s %(message)s")
for _n in ("anthropic", "httpx", "httpx2", "httpcore", "h11", "urllib3", "google", "grpc"):     # SDK DEBUG logs carry request bodies and headers: never emitted, whatever ANTHROPIC_LOG says
    logging.getLogger(_n).setLevel(logging.WARNING)

SERVICE_ACCOUNT = None
_gate = None


@https_fn.on_request(region="us-central1", memory=options.MemoryOption.MB_512, cpu=1, timeout_sec=300, min_instances=0, max_instances=1,
                     concurrency=4, invoker="public", service_account=SERVICE_ACCOUNT)
def altoext(req):
    global _gate
    if _gate is None:
        _gate = proxy_main.build_hosted()
    status, headers, body = _gate.handle_http(req.method, dict(req.headers), req.get_data())
    return https_fn.Response(body, status=status, headers=headers)
