"""Harbour ship spacing and names (1.9.262, alto/build/palace_fleet_space.py): a non-fleet unit test. The pure parts of the hosted script run in node (no browser, no sound):
ships that lie on top of one another in real life are fanned out along the water without overlap and stay in the river, at three zooms; each name sits clear of every other
name and every hull. Python then checks the boxes node returns with its own separating-axes test."""
import json
import re
import shutil
import subprocess

import pytest

from alto.build import palace_fleet_js, palace_fleet_space

NODE = shutil.which("node") or "/Users/lbmandel/.local/node/bin/node"
A = palace_fleet_js.FLEET_A
PRE = "var WK={bb:'bb', sub:'sub', carrier:'cv', cruiser:'dd'}; var MINL={bb:150, cv:170, dd:96, sub:84};\n" + re.search(r"function boatKind\(.*?\n  return 'ship'; \}", A, re.S).group(0) + "\n"
HARNESS = PRE + palace_fleet_space.FLEET_S + r"""
var inp=JSON.parse(require('fs').readFileSync(0,'utf8')), M={river:inp.river, boats:inp.boats}; spaceBoats(M);
var out={boats:M.boats.map(function(b){ return {n:b.n, x:b.x, y:b.y, x0:b.x0, y0:b.y0, L:b._L, W:b._W, a:b.a, pts:hullBox(b).pts}; }), zooms:[]};
inp.zooms.forEach(function(z){ var tw=1/z, items=M.boats.map(function(b){ return {b:b, w:(b.n||'').length*6.8}; }); layoutLabels(items, tw, (inp.avoid||[]).map(function(r){ return r.map(function(v){ return v*tw; }); }));
  out.zooms.push({z:z, labels:items.map(function(it){ return {n:it.b.n, box:it.box, lead:it.lead, hide:it.hide}; })}); });
console.log(JSON.stringify(out));
"""


