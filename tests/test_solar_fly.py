"""Flying between bodies on a Star chart (alto/build/solar_fly.py).

The planner's properties on its Python twin (tests/solar_fly_twin.py), the
twin held equal to the page's JS under node, what the pages carry, and the
flight in a real browser (Chromium and WebKit through Playwright; skipped
without them): it runs, lands on the body where it is, can be re-targeted and
stopped, leaves the System look alone, and costs its frames little. Browser
geometry is read in plan / layout px (window._altoSolarCam, style.left/top),
never screen px (Playwright's WebKit is not Safari)."""
import copy
import gzip
import json
import math
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import solar_fly_twin as tw                                   # noqa: E402
from alto.build.builder import build_timeline, load_brief    # noqa: E402
from alto.build.solar import solar_plan                      # noqa: E402
from alto.build.solar_fly import FLY, FLY_CSS, FLY_JS, FLY_PLAN_JS   # noqa: E402
from test_solar_draw import solar_doc                         # noqa: E402

NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
needs_node = pytest.mark.skipif(not Path(NODE).is_file(), reason="needs node")

# synthetic plans: two systems with moons and satellites; one system in depth;
# three systems of mixed families (a planet with three moons, empty planets)
SHAPES = ([[[0, 0], [], [0, 2], [1], [], [0]], [[0], [0, 2], []]],
          [[[2, 1], [0]]],
          [[[0], [3]], [[1, 1, 0]], [[], [0, 0]]])


def _plan(units, style="orbit"):
    b, nodes, _ = load_brief(copy.deepcopy(solar_doc(units, style, ())))[:3]
    return solar_plan(b, nodes)


def _comets(S):
    """The Star chart look's comets (alto-solar-arch: nodes[id].orbit {e, rot, k},
    an ellipse round what it orbits; k 1 = Kepler-paced, a planet): a planet and
    a moon of the first system made comets, as solar.py would mark them."""
    S = copy.deepcopy(S)
    S["nodes"]["u1-p2"]["orbit"] = {"e": 0.42, "rot": 1.1, "k": 1}
    S["nodes"]["u1-p3-m1"]["orbit"] = {"e": 0.3, "rot": 0.4, "k": 0}
    # the galactic core between the systems (solar.py's plan.core {x, y, r} for 2+ systems)
    assert S.get("core") and len(S["systems"]) > 1
    return S


@pytest.fixture(scope="module")
def plans():
    return [_plan(u) for u in SHAPES] + [_comets(_plan(SHAPES[0]))]


def _routes(plans, n=200, seed=7):
    rng = random.Random(seed)
    for k in range(n):
        S = plans[k % len(plans)]
        W = tw.bodies(S)
        A, B = rng.sample(sorted(i for i in W["B"] if W["B"][i]["role"] != "core"), 2)
        o = {"T0": rng.uniform(0, 200), "r0": rng.choice([0.0, 0.4, 1.0]), "view": [1500, 950]}
        yield S, W, A, B, o, tw.plan(S, A, B, o)


# ── the planner ──────────────────────────────────────────────────────────────

def test_every_flight_arrives_on_its_body_where_the_body_will_be(plans):
    """200 random from/to pairs (two systems, moons, satellites): at the end
    the craft is within 1 px of the target's predicted place at that moment,
    and the flight is 2.5-7 s."""
    kinds = set()
    for S, W, A, B, o, R in _routes(plans):
        assert R is not None, (A, B)
        D = R["D"]
        assert FLY["D_MIN"] - 1e-9 <= D <= FLY["D_MAX"] + 1e-9, (A, B, D)
        end = tw.at(W, R, D)
        tgt = tw.pos(W, B, tw.clock(R["c"], D))
        assert math.hypot(end[0] - tgt[0], end[1] - tgt[1]) < 1.0, (A, B)
        # and it set off from where A was
        p0 = tw.at(W, R, 0.0)
        a0 = tw.pos(W, A, o["T0"])
        assert math.hypot(p0[0] - a0[0], p0[1] - a0[1]) < 1e-6, (A, B)
        assert all(math.isfinite(v) for t in range(41) for v in tw.at(W, R, D * t / 40))
        kinds |= {q[0] for q in R["steps"]}
    assert kinds >= {"esc", "xfer", "fly", "bez", "park", "inj", "ret"}, kinds


