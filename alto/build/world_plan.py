"""Where each card of a World Palace stands (brief.palace_view "world"): pure and deterministic, so a rebuild puts every card in the same place.

Luke's design (2026-10-22):
- A unit is a region; each top card gets a country, and its child cards cluster round it (level "country", the default). With level "deep" a
  top card's children get cities of its country and the grandchildren cluster round those.
- A unit with ONE top card over several (an outline's unit hub) is the region itself: the hub is the region's own card (shown over the region,
  the unit's first Tour stop) and its children are the unit's countries.
- A card stands where the user's notes put it (set_up_world places, notes=true) or where the user says; every other card follows a memory route:
  one region per unit, the regions taken in REGIONS order round the world, and inside a region from country to the nearest unused one (its
  larger countries first: they are the ones a reader knows).
- A country's pin is its capital, unless two or more of its states / provinces / cities are in use: then each of those stands where it really is
  (a state at its capital), and the country's other cards stay at the capital. (A single Oregon card pins at Washington, D.C. — Luke confirmed.)

The brief keeps only what set_up_world was told: brief.world = {"level": "country"|"deep", "places": {node id: place}, "regions": [region names per
unit, "" for auto]}, a place being resolve()'s dict plus "r": 1 when the notes name it.
"""
from __future__ import annotations

import difflib
import math
from collections import Counter

from .world_geo import REGIONS, REGION_WORDS, gazetteer, norm, project

LEVELS = ("country", "deep")
ALIASES = {"us": "USA", "u s": "USA", "usa": "USA", "u s a": "USA", "america": "USA", "united states of america": "USA",
           "uk": "GBR", "u k": "GBR", "britain": "GBR", "great britain": "GBR", "holland": "NLD", "the netherlands": "NLD",
           "russia": "RUS", "south korea": "KOR", "korea": "KOR", "north korea": "PRK", "czech republic": "CZE", "ivory coast": "CIV",
           "burma": "MMR", "persia": "IRN", "vatican": "VAT", "vatican city": "VAT", "uae": "ARE", "drc": "COD", "congo kinshasa": "COD",
           "congo brazzaville": "COG", "east timor": "TLS", "swaziland": "SWZ", "macedonia": "MKD", "turkiye": "TUR"}
# home nations: a country of their own in speech, a part of the United Kingdom on the map (pinned at their capital)
NATIONS = {"england": ("GBR", "London"), "scotland": ("GBR", "Edinburgh"), "wales": ("GBR", "Cardiff"), "northern ireland": ("GBR", "Belfast")}


class PlaceError(ValueError):
    def __init__(self, text, suggestions):
        super().__init__(f"no place called {text!r} on the world map" + (f"; did you mean {', '.join(suggestions)}?" if suggestions else ""))
        self.text, self.suggestions = text, suggestions


def _countries():
    return gazetteer()["countries"]


def _country_index():
    idx = {}
    C = _countries()
    for names in (lambda c, cid: [c["n"]], lambda c, cid: [c.get("iso3") or "", cid], lambda c, cid: [*c["alt"], c.get("iso2") or ""]):
        for cid in sorted(C, key=lambda k: (-C[k].get("area", 0), k)):                   # a name two countries share goes to the bigger one
            for n in names(C[cid], cid):
                k = norm(n)
                if k and k not in idx:
                    idx[k] = cid
    for k, cid in ALIASES.items():
        idx.setdefault(k, cid)
    return idx


def _places():
    return gazetteer()["places"]          # [name, ascii name, country, state, lon, lat, population, class 0 capital / 1 state capital / 2 town]


def _city(cid, name):
    k = norm(name)
    rows = [r for r in _places() if r[2] == cid and (norm(r[0]) == k or norm(r[1]) == k)]
    return max(rows, key=lambda r: (r[7] == 0, r[6])) if rows else None


def _state_rows(cid, name):
    k = norm(name)
    return [r for r in _places() if (cid is None or r[2] == cid) and r[3] and norm(r[3]) == k]


def _state_pin(rows):
    caps = [r for r in rows if r[7] == 1] or [r for r in rows if r[7] == 0]
    return max(caps or rows, key=lambda r: r[6])


