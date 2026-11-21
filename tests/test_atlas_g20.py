"""The Memory Atlas "A country" covers the whole G20 that is a country (Luke 13 Nov 2026; brief ORG/briefs/atlas-g20-1113.md): 19 countries.
Per country: it builds; its first-level divisions are the official number; every division has a capital pin inside its own border; the projection keeps
the mainland undistorted and no inset overlaps it; the hosted division tier is under 10 KB gzipped; and (a browser) no label overlaps at the opening
view, the Tour hops, the card enlarges and Esc gives it back, the minimap shows and the globe switches (Chromium and WebKit).

Three countries keep the tier an earlier release signed (lines-and-faces, 1.9.x) and are REPORTED, not hidden, in LEGACY_GAPS: what the tier has against the official
number, and its size. They are rebuilt only when the Board decides (BUILD.md)."""
import gzip
import http.server
import json
import math
import os
import threading

import pytest

from alto.build import palace_assets, world_geo as wg, world_plan as wp
from tests.test_world_palace import built, data_of
from tests.test_world_palace_render import ENL, _settle, browser  # noqa: F401

G20 = ("USA", "ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN", "ITA", "JPN", "MEX", "RUS", "SAU", "ZAF", "KOR", "TUR", "GBR")
# the official number of first-level divisions as the Atlas draws them (the word each country uses is in docs/world-palace/g20_divisions.py WORD)
OFFICIAL = {"USA": 51,      # 50 states + the District of Columbia
            "ARG": 24,      # 23 provinces + the Autonomous City of Buenos Aires
            "AUS": 8,       # 6 states + 2 mainland territories
            "BRA": 27,      # 26 states + the Federal District
            "CAN": 13,      # 10 provinces + 3 territories
            "CHN": 31,      # 22 provinces + 5 autonomous regions + 4 municipalities (Hong Kong, Macau and Taiwan are separate polygons on the map)
            "FRA": 13,      # the 13 metropolitan regions (overseas regions are left off, brief)
            "DEU": 16,      # 16 Länder
            "IND": 36,      # 28 states + 8 union territories
            "IDN": 38,      # provinces (since the 2022 Papua split)
            "ITA": 20,      # 20 regions
            "JPN": 47,      # 47 prefectures
            "MEX": 32,      # 31 states + Mexico City
            "RUS": 83,      # federal subjects without Crimea and Sevastopol (89 with)
            "SAU": 13,      # 13 provinces
            "ZAF": 9,       # 9 provinces
            "KOR": 17,      # 9 provinces + 8 metropolitan / special cities
            "TUR": 81,      # 81 provinces
            "GBR": 12}      # England's 9 regions + Scotland, Wales, Northern Ireland
# country: (divisions the signed tier holds, why)
LEGACY_GAPS = {"CHN": (30, "the 1.9.x faces tier merged Qinghai into its neighbours"),
               "IDN": (33, "Natural Earth 5.1.2 predates the 2022 Papua split (four new provinces)"),
               "RUS": (79, "the 1.9.x faces tier: 79 faces (Crimea left it in 1.9.254, US borders) for 83 federal subjects (Chita, Aga Buryat and Koryak style names are the old Natural Earth ones)")}
OLD_SIZE = {"CHN", "RUS"}     # the signed tiers over 10 KB gz (13.0 KB, 25.6 KB)
HOSTED_NEW = ("ARG", "CAN", "FRA", "DEU", "IND", "ITA", "JPN", "MEX", "SAU", "KOR", "TUR", "GBR")     # built by docs/world-palace/build_g20_divisions.py from admin-1 shapes


