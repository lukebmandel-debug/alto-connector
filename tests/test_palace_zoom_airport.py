"""1.9.81: the zoom preview agrees with the settled board, a filter flies the camera from anywhere, an airport portal goes
somewhere, mainline stations are seen, the fill-in opens on 90% downtown / 100% beyond, City Hall is a ring round a courtyard."""
from alto.build import palace, palace_fillin, palace_skyline, palace_transit_js, palace_airport, city_transit_data


def test_the_zoom_preview_is_scaled_about_the_city_corner_and_stops_at_the_edge():
    js = palace.PALACE_JS
    assert "world.style.transformOrigin='0 '+WORLD_PAD_TOP+'px'" in js          # the pad above the city does not scale
    assert "function gapAt(" in js and "function gyAt(" in js
    assert "Math.max(0, Math.min(sxT," in js                                     # the preview stops where the page stops scrolling
    assert "'--mx', (-Math.round(" in js                                          # cards are centred at the settle, not a frame later


def test_a_filter_flies_to_its_route_from_a_detail_page_or_an_enlarged_building():
    js = palace.PALACE_JS
    assert "function leaveBoard(then)" in js and "function flyAway(" in js
    assert "leave:leaveBoard" in js
    t = palace_transit_js.TRANSIT_JS
    assert "E.leave(function(){" in t and "fitLines([], [box[0]-60" in t        # the route's box, not every line it rides
    assert "alto-filter-changed" in t and "S.flySig" in t
    assert "pickLine(kr.getAttribute('data-tl')); return; }" in t               # a key row fits the whole line, no second fly


def test_mainline_stations_are_marked_and_drawn_over_the_highways():
    assert "' maj'" in palace_transit_js.TRANSIT_JS.replace('"', "'") or "maj?' maj'" in palace_transit_js.TRANSIT_JS
    assert ".tr-stn.maj .tr-dot" in palace_transit_js.TRANSIT_CSS
    assert "ts=svg.querySelector(':scope > .pl-tstns')" in palace.PALACE_JS
    rr = [f for f in city_transit_data.PHILADELPHIA["families"] if f["id"] == "rr"][0]
    assert rr["branches"] == "routes"                                            # every Regional Rail line, not only the longest run


def test_fill_in_opens_on_auto_90_downtown_100_beyond():
    js = palace_fillin.FILL_FUNCS
    assert "FILL_DT=90, FILL_OUT=100, fillAuto=true" in js
    assert "function downtownAt(" in js and "function fillRank(" in js
    assert 'type="range" min="0" max="100" step="5"' in js


def test_an_airport_portal_makes_the_trip_and_lists_departures():
    assert "function takePortal(" in palace_transit_js.TRANSIT_JS
    assert "window._palAirport={init:" in palace_airport.AIRPORT_JS
    assert "#pal-airport" in palace_airport.AIRPORT_CSS
    assert "window._palAirport.init(" in palace.PALACE_JS


def test_city_hall_is_a_ring_round_an_open_courtyard():
    spec = palace_skyline.LANDMARKS["city"]()
    court = [p for p in spec["parts"] if p["k"] == "court"][0]
    assert court["y0"] == 0 and court["w"] == 76
    ws = [p for p in spec["parts"] if p["k"] == "box" and p.get("top") is False]
    assert len(ws) >= 4                                                           # south, north and two side wings
    assert palace_skyline.Sky(spec).H > 250                                      # the tower still rises over the block


def test_main_line_stations_are_landmarks_with_their_own_art():
    from alto.build import palace_landmarks, palace_towers, city_setup
    assert {"stn", "sub", "jef"} <= set(palace_skyline.LANDMARKS)
    for k in ("stn", "sub", "jef"):
        palace_skyline.Sky(palace_skyline.LANDMARKS[k]())                         # each draws
    assert palace_landmarks.art_key({"n": "William H. Gray III 30th Street Station"}) == "stn"
    assert palace_landmarks.art_key({"n": "Penn Center Suburban Station"}) == "sub"
    assert palace_landmarks.art_key({"n": "Jefferson Station"}) == "jef"
    assert palace_towers.is_station("Penn Center Suburban Station") and not palace_towers.is_station("Cira Centre")
    els = [{"type": "way", "id": 1, "tags": {"name": "Union Station", "railway": "station", "train": "yes", "network": "Amtrak"},
            "geometry": [{"lat": 38.8975, "lon": -77.0}, {"lat": 38.8976, "lon": -77.0001}]},
           {"type": "node", "id": 2, "lat": 38.9, "lon": -77.02, "tags": {"name": "Metro Center", "railway": "station", "subway": "yes"}}]
    assert city_setup.stations_of(els, (38.8, -77.2, 39.0, -76.9)) == ["Union Station"]       # a subway stop is not a main-line station
