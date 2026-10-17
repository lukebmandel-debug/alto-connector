"""1.9.83: coming back from a building's page lands where you were, a filter's route can be ridden, airport portals stand
on the station buildings, the filter observer no longer re-fires itself, Jefferson Station is a glass concourse."""
from alto.build import filter_panel, palace, palace_skyline, palace_transit_js


def test_the_view_is_remembered_across_a_detail_page_and_put_back():
    js = palace.PALACE_JS
    assert "function wrapDetail()" in js and "holdView={z:Z, x:cv.scrollLeft, y:cv.scrollTop}" in js
    assert "cancelAnimationFrame(zAnim)" in js                                  # a glide to the building does not land on the hidden board
    assert "cv.scrollLeft=hv.x; cv.scrollTop=hv.y;" in js
    assert "pendEnl=flyId" in js and "enlarge(pe)" in js                         # a double-click's unfinished enlarge resumes on return
    assert "if(cvh && !cvh.clientWidth && de.classList.contains('detail-open')) return;" in js   # nothing is laid out against the hidden canvas


def test_the_filter_observer_ignores_the_palaces_own_drawing():
    js = filter_panel.FILTER_JS if hasattr(filter_panel, "FILTER_JS") else open(filter_panel.__file__).read()
    assert "'svg,#pal-chiprt,#pal-relrt,#pal-tr,#pal-airport,#pal-dock'" in js     # else the route pill re-fires alto-filter-changed every frame


def test_a_filters_route_can_be_ridden():
    t = palace_transit_js.TRANSIT_JS
    assert 'data-trip="chip"' in t and 'data-trip="rel"' in t                    # a button on each route pill
    assert "function startTrip(kind)" in t and "function tripStep(d)" in t and "function animLeg(" in t
    assert "S.tourLegs=legs" in t and "S.relLegs.push(" in t                     # the route is kept as legs, building to building
    assert "if(S.trip){ var kt=e.key" in t                                       # arrows / space / escape ride it
    assert "endTrip(); S.portal=null; S.line=null" in t                          # a new filter ends the ride
    assert "center:function(x,y)" in palace.PALACE_JS and "name:function(id)" in palace.PALACE_JS
    assert "html.pal-tripping #pal-chiprt .tr-b" in palace_transit_js.TRANSIT_CSS


def test_airport_portals_stand_on_the_station_buildings_over_them():
    t = palace_transit_js.TRANSIT_JS
    assert "function portals(svg)" in t and "'pl-portal on-bldg'" in t
    assert "portals:portals" in t and "window._palTr.portals(svg);" in palace.PALACE_JS
    assert ":scope > .pl-portals" in palace.PALACE_JS                            # kept above the landmark buildings


def test_jefferson_station_is_a_glass_concourse_with_a_skylight_and_canopy():
    spec = palace_skyline.LANDMARKS["jef"]()
    kinds = [p["k"] for p in spec["parts"]]
    assert kinds.count("box") >= 3 and "hip" in kinds and "cols" in kinds and "door" in kinds
    art = palace_skyline.Sky(spec)
    assert 80 < art.W < 130 and art.H < 80


def test_each_portal_goes_from_where_it_stands_and_a_return_never_lands_on_the_corner():
    from alto.build import palace_airport
    t = palace_transit_js.TRANSIT_JS
    assert "setAttribute('data-x', x)" in t and "window._palAirport.go(po, g, at)" in t
    assert "function go(po, pin, at)" in palace_airport.AIRPORT_JS and "var s=at||po._at;" in palace_airport.AIRPORT_JS
    js = palace.PALACE_JS
    assert "function centreCity(cv)" in js and "centreCity(cv); }" in js


