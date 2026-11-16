"""Every desktop minimap's own place (Luke, 2026-11-13, his Torts System in Star chart: "please default the minimap to this
location and size ... make it the same width as the bottom toggles it sits on top of. The user can change it if they want,
and move it, but it always stays there otherwise"). minimap_home.py.

The minimaps: the System's (solar_navopt.py: the System, Star chart and 3D looks) and the Atlas's (palace_world.py). Each
page style (Classic, Retro, Holo), desktop 1440x900 and 1280x720, WebKit first (Luke uses Safari), Chromium where it runs:
 * as wide as the bottom-right toggle group (within 1 px), its right edge on the group's, its bottom the gap above the group;
 * placed again after the window is resized;
 * a user move and a user resize are kept across a reload; a double-click on the corner handle puts it back;
 * it never meets the other chrome.
Skipped without Playwright."""
import copy
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import holo, palace_assets, phone, retro  # noqa: E402
from alto.build import world_plan as wp  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.minimap_home import MM_HOME_JS  # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

STYLES = ("classic", "retro", "holo")
SIZES = {"d1440": (1440, 900), "d1280": (1280, 720)}
MAPS = {"system": "#nvo-map", "atlas": "#wpal-root .wp-mm"}
KEYS = {"system": ("alto-solar-map-at", "alto-solar-map-h"), "atlas": ("alto-world-map-at", "alto-world-map-h")}


def test_the_row_is_measured_not_a_constant():
    for id_ in ("alto-edit-pill", "mode-toggle", "info-btn", "key-toggle", "search-btn"):
        assert id_ in MM_HOME_JS
    assert "getBoundingClientRect" in MM_HOME_JS


@pytest.fixture(scope="module")
def origin():
    if pw is None:
        pytest.skip("Playwright is not installed")
    from test_solar_draw import SMALL, SMALL_LINKS, solar_doc
    from test_world_palace import built
    pages = {"/system.html": build_timeline(*load_brief(copy.deepcopy(solar_doc(SMALL, "orbit", SMALL_LINKS))))[0],
             "/atlas.html": built(world={"places": {"erie": wp.resolve("Peru")}})[0]}
    for mod, folder in ((holo, "holo"), (retro, "retro"), (phone, "phone")):
        name, text = getattr(mod, folder + "_asset")()
        pages[f"/{folder}/{name}"] = text

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            hit = (("text/html" if p.endswith(".html") else "text/javascript" if p.endswith(".js") else "text/css", pages[p]) if p in pages
                   else ("text/javascript", "") if p == "/alto-cloud.js" else palace_assets.find(p))
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


@pytest.fixture(scope="module", params=("webkit", "chromium"))
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


GEO = r"""(sel)=>{const m=document.querySelector(sel), R=window._altoMmRow&&window._altoMmRow(); if(!m||!R) return null;
 const r=m.getBoundingClientRect(), cs=getComputedStyle(m);
 return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height, row:R, on:m.classList.contains('on')&&+cs.opacity>.5,
   z:parseFloat(getComputedStyle(document.documentElement).zoom)||1};}"""

# the other chrome: every visible fixed element on the page's top level (not the canvas, not a full-window layer), the
# System's bottom bar and the Atlas's own bars, the minimap and its tip aside
CHROME = r"""(sel)=>{const vw=innerWidth,vh=innerHeight,mm=document.querySelector(sel),out=[];
 const add=e=>{const cs=getComputedStyle(e); if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity<.05) return; const r=e.getBoundingClientRect();
   const iw=Math.min(r.right,vw)-Math.max(r.left,0), ih=Math.min(r.bottom,vh)-Math.max(r.top,0); if(iw>1&&ih>1&&iw*ih<0.4*vw*vh) out.push({id:e.id||String(e.className).slice(0,30),l:r.left,t:r.top,r:r.right,b:r.bottom});};
 document.querySelectorAll('body>*,#app>*').forEach(e=>{ if(e===mm||e.id==='canvas'||e.id==='nvo-tip'||e.contains(mm)||getComputedStyle(e).position!=='fixed') return; add(e); });
 document.querySelectorAll('#sol-ctl>*,#wpal-root .wp-bar:not(.wp-mm):not(.wp-mmtip)').forEach(add);
 return out;}"""


