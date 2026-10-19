#!/usr/bin/env python3
"""Assemble alto/buildings/pma_plan.json (the curated Philadelphia Museum of Art Building Palace plan) from the research folder.

    python docs/building-palace/build_pma_plan.py --src <research dir> [--out alto/buildings/pma_plan.json]

The research folder holds (read-only, treated as data): traced/plan_L1|L2|L3.json (the 1928 Architectural Forum plates traced into Alto's schema),
traced/L1|L2|L3.json (neutral geometry with the tracer's candidate gallery numbers and changed-since-1928 flags), pma_building.json (OSM footprint, PMA-published
dimensions, entrances, terrain), gallery_guide.md (gallery number -> collection area, installations, public-domain works).

Everything the plan says is either SOURCED (a src id with its licence) or ASSUMED (confidence 0/1 and a basis text). Nothing here is traced from the PMA visitor map or events
plans: they are read for facts only (gallery numbers, levels, published dimensions). Licence notes: alto/buildings/README-pma.md and the plan's own `src`.

Level naming. The plan follows the visitor map's levels G, 1, 2, 3. The 1928 Forum sheets map to them as: basement -> level 1 (Lenfest Hall / Forum Gallery level), first floor ->
level 2 (Great Stair Hall), second floor -> level 3. Level G (vaulted walkway, Williams Forum) is not on the 1928 plates; it comes from PMA-published dimensions only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from alto.build import building_schema as bs  # noqa: E402

FT = 0.3048
IN = 0.0254

# ── collection areas -> section colours (Alto's own palette; the PMA's map colours are not copied) ─────────────────────────────────────────
AREAS = [
    ("am1650", "American Art 1650-1850", "#c0563b"),
    ("am1850", "American Art 1850-1950", "#d98a2b"),
    ("mod", "Modern & Contemporary Art", "#d4509a"),
    ("pdp", "Prints, Drawings, Photographs", "#5b7c99"),
    ("spx", "Special Exhibitions", "#8a4fd6"),
    ("imp", "European Art 1850-1900 / Impressionism", "#3aa05a"),
    ("eu1100", "European Art 1100-1500", "#2f7fb8"),
    ("asia", "Asian Art", "#c83a3a"),
    ("arms", "Arms & Armor", "#6b6f85"),
    ("eu1500", "European Art 1500-1850", "#1f9aa0"),
    ("amper", "American Art Period Rooms", "#a9892b"),
    ("sculpt", "Sculpture & Installations", "#9b6b3f"),
    ("learn", "Learning & Engagement", "#4a9d8a"),
]
AREA_BY_GUIDE = {
    "American Art 1650-1850": "am1650", "American Art 1850-1950": "am1850", "Modern & Contemporary Art": "mod",
    "Prints, Drawings, Photographs": "pdp", "Special Exhibitions": "spx", "European Art 1850-1900 / Impressionism": "imp",
    "European Art 1100-1500 (Medieval to Early Renaissance)": "eu1100", "Asian Art": "asia", "Arms & Armor": "arms",
    "European Art 1500-1850 (Renaissance to Romanticism)": "eu1500", "American Art Period Rooms": "amper",
}

# unique tracer candidates that contradict the 1928 room's own label (nationality/period vs the named installation): left unnumbered, candidate kept
CONFLICTS = {
    "l3-n-13": "1928 'Louis XVI' vs Gallery 362 Jacobean Room",
    "l3-n-14": "1928 'Louis XV' vs Gallery 361 Dutch room (Het Scheepje)",
    "l3-n-dutch": "1928 'Dutch XVII cent.' vs Gallery 355 French Renaissance Hall",
    "l3-sw-33": "1928 'Japan' vs Gallery 326 Chinese reception hall",
    "l3-n-other-eur": "1928 'Other Europe XIX cent.' vs Gallery 363 Tudor Room (Red Lodge)",
}
NUMBER_TYPES = ("gallery",)           # a 1928 office / class room / corridor is not given a gallery number from a schematic label point

# the cloister: resolved by evidence (Saint-Genis cloister installed 1928; PMA LibGuide Gallery 304; traced colonnade 14.8 x 14.7 m vs PMA 14.31 m)
CLOISTER_ROOM = "l3-s-28"

SRC = [
    {"id": "af1928", "t": "The Architectural Forum, July 1928 (vol. 49 no. 1): 'The Philadelphia Museum of Art', plan plates (basement, first, second floor)", "u": "https://archive.org/details/architecturalfo1928unse_0",
     "k": "archive", "lic": "public domain (published 1928 in the US); scan by Boston Public Library via Internet Archive",
     "n": "Walls, rooms, doors, stairs and columns traced by raster extraction plus manual room reading; layout as built in 1928, partly changed since (see x28)",
     "cr": "Floor plans traced from The Architectural Forum, July 1928 (public domain; scan: Boston Public Library via Internet Archive)."},
    {"id": "osm", "t": "OpenStreetMap way 28533972: Philadelphia Museum of Art main building footprint", "u": "https://www.openstreetmap.org/way/28533972", "k": "open-data",
     "lic": "ODbL 1.0 (c) OpenStreetMap contributors: attribute; a published derived database stays ODbL", "n": "Exterior shell outline; the 1928 plates are registered to it (residuals 2-4 m, 7-10 m on the west faces)",
     "cr": "Building footprint (c) OpenStreetMap contributors, ODbL 1.0 (openstreetmap.org/copyright)."},
    {"id": "pma-map", "t": "PMA visitor map (levels G, 1, 2, 3)", "u": "https://www.philamuseum.org/visit/museum-map", "k": "visitor-map",
     "lic": "(c) Philadelphia Museum of Art: facts only (gallery numbers, levels, collection areas, entrance labels); nothing traced, copied or redistributed",
     "n": "Candidate gallery numbers come from where its label points fall in the traced rooms (the map is schematic, ~10-27% stretched)",
     "cr": "Gallery numbers and collection areas: PMA visitor map (facts only; the map itself is not reproduced)."},
    {"id": "pma-events", "t": "PMA Special Events floor plans, Oct 2018 (Great Stair Hall, balcony, cloister zone, East Terrace)", "u": "https://legacyweb.philamuseum.org/doc_downloads/floorplan/UpdatedFloorPlans_Oct2018.pdf",
     "k": "official-plan", "lic": "(c) Philadelphia Museum of Art: published dimensions read as facts; nothing traced or redistributed",
     "n": "Great Stair Hall 95'7 1/8\" x 95'8 9/16\"; balcony 96'2\" x 113'11 1/4\"; cloister zone 46'11 1/2\" x 86'9 3/8\"; East Terrace 230.619 x 226.831 ft",
     "cr": "Published room dimensions: PMA event floor plans (2018) and press releases (facts only)."},
    {"id": "pma-press", "t": "PMA press release 2021: Core Project galleries and public spaces; Architectural Record 2021", "u": "https://press.philamuseum.org/new-galleries-and-public-spaces-in-major-renovation-and-interior-expansion-of-landmark-main-building/",
     "k": "official-plan", "lic": "(c) Philadelphia Museum of Art / BNP Media: published figures read as facts",
     "n": "Williams Forum 45 x 85 x 40 ft, Kasota stone; Vaulted Walkway 640 ft, ~24 ft, Guastavino; Lenfest Hall 69'6\" x 49'9\"; Kasota limestone exterior",
     "cr": "Forum, walkway and Lenfest Hall figures: PMA press release 2021 (facts only)."},
    {"id": "pma-libguide", "t": "PMA library guide: period rooms and architectural installations", "u": "https://philamuseum.libguides.com/period-rooms", "k": "official-plan",
     "lic": "(c) Philadelphia Museum of Art: gallery numbers and installation names read as facts", "n": "About 45 period rooms / installations with their gallery numbers",
     "cr": "Period-room gallery numbers: PMA library guide (facts only)."},
    {"id": "usgs", "t": "USGS 3DEP bare-earth elevation points around the building", "u": "https://epqs.nationalmap.gov/v1/json", "k": "open-data", "lic": "US government work, public domain",
     "n": "East Terrace ~26.7 m and Eakins Oval ~15.2 m NAVD88: used only to size the terrace and steps", "cr": "Grade: USGS 3DEP (public domain)."},
    {"id": "photos", "t": "Wikimedia Commons photographs of the Great Stair Hall (viewed for height and material estimates only)", "u": "https://commons.wikimedia.org/wiki/File:Escalera_Philadelphia_Museum_of_Art_01.JPG",
     "k": "photo", "lic": "CC BY-SA 4.0 / CC BY-SA 2.0 / CC BY 3.0: viewed, not redistributed", "n": "Ashlar limestone walls, Ionic colonnade at the balcony, coffered skylit ceiling; hall height 17-20 m estimated from proportions"},
    {"id": "est", "t": "Assumed values (ceiling and opening heights, floor elevations, unmeasured widths, steps)", "k": "estimate", "lic": "n/a",
     "n": "Typed defaults, each marked confidence 0-1 with its basis in the element's bs / hb field"},
]


# ── small helpers ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def centre(poly):
    x0, y0, x1, y1 = bbox(poly)
    return [(x0 + x1) / 2, (y0 + y1) / 2]


def overlap_area(a, b):
    ax0, ay0, ax1, ay1 = bbox(a); bx0, by0, bx1, by1 = bbox(b)
    w = min(ax1, bx1) - max(ax0, bx0); h = min(ay1, by1) - max(ay0, by0)
    return max(0, w) * max(0, h)


def level_of(pid):
    return pid.split("-", 1)[0]


def parse_guide(text):
    """gallery number -> {area id, area, level, name} from gallery_guide.md section 5 (index) and section 2 (named galleries)."""
    out, level = {}, None
    for line in text.splitlines():
        m = re.match(r"### Level (\w+)", line)
        if m:
            level = m.group(1); continue
        m = re.match(r"- ([0-9a-zA-Z]+): (.+?)(?: - (.+))?$", line)
        if m and level:
            num, area, nm = m.group(1), m.group(2).strip(), m.group(3)
            if area in ("Special Exhibitions",) or area in AREA_BY_GUIDE:
                out[num] = {"area": AREA_BY_GUIDE.get(area), "level": level, "name": nm}
    names = {}
    for line in text.splitlines():
        m = re.match(r"\| (\w+) \| (\w+) \| (.+?) \| (.+?) \|$", line)
        if m and m.group(1) in out and "LibGuide" in m.group(4):
            names[m.group(1)] = m.group(3).split(":")[0].strip()
    nm_over = {"219": "Bok House music room fireplace and doorway", "213": "Newman Gallery (North Family Dwelling elements)"}
    names.update(nm_over)
    return out, names


def seg_point(w, a):
    """the point a metres along wall w's polyline."""
    pts = w["p"] + ([w["p"][0]] if w.get("loop") else [])
    run = 0
    for p, q in zip(pts, pts[1:]):
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        if run + L >= a - 1e-9 and L > 0:
            t = (a - run) / L
            return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]
        run += L
    return pts[-1]


def pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy), t


# ── build ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def build(src: Path, art_manifest: dict) -> dict:
    tr = src / "traced"
    P = {L: json.loads((tr / f"plan_{L}.json").read_text()) for L in ("L1", "L2", "L3")}
    N = {L: json.loads((tr / f"{L}.json").read_text()) for L in ("L1", "L2", "L3")}
    D = json.loads((src / "pma_building.json").read_text())
    guide, inst_names = parse_guide((src / "gallery_guide.md").read_text())
    nrm = {}                                              # plan room id -> neutral room
    for L in N:
        for r in N[L]["rooms"]:
            nrm[f"{L.lower()}-{r['id']}"] = r

    plan = {"v": 1, "id": "pma", "name": "Philadelphia Museum of Art - Main Building", "kind": "museum", "c": 1,
            "geo": {"lat": 39.9656001, "lon": -75.1809999, "north": 44},
            "n": ("Levels follow the PMA visitor map: G, 1, 2, 3. The 1928 Architectural Forum sheets map to them as basement = level 1, first floor = level 2 (Great Stair Hall), second floor = level 3; "
                  "level G (Vaulted Walkway, Williams Forum) is not on the 1928 plates. Rooms drawn from the 1928 plans keep that layout: x28 says how much has changed since. "
                  "Metres; x east, y north (plan north is true bearing 44 degrees)."),
            "src": [dict(s) for s in SRC], "ca": [{"id": i, "n": n, "c": c} for i, n, c in AREAS]}
    plan["lv"] = [
        {"id": "g", "n": "Ground Level (G): Vaulted Walkway and Williams Forum", "lb": "G", "e": 0, "h": 6.2, "c": 1, "s": ["pma-press", "est"], "eb": "datum: Forum floor is at street level (PMA press 2021, Architectural Record 2021); walkway/Forum extents from published dimensions, positions scaled", "ec": 3},
        {"id": "l1", "n": "Level 1 (1928 basement; West Entrance and Lenfest Hall)", "lb": "1", "e": 6.2, "h": 6.3, "c": 1, "s": ["est"], "eb": "assumed midway between G and level 2", "ec": 1},
        {"id": "l2", "n": "Level 2 (1928 first floor; Great Stair Hall and East Entrance)", "lb": "2", "e": 12.5, "h": 6.6, "c": 2, "s": ["pma-press", "est"], "eb": "derived: Forum is 12.19 m high and rises 'to just below the Great Stair Hall floor' (PMA press 2021)", "ec": 2},
        {"id": "l3", "n": "Level 3 (1928 second floor; Great Stair Hall Balcony)", "lb": "3", "e": 19.1, "h": 6.6, "c": 1, "s": ["est", "photos"], "eb": "assumed level 2 + 6.6 m from balcony colonnade proportions in photographs", "ec": 1},
    ]
    elev = {lv["id"]: lv["e"] for lv in plan["lv"]}

    # ── rooms ──
    rooms, walls, stairs, cols, ents = [], [], [], [], []
    dropped = {"l2-c-main", "l3-c-main"}                  # replaced by the published-dimension Great Stair Hall rooms
    for L in ("L1", "L2", "L3"):
        walls += P[L]["wl"]
        cols += P[L].get("cols", [])
        stairs += P[L].get("st", [])
        ents += P[L].get("en", [])
        for r in P[L]["rm"]:
            if r["id"] in dropped:
                continue
            rooms.append(dict(r))
    taken = {}
    for r in rooms:
        nr = nrm.get(r["id"]) or {}
        r.pop("no", None)                                  # the tracer's own numbers are re-decided below
        label = nr.get("name") or r.get("n") or r["id"]
        r["n28"] = label
        r["x28"] = nr.get("changed_since_1928", "likely")
        if nr.get("changed_note"):
            r["nt"] = nr["changed_note"]
        cands = [t["gallery"] for t in nr.get("today", [])]
        kinds = {guide[c]["area"] for c in cands if c in guide}
        number = None
        reason = None
        if r["id"] in CONFLICTS:
            reason = CONFLICTS[r["id"]]
        elif nr.get("today_match") == "unique" and nr.get("today_conf") == "medium" and r.get("ty") in NUMBER_TYPES and len(cands) == 1:
            number = cands[0]
        if number:
            if number in taken:
                number, reason = None, f"number {taken[number]} also matched"
            else:
                taken[number] = r["id"]
        if number:
            g = guide.get(number, {})
            nm = inst_names.get(number)
            r["no"] = number
            r["n"] = nm or f"Gallery {number}"
            r["ca"] = g.get("area")
            r["gm"] = "tracer-unique"
            if nm and re.search(r"panel|room|salon|drawing room|kitchen|bedroom|cubiculum|interior", nm, re.I):
                r["wm"] = "wood"; r["mb"] = "evidenced: period-room installation (PMA library guide); floor and ceiling assumed"
            elif nm and re.search(r"cloister|portal|gothic|romanesque|temple|court", nm, re.I):
                r["wm"] = "stone"; r["mb"] = "evidenced: architectural installation (PMA library guide); floor and ceiling assumed"
        else:
            r["n"] = label if r.get("ty") not in ("gallery", "court") else label + " (1928)"
            if kinds and len(kinds) == 1 and None not in kinds:
                r["ca"] = next(iter(kinds))
        if cands and not number:
            r["cand"] = cands
            if reason:
                r["gm"] = "left-unnumbered: " + reason
            elif nr.get("today_match") in ("ambiguous", "unique-but-size-mismatch", "unique"):
                r["gm"] = "left-unnumbered: " + {"ambiguous": "several schematic-map label points in or near the room", "unique-but-size-mismatch": "label point inside but room size outside 0.4-2.5x",
                                                    "unique": "1928 room type is not a gallery"}[nr["today_match"]]
        r.setdefault("hb", "assumed-type")
        r["hc"] = 1
        r["bs"] = "ceiling height is a typed default (plates carry no vertical data)"
        r.setdefault("fm", "wood"); r.setdefault("wm", "paint"); r.setdefault("cm", "plaster")
        if "mb" not in r:
            r["mb"] = "assumed: neutral gallery finishes"
        if r["id"].startswith("l3-") and r.get("ty") in ("gallery",):
            r["li"] = {"k": "mixed"}

    # the cloister (evidence): a measured overlay on the traced colonnade
    s28 = next(r for r in rooms if r["id"] == CLOISTER_ROOM)
    ring = [c["p"] for c in cols if c["l"] == "l3" and bs.inside(s28["p"], c["p"])]
    cx = (min(p[0] for p in ring) + max(p[0] for p in ring)) / 2; cy = (min(p[1] for p in ring) + max(p[1] for p in ring)) / 2
    s28["n"] = "Romanesque Cloister hall (1928 no. 28)"
    s28["gm"] = "left-unnumbered: the cloister itself is the overlay room l3-sg-cloister"

    gsh_pd = {"ns": 29.14, "ew": 29.17, "u": "PMA event floor plan 2018: 95'7 1/8\" x 95'8 9/16\""}
    gsh_c = [{"id": "l2-gsh", "l": "l2", "n": "Great Stair Hall", "ty": "stair-hall", "p": rect(-36.7, -11.9, -7.5, 17.2), "ch": 17, "c": 2, "s": ["pma-events", "af1928", "photos"],
              "fm": "stone", "wm": "limestone", "cm": "plaster", "li": {"k": "sky"}, "hb": "photo-estimate 17-20 m (low); coffered skylit ceiling", "hc": 1, "mb": "evidenced: ashlar limestone walls, stone floor, coffered plaster ceiling with skylights (photographs; Architectural Record 2021 for Kasota)",
              "pd": gsh_pd, "x28": "no", "nt": "Published 29.14 x 29.17 m; the 1928 hall traced 29.15 x 27.3 m (29.4 m with the west landing). Walls stay as traced.", "n28": "Main Hall",
              "bs": "published size; position registered to the traced hall (+-1 m); height photo-estimated"},
             {"id": "l3-gsh-balcony", "l": "l3", "n": "Great Stair Hall Balcony", "ty": "stair-hall", "p": rect(-41.0, -12.0, -6.3, 17.3), "ch": 10.4, "c": 1, "s": ["pma-events", "af1928", "photos"],
              "fm": "stone", "wm": "limestone", "cm": "plaster", "li": {"k": "sky"}, "hb": "ceiling at the hall's photo-estimated 29.5 m absolute (level 2 floor + 17 m)", "hc": 1, "mb": "evidenced: ashlar limestone walls, Ionic colonnade (photographs)",
              "pd": {"ns": 29.31, "ew": 34.73, "u": "PMA event floor plan 2018"}, "x28": "no", "n28": "Main Hall (balcony level)",
              "nt": "Published 29.31 x 34.73 m; placement of the west edge is +-3 m.", "bs": "published size, estimated placement"},
             {"id": "l1-lenfest", "l": "l1", "n": "Lenfest Hall", "ty": "lobby", "p": rect(-70.0, -7.9, -54.8, 13.2), "ch": 12.2, "c": 1, "s": ["pma-press", "est"], "fm": "stone", "wm": "limestone", "cm": "plaster",
              "hb": "assumed double height (PMA: twin balconies at level 2)", "hc": 1, "mb": "assumed: finishes unrecorded (Tiffany doors restored, PMA press)", "ov": 1, "x28": "new",
              "pd": {"ns": 21.18, "ew": 15.16, "u": "PMA press 2021: 69'6\" x 49'9\""}, "nt": "Modern West Entrance hall (2021), measured size, scaled position (+-2 m). The 1928 foyer stood further east.", "bs": "published size, estimated placement"},
             {"id": "l3-sg-cloister", "l": "l3", "n": "Cloister from Saint-Genis-des-Fontaines", "no": "304", "ty": "court", "p": rect(cx - 7.155, cy - 7.35, cx + 7.155, cy + 7.35), "ch": 10, "c": 2, "s": ["pma-events", "af1928", "pma-libguide"],
              "fm": "stone", "wm": "stone", "cm": "plaster", "ca": "eu1100", "hb": "assumed (court hall type default)", "hc": 1, "mb": "evidenced: cloister of carved stone (PMA library guide); floor assumed",
              "ov": 1, "x28": "partly", "gm": "resolved-by-evidence", "pd": {"ew": 14.31, "ns_zone": 26.45, "u": "PMA event plan 2018: cloister zone 46'11 1/2\" x 86'9 3/8\" includes the Saint-Laurent gallery"},
              "nt": "Cloister installed 1928 (Romanesque Cloister, no. 28), today Gallery 304 per the PMA library guide; traced colonnade 14.8 x 14.7 m vs published 14.31 m.", "bs": "published width on the traced colonnade ring"}]
    rooms += gsh_c

    # ── level G (not on the 1928 plates): published figures only ──
    WX, WW = -26.0, 6.1                                   # walkway centre line x (v), width: assumed
    g_rooms = [
        ("g-walk-s", "Vaulted Walkway (south)", "hall", rect(WX - WW / 2, -83.4, WX + WW / 2, -4.2), 7.32),
        ("g-walk-n", "Vaulted Walkway (north)", "hall", rect(WX - WW / 2, 9.5, WX + WW / 2, 85.9), 7.32),
        ("g-forum", "Williams Forum", "hall", rect(-34.5, -4.2, -8.6, 9.5), 12.19),
        ("g-south-hall", "South Hall", "hall", rect(-36.7, -97.4, -19.1, -83.4), 7.32),
        ("g-north-hall", "North Hall and Entrance", "lobby", rect(-45.5, 85.9, -19.1, 97.67), 7.32),
        ("g-learning", "Learning and Engagement Center", "classroom", rect(-38.8, 64.9, -29.6, 85.6), 3.8),
    ]
    for rid, nm, ty, poly, ch in g_rooms:
        r = {"id": rid, "l": "g", "n": nm, "ty": ty, "p": poly, "ch": ch, "c": 1, "s": ["pma-press", "pma-map", "est"], "x28": "new", "ov": 1,
             "hc": 2 if rid in ("g-forum", "g-walk-s", "g-walk-n") else 1, "fm": "stone", "wm": "limestone", "cm": "plaster", "li": {"k": "day"} if rid == "g-forum" else {"k": "art"}}
        if rid in ("g-walk-s", "g-walk-n"):
            r.update(cm="terracotta", hb="published: ~24 ft (PMA press 2021)", mb="evidenced: Guastavino tile vault, stone pavers (PMA press 2021)", bs="length/height published (640 ft total, ~24 ft); width and lateral position assumed",
                     nt="The vault runs 195.07 m from South Hall to the North Entrance, interrupted by the Forum.")
        elif rid == "g-forum":
            r.update(hb="published: 40 ft = 12.19 m (PMA press 2021)", mb="evidenced: Kasota stone floor and cladding, curved plaster ceiling (PMA press 2021)", pd={"ns": 13.72, "ew": 25.91, "h": 12.19, "u": "PMA press 2021: 45 x 85 x 40 ft"},
                     bs="published size and height; position scaled from the schematic G-level map (+-2 m)", ca="sculpt", cm="plaster", nt="Rises from G to just below the Great Stair Hall floor; created 2021 where the Van Pelt Auditorium stood.")
        else:
            r.update(hb="assumed-type", mb="assumed: neutral finishes", bs="outline from the schematic G-level map (published dims for South Hall: 12.04 x 6.55 / 9.14 m)", c=0 if rid in ("g-north-hall", "g-learning") else 1)
            if rid == "g-learning":
                r["ca"] = "learn"
        rooms.append(r)

    # ── walls for G: a closed wall round each room, a gap wherever two rooms share an edge ──
    def edge_overlap(a0, a1, b0, b1):
        lo, hi = max(min(a0, a1), min(b0, b1)), min(max(a0, a1), max(b0, b1))
        return (lo, hi) if hi - lo > 0.5 else None
    gr = {r[0]: r for r in g_rooms}
    for rid, nm, ty, poly, ch in g_rooms:
        x0, y0, x1, y1 = bbox(poly)
        w = {"id": rid.replace("g-", "g-w-"), "l": "g", "p": poly, "loop": True, "t": 0.9, "m": "limestone", "k": "int", "h": min(ch, 12.19), "c": 1, "s": ["pma-press", "est"], "o": []}
        per = [(x1 - x0), (y1 - y0), (x1 - x0), (y1 - y0)]
        starts = [0, per[0], per[0] + per[1], 2 * per[0] + per[1]]
        for oid, onm, oty, opoly, och in g_rooms:
            if oid == rid:
                continue
            ox0, oy0, ox1, oy1_ = bbox(opoly)
            for side in range(4):
                # side 0: bottom (y=y0, x0->x1); 1: right (x=x1, y0->y1); 2: top (y=y1, x1->x0); 3: left (x=x0, y1->y0)
                if side == 0 and abs(oy1_ - y0) < 0.3 and (ov := edge_overlap(x0, x1, ox0, ox1)):
                    a = starts[0] + ((ov[0] + ov[1]) / 2 - x0)
                elif side == 2 and abs(oy0 - y1) < 0.3 and (ov := edge_overlap(x0, x1, ox0, ox1)):
                    a = starts[2] + (x1 - (ov[0] + ov[1]) / 2)
                elif side == 1 and abs(ox0 - x1) < 0.3 and (ov := edge_overlap(y0, y1, oy0, oy1_)):
                    a = starts[1] + ((ov[0] + ov[1]) / 2 - y0)
                elif side == 3 and abs(ox1 - x0) < 0.3 and (ov := edge_overlap(y0, y1, oy0, oy1_)):
                    a = starts[3] + (y1 - (ov[0] + ov[1]) / 2)
                else:
                    continue
                width = min(ov[1] - ov[0], 6.5)
                w["o"].append({"k": "gap", "a": round(a, 2), "w": round(width, 2), "h": min(ch, 7.0) - 0.3, "c": 1})
        walls.append(w)
    # the Forum is a passage across the walkway; the end halls open onto it: gaps where walkway halves meet halls come from the shared edges above

    # ── stairs: stitch each link to its upper footprint ──
    nst = {}
    for L in N:
        for s in N[L]["stairs"]:
            nst[(L.lower(), s["id"], s["frm"].lower())] = s
    sp = {"gsh-stair": "gsh-stair-up"}
    for s in stairs:
        base = s["id"].split("-", 1)[1]
        frm, to = s["from"], s["to"]
        cand = nst.get((to, sp.get(base, base), frm)) or nst.get((to, base, frm))
        if cand and cand["frm"].lower() == frm:
            s["tp"] = [[p[1], p[0]] for p in cand["fp"]]; s["tb"] = "traced: matching footprint on the upper plate"
        else:
            s["tp"] = [list(p) for p in s["fp"]]; s["tb"] = "assumed: stacked above the lower footprint (no matching footprint traced)"
            s["c"] = min(s.get("c", 1), 0)
        s["dz"] = round(elev[to] - elev[frm], 2)
        s["lb"] = None
    # a link whose upper end was not traced and lands where its level has no room (the 1928 basement had no north wing) leads nowhere: dropped, noted in the README
    def lands(s):
        if s["tb"].startswith("traced"):
            return True
        cx_, cy_ = centre(s["tp"])
        return any(r["l"] == s["to"] and bs.inside(r["p"], [cx_, cy_]) for r in rooms)
    dropped_links = [s["id"] for s in stairs if not lands(s)]
    stairs[:] = [s for s in stairs if s["id"] not in dropped_links]
    stairs.append({"id": "g-forum-stair", "k": "stair", "from": "g", "to": "l1", "fp": rect(-20.0, 5.2, -16.0, 9.2), "tp": rect(-20.0, 5.2, -16.0, 9.2), "w": 1.8, "up": 90, "c": 0,
                   "s": ["pma-press"], "tb": "assumed: PMA press names a cantilevered stair in the Forum (G to level 1); its position is a guess", "dz": 6.2})

    # ── entrances ──
    for e in ents:
        if e["id"] == "l1-west":
            e["n"] = "West vestibule door of the 1928 plan"; e["k"] = "side"
    en = [e for e in ents]
    en += [
        {"id": "west", "n": "West Entrance (Toll Terrace, accessible; most visitors enter here)", "l": "l1", "p": [-74.2, 2.65], "fc": 180, "w": 4.5, "k": "main", "c": 1, "s": ["pma-map", "osm"]},
        {"id": "north", "n": "North Entrance (Kelly Drive side, accessible)", "l": "g", "p": [-32.3, 97.67], "fc": 90, "w": 6.0, "k": "accessible", "c": 0, "s": ["pma-map", "pma-press"]},
        {"id": "south", "n": "South Hall (original south entrance)", "l": "g", "p": [-27.9, -97.4], "fc": 270, "w": 6.0, "k": "side", "c": 1, "s": ["pma-map", "pma-press"]},
    ]
    for e in en:
        if e["id"] == "l2-east":
            e["n"] = "East Entrance (Rocky Steps and Parkway side)"

    # ── exterior ──
    foot = [[v, u] for u, v in D["footprint"]["polygon_uv_m"]]          # (x = v, y = u)
    terr = D["major_spaces"][next(i for i, m in enumerate(D["major_spaces"]) if m["id"] == "east_terrace")]["polygon_uv_m"]
    tx0, tx1 = terr[0][1], terr[2][1]; ty0, ty1 = terr[0][0], terr[1][0]   # polygon_uv: [u, v]
    TZ = 11.2
    sw = 21.3
    yc = 2.65
    steps, landings = [], []
    x = tx1                                              # the top of the steps: the plaza's east edge
    flights = [13, 13, 13, 13, 13, 7]                      # from the top down; 7 + 5 x 13 = 72, the 7-step flight at the foot is an assumption
    riser, tread, ld = 5 * IN, 15 * IN, 3.05
    z = TZ
    for i, n in enumerate(flights):
        run = n * tread
        steps.append({"id": f"rocky-{i + 1}", "p": rect(x, yc - sw / 2, x + run, yc + sw / 2), "z0": round(z - n * riser, 3), "z1": round(z, 3), "n": n, "up": 180, "c": 0, "s": ["est"]})
        x += run; z -= n * riser
        if i < len(flights) - 1:
            landings.append({"id": f"rocky-landing-{i + 1}", "p": rect(x, yc - sw / 2, x + ld, yc + sw / 2), "z": round(z, 3), "m": "granite", "n": f"Rocky Steps landing {i + 1}", "c": 0, "s": ["est"]})
            x += ld
    rocky_len = x - tx1
    ex = {"gz": round(z, 2),
          "sh": [{"id": "main", "p": foot, "h": 25.7, "rf": {"k": "hip", "h": 4.0}, "m": "limestone", "z": 0, "c": 2, "s": ["osm", "af1928"], "bs": "OSM outline (+-1 m); eave = level 3 floor + storey height; roof form assumed (low pitch, skylights); Kasota limestone"}],
          "stp": steps + [{"id": "east-stair", "p": rect(tx0 - 2.7, 2.65 - 6.5, tx0, 2.65 + 6.5), "z0": TZ, "z1": 12.5, "n": 7, "up": 180, "c": 0, "s": ["pma-events", "est"]}],
          "tr": [{"id": "east-terrace", "p": [[tx0, ty0], [tx1, ty0], [tx1, ty1], [tx0, ty1]], "z": TZ, "m": "granite", "n": "East Terrace (230.6 x 226.8 ft; Phillips Fountain at its centre)", "c": 2, "s": ["pma-events", "usgs"],
                 "bs": "published size, position scaled from the events plan; height assumed from grade (USGS 3DEP)"},
                {"id": "east-landing", "p": rect(-3.0, 2.65 - 6.5, tx0 - 2.7, 2.65 + 6.5), "z": 12.5, "m": "granite", "n": "East Entrance landing", "c": 0, "s": ["pma-events", "est"]}] + landings}
    plan["ex"] = ex
    rk = {"len_m": round(rocky_len, 1), "steps": sum(flights), "flights": flights}

    # ── fixtures: Diana and her plinth ──
    fx = [{"id": "gsh-diana-plinth", "l": "l3", "k": "plinth", "p": [-36.2, 2.65], "rot": 0, "sz": [2.0, 2.0, 1.1], "m": "stone", "n": "Plinth of Diana", "c": 1, "s": ["photos", "est"], "bs": "plinth height assumed"},
          {"id": "gsh-diana", "l": "l3", "k": "statue", "p": [-36.2, 2.65], "rot": 0, "sz": [1.8, 1.8, 4.42], "m": "gilt", "n": "Diana, Augustus Saint-Gaudens (1892-93), 14 ft 6 in", "c": 1, "s": ["photos", "pma-map"],
           "bs": "height 14 ft 6 in as given in the brief for this plan (not independently found); plan position from the visitor-map icon; the landing level is not confirmed"}]

    # an opening that touches no room boundary (within 3 m) and not the shell leads nowhere: dropped (these were aisle and box doors inside the traced 1928 auditorium)
    byl = {}
    for r in rooms:
        if not r.get("ov"):
            byl.setdefault(r["l"], []).append(r["p"])
    pruned = 0
    for w in walls:
        keep = []
        for o in w.get("o", []):
            if o["k"] == "window":
                keep.append(o); continue
            pt = seg_point(w, o["a"])
            if any(bs.dist_to_edge(rp, pt) <= 3.0 for rp in byl.get(w["l"], [])) or bs.dist_to_edge(foot, pt) <= 3.0:
                keep.append(o)
            else:
                pruned += 1
        w["o"] = keep
    plan["rm"] = rooms
    plan["wl"] = walls
    plan["st"] = [{k: v for k, v in s.items() if v is not None} for s in stairs]
    plan["cols"] = cols
    plan["fx"] = fx
    plan["en"] = en

    plan["sl"], unplaced = art_slots(plan, guide, inst_names, nrm, art_manifest)
    plan["tour"] = make_tour(plan)
    plan["src"] = credit_sources(plan, art_manifest)
    return plan, {"rocky": rk, "unplaced_works": unplaced, "pruned_openings": pruned, "dropped_links": dropped_links}


