"""With a filter on, stepping (arrow keys, swipes, the next / previous buttons)
goes only between the nodes the filter shows, in every format; with none on,
stepping is as it was. Every format asks one test, `window._altoShown(id)`
(filter_panel.py), whether a node is shown."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.filter_panel import FILTER_PANEL_GLUE  # noqa: E402
from alto.build import engine_patches, lanes, lanes_nav, palace, solar_draw  # noqa: E402

SAMPLES = ROOT / "samples"
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def _with_filter(d):
    """A custom filter that keeps every third node (Heavy), the rest Light."""
    d = copy.deepcopy(d)
    d["brief"]["filters"] = [{"id": "imp", "label": "Importance", "source": "custom",
                              "values": [{"id": "heavy", "name": "Heavy"}, {"id": "light", "name": "Light"}]}]
    for i, n in enumerate(d["nodes"]):
        n["filters"] = {"imp": "heavy" if i % 3 == 0 else "light"}
    return d


def _sample(name, **brief):
    d = json.loads((SAMPLES / name).read_text(encoding="utf-8"))
    d["brief"].update(brief)
    return d


def _palace():
    import test_palace as tp
    return tp.bundle()


FORMATS = {
    "timeline": lambda: _sample("contracts_brief.json"),
    "lanes": lambda: _sample("lanes_v2_brief.json"),
    "outline": lambda: _sample("outline_brief.json"),
    "system": lambda: _sample("outline_brief.json", layout="solar", hub_look="hub"),
    "palace": _palace,
}


# ── one predicate, asked everywhere ─────────────────────────────────────────
def test_one_shared_predicate_every_format_asks():
    assert "window._altoShown=function(id){" in FILTER_PANEL_GLUE
    assert "window._altoFilterOn=function(){" in FILTER_PANEL_GLUE
    assert "(!window._altoShown||window._altoShown(id))" in engine_patches._CHIP_KEEP
    assert "_altoFilterOn" in engine_patches._CHIP_ON
    assert "window._altoShown(n.id.slice(5))" in engine_patches._ARROWS_NEW
    for mod in (lanes, lanes_nav, palace, solar_draw):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "window._altoShown" in src, mod.__name__
        # no format keeps its own copy of the dimmed-class test for stepping
        assert "!c.classList.contains('ent-dimmed') && !c.classList.contains('rel-dimmed')" not in src
    assert "window._altoShown" in lanes.LANES_JS


# ── in a browser ────────────────────────────────────────────────────────────
try:
    import playwright.sync_api as pw
except Exception:                                    # pragma: no cover
    pw = None


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:                                    # no bundled Chromium: the installed Chrome will do
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = tmp_path_factory.mktemp("filternav")
    out = {}
    for k, f in FORMATS.items():
        html, _ = build_timeline(*load_brief(_with_filter(f())))
        out[k] = d / f"{k}.html"
        out[k].write_text(html, encoding="utf-8")
    return out


# (a custom filter takes the first free slot: era here)
HEAVY = "() => NODES_SRC.filter(n => n.era === 'heavy' || n.examWeight === 'heavy').map(n => n.id)"
CHIP = """() => { const b=document.querySelector('#ef-panel .ef-chip[data-fid="heavy"]'); b.click(); return true; }"""
WHERE = "() => window._focusedNodeId || (document.getElementById('detail-page').classList.contains('visible') && window._currentDetailId) || null"


def _open(browser, f, phone=False):
    kw = (dict(viewport={"width": 390, "height": 844}, has_touch=True, user_agent=PHONE_UA, device_scale_factor=2,
               is_mobile=browser.browser_type.name == "chromium")
          if phone else dict(viewport={"width": 1400, "height": 900}))
    ctx = browser.new_context(**kw)
    pg = ctx.new_page()
    errs = []
    # (the first-person ride is a hosted file a file:// page cannot load: not this test's business)
    pg.on("pageerror", lambda e: None if "palace-ride" in str(e) else errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(2500)
    return pg, errs


def _start(pg, heavy):
    """A node the filter hides, with shown nodes after it (the step must find the nearest one)."""
    order = pg.evaluate("() => NODE_ORDER.slice()")
    return next(i for i in order[1:] if i not in heavy)


def _press(pg, key, n):
    seen = []
    for _ in range(n):
        pg.keyboard.press(key)
        pg.wait_for_timeout(800)
        try:                                        # (a System hop glides with nothing enlarged: wait for it to land)
            pg.wait_for_function(WHERE, timeout=2500)
        except Exception:
            pass
        seen.append(pg.evaluate(WHERE))
    return seen


@pytest.mark.parametrize("fmt", list(FORMATS))
def test_arrows_step_only_through_what_the_filter_shows(browser, pages, fmt):
    pg, errs = _open(browser, pages[fmt])
    try:
        heavy = set(pg.evaluate(HEAVY))
        start = _start(pg, heavy)
        assert pg.evaluate("() => window._altoFilterOn()") is False
        pg.evaluate(CHIP)
        pg.wait_for_timeout(500)
        assert pg.evaluate("() => window._altoFilterOn()") is True
        assert {i for i in pg.evaluate("() => NODE_ORDER.slice()") if pg.evaluate("id => window._altoShown(id)", i)} == heavy
        pg.evaluate("id => window.enterFocus(id)", start)
        pg.wait_for_timeout(1000)
        seen = _press(pg, "ArrowRight", 3) + _press(pg, "ArrowDown", 2) + _press(pg, "ArrowLeft", 2)
        moved = [s for s in seen if s and s != start]
        assert moved, seen
        assert all(s in heavy for s in moved), (seen, sorted(heavy))
        assert not errs, errs
    finally:
        pg.context.close()


@pytest.mark.parametrize("fmt", ["timeline", "outline", "system", "palace"])
def test_detail_page_next_buttons_skip_what_the_filter_hides(browser, pages, fmt):
    pg, errs = _open(browser, pages[fmt])
    try:
        heavy = set(pg.evaluate(HEAVY))
        start = _start(pg, heavy)
        pg.evaluate(CHIP)
        pg.wait_for_timeout(500)
        pg.evaluate("id => window.showDetail('node', id)", start)
        pg.wait_for_timeout(900)
        seen = []
        for _ in range(3):
            pg.evaluate("() => document.getElementById('nav-next').click()")
            pg.wait_for_timeout(700)
            seen.append(pg.evaluate("() => window._currentDetailId"))
        seen += _press(pg, "ArrowRight", 2)
        assert all(s in heavy for s in seen), (seen, sorted(heavy))
        assert len(set(seen)) > 1
        assert not errs, errs
    finally:
        pg.context.close()


@pytest.mark.parametrize("fmt", ["timeline", "outline", "lanes", "system"])
def test_phone_cards_step_only_through_what_the_filter_shows(browser, pages, fmt):
    pg, errs = _open(browser, pages[fmt], phone=True)
    try:
        heavy = set(pg.evaluate(HEAVY))
        start = _start(pg, heavy)
        pg.evaluate("id => window.featureNode(id, false)", start)
        pg.wait_for_timeout(500)
        pg.evaluate(CHIP)
        pg.wait_for_timeout(700)
        seen = [pg.evaluate("() => window._featuredNodeId")]
        for _ in range(3):
            pg.evaluate("() => document.getElementById('tlb-next').click()")
            pg.wait_for_timeout(700)
            seen.append(pg.evaluate("() => window._featuredNodeId"))
        assert all(s in heavy for s in seen), (seen, sorted(heavy))
        assert len(set(seen)) > 1
        assert not errs, errs
    finally:
        pg.context.close()


@pytest.mark.parametrize("fmt", ["timeline", "lanes", "system"])
def test_with_no_filter_steps_are_unchanged(browser, pages, fmt):
    """No filter: the same steps reach the nodes a filter would hide."""
    pg, errs = _open(browser, pages[fmt])
    try:
        heavy = set(pg.evaluate(HEAVY))
        start = _start(pg, heavy)
        pg.evaluate("id => window.enterFocus(id)", start)
        pg.wait_for_timeout(1000)
        seen = _press(pg, "ArrowRight", 3) + _press(pg, "ArrowDown", 2)
        assert any(s and s not in heavy for s in seen), seen
        assert not errs, errs
    finally:
        pg.context.close()
