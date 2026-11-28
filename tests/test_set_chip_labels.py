"""set_chip_labels: sets ONLY the labels of existing chips (a case, a statute, an entity). An unknown id or a bad tag writes nothing, [] clears,
and the chip's name, sections and cite stay byte-identical (so a big axis is labelled without resending its records)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto import mcp_server as M  # noqa: E402


@pytest.fixture()
def tid():
    pid = M.create_project("Civ Pro", "1L", "studying")["project_id"]
    t = M.create_timeline(pid, {"title": "Civ Pro", "timeline_id": "cp", "mode": "outline", "columns": 5, "node_noun": "Concept",
                                "acts": [{"label": "UNIT ONE"}, {"label": "UNIT TWO"}],
                                "relations": [{"key": "spine", "label": "Contains"}]})
    assert not t.get("error"), t
    M.record_materials_consent(t["timeline_id"], ["my own outline"], True)
    r = M.set_axis_values(t["timeline_id"], 1, "Cases", "Case", [
        {"id": "erie", "name": "Erie R. Co. v. Tompkins (1938)", "sections": [{"h": "Holding", "t": "No federal general common law.", "prov": "quoted"}],
         "cite": {"p": "12"}},
        {"id": "swift", "name": "Swift v. Tyson (1842)"}], hide_nav=True)
    assert not r.get("error"), r
    r = M.set_entities(t["timeline_id"], [{"id": "erie-doc", "name": "Erie doctrine"}])
    assert not r.get("error"), r
    return t["timeline_id"]


def _brief(tid):
    return M.get_timeline(tid)["brief"]


def test_it_sets_only_the_labels_and_leaves_names_sections_and_cites_byte_identical(tid):
    before = _brief(tid)
    r = M.set_chip_labels(tid, {"erie": ["★", "R"], "swift": ["O"], "erie-doc": ["R"]})
    assert not r.get("error") and r["labelled"] == 3, r
    after = _brief(tid)
    cases = {v["id"]: v for v in after["axes"][0]["values"]}
    assert cases["erie"]["labels"] == ["★", "R"] and cases["swift"]["labels"] == ["O"]
    assert after["entities"][0]["labels"] == ["R"]
    strip = lambda b: json.dumps({**b, "axes": [{**a, "values": [{k: v for k, v in x.items() if k not in ("labels", "label")} for x in a["values"]]} for a in b["axes"]],
                                  "entities": [{k: v for k, v in e.items() if k not in ("labels", "label")} for e in b["entities"]]}, sort_keys=True)
    assert strip(before) == strip(after), "something besides the labels changed"


def test_an_unknown_id_is_an_error_and_writes_nothing(tid):
    before = json.dumps(_brief(tid), sort_keys=True)
    r = M.set_chip_labels(tid, {"erie": ["R"], "nope": ["H"]})
    assert r.get("error") == "unknown_chip" and "nope" in r["unknown"], r
    assert json.dumps(_brief(tid), sort_keys=True) == before


def test_a_bad_tag_is_an_error_and_writes_nothing(tid):
    before = json.dumps(_brief(tid), sort_keys=True)
    for bad in (["H", "R", "O"], ["TOOLONG"], [""]):
        r = M.set_chip_labels(tid, {"erie": ["R"], "swift": bad})
        assert r.get("error") == "invalid_labels", (bad, r)
    assert json.dumps(_brief(tid), sort_keys=True) == before


def test_an_empty_list_clears_a_chips_labels(tid):
    M.set_chip_labels(tid, {"erie": ["R"], "swift": ["O"]})
    r = M.set_chip_labels(tid, {"swift": []})
    assert not r.get("error") and r["cleared"] == 1, r
    cases = {v["id"]: v for v in _brief(tid)["axes"][0]["values"]}
    assert "labels" not in cases["swift"] and cases["erie"]["labels"] == ["R"]
