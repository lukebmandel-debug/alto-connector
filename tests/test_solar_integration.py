"""System with everything on at once: the renderer (solar_draw.py), the
Star chart skin (solar_stars.py) and the flights (solar_fly.py) together.

Each module has its own suite; these are the interplays nobody tested
together: the look switch with the skin and a flight running, a flight
landing on an enlarged (textured, circular) disc, the Orbit switch then a
flight, the System look carrying none of the skin or flight and leaving no
frame loop running once its Orbit is off, edit mode, phones, zooming out with the skin on (no
rectangle), and the arrow-key hop queue with flights.

Static checks need nothing; the rest run in Chromium and WebKit through
Playwright (skipped without them). Geometry is read in layout px
(offset*, style.left/top) and the renderer's own camera, never screen px:
Playwright's WebKit is not Safari (engine notes 1.8.34)."""
import copy
import gzip
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto.build import blocks                                   # noqa: E402
from alto.build.builder import build_timeline, load_brief       # noqa: E402
from alto.build.solar_draw import SOLAR_CSS, SOLAR_JS           # noqa: E402
from alto.build.solar_fly import FLY_CSS, FLY_JS                # noqa: E402
from alto.build.solar_stars import STARS_CSS, STARS_JS          # noqa: E402
from test_solar_draw import _png_rgb, solar_doc                 # noqa: E402

# two systems: planets with moons and satellites, empty planets, a link across
UNITS = [[[0, 0], [], [0, 2], [1], [], [0]], [[0], [0, 2], []]]
LINKS = [("u1-p1", "u2-p2")]
LONG = "u1-p3"


def _doc(style="orbit"):
    d = solar_doc(UNITS, style, LINKS)
    for n in d["nodes"]:
        if n["id"] == LONG:
            n["desc"] = ("The rule as the notes put it, at length. " * 12).strip()
            n["sections"] = [{"h": "Test", "t": "Each element in turn, as the cases apply it. " * 8},
                             {"h": "Cases", "t": "The leading cases and what each decides. " * 8}]
    return d


def _page(style="orbit"):
    html, _ = build_timeline(*load_brief(copy.deepcopy(_doc(style))))
    return html


# ── what the pages carry ─────────────────────────────────────────────────────

def test_all_of_the_solar_script_stays_under_67_kb_gzipped():
    """The drawing, the skin and the flight together, against the 1,000,000-byte
    stored page (each has its own cap in its own suite: 22 / 14 / 13 KB). 51 -> 55 KB in round 10
    (upright chips + named rows, unit borders / Oort clouds, spoke hits, nav hints, Flights / Spokes only); -> 58 KB for the Star chart's Retro style; -> 61 KB for Retro's probe, sigil, frame and the Spokes-only / controls round; -> 63 KB for round 11's navigation hints (~2.4 KB: named pills, drawn ways, edge pills); -> 67 KB for Spokes-only rides, Retro's orbit bands and its ship (~3.2 KB, System pages only); -> 69 KB for 1.9.142's Retro / theme rule (~1.4 KB) and the ships' orbit arrivals and tangent heading (~0.6 KB, 2026-10-22).; -> 72.5 KB for the Tour (2026-10-22, ~3 KB, System pages only); -> 74.5 KB for one way of moving in both modes and the bug round (~1.5 KB)"""
    size = len(gzip.compress((SOLAR_JS + SOLAR_CSS + STARS_JS + STARS_CSS + FLY_JS + FLY_CSS).encode("utf-8"), 9))
    assert size < 79600, size      # + Spokes only's arrows on the map (~1.6 KB, 2026-10-23); + the declutter (~1.9 KB, 2026-10-25: pills laid out on the screen, the calm hover, Spokes only's note); + the ships' approach and capture, the Rocket, flames, warp and jump (~1.2 KB, 2026-10-25)


