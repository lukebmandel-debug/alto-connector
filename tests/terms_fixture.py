"""A fake signed-in user's acceptance of the CURRENT beta terms (alto/legal/VERSION), as the sign-in gate in alto-cloud.js reads it:
terms_acceptance/<uid>_<version>. Tests whose fake Firestore signs a user in seed their docs with this, so the "new terms" dialog stays out of
the way; the tests that prove the dialog (tests/test_legal.py) do not."""
from pathlib import Path

VERSION = (Path(__file__).resolve().parent.parent / "alto" / "legal" / "VERSION").read_text(encoding="utf-8").strip()


def terms_doc(uid):
    """{doc path: data} for one signed-in uid, to merge into a fake Firestore's documents."""
    return {f"terms_acceptance/{uid}_{VERSION}": {"uid": uid, "version": VERSION, "ageConfirmed": True}}


def real_cloud_js(source):
    """alto-cloud.js as the site serves it: the terms version spliced in (emit_cloud_js does this; tests that read the raw source file need it too)."""
    return source.replace("__ALTO_TERMS_V__", VERSION)