def test_the_legs_join_smoothly(plans):
    """At every join between legs the craft neither jumps nor jolts: the
    position is continuous and the velocity (C1, numerically) changes by
    under a fifth of the speed there."""
    for S, W, A, B, o, R in _routes(plans, seed=11):
        D = R["D"]
        for L in R["legs"][1:]:
            t = D * tw.ease_inv(L["s0"])
            a, b = tw.at(W, R, t - 1e-7), tw.at(W, R, t + 1e-7)
            assert math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-3, (A, B, L["k"])
            v1, v2 = tw._vel(W, R, t, -1), tw._vel(W, R, t, +1)
            sp = max(math.hypot(*v1), math.hypot(*v2), 1.0)
            assert math.hypot(v1[0] - v2[0], v1[1] - v2[1]) / sp < 0.2, (A, B, L["k"], v1, v2)


def test_it_starts_and_lands_at_rest_with_the_orbits(plans):
    for S, W, A, B, o, R in list(_routes(plans, n=40, seed=5)):
        D, c = R["D"], R["c"]
        assert tw.clock_rate(c, D) == 0.0                  # the orbits stop as it lands
        assert abs(tw.clock_rate(c, 0.0) - o["r0"]) < 1e-12
        v = tw._vel(W, R, D, -1)
        assert math.hypot(*v) < 5.0                          # px/s: at rest on arrival (the last 1/1000 of the curve)


def test_a_comet_is_met_on_its_ellipse(plans):
    S = plans[3]
    W = tw.bodies(S)
    for A, B in (("u1-p1", "u1-p2"), ("u1-p3", "u1-p3-m1"), ("u2-p1", "u1-p2"), ("u1-p2", "u1-p6")):
        for T0 in (0.0, 37.0, 81.5):
            R = tw.plan(S, A, B, {"T0": T0})
            end = tw.at(W, R, R["D"])
            tgt = tw.pos(W, B, tw.clock(R["c"], R["D"]))
            assert math.hypot(end[0] - tgt[0], end[1] - tgt[1]) < 1.0
    # and the comet is on its ellipse: not on the circle its home was on
    b = W["B"]["u1-p2"]
    rs = [math.hypot(*(tw.pos(W, "u1-p2", t)[k] - tw.pos(W, "u1", t)[k] for k in (0, 1))) for t in range(0, 120, 7)]
    assert max(rs) - min(rs) > 0.06 * b["r"]                     # r(1 ± c), c ≈ 0.05 at e 0.42


def test_between_systems_the_craft_swings_round_the_galactic_core(plans):
    """When the core lies ahead with room to turn round it (_by_core), the
    cruise between systems swings round it."""
    S = plans[2]
    W = tw.bodies(S)
    R, ids = None, sorted(i for i in W["B"] if W["B"][i]["role"] != "core")
    for T0 in (5.0, 40.0, 80.0):
        for A in ids:
            for B in ids:
                if tw.chain(W, A)[-1] != tw.chain(W, B)[-1]:
                    R = tw.plan(S, A, B, {"T0": T0})
                    if ["fly", "#core"] in R["steps"]:
                        break
            if ["fly", "#core"] in R["steps"]:
                break
        if ["fly", "#core"] in R["steps"]:
            break
    assert R and ["fly", "#core"] in R["steps"], "no route between the systems goes round the core"
    st = [q[0] for q in R["steps"]]
    i = R["steps"].index(["fly", "#core"])
    assert st[i - 1] == "bez" and st[i + 1] == "bez", st
    L = R["legs"][i]
    core = S["core"]
    t0, t1 = R["D"] * tw.ease_inv(L["s0"]), R["D"] * tw.ease_inv(L["s1"])
    near = min(math.hypot(*(tw.at(W, R, t0 + (t1 - t0) * k / 40)[j] - (core["x"], core["y"])[j] for j in (0, 1))) for k in range(41))
    assert near < core["r"] + FLY["FLY_Q"] + 2                 # it passes close round the black hole
    end, tgt = tw.at(W, R, R["D"]), tw.pos(W, R["to"], tw.clock(R["c"], R["D"]))
    assert math.hypot(end[0] - tgt[0], end[1] - tgt[1]) < 1.0
    # no core: no swing round it; never a flight to or from the core itself
    bare = {k: v for k, v in S.items() if k != "core"}
    assert ["fly", "#core"] not in tw.plan(bare, R["from"], R["to"], {"T0": R["c"]["T0"]})["steps"]
    assert tw.plan(S, "#core", "u1") is None and tw.plan(S, "u1", "#core") is None


