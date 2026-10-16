"""Subject-aware landmarks: a law palace (a Mind Palace for a law class) gets the city's real courthouses as landmark
buildings, by level — federal (U.S. district courthouses, the courts of appeals, the U.S. Supreme Court), state
(state supreme / appellate / trial courts) and city (municipal, county, family, superior / district courts, a City
Hall that houses courts).

- A built-in city (Philadelphia, NYC, Boston, DC) takes city_presets.COURTS, matched to the map's own spelling.
- Any other city: OSM amenity=courthouse (and building=courthouse / a building named "... Court(house)"), one small
  tags-only query (courts_query), classified by name, ranked by prominence and kept distinct, 9 at most with at
  least one per level the city has.
- Each courthouse becomes a landmark_buildings entry {name, label?, kind: "courthouse", level, levels, page?,
  height_m?, floors?}: `page` opens the matching Index of the user's own timeline (federal -> its federal-law
  index, state -> state law / cases, city -> local rules); it is resolved by keywords over the timeline's own index
  keys and labels and left out when nothing matches (closed-system rule: a page only links the user's materials).
The art (porticoes, federal glass boxes) is drawn by palace_skyline from kind / level / height; nothing here draws.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

MAX_COURTS = 9
LEVELS = ("federal", "state", "city")

_LAW = re.compile(r"\b(law|laws|legal|court|courts|civ(il)? ?pro(cedure)?|crim(inal)? ?(law|pro(cedure)?)|"
                  r"constitutional|torts?|contracts|evidence|statutes?|u\.?\s?s\.?\s?c\.?|f\.?r\.?c\.?p\.?|"
                  r"jurisdiction|litigation|bar exam|1l|lsat|appellate|judicial)\b", re.I)


# ── is this a law palace? ────────────────────────────────────────────────────
def is_law(texts=(), subject=None) -> bool:
    """subject="law" (or "legal") says so outright; any other explicit subject says no; else the timeline's
    title / purpose / section names are read for law words."""
    if subject:
        return str(subject).strip().lower() in ("law", "legal", "law school", "courts")
    return any(_LAW.search(str(t or "")) for t in texts)


def brief_texts(brief: dict) -> list:
    b = brief or {}
    out = [b.get(k) for k in ("title", "subtitle", "purpose", "subject", "course", "description") if b.get(k)]
    for a in b.get("acts") or []:
        out.append(a.get("name") if isinstance(a, dict) else a)
    return out


# ── the timeline's own index pages ──────────────────────────────────────────
def index_keys(b) -> list:
    """[(key, label)] of the timeline's Index pages (the hide_nav axes, one per group), as the page addresses them."""
    from .detail_extras import index_entries
    axes = getattr(b, "axes", None) or []
    ia = [(k, ax) for k, ax in (("env", axes[0] if axes else None), ("theme", axes[1] if len(axes) > 1 else None))
          if ax and getattr(ax, "hide_nav", False)]
    return [(key, label) for key, _kind, label, _ids in index_entries(ia)]


_PAGE_RX = {
    "federal": re.compile(r"federal|u-?s-?c\b|\bu\.?s\.?c\.?|united.states|frcp|f\.?r\.?c\.?p|fed\b|28-u|"
                          r"title-28|constitution|supreme.court.of.the.united", re.I),
    "state": re.compile(r"\bstate\b|state-|commonwealth|pennsylvania|new.york|massachusetts|district.of.columbia|"
                        r"\bcases?\b|case-law|caselaw|common.law|precedent", re.I),
    "city": re.compile(r"local|\bcity\b|municipal|county|ordinance|family|housing|traffic", re.I),
}


def page_for(level: str, keys) -> str | None:
    """'index:<key>' of the timeline's own index whose key or label matches the level, or None. Federal is tried
    on the key and label; a key that already matched a stronger level is not reused for a weaker one."""
    rx = _PAGE_RX.get(level)
    if not rx:
        return None
    for key, label in keys or ():
        hay = f"{key} {label or ''}"
        if rx.search(hay) and not (level != "federal" and _PAGE_RX["federal"].search(hay)):
            return "index:" + key
    return None


# ── finding courthouses on the map ─────────────────────────────────────────
def courts_query(bbox, timeout=60) -> str:
    b = "(%r,%r,%r,%r)" % tuple(float(v) for v in bbox)
    return "\n".join([
        "[out:json][timeout:%d];" % timeout, "(",
        "  nwr[amenity=courthouse]%s;" % b,
        "  nwr[building=courthouse]%s;" % b,
        '  nwr[building][name~"[Cc]ourt ?[Hh]ouse|[Cc]ourts? [Bb]uilding|Justice Center|Center for Criminal Justice"]%s;' % b,
        '  nwr[office=government][name~"[Cc]ourt"]%s;' % b,
        ");", "out tags center;"])


def fetch_courts(bbox, cache_dir=None, timeout=60, log=None, offline=False) -> dict:
    path = Path(cache_dir) / ("courts-%.4f_%.4f_%.4f_%.4f.json" % tuple(float(v) for v in bbox)) if cache_dir else None
    if path is not None and path.exists():
        return json.loads(path.read_text("utf-8"))
    if offline:
        raise RuntimeError("courthouses not cached for %s" % (tuple(bbox),))
    from .city_setup import post_retry
    raw = post_retry(courts_query(bbox, timeout), timeout, log)
    if log:
        log("ok courts %s %d elements" % (tuple(bbox), len(raw.get("elements", []))))
    if path is not None:
        from .city_setup import _store
        _store(path, raw)
    return raw


_FED = re.compile(r"united states|\bu\.\s?s\.|\bus courthouse|\bfederal\b|court of appeals for the|"
                  r"supreme court of the united states|bankruptcy|court of international trade|tax court|"
                  r"court of federal claims|national courts", re.I)
