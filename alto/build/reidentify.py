"""Give a copy of a timeline its own identity, so it cannot touch the original.

A shared copy and its master are the same document twice. They are served from
the same origin, and a `srcdoc` iframe inherits that origin — so unless their
identities differ they address the same `localStorage` keys and, for a signed-in
reader, the same `users/{uid}/tl/{tid}` Firestore document. The owner opening
their own share link would merge a stranger's highlights into their master, and
neither of them would ever see it happen.

So a share is re-identified: every place the page records WHICH timeline it is
(blocks.ID_PATTERNS) is rewritten to `s-{share key}`. The page is otherwise
untouched — it is the same 600 KB, not a rebuild.

This is the Python side, which the tests exercise. `alto-cloud.js` carries the
same five patterns because the Update-shared-copies button runs in the browser,
where the connector's credentials do not exist; `tests/test_share_links.py`
asserts the two agree, since two copies of this list quietly disagreeing is the
one way this can fail and still look fine.
"""
from __future__ import annotations

import re

from .blocks import ID_PATTERNS


class ReidentifyError(ValueError):
    pass


# The page states its own identity here, and nowhere else unambiguously; this
# is how a copy is read without being told what it came from.
_COURSE_ID = re.compile(r"var COURSE_ID = '([^']*)';")

# Prefix for a share's synthetic id. Lowercase alphanumeric plus the hyphen, so
# it satisfies the same component check a real timeline_id does.
SHARE_PREFIX = "s-"


def identity_of(page_html: str) -> str:
    m = _COURSE_ID.search(page_html)
    if not m:
        raise ReidentifyError("no COURSE_ID in this page — not an Alto timeline")
    return m.group(1)


def share_id(share_key: str) -> str:
    return SHARE_PREFIX + share_key


def reidentify(page_html: str, share_key: str) -> str:
    """Return `page_html` re-stamped as the share `share_key`.

    Raises if any pattern still carries the old identity afterwards: a partial
    rewrite is worse than none, because it produces a copy that shares SOME of
    the master's storage and looks entirely normal.
    """
    old = identity_of(page_html)
    new = share_id(share_key)
    if old == new:
        return page_html
    out = page_html
    for tmpl in ID_PATTERNS.values():
        out = out.replace(tmpl.format(tid=old), tmpl.format(tid=new))
    left = [n for n, t in ID_PATTERNS.items() if t.format(tid=old) in out]
    if left:
        raise ReidentifyError(f"still carrying the original identity: {left}")
    return out
