"""A Memory Atlas of one country (Art's sheet, "World or a country"; brief.world.country): its states are the places, each top card on a
state's capital, the cards under it on that state's largest cities; the page frames the country, its button and crumb are the country,
the rest of the world fades. A brief without it is the world map, unchanged. The page in Chromium and WebKit."""
import http.server
import threading

import pytest

from alto.build import palace_assets, world_plan as wp
from tests.test_world_palace import built, data_of, loaded
from tests.test_world_palace_render import browser  # noqa: F401


def test_one_country_plans_states_and_their_cities():
    b, ns, _ = loaded(world={"country": "USA"})
    p = wp.plan(b, ns)
    assert p["used"] == {"USA": 0} and p["multi"] == ["USA"] and p["country"] == "USA"
    tops = [t for u in p["units"] for t in u["tops"]]
    assert all(p["places"][t]["c"] == "USA" and p["places"][t]["k"] == "sub" for t in tops)
    assert len({p["places"][t]["label"] for t in tops}) == len(tops)                 # one state each
    assert p["places"]["pj1"]["k"] == "city"
    assert wp.plan(*loaded(world={"country": "USA"})[:2]) == p                        # deterministic
    with pytest.raises(ValueError):
        wp.validate({"country": "XXX"})
    assert "scope" not in data_of(built()[0]) and data_of(built(world={"country": "USA"})[0])["scope"] == "USA"


@pytest.fixture(scope="module")
def origin():
    html = built(world={"country": "USA"})[0]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js"
                   else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_the_page_frames_the_country(browser, origin):  # noqa: F811
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        page.wait_for_timeout(600)
        assert page.evaluate("AltoWorld.view().k / AltoWorld.view().kW") > 2                       # the country, not the world
        assert "United States" in page.evaluate("document.querySelector('#wpal-root .wp-ctl').textContent")
        assert page.evaluate("document.querySelector('#wpal-root .wp-nav .wp-at').textContent") == "United States"
        assert page.evaluate("document.getElementById('wpal-root').classList.contains('wp-one')")
        page.evaluate("AltoWorld.select('pj')")
        page.wait_for_timeout(1800)
        page.evaluate("AltoWorld.world()")
        page.wait_for_timeout(1500)
        assert page.evaluate("AltoWorld.view().k / AltoWorld.view().kW") > 2                       # home is the country
        assert not errors, errors
    finally:
        page.close()


def test_set_up_world_scope_words_and_picker_markup():
    """The two Atlas doors that need no browser: the MCP words (World | A country, the 9 offered) and the homepage tiles."""
    assert [c for c, _ in wp.ATLAS_COUNTRIES][0] == "USA" and len(wp.ATLAS_COUNTRIES) == 9  # the data for all nine is kept
    assert wp.atlas_country("United States") == wp.atlas_country("us") == wp.atlas_country("usa") == "USA"
    # Round 4 (Art): the picker offers only the signed countries (the US + AUS BRA CHN IDN RUS ZAF); India and Canada stay hidden. One list (world_plan.ATLAS_OFFERED).
    on = ("USA", "AUS", "BRA", "CHN", "IDN", "RUS", "ZAF")
    assert wp.ATLAS_OFFERED == on and [c for c, _ in wp.offered_countries()] == list(on)
    for c, n in wp.ATLAS_COUNTRIES:
        assert (wp.atlas_country(n) == c and wp.atlas_country(c) == c) if c in on else (wp.atlas_country(n) is None and wp.atlas_country(c) is None), c
    assert wp.atlas_country("South Africa") == "ZAF" and wp.atlas_country("India") is None and wp.atlas_country("Canada") is None
    assert wp.atlas_country("France") is None
    import pathlib
    home = (pathlib.Path(wp.__file__).parents[1] / "engine" / "home_template.html").read_text()
    for w in ("A country", "Every card on the whole map.", "One country, with its states or regions.", "Pick a country"):
        assert w in home
    assert home.count('class="nt-crow"') == 9  # the rows stay; NT_COUNTRIES_ON decides which are shown
    import re
    for path in (pathlib.Path(wp.__file__).parents[1] / "engine" / "home_template.html", pathlib.Path(wp.__file__).parents[2] / "engine" / "home_template.html"):
        on = re.search(r"const NT_COUNTRIES_ON = \[([^\]]*)\]", path.read_text()).group(1)
        assert re.findall(r"'(\w+)'", on) == list(wp.ATLAS_OFFERED), path
    from alto import mcp_server
    doc = (mcp_server.set_up_world.__doc__ or "")
    assert "scope:" in doc and "A country" in doc


