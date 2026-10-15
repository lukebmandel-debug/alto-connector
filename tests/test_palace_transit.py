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
        lines.append({"id": "b", "n": "B", "c": "#6ea516", "k": "metro", "w": ways_b, "s": [0]})
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


def _off(polys, x, y):
    """Distance from (x, y) to the nearest drawn run of a line."""
    best = 1e18
    for f in polys:
        for k in range(0, len(f) - 3, 2):
            ax, ay, bx, by = f[k:k + 4]
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / ((dx * dx + dy * dy) or 1e-9)))
            best = min(best, ((ax + t * dx - x) ** 2 + (ay + t * dy - y) ** 2) ** .5)
    return best


def test_a_stop_where_two_lines_part_company_gets_a_dot_on_each_track():
    tr = _tr([[100, 270, 580, 270]], [[100, 440, 580, 440]])
    tr["stops"][0].update(x=170, y=355)                           # halfway between the two rows
    tr["lines"][1]["s"] = [0]
    g = snap(tr, _Id(), XG, YG, 920, 540)
    s1 = [s for s in g["stops"] if s["n"] == "S1"]
    assert len(s1) == 2 and sorted(l for s in s1 for l in s["l"]) == ["a", "b"]    # not one dot floating between the tracks
    for s in s1:
        (lid,) = s["l"]
        (ln,) = [l for l in g["lines"] if l["id"] == lid]
        assert _off(ln["p"], s["x"], s["y"]) < 1


def test_a_stop_whose_track_is_not_there_is_not_drawn_and_a_line_lists_only_stops_it_reaches():
    g = snap(_tr([[110, 262, 360, 280, 570, 275]]), _Id(), XG, YG, 920, 540)
    assert "Far" not in [s["n"] for s in g["stops"]]
    (l,) = g["lines"]
    assert [g["stops"][i]["n"] for i in l["s"]] == ["S1", "S2"]
    assert g["ge"] and all(len(e) == 4 for e in g["ge"])           # the grid edges it runs along (palace_grid gives them streets)


def test_no_stop_floats_off_its_lines_in_the_civ_pro_bundle():
    """Every dot on the real Civ Pro Mind Palace stands on each line it names (to within the lane gap), every line lists
    only stops that list it back, (a trolley's street is checked by test_the_civ_pro_bundles_trolleys_run_on_streets)."""
    import json
    import os
    path = Path(os.environ.get("ALTO_CIVPRO_PALACE", "/private/tmp/claude-501/-Users-lukemandel-Desktop-Terrarium-Alto/"
                                "d7a9f909-c367-4dd8-a20f-98d2861a343b/scratchpad/kit/civ_palace_p8.json"))
    if not path.exists():
        pytest.skip("the Civ Pro bundle is not on this machine")
    m = palace.unpack(json.loads(path.read_text())["brief"]["palace"]["data_z"])["map"]
    tr = m["transit"]
    lines = {l["id"]: l for l in tr["lines"]}
    assert tr["stops"] and lines
    for i, s in enumerate(tr["stops"]):
        assert s["l"] and all(l in lines for l in s["l"]), s["n"]          # a dot only where a line is drawn
        for lid in s["l"]:
            assert i in lines[lid]["s"], (s["n"], lid)
            assert _off(lines[lid]["p"], s["x"], s["y"]) <= 7.5, (s["n"], lid)       # on it (an interchange sits between lanes)
    for l in tr["lines"]:
        assert all(l["id"] in tr["stops"][k]["l"] for k in l["s"])


