"""The numbers the page shows on its cards ("8.g", a timeline's "3.4") come back
from get_nodes / get_timeline beside each id, from the build's own code, and stand
for the card's id in get_nodes and add_nodes. Local test store only."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from alto import mcp_server as srv  # noqa: E402
from alto.build.builder import build_timeline, card_numbers, load_brief  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
LANES = json.loads((ROOT / "samples" / "lanes_brief.json").read_text(encoding="utf-8"))


def _page(sample):
    html, _ = build_timeline(*load_brief(json.loads(json.dumps(sample))))
    return html


def test_outline_numbers_match_the_page():
    html = _page(OUTLINE)
    m = re.search(r"window\._ALTO_OUTLINE=\{num:(\{.*?\}),label:", html)
    shown = json.loads(m.group(1))
    b, nodes, _ = load_brief(json.loads(json.dumps(OUTLINE)))
    got = card_numbers(b, nodes)
    assert got == shown and len(shown) == len(OUTLINE["nodes"])
    assert any(re.match(r"^\d+\.[a-z]", v) for v in got.values())


def test_lanes_numbers_match_the_page():
    html = _page(LANES)
    m = re.search(r"const ACT_SEQS = (\[.*?\n\]);", html, re.S)
    seqs = json.loads(m.group(1))
    shown = {i: f"{a + 1}.{k + 1}" for a, ids in enumerate(seqs) for k, i in enumerate(ids)}
    b, nodes, _ = load_brief(json.loads(json.dumps(LANES)))
    assert card_numbers(b, nodes) == shown and len(shown) == len(LANES["nodes"])


@pytest.fixture
def tid(tmp_path):
    srv.set_store(LocalStore(tmp_path))
    pid = srv.create_project("Law School", "1L year", "studying")["project_id"]
    t = srv.create_timeline(pid, OUTLINE["brief"])["timeline_id"]
    srv.record_materials_consent(t, [{"name": "notes.pdf", "kind": "notes"}], True)
    srv.set_entities(t, OUTLINE["brief"].get("entities") or [])
    assert "error" not in srv.add_nodes(t, json.loads(json.dumps(OUTLINE["nodes"])))
    yield t
    srv.set_store(None)


def test_get_nodes_and_get_timeline_carry_numbers(tid):
    b, nodes, _ = load_brief(json.loads(json.dumps(OUTLINE)))
    want = card_numbers(b, nodes)
    got = srv.get_nodes(tid)["nodes"]
    assert {n["id"]: n["num"] for n in got} == want
    assert list(got[0])[:2] == ["id", "num"]
    assert srv.get_nodes(tid, fields=["title"])["nodes"][0].keys() == {"id", "num", "title"}
    assert srv.get_timeline(tid)["node_numbers"] == want


def test_lookup_by_number_in_get_and_upsert(tid):
    nums = {n["id"]: n["num"] for n in srv.get_nodes(tid)["nodes"]}
    kid = next(i for i, v in nums.items() if re.match(r"^\d+\.[a-z]$", v))
    num = nums[kid]
    r = srv.get_nodes(tid, ids=[num.upper()])
    assert [n["id"] for n in r["nodes"]] == [kid]
    node = next(n for n in srv.get_nodes(tid, ids=[kid])["nodes"])
    upd = {k: v for k, v in node.items() if k != "num"} | {"id": num, "title": node["title"] + " (edited)"}
    r = srv.add_nodes(tid, [upd])
    assert r.get("updated") == [kid], r
    assert srv.get_nodes(tid, ids=[kid])["nodes"][0]["title"].endswith("(edited)")
    # a new child whose parent is named by its number
    new = {"id": "new-kid", "act": node["act"], "tag": "x", "title": "New kid", "desc": "d", "parent": num}
    assert srv.add_nodes(tid, [new]).get("added") == ["new-kid"]
    assert srv.get_nodes(tid, ids=["new-kid"])["nodes"][0]["parent"] == kid


def test_unknown_and_ambiguous_numbers_are_clear(tid, monkeypatch):
    assert srv.get_nodes(tid, ids=["99.zz"])["error"] == "unknown_number"
    r = srv.add_nodes(tid, [{"id": "x-1", "act": 0, "tag": "t", "title": "T", "desc": "d", "parent": "99.zz"}])
    assert r["error"] == "unknown_number" and "parent" in r["message"]
    ids = [n["id"] for n in srv.get_nodes(tid)["nodes"]][:2]
    monkeypatch.setattr(srv, "_card_numbers", lambda t: {ids[0]: "1.a", ids[1]: "1.a"})
    assert srv.get_nodes(tid, ids=["1.a"])["error"] == "ambiguous_number"
    # an id always wins, and a plain unknown id is still just missing
    assert srv.get_nodes(tid, ids=[ids[0], "no-such"])["missing"] == ["no-such"]
