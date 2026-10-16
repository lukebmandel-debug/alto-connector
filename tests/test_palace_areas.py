"""Mind Palace neighbourhood names: label-only area names (brief.palace.areas) beside the section districts. Static checks of
the list, validation and layout; a real browser checks that the names are in the page, are click-through, and that no two
visible names overlap at the whole-city zoom. Nothing here touches the network, Firebase or any ALTO_* setting."""
import copy
import functools
import http.server
import inspect
import math
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto import mcp_server as srv  # noqa: E402
from alto.build import palace, palace_areas as pa, palace_place as pp  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.builder import build_timeline  # noqa: E402
from test_palace import bundle, check, city_map, load  # noqa: E402

PHILLY_BOX = [39.895, -75.245, 40.005, -75.085]
MAJOR = ["South Philadelphia", "North Philadelphia", "West Philadelphia", "Fishtown", "Kensington", "Northern Liberties",
         "Fairmount", "Society Hill", "Spring Garden", "Port Richmond", "Sports Complex", "Chinatown", "Queen Village",
         "Graduate Hospital", "Point Breeze", "East Passyunk", "Brewerytown", "Strawberry Mansion", "Temple",
         "Powelton Village", "Spruce Hill", "Wynnefield", "Penn's Landing", "Kingsessing"]
NAMED = ["Callowhill", "Francisville", "Poplar", "Midtown Village", "Bella Vista", "Passyunk Square", "Pennsport", "Cedar Park",
         "Walnut Hill", "Mill Creek", "Parkside", "Cobbs Creek", "Elmwood", "Garden Court", "Squirrel Hill", "Belmont"]


# ── the list and its checks ─────────────────────────────────────────────────
def test_philadelphias_default_list_names_every_major_neighbourhood_inside_the_box():
    got = {a["name"]: a for a in pa.default_areas("Philadelphia", PHILLY_BOX)}
    for n in MAJOR + NAMED:
        assert n in got, n
    assert len(got) == len(pa.default_areas("Philadelphia, PA", PHILLY_BOX))              # no name twice
    for a in got.values():
        assert PHILLY_BOX[0] <= a["lat"] <= PHILLY_BOX[2] and PHILLY_BOX[1] <= a["lon"] <= PHILLY_BOX[3], a
        assert a["rank"] in (1, 2, 3, 4)
    pa.check_areas(list(got.values()))
    assert {a["name"] for a in got.values() if a["rank"] == 1} >= {"South Philadelphia", "North Philadelphia", "West Philadelphia"}
    # a smaller box keeps only what is in it; another city has no built-in list
    assert all(PHILLY_BOX[0] <= a["lat"] <= 39.96 for a in pa.default_areas("Philadelphia", [39.895, -75.245, 39.96, -75.085]))
    assert pa.default_areas("Testville", PHILLY_BOX) == []


@pytest.mark.parametrize("bad", [
    "x", [{"lat": 1, "lon": 2}], [{"name": "A", "lat": "1", "lon": 2}], [{"name": "A", "lat": 1, "lon": 2, "rank": 9}],
    [{"name": "A", "lat": 99, "lon": 2}], [{"name": "A", "lat": 1, "lon": 2, "tint": "red"}], [{"name": "", "lat": 1, "lon": 2}]])
def test_bad_areas_are_refused(bad):
    with pytest.raises(BriefError):
        pa.check_areas(bad)
    d = bundle()
    d["brief"]["palace"]["areas"] = bad
    with pytest.raises(BriefError):
        check(d)


def test_areas_is_a_palace_key_and_a_set_up_parameter_and_the_guide_says_so():
    assert "areas" in palace.PALACE_KEYS
    assert "areas" in inspect.signature(palace.set_up).parameters
    assert "areas" in inspect.signature(srv.set_up_palace.fn if hasattr(srv.set_up_palace, "fn") else srv.set_up_palace).parameters
    assert "`areas`" in (ROOT / "alto" / "interview_guide.md").read_text(encoding="utf-8")
    d = bundle()
    d["brief"]["palace"]["areas"] = [{"name": "Nowhere", "lat": 39.95, "lon": -75.17, "rank": 2}]
    check(d)


def test_the_layout_puts_a_name_where_it_is_and_drops_the_district_names_duplicates_and_off_city_ones():
    m = city_map()
    s, w, n, e = m["bbox"]
    lat0 = math.radians((s + n) / 2)

    def ll(x, y):
        return n - y / (110574 * m["scale"]), w + x / (math.cos(lat0) * 111320 * m["scale"])

    areas = [{"name": "Alpha", "lat": ll(300, 200)[0], "lon": ll(300, 200)[1], "rank": 2},
             {"name": "District 1", "lat": ll(450, 300)[0], "lon": ll(450, 300)[1], "rank": 1},
             {"name": "alpha", "lat": ll(500, 200)[0], "lon": ll(500, 200)[1], "rank": 1},
             {"name": "Far away", "lat": n + 1, "lon": w, "rank": 1}]
    out = pa.layout(m, areas, ["District 0", "District 1", "District 2"])
    assert [q["n"] for q in out] == ["Alpha"], out
    assert (out[0]["x"], out[0]["y"]) == tuple(round(v) for v in pp.to_px(m, areas[0]["lat"], areas[0]["lon"]))
    assert out[0]["r"] == 2


