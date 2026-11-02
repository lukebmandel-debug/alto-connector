"""Holographic (alto/build/holo.py): the third style, after Classic and Retro (Luke, 2026-10-28: "On holographic style, i like B, but make
sure that text is not blending into the background too much.").

The hard condition is WCAG AA on every page, light and dark. Here: (1) every token pair the rules can put together is computed against the
floor (4.5:1 text, 3:1 a line), (2) the sheet carries no Retro leftovers, (3) a page holds only the switch, and (4) in a browser the
computed colour of every piece of text on a real timeline page is measured against what is really under it, in both themes.
The browser parts are skipped when Playwright is not installed."""
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import backgrounds_import as bi, holo, holo_backgrounds as hb, pages, palace_assets, retro   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


def _build(name, **over):
    d = json.loads((ROOT / "samples" / f"{name}_brief.json").read_text(encoding="utf-8"))
    d["brief"].update(over)
    brief, nodes, conns = load_brief(d)
    return build_timeline(brief, nodes, conns)[0]


@pytest.fixture(scope="module")
def outline():
    return _build("outline")


# ── the floor, by arithmetic ────────────────────────────────────────────────

@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_token_pair_meets_wcag_aa(theme):
    t = holo.TOKENS[theme]
    bad = [(f, b, round(holo.contrast(t[f], t[b]), 2), need) for f, b, need in holo.PAIRS if holo.contrast(t[f], t[b]) < need]
    assert not bad, bad


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_unit_hue_reads_on_every_plate(theme):
    t, u = holo.TOKENS[theme], holo.UNITS[theme]
    bad = [(i, b, round(holo.contrast(u[i], t[b]), 2)) for i, b, need in holo.UNIT_PAIRS if holo.contrast(u[i], t[b]) < need]
    assert not bad, bad


def test_the_contrast_arithmetic_is_wcag():
    assert round(holo.contrast("#000000", "#ffffff"), 2) == 21.0
    assert round(holo.contrast("#777777", "#ffffff"), 2) == 4.48            # the classic just-failing grey


def test_the_sheet_is_retro_re_inked_with_no_gold_and_no_frame():
    c = holo.css()
    assert "html.alto-holo" in c and "html.alto-holo.dark" in c
    for gone in ("#d9ae55", "#efe6cf", "#b9b2a0", "217,174,85", "#sk-frame", "#sk-mark", "font-family", "X ", "FONT"):
        assert gone not in c, gone
    for anchor in ("#world .node-card", "#river-svg path", "#detail-page", "#lanes-svg .ln-main", ".pal-svg .pl-tube", "#bldg-root", "#wpal-root", ".lu-chip",
                   "#title-bar", "#nav .nav-btn", "#pmin-find"):
        assert anchor in c, anchor
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", holo.ink(retro.HOME_CSS))   # the homepage's Retro plates are all re-inked
    assert "#mode-toggle" in c and "#mode-toggle{display:none" not in c     # unlike Retro, the light/dark toggle stays: a square chip (Art, fix 1)
    assert re.search(r"#mode-toggle[^{]*\{[^}]*border-radius:0", c)


# ── what a page carries ─────────────────────────────────────────────────────

def test_the_look_is_a_hosted_script_and_the_page_holds_only_its_hook(outline):
    name, text = holo.holo_asset()
    assert holo.PATH == "/holo/" + name and ("holo", name, text) in palace_assets.assets()
    assert palace_assets.find(holo.PATH)[1] == text
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', outline, re.S).group(1)
    assert json.dumps(holo.PATH) in head and "-style" in head
    assert "alto-holo-css" not in outline and "html.alto-holo" not in outline


def test_the_system_and_the_homepage_carry_the_layer_too():
    page = _build("outline", layout="solar")
    head = re.search(r'<script id="alto-bg-head">(.*?)</script>', page, re.S).group(1)
    assert "_altoHoloLayer" in head and json.dumps(holo.PATH) in head
    assert "Holographic" in page and "_altoHoloLayer" in page               # the System's own switch


def test_the_picker_offers_holographic():
    js = bi.lib_js()
    assert "'Holographic'" in js and "'Retro'" in js


