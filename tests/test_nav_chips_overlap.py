"""The top bar's chips never cover each other (Luke, 2026-11-01, his Civil Procedure Memory Blueprint in Holographic: "one chip is cutting off another").

Measured in a real browser at every width and in every style: each chip's box, each group label's painted plate (its box plus the box-shadow
spread that pads it), the page's chips-collapse x, and the Blueprint's name chip. None may meet another. Checked in WebKit first (Luke
uses Safari) and in Chromium where each is installed. Skipped without Playwright (the repo venv has none; see the 1.9.62 notes)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs, holo, palace_assets, retro  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from tests.test_building_palace_tools import NODES, brief as building_brief  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

ORIGIN = "http://alto.test"
WIDTHS = (700, 820, 1024, 1280, 1440, 1920)
STYLES = ("classic", "dark", "retro", "holo")
TYPES = ["Personal Jurisdiction", "Subject Matter", "Venue", "Pleading", "Joinder", "Discovery", "Summary Judgment", "Preclusion"]
ELEMENTS = ["Notice", "Standing", "Collateral Attack", "Ripeness"]
AUTHORITIES = ["Pennoyer", "Erie", "Twombly"]

MEASURE = r"""()=>{
 const R=e=>{const q=e.getBoundingClientRect();return {l:q.left,t:q.top,r:q.right,b:q.bottom}};
 const nav=document.getElementById('nav'); if(!nav) return {err:'no nav'};
 const items=[...nav.querySelectorAll('button.nav-btn,.nav-group-label')].filter(e=>e.offsetWidth).map(e=>{
   const q=R(e), cs=getComputedStyle(e), label=e.classList.contains('nav-group-label');
   let spread=0; const sh=cs.boxShadow;
   if(label&&sh&&sh!=='none'&&cs.backgroundColor!=='rgba(0, 0, 0, 0)'){ const parts=sh.replace(/rgba?\([^)]*\)/g,'').trim().split(/\s+/); if(parts.length>=4) spread=parseFloat(parts[3])||0; }
   return {label, t:e.textContent.trim().slice(0,18), q, plate:{l:q.l-spread,t:q.t-spread,r:q.r+spread,b:q.b+spread}}});
 const box=s=>{const e=document.querySelector(s); return e&&e.offsetWidth?R(e):null;};
 return {items, x:box('#ct-chips'), head:box('#bldg-root:not([hidden]) .bl-head'), vw:innerWidth};}"""


def _inter(a, b):
    return min(a["r"], b["r"]) - max(a["l"], b["l"]) > 0.5 and min(a["b"], b["b"]) - max(a["t"], b["t"]) > 0.5


def collisions(m):
    """What meets what in one measured page: [(kind, a, b)]."""
    bad, it = [], m["items"]
    plate = lambda e: e["plate"]
    for i, a in enumerate(it):
        for c in it[i + 1:]:
            ra, rc = (a["q"] if not a["label"] else plate(a)), (c["q"] if not c["label"] else plate(c))
            if _inter(ra, rc):
                bad.append(("overlap", a["t"], c["t"]))
        if a["q"]["r"] > m["vw"] + 1 or a["q"]["l"] < -1:
            bad.append(("off the window", a["t"]))
    for name in ("x", "head"):
        if m.get(name):
            bad += [(name + " over", a["t"]) for a in it if _inter(m[name], plate(a))]
    return bad


def _chip_page():
    """A Memory Blueprint page whose bar carries a full, wrapping chip row (types, elements, authorities and an index)."""
    nodes = json.loads(json.dumps(NODES))
    for n in nodes:
        n.update(entity_ids=["e0"], axis1_values=["x0"], axis2_values=["a0"])
    ents = [{"id": "e%d" % i, "name": n, "role": "r", "color": "#4a9eff", "sections": [{"h": "S", "t": "t"}]} for i, n in enumerate(TYPES)]
    axes = [{"label": "Elements", "singular": "Element", "values": [{"id": "x%d" % i, "name": n} for i, n in enumerate(ELEMENTS)]},
            {"label": "Authorities", "singular": "Authority", "values": [{"id": "a%d" % i, "name": n} for i, n in enumerate(AUTHORITIES)]}]
    b, ns, cs = load_brief({"brief": building_brief(entities=ents, axes=axes, entity_axis_label="Types", entity_axis_singular="Type"), "nodes": nodes})
    return build_timeline(b, ns, cs)[0]


@pytest.fixture(scope="module", params=("webkit", "chromium"))
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def html():
    return _chip_page()


def _open(browser, html, width, style):
    pname, ptext = bs.hosted_json(bs.fixture())

    def route(r):
        path = r.request.url[len(ORIGIN):].split("?")[0]
        if path in ("/", "/index.html"):
            return r.fulfill(status=200, content_type="text/html", body=html)
        if path == "/alto-cloud.js":
            return r.fulfill(status=200, content_type="text/javascript", body="")
        hit = palace_assets.find(path, building_plans={pname: ptext}) if path.startswith("/bldg/") else None
        if hit:
            return r.fulfill(status=200, content_type=hit[0], body=hit[1])
        return r.fulfill(status=404, body="no")

    page = browser.new_page(viewport={"width": width, "height": 800})
    page.route(ORIGIN + "/**", route)
    page.goto(ORIGIN + "/index.html")
    try:
        page.wait_for_selector("#bldg-root .bl-head", state="attached", timeout=8000)
    except Exception:
        pass
    if style == "dark":
        page.evaluate("document.documentElement.classList.add('dark')")
    elif style == "retro":
        page.add_script_tag(content=retro.ASSET)
        page.evaluate("window._altoRetro && window._altoRetro.on()")
    elif style == "holo":
        page.add_script_tag(content=holo.ASSET)
        page.evaluate("window._altoHolo && window._altoHolo.on()")
    page.wait_for_timeout(900)
    return page


@pytest.mark.parametrize("style", STYLES)
def test_no_chip_label_or_panel_covers_another_chip_at_any_width(browser, html, style):
    seen = {}
    for w in WIDTHS:
        page = _open(browser, html, w, style)
        try:
            m = page.evaluate(MEASURE)
        finally:
            page.close()
        assert len(m.get("items", [])) >= 18, (w, m)                      # the whole row was measured (3 labels + 15 chips)
        bad = collisions(m)
        if bad:
            seen[w] = bad[:6]
    assert not seen, f"{style}: chips covered by a label plate, the x or the name chip, by width: {seen}"


def test_the_blueprint_name_chip_stands_below_the_chip_rows(browser, html):
    for w in (820, 1280, 1920):
        page = _open(browser, html, w, "classic")
        try:
            m = page.evaluate(MEASURE)
        finally:
            page.close()
        assert m["head"], f"the Blueprint's name chip is not on the page at {w}"
        low = max(i["q"]["b"] for i in m["items"])
        assert m["head"]["t"] >= low - 0.5, (w, m["head"], low)


def test_the_overlap_check_itself_sees_a_label_plate_over_a_chip():
    chip = {"label": False, "t": "Venue", "q": {"l": 100, "t": 0, "r": 160, "b": 20}, "plate": {"l": 100, "t": 0, "r": 160, "b": 20}}
    lab = {"label": True, "t": "Element", "q": {"l": 60, "t": 0, "r": 96, "b": 20}, "plate": {"l": 54, "t": -6, "r": 102, "b": 26}}
    assert collisions({"items": [lab, chip], "vw": 1280})
    lab["plate"] = {"l": 56, "t": -4, "r": 100, "b": 24}                       # a 4px plate in a 5px gap: clear
    chip["q"]["l"] = 101
    assert not collisions({"items": [lab, chip], "vw": 1280})