def test_the_picker_offers_only_the_signed_countries(browser):  # noqa: F811
    """Round 4: of the nine rows only the US + AUS BRA CHN IDN RUS ZAF are visible (not India, Canada), searching never brings the others back."""
    from alto import mcp_server
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        import pathlib
        page.goto((pathlib.Path(__file__).resolve().parents[1] / "alto" / "engine" / "home_template.html").as_uri())
        vis = lambda: page.evaluate("[...document.querySelectorAll('#nt-clist .nt-crow')].filter(r => !r.hidden).map(r => r.dataset.iso)")
        assert vis() == ["USA", "AUS", "BRA", "CHN", "IDN", "RUS", "ZAF"]
        page.evaluate("document.getElementById('nt-cq').value='ind'; document.getElementById('nt-cq').dispatchEvent(new Event('input'))")
        assert vis() == ["IDN"]
        page.evaluate("document.getElementById('nt-cq').value='canada'; document.getElementById('nt-cq').dispatchEvent(new Event('input'))")
        assert vis() == []
    finally:
        page.close()
    assert "India" not in (mcp_server.set_up_world.__doc__ or "")


def test_a_country_tour_leg_rides_a_train_on_a_rail_not_the_plane(browser, origin):  # noqa: F811
    from tests.test_world_palace_render import _settle
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        page.wait_for_timeout(600)
        page.evaluate("AltoWorld.tourMode(true); AltoWorld.select('sj', {instant: true})")
        _settle(page, 600)
        page.evaluate("AltoWorld.hop(1)")
        page.wait_for_timeout(500)
        assert page.evaluate("AltoWorld.plane()")
        assert page.evaluate("!!document.querySelector('#wpal-root .wp-train') && !document.querySelector('#wpal-root .wp-trail')")
        assert page.evaluate("document.querySelectorAll('#wpal-root .wp-train > g').length") >= 4        # the puff layer, the locomotive and two cars
        assert page.evaluate("!!document.querySelector('#wpal-root .wp-rail .c') && document.querySelector('#wpal-root .wp-rail .c').getAttribute('d').length > 10")
        _settle(page, 3200)
        assert not page.evaluate("AltoWorld.plane()") and not page.evaluate("!!document.querySelector('#wpal-root .wp-train')")
        assert not page.evaluate("!!document.querySelector('#wpal-root .wp-ff.on')")                 # the Tour flag fill is OFF in country scope (CEO ruling 2)
        assert not errors, errors
    finally:
        page.close()


def test_the_us_map_has_states_as_shapes_in_albers_and_one_geometry_for_flat_and_globe(browser, origin):  # noqa: F811
    from tests.test_world_palace_render import _settle
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelectorAll('#wpal-root .wp-s').length > 40", timeout=20000)
        n = page.evaluate("document.querySelectorAll('#wpal-root .wp-s').length")
        assert 50 <= n <= 52, n                                            # 50 states + D.C., Rhode Island its own shape
        assert page.evaluate("document.querySelectorAll('#wpal-root .wp-frame').length") == 2        # the Alaska and Hawaii insets
        tones = page.evaluate("new Set([].map.call(document.querySelectorAll('#wpal-root .wp-s'), p => getComputedStyle(p).fill)).size")
        assert tones >= 4, tones                                           # each state has a land tone of its own (five in rotation)
        page.evaluate("AltoWorld.select('pj', {instant: true})")
        _settle(page, 900)
        page.evaluate("AltoWorld.tourMode(true)")
        assert not page.evaluate("!!document.querySelector('#wpal-root .wp-ff.on')")
        assert not errors, errors
    finally:
        page.close()


