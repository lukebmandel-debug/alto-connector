"""2.0.0 street accuracy block: city open data (palace_street_city, stubbed: no network), joins, typology, party walls, front edges, the record's new fields in both
decoders, and the never-fatal / offline / cached behaviour."""
import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from alto.build import palace_street as ps, palace_street_acc as acc, palace_street_city as pc, palace_street_style as sty
from alto.build.palace_street_js import STREET_JS

BBOX = (39.9489, -75.1731, 39.9633, -75.1505)
NODE = Path.home() / ".local" / "node" / "bin" / "node"
D = 0.00005          # ~4.3 m of longitude, ~5.5 m of latitude


def _box(la, lo, w=D, h=0.0001):
    return [{"lat": la, "lon": lo}, {"lat": la, "lon": lo + w}, {"lat": la + h, "lon": lo + w}, {"lat": la + h, "lon": lo}, {"lat": la, "lon": lo}]


LA, LO = 39.9500, -75.1700
ROW = [{"type": "way", "id": 100 + i, "geometry": _box(LA, LO + i * D),
        "tags": {"building": "yes", "addr:housenumber": str(2001 + 2 * i), "addr:street": "Spruce Street"}} for i in range(5)]
LONE = {"type": "way", "id": 200, "geometry": _box(LA + 0.001, LO, 0.0002, 0.0002), "tags": {"building": "house", "roof:shape": "gabled", "architect": "Frank Furness",
                                                                                              "heritage": "2", "ref:nrhp": "123", "wikipedia": "en:Somewhere", "roof:direction": "S"}}
TOWER = {"type": "way", "id": 300, "geometry": _box(LA + 0.003, LO, 0.0006, 0.0006), "tags": {"building": "yes"}}
BLD = {"elements": ROW + [LONE, TOWER]}
ROAD = {"type": "way", "id": 50, "tags": {"highway": "residential", "name": "Spruce Street"}, "geometry": [{"lat": LA - 0.00005, "lon": LO - 0.001}, {"lat": LA - 0.00005, "lon": LO + 0.001}]}
ST = {"elements": [ROAD]}
OPA = [dict(lat=LA + 0.00005, lon=LO + i * D + D / 2, hn=str(2001 + 2 * i), dir="", name="SPRUCE", suf="ST", yr=1870, yre=0, st=3, bc="ROW 3 STY MASONRY", bcn="",
            cat="SINGLE FAMILY", ex=4, fr=14.0, dp=60, la=1500) for i in range(5)]
OPA.append(dict(lat=LA + 0.0033, lon=LO + 0.0003, hn="1", dir="", name="X", suf="ST", yr=1990, yre=0, st=0, bc="OFF BLD COM NO GAR MASON", bcn="", cat="COMMERCIAL", ex=3,
                fr=200, dp=200, la=1))
LIF = [dict(lat=LA + 0.0033, lon=LO + 0.0003, ad="1 X ST", nm="Tower", ah=150.0, mh=160.0, be=12.0, ar=5000)]


def _cells(man, shards):
    return {k: ps.decode_cell(man, k, shards) for k in man["c"]}


def _blds(man, shards):
    return [b for c in _cells(man, shards).values() for b in c["b"]]


def test_streets_and_codes_normalise():
    assert acc.norm_street("South 15th Street") == ("S", "15TH", "ST")
    assert acc.norm_street("John F. Kennedy Boulevard") == ("", "JOHN F KENNEDY", "BLVD")
    assert acc.house_numbers("1301-1319") == [1301, 1319] and acc.house_numbers("12A") == [12]
    assert acc.opa_typology("ROW 3 STY MASONRY")[:2] == (acc.TY["rowhouse"], 3)
    assert acc.opa_typology("ROW 2.5 STY MASONRY")[:3] == (acc.TY["rowhouse"], 2, True)
    assert acc.opa_typology("TWIN 2 STY MASONRY")[0] == acc.TY["twin"]
    assert acc.opa_typology("RES CONDO 5+ STY MASONRY")[0] == acc.TY["midrise"] and not acc.opa_typology("RES CONDO 5+ STY MASONRY")[3]
    assert acc.opa_typology("HOTEL 10-14 STY MASONRY")[:2] == (acc.TY["hotel"], 12)
    assert acc.opa_typology("HSE WORSHIP ALL 2 STY MAS")[0] == acc.TY["religious"]
    assert acc.opa_typology("MISC COURT HOUSE MASONRY")[0] == acc.TY["civic"]
    assert acc.opa_typology("STR/OFF+APT 3 STY MASONRY")[0] == acc.TY["mixed_use"]
    assert acc.opa_typology("CONDO PARKING SPACE")[0] == 0 and acc.opa_typology("VACANT LAND RESIDE < ACRE")[0] == 0
    assert [acc.era_of(y) for y in (0, 1790, 1850, 1925, 1960, 2010)] == [0, 1, 2, 3, 4, 5]
    assert acc.pitch_of({"roof:shape": "flat"}) == 1 and acc.pitch_of({"roof:shape": "mansard"}) == 4 and acc.pitch_of({"roof:angle": "35"}) == 3


