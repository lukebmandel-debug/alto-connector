#!/usr/bin/env python3
"""Visitor-style room names for alto/buildings/pma_plan.json (Batch 4 of the PMA fix list). Idempotent post-process: run it after build_pma_plan.py.

    python docs/building-palace/clean_pma_names.py [--plan alto/buildings/pma_plan.json] [--report out.txt]

The generator copies a room's name from the 1928 Architectural Forum scan: "(1928)" suffixes, "(label illegible)", the 1928 sheet's own room numbers ("29 Byzantine"),
"Arts. room / Curator", the same "Sutton Scarsdale (possibly)" on three rooms. This rewrites `n` (the name every surface shows: the blueprint's label, the first-person
view's signs and search) to one visitor-style line, and keeps the 1928 text in `n28` (already there). Rules, in order:
  1. drop every parenthetical, "?" and the words "label illegible" / "possibly" (what a scan note says, not what a visitor reads); a name that was only a placeholder is gone;
  2. drop a leading 1928 sheet number ("29 Byzantine" -> "Byzantine"); a gallery number a visitor knows is `no` (the PMA's current one) and only that is shown;
  3. a room with a current gallery number reads "Gallery 223 · Name", or just "Gallery 223" when it has no name of its own;
  4. no name left: "Gallery NNN" when its tracer candidate is unique, else the room type's plain word ("Gallery", "Office", "Class room");
  5. the level 1 auditorium of 1928 is now where the Williams Forum's lower level is: "Former auditorium, now the Williams Forum";
  6. a compass word in a parenthesis ("Elevators (south)") stays as ", south"; two gallery-type rooms of one level with the same final name read "Name, room 2",
     "Name, room 3" (two lifts or two curators' offices are not duplicates).
Current gallery names beyond what the generator already has (`no`, installation names from the PMA's own pages) are NOT added here: a name comes from a public PMA page
(https://www.philamuseum.org/visit/museum-map, facts only) or is left as the plain "Gallery NNN". Nothing is invented.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAIN = {"gallery": "Gallery", "office": "Office", "classroom": "Class room", "court": "Court", "hall": "Hall", "lobby": "Lobby", "other": "Room", "service": "Service room",
         "library": "Library", "restroom": "Restroom", "stair": "Stair", "lift": "Lift", "stair-hall": "Stair hall", "auditorium": "Auditorium", "corridor": "Corridor"}
FORMER_AUDITORIUM = "Former auditorium, now the Williams Forum"


COMPASS = re.compile(r"\b(north|south|east|west)(?: side| bay)?\b", re.I)
SCAN_NOTE = re.compile(r"(1928|illegible|possibly|label|\bno\.)", re.I)
DUPLICATE_OK = ("service", "office", "restroom", "classroom", "lift", "other", "library", "stair", "lobby", "corridor")   # two lifts, two curators' offices: not duplicates


def parentheticals(name: str) -> list[str]:
    return [m.strip() for m in re.findall(r"\(([^()]*)\)", name or "")]


def strip_scan(name: str) -> str:
    s = name or ""
    while True:                                                               # parentheticals, innermost first
        t = re.sub(r"\([^()]*\)", " ", s)
        if t == s:
            break
        s = t
    s = s.replace("?", " ")
    s = re.sub(r"\b(label illegible|illegible|possibly)\b", " ", s, flags=re.I)
    s = re.sub(r"^\s*\d+[a-z]?(\s*/\s*\d+[a-z]?)*\s+(?=[A-Za-z])", "", s)      # a leading 1928 sheet number ("29 ", "27 / 26 ")
    s = re.sub(r"\s*/\s*Curator\b", "", s)
    s = re.sub(r"\bArts\.\s*", "Arts ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:-/")
    return s


def clean(plan: dict) -> list[tuple[str, str, str]]:
    changes, seen = [], defaultdict(int)
    for r in plan["rm"]:
        if r.get("ty") == "corridor" or r.get("gp") or not r.get("n"):
            continue
        old = r["n"]
        no = r.get("no")
        src = re.sub(r",\s*room \d+$", "", re.sub(r"^Gallery\s*\d+[a-z]?\s*·\s*", "", old))              # a name this script already wrote: start from what it came from
        base = strip_scan(src)
        notes = parentheticals(src)
        side = next((COMPASS.search(x).group(1).lower() for x in notes if COMPASS.fullmatch(x.strip())), None)
        if base.isdigit() or not base:                                         # "25 (vaulted room)": the scan's own note is the only name
            use = next((x for x in notes if x and not SCAN_NOTE.search(x) and not COMPASS.fullmatch(x)), "")
            base = use[:1].upper() + use[1:] if use and not use.isdigit() else ""
        if r["id"] == "l1-c-aud":
            base, no = FORMER_AUDITORIUM, None
        if re.fullmatch(r"(?i)gallery\s*\d+[a-z]?", base):
            base = ""
        if not base:
            cand = r.get("cand") or []
            if not no and len(cand) == 1:
                no = cand[0]
        if no:
            new = f"Gallery {no} · {base}" if base else f"Gallery {no}"
        else:
            new = base or PLAIN.get(r.get("ty"), "Room")
        if side and not no:                                                    # "Elevators (south)" -> "Elevators, south"; the number tells two numbered rooms apart
            new = f"{new}, {side}"
        key = (r["l"], new)
        seen[key] += 1
        if seen[key] > 1 and r.get("ty") not in DUPLICATE_OK:
            new = f"{new}, room {seen[key]}"
        if new != old:
            r["n"] = new
            changes.append((r["id"], old, new))
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=str(ROOT / "alto" / "buildings" / "pma_plan.json"))
    ap.add_argument("--report")
    a = ap.parse_args()
    path = Path(a.plan)
    plan = json.loads(path.read_text("utf-8"))
    changes = clean(plan)
    path.write_text(json.dumps(plan, separators=(",", ":"), ensure_ascii=False, sort_keys=True), encoding="utf-8")
    text = "\n".join(f"{i}\t{o}\t->\t{n}" for i, o, n in changes)
    if a.report:
        Path(a.report).write_text(text + "\n", "utf-8")
    print(f"{len(changes)} names changed")


if __name__ == "__main__":
    main()
