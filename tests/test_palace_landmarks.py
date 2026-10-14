"""The Mind Palace's landmark buildings (palace_landmarks.py): the art, the
way-in tag with its real count, the key's row, keyboard access, and the hooks in
palace.py. A browser (Chrome via playwright) is used for the drawing tests and
they skip where there is none; nothing here touches the network or any ALTO_*
setting."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import palace, palace_landmarks as pl  # noqa: E402


# ── the module ──────────────────────────────────────────────────────────────
def test_every_landmark_has_art_and_a_default():
    for key in ("ind", "city", "art", "frank", "conv", "stn", "gen"):
        a = pl.ART[key]
        assert a["w"] > 0 and a["h"] > 0 and "<" in a["svg"]


def test_the_art_is_small_and_static():
    total = sum(len(a["svg"]) for a in pl.ART.values())
    assert total < 75_000, total                       # a few KB: it is built once, instanced with <use>
    for a in pl.ART.values():
        assert "<script" not in a["svg"] and "<animate" not in a["svg"] and "<filter" not in a["svg"]
        assert "{s}" in a["svg"]                       # ids carry the svg's own suffix


def test_names_pick_their_building():
    pick = {k: re.compile(p, re.I) for k, p in pl.MATCH}
    assert pick["ind"].search("Independence Hall")
    assert pick["city"].search("City Hall") and pick["city"].search("Philadelphia City Hall")
    assert pick["art"].search("Art Museum") and pick["art"].search("Philadelphia Museum of Art")
    assert pick["frank"].search("Franklin Institute")
    assert pick["conv"].search("Convention Center") and pick["conv"].search("Convention Centre")
    assert pick["stn"].search("30th Street Station")


def test_art_rules_do_not_need_an_ancestor():
    """The art is instanced with <use>, whose clones cannot match `.pal-svg .lz-x`: such a rule
    leaves the faces black. Every lz rule must stand alone."""
    for line in pl.LANDMARK_CSS.splitlines():
        sel = line.strip().split("{")[0]
        if ".lz-" in sel and not sel.startswith("@"):
            assert not re.search(r"\.pal-svg\s+\.lz-", sel) and not re.search(r"\.has-page\s+\.lz-", sel), sel


def test_dark_mode_has_every_material():
    for m in pl._MATS:
        assert f"--lz-{m}-a" in pl.LANDMARK_CSS
    assert "html.dark .pal-svg{" in pl.LANDMARK_CSS


def test_the_page_carries_the_hooks():
    assert pl.LANDMARK_JS in palace.PALACE_JS and pl.LANDMARK_CSS in palace.PALACE_CSS
    for hook in ("window._palLm.draw(", "window._palLm.relayout(", "window._palLm.tip(", "window._palLm.keyRow("):
        assert hook in palace.PALACE_JS, hook
    assert "__ART__" not in pl.LANDMARK_JS and "__MATCH__" not in pl.LANDMARK_JS and "__GRAD__" not in pl.LANDMARK_JS


def test_the_key_explains_landmarks_with_something_inside():
    assert "reference material inside" in pl.LANDMARK_JS


# ── drawn in a browser ──────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                       # no browser installed
            pytest.skip(f"no browser: {e}")
        yield b
        b.close()


PAGE = """<html><body>
<button class="nav-btn env-btn" data-axis-index="env">&#9670; Cases<span class="nav-chip-count">193</span></button>
<button class="nav-btn theme-btn" data-axis-index="theme~frcp">&#167; Federal Rules of Civil Procedure<span class="nav-chip-count">20</span></button>
<button class="nav-btn theme-btn" data-axis-index="theme~usc">&#167; 28 U.S.C.<span class="nav-chip-count">1</span></button>
<svg id="s" class="pal-svg" xmlns="http://www.w3.org/2000/svg" width="800" height="400" viewBox="0 0 800 400"><defs id="d"></defs><g id="lg"></g></svg>
<script>window.opened=[];</script></body></html>"""


def draw_all(browser, landmarks):
    pg = browser.new_page()
    pg.set_content(PAGE)
    pg.add_script_tag(content=pl.LANDMARK_JS)
    pg.evaluate("""(lms)=>{ var NS='http://www.w3.org/2000/svg', svg=document.getElementById('s'), defs=document.getElementById('d'), lg=document.getElementById('lg');
      var names={'index:env':'Cases','index:theme~frcp':'Federal Rules of Civil Procedure','index:theme~usc':'28 U.S.C.'};
      lms.forEach(function(l){ var g=document.createElementNS(NS,'g'); g.setAttribute('class','pl-lmb'+(l.page?' has-page':'')); g.setAttribute('data-page',l.page||''); g.setAttribute('data-name',l.n); lg.appendChild(g);
        window._palLm.draw(g,l,{defs:defs,sid:'t',color:'#4f9a4a',ins:14,pageName:function(pg){return names[pg]||pg;},open:function(p){window.opened.push(p);}}); });
      window._palLm.relayout(svg, 1); }""", landmarks)
    return pg


LMS = [{"n": "Independence Hall", "page": "index:theme~frcp", "box": [100, 100, 312, 242]},
       {"n": "Art Museum", "page": "index:env", "box": [400, 100, 852, 242]},
       {"n": "City Hall", "page": "index:theme~usc", "box": [100, 250, 552, 390]},
       {"n": "Convention Center", "page": "", "box": [560, 250, 780, 390]}]


def test_a_landmark_with_a_page_shows_what_is_inside(browser):
    pg = draw_all(browser, LMS)
    got = pg.evaluate("""()=>Array.from(document.querySelectorAll('.pl-lmb')).map(g=>({n:g.dataset.name, label:g.getAttribute('aria-label'), role:g.getAttribute('role'), tab:g.getAttribute('tabindex'),
      tag:(g.querySelector('.lm-tag .t-n')||{}).textContent||'', glow:!!g.querySelector('.lm-glow'), art:!!g.querySelector('use'), open:(g.querySelector('.lm-tag .t-open')||{}).textContent||''}))""")
    by = {g["n"]: g for g in got}
    assert by["Independence Hall"]["tag"].strip() == "20 rules" and by["Independence Hall"]["open"].startswith("Open")
    assert by["Art Museum"]["tag"].strip() == "193 cases"
    assert by["City Hall"]["tag"].strip() == "1 section"                    # the count's own unit, singular for one
    assert by["Independence Hall"]["label"] == "Independence Hall — inside: Federal Rules of Civil Procedure, 20 rules. Open"
    assert by["Independence Hall"]["role"] == "link" and by["Independence Hall"]["tab"] == "0" and by["Independence Hall"]["glow"]
    cc = by["Convention Center"]                                            # no page: art and a name, no tag, not a tab stop
    assert cc["art"] and not cc["tag"] and not cc["glow"] and cc["tab"] is None and cc["role"] == "img"
    pg.close()


def test_enter_and_space_open_the_page(browser):
    pg = draw_all(browser, LMS)
    pg.focus(".pl-lmb[data-name='Independence Hall']")
    pg.keyboard.press("Enter")
    pg.keyboard.press("Space")
    assert pg.evaluate("window.opened") == ["index:theme~frcp", "index:theme~frcp"]
    pg.close()


def test_the_tip_says_inside_with_the_count(browser):
    pg = draw_all(browser, LMS)
    tip = pg.evaluate("""()=>window._palLm.tip(document.querySelector('.pl-lmb[data-name="Art Museum"]'), function(s){return s;}, function(p){return 'Cases';})""")
    assert "Inside: Cases" in tip and "193 cases" in tip and "Click to open" in tip
    plain = pg.evaluate("""()=>window._palLm.tip(document.querySelector('.pl-lmb[data-name="Convention Center"]'), function(s){return s;}, function(p){return p;})""")
    assert "Inside" not in plain
    pg.close()


def test_the_name_hangs_under_a_small_card_and_sits_in_a_big_one(browser):
    pg = draw_all(browser, LMS)
    far = pg.evaluate("""()=>{ window._palLm.relayout(document.getElementById('s'), .25);
      return Array.from(document.querySelectorAll('.pl-lmb')).map(g=>g.querySelector('.lm-name').getAttribute('class')); }""")
    assert all(c == "lm-name" for c in far)                                 # far away every name hangs under its card
    near = pg.evaluate("""()=>{ window._palLm.relayout(document.getElementById('s'), 1.4);
      return Array.from(document.querySelectorAll('.pl-lmb')).map(g=>g.querySelector('.lm-name').getAttribute('class')); }""")
    assert "lm-name in" in near                                             # close up the big ones carry it inside
    pg.close()


def test_the_key_row(browser):
    pg = draw_all(browser, LMS)
    row = pg.evaluate("window._palLm.keyRow()")
    assert "reference material inside" in row and "pk-row" in row
    pg.close()
