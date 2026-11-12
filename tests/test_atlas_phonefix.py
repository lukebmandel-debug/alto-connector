"""Phone fixes on the one-country Memory Atlas (iPhone Simulator round, 2026-11-11): the rescope dialog hides the unsigned countries, its tiles
hold their text and Build stays on screen; the US inset names stay clear of pins and pins do not stack; the card banner keeps its name whole."""
import pathlib

import pytest

from tests.test_atlas_country import origin, origin_insets  # noqa: F401
from tests.test_world_palace_render import browser, _settle  # noqa: F401

HOME = (pathlib.Path(__file__).resolve().parents[1] / "alto" / "engine" / "home_template.html").as_uri()
PHONE = {"width": 402, "height": 874}
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"


def _dialog(browser):  # noqa: F811
    page = browser.new_page(viewport=PHONE)
    page.goto(HOME)
    page.evaluate("document.getElementById('nt-scrim').classList.add('open'); ntPick('world'); ntScope.scope='country'; ntScopeSync()")
    return page


def test_1a_the_unsigned_countries_are_really_hidden_on_the_phone(browser):  # noqa: F811
    page = _dialog(browser)
    try:
        shown = page.evaluate("[...document.querySelectorAll('#nt-clist .nt-crow')].filter(r => getComputedStyle(r).display !== 'none').map(r => r.dataset.iso)")
        assert shown == ["USA", "AUS", "BRA", "CHN", "IDN", "RUS", "ZAF"]
    finally:
        page.close()


def test_1b_every_mode_tile_holds_its_own_text(browser):  # noqa: F811
    page = _dialog(browser)
    try:
        bad = page.evaluate("""[...document.querySelectorAll('#nt-modal .nt-kinds:not(.nt-sck) .nt-kind')].filter(t => getComputedStyle(t).display !== 'none').map((t, i, all) => {
            var r = t.getBoundingClientRect(), s = t.querySelector('small:not([style*="none"])'), nx = all[i + 1];
            var kids = [...t.querySelectorAll('.nt-t, small')].filter(e => getComputedStyle(e).display !== 'none');
            var over = kids.some(e => e.getBoundingClientRect().bottom > r.bottom + 1);
            return over || (nx && r.bottom > nx.getBoundingClientRect().top + 0.5) ? t.dataset.kind : null; }).filter(Boolean)""")
        assert bad == []
    finally:
        page.close()


def test_1c_build_stays_on_screen_at_44pt_with_the_country_list_open(browser):  # noqa: F811
    page = _dialog(browser)
    try:
        r = page.evaluate("(() => { var b = document.getElementById('nt-make').getBoundingClientRect(); return [b.top, b.bottom, b.height, innerHeight]; })()")
        assert r[2] >= 44 and r[1] <= r[3] and r[0] >= 0, r
        page.evaluate("document.getElementById('nt-modal').scrollTop = 0")
        r = page.evaluate("(() => { var b = document.getElementById('nt-make').getBoundingClientRect(); return [b.top, b.bottom, innerHeight]; })()")
        assert r[1] <= r[2], r                                              # still there with the dialog scrolled to the top
    finally:
        page.close()


def test_2_inset_names_clear_of_pins_and_pins_do_not_stack(browser, origin_insets):  # noqa: F811
    page = browser.new_page(viewport=PHONE)
    try:
        page.goto(origin_insets + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page)
        res = page.evaluate("""(() => {
          var R = e => e.getBoundingClientRect(), hit = (a, b) => a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;
          var pins = [...document.querySelectorAll('#wpal-root .wp-pin')].filter(p => p.style.visibility !== 'hidden' && R(p).width > 0 && R(p).left > -500);
          var labs = [...document.querySelectorAll('#wpal-root .wp-inl')].filter(l => l.style.display !== 'none'), bad = [];
          labs.forEach(l => pins.forEach(p => { if (hit(R(l), R(p))) bad.push(l.textContent + ' x ' + p.getAttribute('aria-label')); }));
          for (var i = 0; i < labs.length; i++) for (var j = i + 1; j < labs.length; j++) if (hit(R(labs[i]), R(labs[j]))) bad.push('labels');
          for (var i = 0; i < pins.length; i++) for (var j = i + 1; j < pins.length; j++) if (hit(R(pins[i]), R(pins[j]))) bad.push(pins[i].textContent + '/' + pins[j].textContent);
          return {n: labs.length, p: pins.length, bad: bad}; })()""")
        assert res["n"] == 2 and res["p"] > 4 and res["bad"] == [], res
    finally:
        page.close()


