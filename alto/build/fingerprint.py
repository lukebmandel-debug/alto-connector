"""A short digest of everything that determines what an emitted page looks like.

Published pages used to carry no evidence of which Alto built them. That made
one class of failure invisible from outside: `regenerate_site` shipped stored
build-time artifacts, so an engine fix reached only the timelines someone
happened to rebuild, and the fit-to-window work sat unshipped for five weeks
while `curl` showed a perfectly healthy site. Nobody could have spotted it,
because a stale page and a current one are indistinguishable by inspection.

So every hosted page now carries `<meta name="alto-build">`, and
`publish_static.verify_live()` fetches the deployed pages and compares. The
question "is what is online the Alto we built?" becomes answerable rather than
assumed.

The digest covers the three runtime templates AND the code that renders them —
a change in `blocks.py` alters the output just as surely as a change in
`timeline_template.html`, and a fingerprint that missed it would certify a
stale page as current.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..engine import RUNTIME_TEMPLATES, engine_dir

_PKG = Path(__file__).resolve().parent.parent      # alto/

# Kept short: this is a cache-busting/equality token, not a security property.
# 12 hex characters is 48 bits, far past any accidental collision across the
# handful of builds a site ever sees.
DIGEST_CHARS = 12

META_NAME = "alto-build"


def _sources() -> list[tuple[str, bytes]]:
    """(label, bytes) for every input that can change an emitted page.

    Sorted and labelled so the digest is stable across machines and filesystem
    ordering — an unstable fingerprint would fail parity on every publish and
    teach everyone to ignore it.
    """
    out: list[tuple[str, bytes]] = []
    eng = engine_dir()
    for name in sorted(RUNTIME_TEMPLATES):
        out.append((f"engine/{name}", (eng / name).read_bytes()))
    for p in sorted((_PKG / "build").glob("*.py")):
        out.append((f"build/{p.name}", p.read_bytes()))
    for rel in ("hosted.py", "cloud/alto-cloud.js"):
        p = _PKG / rel
        if p.exists():
            out.append((rel, p.read_bytes()))
    return out


# The build files that decide what a TIMELINE document contains. Deliberately
# narrower than _sources(): a private page is stamped with this one, and it is
# the only page on the site that a publish cannot refresh — its owner has to
# re-upload it by hand. Stamping it with the whole-build digest meant a change
# to the reports page or the homepage flagged every private timeline as stale,
# and a warning that cries wolf is one people learn to dismiss.
_TIMELINE_SOURCES = (
    "blocks.py", "brief.py", "builder.py", "emit.py", "engine_patches.py",
    "estimate.py", "layout.py", "sanitize.py", "single_file.py", "verify.py",
)


def page_fingerprint() -> str:
    """The digest for a built timeline page — see _TIMELINE_SOURCES."""
    h = hashlib.sha256()
    for label, data in _sources():
        if not (label == "engine/timeline_template.html"
                or (label.startswith("build/")
                    and label[len("build/"):] in _TIMELINE_SOURCES)):
            continue
        h.update(f"{label}:{len(data)}\n".encode())
        h.update(data)
    return h.hexdigest()[:DIGEST_CHARS]


def build_fingerprint() -> str:
    """The digest embedded in every hosted page."""
    h = hashlib.sha256()
    for label, data in _sources():
        # Length-prefixed, so no rename can produce the same stream as an edit.
        h.update(f"{label}:{len(data)}\n".encode())
        h.update(data)
    return h.hexdigest()[:DIGEST_CHARS]


def meta_tag(digest: str = "") -> str:
    return f'<meta name="{META_NAME}" content="{digest or build_fingerprint()}">'


def page_meta_tag() -> str:
    """The stamp a built timeline page carries."""
    return f'<meta name="{META_NAME}" content="{page_fingerprint()}">'
