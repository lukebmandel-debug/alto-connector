"""No show-through behind an open overlay (Luke, 2026-10-30, his Torts Overview in Safari: "You see the problem at the top?
Fix it across everything that is affected"; "It affects notes as well"). With the bars clear (clear_top.py) an Overview or
Notes panel that began under them left the timeline showing above it as a cut strip, and the Overview stopped short of the
window's foot. Here each panel, open on a desktop page in every format and style, must cover the window top to bottom: a
point in the strip above the old panel top, or along the foot, lands on the panel (or on a control of the bars floating over
it), never on the timeline. Chromium and WebKit; skipped when Playwright is not installed."""
import json
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from alto.build import retro  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FORMATS = {"timeline": ("contracts_brief", {}), "outline": ("outline_brief", {}), "lanes": ("lanes_brief", {}),
           "system": ("outline_brief", {"layout": "solar", "hub_look": "hub"})}
OVERLAYS = {"overview": ("summary-wrap", "toggleSummary()"), "notes": ("notes-panel", "toggleNotes()")}


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    t = tmp_path_factory.mktemp("overlay")
    for name, (src, extra) in FORMATS.items():
        d = json.loads((ROOT / "samples" / f"{src}.json").read_text(encoding="utf-8"))
        d["brief"].update(extra)
        b, nodes, conns = load_brief(d)
        (t / f"{name}.html").write_text(build_timeline(b, nodes, conns)[0], encoding="utf-8")
    return t


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def browser(request):
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


# every point of the strip above where the panel used to start, and of the foot, across the panel's width: what is there?
PROBE = """([id])=>{const p=document.getElementById(id), r=p.getBoundingClientRect(), H=innerHeight, W=innerWidth,
  nb=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-bottom'))||0,
  z=parseFloat(getComputedStyle(document.documentElement).zoom)||1, top=nb*z, bad=[];
  const l=Math.max(0,r.left)+4, w=Math.min(W,r.right)-4-l;
  for(const y of [1, top*.25, top*.5, top*.75, top+4, H-12, H-6, H-1]) for(let i=0;i<=12;i++){ const x=l+w*i/12, e=document.elementFromPoint(x,y);
    if(e && !p.contains(e) && e.closest('#canvas,#world,#page-glass,#glass-slab')) bad.push([Math.round(x),Math.round(y),e.id||e.className||e.tagName]); }
  return {top:r.top, bottom:r.bottom, H:H, bad:bad.slice(0,6)};}"""


def _open(pg, overlay):
    pid, js = OVERLAYS[overlay]
    pg.evaluate(js)
    pg.wait_for_timeout(200)       # (the slide starts) and then runs out: WebKit's can take well over its .42s
    pg.wait_for_function("id=>!document.getElementById(id).getAnimations().length", arg=pid, timeout=8000)
    pg.wait_for_timeout(100)
    return pid


def _check(pg, overlay, label):
    pid = _open(pg, overlay)
    r = pg.evaluate(PROBE, [pid])
    try:
        assert r["top"] <= 0.5, f"{label}: {overlay} starts {r['top']:.1f}px below the top"
        assert r["bottom"] >= r["H"] - 0.5, f"{label}: {overlay} ends {r['H'] - r['bottom']:.1f}px above the foot"
        assert not r["bad"], f"{label}: the timeline shows behind the {overlay}: {r['bad']}"
    finally:
        _open(pg, overlay)      # (shut again)


@pytest.mark.parametrize("fmt", list(FORMATS))
def test_no_showthrough_behind_overlays(browser, pages, fmt):
    pg = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
    pg.goto((pages / f"{fmt}.html").as_uri())
    pg.wait_for_timeout(1500)
    for look in ("classic light", "classic dark", "retro"):
        if look == "classic dark":
            pg.evaluate("document.getElementById('mode-toggle').click()")
        elif look == "retro":
            pg.add_script_tag(content=retro.ASSET)
            pg.evaluate("window._altoRetro.on()")
        pg.wait_for_timeout(500)
        for overlay in OVERLAYS:
            _check(pg, overlay, f"{browser.browser_type.name} {fmt} {look}")
    pg.close()


def test_the_overview_over_a_detail_page_reaches_the_foot(browser, pages):
    """A detail page keeps its bars (clear_top.py), so the Overview opens under them there; it must still reach the foot."""
    pg = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
    pg.goto((pages / "timeline.html").as_uri())
    pg.wait_for_timeout(1500)
    pg.evaluate("showDetail('node', 'lucy-v-zehmer')")      # (contracts_brief's first case)
    pg.wait_for_timeout(800)
    assert pg.evaluate("document.documentElement.classList.contains('detail-open')")
    _open(pg, "overview")
    r = pg.evaluate(PROBE, ["summary-wrap"])
    assert r["bottom"] >= r["H"] - 0.5, f"the Overview ends {r['H'] - r['bottom']:.1f}px above the foot"
    pg.close()