@pytest.fixture(scope="module")
def origin_world():
    import http.server
    import threading
    from alto.build import palace_assets, world_plan as wp
    from tests.test_world_palace import built
    html = built(world={"places": {"erie": wp.resolve("Brazil")}})[0]

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


def test_3_the_card_banner_name_is_whole_and_the_unit_label_stays_off_it_on_the_phone(browser, origin_world):  # noqa: F811
    page = browser.new_page(viewport=PHONE, is_mobile=True, has_touch=True, device_scale_factor=3, user_agent=IPHONE)
    try:
        page.goto(origin_world + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page)
        page.evaluate("document.querySelectorAll('#node-erie .node-tag').forEach(t => { t.textContent = 'ERIE'; })")
        page.evaluate("AltoWorld.select('erie', {instant: true})")
        _settle(page)
        page.evaluate("document.querySelector('#wpal-root .wp-ban .ban-n').textContent = 'United States'")     # the longest name the banner meets
        r = page.evaluate("""(() => { var n = document.querySelector('#wpal-root .wp-ban .ban-n'); if (!n) return null;
          var b = n.parentNode.getBoundingClientRect(), t = document.querySelector('#wpal-root .wp-enl .node-tag'), tr = t && t.getBoundingClientRect();
          return {txt: n.textContent, w: [n.scrollWidth, n.clientWidth], h: [n.scrollHeight, n.clientHeight], tag: !!tr && tr.bottom > b.top && tr.top < b.bottom && tr.width > 0, tr: tr && [tr.top, tr.bottom], b: [b.top, b.bottom], mob: document.documentElement.classList.contains('mobile')}; })()""")
        assert r and r["w"][0] <= r["w"][1] + 1 and r["h"][0] <= r["h"][1] + 1 and not r["tag"], r
    finally:
        page.close()


# ── round 2 (iPhone Simulator sim1111d, 2026-11-11): every country leg rides the train, the map refits on a turn, the unit label clears the
# banner, the inset names clear the cards' names, a finger's tap on the Tour arrows always steps ──
LAND = {"width": 874, "height": 402}
VPS = [PHONE, LAND]


def _phone(browser, url, vp):  # noqa: F811
    page = browser.new_page(viewport=vp, is_mobile=True, has_touch=True, device_scale_factor=2, user_agent=IPHONE)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "/index.html")
    page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
    _settle(page, 900)
    return page, errors


@pytest.mark.parametrize("vp", VPS, ids=["portrait", "landscape"])
def test_4_every_lower_48_leg_rides_the_train_forward_and_back(browser, origin_insets, vp):  # noqa: F811
    page, errors = _phone(browser, origin_insets, vp)
    try:
        page.evaluate("AltoWorld.tourMode(true)")
        page.evaluate("AltoWorld.select('pj', {instant: true})")
        _settle(page, 700)
        route = ["pj", "pj1", "pj2", "ms", "gj", "sj"]          # California, Los Angeles, San Diego, Nevada, Idaho, Montana: 36..170 px apart on a phone
        missing = []
        for d, legs in ((1, route[1:]), (-1, route[-2::-1])):
            for to in legs:
                page.evaluate(f"AltoWorld.hop({d})")
                page.wait_for_timeout(120)
                rode = page.evaluate("!!document.querySelector('#wpal-root .wp-train') && AltoWorld.plane()")
                if not rode:
                    missing.append((d, to))
                page.keyboard.press("Escape")                    # (straight to the landing)
                _settle(page, 500)
                assert page.evaluate("AltoWorld.view() && document.querySelector('#wpal-root .wp-tour .c').textContent").find(page.evaluate(f"AltoWorld.data.nodes[{to!r}].n")) >= 0
        assert missing == [], missing
        assert not errors, errors
    finally:
        page.close()