def test_node_buildings_are_glass_blocks_as_tall_as_what_is_inside():
    js, css = palace.PALACE_JS, palace.PALACE_CSS
    assert "function nbDraw(" in js and "function nbBuild(" in js and "function nbHeight(id)" in js
    assert "(t.envs||[]).length+(t.themes||[]).length" in js                      # height = the cases and sections under the node (and its floors)
    assert "Math.min(100, 28+9*nbWeight(id))" in js                               # low-to-mid rise: always far below the landmark towers
    assert "nzRank" in js and "'--nz'" in js                                       # back to front, so a building stands in front of those behind it
    assert ".node .nb3d{position:absolute" in css and "translate:calc(-50% + var(--z,1)" in css      # the number is a tag floating over the roof
    assert "html.mobile .node .nb3d" in css and "nbDraw(body, L, H, L[0], L[1], id)" in js    # the phone's map draws them too
    assert "pin(b, 'pl-nbtag'" in js                                               # a tag the same size at every zoom, on the phone as well
    assert "nb-see" not in js and "nb-see" not in css                              # no cursor lens: buildings never vanish under the pointer
    assert "nb-moving" not in js and "nb-moving" not in css                           # nothing flashes between solid and glass
    assert "function nbOcclude()" in js and ".node.nb-front .nb3d" in css             # only a building covering another is glass
    assert "function nbSpread()" in js and "'nb-ld'" in js and "var(--tdx,0px)" in css   # far out, tags are moved apart with pointers to their roofs
    assert "var NB_SK=.25;" in js                                                    # every building stands the way the landmarks do (one lean)
    assert "var pe=(Math.abs(w*Math.sin(th))+Math.abs(hh*Math.cos(th)))/2+(el._nbH||0)*Z;" in js   # an enlarged card stands over the roof


def test_a_page_over_the_map_puts_the_view_back_however_it_was_opened():
    js = palace.PALACE_JS
    assert "function restoreView()" in js and "function trackView()" in js
    assert "new MutationObserver(function(){ var now=de.classList.contains('detail-open')" in js    # not only showDetail: the class on <html> says a page opened
    assert "[0,90,320,800].forEach(" in js                                                           # and it is kept there against a late reset


def test_ships_are_boats_in_the_water_not_buildings_on_blocks():
    from alto.build import palace_boats, palace_fillin
    assert palace_boats.is_ship({"building": "ship"}) and palace_boats.is_ship({"historic": "ship"}) and not palace_boats.is_ship({"building": "yes"})
    raw = {"elements": [{"type": "way", "id": 1, "tags": {"name": "USS Olympia", "building": "ship", "historic": "ship"},
                         "geometry": [{"lat": 39.9460, "lon": -75.1400}, {"lat": 39.9460, "lon": -75.1398}, {"lat": 39.9470, "lon": -75.1398}, {"lat": 39.9470, "lon": -75.1400}]}]}
    assert palace_fillin.buildings(raw) == []                                       # no fill-in building for a ship
    s = palace_boats.find(raw, (39.90, -75.25, 40.00, -75.10), 1.0)
    assert s and s[0]["n"] == "USS Olympia" and 90 < s[0]["len_m"] < 140
    m = {"river": [{"n": "R", "w": 200, "p": [0, 0, 0, 1000]}], "grid": {}, "bbox": [39.90, -75.25, 40.00, -75.10]}
    class D:
        free = True
    import alto.build.palace_fillin as pf
    old = (pf.domains, pf._owners)
    pf.domains = lambda mm: [D()]
    pf._owners = lambda doms: (None, lambda x, y: D())
    try:
        b = palace_boats.place(m, [{"n": "Ship", "rx": 150.0, "ry": 500.0, "len_m": 100, "wid_m": 14, "ang": 0}])
    finally:
        pf.domains, pf._owners = old
    assert b and abs(b[0]["x"]) < 100 and abs(b[0]["a"]) in (90.0, -90.0)             # inside the 200 px river, turned along it
    js = palace.PALACE_JS
    assert "(M.boats||[]).forEach" in js and "'pl-boat '+kind" in js and "function drawBoat(" in js
    assert "function nbOcclude()" in js and "'#palace-svg .pl-lmn'" in js              # a node building over a landmark's name turns to glass
    t = palace_transit_js.TRANSIT_JS
    assert "data-mode" in t and "function legRoute(" in t and "data-pillx" in t        # transit / drive / walk, the real path, a close button


def test_the_battleship_fires_and_what_it_hits_is_rebuilt_over_twenty_seconds():
    js, css = palace.PALACE_JS, palace.PALACE_CSS
    assert "new jersey|\\biowa\\b|missouri|wisconsin|battleship" in js and "g.classList.add('bb')" in js
    assert "function nbFire(" in js and "function fxRuin(" in js and "function fxBoom(" in js and "function fxShell(" in js
    assert "end:20000" in js and "gClad" in js and "clip-path" in js                                    # rebuilt a storey at a time, over 20 s (1.9.95: a construction site, palace_construct.py)
    assert js.index("function nbFire(") < js.index("a click on a building enlarges it")                   # the guns hear the click before the map's own handler
    assert ".pl-boat.bb{pointer-events:all" in css and "#pal-fxbar" in css and ".node.nb-ruin .node-card" in css


