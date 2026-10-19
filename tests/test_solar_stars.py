"""The Star chart's skin (alto/build/solar_stars.py): a glowing star, planets
that look like planets, cratered moons, tiny craft, a night sky.

Static checks on what pages carry (only orbit pages; Hub & spoke byte for
byte as without the skin), then a real browser (Chromium and WebKit through
Playwright; skipped without them): the skin's pieces, textures the same on
every load, lighting toward the sun, the per-frame contract with solar_draw
(window._altoSkinTick), the frame budget, edit mode flat, no errors.
Geometry is read in #world layout px (style.left/top), never screen px."""
import copy
import gzip
import math
import re
import sys
from pathlib import Path

import pytest

import alto.build.blocks as blocks
from alto.build.builder import build_timeline, load_brief
from alto.build.solar_stars import STARS_CSS, STARS_JS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_solar_draw import SMALL, SMALL_LINKS, solar_doc  # noqa: E402

# 52 bodies in three systems (3 suns, 14 planets, 24 moons, 11 satellites)
BIG = [[[2, 1], [0, 0, 0], [1], [0, 0], []], [[0, 0], [3], [0, 1], []], [[1, 1], [0], [0, 0, 0], [2], [1], []]]


def _page(units=SMALL, style="orbit", links=SMALL_LINKS):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(units, style, links))))
    return html


# ── what the pages carry ─────────────────────────────────────────────────────

def test_every_hub_and_spoke_page_carries_the_skin_and_nothing_else_does():
    """Round 5: one format, two looks switched in the page, so the skin rides
    on every solar page (whichever look it opens in) and on no other page."""
    for page in (_page(), _page(style="spoke")):
        assert page.count("window._altoSkinTick=") == 1 and page.count("@keyframes sk-tw") == 1
        # after the renderer, so it can wrap its layout and lines
        assert page.index("window._altoSolarMount=function") < page.index("window._altoSkinTick=")
    d = solar_doc(SMALL, "spoke")
    d["brief"]["layout"] = "tree"
    tree, _ = build_timeline(*load_brief(d))
    for s in ("_altoSkinTick", "alto-stars", "sk-sky", "@keyframes sk-"):
        assert s not in tree, s


def test_a_page_without_solar_is_byte_identical_whatever_the_skin(monkeypatch):
    d = solar_doc(SMALL, "spoke")
    d["brief"]["layout"] = "tree"
    before, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    monkeypatch.setattr(blocks, "STARS_JS", "/*SKIN-JS-MARK*/")
    monkeypatch.setattr(blocks, "STARS_CSS", "/*SKIN-CSS-MARK*/")
    after, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    assert after == before
    assert "SKIN-JS-MARK" in _page(style="spoke") and "SKIN-CSS-MARK" in _page()


def test_the_skin_is_small_and_safari_safe():
    size = len(gzip.compress((STARS_JS + STARS_CSS).encode("utf-8"), 9))
    assert size < 13000, size
    # no SVG mask, no CSS / SVG filter or blur layer, nothing moves a node by a transform
    assert "<mask" not in STARS_JS and "'mask'" not in STARS_JS and "mask" not in STARS_CSS
    assert "blur(" not in STARS_CSS and "filter:url" not in STARS_CSS and "feGaussian" not in STARS_JS
    assert re.findall(r"(\w+(?:\.\w+)?)\.style\.transform=", STARS_JS) == ["k.lit", "k.tail", "k.craft"]
    assert not re.search(r"\.style\.(left|top)=", STARS_JS)                 # reads them, never writes


def test_motion_respects_reduced_motion_edit_mode_and_print():
    assert "@media (prefers-reduced-motion:reduce)" in STARS_CSS
    red = STARS_CSS.split("@media (prefers-reduced-motion:reduce)")[1].split("}")[0]
    for c in (".sk-cor", ".sk-prom", ".sk-tw", ".sk-gran"):
        assert c in red
    assert "html.alto-editing .sk-cor" in STARS_CSS and "@media print" in STARS_CSS
    assert "alto-editing" in STARS_JS                           # no ticks in edit mode


# ── in a browser ─────────────────────────────────────────────────────────────

try:
    import playwright.sync_api as pw
except ImportError:
    pw = None