def _usbox(page):
    return page.evaluate("""(() => { var b = [1e9, 1e9, -1e9, -1e9];
      [document.querySelector('#wpal-root .wp-sts'), ...document.querySelectorAll('#wpal-root .wp-frame')].forEach(e => { var r = e.getBoundingClientRect(); if (!r.width) return;
        b = [Math.min(b[0], r.left), Math.min(b[1], r.top), Math.max(b[2], r.right), Math.max(b[3], r.bottom)]; });
      var p = document.querySelector('#wpal-root .wp-scope').getBoundingClientRect();
      return {b: b, pill: [p.left, p.top, p.right, p.bottom], v: AltoWorld.view()}; })()""")


@pytest.mark.parametrize("start", [{"width": 874, "height": 250}, PHONE], ids=["late-layout", "turned"])
def test_5_the_country_refits_on_a_turn_or_a_late_landscape_layout_and_clears_the_scope_pill(browser, origin_insets, start):  # noqa: F811
    fresh, _ = _phone(browser, origin_insets, LAND)
    try:
        want = _usbox(fresh)
    finally:
        fresh.close()
    page, errors = _phone(browser, origin_insets, start)
    try:
        page.set_viewport_size(LAND)
        _settle(page, 900)
        got = _usbox(page)
        assert abs(got["v"]["k"] / want["v"]["k"] - 1) < .02, (got["v"], want["v"])        # the same fit as a fresh landscape load
        w = got["b"][2] - got["b"][0]
        assert w > LAND["width"] * .3, got                                                  # not tiny: the US, its insets in, a good part of the screen
        p, b = got["pill"], got["b"]
        assert b[1] >= p[3] - 1 or b[2] <= p[0] or b[0] >= p[2], got                         # nothing of the country under the scope pill
        assert not errors, errors
    finally:
        page.close()


