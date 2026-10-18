"""Wikidata (CC0) for the street blob's landmarks (palace_street.py accuracy block): year, height, floors, style, architect, heritage, instance-of.

At BUILD time, for the in-bounds box only: the items a building's OSM wikidata=* names, plus the buildings Wikidata places inside the box (a SPARQL box query: items with
coordinates that are a building / structure and carry a year, a height or a floor count) — these are joined to the footprint they stand in. Cached for good under
ALTO_WIKIDATA_DIR (default ~/.cache/alto/wikidata/), polite (a User-Agent, batches of 50, a pause between requests, two failures in a row = nothing more is asked),
never fatal, offline = the cache only.

  items(qids, ...)       -> ({qid: rec}, note)      rec {"yr", "h" m, "fl", "sy" style, "ar" architect, "her" heritage, "inst" [instance labels], "nm"}
  in_box(bbox, ...)      -> ([(lat, lon, qid)], note)
  typology(rec)          -> palace_street_acc TY code from the instance labels (0 when they say nothing useful)
"""
from __future__ import annotations

import gzip
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
UA = "Alto-palace-street/2.0 (build-time, cached once) python-urllib"
PAUSE = 1.0
BATCH = 50
SOURCE = {"k": "wikidata", "n": "Wikidata", "l": "CC0 1.0", "a": "Wikidata"}
_FT = {"Q3710": 0.3048, "Q11573": 1.0}           # foot, metre


def wd_dir() -> Path:
    return Path(os.environ.get("ALTO_WIKIDATA_DIR") or (Path.home() / ".cache" / "alto" / "wikidata"))


