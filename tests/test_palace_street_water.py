"""Water in the street data (palace_street_water.py) and the ride (palace_ride_water.py): multipolygon rings, the cut per cell, both decoders, walking rules, size."""
import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from alto.build import palace_street as ps
from alto.build import palace_street_water as pw
from alto.build.palace_street_js import STREET_JS
from alto.build.palace_ride_water import JS_WATER

NODE = Path.home() / ".local" / "node" / "bin" / "node"
BBOX = (39.94, -75.20, 39.96, -75.17)


def _g(*pts):
    return [{"lat": a, "lon": b} for a, b in pts]


# a river as a multipolygon: the outer ring in THREE open ways (one reversed) and an island (inner); a fountain node, a pool, a pier, a stream, a wood
RIVER = {"type": "relation", "id": 1, "tags": {"type": "multipolygon", "natural": "water", "water": "river", "name": "Schuylkill River"}, "members": [
    {"type": "way", "role": "outer", "ref": 11, "geometry": _g((39.945, -75.190), (39.945, -75.185), (39.955, -75.185))},
    {"type": "way", "role": "outer", "ref": 12, "geometry": _g((39.955, -75.190), (39.955, -75.1875), (39.955, -75.185))[::-1]},
    {"type": "way", "role": "outer", "ref": 13, "geometry": _g((39.955, -75.190), (39.945, -75.190))},
    {"type": "way", "role": "inner", "ref": 14, "geometry": _g((39.949, -75.188), (39.949, -75.187), (39.950, -75.187), (39.950, -75.188), (39.949, -75.188))}]}
EXTRA = [
    {"type": "node", "id": 2, "lat": 39.952, "lon": -75.175, "tags": {"amenity": "fountain"}},
    {"type": "way", "id": 3, "tags": {"leisure": "swimming_pool"}, "geometry": _g((39.9500, -75.1760), (39.9500, -75.1758), (39.9502, -75.1758), (39.9502, -75.1760), (39.9500, -75.1760))},
    {"type": "way", "id": 4, "tags": {"leisure": "swimming_pool", "indoor": "yes"}, "geometry": _g((39.951, -75.176), (39.951, -75.1758), (39.9512, -75.1758), (39.951, -75.176))},
    {"type": "way", "id": 5, "tags": {"man_made": "pier"}, "geometry": _g((39.950, -75.1849), (39.950, -75.1860))},
    {"type": "way", "id": 6, "tags": {"waterway": "stream", "width": "3"}, "geometry": _g((39.946, -75.178), (39.947, -75.177))},
    {"type": "way", "id": 7, "tags": {"natural": "wood"}, "geometry": _g((39.946, -75.183), (39.946, -75.182), (39.947, -75.182), (39.946, -75.183))},
]
RAW = {"elements": [RIVER] + EXTRA}


def test_multipolygon_rings_are_stitched_and_oriented():
    p = pw.parse(RAW)
    rivers = [x for x in p["polys"] if x[0] == "river"]
    assert len(rivers) == 2 and sorted(x[3] for x in rivers) == [False, True]           # the outer (3 open ways joined) and the island
    outer = [x for x in rivers if not x[3]][0][2]
    assert len(outer) == 5                                                              # every vertex once, no repeated end point
    assert [x[0] for x in p["polys"] if x[0] != "river"] == ["pool"]                     # the indoor pool is not water to draw
    assert p["points"] == [(39.952, -75.175, "fountain")] and p["lines"][0][0] == "stream" and abs(p["lines"][0][2] - 3) < 1e-9
    assert p["shore"][0][0] == "pier" and p["shore"][0][2] == 0 and p["green"][0][3]["_kind"] == "wood"


