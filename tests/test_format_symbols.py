"""A project format wears a symbol, not its name (alto/build/format_symbols.py)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import format_symbols as F  # noqa: E402
from alto.build.brief import Brief  # noqa: E402
from alto.build.builder import build_from_file  # noqa: E402
from alto.cloud.meta import fmt_of, meta_of  # noqa: E402


def _dict_in(text, name):
    i = text.index(name + " = ") + len(name) + 3
    return json.JSONDecoder().raw_decode(text[i:])[0]


def test_every_format_has_a_distinct_symbol():
    assert F.KEYS == ("timeline", "outline", "system", "palace", "building")
    assert len({F.SYMBOLS[k][1] for k in F.KEYS}) == len(F.KEYS)
    for k in F.KEYS:
        assert F.name(k) and 'stroke="currentColor"' in F.svg(k)
        assert f'title="{F.name(k)}"' in F.badge(k) and f'aria-label="{F.name(k)}"' in F.badge(k)


@pytest.mark.parametrize("kw,key", [
    ({"mode": "linear"}, "timeline"), ({"mode": "lanes"}, "timeline"),
    ({"mode": "outline"}, "outline"), ({"mode": "outline", "layout": "solar"}, "system"),
    ({"mode": "palace"}, "palace"), ({"mode": "palace", "palace_view": "building"}, "building"),
])
def test_a_brief_picks_its_symbol(kw, key):
    assert F.key_of(Brief(title="t", **kw)) == key


@pytest.mark.parametrize("tpl", ["home_template.html", "reports_template.html"])
def test_the_pages_hold_the_same_drawings(tpl):
    for base in (ROOT / "engine", ROOT / "alto" / "engine"):
        mine = _dict_in((base / tpl).read_text(encoding="utf-8"), "FMT_SYMBOLS")
        assert mine == {k: [F.name(k), F.SYMBOLS[k][1]] for k in F.KEYS}


def test_a_page_names_no_format_in_words():
    html, _ = build_from_file(str(ROOT / "samples" / "outline_brief.json"))
    assert "— Alto</title>" in html and "Alto Timeline" not in html
    m = re.search(r'<script id="alto-format-name">\s*\(function\(\)\{var G=(\{.*?\]\}),H=', html, re.S)
    g = json.loads(m.group(1))
    assert list(g) == ["outline"] and g["outline"][1] == F.SYMBOLS["outline"][1]
    assert "Someone shared “" in html and "navigator.share({ title:" in html
    assert "_altoFB ? _altoFB()" in html and "window._altoFB=function" in html   # the print heading


@pytest.mark.parametrize("name,key", [("contracts", "timeline"), ("outline", "outline"),
                                      ("lanes_v2", "timeline")])
def test_the_listing_record_knows_the_format(name, key):
    html, _ = build_from_file(str(ROOT / "samples" / f"{name}_brief.json"))
    assert fmt_of(html) == key and meta_of(html)["fmt"] == key


def test_the_format_is_read_off_each_formats_own_script():
    assert fmt_of("x\nwindow._ALTO_SOLAR={};\nwindow._ALTO_OUTLINE={};") == "system"
    assert fmt_of("x\nwindow._ALTO_BUILDING={};") == "building"
    assert fmt_of("x\nwindow._altoPalace=function(h){") == "palace"
    assert fmt_of("a window._altoPalace=function") == "timeline"     # mid-line mentions don't count


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_browser_reads_the_format_the_same_way(tmp_path):
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    fn = js[js.index("  function _fmtOf"):js.index("  function _metaOf")]
    cases = ["x\nwindow._ALTO_SOLAR={};\nwindow._ALTO_OUTLINE={};", "x\nwindow._ALTO_BUILDING={};",
             "x\nwindow._altoPalace=function(h){", "x\nwindow._ALTO_OUTLINE={};",
             "a window._altoPalace=function", "plain"]
    runner = tmp_path / "f.js"
    runner.write_text("const f=new Function(" + json.dumps(fn + "; return _fmtOf;") + ")();"
                      "process.stdout.write(JSON.stringify(" + json.dumps(cases) + ".map(f)));")
    assert json.loads(subprocess.check_output(["node", str(runner)])) == [fmt_of(c) for c in cases]
