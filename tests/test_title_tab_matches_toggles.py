"""The top label tab is the corner toggles' own plate (Luke, 2026-11-11: "the top label tab is too strong, make it the same opacity as toggles so it doesn't
instantly draw the eye there"; "especially on home page, and especially in classic"). Every style, WebKit: the tab's computed background alpha, backdrop filter,
edge (border + first shadow) equal #search-btn's at 1500x1000, 402x874 and 874x292; and the tab's text keeps 4.5:1 over what the page paints under it."""
import http.server
import io
import json
import shutil
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alto.build import backgrounds, backgrounds_import as bi, holo, pages, phone as _phone, retro   # noqa: E402
from alto.build.backgrounds_catalog import COLOURS, PATTERNS, SCENES   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
HOME = [{"name": "Law", "pid": "p", "courses": [
    {"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e", "#10b981"]}]}]
SIZES = [(1500, 1000), (402, 874), (874, 292)]
HOLO_BGS = ["h-neon-rain", "h-amber-haze", "h-grid-horizon", "h-signal-rain", "h-targeting", "h-lightspeed"]

# reads, in one go: the tab and a bottom-corner toggle, as computed
READ = """()=>{const o={}; for(const [k,s] of [['tab','#title-bar #title-text'],['tog','#search-btn']]){ const e=document.querySelector(s); if(!e){o[k]=null; continue;}
  const c=getComputedStyle(e), r=e.getBoundingClientRect(); const sh=c.boxShadow==='none'?'none':c.boxShadow.split(/,(?![^(]*\\))/)[0].trim();
  o[k]={bg:c.backgroundColor, bf:c.backdropFilter||c.webkitBackdropFilter||'none', bw:c.borderLeftWidth, bc:c.borderLeftColor, sh:sh, color:c.color,
        box:r.width>1&&r.height>1, vis:c.visibility, text:e.textContent.trim()}; } return o;}"""


def alpha(col):
    """'rgba(r, g, b, a)' / 'rgb(...)' / 'color(srgb r g b / a)' -> a"""
    inner = col[col.index("(") + 1:col.index(")")].replace("/", ",").replace(" ", ",")
    v = [x for x in inner.split(",") if x]
    if col.startswith("color("):
        return float(v[4]) if len(v) > 4 else 1.0
    return float(v[3]) if len(v) > 3 else 1.0


def rgb(col):
    inner = col[col.index("(") + 1:col.index(")")].replace("/", ",").replace(" ", ",")
    return [float(x) for x in inner.split(",") if x][:3]


def _lin(v):
    v /= 255
    return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4


def _lum(c):
    return .2126 * _lin(c[0]) + .7152 * _lin(c[1]) + .0722 * _lin(c[2])


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("tabtog")
    data = json.loads((ROOT / "samples" / "outline_brief.json").read_text(encoding="utf-8"))
    b, n, c = load_brief(data)
    (d / "t.html").write_text(build_timeline(b, n, c)[0], encoding="utf-8")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    for mod, sub in ((holo, "holo"), (retro, "retro"), (_phone, "phone")):
        nm, tx = (mod.holo_asset if sub == "holo" else mod.retro_asset if sub == "retro" else mod.phone_asset)()
        (d / sub).mkdir()
        (d / sub / nm).write_text(tx, encoding="utf-8")
    lib, js = bi.site_file()
    (d / lib).write_text(js, encoding="utf-8")
    shutil.copytree(ROOT / "alto" / "assets" / "backgrounds", d / backgrounds.BG_BASE.strip("/"))

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


def _open(webkit, site, page, size, style, theme="dark"):
    mob = size[0] < 500 or size[1] < 500
    ctx = webkit.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2, is_mobile=mob, has_touch=mob, **({"user_agent": UA} if mob else {}))
    pg = ctx.new_page()
    pg.goto(site + page, wait_until="load")
    pg.wait_for_timeout(300)
    pg.evaluate("([s,t])=>{localStorage.clear(); localStorage.setItem('alto-bg-home-v1-style',s); localStorage.setItem('alto-theme-v1',t)}", [style, theme])
    pg.goto(site + page, wait_until="load")
    pg.wait_for_timeout(600)
    pg.evaluate("(s)=>window._altoStyle && window._altoStyle.set(s)", style)
    pg.evaluate("(t)=>document.documentElement.classList.toggle('dark', t==='dark')", theme) if style == "holo" and mob else None
    pg.wait_for_timeout(500)
    return ctx, pg


