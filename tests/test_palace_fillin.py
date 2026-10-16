"""Fill-in prototype (palace_fillin.py): off by default and byte-identical; tiers; footprints land inside their block."""
from types import SimpleNamespace

from alto.build import palace as pal
from alto.build import palace_fillin as pf
from alto.build.palace_grid import Mapping


def test_off_is_unchanged():
    b = SimpleNamespace(palace={"data_z": "x"})
    assert pal.palace_js(b) is pal.PALACE_JS
    assert pal.palace_css(b) is pal.PALACE_CSS


def test_on_splices_every_hook_once():
    b = SimpleNamespace(palace={"fill_z": "x"})
    js = pal.palace_js(b)
    assert js != pal.PALACE_JS
    for fn in ("function fillDraw(", "function fillLOD(", "fillKeyRow()", "fillWire(k)", "fillDraw(svg);\n  drawBuildings(svg);"):
        assert js.count(fn) >= 1, fn
    assert pal.palace_css(b).endswith(pf.FILL_CSS)


def test_tiers():
    assert pf.tier_of({"building": "yes"}, 10, 0) is None
    assert pf.tier_of({"building": "office", "height": "150"}, 900, 150) == 1
    assert pf.tier_of({"building": "yes", "building:levels": "9"}, 400, pf.height_of({"building:levels": "9"})) == 2
    assert pf.tier_of({"building": "yes"}, 500, 9) == 3
    assert pf.tier_of({"building": "house"}, 80, 8) == 4
    assert pf.height_of({"height": "120 m"}) == 120


def _way(lat0, lon0, dlat, dlon, **tags):
    pts = [(lat0, lon0), (lat0, lon0 + dlon), (lat0 + dlat, lon0 + dlon), (lat0 + dlat, lon0), (lat0, lon0)]
    return {"type": "way", "tags": {"building": "yes", **tags}, "geometry": [{"lat": a, "lon": o} for a, o in pts]}


def test_footprints_land_in_their_block_and_skip_landmarks():
    from alto import palace_map as pm
    bbox = (39.95, -75.17, 39.96, -75.15)
    W, H = pm.project(bbox[0], bbox[3], bbox)
    xr, yr = [0, W / 2, W], [0, H / 2, H]
    mp = Mapping(0.0, W / 2, H / 2, xr, [110, 350, 590], yr, [110, 280, 450])
    m = {"bbox": list(bbox), "scale": 1.0, "grid": mp.tables(), "tiles": [[110, 110, 350, 280], [350, 110, 590, 280]],
         "landmarks": [{"n": "L", "box": [350, 110, 590, 280]}]}
    raw = {"elements": [_way(39.957, -75.168, .0006, .0012, name="Big Hall", height="80"),   # north-west block
                        _way(39.957, -75.158, .0006, .0012),                               # north-east: a landmark's block
                        _way(39.951, -75.168, .0003, .0003)]}                              # south-west: not a block
    f = pf.fill_data(raw, m)
    assert len(f["s"]) == 1 and f["s"][0][0] == 1 and f["n"] == {"0": "Big Hall"}
    s = f["s"][0]
    xs, ys, x, y = [s[2]], [s[3]], s[2], s[3]
    for i in range(4, len(s), 2):
        x += s[i]; y += s[i + 1]; xs.append(x); ys.append(y)
    assert 110 + 12 <= min(xs) and max(xs) <= 350 - 12 and 110 + 12 <= min(ys) and max(ys) <= 280 - 12
    assert pf.counts(f) == [1, 0, 0, 0]
