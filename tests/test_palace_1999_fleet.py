"""1.9.99: every city's museum warships, aircraft carriers, submarines and military bases are toys that are armed with a click and attack the next building clicked
(palace_fleet.py data, palace_fleet_*.py the hosted script, palace_assets.py the registry the ride shares).

Source assertions + node syntax checks always run. The data side runs on synthetic OSM answers (no network). The browser checks (OfflineAudioContext renders of the new sounds; the
real palace page of the fixture sandbox `fleet99x`, with a carrier, a destroyer, a submarine, a shore battery and an air base) run through the QA kit's python when it is on this
machine (build the fixture with _qa/fleet99/mkfix.py). Nobody can HEAR these tests: they assert levels, timing and plumbing."""
import gzip
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from alto.build import palace, palace_assets, palace_boats, palace_fleet, palace_fleet_asset, palace_ride, palace_sound, private_shell

QA = Path.home() / "Desktop" / "Alto Development" / "_qa"
NODE = Path.home() / ".local" / "node" / "bin" / "node"
HERE = Path(__file__).parent
KITPY = QA / "kit" / "py"
FJ = palace_fleet_asset.FLEET_JS
PAGE_JS = palace.PALACE_JS


# ── the data: what is a toy ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,tags,want", [
    ("USS New Jersey", {"ship:type": "battleship", "ref": "BB-62"}, "bb"),
    ("USS Texas", {"historic": "ship"}, "bb"),
    ("USS Massachusetts", {"ship:type": "battleship"}, "bb"),
    ("USS Midway", {"historic": "ship", "ship:type": "aircraft_carrier"}, "cv"),
    ("Intrepid", {"ship:type": "carrier"}, "cv"),
    ("USS Hornet", {"ref": "CV-12"}, "cv"),
    ("USS Yorktown", {"building": "ship", "historic": "ship"}, "cv"),
    ("USS Lexington", {"historic": "ship"}, "cv"),
    ("USS Olympia", {"ship:type": "cruiser", "ref": "C-6"}, "dd"),
    ("USS Kidd", {"historic": "ship", "ship:type": "destroyer"}, "dd"),
    ("USS Cassin Young", {"historic": "ship"}, "dd"),
    ("USS The Sullivans", {"ref": "DD-537"}, "dd"),
    ("USS Little Rock", {"ref": "CL-92"}, "dd"),
    ("USS Mystery", {"historic": "ship"}, "dd"),                     # a military vessel of no known class is a destroyer
    ("HMS Belfast", {"historic": "ship"}, "dd"),
    ("USS Becuna", {"ship:type": "submarine", "ref": "SS-319"}, "sub"),
    ("USS Growler", {"historic": "ship"}, "sub"),
    ("USS Pampanito", {"ref": "SS-383"}, "sub"),
    ("Moshulu", {"ship:type": "cargo_ship", "historic": "ship", "amenity": "restaurant"}, None),
    ("BARNEGAT Lightship", {"historic": "ship"}, None),
    ("Spirit of Philadelphia", {"ship:type": "passenger"}, None),
    ("Peking", {"historic": "ship"}, None),
])
def test_what_a_vessel_is(name, tags, want):
    assert palace_fleet.vessel_class(tags, name, 150) == want


@pytest.mark.parametrize("tags,want", [
    ({"landuse": "military", "name": "Naval Support Activity Philadelphia"}, "army"),
    ({"military": "base"}, "army"), ({"military": "naval_base"}, "army"), ({"military": "range"}, "army"), ({"military": "barracks"}, "army"),
    ({"military": "airfield", "name": "Lakehurst"}, "air"),
    ({"aeroway": "aerodrome", "military": "airfield"}, "air"),
    ({"aeroway": "aerodrome", "name": "Willow Grove Naval Air Station"}, "air"),
    ({"landuse": "military", "name": "Joint Base McGuire-Dix-Lakehurst"}, "air"),
    ({"military": "office", "landuse": "military", "name": "Captain of the Port"}, None),           # a Coast Guard office is no base
    ({"military": "checkpoint"}, None), ({"aeroway": "aerodrome", "name": "Philadelphia International Airport"}, None), ({"building": "yes"}, None),
])
def test_what_a_base_is(tags, want):
    assert palace_fleet.base_class(tags) == want


def _bounds(lat, lon, ha):
    side = (ha * 1e4) ** .5
    dl, dn = side / 110574 / 2, side / (111320 * .77) / 2
    return {"minlat": lat - dl, "maxlat": lat + dl, "minlon": lon - dn, "maxlon": lon + dn}


