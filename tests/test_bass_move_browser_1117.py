"""The movable Bass side panel (Board B-1117-MOVE) and the route-neutral placeholder, in real browsers (WebKit and Chromium, local servers, no network, fake uid):
drag by the header, 20px clamp on every edge and clear of the fixed top row (d1440, d1000), restore after a reload, storage that throws, double-click reset, the close
button and the credits pill never drag, selected text never drags, resize re-clamps, a phone keeps its bottom sheet. Shots: PANEL_MOVE_SHOTS=<dir>."""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_bass_panels_235 import SCRIPT as _PANELS  # noqa: E402

HEAD = _PANELS[:_PANELS.index('MEASURE = """')]

BODY = textwrap.dedent('''
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    RECT = "() => { const r = document.querySelector('.bs-panel').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom, innerWidth, innerHeight]; }"
    TOP = "() => { const t = document.getElementById('title-bar'); return t ? t.getBoundingClientRect().bottom : 0; }"
    STORE = "() => { try { return localStorage.getItem('alto-bass-panel-pos-v1'); } catch (e) { return 'threw'; } }"
    THROW = "(() => { const t = () => { throw new Error('storage blocked'); }; Storage.prototype.getItem = t; Storage.prototype.setItem = t; Storage.prototype.removeItem = t; })();"
    def openp(pg, style, theme, hint=None):
        pg.evaluate("p => drawPrivate(p)", PAGES); pg.wait_for_timeout(250)
        pg.evaluate("w => (0, eval)(w)", bundle); pg.wait_for_timeout(350)
        pg.evaluate("window._altoBass.open('panel')"); pg.wait_for_timeout(500)
    def center(pg, sel):
        return pg.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", sel)
    def drag(pg, dx, dy, sel=".bs-panel .bs-name", steps=10):
        x, y = center(pg, sel); pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x + dx, y + dy, steps=steps); pg.mouse.up(); pg.wait_for_timeout(120)
    res = []
    with pw.sync_playwright() as p:
        b = getattr(p, %(engine)r).launch()
        for style, theme, w, h in %(cases)r:
            c = {"case": [%(engine)r, style, theme, w, h], "errs": []}
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg = ctx.new_page(); pg.on("pageerror", lambda e: c["errs"].append(str(e)) if "MIME type" not in str(e) else None)
            pg.add_init_script(FAKE + ";try{localStorage.setItem('alto-bg-home-v1-style','%%s');localStorage.setItem('alto-theme-v1','%%s');localStorage.setItem('alto-bass-ack-u','1')}catch(e){}" %% (style, theme))
            pg.goto(base); pg.wait_for_timeout(900)
            openp(pg, style, theme)
            c["ph_home"] = pg.evaluate("document.querySelector('.bs-say').placeholder"); c["greet_home"] = pg.evaluate("document.querySelector('.bs-log').textContent")
            c["dock"] = pg.evaluate(RECT); c["top"] = pg.evaluate(TOP)
            if OUT and %(shoot)r:
                pg.screenshot(path="%%s/%%s-%%d-dock.png" %% (OUT, style, w))
            drag(pg, -380, 60)
            c["moved"] = pg.evaluate(RECT)
            if OUT and %(shoot)r:
                pg.screenshot(path="%%s/%%s-%%d-moved.png" %% (OUT, style, w))
            drag(pg, -3000, -3000); c["tl"] = pg.evaluate(RECT)
            drag(pg, 3000, 3000); c["br"] = pg.evaluate(RECT)
            drag(pg, -380, 60); c["stored"] = pg.evaluate(STORE); c["before_reload"] = pg.evaluate(RECT)
            pg.reload(); pg.wait_for_timeout(900); openp(pg, style, theme); c["after_reload"] = pg.evaluate(RECT)
            hx, hy = center(pg, ".bs-panel .bs-name")
            pg.mouse.dblclick(hx, hy); pg.wait_for_timeout(200)
            c["reset"] = pg.evaluate(RECT); c["reset_store"] = pg.evaluate(STORE)
            # the close button and the credits pill are not handles
            for key, sel in (("x", '.bs-panel .bs-ib[data-a="close"]'), ("chip", ".bs-panel .bs-chip")):
                if pg.query_selector(sel):
                    before = pg.evaluate(RECT); x, y = center(pg, sel); pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x - 120, y + 80, steps=6)
                    c["nodrag_" + key] = [before, pg.evaluate(RECT)]; pg.mouse.up(); pg.wait_for_timeout(100)
                    if not pg.query_selector(".bs-panel"):
                        pg.evaluate("window._altoBass.open('panel')"); pg.wait_for_timeout(400)
            # selected text in the thread never drags
            pg.evaluate("() => { const l = document.querySelector('.bs-log') || document.querySelector('.bs-b'); const r = document.createRange(); r.selectNodeContents(l); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
            before = pg.evaluate(RECT); x, y = center(pg, ".bs-panel .bs-b"); pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x - 150, y + 60, steps=6); pg.mouse.up()
            c["nodrag_text"] = [before, pg.evaluate(RECT)]
            # resize re-clamps a moved panel
            pg.evaluate("() => getSelection().removeAllRanges()")
            drag(pg, 3000, 3000); pg.set_viewport_size({"width": 1000 if w > 1000 else 900, "height": 700}); pg.wait_for_timeout(300); c["resized"] = pg.evaluate(RECT)
            pg.set_viewport_size({"width": w, "height": h}); pg.wait_for_timeout(200)
            # the placeholder on a timeline keeps the old words
            pg.evaluate("() => { const s = document.createElement('script'); s.setAttribute('data-tid', 't1'); s.type = 'application/json'; document.head.appendChild(s); window._altoBass.open('panel'); }"); pg.wait_for_timeout(400)
            c["ph_timeline"] = pg.evaluate("document.querySelector('.bs-say').placeholder"); c["greet_tl"] = pg.evaluate("document.querySelector('.bs-log').textContent")
            c["has_enter_close"] = None
            pg.keyboard.press("Escape"); pg.wait_for_timeout(150); c["esc_closed"] = pg.query_selector(".bs-panel") is None
            ctx.close()
            # storage that throws: the page works and the panel still drags
            ctx = b.new_context(viewport={"width": w, "height": h}); pg = ctx.new_page(); pg.on("pageerror", lambda e: c["errs"].append("throw-ctx: " + str(e)) if "MIME type" not in str(e) else None)
            pg.add_init_script(FAKE); pg.add_init_script(THROW)
            pg.goto(base); pg.wait_for_timeout(900); openp(pg, style, theme)
            d0 = pg.evaluate(RECT); drag(pg, -200, 40); c["throw"] = [d0, pg.evaluate(RECT)]
            ctx.close()
            res.append(c)
        for style, theme in %(phones)r:
            ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, user_agent=UA, device_scale_factor=2)
            pg = ctx.new_page(); pg.add_init_script(FAKE + ";try{localStorage.setItem('alto-bg-home-v1-style','%%s');localStorage.setItem('alto-theme-v1','%%s');localStorage.setItem('alto-bass-ack-u','1')}catch(e){}" %% (style, theme))
            pg.goto(base); pg.wait_for_timeout(900); openp(pg, style, theme)
            r0 = pg.evaluate(RECT); drag(pg, -100, -200); r1 = pg.evaluate(RECT)
            res.append({"case": [%(engine)r, style, theme, 390, 844], "phone": [r0, r1], "moved_class": pg.evaluate("document.querySelector('.bs-root').classList.contains('bs-moved')"),
                        "pos": pg.evaluate("getComputedStyle(document.querySelector('.bs-panel')).position")})
            ctx.close()
        b.close()
    print("JSON:" + json.dumps(res))
''')