def _run(boats, river, zooms=(.15, .5, 1.4), avoid=()):
    p = subprocess.run([NODE, "-e", HARNESS], input=json.dumps({"boats": boats, "river": river, "zooms": list(zooms), "avoid": [list(a) for a in avoid]}), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def _sat(P, Q):
    for poly in (P, Q):
        for i in range(len(poly)):
            ex, ey = poly[(i + 1) % len(poly)][0] - poly[i][0], poly[(i + 1) % len(poly)][1] - poly[i][1]
            ax, ay = -ey, ex
            a = [p[0] * ax + p[1] * ay for p in P]
            b = [p[0] * ax + p[1] * ay for p in Q]
            if max(a) <= min(b) + 1e-6 or max(b) <= min(a) + 1e-6:
                return False
    return True


def _rect(b):
    return [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]


# Penn's Landing as the data had it: the cruiser and the submarine 11 m apart on one pier, a tall ship farther down; the Delaware runs north-south, 260 px wide
RIVER = [{"n": "Delaware", "w": 260, "p": [0, -2000, 0, 2000]}]
FIX = [{"n": "USS Olympia", "x": 20.0, "y": 0.0, "a": 90.0, "len": 135.0, "wid": 30.0, "k": "dd"},
       {"n": "USS Becuna", "x": 34.0, "y": 6.0, "a": 90.0, "len": 123.0, "wid": 16.0, "k": "sub"},
       {"n": "Moshulu", "x": 22.0, "y": 150.0, "a": 90.0, "len": 140.0, "wid": 30.0},
       {"n": "USS Mystery", "x": 30.0, "y": 140.0, "a": 90.0, "len": 100.0, "wid": 22.0, "k": "dd"}]


def test_close_ships_fan_out_without_overlap_and_stay_in_the_water():
    out = _run([dict(b) for b in FIX], RIVER)
    boats = out["boats"]
    for i in range(len(boats)):
        for j in range(i + 1, len(boats)):
            assert not _sat(boats[i]["pts"], boats[j]["pts"]), (boats[i]["n"], boats[j]["n"])
    for b in boats:
        assert abs(b["x"]) <= 130 - b["W"] / 2, b["n"]                              # inside the river's water (half width 130)
        assert abs(b["x"] - b["x0"]) < 140 and abs(b["y"] - b["y0"]) < 400          # moved only along the shore, never across the map
    assert boats[0]["y"] != boats[1]["y"]                                           # the two on one pier are apart now
    for z in (.15, .5, 1.4):                                                        # a map zoom scales every hull alike: still apart on the screen
        sc = [[[p[0] * z, p[1] * z] for p in b["pts"]] for b in boats]
        assert not any(_sat(sc[i], sc[j]) for i in range(len(sc)) for j in range(i + 1, len(sc)))


def test_a_ship_alone_is_not_moved():
    out = _run([dict(FIX[2])], RIVER)
    assert (out["boats"][0]["x"], out["boats"][0]["y"]) == (22.0, 150.0)


def test_every_name_clear_of_every_other_name_and_every_hull_at_three_zooms():
    out = _run([dict(b) for b in FIX], RIVER)
    hulls = [b["pts"] for b in out["boats"]]
    for zr in out["zooms"]:
        assert len(zr["labels"]) == len(FIX)
        boxes = [l["box"] for l in zr["labels"]]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                assert not _sat(_rect(boxes[i]), _rect(boxes[j])), (zr["z"], i, j)
            for h in hulls:
                assert not _sat(_rect(boxes[i]), h), (zr["z"], i)


def test_the_submarine_is_a_submarine_by_data_and_by_name():
    p = subprocess.run([NODE, "-e", PRE + "console.log(JSON.stringify(['USS Becuna','USS Pampanito','USS Cod','USS Torsk','USS Bowfin','USS Silversides','USS Olympia','Moshulu','USS Codfish Cove'].map(function(n){ return boatKind(n, 120, 20); })))"],
                       capture_output=True, text=True)
    assert json.loads(p.stdout) == ["sub"] * 6 + ["cruiser", "tall", "ship"]


def test_the_submarine_art_is_low_dark_and_bare():
    art = palace_fleet_js.FLEET_A
    sub = art[art.index("function toySub("):art.index("/* ── a base:")]
    assert "pegs(" not in sub and "bb-eng" not in sub                                # no deck clutter: no pegs, no deck line, no tail fins
    assert "rr(.08*L" in sub and "bb-scope" in sub                                   # one conning tower and its periscope
    from alto.build import palace_fleet_css
    assert "@B.sub .bb-plastic" in palace_fleet_css.FLEET_CSS.replace(".pal-svg .pl-boat", "@B")   # a darker hull for every style


def test_the_hosted_script_carries_the_spacing_and_the_page_does_not():
    from alto.build import palace_fleet_asset
    assert "function spaceBoats(" in palace_fleet_asset.FLEET_ASSET and "spaceBoats(M); (M.boats" in palace_fleet_asset.FLEET_ASSET
    assert "labelsFit(lg, M)" in palace_fleet_asset.FLEET_ASSET


def test_no_ship_name_falls_on_the_pages_bars_at_phone_width():
    # p390: the top bar (title + chips) is 0..163 px, the bottom row 772..844 px, each plus 20 px; the map is shown at zoom 1 (screen px = map units here, avoid in screen px)
    top, bottom = [-50, -50, 440, 163 + 20], [-50, 792 - 20, 440, 900]
    boats = [{"n": "USS Olympia", "x": 60.0, "y": 150.0, "a": 90.0, "len": 135.0, "wid": 30.0, "k": "dd"},           # centred right under the chips
             {"n": "USS Becuna", "x": 60.0, "y": 420.0, "a": 90.0, "len": 123.0, "wid": 16.0, "k": "sub"},
             {"n": "Moshulu", "x": 60.0, "y": 790.0, "a": 90.0, "len": 140.0, "wid": 30.0}]                         # centred in the bottom row
    out = _run(boats, [], zooms=(1.0,), avoid=[top, bottom])
    for lab in out["zooms"][0]["labels"]:
        if not lab["hide"]:
            for bar in (top, bottom):
                assert not _sat(_rect(lab["box"]), _rect(bar)), lab["n"]     # a name on a bar is hidden, never drawn there
    shown = {l["n"] for l in out["zooms"][0]["labels"] if not l["hide"]}
    assert "USS Becuna" in shown                                              # the one in the clear keeps its name
