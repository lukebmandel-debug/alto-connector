"""City engine v2, the lattice and the page (alto/build/city_lattice.py; design 2.5, 4.4): a hand-made two-domain city —
an upright domain A above an angled seam ("Baltimore Ave", -19 degrees) and a domain C turned -38 degrees below it, the
fold of A across the seam, so every numbered street of A kinks on the seam into a column of C — built into a real page:
polygon tiles (M.tq), loose tilted lines (M.te), heavy lattice lines (st.L), rotated lots and a rotated landmark (a).
Nothing here touches the network, Firebase or any ALTO_* setting."""
import copy
import functools
import http.server
import json
import math
import re
import socketserver
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import city_lattice as cl, palace  # noqa: E402
from alto.build.builder import build_timeline, load_brief  # noqa: E402
from alto.build.city_types import Domain  # noqa: E402
from alto.build.palace_towers import tower_lots  # noqa: E402

CW, CH = cl.CW, cl.CH
W, H = 12 * CW, 12 * CH                     # 2880 x 2040
PHI, TILT = -19.0, -38.0                    # the seam's page angle, C's page angle (= 2 PHI: the fold)
P0 = (1200.0, 1100.0)                       # a point of the seam
BBOX = [39.95, -75.20, 39.95 + H / 110574, -75.20 + W / (math.cos(math.radians(39.95 + H / 221148)) * 111320)]


def ys(x):
    return P0[1] + (x - P0[0]) * math.tan(math.radians(PHI))


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')} St"


A_ROWS = ["Market St", "Chestnut St", "Walnut St", "Locust St", "Spruce St", "Pine St", "Cedar Ave", "Catharine St",
          "Christian St", "Washington Ave", "Federal St", "Reed St", "Tasker St"]
C_ROWS = ["Florence Ave", "Warrington Ave", "Springfield Ave", "Chester Ave", "Kingsessing Ave", "Greenway Ave",
          "Woodland Ave", "Paschall Ave", "Grays Ave", "Elmwood Ave", "Buist Ave", "Dicks Ave", "Eastwick Ave"]
MAJORS = {"52nd St", "Spruce St", "Woodland Ave", "Baltimore Ave"}


