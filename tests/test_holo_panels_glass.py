"""Holo home, C final (Luke, 2026-11-12): every timeline card wears the Start new project box's glass (one fill, rim, glow and backdrop-filter, read from the same
variables: body, icon cell, clear button row); the outer panels stay clear as on rel-223; no label backings, one halo; Classic is untouched."""
import http.server
import io
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import backgrounds_import as bi, holo, pages, phone as _phone, retro   # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

HOME = [{"name": "Law", "pid": "p", "courses": [
    {"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e"]}]}]
PRIV = [{"key": "k1", "title": "Torts II", "project": "Alpha", "units": ["#4a9eff"], "fmt": "timeline"},
        {"key": "k2", "title": "Evidence II", "project": "Beta", "units": ["#f43f5e"], "fmt": "timeline"}]
PROPS = ("backgroundImage", "backgroundColor", "borderTopColor", "borderTopWidth", "borderTopStyle", "boxShadow", "backdropFilter")


def test_one_glass_in_the_source():
    css = holo.css()
    assert "--ho-glass-bg:" in css and "--ho-glass-sh:" in css
    assert css.count("--ho-glass-bg:") == 1, "the glass is defined once"
    # the box and the New timeline tile read it in one rule; the cards read the same variables
    flat = css.replace("\n", "")
    assert ":is(.course-tile.new-tile,.project-slab.new-project-slab)" in flat
    assert "background:var(--ho-glass-bg) !important;border:var(--ho-glass-bd) !important;box-shadow:var(--ho-glass-sh)" in flat
    # the 3px axis layer of the halo is load-bearing (Grid horizon's count: 4.50 with it, 3.34 without)
    assert "3px 0 0 rgb(var(--ho-bgrgb)),-3px 0 0 rgb(var(--ho-bgrgb)),0 3px 0" in flat


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("hologlass")
    (d / "t.html").write_text("<html><body>t</body></html>")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    for mod, sub in ((holo, "holo"), (retro, "retro"), (_phone, "phone")):
        nm, tx = (mod.holo_asset if sub == "holo" else mod.retro_asset if sub == "retro" else mod.phone_asset)()
        (d / sub).mkdir()
        (d / sub / nm).write_text(tx, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(d), **k)

        def log_message(self, *a):
            pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.fixture(scope="module")
def webkit():
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = p.webkit.launch()
        except Exception as e:
            pytest.skip(f"no webkit: {e}")
        yield b
        b.close()


def _read(webkit, site, style, dark, size):
    ctx = webkit.new_context(viewport={"width": size[0], "height": size[1]})
    pg = ctx.new_page()
    pg.goto(site + "/h.html", wait_until="load")
    pg.evaluate("(s)=>{localStorage.clear();localStorage.setItem('alto-bg-home-v1-style',s)}", style)
    pg.goto(site + "/h.html", wait_until="load")
    pg.wait_for_timeout(700)
    pg.evaluate("(s)=>window._altoStyle && window._altoStyle.set(s)", style)
    pg.evaluate("(d)=>document.documentElement.classList.toggle('dark',d)", dark)
    pg.evaluate("(P)=>{try{drawPrivate(P)}catch(e){}}", PRIV)   # (the signed-in list: the Private label and the sort control)
    pg.wait_for_timeout(500)
    out = pg.evaluate("""(P)=>{const g=e=>{const c=getComputedStyle(e),o={};P.forEach(p=>o[p]=c[p]);o.bf=c.webkitBackdropFilter;return o;};
      const f=s=>document.querySelector(s);
      const L=s=>{const e=f(s);if(!e)return null;const c=getComputedStyle(e);return {bg:c.backgroundColor,ts:c.textShadow}};
      return {emblem:(f('.course-tile:not(.new-tile) .tile-emblem')?getComputedStyle(f('.course-tile:not(.new-tile) .tile-emblem')).backgroundColor:null),kicker:L('.project-slab:not(.new-project-slab) .slab-kicker'),
        chip:L('#home-row .hr-plain, #home-row .hr-switch'),sort:L('#home-row .home-sort'),panel:g(f('.project-slab:not(.new-project-slab)')),box:f('.new-project-slab')?g(f('.new-project-slab')):null,tile:g(f('.course-tile:not(.new-tile)')),
        holo:document.documentElement.classList.contains('alto-holo')}}""", list(PROPS))
    ctx.close()
    return out