def test_5b_the_world_map_keeps_its_own_resize_rule(browser, origin_world):  # noqa: F811
    page, errors = _phone(browser, origin_world, PHONE)
    try:
        a = page.evaluate("AltoWorld.view()")
        page.set_viewport_size(LAND)
        _settle(page, 900)
        b = page.evaluate("AltoWorld.view()")
        assert abs((b["k"] / a["k"]) / (b["kW"] / a["kW"]) - 1) < .01 and abs(b["cx"] - a["cx"]) < 1e-6, (a, b)
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("vp", VPS + [None], ids=["portrait", "landscape", "desktop"])
def test_6_the_unit_label_sits_clear_of_the_flag_banner_and_its_name(browser, origin_world, vp):  # noqa: F811
    if vp:
        page, errors = _phone(browser, origin_world, vp)
    else:
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.goto(origin_world + "/index.html")
        page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        _settle(page)
    try:
        page.evaluate("AltoWorld.select('hanna', {instant: true})")
        _settle(page)
        r = page.evaluate("""(() => { var R = e => e && e.getBoundingClientRect(), ban = R(document.querySelector('#wpal-root .wp-enl .wp-ban')), u = document.querySelector('#wpal-root .wp-enl .node-unit');
          var ur = u && getComputedStyle(u).display !== 'none' ? R(u) : null, t = R(document.querySelector('#wpal-root .wp-enl .node-title'));
          var hit = (a, b) => !!a && !!b && a.width > 0 && a.left < b.right - .5 && b.left < a.right - .5 && a.top < b.bottom - .5 && b.top < a.bottom - .5;
          return {mob: document.documentElement.classList.contains('mobile'), ban: !!ban, unit: !!ur, overBanner: hit(ur, ban), overTitle: hit(ur, t), txt: u && u.textContent}; })()""")
        assert r["ban"] and not r["overBanner"] and not r["overTitle"], r
        if r["mob"]:
            assert r["unit"], r                         # the phone keeps its unit label (never remove phone UI)
        page.evaluate("AltoWorld.select('erie', {instant: true})")
        _settle(page, 900)
        assert page.evaluate("!!document.querySelector('#world #node-hanna > .node-unit') || !document.documentElement.classList.contains('mobile')")   # given back where it was
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("look", ["classic", "retro", "holo"])
@pytest.mark.parametrize("vp", VPS + [{"width": 1280, "height": 800}], ids=["portrait", "landscape", "desktop"])
def test_7_the_inset_names_clear_the_cards_names_at_fit(browser, origin_insets, vp, look):  # noqa: F811
    page, errors = _phone(browser, origin_insets, vp) if vp["width"] < 1000 else (browser.new_page(viewport=vp), [])
    try:
        if vp["width"] >= 1000:
            page.goto(origin_insets + "/index.html")
            page.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        if look != "classic":
            page.evaluate(f"window._altoStyle && window._altoStyle.set({look!r})")
        _settle(page, 900)
        page.evaluate("window.dispatchEvent(new Event('resize')); AltoWorld.world()")
        _settle(page, 1500)
        bad = page.evaluate("""(() => { var R = e => e.getBoundingClientRect(), hit = (a, b) => a.width > 0 && b.width > 0 && a.left < b.right - .5 && b.left < a.right - .5 && a.top < b.bottom - .5 && b.top < a.bottom - .5;
          var ins = [...document.querySelectorAll('#wpal-root .wp-inl')].filter(l => l.style.display !== 'none' && !l.classList.contains('wp-off'));
          var names = [...document.querySelectorAll('#wpal-root .wp-lbl')].filter(l => !l.classList.contains('wp-stn') && !l.classList.contains('wp-off') && getComputedStyle(l).display !== 'none');
          var out = []; ins.forEach(i => names.forEach(n => { if (hit(R(i), R(n))) out.push(i.textContent + ' x ' + n.textContent); })); return {n: ins.length, bad: out}; })()""")
        assert bad["n"] == 2 and bad["bad"] == [], bad
        assert not errors, errors
    finally:
        page.close()


def test_8_a_fingers_tap_on_the_tour_arrows_always_steps_once(browser, origin_insets):  # noqa: F811
    page, errors = _phone(browser, origin_insets, PHONE)
    try:
        page.evaluate("AltoWorld.tourMode(true)")
        page.evaluate("AltoWorld.select('ms', {instant: true})")
        _settle(page, 3600)                               # (a pause: the phone layer has gone idle)
        cur = "document.querySelector('#wpal-root .wp-tour .c').textContent"
        a = page.evaluate(cur)
        # a tap whose click iOS drops: only touchstart + touchend reach the page
        page.evaluate("""(() => { var b = document.querySelector('#wpal-root .wp-tour button[aria-label="Next stop"]'), r = b.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
          var t = {identifier: 1, target: b, clientX: x, clientY: y}, ev = (k, on, ch) => { var e = new Event(k, {bubbles: true, cancelable: true});
            Object.defineProperty(e, 'touches', {value: on}); Object.defineProperty(e, 'changedTouches', {value: ch}); b.dispatchEvent(e); };   // (WebKit has no Touch constructor)
          ev('touchstart', [t], [t]); ev('touchend', [], [t]); })()""")
        page.keyboard.press("Escape")
        _settle(page, 700)
        b = page.evaluate(cur)
        assert "Idaho" in b and a != b, (a, b)
        # a real tap (touch, then the click the browser makes of it) steps one stop, not two
        box = page.locator('#wpal-root .wp-tour button[aria-label="Previous stop"]').bounding_box()
        page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(200)
        page.keyboard.press("Escape")
        _settle(page, 700)
        assert "Nevada" in page.evaluate(cur), page.evaluate(cur)
        assert not errors, errors
    finally:
        page.close()