_REC = """window.__rec=[]; window.__puffY=[]; (function f(){ var t=document.querySelector('#wpal-root .wp-train'); if(t){
  var us=[].slice.call(t.children).filter(function(c,i){ return i>0&&c.tagName=='g'; }).map(function(g){ var m=/translate\\(([-\\d.]+) ([-\\d.]+)\\) rotate\\(([-\\d.]+)\\) scale\\(([-\\d.]+) ([-\\d.]+)\\)/.exec(g.getAttribute('transform')||'');
    return m?m.slice(1).map(Number):null; }); window.__rec.push(us);
  var p=t.children[0].lastElementChild; if(p){ var q=/translate\\(([-\\d.]+) ([-\\d.]+)\\)/.exec(p.getAttribute('transform')||''); if(q) window.__puffY.push([+q[1],+q[2],p.getAttribute('opacity')]); } }
  requestAnimationFrame(f); })();"""


@pytest.mark.parametrize("vp", [{"width": 1280, "height": 800}, {"width": 390, "height": 844}], ids=["desktop", "phone"])
def test_the_train_never_turns_upside_down_keeps_its_cars_apart_and_its_steam_rises(browser, origin, vp):  # noqa: F811
    """Luke L-1106-103418: westward legs flip the sprite left-right and never rotate it past 90 degrees (funnel and steam stay up, the steam rises);
    north-south legs and bends keep the cars spaced (no pile-up at a stop or a corner)."""
    from tests.test_world_palace_render import _settle
    page = browser.new_page(viewport=vp)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        page.wait_for_timeout(600)
        page.evaluate("AltoWorld.tourMode(true); AltoWorld.select('sj', {instant: true})")
        _settle(page, 600)
        page.evaluate(_REC)
        for step in (1, 1, 1, -1, -1, -1):
            page.evaluate(f"AltoWorld.hop({step})")
            page.wait_for_timeout(3600)
        rec = page.evaluate("window.__rec")
        frames = [f for f in rec if f and all(f)]
        assert len(frames) > 20, len(frames)
        units = [u for f in frames for u in f]
        assert max(abs(u[2]) for u in units) <= 90.01                                         # never past 90 degrees: never upside down
        assert any(u[3] < 0 for u in units) and any(u[3] > 0 for u in units)                  # a westward leg is mirrored, an eastward one is not
        assert all(abs(u[3]) == pytest.approx(abs(u[4]), rel=0.01) for u in units)            # mirrored, never squashed
        need = 14 if vp["width"] < 500 else 30                                                 # cars of ~20 units at 0.95x / 1.8x: never piled
        gap = min(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** .5 for f in frames for a, b in zip(f, f[1:]))
        assert gap >= need, gap
        puffs = page.evaluate("window.__puffY")
        assert len(puffs) > 10 and all(float(p[2]) > 0 for p in puffs)                        # steam is on screen during the ride
        assert not errors, errors
    finally:
        page.close()


def test_the_scope_pill_names_the_scope_and_opens_the_homepage_setup_for_this_timeline(browser, origin):  # noqa: F811
    """CEO ruling 6 Nov: the pill shows the scope; tapping it goes to the homepage set-up prefilled for THIS timeline (no in-page rebuild)."""
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        assert page.evaluate("document.querySelector('#wpal-root .wp-scope .n').textContent") == "United States"
        assert page.evaluate("document.querySelector('#wpal-root .wp-scope').getAttribute('aria-haspopup')") == "dialog"
        page.evaluate("document.title = 'Civ Pro'; window.__go = null; window.__altoGo = function(u){ window.__go = u; }")
        page.click("#wpal-root .wp-scope")
        assert page.evaluate("window.__go") == "index.html?rescope=USA&tl=Civ%20Pro"
        assert not errors, errors
    finally:
        page.close()


