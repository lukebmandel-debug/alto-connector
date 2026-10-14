"""Mind Palace interaction pass: a lit route is a line you can follow; an enlarged building's card rises ABOVE its
building (with a notch pointing down onto it) instead of covering it; the elevator takes more than its buttons
(keys, scrolling past an edge, the wheel over it, the car dragged, the roof, a swipe on a phone).

Runs on test_palace's synthetic city. The browser tests are skipped without Playwright's browsers; nothing here
touches the network or any ALTO_* setting."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.engine_patches import PATCHES, apply_patches  # noqa: E402
import test_palace as tp  # noqa: E402


def _bundle():
    d = tp.bundle()
    d["brief"]["relations"] = [{"key": "spine", "label": "Outline"}, {"key": "xref", "label": "Connects"}]
    # the first room of each wing links to the next wing's: routes along the streets
    d["connections"] = [["alpha", "delta", "xref", "alpha leads to delta"], ["alpha", "gamma", "xref", "alpha to gamma"]]
    return d


@pytest.fixture(scope="module")
def html():
    out, _ = build_timeline(*load_brief(copy.deepcopy(_bundle())))
    return out


# ── what the page carries ───────────────────────────────────────────────────
def test_the_engine_centres_card_and_building_together(html):
    names = {p["name"] for p in PATCHES}
    assert {"palace-focus-centres-card-and-building", "palace-focus-centres-card-and-building-fly"} <= names
    assert html.count("window._altoFocusShift(el)") == 2


def test_routes_and_rise_and_elevator_pieces_are_in_the_page(html):
    for s in ("function followRoute", "pl-route-hit", "window._altoFocusShift=", "pal-ghost", "pal-tail", "function stepFloor",
              "function elevWire", "function edgeAt", "pe-call", "pal-pull"):
        assert s in html, s
    # the keys and the other ways are explained on the elevator itself
    assert "drag the car" in palace.PALACE_JS


# ── in a browser ────────────────────────────────────────────────────────────
pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:                      # no browser downloaded
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page_file(tmp_path_factory, html):
    f = tmp_path_factory.mktemp("palint") / "page.html"
    f.write_text(html, encoding="utf-8")
    return f


def _open(browser, f, w=1500, h=900, **kw):
    pg = browser.new_context(viewport={"width": w, "height": h}, **kw).new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1800)
    return pg


def _centre(pg, num):
    return pg.evaluate("""n => { const c = [...document.querySelectorAll('#world .node:not(.pal-floor) .node-card')]
      .filter(c => { const o = c.querySelector('.node-order'); return o && o.textContent.trim() === n; })[0];
      if (!c) return null; const r = c.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }""", num)


def _focus(pg, id_):
    pg.evaluate("""id => { const n = document.getElementById('node-' + id), cv = document.getElementById('canvas');
      cv.scrollLeft = n.offsetLeft - cv.clientWidth / 2; cv.scrollTop = n.offsetTop - cv.clientHeight / 2; }""", id_)
    pg.wait_for_timeout(250)
    c = pg.evaluate("""id => { const r = document.querySelector('#node-' + id + ' .node-card').getBoundingClientRect();
      return [r.x + r.width / 2, r.y + r.height / 2]; }""", id_)
    pg.mouse.click(*c)
    pg.wait_for_function("window._focusedNodeId === arguments[0]", arg=id_, timeout=6000) if False else None
    pg.wait_for_timeout(1800)


def _geo(pg):
    return pg.evaluate("""() => { const n = document.querySelector('.node.focused'); if (!n) return null;
      const f = e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, r: r.right, b: r.bottom, cx: r.x + r.width / 2, cy: r.y + r.height / 2 }; };
      return { card: f(n.querySelector('.node-card')), ghost: f(n.querySelector('.pal-ghost')), tail: f(n.querySelector('.pal-tail')),
               below: n.classList.contains('pal-below'), cv: f(document.getElementById('canvas')) }; }""")


def _by_height(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('#world .node:not(.pal-floor)')]
      .map(n => [n.id.slice(5), parseFloat(n.style.top)]).sort((a, b) => a[1] - b[1]).map(a => a[0])""")


def _clear_of_its_building(g):
    if g["below"]:
        return g["card"]["y"] >= g["ghost"]["b"] - 1
    return g["card"]["b"] <= g["ghost"]["y"] + 1


