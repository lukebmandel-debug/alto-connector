"""Transit for the city engine v2 (design section 5): the any-angle street graph, octilinear grade-separated lines per
domain joined at seams, stops on drawn lines, the city-generic audit and the finished-picture check. The square path
(one domain, or no domains) must stay byte-identical to 1.9.78: it is proved on the small synthetic cases and on the
Philadelphia snap inputs of the 1.9.78 build (tests/fixtures/transit)."""
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import palace  # noqa: E402,F401  (import order: palace before palace_grid)
from alto.build.city_types import Domain  # noqa: E402
from alto.build.palace_grid import mapping_from  # noqa: E402
from alto.build import palace_transit_audit as AU  # noqa: E402
from alto.build import palace_transit_route as RT  # noqa: E402
from alto.build.palace_transit import snap  # noqa: E402
import transit_fixture as F  # noqa: E402


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def sha(o):
    return hashlib.sha256(canon(o).encode()).hexdigest()


class Id:
    def __call__(self, x, y):
        return (x, y)


XG, YG = [100, 340, 580, 820], [100, 270, 440]


def _tr(wa, wb=None):
    lines = [{"id": "a", "n": "A", "c": "#0097d6", "k": "metro", "w": wa, "s": [0, 1]}]
    if wb:
        lines.append({"id": "b", "n": "B", "c": "#6ea516", "k": "metro", "w": wb, "s": [0]})
    return {"lines": lines, "stops": [{"n": "S1", "x": 170, "y": 280, "l": ["a", "b"] if wb else ["a"]},
                                      {"n": "S2", "x": 600, "y": 260, "l": ["a"]}, {"n": "Far", "x": 5000, "y": 5000, "l": ["a"]}]}


def _grid():
    es = [[XG[i], y, XG[i + 1], y] for y in YG for i in range(len(XG) - 1)]
    return es + [[x, YG[j], x, YG[j + 1]] for x in XG for j in range(len(YG) - 1)]


def _trol(stops, ways):
    return {"lines": [{"id": "trl", "n": "Trolleys", "c": "#6ea516", "k": "tram", "w": ways, "s": list(range(len(stops))),
                       "b": [list(range(len(stops)))]}],
            "stops": [{"n": "%s & X" % n, "x": x, "y": y, "l": ["trl"]} for n, x, y in stops]}


def _cases():
    es = _grid()
    yield "snap1", (_tr([[110, 262, 360, 280, 570, 275]]), XG, YG, {})
    yield "lanes", (_tr([[100, 270, 580, 270, 580, 440]], [[100, 270, 580, 270]]), XG, YG, {})
    yield "trolley", (_trol([("A", 110, 262), ("B", 570, 275), ("C", 600, 440), ("Void", 5000, 5000)],
                            [[110, 262, 360, 280, 570, 275, 600, 440]]), XG, YG, {"streets": [], "edges_": es})
    diag = {"n": "Diag", "k": 0, "d": 1, "j": [0, 0], "p": [100, 100, 580, 440]}
    yield "diag", (_trol([("A", 100, 100), ("B", 340, 270), ("C", 580, 440)], [[100, 100, 340, 270, 580, 440]]), XG, YG,
                   {"streets": [diag], "edges_": es})
    xg, yg = [100, 340, 580, 820, 1060], [100, 270, 440]
    tr = {"lines": [{"id": "a", "n": "A", "c": "#0097d6", "k": "metro", "w": [[100, 270, 1060, 270],
                                                                          [340, 270, 340, 440, 820, 440, 820, 270]],
                     "s": [0, 1, 2, 3], "b": [[0, 1], [2, 3]]}],
          "stops": [{"n": "S%d" % i, "x": x, "y": 270, "l": ["a"]} for i, x in enumerate((100, 340, 820, 1060))]}
    yield "branches", (tr, xg, yg, {})


