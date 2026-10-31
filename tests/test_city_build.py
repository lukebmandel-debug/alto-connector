"""Build any place with your own Claude (city_byoc: the scored gate on set_up_palace's generic path, plain words, a draft
when it does not pass) and invent your own city (city_invent: invent_city(spec) -> m, the five templates and Blank, the
eight plain checks with one-tap fixes, the invent_city tool). No network: real cities come from the fixtures."""
import copy
import gzip
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from alto.build import city_byoc, city_gate, city_invent as ci, city_presets, palace_grid  # noqa: E402

from test_city_presets import server  # noqa: E402,F401 — set_up_palace with the network stubbed (a fixture)

FIX = ROOT / "tests" / "fixtures" / "cities"
BUILT = ("grid", "grid_diagonals", "organic_grid", "river", "radial")


def _fixture(name, crop=None):
    m = json.loads(gzip.decompress((FIX / ("%s.json.gz" % name)).read_bytes()).decode())
    if crop:                                    # a centre box (x0, y0, x1, y1): the streets wholly inside it, shifted
        x0, y0, x1, y1 = crop
        inside = lambda p: all(x0 <= x <= x1 for x in p[0::2]) and all(y0 <= y <= y1 for y in p[1::2])  # noqa: E731
        sh = lambda p: [v - (x0 if i % 2 == 0 else y0) for i, v in enumerate(p)]  # noqa: E731
        m["streets"] = [dict(s, p=sh(s["p"])) for s in m["streets"] if inside(s["p"])]
        m["rivers"] = [dict(r, p=sh(r["p"])) for r in m.get("rivers") or [] if inside(r["p"])]
        m["water"] = [sh(r) for r in m.get("water") or [] if inside(r)]
        m["rails"], m["stations"] = [], []
        m.pop("bank", None)
        m["W"], m["H"] = x1 - x0, y1 - y0
    return m


# ── build any place with your own Claude ───────────────────────────────────
@pytest.mark.parametrize("city,crop", [("barcelona", None), ("philadelphia", (4000, 3500, 8500, 8000))])
def test_a_place_that_is_not_a_preset_is_gated_and_told_plainly(city, crop):
    m = _fixture(city, crop)
    assert city_presets.find(city) is None                                    # not a preset: the user's own Claude
    with city_byoc.capture() as cap:
        palace_grid.grid(copy.deepcopy(m), majors=m.get("majors") or ())
    v = city_byoc.gate_built(cap)
    assert set(v) == {"pass", "score", "draft", "failing", "warnings", "message"}
    assert 0 <= v["score"] <= 100 and v["draft"] is (not v["pass"])
    # the fixtures carry no landmarks, so neither can pass: the user is told so in words, never a row code
    assert not v["pass"] and any("8 to 24 landmarks" in f for f in v["failing"])
    assert "draft" in v["message"] and "85" in v["message"]
    assert not any(t.startswith("G") and t[1:].isdigit() for f in v["failing"] + [v["message"]] for t in f.split())


def test_set_up_palace_saves_a_city_that_fails_the_gate_as_a_draft(server, monkeypatch):
    srv, _calls, draft = server
    from alto import palace_map
    from alto.build import palace_buses, palace_fleet
    for mod in (palace_buses, palace_fleet):                    # (the shared fixture leaves these two on the network)
        monkeypatch.setattr(mod, "fetch", lambda *a, **k: {})
    monkeypatch.setattr(palace_map, "build_map", lambda raw, bbox, **kw: _fixture("philadelphia", (5000, 4500, 7500, 7000)))
    tid = draft()
    r = srv.set_up_palace(tid, "Philadelphia")
    assert r.get("ok") is True, r
    g = r["gate"]
    assert g["draft"] and not g["pass"] and g["failing"] and "did not pass" in g["message"]
    pal = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]
    assert pal["preset"] == "auto" and pal["gate"]["draft"] and pal["gate"]["failing"] == g["failing"]


def test_the_verdict_of_a_passing_city_says_so():
    m, g = ci.build(ci.template("grid"))
    v = city_byoc.verdict(city_gate.gate(g, {k: x for k, x in m.items() if k != "plan"}))
    assert v["pass"] and not v["draft"] and not v["failing"] and "passed" in v["message"]


# ── invent your own city ───────────────────────────────────────────────────
def test_the_picker_is_templates_then_blank_with_grid_the_default():
    p = ci.picker()
    assert [x["id"] for x in p] == ["grid", "grid_diagonals", "organic_grid", "river", "radial", "blank"]
    assert [x["id"] for x in p if x["default"]] == ["grid"]


