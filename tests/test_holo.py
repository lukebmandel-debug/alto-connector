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

from alto.build import backgrounds_import as bi, holo, pages, palace_assets, retro   # noqa: E402
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
    pg.wait_for_timeout(500)
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
