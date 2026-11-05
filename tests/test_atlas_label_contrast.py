"""Every Memory Atlas label is readable over any land or sea colour, in every Atlas style (Luke, 2026-11-01: "some text here isn't that visible
with similar colors to the background"; his Safari shot: grey lines under the stop names, route lines across them). The method (Art's): a solid
outline in the plate's own colour (--w-halo) round every letter, so the letters are set against the halo and never against the map; each style
sets only the halo (Classic light white, Classic dark deep navy, Retro black, Holographic its page colour). The pixels are measured in a real
browser (tests/atlas_contrast.py): for each label, the contrast of its text colour against the ground two pixels out from its letters, worst 5%.

The unit colours the scene paints are hostile on purpose: pale yellow, cream, deep navy, the text ink itself. Skipped without Playwright."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import holo, palace_world as pw, retro  # noqa: E402
from tests.atlas_contrast import LEAN, STYLES, page_html, run_all  # noqa: E402
from tests.test_world_palace_render import browser, origin  # noqa: E402,F401

FLOOR = 4.5                                       # WCAG AA for text (the labels are 10.5 to 12.5 px)


def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def _cr(a, b):
    x, y = _lum(a), _lum(b)
    return (max(x, y) + .05) / (min(x, y) + .05)


# ── what the rules carry (no browser) ──

def test_the_label_halo_is_one_variable_each_style_sets():
    css = pw.WORLD_CSS
    assert "--w-halo:#fff" in css and "--w-halo:#0b1122" in css and "--w-ring:" in css and "__RING__" not in css
    ring = re.search(r"--w-ring:([^;]*);", css).group(1)
    assert ring.count("var(--w-halo)") >= 18 and set(re.findall(r"var\((--[\w-]+)\)", ring)) == {"--w-halo"}      # a solid ring of copies, in the halo colour alone
    assert "html:root #wpal-root .wp-lbl{color:var(--w-text);text-shadow:var(--w-ring);}" in css
    assert "html:is(.alto-retro,.alto-holo):root #wpal-root .wp-lbl:not(#_){text-shadow:var(--w-ring);}" in css       # (Retro's own thin shadow would win)
    assert "--w-halo:#000" in retro.FORMAT_CSS
    assert "--w-halo:var(--ho-bg)" in holo.css().replace(" ", "")           # Holographic's halo is its page colour, light and dark


def test_a_phone_gets_the_same_look():
    """Luke, 2026-11-04 ("phone version too"): the contrast rules are no longer gated off phones; the base rules are still there to be overridden."""
    css = pw.WORLD_CSS
    assert "text-shadow:0 0 3px var(--w-sea1),0 0 3px var(--w-sea1),0 0 6px var(--w-sea1);pointer-events:none;}" in css    # the base rule is untouched
    assert "html.dark #wpal-root .wp-pin{color:color-mix(in srgb,var(--u) 70%,#fff);}" in css
    assert "text-shadow:0 0 4px #000,0 0 4px #000;" in retro.FORMAT_CSS
    new = css[css.index("/* ATLAS CONTRAST"):css.index("#wpal-root .wp-mm{")].split("*/", 1)[1].strip().splitlines()
    assert len(new) >= 7 and all(r.startswith(("html:root ", "html:is(.alto-retro,.alto-holo):root ")) for r in new)
    assert not any("mobile" in r for r in new)                                                  # no rule of the block is gated on html.mobile
    assert "html:root #wpal-root .wp-lbl{color:var(--w-text);text-shadow:var(--w-ring);}" in css      # so it reaches html.mobile
    assert "function lbo(){ return 2; }" in pw.WORLD_JS                                         # the 2 px name clearance is not gated either
    assert "classList.contains('mobile')?0:2" not in pw.WORLD_JS


@pytest.mark.parametrize("text,halo", [("#1d2433", "#ffffff"), ("#efe6cf", "#000000")])
def test_the_text_ink_stands_off_its_halo(text, halo):
    assert _cr(text, halo) >= 7


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_holographic_text_stands_off_its_halo(theme):
    t = holo.TOKENS[theme]
    assert _cr(t["tx"], t["bg"]) >= 7 and _cr(t["mu"], t["bg"]) >= FLOOR


# ── the pixels, in a browser ──

@pytest.fixture(scope="module")
def html():
    return page_html()


@pytest.fixture(scope="module")
def measured(browser, origin):                    # noqa: F811
    return run_all(browser, origin, styles=STYLES, zooms=(0, 1, 3), scenes=LEAN)


def test_every_label_reads_in_every_style_scene_and_zoom(measured):
    bad, seen = [], 0
    for m in measured:
        for lab in m["labels"]:
            if "p5" not in lab:
                continue
            seen += 1
            if lab["p5"] < FLOOR:
                bad.append((m["style"], m["scene"], m["zoom"], lab["t"], lab["k"], round(lab["p5"], 2)))
    assert seen > 200, seen                       # (the scenes really did show labels)
    assert not bad, bad[:12]


def test_every_plate_reads_in_every_style(measured):
    bad = [(m["style"], m["scene"], p["what"], p["t"], round(p["cr"], 2)) for m in measured for p in m["plates"] if p["cr"] < FLOOR]
    assert not bad, sorted(set(bad))[:12]
    assert {p["what"] for m in measured for p in m["plates"]} >= {"pin", "tag", "tag number"}



# ── the same, on a 390x844 iPhone (html.mobile) ──

@pytest.fixture(scope="module")
def measured_phone(browser, origin):              # noqa: F811
    return run_all(browser, origin, styles=STYLES, zooms=(0, 1, 3), scenes=LEAN, phone=True)


def test_every_label_reads_on_a_phone(measured_phone):
    bad, seen = [], 0
    for m in measured_phone:
        for lab in m["labels"]:
            if "p5" not in lab:
                continue
            seen += 1
            if lab["p5"] < FLOOR:
                bad.append((m["style"], m["scene"], m["zoom"], lab["t"], lab["k"], round(lab["p5"], 2)))
    assert seen > 100, seen
    assert not bad, bad[:12]


def test_every_plate_reads_on_a_phone(measured_phone):
    bad = [(m["style"], m["scene"], p["what"], p["t"], round(p["cr"], 2)) for m in measured_phone for p in m["plates"] if p["cr"] < FLOOR]
    assert not bad, sorted(set(bad))[:12]
