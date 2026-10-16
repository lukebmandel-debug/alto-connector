"""Which transit lines a city draws: the families read from the OSM route relations (palace_map._transit), for ANY city.

A FAMILY is one line as a rider thinks of it: a trunk and its branches, one colour, one name (Philadelphia's
Market-Frankford Line; New York's 1 2 3 on the Broadway-Seventh Avenue trunk; Washington's Red Line). palace_map draws
each family once: its track is the union of its route relations' member ways inside the box, its branches are the stop
runs of its routes (in the relations' member order, which is ride order in OSM's public-transport schema).

Two ways to get the families, both in this module:

1. AUTO-DISCOVERY (`discover`), no preset needed. The rules, in order:
   a. A candidate is a route relation with route = subway | light_rail | tram | train | monorail (route=railway is
      infrastructure, not a service, and only names trunks, rule f), not "diverted"/"disused", not intercity
      (passenger = national | international, or service = long_distance | high_speed | night | international).
   b. Its KIND: subway/monorail -> "metro", train -> "rail", tram -> "tram", light_rail -> "tram" when at least 40% of its
      track in the box is street running (railway=tram ways, or embedded / street_running tags), else "metro".
      ("tram" lines are routed ON the drawn streets; "metro"/"rail" are grade separated: octilinear runs.)
   c. GROUPING: rail -> one family per network (Philadelphia's "Regional Rail", "NJ Transit", "MARC"); metro/tram ->
      one family per (network, kind, colour). A route with no colour joins the family of its network it shares the most
      track ways with, else it is a family of its own (by ref). A group whose routes share no track way and no stop name
      is split into its connected parts (New York's L and 42nd St Shuttle are both grey: two families).
      So NYC gets one family per trunk colour (1 2 3, 4 5 6, A C E, B D F M, N Q R W, J Z, L, S, 7), Washington one per
      Metro line (Red, Blue, Orange, Silver, Green, Yellow, which share trunks downtown: the page lanes them side by side),
      Boston Red / Orange / Blue / Green (B C D E are its branches) / Mattapan / Commuter Rail.
   d. BRANCHES ("routes" mode): each ref's longest stop run in the box is a branch; a run whose stops are all in another
      branch is dropped (express runs, the second direction, short turns). The family's ride is its longest branch then
      every other branch's new stops.
   e. A family with fewer than 2 named stops inside the box is not drawn (a line that only passes through, intercity
      trains calling once at the terminal, people movers with no stop positions).
   f. NAME: the routes' common line name (operator prefix and "A -> B" direction cut: "WMATA Red Line: Glenmont ->
      Shady Grove" -> "Red Line"); for several refs the trunk's name, from the route=railway relation that holds most of
      the family's track ("IRT Broadway-Seventh Avenue Line (1 2 3)"), else the network's name with the refs.
      COLOUR: the routes' colour tag (case folded), else a kind palette colour. ID: the refs ("123", "ace"), else the
      name, lower-case letters and digits, made unique.
2. PRESETS (`PRESETS`, `preset_for(place)`), a small data format a city preset (city setup, C1) fills:

       {"name": "New York", "places": ["new york", "manhattan", ...],   # place substrings that pick it (lower case)
        "families": [FAMILY, ...],     # explicit families, matched first, in this order
        "exclude": [MATCH, ...],       # routes never drawn
        "auto": True,                  # routes no family matched go to auto-discovery (rules above); False: dropped
        "override": {auto id: {"n"|"c"|"k"|"id": ...}},     # rename / recolour a discovered family
        "legacy": False}               # True: palace_map's 1.9.78 reader, byte for byte (Philadelphia)
       FAMILY = {"id", "n" (name), "c" (colour), "k" ("metro" | "tram" | "rail"), "match": MATCH or [MATCH, ...],
                 "branches": "routes" (rule d) | "longest" (one branch: the longest run) | "per_ref" (each ref's longest
                 run, none dropped), "end": stop-name prefix where a spur's runs stop (it joins its trunk there)}
       MATCH = {"route": str | [str], "network": str, "operator": str, "name": str,    # case-insensitive substrings
                "ref": [str] (exact), "colour": [str] (case folded)}                     # every given key must hold

   Philadelphia's 1.9.78 table is PHILADELPHIA here (legacy: its output is byte-identical, tests/test_city_transit.py).
   An empty place picks Philadelphia too (the engine's default city, as before).

A city with no preset gets rule 1 alone: its subway / light rail / tram / commuter-rail lines with names and colours from
OSM (see _qa/docs/C2.md for what that gives on Manhattan, Washington and Philadelphia).
"""
from __future__ import annotations