@pytest.fixture(scope="module", params=["chromium", "webkit"])
def browser(request):
    if pw is None:
        pytest.skip("Playwright is not installed")
    with pw.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:
            try:
                if request.param != "chromium":
                    raise e
                b = p.chromium.launch(channel="chrome")
            except Exception:
                pytest.skip(f"no {request.param}: {e}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = tmp_path_factory.mktemp("stars")
    out = {}
    for name, html in (("orbit", _page()), ("big", _page(BIG, links=[("u1-p1", "u2-p2")])), ("spoke", _page(style="spoke"))):
        f = d / f"{name}.html"
        f.write_text(html, encoding="utf-8")
        out[name] = f
    out["mock"] = d / "mock.html"
    out["mock"].write_text(_mock(_page(BIG, links=[])), encoding="utf-8")
    return out


LOOKS = {"u1-p3": "blackhole", "u2-p1": "comet", "u2-p4": "asteroid", "u3-p1-m1": "asteroid"}


def _mock(html):
    """LEAD's coming plan keys, mocked into a built page: a galactic core when
    there are 2+ systems, looks on some nodes, an asteroid belt."""
    import json
    at = html.index("window._ALTO_SOLAR=") + len("window._ALTO_SOLAR=")
    S, end = json.JSONDecoder().raw_decode(html[at:])
    s0, s1 = S["systems"][0], S["systems"][1]
    S["core"] = {"x": s0["cx"] + 900, "y": (s0["cy"] + s1["cy"]) / 2, "r": 70}
    for i, lk in LOOKS.items():
        S["nodes"][i]["look"] = lk
    pl = s0["planets"]
    S["belts"] = [{"r": (pl[1]["r"] + pl[2]["r"]) / 2, "w": 90, "n": 300, "seed": 3, "system": 0}]
    return html[:at] + json.dumps(S) + html[at + end:]


def _open(browser, f, reduced=False, wait=1500, theme=None):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950}, reduced_motion="reduce" if reduced else "no-preference")
    if theme:
        ctx.add_init_script("try{localStorage.setItem('alto-theme-v1','%s')}catch(e){}" % theme)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    # a file:// page cannot load the cloud script beside it; anything else is an error
    pg.on("console", lambda m: m.type == "error" and "alto-cloud.js" not in m.text + str((m.location or {}).get("url", ""))
          and errs.append(m.text))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(wait)
    return pg, errs


def _settled(pg, ms=8000):
    pg.wait_for_function("() => window._altoSkinStats && window._altoSkinStats.get().pending === 0", timeout=ms)


SKIN = r"""() => {
  var o={stars:document.documentElement.classList.contains('alto-stars'), sky:document.querySelectorAll('#world .sk-sky').length,
    cor:document.querySelectorAll('.sk-sky canvas.sk-cor').length, tw:document.querySelectorAll('.sk-sky .sk-tw').length, b:{}};
  document.querySelectorAll('#world .node[data-solar]').forEach(function(n){
    var c=n.querySelector('.node-card');
    o.b[n.id.slice(5)]={role:n.getAttribute('data-solar'), kids:[].filter.call(c.children, function(e){ return e.classList.contains('sk') && getComputedStyle(e).display!=='none'; })
      .map(function(e){ return e.className.replace(/^sk /, ''); }), bg:getComputedStyle(c).backgroundColor, bdf:getComputedStyle(c).webkitBackdropFilter||getComputedStyle(c).backdropFilter||'none'};
  });
  return o; }"""


def test_every_body_is_dressed_for_its_role_and_spoke_is_not(browser, pages):
    pg, errs = _open(browser, pages["orbit"])
    s = pg.evaluate(SKIN)
    assert s["stars"] and s["sky"] == 1 and s["cor"] == 3 and s["tw"] >= 12, s
    for i, b in s["b"].items():
        k = b["kids"]
        if b["role"] == "sun":
            assert k[0] == "sk-sun" and k.count("sk-gran") + k.count("sk-gran b") == 2, (i, k)
        elif b["role"] == "sat":
            assert k == ["sk-craft"], (i, k)
        else:
            assert "sk-tex" in k[0] or "sk-tex" in k[1], (i, k)
            assert ("sk-lit m" if b["role"] == "moon" else "sk-lit") in k, (i, k)
        assert b["bdf"] in ("none", ""), (i, b)                 # no backdrop blur behind a moving body
    assert not errs, errs
    pg.context.close()
    pg, errs = _open(browser, pages["spoke"])
    s = pg.evaluate(SKIN)
    assert not s["stars"] and s["sky"] == 0 and all(not b["kids"] for b in s["b"].values()), s
    assert not errs, errs
    pg.context.close()


