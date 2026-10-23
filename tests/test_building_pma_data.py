"""The curated Philadelphia Museum of Art plan (alto/buildings/pma.py): structure, sources, numbers, art, size budget, node assignment, the tool and hosting. No browser."""
import gzip
import json
import math
import re
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import buildings, mcp_server as srv, publish_static  # noqa: E402
from alto.build import building_schema as bs, palace_building_asset as pba  # noqa: E402
from alto.build.builder import load_brief  # noqa: E402
from alto.buildings import pma, pma_art  # noqa: E402
from tests.test_building_palace_tools import NODES, _timeline, local_store  # noqa: E402,F401

PLAN = pma.plan()
ROOMS = {r["id"]: r for r in PLAN["rm"]}
ELEV = {lv["id"]: lv["e"] for lv in PLAN["lv"]}


def _bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return max(xs) - min(xs), max(ys) - min(ys)


def _point_at(w, a):
    pts = w["p"] + ([w["p"][0]] if w.get("loop") else [])
    run = 0
    for p, q in zip(pts, pts[1:]):
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        if run + L >= a - 1e-9 and L > 0:
            t = (a - run) / L
            return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]
        run += L
    return pts[-1]


def _jpeg_size(b):
    i = 2
    while i < len(b):
        marker = b[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    raise AssertionError("no SOF")


# ── structure ────────────────────────────────────────────────────────────────

def test_the_plan_validates_and_is_the_pma():
    warns = bs.validate_plan(PLAN)
    assert not [w for w in warns if "outside room" in w or "floating" in w or "hangs" in w], warns
    assert PLAN["id"] == "pma" and PLAN["kind"] == "museum" and PLAN["geo"]["north"] == 44
    assert [lv["id"] for lv in PLAN["lv"]] == ["g", "l1", "l2", "l3"]
    assert [lv["lb"] for lv in PLAN["lv"]] == ["G", "1", "2", "3"]               # the visitor map's names
    assert ELEV["g"] < ELEV["l1"] < ELEV["l2"] < ELEV["l3"]
    note = PLAN["n"]
    assert "visitor map" in note and "basement = level 1" in note and "first floor = level 2" in note and "second floor = level 3" in note and "not on the 1928" in note
    s = bs.summary(PLAN)
    assert s["rooms"] >= 150 and s["walls"] >= 400 and s["stairs"] >= 12 and s["slots"] >= 40 and s["columns"] >= 100
    for lv in ("g", "l1", "l2", "l3"):
        assert sum(1 for r in PLAN["rm"] if r["l"] == lv) >= 5 and any(w["l"] == lv for w in PLAN["wl"])
    assert bs.plan_hash(PLAN) == bs.plan_hash(pma.plan())                           # deterministic


def test_no_room_polygon_crosses_itself_and_every_id_is_unique():
    for r in PLAN["rm"]:
        assert not bs.self_crossing(r["p"]) and (r.get("gp") or abs(bs.area(r["p"])) > 0.5), r["id"]
    for kind in ("rm", "wl", "st", "cols", "fx", "sl", "en"):
        ids = [e["id"] for e in PLAN.get(kind) or []]
        assert len(ids) == len(set(ids)), kind
    assert not bs.self_crossing(PLAN["ex"]["sh"][0]["p"])


def test_level_links_are_stitched_and_every_level_is_reachable():
    graph = {lv: set() for lv in ELEV}
    for s in PLAN["st"]:
        assert s["from"] in ELEV and s["to"] in ELEV and s["from"] != s["to"], s["id"]
        assert s["tp"] and s["tb"], s["id"]                                         # the upper end exists and says how it is known
        assert abs(s["dz"] - (ELEV[s["to"]] - ELEV[s["from"]])) < 0.011, s["id"]
        cx = sum(p[0] for p in s["tp"]) / len(s["tp"]); cy = sum(p[1] for p in s["tp"]) / len(s["tp"])
        assert any(r["l"] == s["to"] and (bs.inside(r["p"], [cx, cy]) or bs.dist_to_edge(r["p"], [cx, cy]) <= 4.0) for r in PLAN["rm"]), f"{s['id']} lands beside no room of {s['to']}"
        graph[s["from"]].add(s["to"]); graph[s["to"]].add(s["from"])
    seen, todo = set(), ["l2"]
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n); todo += graph[n]
    assert seen == set(ELEV)
    traced = [s for s in PLAN["st"] if s["tb"].startswith("traced")]
    assert len(traced) >= 8 and any(s["id"] == "l2-gsh-stair" for s in traced)


