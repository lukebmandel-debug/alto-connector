"""Search that finds things, and detail pages that never show less than their card.

* card_on_detail: every node page opens with the card's number and summary
  (the Summary lead), on desktop, mobile and the swipe peek alike; a timeline
  whose sections already restate its cards can turn it off.
* search: the matcher (alto/build/search.py MATCH_JS) is run in QuickJS on
  the queries that used to fail — prefixes, typos, filler words, numbers —
  and the engine's three search surfaces are wired to the shared module.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import blocks  # noqa: E402
from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402
from alto.build.search import MATCH_JS  # noqa: E402

SAMPLE = ROOT / "samples" / "contracts_brief.json"


def _build(mutate=None):
    d = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if mutate:
        mutate(d)
    brief, nodes, conns = load_brief(d)
    html, _ = build_timeline(brief, nodes, conns)
    return html


# ── the card on its detail page ─────────────────────────────────────────────

def test_every_node_section_builder_leads_with_the_card():
    for src in (blocks.NODE_SECTIONS_D, blocks.NODE_SECTIONS_M,
                blocks.NODE_SECTIONS_OUTLINE_D, blocks.NODE_SECTIONS_OUTLINE_M):
        assert src.lstrip("var ").split("=", 1)[1].strip().startswith("_altoCardLead("), src


def test_card_lead_is_on_by_default():
    html = _build()
    assert "window._ALTO_CARD_LEAD=true;" in html
    assert "function _altoCardLead(id)" in html
    assert html.count("_altoCardLead(id).concat(") == 1          # desktop showDetail
    assert html.count("_altoCardLead(targetId).concat(") == 1    # mobile swipe peek


def test_card_lead_can_be_turned_off():
    html = _build(lambda d: d["brief"].__setitem__("card_on_detail", False))
    assert "window._ALTO_CARD_LEAD=false;" in html


def test_card_lead_escapes_the_summary():
    """The card renders desc as text; the page renders sections as HTML."""
    assert "e(n.desc)" in blocks.CARD_LEAD_BODY


# ── search wiring ────────────────────────────────────────────────────────────

def test_search_module_and_config_ship_on_every_page():
    html = _build()
    assert "window._ALTO_SEARCH=" in html
    assert "window._altoSearch={" in html and "window._altoMatch={" in html
    assert 'id="alto-search-css"' in html
    cfg = json.loads(html.split("window._ALTO_SEARCH=", 1)[1].split(";</script>", 1)[0])
    assert set(cfg) == {"aliases", "kinds", "labels"}


def test_every_search_surface_delegates():
    names = {p["name"] for p in PATCHES}
    for n in ("search-core-ranked", "search-core-snippet", "search-desktop-grouped-rows",
              "search-lands-enlarged-ringed", "search-mobile-grouped-rows", "search-mobile-lands"):
        assert n in names
    html = _build()
    assert "if(window._altoSearch) return window._altoSearch.search(q);" in html
    assert "if(window._altoSearch){ window._altoSearch.land(id); return; }" in html


# ── the matcher, run for real ────────────────────────────────────────────────

quickjs = pytest.importorskip("quickjs")


@pytest.fixture(scope="module")
def js():
    ctx = quickjs.Context()
    ctx.eval("var window={};" + MATCH_JS + "var M=window._altoMatch;")
    return ctx


def _rank(js, q, items):
    """items: {name: [(weight, text), ...]} → names best first (title = first field)."""
    src = json.dumps({k: [{"w": w, "text": t, "ac": i == 0} for i, (w, t) in enumerate(v)]
                      for k, v in items.items()})
    return json.loads(js.eval(f"""(function(){{
      var I={src}, Q=M.query({json.dumps(q)}), out=[];
      Object.keys(I).forEach(function(k){{ var s=M.score(Q,{{fields:I[k]}}); if(s) out.push([k,s.score,s.exact]); }});
      if(out.some(function(o){{ return o[2]; }})) out=out.filter(function(o){{ return o[2]; }});
      out.sort(function(a,b){{ return b[1]-a[1]; }});
      return JSON.stringify(out.map(function(o){{ return o[0]; }}));
    }})()"""))


TORTS = {
    "ril": [(10, "Res Ipsa Loquitur"), (3, "A permissible inference of negligence from the accident itself.")],
    "rest": [(10, "§168 (2d) — Conditional or Restricted Consent")],
    "neg": [(10, "Negligence"), (3, "Liability for failing to exercise reasonable care.")],
    "vos": [(10, "Vosburg v. Putney"), (1.6, "Defendant kicked plaintiff in the shin during class.")],
    "hooper": [(10, "The T.J. Hooper"), (1.6, "Tugs without radios were unseaworthy.")],
    "rule": [(10, "§328D (2d) — Res Ipsa Loquitur")],
}


@pytest.mark.parametrize("q,first", [
    ("res", "ril"),                    # Luke's example: a prefix finds the concept first
    ("res ispa loquitor", "ril"),      # two typos
    ("negligent", "neg"),              # stem
    ("vosburg v putney", "vos"),       # "v" is filler
    ("vosberg", "vos"),                # typo
    ("tj hooper", "hooper"),           # initials without the dots
    ("what is negligence", "neg"),     # question words are filler
    ("328d", "rule"),                  # a section number
    ("RIL", "ril"),                    # an acronym of a title
])
def test_the_queries_that_used_to_fail(js, q, first):
    assert _rank(js, q, TORTS)[0] == first


def test_every_word_must_match(js):
    assert _rank(js, "vosburg negligence", TORTS) == []


def test_typo_matches_only_when_nothing_matches_properly(js):
    items = {"exact": [(10, "Case")], "typo": [(10, "Cave")]}
    assert _rank(js, "case", items) == ["exact"]
    assert _rank(js, "cave", items) == ["typo"]


def test_a_typo_keeps_its_first_letter(js):
    assert _rank(js, "pinto", {"into": [(10, "Walked into the road")]}) == []


def test_snippet_marks_every_matched_word(js):
    out = js.eval("M.snippet('The thing speaks for itself — res ipsa loquitur.', M.query('res ipsa'))")
    assert "<mark>res</mark>" in out and "<mark>ipsa</mark>" in out
    assert "<mark>loquitur</mark>" not in out