# the legacy (1.9.78) outputs, taken before the v2 change
LEGACY = {"snap1": "1318f0f25453a4c8", "lanes": "34eddad18fd6e8a8", "trolley": "219542276c9269e6",
          "diag": "d825edbfff9bdbc4", "branches": "463bd477212ab7c4"}


def _one(xg, yg):
    d = Domain(id=0, kind="grid", theta=0.0, poly=[(-1e6, -1e6), (1e6, -1e6), (1e6, 1e6), (-1e6, 1e6)], mapping=Id())
    return [(d, F.Lat(d, xg, yg))]


def test_the_square_path_is_byte_identical_on_the_synthetic_cases():
    for name, (tr, xg, yg, kw) in _cases():
        out = snap(copy.deepcopy(tr), Id(), xg, yg, 1160, 540, **kw)
        assert sha(out)[:16] == LEGACY[name], name
        one = snap(copy.deepcopy(tr), None, None, None, 1160, 540, doms=_one(xg, yg), **kw)      # one square domain
        assert canon(one) == canon(out), name


def test_the_square_path_is_byte_identical_on_philadelphia():
    A = F.philly_args()
    mp = mapping_from(A["grid"])
    out = snap(A["tr"], mp, A["xg"], A["yg"], A["W"], A["H"], streets=A["streets"], edges_=[tuple(e) for e in A["edges"]])
    assert sha(out) == A["sha"]
    d = Domain(id=0, kind="grid", theta=0.0, poly=[(-1e6, -1e6), (1e6, -1e6), (1e6, 1e6), (-1e6, 1e6)], mapping=mp)
    one = snap(F.philly_args()["tr"], None, None, None, A["W"], A["H"], streets=A["streets"],
               edges_=[tuple(e) for e in A["edges"]], doms=[(d, F.Lat(d, A["xg"], A["yg"]))])
    assert sha(one) == A["sha"]


# ── the any-angle street graph ─────────────────────────────────────
def test_the_street_graph_cuts_streets_at_any_angle():
    a = (0, 0, 1000, 1000 * math.tan(math.radians(38)))              # a 38-degree street
    b = (0, 600, 1000, 600)                                           # an upright one it crosses
    c = (500, 600, 500, 900)                                          # a T onto b
    adj = RT.street_graph([a, b, c])
    x = 600 / math.tan(math.radians(38))
    hit = RT._k(x, 600)
    assert hit in adj and len(adj[hit]) == 4                          # a real crossing: four ways out
    assert len(adj[(500.0, 600.0)]) == 3                              # the T
    assert RT.street_graph([[0, 0, 100, 0]], []) == RT.street_graph([[0, 0, 100, 0]])     # both forms agree


def test_the_generic_graph_holds_the_square_graph():
    es = _grid()
    old, new = RT.street_graph(es, []), RT.street_graph(es)
    assert set(old) == set(new) and all(set(old[u]) == set(new[u]) for u in old)


# ── a two-domain synthetic city ────────────────────────────────────
def _two(deg=38.0):
    """Root: x < 2400 square lattice; domain 1: x in [2400, 6000] turned by deg (lattice through (4200, 1800))."""
    xg0, yg0 = [k * 240.0 for k in range(11)], [k * 170.0 for k in range(22)]
    root = Domain(id=0, kind="grid", theta=0.0, poly=[(-1e5, -1e5), (2400, -1e5), (2400, 1e5), (-1e5, 1e5)], mapping=Id())
    lat1 = F.Lat(None, [k * 240.0 for k in range(-14, 15)], [k * 170.0 for k in range(-20, 21)], a=deg, o=(4200.0, 1800.0))
    clip = [(2400, 0), (6000, 0), (6000, 3570), (2400, 3570)]
    d1 = Domain(id=1, kind="grid", theta=math.radians(deg), poly=[(2400, -1e5), (1e5, -1e5), (1e5, 1e5), (2400, 1e5)],
                a=deg, clip=clip, mapping=lambda x, y: lat1.local(x, y))
    lat1.dom = d1
    return [(root, F.Lat(root, xg0, yg0)), (d1, lat1)], lat1, clip