def test_every_door_connects_something():
    shell = PLAN["ex"]["sh"][0]["p"]
    by = {}
    for r in PLAN["rm"]:
        if not r.get("ov") or r["l"] == "g":                  # level G is all published-figure rooms; its doorways are where two of them meet
            by.setdefault(r["l"], []).append(r["p"])
    n = 0
    for w in PLAN["wl"]:
        for o in w.get("o", []):
            if o["k"] == "window":
                continue
            n += 1
            pt = _point_at(w, o["a"])
            assert any(bs.dist_to_edge(p, pt) <= 3.0 for p in by.get(w["l"], [])) or bs.dist_to_edge(shell, pt) <= 3.0, (w["id"], o)
    assert n >= 150


# ── sizes and measured spaces ────────────────────────────────────────────────

def test_the_great_stair_hall_and_the_other_measured_spaces_match_the_published_dimensions():
    gsh = ROOMS["l2-gsh"]
    ns, ew = _bbox(gsh["p"])[1], _bbox(gsh["p"])[0]
    assert abs(ns - 29.14) < 0.4 and abs(ew - 29.17) < 0.4                          # 95'7 1/8" x 95'8 9/16"
    bal = ROOMS["l3-gsh-balcony"]
    assert abs(_bbox(bal["p"])[1] - 29.31) < 0.4 and abs(_bbox(bal["p"])[0] - 34.73) < 0.4
    forum = ROOMS["g-forum"]
    assert abs(_bbox(forum["p"])[0] - 25.91) < 0.2 and abs(_bbox(forum["p"])[1] - 13.72) < 0.2 and abs(forum["ch"] - 40 * 0.3048) < 0.02    # 45 x 85 x 40 ft
    assert abs(ROOMS["g-walk-s"]["ch"] - 24 * 0.3048) < 0.05                        # the vault, ~24 ft
    assert abs(_bbox(ROOMS["l1-lenfest"]["p"])[1] - 21.18) < 0.2 and abs(_bbox(ROOMS["l1-lenfest"]["p"])[0] - 15.16) < 0.2
    assert abs(_bbox(ROOMS["l3-sg-cloister"]["p"])[0] - 14.31) < 0.05
    terr = next(t for t in PLAN["ex"]["tr"] if t["id"] == "east-terrace")
    assert sorted(round(d, 1) for d in _bbox(terr["p"])) == sorted([round(230.619 * 0.3048, 1), round(226.831 * 0.3048, 1)])
    for r in (gsh, bal, forum, ROOMS["l1-lenfest"]):
        assert r["pd"] and r["hb"] and r["hc"] == 1 or r["id"] == "g-forum"
    assert gsh["ch"] == 17 and gsh["hc"] == 1 and "photo" in gsh["hb"]              # a photo estimate, marked as one


def test_the_rocky_steps_the_entrances_and_the_shell():
    flights = [s for s in PLAN["ex"]["stp"] if s["id"].startswith("rocky-")]
    assert sorted(s["n"] for s in flights) == [7, 13, 13, 13, 13, 13] and sum(s["n"] for s in flights) == 72
    assert len([t for t in PLAN["ex"]["tr"] if t["id"].startswith("rocky-landing")]) == 5
    assert all(abs((s["z1"] - s["z0"]) / s["n"] - 0.127) < 0.003 for s in flights)   # 5 in risers
    names = {e["id"]: e for e in PLAN["en"]}
    assert {"l2-east", "west", "north"} <= set(names) and names["l2-east"]["l"] == "l2" and names["west"]["l"] == "l1" and names["north"]["l"] == "g"
    shell = PLAN["ex"]["sh"][0]
    assert shell["m"] == "limestone" and len(shell["p"]) == 34 and "osm" in shell["s"]


def test_diana_and_the_thirteen_tapestries():
    diana = next(f for f in PLAN["fx"] if f["id"] == "gsh-diana")
    assert abs(diana["sz"][2] - (14.5 * 0.3048)) < 0.01 and diana["k"] == "statue" and any(f["k"] == "plinth" for f in PLAN["fx"])
    tap = [s for s in PLAN["sl"] if s["id"].startswith("sl-const-")]
    assert len(tap) == 13 and all(s["rm"] == "l3-gsh-balcony" and "of 13" in s["work"]["title"] and "img" not in s["work"] for s in tap)
    assert all("Barberini" in s["work"]["artist"] for s in tap)