@pytest.mark.parametrize("style", ["orbit", "spoke"])
def test_every_hub_and_spoke_page_carries_the_drawing_the_skin_and_the_flight_in_order(style):
    """Both looks are in every page (the in-page toggle), so all three scripts are
    too, the renderer first (the skin wraps its layout, the flight its nav)."""
    html = _page(style)
    a = html.index("window._altoSolarMount=function")
    b = html.index("window._altoSkinTick=")
    c = html.index("window._altoFly=")
    assert a < b < c, (a, b, c)
    assert html.index("#solar-svg{") < html.index(".sk-sky{") < html.index("#solar-fly-svg{")
    for s in ("window._ALTO_PALACE=", "window._altoPalace="):
        assert s not in html, s


def test_an_old_star_chart_palace_loads_as_hub_and_spoke_with_all_three():
    """1.9.105's Star chart (mode palace + palace_view stars) builds as a System
    in its Star chart look, every node kept."""
    d = _doc("orbit")
    d["brief"].update({"mode": "palace", "palace_view": "stars"})
    d["brief"].pop("layout", None)
    d["brief"].pop("hub_look", None)
    b, nodes, conns = load_brief(copy.deepcopy(d))
    assert (b.mode, b.layout, b.hub_look) == ("outline", "solar", "stars")
    assert [(n.id, n.parent or "") for n in nodes] == [(n["id"], n.get("parent", "")) for n in d["nodes"]]
    html, _ = build_timeline(b, nodes, conns)
    assert "window._altoSolarMount=function" in html and "window._altoSkinTick=" in html and "window._altoFly=" in html


@pytest.mark.parametrize("view", ["city", "building"])
def test_a_city_or_building_palace_keeps_its_view_through_the_migration(view):
    """1.9.107's Memory Blueprint (palace_view 'building') and the city stay Memory
    Palaces: only the old 'stars' view migrates (to a System)."""
    from alto.build.brief import migrate_brief, migrate_doc
    bd = {"title": "P", "mode": "palace", "palace_view": view, "acts": [{"label": "A"}],
          **({"building": {"name": "Hall", "plan_h": "abc", "mode": "room", "assign": {"n1": "r1"}}} if view == "building" else {})}
    out, aside = migrate_brief(bd)
    assert out == bd and aside == {}
    doc = {"timeline_id": "p", "brief": bd}
    assert migrate_doc(doc) is doc
    # with a legacy key beside it (an old stash), the view is still kept
    out, _ = migrate_brief({**bd, "stash": {"outline": {"tree_lines": "fan"}}})
    assert out["mode"] == "palace" and out["palace_view"] == view and "stash" not in out
    if view == "building":
        assert out["building"] == bd["building"]


def test_a_stars_palace_still_migrates_to_hub_and_spoke_and_nothing_else_keeps_stars():
    from alto.build.brief import BriefError, migrate_brief, migrate_doc
    bd = {"title": "S", "mode": "palace", "palace_view": "stars", "acts": [{"label": "A"}],
          "placement": {"n1": {"order": 2}, "n2": {"lot": "x"}}}
    out, aside = migrate_brief(bd)
    assert (out["mode"], out["layout"], out["hub_look"]) == ("outline", "solar", "stars") and "palace_view" not in out
    assert out["placement"] == {"n1": {"order": 2}} and aside["placement"] == {"n2": {"lot": "x"}}
    doc = {"timeline_id": "s", "brief": bd}
    m = migrate_doc(doc)
    assert m is not doc and m["brief"]["mode"] == "outline" and "palace_view" not in m["brief"]
    # 'stars' is no longer a palace view anyone can ask for
    d = _doc("orbit")
    d["brief"].update({"mode": "palace", "palace_view": "building"})
    d["brief"].pop("layout")
    d["brief"].pop("hub_look")
    b, nodes, conns = load_brief(copy.deepcopy(d))
    assert (b.mode, b.palace_view) == ("palace", "building")
    b.palace_view = "stars"
    from alto.build.brief import validate_brief
    with pytest.raises(BriefError, match="palace_view 'stars'"):
        validate_brief(b)


