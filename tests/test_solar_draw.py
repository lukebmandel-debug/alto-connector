"""The solar outline's drawing (alto/build/solar_draw.py): circles for cards,
orbit rings and spokes under them, and — in the "orbit" style — the bodies
turning round what they orbit, stopping for hover, focus and the rest.

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


def solar_doc(units, style="orbit", links=()):
    """An outline bundle: units = [[moons per planet as [sats per moon]]].
    Ids spell the place: u1, u1-p2, u1-p2-m1, u1-p2-m1-s1."""
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
    brief = {"title": "Solar draw", "subject": "s", "timeline_id": "solar-draw", "mode": "outline",
             "layout": "solar", "hub_style": style, "columns": 5, "node_noun": "Concept",
             "period_noun": "Unit", "accent": "#a78bfa", "acts": acts, "entities": [], "axes": [],
             "relations": [{"key": "spine", "label": "Contains"},
                           {"key": "limits", "label": "Limits", "color": "#f43f5e"}]}
    return {"brief": brief, "nodes": nodes, "connections": [list(l) + ["limits"] for l in links]}


SMALL = [[[0, 0], [], [0]], [[0], [0, 2]], [[], [0]]]
SMALL_LINKS = [("u1-p1", "u2-p2"), ("u1-p1-m1", "u1-p3")]


def _page(units=SMALL, style="orbit", links=SMALL_LINKS):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(units, style, links))))
    return html


def _plan(html):
    at = html.index("window._ALTO_SOLAR=") + len("window._ALTO_SOLAR=")
    return json.JSONDecoder().raw_decode(html[at:])[0]


# ── what the page carries ────────────────────────────────────────────────────

def test_a_solar_page_carries_the_drawing_and_a_tree_page_does_not():
    html = _page()
    assert html.count("window._altoSolarLayout=") == 1 and "#solar-svg" in html
    assert "html.alto-solar:not(.mobile)" in html
    d = solar_doc(SMALL)
    d["brief"]["layout"] = "tree"
    tree, _ = build_timeline(*load_brief(d))
    assert "window._altoSolarLayout=" not in tree and "#solar-svg{" not in tree


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
    assert re.findall(r"(\w+)\.style\.transform=", SOLAR_JS) == ["world", "world"]
    assert ".n.style.transform" not in SOLAR_JS
    assert "b.n.style.left=x+'px'" in SOLAR_JS and "Math.round(v*zq)/zq" in SOLAR_JS
    # no SVG <mask> on anything that moves (Safari): the rings and spokes are plain
    assert "<mask" not in SOLAR_JS and "'mask'" not in SOLAR_JS


def test_every_pause_is_there():
    for s in ("alto-editing", "beforeprint", "prefers-reduced-motion", "document.hidden", "_focusedNodeId",
              "focus-mode", "edge-hover", "alto-found", "detail-page.visible", "mobile", "dimmed"):
        assert s in SOLAR_JS, s


def test_the_drawing_is_small():
    size = len(gzip.compress((SOLAR_JS + SOLAR_CSS).encode("utf-8"), 9))
    assert size < 15000, size


def test_spoke_style_has_no_motion_and_draws_tubes():
    plan = _plan(_page(style="spoke"))
    assert plan["style"] == "spoke"
    assert all(p["period"] == 0 for s in plan["systems"] for p in s["planets"])
    assert "MOVES=ORBIT &&" in SOLAR_JS and "'sol-tube'" in SOLAR_JS


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
    for name, html in (("orbit", _page()), ("spoke", _page(style="spoke"))):
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
        assert abs(b["w"] - b["h"]) < 0.5 and abs(b["w"] - b["d"]) < 1, (i, b)       # offset* round
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


def test_reduced_motion_and_spoke_stand_still(browser, pages):
    for style, reduced in (("orbit", True), ("spoke", False)):
        f, _ = pages[style]
        pg, errs = _open(browser, f, reduced=reduced)
        g0 = pg.evaluate(BODIES)
        pg.wait_for_timeout(1200)
        g1 = pg.evaluate(BODIES)
        assert _moved(g0, g1) == 0 and g1["T"] == 0, style
        if style == "spoke":
            assert not g1["rings"] and g1["spokes"] > 0
        assert not errs, errs
        pg.context.close()


def test_arrow_keys_pick_the_body_that_way_where_it_is_now(browser, pages):
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, wait=1800)
    pg.mouse.move(2, 940)
    pg.evaluate("() => window.enterFocus('u1')")
    pg.wait_for_timeout(700)
    g = pg.evaluate(BODIES)
    sun = g["b"]["u1"]
    for key, (ux, uy) in (("ArrowRight", (1, 0)), ("ArrowLeft", (-1, 0)), ("ArrowDown", (0, 1)), ("ArrowUp", (0, -1))):
        pg.evaluate("() => window.enterFocus('u1')")
        pg.wait_for_timeout(650)
        pg.keyboard.press(key)
        pg.wait_for_timeout(700)
        got = pg.evaluate("() => window._focusedNodeId")
        if got == "u1":
            continue                                       # nothing that way
        b = g["b"][got]
        dx, dy = b["x"] - sun["x"], b["y"] - sun["y"]
        assert dx * ux + dy * uy > 0, (key, got)            # it is that way from the sun, now
    pg.evaluate("() => window.exitFocus()")
    pg.wait_for_timeout(1500)
    # every card that was enlarged on the way is a circle again
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
@pytest.mark.parametrize("style", ["orbit", "spoke"])
@pytest.mark.parametrize("units", [SMALL, [[[2, 2, 2], [2, 2], [2, 2, 2], [2], [2, 2]], [[0, 0], [0, 0, 0]]],
                                   [[[0, 1, 0], [0, 0], [0, 0, 0], [0, 0, 0]], [[2, 2, 0, 0], [0, 0, 0, 0]], [[]]]])
@pytest.mark.parametrize("bumped", [False, True])
def test_the_page_plans_the_systems_exactly_as_solar_py(tmp_path, units, style, bumped):
    """Edit mode re-plans in the page from the live tables; that plan is solar.py's
    (sizes by child count, a pivotal flag one tier up)."""
    doc = solar_doc(units, style)
    if bumped:
        doc["brief"]["flags"] = [{"id": "pivotal", "name": "Pivotal"}]
        for n in doc["nodes"]:
            if n["id"] in ("u1-p1", "u1-p1-m1", "u2-p2"):
                n["flags"] = ["pivotal"]
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
      var O=window._ALTO_OUTLINE, mv=['u1-p3','u1-p3-m1'];
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
    assert out["rings"] == sum(len(u) for u in SMALL)
    assert not errs, errs
    pg.context.close()


def test_the_whole_chart_zooms_out_to_fit_and_a_click_comes_back_down(browser, pages):
    """Luke (round 2): however big the chart, the reader can zoom out and see all
    of it, the circles shrinking with it — the toggle, ⌘−, pinch — and the orbits go on."""
    f, _ = pages["orbit"]
    pg, errs = _open(browser, f, wait=1500)
    pg.mouse.move(2, 940)
    pg.click("#sol-fit")
    pg.wait_for_timeout(900)
    st = pg.evaluate("""() => { var w=document.getElementById('world').getBoundingClientRect(), c=document.getElementById('canvas').getBoundingClientRect();
      return {z:window._altoSolarZoom(), w:[w.left, w.top, w.right, w.bottom], c:[c.left, c.top, c.right, c.bottom]}; }""")
    assert st["z"] < 1
    w, c = st["w"], st["c"]
    assert w[0] >= c[0] - 1 and w[1] >= c[1] - 1 and w[2] <= c[2] + 1 and w[3] <= c[3] + 1, st   # all of it in view
    g0 = pg.evaluate(BODIES)
    pg.wait_for_timeout(900)
    assert _moved(g0, pg.evaluate(BODIES)) > 0.3                       # the orbits go on
    xy = pg.evaluate("() => { var r=document.querySelector('#node-u2-p1 .node-card').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    pg.mouse.click(xy[0], xy[1])
    pg.wait_for_timeout(1600)
    assert pg.evaluate("() => [window._altoSolarZoom(), window._focusedNodeId]") == [1, "u2-p1"]
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(700)
    pg.keyboard.press("Control+Minus")
    pg.wait_for_timeout(800)
    assert pg.evaluate("() => window._altoSolarZoom()") < 1
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(800)
    assert pg.evaluate("() => [window._altoSolarZoom(), document.getElementById('world').style.transform]") == [1, ""]
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