import math
import re

ROUTE_KINDS = ("subway", "light_rail", "tram", "train", "monorail")
INTERCITY_PASSENGER = ("national", "international")
INTERCITY_SERVICE = ("long_distance", "high_speed", "night", "international")
STREET_SHARE = 0.4            # light rail with this share of its track on the street is a tram
MIN_STOPS = 2                 # named stops in the box a discovered family needs
MIN_STOPS_RAIL = 3            # ... a discovered rail family (one or two calls in the box are an intercity train or a
                              # terminal, not a line of the city's own; a preset can still name such a line)
KIND_RANK = {"metro": 0, "tram": 1, "rail": 2}
PALETTE = {"metro": ("#1f6fb2", "#d9480f", "#2b8a3e", "#ae3ec9", "#e67700", "#0b7285", "#c2255c", "#5c940d"),
           "tram": ("#6ea516", "#0ca678", "#74b816"),
           "rail": ("#4c748c", "#6c5f8d", "#7b6a4d", "#486581")}

# ── presets ───────────────────────────────────────────────────────────────────────────────────────────────────────
PHILADELPHIA = {
    "name": "Philadelphia", "places": ["philadelphia"], "legacy": True, "auto": False,
    "families": [
        {"id": "mfl", "n": "Market–Frankford Line", "c": "#0097d6", "k": "metro", "branches": "longest",
         "match": {"network": "SEPTA", "route": "subway", "ref": ["L"]}},
        {"id": "bsl", "n": "Broad Street Line", "c": "#f58220", "k": "metro", "branches": "longest",
         "match": {"network": "SEPTA", "route": "subway", "ref": ["B1", "B2"]}},
        {"id": "brs", "n": "Broad–Ridge Spur", "c": "#f58220", "k": "metro", "branches": "longest", "end": "girard",
         "match": {"network": "SEPTA", "route": "subway", "ref": ["B3"]}},
        {"id": "trl", "n": "Subway-Surface Trolleys", "c": "#6ea516", "k": "tram", "branches": "per_ref",
         "match": {"network": "SEPTA", "route": "tram", "ref": ["T1", "T2", "T3", "T4", "T5"]}},
        {"id": "rr", "n": "Regional Rail", "c": "#4c748c", "k": "rail", "branches": "routes",
         "match": {"network": "SEPTA", "route": "train"}},
        {"id": "pat", "n": "PATCO Speedline", "c": "#db5450", "k": "metro", "branches": "longest",
         "match": {"network": "PATCO", "route": "subway"}},
    ],
}

_NYCS = "NYC Subway"
NEW_YORK = {
    "name": "New York", "places": ["new york", "manhattan", "brooklyn", "queens", "bronx", "nyc"], "auto": True,
    "families": [
        {"id": "123", "n": "1 2 3 · Broadway–Seventh Avenue", "c": "#ee352e", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["1", "2", "3"]}},
        {"id": "456", "n": "4 5 6 · Lexington Avenue", "c": "#00933c", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["4", "5", "6", "<6>"]}},
        {"id": "7", "n": "7 · Flushing", "c": "#b933ad", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["7", "<7>"]}},
        {"id": "ace", "n": "A C E · Eighth Avenue", "c": "#0039a6", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["A", "C", "E"]}},
        {"id": "bdfm", "n": "B D F M · Sixth Avenue", "c": "#ff6319", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["B", "D", "F", "<F>", "M"]}},
        {"id": "g", "n": "G · Crosstown", "c": "#6cbe45", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["G"]}},
        {"id": "jz", "n": "J Z · Nassau Street", "c": "#996633", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["J", "Z"]}},
        {"id": "l", "n": "L · 14th Street–Canarsie", "c": "#a7a9ac", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["L"]}},
        {"id": "nqrw", "n": "N Q R W · Broadway", "c": "#fccc0a", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["N", "Q", "R", "W"]}},
        {"id": "s", "n": "S · 42nd Street Shuttle", "c": "#808183", "k": "metro",
         "match": {"network": _NYCS, "route": "subway", "ref": ["S"], "name": "42nd"}},
        {"id": "path", "n": "PATH", "c": "#0082c6", "k": "metro", "match": {"network": "PATH", "route": "subway"}},
    ],
    "exclude": [{"network": "Amtrak"}],
}