def test_an_enlarged_card_rises_above_its_building(browser, page_file):
    pg = _open(browser, page_file, h=1100)
    low = _by_height(pg)[-1]                          # the lowest building: plenty of room above it
    _focus(pg, low)
    g = _geo(pg)
    assert g, "nothing enlarged"
    assert not g["below"]
    assert g["card"]["b"] <= g["ghost"]["y"] + 1                  # the card's bottom edge is above the building
    assert g["ghost"]["r"] - g["ghost"]["x"] > 10                  # the building is still there, whole
    assert abs(g["card"]["cx"] - g["ghost"]["cx"]) < 3            # centred over it
    assert g["card"]["b"] <= g["tail"]["y"] + 14 and g["tail"]["b"] <= g["ghost"]["y"] + 3   # the notch sits between
    assert g["card"]["y"] >= g["cv"]["y"] - 1                      # all on screen
    # Esc closes it, the building stays
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(700)
    assert pg.evaluate("window._focusedNodeId") is None and not pg.evaluate("!!document.querySelector('.node.focused')")
    assert not pg.errs


def test_with_no_room_above_it_goes_below_and_the_notch_points_up(browser, page_file):
    pg = _open(browser, page_file)
    high = _by_height(pg)[0]                          # the highest building: the card would run off the top
    _focus(pg, high)
    g = _geo(pg)
    assert g and g["below"] and _clear_of_its_building(g)
    assert g["tail"]["y"] >= g["ghost"]["b"] - 4 and g["tail"]["b"] <= g["card"]["y"] + 14
    assert g["card"]["b"] <= g["cv"]["b"] + 1
    assert not pg.errs


