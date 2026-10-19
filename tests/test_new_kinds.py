"""The new-timeline dialog offers four tiles, each with a small preview: Timeline
(Sketch: kind `timeline`, or Horizontal: kind `lanes`), Outline, Hub & spoke
(kind `solar`) and Mind Palace (City: Claude's, or Star chart: kind `stars`).
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


def test_the_dialog_has_four_tiles_each_with_its_own_preview():
    h = _home()
    kinds = re.findall(r'<button type="button" class="nt-kind[^"]*" data-kind="(\w+)"', h)
    assert kinds == ["timeline", "outline", "solar", "palace"]
    blk = h[h.index('class="nt-kinds"'):h.index('id="nt-msg"')]
    assert blk.count('class="nt-pv"') == 7                       # one each, and a second (a third for the Mind Palace) for the two with modes
    for want in ("Timeline", "Outline", "Hub &amp; spoke", "Mind Palace", ">Sketch<", ">Horizontal<", ">City<", ">Star chart<"):
        assert want in blk, want


def test_the_timeline_and_mind_palace_tiles_choose_a_mode_that_picks_the_starter():
    h = _home()
    js = h[h.index("function ntResolve()"):h.index("function ntClose()")]
    assert "ntModes.timeline === 'horizontal' ? 'lanes' : 'timeline'" in js        # Sketch / Horizontal keep their kind ids
    assert "ntModes.palace === 'stars' ? 'stars' : ntModes.palace === 'building' ? 'building' : 'palace'" in js
    # the city needs the real map, so it goes to Claude's own route instead of making a starter
    assert "if(ntKind === 'palace' || ntKind === 'building'){ ntClose(); openClaude(inProject ? inProjectPrompt(inProject, ntKind) : newProjectPrompt(ntKind)); return; }" in h
    assert "(ntKind === 'palace' || ntKind === 'building') ? 'Build it with Claude' : 'Start writing'" in h


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
    assert "(o.kind === 'timeline' || o.kind === 'lanes' || o.kind === 'solar' || o.kind === 'stars') ? o.kind : 'outline'" in js


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
    for kind in ("outline", "timeline", "lanes", "solar", "stars", "palace"):         # every kind the picker can end on
        assert f"  {kind}: '" in phrases, kind
    assert "layout \\'solar\\'" in phrases and "palace_view \\'stars\\'" in phrases and "set_up_palace" in phrases
    assert "ntClose(); openClaude(p ? inProjectPrompt(p, ntKind) : newProjectPrompt(ntKind));" in h
    guide = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    line = " ".join(guide[guide.index("If the opening message already says which type"):].split("\n\n")[0].split())
    for want in ("Hub & spoke", "Star chart", "Mind Palace as a city", "do not ask again", "set_up_palace", "palace_view: 'stars'"):
        assert want in line, want