_WM = "Washington Metro"
WASHINGTON = {
    "name": "Washington", "places": ["washington, dc", "washington, d.c", "washington dc", "district of columbia"],
    "auto": True,
    "families": [
        {"id": "red", "n": "Red Line", "c": "#bf0d3e", "k": "metro", "match": {"network": _WM, "ref": ["R", "RD"]}},
        {"id": "blue", "n": "Blue Line", "c": "#009cde", "k": "metro", "match": {"network": _WM, "ref": ["B", "BL"]}},
        {"id": "orange", "n": "Orange Line", "c": "#ed8b00", "k": "metro", "match": {"network": _WM, "ref": ["O", "OR"]}},
        {"id": "silver", "n": "Silver Line", "c": "#919d9d", "k": "metro", "match": {"network": _WM, "ref": ["S", "SV"]}},
        {"id": "green", "n": "Green Line", "c": "#00b140", "k": "metro", "match": {"network": _WM, "ref": ["G", "GR"]}},
        {"id": "yellow", "n": "Yellow Line", "c": "#ffd100", "k": "metro", "match": {"network": _WM, "ref": ["Y", "YL"]}},
        {"id": "dcsc", "n": "DC Streetcar", "c": "#c8102e", "k": "tram", "match": {"network": "DC Streetcar"}},
    ],
    "exclude": [{"network": "Amtrak"}, {"operator": "Architect of the Capitol"}, {"network": "Capitol Subway"}],
}

_MB = "MBTA"
BOSTON = {
    "name": "Boston", "places": ["boston", "cambridge, ma", "somerville", "brookline"], "auto": True,
    "families": [
        {"id": "red", "n": "Red Line", "c": "#da291c", "k": "metro", "match": {"network": _MB, "route": "subway", "name": "Red Line"}},
        {"id": "mat", "n": "Mattapan Line", "c": "#da291c", "k": "tram", "match": {"network": _MB, "name": "Mattapan"}},
        {"id": "orange", "n": "Orange Line", "c": "#ed8b00", "k": "metro", "match": {"network": _MB, "route": "subway", "name": "Orange Line"}},
        {"id": "blue", "n": "Blue Line", "c": "#003da5", "k": "metro", "match": {"network": _MB, "route": "subway", "name": "Blue Line"}},
        {"id": "green", "n": "Green Line", "c": "#00843d", "k": "tram", "match": {"network": _MB, "route": ["light_rail", "tram"], "name": "Green Line"}},
        {"id": "cr", "n": "Commuter Rail", "c": "#80276c", "k": "rail", "match": {"network": _MB, "route": "train"}},
    ],
    "exclude": [{"network": "Amtrak"}],
}

PRESETS = [PHILADELPHIA, NEW_YORK, WASHINGTON, BOSTON]


def preset_for(place):
    """The preset whose place names occur in `place` (case-insensitive), PHILADELPHIA for an empty place, else None
    (auto-discovery alone)."""
    pl = str(place or "").lower().strip()
    if not pl:
        return PHILADELPHIA
    for p in PRESETS:
        if any(s in pl for s in p.get("places", ())):
            return p
    return None


# ── matching ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _ci(v):
    return (v or "").lower()


def matches(tags, match) -> bool:
    """MATCH (dict, or a list of them: any) holds for a route relation's tags."""
    if isinstance(match, (list, tuple)):
        return any(matches(tags, m) for m in match)
    rt = match.get("route")
    if rt is not None and tags.get("route") not in ((rt,) if isinstance(rt, str) else tuple(rt)):
        return False
    for key in ("network", "operator", "name"):
        if match.get(key) is not None and _ci(match[key]) not in _ci(tags.get(key)):
            return False
    if match.get("ref") is not None and (tags.get("ref") or "").strip() not in match["ref"]:
        return False
    if match.get("colour") is not None and colour_of(tags) not in [c.lower() for c in match["colour"]]:
        return False
    return True