def test_clip_keeps_area_and_orientation():
    sq = [(0, 0), (10000, 0), (10000, 10000), (0, 10000)]
    pieces = [pw.clip_ring(sq, ix * ps.CS, iy * ps.CS, (ix + 1) * ps.CS, (iy + 1) * ps.CS) for ix in range(2) for iy in range(2)]
    assert all(pieces) and abs(sum(pw.signed_area(q) for q in pieces) - 1e8) < 1 and all(pw.signed_area(q) > 0 for q in pieces)
    cw = pw.orient(sq, False)
    assert pw.signed_area(pw.clip_ring(cw, 0, 0, 5000, 5000)) < 0
    assert pw.clip_ring(sq, 20000, 20000, 25000, 25000) == []


def _build():
    return ps.build(BBOX, {"elements": []}, {"elements": []}, water_raw=RAW)


def _cells(man, shards):
    return {k: ps.decode_cell(man, k, shards) for k in man["c"]}


def test_water_is_cut_per_cell_and_islands_are_holes():
    man, shards = _build()
    cells = _cells(man, shards)
    q = [d for c in cells.values() for d in c["q"]]
    river = [d for d in q if d["k"] == "river"]
    assert len({k for k, c in cells.items() if any(d["k"] == "river" for d in c["q"])}) >= 2      # the river crosses cell borders: a piece in each
    holes = [d for d in river if d["h"]]
    assert holes and all(pw.signed_area(d["ring"]) < 0 for d in holes) and all(pw.signed_area(d["ring"]) > 0 for d in river if not d["h"])
    area = sum(pw.signed_area(d["ring"]) for d in river)                                        # outer minus island, square metres
    fr = ps.Frame(BBOX)
    w = (0.005 * fr.kx) * (0.010 * ps.KY) - (0.001 * fr.kx) * (0.001 * ps.KY)
    assert abs(area - w) / w < 0.01
    assert sum(len(c["o"]) for c in cells.values()) == 1 and sum(len(c["v"]) for c in cells.values()) == 1
    assert any(d["k"] == "pier" and "line" in d and abs(d["wd"] - 4) < 0.01 for c in cells.values() for d in c["k"])
    assert any(a["k"] == "wood" for c in cells.values() for a in c["a"])


def test_an_old_client_reads_a_cell_with_water():
    """The old reader takes the keys it knows; the water keys are arrays (all an old okShard asks of an unknown key)."""
    man, shards = _build()
    for sh in shards.values():
        for c in sh["c"].values():
            assert all(isinstance(c[k], list) for k in pw.KEYS if k in c)


def test_water_reaches_past_the_region():
    class Sc:
        buffer = 150

        def cells(self, cs, nx, ny):
            return {(2, 2)}

        def hits(self, x0, y0, x1, y1, g=0):
            return x0 <= 1250 + g and x1 >= 1000 - g and y0 <= 1250 + g and y1 >= 1000 - g
    assert (3, 2) in pw.reach(Sc(), {(2, 2)}, 6, 6, 500.0) and (5, 5) not in pw.reach(Sc(), {(2, 2)}, 6, 6, 500.0)


def test_fetch_is_cached_offline_and_never_fatal(tmp_path, monkeypatch):
    calls = []

    def fake(q, t):
        calls.append(q)
        return RAW
    monkeypatch.setattr(pw.pmap, "_post_overpass", fake)
    assert pw.fetch(BBOX, cache_dir=tmp_path)["elements"] and pw.fetch(BBOX, cache_dir=tmp_path, offline=True)["elements"] and len(calls) == 1
    assert "natural=water" in calls[0] and "out geom" in calls[0]

    def boom(q, t):
        raise RuntimeError("busy")
    monkeypatch.setattr(pw.pmap, "_post_overpass", boom)
    assert pw.fetch((1, 2, 3, 4), cache_dir=tmp_path)["missing"] is True


def _node():
    return str(NODE) if NODE.exists() else shutil.which("node")