def test_the_page_carries_the_areas_label_only_and_with_its_own_block():
    d = bundle()
    d["brief"]["palace"]["areas"] = [{"name": "Alpha Hill", "lat": 39.9525, "lon": -75.165, "rank": 1}]
    html = build_timeline(*load(copy.deepcopy(d)))[0]
    assert "Alpha Hill" in html
    a, b = html.index("neighbourhood names: label only"), html.index("/neighbourhood names")
    block = html[a:b]
    assert "pl-area" in block and "addEventListener" not in block and "pl-dist" not in block
    assert "pointer-events:none" in html.split(".pl-area{")[1].split("}")[0]


# ── in a browser ────────────────────────────────────────────────────────────
pw = pytest.importorskip("playwright.sync_api")


def _philly_city():
    """A synthetic city on Philadelphia's own box (no map data, just a few streets), so the real list is laid out."""
    m = city_map()
    m.update(bbox=list(PHILLY_BOX), scale=0.1, place="Philadelphia")
    s, w, n, e = PHILLY_BOX
    m["W"] = round((e - w) * math.cos(math.radians((s + n) / 2)) * 111320 * 0.1)
    m["H"] = round((n - s) * 110574 * 0.1)
    m["streets"] = [x for x in m["streets"] if max(x["p"]) < min(m["W"], m["H"])]
    m["rails"], m["stations"], m["landmarks"], m["water"], m["rivers"], m["parks"] = [], [], [], [], [], []
    return m


def _page(tmp_path_factory, areas=None):
    d = bundle(with_city=False)
    m = _philly_city()
    d["brief"]["palace"].update(place="Philadelphia", bbox=list(PHILLY_BOX), data_z=palace.pack({"map": m, "blocks": pp.lots(m)}))
    d["brief"]["palace"]["districts"] = [{"unit": i, "name": f"District {i}", "bounds": [39.93 + i * .01, -75.2 + i * .03, 39.94 + i * .01, -75.17 + i * .03]}
                                         for i in range(3)]
    d["brief"]["palace"]["areas"] = areas if areas is not None else pa.default_areas("Philadelphia", PHILLY_BOX)
    root = tmp_path_factory.mktemp("plar")
    (root / "page.html").write_text(build_timeline(*load(d))[0], encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv_ = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv_.serve_forever, daemon=True).start()
    return srv_, f"http://127.0.0.1:{srv_.server_address[1]}/page.html"


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    s, u = _page(tmp_path_factory)
    yield u
    s.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = None
        for launch in (lambda: p.chromium.launch(), lambda: p.chromium.launch(channel="chrome")):
            try:
                b = launch()
                break
            except Exception:                                # noqa: BLE001
                continue
        if b is None:
            pytest.skip("no browser to drive")
        yield b
        b.close()


VIS = """()=>[...document.querySelectorAll('#palace-svg .pl-area')].filter(t=>t.style.display!=='none').map(t=>{var r=t.getBoundingClientRect();
  return {n:t.textContent, r:+t.dataset.r, l:r.left, t:r.top, rt:r.right, b:r.bottom}})"""


def _whole_city(pg):
    pg.click("#pal-ctl [data-z=fit]")
    pg.wait_for_timeout(1200)
    return pg.evaluate(VIS)


def test_every_major_name_is_in_the_page_label_only_and_no_two_shown_names_overlap_at_the_whole_city_zoom(browser, url):
    ctx = browser.new_context(viewport={"width": 1500, "height": 900})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(1800)
    dom = pg.evaluate("[...document.querySelectorAll('#palace-svg .pl-area')].map(t=>t.textContent)")
    for n in MAJOR + NAMED:
        assert n in dom, n
    assert not any(n in ("District 0", "District 1", "District 2") for n in dom)               # a unit's own name is not drawn twice
    assert pg.evaluate("getComputedStyle(document.querySelector('#palace-svg .pl-area')).pointerEvents") == "none"
    assert pg.evaluate("document.querySelectorAll('#palace-svg .pl-area[data-u]').length") == 0
    vis = _whole_city(pg)
    names = {v["n"] for v in vis}
    assert len(vis) >= 4 and {v["r"] for v in vis} == {1}, vis                                # the major names, and only they, at the far zoom
    assert "South Philadelphia" in names or "North Philadelphia" in names
    for i, a in enumerate(vis):
        for b in vis[i + 1:]:
            assert a["rt"] <= b["l"] or b["rt"] <= a["l"] or a["b"] <= b["t"] or b["b"] <= a["t"], (a["n"], b["n"])
        # and none sits on a district's name
        for d in pg.evaluate("[...document.querySelectorAll('#palace-svg .pl-dist')].map(t=>{var r=t.getBoundingClientRect(); return [r.left,r.top,r.right,r.bottom]})"):
            assert a["rt"] <= d[0] or d[2] <= a["l"] or a["b"] <= d[1] or d[3] <= a["t"], a["n"]
    # coming in brings the smaller names, still without any overlap
    for _ in range(3):
        pg.click("#pal-ctl [data-z=in]")
        pg.wait_for_timeout(600)
    pg.wait_for_timeout(600)
    near = pg.evaluate(VIS)
    for i, a in enumerate(near):
        for b in near[i + 1:]:
            assert a["rt"] <= b["l"] or b["rt"] <= a["l"] or a["b"] <= b["t"] or b["b"] <= a["t"], (a["n"], b["n"])
    assert not errs, errs
    ctx.close()