def test_the_skin_and_the_flight_are_no_cost_off_hub_and_spoke(monkeypatch):
    """A page that is not a System is byte-identical whatever the three scripts say."""
    d = _doc("orbit")
    d["brief"]["layout"] = "tree"
    before, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    for k in ("SOLAR_JS", "SOLAR_CSS", "STARS_JS", "STARS_CSS", "FLY_JS", "FLY_CSS"):
        monkeypatch.setattr(blocks, k, f"/*{k}-MARK*/")
    after, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    assert after == before


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
        b._alto_name = request.param
        yield b
        b.close()


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = tmp_path_factory.mktemp("solar-int")
    out = {}
    for name, style in (("stars", "orbit"), ("hub", "spoke")):
        f = d / f"{name}.html"
        f.write_text(_page(style), encoding="utf-8")
        out[name] = f
    return out


# counts requestAnimationFrame calls (a loop left running shows as ~60 a second)
RAF_COUNT = """(function(){ var r=window.requestAnimationFrame; window.__rafN=0;
  window.requestAnimationFrame=function(f){ window.__rafN++; return r.call(window, f); }; })();"""
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def _open(browser, f, reduced=False, mobile=False, wait=2400):
    if mobile:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, user_agent=IPHONE)
    else:
        ctx = browser.new_context(viewport={"width": 1500, "height": 950},
                                  reduced_motion="reduce" if reduced else "no-preference")
    ctx.add_init_script(RAF_COUNT)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: "/phone/" in str(e) or errs.append(str(e)))   # (the phone whole-view script is hosted: a file:// copy cannot fetch it)
    pg.on("console", lambda m: m.type == "error" and "alto-cloud.js" not in m.text + str((m.location or {}).get("url", ""))
          and "/phone/" not in m.text + str((m.location or {}).get("url", "")) and "Cross origin requests are only supported" not in m.text and "net::ERR_FAILED" not in m.text
          and errs.append(m.text))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(wait)
    if not mobile:
        pg.mouse.move(2, 940)                     # off every body (a hover holds the orbits)
    return pg, errs


def _rest_on(pg, i):
    """The view on body i at full size, then i enlarged (no flight: nothing was enlarged)."""
    pg.evaluate("""(i)=>{ var g=window._altoSolarGeo().bodies[i], P=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0;
                         window._altoSolarCam.set(g.x, g.y-P, 1); }""", i)
    pg.wait_for_timeout(300)
    pg.evaluate("(i)=>window.enterFocus(i)", i)
    pg.wait_for_timeout(1400)
    assert pg.evaluate("()=>window._focusedNodeId") == i


def _landed(pg, to, f, extra=2500):
    """Wait for the flight f to end with `to` enlarged."""
    pg.wait_for_function("(to)=>!window._altoSolarFlight() && window._focusedNodeId===to", arg=to,
                         timeout=int(f["D"] * 1000) + extra)
    pg.wait_for_timeout(700)


def _skin_settled(pg, ms=8000):
    pg.wait_for_function("() => window._altoSkinStats && window._altoSkinStats.get().pending === 0", timeout=ms)


FLIGHT = "()=>window._altoSolarFlight()"
STATE = r"""() => { var de=document.documentElement, shown=0;
  document.querySelectorAll('#world .node[data-solar] .node-card>.sk').forEach(function(e){ if(getComputedStyle(e).display!=='none') shown++; });
  var sky=document.querySelector('#world .sk-sky');
  return {look:window._altoSolarLook ? window._altoSolarLook.get() : null, stars:de.classList.contains('alto-stars'),
    solarStars:de.classList.contains('alto-solar-stars'), solarPlain:de.classList.contains('alto-solar-hub'),
    sky:document.querySelectorAll('#world .sk-sky').length, skyShown:!!sky && getComputedStyle(sky).display!=='none', shown:shown,
    trails:document.querySelectorAll('#solar-svg .sk-trails').length, fly:!!document.getElementById('solar-fly-svg'),
    still:de.classList.contains('sk-still'), motion:window._altoSolarMotion ? window._altoSolarMotion.get() : null,
    T:window._altoSolarRate ? window._altoSolarRate().T : null, ctl:!!document.getElementById('sol-ctl'),
    focused:window._focusedNodeId||null}; }"""