# ── in a browser ───────────────────────────────────────────────────────────

# every element with text of its own: its colour against what is really under it (backgrounds composited up the tree; an image or a
# gradient is read as its own colour where it is a plain one, else the nearest solid below it), WCAG's 4.5 (3 for large text)
AUDIT_JS = r"""(function(){
function parse(c){ var m=c.match(/rgba?\(([^)]+)\)/); if(!m) return null; var p=m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}; }
function over(t,u){ var a=t.a+u.a*(1-t.a); return a? {r:(t.r*t.a+u.r*u.a*(1-t.a))/a,g:(t.g*t.a+u.g*u.a*(1-t.a))/a,b:(t.b*t.a+u.b*u.a*(1-t.a))/a,a:a}:{r:0,g:0,b:0,a:0}; }
function lum(c){ var f=function(v){ v/=255; return v<=.03928? v/12.92 : Math.pow((v+.055)/1.055,2.4); }; return .2126*f(c.r)+.7152*f(c.g)+.0722*f(c.b); }
function bgOf(el){ var stack=[]; for(var e=el;e&&e.nodeType===1;e=e.parentElement){ var s=getComputedStyle(e), c=parse(s.backgroundColor); if(c&&c.a>0) stack.push(c); if(c&&c.a>=.99) break; }
  var acc={r:255,g:255,b:255,a:1}; if(!stack.length||stack[stack.length-1].a<.99){ var h=parse(getComputedStyle(document.documentElement).backgroundColor); if(h&&h.a>0) acc=h; }
  for(var i=stack.length-1;i>=0;i--) acc=over(stack[i],acc); return acc; }
var bad=[], seen=0;
document.querySelectorAll('body *').forEach(function(el){
  if(!el.childNodes) return; var own=''; el.childNodes.forEach(function(n){ if(n.nodeType===3) own+=n.nodeValue; }); own=own.trim(); if(!own) return;
  if(/^(SCRIPT|STYLE|NOSCRIPT|TITLE)$/.test(el.tagName)) return;
  var s=getComputedStyle(el), r=el.getBoundingClientRect();
  if(s.visibility==='hidden'||s.display==='none'||+s.opacity===0||r.width<2||r.height<2||r.bottom<0||r.right<0||r.top>innerHeight||r.left>innerWidth) return;
  for(var p=el;p;p=p.parentElement){ var ps=getComputedStyle(p); if(ps.display==='none'||ps.visibility==='hidden'||+ps.opacity===0) return; }
  seen++; var fg=parse(s.color); if(!fg) return; var bg=bgOf(el), op=1; for(var q=el;q&&q.nodeType===1;q=q.parentElement) op*=+getComputedStyle(q).opacity;
  fg.a=fg.a*op; var f=over(fg,bg), L1=lum(f), L2=lum(bg), ratio=(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);
  var fs=parseFloat(s.fontSize), large=fs>=24||(fs>=18.66&&+s.fontWeight>=700), need=large?3:4.5;
  if(ratio<need) bad.push({t:own.slice(0,40), ratio:Math.round(ratio*100)/100, need:need, fg:s.color, bg:'rgb('+Math.round(bg.r)+','+Math.round(bg.g)+','+Math.round(bg.b)+')',
    el:el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+(el.className&&el.className.baseVal===undefined?'.'+String(el.className).trim().split(/\s+/).join('.'):'')});
});
return {seen:seen, bad:bad}; })()"""


HOME = [{"name": "Law", "pid": "p", "courses": [
    {"title": "Torts", "href": "t.html", "sub": "3 units", "courseId": "a", "units": ["#4a9eff", "#f43f5e", "#10b981"]},
    {"title": "Contracts", "href": "t.html", "sub": "0 units", "courseId": "b", "units": []}]}]