@pytest.mark.parametrize("size", [(1440, 900), (402, 874)])
@pytest.mark.parametrize("dark", [True, False])
def test_cards_share_the_new_project_box_glass_in_holo(webkit, site, size, dark):
    if size[0] > 640 and not dark:
        pytest.skip("Holographic is dark-only on a computer")
    r = _read(webkit, site, "holo", dark, size)
    assert r["holo"]
    for k in ("backgroundImage", "borderTopColor", "borderTopWidth", "borderTopStyle", "boxShadow", "backdropFilter", "bf"):
        assert r["tile"][k] == r["box"][k], (k, r["tile"][k], r["box"][k])
    assert r["tile"]["backgroundImage"].startswith("linear-gradient")
    # the outer panel is NOT the glass: clear, as before
    assert r["panel"]["backgroundImage"] == "none"
    assert r["panel"]["boxShadow"] != r["box"]["boxShadow"]
    # the card's icon cell is clear; the labels have no backing and carry the halo
    assert r["emblem"] == "rgba(0, 0, 0, 0)"
    assert r["kicker"]["bg"] == "rgba(0, 0, 0, 0)" and r["kicker"]["ts"].count(",") > 20, r["kicker"]
    # the new home row (Private | Shared switch, Private chip, sort chip) sits on its own frost plate, the corner toggles' glass, so it needs no halo
    for k in ("chip", "sort"):
        assert r[k] is not None, k
        assert r[k]["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"), (k, r[k])


def test_classic_panels_are_not_the_holo_glass(webkit, site):
    r = _read(webkit, site, "classic", False, (1440, 900))
    assert not r["holo"]
    assert r["panel"]["boxShadow"] != "rgba(79, 240, 224, 0.22) 0px 0px 14px 0px, rgba(79, 240, 224, 0.12) 0px 0px 22px 0px inset"


LABELS = {"title": ".course-tile:not(.new-tile) .tile-title", "units": ".course-tile:not(.new-tile) .t-units", "sub": ".course-tile:not(.new-tile) .tile-sub",
          "pname": ".project-slab:not(.new-project-slab) .slab-kicker", "rswitch": "#home-row .hr-switch .hr-chip", "rprivate": "#home-row .hr-plain", "rsort": "#home-row .home-sort", "spcard": ".sp-card"}



def _lum(c):
    o = 0
    for v, w in zip(c, (.2126, .7152, .0722)):
        v /= 255.0
        o += w * (v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4)
    return o


PLAN_JS = """(P)=>{const z=n=>n<10?'0'+n:''+n,d=new Date(),f=o=>{const x=new Date(d.getTime()+o*864e5);return x.getFullYear()+'-'+z(x.getMonth()+1)+'-'+z(x.getDate())};
  P[0].plan={days:[f(0),f(0),f(0),f(-1),f(-2)]};drawPrivate(P)}"""   # (the first file has a plan, 3 today and 2 late; the second shows "+ Make a study plan")


def _contrast(c1, c2):
    a, b = _lum(c1), _lum(c2)
    return (max(a, b) + .05) / (min(a, b) + .05)


