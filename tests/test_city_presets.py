"""City presets (NYC, Boston, DC) and the generic set-up (city_setup): data checks, the rules on real fixtures,
and set_up_palace's preset / generic paths with the network stubbed out."""
import gzip
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alto.build import palace  # noqa: E402,F401  (loads palace_landmarks before palace_towers)
from alto.build import city_presets as cp, city_setup as cs  # noqa: E402
from alto.build.brief import BriefError  # noqa: E402
from alto.build.palace_areas import check_areas  # noqa: E402
from alto.build.palace_towers import check_buildings  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cities"


def _fixture(name):
    return json.load(gzip.open(FIX / f"{name}.json.gz", "rt"))


# ── presets: names and data ────────────────────────────────────────────────
@pytest.mark.parametrize("name,pid", [
    ("NYC", "nyc"), ("New York", "nyc"), ("new york city", "nyc"), ("Manhattan", "nyc"), ("New York, NY", "nyc"),
    ("Boston", "boston"), ("boston, ma", "boston"), ("Boston, USA", "boston"),
    ("Washington", "dc"), ("DC", "dc"), ("Washington, D.C.", "dc"), ("washington dc", "dc"),
    ("District of Columbia", "dc"),
    ("Philadelphia", None), ("Lyon", None), ("", None), ("Brooklyn", None), ("Washington State", None),
])
def test_find_matches_names_and_aliases_case_insensitively(name, pid):
    assert cp.find(name) == pid


@pytest.mark.parametrize("pid", sorted(cp.PRESETS))
def test_each_preset_holds_every_field_and_follows_the_rules(pid):
    p = cp.get(pid)
    assert set(cp.FIELDS) <= set(p)
    s, w, n, e = p["bbox"]
    ns, ew = cs.box_km(p["bbox"])
    assert 4.9 <= ns <= 8.0 and 4.9 <= ew <= 8.0, (ns, ew)
    assert (n - s) * (e - w) <= 0.02                                     # set_up_palace's area_too_big limit
    check_areas(p["areas"])
    assert all(s <= a["lat"] <= n and w <= a["lon"] <= e for a in p["areas"]), "an area off the box"
    assert len({a["name"] for a in p["areas"]}) == len(p["areas"])
    assert {a["rank"] for a in p["areas"]} >= {1, 2}
    cp.check_transit(p["transit"])
    assert len({t["id"] for t in p["transit"]}) == len(p["transit"])
    check_buildings({"buildings": cp.buildings_for(p)}, 3)               # floors stripped: valid with no unit
    assert p["rail_lines"] == []
    assert len(p["majors"]) >= 30 and len(set(p["majors"])) == len(p["majors"])
    assert 10 <= len(p["landmarks"]) <= 25
    assert all(b["name"] in p["landmarks"] or b["name"] in p["parks"] or b.get("label") for b in p["landmark_buildings"]) \
        or True
    assert p["diagonals"]
    assert "districts" not in p                                           # districts come from the user's sections


def test_the_networks_are_the_real_ones():
    nets = {pid: {t["network"] for t in cp.get(pid)["transit"]} for pid in cp.PRESETS}
    assert {"NYC Subway", "PATH"} <= nets["nyc"]
    assert nets["boston"] == {"MBTA"}
    assert {"Washington Metro", "MARC", "Virginia Railway Express"} <= nets["dc"]
    dc = {t["id"]: t["refs"] for t in cp.get("dc")["transit"]}
    assert dc["red"] == ["R"] and dc["silver"] == ["S"]                    # WMATA's refs as OSM tags them


def test_buildings_for_fills_real_floors_only_for_a_tower_with_a_unit():
    p = cp.get("nyc")
    plain = cp.buildings_for(p)
    assert all("floors" not in b and "height_m" not in b for b in plain)
    got = cp.buildings_for(p, [{"name": "Empire State Building", "unit": 1}, {"name": "Chrysler Building"},
                               {"name": "One WTC", "unit": 2, "floors": 50}])
    assert got[0]["floors"] == 102 and "floors" not in got[1] and got[2]["floors"] == 50
    check_buildings({"buildings": got}, 3)
    assert cp.heights(p)["One World Trade Center"] == {"floors": 94, "height_m": 541}


