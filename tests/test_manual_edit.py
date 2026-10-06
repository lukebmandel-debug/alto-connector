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
        have = {n["id"] for n in self.nodes}
        self.nodes = ([copy.deepcopy(by.get(n["id"], n)) for n in self.nodes]
                      + [copy.deepcopy(n) for n in nodes if n["id"] not in have])

    def delete_nodes(self, uid, tid, ids):
        self.nodes = [n for n in self.nodes if n["id"] not in ids]

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


# ── 1.9.49: cards, filters, kinds of section, files on this computer ────────

def _build(st):
    return build_timeline(*load_brief({"brief": st.doc["brief"], "nodes": st.nodes,
                                       "connections": st.conns}))


def test_a_card_added_on_the_page_folds_with_its_words_and_sections():
    st = Store(_d())
    from alto.build.manual_edit import jhash
    spec = {"p": "offer", "a": 0, "t": "New concept", "g": "Concept", "d": "", "c": "var(--x)"}
    st.edits = {"v": 1, "ops": {
        "nn|card-ab12cd": {"b": None, "v": spec, "t": 1},
        "n|card-ab12cd|title": {"b": "New concept", "v": "Counter-offers", "t": 2},
        "n|card-ab12cd|desc": {"b": "", "v": "A reply that changes the terms.", "t": 3},
        "n|card-ab12cd|order": {"b": jhash("[]"), "v": ["new-x1y2z3"], "t": 4},
        "n|card-ab12cd|s|new-x1y2z3|h": {"b": "", "v": "Rule", "t": 5},
        "n|card-ab12cd|s|new-x1y2z3|t": {"b": "", "v": "It rejects the offer.", "t": 6},
        "n|card-ab12cd|s|new-x1y2z3|p": {"b": "", "v": "notes", "t": 7},
    }}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    assert r["cards_added"] == [{"id": "card-ab12cd", "title": "Counter-offers"}]
    n = _node(st, "card-ab12cd")
    assert (n["parent"], n["act"], n["tag"], n["desc"]) == ("offer", 0, "Concept", "A reply that changes the terms.")
    assert n["sections"] == [{"h": "Rule", "t": "It rejects the offer.", "prov": "notes"}]
    html, _ = _build(st)
    assert "Counter-offers" in html and "From your notes" in html
    # until it is folded a publish leaves its words alone; once folded, done
    assert published(st, "u", "t1") == len(st.edits["ops"])


def test_words_for_a_card_not_yet_in_the_draft_are_not_marked_done():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "nn|card-zz99aa": {"b": None, "v": {"p": "offer", "a": 0, "t": "X", "g": "", "d": ""}, "t": 1},
        "n|card-zz99aa|title": {"b": "X", "v": "Y", "t": 2}}}
    assert published(st, "u", "t1") == 0


def test_a_card_under_a_card_that_is_gone_is_a_conflict():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"nn|card-aaaa11": {"b": None, "v": {"p": "nope", "a": 0, "t": "X"}, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["conflicts"] == ["nn|card-aaaa11"] and not any(n["id"] == "card-aaaa11" for n in st.nodes)


def test_a_card_removed_on_the_page_goes_with_its_lines_but_never_a_parent():
    st = Store(_d())
    st.conns = [["revocation", "mailbox-rule", "spine"], ["offer", "acceptance", "spine"]]
    st.edits = {"v": 1, "ops": {"nd|revocation": {"b": 0, "v": 1, "t": 1},
                                "nd|offer": {"b": 0, "v": 1, "t": 2}}}
    r = fold(st, "u", "t1")
    assert r["cards_removed"] == ["revocation"] and "nd|offer" in r["conflicts"], r
    ids = {n["id"] for n in st.nodes}
    assert "revocation" not in ids and "offer" in ids
    assert st.conns == [["offer", "acceptance", "spine"]]
    _build(st)


def test_a_card_folded_then_taken_out_on_the_same_page_is_removed():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"nn|card-bb22cc": {"b": None, "v": {"p": "offer", "a": 0, "t": "X"}, "t": 1}}}
    fold(st, "u", "t1")
    assert any(n["id"] == "card-bb22cc" for n in st.nodes)
    st.edits["ops"]["nn|card-bb22cc"] = {"b": None, "v": None, "t": 5}
    r = fold(st, "u", "t1")
    assert r.get("cards_removed") == ["card-bb22cc"] and not any(n["id"] == "card-bb22cc" for n in st.nodes)