def test_party_walls_and_the_front_edge_of_a_row():
    rings = [[(i * 50, 0), (i * 50 + 50, 0), (i * 50 + 50, 100), (i * 50, 100)] for i in range(4)]       # CCW, front (edge 0) on y=0
    pw = acc.party_walls(rings)
    assert [m for m, _n in pw] == [0b0010, 0b1010, 0b1010, 0b1000]                                       # edge 1 = east side, edge 3 = west side
    assert pw[1][1] == {0, 2}
    fe = acc.front_edges(rings, [(-500, -60, 1000, -60)], [m for m, _n in pw])
    assert fe == [0, 0, 0, 0]
    # standing in the street (south) facing north: west is on the left, east on the right
    assert acc.side_flags(rings[0], 0, pw[0][0]) == acc.PW_RIGHT
    assert acc.side_flags(rings[3], 0, pw[3][0]) == acc.PW_LEFT
    assert acc.side_flags(rings[1], 0, pw[1][0]) == acc.PW_LEFT | acc.PW_RIGHT
    cw = [list(reversed(r)) for r in rings]                                                              # the same row drawn clockwise
    pwc = acc.party_walls(cw)
    fc = acc.front_edges(cw, [(-500, -60, 1000, -60)], [m for m, _n in pwc])
    assert acc.side_flags(cw[0], fc[0], pwc[0][0]) == acc.PW_RIGHT
    assert acc.side_flags([(0, 0), (50, 0), (50, 100), (0, 100)], 0, 0) == acc.PW_FREE