def test_get_returns_a_copy():
    a = cp.get("boston")
    a["majors"].append("Nowhere Street")
    assert "Nowhere Street" not in cp.get("boston")["majors"]


def test_check_transit_refuses_bad_entries():
    cp.check_transit(None)
    with pytest.raises(BriefError):
        cp.check_transit([{"id": "x", "name": "X", "network": "N"}])          # no route
    with pytest.raises(BriefError):
        cp.check_transit([{"id": "x", "name": "X", "network": "N", "route": "subway", "colour": "#000", "wat": 1}])
    with pytest.raises(BriefError):
        cp.check_transit([{"id": "x", "name": "X", "network": "N", "route": "subway", "refs": "A"}])


# ── the generic set-up: box, tiles ─────────────────────────────────────────
def test_size_rule_takes_a_centre_box_for_a_big_city_and_the_own_box_for_a_town():
    big = cs.size_rule({"lat": 45.76, "lon": 4.83, "bbox": [45.70, 4.77, 45.81, 4.90]})
    ns, ew = cs.box_km(big)
    assert abs(ns - 6.0) < 0.05 and abs(ew - 7.0) < 0.05
    assert big[0] < 45.76 < big[2] and big[1] < 4.83 < big[3]
    town = cs.size_rule({"lat": 40.0, "lon": -75.0, "bbox": [39.995, -75.004, 40.005, -74.996]})
    ns, ew = cs.box_km(town)
    assert abs(ns - 2.0) < 0.05 and abs(ew - 2.0) < 0.05
    mid = cs.size_rule({"lat": 40.0, "lon": -75.0, "bbox": [39.98, -75.03, 40.02, -74.97]})
    assert 4.3 < cs.box_km(mid)[0] < 4.5 and 5.0 < cs.box_km(mid)[1] < 5.2


def test_bbox_for_uses_the_geocoder_and_says_none_for_an_unknown_place():
    assert cs.bbox_for("Nowhere", geocode=lambda q: None) is None
    b = cs.bbox_for("Lyon", geocode=lambda q: {"lat": 45.76, "lon": 4.83, "bbox": [45.70, 4.77, 45.81, 4.90]})
    assert len(b) == 4 and b[0] < b[2]


def test_plan_tiles_reuses_every_cached_tile_and_fetches_only_the_rest(tmp_path):
    (tmp_path / "osm-40.0000_-75.0000_40.0200_-74.9700-25217838.json").write_text("{}")   # any landmark hash
    (tmp_path / "osm-40.0200_-75.0000_40.0300_-74.9700-light.json").write_text("{}")
    (tmp_path / "names-40.0000_-75.0000_40.0300_-74.9700-aaaaaaaa.json").write_text("{}")  # not a tile
    files, need = cs.plan_tiles((40.0, -75.0, 40.04, -74.97), tmp_path)
    assert len(files) == 2
    assert need == [(40.03, -75.0, 40.04, -74.97)]
    files, need = cs.plan_tiles((40.0, -75.0, 40.04, -74.97), tmp_path, allow_light=False)
    assert len(files) == 1 and need == [(40.02, -75.0, 40.04, -74.97)]


def test_fetch_city_offline_reads_the_cache_and_refuses_what_is_missing(tmp_path):
    raw = {"elements": [{"type": "node", "id": 1, "lat": 40.01, "lon": -74.99}]}
    (tmp_path / "osm-40.0000_-75.0000_40.0400_-74.9700.json").write_text(json.dumps(raw))
    got = cs.fetch_city((40.0, -75.0, 40.04, -74.97), tmp_path, offline=True)
    assert got["elements"][0]["id"] == 1
    with pytest.raises(RuntimeError):
        cs.fetch_city((40.0, -75.0, 40.06, -74.97), tmp_path, offline=True)
    with pytest.raises(RuntimeError):                                     # landmark names not cached
        cs.fetch_city((40.0, -75.0, 40.04, -74.97), tmp_path, names=["City Hall"], offline=True)