def test_a_line_runs_only_between_its_stops_and_a_branch_never_joins_a_neighbours():
    """Track left dangling past a line's last stop is cut back to it, and the stops of one branch are joined only to
    each other (never to a stop of another branch by the shortest way through the grid)."""
    xg, yg = [100, 340, 580, 820, 1060], [100, 270, 440]
    way_a = [100, 270, 1060, 270]                                 # a street the line runs along: 4 blocks
    way_b = [340, 270, 340, 440, 820, 440, 820, 270]              # a loop of track beside it (a yard)
    tr = {"lines": [{"id": "a", "n": "A", "c": "#0097d6", "k": "metro", "w": [way_a, way_b], "s": [0, 1, 2, 3],
                     "b": [[0, 1], [2, 3]]}],
          "stops": [{"n": "S%d" % i, "x": x, "y": 270, "l": ["a"]} for i, x in enumerate((100, 340, 820, 1060))]}
    g = snap(tr, _Id(), xg, yg, 1160, 540)
    (l,) = g["lines"]
    assert l["b"] == [[0, 1], [2, 3]] and l["s"] == [0, 1, 2, 3]
    # the loop below the street is not a branch's shortest way: no stub or yard remains under row 440
    assert all(max(f[1::2]) <= 270 + 1 for f in l["p"])


def test_the_audit_names_a_floating_stop_a_stub_and_a_river_crossing():
    from alto.build.palace_transit_audit import audit
    tr = {"lines": [{"id": "trl", "n": "Trolleys", "c": "#6ea516", "k": "tram", "p": [[0, 0, 2000, 0, 2000, 3000]], "s": [0, 1, 2]}],
          "stops": [{"n": "On", "x": 500, "y": 0, "l": ["trl"]}, {"n": "Floating", "x": 1000, "y": 40, "l": ["trl"]},
                    {"n": "Last", "x": 2000, "y": 500, "l": ["trl"]}, {"n": "Orphan", "x": 5, "y": 5, "l": []}]}
    river = [{"n": "Schuylkill River", "w": 100, "p": [1500, -100, 1500, 100]},
             {"n": "Delaware River", "w": 100, "p": [1500, -100, 1500, 100]}]
    bad = " | ".join(audit({"transit": tr, "river": river})["problems"])
    assert "'Floating' is 40.0 px from the line's track" in bad
    assert "track past the last stop" in bad                       # 2500 px of track beyond 'Last'
    assert "lists no line" in bad                                  # a dot no line passes
    assert "Delaware 1 time(s)" in bad and "Schuylkill" not in bad  # a trolley may tunnel the Schuylkill, not cross the Delaware


def test_the_civ_pro_bundles_transit_passes_the_audit():
    """Every line of the real Civ Pro Mind Palace: its stops stand on its track and list it back, no piece of track is left
    without a stop, no stub runs past a last stop, no line crosses a river without a tunnel or bridge, consecutive stops are
    joined by track, and each line runs its real route's stops in order (palace_transit_audit)."""
    import json
    import os
    from alto.build.palace_transit_audit import audit
    path = Path(os.environ.get("ALTO_CIVPRO_PALACE_P6", "/private/tmp/claude-501/-Users-lukemandel-Desktop-Terrarium-Alto/"
                                "d7a9f909-c367-4dd8-a20f-98d2861a343b/scratchpad/kit/civ_palace_p8.json"))
    if not path.exists():
        pytest.skip("the Civ Pro bundle is not on this machine")
    m = palace.unpack(json.loads(path.read_text())["brief"]["palace"]["data_z"])["map"]
    r = audit(m)
    assert {"mfl", "bsl", "brs", "trl", "rr", "pat"} <= set(r["lines"])
    assert not r["problems"], "\n".join(r["problems"])


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


# ── a trolley runs ON a street ─────────────────────────────────────
def _street_grid():
    """Every unit edge of XG x YG, as the page draws them (tiles' sides and loose edges)."""
    es = [[XG[i], y, XG[i + 1], y] for y in YG for i in range(len(XG) - 1)]
    return es + [[x, YG[j], x, YG[j + 1]] for x in XG for j in range(len(YG) - 1)]


def _trolley(stops, ways):
    return {"lines": [{"id": "trl", "n": "Trolleys", "c": "#6ea516", "k": "tram", "w": ways, "s": list(range(len(stops))),
                       "b": [list(range(len(stops)))]}],
            "stops": [{"n": "%s & X" % n, "x": x, "y": y, "l": ["trl"]} for n, x, y in stops]}


