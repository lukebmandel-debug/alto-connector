"""The toy fleet of any city (1.9.99): every museum warship, aircraft carrier, submarine and military base a city has becomes a toy that is armed with a click
and attacks the next building clicked (the battleship of the Philadelphia palace was the first; the hosted script palace_fleet_asset.py has the toys).

This module is the DATA side, read from OpenStreetMap:
  vessel_class(tags, name, len_m)  -> "bb" | "cv" | "dd" | "sub" | None     battleship (shells) / aircraft carrier (air strike) / cruiser, destroyer, any other
                                                                           warship (missile salvo) / submarine (torpedo) / not a warship
  base_class(tags)                 -> "air" | "army" | None                  a military airfield (fighters scramble) / any other base (artillery battery)
  fetch(bbox, cache_dir, offline)  -> raw Overpass answer (cached as fleet-<bbox>.json): museum ships by tag (historic=ship, building=ship, ship:type) with their
                                      outline, and military land (landuse=military, military=base|airfield|naval_base|barracks|range|training_area, military
                                      aerodromes) with their bounds
  bases(raw, bbox, scale)          -> [{n, k, rx, ry, w_m, h_m}]            real px centre and metres
  place_bases(m, bases)            -> [{n, x, y, k, r}]                     on the page (m["bases"]); the toy stands where the real base lies, out of the water
  attach(m, raw, bbox)                                                      adds the ships the building tiles missed to m["boats"] and sets m["bases"]
Ships are found and placed by palace_boats.py (find / place); this module classifies them (find() puts "k" on each) and adds the ones that are not
a `building` (a moored ship tagged only historic=ship / ship:type).
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from .. import palace_map as pmap

MAX_BASES = 3
BASE_MIN_HA = 6.0            # an unnamed stretch of military land smaller than this is a gate house, not a base
BASE_NAMED_MIN_HA = 1.0      # a named base / airfield / naval base
BASE_APART_PX = 700.0        # two bases are not drawn closer than this

_WARSHIP_TYPES = {
    "battleship": "bb", "battlecruiser": "bb",
    "aircraft_carrier": "cv", "carrier": "cv", "helicopter_carrier": "cv", "assault_ship": "cv", "amphibious_assault_ship": "cv", "escort_carrier": "cv",
    "submarine": "sub", "attack_submarine": "sub", "ballistic_missile_submarine": "sub",
    "cruiser": "dd", "heavy_cruiser": "dd", "light_cruiser": "dd", "destroyer": "dd", "frigate": "dd", "corvette": "dd", "destroyer_escort": "dd",
    "minesweeper": "dd", "gunboat": "dd", "patrol_boat": "dd", "missile_boat": "dd", "warship": "dd", "military": "dd", "monitor": "dd", "littoral_combat_ship": "dd",
}
_REF_CLASS = (("bb", r"^BB-?\d"), ("cv", r"^(CV|CVN|CVA|CVE|CVL|CVS|LHA|LHD|LPH)-?\d"), ("sub", r"^(SS|SSN|SSBN|SSG|SSK|SSR|AGSS)-?\d"),
              ("dd", r"^(CG|CGN|CL|CA|DD|DDG|DE|DER|FF|FFG|LCS|PG|PF|PT|PC|MSO|AM|AGR|WHEC|WMEC|LST|LSD|LPD|AO|AE|AS)-?\d"))
_NAME_CLASS = (
    ("bb", r"\b(new jersey|iowa|missouri|wisconsin|battleship|texas|massachusetts|north carolina|alabama|arizona|south dakota|nevada|oklahoma|utah)\b"),
    ("cv", r"\b(intrepid|midway|hornet|yorktown|lexington|enterprise|ranger|saratoga|aircraft carrier|bunker hill|essex|kitty hawk|forrestal|independence|constellation)\b"),
    ("sub", r"\b(submarine|becuna|growler|nautilus|pampanito|bowfin|batfish|cod|cobia|drum|ling|lionfish|torsk|razorback|silversides|clamagore|requin|marlin|"
            r"albacore|blueback|narwhal|dolphin|holland|u-?505|u-?534|u-?995|u-?2540|u-?9|hunley)\b"),
    ("dd", r"\b(cruiser|destroyer|frigate|corvette|olympia|kidd|cassin young|the sullivans|laffey|little rock|slater|orleck|joseph p\.? kennedy|turner joy|barry|"
           r"edson|stewart|cassin|salem|des moines|belfast|hms|hmcs|hmas|uscgc|uss|usns)\b"),
)
_NOT_WARSHIP = r"\b(lightship|light ship|fireboat|fire boat|tug|tugboat|ferry|schooner|barque|clipper|pilot|riverboat|steamboat|showboat|lilac|nantucket|frying pan|ambrose|moshulu|wavertree|gazela|peking|kalmar)\b"
_SHIP_PREFIX = r"^(USS|USCGC|USNS|USAT|HMS|HMAS|HMCS|HMNZS|INS|FS|RFA|ARA|SMS|KRI|ROKS|JS)\s"


def vessel_class(tags: dict, name: str = "", len_m: float = 0.0):
    """The weapon class of a moored vessel from its tags, its hull number and its name; None when it is no warship (a tall ship, a lightship, a restaurant)."""
    t = tags or {}
    name = (name or t.get("name") or "").strip()
    st = str(t.get("ship:type") or "").strip().lower().replace(" ", "_").replace("-", "_")
    if st in _WARSHIP_TYPES:
        return _WARSHIP_TYPES[st]
    if st in ("cargo_ship", "tanker", "tug", "ferry", "sailing_ship", "sailing", "lightship", "fireboat", "passenger", "tall_ship", "yacht", "fishing", "research"):
        return None
    ref = str(t.get("ref") or "").strip().upper()
    for k, rx in _REF_CLASS:
        if ref and re.match(rx, ref):
            return k
    low = name.lower()
    if re.search(_NOT_WARSHIP, low):
        return None
    for k, rx in _NAME_CLASS[:3]:
        if re.search(rx, low):
            return k
    if re.match(_SHIP_PREFIX, name) or re.search(_NAME_CLASS[3][1], low) or str(t.get("military") or "") in ("naval_base", "yes"):
        return "dd"                                      # a military vessel of no known class: a destroyer
    return None


_BASE_KINDS = {"base", "airfield", "naval_base", "barracks", "range", "training_area"}
_AIR_NAME = r"air (force )?base|air station|airfield|naval air|army air|airbase|air national guard|air reserve|joint base|air force"


def base_class(tags: dict):
    """"air" for a military airfield, "army" for any other military base or range, None when it is not one (an office, a checkpoint, a plain airport)."""
    t = tags or {}
    mil = str(t.get("military") or "")
    lu = t.get("landuse") == "military"
    aero = t.get("aeroway") == "aerodrome" and (mil or t.get("operator:type") == "military" or re.search(_AIR_NAME, str(t.get("name") or "").lower()))
    if mil in ("office", "checkpoint", "bunker", "trench", "obstacle_course", "danger_area", "nuclear_explosion_site"):
        return None
    if not (lu or mil in _BASE_KINDS or aero):
        return None
    if mil == "airfield" or aero or re.search(_AIR_NAME, str(t.get("name") or "").lower()):
        return "air"
    return "army"


def _query(bbox) -> str:
    s, w, n, e = bbox
    b = "(%.5f,%.5f,%.5f,%.5f)" % (s, w, n, e)
    return "\n".join([
        "[out:json][timeout:120];", "(", '  nwr[historic=ship]%s;' % b, '  nwr[building=ship]%s;' % b, '  nwr["ship:type"]%s;' % b, ")->.s;", ".s out geom;", "(",
        "  nwr[landuse=military]%s;" % b,
        '  nwr[military~"^(base|airfield|naval_base|barracks|range|training_area)$"]%s;' % b,
        "  nwr[aeroway=aerodrome][military]%s;" % b, '  nwr[aeroway=aerodrome]["operator:type"=military]%s;' % b, ");", "out tags bb;"])


def fetch(bbox, cache_dir=None, offline: bool = False) -> dict:
    """The museum ships (with their outline) and the military land (with its bounds) of the box, cached next to the city's other answers."""
    path = Path(cache_dir) / ("fleet-%.4f_%.4f_%.4f_%.4f.json" % tuple(bbox)) if cache_dir else None
    if path is not None and path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            pass
    if offline:
        return {"elements": []}
    raw = pmap._post_overpass(_query(tuple(bbox)), 130)
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(raw, separators=(",", ":")), "utf-8")
            os.replace(tmp, path)
        except OSError:
            pass
    return raw