# ── art slots ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

WORKS = [
    # gallery, id, title, artist, date, credit, pma object id, size m (w, h), size source, al, image key, note
    ("104", "peale-yarrow-mamout", "Portrait of Yarrow Mamout (Muhammad Yaro)", "Charles Willson Peale", "1819", "Philadelphia Museum of Art, accession 2011-87-1", "319114", (0.508, 0.61), "24 x 20 in; PMA accession 2011-87-1 (via Wikipedia)", ["painting"], "peale"),
    ("211", "tanner-annunciation", "The Annunciation", "Henry Ossawa Tanner", "1898", "Philadelphia Museum of Art, purchased 1899 (W1899-1-1)", "104384", (1.81, 1.448), "57 x 71 1/4 in", ["painting"], "tanner"),
    ("261", "monet-japanese-footbridge", "Japanese Footbridge, Giverny", "Claude Monet", "1895", "Philadelphia Museum of Art, gift of F. Otto Haas, 1993-151-2", "87535", (0.978, 0.787), "78.7 x 97.8 cm (PMA record via Commons)", ["painting"], "monet"),
    ("306", "van-der-weyden-crucifixion", "The Crucifixion, with the Virgin and Saint John the Evangelist Mourning", "Rogier van der Weyden", "c. 1460", "Philadelphia Museum of Art, John G. Johnson Collection", "102845", (1.864, 1.803), "two panels, overall 180.3 x 186.4 cm", ["painting"], "weyden"),
    ("364", "leyster-last-drop", "The Last Drop (The Gay Cavalier)", "Judith Leyster", "c. 1629", "Philadelphia Museum of Art, John G. Johnson Collection, 1917", "102220", (0.735, 0.891), "35 1/16 x 28 15/16 in (89.1 x 73.5 cm)", ["painting"], None),
    ("273", "rivera-sugar-cane", "Sugar Cane", "Diego Rivera", "1931", "Philadelphia Museum of Art, gift of Mr. and Mrs. Herbert Cameron Morris, 1943-46-2", "48441", (2.39, 1.45), "about 57 x 94 in (fresco on cement in a steel frame)", ["painting", "relief"], None),
    ("100", "wampum-belt", "Lenape Wampum Belt", "Lenape women artists (likely)", "c. 1682", "Loan, Historical Society of Pennsylvania / Atwater Kent collections", None, (0.7, 0.2), "assumed (belt reported ~26 in long)", ["textile", "object"], None),
    ("347", "horse-armor-von-worms", "Horse Armor", "Wilhelm von Worms", "1507", "Philadelphia Museum of Art", "309965", (1.2, 2.2), "assumed (object size not recorded here)", ["object", "sculpture"], None),
    ("347", "man-armor-deutsch", "Field Armor", "Matthes Deutsch", "c. 1505", "Philadelphia Museum of Art", "308827", (0.8, 1.9), "assumed (object size not recorded here)", ["object", "sculpture"], None),
]
MAP_URL = "https://www.philamuseum.org/visit/museum-map"
LIBGUIDE = "https://philamuseum.libguides.com/period-rooms"
CONSTANTINE = "https://philamuseum.org/collection/curated/constantine-tapestries"


