"""Cloud Function (2nd gen, Python 3.12) entry point: bass_proxy(request). NOT DEPLOYED: Blaze is off.
Cold start builds ONE Proxy from the vendored alto package (the tested code IS the deployed code) and Google's adapters.
Google libraries are imported inside _build(), so a test can stand in for them and prove the cold-start path does not raise.
The key is read from Secret Manager only when bass_beta/live_go is on; nothing here reads an env var for a key.

Environment (deploy.py sets all of them): GCP_PROJECT, BASS_BETA_TESTERS, ALTO_BUCKET (the Alto store the build tools write to needs
its Cloud Storage bucket), BASS_ALLOWED_ORIGINS (optional, comma separated; the config default otherwise), BASS_DOCS_BUCKET (optional:
the Firebase Storage bucket that holds Bass Documents originals under users/<uid>/bass/<fid>; set, the 7-day purge also deletes the original;
unset, the original stays but storage.rules refuse it to everyone once the index no longer lists it)."""
import datetime as dt
import os

try:
    import functions_framework
    _http = functions_framework.http
except ImportError:                                   # the legacy (request) signature works for an HTTP function too
    def _http(f):
        return f

REQUIRED_ENV = ("GCP_PROJECT", "BASS_BETA_TESTERS", "ALTO_BUCKET")
OPTIONAL_ENV = ("BASS_ALLOWED_ORIGINS", "BASS_DOCS_BUCKET", "BASS_RESEARCH_BUCKET")
DRIVE_ENV = ("ALTO_DRIVE_CLIENT_ID", "ALTO_DRIVE_API_KEY", "ALTO_DRIVE_APP_ID")    # Add from Drive: all three or none (alto/bass/drive.py DriveConfig); values are IT's
_proxy = None


def _build():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise RuntimeError("bass-proxy is missing environment: " + ", ".join(missing))
    part = [k for k in DRIVE_ENV if not os.environ.get(k)]
    if 0 < len(part) < len(DRIVE_ENV):                            # fail closed, loudly: a half-set Drive config is a deploy mistake, not "off"
        raise RuntimeError("bass-proxy: Add from Drive is partly configured, missing environment: " + ", ".join(part) + " (set all three or none)")
    import firebase_admin
    from firebase_admin import auth as fb_auth
    from google.cloud import firestore, secretmanager

    from alto.bass.beta_config import BetaConfig
    from alto.bass.beta_proxy import AuthError, Proxy, SecretReader, TokenVerifier
    from alto.bass.tools import ToolBox
    from alto.store.firestore import FirestoreStore as AltoStore       # the Alto store the build tools write to (ALTO_BUCKET names its bucket)
    from firestore_store import FirestoreStore as GuardStore

    class _Verifier(TokenVerifier):
        def verify(self, id_token):
            try:
                d = fb_auth.verify_id_token(id_token, check_revoked=False)
            except Exception:
                raise AuthError
            # Google sign-in ONLY (review finding S2): a token from any other provider (password, anonymous, phone, a custom token) is
            # refused even if someone later enables that provider in the project and even with a verified email claim.
            fb = d.get("firebase") if isinstance(d, dict) else None
            if not isinstance(fb, dict) or fb.get("sign_in_provider") != "google.com":
                raise AuthError
            return {"uid": d["uid"], "email": d.get("email", ""), "email_verified": d.get("email_verified") is True}

    class _Secrets(SecretReader):
        def __init__(self, project):
            self.c, self.project = secretmanager.SecretManagerServiceClient(), project

        def read(self, name):
            r = self.c.access_secret_version(name=f"projects/{self.project}/secrets/{name}/versions/latest")
            return r.payload.data.decode("utf-8")

    firebase_admin.initialize_app()
    project = os.environ["GCP_PROJECT"]                           # a project id, not a secret
    kw = {}
    if os.environ.get("BASS_ALLOWED_ORIGINS"):
        kw["allowed_origins"] = tuple(o for o in os.environ["BASS_ALLOWED_ORIGINS"].split(",") if o)
    cfg = BetaConfig(testers=int(os.environ["BASS_BETA_TESTERS"]), allowlist=frozenset(), **kw)   # the allowlist lives in Firestore
    db = firestore.Client()
    blobs = None
    if os.environ.get("BASS_DOCS_BUCKET"):
        from firebase_admin import storage as fb_storage

        class _Blobs:
            def __init__(self, name):
                self.bucket = fb_storage.bucket(name)

            def delete(self, path):
                if not path.startswith("users/") or "/bass/" not in path:
                    raise ValueError("not a Bass Documents path")
                self.bucket.blob(path).delete()
        blobs = _Blobs(os.environ["BASS_DOCS_BUCKET"])
    research = None
    if os.environ.get("BASS_RESEARCH_BUCKET"):            # optional and DARK: the bucket exists, but nothing is saved until bass_research/switch {enabled: true}
        from google.cloud import storage as gcs

        from gcs_object_store import CreateOnly
        from alto.bass.research_share import ResearchShare
        secrets = _Secrets(project)
        hmac_name = f"projects/{project}/secrets/bass-research-hmac/versions/latest"
        research = ResearchShare(GuardStore(db), CreateOnly(gcs.Client().bucket(os.environ["BASS_RESEARCH_BUCKET"])),
                                 lambda: secrets.c.access_secret_version(name=hmac_name, timeout=10).payload.data.decode("utf-8"),   # 10 s, not the function's
                                 lambda: dt.datetime.now(dt.timezone.utc))
    return Proxy(cfg, GuardStore(db), _Verifier(), _Secrets(project), ToolBox(AltoStore()),
                 clock=lambda: dt.datetime.now(dt.timezone.utc), blobs=blobs, research=research)