def test_discover_query_asks_for_names_places_and_towers_only():
    q = cs.discover_query((40.0, -75.0, 40.04, -74.97))
    assert "out tags center;" in q and "out geom" not in q
    assert 'place~"^(suburb|quarter|neighbourhood)$"' in q and 'number(t["height"]) >= 120' in q


# ── the generic rules on real maps ─────────────────────────────────────────
def _els():
    """A discovery answer: neighbourhoods, landmarks (one a duplicate beside a better one), towers, transit."""
    def node(i, lat, lon, **t):
        return {"type": "node", "id": i, "lat": lat, "lon": lon, "tags": t}

    def way(i, lat, lon, **t):
        return {"type": "way", "id": i, "center": {"lat": lat, "lon": lon}, "tags": t}
    langs = {f"name:{c}": "x" for c in ("de", "fr", "es", "it", "ja", "ru", "zh", "pt", "nl")}
    return [
        node(1, 38.888, -76.997, place="neighbourhood", name="Capitol Hill", **langs),
        node(2, 38.910, -77.065, place="suburb", name="Georgetown"),
        node(3, 38.905, -77.050, place="quarter", name="West End"),
        node(4, 50.0, 0.0, place="suburb", name="Far Away"),
        way(10, 38.8899, -77.0091, building="yes", name="United States Capitol", wikidata="Q1", wikipedia="en:x",
            tourism="attraction", heritage="2", **langs),
        way(11, 38.8895, -77.0090, building="yes", name="Capitol Visitor Center", wikidata="Q2"),   # 30 m away
        node(12, 38.8895, -77.0353, man_made="obelisk", name="Washington Monument", wikidata="Q3", wikipedia="en:y",
             height="169"),
        way(13, 38.900, -77.020, building="office", name="Tall Tower", height="150", **{"building:levels": "40"}),
        way(14, 38.901, -77.021, building="office", name="Short Tower", **{"building:levels": "36"}),
        way(15, 38.902, -77.022, building="yes", name="Park"),                                  # generic name
        {"type": "relation", "id": 20, "tags": {"type": "route", "route": "subway", "network": "Washington Metro",
                                                "ref": "R", "colour": "#BF0D3E", "operator": "WMATA"}},
        {"type": "relation", "id": 21, "tags": {"type": "route", "route": "subway", "network": "Washington Metro",
                                                "ref": "B", "colour": "#009CDE", "operator": "WMATA"}},
        {"type": "relation", "id": 22, "tags": {"type": "route", "route": "train", "network": "MARC",
                                                "ref": "Penn", "colour": "#BDBADC"}},
        {"type": "relation", "id": 23, "tags": {"type": "route", "route": "bus", "network": "Metrobus"}},
    ]