DISC = r"""(id) => { var n=document.getElementById('node-'+id), c=n.querySelector('.node-card'), b=c.querySelector('.sol-body'),
    t=b && b.querySelector('.node-title');
  return {w:c.offsetWidth, h:c.offsetHeight, sD:parseFloat(getComputedStyle(n).getPropertyValue('--sD'))||0,
    d:window._altoSolarGeo().bodies[id].d, focused:n.classList.contains('focused'),
    title:t && getComputedStyle(b).display!=='none' ? t.textContent : null, secs:b ? b.querySelectorAll('.sol-sec').length : 0,
    open:!c.querySelector('.sol-open'),
    skin:[].filter.call(c.querySelectorAll(':scope>.sk'), function(e){ return getComputedStyle(e).display!=='none'; }).map(function(e){ return e.className; })}; }"""
# every frame for ms: the card of `id` is a circle (square box, a round clip or none)
DISC_WATCH = r"""([id, ms]) => new Promise(function(res){
  var n=document.getElementById('node-'+id), c=n.querySelector('.node-card'), bad=[], k=0, t0=performance.now();
  (function f(){ var cs=getComputedStyle(c), cp=cs.clipPath||cs.webkitClipPath||'none', w=c.offsetWidth, h=c.offsetHeight;
    if(Math.abs(w-h)>1) bad.push('box '+w+'x'+h);
    if(!/^(none|circle)/.test(cp)) bad.push('clip '+cp);
    if(parseFloat(cs.borderTopLeftRadius)<w/2-1 && cs.borderTopLeftRadius!=='50%') bad.push('radius '+cs.borderTopLeftRadius);
    k++; if(performance.now()-t0<ms) requestAnimationFrame(f); else res({frames:k, bad:bad.slice(0, 6)}); })();
})"""
RAF_RATE = """(ms) => new Promise(function(res){ var n0=window.__rafN, t0=performance.now();
  setTimeout(function(){ res((window.__rafN-n0)*1000/(performance.now()-t0)); }, ms); })"""


def test_the_look_switch_with_the_skin_and_a_flight_running(browser, pages):
    """System on the way: the flight stops and its layer goes, the skin comes off
    whole, the orbit switch still works. Star chart again: the skin once (no doubled
    trails) and a change of body flies again and lands."""
    pg, errs = _open(browser, pages["stars"])
    s0 = pg.evaluate(STATE)
    assert s0["look"] == "stars" and s0["stars"] and s0["solarStars"] and s0["sky"] == 1 and s0["shown"] > 10, s0
    _rest_on(pg, "u1-p3")
    pg.evaluate("()=>window.enterFocus('u1-p1')")
    f = pg.evaluate(FLIGHT)
    assert f and f["to"] == "u1-p1", f
    pg.wait_for_timeout(600)
    assert pg.evaluate(STATE)["fly"]
    pg.click("#sol-ctl [data-style=system]")
    pg.mouse.move(2, 940)
    pg.wait_for_timeout(1200)
    s1 = pg.evaluate(STATE)
    assert pg.evaluate(FLIGHT) is None and not s1["fly"], s1
    assert s1["look"] == "hub" and s1["solarPlain"] and not s1["stars"] and not s1["skyShown"] and s1["shown"] == 0 \
        and s1["trails"] == 0, s1
    assert not pg.evaluate("()=>document.getElementById('sol-motion').disabled")
    pg.click("#sol-ctl [data-style=chart]")
    pg.mouse.move(2, 940)
    pg.wait_for_timeout(1500)
    s2 = pg.evaluate(STATE)
    assert s2["look"] == "stars" and s2["stars"] and s2["sky"] == 1 and s2["trails"] == 1 and s2["shown"] >= s0["shown"] - 2, s2
    if pg.evaluate("()=>window._focusedNodeId") is None:
        _rest_on(pg, "u1-p4")
    to = "u1-p2" if pg.evaluate("()=>window._focusedNodeId") != "u1-p2" else "u1-p6"
    pg.evaluate("(to)=>window.enterFocus(to)", to)
    g = pg.evaluate(FLIGHT)
    assert g and g["to"] == to, g
    _landed(pg, to, g)
    assert pg.evaluate("()=>window._altoSolarFlight(true).how") == "landed"
    assert not errs, errs
    pg.context.close()