def _routes(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('#palace-svg .pl-route-hit')].map(h => {
      const L = h.getTotalLength(), m = h.getScreenCTM(); let best = null;
      for (let f = .03; f < 1; f += .03) { const p = h.getPointAtLength(L * f), q = new DOMPoint(p.x, p.y).matrixTransform(m);
        const a = document.getElementById('canvas').getBoundingClientRect();
        if (q.x > a.x + 30 && q.x < a.right - 60 && q.y > a.y + 30 && q.y < a.bottom - 30) { best = [q.x, q.y]; if (f > .3) break; } }
      return { to: h._rt.to, from: h._rt.from, pt: best }; })""")


def test_clicking_a_lit_route_goes_to_the_building_at_its_other_end(browser, page_file):
    pg = _open(browser, page_file)
    pg.evaluate("document.getElementById('canvas').scrollTo(0, 0)")
    a = _centre(pg, "1.1")
    assert a
    pg.mouse.move(*a)
    pg.wait_for_function("document.querySelectorAll('#palace-svg .pl-route-hit').length > 0", timeout=4000)
    rs = [r for r in _routes(pg) if r["pt"]]
    assert rs and {r["from"] for r in rs} == {"alpha"}
    r = rs[0]
    cur = pg.evaluate("""p => { const h = [...document.querySelectorAll('#palace-svg .pl-route-hit')]
        .filter(h => h._rt.to === p)[0]; return getComputedStyle(h).cursor; }""", r["to"])
    assert cur == "pointer"                                      # it looks clickable
    pg.mouse.move(*r["pt"], steps=6)
    pg.wait_for_timeout(300)
    assert pg.evaluate("!!document.querySelector('.pl-rt.hot')")  # and lights under the pointer
    assert "click to go there" in pg.evaluate("document.querySelector('.pal-tip').innerText")
    pg.mouse.click(*r["pt"])
    pg.wait_for_timeout(1800)
    assert pg.evaluate("window._focusedNodeId") == r["to"]
    # and from the enlarged building the same: a route leads on to the next one
    rs2 = [x for x in _routes(pg) if x["pt"]]
    if rs2:
        pg.mouse.move(*rs2[0]["pt"], steps=4)
        pg.mouse.click(*rs2[0]["pt"])
        pg.wait_for_timeout(1800)
        assert pg.evaluate("window._focusedNodeId") == rs2[0]["to"]
    assert not pg.errs


# ── the elevator ────────────────────────────────────────────────────────────
def _detail(pg, id_):
    pg.evaluate("id => window.showDetail('node', id)", id_)
    pg.wait_for_timeout(1200)


def _at(pg):
    return pg.evaluate("window._currentDetailId")


def _wait_at(pg, id_):
    pg.wait_for_function("id => window._currentDetailId === id", arg=id_, timeout=6000)
    pg.wait_for_timeout(1000)                        # the doors open again; a key pressed on a ride is ignored


def _tall(pg):
    pg.evaluate("""() => { const dc = document.getElementById('detail-content');
      if (!dc.querySelector('.spacer')) { const d = document.createElement('div'); d.className = 'spacer'; d.style.height = '2500px'; dc.appendChild(d); } }""")


def test_arrow_keys_ride_the_elevator_when_the_page_cannot_scroll_further(browser, page_file):
    pg = _open(browser, page_file)
    _detail(pg, "alpha")
    pg.keyboard.press("ArrowUp")                    # a short page: at its top edge, so up a floor
    _wait_at(pg, "alpha-1")
    pg.keyboard.press("PageUp")
    _wait_at(pg, "alpha-2")
    pg.wait_for_timeout(500)
    pg.keyboard.press("ArrowDown")
    _wait_at(pg, "alpha-1")
    pg.wait_for_timeout(500)
    pg.keyboard.press("Alt+ArrowDown")
    _wait_at(pg, "alpha")
    # the previous / next card keys keep their meaning
    pg.wait_for_timeout(500)
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(900)
    assert _at(pg) == "alpha-1"
    assert not pg.errs


def test_the_page_scrolls_first_and_a_key_goes_through_a_floor_only_at_the_edge(browser, page_file):
    pg = _open(browser, page_file)
    _detail(pg, "alpha-1")
    _tall(pg)
    pg.evaluate("document.getElementById('detail-page').scrollTop = 600")
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("PageDown")
    pg.wait_for_timeout(700)
    assert _at(pg) == "alpha-1"                     # mid-page: the page's own business
    pg.evaluate("document.getElementById('detail-page').scrollTop = 99999")
    pg.wait_for_timeout(150)
    pg.keyboard.press("ArrowDown")                  # at the bottom edge: down a floor
    _wait_at(pg, "alpha")
    assert not pg.errs


def test_scrolling_past_the_edge_pulls_a_floor_but_momentum_does_not(browser, page_file):
    pg = _open(browser, page_file)
    _detail(pg, "alpha-1")
    _tall(pg)
    pg.mouse.move(900, 500)
    pg.evaluate("document.getElementById('detail-page').scrollTop = 1200")
    pg.wait_for_timeout(150)
    for _ in range(70):                              # a long fling that runs into the bottom
        pg.mouse.wheel(0, 70)
        pg.wait_for_timeout(14)
    pg.wait_for_timeout(1500)
    assert _at(pg) == "alpha-1"
    pg.evaluate("document.getElementById('detail-page').scrollTop = 0")
    pg.wait_for_timeout(200)
    pg.mouse.wheel(0, -60)
    pg.wait_for_timeout(120)
    assert pg.evaluate("document.getElementById('pal-pull').classList.contains('on')")   # a pull shows where it leads
    for _ in range(3):
        pg.mouse.wheel(0, -100)
        pg.wait_for_timeout(180)
    _wait_at(pg, "alpha-2")                          # scrolled past the top: up a floor
    assert not pg.errs


def test_the_wheel_over_the_elevator_the_call_buttons_the_roof_and_the_dragged_car(browser, page_file):
    pg = _open(browser, page_file)
    _detail(pg, "alpha")
    pg.mouse.move(120, 480)
    pg.mouse.wheel(0, -120)
    _wait_at(pg, "alpha-1")
    pg.wait_for_timeout(600)
    pg.click(".pe-up")
    _wait_at(pg, "alpha-2")
    pg.wait_for_timeout(600)
    pg.click(".pe-dn")
    _wait_at(pg, "alpha-1")
    pg.wait_for_timeout(600)
    pg.click(".pe-roof")                             # the roof is the ground floor
    _wait_at(pg, "alpha")
    pg.wait_for_timeout(700)
    assert pg.evaluate("document.querySelector('.pe-dn').disabled") and not pg.evaluate("document.querySelector('.pe-up').disabled")
    # drag the car to the top floor
    rows = pg.evaluate("[...document.querySelectorAll('.pe-fl')].map(r => { const b = r.getBoundingClientRect(); return [r.dataset.id, b.x + b.width / 2, b.y + b.height / 2]; })")
    car = pg.evaluate("(() => { const b = document.querySelector('.pe-car').getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })()")
    top = rows[0]
    pg.mouse.move(*car)
    pg.mouse.down()
    pg.mouse.move(car[0], top[2], steps=8)
    assert pg.evaluate("(document.querySelector('.pe-fl.aim') || {dataset: {}}).dataset.id") == top[0]   # the floor it would stop at lights
    pg.mouse.up()
    _wait_at(pg, top[0])
    assert not pg.errs


def test_a_swipe_down_at_the_top_of_a_page_goes_up_a_floor_on_a_phone(browser, page_file):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"))
    pg = ctx.new_page()
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.goto(page_file.as_uri())
    pg.wait_for_timeout(1800)
    _detail(pg, "alpha")
    cdp = ctx.new_cdp_session(pg)

    def swipe(y0, y1, x=200, steps=10):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
        for i in range(1, steps + 1):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 + (y1 - y0) * i / steps}]})
            pg.wait_for_timeout(16)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

    swipe(300, 460)                                  # finger down at the top: up a floor
    _wait_at(pg, "alpha-1")
    pg.wait_for_timeout(700)
    pg.evaluate("document.getElementById('detail-page').scrollTop = 99999")
    pg.wait_for_timeout(200)
    swipe(520, 380)                                  # finger up at the bottom: down a floor
    _wait_at(pg, "alpha")
    assert not pg.errs