def _country_place(cid):
    c = _countries()[cid]
    lon, lat = (c["cap"][1], c["cap"][2]) if c.get("cap") else tuple(c["lab"])
    return {"c": cid, "lon": lon, "lat": lat, "label": c["n"]}


def resolve(text: str) -> dict:
    """A place the user named — "France", "USA", "Oregon", "Portland, Oregon", "Bavaria, Germany", "Kyoto" — as
    {"c": country id, "s": state or "", "city": city or "", "lon", "lat", "label"}. Raises PlaceError (with suggestions) when nothing matches."""
    raw = (text or "").strip()
    if not raw:
        raise PlaceError(raw, [])
    cidx = _country_index()
    whole = norm(raw)
    if whole in NATIONS:
        cid, town = NATIONS[whole]
        r = _city(cid, town)
        return {"c": cid, "s": raw.strip(), "city": "", "lon": r[4], "lat": r[5], "label": raw.strip()}
    if whole in cidx:
        return {**_country_place(cidx[whole]), "s": "", "city": ""}
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    hint = None
    state = ""
    if len(parts) > 1:
        tail = norm(parts[-1])
        if tail in cidx:
            hint = cidx[tail]
            parts = parts[:-1]
        elif tail in NATIONS:
            hint = NATIONS[tail][0]
            parts = parts[:-1]
        elif _state_rows(None, parts[-1]):
            rows = _state_rows(None, parts[-1])
            hint = Counter(r[2] for r in rows).most_common(1)[0][0]
            state = rows[0][3]
            parts = parts[:-1]
    head = ", ".join(parts)
    if not head and hint:
        return {**_country_place(hint), "s": "", "city": ""}
    # a state or province ("Oregon", "Bavaria, Germany")
    rows = _state_rows(hint, head)
    if rows and not state:
        cid = hint or Counter(r[2] for r in rows).most_common(1)[0][0]
        rows = [r for r in rows if r[2] == cid]
        town = _city(cid, head)
        if town and (town[7] == 0 or town[6] >= 1000000):                       # "New York" is the city, not Albany
            return {"c": cid, "s": town[3], "city": town[0], "lon": town[4], "lat": town[5], "label": f"{town[0]}, {_countries()[cid]['n']}"}
        pin = _state_pin(rows)
        return {"c": cid, "s": rows[0][3], "city": "", "lon": pin[4], "lat": pin[5], "label": f"{rows[0][3]}, {_countries()[cid]['n']}"}
    # a city or town ("Kyoto", "Portland, Oregon", "Washington, D.C.")
    k = norm(head)
    cands = [r for r in _places() if (norm(r[0]) == k or norm(r[1]) == k) and (hint is None or r[2] == hint)
             and (not state or norm(r[3]) == norm(state))]
    if not cands and k:
        cands = [r for r in _places() if norm(r[0]).startswith(k + " ") and (hint is None or r[2] == hint)]     # "Washington" → "Washington, D.C."
    if cands:
        r = max(cands, key=lambda r: (r[7] == 0, r[6]))
        if r[2] in _countries():
            return {"c": r[2], "s": r[3], "city": r[0], "lon": r[4], "lat": r[5], "label": f"{r[0]}, {_countries()[r[2]]['n']}"}
    names = sorted({c["n"] for c in _countries().values()} | {r[3] for r in _places() if r[3]} | {r[0] for r in _places() if r[6] > 500000})
    raise PlaceError(raw, difflib.get_close_matches(raw, names, n=4, cutoff=0.6))


def region_of(words) -> str:
    """The region a user's words name ("Western Europe", "Europe", "east asia", a Natural Earth subregion) → a REGIONS name; "" when none."""
    k = norm(words)
    for name, subs in REGIONS:
        if norm(name) == k:
            return name
    if k in REGION_WORDS:
        return REGION_WORDS[k]
    for name, subs in REGIONS:
        if any(norm(x) == k for x in subs):
            return name
    return ""


def _region_of_country(cid) -> str:
    sub = _countries()[cid]["sub"]
    for name, subs in REGIONS:
        if sub in subs:
            return name
    return ""


def _xy(p):
    return project(p["lon"], p["lat"])


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _at(cid):
    c = _countries()[cid]
    return project(*(c["cap"][1:] if c.get("cap") else c["lab"]))


