"""Print... on a visual format opens with a one-page study sheet (alto/build/study_sheet.py).

Art's spec, 2026-11-01: a System prints a boxed unit map, the three Memory Palaces their route in order, on one
Letter/A4 portrait page in black and grey, then the outline pages as before. Every other format is untouched: its
page carries none of this. The homepage's Print... dialog says what page 1 is, in the same words desktop and phone.

Browser tests run in Chromium (skipped without it) with window.print stubbed: no print dialog, no network.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.engine_patches import PATCHES  # noqa: E402
from alto.build import study_sheet  # noqa: E402

OUTLINE = ROOT / "samples" / "outline_brief.json"
LANES = ROOT / "samples" / "lanes_brief.json"
HOME = ROOT / "alto" / "engine" / "home_template.html"


def _outline(units=None, layout="solar", fat=0):
    """The contracts outline as a System with `units` units (repeating its own units past five); `fat` extra
    concepts under unit 1's hub, to overflow its box."""
    d = json.loads(OUTLINE.read_text(encoding="utf-8"))
    if layout:
        d["brief"]["layout"] = layout
    acts, nodes = d["brief"]["acts"], d["nodes"]
    if units and units <= len(acts):
        d["brief"]["acts"] = acts[:units]
        d["nodes"] = [n for n in nodes if n["act"] < units]
    elif units:
        for a in range(len(acts), units):
            src = a % len(acts)
            d["brief"]["acts"].append({**acts[src], "label": f"UNIT {a + 1} — PART {a + 1}", "short": f"Unit {a + 1}"})
            ids = {n["id"]: f"{n['id']}-u{a}" for n in nodes if n["act"] == src}
            for n in [n for n in nodes if n["act"] == src]:
                m = copy.deepcopy(n)
                m.update(id=ids[n["id"]], act=a)
                if m.get("parent"):
                    m["parent"] = ids.get(m["parent"], m["parent"])
                d["nodes"].append(m)
    for i in range(fat):
        d["nodes"].append({"id": f"extra-{i}", "act": 0, "parent": "formation", "tag": "Concept",
                           "title": f"Extra concept number {i}", "desc": "d"})
    keep = {n["id"] for n in d["nodes"]}
    d["connections"] = [c for c in d["connections"] if c[0] in keep and c[1] in keep]
    return build_timeline(*load_brief(d))[0]


def _city(n=18):
    import test_palace_chrome as tpc
    b = copy.deepcopy(tpc.bundle())
    b["nodes"] = [{"id": f"n{i}", "act": i % 3, "tag": "Room", "title": f"Room {i}", "desc": "d"} for i in range(n)]
    return build_timeline(*load_brief(b))[0]


def _world():
    import test_world_palace as twp
    return twp.built()[0]


def _building():
    import test_building_palace_tools as tbp
    return tbp.built()[0]


# ── source ─────────────────────────────────────────────────────────────────

def test_the_patch_is_registered_and_anchored_once():
    p = {x["name"]: x for x in PATCHES}["outline-prints-as-an-outline"]
    assert p["count"] == 1 and "_altoStudySheet" in p["new"]


@pytest.mark.parametrize("kw,kind", [({"mode": "outline", "layout": "solar"}, "system"),
                                     ({"mode": "palace"}, "city"),
                                     ({"mode": "palace", "palace_view": "world"}, "world"),
                                     ({"mode": "palace", "palace_view": "building"}, "building"),
                                     ({"mode": "outline"}, ""), ({"mode": "outline", "layout": "tree"}, ""),
                                     ({"mode": "linear"}, ""), ({"mode": "lanes"}, "")])
def test_only_the_visual_formats_get_a_sheet(kw, kind):
    class B:
        layout, palace_view = "", "city"
    b = B()
    for k, v in kw.items():
        setattr(b, k, v)
    assert study_sheet.sheet_kind(b) == kind
    assert (study_sheet.study_sheet(b) != "") == bool(kind)


