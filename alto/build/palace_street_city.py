"""Open city data for the street blob's accuracy block (palace_street.py, 2.0.0): what a building IS, from the city's own records, at BUILD time.

Only for boxes the Philadelphia preset covers (palace_street_style.preset_for), only for the IN-BOUNDS tiles (palace_ride_real.Scope.tile_ok), cached for good under
ALTO_CITY_DIR (default ~/.cache/alto/city/), polite (a pause between requests, two failures in a row = nothing more is asked this build), never fatal: a source that fails
is simply absent (the report says so) and the build falls back to OSM + the style preset. offline = the cache only.

SOURCES (SOURCES below carries the licence + attribution recorded in the manifest's "src")
  opa   City of Philadelphia, Office of Property Assessment: opa_properties_public through the city's CARTO SQL API (https://phl.carto.com/api/v2/sql).
        One row per parcel: the parcel point, house_number / street_direction / street_name / street_designation, year_built (+ year_built_estimate), number_stories,
        building_code_description (+ _new), category_code_description, exterior_condition, frontage / depth (feet), total_livable_area.
  lif   City of Philadelphia, Licenses & Inspections: LI_BUILDING_FOOTPRINTS (ArcGIS FeatureServer, OpenDataPhilly 'building-footprints'): per building
        approx_hgt / max_hgt (feet above base), base_elevation, address, building_name. Only the centroid is fetched (returnCentroid), paged 2000 at a time.
  Overture Maps buildings (ODbL) were considered: reading them needs a GeoParquet reader (pyarrow / DuckDB), which Alto does not ship; in Philadelphia their heights are
  OSM's plus ML footprints without heights, so they add nothing the two city layers do not. Not used (see NOTES).

  opa(bbox, ...) -> (rows, note)     rows: [{"lat","lon","hn","dir","name","suf","yr","yre","st","bc","bcn","cat","ex","fr","dp","la"}]
  lif(bbox, ...) -> (rows, note)     rows: [{"lat","lon","ad","nm","ah","mh","be","ar"}]    (heights in METRES)
"""
from __future__ import annotations

import gzip
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .. import palace_map as pmap

TILE = (0.015, 0.03)                     # degrees, the street tile
PAUSE = 1.0                              # seconds between two requests to a city server
PAGE = 2000                              # the ArcGIS layer's maxRecordCount
UA = "Alto-palace-street/2.0 (build-time, cached once)"
CARTO = "https://phl.carto.com/api/v2/sql"
LIF = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/LI_BUILDING_FOOTPRINTS/FeatureServer/0/query"
FT = 0.3048

SOURCES = {
    "osm": {"n": "OpenStreetMap", "l": "ODbL 1.0", "a": "© OpenStreetMap contributors"},
    "opa": {"n": "City of Philadelphia OPA property assessments (opa_properties_public)", "l": "City of Philadelphia License (OpenDataPhilly; as is, free public use)",
            "a": "City of Philadelphia, Office of Property Assessment"},
    "lif": {"n": "City of Philadelphia L&I building footprints (LI_BUILDING_FOOTPRINTS)", "l": "City of Philadelphia License (OpenDataPhilly; as is, free public use)",
            "a": "City of Philadelphia, Licenses & Inspections"},
}
NOTES = {"overture": "Overture Maps buildings not read: no GeoParquet reader (pyarrow/DuckDB) in Alto; in Philadelphia they repeat OSM's heights"}


def city_dir() -> Path:
    return Path(os.environ.get("ALTO_CITY_DIR") or (Path.home() / ".cache" / "alto" / "city"))