def test_size_budget_and_the_stored_brief():
    name, text = bs.hosted_json(PLAN)
    gz = len(gzip.compress(text.encode("utf-8"), 9, mtime=0))
    assert gz < 400_000 and len(text) < 1_000_000 and gz < 120_000                  # (about 31 KB today)
    assert len(bs.pack(PLAN)) < 200_000                                             # what set_up_building stores with the timeline
    assert re.fullmatch(r"plan-[0-9a-f]{12}\.json", name)


# ── sources, credits, licences ───────────────────────────────────────────────

def test_credits_and_licences_are_present_and_in_the_blueprint_footer():
    cr = " ".join(pma.credits())
    for want in ("Architectural Forum", "OpenStreetMap contributors", "ODbL", "Wikimedia Commons", "PMA visitor map", "public domain"):
        assert want in cr, want
    lic = {sid: l for sid, _t, l in pma.licences()}
    assert "ODbL" in lic["osm"] and "public domain" in lic["af1928"] and "facts only" in lic["pma-map"] and "facts" in lic["pma-events"]
    for s in PLAN["src"]:
        assert s.get("lic") and s["k"] in bs.SRC_KINDS, s["id"]
    cited = {x for e in PLAN["rm"] + PLAN["wl"] + PLAN["sl"] for x in e.get("s", [])}
    assert {"af1928", "osm", "pma-map", "pma-events", "pma-press", "commons-art"} <= cited
    assert "bl-foot" in pba.BUILDING_ASSET and "x.cr" in pba.BUILDING_ASSET          # the footer is built from the sources' credit lines
    assert (ROOT / "alto" / "buildings" / "README-pma.md").is_file()


def test_every_hosted_image_has_a_licence_a_size_and_a_credit():
    m = pma_art.manifest()
    files = dict(pma_art.files())
    assert len(m["images"]) >= 30 and set(files) == {v["name"] for v in m["images"].values()}
    total = 0
    banned = ("duchamp", "brancusi", "rivera", "calder", "fernandez", "puryear", "odita", "plensa", "weiwei", "gross", "saint-gaudens")
    for k, im in m["images"].items():
        assert im["licence"].startswith("Public domain") and im["commons"].startswith("https://commons.wikimedia.org/wiki/File:") and im["source_credit"] and im["artist_died"] < 1956
        assert pma_art.ART_RE.match(im["name"])
        assert not any(b in (im["artist"] + im["title"]).lower() for b in banned)
        w, h = _jpeg_size(files[im["name"]])
        assert max(w, h) <= 512, k
        total += im["bytes"]
    assert total < 2_500_000                                                        # ~36 small JPEGs, about 1.8 MB in all
    gal = {s["work"]["img"]: s.get("gl") for s in PLAN["sl"] if "img" in s["work"]}
    for im in m["images"].values():                                                 # each image hangs in the gallery its PMA object page names
        assert gal[im["url"]] == im["gallery"], im["title"]
    used = {s["work"]["img"] for s in PLAN["sl"] if "img" in s["work"]}
    assert used == {v["url"] for v in m["images"].values()}                         # every image is on a slot, every slot image is hosted
    assert {n for n in files} == {u.rsplit("/", 1)[1] for u in used}
    for s in PLAN["sl"]:
        if "img" in s["work"]:
            assert "commons-art" in s["s"] and s["work"]["img"].startswith("/bart/")


# ── gallery numbers, areas ───────────────────────────────────────────────────

def test_gallery_numbers_are_only_defensible_matches():
    numbered = [r for r in PLAN["rm"] if r.get("no")]
    nums = [r["no"] for r in numbered]
    assert len(nums) == len(set(nums)) and len(numbered) >= 50
    for r in numbered:
        assert r["ca"] and (r.get("gm") in ("tracer-unique", "resolved-by-evidence", "sequence-consistent")), r["id"]
        if r.get("gm") != "sequence-consistent":
            assert r["ty"] in ("gallery", "court"), r["id"]
    assert ROOMS["l3-sg-cloister"]["no"] == "304" and ROOMS["l3-sg-cloister"]["gm"] == "resolved-by-evidence"
    # unique candidates whose numbers fall in order along their enfilade are numbered (1928 names are not evidence); an out-of-order pair stays unnumbered
    for rid, no in (("l3-n-13", "362"), ("l3-n-14", "361"), ("l3-n-dutch", "355"), ("l3-sw-33", "326"), ("l3-n-other-eur", "363")):
        assert ROOMS[rid]["no"] == no and ROOMS[rid]["gm"] == "sequence-consistent", rid
    for rid in ("l3-s-24", "l3-s-late-goth-link"):               # 307, 300 beside 314: out of order
        assert not ROOMS[rid].get("no") and ROOMS[rid]["gm"].startswith("left-unnumbered"), rid
    # ambiguous rooms keep every candidate and no number
    amb = ROOMS["l2-s-court"]
    assert not amb.get("no") and {"211", "213"} <= set(amb["cand"])
    assert ROOMS["l2-s-court"]["gm"].startswith("left-unnumbered")
    # period rooms: about 45 in the PMA's guide, those that sit in a traced room carry their installation name
    named = [r for r in numbered if r["id"].startswith("l3-") and r["n"] != f"Gallery {r['no']}"]
    assert len(named) >= 10
    assert ROOMS["l3-s-23"]["no"] == "314" and ROOMS["l3-s-23"]["n"] == "Late Gothic Room"