def test_textures_are_the_same_on_every_load(browser, pages):
    seen = []
    for _ in range(2):
        pg, errs = _open(browser, pages["orbit"])
        _settled(pg)
        h = pg.evaluate("window._altoSkinStats.hashes()")
        assert not errs, errs
        assert len(h) >= 20 and all(h.values()), h
        seen.append(h)
        pg.context.close()
    assert seen[0] == seen[1]


LIGHT = r"""() => { var o={}, S=window._ALTO_SOLAR;
  document.querySelectorAll('#world .node[data-solar=planet],#world .node[data-solar=moon]').forEach(function(n){
    var id=n.id.slice(5), sun=id; while(S.nodes[sun].parent) sun=S.nodes[sun].parent;
    var s=document.getElementById('node-'+sun), l=n.querySelector('.sk-lit'), m=/rotate\(([-\d.]+)deg\)/.exec(l.style.transform||'');
    o[id]={want:Math.atan2(parseFloat(s.style.top)-parseFloat(n.style.top), parseFloat(s.style.left)-parseFloat(n.style.left))*180/Math.PI, got:m ? +m[1] : null}; });
  return o; }"""


def _off(a, b):
    return abs((a - b + 540) % 360 - 180)


def test_the_light_comes_from_the_sun_as_they_orbit(browser, pages):
    pg, errs = _open(browser, pages["orbit"], wait=2500)
    for _ in range(2):
        for i, v in pg.evaluate(LIGHT).items():
            assert v["got"] is not None and _off(v["got"], v["want"]) < 2.5, (i, v)
        pg.wait_for_timeout(2500)                               # they moved on; the light did too
    assert not errs, errs
    pg.context.close()


def test_solar_draws_tick_contract(browser, pages):
    """window._altoSkinTick(plan, bodies, t) takes the bodies' positions from
    the renderer's loop; the skin's own fallback then stands down."""
    pg, errs = _open(browser, pages["orbit"])
    r = pg.evaluate(r"""() => { var S=window._ALTO_SOLAR, p='u1-p1', s=S.nodes['u1'], P=window.WORLD_PAD_TOP||40, B={};
      B[p]={rx:s.x+300, ry:s.y+P};                    /* due east of its sun: lit from the west */
      B['u1']={rx:s.x, ry:s.y+P};
      window._altoSkinTick(S, B, 12.5);
      var l=document.querySelector('#node-u1-p1 .sk-lit').style.transform;
      return {l:l, ext:window._altoSkinStats.get().ext}; }""")
    assert r["ext"] and _off(float(re.search(r"([-\d.]+)deg", r["l"]).group(1)), 180) < 0.5, r
    assert not errs, errs
    pg.context.close()


def test_a_body_is_still_hit_where_it_is_drawn(browser, pages):
    pg, errs = _open(browser, pages["orbit"])
    pg.evaluate("() => document.getElementById('node-u1-p1').scrollIntoView({block:'center', inline:'center'})")
    pg.wait_for_timeout(300)
    hit = pg.evaluate(r"""() => { var c=document.querySelector('#node-u1-p1 .node-card'), r=c.getBoundingClientRect(),
        e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2), f=document.elementFromPoint(r.left+r.width*.5, r.top+r.height*.08);
      return [e && e.closest('.node') && e.closest('.node').id, f && f.closest('.node') && f.closest('.node').id]; }""")
    assert hit == ["node-u1-p1", "node-u1-p1"], hit
    pg.context.close()


def test_edit_mode_is_flat_and_still(browser, pages):
    pg, errs = _open(browser, pages["orbit"])
    pg.evaluate("() => document.documentElement.classList.add('alto-editing')")
    pg.wait_for_timeout(600)
    s = pg.evaluate(SKIN)
    for i, b in s["b"].items():
        assert not b["kids"], (i, b)
        assert b["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"), (i, b)   # a flat disc of its colour
    anim = pg.evaluate("() => [].map.call(document.querySelectorAll('.sk-gran,.sk-cor,.sk-tw'), function(e){ return getComputedStyle(e).animationName; })")
    assert set(anim) <= {"none"}, set(anim)
    assert not errs, errs
    pg.context.close()