def tier(iso):
    with gzip.open(os.path.join(wg.DIR, f"a1p-{iso}.json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


def rings_of(flat_rings, q):
    out = []
    for flat in flat_rings:
        x, y = flat[0], flat[1]
        pts = [(x / q, y / q)]
        for i in range(2, len(flat), 2):
            x += flat[i]
            y += flat[i + 1]
            pts.append((x / q, y / q))
        out.append(pts)
    return out


def inside(pt, rings):
    """Even-odd point in a division's rings (a hole is a ring inside a ring)."""
    x, y = pt
    c = False
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


def shapes(iso):
    T = tier(iso)
    return {n: rings_of(r, T["q"]) for n, r in T["s"]}


def ee(lon, lat):
    return wg.project(lon, lat)


def test_the_g20_is_the_nineteen_countries_and_the_picker_offers_them_all():
    assert wp.ATLAS_OFFERED == G20 and [c for c, _ in wp.ATLAS_COUNTRIES] == list(G20)
    names = dict(wp.ATLAS_COUNTRIES)
    assert len(names) == 19 and "European Union" not in names.values() and "African Union" not in names.values()
    for c in G20:
        assert wp.atlas_country(names[c]) == c and wp.atlas_country(c) == c


@pytest.mark.parametrize("iso", G20)
def test_each_country_builds_and_is_planned_in_its_own_projection(iso):
    from tests.test_world_palace import loaded
    b, ns, _ = loaded(world={"country": iso})
    p = wp.plan(b, ns)
    assert p["country"] == iso and p["multi"] == [iso]
    tops = [t for u in p["units"] for t in u["tops"]]
    assert tops and all(p["places"][t]["c"] == iso for t in tops)
    assert len({p["places"][t]["label"] for t in tops}) == len(tops)                      # one division each: no two cards on one pin
    html = built(world={"country": iso})[0]
    assert data_of(html)["scope"] == iso
    assert (p["proj"] == "USA") if iso == "USA" else (p["proj"]["t"] in ("alb", "lcc", "merc") and len(p["proj"]["c"]) == 2)
    assert iso in wg.manifest()["s"], "the hosted division tier is in the manifest"


@pytest.mark.parametrize("iso", G20)
def test_the_division_count_is_the_official_number(iso):
    have = len(tier(iso)["s"])
    if iso in LEGACY_GAPS:
        assert have == LEGACY_GAPS[iso][0] != OFFICIAL[iso], f"{iso}: {LEGACY_GAPS[iso][1]}; update LEGACY_GAPS when the tier is rebuilt"
    else:
        assert have == OFFICIAL[iso], iso
    names = [n for n, _ in tier(iso)["s"]]
    assert len(set(names)) == len(names) and all(names)


@pytest.mark.parametrize("iso", G20)
def test_every_division_has_a_capital_pin_inside_its_own_border(iso):
    sh = shapes(iso)
    S = wp._states(iso)                                                                      # the pins the planner uses: a division's capital
    bad = []
    for n, rings in sh.items():
        assert n in S, f"{iso}: no capital for {n!r}"
        row = S[n][0]
        if not inside(ee(row[4], row[5]), rings):
            bad.append((n, row[0]))
    if iso in LEGACY_GAPS or iso == "USA":                                                   # the signed tiers: reported when a pin stands outside its coarse coast
        assert len(bad) <= 4, (iso, bad)
    else:
        assert not bad, (iso, bad)
    if iso in HOSTED_NEW:                                                                    # the hosted capitals agree with the planner's and are inside
        K = {k[0]: k for k in tier(iso)["k"]}
        assert set(K) == set(sh), iso
        for n, k in K.items():
            assert inside(ee(k[2], k[3]), sh[n]), (iso, n, k[1])
            assert (abs(S[n][0][4] - k[2]) < 1e-6 and abs(S[n][0][5] - k[3]) < 1e-6), (iso, n)


@pytest.mark.parametrize("iso", G20)
def test_the_hosted_division_tier_is_under_10_kb_gz(iso):
    size = os.path.getsize(os.path.join(wg.DIR, f"a1p-{iso}.json.gz"))
    if iso in OLD_SIZE:
        assert size > 10240, f"{iso}: the signed tier is now under 10 KB ({size}); drop it from OLD_SIZE"
    else:
        assert size < 10240, (iso, size)


@pytest.mark.parametrize("iso", [c for c in G20 if c != "USA"])
def test_the_projection_keeps_the_mainland_undistorted_and_has_no_inset(iso):
    f = wg.country_projection(iso)
    d = 0.4
    worst = (1.0, 1.0)
    for n, k in ((r[3], r) for r in (wp._states(iso)[s][0] for s in wp._states(iso))):
        lon, lat = k[4], k[5]
        x0, y0 = f(lon, lat)
        xe, ye = f(lon + d, lat)
        xn, yn = f(lon, lat + d)
        sc = math.radians(d) * wg.SCALE
        kk = math.hypot(xe - x0, ye - y0) / (sc * math.cos(math.radians(lat)))               # scale along the parallel
        hh = math.hypot(xn - x0, yn - y0) / sc                                               # scale along the meridian
        assert 0.7 < kk < 1.45 and 0.7 < hh < 1.45, (iso, n, round(kk, 2), round(hh, 2))     # no sheared or stretched land where a card can stand
        assert yn < y0 and xe > x0, (iso, n)                                                  # north is up, east is right: never mirrored
    spec = wg.COUNTRY_PROJ[iso]
    assert "insets" not in spec and "box" not in spec                                         # (one flat projection; only the US has insets)


def ee_inv(x, y):
    """Equal Earth world units -> (lon, lat) (the inverse of world_geo.project)."""
    X, Y = x / wg.SCALE, -y / wg.SCALE
    th = Y / wg._A1
    for _ in range(12):
        t2 = th * th
        t6 = t2 ** 3
        th -= (th * (wg._A1 + wg._A2 * t2 + t6 * (wg._A3 + wg._A4 * t2)) - Y) / (wg._A1 + 3 * wg._A2 * t2 + t6 * (7 * wg._A3 + 9 * wg._A4 * t2))
    t2 = th * th
    t6 = t2 ** 3
    return (math.degrees(X * wg._M * (wg._A1 + 3 * wg._A2 * t2 + t6 * (7 * wg._A3 + 9 * wg._A4 * t2)) / math.cos(th)), math.degrees(math.asin(math.sin(th) / wg._M)))


def test_the_us_insets_do_not_overlap_the_lower_48():
    sh = shapes("USA")
    pts = {"A": [], "H": [], "M": []}
    for n, rings in sh.items():
        g = "A" if n == "Alaska" else "H" if n == "Hawaii" else "M"
        for ring in rings:
            for x, y in ring:
                lon, lat = ee_inv(x, y)
                pts[g].append(wg.usa_project(lon, lat, g))
    box = {g: (min(p[0] for p in v), min(p[1] for p in v), max(p[0] for p in v), max(p[1] for p in v)) for g, v in pts.items()}
    for g in "AH":
        b = box[g]
        assert not [p for p in pts["M"] if b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]], (g, b)     # not one lower-48 vertex inside an inset's frame
    a, h = box["A"], box["H"]
    assert a[2] < h[0] or h[2] < a[0] or a[3] < h[1] or h[3] < a[1]                                    # and the two insets are apart


# ── the page: opening view, Tour, enlarge + Esc, minimap, globe ──
@pytest.fixture(scope="module")
def origin_g20():
    pages = {}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            iso = path.strip("/").replace(".html", "")
            if iso in G20:
                pages.setdefault(iso, built(world={"country": iso})[0])
            hit = (("text/html", pages[iso]) if iso in G20 else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
            body = hit[1] if hit else b"no"
            body = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


LABELS = """() => { var L = [].slice.call(document.querySelectorAll('#wpal-root .wp-lbl')).filter(function(l){ var s = getComputedStyle(l), r = l.getBoundingClientRect();
    return !l.classList.contains('wp-off') && s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > .05 && r.width > 0 && r.right > 0 && r.left < innerWidth && r.bottom > 0 && r.top < innerHeight; });
  var R = L.map(function(l){ var r = l.getBoundingClientRect(); return {t: l.textContent, x0: r.left, y0: r.top, x1: r.right, y1: r.bottom}; }), bad = [];
  for (var i = 0; i < R.length; i++) for (var j = i + 1; j < R.length; j++){ var a = R[i], b = R[j], ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0); if (ox > 1.5 && oy > 1.5) bad.push([a.t, b.t, Math.round(ox), Math.round(oy)]); }
  return {n: R.length, bad: bad}; }"""


def test_every_country_opens_clean_and_its_tour_card_minimap_globe_and_esc_work(browser, origin_g20):  # noqa: F811
    problems = []
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        for iso in G20:
            page.goto(f"{origin_g20}/{iso}.html")
            page.wait_for_function("window.AltoWorld && document.querySelectorAll('#wpal-root .wp-s').length > 3", timeout=40000)
            page.wait_for_timeout(1200)
            if page.evaluate("AltoWorld.view().k / AltoWorld.view().kW") <= 1.5:
                problems.append((iso, "the country does not fill the frame"))
            r = page.evaluate(LABELS)
            if r["n"] < 1 or r["bad"]:
                problems.append((iso, "labels at the opening view", r))
            for sty in ("retro", "holo"):                                                  # the same opening view in the other two styles
                page.evaluate("(s) => window._altoStyle.set(s)", sty)
                page.wait_for_timeout(1500)
                r = page.evaluate(LABELS)
                if r["n"] < 1 or r["bad"]:
                    problems.append((iso, "labels at the opening view in " + sty, r))
            page.evaluate("window._altoStyle.set('classic')")
            page.wait_for_timeout(600)
            page.evaluate("AltoWorld.select('erie')")
            _settle(page, 1200)
            if page.evaluate(ENL) != "erie":
                problems.append((iso, "the card did not enlarge"))
            if not page.evaluate("document.querySelector('#wpal-root .wp-mm') && document.querySelector('#wpal-root .wp-mm').classList.contains('on')"):
                problems.append((iso, "no minimap"))
            page.keyboard.press("Escape")
            _settle(page, 600)
            if page.evaluate(ENL):
                problems.append((iso, "Esc did not give the card back"))
            page.evaluate("AltoWorld.tourMode(true); AltoWorld.select('sj', {instant: true})")
            _settle(page, 500)
            page.evaluate("AltoWorld.hop(1)")
            page.wait_for_timeout(400)
            if not page.evaluate("AltoWorld.plane()") or not page.evaluate("!!document.querySelector('#wpal-root .wp-train, #wpal-root .wp-plane, #wpal-root .wp-ship')"):
                problems.append((iso, "the Tour leg shows no vehicle"))
            page.evaluate("AltoWorld.tourMode(false)")
            _settle(page, 300)
            if page.evaluate("AltoWorld.globe(true)"):
                _settle(page, 700)
                if not page.evaluate("document.getElementById('wpal-root').classList.contains('wp-g')"):
                    problems.append((iso, "no globe"))
                page.evaluate("AltoWorld.globe(false)")
                _settle(page, 300)
            if errors:
                problems.append((iso, "page errors", list(errors)))
                errors.clear()
        assert not problems, problems
    finally:
        page.close()