def test_bases_are_read_from_the_bounds_and_the_big_ones_come_first():
    raw = {"elements": [
        {"type": "way", "id": 1, "tags": {"landuse": "military", "name": "Naval Support Activity Philadelphia"}, "bounds": _bounds(39.90, -75.18, 80)},
        {"type": "way", "id": 2, "tags": {"landuse": "military"}, "bounds": _bounds(39.95, -75.20, 2)},                          # a gate house
        {"type": "way", "id": 3, "tags": {"military": "airfield", "name": "Field", "aeroway": "aerodrome"}, "bounds": _bounds(39.97, -75.10, 200)},
        {"type": "relation", "id": 4, "tags": {"military": "office", "landuse": "military"}, "bounds": _bounds(39.91, -75.14, 90)},
        {"type": "way", "id": 5, "tags": {"military": "range"}, "bounds": _bounds(39.92, -75.12, 30)}]}
    bs = palace_fleet.bases(raw, (39.80, -75.30, 40.05, -75.00), 1.0)
    assert [b["k"] for b in bs] == ["air", "army", "army"] and bs[0]["n"] == "Field" and bs[1]["n"] == "Naval Support Activity Philadelphia"
    assert bs[0]["ha"] > bs[1]["ha"] > bs[2]["ha"] and all(0 < b["rx"] and 0 < b["ry"] for b in bs)


class _Dom:
    free = True


def _free_domains(monkeypatch):
    import alto.build.palace_fillin as pf
    monkeypatch.setattr(pf, "domains", lambda mm: [_Dom()])
    monkeypatch.setattr(pf, "_owners", lambda doms: (None, lambda x, y: _Dom()))


def test_a_base_toy_stands_where_the_base_is_out_of_the_water_and_never_in_a_crowd(monkeypatch):
    _free_domains(monkeypatch)
    m = {"W": 4000, "H": 4000, "river": [{"n": "R", "w": 200, "p": [2000, 0, 2000, 4000]}]}
    found = [{"n": "A", "k": "army", "rx": 1000.0, "ry": 1000.0, "ha": 60}, {"n": "In the river", "k": "army", "rx": 2020.0, "ry": 2500.0, "ha": 50},
             {"n": "Beside A", "k": "air", "rx": 1100.0, "ry": 1100.0, "ha": 40}, {"n": "Far away", "k": "air", "rx": 9000.0, "ry": 100.0, "ha": 500}]
    out = palace_fleet.place_bases(m, found)
    names = [b["n"] for b in out]
    assert names == ["A", "In the river"]                                           # one too near the first is dropped, one off the map has no place
    r = out[1]
    assert abs(r["x"] - 2000) >= 100 + r["r"] * .6                                 # slid to the bank side of the water
    assert all(40 <= b["r"] <= 95 for b in out)
    assert len(palace_fleet.place_bases(m, [dict(found[0], n=str(i), rx=500.0 + i * 800.0) for i in range(6)])) <= palace_fleet.MAX_BASES


def test_find_puts_the_weapon_class_on_each_ship_and_place_carries_it(monkeypatch):
    ring = lambda lat: [{"lat": lat, "lon": -75.1400}, {"lat": lat, "lon": -75.1398}, {"lat": lat + .001, "lon": -75.1398}, {"lat": lat + .001, "lon": -75.1400}]   # noqa: E731
    raw = {"elements": [
        {"type": "way", "id": 1, "tags": {"name": "USS Olympia", "building": "ship", "historic": "ship", "ship:type": "cruiser"}, "geometry": ring(39.9460)},
        {"type": "way", "id": 2, "tags": {"name": "USS Midway", "historic": "ship", "ship:type": "aircraft_carrier"}, "geometry": ring(39.9480)},           # not a `building` at all
        {"type": "way", "id": 3, "tags": {"name": "Moshulu", "building": "ship", "historic": "ship", "ship:type": "cargo_ship"}, "geometry": ring(39.9500)},
        {"type": "way", "id": 4, "tags": {"building": "yes"}, "geometry": ring(39.9520)}]}
    s = palace_boats.find(raw, (39.90, -75.25, 40.00, -75.10), 1.0)
    assert {x["n"]: x["k"] for x in s} == {"USS Olympia": "dd", "USS Midway": "cv", "Moshulu": ""}
    _free_domains(monkeypatch)
    m = {"river": [{"n": "R", "w": 200, "p": [0, 0, 0, 1000]}], "grid": {}, "bbox": [39.90, -75.25, 40.00, -75.10]}
    b = palace_boats.place(m, [dict(x, rx=150.0, ry=300.0 + i * 400) for i, x in enumerate(s)])
    assert [x.get("k") for x in b] == ["dd", "cv", None]                              # a tall ship carries no class


