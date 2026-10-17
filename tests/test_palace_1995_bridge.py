"""1.9.95 bridges: a deck with design elements (alto/build/palace_bridges.py), measured on the screen like the rest of the page.

Static guards on the CSS / JS, and a real-browser check of the module's geometry (a river, three streets) in WebKit and Chromium when a
Playwright build can be launched (the _qa wkvenv); skipped otherwise. Offline; nothing here touches the network, Firebase or ALTO_*."""
import json
import re
import subprocess
from pathlib import Path

import pytest

from alto.build import palace, palace_bridges

CSS, JS = palace_bridges.BRIDGE_CSS, palace_bridges.BRIDGE_JS
WKPY = Path.home() / "Desktop/Alto Development/_qa/wkvenv/bin/python"


def test_the_module_is_wired_into_the_page():
    assert palace_bridges.BRIDGE_CSS in palace.PALACE_CSS and palace_bridges.BRIDGE_JS in palace.PALACE_JS
    js = palace.PALACE_JS
    assert "window._palBr.init({M:M, el:el, pts:pts, pin:pin});" in js
    assert "var plan=window._palBr.under(bridges, st, d);" in js and "window._palBr.over(bridges, plan);" in js
    # the deck keeps its order: pier / pilaster / cable, rail lines, deck, joints, then the street's own tube, then abutments and towers
    i = js.index("var plan=window._palBr.under(bridges, st, d);")
    assert js.index("tube(bridges, d,", i) < js.index("window._palBr.over(bridges, plan);", i)
    assert JS.index("pl-br-edge") < JS.index("pl-casing") < JS.index("'br-hang':'br-joint'")


def test_every_size_is_a_screen_size():
    """strokes and dashes are calc(var(--tw) * Npx); towers and abutments are pin()s -- no bare px, no CSS transform on SVG content"""
    for m in re.finditer(r"(stroke-width|stroke-dasharray):([^;}]*)", CSS):
        assert "var(--tw,1)" in m.group(2), m.group(0)
    assert "transform" not in CSS
    assert "E.pin(parent,'br-abut'" in JS and "E.pin(parent,'br-tower'" in JS
    assert "transform:'rotate(" in JS                                  # a rotation ATTRIBUTE inside the scaled pin, no lengths in it
    assert "<mask" not in CSS + JS and "mask" not in CSS


def test_decoration_hides_far_out_but_not_the_structure():
    assert ".pal-svg.far .pl-bridges :is(.br-pil,.br-joint,.br-hang){display:none;}" in CSS
    assert "br-cable" not in CSS.split(".far")[1] and "br-abut" not in CSS.split(".far")[1]


def test_both_colour_modes_have_every_bridge_variable():
    for v in ("--pal-br-fine", "--pal-br-joint", "--pal-br-hang"):
        assert len(re.findall(re.escape(v) + ":", CSS)) == 2        # html{} and html.dark{}
    assert CSS.index("html{--pal-br-fine") < CSS.index("html.dark{--pal-br-fine")


def test_what_a_bridge_crosses_picks_its_character():
    assert "sp.w>=WIDE" in JS and "WIDE=200" in JS                     # the wide river (Delaware, 230) -> suspension
    assert "SUS_NAME=/franklin|whitman|betsy ross" in JS               # a named big one over anything wide enough to count
    assert "type=sus?'sus':sp?'arch':'via'" in JS                      # arch over the narrow river, viaduct over a rail / road
    assert "if(type==='arch') pt('pl-br-pier')" in JS and "plan.type==='sus'" in JS