def _get(url: str, timeout: int = 60) -> dict:
    """GET JSON (the one network call of this module; tests replace it). Raises RuntimeError on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json, application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:                                   # noqa: BLE001
        raise RuntimeError(str(e)[:120]) from None
    if not isinstance(d, dict) or d.get("error"):
        raise RuntimeError("wikidata: %s" % str((d or {}).get("error"))[:120])
    return d


def _sleep(s):
    time.sleep(s)


def _cache_read(p):
    try:
        return json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    except (OSError, ValueError, EOFError):
        return None


def _cache_write(p, obj):
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")))
        os.replace(tmp, p)
    except OSError:
        pass


def _vals(claims, pid):
    out = []
    for c in claims.get(pid) or []:
        if c.get("rank") == "deprecated":
            continue
        dv = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if dv is not None:
            out.append((c.get("rank") == "preferred", dv))
    out.sort(key=lambda x: not x[0])
    return [v for _p, v in out]


def _year(v):
    m = re.match(r"[+]?(\d{3,4})-", str((v or {}).get("time") or ""))
    return int(m.group(1)) if m else 0


def _amount(v):
    try:
        a = float((v or {}).get("amount"))
    except (TypeError, ValueError):
        return 0.0
    unit = str((v or {}).get("unit") or "").rsplit("/", 1)[-1]
    return a * _FT.get(unit, 1.0 if unit in ("", "1") else 0.0)


def _qid(v):
    return (v or {}).get("id") if isinstance(v, dict) else None


def _parse(ent):
    cl = ent.get("claims") or {}
    ys = [y for y in (_year(v) for pid in ("P571", "P580") for v in _vals(cl, pid)) if 1600 < y <= 2100]     # inception / start of construction: the earliest
    if not ys:
        ys = [y for y in (_year(v) for pid in ("P1619", "P729") for v in _vals(cl, pid)) if 1600 < y <= 2100]  # else official opening / service entry
    yr = min(ys) if ys else 0
    h = max([_amount(v) for v in _vals(cl, "P2048")] or [0.0])
    fl = max([int(_amount(v)) for v in _vals(cl, "P1101")] or [0])
    return {"yr": yr, "h": round(h, 1) if 2 < h < 1000 else 0.0, "fl": fl if 0 < fl < 200 else 0,
            "_sy": [_qid(v) for v in _vals(cl, "P149")][:2], "_ar": [_qid(v) for v in _vals(cl, "P84")][:2],
            "_her": [_qid(v) for v in _vals(cl, "P1435")][:2], "_inst": [_qid(v) for v in _vals(cl, "P31")][:4],
            "nm": ((ent.get("labels") or {}).get("en") or {}).get("value", "")}


def _entities(ids, props, state, log):
    """{qid: entity} of one batch through wbgetentities; state carries fails / asked for politeness."""
    if state["fails"] >= 2:
        raise RuntimeError("wikidata: given up this build")
    if state["asked"]:
        _sleep(PAUSE)
    state["asked"] = True
    url = API + "?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(ids), "props": props, "languages": "en", "format": "json", "maxlag": "15"})
    try:
        for attempt in range(3):                                # a lagged Wikidata asks bots to wait and retry (maxlag): that is not a failure
            try:
                d = _get(url, 60)
                break
            except RuntimeError as e:
                if "maxlag" not in str(e) or attempt == 2:
                    raise
                _sleep(6.0 * (attempt + 1))
    except RuntimeError as e:
        state["fails"] += 1
        if log:
            log("wikidata FAIL %s" % str(e)[:80])
        raise
    state["fails"] = 0
    return d.get("entities") or {}


QRE = re.compile(r"^Q\d{1,10}$")


def items(qids, offline: bool = False, log=None, directory=None):
    """({qid: rec}, note) for the qids (OSM wikidata=* values; several ';'-joined values: the first). Labels of style / architect / heritage / instance are resolved."""
    d = Path(directory) if directory else wd_dir()
    want = sorted({str(q).split(";")[0].strip() for q in qids if q and QRE.match(str(q).split(";")[0].strip())})
    out, need, missing = {}, [], 0
    for q in want:
        got = _cache_read(d / ("%s.json.gz" % q))
        if got is not None:
            out[q] = got
        else:
            need.append(q)
    state = {"fails": 0, "asked": False}
    if need and offline:
        missing = len(need)
        need = []
    raw = {}
    for i in range(0, len(need), BATCH):
        try:
            ents = _entities(need[i:i + BATCH], "claims|labels", state, log)
        except RuntimeError:
            missing += len(need[i:i + BATCH])
            continue
        for q, e in ents.items():
            if "missing" not in e:
                raw[q] = _parse(e)
    lab_ids = sorted({x for r in raw.values() for k in ("_sy", "_ar", "_her", "_inst") for x in r[k] if x})
    labels = {}
    for i in range(0, len(lab_ids), BATCH):
        try:
            ents = _entities(lab_ids[i:i + BATCH], "labels", state, log)
        except RuntimeError:
            continue
        for q, e in ents.items():
            labels[q] = ((e.get("labels") or {}).get("en") or {}).get("value", "")
    for q, r in raw.items():
        if lab_ids and not labels:                                  # labels failed: do not cache a half record, use it this build only
            keep = False
        else:
            keep = True
        rec = {"yr": r["yr"], "h": r["h"], "fl": r["fl"], "nm": r["nm"], "sy": "; ".join(labels.get(x, "") for x in r["_sy"] if labels.get(x)),
               "ar": "; ".join(labels.get(x, "") for x in r["_ar"] if labels.get(x)), "her": "; ".join(labels.get(x, "") for x in r["_her"] if labels.get(x)),
               "inst": [labels.get(x, "") for x in r["_inst"] if labels.get(x)]}
        out[q] = rec
        if keep:
            _cache_write(d / ("%s.json.gz" % q), rec)
    for q in need:
        if q not in raw and q not in out:
            out[q] = None
    note = ("wikidata: %d item(s) not available%s" % (missing, " (offline)" if offline else "")) if missing else ""
    return {q: r for q, r in out.items() if r}, note


def box_query(bbox) -> str:
    s, w, n, e = bbox
    return ("SELECT DISTINCT ?item ?coord WHERE { SERVICE wikibase:box { ?item wdt:P625 ?coord . bd:serviceParam wikibase:cornerSouthWest \"Point(%r %r)\"^^geo:wktLiteral . "
            "bd:serviceParam wikibase:cornerNorthEast \"Point(%r %r)\"^^geo:wktLiteral . } ?item wdt:P31/wdt:P279* wd:Q41176 . "
            "FILTER EXISTS { { ?item wdt:P571 [] } UNION { ?item wdt:P2048 [] } UNION { ?item wdt:P1101 [] } } }" % (w, s, e, n))


def in_box(bbox, offline: bool = False, log=None, directory=None):
    """([(lat, lon, qid)], note): Wikidata's buildings with coordinates in the box (one SPARQL query, cached by the box)."""
    d = Path(directory) if directory else wd_dir()
    p = d / ("box-%.4f_%.4f_%.4f_%.4f.json.gz" % tuple(float(v) for v in bbox))
    got = _cache_read(p) if p.exists() else None
    if got is not None:
        return [tuple(x) for x in got], ""
    if offline:
        return [], "wikidata box: not cached (offline)"
    try:
        r = _get(SPARQL + "?" + urllib.parse.urlencode({"query": box_query(bbox), "format": "json"}), 90)
    except RuntimeError as e:
        if log:
            log("wikidata box FAIL %s" % str(e)[:80])
        return [], "wikidata box: %s" % str(e)[:60]
    out = []
    for b in (r.get("results") or {}).get("bindings") or []:
        q = str((b.get("item") or {}).get("value") or "").rsplit("/", 1)[-1]
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", str((b.get("coord") or {}).get("value") or ""))
        if QRE.match(q) and m:
            out.append((round(float(m.group(2)), 7), round(float(m.group(1)), 7), q))
    out = sorted(set(out))
    _cache_write(p, out)
    return out, ""