def test_attach_adds_the_ships_the_building_tiles_missed_and_the_bases(monkeypatch):
    _free_domains(monkeypatch)
    ring = [{"lat": 39.9480, "lon": -75.1400}, {"lat": 39.9480, "lon": -75.1398}, {"lat": 39.9490, "lon": -75.1398}, {"lat": 39.9490, "lon": -75.1400}]
    raw = {"elements": [{"type": "way", "id": 2, "tags": {"name": "USS Midway", "historic": "ship", "ship:type": "aircraft_carrier"}, "geometry": ring},
                        {"type": "way", "id": 1, "tags": {"name": "USS Kidd", "historic": "ship"}, "geometry": ring},
                        {"type": "way", "id": 7, "tags": {"landuse": "military", "name": "Fort X"}, "bounds": _bounds(39.93, -75.20, 60)}]}
    from alto import palace_map as pm
    sx, sy = pm.project(39.9485, -75.1399, (39.90, -75.25, 40.00, -75.10), 1.0)                   # the real ship's place, in the same px as the river
    m = {"river": [{"n": "R", "w": 300, "p": [sx, sy - 1500, sx, sy + 1500]}], "grid": {}, "bbox": [39.90, -75.25, 40.00, -75.10], "W": 200000, "H": 200000, "scale": 1.0,
         "boats": [{"n": "USS Kidd", "x": sx, "y": sy + 700, "a": 90, "len": 150, "wid": 20, "k": "dd"}], "landmarks": [{"n": "USS Midway", "x": 1, "y": 1}, {"n": "Other", "x": 2, "y": 2}]}
    palace_fleet.attach(m, raw, [39.90, -75.25, 40.00, -75.10])
    assert [b["n"] for b in m["boats"]] == ["USS Kidd", "USS Midway"] and m["boats"][1]["k"] == "cv"        # Kidd was found already: not twice
    assert [l["n"] for l in m["landmarks"]] == ["Other"]                           # the ship is no landmark card
    assert [b["n"] for b in m["bases"]] == ["Fort X"] and m["bases"][0]["k"] == "army"
    m2 = {"river": [], "grid": {}, "bbox": [39.9, -75.25, 40.0, -75.10], "W": 100, "H": 100}
    palace_fleet.attach(m2, {"elements": []}, [39.9, -75.25, 40.0, -75.10])
    assert "boats" not in m2 and "bases" not in m2                                  # a city with neither shows nothing new


def test_the_fleet_query_is_cached_and_offline_asks_nothing(tmp_path, monkeypatch):
    from alto import palace_map as pm
    calls = []
    monkeypatch.setattr(pm, "_post_overpass", lambda q, t: calls.append(q) or {"elements": [{"type": "way", "id": 1, "tags": {"name": "X"}}]})
    bb = (39.9, -75.25, 40.0, -75.1)
    assert palace_fleet.fetch(bb, cache_dir=tmp_path, offline=True) == {"elements": []} and not calls
    r1 = palace_fleet.fetch(bb, cache_dir=tmp_path)
    r2 = palace_fleet.fetch(bb, cache_dir=tmp_path)
    assert r1 == r2 and len(calls) == 1 and any(p.name.startswith("fleet-") for p in tmp_path.iterdir())
    q = calls[0]
    for needle in ("historic=ship", "building=ship", '"ship:type"', "landuse=military", "naval_base", "aeroway=aerodrome", "out tags bb;"):
        assert needle in q, needle


# ── the engine: one table of weapons, a hosted script ───────────────────────────────────────────────────
def test_the_weapon_table_has_one_entry_per_class_with_the_fx_bar_words():
    for k, verb in (("bb", "fire"), ("army", "shell it"), ("dd", "launch the missile salvo"), ("cv", "launch the air strike"), ("air", "scramble the fighters"), ("sub", "fire a torpedo")):
        assert re.search(r"WP\.%s=\{verb:'%s'" % (k, verb), FJ), k
    assert "' \\u2014 click a building to '+WP[w].verb+' \\u00b7 Esc to stand down'" in FJ        # 'USS Midway — click a building to launch the air strike · Esc to stand down'
    assert "function fire(tg, toy){" in FJ and "WP[toy._w].fire(tg, toy)" in FJ
    for fn in ("function fireGuns(", "function fireMissiles(", "function fireStrike(", "function fireTorpedo(", "function toyBB(", "function toyDD(", "function toyCV(", "function toySub(", "function drawBase("):
        assert fn in FJ, fn