def art_slots(plan, guide, inst_names, nrm, art_manifest):
    rooms = {r["id"]: r for r in plan["rm"]}
    walls_by_level = {}
    for w in plan["wl"]:
        walls_by_level.setdefault(w["l"], []).append(w)

    def room_for_gallery(num):
        for r in plan["rm"]:
            if r.get("no") == num:
                return r["id"], "room"
        best = None
        for rid, nr in nrm.items():
            if rid not in rooms:
                continue
            for t in nr.get("today", []):
                if t["gallery"] == num and t["how"].startswith("label point inside") and rooms[rid].get("ty") in ("gallery", "court", "corridor"):
                    best = (rid, "cand")
        return best

    # wall positions per room
    cursor = {}

    def positions(room, w, need=1):
        poly = room["p"]
        ccw = bs.area(poly) > 0
        out = []
        edges = []
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L >= max(1.6, w + 0.5):
                edges.append((L, a, b))
        edges.sort(key=lambda e: -e[0])
        wl = walls_by_level.get(room["l"], [])
        blocked = []
        for ww in wl:
            for o in ww.get("o", []):
                c = seg_point(ww, o["a"])
                blocked.append((c, o["w"] / 2 + 0.35))
        for L, a, b in edges:
            dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            nx, ny = (-dy, dx) if ccw else (dy, -dx)           # into the room
            step = w + 1.2
            k = max(1, int((L - 1.0) // step))
            for j in range(k):
                t = (L - (k - 1) * step) / 2 + j * step
                p = [a[0] + dx * t, a[1] + dy * t]
                if any(math.hypot(p[0] - c[0], p[1] - c[1]) < r + w / 2 for c, r in blocked):
                    continue
                out.append(((p[0] + nx * 0.05, p[1] + ny * 0.05), math.degrees(math.atan2(ny, nx)) % 360))
        # order: centre-of-longest-edge first, then spread
        return out

    def wall_for(room, p):
        best, bd = None, 1e9
        for ww in walls_by_level.get(room["l"], []):
            pts = ww["p"] + ([ww["p"][0]] if ww.get("loop") else [])
            for a, b in zip(pts, pts[1:]):
                d, _ = pt_seg(p, a, b)
                if d < bd:
                    bd, best = d, ww["id"]
        return best if bd <= 1.1 else None

    slots, unplaced = [], []
    used = {}

    def place(sid, rid, kind, sz, z, al, work, extra=None, wall_ok=True):
        room = rooms[rid]
        pos = used.setdefault(rid, {"i": 0, "list": positions(room, sz[0])})
        if pos["i"] >= len(pos["list"]):
            return False
        p, fc = pos["list"][pos["i"]]; pos["i"] += 1
        s = {"id": sid, "rm": rid, "p": [round(p[0], 2), round(p[1], 2)], "z": z, "sz": list(sz), "fc": round(fc, 1), "al": al, "work": work, "pc": kind, "c": 1 if kind == "room" else 0, "s": ["pma-map", "est"]}
        wid = wall_for(room, p)
        if wid:
            s["w"] = wid
        if extra:
            s.update(extra)
        slots.append(s)
        return True

    img_url = {k: v["url"] for k, v in (art_manifest.get("images") or {}).items()}
    # named works with a confirmed gallery number
    placed_gal = set()
    for gal, wid, title, artist, date, credit, oid, sz, szsrc, al, imgk in WORKS:
        hit = room_for_gallery(gal)
        if not hit:
            unplaced.append({"work": title, "gallery": gal, "why": "no traced room contains this gallery's label point"})
            continue
        rid, kind = hit
        work = {"title": title, "artist": artist, "date": date, "credit": credit,
                "pma_url": f"https://www.philamuseum.org/collection/object/{oid}" if oid else MAP_URL}
        if imgk and imgk in img_url:
            work["img"] = img_url[imgk]
        ssrc = ["pma-map", "est"] + (["commons-art"] if work.get("img") else [])
        z = round(max(1.5, sz[1] / 2 + 0.35), 2)
        if place(f"sl-{wid}", rid, kind, sz, z, al, work, {"gl": gal, "sr": szsrc, "sb": "catalogued" if "assumed" not in szsrc else "assumed", "s": ssrc}):
            placed_gal.add(gal)
        else:
            unplaced.append({"work": title, "gallery": gal, "why": "no free wall position in the room"})
    # period rooms and installations: a title-card plaque in the room that holds or is the gallery
    for gal, nm in sorted(inst_names.items()):
        if gal in placed_gal:
            continue
        hit = room_for_gallery(gal)
        if not hit:
            continue
        rid, kind = hit
        work = {"title": nm, "artist": "", "date": "", "credit": "Installation or period room, Philadelphia Museum of Art (title card only; no image)", "pma_url": LIBGUIDE}
        place(f"sl-g{gal}", rid, kind, [0.6, 0.4], 1.5, ["text", "any"], work, {"gl": gal, "sr": "plaque size assumed", "sb": "assumed"})
    # the thirteen Constantine (Barberini) tapestries on the Great Stair Hall balcony
    room = rooms["l3-gsh-balcony"]
    pos = positions(room, 3.2)
    step = max(1, len(pos) // 13)
    chosen = pos[::step][:13]
    for i, (p, fc) in enumerate(chosen):
        work = {"title": f"The Story of Constantine, tapestry {i + 1} of 13", "artist": "Barberini workshop, Paris and Rome; designs by Rubens (7) and Pietro da Cortona (6)", "date": "1630s",
                "credit": "Philadelphia Museum of Art, gift of the Samuel H. Kress Foundation, 1959", "pma_url": CONSTANTINE}
        s = {"id": f"sl-const-{i + 1}", "rm": "l3-gsh-balcony", "p": [round(p[0], 2), round(p[1], 2)], "z": 4.8, "sz": [3.2, 4.6], "fc": round(fc, 1), "al": ["tapestry"], "work": work, "pc": "room", "c": 1,
             "s": ["pma-map", "est"], "gl": "Great Stair Hall Balcony", "sr": "tapestry size assumed (not found in the sources used)", "sb": "assumed"}
        wid = wall_for(room, p)
        if wid:
            s["w"] = wid
        slots.append(s)
    if len(chosen) < 13:
        unplaced.append({"work": "Constantine tapestries", "gallery": "balcony", "why": f"only {len(chosen)} of 13 wall positions free"})
    for w in [x for x in ("gross-clinic",)]:
        unplaced.append({"work": "The Gross Clinic (Eakins)", "gallery": "255 or 211", "why": "gallery conflict: the 2025 museum-map banner says 255, a current PMA page lists Gallery 211; no room placement claimed, image not hosted"})
    for w, why in (("Cezanne, The Large Bathers", "gallery number unconfirmed"), ("Van Gogh, Sunflowers", "gallery number unconfirmed"), ("Rubens, Prometheus Bound", "gallery number unconfirmed"),
                   ("Duchamp, The Large Glass", "PMA record says 'currently not on view'; copyright unclear: no placement, no image"), ("Brancusi / Calder / living artists", "rights: no images, no cards")):
        unplaced.append({"work": w, "gallery": "?", "why": why})
    return slots, unplaced


# ── tour ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def make_tour(plan):
    stations = ("gallery", "court", "hall", "stair-hall", "lobby", "auditorium", "library")
    byl = {}
    for r in plan["rm"]:
        if r.get("ty") in stations and abs(bs.area(r["p"])) >= 14 and not (r["id"] in ("l1-c-aud",) and False):
            byl.setdefault(r["l"], []).append(r)
    start = {"l2": "l2-gsh", "l3": "l3-gsh-balcony", "l1": "l1-lenfest", "g": "g-forum"}
    tour = []
    for lv in ("l2", "l3", "l1", "g"):
        rs = byl.get(lv, [])
        cur = next((r for r in rs if r["id"] == start[lv]), None)
        todo = [r for r in rs if r is not cur]
        order = [cur] if cur else []
        pos = centre(cur["p"]) if cur else [0, 0]
        while todo:
            nxt = min(todo, key=lambda r: math.hypot(centre(r["p"])[0] - pos[0], centre(r["p"])[1] - pos[1]))
            todo.remove(nxt); order.append(nxt); pos = centre(nxt["p"])
        tour += [r["id"] for r in order]
    return tour


def credit_sources(plan, art):
    srcs = plan["src"]
    imgs = (art or {}).get("images") or {}
    if imgs:
        lines = []
        for k, v in sorted(imgs.items()):
            lines.append(f"{v['title']} ({v['artist']}): {v['licence']}, {v['source_credit']}")
        srcs.append({"id": "commons-art", "t": "Wikimedia Commons reproductions of public-domain paintings (files listed in the art manifest)", "u": "https://commons.wikimedia.org/", "k": "photo",
                     "lic": "public domain (artists d. before 1956; faithful reproductions marked PD on Commons): per-file licences in the manifest", "n": "; ".join(lines),
                     "cr": "Painting images: Wikimedia Commons, public domain (" + "; ".join(f"{v['title'].split(',')[0].split(' (')[0]} - {v['source_credit']}" for v in imgs.values()) + ")."})
    used = set()
    def walk(o):
        if isinstance(o, dict):
            for s in o.get("s", []) if isinstance(o.get("s"), list) else []:
                used.add(s)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: v for k, v in plan.items() if k != "src"})
    return [s for s in srcs if s["id"] in used or s["id"] in ("commons-art",)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default=str(ROOT / "alto" / "buildings" / "pma_plan.json"))
    a = ap.parse_args()
    from alto.buildings import pma_art
    art = pma_art.manifest()
    plan, info = build(Path(a.src), art)
    warns = bs.validate_plan(plan)
    text = json.dumps(bs.normalize(plan), separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    Path(a.out).write_text(text, encoding="utf-8")
    print(json.dumps({"bytes": len(text), "warnings": len(warns), "info": info, "summary": bs.summary(plan)}, indent=1)[:3000])
    for w in warns[:40]:
        print(" warn:", w)


if __name__ == "__main__":
    main()