def colour_of(tags):
    c = (tags.get("colour") or tags.get("color") or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{6}", c):
        c = "#" + c
    return c


def is_candidate(tags) -> bool:
    """Rule a: a passenger service route this module may draw."""
    if tags.get("type") != "route" or tags.get("route") not in ROUTE_KINDS:
        return False
    nm = _ci(tags.get("name"))
    if "diverted" in nm or "disused" in nm or tags.get("disused") == "yes":
        return False
    if tags.get("route") == "train" and (_ci(tags.get("passenger")) in INTERCITY_PASSENGER
                                          or _ci(tags.get("service")) in INTERCITY_SERVICE):
        return False
    return True


# ── auto-discovery ────────────────────────────────────────────────────────────────────────────────────────────────
def kind_of(tags, ways):
    """Rule b. ways: the route's member way elements present in the data."""
    rt = tags.get("route")
    if rt == "train":
        return "rail"
    if rt == "tram":
        return "tram"
    if rt == "light_rail":
        street = total = 0.0
        for w in ways:
            g = w.get("geometry") or []
            L = sum(math.hypot(b["lat"] - a["lat"], (b["lon"] - a["lon"]) * 0.76) for a, b in zip(g, g[1:]))
            t = w.get("tags") or {}
            total += L
            if t.get("railway") == "tram" or t.get("embedded") in ("yes", "street") or t.get("street_running") == "yes":
                street += L
        return "tram" if total and street / total >= STREET_SHARE else "metro"
    return "metro"


def _refkey(r):
    r = re.sub(r"[^0-9A-Za-z]", "", r or "")
    return (0, int(r), "") if r.isdigit() else (1, 0, r.lower())


def _slug(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def clean_name(name, prefix=""):
    """'WMATA Red Line: Glenmont → Shady Grove' -> 'Red Line' (direction cut, the network's common prefix cut)."""
    n = (name or "").strip()
    if ":" in n:
        n = n.split(":", 1)[0].strip()
    n = re.split(r"\s+(?:=>|→|->|⇒)\s+", n)[0].strip()
    if prefix and n.startswith(prefix) and len(n) > len(prefix) + 1:
        n = n[len(prefix):].strip(" -–:")
    n = re.sub(r"\s*\((?:[^)]*(?:rush|night|weekend|evening)[^)]*)\)", "", n, flags=re.I).strip()
    return n


def _common_prefix(names):
    """The longest whole-word prefix all names share (at least two different names)."""
    names = [n for n in names if n]
    if len(set(names)) < 2:
        return ""
    words = [n.split() for n in names]
    out = []
    for col in zip(*words):
        if len(set(col)) != 1:
            break
        out.append(col[0])
    return " ".join(out)


def discover(rels, way_of, stops_of, trunks=()):
    """Rules b-f on candidate route relations. rels: [(rel id, tags, member way ids)] in id order; way_of(id): the way
    element or None; stops_of(rel id): its named stop names inside the box (ride order); trunks: [(name, set of way
    ids)] of the route=railway relations. -> [{"id", "n", "c", "k", "rels": [rel ids], "branches": "routes",
    "auto": True}] in a stable order (kind, network, refs)."""
    groups = {}
    info = {}
    for rid, tg, wids in rels:
        k = kind_of(tg, [w for w in (way_of(i) for i in wids) if w])
        net = (tg.get("network") or tg.get("operator") or "").strip()
        col = colour_of(tg)
        info[rid] = (tg, set(wids), k, net, col)
        key = (net, "rail") if k == "rail" else (net, k, col)
        groups.setdefault(key, []).append(rid)
    # a route with no colour joins its network's family it shares the most track with
    for key in [k for k in groups if len(k) == 3 and not k[2]]:
        for rid in list(groups[key]):
            ws = info[rid][1]
            best, bn = None, 0
            for k2, rs in groups.items():
                if k2 == key or len(k2) != 3 or k2[0] != key[0] or k2[1] != key[1] or not k2[2]:
                    continue
                n = len(ws & set().union(*(info[r][1] for r in rs)))
                if n > bn:
                    best, bn = k2, n
            if best is not None:
                groups[best].append(rid)
                groups[key].remove(rid)
        if not groups[key]:
            del groups[key]
    prefix = {}                                       # a network's common name prefix ("WMATA", "NYCS -", "MBTA")
    for net in {v[3] for v in info.values()}:
        prefix[net] = _common_prefix(sorted({clean_name(v[0].get("name") or "") for v in info.values() if v[3] == net}))
    fams = []
    for key, rs in groups.items():
        rs = sorted(rs)
        for comp in _components(rs, info, stops_of):
            fams.append(_family(key, comp, info, stops_of, trunks, prefix.get(key[0], "")))
    byname = {}
    for f in fams:
        byname.setdefault(f["n"], []).append(f)
    for nm, fs in byname.items():                    # two families of one name (PATH's lines): told apart by refs
        if len(fs) > 1:
            for f in fs:
                if f["_refs"]:
                    f["n"] = "%s %s" % (nm, " ".join(f["_refs"]))
    fams.sort(key=lambda f: (KIND_RANK.get(f["k"], 9), f["_net"].lower(), [_refkey(r) for r in f["_refs"]], f["n"]))
    seen, nets = set(), {}
    for f in fams:
        base = f["id"] or "line"
        i, fid = 1, base
        while fid in seen:
            i += 1
            fid = "%s%d" % (base, i)
        seen.add(fid)
        f["id"] = fid
        if not f["c"]:
            pal = PALETTE.get(f["k"], PALETTE["metro"])
            n = nets.get(f["k"], 0)
            f["c"] = pal[n % len(pal)]
            nets[f["k"]] = n + 1
    return fams


def _components(rs, info, stops_of):
    """Split a group into the parts that share track (a member way) or a stop name."""
    parent = {r: r for r in rs}

    def find(r):
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        return r
    stopset = {r: {_slug(n) for n in stops_of(r)} for r in rs}
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            if (info[a][1] & info[b][1]) or (stopset[a] & stopset[b]):
                parent[find(a)] = find(b)
    comps = {}
    for r in rs:
        comps.setdefault(find(r), []).append(r)
    return sorted(comps.values(), key=lambda c: c[0])


def _family(key, rids, info, stops_of, trunks, netprefix=""):
    tags = [info[r][0] for r in rids]
    k = info[rids[0]][2]
    net = info[rids[0]][3]
    refs = sorted({(t.get("ref") or "").strip() for t in tags if (t.get("ref") or "").strip()}, key=_refkey)
    cols = {}
    for t in tags:
        c = colour_of(t)
        if c:
            cols[c] = cols.get(c, 0) + 1
    col = max(sorted(cols), key=lambda c: cols[c]) if cols else ""
    raw_names = [clean_name(t.get("name") or "") for t in tags]
    prefix = (_common_prefix(raw_names) if len(refs) > 1 else "") or netprefix
    names = sorted({clean_name(t.get("name") or "", prefix) for t in tags} - {""})
    ws = set().union(*(info[r][1] for r in rids))
    trunk, tn = None, 0
    for nm, tw in trunks:
        n = len(ws & tw)
        if n > tn:
            trunk, tn = nm, n
    if k == "rail":
        name = net or (names[0] if names else "Rail")
    elif len(names) == 1:
        name = names[0]
    elif trunk and tn >= 0.4 * len(ws):
        name = "%s (%s)" % (trunk, " ".join(refs)) if refs else trunk
    else:
        name = "%s %s" % (net or "Line", " ".join(refs)) if refs else (names[0] if names else net or "Line")
    if k == "rail":
        fid = _slug(net)[:10] or "rail"
    elif refs and len("".join(refs)) <= 10:
        fid = "".join(dict.fromkeys(_slug(r) for r in refs)) or _slug(name)[:10]
    else:
        fid = _slug(name)[:10]
    if fid and fid[0].isdigit() and k != "metro":
        fid = k[0] + fid
    return {"id": fid, "n": name, "c": col, "k": k, "rels": list(rids), "branches": "routes", "auto": True,
            "_net": net, "_refs": refs}


def plan(rels, place="", preset=None, way_of=None, stops_of=None, trunks=()):
    """The families to draw. rels: [(rel id, tags, member way ids)] of every route relation, in id order.
    preset: a preset dict, False for auto-discovery alone, None to pick one by place (preset_for).
    -> (families [{"id","n","c","k","rels","branches","end"?}], legacy bool)."""
    if preset is None:
        preset = preset_for(place)
    preset = preset or {"auto": True}
    legacy = bool(preset.get("legacy"))
    fams, used = [], set()
    for fam in preset.get("families", ()):
        rs = []
        for rid, tg, wids in rels:
            if legacy:
                ok = tg.get("type") == "route" and "diverted" not in (tg.get("name") or "").lower()
            else:
                ok = is_candidate(tg)
            if ok and rid not in used and matches(tg, fam["match"]):
                rs.append(rid)
        if not legacy:
            used.update(rs)
        out = {k: v for k, v in fam.items() if k != "match"}
        out.setdefault("branches", "routes")
        out["rels"] = rs
        fams.append(out)
    if preset.get("auto", True) and not legacy:
        rest = [(rid, tg, w) for rid, tg, w in rels if rid not in used and is_candidate(tg)
                and not any(matches(tg, m) for m in preset.get("exclude", ()))]
        found = discover(rest, way_of or (lambda i: None), stops_of or (lambda r: []), trunks)
        taken = {f["id"] for f in fams}
        for f in found:
            ov = (preset.get("override") or {}).get(f["id"]) or {}
            f.update(ov)
            while f["id"] in taken:
                f["id"] += "x"
            taken.add(f["id"])
            fams.append(f)
    return fams, legacy