DESK = [("holo", "dark", 1440, 900), ("classic", "light", 1440, 900), ("retro", "dark", 1440, 900),
        ("holo", "dark", 1000, 800), ("classic", "light", 1000, 800), ("retro", "dark", 1000, 800)]


def _run(engine, cases, phones, shoot=False):
    src = (HEAD + BODY) % {"root": str(ROOT), "cases": cases, "shots": os.environ.get("PANEL_MOVE_SHOTS", ""), "engine": engine, "phones": phones, "shoot": shoot}
    r = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, timeout=1500)
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("JSON:")][-1][5:])


@pytest.fixture(scope="module", params=["webkit", "chromium"])
def moved(request):
    if request.param == "webkit":
        return _run("webkit", DESK, [("classic", "light"), ("holo", "dark")], shoot=True)
    return _run("chromium", [DESK[1], DESK[4]], [("classic", "light")])


def _near(a, b, tol=1.5):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_dragging_the_header_moves_the_panel(moved):
    for m in moved:
        if "phone" in m:
            continue
        assert not m["errs"], (m["case"], m["errs"])
        d, mv = m["dock"], m["moved"]
        assert mv[0] < d[0] - 100 and mv[1] > d[1] + 20, (m["case"], d, mv)           # it went left and down
        assert abs((mv[2] - mv[0]) - (d[2] - d[0])) < 1.5 and abs((mv[3] - mv[1]) - (d[3] - d[1])) < 1.5, (m["case"], d, mv)   # its size is its own