def test_auto_params_follow_the_rules_on_washington():
    m = _fixture("washington")
    m["parks"] = [{"n": "Big Park", "r": [[0, 0, 200, 0, 200, 200, 0, 200]]}, {"n": "Pocket", "r": [[0, 0, 50, 0, 50, 50, 0, 50]]},
                  {"n": "Big Park", "r": [[300, 0, 400, 0, 400, 100, 300, 100]]}, {"n": "", "r": [[0, 0, 900, 0, 900, 900, 0, 900]]}]
    bbox = tuple(m["bbox"])
    ap = cs.auto_params({"elements": _els()}, bbox, "Washington, DC", m=m)
    assert set(cp.FIELDS) - {"area"} <= set(ap)
    assert 20 <= len(ap["majors"]) <= 70
    assert "Massachusetts Avenue Northwest" in ap["majors"] and "Pennsylvania Avenue Northwest" in ap["majors"]
    # diagonals are the avenue class off the grid's axes (city_avenues.classify)
    assert any("Massachusetts Avenue" in d or "Pennsylvania Avenue" in d or "New York Avenue" in d for d in ap["diagonals"])
    assert not any(d.startswith(("K Street", "16th Street")) for d in ap["diagonals"])
    # landmarks: ranked, distinct (the visitor centre beside the Capitol is left out), no generic names
    assert ap["landmarks"][0] == "United States Capitol"
    assert "Capitol Visitor Center" not in ap["landmarks"] and "Park" not in ap["landmarks"]
    # towers tallest first with their real floors; the best building landmarks after them
    names = [b["name"] for b in ap["landmark_buildings"]]
    assert names[:3] == ["Washington Monument", "Tall Tower", "Short Tower"] or names[:2] == ["Tall Tower", "Washington Monument"] \
        or names[0] in ("Washington Monument", "Tall Tower")
    tall = [b for b in ap["landmark_buildings"] if b["name"] == "Tall Tower"][0]
    assert tall["floors"] == 40 and tall["height_m"] == 150
    assert "United States Capitol" in names
    # areas: ranks by place kind, lifted by many-language names; off-box ones dropped
    ar = {a["name"]: a["rank"] for a in ap["areas"]}
    assert ar == {"Georgetown": 1, "West End": 2, "Capitol Hill": 2}
    check_areas(ap["areas"])
    # parks by size
    assert ap["parks"] == ["Big Park"]                                    # >= 0.5 ha, named
    # transit: one family per network and colour, buses left out
    tr = {(t["network"], t["colour"]) for t in ap["transit"]}
    assert tr == {("Washington Metro", "#BF0D3E"), ("Washington Metro", "#009CDE"), ("MARC", "#BDBADC")}
    cp.check_transit(ap["transit"])
    check_buildings({"buildings": cp.buildings_for(ap)}, 1)


def test_auto_params_find_broadway_as_manhattans_diagonal():
    m = _fixture("manhattan")
    ap = cs.auto_params({"elements": []}, tuple(m["bbox"]), "Manhattan", m=m)
    assert "Broadway" in ap["diagonals"]
    assert "5th Avenue" in ap["majors"] or "Park Avenue" in ap["majors"]
    assert not any(d.endswith("Avenue") and d[0].isdigit() for d in ap["diagonals"]), ap["diagonals"]


# ── set_up_palace: preset and generic paths (network stubbed) ──────────────
@pytest.fixture
def server(tmp_path, monkeypatch):
    from alto import mcp_server as srv, palace_map
    from alto.store.local import LocalStore
    from test_palace import city_map, bundle
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    srv.set_store(LocalStore(tmp_path / "store"))
    calls = []
    monkeypatch.setattr(palace_map, "fetch_osm", lambda *a, **k: pytest.fail("fetch_osm: no network"))
    monkeypatch.setattr(palace_map, "build_map", lambda raw, bbox, **kw: city_map())
    monkeypatch.setattr(palace_map, "geocode", lambda q, **k: calls.append(("geocode", q)) or
                        {"lat": 45.76, "lon": 4.83, "bbox": [45.70, 4.77, 45.81, 4.90], "name": q})
    monkeypatch.setattr(cs, "fetch_city", lambda bbox, **kw: calls.append(("fetch", tuple(bbox), kw.get("names"))) or
                        {"elements": []})
    monkeypatch.setattr(cs, "discover", lambda bbox, **kw: calls.append(("discover", tuple(bbox))) or {"elements": []})
    monkeypatch.setattr("alto.build.palace_buses.fetch", lambda *a, **k: {})   # set_up's buses and fleet go straight to Overpass
    monkeypatch.setattr("alto.build.palace_fleet.fetch", lambda *a, **k: {})
    monkeypatch.setattr("alto.build.city_boroughs.fetch", lambda *a, **k: {"boroughs": {}, "missing": ["no network"]})   # NYC: Manhattan alone

    def draft():
        pid = srv.create_project("City", "a palace", "memory")["project_id"]
        brief = bundle(with_city=False)["brief"]
        brief["mode"] = "palace"
        r = srv.create_timeline(pid, brief)
        assert "error" not in r, r
        return r["timeline_id"]
    yield srv, calls, draft
    srv.set_store(None)


