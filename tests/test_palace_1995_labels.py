"""1.9.95: a landmark's name slides to the nearest free place instead of vanishing (One and Two Liberty Place kept both
names zoomed in, and one zoom step out one of them was dropped; every landmark had the same flaw)."""
import json
import os
import re
import subprocess
import sys

import pytest

from alto.build import palace, palace_labels


def _fit():
    js = palace.PALACE_JS
    return js[js.index("function lblFit(svg, viewOnly){"):js.index("/* chips keep a constant size on screen")]


def test_the_name_has_a_ladder_of_places_not_two():
    js = palace.PALACE_JS
    assert palace_labels.LABELS_JS in js and palace_labels.LABELS_CSS in palace.PALACE_CSS
    assert "function lmSpots(card, nat, alt, fs, W, z, prev)" in palace_labels.LABELS_JS
    f = _fit()
    assert "spots=lmSpots(card, [g[0], g[1]], alt, fs, it.q*fs, z, it.spot)" in f
    assert "for(var tier=0;tier<2 && !ok;tier++)" in f        # strict pass, then the one that may lie over a neighbour's card


def test_the_names_wrapper_knows_its_landmark():
    # the root cause of the dead over-the-card fallback: the name was moved into a .pl-lmn wrapper (1.9.8x) and lblFit kept
    # reading the card from t.parentNode._lm, which nothing set any more
    assert "w._lm=L;" in palace.PALACE_JS
    assert "lm=t.parentNode._lm" in _fit()


def test_a_name_that_was_showing_keeps_its_place_and_a_thinner_margin():
    f = _fit()
    assert "held=it.keep" in f and "(it.k==='lm-name' && held)?1:P4" in f   # hysteresis: no blinking at a zoom step's edge
    assert "it.spot" in f and "prev" in palace_labels.LABELS_JS            # and the spot it had is tried first: no hopping


def test_only_names_cards_chips_and_numbered_buildings_stop_a_name():
    f = _fit()
    assert "relax && o.el.classList.contains('lm-card')" in f              # second pass: over a neighbouring landmark's card
    assert ".pl-portal'" in f and "|| o.portal)))" in f                    # an airport portal (on a station building) is never covered by a name
    assert "obbHit(b, (it.k==='lm-name' && o.ext) || o) && (hn=o)" in f      # a numbered building is never covered ...
    assert ":scope > .nb3d, :scope > .node-card" in f                          # ... nor its number card or its tall art
    assert "if(hitKept(b)){ it.why='name:'" in f           # nor another name


def test_a_name_off_its_card_gets_a_leader_that_hides_with_it():
    f = _fit()
    assert "createElementNS('http://www.w3.org/2000/svg','line')" in f and "'lm-lead'" in f
    assert "lmFade(ln, !!(show && ln._on))" in f and "lmFade(it.t, show)" in f    # a name and its leader fade, never pop
    assert "function lmFade(e, on)" in palace_labels.LABELS_JS and "transition:opacity" in palace_labels.LABELS_CSS
    assert ".lm-lead{" in palace_labels.LABELS_CSS and "var(--pz,1)" in palace_labels.LABELS_CSS


def test_a_tilted_districts_translate_is_part_of_the_names_place():
    assert "translate\\(" in palace_labels.LABELS_JS and "function lmToBoard(q, tf)" in palace_labels.LABELS_JS


# ── the ladder itself, run in a real engine when Playwright is installed (the QA kit's venv has it) ──
def _run(js):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        b = p.webkit.launch()
        try:
            pg = b.new_page()
            pg.set_content("<html></html>")
            pg.add_script_tag(content=palace_labels.LABELS_JS)
            return pg.evaluate(js)
        finally:
            b.close()


def test_spots_run_home_first_then_sideways_rows_then_beside():
    r = _run("""()=>{ var s=lmSpots({x:100,y:100,w:80,h:50}, [140,170], [140,95], 11.5, 100, .5, null);
      var ids=s.map(function(a){return a.id;}); var costs=s.map(function(a){return a.c;});
      return {first:ids[0], second:ids[1], n:s.length, sorted:costs.every(function(c,i){return i===0||c>=costs[i-1];}),
              beside:ids.indexOf('sr')>0 && ids.indexOf('sl')>0}; }""")
    assert r["first"] == "b00" and r["second"] == "a00" and r["sorted"] and r["beside"]
    assert r["n"] == 9 * 5 + 2


def test_the_spot_a_name_had_comes_first_so_it_does_not_hop():
    r = _run("""()=>{ var s=lmSpots({x:100,y:100,w:80,h:50}, [140,170], [140,95], 11.5, 100, .5, 'b12'); return s[0].id; }""")
    assert r == "b12"


def test_the_leader_appears_only_when_the_name_is_off_its_card():
    r = _run("""()=>{ var c={x:100,y:100,w:80,h:50};
      return {home: lmLead(c, 140, 164, 11.5, 100, 1), off: lmLead(c, 140, 230, 11.5, 100, 1)}; }""")
    assert r["home"] is None and r["off"] is not None
    x1, y1, x2, y2 = r["off"]
    assert (x1, y1) == (140, 150) and y2 > y1                               # from the card's bottom edge down to the name
