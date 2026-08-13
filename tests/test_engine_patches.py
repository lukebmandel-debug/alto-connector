"""Recorded engine patches: applied to every build, and loud when stale."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_from_file  # noqa: E402
from alto.build.engine_patches import PATCHES, PatchError, apply_patches  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def test_patches_apply_to_every_build():
    html, _ = build_from_file(str(SAMPLE))
    # merge-flag overshoot: the overlay is clamped to the straight run, so the
    # un-inset corner-centre coordinates must no longer reach the path data.
    assert "_mfAtCorner" in html
    assert "'M ' + mergedRide.x1 + ' '" not in html


def test_stale_anchor_fails_loudly():
    """An engine refresh that moves an anchor must break the build, not
    silently ship a page missing the fix."""
    with pytest.raises(PatchError, match="matched 0 times"):
        apply_patches("<html>an engine this patch knows nothing about</html>")


def test_every_patch_is_anchored_once_and_changes_something():
    html, _ = build_from_file(str(SAMPLE))
    for p in PATCHES:
        assert p["old"] != p["new"], f"patch {p['name']} is a no-op"
        assert html.count(p["new"]) == p["count"], \
            f"patch {p['name']} not present in the emitted page"
