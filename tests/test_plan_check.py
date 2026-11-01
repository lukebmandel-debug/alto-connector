"""The study plan record and its one check (alto/build/plan_check.py), and that it rides in the brief without changing a page."""
import copy
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build.brief import BriefError, Brief                       # noqa: E402
from alto.build.builder import build_timeline, load_brief            # noqa: E402
from alto.build import plan_check as PC                              # noqa: E402

OUTLINE = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
IDS = [n["id"] for n in OUTLINE["nodes"]]
TODAY = dt.date(2026, 11, 2)


def plan(*items, **over):
    return {"v": 1, "exam_date": "2026-12-10", "days_per_week": 5, "minutes_per_day": 90, "items": list(items), **over}


def item(node=IDS[0], day="2026-11-03", why="You marked it Still learning.", signal="marks"):
    return {"node": node, "day": day, "why": why, "signal": signal}


def refused(p, needle, **kw):
    with pytest.raises(BriefError) as e:
        PC.check_plan(IDS, p, **kw)
    assert needle in str(e.value), str(e.value)


# ── the check ──────────────────────────────────────────────────────────────

def test_a_good_plan_comes_back_stored_in_day_order():
    out = PC.check_plan(IDS, plan(item(IDS[1], "2026-11-05"), item(IDS[0], "2026-11-03")), today=TODAY)
    assert out["v"] == 1 and out["exam_date"] == "2026-12-10" and out["days_per_week"] == 5 and out["minutes_per_day"] == 90
    assert [(i["node"], i["day"]) for i in out["items"]] == [(IDS[0], "2026-11-03"), (IDS[1], "2026-11-05")]
    assert PC.check_plan(IDS, out, today=TODAY) == out                                   # idempotent
    assert PC.check_plan(IDS, None) == {} and PC.check_plan(IDS, {}) == {}                # no plan is no plan


def test_a_node_that_is_not_in_the_timeline_refuses_the_plan():
    refused(plan(item("no-such-node")), "node 'no-such-node' is not in this timeline")
    out = PC.check_plan(None, plan(item("anything")))                                    # no node list: that check is skipped
    assert out["items"][0]["node"] == "anything"


@pytest.mark.parametrize("day", ["2026-13-01", "2026-02-30", "next week", "11/03/2026", "2026-11-3", "", None])
def test_a_bad_day_refuses_the_plan(day):
    refused(plan(item(day=day)), "day")


def test_a_day_more_than_a_year_from_today_is_refused_only_when_today_is_given():
    refused(plan(item(day="2028-01-01")), "more than 366 days", today=TODAY)
    refused(plan(item(day="2024-01-01")), "more than 366 days", today=TODAY)
    assert PC.check_plan(IDS, plan(item(day="2028-01-01")))["items"]                      # read back later: not re-judged


def test_a_bad_exam_date_or_amount_refuses_the_plan():
    refused(plan(item(), exam_date="soon"), "exam_date")
    refused(plan(item(), days_per_week=9), "days_per_week")
    refused(plan(item(), minutes_per_day=2), "minutes_per_day")
    refused(plan(item(), minutes_per_day=True), "minutes_per_day")
    assert PC.check_plan(IDS, plan(item(), exam_date="", days_per_week=None, minutes_per_day=None))["exam_date"] == ""


def test_the_same_node_on_the_same_day_twice_refuses_the_plan_but_two_days_are_fine():
    refused(plan(item(), item(why="again")), "already planned")
    assert len(PC.check_plan(IDS, plan(item(day="2026-11-03"), item(day="2026-11-04")))["items"]) == 2


def test_the_why_is_required_plain_and_short():
    refused(plan(item(why="")), "why is required")
    refused(plan(item(why="   ")), "why is required")
    refused(plan(item(why="x" * 201)), "at most 200")
    out = PC.check_plan(IDS, plan(item(why="You  said\n<b>remedies</b> <script>alert(1)</script> are weak.")))["items"][0]["why"]
    assert out == "You said remedies alert(1) are weak." and "<" not in out
    assert len(PC.check_plan(IDS, plan(item(why="x" * 200)))["items"][0]["why"]) == 200


def test_the_signal_must_be_one_of_the_students_own():
    for s in PC.SIGNALS:
        assert PC.check_plan(IDS, plan(item(signal=s)))["items"]
    refused(plan(item(signal="importance")), "signal")
    refused(plan(item(signal=None)), "signal")


def test_nothing_outside_the_record_is_allowed():
    refused(plan(item(), extra_field=1), "unknown field")
    refused(plan({**item(), "priority": 1}), "unknown field")
    refused(plan(item(), v=2), "version")
    refused(plan(*[item(day=f"2026-{11 + i // 28:02d}-{i % 28 + 1:02d}") for i in range(121)]), "at most 120")


def test_every_problem_is_named_not_just_the_first():
    with pytest.raises(BriefError) as e:
        PC.check_plan(IDS, plan(item("nope"), item(day="bad"), item(why="")))
    m = str(e.value)
    assert "nope" in m and "not a date" in m and "why is required" in m


def test_not_strict_drops_what_is_wrong_and_keeps_the_rest():
    out = PC.check_plan(IDS, plan(item("gone"), item(IDS[0])), strict=False)
    assert [i["node"] for i in out["items"]] == [IDS[0]]


# ── it rides in the brief and changes no page ──────────────────────────────

def _doc(**plan_over):
    d = copy.deepcopy(OUTLINE)
    if plan_over is not None and "study_plan" in plan_over:
        d["brief"]["study_plan"] = plan_over["study_plan"]
    return d


def _page(d):
    return build_timeline(*load_brief(d))[0]


def test_the_brief_carries_study_plan_and_an_absent_one_builds_the_same_page():
    assert Brief(title="t").study_plan == {}
    base = _page(_doc())
    assert _page(_doc(study_plan={})) == base                                            # the flag-off rule: byte-identical
    b, nodes, _ = load_brief(_doc(study_plan=plan(item(IDS[0]), item("gone-since"))))
    from alto.build.sanitize import sanitize_brief
    sanitize_brief(b, nodes)
    assert [i["node"] for i in b.study_plan["items"]] == [IDS[0]]                        # a deleted node's item drops at build, the rest stands


def test_a_malformed_plan_in_a_brief_is_refused_at_validation():
    with pytest.raises(BriefError):
        load_brief(_doc(study_plan=plan(item(day="never"))))
        b, _, _ = load_brief(_doc(study_plan=plan(item(day="never"))))
        from alto.build.brief import validate_brief
        validate_brief(b)
