"""The new-timeline dialog offers three starts, each with a small preview:
Outline, Timeline Sketch (kind `timeline`) and Timeline Horizontal (kind `lanes`).
Looked at in Chromium and WebKit, desktop and phone, light and dark, against a
stand-in account."""
import re
from pathlib import Path

from alto.build import starter
from alto.build.brief import MODES
from alto.cloud import SOURCE

ROOT = Path(__file__).resolve().parent.parent


def _home():
    return (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")


def test_the_dialog_has_three_choices_each_with_its_own_preview():
    h = _home()
    kinds = re.findall(r'<button type="button" class="nt-kind[^"]*" data-kind="(\w+)"', h)
    assert kinds == ["outline", "timeline", "lanes"]
    blk = h[h.index('class="nt-kinds"'):h.index('id="nt-msg"')]
    assert blk.count('class="nt-pv"') == 3
    assert "Sketch" in blk and "Horizontal" in blk


def test_the_previews_follow_the_page_colours_and_respect_reduced_motion():
    h = _home()
    css = h[h.index(".nt-pv{"):h.index(".nt-make{")]
    assert "var(--text)" in css and "var(--muted)" in css and "var(--surface)" in css
    assert "@media (prefers-reduced-motion:reduce){ .nt-pv .pv-pan{ animation:none; } }" in css
    assert "@media (max-width:640px)" in css


def test_the_chosen_kind_is_marked_and_sent_on():
    h = _home()
    assert "aria-pressed" in h and "kind: ntKind" in h


def test_the_cloud_accepts_lanes_and_defaults_the_rest_to_outline():
    js = SOURCE.read_text(encoding="utf-8")
    assert "(o.kind === 'timeline' || o.kind === 'lanes') ? o.kind : 'outline'" in js


def test_the_lanes_starter_is_a_main_line_with_a_branch():
    s = starter._STARTERS["lanes"]
    assert s["brief"]["mode"] == "lanes" and len(s["brief"]["acts"]) == 2
    assert all(n["when"] for n in s["nodes"]) and "lanes" in starter.KINDS and "lanes" in MODES
    ln = s["brief"]["lines"][0]
    assert ln["from"] == "part-1-start" and ln["to"] == "part-2-start"