def _get(url: str, timeout: int = 60) -> dict:
    """GET JSON (the one network call of this module; tests replace it). Raises RuntimeError on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:                                   # noqa: BLE001 — anything = this tile is not fetched
        raise RuntimeError(str(e)[:120]) from None
    if not isinstance(d, dict) or d.get("error"):
        raise RuntimeError("city api: %s" % str((d or {}).get("error"))[:120])
    return d


def _sleep(s):
    time.sleep(s)


def _path(kind, tb, d):
    return Path(d) / ("%s-%.4f_%.4f_%.4f_%.4f.json.gz" % ((kind,) + tuple(tb)))


def _read(p):
    try:
        return json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    except (OSError, ValueError, EOFError):
        return None


def _save(p, rows):
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(json.dumps(rows, separators=(",", ":")).encode("utf-8")))
        os.replace(tmp, p)
    except OSError:
        pass


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0
    return x if x == x else 0


def _opa_tile(tb):
    s, w, n, e = tb
    q = ("SELECT house_number,street_direction,street_name,street_designation,year_built,year_built_estimate,number_stories,building_code_description,"
         "building_code_description_new,category_code_description,exterior_condition,frontage,depth,total_livable_area,ST_Y(the_geom) AS lat,ST_X(the_geom) AS lon "
         "FROM opa_properties_public WHERE the_geom && ST_MakeEnvelope(%r,%r,%r,%r,4326)" % (w, s, e, n))
    d = _get(CARTO + "?" + urllib.parse.urlencode({"q": q}), 120)
    out = []
    for r in d.get("rows") or []:
        if r.get("lat") is None or r.get("lon") is None:
            continue
        yr = int(_num(str(r.get("year_built") or "")[:4]))
        out.append({"lat": round(r["lat"], 7), "lon": round(r["lon"], 7), "hn": str(r.get("house_number") or "").strip(), "dir": str(r.get("street_direction") or "").strip(),
                    "name": str(r.get("street_name") or "").strip(), "suf": str(r.get("street_designation") or "").strip(),
                    "yr": yr if 1600 < yr <= 2100 else 0, "yre": 1 if str(r.get("year_built_estimate") or "").upper().startswith("Y") else 0,
                    "st": int(_num(r.get("number_stories"))), "bc": str(r.get("building_code_description") or "").strip(),
                    "bcn": str(r.get("building_code_description_new") or "").strip(), "cat": str(r.get("category_code_description") or "").strip(),
                    "ex": int(_num(r.get("exterior_condition"))), "fr": _num(r.get("frontage")), "dp": _num(r.get("depth")), "la": _num(r.get("total_livable_area"))})
    return out


def _lif_tile(tb, pause):
    s, w, n, e = tb
    out, off = [], 0
    while True:
        qs = {"where": "1=1", "geometry": "%r,%r,%r,%r" % (w, s, e, n), "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
              "outFields": "address,building_name,approx_hgt,max_hgt,base_elevation,Shape__Area", "returnGeometry": "false", "returnCentroid": "true", "outSR": "4326",
              "orderByFields": "objectid", "resultOffset": str(off), "resultRecordCount": str(PAGE), "f": "json"}
        d = _get(LIF + "?" + urllib.parse.urlencode(qs), 120)
        fs = d.get("features") or []
        for f in fs:
            a, c = f.get("attributes") or {}, f.get("centroid") or {}
            if c.get("x") is None or c.get("y") is None:
                continue
            la, lo = c["y"], c["x"]
            if not (s <= la < n and w <= lo < e):              # a footprint on two tiles is kept by the tile of its centroid
                continue
            out.append({"lat": round(la, 7), "lon": round(lo, 7), "ad": str(a.get("address") or ""), "nm": str(a.get("building_name") or ""),
                        "ah": round(_num(a.get("approx_hgt")) * FT, 1), "mh": round(_num(a.get("max_hgt")) * FT, 1), "be": round(_num(a.get("base_elevation")) * FT, 1),
                        "ar": round(_num(a.get("Shape__Area")), 1)})
        if not (d.get("exceededTransferLimit") or len(fs) >= PAGE) or not fs:
            return out
        off += len(fs)
        pause()


def _fetch(kind, bbox, scope, offline, log, directory):
    """(rows, note) of one source over the in-bounds tiles of the box; note '' when every tile is in."""
    d = Path(directory) if directory else city_dir()
    rows, missing, fails, asked = [], 0, 0, False
    for tb in pmap.tile_boxes(bbox, *TILE):
        if scope is not None and not scope.tile_ok(tb):
            continue
        p = _path(kind, tb, d)
        got = _read(p) if p.exists() else None
        if got is not None:
            rows += got
            continue
        if offline or fails >= 2:
            missing += 1
            continue
        if asked:
            _sleep(PAUSE)
        asked = True
        try:
            got = _opa_tile(tb) if kind == "opa" else _lif_tile(tb, lambda: _sleep(PAUSE / 2))
        except RuntimeError as e:
            missing += 1
            fails += 1
            if log:
                log("city %s FAIL %s %s" % (kind, tb, str(e)[:80]))
            continue
        fails = 0
        _save(p, got)
        rows += got
    note = "" if not missing else ("%s: %d tile(s) not available%s" % (kind, missing, " (offline)" if offline else ""))
    return rows, note


def opa(bbox, scope=None, offline: bool = False, log=None, directory=None):
    try:
        return _fetch("opa", bbox, scope, offline, log, directory)
    except Exception as e:                                   # noqa: BLE001 — never fatal
        return [], "opa: %s" % str(e)[:80]


def lif(bbox, scope=None, offline: bool = False, log=None, directory=None):
    try:
        return _fetch("lif", bbox, scope, offline, log, directory)
    except Exception as e:                                   # noqa: BLE001
        return [], "lif: %s" % str(e)[:80]