def _ha(b) -> float:
    la = (b["maxlat"] - b["minlat"]) * 110574
    lo = (b["maxlon"] - b["minlon"]) * 111320 * math.cos(math.radians((b["maxlat"] + b["minlat"]) / 2))
    return la * lo / 1e4


def bases(raw, bbox, scale: float = 1.0) -> list:
    """The military bases of an Overpass answer, the biggest first: [{n, k, rx, ry, w_m, h_m, ha}]."""
    out = []
    for e in (raw or {}).get("elements") or []:
        t = e.get("tags") or {}
        b = e.get("bounds")
        k = base_class(t)
        if not k or not b or "minlat" not in b:
            continue
        ha = _ha(b)
        named = bool(t.get("name")) and (t.get("military") in _BASE_KINDS or t.get("aeroway") == "aerodrome")
        if ha < (BASE_NAMED_MIN_HA if named else BASE_MIN_HA):
            continue
        la, lo = (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
        rx, ry = pmap.project(la, lo, bbox, scale)
        out.append({"n": str(t.get("name") or ""), "k": k, "rx": rx, "ry": ry, "ha": ha,
                    "w_m": round((b["maxlon"] - b["minlon"]) * 111320 * math.cos(math.radians(la))), "h_m": round((b["maxlat"] - b["minlat"]) * 110574)})
    out.sort(key=lambda s: -s["ha"])
    return out


def place_bases(m: dict, found: list, doms=None) -> list:
    """Each base's toy on the page where the real base lies (through the domain that owns that real spot, as palace_boats.place does), out of the river."""
    from .palace_fillin import domains, _owners
    from .palace_boats import _nearest
    if not found:
        return []
    doms = doms or domains(m)
    _bp, by_real = _owners(doms)
    W, H = float(m.get("W") or 0), float(m.get("H") or 0)
    out = []
    for s in found:
        d = by_real(s["rx"], s["ry"])
        if d is not None and not d.free and d.mp:
            lx, ly = d.mp(s["rx"], s["ry"])
            X, Y = d.page(lx, ly)
        else:
            X, Y = s["rx"], s["ry"]
        if W and H and not (0 <= X <= W and 0 <= Y <= H):
            continue                                       # a base beyond the drawn city has no place on this map
        near = _nearest(m.get("river") or [], X, Y)
        r = max(46.0, min(92.0, math.sqrt(s["ha"]) * 2.4 + 34))
        if near and near[0] < near[3] + r * .6:            # not in the water: the toy slides to the bank side
            dist, (qx, qy), _t, hw = near
            nx_, ny_ = ((X - qx) / dist, (Y - qy) / dist) if dist > 1e-6 else (0.0, -1.0)
            X, Y = qx + nx_ * (hw + r * .7), qy + ny_ * (hw + r * .7)
        if any(math.hypot(X - o["x"], Y - o["y"]) < BASE_APART_PX for o in out):
            continue
        out.append({"n": s["n"], "x": round(X, 1), "y": round(Y, 1), "k": s["k"], "r": round(r, 1)})
        if len(out) >= MAX_BASES:
            break
    return out


def attach(m: dict, raw: dict, bbox) -> None:
    """Adds what the fleet query found to the map: warships the building tiles missed join m["boats"], bases become m["bases"]. Never fatal."""
    from .palace_boats import find as find_ships, place as place_ships
    sc = m.get("scale", 1.0)
    bb = m.get("bbox") or bbox
    have = list(m.get("boats") or [])
    ships = [s for s in find_ships(raw, bb, sc) if s["n"] and not any(b["n"] == s["n"] for b in have)]
    if ships:
        add = place_ships(m, ships)
        if add:
            m["boats"] = have + add
            nm = {b["n"] for b in add if b["n"]}
            m["landmarks"] = [l for l in m.get("landmarks", []) if l.get("n") not in nm]
    bs = place_bases(m, bases(raw, bb, sc))
    if bs:
        m["bases"] = bs