def test_the_homepage_opens_the_atlas_setup_prefilled_when_the_pill_sends_it_there(browser):  # noqa: F811
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto((root / "alto" / "engine" / "home_template.html").as_uri() + "?rescope=USA&tl=Civ%20Pro")
        page.wait_for_function("document.getElementById('nt-scrim') && document.getElementById('nt-scrim').classList.contains('open')", timeout=8000)
        assert page.evaluate("document.getElementById('nt-title').value") == "Civ Pro"
        assert page.evaluate("document.querySelector('#nt-modal .nt-kind[data-kind=palace]').getAttribute('aria-pressed')") == "true"
        assert page.evaluate("document.querySelector('#nt-scope .nt-kind[data-scope=country]').getAttribute('aria-pressed')") == "true"
        assert page.evaluate("document.querySelector('#nt-clist .nt-crow[data-iso=USA]').classList.contains('on') || ntScope.iso") in (True, "USA")
        page.evaluate("window.openClaude = function(t){ window.__p = t; }")
        page.evaluate("document.getElementById('nt-project').value = 'Civ Pro'")
        page.evaluate("document.getElementById('nt-make').click()")
        p = page.evaluate("window.__p")
        assert "existing Memory Atlas \"Civ Pro\"" in p and "country 'USA'" in p, p
        assert not errors, errors
    finally:
        page.close()