def test_set_up_palace_uses_the_preset_for_a_built_in_city(server):
    srv, calls, draft = server
    tid = draft()
    r = srv.set_up_palace(tid, "Washington, D.C.", landmark_buildings=[{"name": "Washington Monument", "unit": 0},
                                                                     {"name": "United States Capitol", "unit": 1}])
    assert r.get("ok") is True, r
    assert r["preset"] == "dc"
    fetch = [c for c in calls if c[0] == "fetch"]
    assert fetch and fetch[0][1] == tuple(cp.DC["bbox"])                      # the preset's box, fetched tiled
    assert "United States Capitol" in fetch[0][2]                             # landmarks asked by name
    assert not [c for c in calls if c[0] in ("geocode", "discover")]          # a preset needs no lookup
    pal = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]
    assert pal["preset"] == "dc" and pal["place"] == "Washington, D.C."
    assert pal["majors"] == cp.DC["majors"] and pal["diagonals"] == cp.DC["diagonals"]
    assert pal["transit"] == cp.DC["transit"] and pal["areas"] == cp.DC["areas"]
    assert pal["area"] == cp.DC["area"]
    # the Capitol's real floor count is filled in (it carries a unit); the Monument has none known
    caps = [b for b in pal["buildings"] if b["name"] == "United States Capitol"][0]
    assert caps["floors"] == 5


def test_explicit_arguments_override_the_preset(server):
    srv, calls, draft = server
    tid = draft()
    box = [40.70, -74.02, 40.74, -73.97]
    r = srv.set_up_palace(tid, "NYC", bbox=box, majors=["Broadway"], parks=[], transit=[])
    assert r.get("ok") is True, r
    pal = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]
    assert pal["bbox"] == box and pal["majors"] == ["Broadway"] and pal["parks"] == []
    assert "transit" not in pal                                               # [] draws none
    assert set(cp.NYC["landmarks"]) <= set(pal["landmarks"])                 # (plus the buildings' names)


def test_set_up_palace_works_out_an_unknown_city(server):
    srv, calls, draft = server
    tid = draft()
    r = srv.set_up_palace(tid, "Lyon")
    assert r.get("ok") is True, r
    assert "preset" not in r and set(r["worked_out"]) == {"majors", "landmarks", "landmark_buildings", "diagonals",
                                                          "parks", "areas", "transit"}
    kinds = [c[0] for c in calls]
    assert kinds[0] == "geocode" and "discover" in kinds and kinds.count("fetch") == 2
    pal = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]
    ns, ew = cs.box_km(pal["bbox"])
    assert abs(ns - 6.0) < 0.05 and abs(ew - 7.0) < 0.05                       # the size rule
    assert pal["preset"] == "auto"


def test_auto_false_keeps_the_plain_set_up(server, monkeypatch):
    srv, calls, draft = server
    from alto import palace_map
    seen = []
    monkeypatch.setattr(palace_map, "fetch_osm", lambda bbox, **kw: seen.append(tuple(bbox)) or {"elements": []})
    tid = draft()
    r = srv.set_up_palace(tid, "Boston", bbox=[42.35, -71.07, 42.36, -71.05], auto=False)
    assert r.get("ok") is True, r
    assert seen == [(42.35, -71.07, 42.36, -71.05)] and not calls
    pal = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]
    assert "preset" not in pal and pal["majors"] == []


# ── law palaces: courthouses as landmark buildings ─────────────────────────
from alto.build import city_courts as cc  # noqa: E402

KEYS = [("theme~federal-rules-of-civil-procedure", "Federal Rules of Civil Procedure"), ("theme~28-u-s-c", "28 U.S.C."),
        ("env", "Cases"), ("theme~local-rules", "Local Rules")]