def test_a_trolley_is_routed_along_drawn_streets_and_a_stop_with_no_street_is_dropped():
    es = _street_grid()
    tr = _trolley([("A", 110, 262), ("B", 570, 275), ("C", 600, 440), ("Void", 5000, 5000)],
                  [[110, 262, 360, 280, 570, 275, 600, 440]])
    g = snap(tr, _Id(), XG, YG, 920, 540, streets=[], edges_=es)
    (l,) = g["lines"]
    assert [g["stops"][i]["n"] for i in l["s"]] == ["A & X", "B & X", "C & X"]          # nothing for the stop in the void
    assert g["ge"] == []                                                                  # a trolley never makes a street
    from alto.build.palace_transit_audit import street_cover
    c = street_cover({"tiles": [], "edges": es, "streets": [], "transit": g})["trl"]
    assert c["runs"] == [] and c["stops"] == []                                           # a street under every stretch and every stop


def test_a_trolley_follows_a_diagonal_avenue_as_one_line_not_stairs():
    es = _street_grid()
    diag = {"n": "Diag", "k": 0, "d": 1, "j": [0, 0], "p": [100, 100, 580, 440]}           # from (100,100) to (580,440)
    stops = [("A", 100, 100), ("B", 340, 270), ("C", 580, 440)]
    tr = _trolley(stops, [[100, 100, 340, 270, 580, 440]])
    g = snap(tr, _Id(), XG, YG, 920, 540, streets=[diag], edges_=es)
    (l,) = g["lines"]
    (p,) = l["p"]
    assert p == [100.0, 100.0, 580.0, 440.0] or p == [580.0, 440.0, 100.0, 100.0]          # one straight diagonal


def test_the_audit_flags_a_trolley_stop_in_blank_space_and_track_over_a_void():
    from alto.build.palace_transit_audit import audit, street_cover
    m = {"tiles": [], "edges": [[0, 0, 1000, 0]], "streets": [],
         "transit": {"lines": [{"id": "trl", "n": "Trolleys", "c": "#6ea516", "k": "tram", "s": [0, 1],
                                "p": [[0, 0, 1000, 0], [1000, 0, 1000, 600]]}],
                     "stops": [{"n": "On Street", "x": 300, "y": 0, "l": ["trl"]},
                               {"n": "Floating", "x": 1000, "y": 300, "l": ["trl"]}]}}
    c = street_cover(m)["trl"]
    assert [s[0] for s in c["stops"]] == ["Floating"]                                     # the dot with no street under it
    assert len(c["runs"]) == 1 and c["runs"][0][0] >= 560                                  # the 600 px of track over nothing
    assert any("has no street under it" in p for p in audit(m)["problems"])


def test_the_civ_pro_bundles_trolleys_run_on_streets():
    """The real Civ Pro Mind Palace: every stretch of trolley track (sampled every 20 px) and every trolley stop has a drawn
    street under it, none of it runs on a street the grid drew only for the line, and the grid is not grown for it."""
    import json
    import os
    from alto.build.palace_transit_audit import street_cover
    path = Path(os.environ.get("ALTO_CIVPRO_PALACE_P8", "/private/tmp/claude-501/-Users-lukemandel-Desktop-Terrarium-Alto/"
                                "d7a9f909-c367-4dd8-a20f-98d2861a343b/scratchpad/kit/civ_palace_p8.json"))
    if not path.exists():
        pytest.skip("the Civ Pro bundle is not on this machine")
    m = palace.unpack(json.loads(path.read_text())["brief"]["palace"]["data_z"])["map"]
    c = street_cover(m)
    assert c, "no surface line in the bundle"
    for lid, r in c.items():
        assert r["track"] > 0
        assert not r["runs"], (lid, r["runs"])                                             # track over a void
        assert not r["stops"], (lid, r["stops"])                                           # a floating stop
        assert r["invented"] <= 60, (lid, r["invented"])                                   # a street drawn for the trolley
    assert len(m["cols"]) <= 70 and len(m["rows"]) <= 65                                    # the grid did not sprawl for it
