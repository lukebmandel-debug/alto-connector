"""Mind Palace on a phone (palace_mobile.py) and Directions (palace_directions.py): the Apple-Maps-style map page.

Runs on test_palace_transit's little city (a real-looking pair of lines over the grid). Static checks first; the browser
tests drive a 390x844 touch phone with real touch events (CDP), and a desktop window for the Directions panel.
Offline; skipped without Playwright's browsers; nothing here touches the network or any ALTO_* setting."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace, palace_directions, palace_mobile  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
import test_palace_transit as tt  # noqa: E402

PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.5 Mobile/15E148 Safari/604.1")


@pytest.fixture(scope="module")
def html():
    out, _ = build_timeline(*load_brief(copy.deepcopy(tt._bundle())))
    return out


# ── what the page carries ───────────────────────────────────────────────────
def test_the_pieces_are_in_the_page(html):
    for s in ("pm-sheet", "pm-grab", "function pmSnap", "function pmGestures", "function pmSelect", "window._palDir=", "window._palTRx=",
              "pal-dr-banner", "Choose start", "Choose destination", "window._palDirMount(c)", "pal-dir-btn", "function mmapOpen"):
        assert s in html, s
    assert "function mmapOpen" in palace_mobile.MOBILE_JS and "function mmapOpen" not in palace.PALACE_JS.replace(palace_mobile.MOBILE_JS, "")


def test_the_planner_reuses_the_transit_graph_and_its_costs():
    js = palace_directions.DIR_JS
    assert "window._palTRx" in js and "TX.dijk(" in js and "route(A.node" in js            # transit + walk-only alternative
    from alto.build import palace_transit_js as pj
    assert "var WALK=1, RIDE=.2, BOARD=120, XFER=70;" in pj.TRANSIT_JS and "window._palTRx=" in pj.TRANSIT_JS


def test_the_phone_map_asks_for_nothing_the_page_would_scroll():
    css = palace_mobile.MOBILE_CSS
    assert "touch-action:none" in css and "overscroll-behavior" in css and "env(safe-area-inset-bottom" in css and "env(safe-area-inset-top" in css
    assert "backdrop-filter:blur(18px) saturate(190%)" in css                                   # the desktop buttons' glass


# ── in a browser ────────────────────────────────────────────────────────────
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


@pytest.fixture(scope="module")
def page_file(tmp_path_factory, html):
    f = tmp_path_factory.mktemp("palmob") / "page.html"
    f.write_text(html, encoding="utf-8")
    return f


class Phone:
    def __init__(self, browser, f, dark=False):
        self.ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                       user_agent=PHONE_UA, color_scheme="dark" if dark else "light")
        self.pg = self.ctx.new_page()
        self.errs = []
        self.pg.on("pageerror", lambda e: self.errs.append(str(e)))
        self.pg.goto(f.as_uri())
        self.pg.wait_for_timeout(1800)
        assert self.pg.evaluate("document.documentElement.classList.contains('mobile')")
        self.cdp = self.ctx.new_cdp_session(self.pg)
        self.pg.evaluate("document.getElementById('minimap-toggle').click()")
        self.pg.wait_for_timeout(700)

    def pm(self):
        return self.pg.evaluate("(() => { const p = window._palMob.PM(); return {det: p.det, sh: p.sh, mode: p.mode, z: p.z, H: p.H}; })()")

    def drag(self, x, y0, y1, steps=14, dt=16, hold=True):
        c = self.cdp
        c.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
        for i in range(1, steps + 1):
            c.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 + (y1 - y0) * i / steps}]})
            self.pg.wait_for_timeout(dt)
        c.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        self.pg.wait_for_timeout(900)

    def centre(self, sel):
        return self.pg.evaluate("""s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect();
          return [r.x + r.width / 2, r.y + r.height / 2, r.width, r.height]; }""", sel)

    def tap(self, sel):
        c = self.centre(sel)
        assert c, sel
        self.pg.touchscreen.tap(c[0], c[1])
        self.pg.wait_for_timeout(450)

    def tap_building(self, id_):
        """Fly the map so the building sits in the open part of the map, then tap it for real."""
        self.pg.evaluate("""id => { const P = window._ALTO_PALACE, k = P.at[id], b = P.b[+k.split('.')[0]], L = b[+(k.split('.')[1] || 0)];
          window._palMob.goto(L[0], L[1], 1.2); }""", id_)
        self.pg.wait_for_timeout(900)
        c = self.centre('#palace-svg-m .pl-bld[data-id="%s"]' % id_)
        assert c and 0 < c[0] < 390 and 0 < c[1] < 844 * .5, c
        self.pg.touchscreen.tap(c[0], c[1])
        self.pg.wait_for_timeout(700)


@pytest.fixture()
def phone(browser, page_file):
    ph = Phone(browser, page_file)
    yield ph
    assert ph.errs == [], ph.errs
    ph.ctx.close()


def test_the_sheet_snaps_to_three_heights_under_real_touch_drags(phone):
    assert phone.pm()["det"] == "peek" and abs(phone.pm()["sh"] - 82) < 2
    # a search field shows at the peek, over a full-bleed map
    q = phone.centre("#pal-mmap .pm-q")
    assert q and q[1] > 844 - 82 and q[3] >= 40
    top = phone.pg.evaluate("document.getElementById('pal-mmap').getBoundingClientRect().top")
    assert top == 0
    phone.drag(195, 844 - 70, 844 * .5)                                   # a slow drag from the handle to the middle
    s = phone.pm()
    assert s["det"] == "half" and abs(s["sh"] - 844 * .46) < 3, s
    phone.drag(195, 844 * .54 + 12, 140, steps=5, dt=8)                   # a quick flick up
    s = phone.pm()
    assert s["det"] == "full" and s["sh"] > 844 * .8, s
    phone.drag(195, 844 - s["sh"] + 14, 600, steps=10, dt=14)             # down on the header: not past half
    assert phone.pm()["det"] in ("half", "peek")
    phone.drag(195, 844 - phone.pm()["sh"] + 14, 844 - 20, steps=6, dt=8)  # a flick down: the peek
    assert phone.pm()["det"] == "peek"


def test_the_controls_are_thumb_sized_and_sit_above_the_sheet(phone):
    for r in phone.pg.evaluate("[...document.querySelectorAll('#pal-mmap .pm-zoom button, #pal-mmap .pm-close, #pal-mmap .pm-btn')].map(e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; })"):
        assert min(r) >= 43, r
    z = phone.centre("#pal-mmap .pm-zoom")
    sheet_top = phone.pg.evaluate("document.querySelector('#pal-mmap .pm-sheet').getBoundingClientRect().top")
    assert z[1] + z[3] / 2 < sheet_top + 1                                   # the zoom column rides on top of the sheet
    phone.drag(195, 844 - 60, 844 * .5)
    z2 = phone.centre("#pal-mmap .pm-zoom")
    assert z2[1] < z[1] - 100                                                  # and rises with it


def test_one_finger_pans_with_momentum_and_two_fingers_pinch_around_themselves(phone):
    y0 = phone.pg.evaluate("window.scrollY")
    phone.pg.evaluate("(() => { const m = window._ALTO_PALACE.m; window._palMob.goto(m.W / 2, m.H / 2, 2.0); })()")
    phone.pg.wait_for_timeout(200)
    p0 = phone.pg.evaluate("(() => { const p = window._palMob.PM(); return [p.sx, p.sy, p.z]; })()")
    phone.drag(195, 500, 400, steps=6, dt=8)                                # 100px of finger, quickly
    p1 = phone.pg.evaluate("(() => { const p = window._palMob.PM(); return [p.sx, p.sy, p.z]; })()")
    assert p1[1] - p0[1] > 115                                                 # the map followed the finger, and coasted past it
    phone.pg.evaluate("(() => { const m = window._ALTO_PALACE.m; window._palMob.goto(m.W / 2, m.H / 2, 0.9); })()")
    phone.pg.wait_for_timeout(200)
    p1 = phone.pg.evaluate("(() => { const p = window._palMob.PM(); return [p.sx, p.sy, p.z]; })()")
    c = phone.cdp
    pts = lambda a, b: {"type": "touchMove", "touchPoints": [{"x": 195 - a, "y": 400}, {"x": 195 + a, "y": 400}]}
    c.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 175, "y": 400}, {"x": 215, "y": 400}]})
    for a in range(20, 100, 8):
        c.send("Input.dispatchTouchEvent", pts(a, 0))
        phone.pg.wait_for_timeout(16)
    c.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    phone.pg.wait_for_timeout(500)
    p2 = phone.pg.evaluate("(() => { const p = window._palMob.PM(); return [p.sx, p.sy, p.z]; })()")
    assert p2[2] > p1[2] * 1.5, (p1, p2)
    # the pinch kept the point between the fingers in place: the committed size matches the zoom
    assert abs(float(phone.pg.evaluate("document.getElementById('palace-svg-m').getAttribute('width')")) / phone.pg.evaluate("window._ALTO_PALACE.m.W + 180") - p2[2]) < .02
    assert phone.pg.evaluate("window.scrollY") == y0                           # the page behind never scrolled


def test_double_tap_zooms_in_and_a_two_finger_tap_zooms_out(phone):
    z0 = phone.pm()["z"]
    phone.pg.touchscreen.tap(195, 300)
    phone.pg.wait_for_timeout(120)
    phone.pg.touchscreen.tap(195, 300)
    phone.pg.wait_for_timeout(700)
    z1 = phone.pm()["z"]
    assert z1 > z0 * 1.6
    c = phone.cdp
    c.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 160, "y": 300}, {"x": 230, "y": 300}]})
    phone.pg.wait_for_timeout(60)
    c.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    phone.pg.wait_for_timeout(700)
    assert phone.pm()["z"] < z1 * .7


def test_search_finds_a_building_by_name_number_and_station(phone):
    phone.tap("#pal-mmap .pm-q")
    assert phone.pm()["det"] == "full"                                         # the sheet rises for typing
    phone.pg.keyboard.type("gamm")
    phone.pg.wait_for_timeout(300)
    rows = phone.pg.evaluate("[...document.querySelectorAll('#pal-mmap .pm-list li')].map(e => e.textContent)")
    assert rows and "GAMMA" in rows[0]
    phone.pg.fill("#pal-mmap .pm-q", "city hall")                              # a station
    phone.pg.wait_for_timeout(300)
    assert "City Hall" in phone.pg.evaluate("document.querySelector('#pal-mmap .pm-list li').textContent")
    phone.pg.fill("#pal-mmap .pm-q", "1.1")                                    # a number
    phone.pg.wait_for_timeout(300)
    assert phone.pg.evaluate("document.querySelector('#pal-mmap .pm-list li .pm-bd').textContent") == "1.1"
    phone.tap("#pal-mmap .pm-list li")
    s = phone.pm()
    assert s["mode"] == "place" and s["det"] in ("half", "full")


def test_tapping_a_building_opens_its_place_card_and_open_goes_inside(phone):
    phone.tap_building("gamma")
    assert phone.pm()["mode"] == "place" and phone.pm()["det"] == "half"
    head = phone.pg.evaluate("document.querySelector('#pal-mmap .pm-head').textContent")
    assert "GAMMA" in head
    card = phone.pg.evaluate("document.querySelector('#pal-mmap .pm-card').textContent")
    for s in ("Directions", "Open", "Share", "Nearest corner", "Floors", "Neighbourhood"):
        assert s in card, s
    assert phone.pg.evaluate("document.querySelector('#palace-svg-m .pl-bld.pm-sel, #palace-svg-m .pl-bld.pal-hot') !== null")   # lit on the map
    for r in phone.pg.evaluate("[...document.querySelectorAll('#pal-mmap .pm-act')].map(e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; })"):
        assert min(r) >= 44
    # normal viewing: Open goes inside, as the old Go inside did
    phone.tap("#pal-mmap .pm-act[data-a=open]")
    phone.pg.wait_for_timeout(900)
    assert phone.pg.evaluate("document.documentElement.classList.contains('detail-open')")
    assert not phone.pg.evaluate("document.getElementById('pal-mmap').classList.contains('on')")


def test_tapping_empty_map_closes_the_card(phone):
    phone.tap_building("gamma")
    assert phone.pm()["mode"] == "place"
    phone.tap("#pal-mmap .pm-btn.ghost")                                       # the card's close
    assert phone.pm()["mode"] == "home" and phone.pm()["det"] == "peek"


def _stepsets(phone):
    return phone.pg.evaluate("[...document.querySelectorAll('#pal-mmap .dr-st li')].map(e => e.textContent)")


def test_directions_plan_a_route_between_two_buildings_and_draw_it(phone):
    phone.tap("#pal-mmap .pm-btn[data-a=dir]")
    st = phone.pg.evaluate("(() => { const s = window._palDir.state(); return [s.on, s.focus]; })()")
    assert st == [True, "from"]
    assert phone.pg.evaluate("document.getElementById('pal-dr-banner').classList.contains('on')")
    assert "Choose start" in phone.pg.evaluate("document.getElementById('pal-dr-banner').textContent")
    # choose the start by search
    phone.tap(".dr-f.from input")
    phone.pg.keyboard.type("west")
    phone.pg.wait_for_timeout(300)
    phone.tap(".dr-sg li")
    assert phone.pg.evaluate("window._palDir.state().from.name") == "West"
    assert "Choose destination" in phone.pg.evaluate("document.getElementById('pal-dr-banner').textContent")
    # choose the destination by tapping a building on the map: inside Directions it picks, it does not open a card
    phone.pg.evaluate("""() => { const P = window._ALTO_PALACE, k = P.at['eps'], L = P.b[+k.split('.')[0]][+(k.split('.')[1] || 0)]; window._palMob.goto(L[0], L[1], 1.0); }""")
    phone.pg.wait_for_timeout(900)
    c = phone.centre('#palace-svg-m .pl-bld[data-id="eps"]')
    phone.pg.touchscreen.tap(c[0], c[1])
    phone.pg.wait_for_timeout(900)
    s = phone.pg.evaluate("(() => { const s = window._palDir.state(); return {to: s.to && s.to.name, n: s.plans && s.plans.length, mode: window._palMob.PM().mode}; })()")
    assert s["to"] == "EPS" and s["n"] and s["mode"] == "dir", s
    steps = _stepsets(phone)
    assert len(steps) >= 3 and steps[0].startswith("Start at") and steps[-1].startswith("Arrive at"), steps
    assert any(t.startswith("Walk") for t in steps)
    summary = phone.pg.evaluate("document.querySelector('#pal-mmap .dr-sum').textContent")
    assert "min" in summary
    # the route is on the map: dashed walk legs, line-coloured ride legs, a dot at each stop
    n = phone.pg.evaluate("[document.querySelectorAll('#palace-svg-m .pl-dir .dr-walk').length, document.querySelectorAll('#palace-svg-m .pl-dir .dr-ride').length, document.querySelectorAll('#palace-svg-m .pl-dir .dr-mk').length]")
    assert n[0] + n[1] >= 1 and n[2] >= 3
    # tapping a step flies the map to it; Start walks through the route; swap reverses it
    phone.tap(".dr-st li:nth-child(2)")
    assert phone.pg.evaluate("window._palDir.state().step") == 1
    phone.pg.wait_for_timeout(700)
    phone.tap(".dr-go")
    assert phone.pg.evaluate("window._palDir.state().nav") == 0 and phone.pm()["mode"] == "nav" and phone.pm()["det"] == "peek"
    phone.tap(".dr-nb[data-n='1']")
    assert phone.pg.evaluate("window._palDir.state().nav") == 1
    phone.tap(".dr-nb.end")
    assert phone.pg.evaluate("window._palDir.state().nav") is None and phone.pm()["mode"] == "dir"
    a = phone.pg.evaluate("window._palDir.state().from.name")
    phone.tap(".dr-sw")
    assert phone.pg.evaluate("window._palDir.state().to.name") == a
    phone.tap("#pal-dr-banner button") if phone.pg.evaluate("document.getElementById('pal-dr-banner').classList.contains('on')") else None
    phone.pg.evaluate("window._palDir.close()")
    assert phone.pm()["mode"] == "home"
    assert phone.pg.evaluate("document.querySelectorAll('#palace-svg-m .pl-dir .dr-walk, #palace-svg-m .pl-dir .dr-ride').length") == 0


def test_the_planner_offers_the_real_line_with_boarding_riding_and_getting_off_steps(phone):
    r = phone.pg.evaluate("""() => { const D = window._palDir, all = D.index(), w = all.filter(p => p.k === 's' && p.name === 'West')[0],
        e = all.filter(p => p.k === 's' && p.name === 'East')[0], plans = D.plan(w, e);
      return plans && plans.map(o => ({kind: o.kind, min: o.min, rides: o.rides, steps: o.steps.map(s => s.text)})); }""")
    tr = [o for o in r if o["kind"] == "transit"]
    assert tr and tr[0]["rides"] >= 1, r
    t = tr[0]["steps"]
    assert any(s.startswith("Board Market") and " at " in s for s in t), t
    assert any(s.startswith("Ride ") and "stop" in s for s in t) and any(s.startswith("Get off at") for s in t)
    assert {o["kind"] for o in r} == {"transit", "walk"}                                   # walking is the alternative


def test_a_search_for_a_street_or_a_number_finds_it_too(phone):
    r = phone.pg.evaluate("window._palDir.search('2.1', 5).map(p => p.num + '|' + p.name)")
    assert r and r[0].startswith("2.1|")
    assert phone.pg.evaluate("window._palDir.search('zzzz', 5).length") == 0


def test_the_phone_map_still_has_its_old_controls(phone):
    assert phone.pg.evaluate("[...document.querySelectorAll('#pal-mmap .pm-zoom button')].map(e => e.getAttribute('data-z'))") == ["in", "out", "fit"]
    z0 = phone.pm()["z"]
    phone.tap("#pal-mmap [data-z=in]")
    phone.pg.wait_for_timeout(600)
    assert phone.pm()["z"] > z0 * 1.4
    phone.tap("#pal-mmap [data-z=fit]")
    phone.pg.wait_for_timeout(900)
    assert phone.pm()["z"] < z0
    phone.tap("#pal-mmap .pm-close")
    assert not phone.pg.evaluate("document.getElementById('pal-mmap').classList.contains('on')")
    assert not phone.pg.evaluate("document.documentElement.classList.contains('pm-open')")


def test_the_phone_map_works_in_the_dark_too(browser, page_file):
    ph = Phone(browser, page_file, dark=True)
    ph.pg.evaluate("document.documentElement.classList.add('dark')")
    ph.tap_building("gamma")
    assert ph.pm()["mode"] == "place"
    assert ph.errs == []
    ph.ctx.close()


# ── the desktop ─────────────────────────────────────────────────────────────
@pytest.fixture()
def desk(browser, page_file):
    pg = browser.new_context(viewport={"width": 1500, "height": 900}).new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(page_file.as_uri())
    pg.wait_for_timeout(1800)
    yield pg
    assert pg.errs == [], pg.errs


def _node_centre(pg, id_):
    return pg.evaluate("""id => { const c = document.querySelector('#node-' + id + ' .node-card'); if (!c) return null; const r = c.getBoundingClientRect();
      return [r.x + r.width / 2, r.y + r.height / 2]; }""", id_)


def test_desktop_has_a_round_directions_button_beside_the_zoom_controls(desk):
    b = desk.evaluate("""() => { const e = document.querySelector('#pal-ctl .pc-dirb'); if (!e) return null; const r = e.getBoundingClientRect(), p = document.querySelector('#pal-ctl .pc-pill').getBoundingClientRect();
      return {w: r.width, h: r.height, sameRow: Math.abs((r.top + r.bottom) / 2 - (p.top + p.bottom) / 2) < 3, radius: getComputedStyle(e).borderRadius}; }""")
    assert b and b["sameRow"] and b["w"] == b["h"] and b["radius"] in ("50%", "17.5px")
    desk.click("#pal-ctl .pc-dirb")
    assert desk.evaluate("document.getElementById('pal-dir').classList.contains('on')")
    assert desk.evaluate("getComputedStyle(document.getElementById('pal-dir')).position") == "fixed"           # a card, not a tooltip
    assert "Choose start" in desk.evaluate("document.getElementById('pal-dr-banner').textContent")


def test_desktop_directions_pick_by_search_and_by_click_and_never_enlarge_while_choosing(desk):
    desk.click("#pal-ctl .pc-dirb")
    desk.fill("#pal-dir .dr-f.from input", "west")
    desk.wait_for_timeout(250)
    desk.click("#pal-dir .dr-sg li")
    assert desk.evaluate("window._palDir.state().from.name") == "West"
    # the destination: a click on a building picks it, and does not enlarge it
    c = _node_centre(desk, "delta")
    assert c
    desk.mouse.click(*c)
    desk.wait_for_timeout(900)
    s = desk.evaluate("(() => { const s = window._palDir.state(); return [s.to && s.to.name, !!(s.plans && s.plans.length)]; })()")
    assert s == ["DELTA", True], s
    assert not desk.evaluate("document.getElementById('canvas').classList.contains('focus-mode')")
    assert desk.evaluate("document.querySelectorAll('#pal-dir .dr-st li').length") >= 3
    assert desk.evaluate("document.querySelectorAll('#palace-svg .pl-dir .dr-walk, #palace-svg .pl-dir .dr-ride').length") >= 1
    desk.click("#pal-dir .dr-x")
    assert not desk.evaluate("document.getElementById('pal-dir').classList.contains('on')")
    assert desk.evaluate("document.querySelectorAll('#palace-svg .pl-dir .dr-walk, #palace-svg .pl-dir .dr-ride').length") == 0
    # outside Directions a click enlarges, as before
    c = _node_centre(desk, "delta")
    desk.mouse.click(*c)
    desk.wait_for_timeout(1600)
    assert desk.evaluate("document.getElementById('canvas').classList.contains('focus-mode')")