def test_the_art_is_the_board_game_piece_for_each_class():
    assert FJ.count("pegs(top,") >= 5 and "[-.40,-.13,.125,.38]" in FJ                    # the battleship's four peg dimples, as 1.9.97
    assert "fl-run" in FJ and "jet(top," in FJ and "JET='M.5 0L" in FJ                    # a carrier: a flight deck, the angled strip, little jets
    assert "b._cells" in FJ and "b._launch" in FJ and "b._muzzle" in FJ and "s._rw" in FJ    # where missiles, jets, the torpedo leave from
    assert "vector-effect" in FJ and "'bb-wall'" in FJ                                      # the moulded plastic's thick edge
    assert "<mask" not in FJ and "mask" not in re.sub(r"/\*.*?\*/", "", FJ, flags=re.S) and "filter" not in re.sub(r"/\*.*?\*/", "", FJ, flags=re.S)    # nothing Safari draws differently


def test_a_flight_is_sized_on_the_screen_and_driven_by_one_frame_loop():
    assert "function sprite(cls, build){ var g=fxPin(0, 0, cls)" in FJ and "requestAnimationFrame(tick)" in FJ
    assert "freeze:function(ms)" in FJ and "FORCE" in FJ
    assert "rotate('+(rot*180/PI)" in FJ                                                   # the heading is an SVG attribute on an inner group, never a CSS transform on a pinned group


def test_the_toys_hear_the_click_before_the_maps_own_handlers():
    assert "window.addEventListener('click', function(e){\n    if(H.mob() || !H.palaceOn()) return;" in FJ
    assert "e.stopImmediatePropagation(); e.preventDefault(); fxBar(ARM!==wp, wp); return;" in FJ        # a toy again stands it down; another toy arms that one
    assert "if(ARM && e.key==='Escape')" in FJ and "tg.x=cp[0]; tg.y=cp[1];" in FJ


# ── the page: smaller, guarded, nothing inlined ──────────────────────────────────────────────────────────
def test_the_page_carries_a_loader_and_one_call_not_the_fleet():
    assert palace_fleet_asset.FLEET_LOADER in PAGE_JS and len(palace_fleet_asset.FLEET_LOADER) < 500
    for gone in ("function drawBoat(", "function drawToyBB(", "function nbFire(", "function fxBoom(", "function fxShell(", "window._palSnd=(function(){", "window._palPanic=(function(){",
                 "window._palCon=(function(){", "function boatKind("):
        assert gone not in PAGE_JS, gone
    for gone in (".pl-boat", "#pal-fxbar", "nb-ruin", "pl-fx{"):
        assert gone not in palace.PALACE_CSS, gone
    assert "window._palFleet.draw(lg, M, fleetHost())" in PAGE_JS


def test_the_fleet_is_loaded_only_by_a_city_with_a_vessel_or_a_base_and_every_use_is_guarded():
    assert "if(!window._palFleet && ((M.boats&&M.boats.length)||(M.bases&&M.bases.length))) palLoadFleet();" in PAGE_JS
    uses = [l.strip() for l in PAGE_JS.split("\n") if "_palFleet" in l]
    assert uses and all("window._palFleet" in l for l in uses if "palLoadFleet" not in l.split("window._palFleet")[0])
    assert sum("window._palFleet.draw(" in l for l in uses) == 1
    code = (Path(palace.__file__)).read_text()
    assert "palace_fleet.attach(" in code                                              # the data side is in set_up


def test_the_loader_asks_for_exactly_the_hashed_file_synchronously():
    l = palace_fleet_asset.FLEET_LOADER
    name, js = palace_fleet_asset.fleet_asset()
    assert js == palace_fleet_asset.FLEET_ASSET
    assert name == "palace-fleet-" + hashlib.sha256(js.encode("utf-8")).hexdigest()[:10] + ".js"
    assert palace_fleet_asset.FLEET_PATH == "/fleet/" + name and re.fullmatch(r"/fleet/palace-fleet-[0-9a-f]{10}\.js", palace_fleet_asset.FLEET_PATH)
    assert "x.open('GET',\"%s\",false)" % palace_fleet_asset.FLEET_PATH in l and "x.status===200" in l and "s.text=x.responseText" in l and "catch(e){}" in l
    assert "eval(" not in l and "document.write" not in l
    assert "if(window._palFleet) return;" in l