def test_a_black_hole_is_the_swing_by_of_choice(plans):
    S = copy.deepcopy(plans[0])
    W = tw.bodies(S)
    st = tw.plan(S, "u1-p1", "u1-p6", {"T0": 3.0})["steps"]
    mid = st[1][1]
    other = next(i for i in ("u1-p2", "u1-p3", "u1-p4", "u1-p5") if i != mid)
    S["nodes"][other]["look"] = "blackhole"
    assert tw.plan(S, "u1-p1", "u1-p6", {"T0": 3.0})["steps"][1] == ["fly", other]


def test_with_the_orbits_switched_off_the_craft_flies_among_still_bodies(plans):
    S = plans[0]
    W = tw.bodies(S)
    R = tw.plan(S, "u1-p1", "u1-p4", {"T0": 8.0, "still": True})
    assert all(tw.clock(R["c"], R["D"] * k / 10) == 8.0 for k in range(11))
    end, tgt = tw.at(W, R, R["D"]), tw.pos(W, "u1-p4", 8.0)
    assert math.hypot(end[0] - tgt[0], end[1] - tgt[1]) < 1.0


def test_routes_follow_the_rules(plans):
    S, S1 = plans[0], plans[1]
    st = lambda S, a, b: [q[0] for q in tw.plan(S, a, b, {"T0": 3.0})["steps"]]
    assert st(S, "u1-p1", "u1-p1-m1") == ["park", "inj"]      # a lunar injection
    assert st(S, "u1-p1-m1", "u1-p1") == ["ret"]              # back down to the planet
    assert st(S, "u1-p1", "u1-p2") == ["xfer"]                # Hohmann-style, planet to planet
    assert st(S, "u1-p1-m1", "u1-p1-m2") == ["xfer"]          # siblings: one phasing arc
    assert st(S, "u1-p1", "u1-p6") == ["xfer", "fly", "xfer"]  # far rings: a swing-by between
    assert st(S, "u1-p3-m2-s1", "u1-p4-m1") == ["esc", "xfer", "xfer"]
    inter = st(S, "u1-p3-m1", "u2-p2-m2-s1")                  # to another system
    assert inter[0] == "esc" and "bez" in inter and inter[-3:] == ["xfer", "xfer", "xfer"]
    assert 1 <= inter.count("fly") <= 3
    assert st(S1, "u1-p1-m1", "u1-p1-m1-s1") == ["hop"]       # a satellite close by: one short leg
    # the planet to its moon: the injection is a half orbit, out from the parking orbit
    R = tw.plan(S, "u1-p3", "u1-p3-m2", {"T0": 9.0})
    assert abs(R["legs"][1]["phi"] - math.pi) < 1e-9 and R["legs"][1]["prof"] == "conic"


def test_the_plan_is_deterministic(plans):
    a = tw.plan(plans[0], "u1-p3-m2-s1", "u2-p2-m2-s2", {"T0": 12.5, "r0": 1, "view": [1400, 900]})
    b = tw.plan(plans[0], "u1-p3-m2-s1", "u2-p2-m2-s2", {"T0": 12.5, "r0": 1, "view": [1400, 900]})
    assert a["D"] == b["D"] and a["steps"] == b["steps"]
    assert [tw.at(tw.bodies(plans[0]), a, t / 10) for t in range(70)] == [tw.at(tw.bodies(plans[0]), b, t / 10) for t in range(70)]
    assert a["keys"] == b["keys"]


