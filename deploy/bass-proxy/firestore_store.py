"""Firestore adapter for the beta guards (the store interface in alto/bass/beta_store.py): get, put, run_transaction.
Run against the Firestore EMULATOR in CI (.github/workflows/security.yml, tests/security/bass_money_emulator_check.py: the B1 money paths
on the real google-cloud-firestore client); not yet against a real project (it needs Blaze). The guards are also tested against FakeStore,
which has the same interface, and this adapter's retry mapping with a stand-in for the google libraries. IT reviews it.
Keys map to documents:
    <uid>                      -> bass_credits/<uid>
    bass_beta/kill|allowlist|live_go|disabled -> bass_beta/<name>
    bass_beta/day/<YYYY-MM-DD> -> bass_beta_days/<YYYY-MM-DD>
    bass_beta/pc/<period id>   -> bass_beta_period_counters/<period id>   (the period's spend + reservation index)
    bass_beta/periods/<id>     -> bass_beta_periods/<id>                  ({confirmed: true}, written by IT only)
    terms_acceptance/<uid>_<v> -> terms_acceptance/<uid>_<v>              (the Beta Terms record the page writes; READ ONLY here)
    bass_beta/meta/<uid>_<day> -> bass_beta_meta/<uid>_<day>               (metadata log lines per tester per day; tools/bass_beta_report.py)
    bass_docs/<uid>            -> bass_docs/<uid>                         (the Documents index; server only: no client rule matches it)
    bass_doc_text/<uid>_<fid>  -> bass_doc_text/<uid>_<fid>               (one document's extracted text; server only)
    bass_research/switch       -> bass_research/switch                    (opt-in sharing kill switch {enabled}; absent = OFF; IT sets it)
    bass_research_consent/<uid>-> bass_research_consent/<uid>             (the opt-in record; written by the proxy only; server only)
    bass_research_purge/<pseudonym> -> bass_research_purge/<pseudonym>    (a purge ticket; names no one; server only)
    bass_drive/<uid>           -> bass_drive/<uid>                        (Add from Drive: the short-lived token record; server only)
    bass_drive_tok/<sha256>    -> bass_drive_tok/<sha256>                 (which uid registered a token; server only)
Any other key with a slash in it is REFUSED (StoreError): nothing falls through to bass_credits with a bad document id (finding B2).
Transactions: fn works on alto.bass.beta_store.DeferredWrites, so Firestore sees every read before the first write (finding B1).
"""
from __future__ import annotations

from alto.bass.beta_store import ConflictError, StoreError, check_size, reads_first


def _path(key: str) -> tuple:
    if key.startswith("bass_beta/day/"):
        return "bass_beta_days", key.rsplit("/", 1)[1]
    if key.startswith("bass_beta/pc/"):
        return "bass_beta_period_counters", key.rsplit("/", 1)[1]
    if key.startswith("bass_beta/meta/"):
        return "bass_beta_meta", key.rsplit("/", 1)[1]
    if key.startswith("bass_beta/periods/"):
        return "bass_beta_periods", key.rsplit("/", 1)[1]
    if key.startswith("terms_acceptance/"):
        return "terms_acceptance", key.split("/", 1)[1]
    if key.startswith(("bass_research/", "bass_research_consent/", "bass_research_purge/")):
        coll, doc = key.split("/", 1)
        if not doc or "/" in doc:
            raise StoreError("bad key")
        return coll, doc
    if key.startswith(("bass_docs/", "bass_doc_text/", "bass_drive/", "bass_drive_tok/")):
        coll, doc = key.split("/", 1)
        if not doc or "/" in doc:
            raise StoreError("bad key")
        return coll, doc
    if key.startswith("bass_beta/"):
        return "bass_beta", key.split("/", 1)[1]
    if not key or "/" in key:
        raise StoreError("bad key")                       # an unmapped collection never lands in bass_credits under a broken id
    return "bass_credits", key


