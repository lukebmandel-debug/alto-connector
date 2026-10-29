"""The first-person walks are glitch-free (and trips to cards arrive): tests/fpv_walk/walk_audit.js drives the Memory Blueprint renderer's own walking code (no browser, no GL;
node) through EVERY passable doorway of a plan, both ways, walking and running, up and down EVERY stair flight, out of and into every entrance
with traced ground, and hops in every doorway and on every flight; it fails on a door narrower or lower than the walker's capsule, a fall into
another floor (or the safety net catching one), a walker stuck in a corner or in geometry. Also: the hop itself (one per press, never through a
ceiling) .

Skipped without node."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto.build import building_schema as bs, palace_building_fpv as fpv  # noqa: E402
from tests import building_fpv_plans  # noqa: E402

AUDIT = ROOT / "tests" / "fpv_walk" / "walk_audit.js"
NODE = shutil.which("node") or (os.path.expanduser("~/.local/node/bin/node") if os.path.exists(os.path.expanduser("~/.local/node/bin/node")) else None)
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


@pytest.fixture(scope="module")
def tmp():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "fpv.js").write_text(fpv.FPV_ASSET, "utf-8")
        yield d


def _audit(tmp, name, plan, cards=False):
    p = tmp / f"{name}.json"
    p.write_text(bs.hosted_json(plan)[1], "utf-8")
    args = [NODE, str(AUDIT), str(tmp / "fpv.js"), str(p)] + (["cards"] if cards else [])
    out = subprocess.run(args, capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _pma():
    return json.loads((ROOT / "alto" / "buildings" / "pma_plan.json").read_text("utf-8"))


@pytest.mark.parametrize("name,cards", [("pma", True), ("pma", False), ("stress", True), ("fixture", True)])
def test_every_door_and_stair_walks_clean(tmp, name, cards):
    plan = {"pma": _pma, "stress": building_fpv_plans.stress_plan, "fixture": bs.fixture}[name]()
    r = _audit(tmp, name, plan, cards)
    assert not r["fails"], json.dumps(r["fails"][:12], indent=1)
    assert r["nets"] == 0                                  # the safety net never had to catch anyone
    assert r["doors"] > 0 and r["doorWalks"] >= 4
    assert r["capsule"]["r"] * 2 + 0.08 <= r["capsule"]["minDoor"]
    if name == "pma":
        assert r["doors"] >= 170 and r["stairs"] >= 12 and r["stairWalks"] >= 48 and r["entrances"] >= 2
        assert r["hops"] >= 150
    if cards:
        assert r["trips"] >= min(30, r["trips"]) and r["trips"] > 0       # card trips: every one arrived (else a "trip" failure above)
        assert r["tripStuckFade"] <= max(2, r["trips"] // 10)              # rarely stuck on the way (the fade then still gets you there)


def test_every_pma_room_can_be_walked_to(tmp):
    """the inferred doorways (build_pma_plan.INFERRED_DOORS) join every room to the Great Stair Hall on foot, stairs and lifts included; a trip to a
    card walks unless it is far. Lift cabs never hold a card (circulation), so only they may be reached by their floor rather than the card's spot."""
    p = tmp / "pma_reach.json"
    p.write_text(bs.hosted_json(_pma())[1], "utf-8")
    out = subprocess.run([NODE, str(ROOT / "tests" / "fpv_walk" / "reach_audit.js"), str(tmp / "fpv.js"), str(p)], capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["rooms"] >= 160 and not r["missing"], r["missing"]
    lifts = {x["id"] for x in _pma()["rm"] if x.get("ty") == "lift"}
    assert set(r["floorOnly"]) <= lifts, r["floorOnly"]


HOP_JS = r"""
global.window=global; global.document=null; global.navigator={};
eval(require('fs').readFileSync(process.argv[2],'utf8'));
var A=window.AltoBuildingFPV, S=A._debug(), plan=JSON.parse(require('fs').readFileSync(process.argv[3],'utf8')), out={};
function run(ch){ plan.rm.forEach(function(r){ r.ch=ch; }); var G=A.sim(plan), rm=G.rooms.filter(function(r){ return !r.isVoid&&!r.r.gp; })[0]; S.x=rm.ctr[0]; S.y=rm.ctr[1]; S.fz=rm.l.e; S.ez=S.fz+1.65; A.step(1/60,{},1); var z0=S.fz, top=z0; A.step(1/60,{hop:1},1); for(var i=0;i<90;i++){ A.step(1/60,{hop:1},1); top=Math.max(top,S.fz); }
  var hops=S.hops; for(var j=0;j<40;j++) A.step(1/60,{},1); A.step(1/60,{hop:1},1); for(var k=0;k<90;k++) A.step(1/60,{},1);
  return {apex:top-z0, held:hops, again:S.hops, landed:Math.abs(S.fz-z0)<1e-6&&!S.air, bonks:S.bonks}; }
out.tall=run(4); out.low=run(2.05); out.tiny=run(1.9);
console.log(JSON.stringify(out));
"""


def test_the_hop_is_one_per_press_and_never_through_a_ceiling(tmp):
    plan = bs.fixture()
    (tmp / "hop.js").write_text(HOP_JS, "utf-8")
    p = tmp / "hopplan.json"
    p.write_text(bs.hosted_json(plan)[1], "utf-8")
    out = subprocess.run([NODE, str(tmp / "hop.js"), str(tmp / "fpv.js"), str(p)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert 0.3 < r["tall"]["apex"] < 0.5 and r["tall"]["held"] == 1 and r["tall"]["again"] == 2 and r["tall"]["landed"]
    head = fpv.FPV_ASSET.split("head:")[1].split(",")[0]
    assert r["low"]["apex"] <= 2.05 - float(head) and r["low"]["bonks"] >= 1 and r["low"]["landed"]      # a 2.05 m ceiling: the head stops at it
    assert r["tiny"]["apex"] < 1e-6 and r["tiny"]["again"] == 0                                           # no room over the head: no hop at all


def test_the_first_person_views_carry_no_avatar_and_no_third_person():
    js = fpv.FPV_ASSET
    for gone in ("Cherelle Parker", "Zohran Mamdani", "avatarBatch", "setView", "camEye(fw){ var me", "bf-opts", "bf-tag", "alto-fpv-view", "alto-fpv-avatar", "third person", "first / third"):
        assert gone not in js, gone
    assert "(k==='t'||k==='T')" not in js
    assert "HOP={v0:3.3, g:13.5, coyote:.1, buffer:.13}" in js and "k===' '||c==='Space') n='hop'" in js          # the hop stays