def test_filters_of_your_own_and_filters_taken_out_fold_and_build():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "fl|list": {"b": [], "v": [{"id": "exam", "name": "Exam"}], "t": 1},
        "fn|offer": {"b": [], "v": ["exam"], "t": 2},
        "fn|revocation": {"b": [], "v": ["exam"], "t": 3},
        "fx|off": {"b": [], "v": ["filter:depth"], "t": 4}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 4 and not r["conflicts"], r
    assert st.doc["brief"]["flags"] == [{"id": "exam", "name": "Exam"}]
    assert st.doc["brief"]["filters_off"] == ["filter:depth"]
    assert _node(st, "offer")["flags"] == ["exam"]
    html, _ = _build(st)
    from tests.panel import sections
    keys = [s["key"] for s in sections(html)]
    assert "flags" in keys and not any(s["label"] == "Depth" for s in sections(html)), keys
    # taking the filter away again drops it from the cards too
    st.edits = {"v": 1, "ops": {"fl|list": {"b": [{"id": "exam", "name": "Exam"}], "v": [], "t": 9}}}
    fold(st, "u", "t1")
    assert "flags" not in _node(st, "offer") or _node(st, "offer")["flags"] == []
    _build(st)


def test_a_filter_list_changed_meanwhile_is_a_conflict():
    st = Store(_d())
    st.doc["brief"]["flags"] = [{"id": "a", "name": "A"}]
    st.edits = {"v": 1, "ops": {"fl|list": {"b": [], "v": [{"id": "b", "name": "B"}], "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["fl|list"]


def test_a_new_section_with_a_tree_folds_with_its_steps():
    st = Store(_d())
    v = _view(st)
    sig = order_sig(v.owner("n", "formation"))
    cur = [str(j) for j in range(len(_node(st, "formation")["sections"]))]
    st.edits = {"v": 1, "ops": {
        "n|formation|order": {"b": sig, "v": cur + ["new-t1t2t3"], "t": 1},
        "n|formation|s|new-t1t2t3|h": {"b": "", "v": "Is there a deal?", "t": 2},
        "dt|n-formation-new-t1t2t3|tree": {"b": "new", "v": [{"i": "s-aaaa", "t": "First question"},
                                                              {"i": "s-bbbb", "t": "Yes", "p": "s-aaaa"}], "t": 3},
        "dt|n-formation-new-t1t2t3|s-aaaa|title": {"b": "First question", "v": "Was there an offer?", "t": 4},
        "dt|n-formation-new-t1t2t3|s-bbbb|edge": {"b": "", "v": "yes", "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    sec = _node(st, "formation")["sections"][-1]
    assert sec["h"] == "Is there a deal?" and sec["t"] == ""
    assert [(n["id"], n["title"], n.get("edge")) for n in sec["tree"]["nodes"]] == [
        ("s-aaaa", "Was there an offer?", None), ("s-bbbb", "Yes", "yes")]
    html, _ = _build(st)
    assert '"t":"Was there an offer?"' in html


def test_a_link_to_a_file_on_this_computer_is_found_and_kept(tmp_path, monkeypatch):
    import alto.edits as E
    (tmp_path / "Documents" / "Contracts").mkdir(parents=True)
    f = tmp_path / "Documents" / "Contracts" / "Offer letter.pdf"
    f.write_bytes(b"%PDF-1.4 x")
    real = E.find_file
    monkeypatch.setattr(E, "find_file", lambda name, size=None, mod=None, home=None:
                        real(name, size, mod, home=str(tmp_path)))
    st = Store(_d())
    t0 = _node(st, "formation")["sections"][0]["t"]
    page, _ = clean_linked_markup(t0, {})
    link = ('<a href="#" class="note-link" data-file="file-abcdef12" data-file-name="Offer letter.pdf" '
            'data-file-size="10">the letter</a>')
    st.edits = {"v": 1, "ops": {"n|formation|s|0|t": {"b": page, "v": page + " See " + link + ".", "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["folded"] == 1 and not r.get("files_not_found"), r
    assert st.doc["brief"]["linked_files"] == [{"id": "file-abcdef12", "name": "Offer letter.pdf", "local": str(f)}]
    assert 'href="src:file-abcdef12"' in _node(st, "formation")["sections"][0]["t"]
    html, _ = _build(st)
    assert 'data-src="file-abcdef12"' in html
    assert json.dumps(str(f), ensure_ascii=False)[1:-1] in html      # the page's _ALTO_LOCAL


def test_a_link_to_a_file_that_cannot_be_found_waits(tmp_path, monkeypatch):
    import alto.edits as E
    monkeypatch.setattr(E, "find_file", lambda *a, **k: None)
    st = Store(_d())
    t0 = _node(st, "formation")["sections"][0]["t"]
    page, _ = clean_linked_markup(t0, {})
    link = '<a href="#" class="note-link" data-file="file-zzzzzz99" data-file-name="Lost.pdf">x</a>'
    st.edits = {"v": 1, "ops": {"n|formation|s|0|t": {"b": page, "v": page + link, "t": 1}}}
    r = fold(st, "u", "t1")
    assert r["files_not_found"] == ["Lost.pdf"] and r["folded"] == 0
    assert _node(st, "formation")["sections"][0]["t"] == t0
    assert not st.edits or not st.edits["ops"]["n|formation|s|0|t"].get("f")


def test_find_file_prefers_the_same_size_then_the_nearest_date(tmp_path):
    import os
    from alto.edits import find_file
    for d, body, mt in (("Desktop/a", b"12345", 1000), ("Documents/b", b"123", 5000), ("Downloads/c", b"123", 9000)):
        (tmp_path / d).mkdir(parents=True)
        p = tmp_path / d / "Notes.docx"
        p.write_bytes(body)
        os.utime(p, (mt, mt))
    assert Path(find_file("Notes.docx", 3, 5100 * 1000, home=str(tmp_path))) == tmp_path / "Documents/b/Notes.docx"
    assert Path(find_file("Notes.docx", 5, None, home=str(tmp_path))) == tmp_path / "Desktop/a/Notes.docx"
    assert find_file("nothing.pdf", home=str(tmp_path)) is None
    assert find_file("../etc/passwd", home=str(tmp_path)) is None


def test_filters_off_and_linked_files_are_checked():
    from alto.build.brief import BriefError, validate_brief
    d = _d()
    d["brief"]["filters_off"] = ["entity", "filter:depth:level-1", "lines:spine"]
    validate_brief(load_brief(d)[0])
    for bad in (["<script>"], ["entity:"], "entity"):
        d["brief"]["filters_off"] = bad
        with pytest.raises(BriefError):
            validate_brief(load_brief(d)[0])
    d["brief"]["filters_off"] = []
    d["brief"]["linked_files"] = [{"id": "file-abc123", "name": "x", "local": "relative/path"}]
    with pytest.raises(BriefError):
        validate_brief(load_brief(d)[0])


def test_the_page_carries_what_cards_and_filters_need():
    d = _d()
    d["brief"]["flags"] = [{"id": "exam", "name": "Exam"}]
    d["nodes"][1]["flags"] = ["exam"]
    d["brief"]["filters_off"] = ["filter:depth"]
    html, _ = build_timeline(*load_brief(d))
    edk = json.loads(re.search(r"window\._ALTO_EDK=(\{.*?\});</script>", html).group(1).replace("<\\/", "</"))
    assert edk["fl"] == [{"id": "exam", "name": "Exam"}] and edk["fln"] == {d["nodes"][1]["id"]: ["exam"]}
    assert edk["foff"] == ["filter:depth"] and edk["mode"] == "outline"
    assert any(s["label"] == "Depth" for s in edk["fall"]["sections"])        # can be put back
    from tests.panel import sections
    assert not any(s["label"] == "Depth" for s in sections(html))


def test_a_preview_cannot_open_a_linked_file():
    from alto.build.single_file import preview
    b, nodes, conns = load_brief(_d())
    html, _ = build_timeline(b, nodes, conns)
    page = preview(b, html)
    assert "function showBlob(file, name, w){ if(w) w.close(); }" in page



# ── 1.9.51: moving a card under another, units, sub-chips ───────────────────

def test_a_card_moved_under_another_takes_its_progeny_into_the_new_unit():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "rp|offer": {"b": "formation", "v": "reliance", "t": 1},
        "p|offer|shift": {"b": None, "v": None, "t": 1}}}
    st.doc["brief"].setdefault("placement", {})["offer"] = {"shift": [40, 90], "arrange": "row"}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    for i in ("offer", "revocation", "option-contracts", "unilateral-offers"):
        assert _node(st, i)["act"] == 1, i
    assert _node(st, "offer")["parent"] == "reliance"
    pl = st.doc["brief"]["placement"]["offer"]
    assert "shift" not in pl and pl["arrange"] == "row" and pl["order"] == 3   # last under reliance
    html, _ = _build(st)
    o = html[html.index("window._ALTO_OUTLINE="):]
    assert '"offer": "reliance"' in o[o.index("parent:"):]
    assert re.search(r'"reliance": \[[^\]]*"offer"\]', o[o.index("kids:"):])
    assert published(st, "u", "t1") == 2


def test_a_move_under_its_own_card_or_from_a_changed_parent_is_refused():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"rp|offer": {"b": "formation", "v": "revocation", "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["rp|offer"]
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"rp|offer": {"b": "acceptance", "v": "reliance", "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["rp|offer"]
    assert _node(st, "offer")["parent"] == "formation"


def test_a_unit_added_on_the_page_folds_with_its_name_and_first_card():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "nu|unit-ab12cd": {"b": None, "v": {"n": 5, "c": "#2fb380", "l": "New unit"}, "t": 1},
        "nl|unit-ab12cd": {"b": "New unit", "v": "UNIT SIX — THIRD PARTIES", "t": 3},
        "nn|card-ee11ff": {"b": None, "v": {"p": "", "a": "unit-ab12cd", "t": "Third parties", "g": "", "d": ""}, "t": 2},
        "nn|card-ee22ff": {"b": None, "v": {"p": "card-ee11ff", "a": "unit-ab12cd", "t": "Assignment"}, "t": 4},
        "u|0|label": {"b": "UNIT ONE — FORMATION", "v": "UNIT ONE — MAKING A CONTRACT", "t": 5}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    acts = st.doc["brief"]["acts"]
    assert len(acts) == 6 and acts[5]["label"] == "UNIT SIX — THIRD PARTIES" and acts[5]["id"] == "unit-ab12cd"
    assert acts[0]["label"] == "UNIT ONE — MAKING A CONTRACT"
    assert _node(st, "card-ee11ff")["act"] == 5 and _node(st, "card-ee22ff")["parent"] == "card-ee11ff"
    html, _ = _build(st)
    assert '"uids":["","","","","","unit-ab12cd"]' in html          # the page knows it has it
    assert "THIRD PARTIES" in html
    # folding again changes nothing
    r2 = fold(st, "u", "t1")
    assert r2 is None or r2["folded"] == 0


def test_chips_added_taken_off_and_made_on_the_page_fold():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "ne|c|good-faith": {"b": None, "v": {"name": "Good Faith", "color": "#22b8cf"}, "t": 1},
        "ne|env|new-case": {"b": None, "v": {"name": "Smith v. Jones"}, "t": 1},
        "ch|offer|chars": {"b": ["formation"], "v": ["formation", "good-faith"], "t": 2},
        "ch|formation|envs": {"b": ["lucy-v-zehmer"], "v": ["new-case"], "t": 3}}}
    r = fold(st, "u", "t1")
    assert not r["conflicts"] and not r["gone"], r
    ents = {e["id"]: e for e in st.doc["brief"]["entities"]}
    assert ents["good-faith"]["name"] == "Good Faith" and ents["good-faith"]["color"] == "#22b8cf"
    assert any(v["id"] == "new-case" for v in st.doc["brief"]["axes"][0]["values"])
    assert _node(st, "offer")["entity_ids"] == ["formation", "good-faith"]
    assert _node(st, "formation")["axis1_values"] == ["new-case"]
    html, _ = _build(st)
    assert "Good Faith" in html and "Smith v. Jones" in html
    assert published(st, "u", "t1") == 4


def test_a_chip_list_changed_meanwhile_is_a_conflict_and_unknown_chips_drop():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"ch|offer|chars": {"b": ["remedies"], "v": ["formation", "nope"], "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["ch|offer|chars"]
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"ch|offer|chars": {"b": ["formation"], "v": ["formation", "nope"], "t": 1}}}
    fold(st, "u", "t1")
    assert _node(st, "offer")["entity_ids"] == ["formation"]


def test_the_page_carries_unit_ids_and_chip_kinds():
    html, _ = build_timeline(*load_brief(_d()))
    m = re.search(r"window\._ALTO_EDK=(\{.*?\});</script>", html)
    edk = json.loads(m.group(1).replace("<\\/", "</"))
    assert edk["uids"] == [""] * 5
    assert [k["f"] for k in edk["chipk"]] == ["chars", "envs"] and edk["chipk"][0]["fk"] == "entity"
    assert edk["glyph"]


# ── 1.9.52: any card removed, units deleted, chips and categories from the
#    top bar, the glyph library, card sizes ─────────────────────────────────

def _ok(st):
    r = fold(st, "u", "t1")
    assert r and not r["conflicts"] and not r["gone"] and not r.get("error"), r
    return r


def test_a_top_card_removed_hands_its_place_to_its_first_card():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "rp|definiteness": {"b": "formation", "v": "", "t": 1},
        "rp|preliminary-negotiations": {"b": "formation", "v": "definiteness", "t": 2},
        "rp|offer": {"b": "formation", "v": "definiteness", "t": 2},
        "rp|acceptance": {"b": "formation", "v": "definiteness", "t": 2},
        "nd|formation": {"b": 0, "v": 1, "t": 3}}}
    r = _ok(st)
    assert "formation" in r["cards_removed"]
    assert not any(n["id"] == "formation" for n in st.nodes)
    assert "parent" not in _node(st, "definiteness") and _node(st, "offer")["parent"] == "definiteness"
    assert _node(st, "revocation")["parent"] == "offer"          # their own cards stay with them
    _build(st)


def test_a_card_becomes_a_top_card_only_in_place_of_one_taken_out():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"rp|definiteness": {"b": "formation", "v": "", "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["rp|definiteness"]
    assert _node(st, "definiteness")["parent"] == "formation"


def test_a_card_and_all_under_it_removed_together():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {k: {"b": 0, "v": 1, "t": 1} for k in
                                ("nd|offer", "nd|revocation", "nd|option-contracts", "nd|unilateral-offers")}}
    r = _ok(st)
    assert sorted(r["cards_removed"]) == ["offer", "option-contracts", "revocation", "unilateral-offers"]
    _build(st)


def test_a_unit_deleted_with_its_cards_moved_under_another_units_top_card():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "rp|consideration": {"b": "", "v": "formation", "t": 1},
        "ud|1": {"b": "UNIT TWO — CONSIDERATION", "v": 1, "t": 2}}}
    r = _ok(st)
    assert r["units_deleted"] == ["UNIT TWO — CONSIDERATION"]
    acts = [a["label"] for a in st.doc["brief"]["acts"]]
    assert acts == ["UNIT ONE — FORMATION", "UNIT THREE — DEFENSES", "UNIT FOUR — TERMS & PERFORMANCE", "UNIT FIVE — REMEDIES"]
    assert _node(st, "consideration")["parent"] == "formation"
    assert _node(st, "promissory-estoppel")["act"] == 0 and _node(st, "defenses")["act"] == 1 and _node(st, "remedies")["act"] == 3
    _build(st)


def test_a_unit_deleted_with_its_cards_in_a_new_unit():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "nu|unit-aa11bb": {"b": None, "v": {"n": 9, "c": "#2fb380", "l": "New unit"}, "t": 1},
        "nl|unit-aa11bb": {"b": "New unit", "v": "UNIT SIX — DEFENSES, AGAIN", "t": 3},
        "ua|defenses": {"b": [2, "UNIT THREE — DEFENSES"], "v": "unit-aa11bb", "t": 2},
        "ud|2": {"b": "UNIT THREE — DEFENSES", "v": 1, "t": 2}}}
    r = _ok(st)
    acts = [a["label"] for a in st.doc["brief"]["acts"]]
    assert len(acts) == 5 and acts[-1] == "UNIT SIX — DEFENSES, AGAIN" and "UNIT THREE — DEFENSES" not in acts
    assert _node(st, "defenses")["act"] == 4 and _node(st, "within-the-statute")["act"] == 4
    assert _node(st, "performance")["act"] == 2
    assert r["cards_moved_to_unit"][0]["id"] == "defenses"
    _build(st)


