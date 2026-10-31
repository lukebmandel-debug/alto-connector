"""The PMA wall table (alto/buildings/pma_wall.json) stays consistent with the plan and the hosted images (data only; no renderer, no browser)."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "alto" / "buildings"


def _t():
    return json.loads((B / "pma_wall.json").read_text("utf-8"))


def test_every_row_hangs_in_a_real_room_and_is_not_a_duplicate():
    plan = json.loads((B / "pma_plan.json").read_text("utf-8"))
    rooms = {r["id"] for r in plan["rm"]}
    rows = _t()["rows"]
    assert len({r["key"] for r in rows}) == len(rows)
    assert all(r["rm"] in rooms for r in rows), [r["key"] for r in rows if r["rm"] not in rooms]


def test_only_a_public_domain_row_has_a_picture_and_it_is_sourced():
    art = json.loads((B / "pma_art.json").read_text("utf-8"))["images"]
    for r in _t()["rows"]:
        assert r["lic"] in ("pd", "pd-no-image", "in-copyright", "unknown")
        if r["img"]:
            assert r["img"] in art
        if r["img"] or r["lic"] == "pd":                                  # a picture hangs (or may hang) only for a pd row with a Commons file
            assert r["lic"] == "pd" and r["died"] and r["died"] < 1956 and r["commons"].startswith("File:") and re.fullmatch(r"\d{4}-\d\d-\d\d", r["read_on"])
        else:
            assert r["lic"] != "pd"
        if r["lic"] == "pd-no-image":
            assert r["died"] and r["died"] < 1956 and not r["commons"]
        if r["lic"] == "in-copyright":
            assert r["died"] and r["died"] >= 1956
        assert r["title"] and r["gs"] in _t()["gallery_sources"]


def test_a_gallery_maps_to_one_plan_room_and_pc_is_known():
    for r in _t()["rows"]:
        assert r["pc"] in ("room", "cand", "area")


def test_the_table_is_what_the_generator_writes(tmp_path):
    dest = tmp_path / "pma_wall.json"                    # a real file: Windows has no /dev/stdout
    subprocess.run([sys.executable, str(ROOT / "docs" / "building-palace" / "build_pma_wall.py"), "--out", str(dest)], capture_output=True, text=True, check=True)
    assert json.loads(dest.read_text("utf-8").splitlines()[0]) == _t()