@pytest.mark.skipif(not (NODE.exists() or shutil.which("node")), reason="node not on this machine")
def test_both_decoders_agree_on_water(tmp_path):
    man, shards = _build()
    src = tmp_path / "t.js"
    src.write_text("var window={}; " + STREET_JS + "\nvar S=window._palStreet; var man=%s, sh=%s; S.use(man, sh); var out=[];"
                   "for(var k in man.c){ var p=k.split(','), c=S.cell(+p[0],+p[1]); c.q.forEach(function(d){ out.push(['q',d.k,d.nm,d.h,d.ring]); });"
                   " c.v.forEach(function(d){ out.push(['v',d.k,d.wd,d.line]); }); c.o.forEach(function(d){ out.push(['o',d.kind,d.x,d.y]); });"
                   " c.k.forEach(function(d){ out.push(['k',d.k,d.c,d.wd,d.ring||d.line]); }); }"
                   "var N=S.near(%r,%r,40,'q'); console.log(JSON.stringify({out:out, near:N.q.length}));" % (json.dumps(man), json.dumps(shards), 1200.0, 900.0), "utf-8")
    js = json.loads(subprocess.run([_node(), str(src)], capture_output=True, text=True, check=True).stdout)

    def r(v):
        return [[round(a, 4), round(b, 4)] for a, b in v]
    py = []
    for c in _cells(man, shards).values():
        py += [["q", d["k"], d["nm"], d["h"], r(d["ring"])] for d in c["q"]] + [["v", d["k"], round(d["wd"], 4), r(d["line"])] for d in c["v"]]
        py += [["o", d["kind"], round(d["x"], 4), round(d["y"], 4)] for d in c["o"]] + [["k", d["k"], d["c"], round(d["wd"], 4), r(d.get("ring") or d["line"])] for d in c["k"]]

    def norm(x):
        def f(v):
            return [f(i) for i in v] if isinstance(v, list) else (round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
        return json.dumps(f(x))
    assert sorted(map(norm, js["out"])) == sorted(map(norm, py))
    assert js["near"] >= 1                                         # a point inside a big piece, far from its edges, still finds it


@pytest.mark.skipif(not (NODE.exists() or shutil.which("node")), reason="node not on this machine")
def test_the_walker_cannot_enter_the_water_but_may_cross_a_bridge_and_walk_a_pier(tmp_path):
    js = ("var window={}, K=1.3, CELL=300, UM=1.3, REAL={fromStreet:function(){return {};}, load:function(){return {};}};\n" + JS_WATER +
          "\nvar sq=[0,0,100,0,100,100,0,100].map(function(v){return v*K;}), isl=[40,40,40,60,60,60,60,40].map(function(v){return v*K;});"
          "var W={roads:[{br:1,x0:-20*K,y0:20*K,x1:120*K,y1:20*K,w:8*K}], real:{}};"
          "W.rw={pcs:[{k:'river',sunk:true,r:sq,cut:[0,0,0,0],bb:rwBB(sq),D:2.8*K},{k:'river',h:1,sunk:true,r:isl,cut:[0,0,0,0],bb:rwBB(isl),D:2.8*K}],"
          " fo:[[300*K,300*K,'fountain']], strips:[], piers:[{k:'pier',c:0,w:4*K,g:[0,80*K,30*K,80*K],bb:[0,80*K,30*K,80*K]}]};"
          "var H=function(x,y){ return realWaterHit(x*K,y*K,W,.6*K); };"
          "console.log(JSON.stringify([H(70,70), H(-5,70), H(50,50), H(50,21), H(50,33), H(20,80), H(300,300), H(150,150), REAL.waterAt(W,70*K,70*K)]));")
    f = tmp_path / "w.js"
    f.write_text(js, "utf-8")
    got = json.loads(subprocess.run([_node(), str(f)], capture_output=True, text=True, check=True).stdout)
    # water / land / an island / the bridge deck / off the bridge's side / the pier / a fountain basin / land / waterAt
    assert got == [True, False, False, False, True, False, True, False, True]


def test_size_budget():
    assert len(gzip.compress(JS_WATER.encode(), 9)) < 9000                      # the ride asset grows by at most ~15 KB gzipped (measured +6.3 KB with the wiring)
    man, shards = _build()
    assert all("q" not in c or len(json.dumps(c["q"])) < 4000 for sh in shards.values() for c in sh["c"].values())