def _walk(cids, cur):
    """The countries in the order a route walks them: of every nearest-next walk (one per starting country), the shortest, counting the way
    in from `cur` (where the route stands, None at its start)."""
    best = None
    for s0 in cids:
        order, left, at = [s0], [c for c in cids if c != s0], _at(s0)
        total = _dist(cur, at) if cur else 0.0
        while left:
            nx = min(left, key=lambda c: (_dist(at, _at(c)), c))
            total += _dist(at, _at(nx))
            at = _at(nx)
            order.append(nx)
            left.remove(nx)
        if best is None or total < best[0] - 1e-9:
            best = (total, order)
    return best[1] if best else []


def plan(b, nodes) -> dict:
    """{"units": [{"reg": [regions], "tops": [ids, route order], "stops": [ids, tour order]}], "places": {id: {"c", "x", "y", "label", "k", "r"?}},
    "cl": {placed id: [cluster ids in outline order]}, "used": {country: unit}, "multi": [countries with their own state / city pins]}."""
    from .palace import structure
    w = getattr(b, "world", None) or {}
    level = w.get("level") or "country"
    given = dict(w.get("places") or {})
    want_regions = list(w.get("regions") or [])
    units, floors, _of = structure(b, nodes)
    par = {n.id: n.parent for n in nodes if n.parent}
    kids = {}
    for n in nodes:
        if n.parent:
            kids.setdefault(n.parent, []).append(n.id)
    C = _countries()
    names = [r for r, _ in REGIONS]
    subs_of = dict(REGIONS)
    # a region's countries, largest first (the 1:110m map's countries only: the small ones are hard to find at a glance)
    by_region = {r: sorted((cid for cid, c in C.items() if c.get("big") and c["sub"] in subs_of[r]), key=lambda cid: (-C[cid]["area"], cid))
                 for r in names}
    taken = {p["c"] for p in given.values() if p.get("c")}
    used_regions: list = []
    out_units, places, used = [], {}, {}
    cur = None
    ptr = 0
    hubs = {}
    for a, tops in enumerate(units):
        if len(tops) == 1 and len(kids.get(tops[0], [])) >= 2:                    # an outline's unit hub: its concepts are the countries
            hubs[a] = tops[0]
            tops = list(kids[tops[0]])
        # the unit's region: what the user asked, else where its notes put it, else the next one round the world
        regs = []
        if a < len(want_regions) and want_regions[a] and region_of(want_regions[a]):
            regs = [region_of(want_regions[a])]
        if not regs:
            pref = Counter(_region_of_country(given[t]["c"]) for t in tops if t in given and given[t].get("c") in C)
            pref.pop("", None)
            if pref:
                regs = [pref.most_common(1)[0][0]]
        if not regs:
            for k in range(len(names)):
                r = names[(ptr + k) % len(names)]
                if r not in used_regions:
                    regs = [r]
                    break
            regs = regs or [names[ptr % len(names)]]
        ptr = names.index(regs[-1]) + 1
        used_regions += regs
        need = sum(1 for t in tops if t not in given)
        pool = _walk([cid for r in regs for cid in by_region[r] if cid not in taken][:max(need, 1)], cur)   # the region's largest countries
        route = []
        for t in tops:
            if t in given and given[t].get("c") in C:
                p = dict(given[t])
            else:
                free = [cid for cid in pool if cid not in taken]
                k = 0
                while not free and k < len(names):                               # the region is full: borrow the next one round the world
                    r = names[(ptr + k) % len(names)]
                    k += 1
                    if r in regs:
                        continue
                    regs.append(r)
                    free = [cid for cid in by_region[r] if cid not in taken][:max(need - len(route), 1)]
                    pool += free
                if not free:
                    free = pool or sorted(c for r in names for c in by_region[r])       # more cards than countries: they share
                cid = free[0] if cur is None or free[0] in pool else min(free, key=lambda c: (_dist(cur, _at(c)), c))
                p = {**_country_place(cid), "s": "", "city": ""}
            taken.add(p["c"])
            places[t] = p
            used.setdefault(p["c"], a)
            cur = _xy(p)
            route.append(t)
        stops = []
        for t in route:
            stops.append(t)
            if level == "deep":
                cap = places[t]
                towns = [r for r in _places() if r[2] == cap["c"] and r[7] != 0] if not cap.get("city") else []
                towns.sort(key=lambda r: -r[6])
                at = _xy(cap)
                for ch in kids.get(t, []):
                    if ch in given and given[ch].get("c") in C:
                        q = dict(given[ch])
                    elif towns:
                        r = min(towns[:max(6, len(kids.get(t, [])) * 2)], key=lambda r: (_dist(at, project(r[4], r[5])), r[0]))
                        towns.remove(r)
                        q = {"c": r[2], "s": r[3], "city": r[0], "lon": r[4], "lat": r[5], "label": f"{r[0]}, {C[r[2]]['n']}"}
                    else:
                        continue
                    q["k"] = "city"
                    places[ch] = q
                    at = _xy(q)
                    stops.append(ch)
        out_units.append({"reg": regs, "tops": route, "stops": stops, **({"hub": hubs[a]} if a in hubs else {})})
    # any other card the user placed by hand (a floor given a place of its own)
    for nid, p in given.items():
        if nid not in places and p.get("c") in C and nid in par:
            places[nid] = dict(p, k="city")
    # pins: a country's capital, unless two or more of its states / cities are in use
    subs = {}
    for nid, p in places.items():
        key = p.get("city") or p.get("s")
        if key:
            subs.setdefault(p["c"], set()).add(norm(key))
    multi = sorted(c for c, s in subs.items() if len(s) >= 2)
    out = {}
    for nid, p in places.items():
        own = p.get("k") == "city" or (p["c"] in multi and (p.get("city") or p.get("s")))
        q = p if own else {**_country_place(p["c"])}
        x, y = _xy(q)
        rec = {"c": p["c"], "x": round(x, 2), "y": round(y, 2), "label": (p.get("city") or p.get("s") or q["label"]) if own else C[p["c"]]["n"],
               "k": "city" if p.get("k") == "city" else ("sub" if own else "country")}
        if p.get("r"):
            rec["r"] = 1
            if not own and (p.get("city") or p.get("s")):
                rec["named"] = p.get("label") or ""
        out[nid] = rec
    # clusters: the cards with no place of their own, round the nearest placed ancestor
    cl = {}
    for a, tops in enumerate(units):
        for t in tops:
            for f in [t] + floors.get(t, []):
                if f in out or f == hubs.get(a):
                    continue
                up = par.get(f)
                while up and up not in out:
                    up = par.get(up)
                if up:
                    cl.setdefault(up, []).append(f)
    return {"level": level, "units": out_units, "places": out, "cl": cl, "used": used, "multi": multi}


