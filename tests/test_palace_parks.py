"""Mind Palace parks (palace_parks): green glass snapped to the grid with geometric paths, under the streets.
Offline, on the synthetic city of test_palace; the browser test is skipped without Playwright's browsers."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_parks as pk  # noqa: E402
from alto.build.builder import build_timeline  # noqa: E402
from alto.build.palace_grid import grid  # noqa: E402
import test_palace as tp  # noqa: E402

MAJORS = ["John F. Kennedy Boulevard", "Market Street", "South 16th Street"]


def _city(with_park=True):
    m = tp.city_map()
    if with_park:       # a square between 15th and 16th Street, Walnut and Kennedy
        m["parks"] = m["parks"] + [{"n": "Test Square", "r": [[140, 90, 360, 90, 360, 310, 140, 310]]},
                                   {"n": "Tiny Plot", "r": [[600, 400, 610, 400, 610, 410, 600, 410]]}]
    return m


def _grid(parks=("Test Square",), **kw):
    return grid(_city(), majors=MAJORS, parks=parks, **kw)


def test_a_named_park_becomes_a_block_snapped_green_shape_with_paths():
    g = _grid()
    raw = g["parks"]
    assert [p["n"] for p in raw] == ["Test Square"]                 # the small unnamed ones are not major
    xg, yg = g["grid"]["xg"], g["grid"]["yg"]
    out = pk.shape(raw, xg, yg)
    assert len(out) == 1 and out[0]["n"] == "Test Square"
    s = out[0]
    ring = s["r"][0]
    pts = list(zip(ring[0::2], ring[1::2]))
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(pts, pts[1:] + pts[:1]))     # rectilinear: the grid's own lines
    assert min(p[0] for p in pts) >= min(xg) and max(p[0] for p in pts) <= max(xg)
    assert s["p"] and s["o"]                                       # walkways and a plaza
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    for path in s["p"]:                                            # every walkway stays inside the green
        for x, y in zip(path[0::2], path[1::2]):
            assert x0 <= x <= x1 and y0 <= y <= y1
    assert s["k"] in ("x", "+", "*", "+o", "mall", "trail")


def test_big_unnamed_parks_are_major_by_area_but_cemeteries_are_not():
    m = _city(False)
    m["parks"] = [{"n": "Great Park", "r": [[140, 90, 360, 90, 360, 310, 140, 310]]},
                  {"n": "Old Cemetery", "r": [[400, 90, 600, 90, 600, 310, 400, 310]]}]
    g = grid(m, majors=MAJORS)
    assert [p["n"] for p in g["parks"]] == []                       # 220 x 220 m is 5 ha: under the threshold
    m["parks"][0]["r"] = [[0, 0, 900, 0, 900, 300, 0, 300]]         # 27 ha
    m["parks"][1]["r"] = [[0, 300, 900, 300, 900, 600, 0, 600]]
    g = grid(m, majors=MAJORS)
    assert [p["n"] for p in g["parks"]] == ["Great Park"]


def test_a_park_never_moves_a_building_or_a_lot():
    a, b = _grid(), grid(_city(False), majors=MAJORS)
    assert a["blocks"] == b["blocks"]                               # the lots are the same with and without it
    assert [t for t in a["tiles"]] == [t for t in b["tiles"]]


def test_a_block_with_a_building_on_it_is_cut_out_of_the_park():
    g = _grid()
    xg, yg = g["grid"]["xg"], g["grid"]["yg"]
    full = pk.shape(g["parks"], xg, yg)
    assert full
    cells = pk._cells_of(g["parks"][0]["c"])
    i, j = sorted(cells)[0]
    lot = ((xg[i] + xg[i + 1]) / 2 + 10, (yg[j] + yg[j + 1]) / 2 + 10)        # a building's lot inside that block
    cut = pk.shape(g["parks"], xg, yg, [lot])
    n_full = sum(c["z"] for c in full)
    assert sum(c["z"] for c in cut) == n_full - 1                   # exactly that block is un-greened
    for s in cut:                                                   # and nothing green is drawn over its lot
        for ring in s["r"]:
            xs, ys = ring[0::2], ring[1::2]
            assert not (min(xs) < lot[0] < max(xs) and min(ys) < lot[1] < max(ys)) or len(s["r"]) > 1 or s["z"] > 1


def test_squares_get_their_characteristic_paths():
    xg, yg = [0, 240, 480], [0, 170, 340]
    for kind, diag in (("x", True), ("+", False), ("*", True)):
        cells = {(0, 0)}
        paths, plaza = pk._paths(kind, cells, xg, yg, lambda x, y: True)
        assert plaza and len(paths) >= (3 if kind != "+" else 3)
        has_diag = any(len(p) >= 4 and p[0] != p[2] and p[1] != p[3] for p in paths)
        assert has_diag == diag
    assert pk._kind("Rittenhouse Square", 1) == "x" and pk._kind("Franklin Square", 2) == "*"
    assert pk._kind("Fairmount Park", 40) == "trail" and pk._kind("Independence Mall", 3) == "mall"


def test_short_names():
    assert pk.short_name("West Fairmount Park") == "Fairmount Park"
    assert pk.short_name("Franklin Delano Roosevelt Park") == "FDR Park"


def _page():
    g = _grid()
    blocks = g.pop("blocks")
    d = tp.bundle()
    d["brief"]["palace"].update(data_z=palace.pack({"map": g, "blocks": blocks}), parks=["Test Square"])
    return build_timeline(*tp.load(d))[0]


def test_the_page_carries_the_parks_and_draws_them_in_a_delimited_block_under_the_streets():
    page = _page()
    data = json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", page, re.S).group(1))
    parks = data["m"]["parks"]
    assert [p["n"] for p in parks] == ["Test Square"] and parks[0]["r"] and parks[0]["p"]
    assert "── parks:" in page and "/* ── /parks ── */" in page
    assert page.index("pl-parks") < page.index("class':'pl-streets'") < page.index("class':'pl-lms'")
    assert page.index("class':'pl-washes'") < page.index("class':'pl-parks'")
    for needle in (".pl-pk{fill:var(--pal-pk)", "--pal-pk:", "html.dark{--pal-river"):
        assert needle in page


def test_in_a_browser_the_parks_lie_below_the_streets_and_above_the_ground(tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    f = tmp_path / "p.html"
    f.write_text(_page(), encoding="utf-8")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                                         # noqa: BLE001
            pytest.skip(f"no chromium: {e}")
        try:
            pg = b.new_context(viewport={"width": 1400, "height": 800}).new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(f.as_uri())
            pg.wait_for_timeout(1500)
            r = pg.evaluate("""()=>{ var kids=[...document.querySelector('#palace-svg').children].map(e=>e.getAttribute('class')||e.tagName);
              var pk=document.querySelector('#palace-svg .pl-pk'), g=pk?pk.parentNode.getAttribute('data-name'):null;
              var fill=pk?getComputedStyle(pk).fill:'', paths=document.querySelectorAll('#palace-svg .pl-pkp').length;
              return {kids:kids, g:g, fill:fill, paths:paths, label:[...document.querySelectorAll('#palace-svg .pl-pkt')].map(t=>t.textContent)}; }""")
            k = r["kids"]
            assert k.index("pl-washes") < k.index("pl-parks") < k.index("pl-streets") < k.index("pl-lms") < k.index("pl-blds"), k
            assert r["g"] == "Test Square" and r["paths"] >= 3 and r["label"] == ["Test Square"], r
            m = re.match(r"rgba?\((\d+), (\d+), (\d+)", r["fill"])
            assert m and int(m.group(2)) > int(m.group(1)) and int(m.group(2)) > int(m.group(3)), r["fill"]      # green
            assert not errs, errs
        finally:
            b.close()