def _open(browser, origin, kind, style, size, keep=None):
    w, h = SIZES[size]
    ctx = browser.new_context(viewport={"width": w, "height": h}) if keep is None else keep
    if keep is None:
        ctx.add_init_script("try{localStorage.setItem('alto-bg-v1-style',%s)}catch(e){}" % json.dumps(style))
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{origin}/{kind}.html", wait_until="load")
    if kind == "atlas":
        pg.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
    pg.wait_for_timeout(1200)
    pg.evaluate("s=>window._altoStyle&&window._altoStyle.set(s)", style)
    pg.wait_for_timeout(600)
    _enlarge(pg, kind)
    return ctx, pg, errors


def _enlarge(pg, kind):
    if kind == "atlas":
        pg.evaluate("AltoWorld.select('erie')")
    else:
        pg.evaluate("() => window.enterFocus('u1-p1')")
        pg.wait_for_function("() => window._focusedNodeId==='u1-p1' && !window._altoSolarLock.riding() && !window._altoSolarFlight()", timeout=9000)
    pg.wait_for_function("s => { var m=document.querySelector(s); return m && m.classList.contains('on') && +getComputedStyle(m).opacity===1; }",
                         arg=MAPS[kind], timeout=8000)
    pg.wait_for_timeout(400)


def _at_home(g, label):
    R = g["row"]
    assert g["on"], label
    assert abs(g["w"] - (R[2] - R[0])) <= 1, f"{label}: minimap {g['w']:.2f} wide, the toggles {R[2] - R[0]:.2f}"
    assert abs(g["r"] - R[2]) <= 1, f"{label}: right edges {g['r']:.2f} vs {R[2]:.2f}"
    gap = R[1] - g["b"]
    assert 8 <= gap <= 12, f"{label}: {gap:.2f} px above the toggles"


def _clear(pg, kind, label):
    g = pg.evaluate(GEO, MAPS[kind])
    bad = [c["id"] for c in pg.evaluate(CHROME, MAPS[kind])
           if min(g["r"], c["r"]) - max(g["l"], c["l"]) > 0.5 and min(g["b"], c["b"]) - max(g["t"], c["t"]) > 0.5]
    assert not bad, f"{label}: the minimap meets {bad}"


@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("kind", list(MAPS))
def test_it_sits_on_the_toggles_as_wide_as_they_are(browser, origin, kind, style, size):
    ctx, pg, errors = _open(browser, origin, kind, style, size)
    try:
        label = f"{kind} {style} {size}"
        _at_home(pg.evaluate(GEO, MAPS[kind]), label)
        _clear(pg, kind, label)
        if kind == "system":                                                     # the System's other looks: the same place
            for look in ("chart", "3d", "system"):
                pg.evaluate("v => (window._altoSolarBar || window._altoSolarStyles).set(v)", look)
                pg.wait_for_timeout(900)
                _enlarge(pg, kind)
                _at_home(pg.evaluate(GEO, MAPS[kind]), f"{label} {look}")
                _clear(pg, kind, f"{label} {look}")
        w, h = SIZES[size]
        pg.set_viewport_size({"width": w - 160, "height": h - 60})                # a resize: placed again
        pg.wait_for_timeout(900)
        _at_home(pg.evaluate(GEO, MAPS[kind]), f"{label} resized")
        assert not errors, errors
    finally:
        ctx.close()


@pytest.mark.parametrize("kind", list(MAPS))
def test_the_toggles_changing_width_moves_it_with_them(browser, origin, kind):
    ctx, pg, errors = _open(browser, origin, kind, "classic", "d1440")
    try:
        g0 = pg.evaluate(GEO, MAPS[kind])
        pg.evaluate("() => document.getElementById('search-btn').style.setProperty('display','none','important')")   # a button hides
        pg.wait_for_timeout(700)
        g1 = pg.evaluate(GEO, MAPS[kind])
        assert g1["w"] < g0["w"] - 20, (g0["w"], g1["w"])
        _at_home(g1, f"{kind} without search")
    finally:
        ctx.close()


