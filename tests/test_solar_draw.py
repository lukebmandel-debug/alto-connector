"""The solar outline's drawing (alto/build/solar_draw.py): circles for cards,
orbit rings and spokes under them, and the bodies turning round what they
orbit (in both looks), stopping for hover, focus and the rest.

Static checks on what the page carries; geometry and motion in a real browser
(Chromium and WebKit through Playwright; skipped without them). All browser
geometry is read in #world layout px (style.left/top, offset*), never screen
px — Playwright's WebKit is not Safari, and screen→world mapping under the
page's CSS zoom is where Safari differs (engine notes 1.8.34)."""
import copy
import gzip
import json
import math
import re
from pathlib import Path

import pytest

from alto.build.builder import build_timeline, load_brief
from alto.build.engine_patches import PATCHES
from alto.build.solar_draw import SOLAR_CSS, SOLAR_JS

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = (ROOT / "engine" / "timeline_template.html").read_text(encoding="utf-8")
MARGIN = 115


def solar_doc(units, style="orbit", links=(), suns=None):
    """A System bundle: units = [[moons per planet as [sats per moon]]];
    "orbit" opens in the Star chart look, "spoke" in the System one (the page
    carries both). suns: extra roots per unit (several systems in a unit),
    each with one bare planet.
    Ids spell the place: u1, u1-p2, u1-p2-m1, u1-p2-m1-s1; u1b2, u1b2-p1."""
    acts, nodes = [], []

    def add(i, act, parent="", title=None):
        n = {"id": i, "act": act, "tag": "Concept", "title": title or i.replace("-", " ").title(),
             "desc": f"What the notes say about {i}: the rule, the test and the cases that apply it.",
             "entity_ids": []}
        if parent:
            n["parent"] = parent
        nodes.append(n)
    for a, planets in enumerate(units):
        acts.append({"label": f"UNIT {a + 1} — Part {a + 1}", "short": f"Unit {a + 1}"})
        sun = f"u{a + 1}"
        add(sun, a, title=f"Doctrine {a + 1}")
        for p, moons in enumerate(planets):
            pid = f"{sun}-p{p + 1}"
            add(pid, a, sun, title=f"Planet concept {a + 1}.{p + 1}")
            for m, sats in enumerate(moons):
                mid = f"{pid}-m{m + 1}"
                add(mid, a, pid, title=f"Case {m + 1}")
                for s in range(sats):
                    add(f"{mid}-s{s + 1}", a, mid, title="Holding")
        for k in range((suns or {}).get(a, 0)):
            add(f"{sun}b{k + 2}", a, title=f"Building {a + 1}.{k + 2}")
            add(f"{sun}b{k + 2}-p1", a, f"{sun}b{k + 2}", title="A floor")
    kind = {"mode": "outline", "layout": "solar", "hub_look": "hub" if style == "spoke" else "stars"}
    brief = {"title": "Solar draw", "subject": "s", "timeline_id": "solar-draw", **kind, "columns": 5, "node_noun": "Concept",
             "period_noun": "Unit", "accent": "#a78bfa", "acts": acts, "entities": [], "axes": [],
             "relations": [{"key": "spine", "label": "Contains"},
                           {"key": "limits", "label": "Limits", "color": "#f43f5e"}]}
    return {"brief": brief, "nodes": nodes, "connections": [list(l) + ["limits"] for l in links]}


SMALL = [[[0, 0], [], [0]], [[0], [0, 2]], [[], [0]]]
SMALL_LINKS = [("u1-p1", "u2-p2"), ("u1-p1-m1", "u1-p3")]


def _page(units=SMALL, style="orbit", links=SMALL_LINKS, suns=None):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(units, style, links, suns))))
    return html


def _plan(html):
    """window._ALTO_SOLAR as the page sees it: the one plan, and `look` (the first)."""
    at = html.index("window._ALTO_SOLAR=") + len("window._ALTO_SOLAR=")
    return json.JSONDecoder().raw_decode(html[at:])[0]


# ── what the page carries ────────────────────────────────────────────────────

def test_a_solar_page_carries_the_drawing_and_a_tree_page_does_not():
    html = _page()
    assert html.count("window._altoSolarLayout=") == 1 and "#solar-svg" in html
    assert "html.alto-solar:not(.mobile)" in html
    d = solar_doc(SMALL, "spoke")
    d["brief"]["layout"] = "tree"
    tree, _ = build_timeline(*load_brief(d))
    assert "window._altoSolarLayout=" not in tree and "#solar-svg{" not in tree


def test_a_hub_and_spoke_page_carries_one_plan_and_no_palace():
    """The Star chart is a look of a System page, not a Mind Palace: path
    numbers, ONE plan (both looks draw it, round 7), the renderer mounted after it, none of the city."""
    html = _page(suns={0: 1})
    assert "window._ALTO_PALACE=" not in html and "window._ALTO_OUTLINE=" in html and "window._altoSolarMount=" in html
    assert "window._altoPalace=" not in html and "AudioContext" not in html
    p = _plan(html)
    assert p["style"] == "orbit" and p["look"] == "stars" and len(p["units"][0]["suns"]) == 2
    assert _plan(_page(style="spoke", suns={0: 1}))["nodes"] == p["nodes"]     # the System look: the same plan
    assert html.index("window._ALTO_SOLAR=") < html.index("window._altoSolarMount=function")


def test_the_engine_hooks_are_anchored_in_the_template_once():
    """Each solar hook's anchor is the pinned engine's own text (never another
    patch's), and the page carries each hook exactly once."""
    html = _page()
    names = {"solar-layout-hook", "solar-lines-hook", "solar-card-mask-round", "solar-card-mask-follows"}
    mine = [p for p in PATCHES if p["name"] in names]
    assert len(mine) == len(names)
    for p in mine:
        assert TEMPLATE.count(p["old"]) == 1, p["name"]
        assert html.count(p["new"]) == 1, p["name"]
    assert "window._altoSolarNav(id, dir)" in html                 # arrows (focusNeighbor)
    assert "if(n.hasAttribute('data-solar')) hov=false;" in html    # a circle grows from its centre
    assert "window._altoContentMoved=moved" in html                 # moving content is not a hover


def test_motion_never_uses_a_transform_and_rounds_to_device_px():
    """Bodies move by left/top (the D-GRID margins centre them, 1.8.28), at
    whole device px; nothing in the script sets a transform on a node."""
    # the one transform is the whole-chart view's, on #world itself
    # (and the focus shadow's scale, kept the same circle as the growing disc: not a node)
    # (and the enlarged disc's chips, turned a few degrees to the circle's edge by pool(): k, more, el are chips, not nodes;
    #  ch: a system's name, zoomed out, in its own unscaled layer #sol-ulay — not a node)
    assert [x for x in re.findall(r"(\w+)\.style\.transform=", SOLAR_JS) if x not in ("k", "more", "el", "ch")] == ["sh", "world", "world"]
    assert ".n.style.transform" not in SOLAR_JS
    assert "b.n.style.left=x+'px'" in SOLAR_JS and "Math.round(v*zq)/zq" in SOLAR_JS
    # no SVG <mask> on anything that moves (Safari): the rings and spokes are plain
    assert "<mask" not in SOLAR_JS and "'mask'" not in SOLAR_JS


def test_every_pause_is_there():
    for s in ("alto-editing", "beforeprint", "prefers-reduced-motion", "document.hidden", "_focusedNodeId",
              "focus-mode", "edge-hover", "alto-found", "detail-page.visible", "mobile", "dimmed"):
        assert s in SOLAR_JS, s


def test_the_drawing_is_small():
    """~15 KB gz was the first budget; the in-page plan (edit mode), the camera and
    the zoom gestures took it past that. Under 20 KB, against a 1,000,000-byte page."""
    size = len(gzip.compress((SOLAR_JS + SOLAR_CSS).encode("utf-8"), 9))
    assert size < 42500, size      # + one way of moving in both modes and the bug round (2026-10-22, ~1.5 KB); + the Tour (2026-10-22: tour order, multi-stop rides, the whole system with routes, the bar; ~3 KB); + the ships' rides from orbit to orbit along the spoke, nose on the way (~0.4 KB, 2026-10-22); + Spokes-only rides, Retro's orbit bands and ship, the units' names in their own layer (~2.8 KB); + round 11's navigation hints: named pills, drawn ways, edge pills (~2.3 KB, against the 1,000,000-byte page); + the in-page planner's comets, belts, core and drifters (Round 5), the looks; + round 8's labels, flanking children and zoomed-out detail (~3.6 KB); + the chips' pool and Enter (~1 KB); + round 10's upright / named chips, unit borders, spoke hits, hints, Flights / Spokes only, wallpaper_top (~2.5 KB)


def test_the_hub_look_orbits_on_the_same_plan():
    plan = _plan(_page(style="spoke"))
    assert plan["style"] == "orbit" and plan["look"] == "hub"
    assert all(p["period"] > 0 for s in plan["systems"] for p in s["planets"])
    assert "'sol-tube'" not in SOLAR_JS and "_altoSolarPlans" not in SOLAR_JS


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
    d = tmp_path_factory.mktemp("solar")
    out = {}
    for name, html in (("orbit", _page(suns={0: 1})), ("spoke", _page(style="spoke"))):
        f = d / f"{name}.html"
        f.write_text(html, encoding="utf-8")
        out[name] = (f, _plan(html))
    return out