def test_city_records_fill_the_block_and_both_decoders_agree(tmp_path):
    rep = {}
    man, shards = ps.build(BBOX, BLD, ST, city={"opa": OPA, "lif": LIF, "notes": ["n1"]}, report=rep)
    bs = sorted(_blds(man, shards), key=lambda b: (b["ring"][0][1], b["ring"][0][0]))
    rows = [b for b in bs if b["ad"].endswith("Spruce Street")]
    assert len(rows) == 5
    for i, b in enumerate(rows):
        assert b["typology"] == "rowhouse" and b["yr"] == 1870 and b["era"] == "victorian" and b["st"] == 3 and b["ss"] == 2
        assert b["hs"] == 4 and abs(b["hm"] - 10.9) < 0.11 and b["lv"] == 3
        assert b["cf"] & acc.CF_PARCEL and b["cf"] & acc.CF_ADDR and b["cf"] & acc.CF_YEAR and b["cf"] & acc.CF_STORIES and not b["cf"] & acc.CF_HEIGHT
        assert abs(b["frm"] - 14 * 0.3048) < 0.1 and b["by"] == 3 and b["ex"] == 4 and b["pc"] == 1
        assert b["front"] >= 0 and b["fe"] == b["front"] + 1
        assert b["pw"] == ({0: acc.PW_RIGHT, 4: acc.PW_LEFT}.get(i, acc.PW_LEFT | acc.PW_RIGHT))
        assert len(b["party"]) == (1 if i in (0, 4) else 2) and b["front"] not in b["party"]
        assert b["material"] in ("brick", "brownstone", "stone", "stucco", "painted")
    tower = [b for b in bs if b["k"] == "yes" and not b["ad"]][0]
    assert tower["hs"] == 2 and abs(tower["hm"] - 150) < 0.1 and tower["typology"] == "office" and tower["cf"] & acc.CF_HEIGHT and tower["yr"] == 1990
    assert tower["material"] in ("glass", "metal", "concrete") and tower["era"] == "contemporary"
    lone = [b for b in bs if b["k"] == "house"][0]
    assert lone["typology"] == "detached" and lone["pw"] == acc.PW_FREE and lone["pc"] == 3 and lone["cf"] & acc.CF_ROOF
    assert lone["ar"] == "Frank Furness" and lone["hr"] == "heritage=2;nrhp=123" and lone["wp"] == "en:Somewhere" and lone["rd"] == 181
    assert rep["n"] == 7 and rep["typology"] == 100.0 and rep["parcel_by_address"] > 70 and rep["notes"] == ["n1"]
    assert man["src"][0]["k"] == "osm" and {s["k"] for s in man["src"]} == {"osm", "opa", "lif"} and all(s["l"] and s["a"] for s in man["src"])
    assert "City of Philadelphia" in man["a"] and man["sn"] == ["n1"]
    if not (NODE.exists() or shutil.which("node")):
        return
    node = str(NODE) if NODE.exists() else shutil.which("node")
    src = tmp_path / "t.js"
    src.write_text("var window={}; " + STREET_JS + "\nvar S=window._palStreet; var man=%s, sh=%s; S.use(man, sh); var out=[];"
                   "for(var k in man.c){ var p=k.split(','); S.cell(+p[0],+p[1]).b.forEach(function(b){ out.push([b.ad,b.ty,b.typology,b.yr,b.era,b.st,b.ss,b.hs,b.fr,b.by,b.pe,"
                   "b.fe,b.front,b.pw,b.pc,b.rd,b.cf,b.ar,b.hr,b.wp,b.ex,b.party(0),b.party(1),b.party(3)]); }); }"
                   "console.log(JSON.stringify(out));" % (json.dumps(man), json.dumps(shards)))
    js = json.loads(subprocess.run([node, str(src)], capture_output=True, text=True, check=True).stdout)
    py = [[b["ad"], b["ty"], b["typology"], b["yr"], b["era"], b["st"], b["ss"], b["hs"], b["fr"], b["by"], b["pe"], b["fe"], b["front"], b["pw"], b["pc"], b["rd"], b["cf"],
           b["ar"], b["hr"], b["wp"], b["ex"], 0 in b["party"], 1 in b["party"], 3 in b["party"]] for c in (_cells(man, shards)[k] for k in man["c"]) for b in c["b"]]
    assert sorted(map(json.dumps, js)) == sorted(map(json.dumps, py))


def test_an_old_client_reads_the_first_sixteen_fields_and_ignores_the_rest():
    man, shards = ps.build(BBOX, BLD, ST, city={"opa": OPA, "lif": LIF})
    for sh in shards.values():
        for c in sh["c"].values():
            for rec in c.get("b", []):
                old = dict(zip(ps.BFIELDS[:16], rec[1][:16] + [0] * (16 - len(rec[1][:16]))))
                assert isinstance(old["k"], int) and len(ps.BFIELDS) >= 16 and ps.BFIELDS[:16] == ("k", "lv", "h", "bc", "bm", "rs", "rc", "rm", "rl", "nm", "ad", "po", "sd",
                                                                                                     "wd", "fl", "mh")


def test_without_city_data_osm_alone_still_gives_a_typology():
    man, shards = ps.build(BBOX, BLD, ST)
    bs = _blds(man, shards)
    rows = [b for b in bs if b["ad"].endswith("Spruce Street")]
    assert {b["typology"] for b in rows} == {"rowhouse"} and all(b["hs"] == 5 for b in rows) and not any(b["cf"] & acc.CF_PARCEL for b in rows)
    assert {s["k"] for s in man["src"]} == {"osm"} and man["a"] == ps.ATTRIBUTION


