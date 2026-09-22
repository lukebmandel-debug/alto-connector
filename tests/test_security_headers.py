"""The published site's CSP must still let Google sign-in run.

signInWithPopup injects Google's gapi loader from apis.google.com. A CSP that
allows only gstatic (the Firebase SDK) blocks it, and sign-in — and with it all
cross-device sync of highlights, notes and reports — silently does nothing on
every published page.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.publish_static import _security_headers  # noqa: E402


def _csp(headers):
    return next(h["value"] for h in headers[0]["headers"]
                if h["key"] == "Content-Security-Policy")


def _script_src(csp):
    return next(d for d in csp.split("; ") if d.startswith("script-src"))


def test_published_csp_allows_the_google_sign_in_loader():
    src = _script_src(_csp(_security_headers()))
    assert "https://www.gstatic.com" in src      # Firebase SDK
    assert "https://apis.google.com" in src      # gapi, for signInWithPopup


def test_html_and_js_are_revalidated_on_every_load():
    """Firebase Hosting defaults to max-age=3600 and deploy_site regenerates
    firebase.json each publish, so without this a deploy silently takes up to
    an hour to reach anyone who has already visited — including the publisher
    checking their own work."""
    from alto.publish_static import _security_headers
    rules = _security_headers()
    cache = [r for r in rules
             if any(h["key"] == "Cache-Control" for h in r["headers"])]
    assert cache, "nothing sets Cache-Control; Firebase will cache for an hour"
    # "**", not a .html glob: Hosting matches the REQUEST path, and a page
    # served as a directory index (/t/{slug}/, /pv/{key}/) has no .html in it.
    assert cache[0]["source"] == "**"
    val = next(h["value"] for h in cache[0]["headers"] if h["key"] == "Cache-Control")
    assert val == "no-cache"