def test_rail_runs_octilinear_in_each_domain_and_crosses_the_seam():
    doms, lat1, clip = _two()
    p0, p1 = lat1.page(-1680, 0), lat1.page(1200, 0)                 # a track along one of domain 1's own lines
    track = [600, 1530, 2400, 1530] + [v for p in (p0, lat1.page(0, 0), p1) for v in p]
    tr = {"lines": [{"id": "rr", "n": "Rail", "c": "#4c748c", "k": "rail", "w": [track], "s": [0, 1, 2], "b": [[0, 1, 2]]}],
          "stops": [{"n": "West", "x": 600, "y": 1530, "l": ["rr"]}, {"n": "Mid", "x": 4200, "y": 1800, "l": ["rr"]},
                    {"n": "East", "x": p1[0], "y": p1[1], "l": ["rr"]}]}
    g = snap(tr, None, None, None, 6000, 3600, doms=doms, segs=[])
    (ln,) = g["lines"]
    assert [g["stops"][i]["n"] for i in ln["s"]] == ["West", "Mid", "East"]
    ok0 = {0.0, 90.0, 35.3, 144.7}
    ok1 = {round((38 + v) % 180, 1) for v in (0, 90, 35.26, -35.26)}
    seam = 0
    for f in ln["p"]:
        pts = list(zip(f[0::2], f[1::2]))
        for a, b in zip(pts, pts[1:]):
            ang = round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180, 1)
            mx = (a[0] + b[0]) / 2
            if abs(a[0] - 2400) < 1 and abs(b[0] - 2400) < 1:
                seam += 1                                              # a run along the seam
                continue
            allowed = ok0 if mx < 2400 else ok1
            assert any(abs(ang - v) < 0.6 or abs(abs(ang - v) - 180) < 0.6 for v in allowed), (a, b, ang)
        bends = len(pts) - 2
        assert bends <= 4                                              # no stair-step: a few runs, not one per block
    m = {"tiles": [], "edges": [], "streets": [], "transit": g, "doms": [{"a": 0.0}, {"a": 38.0, "clip": clip}]}
    pic = AU.picture(m)
    assert pic["ok"], pic


# ── the tilted Philadelphia ────────────────────────────────────────
def _tilted():
    A, doms, segs, te, edges, streets, box = F.philly_two_domains(38.0, east=4500.0)
    g = snap(A["tr"], None, None, None, A["W"], A["H"], doms=doms, segs=segs, streets=streets, edges_=edges)
    b = box
    m = {"place": "Philadelphia", "tiles": [], "edges": edges, "te": te, "streets": streets, "transit": g,
         "doms": [{"a": 0.0}, {"a": 38.0, "clip": [b[0], b[1], b[2], b[1], b[2], b[3], b[0], b[3]]}]}
    return A, doms, segs, te, box, g, m