# ── round 3 (sim1111f, a ?dbg=1 overlay in the real iPhone 18 Pro Simulator): Mobile Safari's own landscape box is 874 x 292 css px (its toolbar and tab
# strip in), its portrait box 402 x 714, not the bare 874 x 402 / 402 x 874 the earlier tests used. At 874 x 292 the fixed bands (pill + 8 at the top, 96 px
# at the foot, 12 px pad) left the US a 72 px slot: k 0.43, the US ~120 px wide, the pins pushed into a column. At 402 x 714 all three old spots for the ALASKA
# name hit something and the first (over pin 1.1-3) was kept. ──
SAFARI_L = {"width": 874, "height": 292}
SAFARI_P = {"width": 402, "height": 714}


@pytest.mark.parametrize("start", [SAFARI_L, SAFARI_P], ids=["fresh", "turned"])
def test_9_in_safaris_real_landscape_box_the_country_is_big_and_clear_of_the_pill_and_tour_strip(browser, origin_insets, start):  # noqa: F811
    page, errors = _phone(browser, origin_insets, start)
    try:
        if start is not SAFARI_L:
            page.set_viewport_size(SAFARI_L)
            _settle(page, 1600)
        got = _usbox(page)
        b = got["b"]
        assert b[2] - b[0] > SAFARI_L["width"] * .28, got                               # (was ~14%)
        rects = page.evaluate("""[...document.querySelectorAll('#wpal-root .wp-scope, #wpal-root .wp-tour')].filter(e => !e.hidden).map(e => { var r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })""")
        assert len(rects) == 2, rects
        for r in rects:
            assert b[1] >= r[3] - 1 or b[3] <= r[1] + 1 or b[2] <= r[0] + 1 or b[0] >= r[2] - 1, (got, r)   # no part of the country under a panel
        top = page.evaluate("document.getElementById('title-bar') ? document.getElementById('title-bar').getBoundingClientRect().bottom : 0")
        assert b[1] >= top - 1, (got, top)
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("vp", [SAFARI_P, SAFARI_L], ids=["portrait", "landscape"])
def test_10_in_safaris_real_boxes_the_inset_names_clear_pins_card_names_and_each_other(browser, origin_insets, vp):  # noqa: F811
    page, errors = _phone(browser, origin_insets, vp)
    try:
        _settle(page, 900)
        res = page.evaluate("""(() => {
          var R = e => e.getBoundingClientRect(), hit = (a, b) => a.width > 0 && b.width > 0 && a.left < b.right - .5 && b.left < a.right - .5 && a.top < b.bottom - .5 && b.top < a.bottom - .5;
          var pins = [...document.querySelectorAll('#wpal-root .wp-pin')].filter(p => p.style.visibility !== 'hidden' && R(p).width > 0 && R(p).left > -500);
          var ins = [...document.querySelectorAll('#wpal-root .wp-inl')].filter(l => l.style.display !== 'none' && !l.classList.contains('wp-off'));
          var names = [...document.querySelectorAll('#wpal-root .wp-lbl')].filter(l => !l.classList.contains('wp-stn') && !l.classList.contains('wp-off') && getComputedStyle(l).display !== 'none');
          var bars = [...document.querySelectorAll('#wpal-root .wp-scope, #wpal-root .wp-tour')].filter(e => !e.hidden), bad = [];
          ins.forEach(l => { pins.forEach(p => { if (hit(R(l), R(p))) bad.push(l.textContent + ' x pin ' + p.textContent); });
                             names.forEach(n => { if (hit(R(l), R(n))) bad.push(l.textContent + ' x name ' + n.textContent); });
                             bars.forEach(b => { if (hit(R(l), R(b))) bad.push(l.textContent + ' x ' + b.className); });
                             var r = R(l); if (r.left < 0 || r.right > innerWidth || r.bottom > innerHeight) bad.push(l.textContent + ' off screen'); });
          if (ins.length === 2 && hit(R(ins[0]), R(ins[1]))) bad.push('the two names');
          return {n: ins.length, bad: bad}; })()""")
        assert res["n"] == 2 and res["bad"] == [], res
        assert not errors, errors
    finally:
        page.close()