def test_pages_of_other_formats_carry_none_of_it():
    for html in (_outline(layout=None), build_timeline(*load_brief(json.loads(LANES.read_text(encoding="utf-8"))))[0]):
        assert 'id="alto-study-sheet' not in html and "window._altoStudySheet = function" not in html   # the wrapper alone is inert
    assert "alto-study-sheet-js" in _outline()


def test_the_dialog_labels_are_the_spec_table_on_both_copies_of_the_homepage():
    for f in (HOME, ROOT / "engine" / "home_template.html"):
        h = f.read_text(encoding="utf-8")
        for fmt, text in study_sheet.DIALOG_LABELS.items():
            assert f"  {fmt}: '{text}'" in h
    assert study_sheet.DIALOG_LABELS["system"] == "Prints a one-page unit map, then the outline."
    assert study_sheet.PALACE_LABEL == ("Prints your route in order (with a small picture if one is saved), "
                                        "then the outline.")


# ── in a browser ───────────────────────────────────────────────────────────

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no Chromium: {e}")
        yield b
        b.close()


def _printed(browser, html, mode="timeline", pre=""):
    """Open the page, stage the print, return (page, pdf bytes)."""
    pg = browser.new_page(viewport={"width": 1400, "height": 900})
    pg.add_init_script("window.print=function(){window.__printed=(window.__printed||0)+1;};")
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route("http://alto.test/**", lambda r: r.fulfill(body=html, content_type="text/html")
             if r.request.url.split("?")[0].endswith("/index.html") else r.fulfill(status=404, body=""))
    pg.goto("http://alto.test/index.html")
    pg.wait_for_function("document.querySelectorAll('#world .node').length > 0", timeout=15000)
    pg.wait_for_timeout(600)
    if pre:
        pg.evaluate(pre)
    pg.evaluate(f"window.altoPrint('{mode}')")
    pg.wait_for_function("window.__printed > 0", timeout=15000)
    pg.emulate_media(media="print")
    pdf = pg.pdf(format="Letter", prefer_css_page_size=True)
    assert errors == []
    return pg, pdf


def _pages(pdf):
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


SHEET = r"""() => { const host = document.getElementById('print-timeline-host'), s = host.querySelector('.ss-sheet');
  if(!s) return null;
  const px = [...s.querySelectorAll('*')].filter(e => e.childNodes.length && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
                .map(e => parseFloat(getComputedStyle(e).fontSize));
  const cols = [...s.querySelectorAll('*')].map(e => getComputedStyle(e).color);
  const fills = [...s.querySelectorAll('*')].map(e => getComputedStyle(e).backgroundColor);
  return {first: host.firstElementChild === s, count: host.querySelectorAll('.ss-sheet').length,
          fits: [...s.querySelectorAll('.ss-body, .ss-list, .ss-route')].every(e => e.scrollHeight <= e.clientHeight + 1)
                && s.scrollHeight <= s.clientHeight + 1,
          minPx: Math.min(...px), colors: [...new Set(cols)], fills: [...new Set(fills)],
          of: +s.querySelector('.ss-pages').textContent, sub: s.querySelector('.ss-sub:last-of-type').textContent,
          head: s.querySelector('.ss-title').textContent, foot: s.querySelector('.ss-foot').textContent,
          units: [...s.querySelectorAll('.ss-unit-h')].map(e => e.textContent),
          items: [...s.querySelectorAll('.ss-list li:not(.ss-more)')].map(e => [e.querySelector('.ss-num').textContent, e.querySelector('.ss-t').textContent]),
          more: [...s.querySelectorAll('.ss-more')].map(e => e.textContent),
          cols: (s.querySelector('.ss-grid') ? s.querySelector('.ss-grid').style.gridTemplateColumns : '0').replace(/^repeat\((\d+),.*$/, '$1'),
          lines: s.querySelectorAll('.ss-links line').length,
          rows: [...s.querySelectorAll('tbody tr')].map(t => [...t.children].map(c => c.textContent)),
          tables: s.querySelectorAll('.ss-tbl').length, heads: [...s.querySelectorAll('.ss-tbl th')].map(e => e.textContent)}; }"""


