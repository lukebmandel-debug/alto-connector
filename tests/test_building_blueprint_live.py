"""The Memory Blueprint as Luke's civ-pro-museum page is built (2026-10-23): "the museum disappeared" — the page named the renderer of the release that
built it (1.9.154), a later deploy (1.9.155) took that file away, and the page fell back to the timeline's cards. Now the page falls back to the
newest renderer under a fixed name, a deploy keeps earlier renderers, and with no renderer at all the page says so instead of showing cards
(Luke: "we don't need the card view for that style"). Also the chips while zooming in WebKit (Luke uses Safari): pinned, one size, no jump.

A page shaped like civ-pro-museum (92 nodes, the PMA plan, rooms mode), served over real HTTP (WebKit does not route the page's synchronous
loader), in Chromium and WebKit. Skipped without Playwright."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import buildings  # noqa: E402
from alto.build import building_schema as bs, palace_assets  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.palace_building_asset import BUILDING_LATEST, BUILDING_PATH  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

PLAN = buildings.load("pma")
ACTS = [{"label": f"Part {i}", "color": c} for i, c in enumerate(("#7c5cff", "#e0813f", "#2f9e6b", "#d4509a", "#3f8fe0", "#c9a227"))]


def _html():
    nodes = [{"id": f"n{i}", "act": i * 6 // 92, "title": f"Concept number {i + 1}", "tag": "", "desc": "d"} for i in range(92)]
    b = {"title": "Civil Procedure — Memory Blueprint", "timeline_id": "civ-pro-museum", "mode": "palace", "palace_view": "building", "columns": 5,
         "node_noun": "Room", "period_noun": "Wing", "acts": ACTS,
         "building": {"plan_z": bs.pack(PLAN), "plan_h": bs.plan_hash(PLAN), "mode": "room", "assign": {}}}
    br, ns, cs = load_brief({"brief": b, "nodes": nodes})
    return build_timeline(br, ns, cs)[0]


@pytest.fixture(scope="module")
def site():
    if pw is None:
        pytest.skip("Playwright is not installed")
    from tests.building_fpv_support import Server
    srv = Server()
    srv.html, srv.plan = _html(), bs.hosted_json(PLAN)[1]
    yield srv
    srv.close()


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch()
        except Exception as e:
            try:
                b = p.chromium.launch(channel="chrome") if request.param == "chromium" else None
            except Exception:
                b = None
            if b is None:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


def _open(browser, site, block=()):
    site.block = set(block)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(site.origin + "/index.html")
    page.wait_for_timeout(300)
    return page, errors


STATE = """() => { const r = document.getElementById('bldg-root'), w = document.getElementById('world'), f = document.getElementById('bldg-fail');
  return {root: !!r && !r.hidden, open: document.documentElement.classList.contains('bldg-open'), world: w ? getComputedStyle(w).visibility : 'none',
          fail: f ? f.textContent : '', pills: document.querySelectorAll('#bldg-root .bl-pill').length,
          msg: (document.querySelector('#bldg-root .bl-msg') || {}).textContent || ''}; }"""


def test_the_blueprint_renders_and_the_cards_stay_hidden(browser, site):
    page, errors = _open(browser, site)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
        page.wait_for_timeout(300)
        st = page.evaluate(STATE)
        assert st["root"] and st["open"] and st["world"] == "hidden" and st["pills"] > 10 and not st["fail"]
        assert page.locator("#bldg-root .bl-tab").count() >= 3 and page.locator("#bldg-root .bl-room").count() > 20
        assert page.locator("#bldg-toggle").count() == 0                     # no card view to switch to
        assert errors == []
    finally:
        page.close()


def test_a_page_whose_renderer_was_taken_away_loads_the_newest_one(browser, site):
    page, errors = _open(browser, site, block=[BUILDING_PATH])               # as civ-pro-museum on 2026-10-23: its hashed renderer 404s
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
        st = page.evaluate(STATE)
        assert st["root"] and st["open"] and st["world"] == "hidden" and st["pills"] > 10 and not st["fail"]
        assert errors == []
    finally:
        page.close()


def test_no_renderer_at_all_says_so_and_shows_no_cards(browser, site):
    page, errors = _open(browser, site, block=[BUILDING_PATH, BUILDING_LATEST])
    try:
        page.wait_for_selector("#bldg-fail", timeout=10000)
        st = page.evaluate(STATE)
        assert "blueprint could not load" in st["fail"] and st["open"] and st["world"] == "hidden"
        assert page.evaluate("getComputedStyle(document.getElementById('bldg-fail')).position") == "fixed"
    finally:
        page.close()


def test_no_plan_keeps_the_blueprint_and_says_so(browser, site):
    page, errors = _open(browser, site, block=["/bldg/plan-"])
    try:
        page.wait_for_function("document.querySelector('#bldg-root .bl-msg') && /could not load/.test(document.querySelector('#bldg-root .bl-msg').textContent)",
                               timeout=10000)
        st = page.evaluate(STATE)
        assert st["root"] and st["open"] and st["world"] == "hidden"
    finally:
        page.close()


ZOOM = """async () => {
  const svg = document.querySelector('#bldg-root svg.bl-svg'), r = svg.getBoundingClientRect(), out = [];
  const raf = () => new Promise(f => requestAnimationFrame(f));
  const snap = (ph) => out.push({ph, m: (AltoMarkers.debug('bldg') || []).map(c => [c.id, c.x - c.w / 2 - c.ax, c.y - c.ay, c.w, c.op])});
  const wheel = (dy) => svg.dispatchEvent(new WheelEvent('wheel', {deltaY: dy, clientX: r.left + r.width * .47, clientY: r.top + r.height * .55, bubbles: true, cancelable: true}));
  const idle = async (ms, ph) => { const t0 = performance.now(); while (performance.now() - t0 < ms) { await raf(); snap(ph); } };
  snap('start');
  for (const [n, dy] of [[28, -14], [0, 0], [28, -14], [0, 0], [40, 14], [0, 0]]) {
    if (!n) { await idle(240, 'pause'); continue; }
    for (let i = 0; i < n; i++) { wheel(dy); await raf(); snap('in'); }
  }
  await idle(600, 'end'); return out; }"""


def test_chips_never_jump_while_the_blueprint_zooms(browser, site):
    # 1.9.160 in WebKit: a settled re-layout glided by CSS transition, which ran on after the next zoom began (chips drifted 15 px a frame beside
    # their anchors, then snapped by up to 380 px). The glide is driven frame by frame now and frozen by the next input.
    page, errors = _open(browser, site)
    try:
        page.wait_for_function("window.AltoBuilding && AltoBuilding.plan", timeout=30000)
        page.wait_for_timeout(500)
        fr = page.evaluate(ZOOM)
        assert len(fr[0]["m"]) > 10
        worst_in = worst_any = worst_w = 0
        for a, b in zip(fr, fr[1:]):
            A = {m[0]: m for m in a["m"]}
            for m in b["m"]:
                p = A.get(m[0])
                if not p or (m[4] < .5 and p[4] < .5):
                    continue
                d = max(abs(m[1] - p[1]), abs(m[2] - p[2]))
                worst_any = max(worst_any, d)
                if a["ph"] == b["ph"] == "in":
                    worst_in, worst_w = max(worst_in, d), max(worst_w, abs(m[3] - p[3]))
        assert worst_in < .6 and worst_w < .1, (worst_in, worst_w)          # while the wheel runs: pinned and one size
        assert worst_any < 30, worst_any                                      # a settle's glide moves in small steps, never one jump
        a = page.evaluate("AltoMarkers.debug('bldg')"); page.wait_for_timeout(250); b = page.evaluate("AltoMarkers.debug('bldg')")
        assert [(m["x"], m["y"]) for m in a] == [(m["x"], m["y"]) for m in b]   # settled: still
        assert errors == []
    finally:
        page.close()


def test_a_deploy_keeps_earlier_renderers_and_writes_the_newest_under_its_fixed_name(tmp_path):
    from alto import publish_static as ps
    names = {n for f, n, _t in palace_assets.assets() if f == "bldg"}
    assert BUILDING_LATEST.rsplit("/", 1)[1] in names and BUILDING_PATH.rsplit("/", 1)[1] in names
    d = tmp_path / "bldg"; d.mkdir()
    import os
    for i in range(15):
        for k in ("", "fpv-"):
            f = d / ("palace-building-%s%010x.js" % (k, i)); f.write_text("x"); os.utime(f, (1000 + i, 1000 + i))
    (d / "plan-000000000000.json").write_text("{}"); (d / "palace-building-latest.js").write_text("old")
    kept = ps._bldg_kept(d)
    assert len(kept) == 2 * ps.BLDG_KEEP and "palace-building-%010x.js" % 14 in kept and "palace-building-%010x.js" % 0 not in kept
    assert not any(n.startswith("plan-") or "latest" in n for n in kept)
    assert not any(r["source"].endswith("latest.js") for r in ps._bldg_rules(["palace-building-latest.js"]))   # the fixed name is never "immutable"