def test_a_replan_carries_on_from_the_craft_as_it_moves(plans):
    S = plans[0]
    W = tw.bodies(S)
    R = tw.plan(S, "u1-p1", "u1-p6", {"T0": 4.0, "r0": 0})
    t = R["D"] * 0.4
    p, v = tw.at(W, R, t), tw._vel(W, R, t, 1)
    R2 = tw.plan(S, "u1", "u1-p2-m1" if "u1-p2-m1" in W["B"] else "u1-p4-m1",
                 {"T0": tw.clock(R["c"], t), "r0": tw.clock_rate(R["c"], t), "start": [p[0], p[1], v[0], v[1]]})
    q = tw.at(W, R2, 0.0)
    assert math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-6           # from where it is
    v2 = tw._vel(W, R2, 0.0, 1)
    assert math.hypot(v2[0] - v[0], v2[1] - v[1]) < 0.02 * max(1.0, math.hypot(*v))   # as it is going
    end = tw.at(W, R2, R2["D"])
    tgt = tw.pos(W, R2["to"], tw.clock(R2["c"], R2["D"]))
    assert math.hypot(end[0] - tgt[0], end[1] - tgt[1]) < 1.0


def test_the_camera_starts_where_the_view_is_and_ends_on_the_target_at_full_size(plans):
    for S, W, A, B, o, R in list(_routes(plans, n=40, seed=3)):
        o = dict(o, cam=[500.0, 400.0, 1.0])
        c0, c1 = tw.cam(W, R, 0.0, o), tw.cam(W, R, R["D"], o)
        assert abs(c0[0] - 500) < 1e-9 and abs(c0[1] - 400) < 1e-9 and abs(c0[2] - 1) < 1e-9
        end = tw.pos(W, B, tw.clock(R["c"], R["D"]))
        assert abs(c1[0] - end[0]) < 1e-6 and abs(c1[1] - end[1]) < 1e-6 and c1[2] == 1.0
        scales = [tw.cam(W, R, R["D"] * k / 30, o)[2] for k in range(31)]
        assert all(FLY["CAM_MIN"] - 1e-9 <= s <= 1.0 for s in scales)
    # a long flight zooms out on the way
    R = tw.plan(plans[0], "u1-p3-m1", "u2-p2-m2", {"T0": 3.0, "view": [1500, 950]})
    W = tw.bodies(plans[0])
    assert min(tw.cam(W, R, R["D"] * k / 30, {"cam": [0, 0, 1]})[2] for k in range(31)) < 0.6


# ── the planner in the page = its twin ──────────────────────────────────────

@needs_node
def test_the_page_planner_is_the_twin(plans, tmp_path):
    rng = random.Random(3)
    cases = []
    for k in range(60):
        S = plans[k % len(plans)]
        ids = sorted(i for i, b in tw.bodies(S)["B"].items() if b["role"] != "core")
        A, B = rng.sample(ids, 2)
        o = {"T0": rng.uniform(0, 100), "r0": rng.choice([0, 1, .4]), "view": [1500, 950], "cam": [500, 500, 1]}
        if k % 5 == 0:
            o["start"] = [900, 900, 120, -40]
        if k % 7 == 3:
            o["still"] = True
        cases.append([k % len(plans), A, B, o])
    js = ("var window={};\n" + FLY_PLAN_JS + "\nvar P=" + json.dumps(plans) + ", cases=" + json.dumps(cases) + ";\n"
          "var F=window._altoFly, out=cases.map(function(c){ var R=F.plan(P[c[0]], c[1], c[2], c[3]), sm=[];"
          " for(var i=0;i<=24;i++){ var t=R.D*i/24; sm.push(F.at(R, t).concat(F.cam(R, t, c[3]), [F.clock(R, t)])); }"
          " return {D:R.D, steps:R.steps, sm:sm}; });\nconsole.log(JSON.stringify(out));")
    f = tmp_path / "par.js"
    f.write_text(js, encoding="utf-8")
    out = json.loads(subprocess.check_output([NODE, str(f)], timeout=120))
    for (pi, A, B, o), j in zip(cases, out):
        S = plans[pi]
        W = tw.bodies(S)
        R = tw.plan(S, A, B, o)
        assert [list(q) for q in R["steps"]] == j["steps"], (A, B)
        assert abs(R["D"] - j["D"]) < 1e-9, (A, B)
        for i in range(25):
            t = R["D"] * i / 24
            mine = list(tw.at(W, R, t)) + tw.cam(W, R, t, o) + [tw.clock(R["c"], t)]
            assert max(abs(a - b) for a, b in zip(mine, j["sm"][i])) < 1e-6, (A, B, i)


# ── what the pages carry ─────────────────────────────────────────────────────