def test_collection_areas_colour_the_rooms():
    legend = {a["id"]: a for a in PLAN["ca"]}
    assert len(legend) == 13 and all(re.fullmatch(r"#[0-9a-f]{6}", a["c"]) for a in legend.values()) and len({a["c"] for a in legend.values()}) == 13
    for r in PLAN["rm"]:
        assert r.get("ca") is None or r["ca"] in legend, r["id"]
    expect = {"220": "am1850", "251": "imp", "252": "imp", "223": "pdp", "275": "mod", "304": "eu1100", "334": "asia", "350": "eu1500", "385": "amper", "202": "am1850"}
    got = {r["no"]: r["ca"] for r in PLAN["rm"] if r.get("no")}
    for no, area in expect.items():
        if no in got:
            assert got[no] == area, no
    assert sum(1 for r in PLAN["rm"] if r.get("ca")) >= 60


# ── art slots ────────────────────────────────────────────────────────────────

def test_art_slots_only_where_a_gallery_number_is_confirmed():
    slots = {s["id"]: s for s in PLAN["sl"]}
    for s in PLAN["sl"]:
        assert s["rm"] in ROOMS and s["work"]["title"] and s["work"]["pma_url"].startswith("https://"), s["id"]
        assert s["pc"] in ("room", "cand") and s.get("gl")
        room = ROOMS[s["rm"]]
        if s["pc"] == "room" and room.get("no"):
            assert s["gl"] == room["no"], s["id"]
        elif s["pc"] == "cand" and not s["id"].startswith("sl-const"):
            assert s["gl"] in room.get("cand", []), s["id"]
        assert 0.1 <= s["sz"][0] <= 6 and 0.1 <= s["sz"][1] <= 6
    titles = " | ".join(s["work"]["title"].lower() for s in PLAN["sl"])
    for never in ("large bathers", "sunflowers", "prometheus", "large glass", "gross clinic", "fountain", "sleeping muse", "ghost"):
        assert re.search(r"\b" + never + r"\b", titles) is None, never                 # whole words: Hogarth's "Sir Andrew Fountaine" is not Duchamp's Fountain
    # true catalogued sizes where known, with their source
    monet = slots["sl-monet-japanese-footbridge"]
    assert monet["sz"] == [0.98, 0.79] and "78.7 x 97.8" in monet["sr"] and monet["sb"] == "catalogued" and monet["work"]["pma_url"].endswith("/87535")
    assert slots["sl-tanner-annunciation"]["gl"] == "358" and slots["sl-peale-yarrow-mamout"]["gl"] == "104"
    assert "img" not in slots["sl-rivera-sugar-cane"]["work"] and "img" in slots["sl-van-der-weyden-crucifixion"]["work"]
    assert sum(1 for s in PLAN["sl"] if "img" in s["work"]) == len(pma_art.manifest()["images"]) >= 30


# ── nodes ────────────────────────────────────────────────────────────────────

def _nodes(n, children=True):
    out = []
    for i in range(n):
        out.append(SimpleNamespace(id=f"n{i}", parent=None))
        if children and i % 6 == 0:
            out.append(SimpleNamespace(id=f"n{i}c", parent=f"n{i}"))
    return out