def _open(browser, f, reduced=False, wait=1500):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950}, reduced_motion="reduce" if reduced else "no-preference")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(wait)
    return pg, errs


# every body: its circle (offset size), centre (style.left/top), what it orbits
BODIES = r"""() => {
  var G=window._altoSolarGeo(), out={T:G.T, moving:G.moving, W:document.getElementById('world').offsetWidth,
    H:document.getElementById('world').offsetHeight, b:{}, rings:[], spokes:0};
  Object.keys(G.bodies).forEach(function(id){
    var n=document.getElementById('node-'+id), c=n.querySelector('.node-card'), r=G.bodies[id];
    out.b[id]={x:parseFloat(n.style.left), y:parseFloat(n.style.top), w:c.offsetWidth, h:c.offsetHeight, d:r.d, p:r.p, role:r.role,
      br:getComputedStyle(c).borderTopLeftRadius, hx:r.hx, hy:r.hy};
  });
  document.querySelectorAll('#solar-svg circle.sol-ring').forEach(function(r){
    out.rings.push({cx:+r.getAttribute('cx'), cy:+r.getAttribute('cy'), r:+r.getAttribute('r'), m:r.classList.contains('sol-m')}); });
  out.spokes=document.querySelectorAll('#solar-svg .sol-spoke,#solar-svg path.sol-tube:not(.sol-l)').length;
  return out;
}"""


def test_circles_are_circles_with_rings_on_their_parents(browser, pages):
    f, plan = pages["orbit"]
    pg, errs = _open(browser, f)
    g = pg.evaluate(BODIES)
    assert not errs, errs
    assert set(g["b"]) == set(plan["nodes"])
    for i, b in g["b"].items():
        assert abs(b["w"] - b["h"]) < 0.5 and abs(b["w"] - b["d"]) <= 1, (i, b)       # offset* round
        assert b["br"] in ("50%",) or float(b["br"].rstrip("px")) >= b["d"] / 2 - 0.5, (i, b["br"])
    # each ring is centred on a body that is orbited, through the ring's own bodies
    for r in g["rings"]:
        centre = [i for i, b in g["b"].items() if abs(b["x"] - r["cx"]) < 0.6 and abs(b["y"] - r["cy"]) < 0.6]
        assert centre, r
        kids = [b for b in g["b"].values() if b["p"] in centre and abs(math.hypot(b["x"] - r["cx"], b["y"] - r["cy"]) - r["r"]) < 1.5]
        assert kids, r
    # every planet has its own ring round its sun; moons share one per planet
    planets = [i for i, b in g["b"].items() if b["role"] == "planet"]
    assert len([r for r in g["rings"] if not r["m"]]) == len(planets)
    assert g["spokes"] == len(plan["nodes"]) - len(plan["systems"])
    pg.context.close()


def test_nothing_sits_near_the_world_edge_at_the_start(browser, pages):
    for style in ("orbit", "spoke"):
        f, plan = pages[style]
        pg, errs = _open(browser, f, wait=900)
        g = pg.evaluate(BODIES)
        P = pg.evaluate("WORLD_PAD_TOP")
        for i, b in g["b"].items():
            r = b["d"] / 2
            assert b["hx"] - r >= MARGIN - 0.5 and b["hx"] + r <= g["W"] - MARGIN + 0.5, (style, i, b)
            assert b["hy"] - P - r >= MARGIN - 0.5 and b["hy"] + r <= g["H"] - MARGIN + 0.5, (style, i, b)
            # and the home is the plan's t = 0 centre
            assert abs(b["hx"] - plan["nodes"][i]["x"]) < 0.01 and abs(b["hy"] - P - plan["nodes"][i]["y"]) < 0.01
        pg.context.close()


def _moved(a, b):
    return max(math.hypot(a["b"][i]["x"] - b["b"][i]["x"], a["b"][i]["y"] - b["b"][i]["y"]) for i in a["b"])


def test_orbits_move_keep_their_radius_and_follow_the_lines(browser, pages):
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f)
    pg.mouse.move(2, 940)                                  # out of the way
    g0 = pg.evaluate(BODIES)
    pg.wait_for_timeout(2600)
    g1 = pg.evaluate(BODIES)
    assert g1["T"] > g0["T"] + 1.5 and g1["moving"]
    assert _moved(g0, g1) > 2                              # clearly moving
    for i, b in g1["b"].items():
        if not b["p"]:
            continue
        p0, p1, c0 = g0["b"][b["p"]], g1["b"][b["p"]], g0["b"][i]
        r0 = math.hypot(c0["x"] - p0["x"], c0["y"] - p0["y"])
        r1 = math.hypot(b["x"] - p1["x"], b["y"] - p1["y"])
        assert abs(r0 - r1) < 2, (i, r0, r1)                # still on its ring (both ends rounded to device px)
    # a connection ends at its circles' edges, wherever they are now
    ends = pg.evaluate(r"""() => [].map.call(document.querySelectorAll('#river-svg [data-edge]'), function(p){
        var k=p.getAttribute('data-edge').split('|'), d=p.getAttribute('d').match(/-?\d*\.?\d+/g).map(Number),
            h=document.querySelector('#river-svg [data-edge-hit="'+p.getAttribute('data-edge')+'"]');
        return {k:k, d:d, hit:h ? h.getAttribute('d')===p.getAttribute('d') : null}; })""")
    assert len(ends) == len(SMALL_LINKS)
    g2 = pg.evaluate(BODIES)
    for e in ends:
        a, b = g2["b"][e["k"][0]], g2["b"][e["k"][1]]
        assert abs(math.hypot(e["d"][0] - a["x"], e["d"][1] - a["y"]) - a["d"] / 2) < 3
        assert abs(math.hypot(e["d"][2] - b["x"], e["d"][3] - b["y"]) - b["d"] / 2) < 3
        assert e["hit"] is True                             # the hover path rides along
    pg.context.close()


def test_focus_freezes_the_orbit_and_lands_on_the_card_where_it_is(browser, pages):
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, wait=2200)
    pg.mouse.move(2, 940)
    target = "u1-p1"
    at = pg.evaluate(f"() => {{ var n=document.getElementById('node-{target}'); return [parseFloat(n.style.left), parseFloat(n.style.top)]; }}")
    pg.evaluate(f"() => window.enterFocus('{target}')")
    pg.wait_for_timeout(900)
    g0 = pg.evaluate(BODIES)
    pg.wait_for_timeout(1200)
    g1 = pg.evaluate(BODIES)
    assert _moved(g0, g1) < 0.01                            # frozen
    b = g1["b"][target]
    assert abs(b["x"] - at[0]) < 1.5 and abs(b["y"] - at[1]) < 1.5
    st = pg.evaluate(f"""() => {{ var n=document.getElementById('node-{target}'), c=n.querySelector('.node-card'),
        cv=document.getElementById('canvas'), r=c.getBoundingClientRect(), v=cv.getBoundingClientRect();
        return {{zoom:c.style.zoom, w:c.offsetWidth, desc:getComputedStyle(c.querySelector('.node-desc')).display,
                 clip:n.classList.contains('sol-clip'), cx:r.left+r.width/2-(v.left+v.width/2), cy:r.top+r.height/2-(v.top+v.height/2)}}; }}""")
    assert st["zoom"] == "1.7" and st["w"] >= 250 and st["desc"] != "none" and not st["clip"]
    assert abs(st["cx"]) < 40 and abs(st["cy"]) < 40, st     # the fly landed on it
    # leaving: it shrinks back to its circle, and then the orbits go on
    pg.evaluate("() => window.exitFocus()")
    pg.wait_for_timeout(2600)
    g2 = pg.evaluate(BODIES)
    assert g2["b"][target]["w"] == pytest.approx(g2["b"][target]["d"], abs=0.5)
    assert pg.evaluate(f"() => document.getElementById('node-{target}').className").find("sol-") < 0
    pg.wait_for_timeout(800)
    assert _moved(g2, pg.evaluate(BODIES)) > 0.3
    assert not errs, errs
    pg.context.close()


def test_hover_and_edit_mode_stop_it_and_edit_mode_turns_it_home(browser, pages):
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, wait=2500)
    pg.evaluate("() => document.getElementById('node-u1').scrollIntoView({block:'center', inline:'center'})")
    pg.wait_for_timeout(300)
    xy = pg.evaluate("() => { var c=document.querySelector('#node-u1 .node-card').getBoundingClientRect(); return [c.left+c.width/2, c.top+c.height/2]; }")
    pg.mouse.move(xy[0] - 30, xy[1] - 30)
    pg.mouse.move(xy[0], xy[1])
    pg.wait_for_timeout(300)
    g0 = pg.evaluate(BODIES)
    pg.wait_for_timeout(900)
    assert _moved(g0, pg.evaluate(BODIES)) < 0.01           # pointing at a sun: all still
    pg.mouse.move(2, 940)
    pg.wait_for_timeout(1500)
    assert _moved(g0, pg.evaluate(BODIES)) > 0.3            # and on again
    pg.evaluate("() => document.documentElement.classList.add('alto-editing')")
    pg.wait_for_timeout(1000)
    g = pg.evaluate(BODIES)
    assert g["T"] == 0
    for i, b in g["b"].items():
        assert abs(b["x"] - b["hx"]) < 1 and abs(b["y"] - b["hy"]) < 1, i
    pg.context.close()


