"""Mind Palace transit: the real lines read from route relations (palace_map._transit), snapped onto the palace's
grid (palace_grid / palace_transit), drawn and used on the page (palace_transit_js): stops, riding a line, an Element
chip's tour. Offline; the browser tests are skipped without Playwright's browsers."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto import palace_map as pm  # noqa: E402
from alto.build import palace  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.palace_transit import snap  # noqa: E402
import test_palace as tp  # noqa: E402
from test_palace_map import BB, way  # noqa: E402


# ── the data: route relations -> lines and stops ───────────────────
def _septa_raw():
    ways = [way(10, [(39.003, -74.999), (39.003, -74.995)], railway="subway"),
            way(11, [(39.003, -74.995), (39.003, -74.991)], railway="subway"),
            way(12, [(39.007, -74.999), (39.007, -74.991)], railway="rail", service="yard")]
    rels = [{"type": "relation", "id": 100, "tags": {"type": "route", "route": "subway", "ref": "L", "network": "SEPTA",
                                                       "name": "SEPTA Market-Frankford Line: A → B", "colour": "#0097d6"},
             "members": [{"type": "way", "ref": 10, "role": ""}, {"type": "way", "ref": 11, "role": ""},
                         {"type": "node", "ref": 1, "role": "stop"}, {"type": "node", "ref": 2, "role": "stop_exit_only"}]},
            {"type": "relation", "id": 101, "tags": {"type": "route", "route": "subway", "ref": "L", "network": "SEPTA",
                                                       "name": "SEPTA Market-Frankford Line (diverted): A → B"},
             "members": [{"type": "way", "ref": 12, "role": ""}]},
            {"type": "relation", "id": 102, "tags": {"type": "route", "route": "train", "ref": "ACELA", "network": "Amtrak"},
             "members": [{"type": "way", "ref": 12, "role": ""}]}]
    nodes = [{"type": "node", "id": 1, "lat": 39.003, "lon": -74.997, "tags": {"name": "Elm Street"}},
             {"type": "node", "id": 2, "lat": 39.003, "lon": -74.993, "tags": {"name": "Oak Street"}}]
    return {"elements": ways + rels + nodes}


def test_a_septa_line_is_read_from_its_route_relation():
    m = pm.build_map(_septa_raw(), BB)
    t = m["transit"]
    assert [l["id"] for l in t["lines"]] == ["mfl"]               # Amtrak and the diversion are left out
    (l,) = t["lines"]
    assert l["n"].startswith("Market") and l["c"] == "#0097d6" and l["k"] == "metro"
    assert len(l["w"]) == 2                                       # one polyline per rail way
    assert [t["stops"][i]["n"] for i in l["s"]] == ["Elm Street", "Oak Street"]


def test_a_city_without_transit_has_none():
    assert pm.build_map({"elements": []}, BB)["transit"] == {"lines": [], "stops": []}


# ── snapping to the grid ───────────────────────────────────────────
class _Id:                                   # real px == grid px
    def __call__(self, x, y):
        return (x, y)


XG, YG = [100, 340, 580, 820], [100, 270, 440]


def _tr(ways_a, ways_b=None):
    lines = [{"id": "a", "n": "A", "c": "#0097d6", "k": "metro", "w": ways_a, "s": [0, 1]}]
    if ways_b:
        lines.append({"id": "b", "n": "B", "c": "#6ea516", "k": "tram", "w": ways_b, "s": [0]})
    return {"lines": lines, "stops": [{"n": "S1", "x": 170, "y": 280, "l": ["a", "b"] if ways_b else ["a"]},
                                      {"n": "S2", "x": 600, "y": 260, "l": ["a"]},
                                      {"n": "Far", "x": 5000, "y": 5000, "l": ["a"]}]}


def test_a_line_is_snapped_onto_grid_lines_and_stops_stand_on_it():
    g = snap(_tr([[110, 262, 360, 280, 570, 275]]), _Id(), XG, YG, 920, 540)
    (l,) = g["lines"]
    (p,) = l["p"]
    assert sorted([(p[0], p[1]), (p[2], p[3])]) == [(100, 270), (580, 270)] and len(p) == 4                              # one straight run on the row at y=270
    assert [s["n"] for s in g["stops"]] == ["S1", "S2"]           # the stop nowhere near is dropped
    assert all(s["y"] == 270 for s in g["stops"])
    assert l["s"] == [0, 1]


def test_a_turn_is_square_and_lines_sharing_a_street_run_in_lanes():
    g = snap(_tr([[100, 270, 340, 270, 340, 440]], [[100, 270, 580, 270]]), _Id(), XG, YG, 920, 540)
    a, b = g["lines"]
    pa = a["p"][0]
    assert pa[0] != pa[2] or pa[1] != pa[3]
    assert all(pa[i] == pa[i + 2] or pa[i + 1] == pa[i + 3] for i in range(0, len(pa) - 2, 2))   # only straight legs
    ya = {a["p"][0][1]}
    yb = {b["p"][0][1]}
    assert ya != yb and abs(list(ya)[0] - list(yb)[0]) >= 6      # side by side, not on top of each other


# ── the page ───────────────────────────────────────────────────────
def _bundle():
    d = tp.bundle()
    b = d["brief"]
    data = palace.unpack(b["palace"]["data_z"])
    m = data["map"]
    m["transit"] = {"lines": [{"id": "mfl", "n": "Market–Frankford Line", "c": "#0097d6", "k": "metro",
                                "p": [[0, 500, 900, 500]], "s": [0, 1, 2]},
                               {"id": "bsl", "n": "Broad Street Line", "c": "#f58220", "k": "metro",
                                "p": [[350, 0, 350, 600]], "s": [3, 1]}],
                    "stops": [{"n": "West", "x": 150, "y": 500, "l": ["mfl"]},
                              {"n": "City Hall", "x": 350, "y": 500, "l": ["mfl", "bsl"]},
                              {"n": "East", "x": 750, "y": 500, "l": ["mfl"]},
                              {"n": "North", "x": 350, "y": 100, "l": ["bsl"]}]}
    b["palace"]["data_z"] = palace.pack(data)
    return d


@pytest.fixture(scope="module")
def html():
    out, _ = build_timeline(*load_brief(copy.deepcopy(_bundle())))
    return out


def test_transit_pieces_are_in_the_page(html):
    for s in ("window._palTr", "pl-tl-hit", "pal-chiprt", "alto-filter-changed", "Ride this line", "Interchange"):
        assert s in html, s
    assert "window._palTr.holds()" in palace.PALACE_JS           # the chip tour beats the hover routes


pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.fixture()
def page(browser, tmp_path, html):
    f = tmp_path / "p.html"
    f.write_text(html, encoding="utf-8")
    pg = browser.new_context(viewport={"width": 1500, "height": 900}).new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1800)
    yield pg
    assert pg.errs == []


def test_lines_and_stops_are_drawn_and_an_interchange_is_ringed(page):
    n = page.evaluate("() => [document.querySelectorAll('.pl-tl').length, document.querySelectorAll('.tr-stn').length, "
                      "document.querySelectorAll('.tr-stn.hub').length, document.querySelectorAll('.pl-tl-hit').length]")
    assert n == [2, 4, 1, 2]


def test_a_stop_click_lists_its_lines_and_riding_steps_with_the_arrow_keys(page):
    page.evaluate("() => window._palTr.pickStop(1, false)")
    txt = page.evaluate("() => document.getElementById('pal-tr').textContent")
    assert "City Hall" in txt and "Market" in txt and "Broad Street Line" in txt
    page.evaluate("() => window._palTr.ride('mfl', 0)")
    assert page.evaluate("() => window._palTr.state().ride.i") == 0
    page.keyboard.press("ArrowRight")
    assert page.evaluate("() => window._palTr.state().ride.i") == 1
    assert "City Hall" in page.evaluate("() => document.getElementById('pal-tr').textContent")
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("() => window._palTr.state().ride.i") == 0
    page.keyboard.press("Escape")
    assert page.evaluate("() => window._palTr.state().ride") is None
    assert not page.evaluate("() => document.getElementById('pal-tr').classList.contains('on')")


def test_the_key_lists_the_lines_and_what_a_dot_means(page):
    page.evaluate("() => document.getElementById('key-toggle').click()")
    k = page.evaluate("() => document.getElementById('pal-key').textContent")
    assert "Broad Street Line" in k and "Interchange" in k and "Stop" in k
    assert page.evaluate("() => document.querySelectorAll('#pal-key .pk-row[data-tl]').length") == 2


def test_the_route_prefers_transit_over_a_long_walk(page):
    # from a street node near the west stop to one near the east stop: the line, not the street, is the cheap way
    r = page.evaluate("""() => { const T = window._palTr, a = T.nodeNear(150, 500), b = T.nodeNear(750, 500);
      const p = T.route(a, b); return p ? T.ridden(p) : null; }""")
    assert r and "mfl" in r


def _chip(page, ids):
    page.evaluate("""ids => { window.FILTER_NODES = {entity: {tagged: ids}};
      window.FILTER_SECTIONS = [{key: 'entity', kind: 'chips', items: [{id: 'tagged', name: 'Tagged', color: '#e8a87c'}]}];
      const b = document.createElement('button'); b.className = 'nav-btn'; b.id = 'fake-chip'; b.textContent = 'Tagged';
      b.setAttribute('onclick', "showDetail('char','tagged')"); document.getElementById('nav').appendChild(b); }""", ids)


def test_hovering_an_element_chip_lights_what_it_tags_and_draws_one_route(page):
    _chip(page, ["alpha", "gamma", "delta"])
    page.hover("#fake-chip")
    page.wait_for_timeout(400)
    s = page.evaluate("""() => ({hot: [...document.querySelectorAll('#world .node.pal-chip-hot')].map(n => n.id),
        dim: document.querySelectorAll('#world .node.pal-dim:not(.pal-floor)').length,
        routes: document.querySelectorAll('#palace-svg .pl-crt.base').length,
        pill: document.getElementById('pal-chiprt').textContent})""")
    assert set(s["hot"]) >= {"node-alpha", "node-gamma", "node-delta"} and s["routes"] == 1 and s["dim"] >= 1
    assert "3 buildings" in s["pill"]
    page.mouse.move(700, 600)
    page.wait_for_timeout(300)
    assert page.evaluate("() => document.querySelectorAll('#palace-svg .pl-crt.base').length") == 0
    assert page.evaluate("() => document.querySelectorAll('#world .node.pal-chip-hot').length") == 0


def test_a_filter_keeps_the_tour_up_and_beats_the_hover_routes(page):
    _chip(page, ["alpha", "gamma"])
    page.evaluate("""() => { window._altoChipOn = () => true; window._altoChipSel = () => ({entity: ['tagged']});
      window._altoChipKeep = id => ['alpha', 'gamma'].indexOf(id) >= 0; document.dispatchEvent(new CustomEvent('alto-filter-changed')); }""")
    page.wait_for_timeout(300)
    assert page.evaluate("() => document.querySelectorAll('#palace-svg .pl-crt.base').length") == 1
    # a building-hover route is refused while the tour is up
    page.evaluate("() => { const s = document.getElementById('palace-svg'); s._r.innerHTML = ''; }")
    assert page.evaluate("() => window._palTr.holds()") is True
    page.evaluate("""() => { window._altoChipOn = () => false; window._altoChipSel = () => ({}); window._altoChipKeep = () => true;
      document.dispatchEvent(new CustomEvent('alto-filter-changed')); }""")
    page.wait_for_timeout(200)
    assert page.evaluate("() => document.querySelectorAll('#palace-svg .pl-crt.base').length") == 0
    assert page.evaluate("() => window._palTr.holds()") is False
