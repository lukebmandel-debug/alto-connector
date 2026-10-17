"""First-person view scope rule (2.0.0): only where something is active. alto/build/palace_ride_real.py Scope + palace_street scoping."""
import json
import subprocess
from pathlib import Path

from alto import palace_map as pmap
from alto.build import palace_ride_real as prr, palace_street as ps

BBOX = (39.90, -75.20, 39.96, -75.10)        # ~6.6 km x 8.5 km
D_FULL = {"unit": 0, "name": "Populated", "bounds": [39.9300, -75.1600, 39.9360, -75.1520]}
D_EMPTY = {"unit": 1, "name": "Empty", "bounds": [39.9500, -75.1200, 39.9560, -75.1120]}
NODE = Path.home() / ".local" / "node" / "bin" / "node"


def _geom(*pts):
    return [{"lat": la, "lon": lo} for la, lo in pts]


def _sq(la, lo, d=0.0004):
    return _geom((la, lo), (la, lo + d), (la + d, lo + d), (la + d, lo), (la, lo))


def _raw():
    """a house and a tree + a street in each district, and one in neither"""
    b = {"elements": [{"type": "way", "id": 1 + i, "geometry": _sq(la, lo), "tags": {"building": "house"}}
                      for i, (la, lo) in enumerate([(39.9320, -75.1580), (39.9520, -75.1180), (39.9100, -75.1900)])]}
    st = {"elements": [{"type": "node", "id": 10 + i, "lat": la, "lon": lo, "tags": {"natural": "tree"}}
                       for i, (la, lo) in enumerate([(39.9325, -75.1575), (39.9525, -75.1175), (39.9105, -75.1895)])]}
    return b, st


def _map(**kw):
    m = {"bbox": list(BBOX), "scale": 1.0, "W": 9000, "H": 7000, "landmarks": [], "boats": [], "grid": {"t": 0, "cx": 0, "cy": 0, "xr": [0, 1, 2], "xg": [0, 240, 480], "yr": [0, 1, 2], "yg": [0, 170, 340]}}
    m.update(kw)
    return m


def test_populated_district_is_in_bounds_and_the_empty_one_is_not():
    sp = prr.scope_for(_map(), [D_FULL, D_EMPTY], BBOX, nodes_in={0})
    x, y = sp.metres(39.9330, -75.1560)
    assert sp.contains(x, y)
    assert sp.contains(*sp.metres(39.9361 + 100 / 110574, -75.1560))          # inside the buffer
    assert not sp.contains(*sp.metres(39.9361 + 400 / 110574, -75.1560))      # past the 150 m buffer
    assert not sp.contains(*sp.metres(39.9530, -75.1160))                      # the empty district
    assert sp.tile_ok((39.9300, -75.1600, 39.9450, -75.1300)) and not sp.tile_ok((39.9480, -75.1300, 39.9600, -75.1000))


def test_landmark_boat_and_base_discs_stay_reachable():
    # the grid is the identity-ish map: page px == real px here, so a landmark at real (3000, 2000) is a disc of 120 m there
    m = _map(landmarks=[{"n": "L", "x": 3000.0, "y": 2000.0}], boats=[{"n": "B", "x": 6000.0, "y": 4000.0, "len": 200.0}], bases=[{"n": "base", "x": 1000.0, "y": 5000.0, "r": 80.0}])
    m["grid"] = {"t": 0, "cx": 0, "cy": 0, "xr": [0, 9000], "xg": [0, 9000], "yr": [0, 7000], "yg": [0, 7000]}
    sp = prr.scope_for(m, [], BBOX)
    assert sp is not None
    for X, Y in ((3000, 2000), (6000, 4000), (1000, 5000)):
        assert sp.contains(*sp.from_real(X, Y))
    assert sp.contains(*sp.from_real(3000 + 100, 2000))                        # the landmark's 120 m disc
    assert not sp.contains(*sp.from_real(3000 + 400, 2000))
    assert prr.scope_for(_map(), [], BBOX) is None                             # nothing active: the whole box is left alone


def test_only_in_bounds_tiles_are_asked_for(tmp_path, monkeypatch):
    sp = prr.scope_for(_map(), [D_FULL, D_EMPTY], BBOX, nodes_in={0})
    asked = []
    monkeypatch.setattr(pmap, "_post_overpass", lambda q, t=0: (asked.append(q), {"elements": []})[1])
    monkeypatch.setattr(pmap, "_sleep", lambda s: None)
    ps.fetch(BBOX, cache_dir=tmp_path, scope=sp)
    all_tiles = len(pmap.tile_boxes(BBOX, *ps.STREET_TILE))
    assert 0 < len(asked) < all_tiles / 3, (len(asked), all_tiles)


def test_build_writes_only_in_bounds_cells_and_says_so():
    b, st = _raw()
    sp = prr.scope_for(_map(), [D_FULL, D_EMPTY], BBOX, nodes_in={0})
    full_m, full_s = ps.build(BBOX, b, st)
    man, shards = ps.build(BBOX, b, st, scope=sp)
    assert "ib" not in full_m and man["ib"]["b"] == 150 and man["ib"]["r"]
    n_full = sum(len(c.get("b", [])) for s in full_s.values() for c in s["c"].values())
    n_scoped = sum(len(c.get("b", [])) for s in shards.values() for c in s["c"].values())
    assert n_full == 3 and n_scoped == 1                                        # only the populated district's house stays
    assert sum(man["f"].values()) < sum(full_m["f"].values())
    # the manifest's extent says where the data is: the kept cell is in it, the far houses' cells are not
    runs = {(iy, ix) for iy, a, z in man["ib"]["r"] for ix in range(a, z + 1)}
    fr = ps.Frame(BBOX)
    for (la, lo), want in (((39.9320, -75.1580), True), ((39.9520, -75.1180), False), ((39.9100, -75.1900), False)):
        X, Y = fr.xy(la, lo)
        assert (((Y // ps.CS), (X // ps.CS)) in runs) is want


def test_the_js_in_scope_check_agrees_with_the_manifest():
    if not NODE.exists():
        return
    from alto.build.palace_street_js import STREET_JS
    b, st = _raw()
    sp = prr.scope_for(_map(), [D_FULL, D_EMPTY], BBOX, nodes_in={0})
    man, shards = ps.build(BBOX, b, st, scope=sp)
    fr = ps.Frame(BBOX)
    pts = [fr.xy(39.9320, -75.1580), fr.xy(39.9520, -75.1180), fr.xy(39.9100, -75.1900)]
    js = "var window={}; " + STREET_JS + "; var S=window._palStreet; S.use(%s); console.log(JSON.stringify([%s].map(function(p){return S.inScope(p[0]*0.1,p[1]*0.1);})))" % (
        json.dumps(man), ",".join("[%d,%d]" % p for p in pts))
    out = subprocess.run([str(NODE), "-e", js], capture_output=True, text=True, timeout=60)
    assert json.loads(out.stdout) == [True, False, False], out.stdout + out.stderr


def test_the_page_js_has_the_bounds_hooks():
    for name in ("REAL.inBounds", "REAL.clamp", "REAL.edgeDist", "REAL.legInBounds", "REAL.bounds"):
        assert name in prr.JS_REAL