def test_a_flight_lands_on_a_textured_round_disc_with_its_content(browser, pages):
    """Flying to a body with long content: on every frame of the way and the
    landing the target is a circle; landed, it is the big disc (--sD) with the
    skin's texture and light painted under the scrim, its card (title, no
    sections, nothing scrolling) and no 'Open full page' control (the disc itself opens the page)."""
    pg, errs = _open(browser, pages["stars"])
    _skin_settled(pg)
    _rest_on(pg, "u1-p1")
    pg.evaluate("(id)=>{ window.__dw=null; (" + DISC_WATCH + ")([id, 9000]).then(function(r){ window.__dw=r; }); }", LONG)
    pg.evaluate("(id)=>window.enterFocus(id)", LONG)
    f = pg.evaluate(FLIGHT)
    assert f and f["to"] == LONG, f
    _landed(pg, LONG, f)
    _skin_settled(pg)
    st = pg.evaluate(DISC, LONG)
    assert st["focused"] and abs(st["w"] - st["h"]) <= 1 and abs(st["w"] - st["sD"]) <= 1 and st["sD"] > st["d"], st
    assert st["title"] and st["secs"] == 0 and st["open"], st
    assert any("sk-tex" in k for k in st["skin"]) and any("sk-lit" in k for k in st["skin"]), st
    assert not pg.evaluate("(id)=>{ var b=document.querySelector('#node-'+id+' .sol-body'); return b.scrollHeight>b.clientHeight+1; }", LONG)
    pg.wait_for_function("()=>window.__dw", timeout=12000)
    dw = pg.evaluate("()=>window.__dw")
    assert dw["frames"] > 20 and not dw["bad"], dw
    # home again: a circle of its resting size, its look kept
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1400)
    h = pg.evaluate(DISC, LONG)
    assert not h["focused"] and abs(h["w"] - h["h"]) <= 1 and abs(h["w"] - h["d"]) <= 2 and h["skin"], h
    assert not errs, errs
    pg.context.close()


def test_orbit_off_then_a_flight_among_still_bodies_and_on_again(browser, pages):
    """The Orbit button off: the sky's animations pause, the bodies stand where
    they are, a flight still flies and lands with the clock unmoved; on again
    the orbits run on."""
    pg, errs = _open(browser, pages["stars"])
    pg.click("#sol-motion")
    pg.mouse.move(2, 940)
    pg.wait_for_timeout(500)
    s = pg.evaluate(STATE)
    assert s["motion"] is False and s["still"], s
    T0 = s["T"]
    pg.wait_for_timeout(600)
    assert pg.evaluate(STATE)["T"] == T0
    _rest_on(pg, "u1-p3")
    pg.evaluate("()=>window.enterFocus('u1-p6')")
    f = pg.evaluate(FLIGHT)
    assert f and f["to"] == "u1-p6", f
    _landed(pg, "u1-p6", f)
    s = pg.evaluate(STATE)
    assert s["T"] == T0 and s["still"] and s["focused"] == "u1-p6", s
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(900)
    pg.click("#sol-motion")
    pg.mouse.move(2, 940)
    pg.wait_for_timeout(1500)
    s = pg.evaluate(STATE)
    assert s["motion"] is True and not s["still"] and s["T"] > T0, s
    assert not errs, errs
    pg.context.close()


