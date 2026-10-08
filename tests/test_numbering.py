"""Outline card numbers (numbering.py): 2, 2.e, 2.e.6, 2.e.6.2-1c … — the
cycle, letters past z, reading typed numbers back, and the page's JS agreeing
with the Python."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.numbering import NUM_JS, format_num, letters, parse_num, path_numbers  # noqa: E402
from alto.build.builder import load_brief, build_timeline  # noqa: E402
from alto.build.verify import find_node  # noqa: E402


def _chain(depth, width=7):
    """A unit-2 outline (unit 1 is one card) with `width` children per level
    down one spine; returns seqs, kids, parent and the spine ids."""
    kids, parent, seq, spine = {}, {}, ["u2"], ["u2"]
    for d in range(1, depth + 1):
        p = spine[-1]
        ks = [f"{p}-{j}" for j in range(width)]
        kids[p] = ks
        for k in ks:
            parent[k] = p
        seq += ks
        spine.append(ks[min(d, width - 1) % width])
    return [["u1"], seq], kids, parent, spine


def test_letters_bijective():
    assert [letters(i) for i in (0, 1, 25, 26, 27, 51, 52, 701, 702)] == \
        ["a", "b", "z", "aa", "ab", "az", "ba", "zz", "aaa"]


def test_cycle_letter_dot_dot_dash():
    seqs, kids, parent, spine = _chain(9)
    num = path_numbers(seqs, kids, parent)
    assert num["u1"] == "1" and num["u2"] == "2"
    # Luke's example shape: letter, .n, .n, -n, letter (written straight on), .n, .n, -n, letter
    got = [num[i] for i in spine]
    assert got == ["2", "2.b", "2.b.3", "2.b.3.4", "2.b.3.4-5", "2.b.3.4-5f",
                   "2.b.3.4-5f.7", "2.b.3.4-5f.7.7", "2.b.3.4-5f.7.7-7", "2.b.3.4-5f.7.7-7g"]


def test_luke_example_round_trips():
    s = "2.e.6.2-1c.5.4-2"
    unit, idx = parse_num(s)
    assert unit == 2 and idx == [4, 5, 1, 0, 2, 4, 3, 1]
    assert format_num(unit, idx) == s
    assert format_num(*parse_num("e.4.1-1".replace("e", "3.e", 1))) == "3.e.4.1-1"


@pytest.mark.parametrize("bad", ["", "a", "2.1", "2.e.f", "2.e.0", "2.e.1.2.3.4", "x2", "2.e.1.1-1-1"])
def test_parse_rejects_wrong_shapes(bad):
    assert parse_num(bad) is None


def test_parse_forgives_separators_and_case():
    assert parse_num("2E.6.2-1C ") == parse_num("2.e.6.2-1c")
    assert parse_num("2.e.6.2.1") == parse_num("2.e.6.2-1")
    assert parse_num("2.aa") == (2, [26])


def test_two_top_cards_in_a_unit_number_as_siblings():
    num = path_numbers([["r1", "r2", "k"]], {"r2": ["k"]}, {"k": "r2"})
    assert num == {"r1": "1.a", "r2": "1.b", "k": "1.b.1"}


def test_outline_build_uses_path_numbers_everywhere():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text())
    html = build_timeline(*load_brief(d))[0]
    o = html.index("window._ALTO_OUTLINE={num:")
    num = json.loads(html[o + len("window._ALTO_OUTLINE={num:"):html.index(",label:", o)])
    assert num["formation"] == "1" and num["offer"] == "1.c" and num["option-contracts"] == "1.c.2"
    assert "window._ALTO_OUTLINE.num[id])" in html          # card badges take them
    assert "window._altoPathNums" in html


def test_timeline_keeps_unit_dot_place():
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text())
    html = build_timeline(*load_brief(d))[0]
    if '"mode": "outline"' in json.dumps(d):
        pytest.skip("sample is an outline")
    assert "window._altoPathNums = function" not in html


@pytest.mark.skipif(find_node() is None, reason="node not installed")
def test_js_matches_python(tmp_path):
    cases = []
    for depth in (3, 6, 10):
        seqs, kids, parent, _ = _chain(depth, width=30)
        cases.append([seqs, kids, parent])
    texts = ["2.e.6.2-1c.5.4-2", "2E.6.2-1C", "2.e.6.2.1", "2.aa", "2.1", "2.e.0", "1", "x"]
    js = NUM_JS.replace("window.", "globalThis.") + (
        "\nconst C=" + json.dumps(cases) + ", T=" + json.dumps(texts) + ";"
        "console.log(JSON.stringify({n:C.map(c=>globalThis._altoPathNums(c[0],c[1],c[2])),"
        "p:T.map(t=>{const r=globalThis._altoParseNum(t);return r?[r.unit,r.idx]:null;}),"
        "f:T.map(t=>{const r=globalThis._altoParseNum(t);return r?globalThis._altoFormatNum(r.unit,r.idx):null;})}));")
    # a file, not `node -e`: the script is longer than Windows allows on a command line
    f = tmp_path / "num.js"
    f.write_text(js, encoding="utf-8")
    out = json.loads(subprocess.run([find_node(), str(f)], capture_output=True, text=True, check=True).stdout)
    assert out["n"] == [path_numbers(*c) for c in cases]
    py = [parse_num(t) for t in texts]
    assert out["p"] == [[u, i] if r else None for r in py for (u, i) in [r or (0, 0)]]
    assert out["f"] == [format_num(*r) if r else None for r in py]


def test_a_typed_number_folds_to_the_same_number():
    """Typing 2.e.1 on Revocation (1.c.1) writes rp| + so| (manual_edit
    renumber/moveTo); folded and rebuilt, the outline numbers it 2.e.1."""
    from tests.test_manual_edit import Store, _d, _build
    from alto.edits import fold
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "rp|revocation": {"b": "offer", "v": "reliance", "t": 5},
        "so|reliance": {"b": ["promissory-estoppel", "charitable-subscriptions"],
                        "v": ["revocation", "promissory-estoppel", "charitable-subscriptions"], "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    html, _ = _build(st)
    o = html.index("window._ALTO_OUTLINE={num:")
    num = json.loads(html[o + len("window._ALTO_OUTLINE={num:"):html.index(",label:", o)])
    assert num["revocation"] == "2.e.1" and num["promissory-estoppel"] == "2.e.2"
    assert num["option-contracts"] == "1.c.1"
