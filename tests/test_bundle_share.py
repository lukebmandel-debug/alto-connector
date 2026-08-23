"""Share in the offline bundle — two defects the bundling itself introduced.

Both only ever showed up in the single-file bundle, never on a published site,
because both come from how the bundle frames its pages:

  1. every page runs inside a `srcdoc` iframe, where `location.href` is
     "about:srcdoc" — an invalid base, so `new URL(path, location.href)` threw.
     `altoShareLink` is async, so the throw became an unhandled rejection and
     the click did nothing at all: no toast, no copy, no visible error.
  2. the bundle's link shim listens on `document` in the CAPTURE phase, so it
     ran before the share button's own handler and navigated to the timeline
     instead — the button's `preventDefault()` never got a turn.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.single_file import bundle, SHIM  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _bundle():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    brief, nodes, conns = load_brief(d)
    html, _ = build_timeline(brief, nodes, conns)
    return bundle(brief, html)


def test_share_does_not_base_a_url_on_srcdoc():
    """The throwing construct must be gone from the bundled page."""
    assert "new URL(path, location.href)" not in _bundle()


def test_share_falls_back_to_the_containing_document():
    offline = _bundle()
    # resolves against the document that holds the bundle, not the frame
    assert "window.parent.location.href" in offline
    # ...and only when that is a real web address
    assert "/^https?:/i.test(top" in offline


def test_share_says_something_when_there_is_no_url_to_share():
    """A local file has no shareable address. Saying so is the fix; failing
    silently was the bug."""
    assert "Offline copy" in _bundle()


def test_link_shim_steps_aside_for_buttons():
    """Capture phase is what makes the shim a reliable router and what made it
    eat the share click. It has to skip controls that handle themselves."""
    assert "closest('button')" in SHIM
    # the guard must precede the anchor lookup, or the shim still wins
    assert SHIM.index("closest('button')") < SHIM.index("closest('a[href]')")
    # and it reaches the emitted page (the shim is embedded per-document, so it
    # appears once per framed page rather than once overall)
    offline = _bundle()
    assert offline.count("t.closest('button'))return") >= 2


def test_shim_still_routes_ordinary_links():
    """The guard must not disarm the router itself."""
    for page in ("index", "terrarium_glass", "reports"):
        assert page in SHIM
    assert "window.__altoGo(h)" in SHIM
