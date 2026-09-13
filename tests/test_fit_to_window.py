"""The timeline scales to fit the window instead of being pinned at 0.8.

`#world` is authored 1700px wide (five columns), and `html{zoom:0.8}` shrank it
to 1360 so it would fit a 1512px laptop. That pinned every reader to 0.8 — a
1920px monitor with 220px of slack included, where Alto's Georgia body text
lands at 10 device pixels and reads blurry on a 1x display.

The floor stays 0.8, so no window is worse off than today and a JS-off page is
byte-identical; the ceiling is the design's own native size. These tests pin the
three parts and, above all, the one that fails silently: Chrome computes
100vw/100vh against the device viewport and ignores the root zoom, so the engine
divides by 0.8 to recover CSS px. Left hardcoded, a zoom of 1.0 renders <body>
at 125% of the window there.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.engine_patches import PATCHES, PatchError, apply_patches  # noqa: E402
from alto.build.pages import build_home, build_reports  # noqa: E402
from alto.engine import template as engine_template  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"
FIT = [p["name"] for p in PATCHES if p["name"].startswith("fit-")]


@pytest.fixture(scope="module")
def html():
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return build_timeline(*load_brief(d))[0]


def test_the_floor_is_still_the_shipped_zoom(html):
    """A page whose script never runs must render exactly as it does today."""
    assert "html{zoom:0.8; --alto-zoom:0.8;}" in html


def test_the_fit_script_runs_before_any_layout(html):
    """It has to pick the scale before initLayout measures anything, so it goes
    at the end of <head> — not with the other scripts, which are in the body."""
    assert '<script id="alto-fit">' in html
    assert html.index('<script id="alto-fit">') < html.index("\n<body>")


def test_the_scale_is_clamped_to_the_floor_and_the_native_size(html):
    assert "var NEED = 1700, MIN = 0.8, MAX = 1;" in html
    assert "Math.min(MAX, Math.max(MIN, window.innerWidth / NEED))" in html


def test_the_scale_is_measured_at_a_known_zoom_not_inferred(html):
    """innerWidth is zoom-invariant in Blink, but a browser that divided it by
    the root zoom would make the fit circular — 1512px would flip between 0.889
    and 1.0 on every resize. Measuring at zoom 1 cannot oscillate."""
    assert "d.style.zoom = '1';" in html
    assert "void d.offsetWidth;" in html          # flush before reading


def test_the_floor_falls_back_to_the_stylesheet_rather_than_restating_it(html):
    assert "d.style.zoom = (k > MIN) ? String(k) : '';" in html


def test_mobile_is_skipped_outright(html):
    i = html.index('<script id="alto-fit">')
    body = html[i:html.index("</script>", i)]
    assert "if (d.classList.contains('mobile')) return;" in body


def test_resize_refits_ahead_of_the_handlers_that_measure_the_scale(html):
    """centreWorld (120ms) and the d-grid quantizer (160ms) both derive the
    scale by measurement, so they re-settle onto whatever this picks — but only
    if it lands first."""
    i = html.index('<script id="alto-fit">')
    body = html[i:html.index("</script>", i)]
    assert "setTimeout(fit, 100)" in body
    assert "window.addEventListener('resize'" in body


# ── the one that fails silently ─────────────────────────────────────────────

def test_no_blink_compensation_still_divides_by_a_hardcoded_zoom(html):
    for bad in ("calc(100vw / 0.8)", "calc(100vh / 0.8)", "calc(100vh / 0.8 - 104px)"):
        assert bad not in html, f"{bad} would render <body> at 125% of the window in Chrome"


@pytest.mark.parametrize("prop", ["100vw", "100vh"])
def test_the_blink_compensation_tracks_the_chosen_scale(html, prop):
    assert f"calc({prop} / var(--alto-zoom, 0.8))" in html


def test_the_overview_panel_and_the_glass_slab_track_it_too(html):
    assert "width:max(1700px, calc(100vw / var(--alto-zoom, 0.8))) !important;" in html
    assert "height:calc(100vh / var(--alto-zoom, 0.8) - 104px) !important;" in html


# ── Safari 26+: standardized zoom, the same viewport bug as Chrome ──────────

def test_safari_standard_zoom_is_detected_by_behaviour_before_layout(html):
    """Safari 26 resolves 100vw against the unzoomed viewport, like Blink, so
    without the compensation <body> covers only zoom×window. Detected by
    measurement (Safari 18 must not match), in <head>, before layout."""
    add = "de.classList.add('vw-unzoomed')"
    assert add in html
    assert html.index(add) < html.index("\n<body>")
    assert "de.style.zoom = '0.5';" in html        # zoom-independent probe
    assert ("if(de.classList.contains('mobile') || "
            "de.classList.contains('is-blink')) return;") in html


@pytest.mark.parametrize("sel", [
    "html.vw-unzoomed:not(.mobile) body",
    "html.vw-unzoomed:not(.mobile) #glass-slab",
    "html.vw-unzoomed:not(.mobile) #summary-wrap.open",
])
def test_safari_gets_the_same_viewport_fill_as_blink(html, sel):
    assert sel in html


# ── the other two pages never had the zoom, and must not gain it ────────────

def test_the_home_and_reports_pages_are_untouched():
    """Only the timeline carries html{zoom:0.8}; home and reports already render
    at 1.0. Neither goes through apply_patches, and neither should start."""
    home = build_home([{"name": "P", "courses": []}])
    reports = build_reports([], "")
    for name, page in (("home", home), ("reports", reports)):
        assert "alto-fit" not in page, f"{name} gained the timeline's fit script"
        assert "--alto-zoom" not in page, f"{name} gained the timeline's zoom var"
        assert "html{zoom:0.8;}" not in page, f"{name} gained a root zoom it never had"


# ── the anchors ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", FIT)
def test_each_fit_anchor_matches_the_engine_exactly_once(name):
    t = engine_template("timeline_template.html")
    p = next(x for x in PATCHES if x["name"] == name)
    assert p["count"] == 1
    assert t.count(p["old"]) == 1, f"{name}: anchor no longer unique in the engine"


@pytest.mark.parametrize("name", FIT)
def test_a_moved_fit_anchor_fails_the_build_by_name(name):
    p = next(x for x in PATCHES if x["name"] == name)
    moved = engine_template("timeline_template.html").replace(p["old"], "/* moved */", 1)
    with pytest.raises(PatchError, match=name):
        apply_patches(moved)
