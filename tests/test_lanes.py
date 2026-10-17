"""The horizontal timeline (brief.mode "lanes", lanes.py): reading `when`,
checking lines, what the page carries, and manual edit mode's when / line /
lines folded back into the draft."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import BriefError, validate_brief, validate_nodes  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build import lanes  # noqa: E402
from alto.build.lanes import parse_when  # noqa: E402
from alto.build.verify import find_node, verify_scripts  # noqa: E402

SAMPLE = ROOT / "samples" / "lanes_brief.json"


def _d():
    return json.loads(SAMPLE.read_text())


@pytest.mark.parametrize("s,want", [
    ("1842", 1842), ("1842-01", 1842), ("-500", -500), ("500 BC", -500), ("44 BCE", -44),
    ("Year 3", 3), ("Day 12", 12), ("", None), ("someday", None), (7, 7),
])
def test_parse_when(s, want):
    assert parse_when(s) == want


def test_dates_inside_a_year_keep_their_order():
    a, b, c = parse_when("1852-03-01"), parse_when("1852-06"), parse_when("March 1853")
    assert 1852 < a < b < 1853 <= c < 1853.3


def test_sample_validates_and_builds_with_the_layout():
    b, nodes, conns = load_brief(_d())
    validate_brief(b)
    w = validate_nodes(b, nodes)
    assert any("no `when`" in x for x in w)                # the one undated event is named
    html, _ = build_timeline(b, nodes, conns)
    assert "window._ALTO_LANES=" in html and "window._altoLanes=function" in html
    assert "(window._altoLanes && window._altoLanes(nodeHeights))" in html
    data = json.loads(re.search(r"window\._ALTO_LANES=(\{.*?\});\n", html).group(1))
    assert data["ev"]["storm-1810"] == {"l": "flashback", "w": "1810", "t": 1810.0, "i": 0,
                                         "present": [], "flash": "", "g": 0, "gap": ""}
    assert {l["id"]: l["to"] for l in data["lines"]}["flashback"] == "memory"
    assert data["main"] == "The town" and data["v"] == 2 and data["flashbacks"] == []
    # v1 branch / join points are where the line is on the page (presence)
    by = {l["id"]: l for l in data["lines"]}
    assert by["tomas"]["presence"] == ["letter", "council"]
    assert by["flashback"]["presence"] == ["memory"] and by["flashback"]["span"] == ["storm-1810", "memory"]
    assert "window._altoLanesDerive=function" in html


def test_other_modes_carry_no_lanes_code():
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text())
    html, _ = build_timeline(*load_brief(d))
    assert "window._ALTO_LANES=" not in html and "window._altoLanes=function" not in html


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d["nodes"][0].update(line="nope"), "not one of the brief's lines"),
    (lambda d: d["brief"]["lines"].append({"id": "main", "label": "x"}), "main"),
    (lambda d: d["brief"]["lines"][0].update(side="left"), "side"),
    (lambda d: d["brief"]["lines"][0].update(to="tomas-camp"), "on the line itself"),
    (lambda d: d["brief"]["lines"][0].update(to="ghost"), "is not a node"),
    (lambda d: d["brief"]["lines"][0].update(**{"from": "council", "to": "letter"}), "before it branches"),
    (lambda d: d["brief"].update(mode="linear"), "need mode 'lanes'"),
])
def test_bad_lines_are_refused(mutate, msg):
    d = _d()
    mutate(d)
    b, nodes, _ = load_brief(d)
    with pytest.raises(BriefError, match=msg):
        validate_brief(b)
        validate_nodes(b, nodes)


@pytest.mark.skipif(find_node() is None, reason="node not installed")
def test_lanes_page_passes_the_js_gate():
    html, _ = build_timeline(*load_brief(_d()))
    assert verify_scripts(html, "timeline") == ([], [])


def test_when_line_and_lines_fold_into_the_draft():
    from tests.test_manual_edit import Store
    from alto.edits import fold
    st = Store(_d())
    st.doc["brief"]["timeline_id"] = "t1"
    newline = {"id": "line-ab12c", "label": "The ferry", "color": "#3d9a8b", "side": "below", "from": "arrive", "to": ""}
    old = {"id": "tomas", "label": "Tomas", "color": "#e07a5f", "side": "above", "from": "letter", "to": "council"}
    st.edits = {"v": 1, "ops": {
        "ln|line-ab12c": {"b": None, "v": newline, "t": 1},
        "ln|tomas": {"b": old, "v": dict(old, label="Tomas the sailor", to="light"), "t": 2},
        "n|repair|when": {"b": "1853-05", "v": "1853-09", "t": 3},
        "n|repair|line": {"b": "", "v": "line-ab12c", "t": 4}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    lines = {l["id"]: l for l in st.doc["brief"]["lines"]}
    assert lines["line-ab12c"]["label"] == "The ferry" and lines["line-ab12c"]["from"] == "arrive"
    assert lines["tomas"]["label"] == "Tomas the sailor" and lines["tomas"]["to"] == "light"
    n = next(x for x in st.nodes if x["id"] == "repair")
    assert n["when"] == "1853-09" and n["line"] == "line-ab12c"
    b, nodes, conns = load_brief({"brief": st.doc["brief"], "nodes": st.nodes, "connections": st.conns})
    validate_brief(b)
    validate_nodes(b, nodes)


# ── lanes v2: presence and flashbacks (docs/lanes-v2-contract.md) ───────────

V2 = ROOT / "samples" / "lanes_v2_brief.json"


def _v2():
    return json.loads(V2.read_text())


def _payload(d):
    from alto.build.lanes import lanes_payload
    b, nodes, _ = load_brief(d)
    return lanes_payload(b, nodes)


def test_v2_sample_validates_and_carries_presence_and_flashbacks():
    d = _v2()
    b, nodes, conns = load_brief(d)
    validate_brief(b)
    w = validate_nodes(b, nodes)
    assert not [x for x in w if "flashback" in x or "line " in x], w
    html, _ = build_timeline(b, nodes, conns)
    L = json.loads(re.search(r"window\._ALTO_LANES=(\{.*?\});\n", html).group(1))
    assert L["v"] == 2 and L["main"] == "The story"
    assert L["order"] == [n["id"] for n in d["nodes"]]          # already in page order
    by = {l["id"]: l for l in L["lines"]}
    assert by["ada"]["events"] == ["logbooks"]
    assert by["ada"]["presence"] == ["arrive", "warning", "quay", "council", "relight"]
    assert by["ada"]["span"] == ["arrive", "relight"]
    assert by["ben"]["presence"] == ["quay", "council"] and by["ben"]["span"] == ["ben-letter", "ben-leaves"]
    assert by["keeper"]["events"] == [] and by["keeper"]["presence"][1:3] == ["great-storm", "lamp-dark"]
    assert set(by["ada"]) == {"id", "label", "color", "side", "from", "to", "events", "presence", "span"}
    assert L["flashbacks"] == [{"id": "storm", "label": "Twenty years earlier", "nodes": ["great-storm", "lamp-dark"],
                                "prev": "warning", "next": "quay"}]
    e = L["ev"]["great-storm"]
    assert e == {"l": "main", "w": "1870-10", "t": e["t"], "i": 3, "present": ["keeper"], "flash": "storm", "g": 0, "gap": ""}
    assert L["ev"]["logbooks"]["l"] == "ada" and L["ev"]["logbooks"]["present"] == []


def test_page_order_is_unit_by_unit():
    d = _v2()
    d["nodes"].insert(0, d["nodes"].pop())                     # ben-leaves (unit 3) listed first
    L = _payload(d)
    # after units 1 and 2 (7 events), first in unit 3: the material's order inside a unit
    assert L["order"][7:] == ["ben-leaves", "council", "relight"] and L["ev"]["ben-leaves"]["i"] == 7


def _nd(d, i):
    return next(n for n in d["nodes"] if n["id"] == i)


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: _nd(d, "logbooks").update(present=["ben"]), "only for main-line events"),
    (lambda d: _nd(d, "arrive").update(present=["nobody"]), "is not one of the brief's lines"),
    (lambda d: _nd(d, "arrive").update(present=["main"]), "lists 'main'"),
    (lambda d: _nd(d, "arrive").update(present=["ada", "ada"]), "names a line twice"),
    (lambda d: _nd(d, "arrive").update(present="ada"), "must be a list"),
    (lambda d: _nd(d, "logbooks").update(flash="storm"), "flash is only for main-line events"),
    (lambda d: _nd(d, "arrive").update(flash="war"), "not one of the brief's flashbacks"),
    (lambda d: _nd(d, "council").update(flash="storm"), "must be consecutive"),
    (lambda d: d["brief"]["flashbacks"].append({"id": "ada", "label": "x"}), "already a line"),
    (lambda d: d["brief"]["flashbacks"].append({"id": "storm", "label": "x"}), "used twice"),
    (lambda d: d["brief"]["flashbacks"].append({"id": "later", "label": ""}), "needs a label"),
    (lambda d: d["brief"]["flashbacks"].append({"id": "later", "label": "x", "to": "arrive"}), "unknown keys"),
    (lambda d: d["brief"]["flashbacks"].append({"id": "Bad Id", "label": "x"}), "slug"),
    (lambda d: d["brief"].update(flashbacks={}), "must be a list"),
])
def test_bad_presence_and_flashbacks_are_refused(mutate, msg):
    d = _v2()
    mutate(d)
    b, nodes, _ = load_brief(d)
    with pytest.raises(BriefError, match=msg):
        validate_brief(b)
        validate_nodes(b, nodes)


def test_presence_and_flashbacks_need_lanes_mode():
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text())
    d["nodes"][0]["present"] = ["x"]
    b, nodes, _ = load_brief(d)
    with pytest.raises(BriefError, match="need mode 'lanes'"):
        validate_nodes(b, nodes)
    d = json.loads((ROOT / "samples" / "contracts_brief.json").read_text())
    d["brief"]["flashbacks"] = [{"id": "x", "label": "x"}]
    with pytest.raises(BriefError, match="need mode 'lanes'"):
        validate_brief(load_brief(d)[0])


def test_character_events_between_do_not_break_a_flashback():
    d = _v2()
    # a character's own event told between the two flashback events
    d["nodes"].insert(4, {"id": "aside", "act": 1, "tag": "", "title": "Ben, elsewhere", "desc": "x",
                          "line": "ben", "when": "1890-08"})
    b, nodes, _ = load_brief(d)
    validate_nodes(b, nodes)
    assert _payload(d)["flashbacks"][0]["nodes"] == ["great-storm", "lamp-dark"]


def test_flashback_warnings():
    d = _v2()
    _nd(d, "lamp-dark")["when"] = "1895"                       # later than where the story returns
    d["brief"]["flashbacks"].append({"id": "unused", "label": "Never told"})
    b, nodes, _ = load_brief(d)
    validate_brief(b)
    w = validate_nodes(b, nodes)
    assert any("flashback storm" in x and "'quay'" in x for x in w), w
    assert any("flashback unused: has no events" in x for x in w), w


def test_a_flashback_can_open_or_close_the_story():
    d = _v2()
    for i in ("arrive", "warning"):
        _nd(d, i)["flash"] = "storm"
        _nd(d, i)["when"] = "1869"
    for i in ("great-storm", "lamp-dark"):
        _nd(d, i).pop("flash")
    L = _payload(d)
    assert L["flashbacks"][0]["prev"] == "" and L["flashbacks"][0]["next"] == "great-storm"
    d = _v2()
    _nd(d, "relight")["flash"] = "storm"
    for i in ("great-storm", "lamp-dark"):
        _nd(d, i).pop("flash")
    assert _payload(d)["flashbacks"][0]["next"] == ""


def test_a_line_with_neither_from_nor_to_is_just_a_character():
    d = _v2()
    _nd(d, "logbooks")["line"] = ""
    for n in d["nodes"]:
        n.pop("present", None)
    b, nodes, _ = load_brief(d)
    w = validate_nodes(b, nodes)
    assert any("line ada: has no events yet and is on the page nowhere" in x for x in w)
    by = {l["id"]: l for l in _payload(d)["lines"]}
    assert by["ada"]["presence"] == [] and by["ada"]["span"] == [] and by["ada"]["from"] == ""


@pytest.mark.skipif(find_node() is None, reason="node not installed")
@pytest.mark.parametrize("sample", ["lanes_brief.json", "lanes_v2_brief.json"])
def test_the_page_derive_is_the_python_derive(sample, tmp_path):
    """window._altoLanesDerive recomputes exactly what lanes.derive did, also
    after an edit (one more character on the page, a flashback event back in
    the present)."""
    import subprocess
    from alto.build.lanes import LANES_DERIVE_JS, derive
    d = json.loads((ROOT / "samples" / sample).read_text())
    L = _payload(d)
    first_main = next(i for i in L["order"] if L["ev"][i]["l"] == "main")
    E = json.loads(json.dumps(L))
    E["ev"][first_main]["present"] = [l["id"] for l in E["lines"]][:1]
    for k in E["ev"].values():
        if k["flash"]:
            k["flash"] = ""
            break
    want = [L, derive(json.loads(json.dumps(E)))]
    js = ("var window={};" + LANES_DERIVE_JS + "var out=[];"
          + "".join(f"var X={json.dumps(x)};" "['order','lines','flashbacks'].forEach(function(k){ if(k!=='order') X[k].forEach(function(o){"
                    " delete o.events; delete o.presence; delete o.span; delete o.nodes; delete o.prev; delete o.next; }); });"
                    "out.push(window._altoLanesDerive(X, X.order.slice().reverse().reverse()));"
                    for x in (L, E))
          + "console.log(JSON.stringify(out));")
    f = tmp_path / "d.js"
    f.write_text(js, encoding="utf-8")
    got = json.loads(subprocess.check_output([find_node(), str(f)], timeout=60))
    assert got == json.loads(json.dumps(want))


@pytest.mark.skipif(find_node() is None, reason="node not installed")
def test_v2_page_passes_the_js_gate():
    html, _ = build_timeline(*load_brief(_v2()))
    assert verify_scripts(html, "timeline") == ([], [])


def _store(d):
    from tests.test_manual_edit import Store
    st = Store(d)
    st.doc["brief"]["timeline_id"] = "t1"
    return st


def _rebuilds(st):
    b, nodes, _ = load_brief({"brief": st.doc["brief"], "nodes": st.nodes, "connections": st.conns})
    validate_brief(b)
    validate_nodes(b, nodes)


def test_presence_flash_and_flashbacks_fold_into_the_draft():
    from alto.edits import fold
    st = _store(_v2())
    st.edits = {"v": 1, "ops": {
        # Ben on the page at the arrival too (sent in any order: compared as a set)
        "n|arrive|present": {"b": ["ada"], "v": ["ben", "ada"], "t": 1},
        # a new flashback, the arrival's neighbour... the quay told out of time
        "fb|fb-ab12c": {"b": None, "v": {"id": "fb-ab12c", "label": "That spring"}, "t": 2},
        "n|relight|flash": {"b": "", "v": "fb-ab12c", "t": 3},
        "n|relight|when": {"b": "1891-03", "v": "1890-12", "t": 4},
        "fb|storm": {"b": {"id": "storm", "label": "Twenty years earlier"},
                     "v": {"id": "storm", "label": "The storm"}, "t": 5},
        "n|warning|present": {"b": ["ada", "keeper"], "v": [], "t": 6}}}
    r = fold(st, "u", "t1")
    assert not r.get("error") and not r["conflicts"] and not r["gone"], r
    n = {x["id"]: x for x in st.nodes}
    assert n["arrive"]["present"] == ["ada", "ben"]                 # the brief's line order
    assert "present" not in n["warning"]
    assert n["relight"]["flash"] == "fb-ab12c"
    fbs = {f["id"]: f for f in st.doc["brief"]["flashbacks"]}
    assert fbs["fb-ab12c"] == {"id": "fb-ab12c", "label": "That spring"} and fbs["storm"]["label"] == "The storm"
    _rebuilds(st)


def test_a_changed_presence_since_is_a_conflict():
    from alto.edits import fold
    st = _store(_v2())
    st.edits = {"v": 1, "ops": {"n|arrive|present": {"b": ["ben"], "v": ["ada", "ben"], "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["n|arrive|present"]


def test_removing_a_flashback_or_a_line_takes_its_marks_with_it():
    from alto.edits import fold
    st = _store(_v2())
    st.edits = {"v": 1, "ops": {
        "fb|storm": {"b": {"id": "storm", "label": "Twenty years earlier"}, "v": None, "t": 1},
        "ln|keeper": {"b": {"id": "keeper", "label": "The keeper", "color": "#9a7b4f", "side": "above",
                            "from": "", "to": ""}, "v": None, "t": 2}}}
    r = fold(st, "u", "t1")
    assert not r.get("error") and not r["conflicts"], r
    assert "flashbacks" not in st.doc["brief"]
    assert not any(x.get("flash") for x in st.nodes)
    assert not any("keeper" in (x.get("present") or []) for x in st.nodes)
    assert "present" not in {x["id"]: x for x in st.nodes}["great-storm"]
    _rebuilds(st)


def test_marks_that_mean_nothing_any_more_are_dropped_not_refused():
    """An event moved onto a character's own line loses its presence and flash
    mark; a flashback event moved out of its run (to another unit) leaves it."""
    from alto.edits import fold
    st = _store(_v2())
    st.edits = {"v": 1, "ops": {
        "n|great-storm|line": {"b": "", "v": "keeper", "t": 1},
        "ua|lamp-dark": {"b": 1, "v": 2, "t": 2}}}
    r = fold(st, "u", "t1")
    assert not r.get("error"), r
    n = {x["id"]: x for x in st.nodes}
    assert n["great-storm"]["line"] == "keeper" and "present" not in n["great-storm"] and "flash" not in n["great-storm"]
    _rebuilds(st)


def test_tidy_keeps_only_the_first_run_of_a_flashback():
    from alto.build.lanes import tidy
    d = _v2()
    _nd(d, "council")["flash"] = "storm"
    assert tidy(d["brief"], d["nodes"]) == ["council"]
    assert "flash" not in _nd(d, "council") and _nd(d, "lamp-dark")["flash"] == "storm"


def test_set_lines_and_add_nodes_carry_presence_and_flashbacks(tmp_path):
    """The chat's way in: create_timeline with lines + flashbacks, add_nodes
    with present / flash, set_lines to change them later (on a folder)."""
    from alto import mcp_server as srv
    from alto.store.local import LocalStore
    srv.set_store(LocalStore(tmp_path))
    d = _v2()
    pid = srv.create_project("Stories", "a novel", "writing")["project_id"]
    tid = srv.create_timeline(pid, d["brief"])["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "notes.pdf", "kind": "notes"}], True)
    r = srv.add_nodes(tid, d["nodes"])
    assert "error" not in r, r
    bad = dict(_nd(d, "arrive"), flash="nope")
    assert "not one of the brief's flashbacks" in srv.add_nodes(tid, [bad])["message"]
    # a flashback still in use cannot be removed; one more can be added, the main line renamed
    r = srv.set_lines(tid, d["brief"]["lines"], flashbacks=[])
    assert r["error"] == "invalid_lines" and "storm" in r["message"]
    r = srv.set_lines(tid, d["brief"]["lines"] + [{"id": "mayor", "label": "The mayor"}],
                      flashbacks=d["brief"]["flashbacks"] + [{"id": "youth", "label": "Ada as a girl"}],
                      main_line="The novel")
    assert r["ok"] and r["lines"][-1] == "mayor" and r["flashbacks"] == ["storm", "youth"], r
    assert any("flashback youth: has no events" in w for w in r["warnings"])
    doc = srv.get_store().get_timeline(srv.uid(), tid)
    assert doc["brief"]["main_line"] == "The novel" and len(doc["brief"]["flashbacks"]) == 2
    srv.set_store(None)


# ── the pace of the story: node.gap ───────────────────────────────────────

def _story(gaps):
    brief = json.loads((ROOT / "samples" / "lanes_v2_brief.json").read_text())
    for n in brief["nodes"]:
        n.pop("when", None)                                      # undated: the pace is all the page has to go on
    for nid, g in gaps.items():
        next(n for n in brief["nodes"] if n["id"] == nid)["gap"] = g
    return brief


def test_a_gap_is_one_of_the_known_paces():
    brief = _story({})
    brief["nodes"][1]["gap"] = "soon"
    with pytest.raises(BriefError, match="gap"):
        _check(brief)


def test_a_gap_is_weighed_on_the_page_and_nothing_else_changes_without_one():
    brief = _story({})
    ids = [n["id"] for n in brief["nodes"]]
    plain = _ev(brief)
    assert all(plain[i]["g"] == 0 for i in ids)                 # no gap: an ordinary step
    quick = _ev(_story({ids[1]: "hours", ids[2]: "years"}))
    assert quick[ids[1]]["g"] == lanes.GAPS["hours"] < 1 < quick[ids[2]]["g"] == lanes.GAPS["years"]
    assert quick[ids[3]]["g"] == 0


def _check(brief):
    b, nodes, _ = load_brief(brief)
    return validate_brief(b) + validate_nodes(b, nodes)


def _ev(brief):
    b, nodes, conns = load_brief(brief)
    return json.loads(re.search(r"window\._ALTO_LANES=(\{.*?\});\n", build_timeline(b, nodes, conns)[0]).group(1))["ev"]


def test_gap_needs_lanes_mode():
    brief = json.loads((ROOT / "samples" / "lanes_v2_brief.json").read_text())
    brief["brief"]["mode"] = "linear"
    brief["brief"].pop("lines", None); brief["brief"].pop("flashbacks", None)
    for n in brief["nodes"]:
        for k in ("line", "when", "present", "flash"):
            n.pop(k, None)
    brief["nodes"][0]["gap"] = "day"
    with pytest.raises(BriefError, match="gap"):
        _check(brief)
