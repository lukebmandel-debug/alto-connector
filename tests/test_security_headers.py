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


def _directive(csp, name):
    return next(d for d in csp.split("; ") if d.split(" ")[0] == name)


def test_sign_in_frames_may_come_from_the_site_itself():
    """authDomain may be the site itself (<site>.web.app), whose /__/auth/
    iframe the popup flow needs; without 'self' that frame is blocked."""
    assert _directive(_csp(_security_headers()), "frame-src").split(" ")[1:] == \
        ["'self'", "https://*.firebaseapp.com"]


def test_the_rest_of_the_policy_stays_as_strict():
    csp = _csp(_security_headers())
    assert _directive(csp, "default-src") == "default-src 'self'"
    assert _directive(csp, "object-src") == "object-src 'none'"
    assert _directive(csp, "base-uri") == "base-uri 'self'"
    assert _directive(csp, "form-action") == "form-action 'none'"
    assert _directive(csp, "frame-ancestors") == "frame-ancestors 'none'"
    assert "'unsafe-eval'" not in csp and " * " not in csp + " "
    assert "data:" not in _directive(csp, "frame-src")


def test_a_sandboxed_share_can_fetch_the_hosted_palace_files():
    """A shared page runs in an opaque origin, so fetch and crossOrigin images need the header on every hashed file a palace reads."""
    from alto import publish_static as ps
    any_origin = {"key": "Access-Control-Allow-Origin", "value": "*"}
    rules = (ps._cmap_rules(["b-0123456789ab.json", "t-0123456789.json"]) + ps._bldg_rules(["plan-0123456789ab.json"]))
    assert rules and all(any_origin in r["headers"] for r in rules)
    world = [r for r in ps._security_headers(None) if r.get("source") == "/world/**"]
    assert world and any_origin in world[0]["headers"]
    retro = [r for r in ps._security_headers(None) if r.get("source") == "/retro/**"]
    assert retro and any_origin not in retro[0]["headers"]


# ── the site's own origin beside 'self' (WebKit does not match 'self' in a sandboxed, opaque-origin frame) ─────────────────────────────
_FETCH_DIRECTIVES = ("script-src", "style-src", "img-src", "font-src", "connect-src")


def test_the_sites_own_origin_is_named_once_in_every_fetch_directive_that_has_self():
    import alto.publish_static as ps
    csp = _csp(ps._security_headers(None, "luke-alto"))
    for name in _FETCH_DIRECTIVES:
        toks = _directive(csp, name).split(" ")[1:]
        assert "'self'" in toks and toks.count("https://luke-alto.web.app") == 1, name


def test_without_a_site_the_policy_is_byte_for_byte_what_it_was():
    import alto.publish_static as ps
    assert _csp(ps._security_headers(None)) == _csp(ps._security_headers(None, None)) == ps._csp("'none'")
    assert "web.app" not in _csp(ps._security_headers(None))


def test_a_bad_site_name_adds_nothing():
    import alto.publish_static as ps
    base = _csp(ps._security_headers(None))
    for bad in ("", "Luke-Alto", "x.evil.com", "a b", "luke-alto.web.app/x", "ab", "-lead", "a;script-src *", "luke-alto\nfoo", "luke-alto\n"):
        assert _csp(ps._security_headers(None, bad)) == base, repr(bad)


def test_naming_the_origin_opens_nothing_else():
    import alto.publish_static as ps
    csp = _csp(ps._security_headers(None, "alto-timelines"))
    plain = _csp(ps._security_headers(None))
    assert csp.replace(" https://alto-timelines.web.app", "") == plain         # the ONLY difference is that origin, five times
    assert csp.count("https://alto-timelines.web.app") == len(_FETCH_DIRECTIVES)
    assert "*" not in _directive(csp, "script-src").replace("https://*.", "")
    assert _directive(csp, "frame-ancestors") == "frame-ancestors 'none'"
    assert _directive(csp, "object-src") == "object-src 'none'"
    assert _directive(csp, "form-action") == "form-action 'none'"
