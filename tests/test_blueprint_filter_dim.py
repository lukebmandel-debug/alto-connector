"""Luke 2026-11-01: "filters dim things that don't apply ... I was just looking at memory blueprint and things don't dim with the filter on."
The Memory Blueprint dims what a filter hides the way the Atlas does (palace_world.py): the engine's hidden board marks a card .dimmed / .ent-dimmed / .rel-dimmed, and the
blueprint fades that card's chip, its row in the card list, and a room (and its name) when every card in it is hidden. Chromium and WebKit over real local HTTP."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import building_schema as bs  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from tests.building_fpv_support import Server  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _doc():
    import test_building_palace_tools as tbp
    d = {"brief": tbp.brief(), "nodes": json.loads(json.dumps(tbp.NODES))}
    d = copy.deepcopy(d)
    d["brief"]["filters"] = [{"id": "imp", "label": "Importance", "source": "custom",
                              "values": [{"id": "heavy", "name": "Heavy"}, {"id": "light", "name": "Light"}]}]
    for i, n in enumerate(d["nodes"]):
        n["filters"] = {"imp": "heavy" if i % 3 == 0 else "light"}
    return d


STATE = """() => { const R = document.getElementById('bldg-root'), D = AltoBuilding.data, out = [], keep = [];
  const dimmed = id => { const c = document.querySelector('#node-' + id + ' .node-card'); return !!(c && /(^| )(dimmed|ent-dimmed|rel-dimmed)( |$)/.test(c.className)); };
  Object.keys(D.nodes).forEach(id => (dimmed(id) ? out : keep).push(id));
  const pill = id => R.querySelector('.bl-pill[data-node="' + id + '"]');
  return {out, keep, nPills: R.querySelectorAll('.bl-pill').length,
          outNotDim: out.filter(id => pill(id) && !pill(id).classList.contains('bl-dim')),
          keepDim: keep.filter(id => pill(id) && pill(id).classList.contains('bl-dim')),
          outPills: out.filter(id => pill(id)).length, keepPills: keep.filter(id => pill(id)).length,
          roomsDim: R.querySelectorAll('.bl-room.bl-dim').length,
          roomsWant: [...R.querySelectorAll('.bl-room[data-room]')].filter(e => { const l = AltoBuilding.nodesIn(e.getAttribute('data-room')); return l.length && l.every(id => out.includes(id)); }).length, labsDim: R.querySelectorAll('[data-lab].bl-dim').length}; }"""


@pytest.fixture(scope="module")
def view(browser):
    html, _ = build_timeline(*load_brief(_doc()))
    srv = Server()
    srv.html, srv.plan = html, bs.hosted_json(bs.fixture())[1]
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(srv.origin + "/index.html")
    page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
    page.wait_for_selector("#bldg-root .bl-tab", timeout=30000)
    page.evaluate("(() => { const t = [...document.querySelectorAll('#bldg-root .bl-tab:not([data-level=\"outside\"])')]; const w = t.find(b => AltoBuilding.plan.rm.some(r => r.l === b.getAttribute('data-level') && AltoBuilding.nodesIn(r.id).length)) || t[0]; w.click(); })()")   # a floor (the chips are drawn on floors, not outside)
    page.wait_for_selector("#bldg-root .bl-pill", timeout=30000)
    yield page, errors
    try:
        page.close()
    finally:
        srv.close()


CHIP = "(() => { const b = document.querySelector('#ef-panel .ef-chip[data-fid=\"heavy\"]'); if (!b) return false; b.click(); return true; })()"


# The steps run in order on one page (each its own test so a failure names the step).
def test_1_with_no_filter_nothing_dims(view):
    page, _ = view
    s = page.evaluate(STATE)
    assert s["out"] == [] and s["roomsDim"] == 0 and s["nPills"] > 0, s


def test_2_the_filter_chip_hides_some_cards_and_keeps_others(view):
    page, _ = view
    assert page.evaluate(CHIP), "no #ef-panel heavy chip"
    page.wait_for_timeout(700)
    s = page.evaluate(STATE)
    assert s["out"] and s["keep"], s


def test_3_every_hidden_cards_chip_is_dimmed_and_no_shown_one_is(view):
    page, _ = view
    s = page.evaluate(STATE)
    assert s["outPills"] > 0 and s["outNotDim"] == [] and s["keepDim"] == [], s                    # (before the fix nothing dimmed)
    op = page.evaluate("""() => { const e = document.querySelector('#bldg-root .bl-pill.bl-dim'); return e && +getComputedStyle(e).opacity; }""")
    assert op is not None and abs(op - 0.28) < 0.01, op                                           # Art: a hidden card's chip at .28 (was .16)


def test_4_a_room_whose_cards_are_all_hidden_fades(view):
    page, _ = view
    s = page.evaluate(STATE)
    assert s["roomsDim"] == s["roomsWant"], s


def test_5_the_card_list_rows_of_hidden_cards_fade(view):
    page, _ = view
    s = page.evaluate(STATE)
    page.keyboard.press("c")
    page.wait_for_timeout(300)
    rows = page.evaluate("""(out) => [...document.querySelectorAll('#bldg-root .bl-cards button[data-node]')].map(b => [out.includes(b.getAttribute('data-node')), b.classList.contains('bl-dim')])""", s["out"])
    assert rows and all(a == b for a, b in rows), rows
    page.keyboard.press("Escape")


def test_6_chip_off_and_everything_is_back(view):
    page, errors = view
    assert page.evaluate(CHIP)
    page.wait_for_timeout(700)
    s = page.evaluate(STATE)
    assert s["out"] == [] and page.evaluate("document.querySelectorAll('#bldg-root .bl-dim').length") == 0, s
    assert not [e for e in errors if "Failed to load" not in e], errors