def test_the_asset_holds_no_timeline_content_and_no_network():
    js = palace_fleet_asset.FLEET_ASSET
    js = js.replace("http://www.w3.org/2000/svg", "")                                # the SVG namespace (palace_construct.py) is no address
    for bad in ("XMLHttpRequest", "fetch(", "http://", "https://", "_ALTO_PALACE", "localStorage.setItem('alto-palace-ride", "decodeAudioData", "new Audio"):
        assert bad not in js, bad
    assert "(function(){\nif(window._palFleet) return;" in js and js.startswith("(function(){var s=document.createElement('style');s.id='pal-fleet-css'")
    assert len(js) < 140_000


@pytest.mark.skipif(not NODE.exists(), reason="node not installed")
def test_the_asset_parses():
    p = HERE / "_fleet99_check.js"
    p.write_text("new Function(" + json.dumps(palace_fleet_asset.FLEET_ASSET) + ");")
    try:
        r = subprocess.run([str(NODE), str(p)], capture_output=True, text=True)
    finally:
        p.unlink()
    assert r.returncode == 0, r.stderr


def test_the_page_is_smaller_than_it_was_with_the_battleship_code_in_it():
    page = palace.PALACE_JS + palace.PALACE_CSS
    inline = page.replace(palace_fleet_asset.FLEET_LOADER, palace_fleet_asset.FLEET_JS) + palace_fleet_asset.FLEET_CSS_ALL
    assert private_shell.stored_bytes(inline) - private_shell.stored_bytes(page) > 12_000       # gzipped, as the page is stored
    # (the civ-pro palace page, 1,000,923 stored bytes before this change, was 978,800 after: see the hand-over note)


# ── the registry the ride shares ────────────────────────────────────────────────────────────────────────
def test_the_registry_lists_the_ride_and_the_fleet_and_serves_them():
    assert palace_assets.folders() == ["ride", "fleet", "street"]
    got = {(f, n): t for f, n, t in palace_assets.assets()}
    rn, rj = palace_ride.ride_asset()
    fn, fj = palace_fleet_asset.fleet_asset()
    assert got[("ride", rn)] == rj and got[("fleet", fn)] == fj
    assert palace_assets.find("/fleet/" + fn + "?x=1") == ("text/javascript; charset=utf-8", fj) and palace_assets.find("/ride/" + rn)[1] == rj
    assert palace_assets.find("/fleet/palace-fleet-0000000000.js") is None and palace_assets.find("/elsewhere/x.js") is None
    # the ride is untouched: its own loader still stands where RIDE_JS did
    assert palace_ride.RIDE_LOADER in PAGE_JS and palace_ride.RIDE_JS not in PAGE_JS