def lattices():
    """The two domains: A (root, upright) and C (the fold of A across the seam, moved half a block along its columns)."""
    ring_a = [(0, 0), (W, 0), (W, ys(W)), (0, ys(0))]
    ring_c = [(0, ys(0)), (W, ys(W)), (W, H), (0, H)]
    A = cl.Lattice(Domain(0, "grid", 0.0, [], a=0.0, o=(0.0, 0.0), clip=ring_a),
                   [i * CW for i in range(13)], [j * CH for j in range(13)])
    r = math.radians(TILT)
    c, s = math.cos(r), math.sin(r)
    rot = lambda x, y: (x * c - y * s, x * s + y * c)                             # noqa: E731
    q = rot(P0[0], -P0[1])
    h = rot(0, CH / 2)
    o = (P0[0] - q[0] + h[0], P0[1] - q[1] + h[1])
    probe = cl.Lattice(Domain(1, "grid", 0.0, [], a=TILT, o=o, clip=ring_c), [0, CW], [0, CH])
    loc = [probe.local(*p) for p in ring_c]
    i0, i1 = math.floor(min(p[0] for p in loc) / CW), math.ceil(max(p[0] for p in loc) / CW)
    j0, j1 = math.floor(min(p[1] for p in loc) / CH), math.ceil(max(p[1] for p in loc) / CH)
    xg, yg = [i * CW for i in range(i0, i1 + 1)], [j * CH for j in range(j0, j1 + 1)]
    lm = probe.local(2050, 1500)                                                  # the landmark's cell
    li, lj = int((lm[0] - xg[0]) // CW), int((lm[1] - yg[0]) // CH)
    C = cl.Lattice(Domain(1, "grid", 0.0, [], a=TILT, o=o, clip=ring_c), xg, yg, lm_cells=[(li, lj)])
    return A, C, (li, lj)


def build():
    """The map and blocks of the fixture, exactly as the integrator would emit them."""
    A, C, (li, lj) = lattices()
    na = {"v": [ordinal(63 - i) for i in range(13)], "h": A_ROWS}
    nc = {"v": [ordinal(63 - round(x / CW)) if 0 <= round(x / CW) <= 12 else "" for x in C.xg],
          "h": [C_ROWS[k] if 0 <= k < len(C_ROWS) else "" for k in range(-2, len(C.yg) - 2)]}
    ta = {("v", i) for i in range(13)}
    tc = {("v", k) for k, x in enumerate(C.xg) if 0 <= round(x / CW) <= 12}
    seams = [(0, ys(0), W, ys(W))]
    ea = cl.emit(A, na, MAJORS, ta, seams=seams)
    ec = cl.emit(C, nc, MAJORS, tc, seams=seams)
    seam = {"n": "Baltimore Ave", "k": 0, "L": 1, "p": [0, round(ys(0), 1), W, round(ys(W), 1)]}
    streets = cl.join_hinges(ea["streets"] + ec["streets"]) + [seam]
    lm = cl.landmark(C, li, lj, li + 1, lj + 1, "Bartram Hall")
    chester = next(s for s in streets if s["n"] == "Chester Ave")
    p = chester["p"]
    n = len(p) // 2
    stops = [{"n": f"Chester Ave stop {k + 1}", "x": p[2 * i], "y": p[2 * i + 1], "l": ["T1"]}
             for k, i in enumerate((1, n // 2, n - 2))]
    transit = {"lines": [{"id": "T1", "n": "Route 13", "c": "#3c9a47", "k": "tram", "p": [p], "s": [0, 1, 2]}], "stops": stops}
    m = {"v": 1, "place": "Tiltville", "bbox": list(BBOX), "scale": 1.0, "W": W, "H": H,
         "attribution": "© OpenStreetMap contributors", "water": [], "rivers": [], "river": [], "parks": [],
         "trails": [], "rails": [], "stations": [], "streets": streets, "tiles": ea["tiles"], "edges": ea["edges"],
         "tq": ea["tq"] + ec["tq"], "te": ea["te"] + ec["te"], "landmarks": [lm], "majors": sorted(MAJORS),
         "cols": [], "rows": [], "transit": transit}
    blocks = sorted(ea["blocks"] + ec["blocks"], key=lambda b: (b["y"], b["x"]))
    for k, b in enumerate(blocks):
        b["id"] = k
    return m, blocks, (A, C, ea, ec)


def lonlat(x, y):
    s, w, n, e = BBOX
    lat0 = math.radians((s + n) / 2)
    return w + x / (math.cos(lat0) * 111320), n - y / 110574


def bounds(x0, y0, x1, y1):
    w, n = lonlat(x0, y0)
    e, s = lonlat(x1, y1)
    return [s, w, n, e]


def bundle():
    m, blocks, _ = build()
    acts = [{"label": "ONE", "short": "One", "color": "#4a9eff"}, {"label": "TWO", "short": "Two", "color": "#22c55e"},
            {"label": "THREE", "short": "Three", "color": "#f59e0b"}]
    dist = [{"unit": 0, "name": "Cedar Park", "bounds": bounds(80, 80, 1400, 700)},
            {"unit": 1, "name": "Spruce Hill", "bounds": bounds(1500, 80, 2800, 450)},
            {"unit": 2, "name": "Kingsessing", "bounds": bounds(700, 1350, 2800, 1980)}]
    pal = {"place": "Tiltville", "bbox": list(BBOX), "districts": dist, "data_z": palace.pack({"map": m, "blocks": blocks})}
    brief = {"title": "Tilt Palace", "subject": "A made-up city with a turned district", "timeline_id": "tilt-palace",
             "mode": "palace", "node_noun": "Room", "period_noun": "Wing", "accent": "#5b8def", "acts": acts, "palace": pal}

    def nd(i, act, parent=None):
        d = {"id": i, "act": act, "tag": "Room", "title": i.upper(), "desc": f"About {i}."}
        if parent:
            d["parent"] = parent
        return d
    nodes = [nd("alpha", 0), nd("alpha-1", 0, "alpha"), nd("beta", 0), nd("gamma", 1), nd("gamma-1", 1, "gamma"),
             nd("delta", 2), nd("eps", 2), nd("zeta", 2), nd("eta", 2), nd("theta", 2)]
    return {"brief": brief, "nodes": nodes, "connections": []}


def page_html():
    b, nodes, conns = load_brief(copy.deepcopy(bundle()))
    return build_timeline(b, nodes, conns)[0]


# ── the lattice ─────────────────────────────────────────────────────────────
def test_page_and_local_are_inverse_and_turn_like_svg_rotate():
    A, C, _ = lattices()
    for p in ((0, 0), (517.3, -88.1), (2400, 1900)):
        q = C.page(*C.local(*p))
        assert math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-9
    # local +x runs along the page angle (screen convention: y down, positive = clockwise, as SVG rotate)
    a, b = C.page(0, 0), C.page(100, 0)
    assert abs(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) - TILT) < 1e-9
    assert A.page(10, 20) == (10.0, 20.0) and A.node(2, 3) == (480.0, 510.0)


def test_cells_are_clipped_to_the_domain():
    A, C, _ = lattices()
    full = A.cell_poly(0, 0)
    assert abs(abs(cl.area(full)) - CW * CH) < 1e-6
    # a cell the seam cuts: what is left lies on A's side of the seam, and both domains' parts add up to the cell
    i, j = 5, 6
    pa = A.cell_poly(i, j)
    rc = [(0, ys(0)), (W, ys(W)), (W, H), (0, H)]
    pc = cl.clip_convex(rc, A.cell_rect(i, j))
    assert 0 < abs(cl.area(pa)) < CW * CH
    assert abs(abs(cl.area(pa)) + abs(cl.area(pc)) - CW * CH) < 1e-6
    assert all(y <= ys(x) + 1e-6 for x, y in pa)


def test_emit_full_cut_and_sliver_cells():
    _, _, (A, C, ea, ec) = build()
    for e in (ea, ec):
        kinds = list(e["cells"].values())
        assert kinds.count("full") > 30 and kinds.count("cut") > 5
        assert "sliver" not in kinds                       # every sliver was merged, kept as a plaza or dropped
    # the root's full cells are upright tiles; a tilted domain has no upright tiles at all
    assert ea["tiles"] and all(len(t) == 4 for t in ea["tiles"])
    assert not ec["tiles"] and not ec["edges"]
    assert all(len(q) >= 6 and len(q) % 2 == 0 for q in ea["tq"] + ec["tq"])
    assert ec["cells"][lattices()[2]] == "lm"


def test_lots_stand_square_to_their_block_inside_it_and_clear_of_the_seam():
    m, blocks, (A, C, ea, ec) = build()
    for e, lat in ((ea, A), (ec, C)):
        for b in e["blocks"]:
            for cx, cy, w, h, deg in b["lots"]:
                assert deg == round(lat.a, 1)
                for sx in (-1, 1):
                    for sy in (-1, 1):
                        x, y = cl.rot_point(cx + sx * w / 2, cy + sy * h / 2, cx, cy, deg)
                        assert lat.inside(x, y), (b, (x, y))
    # numbered keys: ids follow the (y, x) order of the page centroids
    assert [b["id"] for b in blocks] == list(range(len(blocks)))
    assert sum(len(b["lots"]) for b in ec["blocks"]) > 60


def test_rows_end_on_the_seam_with_a_lead_along_it_and_columns_hinge():
    m, _, (A, C, ea, ec) = build()
    st = {s["n"]: s for s in m["streets"] if s["n"]}
    ux, uy = math.cos(math.radians(PHI)), math.sin(math.radians(PHI))

    def on_seam(x, y):
        return abs((y - P0[1]) * ux - (x - P0[0]) * uy) < 0.6
    # an A row that meets the seam: its last leg runs along the seam (a T-join), toward the smaller turn
    p = st["Spruce St"]["p"]
    assert on_seam(p[-4], p[-3]) and on_seam(p[-2], p[-1])
    lead = math.hypot(p[-2] - p[-4], p[-1] - p[-3])
    assert 20 <= lead <= cl.LEAD + .1
    # a numbered street: ONE polyline from the top of A, kinked on the seam, on down C's column
    p = st["55th St"]["p"]
    pts = list(zip(p[0::2], p[1::2]))
    assert pts[0][1] == 0 and any(on_seam(*q) for q in pts[1:-1])
    k = next(i for i, q in enumerate(pts) if on_seam(*q) and 0 < i < len(pts) - 1)
    d0 = math.degrees(math.atan2(pts[k][1] - pts[0][1], pts[k][0] - pts[0][0]))
    d1 = math.degrees(math.atan2(pts[-1][1] - pts[k][1], pts[-1][0] - pts[k][0]))
    assert abs(d0 - 90) < .05 and abs(d1 - (90 + TILT)) < .05            # A's column, then C's (2 PHI - 90 = 52)
    # majors carry L, minors do not; no street but a hinge line crosses the seam (R5)
    assert st["52nd St"].get("L") == 1 and st["Woodland Ave"].get("L") == 1 and not st["Pine St"].get("L")
    for s in m["streets"]:
        q = list(zip(s["p"][0::2], s["p"][1::2]))
        sides = {(y - P0[1]) * ux - (x - P0[0]) * uy > 0.6 for x, y in q if not on_seam(x, y)}
        if len(sides) == 2:
            assert s["n"].endswith(" St") and s["n"][0].isdigit(), s["n"]


def test_a_turned_landmark_and_a_towers_chip_lot_turn_with_their_domain():
    m, blocks, _ = build()
    lm = m["landmarks"][0]
    assert lm["a"] == TILT
    b = lm["box"]
    assert abs((b[0] + b[2]) / 2 - lm["x"]) < .11 and abs(b[2] - b[0] - CW) < .2 and abs(b[3] - b[1] - CH) < .2
    at = {}
    out = tower_lots(m, blocks, at, {"hub": {"n": "Bartram Hall"}})
    lot = out[-1]["lots"][0]
    assert lot[4] == TILT and at["hub"] == f"{len(out) - 1}.0"
    up = dict(lm)
    up.pop("a")
    flat_ = tower_lots({"landmarks": [up]}, blocks, {}, {"hub": {"n": "Bartram Hall"}})[-1]["lots"][0]
    q = cl.rot_point(flat_[0], flat_[1], lm["x"], lm["y"], TILT)
    assert abs(q[0] - lot[0]) < .2 and abs(q[1] - lot[1]) < .2


# ── the page ────────────────────────────────────────────────────────────────
def test_the_page_carries_the_v2_keys_and_draws_them_optionally():
    html = page_html()
    d = json.loads(re.search(r"window\._ALTO_PALACE=(\{.*?\});\n", html, re.S).group(1))
    assert d["m"]["tq"] and d["m"]["te"] and any(s.get("L") for s in d["m"]["streets"])
    assert d["m"]["landmarks"][0]["a"] == TILT
    assert any(L[4] == TILT for ls in d["b"] for L in ls)
    for frag in ("(M.tq||[]).forEach", "(M.te||[]).forEach", "if(!okGrid || hasL) return;", "function lmLocal(l, p)",
                 "base=E('g',{'class':'lm-base', transform:'rotate('+(+l.a)+' '", "up=E('g',{'class':'lm-up'"):
        assert frag in html, frag


@pytest.fixture(scope="module")
def url(tmp_path_factory):
    root = tmp_path_factory.mktemp("ptilt")
    (root / "page.html").write_text(page_html(), encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    h.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/page.html"
    srv.shutdown()


FAKE = """(function(){ var store=null;
 var C={enabled:true, known:true, user:{uid:'u1'}, getEdits:function(){ return Promise.resolve(store); },
  putEdits:function(t,d){ store=JSON.parse(JSON.stringify(d)); return Promise.resolve(); }, watchEdits:function(){ return function(){}; }};
 Object.defineProperty(window,'AltoCloud',{get:function(){return C;}, set:function(){}, configurable:true}); })();"""


@pytest.fixture
def pg(url):
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        b = None
        for launch in (lambda: p.webkit.launch(), lambda: p.chromium.launch(), lambda: p.chromium.launch(channel="chrome")):
            try:
                b = launch()
                break
            except Exception:                                # noqa: BLE001
                continue
        if b is None:
            pytest.skip("no browser to drive")
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_init_script(FAKE)
        page = ctx.new_page()
        page.errs = []
        page.on("pageerror", lambda e: page.errs.append(str(e)))
        page.goto(url)
        page.wait_for_timeout(1500)
        yield page
        b.close()


GEO = """()=>{ var P=window._ALTO_PALACE, M=P.m, svg=document.getElementById('palace-svg');
  var lm=svg.querySelector('.pl-lmb[data-name="Bartram Hall"]');
  var t=0; svg.querySelectorAll('.pl-streets .pl-tube').forEach(function(p){ t+=(p.getAttribute('d').match(/Z/g)||[]).length; });
  return {tq:M.tq.length, tiles:M.tiles.length, closed:t, maj:svg.querySelectorAll('.pl-streets .pl-tube.t-maj').length,
          lmT:lm&&lm.querySelector('.lm-base')&&lm.querySelector('.lm-base').getAttribute('transform'), gT:lm&&lm.getAttribute('transform'),
          artUp:lm&&lm.querySelector('.lm-up > .lm-art')?1:0, dir:!!window._palDir,
          cardX:lm&&(function(r){ return r.left+r.width/2; })(lm.querySelector('.lm-card').getBoundingClientRect()),
          artX:lm&&(function(r){ return r.left+r.width/2; })(lm.querySelector('.lm-art').getBoundingClientRect()),
          cardW:lm&&lm.querySelector('.lm-card').getBoundingClientRect().width}; }"""


def test_the_page_draws_polygon_tiles_heavy_lines_and_a_turned_landmark(pg):
    g = pg.evaluate(GEO)
    assert g["closed"] == g["tq"] + g["tiles"], g          # every tile and polygon tile drawn, once
    assert g["maj"] >= 3
    assert g["lmT"] and g["lmT"].startswith(f"rotate({TILT:g} "), g     # the card turns with its blocks ...
    assert not g["gT"] and g["artUp"], g                                # ... the building stays upright, standing on it (once, not twice)
    assert abs(g["artX"] - g["cardX"]) < .25 * g["cardW"] + 4, g          # on the turned card's middle, not where the upright card was
    assert not pg.errs, pg.errs


def test_a_rotated_lot_is_hit_where_it_stands_and_not_beside_it(pg):
    """Edit mode's '+' ghost: a point inside the turned lot (outside its upright box) finds it; a point inside the upright box
    but outside the turned one does not; a click there makes a numbered building on that lot, its card turned with it."""
    pg.click("#alto-edit-pill .aep-manual")
    pg.wait_for_timeout(500)
    r = pg.evaluate("""()=>{ var P=window._ALTO_PALACE, t={}, best=null, bd=1e18; Object.keys(P.at).forEach(function(i){ if(!P.of[i]) t[P.at[i]]=1; });
      P.b.forEach(function(ls,i){ ls.forEach(function(L,k){ if(t[i+'.'+k]||L[4]===0) return; var d=Math.hypot(L[0]-1500,L[1]-1150); if(d<bd){ bd=d; best={key:i+'.'+k, L:L}; } }); });
      var svg=document.getElementById('palace-svg'), m=svg.getScreenCTM(), L=best.L, a=L[4]*Math.PI/180, c=Math.cos(a), s=Math.sin(a);
      function scr(x,y){ var q=svg.createSVGPoint(); q.x=x; q.y=y; q=q.matrixTransform(m); return [q.x,q.y]; }
      var u=L[2]/2-4, v=-(L[3]/2-4);
      return {key:best.key, L:L, inner:scr(L[0]+u*c-v*s, L[1]+u*s+v*c), outer:scr(L[0]+L[2]/2-4, L[1]+L[3]/2-4)}; }""")
    ghost = "()=>{ var g=document.querySelector('.pl-addg rect'); return g?g.getAttribute('transform'):null; }"
    L = r["L"]
    pg.mouse.move(*r["outer"])
    pg.wait_for_timeout(200)
    assert pg.evaluate(ghost) is None
    pg.mouse.move(*r["inner"])
    pg.wait_for_timeout(200)
    assert pg.evaluate(ghost) == f"rotate({L[4]:g} {L[0]:g} {L[1]:g})"
    pg.mouse.click(*r["inner"])
    pg.wait_for_timeout(300)
    pg.fill("#aed-form [data-f=title]", "Turned hall")
    pg.click("#aed-form [data-a=ok]")
    pg.wait_for_timeout(900)
    s = pg.evaluate("""()=>{ var P=window._ALTO_PALACE, id=Object.keys(P.num).filter(function(i){ return /^card-/.test(i); })[0]; if(!id) return null;
      var e=document.getElementById('node-'+id), svg=document.getElementById('palace-svg'), k=P.at[id].split('.'), L=P.b[+k[0]][+k[1]], q=svg.createSVGPoint();
      q.x=L[0]; q.y=L[1]; q=q.matrixTransform(svg.getScreenCTM()); var b=e.getBoundingClientRect();         /* the node itself stands on its lot; its chip (.node-card) rides the roof, about 32 px up */
      return {at:P.at[id], num:P.num[id], pr:e.style.getPropertyValue('--pr'), d:Math.hypot((b.left+b.right)/2-q.x,(b.top+b.bottom)/2-q.y)}; }""")
    assert s and s["at"] == r["key"] and s["num"] and s["pr"] == f"{L[4]:g}deg", s
    assert s["d"] < 1.5, s                                   # the turned card's node stands centred on its lot
    assert not pg.errs, pg.errs


def test_directions_route_across_the_seam(pg):
    r = pg.evaluate("""()=>{ var D=window._palDir, A=D.bldPlace('alpha'), B=D.bldPlace('delta'); var pl=D.plan(A,B);
      return {a:A&&[A.x,A.y], b:B&&[B.x,B.y], n:pl?pl.length:0, walk:pl?pl.filter(function(o){ return o.kind==='walk'; }).length:0,
              pts:pl?pl[pl.length-1].legs.reduce(function(s,l){ return s.concat(l.pts); },[]):[]}; }""")
    assert r["n"] >= 1 and r["walk"] == 1, r
    assert r["a"][1] < ys(r["a"][0]) and r["b"][1] > ys(r["b"][0])          # from A's side to C's side
    assert any(y < ys(x) - 50 for x, y in r["pts"]) and any(y > ys(x) + 50 for x, y in r["pts"])