def test_on_a_tilted_philadelphia_trolleys_run_on_the_turned_streets_and_rail_stays_octilinear():
    A, doms, segs, te, box, g, m = _tilted()
    lines = {l["id"]: l for l in g["lines"]}
    # the trolleys reach far into the turned district, on its streets (1.9.78 kept 9 stops of each West Philly branch)
    trl = lines["trl"]
    assert sum(len(b) for b in trl["b"]) >= 90 and sorted(len(b) for b in trl["b"])[-4] >= 19
    inbox = [s for s in g["stops"] if "trl" in s["l"] and box[0] < s["x"] < box[2] and box[1] + 20 < s["y"] < box[3]]
    assert len(inbox) >= 25
    c = AU.street_cover(m)["trl"]
    assert c["stops"] == [] and all(r[0] < 200 for r in c["runs"])
    # every grade-separated run is on a drawn street or on its domain's axes/diagonals; every dot on its line
    pic = AU.picture(m)
    assert pic["stops"] == [] and pic["runs"] == []
    # the Regional Rail through University City is no longer a stair-step (1.9.78: 34 turns)
    assert sum(max(0, len(f) // 2 - 2) for f in lines["rr"]["p"]) <= 25


def test_the_tilted_routing_trolley_branches_inside_the_district_use_only_turned_streets():
    A, doms, segs, te, edges, streets, box = F.philly_two_domains(38.0)
    cm = RT.CityMap(doms)
    adj = RT.street_graph(segs)
    tr = A["tr"]
    ln = next(l for l in tr["lines"] if l["id"] == "trl")
    stops = [cm(s["x"], s["y"]) for s in tr["stops"]]
    real = RT.real_points(ln["w"], cm)

    def on_te(u, v):
        for f in te:
            L = math.hypot(f[2] - f[0], f[3] - f[1])
            if all(abs((f[2] - f[0]) * (p[1] - f[1]) - (f[3] - f[1]) * (p[0] - f[0])) / L < 0.5 for p in (u, v)):
                return True
        return False
    n = 0
    for br in ln["b"]:
        sub = [si for si in br if box[0] < stops[si][0] < box[2] and box[1] < stops[si][1] < box[3]]
        if len(sub) < 5:
            continue
        es, kept, _ = RT.route(adj, real, stops, [sub], 85.0, 60.0, 150.0, set())
        assert len(kept) == len(sub)
        assert sum(on_te(u, v) for u, v in es) >= 0.8 * len(es)
        n += 1
    assert n >= 3


# ── the audit, any city ────────────────────────────────────────────
def test_the_audit_checks_real_routes_from_data_not_tables():
    m = {"place": "Springfield", "tiles": [], "edges": [[0, 0, 3000, 0]], "streets": [],
         "transit": {"lines": [{"id": "x1", "n": "X", "c": "#000", "k": "metro", "p": [[0, 0, 3000, 0]], "s": [0, 2, 1],
                                "b": [[0, 2, 1]]}],
                     "stops": [{"n": "A", "x": 0, "y": 0, "l": ["x1"]}, {"n": "B", "x": 1000, "y": 0, "l": ["x1"]},
                               {"n": "C", "x": 2000, "y": 0, "l": ["x1"]}]}}
    real = {"lines": [{"id": "x1", "w": [[0, 0, 3000, 0]], "s": [0, 1, 2, 3], "b": [[0, 1, 2, 3], [3, 4, 5, 6]]}],
            "stops": [{"n": n, "x": 0, "y": 0} for n in "ABCDEFG"]}
    bad = " | ".join(AU.audit(m, real=real, to_page=lambda x, y: (x, y))["problems"])
    assert "not in ride order along the track" in bad                 # A, C, B along a straight track
    assert "does not run its real stops in order" in bad
    assert "the real branch D .. G is not drawn" in bad                # a lost branch, found with no city table
    assert "Lancaster" not in bad and "Woodland" not in bad            # the Philadelphia table is not applied here


def test_the_finished_picture_flags_rail_off_its_axes_and_a_dot_off_its_line():
    tr = {"lines": [{"id": "r", "n": "R", "c": "#000", "k": "rail", "p": [[0, 0, 1000, 0, 1600, 300]], "s": [0, 1]}],
          "stops": [{"n": "On", "x": 500, "y": 0, "l": ["r"]}, {"n": "Off", "x": 1000, "y": 30, "l": ["r"]}]}
    pic = AU.picture({"tiles": [], "edges": [], "streets": [], "transit": tr})
    assert [s[0] for s in pic["stops"]] == ["Off"]
    assert len(pic["runs"]) == 1 and pic["runs"][0][1] > 600          # the 26.6-degree run is neither street nor axis
    tr["lines"][0]["p"] = [[0, 0, 1000, 0, 1240, 170]]                 # a lattice diagonal (one block across) is legal
    tr["stops"][1]["y"] = 0
    assert AU.picture({"tiles": [], "edges": [], "streets": [], "transit": tr})["ok"]