def test_the_site_writes_every_hosted_script_and_keeps_them_for_a_year(tmp_path):
    from alto.publish_static import regenerate_site, _headers
    from alto.store.local import LocalStore
    site = tmp_path / "site"
    for f, old in (("ride", "palace-ride-0000000000.js"), ("fleet", "palace-fleet-0000000000.js")):
        (site / f).mkdir(parents=True)
        (site / f / old).write_text("old", encoding="utf-8")                          # an earlier release's file is swept
    regenerate_site(LocalStore(tmp_path / "store"), "local", site)
    for f, n, t in palace_assets.assets():
        assert n in [p.name for p in (site / f).iterdir()]
        assert (site / f / n).read_text(encoding="utf-8") == t
    assert sorted(p.name for p in (site / "ride").iterdir()) == [palace_ride.ride_asset()[0]]      # (a folder keeps one script; the street folder keeps every stored blob)
    heads = _headers("csp", "ccsp")
    for f in ("ride", "fleet", "street"):
        rule = next(h for h in heads if h["source"] == "/%s/**" % f)
        assert {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"} in rule["headers"] and heads.index(rule) > 0


# ── sound ────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_new_sounds_are_synthesised_and_the_speaker_names_the_toy():
    js = palace_sound.SOUND_JS
    for needle in ("jet:function(w,d)", "whistle:function(ms)", "rocket:function(ms)", "ping:function()", "torpedo:function(d)", "bar:function(b,a,w){ if(w) W=w;", "'bandpass',2200,380"):
        assert needle in js, needle
    assert len(gzip.compress(js.encode())) < 4600
    for bad in ("fetch(", "XMLHttpRequest", "decodeAudioData", ".mp3", ".wav", ".ogg", "http://", "https://", "<audio", "new Audio"):
        assert bad not in js
    assert re.search(r"WP\.cv=\{verb:'[^']*', snd:'carrier'", FJ) and "SND.bar(b, on, WP[w].snd)" in FJ
    for call in ("SND.jet(", "SND.whistle(", "SND.rocket(", "SND.ping()", "SND.torpedo(", "SND.f(ms)", "SND.b(x, y)", "SND.u(b.x, b.y)"):
        assert call in FJ, call


def _run(script):
    env = {"HOME": str(Path.home()), "PATH": os.environ["PATH"], "ALTO_REPO": str(HERE.parent)}
    r = subprocess.run([str(KITPY), str(HERE / script)], capture_output=True, text=True, env=env, timeout=900)
    line = [x for x in r.stdout.splitlines() if x.startswith("RESULT ")]
    assert line, r.stdout[-1500:] + r.stderr[-1500:]
    return json.loads(line[0][7:])


@pytest.fixture(scope="module")
def blank():
    if not KITPY.exists():
        pytest.skip("QA kit not on this machine")
    return _run("palace_1999_fleet_sound.py")


@pytest.mark.parametrize("eng", ["webkit", "chromium"])
def test_the_new_sounds_render_audible_unclipped_and_end_in_silence(blank, eng):
    r = blank[eng]
    assert r["errors"] == [] and r["noAudio"] is True
    for k in ("jet", "jets", "whistle", "rocket", "ping", "torpedo", "run"):
        assert not r[k].get("bad"), k
        assert 0.03 < r[k]["peak"] < 1.0, (k, r[k])                                # audible, never clips
        assert r[k]["tail"] < 0.002, (k, r[k])                                     # ends near silence
    assert r["jets"]["peak"] < 0.5                                                 # four jets are moderate (the compressor)
    assert r["whistle"]["loud"] < 1.7 and r["ping"]["first"] < 0.05                # a ping starts at once
    assert r["hidden"]["peak"] == 0                                                # a hidden tab schedules nothing


# ── the page, in both engines ──────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def pages():
    if not KITPY.exists() or not (QA / "sandboxes" / "fleet99x").exists():
        pytest.skip("QA sandbox fleet99x not on this machine (copy _qa/sandboxes/w95c to fleet99, run _qa/fleet99/mkfix.py)")
    return _run("palace_1999_fleet_page.py")


@pytest.mark.parametrize("eng", ["webkit", "chromium"])
def test_every_class_is_drawn_armed_fires_with_its_own_sounds_and_stands_down(pages, eng):
    r = pages[eng]
    assert r["errors"] == [] and r["console"] == [] and r["loaded"] == "object"
    by = {t["n"]: t for t in r["toys"]}
    assert {t["w"] for t in r["toys"]} == {"bb", "cv", "dd", "sub", "army", "air"}
    assert all(re.search(r"\bwp\b", t["cls"]) and max(t["box"]) > 25 and min(t["box"]) > 5 for t in r["toys"])
    assert r["other"] == ["Moshulu"]                                               # a tall ship is no toy: drawn, but not armed
    want = {"bb": ("fire", ["u", "f", "b"]), "cv": ("launch the air strike", ["u", "jet", "whistle", "b"]), "dd": ("launch the missile salvo", ["u", "rocket", "b"]),
            "sub": ("fire a torpedo", ["u", "ping", "torpedo", "b"]), "army": ("shell it", ["u", "f", "b"]), "air": ("scramble the fighters", ["u", "jet", "whistle", "b"])}
    seen = set()
    for key, a in r["attacks"].items():
        w, name = key.split(":", 1)
        verb, sounds = want[w]
        seen.add(w)
        assert a["armed"]["armed"] is True and a["armed"]["glow"] == [name]
        assert a["armed"]["bar"] == "%s — click a building to %s · Esc to stand down×" % (name, verb) or a["armed"]["bar"].startswith(name + " — click a building to " + verb)
        assert all(s in a["after"]["calls"] for s in sounds), (key, a["after"]["calls"])
        assert a["after"]["con"] >= 1                                              # the building came down and is being rebuilt (palace_construct)
        assert a["after"]["panic"] >= 1                                            # with its crowd (palace_panic)
        assert a["down"]["armed"] is False and a["down"]["glow"] == []             # Esc stands down
    assert seen == set(want)