def _grey(c):
    m = re.match(r"rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)", c)
    if not m:
        return False
    r, g, b = int(m[1]), int(m[2]), int(m[3])
    a = float(m[4]) if m[4] else 1
    return a == 0 or (r == g == b and (r >= 224 or r == 0 or c.startswith("rgb(255")))


def _check_sheet(s, pdf):
    assert s and s["first"] and s["count"] == 1 and s["fits"]
    assert s["minPx"] >= 8 * 96 / 72 - 0.01                     # nothing under 8 pt
    assert all(_grey(c) for c in s["colors"] + s["fills"]), (s["colors"], s["fills"])    # black, white, 12% grey only
    assert s["of"] == _pages(pdf) and s["foot"] == f"Page 1 of {s['of']}: the outline follows."
    assert "Study sheet" in s["sub"]


@pytest.mark.parametrize("units,cols,lines", [(5, 2, 6), (6, 2, 7), (1, 1, 1), (9, 3, 0)])
def test_a_system_prints_its_unit_map_on_one_page_first(browser, units, cols, lines):
    pg, pdf = _printed(browser, _outline(units))
    s = pg.evaluate(SHEET)
    _check_sheet(s, pdf)
    assert s["sub"] == "System · Study sheet" and s["head"] == "Contracts"
    assert int(s["cols"]) == cols and s["lines"] == lines and len(s["units"]) == units
    assert s["units"][0] == "Unit 1: Formation"
    label = pg.evaluate("window._ALTO_OUTLINE.label")
    title = {n["id"]: n["title"] for n in pg.evaluate("NODES")}
    by_num = {v: k for k, v in label.items()}
    for num, t in s["items"]:                                   # the outline's own numbers and titles
        assert title[by_num[num]] == t
    pg.close()


def test_a_unit_too_long_for_its_box_shrinks_to_8pt_then_says_how_many_more(browser):
    pg, pdf = _printed(browser, _outline(9, fat=40))
    s = pg.evaluate(SHEET)
    _check_sheet(s, pdf)
    assert pg.evaluate("document.querySelector('.ss-sheet').style.getPropertyValue('--ss-fs')") == "8pt"
    assert s["more"] and re.fullmatch(r"\+ \d+ more: see outline", s["more"][0])
    pg.close()


def test_outline_and_all_detail_pages_also_start_with_it_and_count_every_page(browser):
    pg, pdf = _printed(browser, _outline(1), mode="full")
    _check_sheet(pg.evaluate(SHEET), pdf)
    pg.close()


def test_an_outline_prints_as_it_did(browser):
    pg, _ = _printed(browser, _outline(layout=None))
    assert pg.evaluate(SHEET) is None
    pg.close()


def test_the_ink_saver_picture_has_no_sheet(browser):
    pg = browser.new_page(viewport={"width": 1400, "height": 900})
    pg.set_content(_outline(1)); pg.wait_for_timeout(1200)
    assert pg.evaluate("window._altoInkStage()") is True
    assert pg.evaluate("document.querySelectorAll('.ss-sheet').length") == 0
    pg.close()


def test_a_city_palace_prints_its_route_in_two_columns_past_14_stops(browser):
    pg, pdf = _printed(browser, _city(18))
    s = pg.evaluate(SHEET)
    _check_sheet(s, pdf)
    assert s["sub"] == "Mind Palace · Study sheet" and s["tables"] == 2
    assert s["heads"][:3] == ["Stop", "Card", "Street"]
    num = pg.evaluate("NODE_ORDER_MAP")
    title = {n["id"]: n["title"] for n in pg.evaluate("NODES")}
    by_num = {v: k for k, v in num.items()}
    assert [r[0] for r in s["rows"]] == sorted((r[0] for r in s["rows"]), key=lambda x: [int(p) for p in re.split(r"[.-]", x)])
    for n_, t, place in s["rows"]:
        assert title[by_num[n_]] == t and place                  # every Gridville building has a corner
    pg.close()
    pg, pdf = _printed(browser, _city(9))
    assert pg.evaluate(SHEET)["tables"] == 1
    pg.close()