def test_thirty_nodes_in_room_mode():
    nodes = _nodes(30)
    res = bs.assign_nodes(PLAN, nodes, "room")
    assert not res["unplaced"] and not res["notes"]
    rooms = [res["assign"][f"n{i}"]["r"] for i in range(30)]
    assert len(set(rooms)) == 30 and rooms[0] == "l2-gsh"                          # the walk begins in the Great Stair Hall
    assert all(ROOMS[r]["ty"] not in bs.CIRCULATION for r in rooms)
    assert res["assign"]["n0c"]["r"] == "l2-gsh"                                    # a child stands in its parent's room
    assert {ROOMS[r]["l"] for r in rooms[:12]} <= {"l2"} | {"l3"}
    assert bs.room_order(PLAN)[0] == "l2-gsh" and len(bs.room_order(PLAN)) >= 90


def test_thirty_nodes_in_anchor_mode():
    res = bs.assign_nodes(PLAN, _nodes(30, children=False), "anchor")
    assert not res["unplaced"], res["notes"]
    ids = {s["id"] for s in PLAN["sl"]} | {f["id"] for f in PLAN["fx"]}
    assert all(v["a"] in ids and v["r"] in ROOMS for v in res["assign"].values())
    assert len({v["a"] for v in res["assign"].values()}) == 30
    over = bs.assign_nodes(PLAN, _nodes(3, children=False), "anchor", {"n1": "sl-monet-japanese-footbridge"})
    assert over["assign"]["n1"] == {"r": "l2-n-tapestry", "a": "sl-monet-japanese-footbridge"}


# ── registry, tool, hosting ──────────────────────────────────────────────────

def test_the_registry_holds_pma_and_the_fixture():
    assert set(buildings.CURATED) == {"pma", "test-pavilion"}
    assert buildings.resolve("PMA") == "pma" and buildings.resolve("Philadelphia Museum of Art") == "pma" and buildings.resolve("nowhere") is None
    assert buildings.load("pma")["id"] == "pma" and buildings.load("test-pavilion")["id"] == "test-pavilion"
    with pytest.raises(KeyError):
        buildings.load("nowhere")
    buildings.load("pma")["rm"].clear()                                             # a fresh copy each time
    assert buildings.load("pma")["rm"]


def test_set_up_building_takes_a_curated_building_without_a_plan(local_store):
    tid = _timeline()
    r = srv.set_up_building(tid, building="pma")
    assert r.get("ok"), r
    assert r["building"]["id"] == "pma" and r["building"]["levels"][0].startswith("Ground Level") and r["unplaced"] == []
    assert set(r["placed"]) == {n["id"] for n in NODES} and r["placed"]["a"]["room"] == "l2-gsh"
    doc = srv.get_store().get_timeline(srv.uid(), tid)
    assert doc["brief"]["palace_view"] == "building" and doc["brief"]["building"]["plan_h"] == bs.plan_hash(PLAN)
    assert bs.plan_of(load_brief({"brief": doc["brief"]})[0])["id"] == "pma"
    again = srv.set_up_building(tid, mode="anchor")                                  # the stored plan is kept
    assert again["ok"] and again["mode"] == "anchor" and again["building"]["id"] == "pma"
    bad = srv.set_up_building(tid, building="atlantis")
    assert bad["error"] == "unknown_building" and "pma" in bad["message"]
    assert srv.set_up_building(tid, building="test-pavilion")["building"]["id"] == "test-pavilion"


def test_the_tool_doc_and_the_guide_say_how_buildings_are_found():
    import inspect
    doc = " ".join(inspect.getdoc(srv.set_up_building).split())
    for want in ("CURATED building", "'pma'", "PUBLIC building", "baseline plan", "private, thin or gappy", "supplies material, says where to look, or describes it"):
        assert want in doc, want
    guide = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    assert 'building="pma"' in guide and "They do nothing else" in guide and "Wikimedia Commons" in guide


def test_images_are_hosted_immutably_and_packaged():
    names = [n for n, _b in pma_art.files()]
    assert all(pma_art.ART_RE.match(n) for n in names), names
    rules = {h["source"]: {x["key"]: x["value"] for x in h["headers"]} for h in publish_static._headers("csp", "ccsp", art_files=names)}
    for n in names:
        assert rules[f"/bart/{n}"]["Cache-Control"] == "public, max-age=31536000, immutable"
    assert publish_static._art_rules(["../evil.jpg", "pma-x-zz.jpg"]) == []
    assert publish_static._art_names(None) == []
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "assets/bldg/pma/*.jpg" in pyproject and "buildings/*.json" in pyproject
    assert '"alto/assets/bldg/pma", "*.jpg"' in (ROOT / "packaging" / "build_mcpb.py").read_text(encoding="utf-8")
