"""Interim plan-guard (Board B-1123-PLAN-PUBLIC, item 1): a USER-DRAWN Memory Blueprint plan is refused at set_up_building and at publish,
because the plan is hosted as a public file (/bldg/plan-<hash>.json). Only the repo's own curated plans are allowed. Test store only."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import mcp_server as srv  # noqa: E402
from alto.build import building_schema as bs  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

NODES = [{"id": "a", "act": 0, "title": "Alpha", "tag": "", "desc": "d"},
         {"id": "b", "act": 1, "title": "Beta", "tag": "", "desc": "d"}]


@pytest.fixture
def store(tmp_path):
    st = LocalStore(tmp_path)
    srv.set_store(st)
    yield st
    srv.set_store(None)


def _tl():
    pid = srv.create_project("Museum", "x", "studying")["project_id"]
    r = srv.create_timeline(pid, {"title": "Walk", "mode": "palace", "palace_view": "building", "columns": 5, "node_noun": "Room",
                                  "period_noun": "Wing", "acts": [{"label": "Ground"}, {"label": "Upper"}]})
    tid = r["timeline_id"]
    srv.record_materials_consent(tid, [{"name": "n.pdf", "kind": "notes"}], True)
    assert "error" not in srv.add_nodes(tid, json.loads(json.dumps(NODES)))
    return tid


def _drawn():
    p = bs.fixture()
    p["name"] = "My own house"
    p["rm"][0]["n"] = "Study"                       # same shape as the curated fixture, so only the hash tells them apart
    return p


def test_a_drawn_plan_is_refused_and_nothing_is_stored(store):
    tid = _tl()
    r = srv.set_up_building(tid, _drawn())
    assert r["error"] == "user_plan_not_allowed" and "public to anyone with the link" in r["message"] and "coming" in r["message"]
    assert srv.get_timeline(tid)["brief"].get("building") in (None, {})


def test_curated_plans_still_work(store):
    tid = _tl()
    assert srv.set_up_building(tid, demo=True)["ok"]
    assert srv.set_up_building(tid, building="test-pavilion")["ok"]
    assert srv.set_up_building(tid, building="pma").get("error") != "user_plan_not_allowed"


def test_a_name_copied_from_a_curated_plan_does_not_pass(store):
    p = _drawn()
    p["name"], p["id"] = bs.fixture()["name"], bs.fixture().get("id")
    assert srv.set_up_building(_tl(), p)["error"] == "user_plan_not_allowed"


@pytest.mark.parametrize("visibility", ["private-web", "private"])
def test_publish_refuses_a_drawn_plan_stored_before_the_guard(store, visibility):
    tid = _tl()
    assert srv.set_up_building(tid, demo=True)["ok"]
    assert srv.build_timeline(tid).get("verify") == "passed"
    doc = store.get_timeline(srv.uid(), tid)
    p = _drawn()                                     # a plan that got in some other way (an older version, a hand edit)
    doc["brief"]["building"] = {**doc["brief"]["building"], "plan_z": bs.pack(p), "plan_h": bs.plan_hash(p)}
    store.put_timeline(srv.uid(), tid, doc)
    r = srv.publish_timeline(tid, visibility)
    assert r["error"] == "user_plan_not_allowed"
    after = store.get_timeline(srv.uid(), tid)
    assert after.get("status") != "published" and not after.get("private_key")
    from alto import publish_static
    assert publish_static._building_plans(store, srv.uid()) == {}      # nothing would be hosted under /bldg/


def test_a_curated_plan_publishes_and_the_public_value_stays_refused(store):
    tid = _tl()
    assert srv.set_up_building(tid, demo=True)["ok"]
    assert srv.build_timeline(tid).get("verify") == "passed"
    assert srv.publish_timeline(tid, "private").get("error") != "user_plan_not_allowed"
    assert srv.publish_timeline(tid, "link")["error"] == "link_removed"   # no public visibility exists, so no acknowledgement flag is needed


def _built_with(store, plan_z, plan_h):
    tid = _tl()
    assert srv.set_up_building(tid, demo=True)["ok"]
    assert srv.build_timeline(tid).get("verify") == "passed"
    doc = store.get_timeline(srv.uid(), tid)
    doc["brief"]["building"] = {**doc["brief"]["building"], "plan_z": plan_z, "plan_h": plan_h}
    store.put_timeline(srv.uid(), tid, doc)
    return tid


@pytest.mark.parametrize("visibility", ["private-web", "private"])
def test_a_forged_brief_with_a_curated_hash_is_refused_and_nothing_is_hosted(store, visibility):
    p = _drawn()
    tid = _built_with(store, bs.pack(p), bs.plan_hash(bs.fixture()))     # the user's plan under the curated plan's hash
    r = srv.publish_timeline(tid, visibility)
    assert r["error"] == "user_plan_not_allowed"
    from alto import publish_static
    assert publish_static._building_plans(store, srv.uid()) == {}
    assert store.get_timeline(srv.uid(), tid).get("status") != "published"


def test_an_undecodable_plan_is_refused(store):
    for z in ("not base64 at all!!", "AAAA", ""):
        tid = _built_with(store, z or "x", bs.plan_hash(bs.fixture()))
        assert srv.publish_timeline(tid, "private-web")["error"] == "user_plan_not_allowed"


def test_the_hosting_code_hosts_no_drawn_plan_even_for_a_forged_published_doc(store):
    """An imported / hand-made doc with status 'published' and a user plan (any plan_h) gets no /bldg/ file; a curated plan still does."""
    from alto import publish_static
    tid = _built_with(store, bs.pack(_drawn()), bs.plan_hash(bs.fixture()))
    doc = store.get_timeline(srv.uid(), tid)
    doc["status"] = "published"
    store.put_timeline(srv.uid(), tid, doc)
    assert publish_static._building_plans(store, srv.uid()) == {}
    doc["brief"]["building"] = {**doc["brief"]["building"], "plan_z": "garbage"}
    store.put_timeline(srv.uid(), tid, doc)
    assert publish_static._building_plans(store, srv.uid()) == {}
    good = bs.fixture()
    doc["brief"]["building"] = {**doc["brief"]["building"], "plan_z": bs.pack(good), "plan_h": bs.plan_hash(good)}
    store.put_timeline(srv.uid(), tid, doc)
    assert list(publish_static._building_plans(store, srv.uid())) == [bs.file_name(bs.plan_hash(good))]