def test_a_lower_ranked_name_gives_way_to_a_higher_one_it_would_touch(browser, tmp_path_factory):
    m = _philly_city()
    pts = [(1000, 600), (1030, 612)]
    s, w, n, e = PHILLY_BOX
    lat0 = math.radians((s + n) / 2)
    areas = [{"name": nm, "lat": n - y / (110574 * 0.1), "lon": w + x / (math.cos(lat0) * 111320 * 0.1), "rank": r}
             for (x, y), nm, r in zip(pts, ("Lower", "Higher"), (1, 1))]
    areas[0]["rank"], areas[1]["rank"] = 1, 1
    s_, u = _page(tmp_path_factory, areas)
    try:
        ctx = browser.new_context(viewport={"width": 1500, "height": 900})
        pg = ctx.new_page()
        pg.goto(u)
        pg.wait_for_timeout(1800)
        vis = {v["n"] for v in _whole_city(pg)}
        assert len(vis) == 1, vis                                                              # one of two touching names is hidden
        ctx.close()
    finally:
        s_.shutdown()


def test_the_phone_map_draws_the_names_too(browser, url):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.goto(url)
    pg.wait_for_timeout(2500)
    n = pg.evaluate("document.querySelectorAll('#palace-svg-m .pl-area').length")
    if n == 0:
        pg.evaluate("window._palMob.open()")
        pg.wait_for_timeout(1500)
        n = pg.evaluate("document.querySelectorAll('#palace-svg-m .pl-area').length")
    assert n >= 30, n
    pg.wait_for_timeout(500)
    fs = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#palace-svg-m .pl-area')).fontSize) * parseFloat(document.querySelector('#palace-svg-m').style.getPropertyValue('--pz'))")
    assert fs >= 10, fs                                                                        # readable on the phone (px on the screen at the map's zoom)
    ctx.close()


LBL = """()=>{ const s=document.getElementById('palace-svg'), all=[...s.querySelectorAll('text')];
  const shown=t=>t.style.display!=='none' && getComputedStyle(t).display!=='none' && t.getBoundingClientRect().width>0;
  const flat=[...s.querySelectorAll('.pl-area,.pl-dist,.pl-pkt')].filter(shown).map(t=>{const r=t.getBoundingClientRect(); return {n:t.textContent,d:t.classList.contains('pl-dist'),l:r.left,t:r.top,r:r.right,b:r.bottom};});
  return {texts:all.length, laid:all.filter(t=>getComputedStyle(t).display!=='none').length, flat,
          managed:(s._li||[]).length, hidden:(s._li||[]).filter(i=>!i.keep).length, ms:(window._palT||{}).lbl}; }"""


def test_names_are_decluttered_and_only_names_near_the_window_are_laid_out(browser, url):
    """The label pass (lblFit): names in priority order, a colliding lower one hidden, none of the flat names overlapping;
    and names far from the window are not laid out (display:none) until a pan brings them near."""
    ctx = browser.new_context(viewport={"width": 1300, "height": 850})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(1800)
    for _ in range(2):
        pg.click("#pal-ctl [data-z=in]")
        pg.wait_for_timeout(700)
    pg.wait_for_timeout(500)
    near = pg.evaluate(LBL)
    assert near["managed"] > 0 and near["laid"] < near["texts"], near
    for i, a in enumerate(near["flat"]):
        for b in near["flat"][i + 1:]:
            if a["d"] and b["d"]:
                continue                                                               # two units' own names are never hidden
            assert a["r"] <= b["l"] or b["r"] <= a["l"] or a["b"] <= b["t"] or b["b"] <= a["t"], (a["n"], b["n"])
    far = _whole_city(pg) and pg.evaluate(LBL)
    for i, a in enumerate(far["flat"]):
        for b in far["flat"][i + 1:]:
            if a["d"] and b["d"]:
                continue
            assert a["r"] <= b["l"] or b["r"] <= a["l"] or a["b"] <= b["t"] or b["b"] <= a["t"], (a["n"], b["n"])
    assert far["hidden"] >= 1, far                                                     # the whole city has names to hide
    assert not errs, errs
    ctx.close()
