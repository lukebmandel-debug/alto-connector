"""Manual edit mode: the page side (alto/build/manual_edit.py) and folding the
edits into the draft (alto/edits.py)."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.sanitize import sanitize_brief, clean_linked_markup, SourceMap  # noqa: E402
from alto.edits import page_to_source, fold, published  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"


def _d():
    return json.loads(OUTLINE.read_text(encoding="utf-8"))


# ── page markup back to authored markup ─────────────────────────────────────

SOURCES = [{"id": "notes-1", "name": "Notes", "url": "https://docs.google.com/document/d/abc/edit", "local": ""},
           {"id": "notes-2", "name": "Notes 2", "url": "", "local": "/tmp/x.docx"},
           {"id": "notes-3", "name": "Notes 3", "url": "https://docs.google.com/document/d/zzz/edit", "local": "/tmp/y.docx"}]
LINK_TYPES = {"formation": "node", "definiteness": "node", "lucy-v-zehmer": "env", "formation-doc": "char"}
AUTHORED = [
    "Plain words & an ampersand < less than.",
    'See <a href="#" onclick="showDetail(\'node\',\'definiteness\')">Definiteness</a> first.',
    'A case: <a href="#" onclick="showDetail(\'env\',\'lucy-v-zehmer\')"><em>Lucy</em> v. Zehmer</a>.',
    'Out: <a href="https://example.com/a?b=1&c=2">a site</a>, <a href="mailto:x@y.z">mail</a>.',
    'From <a href="https://docs.google.com/document/d/abc/edit">my notes</a> and <a href="src:notes-2">the docx</a>'
    ' and <a href="src:notes-3">both</a>.',
    "<b>Bold</b>, <i>it</i>, <ul><li>one</li><li>two <strong>2</strong></li></ul><p class=\"x\">para</p>",
    'Nested <span class="note">span <a href="#" onclick="showDetail(\'node\',\'formation\')">link</a></span> end',
    "Line<br>break<br/>and <sup>1</sup>",
]


@pytest.mark.parametrize("src", AUTHORED)
def test_page_text_goes_back_to_the_authored_form_exactly(src):
    sm = SourceMap(SOURCES)
    page, _ = clean_linked_markup(src, LINK_TYPES, sm)
    back = page_to_source(page)
    again, _ = clean_linked_markup(back, LINK_TYPES, SourceMap(SOURCES))
    assert again == page, (page, back)


def test_links_made_in_the_page_survive_a_rebuild():
    sm = SourceMap(SOURCES)
    page = ('Read <span class="alto-link" data-sd-type="node" data-sd-id="definiteness">this</span> and '
            '<a href="https://example.com/x" class="note-link" target="_blank" rel="noopener">that</a>.')
    again, w = clean_linked_markup(page_to_source(page), LINK_TYPES, sm)
    assert again == page and not w


# ── the page carries what edit mode needs ───────────────────────────────────

def test_every_page_carries_the_edit_module_and_section_map():
    html, _ = build_timeline(*load_brief(_d()))
    assert '<script id="alto-manual">' in html and '<style id="alto-manual-css">' in html
    m = re.search(r'window._ALTO_EDK=(\{.*?\});</script>', html)
    edk = json.loads(m.group(1))
    # formation has one authored section and a Source notes section the build adds
    assert edk["n"]["formation"][0] == 0


def test_the_section_map_skips_what_the_build_adds():
    d = _d()
    d["brief"]["source_docs"] = [{"id": "s1", "name": "Doc", "url": "https://example.com/doc"}]
    d["nodes"][0]["sources"] = ["s1"]
    d["nodes"][0]["sections"].append({"h": "Two", "t": "second"})
    d["nodes"][0]["sections"].insert(1, {"h": "Empty", "t": ""})
    html, _ = build_timeline(*load_brief(d))
    edk = json.loads(re.search(r'window._ALTO_EDK=(\{.*?\});</script>', html).group(1))
    # page list: Test, Two, Source notes → own indexes 0, 2, and -1 for the build's own
    assert edk["n"]["formation"] == [0, 2, -2]          # -2: after its own (Source notes)


def test_a_share_carries_a_share_key_so_the_module_stands_down():
    """manual_edit.MANUAL_JS returns at once on an 's-' key; a share's page is
    re-stamped with one, and nothing in the module names the timeline itself."""
    from alto.build.reidentify import reidentify
    from alto.build.manual_edit import MANUAL_JS
    html, _ = build_timeline(*load_brief(_d()))
    shared = reidentify(html, "abcdefghijklmnopqrstuv")
    m = re.search(r'window._ALTO_EDIT=(\{.*?\});</script>', shared)
    assert json.loads(m.group(1))["key"].startswith("alto-doc-s-")
    assert "TID.indexOf('s-') === 0) return;" in MANUAL_JS


# ── folding edits into the draft ────────────────────────────────────────────

class Store:
    def __init__(self, d):
        self.doc = {"timeline_id": "t1", "brief": copy.deepcopy(d["brief"]), "consent": {"sources": []}}
        self.nodes = copy.deepcopy(d["nodes"])
        self.edits = None
        self.put_n = []
        self.conns = copy.deepcopy(d.get("connections") or [])

    # Like CloudStore's cache within a call: the SAME objects every time, so a
    # fold that changed them in place (rather than through put_*) shows up.
    def get_timeline(self, uid, tid):
        return self.doc

    def put_timeline(self, uid, tid, doc):
        self.doc = copy.deepcopy(doc)

    def list_nodes(self, uid, tid):
        return self.nodes

    def put_nodes(self, uid, tid, nodes):
        self.put_n += [n["id"] for n in nodes]
        by = {n["id"]: n for n in nodes}
        self.nodes = [copy.deepcopy(by.get(n["id"], n)) for n in self.nodes]

    def get_connections(self, uid, tid):
        return self.conns

    def put_connections(self, uid, tid, conns):
        self.conns = copy.deepcopy(conns)

    def get_edits(self, uid, tid):
        return copy.deepcopy(self.edits)

    def put_edits(self, uid, tid, data):
        self.edits = copy.deepcopy(data)


def _node(st, i):
    return next(n for n in st.nodes if n["id"] == i)


def test_fold_writes_matching_edits_and_reports_conflicts():
    st = Store(_d())
    title0 = _node(st, "definiteness")["title"]
    st.edits = {"v": 1, "ops": {
        "n|definiteness|title": {"b": title0, "v": "Certainty", "t": 1},
        "n|formation|s|0|h": {"b": "Test", "v": "The Test", "t": 2},
        "n|formation|s|0|t": {"b": _node(st, "formation")["sections"][0]["t"],
                              "v": 'Offer + <span class="alto-link" data-sd-type="node" data-sd-id="definiteness">acceptance</span>.',
                              "t": 3},
        "n|preliminary-negotiations|desc": {"b": "not what it says", "v": "x", "t": 4},
        "u|0|label": {"b": st.doc["brief"]["acts"][0]["label"], "v": "Making a Contract", "t": 5},
        "p|definiteness|shift": {"b": None, "v": [40, 120.5], "t": 6},
        "n|gone-node|title": {"b": "a", "v": "b", "t": 7},
        "n|formation|tag": {"b": "x", "v": "y", "t": 8, "done": True},
    }}
    r = fold(st, "u", "t1")
    assert r["folded"] == 5
    assert r["conflicts"] == ["n|preliminary-negotiations|desc"]
    assert r["gone"] == ["n|gone-node|title"]
    assert _node(st, "definiteness")["title"] == "Certainty"
    f = _node(st, "formation")
    assert f["sections"][0]["h"] == "The Test"
    assert f["sections"][0]["t"] == "Offer + <a href=\"#\" onclick=\"showDetail('node','definiteness')\">acceptance</a>."
    assert st.doc["brief"]["acts"][0]["label"] == "Making a Contract"
    assert st.doc["brief"]["placement"]["definiteness"]["shift"] == [40, 120.5]
    assert _node(st, "preliminary-negotiations")["desc"] != "x"
    assert _node(st, "formation")["tag"] != "y"            # a done edit is never applied again
    # the rebuilt page shows exactly what the page showed
    b, ns, _ = load_brief({"brief": st.doc["brief"], "nodes": st.nodes})
    sanitize_brief(b, ns)
    assert next(n for n in ns if n.id == "formation").sections[0].t == st.edits["ops"]["n|formation|s|0|t"]["v"]
    # folding again changes nothing
    before = (copy.deepcopy(st.doc), copy.deepcopy(st.nodes))
    r2 = fold(st, "u", "t1")
    assert r2["folded"] == 0 and r2["already_in_draft"] == 5
    assert (st.doc, st.nodes) == before
    build_timeline(*load_brief({"brief": st.doc["brief"], "nodes": st.nodes}))


def test_a_tree_step_and_an_entity_page_fold():
    d = _d()
    d["nodes"][0]["sections"].append({"h": "Tree", "t": "", "tree": {"nodes": [
        {"id": "q", "title": "Is there an offer?"}, {"id": "y", "parent": "q", "edge": "Yes", "title": "Offer"}]}})
    d["brief"]["entities"][0].setdefault("sections", []).append({"h": "How", "t": "By assent."})
    st = Store(d)
    eid = d["brief"]["entities"][0]["id"]
    j = len(d["brief"]["entities"][0]["sections"]) - 1
    st.edits = {"v": 1, "ops": {
        "dt|n-formation-1|y|edge": {"b": "Yes", "v": "Plainly yes", "t": 1},
        "dt|n-formation-1|q|title": {"b": "Is there an offer?", "v": "An offer?", "t": 2},
        f"c|{eid}|s|{j}|t": {"b": "By assent.", "v": "By <b>mutual</b> assent.", "t": 3},
        f"c|{eid}|name": {"b": d["brief"]["entities"][0]["name"], "v": "Formation (renamed)", "t": 4},
    }}
    r = fold(st, "u", "t1")
    assert r["folded"] == 4, r
    tree = _node(st, "formation")["sections"][1]["tree"]["nodes"]
    assert tree[0]["title"] == "An offer?" and tree[1]["edge"] == "Plainly yes"
    ent = st.doc["brief"]["entities"][0]
    assert ent["sections"][j]["t"] == "By <b>mutual</b> assent." and ent["name"] == "Formation (renamed)"


def test_published_marks_carried_edits_done_and_keeps_the_rest():
    st = Store(_d())
    t0 = _node(st, "definiteness")["title"]
    st.edits = {"v": 1, "ops": {"n|definiteness|title": {"b": t0, "v": "Certainty", "t": 1},
                                "n|formation|title": {"b": "nope", "v": "zzz", "t": 2}}}
    fold(st, "u", "t1")
    assert published(st, "u", "t1") == 1
    ops = st.edits["ops"]
    assert ops["n|definiteness|title"]["done"] is True and ops["n|definiteness|title"]["t"] == 1
    assert not ops["n|formation|title"].get("done")      # a conflict is never marked done


def test_nothing_to_fold_writes_nothing():
    st = Store(_d())
    assert fold(st, "u", "t1") is None
    st.edits = {"v": 1, "ops": {"n|formation|title": {"t": 1, "done": True}}}
    assert fold(st, "u", "t1") is None and st.put_n == []


def test_a_shift_dragged_back_home_removes_the_hint():
    st = Store(_d())
    st.doc["brief"]["placement"] = {"definiteness": {"shift": [10, 10], "arrange": "row"}}
    st.edits = {"v": 1, "ops": {"p|definiteness|shift": {"b": [10, 10], "v": None, "t": 1}}}
    assert fold(st, "u", "t1")["folded"] == 1
    assert st.doc["brief"]["placement"]["definiteness"] == {"arrange": "row"}


def test_fold_never_changes_what_the_store_handed_it():
    st = Store(_d())
    held_doc, held_nodes = st.doc, st.nodes
    snap = (copy.deepcopy(held_doc), copy.deepcopy(held_nodes))
    t0 = _node(st, "formation")["sections"][0]["t"]
    st.put_nodes = lambda uid, tid, nodes: None           # writes go nowhere
    st.put_timeline = lambda uid, tid, doc: None
    st.edits = {"v": 1, "ops": {"n|formation|s|0|t": {"b": t0, "v": "changed", "t": 1},
                                "u|0|label": {"b": held_doc["brief"]["acts"][0]["label"], "v": "U", "t": 2}}}
    assert fold(st, "u", "t1")["folded"] == 2
    assert (held_doc, held_nodes) == snap



# ── 1.9.48: the Overview, section order, whole trees, connection reasons ────

from alto.edits import order_sig, tree_list, _View  # noqa: E402
from alto.build.manual_edit import jhash  # noqa: E402

LINEAR = ROOT / "samples" / "contracts_brief.json"


def _view(st):
    return _View(st.doc, st.nodes, st.conns)


def test_a_new_section_order_with_new_sections_folds():
    st = Store(_d())
    st.nodes[0]["sections"].append({"h": "Two", "t": "second"})
    v = _view(st)
    f = v.owner("n", "formation")
    sig = order_sig(f)
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": ["1", "new-abc123", "0"], "t": 5},
        "n|formation|s|new-abc123|h": {"b": "", "v": "Fresh", "t": 6},
        "n|formation|s|new-abc123|t": {"b": "", "v": 'See <span class="alto-link" data-sd-type="node" data-sd-id="definiteness">this</span>.', "t": 7},
        "n|formation|s|0|h": {"b": "Test", "v": "The Test", "t": 3},     # by its original place
    }}
    r = fold(st, "u", "t1")
    assert r["folded"] == 4 and not r["conflicts"] and not r["gone"], r
    hs = [s["h"] for s in _node(st, "formation")["sections"]]
    assert hs == ["Two", "Fresh", "The Test"]
    assert "showDetail('node','definiteness')" in _node(st, "formation")["sections"][1]["t"]
    assert all(o.get("f") for o in st.edits["ops"].values())
    # built again: nothing more to do, and the marks clear on publish
    assert fold(st, "u", "t1")["folded"] == 0
    assert published(st, "u", "t1") == 4
    build_timeline(*load_brief({"brief": st.doc["brief"], "nodes": st.nodes}))


def test_an_order_made_against_another_page_is_a_conflict():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"n|formation|order": {"b": "deadbeef", "v": [], "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["n|formation|order"] and _node(st, "formation")["sections"]


def test_a_whole_tree_folds_and_a_step_edited_after_it_too():
    d = _d()
    d["nodes"][0]["sections"].append({"h": "Tree", "t": "", "tree": {"label": "L", "nodes": [
        {"id": "q", "title": "Q?"}, {"id": "y", "parent": "q", "edge": "Yes", "title": "Y"}]}})
    st = Store(d)
    lst = tree_list(_view(st).owner("n", "formation").sections[1])
    new = copy.deepcopy(lst) + [{"i": "s-new1", "p": "q", "t": "New step"}]
    new[0], new[1] = new[0], new[1]
    st.edits = {"v": 1, "ops": {
        "dt|n-formation-1|tree": {"b": jhash(json.dumps(lst, ensure_ascii=False, separators=(",", ":"))), "v": new, "t": 1},
        "dt|n-formation-1|s-new1|title": {"b": "New step", "v": "No", "t": 2}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 2 and not r["conflicts"], r
    tree = _node(st, "formation")["sections"][1]["tree"]
    assert tree["label"] == "L" and [n["id"] for n in tree["nodes"]] == ["q", "y", "s-new1"]
    assert tree["nodes"][2] == {"id": "s-new1", "title": "No", "parent": "q"}


def test_a_tree_that_would_not_build_is_refused():
    d = _d()
    d["nodes"][0]["sections"].append({"h": "Tree", "t": "", "tree": {"nodes": [{"id": "q", "title": "Q?"}]}})
    st = Store(d)
    lst = tree_list(_view(st).owner("n", "formation").sections[1])
    bad = [{"i": "a", "t": "A"}, {"i": "b", "t": "B"}]          # two roots
    st.edits = {"v": 1, "ops": {"dt|n-formation-1|tree": {
        "b": jhash(json.dumps(lst, ensure_ascii=False, separators=(",", ":"))), "v": bad, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["dt|n-formation-1|tree"]


def test_an_authored_overview_folds_with_its_links():
    d = _d()
    st = Store(d)
    ov = _view(st).b.overview_html
    page = ov.replace("organised by", "arranged by") + '<p>More: <span class="ov-node-link"><button class="ov-node-btn" onclick="showDetail(\'node\',\'definiteness\')"></button>a chip</span>.</p>'
    st.edits = {"v": 1, "ops": {"ov|html": {"b": jhash(ov), "v": page, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 1, r
    again = _view(st).b.overview_html
    assert "arranged by" in again and "showDetail('node','definiteness')" in again
    assert _view(st).norm_ov(again) == _view(st).norm_ov(page)
    # stale signature: conflict
    st.edits["ops"]["ov|html"] = {"b": "0", "v": "<p>x</p>", "t": 2}
    assert fold(st, "u", "t1")["conflicts"] == ["ov|html"]


def test_a_composed_overview_folds_into_the_units():
    d = _d()
    d["brief"]["overview_html"] = ""
    st = Store(d)
    a0 = st.doc["brief"]["acts"][0]
    st.edits = {"v": 1, "ops": {
        "u|0|summary": {"b": a0.get("summary") or "", "v": "First paragraph.\n\nSecond.", "t": 1},
        "u|0|short": {"b": a0.get("short") or "", "v": "Making It", "t": 2}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 2, r
    assert st.doc["brief"]["acts"][0]["summary"] == "First paragraph.\n\nSecond."
    html, _ = build_timeline(*load_brief({"brief": st.doc["brief"], "nodes": st.nodes}))
    assert "<p>First paragraph.</p>\n<p>Second.</p>" in html


def test_a_connection_reason_folds():
    d = json.loads(LINEAR.read_text(encoding="utf-8"))
    st = Store(d)
    c = st.conns[0]
    st.edits = {"v": 1, "ops": {f"cx|{c[0]}|{c[1]}|0": {"b": "", "v": "Because <b>this</b>.", "t": 1}}}
    if len(c) > 3 and c[3]:
        st.edits["ops"][f"cx|{c[0]}|{c[1]}|0"]["b"] = _view(st).conns[0][3]
    r = fold(st, "u", "t1")
    assert r["folded"] == 1, r
    assert st.conns[0][3] == "Because <b>this</b>."


def test_the_page_and_the_connector_sign_alike(tmp_path):
    """jh() in the page and jhash() here, over the same strings, under node."""
    import shutil, subprocess
    node = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
    if not Path(node).is_file():
        pytest.skip("no node")
    from alto.build.manual_edit import MANUAL_JS
    m = re.search(r"function jh\(s\)\{.*?\}", MANUAL_JS)
    words = ["", "abc", "Café — ✎ “quotes” \\ \" \n\t", "😀 astral", "x" * 5000]
    f = tmp_path / "h.js"
    f.write_text(m.group(0) + "\nconsole.log(JSON.stringify(" + json.dumps(words) + ".map(jh)));", encoding="utf-8")
    out = json.loads(subprocess.check_output([node, str(f)]))
    assert out == [jhash(w) for w in words]