_STATE = re.compile(r"supreme court|court of appeals|appellate|appeals court|commonwealth court|supreme judicial|"
                    r"court of common pleas|court of chancery|criminal justice|state court|court of claims", re.I)
_CITY = re.compile(r"municipal|county|family|juvenile|housing|traffic|superior court|district court|city hall|"
                   r"magistrate|surrogate|probate|small claims|civil court|criminal court|police court|night court",
                   re.I)


def level_of(name: str, tags=None) -> str | None:
    """federal / state / city from the court's name (and operator), or None when it reads as no court."""
    t = tags or {}
    hay = " ".join(str(x) for x in (name, t.get("operator"), t.get("court"), t.get("official_name")) if x)
    if _FED.search(hay):
        return "federal"
    if _STATE.search(hay):            # a state court in a county's building ("New York County Supreme Court") is state
        return "state"
    if _CITY.search(hay):
        return "city"
    if t.get("amenity") == "courthouse" or t.get("building") == "courthouse" or re.search(r"court", hay, re.I):
        return "city"
    return None


def _ll(e):
    if "lat" in e:
        return float(e["lat"]), float(e["lon"])
    c = e.get("center")
    return (float(c["lat"]), float(c["lon"])) if c else None


def _dist(a, b):
    return math.hypot((a[1] - b[1]) * 111320 * math.cos(math.radians(a[0])), (a[0] - b[0]) * 110574)


def _num(v):
    m = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", str(v or ""))
    return float(m.group(1)) if m else None


def courts_of(els, bbox, n_max=MAX_COURTS) -> list:
    """The city's courthouses from OSM tags: [{name, level, levels, lat, lon, height_m?, floors?}], ranked by
    prominence (wikidata / wikipedia / languages / heritage / height), distinct (not within 60 m of a better one
    or the same name twice), at most n_max, with the best of each level the city has kept first."""
    rows = []
    for e in els or ():
        t = e.get("tags") or {}
        n = (t.get("name") or "").strip()
        ll = _ll(e)
        if not n or len(n) > 80 or ll is None or not (bbox[0] <= ll[0] <= bbox[2] and bbox[1] <= ll[1] <= bbox[3]):
            continue
        lv = level_of(n, t)
        if not lv or (t.get("amenity") != "courthouse" and t.get("building") != "courthouse" and not re.search(
                r"court|justice", n, re.I)):
            continue
        sc = 5 * bool(t.get("wikidata")) + 4 * bool(t.get("wikipedia")) + 3 * bool(t.get("heritage")) \
            + sum(1 for k in t if k.startswith("name:")) + (_num(t.get("height")) or 0) / 50.0 \
            + 2 * (t.get("amenity") == "courthouse") + 1 * (e.get("type") != "node")
        rec = {"name": n, "level": lv, "levels": [lv], "lat": round(ll[0], 5), "lon": round(ll[1], 5)}
        if _num(t.get("height")):
            rec["height_m"] = round(_num(t["height"]))
        lv_n = _num(t.get("building:levels"))
        if lv_n and 2 <= lv_n <= 250:
            rec["floors"] = int(lv_n)
        rows.append((sc, rec))
    rows.sort(key=lambda r: (-r[0], r[1]["name"]))
    kept = []
    for sc, r in rows:
        if any(r["name"].lower() == k["name"].lower() or _dist((r["lat"], r["lon"]), (k["lat"], k["lon"])) < 60
               for k in kept):
            continue
        kept.append(r)
    first = []
    for lv in LEVELS:
        best = next((r for r in kept if r["level"] == lv), None)
        if best:
            first.append(best)
    rest = [r for r in kept if r not in first]
    return (first + rest)[:n_max]


def match_names(courts, els) -> list:
    """Each preset court spelled as the map spells it: its name, else an `aka` the map has (case-insensitive,
    near the court's place). The record gains `osm` True/False (found on the map or not)."""
    by = {}
    for e in els or ():
        n = (e.get("tags") or {}).get("name")
        ll = _ll(e)
        if n and ll:
            by.setdefault(n.lower(), []).append((n, ll))
    out = []
    for c in courts:
        c = dict(c)
        hit = None
        for cand in [c["name"], *c.get("aka", [])]:
            for n, ll in by.get(cand.lower(), []):
                if _dist(ll, (c["lat"], c["lon"])) < 400:
                    hit = n
                    break
            if hit:
                break
        c["osm"] = bool(hit)
        if hit:
            c["name"] = hit
        out.append(c)
    return out


def buildings(courts, keys=(), given=()) -> list:
    """The landmark_buildings entries for the courthouses: a court already in `given` (by name or label) keeps its
    entry and gains kind / level; the others are appended. page: the timeline's own matching index, never made up."""
    out = [dict(b) for b in given or ()]
    idx = {}
    for i, b in enumerate(out):
        for k in (b.get("name"), b.get("label")):
            if k:
                idx[str(k).lower()] = i
    for c in courts:
        names = [c["name"], c.get("label"), *c.get("aka", [])]
        i = next((idx[str(n).lower()] for n in names if n and str(n).lower() in idx), None)
        page = page_for(c["level"], keys)
        rec = {"kind": "courthouse", "level": c["level"], "levels": list(c.get("levels") or [c["level"]]),
               **({k: c[k] for k in ("height_m",) if c.get(k)})}
        if i is not None:
            out[i].update(rec)
            if page and not out[i].get("page"):
                out[i]["page"] = page
            continue
        b = {"name": c["name"], **({"label": c["label"]} if c.get("label") else {}), **rec,
             **({"page": page} if page else {})}
        out.append(b)
        idx[c["name"].lower()] = len(out) - 1
    return out
