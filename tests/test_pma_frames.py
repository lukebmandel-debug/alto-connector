"""The PMA's labelled frames (no browser): every painting in the wall table hangs in its gallery with a frame and a label side, a picture only where the row is public domain
and hosted, nothing overlaps on a wall, and the plan stays valid."""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs  # noqa: E402
from alto.buildings import pma, pma_art, pma_frames  # noqa: E402

PLAN = pma.plan()
SLOTS = {s["id"]: s for s in PLAN["sl"]}
ROWS = [r for r in pma_frames.wall_rows() if r["kind"] == "painting"]


def test_every_painting_row_hangs_as_a_frame_in_its_own_room():
    assert len(ROWS) == 69
    for r in ROWS:
        s = SLOTS[pma_frames.slot_id(r["key"])]
        assert s["rm"] == r["rm"] and s["fr"] in ("g", "w") and s["lb"] in ("r", "l", "b"), r["key"]
        assert s["work"]["title"] == r["title"] and s["work"]["lic"] == r["lic"]
        assert (s["fr"] == "w") == ((re.search(r"\d{4}", r["year"]) and int(re.search(r"\d{4}", r["year"]).group(0))) >= 1900), r["key"]
    assert len({s["id"] for s in PLAN["sl"]}) == len(PLAN["sl"])
    warns = bs.validate_plan(PLAN)
    assert not [w for w in warns if "outside room" in w or "floating" in w or "hangs" in w or "sl[" in w], warns


def test_a_picture_hangs_only_for_a_public_domain_row_that_is_hosted():
    hosted = {v["url"] for v in pma_art.manifest()["images"].values()}
    for r in ROWS:
        w = SLOTS[pma_frames.slot_id(r["key"])]["work"]
        if r["lic"] == "pd" and r["img"]:
            assert w["img"] in hosted and w["cl"], r["key"]
        else:
            assert "img" not in w and "cl" not in w, r["key"]                  # in-copyright, unknown and pd-no-image rows: the labelled empty frame
    assert sum(1 for r in ROWS if r["img"]) == 49 == len(hosted)
    assert "img" not in SLOTS["sl-rivera-sugar-cane"]["work"] and SLOTS["sl-rivera-sugar-cane"]["fr"] == "w"


def _edge_u(s, rooms):
    room = rooms[s["rm"]]
    for e in pma_frames._edges(room):
        if pma_frames._on_edge(s, e):
            return e, pma_frames._u(s["p"], e)
    return None, None


def test_nothing_overlaps_on_a_wall_and_every_label_has_its_room():
    rooms = {r["id"]: r for r in PLAN["rm"]}
    for rid in {s["rm"] for s in PLAN["sl"] if s.get("fr")}:
        for e in pma_frames._edges(rooms[rid]):
            on = sorted(((pma_frames._u(s["p"], e), s) for s in PLAN["sl"] if s["rm"] == rid and "sz" in s and pma_frames._on_edge(s, e)), key=lambda t: t[0])
            for (u0, a), (u1, b) in zip(on, on[1:]):
                right = pma_frames.GAP + pma_frames.PLATE_W if a.get("fr") and a.get("lb") == "r" else 0
                assert u1 - b["sz"][0] / 2 - (u0 + a["sz"][0] / 2 + right) > -1e-6, (a["id"], b["id"])
    for s in PLAN["sl"]:
        if s.get("fr"):
            e, u = _edge_u(s, rooms)
            assert e is not None, s["id"]
            lo = min(pma_frames._u(e["a"], e), pma_frames._u((e["a"][0] + e["dir"][0] * e["L"], e["a"][1] + e["dir"][1] * e["L"]), e))
            hi = lo + e["L"]
            assert u - s["sz"][0] / 2 >= lo + pma_frames.CLEAR - 0.31 and u + s["sz"][0] / 2 <= hi - pma_frames.CLEAR + 0.31, s["id"]        # a plan-placed work may sit closer to a corner


def test_the_labels_that_say_right_have_the_room_and_the_slot_count():
    assert len(PLAN["sl"]) == 128 and not [s for s in PLAN["sl"] if s["id"].startswith("sl-") and len(s["id"]) > 32]
    assert math.isclose(pma_frames.PLATE_W, 0.5)