_PAGE = """<!doctype html><svg id=s xmlns="http://www.w3.org/2000/svg"></svg><script>
var NS='http://www.w3.org/2000/svg';
function el(t,a,p){var e=document.createElementNS(NS,t);for(var k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e;}
function pts(a){var s='';for(var i=0;i<a.length;i+=2)s+=(i?'L':'M')+a[i]+' '+a[i+1];return s;}
function pin(parent,cls,x,y){var g=el('g',{'class':cls,transform:'translate('+x+' '+y+')'},parent);return el('g',{'class':'pl-sc'},g);}
%s
var M={river:[{n:'Narrow',w:100,p:[1000,0,1000,2000]},{n:'Wide',w:230,p:[5000,0,5000,2000]}]};
window._palBr.init({M:M,el:el,pts:pts,pin:pin});
var g=el('g',{'class':'pl-bridges'},document.getElementById('s')), out={};
[['Market',[400,500,1700,500],0],['Ben Franklin Bridge',[4500,900,6000,900],1],['Overpass',[3000,300,3080,300],0],['Kinked',[400,1500,900,1500,1100,1600,1700,1600],0]].forEach(function(b){
  var st={n:b[0],p:b[1],o:1,br:b[2]}, plan=window._palBr.under(g,st,pts(st.p)); window._palBr.over(g,plan);
  out[b[0]]={type:plan.type,a:Math.round(plan.a),b:Math.round(plan.b),L:Math.round(plan.L)}; });
out.counts={abut:g.querySelectorAll('.br-abut').length,tower:g.querySelectorAll('.br-tower').length,hang:g.querySelectorAll('.br-hang').length,joint:g.querySelectorAll('.br-joint').length,
  pil:g.querySelectorAll('.br-pil').length,cable:g.querySelectorAll('.br-cable').length,pier:g.querySelectorAll('.pl-br-pier').length,edge:g.querySelectorAll('.pl-br-edge').length,casing:g.querySelectorAll('.pl-casing').length};
out.plans=window._palBr.plans.length;
document.title=JSON.stringify(out);
</script>"""


def _run(engine):
    code = (
        "import sys,json,tempfile,pathlib\n"
        "from playwright.sync_api import sync_playwright\n"
        "html=sys.argv[1]; eng=sys.argv[2]\n"
        "with sync_playwright() as p:\n"
        "    b=p.webkit.launch() if eng=='webkit' else p.chromium.launch(channel='chrome')\n"
        "    pg=b.new_page(); errs=[]; pg.on('pageerror',lambda e: errs.append(str(e)))\n"
        "    pg.set_content(html); print(json.dumps({'t':pg.title(),'errs':errs})); b.close()\n")
    r = subprocess.run([str(WKPY), "-c", code, _PAGE % JS, engine], capture_output=True, text=True, timeout=120)
    if r.returncode:
        pytest.skip("no %s here: %s" % (engine, r.stderr[-200:]))
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not WKPY.exists(), reason="the QA Playwright venv is not here")
@pytest.mark.parametrize("engine", ["webkit", "chromium"])
def test_the_geometry_in_a_real_engine(engine):
    r = _run(engine)
    assert r["errs"] == []
    o = json.loads(r["t"])
    # Market crosses the 100-wide narrow river at x=1000 (water 944..1056 with the 6 px rim): an arch bridge, decoration only there
    m = o["Market"]
    assert m["type"] == "arch" and 880 < m["a"] + 400 < 960 and 1040 < m["b"] + 400 < 1130
    # the Ben Franklin crosses the 230-wide river at x=5000: a suspension bridge
    f = o["Ben Franklin Bridge"]
    assert f["type"] == "sus" and 365 < f["a"] < 380 and 622 < f["b"] < 636 and f["L"] == 1500
    # a short street over no river is a viaduct whose whole deck is decorated, and a bend is followed
    assert o["Overpass"]["type"] == "via" and o["Overpass"]["a"] == 0 and o["Overpass"]["b"] == 80
    assert o["Kinked"]["type"] == "arch"
    c = o["counts"]
    assert c["tower"] == 2 and c["cable"] == 1 and c["hang"] == 1                 # towers and cables only on the suspension bridge
    assert c["abut"] == 8 and c["pier"] == 2 and c["pil"] == 3 and c["joint"] == 3
    assert c["edge"] == 4 and c["casing"] == 4                                    # the deck keeps its two rail lines and its band
    assert o["plans"] == 4