def test_the_clamp_keeps_20px_from_every_edge_and_clear_of_the_top_row(moved):
    for m in moved:
        if "phone" in m:
            continue
        tl, br = m["tl"], m["br"]
        assert abs(tl[0] - 20) < 1 and tl[1] >= m["top"] + 7 and tl[1] >= 19, (m["case"], tl, m["top"])
        assert abs(br[4] - br[2] - 20) < 1 and abs(br[5] - br[3] - 20) < 1, (m["case"], br)
        assert m["top"] > 0, m["case"]


def test_the_position_is_stored_restored_and_a_double_click_resets_it(moved):
    for m in moved:
        if "phone" in m:
            continue
        assert m["stored"] and json.loads(m["stored"])["x"] >= 20, m["case"]
        assert _near(m["after_reload"], m["before_reload"]), (m["case"], m["after_reload"], m["before_reload"])
        assert _near(m["reset"], m["dock"]), (m["case"], m["reset"], m["dock"])
        assert m["reset_store"] is None, m["case"]


def test_storage_that_throws_does_not_break_the_page(moved):
    for m in moved:
        if "phone" in m:
            continue
        d0, d1 = m["throw"]
        assert d1[0] < d0[0] - 100, (m["case"], m["throw"])
        assert not m["errs"], (m["case"], m["errs"])


def test_the_close_button_the_pill_and_selected_text_never_drag(moved):
    for m in moved:
        if "phone" in m:
            continue
        for k in ("nodrag_x", "nodrag_chip", "nodrag_text"):
            if k in m:
                a, b = m[k]
                assert _near(a, b, 0.6), (m["case"], k, a, b)
        assert "nodrag_x" in m and "nodrag_text" in m, m["case"]


def test_resize_reclamps_and_escape_closes(moved):
    for m in moved:
        if "phone" in m:
            continue
        r = m["resized"]
        assert r[0] >= 19.5 and r[1] >= 19.5 and r[4] - r[2] >= 19.5 and r[5] - r[3] >= 19.5, (m["case"], r)
        assert m["esc_closed"], m["case"]


def test_the_phone_keeps_its_bottom_sheet(moved):
    seen = 0
    for m in moved:
        if "phone" not in m:
            continue
        seen += 1
        a, b = m["phone"]
        assert _near(a, b, 0.6) and not m["moved_class"], (m["case"], a, b)
        assert m["pos"] == "fixed" and a[3] > a[5] - 30 and a[0] <= 21, (m["case"], a)
    assert seen >= 1


def test_the_placeholder_is_neutral_on_home_and_unchanged_on_a_timeline(moved):
    for m in moved:
        if "phone" in m:
            continue
        assert m["ph_home"] == "Ask Bass anything about your projects", m["case"]
        assert m["ph_timeline"] == "Ask Bass to change this timeline", m["case"]
        assert "open a timeline to change its cards" in m["greet_home"] and "in this timeline" not in m["greet_home"], m["case"]
        assert "in this timeline" in m["greet_tl"], m["case"]
