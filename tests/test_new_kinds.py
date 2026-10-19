"""The new-timeline dialog offers four tiles, each with a small preview: Timeline
(Sketch: kind `timeline`, or Horizontal: kind `lanes`), Outline, Hub & spoke
(kind `solar`, shown in its star look) and Mind Palace (a city: Claude's).
Looked at in Chromium and WebKit, desktop and phone, light and dark, against a
stand-in account."""
import re

import pytest
from pathlib import Path

from alto.build import starter
from alto.build.brief import MODES
from alto.cloud import SOURCE

ROOT = Path(__file__).resolve().parent.parent


def _home():
    return (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8")


def test_the_dialog_has_four_tiles_each_with_its_own_preview():
    h = _home()
    kinds = re.findall(r'<button type="button" class="nt-kind[^"]*" data-kind="(\w+)"', h)
    assert kinds == ["timeline", "outline", "solar", "palace"]
    blk = h[h.index('class="nt-kinds"'):h.index('id="nt-msg"')]
    assert blk.count('class="nt-pv"') == 5                       # one each, and a second for the Timeline's Horizontal
    for want in ("Timeline", "Outline", "Hub &amp; spoke", "Mind Palace", ">Sketch<", ">Horizontal<"):
        assert want in blk, want
    assert "Star chart</span>" not in blk and 'data-kind="stars"' not in blk and ">City<" not in blk      # one format, two looks: no tile for the second
    hub = blk[blk.index('data-kind="solar"'):blk.index('data-kind="palace"')]
    assert "Toggle Plain or Star chart any time." in hub and "planets, moons and satellites you can orbit between" in hub


def test_the_timeline_tile_chooses_a_mode_and_the_mind_palace_goes_to_claude():
    h = _home()
    js = h[h.index("function ntResolve()"):h.index("function ntClose()")]
    assert "ntModes.timeline === 'horizontal' ? 'lanes' : 'timeline'" in js        # Sketch / Horizontal keep their kind ids
    assert "ntTile === 'palace'" not in js and "'stars'" not in js and "ntModes = { timeline: 'sketch' }" in h
    # the city needs the real map, so it goes to Claude's own route instead of making a starter
    assert "if(ntKind === 'palace'){ ntClose(); openClaude(inProject ? inProjectPrompt(inProject, 'palace') : newProjectPrompt('palace')); return; }" in h
    assert "ntKind === 'palace' ? 'Build it with Claude' : 'Start writing'" in h


def test_the_previews_follow_the_page_colours_and_respect_reduced_motion():
    h = _home()
    css = h[h.index(".nt-pv{"):h.index(".nt-make{")]
    assert "var(--text)" in css and "var(--muted)" in css and "var(--surface)" in css
    assert "@media (prefers-reduced-motion:reduce){ .nt-pv .pv-pan{ animation:none; } }" in css
    assert "@media (max-width:640px)" in css


def test_the_chosen_kind_is_marked_and_sent_on():
    h = _home()
    assert "aria-pressed" in h and "kind: ntKind" in h


def test_the_cloud_accepts_every_starter_and_defaults_the_rest_to_outline():
    js = SOURCE.read_text(encoding="utf-8")
    assert "(o.kind === 'timeline' || o.kind === 'lanes' || o.kind === 'solar') ? o.kind : 'outline'" in js


def test_the_lanes_starter_is_a_story_with_characters_and_a_flashback():
    s = starter._STARTERS["lanes"]
    assert s["brief"]["mode"] == "lanes" and len(s["brief"]["acts"]) == 2
    assert all(n["when"] for n in s["nodes"]) and "lanes" in starter.KINDS and "lanes" in MODES
    assert not any(ln.get("from") or ln.get("to") for ln in s["brief"]["lines"])     # no legacy branch points
    by = {n["id"]: n for n in s["nodes"]}
    assert by["part-2-start"]["present"] == ["first", "second"] and by["second-start"]["line"] == "second"
    assert by["a-memory"]["flash"] == s["brief"]["flashbacks"][0]["id"]


def test_build_it_with_claude_tells_claude_which_tile_was_picked():
    h = _home()
    phrases = h[h.index("const KIND_PHRASE = {"):h.index("function kindSentence(kind)")]
    for kind in ("outline", "timeline", "lanes", "solar", "palace"):                   # every kind the picker can end on
        assert f"  {kind}: '" in phrases, kind
    assert "stars:" not in phrases and "Star chart" not in phrases
    assert "layout \\'solar\\'" in phrases and "set_up_palace" in phrases
    assert "ntClose(); openClaude(p ? inProjectPrompt(p, ntKind) : newProjectPrompt(ntKind));" in h
    guide = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    line = " ".join(guide[guide.index("If the opening message already says which type"):].split("\n\n")[0].split())
    for want in ("Hub & spoke", "Mind Palace as a city", "do not ask again", "set_up_palace"):
        assert want in line, want
    assert "Star chart" not in line and "palace_view" not in line


def test_the_timeline_tile_shows_only_the_chosen_modes_picture_and_words():
    h = _home()
    css = h[h.index(".nt-pv{"):h.index(".nt-make{")]
    assert ('.nt-kind[data-mode="sketch"] [data-for="horizontal"], .nt-kind[data-mode="horizontal"] [data-for="sketch"]'
            '{ display:none; }') in css                       # the rule is whole: it once lost its block


def test_the_picker_in_a_browser_shows_one_picture_per_tile():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            try:
                b = p.webkit.launch()
            except Exception as e:
                pytest.skip(f"no browser: {e}")
        pg = b.new_context(viewport={"width": 1200, "height": 900}).new_page()
        pg.goto((ROOT / "alto" / "engine" / "home_template.html").as_uri())
        pg.wait_for_timeout(500)
        pg.evaluate("document.getElementById('nt-scrim').classList.add('open')")
        shown = lambda: pg.evaluate("[...document.querySelectorAll('#nt-modal .nt-kind')].map(k => [k.dataset.kind, "
                                    "[...k.querySelectorAll('.nt-pv')].filter(v => getComputedStyle(v).display !== 'none').length, "
                                    "[...k.querySelectorAll('small')].filter(v => getComputedStyle(v).display !== 'none').length])")
        assert shown() == [["timeline", 1, 1], ["outline", 1, 1], ["solar", 1, 1], ["palace", 1, 1]]
        pg.evaluate("ntPick('timeline'); ntMode('timeline', 'horizontal')")
        assert shown()[0] == ["timeline", 1, 1] and pg.evaluate("ntKind") == "lanes"
        pg.evaluate("ntPick('palace')")
        assert pg.evaluate("ntKind") == "palace" and pg.evaluate("document.getElementById('nt-make').textContent") == "Build it with Claude"
        b.close()