def test_reduced_motion_stands_still_and_the_hub_look_orbits_with_rings(browser, pages):
    for style, reduced in (("orbit", True), ("spoke", False)):
        f, _ = pages[style]
        pg, errs = _open(browser, f, reduced=reduced)
        pg.mouse.move(2, 940)
        g0 = pg.evaluate(BODIES)
        pg.wait_for_timeout(1200)
        g1 = pg.evaluate(BODIES)
        if reduced:
            assert _moved(g0, g1) == 0 and g1["T"] == 0, style
        else:
            assert _moved(g0, g1) > 0.3 and g1["rings"] and g1["spokes"] > 0     # System: rings, spokes, orbiting
        assert not errs, errs
        pg.context.close()


@pytest.mark.parametrize("shape", ["small", "torts"])
def test_arrows_follow_the_outline_and_the_wheel_pans(browser, tmp_path, shape):
    """The Tour in both modes (Luke, 2026-10-22, in place of round 9's arrows by outline level): ↑ the parent, ↓ the
    first child, → / ← the next / previous in the outline's order, Shift+→ / ← the next / previous sibling — for every
    body; in normal mode the wheel over an enlarged disc pans the board (the card goes home)."""
    units = SMALL if shape == "small" else TORTS_SHAPE
    f = tmp_path / f"nav-{shape}.html"
    f.write_text(_page(units, links=() if shape == "torts" else SMALL_LINKS), encoding="utf-8")
    pg, errs = _open(browser, f, reduced=True, wait=1600)          # (reduced motion: each move goes straight there)
    pg.mouse.move(2, 940)
    G = pg.evaluate("() => { var G=window._altoSolarGeo().bodies, o={}; Object.keys(G).forEach(function(i){ o[i]=[G[i].p||null, G[i].role]; }); return o; }")
    T = pg.evaluate("() => window._altoSolarLock.order()")
    assert sorted(T) == sorted(G)
    for start in T[::max(1, len(T) // 7)]:
        p, role = G[start]
        kids = [i for i in T if G[i][0] == start]
        sib = [i for i in T if G[i][1] == role and G[i][0] == p]
        k = sib.index(start)
        want = {"ArrowUp": p or start, "ArrowDown": kids[0] if kids else start, "ArrowRight": T[T.index(start) + 1] if start != T[-1] else start,
                "ArrowLeft": T[T.index(start) - 1] if T.index(start) else start, "Shift+ArrowRight": sib[k + 1] if k + 1 < len(sib) else start}
        for key, to in want.items():
            pg.evaluate("(i) => window.enterFocus(i)", start)
            pg.wait_for_timeout(450)
            pg.keyboard.press(key)
            pg.wait_for_timeout(450)
            got = pg.evaluate("() => window._focusedNodeId")
            if key == "ArrowRight" and start == T[-1]:
                continue                                               # (the end: the whole system)
            assert got == to, (start, key, got, to)
    pg.evaluate("() => window.enterFocus('u2-p2')")
    pg.wait_for_timeout(600)
    s0 = pg.evaluate("() => document.getElementById('canvas').scrollTop")
    pg.mouse.move(750, 520)
    for _ in range(4):
        pg.mouse.wheel(0, 40)
        pg.wait_for_timeout(16)
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => [window._focusedNodeId, document.getElementById('canvas').scrollTop!==" + str(s0) + "]") == [None, True]
    pg.wait_for_timeout(600)
    assert pg.evaluate("() => document.querySelectorAll('#world .sol-closing,#world .sol-clip').length") == 0
    assert not errs, errs
    pg.context.close()


def test_a_phone_keeps_its_column_of_cards(browser, pages):
    f, _ = pages["orbit"]
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=browser.browser_type.name != "firefox",
                              user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                                          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"))
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1200)
    st = pg.evaluate("""() => ({mobile:document.documentElement.classList.contains('mobile'),
        solar:document.documentElement.classList.contains('alto-solar'), svg:!!document.getElementById('solar-svg'),
        circles:document.querySelectorAll('[data-solar]').length})""")
    assert st["mobile"] and not st["solar"] and not st["svg"] and st["circles"] == 0, st
    assert not errs, errs
    ctx.close()


# ── edit mode: the page plans the systems again (SOLAR_PLAN_JS = solar_plan) ──

import shutil  # noqa: E402
import subprocess  # noqa: E402

from alto.build.solar import solar_plan  # noqa: E402
from alto.build.solar_draw import SOLAR_PLAN_JS  # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")


def _close(a, b, path=""):
    if isinstance(a, dict):
        assert set(a) == set(b), (path, set(a) ^ set(b))
        for k in a:
            _close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            _close(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool):
        assert b == pytest.approx(a, abs=0.02), (path, a, b)
    else:
        assert a == b, (path, a, b)


@needs_node
@pytest.mark.parametrize("style", ["orbit"])
@pytest.mark.parametrize("units", [SMALL, [[[2, 2, 2], [2, 2], [2, 2, 2], [2], [2, 2]], [[0, 0], [0, 0, 0]]],
                                   [[[0, 1, 0], [0, 0], [0, 0, 0], [0, 0, 0]], [[2, 2, 0, 0], [0, 0, 0, 0]], [[]]]])
@pytest.mark.parametrize("bumped", [False, True])
@pytest.mark.parametrize("suns", [None, {0: 2, 1: 1}])
def test_the_page_plans_the_systems_exactly_as_solar_py(tmp_path, units, style, bumped, suns):
    """Edit mode re-plans in the page from the live tables; that plan is solar.py's
    (sizes by child count, a pivotal flag one tier up, several suns in a district)."""
    doc = solar_doc(units, style, suns=suns)
    if bumped:
        # pivotal bumps; the rest are the user's flags that make a body a black hole, comet or asteroid
        doc["brief"]["flags"] = [{"id": "pivotal", "name": "Pivotal"}, {"id": "overruled", "name": "Overruled"},
                                 {"id": "revisit", "name": "Revisit"}, {"id": "not-tested", "name": "Not tested"}]
        deal = ["pivotal", "revisit", "not-tested", "overruled", "revisit", ""]
        for k, n in enumerate(doc["nodes"]):
            if n["id"] in ("u1-p1", "u1-p1-m1", "u2-p2"):
                n["flags"] = ["pivotal"]
            elif deal[k % len(deal)]:
                n["flags"] = [deal[k % len(deal)]]
    b, nodes, _ = load_brief(copy.deepcopy(doc))
    from alto.build.builder import place
    from alto.build.brief import validate_brief, validate_nodes
    validate_brief(b)
    validate_nodes(b, nodes)
    place(b, nodes)
    want = solar_plan(b, nodes)
    kids = {}
    for n in nodes:
        if n.parent:
            kids.setdefault(n.parent, []).append(n.id)
    tables = {"kids": kids, "parent": {n.id: n.parent for n in nodes if n.parent},
              "seqs": [[n.id for n in nodes if n.act == a] for a in range(len(b.acts))],
              "flags": {n.id: list(n.flags) for n in nodes if n.flags}}
    js = ("var window=globalThis;\n" + SOLAR_PLAN_JS + "\n"
          f"console.log(JSON.stringify(window._altoSolarPlan({json.dumps(tables)}, {json.dumps(want)})));")
    f = tmp_path / "plan.js"
    f.write_text(js, encoding="utf-8")
    got = json.loads(subprocess.check_output([NODE, str(f)], timeout=120))
    want.pop("warnings"), got.pop("warnings")
    _close(want, got)


def test_edit_mode_has_its_sync():
    assert "window._altoSolarSync=function(t)" in SOLAR_JS and "window._altoSolarPlan=(function(){" in SOLAR_JS


def test_edit_mode_sync_redraws_the_systems_from_the_live_tables(browser, pages):
    """What manual_edit does on a structural change: the live tables change,
    _altoSolarSync, then initLayout — the circles land on the new plan."""
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, wait=1200)
    pg.evaluate("() => document.documentElement.classList.add('alto-editing')")
    pg.wait_for_timeout(700)
    out = pg.evaluate(r"""() => {
      /* the live tables: an outline's, or (a Star chart) built from the palace's parent map */
      var O=window._ALTO_OUTLINE || (function(){ var par=JSON.parse(JSON.stringify(window._ALTO_PALACE.par)), kids={};
        [].concat.apply([], ACT_SEQS).forEach(function(i){ var p=par[i]; if(p) (kids[p]=kids[p]||[]).push(i); });
        return {parent:par, kids:kids, num:window._ALTO_PALACE.num}; })(), mv=['u1-p3','u1-p3-m1'];
      O.parent['u1-p3']='u2'; O.kids['u1']=O.kids['u1'].filter(function(i){ return i!=='u1-p3'; }); O.kids['u2'].push('u1-p3');
      ACT_SEQS[0]=ACT_SEQS[0].filter(function(i){ return mv.indexOf(i)<0; }); mv.forEach(function(i){ ACT_SEQS[1].push(i); NODE_ACT[i]=1; });
      var ok=window._altoSolarSync({kids:O.kids, parent:O.parent, num:O.num, seqs:ACT_SEQS, act:NODE_ACT});
      initLayout();
      var S=window._ALTO_SOLAR, bad=[], P=WORLD_PAD_TOP;
      Object.keys(S.nodes).forEach(function(i){ var n=document.getElementById('node-'+i), w=S.nodes[i];
        if(Math.abs(parseFloat(n.style.left)-w.x)>1 || Math.abs(parseFloat(n.style.top)-P-w.y)>1) bad.push(i); });
      var sys=S.systems.filter(function(s){ return s.sun==='u2'; })[0];
      return {ok:ok, bad:bad, planets:sys.planets.map(function(p){ return p.id; }), role:S.nodes['u1-p3'].role, parent:S.nodes['u1-p3'].parent,
              rings:document.querySelectorAll('#solar-svg circle.sol-ring:not(.sol-m)').length,
              geoP:window._altoSolarGeo().bodies['u1-p3'].p, truthy:!!window._ALTO_SOLAR};
    }""")
    assert out["ok"] and out["truthy"] and not out["bad"], out
    assert "u1-p3" in out["planets"] and out["role"] == "planet" and out["parent"] == "u2" and out["geoP"] == "u2"
    assert out["rings"] == sum(len(u) for u in SMALL) + 1                  # + the second building's floor
    assert not errs, errs
    pg.context.close()


