"""Every hosted page says which Alto built it, and publish checks the web agrees.

The failure this guards against is the quietest one Alto has had: for five
weeks `regenerate_site` shipped stored build-time artifacts, so an engine fix
reached only the timelines somebody happened to rebuild. Nothing looked wrong.
The deploy succeeded, curl returned a healthy page, and the page was a month
old. A stale page and a current one were indistinguishable from outside — so
the fix is to make them distinguishable.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief          # noqa: E402
from alto.build.fingerprint import (                               # noqa: E402
    META_NAME, _sources, build_fingerprint, meta_tag)
from alto.build.pages import build_home, build_reports             # noqa: E402
from alto.build.private_shell import shell                         # noqa: E402
from alto.hosted import hosted_home, hosted_reports, hosted_timeline  # noqa: E402
from alto.publish_static import live_pages, verify_live            # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
STAMP = re.compile(r'<meta name="%s" content="([0-9a-f]{12})">' % META_NAME)


@pytest.fixture(scope="module")
def built():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    b, nodes, conns = load_brief(d)
    html, _ = build_timeline(b, nodes, conns)
    return b, html


# ── the digest ──────────────────────────────────────────────────────────────

def test_the_digest_is_stable():
    """An unstable fingerprint fails parity on every publish, and a check that
    always fails is a check everyone learns to skip."""
    assert build_fingerprint() == build_fingerprint()
    assert re.fullmatch(r"[0-9a-f]{12}", build_fingerprint())


def test_the_digest_covers_the_code_as_well_as_the_templates():
    """blocks.py decides what a page contains just as much as the template
    does. A fingerprint over templates alone would certify a page built by
    superseded code as current — the precise failure it exists to catch."""
    labels = {label for label, _ in _sources()}
    for needed in ("engine/timeline_template.html", "engine/home_template.html",
                   "engine/reports_template.html", "build/blocks.py",
                   "build/emit.py", "build/pages.py", "hosted.py",
                   "cloud/alto-cloud.js"):
        assert needed in labels, f"{needed} is not in the fingerprint"


def test_editing_any_source_moves_the_digest(monkeypatch):
    real = _sources()
    monkeypatch.setattr("alto.build.fingerprint._sources",
                        lambda: real[:-1] + [(real[-1][0], real[-1][1] + b"x")])
    assert build_fingerprint() != real and build_fingerprint()


def test_a_rename_cannot_impersonate_an_edit(monkeypatch):
    """The stream is length-prefixed per file, so concatenation is unambiguous."""
    monkeypatch.setattr("alto.build.fingerprint._sources",
                        lambda: [("a", b"xy"), ("b", b"z")])
    one = build_fingerprint()
    monkeypatch.setattr("alto.build.fingerprint._sources",
                        lambda: [("a", b"x"), ("b", b"yz")])
    assert build_fingerprint() != one


# ── every hosted page carries it ────────────────────────────────────────────

def test_every_hosted_page_is_stamped(built):
    b, html = built
    pages = {
        "timeline": hosted_timeline(html, b.timeline_id),
        "home": hosted_home(build_home([])),
        "reports": hosted_reports(build_reports([], "")),
        "private shell": shell(),
    }
    want = build_fingerprint()
    for name, page in pages.items():
        m = STAMP.search(page)
        assert m, f"{name} carries no build stamp"
        assert m.group(1) == want, f"{name} stamped {m.group(1)}, not {want}"


def test_the_stamp_is_in_the_real_head_not_a_script_string(built):
    """The templates contain the literal '<head>' inside JS strings too — a
    report builder and a comment. Stamping one of those would put the meta tag
    somewhere no browser and no fetch would ever see it."""
    b, html = built
    page = hosted_timeline(html, b.timeline_id)
    assert page.count(meta_tag()) == 1
    head = page[:page.index("</head>")]
    assert meta_tag() in head, "stamp landed outside the document head"


# ── the live check ──────────────────────────────────────────────────────────

def _site(tmp_path, *, stamp=True, pages=("t/abc", "pv/xyz")):
    site = tmp_path / "site"
    (site / "reports").mkdir(parents=True)
    body = f"<html><head>\n{meta_tag() if stamp else ''}\n</head></html>"
    (site / "index.html").write_text(body, encoding="utf-8")
    (site / "reports" / "index.html").write_text(body, encoding="utf-8")
    for rel in pages:
        d = site / rel
        d.mkdir(parents=True)
        (d / "index.html").write_text(body, encoding="utf-8")
    return site


def test_live_pages_lists_every_deployed_page(tmp_path):
    site = _site(tmp_path)
    assert live_pages(site) == ["/", "/reports/", "/t/abc/", "/pv/xyz/"]


def test_a_directory_without_an_index_is_not_a_page(tmp_path):
    site = _site(tmp_path)
    (site / "t" / "leftover").mkdir()
    assert "/t/leftover/" not in live_pages(site)


def _serve(monkeypatch, body_for):
    class R:
        def __init__(self, body): self._b = body.encode()
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=0):
        return R(body_for(req.full_url))
    monkeypatch.setattr("alto.publish_static.urllib.request.urlopen", fake)


def test_a_matching_site_reports_nothing(tmp_path, monkeypatch):
    site = _site(tmp_path)
    _serve(monkeypatch, lambda url: f"<head>\n{meta_tag()}\n")
    assert verify_live(site, "https://example.web.app") == []


def test_a_page_serving_an_older_build_is_named(tmp_path, monkeypatch):
    """The CDN edge case: the deploy succeeds and one page keeps serving the
    version before it."""
    site = _site(tmp_path)
    old = f'<meta name="{META_NAME}" content="000000000000">'
    _serve(monkeypatch,
           lambda url: old if url.endswith("/t/abc/") else meta_tag())
    problems = verify_live(site, "https://example.web.app")
    assert len(problems) == 1
    assert "/t/abc/" in problems[0] and "000000000000" in problems[0]


def test_a_page_with_no_stamp_at_all_is_named(tmp_path, monkeypatch):
    """Everything published before this feature. It is still stale, and saying
    'no stamp' rather than 'fine' is the difference that matters."""
    site = _site(tmp_path, pages=())
    _serve(monkeypatch, lambda url: "<html><head>nothing here</head></html>")
    problems = verify_live(site, "https://example.web.app")
    assert len(problems) == 2
    assert all("no alto-build stamp" in p for p in problems)


def test_an_unreachable_page_is_a_problem_not_a_pass(tmp_path, monkeypatch):
    """Treating a failed fetch as success would make the check pass hardest
    exactly when the site is broken."""
    site = _site(tmp_path, pages=())

    def boom(req, timeout=0):
        raise OSError("connection reset")
    monkeypatch.setattr("alto.publish_static.urllib.request.urlopen", boom)
    problems = verify_live(site, "https://example.web.app")
    assert len(problems) == 2
    assert all("could not be fetched" in p for p in problems)