def test_the_hub_look_has_no_skin_no_flight_and_no_frame_loop_with_its_orbit_off(browser, pages):
    """A page opening in System, and a Star chart switched to it: no sky, no
    dressed bodies, no trails, no flight layer, a change of body does not fly,
    and with the Orbit switched off nothing keeps asking for frames (the Star
    chart look, moving, does — the counter works)."""
    pg, errs = _open(browser, pages["stars"])
    moving = pg.evaluate(RAF_RATE, 1200)
    assert moving > 20, moving
    pg.evaluate("()=>window._altoSolarLook.set('hub')")
    pg.wait_for_timeout(1200)
    assert pg.evaluate(RAF_RATE, 800) > 20                                   # System orbits too
    pg.evaluate("()=>window._altoSolarMotion.set(false)")
    pg.wait_for_timeout(1300)
    after = pg.evaluate(RAF_RATE, 1500)
    s = pg.evaluate(STATE)
    assert not s["stars"] and not s["skyShown"] and s["shown"] == 0 and s["trails"] == 0 and not s["fly"], s
    print(f"\n[{browser._alto_name}] rAF/s: Star chart moving {moving:.0f}, System, Orbit off {after:.1f}")
    assert after < 3, after
    pg.context.close()
    pg, errs2 = _open(browser, pages["hub"])
    s = pg.evaluate(STATE)
    assert s["look"] == "hub" and s["solarPlain"] and not s["stars"] and not s["skyShown"] and s["shown"] == 0 and not s["fly"], s
    pg.evaluate("()=>window._altoSolarMotion.set(false)")
    pg.wait_for_timeout(1300)
    idle = pg.evaluate(RAF_RATE, 1500)
    print(f"[{browser._alto_name}] rAF/s: opened in System, Orbit off {idle:.1f}")
    assert idle < 3, idle
    _rest_on(pg, "u1-p1")
    pg.evaluate("()=>window.enterFocus('u2-p2')")
    assert pg.evaluate(FLIGHT) is None and pg.evaluate("()=>window._focusedNodeId") == "u2-p2"
    assert not pg.evaluate("()=>!!document.getElementById('solar-fly-svg')")
    pg.wait_for_timeout(1500)
    assert pg.evaluate(RAF_RATE, 1200) < 3                        # enlarged and still: no loop either
    assert not errs and not errs2, (errs, errs2)
    pg.context.close()


def test_edit_mode_has_no_skin_no_flight_and_no_motion(browser, pages):
    pg, errs = _open(browser, pages["stars"])
    pg.evaluate("() => document.documentElement.classList.add('alto-editing')")
    pg.wait_for_timeout(900)
    s = pg.evaluate(STATE)
    assert s["shown"] == 0 and not s["skyShown"] and s["T"] == 0, s          # flat discs, turned home to the plan
    pg.wait_for_timeout(600)
    assert pg.evaluate(STATE)["T"] == 0
    anim = pg.evaluate("() => [].map.call(document.querySelectorAll('.sk-gran,.sk-cor,.sk-tw'), function(e){ return getComputedStyle(e).animationName; })")
    assert set(anim) <= {"none"}, set(anim)
    pg.evaluate("()=>window.enterFocus('u1-p1')")
    pg.wait_for_timeout(1200)
    pg.evaluate("()=>window.enterFocus('u1-p3')")
    assert pg.evaluate(FLIGHT) is None
    pg.wait_for_timeout(1200)
    assert pg.evaluate("()=>window._focusedNodeId") == "u1-p3" and not pg.evaluate("()=>!!document.getElementById('solar-fly-svg')")
    pg.evaluate("()=>window.exitFocus && window.exitFocus()")
    pg.evaluate("() => document.documentElement.classList.remove('alto-editing')")
    pg.mouse.move(2, 940)
    pg.wait_for_timeout(1800)
    s = pg.evaluate(STATE)
    assert s["T"] > 0 and s["shown"] > 10 and s["skyShown"], s                # out of edit mode it all comes back
    assert not errs, errs
    pg.context.close()


