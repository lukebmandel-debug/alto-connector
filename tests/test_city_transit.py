"""City-generic transit (C2): presets, auto-discovery of families from OSM route relations, and Philadelphia's
1.9.78 reading kept byte for byte."""
import gzip
import hashlib
import json
import math
from pathlib import Path

from alto import palace_map as pm
from alto.build import city_transit_data as ctd
from alto.build import palace_transit as pt
from alto.build.palace_transit_audit import picture

FIX = Path(__file__).parent / "fixtures" / "transit" / "philly_transit_raw.json.gz"
PHILLY_BBOX = (39.895, -75.245, 40.005, -75.085)
# sha256 of palace_map._transit on the fixture with the 1.9.78 (pre-C2) code, recorded before the change
PHILLY_SHA = {1.0: "fde21530cebfdbd21e31ddf2bdc307b7154c9fe4340cc288f0f3c66b91f4ea8e",
              1.6: "2824d0c33809ada08cac1405d4fae8c74be0b1b589f421d3ed14a987b6ade56e"}


def _sha(t):
    return hashlib.sha256(json.dumps(t, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _read(raw, bbox, **kw):
    proj, W, H = pm._projector(bbox, kw.pop("scale", 1.0))
    return pm._transit(pm._merge_elements(raw), proj, W, H, **kw)


def test_philadelphia_reading_is_byte_identical():
    raw = json.load(gzip.open(FIX, "rt"))
    for sc, sha in PHILLY_SHA.items():
        assert _sha(_read(raw, PHILLY_BBOX, scale=sc, place="Philadelphia")) == sha
        assert _sha(_read(raw, PHILLY_BBOX, scale=sc, place="")) == sha                 # the default city
        assert _sha(_read(raw, PHILLY_BBOX, scale=sc, preset=ctd.PHILADELPHIA)) == sha  # the table as data


def test_philadelphia_auto_discovery_finds_the_same_lines():
    raw = json.load(gzip.open(FIX, "rt"))
    leg = _read(raw, PHILLY_BBOX, place="Philadelphia")
    gen = _read(raw, PHILLY_BBOX, place="Philadelphia", preset=False)
    assert gen.get("v") == 2 and "v" not in leg
    kinds = sorted((ln["k"], ln["c"]) for ln in gen["lines"])
    assert ("metro", "#f58220") in kinds and ("tram", "#6ea516") in kinds   # Broad Street, the trolleys
    trl = next(ln for ln in gen["lines"] if ln["k"] == "tram")
    assert len(trl["b"]) == len(next(ln for ln in leg["lines"] if ln["id"] == "trl")["b"])
    for ln in gen["lines"]:                                       # every stop a line lists is in its ride
        for si, s in enumerate(gen["stops"]):
            assert (ln["id"] in s["l"]) == (si in ln["s"])


def test_preset_lookup():
    assert ctd.preset_for("Philadelphia") is ctd.PHILADELPHIA and ctd.preset_for("") is ctd.PHILADELPHIA
    assert ctd.preset_for("Manhattan, New York") is ctd.NEW_YORK
    assert ctd.preset_for("Washington, DC") is ctd.WASHINGTON
    assert ctd.preset_for("Boston, Massachusetts") is ctd.BOSTON
    assert ctd.preset_for("Lyon, France") is None


# ── a synthetic city: two red services on one trunk, a grey line and a grey shuttle, an intercity train ──────────
def _city():
    els, nid = [], [1000]
    bbox = (40.0, -75.0, 40.04, -74.95)

    def node(lat, lon, **tags):
        nid[0] += 1
        els.append({"type": "node", "id": nid[0], "lat": lat, "lon": lon, "tags": tags})
        return nid[0]

    def way(wid, pts, **tags):
        els.append({"type": "way", "id": wid, "tags": {"railway": "subway", **tags},
                    "geometry": [{"lat": a, "lon": b} for a, b in pts], "nodes": []})

    def rel(rid, ways, stops, **tags):
        mem = [{"type": "node", "ref": s, "role": "stop"} for s in stops] + [{"type": "way", "ref": w, "role": ""} for w in ways]
        els.append({"type": "relation", "id": rid, "tags": dict(type="route", **tags), "members": mem})
    lats = [40.005 + 0.005 * i for i in range(6)]
    way(1, [(la, -74.99) for la in lats[:3]], tunnel="yes")
    way(2, [(la, -74.99) for la in lats[2:]])
    way(3, [(lats[2], -74.99), (lats[2], -74.96)])                       # the express branch east
    way(4, [(40.03, -74.985), (40.03, -74.955)])                         # the grey line
    way(5, [(40.01, -74.97), (40.01, -74.96)])                           # the grey shuttle, elsewhere
    way(6, [(40.002, -74.999), (40.038, -74.951)], railway="rail")       # intercity
    st = [node(la, -74.99, name="S%d" % i, level="-1" if i < 2 else "0") for i, la in enumerate(lats)]
    ex = node(lats[2], -74.96, name="East")
    g = [node(40.03, -74.985, name="G1"), node(40.03, -74.97, name="G2"), node(40.03, -74.955, name="G3")]
    sh = [node(40.01, -74.97, name="H1"), node(40.01, -74.96, name="H2")]
    it = [node(40.002, -74.999, name="Central"), node(40.038, -74.951, name="North")]
    out = node(40.2, -74.99, name="Far away")                              # a stop outside the box (not fetched)
    els.pop()                                                              # ... so it is not in the data
    net = dict(route="subway", network="Metro", operator="City Transit")
    rel(10, [1, 2], st, ref="1", colour="#EE352E", name="Metro - 1 Train: S0 → S5", **net)
    rel(11, [2, 1], st[::-1], ref="1", colour="#ee352e", name="Metro - 1 Train: S5 → S0", **net)
    rel(12, [1, 3], [st[0], st[2], ex], ref="2", colour="#EE352E", name="Metro - 2 Train: S0 → East", **net)
    rel(13, [1], [st[0], st[1]], ref="3", colour="#ee352e", name="Metro - 3 Train: S0 → S1", **net)   # a subset
    rel(14, [4], g, ref="L", colour="#a7a9ac", name="Metro - L Train", **net)
    rel(15, [5], sh, ref="S", colour="#a7a9ac", name="Metro - S Shuttle", **net)
    rel(16, [6], it, route="train", network="National Rail", ref="99", passenger="national", name="Express 99")
    rel(17, [6], it, route="train", network="Commuter", ref="C", name="Commuter C")      # 2 stops: not a city line
    rel(18, [1, 2], [st[0], st[1], out, st[3], st[4]], ref="4", colour="#00933c", name="Metro - 4 Train",
        **net)                                                             # leaves the box between S1 and S3
    return {"version": 0.6, "elements": els}, bbox


def test_auto_discovery_groups_lines_like_a_rider():
    raw, bbox = _city()
    t = _read(raw, bbox, place="Springfield")          # no preset: auto-discovery alone
    by = {ln["n"]: ln for ln in t["lines"]}
    assert set(by) == {"1 Train", "L Train", "S Shuttle", "4 Train"} or set(by) == {
        "Metro 1 2 3", "L Train", "S Shuttle", "4 Train"}, set(by)
    red = next(ln for ln in t["lines"] if ln["c"] == "#ee352e")
    assert red["id"] == "123" and red["k"] == "metro"
    names = [[t["stops"][i]["n"] for i in b] for b in red["b"]]
    assert len(names) == 2                               # 1 (all stops) and 2 (the express branch); 3 is a subset
    assert names[1][-1] == "East" and names[1][:3] == ["S0", "S1", "S2"]   # the express drawn on its trunk's stops
    grey = [ln for ln in t["lines"] if ln["c"] == "#a7a9ac"]
    assert len(grey) == 2                                # one colour, no shared track: two lines
    green = next(ln for ln in t["lines"] if ln["c"] == "#00933c")
    assert [[t["stops"][i]["n"] for i in b] for b in green["b"]] == [["S3", "S4"]] or len(green["b"]) == 2
    assert not any(ln["k"] == "rail" for ln in t["lines"])            # intercity, and a 2-stop commuter train
    u = {s["n"]: s.get("u") for s in t["stops"]}
    assert u["S0"] and u["S1"] and not u.get("S4")                    # below ground level / on a tunnel way


def test_preset_overrides_and_excludes():
    raw, bbox = _city()
    preset = {"auto": True, "families": [
        {"id": "red", "n": "Red Trunk", "c": "#ff0000", "k": "metro", "match": {"network": "Metro", "ref": ["1", "2", "3"]}}],
        "exclude": [{"ref": ["S"]}], "override": {"l": {"n": "Canarsie"}}}
    t = _read(raw, bbox, preset=preset)
    by = {ln["id"]: ln for ln in t["lines"]}
    assert by["red"]["n"] == "Red Trunk" and by["red"]["c"] == "#ff0000"
    assert by["l"]["n"] == "Canarsie"
    assert not any(ln["n"].startswith("S ") for ln in t["lines"])


def test_snap_generic_reading_helpers():
    tr = {"v": 2, "stops": [{"n": "A & B", "u": 1}, {"n": "C"}], "lines": []}
    assert pt._under(tr, {"s": [0, 1]}) == {0}                         # the OSM flag, not the name
    assert pt._under({"stops": tr["stops"]}, {"s": [0, 1]}) == {1}     # 1.9.78: a name with no "&"
    two = [("a", (0.0, 0.0)), ("b", (7.0, 0.0))]
    three = two + [("c", (14.0, 0.0))]
    assert pt._mean_ok(two) and not pt._mean_ok(three)                # outer lanes of three get their own dot


def test_picture_allows_a_lane_jog():
    m = {"transit": {"lines": [{"id": "x", "k": "metro", "p": [[0, 0, 240, 10.5, 2000, 10.5]], "s": []}], "stops": []}}
    assert picture(m)["ok"]
    m["transit"]["lines"][0]["p"] = [[0, 0, 240, 60, 2000, 60]]        # a real slant is still caught
    assert not picture(m)["ok"]
