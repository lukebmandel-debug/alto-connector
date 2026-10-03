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


def test_section_header_chip_fits_its_name():
    """The name chip used to be a fixed 208px box, so a long unit name wrapped
    to four lines and spilled out of it. It is fitted now, and its ink is
    contrast-adjusted rather than the raw unit colour on unit-coloured glass."""
    html, _ = build_from_file(str(SAMPLE))
    assert "_altoFitUnitChip(lbl)" in html
    assert "max-width:208px" not in html
    assert "_altoUnitInk(lbl,pm.colorRaw)" in html
    assert "lbl.style.color=pm.colorRaw" not in html


# ── connector corners fit the runs they turn on ──────────────────────────────
# A card a little off its parent's x (a band shifted to stay inside the page
# margin) made the router draw two 20px arcs on a 20px jog: the path ran to the
# target's x and then back. Held here by running the page's own code in node.

import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")


def _node(js: str) -> str:
    return subprocess.check_output([NODE, "-e", js], timeout=60).decode().strip()


def _drawn_xs(d: str) -> list:
    """The x of every point a path visits, in order."""
    nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
    pts = []
    i = 0
    for cmd in re.findall(r"[MLQ]", d):
        n = 2 if cmd in "ML" else 4
        pts.append((nums[i + n - 2], nums[i + n - 1]))
        i += n
    return pts


@needs_node
def test_a_short_jog_is_drawn_without_doubling_back():
    html, _ = build_from_file(str(SAMPLE))
    src = html[html.index("function orthPath(pts, r){"):]
    src = src[:src.index("        return d;\n      }\n") + len("        return d;\n      }\n")]
    for jog in (20, 12, 6, 40, 90):
        d = _node(src + "console.log(orthPath([{x:650,y:0},{x:650,y:100},"
                  f"{{x:{650 + jog},y:100}},{{x:{650 + jog},y:200}}], 20));")
        xs = [p[0] for p in _drawn_xs(d)]
        # x only ever moves toward the target: never past it, never back
        assert xs == sorted(xs), (jog, d)
        assert max(xs) == 650 + jog, (jog, d)
    # the usual wide elbow is unchanged: full 20px arcs
    d = _node(src + "console.log(orthPath([{x:100,y:0},{x:100,y:100},{x:400,y:100},{x:400,y:200}], 20));")
    assert d == "M 100 0 L 100 80 Q 100 100 120 100 L 380 100 Q 400 100 400 120 L 400 200"
    # a middle run too short for two arcs, between two longer ones
    d = _node(src + "console.log(orthPath([{x:0,y:0},{x:0,y:100},{x:30,y:100},{x:30,y:140},{x:90,y:140}], 20));")
    ys = [p[1] for p in _drawn_xs(d)]
    assert ys == sorted(ys), d


@needs_node
def test_the_routers_elbow_radius_fits_the_jog_and_the_room_around_the_bus():
    html, _ = build_from_file(str(SAMPLE))
    m = re.search(r"var r = (Math\.min\(20, Math\.abs\(tx - sx\) / 2,.*?\));\n", html, re.S)
    assert m and "var r = 20;\n        var hDir" not in html
    expr = m.group(1)

    def r(sx, tx, sy, ty, mid):
        return float(_node(f"var sx={sx},tx={tx},sy={sy},ty={ty},midY={mid};console.log({expr});"))
    assert r(650, 670, 4180, 5187, 5058) == 10            # Custom -> Not Liable, 20px jog
    assert r(100, 400, 0, 200, 100) == 20                 # an ordinary elbow keeps 20px arcs
    assert r(100, 105, 0, 200, 100) == 2.5                # nearly straight: a hair of curve
    assert r(100, 400, 0, 200, 8) == 8                    # a bus only 8px under its source
    assert r(100, 400, 0, 100, 100) == 20                 # an end ON the bus holds no arc of its own
