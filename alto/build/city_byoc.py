"""Build any place with your own Claude (rules doc section 13, "Bring-your-own-Claude"): for a place that is not a preset,
the user's own Claude runs set_up_palace(place, auto=True), which follows the rules doc, and the scored gate (section 10,
city_gate) checks the result before it is offered. A city that does not pass (any fail, score under 85, or a zero-tolerance
row G5 / G7 / G15 not clean) is saved as a DRAFT and not shown as a preset, and the user is told in plain words what failed.

    with capture() as cap:                       # around palace.set_up: keeps the map and the drawing the gate reads
        pal = palace.set_up(...)
    v = verdict(city_gate.gate(cap["g"], cap["m"], preset=...))
    -> {"pass", "score", "draft", "failing": [plain words], "warnings": [plain words], "message"}
Pure apart from the capture (it wraps palace_grid.grid for the length of the with-block, as city_gate.run_city does).
"""
from __future__ import annotations

import contextlib
import copy
import re

# what the user reads for a row that failed (no raw check codes)
PLAIN = {
    "G1": "part of the street grid could not be read as even blocks",
    "G2": "some drawn streets barely exist in the real city",
    "G3": "some landmarks or stops are drawn more than a block from where they really are",
    "G4": "some main streets cross the grid in the wrong order",
    "G5": "some places are drawn on the wrong side of a river",
    "G6": "where two street grids meet, the join is off",
    "G7": "some streets stop in the middle of nowhere",
    "G8": "some main streets bend too much",
    "G9": "some transit lines leave their streets or run their stops out of order",
    "G10": "some highways are crooked or miss a river crossing",
    "G11": "too many blocks are cut or left open",
    "G12": "the city carries too much map data for its size",
    "G13": "parts of the page overlap",
    "G14": "landmarks are bunched together or set back from their streets",
    "G15": "something is drawn in the water, or a river is too thin",
    "G16": "a park is missing or has a street through it",
    "G17": "a city needs 8 to 24 landmarks that do not overlap",
    "G18": "some neighbourhood names sit on top of each other",
    "G19": "the page is too big to save",
    "G20": "the zoomed-in detail files are too big",
    "G21": "the city took too long to build",
    "G22": "two builds of the same city came out different",
}


@contextlib.contextmanager
def capture():
    """Keep the real map (m, before the drawing) and the drawing (g) of the palace_grid.grid call made inside the block."""
    from . import palace_grid
    cap = {}
    g0 = palace_grid.grid

    def grid(m, **kw):
        cap["m"] = copy.deepcopy(m)
        g = g0(m, **kw)
        cap["g"] = copy.deepcopy(g)
        return g
    palace_grid.grid = grid
    try:
        yield cap
    finally:
        palace_grid.grid = g0


def _say(row, msg):
    s = PLAIN.get(row, row)
    if row == "G17":
        n = re.match(r"(\d+) landmarks", msg or "")
        if n:
            s += " (it has %s)" % n.group(1)
    return s


def verdict(rep) -> dict:
    """The gate's report in the words the user reads: what failed, what is only a warning, and one sentence to say."""
    from .city_gate import PASS_SCORE
    failing = [_say(r, c["msg"]) for r, c in rep["checks"].items() if c["status"] == "fail"]
    warnings = [_say(r, c["msg"]) for r, c in rep["checks"].items() if c["status"] == "warn"]
    ok = bool(rep["pass"])
    if ok:
        msg = "This city passed Alto's city check (%.0f of 100)." % rep["score"]
    else:
        why = failing or (["its score is under %d" % PASS_SCORE] if rep["score"] < PASS_SCORE else ["a required check did not run"])
        msg = ("This city did not pass Alto's city check (%.0f of 100, it needs %d): %s. It is saved as a draft, so you "
               "can still use it, but it is not offered as a ready-made city. Try a smaller box around the centre, or name "
               "the main streets and landmarks yourself." % (rep["score"], PASS_SCORE, "; ".join(why)))
    return {"pass": ok, "score": rep["score"], "draft": not ok, "failing": failing, "warnings": warnings, "message": msg}


def gate_built(cap, parks=(), layout=None, channels=None) -> dict:
    """The gate on what capture() kept, as a verdict (a build that never drew a grid: not passed, said plainly)."""
    from . import city_gate
    if "g" not in cap:
        return {"pass": False, "score": 0.0, "draft": True, "failing": ["the city could not be drawn"], "warnings": [],
                "message": "This city could not be drawn, so it is saved as a draft."}
    rep = city_gate.gate(cap["g"], cap["m"], preset={"parks": list(parks or ()), "layout": layout, "channels": channels or ()})
    return verdict(rep)