def test_a_stop_with_no_place_shows_an_em_dash(browser):
    pg, _ = _printed(browser, _city(9), pre="Object.keys(window._ALTO_PALACE.near).forEach(k => delete window._ALTO_PALACE.near[k])")
    assert {r[2] for r in pg.evaluate(SHEET)["rows"]} == {"—"}
    pg.close()


def test_a_world_palace_prints_country_then_city(browser):
    pg, pdf = _printed(browser, _world())
    s = pg.evaluate(SHEET)
    _check_sheet(s, pdf)
    assert s["sub"] == "World map · Study sheet" and s["heads"][2] == "Country"
    W = pg.evaluate("window._ALTO_WORLD")
    assert {r[0] for r in s["rows"]} == {v["n"] for v in W["nodes"].values()}
    assert all(r[2] for r in s["rows"])
    assert any(", " in r[2] for r in s["rows"])                 # a stop on a city: "Country, City"
    pg.close()


def test_a_building_palace_prints_rooms_floors_and_the_building_name(browser):
    from alto.build import building_schema as bs, palace_assets
    html = _building()
    pname, ptext = bs.hosted_json(bs.fixture())
    pg = browser.new_page(viewport={"width": 1400, "height": 900})
    pg.add_init_script("window.print=function(){window.__printed=(window.__printed||0)+1;};")

    def route(r):
        path = r.request.url.split("alto.test", 1)[-1].split("?")[0]
        if path == "/index.html":
            return r.fulfill(body=html, content_type="text/html")
        hit = palace_assets.find(path, building_plans={pname: ptext}) if path.startswith("/bldg/") else None
        return r.fulfill(status=200, content_type=hit[0], body=hit[1]) if hit else r.fulfill(status=404, body="")
    pg.route("http://alto.test/**", route)
    pg.goto("http://alto.test/index.html")
    pg.wait_for_function("window.AltoBuilding && window.AltoBuilding.plan", timeout=15000)
    pg.evaluate("window.altoPrint('timeline')")
    pg.wait_for_function("window.__printed > 0")
    pg.emulate_media(media="print")
    pdf = pg.pdf(format="Letter", prefer_css_page_size=True)
    s = pg.evaluate(SHEET)
    _check_sheet(s, pdf)
    assert s["heads"][2] == "Room" and s["sub"] == "Memory palace · Study sheet"
    assert pg.evaluate("document.querySelector('.ss-sub').textContent") == pg.evaluate("window._ALTO_BUILDING.name")
    assert all(re.search(r", \w.* floor$", r[2]) for r in s["rows"]), s["rows"]
    assert not any("101 Gallery 101" in r[2] for r in s["rows"])
    pg.close()


@pytest.mark.parametrize("fmt,text", [("system", study_sheet.DIALOG_LABELS["system"]),
                                      ("palace", study_sheet.PALACE_LABEL), ("world", study_sheet.PALACE_LABEL),
                                      ("building", study_sheet.PALACE_LABEL), ("outline", None), ("timeline", None),
                                      ("lanes", None)])
@pytest.mark.parametrize("width", [1280, 390])
def test_the_print_dialog_says_what_page_one_is(browser, fmt, text, width):
    from alto.build.pages import build_home
    from alto.hosted import hosted_home
    pg = browser.new_page(viewport={"width": width, "height": 800})
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.set_content(hosted_home(build_home([])))
    pg.evaluate(f"altoPrintMenu({{heading:'Contracts', fmt:'{fmt}', key:'k'}})")
    lab = pg.locator(".share-menu .sm-fmt")
    if text is None:
        assert lab.count() == 0
    else:
        assert lab.inner_text() == text
        box, menu = lab.bounding_box(), pg.locator(".share-menu").bounding_box()
        assert box["x"] >= menu["x"] + 16 - 0.5 and box["x"] + box["width"] <= menu["x"] + menu["width"] - 16 + 0.5
        assert pg.evaluate("(() => { const e = document.querySelector('.share-menu .sm-fmt'); "
                           "return e.scrollWidth <= e.clientWidth + 1 && parseFloat(getComputedStyle(e).fontSize); })()") == 13
    pg.close()
