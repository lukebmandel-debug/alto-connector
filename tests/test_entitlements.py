"""The one entitlement check (alto/entitlements.py) and the homepage's "Turn into another format…".

Beta: every format is open, nothing is looked up. The paywall only changes the table and flips one switch; every way of making
a format (the connector's tools, the homepage sheet, a build's own route) goes through the same `allowed`.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto import entitlements as E          # noqa: E402
from alto import mcp_server as srv          # noqa: E402
from alto.store.local import LocalStore     # noqa: E402

HOME = ROOT / "alto" / "engine" / "home_template.html"
SAMPLE = json.loads((ROOT / "samples" / "contracts_brief.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    srv.set_store(LocalStore(tmp_path))
    monkeypatch.delenv("ALTO_PAYWALL", raising=False)
    monkeypatch.setattr(E, "FORMAT_MIN_PLAN", dict(E.FORMAT_MIN_PLAN))
    yield
    E.set_plan_lookup(None)
    srv.set_store(None)


def _paywall(monkeypatch, plan_of="free", **table):
    monkeypatch.setenv("ALTO_PAYWALL", "1")
    E.FORMAT_MIN_PLAN.update(table)
    E.set_plan_lookup(lambda uid: plan_of)


# ── the check itself ───────────────────────────────────────────────────────

def test_in_the_beta_every_format_is_open_and_nothing_is_looked_up():
    E.set_plan_lookup(lambda uid: (_ for _ in ()).throw(AssertionError("no lookup in the beta")))
    assert set(E.FORMATS) == {"timeline", "outline", "system", "lanes", "palace", "world", "building"}
    assert all(v == "free" for v in E.FORMAT_MIN_PLAN.values()) and not E.paywall_on()
    assert all(E.allowed("u", f) == {"ok": True} for f in E.FORMATS)
    assert all(r["ok"] for r in E.formats_for("u"))


def test_a_brief_names_the_format_it_builds():
    f = E.format_of_brief
    assert f({}) == f({"mode": "linear"}) == "timeline"
    assert f({"mode": "outline"}) == f({"mode": "outline", "layout": "tree"}) == "outline"
    assert f({"mode": "outline", "layout": "solar"}) == "system"
    assert f({"mode": "lanes"}) == "lanes"
    assert f({"mode": "palace"}) == f({"mode": "palace", "palace_view": "city"}) == "palace"
    assert f({"mode": "palace", "palace_view": "building"}) == "building"
    assert f({"mode": "palace", "palace_view": "world"}) == "world"


def test_with_the_paywall_on_the_target_format_decides_not_the_source(monkeypatch):
    _paywall(monkeypatch, "free", palace="plus", building="pro")
    assert E.allowed("u", "outline") == {"ok": True}
    r = E.allowed("u", "palace")
    assert r["ok"] is False and r["needs_plan"] == "plus" and "Plus" in r["message"]
    assert E.allowed("u", "building")["needs_plan"] == "pro"
    E.set_plan_lookup(lambda uid: "plus")
    assert E.allowed("u", "palace")["ok"] is True and E.allowed("u", "building")["ok"] is False
    E.set_plan_lookup(lambda uid: "pro")
    assert all(E.allowed("u", f)["ok"] for f in E.FORMATS)
    assert E.allowed("u", "orchestra")["ok"] is False
    rows = {r["id"]: r for r in E.formats_for("u")}
    assert rows["palace"]["place"] and not rows["outline"]["place"]


def test_a_missing_or_unknown_plan_counts_as_free(monkeypatch):
    _paywall(monkeypatch, "platinum", palace="plus")
    assert E.plan_of("u") == "free" and E.allowed("u", "palace")["ok"] is False


# ── every way of making a format goes through it ───────────────────────────

def _project():
    return srv.create_project("Law School", "1L year", "studying")["project_id"]


def test_create_timeline_is_checked_on_the_format_the_brief_builds(monkeypatch):
    pid = _project()
    _paywall(monkeypatch, "free", palace="plus", system="plus")
    r = srv.create_timeline(pid, {**SAMPLE["brief"], "mode": "palace"})
    assert r.get("error") == "needs_plan" and r["format"] == "palace" and r["plan"] == "plus"
    r = srv.create_timeline(pid, {**SAMPLE["brief"], "mode": "outline", "layout": "solar"})
    assert r.get("error") == "needs_plan" and r["format"] == "system"
    r = srv.create_timeline(pid, SAMPLE["brief"])                                   # a sketch is in every plan
    assert "error" not in r, r
    E.set_plan_lookup(lambda uid: "plus")
    r = srv.create_timeline(pid, {**SAMPLE["brief"], "timeline_id": "pal", "mode": "palace"})
    assert r.get("error") != "needs_plan", r


def test_build_timeline_is_checked_only_when_it_turns_the_timeline_into_another_format(monkeypatch):
    pid = _project()
    outline = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))["brief"]
    tid = srv.create_timeline(pid, {**outline, "layout": "tree"})["timeline_id"]
    _paywall(monkeypatch, "free", system="plus", lanes="plus")
    srv.record_materials_consent(tid, [{"kind": "paste", "name": "notes"}], True)
    r = srv.build_timeline(tid, layout="solar")
    assert r.get("error") == "needs_plan" and r["format"] == "system", r
    assert srv.build_timeline(tid).get("error") != "needs_plan"                      # same format: not a conversion


def test_the_palace_tools_refuse_before_they_touch_anything(monkeypatch):
    _paywall(monkeypatch, "free", palace="plus", world="plus", building="plus")
    for fn, fmt in ((srv.set_up_palace, "palace"), (srv.set_up_world, "world"), (srv.set_up_building, "building")):
        r = fn("anything", "Paris") if fn is srv.set_up_palace else fn("anything")
        assert r.get("error") == "needs_plan" and r["format"] == fmt, (fmt, r)


def test_with_the_beta_open_the_palace_tools_reach_their_own_checks():
    r = srv.set_up_world("no-such-timeline")
    assert r.get("error") != "needs_plan"


# ── the homepage sheet ─────────────────────────────────────────────────────

def test_the_sheet_knows_exactly_the_formats_the_check_knows():
    h = HOME.read_text(encoding="utf-8")
    block = h[h.index("const CONVERT_FORMATS = ["):h.index("function altoConvertPrompt")]
    rows = re.findall(r"\['(\w+)', '([^']+)', '([^']*)'\]", block)
    assert [r[0] for r in rows] == list(E.FORMATS)
    assert {r[0]: r[1] for r in rows} == E.LABELS
    assert {r[0] for r in rows if r[2]} == set(E.NEEDS_PLACE)
    assert "btn('Turn into another format…'" in h


# in a browser (the same homepage rig as the print tests) ------------------

pw = pytest.importorskip("playwright.sync_api")
from test_print_views import browser, homepage      # noqa: E402,F401  (fixtures)


def _open_sheet(pg):
    pg.locator("a.course-tile.live .tile-more").click()
    rows = [b.inner_text() for b in pg.locator(".share-menu .sm-body button").all()]
    pg.locator(".share-menu .sm-body button", has_text="Turn into another format…").click()
    return rows


def test_the_menu_row_sits_after_print_and_opens_the_other_formats(homepage):
    ctx, pg, errors = homepage
    rows = _open_sheet(pg)
    assert rows.index("Turn into another format…") == rows.index("Print…") + 1 < rows.index("Delete timeline…")
    picks = [b.get_attribute("data-format") for b in pg.locator(".share-menu .sm-pick").all()]
    assert len(picks) == len(E.FORMATS) - 1 and set(picks) < set(E.FORMATS)             # every format but the file's own
    assert errors == []


def test_the_claude_route_copies_one_prompt_that_adds_nothing_and_needs_no_server(homepage):
    ctx, pg, errors = homepage
    _open_sheet(pg)
    pg.locator('.share-menu .sm-pick[data-format="building"]').click()
    prompt = pg.locator(".share-menu textarea.sm-prompt").input_value()
    assert 'Turn my Alto timeline "Contracts"' in prompt and "Memory palace (a building)" in prompt
    assert "leave the original as it is" in prompt and "do not add a card, fact, date or case that is not in it" in prompt
    assert "Ask me which building to use before you start." in prompt
    assert [b.inner_text() for b in pg.locator(".share-menu .sm-pick").all()] == ["Copy the prompt for Claude"]
    pg.locator('.share-menu .sm-quiet', has_text="Back").click()
    pg.locator('.share-menu .sm-pick[data-format="outline"], .share-menu .sm-pick[data-format="lanes"]').first.click()
    assert "Ask me which" not in pg.locator(".share-menu textarea.sm-prompt").input_value()
    assert errors == []


def test_a_build_can_add_its_own_route_and_a_place_is_asked_first(homepage):
    ctx, pg, errors = homepage
    pg.evaluate("window._altoConvertRoutes = [{label:'Make it with Test', run:(p, f, ui) => { window.__ran = [f, ui.place]; ui.close(); }}]")
    _open_sheet(pg)
    pg.locator('.share-menu .sm-pick[data-format="palace"]').click()
    assert [b.inner_text() for b in pg.locator(".share-menu .sm-pick").all()] == ["Make it with Test", "Copy a prompt for Claude instead"]
    pg.locator(".share-menu .sm-pick", has_text="Make it with Test").click()
    assert "Say which city first." in pg.locator(".share-menu .sm-status").inner_text()
    assert pg.evaluate("window.__ran") is None
    pg.locator(".share-menu input.sm-place").fill("Paris")
    pg.locator(".share-menu .sm-pick", has_text="Make it with Test").click()
    assert pg.evaluate("window.__ran") == ["palace", "Paris"] and not pg.locator(".share-scrim").count()
    assert errors == []


def test_a_format_the_server_says_no_to_is_greyed_with_its_plan(homepage):
    ctx, pg, errors = homepage
    pg.evaluate("window._altoFormatAccess = { world: { ok: false, plan: 'plus' } }")
    _open_sheet(pg)
    b = pg.locator('.share-menu .sm-pick[data-format="world"]')
    assert b.is_disabled() and "In the plus plan" in b.inner_text()
    assert pg.locator('.share-menu .sm-pick[data-format="outline"], .share-menu .sm-pick[data-format="lanes"]').first.is_enabled()
    assert errors == []


def test_a_route_that_cannot_make_a_format_is_not_offered_for_it(homepage):
    ctx, pg, errors = homepage
    pg.evaluate("window._altoConvertRoutes = [{label:'Make it with Test', formats:['outline','system'], run:() => {}}]")
    _open_sheet(pg)
    pg.locator('.share-menu .sm-pick[data-format="building"]').click()
    assert [b.inner_text() for b in pg.locator(".share-menu .sm-pick").all()] == ["Copy the prompt for Claude"]
    assert pg.locator(".share-menu input.sm-place").count() == 0
    pg.locator(".share-menu .sm-quiet", has_text="Back").click()
    pg.locator('.share-menu .sm-pick[data-format="system"], .share-menu .sm-pick[data-format="outline"]').first.click()
    assert "Make it with Test" in [b.inner_text() for b in pg.locator(".share-menu .sm-pick").all()]
    assert errors == []


def test_a_route_can_ask_before_it_spends_and_can_hide_itself(homepage):
    ctx, pg, errors = homepage
    pg.evaluate("""window._altoConvertRoutes = [
      {label:'Hidden', when:() => false, run:() => {}},
      {label:'Ask first', run:(p, f, ui) => ui.confirm('About 200 credits. Go on?', 'Make it').then(y => { window.__asked = y; ui.status(y ? 'Done: 3 cards in, 3 out.' : 'no'); })}]""")
    _open_sheet(pg)
    pg.locator('.share-menu .sm-pick[data-format="outline"], .share-menu .sm-pick[data-format="system"]').first.click()
    labels = [b.inner_text() for b in pg.locator(".share-menu .sm-pick").all()]
    assert labels == ["Ask first", "Copy a prompt for Claude instead"]                  # the hidden route is not offered
    pg.locator(".share-menu .sm-pick", has_text="Ask first").click()
    assert "About 200 credits" in pg.locator(".share-menu .sm-note").inner_text()
    pg.locator(".share-menu .sm-pick", has_text="Make it").click()
    pg.wait_for_function("window.__asked === true")
    assert "3 cards in, 3 out" in pg.locator(".share-menu .sm-note").inner_text()          # the result reads in ink at the top, the old question gone
    assert "Go on?" not in pg.locator(".share-menu .sm-note").inner_text()
    assert pg.locator(".share-menu .sm-quiet", has_text="Close").count() == 1
    assert errors == []


def test_with_a_route_on_offer_the_prompt_is_shown_only_after_the_second_choice(homepage):
    ctx, pg, errors = homepage
    pg.evaluate("window._altoConvertRoutes = [{label:'Make it with Test', run:() => {}}]")
    _open_sheet(pg)
    pg.locator('.share-menu .sm-pick[data-format="outline"], .share-menu .sm-pick[data-format="system"]').first.click()
    assert not pg.locator(".share-menu textarea.sm-prompt").is_visible()                 # the primary choice is not outweighed
    pg.locator(".share-menu .sm-pick", has_text="Copy a prompt for Claude instead").click()
    assert pg.locator(".share-menu textarea.sm-prompt").is_visible()
    assert errors == []


def test_the_sheet_reads_in_ink_and_its_phone_rows_are_44px(homepage):
    ctx, pg, errors = homepage
    pg.evaluate("window._altoFormatAccess = { world: { ok: false, plan: 'plus' } }")
    _open_sheet(pg)
    got = pg.evaluate("""() => { const c = e => getComputedStyle(e).color, t = document.querySelector('.share-menu .sm-title');
      return {cancel: c(document.querySelector('.share-menu .sm-quiet')) === c(t), plan: c(document.querySelector('.share-menu .sm-pick[data-format="world"] small')) === c(t),
              row: document.querySelector('.share-menu .sm-pick[data-format="outline"], .share-menu .sm-pick[data-format="system"]').getBoundingClientRect().height} }""")
    assert got["cancel"] and got["plan"] and got["row"] < 44                             # desktop rows are as they were
    assert pg.evaluate("getComputedStyle(document.querySelector('.share-menu .sm-pick[data-format=\"world\"]')).opacity") == "1"     # not dimmed: the plan line keeps its ink
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(200)
    rows = pg.evaluate("[...document.querySelectorAll('.share-menu .sm-pick, .share-menu .sm-quiet')].map(b => b.getBoundingClientRect().height)")
    assert rows and min(rows) >= 44, rows
    assert errors == []