@pytest.fixture(scope="module")
def origin_insets():
    """The US Atlas with two cards put in the insets: Erie & Co in Alaska, Hanna in Hawaii (places as set_up_world resolves them)."""
    ak, hi = wp.resolve("Alaska"), wp.resolve("Hawaii")
    html = built(world={"country": "USA", "places": {"erie": ak, "hanna": hi}})[0]

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            hit = (("text/html", html) if path in ("/", "/index.html") else ("text/javascript", "") if path == "/alto-cloud.js"
                   else palace_assets.find(path))
            body = (hit[1] if hit else "no").encode("utf-8")
            self.send_response(200 if hit else 404)
            self.send_header("Content-Type", hit[0] if hit else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_a_leg_into_or_out_of_an_inset_is_a_hand_off_with_no_rail_and_a_lower_48_leg_has_one(browser, origin_insets):  # noqa: F811
    from tests.test_world_palace_render import _settle
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin_insets + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        page.wait_for_timeout(600)
        # the two inset cards really stand in the insets (Alaska and Hawaii), well apart on the screen
        assert page.evaluate("document.querySelectorAll('#wpal-root .wp-frame').length") == 2
        page.evaluate("AltoWorld.tourMode(true)")
        seen = {"rail": 0, "hand": 0}
        for start, step in (("erie", 1), ("erie", -1), ("hanna", 1), ("hanna", -1)):
            page.evaluate(f"AltoWorld.select({start!r}, {{instant: true}})")
            _settle(page, 700)
            page.evaluate(f"AltoWorld.hop({step})")
            page.wait_for_timeout(450)                                                              # (a train would be on the screen by now)
            assert not page.evaluate("!!document.querySelector('#wpal-root .wp-train') || !!document.querySelector('#wpal-root .wp-rail')"), (start, step)
            assert not page.evaluate("AltoWorld.plane()"), (start, step)
            seen["hand"] += 1
            _settle(page, 1500)
        # control: legs between lower-48 stops still ride the rail (at least one of these does)
        rails = 0
        for nid in ("pj1", "pj2", "ms", "gj", "sj", "byrd"):
            page.evaluate(f"AltoWorld.select({nid!r}, {{instant: true}})")
            _settle(page, 600)
            page.evaluate("AltoWorld.hop(1)")
            page.wait_for_timeout(450)
            rails += bool(page.evaluate("!!document.querySelector('#wpal-root .wp-train')"))
            _settle(page, 1500)
        assert rails >= 1 and seen["hand"] == 4
        assert not errors, errors
    finally:
        page.close()


def test_the_chimney_always_points_screen_up_for_every_heading(browser, origin):  # noqa: F811
    """Art 7 Nov: a unit's pose for headings N, NE, E, SE, S, SW, W, NW and between: the chimney (local 9,-15) is always screen-up of the boiler (local 8,1)."""
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(origin + "/index.html")
        page.wait_for_function("window.AltoWorld && AltoWorld.orient", timeout=20000)
        r = page.evaluate("""(() => { var out = [];
          for (var d = 0; d < 360; d += 15) { var o = AltoWorld.orient(d * Math.PI / 180), ro = o[0], fx = o[1], c = Math.cos(ro), s = Math.sin(ro);
            var ch = [fx * 9, -15], bo = [fx * 8, 1], cy = s * ch[0] + c * ch[1], by = s * bo[0] + c * bo[1];
            out.push([d, cy, by, Math.abs(ro) <= Math.PI / 4 + 1e-9, fx]); } return out; })()""")
        for d, cy, by, tilt_ok, fx in r:
            assert cy < by - 5 and cy < 0, (d, cy, by)                       # the chimney stands above the boiler and above the unit's centre
            assert tilt_ok, d
            if d not in (90, 270):
                assert (fx < 0) == (90 < d < 270), (d, fx)                   # mirrored exactly for the westward headings (the due-north/south tie may go either way)
        assert not errors, errors
    finally:
        page.close()


OTHER_EIGHT = {"AUS": 8, "BRA": 25, "CAN": 12, "CHN": 28, "IDN": 30, "IND": 25, "RUS": 70, "ZAF": 9}   # the fewest state shapes each tier must draw


def test_the_other_eight_countries_have_a_projection_and_a_state_tier():
    from alto.build import world_geo as wg
    m = wg.manifest()
    for iso, need in OTHER_EIGHT.items():
        assert iso in m["s"] and iso in m["a1"], iso
        b, ns, _ = loaded(world={"country": iso})
        p = wp.plan(b, ns)
        assert p["country"] == iso and p["proj"]["t"] in ("alb", "lcc", "merc") and p["proj"]["c"], iso
        f = wg.country_projection(iso)
        n, e = f(p["proj"]["c"][0], p["proj"]["c"][1] + 10), f(p["proj"]["c"][0] + 10, p["proj"]["c"][1])
        assert f(*p["proj"]["c"]) == (0.0, 0.0) and n[1] < 0 < e[0] + 1e-9, iso            # north up, east right, the centre at the origin


@pytest.fixture(scope="module")
def origin_eight():
    pages = {}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            iso = path.strip("/").replace(".html", "")
            if iso in OTHER_EIGHT:
                pages.setdefault(iso, built(world={"country": iso})[0])
            hit = (("text/html", pages[iso]) if iso in OTHER_EIGHT else ("text/javascript", "") if path == "/alto-cloud.js" else palace_assets.find(path))
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


@pytest.mark.parametrize("iso", sorted(OTHER_EIGHT))
def test_each_of_the_other_eight_draws_its_states_in_its_own_projection(browser, origin_eight, iso):  # noqa: F811
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(f"{origin_eight}/{iso}.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=30000)
        page.wait_for_function(f"document.querySelectorAll('#wpal-root .wp-s').length >= {OTHER_EIGHT[iso]}", timeout=20000)
        assert page.evaluate("AltoWorld.view().k / AltoWorld.view().kW") > 1.5                    # the country fills the frame
        assert page.evaluate("document.querySelectorAll('#wpal-root .wp-frame').length") == 0     # no insets
        assert not errors, errors
    finally:
        page.close()