def _same(pg, size, page):
    r = pg.evaluate(READ)
    tab, tog = r["tab"], r["tog"]
    assert tab and tab["box"], "the name must be drawn as a tab here"
    assert tog and tog["box"]
    assert alpha(tab["bg"]) == pytest.approx(alpha(tog["bg"]), abs=.005), (tab["bg"], tog["bg"])
    assert tab["bf"] == tog["bf"], (tab["bf"], tog["bf"])
    assert tab["bw"] == tog["bw"], (tab, tog)
    if tab["bw"] != "0px":   # (a border of no width has no colour of its own: it only inherits the text's)
        assert tab["bc"] == tog["bc"], (tab, tog)
    assert tab["sh"] == tog["sh"], (tab["sh"], tog["sh"])
    return tab, tog


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("style", ["classic", "retro", "holo"])
def test_home_tab_is_the_toggles_plate(webkit, site, style, size):
    portrait = size == (402, 874)
    for theme in (["dark", "light"] if style == "holo" and size != (1500, 1000) else ["dark"]):
        ctx, pg = _open(webkit, site, "/h.html", size, style, theme)
        try:
            if style == "classic" and portrait:
                # a phone keeps its plain Home label in Classic: no plate to match (nothing is drawn behind the word)
                tab = pg.evaluate(READ)["tab"]
                assert alpha(tab["bg"]) == 0 and tab["bw"] == "0px"
                continue
            tab, tog = _same(pg, size, "h")
            if style == "holo":
                # the short-window toggles are the 60% frost: so is the tab
                assert alpha(tab["bg"]) == pytest.approx(.60 if size[1] <= 500 else .46, abs=.005)
        finally:
            ctx.close()


@pytest.mark.parametrize("style", ["classic", "holo"])
def test_timeline_tab_is_the_toggles_plate(webkit, site, style):
    # (Retro's name is hidden on a board: its cartouche carries it; a phone's timeline has no tab)
    ctx, pg = _open(webkit, site, "/t.html", (1500, 1000), style)
    try:
        _same(pg, (1500, 1000), "t")
    finally:
        ctx.close()


HIDE = "(()=>{const s=document.createElement('style'); s.id='_hide'; s.textContent='#title-bar #title-text,#title-bar #title-text::after{color:transparent !important;-webkit-text-fill-color:transparent !important;text-shadow:none !important;visibility:visible} #title-bar #title-text::after{display:none !important}'; document.head.appendChild(s);})()"


def _ratio(pg):
    """The tab's text against the pixels the page paints under it (the text hidden; the glass's blur is not painted headless, so this is the harder case)."""
    from PIL import Image
    info = pg.evaluate("""()=>{const e=document.querySelector('#title-bar #title-text'); const r=document.createRange(); r.selectNodeContents(e);
      return {rs:[...r.getClientRects()].map(x=>[x.left,x.top,x.width,x.height]), col:getComputedStyle(e).color, dpr:devicePixelRatio}}""")
    pg.evaluate(HIDE)
    pg.wait_for_timeout(150)
    im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    pg.evaluate("document.getElementById('_hide').remove()")
    fg = rgb(info["col"])
    px = []
    for x, y, w, h in info["rs"]:
        c = im.crop((max(0, int(x * info["dpr"])), max(0, int(y * info["dpr"])), min(im.width, int((x + w) * info["dpr"])), min(im.height, int((y + h) * info["dpr"]))))
        px += list(c.getdata())
    assert px
    Ls = sorted((_lum(q), q) for q in px)
    k = int(len(Ls) * .998) if _lum(fg) > Ls[len(Ls) // 2][0] else int(len(Ls) * .002)   # the pixel nearest the text's own luminance, 99.8th percentile
    bg = Ls[min(k, len(Ls) - 1)][1]
    a, b = _lum(fg), _lum(bg)
    return (max(a, b) + .05) / (min(a, b) + .05)


def _worst(webkit, site, style, ids, theme, size=(1500, 1000)):
    ctx, pg = _open(webkit, site, "/h.html", size, style, theme)
    out = {}
    try:
        for i in ids:
            pg.evaluate("(id)=>window._altoBg.choose(id)", i)
            pg.wait_for_timeout(1200 if style == "holo" else 500)
            out[i] = _ratio(pg)
    finally:
        ctx.close()
    return out


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_classic_label_contrast_on_every_background(webkit, site, theme):
    ids = [s["id"] for s in SCENES] + [c["id"] for c in COLOURS] + [p["id"] for p in PATTERNS]
    r = _worst(webkit, site, "classic", ids, theme)
    print("classic", theme, "worst", min(r.items(), key=lambda kv: kv[1]))
    assert min(r.values()) >= 4.5, sorted(r.items(), key=lambda kv: kv[1])[:3]


@pytest.mark.parametrize("size,theme", [((1500, 1000), "dark"), ((402, 874), "dark"), ((402, 874), "light"), ((874, 292), "dark"), ((874, 292), "light")])
def test_holo_label_contrast_on_the_six_backgrounds(webkit, site, size, theme):
    r = _worst(webkit, site, "holo", HOLO_BGS, theme, size)
    print("holo", size, theme, "worst", min(r.items(), key=lambda kv: kv[1]))
    assert min(r.values()) >= 4.5, sorted(r.items(), key=lambda kv: kv[1])[:3]


def test_retro_label_is_gold_on_black(webkit, site):
    ctx, pg = _open(webkit, site, "/h.html", (1500, 1000), "retro")
    try:
        tab = pg.evaluate(READ)["tab"]
        a, b = _lum(rgb(tab["color"])), _lum(rgb(tab["bg"]))
        assert alpha(tab["bg"]) == 1 and (a + .05) / (b + .05) >= 4.5
    finally:
        ctx.close()