@pytest.mark.parametrize("kind", list(MAPS))
def test_a_move_and_a_resize_are_kept_and_a_double_click_puts_it_back(browser, origin, kind):
    ctx, pg, errors = _open(browser, origin, kind, "classic", "d1440")
    try:
        sel = MAPS[kind]
        pg.evaluate("k => k.forEach(x => localStorage.removeItem(x))", list(KEYS[kind]))
        g0 = pg.evaluate(GEO, sel)
        # resize by the corner handle (top-left)
        c = pg.evaluate("s => { var r=document.querySelector(s+' .rz').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }", sel)
        pg.mouse.move(*c)
        pg.mouse.down()
        for i in range(1, 9):
            pg.mouse.move(c[0] - 60 * i / 8, c[1] - 40 * i / 8)
        pg.mouse.up()
        pg.wait_for_timeout(500)
        g1 = pg.evaluate(GEO, sel)
        assert g1["h"] > g0["h"] + 10 and abs(g1["r"] - g0["r"]) <= 1.5 and abs(g1["b"] - g0["b"]) <= 1.5, (g0, g1)
        # move by dragging the map outside its view box: grab a point near its bottom-left corner
        sp = pg.evaluate("""s => { var m=document.querySelector(s), r=m.getBoundingClientRect(), b=m.querySelector('svg .vb, svg rect');
          var q=b?b.getBoundingClientRect():null, pts=[[r.left+12,r.bottom-12],[r.right-12,r.bottom-12],[r.left+12,r.top+40],[r.right-12,r.top+30]];
          return pts.find(p => !q || p[0]<q.left-8 || p[0]>q.right+8 || p[1]<q.top-8 || p[1]>q.bottom+8); }""", sel)
        if kind == "system":                                                     # (not on a body: a press there is a click)
            sp = pg.evaluate("""a => { var s=a[0], p=a[1], m=document.querySelector(s), r=m.getBoundingClientRect();
              for(var y=r.bottom-10; y>r.top+30; y-=6) for(var x=r.left+10; x<r.right-10; x+=6){ var e=document.elementFromPoint(x,y); if(e && !(e.closest && e.closest('circle,rect,.rz')) && m.contains(e)) return [x,y]; } return p; }""", [sel, sp])
        pg.mouse.move(*sp)
        pg.mouse.down()
        for i in range(1, 11):
            pg.mouse.move(sp[0] - 400 * i / 10, sp[1] - 250 * i / 10)
        pg.mouse.up()
        pg.wait_for_timeout(600)
        g2 = pg.evaluate(GEO, sel)
        assert g2["r"] < g1["r"] - 300 and g2["b"] < g1["b"] - 180 and abs(g2["h"] - g1["h"]) <= 1, (g1, g2)
        saved = pg.evaluate("k => k.map(x => localStorage.getItem(x))", list(KEYS[kind]))
        assert all(saved), saved
        pg.reload()                                                              # kept across a reload
        if kind == "atlas":
            pg.wait_for_function("window.AltoWorld && document.querySelector('#wpal-root .wp-pin')", timeout=20000)
        pg.wait_for_timeout(1200)
        _enlarge(pg, kind)
        g3 = pg.evaluate(GEO, sel)
        assert abs(g3["l"] - g2["l"]) <= 1.5 and abs(g3["t"] - g2["t"]) <= 1.5 and abs(g3["h"] - g2["h"]) <= 1.5, (g2, g3)
        pg.dblclick(sel + " .rz")                                                # back to its own place and size
        pg.wait_for_timeout(600)
        _at_home(pg.evaluate(GEO, sel), f"{kind} reset")
        assert pg.evaluate("k => k.map(x => localStorage.getItem(x))", list(KEYS[kind])) == [None, None]
        assert not errors, errors
    finally:
        ctx.close()


def test_a_blocked_storage_still_puts_it_home(browser, origin):
    w, h = SIZES["d1440"]
    ctx = browser.new_context(viewport={"width": w, "height": h})
    ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){ throw new Error('blocked'); }});")
    try:
        ctx2, pg, errors = _open(browser, origin, "system", "classic", "d1440", keep=ctx)
        _at_home(pg.evaluate(GEO, MAPS["system"]), "system, storage blocked")
        assert not [e for e in errors if "minimap" in e.lower() or "_altoMm" in e], errors
    finally:
        ctx.close()