def _worst_contrast(webkit, site, ground, dark, size, shot=None):
    """Art's glyph-pixel method: the glyph pixels are the pixels that change when the text is made transparent (the halo stays), kept where they are the text colour;
    the contrast is the text colour against the same pixels with the text gone, on the page as it renders with the background actually loaded
    (localStorage alto-bg-home-v1 = {"v": ground}) and its animation frozen. Unit bars: each bar's centre pixel against the pixels just above and below the bar."""
    from PIL import Image
    ctx = webkit.new_context(viewport={"width": size[0], "height": size[1]})
    pg = ctx.new_page()
    pg.goto(site + "/h.html", wait_until="load")
    pg.evaluate("(g)=>{localStorage.clear();localStorage.setItem('alto-bg-home-v1-style','holo');localStorage.setItem('alto-bg-home-v1',JSON.stringify({v:g}))}", ground)
    pg.goto(site + "/h.html", wait_until="load")
    pg.wait_for_timeout(900)
    pg.evaluate("(s)=>window._altoStyle && window._altoStyle.set(s)", "holo")
    pg.evaluate("(d)=>document.documentElement.classList.toggle('dark',d)", dark)
    pg.evaluate(PLAN_JS, PRIV)
    pg.wait_for_timeout(1000)
    pg.evaluate("()=>{document.documentElement.classList.add('hp-hid');document.querySelectorAll('video').forEach(v=>v.pause())}")
    pg.wait_for_timeout(300)
    boxes = pg.evaluate("""(S)=>{const o={};for(const k in S){o[k]=[...document.querySelectorAll(S[k])].map(e=>{const r=e.getBoundingClientRect();
      return {x:r.x,y:r.y,w:r.width,h:r.height,col:getComputedStyle(e).color,vis:r.width>0&&r.bottom>0&&r.top<innerHeight}}).filter(e=>e.vis)}return o}""", LABELS)
    bars = pg.evaluate("""()=>[...document.querySelectorAll('.course-tile:not(.new-tile) .unit-strip > *')].map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}}).filter(r=>r.w>0&&r.bottom<innerHeight)""".replace("r.bottom", "(r.y+r.h)"))
    shotb = pg.screenshot()
    if shot:
        open(shot, "wb").write(shotb)
    A = Image.open(io.BytesIO(shotb)).convert("RGB")
    pg.add_style_tag(content="*{color:transparent !important;-webkit-text-fill-color:transparent !important}")
    pg.wait_for_timeout(150)
    B = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    ctx.close()
    worst = {}
    for k, els in boxes.items():
        for e in els:
            x0, y0, x1, y1 = max(int(e["x"]) - 2, 0), max(int(e["y"]) - 2, 0), min(int(e["x"] + e["w"]) + 2, A.width), min(int(e["y"] + e["h"]) + 2, A.height)
            tc = [float(v) for v in e["col"][e["col"].index("(") + 1:-1].split(",")[:3]]
            pa, pb = list(A.crop((x0, y0, x1, y1)).getdata()), list(B.crop((x0, y0, x1, y1)).getdata())
            for u, w in zip(pa, pb):
                if sum(abs(u[j] - w[j]) for j in range(3)) > 90 and sum(abs(u[j] - tc[j]) for j in range(3)) < 60:
                    worst[k] = min(worst.get(k, 99), _contrast(tc, w))
    for r in bars:   # (the bar's own centre pixel against the 1 px keyline rows just above and below it, which is its surround)
        top, bot = round(r["y"]), round(r["y"] + r["h"]) - 1
        cx = int(r["x"] + r["w"] / 2)
        bar = A.getpixel((cx, top + (bot - top) // 2))
        for yy in (top - 1, bot + 1):
            if 0 <= yy < A.height:
                worst["bars"] = min(worst.get("bars", 99), _contrast(bar, A.getpixel((cx, yy))))
    return worst


@pytest.mark.parametrize("ground,dark,size", [(g, d, z) for g in ("h-neon-rain", "h-amber-haze", "h-grid-horizon", "h-signal-rain", "h-targeting", "h-lightspeed", None) for d, z in ((True, (1440, 900)), (True, (402, 874)), (False, (402, 874)))])
def test_labels_clear_4_5_over_a_loaded_ground(webkit, site, ground, dark, size):
    w = _worst_contrast(webkit, site, ground, dark, size)
    assert {"title", "pname", "rprivate", "rsort", "units", "bars"} <= set(w) and ("spcard" in w) == (size[0] > 640), w   # (the study-plan line is a computer's)
    assert min(v for k, v in w.items() if k != "bars") >= 4.5, str({k: round(v, 2) for k, v in w.items()})
    print("CHIP", ground, dark, size[0], round(min(w['rprivate'], w['rsort']), 2))
    assert w["bars"] >= 3, w   # (3:1 against the surround in both themes: ground keyline in dark, ink keyline in light)