def test_typology_and_era_drive_the_palette():
    def mats(ty, yr, n=300):
        return [sty.MATERIALS[sty.resolve("philadelphia", {"building": "yes"}, 80, 10.0, 3, sty.seed_of(i), ty=ty, year=yr)["bm"]] for i in range(n)]
    vic = mats(1, 1870)
    assert vic.count("brick") / 300 > 0.55 and vic.count("brownstone") > 15 and "glass" not in vic
    assert "brownstone" not in mats(1, 1795) and mats(1, 1795).count("brick") / 300 > 0.8
    assert set(mats(6, 2015)) <= {"glass", "metal", "concrete"} and mats(6, 2015).count("glass") / 300 > 0.5
    assert set(mats(6, 1928)) <= {"stone", "brick"}
    assert set(mats(11, 1990)) <= {"concrete", "brick"}
    assert sty.resolve("philadelphia", {"building": "yes", "building:material": "glass"}, 80, 10.0, 3, 1, ty=1, year=1870)["bm"] == sty.MAT["glass"]     # OSM wins


def _stub_city(monkeypatch, answers):
    asked = []

    def get(url, timeout=60):
        asked.append(url)
        a = answers(url)
        if isinstance(a, Exception):
            raise a
        return a
    monkeypatch.setattr(pc, "_get", get)
    monkeypatch.setattr(pc, "_sleep", lambda s: None)
    return asked


def test_city_fetch_caches_each_tile_and_works_offline_after(tmp_path, monkeypatch):
    def ans(url):
        if "carto" in url:
            return {"rows": [{"house_number": "12", "street_direction": None, "street_name": "WALNUT", "street_designation": "ST", "year_built": "1925",
                              "year_built_estimate": "Y", "number_stories": 3, "building_code_description": "ROW 3 STY MASONRY", "lat": 39.95, "lon": -75.16}]}
        return {"features": [{"attributes": {"address": "12 WALNUT ST", "approx_hgt": 30, "max_hgt": 33, "base_elevation": 40, "Shape__Area": 80},
                              "centroid": {"x": -75.16, "y": 39.95}}]}
    asked = _stub_city(monkeypatch, ans)
    rows, note = pc.opa(BBOX, directory=tmp_path)
    n = len(asked)
    assert note == "" and n >= 1 and rows and rows[0]["yr"] == 1925 and rows[0]["yre"] == 1 and rows[0]["st"] == 3
    lrows, note = pc.lif(BBOX, directory=tmp_path)
    assert note == "" and abs(lrows[0]["ah"] - 30 * 0.3048) < 0.05
    asked.clear()
    rows2, note = pc.opa(BBOX, directory=tmp_path, offline=True)
    assert rows2 == rows and asked == [] and note == ""
    rows3, note = pc.opa((40.5, -75.0, 40.51, -74.99), directory=tmp_path, offline=True)
    assert rows3 == [] and "offline" in note and asked == []


def test_a_failing_city_server_is_left_alone_and_never_fatal(tmp_path, monkeypatch):
    asked = _stub_city(monkeypatch, lambda url: RuntimeError("503"))
    rows, note = pc.opa((39.90, -75.25, 40.00, -75.08), directory=tmp_path)
    assert rows == [] and "not available" in note and len(asked) == 2                 # two failures in a row: nothing more is asked
    monkeypatch.setattr(pc, "_fetch", lambda *a, **k: 1 / 0)
    assert pc.lif(BBOX, directory=tmp_path)[0] == []
    monkeypatch.setenv("ALTO_CITY_DIR", str(tmp_path))
    c = ps.city_data(BBOX)
    assert c["opa"] == [] and c["lif"] == [] and len(c["notes"]) >= 2
    assert ps.city_data((48.8, 2.3, 48.9, 2.4)) is None                                  # not Philadelphia: nothing asked
    monkeypatch.setenv("ALTO_STREET_CITY", "0")
    assert ps.city_data(BBOX) is None


def test_the_block_costs_little():
    man, shards = ps.build(BBOX, BLD, ST, city={"opa": OPA, "lif": LIF})
    per = sum(man["f"].values()) / 7
    assert per < 400
    assert len(gzip.compress("".join(ps.encode(s) for s in shards.values()).encode())) < 4000


