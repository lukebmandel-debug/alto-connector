"""An axis's values can fall into named groups; each group is its own Index chip
in the top bar, with its own index page (a law outline's "Federal Rules of Civil
Procedure" and "28 U.S.C.")."""
import json
from pathlib import Path

from alto.build import detail_extras as dx
from alto.build.brief import Axis, AxisValue
from alto.build.builder import build_timeline, load_brief

ROOT = Path(__file__).resolve().parent.parent


def _d():
    d = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    d["brief"]["axes"] = [{"label": "Statutes & Rules", "singular": "Section", "hide_nav": True,
        "values": [
            {"id": "r4h", "name": "Fed. R. Civ. P. 4(h)", "group": "Federal Rules of Civil Procedure",
             "aliases": ["Rule 4(h)"], "sections": [{"h": "Rule text", "t": "RULE-TEXT", "prov": "quoted"}]},
            {"id": "u1367", "name": "28 U.S.C. § 1367", "group": "28 U.S.C.", "role": "Supplemental jurisdiction"},
            {"id": "u1332", "name": "28 U.S.C. § 1332", "group": "28 U.S.C."}]}]
    for n in d["nodes"]:
        n["axis1_values"] = []
        n["axis2_values"] = []
    d["nodes"][0]["axis1_values"] = ["r4h", "u1367"]
    return d


def test_each_group_is_its_own_index_chip():
    html, _ = build_timeline(*load_brief(_d()))
    assert 'data-axis-index="env~federal-rules-of-civil-procedure"' in html
    assert 'data-axis-index="env~28-u-s-c"' in html
    assert 'data-axis-index="env"' not in html          # no chip for the axis as a whole
    # counts are per group
    assert html.count('nav-chip-count">1<') >= 1 and html.count('nav-chip-count">2<') >= 1
    cfg = html[html.index("window._ALTO_AXES="):]
    assert '"env~28-u-s-c"' in cfg and '"ids": ["u1367", "u1332"]' in cfg


def test_an_ungrouped_axis_is_unchanged():
    d = _d()
    for v in d["brief"]["axes"][0]["values"]:
        v.pop("group")
    html, _ = build_timeline(*load_brief(d))
    assert 'data-axis-index="env"' in html and "env~" not in html.split("window._ALTO_AXES=")[1][:400]


def test_index_entries_orders_groups_by_first_appearance():
    ax = Axis(label="L", singular="S", hide_nav=True, values=[
        AxisValue(id="a", name="A", group="Two"), AxisValue(id="b", name="B", group="One"),
        AxisValue(id="c", name="C", group="Two"), AxisValue(id="d", name="D")])
    got = dx.index_entries([("theme", ax)])
    assert [(k, l, i) for k, _kind, l, i in got] == [
        ("theme~two", "Two", ["a", "c"]), ("theme~one", "One", ["b"]), ("theme~l", "L", ["d"])]


def test_autolink_does_not_link_a_rule_number_inside_a_longer_one():
    js = dx.AUTOLINK
    assert "(?![A-Za-z0-9])" in js          # "Rule 3" must not link inside "Rule 38"
