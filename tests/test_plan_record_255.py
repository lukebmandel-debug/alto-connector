"""1.9.255, audit gap G2/G10: the page record (users/{uid}/pagemeta/{key}) carries a SMALL study-plan summary so the homepage card can say
"Study plan . Today N". Days + node ids + exam date only: no reason text, no note text. Owner-only like the rest of the record."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudfake import FakeFirebase  # noqa: E402
from test_study_plan import PLAN, _build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
from alto.cloud.meta import meta_of, plan_of  # noqa: E402
from alto.cloud.session import Session  # noqa: E402
from alto.store.cloud import CloudStore  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402

CFG = {"apiKey": "k", "projectId": "proj", "appId": "a"}
BASE = "projects/proj/databases/(default)/documents/users/U1"
WHYS = [i["why"] for i in PLAN["items"]]


@pytest.fixture
def fake():
    return FakeFirebase()


@pytest.fixture
def cloud(fake, tmp_path):
    s = Session(CFG, http=fake, path=tmp_path / "cfg" / "session-proj.json", opener=lambda u: None)
    s._accept("RT")
    return CloudStore(s, LocalStore(tmp_path / "local"))


def test_a_planned_page_gets_a_small_summary_in_its_record():
    page = _build("outline", plan=PLAN)
    m = meta_of(page)
    assert set(m["plan"]) == {"days", "nodes", "exam"}
    assert sorted(zip(m["plan"]["days"], m["plan"]["nodes"])) == sorted((i["day"], i["node"]) for i in PLAN["items"])      # (one node per day, side by side; the page keeps its own order)
    assert m["plan"]["exam"] == "2026-12-01"
    assert len(json.dumps(m["plan"])) < 700                                   # (a day + a node id per item: tiny)


def test_the_record_carries_no_note_text():
    page = _build("outline", plan=PLAN)
    assert all(w in page for w in WHYS)                                       # (the reasons are in the page...)
    blob = json.dumps(meta_of(page)["plan"])
    assert not any(w in blob for w in WHYS) and "why" not in blob and "signal" not in blob and "minutes" not in blob

    for n in meta_of(page)["plan"]["nodes"]:
        assert n in {"formation", "offer", "acceptance", "revocation", "definiteness"}      # (ids of the page's own cards)


def test_a_page_without_a_plan_has_no_plan_in_its_record():
    assert "plan" not in meta_of(_build("outline")) and plan_of("") is None and plan_of("<html>") is None
    assert plan_of('<script id="alto-sp-data">window._ALTO_SP={"items":[]};</script>') is None
    bad = '<script id="alto-sp-data">window._ALTO_SP={"exam":"x","items":[{"node":"a","day":"soon"},{"node":"","day":"2026-11-05"},5]};</script>'
    assert plan_of(bad) is None
    assert plan_of(bad.replace("[{", '[{"node":"a","day":"2026-11-05"},{')) == {"days": ["2026-11-05"], "nodes": ["a"], "exam": ""}


def test_a_reason_with_a_comment_opener_still_reads():
    plan = {"v": 1, "exam_date": "2026-12-01", "items": [dict(node="offer", day="2026-11-05", why="see <!-- this", signal="marks")]}
    assert plan_of(_build("outline", plan=plan))["days"] == ["2026-11-05"]


def test_publishing_writes_the_summary_and_clearing_removes_it(cloud, fake):
    planned = meta_of(_build("outline", plan=PLAN))
    cloud.put_page("U1", "k1", "<html>", "P", {**planned, "added": 5})
    pm = fake.docs[f"{BASE}/pagemeta/k1"]
    plan = pm["plan"]["mapValue"]["fields"]
    assert [v["stringValue"] for v in plan["days"]["arrayValue"]["values"]] == planned["plan"]["days"]
    assert [v["stringValue"] for v in plan["nodes"]["arrayValue"]["values"]] == planned["plan"]["nodes"]
    assert plan["exam"] == {"stringValue": "2026-12-01"}
    assert not any(w in json.dumps(pm) for w in WHYS)                         # no note text reaches the record
    # a republish of the same page with its plan cleared (an empty list) removes the field
    cloud.put_page("U1", "k1", "<html>", "P", meta_of(_build("outline", plan={"v": 1, "items": []})))
    assert "plan" not in fake.docs[f"{BASE}/pagemeta/k1"]
    cloud.put_page("U1", "k1", "<html>", "P", planned)
    assert "plan" in fake.docs[f"{BASE}/pagemeta/k1"]
    cloud.put_page("U1", "k1", "<html>", "P", meta_of(_build("outline")))
    assert "plan" not in fake.docs[f"{BASE}/pagemeta/k1"]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("planned", [True, False])
def test_python_and_browser_summaries_match(tmp_path, planned):
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    a, b = js.index("  const META_V"), js.index("  async function _getPageMeta")
    idf = js[js.index("  function _identityOf"):js.index("  function _reidentify")]
    page = tmp_path / "p.html"
    page.write_text(_build("outline", plan=PLAN if planned else None), encoding="utf-8")
    runner = tmp_path / "m.js"
    runner.write_text("const fs=require('fs');const f=new Function(" + json.dumps(js[a:b] + idf + "; return _metaOf;")
                      + ")();process.stdout.write(JSON.stringify(f(fs.readFileSync(process.argv[2],'utf8'))));")
    got = json.loads(subprocess.check_output(["node", str(runner), str(page)]))
    assert got == meta_of(page.read_text(encoding="utf-8")) and ("plan" in got) == planned


def test_the_list_hands_the_summary_to_the_homepage_and_no_other_reader_gets_one():
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    lp = js[js.index("async function _listPages"):js.index("/* ── shares: a copy anyone")]
    assert "plan:" in lp and "v.plan.days" in lp
    # a copy anyone with the link can read, and the "shared with me" list, never carry the plan (nothing but units/heading/fmt)
    sm = js[js.index("function _sharedMetaOf"):]
    sm = sm[:sm.index("\n  }\n")]
    assert "plan" not in sm.lower() and "_planOf" not in sm
    ls = js[js.index("async function _listShared"):]
    assert "plan" not in ls[:ls.index("\n  }\n")]
    # a merge-write for a page with no plan removes the old field
    assert "deleteField()" in js[js.index("const _planGone"):js.index("const _planGone") + 200]


def test_only_the_owner_can_read_the_record_a_plan_sits_in():
    rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
    assert (ROOT / "alto" / "firestore.rules").read_text(encoding="utf-8") == rules
    assert "match /{coll}/{id} {\n        allow read: if isUser(uid) && ownCollection(coll);" in rules
    assert "'pagemeta'" in rules[rules.index("function ownCollection"):][:400]
    assert not re.search(r"pagemeta[^\n]*allow\s+(read|get|list)[^;]*(true|!= null)", rules)


def test_a_trailing_newline_or_a_non_list_of_items_is_no_plan():
    wrap = lambda body: '<script id="alto-sp-data">window._ALTO_SP=' + body + ';</script>'
    assert plan_of(wrap('{"items":[{"node":"a","day":"2026-11-05\\n"}]}')) is None            # (the JS $ does not match before a newline; nor does fullmatch)
    assert plan_of(wrap('{"items":[{"node":"a","day":"2026-11-05"}],"exam":"2026-12-01\\n"}'))["exam"] == ""
    for bad in ('5', '"abc"', '{"a":1}', 'null', 'true'):
        assert plan_of(wrap('{"items":%s}' % bad)) is None


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("body", ['{"items":5}', '{"items":"abc"}', '{"items":{"a":1}}', '{"items":null}',
                                  '{"items":[{"node":"a","day":"2026-11-05\\n"}]}'])
def test_the_browser_writer_agrees_on_odd_items(tmp_path, body):
    js = (ROOT / "alto" / "cloud" / "alto-cloud.js").read_text(encoding="utf-8")
    a, b = js.index("  function _planOf"), js.index("  // Added to a merge-write")
    runner = tmp_path / "m.js"
    runner.write_text("const f=new Function(" + json.dumps(js[a:b] + "; return _planOf;") + ")();process.stdout.write(JSON.stringify(f(process.argv[2])));")
    html = '<script id="alto-sp-data">window._ALTO_SP=' + body + ';</script>'
    assert json.loads(subprocess.check_output(["node", str(runner), html])) is None and plan_of(html) is None