def _page(units=SHAPES[0], style="orbit"):
    html, _ = build_timeline(*load_brief(copy.deepcopy(solar_doc(units, style, ()))))
    return html


def test_every_hub_and_spoke_page_carries_the_flight_and_other_pages_do_not():
    for style in ("orbit", "spoke"):
        html = _page(style=style)
        assert html.count("window._altoFly=") == 1 and "#solar-fly-svg{" in html, style
        assert html.index("window._altoSolarMount=function") < html.index("window._altoFly=")
    d = solar_doc(SHAPES[0], "spoke", ())
    d["brief"]["layout"] = "tree"
    tree, _ = build_timeline(*load_brief(d))
    assert "window._altoFly=" not in tree and "solar-fly-svg" not in tree


def test_the_flight_is_small_and_draws_without_masks_or_filters():
    size = len(gzip.compress((FLY_JS + FLY_CSS).encode("utf-8"), 9))
    assert size < 14000, size      # (+ the ships' orbit arrivals, a flight at most 5 s and Enter to land: ~0.4 KB, 2026-10-22; 12.6 KB gz at the round-2 merge; the three together stay under 50 KB: test_solar_integration)
    for s in ("<mask", "'mask'", "filter", "backdrop"):
        assert s not in FLY_JS and s not in FLY_CSS, s
    assert re.search(r"pointer-events:none", FLY_CSS)
    # never a transform on a node: the craft moves by its own SVG transform attribute
    assert ".style.transform" not in FLY_JS


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


def _comet_page():
    """A Star chart with a comet planet, a comet moon and a black hole (look flags)."""
    d = solar_doc(SHAPES[0], "orbit", ())
    d["brief"]["flags"] = [{"id": "exception", "name": "Exception"}, {"id": "overruled", "name": "Overruled"}]
    for n in d["nodes"]:
        if n["id"] in ("u1-p2", "u1-p3-m1"):
            n["flags"] = ["exception"]
        if n["id"] == "u1-p4":
            n["flags"] = ["overruled"]
    html, _ = build_timeline(*load_brief(d))
    return html


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = tmp_path_factory.mktemp("fly")
    out = {}
    for name, html in (("orbit", _page(style="orbit")), ("spoke", _page(style="spoke")), ("comet", _comet_page())):
        f = d / f"{name}.html"
        f.write_text(html, encoding="utf-8")
        out[name] = f
    return out


def _open(browser, f, reduced=False, look=None):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950}, reduced_motion="reduce" if reduced else "no-preference")
    if look:                                   # a stand-in for the look toggle (solar_draw.py's window._altoSolarLook)
        ctx.add_init_script("""(function(){ var v='%s', fns=[]; window._altoSolarLook={get:function(){ return v; },
          set:function(x){ v=x; fns.forEach(function(f){ f(v); }); }, onChange:function(f){ fns.push(f); }}; })();""" % look)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f.as_uri())
    pg.wait_for_timeout(2400)
    pg.mouse.move(2, 940)
    return pg, errs


def _rest_on(pg, i):
    """The view centred on body i at full size, then i enlarged (no flight:
    nothing was enlarged and it is the body in the middle)."""
    pg.evaluate("""(i)=>{ var g=window._altoSolarGeo().bodies[i], P=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0;
                         window._altoSolarCam.set(g.x, g.y-P, 1); }""", i)
    pg.wait_for_timeout(300)
    pg.evaluate("(i)=>window.enterFocus(i)", i)
    pg.wait_for_timeout(1400)
    assert pg.evaluate("()=>window._focusedNodeId") == i


FLIGHT = "()=>window._altoSolarFlight()"
WHERE = """(i)=>{ var n=document.getElementById('node-'+i), P=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0, g=window._altoSolarCam.get();
  return {x:parseFloat(n.style.left), y:parseFloat(n.style.top)-P, focused:n.classList.contains('focused'), id:window._focusedNodeId, cam:g,
          svg:!!document.getElementById('solar-fly-svg'), T:window._altoSolarRate().T}; }"""


