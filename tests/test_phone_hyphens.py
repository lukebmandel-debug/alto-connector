"""A5b (Luke: hyphenated text on a phone looks wrong; Art's verdict A5): a word is never split with a hyphen or cut in half.
System faces and labels wrap at spaces on a plate with no ellipsis; a detail-page search result ends on a whole word."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import mobile_chrome, solar_draw   # noqa: E402

try:
    from playwright import sync_api as pw
except ImportError:
    pw = None


def _css():
    return solar_draw.__dict__.get("SOLAR_CSS") or next(v for v in vars(solar_draw).values() if isinstance(v, str) and ".sol-face span" in v)


def test_system_faces_and_labels_never_hyphenate_and_a_label_wraps_on_a_plate():
    css = _css()
    face = re.search(r"\.sol-face span\{[^}]*\}", css).group(0)
    assert "hyphens:manual" in face and "hyphens:auto" not in face and "overflow-wrap:normal" in face
    lbl = re.search(r"html\.alto-solar:not\(\.mobile\) #world \.node\[data-solar\]>\.sol-lbl\{[^}]*\}", css).group(0)
    assert "white-space:normal" in lbl and "text-overflow" not in lbl and "hyphens:manual" in lbl and "color-mix" in lbl
    assert "background:rgba(6,8,22,.85)" in css                                  # the plate under light text on a star chart


@pytest.mark.skipif(pw is None, reason="no Playwright")
@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_a_detail_search_result_ends_on_a_whole_word(engine):
    glue = mobile_chrome.MSEARCH_PANEL_GLUE
    fn = glue[glue.index("function wholeWords("):glue.index("function pageMatches(")]
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, engine).launch()
        except Exception as e:
            pytest.skip(str(e)[:80])
        pg = b.new_page()
        out = pg.evaluate("""(src) => { const f = new Function(src + '; return wholeWords;')();
          const tx = 'The reasonable foreseeability of harm to an unforeseeable plaintiff decides duty';
          return [f('The reasonable foreseeabi\\u2026', tx), f('The reasonable foreseeability of harm to an\\u2026', tx), f('plain', tx)]; }""", fn)
        b.close()
    assert out[0] == "The reasonable…"                  # "foreseeabi" was a cut word: dropped
    assert out[1] == "The reasonable foreseeability of harm to an…"    # a whole word, then a space: kept
    assert out[2] == "plain"