# ── round 4 (sim1111g E8 + E4, Fable seat): the round-3 test only asked for 28% of the width, and passed on the map the Simulator failed. In Safari's real
# landscape box the Tour strip is now a fixed two-row block in a left column under the scope pill, the country takes the box's whole height beside it, a
# state's only card slides to the middle of its state while its capital is crowded (Nevada's on Carson City beside Sacramento sent a column of pins down the
# Pacific), and the Tour's arrows keep their place from stop to stop (a content-sized strip moved them under the finger, onto the End button) ──
_E8 = """(() => { var R = e => { var r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  var v = AltoWorld.view(), root = document.getElementById('wpal-root'), rr = root.getBoundingClientRect(), vw = root.clientWidth, vh = root.clientHeight;
  var sts = [...document.querySelectorAll('#wpal-root .wp-sts path.wp-s')], names = [...document.querySelectorAll('#wpal-root .wp-lbl.wp-stn:not(.wp-inl)')].map(e => e.textContent);
  var svg = sts[0].ownerSVGElement, at = (x, y) => { for (var i = 0; i < sts.length; i++) { var b = sts[i].getBoundingClientRect(); if (x < b.left || x > b.right || y < b.top || y > b.bottom) continue;
    var p = svg.createSVGPoint(); p.x = x; p.y = y; if (sts[i].isPointInFill(p.matrixTransform(sts[i].getScreenCTM().inverse()))) return i; } return -1; };
  var nodes = AltoWorld.data.nodes, ids = Object.keys(nodes).filter(id => nodes[id].x != null), pins = [...document.querySelectorAll('#wpal-root .wp-pin')], out = {};
  ids.forEach((id, i) => { var n = nodes[id], r = pins[i].getBoundingClientRect(), home = at((n.x - v.cx) * v.k + vw / 2 + rr.left, (n.y - v.cy) * v.k + vh / 2 + rr.top);
    out[pins[i].textContent.trim()] = {pin: [(r.left + r.right) / 2, (r.top + r.bottom) / 2], box: [r.left, r.top, r.right, r.bottom], home: names[home] || null, hb: home >= 0 ? R(sts[home]) : null,
      on: home >= 0 && at((r.left + r.right) / 2, (r.top + r.bottom) / 2) === home}; });
  var b = [1e9, 1e9, -1e9, -1e9]; [document.querySelector('#wpal-root .wp-sts'), ...document.querySelectorAll('#wpal-root .wp-frame')].forEach(e => { var r = e.getBoundingClientRect(); if (!r.width) return;
    b = [Math.min(b[0], r.left), Math.min(b[1], r.top), Math.max(b[2], r.right), Math.max(b[3], r.bottom)]; });
  var tb = document.getElementById('title-bar');
  return {us: b, pins: out, frames: [...document.querySelectorAll('#wpal-root .wp-frame')].map(R), pill: R(document.querySelector('#wpal-root .wp-scope')), tour: R(document.querySelector('#wpal-root .wp-tour')),
    top: tb ? tb.getBoundingClientRect().bottom : 0, inl: [...document.querySelectorAll('#wpal-root .wp-inl')].map(R)}; })()"""


def _turn_like_safari(page):
    """sim1111f: orientationchange reports the old size; the resizes arrive at +78 ms (874 x 372) and +418 ms (874 x 292)."""
    page.evaluate("window.dispatchEvent(new Event('orientationchange'))")
    page.wait_for_timeout(78)
    page.set_viewport_size({"width": 874, "height": 372})
    page.wait_for_timeout(340)
    page.set_viewport_size(SAFARI_L)
    _settle(page, 1800)