def test_a_unit_delete_is_refused_when_the_unit_changed_or_still_holds_cards():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"ud|1": {"b": "UNIT TWO — SOMETHING ELSE", "v": 1, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["ud|1"]
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"ud|1": {"b": "UNIT TWO — CONSIDERATION", "v": 1, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["ud|1"]          # its cards are still in it
    assert len(st.doc["brief"]["acts"]) == 5
    # a move into a unit whose number now names another one is refused
    st = Store(_d())
    st.edits = {"v": 1, "ops": {"ua|defenses": {"b": [2, "UNIT TWO — CONSIDERATION"], "v": 4, "t": 1}}}
    assert fold(st, "u", "t1")["conflicts"] == ["ua|defenses"]


def test_a_chip_and_a_category_taken_out_of_the_timeline():
    st = Store(_d())
    on = [n["id"] for n in st.nodes if "remedies" in (n.get("entity_ids") or [])]
    st.edits = {"v": 1, "ops": {
        "xe|c|remedies": {"b": 0, "v": 1, "t": 1},
        "xa|axis1": {"b": "Cases", "v": 1, "t": 2}}}
    r = _ok(st)
    assert on and r["chips_removed"] == ["Remedies"] and r["categories_removed"] == ["Cases"]
    assert not any(e["id"] == "remedies" for e in st.doc["brief"]["entities"])
    assert st.doc["brief"]["axes"] == []
    assert all("remedies" not in (n.get("entity_ids") or []) and not n.get("axis1_values") for n in st.nodes)
    _build(st)


def test_a_category_made_on_the_page_with_a_chip_from_the_glyph_library():
    from alto.build.glyphs import LIBRARY
    star = LIBRARY[4]["s"]
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "na|axis2": {"b": None, "v": {"l": "Themes", "one": "Theme"}, "t": 1},
        "ne|theme|fairness": {"b": None, "v": {"name": "Fairness", "color": "#22b8cf", "svg": star}, "t": 2},
        "ne|c|good-faith": {"b": None, "v": {"name": "Good Faith", "svg": "<svg onload=alert(1)></svg>"}, "t": 2},
        "ch|offer|themes": {"b": [], "v": ["fairness"], "t": 3}}}
    r = _ok(st)
    ax = st.doc["brief"]["axes"]
    assert r["categories_added"] == ["Themes"] and ax[1]["label"] == "Themes" and ax[1]["singular"] == "Theme"
    assert ax[1]["values"][0]["symbol_svg"] == star
    ents = {e["id"]: e for e in st.doc["brief"]["entities"]}
    assert not ents["good-faith"].get("symbol_svg")             # only the library's glyphs, never page markup
    assert _node(st, "offer")["axis2_values"] == ["fairness"]
    html, _ = _build(st)
    assert "Fairness" in html and "onload" not in html