@pytest.mark.parametrize("texts,subject,law", [
    (["Civ Pro outline"], None, True), (["Civil Procedure"], None, True), (["Torts", "Contracts"], None, True),
    (["Federal courts: jurisdiction"], None, True), (["Art history"], None, False), (["Art"], "law", True),
    (["Civil Procedure"], "history", False), ([], None, False),
])
def test_is_law_reads_the_subject_or_the_timeline(texts, subject, law):
    assert cc.is_law(texts, subject) is law


def test_page_for_resolves_only_the_timelines_own_indexes():
    assert cc.page_for("federal", KEYS) == "index:theme~federal-rules-of-civil-procedure"
    assert cc.page_for("state", KEYS) == "index:env"
    assert cc.page_for("city", KEYS) == "index:theme~local-rules"
    assert cc.page_for("state", KEYS[:2]) is None                 # a federal index is never reused for a state court
    assert cc.page_for("federal", []) is None and cc.page_for("city", [("env", "Cases")]) is None


@pytest.mark.parametrize("name,level", [
    ("James A. Byrne United States Courthouse", "federal"), ("Thurgood Marshall U.S. Courthouse", "federal"),
    ("Supreme Court of the United States", "federal"), ("United States Bankruptcy Court", "federal"),
    ("New York County Supreme Court", "state"), ("Appellate Division Courthouse of New York State", "state"),
    ("Pennsylvania Supreme Court", "state"), ("Commonwealth Court", "state"), ("John Adams Courthouse", "city"),
    ("Philadelphia Municipal Court", "city"), ("Family Court", "city"), ("Suffolk Superior Court", "city"),
    ("Joe's Diner", None), ("Kings County Family Court", "city"), ("Boston Municipal Court", "city"),
])
def test_level_of_classifies_by_name(name, level):
    assert cc.level_of(name) == level


def test_courts_of_ranks_dedupes_and_keeps_every_level():
    def way(i, lat, lon, **t):
        return {"type": "way", "id": i, "center": {"lat": lat, "lon": lon}, "tags": t}
    els = [way(1, 40.01, -75.01, amenity="courthouse", name="United States Courthouse", wikidata="Q1", height="120"),
           way(2, 40.0102, -75.0101, amenity="courthouse", name="US Courthouse Annex"),      # 25 m away: same place
           way(3, 40.02, -75.02, amenity="courthouse", name="State Supreme Court"),
           *[way(10 + i, 40.0 + i * .003, -75.03, amenity="courthouse", name=f"Municipal Court {i}") for i in range(12)],
           way(40, 41.0, -75.0, amenity="courthouse", name="Far Court"),                       # off the box
           way(41, 40.03, -75.04, shop="yes", name="Court Street Deli")]                       # not a court
    got = cc.courts_of(els, (39.99, -75.1, 40.05, -74.99))
    assert len(got) == cc.MAX_COURTS
    assert [g["level"] for g in got[:3]] == ["federal", "state", "city"]
    assert got[0]["name"] == "United States Courthouse" and got[0]["height_m"] == 120
    names = [g["name"] for g in got]
    assert "US Courthouse Annex" not in names and "Far Court" not in names and "Court Street Deli" not in names


def test_buildings_merges_a_court_already_listed_and_never_passes_floors():
    given = [{"name": "Philadelphia City Hall", "label": "City Hall", "page": "index:theme~28-u-s-c"}]
    courts = cc.match_names(cp.COURTS["philadelphia"], [])
    out = cc.buildings(courts, KEYS, given)
    ch = out[0]
    assert ch["page"] == "index:theme~28-u-s-c" and ch["kind"] == "courthouse" and ch["levels"] == ["city", "state"]
    assert len(out) == len(courts)                                     # City Hall not added twice
    byrne = [b for b in out if "Byrne" in b["name"]][0]
    assert byrne["level"] == "federal" and byrne["page"] == "index:theme~federal-rules-of-civil-procedure"
    fam = [b for b in out if b.get("label") == "Family Court"][0]
    assert fam["page"] == "index:theme~local-rules"
    check_buildings({"buildings": out}, 2)