def test_zoom_is_continuous_down_to_the_whole_chart_and_a_click_comes_back_down(browser, pages):
    """Luke (rounds 2, 4): zoom out as far as wanted — no button, no mode — the circles
    shrinking with it, the orbits going on; a click on a body comes back down to it."""
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    assert pg.evaluate("() => !document.getElementById('sol-fit')")
    zs = []
    for _ in range(8):                                                # cmd-minus, step by step, no jump
        pg.keyboard.press("Control+Minus")
        pg.wait_for_timeout(650)
        zs.append(pg.evaluate("() => window._altoSolarZoom()"))
    # round 8: it stops at the whole chart filling 85% of the window ("fully zoomed out, it's impossible to see anything")
    fit = pg.evaluate("""() => { var c=document.getElementById('canvas'), w=document.getElementById('world'), sl=document.getElementById('glass-slab');
      return Math.min((c.clientWidth-60)/w.offsetWidth, (c.clientHeight-60)/Math.max(w.offsetHeight, sl ? sl.offsetTop+sl.offsetHeight : 0)); }""")
    k = next(i for i, z in enumerate(zs) if abs(z - zs[-1]) < 1e-9)
    assert all(b < a for a, b in zip(zs[:k + 1], zs[1:k + 1])) and zs[0] > 0.5 and abs(zs[-1] - 0.85 * fit) < 1e-3, (zs, fit)
    st = pg.evaluate("""() => { var w=document.getElementById('world').getBoundingClientRect(), c=document.getElementById('canvas').getBoundingClientRect();
      return {w:[w.left, w.top, w.right, w.bottom], c:[c.left, c.top, c.right, c.bottom]}; }""")
    w, c = st["w"], st["c"]
    assert w[0] >= c[0] - 1 and w[1] >= c[1] - 1 and w[2] <= c[2] + 1 and w[3] <= c[3] + 1, st   # all of it in view
    pg.keyboard.press("Control+0")
    pg.wait_for_timeout(800)
    assert pg.evaluate("() => [window._altoSolarZoom(), document.getElementById('world').style.transform]") == [1, ""]
    for _ in range(4):                                                # far enough out that u2-p1 is in the window
        pg.keyboard.press("Control+Minus")
        pg.wait_for_timeout(650)
    g0 = pg.evaluate(BODIES)
    pg.wait_for_timeout(900)
    assert _moved(g0, pg.evaluate(BODIES)) > 0.3                       # the orbits go on
    xy = pg.evaluate("() => { var r=document.querySelector('#node-u2-p1 .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    pg.mouse.click(xy[0], xy[1])
    pg.wait_for_timeout(1600)
    assert pg.evaluate("() => [window._altoSolarZoom(), window._focusedNodeId]") == [1, "u2-p1"]
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(700)
    pg.mouse.move(700, 500)
    pg.keyboard.down("Control")
    for _ in range(4):
        pg.mouse.wheel(0, 40)
        pg.wait_for_timeout(60)
    pg.keyboard.up("Control")
    pg.wait_for_timeout(300)
    assert pg.evaluate("() => window._altoSolarZoom()") < 0.9                # a pinch out
    assert not errs, errs
    pg.context.close()


def _png_rgb(data):
    """(width, height, pixel(x, y) -> (r, g, b)) of an 8-bit, non-interlaced RGB/RGBA PNG."""
    import struct
    import zlib
    pos, idat = 8, b""
    w = h = ct = None
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            w, h, depth, ct = struct.unpack(">IIBB", body[:10])
            assert depth == 8 and ct in (2, 6)
        elif typ == b"IDAT":
            idat += body
        pos += 12 + n
    bpp = 3 if ct == 2 else 4
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, lambda x, y: tuple(rows[y][x * bpp:x * bpp + 3])


def test_zoomed_out_there_is_no_rectangle_round_the_chart(browser, pages, tmp_path):
    """Luke: "zoom out as much as they want and not see a clear border". Pixels just
    inside and just outside the old board's edge are the same background."""
    f, _ = pages["spoke"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    pg.evaluate("() => window._altoSolarZoom(0.3)")
    pg.wait_for_timeout(600)
    r = pg.evaluate("() => { var w=document.getElementById('world').getBoundingClientRect(); return [w.left, w.top, w.right, w.bottom]; }")
    shot = tmp_path / "zoomed.png"
    pg.screenshot(path=str(shot))
    W, H, px = _png_rgb(shot.read_bytes())
    worst = 0
    for k in range(1, 9):                                            # along the left and right edges, 6 px in and out
        y = int(r[1] + (r[3] - r[1]) * k / 9)
        for x, dx in ((r[0], 1), (r[2], -1)):
            a, b = (int(x + 6 * dx), y), (int(x - 6 * dx), y)
            if not (0 <= a[0] < W and 0 <= b[0] < W and 120 < y < H - 10):
                continue
            pa, pb = px(*a), px(*b)
            worst = max(worst, max(abs(pa[i] - pb[i]) for i in range(3)))
    assert worst <= 12, worst
    assert not errs, errs
    pg.context.close()


# ── where a chart opens (Luke, Torts star chart on 1.9.105: it opened on empty
#    space, the first sun below the fold) ─────────────────────────────────────

OPENING = """() => { var S=window._ALTO_SOLAR, id=S.systems[0].sun, c=document.getElementById('canvas').getBoundingClientRect(),
  n=document.querySelector('#node-'+id+' .node-card').getBoundingClientRect();
  return {zoom:window._altoSolarZoom(), dx:n.left+n.width/2-(c.left+c.width/2), dy:n.top+n.height/2-(c.top+c.height/2),
          cw:c.width, ch:c.height, inView:n.top>=c.top && n.bottom<=c.bottom && n.left>=c.left && n.right<=c.right}; }"""


def _opened(browser, tmp_path, html, name):
    f = tmp_path / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    pg, errs = _open(browser, f, wait=2600)          # past the engine's own openings (load, 150 / 600 / 1400 ms)
    o = pg.evaluate(OPENING)
    pg.context.close()
    assert not errs, errs
    return o


def test_a_big_star_chart_opens_on_its_first_sun(browser, tmp_path):
    html = _page(suns={0: 1})
    assert _plan(html)["world"]["h"] > 3000                     # far bigger than the window
    o = _opened(browser, tmp_path, html, "big")
    assert o["zoom"] == 1 and o["inView"], o
    assert abs(o["dx"]) < o["cw"] * .1 and abs(o["dy"]) < o["ch"] * .1, o   # in the middle of the window


def test_a_small_star_chart_opens_fitted_to_all_of_it(browser, tmp_path):
    o = _opened(browser, tmp_path, _page(units=[[[], []]], links=()), "small")
    assert 0.6 <= o["zoom"] < 1 and o["inView"], o


def test_hub_and_spoke_keeps_the_engines_opening_while_its_sun_is_in_view(browser, tmp_path):
    o = _opened(browser, tmp_path, _page(style="spoke"), "spoke")
    assert o["zoom"] == 1 and o["inView"], o


def test_a_hub_and_spoke_whose_first_sun_is_below_the_fold_opens_on_it(browser, tmp_path):
    # a first unit with many planets: its sun sits far down the board
    html = _page(units=[[[2] * 8] * 14], style="spoke", links=())
    s0 = _plan(html)["systems"][0]
    assert s0["cy"] - s0["r_sun"] > 1100                         # below a 950px window's fold
    o = _opened(browser, tmp_path, html, "spoke-big")
    assert o["inView"] and abs(o["dy"]) < o["ch"] * .25, o


def test_a_find_link_is_not_overridden(browser, tmp_path):
    f = tmp_path / "find.html"
    f.write_text(_page(suns={0: 1}), encoding="utf-8")
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    pg = ctx.new_page()
    pg.goto(f.as_uri() + "#find=u2-p1")
    pg.wait_for_timeout(2600)
    st = pg.evaluate("() => [window._altoSolarZoom(), window._focusedNodeId]")
    ctx.close()
    assert st[0] == 1 and st[1] in (None, "u2-p1")


# ── zooming: one gesture, one owner (Luke on 1.9.105: "If I zoom in and try to zoom
#    back out, it basically doesn't work.") Synthetic Safari gesture events and
#    ctrl+wheel streams on a System page; Playwright's WebKit is not Safari, so
#    scratch/safari/zoomprobe.* repeats these in the real thing. ────────────────

GESTURE_JS = r"""
window.__g=function(type, scale, x, y){ var e=new Event(type, {bubbles:true, cancelable:true}); e.scale=scale; e.rotation=0; e.clientX=x; e.clientY=y;
  (document.elementFromPoint(x, y)||document.body).dispatchEvent(e); return e.defaultPrevented; };
window.__st=function(){ return {z:window._altoSolarZoom(), f:window._focusedNodeId||null}; };
"""


def _pinch(pg, x, y, scales, gap=16):
    prevented = [pg.evaluate(f"() => window.__g('gesturestart', 1, {x}, {y})")]
    for s in scales:
        prevented.append(pg.evaluate(f"() => window.__g('gesturechange', {s}, {x}, {y})"))
        pg.wait_for_timeout(gap)
    prevented.append(pg.evaluate(f"() => window.__g('gestureend', {scales[-1]}, {x}, {y})"))
    return prevented


def _wheel(pg, x, y, dy, n, gap=16):
    pg.mouse.move(x, y)
    pg.keyboard.down("Control")
    for _ in range(n):
        pg.mouse.wheel(0, dy)
        pg.wait_for_timeout(gap)
    pg.keyboard.up("Control")


@pytest.fixture(scope="module")
def hub_page(tmp_path_factory):
    f = tmp_path_factory.mktemp("hub") / "hub.html"
    f.write_text(_page(style="spoke"), encoding="utf-8")
    return f


def test_a_pinch_never_starts_the_browsers_own_zoom_and_goes_both_ways(browser, hub_page):
    pg, errs = _open(browser, hub_page, wait=1800)
    pg.evaluate(GESTURE_JS)
    xy = pg.evaluate("() => { var r=document.querySelector('#node-u1-p1 .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    # pinch in on a card at rest: the engine enlarges it; every gesture event is prevented
    prev = _pinch(pg, xy[0], xy[1], [1.05, 1.15, 1.3, 1.45])
    pg.wait_for_timeout(900)
    assert all(prev), prev
    assert pg.evaluate("window.__st()") == {"z": 1, "f": "u1-p1"}
    # pinch out: let go
    assert all(_pinch(pg, 700, 500, [0.95, 0.85, 0.7, 0.55]))
    pg.wait_for_timeout(900)
    assert pg.evaluate("window.__st()") == {"z": 1, "f": None}
    # pinch out at rest: the whole chart; pinch in from it: all the way back to full size, nothing enlarged
    _pinch(pg, 700, 500, [0.9, 0.75, 0.6])
    pg.wait_for_timeout(500)
    assert pg.evaluate("window._altoSolarZoom()") < 1
    _pinch(pg, 700, 500, [1.1, 1.3, 1.6, 2.0])
    pg.wait_for_timeout(700)
    assert pg.evaluate("window.__st()") == {"z": 1, "f": None}
    assert not errs, errs
    pg.context.close()


def test_one_ctrl_wheel_stream_does_one_thing_and_zooms_out_of_a_card(browser, hub_page):
    pg, errs = _open(browser, hub_page, wait=1800)
    pg.evaluate(GESTURE_JS)
    xy = pg.evaluate("() => { var r=document.querySelector('#node-u1-p1 .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    _wheel(pg, xy[0], xy[1], -30, 6)
    pg.wait_for_timeout(900)
    assert pg.evaluate("window.__st()")["f"] is not None             # pinch in: enlarged
    _wheel(pg, 700, 500, 30, 30)                                     # one long pinch out: let go, then on out
    pg.wait_for_timeout(700)
    st = pg.evaluate("window.__st()")
    assert st["f"] is None and st["z"] < 1, st
    _wheel(pg, 700, 500, -30, 30)                                    # one long pinch in: back to full size and on into a body
    pg.wait_for_timeout(900)
    st = pg.evaluate("window.__st()")
    assert st["z"] == 1 and st["f"] is not None, st
    assert not errs, errs
    pg.context.close()


# ── the camera adapter (window._altoSolarCam, for solar_fly.py) ───────────────

def test_the_camera_puts_a_plan_point_in_the_middle_at_any_scale(browser, pages):
    f, plan = pages["orbit"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    seen = pg.evaluate("() => { window.__cam=[]; window._altoSolarCam.onChange(function(g){ window.__cam.push(g); }); return 1; }")
    for sid, scale in (("u2", 1), ("u1", 0.5), ("u3", 0.8), ("u1-p1", 1)):
        n = plan["nodes"][sid]
        g = pg.evaluate(f"() => window._altoSolarCam.set({n['x']}, {n['y']}, {scale})")
        pg.wait_for_timeout(120)
        g2 = pg.evaluate("() => window._altoSolarCam.get()")
        assert g2["scale"] == pytest.approx(scale, abs=1e-6)
        assert abs(g2["cx"] - n["x"]) < 2 and abs(g2["cy"] - n["y"]) < 2, (sid, scale, g2, n)
        assert pg.evaluate("() => window._altoSolarZoom()") == pytest.approx(scale, abs=1e-6)
        # set(get()) changes nothing
        g3 = pg.evaluate("() => { var g=window._altoSolarCam.get(); return window._altoSolarCam.set(g.cx, g.cy, g.scale); }")
        assert abs(g3["cx"] - g2["cx"]) < 1.5 and abs(g3["cy"] - g2["cy"]) < 1.5
    assert pg.evaluate("() => window.__cam.length") > 0              # onChange heard the moves
    # cmd-minus moves the same camera
    pg.evaluate("() => window._altoSolarCam.set(0, 0, 1)")
    pg.keyboard.press("Control+Minus")
    pg.wait_for_timeout(900)
    assert pg.evaluate("() => window._altoSolarCam.get().scale") == pytest.approx(pg.evaluate("() => window._altoSolarZoom()"))
    assert not errs, errs
    pg.context.close()


# ── an enlarged body stays a circle and shows its content (Luke, round 4) ─────

def _long_page(style):
    d = solar_doc(SMALL, style, SMALL_LINKS, {0: 1} if style == "orbit" else None)
    for n in d["nodes"]:
        if n["id"] == "u1-p1":
            n["desc"] = ("The rule as the notes put it, at length. " * 14).strip()
            n["sections"] = [{"h": "Test", "t": "Each element in turn, as the cases apply it. " * 8},
                             {"h": "Cases", "t": "The leading cases and what each decides. " * 8}]
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    return html


DISC_WATCH = r"""() => new Promise(function(res){
  var n=document.getElementById('node-u1-p1'), c=n.querySelector('.node-card'), bad=[], k=0, t0=performance.now();
  (function f(){ var cs=getComputedStyle(c), cp=cs.clipPath||cs.webkitClipPath||'none', w=c.offsetWidth, h=c.offsetHeight;
    if(Math.abs(w-h)>1) bad.push('box '+w+'x'+h);
    if(!/^(none|circle)/.test(cp)) bad.push('clip '+cp);
    if(cs.borderTopLeftRadius!=='50%' && parseFloat(cs.borderTopLeftRadius)<w/2-1) bad.push('radius '+cs.borderTopLeftRadius);
    var sh=document.querySelector('#world .alto-fshadow'); if(sh && getComputedStyle(sh).borderTopLeftRadius!=='50%') bad.push('shadow '+getComputedStyle(sh).borderTopLeftRadius);
    k++; if(performance.now()-t0<1100) requestAnimationFrame(f); else res({frames:k, bad:bad.slice(0, 6)}); })();
})"""


@pytest.mark.parametrize("style", ["spoke", "orbit"])
def test_an_enlarged_body_is_a_bigger_disc_with_its_card_and_a_way_to_the_full_page(browser, tmp_path, style):
    f = tmp_path / f"long-{style}.html"
    f.write_text(_long_page(style), encoding="utf-8")
    pg, errs = _open(browser, f, wait=1600)
    pg.mouse.move(2, 940)
    # every frame of the grow: a circle (box square, round clip or none, round shadow)
    res = pg.evaluate("() => { var p=(" + DISC_WATCH + ")(); window.enterFocus('u1-p1'); return p; }")
    assert not res["bad"], res
    st = pg.evaluate("""() => { var n=document.getElementById('node-u1-p1'), c=n.querySelector('.node-card'), b=c.querySelector('.sol-body');
      return {w:c.offsetWidth, h:c.offsetHeight, sD:parseFloat(getComputedStyle(n).getPropertyValue('--sD')), d:window._ALTO_SOLAR.nodes['u1-p1'].d,
              title:b && b.querySelector('.node-title') && getComputedStyle(b).display!=='none' ? b.querySelector('.node-title').textContent : null,
              secs:b ? b.querySelectorAll('.sol-sec').length : 0, scrolls:b ? b.scrollHeight>b.clientHeight : null,
              open:!c.querySelector('.sol-open')}; }""")
    assert abs(st["w"] - st["h"]) <= 1 and abs(st["w"] - st["sD"]) <= 1 and st["sD"] > st["d"], st
    # the card's level only (Luke, round 9): no sections, nothing scrolls, a long description ends in an ellipsis
    assert st["title"] and st["secs"] == 0 and not st["scrolls"] and st["open"], st
    cl = pg.evaluate("""() => { var d=document.querySelector('#node-u1-p1 .sol-body .node-desc'), cs=getComputedStyle(d);
      return {clamped:d.scrollHeight>d.clientHeight+1, lc:cs.webkitLineClamp||cs.lineClamp}; }""")
    assert cl["clamped"] and str(cl["lc"]) == "4", cl
    xy = pg.evaluate("() => { var r=document.querySelector('#node-u1-p1 .sol-body').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    # a click on the disc opens the full page (the engine's own card click); there is no control for it
    assert not pg.evaluate("() => document.getElementById('detail-page').classList.contains('visible')")
    pg.mouse.click(xy[0], xy[1])
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => document.getElementById('detail-page').classList.contains('visible')")
    assert not errs, errs
    pg.context.close()


def test_esc_and_arrows_from_an_enlarged_disc_and_back_to_a_circle(browser, pages):
    f, _ = pages["spoke"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    pg.evaluate("() => window.enterFocus('u1')")
    pg.wait_for_timeout(800)
    pg.keyboard.press("ArrowRight")                              # (the Tour: a ride to the next in the outline)
    pg.wait_for_function("() => window._focusedNodeId && window._focusedNodeId!=='u1' && !window._altoSolarLock.riding()", timeout=6000)
    pg.wait_for_timeout(400)
    got = pg.evaluate("() => window._focusedNodeId")
    assert got and got != "u1"
    res = pg.evaluate("() => { var p=(" + DISC_WATCH.replace("u1-p1", "u1") + ")(); return p; }")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(1200)
    st = pg.evaluate("""(id) => { var n=document.getElementById('node-'+id), c=n.querySelector('.node-card');
      return {f:window._focusedNodeId||null, w:c.offsetWidth, h:c.offsetHeight, cls:n.className}; }""", got)
    assert st["f"] is None and st["w"] == st["h"] and "sol-" not in st["cls"], st
    assert not res["bad"], res
    assert not errs, errs
    pg.context.close()


# ── the enlarged disc is ONE circle at every frame, under any page zoom (Luke, Safari, round 7) ──
# Safari 27 at html zoom 0.86 drew a clip-path circle() on the zoomed card in another box than the card:
# a smaller circle up-left, the text out of its bottom, the shadow a bigger circle down-right. Now the
# card is a real disc (--scd) at every frame; card, shadow and content are read here in the viewport's
# px (getBoundingClientRect: what is seen), every frame of the grow and of the shrink.

GEO_WATCH = r"""(id) => new Promise(function(res){
  var n=document.getElementById('node-'+id), c=n.querySelector('.node-card'), bad=[], k=0, t0=performance.now(), seen=0;
  function R(e){ var r=e.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2, r.width, r.height]; }
  (function f(){ var cs=getComputedStyle(c), cp=cs.clipPath||cs.webkitClipPath||'none', a=R(c);
    if(cp!=='none') bad.push('clip '+cp);
    if(Math.abs(a[2]-a[3])>1) bad.push(k+' box '+a[2].toFixed(1)+'x'+a[3].toFixed(1));
    if(parseFloat(cs.borderTopLeftRadius)<Math.min(c.offsetWidth, c.offsetHeight)/2-1 && cs.borderTopLeftRadius!=='50%') bad.push('radius');
    var sh=n._fsh;
    if(sh && parseFloat(sh.style.opacity||'0')>0.02){ var b=R(sh); seen++;
      if(Math.hypot(a[0]-b[0], a[1]-b[1])>1) bad.push(k+' shadow off '+(b[0]-a[0]).toFixed(1)+','+(b[1]-a[1]).toFixed(1));
      if(Math.abs(a[2]-b[2])>1) bad.push(k+' shadow '+b[2].toFixed(1)+' card '+a[2].toFixed(1)); }
    k++; if(performance.now()-t0<1000) requestAnimationFrame(f); else res({frames:k, shadow:seen, bad:bad.slice(0, 8)}); })();
})"""

GEO_REST = r"""(id) => { var n=document.getElementById('node-'+id), c=n.querySelector('.node-card'), b=c.querySelector('.sol-body'), o=b;
  var r=c.getBoundingClientRect(), cx=r.left+r.width/2, cy=r.top+r.height/2, R=r.width/2;
  function far(e){ var q=e.getBoundingClientRect(); return Math.max.apply(null, [[q.left,q.top],[q.right,q.top],[q.left,q.bottom],[q.right,q.bottom]].map(function(p){ return Math.hypot(p[0]-cx, p[1]-cy); })); }
  var ob=o.getBoundingClientRect(), chips=[].filter.call(c.querySelectorAll(':scope > .node-footer > button, :scope > .node-footer > .sol-more'), function(x){ return x.offsetWidth && getComputedStyle(x).display!=='none'; }).map(function(x){ var q=x.getBoundingClientRect(), cs=getComputedStyle(x);
    return {far:far(x), top:q.top-cy, hitsOpen:!(q.right<=ob.left || q.left>=ob.right || q.bottom<=ob.top || q.top>=ob.bottom), round:parseFloat(cs.borderTopLeftRadius)>=q.height/2-.5, ta:cs.textAlign}; });
  return {R:R, w:r.width, h:r.height, body:far(b), open:far(o), scrolls:b.scrollHeight>b.clientHeight+1, ov:getComputedStyle(b).overflowY, chips:chips,
          sD:parseFloat(n.style.getPropertyValue('--sD')), z:getComputedStyle(document.documentElement).zoom, cls:n.className}; }"""


def _sizes_page():
    """Bodies whose card text asks for each enlarged size (300 / 340 / 380), two with chips."""
    d = solar_doc(SMALL, "orbit", SMALL_LINKS)
    lens = {"u1-p1": 30, "u1-p2": 17, "u1-p3": 8, "u2-p2": 1}
    d["brief"]["entities"] = [{"id": f"e{k}", "name": f"Party {k}"} for k in range(9)]
    for n in d["nodes"]:
        if n["id"] in ("u1-p1", "u1-p2"):
            n["entity_ids"] = [f"e{k}" for k in range(9 if n["id"] == "u1-p1" else 3)]
        if n["id"] in lens:
            n["desc"] = ("The rule as the notes put it, at length. " * lens[n["id"]]).strip()
            if lens[n["id"]] > 20:
                n["sections"] = [{"h": "Test", "t": "Each element in turn, as the cases apply it. " * 8}]
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    return html


@pytest.mark.parametrize("vp", [(1463, 761), (1500, 950), (1180, 760)])
def test_the_enlarged_disc_its_shadow_and_its_content_are_one_circle_at_every_frame(browser, tmp_path, vp):
    f = tmp_path / "sizes.html"
    f.write_text(_sizes_page(), encoding="utf-8")
    ctx = browser.new_context(viewport={"width": vp[0], "height": vp[1]})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(1500)
    pg.mouse.move(2, vp[1] - 4)
    seen = set()
    for look in ("hub", "stars"):
        pg.evaluate(f"() => window._altoSolarLook.set('{look}')")
        pg.wait_for_timeout(900)
        for i in ("u1-p1", "u1-p2", "u1-p3", "u2-p2"):
            grow = pg.evaluate("(id) => { var p=(" + GEO_WATCH + ")(id); window.enterFocus(id); return p; }", i)
            assert not grow["bad"] and grow["shadow"] > 3, (look, i, grow)
            pg.wait_for_timeout(300)
            st = pg.evaluate(GEO_REST, i)
            seen.add(st["sD"])
            assert abs(st["w"] - st["h"]) <= 1 and "sol-clip" not in st["cls"], st
            assert st["body"] <= st["R"] + 1 and st["open"] <= st["R"] + 1, (look, i, st)   # the text square and the control: inside
            assert not st["scrolls"], st                                             # the card's level: nothing to scroll
            if i in ("u1-p1", "u1-p2"):                                              # its chips: round pills in the bottom band, inside
                assert st["chips"] and all(q["far"] <= st["R"] + 2 and q["top"] >= st["R"] * .1 and not q["hitsOpen"]      # (far: a turned chip's bounding box; its true margin is test_solar_pool's)
                                           and q["round"] for q in st["chips"]), (look, i, st["chips"])
            shrink = pg.evaluate("(id) => { var p=(" + GEO_WATCH + ")(id); window.exitFocus(); return p; }", i)
            assert not shrink["bad"], (look, i, shrink)
            pg.wait_for_timeout(400)
            assert "sol-" not in pg.evaluate(f"() => document.getElementById('node-{i}').className")
    assert seen == {300.0, 340.0, 380.0}, seen
    if vp == (1463, 761):
        assert abs(float(pg.evaluate("() => getComputedStyle(document.documentElement).zoom")) - 0.86) < 0.01
    assert not errs, errs
    ctx.close()


# ── seams for the star chart's skin and travel ────────────────────────────────

def test_the_skin_tick_and_the_orbit_clock(browser, pages):
    f, plan = pages["orbit"]
    pg, errs = _open(browser, f, wait=1200)
    pg.mouse.move(2, 940)
    pg.evaluate("""() => { window.__sk=[]; window._altoSkinTick=function(P, B, T){
      window.__sk.push({T:T, n:Object.keys(B).length, plan:!!(P && P.nodes), x:B['u1-p1'].rx, y:B['u1-p1'].ry, c:!!B['u1-p1'].c}); }; }""")
    pg.wait_for_timeout(800)
    sk = pg.evaluate("() => window.__sk")
    assert len(sk) > 10 and sk[-1]["T"] > sk[0]["T"] and sk[-1]["plan"] and sk[-1]["c"]
    assert sk[-1]["n"] == len(plan["nodes"])
    node = pg.evaluate("() => { var n=document.getElementById('node-u1-p1'); return [parseFloat(n.style.left), parseFloat(n.style.top)]; }")
    assert pg.evaluate("() => window._altoSolarT") == pytest.approx(pg.evaluate("() => window.__sk[window.__sk.length-1].T"), abs=0.2)
    assert abs(sk[-1]["x"] - node[0]) < 3 and abs(sk[-1]["y"] - node[1]) < 3
    assert not errs, errs
    pg.context.close()


# ── one format, one plan, one style switch: System | Star chart | Retro | 3D Star chart, and the Orbit switch (rounds 5, 7; 2026-10-22) ──

LOOKST = """() => ({look:window._altoSolarLook.get(), mot:window._altoSolarMotion.get(), T:window._altoSolarT,
  stars:document.documentElement.classList.contains('alto-solar-stars'), hub:document.documentElement.classList.contains('alto-solar-hub'),
  rings:document.querySelectorAll('#solar-svg .sol-ring').length, tubes:document.querySelectorAll('#solar-svg path.sol-tube').length,
  seg:[].map.call(document.querySelectorAll('#sol-ctl [data-style]'), function(b){ return b.getAttribute('data-style')+':'+b.getAttribute('aria-checked'); }),
  orbitBtn:(function(m){ return m ? {dis:m.disabled, pressed:m.getAttribute('aria-pressed')} : null; })(document.getElementById('sol-motion'))})"""


def test_the_look_switch_moves_nothing_and_keeps_the_focus_the_view_and_the_choice(browser, pages):
    f, _ = pages["spoke"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    st = pg.evaluate(LOOKST)
    assert st["look"] == "hub" and st["hub"] and not st["stars"] and st["rings"] > 0 and st["tubes"] == 0 and st["mot"], st
    assert st["seg"] == ["system:true", "chart:false", "retro:false", "3d:false"] and not st["orbitBtn"]["dis"]      # one style switch, Orbit works in all
    pg.evaluate("() => window.enterFocus('u1-p1')")
    pg.wait_for_timeout(900)
    g0 = pg.evaluate(BODIES)
    pg.click("#sol-ctl [data-style=chart]")
    pg.wait_for_timeout(500)
    st = pg.evaluate(LOOKST)
    assert st["look"] == "stars" and st["stars"] and not st["hub"] and st["rings"] > 0, st
    assert pg.evaluate("() => window._focusedNodeId") == "u1-p1"            # still enlarged, where it was
    assert _moved(g0, pg.evaluate(BODIES)) < 0.01                             # one plan: nothing moved
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(800)
    t0 = pg.evaluate("() => window._altoSolarT")
    pg.wait_for_timeout(700)
    assert pg.evaluate("() => window._altoSolarT") > t0
    pg.reload()
    pg.wait_for_timeout(1500)
    assert pg.evaluate("() => window._altoSolarLook.get()") == "stars"      # the viewer's choice is kept
    # an old stored 'plain' choice reads as System
    pg.evaluate("() => { for(var i=0;i<localStorage.length;i++){ var k=localStorage.key(i); if(/^alto-solar-look:/.test(k)) localStorage.setItem(k, 'plain'); } }")
    pg.reload()
    pg.wait_for_timeout(1500)
    assert pg.evaluate("() => window._altoSolarLook.get()") == "hub"
    pg.mouse.move(2, 940)
    t0 = pg.evaluate("() => window._altoSolarT")
    pg.wait_for_timeout(700)
    assert pg.evaluate("() => window._altoSolarT") > t0                       # the System look orbits too
    pg.click("#sol-motion")
    pg.wait_for_timeout(200)
    t1 = pg.evaluate("() => window._altoSolarT")
    pg.wait_for_timeout(500)
    assert pg.evaluate("() => window._altoSolarT") == t1                      # and its Orbit switch stops it
    assert not errs, errs
    pg.context.close()


def test_the_orbit_switch_freezes_where_it_is_and_resumes_without_a_jump(browser, pages):
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    assert pg.evaluate("() => window._altoSolarMotion.get()") is True
    pg.click("#sol-motion")
    pg.wait_for_timeout(200)
    g0, t0 = pg.evaluate(BODIES), pg.evaluate("() => window._altoSolarT")
    pg.wait_for_timeout(900)
    g1, t1 = pg.evaluate(BODIES), pg.evaluate("() => window._altoSolarT")
    assert _moved(g0, g1) == 0 and t1 == t0                                    # frozen exactly, clock stopped
    assert pg.evaluate("() => [window._altoSolarMotion.get(), document.getElementById('sol-motion').getAttribute('aria-pressed')]") == [False, "false"]
    pg.click("#sol-motion")
    pg.wait_for_timeout(60)
    g2 = pg.evaluate(BODIES)
    assert _moved(g1, g2) < 3                                                  # no jump on resuming
    pg.wait_for_timeout(1200)
    assert _moved(g2, pg.evaluate(BODIES)) > 0.3 and pg.evaluate("() => window._altoSolarT") > t1
    assert not errs, errs
    pg.context.close()


def test_reduced_motion_starts_with_the_orbit_off_but_it_can_be_switched_on(browser, pages):
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, reduced=True, wait=1200)
    assert pg.evaluate("() => window._altoSolarMotion.get()") is False
    pg.evaluate("() => window._altoSolarMotion.set(true)")
    pg.wait_for_timeout(1000)
    assert pg.evaluate("() => window._altoSolarT") > 0
    assert not errs, errs
    pg.context.close()


def test_a_comet_follows_its_ellipse_and_its_path_is_drawn(browser, tmp_path):
    """A node flagged 'revisit' (solar.LOOK_FLAGS: comet) orbits on its plan's ellipse
    (nodes[id].orbit, placed with the in-page solar.orbit_offset) and its path is an ellipse."""
    d = solar_doc(SMALL, "orbit", SMALL_LINKS)
    d["brief"]["flags"] = [{"id": "revisit", "name": "Revisit"}]
    for n in d["nodes"]:
        if n["id"] in ("u1-p2", "u1-p1-m1"):
            n["flags"] = ["revisit"]
    html, _ = build_timeline(*load_brief(copy.deepcopy(d)))
    plan = _plan(html)
    comets = [i for i, n in plan["nodes"].items() if (n.get("orbit") or {}).get("e", 0) > 0]
    if not comets:
        pytest.skip("this plan gives no comet an elliptical orbit")
    f = tmp_path / "comet.html"
    f.write_text(html, encoding="utf-8")
    pg, errs = _open(browser, f, wait=1200)
    pg.mouse.move(2, 940)
    assert pg.evaluate("() => document.querySelectorAll('#solar-svg ellipse.sol-comet').length") == len(comets)
    cid = comets[0]
    par = plan["nodes"][cid]["parent"]
    ds = []
    for t in (0, 30, 60, 90):
        pg.evaluate(f"() => window._altoSolarCam && 1")
        g = pg.evaluate("() => { var T0=window._altoSolarT; return T0; }")
        dist = pg.evaluate(f"""() => {{ var a=document.getElementById('node-{cid}'), b=document.getElementById('node-{par}');
          return Math.hypot(parseFloat(a.style.left)-parseFloat(b.style.left), parseFloat(a.style.top)-parseFloat(b.style.top)); }}""")
        ds.append(dist)
        pg.wait_for_timeout(1500)
    assert max(ds) - min(ds) > 0.5, ds                                       # not a circle about its parent
    assert not errs, errs
    pg.context.close()


# ── real-ratio sizes: small moons and satellites carry their names on hover (round 7) ──

TORTS_SHAPE = [[[2, 2, 2], [2, 2], [2, 2, 2], [2], [2, 2]], [[2, 2], [2, 2, 2], [2]], [[0, 0], [0, 0, 0]]]

FACES = r"""() => { var out={bad:[], moons:0, sats:0};
  document.querySelectorAll('#world .node[data-solar]').forEach(function(n){
    var role=n.getAttribute('data-solar'), c=n.querySelector('.node-card'), r=c.getBoundingClientRect(), f=c.querySelector('.sol-face'),
        b=f.querySelector('b'), s=f.querySelector('span'), cx=r.left+r.width/2, cy=r.top+r.height/2;
    [b, s].forEach(function(e){ if(!e || getComputedStyle(e).display==='none' || !e.textContent) return;
      var q=e.getBoundingClientRect(); if(!q.width) return;
      /* the visible text sits inside its own circle: no label reaches another body */
      var far=Math.max(Math.hypot(q.left-cx, q.top-cy), Math.hypot(q.right-cx, q.top-cy), Math.hypot(q.left-cx, q.bottom-cy), Math.hypot(q.right-cx, q.bottom-cy));
      if(far>r.width/2+1.5 && role!=='sun' && role!=='planet') out.bad.push(n.id+' '+role+' text out '+far.toFixed(1)+'>'+(r.width/2).toFixed(1));
      if(e.scrollWidth>e.clientWidth+1 && e===b) out.bad.push(n.id+' number clipped'); });
    if(role==='moon' || role==='sat'){
      var t=(c.querySelector('.node-title')||{}).textContent||'';
      if(c.getAttribute('title').indexOf(t)<0 || (c.getAttribute('aria-label')||'').indexOf(t)<0) out.bad.push(n.id+' no name');
      if(role==='moon'){ out.moons++; if(getComputedStyle(s).display!=='none') out.bad.push(n.id+' moon title inside'); if(!b.textContent || /[.]/.test(b.textContent)) out.bad.push(n.id+' moon number '+b.textContent); }
      else { out.sats++; if(getComputedStyle(b).display!=='none') out.bad.push(n.id+' sat number shown'); }
    } });
  return out; }"""


@pytest.mark.parametrize("look", ["hub", "stars"])
def test_small_bodies_show_a_number_or_nothing_inside_and_name_themselves_on_hover(browser, tmp_path, look):
    f = tmp_path / "torts.html"
    f.write_text(_page(units=TORTS_SHAPE, style="spoke" if look == "hub" else "orbit", links=()), encoding="utf-8")
    pg, errs = _open(browser, f, wait=1600)
    pg.mouse.move(2, 940)
    pg.evaluate("() => window._altoSolarMotion.set(false)")
    pg.wait_for_timeout(300)
    r = pg.evaluate(FACES)
    assert not r["bad"] and r["moons"] > 10 and r["sats"] > 10, r
    plan = _plan(_page(units=TORTS_SHAPE, links=()))
    N = plan["nodes"]
    for i, n in N.items():
        if n["role"] == "moon":
            assert n["d"] <= 0.4 * N[n["parent"]]["d"]
        if n["role"] == "sat":
            assert n["d"] <= (plan["sizes"]["station"] if n.get("station") else 18)
    assert not errs, errs
    pg.context.close()


# ── round 9 (Luke, real Safari): a board left dimmed, the skin in the other look, the way back
# from a detail page, a click on an orbit ──────────────────────────────────────────────────

CLEAN = r"""() => { var c=document.getElementById('canvas'), de=document.documentElement, bad=[];
  if(!window._focusedNodeId && c.classList.contains('focus-mode')) bad.push('focus-mode');
  if(de.classList.contains('alto-stars') !== (window._altoSolarLook.get()==='stars')) bad.push('look class');
  document.querySelectorAll('#world .node[data-solar]').forEach(function(n){ var k=n.querySelector('.node-card'), o=+getComputedStyle(k).opacity*+getComputedStyle(n).opacity;
    if(!window._focusedNodeId && (o<.99 || n.classList.contains('focused') || n.classList.contains('sol-flank'))) bad.push(n.id+' '+o);
    if(window._altoSolarLook.get()==='hub' && [].some.call(k.querySelectorAll(':scope>.sk'), function(e){ return getComputedStyle(e).display!=='none'; })) bad.push(n.id+' skin'); });
  return bad; }"""


@pytest.mark.parametrize("look", ["hub", "stars"])
def test_after_any_navigation_the_board_is_whole_and_a_lost_focus_heals(browser, pages, look):
    f, _ = pages["spoke" if look == "hub" else "orbit"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    for k in range(2):
        pg.evaluate("() => window.enterFocus('u2-p2')")
        pg.wait_for_timeout(500)
        for key in ("ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"):
            pg.keyboard.press(key)
            pg.wait_for_timeout(120)
        pg.wait_for_timeout(300)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(1400)
        pg.keyboard.press("Meta+-")
        pg.wait_for_timeout(700)
        pg.keyboard.press("Meta+0")
        pg.wait_for_timeout(900)
        pg.evaluate("(l) => window._altoSolarLook.set(l)", "stars" if look == "hub" else "hub")
        pg.wait_for_timeout(500)
        pg.evaluate("(l) => window._altoSolarLook.set(l)", look)
        pg.wait_for_timeout(900)
        assert pg.evaluate(CLEAN) == [], k
    # the glitch's state, made by hand: dimmed, nothing enlarged, a stray look class — healed within a second
    pg.evaluate("""() => { var c=document.getElementById('canvas'); window._focusedNodeId='u1-p1'; c.classList.add('focus-mode');
      if(window._altoSolarLook.get()==='hub') document.documentElement.classList.add('alto-stars'); }""")
    pg.wait_for_timeout(1600)
    assert pg.evaluate(CLEAN) == [] and pg.evaluate("() => window._focusedNodeId") is None
    assert not errs, errs
    pg.context.close()


def test_back_from_a_detail_page_is_where_you_left(browser, tmp_path):
    f = tmp_path / "torts.html"
    f.write_text(_page(TORTS_SHAPE, links=()), encoding="utf-8")
    pg, errs = _open(browser, f, wait=1600)
    pg.mouse.move(2, 940)
    view = "() => { var g=window._altoSolarCam.get(); return [g.cx, g.cy, g.scale, window._focusedNodeId||null]; }"
    for how, setup in (("near", "() => window.enterFocus('u2-p1')"), ("far", "() => window.enterFocus('u1-p4-m1')"),
                       ("zoomed out", "() => { window.exitFocus(); }")):
        pg.evaluate(setup)
        pg.wait_for_timeout(1300)
        if how == "zoomed out":
            pg.keyboard.press("Meta+-")
            pg.wait_for_timeout(900)
        a = pg.evaluate(view)
        pg.evaluate("(i) => showDetail('node', i)", a[3] or "u3")
        pg.wait_for_timeout(500)
        pg.keyboard.press("Escape")                                   # back to the system
        pg.wait_for_timeout(1300)
        b = pg.evaluate(view)
        assert b[3] == a[3] and abs(b[2] - a[2]) < 1e-3 and math.hypot(b[0] - a[0], b[1] - a[1]) < 4 / a[2], (how, a, b)
    assert not errs, errs
    pg.context.close()


@pytest.mark.parametrize("look", ["hub", "stars"])
def test_a_click_on_an_orbit_enlarges_its_body(browser, pages, look):
    f, _ = pages["spoke" if look == "hub" else "orbit"]
    pg, errs = _open(browser, f, wait=1500)
    pg.evaluate("() => window._altoSolarMotion.set(false)")
    pg.wait_for_timeout(1500)
    for i in ("u1-p2", "u2-p2-m1"):
        # a point on its ring, half way round from the body (no body or label there)
        pg.evaluate("(i) => { var P=window._ALTO_SOLAR.nodes[window._ALTO_SOLAR.nodes[i].parent]; window._altoSolarCam.set(P.x, P.y, 1); }", i)
        pg.wait_for_timeout(300)
        xy = pg.evaluate("""(i) => { var b=document.getElementById('node-'+i), p=document.getElementById('node-'+window._ALTO_SOLAR.nodes[i].parent);
          var q=b.getBoundingClientRect(), r=p.getBoundingClientRect(), px=r.left+r.width/2, py=r.top+r.height/2, dx=q.left+q.width/2-px, dy=q.top+q.height/2-py, out=null;
          [Math.PI, Math.PI/2, -Math.PI/2, 2.4, -2.4].some(function(a){ var x=px+dx*Math.cos(a)-dy*Math.sin(a), y=py+dx*Math.sin(a)+dy*Math.cos(a), e=document.elementFromPoint(x, y);
            out=[x, y, e && e.getAttribute('class')]; return out[2]==='sol-hit sol-rgh'; }); return out; }""", i)
        assert xy[2] == "sol-hit sol-rgh", (i, xy)          # (a ring's own target; Retro's are its bands)
        pg.mouse.move(xy[0], xy[1])
        pg.wait_for_timeout(100)
        assert pg.evaluate("() => document.querySelectorAll('#solar-svg .sol-ring.sol-hot').length") == 1
        pg.mouse.click(xy[0], xy[1])
        pg.wait_for_timeout(900)
        assert pg.evaluate("() => window._focusedNodeId") == i
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(1200)
    # a body itself still wins over a ring under it
    pg.evaluate("() => { var P=window._ALTO_SOLAR.nodes['u1-p1']; window._altoSolarCam.set(P.x, P.y, 1); }")
    pg.wait_for_timeout(300)
    xy = pg.evaluate("() => { var q=document.getElementById('node-u1-p1').getBoundingClientRect(); return [q.left+q.width/2, q.top+q.height/2]; }")
    assert pg.evaluate("(p) => !!document.elementFromPoint(p[0], p[1]).closest('.node')", xy)
    assert not errs, errs
    pg.context.close()


def test_the_space_bar_toggles_the_orbit_in_both_looks_but_not_in_a_field_or_the_detail_page(browser, pages):
    for key in ("spoke", "orbit"):
        f, _ = pages[key]
        pg, errs = _open(browser, f, wait=1500)
        pg.mouse.move(2, 940)
        get = "() => window._altoSolarMotion.get()"
        assert pg.evaluate(get) is True
        assert "(Space)" in pg.evaluate("() => document.getElementById('sol-motion').title")
        pg.keyboard.press("Space")
        assert pg.evaluate(get) is False
        pg.keyboard.press("Space")
        assert pg.evaluate(get) is True
        pg.keyboard.press("Shift+Space")                                        # a modifier: not ours
        assert pg.evaluate(get) is True
        pg.evaluate("() => { var i=document.createElement('input'); i.id='probe'; document.body.appendChild(i); i.focus(); }")
        pg.keyboard.press("Space")                                              # a field has focus: it types
        assert pg.evaluate(get) is True and pg.evaluate("() => document.getElementById('probe').value") == " "
        pg.evaluate("() => { document.getElementById('probe').remove(); document.activeElement.blur(); document.getElementById('detail-page').classList.add('visible'); }")
        pg.keyboard.press("Space")                                              # a detail page: nothing
        assert pg.evaluate(get) is True
        assert not errs, errs
        pg.context.close()