# Firestore refuses an array directly inside an array ("Cannot convert an array value in an array value"). The ledger keeps one: the
# period counter's spend_log, [[t, mc], ...]. Found by the Firestore EMULATOR (tests/security/bass_money_emulator_check.py, 11 Nov): on a
# real Firestore every settle failed, settle_failed tripped the kill switch, and Bass stopped for everyone after the first call. FakeStore
# and the StrictFirestore stand-in accept nested lists, so the guards never saw it. The adapter now stores an inner array as a one-key map
# {NESTED: [...]} and turns it back on every read: the guards' documents are unchanged, and no stored document ever had a nested array
# (every such write was refused), so there is nothing to migrate.
NESTED = "alto_array_v1"                # (Firestore reserves field names that start and end with __)


def _enc(v, in_array: bool = False):
    if isinstance(v, dict):
        return {k: _enc(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        items = [_enc(x, True) for x in v]
        return {NESTED: items} if in_array else items
    return v


def _dec(v):
    if isinstance(v, dict):
        if len(v) == 1 and NESTED in v and isinstance(v[NESTED], list):
            return [_dec(x) for x in v[NESTED]]
        return {k: _dec(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_dec(x) for x in v]
    return v


def is_retries_exhausted(exc: BaseException) -> bool:
    """google-cloud-firestore's @transactional retries Aborted itself and, when it runs out of attempts, raises a plain ValueError
    ("Failed to commit transaction in N attempts."). That is a lost race, not a bug in the guards. Any other ValueError is not."""
    m = str(exc).lower()
    return isinstance(exc, ValueError) and "transaction" in m and ("attempt" in m or "commit" in m or "rollback" in m)


class _Txn:
    """The RAW Firestore transaction. It is only ever driven through DeferredWrites (run_transaction below), so its puts and deletes all
    arrive after its last get."""

    def __init__(self, store, txn):
        self._s, self._t = store, txn

    def get(self, key):
        snap = self._s._ref(key).get(transaction=self._t)
        return _dec(snap.to_dict()) if snap.exists else None

    def put(self, key, doc):
        check_size(doc)                                   # over Firestore's 1 MiB: a StoreError here, before the commit, never a silent loss
        self._t.set(self._s._ref(key), _enc(doc))

    def delete(self, key):
        self._t.delete(self._s._ref(key))


class FirestoreStore:
    def __init__(self, db):
        self.db = db

    def _ref(self, key):
        coll, doc = _path(key)
        return self.db.collection(coll).document(doc)

    def get(self, key):
        try:
            snap = self._ref(key).get()
            return _dec(snap.to_dict()) if snap.exists else None
        except Exception as e:
            raise StoreError(type(e).__name__) from e

    def scan(self, prefix):
        """(key, doc) for every document under a key prefix that names a whole collection: "bass_beta/day/", "bass_beta/meta/", "" (the
        account ledgers, bass_credits), "bass_docs/" (the Documents indexes). Used by tools/bass_beta_report.py (read only) and the Documents
        daily erase job (alto/bass/documents.py purge_expired); never by the proxy's request path."""
        coll = {"bass_beta/day/": "bass_beta_days", "bass_beta/meta/": "bass_beta_meta", "": "bass_credits",
                "bass_docs/": "bass_docs", "bass_research_purge/": "bass_research_purge"}[prefix]
        try:
            for snap in self.db.collection(coll).stream():
                yield prefix + snap.id, _dec(snap.to_dict())
        except Exception as e:
            raise StoreError(type(e).__name__) from e

    def put(self, key, doc):
        check_size(doc)
        try:
            self._ref(key).set(_enc(doc))
        except Exception as e:
            raise StoreError(type(e).__name__) from e

    def run_transaction(self, fn, retries: int = 5):
        from google.api_core import exceptions as gexc
        from google.cloud import firestore

        @firestore.transactional
        def run(txn):
            return reads_first(fn)(_Txn(self, txn))

        try:
            return run(self.db.transaction(max_attempts=max(1, retries)))      # the decorator does the retrying; this sets how many
        except (gexc.Aborted, gexc.Conflict) as e:
            raise ConflictError(type(e).__name__) from e
        except ValueError as e:
            if is_retries_exhausted(e):
                raise ConflictError("the transaction kept conflicting") from e
            raise                                                  # a ValueError from the guards' own code is not a store problem
        except StoreError:
            raise
        except Exception as e:
            if type(e).__module__.startswith(("google", "grpc")):
                raise StoreError(type(e).__name__) from e
            raise                                                  # a BassError from the guards passes through untouched