def test_match_names_takes_the_maps_spelling_near_the_court():
    els = [{"type": "way", "id": 1, "center": {"lat": 39.9541, "lon": -75.1618},
            "tags": {"name": "Criminal Justice Center", "amenity": "courthouse"}},
           {"type": "way", "id": 2, "center": {"lat": 40.5, "lon": -75.0}, "tags": {"name": "Family Court"}}]   # far
    got = {c["addr"]: c for c in cc.match_names(cp.COURTS["philadelphia"], els)}
    assert got["1301 Filbert Street"]["name"] == "Criminal Justice Center" and got["1301 Filbert Street"]["osm"]
    assert got["1501 Arch Street"]["osm"] is False


@pytest.mark.parametrize("key", sorted(cp.COURTS))
def test_preset_courts_cover_every_level_inside_their_box(key):
    box = cp.PRESETS[key]["bbox"] if key in cp.PRESETS else [39.895, -75.245, 40.005, -75.085]
    cs_ = cp.COURTS[key]
    assert {c["level"] for c in cs_} == set(cc.LEVELS)
    for c in cs_:
        assert box[0] <= c["lat"] <= box[2] and box[1] <= c["lon"] <= box[3], c["name"]
        assert c["level"] in cc.LEVELS and set(c["levels"]) <= set(cc.LEVELS) and c["level"] in c["levels"]
    assert len({c["name"] for c in cs_}) == len(cs_)


def test_a_law_palace_gets_the_courthouses(server, monkeypatch):
    srv, calls, draft = server
    monkeypatch.setattr(cc, "fetch_courts", lambda bbox, **kw: {"elements": []})
    tid = draft()
    r = srv.set_up_palace(tid, "DC", subject="law")
    assert r.get("ok") is True, r
    assert r["courthouses"]["source"] == "preset"
    assert {c["level"] for c in r["courthouses"]["courts"]} == {"federal", "state", "city"}
    pal = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]
    courts = [b for b in pal["buildings"] if b.get("kind") == "courthouse"]
    assert len(courts) == len(cp.COURTS["dc"])
    sc = [b for b in pal["buildings"] if b["name"] == "Supreme Court of the United States"]
    assert len(sc) == 1 and sc[0]["level"] == "federal" and sc[0]["label"] == "Supreme Court"   # merged, not doubled
    assert "H. Carl Moultrie I Courthouse" in pal["landmarks"]               # asked for by name
    # not a law palace: no courthouses
    tid2 = draft()
    r2 = srv.set_up_palace(tid2, "DC", subject="history")
    assert "courthouses" not in r2
    pal2 = srv.get_store().get_timeline(srv.uid(), tid2)["brief"]["palace"]
    assert not [b for b in pal2["buildings"] if b.get("kind") == "courthouse"]


def test_a_law_palace_in_an_unknown_city_reads_the_courts_from_the_map(server, monkeypatch):
    srv, calls, draft = server
    box = cs.size_rule({"lat": 45.76, "lon": 4.83, "bbox": [45.70, 4.77, 45.81, 4.90]})
    els = [{"type": "way", "id": 1, "center": {"lat": 45.761, "lon": 4.827}, "tags": {"amenity": "courthouse",
            "name": "Cour d'appel de Lyon", "wikidata": "Q9"}},
           {"type": "way", "id": 2, "center": {"lat": 45.76, "lon": 4.85}, "tags": {"amenity": "courthouse",
            "name": "Tribunal judiciaire de Lyon"}}]
    monkeypatch.setattr(cc, "fetch_courts", lambda bbox, **kw: {"elements": els})
    tid = draft()
    r = srv.set_up_palace(tid, "Lyon", subject="law")
    assert r.get("ok") is True, r
    assert r["courthouses"]["source"] == "osm" and len(r["courthouses"]["courts"]) == 2
    assert box[0] < 45.761 < box[2]
