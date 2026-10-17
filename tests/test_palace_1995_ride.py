"""1.9.95: the first-person ride (alto/build/palace_ride*.py): source assertions and cheap checks (the runtime is checked by the QA kit in _qa/ride95_kit)."""
import re
import shutil
import subprocess
from pathlib import Path

from alto.build import palace, palace_ride, palace_transit_js


def _js():
    return palace_ride.RIDE_JS


def test_the_ride_is_loaded_by_the_page_and_hooked_in_one_line_each():
    assert "window._palRide.init(" in palace.PALACE_JS and palace_ride.RIDE_LOADER in palace.PALACE_JS and palace_ride.RIDE_JS not in palace.PALACE_JS
    assert "#pal-ride{" not in palace.PALACE_CSS and "#pal-ride{" in palace_ride.RIDE_ASSET       # (its rules ride in the hosted asset)
    t = palace_transit_js.TRANSIT_JS
    assert "window._palRide.leg(leg, rev, function(x,y)" in t          # animLeg: first-person beside the map ride, not instead of it
    assert "window._palRide.mark()" in t and "window._palRide.exit()" in t
    assert "rr.lineEnter(id, i)" in t and "window._palRide.lineStep(" in t     # a line's own ride
    assert "window._palRide.switchHtml()" in t                              # the button in the trip panel
    assert "function animLeg(leg, rev, done)" in t and "var p=el('path',{d:leg.d" in t   # animLeg itself is intact


def test_underground_comes_from_the_transit_data_and_known_lines():
    js = _js()
    assert "line.u" in js and "ugNear(" in js                               # the trolley's own tunnel pieces (palace_transit.py "u")
    for line in ("mfl:", "bsl:", "brs:", "pat:", "rr :", "trl:"):
        assert line in js
    assert "/portal/i.test(" in js                                         # a portal stop ends the tunnel exactly there


def test_the_modes_have_their_own_vehicle_window():
    js = _js()
    for fn in ("frameMetro", "frameTram", "frameRail", "frameBus", "frameCar", "frameWalk"):
        assert "function %s(" % fn in js
    assert "var FRAMES={metro:frameMetro, tram:frameTram, rail:frameRail, bus:frameBus, car:frameCar, walk:frameWalk};" in js
    assert "VEH={" in js and "walk :{" in js and "bob" in js


def test_the_tunnel_never_flashes_faster_than_three_a_second():
    js = _js()
    vals = dict(re.findall(r"(RING_HZ|MAX_FLASH_HZ|BAR_HZ|HUE_DPS)=([0-9.]+)", js))
    assert float(vals["RING_HZ"]) < float(vals["MAX_FLASH_HZ"]) <= 3        # a ring passes a given pixel at most RING_HZ times a second
    assert float(vals["BAR_HZ"]) <= 1
    assert "hz=RING_HZ*(" in js and "BAR_HZ" in js
    assert "T.reduce" in js                                                 # reduced motion: a still, calm frame
    # no hard on-off bars: the light bars are sin^2 waves, never a toggled flag
    assert "al=al*al" in js


def test_a_ride_takes_six_to_thirty_seconds_and_the_ends_are_at_the_doors():
    js = _js()
    assert "clamp(t,M.minT||6,30)" in js
    assert "function trimEnds(" in js and "lotRing(meta.a" in js


def test_first_person_is_a_remembered_choice_with_a_key_and_a_button():
    js = _js()
    assert "alto-palace-ride-view" in js and "return 'fp'" in js            # default first-person
    assert "e.key!=='v' && e.key!=='V'" in js
    assert "data-ride=\"view\"" in js or "data-ride=\\\"view\\\"" in js or 'data-ride="view"' in js
    assert "Map view" in js and "Exit ride" in js
    css = palace_ride.RIDE_CSS
    assert "html.pal-fp #pal-tr{z-index:420" in css and "backdrop-filter:none" in css   # no blur over a moving canvas
    assert "html.mobile #pal-ride" in css and "prefers-reduced-motion" in css


def test_exit_puts_the_map_back_the_way_it_was():
    js = _js()
    assert "E.putView(view)" in js and "E.curView" in js
    p = palace.PALACE_JS
    assert "putView:function(v){ if(!v) return; holdView={z:v.z, x:v.x, y:v.y}; restoreView(); }" in p   # the existing restoreView pattern
    assert "keep" in js and "closeNow(false, true)" in js                  # switching to the map view mid-trip keeps the saved view


def test_the_world_comes_from_the_pages_own_data():
    js = _js()
    for needle in ("Mp.tiles", "Mp.tq", "Mp.parks", "Mp.river", "P.at", "E.lot(", "E.fillGroups", "Mp.landmarks", "E.nbH("):
        assert needle in js
    assert "Math.random()*360" in js        # (only the tunnel's starting hue) ...
    assert js.count("Math.random") == 1     # ... nothing else in the ride is random


def test_the_rides_javascript_is_valid():
    node = shutil.which("node") or str(Path.home() / ".local/node/bin/node")
    if not Path(node).exists():
        return
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(palace_ride.RIDE_JS)
    r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
