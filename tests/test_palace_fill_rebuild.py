"""The city's fill-in is rebuilt once the detail tiles stop arriving, not once per tile (Luke 2026-11-01: the memory map is glitchy). In his NYC page one 2.5 s pan
rebuilt the whole fill 13 times (fillDraw 40-85 ms each, then a 60-1000 ms repaint of the canvas and a 450 ms layout at the next zoom settle).
Runs palace_tiles.py's own ctFillSoon / ctFillSet in node with stubbed timers: no browser."""
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")
SRC = (ROOT / "alto" / "build" / "palace_tiles.py").read_text("utf-8")


def _fn(name):
    m = re.search(r"^function %s\(.*?^(?=\S)" % name, SRC, re.S | re.M)
    assert m, name
    text = m.group(0)
    # one-line functions end at their closing brace; the multi-line ones at the next top-level statement
    return text.rstrip()


def _run(script):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "t.js"
        f.write_text(script, "utf-8")
        r = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


HARNESS = """
let now = 0, q = [], draws = 0, nextId = 1;
function setTimeout(f, ms){ const id = nextId++; q.push({id, at: now + ms, f}); return id; }
function clearTimeout(id){ q = q.filter(t => t.id !== id); }
function advance(to){ for(;;){ q.sort((a, b) => a.at - b.at); const t = q[0]; if(!t || t.at > to) break; q.shift(); now = t.at; t.f(); } now = to; }
var CTfill = null, CTfs0 = [null, [], [], [], []], FS = [null, [], [], [], []], FG = 1, FC = null, svgD = {}, MM = {};
function fillShapes(){ return FS; } function fillDraw(){ draws++; } function fillLOD(){} function fillSoon(){} function ctMoving(){ return false; }
const lay = () => ({classList: {contains: () => false}, _fo: false});
var CTC = {a: {fs: [null, [1], [], [], []], e: {k: 'a'}, on: {d: 1}, g: {d: [lay()]}, lv: {d: 2}}, b: {fs: [null, [2], [], [], []], e: {k: 'b'}, on: {d: 1}, g: {d: [lay()]}, lv: {d: 2}}};
var CTfsig = '';
"""


def _script(body):
    return HARNESS + "\n" + _fn("ctFillSoon") + "\n" + _fn("ctFillSet") + "\n" + textwrap.dedent(body)


def test_tiles_landing_one_by_one_cause_one_rebuild_not_one_each():
    out = _run(_script("""
        ctFillSoon(); advance(100); ctFillSoon(); advance(200); ctFillSoon(); advance(300);   // three tiles, 100 ms apart
        advance(400); const mid = draws;                                                     // the fill is not rebuilt while they are still landing
        advance(1200); console.log(mid + ',' + draws);
    """))
    assert out == "0,1", out


def test_a_rebuild_for_the_same_parts_is_skipped():
    out = _run(_script("""
        ctFillSoon(); advance(1000); const first = draws;
        ctFillSoon(); advance(2000);                                                           // another tick, the same parts on: nothing to redo
        CTC.b.on.d = 0; CTC.b.g.d = []; ctFillSoon(); advance(3000);                         // a part went away: rebuilt
        console.log(first + ',' + draws);
    """))
    assert out == "1,2", out