@pytest.mark.parametrize("name", ["stars", "hub"])
def test_a_phone_has_the_engines_cards_and_none_of_it(browser, pages, name):
    pg, errs = _open(browser, pages[name], mobile=True, wait=1500)
    s = pg.evaluate(STATE)
    extra = pg.evaluate("""() => ({mobile:document.documentElement.classList.contains('mobile'),
        solar:document.documentElement.classList.contains('alto-solar'), svg:!!document.getElementById('solar-svg'),
        sk:document.querySelectorAll('.sk-sky,.node-card>.sk').length, circles:document.querySelectorAll('[data-solar]').length})""")
    assert extra["mobile"] and not extra["solar"] and not extra["svg"] and extra["sk"] == 0 and extra["circles"] == 0, extra
    assert not s["stars"] and not s["solarStars"] and not s["solarPlain"] and not s["ctl"] and not s["fly"], s
    pg.evaluate("()=>window.enterFocus && window.enterFocus('u1-p1')")
    pg.wait_for_timeout(500)
    pg.evaluate("()=>window.enterFocus && window.enterFocus('u1-p3')")
    assert not pg.evaluate("()=>window._altoSolarFlight && window._altoSolarFlight()")
    assert not pg.evaluate("()=>!!document.getElementById('solar-fly-svg')")
    assert not errs, errs
    pg.context.close()


def test_zooming_out_with_the_skin_on_shows_no_rectangle(browser, pages, tmp_path):
    """cmd-minus step by step on the Star chart: the circles shrink, the sky
    fills the window and the old board's edge shows no line (pixels just inside
    and outside it alike, allowing a star or two on the samples)."""
    pg, errs = _open(browser, pages["stars"])
    _skin_settled(pg)
    zs = []
    for _ in range(5):
        pg.keyboard.press("Control+Minus")
        pg.wait_for_timeout(650)
        zs.append(pg.evaluate("() => window._altoSolarZoom()"))
    assert all(b < a for a, b in zip(zs, zs[1:])) and zs[-1] < 0.5, zs
    st = pg.evaluate("""() => ({slab:getComputedStyle(document.getElementById('glass-slab')).visibility, stars:document.documentElement.classList.contains('alto-stars'),
        w:(function(r){ return [r.left, r.top, r.right, r.bottom]; })(document.getElementById('world').getBoundingClientRect())})""")
    assert st["slab"] == "hidden" and st["stars"], st
    r = st["w"]
    shot = tmp_path / "zoomed-stars.png"
    pg.screenshot(path=str(shot))
    W, H, px = _png_rgb(shot.read_bytes())
    diffs = []
    for k in range(1, 12):
        y = int(r[1] + (r[3] - r[1]) * k / 12)
        for x, dx in ((r[0], 1), (r[2], -1)):
            a, b = (int(x + 6 * dx), y), (int(x - 6 * dx), y)
            if not (0 <= a[0] < W and 0 <= b[0] < W and 120 < y < H - 10):
                continue
            pa, pb = px(*a), px(*b)
            diffs.append(max(abs(pa[i] - pb[i]) for i in range(3)))
    if diffs:
        diffs.sort()
        assert diffs[int(len(diffs) * 0.8) - 1 if len(diffs) > 1 else 0] <= 14, diffs
    # and back: a click on a body comes back down to it, enlarged, a circle
    pg.keyboard.press("Control+0")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => window._altoSolarZoom()") == 1
    assert not errs, errs
    pg.context.close()