@pytest.mark.parametrize("kind", BUILT)
def test_every_template_builds_and_passes_the_gate(kind):
    sp = ci.template(kind)
    m = ci.invent_city(sp)
    assert m == ci.invent_city(copy.deepcopy(sp))                              # pure: the same spec, the same map
    assert m["preset"] == "invented" and m["bbox"][:2] == [0.0, 0.0]          # never a real place
    rep = ci.check(sp)
    assert rep["pass"] and rep["score"] >= city_gate.PASS_SCORE, rep
    assert [c["id"] for c in rep["checks"]] == [c[0] for c in ci.CHECKS] and len(rep["checks"]) == 8
    assert all(c["ok"] for c in rep["checks"]), [c for c in rep["checks"] if not c["ok"]]
    assert "G10" not in rep["rows"] and "G21" not in rep["rows"] and {"I1", "I2", "I4"} <= set(rep["rows"])


def test_the_radial_template_draws_its_spokes_as_a_free_district():
    m, g = ci.build(ci.template("radial"))
    free = {s["n"] for s in g["streets"] if s.get("fr")}
    assert g["engine"]["free"] and sum(n.endswith(" Road") for n in free) >= 8 and any(n.endswith(" Circle") for n in free)


def test_a_river_city_bridges_its_river_and_keeps_both_banks():
    m, g = ci.build(ci.template("river"))
    assert {s["n"] for s in m["streets"] if s.get("b")} >= {"King Street Bridge", "Queen Street Bridge"}
    assert g["engine"]["domains"] == 2 and g["river"]


def test_blank_cannot_be_built_until_it_has_a_grid_district():
    sp = ci.template("blank", "Nowhere")
    rep = ci.check(sp)
    assert not rep["pass"] and rep["problems"] == ["a city needs at least one district: add one (a grid district is the usual start)"]
    sp["districts"] = [{"name": "Hub", "kind": "radial", "size_km": 2}]
    with pytest.raises(ci.InventError) as e:
        ci.invent_city(sp)
    assert "at least one grid district" in str(e.value)


@pytest.mark.parametrize("change,words", [
    (lambda sp: sp["transit"][0]["stops"].append("Atlantis"), "stops at 'Atlantis', which is not a station"),
    (lambda sp: sp["transit"][0]["stops"].append(sp["landmarks"][0]["name"]), "a line stops at stations"),
    (lambda sp: sp["landmarks"].append({"name": "Tower X", "at": "Nowhere Street"}), "not a district or street"),
    (lambda sp: sp["districts"].append({"name": "Downtown", "size_km": 1}), "two districts are called 'Downtown'"),
    (lambda sp: sp["districts"].append({"name": "Twin", "center": [1450, 1200], "size_km": 2}), "overlap by more than a block"),
    (lambda sp: sp["districts"][0].update(size_km=0.3), "too small"),
    (lambda sp: sp["water"].append({"name": "Bay", "kind": "coast", "course": "up"}), "which side of the city"),
    (lambda sp: sp.update(template="grid", streets=[{"name": "Lost Road", "from": "Downtown"}]), "needs a to"),
])
def test_an_invalid_spec_gives_a_plain_error(change, words):
    sp = ci.template("grid")
    change(sp)
    with pytest.raises(ci.InventError) as e:
        ci.invent_city(sp)
    assert any(words in p for p in e.value.problems), e.value.problems
    assert ci.check(sp)["problems"] == e.value.problems


def _fix(rep, cid):
    c = next(c for c in rep["checks"] if c["id"] == cid)
    assert c["status"] == "fail" and c["why"] and c["fix"]["label"], c
    return c["fix"]


def test_a_district_no_street_reaches_is_fixed_in_one_tap():
    sp = ci.template("river")
    sp["streets"] = []                                                          # no bridge: the south bank is cut off
    rep = ci.check(sp)
    assert not rep["pass"] and "South Bank" in next(c for c in rep["checks"] if c["id"] == "streets")["why"]
    sp2 = ci.apply_fix(sp, _fix(rep, "streets"))
    assert sp["streets"] == [] and ci.check(sp2)["pass"]                        # the old spec is left as it was


def test_too_few_landmarks_is_fixed_in_one_tap():
    sp = ci.template("grid")
    sp["landmarks"] = [l for l in sp["landmarks"] if l["kind"] in ("park", "station")] + sp["landmarks"][:3]
    rep = ci.check(sp)
    assert not rep["pass"]
    f = _fix(rep, "landmarks")
    assert f["op"] == "add_landmarks" and f["n"] == 5
    assert ci.check(ci.apply_fix(sp, f))["pass"]