@pytest.mark.parametrize("start", [SAFARI_L, SAFARI_P], ids=["fresh", "turned"])
def test_11_safari_landscape_the_country_fills_the_box_and_every_pin_sits_on_its_state(browser, origin_insets, start):  # noqa: F811
    page, errors = _phone(browser, origin_insets, start)
    try:
        if start is not SAFARI_L:
            _turn_like_safari(page)
        got = page.evaluate(_E8)
        b, W, H = got["us"], SAFARI_L["width"], SAFARI_L["height"]
        got["top"] = got["top"] or 52                                                       # (the title bar: 52 px where the test page has none measured)
        assert b[2] - b[0] >= W * .40, got["us"]                                           # (the failed map: 258 px = 29.5%)
        assert b[3] - b[1] >= (H - got["top"]) * .88, (got["us"], got["top"])              # the box's height is what limits a wide country: it takes nearly all of it (was 62%)
        assert b[1] >= got["top"] - 1 and b[3] <= H and b[0] >= 0 and b[2] <= W, got["us"]
        for r in (got["pill"], got["tour"]):
            assert b[2] <= r[0] + 1 or b[0] >= r[2] - 1 or b[1] >= r[3] - 1 or b[3] <= r[1] + 1, (got["us"], r)    # no part of the country under the pill or the Tour block
        assert got["pill"][0] < 80 and got["pill"][1] < got["top"] + 12, got["pill"]       # the pill: top left
        P = got["pins"]
        for k in ("1.1-1", "1.1-2", "1.1-3", "1.1-4", "1.1-5", "1.1-6", "2.3"):             # the lower 48: each pin's centre on its own state (6 px for a coast city: San Diego)
            p, hb = P[k]["pin"], P[k]["hb"]
            assert hb and hb[0] - 6 <= p[0] <= hb[2] + 6 and hb[1] - 6 <= p[1] <= hb[3] + 6, (k, P[k])
        assert P["1.1-4"]["home"] == "Nevada" and P["1.1-4"]["on"], P["1.1-4"]              # Nevada's card inside Nevada, not on California's coast
        assert P["1.1-1"]["on"] and P["1.1-5"]["on"] and P["1.1-6"]["on"], P                # California's, Idaho's and Montana's inside their states
        xs = [P[k]["pin"][0] for k in ("1.1-1", "1.1-2", "1.1-3", "1.1-4", "1.1-5", "1.1-6")]
        assert max(xs) - min(xs) > 70, xs                                                   # not a column (it was 48 px wide and 117 tall)
        fr = [min(f[0] for f in got["frames"]), min(f[1] for f in got["frames"]), max(f[2] for f in got["frames"]), max(f[3] for f in got["frames"])]
        for k in ("2.1", "2.1-1", "2.2"):                                                   # Alaska's and Hawaii's pins stay in their frames
            p = P[k]["pin"]
            assert fr[0] - 4 <= p[0] <= fr[2] + 4 and fr[1] - 4 <= p[1] <= fr[3] + 4, (k, p, fr)
        boxes = [P[k]["box"] for k in P]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, c = boxes[i], boxes[j]
                assert not (a[0] < c[2] - 1 and c[0] < a[2] - 1 and a[1] < c[3] - 1 and c[1] < a[3] - 1), (a, c)   # and no pin on another
        for r in got["inl"]:
            assert r[0] >= 0 and r[2] <= W and r[3] <= H, got["inl"]                        # ALASKA / HAWAII whole on the screen
        fresh = getattr(test_11_safari_landscape_the_country_fills_the_box_and_every_pin_sits_on_its_state, "_fresh", None)
        if start is SAFARI_L:
            test_11_safari_landscape_the_country_fills_the_box_and_every_pin_sits_on_its_state._fresh = got["us"]
        elif fresh:
            assert all(abs(x - y) < 2 for x, y in zip(fresh, got["us"])), (fresh, got["us"])   # after a turn == a fresh landscape load
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("vp", [SAFARI_P, SAFARI_L], ids=["portrait", "landscape"])
def test_12_the_tours_arrows_keep_their_place_and_step_every_stop_by_finger(browser, origin_insets, vp):  # noqa: F811
    page, errors = _phone(browser, origin_insets, vp)
    try:
        page.evaluate("AltoWorld.tourMode(true)")
        _settle(page, 600)
        spot = """(l) => { var b = document.querySelector('#wpal-root .wp-tour button[aria-label="' + l + '"]'), r = b.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, e = document.elementFromPoint(x, y);
          return {x: x, y: y, free: e === b || b.contains(e), cur: document.querySelector('#wpal-root .wp-tour .c').textContent}; }"""
        n0, x0 = page.evaluate(spot, "Next stop"), page.evaluate(spot, "End the Tour")
        assert x0["x"] - n0["x"] >= 44, (n0, x0)                                           # the End button a finger's width from the next arrow
        seen = []
        for step in range(11):                                                              # every tap at the SAME spot, as a finger does
            now = page.evaluate(spot, "Next stop")
            assert abs(now["x"] - n0["x"]) < 1 and abs(now["y"] - n0["y"]) < 1 and now["free"], (step, n0, now)   # the arrow has not moved and no card covers it
            page.touchscreen.tap(n0["x"], n0["y"])
            _settle(page, 2600)
            seen.append(page.evaluate(spot, "Next stop")["cur"])
            card = page.evaluate("""(() => { var c = document.querySelector('#wpal-root .wp-enl'); if (!c) return null; var r = c.getBoundingClientRect(), k = c.querySelector('.node-card'), q = k ? k.getBoundingClientRect() : r,
              t = document.querySelector('#wpal-root .wp-tour').getBoundingClientRect(), u = c.querySelector('.node-unit'), ub = u && u.getBoundingClientRect(), bn = c.querySelector('.wp-ban'), bb = bn && bn.getBoundingClientRect();
              return {r: [q.left, q.top, q.right, q.bottom], hitsTour: q.left < t.right && q.right > t.left && q.top < t.bottom && q.bottom > t.top,
                unitIn: !ub || !ub.width || (ub.top >= q.top - 1 && ub.bottom <= q.bottom + 1), unitOffBanner: !ub || !bb || !ub.width || ub.top >= bb.bottom - 1 || ub.bottom <= bb.top + 1}; })()""")
            assert card, (step, seen)                                                       # every stop opens its card (the hub's threw on a landscape phone: a negative scale)
            assert not card["hitsTour"] and card["r"][0] >= -1 and card["r"][2] <= vp["width"] + 1, (step, card)
            assert card["unitIn"] and card["unitOffBanner"], (step, card)                   # the unit label inside the card, off the flag banner
        assert [s.split("·")[0].strip() for s in seen] == ["Tour %d / 11" % (i % 11 + 1) for i in range(1, 12)], seen   # (turning the Tour on opened stop 1: eleven taps go round to it)
        p0 = page.evaluate(spot, "Previous stop")
        for step in range(3):
            page.touchscreen.tap(p0["x"], p0["y"])
            _settle(page, 2600)
        assert page.evaluate(spot, "Previous stop")["cur"].startswith("Tour 9 / 11"), page.evaluate(spot, "Previous stop")
        assert abs(page.evaluate(spot, "Previous stop")["x"] - p0["x"]) < 1
        assert not errors, errors
    finally:
        page.close()


def test_13_three_quick_taps_on_one_spot_step_three_stops_and_never_end_the_tour(browser, origin_insets):  # noqa: F811
    page, errors = _phone(browser, origin_insets, SAFARI_P)
    try:
        page.evaluate("AltoWorld.tourMode(true)")
        _settle(page, 600)
        box = page.locator('#wpal-root .wp-tour button[aria-label="Next stop"]').bounding_box()
        for _ in range(3):                                                                  # (sim1111g E4: the strip grew at the first tap, the arrow left the finger and the Tour was gone)
            page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(120)
        _settle(page, 3200)
        assert page.evaluate("AltoWorld.tourMode()") is True
        assert not page.evaluate("document.querySelector('#wpal-root .wp-tour').hidden")
        cur = page.evaluate("document.querySelector('#wpal-root .wp-tour .c').textContent")
        assert cur.startswith("Tour 4 / 11"), cur                                          # (turning the Tour on opens stop 1; three taps, three stops)
        assert not errors, errors
    finally:
        page.close()