def summary(b, nodes) -> dict:
    """What set_up_world reports: per unit its region(s) and each top card's place, the countries with pins of their own per state / city."""
    p = plan(b, nodes)
    by = {n.id: n for n in nodes}
    return {"level": p["level"],
            "units": [{"unit": i + 1, "regions": u["reg"], **({"region_card": by[u["hub"]].title} if u.get("hub") in by else {}),
                       "stops": [{"node": t, "title": by[t].title if t in by else t, "place": p["places"][t]["label"],
                                  **({"from_notes": True} if p["places"][t].get("r") else {})} for t in u["stops"]]}
                      for i, u in enumerate(p["units"])],
            "own_pins": [_countries()[c]["n"] for c in p["multi"]]}


def validate(world) -> None:
    """Raises ValueError for a malformed brief.world."""
    if world is None:
        return
    if not isinstance(world, dict):
        raise ValueError("world must be an object")
    lv = world.get("level") or "country"
    if lv not in LEVELS:
        raise ValueError(f"world.level {lv!r}: must be one of {LEVELS}")
    for nid, p in (world.get("places") or {}).items():
        if not isinstance(p, dict) or p.get("c") not in _countries():
            raise ValueError(f"world.places[{nid!r}]: not a resolved place (set_up_world resolves them)")
    for r in world.get("regions") or []:
        if r and not region_of(r):
            raise ValueError(f"world.regions: {r!r} is not a region (one of {', '.join(n for n, _ in REGIONS)})")