@_http
def bass_proxy(request):
    global _proxy
    if _proxy is None:
        _proxy = _build()
    status, headers, body = _proxy.handle_http(request.method, dict(request.headers), request.get_data())
    return body, status, headers


# -- Bass Documents erase entry points (D5 / D6). NOT DEPLOYED; IT wires them after "go" -------------------------------------------------
# bass_docs_account_deleted: a Firebase Auth "user deleted" trigger (providers/firebase.auth/eventTypes/user.delete). Erases every document of
#   that account at once (the ones in their 7-day recovery included) and the library index. The uid comes from the AUTH EVENT only.
# bass_docs_daily: an HTTP function for Cloud Scheduler, once a day, with an OIDC token (IT gives only the scheduler's service account the
#   invoker role). Erases every account's documents deleted 7+ days ago. Answers counts only.
# BASS_DOCS_BUCKET (optional): the Storage bucket of the originals; without it the originals stay, refused to everyone by storage.rules.
def _docs_env():
    import firebase_admin
    from google.cloud import firestore

    from firestore_store import FirestoreStore
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    blobs = None
    if os.environ.get("BASS_DOCS_BUCKET"):
        from firebase_admin import storage as fb_storage

        class _Blobs:
            def __init__(self, name):
                self.bucket = fb_storage.bucket(name)

            def delete(self, path):
                if not path.startswith("users/") or "/bass/" not in path:
                    raise ValueError("not a Bass Documents path")
                self.bucket.blob(path).delete()
        blobs = _Blobs(os.environ["BASS_DOCS_BUCKET"])
    return FirestoreStore(firestore.Client()), blobs


def _clock():
    return dt.datetime.now(dt.timezone.utc)


def bass_docs_account_deleted(data, context=None):
    import re

    from alto.bass import documents as D
    from alto.bass.beta_config import BetaConfig
    uid = (data or {}).get("uid") if isinstance(data, dict) else None
    if not isinstance(uid, str) or not re.match(r"^[A-Za-z0-9_-]{1,128}$", uid):
        raise ValueError("no uid in the auth event")               # an error the platform retries and logs; never a guess
    store, blobs = _docs_env()
    from alto.bass.drive import DriveService
    cfg = BetaConfig(testers=1)
    lib = D.Library(store, cfg, _clock, blobs=blobs)
    drive = DriveService(store, cfg, _clock, lib).erase_account(uid)     # first: the Drive token is revoked at Google and no record of it is left (works with Drive unconfigured)
    out = {"erased": lib.erase_account(uid), "drive": drive}
    from alto.store import erase as account_erase          # the SAME list the admin run uses (alto/store/erase.py BASS_COLLECTIONS): the credit
    db = getattr(store, "db", None)                         # the Firestore client behind the guard store
    if db is not None:
        out["records"] = account_erase.erase_bass_records(db, uid)        # ledger, metadata lines, Drive records, consent, anything left
    if os.environ.get("BASS_RESEARCH_BUCKET"):                  # opt-in sharing: ticket the tester's prefix for the purge and drop the consent record
        from google.cloud import secretmanager

        from alto.bass.research_share import ResearchShare
        sm = secretmanager.SecretManagerServiceClient()
        name = f"projects/{os.environ['GCP_PROJECT']}/secrets/bass-research-hmac/versions/latest"
        ResearchShare(store, None, lambda: sm.access_secret_version(name=name, timeout=10).payload.data.decode("utf-8"), _clock).erase_account(uid)
        out["research"] = "ticketed"
    return out


@_http
def bass_docs_daily(request):
    import json

    from alto.bass import documents as D
    from alto.bass.beta_config import BetaConfig
    if getattr(request, "method", "POST") != "POST":
        return b"POST only", 405, {"Content-Type": "text/plain"}
    store, blobs = _docs_env()
    out = D.purge_expired(store, BetaConfig(testers=1), _clock, blobs=blobs)
    return json.dumps(out).encode("utf-8"), 200, {"Content-Type": "application/json"}


# bass_research_purge_daily: an HTTP function for Cloud Scheduler (OIDC, invoker = the scheduler's service account only), once a day, run with
# the ADMIN identity (list + delete on the research bucket, nothing else). Deletes the prefix of every tester whose purge ticket is due
# (withdrawn, or account deleted, 7+ days ago) and drops the ticket. Answers counts only. NOT DEPLOYED; IT wires it after "go".
@_http
def bass_research_purge_daily(request):
    import json

    from google.cloud import storage as gcs

    from gcs_object_store import Admin
    from alto.bass.research_share import purge_due
    if getattr(request, "method", "POST") != "POST":
        return b"POST only", 405, {"Content-Type": "text/plain"}
    store, _ = _docs_env()
    out = purge_due(store, Admin(gcs.Client().bucket(os.environ["BASS_RESEARCH_BUCKET"])), _clock())
    status = 500 if out.get("failed") else 200       # a failed ticket shows as a failed Scheduler run so IT's alert fires (counts only, no content)
    return json.dumps(out).encode("utf-8"), status, {"Content-Type": "application/json"}
