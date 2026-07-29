"""Firebase ID-token verification for the web session."""
from __future__ import annotations

_app = None


def verify_id_token(id_token: str) -> str:
    global _app
    import firebase_admin
    from firebase_admin import auth
    if _app is None:
        _app = firebase_admin.initialize_app()
    return auth.verify_id_token(id_token)["uid"]