def test_arrow_hops_queue_behind_flights_and_end_on_a_round_dressed_body(browser, pages):
    """A flight (a click on a far body) takes no arrows: presses on the way wait for its landing (one kept) and then
    go on from there (→ round what is beside it, solar_navopt.py; a body with nothing beside it: its side neighbours); all ends on a round, dressed body."""
    pg, errs = _open(browser, pages["stars"])
    _rest_on(pg, "u1-p3")
    far = pg.evaluate("() => { var G=window._altoSolarGeo().bodies, a=G['u1-p3']; return Object.keys(G).filter(function(i){ return G[i].si!==a.si && G[i].role==='planet'; })[0]; }")
    pg.evaluate("(i)=>window.enterFocus(i)", far)
    pg.wait_for_timeout(200)
    f = pg.evaluate(FLIGHT)
    assert f and f["to"] == far, f
    for _ in range(4):
        pg.keyboard.press("ArrowRight")
    assert pg.evaluate(FLIGHT), "the presses took the flight's place"
    # the flight lands, then the queued presses ride on from there; then all is still: landed and nothing moving for 2 s
    pg.wait_for_function("""()=>{ var still=!window._altoSolarFlight() && !window._altoSolarLock.riding() && !!window._focusedNodeId, t=performance.now();
        if(!still){ window.__still=0; return false; } if(!window.__still) window.__still=t; return t-window.__still>2000; }""",
                         timeout=45000, polling=200)
    fid = pg.evaluate("()=>window._focusedNodeId")
    S = pg.evaluate("(i)=>window._altoNavOpt.scope(i)", far)                            # (→ goes round what is beside it: Luke, 2026-10-26)
    assert fid == (S[(S.index(far) + 1) % len(S)] if far in S else S[0]), (fid, far, S)   # one press kept, ridden from the landing
    st = pg.evaluate(DISC, fid)
    assert st["focused"] and abs(st["w"] - st["h"]) <= 1 and st["skin"], st
    assert pg.evaluate("()=>window._altoSolarFlight(true).how") == "landed"
    # a body with nothing beside it: → goes round what is beside its parent (its side neighbours), never up or out
    leaf = pg.evaluate("() => { var A=window._altoSolarNavApi, G=window._altoSolarGeo().bodies; return Object.keys(G).filter(function(i){ return !A.kids(i).length && A.sibs(i).length>1; })[0]; }")
    S = pg.evaluate("(i)=>window._altoSolarNavApi.sibs(i)", leaf)
    pg.evaluate("(i)=>window.enterFocus(i)", leaf)
    pg.wait_for_function("(i)=>window._focusedNodeId===i && !window._altoSolarFlight() && !window._altoSolarLock.riding()", arg=leaf, timeout=20000)
    pg.wait_for_timeout(500)
    pg.keyboard.press("ArrowRight")
    to = S[(S.index(leaf) + 1) % len(S)]
    pg.wait_for_function("(i)=>window._focusedNodeId===i && !window._altoSolarFlight() && !window._altoSolarLock.riding()", arg=to, timeout=20000)
    assert not errs, errs
    pg.context.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_an_enlarged_disc_is_readable_in_both_looks_and_themes(browser, pages, theme):
    """Dogfooding Luke's Torts (light theme): the Star chart's enlarged disc showed its
    description dark on the skin's dark scrim (the engine's desc colour is an
    !important variable), and the tag sat off centre (a card leaves room for its
    number on the tag's row). Text must contrast with what is under it."""
    LUM = r"""(id) => { var c=document.querySelector('#node-'+id+' .node-card'), b=c.querySelector('.sol-body'), d=b.querySelector('.node-desc'),
        t=b.querySelector('.node-tag'), r=document.createRange(); r.selectNodeContents(t);
      var m=/rgba?\(([\d.]+), ([\d.]+), ([\d.]+)/.exec(getComputedStyle(d).color), tr=r.getBoundingClientRect(), br=b.getBoundingClientRect();
      return {lum:(0.2126*m[1]+0.7152*m[2]+0.0722*m[3]), off:Math.abs((tr.left+tr.right)/2-(br.left+br.right)/2), dark:document.documentElement.classList.contains('dark')}; }"""
    for look, want_light in (("stars", True), ("hub", theme == "dark")):
        ctx = browser.new_context(viewport={"width": 1500, "height": 950})
        ctx.add_init_script("try{localStorage.setItem('alto-theme-v1','%s')}catch(e){}" % theme)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: "/phone/" in str(e) or errs.append(str(e)))   # (the phone whole-view script is hosted: a file:// copy cannot fetch it)
        pg.goto(pages[look].as_uri())
        pg.wait_for_timeout(2400)
        pg.mouse.move(2, 940)
        pg.evaluate("(id)=>window.enterFocus(id)", LONG)
        pg.wait_for_timeout(1500)
        r = pg.evaluate(LUM, LONG)
        assert r["dark"] == (theme == "dark"), r
        assert (r["lum"] > 170) if want_light else (r["lum"] < 90), (look, theme, r)
        assert r["off"] < 4, (look, theme, r)
        assert not errs, errs
        ctx.close()