def test_spot_check_regressions_landmarks_and_office_codes():
    assert acc.opa_typology("OFF BLD N/PKG N/COM MASON")[0] == acc.TY["office"]                         # N/PKG = no parking, not a garage
    assert acc.opa_typology("PD PKG LOT COMMERCIAL")[0] == acc.TY["parking"]
    assert acc.choose_typology(acc.TY["parking"], acc.TY["civic"], "civic") == acc.TY["civic"]           # City Hall's parcel record names a garage
    assert acc.choose_typology(acc.TY["religious"], acc.TY["highrise"], "apartments") == acc.TY["highrise"]
    assert acc.choose_typology(acc.TY["rowhouse"], acc.TY["twin"], "house") == acc.TY["rowhouse"]       # the city's code is the finer one at home
    assert acc.choose_typology(acc.TY["office"], acc.TY["midrise"], "yes") == acc.TY["office"]
    assert acc.storey_m(1, 2) > acc.storey_m(1, 5) and acc.storey_m(8, 0) == 4.5
    ring = _box(LA + 0.002, LO, 0.0004, 0.0004)
    hist = {"type": "way", "id": 900, "geometry": ring, "tags": {"building": "yes", "ref:nrhp": "1", "height": "16"}}
    opa = [dict(lat=LA + 0.0022, lon=LO + 0.0002, hn="9", dir="", name="Z", suf="ST", yr=2015, yre=0, st=0, bc="OFF BLD N/PKG N/COM MASON", bcn="", cat="COMMERCIAL", ex=3,
                fr=0, dp=0, la=1)]
    man, shards = ps.build(BBOX, {"elements": [hist]}, {"elements": []}, city={"opa": opa, "lif": []})
    b = _blds(man, shards)[0]
    assert b["yr"] == 0 and not b["cf"] & acc.CF_YEAR                                                    # a listed building "built in 2015": the record is of something else
    assert b["st"] == 5 and b["ss"] == 4 and b["lv"] == 5                                                # 16 m / 3.3 (an office; no era)


# ── Wikidata (stubbed) ──────────────────────────────────────────────────────
from alto.build import palace_street_wikidata as pwd


def _wd_answers(url):
    if "sparql" in url:
        return {"results": {"bindings": [{"item": {"value": "http://www.wikidata.org/entity/Q20"}, "coord": {"value": "Point(-75.1696 39.9512)"}},
                                          {"item": {"value": "http://www.wikidata.org/entity/Q30"}, "coord": {"value": "Point(-75.1690 39.9512)"}}]}}
    if "props=labels&" in url or url.endswith("props=labels"):
        return {"entities": {q: {"labels": {"en": {"value": lab}}} for q, lab in (("Q100", "Second Empire architecture"), ("Q101", "John McArthur Jr."),
                                                                                    ("Q102", "National Historic Landmark"), ("Q103", "city hall"), ("Q104", "organization"))}}
    def ent(yr, h, fl, inst):
        tm = lambda y: {"mainsnak": {"datavalue": {"value": {"time": "+%d-00-00T00:00:00Z" % y}}}, "rank": "normal"}
        return {"labels": {"en": {"value": "x"}}, "claims": {
            "P571": [tm(yr)], "P580": [tm(yr - 30)] if yr > 1900 else [],
            "P2048": [{"mainsnak": {"datavalue": {"value": {"amount": "+%s" % h, "unit": "http://www.wikidata.org/entity/Q3710"}}}, "rank": "normal"}] if h else [],
            "P1101": [{"mainsnak": {"datavalue": {"value": {"amount": "+%d" % fl, "unit": "1"}}}, "rank": "normal"}] if fl else [],
            "P149": [{"mainsnak": {"datavalue": {"value": {"id": "Q100"}}}, "rank": "normal"}], "P84": [{"mainsnak": {"datavalue": {"value": {"id": "Q101"}}}, "rank": "normal"}],
            "P1435": [{"mainsnak": {"datavalue": {"value": {"id": "Q102"}}}, "rank": "normal"}], "P31": [{"mainsnak": {"datavalue": {"value": {"id": inst}}}, "rank": "normal"}]}}
    return {"entities": {"Q10": ent(1901, 548, 9, "Q103"), "Q20": ent(1753, 0, 2, "Q103"), "Q30": ent(1914, 0, 0, "Q104")}}