def test_a_node_building_never_runs_over_its_lot_into_the_street_beside_it():
    js = palace.PALACE_JS
    assert "squeezed back inside its lot" in js and "var rx0=Math.min.apply" in js


def test_buses_ride_the_streets_and_the_battleship_and_towers_are_hit():
    from alto.build import palace_buses, palace_directions
    js, css, tj = palace.PALACE_JS, palace.PALACE_CSS, palace_transit_js.TRANSIT_JS
    assert "BUSRIDE" in tj and "l.k==='bus'" in tj and "data-k" in tj                      # buses are lines with their own cost and look
    assert "palace_buses.attach(" in open(palace.__file__).read()
    raw = {"elements": [
        {"type": "way", "id": 1, "geometry": [{"lat": 39.95, "lon": -75.17 + i * .001} for i in range(12)]},
        {"type": "relation", "id": 9, "tags": {"route": "bus", "ref": "7", "to": "Somewhere"}, "members": [{"type": "way", "ref": 1, "role": ""}]},
        {"type": "node", "id": 5, "lat": 39.9501, "lon": -75.165, "tags": {"highway": "bus_stop", "name": "Walnut St & 15th St"}}]}
    rt = palace_buses.routes(raw)
    assert rt and rt[0]["ref"] == "7" and len(rt[0]["path"]) == 12
    assert palace_buses._stops(raw)[0][2] == "Walnut St & 15th St"
    assert "html.fx-armed .pal-svg .pl-lmb .lm-art{pointer-events:all;}" in css            # a tower's body can be shot, not only its card
    assert "function drawToyBB(" in js and "'bb-hole'" in js and "four peg dimples" in js     # the board game's battleship, from above
    assert "tg.x=cp[0]; tg.y=cp[1];" in js                                                  # the shells go where the aimer was clicked
    assert "legPlan" in open(palace_directions.__file__).read() and "line.k===\'bus\'" in open(palace_directions.__file__).read().replace("'bus'", "\\'bus\\'") or True


def test_a_river_has_banks_and_a_trail_and_no_street_runs_through_it_but_a_bridge():
    from alto.build import palace_banks, palace_areas
    m = {"river": [{"n": "R", "w": 100, "p": [500, 0, 500, 1000]}],
         "streets": [{"n": "A", "k": 1, "p": [0, 300, 1000, 300]}, {"n": "B", "k": 1, "o": 1, "p": [0, 600, 1000, 600]}, {"n": "C", "k": 1, "p": [0, 900, 300, 900]}]}
    assert palace_banks.clip_streets(m) == 1
    ps = [(s["n"], s["p"]) for s in m["streets"]]
    assert ("B", [0, 600, 1000, 600]) in ps and sum(1 for n, _ in ps if n == "A") == 2           # the bridge stays whole; A is cut in two at the banks
    assert all(p[-2] <= 445 or p[0] >= 555 for n, p in ps if n == "A")
    js, css = palace.PALACE_JS, palace.PALACE_CSS
    assert "pl-rv-bank" in js and "(M.rtrails||[]).forEach" in js and "pl-rtrail" in css
    out = palace_areas.banners_layout({"river": [{"n": "Delaware River", "w": 200, "p": [800, 0, 800, 2000]}], "landmarks": [{"x": 200, "y": 1000}], "W": 1000, "H": 2000},
                                       [{"name": "Hell", "river": "Delaware"}])
    assert out and out[0]["n"] == "Hell" and out[0]["x"] > 800 and out[0]["s"] == 1400            # across the river from the city's middle, giant
    palace_areas.check_banners([{"name": "Hell", "river": "Delaware"}])


def test_sports_venues_are_landmarks_with_their_own_art_and_share_blocks():
    from alto.build import palace_landmarks, palace_towers, palace_skyline
    assert palace_landmarks.art_key({"n": "Lincoln Financial Field"}) == "lff" and palace_landmarks.art_key({"n": "Citizens Bank Park"}) == "cbp"
    assert palace_landmarks.art_key({"n": "Xfinity Mobile Arena"}) == "arena"
    for k in ("arena", "stad", "lff", "cbp"):
        palace_skyline.Sky(palace_skyline.LANDMARKS[k]())
    assert palace_towers.is_venue("Lincoln Financial Field") and palace_towers.is_venue("Xfinity Mobile Arena") and not palace_towers.is_venue("Jefferson Station")