@pytest.fixture(scope="module")
def site(outline, tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("holosite")
    (d / "t.html").write_text(outline, encoding="utf-8")
    (d / "h.html").write_text(pages.build_home(HOME), encoding="utf-8")
    (d / "s.html").write_text(_build("outline", layout="solar"), encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    name, text = holo.holo_asset()
    (d / "holo" / name).write_text(text, encoding="utf-8")
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")
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


@pytest.fixture(params=["chromium", "webkit"])
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


@pytest.mark.parametrize("dark", [True, False])
@pytest.mark.parametrize("size", [(1400, 900), (390, 844)])
def test_text_on_a_timeline_page_meets_aa_in_both_themes_and_sizes(browser, site, dark, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 500, is_mobile=size[0] < 500)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(500)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false"))
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo') && !!document.getElementById('alto-holo-css')")
    assert pg.evaluate("window._altoStyle.get()") == "holo"
    pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false"))
    pg.wait_for_timeout(300)
    res = pg.evaluate(AUDIT_JS)
    assert res["seen"] > 8, res
    assert not res["bad"], res["bad"][:12]
    # square, like Retro: the cards and the bar's chips have no round corners
    assert pg.evaluate("[...document.querySelectorAll('#world .node-card')].every(c => getComputedStyle(c).borderTopLeftRadius === '0px')")
    # remembered per timeline, and Classic comes back clean
    pg.evaluate("window._altoStyle.set('classic')")
    assert not pg.evaluate("document.documentElement.classList.contains('alto-holo')")
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("dark", [True, False])
@pytest.mark.parametrize("size", [(1400, 900), (390, 844)])
def test_text_on_the_homepage_meets_aa_in_both_themes_and_sizes(browser, site, dark, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=size[0] < 500, is_mobile=size[0] < 500)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + "/h.html")
    pg.wait_for_timeout(500)
    pg.evaluate("localStorage.clear()")
    assert pg.evaluate("window._altoStyle.list") == ["classic", "retro", "holo"]   # the homepage offers all three (alto-home: Classic | Retro)
    pg.evaluate("window._altoStyle.set('holo')")
    pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false"))
    pg.wait_for_timeout(1200)   # (the colours ease over; measure once they have settled)
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo') && !document.documentElement.classList.contains('alto-retro')")
    res = pg.evaluate(AUDIT_JS)
    assert res["seen"] > 4, res
    assert not res["bad"], res["bad"][:12]
    # square cards, like Retro's homepage (retro.HOME_CSS re-inked)
    assert pg.evaluate("[...document.querySelectorAll('.course-tile:not(.new-tile)')].every(c => getComputedStyle(c).borderTopLeftRadius === '0px')")
    pg.evaluate("window._altoStyle.set('retro')")
    assert pg.evaluate("document.documentElement.classList.contains('alto-retro') && !document.documentElement.classList.contains('alto-holo')")
    assert not errors, errors


def test_the_bars_follow_the_top_bar_rule(browser, site):
    """clear_top.py: no bar backgrounds where the page clears its top (html.ct-on: a desktop timeline); where it keeps them (a detail page,
    a phone: no ct-on) Holographic's bars are solid."""
    clear = ("rgba(0, 0, 0, 0)", "transparent")
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear(); window._altoStyle.set('holo')")
    pg.wait_for_timeout(400)
    css = lambda sel, p: pg.evaluate("getComputedStyle(document.querySelector(%r)).%s" % (sel, p))
    assert pg.evaluate("document.documentElement.classList.contains('ct-on')")
    assert css("#title-bar", "backgroundColor") in clear and css("#nav", "backgroundColor") in clear
    assert css("#title-text", "backgroundColor") not in clear            # the name keeps its own solid plate instead
    assert css("#glass-slab", "borderTopWidth") == "0px"                  # no unit-colour sheet running up under the cleared bars
    pg.evaluate("document.documentElement.classList.add('detail-open')")
    pg.wait_for_timeout(300)
    assert not pg.evaluate("document.documentElement.classList.contains('ct-on')")
    assert css("#title-bar", "backgroundColor") not in clear
    ctx.close()


def test_a_system_keeps_its_planets_round(browser, site):
    """Luke, 2026-10-30: "we don't want square planets": Holographic squares the cards, never a System's bodies."""
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(site + "/s.html")
    pg.wait_for_timeout(500)
    pg.evaluate("localStorage.clear(); window._altoSolarStyles.set('holo')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo')")
    radii = pg.evaluate("[...document.querySelectorAll('#world .node[data-solar] .node-card')].map(c => getComputedStyle(c).borderTopLeftRadius)")
    assert radii and all(r == "50%" for r in radii), radii
    ctx.close()



# ── the style's own backgrounds (holo_backgrounds.py) ──────────────────────

def test_each_holographic_background_keeps_its_ground_under_the_text_tokens():
    """Text sits on solid plates, but the free labels' ink must still read on each scene's ground (top, middle, bottom), light and dark."""
    e = hb.client_entries()
    assert len(e) == 6 and all(v["k"] == "h" and v["g"] == "Holographic" for v in e.values())
    for hid, v in e.items():
        for theme, key in (("light", "l"), ("dark", "d")):
            grounds = re.findall(r"#[0-9a-f]{6}", v[key]["b"].rsplit("linear-gradient", 1)[1])
            assert len(grounds) == 3, hid
            for g in grounds:
                for ink in ("tx", "mu", "ac"):
                    assert holo.contrast(holo.TOKENS[theme][ink], g) >= 4.5, (hid, theme, ink, g)


def test_the_backgrounds_ride_in_the_hosted_script_not_the_page(outline):
    assert "h-neon-rain" in holo.ASSET and "h-neon-rain" not in outline


def test_holographic_backgrounds_are_offered_only_in_holographic(browser, site):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear()")
    heads = "[...document.querySelectorAll('#bg-panel .bg-h')].map(h => h.textContent)"
    pg.click("#bg-toggle")
    pg.wait_for_timeout(400)
    assert "Holographic" not in pg.evaluate(heads)                       # Classic: not offered
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(500)
    assert "Holographic" in pg.evaluate(heads)                           # Holographic: its own section
    pg.click('.bg-tile[data-bg="h-neon-rain"]')
    pg.wait_for_timeout(400)
    cls = "document.documentElement.classList"
    assert pg.evaluate(cls + ".contains('alto-bg-h')")
    assert "data:image/svg+xml" in pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').backgroundImage")
    assert pg.evaluate("getComputedStyle(document.getElementById('page-bg'), '::before').display") != "none"
    pg.evaluate("window._altoStyle.set('classic')")                      # back in Classic: no background, no section; the choice is kept
    pg.wait_for_timeout(400)
    assert not pg.evaluate(cls + ".contains('alto-bg')") and "Holographic" not in pg.evaluate(heads)
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(400)
    assert pg.evaluate(cls + ".contains('alto-bg-h')")
    assert pg.evaluate(heads).count("Holographic") == 1
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("width", [1440, 1024])
def test_back_sits_on_the_clef_line_and_clear_of_the_header_line(browser, site, width):
    """Luke, 2026-11-01 (Holographic CASES index): Back sat lower than the name and wordmark with its bottom edge on the header line. Retro lowers
    the whole header row 8px and Back with it; Holographic keeps the row where Classic has it, so Back must not carry the shift."""
    ctx = browser.new_context(viewport={"width": width, "height": 900})
    pg = ctx.new_page()
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(500)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(400)
    pg.evaluate("showDetail('node', NODE_ORDER[0])")
    pg.wait_for_timeout(900)
    r = pg.evaluate("""()=>{const q=s=>document.querySelector(s).getBoundingClientRect(), b=q('#desk-back'), m=q('#title-bar .brand-mark'), t=q('#title-bar'), w=q('#title-bar .brand-word');
      return {bc:b.top+b.height/2, mc:m.top+m.height/2, wc:w.top+w.height/2, bb:b.bottom, barb:t.bottom, on:document.documentElement.classList.contains('alto-holo'),
              disp:getComputedStyle(document.getElementById('desk-back')).display}}""")
    assert r["on"] and r["disp"] != "none", r
    assert abs(r["bc"] - r["mc"]) < 0.6 and abs(r["bc"] - r["wc"]) < 0.6, r
    assert r["bb"] <= r["barb"] - 4, r
    ctx.close()


# ── the homepage's Projector (PROJ_CSS, Art's SPEC-holo-home-A) ──────────────────────────────────────────────────

FMTS = ["timeline", "lanes", "outline", "system", "palace", "building", "world"]


def _live_home(n):
    """The homepage with n live cards (the cloud stub), one format each in turn."""
    pageset = [dict(key=f"k{i}", title=f"T{i}", heading=f"Course {i}", project="Law", fmt=FMTS[i % 7], tid=f"t{i}", units=["#4a9eff", "#e8a87c"][: i % 2 + 1]) for i in range(n)]
    stub = ("<script>window.AltoCloud={enabled:true,known:true,user:{uid:'u1',email:'a@b.c',displayName:'A'},listPages:()=>Promise.resolve(%s),"
            "listShared:()=>Promise.resolve([]),signOut:()=>Promise.resolve(),createTimeline:()=>Promise.resolve({}),signIn:()=>Promise.resolve(),"
            "getPage:()=>Promise.resolve(''),forgetShare:()=>Promise.resolve()};</script>" % json.dumps(pageset))
    return pages.build_home([]).replace("<head>", "<head>" + stub, 1)


@pytest.fixture(scope="module")
def psite(tmp_path_factory):
    if pw is None:
        pytest.skip("Playwright is not installed")
    d = tmp_path_factory.mktemp("holoproj")
    (d / "h7.html").write_text(_live_home(7), encoding="utf-8")
    (d / "h45.html").write_text(_live_home(45), encoding="utf-8")
    (d / "holo").mkdir()
    (d / "retro").mkdir()
    name, text = holo.holo_asset()
    (d / "holo" / name).write_text(text, encoding="utf-8")
    name, text = retro.retro_asset()
    (d / "retro" / name).write_text(text, encoding="utf-8")
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


def test_the_projector_css_is_compositor_only_and_has_a_reduced_motion_still():
    css = holo.css()
    kf = re.findall(r"@keyframes (ho-\w+)\{(.*?)\}\}?(?=@keyframes|\s*@media|\s*html|\s*$|\})", css)
    assert {k for k, _ in kf} == {"ho-spin", "ho-pulse", "ho-scan", "ho-logo"}
    body = "".join(re.findall(r"@keyframes ho-\w+\{.*?\}\}", css))
    assert body and not re.search(r"filter|box-shadow|background-position|width|height|top|left|margin", body), body
    rm = css[css.index("@media (prefers-reduced-motion:reduce)"):]
    assert "animation:none" in rm and "rotateY(28deg)" in rm
    assert holo.JS.count("HOMEB") == 1 and "_altoRetroHome" in holo.ASSET and "hp-stage" in holo.ASSET


@pytest.mark.parametrize("dark", [True, False])
def test_the_homepage_projector_draws_three_layers_and_off_restores_the_plate(browser, psite, dark):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(psite + "/h7.html")
    pg.wait_for_timeout(800)
    pg.evaluate("localStorage.clear()")
    pg.evaluate("document.documentElement.classList.toggle('dark', %s)" % ("true" if dark else "false"))
    grab = "()=>document.getElementById('projects-wrap').innerHTML"
    classic = pg.evaluate(grab)
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(1200)
    got = pg.evaluate("""()=>[...document.querySelectorAll('.course-tile:not(.new-tile)')].map(t=>{const e=t.querySelector('.tile-emblem'), cs=getComputedStyle(e.querySelector('.hp-spin'));
        return {layers:e.querySelectorAll('svg.hp-l').length, role:e.getAttribute('role'), label:e.getAttribute('aria-label'), tab:e.getAttribute('tabindex'), tip:e.querySelector('.hp-tip').textContent,
                anim:cs.animationName, dur:cs.animationDuration, scan:getComputedStyle(t.querySelector('.hp-scan i')).animationName, fmt:t.getAttribute('data-fmt'), noFlat:getComputedStyle(e.querySelector(':scope > svg')).display}})""")
    names = ["Timeline", "Timeline · Horizontal", "Outline", "System", "Memory Map", "Memory Blueprint", "Memory Atlas"]
    assert [g["label"] for g in got] == names and [g["tip"] for g in got] == names
    assert all(g["layers"] == 3 and g["role"] == "img" and g["tab"] == "0" and g["anim"] == "ho-spin" and g["dur"] == "10s" and g["scan"] == "ho-scan" and g["noFlat"] == "none" for g in got), got[:2]
    # light AND dark: every word on the new plates meets AA
    res = pg.evaluate(AUDIT_JS)
    assert res["seen"] > 10 and not res["bad"], res["bad"][:10]
    # the tooltip shows on hover and on focus
    pg.hover(".course-tile .tile-emblem")
    pg.wait_for_timeout(350)
    assert pg.evaluate("+getComputedStyle(document.querySelector('.hp-tip')).opacity") == 1
    pg.mouse.move(5, 5)
    pg.focus(".course-tile .tile-emblem")
    pg.keyboard.press("Shift+Tab")
    pg.keyboard.press("Tab")
    pg.wait_for_timeout(350)
    assert pg.evaluate("document.activeElement.classList.contains('tile-emblem')") and pg.evaluate("+getComputedStyle(document.querySelector('.hp-tip')).opacity") == 1
    # Holographic -> Retro keeps Retro's plate and drops the projector; -> Classic restores the cards exactly
    pg.evaluate("window._altoStyle.set('retro')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelectorAll('.hp-stage').length") == 0 and pg.evaluate("document.querySelectorAll('.t-main').length") == 7
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelectorAll('.hp-stage').length") == 7
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(500)
    assert pg.evaluate(grab) == classic
    assert not errors, errors
    pg.close()


def test_the_homepage_projector_reduced_motion_and_phone(browser, psite):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','holo')}catch(e){}")
    pg.goto(psite + "/h7.html")
    pg.wait_for_timeout(1200)
    r = pg.evaluate("""()=>{const cs=getComputedStyle(document.querySelector('.hp-spin'));
        return [cs.animationName, cs.transform, getComputedStyle(document.querySelector('.hp-scan')).display, getComputedStyle(document.querySelector('.hp-base i + i')).display]}""")
    assert r[0] == "none" and r[2] == "none" and r[3] == "none"
    m = re.search(r"matrix3d\(([^,]+),\s*[^,]+,\s*([^,]+),", r[1])
    assert abs(float(m.group(1)) - 0.8829) < .001 and abs(float(m.group(2)) + 0.4695) < .001      # rotateY(28deg): still, but solid
    ctx.close()
    ph = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pg = ph.new_page()
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','holo')}catch(e){}")
    pg.goto(psite + "/h7.html")
    pg.wait_for_timeout(1200)
    assert pg.evaluate("document.documentElement.classList.contains('alto-holo')")
    assert pg.evaluate("document.querySelectorAll('.hp-stage,.hp-tip,.hp-scan,.t-main').length") == 0       # a phone's page: nothing added
    ph.close()


def test_a_big_homepage_turns_the_first_forty_and_pauses_what_is_off_screen(browser, psite):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','holo')}catch(e){}")
    pg.goto(psite + "/h45.html")
    pg.wait_for_timeout(1500)
    n = pg.evaluate("[document.querySelectorAll('.course-tile.hp').length, document.querySelectorAll('.course-tile.hp-still').length, document.querySelectorAll('.course-tile.hp-off').length]")
    assert n[0] == 45 and n[1] == 5 and n[2] > 20, n                       # (the 5 after the 40th are a still frame; the tiles below the fold are paused)
    assert pg.evaluate("getComputedStyle(document.querySelector('.course-tile.hp-off .hp-spin')).animationPlayState") == "paused"
    assert pg.evaluate("getComputedStyle(document.querySelector('.course-tile.hp-still .hp-spin')).animationName") == "none"
    pg.close()


@pytest.mark.parametrize("style", ["retro", "holo"])
def test_the_home_plate_leaves_the_page_alone_once_drawn(browser, psite, style):
    """(Retro home B rewrote its own numbers every frame, waking its observer about 1,700 times a second at rest.)"""
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.add_init_script("try{localStorage.setItem('alto-bg-home-v1-style','%s')}catch(e){}" % style)
    pg.goto(psite + "/h7.html")
    pg.wait_for_timeout(1500)
    pg.evaluate("window.__m=0; new MutationObserver(r=>{window.__m+=r.length}).observe(document.documentElement,{childList:true,subtree:true,characterData:true})")
    pg.wait_for_timeout(1500)
    assert pg.evaluate("window.__m") == 0
    pg.close()


# ── the Alto marks and dark only (Luke, 2026-11-01) ──

def test_the_logo_turns_on_the_same_motion_budget_and_holds_still_under_reduced_motion():
    css = holo.css()
    kf = re.search(r"@keyframes ho-logo\{(.*?)\}\}", css).group(1)
    assert "transform" in kf and not re.search(r"filter|box-shadow|width|height|top|left|margin|opacity", kf), kf
    assert "ho-logo 10s linear infinite" in css            # the format symbols' 10 s turn
    assert re.search(r"prefers-reduced-motion:reduce\)\{[^@]*brand-mark[^}]*animation:none", css)
    assert "hp-hid #title-bar svg.brand-mark{animation-play-state:paused" in css   # a hidden tab stops it


@pytest.mark.parametrize("page", ["t", "h"])
def test_the_alto_marks_wear_the_light_and_the_clef_turns_on_a_computer_and_a_phone(browser, site, page):
    js = """()=>{var m=document.querySelector('.brand-mark'),w=document.querySelector('.brand-word'),a=m&&getComputedStyle(m);
      return {anim:a&&a.animationName,fill:w&&getComputedStyle(w.querySelector('.alto-word')||w).fill,ghost:a&&a.filter.indexOf('255, 95, 210')>-1}}"""
    for size, touch in (((1400, 900), False), ((390, 844), True)):
        ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, has_touch=touch, is_mobile=touch)
        pg = ctx.new_page()
        pg.goto(site + "/" + page + ".html")
        pg.wait_for_timeout(400)
        pg.evaluate("window._altoStyle.set('holo')")
        pg.wait_for_timeout(900)
        r = pg.evaluate(js)
        assert r["anim"] == "ho-logo" and r["ghost"] and r["fill"] != 'url("#altoWordG")', (size, r)
        pg.evaluate("window._altoStyle.set('classic')")
        pg.wait_for_timeout(300)
        r = pg.evaluate(js)
        assert r["anim"] == "none" and r["fill"].startswith("url"), (size, r)
        ctx.close()
    ctx = browser.new_context(viewport={"width": 1400, "height": 900}, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.goto(site + "/" + page + ".html")
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(700)
    assert pg.evaluate("getComputedStyle(document.querySelector('.brand-mark')).animationName") == "none"
    ctx.close()


@pytest.mark.parametrize("page", ["t", "h"])
def test_holographic_is_dark_only_on_a_computer_and_the_readers_theme_comes_back(browser, site, page):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    pg = ctx.new_page()
    pg.goto(site + "/" + page + ".html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear(); document.documentElement.classList.remove('dark')")
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.documentElement.classList.contains('dark')")
    assert pg.evaluate("getComputedStyle(document.getElementById('mode-toggle')).display") == "none"
    pg.evaluate("document.documentElement.classList.remove('dark')")            # anything that tries the light theme
    pg.wait_for_timeout(200)
    assert pg.evaluate("document.documentElement.classList.contains('dark')")
    pg.evaluate("window._altoStyle.set('classic')")
    pg.wait_for_timeout(300)
    assert not pg.evaluate("document.documentElement.classList.contains('dark')")   # the theme the reader had
    assert pg.evaluate("getComputedStyle(document.getElementById('mode-toggle')).display") != "none"
    pg.evaluate("window._altoStyle.set('holo')")                                    # and Retro to Holographic keeps it dark
    pg.evaluate("window._altoStyle.set('retro')")
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.documentElement.classList.contains('dark')")
    ctx.close()


def test_holographic_on_a_phone_keeps_its_light_dark_button_and_its_theme(browser, site):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    pg.goto(site + "/t.html")
    pg.wait_for_timeout(400)
    pg.evaluate("localStorage.clear(); document.documentElement.classList.remove('dark')")
    pg.evaluate("window._altoStyle.set('holo')")
    pg.wait_for_timeout(600)
    assert not pg.evaluate("document.documentElement.classList.contains('dark')")
    assert pg.evaluate("getComputedStyle(document.getElementById('mode-toggle')).display") != "none"
    ctx.close()