def test_a_flight_runs_lands_on_the_body_and_enlarges_it(browser, pages):
    pg, errs = _open(browser, pages["orbit"])
    _rest_on(pg, "u1-p3")
    pg.evaluate("()=>window.enterFocus('u1-p3-m2')")
    f = pg.evaluate(FLIGHT)
    assert f and f["to"] == "u1-p3-m2" and f["steps"] == ["park", "inj"], f
    assert pg.evaluate("()=>window._focusedNodeId") is None               # the card it left went home
    pg.wait_for_timeout(int(f["D"] * 500))
    mid = pg.evaluate(FLIGHT)
    assert mid and 0.3 * f["D"] < mid["tau"] < 0.8 * f["D"]
    T1 = pg.evaluate(WHERE, "u1-p3-m2")["T"]
    pg.wait_for_timeout(250)
    assert pg.evaluate(WHERE, "u1-p3-m2")["T"] > T1                      # the orbits move on the way
    pg.wait_for_timeout(int(f["D"] * 500) + 900)
    w = pg.evaluate(WHERE, "u1-p3-m2")
    assert pg.evaluate(FLIGHT) is None and w["id"] == "u1-p3-m2" and w["focused"], w
    last = pg.evaluate("()=>window._altoSolarFlight(true)")
    assert last["how"] == "landed" and last["to"] == "u1-p3-m2"
    # it landed where the moon is, and the view is on it
    assert abs(w["cam"]["cx"] - w["x"]) < 60 and abs(w["cam"]["cy"] - w["y"]) < 60, w
    pg.wait_for_timeout(800)
    assert abs(pg.evaluate(WHERE, "u1-p3-m2")["T"] - w["T"]) < 1e-9         # and the orbits stand still
    assert pg.evaluate("()=>document.getElementById('solar-fly-svg').classList.contains('fly-out')")
    assert not errs, errs
    pg.context.close()


def test_a_new_target_on_the_way_replans_and_esc_stops(browser, pages):
    pg, errs = _open(browser, pages["orbit"])
    _rest_on(pg, "u1-p2")
    pg.evaluate("()=>window.enterFocus('u1-p6')")
    f = pg.evaluate(FLIGHT)
    pg.wait_for_timeout(int(f["D"] * 350))
    a = pg.evaluate(FLIGHT)["at"]
    pg.evaluate("()=>window.enterFocus('u1-p1-m1')")
    g = pg.evaluate(FLIGHT)
    assert g["to"] == "u1-p1-m1" and g["tau"] < 0.2
    assert math.hypot(g["at"][0] - a[0], g["at"][1] - a[1]) < 120             # from where the craft was
    pg.wait_for_timeout(int(g["D"] * 1000) + 900)
    assert pg.evaluate("()=>window._focusedNodeId") == "u1-p1-m1"
    # Esc on the way: stopped, nothing enlarged, the orbits run on, the view back at full size
    pg.evaluate("()=>window.enterFocus('u1-p4')")
    pg.wait_for_timeout(700)
    assert pg.evaluate(FLIGHT)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(900)
    w = pg.evaluate(WHERE, "u1-p4")
    assert pg.evaluate(FLIGHT) is None and w["id"] is None and w["cam"]["scale"] == 1
    assert pg.evaluate("()=>window._altoSolarFlight(true).how") == "esc"
    pg.wait_for_timeout(600)
    assert pg.evaluate(WHERE, "u1-p4")["T"] > w["T"]
    assert not errs, errs
    pg.context.close()


def test_arrows_wait_for_a_flight_and_then_walk_the_outline(browser, pages):
    """A click flies (here: enterFocus on a far body); the arrows walk the outline (the Tour, 2026-10-22): pressed on
    the way, they wait for the landing and then go on from where it landed."""
    pg, errs = _open(browser, pages["orbit"])
    _rest_on(pg, "u1-p3")
    far = pg.evaluate("() => { var G=window._altoSolarGeo().bodies, a=G['u1-p3']; return Object.keys(G).filter(function(i){ return G[i].si!==a.si && G[i].role==='planet'; })[0]; }")
    pg.evaluate("(i)=>window.enterFocus(i)", far)
    pg.wait_for_timeout(200)
    f = pg.evaluate(FLIGHT)
    assert f and f["to"] == far, f
    pg.keyboard.press("ArrowRight")
    assert pg.evaluate(FLIGHT)["to"] == far                         # the press waits; the flight flies on
    pg.wait_for_function("(i)=>window._focusedNodeId===i && !window._altoSolarFlight()", arg=far, timeout=12000)
    T = pg.evaluate("()=>window._altoSolarLock.order()")
    pg.wait_for_function("(i)=>window._focusedNodeId===i && !window._altoSolarLock.riding()", arg=T[T.index(far) + 1], timeout=8000)
    assert not errs, errs
    pg.context.close()


