"""Hosted-serving transforms: rewrite intra-app links for the cloud origin.

Built timeline HTML keeps the 3-file-relative link shapes (index.html /
reports.html / alto-cloud.js) so the offline bundle's anchors keep working.
These functions produce the HOSTED variants served at /t/{tid}, / and
/reports. Same assert-count discipline as single_file.py.
"""
from __future__ import annotations

from .build.fingerprint import meta_tag


class HostedError(ValueError):
    pass


def _rep(html, old, new, n, label):
    c = html.count(old)
    if c != n:
        raise HostedError(f"{label}: found {c} != {n} :: {old[:60]!r}")
    return html.replace(old, new)


CLOUD_TAG = '<script type="module" src="alto-cloud.js"></script>\n'

# The one <head> that opens the document. The templates also contain the
# literal inside JS strings (a report builder, a comment), so the newline is
# what distinguishes the real one — hence the counted swap below.
_HEAD = "<head>\n"


def _stamp(html: str, label: str) -> str:
    """Record which Alto built this page, so a stale deploy is visible.

    See alto/build/fingerprint.py: without this, a page shipped from a stale
    build-time artifact is indistinguishable from a current one, which is
    exactly how an engine fix once went five weeks without reaching anybody.
    """
    return _rep(html, _HEAD, _HEAD + meta_tag() + "\n", 1, f"{label} build stamp")


def hosted_timeline(html: str, tid: str) -> str:
    """Built timeline → hosted variant (served at /t/{tid})."""
    html = _rep(html, "onclick=\"location.href='index.html'\"",
                "onclick=\"location.href='/'\"", 2, "brand home links")
    html = _rep(html, "location.href='index.html'", "location.href='/'",
                2, "mobile brand links (js)")
    html = _rep(html, f"'reports.html?course={tid}&amp;from=project'",
                f"'/reports?course={tid}&from=project'", 1, "reports button")
    html = _rep(html, CLOUD_TAG,
                f'<script type="module" src="/alto-cloud.js" data-tid="{tid}"></script>\n',
                1, "cloud tag")
    html = _stamp(html, "timeline")
    return html


def hosted_home(html: str) -> str:
    """Emitted home page → hosted variant (served at /)."""
    html = _rep(html,
                "location.href = 'reports.html?course=' + encodeURIComponent(c.courseId) + '&from=home';",
                "location.href = '/reports?course=' + encodeURIComponent(c.courseId) + '&from=home';",
                1, "home reports link")
    html = _rep(html, CLOUD_TAG,
                '<script type="module" src="/alto-cloud.js"></script>\n',
                1, "cloud tag")
    html = _rep(html, "'index.html?project='", "'/?project='", 1, "project share link")
    html = _stamp(html, "home")
    return html


def hosted_reports(html: str) -> str:
    """Emitted reports page → hosted variant (served at /reports)."""
    html = _rep(html, "onclick=\"location.href='index.html'\"",
                "onclick=\"location.href='/'\"", 2, "brand home links")
    # "← Home". The page is served from /reports/, where a relative index.html
    # is /reports/index.html — this page again, minus its ?course. The link
    # looked dead, or quietly switched to the default timeline.
    html = _rep(html, '<a id="home-link" href="index.html">',
                '<a id="home-link" href="/">', 1, "reports home link")
    html = _rep(html, "back.href = 'index.html';", "back.href = '/';",
                1, "reports home link (js)")
    html = _rep(html, CLOUD_TAG,
                '<script type="module" src="/alto-cloud.js"></script>\n',
                1, "cloud tag")
    html = _stamp(html, "reports")
    return html
