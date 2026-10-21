"""The Building Palace end to end (no browser): brief view, set_up_building, the built page, hosting, convert, homepage picker, guide."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto import publish_static  # noqa: E402
from alto.build import building_schema as bs  # noqa: E402
from alto.build import palace_assets, palace_building_asset as pba  # noqa: E402
from alto.build.brief import BriefError, PALACE_VIEWS, building_view, solar_style, validate_brief, validate_nodes  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

GUIDE = (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
HOME = (ROOT / "engine" / "home_template.html").read_text(encoding="utf-8")

NODES = [{"id": "a", "act": 0, "title": "Alpha & Co", "tag": "", "desc": "d"},
         {"id": "a1", "act": 0, "parent": "a", "title": "Alpha one", "tag": "", "desc": "d"},
         {"id": "b", "act": 0, "title": "Beta", "tag": "", "desc": "d"},
         {"id": "c", "act": 1, "title": "Gamma", "tag": "", "desc": "d"},
         {"id": "d", "act": 1, "title": "Delta", "tag": "", "desc": "d"}]


def brief(plan=None, **kw):
    plan = plan if plan is not None else bs.fixture()
    b = {"title": "Walk", "timeline_id": "walk", "mode": "palace", "palace_view": "building", "columns": 5,
         "node_noun": "Room", "period_noun": "Wing",
         "acts": [{"label": "Ground", "color": "#7c5cff"}, {"label": "Upper", "color": "#e0813f"}],
         "building": {"plan_z": bs.pack(plan), "plan_h": bs.plan_hash(plan), "mode": "room", "assign": {}}}
    b.update(kw)
    return b


def built(**kw):
    b, ns, cs = load_brief({"brief": brief(**kw), "nodes": json.loads(json.dumps(NODES))})
    return build_timeline(b, ns, cs)


@pytest.fixture
def local_store(tmp_path):
    srv.set_store(LocalStore(tmp_path))
    yield
    srv.set_store(None)


def _timeline(view="building"):
    pid = srv.create_project("Museum", "x", "studying")["project_id"]
    r = srv.create_timeline(pid, {"title": "Walk", "mode": "palace", "palace_view": view, "columns": 5, "node_noun": "Room",
                                  "period_noun": "Wing", "acts": [{"label": "Ground"}, {"label": "Upper"}]})
    assert "error" not in r, r
    tid = r["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "n.pdf", "kind": "notes"}], True)
    assert "error" not in srv.add_nodes(tid, json.loads(json.dumps(NODES)))
    return tid


# ── the brief ────────────────────────────────────────────────────────────────

def test_building_is_a_palace_view_and_needs_its_plan():
    assert PALACE_VIEWS == ("city", "building")        # (1.9.105's "stars" view is the System's Star chart look now)
    b, ns, _ = load_brief({"brief": brief(), "nodes": NODES})
    assert building_view(b) and not solar_style(b)
    assert validate_brief(b) is not None
    b.palace_view = "city"                                       # a plan without the view is refused
    with pytest.raises(BriefError, match="palace_view 'building'"):
        validate_brief(b)
    b.palace_view, b.building = "building", {}
    assert any("no plan yet" in w for w in validate_brief(b))    # said, not refused: the page shows a message
    b.building = {"plan_z": bs.pack(bs.fixture()), "plan_h": "0" * 12, "mode": "room"}
    with pytest.raises(BriefError, match="does not match"):
        validate_brief(b)
    b.building = {"plan_z": bs.pack(bs.fixture()), "plan_h": bs.plan_hash(bs.fixture()), "mode": "stroll"}
    with pytest.raises(BriefError, match="building.mode"):
        validate_brief(b)
    b.building = {"plan_z": bs.pack(bs.fixture()), "plan_h": bs.plan_hash(bs.fixture()), "assign": {"a": "attic"}}
    with pytest.raises(BriefError, match="not a room, art slot or fixture"):
        validate_brief(b)
    bad = bs.fixture()
    bad["rm"][0]["ch"] = 0
    b.building = {"plan_z": bs.pack(bad), "plan_h": bs.plan_hash(bad)}
    with pytest.raises(BriefError, match="building plan: .*ch"):
        validate_brief(b)
    b.mode, b.building = "outline", {"name": "x"}
    with pytest.raises(BriefError):
        validate_brief(b)


def test_a_building_palace_may_be_one_section():
    b, ns, _ = load_brief({"brief": brief(acts=[{"label": "Everything"}]), "nodes": [{**n, "act": 0} for n in NODES]})
    validate_brief(b)
    validate_nodes(b, ns)


# ── the page ────────────────────────────────────────────────────────────────

def test_the_page_carries_a_loader_and_the_placements_not_the_plan():
    html, report = built()
    assert "window._ALTO_BUILDING=" in html and "function altoLoadBuilding()" in html and pba.BUILDING_PATH in html
    data = json.loads(re.search(r"window\._ALTO_BUILDING=(\{.*?\});\n", html).group(1).replace("<\\/", "</"))
    assert data["h"] == bs.plan_hash(bs.fixture()) and data["url"] == f"/bldg/plan-{data['h']}.json" and "plan" not in data
    assert data["nodes"]["a"]["n"] == "1.1" and data["nodes"]["a"]["t"] in ("Alpha & Co", "Alpha &amp; Co")      # (the renderer decodes entities, writes with textContent)
    assert [data["nodes"][i]["r"] for i in ("a", "b", "c", "d")] == ["hall", "g101", "u201", "u202"] and data["nodes"]["a1"]["r"] == "hall"
    assert data["acts"][1] == {"n": "Upper", "c": "#e0813f"} and data["order"] == ["a", "a1", "b", "c", "d"]
    assert "Alto Test Pavilion" in html and "bl-tube" not in html              # the renderer is hosted, not inlined
    assert "_ALTO_SOLAR" not in html.split("window._ALTO_BUILDING")[0][-2000:]
    assert "window._ALTO_PALACE={" in html                                      # the numbers (1.1, 1.1-1) still come from the palace stub
    assert report["warnings"] is not None


def test_the_page_grows_by_a_few_kilobytes_only():
    """The private page is at its size cap: a Building Palace costs a loader and the placements, and is far lighter than the city."""
    plain, _ = built(mode="linear", palace_view="city", building={})
    html, _ = built()
    assert 0 < len(html) - len(plain) < 12_000, len(html) - len(plain)
    assert len(html) < len(built(palace_view="city", building={})[0])


def test_a_building_palace_with_no_plan_says_so_in_the_page():
    html, _ = built(building={})
    data = json.loads(re.search(r"window\._ALTO_BUILDING=(\{.*?\});\n", html).group(1))
    assert data["none"] == 1 and "url" not in data


def test_overrides_and_anchor_mode_reach_the_page():
    html, _ = built(building={**brief()["building"], "mode": "anchor", "assign": {"d": "hall"}})
    data = json.loads(re.search(r"window\._ALTO_BUILDING=(\{.*?\});\n", html).group(1))
    assert data["mode"] == "anchor" and data["nodes"]["d"]["r"] == "hall" and data["nodes"]["d"]["s"] is None
    assert [data["nodes"][i]["s"] for i in ("a", "a1", "b")] == ["sl-101a", "sl-101b", "plinth-a"]       # outline order: a, its child, b


def test_the_city_palace_page_is_unchanged_by_the_building_branch():
    city, _ = built(palace_view="city", building={})
    assert "window._ALTO_BUILDING" not in city and "altoLoadBuilding" not in city


# ── the tool ────────────────────────────────────────────────────────────────

def test_set_up_building_stores_proposes_and_builds(local_store):
    tid = _timeline()
    r = srv.set_up_building(tid, demo=True)
    assert r["ok"] and r["palace_view"] == "building" and r["mode"] == "room" and r["unplaced"] == []
    assert r["placed"]["a"] == {"room": "hall"} and r["placed"]["c"] == {"room": "u201"}
    assert r["building"]["rooms"] == 4 and "plan_z" not in json.dumps(r)
    got = srv.get_timeline(tid)["brief"]
    assert got["palace_view"] == "building" and "plan_z" not in got["building"] and got["building"]["plan"]["name"] == "Alto Test Pavilion"
    assert srv.build_timeline(tid).get("verify") == "passed"
    # change only the assignment: the stored plan is kept
    r = srv.set_up_building(tid, mode="anchor", assignments={"d": "u202"})
    assert r["ok"] and r["placed"]["d"] == {"room": "u202"} and r["placed"]["a"] == {"room": "g101", "anchor": "sl-101a"}
    assert srv.get_timeline(tid)["brief"]["building"]["mode"] == "anchor"
    assert srv.set_up_building(tid, assignments={})["ok"]       # {} clears the overrides
    assert srv.build_timeline(tid).get("verify") == "passed"


def test_set_up_building_refuses_clearly(local_store):
    tid = _timeline()
    assert srv.set_up_building(tid)["error"] == "no_plan"
    bad = bs.fixture()
    bad["rm"][0]["p"] = [[0, 0], [4, 4], [4, 0], [0, 4]]
    bad["wl"][0]["t"] = 0
    r = srv.set_up_building(tid, bad)
    assert r["error"] == "invalid_plan" and len(r["problems"]) >= 2 and "rm[0] 'hall'" in r["message"]
    assert srv.set_up_building(tid, demo=True, mode="stroll")["error"] == "invalid_mode"
    assert srv.set_up_building(tid, demo=True, assignments={"a": "attic"})["error"] == "invalid_building"
    assert srv.get_timeline(tid)["brief"].get("building") in (None, {})               # nothing half-stored
    pid = srv.create_project("P2", "x", "studying")["project_id"]
    r2 = srv.create_timeline(pid, {"title": "Flat", "mode": "outline", "columns": 5, "acts": [{"label": "A"}, {"label": "B"}]})
    assert srv.set_up_building(r2["timeline_id"], demo=True)["error"] == "not_a_palace"


def test_unplaced_nodes_are_reported_not_hidden(local_store):
    tid = _timeline()
    tiny = bs.fixture()
    tiny["rm"] = tiny["rm"][:2]
    tiny["sl"] = [s for s in tiny["sl"] if s["rm"] in ("hall", "g101")]
    tiny["tour"] = None
    del tiny["tour"]
    tiny["rm"][0]["c"] = 2
    r = srv.set_up_building(tid, tiny)
    assert r["ok"] and r["unplaced"] == ["c", "d"] and any("found no place" in w for w in r["warnings"])


def test_the_layout_tools_take_the_building_view(local_store):
    tid = _timeline("city")
    assert srv.run_layout_preview(tid, palace_view="swirl")["error"] == "invalid_palace_view"
    r = srv.run_layout_preview(tid, palace_view="building")
    assert "error" not in r, r
    assert srv.build_timeline(tid, palace_view="building").get("verify") == "passed"
    assert srv.get_timeline(tid)["brief"]["palace_view"] == "building"


def test_the_tool_and_docs_say_what_they_do():
    import inspect
    doc = " ".join(inspect.getdoc(srv.set_up_building).split())
    for want in ("building_schema.py", "never invent a room", "mode: how nodes are handed out", "assignments", "demo"):
        assert want in doc, want
    assert "'city'|'building'" in inspect.getdoc(srv.create_timeline)
    assert "§D-Building" in GUIDE and "set_up_building" in GUIDE and "palace_view: 'building'" in GUIDE
    assert srv.mcp._tool_manager.get_tool("set_up_building") is not None


# ── no conversion (System has two looks in the page; convert_timeline is gone) ──

def test_a_building_palace_is_not_migrated_and_there_is_no_convert_tool():
    from alto.build.brief import migrate_brief
    out, aside = migrate_brief(brief())
    assert out["palace_view"] == "building" and out["mode"] == "palace" and aside == {}
    assert not hasattr(srv, "convert_timeline")


# ── hosting ─────────────────────────────────────────────────────────────────

def test_the_renderer_is_a_hashed_asset_and_plans_are_written_beside_it():
    assert ("bldg", "palace_building_asset", "building_asset") in palace_assets.ASSETS and "bldg" in palace_assets.folders()
    name, text = pba.building_asset()
    assert re.fullmatch(r"palace-building-[0-9a-f]{10}\.js", name) and pba.BUILDING_PATH == "/bldg/" + name and "window.AltoBuilding=A" in text
    pname, ptext = bs.hosted_json(bs.fixture())
    got = {(f, n): t for f, n, t in palace_assets.assets(building_plans={pname: ptext}) if f == "bldg"}
    from alto.build import palace_building_fpv as fpv
    assert set(got) == {("bldg", name), ("bldg", pname), ("bldg", fpv.fpv_asset()[0])} and got[("bldg", pname)] == ptext       # + the first-person view (phase 2)
    assert palace_assets.find("/bldg/" + pname, building_plans={pname: ptext})[0].startswith("application/json")
    assert palace_assets.find(pba.BUILDING_PATH)[0].startswith("text/javascript")


def test_the_loader_is_guarded_and_small():
    assert "if(window.AltoBuilding) return;" in pba.BUILDING_LOADER and "catch(e){}" in pba.BUILDING_LOADER
    assert len(pba.BUILDING_LOADER) < 700 and len(pba.BUILDING_START) < 500


def test_publishing_writes_the_plan_of_every_published_building_palace_and_caches_it_for_a_year(tmp_path, local_store):
    tid = _timeline()
    srv.set_up_building(tid, demo=True)
    st = srv.get_store()
    other = _timeline_other_city()
    uid = srv.uid()
    plans = publish_static._building_plans(st, uid)
    assert plans == {}                                           # nothing published yet: no plan is hosted for a draft
    doc = st.get_timeline(uid, tid)
    doc["status"] = "published"
    st.put_timeline(uid, tid, doc)
    plans = publish_static._building_plans(st, uid)
    assert list(plans) == [f"plan-{bs.plan_hash(bs.fixture())}.json"] and json.loads(next(iter(plans.values())))["name"] == "Alto Test Pavilion"
    assert other  # (a city palace publishes no plan)
    hdr = publish_static._headers("csp", "ccsp")
    rules = {h["source"]: {x["key"]: x["value"] for x in h["headers"]} for h in hdr}
    assert "/bldg/**" not in rules                               # a folder-wide rule would cache a not-yet-deployed plan's 404 for a year
    hdr = publish_static._headers("csp", "ccsp", bldg_files=[pba.building_asset()[0], next(iter(plans)), "evil.json"])
    rules = {h["source"]: {x["key"]: x["value"] for x in h["headers"]} for h in hdr}
    assert rules["/bldg/" + next(iter(plans))]["Cache-Control"] == "public, max-age=31536000, immutable"
    assert ("/bldg/" + pba.building_asset()[0]) in rules and "/bldg/evil.json" not in rules


def _timeline_other_city():
    pid = srv.create_project("City", "x", "studying")["project_id"]
    r = srv.create_timeline(pid, {"title": "City", "mode": "palace", "columns": 5, "acts": [{"label": "A"}, {"label": "B"}]})
    return r["timeline_id"]


# ── homepage ────────────────────────────────────────────────────────────────

def test_the_homepage_picker_offers_the_building_and_hands_it_to_claude():
    phrases = HOME[HOME.index("const KIND_PHRASE = {"):HOME.index("function kindSentence(kind)")]
    assert "  building: '" in phrases and "palace_view \\'building\\'" in phrases and "set_up_building" in phrases
    assert 'data-mode="building" aria-pressed="false">' in HOME and 'Museum / building</button>' in HOME and 'data-for="building"' in HOME
    assert "ntModes.palace === 'building' ? 'building' : 'palace'" in HOME
    assert "if(ntKind === 'palace' || ntKind === 'building'){ ntClose(); openClaude(" in HOME      # a building needs its plan: Claude's, never a browser starter
    assert (ROOT / "alto" / "engine" / "home_template.html").read_text(encoding="utf-8") == HOME     # staged
    assert "building" not in __import__("alto.build.starter", fromlist=["KINDS"]).KINDS