def test_no_flight_with_reduced_motion_on_the_hub_look_or_zoomed_out(browser, pages):
    # reduced motion: the existing instant enlarging
    pg, errs = _open(browser, pages["orbit"], reduced=True)
    _rest_on(pg, "u1-p3")
    pg.evaluate("()=>window.enterFocus('u1-p3-m2')")
    assert pg.evaluate(FLIGHT) is None and pg.evaluate("()=>window._focusedNodeId") == "u1-p3-m2"
    assert not pg.evaluate("()=>!!document.getElementById('solar-fly-svg')")
    pg.context.close()
    # the System look: nothing of the flight runs
    pg, errs2 = _open(browser, pages["spoke"])
    _rest_on(pg, "u1-p1")
    pg.evaluate("()=>window.enterFocus('u1-p2')")
    assert pg.evaluate(FLIGHT) is None and pg.evaluate("()=>window._focusedNodeId") == "u1-p2"
    assert not pg.evaluate("()=>!!document.getElementById('solar-fly-svg')")
    pg.context.close()
    # zoomed out (the whole chart): a click there enlarges, no flight
    pg, errs3 = _open(browser, pages["orbit"])
    pg.evaluate("()=>window._altoSolarCam.set(850, 1200, .4)")
    pg.wait_for_timeout(200)
    pg.evaluate("()=>window.enterFocus('u1-p2')")
    assert pg.evaluate(FLIGHT) is None
    pg.context.close()
    assert not errs and not errs2 and not errs3, (errs, errs2, errs3)


def test_switching_to_the_hub_look_stops_the_flight_and_clears_its_layer(browser, pages):
    """The look toggle (solar_draw.py, window._altoSolarLook): System on the way
    stops the flight and takes its layer away; System flies nothing; back in
    the Star chart look a change of body flies again."""
    pg, errs = _open(browser, pages["orbit"])
    assert pg.evaluate("()=>window._altoSolarLook.get()") == "stars"
    _rest_on(pg, "u1-p3")
    pg.evaluate("()=>window.enterFocus('u1-p1')")
    assert pg.evaluate(FLIGHT)
    pg.wait_for_timeout(600)
    pg.evaluate("()=>window._altoSolarLook.set('hub')")
    pg.wait_for_timeout(300)
    assert pg.evaluate(FLIGHT) is None and not pg.evaluate("()=>!!document.getElementById('solar-fly-svg')")
    assert pg.evaluate("()=>window._altoSolarFlight(true).how") == "stopped"
    pg.wait_for_timeout(900)
    pg.evaluate("()=>window.enterFocus('u1-p2')")
    pg.wait_for_timeout(700)
    pg.evaluate("()=>window.enterFocus('u1-p4')")
    assert pg.evaluate(FLIGHT) is None
    pg.evaluate("()=>window._altoSolarLook.set('stars')")
    pg.wait_for_timeout(1500)
    if pg.evaluate("()=>window._focusedNodeId") is None:
        _rest_on(pg, "u1-p4")
    pg.evaluate("()=>window.enterFocus('u1-p3')")
    assert pg.evaluate(FLIGHT)
    assert not errs, errs
    pg.context.close()