def test_wikidata_overrides_the_parcel_for_landmarks_and_is_cached(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(pwd, "_get", lambda url, timeout=60: asked.append(url) or _wd_answers(url))
    monkeypatch.setattr(pwd, "_sleep", lambda s: None)
    hall = {"type": "way", "id": 700, "geometry": _box(LA + 0.0010, LO + 0.0010, 0.0004, 0.0004), "tags": {"building": "yes", "wikidata": "Q10", "height": "20"}}
    tagless = {"type": "way", "id": 701, "geometry": _box(LA + 0.0010, LO + 0.0002, 0.0003, 0.0003), "tags": {"building": "yes"}}
    org = {"type": "way", "id": 702, "geometry": _box(LA + 0.0010, LO + 0.0008, 0.0001, 0.0003), "tags": {"building": "yes"}}
    bld = {"elements": [hall, tagless, org]}
    wd = ps.wikidata_data(BBOX, bld, directory=tmp_path)
    assert set(wd["wd"]) == {"Q10", "Q20", "Q30"} and len(wd["wdp"]) == 2 and wd["notes"] == []
    opa = [dict(lat=LA + 0.0012, lon=LO + 0.0012, hn="1", dir="", name="Z", suf="ST", yr=2015, yre=0, st=0, bc="PD PKG LOT COMMERCIAL", bcn="", cat="COMMERCIAL", ex=3,
                fr=0, dp=0, la=1)]
    man, shards = ps.build(BBOX, bld, {"elements": []}, city={"opa": opa, "lif": [], "wd": wd["wd"], "wdp": wd["wdp"]})
    bs = {b["ring"][0][0] // 1: b for b in _blds(man, shards)}
    h = [b for b in bs.values() if b["wd"] == "Q10"][0]
    assert h["yr"] == 1871 and h["era"] == "victorian" and h["typology"] == "civic" and h["sy"] == "Second Empire architecture" and h["ar"] == "John McArthur Jr."
    assert h["hm"] == 20 and abs(h["tpm"] - 548 * 0.3048) < 0.2 and "wd=National Historic Landmark" in h["hr"]
    t = [b for b in bs.values() if b["wd"] == "" and b["yr"] == 1753]
    assert len(t) == 1 and t[0]["st"] == 2 and t[0]["ss"] == 5                              # joined by position
    assert not [b for b in bs.values() if b["yr"] == 1914]                                   # an organisation's point is not a building
    assert {s["k"] for s in man["src"]} >= {"osm", "wikidata"} and [s for s in man["src"] if s["k"] == "wikidata"][0]["l"] == "CC0 1.0"
    asked.clear()
    wd2 = ps.wikidata_data(BBOX, bld, directory=tmp_path, offline=True)                     # cached: offline gives the same, nothing asked
    assert wd2["wd"] == wd["wd"] and asked == []


def test_a_lagged_or_failing_wikidata_is_never_fatal(tmp_path, monkeypatch):
    calls = []

    def lag(url, timeout=60):
        calls.append(url)
        raise RuntimeError("wikidata: {'code': 'maxlag'}")
    monkeypatch.setattr(pwd, "_get", lag)
    monkeypatch.setattr(pwd, "_sleep", lambda s: None)
    recs, note = pwd.items(["Q%d" % i for i in range(1, 200)], directory=tmp_path)
    assert recs == {} and "not available" in note and len(calls) == 6                      # 2 batches x 3 tries (maxlag retries), then it gives up
    assert pwd.in_box(BBOX, directory=tmp_path)[0] == [] and pwd.in_box(BBOX, directory=tmp_path, offline=True)[1]


def test_a_spire_part_is_the_top_not_the_body():
    body = {"type": "way", "id": 800, "geometry": _box(LA + 0.002, LO, 0.0004, 0.0004), "tags": {"building": "yes"}}
    hall = {"type": "way", "id": 801, "geometry": _box(LA + 0.002, LO, 0.0004, 0.0003), "tags": {"building:part": "yes", "height": "15"}}
    spire = {"type": "way", "id": 802, "geometry": _box(LA + 0.00235, LO + 0.00015, 0.00005, 0.00004), "tags": {"building:part": "yes", "height": "51"}}
    man, shards = ps.build(BBOX, {"elements": [body, hall, spire]}, {"elements": []})
    b = [x for x in _blds(man, shards) if x["k"] == "yes"][0]
    assert b["hm"] == 15 and b["tpm"] == 51 and b["hs"] == 1