def test_a_loose_street_is_fixed_in_one_tap():
    sp = ci.template("grid")
    sp["streets"] = [{"name": "Stray Road", "class": "main", "from": "Downtown", "to": [5200, 1200]}]
    sp["districts"].append({"name": "Far Field", "kind": "grid", "center": [5200, 1200], "size_km": [1.0, 1.0]})
    rep = ci.check(sp)
    assert rep["pass"], rep                       # a main street ends on a district's crossing: it joins up
    sp["water"] = [{"name": "Long Lake", "kind": "lake", "at": [4000, 1200], "size_km": .4}]
    rep = ci.check(sp)
    if not rep["pass"]:
        c = [c for c in rep["checks"] if c["status"] == "fail"][0]
        assert c["fix"] and ci.check(ci.apply_fix(sp, c["fix"]))["score"] >= rep["score"]


# ── the tool ───────────────────────────────────────────────────────────────
def test_the_invent_city_tool_stores_a_finished_city(server):
    srv, calls, draft = server
    tid = draft()
    r = srv.invent_city(tid, template="river", name="Lowmoor")
    assert r.get("ok") is True and r["finished"] and r["score"] >= 85, r
    assert not calls                                                           # nothing fetched
    pal = srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]
    assert pal["place"] == "Lowmoor" and pal["preset"] == "invented" and pal["gate"]["pass"] and pal["data_z"]
    assert pal["invented"]["template"] == "river"


def test_the_invent_city_tool_keeps_a_failing_city_as_a_draft_and_applies_a_fix(server):
    srv, _calls, draft = server
    tid = draft()
    sp = ci.template("river")
    sp["streets"] = []
    r = srv.invent_city(tid, spec=sp)
    assert r.get("ok") and not r["finished"] and "draft" in r["message"]
    assert srv.get_store().get_timeline(srv.uid(), tid)["brief"]["palace"]["gate"]["draft"]
    r2 = srv.invent_city(tid, spec=sp, fix="streets")
    assert r2["finished"] and r2["spec"]["streets"]
    bad = srv.invent_city(tid, spec={"districts": []})
    assert bad["error"] == "invalid_city" and bad["problems"]


def test_a_line_through_a_landmark_is_found_and_has_a_fix():
    m, g = ci.build(ci.template("grid"))
    g = copy.deepcopy(g)
    lm = g["landmarks"][0]
    y = (lm["box"][1] + lm["box"][3]) / 2
    g["rails"] = [{"n": "Red Line", "p": [lm["box"][0] - 500, y, lm["box"][2] + 500, y]}]
    rows = ci.i_rows(m, g)
    assert rows["I6"][0] == "warn" and ("Red Line", lm["n"]) in rows["I6"][2]["through"]
    why, fix = ci._plain("transit", rows, ci.template("grid"))
    assert lm["n"] in why and fix["op"] == "unpin" and lm["n"] in fix["names"]


def test_invented_landmarks_never_take_a_real_buildings_art_and_cities_differ():
    from alto.build.palace_landmarks import art_key
    looks = {}
    for kind in BUILT:
        _m, g = ci.build(ci.template(kind))
        keys = {l["n"]: art_key(l) for l in g["landmarks"]}
        assert all(k in set(ci.LOOKS.values()) for k in keys.values()), keys      # never Philadelphia's City Hall, Museum...
        assert len(set(keys.values())) >= 5                                       # a city of varied buildings
        looks[kind] = keys
    assert len({tuple(sorted(v.items())) for v in looks.values()}) == len(BUILT)   # no two cities alike
    sp = ci.template("grid")
    sp["landmarks"][0]["look"] = "pyramid"
    _m, g = ci.build(sp)
    assert art_key(next(l for l in g["landmarks"] if l["n"] == sp["landmarks"][0]["name"])) == "g-pyramid"
    sp["landmarks"][0]["look"] = "philly"
    with pytest.raises(ci.InventError):
        ci.invent_city(sp)


@pytest.mark.parametrize("place,art", [("Lyon", "g-dome"), ("Philadelphia", "city")])
def test_city_hall_art_is_philadelphias_only(place, art):
    from alto.build import palace
    from alto.build.palace_landmarks import art_key
    sp = ci.template("grid")
    sp["landmarks"][0]["name"] = "City Hall"
    m = ci.invent_city(sp)
    pl = m["plan"]
    blds = [{"name": b["name"]} for b in pl["landmarks"]]                # no look of their own: art by name
    pal = palace.set_up(place, list(m["bbox"]), majors=pl["majors"], landmarks=[b["name"] for b in blds], buildings=blds,
                        parks=pl["parks"], areas=[], offline=True, fill=False, city_tiles=False, plan=m)
    hall = next(l for l in palace.unpack(pal["data_z"])["map"]["landmarks"] if l["n"] == "City Hall")
    assert art_key(hall) == art