def test_the_planner_predicts_every_body_where_the_page_puts_it(browser, pages):
    """The planner's bodies (comets on their ellipses included) are where the
    page's own orbit loop draws them, at whatever the clock reads."""
    pg, errs = _open(browser, pages["comet"])
    pg.wait_for_timeout(1500)
    looks = pg.evaluate("()=>{ var o={}, N=window._ALTO_SOLAR.nodes; for(var i in N) if(N[i].look) o[i]=N[i].look; return o; }")
    assert looks.get("u1-p2") == "comet" and looks.get("u1-p3-m1") == "comet", looks
    for _ in range(3):
        d = pg.evaluate("""()=>{ var F=window._altoFly, W=F.bodies(window._ALTO_SOLAR), G=window._altoSolarGeo(), T=window._altoSolarRate().T,
            P=(typeof WORLD_PAD_TOP!=='undefined') ? WORLD_PAD_TOP : 0, worst=0, at='';
          Object.keys(G.bodies).forEach(function(i){ if(!W.B[i]) return; var p=F.pos(W, i, T), g=G.bodies[i], e=Math.hypot(p[0]-g.x, p[1]-(g.y-P));
            if(e>worst){ worst=e; at=i; } });
          return [worst, at]; }""")
        assert d[0] < 1.5, d                                    # device-px rounding of the page's left/top
        pg.wait_for_timeout(700)
    # a flight to the comet lands on it
    _rest_on(pg, "u1-p1")
    pg.evaluate("()=>window.enterFocus('u1-p2')")
    f = pg.evaluate(FLIGHT)
    pg.wait_for_timeout(int(f["D"] * 1000) + 900)
    assert pg.evaluate("()=>window._focusedNodeId") == "u1-p2"
    assert not errs, errs
    pg.context.close()


def test_with_the_orbit_switched_off_it_flies_among_still_bodies(browser, pages):
    pg, errs = _open(browser, pages["orbit"])
    _rest_on(pg, "u1-p3")
    pg.evaluate("()=>window._altoSolarMotion.set(false)")
    T0 = pg.evaluate("()=>window._altoSolarRate().T")
    pg.evaluate("()=>window.enterFocus('u1-p1')")
    f = pg.evaluate(FLIGHT)
    assert f
    pg.wait_for_timeout(int(f["D"] * 500))
    assert pg.evaluate("()=>window._altoSolarRate().T") == T0
    pg.wait_for_timeout(int(f["D"] * 500) + 900)
    assert pg.evaluate("()=>window._focusedNodeId") == "u1-p1" and pg.evaluate("()=>window._altoSolarRate().T") == T0
    # switched back on mid-flight: re-planned on the moving clock, and still lands
    pg.evaluate("()=>window.enterFocus('u1-p3')")
    pg.wait_for_timeout(500)
    pg.evaluate("()=>window._altoSolarMotion.set(true)")
    g = pg.evaluate(FLIGHT)
    assert g and g["to"] == "u1-p3"
    pg.wait_for_timeout(int(g["D"] * 1000) + 900)
    assert pg.evaluate("()=>window._focusedNodeId") == "u1-p3"
    assert not errs, errs
    pg.context.close()


def test_a_flight_to_another_system_swings_by_and_its_frames_are_cheap(browser, pages):
    """The long route: escape, gravity assists, cruise, capture. Frame times
    while flying (rAF intervals) and this layer's own work per frame."""
    pg, errs = _open(browser, pages["orbit"])
    _rest_on(pg, "u1-p3-m1")
    pg.evaluate("""()=>{ window.__fr=[]; var l=null; (function f(t){ if(l!==null) window.__fr.push(t-l); l=t;
                       if(window.__fr.length<2000) requestAnimationFrame(f); })(performance.now()); }""")
    pg.evaluate("()=>window.enterFocus('u2-p2-m2')")
    f = pg.evaluate(FLIGHT)
    assert f["steps"][0] == "esc" and "bez" in f["steps"] and "fly" in f["steps"], f["steps"]
    pg.wait_for_timeout(int(f["D"] * 450))
    assert pg.evaluate("()=>window._altoSolarCam.get().scale") < 0.9          # zoomed out for the crossing
    pg.wait_for_timeout(int(f["D"] * 550) + 900)
    assert pg.evaluate("()=>window._focusedNodeId") == "u2-p2-m2"
    last = pg.evaluate("()=>window._altoSolarFlight(true)")
    ms = sorted(last["ms"])
    fr = sorted(pg.evaluate("()=>window.__fr")[:int(f["D"] * 60)])
    p = lambda a, q: a[min(len(a) - 1, int(len(a) * q))]
    print(f"\n[{browser._alto_name}] flight frames n={len(fr)} p50={p(fr, .5):.1f}ms p95={p(fr, .95):.1f}ms max={fr[-1]:.1f}ms;"
          f" layer work p50={p(ms, .5):.2f}ms p95={p(ms, .95):.2f}ms max={ms[-1]:.2f}ms")
    assert p(ms, .95) < 8 and ms[-1] < 25, ms[-5:]                          # this layer never costs a 25ms frame
    assert not errs, errs
    pg.context.close()