def test_reduced_motion_stops_the_sky(browser, pages):
    pg, errs = _open(browser, pages["orbit"], reduced=True)
    anim = pg.evaluate("() => [].map.call(document.querySelectorAll('.sk-gran,.sk-cor,.sk-prom,.sk-tw'), function(e){ return getComputedStyle(e).animationName; })")
    assert anim and set(anim) == {"none"}, set(anim)
    pg.context.close()


def test_light_theme_keeps_a_night_sky_and_light_lines(browser, pages):
    pg, errs = _open(browser, pages["orbit"], theme="light")
    r = pg.evaluate(r"""() => { var sl=getComputedStyle(document.getElementById('glass-slab')), p=document.querySelector('#river-svg path[data-edge]');
      return {dark:document.documentElement.classList.contains('dark'), bg:sl.backgroundImage, line:p && p.getAttribute('stroke'),
        ink:getComputedStyle(document.querySelector('#node-u1-p1 .sol-face')).color}; }""")
    assert not r["dark"] and "gradient" in r["bg"], r
    lum = [int(v) for v in re.findall(r"\d+", r["line"])[:3]]
    assert sum(lum) / 3 > 110, r                                # a line readable on the night sky
    assert r["ink"].replace(" ", "") in ("rgb(243,246,255)",), r
    assert not errs, errs
    pg.context.close()


def test_a_phone_has_no_skin(browser, pages):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True,
                              user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"))
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(pages["orbit"].as_uri())
    pg.wait_for_timeout(1200)
    st = pg.evaluate("() => ({stars:document.documentElement.classList.contains('alto-stars'), sk:document.querySelectorAll('.sk-sky,.node-card>.sk').length})")
    assert not st["stars"] and st["sk"] == 0, st
    assert not errs, errs
    ctx.close()


FRAMES = r"""async (ms) => { var d=[], last=null, t0=performance.now(); window._altoSkinStats.reset();
  await new Promise(function(res){ requestAnimationFrame(function f(ts){ if(last!=null) d.push(ts-last); last=ts; if(performance.now()-t0<ms) requestAnimationFrame(f); else res(); }); });
  d.sort(function(a, b){ return a-b; });
  return {n:d.length, p50:d[Math.floor(d.length*.5)], p95:d[Math.floor(d.length*.95)], skin:window._altoSkinStats.get()}; }"""


def test_frame_budget_with_52_bodies(browser, pages):
    """52 bodies turning in a busy view: the skin's own work per frame stays
    small, and frames keep coming (headless, so a loose bound: the real check
    is the A/B numbers in the report)."""
    if browser.browser_type.name != "webkit":
        pytest.skip("the budget is Safari's (WebKit)")
    pg, errs = _open(browser, pages["big"])
    _settled(pg)
    pg.evaluate("""() => { var c=document.getElementById('canvas'), s=document.getElementById('node-u1');
      c.scrollLeft=parseFloat(s.style.left)-c.clientWidth/2; c.scrollTop=parseFloat(s.style.top)-c.clientHeight/2; }""")
    pg.wait_for_timeout(800)
    assert pg.evaluate("window._altoSolarGeo().moving")
    r = pg.evaluate(FRAMES, 3000)
    assert r["skin"]["n"] > 40 and r["skin"]["p95"] <= 2, r
    assert r["p50"] < 34, r
    assert not errs, errs
    pg.context.close()


SWITCH = r"""async (cls) => { var de=document.documentElement;
  de.classList.remove('alto-solar-stars', 'alto-solar-plain'); de.classList.add(cls);
  await new Promise(function(r){ setTimeout(r, 120); });
  return {stars:de.classList.contains('alto-stars'), sky:document.querySelectorAll('#world .sk-sky').length,
    trails:document.querySelectorAll('#solar-svg .sk-trails,#solar-svg .sk-rg').length,
    shown:[].filter.call(document.querySelectorAll('#world .node-card>.sk'), function(e){ return getComputedStyle(e).display!=='none'; }).length}; }"""