def test_the_glyph_library_is_fifty_distinct_glyphs():
    from alto.build.glyphs import LIBRARY, inner, from_library
    assert len(LIBRARY) == 50
    assert len({inner(g["s"]) for g in LIBRARY}) == 50 and len({g["n"] for g in LIBRARY}) == 50
    assert all(g["s"].startswith('<svg viewBox="0 0 20 20"') and "currentColor" in g["s"] for g in LIBRARY)
    assert from_library(LIBRARY[0]["s"]) and not from_library("<svg></svg>") and not from_library(None)


def test_a_card_size_set_on_the_page_folds_and_builds():
    st = Store(_d())
    st.edits = {"v": 1, "ops": {
        "sz|offer": {"b": None, "v": {"w": 400, "h": 300}, "t": 1},
        "sz|acceptance": {"b": None, "v": {"w": 9999, "h": -5}, "t": 1}}}
    r = _ok(st)
    cs = st.doc["brief"]["card_size"]
    assert cs["offer"] == {"w": 400, "h": 300} and cs["acceptance"] == {"w": 520, "h": 40}
    assert sorted(c["id"] for c in r["cards_resized"]) == ["acceptance", "offer"]
    html, _ = _build(st)
    assert "html:not(.mobile) #node-offer .node-card{width:400px;min-height:300px;}" in html
    m = re.search(r"window\._ALTO_EDK=(\{.*?\});</script>", html)
    assert json.loads(m.group(1).replace("<\\/", "</"))["sz"]["offer"] == {"w": 400, "h": 300}
    # a card taken out takes its size with it
    st.edits = {"v": 1, "ops": {"nd|offer": {"b": 0, "v": 1, "t": 5}, "nd|revocation": {"b": 0, "v": 1, "t": 5},
                                "nd|option-contracts": {"b": 0, "v": 1, "t": 5}, "nd|unilateral-offers": {"b": 0, "v": 1, "t": 5}}}
    _ok(st)
    assert "offer" not in st.doc["brief"]["card_size"]


def test_card_size_is_checked():
    from alto.build.brief import BriefError, validate_brief
    for bad in ({"w": 100}, {"w": 300, "depth": 2}, {"h": True}):
        d = _d()
        d["brief"]["card_size"] = {"offer": bad}
        with pytest.raises(BriefError, match="card_size offer"):
            validate_brief(load_brief(d)[0])
    d = _d()
    d["brief"]["card_size"] = {"offer": {"w": 300}}
    validate_brief(load_brief(d)[0])


def test_the_page_carries_the_glyphs_axes_and_sizes():
    html, _ = build_timeline(*load_brief(_d()))
    m = re.search(r"window\._ALTO_EDK=(\{.*?\});</script>", html)
    edk = json.loads(m.group(1).replace("<\\/", "</"))
    assert len(edk["glyphs"]) == 50 and edk["nax"] == 1 and edk["sz"] == {}
    from alto.build.manual_edit import MANUAL_JS
    for need in ("function withGlyph(", "function deleteUnit(", "function navSync(", "function chipPop(",
                 "function startResize(", "function growFor(", "function chipMenu("):
        assert need in MANUAL_JS, need
