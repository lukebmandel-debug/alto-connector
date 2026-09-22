"""Offline copies: the multi-timeline bundle and the homepage buttons that fetch it.

A bundle is one file holding N timelines behind a srcdoc router. The things that
can break silently are the router key scheme (a key the regex cannot match just
falls through to the homepage) and the reports exclusion (a dropped _rep leaves
an anchor pointing at a document that is no longer there).
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.single_file import bundle, bundle_many, SHIM  # noqa: E402
from alto.engine import template as engine_template  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"

def _doc(bundle_html, key):
    """Pull one embedded document back out of __DOCS."""
    m = re.search(key + r':("(?:[^"\\]|\\.)*")', bundle_html)
    assert m, f"no {key} document in the bundle"
    return json.loads(m.group(1))


@pytest.fixture(scope="module")
def built():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    html, _ = build_timeline(brief, nodes, conns)
    return brief, html


def _keys(bundle_html):
    return json.loads(re.search(r"var __KEY=(\{.*?\});", bundle_html).group(1))


def test_single_bundle_keys_its_one_timeline(built):
    brief, html = built
    out = bundle(brief, html)
    assert _keys(out) == {"t_0.html": "t_0", "index.html": "home"}


def test_multi_bundle_keys_every_timeline(built):
    brief, html = built
    out = bundle_many([{"name": "A", "items": [(brief, html)]},
                       {"name": "B", "items": [(brief, html), (brief, html)]}],
                      title="All")
    assert _keys(out) == {"t_0.html": "t_0", "t_1.html": "t_1",
                          "t_2.html": "t_2", "index.html": "home"}


def test_router_regex_accepts_digits(built):
    """t_0.html must match. The original [a-z_]+ silently did not, which sends
    every chip click to the homepage instead of its timeline."""
    brief, html = built
    out = bundle_many([{"name": "A", "items": [(brief, html)]}], title="A")
    assert "[a-z0-9_]+" in out, "router character class cannot match t_0.html"


def test_shim_routes_bundled_timeline_hrefs():
    """The chip anchors are t_<n>.html; if the shim does not claim them the
    click escapes the bundle and 404s."""
    assert "t_\\d+" in SHIM


def test_every_home_href_is_routable(built):
    """Each PROJECTS href must resolve to a key the router actually holds."""
    brief, html = built
    out = bundle_many([{"name": "A", "items": [(brief, html)]},
                       {"name": "B", "items": [(brief, html)]}], title="All")
    keys = _keys(out)
    hrefs = re.findall(r'href:"([^"]+)"', _doc(out, "home"))
    assert hrefs, "no course hrefs found in the bundled homepage"
    for h in hrefs:
        assert h in keys, f"href {h!r} has no router key"


def test_bundle_carries_no_reports(built):
    brief, html = built
    out = bundle(brief, html)
    docs = out.split("var __DOCS={", 1)[1][:400]
    assert "reports:" not in docs
    assert _keys(out).get("reports.html") is None
    # ...and the timeline's own button for it is hidden, not left pointing at a
    # document the bundle no longer carries.
    tl = _doc(out, "t_0")
    # the anchor itself, not the incidental mentions in comments/auto-save code
    assert "onclick=\"__altoGo('reports.html" not in tl
    assert "onclick=\"location.href='reports.html" not in tl
    assert 'style="display:none" onclick="return false"' in tl


def test_bundle_has_no_external_resources(built):
    """Nothing may be fetched at open time — the file has to work with the
    network off. Embedded documents are JSON strings (with < escaped), so the
    only real tags in the bundle are the shell's own."""
    brief, html = built
    out = bundle(brief, html)
    assert re.findall(r"<script[^>]*\ssrc=", out) == []
    assert re.findall(r"<link[^>]*\shref=", out) == []
    assert "gstatic.com" not in out
    assert "@font-face" not in out
    # the one remaining absolute URL is a dead code path, not a load
    assert "firestore.googleapis.com" not in _doc(out, "home")


def test_bundle_many_refuses_an_empty_set():
    from alto.build.single_file import BundleError
    with pytest.raises(BundleError):
        bundle_many([], title="x")
    with pytest.raises(BundleError):
        bundle_many([{"name": "A", "items": []}], title="x")


# ── the homepage side ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def home_src():
    return engine_template("home_template.html")


def test_homepage_has_all_three_download_buttons(home_src):
    for cls in ("tile-download", "slab-download", "download-all"):
        assert cls in home_src, cls


def test_download_controls_are_buttons(home_src):
    """The bundle's link shim only steps aside for <button>. An <a download>
    inside a course tile gets eaten by the capture-phase router."""
    assert "createElement('button')" in home_src
    assert "<a download" not in home_src
    assert 'id="download-all"' in home_src
    assert re.search(r"<button id=\"download-all\"", home_src)


def test_download_is_desktop_only(home_src):
    """No offline copies on a phone — it has nowhere to put the file."""
    m = re.search(r"@media \(max-width:640px\)\{\s*\.tile-download[^}]*\}", home_src)
    assert m, "no mobile rule hiding the download controls"
    assert "display:none" in m.group(0)


def test_download_is_suppressed_off_the_web(home_src):
    """Inside a bundle every page runs from about:srcdoc, where these fetches
    can only 404 — so the buttons must not be drawn there at all."""
    assert "const DL_OK = /^https?:$/.test(location.protocol);" in home_src
    assert "if(live && c.courseId && DL_OK)" in home_src


def test_seed_only_fills_empty_keys(home_src):
    """Re-opening a seeded copy must not clobber notes made inside it."""
    assert "if(!localStorage.getItem(k))localStorage.setItem(k,S[k])" in home_src


def test_download_buttons_are_not_printed(home_src):
    m = re.search(r"@media print\{.*?\}\s*\n", home_src, re.S)
    assert ".tile-download, .slab-download" in home_src
    assert "#download-all, #dl-scrim{ display:none !important; }" in home_src