def test_the_look_switch_puts_the_skin_on_and_takes_it_off(browser, pages):
    """Plain look: no skin at all (no sky, no trails, every card its plain
    self); back to Star chart: all of it again, once (no doubled trails)."""
    pg, errs = _open(browser, pages["orbit"])
    a = pg.evaluate(SWITCH, "alto-solar-plain")
    assert not a["stars"] and a["sky"] == 0 and a["trails"] == 0 and a["shown"] == 0, a
    b = pg.evaluate(SWITCH, "alto-solar-stars")
    c = pg.evaluate(SWITCH, "alto-solar-stars")
    assert b["stars"] and b["sky"] == 1 and b["shown"] > 20 and b["trails"] > 0, b
    assert c == b, (b, c)
    # the look switch's own API, when the renderer has one, wins over the classes
    d = pg.evaluate(r"""async () => { var fn=null, cur='plain';
      window._altoSolarLook={get:function(){ return cur; }, set:function(v){ cur=v; if(fn) fn(v); }, onChange:function(f){ fn=f; return function(){}; }};
      document.documentElement.classList.add('x-poke');              /* any class change re-reads the look */
      await new Promise(function(r){ setTimeout(r, 120); });
      return document.documentElement.classList.contains('alto-stars'); }""")
    assert d is False
    assert not errs, errs
    pg.context.close()


def test_motion_off_pauses_the_sky(browser, pages):
    pg, errs = _open(browser, pages["orbit"])
    st = pg.evaluate(r"""async () => { var on=true, fn=null;
      window._altoSolarMotion={get:function(){ return on; }, set:function(v){ on=!!v; if(fn) fn(on); }, onChange:function(f){ fn=f; return function(){}; }};
      document.documentElement.classList.add('x-poke');
      await new Promise(function(r){ setTimeout(r, 80); });
      window._altoSolarMotion.set(false);
      var a=getComputedStyle(document.querySelector('.sk-tw')).animationPlayState;
      window._altoSolarMotion.set(true);
      return [a, getComputedStyle(document.querySelector('.sk-tw')).animationPlayState]; }""")
    assert st == ["paused", "running"], st
    assert not errs, errs
    pg.context.close()


def test_black_holes_comets_asteroids_core_and_belts(browser, pages):
    pg, errs = _open(browser, pages["mock"])
    _settled(pg)
    s = pg.evaluate(SKIN)
    assert s["b"]["u1-p3"]["kids"] == ["sk-rb", "sk-bh", "sk-rf"], s["b"]["u1-p3"]
    assert s["b"]["u2-p1"]["kids"][0] == "sk-tail" and "sk-lit m" in s["b"]["u2-p1"]["kids"]
    assert "sk-lit m a" in s["b"]["u2-p4"]["kids"] and "sk-lit m a" in s["b"]["u3-p1-m1"]["kids"]
    r = pg.evaluate(r"""() => { var S=window._ALTO_SOLAR, n=document.getElementById('node-u2-p1'), u=document.getElementById('node-u2'),
        t=/rotate\(([-\d.]+)deg\)/.exec(n.querySelector('.sk-tail').style.transform);
      return {tail:t ? +t[1] : null, away:Math.atan2(parseFloat(n.style.top)-parseFloat(u.style.top), parseFloat(n.style.left)-parseFloat(u.style.left))*180/Math.PI,
        core:document.querySelectorAll('.sk-sky .sk-cacc,.sk-sky .sk-hz').length, grains:document.querySelectorAll('#solar-svg .sk-belt circle').length}; }""")
    assert r["tail"] is not None and _off(r["tail"], r["away"]) < 2.5, r      # a comet's tail points away from its sun
    assert r["core"] == 2 and r["grains"] == 300, r
    assert not errs, errs
    pg.context.close()


def test_an_enlarged_body_drops_the_skin_and_gets_it_back(browser, pages):
    """Focus (the renderer's enlarged disc) shows the node's content, not the
    planet; back home the planet is there again."""
    pg, errs = _open(browser, pages["orbit"])
    shown = "() => [].filter.call(document.querySelectorAll('#node-u1-p1 .node-card>.sk'), function(e){ return getComputedStyle(e).display!=='none'; }).length"
    assert pg.evaluate(shown) >= 2
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(900)
    assert pg.evaluate(shown) == 0
    pg.evaluate("() => window.exitFocus()")
    pg.wait_for_timeout(1500)
    assert pg.evaluate(shown) >= 2
    assert not errs, errs
    pg.context.close()