_TY_WORDS = [  # (substring of an instance-of label, palace_street_acc TY name) — the first that matches wins; Masonic temples are civic, not churches
    ("masonic", "civic"), ("courthouse", "civic"), ("city hall", "civic"), ("town hall", "civic"), ("capitol", "civic"), ("government", "civic"),
    ("railway station", "civic"), ("train station", "civic"), ("station", "civic"), ("museum", "civic"), ("library", "civic"), ("post office", "civic"),
    ("theatre", "civic"), ("theater", "civic"), ("concert hall", "civic"), ("market", "civic"), ("bank", "office"), ("exchange", "office"),
    ("cathedral", "religious"), ("basilica", "religious"), ("church", "religious"), ("synagogue", "religious"), ("mosque", "religious"), ("meeting house", "religious"),
    ("temple", "religious"), ("chapel", "religious"), ("skyscraper", "highrise"), ("office", "office"), ("hotel", "hotel"), ("hospital", "hospital"),
    ("school", "school"), ("university", "school"), ("college", "school"), ("apartment", "lowrise_apts"), ("warehouse", "industrial"), ("factory", "industrial"),
    ("parking", "parking"), ("garage", "parking"), ("row house", "rowhouse"), ("townhouse", "rowhouse"), ("house museum", "civic")]


def typology(rec) -> int:
    from .palace_street_acc import TY
    for lab in (rec or {}).get("inst") or ():
        low = lab.lower()
        for word, ty in _TY_WORDS:
            if word in low:
                return TY[ty]
    return 0


_NOT_A_BUILDING = ("organization", "organisation", "company", "business", "agency", "institution", "bank", "enterprise", "brand", "association")


def is_building(rec) -> bool:
    """False for an item that is an organisation housed somewhere (its coordinates are an address, not a footprint): such an item is never joined by position."""
    return not any(w in lab.lower() for lab in (rec or {}).get("inst") or () for w in _NOT_A_BUILDING)
